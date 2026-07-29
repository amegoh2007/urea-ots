"""Neutral H2O/urea UNIQUAC thermodynamic boundary for Unit 324.

Model and provenance
--------------------
Urea and water are neutral species, so the Debye-Huckel term of Extended
UNIQUAC is identically zero and the liquid activity model reduces to ordinary
UNIQUAC.  The equations, structural parameters, and interaction convention
are transcribed from the open supplementary implementation accompanying
Voskov A. L. and Voronin G. F., *Thermodynamic model of the urea synthesis
process*, DOI 10.1021/acs.jced.6b00557 (files ``GRT_UNIQUAC.m``,
``liquid_hc.m``, and ``liquid6comp.cpp``).

The supplementary source is X11/MIT licensed.  Copyright (c) 2008-2016
Alexey L. Voskov and Gennady F. Voronin.  The binary parameter set used here
is H2O->urea ``(a0, a1) = (0, 0)`` and urea->H2O
``(-211.9567785927018 K, 0)``.

Range and deliberate exception
------------------------------
This first integration is guarded to a bounded OTS operating envelope:
372.15-473.15 K and 0.02-1.00 bar absolute. These are application bounds,
not a claim that the source fitted vacuum pressure. The published full-model
validation envelope is 408.15-503.15 K and 35-450 bar absolute, so Unit 324
is explicitly classified as a design-anchored extrapolation. Water fugacity is
temporarily represented by the simulator's existing pure-water Antoine
correlation.  That is an explicit ``PURE_WATER_STEAM`` exception, not an
Extended-UNIQUAC property.  No electrolyte speciation, gas EOS, Poynting
correction, or absolute enthalpy is provided by this module.

All compositions are true fractions, not percentages.  Public temperature
arguments are kelvin and pressure arguments are bar absolute.
"""

from __future__ import annotations

import math
from functools import lru_cache


MODEL_NAME = "Extended UNIQUAC neutral H2O/urea limit (Voskov-Voronin)"
VALID_TEMPERATURE_K = (372.15, 473.15)
VALID_PRESSURE_BARA = (0.02, 1.00)
SOURCE_VALID_TEMPERATURE_K = (408.15, 503.15)
SOURCE_VALID_PRESSURE_BARA = (35.0, 450.0)

MOLAR_MASS_WATER_G_MOL = 18.01528
MOLAR_MASS_UREA_G_MOL = 60.05526

_R = (0.92, 2.1408)  # H2O, urea
_Q = (1.40, 2.4860)  # H2O, urea
_A0 = (
    (0.0, 0.0),
    (-211.9567785927018, 0.0),
)
_A1 = (
    (0.0, 0.0),
    (0.0, 0.0),
)
_COORDINATION_NUMBER = 10.0


class UnsupportedThermodynamicDomain(ValueError):
    """Raised when a call lies outside this initial model's stated range."""


def validity_status(temperature_k: float, pressure_bara: float) -> str:
    """Return ``VALIDATED`` or ``DESIGN_ANCHORED_EXTRAPOLATION``.

    The Unit-324 vacuum application is outside the publication's full-model
    validation-pressure range. Keeping that status machine-readable prevents
    a numerically converged activity solve from being mistaken for validation.
    """

    _validate_temperature(temperature_k)
    _validate_pressure(pressure_bara)
    t_low, t_high = SOURCE_VALID_TEMPERATURE_K
    p_low, p_high = SOURCE_VALID_PRESSURE_BARA
    if t_low <= temperature_k <= t_high and p_low <= pressure_bara <= p_high:
        return "VALIDATED"
    return "DESIGN_ANCHORED_EXTRAPOLATION"


def _validate_temperature(temperature_k: float) -> None:
    low, high = VALID_TEMPERATURE_K
    if not math.isfinite(temperature_k) or not low <= temperature_k <= high:
        raise UnsupportedThermodynamicDomain(
            f"temperature must be finite and within {low}-{high} K"
        )


