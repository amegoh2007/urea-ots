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
import hashlib
import math
import os
import time
import threading
from collections import deque
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


def psat_water_bara(T_C: float) -> float:
    """Saturated-water vapour pressure [bar a] from temperature [deg C].

    Forward form of the tsat_steam Antoine correlation (same coefficients):
        log10(P_mmHg) = 8.14019 - 1810.94 / (244.485 + T_C),  P_bara = P_mmHg / 750.0617.
    """
    p_mmhg = 10.0 ** (8.14019 - 1810.94 / (244.485 + T_C))
    return p_mmhg / 750.0616827


# ----- Modelling scope boundary (§7.7 P6-B) -----
# The following 6 P&ID tags are intentionally NOT modelled: they are out-of-envelope
# auxiliaries with no mass/energy coupling to any modelled unit (no stream on the PFD/HMB
# crosses the sim boundary through them), so their omission cannot perturb conservation or
# the design fingerprint. Listed here as an explicit scope declaration, not a TODO:
#   323D003  - unit 323-2 auxiliary drum   (off-envelope, no HMB stream)
#   329E002  - unit 329 auxiliary exchanger (off-envelope, no HMB stream)
#   329E004  - unit 329 auxiliary exchanger (off-envelope, no HMB stream)
#   329P004  - unit 329 auxiliary pump      (off-envelope, no HMB stream)
#   329U001  - unit 329 auxiliary package   (off-envelope, no HMB stream)
#   335D007  - unit 335 auxiliary drum      (off-envelope, no HMB stream)
# Any future coupling of these tags MUST re-source from PFD/HMB before adding state.

# ----- Constants -----
NH3_RHO         = 604.8          # kg/m^3, design (eff. density NH3 feed @ 25 C). NIST-validated 2026-07-03: sat. liquid 602.96 @ 25 C; compressed liquid 604.8 corresponds to 25 C / ~29 bar a (pump suction) -> constant is the compressed-liquid density at design suction condition, not an error.
G               = 9.81
PUMP_D          = 0.140          # m
PUMP_L          = 0.205          # m
PUMP_N_PLGR     = 3
PUMP_ETA_V      = 0.980         # field-calibrated: DCS 3.6.2025 startup, T-separated fit 0.980+/-0.001 (n=5, flat across 100-142 bar g -> design value, not low-slip artifact). Was 0.95 (assumed, +3.2% under). Conservation-neutral: eta_v cancels in the closed-loop ratio reconstruction (rpm back-computed then mass rebuilt), only SIC-321950 rpm display shifts. CAVEAT (2026-07-03): FY-321401 shown to be a fixed-constant DCS compute tag (28-06 warm-feed slope -0.07% vs -2.1% predicted for live-rho; ISA-5.1 letter Y), so the fit constrains only the product eta_v*rho_cfg = 601.6 kg/m3; 0.980 assumes rho_cfg = rho_sat(17.6 C) = 613.9 kg/m3. Degenerate with the DCS density constant but conservation-neutral either way.
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
           "N2":28.0134,"NH3":17.0304,"O2":31.9988,"Urea":60.0554,"Biuret":103.0804}
# Urea   MW = C+2N+4H+O   -> urea-couple   (CO2+2NH3->Urea+H2O) Sum(nu*MW) = 0 exactly
# Biuret MW = 2*Urea-NH3  -> biuret-couple (2Urea->Biuret+NH3)  Sum(nu*MW) = 0 exactly
# both atom-consistent w.r.t. the listed CO2/NH3/H2O MW -> reactor mass closes to machine zero.
EJ_MOTIVE_NH3_DES = 42762.05427809782   # kg/h, design motive NH3 (pure, 321P002 A/B BL feed)
#   RE-PINNED to physical Cluster-2023 design point: motive = RATIO_PV_DES*NC_TO_MASS*CO2_DES_KGH.
#   Prior 40756.0 implied fresh N/C = 1.928 < 2.0 (sub-stoichiometric -> proven non-steady free-run);
#   re-pin restores ejector phi_m == 1 at the published operating point (W_inst == W0, L_feed == L0).
# -- SUPERSEDED datasheet provenance (Carb.Liq. HMB table; FALSIFIED by Path-B tear-closure audit) --
#   The 98320 kg/h nameplate + mass-pct table do NOT atom-close against the reconciled stripper-top /
#   reactor-offgas vectors (rank-1 free DOF ov_CO2 forced the discharge off the datasheet).  Retained
#   ONLY as provenance (Sourcing Law) + to keep the audit imports resolvable; NOT fed to live streams.
EJ_DES_TOTAL_NAMEPLATE = 98320.0   # kg/h, OLD datasheet discharge total (Carb. Liq.) -- superseded
EJ_DES_MASSPCT    = {"CO2":23.24,"CH4":0.06,"H2":4.17e-3,"H2O":12.39,
                     "N2":0.02,"NH3":64.27,"O2":0.0,"Urea":0.02,"Biuret":0.0}   # superseded datasheet mass%
_EJ_DES_MASS   = {k: EJ_DES_MASSPCT[k]/100.0*EJ_DES_TOTAL_NAMEPLATE for k in MW_COMP}  # superseded reconstruction
# -- RECONCILED design suction (Path B, Option 1: free DOF ov_CO2 = 458.358305 kmol/h, the feasible-band MAX
#   -> vent_H2O=0, max heavy recovery).  Overflow (kmol/h) is the source of truth; EJ_SUCTION = overflow*MW.
#   Verified atom-/mass-closing: scrubber GAP=0, W_inst=W0_DES, L_inst=L0_DES, reactor-node dM/dt sump=0. --
_EJ_OVERFLOW_KMOLH = {"CO2": 458.35830512, "CH4": 0.0, "H2": 0.0, "H2O": 674.24844864,
                      "N2": 0.0, "NH3": 1234.46697667, "O2": 0.0, "Urea": 0.43027771, "Biuret": 0.0}
EJ_SUCTION_KGH = {k: _EJ_OVERFLOW_KMOLH[k] * MW_COMP[k] for k in MW_COMP}   # kg/h reconciled design suction
#   NOTE: the former "~94124" annotation here was stale -- it was arithmetic off the OLD 40756 kg/h
#   motive and is superseded by the Path-B tear-closure reconciliation (motive re-pinned to 42762.05).
EJ_DES_TOTAL   = EJ_MOTIVE_NH3_DES + sum(EJ_SUCTION_KGH.values())           # kg/h reconciled discharge (~96130)
EJ_MU          = sum(EJ_SUCTION_KGH.values()) / EJ_MOTIVE_NH3_DES   # entrainment ~1.3095 (reconciled)
EJ_OPEN_DES    = 74.0            # %, HV-322602 design opening (HIC-322602 design SP)
# HV-322602 spindle characteristic (322F001 DDS, item (d)): the diaphragm-actuated parabolic NH3-nozzle
# needle is a CONVERGING motive throat.  Motive NH3 comes from the 321P002 A/B POSITIVE-DISPLACEMENT
# (triplex) pumps -> motive MASS flow is CONSTANT (set by pump speed, NOT by valve opening).  At constant
# m_dot the jet velocity v=m_dot/(rho*A) and the momentum flux m_dot*v=m_dot^2/(rho*A) vary INVERSELY with
# nozzle free area A, so CLOSING the spindle (smaller A) RAISES jet momentum -> RAISES entrainment/suction
# capacity (NEGATIVE law).  Datasheet (Remarks 3-5): free area variable 40-100 %, linear instrument map
# a(theta)=40+0.6*theta; the DDS free-area turndown anchors a suction-capacity rangeability R=2.1517 over
# the band.  Equal-% factor phi_sp(theta)=R^((EJ_OPEN_DES-theta)/100), phi_sp(74)=R^0=1 (design bit-exact).
# (Restores the INVERSE direction: for a constant-m_dot PD-pump-fed jet, motive MOMENTUM -- not free area --
# sets capacity; the prior POSITIVE law implicitly assumed constant motive PRESSURE, which is wrong here.)
EJ_SPINDLE_R   = 2.1517          # effective equal-% rangeability of ejector suction capacity vs HV-322602
EJ_STALL_PHI   = 0.20            # phi_m DEEP-stall KNEE: f_stall==0 at/below this motive fraction (jet
                                 #   momentum cannot overcome discharge backpressure -> capacity collapses).
                                 #   Set LOW: this is a genuine motive FAULT, not normal turndown.  Healthy
                                 #   proportional turndown does NOT false-stall because capacity AND scrubber
                                 #   overflow both scale with motive -> sump self-regulates at NLL (see below).
EJ_STALL_REC   = 0.35            # phi_m RECOVERY fraction: f_stall saturates at 1.0 at/above this.  For any
                                 #   phi_m >= EJ_STALL_REC the entrainment RATIO mu is ~constant (jet-ejector
                                 #   physics); below it the capacity collapses sharply (deep motive loss /
                                 #   N/C-ratio break with load held -> ejector STALLS -> 322E003 sump floods).
EJ_STALL_EXP   = 2.0             # convexity of the f_stall collapse inside the deep-stall band [PHI, REC]:
                                 #   f_stall = clamp((phi_m-PHI)/(REC-PHI),0,1)^EXP.  EXP=2 -> sharp
                                 #   quadratic knee: f(0.25)=0.11, f(0.30)=0.44, f(0.35)=1.  NOT a linear
                                 #   phi_m cheat and NOT a curve that only reaches 1 at phi_m=1.
EJ_HYD_FRAC_MAX = 1.25           # —, HYDRAULIC-CAPACITY (throat-choke) ceiling on the suction-head
#   multiplier frac = L_329501/NLL.  A real jet ejector chokes: above a finite suction head the throat
#   reaches max mass capacity and entrainment STOPS rising with head.  m_suc = capacity·min(frac, this).
#   >1 -> design (frac=1 at NLL) is below the ceiling -> NEVER engages at design -> every pin bit-exact.
#   25 % head-overcapacity above NLL = typical HP jet-ejector hydraulic margin.  On a 322E003 flood the
#   raw frac wants 2.0 (L=100%/NLL=50%); the ceiling caps entrainment at 1.25·capacity, so the un-pumpable
#   overflow excess backs up the sump (already at SCRUB_HOLDUP_MAX clamp) INSTEAD of recirculating the
#   flood into the discharge -> 322E002 -> reactor loop -> the reactor conversion self-loop re-bounds.
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
#   Dynamic (pressure-gated split of the raw BL CO2 at the feed tee; bugs 1+4 are ONE
#   defect -- the feed never respected the CO2-line vs synthesis dP):
#     320K002 is flow(load)-controlled, so its discharge FLOATS to hold the design feed dP
#     against synthesis backpressure -- there is ALWAYS a dP between the line and the loop --
#     up to a deliverable ceiling:
#       P_line = min(P_syn + DP_HP_DES, P_line_ceil) - CO2_PV_DP_GAIN*PV_open
#       DP_HP_DES = CO2_P_DES - SYN_P_DES = 3.5 bar ;  P_line_ceil = SYN_P_MAX + DP_HP_DES
#       (ceiling derived from existing constants: the compressor must still feed at the max
#        synthesis pressure + the feed dP -- NO fabricated head).
#     The CO2 then splits between two parallel downstream paths by a conductance*sqrt(dP):
#       (HP)   into 322E001/synthesis loop, dP_HP = max(P_line - P_syn, 0)  -- check valve;
#       (vent) out PV-322203 to the LP safe header, dP_vent = max(P_line - P_vent, 0),
#              gated by PV_open = max(HIC-322203 min, PIC-322203 op).
#     phi_HP = min(1, sqrt(dP_HP/DP_HP_DES))   -- compressor/check-valve DELIVERY (bug 1)
#     g_HP = sqrt(dP_HP);  g_vent = (PV_open/100)*CO2_VENT_COND*sqrt(dP_vent)
#     f_toHP = g_HP/(g_HP+g_vent)               -- vent-diversion SPLIT (bug 4)
#     F_feed = F_raw*feed_factor*phi_HP*f_toHP;  F_vent = F_raw*feed_factor*(1-phi_HP*f_toHP).
#     Across the normal band (P_syn 140.7..144.2, PV shut) the float holds dP_HP~3.5 ->
#     phi_HP=1 -> feed stays at load (small synthesis excursions do NOT throttle the feed;
#     correct plant behaviour).  Opening PV-322203 >= ~14 % sags the line below P_syn ->
#     dP_HP=0 -> ALL CO2 vents (bug 4).  P_syn at/above the ceiling shrinks dP_HP -> phi_HP
#     falls -> check valve shuts (bug 1 extreme).
#     At design (PV_open=0, P_syn=140.7): P_line=144.2, phi_HP=1, g_vent=0 -> F_feed=F_raw (bit-exact).
#     s.F_CO2_th = F_feed drives the N/C ratio block + every downstream CO2 stream.
CO2_FEED_MOLFRAC  = {"CO2": 0.9524, "H2O": 0.0061, "N2": 0.0355, "O2": 0.0060}
CO2_FEED_MW       = sum(CO2_FEED_MOLFRAC[k] * MW_COMP[k] for k in CO2_FEED_MOLFRAC)  # = 43.21
CO2_DES_KGH       = 54618.0      # kg/h design total CO2-feed mass (54.618 t/h = 100 % Load)
CO2_DES_KMOLH     = 1264.0       # kmol/h design total molar flow
CO2_T_FEED_C      = 120.0        # C, TI-322017 feed temperature (design)
CO2_P_DES_BARA    = 144.2        # bar a, design CO2 feed-line pressure (PIC-322203 PV)
CO2_RHO           = 242.70       # kg/m3, eff. density @ 120 C, 144.2 bar a
NM3_PER_KMOL      = 22.414       # Nm3/kmol at 0 C, 1 atm (FT-322403 normal-volume basis)
CO2_VENT_COND     = 0.50         # PV-322203 vent conductance (sqrt-dP orifice coeff, rel. HP path)
CO2_VENT_P_BARA   = 5.0          # bar a, PV-322203 discharge backpressure (LP safe header)
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
STRIP_T_TOP_LOAD_K   = 0.5      # overhead (TT-322013) attenuation of the bottom feed-load thermal swing
                                #   (dT_bot is a liquid/reboiler effect; the top gas feels it only weakly).
                                #   The G/L strip-cool endotherm (dT_strip) couples to the OVERHEAD at full
                                #   weight — the rising vapour is first to carry the CO2-sweep flash latent load.
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
#   FIELD CALIBRATION (DCS 28-06-2025 startup anchors, reports/dcs_anchor_dynamics_2025-06-28.md):
#   at 97 % urea load LV-322501 held 45.4 % (stable 42-45.4 % over final 3 h); dP-corrected to
#   design (sqrt((P_syn-4)/(140.7-4)) = 0.9853) and load-corrected (/0.97) -> 46.1 % opening at
#   design flow (cross-checks 46.4 / 44.2 % at 14:01/15:01).  Datasheet-predicted 82 % stroke
#   over-states required travel ~1.8x for the installed flashing service; DCS reality governs.
#   Pin-safe: constant enters only as boot seed (op = OPEN_DES) and ratio normalizer
#   (op/OPEN_DES), so the design steady state is bit-identical.
LV322501_OPEN_DES   = 46.1        # %, opening at the design bottom-solution flow (field-calibrated)
STRIP_SUMP_DT_LOSS_DES_C = 4.0    # C, design-throughput sump heat-loss ΔT (falling-film tube exit -> LV-322501 drain)
STRIP_BOT_T_CRYST_C      = 132.7  # C, urea-melt crystallization floor = sump heat-loss sink T (low-throughput asymptote)
STRIP_SUMP_NTU_DES       = STRIP_SUMP_DT_LOSS_DES_C / (STRIP_T_BOTTOM_DES_C - STRIP_BOT_T_CRYST_C)  # τ_des = UA/(ṁ_des·cp), design sump heat-loss NTU ≈ 0.1018
LV322501_DP_DES_BAR = 139.8       # bar, design pressure drop (144.0 - 4.2)
STRIP_P_DOWN_BARA   = 4.2         # bar a, downstream of LV-322501 (-> 323C003)
LV322501_P_DOWN_BARA = 4.0        # bar a, L3-1 LP-loop downstream ref for live-P_syn drain head

# ==========================================================================
#  UNIT 323 - LP RECIRCULATION & PRE-EVAPORATION (Screen 323-1)
#  Design steady-state anchors (Combined 1750 MTPD 100%-load PFD/MB tables).
#  Compositions are MASS %. Feed = 322E001 letdown bottoms (live drain_kgh,
#  TT_323001). Conservation is enforced exactly on the live feed every tick;
#  the numbers below only seed dm/dt = dT/dt = 0 at the design fixed point.
# ==========================================================================
R323_CP_SOLN     = 2.5            # kJ/kg.K, lumped urea-solution specific heat
R323_P_STEAM_SUP = 4.4            # bar a, LP steam header feeding 323E002/323E010

# --- Stage 1: Rectifying Column 323C003 + Recirc Heater 323E002 (4.1 bar a, hold 135 C)
R323_FEED_DES_KGH   = STRIP_BOT_DES_KGH        # 130482 kg/h, live = drain_kgh
R323_FEED_DES_T_C   = STRIP_T_DOWN_DES_C       # 119 C, live = TT_323001
R323_C003_P_BARA    = 4.1                       # bar a, rectifier operating pressure
R323_C003_T_SP_C    = 135.0                     # C, bottom-liquid boundary (stream 314)
R323_C003_T313_C    = 121.0                     # C, column-bottom sump liquid (PFD-20 stream 313, TT-323002)
R323_PHI_V305       = 24582.0 / 130582.0        # 0.188249 vapor split -> LPCC (stream 305)
R323_305_T_C        = 119.0                     # C, top vapor to 323E003 LPCC
R323_E002_Q_DES_KW  = 5858.0                    # kW, design heater duty (PDS: Q=5858, A=535)
R323_E002_OP_DES    = 90.0                      # %, PV-329202 design stroke
R323_E002_PCHEST_DES = R323_E002_OP_DES / 100.0 * R323_P_STEAM_SUP   # 3.96 bar a
R323_C003_M_TAU_S   = 120.0                     # s, liquid residence -> holdup sizing
R323_C003_LVL_SP    = 60.0                      # %, LIC-323501 level setpoint
R323_C003_RHO       = 1250.0                    # kg/m3, ~135 C bottom liquor
R323_LV501_OP_DES   = 50.0                      # %, LV-323501 design stroke
# Dynamic column pressure PT-323201 (hydraulic coupling to LV-322501 via top-vapour flow 305).
#   First-order relaxation of P_C003 toward a flow-scaled target so opening LV-322501 (drain_kgh up
#   -> m_feed_323 up -> m_305 up) forward-accumulates head:
#     P_tgt = P_des + K_P * (m_305 - m_305,des) / m_305,des      [bar a]
#     dP/dt = (P_tgt - P) / tau_P
#   Seed-exact: at design m_305 == R323_M305_DES => P_tgt == R323_C003_P_BARA => dP/dt == 0 (pin invariant).
R323_C003_P_GAIN    = 1.20                      # bar a per unit fractional top-vapour excess
R323_C003_P_TAU_S   = 90.0                      # s, column vapour-space pressure relaxation

# --- Stage 2: Flash Tank 323F004 (adiabatic flash 4.1 -> 1.13 bar a, -> 106 C)
R323_F004_P_BARA    = 1.13                      # bar a, flash pressure
R323_F004_T_SP_C    = 106.0                     # C, flash-liquid boundary (stream 319)
R323_PHI_V701       = 4430.0 / 106000.0         # 0.041792 flash-vapor split (stream 701)
R323_F004_M_TAU_S   = 180.0                     # s, liquid residence
R323_F004_LVL_SP    = 60.0                      # %
R323_F004_RHO       = 1180.0                    # kg/m3, ~106 C liquor
R323_LV505_OP_DES   = 50.0                      # %, LV-323505 design stroke
# Dynamic flash pressure 323F004 (hydraulic coupling to LV-323501 via bottom-drain / flash-vapour 701).
#   Opening LV-323501 (m_314 up) raises flash-vapour m_701 into the LP node read by PIC-323203:
#     P_tgt = P_des + K_P * (m_701 - m_701,des) / m_701,des      [bar a]
#     dP/dt = (P_tgt - P) / tau_P
#   Seed-exact: at design m_701 == R323_M701_DES => P_tgt == R323_F004_P_BARA => dP/dt == 0 (pin invariant).
R323_F004_P_GAIN    = 0.45                      # bar a per unit fractional flash-vapour excess
R323_F004_P_TAU_S   = 90.0                      # s, flash-drum pressure relaxation

# --- Stage 3: Pre-evaporator 323E010 + Separator 323F010 (vacuum 0.46 bar a, hold 99 C)
R323_F010_P_BARA    = 0.46                      # bar a, FIXED vacuum boundary (Ejector I 324F002)
R323_F010_T_SP_C    = 99.0                      # C, product boundary (stream 315/317, 80% urea)
R323_PHI_VEVAP      = 8750.0 / 101570.0         # 0.086147 evaporated-water split (-> vacuum sys)
R323_EVAP_LAMBDA    = 2280.0                    # kJ/kg, water latent @ 0.46 bar a
R323_E010_OP_DES    = 40.0                      # %, PV-329208 design stroke
R323_E010_PCHEST_DES = R323_E010_OP_DES / 100.0 * R323_P_STEAM_SUP   # 1.76 bar a
R323_F010_M_TAU_S   = 240.0                     # s, liquid residence
R323_F010_LVL_SP    = 60.0                      # %
R323_F010_RHO       = 1300.0                    # kg/m3, 80% urea @ 99 C

# --- Stage 4: Urea Solution Tank 323D002 (atmospheric, two-compartment buffer)
R323_D002_VOL_I_M3  = 80.0                      # m3, Compartment I (active flow-through)
R323_D002_VOL_II_M3 = 300.0                     # m3, Compartment II (passive buffer)
R323_D002_RHO       = 1300.0                    # kg/m3, 80% urea @ 99 C
R323_D002_LVL_SP    = 65.0                      # %, LIC-323507 (Compartment I) setpoint
R323_FV401_OP_DES   = 50.0                      # %, FV-324401 design stroke

# --- Derived design flows (kg/h) from the split fractions on the design feed ---
R323_M305_DES  = R323_PHI_V305  * R323_FEED_DES_KGH                       # top vapor -> LPCC
R323_M314_DES  = (1.0 - R323_PHI_V305) * R323_FEED_DES_KGH                # rectifier bottom -> flash
R323_M701_DES  = R323_PHI_V701  * R323_M314_DES                           # flash vapor -> LPCC
R323_M319_DES  = (1.0 - R323_PHI_V701) * R323_M314_DES                    # flash liquid -> pre-evap
R323_MEVAP_DES = R323_PHI_VEVAP * R323_M319_DES                           # evaporated water -> vac
R323_M317_DES  = (1.0 - R323_PHI_VEVAP) * R323_M319_DES                   # product -> tank
R323_M324_DES  = R323_M317_DES                                           # tank throughput -> Unit 324

# --- Derived latent / duty terms (force dT/dt = 0 at each design fixed point) ---
# Stage 1 energy balance: mdot_feed*cp*(Tfeed-135) + Q_E002 - mdot_305*lambda_305 = 0
R323_LAMBDA_305 = (R323_FEED_DES_KGH/3600.0*R323_CP_SOLN*(R323_FEED_DES_T_C - R323_C003_T_SP_C)
                   + R323_E002_Q_DES_KW) / (R323_M305_DES/3600.0)          # kJ/kg (~645.6)
R323_E002_UA_KW = R323_E002_Q_DES_KW / (tsat_steam(R323_E002_PCHEST_DES) - R323_C003_T_SP_C)  # kW/K
# Stage 2 adiabatic flash: mdot_314*cp*(135-106) - mdot_701*lambda_701 = 0
R323_LAMBDA_701 = (R323_M314_DES/3600.0*R323_CP_SOLN*(R323_C003_T_SP_C - R323_F004_T_SP_C)) \
                  / (R323_M701_DES/3600.0)                                 # kJ/kg (~1734.8)
# Stage 3 energy balance: mdot_319*cp*(106-99) + Q_E010 - mdot_evap*lambda_evap = 0
R323_E010_Q_DES_KW = (R323_MEVAP_DES/3600.0*R323_EVAP_LAMBDA
                      - R323_M319_DES/3600.0*R323_CP_SOLN*(R323_F004_T_SP_C - R323_F010_T_SP_C))  # kW (~5048)
R323_E010_UA_KW = R323_E010_Q_DES_KW / (tsat_steam(R323_E010_PCHEST_DES) - R323_F010_T_SP_C)  # kW/K

# --- Design liquid holdups (kg) and level spans from residence times ---
R323_C003_M_DES  = R323_M314_DES/3600.0 * R323_C003_M_TAU_S               # kg at design
R323_C003_M_FULL = R323_C003_M_DES / (R323_C003_LVL_SP/100.0)             # kg at 100% level
R323_F004_M_DES  = R323_M319_DES/3600.0 * R323_F004_M_TAU_S
R323_F004_M_FULL = R323_F004_M_DES / (R323_F004_LVL_SP/100.0)
R323_F010_M_DES  = R323_M317_DES/3600.0 * R323_F010_M_TAU_S
R323_F010_M_FULL = R323_F010_M_DES / (R323_F010_LVL_SP/100.0)
R323_D002_M_I_FULL  = R323_D002_VOL_I_M3  * R323_D002_RHO                 # kg at 100% Comp I
R323_D002_M_II_FULL = R323_D002_VOL_II_M3 * R323_D002_RHO                 # kg at 100% Comp II
R323_D002_M_I_DES   = R323_D002_M_I_FULL  * (R323_D002_LVL_SP/100.0)

# ==========================================================================
#  UNITS 323-2 / 328-1 / 328-2 — LP RECIRCULATION & DESORPTION
#  Screens 323-2 (LP carbamate condensation), 328-1 (desorption/hydrolysis
#  train), 328-2 (LP absorber + carbamate collection). Design anchors:
#  Combined 1750 MTPD 100%-load PFD-21/22 MB + LPCC/desorber/hydrolyser DS.
#
#  Design-fixed-point discipline (identical to Unit 323-1 above):
#    * every design flow is a Python expression over the existing R323_*
#      constants, or over anchors defined here IN DEPENDENCY ORDER — never a
#      re-typed PFD number — so the boot state is bit-exact.  (e.g.
#      R323_M305_DES = (24582/130582)*130482 = 24563.4, NOT the raw 24582.)
#    * every holdup ODE   dM/dt = Σṁ_in − ṁ_vap − ṁ_out          = 0 at design
#    * every thermal ODE  M·cp·dT/dt = Σṁ_in·cp·(T_in−T) + Q − ṁ_vap·λ = 0 at
#      design, with the unknown λ (phase change) or UA/Q (exchanger) BACK-
#      SOLVED here so the RHS is exactly 0 at the design seed.
#    * every flow = live valve/speed stroke normalised to its design stroke;
#      every vapour/vent = design split-fraction × live inflow.
#  These screens only READ Unit-323 outputs (feed-forward) -> the 135/106/99°C
#  boundaries stay isolated by construction.
#
#  Whole-network mass closure (design, kg/h) — verified to close exactly:
#    328D003 Comp I : in 719+720+721+V001(3579) = 34868 = out 735+402+401
#    Comp II        : in 744(31478)             = out 755(31478)
#    322C001        : in 755+GCB+CPL(900)       = vent + 756(33358); abs 980
#    323E003        : in 305+718B+776+797+756   = 321(1323)+744(31478)+308
#    323E011        : in 701+702+786+321+402    = v011(3099)+718 liq;  +401 -> D011
#    328C002        : in 738+748+750+775(40434) = 737(6665)+743(33769)
#    328C003        : in 746+911(34874)         = 748(812)+747(34062)
#    328C004        : in 749+931(40557)         = 750(6833)+739(33724)
#    328D001        : in 737(6665)+718A         = 786(276)+775(1675)+776(8274)
# ==========================================================================
R3232_CP = 3.0     # kJ/kg·K  LP-carbamate / condensate train (323E003, 323E011)
R328_CP  = 4.0     # kJ/kg·K  desorber / hydrolyser aqueous train (328C002/003/004)
A328_CP  = 4.0     # kJ/kg·K  LP absorber 322C001 aqueous liquor

# ---- boundary (fixed) feed streams  (kg/h @ °C) ----
R3232_M797_DES = 1758.0 ; R3232_M797_T = 46.0     # inert-laden recycle -> 323E003
R3232_M702_DES = 440.0  ; R3232_M702_T = 45.0     # flash recycle       -> 323E011
A328_CPL_DES   = 900.0  ; A328_CPL_T   = 30.0     # process condensate  -> 322C001
A328_D003_M719 = 26768.0; A328_D003_M719_T = 45.0 # 719 -> 328D003 Comp I
A328_D003_M720 = 2758.0 ; A328_D003_M720_T = 40.0 # 720 -> 328D003 Comp I
A328_D003_M721 = 1763.0 ; A328_D003_M721_T = 41.0 # 721 -> 328D003 Comp I

# ==========================================================================
#  328C002  Desorber-I  (bottoms 139 °C ; top 117 °C ; floats on PIC-328202)
#  Reboil heat = latent of the two hot recycle OVHDs 748(@188)+750(@140) that
#  CONDENSE here; the stripped OVHD 737 is generated (latent λ737 back-solved).
# ==========================================================================
R328_C002_M738_DES = 31114.0                                # 738 liquid feed (=735 via 328E007)
R328_C002_M748_DES = 812.0                                  # 748 hydrolyser-I OVHD (condenses)
R328_C002_M750_DES = 6833.0                                 # 750 desorber-II OVHD (condenses)
R328_C002_M775_DES = 1675.0                                 # 775 reflux from 328D001
R328_C002_IN_DES   = (R328_C002_M738_DES + R328_C002_M748_DES
                      + R328_C002_M750_DES + R328_C002_M775_DES)          # 40434
R328_C002_PHI737   = 6665.0 / 40434.0                       # OVHD split -> 328D001 (737)
R328_C002_M737_DES = R328_C002_PHI737 * R328_C002_IN_DES    # 6665
R328_C002_M743_DES = R328_C002_IN_DES - R328_C002_M737_DES  # 33769 bottoms -> hydrolyser
R328_C002_T_BOT = 139.0 ; R328_C002_T_TOP = 117.0
R328_C002_T738 = 114.0 ; R328_C002_T748 = 188.0 ; R328_C002_T750 = 140.0
R328_D001_T = 61.0                                          # 775 reflux temperature (from 328D001)
R328_C002_M_TAU_S = 900.0
R328_C002_M_DES   = R328_C002_M743_DES/3600.0 * R328_C002_M_TAU_S         # 8442 kg
R328_C002_LAM748 = 2000.0 ; R328_C002_LAM750 = 2100.0       # kJ/kg condensation of recycle OVHDs
# sensible net onto the 139°C bottoms (kW), then λ737 closes M·cp·dT/dt = 0:
R328_C002_SENS = ((R328_C002_M738_DES*(R328_C002_T738 - R328_C002_T_BOT)
                   + R328_C002_M775_DES*(R328_D001_T   - R328_C002_T_BOT)
                   + R328_C002_M748_DES*(R328_C002_T748 - R328_C002_T_BOT)
                   + R328_C002_M750_DES*(R328_C002_T750 - R328_C002_T_BOT))
                  / 3600.0 * R328_CP)                                     # kW
R328_C002_LAM737 = ((R328_C002_SENS
                     + R328_C002_M748_DES/3600.0*R328_C002_LAM748
                     + R328_C002_M750_DES/3600.0*R328_C002_LAM750)
                    / (R328_C002_M737_DES/3600.0))                        # kJ/kg (~1879)

# ==========================================================================
#  328C003  Hydrolyser  (200 °C, 16.8 bar a, MP-steam 911, 1 h residence)
#  Hydrolysis  NH2CONH2 + H2O <=> 2NH3 + CO2  is ENDOTHERMIC; MP steam 911
#  supplies it.  λ748_gen (OVHD generation latent) lumps the reaction endotherm
#  and is back-solved so M·cp·dT/dt = 0 at design.
# ==========================================================================
R328_C003_M746_DES = R328_C002_M743_DES                     # 33769 feed via 328E021 (cold)
R328_C003_M911_DES = 1105.0                                 # MP-steam strip (FIC-326402)
R328_C003_M911_DH  = 2235.0                                 # kJ/kg MP-steam enthalpy drop
R328_C003_IN_DES   = R328_C003_M746_DES + R328_C003_M911_DES              # 34874
R328_C003_PHI748   = 812.0 / 34874.0                        # OVHD split -> 328C002 (748)
R328_C003_M748_DES = R328_C003_PHI748 * R328_C003_IN_DES    # 812
R328_C003_M747_DES = R328_C003_IN_DES - R328_C003_M748_DES  # 34062 bottoms -> desorber-II
R328_C003_T = 200.0 ; R328_C003_T746 = 190.0
R328_C003_DT_DES = R328_C003_T - R328_C003_T746            # 10 C differential (TT-328013 bottom - TT-328012 3rd tray), TIC-328012
R328_C003_P_BARA = 16.8 ; R328_C003_P_KP = 0.02
R328_C003_PV_OP_DES = 50.0                                  # PV-328203 OVHD stroke
R328_C003_M_DES = R328_C003_M747_DES/3600.0 * 3600.0        # 34062 kg (1 h residence)
# λ748_gen back-solve: m746·cp·(190−200) + m911·ΔH − m748·λ748 = 0
R328_C003_LAM748 = ((R328_C003_M746_DES/3600.0*R328_CP*(R328_C003_T746 - R328_C003_T)
                     + R328_C003_M911_DES/3600.0*R328_C003_M911_DH)
                    / (R328_C003_M748_DES/3600.0))                        # kJ/kg (~1378)

# ==========================================================================
#  328C004  Desorber-II  (143 °C, LP-steam 931, 900 s residence)
# ==========================================================================
R328_C004_M749_DES = R328_C003_M747_DES                     # 34062 feed via 328E021 (hot)
R328_C004_M931_DES = 6495.0                                 # LP-steam strip (FIC-328401)
R328_C004_M931_DH  = 2136.0                                 # kJ/kg LP-steam enthalpy drop
R328_C004_IN_DES   = R328_C004_M749_DES + R328_C004_M931_DES             # 40557
R328_C004_PHI750   = 6833.0 / 40557.0                       # OVHD split -> 328C002 (750)
R328_C004_M750_DES = R328_C004_PHI750 * R328_C004_IN_DES    # 6833
R328_C004_M739_DES = R328_C004_IN_DES - R328_C004_M750_DES  # 33724 bottoms -> 328E007 -> boundary
R328_C004_T = 143.0 ; R328_C004_T749 = 148.0
R328_C004_DT_DES = R328_C004_T - R328_C002_T750             # 3 C bottom (143) - top tray (140 = OVHD 750), TT-328004
R328_C004_M_TAU_S = 900.0
R328_C004_M_DES   = R328_C004_M739_DES/3600.0 * R328_C004_M_TAU_S         # 8431 kg
R328_C004_LAM750 = ((R328_C004_M749_DES/3600.0*R328_CP*(R328_C004_T749 - R328_C004_T)
                     + R328_C004_M931_DES/3600.0*R328_C004_M931_DH)
                    / (R328_C004_M750_DES/3600.0))                        # kJ/kg (~2130)
# FFIC-328401 master ratio  m931/m735  (steam-to-feed, held on desorber-II load)
R328_FFIC_RATIO_DES = R328_C004_M931_DES / R328_C002_M738_DES             # 0.20876

# ==========================================================================
#  323E011 + 323D011  (LP carbamate condenser + drum, 45 °C, 1.13 bar a)
#  Combined 9400 kg/h datasheet closes the E011 inlet exactly.  Vapour v011
#  (3100/9400) -> 323C005; liquid + FIC-323401 flush 401 -> 323D011 -> 718.
# ==========================================================================
R3232_E011_M701_DES = R323_M701_DES                         # 4426.6 flash vapour ex 323F004
R3232_E011_M786_DES = 276.0                                 # vent from 328D001 (stream 786)
R3232_E011_M321_DES = R3232_M797_DES*0.0 + 1323.0           # 323E003 vent (stream 321)
R3232_E011_M402_DES = 2931.0                                # 328D003 Comp-I wash (FIC-323402)
R3232_E011_IN_DES   = (R3232_E011_M701_DES + R3232_M702_DES + R3232_E011_M786_DES
                       + R3232_E011_M321_DES + R3232_E011_M402_DES)       # 9396.6
R3232_E011_PHIV     = 3100.0 / 9400.0                       # vapour split -> 323C005 (v011)
R3232_E011_MV_DES   = R3232_E011_PHIV * R3232_E011_IN_DES   # 3098.8
R3232_E011_M401_DES = 823.0                                 # 328D003 Comp-I flush (FIC-323401)
R3232_D011_M718_DES = (R3232_E011_IN_DES - R3232_E011_MV_DES) + R3232_E011_M401_DES  # 7120.8
R3232_M718A_DES = 0.5 * R3232_D011_M718_DES                 # 3560.4 -> 328D001
R3232_M718B_DES = 0.5 * R3232_D011_M718_DES                 # 3560.4 -> 323E003
R3232_E011_T = 45.0 ; R3232_E011_T701 = 106.0 ; R3232_E011_T786 = 61.0
R3232_E011_P_BARA = 1.13 ; R3232_E011_P_KP = 0.05
R3232_E011_PV_OP_DES = 25.0                                 # PIC-323203 vent stroke
R3232_D011_M_TAU_S = 600.0
R3232_D011_M_DES   = R3232_D011_M718_DES/3600.0 * R3232_D011_M_TAU_S      # 1186.8 kg
R3232_D011_LVL_SP  = 50.0                        # LT-323503 design level (%): OEM "maintains the
#   flash tank condenser level tank at 50% capacity" (328E021 328E007 328P003 328P006.md:359).
R3232_LV503_OP_DES  = 50.0                       # LV-323503 stroke, 323P008 common discharge header
R3232_FIC405_OP_DES = 50.0                       # FV-323405 stroke, 718A leg -> 328E004/328D001
R3232_FIC418_OP_DES = 50.0                       # FV-323418 stroke, 718B leg -> 323E003
R3232_E011_Q_DES_KW = 3440.0                                # datasheet condenser duty
R3232_E011_UA_KW    = R3232_E011_Q_DES_KW / (R3232_E011_T - 35.0)         # kW/K vs 35°C CW
# λ_v011 (vapour-generation latent) closes the drum energy balance at 45°C:
R3232_E011_SENS = ((R3232_E011_M701_DES*(R3232_E011_T701 - R3232_E011_T)
                    + R3232_M702_DES*(R3232_M702_T       - R3232_E011_T)
                    + R3232_E011_M786_DES*(R3232_E011_T786 - R3232_E011_T)
                    + R3232_E011_M321_DES*(74.0          - R3232_E011_T)
                    + R3232_E011_M402_DES*(56.0          - R3232_E011_T))
                   / 3600.0 * R3232_CP)                                   # kW
R3232_E011_LAMV = ((R3232_E011_SENS - R3232_E011_Q_DES_KW)
                   / (R3232_E011_MV_DES/3600.0)) * -1.0                   # kJ/kg (>0)

