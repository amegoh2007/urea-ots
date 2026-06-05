# Control-Loop Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `backend/controllers.py` (velocity I-PD, MAN/AUTO/CAS/OOS, slew, bad-PV fail-freeze) and wire REST + WebSocket controller transport into `backend/main.py`.

**Architecture:** New quarantined module `controllers.py` (zero dependency on `main.py`) exposes `PID` (pure velocity I-PD math) and `Controller` (mode state machine + slew + clamp). `main.py` deletes its legacy positional-form PID/Controller classes, imports the new ones, adds a `state.controllers` registry dict, ticks controllers under a `threading.Lock`, emits a `controllers` block in the WebSocket packet, and registers REST routes `POST/GET /api/ctrl/{tag}` with Pydantic `CtrlCommand` validation.

**Tech Stack:** Python 3.x · FastAPI · Pydantic (already in venv) · `threading.Lock` · FastAPI `TestClient` for route tests · plain-assert test pattern (`python test_x.py`, NOT pytest)

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| **Create** | `backend/controllers.py` | `PID` velocity I-PD math; `Controller` 4-mode state machine |
| **Create** | `backend/test_controllers.py` | Unit tests for `PID` + `Controller` (all modes, bad-PV, to_packet) |
| **Create** | `backend/test_ctrl_routes.py` | Integration tests for REST `POST/GET /api/ctrl/{tag}` |
| **Modify** | `backend/main.py:33` | Add `HTTPException` to FastAPI import |
| **Modify** | `backend/main.py:34–35` | Add `from pydantic import BaseModel`, `import threading`, `from controllers import Controller` |
| **Modify** | `backend/main.py:675–728` | Delete legacy `PID` + `Controller` classes |
| **Modify** | `backend/main.py:745–746` | `mode_tag()` — add OOS→"O" mapping |
| **Modify** | `backend/main.py:778–779` | `State.__init__` — update Controller constructor signature |
| **Modify** | `backend/main.py` after L779 | Add `self.controllers` registry + `_ctrl_lock` after `state = State()` |
| **Modify** | `backend/main.py:860` | Pump loop: `ctrl.op` → `ctrl.mv` |
| **Modify** | `backend/main.py:1314–1328` | SIC packet blocks: `.op` → `.mv`, `.nc` → `.bias` |
| **Modify** | `backend/main.py:1330` | Add `"controllers"` block to packet |
| **Modify** | `backend/main.py:1354–1372` | `controller_set` handler: update set_mode call + attr names |
| **Modify** | `backend/main.py` after L1433 | Add `CtrlCommand` Pydantic model + REST route handlers |

---

## Task 1: `controllers.py` — PID class

**Files:**
- Create: `backend/controllers.py`
- Create: `backend/test_controllers.py`

- [ ] **Step 1: Write failing tests for `PID`**

Create `backend/test_controllers.py`:

```python
"""Unit tests for controllers.py velocity I-PD module.
Plain-assert, run directly: python test_controllers.py
"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from controllers import PID, Controller, BAD_PV_LO, BAD_PV_HI


def approx(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(b))


# ===== PID tests =====

def test_pid_pure_integral_first_step():
    """First step: pv1=pv2=pv, so P=D=0; Δu = Kc*(dt/Ti)*(sp-pv)."""
    pid = PID(Kc=1.0, Ti=10.0, Td=0.0)
    delta = pid.step(sp=80.0, pv=70.0, dt=1.0)
    expected = 1.0 * (1.0 / 10.0) * (80.0 - 70.0)   # = 1.0
    assert approx(delta, expected), f"got {delta}, want {expected}"


def test_pid_no_p_kick_on_sp_step():
    """SP step with PV frozen: P=D=0 (both on PV); only I responds."""
    pid = PID(Kc=2.0, Ti=8.0, Td=0.0)
    pv = 78.4
    pid.step(sp=80.0, pv=pv, dt=2.0)            # prime history
    delta = pid.step(sp=90.0, pv=pv, dt=2.0)    # SP jumps, PV frozen
    expected = 2.0 * (2.0 / 8.0) * (90.0 - pv)  # pure I
    assert approx(delta, expected), f"got {delta}, want {expected}"


def test_pid_d_term_on_pv_step():
    """PV step after settled: D = -Td*(pv-2*pv1+pv2)/dt fires."""
    pid = PID(Kc=1.0, Ti=1e9, Td=2.0)   # huge Ti -> only D+P active
    pid.step(sp=0.0, pv=0.0, dt=1.0)    # prime pv1=pv2=0
    pid.step(sp=0.0, pv=0.0, dt=1.0)    # confirm pv2=0, pv1=0
    delta = pid.step(sp=0.0, pv=1.0, dt=1.0)
    # P = -(1-0) = -1; I ≈ 0; D = -2*(1-0+0)/1 = -2 → delta = 1*(-3) = -3
    assert approx(delta, -3.0), f"got {delta}, want -3.0"


def test_pid_reset_clears_history():
    """reset() -> next step is pure integral (pv1=pv2=pv)."""
    pid = PID(Kc=1.0, Ti=10.0, Td=2.0)
    pid.step(sp=100.0, pv=50.0, dt=1.0)
    pid.step(sp=100.0, pv=60.0, dt=1.0)   # history: pv2=50, pv1=60
    pid.reset()
    delta = pid.step(sp=80.0, pv=70.0, dt=1.0)
    expected = 1.0 * (1.0 / 10.0) * (80.0 - 70.0)   # pure I after reset
    assert approx(delta, expected), f"got {delta}, want {expected}"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    fails = 0
    for t in tests:
        try:
            t(); print("PASS", t.__name__)
        except Exception:
            fails += 1; print("FAIL", t.__name__); traceback.print_exc()
    raise SystemExit(1 if fails else 0)
```

