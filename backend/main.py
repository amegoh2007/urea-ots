"""
Urea OTS - Unit 321-1 NH3 Pumping Station Backend.

Physics:
    321P002 A/B  : Triplex (3-plunger) reciprocating positive-displacement pump.
                   D=140 mm, L=205 mm, n_plgr=3, eta_v=0.95, eta_m=0.915.
                   V_swept_rev = (pi/4) * D^2 * L * n_plgr        [m^3/rev]
                   Q[m^3/h]    = N[rpm] * V_swept_rev * eta_v * 60
                       N = 124 rpm -> Q = 66.91 m^3/h  (datasheet 67.1)
                       N = 152 rpm -> Q = 82.02 m^3/h  (datasheet 82)
    Speed control: VOITH torque-converter scoop. The controlled/displayed
                   process variable is the torque-converter VALVE OPENING (%).
                       opening 0..100 %  ->  N = opening/100 * N_rated
                   SIC PV = actual opening %, MV/OP = commanded opening %.
                   Pump RPM is derived and shown separately on the pump tile.
    321D003      : ID=0.97 m, H=1.4 m (cyl) -> V = 1.0345 m^3.
                   Mass balance: dm/dt = F_in_BL - F_pump_total.
    SIC-321950/1 : MAN sets opening directly (PV entry); AUTO uses local SP%+PID;
                   CAS takes opening SP from the ratio block (+ operator N/C bias).
    Ratio block  : SP_NH3_flow = ratio_SP * F_CO2. In CAS the SIC opening SP is
                   derived from the required NH3 flow split across active pumps.
"""

import asyncio
import json
import math
import os
import time
from typing import Set

import reactor  # 322R001 Modified Inoue-Kanai conversion kinetics (quarantined)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles


def tsat_steam(p_bara: float) -> float:
    """Saturated-steam temperature [deg C] from absolute pressure [bar a].

    Antoine equation for water (valid 100-374 C), pressure in mmHg:
        log10(P_mmHg) = 8.14019 - 1810.94 / (244.485 + T_C)
    inverted for temperature, with P_mmHg = P_bara * 750.0617.  Reproduces the
    steam tables and the plant reference (saturated-steam T-vs-P, Fig. 9) to
    <0.2 % over the 18-23 bar a HP-steam band.
    """
    p_mmhg = max(p_bara, 0.01) * 750.0616827
    return 1810.94 / (8.14019 - math.log10(p_mmhg)) - 244.485


# ----- Constants -----
NH3_RHO         = 604.8          # kg/m^3, design (eff. density NH3 feed @ 25 C)
G               = 9.81
PUMP_D          = 0.140          # m
PUMP_L          = 0.205          # m
PUMP_N_PLGR     = 3
PUMP_ETA_V      = 0.95
PUMP_ETA_M      = 0.915
PUMP_V_PER_REV  = (math.pi/4.0) * PUMP_D**2 * PUMP_L * PUMP_N_PLGR   # m^3/rev
PUMP_RATED_RPM  = 152.0
PUMP_MIN_RPM    = 37.0
PUMP_NORMAL_RPM = 124.0
PUMP_RATED_I    = 51.0           # A (display proxy; DCS 43.9 A @ 131 rpm = 86 %)
TANK_ID         = 0.970          # m
TANK_H          = 1.400          # m
TANK_VOL        = (math.pi/4.0) * TANK_ID**2 * TANK_H                # m^3
P_SYN_DOWN_BAR  = 165.0          # bar a, downstream synthesis nominal
P_ATM_BAR       = 1.013          # bar, atmosphere (gauge<->abs)
PT_FEED_DESIGN_BARA = 20.0       # bar a, NH3 feed (suction) design pressure - DS normal
CP_NH3          = 4740.0         # J/kg-K, liquid NH3 specific heat (~25 C)
BETA_NH3        = 1.9e-3         # 1/K, liquid NH3 isobaric expansivity (~25 C)
ETA_PUMP_HYD    = 0.85           # hydraulic efficiency (discharge thermal rise)
M_NH3           = 17.031         # g/mol, ammonia molar mass
M_CO2           = 44.009         # g/mol, carbon dioxide molar mass
# N/C ratio = moles N / moles C.  Each NH3 -> 1 N, each CO2 -> 1 C, so per the
# feed-ratio equation:  N/C = (m_NH3 / m_CO2) * (M_CO2 / M_NH3) = (m_NH3/m_CO2)*2.584.
NC_FACTOR       = M_CO2 / M_NH3   # = 2.584; N/C = (m_NH3/m_CO2)*NC_FACTOR  (feed-ratio eq)
# Cascade demand inverts it:  m_NH3 = (N/C / NC_FACTOR) * m_CO2 = (N/C)*(M_NH3/M_CO2)*m_CO2.
NC_TO_MASS      = M_NH3 / M_CO2   # = 1/NC_FACTOR; multiply molar N/C by this * m_CO2 -> NH3 mass
DT              = 0.1            # s sim tick
T_BL_FEED_C     = 25.0           # C, BL NH3 supply temp to 321D003 (design feed temp)

# ----- 322F001 HP Ejector (liquid-liquid jet pump) model -----
#   Motive  : HP liquid NH3 from 321P002 A/B (pure NH3) via TI-321020 -> XV-322901
#   Suction : enriched carbamate from 322E003 overflow, via PI-329201 -> TI-322002
#   Discharge -> TT-322012 -> 322E002 HP Carbamate Condenser (HPCC).
# Component mass balance:  m_i,disch = m_i,motive + m_i,suction
# Suction entrains at a fixed design ratio mu (fixed nozzle/throat geometry), so the
# discharge composition stays pinned to the design 'Carb. Liq.' table while total flow
# tracks the live motive.  Verified IDENTICAL to design (verify_322f001.py: PASS).
MW_COMP = {"CO2":44.0098,"CH4":16.043,"H2":2.0158,"H2O":18.0152,
           "N2":28.0134,"NH3":17.0304,"O2":31.9988,"Urea":60.056,"Biuret":103.081}
EJ_MOTIVE_NH3_DES = 40756.0      # kg/h, design motive NH3 (pure, 321P002 A/B BL feed)
EJ_DES_TOTAL      = 98320.0      # kg/h, design discharge total (Carb. Liq.)
EJ_DES_MASSPCT    = {"CO2":23.24,"CH4":0.06,"H2":4.17e-3,"H2O":12.39,
                     "N2":0.02,"NH3":64.27,"O2":0.0,"Urea":0.02,"Biuret":0.0}
# 322E003 overflow suction spec (kg/h) = design discharge - pure motive NH3:
_EJ_DES_MASS   = {k: EJ_DES_MASSPCT[k]/100.0*EJ_DES_TOTAL for k in MW_COMP}
EJ_SUCTION_KGH = {k: _EJ_DES_MASS[k] - (EJ_MOTIVE_NH3_DES if k == "NH3" else 0.0)
                  for k in MW_COMP}
EJ_MU          = sum(EJ_SUCTION_KGH.values()) / EJ_MOTIVE_NH3_DES   # entrainment ~1.4125
EJ_OPEN_DES    = 74.0            # %, HV-322602 design opening (HIC-322602 design SP)
EJ_SUC_TOT_DES = sum(EJ_SUCTION_KGH.values())                      # kg/h, design suction
EJ_CARB_FRAC   = {k: EJ_SUCTION_KGH[k] / EJ_SUC_TOT_DES for k in MW_COMP}  # 322E003 overflow comp
EJ_CP_N, EJ_CP_C, EJ_CP_D = 4.74, 3.10, 3.50    # kJ/kg.K  motive / carbamate / discharge
EJ_T_SUCTION_C  = 178.8          # C, carbamate suction (322E003 overflow; dH_mix lumped in)
EJ_P_DISCH_BARA = 144.2          # bar a, diffuser pressure recovery (design)
EJ_RHO_DISCH    = 877.9          # kg/m3, discharge eff. density (design, comp-invariant)
EJ_P_SUCTION_BARA = 140.0        # bar a, 322E003 overflow -> 322F001 suction-B line (PI-329201).
                                 # Design boundary; STATIC until 322E003 HP scrubber is modelled,
                                 # then PI-329201 becomes the live 322E003 overflow line pressure.

# ----- CO2 Feed line (320K002 compressor BL -> XV-322902 -> HP Stripper 322E001) -----
#   Datasheet (design): 1264 kmol/h, 54,618 kg/h, 225 m3/h, MW 43.21, rho 242.70,
#   T 120 C, P 144.2 bar a.  Mol%: CO2 95.24, H2O 0.61, N2 3.55, O2 0.60.
#   Tags: FT-322403 = CO2 feed (Nm3/h), FY-322403 = CO2 feed (t/h),
#         TI-322017 = feed T (C), XV-322902 = isolation to 322E001.
#   Vent: PV-322203 -> safe location; PIC-322203 = CO2 line pressure -> PV-322203 opening;
#         HIC-322203 = PV-322203 minimum opening.  Opening PV-322203 vents CO2 so the
#         feed to 322E001 and the plant Load both decrease.
#   Load% = CO2 feed mass / CO2 design feed mass * 100  (54.618 t/h = 100 % Load).
#   Dynamic: F_feed = F_raw*(1 - f_vent); f_vent = (PV_open/100)*CO2_VENT_MAX_FRAC;
#            PV_open = max(HIC-322203 min, PIC-322203 op); s.F_CO2_th = F_feed drives
#            the N/C ratio block + every downstream CO2 stream.
CO2_FEED_MOLFRAC  = {"CO2": 0.9524, "H2O": 0.0061, "N2": 0.0355, "O2": 0.0060}
CO2_FEED_MW       = sum(CO2_FEED_MOLFRAC[k] * MW_COMP[k] for k in CO2_FEED_MOLFRAC)  # = 43.21
CO2_DES_KGH       = 54618.0      # kg/h design total CO2-feed mass (54.618 t/h = 100 % Load)
CO2_DES_KMOLH     = 1264.0       # kmol/h design total molar flow
CO2_T_FEED_C      = 120.0        # C, TI-322017 feed temperature (design)
CO2_P_DES_BARA    = 144.2        # bar a, design CO2 feed-line pressure (PIC-322203 PV)
CO2_RHO           = 242.70       # kg/m3, eff. density @ 120 C, 144.2 bar a
NM3_PER_KMOL      = 22.414       # Nm3/kmol at 0 C, 1 atm (FT-322403 normal-volume basis)
CO2_VENT_MAX_FRAC = 0.15         # PV-322203 fully open vents up to 15 % of raw CO2 feed
CO2_PV_DP_GAIN    = 0.25         # bar a line-pressure drop per % PV-322203 opening
CO2_MASSFRAC_CO2  = CO2_FEED_MOLFRAC["CO2"] * MW_COMP["CO2"] / CO2_FEED_MW   # ~0.970 pure CO2

# ----- HP Stripper 322E001 (322R001 reactor effluent + CO2 strip gas) ---------------------
#   Vertical falling-film shell&tube: 2600 tubes, L=6 m, OD31x3 (ID25), area 1519 m2,
#   duty 39,400 kW.  Tube side = urea solution (144 bar a); shell side = condensing
#   329D005 MP steam (~19.7 bar a, 214 C, 75,300 kg/h).
#   Feeds  - tube top  : 322R001 overflow (TT-322014, HV-322605)  [reactor NOT modelled ->
#                        boundary constant, stream 207].
#          - tube bottom: live CO2 strip gas (s.F_CO2_th) from the CO2-feed line.
#          - shell      : 19.7 bar a steam (329D005).
#   Prods  - top gas    : 322E001 -> TT-322013 -> 322E002.
#          - bottom soln : 322E001 -> TT-322004 -> LV-322501 -> TT-323001 -> 323C003.
#   Reduced model: component split-fraction calibrated EXACT to the shared design HMB,
#   modulated by steam T, CO2 strip-gas ratio and pressure.  Non-volatiles (Urea,Biuret)
#   -> 100 % bottom; inerts (N2,O2) -> ~100 % top.  Carbamate decomposition NH2COONH4(l)
#   <=> 2NH3(aq)+CO2(aq) is implicit in the dissolved CO2/NH3 phase transfer (no component
#   mole change); urea hydrolysis + biuret formation carry the small component deltas.
#   Validated: closes mass balance < 0.1 % vs the shared streams.
# --- Top liquid feed = 322R001 overflow (stream 207); boundary constant (kmol/h):
STRIP_FEED207_KMOLH = {"Urea": 1302.6, "Biuret": 2.414, "NH3": 4002.4, "CO2": 897.7,
                       "H2O": 2222.0, "N2": 0.0, "O2": 0.0, "CH4": 0.0, "H2": 0.0}
STRIP_FEED207_T_C   = 183.0       # C, TT-322014 = 322R001 overflow feed temp
# --- Reaction extents at the design point (kmol/h):
STRIP_XI_HYD_DES = 88.1           # urea hydrolysis  : Urea + H2O -> 2 NH3 + CO2
STRIP_XI_BIU_DES = 0.667          # biuret formation : 2 Urea -> Biuret + NH3
# --- Design strip fractions to top gas (calibrated to the shared streams):
STRIP_FRAC_DES = {"NH3": 0.8546, "CO2": 0.8606, "H2O": 0.1313, "N2": 0.9987, "O2": 0.975,
                  "Urea": 0.0, "Biuret": 0.0, "CH4": 0.999, "H2": 0.999}
