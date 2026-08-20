"""Focused PFD-path regressions for the Unit 329 steam/condensate network."""

import pytest

import steam_system


def _isolated_lp_state(pressure_bara: float) -> steam_system.SteamState:
    """Return a state with only the selected LP pressure leg free to move."""
    state = steam_system.SteamState(P_LP=pressure_bara)
    state.master207_on = False
    state.pic207a_mode = "MAN"
    state.pic207_mode = "MAN"
    state.pic207c_mode = "MAN"
    state.pv207a_pct = 0.0
    state.pv207b_pct = 0.0
    state.valve_963_pct = 0.0
    return state


def _step_with_balanced_lp_sources(state: steam_system.SteamState) -> None:
    steam_system.step_steam(
        state,
        dt=0.1,
        m_strip_consume=0.0,
        m_hpcc_gen=steam_system.M_USERS_LP,
        m_9_users=0.0,
    )


def test_pv329207b_opens_on_high_pressure_and_exports_from_lp_header():
    """Catches reversed B action or counting the turbine leg as an LP inlet."""
    exported = _isolated_lp_state(4.6)
    exported.pic207_mode = "AUTO"
    exported.pic207_sp = 4.4

    shut = _isolated_lp_state(4.6)

    _step_with_balanced_lp_sources(exported)
    _step_with_balanced_lp_sources(shut)

    assert exported.pv207b_pct > 0.0
    assert exported.m_turbine > 0.0
    assert exported.P_LP < shut.P_LP


def test_pv329207c_opens_on_low_pressure_and_makes_up_lp_header():
    """Catches reversed C action or counting battery-limit make-up as an outlet."""
    admitted = _isolated_lp_state(4.1)
    admitted.pic207c_mode = "AUTO"
    admitted.pic207c_sp = 4.3

    shut = _isolated_lp_state(4.1)

    _step_with_balanced_lp_sources(admitted)
    _step_with_balanced_lp_sources(shut)

    assert admitted.valve_963_pct > 0.0
    assert admitted.m_963 > 0.0
    assert admitted.P_LP > shut.P_LP


def test_d009_liquid_balance_deducts_flash_vapor_from_lv329502_inflow():
    """Catches violating PFD identity 904 = 905 liquid + 906 vapor."""
    state = steam_system.SteamState()
    state.lic502_mode = "MAN"
    state.lic503_mode = "MAN"
    state.lic502_op = 50.0
    state.lic503_op = 0.0
    initial_level = state.lic503_lvl

    steam_system.step_steam(
        state,
        dt=1.0,
        m_strip_consume=steam_system.M_STRIP_DES,
        m_hpcc_gen=0.0,
        m_9_users=steam_system.M_USERS_9_DES,
    )

    accumulated_kg = (state.lic503_lvl - initial_level) / 100.0 * steam_system.MSPAN_503
    expected_kg = steam_system.M_502_DES - state.m_flash9
    assert getattr(state, "mass_residual_d009_liquid", None) == pytest.approx(
        expected_kg, abs=1e-10
    )
    assert accumulated_kg == pytest.approx(expected_kg, abs=1e-10)


def test_d009_flash_vapor_stops_when_lv329502_is_shut():
    """Catches generating flash vapor without condensate crossing LV329502."""
    state = steam_system.SteamState()
    state.lic502_mode = "MAN"
    state.lic502_op = 0.0

    steam_system.step_steam(
        state,
        dt=1.0,
        m_strip_consume=steam_system.M_STRIP_DES,
        m_hpcc_gen=0.0,
        m_9_users=steam_system.M_USERS_9_DES,
    )

    assert state.m_flash9 == pytest.approx(0.0, abs=1e-12)


def test_9bar_design_sources_reproduce_strict_pfd_identity():
    """Catches conflating stream 906 flash with the 275 kg/h saturation-water increment."""
    state = steam_system.SteamState()

    steam_system.step_steam(
        state,
        dt=0.1,
        m_strip_consume=steam_system.M_STRIP_DES,
        m_hpcc_gen=steam_system.M_HPCC_DES,
        m_9_users=steam_system.M_USERS_9_DES,
    )

    assert state.m_903 * 3600.0 == pytest.approx(1754.0, abs=1e-9)
    assert state.m_flash9 * 3600.0 == pytest.approx(4658.0, abs=1e-9)
    assert getattr(state, "m_attemper9", 0.0) * 3600.0 == pytest.approx(275.0, abs=1e-9)
    assert getattr(state, "mass_residual_d009_vapor", None) == pytest.approx(0.0, abs=1e-12)


def test_lp_drum_liquid_balance_includes_lv329503_inflow():
    """Catches dropping the D009 condensate transfer at the LP-drum boundary."""
    state = steam_system.SteamState()
    state.lic502_mode = "MAN"
    state.lic503_mode = "MAN"
    state.lic504_mode = "MAN"
    state.lic502_op = 0.0
    state.lic503_op = 50.0
    state.lic504_op = 0.0
    initial_level = state.lic504_lvl

    steam_system.step_steam(
        state,
        dt=1.0,
        m_strip_consume=0.0,
        m_hpcc_gen=0.0,
        m_9_users=0.0,
    )

    accumulated_kg = (state.lic504_lvl - initial_level) / 100.0 * steam_system.MSPAN_504
    assert getattr(state, "mass_residual_lp_liquid", None) == pytest.approx(
        steam_system.M_503_DES, abs=1e-10
    )
    assert accumulated_kg == pytest.approx(steam_system.M_503_DES, abs=1e-10)