- [ ] **Step 2: Run — confirm ImportError (module doesn't exist yet)**

```
cd D:\Work\Urea Simulation\backend
python test_controllers.py
```
Expected: `ModuleNotFoundError: No module named 'controllers'`

- [ ] **Step 3: Create `backend/controllers.py` with `PID` class**

```python
"""Regulatory PID controllers — quarantined DCS control module.

Zero dependency on main.py or reactor.py.

Velocity I-PD increment (pre-direction σ, pre-slew, pre-output-clamp):
    Δu_k = Kc·[−(PV_k−PV_{k−1}) + (Δt/Ti)·(SP_k−PV_k) − Td·(PV_k−2·PV_{k−1}+PV_{k−2})/Δt]
Applied in Controller.step():
    Δu_k ← clamp(σ·Δu_k, −ṙ·Δt, +ṙ·Δt)          slew limit
    u_k  ← clamp(u_{k−1}+Δu_k, u_lo, u_hi)         output clamp / anti-windup
σ = +1 REVERSE action, −1 DIRECT action; Kc > 0 always.
"""
import math
from typing import Optional

BAD_PV_LO = -5.0    # % — below this PV is declared bad/failed
BAD_PV_HI = 105.0   # % — above this PV is declared bad/failed


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class PID:
    """Velocity I-PD increment. P, D act on PV; I acts on error.
    Returns Δu pre-direction (σ), pre-slew, pre-output-clamp.
    Stores only PV_{k-1} and PV_{k-2} — no integral accumulator to wind up."""

    def __init__(self, Kc: float, Ti: float, Td: float = 0.0):
        self.Kc = Kc
        self.Ti = Ti
        self.Td = Td
        self._pv1: Optional[float] = None   # PV_{k-1}
        self._pv2: Optional[float] = None   # PV_{k-2}

    def reset(self) -> None:
        """Clear PV history so next step is like a fresh start."""
        self._pv1 = None
        self._pv2 = None

    def step(self, sp: float, pv: float, dt: float) -> float:
        """Compute Δu = Kc·(P + I + D).
        First call seeds pv1=pv2=pv so P=D=0 (pure integral warmup).
        """
        if self._pv1 is None:
            self._pv1 = pv
        if self._pv2 is None:
            self._pv2 = pv

        p = -(pv - self._pv1)
        i = (dt / max(self.Ti, 1e-9)) * (sp - pv)
        d = (-self.Td * (pv - 2.0 * self._pv1 + self._pv2) / dt
             if dt > 0 else 0.0)

        self._pv2 = self._pv1
        self._pv1 = pv
        return self.Kc * (p + i + d)
```

- [ ] **Step 4: Run tests — confirm PID tests pass, Controller tests fail**

```
python test_controllers.py
```
Expected:
```
PASS test_pid_pure_integral_first_step
PASS test_pid_no_p_kick_on_sp_step
PASS test_pid_d_term_on_pv_step
PASS test_pid_reset_clears_history
```
(Controller tests not yet in file — all 4 PID tests pass.)

- [ ] **Step 5: Commit**

```
git -C "D:\Work\Urea Simulation" add backend/controllers.py backend/test_controllers.py
git -C "D:\Work\Urea Simulation" commit -m "$(cat <<'EOF'
feat(controllers): PID velocity I-PD class + unit tests

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `controllers.py` — Controller class (all modes + bad-PV + to_packet)

**Files:**
- Modify: `backend/controllers.py` (append Controller class)
- Modify: `backend/test_controllers.py` (append Controller tests)

- [ ] **Step 1: Append Controller tests to `test_controllers.py`**

Insert before `if __name__ == "__main__":`:

```python
# ===== Controller — MAN mode =====

def test_ctrl_man_mv_frozen():
    """MAN: step() does not change mv."""
    c = Controller("TAG", mv=50.0)
    mv = c.step(pv=70.0, dt=2.0)
    assert approx(mv, 50.0), f"mv frozen at 50, got {mv}"


def test_ctrl_man_set_op_clamps():
    """set_op() clamps to [op_lo, op_hi]."""
    c = Controller("TAG", op_lo=10.0, op_hi=90.0, mv=50.0)
    c.set_op(200.0)
    assert approx(c.mv, 90.0), f"should clamp to 90, got {c.mv}"
    c.set_op(5.0)
    assert approx(c.mv, 10.0), f"should clamp to 10, got {c.mv}"


# ===== Controller — AUTO mode =====

def test_ctrl_auto_entry_sp_tracks_pv():
    """AUTO entry: SP ← PV (bumpless)."""
    c = Controller("TAG", sp=80.0, mv=50.0)
    c.pv = 65.3
    c.set_mode("AUTO")
    assert approx(c.sp, 65.3), f"sp should snap to pv, got {c.sp}"


def test_ctrl_auto_mv_rises_toward_sp():
    """AUTO REVERSE: positive error drives mv up over multiple steps."""
    c = Controller("TAG", Kc=2.0, Ti=8.0, action="REVERSE", mv=40.0)
    c.set_mode("AUTO")
    c.sp = 80.0   # override bumpless snap
    mv0 = c.mv
    for _ in range(30):
        c.step(pv=40.0, dt=2.0)   # error = 40 -> mv should rise
    assert c.mv > mv0 + 1.0, f"mv={c.mv:.2f} should rise from {mv0}"


def test_ctrl_auto_slew_limited():
    """AUTO: single-step MV change ≤ rate * dt regardless of Kc."""
    c = Controller("TAG", Kc=500.0, Ti=0.01, rate=5.0, mv=50.0)
    c.set_mode("AUTO")
    c.sp = 90.0
    mv_before = c.mv
    c.step(pv=10.0, dt=2.0)
    assert abs(c.mv - mv_before) <= 5.0 * 2.0 + 1e-9, \
        f"slew {abs(c.mv - mv_before):.3f} > rate*dt=10"


def test_ctrl_auto_direct_action():
    """AUTO DIRECT (σ=-1): positive error drives mv DOWN."""
    c = Controller("TAG", Kc=2.0, Ti=8.0, action="DIRECT", mv=60.0)
    c.set_mode("AUTO")
    c.sp = 80.0
    mv0 = c.mv
    for _ in range(30):
        c.step(pv=40.0, dt=2.0)   # error = 40, DIRECT -> mv falls
    assert c.mv < mv0 - 1.0, f"mv={c.mv:.2f} should fall from {mv0} (DIRECT)"


# ===== Controller — CAS mode =====

def test_ctrl_cas_entry_bias_resets():
    """CAS entry: bias resets to 0."""
    c = Controller("TAG", mv=50.0)
    c.bias = 3.5
    c.pv = 70.0
    c.set_mode("CAS")
    assert approx(c.bias, 0.0), f"bias should reset to 0, got {c.bias}"


def test_ctrl_cas_sp_from_cas_sp_plus_bias():
    """CAS: SP = clamp(cas_sp + bias, sp_lo, sp_hi)."""
    c = Controller("TAG", sp_lo=0.0, sp_hi=100.0, mv=50.0)
    c.pv = 50.0
    c.set_mode("CAS")
    c.bias = 2.0
    c.step(pv=50.0, dt=1.0, cas_sp=70.0)
    assert approx(c.sp, 72.0), f"sp should be 72.0, got {c.sp}"


def test_ctrl_cas_sp_clamps_at_sp_hi():
    """CAS: SP clamps at sp_hi when cas_sp + bias exceeds it."""
    c = Controller("TAG", sp_lo=0.0, sp_hi=100.0, mv=50.0)
    c.pv = 50.0
    c.set_mode("CAS")
    c.bias = 10.0
    c.step(pv=50.0, dt=1.0, cas_sp=95.0)
    assert approx(c.sp, 100.0), f"sp should clamp at 100, got {c.sp}"


# ===== Controller — OOS mode =====

def test_ctrl_oos_fc_strokes_to_zero():
    """OOS + FC: mv strokes toward 0 at slew rate; reaches 0 after enough steps."""
    c = Controller("TAG", fail_action="FC", rate=5.0, mv=80.0)
    c.pv = 80.0
    c.set_mode("OOS")
    for _ in range(100):
        c.step(pv=80.0, dt=2.0)
    assert approx(c.mv, 0.0, tol=1e-6), f"mv should reach 0 (FC), got {c.mv}"


def test_ctrl_oos_fo_strokes_to_100():
    """OOS + FO: mv strokes toward 100."""
    c = Controller("TAG", fail_action="FO", rate=5.0, mv=20.0)
    c.pv = 20.0
    c.set_mode("OOS")
    for _ in range(100):
        c.step(pv=20.0, dt=2.0)
    assert approx(c.mv, 100.0, tol=1e-6), f"mv should reach 100 (FO), got {c.mv}"


def test_ctrl_oos_fl_freezes_mv():
    """OOS + FL: mv stays at entry value."""
    c = Controller("TAG", fail_action="FL", rate=5.0, mv=63.5)
    c.pv = 63.5
    c.set_mode("OOS")
    for _ in range(20):
        c.step(pv=63.5, dt=2.0)
    assert approx(c.mv, 63.5), f"mv should freeze at 63.5 (FL), got {c.mv}"


def test_ctrl_oos_slew_rate():
    """OOS FC: single-step change ≤ rate*dt."""
    c = Controller("TAG", fail_action="FC", rate=5.0, mv=80.0)
    c.pv = 80.0
    c.set_mode("OOS")
    mv_before = c.mv
    c.step(pv=80.0, dt=2.0)
    assert abs(c.mv - mv_before) <= 5.0 * 2.0 + 1e-9, \
        f"slew {abs(c.mv - mv_before):.3f} > rate*dt=10"


# ===== Controller — bad-PV fail-freeze =====

def test_bad_pv_none_forces_man_freezes_mv():
    """PV=None: mode falls to MAN, mv frozen, pv_bad set."""
    c = Controller("TAG", mv=60.0)
    c.set_mode("AUTO")
    mv = c.step(pv=None, dt=2.0)
    assert c.mode == "MAN", f"mode should be MAN, got {c.mode}"
    assert c._pv_bad is True
    assert approx(mv, 60.0), f"mv frozen at 60, got {mv}"


def test_bad_pv_nan():
    """PV=NaN: pv_bad flagged."""
    c = Controller("TAG", mv=55.0)
    c.set_mode("AUTO")
    c.step(pv=float("nan"), dt=2.0)
    assert c._pv_bad is True
    assert c.mode == "MAN"


def test_bad_pv_out_of_range():
    """PV outside [-5, 105]: pv_bad flagged."""
    c = Controller("TAG", mv=50.0)
    c.set_mode("AUTO")
    c.step(pv=110.0, dt=2.0)
    assert c._pv_bad is True
    assert c.mode == "MAN"


def test_bad_pv_recovery_stays_man():
    """Good PV after bad: pv_bad clears but mode stays MAN — operator re-engages."""
    c = Controller("TAG", mv=50.0)
    c.set_mode("AUTO")
    c.step(pv=None, dt=2.0)       # trigger bad-PV
    assert c._pv_bad is True
    c.step(pv=70.0, dt=2.0)       # good PV
    assert c._pv_bad is False
    assert c.mode == "MAN"         # operator must manually re-engage


# ===== to_packet() =====

def test_to_packet_schema():
    """to_packet() includes all required keys per WS schema."""
    c = Controller("SIC_321951", Kc=2.0, Ti=8.0, sp=80.0, mv=42.1)
    pkt = c.to_packet()
    for key in ("mode", "pv", "sp", "mv", "cas_sp", "bias", "action",
                "tuning", "limits", "fail_action", "status"):
        assert key in pkt, f"missing key {key!r}"
    assert "Kc" in pkt["tuning"] and "Ti" in pkt["tuning"] and "Td" in pkt["tuning"]
    assert "sp_lo" in pkt["limits"] and "sp_hi" in pkt["limits"]
    assert "pv_bad" in pkt["status"]


def test_to_packet_values():
    """to_packet() values round-trip correctly."""
    c = Controller("SIC_321951", Kc=2.0, Ti=8.0, Td=0.5,
                   sp=80.0, mv=42.1, action="REVERSE", fail_action="FC")
    pkt = c.to_packet()
    assert pkt["mode"] == "MAN"
    assert approx(pkt["mv"], 42.1)
    assert approx(pkt["sp"], 80.0)
    assert approx(pkt["tuning"]["Kc"], 2.0)
    assert approx(pkt["tuning"]["Td"], 0.5)
    assert pkt["action"] == "REVERSE"
    assert pkt["fail_action"] == "FC"
```

- [ ] **Step 2: Run — confirm Controller tests all fail (class not yet defined)**

```
python test_controllers.py
```
Expected: PID tests PASS; Controller tests FAIL with `ImportError` or `NameError`

- [ ] **Step 3: Append `Controller` class to `backend/controllers.py`**

```python
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
        action: str = "REVERSE",     # "REVERSE" σ=+1  |  "DIRECT" σ=-1
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
        self._pid = PID(Kc=Kc, Ti=Ti, Td=Td)

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
        """CAS bias n_c (%). Legal in CAS only (enforced by route handler)."""
        self.bias = v

    def set_tuning(self, *, Kc: Optional[float] = None,
                   Ti: Optional[float] = None, Td: Optional[float] = None) -> None:
        """Bumpless tuning update. Legal in any mode."""
        if Kc is not None: self._pid.Kc = Kc
        if Ti is not None: self._pid.Ti = Ti
        if Td is not None: self._pid.Td = Td

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
```

- [ ] **Step 4: Run all tests — confirm all pass**

```
python test_controllers.py
```
Expected (20 tests):
```
PASS test_pid_pure_integral_first_step
PASS test_pid_no_p_kick_on_sp_step
PASS test_pid_d_term_on_pv_step
PASS test_pid_reset_clears_history
PASS test_ctrl_man_mv_frozen
PASS test_ctrl_man_set_op_clamps
PASS test_ctrl_auto_entry_sp_tracks_pv
PASS test_ctrl_auto_mv_rises_toward_sp
PASS test_ctrl_auto_slew_limited
PASS test_ctrl_auto_direct_action
PASS test_ctrl_cas_entry_bias_resets
PASS test_ctrl_cas_sp_from_cas_sp_plus_bias
PASS test_ctrl_cas_sp_clamps_at_sp_hi
PASS test_ctrl_oos_fc_strokes_to_zero
PASS test_ctrl_oos_fo_strokes_to_100
PASS test_ctrl_oos_fl_freezes_mv
PASS test_ctrl_oos_slew_rate
PASS test_bad_pv_none_forces_man_freezes_mv
PASS test_bad_pv_nan
PASS test_bad_pv_out_of_range
PASS test_bad_pv_recovery_stays_man
PASS test_to_packet_schema
PASS test_to_packet_values
```

- [ ] **Step 5: Commit**

```
git -C "D:\Work\Urea Simulation" add backend/controllers.py backend/test_controllers.py
git -C "D:\Work\Urea Simulation" commit -m "$(cat <<'EOF'
feat(controllers): Controller class — MAN/AUTO/CAS/OOS + bad-PV fail-freeze + to_packet()

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `main.py` migration — delete legacy, update imports, State, pump loop, mode_tag, controller_set, packet

**Files:**
- Modify: `backend/main.py` (multiple surgical edits)

- [ ] **Step 1: Add imports (L33–35 region)**

Current L33:
```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
```
Replace with:
```python
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import threading
```

Add after L34 (after `from fastapi.staticfiles import StaticFiles`):
```python
from controllers import Controller
```

- [ ] **Step 2: Delete legacy PID + Controller classes (L675–728)**

Replace the entire block from `# ----- PID -----` through the trailing blank line before `# ----- Pump model -----`:

Old (L675–728):
```python
# ----- PID -----
class PID:
    def __init__(self, Kc=2.0, Ti=8.0, Td=0.0, op_lo=0.0, op_hi=100.0):
        self.Kc, self.Ti, self.Td = Kc, Ti, Td
        self.op_lo, self.op_hi = op_lo, op_hi
        self.integ, self.prev_e = 0.0, 0.0

    def step(self, sp, pv, dt):
        e = sp - pv
        self.integ += e * dt / max(self.Ti, 1e-6)
        self.integ = clamp(self.integ, -self.op_hi, self.op_hi)   # anti-windup
        d = (e - self.prev_e) / dt if dt > 0 else 0.0
        op = self.Kc * (e + self.integ + self.Td * d)
        op = clamp(op, self.op_lo, self.op_hi)
        self.prev_e = e
        return op


# ----- Controller / SIC faceplate -----
class Controller:
    """SIC on torque-converter valve opening (%).
       MAN : operator sets opening directly (PV entry -> op).
       AUTO: local SP% with PID.
       CAS : opening SP from ratio block + operator N/C bias (%).
       PV, SP, MV(op), N/C are all in percent."""

    def __init__(self, sp=80.0, op=0.0):
        self.mode = "MAN"
        self.sp   = sp     # % opening setpoint
        self.op   = op     # % opening output  (MV)
        self.pv   = 0.0    # % opening actual
        self.nc   = 0.0    # % cascade bias
        self.pid  = PID(Kc=2.0, Ti=8.0, op_lo=0.0, op_hi=100.0)

    def set_mode(self, mode, current_pv):
        if mode == "AUTO" and self.mode == "MAN":
            self.sp = current_pv          # bumpless: adopt current opening
        if mode == "CAS" and self.mode != "CAS":
            self.nc = 0.0                 # reset bias on cascade entry
        self.mode = mode

    def step(self, pv, dt, cas_sp=None):
        self.pv = pv
        if self.mode == "MAN":
            pass                          # op held by operator
        elif self.mode == "AUTO":
            self.op = self.pid.step(self.sp, pv, dt)
        elif self.mode == "CAS":
            if cas_sp is not None:
                self.sp = clamp(cas_sp + self.nc, 0.0, 100.0)
            self.op = self.pid.step(self.sp, pv, dt)
        return self.op

```

New (just a blank separator — pump model follows immediately):
```python

```

- [ ] **Step 3: Update `mode_tag()` (L745–746) — add OOS**

Old:
```python
def mode_tag(c: "Controller") -> str: return {"MAN": "M", "AUTO": "A", "CAS": "C"}.get(c.mode, "M")
```
New:
```python
def mode_tag(c: "Controller") -> str:
    return {"MAN": "M", "AUTO": "A", "CAS": "C", "OOS": "O"}.get(c.mode, "M")
```

- [ ] **Step 4: Update `State.__init__` Controller construction (L778–779)**

Old:
```python
        self.SIC_321950 = Controller(sp=80.0, op=0.0)
        self.SIC_321951 = Controller(sp=86.2, op=86.2)
```
New:
```python
        self.SIC_321950 = Controller("SIC_321950", Kc=2.0, Ti=8.0,
                                     sp=80.0, mv=0.0)
        self.SIC_321951 = Controller("SIC_321951", Kc=2.0, Ti=8.0,
                                     sp=86.2, mv=86.2)
        self.controllers: dict = {
            "SIC_321950": self.SIC_321950,
            "SIC_321951": self.SIC_321951,
        }
```

- [ ] **Step 5: Add `_ctrl_lock` after `state = State()` (L815)**

Old:
```python
state = State()
clients: Set[WebSocket] = set()
```
New:
```python
state = State()
_ctrl_lock = threading.Lock()
clients: Set[WebSocket] = set()
```

- [ ] **Step 6: Update pump loop — `ctrl.op` → `ctrl.mv` (L860)**

Old:
```python
        else:
            target = ctrl.op
```
New:
```python
        else:
            target = ctrl.mv
```

- [ ] **Step 7: Update `controller_set` handler (L1354–1372)**

Old:
```python
    elif t == "controller_set":
        cid  = cmd["id"]
        ctrl = getattr(s, cid, None)
        if ctrl is None:
            return
        if "mode" in cmd:
            ctrl.set_mode(cmd["mode"], current_pv=ctrl.pv)
            if cmd["mode"] == "CAS":
                # ui_guidelines rule 6: master (ratio) -> AUTO, adopt current value as SP
                s.ratio_mode = "AUTO"
                s.ratio_SP   = round(s.ratio_PV, 3)
        if "op" in cmd and ctrl.mode == "MAN":      # PV entry drives opening
            ctrl.op = clamp(float(cmd["op"]), 0.0, 100.0)
        if "sp_rpm" in cmd and ctrl.mode == "AUTO":     # AUTO setpoint entered as RPM
            ctrl.sp = clamp(float(cmd["sp_rpm"]) / PUMP_RATED_RPM * 100.0, 0.0, 100.0)
        elif "sp" in cmd and ctrl.mode == "AUTO":
            ctrl.sp = clamp(float(cmd["sp"]), 0.0, 100.0)
        if "nc" in cmd and ctrl.mode == "CAS":
            ctrl.nc = float(cmd["nc"])
```
New:
```python
    elif t == "controller_set":
        cid  = cmd["id"]
        ctrl = getattr(s, cid, None)
        if ctrl is None:
            return
        if "mode" in cmd:
            ctrl.set_mode(cmd["mode"])
            if cmd["mode"] == "CAS":
                # ui_guidelines rule 6: master (ratio) -> AUTO, adopt current value as SP
                s.ratio_mode = "AUTO"
                s.ratio_SP   = round(s.ratio_PV, 3)
        if "op" in cmd and ctrl.mode == "MAN":
            ctrl.set_op(float(cmd["op"]))
        if "sp_rpm" in cmd and ctrl.mode == "AUTO":
            ctrl.set_sp(float(cmd["sp_rpm"]) / PUMP_RATED_RPM * 100.0)
        elif "sp" in cmd and ctrl.mode == "AUTO":
            ctrl.set_sp(float(cmd["sp"]))
        if "nc" in cmd and ctrl.mode == "CAS":
            ctrl.set_bias(float(cmd["nc"]))
```

- [ ] **Step 8: Update SIC packet blocks (L1314–1328) — `.op`→`.mv`, `.nc`→`.bias`**

Old:
```python
        "SIC_321950": {
            "pv":     round(s.SIC_321950.pv, 1),
            "sp":     round(s.SIC_321950.sp, 1),
            "sp_rpm": round(s.SIC_321950.sp / 100.0 * PUMP_RATED_RPM, 0),
            "mv":     round(s.SIC_321950.op, 1),
            "nc":     round(s.SIC_321950.nc, 1),
            "mode":   s.SIC_321950.mode,
        },
        "SIC_321951": {
            "pv":     round(s.SIC_321951.pv, 1),
            "sp":     round(s.SIC_321951.sp, 1),
            "sp_rpm": round(s.SIC_321951.sp / 100.0 * PUMP_RATED_RPM, 0),
            "mv":     round(s.SIC_321951.op, 1),
            "nc":     round(s.SIC_321951.nc, 1),
            "mode":   s.SIC_321951.mode,
        },
```
New:
```python
        "SIC_321950": {
            "pv":     round(s.SIC_321950.pv, 1),
            "sp":     round(s.SIC_321950.sp, 1),
            "sp_rpm": round(s.SIC_321950.sp / 100.0 * PUMP_RATED_RPM, 0),
            "mv":     round(s.SIC_321950.mv, 1),
            "nc":     round(s.SIC_321950.bias, 1),
            "mode":   s.SIC_321950.mode,
        },
        "SIC_321951": {
            "pv":     round(s.SIC_321951.pv, 1),
            "sp":     round(s.SIC_321951.sp, 1),
            "sp_rpm": round(s.SIC_321951.sp / 100.0 * PUMP_RATED_RPM, 0),
            "mv":     round(s.SIC_321951.mv, 1),
            "nc":     round(s.SIC_321951.bias, 1),
            "mode":   s.SIC_321951.mode,
        },
```

- [ ] **Step 9: Add `controllers` block to packet return (after `"trips": s.trips` line, before closing `}`)**

Old:
```python
        "trips": s.trips,
    }
```
New:
```python
        "trips": s.trips,
        "controllers": {tag: ctrl.to_packet()
                        for tag, ctrl in s.controllers.items()},
    }
```

- [ ] **Step 10: Smoke-test — import main without crash**

```
cd D:\Work\Urea Simulation\backend
python -c "import main; p = main.step_sim(2.0); print('ok, controllers keys:', list(p.get('controllers', {}).keys()))"
```
Expected:
```
ok, controllers keys: ['SIC_321950', 'SIC_321951']
```

- [ ] **Step 11: Run existing kinetics tests — confirm no regression**

```
python test_reactor_kinetics.py
```
Expected: all 6 tests PASS.

- [ ] **Step 12: Commit**

```
git -C "D:\Work\Urea Simulation" add backend/main.py
git -C "D:\Work\Urea Simulation" commit -m "$(cat <<'EOF'
feat(main): migrate to controllers.py — delete legacy PID/Controller, update State/pump loop/packet

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `main.py` — REST routes + Pydantic `CtrlCommand` + threading.Lock in routes

**Files:**
- Modify: `backend/main.py` (append Pydantic model + REST routes after `app = FastAPI()`)

- [ ] **Step 1: Add `CtrlCommand` Pydantic model and REST routes**

Insert after `app = FastAPI()` (L1433), before `@app.websocket("/ws")`:

```python
# ----- Controller REST API -----

class _TuningPayload(BaseModel):
    Kc: Optional[float] = None
    Ti: Optional[float] = None
    Td: Optional[float] = None


class CtrlCommand(BaseModel):
    set_mode:   Optional[str]           = None
    set_sp:     Optional[float]         = None
    set_op:     Optional[float]         = None
    set_bias:   Optional[float]         = None
    set_tuning: Optional[_TuningPayload] = None


@app.post("/api/ctrl/{tag}")
async def ctrl_post(tag: str, cmd: CtrlCommand):
    """Apply operator command to a named controller. 409 if mode-illegal."""
    with _ctrl_lock:
        ctrl = state.controllers.get(tag)
        if ctrl is None:
            raise HTTPException(status_code=404, detail=f"unknown tag {tag!r}")

        reason = None

        if cmd.set_mode is not None:
            if cmd.set_mode not in ("MAN", "AUTO", "CAS", "OOS"):
                raise HTTPException(status_code=422,
                                    detail=f"invalid mode {cmd.set_mode!r}")
            ctrl.set_mode(cmd.set_mode)

        if cmd.set_sp is not None:
            if ctrl.mode != "AUTO":
                raise HTTPException(status_code=409,
                                    detail="set_sp requires AUTO mode")
            ctrl.set_sp(cmd.set_sp)
            reason = "clamped" if (ctrl.sp != cmd.set_sp) else None

        if cmd.set_op is not None:
            if ctrl.mode != "MAN":
                raise HTTPException(status_code=409,
                                    detail="set_op requires MAN mode")
            ctrl.set_op(cmd.set_op)

        if cmd.set_bias is not None:
            if ctrl.mode != "CAS":
                raise HTTPException(status_code=409,
                                    detail="set_bias requires CAS mode")
            ctrl.set_bias(cmd.set_bias)

        if cmd.set_tuning is not None:
            ctrl.set_tuning(
                Kc=cmd.set_tuning.Kc,
                Ti=cmd.set_tuning.Ti,
                Td=cmd.set_tuning.Td,
            )

        return {"ok": True, "tag": tag, "mode": ctrl.mode, "reason": reason}


@app.get("/api/ctrl")
async def ctrl_get_all():
    """Return to_packet() for every registered controller."""
    with _ctrl_lock:
        return {tag: ctrl.to_packet()
                for tag, ctrl in state.controllers.items()}


@app.get("/api/ctrl/{tag}")
async def ctrl_get(tag: str):
    """Return to_packet() for a single controller."""
    with _ctrl_lock:
        ctrl = state.controllers.get(tag)
        if ctrl is None:
            raise HTTPException(status_code=404, detail=f"unknown tag {tag!r}")
        return ctrl.to_packet()
```

Also add `Optional` to main.py imports if not present. Add at top of file (near existing imports):
```python
from typing import Optional, Set
```
(replace existing `from typing import Set` if present)

- [ ] **Step 2: Verify FastAPI app starts without error**

```
python -c "
import main
from fastapi.testclient import TestClient
c = TestClient(main.app)
r = c.get('/api/ctrl')
print('GET /api/ctrl status:', r.status_code)
print('keys:', list(r.json().keys()))
"
```
Expected:
```
GET /api/ctrl status: 200
keys: ['SIC_321950', 'SIC_321951']
```

- [ ] **Step 3: Commit**

```
git -C "D:\Work\Urea Simulation" add backend/main.py
git -C "D:\Work\Urea Simulation" commit -m "$(cat <<'EOF'
feat(main): add CtrlCommand Pydantic model + REST POST/GET /api/ctrl routes + threading.Lock

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Integration tests — `test_ctrl_routes.py`

**Files:**
- Create: `backend/test_ctrl_routes.py`

- [ ] **Step 1: Write `test_ctrl_routes.py`**

```python
"""Integration tests for /api/ctrl REST routes.
Uses FastAPI TestClient (synchronous). Run: python test_ctrl_routes.py
"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi.testclient import TestClient
import main


def fresh():
    """Reset state to design SS; return a new TestClient."""
    main.state = main.State()
    return TestClient(main.app)


# ===== GET routes =====

def test_get_all_has_both_sic():
    c = fresh()
    r = c.get("/api/ctrl")
    assert r.status_code == 200
    data = r.json()
    assert "SIC_321950" in data and "SIC_321951" in data, \
        f"expected both SIC keys, got: {list(data.keys())}"


def test_get_single_tag_schema():
    c = fresh()
    r = c.get("/api/ctrl/SIC_321951")
    assert r.status_code == 200
    pkt = r.json()
    for key in ("mode", "pv", "sp", "mv", "tuning", "limits", "status"):
        assert key in pkt, f"missing key {key!r}"
    assert pkt["mode"] == "MAN"


def test_get_unknown_tag_404():
    c = fresh()
    r = c.get("/api/ctrl/NOPE")
    assert r.status_code == 404


# ===== POST — mode transitions =====

def test_set_mode_man_to_auto():
    c = fresh()
    r = c.post("/api/ctrl/SIC_321951", json={"set_mode": "AUTO"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["mode"] == "AUTO"


def test_set_mode_unknown_tag_404():
    c = fresh()
    r = c.post("/api/ctrl/NOPE", json={"set_mode": "AUTO"})
    assert r.status_code == 404


def test_set_mode_invalid_value_422():
    c = fresh()
    r = c.post("/api/ctrl/SIC_321951", json={"set_mode": "BANANA"})
    assert r.status_code == 422, f"expected 422, got {r.status_code}"


def test_set_mode_oos():
    c = fresh()
    r = c.post("/api/ctrl/SIC_321951", json={"set_mode": "OOS"})
    assert r.status_code == 200
    assert r.json()["mode"] == "OOS"


# ===== POST — set_sp =====

def test_set_sp_in_man_returns_409():
    c = fresh()   # starts MAN
    r = c.post("/api/ctrl/SIC_321951", json={"set_sp": 85.0})
    assert r.status_code == 409, f"expected 409, got {r.status_code}"


def test_set_sp_in_auto():
    c = fresh()
    c.post("/api/ctrl/SIC_321951", json={"set_mode": "AUTO"})
    r = c.post("/api/ctrl/SIC_321951", json={"set_sp": 85.0})
    assert r.status_code == 200
    pkt = c.get("/api/ctrl/SIC_321951").json()
    assert abs(pkt["sp"] - 85.0) < 0.01, f"sp={pkt['sp']}, want 85.0"


def test_set_sp_clamped_to_sp_hi():
    c = fresh()
    c.post("/api/ctrl/SIC_321951", json={"set_mode": "AUTO"})
    c.post("/api/ctrl/SIC_321951", json={"set_sp": 999.0})   # above sp_hi=100
    pkt = c.get("/api/ctrl/SIC_321951").json()
    assert pkt["sp"] <= 100.0, f"sp={pkt['sp']} should clamp to ≤ 100"


# ===== POST — set_op =====

def test_set_op_in_auto_returns_409():
    c = fresh()
    c.post("/api/ctrl/SIC_321951", json={"set_mode": "AUTO"})
    r = c.post("/api/ctrl/SIC_321951", json={"set_op": 50.0})
    assert r.status_code == 409


def test_set_op_in_man():
    c = fresh()
    r = c.post("/api/ctrl/SIC_321951", json={"set_op": 55.0})
    assert r.status_code == 200
    pkt = c.get("/api/ctrl/SIC_321951").json()
    assert abs(pkt["mv"] - 55.0) < 0.01, f"mv={pkt['mv']}, want 55.0"


# ===== POST — set_bias =====

def test_set_bias_in_man_returns_409():
    c = fresh()
    r = c.post("/api/ctrl/SIC_321951", json={"set_bias": 2.5})
    assert r.status_code == 409


def test_set_bias_in_cas():
    c = fresh()
    c.post("/api/ctrl/SIC_321951", json={"set_mode": "CAS"})
    r = c.post("/api/ctrl/SIC_321951", json={"set_bias": 3.0})
    assert r.status_code == 200
    pkt = c.get("/api/ctrl/SIC_321951").json()
    assert abs(pkt["bias"] - 3.0) < 0.01, f"bias={pkt['bias']}, want 3.0"


# ===== POST — set_tuning (always legal) =====

def test_set_tuning_in_man():
    c = fresh()
    r = c.post("/api/ctrl/SIC_321951", json={"set_tuning": {"Kc": 3.0, "Ti": 12.0}})
    assert r.status_code == 200
    pkt = c.get("/api/ctrl/SIC_321951").json()
    assert abs(pkt["tuning"]["Kc"] - 3.0) < 1e-9
    assert abs(pkt["tuning"]["Ti"] - 12.0) < 1e-9


def test_set_tuning_in_auto():
    c = fresh()
    c.post("/api/ctrl/SIC_321951", json={"set_mode": "AUTO"})
    r = c.post("/api/ctrl/SIC_321951", json={"set_tuning": {"Kc": 1.5}})
    assert r.status_code == 200
    pkt = c.get("/api/ctrl/SIC_321951").json()
    assert abs(pkt["tuning"]["Kc"] - 1.5) < 1e-9


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    fails = 0
    for t in tests:
        try:
            t(); print("PASS", t.__name__)
        except Exception:
            fails += 1; print("FAIL", t.__name__); traceback.print_exc()
    raise SystemExit(1 if fails else 0)
```

- [ ] **Step 2: Run — confirm all pass**

```
cd D:\Work\Urea Simulation\backend
python test_ctrl_routes.py
```
Expected (20 tests):
```
PASS test_get_all_has_both_sic
PASS test_get_single_tag_schema
PASS test_get_unknown_tag_404
PASS test_set_mode_man_to_auto
PASS test_set_mode_unknown_tag_404
PASS test_set_mode_invalid_value_422
PASS test_set_mode_oos
PASS test_set_sp_in_man_returns_409
PASS test_set_sp_in_auto
PASS test_set_sp_clamped_to_sp_hi
PASS test_set_op_in_auto_returns_409
PASS test_set_op_in_man
PASS test_set_bias_in_man_returns_409
PASS test_set_bias_in_cas
PASS test_set_tuning_in_man
PASS test_set_tuning_in_auto
```

- [ ] **Step 3: Commit**

```
git -C "D:\Work\Urea Simulation" add backend/test_ctrl_routes.py
git -C "D:\Work\Urea Simulation" commit -m "$(cat <<'EOF'
test(ctrl_routes): integration tests for POST/GET /api/ctrl REST routes

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Full regression

**Files:** No changes — validation only.

- [ ] **Step 1: Run all controller unit tests**

```
cd D:\Work\Urea Simulation\backend
python test_controllers.py
```
Expected: all tests PASS, exit 0.

- [ ] **Step 2: Run all route integration tests**

```
python test_ctrl_routes.py
```
Expected: all tests PASS, exit 0.

- [ ] **Step 3: Run reactor kinetics tests**

```
python test_reactor_kinetics.py
```
Expected: all 6 tests PASS, exit 0.

- [ ] **Step 4: Run ejector-stall system test**

```
python test_2_ejector_stall.py
```
Expected output: time-series table + `VERDICT: X/4 physical expectations met.` (same structural-gap count as before migration — no regression introduced).

- [ ] **Step 5: Smoke-check WS packet contains controllers block**

```
python -c "
import main
pkt = main.step_sim(2.0)
ctrls = pkt.get('controllers', {})
print('controllers block keys:', sorted(ctrls.keys()))
sic = ctrls.get('SIC_321951', {})
print('SIC_321951 mode:', sic.get('mode'))
print('SIC_321951 mv:', sic.get('mv'))
print('SIC_321951 status:', sic.get('status'))
"
```
Expected:
```
controllers block keys: ['SIC_321950', 'SIC_321951']
SIC_321951 mode: MAN
SIC_321951 mv: 86.2
SIC_321951 status: {'pv_bad': False, 'mv_hi_clamp': False, 'mv_lo_clamp': False}
```

- [ ] **Step 6: Final commit**

```
git -C "D:\Work\Urea Simulation" add -A
git -C "D:\Work\Urea Simulation" commit -m "$(cat <<'EOF'
chore(controllers): full regression green — controllers.py + REST routes complete

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)" --allow-empty
```
(Use `--allow-empty` only if all files were already staged in earlier commits; otherwise stage any stragglers first.)

---

## Self-Review

### Spec coverage check

| Spec requirement | Task covering it |
|-----------------|-----------------|
| Velocity I-PD equation (Δu, slew clamp, MV clamp) | Task 1 (PID), Task 2 (Controller.step) |
| σ = +1 REVERSE / -1 DIRECT; Kc > 0 always | Task 2 (`_sigma()` + `action` param) |
| Stores PV_{k-1}, PV_{k-2}, u_{k-1} only | Task 1 (`_pv1`, `_pv2`; Task 2 `mv`) |
| MAN mode: MV held by operator, set_op slew-limited | Task 2 (`step` MAN branch + `set_op`) |
| AUTO entry: SP ← PV bumpless | Task 2 (`set_mode("AUTO")`) |
| CAS entry: bias ← 0, PID reset bumpless | Task 2 (`set_mode("CAS")`) |
| OOS entry + stroke to fail target at slew rate | Task 2 (OOS branch + `_fail_target()`) |
| Fail actions FC/FO/FL | Task 2 (`_fail_target()`) |
| Slew limit applied ALL modes | Task 2 (slew_max in every active branch; OOS delta clamp) |
| Anti-windup = MV clamp only (no integral state) | Inherent to velocity form — no accumulator |
| Bad-PV fail-freeze: None/NaN/out-of-range → force MAN, freeze MV | Task 2 (`step()` guard) |
| BAD_PV_LO=-5.0, BAD_PV_HI=105.0 | Task 1 (module constants) |
| set_op MAN-only 409 | Task 4 (route handler) |
| set_sp AUTO-only 409 | Task 4 (route handler) |
| set_bias CAS-only 409 | Task 4 (route handler) |
| set_mode always legal | Task 4 |
| set_tuning always legal | Task 4 |
| WS read schema (mode/pv/sp/mv/cas_sp/bias/action/tuning/limits/fail_action/status) | Task 2 (`to_packet()`) |
| `controllers` block in WS packet | Task 3 (packet return dict) |
| POST /api/ctrl/{tag} + CtrlCommand + ack schema | Task 4 |
| GET /api/ctrl + GET /api/ctrl/{tag} | Task 4 |
| 404 unknown tag, 422 malformed, 409 mode-illegal, 200 valid | Task 4 + Task 5 tests |
| threading.Lock | Task 3 (`_ctrl_lock = threading.Lock()`) + Task 4 (route `with _ctrl_lock`) |
| SIC_321950 + SIC_321951 migrated to new Controller | Task 3 (State.__init__) |
| Legacy `.op`→`.mv`, `.nc`→`.bias` in packet | Task 3 (Step 8) |
| mode_tag() 4-state update (OOS→"O") | Task 3 (Step 3) |
| controller_set WS handler updated | Task 3 (Step 7) |
| Regression: kinetics tests + ejector-stall | Task 6 |

All 29 spec requirements covered. No gaps.

### Placeholder scan

No TBD, TODO, "implement later", "similar to Task N", or "add appropriate error handling" phrases present. Every step contains exact code.

### Type consistency

| Symbol | Defined in | Used in |
|--------|-----------|---------|
| `PID(Kc, Ti, Td)` | Task 1 `controllers.py` | Task 2 `Controller.__init__` |
| `Controller(tag, *, Kc, Ti, ...)` | Task 2 `controllers.py` | Task 3 `State.__init__` |
| `Controller.mv` | Task 2 | Task 3 pump loop, packet |
| `Controller.bias` | Task 2 | Task 3 packet (`nc` key kept for frontend compat) |
| `Controller.set_mode(mode: str)` | Task 2 | Task 3 `controller_set` handler, Task 4 route |
| `Controller.set_sp/set_op/set_bias/set_tuning` | Task 2 | Task 3 `controller_set`, Task 4 route |
| `Controller.to_packet() -> dict` | Task 2 | Task 3 packet, Task 4 `ctrl_get` |
| `state.controllers: dict` | Task 3 `State.__init__` | Task 4 routes, Task 3 packet loop |
| `_ctrl_lock: threading.Lock` | Task 3 module-level | Task 4 route `with _ctrl_lock` |
| `CtrlCommand` (Pydantic) | Task 4 | Task 4 `ctrl_post` signature |

All consistent.
