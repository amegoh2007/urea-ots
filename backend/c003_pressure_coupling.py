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

# 2025-06-28 startup-trend residual: RETIRED, and the trend's own rows are why.
#
# The head this module returns is the friction head of ONE flowing line.  There is no valve between
# the 323C003 overhead and 323E003, so PT-323201 and the PIC-323202 transmitter are two ends of one
# gas node and  Q = C*sqrt(P_c003^2 - P_d001^2)  is the only relation allowed between them.  The
# node itself is integrated from the whole-envelope gas balance in step_sim() (generated, condensed,
# vented); this function only puts the column above it.
#
# A 0.100 bar per % LV-322501 opening residual used to be added to the ANSWER, i.e. outside that
# law, and it broke it on exactly the lever it was calibrated for: across an LV sweep the head
# implied -100 % to +101 % of the flow actually passing, and at 30 % opening it drove the column
# onto its own downstream floor (PT-323201 == PIC-323202 with 5555 m3/h still flowing).
#
# It is not a process gain.  Regressing the trend's own 721 rows:
#     whole startup, LV 0.00-45.40 %      slope +0.0980 bar/%,  r = +0.983
#     near design,   LV 35-50 %, n = 373  slope -0.0099 bar/%,  r = -0.072
# Over the ramp LV-322501 and PT-323201 rise together because the whole recirculation section is
# filling and coming up to load -- the regression captures the ramp, not the lever.  At load the
# field data shows no dependence at all, because 323E003 absorbs the extra gas for a few hundredths
# of a bar.  That is what the closed balance produces: 0.0222 bar/% at design, the hydraulic slope.
# Constants kept as provenance and for the sensitivity tests; nothing here consumes them.
C003_LV_OPEN_DES_PCT = 46.1                 # %, LV-322501 design stroke (trend normalisation)
C003_LV_TREND_BARA_PER_PCT = 0.100          # bar per % opening, the SUPERSEDED ramp reading

# 323E011 LP carbamate condenser: fixed condensation capacity, so incremental gas above it
# has nowhere to go but the PIC-323203 vent.
E011_GAS_FEED_DES_KGH = 6029.0                  # kg/h design gas load (701 + 786 + 321)
E011_CONDENSATION_CAPACITY_DES_KGH = 5589.0     # kg/h condensed at design -> 440 vented

def c003_pressure_target_bara(
    flash_gas_ratio: float,
    e002_gas_ratio: float,
    downstream_pressure_bara: float,
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

    The result is the friction head of one flowing line above that node, so inverting it gives
    back the same relation PIC-323202 sees:  Q = C * sqrt(P_c003^2 - P_d001^2).  Nothing is added
    outside the square root, which is what keeps the two pressures on one node (see the module
    comment).  At design (both ratios 1.0, downstream 3.2 bar a) it returns exactly 4.1 bar a.
    """
    values = (flash_gas_ratio, e002_gas_ratio, downstream_pressure_bara)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("pressure-coupling inputs must be finite")
    if flash_gas_ratio < 0.0 or e002_gas_ratio < 0.0:
        raise ValueError("gas-load flow ratios must be nonnegative")
    if downstream_pressure_bara <= 0.0:
        raise ValueError("downstream absolute pressure must be positive")

    equivalent_gas_load_m3h = (
        C003_Q301_DES_M3H * flash_gas_ratio        # LV-322501 letdown flash gas
        + C003_Q302_DES_M3H * e002_gas_ratio       # 323E002 rectifying-heater gas
    )
    return math.sqrt(
        downstream_pressure_bara ** 2
        + (equivalent_gas_load_m3h / C003_GAS_LOAD_COEFF_M3H_PER_BAR) ** 2
    )


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