def _validate_pressure(pressure_bara: float) -> None:
    low, high = VALID_PRESSURE_BARA
    if not math.isfinite(pressure_bara) or not low <= pressure_bara <= high:
        raise UnsupportedThermodynamicDomain(
            f"pressure must be finite and within {low}-{high} bar(a)"
        )


def _validate_urea_mass_fraction(urea_mass_fraction: float) -> None:
    if (
        not math.isfinite(urea_mass_fraction)
        or not 0.0 <= urea_mass_fraction <= 1.0
    ):
        raise ValueError("urea mass fraction must be finite and within [0, 1]")


def mole_fractions_from_urea_mass_fraction(
    urea_mass_fraction: float,
) -> tuple[float, float]:
    """Return ``(x_water, x_urea)`` from a binary urea mass fraction."""

    _validate_urea_mass_fraction(urea_mass_fraction)
    moles_water = (1.0 - urea_mass_fraction) / MOLAR_MASS_WATER_G_MOL
    moles_urea = urea_mass_fraction / MOLAR_MASS_UREA_G_MOL
    total_moles = moles_water + moles_urea
    return moles_water / total_moles, moles_urea / total_moles


def ln_gamma(
    x_water: float,
    x_urea: float,
    temperature_k: float,
) -> tuple[float, float]:
    """Return ``(ln(gamma_water), ln(gamma_urea))`` from binary UNIQUAC.

    The interaction matrix is ordered by source species (row) and destination
    species (column), matching ``a_ij`` and ``tau_ij`` in the Voskov source.
    Exact zero mole fractions are accepted so pure-component limits can be
    evaluated without arbitrary composition clipping.
    """

    _validate_temperature(temperature_k)
    if (
        not math.isfinite(x_water)
        or not math.isfinite(x_urea)
        or x_water < 0.0
        or x_urea < 0.0
        or not math.isclose(x_water + x_urea, 1.0, rel_tol=0.0, abs_tol=1.0e-12)
    ):
        raise ValueError(
            "mole fractions must be finite, nonnegative, and sum to one"
        )

    total = x_water + x_urea
    x = (x_water / total, x_urea / total)
    r_sum = sum(x_i * r_i for x_i, r_i in zip(x, _R))
    q_sum = sum(x_i * q_i for x_i, q_i in zip(x, _Q))
    theta = tuple(x[i] * _Q[i] / q_sum for i in range(2))

    z = _COORDINATION_NUMBER
    ell = tuple(z / 2.0 * (_R[i] - _Q[i]) - (_R[i] - 1.0) for i in range(2))
    sum_x_ell = sum(x[i] * ell[i] for i in range(2))
    tau = tuple(
        tuple(
            math.exp(-_A0[i][j] / temperature_k - _A1[i][j])
            for j in range(2)
        )
        for i in range(2)
    )
    theta_tau = tuple(
        sum(theta[j] * tau[j][i] for j in range(2)) for i in range(2)
    )

    result = []
    for i in range(2):
        phi_over_x = _R[i] / r_sum
        theta_over_phi = (_Q[i] / q_sum) / phi_over_x
        combinatorial = (
            math.log(phi_over_x)
            + z / 2.0 * _Q[i] * math.log(theta_over_phi)
            + ell[i]
            - phi_over_x * sum_x_ell
        )
        residual = _Q[i] * (
            1.0
            - math.log(theta_tau[i])
            - sum(theta[j] * tau[i][j] / theta_tau[j] for j in range(2))
        )
        result.append(combinatorial + residual)
    return result[0], result[1]


def water_activity(urea_mass_fraction: float, temperature_k: float) -> float:
    """Return liquid water activity ``a_w = x_w * gamma_w``."""

    _validate_temperature(temperature_k)
    _validate_urea_mass_fraction(urea_mass_fraction)
    if urea_mass_fraction == 0.0:
        return 1.0
    if urea_mass_fraction == 1.0:
        return 0.0
    x_water, x_urea = mole_fractions_from_urea_mass_fraction(
        urea_mass_fraction
    )
    ln_gamma_water, _ = ln_gamma(x_water, x_urea, temperature_k)
    return x_water * math.exp(ln_gamma_water)


