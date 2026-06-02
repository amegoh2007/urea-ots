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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

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
STRIP_STEAM_T_DES_C = 214.0       # C, condensing temp at ~20 bar a
STRIP_STEAM_P_BARA  = 19.7        # bar a, 329D005 steam supply pressure
STRIP_DUTY_DES_KW   = 39400.0     # kW, design heat duty
STRIP_P_DES_BARA    = 144.0       # bar a, tube-side (synthesis-loop) pressure
# --- Design product temperatures (C):
STRIP_T_TOPGAS_DES_C = 187.0      # TT-322013 top gas -> 322E002
STRIP_T_BOTTOM_DES_C = 172.0      # TT-322004 bottom solution -> LV-322501 (pre-flash)
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


def stripper_322e001(co2_feed_th: float, T_steam_C: float, P_bara: float) -> dict:
    """HP Stripper 322E001 reduced steady-state model.
    Top liquid feed = 322R001 overflow (boundary constant, stream 207).
    Bottom strip gas = live CO2 feed (co2_feed_th, t/h).  Shell = condensing MP steam.
    Splits each component to top gas (-> 322E002) and bottom solution (-> LV-322501) using
    design strip fractions modulated by steam T, CO2 strip-gas ratio and pressure.  Reactions
    (urea hydrolysis + biuret formation) carry the component-balance deltas.  At design
    conditions reproduces the shared HMB exactly.  Returns both product streams + props."""
    # 1. component molar feed (kmol/h): reactor effluent (const) + live CO2 strip gas
    co2_scale = co2_feed_th / (CO2_DES_KGH / 1000.0)                     # 1.0 at design
    co2_kmolh = {k: CO2_FEED_MOLFRAC.get(k, 0.0) * CO2_DES_KMOLH * co2_scale for k in MW_COMP}
    feed = {k: STRIP_FEED207_KMOLH.get(k, 0.0) + co2_kmolh.get(k, 0.0) for k in MW_COMP}

    # 2. reactions (scale with steam heat: hotter film -> more hydrolysis/biuret)
    eta_T  = clamp(T_steam_C / STRIP_STEAM_T_DES_C, 0.0, 1.15)           # 1.0 at design
    xi_hyd = STRIP_XI_HYD_DES * eta_T
    xi_biu = STRIP_XI_BIU_DES * eta_T
    avail = dict(feed)
    avail["Urea"]   -= (xi_hyd + 2.0 * xi_biu)
    avail["Biuret"] += xi_biu
    avail["NH3"]    += (2.0 * xi_hyd + xi_biu)
    avail["CO2"]    += xi_hyd
    avail["H2O"]    -= xi_hyd
    for k in avail:
        avail[k] = max(avail[k], 0.0)

    # 3. strip-fraction modulation: steam heat (eta_T) x CO2 strip-gas dilution (eta_co2)
    #    x synthesis-pressure (lower P -> more flashing -> more strip).  =1.0 at design.
    eta_co2 = clamp(0.5 + 0.5 * co2_scale, 0.4, 1.05)
    eta_P   = clamp(2.0 - P_bara / STRIP_P_DES_BARA, 0.85, 1.15)
    mod = clamp(eta_T * eta_co2 * eta_P, 0.0, 1.12)
    top = {}; bot = {}
    for k in MW_COMP:
        f = clamp(STRIP_FRAC_DES.get(k, 0.0) * mod, 0.0, 0.999)
        top[k] = avail[k] * f
        bot[k] = avail[k] * (1.0 - f)

    # 4. stream totals (kg/h) + intensive props
    top_kgh = {k: top[k] * MW_COMP[k] for k in MW_COMP}
    bot_kgh = {k: bot[k] * MW_COMP[k] for k in MW_COMP}
    top_m = sum(top_kgh.values()); top_n = sum(top.values())
    bot_m = sum(bot_kgh.values()); bot_n = sum(bot.values())
    dTs = T_steam_C - STRIP_STEAM_T_DES_C
    return {
        "feed_kmolh": feed, "top_kmolh": top, "bot_kmolh": bot,
        "top_kgh": top_m, "bot_kgh": bot_m,
        "top_th": top_m / 1000.0, "bot_th": bot_m / 1000.0,
        "top_mol": top_n, "bot_mol": bot_n,
        "top_MW": (top_m / top_n if top_n else 0.0),
        "bot_MW": (bot_m / bot_n if bot_n else 0.0),
        "top_comp_pct": {k: (top[k] / top_n * 100.0 if top_n else 0.0) for k in MW_COMP},   # mol %
        "bot_mass_pct": {k: (bot_kgh[k] / bot_m * 100.0 if bot_m else 0.0) for k in MW_COMP},# mass %
        "T_top": STRIP_T_TOPGAS_DES_C + 0.6 * dTs,
        "T_bot": STRIP_T_BOTTOM_DES_C + 0.7 * dTs,
        "xi_hyd": xi_hyd, "xi_biu": xi_biu,
    }


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
        "T_prod": HPCC_T_PROD_DES_C, "P_bara": HPCC_P_DES_BARA,
        "duty_kw": duty_kw, "steam_kgh": steam_kgh,
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
    strip = stripper_322e001(s.F_CO2_th, STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA)

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

    # Trips
    s.trips["21_2"]  = (s.tank_level_frac < 0.05)
    s.trips["21_8"]  = (P_suct_barG < 17.0 and s.pumpA["on"])
    s.trips["21_10"] = (P_suct_barG < 17.0 and s.pumpB["on"])

    # Discharge header
    P_disch_header_barG = (P_SYN_DOWN_BAR - 1.0) if (s.pumpA["on"] or s.pumpB["on"]) else 7.5

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
            "TI_322002":   round(EJ_T_SUCTION_C, 1),    # suction-B temp (C): 322E003 overflow
            "PI_329201":   round(EJ_P_SUCTION_BARA, 1), # suction-B line P (bar a): 322E003->322F001
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
            "xi_biu":      round(strip["xi_biu"], 3),     # biuret formation extent (kmol/h)
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
                "TI_shell": round(STRIP_STEAM_T_DES_C, 1),   # condensing temp (C)
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
