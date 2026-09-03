"""Regression tests for the HP carbamate-recycle causal chain."""

import pytest

import thermo_urea_hp as hp
import reactor
import hp_recycle
import main as simulation


def test_hp_equilibrium_water_penalty_and_design_anchor():
    """Catches a missing/reversed H/C term or loss of the plant conversion anchor."""
    assert hp.conversion_factor(hp.NC_DES, hp.HC_DES, hp.T_DES_C) == pytest.approx(1.0)
    assert hp.equilibrium_conversion(3.1, 0.8, 183.0) < hp.equilibrium_conversion(3.1, 0.4, 183.0)


def test_synthesis_ratios_count_reacted_products_as_feed_equivalents():
    """Catches raw NH3/CO2 ratios that change merely because urea formed."""
    nc, hc = hp.synthesis_ratios({"NH3": 300.0, "CO2": 50.0, "H2O": 80.0, "Urea": 50.0})
    assert nc == pytest.approx(4.0)
    assert hc == pytest.approx(0.3)


def test_reactor_uses_hp_package_and_conserved_ratios():
    """Catches fallback to the fabricated curve or raw molecular feed ratios."""
    feed = {"NH3": 300.0, "CO2": 50.0, "H2O": 80.0, "Urea": 50.0}
    overflow = {"NH3": 200.0, "CO2": 30.0, "H2O": 100.0, "Urea": 100.0}
    _xi, _ov, conversion, nc, hc = reactor.react_couple(feed, overflow, 20.0)
    assert conversion == pytest.approx(hp.plant_anchored_conversion(4.0, 0.3, 183.0))
    assert nc == pytest.approx(4.0)
    assert hc == pytest.approx(0.3)


def test_323p001_flow_follows_triplex_displacement_and_running_limits():
    """Catches a centrifugal pressure curve or loss of datasheet speed limits."""
    assert hp_recycle.pump_323p001_flow_m3h(0.0) == 0.0
    assert hp_recycle.pump_323p001_flow_m3h(64.0) == pytest.approx(32.2944)
    assert hp_recycle.pump_323p001_flow_m3h(80.0) == pytest.approx(
        2.0 * hp_recycle.pump_323p001_flow_m3h(40.0)
    )
    assert hp_recycle.pump_323p001_flow_m3h(5.0) == pytest.approx(0.5046 * 19.0)
    assert hp_recycle.pump_323p001_flow_m3h(90.0) == pytest.approx(0.5046 * 81.0)
    assert hp_recycle.pump_323p001_flow_m3h(64.0, suction_factor=0.5) == pytest.approx(16.1472)


def test_reactive_scrubber_capacity_controls_breakthrough_and_closes_components():
    """Catches non-conservative gain injection or a reversed solvent-flow gradient."""
    gas_feed = {"NH3": 100.0, "CO2": 50.0, "N2": 10.0}
    wash_low = {"NH3": 10.0, "CO2": 2.5, "H2O": 25.0}
    wash_high = {"NH3": 30.0, "CO2": 7.5, "H2O": 75.0}
    design_capacity = {"NH3": 80.0, "CO2": 40.0, "H2O": 0.0}

    low = hp_recycle.reactive_scrubber_split(gas_feed, wash_low, design_capacity, 0.5)
    high = hp_recycle.reactive_scrubber_split(gas_feed, wash_high, design_capacity, 1.5)

    assert high["gas"]["NH3"] < low["gas"]["NH3"]
    assert high["gas"]["CO2"] < low["gas"]["CO2"]
    assert sum(high["liquid"].values()) > sum(low["liquid"].values())
    for component in set(gas_feed) | set(wash_low):
        inlet = gas_feed.get(component, 0.0) + wash_low.get(component, 0.0)
        outlet = low["gas"].get(component, 0.0) + low["liquid"].get(component, 0.0)
        assert outlet == pytest.approx(inlet)


