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
import threading
from typing import Optional, Set

import reactor  # 322R001 Modified Inoue-Kanai conversion kinetics (quarantined)
from controllers import Controller
from steam_system import SteamState, step_steam  # MP/LP steam-header dynamics (quarantined)

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


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
# Lube-oil fluid dynamics abstracted away (Batch 4 refinement): the per-pump trips 21.8/21.10 now
#   fire on a generic boolean equipment fault pump["fault"] (instructor-set), not a continuous
#   lube-oil pressure.  See pumpA/pumpB state + trip block + trigger_fault command handler.
TANK_ID         = 0.970          # m
TANK_H          = 1.400          # m
TANK_VOL        = (math.pi/4.0) * TANK_ID**2 * TANK_H                # m^3
# 321D003 feed-drum level control (LIC-321501).  BL NH3 import tracks the live feed-pump draw plus a
# proportional level-restoring term, so import == draw at steady state (the drum neither drains into the
# 21_2 low-level trip nor floods on a feed disturbance).  P-only on the tank integrator with a draw
# feed-forward holds the level at SP with ZERO offset; bit-exact at design (level==SP -> makeup==draw).
TANK_LEVEL_SP_FRAC = 0.65        # 321D003 design working level (LI-321501 setpoint, fraction)
TANK_LIC_KP_TH     = 80.0        # t/h per unit level-fraction error, feed-drum makeup level gain
TANK_BL_MAX_TH     = 90.0        # t/h, BL NH3 import-line max capacity (makeup valve fully open)
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
# ----- Simulation speed modes -----
#   SLOW = real-time (1 sim-s per real-s): physical time constants (tau_loss=6 h etc.) run at
#          wall-clock -> realistic but slow transients.  This is the design/anchor reference.
#   FAST = time-accelerated training mode: SIM_SPEED["FAST"] sim-s per real-s, integrated in
#          fixed sub-steps of <= STEP_CAP so the per-step physics (and the design steady state)
#          stay BIT-IDENTICAL to SLOW -- only the wall-clock pace changes.  60x => a 6 h reactor
#          relaxation is seen in ~6 real-min.  Tune the factor here.
SIM_SPEED       = {"SLOW": 1.0, "FAST": 60.0}    # sim-seconds advanced per real-second, per mode
STEP_CAP        = 0.5            # s, max physical sub-step (== existing dt clamp -> Euler-stable)
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
EJ_STALL_PHI   = 0.35            # motive-fraction (phi_m) jet-stall knee: below this the ejector
                                 # can no longer entrain -> mu collapses.  f_stall==1.0 at design
                                 # motive (phi_m=1) so mu == spindle value (design bit-exact).
EJ_SUC_TOT_DES = sum(EJ_SUCTION_KGH.values())                      # kg/h, design suction
EJ_CARB_FRAC   = {k: EJ_SUCTION_KGH[k] / EJ_SUC_TOT_DES for k in MW_COMP}  # 322E003 overflow comp
EJ_CP_N, EJ_CP_C, EJ_CP_D = 4.74, 3.10, 3.50    # kJ/kg.K  motive / carbamate / discharge
EJ_T_SUCTION_C  = 178.8          # C, carbamate suction (322E003 overflow; dH_mix lumped in)
# design motive-NH3 temp at the ejector nozzle (TI-321020) reconstructed from the live pump-thermal
# path at the design tank state (T=25 C, level=0.65, P_top=12.3 barg) so the HPCC UA back-calc below
# sees the SAME cold motive (~28.93 C) the running loop actually feeds, NOT 170 C:
#   dT_pump = dP/(rho*cp)*(beta*T + (1-eta_h)/eta_h);  EJ_MOTIVE_T_DES_C = T_BL_FEED_C + dT_pump.
_EJ_P_SUCT_DES  = 12.3 + (NH3_RHO * G * 0.65 * TANK_H) / 1e5 - 0.15
_EJ_DP_DES_PA   = max(0.0, P_SYN_DOWN_BAR - (_EJ_P_SUCT_DES + P_ATM_BAR)) * 1e5
EJ_MOTIVE_T_DES_C = T_BL_FEED_C + _EJ_DP_DES_PA / (NH3_RHO * CP_NH3) \
                    * (BETA_NH3 * (T_BL_FEED_C + 273.15) + (1.0 - ETA_PUMP_HYD) / ETA_PUMP_HYD)
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
PIC_322203_KC     = 1.0          # %OP per bar (velocity I-PD proportional gain, DIRECT-acting)
PIC_322203_TI     = 2.0          # s, integral time (Kc/Ti = 0.5 preserves prior integral-only gain)
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
STRIP_T_FLOOD_ANCHOR_C = reactor.T0_DES_C   # 183.0 °C (= REACT_OVERFLOW_T_C, fwd-defined): hot reactor
#   liquor T the bottom asymptotes UP to when the stripper floods (GAP #1 ceiling). reactor.T0_DES_C is
#   import-time available (REACT_OVERFLOW_T_C is defined after this module's design-point self-call).
# --- N/C + H/C stripping-efficiency penalty + Arrhenius biuret (live reactor-effluent coupling) ---
#   Design stripper feed = stream-207 overflow + CO2 strip gas (molfrac x design CO2 rate).  L0/W0/U0
#   anchors are DERIVED from existing design constants (no fabricated numbers); differ from the
#   reactor-feed N/C because the stripper feed includes the CO2 sweep gas.
_STRIP_FEED_DES = {k: STRIP_FEED207_KMOLH.get(k, 0.0)
                   + CO2_FEED_MOLFRAC.get(k, 0.0) * CO2_DES_KMOLH for k in MW_COMP}
STRIP_L0    = _STRIP_FEED_DES["NH3"] / _STRIP_FEED_DES["CO2"]    # 1.9045  design feed N/C
STRIP_W0    = _STRIP_FEED_DES["H2O"] / _STRIP_FEED_DES["CO2"]    # 1.0610  design feed H/C
STRIP_UREA0 = _STRIP_FEED_DES["Urea"]                           # 1302.6  design feed urea (kmol/h)
# --- Stripper liquid-side energy balance (fixed reboiler duty spread over LIVE feed mass) ---
#   The 329D005 MP-steam reboiler delivers ~Q_steam,des; the per-unit-mass heating available to
#   the descending liquid is Q_steam/(ṁ_feed·cp).  A reactor-overflow feed spike at constant steam
#   duty dilutes that specific heating, so the bottom solution leaves COLDER.  ΔT_steam,des is the
#   design steam specific heating; the carbamate-decomposition endotherm (∝ feed) cancels its own
#   per-mass term, leaving this steam-dilution swing as the net bottom-temperature response.
STRIP_CP_BOTTOM      = 2.93     # kJ/kg·K, bottom-solution (urea/carbamate/NH3 melt) mean cp ~175 °C
STRIP_FEED_DES_KGH   = sum(_STRIP_FEED_DES[k] * MW_COMP[k] for k in MW_COMP)   # 280797 kg/h design feed
STRIP_DT_STEAM_DES_C = STRIP_DUTY_DES_KW * 3600.0 / (STRIP_FEED_DES_KGH * STRIP_CP_BOTTOM)  # ΔT_steam,des ≈172.4 °C
# --- CO2 stripping-gas endotherm (Stamicarbon G/L): the bottom CO2 sweep is held by the compressor while
#   the reactor liquid feed varies.  When ṁ_feed collapses at constant CO2, the Gas/Liquid ratio spikes,
#   forcing carbamate decomposition + NH3/CO2 evaporation -- a strong ENDOTHERM that OVERPOWERS the steam
#   heat and pulls the bottom COLDER.  Acts only on EXCESS G/L (feed-lean / CO2-rich); saturates (no pole).
STRIP_STRIPCOOL_MAX  = 72.0     # °C, max forced-decomposition/evaporation endotherm (G/L -> ∞ asymptote)
STRIP_STRIPCOOL_KGL  = 1.80     # cooling ramp per unit excess G/L ratio ((G/L)/(G/L)_des − 1)
STRIP_ETA_KT    = 1.50     # eta_T penalty per unit fractional bottom-T deficit (feed-load cooling chokes strip)
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
LV322501_P_DOWN_BARA = 4.0        # bar a, L3-1 LP-loop downstream ref for live-P_syn drain head


def ejector_322f001(motive_nh3_kgh: float, T_motive_C: float, hv_open_pct: float,
                    m_suc_avail: float = None) -> dict:
    """322F001 HP ejector: mix live motive NH3 with entrained 322E003 carbamate.
    Entrainment is set by the HV-322602 spindle opening (HIC-322602): decreasing the
    opening raises mu -> more 322E003 carbamate suction.  At the design opening (74 %)
    mu = EJ_MU and the discharge reproduces the design 'Carb. Liq.' table.  Energy
    balance sets discharge temp.  Returns the discharge stream (-> 322E002) + props.

    P1-3 mass conservation: a jet pump cannot entrain more than the upstream actually
    supplies.  m_suc_avail (kg/h) = live 322E003 overflow mass; the entrained suction is
    capped at min(mu*motive, m_suc_avail) so no phantom carbamate is created.  None
    (unit-test path) leaves the demand uncapped (= legacy behaviour)."""
    if motive_nh3_kgh <= 1e-6:
        # No-flow (pumps tripped): zero MASS, but the discharge thermowell (TT-322012) is NOT at
        #   0 C -- it reads the stagnant fluid backed up into the dead jet pump, i.e. the entrained
        #   322E003 carbamate at EJ_T_SUCTION_C.  Losing the COLD motive NH3 (~29 C) that normally
        #   pulls the design blend down to ~108 C leaves only the hot suction carbamate, so the tag
        #   RISES to the suction temp rather than collapsing to 0.  (Reduced model: stateless step,
        #   no thermal-inertia decay.)  Mass leaves remain 0 -> no effect on the HPCC T_feed_mix
        #   (m_liq_in = 0), so this does not perturb TT-322010.
        return {"comp": {k: 0.0 for k in MW_COMP}, "total_kgh": 0.0, "suction_kgh": 0.0,
                "mol_kmolh": 0.0, "MW": 0.0, "T_C": EJ_T_SUCTION_C, "P_bara": 0.0,
                "rho": 0.0, "vol_m3h": 0.0, "mu": 0.0}
    # HV-322602 (HIC-322602) sets entrainment: decreasing opening -> more 322E003 suction.
    open_eff = clamp(hv_open_pct, 10.0, 100.0)
    # motive-linked entrainment stall: a jet pump can no longer entrain below a critical motive
    # momentum -> suction chokes.  Linear ramp on motive fraction phi_m, knee EJ_STALL_PHI.
    phi_m    = motive_nh3_kgh / EJ_MOTIVE_NH3_DES
    f_stall  = clamp((phi_m - EJ_STALL_PHI) / (1.0 - EJ_STALL_PHI), 0.0, 1.0)
    mu       = EJ_MU * (EJ_OPEN_DES / open_eff) * f_stall   # spindle entrainment x motive stall
    m_suc    = mu * motive_nh3_kgh                          # entrainment DEMAND (kg/h)
    # P1-3 cap: suction strictly bounded by the live scrubber-overflow availability.
    if m_suc_avail is not None:
        m_suc = min(m_suc, max(m_suc_avail, 0.0))
    suction  = {k: m_suc * EJ_CARB_FRAC[k] for k in MW_COMP}
    disch   = {k: (motive_nh3_kgh if k == "NH3" else 0.0) + suction[k] for k in MW_COMP}
    m_d   = sum(disch.values())
    n_d   = sum(disch[k] / MW_COMP[k] for k in MW_COMP)   # kmol/h
    m_suc = sum(suction.values())
    # mass-energy balance (user P1-3): m_mot*cpN*T_mot + m_suc*cpC*T_suc in the numerator;
    #   denominator carries the lumped discharge heat-capacity m_d*cpD (cp_D calibrated to hold
    #   the design TT-322012 bit-exact).  NB: the literal mass-only denominator (m_mot+m_suc)
    #   is dimensionally an enthalpy, not a temperature, and breaks the design pin -> the
    #   dimensionally-correct cp-weighted form is retained.  Capped m_suc now drives T_d.
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


# ----- L3 boundary guards (Level-3 audit, Batch 1) -----
def _finite(x, tag: str = "operator input") -> float:
    """L3-8: reject (raise) a non-finite operator write before casting/clamping.
    Raises ValueError on NaN/+/-Inf so handle_cmd's caller drops the whole frame."""
    v = float(x)
    if not math.isfinite(v):
        raise ValueError(f"non-finite {tag}: {x!r}")
    return v


def _reject_nonfinite(const: str):
    """json.loads parse_constant hook: reject NaN / Infinity / -Infinity literals (L3-8)."""
    raise ValueError(f"non-finite literal in command frame: {const}")


def _loads_cmd(msg: str) -> dict:
    """Parse a WebSocket command frame; reject any non-finite literal at ingress (L3-8 gate)."""
    return json.loads(msg, parse_constant=_reject_nonfinite)


def _pv_ok(*vals) -> bool:
    """L3-9: True iff every value is a finite real number (hand-rolled-loop bad-PV guard)."""
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in vals)


