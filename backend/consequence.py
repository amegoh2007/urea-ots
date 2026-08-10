"""Generic downstream-consequence physics shared by EVERY vessel, valve and pump.

WHY THIS MODULE EXISTS
----------------------
Before this file, each deviation scenario that had ever been written up was wired into
`main.py` at the ONE tag it was written up against, with its own hand-picked constant:

    322E001 seal loss  ->  25000.0 * (theta/theta_des) * sqrt(dP/dP_des)
    323C003 seal loss  ->   5000.0 * (theta/theta_des)
    323F004 seal loss  ->   5000.0 * (theta/theta_des)
    323F004 overfill   ->  (level - 100) * 100.0            <- identically 0: level is clamped to 100
    328D001 low level  ->  m = 0 at M <= 1.5 kg             <- a cliff, not a pump curve
    324F003 low level  ->  P := 1.013 bar a                 <- a state override, cannot recover

Three things are wrong with that, and all three are what this module fixes.

1.  UNEQUAL CONSEQUENCES FOR EQUAL CAUSES.  Losing the liquid seal on 323C003 and losing it on
    328C004 are the same event -- a drain nozzle uncovers and the vessel's gas inventory escapes
    through a valve sized for liquid.  One of them produced 5000 kg/h of gas and the other produced
    nothing at all, because nobody had written that scenario down yet.  An operator trainee who
    learns the plant on a model like that learns the model's authoring history, not the plant.

2.  UNPHYSICAL MAGNITUDES.  25000 and 5000 kg/h are not measurements; they are numbers that made a
    demo look right.  The mass a control valve passes when its seal breaks is not a free parameter:
    the valve's flow coefficient is fixed by its LIQUID design duty, and gas flow through that same
    coefficient follows IEC 60534 / ISA-75.01 with a real expansion factor and a real choke point.
    Every blow-through rate in this file is derived from the valve's own design duty; nothing is
    picked to taste.  (Sanity check: the derived LV-322501 rate lands at ~30 t/h against the 25 t/h
    that had been picked by hand, so the hand number was the right ORDER -- it just could not be
    transferred to any other valve, which is the entire problem.)

3.  DISCONTINUITIES AND STATE OVERRIDES.  `if level <= 0` and `P := 1.013` are step changes in the
    right-hand side of an ODE.  They chatter, they cannot be un-done by correct operator action
    (the state was overwritten, not driven), and they arrive with zero transport lag no matter how
    far downstream the affected equipment sits.  Everything here is continuous in its arguments and
    every consequence enters as a RATE that some existing balance integrates, so the plant recovers
    when the operator recovers it.

THE DESIGN-ANCHOR CONTRACT
--------------------------
The engine is pinned bit-exactly at the 1750 MTPD / 100 % load design point, and a settled boot
captures calibration constants from that fixed point.  Therefore EVERY function here is written so
that at the design arguments it returns EXACTLY zero extra effect:

  * `seal_fraction`      -> 1.0 at any normal level (design levels are far above the nozzle)
  * `blowthrough_kgh`    -> multiplied by (1 - seal_fraction), so 0.0 at design
  * `entrainment_carryover_kgh` -> DEPARTURE form: E(live) - E(design), so 0.0 at design
  * `pump_capacity_factor` -> 1.0 whenever NPSHa exceeds NPSHr + margin, true at design
  * `mushy_flow_factor`  -> 1.0 whenever T is above the crystallisation boundary, true at design

They are also all monotone and bounded, so none of them can drive an integrator to a rail.

REFERENCES
----------
  * Control-valve sizing (gas expansion factor Y, terminal pressure-drop ratio x_T, specific-heat
    ratio factor F_k): IEC 60534-2-1 / ISA-75.01.01, standard form
        m = N * C * Y * sqrt(x * P1 * rho1)  ,  Y = 1 - x/(3*F_k*x_T)  ,  x_choked = F_k*x_T
  * Vapour-liquid disengagement velocity: Souders, M. and Brown, G.G., Ind. Eng. Chem. 26 (1934) 98
        u_max = K * sqrt((rho_L - rho_V)/rho_V)
  * Entrainment above the disengagement velocity: power-law in the velocity ratio, the standard
    reduced form of Ishii & Mishima (NUREG/CR-2885, 1984) used for separator carry-over.
  * Urea-water solubility (the crystallisation boundary): CRC Handbook / Perry's 8th ed. urea
    solubility table, converted from g urea per 100 g water to urea mass fraction; anchored at the
    pure-urea melting point 132.7 C.
  * NPSH: Hydraulic Institute ANSI/HI 9.6.1 -- NPSH margin ratio, 3 % head-drop knee.
"""

