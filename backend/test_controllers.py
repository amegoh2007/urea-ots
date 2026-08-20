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
    """AUTO: single-step MV change <= rate * dt regardless of Kc."""
    c = Controller("TAG", Kc=500.0, Ti=0.01, rate=5.0, mv=50.0)
    c.set_mode("AUTO")
    c.sp = 90.0
    mv_before = c.mv
    c.step(pv=10.0, dt=2.0)
    assert abs(c.mv - mv_before) <= 5.0 * 2.0 + 1e-9, \
        f"slew {abs(c.mv - mv_before):.3f} > rate*dt=10"


def test_ctrl_auto_direct_action():
    """AUTO DIRECT (sigma=-1): positive error drives mv DOWN."""
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
    """OOS FC: single-step change <= rate*dt."""
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


# ===== PID Tf derivative filter + Dz deadzone (P3-A) =====

def _run_seq(pid, seq, dt):
    return [pid.step(sp, pv, dt) for (sp, pv) in seq]


def test_pid_tf_zero_matches_legacy():
    """Tf=0 path is byte-identical to the legacy 2nd-difference derivative."""
    seq = [(80.0, 70.0), (80.0, 72.0), (80.0, 71.0), (80.0, 75.0), (80.0, 74.5)]
    Kc, Ti, Td, dt = 1.7, 8.0, 2.0, 0.5
    outs = _run_seq(PID(Kc=Kc, Ti=Ti, Td=Td, Tf=0.0), seq, dt)
    pv1 = pv2 = seq[0][1]
    ref = []
    for sp, pv in seq:                                   # independent legacy recomputation
        p = -(pv - pv1); i = (dt / Ti) * (sp - pv); d = -Td * (pv - 2 * pv1 + pv2) / dt
        ref.append(Kc * (p + i + d)); pv2 = pv1; pv1 = pv
    for o, r in zip(outs, ref):
        assert approx(o, r, 0.0), f"Tf=0 got {o}, legacy {r}"   # tol=0 -> exact


def test_pid_tf_collapses_to_legacy_as_tf_small():
    """Filtered derivative with tiny Tf -> legacy term within float tol."""
    seq = [(50.0, 50.0), (50.0, 52.0), (50.0, 51.0), (50.0, 55.0)]
    dt = 0.5
    leg = _run_seq(PID(Kc=1.0, Ti=1e9, Td=3.0, Tf=0.0), seq, dt)
    flt = _run_seq(PID(Kc=1.0, Ti=1e9, Td=3.0, Tf=1e-9), seq, dt)
    for a, b in zip(leg, flt):
        assert approx(a, b, 1e-6), f"legacy {a} vs filt {b}"


def test_pid_tf_attenuates_derivative_kick():
    """On a PV step, larger Tf yields a SMALLER first derivative increment."""
    step = [(0.0, 0.0), (0.0, 0.0), (0.0, 10.0)]   # huge Ti kills I -> isolate D
    dt = 1.0
    d0 = _run_seq(PID(Kc=1.0, Ti=1e12, Td=5.0, Tf=0.0), step, dt)[-1]
    d1 = _run_seq(PID(Kc=1.0, Ti=1e12, Td=5.0, Tf=4.0), step, dt)[-1]
    assert abs(d1) < abs(d0), f"filtered |{d1}| should be < unfiltered |{d0}|"


def test_pid_dz_zero_is_inert():
    """Dz=0 -> integral identical to legacy pure-integral first step."""
    d = PID(Kc=1.0, Ti=10.0, Td=0.0, Dz=0.0).step(80.0, 79.0, 1.0)
    assert approx(d, (1.0 / 10.0) * (80.0 - 79.0)), f"got {d}"


def test_pid_dz_zeros_integral_inside_band():
    """|err| < Dz -> integral suppressed; first step P=D=0 -> delta 0."""
    d = PID(Kc=1.0, Ti=10.0, Td=0.0, Dz=5.0).step(80.0, 78.0, 1.0)   # err=2 < 5
    assert approx(d, 0.0, 1e-12), f"inside deadzone should give 0, got {d}"


def test_pid_dz_active_outside_band():
    """|err| >= Dz -> integral acts normally."""
    d = PID(Kc=1.0, Ti=10.0, Td=0.0, Dz=1.0).step(80.0, 70.0, 1.0)   # err=10 >= 1
    assert approx(d, (1.0 / 10.0) * 10.0), f"got {d}"


def test_pid_reset_clears_dfilt():
    """reset() zeros the derivative filter state."""
    pid = PID(Kc=1.0, Ti=1e12, Td=3.0, Tf=4.0)
    pid.step(0.0, 0.0, 1.0); pid.step(0.0, 10.0, 1.0)
    assert pid._dfilt != 0.0
    pid.reset()
    assert pid._dfilt == 0.0


def test_to_packet_includes_tf_dz():
    """to_packet() exposes Tf/Dz in tuning block."""
    pkt = Controller("TAG", Kc=1.0, Ti=8.0, Td=0.5, Tf=2.0, Dz=1.5).to_packet()
    assert approx(pkt["tuning"]["Tf"], 2.0) and approx(pkt["tuning"]["Dz"], 1.5)


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