# ==========================================================================
#  328D001  Desorber-I reflux drum (61 °C, 2.6 bar a); 328E004 condenses 737
# ==========================================================================
R328_D001_M737_DES  = R328_C002_M737_DES                    # 6665 OVHD vapour in
R328_D001_M718A_DES = R3232_M718A_DES                       # 3560.4 recycle in
R328_D001_IN_DES    = R328_D001_M737_DES + R328_D001_M718A_DES
R328_D001_M786_DES  = 276.0                                 # vent -> 323E011
R328_D001_M775_DES  = R328_C002_M775_DES                    # 1675 reflux -> 328C002 (FIC-328404)
R328_D001_M776_DES  = R328_D001_IN_DES - R328_D001_M786_DES - R328_D001_M775_DES  # 8274.4 -> 323E003
R328_D001_M776_RHO  = 1095.0    # kg/m3, stream 776 eff. density @61 C (Combined_1750 tbl, col 776) -> FT-328401 m3/h (8274.4/1095=7.56 -> PFD 7.6)
R328_D001_M774_DES  = R328_D001_M775_DES + R328_D001_M776_DES             # 9949 (PFD 774 ✓)
R328_D001_T718A = 45.0
R328_D001_M_FULL = 20900.0
R328_D001_LVL_SP = 50.5
R328_D001_M_DES  = R328_D001_M_FULL * (R328_D001_LVL_SP/100.0)            # 10554.5 kg
R328_D001_P_BARA = 2.6 ; R328_D001_P_KP = 0.05
R328_D001_PV_OP_DES = 50.0                                  # PIC-328202 vent stroke
R328_D001_LV_OP_DES = 50.0                                  # LV-328501 stroke
R328_D001_FIC404_OP_DES = 30.2                              # FIC-328404 (775 reflux) stroke
R328_E004_Q_DES_KW = 4357.0                                 # datasheet condenser duty
R328_E004_TV_OP_DES = 50.0                                  # TV-328002 CW stroke
# λ737_cond (condensation latent) closes drum energy balance at 61°C:
R328_D001_SENS = ((R328_D001_M737_DES*(R328_C002_T_TOP - R328_D001_T)
                   + R328_D001_M718A_DES*(R328_D001_T718A - R328_D001_T))
                  / 3600.0 * R328_CP)                                     # kW
R328_D001_LAM737 = ((R328_E004_Q_DES_KW - R328_D001_SENS)
                    / (R328_D001_M737_DES/3600.0))                        # kJ/kg (~2163)

# ==========================================================================
#  322C001  LP absorber (43 °C, 3.9 bar a); GCB off-gas boot-pinned at runtime
# ==========================================================================
A328_M755_DES = 31478.0                                     # Comp-II draw via 322P002
A328_M755_RHO = 1005.0                                      # kg/m3, stream 755 eff. density @40 C (Combined_1750 tbl, col 755) -> FT-322402 m3/h (31478/1005=31.32 -> PFD 31.3)
A328_ABS_DES  = 980.0                                       # NH3/CO2 absorbed into liquor
A328_M756_DES = A328_M755_DES + A328_CPL_DES + A328_ABS_DES # 33358 -> 323E003 wash feed
A328_C001_T = 43.0 ; A328_M755_T = 40.0
A328_C001_P_BARA = 3.9 ; A328_C001_P_KP = 0.02
A328_PIC_OP_DES = 67.8                                      # PIC-322201 vent stroke
A328_LIC_OP_DES = 50.0                                      # LIC-322502 -> LV-322502 stroke
A328_C001_M_TAU_S = 600.0
A328_C001_M_DES = A328_M756_DES/3600.0 * A328_C001_M_TAU_S  # 5559.7 kg
A328_QFLOOD_KW  = 500.0                                     # XV-322915 steam-flood latent load
# GCB boot-pin globals (lazy-pinned in step_sim Stage I; reset in _pin_hpcc_ua):
A328_GCB_DES    = None   # kg/h off-gas from HV-322604 at the settled design seed
A328_GCB_T      = None   # °C off-gas temperature
A328_PHI_ABS    = None   # absorbed fraction 980/GCB_DES
A328_VENT_DES   = None   # kg/h vented = GCB_DES − 980
A328_LAMBDA_ABS = None   # kJ/kg absorption enthalpy (back-solved at pin for T=43)

# ==========================================================================
#  323E003 + 323D001 + 323P001  LPCC (74 °C, tempered-water cooled, 3.2 bar a)
# ==========================================================================
R3232_E003_M305_DES  = R323_M305_DES                        # 24563.4 top vapour ex 323C003
R3232_E003_M718B_DES = R3232_M718B_DES                      # 3560.4
R3232_E003_M776_DES  = R328_D001_M776_DES                   # 8274.4
R3232_E003_M797_DES  = R3232_M797_DES                       # 1758
R3232_E003_M756_DES  = A328_M756_DES                        # 33358
R3232_E003_IN_DES    = (R3232_E003_M305_DES + R3232_E003_M718B_DES + R3232_E003_M776_DES
                        + R3232_E003_M797_DES + R3232_E003_M756_DES)      # 71514.2
R3232_E003_PHI321 = 1323.0 / (R3232_E003_M305_DES + R3232_E003_M797_DES)  # vent split on (305+797)
R3232_E003_M321_DES = R3232_E003_PHI321 * (R3232_E003_M305_DES + R3232_E003_M797_DES)  # 1323
R3232_E003_PHI744 = 31478.0 / A328_M756_DES                 # wash split on 756 -> Comp II
R3232_E003_M744_DES = R3232_E003_PHI744 * A328_M756_DES      # 31478
R3232_E003_M308_DES = R3232_E003_IN_DES - R3232_E003_M321_DES - R3232_E003_M744_DES  # 38713.2
R3232_E003_T = 74.0 ; R3232_TW_T = 60.0 ; R3232_E003_T305 = 119.0
# 323E003 tempered-water circuit: PFD stream 1102 supply 55 °C / 1103 return 65 °C.  R3232_TW_T is
#   their mean (== 60) and stays the DESIGN datum for the UA back-solve below -- never a live value.
R3232_TW_SUP_T = 55.0 ; R3232_TW_RET_T = 65.0               # TIC-323013 SP (1102) ; TT-323015 (1103)
R3232_TV13_DES_PCT = 50.0 ; R3232_TW_TAU_S = 25.0           # TV-323013A design stroke ; supply-T lag (s)
R3232_E003_T744 = R3232_E003_T - 30.0                       # 44 °C wash to Comp II
R3232_D001_P_BARA = 3.2 ; R3232_D001_P_KP = 0.03
R3232_E003_PV_OP_DES = 25.0                                 # PV-323202 vent stroke
R3232_D001_M_FULL = 11.10 * 1218.0                          # 13519.8 kg (V·ρ)
R3232_D001_LVL_SP = 50.0
R3232_D001_M_DES  = R3232_D001_M_FULL * (R3232_D001_LVL_SP/100.0)         # 6759.9 kg
R3232_E003_Q_DES_KW = 14000.0                               # tempered-water duty (LPCC datasheet)
R3232_E003_UA_KW    = R3232_E003_Q_DES_KW / (R3232_E003_T - R3232_TW_T)   # 1000 kW/K vs T_tw
R3232_E003_M_COND_DES = R3232_E003_M305_DES + R3232_E003_M797_DES - R3232_E003_M321_DES  # 24998.4
# λ_cond back-solve: Σṁ_in·cp·(T_in−74) + ṁ_cond·λ − Q_cw = 0
R3232_E003_SENS = ((R3232_E003_M305_DES *(R3232_E003_T305    - R3232_E003_T)
                    + R3232_E003_M718B_DES*(R3232_E011_T      - R3232_E003_T)
                    + R3232_E003_M776_DES *(R328_D001_T       - R3232_E003_T)
                    + R3232_E003_M797_DES *(R3232_M797_T      - R3232_E003_T)
                    + R3232_E003_M756_DES *(A328_C001_T       - R3232_E003_T))
                   / 3600.0 * R3232_CP)                                   # kW
R3232_E003_LAMC = ((R3232_E003_Q_DES_KW - R3232_E003_SENS)
                   / (R3232_E003_M_COND_DES/3600.0))                      # kJ/kg
R3232_P001_RPM_DES = R3232_E003_M308_DES / (1218.0 * 0.5046)              # 62.99 rpm (SIC-323901)

# ==========================================================================
#  323C005 + 328V001 + 328D003  (LP absorber vent scrub + carbamate collector)
# ==========================================================================
A323_C005_MV_DES   = R3232_E011_MV_DES                      # 3098.8 vapour in ex 323E011
A323_C005_MAKEUP   = ((R328_C002_M738_DES + R3232_E011_M401_DES + R3232_E011_M402_DES
                       - A328_D003_M719 - A328_D003_M720 - A328_D003_M721)
                      - A323_C005_MV_DES)                   # 480.2: makeup water back-solved
#   so bot_c005 (=MV_DES+MAKEUP) exactly closes 328D003 Comp-I: in_compI == out_compI at design.
A323_C005_BOT_DES  = A323_C005_MV_DES + A323_C005_MAKEUP    # 3579 -> 328V001 -> Comp I
A323_C005_T = 55.0 ; A323_C005_MAKEUP_T = 30.0
A323_C005_M_TAU_S = 300.0
A323_C005_M_DES = A323_C005_BOT_DES/3600.0 * A323_C005_M_TAU_S            # 298.2 kg
A323_C005_LAM = ((A323_C005_MV_DES/3600.0*R3232_CP*(R3232_E011_T - A323_C005_T)
                  + A323_C005_MAKEUP/3600.0*4.0*(A323_C005_MAKEUP_T - A323_C005_T))
                 / (A323_C005_MV_DES/3600.0)) * -1.0                      # kJ/kg absorbed
A328_D003_MI_FULL = 280.50 * 992.0                          # Comp I  (V·ρ)  278256 kg
A328_D003_MII_FULL = 168.30 * 992.0                         # Comp II       166954 kg
A328_D003_MI_DES  = A328_D003_MI_FULL * 0.50               # 139128 kg
A328_D003_MII_DES = A328_D003_MII_FULL * 0.50              # 83477 kg
A328_D003_M343_DES = R328_C002_M738_DES + R3232_E011_M402_DES + R3232_E011_M401_DES  # 34868 out
A328_D003_TI = 56.0 ; A328_D003_TII = 44.0
A328_D003_V001_T = A323_C005_T                             # 55 °C V001 pass-through
# Comp I carbamate-formation exotherm 2NH3+CO2<=>NH2COONH4 (λ_I on total inflow):
A328_D003_LAM_I = -A328_CP * (
      A328_D003_M719*(A328_D003_M719_T - A328_D003_TI)
    + A328_D003_M720*(A328_D003_M720_T - A328_D003_TI)
    + A328_D003_M721*(A328_D003_M721_T - A328_D003_TI)
    + A323_C005_BOT_DES*(A328_D003_V001_T - A328_D003_TI)
    ) / (A328_D003_M719 + A328_D003_M720 + A328_D003_M721 + A323_C005_BOT_DES)  # 42.2858: exact back-solve, P_compI==0 at 56C seed

# ==========================================================================
#  328E021 A/B  (hydrolyser feed/effluent interchanger, two shells in series)
#  Heats C002 bottoms 139->190 (cold) with C003 bottoms 200->148 (hot).
# ==========================================================================
R328_E021_EPS  = 1913.6 / (37.52 * 61.0)                    # 0.836 effectiveness (datasheet, rounded)
R328_E021_LOSS = 54.4                                       # kW shell heat loss (closes both anchors)
# Live cold-outlet effectiveness (stream 746).  The rounded datasheet pair above back-solves to
#   190.0021 C, so it cannot carry the design anchor; the design temperatures give the same
#   effectiveness exactly and reconstruct the datasheet in the process -- Q_cold = 33769/3600*4.0*51
#   = 1913.58 kW (~ its 1913.6) and the hot/cold closure 1968.03 - 1913.58 = 54.45 kW (~ its 54.4).
R328_E021_EPS_T = (R328_C003_T746 - R328_C002_T_BOT) / (R328_C003_T - R328_C002_T_BOT)   # 51/61 = 0.83607
R328_E007_EPS  = 0.6667                                     # 328E007 feed/effluent interchanger
R328_E007_LOSS = 18.3                                       # kW shell heat loss
R328_E007_TC_OUT = 114.0 ; R328_E007_TH_OUT = 89.0         # -> 738 feed / 740 boundary
# --- TIC-328008 inferential: H2O mol% in 328C002 offgas (-> 328E004) ---
# VLE node is the 328C002 OVHD (117 C / 3.5 bar a), NOT the 328D001 drum (2.6 bar a):
# the drum sits 0.9 bar below the column top across 328E004, so the drum-node Raoult
# (62.9 mol%) mis-anchored the split. Pure Raoult at the true node is 51.44 mol%,
# still 5.2 pts over the datasheet, so a lumped H2O activity coeff PHI closes it to
# the mandated PFD stream 737 (46.21 mol%). PHI back-solves as an identity, so DES
# reproduces 46.21 bit-exact while the runtime form (main.py:~3757) stays live on drum P.
R328_C002_P_TOP  = 3.5                                      # 328C002 OVHD press (bar a) at the VLE node
R328_E004_DP     = R328_C002_P_TOP - R328_D001_P_BARA       # 0.9 bar drop 328C002 top -> 328D001 drum over 328E004
R328_D001_OFFGAS_H2O_PFD = 46.21                            # mol% H2O in offgas, Combined_1750 PFD stream 737 @117 C / 3.5 bar a
R328_D001_OFFGAS_PHI = (R328_D001_OFFGAS_H2O_PFD/100.0) * R328_C002_P_TOP / psat_water_bara(R328_C002_T_TOP)   # H2O activity coeff back-solved to PFD 737; psat(117)=1.8004 -> 0.898328
R328_D001_OFFGAS_H2O_DES = 100.0 * R328_D001_OFFGAS_PHI * psat_water_bara(R328_C002_T_TOP) / R328_C002_P_TOP   # = 46.21 mol% -> 328E004 (identity anchor; supersedes 62.9 drum-node Raoult)


# ==========================================================================
#  UNIT 324  —  TWO-STAGE VACUUM EVAPORATION  (Screens 324-1 / 324-1B)
#  Feed  = 323D002 product delivered by FIC-324401 (m_324, live): 80 % urea,
#          ~99 C.  Product = 98.6 % urea melt to 335 finishing.
#    Stage 1  Evaporator I   324E001 (heater) + 324F001 (separator)
#             HARD anchors : 0.33  bar a vacuum, hold 130 C, urea 80 % -> 95 %.
#    Stage 2  Evaporator II  324E003 (heater) + 324F003 (separator)
#             HARD anchors : 0.131 bar a vacuum, hold 140 C, urea 95 % -> 98.6 %.
#  Urea is strictly conserved (zero urea in the vapour).  Each stage removes
#  exactly the water needed to hit its concentration anchor, so the design
#  mass balance is a pure function of the *live* feed and boots bit-exact:
#      U   = w_in  * feed                         (urea, conserved)
#      P1  = U / w_ev1 ,   V1 = feed - P1         (Stage-1 melt / vapour)
#      P2  = U / w_ev2 ,   V2 = P1   - P2         (Stage-2 melt / vapour)
#  Latent / UA coefficients are back-solved at the seed so dT/dt = 0 exactly
#  at the 130/140 C fixed points; each vacuum is held by a PIC-324202/324203
#  false-air bleed balanced against a fixed-capacity ejector pull.
# ==========================================================================
R324_CP_SOLN   = R323_CP_SOLN                     # 2.5 kJ/kg.K lumped urea-melt cp
R324_W_IN      = 0.80                             # feed urea mass fraction (ex 323D002)
R324_W_EV1     = 0.9431                           # Evaporator-I product frac (HARD; HMB 324, was 0.95)
R324_W_EV2     = 0.9771                           # Evaporator-II product frac (HARD; HMB 324, was 0.986)
R324_FEED_T_C  = R323_F010_T_SP_C                 # 99 C feed boundary (stream ex 323)

# --- design mass balance (kg/h) : derived from the live design feed -----------
R324_FEED_DES  = R323_M324_DES                    # = R323_M317_DES tank throughput
R324_U_DES     = R324_W_IN  * R324_FEED_DES       # urea mass flow (conserved end-to-end)
R324_P1_DES    = R324_U_DES / R324_W_EV1          # Stage-1 melt @94.31 %
R324_V1_DES    = R324_FEED_DES - R324_P1_DES      # Stage-1 vapour -> 324E002 condenser
R324_P2_DES    = R324_U_DES / R324_W_EV2          # Stage-2 melt @97.71 % (final product)
R324_V2_DES    = R324_P1_DES  - R324_P2_DES       # Stage-2 vapour -> 324E005 condenser

# --- Stage 1 : Evaporator I  324E001 / 324F001  (0.33 bar a, hold 130 C) ------
R324_F001_P_BARA = 0.33                           # bar a separator vacuum boundary (HARD)
R324_E001_T_SP_C = 130.0                          # C melt boundary (HARD)
R324_LAM_V1      = 2174.0                          # kJ/kg water latent @130 C
R324_E001_OP_DES = 90.0                           # % PIC-329203 design steam-valve stroke
R324_E001_PCHEST_DES = R324_E001_OP_DES/100.0 * R323_P_STEAM_SUP   # bar a steam-chest press.
# Q_E001 = feed sensible (99->130) + latent(V1) ; kW
R324_E001_Q_DES_KW = (R324_FEED_DES/3600.0*R324_CP_SOLN*(R324_E001_T_SP_C - R324_FEED_T_C)
                      + R324_V1_DES/3600.0*R324_LAM_V1)
R324_E001_UA_KW  = R324_E001_Q_DES_KW / (tsat_steam(R324_E001_PCHEST_DES) - R324_E001_T_SP_C)
R324_F001_M_TAU_S = 180.0                          # s melt residence -> separator holdup
R324_F001_LVL_SP  = 55.0                           # % (LIC-free gravity leg, indicative)
R324_F001_M_DES   = R324_P1_DES/3600.0 * R324_F001_M_TAU_S
R324_F001_M_FULL  = R324_F001_M_DES / (R324_F001_LVL_SP/100.0)
# vacuum : PIC-324202 false-air bleed balances the 324F002 ejector pull at design
R324_F001_P_KP    = 0.02                           # bar a per (kg/s) net vapour imbalance
R324_F001_FA_DES  = 250.0                           # kg/h design false-air (PV-324202)
R324_PV202_OP_DES = 50.0                            # % PV-324202 design stroke
R324_F001_EJPULL_DES = R324_V1_DES + R324_F001_FA_DES   # ejector pull = gen + air at design

# --- Stage 2 : Evaporator II 324E003 / 324F003  (0.131 bar a, hold 140 C) -----
R324_F003_P_BARA = 0.131                           # bar a deep-vacuum boundary (HARD)
R324_E003_T_SP_C = 140.0                           # C melt boundary (HARD)
R324_LAM_V2      = 2144.0                           # kJ/kg water latent @140 C
R324_E003_OP_DES = 90.0                             # % PIC-329212 design steam-valve stroke
R324_E003_PCHEST_DES = R324_E003_OP_DES/100.0 * R323_P_STEAM_SUP
# Q_E003 = P1 sensible (130->140) + latent(V2) ; kW
R324_E003_Q_DES_KW = (R324_P1_DES/3600.0*R324_CP_SOLN*(R324_E003_T_SP_C - R324_E001_T_SP_C)
                      + R324_V2_DES/3600.0*R324_LAM_V2)
R324_E003_UA_KW  = R324_E003_Q_DES_KW / (tsat_steam(R324_E003_PCHEST_DES) - R324_E003_T_SP_C)
R324_F003_M_TAU_S = 180.0
R324_F003_LVL_SP  = 54.7                            # % LIC-324501 setpoint (tagged screenshot)
R324_F003_M_DES   = R324_P2_DES/3600.0 * R324_F003_M_TAU_S
R324_F003_M_FULL  = R324_F003_M_DES / (R324_F003_LVL_SP/100.0)
R324_F003_P_KP    = 0.02
R324_F003_FA_DES  = 120.0                            # kg/h design false-air (PV-324203)
R324_PV203_OP_DES = 50.0
R324_F003_EJPULL_DES = R324_V2_DES + R324_F003_FA_DES

# --- LIC-324501 split-range melt drain : LV-A forward (335P001) / LV-B recycle -
#     op 50->100 % strokes LV-A 0->100 % (forward) ; op 50->0 % strokes LV-B
#     0->100 % (recycle back to Stage-1 feed).  op_des 75 % -> LV-A 50 %, LV-B 0.
R324_LIC501_OP_DES = 75.0
R324_LVA_SPAN      = R324_P2_DES / 0.50             # kg/h at 100 % LV-A stroke
R324_LVB_SPAN      = R324_P1_DES                    # kg/h at 100 % LV-B recycle stroke

# --- FFIC-335406 UF85 ratio injection : m_uf85 = ratio * forward melt ----------
R324_UF_RATIO      = 697.0 / R324_P2_DES            # UF85/melt: HMB stream 697 = 697 kg/h abs @design (biuret guard); was 0.005 (376.3 kg/h)
R324_UF85_RHO      = 1320.0                          # kg/m3 UF85 (335D007)
R324_M_UF_DES      = R324_UF_RATIO * R324_P2_DES     # design UF85 injection (kg/h)
R324_FIC405_OP_DES = 50.0                            # % FIC-335405 slave design stroke


def ejector_322f001(motive_nh3_kgh: float, T_motive_C: float, hv_open_pct: float,
                    scrub_level_frac: float = 1.0) -> dict:
    """322F001 HP ejector: mix live motive NH3 with entrained 322E003 carbamate.
    Entrainment capacity is set by the HV-322602 spindle opening (HIC-322602).  Motive NH3
    is supplied by the 321P002 A/B POSITIVE-DISPLACEMENT (triplex) pumps -> motive MASS flow
    is CONSTANT.  The parabolic NH3-nozzle needle is a converging throat, so CLOSING it shrinks
    the area A and (at constant m_dot) raises the jet momentum m_dot^2/(rho*A) -> CLOSING the
    spindle raises the suction CAPACITY at ~const mu (NEGATIVE equal-% law, EJ_SPINDLE_R, from
    the 322F001 datasheet).  At the design opening (74 %) phi_sp = 1, mu = EJ_MU and the
    discharge reproduces the design 'Carb. Liq.' table.  Energy
    balance sets discharge temp.  Returns the discharge stream (-> 322E002) + props.

    Option-3 self-regulation: actual entrainment = CAPACITY * (L_scrub/NLL).  The
    scrub_level_frac (= prior-step 322E003 level / NLL, gravity suction head) makes the
    sump a STABLE attractor: at design L=NLL -> frac=1 -> entrain=capacity.  If the
    ejector stalls (capacity << overflow) the sump rises -> frac>1 -> entrain climbs back,
    settling at L_eq = NLL*(overflow/capacity); a true motive fault floods it.  frac=1.0
    (unit-test / warm-up path) reproduces design entrainment exactly."""
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
    # HV-322602 (HIC-322602) sets entrainment: CLOSING the spindle -> higher jet momentum (const-ṁ) -> more 322E003 suction.
    open_eff = clamp(hv_open_pct, 10.0, 100.0)
    # Representative non-linear liquid-liquid jet-ejector entrainment law (322F001, Options 2+3):
    #   The entrainment RATIO mu is ~constant across the healthy band and the suction CAPACITY scales
    #   with live motive; a deep-stall factor collapses it only on a genuine motive fault.  ACTUAL
    #   entrainment is then gated by the gravity suction head (scrub level) so the sump is a STABLE
    #   self-regulating attractor at NLL -- it does NOT false-flood on proportional turndown (where
    #   capacity AND overflow drop together) yet floods on a real stall (capacity << overflow):
    #       phi_m    = motive / EJ_MOTIVE_DES_LIVE        (live design motive -> phi_m==1 bit-exact)
    #       phi_sp   = EJ_SPINDLE_R^((EJ_OPEN_DES - open_eff)/100)   (NEGATIVE equal-% spindle char, 322F001
    #                  DDS; phi_sp(74)=R^0=1 bit-exact; CLOSING MORE -> MORE capacity, const-ṁ converging-nozzle momentum)
    #       f_stall  = clamp((phi_m - PHI)/(REC - PHI), 0, 1) ^ EXP      PHI=0.20, REC=0.35, EXP=2
    #       capacity = EJ_SUC_TOT_DES * phi_m * phi_sp * f_stall
    #       m_suc    = capacity * scrub_level_frac        (frac = L_scrub/NLL, gravity suction head)
    #   Steady fixed point: m_suc==overflow -> L_eq = NLL*(overflow/capacity).  Proportional turndown:
    #     capacity ~ phi_m ~ overflow -> L_eq=NLL (dead steady).  Motive fault (phi_m<REC, load held):
    #     f_stall->0 -> capacity<<overflow -> L_eq>>NLL -> sump RISES (true stall).  Design (phi_m=1,
    #     open=EJ_OPEN_DES -> phi_sp=1, L=NLL -> frac=1): m_suc == EJ_SUC_TOT_DES bit-exact.
    _ej_mot_des = EJ_MOTIVE_DES_LIVE if EJ_MOTIVE_DES_LIVE is not None else EJ_MOTIVE_NH3_DES
    phi_m    = motive_nh3_kgh / _ej_mot_des
    phi_sp   = EJ_SPINDLE_R ** ((EJ_OPEN_DES - open_eff) / 100.0)   # equal-% spindle char (NEGATIVE law: const-ṁ PD-pump momentum)
    f_stall  = clamp((phi_m - EJ_STALL_PHI) / (EJ_STALL_REC - EJ_STALL_PHI), 0.0, 1.0) ** EJ_STALL_EXP
    capacity = EJ_SUC_TOT_DES * phi_m * phi_sp * f_stall   # entrainment CAPACITY (kg/h)
    # Phase B: HYDRAULIC-CAPACITY (throat-choke) ceiling on the gravity-head multiplier.  The suction throat
    # chokes -> entrainment cannot rise with head past EJ_HYD_FRAC_MAX·capacity.  At design (L=NLL -> frac=1
    # < EJ_HYD_FRAC_MAX) the cap is inactive -> bit-exact.  On flood (frac->2.0) it caps the recirculation,
    # so the un-pumpable overflow backs up the 322E003 sump instead of self-amplifying the synthesis loop.
    frac_eff = min(max(scrub_level_frac, 0.0), EJ_HYD_FRAC_MAX)  # head multiplier, choke-limited
    m_suc    = capacity * frac_eff                        # actual entrainment = capacity * (capped head)
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


def _ctrl_ipd(c: dict, pv: float, dt: float, cas_sp: float = None) -> float:
    """Velocity-form I-PD tick for an inline DCS controller dict, in ENGINEERING units
    (temperature C / pressure bar a / level % / flow t/h).  Mirrors the controllers.py
    PID math exactly but with the finite-only `_pv_ok` guard (no [-5,105] % clamp) so
    engineering-unit PVs such as 135 C or 99 C are legal.

    c keys: mode {'MAN','AUTO','CAS'}, op, sp, pv, pv1, pv2, Kc, Ti, Td,
            act (+1 REVERSE: op rises when pv < sp | -1 DIRECT: op rises when pv > sp),
            op_lo, op_hi, sp_lo, sp_hi.
    Optional keys (default inert, byte-identical when absent), mirroring controllers.py PID:
            Tf (s, derivative 1st-order filter time; <=0 -> unfiltered legacy 2nd-difference),
            Dz (EU error deadzone half-width; 0 -> no deadzone), dfilt (filtered-derivative state).
    In CAS the remote `cas_sp` (clamped to the sp span) overwrites the local sp.
    Velocity law:  du = act * Kc * [ -(pv - pv1) + I(sp,pv) + D(pv) ]
        I = 0 if |sp-pv| < Dz else (dt/Ti)*(sp - pv)                        (Dz=0 -> always active)
        D = -Td*(pv - 2*pv1 + pv2)/dt                          (Tf<=0, legacy 2nd-difference form)
          = G_k - G_{k-1},  G_k = Tf/(Tf+dt)*G_{k-1} - Td/(Tf+dt)*(pv-pv1)       (Tf>0, filtered)
    Non-finite PV/SP freezes op at the last good value (bumpless hold).  At the design
    seed pv == sp == pv1 == pv2 -> du = 0, so the boot fixed point is preserved bit-exact.
    act=-1,Td=0 reduces to the existing LIC-322501 velocity-PI form.  With Tf=0,Dz=0 the term
    grouping collapses byte-identically to the legacy du expression (IEEE x + (-y) == x - y)."""
    if not _pv_ok(pv, c["sp"]):
        return clamp(c["op"], c["op_lo"], c["op_hi"])              # freeze last-good on bad PV
    if c["mode"] == "CAS" and cas_sp is not None:
        c["sp"] = clamp(cas_sp, c["sp_lo"], c["sp_hi"])           # remote setpoint from master
    pv1 = c["pv1"]; pv2 = c["pv2"]
    if c["mode"] in ("AUTO", "CAS"):
        p = -(pv - pv1)
        err = c["sp"] - pv
        Dz = c.get("Dz", 0.0)
        i = 0.0 if abs(err) < Dz else (dt / c["Ti"]) * err        # Dz=0 -> abs(err)<0 never -> inert
        # Td sentinel decode: official Td = -1 means "derivative disabled"; a negative derivative
        # time is non-physical and, un-guarded, flips the D-term sign (+d2) injecting a wrong-way
        # kick on every transient.  Clamp <0 -> 0 (disabled) so the sentinel is honoured exactly.
        Td = c["Td"]
        if Td < 0.0:
            Td = 0.0
        Tf = c.get("Tf", 0.0)
        if dt <= 0.0:
            d = 0.0
        elif Tf <= 0.0:
            d2 = (pv - 2.0 * pv1 + pv2) / dt
            d = -Td * d2                                          # == -(Td*d2): legacy term, bit-exact
        else:
            g_prev = c.get("dfilt", 0.0)
            g_k = (Tf / (Tf + dt)) * g_prev - (Td / (Tf + dt)) * (pv - pv1)
            d = g_k - g_prev
            c["dfilt"] = g_k
        du = c["act"] * c["Kc"] * (p + i + d)
        c["op"] = clamp(c["op"] + du, c["op_lo"], c["op_hi"])
    c["pv2"] = pv1
    c["pv1"] = pv
    c["pv"]  = pv
    return c["op"]


def _f_flow(T: float, T_cryst: float, dT_mush: float = 5.0) -> float:
    """L3 generic mushy-zone flow factor (Batch 2): 1.0 fully molten, ramps linearly to 0.0 at the
    crystallization solidus.  f = clamp((T - T_cryst)/dT_mush, 0, 1) -> liquidus at T_cryst+dT_mush."""
    return clamp((T - T_cryst) / dT_mush, 0.0, 1.0)


# ----- Bug 2: predictive carbamate-crystallization monitor (Batch 3) -----
#   Ammonium-carbamate liquor freezes to a solid crust before it reaches its solidus.  The model
#   already carries two REACTIVE cut-off anchors (STRIP_BOT_T_CRYST_C urea-melt floor 132.7 C via
#   _f_flow at the stripper drain, and the 60.0 C carbamate anchor at the scrubber overflow) that
#   only bite once flow is ALREADY choking.  This block adds a PREDICTIVE freezing-margin monitor
#   across every carbamate/urea liquid so an alarm is raised BEFORE the crystallization point is
#   reached, per the operability requirement ("alarms should be given if crystallization point is
#   about to occur"), and -- critically -- is emitted to telemetry so it reaches the operator UI.
#   Sourcing Law: only two VERIFIED anchors place the composition-dependent freezing line -- pure
#   ammonium carbamate m.p. 152 C (NIST) at zero free water, and the plant's own validated 60 C
#   carbamate cut-off at the upper recycle water envelope (~40 wt% H2O).  The line between them is
#   the minimum-assumption monotone interpolation (freezing T falls as free water rises, matching
#   the verified CO2/H2O-ratio crystallization direction); no fabricated polynomial or constant.
CARB_MP_PURE_C  = 152.0    # NIST pure ammonium-carbamate melting point (0 wt% free-water anchor)
CARB_W_HI       = 0.40     # upper reliable recycle-liquor free-water mass fraction (60 C anchor)
CARB_T_CRYST_LO = 60.0     # model-validated carbamate freezing anchor at CARB_W_HI
CARB_WARN_DT_C  = 15.0     # freezing margin below which a predictive WARN is raised (approaching)
CARB_MUSH_DT_C  = 5.0      # freezing margin below which a crystallization ALARM is raised (onset)
#   Applicability of the composition freezing line is gated by molar N/C: the two anchors both sit
#   inside the verified reliable envelope (N/C 1.8-2.6).  Outside it the water-only line no longer
#   describes the mixture -- excess ammonia (high N/C) acts as a solvent that DISSOLVES carbamate
#   and depresses freezing (e.g. the NH3-flooded 322F001 ejector discharge, N/C ~ 8), while the
#   CO2-rich side (low N/C) RAISES it.  Gate rather than fabricate a wider correlation (Sourcing Law).
CARB_NC_LO      = 1.8      # verified lower N/C bound of the reliable carbamate freezing envelope
CARB_NC_HI      = 4.0      # applicability cap: above this the liquor is ammonia-solvent-dominated
#                            (well beyond the 2.6 upper envelope) -> no freezing point is asserted


def _carb_t_cryst_water(w_h2o: float) -> float:
    r"""Composition-dependent carbamate freezing temperature (deg C) vs free-water mass fraction.
    Minimum-assumption monotone interpolation between two VERIFIED anchors:
        w = 0          -> 152.0 C  (pure ammonium carbamate m.p., NIST)
        w = CARB_W_HI  ->  60.0 C  (plant-validated carbamate cut-off, upper recycle envelope)
    Linear in w, clamped to [CARB_T_CRYST_LO, CARB_MP_PURE_C]:
        $T_{cryst}(w) = 152.0 + (60.0 - 152.0)\,\dfrac{\mathrm{clamp}(w,\,0,\,0.40)}{0.40}$
    Monotonically decreasing in free water, consistent with the verified CO2/H2O crystallization
    direction (freezing point rises with CO2/H2O mass ratio, i.e. falls with free-water fraction)."""
    w = clamp(w_h2o, 0.0, CARB_W_HI)
    return CARB_MP_PURE_C + (CARB_T_CRYST_LO - CARB_MP_PURE_C) * (w / CARB_W_HI)


def _stream_nc(mol_pct: dict) -> float:
    """Molar N/C atom ratio from a stream's mol %:  N = NH3 + 2*Urea + 3*Biuret,
    C = CO2 + Urea + 2*Biuret.  Returns None if the stream carries no carbon (no carbamate
    phase to freeze).  mol %/mole counts differ only by a common factor, so the ratio is exact."""
    nN = mol_pct.get("NH3", 0.0) + 2.0 * mol_pct.get("Urea", 0.0) + 3.0 * mol_pct.get("Biuret", 0.0)
    nC = mol_pct.get("CO2", 0.0) + mol_pct.get("Urea", 0.0) + 2.0 * mol_pct.get("Biuret", 0.0)
    return (nN / nC) if nC > 1e-9 else None


def _cryst_assess(stream: dict, T_cryst: float = None) -> dict:
    """Predictive crystallization assessment for ONE carbamate/urea liquid stream (as built by
    make_stream).  Reads the stream's own derived mass %, computes the freezing margin and a
    three-tier state.  T_cryst None -> derive the freezing line from the stream's free-water
    content via _carb_t_cryst_water; else use the caller's equipment anchor (e.g. the 132.7 C
    urea-melt floor at the stripper bottom).
        margin = T - T_cryst ;  ALARM if margin < CARB_MUSH_DT_C, WARN if < CARB_WARN_DT_C, else OK.

    The composition line (T_cryst None) is only physically valid inside the verified carbamate
    envelope, so its applicability is gated by molar N/C:
      * N/C > CARB_NC_HI  -> liquor is ammonia-solvent-dominated (e.g. the NH3-flooded 322F001
        ejector discharge, N/C ~ 8); carbamate stays dissolved, no freezing point is asserted ->
        state 'OOR' (out of range), EXCLUDED from the WARN/ALARM aggregation.
      * N/C < CARB_NC_LO  -> CO2-rich side, where the water-only line UNDER-predicts freezing
        (non-conservative); the state is floored at WARN so a possibly-freezing stream is never
        reported a false OK.
    An explicit T_cryst (a distinct solid phase, e.g. the urea-melt floor) is always assessed and
    is NOT N/C-gated.  Any non-finite core input -> 'BAD' (a bad measurement never reads OK)."""
    T   = stream.get("T_C")
    mp  = stream.get("mass_pct", {})
    co2 = mp.get("CO2", 0.0)
    h2o = mp.get("H2O", 0.0)
    w   = h2o / 100.0
    nc  = _stream_nc(stream.get("mol_pct", {}))
    nc_r = (round(nc, 2) if (nc is not None and math.isfinite(nc)) else None)
    explicit = T_cryst is not None
    if not _pv_ok(T, w) or (explicit and not _pv_ok(T_cryst)):
        return {"T_cryst": None, "margin": None, "co2_h2o": None, "h2o_wt": None,
                "nc": nc_r, "state": "BAD"}
    if not explicit:
        if nc is None or not math.isfinite(nc) or nc > CARB_NC_HI:
            return {"T_cryst": None, "margin": None, "co2_h2o": None,
                    "h2o_wt": round(h2o, 2), "nc": nc_r, "state": "OOR"}
        T_cryst = _carb_t_cryst_water(w)
    margin  = T - T_cryst
    co2_h2o = (co2 / h2o) if h2o > 1e-9 else None
    state   = "ALARM" if margin < CARB_MUSH_DT_C else ("WARN" if margin < CARB_WARN_DT_C else "OK")
    if (not explicit) and (nc is not None) and nc < CARB_NC_LO and state == "OK":
        state = "WARN"    # CO2-rich: water-only line under-predicts -> never a false OK
    return {"T_cryst": round(T_cryst, 1), "margin": round(margin, 1),
            "co2_h2o": (round(co2_h2o, 3) if co2_h2o is not None else None),
            "h2o_wt": round(h2o, 2), "nc": nc_r, "state": state}


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
    # (flood) branch it stays the RAW negative load so η_T keeps choking and the split keeps closing
    # (unstripped volatiles held in the BOTTOMS -- they exit the loop via LV-322501, not overhead).
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
    # the raw load — so η_T stays choked: a flood gives HOT but UNSTRIPPED bottoms, and the unstripped
    # volatiles LEAVE WITH THE BOTTOMS (mod × g_T split cut below) — classic NH3 slip to the LP section.
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
    # Feed-load (flood) choke g_T<1 CUTS the split -- steam-limited stripping leaves the volatiles in
    # the BOTTOMS (NH3 slip to LP via LV-322501), it does NOT lift them overhead.  min(g_T,1) keeps the
    # feed-lean branch (g_T>1, already rewarded through eta_T) and the design point (g_T=1) bit-exact.
    mod = clamp(eta_T_steam * eta_co2 * eta_P, 0.0, 1.12) * min(g_T, 1.0)
    slip = max(1.0 - g_NC, 0.0) + max(1.0 - g_HC, 0.0)   # composition (N/C, H/C) breakthrough only
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
        "T_top": min(STRIP_T_TOPGAS_DES_C + 0.6 * dTs
                     + STRIP_T_TOP_LOAD_K * dT_bot + dT_strip, T_steam_C),  # TT-322013: steam-heat + feed-load (atten.) + G/L strip-cool (full); ≤ steam sat
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
# Calibrated vapour/liquid split fraction theta_i = OGd_i/(OVd_i+OGd_i): partitions reactor product
# molar flow to liquid overflow (->322E001) vs off-gas (->322E003).  Derived from the published design
# vectors so the design point is bit-exact; guarded for pure-overflow / pure-off-gas species.
REACT_THETA_OG = {
    k: (REACT_OFFGAS_DES.get(k, 0.0)
        / (REACT_OVERFLOW_DES.get(k, 0.0) + REACT_OFFGAS_DES.get(k, 0.0))
        if (REACT_OVERFLOW_DES.get(k, 0.0) + REACT_OFFGAS_DES.get(k, 0.0)) > 1e-12
        else (1.0 if REACT_OFFGAS_DES.get(k, 0.0) > 0.0 else 0.0))
    for k in MW_COMP}
