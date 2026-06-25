"""322F001 ejector-spindle (HV-322602) characteristic self-test.

Stamicarbon motive NH3 is supplied by 321P002 A/B POSITIVE-DISPLACEMENT (triplex)
pumps -> motive mass flow is CONSTANT (set by pump speed, not valve).  HV-322602 is
the converging parabolic NH3-nozzle needle: closing it shrinks the nozzle area A, so
at constant m_dot the jet velocity v = m_dot/(rho*A) RISES and the momentum flux
m_dot*v = m_dot^2/(rho*A) RISES.  Higher motive momentum -> HIGHER entrainment
capacity -> the ejector drains the 322E003 sump -> LT-329501 FALLS on CLOSING.

So phi_sp must be a NEGATIVE equal-% characteristic about the 74 % design opening
(phi_sp(74)=1 bit-exact; phi_sp(<74)>1; phi_sp(>74)<1).  Plain asserts (no pytest).
Run:  python backend/test_ejector_spindle.py
"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main


def _mot_des():
    return main.EJ_MOTIVE_DES_LIVE if main.EJ_MOTIVE_DES_LIVE is not None else main.EJ_MOTIVE_NH3_DES


def test_spindle_design_anchor():
    """At the 74 % design opening, design motive, frac=1 -> suction == EJ_SUC_TOT_DES bit-exact."""
    ej = main.ejector_322f001(_mot_des(), main.EJ_T_SUCTION_C, main.EJ_OPEN_DES, scrub_level_frac=1.0)
    assert abs(ej["suction_kgh"] - main.EJ_SUC_TOT_DES) < 1e-6, ej["suction_kgh"]


def test_spindle_negative_characteristic():
    """Constant-m_dot momentum: CLOSING the spindle RAISES entrainment capacity, opening lowers it.
    Decoupled from the sump (frac=1.0) so this isolates the phi_sp characteristic only."""
    mot = _mot_des()
    s_open  = main.ejector_322f001(mot, main.EJ_T_SUCTION_C, 95.0, scrub_level_frac=1.0)["suction_kgh"]
    s_des   = main.ejector_322f001(mot, main.EJ_T_SUCTION_C, 74.0, scrub_level_frac=1.0)["suction_kgh"]
    s_close = main.ejector_322f001(mot, main.EJ_T_SUCTION_C, 50.0, scrub_level_frac=1.0)["suction_kgh"]
    assert s_close > s_des > s_open, (s_close, s_des, s_open)


def _settle(n):
    pkt = None
    for _ in range(n):
        pkt = main.step_sim(1.0)
    return pkt


def _run_lt(open_val, warm=800, hold=2500):
    main.state = main.State()
    base = _settle(warm)["SCRUB_322E003"]["LT_329501"]
    main.handle_cmd({"type": "hic_set", "value": open_val})
    lt = _settle(hold)["SCRUB_322E003"]["LT_329501"]
    return base, lt


def test_lt329501_falls_on_close():
    """Integration: CLOSING HV-322602 -> more entrainment -> 322E003 sump drains -> LT-329501 FALLS."""
    base, lt = _run_lt(50.0)
    assert lt < base - 1.0, (base, lt)


def test_lt329501_rises_on_open():
    """Integration: OPENING HV-322602 -> less entrainment -> sump backs up -> LT-329501 RISES."""
    base, lt = _run_lt(95.0)
    assert lt > base + 1.0, (base, lt)


def test_lt329501_design_holds():
    """Design anchor: at the 74 % design opening LT-329501 holds its steady NLL (no drift)."""
    base, lt = _run_lt(74.0)
    assert abs(lt - base) < 0.5, (base, lt)


def _run_lt504(open_val, warm=800, hold=600):
    """Reactor 322R001 narrow-band LT-322504 before/after an HV-322602 move (transient-swell window)."""
    main.state = main.State()
    base = _settle(warm)["REACT_322R001"]["LT_322504"]
    main.handle_cmd({"type": "hic_set", "value": open_val})
    lt = _settle(hold)["REACT_322R001"]["LT_322504"]
    return base, lt


def test_lt322504_rises_on_close():
    """DOMINO: CLOSING HV-322602 -> more entrainment -> more carbamate fwd 322E003->322E002->322R001
    -> the reactor holdup swells -> LT-322504 RISES (the chain the user reported as broken)."""
    base, lt = _run_lt504(50.0)
    assert lt > base + 0.3, (base, lt)


def test_lt322504_falls_on_open():
    """DOMINO: OPENING HV-322602 -> less entrainment -> less carbamate fwd -> LT-322504 FALLS."""
    base, lt = _run_lt504(95.0)
    assert lt < base - 0.3, (base, lt)


def test_lt322504_design_holds():
    """Design anchor: at the 74 % design opening the fwd-flow deviation is 0 -> LT-322504 holds NLL."""
    base, lt = _run_lt504(74.0)
    assert abs(lt - base) < 0.1, (base, lt)


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