# --- Shell steam side (329D005 HP steam drum) + duty:
STRIP_STEAM_KGH_DES = 75300.0     # kg/h saturated MP steam (design)
STRIP_STEAM_P_DES_BARA = 19.7     # bar a, design 329D005 steam supply (eta_T normalization ref)
STRIP_STEAM_P_BARA  = 19.7        # bar a, LIVE 329D005 steam supply pressure (sensitivity lever)
STRIP_STEAM_T_DES_C = tsat_steam(STRIP_STEAM_P_DES_BARA)  # C, sat-steam T at design P (= 211.6)
STRIP_DUTY_DES_KW   = 39400.0     # kW, design heat duty
STRIP_P_DES_BARA    = 144.0       # bar a, tube-side (synthesis-loop) pressure
# --- Design product temperatures (C):
STRIP_T_TOPGAS_DES_C = 187.0      # TT-322013 top gas -> 322E002
STRIP_T_BOTTOM_DES_C = 172.0      # TT-322004 bottom solution -> LV-322501 (pre-flash)
# --- N/C + H/C stripping-efficiency penalty + Arrhenius biuret (live reactor-effluent coupling) ---
#   Design stripper feed = stream-207 overflow + CO2 strip gas (molfrac x design CO2 rate).  L0/W0/U0
#   anchors are DERIVED from existing design constants (no fabricated numbers); differ from the
#   reactor-feed N/C because the stripper feed includes the CO2 sweep gas.
_STRIP_FEED_DES = {k: STRIP_FEED207_KMOLH.get(k, 0.0)
                   + CO2_FEED_MOLFRAC.get(k, 0.0) * CO2_DES_KMOLH for k in MW_COMP}
STRIP_L0    = _STRIP_FEED_DES["NH3"] / _STRIP_FEED_DES["CO2"]    # 1.9045  design feed N/C
STRIP_W0    = _STRIP_FEED_DES["H2O"] / _STRIP_FEED_DES["CO2"]    # 1.0610  design feed H/C
STRIP_UREA0 = _STRIP_FEED_DES["Urea"]                           # 1302.6  design feed urea (kmol/h)
STRIP_ETA_KN    = 1.50     # eta_T penalty per unit reactor-feed N/C above design (excess NH3 chokes)
STRIP_ETA_KW    = 1.50     # eta_T penalty per unit reactor-feed H/C above design (dilution chokes)
STRIP_ETA_FLOOR = 0.50     # min penalty factor (g_NC, g_HC clamp floor)
STRIP_SLIP_GAIN = 4.0      # NH3/CO2 overhead breakthrough gain per unit choke (vapour pushed to HPCC)
STRIP_BIU_EA    = 85000.0  # J/mol  biuret-formation activation energy (Arrhenius)
STRIP_R_GAS_J   = 8.314    # J/mol-K  gas constant
STRIP_T_BIU_DES_K = STRIP_T_BOTTOM_DES_C + 273.15   # 445.15 K  biuret Arrhenius ref (design bottom T)
STRIP_T_DOWN_DES_C   = 119.0      # TT-323001 post-LV flash -> 323C003
STRIP_BOT_DES_KGH    = 130482.0   # kg/h design bottom-solution flow (= model design bottom)
# --- Bottom-sump level (LIC-322501 -> LV-322501): bottom head ID 2430 mm:
STRIP_SUMP_AREA_M2  = 4.638       # m2, pi/4 * 2.43^2 bottom-head cross-section
STRIP_LEVEL_SPAN_M  = 1.5         # m, liquid band for 0..100 % (LT-322501 span)
STRIP_RHO_BOTTOM    = 1134.64     # kg/m3, bottom-solution density (LV inlet, 172 C)
STRIP_LEVEL_SP_DES  = 50.0        # %, design level setpoint (LIC-322501)
# Direct-acting PI on the bottom-sump level.  Level is an INTEGRATING process, so the loop
# must be proportional-dominant (pure-I -> 2 integrators -> limit cycle); velocity form.
LIC_322501_KC       = 2.5         # %OP per %level (proportional gain)
LIC_322501_TI       = 90.0        # s, integral time

# ----- LV-322501 bottom-solution level control valve --------------------------------------
#   Datasheet: DN-90 angle, parabolic plug single-seat, LINEAR char, Kvs=36, FC (fail-closed),
#   air-to-open (4 mA closed / 20 mA open).  p1 143.7 -> p2 4.2 bar a (flashing), t1 173 C,
#   rho 1134.64; norm 114.58 m3/h ~ 82 % stroke, max 126.1 m3/h ~ 90 %.  Flashing service +
#   manufacturer Kv method -> textbook Kv eq over-predicts ~3x; the two datasheet operating
#   points are LINEAR, so flow is modelled linear in opening anchored at the design point
#   (effective dP folded into the constant), with mild sqrt(dP) synthesis-pressure coupling.
#   LIC-322501 DIRECT-acting on the FC valve = correct negative feedback (level^ -> drain^).
LV322501_KVS        = 36.0        # m3/h flow coefficient (full open) [reference]
LV322501_OPEN_DES   = 82.0        # %, opening at the design bottom-solution flow
LV322501_DP_DES_BAR = 139.8       # bar, design pressure drop (144.0 - 4.2)
STRIP_P_DOWN_BARA   = 4.2         # bar a, downstream of LV-322501 (-> 323C003)


def ejector_322f001(motive_nh3_kgh: float, T_motive_C: float, hv_open_pct: float) -> dict:
    """322F001 HP ejector: mix live motive NH3 with entrained 322E003 carbamate.
    Entrainment is set by the HV-322602 spindle opening (HIC-322602): decreasing the
    opening raises mu -> more 322E003 carbamate suction.  At the design opening (74 %)
    mu = EJ_MU and the discharge reproduces the design 'Carb. Liq.' table.  Energy
    balance sets discharge temp.  Returns the discharge stream (-> 322E002) + props."""
    if motive_nh3_kgh <= 1e-6:
        return {"comp": {k: 0.0 for k in MW_COMP}, "total_kgh": 0.0, "suction_kgh": 0.0,
                "mol_kmolh": 0.0, "MW": 0.0, "T_C": 0.0, "P_bara": 0.0,
                "rho": 0.0, "vol_m3h": 0.0, "mu": 0.0}
    # HV-322602 (HIC-322602) sets entrainment: decreasing opening -> more 322E003 suction.
    open_eff = clamp(hv_open_pct, 10.0, 100.0)
    mu       = EJ_MU * (EJ_OPEN_DES / open_eff)          # = EJ_MU at design opening (74 %)
    m_suc    = mu * motive_nh3_kgh
    suction  = {k: m_suc * EJ_CARB_FRAC[k] for k in MW_COMP}
    disch   = {k: (motive_nh3_kgh if k == "NH3" else 0.0) + suction[k] for k in MW_COMP}
    m_d   = sum(disch.values())
    n_d   = sum(disch[k] / MW_COMP[k] for k in MW_COMP)   # kmol/h
    m_suc = sum(suction.values())
    # energy balance: m_d*cpD*T_d = m_mot*cpN*T_mot + m_suc*cpC*T_suc
    T_d = (motive_nh3_kgh*EJ_CP_N*T_motive_C + m_suc*EJ_CP_C*EJ_T_SUCTION_C) / (m_d*EJ_CP_D)
    return {"comp": disch, "total_kgh": m_d, "suction_kgh": m_suc, "mol_kmolh": n_d,
            "MW": (m_d/n_d if n_d else 0.0), "T_C": T_d, "P_bara": EJ_P_DISCH_BARA,
            "rho": EJ_RHO_DISCH, "vol_m3h": m_d/EJ_RHO_DISCH, "mu": m_suc/motive_nh3_kgh}


def psat_nh3_bara(T_C: float) -> float:
    """NH3 saturated vapour pressure (bar a) via NIST Antoine, valid ~239-372 K:
           log10(P[bar]) = A - B / (T[K] + C)
       A=4.86886, B=1113.928, C=-10.409."""
    A, B, C = 4.86886, 1113.928, -10.409
    T = T_C + 273.15
    return 10.0 ** (A - B / (T + C))


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def stripper_322e001(co2_feed_th: float, T_steam_C: float, P_bara: float,
                     overflow_kmolh: dict = None, L_feed: float = None,
                     W_feed: float = None) -> dict:
    """HP Stripper 322E001 reduced steady-state model.
    Top liquid feed = 322R001 overflow (boundary constant, stream 207).
    Bottom strip gas = live CO2 feed (co2_feed_th, t/h).  Shell = condensing MP steam.
    Splits each component to top gas (-> 322E002) and bottom solution (-> LV-322501) using
    design strip fractions modulated by steam T, CO2 strip-gas ratio and pressure.  Reactions
    (urea hydrolysis + biuret formation) carry the component-balance deltas.  At design
    conditions reproduces the shared HMB exactly.  Returns both product streams + props."""
    # 1. component molar feed (kmol/h): reactor effluent (live overflow, 1-step lag) + CO2 strip gas
    if overflow_kmolh is None:
        overflow_kmolh = STRIP_FEED207_KMOLH          # frozen design vector (backward-compat)
    co2_scale = co2_feed_th / (CO2_DES_KGH / 1000.0)                     # 1.0 at design
    co2_kmolh = {k: CO2_FEED_MOLFRAC.get(k, 0.0) * CO2_DES_KMOLH * co2_scale for k in MW_COMP}
    feed = {k: overflow_kmolh.get(k, 0.0) + co2_kmolh.get(k, 0.0) for k in MW_COMP}

    # 2. stripping efficiency: steam heat, PENALIZED by feed N/C and H/C.  Excess NH3 (high N/C) and
    #    dilution (high H/C) make the solution harder to thermally strip without a CO2 sweep.
    #    The reduced reactor PINS its overflow N/C (atom-conserving ripple), so the disturbance is
    #    carried by the REACTOR-FEED N/C / H/C (1-step lag) -- the same ratios that drop conversion
    #    and load the stripper.  Anchored to reactor design (L0_DES / W0_DES) -> g=1.0 at design.
    dTs = T_steam_C - STRIP_STEAM_T_DES_C
    eta_T_steam = clamp(T_steam_C / STRIP_STEAM_T_DES_C, 0.0, 1.15)      # thermal part (1.0 at design)
    L_react = reactor.L0_DES if L_feed is None else L_feed              # reactor-feed N/C
    W_react = reactor.W0_DES if W_feed is None else W_feed              # reactor-feed H/C
    g_NC = clamp(1.0 - STRIP_ETA_KN * (L_react - reactor.L0_DES), STRIP_ETA_FLOOR, 1.05)
    g_HC = clamp(1.0 - STRIP_ETA_KW * (W_react - reactor.W0_DES), STRIP_ETA_FLOOR, 1.05)
    eta_T = clamp(eta_T_steam * g_NC * g_HC, 0.0, 1.15)                  # reported strip efficiency
    L_strip = (feed["NH3"] / feed["CO2"]) if feed["CO2"] else STRIP_L0   # stripper-feed N/C (diag)
    W_strip = (feed["H2O"] / feed["CO2"]) if feed["CO2"] else STRIP_W0   # stripper-feed H/C (diag)

    # 3. reactions: hydrolysis scales with penalized eta_T; biuret = Arrhenius k0 exp(-Ea/RT)*[Urea].
    T_bot_K = (STRIP_T_BOTTOM_DES_C + 0.7 * dTs) + 273.15
    xi_hyd = STRIP_XI_HYD_DES * eta_T
    xi_biu = (STRIP_XI_BIU_DES
              * math.exp((STRIP_BIU_EA / STRIP_R_GAS_J) * (1.0 / STRIP_T_BIU_DES_K - 1.0 / T_bot_K))
              * (feed["Urea"] / STRIP_UREA0))                           # 0.667 at design (ratio=1)
    avail = dict(feed)
    avail["Urea"]   -= (xi_hyd + 2.0 * xi_biu)
    avail["Biuret"] += xi_biu
    avail["NH3"]    += (2.0 * xi_hyd + xi_biu)
    avail["CO2"]    += xi_hyd
    avail["H2O"]    -= xi_hyd
    for k in avail:
        avail[k] = max(avail[k], 0.0)

    # 4. strip-fraction modulation: thermal steam heat x CO2 strip-gas dilution x synthesis-pressure
    #    (=1.0 at design).  The N/C+H/C choke does NOT cut the thermal split; instead it forces
    #    volatile NH3/CO2 BREAKTHROUGH to the overhead (slip), raising the vapour load back to HPCC.
    eta_co2 = clamp(0.5 + 0.5 * co2_scale, 0.4, 1.05)
    eta_P   = clamp(2.0 - P_bara / STRIP_P_DES_BARA, 0.85, 1.15)
    mod = clamp(eta_T_steam * eta_co2 * eta_P, 0.0, 1.12)
    slip = max(1.0 - g_NC, 0.0) + max(1.0 - g_HC, 0.0)                  # 0.0 at design
    top = {}; bot = {}
    for k in MW_COMP:
        f = clamp(STRIP_FRAC_DES.get(k, 0.0) * mod, 0.0, 0.999)
        if k in ("NH3", "CO2"):
            f = clamp(f + STRIP_SLIP_GAIN * slip * (1.0 - f), 0.0, 0.999)  # volatile breakthrough
        top[k] = avail[k] * f
        bot[k] = avail[k] * (1.0 - f)

    # 5. stream totals (kg/h) + intensive props
    top_kgh = {k: top[k] * MW_COMP[k] for k in MW_COMP}
    bot_kgh = {k: bot[k] * MW_COMP[k] for k in MW_COMP}
    top_m = sum(top_kgh.values()); top_n = sum(top.values())
    bot_m = sum(bot_kgh.values()); bot_n = sum(bot.values())
    return {
        "feed_kmolh": feed, "co2_feed_kmolh": co2_kmolh, "top_kmolh": top, "bot_kmolh": bot,
        "top_kgh": top_m, "bot_kgh": bot_m,
        "top_th": top_m / 1000.0, "bot_th": bot_m / 1000.0,
        "top_mol": top_n, "bot_mol": bot_n,
        "top_MW": (top_m / top_n if top_n else 0.0),
        "bot_MW": (bot_m / bot_n if bot_n else 0.0),
        "top_comp_pct": {k: (top[k] / top_n * 100.0 if top_n else 0.0) for k in MW_COMP},   # mol %
        "bot_mass_pct": {k: (bot_kgh[k] / bot_m * 100.0 if bot_m else 0.0) for k in MW_COMP},# mass %
        "T_top": STRIP_T_TOPGAS_DES_C + 0.6 * dTs,
        "T_bot": STRIP_T_BOTTOM_DES_C + 0.7 * dTs,
        "xi_hyd": xi_hyd, "xi_biu": xi_biu, "eta_T": eta_T, "T_steam": T_steam_C,
        "eta_T_steam": eta_T_steam, "g_NC": g_NC, "g_HC": g_HC,
        "L_strip": L_strip, "W_strip": W_strip, "slip": slip,
    }


