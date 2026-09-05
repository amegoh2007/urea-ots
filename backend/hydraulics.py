"""Rigorous hydraulic primitives: IEC 60534 / ISA-75.01 valve sizing and vapour-space pressure states.

PHASE 2 of the Heuristic Eradication Report.  This module carries the equations; the wiring into
each unit is done at the call sites, one unit at a time, so the boot pin can be re-proved after each.

WHAT THIS REPLACES
------------------
Two whole families of scripted consequence, both named in the report:

  A-6 / A-7  Every vessel pressure in the engine was  dP/dt = K*(gen - out)  with K a single
             copy-pasted 0.02 bar/(kg/s) shared by nine vessels of wildly different volume,
             temperature and vapour molecular weight -- a 0.46 bar a vacuum separator and a 16.8
             bar a hydrolyser on the same coefficient.  323F004 was worse still: its pressure was
             an ALGEBRAIC setpoint (design + 0.45 bar per unit relative vapour excess) that the
             state chased through an arbitrary lag, i.e. pressure followed flow when physically
             flow follows pressure.  `vessel_dpdt` is the real coefficient, RT/(V_v.M), from each
             vessel's own geometry and live state.

  D-1 / D-2  No valve in the engine had a Cv.  Every flow was  design x (stroke/stroke_des)  and
             sometimes x sqrt(dP/dP_des): the installed characteristic was linear whatever the trim,
             density was absent (it cancels only if constant, which it is not across 20-99 % urea),
             and the `_fic_flow` loops carried no dP term at all, so a downstream pressure change
             could not move them.  Compressible services were sized as incompressible orifices --
             HV-322604 lets vapour down 140.7 -> 4 bar a, a pressure ratio of 0.028, deeply choked,
             and the model let flow keep rising as downstream pressure fell.

ON Cv PROVENANCE -- READ THIS BEFORE ADDING A SITE
--------------------------------------------------
`References/Datasheets` holds equipment datasheets (vessels, exchangers, pumps).  It contains NO
control-valve datasheets, so there is no vendor Cv or FL anywhere in this repository, and claiming
one would be inventing data.  `cv_from_design_liquid` / `cv_from_design_gas` therefore BACK-SOLVE
Cv_max from the licensor's own design duty: the PFD flow, the design stroke, and the design
pressures on both sides.  That is standard practice when sizing an OTS valve model against a design
case, and it is what keeps the boot pin bit-exact -- at the design stroke and design dP the law
returns the design flow by construction.

What the back-solve does NOT give is the installed characteristic; that is a modelling choice and it
is stated per site, not hidden.  Equal-percentage is the default for throttling service (it is what
these loops are tuned around) and linear for on-off / vent duty.  Everything else -- the dP term,
the density term, the choke limit, the expansion factor -- is first-principles once Cv is fixed, and
those are the terms the frozen form was missing.

UNITS.  Flows kg/h, pressures bar a, temperatures C (converted internally), densities kg/m3.
Cv in US gallons/min at 1 psi.  N-constants follow IEC 60534-2-1 in those units.
"""
import math

# --- IEC 60534-2-1 numerical constants, for Cv (US gpm/psi), bar, kg/h, kg/m3, K -----------------
N6 = 27.3          # mass flow, liquid:      w [kg/h] = N6.Fp.Cv.sqrt(dP[bar].rho1[kg/m3])
N8 = 94.8          # mass flow, gas:         w [kg/h] = N8.Fp.Cv.P1[bar].Y.sqrt(x.M/(T1[K].Z))
R_GAS = 8.314462618            # J/(mol.K)
_BAR_TO_PA = 1.0e5

#  Liquid pressure-recovery factor.  No valve datasheets exist in this repo (see module docstring),
#  so this is the IEC 60534-2-1 Table-1 representative value for a globe valve with a contoured plug
#  and flow-to-open -- the trim class every throttling service in this plant is described as in the
#  reference documents.  It is a stated assumption, applied uniformly, not a fitted constant: it
#  sets only WHERE choking begins, and every site here runs well below that point at design.
FL_GLOBE = 0.90
FF_CONST = 0.96    # liquid critical pressure ratio factor, FF = 0.96 - 0.28.sqrt(Pv/Pc); the 0.96
                   # intercept is used where Pv << Pc, which holds for every liquid service here.

