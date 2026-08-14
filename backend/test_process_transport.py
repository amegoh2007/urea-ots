"""Normal-process packet transport and downstream-ripple tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import main


PRODUCT_ROUTES = (
    "322E001_TO_323C003",
    "323C003_TO_323F004",
    "323F004_TO_323F010",
    "323F010_TO_323D002",
    "323D002_TO_324E001",
)


@pytest.mark.parametrize("route_name", PRODUCT_ROUTES)
def test_every_principal_product_connection_has_process_transport(route_name):
    """Catch a vessel boundary reverting to same-tick property teleportation."""
    assert route_name in main.PROCESS_ROUTES


def test_route_delays_fit_the_independent_hourly_trend_bound():
    """The supplied 30 s rows are interpolated; only a <3600 s bound is supported."""
    for route in main.PROCESS_ROUTES.values():
        assert 0.0 < route.design_dead_time_s < 3600.0
        assert route.line_inventory_kg > 0.0


def test_322e001_feed_step_reaches_c003_only_after_packet_dead_time():
    """Catch the source and receiver consuming the same changed parcel on the same tick."""
    state = SimpleNamespace(tlag={})
    route = main.PROCESS_ROUTES["322E001_TO_323C003"]
    baseline = main._cq_packet(
        route.design_carrier_kgh, 119.0, {"Urea": 0.56, "H2O": 0.44}, 2.5
    )
    changed = main._cq_packet(
        route.design_carrier_kgh * 1.2, 125.0, {"Urea": 0.60, "H2O": 0.40}, 2.6
    )
    arrived = main._transport_process(
        state, "322E001_TO_323C003", baseline, baseline.mass_kgh, 1.0
    )
    receiver_inventory = 10_000.0
    assert arrived == baseline

    for _ in range(5):
        arrived = main._transport_process(
            state, "322E001_TO_323C003", changed, changed.mass_kgh, 1.0
        )
        receiver_inventory += (arrived.mass_kgh - baseline.mass_kgh) / 3600.0
    early_diag = state.tlag["PROCESS_DIAGNOSTICS"]["322E001_TO_323C003"]
    assert early_diag["departure_mass_kgh"] == pytest.approx(changed.mass_kgh)
    assert early_diag["arrived_mass_kgh"] == pytest.approx(baseline.mass_kgh)
    assert receiver_inventory == pytest.approx(10_000.0)

    for _ in range(20):
        arrived = main._transport_process(
            state, "322E001_TO_323C003", changed, changed.mass_kgh, 1.0
        )
        receiver_inventory += (arrived.mass_kgh - baseline.mass_kgh) / 3600.0
    late_diag = state.tlag["PROCESS_DIAGNOSTICS"]["322E001_TO_323C003"]
    assert late_diag["arrived_mass_kgh"] == pytest.approx(changed.mass_kgh)
    assert receiver_inventory > 10_000.0
    assert sum(late_diag["mass_fraction"].values()) == pytest.approx(1.0)