# Design-point stripper top-gas molar flow + synthesis-pressure coupling gain (PT-329201).
# Higher steam Tsat -> higher stripping efficiency -> more overhead (off-gas) returned to the
# HP synthesis loop -> higher synthesis pressure (plant reference, carbamate-condenser path).
_STRIP_TOP_DES    = stripper_322e001(CO2_DES_KGH / 1000.0,
                                     STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA)["top_kmolh"]
STRIP_TOP_MOL_DES = sum(_STRIP_TOP_DES.values())                # 5789.4018 design overhead (kmol/h)
STRIP_TOP_NH3_DES = _STRIP_TOP_DES["NH3"]                       # 3571.6 design overhead NH3 (condensable)
# Pressure-building acid anchor = design CO2 NOT paired into carbamate (2 NH3 + CO2 -> carbamate):
STRIP_TOP_CO2FREE_DES = max(_STRIP_TOP_DES["CO2"] - 0.5 * _STRIP_TOP_DES["NH3"], 0.0)  # 98.6 free CO2
SYN_P_COUPLING = 1.0              # synthesis-P sensitivity to pressure-building (free-CO2) overhead push

# ---- HP Carbamate Condenser 322E002 (HPCC) -------------------------------
# Reduced split-fraction condensation model, calibrated EXACT to the design HMB.
# Tube side (process): hot strip gas (322E001 top, TT-322013) + recycle carbamate liquid
#   (322F001 ejector discharge, TT-322012) enter the top channel and flow co-current downward;
#   NH3/CO2 condense into the falling film forming ammonium carbamate, leaving a two-phase
#   product to HP reactor 322R001 (gas overhead + liquid TT-322010).
# Shell side (utility): BFW/condensate from 322D001 A/B (TT-329001) boils -> 4.4 bar a LP steam.
# Design HMB shows urea unchanged across 322E002, so at calibration the unit is a pure component
# phase-split: gas fraction phi_i of each combined-feed component leaves as gas, (1-phi_i) as liq.
HPCC_FRAC_GAS_DES = {            # design split fraction of each feed component leaving AS GAS
    "CO2": 0.2036, "NH3": 0.2977, "H2O": 0.0450,
    "N2": 0.982,  "O2": 1.0,    "CH4": 1.0,  "H2": 1.0,
    "Urea": 0.0,  "Biuret": 0.0,
}
HPCC_T_PROD_DES_C  = 170.0       # two-phase outlet temp (gas & liquid TT-322010) at design (C)
HPCC_P_DES_BARA    = 144.2       # synthesis-loop pressure at HPCC outlet (bar a)
HPCC_STEAM_P_BARA  = 4.4         # shell-side LP steam pressure (bar a)
HPCC_STEAM_TSAT_C  = 146.3       # T_sat(4.4 bar a): shell condensing temp + BFW feed (TT-329001)
HPCC_DH_CARB_KJMOL = 160.0       # carbamate exotherm 2NH3+CO2->NH2COONH4 (kJ/mol CO2 absorbed)
HPCC_CP_GAS        = 2.0         # mean strip-gas cp for sensible duty (kJ/kg.K)
HPCC_LATENT_4BAR   = 2120.0      # latent heat of 4.4 bar a steam (kJ/kg)

# ----- 322R001 HP Urea Reactor (reduced calibrated split-fraction, pinned to design HMB) -----
#   Products pinned to shared HMB:  ṅᵒᵛ_i = νᵒᵛ_des,i · s · (φ/φ_des) ;  ṅᵒᵍ_i = νᵒᵍ_des,i · s
#   s  = CO₂ throughput ratio (= stripper co2_scale);  φ = HV-322605 opening fraction.
# Overflow design vector IS stream 207 (322R001 overflow = 322E001 feed) -> derive from the
# single source of truth so the design point is bit-identical and DRY.
#   Documented literals (kmol/h): Urea 1302.6, Biuret 2.414, NH3 4002.4, CO2 897.7, H2O 2222.0.
REACT_OVERFLOW_DES = {k: STRIP_FEED207_KMOLH.get(k, 0.0) for k in MW_COMP}   # Σ ≈ 8427.11
REACT_OFFGAS_DES   = {"NH3": 665.73, "CO2": 197.69, "N2": 44.53, "H2O": 42.51,
                      "O2": 7.42, "CH4": 3.86, "H2": 2.02, "Urea": 0.0, "Biuret": 0.0}  # Σ ≈ 963.76
REACT_XI_UREA_DES  = 1302.27     # urea-formation extent at design (kmol/h)
REACT_XI_BIU_DES   = 2.414       # biuret-formation extent at design (kmol/h)
REACT_HIC605_DES_PCT = 60.0      # φ_des: HV-322605 design opening (Kv_req/Kvs, linear trim)
REACT_OVERFLOW_T_C = 183.0       # TT-322014 overflow temp -> 322E001
REACT_OFFGAS_T_C   = 183.0       # TT-322009 gas-line temp -> 322E003
REACT_P_BARA       = 144.9       # reactor operating pressure (bar a)
REACT_OFFGAS_P_BARA = 141.3      # off-gas line pressure -> 322E003 (bar a)
REACT_OVERFLOW_RHO = 990.0       # urea solution density (kg/m³)
REACT_OFFGAS_RHO   = 113.30      # off-gas density (kg/m³)
# --- TT-322005/6/7/8 axial temperature profile (residence-time model, datasheet N6 A/B/C/D) ---
# Liquid plug-flow rises from bottom T.L (+0); thermowell elevations (mm) traced from nozzles
# N6 A/B/C/D on Reactor Datasheet2.  tau(z)=(z/H_L)*tau_tot ; first-order thermal approach to the
# outlet temp:  T(tau)=T_out-(T_out-T_in)*exp(-tau/tau_T).  T_in=HPCC feed 170 C (TT-322010/012),
# T_out=overflow 183 C (TT-322014); tau_T = carbamate-exotherm thermal time constant.
REACT_ID_MM          = 2950.0    # reactor inside diameter (datasheet shell 2950 ID)
REACT_LIQ_H_MM       = 25000.0   # liquid height bottom T.L -> top T.L (overflow zone)
REACT_THERM_TAU_MIN  = 8.0       # carbamate-exotherm thermal time constant (min)
REACT_TT_EL_MM = {"TT_322005": 21700.0, "TT_322006": 14800.0,    # N6 A (top), N6 B
                  "TT_322007": 7900.0,  "TT_322008": 1000.0}      # N6 C, N6 D (bottom)
_react_area_m2   = (math.pi / 4.0) * (REACT_ID_MM / 1000.0) ** 2
_react_mdot_kgh  = sum(REACT_OVERFLOW_DES[k] * MW_COMP[k] for k in MW_COMP)   # design overflow kg/h
_react_vdot_m3h  = _react_mdot_kgh / REACT_OVERFLOW_RHO
REACT_TAU_TOT_MIN = (_react_area_m2 * (REACT_LIQ_H_MM / 1000.0) / _react_vdot_m3h) * 60.0  # ~44.9 min


def _react_tt_temp(el_mm: float) -> float:
    """Liquid temperature at thermowell elevation el_mm (mm above bottom T.L)."""
    tau = (el_mm / REACT_LIQ_H_MM) * REACT_TAU_TOT_MIN               # residence time to elevation
    return REACT_OVERFLOW_T_C - (REACT_OVERFLOW_T_C - HPCC_T_PROD_DES_C) * math.exp(-tau / REACT_THERM_TAU_MIN)


REACT_TT_TEMPS_C = {tag: _react_tt_temp(el) for tag, el in REACT_TT_EL_MM.items()}  # 182.9/182.5/180.8/172.6
REACT_LEVEL_NLL_PCT  = 80.0      # LT-322504 top normal liquid level (% at design φ=φ_des)
REACT_V_SPAN_M3      = _react_area_m2 * (REACT_LIQ_H_MM / 1000.0)   # liquid-span volume LT 0->100 %
# AT-322701 analyzer: atom-count N/C molar ratio of 322R001 overflow (Σnᵢ·#Nᵢ)/(Σnᵢ·#Cᵢ)
REACT_N_ATOMS = {"NH3": 1, "Urea": 2, "Biuret": 3, "N2": 2}
REACT_C_ATOMS = {"CO2": 1, "Urea": 1, "Biuret": 2, "CH4": 1}
# statics (display only): H 25000 mm, ID 2950 mm, 11 sieve trays, volume 191 m³

# ----- 322E003 HP Scrubber (reactive falling-film absorber, pinned split-fraction) -----------
#   Tube side, counter-current: inert-rich reactor off-gas (322R001 -> TT-322009, live
#   react["offgas_kmolh"]) rises through the tubes; cold weak carbamate wash (323P001 A/B,
#   design vector) falls as a film.  NH3/CO2/H2O are recovered by instantaneous carbamate
#   formation 2NH3(aq)+CO2(aq) <=> NH2COONH4(l), dH≈-160 kJ/mol; inerts (N2/O2/CH4/H2) slip to
#   the off-gas.  BOTH discharges are PINNED to the shared design HMB (proven IDENTICAL by
#   compare_scrubber.py); closure_resid is a diagnostic only (NOT injected into any stream):
#     off-gas  322E003 -> TT-322011 -> HV-322604 -> 322C001 LP absorber  (img1, MOL%, 64.78 kmol/h)
#     overflow 322E003 -> PT-329201/TT-322002/LT-329501 -> 322F001       (= EJ_SUCTION, ejector suction)
#       off-gasᵢ = νᵒᵍ_des,i · s ;  overflowᵢ = νᵒᵛ_des,i · s ;  s = react co2_scale.
SCRUB_CARB_KGH_DES   = 36915.0   # kg/h design weak-carbamate wash (323P001 A/B -> 322E003)
SCRUB_CARB_MASSPCT   = {"CO2": 38.49, "H2O": 30.83, "NH3": 30.61, "Urea": 0.07}   # img2 MASS%
SCRUB_CARB_KMOLH_DES = {k: SCRUB_CARB_MASSPCT.get(k, 0.0) / 100.0 * SCRUB_CARB_KGH_DES / MW_COMP[k]
                        for k in MW_COMP}                            # Σ ≈ 1618.5 kmol/h
SCRUB_OFFGAS_MOLPCT  = {"N2": 68.81, "O2": 11.39, "NH3": 8.26, "CH4": 5.93,       # img1 MOL%
                        "H2": 3.14, "CO2": 2.22, "H2O": 0.26}
SCRUB_OFFGAS_MOL_DES = 64.78     # kmol/h design off-gas total (322E003 -> 322C001)
SCRUB_OFFGAS_KMOLH_DES = {k: SCRUB_OFFGAS_MOLPCT.get(k, 0.0) / 100.0 * SCRUB_OFFGAS_MOL_DES
                          for k in MW_COMP}
# Overflow design vector IS the 322F001 ejector suction (single source of truth -> DRY, bit-identical):
SCRUB_OVERFLOW_KMOLH_DES = {k: EJ_SUCTION_KGH[k] / MW_COMP[k] for k in MW_COMP}   # Σ ≈ 2519.4 kmol/h
SCRUB_CARB_T_C       = 74.0      # C, weak-carbamate wash inlet (323P001 A/B)
SCRUB_CARB_P_BARA    = 140.7     # bar a, carbamate feed line
SCRUB_CARB_RHO       = 1226.0    # kg/m³, carbamate density (74 C)
SCRUB_OFFGAS_T_C     = 114.0     # C, TT-322011 off-gas temp -> HV-322604 (design)
SCRUB_OFFGAS_P_BARA  = 140.7     # bar a, off-gas line pressure (synthesis)
SCRUB_OFFGAS_RHO     = 111.0     # kg/m³, off-gas density (114 C, 140.7 bar a)
SCRUB_OVERFLOW_T_C   = 178.8     # C, TT-322002 overflow temp -> 322F001 (= EJ_T_SUCTION_C)
SCRUB_OVERFLOW_P_BARA = 140.7    # bar a, PT-329201 overflow-line pressure
SCRUB_DH_CARB_KJMOL  = 160.0     # kJ/mol CO2 absorbed, carbamate-formation exotherm (diagnostic)
# --- HV-322604 off-gas valve (choked isenthalpic letdown 322E003 -> 322C001) ---
SCRUB_HIC604_DES_PCT = 50.0      # %, HIC-322604 design opening (HV-322604, inert purge)
SCRUB_HV604_P_OUT    = 4.0       # bar a, 322C001 LP-absorber downstream pressure
SCRUB_HV604_MU_JT    = 0.55      # C/bar, mixture Joule-Thomson coeff (NH3/CO2-rich off-gas)
# --- Shell-side CCW (Conditioning Cooling Water) closed loop: 329P006 A/B pump + 329E004 cooler ---
#   322E003 shell -- TT-329125 -- 329P006 A/B -- FV-329409/FIC-329409 -- TIC-329005 -- shell in;
#   branch after 329P006: TV-329005 -- 329E002 -- main CCW header (heat rejected via 329E004).
#   Q_ccw = ṁ_ccw·cp·ΔT removes the condensation/reaction heat; design-pinned, throughput-scaled.
#   TT-329125 = TIC-329005 + Q_ccw/(ṁ_ccw·cp);  TDY-329125 = TT-329125 − TIC-329005 (cond. quality).
SCRUB_CCW_KGH_DES    = 306000.0  # kg/h design CCW circulation (329P006 A/B, 306 t/h)
SCRUB_CCW_CP         = 4.18      # kJ/kg.K, water
SCRUB_CCW_T_IN_DES   = 80.0      # C, TIC-329005 supply into shell (design SP)
SCRUB_CCW_T_OUT_DES  = 95.0      # C, TT-329125 return out of shell (design)
SCRUB_CCW_P_IN_BARA  = 9.0       # bar a, CCW supply (stream 1111)
SCRUB_CCW_P_OUT_BARA = 8.0       # bar a, CCW return (stream 1112)
SCRUB_CCW_RHO_IN     = 971.8     # kg/m³, water @ 80 C
SCRUB_CCW_RHO_OUT    = 961.9     # kg/m³, water @ 95 C
SCRUB_FV409_DES_PCT  = 60.0      # %, FV-329409 design opening (FIC-329409 -> CCW flow)
SCRUB_TV005_DES_PCT  = 50.0      # %, TV-329005 design opening (TIC-329005 -> 329E002 branch)
# ---- Synthesis-loop pressure coupling (322E002 bubble-P  +  PT-329201 reverse Q->P) ----------
# (1) HPCC 322E002 bubble-point: P_bub(T, N/C, H/C) replaces the pinned synthesis-loop outlet P.
#     Reduced Clausius-Clapeyron T-slope x separable N/C, H/C modifiers, anchored bit-exact to the
#     design combined feed (reactor.L0_DES/W0_DES @ HPCC_T_PROD_DES_C) so that
#     bubble_p_322e002(170, L0_DES, W0_DES) == HPCC_P_DES_BARA (144.2).  Free NH3 (N/C) lifts the
#     melt vapour pressure (kN>0); water (H/C) dilutes the volatiles (kW<0).
HPCC_BUB_DHVAP_JMOL = 23000.0    # J/mol, effective NH3-dominated vaporisation enthalpy (C-C slope)
HPCC_BUB_KN         = 0.18       # 1/(N/C), bubble-P sensitivity to feed N/C (free NH3)   -- calib
HPCC_BUB_KW         = -0.25      # 1/(H/C), bubble-P sensitivity to feed H/C (dilution)    -- calib
_HPCC_BUB_T0_K      = HPCC_T_PROD_DES_C + 273.15
# (2) PT-329201 reverse heat->pressure: the synthesis-loop top pressure is a DYNAMIC state.  CCW
#     flow sets the off-gas condensation capacity; when capacity < vent demand the uncondensed
#     vapour accumulates and lifts PT-329201.  rho_cond = (m_ccw/m_ccw_des)/(s*nu), nu = PT/PT_des.
#     First-order accumulation:  tau dPT/dt = PT_fwd + K_def*max(1-rho_cond,0)*PT_des - PT.
SYN_P_DES_BARA      = SCRUB_OVERFLOW_P_BARA   # 140.7 bar a, PT-329201 design (322E003 overflow line)
SYN_P_DEFICIT_GAIN  = 0.30       # bar/bar, PT lift per unit condensation deficit (1-rho_cond)  -- calib
SYN_P_TAU_MIN       = 4.0        # min, loop-pressure accumulation time constant (vapour inventory)
SYN_P_MIN_BARA      = 120.0      # bar a, PT clamp floor
SYN_P_MAX_BARA      = 175.0      # bar a, PT clamp ceiling (relief margin)
SCRUB_Q_CCW_DES_KW   = SCRUB_CCW_KGH_DES * SCRUB_CCW_CP * (SCRUB_CCW_T_OUT_DES - SCRUB_CCW_T_IN_DES) / 3600.0  # ≈5329 kW


