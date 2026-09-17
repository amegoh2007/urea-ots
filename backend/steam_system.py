"""Steam-system dynamics — quarantined utility module (Unit 329 steam network).

Zero dependency on main.py / reactor.py / controllers.py.

FOUR pressure levels (Stamicarbon CO2-stripping OTS, Unit 329), lumped-capacitance
headers integrated by explicit Euler at the host dt:

    BL supply  25.0 bar a : stream 901 from 320E006 (battery limit, held boundary).
                            Splits -> 902 (329D005), 903 (329D009), 963 (322D001A/B),
                            911 (328C003 hydrolyzer, downstream-only sink).
    HP saturator 19.7 bar a (329D005, P_MP field) : 902 in -> HP stripper 322E001 shell.
    MP drum       9.0 bar a (329D009, P_9 field)  : 903 in -> 9-bar header + PV-329205B
                            let-down to the 4-bar header (split-range PIC-329205).
    LP drums      4.4 bar a (322D001A/B, P_LP)    : HPCC 322E002 steam-raising + 9->4
                            let-down + 963 in -> 4-bar header (master-SP PIC-329207A/B/C).

Valve flows are IEC 60534-2-1 / ISA-75.01 COMPRESSIBLE (report D-2).  They used to be the
incompressible orifice law

    m_dot = K * (valve%/100) * sqrt(max(P_up - P_down, 0))                      [kg/s]

which is wrong on saturated steam and wrong in a way that matters here: four of these eight
valves are CHOKED at their own design point -- HV-329601 vents 9 bar a to atmosphere, PV-329207A
vents 5.01, and PV-329207C / HV-329602 both drop 25 -> 5.01, all at pressure ratios above the
critical F_gamma.xT of 0.696 -- and under the sqrt(dP) law their flow kept climbing as the
downstream pressure fell, without limit.  A choked valve passes a flow that is a function of
UPSTREAM conditions ONLY.  `_valve_flow` now applies the ISA expansion factor and the hard choke
through `hydraulics._phi_gas`, ANCHORED on each valve's own design node pressures so every K
seeding below and every design flow it was sized to reproduce are preserved bit-exactly.

Header pressure is a lumped capacitance C [ (kg/s) per bar ]:

    dP/dt = (sum m_in - sum m_out) / C                                        [bar/s]

Desuperheating water on a let-down (attemperator to saturated downstream):

    m_water = m_ld * (h_g_up - h_g_dn) / (h_g_dn - h_w)

BIT-EXACT DESIGN ANCHOR
    The plant H&MB couples to this module ONLY through the two saturation temperatures
    Tsat(P_MP) -> HP-stripper reboiler and Tsat(P_LP) -> HPCC shell.  P_MP and P_LP are
    held at their design saturation pressures (19.7 / 4.4 bar a) by the HP supply seed and
    the LP header PIC, so the published plant H&MB (stripper duty, reactor, urea%) is
    unchanged.  The 25-bar supply boundary and the 9-bar drum are additive faithful
    structure; the internal steam flow telemetry (m_supply, m_ld, ...) is the true
    PFD-26 conserved split, which reduces the earlier lumped 2-node stand-in.
"""
from dataclasses import dataclass, field

import hydraulics                    # PHASE 2 report D-2: ISA-75.01 compressible valve law
from iapws_if97 import tsat_c, v_vapour_sat_m3kg   # shared pure-water saturation line + sat vapour v
from iapws_if97 import rho_liquid_sat_kgm3          # saturated condensate density at a drum's own P

P_TRIPLE_BARA = 0.00611657                          # water triple point: IF97's saturation line starts here


def _rho_drum_liquid(p_bara: float) -> float:
    """Saturated condensate density at a drum pressure, held at the triple point below it.

    A tripped plant can pull a header under 6.1 mbar a (test_ccw_loss_chain's post-trip leg does),
    where there is no saturated liquid for IF97 to describe and `psat` raises OutOfRange.  The
    drum's water is then subcooled at ~1000 kg/m3, which the triple-point value (999.8) is."""
    return rho_liquid_sat_kgm3(tsat_c(max(p_bara, P_TRIPLE_BARA)))

# ---------------------------------------------------------------- saturated-steam enthalpies (kJ/kg)
#   Standard IAPWS/IF97 saturation table (sourced), used only for let-down desuperheat trims.
H_G_SUP = 2801.0    # h_g, 25 bar a supply steam (stream 901)
H_G_HP  = 2798.0    # h_g, 19.7 bar a (329D005 saturated)
H_G_MP  = 2773.0    # h_g, 9.0 bar a  (329D009 saturated)
H_G_LP  = 2743.0    # h_g, 4.4 bar a  (322D001A/B saturated)
H_F_MP  = 742.0     # h_f, 9.0 bar a saturated condensate
H_W     = 419.0     # h_f desuperheat condensate (~100 C, BFW)
# back-compat aliases (legacy 2-node names still referenced by external probes)
H_MP = H_G_HP
H_LP = H_G_LP

# ---------------------------------------------------------------- boundary + node design pressures (bar a)
P_SUP_BARA = 25.0   # BL 25-bar supply header (stream 901 from 320E006), held boundary
P_HP_BARA  = 19.7   # 329D005 HP saturator design (== STRIP_STEAM_P_BARA)  -> P_MP field
P_MP_BARA  = 9.0    # 329D009 MP drum design (Tsat ~= 175 C per mapping -> 9 bar a)
P_LP_BARA  = 5.01325  # 4.0 barg == 5.01325 bar a (322D001A/B LP drums design pressure)
P_TURBINE_OUT_BARA = 3.9  # PFD stream 932 downstream pressure at turbine 320MT02

# ---------------------------------------------------------------- valve flow coeffs [ (kg/s)/sqrt(bar) ]
#   Seeded so the design stream split (PFD-26) is reproduced at the design node pressures.
K_902 = (39400.0 / 1850.0) / (0.50 * (P_SUP_BARA - P_HP_BARA) ** 0.5)  # PV-329204 BL(25)->329D005: sized so a 50% design opening passes the HP-stripper draw (STRIP_DUTY_DES_KW 39400 / lambda_MP 1850 = 21.297 kg/s) at 25->19.7 bar  (~18.50)
# PFD-26 stream 903 is a real 1,754 kg/h make-up flow at the design point.
# Size PV-329205A for a 50 % design opening at 25 -> 9 bar.
M_903_DES = 1754.0 / 3600.0
PV205A_BIAS_PCT = 50.0
K_903 = M_903_DES / ((PV205A_BIAS_PCT / 100.0) * (P_SUP_BARA - P_MP_BARA) ** 0.5)
K_963 = 2.0         # PV-329207C : BL(25) -> 4-bar header auto make-up (PIC-329207C, design shut)
K_HV602 = 2.0       # HV-329602  : BL(25) -> 4-bar header HAND valve (HIC-329602 only; parallel to PV-329207C, design shut)
K_LD9 = 2.0         # PV-329205B  : 329D009 (9) -> 4-bar header let-down (split-range vent)

