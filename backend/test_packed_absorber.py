"""322C001 on rate-based transfer units (packed_absorber, As-Built Phase 5m).

The column was a boot-pinned fraction of the offered off-gas MASS, so its slip was a ~2 % residual of
two proportional terms and it had no capacity.  These tests exercise the law on its own, at the PFD
design and at the upsets the fraction could not express.  No engine import: the design gas is PFD 204,
the washes PFD 755 / 954 and the liquor PFD 756.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import packed_absorber as pa  # noqa: E402

MW = pa.MW
GAS = {k: 64.78 * v / 100.0 for k, v in
       {"CH4": 5.93, "CO2": 2.22, "H2": 3.14, "H2O": 0.26, "N2": 68.81, "NH3": 8.26, "O2": 11.39}.items()}
W755 = {"CO2": 0.0381, "H2O": 0.9113, "NH3": 0.0417, "Urea": 0.0089}
W756 = {"CO2": 0.0379, "H2O": 0.9118, "NH3": 0.0420, "Urea": 0.0083}
TARGET = {"NH3": 89.33 / MW["NH3"], "CO2": 62.00 / MW["CO2"], "H2O": -21.33 / MW["H2O"]}
_CAL = {}


def _cal():
    if not _CAL:
        _CAL.update(pa.calibrate(GAS, 43.0, 46.0, 3.9, 31478.0, W755, 1750.0, W756, TARGET))
    return _CAL


def _run(gas=GAS, t_liq=43.0, t_cpl=46.0, p=3.9, m755=31478.0, cpl=1750.0, liquor=W756):
    return pa.solve(gas, t_liq, t_cpl, p, m755, W755, cpl, liquor, _cal(), passes=200)


def _slip(r, sp):
    return r["vent_kmolh"][sp] * MW[sp]


def test_the_packing_and_beds_are_the_vendor_documents():
    assert pa.A_PACK == 250.0 and pa.D_PACK == 0.025                   # Raflux 25-10 datasheet
    assert pa.BED_LO == {"Z": 1.5, "ID": 0.922}                        # EC-0007 + arrangement rev 02
    assert pa.BED_UP == {"Z": 1.0, "ID": 0.576}


def test_design_uptake_is_the_pfd_split_and_the_factors_are_onda_sized():
    """The per-species factor is the only unsourced number, and it lands inside Onda's own +/-30 %."""
    cal = _cal()
    r = _run()
    for sp in ("NH3", "CO2", "H2O"):
        assert abs(r["absorbed_kmolh"][sp] - TARGET[sp]) < 1e-6 * max(abs(TARGET[sp]), 1.0), sp
    assert 0.6 < cal["NH3"] < 1.3 and 0.6 < cal["CO2"] < 1.3, cal
    vent = r["vent_kmolh"]
    tot = sum(vent.values())
    assert abs(vent["H2O"] / tot - 0.0228) < 2e-4                       # PFD 797 water, saturated
    assert abs(vent["NH3"] / tot - 0.0018) < 1e-4                       # PFD 797 NH3


def test_the_lower_bed_pinches_on_the_ammonia_water_back_pressure():
    """Stream 755 at 43 C holds ~1.2 mol% NH3 in the gas above it: the lower bed cannot take the vent
    lower than that, which is why the CPL-washed upper bed exists."""
    r = _run()
    assert 0.008 < r["y_star_lo"]["NH3"] < 0.016
    assert r["ntu"]["lo_NH3"] > 5.0                                    # at its pinch
    assert 1.0 < r["ntu"]["up_NH3"] < 5.0                              # the polishing bed does the work


def test_more_gas_slips_more_and_less_gas_slips_less():
    base = _slip(_run(), "NH3")
    assert _slip(_run(gas={k: 1.5 * v for k, v in GAS.items()}), "NH3") > 1.5 * base
    assert _slip(_run(gas={k: 0.4 * v for k, v in GAS.items()}), "NH3") < 0.4 * base


def test_losing_the_cpl_wash_breaks_the_nh3_through():
    assert _slip(_run(cpl=0.0), "NH3") > 5.0 * _slip(_run(), "NH3")


def test_a_hot_liquor_releases_what_it_should_hold():
    """Back-pressure is exponential in temperature: at 80 C the wash strips CO2 instead of taking it."""
    base = _run()
    hot = _run(t_liq=80.0)
    assert _slip(hot, "NH3") > 3.0 * _slip(base, "NH3")
    assert hot["absorbed_kmolh"]["CO2"] < 0.0