def _f_flow(T: float, T_cryst: float, dT_mush: float = 5.0) -> float:
    """L3 generic mushy-zone flow factor (Batch 2): 1.0 fully molten, ramps linearly to 0.0 at the
    crystallization solidus.  f = clamp((T - T_cryst)/dT_mush, 0, 1) -> liquidus at T_cryst+dT_mush."""
    return clamp((T - T_cryst) / dT_mush, 0.0, 1.0)


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
    # liquid-side ENERGY BALANCE: fixed steam duty diluted across the LIVE feed mass (kg/h).  More
    # feed (reactor overflow valve opened) at constant duty -> less specific heating -> COLDER bottom.
    #   raw_load = ΔT_steam,des·(ṁ_feed,des/ṁ_feed − 1)   (=0 at design, <0 on a feed spike)
    m_feed_kgh = sum(feed[k] * MW_COMP[k] for k in MW_COMP)             # live stripper feed mass
    raw_load   = STRIP_DT_STEAM_DES_C * (STRIP_FEED_DES_KGH / max(m_feed_kgh, 1e-6) - 1.0)
    # THERMAL CEILING (NTU effectiveness): the bottom liquid can never out-heat the condensing shell
    # steam, so the raw 1/ṁ_feed pole must NOT diverge as ṁ_feed -> 0; T_bot asymptotes to T_steam.
    # cap = live head-room below steam sat (T_steam − T_bot,des = gap_des + 0.3·dTs).  The low-feed
    # (heating) branch saturates as  dT_load = cap·(1 − e^{−raw/cap}) -> cap  (T_bot -> T_steam),
    # staying slope-1 near design.  dT_load remains the EFFICIENCY driver (g_T below): on the high-feed
    # (flood) branch it stays the RAW negative load so η_T keeps choking and volatile slip keeps rising.
    cap        = max(STRIP_STEAM_T_DES_C - STRIP_T_BOTTOM_DES_C + 0.3 * dTs, 1e-6)
    dT_load    = cap * (1.0 - math.exp(-raw_load / cap)) if raw_load > 0.0 else raw_load
    g_T        = clamp(1.0 + STRIP_ETA_KT * dT_load / STRIP_T_BOTTOM_DES_C, STRIP_ETA_FLOOR, 1.05)
    # GAP #1 fix — SEPARATE T_bot driver (dT_bot), decoupled from the g_T driver (dT_load).  The OLD
    # code fed the raw linear dT_load straight into T_bot, so a feed spike (raw<0) drove the bottom T
    # DOWN without bound (ṁ_feed→∞ ⇒ raw→−ΔT_steam,des ⇒ T_bot→−0.4 °C, absurd & wrong sign).
    # Physics: a flooded stripper is STEAM-LIMITED — carbamate decomposition stalls, its endotherm fades,
    # and the already-hot reactor liquor (STRIP_T_FLOOD_ANCHOR_C ≈ REACT_OVERFLOW_T_C) falls through the
    # tubes untouched.  So T_bot must RISE and asymptote UP to the reactor overflow T, never crash:
    #   dT_bot = D·(1 − e^{raw/D}),  D = anchor − T_bot,des ;  raw≤0 ⇒ dT_bot ∈ [0, D)  (→ +D as ṁ→∞)
    # Low-feed branch keeps dT_bot = dT_load (heat toward steam sat).  g_T (above) is UNTOUCHED — still on
    # the raw load — so η_T / slip stay choked: a flood gives HOT but UNSTRIPPED bottoms, slip still climbs.
    strip_flood_gap = max(STRIP_T_FLOOD_ANCHOR_C - STRIP_T_BOTTOM_DES_C, 1e-6)
    dT_bot = dT_load if raw_load > 0.0 else strip_flood_gap * (1.0 - math.exp(raw_load / strip_flood_gap))
    # CO2 STRIPPING ENDOTHERM (G/L cooling): excess strip gas per liquid forces carbamate decomposition +
    # NH3/CO2 flash -> endothermic.  r_GL = (G/L)/(G/L)_des − 1 = co2_scale·ṁ_feed,des/ṁ_feed − 1 (=0 at
    # design).  Only feed-lean / CO2-rich (r_GL>0) cools; the feed-spike branch (r_GL<0) is left untouched.
    # Saturates at STRIP_STRIPCOOL_MAX as G/L -> ∞ (no 1/ṁ_feed pole).  This term OVERPOWERS the dT_load
    # steam-heating spike on a low-feed / constant-CO2 excursion -> bottom goes COLDER, not toward steam sat.
    r_GL     = co2_scale * STRIP_FEED_DES_KGH / max(m_feed_kgh, 1e-6) - 1.0
    dT_strip = -STRIP_STRIPCOOL_MAX * (1.0 - math.exp(-STRIP_STRIPCOOL_KGL * max(r_GL, 0.0)))
    L_react = reactor.L0_DES if L_feed is None else L_feed              # reactor-feed N/C
    W_react = reactor.W0_DES if W_feed is None else W_feed              # reactor-feed H/C
    g_NC = clamp(1.0 - STRIP_ETA_KN * (L_react - reactor.L0_DES), STRIP_ETA_FLOOR, 1.05)
    g_HC = clamp(1.0 - STRIP_ETA_KW * (W_react - reactor.W0_DES), STRIP_ETA_FLOOR, 1.05)
    eta_T = clamp(eta_T_steam * g_NC * g_HC * g_T, 0.0, 1.15)            # reported strip efficiency (incl. feed-load thermal)
    L_strip = (feed["NH3"] / feed["CO2"]) if feed["CO2"] else STRIP_L0   # stripper-feed N/C (diag)
    W_strip = (feed["H2O"] / feed["CO2"]) if feed["CO2"] else STRIP_W0   # stripper-feed H/C (diag)

    # 3. reactions: hydrolysis scales with penalized eta_T; biuret = Arrhenius k0 exp(-Ea/RT)*[Urea].
    T_bot_C = min(STRIP_T_BOTTOM_DES_C + 0.7 * dTs + dT_bot + dT_strip, T_steam_C) # TT-322004 (steam-heat + G/L strip-cool, ≤ steam sat; dT_bot flood-anchored to reactor T)
    T_bot_K = T_bot_C + 273.15
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
    slip = max(1.0 - g_NC, 0.0) + max(1.0 - g_HC, 0.0) + max(1.0 - g_T, 0.0)  # +feed-load thermal breakthrough
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
        "T_bot": T_bot_C,
        "xi_hyd": xi_hyd, "xi_biu": xi_biu, "eta_T": eta_T, "T_steam": T_steam_C,
        "eta_T_steam": eta_T_steam, "g_NC": g_NC, "g_HC": g_HC, "g_T": g_T,
        "dT_load": dT_load, "dT_bot": dT_bot, "dT_strip": dT_strip, "r_GL": r_GL, "m_feed_kgh": m_feed_kgh,  # energy-balance + G/L strip-cool diag
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
RATIO_PV_DES       = 2.0231315310702604   # design fresh-feed N/C (live-probed settled ratio.PV)
REACT_NC_LOOP_GAIN = 0.50        # f_L loop N/C gain: maps the EXOGENOUS fresh-feed N/C deviation
                                 # (ratio.PV, set by pump speeds — feedback-free) onto the reactor-feed
                                 # N/C that drives Inoue-Kanai f_L.  The pinned recycle otherwise
                                 # suppresses loop NH3-enrichment; this restores it.  ==L0 at design
                                 # (ratio.PV=RATIO_PV_DES -> conv=1) -> bit-exact, AT-322701 invariant.
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


REACT_TT_TEMPS_C = {tag: _react_tt_temp(el) for tag, el in REACT_TT_EL_MM.items()}  # 182.9/182.5/180.8/172.6 (static seed)
REACT_LEVEL_NLL_PCT  = 80.0      # LT-322504 top normal liquid level (% at design φ=φ_des)
REACT_V_SPAN_M3      = _react_area_m2 * (REACT_LIQ_H_MM / 1000.0)   # liquid-span volume LT 0->100 %

# --- Fix-1: DYNAMIC 4-node axial thermal profile (replaces the static residence-time probe) ----
# Lumped node energy balance integrated each tick (see reactor.py module note + step_sim):
#     dT_n/dt = [ (T_{n-1} - T_n) + g_n·ΔT_col ] / τ_n ,  T_0 = T_feed (HPCC two-phase product).
#   ΔT_col = REACT_DT_COL_DES · conversion_factor  -> the whole profile FLEXES with per-pass conversion.
#   g_n    = Damköhler heat-release weights (reactor.node_heat_weights); β = τ_tot/τ_therm makes the
#            steady-state node temps reproduce the as-built static probe bit-exact (HMB-preserving).
#   τ_n    = Δζ_n·τ_tot  (per-node liquid residence time, min).
REACT_BETA_DAMK    = REACT_TAU_TOT_MIN / REACT_THERM_TAU_MIN          # ≈ 5.61 (column τ / exotherm τ)
REACT_NODE_TAGS    = ["TT_322008", "TT_322007", "TT_322006", "TT_322005"]  # ASCENDING EL: node1(bot)..node4(top)
REACT_ZETA_NODES   = [REACT_TT_EL_MM[t] / REACT_LIQ_H_MM for t in REACT_NODE_TAGS]   # dimensionless elevations
REACT_G_NODES, REACT_G_OV = reactor.node_heat_weights(REACT_ZETA_NODES, REACT_BETA_DAMK)  # Σ + g_ov = 1
_react_zeta_prev   = [0.0] + REACT_ZETA_NODES[:-1]
REACT_TAU_NODE_MIN = [(z - zp) * REACT_TAU_TOT_MIN for z, zp in zip(REACT_ZETA_NODES, _react_zeta_prev)]  # node residence, min
REACT_DT_COL_DES   = REACT_OVERFLOW_T_C - HPCC_T_PROD_DES_C           # 13.0 C design column rise (conv=1)
REACT_OFFGAS_GAMMA = 0.6         # off-gas blend: T_offgas = T_top + γ_o·(T_overflow - T_top)
REACT_NODE_SS_DES  = reactor.node_profile_ss(HPCC_T_PROD_DES_C, REACT_OVERFLOW_T_C,
                                             REACT_ZETA_NODES, REACT_BETA_DAMK)  # design SS seed [T1..T4]
# --- Fix-2b: stagnant-flow hydraulic anchoring (Francis weir geometry + conserved holdup mass) -
# Decouples reactor OUTFLOW from inflow (weir) and makes level a state of a CONSERVED holdup mass,
# so a closed CO2 XV un-freezes level: it parks at the lip, then thermal contraction drops it below.
# Every constant is solved against the REAL design overflow + level -> design HMB stays bit-exact:
#   * crest sits REACT_WEIR_HEAD_DES below the design level (80 % of the 25 m span) -> head_des = 0.05 m
#   * C_w solved so  rho_bulk·C_w·head_des^1.5 == design overflow  -> d(m_liq)/dt = 0 at design
#   * holdup seeded rho_bulk·A·level_des  -> level_from_holdup reads exactly 80 % at design T_bulk.
REACT_LIQ_H_M       = REACT_LIQ_H_MM / 1000.0                      # 25.0 m liquid span (LT 0->100 %)
REACT_T_BULK_DES    = sum(REACT_NODE_SS_DES) / 4.0                 # design bulk temp = node mean (~179.7 C)
REACT_RHO_BULK_DES  = reactor.liquid_density(REACT_T_BULK_DES)     # design bulk melt density, kg/m^3
REACT_WEIR_HEAD_DES = 0.05                                         # design head over the lip, m (sets C_w)
REACT_WEIR_CREST_M  = REACT_LEVEL_NLL_PCT / 100.0 * REACT_LIQ_H_M - REACT_WEIR_HEAD_DES  # 19.95 m lip elev
REACT_WEIR_CW       = _react_mdot_kgh / (REACT_RHO_BULK_DES * REACT_WEIR_HEAD_DES ** 1.5)  # Francis coeff, m^3/h/m^1.5
REACT_M_LIQ_DES     = REACT_RHO_BULK_DES * _react_area_m2 * (REACT_LEVEL_NLL_PCT / 100.0 * REACT_LIQ_H_M)  # design holdup, kg
# --- Fix-2: synthesis-pressure forcing from the per-pass conversion deficit -------------------
REACT_OFFGAS_DEFICIT_GAIN = 1.0  # off-gas NH3/CO2 slip amplifier per unit conversion deficit δ_X
REACT_PI_KAPPA     = 2.0         # κ: dimensionless pressure forcing Π = κ·δ_X (δ_X = 1 - conversion_factor)
REACT_NC_OVERFLOW_GAIN = 0.5     # AT-322701 excess-NH3 partition gain: fraction of the design overflow
                                 # NH3 repartitioned overflow<->off-gas per unit feed-N/C deviation
                                 # (L_feed/L0 - 1).  NH3-only shift -> total N & C conserved (CO2 fixed),
                                 # so the reactor->stripper stream N/C (AT-322701) tracks the feed N/C
                                 # instead of staying atom-pinned.  == 0 at design (L_feed=L0 -> bit-exact).
# --- Fix-3: first-order recycle lag + genuine blended reactor feed ----------------------------
REACT_TAU_REC_MIN  = 5.0         # τ_rec: HP synthesis-loop recycle inventory lag time constant (min)
REACT_FRESH_FRAC   = 0.30        # φ_f: fresh make-up fraction of the reactor feed (1-φ_f = lagged recycle)
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
SCRUB_CARB_KMOLH_DES_REF = dict(SCRUB_CARB_KMOLH_DES)    # FROZEN design wash (deviation datum; never mutate)
SCRUB_CARB_ABS_GAIN  = 0.15      # kmol extra CO2 scrubbed per kmol surplus carbamate-wash flow (323P001)
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
SCRUB_OFFGAS_T_C     = 114.0     # C, TT-322011 off-gas vent-top temp -> HV-322604 (DESIGN PIN)
SCRUB_OFFGAS_T_GAIN  = 120.0     # C / (N/C unit), TT-322011 rise w/ excess-NH3 loop slip: k*(AT-322701 - N/C_des)
SCRUB_OFFGAS_T_VENT_GAIN  = 20.0 # C / (theta/theta_des - 1), TT-322011 rise w/ HV-322604 opening (more uncondensed vent overhead)
SCRUB_OVERFLOW_T_VENT_GAIN = 12.0 # C / (theta/theta_des - 1), TT-322002 fall w/ HV-322604 opening (vent relief cools bottom overflow)
SCRUB_OFFGAS_P_BARA  = 140.7     # bar a, off-gas line pressure (synthesis)
SCRUB_OFFGAS_RHO     = 111.0     # kg/m³, off-gas density (114 C, 140.7 bar a)
SCRUB_OVERFLOW_T_C   = 178.8     # C, TT-322002 overflow temp -> 322F001 (= EJ_T_SUCTION_C)
SCRUB_OVERFLOW_P_BARA = 140.7    # bar a, PT-329201 overflow-line pressure
SCRUB_DH_CARB_KJMOL  = 160.0     # kJ/mol CO2 absorbed, carbamate-formation exotherm (diagnostic)
# --- HV-322604 off-gas valve (choked isenthalpic letdown 322E003 -> 322C001) ---
SCRUB_HIC604_DES_PCT = 50.0      # %, HIC-322604 design opening (HV-322604, inert purge)
SCRUB_HV604_P_OUT    = 4.0       # bar a, 322C001 LP-absorber downstream pressure
SCRUB_HV604_MU_JT    = 0.55      # C/bar, mixture Joule-Thomson coeff (NH3/CO2-rich off-gas)
SCRUB_HV604_DP_DES   = SCRUB_OFFGAS_P_BARA - SCRUB_HV604_P_OUT   # 136.7 bar, design ΔP across HV-322604 (dP_des)
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
# F4: CCW loops are now real first-order plant lag + velocity I-PD (no algebraic SP-pin island).
FIC_329409_TAU_S     = 3.0       # s, FV-329409 flow-loop plant lag (fast circulation pump)
FIC_329409_KC        = 0.08      # %OP per t/h, REVERSE-acting velocity gain (PV in raw t/h, O(300))
FIC_329409_TI        = 6.0       # s, integral time
TIC_329005_TAU_S     = 25.0      # s, TV-329005 supply-T plant lag (tempered-water thermal mass)
TIC_329005_KC        = 1.0       # %OP per C, DIRECT-acting velocity gain (PV in raw C, O(80))
TIC_329005_TI        = 15.0      # s, integral time
TIC_329005_LOAD_GAIN = 10.0      # C load offset per unit (co2_scale-1 + delta_X); 0 at design (s=1)
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
SYN_P_VENT_GAIN     = 0.30       # bar/bar, PT lift per unit HV-322604 vent deficit (1-vent_frac) -- calib
SYN_P_TAU_MIN       = 4.0        # min, loop-pressure accumulation time constant (vapour inventory)
SYN_P_MIN_BARA      = 120.0      # bar a, PT clamp floor
SYN_P_MAX_BARA      = HPCC_P_DES_BARA  # 144.2 bar a, PT ceiling = feed-supply head (CO2/HPCC/ejector all 144.2); loop cannot exceed feed delivery P
SCRUB_Q_CCW_DES_KW   = SCRUB_CCW_KGH_DES * SCRUB_CCW_CP * (SCRUB_CCW_T_OUT_DES - SCRUB_CCW_T_IN_DES) / 3600.0  # ≈5329 kW
# 322E003 shell-side effective conductance (ε-NTU). Back-calibrated so the design
# carbamate-condensation duty pins BOTH the design overflow temp and CCW outlet EXACTLY:
#   UA_eff,des = Q_des/(T_overflow,des − T_ccw,in,des) = 5329/(178.8−80) = 53.94 kW/K
#   C_ccw,des  = ṁ_ccw,des·cp/3600 = 355.3 kW/K ;  ε_des = UA_eff/C_ccw = 0.1518
#   UA = −C_ccw·ln(1−ε_des) = 58.5 kW/K  (constant; ε floats with CCW flow off-design)
_SCRUB_C_CCW_DES_KWK = SCRUB_CCW_KGH_DES * SCRUB_CCW_CP / 3600.0                                  # ≈355.3 kW/K
_SCRUB_UAEFF_DES_KWK = SCRUB_Q_CCW_DES_KW / (SCRUB_OVERFLOW_T_C - SCRUB_CCW_T_IN_DES)             # ≈53.94 kW/K
SCRUB_UA_KWK         = -_SCRUB_C_CCW_DES_KWK * math.log(1.0 - _SCRUB_UAEFF_DES_KWK / _SCRUB_C_CCW_DES_KWK)  # ≈58.5 kW/K
SCRUB_T_PROC_C       = 185.0     # C, process-gas (carbamate) condensation ceiling — the absolute max T
#   the shell side can reach.  GAP #2 ε-NTU anchor: as ṁ_ccw -> 0 (FIC-329409 shut) both TT-329125 and
#   TT-322002 asymptote here instead of +inf.  > SCRUB_OVERFLOW_T_C design 178.8 (synthesis-P headroom).


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