# ---------------------------------------------------------------- header capacitance ( (kg/s)/bar )
#   Physical lumped capacitance C = V * (drho_sat/dP).  V from datasheet/mapping (329D005 13.0 m3,
#   329D009 8.16 m3); drho/dP from the PFD-26 process densities (25:9.48, 19.7:7.4, 9:3.37, 4.4:2.37
#   kg/m3).  The HP/LP capacitances are held at the calibrated lumped value that pins the existing
#   HP-stripper/HPCC transient (design fixed point is C-independent); the 9-bar node is derived.
#  PHASE 5b, reports D-14 / D-15.  These were `C_MP = C_LP = 25.0` ("lumped, calibrated", the same
#  number for two different headers) and `C_9 = 8.16 * 0.2174 * 30.0` -- a derived capacitance
#  multiplied by a stated x30 "lumping factor".  The factor was there to keep the node Euler-stable
#  at the host dt, which is a property of the INTEGRATOR, not of the drum; the fix is therefore a
#  stable integration (see the semi-implicit step in `step`), not a fictitious volume.
#
#  Each capacitance is V_vapour * drho_sat/dP, with drho/dP from IAPWS-IF97 on the saturation line
#  at that header's own pressure and V_vapour from the as-built vendor drawings.  The three drums
#  are set out in DRUM GEOMETRY below, which the level spans read as well -- one description of the
#  vessel serving both the vapour side and the liquid side, rather than two that can drift apart.
#
#  What this changes against the constants: the LP value is VINDICATED IN ORDER OF MAGNITUDE (two
#  3.47 m drums, and they run a fifth full, not half) while the MP header is ~7x and the 9-bar drum
#  ~27x stiffer than the constants claimed.


def _rho_vapour_sat(p_bara: float) -> float:
    """Saturated-steam density [kg/m3] at a header pressure, IAPWS-IF97."""
    return 1.0 / v_vapour_sat_m3kg(tsat_c(p_bara))


def _header_capacitance(v_vapour_m3: float, p_bara: float, dp: float = 0.5) -> float:
    """dm/dP of a saturated vapour space [kg/bar] -- the physical meaning of the old constants."""
    return v_vapour_m3 * (_rho_vapour_sat(p_bara + dp) - _rho_vapour_sat(p_bara - dp)) / (2.0 * dp)


# ---------------------------------------------------------------- DRUM GEOMETRY (vendor as-built)
#  Sources, all read from the vendor archive and visually verified on the scans:
#
#  322D001A/B  LP steam drums, QUANTITY 2, VERTICAL       UD-AU-322-EC-0009 p2 (DDS)
#      ID 3470 mm, cyl. height (t.l./t.l.) 5300 mm, 2:1 ellipsoidal heads, rho_liq 919.36 kg/m3.
#      As-built GA UD-AU-322-DZ-0009-006 rev 05 prints NLL 1050 mm above the bottom tangent line
#      and the LICA-329504 tappings N8B / N8A at 300 mm and 1800 mm above it -- so the level
#      transmitter spans 1500 mm, both taps are in the cylindrical shell, and NLL sits at EXACTLY
#      mid-span, which is the drawing confirming the model's 50 % design level rather than the
#      model assuming it.  The same GA's design block states CAPACITY 62 m3; the geometry built up
#      here gives 61.06 m3 and the DDS hydrostatic-test weight (80 065 - 19 065 = 61 000 kg of cold
#      water) gives 61.0 m3.  Three independent numbers agreeing to 1.5 % also settle the head
#      shape: torispherical heads would give 58.5 m3 and miss all three.
#
#  329D005  HP steam saturator, QUANTITY 1, HORIZONTAL    DDS p2 (References/Datasheets/329D005)
#      ID 1760 mm x 5000 mm.  As-built GA UD-AU-329-DZ-0001-005 rev 02 states CAPACITY 13.8 m3
#      (the DDS "nominal volume" 13.00 m3 is the design figure; the hydrostatic-test weight
#      21 725 - 7 820 = 13 905 kg agrees with the as-built one) and draws NLL on the shell axis.
#
#  329D009  MP steam drum, QUANTITY 1, HORIZONTAL         DDS p2 (References/Datasheets/329D009)
#      ID 1776 mm x 2600 mm.  As-built GA UD-AU-329-DZ-0003-005 rev 04 carries the manufacturer's
#      nameplate, shell-side Volume 8 m3, and draws NLL on the shell axis.
#
#  So the "each drum runs half full" assumption that stood here is a DATUM for the two horizontal
#  drums -- both GAs put the NLL flag on the axis -- and was WRONG for the vertical LP drums, which
#  carry 1.05 m of water in a 5.3 m shell.  Their vapour space is 45.7 m3 per drum, not 25.1.
A_D001_M2      = 0.78539816 * 3.470 ** 2              # m2, 322D001 cross-section (constant over the span)
V_D001_HEAD_M3 = 3.14159265 * 3.470 ** 3 / 24.0       # m3, one 2:1 ellipsoidal head (pi.D^3/24)
V_D001_M3      = A_D001_M2 * 5.300 + 2.0 * V_D001_HEAD_M3     # 61.06 m3 per drum (as-built 62)
N_D001         = 2                                    # -, drums on the one lumped LP node
D001_NLL_M     = 1.050                                # m, normal liquid level above bottom t.l. (GA)
RHO_D001_L     = 919.36                               # kg/m3, DDS line 8 (was 917.0)

V_D001_VAP_M3 = N_D001 * (V_D001_M3 - (V_D001_HEAD_M3 + A_D001_M2 * D001_NLL_M))
V_D005_VAP_M3 = 0.50 * 13.80    # m3, NLL on the axis of a 13.8 m3 horizontal shell (GA)
V_D009_VAP_M3 = 0.50 * 8.00     # m3, NLL on the axis of an 8 m3 horizontal shell (nameplate)

C_MP = _header_capacitance(V_D005_VAP_M3, P_HP_BARA)    # ~3.4 kg/bar (was 25.0)
C_LP = _header_capacitance(V_D001_VAP_M3, P_LP_BARA)    # ~46 kg/bar  (was 25.0)
C_9  = _header_capacitance(V_D009_VAP_M3, P_MP_BARA)    # ~2.0 kg/bar (was 53.2)

# ---------------------------------------------------------------- LP header floor (site LP-main tie-in)
#   Make-up import holds the header when local generation (HPCC steam raising + 9->4 let-down)
#   collapses -- e.g. a CO2-feed cut zeroes the carbamate condensation duty.  Set just below design
#   so it only acts on a genuine deficit; the design steady state is untouched.
P_LP_MIN_BARA = 3.5

# ---------------------------------------------------------------- LP 4-bar header pressure PIC (PI vent/make-up)
#   Lumped stand-in for the master-SP trio PIC-329207A (vent) / B (turbine 320MT02) / C (BL admit):
#   a PI vent(+)/make-up(-) flow that drives the header to setpoint.
P_LP_SP_BARA = 5.01325  # 4.0 barg == 5.01325 bar a (PIC-329207 master SP)
K_PIC_LP     = 8.0      # proportional vent/make-up gain   [ (kg/s)/bar ]
KI_PIC_LP    = 0.4      # integral vent/make-up gain        [ (kg/s)/(bar.s) ]
M_PIC_CLAMP  = 10.0     # anti-windup clamp on the integral contribution [ kg/s ]