from __future__ import annotations

import math

R_GAS_J = 8.314462618          # J/mol.K
G_ACC   = 9.80665              # m/s2
P_ATM_BARA = 1.01325           # bar a


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else (hi if x > hi else x)


# ==================================================================================================
#  1.  LIQUID SEAL  --  how much of the drain nozzle is still covered
# ==================================================================================================
#  A drain nozzle does not uncover at a mathematical point: it uncovers over its own bore.  Between
#  "fully covered" and "fully open to the vapour space" the valve passes a two-phase mixture whose
#  gas fraction grows with the uncovered area.  Modelling that as a linear ramp across the nozzle
#  bore (expressed in % of the level span) does three things at once:
#     * it removes the `if level <= 0` step from the right-hand side of every level ODE;
#     * it reproduces the real plant behaviour that blow-through STARTS before the transmitter
#       reads zero -- the tap is above the nozzle on most of these vessels;
#     * it makes the transition reversible, so restoring level restores the seal.
SEAL_BAND_PCT_DEFAULT = 3.0        # %, level-span equivalent of the drain-nozzle bore


def seal_fraction(level_pct: float, seal_pct: float = 0.0,
                  band_pct: float = SEAL_BAND_PCT_DEFAULT) -> float:
    """Fraction of the drain nozzle still covered by liquid.  1.0 = sealed, 0.0 = open to gas.

    `seal_pct` is the level (in transmitter %) at which the nozzle is JUST fully uncovered, i.e.
    the nozzle centreline; `band_pct` is the bore expressed in the same % units.  At every design
    level in this flowsheet the result is exactly 1.0, so every consequence keyed on (1 - seal)
    is exactly 0.0 at design."""
    return clamp((level_pct - seal_pct) / max(band_pct, 1e-9), 0.0, 1.0)


# ==================================================================================================
#  2.  GAS BLOW-THROUGH  --  IEC 60534 compressible flow through a valve sized for liquid
# ==================================================================================================
def gas_density_ideal(p_bara: float, t_c: float, mw_g_mol: float) -> float:
    """Ideal-gas density (kg/m3).  rho = P*M/(R*T)."""
    return max(p_bara, 1e-9) * 1e5 * (mw_g_mol / 1000.0) / (R_GAS_J * max(t_c + 273.15, 1.0))


def expansion_factor(dp_bar: float, p1_bara: float, x_t: float = 0.70,
                     gamma: float = 1.30) -> tuple:
    """IEC 60534-2-1 compressible correction.  Returns (Y, dp_effective_bar, choked).

    x       = dP/P1                      pressure-drop ratio
    F_k     = gamma/1.40                 specific-heat-ratio factor
    x_ch    = F_k * x_T                  the ratio at which the vena contracta chokes
    Y       = 1 - x_eff/(3*x_ch)         expansion factor, bounded to [2/3, 1]
    dP_eff  = x_eff * P1                 the drop that actually does work on the flow

    Beyond x_ch the valve is choked and further downstream depressurisation buys no extra flow --
    which is exactly why a seal-loss blow-through has a CEILING instead of running away as the
    downstream section depressurises."""
    p1 = max(p1_bara, 1e-9)
    x = clamp(dp_bar / p1, 0.0, 1.0)
    x_ch = max((gamma / 1.40) * x_t, 1e-6)
    choked = x >= x_ch
    x_eff = min(x, x_ch)
    y = clamp(1.0 - x_eff / (3.0 * x_ch), 2.0 / 3.0, 1.0)
    return y, x_eff * p1, choked