HPCC_UA = None       # shell conductance (kJ/h.K); back-calculated at module load (design-pinned)
_STEAM_READY = False # gate: step_steam stays OFF until valve coeffs are pinned (boot-pin phase 2)


def hpcc_322e002(gas_feed: dict, liq_feed: dict, t_shell: float = HPCC_STEAM_TSAT_C) -> dict:
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
    # NOTE (intended emergent behavior, NOT a bug): co2_abs is MINIMIZED at the design N/C (CO2 recycle
    # is smallest at the balanced operating point; off-design either way sheds more CO2 into the loop).
    # This minimum propagates through the steam header as a POSITIVE feedback V-trough in TT-322010:
    #   co2_abs(min@des) -> q_carb -> P_LP -> MP->LP letdown drains MP -> P_MP -> T_steam=Tsat(P_MP)
    #   -> stripper T_top/T_bot + HPCC T_feed_mix/T_adb -> T_prod (TT-322010, min ~167 C at design).
    # The vertex is sharp but CONTINUOUS (fine N/C probe: 180.9 -> 167.0 -> 211.4 across 2.00/2.023/2.05);
    # the ~30 C "seam jump" seen on a coarse 0.05-step N/C sweep is a SAMPLING artifact of a sharp min,
    # amplified by the NTU exp() quench -- not a model discontinuity. Do NOT "smooth" this in the
    # chemistry; the only legitimate lever is steam-header feedback gain (letdown sizing / P_LP setpoint).
    co2_abs   = max(gas_feed["top_kmolh"].get("CO2", 0.0) - gas["CO2"], 0.0)   # kmol/h gas->liq
    q_carb_kw = co2_abs * 1000.0 * HPCC_DH_CARB_KJMOL / 3600.0
    q_sens_kw = gas_m * HPCC_CP_GAS * max(gas_feed["T_top"] - HPCC_T_PROD_DES_C, 0.0) / 3600.0
    duty_kw   = q_carb_kw + q_sens_kw
    steam_kgh = duty_kw * 3600.0 / HPCC_LATENT_4BAR
    # 4. adiabatic carbamate-exotherm spike, THEN design-pinned single-stream effectiveness-NTU
    #    quench against the shell saturation limit (mass-energy coupled, two-phase outlet temp):
    #       T_adb  = T_feed_mix + q_carb*3600/(m_dot*cp)                 (reaction-heated stream)
    #       T_prod = T_sat_shell + (T_adb - T_sat_shell)*exp(-UA/(m_dot*cp))   (NTU quench)
    #    T_feed_mix = mass-weighted mix of strip-gas (T_top) + ejector-carbamate (T_C, COLD motive ~29 C)
    #    tube-side feeds; m_dot = total tube-side throughput.  The carbamate-formation exotherm q_carb
    #    lifts the cold mixed feed (~156 C) above the 170 C pin; the shell then quenches it back down.
    #    q_carb ~ throughput and m_dot ~ throughput, so the spike is INTENSIVE (~const vs flow), keeping
    #    the asymptotes physical.  UA back-calculated at module load so T_prod == 170.0 C exactly at
    #    m_dot_des.  flow->0 => NTU->inf => T_prod->T_sat_shell (146.3, full quench to shell);
    #    flow->inf => NTU->0 => T_prod->T_adb (full adiabatic reaction temp, no shell duty reaches it).
    m_gas_in   = sum(gas_feed["top_kmolh"].get(k, 0.0) * MW_COMP[k] for k in MW_COMP)
    m_liq_in   = sum(liq_feed["comp"].get(k, 0.0) for k in MW_COMP)
    m_dot      = m_gas_in + m_liq_in
    T_feed_mix = ((m_gas_in * gas_feed["T_top"] + m_liq_in * liq_feed["T_C"]) / m_dot
                  if m_dot > 1e-9 else t_shell)
    T_adb      = T_feed_mix + q_carb_kw * 3600.0 / max(m_dot * HPCC_CP_GAS, 1e-9)
    if HPCC_UA is None:                       # module-load back-calc pass: hold the design pin
        T_prod = HPCC_T_PROD_DES_C
    else:
        T_prod = t_shell + (T_adb - t_shell) \
                 * math.exp(-HPCC_UA / max(m_dot * HPCC_CP_GAS, 1e-9))
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
        "T_prod": T_prod, "T_feed_mix": T_feed_mix, "T_adb": T_adb, "m_dot": m_dot, "P_bara": p_bub,
        "P_bub": p_bub, "L_hpcc": L_hpcc, "W_hpcc": W_hpcc,
        "duty_kw": duty_kw, "steam_kgh": steam_kgh,
    }


# ----- 322E002 HPCC liquid inventory (Euler level state) -------------------------------------
# Dynamic liquid level driven by the hydraulic ODE:
#   d(HPCC_Level)/dt = (carbamate condensation/recycle in) - (ejector-driven forward flow out).
# Forward flow (HPCC -> 322R001) is pushed by the ejector developed head (PI_disch ~ phi_m^2, the
# loop circulator); inflow is the live carbamate condensation make.  Both fractions == 1 at design
# -> dLevel/dt == 0 (holds NLL, bit-exact).  On motive (ejector) stall the forward flow collapses
# as phi_m^2 faster than the condensation inflow (stripper top gas keeps condensing, motive-
# independent) -> the HPCC level SWELLS (accumulates).
HPCC_LEVEL_NLL_PCT = 50.0        # LT-322E002 design normal liquid level (% of sump span)
HPCC_TAU_FILL_MIN  = 6.0         # carbamate-condenser liquid holdup time (level fill const, min)
_HPCC_DES = hpcc_322e002(
    stripper_322e001(CO2_DES_KGH / 1000.0, STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA),
    ejector_322f001(EJ_MOTIVE_NH3_DES, EJ_MOTIVE_T_DES_C, EJ_OPEN_DES))            # design make ref
HPCC_LIQ_DES_KGH   = _HPCC_DES["liq_kgh"]                                          # design make
# HPCC_UA (shell conductance, kJ/h.K) is design-pinned AFTER step_sim is defined, by a one-shot
# settle warm-up on the LIVE loop (see _pin_hpcc_ua() near the module tail).  The synthetic single-
# call construction above understates the tube throughput by ~2 % (its stripper sees CO2_DES_KGH
# directly, not the SETTLED reactor-overflow recycle tear), and with the steep adiabatic-exotherm
# spike (T_adb_des ~600 C) that 2 % m_dot error displaces the NTU-pinned outlet by ~0.4 C.  Pinning
# on the settled live design state instead anchors TT-322010 to exactly 170.0 C.  HPCC_UA stays None
# until that pass runs (None => hpcc_322e002 holds the 170.0 C design pin every tick).


def react_322r001(hpcc: dict, co2_feed_th: float, hic_322605_pct: float,
                  L_drive: float = None, W_drive: float = None,
                  T_overflow_c: float = REACT_OVERFLOW_T_C) -> dict:
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
    # F5: T_overflow_c is the PRIOR-step live reactor lip temp (loop-break) so the f_T(T,L) optimum
    # parabola now flexes the conversion with bulk temperature; == REACT_OVERFLOW_T_C at design (s=1)
    # -> conversion_factor==1.0 bit-exact.  Loop gain dT_lip/dT_in = ΔT_col·df_T/dT ≈ 0.16 < 1 (stable).
    xi_urea, overflow, X_conv, L_feed, W_feed = reactor.react_couple(
        feed, overflow, REACT_XI_UREA_DES * s, T_overflow_c,
        L_override=L_drive, W_override=W_drive)
    # AT-322701 response (excess-NH3 partition).  The urea couple (CO2 + 2 NH3 -> Urea + H2O) has
    # ΔN = ΔC = 0, so it leaves the overflow N/C atom-pinned regardless of feed N/C -> AT-322701 was
    # invariant.  Physically an NH3-rich feed (L_feed > L0) carries proportionally more FREE NH3 in
    # the liquid overflow to the stripper, while an NH3-starved feed sheds NH3 to the off-gas.  Move
    # NH3 ONLY between overflow and off-gas (CO2 untouched) so total N & C are conserved (global
    # closure_resid invariant) but the reactor->stripper stream N/C now tracks the feed N/C.
    # Bit-exact at design: L_feed = L0 -> nh3_shift = 0 -> overflow/off-gas == pinned design HMB.
    nh3_shift = REACT_NC_OVERFLOW_GAIN * (L_feed / reactor.L0_DES - 1.0) * REACT_OVERFLOW_DES["NH3"] * s
    nh3_shift = max(min(nh3_shift, 0.9 * offgas.get("NH3", 0.0)), -0.5 * overflow.get("NH3", 0.0))
    overflow["NH3"] = overflow.get("NH3", 0.0) + nh3_shift   # NH3-rich liquid effluent at high N/C
    offgas["NH3"]   = offgas.get("NH3", 0.0)   - nh3_shift   # conserved: total NH3 unchanged
    # Fix-2: de-pin the off-gas off the conversion deficit.  δ_X is the fractional shortfall of the
    # live per-pass conversion below design (clamped >= 0): the un-converted NH3 + CO2 that DON'T
    # make carbamate/urea flash off the reactor top, so the off-gas NH3 and CO2 are amplified by
    # (1 + gain·δ_X).  At/above design δ_X = 0 -> off-gas == pinned design (bit-exact, no spurious
    # shrink at high N/C).  Dalton partial pressures p_i = y_i · P_offgas are then tracked off the
    # AMPLIFIED off-gas composition; the dimensionless loop forcing Π = κ·δ_X (built in step_sim).
    delta_X = max(1.0 - X_conv / reactor.X_DES_RAW, 0.0)
    amp = 1.0 + REACT_OFFGAS_DEFICIT_GAIN * delta_X
    offgas["NH3"] = offgas.get("NH3", 0.0) * amp
    offgas["CO2"] = offgas.get("CO2", 0.0) * amp
    og_tot   = sum(offgas.values())
    p_nh3_og = (offgas.get("NH3", 0.0) / og_tot) * REACT_OFFGAS_P_BARA if og_tot > 0.0 else 0.0
    p_co2_og = (offgas.get("CO2", 0.0) / og_tot) * REACT_OFFGAS_P_BARA if og_tot > 0.0 else 0.0
    closure_resid = (sum(feed.values())
                     - (sum(overflow.values()) + sum(offgas.values()))
                     - xi_urea)
    return {"overflow_kmolh": overflow, "offgas_kmolh": offgas, "feed_kmolh": feed,
            "xi_urea": xi_urea, "xi_biu": xi_biu, "closure_resid": closure_resid,
            "T_overflow": REACT_OVERFLOW_T_C, "T_offgas": REACT_OFFGAS_T_C,
            "P_bara": REACT_P_BARA, "P_offgas": REACT_OFFGAS_P_BARA,
            "phi": phi, "phi_des": phi_des, "co2_scale": s,
            "X_conv": X_conv, "L_feed": L_feed, "W_feed": W_feed,
            "delta_X": delta_X, "p_nh3_og": p_nh3_og, "p_co2_og": p_co2_og}


