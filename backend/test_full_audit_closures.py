"""Evidence-backed regression tests for the 2026-07-26 full-model audit."""

import math

import main
import steam_system


def test_hydrolysis_rate_matches_inoue_otsuka_correlation():
    """Inoue/Otsuka Eq. (6): ln(k_H) = 21.8 - 11100/T, k in m3/(kmol h)."""
    temperature_k = 160.0 + 273.15
    expected = math.exp(21.8 - 11_100.0 / temperature_k)
    assert main.urea_hydrolysis_k_m3_kmol_h(160.0) == expected


def test_hydrolysis_conversion_uses_water_concentration():
    wet = main.hydrolysis_x_328c003(
        160.0, main.R328_C003_M746_DES,
        w_urea=0.01, w_h2o=0.98, rho_kgm3=900.0,
    )
    dry = main.hydrolysis_x_328c003(
        160.0, main.R328_C003_M746_DES,
        w_urea=0.50, w_h2o=0.49, rho_kgm3=900.0,
    )
    assert 0.0 < dry < wet < 1.0


def test_hpcc_shell_tracks_internal_lp_header_pressure():
    main.state = main.State()
    main.state.steam.P_LP = 6.5
    packet = main.step_sim(0.1)
    lp = packet["STEAM_SYSTEM"]["LP"]
    assert abs(lp["TI_HPCC_shell"] - lp["TI_sat"]) <= 0.1


def test_evaporator_equilibrium_uses_live_pressure():
    main.state = main.State()
    main.state.r324_f001_P = 0.60
    main.state.r324_f003_P = 0.25
    main.step_sim(0.1)
    expected_e001 = main.evap_w_eq(
        main.state.r324_e001_T, main.state.r324_f001_P,
        main.R324_W_EV1, main.R324_E001_T_SP_C, main.R324_F001_P_BARA,
    )
    expected_e003 = main.evap_w_eq(
        main.state.r324_e003_T, main.state.r324_f003_P,
        main.R324_W_EV2, main.R324_E003_T_SP_C, main.R324_F003_P_BARA,
    )
    assert main._DIAG["E001"]["weq"] == expected_e001
    assert main._DIAG["E003"]["weq"] == expected_e003


def test_9bar_header_reproduces_pfd_makeup_flow():
    state = steam_system.SteamState()
    steam_system.step_steam(
        state, 0.1,
        steam_system.M_STRIP_DES,
        steam_system.M_HPCC_DES,
        steam_system.M_USERS_9_DES,
    )
    assert abs(state.m_903 - steam_system.M_903_DES) <= 1e-12
    assert abs(state.P_9 - steam_system.P_MP_BARA) <= 1e-12


def test_9bar_header_demand_changes_pressure():
    state = steam_system.SteamState()
    steam_system.step_steam(
        state, 1.0,
        steam_system.M_STRIP_DES,
        steam_system.M_HPCC_DES,
        steam_system.M_USERS_9_DES * 1.2,
    )
    assert state.P_9 < steam_system.P_MP_BARA


def test_recycle_tear_residual_is_reported_without_solver_claim():
    main.state = main.State()
    packet = main.step_sim(0.1)
    residual = packet["RECYCLE_TEAR_RESIDUAL"]
    assert residual["method"] == "observed_dynamic_transport_tears"
    assert residual["is_solver_convergence"] is False
    assert residual["max_relative_residual"] >= 0.0
    assert residual["tolerance"] > 0.0
    assert isinstance(residual["settled"], bool)