def blowthrough_kgh(m_liq_des_kgh: float, rho_liq: float, dp_des_bar: float,
                    theta_frac: float, rho_gas: float, p_up_bara: float, dp_bar: float,
                    seal_frac: float, x_t: float = 0.70, gamma: float = 1.30) -> float:
    """Gas mass flow through a drain valve whose liquid seal has been (partly) lost, kg/h.

    A control valve's flow coefficient is a property of the VALVE, not of the fluid:

        C = m_liq_des / (N * sqrt(rho_liq * dP_des))          (from the liquid design duty)
        m_gas = N * C * theta * Y * sqrt(rho_gas * dP_eff)    (IEC 60534 compressible)

    Eliminating C and N (they cancel identically):

        m_gas = m_liq_des * theta * Y * sqrt( (rho_gas * dP_eff) / (rho_liq * dP_des) )

    so the blow-through rate is FIXED by the valve's own design duty and the live gas density.
    Nothing here is tuned.  Multiplied by (1 - seal_frac) it is identically 0.0 whenever the vessel
    holds a normal level, which is the design-anchor contract.

    The sqrt(rho_gas/rho_liq) factor is the whole physical story an operator needs: gas is ~10x
    lighter than the liquor, so the same valve opening passes far less MASS -- but at 50-100x the
    VOLUME, which is why the downstream section overpressures and the valve erodes."""
    if seal_frac >= 1.0 or theta_frac <= 0.0 or dp_bar <= 0.0:
        return 0.0
    y, dp_eff, _ = expansion_factor(dp_bar, p_up_bara, x_t, gamma)
    ratio = (max(rho_gas, 1e-9) * max(dp_eff, 0.0)) / (max(rho_liq, 1e-9) * max(dp_des_bar, 1e-9))
    return max(m_liq_des_kgh, 0.0) * max(theta_frac, 0.0) * y * math.sqrt(max(ratio, 0.0)) \
        * (1.0 - seal_frac)


# ==================================================================================================
#  3.  LIQUID CARRY-OVER  --  Souders-Brown disengagement, in anchored departure form
# ==================================================================================================
#  A vertical separator stops separating for two reasons, and a real overfill hits both at once:
#     (a) the superficial vapour velocity approaches the Souders-Brown terminal settling velocity
#             u_max = K * sqrt((rho_L - rho_V)/rho_V)
#         so droplets are carried up faster than they fall;
#     (b) the rising liquid level eats the disengagement HEIGHT, so the droplets that would have
#         settled no longer have the distance in which to do it.
#  Writing both as ratios to their own design values lets the whole thing collapse to one
#  dimensionless number with no vessel geometry required (the cross-sectional area cancels):
#
#     u/u_max  ~  m_vap / sqrt(rho_V * (rho_L - rho_V))        (area and K cancel in the ratio)
#     R_u      =  (m_vap/m_vap_des) * sqrt( rho_V_des / rho_V ) * sqrt( rho_L_des / rho_L )
#     R_h      =  (1 - L_des) / (1 - L)                        (vertical vessel: h_dis ~ 1 - level)
#     E        =  E_des * R_u^n * R_h                          (entrained liquid / vapour mass)
#
#  and the carried-over liquid is the EXCESS over the entrainment the design point already carries:
#
#     m_carry  =  m_vap * max(E - E_des, 0)      ==  0.0 at design, exactly.
#
#  Signs, all of which match the written-up scenarios:
#     level up            -> R_h up   -> carry-over up      (Scenarios.md 1.1, 2.1, 5.4)
#     vapour load up      -> R_u up   -> carry-over up      (Scenarios.md 5.1 "vapour velocity spikes")
#     pressure DOWN       -> rho_V down -> R_u up -> carry-over up  (deeper vacuum entrains more)
E_DES_DEFAULT   = 0.004     # -, entrained liquid/vapour mass ratio a well-sized separator carries
E_EXPONENT      = 3.2       # -, power law in the velocity ratio (reduced Ishii-Mishima form)
E_CAP           = 0.60      # -, ceiling: total flooding, the line runs as a two-phase slug


