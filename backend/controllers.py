"""Regulatory PID controllers — quarantined DCS control module.

Zero dependency on main.py or reactor.py.

Velocity I-PD increment (pre-direction sigma, pre-slew, pre-output-clamp):
    du_k = Kc * [-(PV_k - PV_{k-1}) + (dt/Ti)*(SP_k - PV_k) - Td*(PV_k - 2*PV_{k-1} + PV_{k-2})/dt]

Applied in Controller.step():
    du_k <- clamp(sigma * du_k, -rate*dt, +rate*dt)   slew limit
    u_k  <- clamp(u_{k-1} + du_k, u_lo, u_hi)         output clamp / anti-windup

sigma = +1 REVERSE action, -1 DIRECT action; Kc > 0 always.
"""
import math
from typing import Optional

BAD_PV_LO = -5.0    # % — below this PV is declared bad/failed
BAD_PV_HI = 105.0   # % — above this PV is declared bad/failed
CAS_BIAS_LIM = 100.0  # % — max |CAS bias| (full SP-span offset; P1-1 anti-saturation clamp)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class PID:
    """Velocity I-PD increment. P, D act on PV; I acts on error.
    Returns delta-u pre-direction (sigma), pre-slew, pre-output-clamp.
    Stores only PV_{k-1} and PV_{k-2} — no integral accumulator to wind up."""

    def __init__(self, Kc: float, Ti: float, Td: float = 0.0,
                 Tf: float = 0.0, Dz: float = 0.0):
        self.Kc = Kc
        self.Ti = Ti
        self.Td = Td
        self.Tf = Tf            # s, derivative 1st-order filter time (0 -> unfiltered, inert)
        self.Dz = Dz            # EU error deadzone half-width (0 -> no deadzone, inert)
        self._pv1: Optional[float] = None   # PV_{k-1}
        self._pv2: Optional[float] = None   # PV_{k-2}
        self._dfilt: float = 0.0            # G_{k-1}: filtered position-derivative (per-unit-Kc)

    def reset(self) -> None:
        """Clear PV history so next step is like a fresh start."""
        self._pv1 = None
        self._pv2 = None
        self._dfilt = 0.0

    def step(self, sp: float, pv: float, dt: float) -> float:
        """Compute delta-u = Kc*(P + I + D).
        First call seeds pv1=pv2=pv so P=D=0 (pure integral warmup).
        """
        if self._pv1 is None:
            self._pv1 = pv
        if self._pv2 is None:
            self._pv2 = pv

        p = -(pv - self._pv1)
        # Integral term with optional error deadzone (Dz=0 -> abs(err)<0 never true -> inert):
        err = sp - pv
        i = 0.0 if abs(err) < self.Dz else (dt / max(self.Ti, 1e-9)) * err
        # Derivative term. Tf<=0 -> legacy 2nd-difference velocity form (byte-identical, inert
        # default). Tf>0 -> 1st-order-filtered position-derivative G_k, velocity increment
        # d = G_k - G_{k-1}. Collapses EXACTLY to the legacy term as Tf->0 (unit-tested):
        #   G_k = Tf/(Tf+dt)*G_{k-1} - Td/(Tf+dt)*(PV_k-PV_{k-1}); Kc applied on return.
        if dt <= 0:
            d = 0.0
        elif self.Tf <= 0.0:
            d = -self.Td * (pv - 2.0 * self._pv1 + self._pv2) / dt
        else:
            g_prev = self._dfilt
            g_k = ((self.Tf / (self.Tf + dt)) * g_prev
                   - (self.Td / (self.Tf + dt)) * (pv - self._pv1))
            d = g_k - g_prev
            self._dfilt = g_k

        self._pv2 = self._pv1
        self._pv1 = pv
        return self.Kc * (p + i + d)