# ---------------------------------------------------------------- MASTER-SP trio PIC-329207A/B/C
#   The lumped LP PIC above resolves into three staggered sub-controllers on the 4-bar header.
#   MASTER ON : user sets one master SP; the trio fans out and locks to it --
#       PIC-329207A (vent PV-329207A, atm)          SP = master + DB_LP   (highest -> opens first on over-P)
#       PIC-329207B (turbine 320MT02 export)        SP = master            (== header master)
#       PIC-329207C (BL 25-bar admit PV-329207C)    SP = master - DB_LP   (lowest  -> opens first on under-P)
#   MASTER OFF: the three loops are independent (operator sets each SP / mode / MAN opening).
#   At design P_LP=4.400 (master 4.4 -> SP_A=4.5/SP_B=4.4/SP_C=4.3): eA=-0.1 & eC=-0.1 floor the
#   one-sided A/C integrals at 0 so the vent PV-329207A and BL-admit PV-329207C stay shut; leg B has
#   eB=0 so it holds its anchored bias (BIAS_207B_PCT), exporting M_TURBINE_DES to the turbine.  The
#   header balances at 4.4 bar because design generation == M_USERS_LP + M_TURBINE_DES (G8), so P_LP
#   and the Tsat(P_LP) coupling to the HPCC are bit-for-bit unchanged.
DB_LP      = 0.1        # bar, master-SP stagger: A=SP+DB_LP (vent) / C=SP-DB_LP (make-up)
K_207A     = 3.0        # PV-329207A vent valve coeff  (P_LP -> atm)          [ (kg/s)/sqrt(bar) ]
# G8: PV-329207B carries the DESIGN 4-bar surplus to turbine 320MT02 (PFD-26 stream 932 = 16 707 kg/h).
#   Anchored-bias idiom (same as PV-329204 / PV-329205A): at design P_LP=4.4 the leg-B error is zero,
#   so the valve sits at BIAS_207B_PCT and passes exactly M_TURBINE_DES; K_207B is sized so that bias
#   opening delivers the design export at the design differential (4.4 -> 3.9 bar). This makes
#   FT-329407 read its PFD design value from the connected valve (not a shut-valve synthesis) while
#   the header still balances at 4.4 bar bit-exact (see M_USERS_LP below).
M_TURBINE_DES = 16707.0 / 3600.0   # kg/s, PFD-26 stream 932 turbine 320MT02 export at design (4.64083)
BIAS_207B_PCT = 50.0               # design-seed PV-329207B opening (anchored bias; eB==0 at design)
K_207B     = M_TURBINE_DES / ((BIAS_207B_PCT / 100.0) * (P_LP_BARA - P_TURBINE_OUT_BARA) ** 0.5)  # ~13.128
K_PIC_207  = 24.0      # sub-controller proportional gain                    [ %/bar ]  (retuned 4->24: LP header PIC-329207A/B/C were sluggish on master-SP steps -- now reaches SP in ~2 min with NO overshoot; probe shows peak==final up to K=34, so ample stability margin at the sim dt)
KI_PIC_207 = 0.28      # sub-controller integral gain                        [ %/(bar.s) ]  (retuned 0.0267->0.28 with K; design pin bit-exact since eB=0 -> pv sits at bias regardless of gain)
I207_CLAMP = 100.0 / KI_PIC_207   # one-sided integral clamp (integral term <= 100 %)

# ---------------------------------------------------------------- 9-bar header PIC (split-range PIC-329205)
#   329D009 held at SP by a split-range controller:
#     P_9 > SP: PV-329205A closes (BL admit -> 0), then PV-329205B opens (vent excess to 4-bar).
#     P_9 < SP: PV-329205B closes (let-down -> 0), then PV-329205A opens (admit BL steam).
#   Proportional split about SP with a small dead-band; both legs ~0 at SP -> design-preserving.
P_9_SP_BARA = 9.0
K_PIC_9     = 40.0     # split gain: % valve travel per bar error
DB_9        = 0.02     # bar dead-band about SP (both legs shut inside)

# ---------------------------------------------------------------- HP-saturator PIC (PIC-329204)
#   329D005 (P_MP, 19.7 bar a) held at SP by direct-acting PI on the BL supply valve PV-329204:
#     P_MP < SP -> open PV-329204 (admit more 25-bar steam) ; P_MP > SP -> close it.
#   Bias-anchored on the design seed opening (_seed_supply_pct, ~50 %): at design P_MP=SP the
#   error and integral are both 0, so the valve holds the seed exactly and the pinned fixed point
#   is bit-for-bit unchanged.  Gains are controller tuning (not physical constants) -> Sourcing Law
#   clean.  step_steam is gated OFF during the boot-pin settle, so this loop cannot perturb any
#   design-pinned constant.
P_HP_SP_BARA = P_HP_BARA   # 19.7 bar a design SP for the HP saturator
K_PIC_204    = 1.8        # proportional gain [ %/bar ]  (under-P opens supply)
KI_PIC_204   = 0.018000000000000002         # integral gain     [ %/(bar.s) ]
I204_CLAMP   = 50.0 / KI_PIC_204   # two-sided integral clamp (integral term within +/-50 %)

# ---------------------------------------------------------------- design throughputs (probe / seed)
M_STRIP_DES = 39400.0 / 1850.0   # kg/s (21.297), design MP steam consumed by HP-stripper reboiler == STRIP_DUTY_DES_KW / lambda_MP (main.py design duty; MP header consume is design-pinned constant)
M_HPCC_DES  = 3.0      # kg/s, design LP steam raised in the HP carbamate condenser

# ---------------------------------------------------------------- LP 4-bar consumer boundary (G8)
#   M_USERS_LP is the aggregate 4-bar H.Ex user draw (322D001 mapping section C consumers: 323E002/
#   323E010/324E001/324F002/F004/F005/328C004/melt-line/tracing/storage/granulation), per PFD-26
#   until each is wired as its own live edge.  The turbine 320MT02 export is now a SEPARATE connected
#   edge (M_TURBINE_DES via PV-329207B), no longer folded into this aggregate.  Design closure:
#       generation (HPCC steam-raising) = M_USERS_LP + M_TURBINE_DES + vent(0)
#   so at runtime main.py's boot sets M_USERS_LP = m_hpcc_des - M_TURBINE_DES (the users get the
#   generation NOT exported to the turbine), the header holds 4.4 bar bit-exact, and FT-329407 reads
#   the design 16 707 kg/h from the connected valve.  The module default below is only the standalone
#   probe placeholder (main.py overrides it at boot from the live design HPCC duty).
M_USERS_LP = M_HPCC_DES

# ---------------------------------------------------------------- 9-bar flash source and consumers
# PFD-26 closes the design 329D009 vapour node directly:
#   stream 907 (9-bar header) = 6,687 kg/h
#   stream 903 (25-bar make-up) = 1,754 kg/h
# Stream 904 splits strictly into 905 liquid (53,331 kg/h) + 906 flash vapour (4,658 kg/h).
# A separate 275 kg/h saturation-water increment closes 903 + 906 + water = stream 907.
# Keeping those terms separate prevents saturation water from being deducted from liquid stream 904.
M_USERS_9_DES = 6687.0 / 3600.0
M_FLASH9_DES = 4658.0 / 3600.0
M_ATTEMPER9_DES = M_USERS_9_DES - M_903_DES - M_FLASH9_DES

