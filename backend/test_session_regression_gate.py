"""Regression gate for the Red Team consensus fixes (G6, Expert_Interrogation_Log).

WHY THIS FILE EXISTS
--------------------
The boot pin (`main._collect_pin`) covers 15 DESIGN-TIME module constants. It does NOT touch a
single runtime control loop, so it read `leaves 25 / keys 15 / diffs 0` whether the stream-741
recycle conserved mass or invented 34 t/h (CP-2), and it runs only at dt=0.1 so it never saw the
FAST-mode integrator diverge (CP-1). "pin 0 diffs, 103 passed" was true and uninformative.

This gate closes that hole. Every test drives the PUBLIC step_sim() on a fresh design State and
asserts a property the pin structurally cannot:

  * step-size invariance          -> would have caught CP-1
  * runtime loops sit at design   -> catches TD-005-style silent drift
  * 740-node mass conservation    -> would have caught CP-2 at any stroke
  * HPCC pressure ceiling         -> guards CP-5
  * FFIC / TIC master fixed point -> guards TD-003 / TD-004

No engine constant is touched, so the boot-pin bit-exactness is unaffected (a sibling concern the
existing test_transient_coldstart.py already asserts).

Run from backend/:  python -m pytest test_session_regression_gate.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402


def _fresh(settle=400, dt=0.1):
    """Fresh design State, settled, returns (state, last packet)."""
    main.state = main.State()
    p = None
    for _ in range(settle):
        p = main.step_sim(dt)
    return main.state, p


def _tree(p, *keys):
    for k in keys:
        p = p[k]
    return p


# --------------------------------------------------------------------------------------------
#  CP-1 guard: step-size invariance. The design hold must land on the SAME steady state whatever
#  the sub-step, or FAST mode is integrating a different plant than SLOW.
# --------------------------------------------------------------------------------------------
def test_step_cap_below_stability_limit():
    """CP-1, the direct guard: the fast flow loops go non-monotone above a critical sub-step of
    ~0.389 s, so STEP_CAP (the largest step the real-time / FAST loop ever takes) MUST stay below
    it.  This is the one-line assertion that fails the instant someone bumps STEP_CAP back to 0.5.
    Confirmed empirically: at dt=0.5 an undisturbed design hold diverges (FIC-328404 op -> 100 %,
    pv -> 2.41 vs a 1.53 design); at 0.25 it sits exactly on design."""
    assert main.STEP_CAP <= 0.30, \
        f"STEP_CAP={main.STEP_CAP} is at/above the ~0.389 s stability limit -- FAST mode will diverge"


def test_step_size_invariance_in_operating_range():
    """Within the REACHABLE step range (dt <= STEP_CAP) the design steady state must be
    step-independent, or SLOW and FAST integrate different plants.  Tested at dt=0.1 (the pin
    step) and dt=STEP_CAP (the coarsest step production ever uses).  dt=0.5 is deliberately NOT
    tested -- test_step_cap_below_stability_limit guarantees it is never reached, and it genuinely
    diverges, so asserting invariance there would be asserting a falsehood."""
    ref_state, ref = _fresh(settle=600, dt=0.1)
    def scalars(pkt, st):
        return [
            st.p_syn_bara,
            _tree(pkt, "DESORB_328", "D001", "FIC_328404")["m_kgh"],
            _tree(pkt, "DESORB_328", "C004")["steam931_th"],
            _tree(pkt, "DESORB_328", "C004")["recyc741_th"],
            _tree(pkt, "LPCC_3232", "E011", "FIC_323402")["m_kgh"],
            _tree(pkt, "HPCC_322E002")["P_bara"],
        ]
    ref_vals = scalars(ref, ref_state)
    dt = main.STEP_CAP
    st, p = _fresh(settle=int(round(600 * 0.1 / dt)), dt=dt)
    vals = scalars(p, st)
    for name, a, b in zip(
        ("p_syn", "reflux775", "steam931", "recyc741", "wash402", "hpcc_P"),
        ref_vals, vals,
    ):
        tol = 1e-6 if a == 0 else abs(a) * 5e-3              # 0.5 % band; exact for zero-valued
        assert abs(a - b) <= tol + 1e-9, \
            f"step-size variance in {name}: dt=0.1 -> {a!r}, dt={dt} -> {b!r} (tol {tol:.3g})"
    main.state = main.State()


# --------------------------------------------------------------------------------------------
#  Runtime loops sit at their PFD design values (the pin never checks these).
# --------------------------------------------------------------------------------------------
def test_runtime_loops_at_design():
    _, p = _fresh()
    checks = [
        ("FIC-328404 reflux 775", _tree(p, "DESORB_328", "D001", "FIC_328404")["m_kgh"],
         main.R328_D001_M775_DES, 1.0),
        ("FIC-329401 steam 931 (t/h)", _tree(p, "DESORB_328", "C004")["steam931_th"],
         main.R328_C004_M931_DES / 1000.0, 0.05),
        ("FIC-328402 wash 744 (kg/h)", _tree(p, "LPCC_3232", "E003", "FIC_328402")["kgh"],
         main.R3232_E003_M744_DES, 5.0),
        ("FIC-323402 wash 402 (kg/h)", _tree(p, "LPCC_3232", "E011", "FIC_323402")["m_kgh"],
         main.R3232_E011_M402_DES, 5.0),
    ]
    for name, got, want, tol in checks:
        assert abs(got - want) <= tol, f"{name}: {got!r} != design {want!r} (tol {tol})"


def test_stream_741_zero_at_design():
    """TD-005: the recycle is normally closed, so at design it must be exactly 0 and the 740
    export must equal the full 739 bottoms."""
    _, p = _fresh()
    c004 = _tree(p, "DESORB_328", "C004")
    assert c004["recyc741_th"] == 0.0, f"741 recycle nonzero at design: {c004['recyc741_th']}"
    assert abs(c004["export740_th"] - c004["bot739_th"]) <= 0.02, \
        f"740 export != 739 at design: {c004['export740_th']} vs {c004['bot739_th']}"


# --------------------------------------------------------------------------------------------
#  CP-2 guard: the 740 node conserves at EVERY FIC-328406 stroke. recyc + export == bottoms.
# --------------------------------------------------------------------------------------------
def test_stream_741_node_conserves_across_stroke():
    main.state = main.State()
    s = main.state
    for _ in range(300):
        main.step_sim(0.1)
    s.FIC_328406["mode"] = "MAN"
    for stroke in (0.0, 50.0, 100.0):
        s.FIC_328406["op"] = stroke
        p = None
        for _ in range(3000):
            p = main.step_sim(0.1)
        c = _tree(p, "DESORB_328", "C004")
        resid = c["bot739_th"] - (c["recyc741_th"] + c["export740_th"])
        assert abs(resid) <= 0.02, \
            f"740-node leak at {stroke}% stroke: 739={c['bot739_th']} != " \
            f"741({c['recyc741_th']}) + 740({c['export740_th']}), resid {resid:+.3f} t/h"
    main.state = main.State()


# --------------------------------------------------------------------------------------------
#  CP-5 guard: HPCC published pressure never exceeds the feed-supply head, at design or turndown.
# --------------------------------------------------------------------------------------------
def test_hpcc_pressure_capped_at_supply_head():
    s, p = _fresh()
    assert _tree(p, "HPCC_322E002")["P_bara"] <= main.SYN_P_MAX_BARA + 1e-6, "HPCC P over ceiling at design"
    s.F_CO2_raw_th = 0.40 * s.F_CO2_raw_th          # force the bubble point up via turndown
    for _ in range(6000):
        p = main.step_sim(0.1)
    assert _tree(p, "HPCC_322E002")["P_bara"] <= main.SYN_P_MAX_BARA + 1e-6, \
        f"HPCC P {_tree(p,'HPCC_322E002')['P_bara']} exceeds ceiling {main.SYN_P_MAX_BARA} on turndown"
    main.state = main.State()


# --------------------------------------------------------------------------------------------
#  TD-003 / TD-004: the ratio and cascade masters hold their design fixed point (pv == sp).
# --------------------------------------------------------------------------------------------
def test_master_fixed_points_at_design():
    _, p = _fresh()
    ffic = _tree(p, "DESORB_328", "C004")["FFIC_329401"]
    tic = _tree(p, "DESORB_328", "D001")["TIC_328008"]
    assert abs(ffic["pv"] - ffic["sp"]) <= 1e-3, f"FFIC-329401 off fixed point: {ffic}"
    assert abs(tic["pv"] - tic["sp"]) <= 0.05, f"TIC-328008 off fixed point: {tic}"
    # CP-4: TIC-328008's design SP must sit inside its reachable band (the span is on the seed
    # dict, not published in telemetry, so read it off a fresh State).
    seed = main.State().TIC_328008
    assert seed["sp_lo"] <= tic["sp"] <= seed["sp_hi"], \
        f"TIC-328008 design SP {tic['sp']} outside its reachable band [{seed['sp_lo']},{seed['sp_hi']}]"


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fails = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception as e:                                    # noqa: BLE001
            fails += 1
            print(f"FAIL  {fn.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(fns) - fails}/{len(fns)} passed")
    sys.exit(1 if fails else 0)