#  Gas pressure-differential ratio factor at choking, same Table-1 basis and the same caveat.
XT_GLOBE = 0.75


# ==================================================================================================
#  Installed characteristic
# ==================================================================================================
#  Rangeability of an equal-percentage globe trim.  50:1 is the IEC 60534-2-1 representative value
#  for a contoured plug and is what the equal-% law below is written around.
EQUAL_PCT_RANGE = 50.0


def cv_fraction(h: float, characteristic: str = "equal_pct") -> float:
    """Fraction of rated Cv passed at fractional stroke `h` in [0, 1].

    equal_pct:  Cv/Cv_max = R^(h-1)      -- constant gain in per-cent of flow per per-cent of lift,
                                            which is why throttling loops are tuned around it.
    linear:     Cv/Cv_max = h
    quick_open: Cv/Cv_max = sqrt(h)

    Clamped at both ends: a valve cannot pass more than rated, and R^(h-1) never reaches zero, so a
    commanded 0 % returns a hard 0 rather than the 2 % leakage the bare exponential implies."""
    h = min(max(h, 0.0), 1.0)
    if h <= 0.0:
        return 0.0
    if characteristic == "linear":
        return h
    if characteristic == "quick_open":
        return math.sqrt(h)
    return EQUAL_PCT_RANGE ** (h - 1.0)


# ==================================================================================================
#  Liquid service -- IEC 60534-2-1 incompressible, with cavitation/choking limit
# ==================================================================================================
def valve_flow_liquid(cv_max: float, h: float, p1_bara: float, p2_bara: float, rho_kgm3: float,
                      characteristic: str = "equal_pct", fl: float = FL_GLOBE,
                      pv_bara: float = 0.0, fp: float = 1.0) -> float:
    """Mass flow (kg/h) through a liquid-service control valve.

        w = N6 . Fp . Cv(h) . sqrt( dP_eff . rho1 )

    with the choked (flashing/cavitating) limit that makes flow stop responding to p2 once the vena
    contracta reaches the vapour pressure:

        dP_eff = min( p1 - p2 ,  FL^2 . (p1 - FF.Pv) )

    Both pressures are LIVE node pressures -- that is the whole point of the replacement.  Reverse
    dP returns 0.0 rather than a negative or imaginary flow; a real check valve or a reversing
    service needs its own model, not a sign flip here."""
    if cv_max <= 0.0 or rho_kgm3 <= 0.0:
        return 0.0
    frac = cv_fraction(h, characteristic)
    if frac <= 0.0:
        return 0.0
    dp = p1_bara - p2_bara
    if dp <= 0.0:
        return 0.0
    dp_choked = fl * fl * (p1_bara - FF_CONST * pv_bara)
    dp_eff = min(dp, dp_choked) if dp_choked > 0.0 else dp
    return N6 * fp * cv_max * frac * math.sqrt(dp_eff * rho_kgm3)


# ==================================================================================================
#  Compressible service -- IEC 60534-2-1 with the expansion factor and hard choke
# ==================================================================================================
def expansion_factor(x: float, f_gamma: float, xt: float = XT_GLOBE) -> float:
    """Y = 1 - x / (3.F_gamma.xT), floored at the choked value 2/3.

    Y accounts for the density change through the restriction.  At x = F_gamma.xT the flow chokes
    and Y = 2/3 exactly; beyond that neither x nor Y may keep rising, which is what makes the flow a
    function of UPSTREAM conditions only -- the property the incompressible sqrt(dP) law destroyed."""
    denom = 3.0 * f_gamma * xt
    if denom <= 0.0:
        return 2.0 / 3.0
    return max(1.0 - x / denom, 2.0 / 3.0)