def scrub_322e003(offgas_feed: dict, co2_scale: float, t_ccw_in: float,
                  m_ccw_kgh: float, vent_ratio: float = 1.0, nc_act: float = None,
                  hic604_pct: float = None) -> dict:
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
    # --- 323P001 weak-carbamate recycle wash: LIVE deviation injection (design bit-exact) ----------
    # Surplus wash above/below the design rate (carb_dev = carb − carb_des·s) is a real liquid-phase
    # absorbent perturbation: (1) its mass leaves with the bottom overflow (-> 322F001 ejector suction),
    # and (2) the surplus absorbent scrubs extra CO2 (+ paired NH3 at the 2:1 carbamate stoichiometry)
    # out of the off-gas into that overflow.  Both terms are DEVIATIONS from the design wash, so at
    # carb == carb_des·s every term is identically 0 -> pinned off-gas/overflow HMB + TT pins hold exact.
    carb_dev     = {k: carb[k] - SCRUB_CARB_KMOLH_DES_REF.get(k, 0.0) * s for k in MW_COMP}
    carb_dev_tot = sum(carb_dev.values())
    for k in MW_COMP:
        overflow[k] += carb_dev[k]                                            # surplus absorbent -> bottom liquid
    d_co2 = SCRUB_CARB_ABS_GAIN * carb_dev_tot                                 # extra CO2 scrubbed by surplus wash
    d_co2 = max(min(d_co2, 0.5 * offgas.get("CO2", 0.0)), -0.5 * offgas.get("CO2", 0.0))  # bounded -> off-gas>0
    d_nh3 = max(min(2.0 * d_co2, 0.5 * offgas.get("NH3", 0.0)), -0.5 * offgas.get("NH3", 0.0))  # 2 NH3:1 CO2
    offgas["CO2"] -= d_co2;  overflow["CO2"] += d_co2                          # mass-conserving gas->liquid
    offgas["NH3"] -= d_nh3;  overflow["NH3"] += d_nh3
    closure_resid = sum(feed.values()) - sum(offgas.values()) - sum(overflow.values())
    co2_abs   = max(offgas_feed.get("CO2", 0.0) - offgas["CO2"], 0.0)          # kmol/h gas->carbamate (now wash-live)
    q_carb_kw = co2_abs * 1000.0 * SCRUB_DH_CARB_KJMOL / 3600.0                # full exotherm (diag)
    q_ccw_kw  = SCRUB_Q_CCW_DES_KW * s * vent_ratio                            # Q_scrubber: carbamate-cond. duty (s × synthesis-vent load PT-329201)
    # GAP #2 — ε-NTU condenser bridge bounds BOTH the CCW outlet and the process overflow against the
    # condensation ceiling T_proc, killing the ṁ_ccw -> 0 (FIC-329409 shut) divide-by-zero pole.  Old
    # code blew up two ways: the raw sensible rise q_ccw/(ṁ_ccw·cp) AND q_ccw/UA_eff both -> ~1e9 C.
    #   C_ccw = max(ṁ_ccw·cp/3600, 1e-6) ; ε = 1−exp(−UA/C_ccw) ; UA_eff = max(ε·C_ccw, 1e-6)
    #   T_overflow = min(t_ccw_in + q_ccw/UA_eff, T_proc)        (design 80 + 5329/53.94 = 178.8, pinned)
    #   T_ccw_out  = t_ccw_in + (T_overflow − t_ccw_in)·ε        (CCW rides the SAME ε toward the LIVE
    #     condensing temp T_overflow, itself ≤ T_proc).  Because 98.8·UA_eff,des ≡ q_ccw,des, design
    #     ε·98.8 = q_ccw/C_ccw = 15.0 -> TT-329125 = 95.0 EXACT (holds the line-557 pin); ṁ_ccw -> 0 ->
    #     ε -> 1 -> T_overflow, T_ccw_out -> T_proc (185) instead of +inf.  Anchoring T_ccw_out's
    #     gradient to T_overflow (not raw T_proc) is what preserves the 95.0 pin — raw T_proc drifts 95.9.
    C_ccw_kwk  = max(m_ccw_kgh * SCRUB_CCW_CP / 3600.0, 1e-6)                  # floored heat-capacity rate
    eps_ht     = 1.0 - math.exp(-SCRUB_UA_KWK / C_ccw_kwk)                     # single-stream effectiveness
    ua_eff_kwk = max(eps_ht * C_ccw_kwk, 1e-6)
    # HV-322604 vent-opening deviation theta_dev = θ/θ_des − 1 ∈ [−1,+1] over 0..100 %; ≡ 0 at θ_des (50 %).
    # Two-sided LIVE coupling, zero at design -> off-gas/overflow HMB + every TT pin stay bit-exact at θ_des.
    theta_dev  = (hic604_pct if hic604_pct is not None else SCRUB_HIC604_DES_PCT) / SCRUB_HIC604_DES_PCT - 1.0
    t_overflow_cond = min(t_ccw_in + q_ccw_kw / ua_eff_kwk, SCRUB_T_PROC_C)   # condensation-driven overflow T
    t_ccw_out  = t_ccw_in + (t_overflow_cond - t_ccw_in) * eps_ht            # TT-329125 (CCW pin anchored to cond. T)
    # TT-322002: condensation T minus the vent-opening deviation — opening HV-322604 relieves the scrubber and
    # cools the bottom carbamate overflow; closing pressurises and heats it (toward the T_proc ceiling).
    t_overflow = min(max(t_overflow_cond - SCRUB_OVERFLOW_T_VENT_GAIN * theta_dev, t_ccw_in),
                     SCRUB_T_PROC_C)                                          # TT-322002 (vent-coupled, clamped)
    dT_ccw     = t_ccw_out - t_ccw_in                                         # TDY-329125 (cond. quality)
    # TT-322011 off-gas vent-top temp — LIVE off the excess-NH3 loop slip (AT-322701).  At higher feed N/C
    # the synthesis loop runs CO2-limited: excess NH3 cannot form carbamate, slips unabsorbed through the
    # scrubber, and its higher vapour load lifts the uncondensed vent-top temp.  Driver = (AT-322701 - N/C_des):
    # at design L_feed=L0 -> nh3_shift=0 -> AT-322701 = N/C_des -> deviation 0 -> 114.0 EXACT (bit-pin).
    # Physically bounded: cannot fall below the CCW inlet, cannot exceed the condensation ceiling T_proc.
    nc = nc_act if nc_act is not None else SCRUB_OFFGAS_NC_DES                # AT-322701 (loop N/C); design fallback
    t_offgas   = min(max(SCRUB_OFFGAS_T_C + SCRUB_OFFGAS_T_GAIN * (nc - SCRUB_OFFGAS_NC_DES)
                         + SCRUB_OFFGAS_T_VENT_GAIN * theta_dev,
                         t_ccw_in), SCRUB_T_PROC_C)                           # TT-322011 (N/C + vent-coupled, clamped)
    return {"feed_kmolh": feed, "carb_kmolh": carb,
            "offgas_kmolh": offgas, "overflow_kmolh": overflow,
            "closure_resid": closure_resid, "co2_abs": co2_abs,
            "q_carb_kw": q_carb_kw, "q_ccw_kw": q_ccw_kw,
            "t_ccw_in": t_ccw_in, "t_ccw_out": t_ccw_out, "dT_ccw": dT_ccw,
            "m_ccw_kgh": m_ccw_kgh, "co2_scale": s, "vent_ratio": vent_ratio,
            "eps_ht": eps_ht, "ua_eff_kwk": ua_eff_kwk,                        # ε-NTU bridge diag
            "T_offgas": t_offgas, "P_offgas": SCRUB_OFFGAS_P_BARA,
            "T_overflow": t_overflow, "P_overflow": SCRUB_OVERFLOW_P_BARA}


def hv_322604(offgas: dict, T_in: float, hic_pct: float, p_up: float) -> dict:
    """HV-322604 HP-scrubber off-gas valve — dynamic isenthalpic letdown 322E003 -> 322C001.
    Inert purge to the LP absorber.  Flow follows the valve hydraulic characteristic, driven by
    the live controller opening θ (HIC-322604) and √ΔP across the seat:
        m_og = m_og_des·s · (θ/θ_des) · √(max(P_up−P_down,0)/ΔP_des)   (θ_des = design opening 50%)
    The incoming `offgas` vector is already the design purge × s, so the valve factor scales it
    1:1 (composition held; θ=θ_des & P_up=design -> factor=1 -> bit-exact design HMB).  Dynamic
    Joule-Thomson cooling on the ACTUAL pressure drop:  T_out = T_in − μ_JT·ΔP."""
    dP    = max(p_up - SCRUB_HV604_P_OUT, 0.0)
    theta = max(hic_pct, 0.0)
    valve = (theta / SCRUB_HIC604_DES_PCT) * math.sqrt(dP / SCRUB_HV604_DP_DES)   # θ-opening × √ΔP-ratio
    comp  = {k: offgas.get(k, 0.0) * valve for k in MW_COMP}                      # throttled flow, comp held
    T_out = T_in - SCRUB_HV604_MU_JT * dP                                         # dynamic JT letdown
    m_kgh = sum(comp.get(k, 0.0) * MW_COMP[k] for k in MW_COMP)                   # = m_og_des·s·valve
    return {"comp_kmolh": comp, "T_out": round(T_out, 1),
            "P_out": SCRUB_HV604_P_OUT, "P_in": round(p_up, 1), "open_pct": hic_pct,
            "mass_kgh": m_kgh, "valve_frac": valve, "dP": round(dP, 1)}


def react_nc_ratio(comp_kmolh: dict) -> float:
    """AT-322701: molar N/C ratio (Σ nᵢ·#Nᵢ)/(Σ nᵢ·#Cᵢ) of a stream on an atom basis."""
    n = sum(comp_kmolh.get(k, 0.0) * a for k, a in REACT_N_ATOMS.items())
    c = sum(comp_kmolh.get(k, 0.0) * a for k, a in REACT_C_ATOMS.items())
    return (n / c) if c else 0.0


# Design AT-322701 (overflow N/C) reference for TT-322011 off-gas-temp slip model.  At design L_feed=L0 ->
# nh3_shift=0 -> overflow == pinned design HMB, so this is the exact bit-pin anchor (nc_act-nc_des = 0).
SCRUB_OFFGAS_NC_DES = react_nc_ratio(REACT_OVERFLOW_DES)   # ≈ 3.000, computed once at import


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
    return {"MAN": "M", "AUTO": "A", "CAS": "C", "OOS": "O"}.get(c.mode, "M")


# ----- Plant state -----
class State:
    def __init__(self):
        # tank
        self.tank_level_frac = 0.65
        self.tank_T_C        = 25.0
        self.tank_P_top_barG = 12.3
        self.F_in_BL_th      = 42.762   # t/h, BL NH3 makeup (seed; set live by LIC-321501 = pump draw)
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
        # Fix-1: DYNAMIC 4-node axial thermal state [T1(bot)..T4(top)] -> TT-322008..005, seeded at
        #   the design SS profile so the as-built telemetry (172.6/180.8/182.5/182.9) is bit-exact on init.
        self.react_T_node     = list(REACT_NODE_SS_DES)
        self.react_T_overflow = REACT_OVERFLOW_T_C   # TT-322014 overflow lip temp (dynamic anchor)
        self.react_T_offgas   = REACT_OFFGAS_T_C     # TT-322009 off-gas line temp (dynamic)
        # Fix-3: lagged recycle states (τ_rec) blended with the fresh feed to drive Inoue-Kanai f_L/f_W.
        #   Seeded at design (L0/W0) -> blend == design feed -> conversion bit-exact on init.
        self.react_L_rec = reactor.L0_DES    # lagged recycle N/C (NH3/CO2) contribution
        self.react_W_rec = reactor.W0_DES    # lagged recycle H/C (H2O/CO2) contribution
        # LT-322504 reactor liquid level (%) — DYNAMIC inventory state (mass balance, open-loop:
        # HV-322605 is hand/auto and does NOT control level). dV/dt = Q_in - Q_out(φ).
        self.react_level_pct = REACT_LEVEL_NLL_PCT      # init at design NLL = 80 % (derived from react_m_liq)
        # Fix-2b: CONSERVED liquid holdup mass (kg) — the true level state.  level = m_liq/(rho(T)·A),
        #   so cooling (rho up) drops the level below the weir lip even with the holdup frozen.
        self.react_m_liq     = REACT_M_LIQ_DES          # seeded rho_bulk·A·level_des -> reads 80 % at design
        self.hpcc_level_pct  = HPCC_LEVEL_NLL_PCT       # 322E002 liquid inventory, init design NLL
        # pumps: open_act = torque-converter valve opening %
        self.pumpA = {"on": False, "open_act": 0.0,  "speed_act": 0.0,   "current": 0.2,  "mode": "M", "fault": False}
        self.pumpB = {"on": True,  "open_act": 86.2, "speed_act": 131.0, "current": 43.9, "mode": "M", "fault": False}
        # controllers (percent)
        self.SIC_321950 = Controller("SIC_321950", Kc=2.0, Ti=8.0,
                                     sp=80.0, mv=0.0)
        self.SIC_321951 = Controller("SIC_321951", Kc=2.0, Ti=8.0,
                                     sp=86.2, mv=86.2)   # MAN holds B at 86 %
        self.controllers: dict = {
            "SIC_321950": self.SIC_321950,
            "SIC_321951": self.SIC_321951,
        }
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
        self.PIC_322203   = {"mode": "MAN", "op": 0.0, "sp": CO2_P_DES_BARA,
                             "pv": CO2_P_DES_BARA, "pv_prev": CO2_P_DES_BARA}
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
                            "sp": SCRUB_CCW_KGH_DES / 1000.0, "pv": SCRUB_CCW_KGH_DES / 1000.0,
                            "pv_prev": SCRUB_CCW_KGH_DES / 1000.0}                              # t/h
        self.TIC_329005  = {"mode": "AUTO", "op": SCRUB_TV005_DES_PCT,
                            "sp": SCRUB_CCW_T_IN_DES, "pv": SCRUB_CCW_T_IN_DES,
                            "pv_prev": SCRUB_CCW_T_IN_DES}                                      # C
        # PT-329201 synthesis-loop top pressure (DYNAMIC state, reverse Q->P accumulation):
        #   CCW condensation deficit lifts it; first-order relax to the forward stripper-set target.
        self.p_syn_bara  = SYN_P_DES_BARA                # init at design PT-329201 = 140.7 bar a
        # MP/LP steam headers (DYNAMIC lumped-capacitance states, quarantined steam_system module).
        #   Seeded at the stripper/HPCC design saturation pressures (NOT steam_system's generic 25.0
        #   default) so tsat(P_MP)=211.6 == STRIP_STEAM_T_DES_C and the LP offset is 0 -> design
        #   forward pass is bit-exact; valve coeffs are pinned at import for a stationary fixed point.
        self.steam = SteamState(P_MP=STRIP_STEAM_P_BARA, P_LP=HPCC_STEAM_P_BARA)
        # ext override
        self.ext_override = False
        # sim-speed mode (set_sim_mode cmd): "SLOW" = real-time/realistic (default, anchor), "FAST" = accelerated
        self.sim_mode = "SLOW"
        # trips: live initiator conditions (instantaneous) + latched state (P1-2).
        #   A latch holds once set and can only be cleared by an operator trip_reset AND
        #   the live condition having recovered -> a tripped pump cannot self-restart.
        self.trips        = {"21_2": False, "21_4": False, "21_8": False, "21_10": False}
        self.trip_latched = {"21_2": False, "21_4": False, "21_8": False, "21_10": False}
        # L3 phase-boundary diagnostics (mushy-zone / crystallization detection, Batch 2)
        self.flags = {"SCRUBBER_SOLIDIFICATION": False,
                      "STRIPPER_SOLIDIFICATION": False,
                      "CARBAMATE_DEPOSITION":    False,
                      "RATIO_PV_BAD":            False}   # L3-3 N/C measurement-validity (Batch 3)