class Controller:
    """Velocity I-PD regulatory controller. Modes: MAN / AUTO / CAS / OOS.

    Operator writes: set_mode(), set_sp(), set_op(), set_bias(), set_tuning()
    Sim-tick writes: step(pv, dt, cas_sp) -> mv
    """

    def __init__(
        self,
        tag: str,
        *,
        Kc: float = 2.0,
        Ti: float = 8.0,
        Td: float = 0.0,
        Tf: float = 0.0,             # derivative filter time (0 -> inert); source: Constraint List
        Dz: float = 0.0,             # error deadzone half-width (0 -> inert); source: Constraint List
        action: str = "REVERSE",     # "REVERSE" sigma=+1  |  "DIRECT" sigma=-1
        op_lo: float = 0.0,
        op_hi: float = 100.0,
        sp_lo: float = 0.0,
        sp_hi: float = 100.0,
        rate: float = 10.0,          # max output slew rate (%/s)
        fail_action: str = "FC",     # "FC" -> op_lo | "FO" -> op_hi | "FL" -> freeze
        sp: Optional[float] = None,  # initial SP (defaults to midrange)
        mv: Optional[float] = None,  # initial MV (defaults to op_lo)
    ):
        self.tag = tag
        self.action = action
        self.op_lo, self.op_hi = op_lo, op_hi
        self.sp_lo, self.sp_hi = sp_lo, sp_hi
        self.rate = rate
        self.fail_action = fail_action
        self._pid = PID(Kc=Kc, Ti=Ti, Td=Td, Tf=Tf, Dz=Dz)

        self.mode: str = "MAN"
        self.sp: float = sp if sp is not None else (sp_lo + sp_hi) / 2.0
        self.mv: float = mv if mv is not None else op_lo
        self.pv: float = 0.0
        self.bias: float = 0.0
        self.cas_sp: Optional[float] = None

        self._pv_bad: bool = False
        self._mv_hi_clamp: bool = False
        self._mv_lo_clamp: bool = False

    # -- tuning read-back
    @property
    def Kc(self) -> float: return self._pid.Kc
    @property
    def Ti(self) -> float: return self._pid.Ti
    @property
    def Td(self) -> float: return self._pid.Td
    @property
    def Tf(self) -> float: return self._pid.Tf
    @property
    def Dz(self) -> float: return self._pid.Dz

    def _sigma(self) -> float:
        return 1.0 if self.action == "REVERSE" else -1.0

    def _fail_target(self) -> float:
        if self.fail_action == "FC": return self.op_lo
        if self.fail_action == "FO": return self.op_hi
        return self.mv   # FL: freeze at current mv

    # -- operator command methods (called under _ctrl_lock from REST routes)

    def set_mode(self, mode: str) -> None:
        if mode not in ("MAN", "AUTO", "CAS", "OOS"):
            raise ValueError(f"unknown mode {mode!r}")
        if mode == "AUTO" and self.mode != "AUTO":
            # Bumpless AUTO entry: SP adopts current PV
            self.sp = _clamp(self.pv, self.sp_lo, self.sp_hi)
            self._pid.reset()
        if mode == "CAS" and self.mode != "CAS":
            # Bumpless CAS entry: zero bias, reset PID history
            self.bias = 0.0
            self._pid.reset()
        self.mode = mode

    def set_sp(self, v: float) -> None:
        """Clamps to [sp_lo, sp_hi]. Legal in AUTO only (enforced by route handler)."""
        self.sp = _clamp(v, self.sp_lo, self.sp_hi)

    def set_op(self, v: float) -> None:
        """Clamps to [op_lo, op_hi]. Legal in MAN only (enforced by route handler)."""
        self.mv = _clamp(v, self.op_lo, self.op_hi)

    def set_bias(self, v: float) -> None:
        """CAS bias n_c (%). Clamped to +/-CAS_BIAS_LIM (P1-1 anti-saturation).
        Legal in CAS only (enforced by route handler)."""
        self.bias = _clamp(v, -CAS_BIAS_LIM, CAS_BIAS_LIM)

    def set_tuning(self, *, Kc: Optional[float] = None,
                   Ti: Optional[float] = None, Td: Optional[float] = None,
                   Tf: Optional[float] = None, Dz: Optional[float] = None) -> None:
        """Bumpless tuning update. Legal in any mode."""
        if Kc is not None: self._pid.Kc = Kc
        if Ti is not None: self._pid.Ti = Ti
        if Td is not None: self._pid.Td = Td
        if Tf is not None: self._pid.Tf = Tf
        if Dz is not None: self._pid.Dz = Dz

    # -- sim tick (called from step_sim under _ctrl_lock)

    def step(self, pv: Optional[float], dt: float,
             cas_sp: Optional[float] = None) -> float:
        """Advance one simulation tick. Returns current MV (%)."""
        # Bad-PV guard: None, NaN, or outside [-5, 105]% -> fail-freeze
        bad = (pv is None
               or (isinstance(pv, float) and math.isnan(pv))
               or pv < BAD_PV_LO or pv > BAD_PV_HI)
        if bad:
            self._pv_bad = True
            if self.mode != "MAN":
                self.mode = "MAN"
                self._pid.reset()
            return self.mv   # freeze last-good MV

        self._pv_bad = False
        self.pv = pv
        self.cas_sp = cas_sp
        slew_max = self.rate * dt

        if self.mode == "MAN":
            pass   # mv held; operator uses set_op()

        elif self.mode == "AUTO":
            raw = self._sigma() * self._pid.step(self.sp, pv, dt)
            delta = _clamp(raw, -slew_max, slew_max)
            new_mv = _clamp(self.mv + delta, self.op_lo, self.op_hi)
            self._mv_hi_clamp = (new_mv >= self.op_hi)
            self._mv_lo_clamp = (new_mv <= self.op_lo)
            self.mv = new_mv

        elif self.mode == "CAS":
            if cas_sp is not None:
                self.sp = _clamp(cas_sp + self.bias, self.sp_lo, self.sp_hi)
            raw = self._sigma() * self._pid.step(self.sp, pv, dt)
            delta = _clamp(raw, -slew_max, slew_max)
            new_mv = _clamp(self.mv + delta, self.op_lo, self.op_hi)
            self._mv_hi_clamp = (new_mv >= self.op_hi)
            self._mv_lo_clamp = (new_mv <= self.op_lo)
            self.mv = new_mv

        elif self.mode == "OOS":
            target = self._fail_target()
            delta = _clamp(target - self.mv, -slew_max, slew_max)
            self.mv = _clamp(self.mv + delta, self.op_lo, self.op_hi)

        return self.mv

    def to_packet(self) -> dict:
        """Serialise controller state to WebSocket packet block."""
        return {
            "mode": self.mode,
            "pv":   self.pv,
            "sp":   self.sp,
            "mv":   self.mv,
            "cas_sp": self.cas_sp,
            "bias": self.bias,
            "action": self.action,
            "tuning": {
                "Kc": self._pid.Kc,
                "Ti": self._pid.Ti,
                "Td": self._pid.Td,
                "Tf": self._pid.Tf,
                "Dz": self._pid.Dz,
            },
            "limits": {
                "op_lo": self.op_lo, "op_hi": self.op_hi,
                "sp_lo": self.sp_lo, "sp_hi": self.sp_hi,
                "rate":  self.rate,
            },
            "fail_action": self.fail_action,
            "status": {
                "pv_bad":      self._pv_bad,
                "mv_hi_clamp": self._mv_hi_clamp,
                "mv_lo_clamp": self._mv_lo_clamp,
            },
        }