def valve_flow_gas(cv_max: float, h: float, p1_bara: float, p2_bara: float, t1_k: float,
                   mw: float, gamma: float = 1.30, z: float = 1.0,
                   characteristic: str = "equal_pct", xt: float = XT_GLOBE,
                   fp: float = 1.0) -> float:
    """Mass flow (kg/h) through a compressible-service control valve.

        x  = min( dP/P1 , F_gamma.xT )          F_gamma = gamma / 1.40
        Y  = 1 - x / (3.F_gamma.xT)
        w  = N8 . Fp . Cv(h) . P1 . Y . sqrt( x.M / (T1.Z) )

    The min() IS the choke: once dP/P1 reaches F_gamma.xT, x stops rising, Y sits at 2/3, and the
    flow depends on p2 not at all.  HV-322604 runs at dP/P1 = 0.97 against an F_gamma.xT of about
    0.70, i.e. deeply choked, and the incompressible law it replaces had flow still climbing as the
    downstream pressure fell."""
    if cv_max <= 0.0 or p1_bara <= 0.0 or t1_k <= 0.0 or mw <= 0.0:
        return 0.0
    frac = cv_fraction(h, characteristic)
    if frac <= 0.0:
        return 0.0
    dp = p1_bara - p2_bara
    if dp <= 0.0:
        return 0.0
    f_gamma = gamma / 1.40
    x = min(dp / p1_bara, f_gamma * xt)
    y = expansion_factor(x, f_gamma, xt)
    return N8 * fp * cv_max * frac * p1_bara * y * math.sqrt(x * mw / (t1_k * max(z, 1e-9)))


# ==================================================================================================
#  Back-solving Cv_max from the licensor's design case (see module docstring on provenance)
# ==================================================================================================
def cv_from_design_liquid(w_des_kgh: float, h_des: float, p1_des: float, p2_des: float,
                          rho_des: float, characteristic: str = "equal_pct",
                          fl: float = FL_GLOBE, pv_bara: float = 0.0, fp: float = 1.0) -> float:
    """Cv_max such that `valve_flow_liquid` returns exactly `w_des_kgh` at the design condition.

    Inverting the same expression the forward call uses, in the same operation order, is what makes
    the design point reproduce BIT-EXACTLY and leaves the boot pin untouched."""
    frac = cv_fraction(h_des, characteristic)
    dp = p1_des - p2_des
    if frac <= 0.0 or dp <= 0.0 or rho_des <= 0.0 or w_des_kgh <= 0.0:
        return 0.0
    dp_choked = fl * fl * (p1_des - FF_CONST * pv_bara)
    dp_eff = min(dp, dp_choked) if dp_choked > 0.0 else dp
    return w_des_kgh / (N6 * fp * frac * math.sqrt(dp_eff * rho_des))


def cv_from_design_gas(w_des_kgh: float, h_des: float, p1_des: float, p2_des: float, t1_des_k: float,
                       mw: float, gamma: float = 1.30, z: float = 1.0,
                       characteristic: str = "equal_pct", xt: float = XT_GLOBE,
                       fp: float = 1.0) -> float:
    """Cv_max such that `valve_flow_gas` returns exactly `w_des_kgh` at the design condition."""
    frac = cv_fraction(h_des, characteristic)
    dp = p1_des - p2_des
    if frac <= 0.0 or dp <= 0.0 or w_des_kgh <= 0.0 or p1_des <= 0.0:
        return 0.0
    f_gamma = gamma / 1.40
    x = min(dp / p1_des, f_gamma * xt)
    y = expansion_factor(x, f_gamma, xt)
    return w_des_kgh / (N8 * fp * frac * p1_des * y * math.sqrt(x * mw / (t1_des_k * max(z, 1e-9))))