state = State()
_ctrl_lock = threading.Lock()
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
    pic["pv_bad"] = not _pv_ok(pic["pv"], pic["sp"])        # L3-9 freeze-last-good on bad PV/SP
    if pic["mode"] == "AUTO" and not pic["pv_bad"]:
        # F2: velocity I-PD, DIRECT-acting (sigma=-1): rising line-P -> open vent.  P acts on PV
        # (no SP derivative kick), I acts on error.  Kc/Ti = 0.5 reproduces the old integral-only
        # gain; the added Kc·ΔPV proportional term damps the static-gain vent loop.  PV==SP & steady
        # -> du=0 (bumpless, design-preserving).
        du = PIC_322203_KC * ((pic["pv"] - pic["pv_prev"])
                              + (dt / PIC_322203_TI) * (pic["pv"] - pic["sp"]))
        pic["op"] = clamp(pic["op"] + du, 0.0, 100.0)
    pic["pv_prev"] = pic["pv"]                              # PV_{k-1} for next-tick velocity term
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
            target = ctrl.mv
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

    # LIC-321501 feed-drum makeup: BL import = live pump draw (feed-forward) + P level-restore term,
    #   clamped to the import-line capacity.  import == draw at SS -> level held at SP, no spurious trip.
    s.F_in_BL_th = clamp(F_pump_total_th + TANK_LIC_KP_TH * (TANK_LEVEL_SP_FRAC - s.tank_level_frac),
                         0.0, TANK_BL_MAX_TH)
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
    # P1-3: live 322E003 overflow mass available to entrain = design suction * co2_scale
    #   (scrub overflow = SCRUB_OVERFLOW_KMOLH_DES * co2_scale, no phi term).  Computed here
    #   (ejector precedes the scrubber block this tick) from the live CO2 throughput ratio.
    ej_co2_scale = s.F_CO2_th / (CO2_DES_KGH / 1000.0)
    ej_m_avail   = EJ_SUC_TOT_DES * max(ej_co2_scale, 0.0)
    ej = ejector_322f001(motive_nh3_kgh, TI_321020, s.HIC_322602, m_suc_avail=ej_m_avail)
    # motive fraction (PD pump -> flow ~ speed) and ejector developed-head forward-flow fraction.
    # phi_fwd ~ phi_m^2 (affinity head curve): drives the HPCC->reactor liquid circulation and the
    # discharge-header pressure.  ==1 at design motive -> all hydraulic states hold design.
    phi_m   = clamp(motive_nh3_kgh / EJ_MOTIVE_NH3_DES, 0.0, 1.5)
    phi_fwd = phi_m * phi_m

    # Ratio block PV = molar N/C per feed-ratio eq:  N/C = (m_NH3/m_CO2)*2.584.
    # L3-3 measurement-validity gate: below 5% of design CO2 feed the divisor collapses and the molar
    #   N/C is numerically meaningless -> hold the last-good ratio and raise RATIO_PV_BAD to freeze the
    #   cascade (no garbage SP propagation on black-start / CO2-feed loss).
    NC_A = NC_B = 0.5 * s.ratio_PV            # telemetry default = held last-good split (gated branch)
    if s.F_CO2_th < 0.05 * (CO2_DES_KGH / 1000.0):
        s.flags["RATIO_PV_BAD"] = True        # s.ratio_PV / s.ratio_bal hold last-good (not recomputed)
    else:
        s.flags["RATIO_PV_BAD"] = False
        m_CO2 = max(s.F_CO2_th, 1e-6)
        NC_A  = (F_A_th / m_CO2) * NC_FACTOR      # N/C contributed by pump A
        NC_B  = (F_B_th / m_CO2) * NC_FACTOR      # N/C contributed by pump B
        s.ratio_PV  = NC_A + NC_B                 # total system N/C = (m_NH3_tot/m_CO2)*2.584
        s.ratio_bal = s.ratio_PV

    # ----- HP Stripper 322E001: reactor effluent + live CO2 strip gas -> top gas (322E002)
    #   + bottom solution (LV-322501).  Shell = condensing 329D005 MP steam (boundary T).
    # Stripper consumes the previous step's reactor overflow (tear stream of the synthesis
    # recycle); at design this equals the frozen STRIP_FEED207_KMOLH -> output unchanged.
    T_steam_live = tsat_steam(s.steam.P_MP)           # live sat-steam shell T from MP header pressure
    strip = stripper_322e001(s.F_CO2_th, T_steam_live, STRIP_P_DES_BARA,
                             overflow_kmolh=s.react_overflow_kmolh,
                             L_feed=s.react_L_feed, W_feed=s.react_W_feed)

    # LIC-322501 bottom-solution level control, DIRECT-acting on the FC LV-322501:
    #   level^ -> op^ -> air-to-open valve opens -> drain^ -> level v  (neg. feedback).
    lic = s.LIC_322501
    lic["pv_bad"] = not _pv_ok(s.strip_level, lic["sp"])    # L3-9 freeze-last-good on bad PV/SP
    if lic["pv_bad"]:
        e_lvl = lic["e_prev"]                  # hold last-good error; op frozen (update skipped)
    else:
        e_lvl = s.strip_level - lic["sp"]      # direct-acting error (level above SP -> open)
        if lic["mode"] == "AUTO":              # velocity-form PI (proportional-dominant)
            lic["op"] = clamp(lic["op"]
                              + LIC_322501_KC * ((e_lvl - lic["e_prev"]) + (dt / LIC_322501_TI) * e_lvl),
                              0.0, 100.0)
    lic["e_prev"] = e_lvl                       # track for bumpless MAN->AUTO
    lv_open = clamp(lic["op"], 0.0, 100.0)
    # L3-1 LV-322501 letdown driven by the LIVE synthesis pressure (PT-329201 = s.p_syn_bara), not a
    #   frozen design ΔP.  As the loop depressurizes (black-start / blowdown) the drain head collapses
    #   -> drain -> 0, no spurious letdown from an empty vessel.  Uses prior-step p_syn (same loop-break
    #   convention as nu / dP_vent).  P_down = 4.0 bar a (LP loop downstream of LV-322501).
    #       m_drain = m_drain_des * (Op_LV/Op_LV_des) * sqrt(max(P_syn - P_down,0)/(P_syn_des - P_down))
    dP_lv = max(s.p_syn_bara - LV322501_P_DOWN_BARA, 0.0)
    drain_kgh = STRIP_BOT_DES_KGH * (lv_open / LV322501_OPEN_DES) \
                * (dP_lv / max(SYN_P_DES_BARA - LV322501_P_DOWN_BARA, 1e-6)) ** 0.5
    # L3-6 stripper-bottoms mushy-zone: urea-melt crystallization (T_cryst=132.7 C) throttles the
    #   LV-322501 drain as T_bot falls; the un-drained mass stays in the LT-322501 ODE -> level rises.
    f_drain = _f_flow(strip["T_bot"], 132.7)
    drain_kgh *= f_drain
    s.flags["STRIPPER_SOLIDIFICATION"] = (f_drain < 1.0)
    # bottom-sump mass balance -> LT-322501 level (%)
    m_span_kg = STRIP_SUMP_AREA_M2 * STRIP_LEVEL_SPAN_M * STRIP_RHO_BOTTOM
    s.strip_level = clamp(s.strip_level
                          + (strip["bot_kgh"] - drain_kgh) / 3600.0 * dt / m_span_kg * 100.0,
                          0.0, 100.0)
    lic["pv"] = s.strip_level
    TT_323001 = STRIP_T_DOWN_DES_C + 0.7 * (strip["T_bot"] - STRIP_T_BOTTOM_DES_C)

    # HP carbamate condenser 322E002: strip gas + ejector liquid -> two-phase product to 322R001.
    #   Shell-side LP-steam saturation T tracks the live LP header, but as an OFFSET about the
    #   pinned design constant (HPCC_STEAM_TSAT_C=146.3 differs from Antoine tsat(4.4)~147.4); at
    #   design P_LP==HPCC_STEAM_P_BARA so the offset is 0 -> T_shell_lp==146.3 bit-exact.
    T_shell_lp = HPCC_STEAM_TSAT_C + (tsat_steam(s.steam.P_LP) - tsat_steam(HPCC_STEAM_P_BARA))
    hpcc = hpcc_322e002(strip, ej, t_shell=T_shell_lp)

    # 322R001 HP urea reactor: pinned products from hpcc feed, throughput s, valve φ.
    # f_L loop coupling: the reduced model pins the recycle overflow, so the endogenous feed N/C
    # (hpcc L_hpcc) is dominated by the atom-conserving ripple (conv^ -> NH3 -2d -> feed N/C v):
    # a strong NEGATIVE loop that cannot be amplified.  Drive f_L instead off the EXOGENOUS
    # fresh-feed N/C (s.ratio_PV, set by pump speeds — feedback-free): L_drive maps its deviation
    # onto the reactor-feed N/C, == L0 at design (ratio.PV=RATIO_PV_DES -> conv=1, bit-exact).
    # Drives Inoue-Kanai f_L only; overflow ripple keeps AT-322701 atom-invariant; PT-329201
    # (L_hpcc bubble-point) untouched.
    # Fix-3: genuine blended reactor feed with a first-order recycle lag (replaces the L_override
    # band-aid).  The EXOGENOUS fresh-feed N/C (pump speeds, feedback-free) is the disturbance target
    # L_fresh; the recycle leg L_rec chases it through a τ_rec first-order Euler lag, and the reactor
    # sees the φ_f-weighted blend.  W (reactor-feed H/C) blends the same way off the LIVE HPCC feed.
    # At design L_fresh==L0, W_inst==W0, L_rec/W_rec seeded at design -> blend == design (bit-exact);
    # at settled steady state (t >> τ_rec) the lag fully relaxes (L_rec->L_fresh, W_rec->W_inst) so
    # the blend -> the instantaneous feed and the prior settled conversion is recovered exactly.
    a_rec   = dt / (REACT_TAU_REC_MIN * 60.0)                 # per-tick first-order lag coefficient
    L_fresh = reactor.L0_DES * (1.0 + REACT_NC_LOOP_GAIN * (s.ratio_PV / RATIO_PV_DES - 1.0))
    co2_fd  = hpcc["feed_kmolh"].get("CO2", 0.0)
    W_inst  = (hpcc["feed_kmolh"].get("H2O", 0.0) / co2_fd) if co2_fd > 0.0 else reactor.W0_DES
    s.react_L_rec += a_rec * (L_fresh - s.react_L_rec)        # recycle N/C lags the fresh disturbance
    s.react_W_rec += a_rec * (W_inst  - s.react_W_rec)        # recycle H/C lags the live feed water
    L_blend = REACT_FRESH_FRAC * L_fresh + (1.0 - REACT_FRESH_FRAC) * s.react_L_rec
    W_blend = REACT_FRESH_FRAC * W_inst  + (1.0 - REACT_FRESH_FRAC) * s.react_W_rec
    react   = react_322r001(hpcc, s.F_CO2_th, s.HIC_322605, L_drive=L_blend, W_drive=W_blend,
                            T_overflow_c=s.react_T_overflow)   # F5: prior-step lip temp (loop-break)
    s.react_overflow_kmolh = react["overflow_kmolh"]   # tear -> next step's stripper feed
    s.react_L_feed = react["L_feed"]                   # tear -> next step's stripper eta_T penalty
    s.react_W_feed = react["W_feed"]

    # Fix-1: integrate the distributed 4-node axial thermal profile (Damköhler-shaped exotherm).
    #   dT_n/dt = [ (T_{n-1} - T_n) + g_n·ΔT_col ] / τ_n ,  T_0 = T_feed (HPCC two-phase product),
    #   ΔT_col = ΔT_col,des · conversion_factor  (the profile FLEXES with the live per-pass conversion).
    # Explicit Euler; the upstream term uses the PREVIOUS-step node temps (T_old) so the cascade is
    # decoupled within a tick (steady state is identical: T_old[n-1]==T_new[n-1] -> telescopes to
    # T_n = T_feed + ΔT_col·G_raw(ζ_n), the as-built residence-time probe profile when conv_fac->1).
    conv_fac = react["X_conv"] / reactor.X_DES_RAW
    dT_col   = REACT_DT_COL_DES * conv_fac
    T_old     = list(s.react_T_node)
    T_up      = HPCC_T_PROD_DES_C                             # node-0 upstream = reactor feed T
    flow_frac = clamp(react["co2_scale"], 0.0, 1.0)          # m_dot/m_dot_des proxy: tau-scale + loss gate
    new_T     = []
    for n in range(4):
        # Fix-1/2: flow-scaled residence  tau_n = tau_des/flow_frac  (-> +inf as flow collapses, zero-flow
        #   safe); node_dTdt adds the ANCHOR-GATED ambient wall loss (zero at design, full when stagnant)
        #   so a frozen reactor relaxes dT/dt = -(T_n - T_amb)/tau_loss -> ambient instead of sticking.
        tau_n = (REACT_TAU_NODE_MIN[n] * 60.0 / flow_frac) if flow_frac > 1.0e-9 else float("inf")
        Tn = T_old[n] + reactor.node_dTdt(T_old[n], T_up, REACT_G_NODES[n], dT_col,
                                          tau_n, flow_frac) * dt
        new_T.append(Tn)
        T_up = T_old[n]                                       # next node's upstream = this node (prev step)
    s.react_T_node     = new_T
    s.react_T_overflow = HPCC_T_PROD_DES_C + dT_col           # overflow lip (Σ g_n + g_ov = 1 anchor)
    s.react_T_offgas   = new_T[3] + REACT_OFFGAS_GAMMA * (s.react_T_overflow - new_T[3])
    react["T_overflow"] = s.react_T_overflow                 # publish live profile to telemetry + scrubber
    react["T_offgas"]   = s.react_T_offgas

    # ----- Steam balance handshake (reverse pass): forward duties -> header mass draws -> Euler tick.
    #   Q [kJ/h] = duty_kW * 3600 ;  m [kg/s] = Q / lambda[kJ/kg] / 3600  ==  duty_kW / lambda.
    #   Stripper reboiler draws MP steam (fixed design duty); HPCC raises LP steam (live duty).
    Q_strip_kjh = STRIP_DUTY_DES_KW * 3600.0
    Q_hpcc_kjh  = hpcc["duty_kw"]   * 3600.0
    m_strip = Q_strip_kjh / 1850.0          / 3600.0   # MP steam consumed (kg/s)
    m_hpcc  = Q_hpcc_kjh  / HPCC_LATENT_4BAR / 3600.0  # LP steam generated (kg/s)
    if _STEAM_READY:                        # OFF during both boot-pin settles (headers frozen at design)
        step_steam(s.steam, dt, m_strip, m_hpcc)

    # LT-322504 dynamic level — Fix-2b CONSERVED holdup mass + Francis-weir overflow (DECOUPLED):
    #   m_in   = m_dot_des·s·φ_fwd                         (actual ejector-driven forward feed from HPCC)
    #   m_out  = rho(T_bulk)·C_w·max(0, L - L_weir)^1.5    (level-driven weir; below the lip -> m_out = 0)
    #   d(m_liq)/dt = m_in - m_out ;  L = m_liq/(rho(T_bulk)·A).
    #   Closed CO2 XV (s -> 0): m_in -> 0, level drains to the lip then m_out -> 0, holdup FREEZES; the
    #   reactor then cools, rho(T_bulk) rises, and the same mass reads a level BELOW the lip (un-freeze).
    m_in_react    = _react_mdot_kgh * react["co2_scale"] * phi_fwd
    T_bulk_react  = sum(new_T) / 4.0                          # live bulk temp (= node mean; design 179.7 C)
    level_m_react = REACT_LIQ_H_M * s.react_level_pct / 100.0  # prev-step head feeding the weir (explicit)
    s.react_m_liq += reactor.holdup_dmdt_kgph(m_in_react, level_m_react, T_bulk_react,
                                              crest_m=REACT_WEIR_CREST_M, cw=REACT_WEIR_CW) * (dt / 3600.0)
    s.react_m_liq  = max(s.react_m_liq, reactor.M_HOLDUP_MIN)  # holdup floor -> guards level_from_holdup
    s.react_level_pct = clamp(reactor.level_from_holdup(s.react_m_liq, T_bulk_react,
                                                        area_m2=_react_area_m2) / REACT_LIQ_H_M * 100.0,
                              0.0, 100.0)

    # LT-322E002 HPCC liquid inventory (Euler): carbamate condensation make in - ejector fwd out.
    #   phi_in  = live HPCC liquid make / design make  (stripper-gas condensation is motive-indep)
    #   phi_fwd = phi_m^2 forward circulation out (ejector developed head)
    #   dLevel/dt = (phi_in - phi_fwd)·100/(tau·60)  ->  SWELLS on ejector stall (in > out).
    phi_in_hpcc = (hpcc["liq_kgh"] / HPCC_LIQ_DES_KGH) if HPCC_LIQ_DES_KGH else phi_fwd
    dL_hpcc     = (phi_in_hpcc - phi_fwd) * 100.0 * dt / (HPCC_TAU_FILL_MIN * 60.0)
    s.hpcc_level_pct = clamp(s.hpcc_level_pct + dL_hpcc, 0.0, 100.0)

    # ----- 322E003 HP Scrubber: reactor off-gas + weak carbamate (323P001 A/B) -> off-gas line
    #   (322C001 via HV-322604) + overflow line (322F001).  Shell-side CCW loop (329P006 A/B
    #   circulation + 329E004 tempered-water cooler) removes the carbamate-formation exotherm.
    fic = s.FIC_329409                           # CCW circulation flow controller (FV-329409)
    tic = s.TIC_329005                           # CCW supply-temperature controller (TV-329005)
    fic["pv_bad"] = not _pv_ok(fic["sp"], fic["op"], fic["pv"])   # L3-9 freeze-last-good on bad PV
    if fic["pv_bad"]:                             # bad PV -> hold design CCW flow; op held last-good
        if not math.isfinite(fic["op"]):  fic["op"] = SCRUB_FV409_DES_PCT
        fic["pv"] = SCRUB_CCW_KGH_DES / 1000.0    # coerce finite so no NaN enters m_ccw below
    else:                                         # F4: first-order flow plant lag + AUTO velocity I-PD
        flow_ss = (SCRUB_CCW_KGH_DES / 1000.0) * (fic["op"] / max(SCRUB_FV409_DES_PCT, 1e-6))
        pv_prev = fic["pv_prev"]                   # PV_{k-1} for the velocity proportional term
        fic["pv"] += (dt / FIC_329409_TAU_S) * (flow_ss - fic["pv"])   # lag PV toward valve-char SS
        if fic["mode"] == "AUTO":                  # REVERSE-acting: PV below SP -> open FV-329409
            fic["op"] = clamp(fic["op"] + FIC_329409_KC * (-(fic["pv"] - pv_prev)
                              + (dt / FIC_329409_TI) * (fic["sp"] - fic["pv"])), 0.0, 100.0)
        fic["pv_prev"] = fic["pv"]                 # MAN: op held by operator, PV still lags valve char
    tic["pv_bad"] = not _pv_ok(tic["sp"], tic["op"], tic["pv"])   # L3-9 freeze-last-good on bad PV
    if tic["pv_bad"]:                             # bad PV -> hold design CCW supply T; op held last-good
        if not math.isfinite(tic["op"]):  tic["op"] = SCRUB_TV005_DES_PCT
        tic["pv"] = SCRUB_CCW_T_IN_DES            # coerce finite so no NaN propagates downstream
    else:                                         # F4: first-order supply-T plant lag + AUTO velocity I-PD
        #   T_ss = cooler valve char + exotherm load.  Load = gain·((s-1)+δ_X) -> 0 at design (bit-exact);
        #   a throughput/conversion-deficit rise warms the returning tempered water, which the loop rejects.
        t_load  = TIC_329005_LOAD_GAIN * ((react["co2_scale"] - 1.0) + react["delta_X"])
        T_ss    = clamp(SCRUB_CCW_T_OUT_DES
                        - (SCRUB_CCW_T_OUT_DES - SCRUB_CCW_T_IN_DES) * (tic["op"] / max(SCRUB_TV005_DES_PCT, 1e-6))
                        + t_load, 20.0, SCRUB_CCW_T_OUT_DES)
        pv_prev = tic["pv_prev"]                   # PV_{k-1} for the velocity proportional term
        tic["pv"] += (dt / TIC_329005_TAU_S) * (T_ss - tic["pv"])      # lag PV toward valve-char SS + load
        if tic["mode"] == "AUTO":                  # DIRECT-acting: PV above SP -> open TV-329005 (more cooling)
            tic["op"] = clamp(tic["op"] + TIC_329005_KC * ((tic["pv"] - pv_prev)
                              + (dt / TIC_329005_TI) * (tic["pv"] - tic["sp"])), 0.0, 100.0)
        tic["pv_prev"] = tic["pv"]                 # MAN: op held by operator, PV still lags valve char
    m_ccw_kgh  = max(fic["pv"], 1e-6) * 1000.0    # CCW circulation (t/h -> kg/h)
    top_ratio  = (strip["top_mol"] / STRIP_TOP_MOL_DES) if STRIP_TOP_MOL_DES else 1.0  # stripper overhead push
    nu = s.p_syn_bara / SYN_P_DES_BARA            # vent ratio = PT-329201/PT_des (prior-step state; breaks the algebraic loop)
    # HV-322604 back-pressure penalty — valve vent capacity vs the scrubber's required inert purge:
    #   vent_frac = m_og/(m_og_des·s) = (θ/θ_des)·√(ΔP/ΔP_des);  θ_des = design opening (50%, demand-met).
    #   Pinch below design (vent_frac<1) starves the inert vent -> uncondensed inerts accumulate and
    #   integrate PT-329201 up.  Uses prior-step p_syn for ΔP (same loop-break convention as nu).
    dP_vent   = max(s.p_syn_bara - SCRUB_HV604_P_OUT, 0.0)
    vent_frac = (s.HIC_322604 / SCRUB_HIC604_DES_PCT) * math.sqrt(dP_vent / SCRUB_HV604_DP_DES)
    scrub = scrub_322e003(react["offgas_kmolh"], react["co2_scale"], tic["pv"], m_ccw_kgh,
                          vent_ratio=nu, nc_act=react_nc_ratio(react["overflow_kmolh"]),
                          hic604_pct=s.HIC_322604)
    # PT-329201 reverse heat->pressure: condensation capacity (CCW flow) vs vent demand (s*nu).
    #   rho_cond < 1 (e.g. CCW throttled) -> off-gas under-condenses, accumulates, integrates PT up.
    #   Forward stripper push (top_ratio) sets the no-deficit target; first-order Euler accumulation
    #   over tau (min -> s).  Design: m_ccw=des, s=1, nu=1, top_ratio=1 -> rho=1 -> PT holds 140.7.
    #   Thermal factor f_th = (T_cond − T_ccw_in)/(T_cond − T_ccw_in,des): a WARMER CCW supply
    #   shrinks the condensation driving force -> capacity falls -> rho_cond drops -> PT-329201 rises.
    #   f_th ≡ 1 at design T_ccw_in=80 C, so a pure CCW-flow move reduces to the prior calibration.
    f_th      = (SCRUB_OVERFLOW_T_C - tic["pv"]) / max(SCRUB_OVERFLOW_T_C - SCRUB_CCW_T_IN_DES, 1e-6)
    rho_cond  = (m_ccw_kgh / SCRUB_CCW_KGH_DES) * max(f_th, 0.0) / max(react["co2_scale"] * nu, 1e-6)
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
    # Fix-2: dimensionless conversion-deficit forcing Π = κ·δ_X injected ADDITIVELY into the PT
    # target.  When the reactor under-converts (low N/C / high H/C), the unconverted NH3 + CO2 flash
    # to the synthesis loop and aggressively pressurise it: Π·P_des bar of extra forcing.  δ_X is
    # clamped >= 0 (Fix-2), so at/above design Π = 0 -> no spurious depressurisation at high N/C.
    Pi_conv   = REACT_PI_KAPPA * react["delta_X"]
    pt_target = pt_fwd + SYN_P_DEFICIT_GAIN * max(1.0 - rho_cond, 0.0) * SYN_P_DES_BARA \
                       + SYN_P_VENT_GAIN * (1.0 - vent_frac) * SYN_P_DES_BARA \
                       + Pi_conv * SYN_P_DES_BARA   # HV-322604 vent: TWO-SIDED (open<des -> PT up; open>des -> PT down) + Π forcing
    # L3-2 inventory-aware PT floor: a totally empty loop must be able to bottom out at atmospheric,
    #   not a hard 120 bar.  Loop-mass fraction = mean of the three HP liquid inventories vs their design
    #   NLL (LT-322504 80%, LT-322E002 50%, LT-322501 50%); == 1.0 at design -> P_min == 120 bar (the
    #   static SYN_P_MIN_BARA preserved exactly), -> 1.0 atm as the loop empties.
    #       P_min = 1.0 + 119.0 * clamp(M_loop / M_loop_des, 0, 1)
    m_loop_frac = clamp((s.react_level_pct + s.hpcc_level_pct + s.strip_level)
                        / (REACT_LEVEL_NLL_PCT + HPCC_LEVEL_NLL_PCT + STRIP_LEVEL_SP_DES), 0.0, 1.0)
    p_syn_min   = 1.0 + 119.0 * m_loop_frac
    s.p_syn_bara = clamp(s.p_syn_bara + (dt / (SYN_P_TAU_MIN * 60.0)) * (pt_target - s.p_syn_bara),
                         p_syn_min, SYN_P_MAX_BARA)
    scrub["P_overflow"] = s.p_syn_bara            # PT-329201 dynamic synthesis pressure (bar a)
    scrub["P_offgas"]   = s.p_syn_bara            # off-gas line rides the live synthesis P (HV-322604 P_up)
    scrub["vent_frac"]  = vent_frac               # HV-322604 vent capacity / required purge (<1 -> PT rises)
    scrub["rho_cond"]   = rho_cond                # condensation capacity/demand (diag; <1 -> PT rises)
    scrub["co2_free"]   = co2_free                # free acid CO2 overhead (pressure-building, kmol/h)
    scrub["pb_push"]    = pb_push                 # PT forward push (pressure-building overhead deviation)
    scrub["top_ratio"]  = top_ratio              # total overhead ratio (diag only; superseded by pb_push)
    scrub["P_bub_hpcc"] = hpcc["P_bub"]           # 322E002 bubble-point synthesis P (bar a, diag)
    # L3-5 scrubber-overflow mushy-zone: carbamate crystallization (T_cryst=60 C) throttles the
    #   322F001 overflow as T_overflow falls.  No vessel inventory ODE here (scrubber is a tear) ->
    #   raise SCRUBBER_SOLIDIFICATION as the accumulation proxy when flow is choked.
    f_ovf = _f_flow(scrub["T_overflow"], 60.0)
    scrub["overflow_kmolh"] = {k: v * f_ovf for k, v in scrub["overflow_kmolh"].items()}
    s.flags["SCRUBBER_SOLIDIFICATION"] = (f_ovf < 1.0)
    hv604 = hv_322604(scrub["offgas_kmolh"], scrub["T_offgas"], s.HIC_322604, scrub["P_offgas"])
    # L3-7 HV-322604 off-gas: external steam-tracing holds the 60 C baseline; flag only when extreme JT
    #   cooling overwhelms the jacket (T_out < 20 C).  Flow NOT restricted (gas line) -> fouling warning.
    s.flags["CARBAMATE_DEPOSITION"] = (hv604["T_out"] < 20.0)
    TDY_329125 = scrub["t_ccw_out"] - tic["pv"]   # TT-329125 − TIC-329005 (condensation quality)
    q_e004_kw  = scrub["q_ccw_kw"]                # 329E004 tempered-water-cooler duty (loop closure)

    # ----- Trips (P1-2 stateful interlocks) -----
    # Live initiator conditions (instantaneous). 21_2 = Urea-Synthesis main trip; its initiators
    #   per the trip schedule include loss of NH3 supply head (tank empty here) and the
    #   pressure-vs-saturation margin PDYI321203/204 < 0.1 bar (cavitation guard).  21_8/21_10 =
    #   per-pump mechanical equipment-fault trips (PI 321211/321221 abstraction); armed only while
    #   the pump runs (a stopped pump cannot be faulted into a trip -> would otherwise self-latch).
    s.trips["21_2"]  = (s.tank_level_frac < 0.05) or (PDY_A < 0.1) or (PDY_B < 0.1)
    s.trips["21_8"]  = s.pumpA["on"] and s.pumpA["fault"]
    s.trips["21_10"] = s.pumpB["on"] and s.pumpB["fault"]
    # 21_4 = Loss-of-CO2-feed -> NH3 main interlock (Stamicarbon feed-ratio safeguard): a sustained loss
    #   of CO2 to 322E001 runs the reactor N/C away -> trip the NH3 feed to arrest it (the missing
    #   CO2->NH3 domino link).  Live RESET-BLOCK condition = low CO2 feed alone (cannot reset while CO2
    #   still lost).  The LATCH is ARMED only while synthesis is actually running (>=1 HP-NH3 pump on +
    #   NH3 shut-off XV-322901 open) so an idle / black-start plant valved out of CO2 does NOT self-latch.
    #   CO2 is full at design (XV-322902 open) -> condition False -> design steady state stays bit-exact.
    co2_lost_21_4   = s.F_CO2_th < 0.05 * (CO2_DES_KGH / 1000.0)     # < 5% design CO2 (== L3-3 ratio gate)
    syn_running_214 = disch_open and (s.pumpA["on"] or s.pumpB["on"])
    s.trips["21_4"] = co2_lost_21_4
    if co2_lost_21_4 and syn_running_214:
        s.trip_latched["21_4"] = True
    # Latch on any live condition; the latch holds until trip_reset (operator) clears it.
    for _tk in ("21_2", "21_8", "21_10"):
        if s.trips[_tk]:
            s.trip_latched[_tk] = True
    # Enforce latched actions. 21_2 main trip -> STOP both HP-NH3 pumps, close NH3 quick-closing
    #   XV-321901 + NH3 shut-off XV-322901, drive SIC-321950/951 to min speed (MAN, 0 %).
    if s.trip_latched["21_2"]:
        s.pumpA["on"] = False
        s.pumpB["on"] = False
        s.XV_321901   = False
        s.XV_322901   = False
        s.SIC_321950.set_mode("MAN"); s.SIC_321950.set_op(0.0)
        s.SIC_321951.set_mode("MAN"); s.SIC_321951.set_op(0.0)
    # 21_4 loss-of-CO2 trip -> cut the NH3 feed (mirror the 21_2 NH3 action): STOP both HP-NH3 pumps,
    #   force SIC-321950/951 to MAN 0 (overrides a hand-held MAN pump).  Ejector motive -> 0 via the
    #   TRIPPED PUMPS (motive_nh3 prop. pump flow), so the HPCC/reactor-feed cascade still collapses
    #   without slamming the valve.  XV-322901 is deliberately NOT force-closed here: the operator
    #   keeps manual control of the NH3 shut-off XV while latched (it opens with NO flow until the
    #   pumps are restarted).  The more severe 21_2 main trip still closes XV-322901.
    if s.trip_latched["21_4"]:
        s.pumpA["on"] = False
        s.pumpB["on"] = False
        s.SIC_321950.set_mode("MAN"); s.SIC_321950.set_op(0.0)
        s.SIC_321951.set_mode("MAN"); s.SIC_321951.set_op(0.0)
    if s.trip_latched["21_8"]:
        s.pumpA["on"] = False    # Trip 21.8: stop HP-NH3 pump 321P002A
    if s.trip_latched["21_10"]:
        s.pumpB["on"] = False    # Trip 21.10: stop HP-NH3 pump 321P002B

    # Discharge header
    # Discharge header: affinity-law developed head droops with motive (pump-speed) fraction.
    #   P = P_idle + (P_design - P_idle)·phi_m^2 ;  == 164.0 at design (phi_m=1), 7.5 idle (phi_m=0).
    P_disch_header_barG = (7.5 + ((P_SYN_DOWN_BAR - 1.0) - 7.5) * phi_fwd) \
        if (s.pumpA["on"] or s.pumpB["on"]) else 7.5

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
        # F6: TT-321002 de-aliased — top-right thermowell reads a level-dependent stratification
        #     offset below TT-321001 (empties -> larger vapour-space gradient); tracks both live
        #     tank_T_C and tank_level_frac so boundary disturbances still ripple through.
        "TI_top2":     round(s.tank_T_C - 0.8 * (1.0 - s.tank_level_frac), 1),  # TT-321002 (right)
        "LSL_321501":  (s.tank_level_frac < 0.15),   # low-level switch (active=LO)
        "PI_top1":     round(s.tank_P_top_barG, 1),
        "PI_top2":     round(s.tank_P_top_barG, 1),
        "PI_header":   round(7.3 * phi_fwd, 1),      # F6: PI-321003 feed-header P de-pinned — affinity-law w/ pump motive (phi_fwd^=1 at design -> 7.3)
        "LI_321501":   round(s.tank_level_frac * 100.0, 1),
        "totalizer":   round(s.totalizer_t, 2),
        "XV_321901":   bool(s.XV_321901),
        "XV_322901":   bool(s.XV_322901),
        "PI_321201":   round(PT_A, 1),          # PT-321201 feed pressure (bar g = 321D003)
        "PI_321202":   round(PT_B, 1),          # PT-321202 feed pressure (bar g = 321D003)
        "PI_321201_alarm": bool(s.pumpA["fault"]),  # PI-321211 equipment-fault pre-alarm (lube abstraction)
        "PI_321202_alarm": bool(s.pumpB["fault"]),  # PI-321221 equipment-fault pre-alarm (lube abstraction)
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
            "steam": {                            # shell side: 329D005 MP steam (live MP header)
                "TI_shell": round(strip["T_steam"], 1),      # live sat-steam condensing temp (C)
                "P_bara":   round(s.steam.P_MP, 1),          # live MP header pressure (bar a)
                "kgh":      round(STRIP_STEAM_KGH_DES, 0),   # steam flow (kg/h)
                "duty_kW":  round(STRIP_DUTY_DES_KW, 0),     # heat duty (kW)
            },
        },
        "HPCC_322E002": {                        # HP Carbamate Condenser 322E002 -> 322R001
            "TT_322012":   round(ej["T_C"], 1),          # tube feed 1: ejector-disch liquid temp (C)
            "TT_322013":   round(strip["T_top"], 1),     # tube feed 2: stripper-top gas temp (C)
            "TT_322010":   round(hpcc["T_prod"], 1),     # liquid product -> 322R001 (C)
            "TT_329001":   round(T_shell_lp, 1),         # F6: shell BFW/condensate feed T de-pinned -> live LP-header sat T (==146.3 at design)
            "gas_th":      round(hpcc["gas_th"], 2),     # gas product (t/h)
            "gas_MW":      round(hpcc["gas_MW"], 2),
            "gas_mol_pct": {k: round(hpcc["gas_mol_pct"][k], 3) for k in MW_COMP},   # mol %
            "liq_th":      round(hpcc["liq_th"], 2),     # liquid product (t/h)
            "liq_MW":      round(hpcc["liq_MW"], 2),
            "liq_mass_pct":{k: round(hpcc["liq_mass_pct"][k], 3) for k in MW_COMP},  # mass %
            "LT_322E002":  round(s.hpcc_level_pct, 1),   # liquid level (%) — DYNAMIC inventory (swells on stall)
            "P_bara":      round(hpcc["P_bara"], 1),
            "steam": {                            # shell side: LP steam (live LP header, heat recovery)
                "TI_shell": round(T_shell_lp, 1),            # live LP-header sat condensing temp (C)
                "P_bara":   round(s.steam.P_LP, 1),          # live LP header pressure (bar a)
                "kgh":      round(hpcc["steam_kgh"], 0),     # LP steam produced (kg/h)
                "duty_kW":  round(hpcc["duty_kw"], 0),       # condensation duty (kW)
            },
        },
        "STEAM_SYSTEM": {                        # MP/LP steam headers (lumped-capacitance dynamic)
            "MP": {
                "P_bara":      round(s.steam.P_MP, 2),       # MP header pressure (bar a)
                "TI_sat":      round(tsat_steam(s.steam.P_MP), 1),  # MP sat temp (C)
                "supply_pct":  round(s.steam.valve_supply_pct, 1),  # MP supply valve opening (%)
                "m_supply_th": round(s.steam.m_supply * 3.6, 1),    # supply flow (t/h)
            },
            "LP": {
                "P_bara":      round(s.steam.P_LP, 2),       # LP header pressure (bar a)
                "TI_sat":      round(T_shell_lp, 1),         # LP sat temp (C, offset-pinned)
                "letdown_pct": round(s.steam.valve_letdown_pct, 1), # MP->LP let-down opening (%)
                "m_ld_th":     round(s.steam.m_ld * 3.6, 1),        # let-down flow (t/h)
                "m_water_th":  round(s.steam.m_water * 3.6, 1),     # desuperheat water (t/h)
            },
        },
        "REACT_322R001": {                       # HP Urea Reactor 322R001 -> 322E001 / 322E003
            "TT_322005":   round(s.react_T_node[3], 1),  # N6 A top (EL +21700) — node-4 DYNAMIC profile
            "TT_322006":   round(s.react_T_node[2], 1),  # N6 B     (EL +14800) — node-3 DYNAMIC profile
            "TT_322007":   round(s.react_T_node[1], 1),  # N6 C     (EL  +7900) — node-2 DYNAMIC profile
            "TT_322008":   round(s.react_T_node[0], 1),  # N6 D bot (EL  +1000) — node-1 DYNAMIC profile
            "TT_322009":   round(react["T_offgas"], 1),      # off-gas line -> 322E003 (C, live profile)
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
            "og_lp_th":    round(hv604["mass_kgh"] / 1000.0, 3),  # HV-322604 vented off-gas mass flow (t/h, live)
            "vent_frac":   round(scrub["vent_frac"], 4),     # HV-322604 vent capacity / required purge (<1 -> PT rises)
            "P_offgas":    round(scrub["P_offgas"], 1),      # off-gas line P (bar a)
            "P_overflow":  round(scrub["P_overflow"], 1),    # PT-329201 overflow line P (bar a)
            "TT_322002":   round(scrub["T_overflow"], 1),    # overflow temp -> 322F001 (C)
            # F6: LT-329501 de-pinned — seal-leg level rises with overflow throughput (co2_scale) and
            #     downstream synthesis backpressure (nu); ==50% design NLL at s=1, nu=1 (bit-exact).
            "LT_329501":   round(clamp(50.0 + 40.0 * (react["co2_scale"] - 1.0)
                                       + 25.0 * (nu - 1.0), 0.0, 100.0), 1),  # overflow seal-leg level (%)
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
        "sim_mode": s.sim_mode,                           # "SLOW" (real-time) | "FAST" (accelerated)
        "sim_speed": SIM_SPEED.get(s.sim_mode, 1.0),      # sim-s advanced per real-s in the active mode
        "trips": s.trips,
        "trip_latched": s.trip_latched,
        "controllers": {tag: ctrl.to_packet()
                        for tag, ctrl in s.controllers.items()},
    }


