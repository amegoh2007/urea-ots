"""Regression gate for the EQUATION_AUDIT F-1..F-5 / F-10 fixes (units 323 + 324).

WHY THIS FILE EXISTS
--------------------
The boot pin is a UNIT-322 contract (HPCC_UA, REACT_TEAR_DES, the GCB pins ...). It is structurally
blind to whether the 323/324 vapour rates are energy-limited or frozen split fractions, so it read
`leaves 25 / keys 15 / diffs 0` just as happily when shutting the Evap-I steam left the melt
strength pinned at 94.31 % and drove the melt to 22 °C.

Each test drives the PUBLIC step_sim() on a FRESH design State (the `_fresh` house idiom from
test_session_regression_gate.py, so no test inherits another's disturbance) and asserts physics an
operator can actually provoke from the HMI:

  * design fixed point still exactly non-binding  -> the duty ratio really is 1.0 at the seed
  * Evap-I steam cut dilutes the product          -> F-4 (was impossible: strength was a constant)
  * rectifier steam cut collapses the boil-up     -> F-2
  * ... and the downstream flash then makes LESS  -> F-1 (was blind to feed temperature)
  * no steam chest ever produces negative duty    -> F-10 (a condenser is not a refrigerator)

Run from backend/:  python -m pytest test_equation_audit_323_324.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402

DT = 0.25


def _fresh(seconds=300.0):
    """Fresh design State, settled `seconds` of sim time; returns the last packet."""
    main.state = main.State()
    return _run(seconds)


def _run(seconds):
    out = None
    for _ in range(int(seconds / DT)):
        out = main.step_sim(DT)
    return out


# ------------------------------------------------------------------ F-1..F-5 design invariance
def test_design_fixed_point_holds():
    """At the design seed the new energy limits must be exactly non-binding: every 323/324 anchor
    has to sit on its design value, otherwise the duty ratio is not 1.0 and the HMB has drifted."""
    t = _fresh(600.0)
    e1, e3 = t["EVAP_324"]["E001"], t["EVAP_324"]["E003"]
    c3, f4, f10 = (t["RECIRC_323"]["C003"], t["RECIRC_323"]["F004"], t["RECIRC_323"]["F010"])

    assert e1["urea_pct"] == 94.3, e1["urea_pct"]        # F-4: live, still lands on the anchor
    assert e3["urea_pct"] == 97.7, e3["urea_pct"]        # F-5
    assert e1["TT_324001"] == 130.0
    assert e3["TT_324002"] == 140.0
    assert f4["TT_323005"] == 106.0                      # F-1: flash sits at its bubble point
    # published to 2 dp (t/h), so half the last digit -- 0.005 -- is the achievable tolerance
    assert abs(c3["v305_th"] - main.R323_M305_DES / 1000.0) < 6e-3      # F-2
    assert abs(f4["v701_th"] - main.R323_M701_DES / 1000.0) < 6e-3      # F-1
    assert abs(f10["evap_th"] - main.R323_MEVAP_DES / 1000.0) < 6e-3    # F-3
    assert abs(e1["vapour_th"] - main.R324_V1_DES / 1000.0) < 6e-3      # F-4
    assert abs(e3["vapour_th"] - main.R324_V2_DES / 1000.0) < 6e-3      # F-5


def test_design_point_does_not_drift():
    """Two consecutive 300 s windows on an undisturbed design hold must publish identical anchors.
    The energy limits are ratio-anchored, so any creep here means a duty ratio is not exactly 1."""
    a = _fresh(300.0)
    b = _run(300.0)
    assert a["EVAP_324"]["E001"]["urea_pct"] == b["EVAP_324"]["E001"]["urea_pct"]
    assert a["EVAP_324"]["E003"]["urea_pct"] == b["EVAP_324"]["E003"]["urea_pct"]
    assert a["RECIRC_323"]["C003"]["v305_th"] == b["RECIRC_323"]["C003"]["v305_th"]
    assert a["RECIRC_323"]["F004"]["v701_th"] == b["RECIRC_323"]["F004"]["v701_th"]
    assert a["RECIRC_323"]["F004"]["TT_323005"] == b["RECIRC_323"]["F004"]["TT_323005"]


# ------------------------------------------------------------------------------ F-4 / F-10
def test_evap1_steam_cut_dilutes_product_and_never_cools():
    """Cutting the Evap-I LP steam must (a) collapse the evaporation, (b) DILUTE the melt -- the
    old hard `urea_in / W_EV1` made this impossible -- and (c) never drive the duty negative."""
    t = _fresh(300.0)
    base = t["EVAP_324"]["E001"]["urea_pct"]
    s = main.state

    s.PIC_329203["mode"] = "MAN"
    s.PIC_329203["op"] = 0.0
    s.TIC_324001["mode"] = "MAN"
    q_min = None
    for _ in range(8):
        t = _run(60.0)
        q = t["EVAP_324"]["E001"]["Q_kW"]
        q_min = q if q_min is None else min(q_min, q)
    e1 = t["EVAP_324"]["E001"]

    assert e1["vapour_th"] == 0.0, e1["vapour_th"]              # F-4: no duty -> no boil-up
    assert e1["urea_pct"] < base - 5.0, (e1["urea_pct"], base)  # F-4: product really dilutes
    assert q_min >= 0.0, q_min                                  # F-10: chest cannot refrigerate
    assert e1["TT_324001"] > 90.0, e1["TT_324001"]              # F-10: coasts to feed T, not ~22 C


# ------------------------------------------------------------------------ F-2 / F-1 / F-10
def test_rectifier_steam_cut_collapses_boilup_and_flash():
    """Cutting the 323E002 LP steam must collapse the 305 overhead (F-2), must not refrigerate the
    column (F-10), and the downstream 323F004 flash must produce LESS vapour on its now-colder feed
    (F-1 -- with a frozen split fraction the flash was completely blind to feed temperature)."""
    t = _fresh(300.0)
    v701_base = t["RECIRC_323"]["F004"]["v701_th"]
    s = main.state

    s.PIC_329202["mode"] = "MAN"
    s.PIC_329202["op"] = 0.0
    s.TIC_323007["mode"] = "MAN"
    q_min = None
    for _ in range(8):
        t = _run(60.0)
        q = t["RECIRC_323"]["C003"]["Q_kW"]
        q_min = q if q_min is None else min(q_min, q)
    c3, f4 = t["RECIRC_323"]["C003"], t["RECIRC_323"]["F004"]

    assert c3["v305_th"] == 0.0, c3["v305_th"]                          # F-2
    assert q_min >= 0.0, q_min                                          # F-10
    assert c3["TT_323002"] > 80.0, c3["TT_323002"]                      # F-10: not dragged to ~14 C
    assert f4["v701_th"] < v701_base - 0.5, (f4["v701_th"], v701_base)  # F-1


# ------------------------------------------------------------------------------------ F-4/F-5
def test_conc_infer_survives_zero_strength():
    """`conc_infer_324` now receives the LIVE melt strength, which legally reaches 0 on a cold
    start.  It must not divide by zero (this crashed the four cold-start tests mid-fix)."""
    assert main.conc_infer_324(0.0, main.R324_E001_T_SP_C, main.R324_F001_P_BARA,
                               main.R324_E001_T_SP_C, main.R324_F001_P_BARA) is not None
    # design point still lands exactly on its anchor
    assert round(main.conc_infer_324(main.R324_W_EV1, main.R324_E001_T_SP_C, main.R324_F001_P_BARA,
                                     main.R324_E001_T_SP_C, main.R324_F001_P_BARA), 6) \
        == round(main.R324_W_EV1 * 100.0, 6)