def test_vent_retains_gas_above_finite_valve_capacity():
    """Catches the former behavior that multiplied and vented the full gas supply."""
    result = hp_recycle.capacity_limited_vent(
        {"NH3": 20.0, "CO2": 10.0, "N2": 5.0},
        {"NH3": 17.0, "CO2": 44.0, "N2": 28.0},
        capacity_kgh=500.0,
    )
    assert result["available_kgh"] == pytest.approx(920.0)
    assert result["vented_kgh"] == pytest.approx(500.0)
    assert result["retained_kgh"] == pytest.approx(420.0)
    assert sum(result["retained"].values()) > 0.0


def test_conversion_loss_adds_carbamate_recycle_and_stripper_steam():
    """Catches a reactor conversion change that has no downstream energy consequence."""
    burden = hp_recycle.conversion_loss_burden(100.0, 90.0)
    assert burden["unconverted_co2_kmolh"] == pytest.approx(10.0)
    assert burden["hpcc_recycle_increment_kgh"] == pytest.approx(780.0)
    assert burden["stripper_steam_increment_kgh"] == pytest.approx(1050000.0 / 1850.0)


def test_recycle_deficit_sets_sustainable_load_without_penalizing_surplus():
    """Catches a missing front-end cutback requirement at severe recycle shortage."""
    assert hp_recycle.sustainable_load_factor(0.5, 1.0) == pytest.approx(0.5)
    assert hp_recycle.sustainable_load_factor(1.2, 1.0) == pytest.approx(1.0)


def test_live_scrubber_wash_gradient_is_mass_conserving_and_thermal():
    """Catches loss of the gas/liquid and cold-wash gradients in the live unit function."""
    cases = {
        scale: simulation.scrub_322e003(
            simulation.REACT_OFFGAS_DES,
            1.0,
            simulation.SCRUB_CCW_T_IN_DES,
            simulation.SCRUB_CCW_KGH_DES,
            wash_scale=scale,
        )
        for scale in (0.5, 1.0, 1.3)
    }
    low, design, high = cases[0.5], cases[1.0], cases[1.3]
    assert high["breakthrough_kmolh"] < design["breakthrough_kmolh"] < low["breakthrough_kmolh"]
    assert high["T_offgas"] < design["T_offgas"] < low["T_offgas"]
    assert high["T_overflow"] < design["T_overflow"] < low["T_overflow"]
    assert sum(high["overflow_kmolh"].values()) > sum(low["overflow_kmolh"].values())
    assert max(abs(v) for v in low["closure_kmolh"].values()) < 1e-9


def _run_323p001_case(rpm: float, seconds: int = 300):
    simulation.state = simulation.State()
    state = simulation.state
    state.SIC_323901["mode"] = "MAN"
    state.SIC_323901["op"] = rpm
    packet = None
    for _ in range(seconds):
        packet = simulation.step_sim(1.0)
    return state, packet


def test_low_recycle_pressurizes_hp_loop_and_overloads_absorber():
    """Catches the former wrong-sign pressure response to loss of 323P001 wash."""
    low_state, low = _run_323p001_case(32.0)
    high_state, high = _run_323p001_case(80.0)
    low_scrub, high_scrub = low["SCRUB_322E003"], high["SCRUB_322E003"]
    low_reactor, high_reactor = low["REACT_322R001"], high["REACT_322R001"]

    assert low_state.p_syn_bara > high_state.p_syn_bara + 0.2
    assert low_scrub["breakthrough_th"] > high_scrub["breakthrough_th"]
    assert low_scrub["retained_gas_th"] > 0.0
    assert low_scrub["lp_absorber_load_ratio"] > simulation.SCRUB_LP_ABS_CAPACITY_RATIO
    assert low_scrub["lp_absorber_relief_th"] > 0.0
    assert low_reactor["sustainable_production_factor"] < 0.6
    assert low_reactor["W_feed"] < high_reactor["W_feed"]
    assert low_reactor["X_conv"] > high_reactor["X_conv"]
    assert abs(low_reactor["L_feed"] - high_reactor["L_feed"]) > 0.01
    assert low_state.react_level_pct < high_state.react_level_pct