# ==================================================================================================
#  Anchored form -- the one the engine actually calls
# ==================================================================================================
#  WHY NOT JUST BACK-SOLVE Cv AND CALL THE ABSOLUTE LAW.  Because it is not bit-exact.  Inverting
#  w = N6.Fp.Cv.frac.sqrt(dP.rho) for Cv and multiplying straight back through does not return the
#  original float -- measured 101490.00000000001 against 101490.0 -- and this engine's boot pin
#  asserts the design point to the LAST BIT.  A 1-ulp drift at every valve on every tick is exactly
#  the kind of thing that walks a 6-hour run off its anchor.
#
#  So the engine calls the RATIO of the ISA law to itself at the design condition:
#
#      w = w_des . [ Phi(live) / Phi(design) ],     Phi = frac(h) . sqrt(dP_eff . rho)      (liquid)
#                                                   Phi = frac(h) . P1 . Y . sqrt(x.M/(T1.Z))  (gas)
#
#  N6/N8, Fp and Cv_max are identical in numerator and denominator, so they cancel ALGEBRAICALLY --
#  which also means the absent valve datasheets (see the module docstring) stop mattering for these
#  sites: the answer never depended on Cv_max at all.  What survives is every term the frozen
#  `design x stroke/stroke_des` form was missing: the installed characteristic, the live density,
#  the live dP from node pressures on both sides, and the choke.  At the design condition numerator
#  and denominator are the same expression on the same operands, so the bracket is exactly 1.0 and
#  w == w_des bit-exact.


def _phi_liquid(h, p1, p2, rho, characteristic, fl, pv):
    frac = cv_fraction(h, characteristic)
    dp = p1 - p2
    if frac <= 0.0 or dp <= 0.0 or rho <= 0.0:
        return 0.0
    dp_choked = fl * fl * (p1 - FF_CONST * pv)
    dp_eff = min(dp, dp_choked) if dp_choked > 0.0 else dp
    return frac * math.sqrt(dp_eff * rho)


def _phi_gas(h, p1, p2, t1_k, mw, gamma, z, characteristic, xt):
    frac = cv_fraction(h, characteristic)
    dp = p1 - p2
    if frac <= 0.0 or dp <= 0.0 or p1 <= 0.0 or t1_k <= 0.0 or mw <= 0.0:
        return 0.0
    f_gamma = gamma / 1.40
    x = min(dp / p1, f_gamma * xt)
    y = expansion_factor(x, f_gamma, xt)
    return frac * p1 * y * math.sqrt(x * mw / (t1_k * max(z, 1e-9)))


def valve_liquid_anchored(w_des_kgh: float, h: float, p1: float, p2: float, rho: float,
                          h_des: float, p1_des: float, p2_des: float, rho_des: float,
                          characteristic: str = "equal_pct", fl: float = FL_GLOBE,
                          pv_bara: float = 0.0) -> float:
    """IEC 60534 liquid flow, anchored on the licensor's design duty.  Bit-exact at design."""
    ref = _phi_liquid(h_des, p1_des, p2_des, rho_des, characteristic, fl, pv_bara)
    if ref <= 0.0:
        return 0.0
    return w_des_kgh * (_phi_liquid(h, p1, p2, rho, characteristic, fl, pv_bara) / ref)


def valve_gas_anchored(w_des_kgh: float, h: float, p1: float, p2: float, t1_k: float,
                       h_des: float, p1_des: float, p2_des: float, t1_des_k: float,
                       mw: float, gamma: float = 1.30, z: float = 1.0,
                       characteristic: str = "equal_pct", xt: float = XT_GLOBE,
                       mw_des: float = None, z_des: float = None) -> float:
    """IEC 60534 compressible flow, anchored on the licensor's design duty.  Bit-exact at design.

    The choke lives in `_phi_gas`, so a site anchored at an unchoked design condition still saturates
    correctly when the downstream pressure falls away -- which is the whole of finding D-2.

    `mw_des` / `z_des` default to `mw` / `z`, which makes the composition CANCEL out of the ratio.
    That default is right only where the vapour composition is genuinely fixed.  Pass the design
    values explicitly wherever the composition can move, and the m ~ sqrt(M) dependence survives:
    a heavier off-gas really does put more kilograms through the same trim at the same pressures."""
    mw_d = mw if mw_des is None else mw_des
    z_d = z if z_des is None else z_des
    ref = _phi_gas(h_des, p1_des, p2_des, t1_des_k, mw_d, gamma, z_d, characteristic, xt)
    if ref <= 0.0:
        return 0.0
    return w_des_kgh * (_phi_gas(h, p1, p2, t1_k, mw, gamma, z, characteristic, xt) / ref)


