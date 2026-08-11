"""Dynamic parity tests for listed and unlisted downstream consequences."""

from __future__ import annotations

import pytest

import main


SEAL_LOSS_ROUTES = (
    "322E001_TO_323C003",
    "323C003_TO_323F004",
    "323F004_TO_323F010",
    "323F010_TO_324E002",
    "328C003_TO_328C004",
    "328C004_TO_740",
    "322C001_TO_323E003",
)


@pytest.mark.parametrize("route_name", SEAL_LOSS_ROUTES)
def test_every_seal_loss_connection_uses_a_consequence_route(route_name):
    """Catch an unlisted vessel reverting to a flag-only or scalar-only path."""
    assert route_name in main.CONSEQUENCE_ROUTES


def test_route_design_dead_times_are_positive_and_bounded():
    """Catch zero-time teleportation or an operationally useless delay."""
    for route in main.CONSEQUENCE_ROUTES.values():
        assert 2.0 <= route.design_dead_time_s <= 120.0
        assert route.line_inventory_kg > 0.0


def _fresh_and_run(seconds: float, before_step=None):
    main.state = main.State()
    packet = None
    for _ in range(round(seconds / 0.1)):
        if before_step is not None:
            before_step(main.state)
        packet = main.step_sim(0.1)
    return main.state, packet


def test_unlisted_hydrolyser_seal_loss_reaches_desorber_with_one_closed_packet():
    """Catch 328C003 low level remaining a local flag with no delayed D/S gas load."""
    state, _ = _fresh_and_run(20.0)
    pressure_before = state.a328_c004_P

    def hold_hydrolyser_empty(live_state):
        live_state.a328_c003_M = 1.0

    early_peak = 0.0
    for _ in range(10):
        hold_hydrolyser_empty(state)
        packet = main.step_sim(0.1)
        early_peak = max(
            early_peak,
            packet["CONSEQUENCE_TRANSPORT"]["328C003_TO_328C004"]["arrived_mass_kgh"],
        )
    assert early_peak == 0.0

    arrived_peak = 0.0
    pressure_peak = pressure_before
    arrived_diag = None
    for _ in range(200):
        hold_hydrolyser_empty(state)
        packet = main.step_sim(0.1)
        diag = packet["CONSEQUENCE_TRANSPORT"]["328C003_TO_328C004"]
        if diag["arrived_mass_kgh"] > arrived_peak:
            arrived_peak = diag["arrived_mass_kgh"]
            arrived_diag = diag
        pressure_peak = max(pressure_peak, state.a328_c004_P)

    assert arrived_diag is not None
    assert arrived_peak > 0.0
    assert sum(arrived_diag["component_kgh"].values()) == pytest.approx(arrived_peak)
    assert sum(arrived_diag["mass_fraction"].values()) == pytest.approx(1.0)
    assert pressure_peak > pressure_before


def test_lp_absorber_seal_loss_adds_delayed_closed_gas_load_to_lpcc():
    """Catch 322C001 seal loss failing to affect the receiving LPCC inventory and properties."""
    state, _ = _fresh_and_run(20.0)
    inventory_before = state.r3232_d001_M
    state.LIC_322502["mode"] = "MAN"
    state.LIC_322502["op"] = 100.0

    def hold_absorber_empty(live_state):
        live_state.a328_c001_M = 1.0

    early_peak = 0.0
    for _ in range(10):
        hold_absorber_empty(state)
        packet = main.step_sim(0.1)
        early_peak = max(
            early_peak,
            packet["CONSEQUENCE_TRANSPORT"]["322C001_TO_323E003"]["arrived_mass_kgh"],
        )
    assert early_peak == 0.0

    arrived_peak = 0.0
    inventory_peak = inventory_before
    arrived_diag = None
    # The small 3.9 -> 3.2 bar gas escape has an approximately 83 s live transit time through a
    # line sized for 33 t/h of liquid, so sample beyond that physical delay rather than assuming the
    # 8 s design-carrier anchor applies after the carrier collapses.
    for _ in range(1200):
        hold_absorber_empty(state)
        packet = main.step_sim(0.1)
        diag = packet["CONSEQUENCE_TRANSPORT"]["322C001_TO_323E003"]
        if diag["arrived_mass_kgh"] > arrived_peak:
            arrived_peak = diag["arrived_mass_kgh"]
            arrived_diag = diag
        inventory_peak = max(inventory_peak, state.r3232_d001_M)

    assert arrived_diag is not None
    assert arrived_peak > 0.0
    assert sum(arrived_diag["component_kgh"].values()) == pytest.approx(arrived_peak)
    assert arrived_diag["temperature_c"] > 0.0
    assert inventory_peak > inventory_before