# ----- Commands from UI -----
def handle_cmd(cmd: dict):
    s = state
    t = cmd.get("type")

    if t == "pump_toggle":
        pid = cmd["id"]
        p   = s.pumpA if pid == "A" else s.pumpB
        latch_key = "21_8" if pid == "A" else "21_10"
        # P1-2: restart of a tripped pump.  Turning a pump OFF is always allowed; only the OFF->ON
        #   restart is gated by a latched trip (21_2 main latches BOTH pumps; per-pump 21_8/21_10
        #   latches its own pump).  The UI exposes NO separate trip_reset control, so the OFF->ON
        #   click itself AUTO-ACKNOWLEDGES any latched trip whose LIVE cause has already recovered
        #   and clears this pump's mechanical fault -- "restart == reset, mechanical obstacle ignored"
        #   per spec.  A latch whose cause is STILL live (tank empty, CO2 lost) stays set and keeps
        #   the restart blocked.  (21_8/21_10 live-cond = pump_on AND fault; the pump is OFF here so
        #   the live cond is False -> the latch clears and the lube-oil fault is resolved on restart.)
        if not p["on"]:
            for k in ("21_2", "21_4", latch_key):
                if s.trip_latched.get(k) and not s.trips.get(k, False):
                    s.trip_latched[k] = False
                    if k == "21_8":
                        s.pumpA["fault"] = False
                    elif k == "21_10":
                        s.pumpB["fault"] = False
        if (not p["on"]) and (s.trip_latched["21_2"] or s.trip_latched["21_4"] or s.trip_latched[latch_key]):
            pass   # restart still blocked: a blocking interlock cause is unresolved
        else:
            p["on"] = not p["on"]

    elif t == "trip_reset":
        # Operator clear: only succeeds for trips whose LIVE condition has already recovered
        #   (a latch over a still-active condition cannot be cleared).  id = "21_2"|"21_8"|"21_10"
        #   or "ALL"/None for every trip.
        key  = cmd.get("id")
        keys = ("21_2", "21_4", "21_8", "21_10") if key in (None, "ALL") else (key,)
        for k in keys:
            if k in s.trip_latched and not s.trips.get(k, False):
                s.trip_latched[k] = False
                # Resolve the mechanical trip cause on reset so the pump is restartable.
                #   21_8/21_10 are armed by the instructor lube-oil fault (pump["fault"]),
                #   which persists past the latch clear and would re-trip the pump on the next
                #   tick after restart.  Clearing it here makes "reset" == cause resolved, so the
                #   pump can be restarted and stays running (mechanical obstacle ignored).
                if k == "21_8":
                    s.pumpA["fault"] = False
                elif k == "21_10":
                    s.pumpB["fault"] = False

    elif t == "xv_toggle":
        if cmd["id"] == "321901":
            s.XV_321901 = not s.XV_321901
        elif cmd["id"] == "322901":
            s.XV_322901 = not s.XV_322901
        elif cmd["id"] == "322902":
            s.XV_322902 = not s.XV_322902

    elif t == "ext_override":
        s.ext_override = bool(cmd["value"])

    elif t == "set_sim_mode":
        # {"type":"set_sim_mode","mode":"FAST"|"SLOW"}  -- toggles time-acceleration; unknown -> ignored
        m = str(cmd.get("mode", "")).upper()
        if m in SIM_SPEED:
            s.sim_mode = m

    elif t == "controller_set":
        cid  = cmd["id"]
        ctrl = getattr(s, cid, None)
        if ctrl is None:
            return
        if "mode" in cmd:
            ctrl.set_mode(cmd["mode"])
            if cmd["mode"] == "CAS":
                # ui_guidelines rule 6: master (ratio) -> AUTO, adopt current value as SP
                s.ratio_mode = "AUTO"
                s.ratio_SP   = round(s.ratio_PV, 3)
        if "op" in cmd and ctrl.mode == "MAN":
            ctrl.set_op(_finite(cmd["op"], "op"))
        if "sp_rpm" in cmd and ctrl.mode == "AUTO":     # AUTO setpoint entered as RPM
            ctrl.set_sp(_finite(cmd["sp_rpm"], "sp_rpm") / PUMP_RATED_RPM * 100.0)
        elif "sp" in cmd and ctrl.mode == "AUTO":
            ctrl.set_sp(_finite(cmd["sp"], "sp"))
        if "nc" in cmd and ctrl.mode == "CAS":
            ctrl.set_bias(_finite(cmd["nc"], "nc"))

    elif t == "ratio_set":
        if "sp" in cmd:
            s.ratio_SP = clamp(_finite(cmd["sp"], "ratio_SP"), 2.0, 5.0)

    elif t == "co2_set":                       # raw CO2 from 320K002 compressor (t/h)
        s.F_CO2_raw_th = max(0.0, _finite(cmd["value"], "co2"))

    elif t == "hic_set":                       # HIC-322602 -> HV-322602 ejector opening
        s.HIC_322602 = clamp(_finite(cmd["value"], "value"), 0.0, 100.0)

    elif t == "hic2_set":                      # HIC-322203 -> PV-322203 minimum opening
        s.HIC_322203 = clamp(_finite(cmd["value"], "value"), 0.0, 100.0)

    elif t == "hic605_set":                    # HIC-322605 -> HV-322605 reactor overflow valve
        if "op" in cmd:
            s.HIC_322605 = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "pic_set":                       # PIC-322203 CO2 line-pressure controller
        pic = s.PIC_322203
        if "mode" in cmd:
            if cmd["mode"] == "AUTO" and pic["mode"] != "AUTO":   # F1: bumpless SP<-PV on AUTO entry
                pic["sp"] = clamp(pic["pv"], 120.0, 175.0)
            pic["mode"] = cmd["mode"]
        if "op" in cmd and pic["mode"] == "MAN":
            pic["op"] = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)
        if "sp" in cmd:
            pic["sp"] = clamp(_finite(cmd["sp"], "pic_sp"), 120.0, 175.0)

    elif t == "lic_set":                       # LIC-322501 bottom-solution level controller
        lic = s.LIC_322501
        if "mode" in cmd:
            if cmd["mode"] == "AUTO" and lic["mode"] != "AUTO":   # F1: bumpless SP<-PV on AUTO entry
                lic["sp"] = clamp(lic["pv"], 0.0, 100.0)
            lic["mode"] = cmd["mode"]
        if "op" in cmd and lic["mode"] == "MAN":   # MAN: operator sets LV-322501 opening (%)
            lic["op"] = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)
        if "sp" in cmd:                            # level setpoint (%)
            lic["sp"] = clamp(_finite(cmd["sp"], "lic_sp"), 0.0, 100.0)

    elif t == "hic604_set":                    # HIC-322604 -> HV-322604 scrubber off-gas valve
        if "op" in cmd:
            s.HIC_322604 = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "steam_supply_set":              # MP supply valve (utility import -> MP header)
        if "op" in cmd:
            s.steam.valve_supply_pct = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "steam_letdown_set":             # MP->LP let-down valve (with desuperheater)
        if "op" in cmd:
            s.steam.valve_letdown_pct = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "trigger_fault" or (t == "set" and str(cmd.get("id", "")).lower().endswith("_fault")):
        # Instructor mechanical equipment-fault toggle (lube-oil abstraction).  Sets pump["fault"] to
        #   arm/clear the per-pump trip 21_8 (pump A) / 21_10 (pump B) without simulating lube-oil
        #   pressure.  Accepts the dedicated {"type":"trigger_fault","id":"A"|"B","value":bool} command
        #   or the generic UI form {"type":"set","id":"pumpA_fault"|"pumpB_fault","value":bool}.
        key = str(cmd.get("id", "")).upper().replace("PUMP", "").replace("_FAULT", "")  # -> "A"/"B"
        p   = s.pumpA if key == "A" else (s.pumpB if key == "B" else None)
        if p is not None:
            p["fault"] = bool(cmd.get("value", True))

    elif t == "fic_set":                       # FIC-329409 CCW circulation-flow controller -> FV-329409
        fic = s.FIC_329409
        if "mode" in cmd:
            if cmd["mode"] == "AUTO" and fic["mode"] != "AUTO":   # F1: bumpless SP<-PV on AUTO entry
                fic["sp"] = clamp(fic["pv"], 0.0, 2.0 * SCRUB_CCW_KGH_DES / 1000.0)
            fic["mode"] = cmd["mode"]
        if "op" in cmd and fic["mode"] == "MAN":   # MAN: operator sets FV-329409 opening (%)
            fic["op"] = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)
        if "sp" in cmd:                            # CCW flow setpoint (t/h)
            fic["sp"] = clamp(_finite(cmd["sp"], "fic_sp"), 0.0, 2.0 * SCRUB_CCW_KGH_DES / 1000.0)

    elif t == "tic_set":                       # TIC-329005 CCW supply-temp controller -> TV-329005
        tic = s.TIC_329005
        if "mode" in cmd:
            if cmd["mode"] == "AUTO" and tic["mode"] != "AUTO":   # F1: bumpless SP<-PV on AUTO entry
                tic["sp"] = clamp(tic["pv"], 20.0, SCRUB_CCW_T_OUT_DES)
            tic["mode"] = cmd["mode"]
        if "op" in cmd and tic["mode"] == "MAN":   # MAN: operator sets TV-329005 opening (%)
            tic["op"] = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)
        if "sp" in cmd:                            # CCW supply-temp setpoint (C)
            tic["sp"] = clamp(_finite(cmd["sp"], "tic_sp"), 20.0, SCRUB_CCW_T_OUT_DES)