# ISSUE-c incremental mass-conservation references (kg/h), captured on the SETTLED live design loop
# by _pin_hpcc_ua (mirrors the HPCC_UA pin).  None -> reactor overflow rescale is INACTIVE (warm-up
# pass + any pre-pin call), so the references themselves are taken from the un-rescaled design point.
REACT_MASS_DES = None            # (m_feed_des, m_overflow_des, m_offgas_des) kg/h
# Option-A conserving-rebuild pins (captured by _pin_hpcc_ua at the MAN design seed; None -> rebuild
# falls back to zero tear / kinetics-module anchors on warm-up + pre-pin calls).
REACT_TEAR_DES   = None   # explicit pinned recycle-tear vector (kmol/h): feed_des - implied_feed
REACT_L_FEED_DES = None   # boot-pinned design liquid-NH3 driver L_feed (AT-322701 shift anchor)
REACT_W_FEED_DES = None   # boot-pinned design water driver W_feed
REACT_X_DES      = None   # boot-pinned design per-pass conversion X_conv (deficit-slip anchor)
EJ_MOTIVE_DES_LIVE = None        # settled live design motive NH3 (kg/h), pinned in _pin_hpcc_ua ->
                                 #   phi_m = motive/EJ_MOTIVE_DES_LIVE == 1.0 bit-exact at design steady
                                 #   state (so the 322E003 sump holdup ODE is a STATIONARY fixed point).
                                 #   None -> fall back to const EJ_MOTIVE_NH3_DES (warm-up/pre-pin calls).
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
REACT_LEVEL_DES_M   = REACT_LEVEL_NLL_PCT / 100.0 * REACT_LIQ_H_M  # 20.0 m design liquid level (outlet-line head ref)
# --- LT-322504 NARROW-BAND transmitter geometry (datasheet UD-AU-322-EC-0006, nozzle N7 = "LT 322504")
# N7 is a stilling-well / protection-pipe level transmitter at the reactor TOP, NOT a full-height gauge:
#   * datasheet p14 "1000 TO OVERFLOW PIPE" -> protection-pipe bottom (= measuring-range TOP tap / URV)
#     sits 1.0 m above the overflow weir;  p6 "1500" -> measuring SPAN = 1.5 m.
# So the 0->100 % indication maps a 1.5 m band whose TOP tap (URV, 100 %) is 1.0 m above the overflow line.
# The liquid HOLDUP + hydraulics stay on the full physical head (react_level_pct, the 25 m column) — ONLY the
# DISPLAYED transmitter reading is re-scoped to this real narrow band, which SATURATES (0 %/100 %) once the
# surface leaves its range (real instrument behavior).  The reading maps the PHYSICAL head directly through
# the fixed N7 geometry — LT-322504 tracks the 322R001 mass balance and nothing else (2026-07-03 order: no
# coupling/pinning to plant load).  At the design head 20.0 m it reads exactly NLL 80 %; see DISPLAY block.
REACT_LT_SPAN_M       = 1.5      # N7 measuring span, m (datasheet p6 "1500")
REACT_LT_ABOVE_OVF_M  = 1.0      # URV (100 %) elevation above the overflow line, m (datasheet p14 "1000")
#   URV = LRV + span = 20.3 m;  overflow line = URV - 1.0 = 19.3 m -> design level sits 0.7 m above the weir.
#   Span 1.5 m vs the old 25 m full-height map -> ~16.7x more sensitive: HV-322605 head moves now read PROMPT.
REACT_PHI_FWD_FLOOR = 0.25  # Fix-4: residual letdown floor on φ_fwd in the OUTLET reference (see line ~1619).
#   Bottom take-off drains by loop-pressure/gravity head even when forward circulation stops, so the outlet
#   reference is m_dot_des·max(φ_fwd, FLOOR), NOT m_dot_des·φ_fwd.  At runtime design φ_fwd≈1.10 ≫ FLOOR so the
#   max() picks φ_fwd and it cancels m_in's φ_fwd -> bit-exact L_des pin.  On a CO2-cut pump trip φ_fwd->0 but
#   the FLOOR keeps m_out>0 -> the vessel drains (φ_fwd-coupled m_out would collapse to 0 and freeze — Bug #4).
#   FLOOR engages only below motive ≈ sqrt(FLOOR)·EJ_MOTIVE_NH3_DES ≈ 20.4 t/h (~half design = trip/deep turndown).
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
# --- Fix-4: ejector forward-carbamate coupling 322E003 -> 322F001 -> 322E002 -> 322R001 ---------
REACT_FWD_GAIN     = 1.0         # G_fwd: fraction of the TRANSIENT (washed-out) spindle-attributable draw
                                 # pumped forward through the HPCC into the reactor holdup as extra carbamate
                                 # make.  Driver = ṁ_suc·(1 − 1/φ_sp(θ)) (≡0 at the design valve θ=74, φ_sp=1);
                                 # the high-pass of it isolates the valve-move PULSE and dies to 0 at any steady
                                 # θ -> mass-conservative (no sustained source).  >0 closing, <0 opening.
REACT_FWD_TAU_MIN  = 8.0         # τ_fwd: washout time constant (min) ≈ 322E003 sump-drain redistribution time;
                                 # sets how long the LT-322504 forward-carbamate swell persists before relaxing.
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
# -- SUPERSEDED off-gas datasheet (img1 MOL%, 64.78 kmol/h): does NOT route 100% of inerts -> vent and
#   leaves the scrubber node open.  Retained as provenance + to keep audit imports resolvable; NOT live. --
SCRUB_OFFGAS_MOLPCT  = {"N2": 68.81, "O2": 11.39, "NH3": 8.26, "CH4": 5.93,       # superseded img1 MOL%
                        "H2": 3.14, "CO2": 2.22, "H2O": 0.26}
SCRUB_OFFGAS_MOL_DES = 64.78     # kmol/h OLD design off-gas total (322E003 -> 322C001) -- superseded
# -- RECONCILED off-gas (Path B, Option 1): 100% of inerts (N2,O2,CH4,H2) routed to vent; NH3/CO2 vent =
#   reactor-offgas IN minus heavy-overflow recovery (forced reactant slip 156.95 kmol/h); H2O vent = 0
#   (ov_CO2 at feasible max).  Closes the 322E003 component balance to machine zero (GAP=0). --
_SCRUB_OFFGAS_RECON = {"CO2": 62.18213955, "CH4": 3.86000000, "H2": 2.02000000, "N2": 44.53000000,
                       "NH3": 94.76367511, "O2": 7.42000000, "H2O": 0.0}
SCRUB_OFFGAS_KMOLH_DES = {k: _SCRUB_OFFGAS_RECON.get(k, 0.0) for k in MW_COMP}   # span all 9 comps (Urea/Biuret=0)
# Overflow design vector IS the 322F001 ejector suction (single source of truth -> DRY, bit-identical):
SCRUB_OVERFLOW_KMOLH_DES = {k: EJ_SUCTION_KGH[k] / MW_COMP[k] for k in MW_COMP}   # Σ ≈ 2519.4 kmol/h
# --- 322E003 sump liquid inventory (Option 3: TRUE dynamic state, not a display lag) ---
#   dM_scrub/dt = ṁ_cond,in − ṁ_entrain ;  ṁ_cond,in = Σ overflow_kmolh·MWᵢ (carbamate make from
#   condensation/absorption), ṁ_entrain = ej["suction_kgh"] (actual non-linear-curve entrainment).
#   At design cond == entrain == EJ_SUC_TOT_DES -> dM=0, level == NLL (bit-exact, indep. of τ).
#   If the ejector STALLS (C(phi_m)->0) entrainment collapses while condensation continues -> M rises.
SCRUB_LEVEL_NLL_PCT  = 50.0      # %, 322E003 sump design normal liquid level
SCRUB_TAU_HOLDUP_MIN = 4.0       # min, sump residence time at design throughput (sets holdup scale)
SCRUB_HOLDUP_NLL_KG  = EJ_SUC_TOT_DES * SCRUB_TAU_HOLDUP_MIN / 60.0   # kg liquid at NLL (≈3837 kg)
SCRUB_HOLDUP_MAX_KG  = SCRUB_HOLDUP_NLL_KG * 100.0 / SCRUB_LEVEL_NLL_PCT  # kg at 100% (sump full)
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
SCRUB_HV604_RANGE    = 50.0      # equal-% inherent rangeability R (datasheet char = EQUAL %): K_v(h)=K_vs·R^(h-1)
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
# §7.6 P5-A provenance: the two TAU_S below are CALIBRATED instrument-response lags fit to CCW step
#   data, NOT hydraulically derived -- FIC_329409_TAU_S = FV-329409 actuator stroke + FT filter (fast
#   circ pump, ~3 s); TIC_329005_TAU_S = tempered-water thermal mass + RTD lag (~25 s). Both are inner
#   loops subordinate to the feed dead time (FEED_TD_S), so they cannot shift the synthesis-loop FOPTD
#   fingerprint [tau 2884..4055 s, t_d<=572 s]; that invariant is regression-asserted in
#   test_foptd_fingerprint.py, which must pass after ANY change to these constants.
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
HPCC_NC_DES_LIVE    = None       # design HPCC carbamate-MELT N/C (NH3/CO2) -- AUTO-CAPTURED at boot from
#   the MAN runtime design seed (the stable Cluster-2023 fixed point, ~3.12324).  This is the actual
#   combined-melt N/C the synthesis loop settles at -- DISTINCT from the controlled reactor-FEED N/C
#   reactor.L0_DES (3.07296): the HPCC melt is NH3-richer than the reactor feed it produces because ALL
#   fresh NH3 enters as ejector motive (loads the melt NH3 numerator) while the melt water is entrainment-
#   pinned to W0 (phi_m==1).  bubble_p_322e002 anchors fN HERE so P_bub == HPCC_P_DES_BARA (144.2 bar a,
#   datasheet) BIT-EXACT at the live design operating point (residual -> 0).  Falls back to reactor.L0_DES
#   when unset (pre-boot).  [Was anchored to L0_DES -> read +1.3 bar HIGH (145.5, above the 144.2 PT
#   ceiling) at the live melt N/C of 3.12324; the L0 anchor wrongly assumed melt N/C == reactor-feed N/C.]
# (2) PT-329201 reverse heat->pressure: the synthesis-loop top pressure is a DYNAMIC state.  CCW
#     flow sets the off-gas condensation capacity; when capacity < vent demand the uncondensed
#     vapour accumulates and lifts PT-329201.  rho_cond = (m_ccw/m_ccw_des)/(s*nu), nu = PT/PT_des.
#     First-order accumulation:  tau dPT/dt = PT_fwd + K_def*max(1-rho_cond,0)*PT_des - PT.
SYN_P_DES_BARA      = SCRUB_OVERFLOW_P_BARA   # 140.7 bar a, PT-329201 design (322E003 overflow line)
SYN_P_DEFICIT_GAIN  = 0.30       # bar/bar, PT lift per unit condensation deficit (1-rho_cond)  -- calib
SYN_P_VENT_GAIN     = 0.30       # bar/bar, PT lift per unit HV-322604 vent deficit (1-vent_frac) -- calib
SYN_P_TAU_MIN       = 4.0        # min, loop-pressure accumulation time constant (vapour inventory, warm op-pt)
# Cold-start loop-fill pressurisation time constant.  SOURCED, NOT fabricated: FOPTD fit of 9 exact field
# points of PT-329201 (3.6.2025 synthesis startup trend) -> tau = 3469.5 s = 57.8 min +/- 585.9
# (dcs_anchor_dynamics_2025-06-03.md Section 1.2; this fit defines the Section 6.4 band [2884,4055] s).
# Used ONLY to STRETCH the effective accumulation tau when the HP loop is empty (m_loop_frac -> 0); the
# emergent FOPTD tau of the pressurisation must reproduce the field value.  This is NOT a hard lag on the
# pressure state: tau_eff blends to SYN_P_TAU_MIN as inventory fills, so at design (m_loop_frac == 1) the
# warm op-pt constant is recovered EXACTLY and the steady-state hold stays bit-exact (driving error == 0).
SYN_P_TAU_FILL_MIN  = 57.8       # min, cold-start (empty-loop) pressurisation tau (06-03 Section 1.2 FOPTD)
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
SCRUB_COND_CHOKE_MIN = 0.30      # —, residual condensation-duty fraction at a FULLY choked (L-329501=100%)
#   sump.  Phase-B-coupled CHOKE derate: a flooding 322E003 sump (LT-329501 above NLL) progressively floods
#   the shell-side condensation surface, constricting the carbamate-condensation duty Q_scrubber.  The
#   condensation-availability factor χ_choke ramps LINEARLY from 1.0 at NLL (50 %) down to this floor at
#   100 %: χ_choke = 1 − (1−SCRUB_COND_CHOKE_MIN)·max(L−L_NLL,0)/(100−L_NLL).  At/below NLL χ_choke ≡ 1 ->
#   q_ccw unchanged -> TDY-329125 + every TT pin stay bit-exact at design.  Above NLL it cuts q_ccw, so the
#   CCW-rise indicator TDY-329125 FALLS (condensation constricted) — the physically-correct choke signature.
SCRUB_COND_SPINDLE_GAIN = 0.25   # —, carbamate-condensation duty sensitivity to the 322F001 ejector-spindle
#   intensity (HV-322602).  The motive jet sets how vigorously the off-gas is drawn through the bottom
#   condensation zone: CLOSING HV-322602 raises phi_sp>1 (stronger jet, deeper suction) -> more off-gas is
#   condensed into carbamate per unit time -> Q_scrubber RISES; opening (phi_sp<1) lowers it.  Spindle-duty
#   factor χ_sp = 1 + SCRUB_COND_SPINDLE_GAIN·(1 − 1/phi_sp), the SAME (1−1/phi_sp) spindle driver as the
#   322R001 forward-carbamate domino (Rev Δ#11).  At θ_des phi_sp≡1 -> χ_sp≡1 -> q_ccw unscaled -> TT-322002
#   (178.8) + TDY-329125 (15.0) hold bit-exact; off-design it couples HV-322602 into the FULL 322E003 thermo
#   (t_overflow_cond -> TT-322002, t_ccw_out/dT_ccw -> TT/TDY-329125).  Two-sided, persistent, phi_sp-keyed
#   so it is independent of the steady sump level (which sits below NLL at θ_des) — pin holds by construction.


def bubble_p_322e002(T_c: float, L: float, W: float) -> float:
    """322E002 HPCC carbamate-melt bubble-point synthesis pressure (bar a) = f(T, N/C=L, H/C=W).
    Reduced Clausius-Clapeyron T-slope x separable N/C, H/C modifiers, anchored bit-exact at the
    DESIGN MELT composition:  bubble_p_322e002(HPCC_T_PROD_DES_C, HPCC_NC_DES_LIVE, reactor.W0_DES)
    == HPCC_P_DES_BARA.  The fN anchor is the design HPCC-MELT N/C (HPCC_NC_DES_LIVE ~= 3.12324, auto-
    captured at boot), NOT the controlled reactor-FEED N/C reactor.L0_DES (3.07296): the live combined
    melt is NH3-richer than the reactor feed (all fresh NH3 enters as ejector motive).  fW keeps the
    reactor.W0_DES anchor because the melt H/C settles at W0 exactly (entrainment phi_m==1).
    Monotone: dP/dT>0, dP/dL>0 (free NH3 volatility), dP/dW<0 (water dilution)."""
    _nc0 = HPCC_NC_DES_LIVE if HPCC_NC_DES_LIVE is not None else reactor.L0_DES   # design melt N/C anchor
    cc = math.exp((HPCC_BUB_DHVAP_JMOL / reactor.R_GAS)
                  * (1.0 / _HPCC_BUB_T0_K - 1.0 / (T_c + 273.15)))
    fN = 1.0 + HPCC_BUB_KN * (L - _nc0)               # free-NH3 (N/C) volatility lift (anchor = design melt N/C)
    fW = 1.0 + HPCC_BUB_KW * (W - reactor.W0_DES)      # water (H/C) dilution
    return HPCC_P_DES_BARA * cc * max(fN, 0.0) * max(fW, 0.0)


HPCC_UA = None       # shell conductance (kJ/h.K); back-calculated at module load (design-pinned)
_STEAM_READY = False # gate: step_steam stays OFF until valve coeffs are pinned (boot-pin phase 2)

# ---- Option-1 disturbance gate (over-temp runaway fix) ------------------------------------------
#   The HPCC shell-temp (t_shell<-P_LP) and product-temp (T_prod<-T_adb) off-design couplings are
#   EXACTLY their design value at the published operating point, but the coupled loops
#       P_LP^ -> t_shell^ -> T_prod^ -> reactor^ -> duty^ -> m_hpcc^ -> P_LP^      (steam loop)
#       X_conv^ -> T_adb^ -> T_prod^ -> node0^ -> X_conv^                          (loop-tear)
#   have gain > 1, so the fresh-State() seed (NOT the dynamic fixed point) self-excites a thermal
#   runaway (t_shell 220 C, node0 253 C) with NO operator action.  Gate BOTH coupling deltas by a
#   genuine-disturbance factor g in [0,1]: g==0 when every EXOGENOUS operator/feed handle sits at its
#   design value (seed) -> couplings pinned to design -> bit-exact HMB and no self-excitation; g->1
#   the instant any handle moves -> full live off-design response (V-trough fidelity preserved).
GATE_DEADBAND       = 0.002   # rel. dead-band: |dev| below this == "at design" (numerical noise floor)
GATE_RAMP           = 0.010   # rel. span over which g ramps 0->1 above the dead-band
RATIO_SP_DES        = 2.0231315310702604   # design molar N/C setpoint (seed) == RATIO_PV_DES -- exogenous N/C disturbance handle
HIC602_DES_PCT      = 74.0    # design HV-322602 ejector-spindle opening (seed)
STEAM_VALVE_DES_PCT = 50.0    # design MP-supply / MP->LP let-down valve opening (seed)


def _disturbance_gate(s) -> float:
    """Genuine-disturbance factor g in [0,1] from the EXOGENOUS operator/feed boundary vector.
    Each handle is seeded EXACTLY at design, so g==0 at the published operating point (bit-exact);
    g->1 as soon as an operator/feed move pushes any handle off design (live off-design response)."""
    dev = max(
        abs(s.F_CO2_th                - CO2_DES_KGH / 1000.0)  / (CO2_DES_KGH / 1000.0),
        abs(s.ratio_SP                - RATIO_SP_DES)          / RATIO_SP_DES,
        abs(s.HIC_322602              - HIC602_DES_PCT)        / HIC602_DES_PCT,
        abs(s.HIC_322605              - REACT_HIC605_DES_PCT)  / REACT_HIC605_DES_PCT,
        abs(s.steam.valve_supply_pct  - STEAM_VALVE_DES_PCT)   / STEAM_VALVE_DES_PCT,
    )   # NB: PV-329205B (valve_letdown_pct) is now a split-range CONTROLLED var (design-shut, not an
        #     operator handle) -> excluded from the exogenous disturbance vector.
    return clamp((dev - GATE_DEADBAND) / GATE_RAMP, 0.0, 1.0)


def hpcc_322e002(gas_feed: dict, liq_feed: dict, t_shell: float = HPCC_STEAM_TSAT_C,
                 gate: float = 1.0) -> dict:
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
        T_prod_live = t_shell + (T_adb - t_shell) \
                      * math.exp(-HPCC_UA / max(m_dot * HPCC_CP_GAS, 1e-9))
        # Option-1 gate the off-design EXCESS above the design pin: gate==0 (no operator/feed
        #   disturbance) -> T_prod==HPCC_T_PROD_DES_C bit-exact (kills the loop-tear self-excitation);
        #   gate->1 (genuine disturbance) -> full live NTU quench (TT-322010 V-trough preserved).
        T_prod = HPCC_T_PROD_DES_C + gate * (T_prod_live - HPCC_T_PROD_DES_C)
    # LP steam actually RAISED on the shell = process duty MINUS the extra sensible heat carried out in the
    #   product above the design pin.  Energy split of the carbamate/sens release: boiled into LP steam +
    #   retained as product enthalpy when T_prod exceeds HPCC_T_PROD_DES_C (rising t_shell -> rising P_LP).
    #   At design T_prod==HPCC_T_PROD_DES_C -> q_steam_kw==duty_kw bit-exact; this is the shell back-pressure
    #   that stabilizes the LP header (see step_sim steam handshake).  Floor at 0 (full-quench limit).
    q_steam_kw = max(duty_kw - m_dot * HPCC_CP_GAS * (T_prod - HPCC_T_PROD_DES_C) / 3600.0, 0.0)
    # bubble-point synthesis pressure of the combined carbamate MELT (N/C, H/C molar); replaces the
    # pinned HPCC_P_DES_BARA.  At design this melt's N/C == HPCC_NC_DES_LIVE (~3.12324, the bubble_p fN
    #   anchor -- NH3-richer than reactor-feed L0_DES) and H/C == reactor.W0_DES (entrainment phi_m==1)
    #   -> P=144.2 exact.  The N/C, H/C ratios are NH3/CO2 and H2O/CO2: as a CO2-feed cut drives CO2 -> 0
    #   they diverge, so on the transient (CO2 in the (1e-9, small] band before it crosses the cliff) the
    #   bubble pressure used to IMPULSE to ~330 bar a for one tick -- an unphysical N/C->inf artifact, not
    #   a real synthesis pressure.  Clamp both ratios to a physical band about design (0.5x .. 2.0x of the
    #   reactor-feed refs) so the published PI-322E002 moves only within a bounded, physical range; the
    #   design melt N/C (3.12324) and H/C (W0) both sit inside the band (untouched) -> P = 144.2 bit-exact.
    _co2   = feed.get("CO2", 0.0)
    L_hpcc = (clamp(feed.get("NH3", 0.0) / _co2, 0.5 * reactor.L0_DES, 2.0 * reactor.L0_DES)
              if _co2 > 1e-9 else reactor.L0_DES)
    W_hpcc = (clamp(feed.get("H2O", 0.0) / _co2, 0.5 * reactor.W0_DES, 2.0 * reactor.W0_DES)
              if _co2 > 1e-9 else reactor.W0_DES)
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
        "duty_kw": duty_kw, "steam_kgh": steam_kgh, "q_steam_kw": q_steam_kw,
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
HPCC_LIQ_DES_LIVE  = None        # ISSUE-c/e: SETTLED live design liquid make (pinned in _pin_hpcc_ua);
#   the synthetic HPCC_LIQ_DES_KGH above understates it ~2 %, so normalising phi_in on it left the
#   level winding past NLL (drift +0.33 %/2min, never steady).  The live ref makes NLL a true fixed pt.
# HPCC_UA (shell conductance, kJ/h.K) is design-pinned AFTER step_sim is defined, by a one-shot
# settle warm-up on the LIVE loop (see _pin_hpcc_ua() near the module tail).  The synthetic single-
# call construction above understates the tube throughput by ~2 % (its stripper sees CO2_DES_KGH
# directly, not the SETTLED reactor-overflow recycle tear), and with the steep adiabatic-exotherm
# spike (T_adb_des ~600 C) that 2 % m_dot error displaces the NTU-pinned outlet by ~0.4 C.  Pinning
# on the settled live design state instead anchors TT-322010 to exactly 170.0 C.  HPCC_UA stays None
# until that pass runs (None => hpcc_322e002 holds the 170.0 C design pin every tick).


def _react_delta(fc: dict, xi_urea: float, xi_biu: float) -> dict:
    """out_total_i = feed_corrected_i + sum_r nu_{i,r}*xi_r for the urea couple + biuret reactions.
      Urea couple  CO2 + 2 NH3 -> Urea + H2O   (xi_urea): dN=dC=0, dn_tot=-1.
      Biuret       2 Urea -> Biuret + NH3       (xi_biu) : dn_tot= 0.   Atoms exactly conserved."""
    out = {k: fc.get(k, 0.0) for k in MW_COMP}
    out["CO2"]    -= xi_urea
    out["NH3"]    -= 2.0 * xi_urea
    out["Urea"]   += xi_urea
    out["H2O"]    += xi_urea
    out["Urea"]   -= 2.0 * xi_biu
    out["Biuret"] += xi_biu
    out["NH3"]    += xi_biu
    return out


def react_322r001(hpcc: dict, co2_feed_th: float, hic_322605_pct: float,
                  L_drive: float = None, W_drive: float = None,
                  T_overflow_c: float = REACT_OVERFLOW_T_C) -> dict:
    """322R001 HP urea reactor -- rigorous component mole balance with exact atom conservation.
      feed_corrected_i = feed_i - TEAR_DES_i * s          (explicit pinned recycle tear)
      out_total_i      = feed_corrected_i + sum_r nu_{i,r} * xi_r   (urea couple + biuret)
      overflow_i = out_total_i * (1 - theta_i);  offgas_i = out_total_i * theta_i
    Conservative composition shifts (AT-322701 NH3 partition; conversion-deficit slip) move species
    BETWEEN overflow and off-gas only -> per-species totals (hence atoms + mass) invariant.  Bit-exact
    at design: xi_live == xi_pin and feed == feed_des -> out_total == OVd + OGd exactly.  closure_resid
    is a true conservation diagnostic (~0), reported only -- never injected into any stream.
    NOTE: the phi (HIC-322605) -> overflow split coupling of the prior pinned model is intentionally
    NOT reintroduced here (it was part of the mass-creating split-fraction defect); a conservative
    theta(phi) modulation is DEFERRED to Phase 3."""
    s   = co2_feed_th / (CO2_DES_KGH / 1000.0)
    phi = hic_322605_pct / 100.0
    phi_des = REACT_HIC605_DES_PCT / 100.0
    feed = hpcc["feed_kmolh"]
    # kinetics module supplies ONLY the scalar extent + conversion/holdup state; its internal overflow
    # mutation is discarded (throwaway design vector passed in).
    xi_urea, _ov_discard, X_conv, L_feed, W_feed = reactor.react_couple(
        feed, dict(REACT_OVERFLOW_DES), REACT_XI_UREA_DES * s, T_overflow_c,
        L_override=L_drive, W_override=W_drive)
    xi_biu = REACT_XI_BIU_DES * s
    # feed corrected for the pinned recycle tear (documented torn quantity, main.py:995):
    s_tear = s if REACT_TEAR_DES is not None else 0.0
    fc = {k: feed.get(k, 0.0) - (REACT_TEAR_DES.get(k, 0.0) if REACT_TEAR_DES else 0.0) * s_tear
          for k in MW_COMP}
    # extent feasibility clamps (non-binding at/near design -> bit-exact; bind under reagent starvation)
    xi_urea = max(min(xi_urea, fc.get("CO2", 0.0), 0.5 * fc.get("NH3", 0.0)), 0.0)
    xi_biu  = max(min(xi_biu, 0.5 * (fc.get("Urea", 0.0) + xi_urea)), 0.0)
    out_total = _react_delta(fc, xi_urea, xi_biu)
    overflow = {k: out_total[k] * (1.0 - REACT_THETA_OG[k]) for k in MW_COMP}
    offgas   = {k: out_total[k] * REACT_THETA_OG[k]         for k in MW_COMP}
    # AT-322701 excess-NH3 partition (CONSERVATIVE: NH3 overflow<->off-gas only; total N & C held).
    # Anchored to boot-pinned design L_feed (NOT reactor.L0_DES) so H-1 seed creep cannot unpin it.
    L_ref = REACT_L_FEED_DES if REACT_L_FEED_DES is not None else reactor.L0_DES
    nh3_shift = REACT_NC_OVERFLOW_GAIN * (L_feed / L_ref - 1.0) * REACT_OVERFLOW_DES["NH3"] * s
    nh3_shift = max(min(nh3_shift, 0.9 * offgas.get("NH3", 0.0)), -0.5 * overflow.get("NH3", 0.0))
    overflow["NH3"] = overflow.get("NH3", 0.0) + nh3_shift   # NH3-rich liquid effluent at high N/C
    offgas["NH3"]   = offgas.get("NH3", 0.0)   - nh3_shift   # conserved: total NH3 unchanged
    # conversion-deficit slip (CONSERVATIVE re-partition overflow->off-gas; total per-species held).
    # delta_X is the fractional per-pass conversion shortfall below design (clamped >= 0): un-converted
    # NH3 + CO2 slip to the off-gas instead of the liquid overflow.  Replaces the prior mass-CREATING
    # amplifier (offgas *= 1+g).  Anchored to boot-pinned design X so H-1 creep cannot unpin it.  At/
    # above design delta_X = 0 -> no shift (bit-exact).  Dalton partials p_i = y_i*P_offgas tracked off
    # the re-partitioned off-gas; dimensionless loop forcing Pi = kappa*delta_X (built in step_sim).
    X_ref = REACT_X_DES if REACT_X_DES is not None else reactor.X_DES_RAW
    delta_X = max(1.0 - X_conv / X_ref, 0.0)
    g = REACT_OFFGAS_DEFICIT_GAIN * delta_X
    for k in ("NH3", "CO2"):
        sh = min(g * offgas.get(k, 0.0), overflow.get(k, 0.0))
        offgas[k]   = offgas.get(k, 0.0)   + sh
        overflow[k] = overflow.get(k, 0.0) - sh
    og_tot   = sum(offgas.values())
    p_nh3_og = (offgas.get("NH3", 0.0) / og_tot) * REACT_OFFGAS_P_BARA if og_tot > 0.0 else 0.0
    p_co2_og = (offgas.get("CO2", 0.0) / og_tot) * REACT_OFFGAS_P_BARA if og_tot > 0.0 else 0.0
    # true conservation diagnostic: feed_corrected - urea-couple dn - products ~= 0 (machine zero).
    # reported ONLY -- never injected into any stream.
    closure_resid = (sum(fc.values()) - xi_urea
                     - (sum(overflow.values()) + sum(offgas.values())))
    tear_mass = sum((REACT_TEAR_DES.get(k, 0.0) if REACT_TEAR_DES else 0.0) * MW_COMP[k]
                    for k in MW_COMP) * s_tear
    return {"overflow_kmolh": overflow, "offgas_kmolh": offgas, "feed_kmolh": feed,
            "feed_corrected_kmolh": fc, "tear_mass_kgh": tear_mass,
            "xi_urea": xi_urea, "xi_biu": xi_biu, "closure_resid": closure_resid,
            "T_overflow": REACT_OVERFLOW_T_C, "T_offgas": REACT_OFFGAS_T_C,
            "P_bara": REACT_P_BARA, "P_offgas": REACT_OFFGAS_P_BARA,
            "phi": phi, "phi_des": phi_des, "co2_scale": s,
            "X_conv": X_conv, "L_feed": L_feed, "W_feed": W_feed,
            "delta_X": delta_X, "p_nh3_og": p_nh3_og, "p_co2_og": p_co2_og}


def scrub_322e003(offgas_feed: dict, co2_scale: float, t_ccw_in: float,
                  m_ccw_kgh: float, vent_ratio: float = 1.0, nc_act: float = None,
                  hic604_pct: float = None,
                  liq_carry_kmolh: dict = None, t_carry_c: float = None,
                  choke_level_pct: float = None, spindle_phi: float = 1.0) -> dict:
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
    # --- Phase A: reactor OFF-GAS-LINE LIQUID CARRYOVER (flood entrainment) -------------------------
    # On reactor flood (holdup at PHYSICAL vessel-full; LT-322504 narrow-band already pegged 100%) the
    # un-passable melt spills the off-gas line into 322E003 as
    # entrained liquid of reactor-OVERFLOW composition.  It joins the tube feed AND leaves with the bottom
    # overflow (-> 322F001 ejector suction -> 322E003 sump inventory ODE), so closure stays balanced
    # (feed += c, overflow += c -> net 0).  Below the flood lip liq_carry_kmolh is None -> every term is
    # identically unchanged -> pinned off-gas/overflow HMB + all TT pins remain bit-exact at design.
    carry_mass_kgh = 0.0
    if liq_carry_kmolh:
        for k in MW_COMP:
            c = liq_carry_kmolh.get(k, 0.0)
            feed[k]        += c                                               # enters the combined tube feed
            overflow[k]    += c                                               # leaves with the bottom liquid
            carry_mass_kgh += c * MW_COMP[k]
    closure_resid = sum(feed.values()) - sum(offgas.values()) - sum(overflow.values())
    co2_abs   = max(offgas_feed.get("CO2", 0.0) - offgas["CO2"], 0.0)          # kmol/h gas->carbamate (now wash-live)
    q_carb_kw = co2_abs * 1000.0 * SCRUB_DH_CARB_KJMOL / 3600.0                # full exotherm (diag)
    q_ccw_kw  = SCRUB_Q_CCW_DES_KW * s * vent_ratio                            # Q_scrubber: carbamate-cond. duty (s × synthesis-vent load PT-329201)
    # --- HV-322602 ejector-spindle CONDENSATION-INTENSITY coupling (TT-322002 / TDY-329125 / 322E003 thermo) ---
    # The 322F001 motive jet sets how vigorously the off-gas is drawn through the bottom condensation zone.
    # CLOSING HV-322602 raises phi_sp>1 (stronger jet, deeper suction) -> more off-gas condensed into carbamate
    # per unit time -> Q_scrubber RISES; opening (phi_sp<1) lowers it.  Same (1−1/phi_sp) spindle driver as the
    # 322R001 forward-carbamate domino.  At θ_des phi_sp≡1 -> chi_sp≡1 -> q_ccw unscaled -> TT-322002 (178.8)
    # + TDY-329125 (15.0) bit-exact; phi_sp-keyed so it is independent of the steady sump level (below NLL @θ_des).
    chi_sp    = 1.0 + SCRUB_COND_SPINDLE_GAIN * (1.0 - 1.0 / max(spindle_phi, 1e-6))
    q_ccw_kw *= max(chi_sp, SCRUB_COND_CHOKE_MIN)
    # --- Phase-B-coupled CONDENSATION CHOKE derate (TDY-329125 / TT-322002 response to sump flood) -----
    # A flooding sump (LT-329501 above NLL, prior-step tear) floods the shell-side condensation surface,
    # so the carbamate-condensation duty Q_scrubber is constricted by χ_choke ∈ [SCRUB_COND_CHOKE_MIN, 1]:
    #   χ_choke = 1 − (1−SCRUB_COND_CHOKE_MIN)·max(L_329501 − L_NLL, 0)/(100 − L_NLL)   (L_NLL = NLL %)
    # At/below NLL χ_choke ≡ 1 -> q_ccw unchanged -> design bit-exact (TDY-329125 holds 15.0).  Above NLL
    # q_ccw is cut, so TDY-329125 = χ_choke·q_ccw/UA_eff·ε FALLS — condensation constricted by the choke.
    if choke_level_pct is not None:
        chi_choke = 1.0 - (1.0 - SCRUB_COND_CHOKE_MIN) * max(choke_level_pct - SCRUB_LEVEL_NLL_PCT, 0.0) \
                          / max(100.0 - SCRUB_LEVEL_NLL_PCT, 1e-6)
        q_ccw_kw *= clamp(chi_choke, SCRUB_COND_CHOKE_MIN, 1.0)
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
    # Phase A: entrained hot reactor melt (t_carry_c ~ react_T_overflow) lifts the bottom-overflow
    # temperature by an enthalpy mass-blend over the post-carryover overflow mass.  w_carry == 0 below
    # the flood lip (carry_mass_kgh == 0) -> t_overflow unchanged -> TT-322002 design pin bit-exact.
    if carry_mass_kgh > 0.0 and t_carry_c is not None:
        m_ov_tot = sum(overflow[k] * MW_COMP[k] for k in MW_COMP)             # incl. entrained carryover
        if m_ov_tot > 0.0:
            w_carry    = carry_mass_kgh / m_ov_tot
            t_overflow = min(t_overflow + w_carry * (t_carry_c - t_overflow), SCRUB_T_PROC_C)
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


def _eq_pct(theta_pct: float, theta_des_pct: float, R: float = SCRUB_HV604_RANGE) -> float:
    """Equal-percentage valve characteristic factor, normalised to the design opening.

    IEC 60534 inherent equal-percentage trim  K_v(h) = K_vs · R^(h-1)  (h = fractional travel,
    R = rangeability).  Normalised to the design travel h_des the K_vs cancels:
        φ_ep(θ) = K_v(θ)/K_v(θ_des) = R^(h - h_des) = R^((θ - θ_des)/100)
    so φ_ep(θ_des) = R^0 = 1 exactly (design bit-exact) and each +1 % travel multiplies the
    installed K_v by R^0.01 (≈ +8 %/1 % at R=50) — the steep top-of-travel gain that distinguishes
    an equal-% trim from a linear one near the seat-limited / choked operating band."""
    return R ** ((max(theta_pct, 0.0) - theta_des_pct) / 100.0)


def hv_322604(offgas: dict, T_in: float, hic_pct: float, p_up: float) -> dict:
    """HV-322604 HP-scrubber off-gas valve — dynamic isenthalpic letdown 322E003 -> 322C001.
    Inert purge to the LP absorber.  Flow follows the valve hydraulic characteristic, driven by
    the live controller opening θ (HIC-322604) and √ΔP across the seat.  Datasheet trim is
    EQUAL PERCENTAGE (DN-24, Kvs 2.1, carbamate gas), so the opening term is R^((θ−θ_des)/100):
        m_og = m_og_des·s · R^((θ−θ_des)/100) · √(max(P_up−P_down,0)/ΔP_des)   (θ_des = 50%, R = 50)
    The incoming `offgas` vector is already the design purge × s, so the valve factor scales it
    1:1 (composition held; θ=θ_des & P_up=design -> factor=1 -> bit-exact design HMB).  Dynamic
    Joule-Thomson cooling on the ACTUAL pressure drop:  T_out = T_in − μ_JT·ΔP."""
    dP    = max(p_up - SCRUB_HV604_P_OUT, 0.0)
    valve = _eq_pct(hic_pct, SCRUB_HIC604_DES_PCT) * math.sqrt(dP / SCRUB_HV604_DP_DES)   # equal-% trim × √ΔP-ratio
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