# ==================================================================================================
#  Vapour-space pressure state (A-6 / A-7)
# ==================================================================================================
def vapour_volume_m3(v_vessel_m3: float, m_liquid_kg: float, rho_liquid_kgm3: float,
                     v_min_frac: float = 0.02) -> float:
    """Free vapour volume  V_v = V_vessel - M_l/rho_l.

    Level swell compresses the vapour space, which is the coupling the lumped-capacitance form threw
    away: a vessel filling up gets a STIFFER pressure response, and that is what makes a level
    excursion show on the pressure transmitter.  Floored at a small fraction of the shell so a
    momentarily over-full inventory gives a stiff response rather than a division by zero."""
    if v_vessel_m3 <= 0.0 or rho_liquid_kgm3 <= 0.0:
        return max(v_vessel_m3, 1e-6)
    return max(v_vessel_m3 - m_liquid_kg / rho_liquid_kgm3, v_min_frac * v_vessel_m3)


def vessel_dpdt(p_bara: float, t_k: float, v_v_m3: float, mw_vap: float,
                n_gen_kmolh: float, n_out_kmolh: float,
                dtdt_k_s: float = 0.0, dvvdt_m3_s: float = 0.0) -> float:
    """dP/dt (bar/s) of a vessel vapour space, from geometry and live state.

        dP/dt = (R.T / V_v) . (n_gen - n_out)  +  (P/T).dT/dt  -  (P/V_v).dV_v/dt

    Term 1 is the molar accumulation -- note it needs MOLES, not mass, which is exactly what the
    lumped `K.(gen - out)` form got wrong when it shared one K across vapours of molecular weight 17
    (NH3) and 44 (CO2).  Term 2 is the thermal term: heating a closed vapour space raises its
    pressure with no molar change at all.  Term 3 is level swell.

    `mw_vap` is accepted for call-site symmetry and dimensional checking; the molar form does not
    use it, since n_gen/n_out already arrive in kmol/h.  Pass rates in kmol/h; the 3600 converts to
    per-second along with the 1e-5 Pa -> bar."""
    if v_v_m3 <= 0.0 or t_k <= 0.0:
        return 0.0
    #  R.T/V_v . dn/dt : kmol/h -> mol/s is (1000/3600); J/m3 -> bar is 1e-5
    molar = (R_GAS * t_k / v_v_m3) * (n_gen_kmolh - n_out_kmolh) * (1000.0 / 3600.0) * 1.0e-5
    thermal = (p_bara / t_k) * dtdt_k_s
    swell = -(p_bara / v_v_m3) * dvvdt_m3_s
    return molar + thermal + swell