def bubble_p_322e002(T_c: float, L: float, W: float) -> float:
    """322E002 HPCC carbamate-melt bubble-point synthesis pressure (bar a) = f(T, N/C=L, H/C=W).
    Reduced Clausius-Clapeyron T-slope x separable N/C, H/C modifiers, anchored bit-exact at the
    design combined feed:  bubble_p_322e002(HPCC_T_PROD_DES_C, reactor.L0_DES, reactor.W0_DES)
    == HPCC_P_DES_BARA.  Monotone: dP/dT>0, dP/dL>0 (free NH3 volatility), dP/dW<0 (water dilution)."""
    cc = math.exp((HPCC_BUB_DHVAP_JMOL / reactor.R_GAS)
                  * (1.0 / _HPCC_BUB_T0_K - 1.0 / (T_c + 273.15)))
    fN = 1.0 + HPCC_BUB_KN * (L - reactor.L0_DES)      # free-NH3 (N/C) volatility lift
    fW = 1.0 + HPCC_BUB_KW * (W - reactor.W0_DES)      # water (H/C) dilution
    return HPCC_P_DES_BARA * cc * max(fN, 0.0) * max(fW, 0.0)


def hpcc_322e002(gas_feed: dict, liq_feed: dict) -> dict:
    """HP Carbamate Condenser 322E002 reduced model.
    gas_feed = stripper_322e001() return (top gas -> TT-322013); liq_feed = ejector_322f001()
    return (carbamate liquid -> TT-322012).  Combines both tube-side feeds and condenses NH3/CO2
    into the liquid via calibrated component split fractions (carbamate reaction implicit), then
    returns the two-phase products to 322R001 plus shell-side LP-steam duty.  Reproduces the
    shared gas- and liquid-product HMB exactly at design conditions."""
    # 1. combined tube-side feed (kmol/h per comp): strip gas (kmol/h) + ejector liq (kg/h -> kmol/h)
    feed = {k: gas_feed["top_kmolh"].get(k, 0.0)
               + liq_feed["comp"].get(k, 0.0) / MW_COMP[k] for k in MW_COMP}
    # 2. calibrated phase split: phi_i -> gas product, (1-phi_i) -> liquid product
    gas = {k: feed[k] * HPCC_FRAC_GAS_DES.get(k, 0.0) for k in MW_COMP}
    liq = {k: feed[k] - gas[k] for k in MW_COMP}
    gas_kgh = {k: gas[k] * MW_COMP[k] for k in MW_COMP}
    liq_kgh = {k: liq[k] * MW_COMP[k] for k in MW_COMP}
    gas_n = sum(gas.values());     liq_n = sum(liq.values())
    gas_m = sum(gas_kgh.values()); liq_m = sum(liq_kgh.values())
    # 3. shell-side duty + LP steam: carbamate exotherm (net CO2 absorbed) + gas sensible cooling
    co2_abs   = max(gas_feed["top_kmolh"].get("CO2", 0.0) - gas["CO2"], 0.0)   # kmol/h gas->liq
    q_carb_kw = co2_abs * 1000.0 * HPCC_DH_CARB_KJMOL / 3600.0
    q_sens_kw = gas_m * HPCC_CP_GAS * max(gas_feed["T_top"] - HPCC_T_PROD_DES_C, 0.0) / 3600.0
    duty_kw   = q_carb_kw + q_sens_kw
    steam_kgh = duty_kw * 3600.0 / HPCC_LATENT_4BAR
    # bubble-point synthesis pressure of the combined carbamate feed (N/C, H/C molar); replaces the
    # pinned HPCC_P_DES_BARA.  At design this feed's N/C, H/C == reactor.L0_DES/W0_DES -> P=144.2 exact.
    _co2   = feed.get("CO2", 0.0)
    L_hpcc = feed.get("NH3", 0.0) / _co2 if _co2 > 1e-9 else reactor.L0_DES
    W_hpcc = feed.get("H2O", 0.0) / _co2 if _co2 > 1e-9 else reactor.W0_DES
    p_bub  = bubble_p_322e002(HPCC_T_PROD_DES_C, L_hpcc, W_hpcc)
    return {
        "feed_kmolh": feed,
        "gas_kmolh": gas, "liq_kmolh": liq,
        "gas_kgh": gas_m, "liq_kgh": liq_m,
        "gas_th": gas_m / 1000.0, "liq_th": liq_m / 1000.0,
        "gas_mol": gas_n, "liq_mol": liq_n,
        "gas_MW": (gas_m / gas_n if gas_n else 0.0),
        "liq_MW": (liq_m / liq_n if liq_n else 0.0),
        "gas_mol_pct":  {k: (gas[k] / gas_n * 100.0 if gas_n else 0.0) for k in MW_COMP},   # mol %
        "liq_mass_pct": {k: (liq_kgh[k] / liq_m * 100.0 if liq_m else 0.0) for k in MW_COMP},# mass %
        "T_prod": HPCC_T_PROD_DES_C, "P_bara": p_bub,
        "P_bub": p_bub, "L_hpcc": L_hpcc, "W_hpcc": W_hpcc,
        "duty_kw": duty_kw, "steam_kgh": steam_kgh,
    }


def react_322r001(hpcc: dict, co2_feed_th: float, hic_322605_pct: float) -> dict:
    """322R001 HP urea reactor — reduced calibrated split-fraction, pinned to design HMB.
    overflow_i = nu_overflow_i,des * co2_scale * (phi/phi_des);  offgas_i = nu_offgas_i,des * co2_scale.
    closure_resid is reported as a diagnostic only (NOT injected back into any stream)."""
    s   = co2_feed_th / (CO2_DES_KGH / 1000.0)
    phi = hic_322605_pct / 100.0
    phi_des = REACT_HIC605_DES_PCT / 100.0
    overflow = {k: REACT_OVERFLOW_DES.get(k, 0.0) * s * (phi / phi_des) for k in MW_COMP}
    offgas   = {k: REACT_OFFGAS_DES.get(k, 0.0) * s for k in MW_COMP}
    xi_biu   = REACT_XI_BIU_DES * s
    feed     = hpcc["feed_kmolh"]
    # Modified Inoue-Kanai conversion coupling: shifts xi_urea + overflow by f(N/C, H/C, T),
    # atom-conserving, == design when feed is at (L0,W0,T0). closure_resid stays invariant.
    xi_urea, overflow, X_conv, L_feed, W_feed = reactor.react_couple(
        feed, overflow, REACT_XI_UREA_DES * s, REACT_OVERFLOW_T_C)
    closure_resid = (sum(feed.values())
                     - (sum(overflow.values()) + sum(offgas.values()))
                     - xi_urea)
    return {"overflow_kmolh": overflow, "offgas_kmolh": offgas, "feed_kmolh": feed,
            "xi_urea": xi_urea, "xi_biu": xi_biu, "closure_resid": closure_resid,
            "T_overflow": REACT_OVERFLOW_T_C, "T_offgas": REACT_OFFGAS_T_C,
            "P_bara": REACT_P_BARA, "P_offgas": REACT_OFFGAS_P_BARA,
            "phi": phi, "phi_des": phi_des, "co2_scale": s,
            "X_conv": X_conv, "L_feed": L_feed, "W_feed": W_feed}


def scrub_322e003(offgas_feed: dict, co2_scale: float, t_ccw_in: float,
                  m_ccw_kgh: float, vent_ratio: float = 1.0) -> dict:
    """322E003 HP scrubber — reduced calibrated split-fraction, pinned to the shared design HMB.
    Tube feeds: live reactor off-gas (offgas_feed kmol/h, 322R001 -> TT-322009) + weak carbamate
    wash (323P001 A/B design vector × s).  Both discharges PINNED (proven IDENTICAL):
        offgasᵢ   = SCRUB_OFFGAS_KMOLH_DES_i   · s   (322E003 -> HV-322604 -> 322C001)
        overflowᵢ = SCRUB_OVERFLOW_KMOLH_DES_i · s   (322E003 -> 322F001, ejector suction)
    closure_resid is a diagnostic only (NOT injected).  Shell-side CCW removes the carbamate
    exotherm.  Boundary-coupled duty: in a closed synthesis loop a rise in reactor-top pressure
    (PT-329201) lifts the uncondensed off-gas vent load into 322E003, so the carbamate-
    condensation exotherm Q_scrubber scales with the synthesis-vent ratio:
        Q_scrubber = q_ccw = SCRUB_Q_CCW_DES_KW · s · vent_ratio   (vent_ratio = PT-329201/PT_des)
    With ṁ_ccw constant the sensible-heat balance then lifts TT-329125 proportionally:
        TT-329125 = t_ccw_in + Q_scrubber/(ṁ_ccw·cp).  vent_ratio defaults to 1.0 (design-exact)."""
    s = co2_scale
    carb     = {k: SCRUB_CARB_KMOLH_DES.get(k, 0.0) * s for k in MW_COMP}      # 323P001 A/B wash
    feed     = {k: offgas_feed.get(k, 0.0) + carb[k] for k in MW_COMP}         # combined tube feed
    offgas   = {k: SCRUB_OFFGAS_KMOLH_DES.get(k, 0.0) * s for k in MW_COMP}    # pinned -> img1
    overflow = {k: SCRUB_OVERFLOW_KMOLH_DES.get(k, 0.0) * s for k in MW_COMP}  # pinned -> EJ suction
    closure_resid = sum(feed.values()) - sum(offgas.values()) - sum(overflow.values())
    co2_abs   = max(offgas_feed.get("CO2", 0.0) - offgas["CO2"], 0.0)          # kmol/h gas->carbamate
    q_carb_kw = co2_abs * 1000.0 * SCRUB_DH_CARB_KJMOL / 3600.0                # full exotherm (diag)
    q_ccw_kw  = SCRUB_Q_CCW_DES_KW * s * vent_ratio                            # Q_scrubber: carbamate-cond. duty (s × synthesis-vent load PT-329201)
    dT_ccw    = q_ccw_kw * 3600.0 / (m_ccw_kgh * SCRUB_CCW_CP) if m_ccw_kgh > 0 else 0.0
    t_ccw_out = t_ccw_in + dT_ccw                                              # TT-329125
    return {"feed_kmolh": feed, "carb_kmolh": carb,
            "offgas_kmolh": offgas, "overflow_kmolh": overflow,
            "closure_resid": closure_resid, "co2_abs": co2_abs,
            "q_carb_kw": q_carb_kw, "q_ccw_kw": q_ccw_kw,
            "t_ccw_in": t_ccw_in, "t_ccw_out": t_ccw_out, "dT_ccw": dT_ccw,
            "m_ccw_kgh": m_ccw_kgh, "co2_scale": s, "vent_ratio": vent_ratio,
            "T_offgas": SCRUB_OFFGAS_T_C, "P_offgas": SCRUB_OFFGAS_P_BARA,
            "T_overflow": SCRUB_OVERFLOW_T_C, "P_overflow": SCRUB_OVERFLOW_P_BARA}