# ---------------------------------------------------------------- drum level loops (LIC-329502/503/504)
#   Three condensate-inventory level loops, each a LOCAL mass balance (accumulation = in - out).
#   Valve openings are design-seeded at SP=50%; downstream inventories then expose any real net
#   cascade accumulation instead of dropping inter-drum transfers.  step_steam is gated OFF during the boot-pin
#   settle (_STEAM_READY=False), so these cannot perturb any design-pinned header pressure; and the
#   level states never write P_MP/P_9/P_LP (liquid inventory decoupled from the vapor-pressure ODEs).
#   Control sense (PID_No_107_1 / 329-1 mapping):
#     LIC-329502  329D005 condensate drain -> 329D009  : DIRECT  (level>SP -> open LV-329502 -> drain^)
#     LIC-329503  329D009 condensate drain -> 322D001  : DIRECT  (level>SP -> open LV-329503 -> drain^)
#     LIC-329504  322D001 make-up f. 329P001A/B pumps  : REVERSE (level>SP -> close LV-329504 -> make-up v)
#   Cascade conservation: LV-329502 carries the HP-stripper condensate return; its flash-vapour split
#   is removed before LV-329503 transfers the remaining liquid into 322D001A/B.  LV-329504 provides
#   additional condensate-pump make-up, and LP boil-off is the liquid sink.
#   Mass-per-%level  m_span = rho_liq * A_surface * span  (sets the level TIMESCALE only; NOT design-
#   pinned -- each loop is seeded so dm/dt = 0 at the design point whatever m_span is).  Datasheet
#   geometry (NSF/Uhde DDS, folder 329-1):
#     329D005 horiz ID 1.760 m x L 5.000 m, LT-329502 span 1.500 m, rho 850.25 -> ~11223 kg
#     329D009 horiz ID 1.776 m x L 2.600 m, LT-329503 span 0.750 m, rho 892.15 -> ~ 3090 kg
#     322D001 vert, TWO drums, see DRUM GEOMETRY above                          -> ~26085 kg
#
#   322D001 used to read `ID 1.600 m, LT-329504 span 2.000 m, rho 917.0 -> ~3688 kg`, and every
#   one of those four numbers was wrong.  The drums are ID 3.470 m (UD-AU-322-EC-0009 p2), there
#   are TWO of them on this one controller, the LICA-329504 taps N8B/N8A are 1.500 m apart
#   (UD-AU-322-DZ-0009-006), and the liquid is 919.36 kg/m3.  Together that is 26.1 t per full
#   span against 3.7 t -- a level loop given 7x the inventory it actually has to move, so it was
#   swinging about seven times too fast for the make-up flow driving it.  The area is the plain
#   cross-section because BOTH taps sit in the cylindrical shell (300 mm and 1800 mm above the
#   bottom tangent line), so there is no head correction anywhere in the span.
LEVEL_SP_DES = 50.0        # %, design normal liquid level (all three drums)
LV_OPEN_DES  = 50.0        # %, design-seed level-valve opening (valve flow == design draw at this opening)
LIC_KC       = 2.5         # %op per %level, velocity-form PI proportional gain (controller tuning)
LIC_TI       = 90.0        # s, velocity-form PI integral time
M_502_DES    = M_STRIP_DES    # kg/s, 329D005 condensate throughput = HP-stripper condensate return
M_503_DES    = M_502_DES - M_FLASH9_DES  # kg/s, D009 liquid draw after the 904 -> 905 + 906 split
M_504_DES    = M_HPCC_DES     # kg/s, 322D001 make-up = LP steam boil-off replaced (HPCC raising)
FLASH9_FRACTION = M_FLASH9_DES / M_502_DES  # design-anchored fraction of LV329502 transfer flashed
MSPAN_502    = 850.25 * (1.760 * 5.000) * 1.500         # kg, 329D005 horiz (mid-level chord = ID)
MSPAN_503    = 892.15 * (1.776 * 2.600) * 0.750         # kg, 329D009 horiz
LT504_SPAN_M = 1.500      # m, LICA-329504 tap separation N8B 300 -> N8A 1800 above bottom t.l.
MSPAN_504    = RHO_D001_L * (N_D001 * A_D001_M2) * LT504_SPAN_M   # kg, 322D001A+B (~26085)

#  LEVEL-VALVE HYDRAULICS (report D-16).  Each valve passes liquid between two pressures the mapping
#  names ("Mapping of the steam system.md" lines 13, 20, 28) and PFD-26 tabulates:
#     LV-329502  329D005 19.7 -> 329D009 9.0 bar a   stream 904, saturated condensate  850.84 kg/m3
#     LV-329503  329D009  9.0 -> 322D001 4.4 bar a   stream 913, saturated condensate  891.84 kg/m3
#     LV-329504  329P001A/B 9.0 -> 322D001 4.4 bar a stream 916, condensate at 100 C   958.58 kg/m3
#  The two drum-to-drum valves read both ends live and take the density of saturated liquid at the
#  upstream drum's own pressure; LV-329504's upstream is the condensate-pump discharge, which this
#  module does not simulate, so it is the PFD-26 stream-916 boundary.
P_916_BARA   = 9.0        # bar a, PFD-26 stream 916 -- 329P001A/B discharge into LV-329504
RHO_916      = 958.58     # kg/m3, PFD-26 stream 916 (100 C, subcooled: density does not follow P)
#  No level-valve datasheet exists in References/, so the trim is LINEAR -- the gain basis LIC_KC /
#  LIC_TI were tuned against when the law was `m_des . op/50`, so the terms added here are the live
#  differential and density, not a retune.  Both drum-to-drum valves pass SATURATED liquid, whose
#  vena contracta flashes; with Pv at saturation the single-phase choke would collapse dP_eff to ~4 %
#  of P1 and make them hard orifices.  They run with Pv = 0, so the FL^2.P1 ceiling applies the right
#  qualitative limit without claiming a two-phase capacity -- the same stated treatment as the three
#  328 bottoms valves, and the same open IEC 60534 two-phase gap.
LV_CHAR      = "linear"


#  Saturated steam, gamma = c_p/c_v.  1.30 is the standard value for superheated/saturated steam
#  over this pressure range and is the same one `hydraulics` defaults to; F_gamma = 1.30/1.40 =
#  0.9286, so choking begins at dP/P1 = F_gamma.xT = 0.696 for the globe trim assumed throughout.
STEAM_GAMMA = 1.30
STEAM_MW    = 18.01528      # kg/kmol, H2O


def _valve_flow(K: float, opening_pct: float, p_up: float, p_down: float,
                p_up_des: float = None, p_down_des: float = None) -> float:
    """ISA-75.01 compressible steam flow (kg/s), anchored on this valve's design node pressures.

        m_dot = K.(op/100).sqrt(dP_des) . [ Phi_gas(live) / Phi_gas(design) ]

        Phi_gas = P1 . Y . sqrt(x.M/(T1.Z)) ,   x = min(dP/P1, F_gamma.xT) ,  Y = 1 - x/(3.F_gamma.xT)

    The min() IS the choke: past x = F_gamma.xT neither x nor Y may rise, so the flow stops
    responding to p_down entirely -- which is the whole of finding D-2 and the reason four of the
    valves in this module were unbounded.  T1 is the LIVE saturation temperature of the upstream
    header, so a header that depressurises also gets hotter-per-kilogram in the right direction.

    Anchoring rather than back-solving a Cv keeps every K seeding above untouched: at the design
    node pressures the bracket is the same expression on the same operands, i.e. exactly 1.0, and
    the law returns K.(op/100).sqrt(dP_des) for ANY opening -- the identical value the
    incompressible form returned there.  Design splits and the boot pin are therefore bit-exact.
    Defaults make p_up/p_down their own design condition (a boundary-to-atmosphere vent), which is
    also exactly 1.0.
    """
    op = max(0.0, min(100.0, opening_pct))
    if op <= 0.0:
        return 0.0
    p1d = p_up   if p_up_des   is None else p_up_des
    p2d = p_down if p_down_des is None else p_down_des
    dP_des = max(p1d - p2d, 0.0)
    if dP_des <= 0.0:
        return 0.0
    ref = hydraulics._phi_gas(1.0, p1d, p2d, tsat_c(p1d) + 273.15, STEAM_MW,
                              STEAM_GAMMA, 1.0, "linear", hydraulics.XT_GLOBE)
    if ref <= 0.0:
        return 0.0
    live = hydraulics._phi_gas(1.0, p_up, p_down, tsat_c(max(p_up, 1e-6)) + 273.15, STEAM_MW,
                               STEAM_GAMMA, 1.0, "linear", hydraulics.XT_GLOBE)
    return K * (op / 100.0) * dP_des ** 0.5 * (live / ref)