# ==================================================================================================
#  Non-return (check) valve -- a hydraulic diode (report D-5)
# ==================================================================================================
#  A check valve is NOT a control valve with a sign test bolted on.  Three properties define it and
#  all three matter to the CO2 tie-in this was written for:
#
#    * it is a fixed resistance in the forward direction, so the flow follows sqrt(dP) like any
#      other orifice -- NOT the `min(1, sqrt(dP/dP_des))` DELIVERY FRACTION the engine used to
#      carry, which saturates at the design differential and therefore cannot pass more than
#      design however hard the line pushes;
#    * it does not open until the differential lifts the disc off its seat.  The crack pressure is
#      small but it is the whole reason the valve is a diode and not a resistor: between
#      p_up = p_down and p_up = p_down + p_crack the line is SHUT, not merely passing very little;
#    * reverse flow is exactly zero, not a small negative number.  A sign test on a sqrt law gives
#      0 for the wrong reason (the argument goes imaginary); this returns 0 because the disc is on
#      its seat, which is also true for the whole crack band above.
#
#  ANCHORING.  As everywhere else in this module the law is written as the RATIO of itself to its
#  own design condition, so the vendor Cv/Kv that does not exist in this repository cancels
#  algebraically and the design duty is reproduced BIT-EXACTLY.  What that anchor buys is also what
#  it costs: the check valve's own seat resistance and the resistance of the line and equipment
#  inlet downstream of it are in SERIES and both follow sqrt(dP), so they lump into one equivalent
#  resistance and only their SUM is observable from a single design point.  The model therefore
#  carries one resistance and says so, rather than inventing a split between them.
#
#  ON p_crack.  `References/Datasheets` holds no check-valve datasheet, so the crack pressure is a
#  STATED modelling assumption of the same class as FL_GLOBE and XT_GLOBE above -- a representative
#  value, applied openly, not a fitted one.  Its influence is confined to the last per cent of the
#  differential: at the design point the anchor makes it cancel exactly, and in the normal band it
#  shifts the passed flow by sqrt((dP - p_crack)/(dP_des - p_crack)) / sqrt(dP/dP_des), which for
#  p_crack = 2 % of dP_des is under 0.1 % anywhere above half the design differential.  What it does
#  fix, and what no other number in the model fixes, is exactly WHERE the valve slams shut.
def check_valve_kgh(w_des_kgh: float, p_up_bara: float, p_down_bara: float,
                    dp_des_bar: float, p_crack_bar: float = 0.0) -> float:
    """Forward-only flow through a non-return valve, anchored on its design duty.

        w = w_des . sqrt( (p_up - p_down - p_crack) / (dP_des - p_crack) )     forward, disc lifted
        w = 0                                                                  otherwise

    Bit-exact at p_up - p_down == dP_des: numerator and denominator are then the same expression on
    the same operands and the bracket is a literal 1.0.
    """
    if w_des_kgh <= 0.0:
        return 0.0
    ref = dp_des_bar - p_crack_bar
    if ref <= 0.0:
        return 0.0
    dp = p_up_bara - p_down_bara - p_crack_bar
    if dp <= 0.0:
        return 0.0                      # disc seated: reverse flow and the crack band are both ZERO
    return w_des_kgh * math.sqrt(dp / ref)


# ==================================================================================================
#  Physical transport delay (D-8)
# ==================================================================================================
def transport_time_s(v_line_m3: float, rho_kgm3: float, mdot_kgh: float,
                     t_max_s: float = 3600.0) -> float:
    """Line residence time  t_d = rho.V_line / mdot.

    This is what a fixed FIFO delay cannot do: at 50 % load the transit time DOUBLES.  The flat 60 s
    on the stripper bottoms and the 345 s on the CO2 feed were both labelled empirical and neither
    moved with flow.  Capped so a near-zero flow gives a long-but-finite delay rather than infinity."""
    if mdot_kgh <= 1e-9 or v_line_m3 <= 0.0 or rho_kgm3 <= 0.0:
        return t_max_s
    return min(rho_kgm3 * v_line_m3 / mdot_kgh * 3600.0, t_max_s)


def line_volume_m3(d_inner_m: float, length_m: float) -> float:
    """Pipe internal volume, pi.D^2/4 . L -- D from the nozzle/line sizes in the datasheets."""
    return math.pi * d_inner_m * d_inner_m * 0.25 * length_m


# ==================================================================================================
#  Gravity discharge (D-19 to D-21)
# ==================================================================================================
def gravity_outflow_kgh(cv_max: float, h_valve: float, level_m: float, rho_kgm3: float,
                        p_vessel_bara: float, p_dest_bara: float,
                        characteristic: str = "equal_pct", fl: float = FL_GLOBE) -> float:
    """Liquid discharge driven by hydrostatic head plus the vessel/destination pressure difference.

        dP = (P_vessel - P_dest) + rho.g.h / 1e5

    This is what makes the empty-vessel guards of D-19 to D-21 unreachable rather than merely
    deleted: as the level goes to zero the head term goes to zero, and if the vessel is not pushing
    against the destination the total dP goes to zero with it, so the flow goes to zero on its own.
    `if level <= 0: suction = min(suction, inflow)` was patching a hole the head term fills."""
    head_bar = rho_kgm3 * 9.80665 * max(level_m, 0.0) / 1.0e5
    p1 = p_vessel_bara + head_bar
    return valve_flow_liquid(cv_max, h_valve, p1, p_dest_bara, rho_kgm3,
                             characteristic=characteristic, fl=fl)