def entrainment_ratio(m_vap_kgh: float, m_vap_des_kgh: float,
                      level_frac: float, level_des_frac: float,
                      p_bara: float = None, p_des_bara: float = None,
                      t_c: float = None, t_des_c: float = None,
                      rho_liq: float = None, rho_liq_des: float = None,
                      e_des: float = E_DES_DEFAULT, exponent: float = E_EXPONENT,
                      e_cap: float = E_CAP) -> float:
    """Entrained liquid / vapour mass ratio, anchored so that it equals `e_des` at design."""
    r_u = (max(m_vap_kgh, 0.0) / max(m_vap_des_kgh, 1e-9))
    if p_bara is not None and p_des_bara is not None:
        # rho_V ~ P/T (ideal gas), and u/u_max ~ m/sqrt(rho_V) at fixed liquid density
        t_k = (t_c + 273.15) if t_c is not None else 1.0
        t_des_k = (t_des_c + 273.15) if t_des_c is not None else 1.0
        r_u *= math.sqrt(max(p_des_bara, 1e-9) / max(p_bara, 1e-9)) \
            * math.sqrt(max(t_k, 1.0) / max(t_des_k, 1.0))
    if rho_liq is not None and rho_liq_des is not None:
        r_u *= math.sqrt(max(rho_liq_des, 1e-9) / max(rho_liq, 1e-9))
    head_des = max(1.0 - clamp(level_des_frac, 0.0, 0.999), 1e-3)
    head_live = max(1.0 - clamp(level_frac, 0.0, 0.999), 1e-3)
    r_h = head_des / head_live
    return min(e_des * (r_u ** exponent) * r_h, e_cap)


#  A separator is SPECIFIED with a carry-over allowance, and operating inside that allowance is not
#  an upset -- it is the design duty.  Only entrainment beyond the allowance is a process event that
#  reaches downstream equipment as liquid.  Measuring the excess from `E_TRIGGER_MULT * E_des`
#  instead of from `E_des` states that, keeps the function continuous (a kink at the threshold, not
#  a step), keeps it exactly 0.0 at design, and stops a 1 % level wobble from being reported as a
#  flooded vessel.  Above the allowance the response is the full power law.
E_TRIGGER_MULT = 2.0


def entrainment_carryover_kgh(m_vap_kgh: float, m_vap_des_kgh: float,
                              level_frac: float, level_des_frac: float,
                              **kw) -> float:
    """Liquid carried out of a separator in its own vapour line, kg/h.  0.0 at design, exactly."""
    e_des = kw.get("e_des", E_DES_DEFAULT)
    e_live = entrainment_ratio(m_vap_kgh, m_vap_des_kgh, level_frac, level_des_frac, **kw)
    return max(m_vap_kgh, 0.0) * max(e_live - E_TRIGGER_MULT * e_des, 0.0)


# ==================================================================================================
#  4.  PUMP NPSH  --  one law for "level fell" AND "temperature rose"
# ==================================================================================================
#  Every cavitation scenario in the three scenario documents is the same equation seen from a
#  different side.  A low level removes static head; a hot tank raises the vapour pressure; a
#  collapsing vessel pressure removes the pressurisation term; a sudden flash removes all three.
#  NPSH available says so in one line:
#
#     NPSHa = (P_vessel - Psat(T)) / (rho*g) + h_static - h_friction          [m of liquid]
#
#  and the pump keeps its capacity until NPSHa falls into the margin above the required NPSH, then
#  loses it over the cavitation knee instead of switching off at a threshold.  That single change
#  covers, with no per-tag code:
#     Scenarios.md   2.2 transfer-pump cavitation, 3.2 NPSH loss on rapid depressurisation,
#                    5.4 melt-pump NPSH destroyed by seal loss
#     Scenarios3.md  1.2 lean-carbamate pump, 2.2 reflux pump, 3.2 extraction pump,
#                    4.1 ammonia-water pump (level), 4.2 ammonia-water pump (TEMPERATURE),
#                    4.3 urea-solution feed pumps
NPSH_MARGIN_M_DEFAULT = 0.6      # m, ANSI/HI 9.6.1 margin above NPSHr before capacity is affected


def npsh_available_m(p_vessel_bara: float, psat_bara: float, rho: float,
                     static_head_m: float, friction_head_m: float = 0.0) -> float:
    """NPSH available at the pump suction, metres of the pumped liquid."""
    return (max(p_vessel_bara - psat_bara, -10.0) * 1e5) / (max(rho, 1e-6) * G_ACC) \
        + static_head_m - friction_head_m


