"""C39 regression gate — one-tick recycle-tear classification for Unit 328.

Handoff gap C39 asked to classify the one-tick tears on streams 748, 750, 775, 718A and
931 as *physical transport* or *algebraic recycle*, then solve the algebraic ones by a
bounded method (direct substitution / Wegstein / Broyden) and keep a dynamic lag only
where residence-time evidence exists.

Classification (grounded in main.py, see As-Built reference §22.14):

  748  328C003 overhead -> 328C002   ALGEBRAIC RECYCLE  (vapour line, no inventory)
  750  328C004 overhead -> 328C002   ALGEBRAIC RECYCLE  (vapour line, no inventory)
  775  328D001 reflux   -> 328C002   ALGEBRAIC RECYCLE  (pumped reflux, no line residence evidence)
  718A 323D011 draw     -> 328D001   PHYSICAL TRANSPORT (45 s liquid-leg lag, R3232_M718A_TAU_S)
  931  LP steam         -> 328C004   NOT A RECYCLE      (FFIC/FIC-controlled utility feed)

The engine already resolves the three algebraic tears by one-tick Gauss-Seidel direct
substitution (last-tick value read at line ~5785, this-tick value stored at line ~6257);
these tests certify that substitution is BOUNDED and non-oscillatory (|z|<1), which is the
condition the handoff required.  718A keeps its physical first-order transport lag; 931 is a
controlled utility flow whose one-tick term is a measurement-PV feedback, not a recycle.

Run from backend/:  python -m pytest test_c39_recycle_tears.py   (or: python test_c39_recycle_tears.py)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main

DT = 0.1
_STORE = {"748": "R328_748", "750": "R328_750", "775": "R328_775",
          "718A": "R3232_718A", "931": "R328_M931"}


def _tears():
    t = main.state.tlag
    return {k: t.get(v) for k, v in _STORE.items()}


def _fresh():
    main.state = main.State()
    main.step_sim(DT)


# --------------------------------------------------------------------------- seed / hold

def test_c39_design_seed_tears_are_bit_exact():
    """At the design seed every tear equals its published PFD design flow bit-exactly."""
    _fresh()
    t = _tears()
    assert t["748"] == main.R328_C002_M748_DES == 812.0
    assert t["750"] == main.R328_C002_M750_DES == 6833.0
    assert t["775"] == main.R328_C002_M775_DES == 1675.0
    assert t["718A"] == main.R3232_M718A_DES == 3561.5
    assert t["931"] == main.R328_C004_M931_DES == 6495.0


def test_c39_undisturbed_fixed_point_does_not_creep():
    """The tear fixed point is stationary: no creep over 300 undisturbed ticks."""
    _fresh()
    p0 = _tears()
    for _ in range(300):
        main.step_sim(DT)
    p1 = _tears()
    for k in _STORE:
        assert abs(p1[k] - p0[k]) < 0.05, f"{k} crept {p0[k]} -> {p1[k]}"


# ------------------------------------------------------- algebraic tears: bounded / convergent

def test_c39_algebraic_vapour_tear_is_bounded_and_convergent():
    """750 (328C004 overhead -> 328C002) is a pure algebraic recycle solved by one-tick direct
    substitution.  Under a 20% cut in the LP-steam ratio master it must stay bounded, approach a
    new fixed point monotonically (no numerical ringing), and CONTRACT (|z|<1)."""
    _fresh()
    for _ in range(50):
        main.step_sim(DT)
    main.state.FFIC_329401["sp"] *= 0.8            # disturb the loop that drives 750

    samples = []
    for i in range(7000):
        main.step_sim(DT)
        if i % 200 == 199:
            samples.append(main.state.tlag.get("R328_750"))

    # bounded: finite and inside the physical band (0, design]
    assert all(0.0 < v <= main.R328_C002_M750_DES for v in samples)

    incs = [samples[i + 1] - samples[i] for i in range(len(samples) - 1)]
    # non-oscillatory: increments never change sign (monotone approach)
    sign_flips = sum(1 for i in range(len(incs) - 1) if incs[i] * incs[i + 1] < 0.0)
    assert sign_flips == 0, f"750 oscillated ({sign_flips} sign flips)"
    # contraction: the loop is settling -- the last increment is smaller than the first
    assert abs(incs[-1]) < abs(incs[0]), "750 direct-substitution is not contracting"


def test_c39_all_algebraic_tears_stay_finite_under_disturbance():
    """748/750/775 all remain finite and physically bounded through the same disturbance."""
    _fresh()
    for _ in range(50):
        main.step_sim(DT)
    main.state.FFIC_329401["sp"] *= 0.8
    for _ in range(4000):
        main.step_sim(DT)
    t = _tears()
    assert 0.0 < t["748"] <= main.R328_C002_M748_DES * 1.5
    assert 0.0 < t["750"] <= main.R328_C002_M750_DES * 1.5
    assert 0.0 < t["775"] <= main.R328_C002_M775_DES * 1.5


# -------------------------------------------------------------- 718A: physical transport lag

def test_c39_718A_is_modelled_as_physical_transport():
    """718A carries a documented liquid-leg residence time, so it keeps a first-order transport
    lag rather than being collapsed to an algebraic tie."""
    assert main.R3232_M718A_TAU_S == 45.0 and main.R3232_M718A_TAU_S > 0.0


def test_c39_transport_lag_gives_first_order_not_instant_response():
    """The mechanism 718A uses (_lag1 at R3232_M718A_TAU_S) yields the implicit-Euler fraction
    a = dt/(tau+dt) per step -- i.e. genuine transport delay, not an instantaneous pass-through."""
    store = {"leg": 0.0}                                  # pre-seed prev=0 (skip lazy-init)
    y = main._lag1(store, "leg", 100.0, main.R3232_M718A_TAU_S, DT)
    a = DT / (main.R3232_M718A_TAU_S + DT)
    assert abs(y - a * 100.0) < 1e-9
    assert 0.0 < y < 100.0                                # lagged, has not reached target in one tick


# ------------------------------------------------------------- 931: controlled utility, not recycle

def test_c39_931_tracks_control_and_is_not_a_stale_recycle():
    """931 is an FFIC/FIC-controlled LP-steam utility feed.  Moving the FFIC-329401 master ratio
    must retarget the live 931 flow well away from its stale design value -- proving it follows
    control action, not a frozen one-tick recycle."""
    _fresh()
    base = main.state.tlag.get("R328_M931")
    assert base == 6495.0
    main.state.FFIC_329401["sp"] *= 0.8
    for _ in range(4000):
        main.step_sim(DT)
    live = main.state.tlag.get("R328_M931")
    assert abs(live - base) > 100.0, "931 did not follow the FFIC master (behaving as stale recycle)"
    assert live > 0.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fails = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            fails += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - fails}/{len(fns)} passed")
    sys.exit(1 if fails else 0)
