"""Near-design LV-322501 gas-load coupling to 323C003 absolute pressure."""
from __future__ import annotations

import math


C003_Q301_DES_M3H = 5064.7
C003_Q305_DES_M3H = 7677.1
C003_QOTHER_DES_M3H = C003_Q305_DES_M3H - C003_Q301_DES_M3H
C003_P_DES_BARA = 4.1
E003_P_DES_BARA = 3.2
# 2025-06-28 startup trend residual: 0.100 bar per LV opening point.
# LV flow ratio is normalized at the field-calibrated 46.1% design opening.
C003_LV_FIELD_GAIN_BARA_PER_RATIO = 4.61
C003_TO_E003_LINK_TAU_S = 1.0
C003_GAS_LOAD_COEFF_M3H_PER_BAR = (
    C003_Q305_DES_M3H
    / math.sqrt(C003_P_DES_BARA ** 2 - E003_P_DES_BARA ** 2)
)
E011_GAS_FEED_DES_KGH = 6029.0
E011_CONDENSATION_CAPACITY_DES_KGH = 5589.0

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
        C003_Q301_DES_M3H * lv_flow_ratio
        + C003_QOTHER_DES_M3H * overhead_flow_ratio
    )
    hydraulic_target_bara = math.sqrt(
        downstream_pressure_bara ** 2
        + (equivalent_gas_load_m3h / C003_GAS_LOAD_COEFF_M3H_PER_BAR) ** 2
    )
    field_residual_bara = C003_LV_FIELD_GAIN_BARA_PER_RATIO * (lv_flow_ratio - 1.0)
    return max(downstream_pressure_bara, hydraulic_target_bara + field_residual_bara)


def e011_vent_generation_kgh(gas_inlet_kgh: float) -> float:
    if not math.isfinite(gas_inlet_kgh):
        raise ValueError("E011 gas inlet must be finite")
    if gas_inlet_kgh < 0.0:
        raise ValueError("E011 gas inlet must be nonnegative")
    return max(gas_inlet_kgh - E011_CONDENSATION_CAPACITY_DES_KGH, 0.0)


def lpcc_pressure_target_bara(lv_flow_ratio: float) -> float:
    """Return the field-retuned PIC-323202 pressure target in bar absolute.

    With no let-down valve between 323C003 and 323E003/D001, the startup-trend
    residual belongs to the common downstream pressure node.  The upstream
    PT-323201 hydraulic calculation then adds the live condenser pressure drop.
    """
    if not math.isfinite(lv_flow_ratio):
        raise ValueError("LV-322501 flow ratio must be finite")
    if lv_flow_ratio < 0.0:
        raise ValueError("LV-322501 flow ratio must be nonnegative")
    return max(
        E003_P_DES_BARA
        + C003_LV_FIELD_GAIN_BARA_PER_RATIO * (lv_flow_ratio - 1.0),
        0.1,
    )