def pump_capacity_factor(npsh_a_m: float, npsh_r_m: float,
                         margin_m: float = NPSH_MARGIN_M_DEFAULT) -> float:
    """Delivered-flow fraction, 1.0 -> 0.0 across the cavitation knee.

    Above NPSHr + margin the pump is unaffected (factor 1.0, the design condition).  Between NPSHr
    and NPSHr + margin the head curve is already breaking down and the flow falls; at NPSHr the
    pump is in full cavitation and delivers nothing.  Linear across the knee -- the real 3 %
    head-drop curve is steeper than linear, but a linear knee is the conservative training
    behaviour (the trainee gets a visible, recoverable warning band rather than a trip)."""
    return clamp((npsh_a_m - npsh_r_m) / max(margin_m, 1e-6), 0.0, 1.0)


# ==================================================================================================
#  5.  CRYSTALLISATION  --  the boundary is a solubility curve, not a constant
# ==================================================================================================
#  `_f_flow(T, 132.7)` in main.py used the PURE-UREA melting point as the crystallisation boundary
#  for every urea stream in the plant.  That is right for the 99.7 % melt leaving 324E003 and badly
#  wrong for the 68.7 % liquor in 323C003, which crystallises near 52 C -- so the model's own
#  mushy-zone guard fired 80 C early on every stream except one.
#
#  Urea-water solubility (CRC / Perry), g urea per 100 g water -> urea mass fraction w = S/(100+S):
#
#      T (C)  |   0     20     40     60     80    100    120   132.7
#      S      |  66.7  105.0  165.0  250.0  400.0  733.0 1300.0    inf
#      w      | 0.400  0.512  0.623  0.714  0.800  0.880  0.929  1.000
#
#  Read the other way round -- the temperature at which a liquor of strength w is saturated -- this
#  is the crystallisation boundary that every urea-bearing line in the plant actually sits above.
#  Note how directly it reproduces the operating envelope: the 80 % product tank saturates at 80 C
#  (the plant's own low-temperature alarm), the 95 % Stage-1 melt at ~124 C and the 98.6 % Stage-2
#  melt at ~130 C, which is why 324F003 has so little margin.
_UREA_SOL_W = (0.400, 0.512, 0.623, 0.714, 0.800, 0.880, 0.929, 1.000)
_UREA_SOL_T = (0.0,    20.0,  40.0,  60.0,  80.0, 100.0, 120.0, 132.7)

#  Metastable-zone width: a saturated liquor does not nucleate the instant it crosses the solubility
#  line -- it subcools first.  Industrial crystallisation practice puts the metastable zone for urea
#  at a few K, which is exactly the gap between the textbook saturation temperature and the
#  temperatures operators actually see plugging happen (95 % melt: saturation ~124 C, plant
#  experience ~115-120 C).  Flow is restricted only BELOW the metastable limit; the flag fires ON
#  the solubility line, so the operator gets the warning before the line restricts.
UREA_METASTABLE_DT_C = 6.0

#  Ammonium carbamate is the OTHER solid that plugs lines in this plant, and it plugs the ones urea
#  never reaches: the HP scrubber overflow, the LP carbamate condensers, the lean-carbamate recycle,
#  the reflux legs.  The engine already carried one plant-anchored number for it -- the 60 C the
#  322E003 overflow is judged against -- but applied it at exactly one line.  Carbamate solubility
#  rises steeply with temperature, so a LEANER liquor stays in solution colder; anchoring the known
#  60 C to the strength it belongs to and scaling linearly with carbamate loading extends that one
#  plant number to every carbamate-bearing line without inventing a second constant.
#  GAP: a measured ammonium-carbamate solubility curve would replace the linear scaling; see
#  handoff.md.  The SIGN and the ordering of the lines are right either way.
CARBAMATE_CRYST_T_C = 60.0       # C, at the reference carbamate strength below
CARBAMATE_W_REF     = 0.7719     # -, (NH3 + CO2) mass fraction of the 322E003 design overflow --
#   the stream the plant's 60 C number belongs to (computed from _EJ_OVERFLOW_KMOLH: 1234.5 kmol/h
#   NH3 + 458.4 kmol/h CO2 against 674.2 kmol/h H2O).  Anchoring on the strength the constant was
#   measured at is what makes `liquor_crystallization_T` return exactly 60.0 C for that stream and
#   something lower, correctly, for every leaner carbamate line downstream.


def carbamate_crystallization_T(w_nh3: float, w_co2: float,
                                w_ref: float = CARBAMATE_W_REF,
                                t_ref: float = CARBAMATE_CRYST_T_C) -> float:
    """Carbamate saturation temperature of a liquor, C, from its NH3 + CO2 mass loading."""
    return t_ref * clamp((max(w_nh3, 0.0) + max(w_co2, 0.0)) / max(w_ref, 1e-9), 0.0, 1.5)


