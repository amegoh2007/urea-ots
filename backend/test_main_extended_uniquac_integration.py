"""Focused wiring tests for the Unit-324 thermodynamic boundary."""

from __future__ import annotations

import pytest

import main


def test_evaporator_departure_is_computed_by_extended_uniquac(monkeypatch) -> None:
    calls: list[tuple[float, float]] = []

    def fake_solve(temperature_k: float, pressure_bara: float) -> float:
        calls.append((temperature_k, pressure_bara))
        return 0.90 + 0.001 * len(calls)

    monkeypatch.setattr(
        main.extended_uniquac, "solve_urea_mass_fraction_fast", fake_solve
    )

    result = main.evap_w_eq(131.0, 0.32, 0.9431, 130.0, 0.33)

    assert calls == [(404.15, 0.32), (403.15, 0.33)]
    assert result == pytest.approx(0.9421, abs=1.0e-15)


@pytest.mark.parametrize(
    ("temperature_c", "pressure_bara", "design_fraction"),
    [
        pytest.param(130.0, 0.33, 0.9431, id="stage-one"),
        pytest.param(140.0, 0.131, 0.9771, id="stage-two"),
    ],
)
def test_evaporator_departure_is_exact_at_design(
    temperature_c: float, pressure_bara: float, design_fraction: float
) -> None:
    assert main.evap_w_eq(
        temperature_c,
        pressure_bara,
        design_fraction,
        temperature_c,
        pressure_bara,
    ) == design_fraction


def test_legacy_fahmy_thermodynamic_path_is_retired() -> None:
    assert not hasattr(main, "_fahmy_Cu")


def _e002_chest(op_pct: float, header_bara: float, t_process_c: float) -> float:
    return main.steam_chest_pressure(
        op_pct, header_bara, main.R323_E002_OP_DES, main.R323_E002_PCHEST_DES,
        main.R323_E002_UA_KW, t_process_c, main.R323_E002_Q_DES_KW, main.R323_P_STEAM_SUP)


def test_steam_chest_is_steam_admitted_equals_steam_condensed() -> None:
    """Report A-5: the chest is no longer opening x header; it is where valve inflow meets wall duty."""
    design = _e002_chest(main.R323_E002_OP_DES, main.R323_P_STEAM_SUP, main.R323_C003_T_SP_C)
    assert design == pytest.approx(main.R323_E002_PCHEST_DES, abs=1e-8)

    # A richer header at the same opening lifts the chest, but never to the header itself.
    rich = _e002_chest(main.R323_E002_OP_DES, main.R323_P_STEAM_SUP + 1.0, main.R323_C003_T_SP_C)
    assert main.R323_E002_PCHEST_DES < rich < main.R323_P_STEAM_SUP + 1.0

    # A hotter process takes less steam, so the chest pressure RISES -- the old law could not move.
    hot = _e002_chest(main.R323_E002_OP_DES, main.R323_P_STEAM_SUP, main.R323_C003_T_SP_C + 3.0)
    assert hot > design


def test_shut_steam_valve_leaves_the_chest_at_process_saturation() -> None:
    shut = _e002_chest(0.0, main.R323_P_STEAM_SUP, main.R323_C003_T_SP_C)
    assert main.tsat_steam(shut) == pytest.approx(main.R323_C003_T_SP_C, abs=1e-6)


def test_f010_barometric_leg_responds_to_head_and_to_vacuum() -> None:
    """Report A-17.  The drain was `M317_DES*sqrt(M/M_DES)` -- a mass ratio, so a quarter of the
    holdup gave exactly half the flow and the vessel's own vacuum did nothing at all.  On a real
    barometric leg the liquid column is the SMALL term: about 64 mbar of melt against the 0.46 bar a
    the leg's own column is balancing, so level moves the drain a little and breaking the vacuum
    moves it a lot."""
    p_des = main.R323_F010_P_BARA
    design = main.gravity_outflow_323f010(main.R323_F010_M_DES, p_des)
    quarter = main.gravity_outflow_323f010(0.25 * main.R323_F010_M_DES, p_des)
    broken = main.gravity_outflow_323f010(main.R323_F010_M_DES, 1.01325)

    assert design == main.R323_M317_DES                       # design is exact, not approximate
    assert 0.90 * design < quarter < design                   # level is a real but minor term
    assert broken == pytest.approx(1.43 * design, rel=0.02)   # the seal is no longer holding atmosphere


def test_lv324501_route_selector_uses_documented_a_and_b_destinations() -> None:
    original_state = main.state
    try:
        main.state = main.State()
        # G12: LV-324501B is the PIC-335201 overpressure relief; normally closed at the design header.
        assert main.state.PIC_335201 < main.R335_LVB_RELIEF_BARG

        main.handle_cmd({"type": "lv324501_route_set", "route": "B"})     # deprecated alias forces relief
        assert main.state.PIC_335201 > main.R335_LVB_RELIEF_BARG

        main.handle_cmd({"type": "lv324501_route_set", "route": "A"})     # restores the design header
        assert main.state.PIC_335201 < main.R335_LVB_RELIEF_BARG

        with pytest.raises(ValueError, match="route must be A or B"):
            main.handle_cmd({"type": "lv324501_route_set", "route": "C"})
    finally:
        main.state = original_state
