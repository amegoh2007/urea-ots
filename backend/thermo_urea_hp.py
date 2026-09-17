"""High-pressure urea-synthesis equilibrium surrogate.

The correlation is transcribed from the supplementary implementation for
Voskov and Voronin, *J. Chem. Eng. Data* 61 (2016) 4110-4125.  It covers the
industrial urea-synthesis domain (135-230 deg C, N/C 2-5.5, H/C -0.75-1.2).
The OTS normalizes it to the verified plant design conversion so the static
heat and material balance remains the design fixed point.
"""

from __future__ import annotations

import math
from typing import Mapping

NC_DES = 3.072961
HC_DES = 0.407828
T_DES_C = 183.0
X_DES = 0.543

NC_RANGE = (2.0, 5.5)
HC_RANGE = (-0.75, 1.2)
T_RANGE_C = (135.0, 230.0)


def _clamp(value: float, limits: tuple[float, float]) -> float:
    return min(max(float(value), limits[0]), limits[1])


def synthesis_ratios(comp_kmolh: Mapping[str, float]) -> tuple[float, float]:
    """Return conserved N/C and H/C synthesis ratios from molecular components.

    Urea and biuret remain part of the original synthesis-feed equivalents.
    This avoids changing the reported ratios merely because reaction proceeds.
    """
    co2 = max(float(comp_kmolh.get("CO2", 0.0)), 0.0)
    nh3 = max(float(comp_kmolh.get("NH3", 0.0)), 0.0)
    h2o = max(float(comp_kmolh.get("H2O", 0.0)), 0.0)
    urea = max(float(comp_kmolh.get("Urea", 0.0)), 0.0)
    biuret = max(float(comp_kmolh.get("Biuret", 0.0)), 0.0)
    carbon = co2 + urea + 2.0 * biuret
    if carbon <= 0.0:
        return NC_DES, HC_DES
    nitrogen = nh3 + 2.0 * urea + 3.0 * biuret
    water_equiv = h2o - urea - 2.0 * biuret
    return nitrogen / carbon, water_equiv / carbon


def equilibrium_conversion(nc: float, hc: float, t_c: float) -> float:
    """Return absolute equilibrium CO2-to-urea conversion as a fraction.

    Inputs outside the published fit domain are evaluated at the nearest
    boundary.  Call :func:`outside_validity` when a diagnostic is required.
    """
    nc_fit = _clamp(nc, NC_RANGE)
    hc_fit = _clamp(hc, HC_RANGE)
    t_k = _clamp(t_c, T_RANGE_C) + 273.15
    temperature_term = -121.1458 - 5.1135e-5 * t_k**2 + 21.6826 * math.log(t_k)
    exponent = (
        -2.1908 * nc_fit**-2 * hc_fit
        - 4.1059e-3 * nc_fit**2 * hc_fit
        - 2.8380 * nc_fit**-2
    )
    return _clamp(temperature_term * math.exp(exponent), (0.0, 1.0))


_X_CORR_DES = equilibrium_conversion(NC_DES, HC_DES, T_DES_C)


def conversion_factor(nc: float, hc: float, t_c: float = T_DES_C) -> float:
    """Return the equilibrium conversion relative to the plant design point."""
    return equilibrium_conversion(nc, hc, t_c) / _X_CORR_DES


def plant_anchored_conversion(nc: float, hc: float, t_c: float = T_DES_C) -> float:
    """Return equilibrium conversion normalized to the PFD's 0.543 design value."""
    return _clamp(X_DES * conversion_factor(nc, hc, t_c), (0.0, 1.0))


def outside_validity(nc: float, hc: float, t_c: float) -> bool:
    """Report whether any input lies outside the published correlation domain."""
    return not (
        NC_RANGE[0] <= nc <= NC_RANGE[1]
        and HC_RANGE[0] <= hc <= HC_RANGE[1]
        and T_RANGE_C[0] <= t_c <= T_RANGE_C[1]
    )