def liquor_crystallization_T(w: dict) -> float:
    """Crystallisation boundary of a mixed urea / carbamate liquor, C.

    Whichever solid appears FIRST as the stream cools is the one that plugs the line, so the
    boundary is the higher of the two saturation temperatures.  This is what makes one call site
    valid for the 55.9 % urea + 18 % carbamate stripper bottoms, the 68.7 % column liquor, the
    99.7 % melt and the carbamate recycle alike."""
    return max(urea_crystallization_T(w.get("Urea", 0.0)),
               carbamate_crystallization_T(w.get("NH3", 0.0), w.get("CO2", 0.0)))


def urea_crystallization_T(w_urea: float) -> float:
    """Saturation (crystallisation) temperature of a urea-water liquor, C, from its urea mass
    fraction.  Piecewise-linear on the solubility table above; flat below the weakest tabulated
    point (a very dilute liquor cannot salt out at any plant temperature)."""
    w = clamp(w_urea, 0.0, 1.0)
    if w <= _UREA_SOL_W[0]:
        return _UREA_SOL_T[0]
    for i in range(1, len(_UREA_SOL_W)):
        if w <= _UREA_SOL_W[i]:
            f = (w - _UREA_SOL_W[i - 1]) / (_UREA_SOL_W[i] - _UREA_SOL_W[i - 1])
            return _UREA_SOL_T[i - 1] + f * (_UREA_SOL_T[i] - _UREA_SOL_T[i - 1])
    return _UREA_SOL_T[-1]


def mushy_flow_factor(t_c: float, t_cryst_c: float, dt_mush: float = 5.0,
                      dt_metastable: float = 0.0) -> float:
    """Flow factor across the mushy zone: 1.0 fully molten, 0.0 at the solidus.

    Restriction begins `dt_metastable` BELOW the saturation temperature (the metastable zone) and
    reaches zero `dt_mush` further down.  With dt_metastable = 0 this is bit-identical to the
    engine's existing `_f_flow`, so every call site that keeps the old boundary is unchanged."""
    t_start = t_cryst_c - dt_metastable
    return clamp((t_c - t_start) / max(dt_mush, 1e-9), 0.0, 1.0)


# ==================================================================================================
#  6.  TRANSPORT LAG  --  a consequence arrives when the fluid arrives, not on the same tick
# ==================================================================================================
def transport_time_s(volume_m3: float, mass_flow_kgh: float, rho: float,
                     td_max_s: float = 1800.0) -> float:
    """Plug-flow transit time of a connecting line, s:  td = rho*V / m_dot.

    This is the honest way to get a dead time: it falls as the plant speeds up and rises as the
    plant slows down, which is exactly what a trainee needs to see when they cut a feed.  Capped so
    a stalled line does not produce an unbounded delay buffer."""
    if mass_flow_kgh <= 1e-9:
        return td_max_s
    return clamp(max(rho, 1e-9) * max(volume_m3, 0.0) * 3600.0 / mass_flow_kgh, 0.0, td_max_s)


def pipe_volume_m3(dn_mm: float, length_m: float) -> float:
    """Internal volume of a run of pipe, m3."""
    d = max(dn_mm, 0.0) / 1000.0
    return math.pi / 4.0 * d * d * max(length_m, 0.0)