# ----- FastAPI app -----
app = FastAPI()


# ----- Controller REST API -----

class _TuningPayload(BaseModel):
    # P1-1: reject NaN/Inf + enforce PID physical constraints (Kc>0, Ti>=1e-9, Td>=0)
    Kc: Optional[float] = Field(default=None, gt=0.0,   allow_inf_nan=False)
    Ti: Optional[float] = Field(default=None, ge=1e-9,  allow_inf_nan=False)
    Td: Optional[float] = Field(default=None, ge=0.0,   allow_inf_nan=False)


class CtrlCommand(BaseModel):
    # P1-1: every float field rejects NaN/Inf at the REST boundary (set_bias additionally
    #   clamped to +/-CAS_BIAS_LIM in Controller.set_bias against saturation exploits).
    set_mode:   Optional[str]            = None
    set_sp:     Optional[float]          = Field(default=None, allow_inf_nan=False)
    set_op:     Optional[float]          = Field(default=None, allow_inf_nan=False)
    set_bias:   Optional[float]          = Field(default=None, allow_inf_nan=False)
    set_tuning: Optional[_TuningPayload] = None


@app.post("/api/ctrl/{tag}")
async def ctrl_post(tag: str, cmd: CtrlCommand):
    """Apply operator command to a named controller. 409 if mode-illegal."""
    with _ctrl_lock:
        ctrl = state.controllers.get(tag)
        if ctrl is None:
            raise HTTPException(status_code=404, detail=f"unknown tag {tag!r}")

        reason = None

        if cmd.set_mode is not None:
            if cmd.set_mode not in ("MAN", "AUTO", "CAS", "OOS"):
                raise HTTPException(status_code=422,
                                    detail=f"invalid mode {cmd.set_mode!r}")
            ctrl.set_mode(cmd.set_mode)

        if cmd.set_sp is not None:
            if ctrl.mode != "AUTO":
                raise HTTPException(status_code=409,
                                    detail="set_sp requires AUTO mode")
            ctrl.set_sp(cmd.set_sp)
            reason = "clamped" if (ctrl.sp != cmd.set_sp) else None

        if cmd.set_op is not None:
            if ctrl.mode != "MAN":
                raise HTTPException(status_code=409,
                                    detail="set_op requires MAN mode")
            ctrl.set_op(cmd.set_op)

        if cmd.set_bias is not None:
            if ctrl.mode != "CAS":
                raise HTTPException(status_code=409,
                                    detail="set_bias requires CAS mode")
            ctrl.set_bias(cmd.set_bias)

        if cmd.set_tuning is not None:
            ctrl.set_tuning(
                Kc=cmd.set_tuning.Kc,
                Ti=cmd.set_tuning.Ti,
                Td=cmd.set_tuning.Td,
            )

        return {"ok": True, "tag": tag, "mode": ctrl.mode, "reason": reason}


