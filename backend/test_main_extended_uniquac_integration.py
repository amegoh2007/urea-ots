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


def test_steam_chest_tracks_the_connected_live_header() -> None:
    low_header = main.steam_chest_pressure(50.0, 4.0)
    high_header = main.steam_chest_pressure(50.0, 8.0)

    assert low_header == pytest.approx(2.0)
    assert high_header == pytest.approx(4.0)


def test_f010_gravity_outlet_has_independent_holdup_response() -> None:
    design = main.gravity_outflow_323f010(main.R323_F010_M_DES)
    quarter_holdup = main.gravity_outflow_323f010(0.25 * main.R323_F010_M_DES)

    assert design == main.R323_M317_DES
    assert quarter_holdup == pytest.approx(0.5 * main.R323_M317_DES)


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
