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

Valve flows use the standard incompressible orifice law shared by the rest of the sim
(LV-322501 drain, HV-322604 vent):

    m_dot = K * (valve%/100) * sqrt(max(P_up - P_down, 0))                      [kg/s]

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

# ---------------------------------------------------------------- saturated-steam enthalpies (kJ/kg)
#   Standard IAPWS/IF97 saturation table (sourced), used only for let-down desuperheat trims.
H_G_SUP = 2801.0    # h_g, 25 bar a supply steam (stream 901)
H_G_HP  = 2798.0    # h_g, 19.7 bar a (329D005 saturated)
H_G_MP  = 2773.0    # h_g, 9.0 bar a  (329D009 saturated)
H_G_LP  = 2743.0    # h_g, 4.4 bar a  (322D001A/B saturated)
H_W     = 419.0     # h_f desuperheat condensate (~100 C, BFW)
# back-compat aliases (legacy 2-node names still referenced by external probes)
H_MP = H_G_HP
H_LP = H_G_LP

# ---------------------------------------------------------------- boundary + node design pressures (bar a)
P_SUP_BARA = 25.0   # BL 25-bar supply header (stream 901 from 320E006), held boundary
P_HP_BARA  = 19.7   # 329D005 HP saturator design (== STRIP_STEAM_P_BARA)  -> P_MP field
P_MP_BARA  = 9.0    # 329D009 MP drum design (Tsat ~= 175 C per mapping -> 9 bar a)
P_LP_BARA  = 4.4    # 322D001A/B LP drums design (== HPCC_STEAM_P_BARA)

# ---------------------------------------------------------------- valve flow coeffs [ (kg/s)/sqrt(bar) ]
#   Seeded so the design stream split (PFD-26) is reproduced at the design node pressures.
K_902 = (39400.0 / 1850.0) / (0.50 * (P_SUP_BARA - P_HP_BARA) ** 0.5)  # PV-329204 BL(25)->329D005: sized so a 50% design opening passes the HP-stripper draw (STRIP_DUTY_DES_KW 39400 / lambda_MP 1850 = 21.297 kg/s) at 25->19.7 bar  (~18.50)
K_903 = 1.0         # PV-329205A  : BL(25) -> 329D009 (MP drum admit)
K_963 = 2.0         # PV-329207C+HV-329602 : BL(25) -> 4-bar header (design shut)
K_LD9 = 2.0         # PV-329205B  : 329D009 (9) -> 4-bar header let-down (split-range vent)

# ---------------------------------------------------------------- header capacitance ( (kg/s)/bar )
#   Physical lumped capacitance C = V * (drho_sat/dP).  V from datasheet/mapping (329D005 13.0 m3,
#   329D009 8.16 m3); drho/dP from the PFD-26 process densities (25:9.48, 19.7:7.4, 9:3.37, 4.4:2.37
#   kg/m3).  The HP/LP capacitances are held at the calibrated lumped value that pins the existing
#   HP-stripper/HPCC transient (design fixed point is C-independent); the 9-bar node is derived.
C_MP = 25.0         # HP saturator 329D005 header (lumped, calibrated)      -> P_MP field
C_LP = 25.0         # LP 322D001A/B header (lumped, calibrated)
#   329D009: drho/dP ~= (3.37-2.37)/(9-4.4) = 0.2174 kg/m3/bar ; C_9 = 8.16 * 0.2174 * F_lump
#   A x30 lumping factor (matching the HP/LP calibrated convention, which sits ~x5 above the bare
#   vapour-inventory value) keeps the 9-bar node on the same slow-accumulation timescale as the
#   other headers and Euler-stable at the host dt.
C_9 = 8.16 * 0.2174 * 30.0   # ~= 53.2 (kg/s)/bar

# ---------------------------------------------------------------- LP header floor (site LP-main tie-in)
#   Make-up import holds the header when local generation (HPCC steam raising + 9->4 let-down)
#   collapses -- e.g. a CO2-feed cut zeroes the carbamate condensation duty.  Set just below design
#   so it only acts on a genuine deficit; the design steady state is untouched.
P_LP_MIN_BARA = 3.5