@app.get("/api/ctrl")
async def ctrl_get_all():
    """Return to_packet() for every registered controller."""
    with _ctrl_lock:
        return {tag: ctrl.to_packet()
                for tag, ctrl in state.controllers.items()}


@app.get("/api/ctrl/{tag}")
async def ctrl_get(tag: str):
    """Return to_packet() for a single controller."""
    with _ctrl_lock:
        ctrl = state.controllers.get(tag)
        if ctrl is None:
            raise HTTPException(status_code=404, detail=f"unknown tag {tag!r}")
        return ctrl.to_packet()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            msg = await ws.receive_text()
            try:
                handle_cmd(_loads_cmd(msg))
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
        # Total sim-time to advance this real tick = wall-clock elapsed * mode speed factor.
        #   SLOW (x1) -> advance == dt -> single STEP_CAP-bounded step (identical to legacy real-time).
        #   FAST (xN) -> advance == dt*N, integrated in fixed STEP_CAP sub-steps so each physical
        #   step is bit-identical to SLOW; only the number of steps per real second changes.
        sim_advance = dt * SIM_SPEED.get(state.sim_mode, 1.0)
        while sim_advance > 1e-9:
            h = min(STEP_CAP, sim_advance)
            last_packet = step_sim(h)
            sim_advance -= h
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


def _pin_hpcc_ua():
    """Design-pin HPCC_UA on the SETTLED live design steady state (not the synthetic single-call
    _HPCC_DES, which understates tube throughput ~2 %).  With HPCC_UA is None, hpcc_322e002 holds
    T_prod == 170.0 C every tick, so the mass loop settles to the SAME m_dot/T_adb the NTU run would
    converge to (T_prod does NOT feed back into any mass: reactor uses fixed REACT_OVERFLOW_T_C, and
    the ejector/stripper masses are T_prod-independent).  We capture that settled (m_dot, T_adb),
    back-calc UA from the design NTU pin, then discard the warm-up transient by re-seeding state.

        UA = -m_dot*cp * ln[(T_prod_des - T_sat) / (T_adb - T_sat)]

    This anchors TT-322010 to exactly 170.0 C at 100 % live design steady state."""
    global HPCC_UA, state, last_packet, hpcc_322e002, _STEAM_READY
    state.SIC_321951.set_mode("CAS")                 # match the live design driver (ratio cascade)
    _orig = hpcc_322e002
    _cap = {}
    def _cap_hpcc(gas_feed, liq_feed, **kw):
        r = _orig(gas_feed, liq_feed, **kw)
        _cap["r"] = r
        return r
    hpcc_322e002 = _cap_hpcc
    for _ in range(18000):                           # 30 sim-min @ dt=0.1 s -> settled design steady state
        step_sim(0.1)
    hpcc_322e002 = _orig
    r = _cap["r"]
    # L3-4 boot-pin domain assert: the UA back-calc log requires 0 < (T_prod_des - T_sat)/(T_adb - T_sat)
    #   < 1, i.e. T_adb > T_prod_des > T_sat_shell.  A failed warm-up settle (bad steam/feed) would feed
    #   a non-positive or >1 argument -> ValueError/NaN at import.  Fail loud here instead of hiding it.
    assert r["T_adb"] > HPCC_T_PROD_DES_C > HPCC_STEAM_TSAT_C, "HPCC UA back-calc domain error"
    HPCC_UA = -r["m_dot"] * HPCC_CP_GAS * math.log(
        (HPCC_T_PROD_DES_C - HPCC_STEAM_TSAT_C) / (r["T_adb"] - HPCC_STEAM_TSAT_C))
    state = State()                                  # discard the warm-up transient (fresh design seed)

    # ---- pin the steam-header valve coeffs so the runtime design seed is a STATIONARY fixed point.
    #   The steam shell T feeds BACK into the process (stripper eta_T_steam = f(tsat(P_MP))), so the
    #   headers must hold EXACTLY at the seed (19.7 / 4.4) or design bit-exactness is lost downstream.
    #   That requires net header flow == 0 at the seed, using the design HPCC duty AS SEEN AT THE
    #   RUNTIME (MAN) STATE WITH STEAM FROZEN -- not the CAS warm-up r above.  So: re-seed, settle a
    #   second time with step_steam still gated OFF (_STEAM_READY=False), capture the frozen-steam
    #   design duty, then size the valves:
    #     MP:  supply(50%) = m_strip + m_ld          -> K_SUPPLY
    #     LP:  M_USERS_LP  = m_hpcc + m_ld + m_water  (sink balances the three sources)
    import steam_system as _ss
    _orig2 = hpcc_322e002
    _cap2 = {}
    def _cap_hpcc2(gas_feed, liq_feed, **kw):
        rr = _orig2(gas_feed, liq_feed, **kw)
        _cap2["r"] = rr
        return rr
    hpcc_322e002 = _cap_hpcc2
    for _ in range(3000):                            # 5 sim-min: STOP on the stable MAN design plateau,
        step_sim(0.1)                                #   BEFORE the NH3-inventory main trip (21_2 latches
    hpcc_322e002 = _orig2                            #   ~tick 6500 in free-running MAN -> post-trip duty
    _duty_des    = _cap2["r"]["duty_kw"]             #   is garbage). Plateau duty is flat ticks 3000-6000.
    _m_strip_des = STRIP_DUTY_DES_KW / 1850.0
    _m_hpcc_des  = _duty_des / HPCC_LATENT_4BAR
    _m_ld_des    = _ss.K_LETDOWN * 0.5 * (STRIP_STEAM_P_BARA - HPCC_STEAM_P_BARA) ** 0.5
    _m_water_des = _m_ld_des * (_ss.H_MP - _ss.H_LP) / (_ss.H_LP - _ss.H_W)
    _ss.K_SUPPLY   = (_m_strip_des + _m_ld_des) / (0.5 * (_ss.P_EXT_MP_BARA - STRIP_STEAM_P_BARA) ** 0.5)
    _ss.M_USERS_LP = _m_hpcc_des + _m_ld_des + _m_water_des
    _STEAM_READY = True                              # arm step_steam for live operation
    state = State()                                  # discard the second transient (fresh design seed)
    last_packet = {}


if HPCC_UA is None:
    _pin_hpcc_ua()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
