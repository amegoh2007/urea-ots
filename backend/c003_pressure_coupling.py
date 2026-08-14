"""Near-design 323C003 pressure model: two separate gas-load paths.

LV-322501 letdown flash gas (stream 301) and 323E002 reboiler vapour are the
two independent sources that charge the 323C003 overhead.  Keeping them
separated means:

  * opening LV-322501 → more flash gas → higher column pressure, *and*
  * more reboiler duty on 323E002 → more pool-boil vapour → higher column pressure

as two independent, physically distinct coupling chains.

Design identities (all at 100 % / PFD / R323_C003_P_BARA = 4.1 bar a):
  flash_gas_ratio = 1.0  →  stream-301 contribution = C003_Q301_DES_M3H
  e002_vap_ratio  = 1.0  →  reboiler contribution   = C003_QOTHER_DES_M3H
  downstream      = E003_P_DES_BARA = 3.2 bar a
  → p_target = sqrt(3.2² + ((5064.7 + 2612.4)/C_gas)²) + field_residual ≡ 4.1
"""
from __future__ import annotations

import math


C003_Q301_DES_M3H = 5064.7          # m³/h  LV-322501 letdown flash gas, stream 301
C003_Q305_DES_M3H = 7677.1          # m³/h  total 323C003 overhead, stream 305
C003_QOTHER_DES_M3H = C003_Q305_DES_M3H - C003_Q301_DES_M3H   # = 2612.4  (reboiler only)
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

# Design fractions of the total overhead that belong to each source.
# Used by main.py to normalise m_flash_gas and m_pool_vap before calling
# c003_pressure_target_bara.  At design both ratios == 1.0 so the call is
# bit-identical to the old (lv_flow_ratio=1.0, overhead_flow_ratio=1.0) form.
C003_FLASH_GAS_FRAC = C003_Q301_DES_M3H / C003_Q305_DES_M3H     # 0.65974
C003_POOL_VAP_FRAC  = C003_QOTHER_DES_M3H / C003_Q305_DES_M3H   # 0.34026


def c003_pressure_target_bara(
    flash_gas_ratio: float,
    e002_vap_ratio: float,
    downstream_pressure_bara: float,
) -> float:
    """Return the reduced-order 323C003 target pressure in bar absolute.

    ``flash_gas_ratio``
        Live flash-gas rate (stream 301, from LV-322501 letdown) normalised by
        its design value.  Drives the C003_Q301_DES_M3H term directly.

    ``e002_vap_ratio``
        Live 323E002 pool-boil vapour rate normalised by its design value.
        Drives the C003_QOTHER_DES_M3H term directly.

    ``downstream_pressure_bara``
        Absolute pressure of the receiving node (323E003 / 323D001) in bar.

    At design (both ratios = 1.0, downstream = 3.2 bar a) the function returns
    exactly 4.1 bar a — the PFD anchor.

    The field-gain residual term tracks the startup-trend LV-322501 sensitivity
    (0.100 bar per % LV opening, i.e. C003_LV_FIELD_GAIN_BARA_PER_RATIO per
    unit ratio).  It is driven by the flash-gas ratio because that ratio is
    proportional to the LV-322501 opening at constant upstream/downstream
    conditions.
    """
    values = (flash_gas_ratio, e002_vap_ratio, downstream_pressure_bara)
    if not all(math.isfinite(v) for v in values):
        raise ValueError("pressure-coupling inputs must be finite")
    if flash_gas_ratio < 0.0 or e002_vap_ratio < 0.0:
        raise ValueError("gas-load flow ratios must be nonneg")
    if downstream_pressure_bara <= 0.0:
        raise ValueError("downstream absolute pressure must be positive")

    equivalent_gas_load_m3h = (
        C003_Q301_DES_M3H * flash_gas_ratio      # LV-322501 letdown flash gas
        + C003_QOTHER_DES_M3H * e002_vap_ratio   # 323E002 reboiler pool-boil vapour
    )
    hydraulic_target_bara = math.sqrt(
        downstream_pressure_bara ** 2
        + (equivalent_gas_load_m3h / C003_GAS_LOAD_COEFF_M3H_PER_BAR) ** 2
    )
    # Field-gain residual: keyed on flash_gas_ratio because flash-gas scales
    # with LV-322501 opening, which is the measured startup-trend variable.
    field_residual_bara = C003_LV_FIELD_GAIN_BARA_PER_RATIO * (flash_gas_ratio - 1.0)
    return max(downstream_pressure_bara, hydraulic_target_bara + field_residual_bara)


def e011_vent_generation_kgh(gas_inlet_kgh: float) -> float:
    if not math.isfinite(gas_inlet_kgh):
        raise ValueError("E011 gas inlet must be finite")
    if gas_inlet_kgh < 0.0:
        raise ValueError("E011 gas inlet must be nonneg")
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
        raise ValueError("LV-322501 flow ratio must be nonneg")
    return max(
        E003_P_DES_BARA
        + C003_LV_FIELD_GAIN_BARA_PER_RATIO * (lv_flow_ratio - 1.0),
        0.1,
    )