def _seed_supply_pct() -> float:
    """PV-329204 opening that delivers the design stripper draw at P_SUP->P_HP."""
    dP = (P_SUP_BARA - P_HP_BARA) ** 0.5
    return min(100.0, M_STRIP_DES / (K_902 * dP) * 100.0)


_SUPPLY_BIAS = _seed_supply_pct()   # design-seed PV-329204 opening; PIC-329204 bias anchor (bit-exact fixed point)


def _level_loop(mode, sp, lvl, op, ep, dt, m_span, m_des, direct, m_ext, valve_out,
                p_up, p_dn, p_up_des, p_dn_des, rho, rho_des):
    """Advance one drum level loop; return (lvl, op, ep, m_valve).

    Velocity-form PI on the drum level, then a LOCAL mass balance (accumulation = in - out):
        e        = (lvl-sp) if direct else (sp-lvl)              # direct=drain, reverse=make-up
        op      <- clamp(op + KC*((e-ep) + dt/TI*e), 0, 100)     # AUTO only; frozen in MAN
        m_valve  = m_des . Phi(op, p_up, p_dn, rho) / Phi(LV_OPEN_DES, design)     (kg/s)
                   Phi = frac(op) . sqrt(dP_eff . rho)           # IEC 60534 liquid, report D-16
        dm       = (m_ext - m_valve) if valve_out else (m_valve - m_ext)   # in - out
        lvl     <- clamp(lvl + dm*dt/m_span*100, 0, 100)
    The valve law was `m_des * op/LV_OPEN_DES`: stroke alone, so a valve in MAN kept passing its
    design flow whatever happened to the drums on either side of it, and a let-down drum that lost
    pressure kept receiving condensate it could no longer be pushed.  ep is tracked every tick
    (incl. MAN) -> bumpless MAN->AUTO.  Seeded op==LV_OPEN_DES at the design pressures and density
    gives a bracket of exactly 1.0 -> m_valve==m_des==m_ext -> dm==0 -> level parks at SP.
    """
    e = (lvl - sp) if direct else (sp - lvl)
    if mode == "AUTO":
        op = max(0.0, min(100.0, op + LIC_KC * ((e - ep) + (dt / LIC_TI) * e)))
    ep = e
    m_valve = hydraulics.valve_liquid_anchored(
        m_des, max(0.0, min(100.0, op)) / 100.0, p_up, p_dn, rho,
        LV_OPEN_DES / 100.0, p_up_des, p_dn_des, rho_des, characteristic=LV_CHAR, pv_bara=0.0)
    dm = (m_ext - m_valve) if valve_out else (m_valve - m_ext)
    lvl = max(0.0, min(100.0, lvl + dm * dt / m_span * 100.0))
    return lvl, op, ep, m_valve


@dataclass
class SteamState:
    # --- node pressures (bar a) ---
    P_SUP: float = P_SUP_BARA       # BL 25-bar supply header (held boundary)
    P_MP:  float = P_HP_BARA        # 329D005 HP saturator 19.7 (name kept for main.py compat)
    P_9:   float = P_MP_BARA        # 329D009 MP drum 9.0
    P_LP:  float = P_LP_BARA        # 322D001A/B LP drums 4.4
    # --- valve openings (%) ---
    valve_supply_pct:  float = field(default_factory=_seed_supply_pct)   # PV-329204
    valve_admit9_pct:  float = PV205A_BIAS_PCT  # PV-329205A; 1,754 kg/h design make-up
    valve_letdown_pct: float = 0.0   # PV-329205B (9->4 let-down); split-range, design shut
    valve_963_pct:     float = 0.0   # PV-329207C (BL->4-bar); design shut
    hv_329602_pct:     float = 0.0   # HV-329602 (BL->4-bar) HAND valve; positioned ONLY by HIC-329602, loop-independent; design shut
    hv_vent_hp_pct:    float = 0.0   # HV-329601 329D005 atm vent (design shut)
    # --- last-tick flow diagnostics (kg/s) ---
    m_supply: float = 0.0            # stream 902  (BL -> 329D005)
    m_903:    float = 0.0            # stream 903  (BL -> 329D009)
    m_flash9: float = 0.0            # stream 904 flash contribution to 9-bar vapour header
    m_attemper9: float = 0.0         # saturation-water increment closing stream 907 at design
    m_users9: float = M_USERS_9_DES  # actual 9-bar users (324E003 + remaining header users)
    m_ld:     float = 0.0            # 9->4 let-down (PV-329205B)  [m_ld field kept for compat]
    m_963:    float = 0.0            # stream 963  (BL -> 4-bar header)
    m_water:  float = 0.0            # desuperheat water on the 9->4 let-down
    m_vent_hp:float = 0.0            # HV-329601 HP vent
    m_pic:    float = 0.0            # 4-bar header PIC vent(+)/make-up(-)
    i_pic:    float = 0.0            # bar.s, 4-bar PIC integral accumulator
    # --- controller mode / SP (design-neutral; defaults reproduce the fixed point bit-for-bit) ---
    pic204_mode: str = "AUTO"           # PIC-329204: AUTO=hold P_MP at SP via PV-329204; MAN=freeze supply valve
    pic204_sp:   float = P_HP_SP_BARA   # 329D005 HP-saturator SP (bar a) == 19.7
    i_204:       float = 0.0            # bar.s, PIC-329204 integral accumulator (held in MAN -> bumpless)
    pic205_mode: str = "AUTO"           # PIC-329205: AUTO=split-range; MAN=freeze split writes (operator holds 205A/205B)
    pic205_sp:   float = P_9_SP_BARA    # 9-bar drum SP (bar a)
    pic207_mode: str = "AUTO"           # PIC-329207 == leg B (turbine export): AUTO=PI; MAN=freeze valve, hold integral
    pic207_sp:   float = P_LP_SP_BARA   # 4-bar header master SP (bar a) == leg-B SP
    # --- MASTER-SP trio (leg B reuses pic207_sp / pic207_mode / i_pic / valve pv207b_pct; leg C reuses valve_963_pct) ---
    master207_on: bool  = True                  # ON=one SP fans out A=+DB/B/C=-DB & locks; OFF=3 independent loops
    master207_sp: float = P_LP_SP_BARA          # master SP (bar a); 4.4 -> B=4.4 / A=4.5 / C=4.3
    pic207a_mode: str   = "AUTO"                # PIC-329207A vent      (SP = master + DB_LP)
    pic207a_sp:   float = P_LP_SP_BARA + DB_LP
    pic207c_mode: str   = "AUTO"                # PIC-329207C BL admit  (SP = master - DB_LP)
    pic207c_sp:   float = P_LP_SP_BARA - DB_LP
    pv207a_pct:   float = 0.0                   # PV-329207A vent opening (%)
    pv207b_pct:   float = 0.0                   # PV-329207B turbine export opening (%)
    i_207a:       float = 0.0                   # PIC-329207A integral (one-sided, bar.s-scaled)
    i_207c:       float = 0.0                   # PIC-329207C integral (one-sided, bar.s-scaled)
    m_vent:       float = 0.0                   # PV-329207A vent flow (kg/s)
    m_turbine:    float = 0.0                   # PV-329207B LP-header export to turbine (kg/s)
    # --- drum level loops (LIC-329502/503/504); design-seeded -> dm/dt=0 at pin (bit-exact) ---
    lic502_mode: str   = "AUTO"          # 329D005 level (LT-329502) -> LV-329502 drain to 329D009 (direct)
    lic502_sp:   float = LEVEL_SP_DES    # level SP (%)
    lic502_lvl:  float = LEVEL_SP_DES    # 329D005 condensate level (%)
    lic502_op:   float = LV_OPEN_DES     # LV-329502 opening (%)
    lic502_ep:   float = 0.0             # velocity-PI previous error (bumpless MAN->AUTO)
    lic503_mode: str   = "AUTO"          # 329D009 level (LT-329503) -> LV-329503 drain to 322D001 (direct)
    lic503_sp:   float = LEVEL_SP_DES
    lic503_lvl:  float = LEVEL_SP_DES    # 329D009 condensate level (%)
    lic503_op:   float = LV_OPEN_DES     # LV-329503 opening (%)
    lic503_ep:   float = 0.0
    lic504_mode: str   = "AUTO"          # 322D001 level (LT-329504) -> LV-329504 make-up f.329P001 (reverse)
    lic504_sp:   float = LEVEL_SP_DES
    lic504_lvl:  float = LEVEL_SP_DES    # 322D001 water level (%)
    lic504_op:   float = LV_OPEN_DES     # LV-329504 opening (%)
    lic504_ep:   float = 0.0
    # --- last-tick node mass residuals (sum in - sum out, kg/s) ---
    mass_residual_d005_vapor:  float = 0.0
    mass_residual_d009_vapor:  float = 0.0
    mass_residual_lp_vapor:    float = 0.0
    mass_residual_d005_liquid: float = 0.0
    mass_residual_d009_liquid: float = 0.0
    mass_residual_lp_liquid:   float = 0.0