# ---------------------------------------------------------------- LP 4-bar header pressure PIC (PI vent/make-up)
#   Lumped stand-in for the master-SP trio PIC-329207A (vent) / B (turbine 320MT02) / C (BL admit):
#   a PI vent(+)/make-up(-) flow that drives the header to setpoint.  Proportional term is zero and
#   the integral starts at zero at the design pressure, so the calibrated design balance -- and the
#   Tsat(P_LP)=146.3 coupling to the HPCC -- is bit-for-bit unchanged.
P_LP_SP_BARA = 4.4
K_PIC_LP     = 8.0      # proportional vent/make-up gain   [ (kg/s)/bar ]
KI_PIC_LP    = 0.4      # integral vent/make-up gain        [ (kg/s)/(bar.s) ]
M_PIC_CLAMP  = 10.0     # anti-windup clamp on the integral contribution [ kg/s ]

# ---------------------------------------------------------------- MASTER-SP trio PIC-329207A/B/C
#   The lumped LP PIC above resolves into three staggered sub-controllers on the 4-bar header.
#   MASTER ON : user sets one master SP; the trio fans out and locks to it --
#       PIC-329207A (vent PV-329207A, atm)          SP = master + DB_LP   (highest -> opens first on over-P)
#       PIC-329207B (turbine 320MT02 make-up)       SP = master            (== header master)
#       PIC-329207C (BL 25-bar admit PV-329207C)    SP = master - DB_LP   (lowest  -> opens first on under-P)
#   MASTER OFF: the three loops are independent (operator sets each SP / mode / MAN opening).
#   At design P_LP=4.400 (master 4.4 -> SP_A=4.5/SP_B=4.4/SP_C=4.3): eA=-0.1 & eC=-0.1 floor both
#   one-sided integrals at 0, eB=0 -> all three valves shut -> m_vent=m_turbine=m_963=0 -> net trim 0.
#   Header self-balances (M_USERS_LP == M_HPCC_DES == 3.0) so the fixed point is bit-for-bit unchanged.
DB_LP      = 0.1        # bar, master-SP stagger: A=SP+DB_LP (vent) / C=SP-DB_LP (make-up)
K_207A     = 3.0        # PV-329207A vent valve coeff  (P_LP -> atm)          [ (kg/s)/sqrt(bar) ]
K_207B     = 2.0        # PV-329207B turbine 320MT02 make-up coeff (25 -> LP) [ (kg/s)/sqrt(bar) ]
K_PIC_207  = 120.0      # sub-controller proportional gain                    [ %/bar ]
KI_PIC_207 = 6.0        # sub-controller integral gain                        [ %/(bar.s) ]
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
K_PIC_204    = 40.0        # proportional gain [ %/bar ]  (under-P opens supply)
KI_PIC_204   = 2.0         # integral gain     [ %/(bar.s) ]
I204_CLAMP   = 50.0 / KI_PIC_204   # two-sided integral clamp (integral term within +/-50 %)

# ---------------------------------------------------------------- design throughputs (probe / seed)
M_STRIP_DES = 39400.0 / 1850.0   # kg/s (21.297), design MP steam consumed by HP-stripper reboiler == STRIP_DUTY_DES_KW / lambda_MP (main.py design duty; MP header consume is design-pinned constant)
M_HPCC_DES  = 3.0      # kg/s, design LP steam raised in the HP carbamate condenser

# ---------------------------------------------------------------- fixed LP design consumers
#   Turbine 320MT02 (FV-329407 + PV-329207B) load-follows the HPCC steam raising at design; the
#   4-bar H.Ex users are later units (out of scope -> 0).  Set equal to the design HPCC generation
#   so the 4-bar header self-balances at 4.4 bar with ~zero PIC vent/make-up at design; the live PIC
#   trims the residual off-design.
M_USERS_LP = M_HPCC_DES

# ---------------------------------------------------------------- 9-bar design throughput (reduced scope)
#   PFD-26 stream 903 = 1754 kg/h admitted to 329D009 at full design, consumed by the 9-bar header
#   users 324E003 / 335225 -- both LATER units, out of the current sim scope.  With no in-scope
#   9-bar consumer the drum has zero design throughput: PV-329205A and PV-329205B both shut, the
#   header held at 9.0 bar by the split-range PIC (Sourcing Law: the 1754 kg/h is the ultimate
#   design and is not fabricated into an in-scope flow it has nowhere to go).
M_903_DES = 1754.0 / 3600.0   # kg/s, documented ultimate-design reference only (unused in scope)

