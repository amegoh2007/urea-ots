"""Fresh-process fixed-point regression for the complete flowsheet."""

from __future__ import annotations

import math

import pytest

import main


UPSET_TOKENS = (
    "BLOW", "CARRY", "CAVIT", "CRYST", "DEPOSITION", "ENTRAIN", "EROSION",
    "FLOOD", "HYDROLYSIS_LOSS", "OVERLOAD", "SOLID", "TRIP", "VACUUM_COLLAPSE",
)

TRACKED_DESIGN_STATES = {
    "p_syn_bara": (main.SYN_P_DES_BARA, 0.15),
    "react_level_pct": (main.REACT_LEVEL_DES_M / main.REACT_LIQ_H_M * 100.0, 1.0),
    "scrub_level_pct": (main.SCRUB_LEVEL_NLL_PCT, 1.0),
    "strip_level": (main.STRIP_LEVEL_SP_DES, 1.0),
    "hpcc_level_pct": (main.HPCC_LEVEL_NLL_PCT, 1.0),
    "r323_c003_T": (main.R323_C003_T_SP_C, 1.0),
    "r323_f004_T": (main.R323_F004_T_SP_C, 1.0),
    "r323_f010_T": (main.R323_F010_T_SP_C, 1.0),
    "r324_e001_T": (main.R324_E001_T_SP_C, 1.0),
    "r324_e003_T": (main.R324_E003_T_SP_C, 1.0),
}


def fresh():
    main.state = main.State()
    return main.state


def test_hpcc_runtime_liquid_anchor_matches_fresh_design_seed():
    """Catch pinning HPCC inventory against a discarded CAS warm-up operating point."""
    fresh()
    packet = main.step_sim(0.1)
    live_liquid = packet["sm_diagnostics"]["hpcc"]["liq_kgh"]

    assert live_liquid == pytest.approx(main.HPCC_LIQ_DES_LIVE, rel=1.0e-6)


@pytest.mark.parametrize(
    ("controller_name", "chest_pressure"),
    [
        ("PIC_329202", main.R323_E002_PCHEST_DES),
        ("PIC_329208", main.R323_E010_PCHEST_DES),
        ("PIC_329203", main.R324_E001_PCHEST_DES),
    ],
)
def test_lp_steam_valve_seed_matches_live_header_design_pressure(controller_name, chest_pressure):
    """Catch a valve bias calculated from a different LP header than the live steam state."""
    state = fresh()
    controller = getattr(state, controller_name)
    live_chest = controller["op"] / 100.0 * state.steam.P_LP

    assert live_chest == pytest.approx(chest_pressure, abs=1.0e-12)


def test_fresh_process_remains_at_design_without_false_upsets_for_ten_minutes():
    """Catch any nonzero design residual that makes a fresh program invent an upset."""
    state = fresh()
    for _ in range(6000):
        main.step_sim(0.1)

    drift = {
        name: getattr(state, name) - expected
        for name, (expected, _) in TRACKED_DESIGN_STATES.items()
    }
    failures = {
        name: delta
        for name, delta in drift.items()
        if abs(delta) > TRACKED_DESIGN_STATES[name][1]
    }
    assert not failures, failures

    assert abs(state.r324_f001_P / main.R324_F001_P_BARA - 1.0) <= 0.03
    assert abs(state.r324_f003_P / main.R324_F003_P_BARA - 1.0) <= 0.03

    active_upsets = sorted(
        flag for flag, active in state.flags.items()
        if active and any(token in flag for token in UPSET_TOKENS)
    )
    assert not active_upsets, active_upsets

    for name, value in vars(state).items():
        if isinstance(value, float):
            assert math.isfinite(value), name
    for name in (
        "react_m_liq", "scrub_holdup_kg", "r323_c003_M", "r323_f004_M",
        "r323_f010_M", "r324_f001_M", "r324_f003_M", "a328_c002_M",
        "a328_c003_M", "a328_c004_M", "a328_d001_M",
    ):
        assert getattr(state, name) >= 0.0, name