def step_steam(state: SteamState, dt: float,
               m_strip_consume: float, m_hpcc_gen: float,
               m_9_users: float = M_USERS_9_DES) -> SteamState:
    """Advance the 4-level steam network one Euler tick.

    Args:
        state            : SteamState (mutated in place and returned).
        dt               : timestep (s).
        m_strip_consume  : MP steam drawn by the HP-stripper reboiler (kg/s).
        m_hpcc_gen       : LP steam raised in the HPCC (kg/s).
        m_9_users        : total steam drawn from 329D009's 9-bar vapour header (kg/s).
    """
    # -- BL supply header held at boundary (site 25-bar main) --
    state.P_SUP = P_SUP_BARA

    # -- LV-329502 transfer must be known before the D009 flash source is evaluated. --
    # Flashing belongs to condensate that actually crosses the valve, not to upstream steam demand.
    state.lic502_lvl, state.lic502_op, state.lic502_ep, m_lv502 = _level_loop(
        state.lic502_mode, state.lic502_sp, state.lic502_lvl, state.lic502_op, state.lic502_ep,
        dt, MSPAN_502, M_502_DES, direct=True, m_ext=m_strip_consume, valve_out=True,
        p_up=state.P_MP, p_dn=state.P_9, p_up_des=P_HP_BARA, p_dn_des=P_MP_BARA,
        rho=_rho_drum_liquid(state.P_MP),
        rho_des=rho_liquid_sat_kgm3(tsat_c(P_HP_BARA)))
    m_flash9 = FLASH9_FRACTION * m_lv502

    # -- PIC-329204 HP-saturator pressure (direct PI about the seed opening: under-P -> open supply) --
    if state.pic204_mode == "AUTO":
        e204 = state.pic204_sp - state.P_MP
        state.i_204 = max(-I204_CLAMP, min(I204_CLAMP, state.i_204 + e204 * dt))
        state.valve_supply_pct = max(0.0, min(100.0,
            _SUPPLY_BIAS + K_PIC_204 * e204 + KI_PIC_204 * state.i_204))
    # MAN: valve_supply_pct frozen; i_204 held -> bumpless return to AUTO

    # -- stream 902: BL -> 329D005 HP saturator (PV-329204) --
    # D-2 design anchors: each valve's OWN design node pressures, the same pair its K above was
    # seeded at, so the compressible law returns the identical design flow.  PV-329204 25 -> 19.7,
    # dP/P1 = 0.21, comfortably sub-critical.
    m_supply = _valve_flow(K_902, state.valve_supply_pct, state.P_SUP, state.P_MP,
                           P_SUP_BARA, P_HP_BARA)
    # HV-329601 vents the 19.7 bar saturator to atmosphere: dP/P1 = 0.949 against a critical
    # 0.696, i.e. DEEPLY CHOKED at every opening.  Under the old sqrt(dP) law its flow rose
    # without bound as the header pressure climbed; it is now a function of P1 alone.
    m_vent_hp = _valve_flow(K_902, state.hv_vent_hp_pct, state.P_MP, 1.01325,
                            P_HP_BARA, 1.01325)  # HV-329601 atm

    # -- 329D009 split-range PIC-329205 about the measured design make-up bias --
    # The A valve carries stream 903 at the design point.  Rising pressure first closes A; only
    # after A reaches zero does B let excess steam down to the 4-bar header.  Falling pressure
    # opens A above its bias.  This is the physical split range described by the operating manual.
    if state.pic205_mode == "AUTO":
        err9 = state.P_9 - state.pic205_sp
        split = PV205A_BIAS_PCT - K_PIC_9 * err9
        if split >= 0.0:
            state.valve_admit9_pct = min(100.0, split)
            state.valve_letdown_pct = 0.0
        else:
            state.valve_admit9_pct = 0.0
            state.valve_letdown_pct = min(100.0, -split)
    # MAN: split-range writes frozen; operator-set 205A/205B openings persist unchanged.

    # -- stream 903: BL -> 329D009 (PV-329205A) ; 9->4 let-down (PV-329205B) --
    m_903 = _valve_flow(K_903, state.valve_admit9_pct,  state.P_SUP, state.P_9,
                        P_SUP_BARA, P_MP_BARA)     # PV-329205A 25 -> 9, dP/P1 = 0.64, just sub-critical
    m_ld9 = _valve_flow(K_LD9, state.valve_letdown_pct, state.P_9,   state.P_LP,
                        P_MP_BARA, P_LP_BARA)      # PV-329205B 9 -> 4 let-down, dP/P1 = 0.44
    m_attemper9 = M_ATTEMPER9_DES * (m_903 / max(M_903_DES, 1e-12))
    # desuperheat water bringing 9-bar let-down to saturated 4-bar
    m_water = m_ld9 * (H_G_MP - H_G_LP) / (H_G_LP - H_W)

    # -- MASTER-SP fan-out: ON stamps the staggered trio SPs and locks all three to AUTO --
    if state.master207_on:
        state.pic207a_sp   = state.master207_sp + DB_LP   # leg A vent  (opens first on over-P)
        state.pic207_sp    = state.master207_sp           # leg B == header master
        state.pic207c_sp   = state.master207_sp - DB_LP   # leg C admit (opens first on under-P)
        state.pic207a_mode = state.pic207_mode = state.pic207c_mode = "AUTO"

    # -- PIC-329207A vent (reverse-acting: P_LP > SP_A -> open PV-329207A to atm) --
    if state.pic207a_mode == "AUTO":
        eA = state.P_LP - state.pic207a_sp
        state.i_207a = max(0.0, min(I207_CLAMP, state.i_207a + eA * dt))
        state.pv207a_pct = max(0.0, min(100.0, K_PIC_207 * eA + KI_PIC_207 * state.i_207a))
    # MAN: pv207a_pct frozen; i_207a held -> bumpless return to AUTO
    # PV-329207A vents the 4-bar header to atmosphere: dP/P1 = 0.798, CHOKED.
    m_vent = _valve_flow(K_207A, state.pv207a_pct, state.P_LP, 1.01325,
                         P_LP_BARA, 1.01325)

    # -- PIC-329207B turbine 320MT02 export: biased PI holds P_LP at SP_B by trimming the design
    #    export around BIAS_207B_PCT (G8).  At design eB==0 & i_pic==0 -> valve sits at the bias and
    #    passes M_TURBINE_DES exactly; the integral is TWO-SIDED so it trims symmetrically off-design
    #    (over-P opens above bias, under-P closes below it) with no steady-state offset.
    if state.pic207_mode == "AUTO":
        eB = state.P_LP - state.pic207_sp
        state.i_pic = max(-I207_CLAMP, min(I207_CLAMP, state.i_pic + eB * dt))
        state.pv207b_pct = max(0.0, min(100.0,
            BIAS_207B_PCT + K_PIC_207 * eB + KI_PIC_207 * state.i_pic))
    # MAN: pv207b_pct frozen; i_pic held -> bumpless return to AUTO
    m_turbine = _valve_flow(K_207B, state.pv207b_pct, state.P_LP, P_TURBINE_OUT_BARA,
                            P_LP_BARA, P_TURBINE_OUT_BARA)   # PV-329207B, dP/P1 = 0.22

    # -- PIC-329207C BL 25-bar admit (direct: P_LP < SP_C -> open PV-329207C) --
    if state.pic207c_mode == "AUTO":
        eC = state.pic207c_sp - state.P_LP
        state.i_207c = max(0.0, min(I207_CLAMP, state.i_207c + eC * dt))
        state.valve_963_pct = max(0.0, min(100.0, K_PIC_207 * eC + KI_PIC_207 * state.i_207c))
    # MAN: valve_963_pct frozen; i_207c held -> bumpless return to AUTO
    # HV-329602 is a HAND valve, positioned ONLY by HIC-329602 (hv_329602_pct) -- it is NOT coupled to
    # any control loop.  The BL(25)->4-bar make-up is therefore the SUM of two independent parallel legs:
    # the PIC-329207C auto admit (PV-329207C) and the manual HV-329602.  (Previously the two were
    # MULTIPLIED in series, which both wired the hand valve into the PIC-329207C loop and -- because the
    # hand valve is design-shut at 0% -- zeroed the automatic make-up entirely.)  Both legs are 0 at the
    # design point (valve_963_pct=0 & hv_329602_pct=0) -> m_963=0 -> header balance bit-exact.
    # Both 25 -> 4-bar make-up valves sit at dP/P1 = 0.80, i.e. CHOKED whenever they are cracked
    # open.  Design-shut, so they contribute nothing at the seed either way -- but on a header
    # collapse the old law had them accelerating into the falling pressure instead of saturating.
    m_963_auto = _valve_flow(K_963,   state.valve_963_pct,  state.P_SUP, state.P_LP,
                             P_SUP_BARA, P_LP_BARA)   # PV-329207C (PIC loop)
    m_hv602    = _valve_flow(K_HV602, state.hv_329602_pct,  state.P_SUP, state.P_LP,
                             P_SUP_BARA, P_LP_BARA)   # HV-329602 (hand, HIC-329602)
    m_963 = m_963_auto + m_hv602

    # net controlled export; leg C make-up (m_963) is accounted separately in the balance
    m_pic = m_vent + m_turbine

    # -- node mass balances --
    #   329D005 (HP):  in 902 ; out stripper + HP vent
    residual_d005_vapor = m_supply - m_strip_consume - m_vent_hp
    dP_MP = residual_d005_vapor / C_MP
    #   329D009 (9-bar): in 903 + flash vapour from the HP-stripper condensate;
    #                     out actual 9-bar users + optional 9->4 let-down.
    residual_d009_vapor = m_903 + m_flash9 + m_attemper9 - m_9_users - m_ld9
    dP_9 = residual_d009_vapor / C_9
    #   322D001A/B (4-bar): in HPCC + let-down + desuperheat + 963(C); out users + A/B exports
    residual_lp_vapor = m_hpcc_gen + m_ld9 + m_water + m_963 - M_USERS_LP - m_vent - m_turbine
    dP_LP = residual_lp_vapor / C_LP

    #  SEMI-IMPLICIT, reports D-14 / D-15.  On the real capacitances above, an explicit step is
    #  unstable at the host dt -- which is exactly what the retired x30 `F_lump` was compensating
    #  for.  Every term that resists a pressure change is a valve whose flow depends on that same
    #  pressure, so the resisting conductance g = -d(residual)/dP is computable by re-evaluating the
    #  same laws one perturbation away, and the step becomes
    #
    #      (C/dt)(P' - P) = res(P) - g.(P' - P)   ->   P' = P + res.dt/(C + g.dt)
    #
    #  Amplification is C/(C + g.dt), in (0, 1] for ANY dt and ANY C, so the stability limit that
    #  forced the lumping ceases to exist.  Same scheme and same reason as the melt temperatures in
    #  unit 324 (As-Built, *Melt-Temperature Integration in Unit 324*).  BIT-EXACT at the design
    #  seed: every residual is zero there, so P' == P whatever the denominator is.
    _DP_PROBE = 1.0e-3      # bar, perturbation for the resisting conductance

    def _res_mp(p):
        return (_valve_flow(K_902, state.valve_supply_pct, state.P_SUP, p, P_SUP_BARA, P_HP_BARA)
                - m_strip_consume
                - _valve_flow(K_902, state.hv_vent_hp_pct, p, 1.01325, P_HP_BARA, 1.01325))

    def _res_9(p):
        m903_p = _valve_flow(K_903, state.valve_admit9_pct, state.P_SUP, p, P_SUP_BARA, P_MP_BARA)
        mld_p = _valve_flow(K_LD9, state.valve_letdown_pct, p, state.P_LP, P_MP_BARA, P_LP_BARA)
        att_p = M_ATTEMPER9_DES * (m903_p / max(M_903_DES, 1e-12))
        return m903_p + m_flash9 + att_p - m_9_users - mld_p

    def _res_lp(p):
        mld_p = _valve_flow(K_LD9, state.valve_letdown_pct, state.P_9, p, P_MP_BARA, P_LP_BARA)
        water_p = mld_p * (H_G_MP - H_G_LP) / (H_G_LP - H_W)
        m963_p = (_valve_flow(K_963, state.valve_963_pct, state.P_SUP, p, P_SUP_BARA, P_LP_BARA)
                  + _valve_flow(K_HV602, state.hv_329602_pct, state.P_SUP, p, P_SUP_BARA, P_LP_BARA))
        vent_p = _valve_flow(K_207A, state.pv207a_pct, p, 1.01325, P_LP_BARA, 1.01325)
        turb_p = _valve_flow(K_207B, state.pv207b_pct, p, P_TURBINE_OUT_BARA,
                             P_LP_BARA, P_TURBINE_OUT_BARA)
        return m_hpcc_gen + mld_p + water_p + m963_p - M_USERS_LP - vent_p - turb_p

    def _implicit(p, res, res_fn, capacitance):
        g = (res - res_fn(p + _DP_PROBE)) / _DP_PROBE       # kg/s per bar, >= 0 for a stable node
        return p + res * dt / (capacitance + max(g, 0.0) * dt)

    state.P_MP = max(0.0, _implicit(state.P_MP, residual_d005_vapor, _res_mp, C_MP))
    state.P_9 = max(0.0, _implicit(state.P_9, residual_d009_vapor, _res_9, C_9))
    state.P_LP = max(P_LP_MIN_BARA, _implicit(state.P_LP, residual_lp_vapor, _res_lp, C_LP))

    # publish diagnostics (m_ld field carries the 9->4 let-down for back-compat telemetry)
    state.m_supply, state.m_903, state.m_ld = m_supply, m_903, m_ld9
    state.m_flash9, state.m_attemper9, state.m_users9 = m_flash9, m_attemper9, m_9_users
    state.m_963, state.m_water, state.m_vent_hp, state.m_pic = m_963, m_water, m_vent_hp, m_pic
    state.m_vent, state.m_turbine = m_vent, m_turbine

    # -- drum level loops (LIC-329502/503/504): local condensate inventories, design-seeded --
    #    502: 329D005 drain->329D009  (in = HP-stripper condensate return = m_strip_consume)
    #    503: 329D009 drain->322D001  (in = 502 drain - flash vapour)
    #    504: 322D001 make-up plus LV503 inflow balances LP boil-off (reverse-acting make-up)
    #    Liquid inventories do not write the header pressures; their published residuals expose net flow.
    state.lic503_lvl, state.lic503_op, state.lic503_ep, m_lv503 = _level_loop(
        state.lic503_mode, state.lic503_sp, state.lic503_lvl, state.lic503_op, state.lic503_ep,
        dt, MSPAN_503, M_503_DES, direct=True, m_ext=m_lv502 - m_flash9, valve_out=True,
        p_up=state.P_9, p_dn=state.P_LP, p_up_des=P_MP_BARA, p_dn_des=P_LP_BARA,
        rho=_rho_drum_liquid(state.P_9),
        rho_des=rho_liquid_sat_kgm3(tsat_c(P_MP_BARA)))
    state.lic504_lvl, state.lic504_op, state.lic504_ep, m_lv504 = _level_loop(
        state.lic504_mode, state.lic504_sp, state.lic504_lvl, state.lic504_op, state.lic504_ep,
        dt, MSPAN_504, M_504_DES, direct=False, m_ext=m_hpcc_gen - m_lv503, valve_out=False,
        p_up=P_916_BARA, p_dn=state.P_LP, p_up_des=P_916_BARA, p_dn_des=P_LP_BARA,
        rho=RHO_916, rho_des=RHO_916)

    state.mass_residual_d005_vapor = residual_d005_vapor
    state.mass_residual_d009_vapor = residual_d009_vapor
    state.mass_residual_lp_vapor = residual_lp_vapor
    state.mass_residual_d005_liquid = m_strip_consume - m_lv502
    state.mass_residual_d009_liquid = m_lv502 - m_flash9 - m_lv503
    state.mass_residual_lp_liquid = m_lv503 + m_lv504 - m_hpcc_gen
    return state


