"""Behavioral tests for conservative downstream-consequence transport."""

from __future__ import annotations

import pytest

import consequence as cq


def test_packet_derives_total_and_fraction_from_components():
    """Catch totals or fractions being carried independently from species rates."""
    packet = cq.make_stream_packet(
        100.0,
        {"NH3": 25.0, "CO2": 75.0},
        temperature_c=80.0,
        cp_kj_kgk=2.2,
    )

    assert packet.mass_kgh == pytest.approx(100.0)
    assert packet.mass_fraction == pytest.approx({"NH3": 0.25, "CO2": 0.75})
    assert sum(packet.component_kgh.values()) == pytest.approx(packet.mass_kgh)


def test_packet_rejects_a_total_that_disagrees_with_components():
    """Catch a stream whose displayed flow cannot close its component balance."""
    with pytest.raises(ValueError, match="component mass flow"):
        cq.make_stream_packet(
            101.0,
            {"NH3": 25.0, "CO2": 75.0},
            temperature_c=80.0,
            cp_kj_kgk=2.2,
        )


def test_mixing_conserves_components_and_sensible_enthalpy():
    """Catch independently averaged temperature or composition."""
    cold = cq.make_stream_packet(100.0, {"H2O": 100.0}, 20.0, 4.0)
    hot = cq.make_stream_packet(100.0, {"H2O": 100.0}, 100.0, 4.0)

    mixed = cq.mix_stream_packets(cold, hot)

    assert mixed.component_kgh["H2O"] == pytest.approx(200.0)
    assert mixed.temperature_c == pytest.approx(60.0)
    assert mixed.sensible_kw == pytest.approx(cold.sensible_kw + hot.sensible_kw)


def test_equivalent_sources_have_identical_delayed_packets():
    """Catch source/scenario names leaking into downstream physical behavior."""
    route = cq.ConsequenceRoute("A", "B", 3600.0, 10.0, 120.0)
    packet = cq.make_stream_packet(
        20.0,
        {"NH3": 5.0, "CO2": 15.0},
        temperature_c=120.0,
        cp_kj_kgk=2.2,
    )
    listed_store, unlisted_store = {}, {}

    for _ in range(200):
        cq.transport_stream_packet(
            listed_store, "listed", cq.ZERO_PACKET, route, 3600.0, 0.1
        )
        cq.transport_stream_packet(
            unlisted_store, "unlisted", cq.ZERO_PACKET, route, 3600.0, 0.1
        )

    listed = cq.transport_stream_packet(
        listed_store, "listed", packet, route, 3600.0, 0.1
    )
    unlisted = cq.transport_stream_packet(
        unlisted_store, "unlisted", packet, route, 3600.0, 0.1
    )

    assert listed == unlisted == cq.ZERO_PACKET

    for _ in range(100):
        listed = cq.transport_stream_packet(
            listed_store, "listed", packet, route, 3600.0, 0.1
        )
        unlisted = cq.transport_stream_packet(
            unlisted_store, "unlisted", packet, route, 3600.0, 0.1
        )

    assert listed == unlisted == packet


def test_lower_carrier_flow_lengthens_dead_time():
    """Catch a fixed or wrongly signed transport-time relation."""
    route = cq.ConsequenceRoute("A", "B", 3600.0, 10.0, 120.0)

    assert route.dead_time_s(1800.0) == pytest.approx(20.0)
    assert route.dead_time_s(7200.0) == pytest.approx(5.0)


def test_whole_packet_arrives_after_dead_time_without_property_desynchronization():
    """Catch mass arriving on a different tick from temperature or composition."""
    route = cq.ConsequenceRoute("A", "B", 3600.0, 5.0, 120.0)
    packet = cq.make_stream_packet(
        40.0,
        {"NH3": 10.0, "CO2": 20.0, "H2O": 10.0},
        temperature_c=150.0,
        cp_kj_kgk=2.5,
    )
    store = {}
    for _ in range(100):
        cq.transport_stream_packet(store, "route", cq.ZERO_PACKET, route, 3600.0, 0.1)

    # The changed parcel enters at the end of the first event tick (t=10.1 s), so it leaves at
    # t=15.1 s. Fifty samples through t=15.0 remain the original parcel.
    for _ in range(50):
        arrived = cq.transport_stream_packet(store, "route", packet, route, 3600.0, 0.1)
        assert arrived == cq.ZERO_PACKET

    arrived = cq.transport_stream_packet(store, "route", packet, route, 3600.0, 0.1)
    assert arrived == packet
    assert arrived.temperature_c == pytest.approx(150.0)
    assert arrived.mass_fraction == pytest.approx(
        {"NH3": 0.25, "CO2": 0.50, "H2O": 0.25}
    )


def test_process_transport_seeds_the_live_packet_instead_of_an_empty_line():
    """Catch a fresh design simulation draining every process line at boot."""
    route = cq.ConsequenceRoute("A", "B", 3600.0, 5.0, 120.0)
    baseline = cq.make_stream_packet(100.0, {"H2O": 100.0}, 80.0, 4.0)

    arrived = cq.transport_process_packet({}, "route", baseline, route, 3600.0, 0.1)

    assert arrived == baseline


def test_process_step_arrives_as_one_packet_after_dead_time():
    """Catch normal flow, temperature, or composition travelling on separate clocks."""
    route = cq.ConsequenceRoute("A", "B", 3600.0, 5.0, 120.0)
    baseline = cq.make_stream_packet(100.0, {"H2O": 100.0}, 80.0, 4.0)
    changed = cq.make_stream_packet(
        120.0, {"H2O": 60.0, "Urea": 60.0}, 110.0, 3.0
    )
    store = {}
    for _ in range(100):
        assert cq.transport_process_packet(
            store, "route", baseline, route, 3600.0, 0.1
        ) == baseline

    for _ in range(50):
        arrived = cq.transport_process_packet(
            store, "route", changed, route, 3600.0, 0.1
        )
        assert arrived == baseline

    arrived = cq.transport_process_packet(
        store, "route", changed, route, 3600.0, 0.1
    )
    assert arrived == changed
    assert arrived.mass_fraction == pytest.approx({"H2O": 0.5, "Urea": 0.5})
    assert arrived.temperature_c == pytest.approx(110.0)