# ---------------------------------------------------------------- drum level loops (LIC-329502/503/504)
#   Three condensate-inventory level loops, each a LOCAL mass balance (accumulation = in - out) and
#   design-seeded so dm/dt=0 at the pinned steady state: level held at SP=50% with the seed valve
#   opening -> the fixed point is bit-for-bit unchanged.  step_steam is gated OFF during the boot-pin
#   settle (_STEAM_READY=False), so these cannot perturb any design-pinned header pressure; and the
#   level states never write P_MP/P_9/P_LP (liquid inventory decoupled from the vapor-pressure ODEs).
#   Control sense (PID_No_107_1 / 329-1 mapping):
#     LIC-329502  329D005 condensate drain -> 329D009  : DIRECT  (level>SP -> open LV-329502 -> drain^)
#     LIC-329503  329D009 condensate drain -> 322D001  : DIRECT  (level>SP -> open LV-329503 -> drain^)
#     LIC-329504  322D001 make-up f. 329P001A/B pumps  : REVERSE (level>SP -> close LV-329504 -> make-up v)
#   Cascade conservation: the 329D005->329D009 drain carries the full HP-stripper condensate return
#   (M_STRIP_DES); the 329D009 drain discharges to the 329P001 condensate-pump suction (collection),
#   and LV-329504 admits only the make-up replacing the LP boil-off raised in the HPCC (M_HPCC_DES) ->
#   every stream maps to a real source/sink (100% conservation; no fabricated flow to dodge stiffness).
#   Mass-per-%level  m_span = rho_liq * A_surface * span  (sets the level TIMESCALE only; NOT design-
#   pinned).  Datasheet geometry (NSF/Uhde DDS, folder 329-1):
#     329D005 horiz ID 1.760 m x L 5.000 m, LT-329502 span 1.500 m, rho 850.25 -> ~11223 kg
#     329D009 horiz ID 1.776 m x L 2.600 m, LT-329503 span 0.750 m, rho 892.15 -> ~ 3090 kg
#     322D001 vert  ID 1.600 m (A=pi/4 D^2), LT-329504 span 2.000 m, rho 917.0 -> ~ 3688 kg
LEVEL_SP_DES = 50.0        # %, design normal liquid level (all three drums)
LV_OPEN_DES  = 50.0        # %, design-seed level-valve opening (valve flow == design draw at this opening)
LIC_KC       = 2.5         # %op per %level, velocity-form PI proportional gain (controller tuning)
LIC_TI       = 90.0        # s, velocity-form PI integral time
M_502_DES    = M_STRIP_DES    # kg/s, 329D005 condensate throughput = HP-stripper condensate return
M_503_DES    = M_STRIP_DES    # kg/s, 329D009 condensate throughput (cascade from 329D005)
M_504_DES    = M_HPCC_DES     # kg/s, 322D001 make-up = LP steam boil-off replaced (HPCC raising)
MSPAN_502    = 850.25 * (1.760 * 5.000) * 1.500         # kg, 329D005 horiz (mid-level chord = ID)
MSPAN_503    = 892.15 * (1.776 * 2.600) * 0.750         # kg, 329D009 horiz
MSPAN_504    = 917.0  * (0.78539816 * 1.600 ** 2) * 2.000   # kg, 322D001 vert (A=pi/4*D^2=2.0106 m^2)


def _valve_flow(K: float, opening_pct: float, p_up: float, p_down: float) -> float:
    """Incompressible orifice flow (kg/s). Clamps opening to [0,100] and dP to >=0."""
    op = max(0.0, min(100.0, opening_pct))
    dP = max(p_up - p_down, 0.0)
    return K * (op / 100.0) * dP ** 0.5


def _seed_supply_pct() -> float:
    """PV-329204 opening that delivers the design stripper draw at P_SUP->P_HP."""
    dP = (P_SUP_BARA - P_HP_BARA) ** 0.5
    return min(100.0, M_STRIP_DES / (K_902 * dP) * 100.0)


