"""Near-design LV-322501 gas-load coupling to 323C003 absolute pressure."""
from __future__ import annotations

import math


C003_Q301_DES_M3H = 5064.7
C003_Q305_DES_M3H = 7677.1
C003_QOTHER_DES_M3H = C003_Q305_DES_M3H - C003_Q301_DES_M3H
C003_P_DES_BARA = 4.1
E003_P_DES_BARA = 3.2
C003_GAS_LOAD_COEFF_M3H_PER_BAR = (
    C003_Q305_DES_M3H
    / math.sqrt(C003_P_DES_BARA ** 2 - E003_P_DES_BARA ** 2)
)


def c003_pressure_target_bara(
    lv_flow_ratio: float,
    overhead_flow_ratio: float,
    downstream_pressure_bara: float,
) -> float:
    """Return the reduced-order 323C003 target pressure in bar absolute.

    `lv_flow_ratio` drives PFD stream 301's prompt flash-gas contribution.
    `overhead_flow_ratio` preserves the remaining live stream-305/reboiler load.
    All volume anchors are equivalent loads at the stream-305 design state.
    """
    values = (lv_flow_ratio, overhead_flow_ratio, downstream_pressure_bara)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("pressure-coupling inputs must be finite")
    if lv_flow_ratio < 0.0 or overhead_flow_ratio < 0.0:
        raise ValueError("gas-load flow ratios must be nonnegative")
    if downstream_pressure_bara <= 0.0:
        raise ValueError("downstream absolute pressure must be positive")

    equivalent_gas_load_m3h = (
        C003_Q301_DES_M3H * lv_flow_ratio + 
        C003_QOTHER_DES_M3H * overhead_flow_ratio
    )
    return math.sqrt(
        downstream_pressure_bara ** 2
        + (equivalent_gas_load_m3h / C003_GAS_LOAD_COEFF_M3H_PER_BAR) ** 2
    )
