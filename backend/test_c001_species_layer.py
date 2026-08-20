"""Regression gate for the 322C001 LP-absorber species layer (TD-009 remainder).

The LP off-gas absorber used to carry NO composition: the atmospheric NH3 slip was a boot-pinned
scalar split (A328_PHI_ABS * gcb_m) with no vent `y`.  The species layer adds, ON TOP of the
untouched total-mass / energy ODEs:

  * a six-species liquor vector s.a328_c001_w (Sum w == 1), the recycle ammonia-water 755/756 loop;
  * the reactive-absorption split CO2 + 2 NH3 -> carbamate at the frozen carbamate mass ratio;
  * a LIVE per-species vent composition y = (off-gas - absorbed), so the NH3 slip is a real number.

The total recovered mass keeps the boot-pinned A328_PHI_ABS, so C1, the energy balance and the
15-key boot pin are byte-identical — this gate proves the layer is a fixed point at design and moves
the right way off it.

Run from backend/:  python -m pytest test_c001_species_layer.py -q -p no:cacheprovider
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402

DT = 0.25


def _fresh(seconds=300.0):
    main.state = main.State()
    _run(seconds)
    return main.state


def _run(seconds):
    out = None
    for _ in range(int(seconds / DT)):
        out = main.step_sim(DT)
    return out


def _c001():
    return main.step_sim(DT)["ABSORB_328"]["C001"]


def test_absorbed_splits_at_carbamate_stoichiometry():
    """The design 130 kg/h splits 2 NH3 : 1 CO2 (mole) and the two parts sum to A328_ABS_DES exactly."""
    assert main.A328_ABS_CO2_DES + main.A328_ABS_NH3_DES == main.A328_ABS_DES     # bit-exact closure
    n_co2 = main.A328_ABS_CO2_DES / main.MW_COMP["CO2"]
    n_nh3 = main.A328_ABS_NH3_DES / main.MW_COMP["NH3"]
    assert abs(n_nh3 / n_co2 - 2.0) < 1e-9                                        # carbamate stoichiometry


def test_design_liquor_is_stationary_and_bitexact():
    """At the seed the liquor vector equals the design feed mix and does not drift; TT holds 43 C."""
    main.state = main.State()
    w0 = dict(main.state.a328_c001_w)
    assert w0 == main.W_C001_DES                                                  # seeded on the anchor
    _run(600.0)
    s = main.state
    drift = max(abs(s.a328_c001_w[k] - main.W_C001_DES[k]) for k in s.a328_c001_w)
    assert drift < 1e-9, drift                                                    # stationary fixed point
    assert abs(sum(s.a328_c001_w.values()) - 1.0) < 1e-12                         # C6 summation
    c = _c001()
    assert abs(c["TT_322015"] - 43.0) < 1e-3                                      # energy balance untouched
    assert abs(c["abs_th"] - 0.130) < 1e-4                                        # 130 kg/h recovered


def test_absorber_conserves_total_mass_at_design():
    """Off-gas in == absorbed (to liquor) + vent (to 328V001): the vapour-path mass balance closes."""
    _fresh(600.0)
    c = _c001()
    assert abs(c["gcb_th"] - (c["abs_th"] + c["vent_th"])) < 5e-3, c              # in == out


def test_vent_carries_a_live_nh3_slip():
    """The vent is no longer composition-blind: it reports a nonzero NH3 slip and CO2, and the two
    plus the inerts are a normalised composition (each between 0 and 100 %)."""
    _fresh(600.0)
    c = _c001()
    assert c["vent_nh3_kgh"] > 1000.0                                             # design slip ~1557 kg/h
    assert 0.0 < c["vent_nh3_pct"] < 100.0 and 0.0 < c["vent_co2_pct"] < 100.0
    assert c["vent_nh3_pct"] + c["vent_co2_pct"] < 100.0                          # inerts take the balance


def test_vent_nh3_slip_tracks_offgas_throughput():
    """Open HV-322604 -> more inert-purge off-gas -> more NH3 slip; throttle it -> less.  This is the
    live behaviour the boot-pinned scalar could not express."""
    s = _fresh(600.0)
    base = _c001()["vent_nh3_kgh"]
    s.HIC_322604 = 60.0
    _run(600.0)
    up = _c001()["vent_nh3_kgh"]
    s.HIC_322604 = 40.0
    _run(600.0)
    dn = _c001()["vent_nh3_kgh"]
    assert up > base + 1.0, (base, up)                                            # open -> slip rises
    assert dn < base - 1.0, (base, dn)                                            # throttle -> slip falls