def water_psat_bara(temperature_k: float) -> float:
    """Return pure-water saturation pressure [bar(a)] via Antoine.

    This is intentionally the current simulator correlation, isolated here as
    a pure-water exception until an IAPWS boundary replaces it.
    """

    _validate_temperature(temperature_k)
    temperature_c = temperature_k - 273.15
    pressure_mmhg = 10.0 ** (
        8.14019 - 1810.94 / (244.485 + temperature_c)
    )
    return pressure_mmhg / 750.0616827


def px_equilibrium_residual(
    urea_mass_fraction: float,
    temperature_k: float,
    pressure_bara: float,
) -> float:
    """Return the pure-water-vapour P-x residual [bar].

    The residual is ``a_water * Psat_water - P``; zero therefore denotes a
    liquid in equilibrium with a vapour whose pressure is attributed to water.
    """

    _validate_temperature(temperature_k)
    _validate_pressure(pressure_bara)
    _validate_urea_mass_fraction(urea_mass_fraction)
    return (
        water_activity(urea_mass_fraction, temperature_k)
        * water_psat_bara(temperature_k)
        - pressure_bara
    )


@lru_cache(maxsize=16384)
def solve_urea_mass_fraction(
    temperature_k: float,
    pressure_bara: float,
    *,
    mass_fraction_tolerance: float = 1.0e-12,
    pressure_tolerance_bara: float = 1.0e-12,
    max_iterations: int = 100,
) -> float:
    """Solve the binary P-x residual by safeguarded Newton iteration.

    Pure water and pure urea provide a guaranteed physical bracket throughout
    the applicable part of the guarded Unit-324 range. A numerical Newton step
    is accepted only inside that bracket; otherwise the method bisects. This
    keeps deterministic bounds while avoiding dozens of bisections per OTS tick.
    """

    _validate_temperature(temperature_k)
    _validate_pressure(pressure_bara)
    if (
        not math.isfinite(mass_fraction_tolerance)
        or mass_fraction_tolerance <= 0.0
    ):
        raise ValueError("mass fraction tolerance must be finite and positive")
    if (
        not math.isfinite(pressure_tolerance_bara)
        or pressure_tolerance_bara <= 0.0
    ):
        raise ValueError("pressure tolerance must be finite and positive")
    if not isinstance(max_iterations, int) or max_iterations <= 0:
        raise ValueError("max iterations must be a positive integer")

    low = 0.0
    high = 1.0
    residual_low = px_equilibrium_residual(
        low, temperature_k, pressure_bara
    )
    residual_high = px_equilibrium_residual(
        high, temperature_k, pressure_bara
    )
    if abs(residual_low) <= pressure_tolerance_bara:
        return low
    if abs(residual_high) <= pressure_tolerance_bara:
        return high
    if residual_low * residual_high > 0.0:
        raise UnsupportedThermodynamicDomain(
            "water-vapour equilibrium has no root within urea mass fraction [0, 1]"
        )

    # Ideal-water-activity inversion is a close first estimate; activity
    # coefficients then supply the non-ideal correction.
    x_water_ideal = min(
        max(pressure_bara / water_psat_bara(temperature_k), 0.0), 1.0
    )
    denominator = (
        (1.0 - x_water_ideal) * MOLAR_MASS_UREA_G_MOL
        + x_water_ideal * MOLAR_MASS_WATER_G_MOL
    )
    estimate = (
        (1.0 - x_water_ideal) * MOLAR_MASS_UREA_G_MOL / denominator
        if denominator > 0.0 else 0.5
    )
    estimate = min(max(estimate, low), high)

    for _ in range(max_iterations):
        residual_estimate = px_equilibrium_residual(
            estimate, temperature_k, pressure_bara
        )
        if abs(residual_estimate) <= pressure_tolerance_bara:
            return estimate

        if residual_low * residual_estimate > 0.0:
            low = estimate
            residual_low = residual_estimate
        else:
            high = estimate
            residual_high = residual_estimate
        if high - low <= mass_fraction_tolerance:
            return (low + high) / 2.0

        derivative_step = min(1.0e-4, 0.25 * (high - low))
        left = max(low, estimate - derivative_step)
        right = min(high, estimate + derivative_step)
        derivative = None
        if right > left:
            derivative = (
                px_equilibrium_residual(right, temperature_k, pressure_bara)
                - px_equilibrium_residual(left, temperature_k, pressure_bara)
            ) / (right - left)
        newton = (
            estimate - residual_estimate / derivative
            if derivative is not None and derivative < 0.0 else math.nan
        )
        estimate = newton if low < newton < high else (low + high) / 2.0

    raise RuntimeError(
        "urea-water P-x solve did not converge within "
        f"{max_iterations} iterations; final bracket residuals "
        f"{residual_low:.6g}, {residual_high:.6g} bar"
    )


