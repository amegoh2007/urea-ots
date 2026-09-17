"""Regression gate for the 322C001 LP-absorber species layer (TD-009 remainder).

The LP off-gas absorber used to carry NO composition: the atmospheric NH3 slip was a boot-pinned
scalar split (A328_PHI_ABS * gcb_m) with no vent `y`.  The species layer adds, ON TOP of the
untouched total-mass / energy ODEs:

  * a six-species liquor vector s.a328_c001_w (Sum w == 1), the recycle ammonia-water 755/756 loop;
  * per-species uptake from `packed_absorber` (Phase 5m): Onda transfer units per bed against the
    Extended UNIQUAC back-pressure of the wash, calibrated at the boot pin to the PFD 204 -> 797 split;
  * a LIVE per-species vent composition y = (off-gas - absorbed), so the NH3 slip is a real number.

This gate proves the layer is a fixed point at design and moves the right way off it; the law's own
off-design behaviour (capacity, CPL loss, hot liquor) is in test_packed_absorber.py.

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


def test_absorbed_splits_on_the_pfd_vapour_rows():
    """The design 130 kg/h is PFD 204 in minus PFD 797 out per species (report A-2): NH3 and CO2 are
    taken up, water vapour is given off, and the three sum to A328_ABS_DES."""
    total = main.A328_ABS_CO2_DES + main.A328_ABS_NH3_DES + main.A328_ABS_H2O_DES
    assert abs(total - main.A328_ABS_DES) < 1e-9                                  # closure
    assert abs(main.A328_ABS_NH3_DES / main.MW_COMP["NH3"] - (5.351 - 0.107)) < 0.01   # 204 - 797, kmol/h
    assert abs(main.A328_ABS_CO2_DES / main.MW_COMP["CO2"] - (1.438 - 0.030)) < 0.01
    assert abs(main.A328_ABS_H2O_DES / main.MW_COMP["H2O"] - (0.168 - 1.353)) < 0.01


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
    assert 0.5 < c["vent_nh3_kgh"] < 5.0                                         # PFD 797: 0.11 kmol/h = 1.9 kg/h
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
    #  Report A-2: on PFD 204 the design slip is PFD 797's 1.9 kg/h, not the ~1557 kg/h of the
    #  NH3-rich Path-B vent, so the direction is asserted as a fraction of it.  Measured on the
    #  transfer-unit law (Phase 5m): HIC-322604 at 60 % takes the slip from 1.8 to 4.2 kg/h.
    assert up > base * 1.10, (base, up)                                           # open -> slip rises
    assert dn < base * 0.95, (base, dn)                                           # throttle -> slip falls


def test_the_liquor_balance_closes_on_real_enthalpies():
    """Phase 5m.  The liquor balance used to close on a back-solved 21 kJ/kg absorption heat and the
    liquor's cp for the gas.  On H0 enthalpies and the speciated heats of absorption the design seed
    closes to within the PFD's rounded temperatures by itself, so the one anchor left is a few kW."""
    assert abs(main.A328_C001_Q_RES_KW) < 5.0
    # one kmol/h of NH3 taken up at the gas's own temperature releases its heat of absorption, ~10 kW
    q = main.c001_offgas_heat_kw({"NH3": 1.0}, 43.0, 43.0, {"NH3": 1.0}, main.W_C001_DES)
    assert 8.5 < q < 11.0
    # water the vent picks up (absorbed < 0) is paid for at its latent heat
    q_w = main.c001_offgas_heat_kw({}, 43.0, 43.0, {"H2O": -1.0}, main.W_C001_DES)
    assert -12.5 < q_w < -11.5