def test_a_breakthrough_without_the_322p002_wash_overruns_the_column():
    """The capacity the fraction never had: twenty times the NH3/CO2 with no 755 wash."""
    brk = dict(GAS)
    brk["NH3"] *= 20.0
    brk["CO2"] *= 20.0
    r = _run(gas=brk, m755=0.0)
    assert _slip(r, "NH3") > 100.0 * _slip(_run(), "NH3")
    assert r["dT_up"] > 20.0                                            # the CPL boils toward its limit


def test_one_pass_from_the_steady_tear_is_the_steady_state():
    """The engine takes one pass a tick on the lagged bed-coupling tear; at steady state that is the
    relaxed solution, so the lag cannot move the design point."""
    ss = _run()
    one = pa.solve(GAS, 43.0, 46.0, 3.9, 31478.0, W755, 1750.0, W756, _cal(), abs_up=ss["abs_up"])
    for sp in ("NH3", "CO2", "H2O"):
        assert abs(one["absorbed_kmolh"][sp] - ss["absorbed_kmolh"][sp]) < 1e-9


def test_the_back_pressure_is_continuous_in_temperature_and_loading():
    a = pa.back_pressure(W755, 43.0)
    b = pa.back_pressure(W755, 43.0 + 1e-6)
    assert all(abs(x - y) <= 1e-4 * abs(x) for x, y in zip(a, b))
    lo = pa.back_pressure(W755, 30.0)[0]
    hi = pa.back_pressure(W755, 60.0)[0]
    assert hi > 2.0 * lo                                                # NH3 pressure climbs with T


def test_the_upper_bed_liquid_residence_is_its_film_holdup():
    tau = pa.liquid_residence_s(pa.BED_UP, 1750.0, 319.15)
    assert 15.0 < tau < 35.0
    assert pa.liquid_residence_s(pa.BED_UP, 0.0, 319.15) == 3600.0
    assert math.isfinite(pa.onda_ntu("NH3", pa.BED_UP, 0.0, 1500.0, 59.0, 319.15, 3.9e5))


def test_no_gas_takes_nothing_up_and_still_hands_back_the_tear():
    """HV-322604 shut (the CCW-loss chain reaches it): no uptake, no slip, and the bed-coupling tear
    the engine lags is zero rather than missing."""
    r = pa.solve({k: 0.0 for k in GAS}, 43.0, 46.0, 3.9, 31478.0, W755, 1750.0, W756, _cal(),
                 abs_up=_cal()["abs_up"])
    assert r["abs_up"] == {"NH3": 0.0, "CO2": 0.0, "dT": 0.0}
    assert all(v == 0.0 for v in r["absorbed_kmolh"].values())
    assert all(v == 0.0 for v in r["vent_kmolh"].values())


def test_the_heat_of_absorption_carries_the_carbamate():
    """The slope of the speciated back-pressure is the whole heat: CO2 into ammonia water forms
    carbamate and bicarbonate, 80 kJ/mol, where the bare Henry constant would say 16."""
    dh_n, dh_c = pa.heat_of_absorption_j_mol(W756, 43.0)
    assert 30e3 < dh_n < 40e3
    assert 70e3 < dh_c < 100e3


def test_the_back_pressure_carries_on_past_the_speciation_range():
    """A boiling liquor must keep its pressures rising: held flat at 100 C, a CCW-loss dump went on
    absorbing while the liquor sat at 150 C.  Continuous at the edge, van 't Hoff beyond it."""
    loaded = {"CO2": 0.11, "H2O": 0.72, "NH3": 0.157, "Urea": 0.0066}
    lo = pa.back_pressure(loaded, 100.0 - 1e-6)
    hi = pa.back_pressure(loaded, 100.0 + 1e-6)
    assert all(abs(a - b) <= 1e-4 * abs(a) for a, b in zip(lo, hi))
    p110, p150 = pa.back_pressure(loaded, 110.0), pa.back_pressure(loaded, 150.0)
    assert p150[0] > 2.0 * p110[0] and p150[1] > 5.0 * p110[1]
    cold = pa.back_pressure(W756, 5.0)
    assert 0.0 < cold[0] < pa.back_pressure(W756, 10.0)[0]