def hv_322604(offgas: dict, T_in: float, hic_pct: float) -> dict:
    """HV-322604 HP-scrubber off-gas valve — choked isenthalpic letdown 322E003 -> 322C001.
    Inert purge to the LP absorber.  P drops ~140.7 -> 4 bar a (sonic/choked); Joule-Thomson
    cooling T_out = T_in − μ_JT·ΔP.  Steam-traced -> single gas phase preserved (no carbamate
    desublimation at healthy op); composition unchanged.  HIC-322604 sets the opening 1:1."""
    dP    = max(SCRUB_OFFGAS_P_BARA - SCRUB_HV604_P_OUT, 0.0)
    T_out = T_in - SCRUB_HV604_MU_JT * dP
    m_kgh = sum(offgas.get(k, 0.0) * MW_COMP[k] for k in MW_COMP)
    return {"comp_kmolh": dict(offgas), "T_out": round(T_out, 1),
            "P_out": SCRUB_HV604_P_OUT, "open_pct": hic_pct, "mass_kgh": m_kgh}


def react_nc_ratio(comp_kmolh: dict) -> float:
    """AT-322701: molar N/C ratio (Σ nᵢ·#Nᵢ)/(Σ nᵢ·#Cᵢ) of a stream on an atom basis."""
    n = sum(comp_kmolh.get(k, 0.0) * a for k, a in REACT_N_ATOMS.items())
    c = sum(comp_kmolh.get(k, 0.0) * a for k, a in REACT_C_ATOMS.items())
    return (n / c) if c else 0.0


def make_stream(comp_kmolh, T, P, name, src, dst, phase, rho=None):
    """Uniform process-stream object. Derives BOTH mol % and mass % from the same
    per-component kmol/h vector, so the two bases can never drift. rho unknown -> None
    -> density/volumetric flow render as '—' (no fabricated numbers)."""
    n = {k: comp_kmolh.get(k, 0.0) for k in MW_COMP}
    m = {k: n[k] * MW_COMP[k] for k in MW_COMP}
    n_tot = sum(n.values()); m_tot = sum(m.values())
    return {
        "name": name, "src": src, "dst": dst, "phase": phase,
        "T_C": round(T, 1), "P_bara": round(P, 1),
        "mass_kgh": round(m_tot, 1), "mass_th": round(m_tot / 1000.0, 3),
        "mol_kmolh": round(n_tot, 2),
        "MW": round(m_tot / n_tot, 3) if n_tot else 0.0,
        "rho": (round(rho, 1) if rho else None),
        "vol_m3h": (round(m_tot / rho, 2) if rho else None),
        "mol_pct":  {k: round(n[k] / n_tot * 100.0, 3) if n_tot else 0.0 for k in MW_COMP},
        "mass_pct": {k: round(m[k] / m_tot * 100.0, 3) if m_tot else 0.0 for k in MW_COMP},
    }


# ----- PID -----
class PID:
    def __init__(self, Kc=2.0, Ti=8.0, Td=0.0, op_lo=0.0, op_hi=100.0):
        self.Kc, self.Ti, self.Td = Kc, Ti, Td
        self.op_lo, self.op_hi = op_lo, op_hi
        self.integ, self.prev_e = 0.0, 0.0

    def step(self, sp, pv, dt):
        e = sp - pv
        self.integ += e * dt / max(self.Ti, 1e-6)
        self.integ = clamp(self.integ, -self.op_hi, self.op_hi)   # anti-windup
        d = (e - self.prev_e) / dt if dt > 0 else 0.0
        op = self.Kc * (e + self.integ + self.Td * d)
        op = clamp(op, self.op_lo, self.op_hi)
        self.prev_e = e
        return op


# ----- Controller / SIC faceplate -----
class Controller:
    """SIC on torque-converter valve opening (%).
       MAN : operator sets opening directly (PV entry -> op).
       AUTO: local SP% with PID.
       CAS : opening SP from ratio block + operator N/C bias (%).
       PV, SP, MV(op), N/C are all in percent."""

    def __init__(self, sp=80.0, op=0.0):
        self.mode = "MAN"
        self.sp   = sp     # % opening setpoint
        self.op   = op     # % opening output  (MV)
        self.pv   = 0.0    # % opening actual
        self.nc   = 0.0    # % cascade bias
        self.pid  = PID(Kc=2.0, Ti=8.0, op_lo=0.0, op_hi=100.0)

    def set_mode(self, mode, current_pv):
        if mode == "AUTO" and self.mode == "MAN":
            self.sp = current_pv          # bumpless: adopt current opening
        if mode == "CAS" and self.mode != "CAS":
            self.nc = 0.0                 # reset bias on cascade entry
        self.mode = mode

    def step(self, pv, dt, cas_sp=None):
        self.pv = pv
        if self.mode == "MAN":
            pass                          # op held by operator
        elif self.mode == "AUTO":
            self.op = self.pid.step(self.sp, pv, dt)
        elif self.mode == "CAS":
            if cas_sp is not None:
                self.sp = clamp(cas_sp + self.nc, 0.0, 100.0)
            self.op = self.pid.step(self.sp, pv, dt)
        return self.op


# ----- Pump model -----
def pump_flow_m3h(N_rpm: float) -> float:
    return max(0.0, N_rpm) * PUMP_V_PER_REV * PUMP_ETA_V * 60.0


def pump_shaft_power_kW(N_rpm: float, dP_bar: float) -> float:
    Q_m3s = pump_flow_m3h(N_rpm) / 3600.0
    return (Q_m3s * dP_bar * 1e5) / PUMP_ETA_M / 1000.0


def pump_current_A(N_rpm: float, on: bool) -> float:
    if not on:
        return 0.2
    return max(0.2, (max(0.0, N_rpm) / PUMP_RATED_RPM) * PUMP_RATED_I)


def mode_tag(c: "Controller") -> str:
    return {"MAN": "M", "AUTO": "A", "CAS": "C"}.get(c.mode, "M")


# ----- Plant state -----
class State:
    def __init__(self):
        # tank
        self.tank_level_frac = 0.65
        self.tank_T_C        = 25.0
        self.tank_P_top_barG = 12.3
        self.F_in_BL_th      = 40.756   # t/h, design NH3 feed from BL (40,756 kg/h)
        self.totalizer_t     = 177001.09
        # block valves (booleans: True = OPEN)
        self.XV_321901 = True
        self.XV_322901 = True
        # 322F001 ejector spindle opening (HIC-322602 -> HV-322602), % open
        self.HIC_322602 = 74.0
        # 322R001 HP urea reactor: HIC-322605 -> HV-322605 overflow valve opening (%)
        self.HIC_322605 = REACT_HIC605_DES_PCT          # φ_des = 60 %
        # reactor-overflow tear stream (synthesis recycle): the stripper feed consumes the
        # previous step's value (initialised to the design vector -> design = bit-identical).
        self.react_overflow_kmolh = dict(REACT_OVERFLOW_DES)
        self.react_L_feed = reactor.L0_DES   # 1-step-lag reactor-feed N/C -> stripper eta_T penalty
        self.react_W_feed = reactor.W0_DES   # 1-step-lag reactor-feed H/C -> stripper eta_T penalty
        # LT-322504 reactor liquid level (%) — DYNAMIC inventory state (mass balance, open-loop:
        # HV-322605 is hand/auto and does NOT control level). dV/dt = Q_in - Q_out(φ).
        self.react_level_pct = REACT_LEVEL_NLL_PCT      # init at design NLL = 80 %
        # pumps: open_act = torque-converter valve opening %
        self.pumpA = {"on": False, "open_act": 0.0,  "speed_act": 0.0,   "current": 0.2,  "mode": "M"}
        self.pumpB = {"on": True,  "open_act": 86.2, "speed_act": 131.0, "current": 43.9, "mode": "M"}
        # controllers (percent)
        self.SIC_321950 = Controller(sp=80.0, op=0.0)
        self.SIC_321951 = Controller(sp=86.2, op=86.2)   # MAN holds B at 86 %
        # ratio
        self.ratio_mode = "MAN"
        self.ratio_SP   = 1.928    # design molar N/C = (40.756/54.618)*2.584 (attached eq)
        self.ratio_PV   = 1.928    # molar N/C PV
        self.ratio_bal  = 1.928
        self.F_CO2_th   = 54.618   # t/h, actual CO2 feed to 322E001 (derived: raw - vent)
        # CO2 feed line (320K002 BL -> XV-322902 -> 322E001), vent via PV-322203
        self.F_CO2_raw_th = 54.618 # t/h, raw CO2 from 320K002 compressor (BL boundary)
        self.XV_322902    = True   # CO2 feed isolation to HP Stripper 322E001 (True=OPEN)
        self.HIC_322203   = 0.0    # %, HIC-322203 = PV-322203 minimum opening (operator)
        # PIC-322203 CO2 line-pressure controller -> PV-322203 opening (reverse-acting)
        self.PIC_322203   = {"mode": "MAN", "op": 0.0, "sp": CO2_P_DES_BARA, "pv": CO2_P_DES_BARA}
        # HP Stripper 322E001 bottom-sump level (LT-322501) + LIC-322501 -> LV-322501.
        #   AUTO holds the design level (50 %) at the design opening (82 %); direct-acting.
        self.strip_level = STRIP_LEVEL_SP_DES
        self.LIC_322501  = {"mode": "AUTO", "op": LV322501_OPEN_DES,
                            "sp": STRIP_LEVEL_SP_DES, "pv": STRIP_LEVEL_SP_DES, "e_prev": 0.0}
        # 322E003 HP scrubber off-gas valve: HIC-322604 -> HV-322604 (inert purge to 322C001).
        self.HIC_322604  = SCRUB_HIC604_DES_PCT          # % opening (automatic hand valve)
        # 322E003 shell-side CCW loop controllers (329P006 A/B pump + 329E004 tempered-water cooler):
        #   FIC-329409 -> FV-329409 (CCW circulation flow);  TIC-329005 -> TV-329005 (CCW supply T).
        #   Boundary-controlled tempered loop -> AUTO holds PV at SP at the design openings.
        self.FIC_329409  = {"mode": "AUTO", "op": SCRUB_FV409_DES_PCT,
                            "sp": SCRUB_CCW_KGH_DES / 1000.0, "pv": SCRUB_CCW_KGH_DES / 1000.0}  # t/h
        self.TIC_329005  = {"mode": "AUTO", "op": SCRUB_TV005_DES_PCT,
                            "sp": SCRUB_CCW_T_IN_DES, "pv": SCRUB_CCW_T_IN_DES}                  # C
        # PT-329201 synthesis-loop top pressure (DYNAMIC state, reverse Q->P accumulation):
        #   CCW condensation deficit lifts it; first-order relax to the forward stripper-set target.
        self.p_syn_bara  = SYN_P_DES_BARA                # init at design PT-329201 = 140.7 bar a
        # ext override
        self.ext_override = False
        # trips
        self.trips = {"21_2": False, "21_8": False, "21_10": False}


state = State()
clients: Set[WebSocket] = set()
last_packet: dict = {}


