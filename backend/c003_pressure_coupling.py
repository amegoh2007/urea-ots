"""Near-design 323C003 pressure model: two independent gas-load paths.

PT-323201 is charged by two physically distinct carbamate-gas sources, which the PFD
tabulates separately at the 4.1 bar a column pressure:

  * stream 301 -- prompt flash gas released across LV-322501 as the 144 bar stripper
    bottoms let down to 4.1 bar a (5064.7 m3/h, 119 C, MW 26.39).  It enters above the
    packed bed with the 311 reflux.
  * stream 302 -- gas evolved in the 323E002 rectifying heater and returned to the
    column below the bed (2875.7 m3/h, 135 C, MW 21.14).

Keeping them separate gives each source its own coupling chain:

  * opening LV-322501  -> more letdown flash gas  -> higher column pressure
  * more 323E002 duty  -> more evolved gas        -> higher column pressure

and neither term is inferred from the other.  Stream 305 (7677.1 m3/h) is the column
OUTLET, not a source: 301 + 302 = 7940.4 m3/h enter, and 263.3 m3/h (3.3 %) condense on
the bed where the 135 C heater gas meets the 119 C reflux.  Driving an inlet term with
305 would make the total feed back on itself, so the two inlet volumes are read from
their own PFD rows rather than back-computed by subtracting 301 from 305.

Design identity: both ratios 1.0 against a 3.2 bar a downstream node returns exactly
4.1 bar a, the PFD anchor.
"""
from __future__ import annotations

import math


# --- PFD volumetric gas loads at the 4.1 bar a / column-inlet states ------------------
C003_Q301_DES_M3H = 5064.7          # m3/h  LV-322501 letdown flash gas   (PFD stream 301)
C003_Q302_DES_M3H = 2875.7          # m3/h  323E002 rectifying-heater gas (PFD stream 302)
C003_Q305_DES_M3H = 7677.1          # m3/h  combined overhead -> 323E003  (PFD stream 305)
# Total charging the column.  Exceeds stream 305 by the packed-bed condensation the PFD
# implies (301 + 302 - 305), which is why 305 is not an inlet driver.
C003_Q_IN_DES_M3H = C003_Q301_DES_M3H + C003_Q302_DES_M3H          # 7940.4
C003_BED_CONDENSATION_DES_M3H = C003_Q_IN_DES_M3H - C003_Q305_DES_M3H   # 263.3

C003_P_DES_BARA = 4.1               # bar a, PT-323201 design (R323_C003_P_BARA)
E003_P_DES_BARA = 3.2               # bar a, receiving 323E003 / 323D001 node

# Compressible gas-load coefficient, anchored so the design inlet load reproduces the
# design column pressure against the design downstream pressure.
C003_GAS_LOAD_COEFF_M3H_PER_BAR = (
    C003_Q_IN_DES_M3H
    / math.sqrt(C003_P_DES_BARA ** 2 - E003_P_DES_BARA ** 2)
)

# 2025-06-28 startup-trend residual: 0.100 bar per point of LV-322501 opening, carried on
# the flash-gas ratio because that ratio is proportional to the valve opening at fixed
# upstream/downstream conditions.  Normalised at the field-calibrated 46.1 % design stroke.
C003_LV_OPEN_DES_PCT = 46.1
C003_LV_FIELD_GAIN_BARA_PER_RATIO = 0.100 * C003_LV_OPEN_DES_PCT    # 4.61

# 323E011 LP carbamate condenser: fixed condensation capacity, so incremental gas above it
# has nowhere to go but the PIC-323203 vent.
E011_GAS_FEED_DES_KGH = 6029.0                  # kg/h design gas load (701 + 786 + 321)
E011_CONDENSATION_CAPACITY_DES_KGH = 5589.0     # kg/h condensed at design -> 440 vented

def c003_pressure_target_bara(
    flash_gas_ratio: float,
    e002_gas_ratio: float,
    downstream_pressure_bara: float,
    lv_open_ratio: float | None = None,
) -> float:
    """Return the reduced-order PT-323201 target pressure, bar absolute.

    ``flash_gas_ratio``
        Live LV-322501 letdown flash-gas rate (PFD stream 301) over its design value.
    ``e002_gas_ratio``
        Live 323E002 rectifying-heater evolved-gas rate (PFD stream 302) over its design
        value.  Independent of the flash path: cutting PV-329202 collapses this term while
        the letdown keeps charging the column through the other.
    ``downstream_pressure_bara``
        Absolute pressure of the receiving 323E003 / 323D001 node, bar a.
    ``lv_open_ratio``
        Live LV-322501 throughput over design, carrying the empirical field residual.  The
        startup trend was measured against VALVE OPENING, so the residual rides the valve
        signal rather than the back-computed gas rate -- the latter carries a small
        steady-state offset from its live temperature terms, which this 4.61 bar/ratio gain
        would amplify into a design-point error.  Defaults to ``flash_gas_ratio``.

    At design (all ratios 1.0, downstream 3.2 bar a) this returns exactly 4.1 bar a.
    """
    if lv_open_ratio is None:
        lv_open_ratio = flash_gas_ratio
    values = (flash_gas_ratio, e002_gas_ratio, downstream_pressure_bara, lv_open_ratio)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("pressure-coupling inputs must be finite")
    if flash_gas_ratio < 0.0 or e002_gas_ratio < 0.0 or lv_open_ratio < 0.0:
        raise ValueError("gas-load flow ratios must be nonnegative")
    if downstream_pressure_bara <= 0.0:
        raise ValueError("downstream absolute pressure must be positive")

    equivalent_gas_load_m3h = (
        C003_Q301_DES_M3H * flash_gas_ratio        # LV-322501 letdown flash gas
        + C003_Q302_DES_M3H * e002_gas_ratio       # 323E002 rectifying-heater gas
    )
    hydraulic_target_bara = math.sqrt(
        downstream_pressure_bara ** 2
        + (equivalent_gas_load_m3h / C003_GAS_LOAD_COEFF_M3H_PER_BAR) ** 2
    )
    field_residual_bara = C003_LV_FIELD_GAIN_BARA_PER_RATIO * (lv_open_ratio - 1.0)
    return max(downstream_pressure_bara, hydraulic_target_bara + field_residual_bara)


def e011_vent_generation_kgh(gas_inlet_kgh: float) -> float:
    """Return the 323E011 gas that cannot condense and must leave via PIC-323203, kg/h.

    The condenser's cooling surface is fixed, so its condensation rate saturates at the
    design value.  Every kg/h of gas above that capacity is vented; below it, the drum
    condenses everything and generates no vent gas.
    """
    if not math.isfinite(gas_inlet_kgh):
        raise ValueError("E011 gas inlet must be finite")
    if gas_inlet_kgh < 0.0:
        raise ValueError("E011 gas inlet must be nonnegative")
    return max(gas_inlet_kgh - E011_CONDENSATION_CAPACITY_DES_KGH, 0.0)