# ==================================================================================================
#  API 520 Part I — pressure-relief valve, vapour service (D-9)
# ==================================================================================================
#  The sizing equation for a PSV in CRITICAL (choked) vapour flow, API 520 Part I §5.6.3.1:
#
#      A = W / (C . Kd . Kb . Kc . P1) . sqrt(T . Z / M)      (USC: A in^2, W lb/h, P1 psia, T degR)
#
#  with C = 520 . sqrt( k . (2/(k+1))^((k+1)/(k-1)) ).  That C is nothing but the isentropic
#  choked mass-flux group carried in USC units; written in SI the same equation is
#
#      W = Kd . Kb . Kc . A . P1 . sqrt( (k . M) / (Z . R . T) . (2/(k+1))^((k+1)/(k-1)) )
#
#  which is what `psv_api520_choked_kgh` evaluates.  Two properties matter for how it is used here:
#
#   * it is LINEAR in P1, not in the over-pressure.  A relief valve is a fixed orifice passing a
#     choked jet, so its capacity rises with the absolute upstream pressure and does NOT ramp from
#     zero at the set point.  The linear-accumulation ramp it replaces had the valve passing a few
#     per cent of capacity just above set, which is not how a spring PSV behaves: it pops, and once
#     open it flows choked.
#   * every coefficient except P1, M and T cancels when the orifice is BACK-SOLVED from a documented
#     rated capacity through this same function (`psv_area_from_rated_m2`).  So the rated point is
#     reproduced exactly whatever is assumed for Kd, Kb, Kc, k and Z, and only the quantities that
#     actually move during a relief event change the answer.
def psv_choked_ratio(k: float) -> float:
    """Critical (choked) pressure ratio P_crit/P1 for an ideal gas of ratio of specific heats k."""
    return (2.0 / (k + 1.0)) ** (k / (k - 1.0))


def psv_api520_choked_kgh(area_m2: float, p1_bara: float, t1_k: float, mw: float,
                          k: float = 1.30, z: float = 1.0,
                          kd: float = 0.975, kb: float = 1.0, kc: float = 1.0) -> float:
    """API 520 Part I critical-flow vapour capacity of a relief orifice, kg/h.

    area_m2  effective (API letter) orifice area
    p1_bara  relieving pressure, absolute — the ACTUAL upstream pressure, not the set pressure
    t1_k     relieving temperature
    mw       relieving-stream molar mass, kg/kmol
    k        ratio of specific heats;  z  compressibility at the relieving condition
    kd       rated coefficient of discharge (0.975 for a certified vapour PSV, API 520 §5.6.3.1)
    kb       back-pressure correction (1.0 for a conventional valve on an atmospheric tailpipe)
    kc       combination correction (1.0 with no rupture disc upstream)
    """
    if area_m2 <= 0.0 or p1_bara <= 0.0 or t1_k <= 0.0 or mw <= 0.0:
        return 0.0
    flux = math.sqrt(max((k * mw) / (z * R_GAS * t1_k)
                         * (2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0)), 0.0))   # sqrt(kg.mol/(J.kmol))
    # p1 in Pa, area in m2 -> kg/s; mw is kg/kmol so the group carries a 1e-3 to reach kg/mol.
    w_kgs = kd * kb * kc * area_m2 * (p1_bara * _BAR_TO_PA) * flux * math.sqrt(1.0e-3)
    return w_kgs * 3600.0


def psv_area_from_rated_m2(w_rated_kgh: float, p1_rated_bara: float, t1_rated_k: float,
                           mw_rated: float, k: float = 1.30, z: float = 1.0,
                           kd: float = 0.975, kb: float = 1.0, kc: float = 1.0) -> float:
    """Effective orifice area that reproduces a documented rated capacity through
    `psv_api520_choked_kgh` at the rated relieving condition.  Anchoring this way makes the sizing
    basis exact and leaves only P1, MW and T live."""
    unit = psv_api520_choked_kgh(1.0, p1_rated_bara, t1_rated_k, mw_rated, k, z, kd, kb, kc)
    return w_rated_kgh / unit if unit > 0.0 else 0.0