# ----- Sim step -----
def step_sim(dt: float) -> dict:
    s = state
    suct_open  = bool(s.XV_321901) and (s.tank_level_frac > 0.05)
    disch_open = bool(s.XV_322901)

    # ----- CO2 feed line (320K002 -> XV-322902 -> 322E001), vent via PV-322203 -----
    #   PV-322203 effective opening = max(HIC-322203 min, PIC-322203 op).  PIC-322203
    #   (reverse-acting) opens the vent when CO2 line P rises above SP.  Venting bleeds
    #   CO2 to safe location so the feed to 322E001 drops -> N/C ratio + Load follow.
    pic = s.PIC_322203
    if pic["mode"] == "AUTO":
        pic["op"] = clamp(pic["op"] + 0.5 * (pic["pv"] - pic["sp"]) * dt, 0.0, 100.0)
    pv_open = clamp(max(s.HIC_322203, pic["op"]), 0.0, 100.0)
    feed_factor = 1.0 if s.XV_322902 else 0.0          # isolation shut -> no feed
    f_vent = (pv_open / 100.0) * CO2_VENT_MAX_FRAC
    F_CO2_feed_kgh = s.F_CO2_raw_th * 1000.0 * (1.0 - f_vent) * feed_factor
    s.F_CO2_th = F_CO2_feed_kgh / 1000.0               # t/h actual feed -> drives ratio block
    CO2_feed_kmolh = F_CO2_feed_kgh / CO2_FEED_MW      # kmol/h
    FT_322403 = CO2_feed_kmolh * NM3_PER_KMOL          # Nm3/h  (FT-322403)
    FY_322403 = s.F_CO2_th                             # t/h    (FY-322403)
    Load_pct  = s.F_CO2_th / (CO2_DES_KGH / 1000.0) * 100.0   # % of design CO2 flow
    P_line_bara = CO2_P_DES_BARA - CO2_PV_DP_GAIN * pv_open   # PIC-322203 PV (bar a)
    pic["pv"] = P_line_bara

    # Cascade opening setpoint (%) from ratio flow demand.
    #   ratio_SP is molar N/C -> NH3 mass demand = (N/C)*(M_NH3/M_CO2)*m_CO2.
    F_NH3_sp_th    = s.ratio_SP * NC_TO_MASS * s.F_CO2_th
    Q_total_sp_m3h = F_NH3_sp_th * 1000.0 / NH3_RHO
    n_active       = (1 if s.pumpA["on"] else 0) + (1 if s.pumpB["on"] else 0)
    Q_per_pump     = Q_total_sp_m3h / max(n_active, 1)
    rpm_req        = Q_per_pump / (PUMP_V_PER_REV * PUMP_ETA_V * 60.0)
    open_cas       = clamp(rpm_req / PUMP_RATED_RPM * 100.0, 0.0, 100.0)

    # Drive each pump's converter opening toward controller output
    for p, ctrl in [(s.pumpA, s.SIC_321950), (s.pumpB, s.SIC_321951)]:
        ctrl.step(p["open_act"], dt, cas_sp=open_cas)      # updates op + pv
        if (not p["on"]) or (not suct_open) or (not disch_open):
            target = 0.0
        else:
            target = ctrl.op
        alpha = min(1.0, dt / 2.0)                         # tau ~ 2 s
        p["open_act"] += (target - p["open_act"]) * alpha
        p["open_act"]  = clamp(p["open_act"], 0.0, 100.0)
        p["speed_act"] = p["open_act"] / 100.0 * PUMP_RATED_RPM
        p["current"]   = pump_current_A(p["speed_act"], p["on"])
        p["mode"]      = mode_tag(ctrl)

    # Pump flows
    Q_A_m3h = pump_flow_m3h(s.pumpA["speed_act"]) if s.pumpA["on"] else 0.0
    Q_B_m3h = pump_flow_m3h(s.pumpB["speed_act"]) if s.pumpB["on"] else 0.0
    F_A_th  = Q_A_m3h * NH3_RHO / 1000.0                       # t/h NH3 pump A
    F_B_th  = Q_B_m3h * NH3_RHO / 1000.0                       # t/h NH3 pump B
    F_pump_total_th = F_A_th + F_B_th                          # t/h

    # Tank mass balance:  dM/dt = F_BL_in - F_pump_out   (BL makeup fills tank)
    dm_kg = (s.F_in_BL_th - F_pump_total_th) * 1000.0 / 3600.0 * dt
    V_new = clamp(s.tank_level_frac * TANK_VOL + dm_kg / NH3_RHO, 0.0, TANK_VOL)
    s.tank_level_frac = V_new / TANK_VOL
    s.totalizer_t += F_pump_total_th * dt / 3600.0          # FQI-321401: delivered NH3

    # 321D003 NH3 feed-drum energy balance -> TT-321001/TT-321002.
    #   M*cp*dT/dt = F_BL_in*cp*(T_BL - T_tank)   (adiabatic drum, Q_env ~ 0)
    # Subcooled liquid NH3 relaxes to the BL supply temp; sub-cooling held by PDY.
    M_tank_kg = s.tank_level_frac * TANK_VOL * NH3_RHO
    F_in_kgs  = s.F_in_BL_th * 1000.0 / 3600.0
    if M_tank_kg > 1.0:
        s.tank_T_C += (F_in_kgs * (T_BL_FEED_C - s.tank_T_C) / M_tank_kg) * dt

    # PT-321201/202 = NH3 feed (suction) pressure = upstream NH3 feed-stream
    #   pressure at tank 321D003 (= tank top operating pressure, bar g). Matches
    #   the AL feed-stream reading. Real suction head kept for physics + trips.
    P_suct_barG = (s.tank_P_top_barG
                   + (NH3_RHO * G * s.tank_level_frac * TANK_H) / 1e5
                   - 0.15)
    if not suct_open:
        P_suct_barG = 0.0
    PT_A = PT_B = s.tank_P_top_barG                          # bar g (feed-stream P)

    # PY-321201/202 = NH3 saturated vapour pressure at TT-321002 (bar a)
    PY = psat_nh3_bara(s.tank_T_C)
    # PDY-321203/204 = sub-cooling margin (bar) = P_feed(abs) - P_sat(abs); >0 => liquid
    PDY_A = (PT_A + P_ATM_BAR) - PY
    PDY_B = (PT_B + P_ATM_BAR) - PY

    # TI-321020 = common discharge temperature = T_suct + pump enthalpy rise
    #   dT = dP/(rho*cp) * ( beta*T + (1-eta_h)/eta_h )
    if (s.pumpA["on"] or s.pumpB["on"]) and disch_open:
        dP_pa   = max(0.0, P_SYN_DOWN_BAR - (P_suct_barG + P_ATM_BAR)) * 1e5
        T_K     = s.tank_T_C + 273.15
        dT_pump = dP_pa / (NH3_RHO * CP_NH3) * (BETA_NH3 * T_K + (1.0 - ETA_PUMP_HYD) / ETA_PUMP_HYD)
    else:
        dT_pump = 0.0
    TI_321020 = s.tank_T_C + dT_pump

    # 322F001 HP ejector: live motive NH3 (gated by XV-322901) + entrained carbamate
    #   -> discharge stream to 322E002 (TT-322012). Motive temp = TI-321020.
    motive_nh3_kgh = (F_pump_total_th * 1000.0) if disch_open else 0.0
    ej = ejector_322f001(motive_nh3_kgh, TI_321020, s.HIC_322602)

    # Ratio block PV = molar N/C per feed-ratio eq:  N/C = (m_NH3/m_CO2)*2.584.
    m_CO2 = max(s.F_CO2_th, 1e-6)
    NC_A  = (F_A_th / m_CO2) * NC_FACTOR      # N/C contributed by pump A
    NC_B  = (F_B_th / m_CO2) * NC_FACTOR      # N/C contributed by pump B
    s.ratio_PV  = NC_A + NC_B                 # total system N/C = (m_NH3_tot/m_CO2)*2.584
    s.ratio_bal = s.ratio_PV

    # ----- HP Stripper 322E001: reactor effluent + live CO2 strip gas -> top gas (322E002)
    #   + bottom solution (LV-322501).  Shell = condensing 329D005 MP steam (boundary T).
    # Stripper consumes the previous step's reactor overflow (tear stream of the synthesis
    # recycle); at design this equals the frozen STRIP_FEED207_KMOLH -> output unchanged.
    T_steam_live = tsat_steam(STRIP_STEAM_P_BARA)     # live sat-steam shell T from supply pressure
    strip = stripper_322e001(s.F_CO2_th, T_steam_live, STRIP_P_DES_BARA,
                             overflow_kmolh=s.react_overflow_kmolh,
                             L_feed=s.react_L_feed, W_feed=s.react_W_feed)

    # LIC-322501 bottom-solution level control, DIRECT-acting on the FC LV-322501:
    #   level^ -> op^ -> air-to-open valve opens -> drain^ -> level v  (neg. feedback).
    lic = s.LIC_322501
    e_lvl = s.strip_level - lic["sp"]          # direct-acting error (level above SP -> open)
    if lic["mode"] == "AUTO":                  # velocity-form PI (proportional-dominant)
        lic["op"] = clamp(lic["op"]
                          + LIC_322501_KC * ((e_lvl - lic["e_prev"]) + (dt / LIC_322501_TI) * e_lvl),
                          0.0, 100.0)
    lic["e_prev"] = e_lvl                       # track for bumpless MAN->AUTO
    lv_open = clamp(lic["op"], 0.0, 100.0)
    # LV-322501 linear characteristic anchored at design; mild sqrt(dP) synthesis coupling.
    dP_lv = max(STRIP_P_DES_BARA - STRIP_P_DOWN_BARA, 0.0)
    drain_kgh = STRIP_BOT_DES_KGH * (lv_open / LV322501_OPEN_DES) * (dP_lv / LV322501_DP_DES_BAR) ** 0.5
    # bottom-sump mass balance -> LT-322501 level (%)
    m_span_kg = STRIP_SUMP_AREA_M2 * STRIP_LEVEL_SPAN_M * STRIP_RHO_BOTTOM
    s.strip_level = clamp(s.strip_level
                          + (strip["bot_kgh"] - drain_kgh) / 3600.0 * dt / m_span_kg * 100.0,
                          0.0, 100.0)
    lic["pv"] = s.strip_level
    TT_323001 = STRIP_T_DOWN_DES_C + 0.7 * (strip["T_bot"] - STRIP_T_BOTTOM_DES_C)

    # HP carbamate condenser 322E002: strip gas + ejector liquid -> two-phase product to 322R001
    hpcc = hpcc_322e002(strip, ej)

    # 322R001 HP urea reactor: pinned products from hpcc feed, throughput s, valve φ.
    react = react_322r001(hpcc, s.F_CO2_th, s.HIC_322605)
    s.react_overflow_kmolh = react["overflow_kmolh"]   # tear -> next step's stripper feed
    s.react_L_feed = react["L_feed"]                   # tear -> next step's stripper eta_T penalty
    s.react_W_feed = react["W_feed"]

    # LT-322504 dynamic level — inventory mass balance (open-loop; HV-322605 sets only Q_out):
    #   Q_in  = V̇_des·s              (HPCC product fill, scales with CO₂ throughput)
    #   Q_out = V̇_des·s·(φ/φ_des)    (overflow letdown through HV-322605)
    #   dV/dt = Q_in - Q_out = V̇_des·s·(1 - φ/φ_des)  ->  level FALLS when φ>φ_des (valve opened).
    q_in_m3h  = _react_vdot_m3h * react["co2_scale"]
    q_out_m3h = q_in_m3h * (react["phi"] / react["phi_des"]) if react["phi_des"] else q_in_m3h
    dV_m3     = (q_in_m3h - q_out_m3h) * dt / 3600.0
    s.react_level_pct = clamp(s.react_level_pct + dV_m3 / REACT_V_SPAN_M3 * 100.0, 0.0, 100.0)

    # ----- 322E003 HP Scrubber: reactor off-gas + weak carbamate (323P001 A/B) -> off-gas line
    #   (322C001 via HV-322604) + overflow line (322F001).  Shell-side CCW loop (329P006 A/B
    #   circulation + 329E004 tempered-water cooler) removes the carbamate-formation exotherm.
    fic = s.FIC_329409                           # CCW circulation flow controller (FV-329409)
    tic = s.TIC_329005                           # CCW supply-temperature controller (TV-329005)
    if fic["mode"] == "AUTO":                     # boundary loop holds PV at SP; valve tracks SP
        fic["pv"] = fic["sp"]                      #   op = inverse of MAN valve char. (line below)
        fic["op"] = clamp(SCRUB_FV409_DES_PCT * fic["sp"] / max(SCRUB_CCW_KGH_DES / 1000.0, 1e-6),
                          0.0, 100.0)
    else:                                         # MAN: CCW flow follows FV-329409 opening
        fic["pv"] = (SCRUB_CCW_KGH_DES / 1000.0) * (fic["op"] / SCRUB_FV409_DES_PCT)
    if tic["mode"] == "AUTO":                      # boundary loop holds PV at SP; valve tracks SP
        tic["pv"] = tic["sp"]                      #   op = inverse of MAN valve char. (line below)
        tic["op"] = clamp(SCRUB_TV005_DES_PCT * (SCRUB_CCW_T_OUT_DES - tic["sp"])
                          / max(SCRUB_CCW_T_OUT_DES - SCRUB_CCW_T_IN_DES, 1e-6),
                          0.0, 100.0)
    else:                                         # MAN: supply T follows TV-329005 (cooler) opening
        tic["pv"] = clamp(SCRUB_CCW_T_OUT_DES
                          - (SCRUB_CCW_T_OUT_DES - SCRUB_CCW_T_IN_DES) * (tic["op"] / SCRUB_TV005_DES_PCT),
                          20.0, SCRUB_CCW_T_OUT_DES)
    m_ccw_kgh  = max(fic["pv"], 1e-6) * 1000.0    # CCW circulation (t/h -> kg/h)
    top_ratio  = (strip["top_mol"] / STRIP_TOP_MOL_DES) if STRIP_TOP_MOL_DES else 1.0  # stripper overhead push
    nu = s.p_syn_bara / SYN_P_DES_BARA            # vent ratio = PT-329201/PT_des (prior-step state; breaks the algebraic loop)
    scrub = scrub_322e003(react["offgas_kmolh"], react["co2_scale"], tic["pv"], m_ccw_kgh,
                          vent_ratio=nu)
    # PT-329201 reverse heat->pressure: condensation capacity (CCW flow) vs vent demand (s*nu).
    #   rho_cond < 1 (e.g. CCW throttled) -> off-gas under-condenses, accumulates, integrates PT up.
    #   Forward stripper push (top_ratio) sets the no-deficit target; first-order Euler accumulation
    #   over tau (min -> s).  Design: m_ccw=des, s=1, nu=1, top_ratio=1 -> rho=1 -> PT holds 140.7.
    rho_cond  = (m_ccw_kgh / SCRUB_CCW_KGH_DES) / max(react["co2_scale"] * nu, 1e-6)
    # PT-329201 vapour differentiation: NH3 + H2O overhead are CONDENSABLE solvents (absorbed into
    # carbamate/condensate, NOT pressure-building); only ACID CO2 unpaired by NH3 (free CO2 =
    # CO2 - NH3/2, from 2 NH3 + CO2 -> carbamate) plus NH3 that exceeds condensation capacity
    # (rho_cond < 1) builds synthesis pressure.  Normalised by TOTAL design overhead (not the small
    # free-CO2 anchor) for numerical stability.  Design: co2_free=98.6, slip=0 -> pb_push=0.
    n_top     = strip["top_kmolh"]
    co2_free  = max(n_top["CO2"] - 0.5 * n_top["NH3"], 0.0)                           # free acid CO2
    nh3_slip  = max(1.0 - rho_cond, 0.0) * max(n_top["NH3"] - STRIP_TOP_NH3_DES, 0.0)  # un-absorbed NH3
    n_pb      = co2_free + nh3_slip                                                   # pressure-building load
    pb_push   = (n_pb - STRIP_TOP_CO2FREE_DES) / STRIP_TOP_MOL_DES if STRIP_TOP_MOL_DES else 0.0
    pt_fwd    = SYN_P_DES_BARA * (1.0 + SYN_P_COUPLING * pb_push)
    pt_target = pt_fwd + SYN_P_DEFICIT_GAIN * max(1.0 - rho_cond, 0.0) * SYN_P_DES_BARA
    s.p_syn_bara = clamp(s.p_syn_bara + (dt / (SYN_P_TAU_MIN * 60.0)) * (pt_target - s.p_syn_bara),
                         SYN_P_MIN_BARA, SYN_P_MAX_BARA)
    scrub["P_overflow"] = s.p_syn_bara            # PT-329201 dynamic synthesis pressure (bar a)
    scrub["rho_cond"]   = rho_cond                # condensation capacity/demand (diag; <1 -> PT rises)
    scrub["co2_free"]   = co2_free                # free acid CO2 overhead (pressure-building, kmol/h)
    scrub["pb_push"]    = pb_push                 # PT forward push (pressure-building overhead deviation)
    scrub["top_ratio"]  = top_ratio              # total overhead ratio (diag only; superseded by pb_push)
    scrub["P_bub_hpcc"] = hpcc["P_bub"]           # 322E002 bubble-point synthesis P (bar a, diag)
    hv604 = hv_322604(scrub["offgas_kmolh"], scrub["T_offgas"], s.HIC_322604)
    TDY_329125 = scrub["t_ccw_out"] - tic["pv"]   # TT-329125 − TIC-329005 (condensation quality)
    q_e004_kw  = scrub["q_ccw_kw"]                # 329E004 tempered-water-cooler duty (loop closure)

    # Trips
    s.trips["21_2"]  = (s.tank_level_frac < 0.05)
    s.trips["21_8"]  = (P_suct_barG < 17.0 and s.pumpA["on"])
    s.trips["21_10"] = (P_suct_barG < 17.0 and s.pumpB["on"])

    # Discharge header
    P_disch_header_barG = (P_SYN_DOWN_BAR - 1.0) if (s.pumpA["on"] or s.pumpB["on"]) else 7.5

    # ---- uniform process-stream registry (clickable stream inspector) ----
    MW_NH3 = MW_COMP["NH3"]
    streams = {
        "NH3_FEED": make_stream(
            {"NH3": F_pump_total_th * 1000.0 / MW_NH3}, s.tank_T_C, s.tank_P_top_barG + 1.0,
            "NH3 ex 309E005", "309E005", "321D003", "liquid", rho=NH3_RHO),
        "PUMP_SUCT": make_stream(
            {"NH3": F_pump_total_th * 1000.0 / MW_NH3}, s.tank_T_C, PT_A + 1.0,
            "NH3 pump suction header", "321D003", "321P002 A/B", "liquid", rho=NH3_RHO),
        "HP_DISCH": make_stream(
            {"NH3": motive_nh3_kgh / MW_NH3}, TI_321020, P_SYN_DOWN_BAR,
            "HP NH3 discharge (motive)", "321P002 A/B", "322F001", "liquid", rho=NH3_RHO),
        "CARB_RECYCLE": make_stream(
            scrub["overflow_kmolh"], scrub["T_overflow"], scrub["P_overflow"],
            "Carbamate recycle (322E003 overflow)", "322E003", "322F001", "liquid"),
        "EJ_DISCH": make_stream(
            {k: ej["comp"][k] / MW_COMP[k] for k in MW_COMP}, ej["T_C"], ej["P_bara"],
            "Ejector discharge (carbamate liq.)", "322F001", "322E002", "liquid", rho=ej["rho"]),
        "CO2_FEED": make_stream(
            strip["co2_feed_kmolh"], CO2_T_FEED_C, STRIP_P_DES_BARA,
            "CO2 feed gas", "320K002", "322E001", "gas"),
        "STRIP_TOP": make_stream(
            strip["top_kmolh"], strip["T_top"], STRIP_P_DES_BARA,
            "Stripper top gas", "322E001", "322E002", "gas"),
        "STRIP_BOT": make_stream(
            strip["bot_kmolh"], strip["T_bot"], STRIP_P_DES_BARA,
            "Stripper bottom solution", "322E001", "LV-322501", "liquid"),
        "HPCC_PROD": make_stream(
            hpcc["feed_kmolh"], hpcc["T_prod"], hpcc["P_bara"],
            "HPCC two-phase product", "322E002", "322R001", "two-phase"),
        "HPCC_STEAM": make_stream(
            {"H2O": hpcc["steam_kgh"] / MW_COMP["H2O"]}, HPCC_STEAM_TSAT_C, HPCC_STEAM_P_BARA,
            "LP steam (shell side)", "322E002 shell", "LP header", "vapor"),
        "HPCC_COND": make_stream(
            {"H2O": hpcc["steam_kgh"] / MW_COMP["H2O"]}, HPCC_STEAM_TSAT_C, HPCC_STEAM_P_BARA,
            "BFW/condensate feed", "322D001 A/B", "322E002 shell", "liquid"),
        "REACT_OVERFLOW": make_stream(
            react["overflow_kmolh"], react["T_overflow"], react["P_bara"],
            "Reactor overflow (urea soln.)", "322R001", "322E001", "liquid",
            rho=REACT_OVERFLOW_RHO),
        "REACT_OFFGAS": make_stream(
            react["offgas_kmolh"], react["T_offgas"], react["P_offgas"],
            "Reactor off-gas", "322R001", "322E003", "vapor",
            rho=REACT_OFFGAS_RHO),
        "SCRUB_OFFGAS": make_stream(
            scrub["offgas_kmolh"], scrub["T_offgas"], scrub["P_offgas"],
            "HP scrubber off-gas (to HV-322604)", "322E003", "HV-322604", "vapor",
            rho=SCRUB_OFFGAS_RHO),
        "SCRUB_OFFGAS_LP": make_stream(
            hv604["comp_kmolh"], hv604["T_out"], hv604["P_out"],
            "HP scrubber off-gas (LP, JT-cooled)", "HV-322604", "322C001", "vapor"),
        "CCW_SUPPLY": make_stream(
            {"H2O": m_ccw_kgh / MW_COMP["H2O"]}, tic["pv"], SCRUB_CCW_P_IN_BARA,
            "CCW supply (shell side, cold)", "329P006 A/B", "322E003", "liquid",
            rho=SCRUB_CCW_RHO_IN),
        "CCW_RETURN": make_stream(
            {"H2O": m_ccw_kgh / MW_COMP["H2O"]}, scrub["t_ccw_out"], SCRUB_CCW_P_OUT_BARA,
            "CCW return (shell side, warm)", "322E003", "329P006 A/B", "liquid",
            rho=SCRUB_CCW_RHO_OUT),
    }

    return {
        "t":           time.time(),
        "FI_321401":   round(F_pump_total_th, 2),   # FT-321401 live discharge flow
        "TI_top1":     round(s.tank_T_C, 1),         # TT-321001 tank temp (left)
        "TI_top2":     round(s.tank_T_C, 1),         # TT-321002 tank temp (right)
        "LSL_321501":  (s.tank_level_frac < 0.15),   # low-level switch (active=LO)
        "PI_top1":     round(s.tank_P_top_barG, 1),
        "PI_top2":     round(s.tank_P_top_barG, 1),
        "PI_header":   7.3,
        "LI_321501":   round(s.tank_level_frac * 100.0, 1),
        "totalizer":   round(s.totalizer_t, 2),
        "XV_321901":   bool(s.XV_321901),
        "XV_322901":   bool(s.XV_322901),
        "PI_321201":   round(PT_A, 1),          # PT-321201 feed pressure (bar g = 321D003)
        "PI_321202":   round(PT_B, 1),          # PT-321202 feed pressure (bar g = 321D003)
        "PI_321201_alarm": (P_suct_barG < 17.0),
        "PI_321202_alarm": (P_suct_barG < 17.0),
        "PY_321201":   round(PY, 2),            # NH3 sat vapour P (bar a)
        "PY_321202":   round(PY, 2),
        "PDY_321203":  round(PDY_A, 2),         # sub-cooling margin (bar)
        "PDY_321204":  round(PDY_B, 2),
        "PDY_321203_alarm": PDY_A <= 0.0,
        "PDY_321204_alarm": PDY_B <= 0.0,
        "pumpA": {
            "on":      s.pumpA["on"],
            "speed":   round(s.pumpA["speed_act"], 1),
            "current": round(s.pumpA["current"], 1),
            "mode":    s.pumpA["mode"],
        },
        "pumpB": {
            "on":      s.pumpB["on"],
            "speed":   round(s.pumpB["speed_act"], 1),
            "current": round(s.pumpB["current"], 1),
            "mode":    s.pumpB["mode"],
        },
        "PI_disch": round(P_disch_header_barG if (s.pumpA["on"] or s.pumpB["on"]) else 7.5, 1),
        "TI_321020": round(TI_321020, 1),       # common discharge temperature
        "EJ_322F001": {                          # HP ejector discharge -> 322E002 (TT-322012)
            "motive_kgh":  round(motive_nh3_kgh, 1),
            "suction_kgh": round(ej["suction_kgh"], 1),
            "HIC_322602":  round(s.HIC_322602, 1),   # HV-322602 spindle opening (%)
            "mu":          round(ej["mu"], 4),       # entrainment ratio m_suc/m_motive
            "TT_322012":   round(ej["T_C"], 1),      # discharge temp (C) -> 322E002 HPCC
            "PI_disch":    round(ej["P_bara"], 1),   # discharge pressure (bar a)
            "TI_322002":   round(scrub["T_overflow"], 1), # TT-322002 = 322E003 overflow temp (C, live)
            "PI_329201":   round(scrub["P_overflow"], 1), # PT-329201 = 322E003 overflow line P (bar a, live)
            "total_kgh":   round(ej["total_kgh"], 1),
            "total_th":    round(ej["total_kgh"]/1000.0, 2),
            "mol_kmolh":   round(ej["mol_kmolh"], 2),
            "MW":          round(ej["MW"], 2),
            "rho":         round(ej["rho"], 1),
            "vol_m3h":     round(ej["vol_m3h"], 2),
            "comp_pct":    {k: (round(ej["comp"][k]/ej["total_kgh"]*100.0, 3)
                                if ej["total_kgh"] > 0 else 0.0) for k in MW_COMP},
        },
        "CO2_FEED": {                            # 320K002 -> XV-322902 -> 322E001 feed line
            "FT_322403":  round(FT_322403, 0),       # CO2 feed (Nm3/h)
            "FY_322403":  round(FY_322403, 2),       # CO2 feed (t/h, total stream)
            "TI_322017":  round(CO2_T_FEED_C, 1),    # CO2 feed temperature (C)
            "pure_th":    round(s.F_CO2_th * CO2_MASSFRAC_CO2, 2),  # t/h pure CO2 component
            "raw_th":     round(s.F_CO2_raw_th, 2),  # t/h raw from 320K002 (pre-vent)
            "Load":       round(Load_pct, 1),        # plant Load (% of design CO2 flow)
            "XV_322902":  bool(s.XV_322902),         # CO2 isolation to 322E001 (True=OPEN)
            "PV_322203":  round(pv_open, 1),         # vent valve opening (%)
            "HIC_322203": round(s.HIC_322203, 1),    # PV-322203 minimum opening (%)
            "PIC_322203": round(pic["pv"], 1),       # CO2 line pressure (bar a)
            "PIC_op":     round(pic["op"], 1),       # PIC-322203 output (vent demand %)
            "PIC_sp":     round(pic["sp"], 1),       # PIC-322203 setpoint (bar a)
            "PIC_mode":   pic["mode"],
        },
        "STRIP_322E001": {                       # HP Stripper 322E001 feeds -> products
            "TT_322014":   round(STRIP_FEED207_T_C, 1),   # 322R001 overflow feed temp (C)
            "TT_322013":   round(strip["T_top"], 1),      # top gas -> 322E002 (C)
            "TT_322004":   round(strip["T_bot"], 1),      # bottom soln -> LV-322501, pre-flash (C)
            "TT_323001":   round(TT_323001, 1),           # post-LV flash -> 323C003 (C)
            "top_th":      round(strip["top_th"], 2),     # top gas (t/h)
            "top_MW":      round(strip["top_MW"], 2),
            "top_mol_pct": {k: round(strip["top_comp_pct"][k], 3) for k in MW_COMP},
            "bot_th":      round(strip["bot_th"], 2),     # bottom solution (t/h)
            "bot_MW":      round(strip["bot_MW"], 2),
            "bot_mass_pct":{k: round(strip["bot_mass_pct"][k], 3) for k in MW_COMP},
            "xi_hyd":      round(strip["xi_hyd"], 2),     # urea hydrolysis extent (kmol/h)
            "xi_biu":      round(strip["xi_biu"], 3),     # biuret formation extent (Arrhenius, kmol/h)
            "eta_T":       round(strip["eta_T"], 4),      # strip efficiency (steam x N/C x H/C penalty)
            "g_NC":        round(strip["g_NC"], 4),       # feed-N/C penalty factor (1.0 = no penalty)
            "g_HC":        round(strip["g_HC"], 4),       # feed-H/C penalty factor (1.0 = no penalty)
            "L_strip":     round(strip["L_strip"], 4),    # live stripper-feed N/C
            "W_strip":     round(strip["W_strip"], 4),    # live stripper-feed H/C
            "LI_322501":   round(s.strip_level, 1),       # LT-322501 bottom-sump level (%)
            "LV_322501":   round(lv_open, 1),             # LV-322501 opening (%)
            "drain_th":    round(drain_kgh / 1000.0, 2),  # bottom drain -> 323C003 (t/h)
            "LIC_322501": {
                "pv":   round(lic["pv"], 1),
                "sp":   round(lic["sp"], 1),
                "op":   round(lic["op"], 1),
                "mode": lic["mode"],
            },
            "steam": {                            # shell side: 329D005 MP steam (boundary)
                "TI_shell": round(strip["T_steam"], 1),      # live sat-steam condensing temp (C)
                "P_bara":   round(STRIP_STEAM_P_BARA, 1),    # steam pressure (bar a)
                "kgh":      round(STRIP_STEAM_KGH_DES, 0),   # steam flow (kg/h)
                "duty_kW":  round(STRIP_DUTY_DES_KW, 0),     # heat duty (kW)
            },
        },
        "HPCC_322E002": {                        # HP Carbamate Condenser 322E002 -> 322R001
            "TT_322012":   round(ej["T_C"], 1),          # tube feed 1: ejector-disch liquid temp (C)
            "TT_322013":   round(strip["T_top"], 1),     # tube feed 2: stripper-top gas temp (C)
            "TT_322010":   round(hpcc["T_prod"], 1),     # liquid product -> 322R001 (C)
            "TT_329001":   round(HPCC_STEAM_TSAT_C, 1),  # shell BFW/condensate feed temp (C)
            "gas_th":      round(hpcc["gas_th"], 2),     # gas product (t/h)
            "gas_MW":      round(hpcc["gas_MW"], 2),
            "gas_mol_pct": {k: round(hpcc["gas_mol_pct"][k], 3) for k in MW_COMP},   # mol %
            "liq_th":      round(hpcc["liq_th"], 2),     # liquid product (t/h)
            "liq_MW":      round(hpcc["liq_MW"], 2),
            "liq_mass_pct":{k: round(hpcc["liq_mass_pct"][k], 3) for k in MW_COMP},  # mass %
            "P_bara":      round(hpcc["P_bara"], 1),
            "steam": {                            # shell side: 4.4 bar a LP steam (heat recovery)
                "TI_shell": round(HPCC_STEAM_TSAT_C, 1),     # T_sat(4.4 bar a) condensing temp (C)
                "P_bara":   round(HPCC_STEAM_P_BARA, 1),     # LP steam pressure (bar a)
                "kgh":      round(hpcc["steam_kgh"], 0),     # LP steam produced (kg/h)
                "duty_kW":  round(hpcc["duty_kw"], 0),       # condensation duty (kW)
            },
        },
        "REACT_322R001": {                       # HP Urea Reactor 322R001 -> 322E001 / 322E003
            "TT_322005":   round(REACT_TT_TEMPS_C["TT_322005"], 1),  # N6 A top (EL +21700, tau 38.9 min)
            "TT_322006":   round(REACT_TT_TEMPS_C["TT_322006"], 1),  # N6 B     (EL +14800, tau 26.6 min)
            "TT_322007":   round(REACT_TT_TEMPS_C["TT_322007"], 1),  # N6 C     (EL  +7900, tau 14.2 min)
            "TT_322008":   round(REACT_TT_TEMPS_C["TT_322008"], 1),  # N6 D bot (EL  +1000, tau  1.8 min)
            "TT_322009":   round(react["T_offgas"], 1),      # off-gas line -> 322E003 (C)
            "LT_322504":   round(s.react_level_pct, 1),      # top liquid level (%) — DYNAMIC
            "AT_322701":   round(react_nc_ratio(react["overflow_kmolh"]), 3),  # N/C molar ratio ->322E001
            "HIC_322605":  round(s.HIC_322605, 1),           # overflow valve controller (%)
            "HV_322605":   round(s.HIC_322605, 1),           # HV-322605 opening (tracks HIC 1:1)
            "P_bara":      round(react["P_bara"], 1),        # reactor pressure (bar a)
            "P_offgas":    round(react["P_offgas"], 1),      # off-gas line pressure (bar a)
            "closure_resid": round(react["closure_resid"], 2),  # mass-closure diag (kmol/h, not injected)
            "X_conv":      round(react["X_conv"] * 100.0, 2),    # per-pass CO2->urea conversion (%) — Inoue-Kanai
            "L_feed":      round(react["L_feed"], 3),            # reactor-feed N/C molar (NH3/CO2)
            "W_feed":      round(react["W_feed"], 4),            # reactor-feed H/C molar (H2O/CO2) — water-penalty driver
            "xi_urea":     round(react["xi_urea"], 2),           # urea-formation extent (kmol/h, conversion-coupled)
        },
        "SCRUB_322E003": {                       # HP Scrubber 322E003 -> 322C001 (off-gas) / 322F001 (overflow)
            "TT_322009":   round(react["T_offgas"], 1),      # reactor off-gas feed in (C)
            "TT_322011":   round(scrub["T_offgas"], 1),      # off-gas temp -> HV-322604 (C)
            "off_th":      streams["SCRUB_OFFGAS"]["mass_th"],   # off-gas mass flow (t/h)
            "off_mol":     streams["SCRUB_OFFGAS"]["mol_kmolh"], # off-gas molar flow (kmol/h)
            "off_MW":      streams["SCRUB_OFFGAS"]["MW"],        # off-gas mean MW
            "off_mol_pct": streams["SCRUB_OFFGAS"]["mol_pct"],   # off-gas composition (mol %)
            "ov_th":       streams["CARB_RECYCLE"]["mass_th"],   # overflow mass flow (t/h)
            "ov_mol":      streams["CARB_RECYCLE"]["mol_kmolh"], # overflow molar flow (kmol/h)
            "ov_MW":       streams["CARB_RECYCLE"]["MW"],        # overflow mean MW
            "ov_mass_pct": streams["CARB_RECYCLE"]["mass_pct"],  # overflow composition (mass %)
            "carb_th":     round(sum(scrub["carb_kmolh"][k] * MW_COMP[k] for k in MW_COMP) / 1000.0, 3),  # 323P001 wash (t/h)
            "closure_resid": round(scrub["closure_resid"], 2),  # tube-side mole-balance diag (kmol/h, not injected)
            "HV_322604":   round(s.HIC_322604, 1),           # HV-322604 opening (tracks HIC 1:1)
            "HIC_322604":  round(s.HIC_322604, 1),           # off-gas valve controller (%)
            "TT_322011_lp":round(hv604["T_out"], 1),         # off-gas T after HV-322604 (JT-cooled, C)
            "P_offgas":    round(scrub["P_offgas"], 1),      # off-gas line P (bar a)
            "P_overflow":  round(scrub["P_overflow"], 1),    # PT-329201 overflow line P (bar a)
            "TT_322002":   round(scrub["T_overflow"], 1),    # overflow temp -> 322F001 (C)
            "LT_329501":   50.0,                             # overflow seal-leg level (% — design NLL, pinned)
            "ccw": {                              # shell-side CCW loop (329P006 A/B pump + 329E004 cooler)
                "TT_329125":  round(scrub["t_ccw_out"], 2),     # CCW return temp out of shell (C)
                "TDY_329125": round(TDY_329125, 2),             # TT-329125 − TIC-329005 (cond. quality, C) — live PT-329201 cascade
                "vent_ratio": round(scrub["vent_ratio"], 4),    # synthesis-vent load PT-329201/PT_des (= nu, prior-step state)
                "rho_cond":   round(scrub["rho_cond"], 4),      # condensation capacity/demand (CCW flow / vent load); <1 -> PT-329201 rises
                "co2_free":   round(scrub["co2_free"], 1),      # free acid CO2 overhead (pressure-building, kmol/h)
                "pb_push":    round(scrub["pb_push"], 5),       # PT forward push = pressure-building overhead deviation (0 at design)
                "PI_322E002": round(scrub["P_bub_hpcc"], 1),    # 322E002 HPCC bubble-point synthesis P (bar a)
                "Q_ccw_kW":   round(scrub["q_ccw_kw"], 0),      # heat removed by CCW (kW)
                "Q_carb_kW":  round(scrub["q_carb_kw"], 0),     # carbamate exotherm (diag, kW)
                "co2_abs":    round(scrub["co2_abs"], 2),       # CO2 absorbed gas->carbamate (kmol/h)
                "FIC_329409": {"pv": round(fic["pv"], 1), "sp": round(fic["sp"], 1),
                               "op": round(fic["op"], 1), "mode": fic["mode"]},  # CCW flow (t/h) -> FV-329409
                "TIC_329005": {"pv": round(tic["pv"], 1), "sp": round(tic["sp"], 1),
                               "op": round(tic["op"], 1), "mode": tic["mode"]},  # CCW supply T (C) -> TV-329005
                "P329P006_in":  round(SCRUB_CCW_P_OUT_BARA, 1), # 329P006 A/B suction P (CCW return)
                "P329P006_out": round(SCRUB_CCW_P_IN_BARA, 1),  # 329P006 A/B discharge P (CCW supply)
                "E004_duty_kW": round(q_e004_kw, 0),            # 329E004 tempered-water-cooler duty (kW)
            },
        },
        "STREAMS": streams,
        "ratio": {
            "SP":  round(s.ratio_SP, 3),
            "PV":  round(s.ratio_PV, 3),
            "bal": round(s.ratio_bal, 3),
            "NC_A": round(NC_A, 3),           # N/C ratio 321P002A (molar)
            "NC_B": round(NC_B, 3),           # N/C ratio 321P002B (molar)
        },
        "ext_override": s.ext_override,
        "SIC_321950": {
            "pv":     round(s.SIC_321950.pv, 1),
            "sp":     round(s.SIC_321950.sp, 1),
            "sp_rpm": round(s.SIC_321950.sp / 100.0 * PUMP_RATED_RPM, 0),
            "mv":     round(s.SIC_321950.op, 1),
            "nc":     round(s.SIC_321950.nc, 1),
            "mode":   s.SIC_321950.mode,
        },
        "SIC_321951": {
            "pv":     round(s.SIC_321951.pv, 1),
            "sp":     round(s.SIC_321951.sp, 1),
            "sp_rpm": round(s.SIC_321951.sp / 100.0 * PUMP_RATED_RPM, 0),
            "mv":     round(s.SIC_321951.op, 1),
            "nc":     round(s.SIC_321951.nc, 1),
            "mode":   s.SIC_321951.mode,
        },
        "trips": s.trips,
    }


