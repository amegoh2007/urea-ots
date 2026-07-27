"""Regression gates for the approved 328D003 three-compartment arrangement."""

import math
from pathlib import Path

import pytest

import main


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_approved_compartment_capacities_replace_theoretical_split():
    assert main.A328_D003_VOL_I_M3 == 18.0
    assert main.A328_D003_VOL_II_M3 == 43.0
    assert main.A328_D003_VOL_III_M3 == 429.0
    assert main.A328_D003_VOL_TOTAL_M3 == 490.0
    assert math.isclose(
        main.A328_D003_MI_FULL
        + main.A328_D003_MII_FULL
        + main.A328_D003_MIII_FULL,
        main.A328_D003_VOL_TOTAL_M3 * main.A328_D003_RHO_KGM3,
    )


@pytest.mark.parametrize(
    "masses,temperatures",
    [
        ((9_000.0, 21_500.0, 214_500.0), (44.0, 56.0, 52.0)),
        ((17_000.0, 10_000.0, 300_000.0), (39.0, 71.0, 48.0)),
        ((1_000.0, 40_000.0, 80_000.0), (90.0, 35.0, 61.0)),
        ((5_000.0, 5_000.0, 450_000.0), (20.0, 80.0, 50.0)),
    ],
)
def test_communicating_baffle_conserves_mass_energy_and_equalizes_head(
    masses, temperatures,
):
    full_masses = (18_000.0, 43_000.0, 429_000.0)
    new_masses, new_temperatures = main.redistribute_communicating_compartments(
        masses, temperatures, full_masses,
    )

    assert math.isclose(sum(new_masses), sum(masses), abs_tol=1e-8)
    assert math.isclose(
        sum(m * t for m, t in zip(new_masses, new_temperatures)),
        sum(m * t for m, t in zip(masses, temperatures)),
        abs_tol=1e-6,
    )
    levels = [mass / full for mass, full in zip(new_masses, full_masses)]
    assert max(levels) - min(levels) <= 1e-12
    assert all(math.isfinite(value) for value in new_temperatures)


def test_compartment_three_absorbs_most_of_a_compartment_one_disturbance():
    full_masses = (18_000.0, 43_000.0, 429_000.0)
    baseline = tuple(0.5 * full for full in full_masses)
    disturbed = (baseline[0] + 1_000.0, baseline[1], baseline[2])

    new_masses, _ = main.redistribute_communicating_compartments(
        disturbed, (44.0, 56.0, 52.0), full_masses,
    )

    increments = tuple(new - old for new, old in zip(new_masses, baseline))
    assert math.isclose(sum(increments), 1_000.0, abs_tol=1e-8)
    assert math.isclose(increments[2], 1_000.0 * 429.0 / 490.0, abs_tol=1e-8)
    assert increments[2] > increments[0] + increments[1]


def test_equal_temperature_is_unchanged_by_internal_redistribution():
    new_masses, new_temperatures = main.redistribute_communicating_compartments(
        (2_000.0, 30_000.0, 300_000.0),
        (55.0, 55.0, 55.0),
        (18_000.0, 43_000.0, 429_000.0),
    )

    assert math.isclose(sum(new_masses), 332_000.0, abs_tol=1e-8)
    assert new_temperatures == pytest.approx((55.0, 55.0, 55.0))


def test_nearly_empty_buffer_mixes_donors_before_supplying_receivers():
    _, new_temperatures = main.redistribute_communicating_compartments(
        (100_000.0, 0.0, 1.0),
        (0.0, 100.0, 100.0),
        (18_000.0, 43_000.0, 429_000.0),
    )

    assert min(new_temperatures) >= 0.0
    assert max(new_temperatures) <= 100.0


def test_state_and_packet_expose_all_three_physical_compartments():
    main.state = main.State()
    assert main.state.a328_d003_MI == 0.5 * main.A328_D003_MI_FULL
    assert main.state.a328_d003_MII == 0.5 * main.A328_D003_MII_FULL
    assert main.state.a328_d003_MIII == 0.5 * main.A328_D003_MIII_FULL

    packet = main.step_sim(0.1)
    d003 = packet["ABSORB_328"]["D003"]

    assert d003["capacities_m3"] == {"I": 18.0, "II": 43.0, "III": 429.0}
    assert d003["LI_328I"] == 50.0
    assert d003["LI_328II"] == 50.0
    assert d003["LI_328III"] == 50.0
    assert d003["LT_328507_open_loop"] == d003["LI_328I"]
    assert d003["LT_328508_open_loop"] == d003["LI_328II"]
    assert d003["form735_th"] == 31.11
    assert d003["collect755_th"] == 31.48


def test_stream_741_recycle_returns_to_physical_compartment_two():
    main.state = main.State()
    main.state.FIC_328406["mode"] = "MAN"
    main.state.FIC_328406["op"] = 100.0

    main.step_sim(10.0)

    # Stream 741 is 40 C: it cools compartment II directly. Compartment I only receives the small
    # communicated surge from the warmer shared buffer, so it must not show direct-feed cooling.
    assert main.state.a328_d003_TII < main.A328_D003_TII
    assert main.state.a328_d003_TI > main.A328_D003_TI


def test_open_loop_level_tags_follow_the_approved_compartment_assignments():
    state = main.State()
    state.a328_d003_MI = 0.30 * main.A328_D003_MI_FULL
    state.a328_d003_MII = 0.40 * main.A328_D003_MII_FULL
    state.a328_d003_MIII = 0.60 * main.A328_D003_MIII_FULL

    levels = main.d003_level_telemetry(state)

    assert levels["LI_328I"] == 30.0
    assert levels["LI_328II"] == 40.0
    assert levels["LI_328III"] == 60.0
    assert levels["LT_328507_open_loop"] == 30.0
    assert levels["LT_328508_open_loop"] == 40.0


def test_level_overlays_bind_to_the_approved_open_loop_tags():
    overlay = (PROJECT_ROOT / "frontend" / "overlays.js").read_text(encoding="utf-8")
    lt_328508 = next(line for line in overlay.splitlines() if "k: 'lt8508'" in line)
    lt_328507_lines = [line for line in overlay.splitlines() if "tag: 'LT-328507'" in line]

    assert "bind: 'ABSORB_328.D003.LT_328508_open_loop'," in lt_328508
    assert "LI_328III" not in lt_328508
    assert lt_328508.rstrip().endswith("// compartment II")
    assert len(lt_328507_lines) == 2
    assert all(
        "bind: 'ABSORB_328.D003.LT_328507_open_loop'" in line
        for line in lt_328507_lines
    )