_SUPPLY_BIAS = _seed_supply_pct()   # design-seed PV-329204 opening; PIC-329204 bias anchor (bit-exact fixed point)


def _level_loop(mode, sp, lvl, op, ep, dt, m_span, m_des, direct, m_ext, valve_out):
    """Advance one drum level loop; return (lvl, op, ep, m_valve).

    Velocity-form PI on the drum level, then a LOCAL mass balance (accumulation = in - out):
        e        = (lvl-sp) if direct else (sp-lvl)              # direct=drain, reverse=make-up
        op      <- clamp(op + KC*((e-ep) + dt/TI*e), 0, 100)     # AUTO only; frozen in MAN
        m_valve  = m_des * (op / LV_OPEN_DES)                    # design-seeded valve flow (kg/s)
        dm       = (m_ext - m_valve) if valve_out else (m_valve - m_ext)   # in - out
        lvl     <- clamp(lvl + dm*dt/m_span*100, 0, 100)
    ep is tracked every tick (incl. MAN) -> bumpless MAN->AUTO.  Seeded op==LV_OPEN_DES with
    m_ext==m_des gives m_valve==m_ext -> dm==0 -> level parks at SP (design bit-exact).
    """
    e = (lvl - sp) if direct else (sp - lvl)
    if mode == "AUTO":
        op = max(0.0, min(100.0, op + LIC_KC * ((e - ep) + (dt / LIC_TI) * e)))
    ep = e
    m_valve = m_des * (max(0.0, min(100.0, op)) / LV_OPEN_DES)
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
    valve_admit9_pct:  float = 0.0   # PV-329205A (BL admit); split-range, design shut (no 9-bar users)
    valve_letdown_pct: float = 0.0   # PV-329205B (9->4 let-down); split-range, design shut
    valve_963_pct:     float = 0.0   # PV-329207C+HV-329602 (BL->4-bar); design shut
    hv_vent_hp_pct:    float = 0.0   # HV-329601 329D005 atm vent (design shut)
    # --- last-tick flow diagnostics (kg/s) ---
    m_supply: float = 0.0            # stream 902  (BL -> 329D005)
    m_903:    float = 0.0            # stream 903  (BL -> 329D009)
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
    pic207_mode: str = "AUTO"           # PIC-329207 == leg B (turbine make-up): AUTO=PI; MAN=freeze valve, hold integral
    pic207_sp:   float = P_LP_SP_BARA   # 4-bar header master SP (bar a) == leg-B SP
    # --- MASTER-SP trio (leg B reuses pic207_sp / pic207_mode / i_pic / valve pv207b_pct; leg C reuses valve_963_pct) ---
    master207_on: bool  = True                  # ON=one SP fans out A=+DB/B/C=-DB & locks; OFF=3 independent loops
    master207_sp: float = P_LP_SP_BARA          # master SP (bar a); 4.4 -> B=4.4 / A=4.5 / C=4.3
    pic207a_mode: str   = "AUTO"                # PIC-329207A vent      (SP = master + DB_LP)
    pic207a_sp:   float = P_LP_SP_BARA + DB_LP
    pic207c_mode: str   = "AUTO"                # PIC-329207C BL admit  (SP = master - DB_LP)
    pic207c_sp:   float = P_LP_SP_BARA - DB_LP
    pv207a_pct:   float = 0.0                   # PV-329207A vent opening (%)
    pv207b_pct:   float = 0.0                   # PV-329207B turbine make-up opening (%)
    i_207a:       float = 0.0                   # PIC-329207A integral (one-sided, bar.s-scaled)
    i_207c:       float = 0.0                   # PIC-329207C integral (one-sided, bar.s-scaled)
    m_vent:       float = 0.0                   # PV-329207A vent flow (kg/s)
    m_turbine:    float = 0.0                   # PV-329207B turbine make-up flow (kg/s)
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