# ----------------------------------------------------------------------------------------------------
#  Section-322 downstream (scrubber / ejector / stripper / HPCC-product) display-lag time constants.
#  That block is an explicit ALGEBRAIC TEAR (no vessel-inventory ODE) -- without a lag its published
#  temperatures / level / analyzer SNAP to the new pinned value in a single 0.1 s tick when an upstream
#  stream property or composition steps, which is unphysical (a thermowell, a liquid pool, a seal-leg
#  level and an on-line analyzer all have real capacitance).  We give each PUBLISHED indicator a
#  first-order lag  X += (dt/tau)*(X_ss - X)  so its rate of change is governed by a time constant.
#  Display-only: the tear physics is untouched, and a first-order lag converges to its target, so the
#  pinned design steady state stays bit-exact.  tau values [s] reflect the dominant capacitance:
EJ_T_TAU_S      = 120.0   # 322F001 ejector discharge + suction-side carbamate inventory thermal mass
STRIP_T_TAU_S   = 180.0   # 322E001 stripper liquid holdup (falling-film + bottom sump) + HP shell metal
HPCC_T_TAU_S    = 240.0   # 322E002 carbamate-condenser liquid product + tube-bundle metal mass (slow)
HPCC_P_TAU_S    = 30.0    # 322E002 bubble-point synthesis P (PI-322E002): carbamate-condenser liquid holdup
SCRUB_T_TAU_S   = 180.0   # 322E003 scrubber overflow liquid pool + HP shell metal thermal mass
OFFGAS_T_TAU_S  = 120.0   # off-gas line + HV-322604 vent thermowell (vapour line holdup + metal)
CCW_T_TAU_S     = 25.0    # tempered-CCW shell return (matches TIC-329005 plant lag)
AT_322701_TAU_S = 40.0    # 322701 on-line N/C analyzer (sample deadtime + measurement lag)
SCRUB_LVL_TAU_S = 120.0   # 322E003 overflow seal-leg level inventory (slow integrator)


def _lag1(store: dict, key: str, target: float, tau_s: float, dt: float) -> float:
    """First-order lag of a published display value toward `target` with time constant tau_s [s].

    Discrete implicit-Euler weight  a = dt/(tau+dt)  is unconditionally stable for any dt/tau and
    converges to `target` at steady state (=> design bit-exact).  Lazy-inits to `target` on first
    call so there is no boot transient.  State lives in `store` (State.tlag), keyed by `key`.
    """
    prev = store.get(key)
    if prev is None or tau_s <= 0.0:
        store[key] = target
        return target
    a = dt / (tau_s + dt)
    val = prev + a * (target - prev)
    store[key] = val
    return val


def _fic_flow(c: dict, design: float, op_des: float, store: dict, key: str,
              dt: float, tau_s: float = 5.0, cas_sp=None) -> float:
    """Design-normalised flow-controller step.  Delivered flow = design*(op/op_des).

    The plant is a pure-gain flow element (valve stroke -> flow); its PV is the delivered
    flow lagged tau_s so the measurement forms a proper first-order loop (|z|<1, stable).
    `c["op"]` from the previous tick sets this tick's pre-lag flow, `_ctrl_ipd` then advances
    the controller.  Bit-exact at design:  op==op_des  ->  pre==design  ->  pv==design==sp
    ->  du==0  ->  op stays op_des  ->  flow==design.  Mutates `c` (velocity form) in place.

    A FIC in AUTO holds its leg at SP by integral action, so it REJECTS any upstream element
    placed in series with it -- do not model a series level valve by derating `design` here.
    An upstream level loop must instead cascade into this FIC via `cas_sp` (see LIC-323503 /
    FIC-323405), or it has no steady-state authority and winds up.
    """
    pre = design * (c["op"] / op_des)
    pv  = _lag1(store, key, pre, tau_s, dt)
    op  = _ctrl_ipd(c, pv, dt, cas_sp)
    return design * (op / op_des)


# --- Empirical transport dead time (DCS 03-06-2025 anchor analysis) -------------------
#  Feed-introduction propagation: dead time bracketed to <=572 s, best estimate 345 s
#  (PT-329201 FOPTD fit, R2=0.9888; see reports/dcs_anchor_dynamics_2025-06-03.md §1.2).
#  Applied ONLY to the feed tear streams (NH3 motive, CO2 feed) — the loop's 3470 s
#  pressurization time constant is an EMERGENT property of the inventory ODEs and is a
#  validation target, NOT a hard-coded lag (hard-coding it would double-count dynamics).
FEED_TD_S = 345.0          # s, NH3/CO2 feed -> synthesis-loop response dead time


def _delay(store: dict, key: str, target: float, td_s: float, dt: float) -> float:
    """Pure transport delay y(t) = u(t - td), robust to a VARIABLE sub-step dt.

    sim_task advances each real tick in STEP_CAP-bounded sub-steps whose size is not
    fixed — the remainder sub-step is often a tiny numerical crumb (~1e-8 s).  So the
    buffer length must NOT be derived from dt (n = td/dt would explode to ~1e10 on a
    crumb -> MemoryError).  Instead this is a timestamp-tagged FIFO of past inputs,
    zero-order-held against a per-sub-step sim clock.

    Conservation-safe: every input sample is emitted exactly once (FIFO), only re-timed,
    never scaled or created.  Pin bit-exact: until td seconds of history accumulate the
    input passes through unchanged, and a constant input yields a constant output for
    all t.  State lives in `store` (State.tlag), keyed by `key`.
    """
    if td_s <= 0.0 or dt <= 0.0:
        return target
    st = store.get(key)
    if st is None:
        st = {"t": 0.0, "buf": deque()}          # buf: (entry_time, value), oldest-first
        store[key] = st
    st["t"] += dt
    now = st["t"]
    buf = st["buf"]
    buf.append((now, target))
    cutoff = now - td_s
    # Drop only superseded samples: keep the newest whose entry_time <= cutoff so the
    # zero-order hold still has a value to emit on later ticks (O(1) amortized/tick).
    while len(buf) >= 2 and buf[1][0] <= cutoff:
        buf.popleft()
    if buf[0][0] <= cutoff:
        return buf[0][1]
    return target                                # history younger than td -> pass-through