_FAST_T_STEP_K = 0.05
_FAST_P_STEP_BARA = 0.00025


@lru_cache(maxsize=32768)
def _fast_grid_node(temperature_index: int, pressure_index: int) -> float:
    temperature_k = (
        VALID_TEMPERATURE_K[0] + temperature_index * _FAST_T_STEP_K
    )
    pressure_bara = (
        VALID_PRESSURE_BARA[0] + pressure_index * _FAST_P_STEP_BARA
    )
    return solve_urea_mass_fraction(temperature_k, pressure_bara)


def solve_urea_mass_fraction_fast(
    temperature_k: float, pressure_bara: float
) -> float:
    """Return a cached local bilinear interpolation of the exact UNIQUAC root.

    The 0.05 K by 0.00025 bar cells are populated lazily from the exact solver.
    A dynamic trajectory therefore solves only four nodes when it enters a new
    cell, while repeated Picard iterations use cached values. If a cell corner
    has no boiling root, the exact query is used so phase-domain errors remain
    explicit rather than being interpolated through.
    """

    _validate_temperature(temperature_k)
    _validate_pressure(pressure_bara)
    t_low, t_high = VALID_TEMPERATURE_K
    p_low, p_high = VALID_PRESSURE_BARA
    t_index = int(math.floor((temperature_k - t_low) / _FAST_T_STEP_K))
    p_index = int(math.floor((pressure_bara - p_low) / _FAST_P_STEP_BARA))
    if temperature_k >= t_high:
        t_index -= 1
    if pressure_bara >= p_high:
        p_index -= 1
    t_index = max(t_index, 0)
    p_index = max(p_index, 0)
    t0 = t_low + t_index * _FAST_T_STEP_K
    p0 = p_low + p_index * _FAST_P_STEP_BARA
    ft = min(max((temperature_k - t0) / _FAST_T_STEP_K, 0.0), 1.0)
    fp = min(max((pressure_bara - p0) / _FAST_P_STEP_BARA, 0.0), 1.0)
    try:
        w00 = _fast_grid_node(t_index, p_index)
        w10 = _fast_grid_node(t_index + 1, p_index)
        w01 = _fast_grid_node(t_index, p_index + 1)
        w11 = _fast_grid_node(t_index + 1, p_index + 1)
    except UnsupportedThermodynamicDomain:
        return solve_urea_mass_fraction(temperature_k, pressure_bara)
    w0 = w00 + ft * (w10 - w00)
    w1 = w01 + ft * (w11 - w01)
    return w0 + fp * (w1 - w0)


def fast_solver_cache_clear() -> None:
    _fast_grid_node.cache_clear()


def fast_solver_cache_info():
    return _fast_grid_node.cache_info()


__all__ = [
    "MODEL_NAME",
    "VALID_PRESSURE_BARA",
    "VALID_TEMPERATURE_K",
    "SOURCE_VALID_PRESSURE_BARA",
    "SOURCE_VALID_TEMPERATURE_K",
    "UnsupportedThermodynamicDomain",
    "ln_gamma",
    "mole_fractions_from_urea_mass_fraction",
    "px_equilibrium_residual",
    "fast_solver_cache_clear",
    "fast_solver_cache_info",
    "solve_urea_mass_fraction",
    "solve_urea_mass_fraction_fast",
    "validity_status",
    "water_activity",
    "water_psat_bara",
]