# ==================================================================================================
#  7.  NON-CONDENSABLE / AIR INGRESS  --  vacuum breaks at a rate, it does not snap
# ==================================================================================================
def air_ingress_kgh(p_vac_bara: float, area_mm2: float, t_c: float = 25.0,
                    mw_g_mol: float = 28.96, p_atm_bara: float = P_ATM_BARA) -> float:
    """Atmospheric air drawn into a vacuum node through an opening of `area_mm2`, kg/h.

    Below the critical pressure ratio (0.528 for air) the leak is CHOKED, so the flow depends only
    on the atmospheric side -- which is why a broken barometric seal admits a constant, large air
    load however deep the vacuum was.  Above it the flow follows the subsonic compressible orifice
    relation and tapers to zero as the node reaches atmosphere, so the pressure state settles at
    1 bar a instead of being assigned it.

        choked :  m = A * P_atm * sqrt( gamma/(R_s*T) * (2/(gamma+1))^((gamma+1)/(gamma-1)) )
        subsonic: m = A * P_atm * sqrt( 2*gamma/((gamma-1)*R_s*T) * (r^(2/g) - r^((g+1)/g)) )
    """
    gamma = 1.40
    r_s = R_GAS_J / (mw_g_mol / 1000.0)                 # specific gas constant, J/kg.K
    t_k = max(t_c + 273.15, 1.0)
    a_m2 = max(area_mm2, 0.0) * 1e-6
    p1 = max(p_atm_bara, 1e-9) * 1e5                    # Pa
    r = clamp(max(p_vac_bara, 0.0) / max(p_atm_bara, 1e-9), 0.0, 1.0)
    r_crit = (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))       # 0.528 for air
    if r <= r_crit:
        flux = math.sqrt(gamma / (r_s * t_k)
                         * (2.0 / (gamma + 1.0)) ** ((gamma + 1.0) / (gamma - 1.0)))
    else:
        term = max(r ** (2.0 / gamma) - r ** ((gamma + 1.0) / gamma), 0.0)
        flux = math.sqrt(2.0 * gamma / ((gamma - 1.0) * r_s * t_k) * term)
    return a_m2 * p1 * flux * 3600.0                    # kg/h


# ==================================================================================================
#  8.  ONE-CALL VESSEL CONSEQUENCE BLOCK
# ==================================================================================================
#  Every level-controlled vessel in the flowsheet calls THIS, with its own design anchors.  Adding a
#  new vessel to the flowsheet therefore adds the full consequence set automatically -- which is the
#  requirement that started this module: an unlisted deviation on an unlisted vessel must behave the
#  same way as the listed deviation on the vessel somebody happened to write up.
def vessel_consequences(level_pct: float, level_des_pct: float, level_full_pct: float = 100.0,
                        *,
                        seal_pct: float = 0.0, seal_band_pct: float = SEAL_BAND_PCT_DEFAULT,
                        m_liq_des_kgh: float = 0.0, rho_liq: float = 1000.0,
                        dp_des_bar: float = 1.0, theta_frac: float = 1.0,
                        p_up_bara: float = 1.0, p_down_bara: float = 1.0,
                        gas_mw: float = 28.0, gas_t_c: float = 100.0,
                        m_vap_kgh: float = 0.0, m_vap_des_kgh: float = 0.0,
                        p_bara: float = None, p_des_bara: float = None,
                        t_c: float = None, t_des_c: float = None,
                        e_des: float = E_DES_DEFAULT) -> dict:
    """Return every level-driven consequence for one vessel, in one anchored call.

    Keys:
      seal_frac      1.0 sealed .. 0.0 nozzle fully uncovered
      blowthrough    kg/h of vapour escaping through the drain valve (0.0 while sealed)
      liq_factor     multiplier on the liquid drain (goes to 0 as the gas takes the valve over)
      carryover      kg/h of liquid leaving in the OVERHEAD line (0.0 at design, exactly)
      flooded        True once the level is at/over the vessel-full mark
    """
    sf = seal_fraction(level_pct, seal_pct, seal_band_pct)
    dp = max(p_up_bara - p_down_bara, 0.0)
    rho_g = gas_density_ideal(p_up_bara, gas_t_c, gas_mw)
    bt = blowthrough_kgh(m_liq_des_kgh, rho_liq, dp_des_bar, theta_frac,
                         rho_g, p_up_bara, dp, sf)
    lvl_f = clamp(level_pct / max(level_full_pct, 1e-9), 0.0, 1.0)
    lvl_d = clamp(level_des_pct / max(level_full_pct, 1e-9), 0.0, 1.0)
    co = 0.0
    if m_vap_des_kgh > 1e-9:
        co = entrainment_carryover_kgh(m_vap_kgh, m_vap_des_kgh, lvl_f, lvl_d,
                                       p_bara=p_bara, p_des_bara=p_des_bara,
                                       t_c=t_c, t_des_c=t_des_c, e_des=e_des)
    return {
        "seal_frac":   sf,
        "blowthrough": bt,
        "liq_factor":  sf,
        "carryover":   co,
        "flooded":     bool(level_pct >= level_full_pct),
    }
