"""Focused tests for the neutral H2O/urea UNIQUAC boundary.

The numerical expectations below are literal, hand-evaluated values from the
Voskov-Voronin UNIQUAC equations and the currently approved water Antoine
exception.  They intentionally do not call a second implementation to build
their expected values.
"""

from __future__ import annotations

import importlib
import math

import pytest


def _thermo():
    """Import inside each test so the initial TDD run is a test failure."""

    return importlib.import_module("thermo_extended_uniquac")


def test_equal_moles_convert_from_literal_mass_fraction() -> None:
    thermo = _thermo()
    # 60.05526 g urea + 18.01528 g water is exactly one mole of each.
    w_urea = 60.05526 / (60.05526 + 18.01528)

    assert thermo.mole_fractions_from_urea_mass_fraction(w_urea) == pytest.approx(
        (0.5, 0.5), abs=1.0e-14
    )


def test_ln_gamma_matches_literal_binary_evaluation() -> None:
    thermo = _thermo()

    actual = thermo.ln_gamma(0.75, 0.25, 403.15)

    assert actual == pytest.approx(
        (-0.1376221922082906, -0.5586200625516576), abs=1.0e-12
    )


def test_water_ln_gamma_is_zero_at_pure_water_limit() -> None:
    thermo = _thermo()

    ln_gamma_water, _ = thermo.ln_gamma(1.0, 0.0, 403.15)

    assert ln_gamma_water == pytest.approx(0.0, abs=1.0e-14)


def test_urea_ln_gamma_is_zero_at_pure_urea_limit() -> None:
    thermo = _thermo()

    _, ln_gamma_urea = thermo.ln_gamma(0.0, 1.0, 403.15)

    assert ln_gamma_urea == pytest.approx(0.0, abs=1.0e-14)


def test_pure_water_activity_limit_is_one() -> None:
    thermo = _thermo()

    assert thermo.water_activity(0.0, 403.15) == 1.0


def test_pure_urea_water_activity_limit_is_zero() -> None:
    thermo = _thermo()

    assert thermo.water_activity(1.0, 403.15) == 0.0


def test_pure_water_exception_matches_literal_antoine_value() -> None:
    thermo = _thermo()

    assert thermo.water_psat_bara(373.15) == pytest.approx(
        1.0189297473505128, abs=1.0e-12
    )


def test_px_residual_matches_first_stage_design_evaluation() -> None:
    thermo = _thermo()

    residual = thermo.px_equilibrium_residual(0.9431, 403.15, 0.33)

    assert residual == pytest.approx(-0.09414494805149266, abs=1.0e-12)


def test_solver_matches_first_stage_design_root() -> None:
    thermo = _thermo()

    result = thermo.solve_urea_mass_fraction(403.15, 0.33)

    assert result == pytest.approx(0.9204110746605021, abs=2.0e-10)


def test_solver_closes_second_stage_design_residual() -> None:
    thermo = _thermo()

    result = thermo.solve_urea_mass_fraction(413.15, 0.131)

    assert abs(thermo.px_equilibrium_residual(result, 413.15, 0.131)) < 1.0e-10


def test_solved_urea_fraction_increases_with_temperature() -> None:
    thermo = _thermo()

    lower_temperature = thermo.solve_urea_mass_fraction(403.15, 0.20)
    higher_temperature = thermo.solve_urea_mass_fraction(413.15, 0.20)

    assert higher_temperature > lower_temperature


def test_solved_urea_fraction_decreases_with_pressure() -> None:
    thermo = _thermo()

    lower_pressure = thermo.solve_urea_mass_fraction(403.15, 0.20)
    higher_pressure = thermo.solve_urea_mass_fraction(403.15, 0.40)

    assert higher_pressure < lower_pressure


@pytest.mark.parametrize(
    ("x_water", "x_urea"),
    [
        pytest.param(-0.01, 1.01, id="negative-water"),
        pytest.param(1.01, -0.01, id="negative-urea"),
        pytest.param(0.60, 0.50, id="sum-above-one"),
        pytest.param(math.nan, math.nan, id="not-finite"),
    ],
)
def test_ln_gamma_rejects_invalid_composition(
    x_water: float, x_urea: float
) -> None:
    thermo = _thermo()

    with pytest.raises(ValueError, match="mole fractions"):
        thermo.ln_gamma(x_water, x_urea, 403.15)


@pytest.mark.parametrize(
    "w_urea",
    [
        pytest.param(-1.0e-9, id="below-zero"),
        pytest.param(1.0 + 1.0e-9, id="above-one"),
        pytest.param(math.inf, id="not-finite"),
    ],
)
def test_water_activity_rejects_invalid_mass_fraction(w_urea: float) -> None:
    thermo = _thermo()

    with pytest.raises(ValueError, match="urea mass fraction"):
        thermo.water_activity(w_urea, 403.15)


@pytest.mark.parametrize(
    "temperature_k",
    [
        pytest.param(372.15 - 1.0e-9, id="below-range"),
        pytest.param(473.15 + 1.0e-9, id="above-range"),
        pytest.param(math.nan, id="not-finite"),
    ],
)
def test_solver_rejects_unsupported_temperature(temperature_k: float) -> None:
    thermo = _thermo()

    with pytest.raises(ValueError, match="temperature"):
        thermo.solve_urea_mass_fraction(temperature_k, 0.20)


@pytest.mark.parametrize(
    "pressure_bara",
    [
        pytest.param(0.02 - 1.0e-9, id="below-range"),
        pytest.param(1.00 + 1.0e-9, id="above-range"),
        pytest.param(math.inf, id="not-finite"),
    ],
)
def test_solver_rejects_unsupported_pressure(pressure_bara: float) -> None:
    thermo = _thermo()

    with pytest.raises(ValueError, match="pressure"):
        thermo.solve_urea_mass_fraction(403.15, pressure_bara)


def test_unit_324_domain_is_explicitly_an_extrapolation() -> None:
    thermo = _thermo()

    assert thermo.validity_status(403.15, 0.33) == "DESIGN_ANCHORED_EXTRAPOLATION"


@pytest.mark.parametrize(
    ("temperature_k", "pressure_bara"),
    [
        pytest.param(403.37, 0.3274, id="stage-one-near-design"),
        pytest.param(412.81, 0.1342, id="stage-two-near-design"),
        pytest.param(398.29, 0.2507, id="intermediate"),
    ],
)
def test_fast_ots_solver_tracks_exact_uniquac_root(
    temperature_k: float, pressure_bara: float
) -> None:
    thermo = _thermo()

    exact = thermo.solve_urea_mass_fraction(temperature_k, pressure_bara)
    fast = thermo.solve_urea_mass_fraction_fast(temperature_k, pressure_bara)

    assert fast == pytest.approx(exact, abs=2.0e-7)


def test_fast_ots_solver_reuses_cached_cell_nodes() -> None:
    thermo = _thermo()
    thermo.fast_solver_cache_clear()

    thermo.solve_urea_mass_fraction_fast(403.371, 0.32741)
    first = thermo.fast_solver_cache_info()
    thermo.solve_urea_mass_fraction_fast(403.372, 0.32742)
    second = thermo.fast_solver_cache_info()

    assert first.misses == 4
    assert second.misses == first.misses
    assert second.hits >= first.hits + 4