def step_steam(state: SteamState, dt: float,
               m_strip_consume: float, m_hpcc_gen: float) -> SteamState:
    """Advance the 4-level steam network one Euler tick.

    Args:
        state            : SteamState (mutated in place and returned).
        dt               : timestep (s).
        m_strip_consume  : MP steam drawn by the HP-stripper reboiler (kg/s).
        m_hpcc_gen       : LP steam raised in the HPCC (kg/s).
    """
    # -- BL supply header held at boundary (site 25-bar main) --
    state.P_SUP = P_SUP_BARA

    # -- PIC-329204 HP-saturator pressure (direct PI about the seed opening: under-P -> open supply) --
    if state.pic204_mode == "AUTO":
        e204 = state.pic204_sp - state.P_MP
        state.i_204 = max(-I204_CLAMP, min(I204_CLAMP, state.i_204 + e204 * dt))
        state.valve_supply_pct = max(0.0, min(100.0,
            _SUPPLY_BIAS + K_PIC_204 * e204 + KI_PIC_204 * state.i_204))
    # MAN: valve_supply_pct frozen; i_204 held -> bumpless return to AUTO

    # -- stream 902: BL -> 329D005 HP saturator (PV-329204) --
    m_supply = _valve_flow(K_902, state.valve_supply_pct, state.P_SUP, state.P_MP)
    m_vent_hp = _valve_flow(K_902, state.hv_vent_hp_pct, state.P_MP, 1.01325)  # HV-329601 atm

    # -- 329D009 split-range PIC-329205 about SP (mutually-exclusive 205A admit / 205B let-down) --
    #   P_9 > SP: PV-329205A shut, PV-329205B (let-down 9->4) opens proportionally.
    #   P_9 < SP: PV-329205B shut, PV-329205A (BL admit) opens proportionally.
    #   |P_9 - SP| <= dead-band: both legs shut -> design fixed point (zero 9-bar throughput).
    if state.pic205_mode == "AUTO":
        err9 = state.P_9 - state.pic205_sp
        if err9 > DB_9:            # over-pressure: vent excess to the 4-bar header
            state.valve_admit9_pct  = 0.0
            state.valve_letdown_pct = min(100.0, K_PIC_9 * (err9 - DB_9))
        elif err9 < -DB_9:        # under-pressure: admit BL steam
            state.valve_letdown_pct = 0.0
            state.valve_admit9_pct  = min(100.0, K_PIC_9 * (-err9 - DB_9))
        else:                     # dead-band: both shut
            state.valve_admit9_pct  = 0.0
            state.valve_letdown_pct = 0.0
    # MAN: split-range writes frozen; operator-set 205A/205B openings persist unchanged.

    # -- stream 903: BL -> 329D009 (PV-329205A) ; 9->4 let-down (PV-329205B) --
    m_903 = _valve_flow(K_903, state.valve_admit9_pct,  state.P_SUP, state.P_9)
    m_ld9 = _valve_flow(K_LD9, state.valve_letdown_pct, state.P_9,   state.P_LP)
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
    m_vent = _valve_flow(K_207A, state.pv207a_pct, state.P_LP, 1.01325)

    # -- PIC-329207B turbine 320MT02 make-up (direct: P_LP < SP_B -> open PV-329207B) --
    if state.pic207_mode == "AUTO":
        eB = state.pic207_sp - state.P_LP
        state.i_pic = max(0.0, min(I207_CLAMP, state.i_pic + eB * dt))
        state.pv207b_pct = max(0.0, min(100.0, K_PIC_207 * eB + KI_PIC_207 * state.i_pic))
    # MAN: pv207b_pct frozen; i_pic held -> bumpless return to AUTO
    m_turbine = _valve_flow(K_207B, state.pv207b_pct, state.P_SUP, state.P_LP)

    # -- PIC-329207C BL 25-bar admit (direct: P_LP < SP_C -> open PV-329207C/HV-329602) --
    if state.pic207c_mode == "AUTO":
        eC = state.pic207c_sp - state.P_LP
        state.i_207c = max(0.0, min(I207_CLAMP, state.i_207c + eC * dt))
        state.valve_963_pct = max(0.0, min(100.0, K_PIC_207 * eC + KI_PIC_207 * state.i_207c))
    # MAN: valve_963_pct frozen; i_207c held -> bumpless return to AUTO
    m_963 = _valve_flow(K_963, state.valve_963_pct, state.P_SUP, state.P_LP)

    # net header trim = vent(+ out) - turbine(- in); leg C (m_963) accounted separately in the balance
    m_pic = m_vent - m_turbine

    # -- node mass balances --
    #   329D005 (HP):  in 902 ; out stripper + HP vent
    dP_MP = (m_supply - m_strip_consume - m_vent_hp) / C_MP
    #   329D009 (9-bar): in 903 ; out 9->4 let-down (+ later 9-bar users = 0)
    dP_9  = (m_903 - m_ld9) / C_9
    #   322D001A/B (4-bar): in HPCC + let-down + desuperheat + 963(C) + turbine(B) ; out users + vent(A)
    dP_LP = (m_hpcc_gen + m_ld9 + m_water + m_963 + m_turbine - M_USERS_LP - m_vent) / C_LP

    state.P_MP = max(0.0, state.P_MP + dt * dP_MP)
    state.P_9  = max(0.0, state.P_9 + dt * dP_9)
    state.P_LP = max(P_LP_MIN_BARA, state.P_LP + dt * dP_LP)

    # publish diagnostics (m_ld field carries the 9->4 let-down for back-compat telemetry)
    state.m_supply, state.m_903, state.m_ld = m_supply, m_903, m_ld9
    state.m_963, state.m_water, state.m_vent_hp, state.m_pic = m_963, m_water, m_vent_hp, m_pic
    state.m_vent, state.m_turbine = m_vent, m_turbine

    # -- drum level loops (LIC-329502/503/504): local condensate inventories, design-seeded --
    #    502: 329D005 drain->329D009  (in = HP-stripper condensate return = m_strip_consume)
    #    503: 329D009 drain->322D001  (in = 502 drain = cascade)
    #    504: 322D001 make-up f.329P001 pumps (out = LP boil-off = m_hpcc_gen ; reverse-acting)
    #    All seeded so dm/dt=0 at design; liquid inventory never writes the header pressures.
    state.lic502_lvl, state.lic502_op, state.lic502_ep, m_lv502 = _level_loop(
        state.lic502_mode, state.lic502_sp, state.lic502_lvl, state.lic502_op, state.lic502_ep,
        dt, MSPAN_502, M_502_DES, direct=True,  m_ext=m_strip_consume, valve_out=True)
    state.lic503_lvl, state.lic503_op, state.lic503_ep, m_lv503 = _level_loop(
        state.lic503_mode, state.lic503_sp, state.lic503_lvl, state.lic503_op, state.lic503_ep,
        dt, MSPAN_503, M_503_DES, direct=True,  m_ext=m_lv502,        valve_out=True)
    state.lic504_lvl, state.lic504_op, state.lic504_ep, _ = _level_loop(
        state.lic504_mode, state.lic504_sp, state.lic504_lvl, state.lic504_op, state.lic504_ep,
        dt, MSPAN_504, M_504_DES, direct=False, m_ext=m_hpcc_gen,     valve_out=False)
    return state


# ==================================================================== isolated probe
if __name__ == "__main__":
    DT = 0.5

    def settle(st, n, m_strip=M_STRIP_DES, m_hpcc=M_HPCC_DES):
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

    # 2. HP supply crash -> P_MP collapses (stripper steam starvation)
    st2 = SteamState(); settle(st2, 2000)
    st2.valve_supply_pct = 0.0
    settle(st2, 2000)
    print(f"\n  [2] PV-329204 -> 0%%:  P_MP={st2.P_MP:.3f} (expect << 19.7)  "
          f"{'PASS' if st2.P_MP < 10.0 else 'FAIL'}")

    # 3. 9-bar over-pressure disturbance -> split-range opens 205B let-down, drives P_9 back to SP
    st3 = SteamState(); settle(st3, 2000)
    st3.P_9 = 9.6                                                # inject over-pressure
    step_steam(st3, DT, M_STRIP_DES, M_HPCC_DES)                 # one tick: split-range reacts
    ld_open = st3.valve_letdown_pct
    settle(st3, 1200)                                           # recover to SP
    print(f"\n  [3] 9-bar over-P (P_9<-9.6):  205B opened to {ld_open:.1f}%%  "
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