# ----- Commands from UI -----
def handle_cmd(cmd: dict):
    s = state
    t = cmd.get("type")

    if t == "pump_toggle":
        p = s.pumpA if cmd["id"] == "A" else s.pumpB
        p["on"] = not p["on"]

    elif t == "xv_toggle":
        if cmd["id"] == "321901":
            s.XV_321901 = not s.XV_321901
        elif cmd["id"] == "322901":
            s.XV_322901 = not s.XV_322901
        elif cmd["id"] == "322902":
            s.XV_322902 = not s.XV_322902

    elif t == "ext_override":
        s.ext_override = bool(cmd["value"])

    elif t == "controller_set":
        cid  = cmd["id"]
        ctrl = getattr(s, cid, None)
        if ctrl is None:
            return
        if "mode" in cmd:
            ctrl.set_mode(cmd["mode"], current_pv=ctrl.pv)
            if cmd["mode"] == "CAS":
                # ui_guidelines rule 6: master (ratio) -> AUTO, adopt current value as SP
                s.ratio_mode = "AUTO"
                s.ratio_SP   = round(s.ratio_PV, 3)
        if "op" in cmd and ctrl.mode == "MAN":      # PV entry drives opening
            ctrl.op = clamp(float(cmd["op"]), 0.0, 100.0)
        if "sp_rpm" in cmd and ctrl.mode == "AUTO":     # AUTO setpoint entered as RPM
            ctrl.sp = clamp(float(cmd["sp_rpm"]) / PUMP_RATED_RPM * 100.0, 0.0, 100.0)
        elif "sp" in cmd and ctrl.mode == "AUTO":
            ctrl.sp = clamp(float(cmd["sp"]), 0.0, 100.0)
        if "nc" in cmd and ctrl.mode == "CAS":
            ctrl.nc = float(cmd["nc"])

    elif t == "ratio_set":
        if "sp" in cmd:
            s.ratio_SP = float(cmd["sp"])

    elif t == "co2_set":                       # raw CO2 from 320K002 compressor (t/h)
        s.F_CO2_raw_th = max(0.0, float(cmd["value"]))

    elif t == "hic_set":                       # HIC-322602 -> HV-322602 ejector opening
        s.HIC_322602 = clamp(float(cmd["value"]), 0.0, 100.0)

    elif t == "hic2_set":                      # HIC-322203 -> PV-322203 minimum opening
        s.HIC_322203 = clamp(float(cmd["value"]), 0.0, 100.0)

    elif t == "hic605_set":                    # HIC-322605 -> HV-322605 reactor overflow valve
        if "op" in cmd:
            s.HIC_322605 = clamp(float(cmd["op"]), 0.0, 100.0)

    elif t == "pic_set":                       # PIC-322203 CO2 line-pressure controller
        pic = s.PIC_322203
        if "mode" in cmd:
            pic["mode"] = cmd["mode"]
        if "op" in cmd and pic["mode"] == "MAN":
            pic["op"] = clamp(float(cmd["op"]), 0.0, 100.0)
        if "sp" in cmd:
            pic["sp"] = float(cmd["sp"])

    elif t == "lic_set":                       # LIC-322501 bottom-solution level controller
        lic = s.LIC_322501
        if "mode" in cmd:
            lic["mode"] = cmd["mode"]
        if "op" in cmd and lic["mode"] == "MAN":   # MAN: operator sets LV-322501 opening (%)
            lic["op"] = clamp(float(cmd["op"]), 0.0, 100.0)
        if "sp" in cmd:                            # level setpoint (%)
            lic["sp"] = clamp(float(cmd["sp"]), 0.0, 100.0)

    elif t == "hic604_set":                    # HIC-322604 -> HV-322604 scrubber off-gas valve
        if "op" in cmd:
            s.HIC_322604 = clamp(float(cmd["op"]), 0.0, 100.0)

    elif t == "fic_set":                       # FIC-329409 CCW circulation-flow controller -> FV-329409
        fic = s.FIC_329409
        if "mode" in cmd:
            fic["mode"] = cmd["mode"]
        if "op" in cmd and fic["mode"] == "MAN":   # MAN: operator sets FV-329409 opening (%)
            fic["op"] = clamp(float(cmd["op"]), 0.0, 100.0)
        if "sp" in cmd:                            # CCW flow setpoint (t/h)
            fic["sp"] = max(float(cmd["sp"]), 0.0)

    elif t == "tic_set":                       # TIC-329005 CCW supply-temp controller -> TV-329005
        tic = s.TIC_329005
        if "mode" in cmd:
            tic["mode"] = cmd["mode"]
        if "op" in cmd and tic["mode"] == "MAN":   # MAN: operator sets TV-329005 opening (%)
            tic["op"] = clamp(float(cmd["op"]), 0.0, 100.0)
        if "sp" in cmd:                            # CCW supply-temp setpoint (C)
            tic["sp"] = float(cmd["sp"])


# ----- FastAPI app -----
app = FastAPI()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            msg = await ws.receive_text()
            try:
                handle_cmd(json.loads(msg))
            except Exception as ex:
                print("cmd error:", ex)
    except WebSocketDisconnect:
        clients.discard(ws)


async def sim_task():
    global last_packet
    last_t = time.time()
    while True:
        now = time.time()
        dt = min(now - last_t, 0.5)
        last_t = now
        last_packet = step_sim(dt)
        await asyncio.sleep(DT)


async def push_task():
    while True:
        if clients and last_packet:
            msg = json.dumps(last_packet)
            dead = []
            for c in list(clients):
                try:
                    await c.send_text(msg)
                except Exception:
                    dead.append(c)
            for d in dead:
                clients.discard(d)
        await asyncio.sleep(0.1)


@app.on_event("startup")
async def on_start():
    asyncio.create_task(sim_task())
    asyncio.create_task(push_task())


# Serve frontend from sibling folder (path anchored to this file, not CWD)
_FRONTEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

class _NoCacheStatic(StaticFiles):
    """Force browsers to revalidate every asset so index.html/app.js never serve stale."""
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

app.mount("/", _NoCacheStatic(directory=_FRONTEND, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