# ==================================================================== isolated probe
if __name__ == "__main__":
    DT = 0.5

    # G8: standalone design generation must feed BOTH the local users (M_HPCC_DES placeholder) and
    # the turbine export (M_TURBINE_DES), so the 4-bar header closes at 4.4 with leg B at its bias.
    def settle(st, n, m_strip=M_STRIP_DES, m_hpcc=M_HPCC_DES + M_TURBINE_DES):
        for _ in range(n):
            step_steam(st, DT, m_strip, m_hpcc)
        return st

    print("=" * 56)
    print("  STEAM-SYSTEM 4-LEVEL ISOLATED PROBE")
    print("=" * 56)

    # 1. design fixed point: all four nodes settle to design pressures
    st = SteamState()
    settle(st, 6000)
    print("\n  [1] design fixed point (settle 3000 s):")
    print(f"      P_SUP={st.P_SUP:.3f} (25.0)   P_MP={st.P_MP:.3f} (19.7)")
    print(f"      P_9  ={st.P_9:.3f} (9.0)    P_LP={st.P_LP:.3f} (4.4)")
    print(f"      m_supply={st.m_supply:.3f}  m_903={st.m_903:.4f}  "
          f"m_ld9={st.m_ld:.4f}  m_pic={st.m_pic:.3f}")
    ok_hp = abs(st.P_MP - P_HP_BARA) < 0.05
    ok_9  = abs(st.P_9  - P_MP_BARA) < 0.10
    ok_lp = abs(st.P_LP - P_LP_BARA) < 0.05
    print(f"      P_MP@19.7 {'PASS' if ok_hp else 'FAIL'} | "
          f"P_9@9.0 {'PASS' if ok_9 else 'FAIL'} | P_LP@4.4 {'PASS' if ok_lp else 'FAIL'}")

    # 2. HP supply crash -> P_MP collapses (stripper steam starvation).
    #    PIC-329204 must be in MAN, else the AUTO loop correctly rejects the valve poke and holds P_MP.
    st2 = SteamState(); settle(st2, 2000)
    st2.pic204_mode = "MAN"
    st2.valve_supply_pct = 0.0
    settle(st2, 2000)
    print(f"\n  [2] PV-329204 -> 0%%:  P_MP={st2.P_MP:.3f} (expect << 19.7)  "
          f"{'PASS' if st2.P_MP < 10.0 else 'FAIL'}")

    # 3. 9-bar over-pressure disturbance -> split-range opens 205B let-down, drives P_9 back to SP
    st3 = SteamState(); settle(st3, 2000)
    st3.P_9 = 10.5                                               # inject over-pressure past the split DB (err9=1.5 > DB_9) so 205B let-down must open
    step_steam(st3, DT, M_STRIP_DES, M_HPCC_DES)                 # one tick: split-range reacts
    ld_open = st3.valve_letdown_pct
    settle(st3, 1200)                                           # recover to SP
    print(f"\n  [3] 9-bar over-P (P_9<-10.5):  205B opened to {ld_open:.1f}%%  "
          f"-> recovered P_9={st3.P_9:.3f} (9.0)  "
          f"{'PASS' if ld_open > 0.0 and abs(st3.P_9 - P_MP_BARA) < 0.10 else 'FAIL'}")
    ok_split = ld_open > 0.0 and abs(st3.P_9 - P_MP_BARA) < 0.10

    # 4. LP generation collapse -> PIC make-up holds floor, Tsat(P_LP) stays physical
    st4 = SteamState(); settle(st4, 2000)
    settle(st4, 3000, m_hpcc=0.0)
    print(f"\n  [4] HPCC gen -> 0:  P_LP={st4.P_LP:.3f} (floor {P_LP_MIN_BARA})  "
          f"m_pic={st4.m_pic:.3f}  {'PASS' if st4.P_LP >= P_LP_MIN_BARA - 1e-6 else 'FAIL'}")

    print("\n" + "=" * 56)
    allok = (ok_hp and ok_9 and ok_lp and st2.P_MP < 10.0 and ok_split
             and st4.P_LP >= P_LP_MIN_BARA - 1e-6)
    print(f"  OVERALL: {'PASS' if allok else 'FAIL'}")
    print("=" * 56)