def _foptd(store: dict, key: str, target: float, tau_s: float, td_s: float,
           dt: float) -> float:
    """First-order-plus-dead-time: dy/dt = (u(t-td) - y)/tau.

    Composition of _delay and _lag1 (implicit Euler, unconditionally stable).
    Realizes G(s) = e^(-td*s) / (tau*s + 1) on a published signal without
    touching the underlying physics states.
    """
    u_delayed = _delay(store, key + ":dl", target, td_s, dt)
    return _lag1(store, key + ":lag", u_delayed, tau_s, dt)


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
    return {"MAN": "M", "AUTO": "A", "CAS": "E", "OOS": "O"}.get(c.mode, "M")


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
        # Prior-step conversion factor (tear var). Feeds the design-ANCHORED bulk temp into f_T so the
        #   conversion self-loop (gain ~0.16) flexes with its OWN exotherm but does NOT ride the HPCC
        #   T_prod cold-cliff (which closed an unstable G~-15 thermal recycle). =1.0 -> design bit-exact.
        self.react_conv_fac = 1.0
        # PHYSICAL liquid-head fraction (% of the 25 m column) — DYNAMIC inventory state (mass balance,
        # open-loop: HV-322605 is hand/auto and does NOT control level). dV/dt = Q_in - Q_out(φ).  Drives
        # the bottom-take-off hydraulics, the flood/carryover guard and the loop-mass P_min (full-column).
        self.react_level_pct = REACT_LEVEL_NLL_PCT      # init at design NLL = 80 % (derived from react_m_liq)
        # LT-322504 transmitter reading (%) — the DISPLAYED narrow-band indication (N7, 1.5 m span, top tap
        #   1 m above overflow): a re-scope of react_level_pct, NOT a separate inventory.  Init 80 % (design).
        self.react_lt322504_pct = REACT_LEVEL_NLL_PCT
        # Fix-2b: CONSERVED liquid holdup mass (kg) — the true level state.  level = m_liq/(rho(T)·A),
        #   so cooling (rho up) drops the level below the weir lip even with the holdup frozen.
        self.react_m_liq     = REACT_M_LIQ_DES          # seeded rho_bulk·A·level_des -> reads 80 % at design
        # Recycle-mass transport lag (τ_rec): the (1-φ_f) recycle leg of the production-mass surge buffers
        #   through the loop inventory before reaching the holdup In term, so HV-322605 keeps PROMPT drain
        #   authority over LT-322504.  Seeded 0 (no surge at design) -> m_in==ṁ_des on init (bit-exact).
        self.react_m_in_lag  = 0.0
        # Fix-4 ejector forward-carbamate washout: low-pass of the spindle-attributable draw
        #   ṁ_suc·(1−1/φ_sp(θ)).  The high-pass (driver − this state) is the TRANSIENT forward-carbamate
        #   pulse on an HV-322602 move, decaying to 0 at any steady θ (so no sustained fictitious source).
        #   Seeded 0; driver ≡ 0 at the design valve θ=74 -> state stays 0 -> LT-322504 pin bit-exact.
        self.react_fwd_wash  = 0.0
        self.hpcc_level_pct  = HPCC_LEVEL_NLL_PCT       # 322E002 liquid inventory, init design NLL
        # 322E003 scrubber sump — TRUE dynamic liquid inventory (Option 3). holdup kg integrated
        #   each tick from (condensation make − actual ejector entrainment); level = holdup/NLL_KG·NLL%.
        self.scrub_holdup_kg = SCRUB_HOLDUP_NLL_KG      # init at design NLL holdup -> 50 % (bit-exact)
        self.scrub_level_pct = SCRUB_LEVEL_NLL_PCT      # 322E003 sump level (LT-329501), design NLL
        # pumps: open_act = torque-converter valve opening %
        self.pumpA = {"on": False, "open_act": 0.0,  "speed_act": 0.0,   "current": 0.2,  "mode": "M", "fault": False}
        # pumpB MANUAL seed pinned at the ratio-cascade DESIGN opening (step_sim ~L1539-1544:
        #   open_cas = clamp(rpm_req/PUMP_RATED_RPM*100), rpm_req from ratio_SP*NC_TO_MASS*F_CO2_th).
        #   Cluster-2023 design point (fresh N/C = RATIO_PV_DES >= 2.0): the seed is the exact inverse of
        #   the cascade flow law (NC_FACTOR*NC_TO_MASS == 1) so the pump delivers motive
        #   == EJ_MOTIVE_NH3_DES == 42762.05 kg/h -> ejector phi_m == 1 -> W_feed == W0, L_feed == L0 at
        #   the design seed (stationary). DERIVED from the module constants (not a hardcoded literal) so it
        #   stays bumpless-consistent with PUMP_ETA_V by construction: eta_v=0.95 -> 86.200 %, eta_v=0.980
        #   -> 83.561 %.  [Was 82.147 % under the SUPERSEDED N/C=1.928 Cluster-1928 point, which forced
        #   ratio_PV=1.928 != RATIO_PV_DES -> L_fresh normalization off -> L_feed != L0.]
        _OPEN_DES_B = (EJ_MOTIVE_NH3_DES / NH3_RHO) / (PUMP_V_PER_REV * PUMP_ETA_V * 60.0) / PUMP_RATED_RPM * 100.0
        self.pumpB = {"on": True, "open_act": _OPEN_DES_B,
                      "speed_act": _OPEN_DES_B / 100.0 * PUMP_RATED_RPM,
                      "current": pump_current_A(_OPEN_DES_B / 100.0 * PUMP_RATED_RPM, True),
                      "mode": "M", "fault": False}
        # controllers (percent)
        self.SIC_321950 = Controller("SIC_321950", Kc=2.0, Ti=8.0,
                                     sp=80.0, mv=0.0)
        self.SIC_321951 = Controller("SIC_321951", Kc=2.0, Ti=8.0,
                                     sp=_OPEN_DES_B, mv=_OPEN_DES_B)
        self.controllers: dict = {
            "SIC_321950": self.SIC_321950,
            "SIC_321951": self.SIC_321951,
        }
        # Bug-6 boot mode: running pump-B speed controller starts on CASCADE (slave to the N/C ratio
        #   master) -- "all automatic valves on Cascade if applicable, else Auto".  CAS entry is
        #   bumpless (bias=0, PID reset) and cas_sp == open_cas == _OPEN_DES_B at the design seed
        #   (verified bit-exact), so the design fixed point is preserved.  SIC_321950 stays MAN: pump A
        #   is an OFF standby (pv=open_act=0); CAS on a stopped pump would wind mv up toward cas_sp.
        self.SIC_321951.set_mode("CAS")
        # ratio: AUTO at boot (master of the SIC-951 cascade).  ratio_mode is the operator-station
        #   display mode; open_cas is always derived from ratio_SP, so AUTO is math-identical here.
        self.ratio_mode = "AUTO"
        self.ratio_SP   = 2.0231315310702604    # design molar N/C == RATIO_PV_DES (fresh N/C>=2.0, Cluster-2023)
        self.ratio_PV   = 2.0231315310702604    # molar N/C PV
        self.ratio_bal  = 2.0231315310702604
        self.F_CO2_th   = 54.618   # t/h, actual CO2 feed to 322E001 (derived: raw - vent)
        # CO2 feed line (320K002 BL -> XV-322902 -> 322E001), vent via PV-322203
        self.F_CO2_raw_th = 54.618 # t/h, raw CO2 from 320K002 compressor (BL boundary)
        self.F_CO2_vent_th = 0.0   # t/h, CO2 vented via PV-322203 (design: vent shut -> 0)
        self.XV_322902    = True   # CO2 feed isolation to HP Stripper 322E001 (True=OPEN)
        self.HIC_322203   = 0.0    # %, HIC-322203 = PV-322203 minimum opening (operator)
        # PIC-322203 CO2 line-pressure controller -> PV-322203 opening (direct-acting velocity I-PD).
        #   Bug-6 boot mode: AUTO (it is an automatic valve, not a hand valve), set as a DORMANT
        #   over-pressure relief.  The 320K002-float model (bugs 1/4) caps the CO2 line at the
        #   deliverable ceiling P_line_ceil = SYN_P_MAX_BARA + DP_HP_DES (147.7 bar a); the line can
        #   never exceed it.  SP is set one design feed-dP ABOVE that ceiling --
        #     sp = SYN_P_MAX_BARA + 2*(CO2_P_DES_BARA - SYN_P_DES_BARA) = 151.2 bar a --
        #   so the relief opens only on genuine line over-pressure (line > floating ceiling + one
        #   feed-dP), NOT on the normal floating band (P_line 144.2..147.7).  SP strictly above the
        #   ceiling keeps op clamped at 0 across the whole band (the velocity term's pv-sp stays
        #   negative): at sp == ceiling exactly, the ramp-up velocity transient cracked a hair of
        #   vent which the SIC-951 CASCADE then amplified into a synthesis-pressure lock (test_3
        #   relax regression) -- the +1 feed-dP margin removes that marginal coupling.  All from
        #   existing constants (no fabricated relief head).  op=0 at the design seed -> design-
        #   preserving.  Operator still forces a minimum opening for carbamate-activation via the
        #   HIC-322203 hand station (max(HIC, PIC.op)).
        self.PIC_322203   = {"mode": "AUTO", "op": 0.0,
                             "sp": SYN_P_MAX_BARA + 2.0 * (CO2_P_DES_BARA - SYN_P_DES_BARA),
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
        # Section-322 tear display-lag store: {key: last published lagged value} for every downstream
        #   temperature / level / analyzer indicator (see _lag1).  Lazy-inits to design on first tick.
        self.tlag = {}
        # MP/LP steam headers (DYNAMIC lumped-capacitance states, quarantined steam_system module).
        #   Seeded at the stripper/HPCC design saturation pressures (NOT steam_system's generic 25.0
        #   default) so tsat(P_MP)=211.6 == STRIP_STEAM_T_DES_C and the LP offset is 0 -> design
        #   forward pass is bit-exact; valve coeffs are pinned at import for a stationary fixed point.
        self.steam = SteamState(P_MP=STRIP_STEAM_P_BARA, P_LP=HPCC_STEAM_P_BARA)

        # ==================================================================
        #  UNIT 323 - LP RECIRCULATION & PRE-EVAPORATION state + controllers
        #  Lumped liquid holdups (kg) and temperatures (C) seeded at the design
        #  fixed point so dm/dt = dT/dt = 0 at boot.  Every flow is driven by a
        #  live valve stroke normalized to its design stroke -> design-preserving.
        #  Controllers are inline velocity-I-PD dicts in ENGINEERING units (the
        #  codebase idiom for process loops -- cf. LIC-322501 / TIC-329005), stepped
        #  by _ctrl_ipd and published under the RECIRC_323 telemetry block.
        # ==================================================================
        # Liquid inventories (kg) and bulk temperatures (C)
        self.r323_c003_M = R323_C003_M_DES        # 323C003 rectifier bottom holdup
        self.r323_c003_T = R323_C003_T_SP_C        # 135 C
        self.r323_c003_P = R323_C003_P_BARA        # PT-323201 column pressure (dynamic, hydraulic coupling)
        self.r323_f004_M = R323_F004_M_DES         # 323F004 flash-tank holdup
        self.r323_f004_T = R323_F004_T_SP_C        # 106 C
        self.r323_f004_P = R323_F004_P_BARA        # 323F004 flash pressure (dynamic, read by PIC-323203 LP node)
        self.r323_f010_M = R323_F010_M_DES         # 323F010 pre-evap separator holdup
        self.r323_f010_T = R323_F010_T_SP_C        # 99 C
        self.r323_d002_M_I  = R323_D002_M_I_DES    # 323D002 Compartment I (active, 80 m3)
        self.r323_d002_M_II = R323_D002_M_II_FULL * 0.50   # Compartment II (passive buffer, 300 m3)

        # -- Stage 1 cascade: TIC-323007 (master, hold 135 C) -> PIC-329202 (steam pressure to 323E002).
        #    Master OP = steam-chest pressure demand (bar a, 0..P_sup); slave OP = steam valve stroke (%).
        self.TIC_323007 = {"mode": "AUTO", "op": R323_E002_PCHEST_DES,
                           "sp": R323_C003_T_SP_C, "pv": R323_C003_T_SP_C,
                           "pv1": R323_C003_T_SP_C, "pv2": R323_C003_T_SP_C,
                           "Kc": 2.0, "Ti": 500.0, "Td": 0.0, "act": +1.0,  # official Td=-1 (deriv disabled) -> 0.0
                           "op_lo": 0.0, "op_hi": R323_P_STEAM_SUP, "sp_lo": 50.0, "sp_hi": 160.0}
        self.PIC_329202 = {"mode": "CAS", "op": R323_E002_OP_DES,
                           "sp": R323_E002_PCHEST_DES, "pv": R323_E002_PCHEST_DES,
                           "pv1": R323_E002_PCHEST_DES, "pv2": R323_E002_PCHEST_DES,
                           "Kc": 8.0, "Ti": 20.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": R323_P_STEAM_SUP}
        # -- Stage 1/2 level loops -> LV-323501 / LV-323505 (DIRECT: level above SP -> drain more).
        self.LIC_323501 = {"mode": "AUTO", "op": R323_LV501_OP_DES,
                           "sp": R323_C003_LVL_SP, "pv": R323_C003_LVL_SP,
                           "pv1": R323_C003_LVL_SP, "pv2": R323_C003_LVL_SP,
                           "Kc": 2.0, "Ti": 120.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        self.LIC_323505 = {"mode": "AUTO", "op": R323_LV505_OP_DES,
                           "sp": R323_F004_LVL_SP, "pv": R323_F004_LVL_SP,
                           "pv1": R323_F004_LVL_SP, "pv2": R323_F004_LVL_SP,
                           "Kc": 2.0, "Ti": 120.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # -- Stage 3 cascade: TIC-323012 (master, hold 99 C) -> PIC-329208 (steam pressure to 323E010).
        self.TIC_323012 = {"mode": "AUTO", "op": R323_E010_PCHEST_DES,
                           "sp": R323_F010_T_SP_C, "pv": R323_F010_T_SP_C,
                           "pv1": R323_F010_T_SP_C, "pv2": R323_F010_T_SP_C,
                           "Kc": 3.6, "Ti": 306.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": R323_P_STEAM_SUP, "sp_lo": 50.0, "sp_hi": 130.0}
        self.PIC_329208 = {"mode": "CAS", "op": R323_E010_OP_DES,
                           "sp": R323_E010_PCHEST_DES, "pv": R323_E010_PCHEST_DES,
                           "pv1": R323_E010_PCHEST_DES, "pv2": R323_E010_PCHEST_DES,
                           "Kc": 8.0, "Ti": 20.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": R323_P_STEAM_SUP}
        # -- Stage 4 cascade: LIC-323507 (tank Comp I level, DIRECT) -> FIC-324401 -> FV-324401 (to 324).
        #    LIC-323507 faceplate missing: Ti = hydraulic settling time V_I/Q = 80/(92.75/1.3) ~ 4030 s.
        #    Master OP = product-flow demand (t/h); slave OP = FV-324401 stroke (%).
        self.LIC_323507 = {"mode": "AUTO", "op": R323_M324_DES / 1000.0,
                           "sp": R323_D002_LVL_SP, "pv": R323_D002_LVL_SP,
                           "pv1": R323_D002_LVL_SP, "pv2": R323_D002_LVL_SP,
                           "Kc": 1.0, "Ti": 4030.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 150.0, "sp_lo": 0.0, "sp_hi": 100.0}
        self.FIC_324401 = {"mode": "CAS", "op": R323_FV401_OP_DES,
                           "sp": R323_M324_DES / 1000.0, "pv": R323_M324_DES / 1000.0,
                           "pv1": R323_M324_DES / 1000.0, "pv2": R323_M324_DES / 1000.0,
                           "Kc": 1.5, "Ti": 30.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 150.0}

        # ==================================================================
        #  UNIT 324 — TWO-STAGE EVAPORATION controllers + lumped state.
        #  Every controller seeded pv==sp==pv1==pv2 -> du==0 (bit-exact boot);
        #  every holdup/temp/pressure seeded at its design fixed point so
        #  dM/dt = dT/dt = dP/dt = 0 at t=0.  Steam is a TIC->PIC cascade
        #  (master demand in bar a chest-pressure, slave in % valve stroke);
        #  vacuum is a false-air PIC around a fixed boundary.
        # ==================================================================
        # ---- Stage 1 steam : TIC-324001 (130 C) -> PIC-329203 (steam chest) ----
        self.TIC_324001 = {"mode": "AUTO", "op": R324_E001_PCHEST_DES,
                           "sp": R324_E001_T_SP_C, "pv": R324_E001_T_SP_C,
                           "pv1": R324_E001_T_SP_C, "pv2": R324_E001_T_SP_C,
                           "Kc": 2.0, "Ti": 120.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": R323_P_STEAM_SUP,
                           "sp_lo": 0.0, "sp_hi": 200.0}
        self.PIC_329203 = {"mode": "CAS", "op": R324_E001_OP_DES,
                           "sp": R324_E001_PCHEST_DES, "pv": R324_E001_PCHEST_DES,
                           "pv1": R324_E001_PCHEST_DES, "pv2": R324_E001_PCHEST_DES,
                           "Kc": 1.5, "Ti": 20.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0,
                           "sp_lo": 0.0, "sp_hi": R323_P_STEAM_SUP}
        # ---- Stage 2 steam : TIC-324002 (140 C) -> PIC-329212 (steam chest) ----
        self.TIC_324002 = {"mode": "AUTO", "op": R324_E003_PCHEST_DES,
                           "sp": R324_E003_T_SP_C, "pv": R324_E003_T_SP_C,
                           "pv1": R324_E003_T_SP_C, "pv2": R324_E003_T_SP_C,
                           "Kc": 2.0, "Ti": 120.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": R323_P_STEAM_SUP,
                           "sp_lo": 0.0, "sp_hi": 200.0}
        self.PIC_329212 = {"mode": "CAS", "op": R324_E003_OP_DES,
                           "sp": R324_E003_PCHEST_DES, "pv": R324_E003_PCHEST_DES,
                           "pv1": R324_E003_PCHEST_DES, "pv2": R324_E003_PCHEST_DES,
                           "Kc": 1.5, "Ti": 20.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0,
                           "sp_lo": 0.0, "sp_hi": R323_P_STEAM_SUP}
        # ---- Vacuum : PIC-324202 (324F001) / PIC-324203 (324F003) false air ----
        #      REVERSE acting: pressure below SP -> admit more false air (op up).
        self.PIC_324202 = {"mode": "AUTO", "op": R324_PV202_OP_DES,
                           "sp": R324_F001_P_BARA, "pv": R324_F001_P_BARA,
                           "pv1": R324_F001_P_BARA, "pv2": R324_F001_P_BARA,
                           "Kc": 1.0, "Ti": 40.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 1.0}
        self.PIC_324203 = {"mode": "AUTO", "op": R324_PV203_OP_DES,
                           "sp": R324_F003_P_BARA, "pv": R324_F003_P_BARA,
                           "pv1": R324_F003_P_BARA, "pv2": R324_F003_P_BARA,
                           "Kc": 1.0, "Ti": 40.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 1.0}
        # ---- LIC-324501 split-range 324F003 drain : LV-A forward / LV-B recycle
        #      DIRECT acting: level above SP -> drain more (op up).
        self.LIC_324501 = {"mode": "AUTO", "op": R324_LIC501_OP_DES,
                           "sp": R324_F003_LVL_SP, "pv": R324_F003_LVL_SP,
                           "pv1": R324_F003_LVL_SP, "pv2": R324_F003_LVL_SP,
                           "Kc": 1.2, "Ti": 300.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # ---- FFIC-335406 UF85 ratio station -> FIC-335405 flow slave -----------
        self.FFIC_335406 = {"mode": "AUTO", "op": R324_UF_RATIO,
                            "sp": R324_UF_RATIO, "pv": R324_UF_RATIO,
                            "pv1": R324_UF_RATIO, "pv2": R324_UF_RATIO,
                            "Kc": 0.5, "Ti": 60.0, "Td": 0.0, "act": +1.0,
                            "op_lo": 0.0, "op_hi": 0.05, "sp_lo": 0.0, "sp_hi": 0.05}
        self.FIC_335405 = {"mode": "CAS", "op": R324_FIC405_OP_DES,
                           "sp": R324_M_UF_DES / 1000.0, "pv": R324_M_UF_DES / 1000.0,
                           "pv1": R324_M_UF_DES / 1000.0, "pv2": R324_M_UF_DES / 1000.0,
                           "Kc": 1.0, "Ti": 15.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 1.0}
        # ---- Unit 324 lumped physical state (seeded at design fixed point) -----
        self.r324_e001_T = R324_E001_T_SP_C          # C  324E001/F001 melt temp
        self.r324_f001_M = R324_F001_M_DES           # kg 324F001 melt holdup
        self.r324_f001_P = R324_F001_P_BARA          # bar a 324F001 vacuum
        self.r324_e003_T = R324_E003_T_SP_C          # C  324E003/F003 melt temp
        self.r324_f003_M = R324_F003_M_DES           # kg 324F003 melt holdup
        self.r324_f003_P = R324_F003_P_BARA          # bar a 324F003 vacuum

        # ==================================================================
        #  UNITS 323-2 / 328-1 / 328-2 — LP RECIRCULATION & DESORPTION state
        #  Lumped liquid holdups (kg), bulk temps (C), section pressures (bar a)
        #  seeded at the design fixed point so dM/dt = dT/dt = dP/dt = 0 at boot.
        #  Controllers are inline velocity-I-PD dicts (EU) stepped by _ctrl_ipd,
        #  every one seeded pv==sp==pv1==pv2 -> du==0 (bit-exact boot).  Design
        #  strokes normalise every flow so the whole network closes at design.
        # ==================================================================
        # ---- 323E011 + 323D011  LP carbamate condenser + drum (45 C, 1.13 bar a)
        self.r3232_e011_M = R3232_D011_M_DES
        self.r3232_e011_T = R3232_E011_T
        self.r3232_e011_P = R3232_E011_P_BARA
        # ---- 323E003 + 323D001 + 323P001  LPCC (74 C, tempered water, 3.2 bar a)
        self.r3232_e003_T = R3232_E003_T
        self.r3232_d001_M = R3232_D001_M_DES
        self.r3232_d001_P = R3232_D001_P_BARA
        # ---- 328C002 Desorber-I (bottoms 139 C) / 328D001 reflux drum (61 C, 2.6)
        self.a328_c002_M = R328_C002_M_DES
        self.a328_c002_T = R328_C002_T_BOT
        self.a328_d001_M = R328_D001_M_DES
        self.a328_d001_T = R328_D001_T
        self.a328_d001_P = R328_D001_P_BARA
        # ---- 328C003 Hydrolyser (200 C, 16.8 bar a) / 328C004 Desorber-II (143 C)
        self.a328_c003_M = R328_C003_M_DES
        self.a328_c003_T = R328_C003_T
        self.a328_c003_P = R328_C003_P_BARA
        self.a328_c004_M = R328_C004_M_DES
        self.a328_c004_T = R328_C004_T
        # ---- 322C001 LP absorber (43 C, 3.9 bar a)
        self.a328_c001_M = A328_C001_M_DES
        self.a328_c001_T = A328_C001_T
        self.a328_c001_P = A328_C001_P_BARA
        # ---- 323C005 vent scrub (55 C) / 328D003 carbamate collector (Comp I 56, II 44)
        self.a323_c005_M  = A323_C005_M_DES
        self.a323_c005_T  = A323_C005_T
        self.a328_d003_MI  = A328_D003_MI_DES
        self.a328_d003_MII = A328_D003_MII_DES
        self.a328_d003_TI  = A328_D003_TI
        self.a328_d003_TII = A328_D003_TII

        # -- 323-2 controllers -------------------------------------------------
        # PIC-323202 LPCC/323D001 vent pressure -> PV-323202 (DIRECT: P>SP -> vent more).
        self.PIC_323202 = {"mode": "AUTO", "op": R3232_E003_PV_OP_DES,
                           "sp": R3232_D001_P_BARA, "pv": R3232_D001_P_BARA,
                           "pv1": R3232_D001_P_BARA, "pv2": R3232_D001_P_BARA,
                           "Kc": 5.0, "Ti": 40.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 2.0, "sp_hi": 5.0}
        # PIC-323203 323E011/D011 vent pressure -> PV-323203 (DIRECT).
        self.PIC_323203 = {"mode": "AUTO", "op": R3232_E011_PV_OP_DES,
                           "sp": R3232_E011_P_BARA, "pv": R3232_E011_P_BARA,
                           "pv1": R3232_E011_P_BARA, "pv2": R3232_E011_P_BARA,
                           "Kc": 5.0, "Ti": 40.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.5, "sp_hi": 2.0}
        # LIC-323502 323D001 drum level (master) -> SIC-323901 pump-speed demand (DIRECT).
        self.LIC_323502 = {"mode": "AUTO", "op": R3232_P001_RPM_DES,
                           "sp": R3232_D001_LVL_SP, "pv": R3232_D001_LVL_SP,
                           "pv1": R3232_D001_LVL_SP, "pv2": R3232_D001_LVL_SP,
                           "Kc": 1.5, "Ti": 300.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # SIC-323901 323P001 LPCC pump speed (slave, rpm) -> m_308 (REVERSE).
        self.SIC_323901 = {"mode": "CAS", "op": R3232_P001_RPM_DES,
                           "sp": R3232_P001_RPM_DES, "pv": R3232_P001_RPM_DES,
                           "pv1": R3232_P001_RPM_DES, "pv2": R3232_P001_RPM_DES,
                           "Kc": 1.0, "Ti": 20.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # SIC-323902 323P001 standby pump speed (MAN 0, spare).
        self.SIC_323902 = {"mode": "MAN", "op": 0.0,
                           "sp": 0.0, "pv": 0.0, "pv1": 0.0, "pv2": 0.0,
                           "Kc": 1.0, "Ti": 20.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # LIC-323503 323D011 flash-tank-condenser level tank (LT-323503) -> LV-323503 on the 323P008
        #   lean-carbamate pump discharge header.  DIRECT: level above SP -> op rises -> LV-503 opens ->
        #   less discharge resistance -> the pump runs out on its curve -> tank drains faster
        #   (323E011 323D011 323P008 Datasheets.md:54).  The tank is 323P008's NPSH buffer; OEM holds
        #   it at 50 % capacity.  MASTER of a cascade: because both 718 legs terminate in AUTO flow
        #   controllers, this op is realised as the TOTAL DRAW DEMAND for the header rather than as a
        #   raw stroke -- FIC-323418 holds its slipstream and FIC-323405 takes the balance as a remote
        #   setpoint.  See the 323D011 runtime block for why the series form cannot work.
        #   Tuning is the OEM DCS pair verbatim (Master_PID_Tuning_Constants.md:26, "323D011,ACA").
        #   Legal here (and NOT for the flow loops) because the PV is a level in percent, so the
        #   controller's engineering unit IS %span and no gain rescale applies.  Integrating level,
        #   k = 7120.8/(3600*1186.8) = 1.667e-3 %/s per %op (unchanged by the cascade: m718_dmd keeps
        #   the same DES/op_des slope the header stroke had); PI closes s^2 + k*Kc*s + k*Kc/Ti, giving
        #   wn = 5.0e-3 rad/s (period ~1257 s) and zeta = 0.30 -> stable, slow averaging control.
        self.LIC_323503 = {"mode": "AUTO", "op": R3232_LV503_OP_DES,
                           "sp": R3232_D011_LVL_SP, "pv": R3232_D011_LVL_SP,
                           "pv1": R3232_D011_LVL_SP, "pv2": R3232_D011_LVL_SP,
                           "Kc": 1.80, "Ti": 120.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # TIC-323013 323E003 tempered-water SUPPLY temp (stream 1102, 55 °C) -> split-range TV-323013A/B.
        #   DIRECT: PV above SP -> op rises -> TV-A opens (cold make-up in) and TV-B closes (hot bypass
        #   out); the two strokes are exact opposites.  sp span = the achievable supply band: 45 °C at
        #   TV-A wide open, 65 °C (= return temp) at TV-A shut / full bypass.
        self.TIC_323013 = {"mode": "CAS", "op": R3232_TV13_DES_PCT,
                           "sp": R3232_TW_SUP_T, "pv": R3232_TW_SUP_T,
                           "pv1": R3232_TW_SUP_T, "pv2": R3232_TW_SUP_T,
                           "Kc": 3.0, "Ti": 250.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 45.0, "sp_hi": R3232_TW_RET_T}
        # FIC-323401 328D003 Comp-I flush 401 -> FV-323401 (REVERSE flow).
        self.FIC_323401 = {"mode": "AUTO", "op": 50.0,
                           "sp": R3232_E011_M401_DES, "pv": R3232_E011_M401_DES,
                           "pv1": R3232_E011_M401_DES, "pv2": R3232_E011_M401_DES,
                           "Kc": 1.2, "Ti": 25.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 2000.0}
        # FIC-323402 328D003 Comp-I wash 402 -> FV-323402 (REVERSE flow).
        self.FIC_323402 = {"mode": "AUTO", "op": 50.0,
                           "sp": R3232_E011_M402_DES, "pv": R3232_E011_M402_DES,
                           "pv1": R3232_E011_M402_DES, "pv2": R3232_E011_M402_DES,
                           "Kc": 0.5, "Ti": 25.0, "Td": 0.0, "act": +1.0,   # Kc 1.2->0.5: g=2931/50=58.6, M=Kc*a*g/a units; loop coef 1-Kc*a*g, a=0.0196. Kc=1.2 gives M=70 (damped-oscillatory band 51-102, rings on disturbance). Kc=0.5 -> M=29, coef 0.43 monotone.
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 6000.0}
        # FIC-323405 lean-carbamate 718A leg, 323D011/323P008 -> 328E004/328D001 -> FV-323405 (REVERSE).
        #   CAS slave of LIC-323503: its remote SP is the level loop's total draw demand less the
        #   FIC-323418 slipstream, so 718A balances the 323D011 inventory.  Dropping it to AUTO/MAN
        #   is legal and simply leaves the tank on manual draw (LIC-323503's output then goes nowhere).
        self.FIC_323405 = {"mode": "CAS", "op": R3232_FIC405_OP_DES,
                           "sp": R3232_M718A_DES, "pv": R3232_M718A_DES,
                           "pv1": R3232_M718A_DES, "pv2": R3232_M718A_DES,
                           "Kc": 0.4, "Ti": 25.0, "Td": 0.0, "act": +1.0,   # Kc 1.2->0.4: g=3560.4/50=71.2, loop coef 1-Kc*a*g, a=0.0196. Kc=1.2 gives coef -0.674 (alternating). Kc=0.4 -> M=28.5, coef 0.442 monotone; brackets FIC-323402 (g=58.6, Kc=0.5, coef 0.43) and FIC-328404 (g=55.5, Kc=0.5, coef 0.46).
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 8000.0}
        # FIC-323418 lean-carbamate 718B leg, 323D011/323P008 -> 323E003 -> FV-323418 (REVERSE).
        #   OEM service is "ACA FROM 323P8A/B" (Master_PID_Tuning_Constants.md:14), i.e. this leg.
        self.FIC_323418 = {"mode": "AUTO", "op": R3232_FIC418_OP_DES,
                           "sp": R3232_M718B_DES, "pv": R3232_M718B_DES,
                           "pv1": R3232_M718B_DES, "pv2": R3232_M718B_DES,
                           "Kc": 0.4, "Ti": 25.0, "Td": 0.0, "act": +1.0,   # same g=71.2 retune as FIC-323405 (718A/718B legs are identical by design).
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 8000.0}

        # -- 328-1 controllers (desorption / hydrolysis train) -----------------
        # LIC-328501 328D001 reflux-drum level -> LV-328501 (DIRECT, 776 -> 323E003).
        self.LIC_328501 = {"mode": "AUTO", "op": R328_D001_LV_OP_DES,
                           "sp": R328_D001_LVL_SP, "pv": R328_D001_LVL_SP,
                           "pv1": R328_D001_LVL_SP, "pv2": R328_D001_LVL_SP,
                           "Kc": 2.0, "Ti": 150.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # PIC-328202 328D001 vent pressure -> PV-328202 (DIRECT, 786 vent -> 323E011).
        self.PIC_328202 = {"mode": "AUTO", "op": R328_D001_PV_OP_DES,
                           "sp": R328_D001_P_BARA, "pv": R328_D001_P_BARA,
                           "pv1": R328_D001_P_BARA, "pv2": R328_D001_P_BARA,
                           "Kc": 5.0, "Ti": 40.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 1.5, "sp_hi": 4.0}
        # TIC-328002 328E004 CW to condenser -> TV-328002 (DIRECT cooling, hold drum 61 C).
        self.TIC_328002 = {"mode": "AUTO", "op": R328_E004_TV_OP_DES,
                           "sp": R328_D001_T, "pv": R328_D001_T,
                           "pv1": R328_D001_T, "pv2": R328_D001_T,
                           "Kc": 3.0, "Ti": 200.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 45.0, "sp_hi": 80.0}
        # FIC-328404 328D001 reflux 775 -> FV-328404 (REVERSE flow, remote-CAS capable).
        self.FIC_328404 = {"mode": "CAS", "op": R328_D001_FIC404_OP_DES,
                           "sp": R328_D001_M775_DES, "pv": R328_D001_M775_DES,
                           "pv1": R328_D001_M775_DES, "pv2": R328_D001_M775_DES,
                           "Kc": 0.5, "Ti": 25.0, "Td": 0.0, "act": +1.0,   # Kc 1.2->0.5: g=1675/30.2=55.5, loop coef 1-Kc*a*g, a=0.0196. Kc=1.2 gives M=67 (damped-oscillatory 51-102). Kc=0.5 -> M=27.7, coef 0.46 monotone.
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 4000.0}
        # FIC-326402 328C003 hydrolyser MP-steam 911 -> FV-326402 (REVERSE flow, CAS).
        self.FIC_326402 = {"mode": "CAS", "op": 50.0,
                           "sp": R328_C003_M911_DES, "pv": R328_C003_M911_DES,
                           "pv1": R328_C003_M911_DES, "pv2": R328_C003_M911_DES,
                           "Kc": 1.2, "Ti": 25.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 3000.0}
        # PIC-328203 328C003 hydrolyser OVHD pressure -> PV-328203 (DIRECT, 16.8 bar a).
        self.PIC_328203 = {"mode": "AUTO", "op": R328_C003_PV_OP_DES,
                           "sp": R328_C003_P_BARA, "pv": R328_C003_P_BARA,
                           "pv1": R328_C003_P_BARA, "pv2": R328_C003_P_BARA,
                           "Kc": 4.0, "Ti": 60.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 12.0, "sp_hi": 20.0}
        # FFIC-328401 328C004 desorber-II steam/feed RATIO master (m931/m738).
        self.FFIC_328401 = {"mode": "AUTO", "op": R328_C004_M931_DES,
                            "sp": R328_FFIC_RATIO_DES, "pv": R328_FFIC_RATIO_DES,
                            "pv1": R328_FFIC_RATIO_DES, "pv2": R328_FFIC_RATIO_DES,
                            "Kc": 0.8, "Ti": 40.0, "Td": 0.0, "act": +1.0,
                            "op_lo": 0.0, "op_hi": 12000.0, "sp_lo": 0.0, "sp_hi": 0.5}
        # FIC-328401 328C004 LP-steam 931 slave (REVERSE flow) <- FFIC-328401 demand.
        self.FIC_328401 = {"mode": "CAS", "op": 50.0,
                           "sp": R328_C004_M931_DES, "pv": R328_C004_M931_DES,
                           "pv1": R328_C004_M931_DES, "pv2": R328_C004_M931_DES,
                           "Kc": 0.30, "Ti": 25.0, "Td": 0.0, "act": +1.0,   # Kc 1.2->0.30: PV in kg/h, process gain g=6495/50=129.9; loop coef 1-Kc*a*g, a=dt/(tau+dt)=0.0196; Kc=1.2 gives coef -2.06 (unstable 0<->100 limit cycle). Kc<0.39 monotonic; 0.30 -> coef 0.24, 2.6x margin.
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 12000.0}
        # TIC-328008 inferential: offgas H2O content to reflux condenser 328E004 (mol%), from TT-328008 & PIC-328202.
        self.TIC_328008 = {"mode": "AUTO", "op": 50.0,
                           "sp": R328_D001_OFFGAS_H2O_DES, "pv": R328_D001_OFFGAS_H2O_DES,
                           "pv1": R328_D001_OFFGAS_H2O_DES, "pv2": R328_D001_OFFGAS_H2O_DES,
                           "Kc": 3.0, "Ti": 250.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # TIC-328012 differential temp controller: TT-328013 (bottom 200) - TT-328012 (3rd tray 190) = 10 C.
        self.TIC_328012 = {"mode": "AUTO", "op": 50.0,
                           "sp": R328_C003_DT_DES, "pv": R328_C003_DT_DES,
                           "pv1": R328_C003_DT_DES, "pv2": R328_C003_DT_DES,
                           "Kc": 3.0, "Ti": 250.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 30.0}
        # LIC-328503 328C002 desorber-I bottoms level -> LV-328503 (DIRECT, 743 -> hydrolyser).
        self.LIC_328503 = {"mode": "AUTO", "op": 50.0,
                           "sp": 50.0, "pv": 50.0, "pv1": 50.0, "pv2": 50.0,
                           "Kc": 2.0, "Ti": 150.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # LIC-328504 328C004 desorber-II bottoms level -> LV-328504 (DIRECT, 739 -> 328E007).
        self.LIC_328504 = {"mode": "AUTO", "op": 50.0,
                           "sp": 50.0, "pv": 50.0, "pv1": 50.0, "pv2": 50.0,
                           "Kc": 2.0, "Ti": 150.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # LIC-328505 328C003 hydrolyser bottoms level -> LV-328505 (DIRECT, 747 -> desorber-II).
        self.LIC_328505 = {"mode": "AUTO", "op": 50.0,
                           "sp": 50.0, "pv": 50.0, "pv1": 50.0, "pv2": 50.0,
                           "Kc": 2.0, "Ti": 150.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # FIC-328402 328D003 Comp-I -> Comp-II transfer 744 wash -> FV-328402 (REVERSE flow).
        self.FIC_328402 = {"mode": "AUTO", "op": 50.0,
                           "sp": R3232_E003_M744_DES, "pv": R3232_E003_M744_DES,
                           "pv1": R3232_E003_M744_DES, "pv2": R3232_E003_M744_DES,
                           "Kc": 0.06, "Ti": 25.0, "Td": 0.0, "act": +1.0,   # Kc 1.2->0.06: design=31478 large, g=629.6, loop coef 1-Kc*a*g, a=0.0196. Kc=1.2 gives M=755 (VIOLENTLY unstable if perturbed; quiet only at bit-exact fixed-point seed). Kc=0.06 -> M=37.8, coef 0.26 monotone. Defends Domino live tie-ins.
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 60000.0}
        # FIC-328406 328D003 standby transfer pump flow (MAN 0, spare).
        self.FIC_328406 = {"mode": "MAN", "op": 0.0,
                           "sp": 0.0, "pv": 0.0, "pv1": 0.0, "pv2": 0.0,
                           "Kc": 1.2, "Ti": 25.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 60000.0}

        # -- 328-2 controllers (LP absorber 322C001) ---------------------------
        # PIC-322201 322C001 absorber vent pressure -> PV-322201 (DIRECT, 3.9 bar a).
        self.PIC_322201 = {"mode": "AUTO", "op": A328_PIC_OP_DES,
                           "sp": A328_C001_P_BARA, "pv": A328_C001_P_BARA,
                           "pv1": A328_C001_P_BARA, "pv2": A328_C001_P_BARA,
                           "Kc": 5.0, "Ti": 40.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 2.5, "sp_hi": 5.5}
        # LIC-322502 322C001 sump level -> LV-322502 (DIRECT, 755 draw via 322P002).
        self.LIC_322502 = {"mode": "AUTO", "op": A328_LIC_OP_DES,
                           "sp": 50.0, "pv": 50.0, "pv1": 50.0, "pv2": 50.0,
                           "Kc": 2.0, "Ti": 150.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}

        # Auxiliary pump roster (running duty / standby spare); toggled via aux_pump_toggle.
        self.aux_pumps = {"323P001A": {"on": True,  "mode": "AUTO"}, "323P001B": {"on": False, "mode": "AUTO"},
                          "322P002A": {"on": True,  "mode": "AUTO"}, "322P002B": {"on": False, "mode": "AUTO"},
                          "328P001A": {"on": True,  "mode": "AUTO"}, "328P001B": {"on": False, "mode": "AUTO"},
                          "328P003A": {"on": True,  "mode": "AUTO"}, "328P003B": {"on": False, "mode": "AUTO"}}
        # XV-322915 steam-flood valve (trip 22.1: 322C001 TT-322015 > 57 C -> latch open).
        self.XV_322915 = False

        # ext override
        self.ext_override = False
        # sim-speed mode (set_sim_mode cmd): "SLOW" = real-time/realistic (default, anchor), "FAST" = accelerated
        self.sim_mode = "SLOW"
        # trips: live initiator conditions (instantaneous) + latched state (P1-2).
        #   A latch holds once set and can only be cleared by an operator trip_reset AND
        #   the live condition having recovered -> a tripped pump cannot self-restart.
        self.trips        = {"21_2": False, "21_4": False, "21_8": False, "21_10": False, "22_1": False}
        self.trip_latched = {"21_2": False, "21_4": False, "21_8": False, "21_10": False, "22_1": False}
        # L3 phase-boundary diagnostics (mushy-zone / crystallization detection, Batch 2)
        self.flags = {"SCRUBBER_SOLIDIFICATION": False,
                      "STRIPPER_SOLIDIFICATION": False,
                      "CARBAMATE_DEPOSITION":    False,
                      "RATIO_PV_BAD":            False,   # L3-3 N/C measurement-validity (Batch 3)
                      "CARBAMATE_CRYST_WARN":    False,   # Bug 2 predictive: approaching freezing
                      "CARBAMATE_CRYST_ALARM":   False}   # Bug 2 predictive: crystallization onset


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
    # Pressure-driven delivery + split of the raw CO2 (bugs 1 & 4 are ONE defect: the feed
    # never respected the CO2-line vs synthesis dP).  s.p_syn_bara is the prev-tick synthesis
    # pressure (tear lag).  The CO2 line pressure (PIC-322203 PV) is modelled physically:
    #   * 320K002 is flow(load)-controlled, so it FLOATS its discharge to hold the design feed
    #     dP against synthesis backpressure -- there is ALWAYS a dP between the line and the
    #     loop (bug 1) -- up to the compressor's deliverable ceiling P_line_ceil (= the max
    #     synthesis pressure SYN_P_MAX it must still feed, plus the design feed dP; derived
    #     from existing constants, no fabricated head).  Within the normal band dP_HP holds at
    #     ~design so phi_HP=1 and feed stays at load (correct: feed is NOT pressure-throttled
    #     by small excursions).  Only when P_syn nears/exceeds the ceiling does dP_HP shrink ->
    #     phi_HP tapers -> check valve shuts (feed 0).
    #   * Opening PV-322203 sags the line by CO2_PV_DP_GAIN per % -- toward/below P_syn -- and
    #     raises g_vent, so f_to_HP -> 0: almost all CO2 leaves via the vent, not the HP loop
    #     even though it kept flowing before (bug 4).
    DP_HP_DES   = CO2_P_DES_BARA - SYN_P_DES_BARA            # 3.5 bar design feed dP
    P_line_ceil = SYN_P_MAX_BARA + DP_HP_DES                 # compressor deliverable ceiling (feed dP held at max-P synthesis)
    P_line_float = min(s.p_syn_bara + DP_HP_DES, P_line_ceil)  # discharge floats to hold the feed dP, capped at shutoff
    P_line_bara = P_line_float - CO2_PV_DP_GAIN * pv_open    # PV-322203 venting pulls the line down -> PIC-322203 PV (bar a)
    dP_HP   = max(P_line_bara - s.p_syn_bara, 0.0)           # drives CO2 INTO HP loop (>=0: check valve)
    dP_vent = max(P_line_bara - CO2_VENT_P_BARA, 0.0)        # drives CO2 OUT the vent
    phi_HP  = min(1.0, (dP_HP / DP_HP_DES) ** 0.5)          # bug 1: delivery taper (1.0 across band, shuts near ceiling)
    g_HP    = dP_HP ** 0.5
    g_vent  = (pv_open / 100.0) * CO2_VENT_COND * dP_vent ** 0.5
    f_to_HP = g_HP / (g_HP + g_vent) if (g_HP + g_vent) > 1e-12 else 0.0   # bug 4: vent-diversion split
    frac_HP = phi_HP * f_to_HP                               # net fraction of raw reaching the HP loop
    F_CO2_feed_kgh = s.F_CO2_raw_th * 1000.0 * feed_factor * frac_HP
    F_CO2_vent_kgh = s.F_CO2_raw_th * 1000.0 * feed_factor * (1.0 - frac_HP)  # all CO2 not delivered to HP -> vent/relief
    s.F_CO2_th = F_CO2_feed_kgh / 1000.0               # t/h actual feed -> drives ratio block
    s.F_CO2_vent_th = F_CO2_vent_kgh / 1000.0          # t/h vented via PV-322203
    CO2_feed_kmolh = F_CO2_feed_kgh / CO2_FEED_MW      # kmol/h
    FT_322403 = CO2_feed_kmolh * NM3_PER_KMOL          # Nm3/h  (FT-322403)
    FY_322403 = s.F_CO2_th                             # t/h    (FY-322403)
    # Empirical BL->loop transport dead time (FEED_TD_S): the CO2 the synthesis loop
    # (stripper strip-gas + reactor) receives NOW left the battery-limit meter 345 s ago.
    # FY/FT-322403, load % and the DCS ratio cascade/PV all read the LIVE BL meter above.
    F_CO2_syn_th = _delay(s.tlag, "FEED_CO2", s.F_CO2_th, FEED_TD_S, dt)
    Load_pct  = s.F_CO2_th / (CO2_DES_KGH / 1000.0) * 100.0   # % of design CO2 flow
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
    # Empirical BL->loop transport dead time (FEED_TD_S): NH3 leaving the pump discharge
    # header transits the BL->ejector line before the loop sees it.  Pure re-timing (ring
    # buffer) — the tank/pump balance above debits the LIVE flow; the difference is line
    # pack in transit.  FY-321401 / ratio-PV read the live pump-discharge transmitters.
    motive_nh3_kgh = _delay(s.tlag, "FEED_NH3", motive_nh3_kgh, FEED_TD_S, dt)
    # Option 3 coupling: ACTUAL entrainment = ejector capacity * gravity suction head (scrub level).
    #   scrub_lvl_frac = prior-step 322E003 level / NLL (loop tear: ejector runs BEFORE the scrubber
    #   block, so it sees last-tick level).  frac=1 at NLL -> design entrainment; frac self-regulates
    #   the sump to L_eq=NLL*(overflow/capacity) -> stable at NLL on turndown, floods on a true stall.
    scrub_lvl_frac = s.scrub_level_pct / SCRUB_LEVEL_NLL_PCT
    ej = ejector_322f001(motive_nh3_kgh, TI_321020, s.HIC_322602, scrub_level_frac=scrub_lvl_frac)
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
    strip = stripper_322e001(F_CO2_syn_th, T_steam_live, STRIP_P_DES_BARA,
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
    # --- cold-start HP-loop fill-rate scaling (SS-NEUTRAL).  Field PT-329201 pressurises over ~58 min
    #   (06-03 Section 1.2 FOPTD, tau=3469.5 s); the model's native mass-balance fills the three HP
    #   holdups in ~10 min, so the emergent tau under-shoots the Section 6.4 band.  Per the report's
    #   Section 6.1 mandate (tau must EMERGE from the physical inventory, never a fudge lag on the
    #   pressure state) we slow the loop-fill itself: scale each HP holdup's NET accumulation by
    #   k_loop_fill, tied to the aggregate loop-mass fraction so it -> 1.0 as the loop fills.  At/near
    #   design m_loop_frac == 1 -> k_loop_fill == 1 (fill untouched) AND every net rate == 0 (in==out),
    #   so the steady-state hold and the warm-start audits stay bit-exact regardless of the scaling.
    _mf_prev    = clamp((s.react_level_pct + s.hpcc_level_pct + s.strip_level)
                        / (REACT_LEVEL_NLL_PCT + HPCC_LEVEL_NLL_PCT + STRIP_LEVEL_SP_DES), 0.0, 1.0)
    #   _fc / _fe calibrated so the emergent cold-start pressurisation tau (model-free Smith 63.2%
    #   two-point ID in tests/coldstart_probe.py) lands inside the DCS-anchored FOPTD band
    #   tau in [2884, 4055] s (center 3469.5 s == SYN_P_TAU_FILL_MIN 57.8 min; dcs_anchor_dynamics
    #   Section 1.2).  _fe == 8 holds k_loop_fill ~= _fc (near-uniform slow fill) across most of the
    #   empty-loop transient; both revert to 1.0 as m_loop_frac -> 1 (design SS bit-exact, SS-neutral).
    _fc         = 0.06     # empty-loop net-rate scale (Smith-calibrated to Section 6.4 band)
    _fe         = 8.0      # gate exponent (Smith-calibrated to Section 6.4 band)
    k_loop_fill = _fc + (1.0 - _fc) * _mf_prev ** _fe
    # bottom-sump mass balance -> LT-322501 level (%)
    m_span_kg = STRIP_SUMP_AREA_M2 * STRIP_LEVEL_SPAN_M * STRIP_RHO_BOTTOM
    s.strip_level = clamp(s.strip_level
                          + k_loop_fill * (strip["bot_kgh"] - drain_kgh) / 3600.0 * dt / m_span_kg * 100.0,
                          0.0, 100.0)
    lic["pv"] = s.strip_level
    # L3-7 bottoms-sump ENERGY BALANCE -> TT-322004 (stream 322E001 falling-film exit -> LV-322501):
    #   The bottom sump is a stirred buffer below the steam-heated falling-film tubes.  Steady-state sump
    #   energy balance (film enthalpy in = drain enthalpy out + heat loss to surroundings):
    #       ṁ·cp·T_film = ṁ·cp·T_out + UA·(T_out − T_amb)
    #   The rigorous stripper model's strip["T_bot"] already equals the DESIGN-drain sump outlet (design HMB
    #   anchor), so the film feeding the sump is  T_film = T_bot·(1+τ) − τ·T_amb  with the design sump-loss
    #   NTU  τ = UA/(ṁ_des·cp) = STRIP_SUMP_NTU_DES.  Eliminating T_film and writing r = ṁ_drain/ṁ_des
    #   (live drain / design drain) gives the closed-form sump outlet temperature:
    #       T_out = [ r·(1+τ)·T_bot + τ·(1−r)·T_amb ] / (r + τ)
    #   r=1 -> T_out = T_bot  (bit-exact design HMB);  r↑ (LV-322501 opened -> more bottoms flow, less sump
    #   residence) -> T_out -> (1+τ)·T_bot = T_film  (hotter, ≤ steam sat);  r↓ (throttled, long residence)
    #   -> T_out -> T_amb  (crystallization-pinned floor).  dT_out/dr = τ(1+τ)(T_bot−T_amb)/(r+τ)² > 0 since
    #   T_bot > T_amb, so opening LV-322501 raises the bottoms flow which raises TT-322004 (item 3) — now
    #   driven by the ACTUAL drain mass flow through the sump heat balance, not an empirical opening curve.
    #   drain_kgh keys off strip["T_bot"] (f_drain) only, never T_out -> no algebraic loop.
    T_amb_sump = STRIP_BOT_T_CRYST_C
    if strip["T_bot"] > T_amb_sump:
        r_drain    = drain_kgh / STRIP_BOT_DES_KGH
        tau_sump   = STRIP_SUMP_NTU_DES
        T_bot_disp = (r_drain * (1.0 + tau_sump) * strip["T_bot"] + tau_sump * (1.0 - r_drain) * T_amb_sump) \
                     / (r_drain + tau_sump)
        T_bot_disp = min(T_bot_disp, strip["T_steam"])   # bottoms can never out-heat the condensing shell
    else:
        T_bot_disp = strip["T_bot"]                      # cold start / solidified: no hot-film sump residence effect
    TT_323001 = STRIP_T_DOWN_DES_C + 0.7 * (T_bot_disp - STRIP_T_BOTTOM_DES_C)   # post-flash ripples the same bottoms T

    # HP carbamate condenser 322E002: strip gas + ejector liquid -> two-phase product to 322R001.
    #   Shell-side LP-steam saturation T tracks the live LP header, but as an OFFSET about the
    #   pinned design constant (HPCC_STEAM_TSAT_C=146.3 differs from Antoine tsat(4.4)~147.4); at
    #   design P_LP==HPCC_STEAM_P_BARA so the offset is 0 -> T_shell_lp==146.3 bit-exact.
    #   The OFFSET is Option-1 disturbance-gated: g_dist==0 (no operator/feed move) freezes t_shell at
    #   the design constant -> kills the P_LP->t_shell->T_prod->reactor->duty->P_LP runaway; g_dist->1
    #   on a genuine disturbance restores the full live shell-temp response.
    g_dist = _disturbance_gate(s)
    T_shell_lp = HPCC_STEAM_TSAT_C + g_dist * (tsat_steam(s.steam.P_LP) - tsat_steam(HPCC_STEAM_P_BARA))
    hpcc = hpcc_322e002(strip, ej, t_shell=T_shell_lp, gate=g_dist)

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
    # f_T bulk temp = design HPCC base + the reactor's OWN prior-step exotherm (NOT the live cascading
    #   lip). This keeps the deliberate conversion self-loop (gain ~0.16, stable) while CUTTING the
    #   conversion->composition->HPCC-N/C cliff return leg that closed an unstable G~-15 thermal recycle
    #   (the source of the TT-322010 161<->213 oscillation). conv_fac=1 -> 170+13=183=T0_DES (bit-exact).
    T_conv_c = HPCC_T_PROD_DES_C + REACT_DT_COL_DES * s.react_conv_fac
    react   = react_322r001(hpcc, F_CO2_syn_th, s.HIC_322605, L_drive=L_blend, W_drive=W_blend,
                            T_overflow_c=T_conv_c)
    s.react_L_feed = react["L_feed"]                   # tear -> next step's stripper eta_T penalty
    s.react_W_feed = react["W_feed"]
    # NB: s.react_overflow_kmolh (the stripper-feed tear) is set BELOW in the reactor-inventory block —
    #     it is the HYDRAULIC bottom take-off m_out (HV-322605 × column head), NOT the raw split production.

    # Fix-1: integrate the distributed 4-node axial thermal profile (Damköhler-shaped exotherm).
    #   dT_n/dt = [ (T_{n-1} - T_n) + g_n·ΔT_col ] / τ_n ,  T_0 = T_feed (HPCC two-phase product),
    #   ΔT_col = ΔT_col,des · conversion_factor  (the profile FLEXES with the live per-pass conversion).
    # Explicit Euler; the upstream term uses the PREVIOUS-step node temps (T_old) so the cascade is
    # decoupled within a tick (steady state is identical: T_old[n-1]==T_new[n-1] -> telescopes to
    # T_n = T_feed + ΔT_col·G_raw(ζ_n), the as-built residence-time probe profile when conv_fac->1).
    conv_fac = react["X_conv"] / reactor.X_DES_RAW
    s.react_conv_fac = conv_fac                              # tear -> next step's design-anchored f_T base
    dT_col   = REACT_DT_COL_DES * conv_fac
    T_old     = list(s.react_T_node)
    T_up      = hpcc["T_prod"]                               # node-0 upstream = LIVE HPCC two-phase feed T (cascade)
    flow_frac = max(clamp(react["co2_scale"], 0.0, 1.0), 1.0e-3)  # m_dot/m_dot_des proxy (§7.6 P5-B: floor 1e-3>0 so tau_n=tau_des/flow_frac stays finite as load->0; bit-exact at design, co2_scale>>1e-3); tau-scale + loss gate
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
    s.react_T_overflow = new_T[3] + REACT_G_OV * dT_col       # overflow lip off INERTIAL node-3 (Σ g_n + g_ov = 1 anchor)
    s.react_T_offgas   = new_T[3] + REACT_OFFGAS_GAMMA * (s.react_T_overflow - new_T[3])
    react["T_overflow"] = s.react_T_overflow                 # publish live profile to telemetry + scrubber
    react["T_offgas"]   = s.react_T_offgas

    # ----- Steam balance handshake (reverse pass): forward duties -> header mass draws -> Euler tick.
    #   Q [kJ/h] = duty_kW * 3600 ;  m [kg/s] = Q / lambda[kJ/kg] / 3600  ==  duty_kW / lambda.
    #   Stripper reboiler draws MP steam (fixed design duty); HPCC raises LP steam (live duty).
    Q_strip_kjh = STRIP_DUTY_DES_KW   * 3600.0
    Q_hpcc_kjh  = hpcc["q_steam_kw"]  * 3600.0   # LP steam RAISED, not the full process duty (see below)
    m_strip = Q_strip_kjh / 1850.0          / 3600.0   # MP steam consumed (kg/s)
    m_hpcc  = Q_hpcc_kjh  / HPCC_LATENT_4BAR / 3600.0  # LP steam generated (kg/s)
    # q_steam_kw (computed in hpcc_322e002) = process duty MINUS the extra sensible heat carried out in the
    #   product when it leaves above the design pin (T_prod>HPCC_T_PROD_DES_C at a higher shell P).  This is
    #   the physical shell back-pressure on steam-raising and the missing stabilizing feedback: as P_LP rises
    #   -> t_shell rises -> T_prod rises -> q_steam falls -> m_hpcc falls -> P_LP pulled back to design.  It
    #   references the PINNED 170 C (not live T_adb), so it does NOT self-defeat when the reactor heats.  At
    #   design T_prod==HPCC_T_PROD_DES_C -> q_steam==duty_kw bit-exact -> LP balance untouched.  WITHOUT it the
    #   loop P_LP^->t_shell^->T_prod^->reactor^->(tear)stripper/gas^->HPCC duty^->m_hpcc^->P_LP^ is a positive
    #   runaway (free t_shell -> P_LP runs to ~24 bar a / t_shell 220 C); this re-stabilizes the fixed point.
    if _STEAM_READY:                        # OFF during both boot-pin settles (headers frozen at design)
        step_steam(s.steam, dt, m_strip, m_hpcc)

    # LT-322504 dynamic level — DOMINO inventory (Option 2, Lead-Ops mandate): the reactor 322R001 is a
    #   true liquid HOLDUP and HV/HIC-322605 has STRICT HYDRAULIC authority over the BOTTOM take-off to the
    #   stripper (NOT over the molar off-gas split — vaporization happens DOWNSTREAM in the 322E001 tubes):
    #       m_in  = ṁ_ov,split                              (live urea-solution PRODUCTION; φ-independent)
    #       m_out = ṁ_des·(θ/θ_des)·(max(L,0)/L_des)        (HV-322605 gate × column head; capacity = ṁ_des)
    #       d(m_liq)/dt = m_in − m_out ;  L = m_liq/(rho(T_bulk)·A).
    #   m_out IS the liquid fed to the stripper (conservation through the holdup) — see f_strip below.  At
    #   design θ==θ_des, L==L_des and ṁ_ov,split==ṁ_des -> m_out==m_in==ṁ_des -> dm/dt=0, f_strip=1.0
    #   (bit-exact pin).  OPEN HV-322605: m_out>m_in -> reactor DRAINS (L↓) AND surges the stripper feed
    #   (transient); level re-settles at L_eq=L_des·(θ_des/θ) while steady feed returns to production.
    #   THROTTLE: m_out<m_in -> reactor FLOODS (L↑, see carryover below) and starves the stripper.  The
    #   take-off capacity is ṁ_des (production-independent), so a CO2-cut feed trip (m_in -> 0) drains the
    #   vessel CONTINUOUSLY toward empty — no φ_fwd FLOOR hack needed (Bug #4 safe by construction).
    T_bulk_react   = sum(new_T) / 4.0                          # live bulk temp (= node mean; design 179.7 C)
    level_m_react  = REACT_LIQ_H_M * s.react_level_pct / 100.0  # prev-step head feeding the discharge (explicit)
    m_ov_split_kgh = sum(react["overflow_kmolh"][k] * MW_COMP[k] for k in react["overflow_kmolh"])  # instantaneous production
    # HV-322605 ⟶ mass-balance timing fix.  The production surge above design (m_ov_split − ṁ_des) is the
    #   synthesis-loop recycle returning as urea solution; the reduced model returns it with ZERO transport
    #   delay (1-step tears), so production refilled the holdup as fast as HV-322605 drained it and LT-322504
    #   barely moved.  Split the surge exactly like the L/W composition lag above: the fresh fraction φ_f
    #   arrives PROMPT, the (1−φ_f) recycle leg buffers through the loop inventory τ_rec (same a_rec, φ_f).
    #   Result: m_out responds to HV-322605 at once while m_in refills over τ_rec -> HV-322605 has prompt,
    #   visible hydraulic authority over the level, re-settling at L_eq=L_des·(θ_des/θ).  At design the surge
    #   is 0 -> lag stays 0 -> m_in==ṁ_des==m_out -> dm/dt=0 (bit-exact pin preserved).
    m_surge_kgh       = m_ov_split_kgh - _react_mdot_kgh                    # production above design (0 at design)
    s.react_m_in_lag += a_rec * (m_surge_kgh - s.react_m_in_lag)           # recycle leg lags through τ_rec
    m_in_kgh          = (_react_mdot_kgh + REACT_FRESH_FRAC * m_surge_kgh
                         + (1.0 - REACT_FRESH_FRAC) * s.react_m_in_lag)    # prompt fresh + lagged recycle
    m_out_kgh      = reactor.outlet_line_outflow_kgph(level_m_react, _react_mdot_kgh, REACT_LEVEL_DES_M,
                                                      s.HIC_322605, REACT_HIC605_DES_PCT)  # HV-322605 take-off
    # DOMINO (Fix-4): ejector forward-carbamate coupling 322E003 -> 322F001 -> 322E002 -> 322R001.
    #   Closing HV-322602 raises the spindle momentum flux ṁ²/(ρA) -> the 322F001 ejector entrains MORE
    #   carbamate from the 322E003 sump (ej["suction_kgh"] climbs above its design draw EJ_SUC_TOT_DES); that
    #   surge is pumped forward through the HPCC (322E002) into the reactor as extra liquid make.  The reduced
    #   loop previously dead-ended this wave at the HPCC — reactor m_in carried no forward-flow term — so
    #   LT-322504 was stone-dead to HV-322602.  Inject the surge (kg/h above design) directly into the holdup
    #   (bypassing m_in_kgh's recycle-lag split — it is a prompt forward-pumped wave, not production).  The
    #   head then climbs above design -> LT-322504 RISES on closing / FALLS on opening.
    #   Driver = the SPINDLE-attributable part of the draw, ṁ_suc·(1 − 1/φ_sp(θ)) -> identically 0 at the design
    #   valve θ=74 (φ_sp=1) at ANY sump state, so the LT-322504 startup/relaxation NLL pin stays bit-exact (it is
    #   NOT keyed on raw suction, which is nonzero off-NLL during the sump fill).  The driver's SUSTAINED part is
    #   a counterfactual (at steady state the sump can only supply its inflow -> a constant forward term would
    #   INVENT mass), so wash it out: low-pass the driver (react_fwd_wash, τ_fwd ≈ sump-drain time) and inject
    #   only the HIGH-PASS residue (driver − wash) — the TRANSIENT pulse on an HV-322602 move that decays to 0
    #   at any steady θ.  Mass-conservative inventory REDISTRIBUTION sump->reactor->stripper; the higher
    #   head raises the level-servoed take-off m_out and the swell relaxes back.
    _phi_sp_theta    = EJ_SPINDLE_R ** ((EJ_OPEN_DES - s.HIC_322602) / 100.0)   # >1 closing, =1 @74, <1 opening
    _fwd_drive_kgh   = ej["suction_kgh"] * (1.0 - 1.0 / _phi_sp_theta)          # spindle-attributable draw (0 @74)
    _a_fwd           = dt / (REACT_FWD_TAU_MIN * 60.0)
    s.react_fwd_wash += _a_fwd * (_fwd_drive_kgh - s.react_fwd_wash)            # low-pass (sustained part)
    m_fwd_carb_kgh   = REACT_FWD_GAIN * (_fwd_drive_kgh - s.react_fwd_wash)     # high-pass: transient pulse, ->0 steady
    s.react_m_liq += k_loop_fill * (m_in_kgh - m_out_kgh + m_fwd_carb_kgh) * (dt / 3600.0)
    s.react_m_liq  = max(s.react_m_liq, reactor.M_HOLDUP_MIN)  # holdup floor -> guards level_from_holdup
    # DOMINO: the hydraulic take-off m_out IS this step's stripper liquid feed — scale the split-fraction
    #   overflow composition to the live outlet mass (f_strip=1 at design -> bit-exact).  The 322E001 native
    #   heat/CO2-strip equations then drive this liquid surge into the overhead gas at its own equilibrium.
    f_strip = (m_out_kgh / m_ov_split_kgh) if m_ov_split_kgh > 1.0e-9 else 1.0
    s.react_overflow_kmolh = {k: react["overflow_kmolh"][k] * f_strip for k in react["overflow_kmolh"]}
    # ISSUE (Phase A): OFF-GAS-LINE LIQUID CARRYOVER on flood.  Throttling the bottom take-off (HV-322605)
    #   cannot pass m_in, so holdup rises to the vessel-full mass M_full = rho(T_bulk)·A·H_liq (PHYSICAL
    #   vessel-full lip; the LT-322504 narrow band saturates 100% earlier, at overflow+1 m).  Liquid above
    #   M_full CANNOT accumulate in the reactor — it physically spills
    #   over the off-gas line (TT-322009) into the HP scrubber (322E003) as ENTRAINED MELT.  Capping m_liq
    #   at M_full simultaneously (a) closes a latent conservation leak (m_liq integrated unbounded above
    #   full while only the level DISPLAY was clamped, so m_out saturated < m_in forever) and (b) yields
    #   the carryover rate = the un-passable excess (m_in − m_out)|_full.  Carryover carries reactor-
    #   OVERFLOW composition + enthalpy (react_T_overflow).  Identically ZERO below the flood lip
    #   (m_liq < M_full at design 80% NLL) -> react_carry_kmolh is None -> scrubber HMB/TT pins bit-exact.
    M_full_react      = reactor.liquid_density(T_bulk_react) * _react_area_m2 * REACT_LIQ_H_M
    react_carry_kgh   = max(s.react_m_liq - M_full_react, 0.0) * (3600.0 / dt)   # spilled melt rate (kg/h)
    s.react_m_liq     = min(s.react_m_liq, M_full_react)                         # vessel cannot exceed full
    s.react_level_pct = clamp(reactor.level_from_holdup(s.react_m_liq, T_bulk_react,
                                                        area_m2=_react_area_m2) / REACT_LIQ_H_M * 100.0,
                              0.0, 100.0)
    # LT-322504 DISPLAY: direct N7 narrow band (datasheet 1.5 m span; top tap 1 m above overflow).  The
    #   transmitter reads the PHYSICAL liquid head through the fixed instrument geometry — LT-322504 tracks
    #   the 322R001 mass balance and NOTHING else (2026-07-03 order: no coupling/pinning to plant load; the
    #   former design-valve SHADOW reference + _load_gate machinery is DELETED).  At the design head
    #   L = REACT_LEVEL_DES_M = 20.0 m it reads exactly NLL 80 %, so the design boot and short holds stay
    #   bit-exact.  KNOWN CONSEQUENCE (was the shadow's raison d'etre): the static design seed is not the
    #   coupled-loop fixed point — over ~5 h the loop relaxes (reactor head −0.49 m / −1.9 %) and the 1.5 m
    #   band amplifies that sag 16.7x (80 % -> ~48 %); that drift is now the INTENDED mass-balance reading.
    #   Saturates 0/100 % off the 1.5 m band like the real transmitter.  HOLDUP, discharge hydraulics, flood
    #   guard and loop P_min all stay on the PHYSICAL head s.react_level_pct.
    _H_liq_react          = REACT_LIQ_H_M * s.react_level_pct / 100.0            # physical head, m
    s.react_lt322504_pct  = clamp(REACT_LEVEL_NLL_PCT
                                  + (_H_liq_react - REACT_LEVEL_DES_M) / REACT_LT_SPAN_M * 100.0,
                                  0.0, 100.0)
    # carryover molar vector = reactor-overflow composition scaled by (entrained mass / overflow mass):
    #   ν_carry,k = ṁ_carry · ν_ov,k / Σ_j ν_ov,j·MW_j  -> preserves overflow mole fractions exactly.
    _ov_mass_kgh      = sum(react["overflow_kmolh"][k] * MW_COMP[k] for k in react["overflow_kmolh"])
    react_carry_kmolh = ({k: react["overflow_kmolh"][k] * (react_carry_kgh / _ov_mass_kgh)
                          for k in react["overflow_kmolh"]}
                         if (react_carry_kgh > 0.0 and _ov_mass_kgh > 0.0) else None)

    # LT-322E002 HPCC liquid inventory (Euler): carbamate condensation make in - ejector fwd out.
    #   phi_in  = live HPCC liquid make / design make  (stripper-gas condensation is motive-indep)
    #   phi_fwd = phi_m^2 forward circulation out (ejector developed head)
    # ISSUE-c/e: the old outflow term was phi_fwd ALONE (level-independent) -> a pure integrator: any
    # in!=out mismatch wound the level to a rail (floods to 100 % at 70 % load, drifts even at design).
    # A condenser sump drains by gravity head, so make the outflow rise with level: phi_out =
    # phi_fwd·(L/NLL).  This closes the loop -> a stable first-order lag that SETTLES at the bounded
    # equilibrium L_eq = NLL·(phi_in/phi_fwd) instead of railing.  At design phi_in = phi_fwd = 1 and
    # L = NLL -> phi_out = phi_fwd -> dL = 0 (NLL is now an exact fixed point; bit-exact design).
    _hpcc_liq_des = HPCC_LIQ_DES_LIVE or HPCC_LIQ_DES_KGH      # live settled ref once pinned
    phi_in_hpcc  = (hpcc["liq_kgh"] / _hpcc_liq_des) if _hpcc_liq_des else phi_fwd
    phi_out_hpcc = phi_fwd * (s.hpcc_level_pct / HPCC_LEVEL_NLL_PCT)
    dL_hpcc      = k_loop_fill * (phi_in_hpcc - phi_out_hpcc) * 100.0 * dt / (HPCC_TAU_FILL_MIN * 60.0)
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
    #   vent_frac = m_og/(m_og_des·s) = R^((θ−θ_des)/100)·√(ΔP/ΔP_des);  θ_des = design opening (50%,
    #   demand-met), equal-% trim per datasheet (must match hv_322604 so the diagnostic vent flow and
    #   the back-pressure penalty use one characteristic).  Pinch below design (vent_frac<1) starves the
    #   inert vent -> uncondensed inerts accumulate and integrate PT-329201 up.  Prior-step p_syn for ΔP.
    dP_vent   = max(s.p_syn_bara - SCRUB_HV604_P_OUT, 0.0)
    vent_frac = _eq_pct(s.HIC_322604, SCRUB_HIC604_DES_PCT) * math.sqrt(dP_vent / SCRUB_HV604_DP_DES)
    scrub = scrub_322e003(react["offgas_kmolh"], react["co2_scale"], tic["pv"], m_ccw_kgh,
                          vent_ratio=nu, nc_act=react_nc_ratio(react["overflow_kmolh"]),
                          hic604_pct=s.HIC_322604,
                          liq_carry_kmolh=react_carry_kmolh, t_carry_c=s.react_T_overflow,
                          choke_level_pct=s.scrub_level_pct, spindle_phi=_phi_sp_theta)
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
    # L3-2c cold-start fix: loop-mass fraction (mean of the three HP liquid inventories vs their design
    #   NLL) hoisted above pt_fwd so the BASE stripper forward-push deviation is ALSO inventory-gated.  An
    #   empty loop has no circulation to develop stripper overhead, so it must not push the PT target above
    #   design -- previously pt_fwd overshot to ~162 barg at cold start (pb_push ungated), which made the
    #   model-free pressurisation tau read short (§6.4).  == 1.0 at design (levels at NLL) AND pb_push == 0
    #   -> pt_fwd == SYN_P_DES_BARA exactly (design SS bit-exact); -> pure SYN_P_TAU_FILL_MIN lag toward
    #   design as the loop empties (§6.1 emergent tau, never a hard lag on the pressure state).
    m_loop_frac = clamp((s.react_level_pct + s.hpcc_level_pct + s.strip_level)
                        / (REACT_LEVEL_NLL_PCT + HPCC_LEVEL_NLL_PCT + STRIP_LEVEL_SP_DES), 0.0, 1.0)
    pt_fwd    = SYN_P_DES_BARA * (1.0 + m_loop_frac * SYN_P_COUPLING * pb_push)
    # L3-2b inventory gate on the PT forcing offsets.  m_loop_frac (the same loop-mass fraction used
    #   for the PT floor below) multiplies EVERY additive forcing term so an empty / part-filled loop
    #   cannot saturate p_target: the deficit / vent / conversion push can only develop as the HP
    #   liquid inventories physically accumulate.  == 1.0 at design (levels at NLL) -> forcing
    #   unchanged -> design steady state stays bit-exact; -> 0 as the loop empties -> cold-start
    #   pressurisation tracks inventory fill (emergent tau), never a hard lag on the pressure state
    #   (report §6.1 / §6.4 remediation option 2).  m_loop_frac computed above (hoisted for pt_fwd gate).
    # Fix-2: dimensionless conversion-deficit forcing Π = κ·δ_X injected ADDITIVELY into the PT
    # target.  When the reactor under-converts (low N/C / high H/C), the unconverted NH3 + CO2 flash
    # to the synthesis loop and aggressively pressurise it: Π·P_des bar of extra forcing.  δ_X is
    # clamped >= 0 (Fix-2), so at/above design Π = 0 -> no spurious depressurisation at high N/C.
    Pi_conv   = REACT_PI_KAPPA * react["delta_X"]
    pt_target = pt_fwd + m_loop_frac * (
                         SYN_P_DEFICIT_GAIN * max(1.0 - rho_cond, 0.0) * SYN_P_DES_BARA
                       + SYN_P_VENT_GAIN * max(1.0 - vent_frac, 0.0) * SYN_P_DES_BARA
                       + Pi_conv * SYN_P_DES_BARA)  # HV-322604 vent: ONE-SIDED inert-purge deficit only
                                                    #   (close<des -> inerts accumulate -> PT up; open>=des
                                                    #   -> purge is supply-limited, no extra venting -> PT
                                                    #   unchanged).  Tiny purge valve cannot crash HP P.
    # L3-2 inventory-aware PT floor: a totally empty loop must be able to bottom out at atmospheric,
    #   not a hard 120 bar.  Loop-mass fraction = mean of the three HP liquid inventories vs their design
    #   NLL (LT-322504 80%, LT-322E002 50%, LT-322501 50%); == 1.0 at design -> P_min == 120 bar (the
    #   static SYN_P_MIN_BARA preserved exactly), -> 1.0 atm as the loop empties.
    #       P_min = 1.0 + 119.0 * clamp(M_loop / M_loop_des, 0, 1)
    #   (m_loop_frac computed above, at the forcing gate.)
    p_syn_min   = 1.0 + 119.0 * m_loop_frac
    # Inventory-emergent pressurisation tau: an EMPTY loop (m_loop_frac -> 0) has little condensable/
    #   vapour inventory to build head, so PT climbs on the sourced cold-start constant SYN_P_TAU_FILL_MIN
    #   (57.8 min, 06-03 Section 1.2 field FOPTD); as the three HP liquid inventories fill toward NLL the
    #   constant relaxes linearly to the warm op-pt SYN_P_TAU_MIN (4 min).  tau EMERGES from inventory fill
    #   -- NOT a hard lag on the pressure state (report Section 6.1: never a fudge lag; tune physical
    #   inventory).  At design m_loop_frac == 1 -> tau_eff == SYN_P_TAU_MIN and (pt_target - p_syn) == 0,
    #   so the steady-state hold is bit-exact regardless of tau_eff.
    _tre = 4.0   # relax-schedule shape (Smith-calibrated to Section 6.4 band); holds tau_eff at
                 #   SYN_P_TAU_FILL_MIN until m_loop_frac -> 1, then collapses to warm SYN_P_TAU_MIN
    tau_eff_min = SYN_P_TAU_FILL_MIN + m_loop_frac ** _tre * (SYN_P_TAU_MIN - SYN_P_TAU_FILL_MIN)
    s.p_syn_bara = clamp(s.p_syn_bara + (dt / (tau_eff_min * 60.0)) * (pt_target - s.p_syn_bara),
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
    # --- Option 3: 322E003 sump inventory ODE (Euler) ---------------------------------------------
    #   dM/dt = ṁ_cond,in − ṁ_entrain.  ṁ_cond,in = the condensation/absorption make this tick
    #   (post-mushy-zone overflow mass); ṁ_entrain = what the ejector actually pulled this tick
    #   (ej["suction_kgh"], from the non-linear curve, computed earlier this step).  At design
    #   both == EJ_SUC_TOT_DES -> dM=0, level holds NLL.  Ejector stall -> entrain<<cond -> M rises.
    m_cond_in = sum(scrub["overflow_kmolh"][k] * MW_COMP[k] for k in scrub["overflow_kmolh"])
    s.scrub_holdup_kg = clamp(s.scrub_holdup_kg + (m_cond_in - ej["suction_kgh"]) * (dt / 3600.0),
                              0.0, SCRUB_HOLDUP_MAX_KG)
    s.scrub_level_pct = clamp(s.scrub_holdup_kg / SCRUB_HOLDUP_NLL_KG * SCRUB_LEVEL_NLL_PCT,
                              0.0, 100.0)
    hv604 = hv_322604(scrub["offgas_kmolh"], scrub["T_offgas"], s.HIC_322604, scrub["P_offgas"])
    # L3-7 HV-322604 off-gas: external steam-tracing holds the 60 C baseline; flag only when extreme JT
    #   cooling overwhelms the jacket (T_out < 20 C).  Flow NOT restricted (gas line) -> fouling warning.
    s.flags["CARBAMATE_DEPOSITION"] = (hv604["T_out"] < 20.0)
    TDY_329125 = scrub["t_ccw_out"] - tic["pv"]   # TT-329125 − TIC-329005 (condensation quality)
    q_e004_kw  = scrub["q_ccw_kw"]                # 329E004 tempered-water-cooler duty (loop closure)

    # ----- Section-322 tear display lags (compute ONCE per tick -> shared by both telemetry views) -----
    #   Each published downstream temperature / level / analyzer is relaxed toward its algebraic target
    #   with a real time constant (see _lag1 + the TAU block) so an upstream stream-property or
    #   composition step RAMPS the indicator instead of snapping in a single 0.1 s tick.  Computed once
    #   here because several tags appear in two telemetry blocks; calling the relax twice would double-step.
    d_TT322012  = _lag1(s.tlag, "TT322012", ej["T_C"],                                 EJ_T_TAU_S,      dt)
    d_TT322013  = _lag1(s.tlag, "TT322013", strip["T_top"],                            STRIP_T_TAU_S,   dt)
    d_TT322004  = _lag1(s.tlag, "TT322004", T_bot_disp,                                STRIP_T_TAU_S,   dt)
    d_TT323001  = _lag1(s.tlag, "TT323001", TT_323001,                                 STRIP_T_TAU_S,   dt)
    d_TT322010  = _lag1(s.tlag, "TT322010", hpcc["T_prod"],                            HPCC_T_TAU_S,    dt)
    d_HPCC_P    = _lag1(s.tlag, "HPCCP",    hpcc["P_bub"],                             HPCC_P_TAU_S,    dt)
    d_TT322002  = _lag1(s.tlag, "TT322002", scrub["T_overflow"],                       SCRUB_T_TAU_S,   dt)
    d_TT322011  = _lag1(s.tlag, "TT322011", scrub["T_offgas"],                         OFFGAS_T_TAU_S,  dt)
    d_TT322011l = _lag1(s.tlag, "TT322011l", hv604["T_out"],                           OFFGAS_T_TAU_S,  dt)
    d_TT329125  = _lag1(s.tlag, "TT329125", scrub["t_ccw_out"],                        CCW_T_TAU_S,     dt)
    d_AT322701  = _lag1(s.tlag, "AT322701", react_nc_ratio(react["overflow_kmolh"]),  AT_322701_TAU_S, dt)

    # ==================================================================================
    #  UNIT 323 - LP RECIRCULATION & PRE-EVAPORATION  (rigorous state-space, conservative)
    #  Boundary feed = 322E001 letdown bottoms:  m_feed = drain_kgh (kg/h) at T = TT_323001
    #  (post-LV-322501 flash, un-lagged).  Four lumped liquid stages; each stage carries an
    #  inventory ODE  dM/dt = m_in - m_vap - m_out  and a well-mixed energy ODE
    #        M*cp*dT/dt = m_in*cp*(T_in - T) + Q - m_vap*lambda
    #  integrated with the live sub-step dt.  Vapor rates are the DESIGN mass split fractions
    #  of the live inflow, so mass closes every tick by construction:
    #        m_feed == SUM(vapor) + product_317 + d(inventory)/dt .
    #  All latent/duty coefficients were back-solved at the design seed, so at boot every
    #  dM/dt == dT/dt == 0 (the MB/PFD anchors are the exact fixed point).
    # ==================================================================================
    cp323      = R323_CP_SOLN
    m_feed_323 = max(drain_kgh, 0.0)                       # live 322E001 bottoms -> 323C003 (kg/h)
    T_feed_323 = TT_323001                                 # C, post-LV-322501 flash (un-lagged)

    # ---- Stage 1: Rectifying Column 323C003 + Recirc Heater 323E002  (hold 135 C) ------------
    #  Cascade  TIC-323007 (temp master, EU) -> PIC-329202 (LP-steam chest-P slave) -> heater duty.
    tic07_op  = _ctrl_ipd(s.TIC_323007, s.r323_c003_T, dt)                        # steam-P demand (bar a)
    pic02_pv  = clamp(s.PIC_329202["op"] / 100.0 * R323_P_STEAM_SUP, 0.0, R323_P_STEAM_SUP)  # chest P from last stroke
    pic02_op  = _ctrl_ipd(s.PIC_329202, pic02_pv, dt, cas_sp=tic07_op)            # steam valve stroke (%)
    p_chest_e002 = clamp(pic02_op / 100.0 * R323_P_STEAM_SUP, 0.02, R323_P_STEAM_SUP)
    Q_e002_kw = R323_E002_UA_KW * (tsat_steam(p_chest_e002) - s.r323_c003_T)      # heater duty (kW)
    m_305     = R323_PHI_V305 * m_feed_323                                        # top vapor -> 323E003 LPCC (305, kg/h)
    lvl_c003  = clamp(s.r323_c003_M / R323_C003_M_FULL * 100.0, 0.0, 100.0)
    lv501_op  = _ctrl_ipd(s.LIC_323501, lvl_c003, dt)                             # LV-323501 stroke (%)
    m_314     = max(R323_M314_DES * (lv501_op / R323_LV501_OP_DES), 0.0)          # bottom drain -> flash (kg/h)
    P_c003    = (m_feed_323 / 3600.0 * cp323 * (T_feed_323 - s.r323_c003_T)
                 + Q_e002_kw - m_305 / 3600.0 * R323_LAMBDA_305)                  # net kW on holdup
    M_c003_pre = s.r323_c003_M
    s.r323_c003_T = s.r323_c003_T + P_c003 * dt / max(M_c003_pre * cp323, 1e-6)
    s.r323_c003_M = max(M_c003_pre + (m_feed_323 - m_305 - m_314) / 3600.0 * dt, 1.0)
    #  PT-323201 hydraulic coupling: forward pressure accumulation from live top-vapour flow (305).
    #  Opening LV-322501 raises drain_kgh -> m_feed_323 -> m_305 > design => P relaxes UP toward target.
    p_c003_tgt = R323_C003_P_BARA + R323_C003_P_GAIN * (m_305 - R323_M305_DES) / R323_M305_DES
    s.r323_c003_P = clamp(s.r323_c003_P + (p_c003_tgt - s.r323_c003_P) / R323_C003_P_TAU_S * dt, 1.0, 12.0)

    # ---- Stage 2: Flash Tank 323F004  (adiabatic letdown 4.1 -> 1.13 bar, hold 106 C) --------
    m_701     = R323_PHI_V701 * m_314                                             # flash vapor -> LPCC (701, kg/h)
    lvl_f004  = clamp(s.r323_f004_M / R323_F004_M_FULL * 100.0, 0.0, 100.0)
    lv505_op  = _ctrl_ipd(s.LIC_323505, lvl_f004, dt)                            # LV-323505 stroke (%)
    m_319     = max(R323_M319_DES * (lv505_op / R323_LV505_OP_DES), 0.0)          # drain -> pre-evaporator (kg/h)
    P_f004    = (m_314 / 3600.0 * cp323 * (s.r323_c003_T - s.r323_f004_T)
                 - m_701 / 3600.0 * R323_LAMBDA_701)                              # adiabatic (no Q) kW
    M_f004_pre = s.r323_f004_M
    s.r323_f004_T = s.r323_f004_T + P_f004 * dt / max(M_f004_pre * cp323, 1e-6)
    s.r323_f004_M = max(M_f004_pre + (m_314 - m_701 - m_319) / 3600.0 * dt, 1.0)
    #  323F004 hydraulic coupling: forward pressure accumulation from live flash-vapour flow (701).
    #  Opening LV-323501 raises m_314 -> m_701 > design => flash-drum P relaxes UP (feeds PIC-323203 LP node).
    p_f004_tgt = R323_F004_P_BARA + R323_F004_P_GAIN * (m_701 - R323_M701_DES) / R323_M701_DES
    s.r323_f004_P = clamp(s.r323_f004_P + (p_f004_tgt - s.r323_f004_P) / R323_F004_P_TAU_S * dt, 0.3, 6.0)

    # ---- Stage 3: Pre-evaporator 323F010 + Heater 323E010  (vacuum 0.46 bar, hold 99 C) ------
    #  Cascade  TIC-323012 (temp master) -> PIC-329208 (LP-steam chest-P slave) -> heater duty.
    #  Un-controlled separator -> modelled pass-through (m_317 = m_319 - m_evap); holdup ~ const.
    tic12_op  = _ctrl_ipd(s.TIC_323012, s.r323_f010_T, dt)                        # steam-P demand (bar a)
    pic08_pv  = clamp(s.PIC_329208["op"] / 100.0 * R323_P_STEAM_SUP, 0.0, R323_P_STEAM_SUP)
    pic08_op  = _ctrl_ipd(s.PIC_329208, pic08_pv, dt, cas_sp=tic12_op)            # steam valve stroke (%)
    p_chest_e010 = clamp(pic08_op / 100.0 * R323_P_STEAM_SUP, 0.02, R323_P_STEAM_SUP)
    Q_e010_kw = R323_E010_UA_KW * (tsat_steam(p_chest_e010) - s.r323_f010_T)      # heater duty (kW)
    m_evap    = R323_PHI_VEVAP * m_319                                            # evaporated water -> vac (kg/h)
    m_317     = max(m_319 - m_evap, 0.0)                                          # concentrated product -> tank (kg/h)
    P_f010    = (m_319 / 3600.0 * cp323 * (s.r323_f004_T - s.r323_f010_T)
                 + Q_e010_kw - m_evap / 3600.0 * R323_EVAP_LAMBDA)               # net kW on holdup
    M_f010_pre = s.r323_f010_M
    s.r323_f010_T = s.r323_f010_T + P_f010 * dt / max(M_f010_pre * cp323, 1e-6)
    s.r323_f010_M = max(M_f010_pre + (m_319 - m_evap - m_317) / 3600.0 * dt, 1.0)

    # ---- Stage 4: Urea Solution Tank 323D002  (atmospheric, two-compartment) ------------------
    #  Comp I (80 m3, active flow-through): in = m_317, out = m_324 via LIC-323507 -> FIC-324401
    #  -> FV-324401.  Comp II (300 m3, passive): receives Comp-I weir overflow only, no outflow.
    flow_span_324 = R323_M324_DES / 1000.0 / (R323_FV401_OP_DES / 100.0)          # t/h at 100% stroke
    lvl_d002_I = clamp(s.r323_d002_M_I / R323_D002_M_I_FULL * 100.0, 0.0, 100.0)
    lic07_op  = _ctrl_ipd(s.LIC_323507, lvl_d002_I, dt)                           # product-flow demand (t/h)
    #  FT-324401 measured flow is a first-order lag of the delivered valve flow (tau=5 s transmitter
    #  + stroke dynamics).  Lagging the PV is physically real AND numerically essential: the valve is
    #  a pure-gain plant (flow = op/100*span, span=185.5 t/h => process gain 1.855 t/h per %), so an
    #  UNLAGGED velocity-form PV would give a discrete loop pole |z|=Kc*G=2.78>1 (bang-bang divergence).
    #  The lag makes -(pv-pv1) see gradual change, restoring a stable, bumpless (seed-exact) loop.
    prior_flow_324 = s.FIC_324401["op"] / 100.0 * flow_span_324                   # delivered flow last tick (t/h)
    fic01_pv  = _lag1(s.tlag, "R323_FIC324", prior_flow_324, 5.0, dt)             # measured flow (t/h, lagged)
    fic01_op  = _ctrl_ipd(s.FIC_324401, fic01_pv, dt, cas_sp=lic07_op)            # FV-324401 stroke (%)
    m_324     = max(fic01_op / 100.0 * flow_span_324, 0.0) * 1000.0               # product -> Unit 324 (kg/h)
    M_I_new   = s.r323_d002_M_I + (m_317 - m_324) / 3600.0 * dt
    d002_overflow = 0.0
    if M_I_new > R323_D002_M_I_FULL:                                              # weir spill -> Comp II
        d002_overflow = M_I_new - R323_D002_M_I_FULL
        M_I_new = R323_D002_M_I_FULL
    s.r323_d002_M_I  = max(M_I_new, 1.0)
    s.r323_d002_M_II = clamp(s.r323_d002_M_II + d002_overflow, 0.0, R323_D002_M_II_FULL)

    # ======================================================================
    #  UNITS 323-2 / 328-1 / 328-2  — LP RECIRCULATION & DESORPTION
    #  Feed-forward 9-stage state-space model (dependency order).  Every
    #  holdup ODE  dM/dt = Σṁ_in − ṁ_vap − ṁ_out = 0 and every thermal ODE
    #  M·cp·dT/dt = Σṁ_in·cp·(T_in−T) + Q − ṁ_vap·λ = 0 at the design seed
    #  (λ / UA back-solved in the constants block above).  Seven recycle
    #  tears are read one-tick-delayed via s.tlag.get(key, design) and
    #  rewritten at the end -> stable, bit-exact at design.  Live upstream
    #  feeds: m_305 (323C003 top vapour), m_701 (323F004 flash vapour),
    #  hv604 (HV-322604 off-gas -> 322C001).
    # ======================================================================
    mv011_prev = s.tlag.get("R3232_v011", R3232_E011_MV_DES)
    m748_prev  = s.tlag.get("R328_748",   R328_C002_M748_DES)
    m750_prev  = s.tlag.get("R328_750",   R328_C002_M750_DES)
    m775_prev  = s.tlag.get("R328_775",   R328_C002_M775_DES)
    m718A_prev = s.tlag.get("R3232_718A", R3232_M718A_DES)
    m744_prev  = s.tlag.get("R3232_744",  R3232_E003_M744_DES)
    m718B_prev = s.tlag.get("R3232_718B", R3232_M718B_DES)
    m931_prev  = s.tlag.get("R328_M931",  R328_C004_M931_DES)

    # ----- Stage 1 : 323C005 vent scrub -> 328V001 -> Comp-I feed ---------
    Tc005    = s.a323_c005_T
    m_makeup = A323_C005_MAKEUP     # demin make-up from an unmodelled utility header: constant per
    #   ui_guidelines.md §4.  FIC-323418 used to drive this, but its OEM service is "ACA FROM 323P8A/B"
    #   (Master_PID_Tuning_Constants.md:14) -- the 718B leg -- so that binding was false and is gone.
    #   Modelling gap: this leg has no flow controller of its own until the make-up header is built.
    in_c005  = mv011_prev + m_makeup
    bot_c005 = A323_C005_BOT_DES * (s.a323_c005_M / A323_C005_M_DES)      # -> V001 @ 55°C
    P_c005   = (mv011_prev/3600.0*R3232_CP*(R3232_E011_T       - Tc005)
                + m_makeup/3600.0*4.0   *(A323_C005_MAKEUP_T   - Tc005)
                + mv011_prev/3600.0*A323_C005_LAM)
    s.a323_c005_T = Tc005 + P_c005*dt/max(s.a323_c005_M*R3232_CP, 1e-6)
    s.a323_c005_M = max(s.a323_c005_M + (in_c005 - bot_c005)/3600.0*dt, 1.0)

    # ----- Stage 2 : 328D003  Comp-I (formation) + Comp-II (collector) ----
    TI       = s.a328_d003_TI
    m_401    = _fic_flow(s.FIC_323401, R3232_E011_M401_DES, 50.0, s.tlag, "F_323401", dt)
    m_402    = _fic_flow(s.FIC_323402, R3232_E011_M402_DES, 50.0, s.tlag, "F_323402", dt)
    m_735    = R328_C002_M738_DES * (s.a328_d003_MI / A328_D003_MI_DES)   # -> 738 via 328E007
    in_compI = A328_D003_M719 + A328_D003_M720 + A328_D003_M721 + bot_c005
    out_compI= m_735 + m_401 + m_402
    P_compI  = ((A328_D003_M719*(A328_D003_M719_T - TI)
                 + A328_D003_M720*(A328_D003_M720_T - TI)
                 + A328_D003_M721*(A328_D003_M721_T - TI)
                 + bot_c005     *(A328_D003_V001_T  - TI))/3600.0*A328_CP
                + in_compI/3600.0*A328_D003_LAM_I)
    s.a328_d003_TI = TI + P_compI*dt/max(s.a328_d003_MI*A328_CP, 1e-6)
    s.a328_d003_MI = max(s.a328_d003_MI + (in_compI - out_compI)/3600.0*dt, 1.0)
    TII      = s.a328_d003_TII
    run_p002 = s.aux_pumps["322P002A"]["on"] or s.aux_pumps["322P002B"]["on"]
    m_755    = A328_M755_DES * (s.a328_d003_MII / A328_D003_MII_DES) * (1.0 if run_p002 else 0.0)
    P_compII = m744_prev/3600.0*A328_CP*(R3232_E003_T744 - TII)          # 744 in @ 44 = TII
    s.a328_d003_TII = TII + P_compII*dt/max(s.a328_d003_MII*A328_CP, 1e-6)
    s.a328_d003_MII = max(s.a328_d003_MII + (m744_prev - m_755)/3600.0*dt, 1.0)

    # ----- Stage 3 : 328C002  Desorber-I (bottoms 139°C, floats PIC-328202)
    Tc002    = s.a328_c002_T
    m_738    = m_735
    in_c002  = m_738 + m748_prev + m750_prev + m775_prev
    m_737    = R328_C002_PHI737 * in_c002                                 # OVHD split -> 328D001
    lvl_c002 = s.a328_c002_M / R328_C002_M_DES * 50.0
    lic503_op= _ctrl_ipd(s.LIC_328503, lvl_c002, dt)
    m_743    = R328_C002_M743_DES * (lic503_op / 50.0)                    # bottoms -> hydrolyser
    sens_c002= ((m_738*(R328_C002_T738 - Tc002)
                 + m775_prev*(R328_D001_T   - Tc002)
                 + m748_prev*(R328_C002_T748 - Tc002)
                 + m750_prev*(R328_C002_T750 - Tc002))/3600.0*R328_CP)
    P_c002   = (sens_c002 + m748_prev/3600.0*R328_C002_LAM748
                + m750_prev/3600.0*R328_C002_LAM750
                - m_737/3600.0*R328_C002_LAM737)
    s.a328_c002_T = Tc002 + P_c002*dt/max(s.a328_c002_M*R328_CP, 1e-6)
    s.a328_c002_M = max(s.a328_c002_M + (in_c002 - m_737 - m_743)/3600.0*dt, 1.0)

    # ----- Stage 4 : 328C003  Hydrolyser (200°C, MP-steam 911) -----------
    Tc003    = s.a328_c003_T
    m_746    = m_743                                                     # via 328E021
    # 328E021 cold outlet (stream 746, TT-328009): C002 bottoms 139 heated by C003 bottoms 200.
    #   eps in (0,1) => T_746 is a convex combination of the two live inlets and can never cross
    #   either, so no clamp is needed.  At design 139 + (51/61)*(200-139) = 190.0 exactly.
    T_746    = s.a328_c002_T + R328_E021_EPS_T * (Tc003 - s.a328_c002_T)
    m_911    = _fic_flow(s.FIC_326402, R328_C003_M911_DES, 50.0, s.tlag, "F_326402", dt)
    in_c003  = m_746 + m_911
    pic203b_op = _ctrl_ipd(s.PIC_328203, s.a328_c003_P, dt)
    m_748    = R328_C003_M748_DES * (pic203b_op / R328_C003_PV_OP_DES)    # OVHD relief -> 328C002
    gen748   = R328_C003_PHI748 * in_c003
    lvl_c003 = s.a328_c003_M / R328_C003_M_DES * 50.0
    lic505_op= _ctrl_ipd(s.LIC_328505, lvl_c003, dt)
    m_747    = R328_C003_M747_DES * (lic505_op / 50.0)                    # bottoms -> desorber-II
    sens_c003= m_746/3600.0*R328_CP*(T_746 - Tc003)
    P_c003   = sens_c003 + m_911/3600.0*R328_C003_M911_DH - m_748/3600.0*R328_C003_LAM748
    s.a328_c003_P = max(s.a328_c003_P + R328_C003_P_KP*(gen748 - m_748)/3600.0*dt, 0.1)
    s.a328_c003_T = Tc003 + P_c003*dt/max(s.a328_c003_M*R328_CP, 1e-6)
    s.a328_c003_M = max(s.a328_c003_M + (in_c003 - m_748 - m_747)/3600.0*dt, 1.0)

    # ----- Stage 5 : 328C004  Desorber-II (143°C, LP-steam 931, FFIC) -----
    Tc004    = s.a328_c004_T
    m_749    = m_747                                                     # via 328E021 (148°C)
    ffic_pv  = _lag1(s.tlag, "FF_ratio", m931_prev/max(m_738, 1e-6), 5.0, dt)
    ffic_op  = _ctrl_ipd(s.FFIC_328401, ffic_pv, dt)                     # 931-flow demand (kg/h)
    m_931    = _fic_flow(s.FIC_328401, R328_C004_M931_DES, 50.0, s.tlag, "F_328401", dt, cas_sp=ffic_op)
    in_c004  = m_749 + m_931
    m_750    = R328_C004_PHI750 * in_c004                                # OVHD split -> 328C002
    lvl_c004 = s.a328_c004_M / R328_C004_M_DES * 50.0
    lic504_op= _ctrl_ipd(s.LIC_328504, lvl_c004, dt)
    m_739    = R328_C004_M739_DES * (lic504_op / 50.0)                    # bottoms -> 328E007 boundary
    sens_c004= m_749/3600.0*R328_CP*(R328_C004_T749 - Tc004)
    P_c004   = sens_c004 + m_931/3600.0*R328_C004_M931_DH - m_750/3600.0*R328_C004_LAM750
    s.a328_c004_T = Tc004 + P_c004*dt/max(s.a328_c004_M*R328_CP, 1e-6)
    s.a328_c004_M = max(s.a328_c004_M + (in_c004 - m_750 - m_739)/3600.0*dt, 1.0)

    # ----- Stage 6 : 328D001  Desorber-I reflux drum (61°C, 328E004) -----
    Td001    = s.a328_d001_T
    in_d001  = m_737 + m718A_prev
    pic202b_op = _ctrl_ipd(s.PIC_328202, s.a328_d001_P, dt)
    m_786_d001 = R328_D001_M786_DES * (pic202b_op / R328_D001_PV_OP_DES)  # vent -> 323E011
    gen786   = R328_D001_M786_DES * (m_737 / R328_D001_M737_DES)
    m_775    = _fic_flow(s.FIC_328404, R328_D001_M775_DES, R328_D001_FIC404_OP_DES, s.tlag, "F_328404", dt)
    lvl_d001_328 = s.a328_d001_M / R328_D001_M_DES * R328_D001_LVL_SP
    lic501_op= _ctrl_ipd(s.LIC_328501, lvl_d001_328, dt)
    m_776    = R328_D001_M776_DES * (lic501_op / R328_D001_LV_OP_DES)     # draw -> 323E003
    tic002_op= _ctrl_ipd(s.TIC_328002, Td001, dt)
    Q_e004   = R328_E004_Q_DES_KW * (tic002_op / R328_E004_TV_OP_DES)
    sens_d001= ((m_737*(R328_C002_T_TOP - Td001)
                 + m718A_prev*(R328_D001_T718A - Td001))/3600.0*R328_CP)
    P_d001   = sens_d001 + m_737/3600.0*R328_D001_LAM737 - Q_e004
    s.a328_d001_P = max(s.a328_d001_P + R328_D001_P_KP*(gen786 - m_786_d001)/3600.0*dt, 0.1)
    s.a328_d001_T = Td001 + P_d001*dt/max(s.a328_d001_M*R328_CP, 1e-6)
    s.a328_d001_M = max(s.a328_d001_M + (in_d001 - m_786_d001 - m_775 - m_776)/3600.0*dt, 1.0)

    # ----- Stage 7 : 322C001  LP absorber (43°C, live GCB off-gas) --------
    Tc001    = s.a328_c001_T
    gcb_m    = hv604["mass_kgh"]
    gcb_T    = hv604["T_out"]
    pic201_op= _ctrl_ipd(s.PIC_322201, s.a328_c001_P, dt)
    lvl_c001 = s.a328_c001_M / A328_C001_M_DES * 50.0
    lic502c_op = _ctrl_ipd(s.LIC_322502, lvl_c001, dt)
    m_756    = A328_M756_DES * (lic502c_op / A328_LIC_OP_DES)             # liquor draw -> 323E003
    Q_flood  = A328_QFLOOD_KW if s.XV_322915 else 0.0                     # trip 22.1 steam flood
    if A328_GCB_DES is None:                                              # pre-pin: design absorb, hold P
        abs_c001  = A328_ABS_DES
        vent_c001 = max(gcb_m - abs_c001, 0.0)
    else:                                                                # post-pin: live off-gas
        abs_c001  = A328_PHI_ABS * gcb_m
        vent_c001 = A328_VENT_DES * (pic201_op / A328_PIC_OP_DES)
        s.a328_c001_P = max(s.a328_c001_P
                            + A328_C001_P_KP*((gcb_m - abs_c001) - vent_c001)/3600.0*dt, 0.1)
    if A328_LAMBDA_ABS is not None:
        sens_c001 = ((m_755*(A328_M755_T - Tc001) + A328_CPL_DES*(A328_CPL_T - Tc001))/3600.0*A328_CP
                     + gcb_m*(gcb_T - Tc001)/3600.0*A328_CP)
        P_c001    = sens_c001 + abs_c001/3600.0*A328_LAMBDA_ABS + Q_flood
        s.a328_c001_T = Tc001 + P_c001*dt/max(s.a328_c001_M*A328_CP, 1e-6)
    s.a328_c001_M = max(s.a328_c001_M + (m_755 + A328_CPL_DES + abs_c001 - m_756)/3600.0*dt, 1.0)

    # ----- Stage 8 : 323E003 + 323D001  LPCC (74°C, tempered water) -------
    Te003    = s.r3232_e003_T
    in_e003  = m_305 + m718B_prev + m_776 + R3232_M797_DES + m_756
    pic202_op= _ctrl_ipd(s.PIC_323202, s.r3232_d001_P, dt)
    m_321    = R3232_E003_M321_DES * (pic202_op / R3232_E003_PV_OP_DES)   # vent -> 323E011
    gen321   = R3232_E003_PHI321 * (m_305 + R3232_M797_DES)
    m_744    = _fic_flow(s.FIC_328402, R3232_E003_M744_DES, 50.0, s.tlag, "F_328402", dt)  # wash -> Comp-II
    lvl_d001_323 = s.r3232_d001_M / R3232_D001_M_DES * R3232_D001_LVL_SP
    lic502_op= _ctrl_ipd(s.LIC_323502, lvl_d001_323, dt)                 # master
    rpm_pv   = _lag1(s.tlag, "S_323901", s.SIC_323901["op"], 3.0, dt)
    sic_op   = _ctrl_ipd(s.SIC_323901, rpm_pv, dt, lic502_op)            # cascade slave (speed)
    m_308    = R3232_E003_M308_DES * (sic_op / R3232_P001_RPM_DES)        # condensate -> boundary
    #   Tempered-water circuit (PFD 1102 supply / 1103 return).  TV-323013A admits cold make-up, TV-323013B
    #   bypasses hot return -> split-range opposites off one op.  House normalized-stroke valve char: at
    #   op == op_des the ratio is 1 -> T_ss == R3232_TW_SUP_T == sp -> PV stationary -> du == 0 (design exact).
    #   Duty now rides the physical driving force (live TW mean vs shell) instead of a linear op fudge:
    #   at design 1000*(74 - 60) == 14000 kW, identical to the retired (tic13_op/50) form.
    tva_op   = s.TIC_323013["op"]                              # prior-step TV-323013A stroke
    T_tw_ss  = clamp(R3232_TW_RET_T - (R3232_TW_RET_T - R3232_TW_SUP_T)
                     * (tva_op / max(R3232_TV13_DES_PCT, 1e-6)), 20.0, R3232_TW_RET_T)
    T_tw_sup = _lag1(s.tlag, "R3232_TW_SUP", T_tw_ss, R3232_TW_TAU_S, dt)   # stream 1102 (55 °C)
    T_tw_ret = s.tlag.get("R3232_TW_RET", R3232_TW_RET_T)      # prior-step state; breaks the algebraic loop
    tic13_op = _ctrl_ipd(s.TIC_323013, T_tw_sup, dt)           # PV = TW supply, NOT the shell temp
    Q_e003   = R3232_E003_UA_KW * (Te003 - 0.5*(T_tw_sup + T_tw_ret))
    T_tw_ret = T_tw_sup + (R3232_TW_RET_T - R3232_TW_SUP_T) * (Q_e003 / R3232_E003_Q_DES_KW)  # 1103 (65 °C)
    s.tlag["R3232_TW_RET"] = T_tw_ret                          # TT-323015
    m_cond   = m_305 + R3232_M797_DES - m_321
    sens_e003= ((m_305*(R3232_E003_T305 - Te003)
                 + m718B_prev*(R3232_E011_T - Te003)
                 + m_776    *(R328_D001_T  - Te003)
                 + R3232_M797_DES*(R3232_M797_T - Te003)
                 + m_756    *(A328_C001_T  - Te003))/3600.0*R3232_CP)
    P_e003   = sens_e003 + m_cond/3600.0*R3232_E003_LAMC - Q_e003
    s.r3232_d001_P = max(s.r3232_d001_P + R3232_D001_P_KP*(gen321 - m_321)/3600.0*dt, 0.1)
    s.r3232_e003_T = Te003 + P_e003*dt/max(s.r3232_d001_M*R3232_CP, 1e-6)
    s.r3232_d001_M = max(s.r3232_d001_M + (in_e003 - m_321 - m_744 - m_308)/3600.0*dt, 1.0)

    # ----- Stage 9 : 323E011 + 323D011  LP carbamate condenser (45°C) -----
    Te011    = s.r3232_e011_T
    in_e011  = m_701 + R3232_M702_DES + m_786_d001 + m_321 + m_402
    pic203_op= _ctrl_ipd(s.PIC_323203, s.r3232_e011_P, dt)
    m_v011   = R3232_E011_MV_DES * (pic203_op / R3232_E011_PV_OP_DES)     # vapour -> 323C005
    gen_v011 = R3232_E011_PHIV * in_e011
    # 323D011 level tank: condensed liquid (in_e011 - m_v011) + the FIC-323401 flush 401 fall in; the
    # 323P008 lean-carbamate pumps draw out through LV-323503 on the common discharge header, which then
    # splits into the 718A and 718B legs, each with its own FV.  Each leg is therefore two valves in
    # series -> stroke ratios multiply.  Total is DERIVED from the legs: the legs are authoritative, so
    # an operator stroking them apart shows up as a real inventory error that LIC-323503 integrates out.
    # 323D011 level tank: condensed liquid (in_e011 - m_v011) + the FIC-323401 flush 401 fall in; the
    # 323P008 lean-carbamate pumps draw out through LV-323503, and the discharge header splits into
    # the 718A and 718B legs.  LIC-323503 -> LV-323503 sets the TOTAL draw; FIC-323418 holds the 718B
    # slipstream ("regulates the SPECIFIC recycle flow rate of lean carbamate", 328E021 328E007
    # 328P003 328P006.md:369) and FIC-323405 takes the remainder as a CASCADE setpoint, so the level
    # loop's authority lands on 718A instead of being rejected by it.  One integrator per degree of
    # freedom (inventory -> LIC-323503/FIC-323405 cascade; split -> FIC-323418).  Modelling a series
    # LV-503 as a derate on both FVs instead was tried and REJECTED: two AUTO FICs reject the header
    # stroke by integral action, so LIC-323503 wound up to op_hi and level parked off SP (see
    # scratchpad/dyn503.py).  The cascade slave is ~250x faster than the level loop (5 s lag vs the
    # 1257 s natural period), so the standard >=5x separation for cascade stability holds easily.
    lvl_d011 = s.r3232_e011_M / R3232_D011_M_DES * R3232_D011_LVL_SP      # LT-323503 (%)
    lic503_op= _ctrl_ipd(s.LIC_323503, lvl_d011, dt)                      # -> LV-323503 (total draw)
    m718_dmd = R3232_D011_M718_DES * (lic503_op / R3232_LV503_OP_DES)     # total draw demand (kg/h)
    m_718B   = _fic_flow(s.FIC_323418, R3232_M718B_DES, R3232_FIC418_OP_DES, s.tlag,
                         "F_323418", dt)                                  # -> 323E003 (slipstream)
    m_718A   = _fic_flow(s.FIC_323405, R3232_M718A_DES, R3232_FIC405_OP_DES, s.tlag,
                         "F_323405", dt,
                         cas_sp=max(m718_dmd - m_718B, 0.0))              # -> 328E004/328D001 (bal)
    m_718_tot= m_718A + m_718B                                            # -> 323D011 draw (kg/h)
    Q_e011   = R3232_E011_UA_KW * (Te011 - 35.0)
    sens_e011= ((m_701*(R3232_E011_T701 - Te011)
                 + R3232_M702_DES*(R3232_M702_T   - Te011)
                 + m_786_d001*(R3232_E011_T786    - Te011)
                 + m_321*(74.0 - Te011)
                 + m_402*(56.0 - Te011))/3600.0*R3232_CP)
    P_e011   = sens_e011 + m_v011/3600.0*R3232_E011_LAMV - Q_e011
    s.r3232_e011_P = max(s.r3232_e011_P + R3232_E011_P_KP*(gen_v011 - m_v011)/3600.0*dt, 0.1)
    s.r3232_e011_T = Te011 + P_e011*dt/max(s.r3232_e011_M*R3232_CP, 1e-6)
    s.r3232_e011_M = max(s.r3232_e011_M + (in_e011 + m_401 - m_v011 - m_718A - m_718B)/3600.0*dt, 1.0)

    # ----- recycle-tear writes (one-tick delay -> next step reads these) --
    s.tlag["R3232_v011"] = m_v011
    s.tlag["R328_748"]   = m_748
    s.tlag["R328_750"]   = m_750
    s.tlag["R328_775"]   = m_775
    s.tlag["R3232_718A"] = m_718A
    s.tlag["R3232_744"]  = m_744
    s.tlag["R3232_718B"] = m_718B
    s.tlag["R328_M931"]  = m_931

    # ======================================================================
    #  UNIT 324 — TWO-STAGE VACUUM EVAPORATION  (rigorous, conservative)
    #  Feed = m_324 (kg/h, 80% urea, ~99 C) delivered by FIC-324401.  LV-B
    #  recycle (98.6% melt) is read one tick delayed and re-blended into the
    #  Stage-1 feed.  Each stage runs a TIC->PIC steam cascade that sets the
    #  chest pressure -> Q = UA*(tsat(p_chest) - T); urea is conserved so the
    #  water evaporated is fixed exactly by the concentration anchor, and the
    #  energy/mass/pressure ODEs integrate the live sub-step dt.  UA/λ were
    #  back-solved at the seed so dM/dt = dT/dt = dP/dt = 0 at design.  Vacuum
    #  is held by a false-air PIC balanced against a fixed ejector pull.
    #      HARD anchors: Stage 1 0.33 bar a / 130 C / 80->95 % ;
    #                    Stage 2 0.131 bar a / 140 C / 95->98.6 %.
    # ======================================================================
    cp324      = R324_CP_SOLN
    recyc_prev = s.tlag.get("R324_recyc", 0.0)                                # LV-B recycle (kg/h, 98.6%)

    # ---- Stage 1 : Evaporator I 324E001 + separator 324F001 (0.33 bar a, 130 C) --
    feed1_m    = max(m_324, 0.0) + recyc_prev                                 # blended Stage-1 feed (kg/h)
    urea1_in   = R324_W_IN*max(m_324, 0.0) + R324_W_EV2*recyc_prev            # urea into Stage 1 (kg/h)
    tic1_op    = _ctrl_ipd(s.TIC_324001, s.r324_e001_T, dt)                   # steam chest-P demand (bar a)
    pic203_pv  = clamp(s.PIC_329203["op"]/100.0*R323_P_STEAM_SUP, 0.0, R323_P_STEAM_SUP)
    pic203_op  = _ctrl_ipd(s.PIC_329203, pic203_pv, dt, cas_sp=tic1_op)       # steam valve stroke (%)
    p_chest_e001 = clamp(pic203_op/100.0*R323_P_STEAM_SUP, 0.02, R323_P_STEAM_SUP)
    Q_e001_kw  = R324_E001_UA_KW*(tsat_steam(p_chest_e001) - s.r324_e001_T)   # Evap-I duty (kW)
    p1_m       = urea1_in / R324_W_EV1                                        # melt @94.31% to hold conc (kg/h)
    v1_m       = max(feed1_m - p1_m, 0.0)                                     # water vapour -> 324E002 (kg/h)
    P_e001     = (feed1_m/3600.0*cp324*(R324_FEED_T_C - s.r324_e001_T)
                  + Q_e001_kw - v1_m/3600.0*R324_LAM_V1)                      # net kW on holdup
    M_f001_pre = s.r324_f001_M
    s.r324_e001_T = s.r324_e001_T + P_e001*dt/max(M_f001_pre*cp324, 1e-6)
    m_p1       = p1_m                                                         # barometric leg -> Stage 2 (kg/h)
    s.r324_f001_M = max(M_f001_pre + (feed1_m - v1_m - m_p1)/3600.0*dt, 1.0)
    # vacuum: PIC-324202 false-air bleed balanced against 324F002 ejector pull
    fa202_m    = R324_F001_FA_DES * (s.PIC_324202["op"]/max(R324_PV202_OP_DES, 1e-6))
    _ctrl_ipd(s.PIC_324202, s.r324_f001_P, dt)                               # false-air stroke (%)
    s.r324_f001_P = clamp(s.r324_f001_P
                          + R324_F001_P_KP*((v1_m + fa202_m) - R324_F001_EJPULL_DES)/3600.0*dt,
                          0.05, 1.0)

    # ---- Stage 2 : Evaporator II 324E003 + separator 324F003 (0.131 bar a, 140 C) -
    feed2_m    = m_p1                                                         # Stage-1 melt (95%) -> Stage 2
    urea2_in   = R324_W_EV1 * feed2_m                                         # urea into Stage 2 (kg/h)
    tic2_op    = _ctrl_ipd(s.TIC_324002, s.r324_e003_T, dt)                   # steam chest-P demand (bar a)
    pic212_pv  = clamp(s.PIC_329212["op"]/100.0*R323_P_STEAM_SUP, 0.0, R323_P_STEAM_SUP)
    pic212_op  = _ctrl_ipd(s.PIC_329212, pic212_pv, dt, cas_sp=tic2_op)       # steam valve stroke (%)
    p_chest_e003 = clamp(pic212_op/100.0*R323_P_STEAM_SUP, 0.02, R323_P_STEAM_SUP)
    Q_e003_kw  = R324_E003_UA_KW*(tsat_steam(p_chest_e003) - s.r324_e003_T)   # Evap-II duty (kW)
    p2_gen     = urea2_in / R324_W_EV2                                        # melt @97.71% produced (kg/h)
    v2_m       = max(feed2_m - p2_gen, 0.0)                                   # water vapour -> 324E005 (kg/h)
    P_e003     = (feed2_m/3600.0*cp324*(R324_E001_T_SP_C - s.r324_e003_T)
                  + Q_e003_kw - v2_m/3600.0*R324_LAM_V2)                      # net kW on holdup
    M_f003_pre = s.r324_f003_M
    s.r324_e003_T = s.r324_e003_T + P_e003*dt/max(M_f003_pre*cp324, 1e-6)
    # LIC-324501 split-range drain: LV-A forward (335P001) / LV-B recycle (Stage 1)
    lvl_f003   = clamp(s.r324_f003_M / R324_F003_M_FULL * 100.0, 0.0, 100.0)
    lic501_op  = _ctrl_ipd(s.LIC_324501, lvl_f003, dt)                       # split-range command (%)
    lva_stroke = clamp((lic501_op - 50.0)*2.0, 0.0, 100.0)                    # LV-A forward stroke (%)
    lvb_stroke = clamp((50.0 - lic501_op)*2.0, 0.0, 100.0)                    # LV-B recycle stroke (%)
    m_fwd      = lva_stroke/100.0 * R324_LVA_SPAN                             # forward melt (kg/h)
    m_recyc    = lvb_stroke/100.0 * R324_LVB_SPAN                             # recycle melt -> Stage 1 (kg/h)
    s.r324_f003_M = max(M_f003_pre + (feed2_m - v2_m - m_fwd - m_recyc)/3600.0*dt, 1.0)
    # vacuum: PIC-324203 deep-vacuum false-air bleed vs 324F004 ejector pull
    fa203_m    = R324_F003_FA_DES * (s.PIC_324203["op"]/max(R324_PV203_OP_DES, 1e-6))
    _ctrl_ipd(s.PIC_324203, s.r324_f003_P, dt)
    s.r324_f003_P = clamp(s.r324_f003_P
                          + R324_F003_P_KP*((v2_m + fa203_m) - R324_F003_EJPULL_DES)/3600.0*dt,
                          0.02, 1.0)

    # ---- UF85 ratio injection (FFIC-335406 ratio station -> FIC-335405 flow) ------
    #  Feed-forward: UF85 = active ratio * forward melt.  Controllers stepped for
    #  faceplate liveness; UF85 is an external additive (biuret guard), off the
    #  urea-conservation network.
    uf_ratio   = clamp(s.FFIC_335406["op"], 0.0, R324_UF_RATIO*4.0)           # active ratio (holds 0.005)
    m_uf       = uf_ratio * m_fwd                                             # UF85 injection (kg/h)
    m_product  = m_fwd + m_uf                                                 # final 98.6% melt + UF85 -> 335
    _ctrl_ipd(s.FFIC_335406, R324_UF_RATIO, dt)                              # ratio station liveness
    _fic_flow(s.FIC_335405, R324_M_UF_DES/1000.0, R324_FIC405_OP_DES,
              s.tlag, "R324_UF", dt, cas_sp=m_uf/1000.0)                      # FIC-335405 slave liveness (t/h)

    # ---- condensation train sinks (conservative pass-through boundary) -----------
    #  Stage vapours + false air are pulled by ejectors 324F002/F004 through the
    #  vacuum condensers 324E002/E005/E006/E007: water condenses (-> 328D003 process
    #  condensate) and the non-condensables (false air) vent via 324F005.  Modelled
    #  as boundary sinks so the 324 envelope closes:  V1+V2 -> condensate,
    #  false air -> vent.
    m_324_cond = v1_m + v2_m                                                  # total process condensate (kg/h)
    m_324_vent = fa202_m + fa203_m                                            # non-condensable vent (kg/h)
    # ---- recycle tear write (one-tick delay -> next step reads it) ---------------
    s.tlag["R324_recyc"] = m_recyc

    # ----- auxiliary faceplate trims (stepped for liveness; off the network)
    #   FIC-323405 / LIC-323503 dropped from here: both now step on the live 718A/718B/323D011 network.
    _ctrl_ipd(s.TIC_328008, 100.0 * R328_D001_OFFGAS_PHI * psat_water_bara(R328_C002_T_TOP) / max(s.a328_d001_P + R328_E004_DP, 0.1), dt)   # inferential offgas H2O mol% at 328C002 top (117C/3.5bara), PHI to PFD 737; live on drum PIC-328202 + 0.9 bar dP
    _ctrl_ipd(s.TIC_328012, s.a328_c003_T - R328_C003_T746, dt)              # differential PV: TT-328013 (bottom) - TT-328012 (3rd tray)
    _ctrl_ipd(s.SIC_323902, s.SIC_323902["op"], dt)
    _ctrl_ipd(s.FIC_328406, s.FIC_328406["op"], dt)

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

    # ----- Trip 22.1 (LP absorber 322C001 over-temperature steam-flood) -----
    #   TT-322015 > 57 C latches the steam-flood valve XV-322915 OPEN to inert/quench the
    #   absorber off-gas space.  Hysteretic self-clear once the bed cools below 55 C returns
    #   manual control of XV-322915 to the operator (no dedicated reset control on the overlay).
    #   The flood duty Q_FLOOD = A328_QFLOOD_KW is consumed one tick later in stage-7 physics
    #   (the flood valve is read at the top of the step).  At design Tc001 ~ 43 C the condition
    #   is False -> XV shut, Q_FLOOD = 0 -> steady state stays bit-exact.
    s.trips["22_1"] = s.a328_c001_T > 57.0
    if s.trips["22_1"]:
        s.trip_latched["22_1"] = True
    elif s.a328_c001_T < 55.0:
        s.trip_latched["22_1"] = False
    if s.trip_latched["22_1"]:
        s.XV_322915 = True

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
            hpcc["feed_kmolh"], hpcc["T_prod"], d_HPCC_P,
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

    # ---- Bug 2: predictive carbamate-crystallization monitor across every carbamate/urea liquid ----
    #   STRIP_BOT keeps its urea-melt-floor anchor (132.7 C, same value the reactive drain factor
    #   uses); the carbamate/urea liquors derive their freezing line from their own live free-water
    #   content.  WARN raised while still molten but within CARB_WARN_DT_C of freezing; ALARM at the
    #   CARB_MUSH_DT_C onset margin -- both BEFORE the reactive _f_flow cut-off starts choking flow.
    cryst = {
        "STRIP_BOT":      _cryst_assess(streams["STRIP_BOT"], T_cryst=STRIP_BOT_T_CRYST_C),
        "CARB_RECYCLE":   _cryst_assess(streams["CARB_RECYCLE"]),
        "EJ_DISCH":       _cryst_assess(streams["EJ_DISCH"]),
        "HPCC_PROD":      _cryst_assess(streams["HPCC_PROD"]),
        "REACT_OVERFLOW": _cryst_assess(streams["REACT_OVERFLOW"]),
    }
    _cryst_states = [v["state"] for v in cryst.values()]
    s.flags["CARBAMATE_CRYST_WARN"]  = any(st in ("WARN", "ALARM") for st in _cryst_states)
    s.flags["CARBAMATE_CRYST_ALARM"] = any(st == "ALARM" for st in _cryst_states)

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
            "TT_322012":   round(d_TT322012, 1),     # discharge temp (C) -> 322E002 HPCC (lagged)
            "PI_disch":    round(ej["P_bara"], 1),   # discharge pressure (bar a)
            "TI_322002":   round(d_TT322002, 1), # TT-322002 = 322E003 overflow temp (C, lagged)
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
            "vent_th":    round(s.F_CO2_vent_th, 2), # t/h CO2 diverted out PV-322203
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
            "TT_322014":   round(s.react_T_overflow, 1),  # 322R001 overflow feed temp (C, live cascade lip)
            "TT_322013":   round(d_TT322013, 1),      # top gas -> 322E002 (C, lagged)
            "TT_322004":   round(d_TT322004, 1),      # bottom soln -> LV-322501, pre-flash (C, lagged)
            "TT_323001":   round(d_TT323001, 1),          # post-LV flash -> 323C003 (C, lagged)
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
        "RECIRC_323": {                          # Unit 323 - LP Recirculation & Pre-Evaporation
            "C003": {                            # Rectifying Column 323C003 + Recirc Heater 323E002
                "TT_323002":  round(s.r323_c003_T - (R323_C003_T_SP_C - R323_C003_T313_C), 1),  # stream 313 sump (PFD-20 121C = 314 drain 135 - reboiler rise)
                "P_bara":     round(s.r323_c003_P, 2),                       # PT-323201 column pressure (bar a, dynamic)
                "LI_323501":  round(s.r323_c003_M / R323_C003_M_FULL * 100.0, 1),  # level (%)
                "feed_th":    round(m_feed_323 / 1000.0, 2),                 # feed from 322E001 (t/h)
                "feed_T":     round(T_feed_323, 1),                          # feed temp (C, TT-323001)
                "v305_th":    round(m_305 / 1000.0, 2),                      # top vapor -> LPCC (t/h)
                "drain314_th":round(m_314 / 1000.0, 2),                      # bottom drain -> flash (t/h)
                "Q_kW":       round(Q_e002_kw, 0),                           # heater 323E002 duty (kW)
                "TIC_323007": {"pv": round(s.TIC_323007["pv"], 1), "sp": round(s.TIC_323007["sp"], 1),
                               "op": round(s.TIC_323007["op"], 2), "mode": s.TIC_323007["mode"]},
                "PIC_329202": {"pv": round(s.PIC_329202["pv"], 2), "sp": round(s.PIC_329202["sp"], 2),
                               "op": round(s.PIC_329202["op"], 1), "mode": s.PIC_329202["mode"]},
                "LIC_323501": {"pv": round(s.LIC_323501["pv"], 1), "sp": round(s.LIC_323501["sp"], 1),
                               "op": round(s.LIC_323501["op"], 1), "mode": s.LIC_323501["mode"]},
            },
            "F004": {                            # Flash Tank 323F004 (adiabatic 4.1 -> 1.13 bar)
                "TT_323005":  round(s.r323_f004_T, 1),                       # flash temp (C, hold 106)
                "P_bara":     round(s.r323_f004_P, 2),                       # flash pressure (bar a, dynamic)
                "LI_323505":  round(s.r323_f004_M / R323_F004_M_FULL * 100.0, 1),
                "v701_th":    round(m_701 / 1000.0, 2),                      # flash vapor -> LPCC (t/h)
                "drain319_th":round(m_319 / 1000.0, 2),                      # drain -> pre-evaporator (t/h)
                "LIC_323505": {"pv": round(s.LIC_323505["pv"], 1), "sp": round(s.LIC_323505["sp"], 1),
                               "op": round(s.LIC_323505["op"], 1), "mode": s.LIC_323505["mode"]},
            },
            "F010": {                            # Pre-evaporator 323F010 + Heater 323E010 (vacuum 0.46 bar)
                "TT_323010":  round(s.r323_f010_T, 1),                       # pre-evap temp (C, hold 99)
                "P_bara":     R323_F010_P_BARA,                              # vacuum (bar a, fixed)
                "LI_323F010": round(s.r323_f010_M / R323_F010_M_FULL * 100.0, 1),
                "evap_th":    round(m_evap / 1000.0, 2),                     # evaporated water -> vac (t/h)
                "product317_th": round(m_317 / 1000.0, 2),                   # product -> 323D002 (t/h)
                "Q_kW":       round(Q_e010_kw, 0),                           # heater 323E010 duty (kW)
                "TIC_323012": {"pv": round(s.TIC_323012["pv"], 1), "sp": round(s.TIC_323012["sp"], 1),
                               "op": round(s.TIC_323012["op"], 2), "mode": s.TIC_323012["mode"]},
                "PIC_329208": {"pv": round(s.PIC_329208["pv"], 2), "sp": round(s.PIC_329208["sp"], 2),
                               "op": round(s.PIC_329208["op"], 1), "mode": s.PIC_329208["mode"]},
            },
            "D002": {                            # Urea Solution Tank 323D002 (2-compartment, atm)
                "T_C":        round(s.r323_f010_T, 1),                       # product temp (~99, ex pre-evap)
                "LI_323507":  round(s.r323_d002_M_I / R323_D002_M_I_FULL * 100.0, 1),   # Comp I level (%)
                "LI_comp2":   round(s.r323_d002_M_II / R323_D002_M_II_FULL * 100.0, 1), # Comp II level (%)
                "product324_th": round(m_324 / 1000.0, 2),                   # product -> Unit 324 (t/h)
                "LIC_323507": {"pv": round(s.LIC_323507["pv"], 1), "sp": round(s.LIC_323507["sp"], 1),
                               "op": round(s.LIC_323507["op"], 1), "mode": s.LIC_323507["mode"]},
                "FIC_324401": {"pv": round(s.FIC_324401["pv"], 1), "sp": round(s.FIC_324401["sp"], 1),
                               "op": round(s.FIC_324401["op"], 1), "mode": s.FIC_324401["mode"]},
            },
        },
        "LPCC_3232": {                           # Screen 323-2 : LP Carbamate Condenser train
            "E003": {                            # 323E003 LPCC + 323D001 carbamate separator (74°C)
                "TT_323003":  round(s.r3232_e003_T, 1),                    # shell liquid temp (C, hold 74)
                "P_bara":     round(s.r3232_d001_P, 2),                    # 323D001 pressure (bar a)
                "LI_323502":  round(s.r3232_d001_M / R3232_D001_M_FULL * 100.0, 1),
                "in305_th":   round(m_305 / 1000.0, 2),                    # 323C003 vapour in (t/h)
                "carbamate308_th": round(m_308 / 1000.0, 2),              # 323P001 carbamate -> HP (t/h)
                "vent321_th": round(m_321 / 1000.0, 2),                    # PV-323202 vent -> 323E011 (t/h)
                "wash744_th": round(m_744 / 1000.0, 2),                    # FIC-328402 wash -> 328D003-II (t/h)
                "liquor756_th": round(m_756 / 1000.0, 2),                  # 322C001 liquor feed (t/h)
                "PIC_323202": {"pv": round(s.PIC_323202["pv"], 2), "sp": round(s.PIC_323202["sp"], 2),
                               "op": round(s.PIC_323202["op"], 1), "mode": s.PIC_323202["mode"]},
                "LIC_323502": {"pv": round(s.LIC_323502["pv"], 1), "sp": round(s.LIC_323502["sp"], 1),
                               "op": round(s.LIC_323502["op"], 1), "mode": s.LIC_323502["mode"]},
                "SIC_323901": {"pv": round(s.SIC_323901["pv"], 1), "sp": round(s.SIC_323901["sp"], 1),
                               "op": round(s.SIC_323901["op"], 1), "mode": s.SIC_323901["mode"]},
                "SIC_323902": {"pv": round(s.SIC_323902["pv"], 1), "sp": round(s.SIC_323902["sp"], 1),
                               "op": round(s.SIC_323902["op"], 1), "mode": s.SIC_323902["mode"]},
                "TIC_323013": {"pv": round(s.TIC_323013["pv"], 1), "sp": round(s.TIC_323013["sp"], 1),
                               "op": round(s.TIC_323013["op"], 2), "mode": s.TIC_323013["mode"]},
                "TV_323013A": round(tic13_op, 1),              # cold make-up : opens as PV rises above SP
                "TV_323013B": round(100.0 - tic13_op, 1),      # hot bypass : exact opposite of TV-323013A
                "TT_323015":  round(T_tw_ret, 1),              # TW return 323E003 -> 323P003 (1103, 65 °C)
                "FIC_328402": {"pv": round(s.FIC_328402["pv"], 1), "sp": round(s.FIC_328402["sp"], 1),
                               "op": round(s.FIC_328402["op"], 1), "mode": s.FIC_328402["mode"]},
            },
            "E011": {                            # 323E011 LP carbamate condenser + 323D011 (45°C)
                "TT_323011":  round(s.r3232_e011_T, 1),                    # shell liquid temp (C, hold 45)
                "P_bara":     round(s.r3232_e011_P, 2),                    # 323D011 pressure (bar a)
                "LI_323D011": round(s.r3232_e011_M / R3232_D011_M_DES * R3232_D011_LVL_SP, 1),
                "in701_th":   round(m_701 / 1000.0, 2),                    # 323F004 flash vapour in (t/h)
                "vap011_th":  round(m_v011 / 1000.0, 2),                   # PIC-323203 vapour -> 323C005 (t/h)
                "carb718A_th":round(m_718A / 1000.0, 2),                   # -> 328D001 (t/h)
                "carb718B_th":round(m_718B / 1000.0, 2),                   # -> 323E003 (t/h)
                "PIC_323203": {"pv": round(s.PIC_323203["pv"], 2), "sp": round(s.PIC_323203["sp"], 2),
                               "op": round(s.PIC_323203["op"], 1), "mode": s.PIC_323203["mode"]},
                "FIC_323401": {"pv": round(s.FIC_323401["pv"], 1), "sp": round(s.FIC_323401["sp"], 1),
                               "op": round(s.FIC_323401["op"], 1), "mode": s.FIC_323401["mode"]},
                "FIC_323402": {"pv": round(s.FIC_323402["pv"], 1), "sp": round(s.FIC_323402["sp"], 1),
                               "op": round(s.FIC_323402["op"], 1), "mode": s.FIC_323402["mode"]},
            },
            "C005": {                            # 323C005 off-gas scrubber -> 328V001
                "TT_323C005": round(s.a323_c005_T, 1),                     # scrub liquid temp (C, hold 55)
                "LI_323503":  round(s.a323_c005_M / A323_C005_M_DES * 50.0, 1),
                "bot_th":     round(bot_c005 / 1000.0, 2),                 # bottoms -> 328V001 (t/h)
                "FIC_323418": {"pv": round(s.FIC_323418["pv"], 1), "sp": round(s.FIC_323418["sp"], 1),
                               "op": round(s.FIC_323418["op"], 1), "mode": s.FIC_323418["mode"]},
                "FIC_323405": {"pv": round(s.FIC_323405["pv"], 1), "sp": round(s.FIC_323405["sp"], 1),
                               "op": round(s.FIC_323405["op"], 1), "mode": s.FIC_323405["mode"]},
                "LIC_323503": {"pv": round(s.LIC_323503["pv"], 1), "sp": round(s.LIC_323503["sp"], 1),
                               "op": round(s.LIC_323503["op"], 1), "mode": s.LIC_323503["mode"]},
            },
        },
        "DESORB_328": {                          # Screen 328-1 : Desorption / Hydrolysis train
            "C002": {                            # 328C002 Desorber-I (bottoms 139°C)
                "TT_328C002": round(s.a328_c002_T, 1),                     # bottom temp (C, hold 139)
                "TT_328007":  round(s.a328_c002_T, 1),                     # bottoms draw -> 328P006 (stream 743, 139C)
                "LI_328503":  round(s.a328_c002_M / R328_C002_M_DES * 50.0, 1),
                "feed738_th": round(m_738 / 1000.0, 2),                    # 328D003 feed via 328E007 (t/h)
                "ovhd737_th": round(m_737 / 1000.0, 2),                    # top vapour -> 328D001 (t/h)
                "bot743_th":  round(m_743 / 1000.0, 2),                    # bottoms -> 328C003 (t/h)
                "LIC_328503": {"pv": round(s.LIC_328503["pv"], 1), "sp": round(s.LIC_328503["sp"], 1),
                               "op": round(s.LIC_328503["op"], 1), "mode": s.LIC_328503["mode"]},
            },
            "C003": {                            # 328C003 Hydrolyser (200°C, MP steam)
                "TT_328C003": round(s.a328_c003_T, 1),                     # temp (C, hold 200)
                "TT_328012":  round(R328_C003_T746, 1),                    # 3rd-tray / 746 absolute (C, 190) - TT-328011/TT-328012 display
                "TT_328009":  round(T_746, 1),                             # 328E021 cold out -> C003 feed (stream 746, 190C)
                "P_bara":     round(s.a328_c003_P, 2),
                "LI_328505":  round(s.a328_c003_M / R328_C003_M_DES * 50.0, 1),
                "steam911_th":round(m_911 / 1000.0, 2),                    # FIC-326402 MP steam (t/h)
                "ovhd748_th": round(m_748 / 1000.0, 2),                    # relief -> 328C002 (t/h)
                "bot747_th":  round(m_747 / 1000.0, 2),                    # bottoms -> 328C004 (t/h)
                "PIC_328203": {"pv": round(s.PIC_328203["pv"], 2), "sp": round(s.PIC_328203["sp"], 2),
                               "op": round(s.PIC_328203["op"], 1), "mode": s.PIC_328203["mode"]},
                "LIC_328505": {"pv": round(s.LIC_328505["pv"], 1), "sp": round(s.LIC_328505["sp"], 1),
                               "op": round(s.LIC_328505["op"], 1), "mode": s.LIC_328505["mode"]},
                "FIC_326402": {"pv": round(s.FIC_326402["pv"], 1), "sp": round(s.FIC_326402["sp"], 1),
                               "op": round(s.FIC_326402["op"], 1), "mode": s.FIC_326402["mode"]},
                "TIC_328012": {"pv": round(s.TIC_328012["pv"], 1), "sp": round(s.TIC_328012["sp"], 1),
                               "op": round(s.TIC_328012["op"], 2), "mode": s.TIC_328012["mode"]},
            },
            "C004": {                            # 328C004 Desorber-II (143°C, LP steam, FFIC ratio)
                "TT_328C004": round(s.a328_c004_T, 1),                     # temp (C, hold 143)
                "TT_328005":  round(s.a328_c004_T, 1),                     # bottoms draw -> 328E007 (stream 739, 143C)
                "TT_328004":  round(s.a328_c004_T - R328_C004_DT_DES, 1),  # top tray = OVHD 750 (140C), tracks live bottoms
                "LI_328504":  round(s.a328_c004_M / R328_C004_M_DES * 50.0, 1),
                "steam931_th":round(m_931 / 1000.0, 2),                    # FIC-328401 LP steam (t/h)
                "ovhd750_th": round(m_750 / 1000.0, 2),                    # relief -> 328C002 (t/h)
                "bot739_th":  round(m_739 / 1000.0, 2),                    # bottoms -> 328E007 boundary (t/h)
                "FFIC_328401":{"pv": round(s.FFIC_328401["pv"], 4), "sp": round(s.FFIC_328401["sp"], 4),
                               "op": round(s.FFIC_328401["op"], 1), "mode": s.FFIC_328401["mode"]},
                "FIC_328401": {"pv": round(s.FIC_328401["pv"], 1), "sp": round(s.FIC_328401["sp"], 1),
                               "op": round(s.FIC_328401["op"], 1), "mode": s.FIC_328401["mode"]},
                "LIC_328504": {"pv": round(s.LIC_328504["pv"], 1), "sp": round(s.LIC_328504["sp"], 1),
                               "op": round(s.LIC_328504["op"], 1), "mode": s.LIC_328504["mode"]},
            },
            "D001": {                            # 328D001 Desorber-I reflux drum (61°C, 328E004)
                "TT_328D001": round(s.a328_d001_T, 1),                     # temp (C, hold 61)
                "TT_328008":  round(R328_E007_TC_OUT, 1),                  # 328E007 cold-out / Desorber-I top (C, 114) - TT-328008/TT-328010 display
                "P_bara":     round(s.a328_d001_P, 2),
                "LI_328501":  round(s.a328_d001_M / R328_D001_M_DES * R328_D001_LVL_SP, 1),
                "vent786_th": round(m_786_d001 / 1000.0, 2),               # PIC-328202 vent -> 323E011 (t/h)
                "reflux775_th":round(m_775 / 1000.0, 2),                   # FIC-328404 reflux -> 328C002 (t/h)
                "draw776_th": round(m_776 / 1000.0, 2),                    # LV-328501 draw -> 323E003 (t/h)
                "flow776_m3h": round(m_776 / R328_D001_M776_RHO, 2),        # FT-328401: LV-328501 draw in m3/h (stream 776, des 7.6)
                "PIC_328202": {"pv": round(s.PIC_328202["pv"], 2), "sp": round(s.PIC_328202["sp"], 2),
                               "op": round(s.PIC_328202["op"], 1), "mode": s.PIC_328202["mode"]},
                "LIC_328501": {"pv": round(s.LIC_328501["pv"], 1), "sp": round(s.LIC_328501["sp"], 1),
                               "op": round(s.LIC_328501["op"], 1), "mode": s.LIC_328501["mode"]},
                "FIC_328404": {"pv": round(s.FIC_328404["pv"], 1), "sp": round(s.FIC_328404["sp"], 1),
                               "op": round(s.FIC_328404["op"], 1), "mode": s.FIC_328404["mode"]},
                "TIC_328002": {"pv": round(s.TIC_328002["pv"], 1), "sp": round(s.TIC_328002["sp"], 1),
                               "op": round(s.TIC_328002["op"], 2), "mode": s.TIC_328002["mode"]},
                "TIC_328008": {"pv": round(s.TIC_328008["pv"], 1), "sp": round(s.TIC_328008["sp"], 1),
                               "op": round(s.TIC_328008["op"], 2), "mode": s.TIC_328008["mode"]},
            },
        },
        "ABSORB_328": {                          # Screen 328-2 : LP Absorber + recirc collector
            "C001": {                            # 322C001 LP off-gas absorber (43°C, live GCB)
                "TT_322015":  round(s.a328_c001_T, 1),                     # liquid temp (C, hold 43; trip>57)
                "P_bara":     round(s.a328_c001_P, 2),
                "LI_322502":  round(s.a328_c001_M / A328_C001_M_DES * 50.0, 1),
                "gcb_th":     round(gcb_m / 1000.0, 2),                    # HV-322604 off-gas in (t/h)
                "gcb_T":      round(gcb_T, 1),                             # off-gas temp (C)
                "abs_th":     round(abs_c001 / 1000.0, 2),                 # NH3/CO2 absorbed (t/h)
                "vent_th":    round(vent_c001 / 1000.0, 2),               # inert vent -> atm (t/h)
                "liquor756_th": round(m_756 / 1000.0, 2),                 # LV-322502 draw -> 323E003 (t/h)
                "XV_322915":  bool(s.XV_322915),                          # steam-flood trip valve (22.1)
                "PIC_322201": {"pv": round(s.PIC_322201["pv"], 2), "sp": round(s.PIC_322201["sp"], 2),
                               "op": round(s.PIC_322201["op"], 1), "mode": s.PIC_322201["mode"]},
                "LIC_322502": {"pv": round(s.LIC_322502["pv"], 1), "sp": round(s.LIC_322502["sp"], 1),
                               "op": round(s.LIC_322502["op"], 1), "mode": s.LIC_322502["mode"]},
            },
            "D003": {                            # 328D003 recirc collector (Comp-I 56°C / Comp-II 44°C)
                "TT_328I":    round(s.a328_d003_TI, 1),                    # Comp-I temp (C, hold 56)
                "TT_328II":   round(s.a328_d003_TII, 1),                   # Comp-II temp (C, hold 44)
                "LI_328I":    round(s.a328_d003_MI / A328_D003_MI_FULL * 100.0, 1),
                "LI_328II":   round(s.a328_d003_MII / A328_D003_MII_FULL * 100.0, 1),
                "form735_th": round(m_735 / 1000.0, 2),                    # Comp-I formation -> 328C002 (t/h)
                "collect755_th": round(m_755 / 1000.0, 2),                 # 322P002 collector -> 322C001 (t/h)
                "flow755_m3h": round(m_755 / A328_M755_RHO, 2),            # FT-322402: 755 draw in m3/h (des 31.3)
                "FIC_328406": {"pv": round(s.FIC_328406["pv"], 1), "sp": round(s.FIC_328406["sp"], 1),
                               "op": round(s.FIC_328406["op"], 1), "mode": s.FIC_328406["mode"]},
                "P002A":      {"on": s.aux_pumps["322P002A"]["on"], "mode": s.aux_pumps["322P002A"]["mode"]},
                "P002B":      {"on": s.aux_pumps["322P002B"]["on"], "mode": s.aux_pumps["322P002B"]["mode"]},
            },
        },
        "EVAP_324": {                            # Screens 324-1 / 324-1B : two-stage vacuum evaporation
            "E001": {                            # Screen 324-1 : Evaporator I 324E001 / 324F001 (130 C, 0.33 bar a)
                "TT_324001":   round(s.r324_e001_T, 1),                       # melt temp (C, hold 130)
                "PT_324202":   round(s.r324_f001_P, 3),                       # separator vacuum (bar a, hold 0.33)
                "LI_324F001":  round(s.r324_f001_M / R324_F001_M_FULL * 100.0, 1),
                "feed_th":     round(feed1_m / 1000.0, 2),                    # blended Stage-1 feed (t/h)
                "vapour_th":   round(v1_m / 1000.0, 2),                       # water vapour -> 324E002 (t/h)
                "melt_th":     round(m_p1 / 1000.0, 2),                       # 95% melt -> Stage 2 (t/h)
                "urea_pct":    round(R324_W_EV1 * 100.0, 1),                  # product conc (94.31 %, HARD)
                "p_chest_bara":round(p_chest_e001, 2),                        # steam chest press. (bar a)
                "Q_kW":        round(Q_e001_kw, 0),                           # Evap-I duty (kW)
                "TIC_324001":  {"pv": round(s.TIC_324001["pv"], 1), "sp": round(s.TIC_324001["sp"], 1),
                                "op": round(s.TIC_324001["op"], 2), "mode": s.TIC_324001["mode"]},
                "PIC_329203":  {"pv": round(s.PIC_329203["pv"], 2), "sp": round(s.PIC_329203["sp"], 2),
                                "op": round(s.PIC_329203["op"], 1), "mode": s.PIC_329203["mode"]},
                "PIC_324202":  {"pv": round(s.PIC_324202["pv"], 3), "sp": round(s.PIC_324202["sp"], 3),
                                "op": round(s.PIC_324202["op"], 1), "mode": s.PIC_324202["mode"]},
                "FIC_324401":  {"pv": round(s.FIC_324401["pv"], 2), "sp": round(s.FIC_324401["sp"], 2),
                                "op": round(s.FIC_324401["op"], 1), "mode": s.FIC_324401["mode"]},
            },
            "E003": {                            # Screen 324-1B : Evaporator II 324E003 / 324F003 (140 C, 0.131 bar a)
                "TT_324002":   round(s.r324_e003_T, 1),                       # melt temp (C, hold 140)
                "PT_324203":   round(s.r324_f003_P, 3),                       # deep vacuum (bar a, hold 0.131)
                "LI_324F003":  round(s.r324_f003_M / R324_F003_M_FULL * 100.0, 1),
                "feed_th":     round(feed2_m / 1000.0, 2),                    # 95% melt from Stage 1 (t/h)
                "vapour_th":   round(v2_m / 1000.0, 2),                       # water vapour -> 324E005 (t/h)
                "melt_fwd_th": round(m_fwd / 1000.0, 2),                      # LV-A forward melt (t/h)
                "recyc_th":    round(m_recyc / 1000.0, 2),                    # LV-B recycle -> Stage 1 (t/h)
                "urea_pct":    round(R324_W_EV2 * 100.0, 1),                  # product conc (97.71 %, HARD)
                "product_th":  round(m_product / 1000.0, 2),                  # final melt + UF85 -> 335 (t/h)
                "uf85_kgh":    round(m_uf, 1),                                # UF85 injection (kg/h)
                "p_chest_bara":round(p_chest_e003, 2),                        # steam chest press. (bar a)
                "Q_kW":        round(Q_e003_kw, 0),                           # Evap-II duty (kW)
                "TIC_324002":  {"pv": round(s.TIC_324002["pv"], 1), "sp": round(s.TIC_324002["sp"], 1),
                                "op": round(s.TIC_324002["op"], 2), "mode": s.TIC_324002["mode"]},
                "PIC_329212":  {"pv": round(s.PIC_329212["pv"], 2), "sp": round(s.PIC_329212["sp"], 2),
                                "op": round(s.PIC_329212["op"], 1), "mode": s.PIC_329212["mode"]},
                "PIC_324203":  {"pv": round(s.PIC_324203["pv"], 3), "sp": round(s.PIC_324203["sp"], 3),
                                "op": round(s.PIC_324203["op"], 1), "mode": s.PIC_324203["mode"]},
                "LIC_324501":  {"pv": round(s.LIC_324501["pv"], 1), "sp": round(s.LIC_324501["sp"], 1),
                                "op": round(s.LIC_324501["op"], 1), "mode": s.LIC_324501["mode"]},
                "FFIC_335406": {"pv": round(s.FFIC_335406["pv"], 4), "sp": round(s.FFIC_335406["sp"], 4),
                                "op": round(s.FFIC_335406["op"], 4), "mode": s.FFIC_335406["mode"]},
                "FIC_335405":  {"pv": round(s.FIC_335405["pv"], 3), "sp": round(s.FIC_335405["sp"], 3),
                                "op": round(s.FIC_335405["op"], 1), "mode": s.FIC_335405["mode"]},
            },
            "VAC": {                             # vacuum condensation train (324E002/E005/E006/E007 + ejectors)
                "condensate_th": round(m_324_cond / 1000.0, 2),              # V1+V2 -> 328D003 (t/h)
                "vent_kgh":      round(m_324_vent, 1),                        # non-condensable vent -> atm (kg/h)
            },
        },
        "HPCC_322E002": {                        # HP Carbamate Condenser 322E002 -> 322R001
            "TT_322012":   round(d_TT322012, 1),         # tube feed 1: ejector-disch liquid temp (C, lagged)
            "TT_322013":   round(d_TT322013, 1),         # tube feed 2: stripper-top gas temp (C, lagged)
            "TT_322010":   round(d_TT322010, 1),         # liquid product -> 322R001 (C, lagged)
            "TT_329001":   round(T_shell_lp, 1),         # F6: shell BFW/condensate feed T de-pinned -> live LP-header sat T (==146.3 at design)
            "gas_th":      round(hpcc["gas_th"], 2),     # gas product (t/h)
            "gas_MW":      round(hpcc["gas_MW"], 2),
            "gas_mol_pct": {k: round(hpcc["gas_mol_pct"][k], 3) for k in MW_COMP},   # mol %
            "liq_th":      round(hpcc["liq_th"], 2),     # liquid product (t/h)
            "liq_MW":      round(hpcc["liq_MW"], 2),
            "liq_mass_pct":{k: round(hpcc["liq_mass_pct"][k], 3) for k in MW_COMP},  # mass %
            "LT_322E002":  round(s.hpcc_level_pct, 1),   # liquid level (%) — DYNAMIC inventory (swells on stall)
            "P_bara":      round(d_HPCC_P, 1),
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
                "letdown_pct": round(s.steam.valve_letdown_pct, 1), # 9->4 let-down (PV-329205B) opening (%)
                "m_ld_th":     round(s.steam.m_ld * 3.6, 1),        # let-down flow (t/h)
                "m_water_th":  round(s.steam.m_water * 3.6, 1),     # desuperheat water (t/h)
            },
            "SUPPLY_25BAR": {                    # 25-bar site main (stream 901, boundary held)
                "P_bara":  round(s.steam.P_SUP, 2),
                "TI_sat":  round(tsat_steam(s.steam.P_SUP), 1),
            },
            "DRUM_9BAR": {                       # 329D009 MP drum (stream 903); split-range PIC-329205
                "P_bara":      round(s.steam.P_9, 2),
                "TI_sat":      round(tsat_steam(s.steam.P_9), 1),
                "admit_pct":   round(s.steam.valve_admit9_pct, 1),  # PV-329205A BL admit
                "letdown_pct": round(s.steam.valve_letdown_pct, 1), # PV-329205B 9->4 let-down
                "m_903_th":    round(s.steam.m_903 * 3.6, 2),       # BL -> 9-bar (t/h)
                "m_ld_th":     round(s.steam.m_ld * 3.6, 2),        # 9 -> 4 let-down (t/h)
            },
            "HP_VENT": {                         # 329D005 HV-329601 atmospheric vent
                "pct":  round(s.steam.hv_vent_hp_pct, 1),
                "m_th": round(s.steam.m_vent_hp * 3.6, 2),
            },
            "LP_MAKEUP": {                       # 4-bar make-up / vent balance
                "PV_329207C": round(s.steam.valve_963_pct, 1),      # BL -> 4-bar (stream 963)
                "m_963_th":   round(s.steam.m_963 * 3.6, 2),
                "m_pic_th":   round(s.steam.m_pic * 3.6, 2),        # PIC-329207A/B vent(+)/make-up(-)
            },
            "PIC_329204": {                      # 329D005 HP-saturator faceplate (PV=MP header P)
                "pv":   round(s.steam.P_MP, 2),                     # bar a
                "sp":   round(s.steam.pic204_sp, 2),
                "op":   round(s.steam.valve_supply_pct, 1),        # PV-329204 opening (%)
                "mode": s.steam.pic204_mode,
            },
            "PIC_329205": {                      # 329D009 split-range faceplate (PV=9-bar drum P)
                "pv":   round(s.steam.P_9, 2),                      # bar a
                "sp":   round(s.steam.pic205_sp, 2),
                "op":   round(s.steam.valve_admit9_pct - s.steam.valve_letdown_pct, 1),  # net split % (+205A admit / -205B let-down)
                "mode": s.steam.pic205_mode,
            },
            "PIC_329207": {                      # 4-bar header (leg-B alias; PV=LP header P)
                "pv":   round(s.steam.P_LP, 2),                     # bar a
                "sp":   round(s.steam.pic207_sp, 2),
                "op":   round(s.steam.m_pic * 3.6, 2),             # net vent(+)/make-up(-) t/h
                "mode": s.steam.pic207_mode,
            },
            "MASTER_SP_329207": {                # 4-bar header MASTER SP faceplate (ON/OFF cascade)
                "on": s.steam.master207_on,
                "sp": round(s.steam.master207_sp, 2),              # bar a
                "pv": round(s.steam.P_LP, 2),
            },
            "PIC_329207A": {                     # vent PV-329207A (SP = master + 0.1)
                "pv":   round(s.steam.P_LP, 2),
                "sp":   round(s.steam.pic207a_sp, 2),
                "op":   round(s.steam.pv207a_pct, 1),              # valve %
                "mode": s.steam.pic207a_mode,
            },
            "PIC_329207B": {                     # turbine 320MT02 make-up PV-329207B (SP = master)
                "pv":   round(s.steam.P_LP, 2),
                "sp":   round(s.steam.pic207_sp, 2),
                "op":   round(s.steam.pv207b_pct, 1),              # valve %
                "mode": s.steam.pic207_mode,
            },
            "PIC_329207C": {                     # BL admit PV-329207C (SP = master - 0.1)
                "pv":   round(s.steam.P_LP, 2),
                "sp":   round(s.steam.pic207c_sp, 2),
                "op":   round(s.steam.valve_963_pct, 1),           # valve %
                "mode": s.steam.pic207c_mode,
            },
            "LIC_329502": {                      # 329D005 HP-saturator level -> LV-329502 drain to 329D009
                "pv":   round(s.steam.lic502_lvl, 1),              # level %
                "sp":   round(s.steam.lic502_sp, 1),
                "op":   round(s.steam.lic502_op, 1),               # LV-329502 %
                "mode": s.steam.lic502_mode,
            },
            "LIC_329503": {                      # 329D009 MP-drum level -> LV-329503 drain to 322D001A/B
                "pv":   round(s.steam.lic503_lvl, 1),              # level %
                "sp":   round(s.steam.lic503_sp, 1),
                "op":   round(s.steam.lic503_op, 1),               # LV-329503 %
                "mode": s.steam.lic503_mode,
            },
            "LIC_329504": {                      # 322D001A/B LP-drum level -> LV-329504 make-up f.329P001
                "pv":   round(s.steam.lic504_lvl, 1),              # level %
                "sp":   round(s.steam.lic504_sp, 1),
                "op":   round(s.steam.lic504_op, 1),               # LV-329504 %
                "mode": s.steam.lic504_mode,
            },
        },
        "REACT_322R001": {                       # HP Urea Reactor 322R001 -> 322E001 / 322E003
            "TT_322005":   round(s.react_T_node[3], 1),  # N6 A top (EL +21700) — node-4 DYNAMIC profile
            "TT_322006":   round(s.react_T_node[2], 1),  # N6 B     (EL +14800) — node-3 DYNAMIC profile
            "TT_322007":   round(s.react_T_node[1], 1),  # N6 C     (EL  +7900) — node-2 DYNAMIC profile
            "TT_322008":   round(s.react_T_node[0], 1),  # N6 D bot (EL  +1000) — node-1 DYNAMIC profile
            "TT_322009":   round(react["T_offgas"], 1),      # off-gas line -> 322E003 (C, live profile)
            "LT_322504":   round(s.react_lt322504_pct, 1),   # N7 narrow-band reading (1.5 m span, top tap 1 m above overflow) — DYNAMIC
            "AT_322701":   round(d_AT322701, 3),  # N/C molar ratio ->322E001 (lagged analyzer)
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
            "TT_322011":   round(d_TT322011, 1),      # off-gas temp -> HV-322604 (C, lagged)
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
            "TT_322011_lp":round(d_TT322011l, 1),        # off-gas T after HV-322604 (JT-cooled, C, lagged)
            "og_lp_th":    round(hv604["mass_kgh"] / 1000.0, 3),  # HV-322604 vented off-gas mass flow (t/h, live)
            "vent_frac":   round(scrub["vent_frac"], 4),     # HV-322604 vent capacity / required purge (<1 -> PT rises)
            "P_offgas":    round(scrub["P_offgas"], 1),      # off-gas line P (bar a)
            "P_overflow":  round(scrub["P_overflow"], 1),    # PT-329201 overflow line P (bar a)
            "TT_322002":   round(d_TT322002, 1),    # overflow temp -> 322F001 (C, lagged)
            # Option 3: LT-329501 now reads the TRUE 322E003 sump inventory state (holdup ODE):
            #     50% design NLL when cond==entrain; RISES on ejector stall as entrainment collapses.
            "LT_329501":   round(s.scrub_level_pct, 1),  # 322E003 sump level (%, true dynamic inventory)
            "ccw": {                              # shell-side CCW loop (329P006 A/B pump + 329E004 cooler)
                "TT_329125":  round(d_TT329125, 2),     # CCW return temp out of shell (C, lagged)
                "TDY_329125": round(TDY_329125, 2),             # TT-329125 − TIC-329005 (cond. quality, C) — live PT-329201 cascade
                "vent_ratio": round(scrub["vent_ratio"], 4),    # synthesis-vent load PT-329201/PT_des (= nu, prior-step state)
                "rho_cond":   round(scrub["rho_cond"], 4),      # condensation capacity/demand (CCW flow / vent load); <1 -> PT-329201 rises
                "co2_free":   round(scrub["co2_free"], 1),      # free acid CO2 overhead (pressure-building, kmol/h)
                "pb_push":    round(scrub["pb_push"], 5),       # PT forward push = pressure-building overhead deviation (0 at design)
                "PI_322E002": round(d_HPCC_P, 1),    # 322E002 HPCC bubble-point synthesis P (bar a, lagged)
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
        "CRYST":   cryst,                              # Bug 2 per-equipment predictive freezing margins
        "flags":   {k: v for k, v in s.flags.items()}, # Bug 2 crystallization + existing phase-boundary flags
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
# Unit-323 inline I-PD controller command whitelist.  These 8 loops are plain dicts on `state`
#   (velocity-form EU-unit I-PD, NOT Controller-class instances), so they are unreachable via the
#   /api/ctrl REST route and are commanded through handle_cmd like the steam-system inline dicts.
#   The whitelist bounds getattr() to these exact attributes (no arbitrary state write via a crafted
#   id) and the mode map fixes each loop's legal modes (cascade slaves add CAS; masters/levels do not).
R323_CTRL_MODES = {
    "TIC_323007": ("MAN", "AUTO"),
    "PIC_329202": ("MAN", "AUTO", "CAS"),
    "LIC_323501": ("MAN", "AUTO"),
    "LIC_323505": ("MAN", "AUTO"),
    "TIC_323012": ("MAN", "AUTO"),
    "PIC_329208": ("MAN", "AUTO", "CAS"),
    "LIC_323507": ("MAN", "AUTO"),
    "FIC_324401": ("MAN", "AUTO", "CAS"),
    # -- 323-2 (LP recirculation) ------------------------------------------
    "PIC_323202": ("MAN", "AUTO"),
    "PIC_323203": ("MAN", "AUTO"),
    "LIC_323502": ("MAN", "AUTO"),          # drum-level master -> SIC-323901
    "SIC_323901": ("MAN", "AUTO", "CAS"),   # pump-speed slave
    "SIC_323902": ("MAN",),                 # standby pump, MAN-0 spare
    "LIC_323503": ("MAN", "AUTO"),
    "TIC_323013": ("MAN", "AUTO", "CAS"),
    "FIC_323401": ("MAN", "AUTO"),
    "FIC_323402": ("MAN", "AUTO"),
    "FIC_323405": ("MAN", "AUTO", "CAS"),   # CAS: LIC-323503 total-draw slave
    "FIC_323418": ("MAN", "AUTO"),
    # -- 328-1 (desorption / hydrolysis) -----------------------------------
    "LIC_328501": ("MAN", "AUTO"),
    "PIC_328202": ("MAN", "AUTO"),
    "TIC_328002": ("MAN", "AUTO"),
    "FIC_328404": ("MAN", "AUTO", "CAS"),
    "FIC_326402": ("MAN", "AUTO", "CAS"),
    "PIC_328203": ("MAN", "AUTO"),
    "FFIC_328401": ("MAN", "AUTO"),         # steam/feed ratio master
    "FIC_328401": ("MAN", "AUTO", "CAS"),   # LP-steam slave
    "TIC_328008": ("MAN", "AUTO"),
    "TIC_328012": ("MAN", "AUTO"),
    "LIC_328503": ("MAN", "AUTO"),
    "LIC_328504": ("MAN", "AUTO"),
    "LIC_328505": ("MAN", "AUTO"),
    "FIC_328402": ("MAN", "AUTO"),
    "FIC_328406": ("MAN",),                 # standby transfer pump, MAN-0 spare
    # -- 328-2 (LP absorber) -----------------------------------------------
    "PIC_322201": ("MAN", "AUTO"),
    "LIC_322502": ("MAN", "AUTO"),
}

# Auxiliary running/standby pump pairs toggled from the 323-2/328 overlays.
AUX_PUMPS = ("323P001A", "323P001B", "322P002A", "322P002B",
             "328P001A", "328P001B", "328P003A", "328P003B")


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
        elif cmd["id"] == "322915":
            # 322C001 steam-flood valve.  Operator may CLOSE at will; the OPEN command is
            #   auto-latched by trip 22.1 (TT-322015 > 57 C) and cannot be forced open while
            #   the live over-temperature cause persists.
            if s.XV_322915:
                s.XV_322915 = False
            elif not s.trip_latched.get("22_1", False):
                s.XV_322915 = True

    elif t == "aux_pump_toggle":
        # {"type":"aux_pump_toggle","id":"322P002A"[,"mode":"AUTO"|"MAN"]}  running/standby spare.
        pid = str(cmd.get("id", ""))
        if pid in AUX_PUMPS:
            p = s.aux_pumps[pid]
            if "mode" in cmd:
                m = str(cmd["mode"]).upper()
                if m in ("AUTO", "MAN"):
                    p["mode"] = m
            if "on" in cmd:
                p["on"] = bool(cmd["on"])
            else:
                p["on"] = not p["on"]

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

    elif t == "steam_letdown_set":             # PV-329205B 9->4 let-down (NB: split-range PIC-329205
        if "op" in cmd:                        #   AUTO-drives this each tick -> manual write is transient)
            s.steam.valve_letdown_pct = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "steam_hpvent_set":              # HV-329601 329D005 HP saturator atmospheric vent
        if "op" in cmd:
            s.steam.hv_vent_hp_pct = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "steam_963_set":                 # PV-329207C+HV-329602 BL(25)->4-bar header make-up (963)
        if "op" in cmd:
            s.steam.valve_963_pct = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "pic329204_set":                 # 329D005 HP-saturator PIC-329204 -> PV-329204 (25->MP supply)
        m = str(cmd.get("mode", s.steam.pic204_mode)).upper()
        if m in ("AUTO", "MAN"):
            s.steam.pic204_mode = m            # MAN freezes valve_supply_pct; i_204 held -> bumpless
        if "sp" in cmd:
            s.steam.pic204_sp = clamp(_finite(cmd["sp"], "sp"), 0.0, 25.0)
        if "op" in cmd and s.steam.pic204_mode == "MAN":
            s.steam.valve_supply_pct = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "pic329205_set":                 # 329D009 split-range PIC-329205 (mode/SP; op=split-range in MAN)
        m = str(cmd.get("mode", s.steam.pic205_mode)).upper()
        if m in ("AUTO", "MAN"):
            s.steam.pic205_mode = m            # MAN freezes AUTO writes; op below drives the split legs
        if "sp" in cmd:
            s.steam.pic205_sp = clamp(_finite(cmd["sp"], "sp"), 0.0, 25.0)
        if "op" in cmd and s.steam.pic205_mode == "MAN":
            # single-op split-range: 0-50% -> PV-329205A (admit) 0-100 ; 50-100% -> PV-329205B (let-down) 0-100
            op = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)
            if op <= 50.0:
                s.steam.valve_admit9_pct  = op * 2.0
                s.steam.valve_letdown_pct = 0.0
            else:
                s.steam.valve_admit9_pct  = 0.0
                s.steam.valve_letdown_pct = (op - 50.0) * 2.0

    elif t == "lic329502_set":                 # 329D005 level LIC-329502 -> LV-329502 (drain to 329D009)
        m = str(cmd.get("mode", s.steam.lic502_mode)).upper()
        if m in ("AUTO", "MAN"):
            if m == "AUTO" and s.steam.lic502_mode != "AUTO":     # bumpless SP<-PV on AUTO entry
                s.steam.lic502_sp = clamp(s.steam.lic502_lvl, 0.0, 100.0)
            s.steam.lic502_mode = m            # MAN freezes LV-329502 (op held; ep updated -> bumpless)
        if "sp" in cmd:
            s.steam.lic502_sp = clamp(_finite(cmd["sp"], "lic_sp"), 0.0, 100.0)
        if "op" in cmd and s.steam.lic502_mode == "MAN":
            s.steam.lic502_op = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "lic329503_set":                 # 329D009 level LIC-329503 -> LV-329503 (drain to 322D001A/B)
        m = str(cmd.get("mode", s.steam.lic503_mode)).upper()
        if m in ("AUTO", "MAN"):
            if m == "AUTO" and s.steam.lic503_mode != "AUTO":     # bumpless SP<-PV on AUTO entry
                s.steam.lic503_sp = clamp(s.steam.lic503_lvl, 0.0, 100.0)
            s.steam.lic503_mode = m            # MAN freezes LV-329503 (op held; ep updated -> bumpless)
        if "sp" in cmd:
            s.steam.lic503_sp = clamp(_finite(cmd["sp"], "lic_sp"), 0.0, 100.0)
        if "op" in cmd and s.steam.lic503_mode == "MAN":
            s.steam.lic503_op = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "lic329504_set":                 # 322D001A/B level LIC-329504 -> LV-329504 (make-up f.329P001)
        m = str(cmd.get("mode", s.steam.lic504_mode)).upper()
        if m in ("AUTO", "MAN"):
            if m == "AUTO" and s.steam.lic504_mode != "AUTO":     # bumpless SP<-PV on AUTO entry
                s.steam.lic504_sp = clamp(s.steam.lic504_lvl, 0.0, 100.0)
            s.steam.lic504_mode = m            # MAN freezes LV-329504 (op held; ep updated -> bumpless)
        if "sp" in cmd:
            s.steam.lic504_sp = clamp(_finite(cmd["sp"], "lic_sp"), 0.0, 100.0)
        if "op" in cmd and s.steam.lic504_mode == "MAN":
            s.steam.lic504_op = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "pic329207_set":                 # 4-bar header leg-B PIC-329207 (mode/SP only; design-neutral)
        m = str(cmd.get("mode", s.steam.pic207_mode)).upper()
        if m in ("AUTO", "MAN"):
            s.steam.pic207_mode = m            # MAN freezes PV-329207B (pv207b_pct held, i_pic held -> bumpless)
        if "sp" in cmd:
            s.steam.pic207_sp = clamp(_finite(cmd["sp"], "sp"), 0.0, 25.0)

    elif t == "master207_set":                 # 4-bar header MASTER SP (ON/OFF cascade over PIC-329207A/B/C)
        if "on" in cmd:
            s.steam.master207_on = bool(cmd["on"])
        if "sp" in cmd:
            s.steam.master207_sp = clamp(_finite(cmd["sp"], "sp"), 0.0, 25.0)

    elif t in ("pic329207a_set", "pic329207b_set", "pic329207c_set"):
        # Individual sub-controller writes; honored only when MASTER is OFF (ON locks the trio to master).
        if not s.steam.master207_on:
            leg = t[9]                         # 'a' | 'b' | 'c'  in "pic329207X_set"
            m = str(cmd.get("mode", "")).upper()
            if leg == "a":
                if m in ("AUTO", "MAN"): s.steam.pic207a_mode = m
                if "sp" in cmd: s.steam.pic207a_sp = clamp(_finite(cmd["sp"], "sp"), 0.0, 25.0)
                if "op" in cmd and s.steam.pic207a_mode == "MAN":
                    s.steam.pv207a_pct = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)
            elif leg == "b":
                if m in ("AUTO", "MAN"): s.steam.pic207_mode = m
                if "sp" in cmd: s.steam.pic207_sp = clamp(_finite(cmd["sp"], "sp"), 0.0, 25.0)
                if "op" in cmd and s.steam.pic207_mode == "MAN":
                    s.steam.pv207b_pct = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)
            else:  # leg == "c"
                if m in ("AUTO", "MAN"): s.steam.pic207c_mode = m
                if "sp" in cmd: s.steam.pic207c_sp = clamp(_finite(cmd["sp"], "sp"), 0.0, 25.0)
                if "op" in cmd and s.steam.pic207c_mode == "MAN":
                    s.steam.valve_963_pct = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

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

    elif t == "r323_ctrl_set":                     # Unit-323 recirc/pre-evap inline I-PD faceplates
        # {"type":"r323_ctrl_set","id":<tag>,"mode":?,"sp":?,"op":?}.  Velocity form is inherently
        #   bumpless (op held on any mode change; pv1/pv2 history advances every tick even in MAN, so
        #   no derivative kick and no integral to reset).  SP<-PV on AUTO entry avoids a setpoint step;
        #   SP writes gated to AUTO, OP writes gated to MAN (CAS SP is driven by the master each tick).
        cid = str(cmd.get("id", "")).replace("-", "_")   # faceplate sends dash-tags (TIC-323007); whitelist keys are underscore
        c   = getattr(s, cid, None) if cid in R323_CTRL_MODES else None
        if c is not None:
            if "mode" in cmd:
                m = str(cmd["mode"]).upper()
                if m in R323_CTRL_MODES[cid]:
                    if m == "AUTO" and c["mode"] != "AUTO":      # bumpless SP<-PV on AUTO entry
                        c["sp"] = clamp(c["pv"], c["sp_lo"], c["sp_hi"])
                    c["mode"] = m
            if "sp" in cmd and c["mode"] == "AUTO":
                c["sp"] = clamp(_finite(cmd["sp"], "sp"), c["sp_lo"], c["sp_hi"])
            if "op" in cmd and c["mode"] == "MAN":
                c["op"] = clamp(_finite(cmd["op"], "op"), c["op_lo"], c["op_hi"])


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
    """Design-pin HPCC_UA at the RECONCILED design point (synthetic single-call feed at W0/L0 -- the
    same basis tests/audit_e002_hpcc.py checks the gate=1 quench against).  The scrubber-tear
    reconciliation moved the design anchor onto W0/L0; post-recon the SETTLED-live loop attractor
    drifts off W0/L0 (W_feed~=0.410, L~=3.128), so pinning UA on the settled state lands the gate=1
    design quench HIGH (T_prod~=170.41 > 170 -> q_steam < duty).  We therefore back-calc UA on the
    synthetic design feed evaluated exactly at the reconciled W0/L0 (m_dot/T_adb are UA- and
    gate-independent pure feed properties):

        g_syn = stripper_322e001(CO2_DES, ..., L_feed=L0_DES, W_feed=W0_DES)
        l_syn = ejector_322f001(EJ_MOTIVE_NH3_DES, ...)        # nameplate motive
        d_syn = hpcc_322e002(g_syn, l_syn, gate=1.0)           # read m_dot/T_adb only
        UA    = -m_dot*cp * ln[(T_prod_des - T_sat) / (T_adb - T_sat)]

    LIVE loop is unaffected: at design steady state it runs gate~=0, where hpcc_322e002 holds
    T_prod == 170.0 C for ANY UA (gate masks the NTU term), so this re-pin only sets the gate=1
    design-audit quench and the off-design (disturbed) NTU response.  Anchors TT-322010 to exactly
    170.0 C at the reconciled design point."""
    global HPCC_UA, state, last_packet, hpcc_322e002, react_322r001, ejector_322f001
    global REACT_MASS_DES, HPCC_LIQ_DES_LIVE, EJ_MOTIVE_DES_LIVE, _STEAM_READY
    global REACT_TEAR_DES, REACT_L_FEED_DES, REACT_W_FEED_DES, REACT_X_DES
    global HPCC_NC_DES_LIVE
    state.SIC_321951.set_mode("CAS")                 # match the live design driver (ratio cascade)
    _orig = hpcc_322e002                             # capture the settled HPCC product (HPCC_UA back-calc)
    _orig_ej = ejector_322f001                       #   and the settled design motive NH3 for the
    _cap = {}                                        #   EJ_MOTIVE_DES_LIVE -> phi_m bit-exact pin
    def _cap_hpcc(gas_feed, liq_feed, **kw):
        r = _orig(gas_feed, liq_feed, **kw)
        _cap["r"] = r
        return r
    def _cap_ej(motive, *a, **kw):
        rr = _orig_ej(motive, *a, **kw)
        _cap["ejm"] = motive
        return rr
    hpcc_322e002 = _cap_hpcc
    ejector_322f001 = _cap_ej
    for _ in range(18000):                           # 30 sim-min @ dt=0.1 s -> settled design steady state
        step_sim(0.1)
    hpcc_322e002 = _orig
    ejector_322f001 = _orig_ej
    r = _cap["r"]
    # ISSUE-c reactor mass-conservation refs are NOT pinned here on the CAS warm-up settle (wrong
    # operating point: the off-gas carries the conversion-deficit amplification and the feed differs
    # from the MAN seed).  They are pinned below at the MAN runtime design seed -- see REACT_MASS_DES
    # following `state = State()`.
    HPCC_LIQ_DES_LIVE = r["liq_kgh"]                 # ISSUE-c/e: anchor LT-322E002 NLL fixed point
    EJ_MOTIVE_DES_LIVE = _cap["ejm"]                 # settled live design motive NH3 -> phi_m == 1 exact
    # L3-4 boot-pin domain assert: the UA back-calc log requires 0 < (T_prod_des - T_sat)/(T_adb - T_sat)
    #   < 1, i.e. T_adb > T_prod_des > T_sat_shell.  A failed warm-up settle (bad steam/feed) would feed
    #   a non-positive or >1 argument -> ValueError/NaN at import.  Fail loud here instead of hiding it.
    # back-calc UA on the RECONCILED synthetic design feed at W0/L0 (audit gate=1 basis), NOT the
    #   settled-live `r` (drifts off W0/L0 post-recon).  m_dot/T_adb are UA/gate-independent.
    _g_syn = stripper_322e001(CO2_DES_KGH / 1000.0, STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA,
                              overflow_kmolh=STRIP_FEED207_KMOLH,
                              L_feed=reactor.L0_DES, W_feed=reactor.W0_DES)
    _l_syn = ejector_322f001(EJ_MOTIVE_NH3_DES, EJ_MOTIVE_T_DES_C, EJ_OPEN_DES)
    _d_syn = hpcc_322e002(_g_syn, _l_syn, t_shell=HPCC_STEAM_TSAT_C, gate=1.0)
    assert _d_syn["T_adb"] > HPCC_T_PROD_DES_C > HPCC_STEAM_TSAT_C, "HPCC UA back-calc domain error"
    HPCC_UA = -_d_syn["m_dot"] * HPCC_CP_GAS * math.log(
        (HPCC_T_PROD_DES_C - HPCC_STEAM_TSAT_C) / (_d_syn["T_adb"] - HPCC_STEAM_TSAT_C))
    state = State()                                  # discard the warm-up transient (fresh design seed)

    # ---- ISSUE-c: pin the reactor mass-conservation refs at the MAN RUNTIME design seed (where the
    #   live loop AND the unit tests actually operate: `State(); step_sim()`), NOT the CAS warm-up
    #   settle above.  The overflow/off-gas refs are the DETERMINISTIC pinned design-vector masses
    #   (at design s=1, phi=phi_des, delta_X=0 -> amp=1 and nh3_shift~=0, so the emitted vectors equal
    #   REACT_OVERFLOW_DES / REACT_OFFGAS_DES exactly); only the feed mass is genuinely upstream-coupled
    #   (ejector phi_m^2 / HPCC), so capture it from the first MAN-seed reactor step.  Then every delta
    #   is identically 0 at the seed -> f_cons == 1.0 bit-exact (restores the design pin).
    _orig_r2 = react_322r001
    _capf = {}
    def _cap_react2(*a, **kw):
        rr = _orig_r2(*a, **kw)
        _capf["feed"]    = rr["feed_kmolh"]
        _capf["xi_urea"] = rr["xi_urea"]; _capf["xi_biu"] = rr["xi_biu"]
        _capf["L"]       = rr["L_feed"];  _capf["W"]      = rr["W_feed"]
        _capf["X"]       = rr["X_conv"]
        # design HPCC carbamate-MELT N/C (NH3/CO2) for the bubble_p_322e002 fN anchor.  a[0] is the
        #   hpcc dict (positional); hpcc_322e002 runs BEFORE react_322r001 this step so its raw combined
        #   melt feed is populated.  This is the NH3-richer melt N/C (~3.12324), DISTINCT from the
        #   reactor-feed N/C L (3.07296) captured above.  Guard a zero/absent CO2 (pre-warm pathological).
        _hf  = a[0].get("feed_kmolh", {}) if a else {}
        _co2 = _hf.get("CO2", 0.0)
        if _co2 > 1e-9:
            _capf["hpcc_L"] = _hf.get("NH3", 0.0) / _co2
        return rr
    react_322r001 = _cap_react2
    step_sim(0.1)                                    # one MAN-seed step (REACT_TEAR_DES still None ->
    react_322r001 = _orig_r2                          #   tear inactive -> feed_corrected == raw feed)
    REACT_MASS_DES = (
        sum(_capf["feed"].get(k, 0.0)        * MW_COMP[k] for k in MW_COMP),
        sum(REACT_OVERFLOW_DES.get(k, 0.0)   * MW_COMP[k] for k in MW_COMP),
        sum(REACT_OFFGAS_DES.get(k, 0.0)     * MW_COMP[k] for k in MW_COMP))
    # ---- C-1 ISSUE-c: pin the explicit recycle-tear vector + conservative-shift anchors (Basis A).
    #   implied_feed_i = (OVd_i + OGd_i) - sum_r nu_{i,r} * xi_pin_r  is the CLOSED feed that makes
    #   out_total == published design exactly; TEAR_DES_i = feed_des_i - implied_feed_i is the torn
    #   recycle (the undocumented ~2 % the published HMB drops).  Subtracting TEAR_DES*s from the raw
    #   feed gives feed_corrected, and out_total = feed_corrected + nu*xi closes atoms AND mass to
    #   machine zero.  At the seed xi_live == xi_pin and feed == feed_des -> feed_corrected restores
    #   the closed design feed -> overflow/off-gas partition == published vectors bit-exact.
    _xu, _xb = _capf["xi_urea"], _capf["xi_biu"]
    _impl = {k: REACT_OVERFLOW_DES.get(k, 0.0) + REACT_OFFGAS_DES.get(k, 0.0) for k in MW_COMP}
    _impl["CO2"]    += _xu
    _impl["NH3"]    += 2.0 * _xu - _xb
    _impl["Urea"]   += -_xu + 2.0 * _xb
    _impl["H2O"]    += -_xu
    _impl["Biuret"] += -_xb
    REACT_TEAR_DES   = {k: _capf["feed"].get(k, 0.0) - _impl[k] for k in MW_COMP}
    REACT_L_FEED_DES = _capf["L"]; REACT_W_FEED_DES = _capf["W"]; REACT_X_DES = _capf["X"]
    HPCC_NC_DES_LIVE = _capf.get("hpcc_L", REACT_L_FEED_DES)   # design melt N/C -> bubble_p fN anchor (P_bub==144.2)
    state = State()                                  # discard the capture step (fresh design seed)

    # ---- pin the steam-header valve coeffs so the runtime design seed is a STATIONARY fixed point.
    #   The steam shell T feeds BACK into the process (stripper eta_T_steam = f(tsat(P_MP))), so the
    #   headers must hold EXACTLY at the seed (19.7 / 4.4) or design bit-exactness is lost downstream.
    #   That requires net header flow == 0 at the seed, using the design HPCC duty AS SEEN AT THE
    #   RUNTIME (MAN) STATE WITH STEAM FROZEN -- not the CAS warm-up r above.  So: re-seed, settle a
    #   second time with step_steam still gated OFF (_STEAM_READY=False), capture the frozen-steam
    #   design duty, then size the valves:
    #     MP:  supply(50% seed) == m_strip  (self-pinned in steam_system via K_902; nothing to size here)
    #     LP:  M_USERS_LP == m_hpcc_des     (4-bar users load-follow HPCC steam-raising -> m_pic == 0)
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
    _m_hpcc_des    = _duty_des / HPCC_LATENT_4BAR
    _ss.M_USERS_LP = _m_hpcc_des   # 4-bar users load-follow HPCC steam-raising -> m_pic == 0 at design
    _ss.M_504_DES  = _m_hpcc_des   # LV-329504 condensate makeup (329P001A/B) sized to the real design LP
                                   #   boil-off so at the seed op (50%) m_valve == m_hpcc -> dm == 0 and
                                   #   322D001A/B level holds; the static 3.0 placeholder undersized the
                                   #   valve (max 6 kg/s << 29.8) so makeup could not match boil-off and
                                   #   the level drained to 0 at startup.
    _STEAM_READY = True                              # arm step_steam for live operation
    state = State()                                  # fresh MAN design seed for the GCB capture below

    # ---- pin the 322C001 LP-absorber GCB off-gas design point (live HV-322604 JT product) at the MAN
    #   runtime seed, mirroring the reactor-mass pin.  The absorber runs PRE-PIN (T/P frozen, mass
    #   self-closed) through every settle above because A328_GCB_DES stays None until set here, so the
    #   warm-up never perturbs it.  Capture the settled-design off-gas from one MAN-seed step, then
    #   back-solve LAMBDA_ABS so the post-pin live energy balance sums to 0 at design (Tc001 == 43 C,
    #   bit-exact) while activating the live absorber dynamics off-design.
    global A328_GCB_DES, A328_GCB_T, A328_PHI_ABS, A328_VENT_DES, A328_LAMBDA_ABS, hv_322604
    _orig_hv = hv_322604
    _caphv   = {}
    def _cap_hv(offgas, T_in, hic_pct, p_up):
        rr = _orig_hv(offgas, T_in, hic_pct, p_up)
        _caphv["m"] = rr["mass_kgh"]; _caphv["T"] = rr["T_out"]
        return rr
    hv_322604 = _cap_hv
    step_sim(0.1)                                    # one MAN-seed step (absorber pre-pin -> holds)
    hv_322604 = _orig_hv
    _gcb_m = _caphv["m"]; _gcb_T = _caphv["T"]
    # SAME stage-7 sensible-heat kernel, evaluated at the pinned design off-gas and Tc001 == A328_C001_T:
    _sens_pin = ((A328_M755_DES*(A328_M755_T - A328_C001_T)
                  + A328_CPL_DES*(A328_CPL_T - A328_C001_T))/3600.0*A328_CP
                 + _gcb_m*(_gcb_T - A328_C001_T)/3600.0*A328_CP)
    A328_GCB_DES    = _gcb_m
    A328_GCB_T      = _gcb_T
    A328_PHI_ABS    = A328_ABS_DES / _gcb_m          # absorbed fraction (PHI_ABS*GCB_DES == A328_ABS_DES)
    A328_VENT_DES   = _gcb_m - A328_ABS_DES          # design vent = off-gas − absorbed
    A328_LAMBDA_ABS = -_sens_pin*3600.0/A328_ABS_DES # back-solved -> P_c001 == 0 at design (bit-exact)

    state = State()                                  # discard the capture step (fresh design seed)
    last_packet = {}


# ---- boot-pin result cache -----------------------------------------------------------------------
#   _pin_hpcc_ua() settles two design fixed points over 21,000 step_sim() ticks (~20 s) to compute a
#   handful of DETERMINISTIC calibration constants.  The result depends only on the simulation source,
#   so it is cached to disk keyed by a SHA-256 of the backend model files: an unchanged tree restores
#   the pinned constants in milliseconds; ANY model edit busts the key and forces a fresh settle.  The
#   exact computed constants are stored and restored -- the settle math is untouched -- so design
#   bit-exactness is preserved while the ~20 s import stall behind the desktop launch is removed.
_HERE           = os.path.dirname(os.path.abspath(__file__))
_PIN_CACHE_PATH = os.path.join(_HERE, ".boot_pin_cache.json")
_PIN_SRC_FILES  = ("main.py", "steam_system.py", "reactor.py", "controllers.py")


def _pin_cache_key() -> str:
    h = hashlib.sha256()
    for _fn in _PIN_SRC_FILES:
        try:
            with open(os.path.join(_HERE, _fn), "rb") as _f:
                h.update(_f.read())
        except OSError:
            h.update(b"\x00")            # missing source -> stable sentinel (busts again on reappear)
    return h.hexdigest()


def _apply_pin(d: dict) -> None:
    """Restore the pinned design constants from a cache dict (== state after a fresh _pin_hpcc_ua())."""
    global HPCC_UA, REACT_MASS_DES, HPCC_LIQ_DES_LIVE, EJ_MOTIVE_DES_LIVE
    global _STEAM_READY, state, last_packet
    global REACT_TEAR_DES, REACT_L_FEED_DES, REACT_W_FEED_DES, REACT_X_DES
    global HPCC_NC_DES_LIVE
    global A328_GCB_DES, A328_GCB_T, A328_PHI_ABS, A328_VENT_DES, A328_LAMBDA_ABS
    import steam_system as _ss
    HPCC_UA            = d["HPCC_UA"]
    REACT_MASS_DES     = tuple(d["REACT_MASS_DES"])
    HPCC_LIQ_DES_LIVE  = d["HPCC_LIQ_DES_LIVE"]
    EJ_MOTIVE_DES_LIVE = d["EJ_MOTIVE_DES_LIVE"]
    REACT_TEAR_DES     = {k: d["REACT_TEAR_DES"].get(k, 0.0) for k in MW_COMP}
    REACT_L_FEED_DES   = d["REACT_L_FEED_DES"]
    REACT_W_FEED_DES   = d["REACT_W_FEED_DES"]
    REACT_X_DES        = d["REACT_X_DES"]
    HPCC_NC_DES_LIVE   = d.get("HPCC_NC_DES_LIVE", REACT_L_FEED_DES)   # bubble_p fN anchor (design melt N/C)
    _ss.M_USERS_LP     = d["M_USERS_LP"]
    _ss.M_504_DES      = d["M_USERS_LP"]   # LV-329504 makeup == design LP boil-off (see _pin_hpcc_ua)
    A328_GCB_DES       = d["A328_GCB_DES"]
    A328_GCB_T         = d["A328_GCB_T"]
    A328_PHI_ABS       = d["A328_PHI_ABS"]
    A328_VENT_DES      = d["A328_VENT_DES"]
    A328_LAMBDA_ABS    = d["A328_LAMBDA_ABS"]
    _STEAM_READY       = True
    state              = State()         # fresh design seed (the settle transient is never persisted)
    last_packet        = {}


def _collect_pin() -> dict:
    import steam_system as _ss
    return {
        "HPCC_UA":            HPCC_UA,
        "REACT_MASS_DES":     list(REACT_MASS_DES),
        "HPCC_LIQ_DES_LIVE":  HPCC_LIQ_DES_LIVE,
        "EJ_MOTIVE_DES_LIVE": EJ_MOTIVE_DES_LIVE,
        "REACT_TEAR_DES":     dict(REACT_TEAR_DES),
        "REACT_L_FEED_DES":   REACT_L_FEED_DES,
        "REACT_W_FEED_DES":   REACT_W_FEED_DES,
        "REACT_X_DES":        REACT_X_DES,
        "HPCC_NC_DES_LIVE":   HPCC_NC_DES_LIVE,
        "M_USERS_LP":         _ss.M_USERS_LP,
        "A328_GCB_DES":       A328_GCB_DES,
        "A328_GCB_T":         A328_GCB_T,
        "A328_PHI_ABS":       A328_PHI_ABS,
        "A328_VENT_DES":      A328_VENT_DES,
        "A328_LAMBDA_ABS":    A328_LAMBDA_ABS,
    }


if HPCC_UA is None:
    _key = _pin_cache_key()
    _cached = None
    try:
        with open(_PIN_CACHE_PATH, "r", encoding="utf-8") as _f:
            _doc = json.load(_f)
        if _doc.get("key") == _key:
            _cached = _doc.get("pin")
    except (OSError, ValueError):
        _cached = None
    if _cached is not None:
        _apply_pin(_cached)              # cache hit: skip the 21k-tick settle
    else:
        _pin_hpcc_ua()                   # cache miss/stale: full settle, then persist for next launch
        try:
            with open(_PIN_CACHE_PATH, "w", encoding="utf-8") as _f:
                json.dump({"key": _key, "pin": _collect_pin()}, _f, indent=2)
        except OSError:
            pass                          # cache is an optimization; never fail import on a write error


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
