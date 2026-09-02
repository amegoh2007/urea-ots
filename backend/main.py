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
import sys
if __name__ == "__main__":
    sys.modules["main"] = sys.modules["__main__"]
import sys
if __name__ == "__main__":
    sys.modules["main"] = sys.modules["__main__"]
import os
import time
import threading
import traceback
from collections import deque
from typing import Optional, Set

import reactor  # 322R001 Modified Inoue-Kanai conversion kinetics (quarantined)
import thermo_extended_uniquac as extended_uniquac
import iapws_if97  # shared pure-water steam/condensate boundary (IAPWS-IF97 R7-97)
import gap_g6_h0_enthalpy as h0_enthalpy  # H0 stream enthalpy on the elements-at-298.15 K datum
import consequence  # ISA-75.01.01 consequence physics + plug-flow line transport (StreamPacket)
from core.thermo import EmpiricalThermo
thermo = EmpiricalThermo()
from controllers import Controller
import steam_system
from steam_system import SteamState, step_steam  # MP/LP steam-header dynamics (quarantined)
from c003_pressure_coupling import c003_pressure_target_bara, e011_vent_generation_kgh
from historian import Historian  # background trend recorder (plant-time sampled)

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


def _tsat_steam_antoine(p_bara: float) -> float:
    """Retained Antoine saturation-T oracle (superseded by IAPWS-IF97).

    Antoine equation for water (valid 100-374 C), pressure in mmHg:
        log10(P_mmHg) = 8.14019 - 1810.94 / (244.485 + T_C)
    inverted for temperature, with P_mmHg = P_bara * 750.0617.  Kept only as a
    versioned comparison oracle during the IF97 migration (G11).
    """
    p_mmhg = max(p_bara, 0.01) * 750.0616827
    return 1810.94 / (8.14019 - math.log10(p_mmhg)) - 244.485


def _psat_water_antoine(T_C: float) -> float:
    """Retained Antoine saturation-P oracle (superseded by IAPWS-IF97)."""
    p_mmhg = 10.0 ** (8.14019 - 1810.94 / (244.485 + T_C))
    return p_mmhg / 750.0616827


def tsat_steam(p_bara: float) -> float:
    """Saturated-steam temperature [deg C] from absolute pressure [bar a].

    Now backed by the shared IAPWS-IF97 pure-water boundary (Region 4, Eq.31),
    which reproduces the official IF97 saturation line to <1e-9 relative error.
    Every steam-heated shell and the 329 header network share this one call so
    saturation, latent heat, and condensate enthalpy come from one reference
    state.  The design point is preserved by construction: each UA/eta_T anchor
    is itself defined as ``tsat_steam(P_design)`` and every live duty divides by
    the same call, so a design-pressure query returns the design temperature and
    only the off-design slope now follows IF97 instead of Antoine (worst
    Antoine->IF97 shift 0.02 C at the 19.7 bar stripper design point).
    """
    return iapws_if97.tsat_c(p_bara)


def psat_water_bara(T_C: float) -> float:
    """Saturated-water vapour pressure [bar a] from temperature [deg C].

    Analytic partner of tsat_steam, now the IAPWS-IF97 forward saturation
    pressure (Region 4, Eq.30).  tsat_steam(psat_water_bara(T)) == T holds to
    IF97 inversion tolerance, so every bubble-point round trip is preserved.
    """
    return iapws_if97.psat_bara(T_C)


def conc_infer_324(w_des: float, T_des: float, P_des: float,
                   T_live: float, P_live: float) -> float:
    """Urea-melt concentration soft sensor [wt %] (PY-324201 / AY-324701).

    Uses the same neutral-species Extended-UNIQUAC boundary as the material
    balance. The strict PFD state remains an additive design calibration; only
    the live departure is predicted by the published activity model.
    """
    return 100.0 * evap_w_eq(T_live, P_live, w_des, T_des, P_des)


def evap_w_eq(T_C: float, P_bara: float, w_des: float, T_des: float, P_des: float) -> float:
    """Anchored H2O/urea Extended-UNIQUAC equilibrium mass fraction.

    H2O and urea are neutral, so the Extended-UNIQUAC Debye-Huckel term is
    zero and the liquid model reduces to binary UNIQUAC. The design HMB point
    is preserved exactly while its off-design slope comes from the model.
    """
    w_model = extended_uniquac.solve_urea_mass_fraction_fast(T_C + 273.15, P_bara)
    w_model_des = extended_uniquac.solve_urea_mass_fraction_fast(
        T_des + 273.15, P_des
    )
    return clamp(w_des + (w_model - w_model_des), 1.0e-9, 1.0 - 1.0e-9)


# ===================================================================
#  AI-328701  process-condensate conductivity soft sensor  (stream 740)
#  Node: 328E007 hot outlet (739) -> 740 boundary -> 328P007, 89 C.
#  Live trace NH3 / urea ppm are DERIVED BOTTOM-UP (not back-solved from
#  the 1 ppm guarantee): Desorber-II (328C004) tray efficiency comes from
#  the datasheet geometry via O'Connell (1946) [E_o=0.635, 22 perf trays],
#  the residual NH3 slip from Kremser (1930) stripping, and the urea slip
#  from the published second-order urea-water hydrolysis law in 328C003.  Both are emitted in
#  ANCHORED-CORRECTION form (residual RATIO vs the plant's own design
#  state) so each is bit-exact the PFD 1 ppm guarantee at the design point
#  and only moves off-design.  Read-only readout: no state, no coupling to
#  the pinned H&MB.  See scratchpad/derive_328_trace.py for the derivation.
# -------------------------------------------------------------------
R328_AI701_NH3_PPM_DES  = 1.0        # PFD stream 740 NH3 guarantee   (ppm mass)
R328_AI701_UREA_PPM_DES = 1.0        # PFD stream 740 urea guarantee  (ppm mass)
R328_AI701_KINF_C004    = 9.5        # derived dilute NH3-water stripping factor K_inf @143 C, Desorber-II
R328_AI701_NTHEO_C004   = 13.98      # theoretical stages = E_o(0.635) x 22 actual (O'Connell + geom)
R328_AI701_DHSTRIP      = 34200.0    # J/mol, NH3-water differential enthalpy of solution (Perry's) -> K(T)
R328_AI701_TAU_S        = 3600.0     # s, 328C003 hydrolyser residence time (tau)
R328_AI701_UREA_PHI     = 0.05       # urea-slip partial-hydrolysis fraction in the hot condensate line
# Kohlrausch limiting molar ionic conductivities  Lambda_0  (S.cm2/mol, CRC 25 C):
R328_AI701_KB_NH3       = 1.8e-5     # NH3 + H2O <-> NH4+ + OH- base dissociation constant (CRC)
R328_AI701_L0_NH4       = 73.5
R328_AI701_L0_OH        = 198.0
R328_AI701_L0_HCO3      = 44.5
_R328_MW_NH3, _R328_MW_UREA, _R328_MW_CO2 = 17.0304, 60.056, 44.01


def _kremser_resid(S: float, N_theo: float) -> float:
    """Kremser (1930) residual liquid fraction x_out/x_in for a stripping
    section: r = (S-1)/(S^(N+1)-1), S = K*V/L. Continuous at S->1."""
    if abs(S - 1.0) < 1e-9:
        return 1.0 / (N_theo + 1.0)
    return (S - 1.0) / (S ** (N_theo + 1.0) - 1.0)


def ppm_infer_328701(T_c004: float, T_c003: float):
    """Live trace (NH3 ppm, urea ppm) in stream 740, anchored-correction form.

    NH3: the Desorber-II residual slip is Kremser r(S,N_theo) with the derived
    E_o-based stage count and the dilute strip factor S = K(T)*(V/L).  The design
    strip ratio V/L is the PFD 100%-load steam/bottoms split (R328_C004_M931_DES/
    R328_C004_M739_DES); the LP-strip steam (FIC-329401) is pinned at that design
    duty in the current H&MB, so the live OFF-DESIGN driver is the Desorber-II
    operating temperature, which sets the NH3 relative volatility via a
    Clausius-Clapeyron K(T) = K_inf*exp(-(dH/R)(1/T - 1/T_des)) [dH = NH3-water
    enthalpy of solution].  The slip is the residual RATIO r(S_live)/r(S_des), so
    it is bit-exact R328_AI701_NH3_PPM_DES (=1 ppm) at the 143 C design point and
    rises as the column cools (K falls -> less stripping) -- physically correct.

    Urea: the Inoue/Otsuka second-order urea-water PFR residual in 328C003, scaled by
    the ratio vs the 200 C design residual, so it is bit-exact 1 ppm at design T and
    rises as the hydrolyser cools (k falls -> more urea slip)."""
    vol_des = R328_C004_M931_DES / R328_C004_M739_DES        # PFD design molar V/L (MW ~cancels)
    N = R328_AI701_NTHEO_C004
    Tc4_des_K, Tc4_live_K = R328_C004_T + 273.15, T_c004 + 273.15
    K_live = R328_AI701_KINF_C004 * math.exp(
        -(R328_AI701_DHSTRIP / 8.314) * (1.0 / Tc4_live_K - 1.0 / Tc4_des_K))
    r_des = _kremser_resid(R328_AI701_KINF_C004 * vol_des, N)
    r_live = _kremser_resid(K_live * vol_des, N)
    nh3_ppm = R328_AI701_NH3_PPM_DES * (r_live / r_des if r_des > 0.0 else 1.0)

    x_des = hydrolysis_x_328c003(R328_C003_T, R328_C003_M746_DES)
    x_live = hydrolysis_x_328c003(T_c003, R328_C003_M746_DES)
    resid_des = max(1.0 - x_des, 1e-300)
    urea_ppm = R328_AI701_UREA_PPM_DES * ((1.0 - x_live) / resid_des)
    return max(nh3_ppm, 0.0), max(urea_ppm, 0.0)


def cond_infer_328701(nh3_ppm: float, urea_ppm: float, co2_ppm: float) -> float:
    """Condensate conductivity kappa [uS/cm, temperature-compensated to 25 C]
    from the live trace composition, via the Kohlrausch independent-ion matrix.

    NH3 is a weak base: [OH-]^2/(C_NH3 - [OH-]) = Kb  ->  [NH4+]=[OH-].
    Dissolved CO2 in the ammoniacal condensate carries as HCO3- (with a matching
    NH4+ from neutralisation).  Urea is non-ionic, but the fraction that partially
    hydrolyses in the hot condensate line (NH2CONH2 + H2O -> 2 NH3 + CO2) adds to
    both the NH3 and CO2 ion pools -- so urea explicitly moves the reading.
    kappa = sum_i c_i[mol/cm3] * Lambda0_i * 1e6."""
    c_urea = max(urea_ppm, 0.0) * 1e-3 / _R328_MW_UREA         # mol/L
    hyd = c_urea * R328_AI701_UREA_PHI                          # hydrolysed urea, mol/L
    c_nh3 = max(nh3_ppm, 0.0) * 1e-3 / _R328_MW_NH3 + 2.0 * hyd  # total free NH3, mol/L
    c_co2 = max(co2_ppm, 0.0) * 1e-3 / _R328_MW_CO2 + hyd       # total dissolved CO2, mol/L

    Kb = R328_AI701_KB_NH3
    oh = (-Kb + math.sqrt(Kb * Kb + 4.0 * Kb * c_nh3)) / 2.0    # weak-base quadratic
    hco3 = c_co2                                                # CO2 -> HCO3- in ammoniacal medium
    nh4 = oh + hco3                                             # charge balance NH4+ = OH- + HCO3-

    kappa = (nh4 * R328_AI701_L0_NH4 + oh * R328_AI701_L0_OH
             + hco3 * R328_AI701_L0_HCO3) / 1000.0 * 1e6         # mol/L -> mol/cm3 -> uS/cm
    return kappa


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
STEP_CAP        = 0.25           # s, max physical sub-step.  Was 0.5, which is UNSTABLE: the
                                 # fastest flow loops (FIC-328404 et al., tau_s=5 s pure-gain +
                                 # 1-lag) go non-monotone above a critical step ~0.389 s, so at
                                 # 0.5 a bare settle diverges (op slams to a rail, PV runs away)
                                 # with no disturbance -- FAST mode and any wall-clock stall
                                 # >=0.389 s in SLOW both cross it.  0.25 keeps every loop monotone
                                 # with margin; the pin runs at dt=0.1 so the design anchor is
                                 # untouched.  See Expert_Interrogation_Log CP-1.
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
_H0_GAPS = h0_enthalpy.unsupported_species(MW_COMP)
assert not _H0_GAPS, f"no H0 enthalpy datum for {sorted(_H0_GAPS)}; add it before publishing streams"
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

# ==========================================================================================
#  TUBE BUNDLE + HYDRODYNAMIC FLOODING LIMIT   (audit TD-006, second half)
#
#  Until now the unit had NO tube geometry at all -- every "flood" term above is a THERMAL
#  metaphor for the steam-dilution branch (raw_load < 0), not a hydraulic limit.  A real
#  falling-film stripper has a hard hydrodynamic ceiling: once the rising gas core shears the
#  descending film off the wall, the film thickens, liquid is dragged upward, residence time
#  collapses and stripping stops.  That is a LIQUID-LOAD limit, independent of steam duty.
#
#  Geometry: licensor DDS 322E001 (Uhde UD-AU-322-DZ-0003-003 rev 00, page 3).  The DDS is
#  self-consistent -- its own tabulated surface area confirms the tube count:
#      N·π·d_o·L = 2600 × π × 0.031 × 6.000 = 1519.27 m²   vs line 25 "1519.00"   (+0.018 %)
STRIP_N_TUBES        = 2600     # DDS line 34, number of tubes
STRIP_TUBE_OD_M      = 0.031    # DDS line 36, tube O.D. 31 mm
STRIP_TUBE_WALL_M    = 0.003    # DDS line 36, wall thickness 3.0 mm
STRIP_TUBE_ID_M      = STRIP_TUBE_OD_M - 2.0 * STRIP_TUBE_WALL_M   # 0.025 m == 0.984 inch
STRIP_TUBE_L_EFF_M   = 6.000    # DDS line 35, tube length "6000 mm eff."
STRIP_SURF_DES_M2    = 1519.00  # DDS line 25, exchange surface per exchanger
STRIP_RHO_G_DES      = 10.28    # DDS line 14, tube-side gas density at operating conditions
STRIP_RHO_L_IN_DES   = 989.88   # DDS line 13, tube-side liquid density in
#
#  The limit itself: Brouwer, "How to Solve Stripper Efficiency Issues", UreaKnowHow 2025,
#  citing IFS Proceeding 166 -- "at a temperature of the reactor outlet solution of 183 °C and
#  a pressure of 140 bar, the flooding limit in a 1-inch tube is found to be 145 kg of solution
#  per hour.  In practice, an upper limit of 70 % of this value is applied."
#  Three documents agree and nothing has to be fabricated:
#    * the DDS tube I.D. is 25.0 mm = 0.984 inch, so the 1-inch figure applies WITHOUT scaling;
#    * the DDS effective tube length is 6.000 m, and the same paper states that 6 m effective
#      length is what gives a Stamicarbon CO2 stripper its 80 % design stripping efficiency;
#    * the quoted reference condition (183 °C) is STRIP_FEED207_T_C, this stripper's own feed
#      temperature, and 140 bar is within 3 % of its 144 bar tube side.
STRIP_FLOOD_KGH_TUBE = 145.0    # kg/h of solution per tube at the flooding limit
STRIP_FLOOD_PRACTICE = 0.70     # industry operating cap as a fraction of the limit
#  DESIGN FLOODING FRACTION -- a COMPUTED result, not a tuned constant:
#      280797 / 2600 / 145 = 0.7448,  i.e. 108.0 kg/h per tube, 74.5 % of the limit.
#  Two consequences, both load-bearing:
#    1. the plant-level limit is 145 × 2600 = 377 000 kg/h, so flooding starts at 134 % of design
#       plant load -- the same order as Brouwer's "110 % when new, 120 % at end of life";
#    2. because 0.7448 < 1.0 the flooding term is IDENTICALLY INACTIVE at the design seed.  It is
#       a one-sided constraint that does not bind, so it cannot move a single bit of the pinned
#       design state.  That is the whole bit-exactness argument for this block -- not an anchored
#       ratio, just a constraint the plant genuinely operates below.
STRIP_FLOOD_DES_FRAC = STRIP_FEED_DES_KGH / STRIP_N_TUBES / STRIP_FLOOD_KGH_TUBE   # 0.7448
#  Bottom-temperature signature.  Brouwer: "a sudden temperature increase of the stripper bottom
#  temperature, let's say 3-4 °C in 15 minutes, is a clear indication for reaching the flooding
#  limit".  The rise is capped by the SAME ceiling the existing steam-dilution branch already
#  uses -- strip_flood_gap = reactor overflow T − bottom T = 183 − 172 = 11 °C -- because both
#  describe the same end state: unstripped reactor liquor falling through the tubes untouched.
#  K is then FIXED by Brouwer's own number rather than tuned: at 10 % over the limit,
#      11.0 × (1 − e^(−K·0.10)) = 3.5 °C   ->   K = 3.83.
STRIP_FLOOD_T_K      = 3.83     # bottom-T rise ramp per unit excess over the flooding limit
#  Efficiency penalty -- DERIVED, no constant.  The first cut of this block used a fitted
#  1/(1 + K·x) with K = 1.50 borrowed from STRIP_ETA_KT.  That number is now RETIRED: it was
#  never sourced, and it turned out to be roughly an order of magnitude too aggressive (it gave
#  a 13 % efficiency loss at 10 % over the limit against ~1-3 % from three independent checks).
#  Worse, it DOUBLE-COUNTED: g_T already collapses eta_T on a feed spike through the thermal
#  path, so a large hydraulic knockdown on top of it charged the same excursion twice.
#
#  The replacement needs no new constant at all, because the bottom-temperature signature and
#  the efficiency loss are THE SAME EVENT measured two ways.  The bottom runs hotter precisely
#  because the carbamate decomposition endotherm did NOT happen; the heat that should have been
#  absorbed by dissociation shows up as sensible heat in the liquid instead.  So
#
#      Q_deficit = m_feed · cp · dT_flood                      (heat not absorbed)
#      g_flood   = 1 − Q_deficit / (n_carbamate_CO2 · dH_carb)  (fraction of stripping lost)
#
#  Every term on the right is already sourced: dT_flood is fixed by Brouwer's 3-4 °C signature,
#  cp is STRIP_CP_BOTTOM, and dH_carb is the Frejacques carbamate enthalpy below.  At the design
#  seed dT_flood is exactly 0.0, so g_flood is exactly 1 − 0.0/Q == 1.0 -- the same structural
#  identity as the rest of this block, not a float-ordering trick.
#
#  Cross-checks (all three agree the knockdown at 10 % over the limit is a few percent, not 13):
#    * this energy balance                                        ~2.9 %
#    * Brouwer's Shangdong Hualu Hengsheng case study, where a 3 °C bottom-temperature change
#      accompanied a 79 % -> 81 % efficiency change                ~2.5 %
#    * the licensor length correlation quoted in the same paper (6 m eff. -> 80 % efficiency,
#      8 m eff. -> 82 %) applied to the flooded-length fraction    ~0.8 %
#  The balance is charged against the CARBAMATE endotherm alone rather than the full endotherm
#  sum.  That is both the simpler choice and the conservative one (a smaller denominator gives a
#  LARGER knockdown), and it is what the source describes: flooding destroys the falling film,
#  and it is the falling film that "facilitates the dissociation of liquid ammonium carbamate".
STRIP_FLOOD_ETA_FLOOR = 0.50    # clamp: the hydraulic term alone can never zero the stripper
                                #   (g_T carries the thermal collapse; this is incremental to it)

# ==========================================================================================
#  PER-SPECIES ENTHALPY BALANCE   (audit TD-006, second half)
#
#  What this replaces.  The stripper's MP-steam draw used to be Q = DUTY_DES · (ṁ_feed/ṁ_feed,des),
#  i.e. duty strictly proportional to feed MASS.  That is wrong in a way that matters: it says a
#  stripper fed the same tonnage of pure water and of carbamate-rich reactor liquor needs the same
#  steam.  Composition did not enter at all, so the single largest heat sink in the unit -- the
#  carbamate dissociation endotherm -- was invisible to the steam header.
#
#  Sources.  Frejacques, quoted in Brouwer, "Thermodynamics of the Urea Process", UreaKnowHow
#  Process Paper June 2009, p.12, which gives BOTH reactions at PROCESS conditions rather than at
#  the usual 25 °C standard state:
#      CO2(G) + 2 NH3(G) -> NH2COONH4(L)          dH = -117 kJ/mol at 110 atm and 160 °C
#      NH2COONH4(L) -> NH2CONH2(L) + H2O(L)       dH = +15.5 kJ/mol at 160-180 °C
#  Those conditions are close to this stripper's own (144 bar, 172-183 °C), which is why the
#  process-condition 117 is used here and not the 159-160 kJ/mol figure that is quoted for SOLID
#  carbamate at 1 atm / 25 °C.  The stripper runs reaction 1 BACKWARDS, so +117 kJ per mol of CO2
#  released from the liquid; urea hydrolysis runs reaction 2 backwards, so -15.5 kJ/mol.
STRIP_DH_CARB_JMOL = 117_000.0   # J/mol CO2 liberated from carbamate (endothermic here)
STRIP_DH_HYD_JMOL  = -15_500.0   # J/mol urea hydrolysed -- the LIQUID step (urea + H2O -> carbamate)
#                                  only; the carbamate it produces is decomposed by the term above,
#                                  so counting both is a sum, not a double count.
#  NH3 desorption.  NH3 is SUPERCRITICAL at stripper temperature (Tc = 132.4 °C), so there is no
#  latent heat to look up -- what the duty has to pay is the desorption enthalpy out of the melt.
#  This is NOT a new number: it is the value the loop already uses at the other end of the same
#  circuit (HPCC_BUB_DHVAP_JMOL, the NH3-dominated vaporisation enthalpy fitted to the synthesis
#  bubble point).  It is restated here rather than aliased because HPCC_BUB_DHVAP_JMOL is defined
#  further down the module and this unit's design-point self-call runs BEFORE that line.
#  test_equation_audit_322e001_enthalpy.py asserts the two stay equal so they cannot drift apart.
STRIP_DH_NH3_JMOL  = 23_000.0    # J/mol free NH3 desorbed  (== HPCC_BUB_DHVAP_JMOL)
STRIP_LAM_H2O_JMOL = 36_900.0    # J/mol water vaporised overhead == 2049 kJ/kg (steam tables,
#                                  ~170 °C); the same value HPCC_FLASH_DH already uses for H2O.
STRIP_CP_GAS       = 2.0         # kJ/kg.K mean overhead-gas cp  (== HPCC_CP_GAS, same reason)
#  VALIDATION (scratchpad/probe_td006_enthalpy.py).  Summing these terms over the design streams,
#  with nothing fitted and no free parameter, gives 37 831 kW against the licensor's design duty
#  STRIP_DUTY_DES_KW = 39 400 kW -- 96.0 %.  The 4 % residue is shell/ambient loss, biuret (whose
#  enthalpy is not published and which is 0.667 kmol/h against 88.1 for hydrolysis), and the mean-cp
#  approximation.  That agreement is the corroboration that this constant set is the right one.
#
#  HOW IT IS USED -- and why the pin cannot move.  The licensor duty stays the anchor: only the
#  RATIO of the live balance to the design balance is applied,
#      Q_strip = STRIP_DUTY_DES_KW · (H_live / H_des) · 3600
#  with H_live and H_des produced by the SAME function from the SAME inputs at design, so the
#  ratio is X/X == 1.0 exactly and Q_strip is bit-identical to the old feed-proportional form
#  (which was also exactly 1.0 at design).  The absolute 4 % offset therefore never enters the
#  model -- it cancels in the ratio -- and the design duty remains the PFD value, not a computed one.
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
STRIP_ETA_KT    = 0.15     # eta_T penalty per unit fractional bottom-T deficit (feed-load cooling chokes strip)
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
#                                   (design-point anchor; see urea_soln_cp below -- this stays the
#                                    authoritative value AT the design composition, and the
#                                    correlation carries the departure from it)

# ==============================================================================================
#  AUDIT C10 -- urea-solution properties are NOT constants
#
#  A single cp of 2.5 kJ/kg.K and a set of fixed densities were used everywhere a urea solution
#  appears, from 44 % urea in the LP recirculation to 97.7 % melt leaving Evaporator II.  That is
#  wrong where it matters most: the evaporation train exists precisely to change the composition,
#  so the property is most in error exactly where the model does its most important work.
#
#  Measured error of the single 2.5 constant against the mixing rule below (probe_c10_props.py):
#      44 % urea, 40 C  ->  cp 3.23   constant is 23 % LOW
#      80 % urea, 99 C  ->  cp 2.50   constant is right (this IS the anchor)
#      94 % urea, 130 C ->  cp 2.16   constant is 16 % HIGH
#      98 % urea, 140 C ->  cp 2.08   constant is 20 % HIGH
#
#  cp -- BACK-SOLVED, not guessed (CLAUDE.md §1 allows sourced or back-solved).  Take cp_water
#  from steam tables, require the mass-weighted mixing rule to reproduce the model's own
#  R323_CP_SOLN at the design composition, and read off cp_urea:
#      cp_urea = (2.5 - 0.20 * 4.2183) / 0.80 = 2.0704 kJ/kg.K
#  The published value for molten urea is ~2.0-2.1 kJ/kg.K, so the number that falls out of the
#  back-solve matches the literature independently.  That is the corroboration.
#
#  rho -- REGRESSED FROM THE PFD, which CLAUDE.md §0 makes the strict source and which tabulates
#  urea %, water %, temperature and effective density for every urea-solution stream in the plant
#  (12 streams, 34-98 % urea, 40-183 C; probe_c10_rho.py).  Least squares gives
#      rho = 972.08 + 255.95 * w_urea - 0.4659 * (T - 100)      kg/m3
#  Both signs are physically right -- denser with urea, thinner when hot -- and the fit is its own
#  evidence: it was NOT imposed.  Worst residual 6.2 %, on the two HP synthesis streams (207/208)
#  that carry dissolved NH3/CO2 and so are not urea/water binaries at all.
#
#  BIT-EXACTNESS.  Both functions are used as a DEPARTURE from the existing design anchor, never
#  as an absolute:  prop(w,T) = ANCHOR + [raw(w,T) - raw(w_des,T_des)].  At design the bracket is
#  a literal 0.0 (same function, same inputs), and ANCHOR + 0.0 == ANCHOR bit-exactly in IEEE-754.
#  So every design value the licensor published is preserved to the bit, and only the off-design
#  response changes -- the same structural argument the stripper flooding term uses.
C10_RHO_A        = 972.0821       # kg/m3   PFD regression intercept
C10_RHO_B        = 255.9536       # kg/m3   per unit urea mass fraction
C10_RHO_C        = -0.465942      # kg/m3.K temperature slope
C10_W_DES        = 0.80           # design anchor composition (stream 315/317, ex 323D002)
C10_T_DES        = 99.0           # design anchor temperature (C)


def cp_water_kjkgk(T_C: float) -> float:
    """Saturated-liquid water cp, kJ/kg.K.  Least squares against IAPWS-IF97 at 19 points spanning
    0-212 C, which is the full range this engine's aqueous streams occupy (40 C absorber liquor to
    200 C hydrolyser).  Worst residual 0.0090 kJ/kg.K (0.21 %).

    CUBIC, not quadratic.  cp(T) has a minimum near 35 C and then curves upward increasingly
    steeply -- 4.18 at 40 C but 4.56 at 212 C -- and a quadratic fitted over 20-200 C could not
    hold 0.02 kJ/kg.K at both ends of the wider range (it missed IF97 by 0.021 at 212 C).
    test_water_cp_tracks_if97 pins this against the reference table."""
    return (4.21143048 - 0.0010464288 * T_C
            + 0.000008708461 * T_C * T_C + 0.00000001809921 * T_C ** 3)


# cp of molten urea, BACK-SOLVED rather than hardcoded, so it can never drift out of step with
# cp_water or with the anchor it was derived from: require the mixing rule to reproduce the model's
# own R323_CP_SOLN at the design composition and solve for the urea term.  The result is ~2.072,
# and the published value for molten urea is ~2.0-2.1 -- an independent corroboration, asserted in
# test_equation_audit_c10_props.py so a future edit cannot quietly push it out of the physical band.
CP_UREA_MELT = ((R323_CP_SOLN - (1.0 - C10_W_DES) * cp_water_kjkgk(C10_T_DES)) / C10_W_DES)


def _urea_cp_raw(w_urea: float, T_C: float) -> float:
    # min/max rather than clamp(): this block is defined well above clamp's definition.
    w = min(max(w_urea, 0.0), 1.0)
    return w * CP_UREA_MELT + (1.0 - w) * cp_water_kjkgk(T_C)


def _urea_rho_raw(w_urea: float, T_C: float) -> float:
    w = min(max(w_urea, 0.0), 1.0)
    return C10_RHO_A + C10_RHO_B * w + C10_RHO_C * (T_C - 100.0)


_CP_RAW_DES  = _urea_cp_raw(C10_W_DES, C10_T_DES)
_RHO_RAW_DES = _urea_rho_raw(C10_W_DES, C10_T_DES)


def urea_soln_cp(w_urea: float, T_C: float, anchor: float = R323_CP_SOLN) -> float:
    """Specific heat of a urea solution, kJ/kg.K, as a DEPARTURE from the design anchor.
    Returns `anchor` bit-exactly at the design composition and temperature."""
    return anchor + (_urea_cp_raw(w_urea, T_C) - _CP_RAW_DES)


def urea_soln_rho(w_urea: float, T_C: float, anchor: float) -> float:
    """Density of a urea solution, kg/m3, as a DEPARTURE from the caller's own design anchor.
    Each call site keeps its PFD-published design density and gains the correct slopes around it."""
    return anchor + (_urea_rho_raw(w_urea, T_C) - _RHO_RAW_DES)


# ==============================================================================================
#  AUDIT C10, aqueous half -- water properties from IAPWS, and why that does not violate §0
#
#  §0 makes the PFD the strict source, so departing from its tabulated density needs a reason
#  stronger than "the number looks wrong".  Here is the reason, and it is specific rather than
#  general: the PFD's density row is RIGHT almost everywhere and wrong for exactly two streams.
#
#    * The utility sheet's seven steam condensates, 142-212 C, match IAPWS-IF97 to a mean 0.04 %.
#    * The desorption sheet's OWN pure-water streams match to 0.02 % (742G 88 C, 740 89 C,
#      739 143 C).  So this is not one sheet being sloppy.
#    * Only the "Amm. Water" mixture-model family is off, and only above 150 C: stream 746
#      (190 C) tabulates 908.5 against 876.08, and 747 (200 C) tabulates 897.7 against 864.67
#      -- +3.70 % and +3.82 %.
#
#  Those two are not merely improbable, they are IMPOSSIBLE, and three independent checks say so:
#    1. Compressed liquid explains almost none of it.  At their tabulated pressures the density
#       gain over the saturation line is +0.009 % and +0.018 %, i.e. 0.24 % and 0.47 % of the gap.
#    2. Dissolved solids would need NEGATIVE volume.  Solving 1/rho = (1-ws)/rho_w + ws/rho_app,
#       the water alone already occupies more than the tabulated total volume, giving apparent
#       solute densities of -308 and -12 507 kg/m3.  Even if every solute were as dense as SOLID
#       urea (1335), the maxima are 867.6 and 886.2 -- still below the tabulated values.
#    3. Composition cannot be the variable at all: 743->746 and 749->747 are the same streams
#       heated, at identical composition and identical mass flow, yet the excess grows by +3.06
#       and +3.25 points over ~51 K.
#
#  The artefact is identified.  Solving rho(T2)/rho(T1) = exp(-beta*(T2-T1)) across three
#  independent composition families gives beta = 5.22, 5.57 and 5.74e-4 /K -- water's true
#  expansivity at 60-68 C, i.e. the desorption section's own 56-60 C reference temperature.  Water's
#  actual beta at 190 C is 1.27e-3, more than double.  The licensor's mixture model carried a
#  CONSTANT thermal-expansion coefficient frozen near the section reference; a single beta = 5.5e-4
#  reproduces every high-T entry from its low-T partner to within 0.14 %.  The identical pattern
#  appears in the 1925 MTPD PFD, so it is systematic behaviour, not a transcription slip.
#
#  Crucially, NEITHER impossible value is used as a constant anywhere in this engine (grep: 908.5
#  matches nothing; 897.7 matches only a kmol/h figure).  The 328 anchors are R328_C002_RHO = 933.0
#  at 139 C and R328_C004_RHO = 923.28 at 143 C, which sit +0.64 % and -0.02 % from real water.
#  So the fix never has to anchor on a bad number: §0 is honoured where the PFD is sound, and the
#  DERIVATIVE comes from physics.
WATER_TC_K   = 647.096      # K, critical temperature of ordinary water (IAPWS)
WATER_RHOC   = 322.0        # kg/m3, critical density
#  Wagner & Pruss, J. Phys. Chem. Ref. Data 22 (1993) 783, Eq. 2.6; reproduced as the auxiliary
#  saturated-liquid equation in IAPWS R7-97 §8.1.  Six PUBLISHED coefficients -- nothing is fitted
#  here, so §1 is satisfied without any regression at all.  Verified against an independent IF97
#  implementation: worst deviation 0.0047 % over 0-220 C, 0.043 % out to 250 C.
_WP_B = (1.99274064, 1.09965342, -0.510839303, -1.75493479, -45.5170352, -6.74694450e5)
_WP_E = (1.0 / 3.0, 2.0 / 3.0, 5.0 / 3.0, 16.0 / 3.0, 43.0 / 3.0, 110.0 / 3.0)


def water_rho_sat(T_C: float) -> float:
    """Saturated-liquid density of ordinary water, kg/m3.  Wagner & Pruss (1993) Eq. 2.6."""
    tau = 1.0 - (T_C + 273.15) / WATER_TC_K
    if tau <= 0.0:
        return WATER_RHOC
    return WATER_RHOC * (1.0 + sum(b * tau ** e for b, e in zip(_WP_B, _WP_E)))


def aqueous_rho(anchor: float, T_des_C: float, T_C: float) -> float:
    """Density of an aqueous stream, kg/m3, as a MULTIPLICATIVE departure from its own design
    anchor: the absolute value stays the PFD's (§0), only the temperature slope comes from IAPWS.

    Multiplicative rather than additive because these anchors sit 0-1.3 % above pure water and a
    solution's expansivity tracks water's FRACTIONALLY, not absolutely.  Across the full 44->200 C
    span the two forms differ by at most 1.5 kg/m3, so this is a refinement, not a reversal.

    The parentheses around the ratio are LOAD-BEARING and not cosmetic.  `anchor * (r/r)` returns
    anchor bit-exactly for every operand; `anchor * r / r`, evaluated left to right, does not --
    measured at ~10 % of random operand pairs.  Test test_ratio_must_be_parenthesised guards it.
    """
    return anchor * (water_rho_sat(T_C) / water_rho_sat(T_des_C))


def aqueous_cp(anchor: float, T_des_C: float, T_C: float) -> float:
    """cp of an aqueous stream, kJ/kg.K, as an additive departure from its own design anchor.

    Note that §0 does not bind here at all: the PFD has NO cp row anywhere (its rows are flows,
    molar weight, density, temperature and pressure), so steam tables are the only admissible
    source rather than merely the better one.  Additive rather than multiplicative because these
    anchors are LUMPED values well below pure water (4.0 and 3.0 against water's 4.18-4.49), so
    they carry solute content whose own cp should not be scaled by water's temperature slope.
    """
    return anchor + (cp_water_kjkgk(T_C) - cp_water_kjkgk(T_des_C))

# LP steam header feeding the 323E002 / 323E010 / 324E001 chests.  This MUST be the header the
# engine actually runs, `steam_system.P_LP_BARA` = 5.01325 bar a (4.0 barg, the 322D001A/B LP-drum
# design pressure).  The former 4.4 bar a literal predates that header and left every chest design
# pin below computed against a pressure the live model never sees: the seeded valve strokes then
# admitted OP_DES/100 * 5.01325 instead of the datasheet chest pressure -- 4.494 bar a into 323E002
# against its 3.96 design, i.e. tsat 147.9 C instead of 143.3 C and a 9127 kW duty at the DESIGN SEED
# against the 5858 kW datasheet.  The chest pressures are the physical anchors (equipment DDS), so
# each design STROKE is now derived from them and the live header, not the other way round.
R323_P_STEAM_SUP = steam_system.P_LP_BARA   # bar a, live LP header (4.0 barg == 5.01325 bar a)

# --- Stage 1: Rectifying Column 323C003 + Recirc Heater 323E002 (4.1 bar a, hold 135 C)
R323_FEED_DES_KGH   = STRIP_BOT_DES_KGH        # 130482 kg/h, live = drain_kgh
R323_FEED_DES_T_C   = STRIP_T_DOWN_DES_C       # 119 C, live = TT_323001
R323_C003_P_BARA    = 4.1                       # bar a, rectifier operating pressure
R323_C003_T_SP_C    = 135.0                     # C, bottom-liquid boundary (stream 314)
R323_C003_T313_C    = 121.0                     # C, column-bottom sump liquid (PFD-20 stream 313, TT-323002)
R323_PHI_V305       = 24582.0 / 130582.0        # 0.188249 vapor split -> LPCC (stream 305)
R323_305_T_C        = 119.0                     # C, top vapor to 323E003 LPCC
R323_E002_Q_DES_KW  = 5858.0                    # kW, design heater duty (PDS: Q=5858, A=535)
R323_E002_PCHEST_DES = 3.96                     # bar a, 323E002 shell-side design steam (DDS N1:
                                                #   9850 kg/h sat. LP at 3.9 bar a / 145 C)
R323_E002_OP_DES    = R323_E002_PCHEST_DES / R323_P_STEAM_SUP * 100.0   # 78.99 %, PV-329202 design stroke
R323_C003_M_TAU_S   = 120.0                     # s, liquid residence -> holdup sizing
R323_C003_LVL_SP    = 60.0                      # %, LIC-323501 level setpoint
R323_LV501_OP_DES   = 50.0                      # %, LV-323501 design stroke
# Dynamic PT-323201 pressure response. The pure target helper separates prompt flash gas from
# LV-322501 (`drain_kgh`) from the remaining live overhead/reboiler load (`m_305`), consumes the
# beginning-of-substep 323E003/323D001 pressure, and closes exactly at the PFD design point.
# The 1 s constant is the GAS-SPACE pressure capacitance only (vapour compressibility of the small
# overhead volume, consistent with the 1-3 s steam-header lag deduced in References/scenarios).
# It is deliberately NOT reused as the liquid thermal lag; that path uses R323_C003_M_TAU_S.
R323_C003_P_TAU_S = 1.0

# --- Stage 2: Flash Tank 323F004 (adiabatic flash 4.1 -> 1.13 bar a, -> 106 C)
R323_F004_P_BARA    = 1.13                      # bar a, flash pressure
R323_F004_T_SP_C    = 106.0                     # C, flash-liquid boundary (stream 319)
R323_PHI_V701       = 4430.0 / 106000.0         # 0.041792 flash-vapor split (stream 701)
R323_F004_M_TAU_S   = 180.0                     # s, liquid residence
R323_F004_LVL_SP    = 60.0                      # %
R323_LV505_OP_DES   = 50.0                      # %, LV-323505 design stroke
# Dynamic flash pressure 323F004 (hydraulic coupling to LV-323501 via bottom-drain / flash-vapour 701).
#   Opening LV-323501 (m_314 up) raises flash-vapour m_701 into the LP node read by PIC-323203:
#     P_tgt = P_des + K_P * (m_701 - m_701,des) / m_701,des      [bar a]
#     dP/dt = (P_tgt - P) / tau_P
#   Seed-exact: at design m_701 == R323_M701_DES => P_tgt == R323_F004_P_BARA => dP/dt == 0 (pin invariant).
R323_F004_P_GAIN    = 0.45                      # bar a per unit fractional flash-vapour excess
R323_F004_P_TAU_S   = 90.0                      # s, flash-drum pressure relaxation

# --- Stage 3: Pre-evaporator 323E010 + Separator 323F010 (vacuum 0.46 bar a, hold 99 C)
#  AUDIT F-11 (CLOSED): this stage takes TWO feeds, not one.  Stream 319 (323F004 liquid) is joined
#  by stream 331 -- the urea-recovery return from the granulation scrubber -- and the combined
#  solution is heated by LP steam on the 323E010 shell side before flashing in 323F010 under vacuum:
#      319 + 331  ->  323E010  ->  323F010  ->  vapour 790 + liquid 315   (315 == 317 after the pump)
#  With 331 missing, the PFD's stream-317 composition was simply unreachable from 319 by
#  evaporation, and ~1.4 t/h of urea had to appear from nowhere across the stage.  With it, the
#  total mass balance closes to 20 kg/h in 105 t/h (0.019 %) on the licensor's own tabulated flows,
#  and the formaldehyde tracer settles it beyond doubt: 331 carries 7.5 kg/h HCHO in, stream 315
#  carries 7.4 kg/h out, and 331 is the ONLY source of formaldehyde anywhere in the train.
R323_F010_P_BARA    = 0.46                      # bar a, FIXED vacuum boundary (Ejector I 324F002)
R323_F010_T_SP_C    = 99.0                      # C, product boundary (stream 315/317, 80% urea)
R323_M331_DES       = 3270.0                    # kg/h, PFD stream 331 (44.37 % urea, 55 % water)
R323_M331_T_C       = 40.0                      # C,    PFD stream 331 -- a COLD side feed
R323_PHI_VEVAP      = 8750.0 / 101570.0         # 0.086147 water boiled off stream 319 itself
R323_EVAP_LAMBDA    = 2280.0                    # kJ/kg, water latent @ 0.46 bar a
R323_E010_PCHEST_DES = 1.76                     # bar a, 323E010 shell-side design steam (tsat 116.1 C
                                                #   against the 99 C / 0.46 bar a pre-evaporator boil)
R323_E010_OP_DES    = R323_E010_PCHEST_DES / R323_P_STEAM_SUP * 100.0   # 35.11 %, PV-329208 design stroke
R323_F010_M_TAU_S   = 240.0                     # s, liquid residence
R323_F010_LVL_SP    = 60.0                      # %

# --- Stage 4: Urea Solution Tank 323D002 (atmospheric, two-compartment buffer)
R323_D002_VOL_I_M3  = 80.0                      # m3, Compartment I (active flow-through)
R323_D002_VOL_II_M3 = 300.0                     # m3, Compartment II (passive buffer)
R323_D002_RHO       = 1151.0                    # kg/m3, PFD stream 315/317 effective density (80 % urea, 99 C)
# LIC-323507 sits LOW on purpose.  At 80 % urea and 99 C the protective ammonia has already been
# flashed off, so 2 Urea -> Biuret + NH3 runs in the tank; the licensor sizes Comp I so the ACTIVE
# residence stays under ~6 min (10 % of 80 m3 = 8 m3 against an 80.6 m3/h feed).  Holding it at a
# comfortable mid-range level instead would multiply the biuret exposure several-fold, which is the
# whole reason the vessel is compartmented at all.  Source: References/323D002.md §3.2.
R323_D002_LVL_SP    = 10.0                      # %, LIC-323507 (Compartment I) setpoint
R323_FV401_OP_DES   = 50.0                      # %, FV-324401 design stroke

# --- Derived design flows (kg/h) from the split fractions on the design feed ---
R323_M305_DES  = R323_PHI_V305  * R323_FEED_DES_KGH                       # top vapor -> LPCC
R323_M314_DES  = (1.0 - R323_PHI_V305) * R323_FEED_DES_KGH                # rectifier bottom -> flash
R323_M701_DES  = R323_PHI_V701  * R323_M314_DES                           # flash vapor -> LPCC
R323_M319_DES  = (1.0 - R323_PHI_V701) * R323_M314_DES                    # flash liquid -> pre-evap
# Total vapour to the vacuum system (PFD stream 790) = the water boiled off 319 PLUS everything
# stream 331 brings in that does not leave in the product.  Written as a SUM so that R323_M317_DES
# below keeps the exact bits it had before F-11 -- unit 324 hangs off it and must not move.
#   in  101 570 + 3 270 = 104 840      out  92 820 + 12 020 = 104 840      (PFD 790 tabulates 12 040)
R323_MEVAP_DES = R323_PHI_VEVAP * R323_M319_DES + R323_M331_DES           # vapour 790 -> vacuum
R323_M317_DES  = (1.0 - R323_PHI_VEVAP) * R323_M319_DES                   # product -> tank
# 323F010 vacuum is a LIVE state (PT-323204) driven by two hand valves — HV-323605 (gas outlet 790,
# HIC-323605) and HV-329605 (324F002 ejector motive).  Mapping rule: opening either drops the
# pressure.  No controller on this node, so stability comes from the ejector's suction-pressure
# capacity roll-off (pull ∝ P/P_des); anchored so m_evap == pull == R323_MEVAP_DES at design.
R323_HIC605_DES_PCT = 50.0        # % HIC-323605 design opening (HV-323605 gas-outlet hand valve, stream 790)
R323_F010_P_KP      = 0.02        # bar a per (kg/s) net vapour imbalance -> 323F010 vacuum ODE
R323_M324_DES  = R323_M317_DES                                           # tank throughput -> Unit 324

# --- Derived latent / duty terms (force dT/dt = 0 at each design fixed point) ---
# Stage 1 energy balance: mdot_feed*cp*(T_strip_bot - T_flash_sat) + Q_E002 - mdot_305*lambda_305 = 0
R323_Q305_DES_KW  = (R323_FEED_DES_KGH/3600.0*R323_CP_SOLN*(STRIP_T_BOTTOM_DES_C - STRIP_T_DOWN_DES_C)
                     + R323_E002_Q_DES_KW)                            # kW available to boil 305
R323_LAMBDA_305 = R323_Q305_DES_KW / (R323_M305_DES/3600.0)          # kJ/kg (~645.6)
R323_E002_UA_KW = R323_E002_Q_DES_KW / (tsat_steam(R323_E002_PCHEST_DES) - R323_C003_T_SP_C)  # kW/K
# Stage 2 adiabatic flash: mdot_314*cp*(135-106) - mdot_701*lambda_701 = 0
R323_LAMBDA_701 = (R323_M314_DES/3600.0*R323_CP_SOLN*(R323_C003_T_SP_C - R323_F004_T_SP_C)) \
                  / (R323_M701_DES/3600.0)                                 # kJ/kg (~1734.8)
# Stage 3 energy balance (F-11: TWO feeds):
#   mdot_319*cp*(106-99) + mdot_331*cp*(40-99) + Q_E010 - mdot_evap*lambda_evap = 0
# Stream 331 arrives at 40 C against a 99 C product, so it is a heat SINK: the pre-evaporator has to
# pay to bring it up to boiling as well as to evaporate the extra water it carries.
R323_E010_Q_DES_KW = (R323_MEVAP_DES/3600.0*R323_EVAP_LAMBDA
                      - R323_M319_DES/3600.0*R323_CP_SOLN*(R323_F004_T_SP_C - R323_F010_T_SP_C)
                      - R323_M331_DES/3600.0*R323_CP_SOLN*(R323_M331_T_C - R323_F010_T_SP_C))  # kW (~7253)
R323_E010_UA_KW = R323_E010_Q_DES_KW / (tsat_steam(R323_E010_PCHEST_DES) - R323_F010_T_SP_C)  # kW/K

# --- AUDIT F-1/F-2/F-3: design LATENT duties, so vapour generation is energy-limited ----------
# Every vapour rate above was a frozen split fraction of the live INFLOW, i.e. the total-mass
# balance (C1) and the energy balance (C3) were solved independently.  Shutting PV-329202 drove
# Q_E002 -> 0 while the column still boiled the full design overhead, and the whole deficit was
# dumped into the temperature ODE (non-physical: no heat, no boil-up).  The three constants below
# are each the SAME expression, in the SAME float operation order, as the corresponding runtime
# `q_avail` term, so at the design seed the ratio q_avail/Q_DES is exactly 1.0 and the duty limit
# reproduces the design vapour BIT-EXACT (the min() ties on two identical values).
#   Stage 1  m_feed·cp·(T_strip_bot − T_flash_sat) + Q_E002  == m_305·λ_305   (== R323_LAMBDA_305 back-solve)
#   Stage 2  m_314·cp·(135 − 106)               == m_701·λ_701       (adiabatic: no Q term)
#   Stage 3  m_319·cp·(106 − 99) + m_331·cp·(40 − 99) + Q_E010  == m_evap·λ_evap
R323_Q305_DES_KW  = (R323_FEED_DES_KGH/3600.0*R323_CP_SOLN*(STRIP_T_BOTTOM_DES_C - STRIP_T_DOWN_DES_C)
                     + R323_E002_Q_DES_KW)                            # kW available to boil 305
R323_Q701_DES_KW  = (R323_M314_DES/3600.0*R323_CP_SOLN
                     * (R323_C003_T_SP_C - R323_F004_T_SP_C))         # kW released by the 4.1->1.13 letdown
R323_QEVAP_DES_KW = (R323_M319_DES/3600.0*R323_CP_SOLN*(R323_F004_T_SP_C - R323_F010_T_SP_C)
                     + R323_M331_DES/3600.0*R323_CP_SOLN*(R323_M331_T_C - R323_F010_T_SP_C)
                     + R323_E010_Q_DES_KW)                            # kW available to evaporate
# 323F004 isenthalpic-flash saturation anchor.  T and P of a flashing drum are NOT independent:
# the liquid sits at its bubble point.  The boiling-point elevation of the urea liquor is held at
# its design value (same frozen-activity assumption `conc_infer_324` makes), so the live flash
# temperature rides the water saturation curve offset by the plant's own design anchor:
#     T_flash = 106 + [ Tsat(P_live) − Tsat(1.13) ]        -> exactly 106.0 at design (offset ≡ 0)
_R323_TSAT_F004_DES = tsat_steam(R323_F004_P_BARA)                    # °C, design flash-drum Tsat
# TD-014: 323C003 needs the same anchor.  Its bottoms sit ~9.8 °C BELOW water's saturation
# temperature at 4.1 bar a because the vapour it is in equilibrium with is 33 % NH3 / 50 % CO2, not
# steam -- so the offset is a depression, not an elevation, and Raoult-on-water cannot produce it.
# Held at its design value (the same frozen-activity assumption 323F004 already makes) and carried
# on the live water saturation slope.
_R323_TSAT_C003_DES = tsat_steam(R323_C003_P_BARA)                    # °C, design column-bottom Tsat
# --- 323C003 gas-source design rates, for the PT-323201 two-path pressure coupling ---
# The column is charged by TWO physically distinct carbamate-gas streams, tabulated
# separately on the PFD:  stream 301, the prompt flash released across LV-322501, and
# stream 302, the gas evolved in the 323E002 rectifying heater.  Their design rates are the
# design overhead apportioned by the duty that raises each one, so they sum to R323_M305_DES
# exactly and the design ratios below are both exactly 1.0.
_R323_Q_FLASH_DES_KW = (R323_FEED_DES_KGH / 3600.0 * R323_CP_SOLN
                        * (STRIP_T_BOTTOM_DES_C - STRIP_T_DOWN_DES_C))   # kW, letdown flash
R323_M_FLASH_GAS_DES_KGH = R323_M305_DES * (_R323_Q_FLASH_DES_KW / R323_Q305_DES_KW)
R323_M_POOL_VAP_DES_KGH  = R323_M305_DES * (R323_E002_Q_DES_KW / R323_Q305_DES_KW)

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
# TD-013: with the field tie-in spool OPEN the two compartments are connected vessels, so they hold
# one pooled inventory at one common level.  Equal HEIGHT, not equal mass -- they share the tank
# shell, so an equal level FRACTION is an equal head, and the pooled span is simply the sum.
R323_D002_M_TIE_FULL = R323_D002_M_I_FULL + R323_D002_M_II_FULL

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
#  Whole-network design closure follows the PFD-20/21/22 stream table (CLAUDE.md §0):
#    328D003 Comp I : in 719+720+721+759 = 31479; out 744 = 31478 (1 kg/h table rounding)
#    Comp II        : in 343 = 34180; out 735+791+734+793 = 34182 (2 kg/h table rounding)
#    322C001        : in 744+GCB+CPL = vent + 756(33358)
#    323C005        : in 756+702+708 = 343(34180)+341(80), exact
#    323E003        : in 305+718B+776+797 = 321(1323)+308
#    323E011        : in 701+786+321+791 = 7563 = 718(7123)+702(440), exact
#    323D011        : in 718+734 = split 718A+718B plus the 734 wash contribution
#    328C002        : in 738+748+750+775(40434) = 737(6665)+743(33769)
#    328C003        : in 746+911(34874)         = 748(812)+747(34062)
#    328C004        : in 749+931(40557)         = 750(6833)+739(33724)
#    328D001        : in 737(6665)+718A(3561.5) = 786(276)+775(1675)+776(8275.5)
# ==========================================================================
R3232_CP = 3.0     # kJ/kg·K  LP-carbamate / condensate train (323E003, 323E011).
# UN-SOURCED on purpose (reconciled 2026-07-24 vs References/Ammonium Carbamate Heat Capacity Data.md):
# no single valid equation for the reactive aqueous fluid -- the rigorous cp is a full e-NRTL/UNIQUAC
# electrolyte package (ion cp tabulated only at 298 K), the one closed form (Chauhan cubic) is the pure
# molten salt (~2.08 @90 C), and the real governing property is the reaction-shifted APPARENT cp that no
# constant can carry.  Reference frozen band for the SOLUTION is 3.2-3.8 (Stamicarbon lean-NH3 ~3.2 low
# end); 3.0 is above pure-salt ~2.1 and ~6% below that floor -- a defensible lean-liquor value.  aqueous_cp
# is WRONG here (carbamate ion cp < 0, electrostriction).  LOCKED: back-solved lambdas + C10 test use 3.0.
R328_CP  = 4.0     # kJ/kg·K  desorber / hydrolyser aqueous train (328C002/003/004)
A328_CP  = 4.0     # kJ/kg·K  LP absorber 322C001 aqueous liquor

# AUDIT C4 / gap G5 — explicit Unit-328 carbamate-desorption enthalpy for the energy-closure ledger.
# The C4 diagnostic residual is the net NH3-CO2 (carbamate) desorption enthalpy the reboiler steam
# supplies to strip the columns, previously buried in the back-solved boil-up/condensation latents
# instead of an explicit xi*dH term (see the derivation at the diagnostic itself). Its design
# magnitude is CAPTURED from the design seed (the first tick from a fresh design State) so the ledger
# closes bit-exact at design regardless of any small IAPWS-IF97 saturation shift, and off-design it
# scales with the live MP+LP reboiler steam that drives desorption (anchored-ratio form, the same
# idiom as gen748/gen750). Read-only: it enters ONLY the published Q328 residual, never a state ODE,
# so no pinned dynamic balance changes. Corroboration: the ~100 kJ/mol heat of CO2-NH3 desorption
# over the ~39.5 kmol/h CO2 the C4 comment identifies is ~1.1-1.4 MW for CO2 alone, consistent with
# the captured magnitude once the associated NH3 desorption is added. The reaction enthalpy is that
# of the aqueous NH3-CO2 speciation network now available off-25 C in props_nh3co2h2o.py (gap G1).
_A328_Q_REACT_DES_KW = None    # captured on the first (design) tick; see the 328 energy diagnostic

# ---- boundary (fixed) feed streams  (kg/h @ °C) ----
R3232_M797_DES = 1758.0 ; R3232_M797_T = 46.0     # inert-laden recycle -> 323E003
R3232_M702_DES = 440.0  ; R3232_M702_T = 45.0     # flash recycle       -> 323E011
A328_CPL_DES   = 1750.0 ; A328_CPL_T   = 46.0     # process condensate 954 -> 322C001 (PFD 1750 kg/h @46 C)
A328_D003_M719 = 26768.0; A328_D003_M719_T = 45.0 # 719 -> 328D003 Comp I
A328_D003_M720 = 2758.0 ; A328_D003_M720_T = 40.0 # 720 -> 328D003 Comp I
A328_D003_M721 = 1763.0 ; A328_D003_M721_T = 41.0 # 721 -> 328D003 Comp I
# AUDIT B10 — 324E007 condensate.  Confirmed from the P&ID ("Condensed gases in bottom of shell side
# of 324E007 is discharged to 328D003") and by the 324E007 closure 717 (221) = 759 (190) + 722 (31).
A328_D003_M759 = 190.0  ; A328_D003_M759_T = 55.0 # 759 -> 328D003 Comp I (PFD-21, hottest of the four)

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
R328_C002_T_BOT_BOT = 139.0 ; R328_C002_T_BOT_TOP = 117.0
R328_C002_T_BOT738 = 114.0 ; R328_C002_T_BOT748 = 188.0 ; R328_C002_T_BOT750 = 140.0
R328_D001_T = 61.0                                          # 775 reflux temperature (from 328D001)
# Holdup: see the F-8 geometry block below -- R328_C002_M_DES is set there from the datasheet.
R328_C002_LAM748 = 2000.0 ; R328_C002_LAM750 = 2100.0       # kJ/kg condensation of recycle OVHDs
# sensible net onto the 139°C bottoms (kW), then λ737 closes M·cp·dT/dt = 0:
R328_C002_SENS = ((R328_C002_M738_DES*(R328_C002_T_BOT738 - R328_C002_T_BOT_BOT)
                   + R328_C002_M775_DES*(R328_D001_T   - R328_C002_T_BOT_BOT)
                   + R328_C002_M748_DES*(R328_C002_T_BOT748 - R328_C002_T_BOT_BOT)
                   + R328_C002_M750_DES*(R328_C002_T_BOT750 - R328_C002_T_BOT_BOT))
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
R328_C003_M911_DES = 1105.0                                 # MP-steam strip (FIC-329402)
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
R328_C004_M931_DES = 6495.0                                 # LP-steam strip (FIC-329401)
R328_C004_M931_DH  = 2136.0                                 # kJ/kg LP-steam enthalpy drop
R328_C004_IN_DES   = R328_C004_M749_DES + R328_C004_M931_DES             # 40557
R328_C004_PHI750   = 6833.0 / 40557.0                       # OVHD split -> 328C002 (750)
R328_C004_M750_DES = R328_C004_PHI750 * R328_C004_IN_DES    # 6833
R328_C004_M739_DES = R328_C004_IN_DES - R328_C004_M750_DES  # 33724 bottoms -> 328E007 -> boundary
R328_C004_T = 143.0 ; R328_C004_T749 = 148.0
R328_C004_DT_DES = R328_C004_T - R328_C002_T_BOT750             # 3 C bottom (143) - top tray (140 = OVHD 750), TT-328004
# Holdup: see the F-8 geometry block below -- R328_C004_M_DES is set there from the datasheet.
R328_C004_LAM750 = ((R328_C004_M749_DES/3600.0*R328_CP*(R328_C004_T749 - R328_C004_T)
                     + R328_C004_M931_DES/3600.0*R328_C004_M931_DH)
                    / (R328_C004_M750_DES/3600.0))                        # kJ/kg (~2130)
# FFIC-329401 master ratio is defined further down, after R3232_E003_M744_DES: its feed
# measurement is the FIC-328402 wash leg (PFD stream 744, 323E003 -> 328D003 Comp-II), not a
# 328C002 term,
# so the denominator must exist first.  See the RHO_744_KGM3 block.

# ==========================================================================
#  AUDIT F-8 -- desorber GEOMETRY from the licensor mechanical datasheet
#  Uhde UD-AU-328-EC-0001 rev 01, "Desorption Column I / II", pages 2-3 (DDS),
#  6 (principle sketch), 7 (tray arrangement), 9 (section X-X), 10 (tray detail).
#
#  The drawing settles a structural question the PFD alone cannot: 328C002 and
#  328C004 are ONE 25.5 m tower, C002 stacked on top of C004 on a common skirt,
#  each with its own sump.  Stamicarbon's own description agrees -- it calls them
#  the "top part" and "bottom part" of the desorber, with the hydrolyser between
#  them and the bottom part's off-gas used as the top part's stripping agent
#  (van der Zande, "Zero waste urea production", Nitrogen+Syngas 2019).  That is
#  exactly streams 750 -> 328C002 and 748 -> 328C002 in the PFD.
#
#  Holdup was previously a 900 s residence-time GUESS (8442 / 8431 kg).  The
#  datasheet replaces the guess with geometry: tray inventory over the executed
#  tray count plus the sump at its drawn normal liquid level.  The result is ~5x
#  smaller, i.e. the real columns respond ~5x faster than the model did.
#  Level is defined as M / M_DES * 50, so the design point is untouched (50 % at
#  the seed either way) -- only the transient speed changes.
# ==========================================================================
R328_COL_ID      = 1.250                      # m,  shell inside diameter, both sections (DDS line 27)
R328_COL_AREA    = math.pi / 4.0 * R328_COL_ID ** 2                     # 1.2272 m2
R328_TRAY_DC_W   = 0.202                      # m,  downcomer chord width off the wall (section X-X)
_r328_R          = R328_COL_ID / 2.0
_r328_seg        = (_r328_R ** 2 * math.acos((_r328_R - R328_TRAY_DC_W) / _r328_R)
                    - (_r328_R - R328_TRAY_DC_W)
                    * math.sqrt(2.0 * _r328_R * R328_TRAY_DC_W - R328_TRAY_DC_W ** 2))
R328_TRAY_ACTIVE = R328_COL_AREA - 2.0 * _r328_seg                      # 0.9700 m2 bubbling area
R328_TRAY_NHOLE  = 3125                       # holes per tray, dia 6 mm, equally spaced (section X-X)
R328_TRAY_DHOLE  = 0.006                      # m
R328_TRAY_AHOLE  = R328_TRAY_NHOLE * math.pi / 4.0 * R328_TRAY_DHOLE ** 2   # 0.0884 m2 (9.1 % of active)
R328_TRAY_HWEIR  = 0.040                      # m,  outlet weir height (section C-C)
R328_FROTH_PHI   = 0.5                        # clear-liquid height / weir height on an aerated tray
R328_C002_NTRAY  = 15                         # executed trays, 328C002 (DDS line 35)
R328_C004_NTRAY  = 22                         # executed trays, 328C004 (DDS line 35)
R328_C002_H_NLL  = 1.150                      # m,  sump normal liquid level above T.L. (tray arrangement)
R328_C004_H_NLL  = 0.920                      # m
# Densities: the PFD rules (CLAUDE.md §0).  Its stream-739 "Density eff." 923.28 kg/m3 @ 143 C and
# the datasheet's 923.25 @ 143 C agree to 3e-5 relative -- two independent licensor documents on the
# same number, and both are simply water at 143 C, which is what a <1 ppm purified condensate is.
# For 328C002 the two differ (PFD 743 = 933.0 @ 139 C, datasheet = 944.0 @ 138 C); the datasheet
# figure is the conservative MECHANICAL design value used for weights and hydrostatic head, so the
# process model takes the PFD's.
R328_C002_RHO    = 933.0                      # kg/m3, PFD stream 743 @ 139 C
R328_C004_RHO    = 923.28                     # kg/m3, PFD stream 739 @ 143 C


def _r328_holdup(ntray: int, h_nll: float, rho: float) -> float:
    """Design liquid inventory of a desorber section = aerated tray holdup + sump at NLL (kg)."""
    return (ntray * R328_TRAY_ACTIVE * R328_TRAY_HWEIR * R328_FROTH_PHI
            + R328_COL_AREA * h_nll) * rho


R328_C002_M_DES = _r328_holdup(R328_C002_NTRAY, R328_C002_H_NLL, R328_C002_RHO)   # ~1588 kg (was 8442)
R328_C004_M_DES = _r328_holdup(R328_C004_NTRAY, R328_C004_H_NLL, R328_C004_RHO)   # ~1436 kg (was 8431)

# ==========================================================================
#  323E011 + 323D011  (LP carbamate condenser + drum, 45 °C, 1.13 bar a)
#  Inlets are PFD-21/22 streams 701+786+321+791.  Outputs are liquid 718 to
#  323D011 and gas 702 to 323C005.  Stream 734 is a separate 328D003 Comp-II
#  wash branch into 323D011; it is not an E011 inlet.  The PFD closes E011 at
#  7563 = 7123 + 440 kg/h exactly and supersedes the old vendor process case.
# ==========================================================================
R3232_E011_M701_DES = R323_M701_DES                         # 4426.6 flash vapour ex 323F004 (PFD 701 4430)
R3232_E011_M786_DES = 276.0                                 # vent from 328D001 (stream 786)
R3232_E011_M321_DES = R3232_M797_DES*0.0 + 1323.0           # 323E003 vent (stream 321)
R3232_E011_M402_DES = 1534.0                                # PFD-21/22 stream 791 Amm. Water 56 C / 4.1 bar,
#   328D003 Comp-II wash (FIC-323402).  Was 2931 (an unsourced coded constant back-fitted to the
#   3100/9400 condenser datasheet); PFD-ruled to 1534 kg/h.
# PFD-21/22 stream 791 design volumetric flow (m3/h) = 1534/992.4 = 1.546 -> tabulated 1.5.
# Read-only UI anchor for FIC-323402: vol = 1.5 * (m_402 / M402_DES), bit-exact 1.5 at design.
S791_VOL_DES = 1.5
R3232_E011_IN_DES   = 7563.0                               # PFD: 701+786+321+791, reconciled rounded total
R3232_E011_RECON_KGH = (R3232_E011_IN_DES -
                        (R3232_E011_M701_DES + R3232_E011_M786_DES
                         + R3232_E011_M321_DES + R3232_E011_M402_DES))
R3232_E011_M401_DES = 1534.0                                # PFD-21/22 stream 734 Amm. Water 56 C / 4.1 bar,
#   328D003 Comp-II flush (FIC-323401) -> 323D011.  Was 823 (back-fitted residual); the PFD splits the
#   Comp-II discharge header 343/733 (34180) into 735(31114) + 791(1534) + 734(1534), so 734 is
#   this leg and 343 now closes on the PFD (34182 vs tabulated 34180 = table rounding; molar 1850.65
#   vs 1850.64 closes exactly).
R3232_D011_M718_DES = 7123.0                                # PFD-21/22 stream 718 Carb. Liq. 45 C, 6.7 m3/h
# The supplied mapping identifies 702 as the 323D011 gas outlet.  On the PFD basis,
# 701+786+321+791 = 7563 = 718(7123)+702(440) kg/h exactly.  Stream 734 is a separate
# 328D003 branch and does not enter this node.
R3232_E011_MV_DES   = 440.0                                 # PFD stream 702 -> 323C005
R3232_E011_PHIV     = R3232_E011_MV_DES / R3232_E011_IN_DES
R3232_E011_MCOND_DES = (R3232_E011_IN_DES - R3232_E011_M402_DES
                        - R3232_E011_MV_DES)                 # gas condensed/absorbed in 323E011
R3232_M718A_DES = 0.5 * R3232_D011_M718_DES                 # 3561.5 -> 328D001 (PFD 718A 3562 ✓)
R3232_M718B_DES = 0.5 * R3232_D011_M718_DES                 # 3561.5 -> 323E003 (PFD 718B 3562 ✓)
R3232_E011_T = 45.0 ; R3232_E011_T701 = 106.0 ; R3232_E011_T786 = 61.0
R3232_E011_P_BARA = 1.13 ; R3232_E011_P_KP = 0.05
R3232_E011_PV_OP_DES = 25.0                                 # PIC-323203 vent stroke
R3232_D011_M_TAU_S = 600.0
R3232_D011_M_DES   = R3232_D011_M718_DES/3600.0 * R3232_D011_M_TAU_S      # 1187.2 kg
R3232_D011_LVL_SP  = 50.0                        # LT-323503 design level (%): OEM "maintains the
#   flash tank condenser level tank at 50% capacity" (328E021 328E007 328P003 328P006.md:359).
R3232_LV503_OP_DES  = 50.0                       # LV-323503 stroke, 323P008 common discharge header
R3232_FIC405_OP_DES = 0.0                        # FV-328405 stroke — the loop is stream 793, a
#   normally-closed Comp-I header spare (PFD 0 kg/h), so it sits shut at design.  It is NOT the
#   718A leg: 718A is the LIC-323503 total draw minus the FIC-323418 718B leg, an unmetered
#   remainder, and driving it from a second integrator made the D011 level loop ring.
R3232_FIC418_OP_DES = 50.0                       # FV-323418 stroke, 718B leg -> 323E003
R3232_M718A_TAU_S   = 45.0                       # 718A leg transport lag (was the FIC-328405 lag)
R3232_E011_Q_DES_KW = 3440.0                                # datasheet condenser duty
R3232_E011_UA_KW    = R3232_E011_Q_DES_KW / (R3232_E011_T - 35.0)         # kW/K vs 35°C CW
# λ_v011 (vapour-generation latent) closes the drum energy balance at 45°C:
R3232_E011_SENS = (((R3232_E011_M701_DES + R3232_E011_RECON_KGH)*(R3232_E011_T701 - R3232_E011_T)
                    + R3232_E011_M786_DES*(R3232_E011_T786 - R3232_E011_T)
                    + R3232_E011_M321_DES*(74.0          - R3232_E011_T)
                    + R3232_E011_M402_DES*(56.0          - R3232_E011_T))
                   / 3600.0 * R3232_CP)                                   # kW
R3232_E011_LAMV = ((R3232_E011_Q_DES_KW - R3232_E011_SENS)
                   / (R3232_E011_MCOND_DES/3600.0))                       # kJ/kg condensed gas

# ==========================================================================
#  328D001  Desorber-I reflux drum (61 °C, 2.6 bar a); 328E004 condenses 737
# ==========================================================================
R328_D001_M737_DES  = R328_C002_M737_DES                    # 6665 OVHD vapour in
R328_D001_M718A_DES = R3232_M718A_DES                       # 3561.5 recycle in (PFD 718A 3562 ✓)
R328_D001_IN_DES    = R328_D001_M737_DES + R328_D001_M718A_DES
R328_D001_M786_DES  = 276.0                                 # vent -> 323E011
R328_D001_M775_DES  = R328_C002_M775_DES                    # 1675 reflux -> 328C002 (FIC-328404)
# PFD-22 stream 775 (328D001 carbamate-liquid reflux -> 328C002) design volumetric flow (m3/h).
# Read-only UI anchor for FIC-328404: vol = 1.5 * (m_775 / M775_DES), bit-exact 1.5 at design
# (PFD mass 1675 kg/h / rho 1095 = 1.53 -> tabulated 1.5).  Physics mass balance (m_775) UNTOUCHED.
S775_VOL_DES = 1.5
R328_D001_M776_DES  = R328_D001_IN_DES - R328_D001_M786_DES - R328_D001_M775_DES  # 8275.5 -> 323E003 (PFD 776 8275 ✓)
R328_D001_M776_RHO  = 1095.0    # kg/m3, stream 776 eff. density @61 C (Combined_1750 tbl, col 776) -> FT-328401 m3/h (8275.5/1095=7.56 -> PFD 7.6)
R328_D001_M774_DES  = R328_D001_M775_DES + R328_D001_M776_DES             # 9950.5 (PFD 774 9950 ✓)
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
# 328E004 cooling-water side.  Strict-source PFD (Combined_1750, cooling-water block) + Mapping of
# cooling water.md: 328E004 CW SUPPLY = stream 1028 (30 C), CW RETURN = stream 1029 (38 C), 408 t/h.
# TIC-328002 controls the opening of TV-328002 (on the CW RETURN line, nozzle N6) = the CW FLOW.
# TT-329007 reads stream 1029 (the CW return temp): with the process condensation load roughly fixed,
# the return temp is INVERSE in the CW flow -> opening TV-328002 (more flow) COOLS the return, closing
# it heats the return:  T_cw_out = T_in + ΔT_des·(op_des/op), = 38 C at the design 50 % opening.
R328_E004_CW_T_IN_C     = 30.0                              # CW supply (stream 1028) inlet temp, C
R328_E004_CW_T_OUT_DES_C = 38.0                             # CW return (stream 1029) outlet temp at design, C
R328_E004_CW_T_MAX_C     = 110.0                            # display clamp: CW flashes near this at the 2.2 bar a return
# λ737_cond (condensation latent) closes drum energy balance at 61°C:
R328_D001_SENS = ((R328_D001_M737_DES*(R328_C002_T_BOT_TOP - R328_D001_T)
                   + R328_D001_M718A_DES*(R328_D001_T718A - R328_D001_T))
                  / 3600.0 * R328_CP)                                     # kW
R328_D001_LAM737 = ((R328_E004_Q_DES_KW - R328_D001_SENS)
                    / (R328_D001_M737_DES/3600.0))                        # kJ/kg (~2163)

# ==========================================================================
#  322C001  LP absorber (43 °C, 3.9 bar a); GCB off-gas boot-pinned at runtime
# ==========================================================================
A328_M755_DES = 31478.0                                     # Comp-II draw via 322P002
A328_M755_RHO = 1005.0                                      # kg/m3, stream 755 eff. density @40 C (Combined_1750 tbl, col 755) -> FT-322402 m3/h (31478/1005=31.32 -> PFD 31.3)
A328_M756_DES = 33358.0                                     # 756 -> 323E003 wash feed (PFD anchor, stream 756)
A328_ABS_DES  = A328_M756_DES - A328_M755_DES - A328_CPL_DES # 130 NH3/CO2 absorbed (mass-balance closure: 33358-31478-1750)
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
A328_PHI_ABS    = None   # absorbed fraction 980/GCB_DES (total); species split is a frozen carbamate ratio on top
A328_VENT_DES   = None   # kg/h vented = GCB_DES − 980
A328_LAMBDA_ABS = None   # kJ/kg absorption enthalpy (back-solved at pin for T=43)

# ==========================================================================
#  323E003 + 323D001 + 323P001  LPCC (74 °C, tempered-water cooled, 3.2 bar a)
# ==========================================================================
R3232_E003_M305_DES  = R323_M305_DES                        # 24563.4 top vapour ex 323C003
R3232_E003_M718B_DES = R3232_M718B_DES                      # 3560.4
R3232_E003_M776_DES  = R328_D001_M776_DES                   # 8274.4
R3232_E003_M797_DES  = R3232_M797_DES                       # 1758
R3232_E003_IN_DES    = (R3232_E003_M305_DES + R3232_E003_M718B_DES + R3232_E003_M776_DES
                       + R3232_E003_M797_DES)                              # mapped physical inlets
R3232_E003_PHI321 = 1323.0 / (R3232_E003_M305_DES + R3232_E003_M797_DES)  # vent split on (305+797)
R3232_E003_M321_DES = R3232_E003_PHI321 * (R3232_E003_M305_DES + R3232_E003_M797_DES)  # 1323
R3232_E003_PHI744 = 31478.0 / A328_M756_DES                 # wash split on 756 -> Comp II
R3232_E003_M744_DES = R3232_E003_PHI744 * A328_M756_DES      # 31478
# PFD-22 stream 744 (328C002 -> 323E003 Comp-II wash, Amm. Water) design volumetric flow
# (m3/h).  The FIC-328402 leg carries 31478 kg/h, which is stream 744, NOT 735 -- the two are
# easy to confuse because the PFD gives BOTH a volume flow of 31.4 m3/h, but they are distinct
# streams (735: 31114 kg/h, 56 C, 4.1 bar, rho 992.4  |  744: 31478 kg/h, 44 C, 1 bar, rho 1002).
# FIC-328402 is a VOLUMETRIC loop: the operator enters SP in m3/h, so the density is BACK-SOLVED
# from the plant's own design state (31478 kg/h at 31.4 m3/h) rather than lifted from a table --
# no fabricated constant, and it lands on the PFD's own stream-744 density (1002) to 0.05 %.
# The physics mass balance (m_744) is UNTOUCHED: _fic_flow(rho=RHO_744_KGM3) still returns kg/h.
S744_VOL_DES = 31.4
RHO_744_KGM3 = R3232_E003_M744_DES / S744_VOL_DES            # 1002.48 kg/m3, PFD-744 back-solve
# FFIC-329401 328C004 desorber-II steam/feed RATIO master, in T/M3 -- the DCS basis (the baked
# 328-1 ratio panel reads "SP 0.169 T/M3 / MV 0.168 T/M3").  On CAS the FIC-329401 slave SP is
# FIC-328402 * this ratio, and FV-329401 strokes to hold it.  The feed measurement is therefore
# the FIC-328402 wash leg, which is a VOLUMETRIC loop, so the ratio is LP steam in t/h per m3/h
# of that feed -- NOT a dimensionless kg/kg.
# Written with the SAME float operation order as the live ffic_pv in step_sim so the design
# point is bit-exact: pv == sp -> du == 0 -> the LP-steam demand holds 6495 kg/h and the boot
# pin cannot move.  At design 6.495 t/h / 31.4 m3/h = 0.20685 T/M3.
R328_FFIC_RATIO_DES = ((R328_C004_M931_DES / 1000.0)
                       / (R3232_E003_M744_DES / RHO_744_KGM3))           # 0.20685 T/M3
R3232_E003_M308_DES = R3232_E003_IN_DES - R3232_E003_M321_DES             # condensed-liquid draw
R3232_E003_T = 74.0 ; R3232_TW_T = 60.0 ; R3232_E003_T305 = 119.0
# 323E003 tempered-water circuit: PFD stream 1102 supply 55 °C / 1103 return 65 °C.  R3232_TW_T is
#   their mean (== 60) and stays the DESIGN datum for the UA back-solve below -- never a live value.
R3232_TW_SUP_T = 55.0 ; R3232_TW_RET_T = 65.0               # TIC-323013 SP (1102) ; TT-323015 (1103)
R3232_TV13_DES_PCT = 50.0 ; R3232_TW_TAU_S = 25.0           # TV-323013A design stroke ; supply-T lag (s)
R3232_E003_T744 = R3232_E003_T - 30.0                       # 44 °C wash to Comp II
R3232_D001_P_BARA = 3.2 ; R3232_D001_P_KP = 0.30
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
                    + R3232_E003_M797_DES *(R3232_M797_T      - R3232_E003_T))
                   / 3600.0 * R3232_CP)                                   # kW
R3232_E003_LAMC = ((R3232_E003_Q_DES_KW - R3232_E003_SENS)
                   / (R3232_E003_M_COND_DES/3600.0))                      # kJ/kg
R3232_P001_RPM_DES = R3232_E003_M308_DES / (1218.0 * 0.5046)              # 62.99 rpm (SIC-323901)

# ==========================================================================
#  323C005 + 328V001 + 328D003  (LP absorber vent scrub + carbamate collector)
# ==========================================================================
A323_C005_M756_DES = 33358.0
A323_C005_M702_DES = 440.0
A323_C005_M708_DES = 462.0
A323_C005_VENT_DES = 80.0
# Supplied absorber mapping closes this unit without a fictitious makeup stream:
# 756(33358)+702(440)+708(462) = 343(34180)+341(80) kg/h exactly.
A323_C005_MAKEUP = 0.0
A323_C005_BOT_DES  = 34180.0
A323_C005_T = 55.0 ; A323_C005_MAKEUP_T = 30.0
A323_C005_M_TAU_S = 300.0
A323_C005_M_DES = A323_C005_BOT_DES/3600.0 * A323_C005_M_TAU_S
A323_C005_ABS_DES = A323_C005_M702_DES + A323_C005_M708_DES - A323_C005_VENT_DES
A323_C005_SENS_DES = ((A323_C005_M756_DES*(A328_C001_T - A323_C005_T)
                       + A323_C005_M702_DES*(45.0 - A323_C005_T)
                       + A323_C005_M708_DES*(121.0 - A323_C005_T))
                      / 3600.0 * R3232_CP)
A323_C005_LAM = -A323_C005_SENS_DES * 3600.0 / A323_C005_ABS_DES
# Owner-approved 328D003 physical capacities. These supersede the theoretical 561 m3,
# 50/30/20 split formerly copied from a secondary equipment summary. All three liquid bays
# communicate through openings; compartment III is the large shared accumulation baffle.
A328_D003_VOL_I_M3 = 18.0
A328_D003_VOL_II_M3 = 43.0
A328_D003_VOL_III_M3 = 429.0
A328_D003_VOL_TOTAL_M3 = (
    A328_D003_VOL_I_M3 + A328_D003_VOL_II_M3 + A328_D003_VOL_III_M3
)
A328_D003_RHO_KGM3 = 992.0
A328_D003_MI_FULL = A328_D003_VOL_I_M3 * A328_D003_RHO_KGM3
A328_D003_MII_FULL = A328_D003_VOL_II_M3 * A328_D003_RHO_KGM3
A328_D003_MIII_FULL = A328_D003_VOL_III_M3 * A328_D003_RHO_KGM3
A328_D003_MI_DES = A328_D003_MI_FULL * 0.50
A328_D003_MII_DES = A328_D003_MII_FULL * 0.50
A328_D003_MIII_DES = A328_D003_MIII_FULL * 0.50
A328_D003_M343_DES = A323_C005_BOT_DES
A328_D003_COMP_I_ROUNDING_KGH = 1.0
A328_D003_COMP_II_ROUNDING_KGH = 2.0
# PFD-22 stream 793 (Amm. Water 56 C, rho 992.4) — a normally-closed SPARE branch off the same
# 343/733 Comp-II discharge header that feeds 735 / 791 / 734.  PFD design flow is 0 kg/h and
# 0 m3/h, so FIC-328405 sits at 0 % stroke at design; full stroke is one branch capacity, i.e.
# the twin of the 791/734 legs (1534 kg/h).
S793_CAP_KGH = R3232_E011_M402_DES                          # 1534.0 kg/h at 100 % stroke
# Stream 741 (TD-005): purified process-condensate RECYCLE, 328E007 -> 328E001 -> 328D003 Comp II.
# PFD-22 col 741 is "Pur. Pr. C", 0 kg/h / 0 m3/h at 40 C / 3.9 bar with rho 992.42 -- i.e. the line
# exists but is NORMALLY CLOSED at 100 % load, exactly like the 793 spare.  It is a DIVERSION of
# the 740 boundary export (the condensed 328C004 bottoms, stream 739), NOT new mass: at run time
# m_741 is clamped to m739_prev and the 740 export is published as (m_739 - m_741), so Comp II gains
# exactly what the boundary loses and the plant balance closes (Expert_Interrogation_Log CP-2).
# S741_CAP is the full-stroke ask; the min() against m739_prev enforces the physical cap.
S741_CAP_KGH  = R328_C004_M739_DES                          # 33724 kg/h full-stroke ask (= design 740)
RHO_741_KGM3  = 992.42                                      # kg/m3, PFD col 741 "Density eff." @ 40 C
A328_M741_T   = 40.0                                        # C, PFD col 741 operating temperature
S793_M_DES   = 0.0                                          # PFD design flow (normally closed)
A328_D003_TI = 44.0 ; A328_D003_TII = 56.0
# Compartment III has no independent process feed temperature. Seed it from the inventory-weighted
# temperatures of the two active bays so the buffer introduces no independent heat anchor.
A328_D003_TIII = ((A328_D003_MI_DES * A328_D003_TI
                   + A328_D003_MII_DES * A328_D003_TII)
                  / (A328_D003_MI_DES + A328_D003_MII_DES))
A328_D003_V001_T = A328_D003_TII
# Comp I carbamate-formation exotherm 2NH3+CO2<=>NH2COONH4 (λ_I on total inflow):
A328_D003_LAM_I = -A328_CP * (
      A328_D003_M719*(A328_D003_M719_T - A328_D003_TI)
    + A328_D003_M720*(A328_D003_M720_T - A328_D003_TI)
    + A328_D003_M721*(A328_D003_M721_T - A328_D003_TI)
    + A328_D003_M759*(A328_D003_M759_T - A328_D003_TI)
    ) / (A328_D003_M719 + A328_D003_M720 + A328_D003_M721 + A328_D003_M759)

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
R328_E021_EPS_T = (R328_C003_T746 - R328_C002_T_BOT_BOT) / (R328_C003_T - R328_C002_T_BOT_BOT)   # 51/61 = 0.83607
# Hot-side (stream 749) shell loss in flow-temperature units [kg.K/h], back-solved from the plant's
# own design state -- the hot duty the cold side does NOT receive:
#   34062*(200-148) - 33769*(190-139) = 1771224 - 1722219 = 49005 kg.K/h = 49005/3600*4.0 = 54.45 kW,
# i.e. it reconstructs the datasheet's own R328_E021_LOSS = 54.4 kW (same provenance argument as
# R328_E021_EPS_T above).  Used as an ENERGY-BALANCE closure, not as a second effectiveness, so
# 328E021 can neither create nor destroy energy off-design.
R328_E021_LOSS_DT = (R328_C004_M749_DES * (R328_C003_T    - R328_C004_T749)
                     - R328_C003_M746_DES * (R328_C003_T746 - R328_C002_T_BOT_BOT))   # 49005 kg.K/h
R328_E007_EPS  = 0.6667                                     # 328E007 feed/effluent interchanger
R328_E007_LOSS = 18.3                                       # kW shell heat loss
R328_E007_TC_OUT = 114.0 ; R328_E007_TH_OUT = 89.0         # -> 738 feed / 740 boundary (design anchors)
# AUDIT C10 — 328E007 was DEAD: the two constants above were defined and never referenced, so the
# 328C002 feed sat on a frozen R328_C002_T_BOT738 = 114 and TT-328006 on a frozen 89, i.e. a 2005 kW
# interchanger duty completely decoupled from its own live hot stream (the 328C004 bottoms).  Wired
# with the SAME two-part idiom 328E021 already uses: a design-temperature effectiveness for the cold
# outlet, and an ENERGY-BALANCE closure (not a second effectiveness) for the hot outlet, so 328E007
# can neither create nor destroy energy off-design.
#   cold: 56 + (58/87)*(143-56) = 114.0 EXACTLY  (Q_cold = 31114/3600*4.0*58 = 2005.1 kW)
#   hot : 143 - (31114*58 + 16484)/33724 = 89.0 EXACTLY  (16484 kg.K/h = 18.32 kW ~ R328_E007_LOSS)
# Both verified bit-exact in IEEE754, same as R328_E021_EPS_T / R328_E021_LOSS_DT above.
R328_E007_EPS_T   = (R328_E007_TC_OUT - A328_D003_TII) / (R328_C004_T - A328_D003_TII)   # 58/87 = 0.66667
R328_E007_LOSS_DT = (R328_C004_M739_DES * (R328_C004_T - R328_E007_TH_OUT)
                     - R328_C002_M738_DES * (R328_E007_TC_OUT - A328_D003_TII))         # 16484 kg.K/h
# 328C002 top-to-bottom design differential: the column top (stream 737 / TT-328008 node, 117 C) sits
# 22 C below the bottoms state s.a328_c002_T (139 C).  Lets TT-328008 and the TIC-328008 inferential
# ride the LIVE column instead of a module constant (AUDIT B4 / C31).
R328_C002_DT_TOP = R328_C002_T_BOT_BOT - R328_C002_T_BOT_TOP        # 22 C
# 328C003 bottoms-to-overhead design differential: stream 748 leaves at 188 C (PFD-22) against the
# 200 C bulk, so TT-328011 rides the live hydrolyser state at that offset (AUDIT B6).
R328_C003_DT_748 = R328_C003_T - R328_C002_T_BOT748             # 12 C
# --- TIC-328008 inferential: H2O mol% in 328C002 offgas (-> 328E004) ---
# VLE node is the 328C002 OVHD (117 C / 3.5 bar a), NOT the 328D001 drum (2.6 bar a):
# the drum sits 0.9 bar below the column top across 328E004, so the drum-node Raoult
# (62.9 mol%) mis-anchored the split. Pure Raoult at the true node is 51.44 mol%,
# still 5.2 pts over the datasheet, so a lumped H2O activity coeff PHI closes it to
# the mandated PFD stream 737 (46.21 mol%). PHI back-solves as an identity, so DES
# reproduces 46.21 bit-exact while the runtime form (main.py:~3757) stays live on drum P.
R328_C002_P_TOP  = 3.5                                      # 328C002 OVHD press (bar a) at the VLE node
# ==========================================================================
#  AUDIT C1 / C29 — column PRESSURE states for 328C002 and 328C004
# ==========================================================================
#  The bug the audit measured: a 30 % LP-steam cut to 328C004 moved its temperature by EXACTLY
#  0.0 K, and cutting the 328C003 overhead relief moved 328C002 by 8e-10 K.  The mechanism was an
#  algebraic cancellation -- LAM737 was back-solved as Q_DES/(m737_DES/3600) while m_737 was defined
#  as m737_DES*(q/Q_DES), so P_c002 = q - m_737*LAM737/3600 collapsed to q - q == 0 identically.
#
#  The auditor's proposed cure (redefine the latents) is WRONG: a boiling vessel at fixed pressure
#  genuinely does hold its temperature -- surplus duty leaves as vapour, not as sensible heat.  The
#  real defect is one level down.  Neither column had a PRESSURE state (328C002's pressure existed
#  only as s.a328_d001_P + 0.9 inside one inferential; 328C004 had none at all), so the boiling
#  temperature was pinned at the DESIGN value instead of tracking the live bubble point.  On the
#  plant a strip-steam loss cuts boil-up, the column pressure falls, and the temperature falls with
#  it.  That chain now exists:  duty -> boil-up -> pressure -> bubble point -> temperature.
#
#  Bottom-node offset: the bubble point is evaluated at the column BOTTOM, which sits above the
#  overhead by the tray/static head.  Back-solved from each column's own PFD (T_bottom, P_overhead)
#  pair, so tsat at the bottom node reproduces the PFD bottoms temperature exactly.  psat_water_bara
#  and tsat_steam are analytic inverses (identical Antoine coefficients), and the round trip
#  tsat_steam(psat_water_bara(T)) == T was verified bit-exact at both 143.0 and 139.0.
#    328C004: psat(143) - 3.7  = +0.204 bar  -- 22 trays of head, physically a static column.
#    328C002: psat(139) - 3.5  = -0.010 bar  -- essentially zero; the small NEGATIVE value is the
#             dissolved NH3/CO2 raising the liquor's vapour pressure above pure water, so the
#             pure-water bubble point slightly overstates it.  Treated as one lumped offset.
R328_C002_P_KP   = 0.02                                     # bar per (kg/s) net vapour imbalance
R328_C002_DP_COL = psat_water_bara(R328_C002_T_BOT_BOT) - R328_C002_P_TOP     # -0.0104 bar
R328_C004_P_BARA = 3.7                                      # bar a, PFD-22 stream 750 / 779 / 780
R328_C004_P_KP   = 0.02                                     # bar per (kg/s) net vapour imbalance
R328_C004_DP_COL = psat_water_bara(R328_C004_T) - R328_C004_P_BARA        # +0.2041 bar
R328_E004_DP     = R328_C002_P_TOP - R328_D001_P_BARA       # 0.9 bar drop 328C002 top -> 328D001 drum over 328E004
R328_D001_OFFGAS_H2O_PFD = 46.21                            # mol% H2O in offgas, Combined_1750 PFD stream 737 @117 C / 3.5 bar a
R328_D001_OFFGAS_PHI = (R328_D001_OFFGAS_H2O_PFD/100.0) * R328_C002_P_TOP / psat_water_bara(R328_C002_T_BOT_TOP)   # H2O activity coeff back-solved to PFD 737; psat(117)=1.8004 -> 0.898328
R328_D001_OFFGAS_H2O_DES = 100.0 * R328_D001_OFFGAS_PHI * psat_water_bara(R328_C002_T_BOT_TOP) / R328_C002_P_TOP   # = 46.21 mol% -> 328E004 (identity anchor; supersedes 62.9 drum-node Raoult)


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
R324_CP_SOLN   = R323_CP_SOLN                     # 2.5 kJ/kg.K lumped urea-melt cp (design anchor)
# AUDIT C10.  The evaporation train is where the single lumped cp is most wrong, because it is the
# one place whose PURPOSE is to change the composition: the feed enters at 80 % urea and Stage 2
# leaves at 97.71 %, over which the true cp falls 2.50 -> 2.12 (the constant runs 18 % high at the
# Stage-2 end).  Each stage now takes cp at its OWN local composition and temperature.
#   * FEED cp appears in both the design duty derivation and the tick, and is changed in BOTH, so
#     the back-solved UA still gives dT/dt = 0 at the seed -- the fixed point is preserved by
#     construction, not by luck.
#   * HOLDUP cp appears only as the denominator of the temperature ODE.  At design the numerator
#     P_e001 is exactly 0, so 0/(M*cp) = 0 for ANY cp: the holdup value cannot move the fixed
#     point at all, only the speed of the approach to it.
# The three per-location values are defined below, each next to the anchors it needs.
R324_W_IN      = 0.80                             # feed urea mass fraction (ex 323D002)
R324_W_EV1     = 0.9431                           # Evaporator-I product frac (HARD; HMB 324, was 0.95)
R324_W_EV2     = 0.9771                           # Evaporator-II product frac (HARD; HMB 324, was 0.986)
# --- G7: the 324E001/F001 and 324E003/F003 vacuum P/T tears are ALGEBRAIC recycles (no inter-stage
#     holdup within a tick: separator pressure sets equilibrium vapour, vapour + ejector pull set
#     pressure). They are closed by a bounded Picard fixed-point inner solve whose declared tolerance
#     and iteration cap live here as the single source of truth shared by the loops and the
#     RECYCLE_CLASSIFICATION telemetry. Measured convergence: <=7 of 20 iters to <1e-12 across the
#     0.05-0.80 bar(a) separator envelope, so plain Picard already satisfies the acceptance and
#     Wegstein/Anderson acceleration is unnecessary. Fallback if the cap is hit: the last iterate.
R324_PT_LOOP_TOL   = 1e-12                        # max(|dP|,|dT|) convergence tolerance (bar / degC)
R324_PT_LOOP_MAXIT = 20                           # bounded iteration cap; on cap -> last-iterate fallback
R324_FEED_T_C  = R323_F010_T_SP_C                 # 99 C feed boundary (stream ex 323)

# --- design mass balance (kg/h) : derived from the live design feed -----------
R324_FEED_DES  = R323_M324_DES                    # = R323_M317_DES tank throughput
R324_U_DES     = R324_W_IN  * R324_FEED_DES       # urea mass flow (conserved end-to-end)
R324_P1_DES    = R324_U_DES / R324_W_EV1          # Stage-1 melt @94.31 %
R324_V1_DES    = R324_FEED_DES - R324_P1_DES      # Stage-1 vapour -> 324E002 condenser
R324_P2_DES    = R324_U_DES / R324_W_EV2          # Stage-2 melt @97.71 % (final product)
R324_V2_DES    = R324_P1_DES  - R324_P2_DES       # Stage-2 vapour -> 324E005 condenser
# AUDIT C2 — total CONDENSABLE load on the vacuum-condenser train (324E002/E005/E006/E007), i.e. the
# 323F010 flash vapour 790 plus both evaporator-stage vapours 705/709.  Used to make the 328D003
# Comp-I condensate return (PFD 719+720+721) a LIVE function of what the evaporation section actually
# boils, instead of the three frozen constants that decoupled the two units entirely.  Anchored, so
# the ratio is exactly 1.0 at design.
R324_COND_DES  = R323_MEVAP_DES + R324_V1_DES + R324_V2_DES    # kg/h (12013.3 + 14073.1 + 2737.7)

# --- AUDIT F-4/F-5 ---------------------------------------------------------------------------
# The two W_EV anchors above are the CONCENTRATION TARGET, not a law of nature.  Coded as
# `p_m = urea_in / W_EV` they pinned the melt strength to a constant: cutting the Evap-I steam
# could not dilute the product, and the whole latent deficit was absorbed by the temperature ODE.
# Worse, the PY-324201 / AY-324701 soft sensors (`conc_infer_324`) DID move off design, so the
# HMI showed a strength the mass balance refused to produce.  The water actually removed is now
# min(concentration-limited, duty-limited) and the published strength follows the live melt.
# The design latent loads R324_Q1_DES_KW / R324_Q2_DES_KW are defined with the λ constants below.

# --- Stage 1 : Evaporator I  324E001 / 324F001  (0.33 bar a, hold 130 C) ------
R324_F001_P_BARA = 0.33                           # bar a separator vacuum boundary (HARD)
R324_E001_T_SP_C = 130.0                          # C melt boundary (HARD)
R324_LAM_V1      = 2174.0                          # kJ/kg water latent @130 C
R324_E001_PCHEST_DES = 3.96                       # bar a steam-chest press. (324E001 DDS N2: sat. LP,
                                                  #   between the 3.7 bar a/144 C and 4.1 bar a/146 C rows)
R324_E001_OP_DES = R324_E001_PCHEST_DES / R323_P_STEAM_SUP * 100.0   # 78.99 % PIC-329203 design stroke
# Q_E001 = feed sensible (99->130) + latent(V1) ; kW
R324_CP_FEED1 = urea_soln_cp(R324_W_IN,  R324_FEED_T_C)      # 80 % urea @ 99 C -> 2.5 BIT-EXACTLY
R324_CP_HOLD1 = urea_soln_cp(R324_W_EV1, R324_E001_T_SP_C)   # 94.31 % @ 130 C  -> ~2.19
R324_E001_Q_DES_KW = (R324_FEED_DES/3600.0*R324_CP_FEED1*(R324_E001_T_SP_C - R324_FEED_T_C)
                      + R324_V1_DES/3600.0*R324_LAM_V1)
R324_E001_UA_KW  = R324_E001_Q_DES_KW / (tsat_steam(R324_E001_PCHEST_DES) - R324_E001_T_SP_C)
R324_Q1_DES_KW   = R324_V1_DES/3600.0*R324_LAM_V1   # AUDIT F-4: design Stage-1 LATENT load (kW)
R324_F001_M_TAU_S = 180.0                          # s melt residence -> separator holdup
R324_F001_LVL_SP  = 55.0                           # % (LIC-free gravity leg, indicative)
R324_F001_M_DES   = R324_P1_DES/3600.0 * R324_F001_M_TAU_S
R324_F001_M_FULL  = R324_F001_M_DES / (R324_F001_LVL_SP/100.0)
# vacuum : PIC-324202 false-air bleed balances the 324F002 ejector pull at design
R324_F001_P_KP    = 0.02                           # bar a per (kg/s) net vapour imbalance
R324_F001_FA_DES  = 21.0                            # kg/h PFD stream 784 false-air (PV-324202)
R324_PV202_OP_DES = 50.0                            # % PV-324202 design stroke
R324_F001_EJPULL_DES = 72.0                         # kg/h PFD stream 706, gas leaving 324E002
# --- 324E001 steam-side condensate : LIC-329505 "active controlled steam trap" -
#  The chest condenses the LP heating steam whose latent it surrenders as Q_e001,
#  so the shell fills with condensate; LV-329505 drains it to hold the level and
#  keep the tubes flooded to the design point.  Steam-side ONLY -> off the
#  urea/water conservation network: at design condensate generated == LV-329505
#  discharge, so the level parks at SP and neither drifts nor couples a pinned qty.
R324_E001_LAM_STEAM   = 2133.0                     # kJ/kg LP steam latent @~3.96 bar a chest (sat. steam table)
R324_E001_COND_DES    = R324_E001_Q_DES_KW / R324_E001_LAM_STEAM * 3600.0   # kg/h steam condensed at design
R324_E001_COND_LVL_SP = 50.0                       # % LIC-329505 shell condensate setpoint (indicative)
R324_E001_COND_TAU_S  = 90.0                       # s condensate residence -> shell holdup
R324_E001_COND_M_DES  = R324_E001_COND_DES/3600.0 * R324_E001_COND_TAU_S    # kg holdup at SP
R324_E001_COND_M_FULL = R324_E001_COND_M_DES / (R324_E001_COND_LVL_SP/100.0)   # kg at 100% level
R324_LV9505_OP_DES    = 50.0                       # % LV-329505 design drain stroke
R324_LV9505_SPAN      = R324_E001_COND_DES / (R324_LV9505_OP_DES/100.0)     # kg/h full-open drain capacity
# --- 324F002 Stage-1 vacuum ejector : HIC-329605 motive LP steam hand controller
#  324F002 is the steam-jet ejector that pulls the 324F001 vacuum; its saturated
#  LP motive steam (650 kg/h, 4.1 bar a / 146 C through nozzle N2, 324-1 ED-2)
#  drives the entrainment.  HIC-329605 is the operator hand valve on that motive
#  line (published as HV-329605, tracks 1:1).  Entrainment ratio ~ constant, so the
#  ejector pull scales linearly with motive; anchored so at the design stroke the
#  live pull == R324_F001_EJPULL_DES bit-exact (ratio 1.0) -> vacuum ODE unchanged
#  at steady state.  Steam-side hand valve -> off the urea/water conservation network.
# AUDIT C16 — was 650.0, sourced from the ejector datasheet (324-1 ED-2), not the PFD.  CLAUDE.md §2:
# PFD values strictly override coded constants, and here the PFD is also the stronger evidence — the
# licensor's own closure around 324F002 is exact on it: 706 (72 kg/h, the 324E002 shell vent) + 924
# (390) = 462 = stream 708 to 323C005.  The pull is anchored as a RATIO (mot9605_m / MOTIVE_DES), so
# the design fixed point is untouched and only the published motive flow corrects, 650 -> 390 kg/h.
R324_F002_MOTIVE_DES  = 390.0                      # kg/h sat. LP motive steam @4.1 bar a / 146 C (PFD-21 stream 924)
R324_HIC9605_DES_PCT  = 50.0                        # % HIC-329605 design motive-valve stroke (indicative)
R324_HV9605_SPAN      = R324_F002_MOTIVE_DES / (R324_HIC9605_DES_PCT/100.0)   # kg/h full-open motive capacity

# --- Stage 2 : Evaporator II 324E003 / 324F003  (0.131 bar a, hold 140 C) -----
R324_F003_P_BARA = 0.131                           # bar a deep-vacuum boundary (HARD)
R324_E003_T_SP_C = 140.0                           # C melt boundary (HARD)
R324_LAM_V2      = 2144.0                           # kJ/kg water latent @140 C
R324_E003_OP_DES = 90.0                             # % PIC-329212 design steam-valve stroke
R324_E003_PCHEST_DES = R324_E003_OP_DES/100.0 * steam_system.P_MP_BARA
# Q_E003 = P1 sensible (130->140) + latent(V2) ; kW
# Stage 2's feed IS the Stage-1 melt, so its cp is the Stage-1 melt cp -- same composition, same
# temperature.  Naming it separately keeps the two roles readable at the call sites below.
R324_CP_FEED2 = R324_CP_HOLD1                                # 94.31 % @ 130 C, the Stage-1 melt
R324_CP_HOLD2 = urea_soln_cp(R324_W_EV2, R324_E003_T_SP_C)   # 97.71 % @ 140 C -> ~2.12
R324_E003_Q_DES_KW = (R324_P1_DES/3600.0*R324_CP_FEED2*(R324_E003_T_SP_C - R324_E001_T_SP_C)
                      + R324_V2_DES/3600.0*R324_LAM_V2)
R324_E003_UA_KW  = R324_E003_Q_DES_KW / (tsat_steam(R324_E003_PCHEST_DES) - R324_E003_T_SP_C)
R324_E003_LAM_STEAM = steam_system.H_G_MP - steam_system.H_F_MP
R324_9BAR_OTHER_DES = (steam_system.M_USERS_9_DES
                       - R324_E003_Q_DES_KW / R324_E003_LAM_STEAM)
R324_Q2_DES_KW   = R324_V2_DES/3600.0*R324_LAM_V2   # AUDIT F-5: design Stage-2 LATENT load (kW)
R324_F003_M_TAU_S = 180.0
R324_F003_LVL_SP  = 54.7                            # % LIC-324501 setpoint (tagged screenshot)
R324_F003_M_DES   = R324_P2_DES/3600.0 * R324_F003_M_TAU_S
R324_F003_M_FULL  = R324_F003_M_DES / (R324_F003_LVL_SP/100.0)
R324_F003_P_KP    = 0.02
R324_F003_FA_DES  = 21.0                             # kg/h PFD stream 783 false-air (PV-324203)
R324_PV203_OP_DES = 50.0

# ==============================================================================================
#  AUDIT F-8 / TD-009 — DOWNSTREAM COMPONENT SPECIES BALANCE (units 323 + 324)
# ==============================================================================================
# Species tracking used to stop dead at LV-322501: everything downstream was LUMPED MASS moved by
# design split fractions, so there was no C2 component balance and no C6 summation equation past
# the HP loop, and the only composition-aware objects were read-only soft sensors.
#
# The layer below rides ON TOP of the existing (already conservative, already anchored) total-mass
# and energy ODEs -- it does not touch a single one of them.  Each downstream liquid stage gains a
# six-species mass-fraction state; the species are advanced by the SAME flows the mass ODEs already
# compute, so C1 is untouched by construction and C2/C6 are added on top:
#
#     d(M·w_i)/dt = ṁ_in·w_in,i − ṁ_liq·w_i − ṁ_vap·y_i + ν_i·ξ ,     Σ w_i = Σ y_i = 1
#
# Two pieces of real physics fall out of the design data and had to be modelled explicitly:
#
#  (1) BIURET FORMATION, 2 Urea -> Biuret + NH3, happens in every warm stage.  Back-solving the PFD
#      biuret rise (0.24 % at stream 208 -> 0.85 % at stream 402) gives design extents of 0.66 /
#      0.00 / 0.14 / 1.49 / 1.00 kmol/h across C003/F004/F010/E001/E003 -- 3.28 kmol/h = 338 kg/h
#      total against the 322 kg/h the PFD stream flows imply.  The extents rise with temperature
#      exactly as expected (the two evaporators dominate), which is why UF-85 is dosed at all.
#      Same Arrhenius form and activation energy the stripper already uses (STRIP_BIU_EA).
#
#  (2) VAPOUR COMPOSITION BY RELATIVE VOLATILITY.  y_i is not a free vector: it is set by the live
#      liquid composition through α_i (volatility relative to water), back-solved at the design
#      point AFTER the reaction extent is removed, so the component balance closes exactly:
#          y_i = α_i·w_i / Σ_j α_j·w_j        <- this normalisation IS the C6 summation equation
#      Biuret and HCHO are forced non-volatile (α = 0); the tiny apparent biuret/HCHO vapour in the
#      back-solve is PFD rounding, not chemistry.  Water is the reference (α = 1) and carries the
#      closure residual, which is how a balance closer should behave.
#
# EVERYTHING IS ANCHORED: at the design seed w == w_des at every stage, so y == y_des, so every
# species flow equals its design value and dw/dt == 0 exactly.  The layer is a fixed point of the
# design state, which is why it cannot move the HMB.
MW_SOL = {"Urea": 60.056, "Biuret": 103.081, "NH3": 17.0304,
          "CO2": 44.0098, "H2O": 18.0152, "HCHO": 32.031}
SOL_SPECIES = tuple(MW_SOL)
SOL_NONVOL  = ("Biuret", "HCHO")     # never leave in the vapour at these temperatures


def _w_norm(d: dict) -> dict:
    """PFD mass-% row -> mass FRACTIONS summing to exactly 1 (the C6 summation, applied once)."""
    tot = sum(d.get(k, 0.0) for k in SOL_SPECIES)
    return {k: d.get(k, 0.0) / tot for k in SOL_SPECIES}


def _reconcile_melt(w_in: dict, m_in: float, m_out: float, w_out_tab: dict) -> dict:
    """Deduce the atom-consistent liquid/melt row (G3, doc sec.4.2 reconciliation, determined case).
    Cap every species' outlet at its conservation limit m_in*w_in/m_out: non-volatiles (Urea/Biuret/
    HCHO) conserve exactly; volatiles (NH3/CO2) keep the tabulated outlet only where it does not exceed
    the feed supply (else conserve -- a volatile cannot concentrate up across a boiling/flash stage);
    water balances. The back-solved vapour is then non-negative for every species, so the
    `_sol_stage_anchor` gross-error clip vanishes while the hard urea/water design strength is held."""
    out = {}
    for k in SOL_SPECIES:
        if k == "H2O":
            continue
        conserved = m_in * w_in.get(k, 0.0) / max(m_out, 1e-12)
        out[k] = conserved if k in SOL_NONVOL else min(w_out_tab.get(k, 0.0), conserved)
    out["H2O"] = max(1.0 - sum(out.values()), 0.0)
    tot = sum(out.values())
    return {k: out[k] / tot for k in SOL_SPECIES}


# --- PFD design compositions (MASS %), STRICT source: PFD_20 / PFD_21 process-stream tables -----
W_S208 = _w_norm(dict(Urea=55.85, Biuret=0.24, NH3=7.92, CO2=10.28, H2O=25.68))  # 322E001 bottoms
W_S314 = _w_norm(dict(Urea=68.74, Biuret=0.36, NH3=2.13, CO2=1.05,  H2O=27.72))  # 323C003 bottoms
W_S319_TAB = _w_norm(dict(Urea=71.74, Biuret=0.37, NH3=0.88, CO2=0.66, H2O=26.35))  # PFD 323F004 liquid (rounded)
# G3: reconcile the 323F004 flash liquid to atom-consistency (closes its -1.92 kg/h anchor clip).
W_S319 = _reconcile_melt(W_S314, R323_M314_DES, R323_M319_DES, W_S319_TAB)        # 323F004 liquid (reconciled)
W_S331 = _w_norm(dict(Urea=44.37, Biuret=0.41, H2O=55.00, HCHO=0.23))            # granulation return
W_S317 = _w_norm(dict(Urea=80.00, Biuret=0.42, NH3=0.08, CO2=0.02,  H2O=19.47,
                      HCHO=0.00797))                                             # 323F010 product
# --- G3: the tabulated 324E001/E003 melt rows (below) are mutually inconsistent with their feed at
#     the 1-5 % level (proven gross error, backend/gap_g3_data_reconciliation.py: Chi-square 990/679
#     vs 3.841). The tabulated melt would need urea/species the feed cannot supply, forcing the
#     _sol_stage_anchor back-solve to clip -170/-127 kg/h of negative vapour. Deduce the licensor's
#     UNROUNDED rows by the doc-sec.4.2 reconciliation collapsed to the determined case: hold the hard
#     urea/water design strengths and the shared W_S317 feed, and cap every species' melt at its
#     mass-conservation limit m_in*w_in/m_out (no unsupported net biuret formation; a volatile cannot
#     concentrate up). Water balances. This drives every stage's anchor clip to 0 by construction while
#     the urea strength (=R324_W_EV) and the plant HMB are untouched.  Tabulated rows retained as
#     *_TAB provenance.
W_S401_TAB = _w_norm(dict(Urea=94.31, Biuret=0.69, NH3=0.03, H2O=4.97, HCHO=0.00948))  # PFD-21 324E001 melt (rounded)
W_S402_TAB = _w_norm(dict(Urea=97.71, Biuret=0.85, NH3=0.04, H2O=1.39, HCHO=0.0099))   # PFD-21 324E003 melt (rounded)
W_S401 = _reconcile_melt(W_S317, R324_FEED_DES, R324_P1_DES, W_S401_TAB)  # 324E001 melt (reconciled)
W_S402 = _reconcile_melt(W_S401, R324_P1_DES,   R324_P2_DES, W_S402_TAB)  # 324E003 melt (reconciled)
# PFD-21 finishing boundary. 402G is the raw melt entering 335; UF85 stream 697 is admitted only
# on forward route A, producing stream 609. Datasheet-3 section 5.2 explicitly interlocks UF85 off
# when LV-324501A closes, so route B remains raw 402G despite conflicting prose in 323D002.md.
W_S402G = dict(W_S402)   # G3: raw melt to 335 == the reconciled final-product melt (atom-consistent)
W_S697 = _w_norm(dict(Urea=25.0, H2O=15.0, HCHO=60.0))
W_S609 = _w_norm(dict(Urea=97.07, Biuret=0.89, NH3=0.04, H2O=1.50, HCHO=0.49))


def route_lv324501(m_402g_kgh: float, w_402g: dict, T_402g_C: float,
                   recycle: bool, uf_ratio: float | None = None) -> dict:
    """Conservative LV-324501 selector node.

    A: raw melt 402G + UF85 697 -> mixed stream 609 -> Unit 335.
    B: raw melt 402G -> 323D002 Compartment I; UF85 is interlocked off.

    The reduced energy closure uses the simulator's existing liquid sensible-cp basis.  UF85 has no
    validated excess-enthalpy data in the project, so no heat of mixing is fabricated.
    """
    m_base = max(float(m_402g_kgh), 0.0)
    ratio = R324_UF_RATIO if uf_ratio is None else max(float(uf_ratio), 0.0)
    route_b = bool(recycle)

    total_w = sum(max(float(w_402g.get(k, 0.0)), 0.0) for k in SOL_SPECIES)
    if total_w <= 1.0e-15:
        raise ValueError("LV-324501 stream 402G composition is empty")
    if abs(total_w - 1.0) <= 1.0e-12:
        base_w = {k: float(w_402g.get(k, 0.0)) for k in SOL_SPECIES}
    else:
        base_w = {k: max(float(w_402g.get(k, 0.0)), 0.0) / total_w for k in SOL_SPECIES}

    m_uf = 0.0 if route_b else ratio * m_base
    m_selector = m_base + m_uf
    if m_selector > 1.0e-15:
        selector_w = {
            k: (m_base * base_w[k] + m_uf * W_S697[k]) / m_selector
            for k in SOL_SPECIES
        }
    else:
        selector_w = dict(base_w)

    cp_base = urea_soln_cp(base_w["Urea"], T_402g_C)
    cp_uf = urea_soln_cp(W_S697["Urea"], 40.0)
    heat_capacity_flow = m_base * cp_base + m_uf * cp_uf
    selector_T = (
        (m_base * cp_base * T_402g_C + m_uf * cp_uf * 40.0) / heat_capacity_flow
        if heat_capacity_flow > 1.0e-15 else float(T_402g_C)
    )
    selector_cp = heat_capacity_flow / m_selector if m_selector > 1.0e-15 else cp_base

    m_forward = 0.0 if route_b else m_selector
    m_recycle = m_base if route_b else 0.0
    forward_w = dict(selector_w) if not route_b else dict(base_w)
    recycle_w = dict(base_w)
    forward_T = selector_T if not route_b else float(T_402g_C)
    recycle_T = float(T_402g_C)

    species_residual = {
        k: (m_base * base_w[k] + m_uf * W_S697[k]
            - m_forward * forward_w[k] - m_recycle * recycle_w[k])
        for k in SOL_SPECIES
    }
    energy_in_kw = (
        m_base * cp_base * T_402g_C + m_uf * cp_uf * 40.0
    ) / 3600.0
    energy_out_kw = (
        m_forward * selector_cp * forward_T + m_recycle * cp_base * recycle_T
    ) / 3600.0

    return {
        "route": "B" if route_b else "A",
        "selector_stream": "402G" if route_b else "609",
        "uf85_interlocked": route_b,
        "stream_402g_kgh": m_base,
        "uf85_kgh": m_uf,
        "selector_feed_kgh": m_selector,
        "selector_feed_comp": selector_w,
        "selector_feed_T_C": selector_T,
        "forward_kgh": m_forward,
        "forward_comp": forward_w,
        "forward_T_C": forward_T,
        "recycle_kgh": m_recycle,
        "recycle_comp": recycle_w,
        "recycle_T_C": recycle_T,
        "mass_residual_kgh": m_base + m_uf - m_forward - m_recycle,
        "species_residual_kgh": species_residual,
        "energy_in_kw": energy_in_kw,
        "energy_out_kw": energy_out_kw,
        "energy_residual_kw": energy_in_kw - energy_out_kw,
    }

SOL_BIU_EA    = STRIP_BIU_EA        # J/mol -- biuret formation shares the stripper's activation E
SOL_BIU_ORDER = 2.0                 # 2 Urea -> Biuret + NH3: second order in the urea fraction


#  Full-precision audit hook.  The telemetry payload rounds everything for the HMI, which is right
#  for the operator and useless for an audit: TD-014 was a 1e-5 °C offset amplified by an open
#  integrator, and nothing in the rounded payload could have shown it.  Each of the four
#  bubble-point stages writes its raw branch selectors here every tick.  Written, never read by the
#  engine -- it cannot influence a single number in the model.
_DIAG: dict = {}


def x_water_mol(w: dict) -> float:
    """Water MOLE fraction of a six-species urea liquor, from its mass fractions."""
    n   = {k: w.get(k, 0.0) / MW_SOL[k] for k in SOL_SPECIES}
    tot = sum(n.values())
    return n["H2O"] / tot if tot > 1e-15 else 1.0


def bubble_T_raoult(P_bara: float, w: dict) -> float:
    """Bubble-point temperature (°C) of a urea liquor whose only volatile is water.

    TD-014.  Raoult's law: the partial pressure of water over the solution is x_H2O·Psat(T), and at
    the bubble point that equals the stage pressure, so

        Psat(T_bub) = P / x_H2O      =>      T_bub = Tsat(P / x_H2O)

    Nothing is fitted -- urea, biuret and HCHO raise the boiling point purely by diluting the water
    on a MOLE basis, which is why the mass-fraction vector has to be converted first.  Checked
    against the PFD's own (w, P, T) triplets for the three stages this is used on:

        323F010   80.00 % urea, 0.46 bar a   Raoult 100.3 °C   PFD  99 °C   (+1.3)
        324E001   94.31 % urea, 0.33 bar a   Raoult 123.7 °C   PFD 130 °C   (−6.3)
        324E003   97.71 % urea, 0.131 bar a  Raoult 132.7 °C   PFD 140 °C   (−7.3)

    i.e. it reproduces 88-99 % of a 20-90 °C elevation with no adjustable parameter; the residual is
    the non-ideality (γ_H2O < 1 at these concentrations) and is absorbed by the design anchor,
    because every call site uses the DEPARTURE  T_des + [T_bub(live) − T_bub(design)].  What has to
    be right for the model is the SLOPE with composition, and that is what Raoult supplies.

    NOT valid for 323C003 / 323F004, whose liquors carry NH3 and CO2: there the volatiles dominate
    the bubble point and Raoult-on-water overshoots by 33 °C and 16 °C respectively.  Those two
    stages keep the frozen-offset form anchored on _R323_TSAT_C003_DES / _R323_TSAT_F004_DES.
    """
    return tsat_steam(P_bara / max(x_water_mol(w), 1e-6))


# TD-014 design bubble-point anchors.  Each is the value the DEPARTURE is measured from, so at the
# design composition the bracket is a literal 0.0 and the stage temperature target is exactly the
# PFD boundary -- bit-exact, not a tolerance.
R323_F010_TBUB_DES = bubble_T_raoult(R323_F010_P_BARA, W_S317)   # 80.00 % urea @ 0.46 bar a

# --- AUDIT C10, 323 half: one lumped cp for the whole recirculation train ----------------------
# `cp323 = R323_CP_SOLN` (2.5 kJ/kg.K) covered every stream from the 44 % granulation return at
# 40 C to the 80 % product at 99 C.  cp falls as the solution concentrates -- molten urea is about
# 2.07 against water's 4.2 -- so a single constant is wrong in both directions at once, and it is
# most wrong exactly where the model does its work, because concentrating the solution IS the job.
# Each stage now carries its own, anchored as a DEPARTURE from the licensor's lumped value:
#     cp_stage = R323_CP_SOLN + [ cp(w_live, T_live) - cp(w_des, T_des) ]
# so at the design composition the bracket is a literal 0.0, every back-solved lambda/UA above is
# untouched, and the design energy balance is preserved bit-exactly -- while a real composition or
# temperature excursion now moves the sensible duty the way it does on the plant.
R323_CP_S208_DES = urea_soln_cp(W_S208["Urea"], R323_FEED_DES_T_C)   # 55.87 % @ 119 C, stripper bottoms
R323_CP_C003_DES = urea_soln_cp(W_S314["Urea"], R323_C003_T_SP_C)    # 68.74 % @ 135 C, column bottoms
R323_CP_F004_DES = urea_soln_cp(W_S319["Urea"], R323_F004_T_SP_C)    # 71.74 % @ 106 C, flash liquid
R323_CP_F010_DES = urea_soln_cp(W_S317["Urea"], R323_F010_T_SP_C)    # 80.00 % @  99 C == R323_CP_SOLN
R323_CP_S331_DES = urea_soln_cp(W_S331["Urea"], R323_M331_T_C)       # 44.37 % @  40 C, granulation return


def _sol_stage_anchor(w_in: dict, w_out: dict, m_in: float, m_vap: float, m_liq: float,
                      w_in2: dict = None, m_in2: float = 0.0) -> dict:
    """Back-solve one stage's design biuret extent and relative volatilities from the PFD.

    A stage with a second inlet passes w_in2/m_in2 and the two feeds are summed component-wise
    before the balance is struck.  323F010 is the one that needs it: PFD stream 331, the
    urea-recovery return from the granulation scrubber, joins stream 319 ahead of 323E010.

    Returns {'xi': kmol/h, 'y': design vapour mass fractions, 'alpha': volatility vs water,
             'resid': the kg/h that had to be clipped to keep every vapour flow non-negative}.
    The clip residual is reported, never hidden.  It used to be -1414 kg/h of urea at 323F010 with
    stream 331 absent (finding F-11); with the real two-feed topology it is 0.0 there and the water
    closure term falls from ~1.4 t/h to ~1 kg/h.  Everywhere else it is under 0.4 % of the vapour
    and is PFD percentage rounding."""
    m_i = {k: m_in * w_in[k] + (m_in2 * w_in2[k] if w_in2 else 0.0) for k in SOL_SPECIES}
    xi  = max((m_liq * w_out["Biuret"] - m_i["Biuret"]) / MW_SOL["Biuret"], 0.0)
    gen = {k: 0.0 for k in SOL_SPECIES}
    gen["Biuret"] = +xi * MW_SOL["Biuret"]
    gen["Urea"]   = -xi * 2.0 * MW_SOL["Urea"]
    gen["NH3"]    = +xi * MW_SOL["NH3"]
    vap   = {k: m_i[k] + gen[k] - m_liq * w_out[k] for k in SOL_SPECIES}
    resid = sum(v for v in vap.values() if v < 0.0)
    for k in SOL_SPECIES:
        if k in SOL_NONVOL or vap[k] < 0.0:
            vap[k] = 0.0
    vap["H2O"] += m_vap - sum(vap.values())          # water closes the balance (reference species)
    y = {k: vap[k] / m_vap for k in SOL_SPECIES} if m_vap > 1e-9 else dict(w_out)
    aw = y["H2O"] / w_out["H2O"]
    alpha = {k: ((y[k] / w_out[k]) / aw if (w_out[k] > 1e-12 and k not in SOL_NONVOL) else 0.0)
             for k in SOL_SPECIES}
    alpha["H2O"] = 1.0                               # reference species, by definition
    return {"xi": xi, "y": y, "alpha": alpha, "resid": resid}


SOL_C003 = _sol_stage_anchor(W_S208, W_S314, R323_FEED_DES_KGH, R323_M305_DES,  R323_M314_DES)
SOL_F004 = _sol_stage_anchor(W_S314, W_S319, R323_M314_DES,     R323_M701_DES,  R323_M319_DES)
SOL_F010 = _sol_stage_anchor(W_S319, W_S317, R323_M319_DES,     R323_MEVAP_DES, R323_M317_DES,
                             w_in2=W_S331, m_in2=R323_M331_DES)   # F-11: 319 + 331 -> E010 -> F010
SOL_E001 = _sol_stage_anchor(W_S317, W_S401, R324_FEED_DES,     R324_V1_DES,    R324_P1_DES)
SOL_E003 = _sol_stage_anchor(W_S401, W_S402, R324_P1_DES,       R324_V2_DES,    R324_P2_DES)

# Design (holdup, temperature) anchors for the biuret Arrhenius -- extent scales with inventory,
# urea fraction squared and the Arrhenius factor, each written as a ratio to its design value so
# every factor is exactly 1.0 at the seed.
SOL_STAGES = {
    "C003": {"w": W_S314, "a": SOL_C003, "M": R323_C003_M_DES, "T": R323_C003_T_SP_C},
    "F004": {"w": W_S319, "a": SOL_F004, "M": R323_F004_M_DES, "T": R323_F004_T_SP_C},
    "F010": {"w": W_S317, "a": SOL_F010, "M": R323_F010_M_DES, "T": R323_F010_T_SP_C},
    "E001": {"w": W_S401, "a": SOL_E001, "M": R324_F001_M_DES, "T": R324_E001_T_SP_C},
    "E003": {"w": W_S402, "a": SOL_E003, "M": R324_F003_M_DES, "T": R324_E003_T_SP_C},
}


def sol_vapour_y(w: dict, alpha: dict) -> dict:
    """C6 summation equation: y_i = α_i·w_i / Σ α_j·w_j, so Σ y == 1 by construction.
    At the design liquid composition this returns the design vapour composition bit-exact."""
    num = {k: alpha[k] * w.get(k, 0.0) for k in SOL_SPECIES}
    tot = sum(num.values())
    if tot <= 1e-15:
        return {k: (1.0 if k == "H2O" else 0.0) for k in SOL_SPECIES}
    return {k: num[k] / tot for k in SOL_SPECIES}


def sol_biuret_xi(key: str, M: float, w: dict, T_c: float) -> float:
    """Biuret formation extent (kmol/h), 2 Urea -> Biuret + NH3.  Anchored ratio form: every factor
    is exactly 1.0 at the design seed, so xi == xi_des there and the species balance is stationary.
    Arrhenius uses the stripper's own activation energy -- one biuret reaction, one Ea."""
    st = SOL_STAGES[key]
    if st["a"]["xi"] <= 0.0:
        return 0.0
    r_hold = max(M, 0.0) / st["M"]
    r_urea = (w.get("Urea", 0.0) / st["w"]["Urea"]) ** SOL_BIU_ORDER
    r_arrh = math.exp((SOL_BIU_EA / STRIP_R_GAS_J)
                      * (1.0 / (st["T"] + 273.15) - 1.0 / (T_c + 273.15)))
    return st["a"]["xi"] * r_hold * r_urea * r_arrh


def sol_advance(w: dict, M_pre: float, M_new: float, m_in: float, w_in: dict,
                m_vap: float, y: dict, m_liq: float, xi: float, dt: float,
                m_in2: float = 0.0, w_in2: dict = None) -> dict:
    """Integrate one stage's species holdup and renormalise.  C1 is NOT re-derived here -- M_pre and
    M_new come from the existing total-mass ODE, so this layer can never perturb it.  Returns the
    new mass-fraction vector (Σ w == 1).  m_in2/w_in2 carry a stage's second inlet where it has one
    (323F010 takes PFD stream 331 alongside stream 319 -- finding F-11)."""
    out = {}
    for k in SOL_SPECIES:
        nu = (2.0 * -MW_SOL["Urea"] if k == "Urea" else
              MW_SOL["Biuret"] if k == "Biuret" else
              MW_SOL["NH3"] if k == "NH3" else 0.0)
        m_k = (M_pre * w.get(k, 0.0)
               + (m_in * w_in.get(k, 0.0) + (m_in2 * w_in2.get(k, 0.0) if w_in2 else 0.0)
                  - m_vap * y.get(k, 0.0) - m_liq * w.get(k, 0.0)
                  + nu * xi) / 3600.0 * dt)
        out[k] = max(m_k, 0.0)
    tot = sum(out.values())
    if tot <= 1e-12 or M_new <= 1e-12:
        return dict(w)
    return {k: out[k] / tot for k in SOL_SPECIES}      # C6: renormalise to Sum w == 1


# ==================================================================================================
#  AUDIT F-8 -- rigorous species layer through the desorption train (328C002 / 328C003 / 328C004)
#
#  THE PFD COMPOSITION-UNIT CONVENTION.  Before any of this could be anchored, one thing had to be
#  settled.  A straight mass-% reading of the PFD-22 rows says CARBON IS NOT CONSERVED across
#  328C002: 1658 kg/h CO2 in, 858 kg/h out, 800 kg/h gone.  That is not a licensor error.  The PFD
#  tabulates LIQUID streams in MASS % and VAPOUR/GAS streams in MOLE %, and the "Average Molar
#  Weight" row is the discriminator that proves it -- for stream 737 the mole-% reading reproduces
#  the tabulated 20.81 to 0.001 while the mass-% reading gives 18.94.  Checked across ~90 streams in
#  all four process-stream tables, every stream lands on its class:
#      Carb. Gas / Vapour / CO2 / Air / Inerts / steam ... MOLE %
#      Urea Sol. / Carb. Liq. / Amm. Water / Vap. Cond. .. MASS %
#  Read that way the whole train closes per component to under 2 kg/h in 34-40 t/h, with NOTHING
#  fitted.  See scratchpad/probe_f8_pfd_units.py.
#
#  The same convention retires an "accepted variance" recorded during F-11: stream 790's tabulated
#  2.29 % CO2 was read as mass % (276 kg/h) and did not close against the 651 kg/h the 319/331/315
#  balance forces.  As mole % it is 652.0 kg/h.  It closes to 0.25 kg/h.  The variance was a
#  units misreading of mine, not licensor data.
#
#  WHAT THIS REPLACES.  328C002 and 328C004 ran on FROZEN overhead split constants
#  (R328_C002_PHI737, R328_C004_PHI750): a fixed fraction of whatever flowed in left overhead, with
#  no composition anywhere in unit 328.  Nothing carried urea, NH3 or CO2 as a tracked quantity, so
#  the hydrolyser's urea load had to be a hardcoded fraction -- and it was the WRONG stream's:
#  R328_C003_W_UREA_746 was 0.0082, which is stream 738 (the feed to 328C002), where the PFD gives
#  stream 743/746 as 0.76 %.  328C002 dilutes 31 114 kg/h of feed into 33 769 kg/h of bottoms, so
#  the hydrolyser was being handed 276.9 kg/h of urea against the tabulated 256.6, +7.9 %.  With a
#  real component balance in 328C002 that number is computed, not assumed, and the error cannot
#  recur.
# ==================================================================================================


def _w_from_molepct(d: dict) -> dict:
    """PFD VAPOUR row (MOLE %) -> mass fractions.  See the convention note above: liquid rows are
    mass %, vapour rows are mole %, and mixing the two silently destroys carbon."""
    m = {k: d.get(k, 0.0) * MW_SOL[k] for k in SOL_SPECIES}
    tot = sum(m.values())
    return {k: m[k] / tot for k in SOL_SPECIES}


# --- PFD_22 design compositions, STRICT source: PFD_No__22_Desorption process-stream table --------
W_S738 = _w_norm(dict(CO2=3.71,  H2O=90.24, NH3=5.23,  Urea=0.82))   # liquid: condensate -> 328C002
W_S775 = _w_norm(dict(CO2=23.63, H2O=47.10, NH3=29.20, Urea=0.07))   # liquid: 328D001 reflux
W_S743 = _w_norm(dict(CO2=0.11,  H2O=98.50, NH3=0.63,  Urea=0.76))   # liquid: 328C002 bottoms (=746)
W_S747 = _w_norm(dict(CO2=0.02,  H2O=99.02, NH3=0.97))               # liquid: 328C003 bottoms (=749)
# Stream 739/740 is the <1 ppm purified condensate.  The PFD tabulates NH3 and urea AT 1 ppm and
# leaves CO2 blank -- blank because it rounds to 0.00 %, not because it is absent: 6.8 kg/h of CO2
# enters 328C004 in stream 749 and the column has exactly two outlets.  Taken as zero the volatility
# back-solve divides into it, pins alpha_CO2 to 0, and that CO2 can then never leave -- it piles up
# in the sump forever.  Given the same 1 ppm basis the licensor used for the other two traces on
# this very stream, it strips out with the ammonia, which is what a desorber does to dissolved CO2.
W_S739 = _w_norm(dict(H2O=99.9997, NH3=1.0e-4, Urea=1.0e-4, CO2=1.0e-4))   # liquid: purified
W_S737 = _w_from_molepct(dict(CO2=12.32, H2O=46.21, NH3=41.47))      # VAPOUR: 328C002 OVHD -> 328D001
W_S748 = _w_from_molepct(dict(CO2=13.06, H2O=82.37, NH3=4.57))       # VAPOUR: 328C003 OVHD -> 328C002
W_S750 = _w_from_molepct(dict(CO2=0.03,  H2O=94.88, NH3=5.08))       # VAPOUR: 328C004 OVHD -> 328C002
W_STEAM = _w_norm(dict(H2O=100.0))                                   # 911 MP / 931 LP stripping steam

# --- 322C001 LP-absorber species layer (TD-009 remainder) -----------------------------------------
# The reactive-absorption mirror of the 322E003 scrubber: the inert-purge off-gas (HV-322604, NH3/CO2
# + inerts) is contacted with the recycle ammonia-water loop 755 -> 322C001 -> 756.  NH3/CO2 are taken
# up into the liquor (CO2 + 2 NH3 -> carbamate, tracked as dissolved NH3/CO2); the inerts N2/O2/CH4/H2
# and the NH3/CO2 SLIP leave in the atmospheric vent.  The total recovered mass keeps the boot-pinned
# scalar A328_PHI_ABS (so C1/energy/pin are untouched); the species layer splits it at the frozen
# carbamate ratio and carries a LIVE per-species vent composition — the atmospheric NH3 slip is now a
# real number off the balance, where it used to be a composition-blind constant.
W_S755 = _w_norm(dict(CO2=3.81, H2O=91.13, NH3=4.17, Urea=0.89))     # PFD-20 col 755 Amm.Water in (40 C, MASS %)
W_CPL  = _w_norm(dict(H2O=100.0))                                    # PFD-20 col 954 process condensate (46 C, 100 % H2O)
# Design absorbed 130 kg/h (A328_ABS_DES) split at carbamate stoichiometry 2 NH3 : 1 CO2 — the same
# 2:1 the scrubber uses (d_nh3 = 2*d_co2).  Written so the two sum to A328_ABS_DES exactly (float).
A328_ABS_CO2_DES = A328_ABS_DES * MW_COMP["CO2"] / (MW_COMP["CO2"] + 2.0 * MW_COMP["NH3"])   # 73.286 kg/h
A328_ABS_NH3_DES = A328_ABS_DES - A328_ABS_CO2_DES                                            # 56.714 kg/h
A328_C001_ALPHA  = {k: 1.0 for k in SOL_SPECIES}     # des_advance needs an alpha; m_vap==0 -> unused for w


def _c001_liq_anchor() -> dict:
    """Design liquor / 756-draw composition = the normalised feed mixture (755 + CPL + absorbed).
    Because 755 + CPL + absorbed == 756 in mass (the A328_ABS_DES closure), this vector IS the CSTR
    steady state, so the species holdup is stationary at the design seed and cannot move the HMB."""
    m = {k: A328_M755_DES * W_S755.get(k, 0.0) + A328_CPL_DES * W_CPL.get(k, 0.0) for k in SOL_SPECIES}
    m["CO2"] += A328_ABS_CO2_DES
    m["NH3"] += A328_ABS_NH3_DES
    tot = sum(m.values())
    return {k: m[k] / tot for k in SOL_SPECIES}


W_C001_DES = _c001_liq_anchor()


def _des_stage_anchor(feeds, w_out: dict, m_liq: float, m_vap: float,
                      hydrolyse: bool = False, y_pfd: dict = None) -> dict:
    """Back-solve one desorber/hydrolyser stage from the PFD, the unit-328 counterpart of
    _sol_stage_anchor.  Kept separate rather than folded into that function so unit 328 carries zero
    blast radius into the 323/324 stages the boot pin depends on.

    feeds is a list of (w, kg/h) pairs -- 328C002 has FOUR inlets (738 + 775 + 748 + 750), which is
    the whole reason a new anchor was needed.  hydrolyse=True back-solves the urea-hydrolysis extent
        NH2CONH2 + H2O -> 2 NH3 + CO2
    from the urea that disappears across the stage; the licensor's own numbers put it at 4.2734
    kmol/h in 328C003 (256.6 kg/h of urea destroyed, and stream 747 tabulates no urea at all).

    y_pfd, where the PFD tabulates the overhead composition, is used only to REPORT how far the
    back-solved vapour sits from the licensor's -- an independent check the 323/324 stages never
    had, because no vapour composition is tabulated there.  It is never fed back into the anchor:
    the back-solve is what makes the component balance close exactly, which is what makes the design
    state a fixed point of the species ODE.

    Returns {'xi', 'y', 'alpha', 'resid', 'dev'}."""
    m_i = {k: 0.0 for k in SOL_SPECIES}
    for w, m in feeds:
        for k in SOL_SPECIES:
            m_i[k] += m * w[k]
    xi = max((m_i["Urea"] - m_liq * w_out["Urea"]) / MW_SOL["Urea"], 0.0) if hydrolyse else 0.0
    gen = {k: 0.0 for k in SOL_SPECIES}
    gen["Urea"] = -xi * MW_SOL["Urea"]
    gen["H2O"]  = -xi * MW_SOL["H2O"]
    gen["NH3"]  = +xi * 2.0 * MW_SOL["NH3"]
    gen["CO2"]  = +xi * MW_SOL["CO2"]
    vap   = {k: m_i[k] + gen[k] - m_liq * w_out[k] for k in SOL_SPECIES}
    resid = sum(v for v in vap.values() if v < 0.0)
    for k in SOL_SPECIES:
        if k in SOL_NONVOL or vap[k] < 0.0:
            vap[k] = 0.0
    vap["H2O"] += m_vap - sum(vap.values())          # water closes the balance (reference species)
    y = {k: vap[k] / m_vap for k in SOL_SPECIES} if m_vap > 1e-9 else dict(w_out)
    aw = y["H2O"] / w_out["H2O"]
    alpha = {k: ((y[k] / w_out[k]) / aw if (w_out[k] > 1e-12 and k not in SOL_NONVOL) else 0.0)
             for k in SOL_SPECIES}
    alpha["H2O"] = 1.0                               # reference species, by definition
    dev = max(abs(y[k] - y_pfd[k]) for k in SOL_SPECIES) if y_pfd else 0.0
    return {"xi": xi, "y": y, "alpha": alpha, "resid": resid, "dev": dev}


# ORDER MATTERS.  328C003 and 328C004 both discharge overhead into 328C002, so 328C002 must be
# anchored against the compositions the model will actually deliver there -- its own back-solved
# DES_C003["y"] / DES_C004["y"] -- and NOT against the PFD's tabulated 748 / 750 rows.  The two
# differ by up to 0.2 %pt (PFD percentage rounding), and anchoring on the tabulated rows while
# feeding the back-solved ones makes the design state a slow LEAK instead of a fixed point: it
# showed up as 328C002 ammonia climbing 0.63 % -> 1.53 % over twenty simulated minutes.
# There is no circularity -- both upstream anchors need only tabulated liquid rows.
DES_C003 = _des_stage_anchor(
    [(W_S743, R328_C003_M746_DES), (W_STEAM, R328_C003_M911_DES)],
    W_S747, R328_C003_M747_DES, R328_C003_M748_DES, hydrolyse=True, y_pfd=W_S748)
DES_C004 = _des_stage_anchor(
    [(W_S747, R328_C004_M749_DES), (W_STEAM, R328_C004_M931_DES)],
    W_S739, R328_C004_M739_DES, R328_C004_M750_DES, y_pfd=W_S750)
DES_C002 = _des_stage_anchor(
    [(W_S738, R328_C002_M738_DES), (W_S775, R328_C002_M775_DES),
     (DES_C003["y"], R328_C002_M748_DES), (DES_C004["y"], R328_C002_M750_DES)],
    W_S743, R328_C002_M743_DES, R328_C002_M737_DES, y_pfd=W_S737)

# Design overhead DUTY of each desorber, in exactly the operand order the runtime uses, so the live
# ratio is bit-exactly 1.0 at the seed and the energy-limited overhead rate reproduces its design
# value.  These are algebraic identities of the LAM737 / LAM750 back-solves above -- writing them
# out is what lets the runtime stop using a frozen split fraction.
R328_C002_Q_DES = (R328_C002_SENS
                   + R328_C002_M748_DES / 3600.0 * R328_C002_LAM748
                   + R328_C002_M750_DES / 3600.0 * R328_C002_LAM750)              # kW == m737*lam737
R328_C004_Q_DES = (R328_C004_M749_DES / 3600.0 * R328_CP
                   * (R328_C004_T749 - R328_C004_T)
                   + R328_C004_M931_DES / 3600.0 * R328_C004_M931_DH)             # kW == m750*lam750

# --- how the datasheet TRAY COUNT earns its keep -------------------------------------------------
# The back-solved alphas above are LUMPED single-stage-equivalent volatilities, not tray-level
# equilibrium constants: alpha_NH3 comes out at 5.1e4 in 328C004 because one well-mixed stage has to
# reproduce what 22 real trays achieve (Henry's law for dilute NH3 at 143 C is nearer 10).  Stated
# plainly so nobody mistakes it for thermodynamics.
#
# Left there, the columns would separate identically no matter what the operator did to the steam --
# a 22-tray column and a single flash degrade very differently.  So the lumped alpha is made to move
# with the column's Kremser residual r(S, N), N coming from the datasheet's EXECUTED tray count
# (15 and 22, DDS line 35) times the overall efficiency already derived for 328C004.  For a trace
# species on one well-mixed stage the fraction leaving overhead is m_vap*alpha/(m_vap*alpha + m_liq),
# and setting that equal to (1 - r) inverts EXACTLY to
#       alpha_eff = (L / V) * (1 - r) / r
# so the correction is an identity of the lumped form, not a fitted fudge.  Written as a ratio of
# that expression at live over design conditions: the two calls are bit-identical at the seed, the
# ratio is exactly 1.0, and alpha_live == alpha_des to the last bit.
#
# Applied to the volatile pair (NH3, CO2) using the NH3 stripping factor -- NH3 is what the desorber
# is guaranteed on and what dominates its duty.  Water is the reference (alpha == 1) and urea does
# not strip, so neither moves.
R328_TRAY_EO      = R328_AI701_NTHEO_C004 / R328_C004_NTRAY      # 0.635 overall efficiency, O'Connell
R328_NTHEO_C002   = R328_TRAY_EO * R328_C002_NTRAY               # 9.525 theoretical stages, 15 trays
R328_DES_VOLATILE = ("NH3", "CO2")


def _des_kfac(m_liq: float, m_vap: float, r: float) -> float:
    """Single-stage-equivalent volatility that reproduces a Kremser residual r: (L/V)(1-r)/r."""
    return (m_liq / max(m_vap, 1e-9)) * (1.0 - r) / max(r, 1e-12)


DES_STAGES = {
    "C002": {"a": DES_C002, "w": W_S743, "N": R328_NTHEO_C002, "T": R328_C002_T_BOT_BOT,
             "M": R328_C002_M_DES,
             "V": R328_C002_M748_DES + R328_C002_M750_DES,   # stripping agent: the two hot OVHDs
             "L": R328_C002_M743_DES},
    "C004": {"a": DES_C004, "w": W_S739, "N": R328_AI701_NTHEO_C004, "T": R328_C004_T,
             "M": R328_C004_M_DES,
             "V": R328_C004_M931_DES,                        # stripping agent: the LP steam
             "L": R328_C004_M739_DES},
}
for _st in DES_STAGES.values():
    _st["S"] = R328_AI701_KINF_C004 * (_st["V"] / _st["L"])
    _st["r"] = _kremser_resid(_st["S"], _st["N"])
    _st["k"] = _des_kfac(_st["L"], _st["V"], _st["r"])


def des_alpha_live(key: str, T_c: float, m_vap: float, m_liq: float) -> dict:
    """Live lumped volatilities for a desorber section, anchored so that at the design seed every
    factor is exactly 1.0 and the returned dict is bit-identical to the back-solved design alphas."""
    st = DES_STAGES[key]
    S_live = clamp(R328_AI701_KINF_C004 * math.exp(
        -(R328_AI701_DHSTRIP / 8.314) * (1.0 / (T_c + 273.15) - 1.0 / (st["T"] + 273.15))
    ) * (m_vap / max(m_liq, 1e-9)), 1e-6, 1e6)
    k_live = _des_kfac(m_liq, m_vap, _kremser_resid(S_live, st["N"]))
    # Anti-overflow bounds only -- S^(N+1) with N ~ 14 goes infinite on a cold-start transient.  Both
    # bounds are orders of magnitude outside anything the plant reaches, so the design seed passes
    # through untouched (clamp returns its argument when it is already inside the band) and
    # alpha_live stays bit-identical to the anchor there.
    f = clamp(k_live / st["k"], 1e-6, 1e6)
    return {k: (v * f if k in R328_DES_VOLATILE else v) for k, v in st["a"]["alpha"].items()}


def des_advance(w: dict, M_new: float, feeds, m_vap: float, alpha: dict,
                m_liq: float, xi: float, dt: float):
    """Integrate one desorption-train stage's species holdup and renormalise.  The unit-328
    counterpart of sol_advance: N feeds instead of at most two, and the reaction is urea HYDROLYSIS
        NH2CONH2 + H2O -> 2 NH3 + CO2      (xi in kmol/h)
    rather than biuret formation.  C1 is not re-derived here -- M_new comes from the existing
    total-mass ODE, so this layer cannot perturb the heat-and-mass balance.  Returns (w, y).

    IMPLICIT Euler, unlike the explicit sol_advance upstream, and it has to be.  The trace species
    here are violently stiff: 328C004 holds 1436 kg of liquid at 1 ppm ammonia -- 1.4 GRAMS of NH3 --
    while 330 kg/h flows through it.  Its ammonia time constant is ~0.015 s against a 0.25 s tick, so
    explicit Euler overshoots by ~16x, slams into the non-negativity clamp, and walks the whole
    desorption train off its design point (328C002 ammonia crept 0.63 % -> 2.2 % over four hours).
    The removal term is LINEAR in w_k once the summation denominator is lagged one tick --
    y_k = (alpha_k / SUM_j alpha_j w_j) * w_k -- so the implicit step is closed-form, needs no
    iteration, is unconditionally stable, cannot go negative, and is EXACTLY stationary when
    src == sink*m_k.  That last property is what makes the design point a genuine fixed point."""
    den = sum(alpha.get(k, 0.0) * w.get(k, 0.0) for k in SOL_SPECIES)
    c = ({k: alpha.get(k, 0.0) / den for k in SOL_SPECIES} if den > 1e-15
         else {k: 0.0 for k in SOL_SPECIES})           # y_k = c_k * w_k
    M = max(M_new, 1.0)
    h = dt / 3600.0
    out = {}
    for k in SOL_SPECIES:
        f_in = 0.0
        for w_f, m_f in feeds:
            f_in += m_f * w_f.get(k, 0.0)
        src  = f_in + DES_HYD_NU.get(k, 0.0) * xi              # kg/h into the liquid
        sink = (m_vap * c[k] + m_liq) / M                      # 1/h, coefficient on m_k
        out[k] = max((M * w.get(k, 0.0) + src * h) / (1.0 + sink * h), 0.0)
    tot = sum(out.values())
    if tot <= 1e-12:
        return dict(w), sol_vapour_y(w, alpha)
    w_new = {k: out[k] / tot for k in SOL_SPECIES}     # C6: renormalise to Sum w == 1
    return w_new, sol_vapour_y(w_new, alpha)


# kg per kmol of urea hydrolysed:  NH2CONH2 + H2O -> 2 NH3 + CO2
# CO2 is written as the CLOSER rather than as its own molar mass.  MW_SOL rounds NH3 to 17.0304
# where the reaction needs 17.0307, so the literal coefficients leave 6e-4 kg/kmol unbalanced --
# 0.0026 kg/h at the design extent.  Physically nothing; but CLAUDE.md §1 says 100 % conservation of
# mass, and a stoichiometry vector that does not sum to zero is a mass source no matter how small.
DES_HYD_NU = {"Urea": -MW_SOL["Urea"], "H2O": -MW_SOL["H2O"], "NH3": 2.0 * MW_SOL["NH3"]}
DES_HYD_NU["CO2"] = -(DES_HYD_NU["Urea"] + DES_HYD_NU["H2O"] + DES_HYD_NU["NH3"])

# ---- AUDIT F-7 / TD-008: 328C003 hydrolyser reaction extent -----------------------------------
# NH2CONH2 + H2O -> 2 NH3 + CO2 is the entire purpose of 328C003, and the engine modelled it as a
# frozen overhead split `gen748 = R328_C003_PHI748 * in_c003` with the endotherm buried in the
# back-solved latent R328_C003_LAM748.  No extent, no rate, no residence-time dependence: raising
# the MP steam or cutting the feed changed nothing about how much urea was actually destroyed, and
# the only place the rate law existed was the READ-ONLY soft sensor ppm_infer_328701.
#
# 328C003 is a trayed column, so it is PLUG FLOW, not a CSTR -- which is the only way the PFD's
# 0.82 % inlet -> 1 ppm outlet is reachable.  A CSTR at k.tau = 10.14 converts 91 %; plug flow
# converts 1 - exp(-10.14) = 99.996 %.  Residence time scales inversely with throughput, so:
#
#     tau_live = tau_des * (m_746_des / m_746)
#     X        = 1 - exp(-k(T) * tau_live)                     first-order in urea
#     xi       = (m_746 * w_urea) / MW_urea * X                kmol/h destroyed
#
# The 812 kg/h overhead then decomposes into what the reaction actually makes and what the MP steam
# strips, instead of being one opaque split fraction:
#     gen748 = xi * (2*MW_NH3 + MW_CO2)  +  gas_strip_des * (m_911 / m_911_des)
# Both terms are exactly their design value at the seed, so gen748 == R328_C003_M748_DES bit-exact
# and the 328C003 pressure ODE stays stationary.
# AUDIT F-8: this was hardcoded 0.0082 -- stream 738's urea, not stream 746's.  328C002 dilutes the
# 31 114 kg/h feed into 33 769 kg/h of bottoms, so the PFD tabulates 743/746 at 0.76 %, and the
# hydrolyser was being handed 276.9 kg/h of urea instead of 256.6 (+7.9 %).  Now taken from the one
# place the composition lives, so the two cannot drift apart again.
R328_C003_W_UREA_746 = W_S743["Urea"]   # PFD: urea mass fraction in the desorber-I bottoms (746)
R328_C003_UREA_DES   = R328_C003_M746_DES * R328_C003_W_UREA_746        # 276.9 kg/h urea to hydrolyse
R328_C003_RHO_746_KGM3 = 908.5                  # PFD-22 stream 746 density at 190 C / 14.7 bar a
R328_HYD_K_LN_A = 21.8                          # Inoue & Otsuka (1973), Eq. (6)
R328_HYD_K_B_K = 11_100.0                       # K, Inoue & Otsuka (1973), Eq. (6)


def urea_hydrolysis_k_m3_kmol_h(T_c: float) -> float:
    """Second-order liquid rate constant from Inoue/Otsuka Eq. (6).

    ``ln(k_H) = 21.8 - 11100/T`` with T in kelvin.  The paper reports k in L/(mol h),
    numerically identical to m3/(kmol h), for ``Urea + H2O -> 2 NH3 + CO2``.
    """
    return math.exp(R328_HYD_K_LN_A - R328_HYD_K_B_K / (T_c + 273.15))


def hydrolysis_x_328c003(T_c: float, m_746: float,
                         w_urea: float = R328_C003_W_UREA_746,
                         w_h2o: float = W_S743["H2O"],
                         rho_kgm3: float = R328_C003_RHO_746_KGM3) -> float:
    """Second-order PFR conversion for the nearly liquid-filled 328C003 hydrolyser.

    Rate law: ``dX/dt = k (U0-X)(H0-X)``.  The analytical integral is used, with
    concentrations from the live mass fractions and the PFD stream-746 density.  Residence time
    scales inversely with live liquid throughput.  No pseudo-first-order fit to the 1 ppm product
    guarantee remains.
    """
    u0 = max(rho_kgm3 * w_urea / MW_SOL["Urea"], 0.0)  # kmol/m3
    h0 = max(rho_kgm3 * w_h2o / MW_SOL["H2O"], 0.0)    # kmol/m3
    if u0 <= 0.0 or h0 <= 0.0:
        return 0.0
    tau_h = (R328_AI701_TAU_S / 3600.0) * (R328_C003_M746_DES / max(m_746, 1e-6))
    k_h = urea_hydrolysis_k_m3_kmol_h(T_c)
    delta = h0 - u0
    if abs(delta) <= 1e-12:
        conversion = k_h * u0 * tau_h / (1.0 + k_h * u0 * tau_h)
    else:
        # Stable form of X/U0 = H0(1-exp[-k(H0-U0)t])/(H0-U0 exp[...]).
        e_minus = math.exp(max(-k_h * delta * tau_h, -700.0))
        conversion = h0 * (1.0 - e_minus) / (h0 - u0 * e_minus)
    return max(0.0, min(1.0, conversion))


R328_C003_X_DES      = hydrolysis_x_328c003(R328_C003_T, R328_C003_M746_DES)
R328_C003_XI_DES     = R328_C003_UREA_DES / MW_SOL["Urea"] * R328_C003_X_DES
R328_HYD_GAS_MW      = 2.0 * MW_SOL["NH3"] + MW_SOL["CO2"]              # 78.0706 kg gas per kmol urea
R328_C003_GASHYD_DES = R328_C003_XI_DES * R328_HYD_GAS_MW
R328_C003_GASSTR_DES = R328_C003_M748_DES - R328_C003_GASHYD_DES

# Helwan Fundamentals pp. 1-2: carbamate formation = -117 kJ/mol and dehydration to urea =
# +15.5 kJ/mol.  Their sum is -101.5 kJ/mol for urea formation, hence +101.5 kJ/mol for hydrolysis.
R328_HYD_DH_KJMOL = 101.5
R328_C003_QHYD_DES_KW = R328_C003_XI_DES * R328_HYD_DH_KJMOL * 1000.0 / 3600.0
# Remove the same design heat from the old back-solved overhead lambda.  Adding the explicit
# extent*dH term below therefore preserves the published design temperature exactly.
R328_C003_LAM748 -= R328_C003_QHYD_DES_KW / (R328_C003_M748_DES / 3600.0)


def sol_pin_strength(w: dict, w_urea_auth: float) -> dict:
    """RETIRED (G3). Component-conserving pass-through -- no overwrite.

    This used to overwrite the species urea/water pair onto the mass-energy strength each tick to stop
    the melt strength creeping off its anchor under the 2-dp PFD rounding across 324E001/E003. That
    creep was a symptom of the tabulated 324 melt rows being mutually inconsistent with their feed (the
    proven G3 gross error). Now that the design anchor rows are RECONCILED to atom-consistency
    (`_reconcile_melt`, so `_sol_stage_anchor` clips nothing and the species melt strength already
    equals the mass-energy strength at design), the reconciliation term is an identity and is removed:
    the species layer runs on the conservative `sol_advance` holdup ODE alone, with no component
    overwrite. `w_urea_auth` is retained in the signature for call-site compatibility but unused."""
    return dict(w)
R324_F003_EJPULL_DES = 584.0                         # kg/h PFD stream 712, gas leaving 324E005
R324_HIC9606_DES_PCT = 50.0       # % HIC-329606 design opening (HV-329606 motive steam -> 324F004/F005 ejectors)
R324_F004_MOTIVE_DES = 1220.0     # kg/h PFD stream 927, first deep-vacuum ejector motive steam
R324_F005_MOTIVE_DES = 180.0      # kg/h PFD stream 929, second deep-vacuum ejector motive steam

# --- LIC-324501 routed melt drain (gap G12 operability, approved). LV-324501A level-controls the
#     324F003 drain (LIC-324501 on LT-324501) and EXPORTS the urea melt to Battery Limit (BL) -- a
#     boundary, until the granulation section (335) is simulated. LV-324501B is a NORMALLY-CLOSED
#     overpressure relief that opens only when the 335 melt-header pressure PIC-335201 rises above
#     R335_LVB_RELIEF_BARG, diverting the melt back to 323D002 Compartment I. The route selector sends
#     the same LIC demand to exactly one valve, so total outflow and inventory stay conservative.
R324_LIC501_OP_DES = 75.0
R324_LVA_SPAN      = R324_P2_DES / (R324_LIC501_OP_DES/100.0)   # kg/h at 100 % routed drain stroke
R335_LVB_RELIEF_BARG = 3.8      # PIC-335201 setpoint (bar g) above which LV-324501B opens (approved G12 datum)
R335_PIC201_DES_BARG = 3.5      # design/normal 335 melt-header pressure (bar g); BL boundary input, < relief

# --- PFD-21 finishing boundary: 402G + 697 = 609 on route A -------------------
R324_M402G_PFD     = 85_405.0                        # kg/h raw melt, stream 402G
R324_M697_PFD      = 694.0                           # kg/h UF85, stream 697
R324_M609_PFD      = 86_100.0                        # kg/h mixed forward melt, stream 609 (1 kg/h table rounding)
R324_UF_RATIO      = R324_M697_PFD / R324_M402G_PFD # UF85/raw-melt ratio; DCS source FQI-335401
R324_UF85_RHO      = 1305.0                          # kg/m3 UF85 40 C (PFD stream 697; 1320 was the 335PD05 xmtr SG-cal, not the stream density)
R324_M_UF_DES      = R324_M697_PFD                    # design UF85 injection (kg/h)
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
    m_suc    = capacity                        # actual entrainment = capacity (no head multiplier)
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


def steam_chest_pressure(valve_open_pct: float, header_pressure_bara: float) -> float:
    """Valve-position chest pressure driven by the connected live header."""

    return clamp(
        valve_open_pct / 100.0 * header_pressure_bara,
        0.02,
        header_pressure_bara,
    )


def gravity_outflow_323f010(holdup_kg: float) -> float:
    """Design-anchored gravity drain from 323F010 [kg/h]."""

    return R323_M317_DES * math.sqrt(max(holdup_kg / R323_F010_M_DES, 0.0))


def redistribute_communicating_compartments(masses_kg, temperatures_c, full_masses_kg):
    """Equalize three communicating liquid heads without creating mass or sensible energy.

    Compartments I and II are the active process bays and compartment III is the common
    accumulation baffle. Transfers are routed through III at the donor temperature. This is the
    parameter-free reduced model supported by the approved openings; an orifice model would require
    opening geometry and elevations that are not available.
    """
    if not (len(masses_kg) == len(temperatures_c) == len(full_masses_kg) == 3):
        raise ValueError("the 328D003 communicating model requires exactly three compartments")
    if any(not math.isfinite(value) for value in (*masses_kg, *temperatures_c, *full_masses_kg)):
        raise ValueError("compartment inventory inputs must be finite")
    if any(mass < 0.0 for mass in masses_kg):
        raise ValueError("compartment masses cannot be negative")
    if any(full <= 0.0 for full in full_masses_kg):
        raise ValueError("compartment full masses must be positive")

    total_mass = sum(masses_kg)
    if total_mass == 0.0:
        return tuple(0.0 for _ in masses_kg), tuple(temperatures_c)

    common_level = total_mass / sum(full_masses_kg)
    target_masses = tuple(common_level * full for full in full_masses_kg)
    energies = [mass * temp for mass, temp in zip(masses_kg, temperatures_c)]
    buffer_mass = masses_kg[2]
    buffer_energy = energies[2]

    # Every active-bay transfer crosses the shared compartment-III boundary. Mix all active-bay
    # donors into III first, then supply receivers from that mixed buffer. The order prevents an
    # almost-empty buffer from exporting more liquid at its old temperature than it initially held.
    deltas = tuple(target_masses[index] - masses_kg[index] for index in (0, 1))
    for index, delta in enumerate(deltas):
        if delta < 0.0:
            donated_mass = -delta
            donated_energy = donated_mass * temperatures_c[index]
            energies[index] -= donated_energy
            buffer_mass += donated_mass
            buffer_energy += donated_energy

    buffer_temperature = buffer_energy / buffer_mass if buffer_mass > 0.0 else temperatures_c[2]
    for index, delta in enumerate(deltas):
        if delta > 0.0:
            received_energy = delta * buffer_temperature
            energies[index] += received_energy
            buffer_mass -= delta
            buffer_energy -= received_energy
    energies[2] = buffer_energy

    target_temperatures = tuple(
        energy / mass if mass > 0.0 else temperatures_c[index]
        for index, (energy, mass) in enumerate(zip(energies, target_masses))
    )
    return target_masses, target_temperatures


def d003_level_telemetry(s):
    """Map calculated compartment levels to the approved open-loop LT assignments."""
    level_i = round(s.a328_d003_MI / A328_D003_MI_FULL * 100.0, 1)
    level_ii = round(s.a328_d003_MII / A328_D003_MII_FULL * 100.0, 1)
    level_iii = round(s.a328_d003_MIII / A328_D003_MIII_FULL * 100.0, 1)
    return {
        "LI_328I": level_i,
        "LI_328II": level_ii,
        "LI_328III": level_iii,
        "LT_328507_open_loop": level_i,
        "LT_328508_open_loop": level_ii,
    }


def lmtd_countercurrent(hot_in_c, hot_out_c, cold_in_c, cold_out_c):
    """Counter-current log-mean temperature difference with pinch guards."""
    dt_hot_end = hot_in_c - cold_out_c
    dt_cold_end = hot_out_c - cold_in_c
    if dt_hot_end <= 0.0 or dt_cold_end <= 0.0:
        return 0.0
    if math.isclose(dt_hot_end, dt_cold_end, rel_tol=0.0, abs_tol=1e-12):
        return 0.5 * (dt_hot_end + dt_cold_end)
    return (dt_hot_end - dt_cold_end) / math.log(dt_hot_end / dt_cold_end)


# PFD-28 cooling-water heat capacity back-solved from the largest, best-resolved node:
# 324E002, 18.46 MW = 1591 t/h * Cp * (40-30) K.  The other three mapped duties round
# to 1.93, 1.21, and 0.13 MW with the same Cp.
CW_CP_KJKG_K = 18_460.0 * 3600.0 / (1_591_000.0 * 10.0)


def _vacuum_condenser_spec(tag, inlet, condensate, vent, hot_in, hot_out,
                           cw_flow, cw_in, cw_out, area, tubes, length_mm,
                           shell_id_mm, tube_od_mm, tube_wall_mm):
    q_kw = cw_flow / 3600.0 * CW_CP_KJKG_K * (cw_out - cw_in)
    lmtd_k = lmtd_countercurrent(hot_in, hot_out, cw_in, cw_out)
    return {
        "tag": tag,
        "inlet_kgh": inlet,
        "condensate_kgh": condensate,
        "vent_kgh": vent,
        "hot_in_c": hot_in,
        "hot_out_c": hot_out,
        "cw_flow_kgh": cw_flow,
        "cw_in_c": cw_in,
        "cw_out_c": cw_out,
        "q_kw": q_kw,
        "lmtd_k": lmtd_k,
        "ua_kw_k": q_kw / lmtd_k,
        "h_eff_kjkg": q_kw * 3600.0 / condensate,
        "area_m2": area,
        "tube_count": tubes,
        "tube_length_mm": length_mm,
        "shell_id_mm": shell_id_mm,
        "tube_od_mm": tube_od_mm,
        "tube_wall_mm": tube_wall_mm,
    }


# Operating flows and temperatures are PFD-21/28 anchors.  Geometry is transcribed from
# the four supplied equipment datasheets.  324E006/E007 have no vendor process case, so no
# process value is inferred from their blank sheets.
VACUUM_CONDENSERS = {
    "324E002": _vacuum_condenser_spec(
        "324E002", 26840.0, 26768.0, 72.0, 116.0, 45.0,
        1_591_000.0, 30.0, 40.0, 1079.0, 2329, 5900.0, 1850.0, 25.0, 1.6,
    ),
    "324E005": _vacuum_condenser_spec(
        "324E005", 3342.0, 2758.0, 584.0, 140.0, 40.0,
        415_000.0, 30.0, 34.0, 187.0, 486, 4900.0, 925.0, 25.0, 1.6,
    ),
    "324E006": _vacuum_condenser_spec(
        "324E006", 1804.0, 1763.0, 41.0, 104.0, 41.0,
        208_000.0, 30.0, 35.0, 56.5, 250, 3600.0, 550.0, 20.0, 2.0,
    ),
    "324E007": _vacuum_condenser_spec(
        "324E007", 221.0, 190.0, 31.0, 120.0, 55.0,
        23_000.0, 30.0, 35.0, 11.0, 70, 2500.0, 324.0, 20.0, 2.0,
    ),
}

# PFD-20/21 mass-percent rows for the mapped absorber and vacuum-train streams.
# make_stream_mass_pct normalizes independently rounded rows to preserve the stated stream total.
PFD_324_MASS_PCT = {
    "204": {"CH4": 5.93, "CO2": 2.22, "H2": 3.14, "H2O": 0.26,
            "N2": 68.81, "NH3": 8.26, "O2": 11.39},
    "341": {"CO2": 1.17, "H2O": 8.21, "N2": 68.04, "NH3": 5.05, "O2": 17.53},
    "343": {"CO2": 3.71, "H2O": 90.24, "NH3": 5.23, "Urea": 0.82},
    "702": {"CO2": 0.14, "H2O": 6.35, "N2": 3.30, "NH3": 89.40, "O2": 0.81},
    "703": {"CO2": 1.47, "H2O": 93.78, "N2": 0.08, "NH3": 4.45, "O2": 0.02, "Urea": 0.20},
    "705": {"CO2": 0.82, "H2O": 96.77, "N2": 0.07, "NH3": 2.07, "O2": 0.02, "Urea": 0.25},
    "706": {"CO2": 3.81, "H2O": 29.39, "N2": 38.64, "NH3": 17.91, "O2": 10.26},
    "708": {"CO2": 0.46, "H2O": 91.45, "N2": 4.68, "NH3": 2.17, "O2": 1.24},
    "709": {"CO2": 3.54, "H2O": 87.58, "N2": 0.33, "NH3": 7.48, "O2": 0.09, "Urea": 0.98},
    "712": {"CO2": 13.59, "H2O": 57.87, "N2": 2.14, "NH3": 25.84, "O2": 0.57},
    "714": {"CO2": 3.88, "H2O": 87.98, "N2": 0.61, "NH3": 7.37, "O2": 0.16},
    "715": {"CO2": 17.22, "H2O": 21.22, "N2": 39.48, "NH3": 11.63, "O2": 10.45},
    "717": {"CO2": 2.22, "H2O": 89.93, "N2": 5.05, "NH3": 1.49, "O2": 1.34},
    "719": {"CO2": 3.50, "H2O": 91.75, "NH3": 4.08, "Urea": 0.66},
    "720": {"CO2": 3.92, "H2O": 88.73, "NH3": 3.68, "Urea": 3.68},
    "721": {"CO2": 8.54, "H2O": 84.87, "NH3": 6.59},
    "722": {"CO2": 14.33, "H2O": 15.15, "N2": 54.44, "NH3": 1.66, "O2": 14.42},
    "744": {"CO2": 0.11, "H2O": 98.50, "NH3": 0.63, "Urea": 0.76},
    "755": {"CO2": 3.81, "H2O": 91.13, "NH3": 4.17, "Urea": 0.89},
    "756": {"CO2": 3.79, "H2O": 91.18, "NH3": 4.20, "Urea": 0.84},
    "759": {"CO2": 2.27, "H2O": 96.31, "NH3": 1.42},
    "783": {"N2": 79.06, "O2": 20.94},
    "784": {"N2": 79.06, "O2": 20.94},
    "790": {"CO2": 2.29, "H2O": 90.04, "N2": 0.09, "NH3": 7.41, "O2": 0.02, "Urea": 0.14},
    "797": {"CH4": 6.47, "CO2": 0.05, "H2": 3.43, "H2O": 2.28,
            "N2": 75.15, "NH3": 0.18, "O2": 12.44},
}


def vacuum_condenser_node(spec, inlet_kgh, noncondensable_kgh, hot_in_c,
                          cw_flow_kgh=None, cw_in_c=None):
    """Reduced condenser node, anchored exactly to its PFD design point.

    The design UA already contains the design gas-film resistance.  Above the design
    noncondensable fraction, UA is derated by the remaining condensable fraction.  This
    supplies the source-backed direction of effect without inventing a fitted coefficient.
    """
    cw_flow = spec["cw_flow_kgh"] if cw_flow_kgh is None else max(cw_flow_kgh, 0.0)
    cw_in = spec["cw_in_c"] if cw_in_c is None else cw_in_c
    inlet = max(inlet_kgh, 0.0)
    nc = clamp(noncondensable_kgh, 0.0, inlet)

    if (inlet == spec["inlet_kgh"] and nc == spec["vent_kgh"]
            and hot_in_c == spec["hot_in_c"] and cw_flow == spec["cw_flow_kgh"]
            and cw_in == spec["cw_in_c"]):
        return {
            "tag": spec["tag"], "inlet_kgh": inlet,
            "condensate_kgh": spec["condensate_kgh"], "vent_kgh": spec["vent_kgh"],
            "q_kw": spec["q_kw"], "lmtd_k": spec["lmtd_k"],
            "ua_kw_k": spec["ua_kw_k"], "ua_eff_kw_k": spec["ua_kw_k"],
            "cw_flow_kgh": cw_flow, "cw_in_c": cw_in, "cw_out_c": spec["cw_out_c"],
            "hot_in_c": hot_in_c, "hot_out_c": spec["hot_out_c"],
            "mass_residual_kgh": 0.0, "energy_residual_kw": 0.0,
        }

    if inlet <= 0.0 or cw_flow <= 0.0:
        return {
            "tag": spec["tag"], "inlet_kgh": inlet,
            "condensate_kgh": 0.0, "vent_kgh": inlet,
            "q_kw": 0.0, "lmtd_k": 0.0, "ua_kw_k": spec["ua_kw_k"],
            "ua_eff_kw_k": 0.0, "cw_flow_kgh": cw_flow,
            "cw_in_c": cw_in, "cw_out_c": cw_in, "hot_in_c": hot_in_c,
            "hot_out_c": hot_in_c, "mass_residual_kgh": 0.0,
            "energy_residual_kw": 0.0,
        }

    x_nc = nc / inlet
    x_nc_des = spec["vent_kgh"] / spec["inlet_kgh"]
    condensable_ratio = clamp((1.0 - x_nc) / max(1.0 - x_nc_des, 1e-12), 0.0, 1.0)
    ua_eff = spec["ua_kw_k"] * condensable_ratio
    hot_out = spec["hot_out_c"] + (hot_in_c - spec["hot_in_c"])
    q_kw = spec["q_kw"] * min(cw_flow / spec["cw_flow_kgh"], inlet / spec["inlet_kgh"])
    lmtd_k = 0.0
    for _ in range(30):
        cw_out = cw_in + q_kw * 3600.0 / (cw_flow * CW_CP_KJKG_K)
        lmtd_k = lmtd_countercurrent(hot_in_c, hot_out, cw_in, cw_out)
        q_cap = max(ua_eff * lmtd_k, 0.0)
        cond = min(max(inlet - nc, 0.0), q_cap * 3600.0 / spec["h_eff_kjkg"])
        q_next = cond * spec["h_eff_kjkg"] / 3600.0
        if abs(q_next - q_kw) <= 1e-10:
            q_kw = q_next
            break
        q_kw = 0.5 * (q_kw + q_next)
    condensate = min(max(inlet - nc, 0.0), q_kw * 3600.0 / spec["h_eff_kjkg"])
    vent = inlet - condensate
    cw_out = cw_in + q_kw * 3600.0 / (cw_flow * CW_CP_KJKG_K)
    return {
        "tag": spec["tag"], "inlet_kgh": inlet,
        "condensate_kgh": condensate, "vent_kgh": vent,
        "q_kw": q_kw, "lmtd_k": lmtd_k, "ua_kw_k": spec["ua_kw_k"],
        "ua_eff_kw_k": ua_eff, "cw_flow_kgh": cw_flow,
        "cw_in_c": cw_in, "cw_out_c": cw_out, "hot_in_c": hot_in_c,
        "hot_out_c": hot_out, "mass_residual_kgh": inlet - condensate - vent,
        "energy_residual_kw": q_kw - cw_flow / 3600.0 * CW_CP_KJKG_K * (cw_out - cw_in),
    }


def vacuum_train_324(m_evap_kgh, vapour1_kgh, vapour2_kgh, false_air1_kgh,
                     false_air2_kgh, motive924_kgh, motive927_kgh, motive929_kgh,
                     cw_factors=None):
    """Four condensers and three ejector mixing nodes on the PFD-21 basis."""
    cw_factors = cw_factors or {}
    streams = {
        "705": 14799.0 + (vapour1_kgh - R324_V1_DES) + (false_air1_kgh - R324_F001_FA_DES),
        "790": 12040.0 + (m_evap_kgh - R323_MEVAP_DES),
        "709": 3342.0 + (vapour2_kgh - R324_V2_DES) + (false_air2_kgh - R324_F003_FA_DES),
        "924": motive924_kgh, "927": motive927_kgh, "929": motive929_kgh,
    }
    streams["703"] = 26840.0 + (streams["705"] - 14799.0) + (streams["790"] - 12040.0)
    e002 = vacuum_condenser_node(
        VACUUM_CONDENSERS["324E002"], streams["703"],
        max(72.0 - R324_F001_FA_DES + false_air1_kgh, 0.0), 116.0,
        VACUUM_CONDENSERS["324E002"]["cw_flow_kgh"] * cw_factors.get("324E002", 1.0),
    )
    streams["719"], streams["706"] = e002["condensate_kgh"], e002["vent_kgh"]
    streams["708"] = streams["706"] + streams["924"]

    e005 = vacuum_condenser_node(
        VACUUM_CONDENSERS["324E005"], streams["709"],
        max(584.0 - R324_F003_FA_DES + false_air2_kgh, 0.0), 140.0,
        VACUUM_CONDENSERS["324E005"]["cw_flow_kgh"] * cw_factors.get("324E005", 1.0),
    )
    streams["720"], streams["712"] = e005["condensate_kgh"], e005["vent_kgh"]
    streams["714"] = streams["712"] + streams["927"]

    e006 = vacuum_condenser_node(
        VACUUM_CONDENSERS["324E006"], streams["714"],
        41.0 + max(streams["712"] - 584.0, 0.0), 104.0,
        VACUUM_CONDENSERS["324E006"]["cw_flow_kgh"] * cw_factors.get("324E006", 1.0),
    )
    streams["721"], streams["715"] = e006["condensate_kgh"], e006["vent_kgh"]
    streams["717"] = streams["715"] + streams["929"]

    e007 = vacuum_condenser_node(
        VACUUM_CONDENSERS["324E007"], streams["717"],
        31.0 + max(streams["715"] - 41.0, 0.0), 120.0,
        VACUUM_CONDENSERS["324E007"]["cw_flow_kgh"] * cw_factors.get("324E007", 1.0),
    )
    streams["759"], streams["722"] = e007["condensate_kgh"], e007["vent_kgh"]
    return {"streams_kgh": streams,
            "nodes": {"324E002": e002, "324E005": e005, "324E006": e006, "324E007": e007},
            "mixing_residual_703_kgh": streams["703"] - streams["705"] - streams["790"]}


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


def stripper_322e001(co2_feed_th: float, T_steam_C: float, P_bara: float,
                     overflow_kmolh: dict = None, L_feed: float = None,
                     W_feed: float = None, T_feed_C: float = None) -> dict:
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
    if T_feed_C is None:
        T_feed_C = STRIP_FEED207_T_C                  # design reactor-overflow T (TT-322014)
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
    # HYDRODYNAMIC FLOODING (TD-006).  Everything above is a THERMAL response -- it asks whether the
    # shell steam can keep up with the liquid.  This asks a different and independent question: can the
    # tube physically carry the film at all?  Once the rising gas core shears the descending film off
    # the wall the film thickens, liquid is dragged upward, and stripping stops regardless of how much
    # steam is available.  Licensor DDS geometry + the IFS-166 limit (see the constant block):
    #     flood_frac = ṁ_feed / N_tubes / 145 kg/h      = 0.7448 at design (108.0 of 145 kg/h per tube)
    # flood_x is the EXCESS over the limit and is EXACTLY 0.0 at design because max() returns the
    # literal 0.0 for any negative argument -- 0.7448 − 1.0 < 0.  Every term below is therefore an
    # exact identity at the seed (1 − e^0 = 0.0 ; 1/(1 + K·0.0) = 1.0), so the pin cannot move.
    flood_frac = m_feed_kgh / STRIP_N_TUBES / STRIP_FLOOD_KGH_TUBE
    flood_x    = max(flood_frac - 1.0, 0.0)                       # 0.0 at design, exactly
    # Flooded tubes hold un-decomposed carbamate and hot reactor liquor falls through untouched, so the
    # BOTTOM RUNS HOTTER -- Brouwer's 3-4 °C signature -- capped by the same 183 °C reactor-liquor
    # ceiling the steam-dilution branch already asymptotes to.
    dT_flood   = strip_flood_gap * (1.0 - math.exp(-STRIP_FLOOD_T_K * flood_x))   # 0.0 at design
    dT_bot     = dT_bot + dT_flood                                # + 0.0 is bit-exact
    # ...and the split CLOSES: the volatiles stay in the bottoms and slip to the LP section via
    # LV-322501, which is exactly the cascade Brouwer describes (more NH3 in the bottoms -> more gas
    # to LP recirculation -> LP pressure rises -> operators must cut load).  g_flood itself is
    # DERIVED from dT_flood by the carbamate energy balance and is computed below, once `avail`
    # is known -- see the STRIP_FLOOD_ETA_FLOOR block for the derivation.
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
    # TT-322013 overhead: hoisted out of the return dict because the enthalpy balance below needs it.
    T_top_C = min(STRIP_T_TOPGAS_DES_C + 0.6 * dTs
                  + STRIP_T_TOP_LOAD_K * dT_bot + dT_strip, T_steam_C)
    xi_hyd_raw = STRIP_XI_HYD_DES * eta_T
    xi_hyd = max(min(xi_hyd_raw, feed["Urea"], feed["H2O"]), 0.0)
    urea_after_hyd = max(feed["Urea"] - xi_hyd, 0.0)
    xi_biu_raw = (STRIP_XI_BIU_DES
                  * math.exp((STRIP_BIU_EA / STRIP_R_GAS_J) * (1.0 / STRIP_T_BIU_DES_K - 1.0 / T_bot_K))
                  * (feed["Urea"] / STRIP_UREA0))                       # 0.667 at design (ratio=1)
    xi_biu = max(min(xi_biu_raw, 0.5 * urea_after_hyd), 0.0)
    avail = dict(feed)
    avail["Urea"]   -= (xi_hyd + 2.0 * xi_biu)
    avail["Biuret"] += xi_biu
    avail["NH3"]    += (2.0 * xi_hyd + xi_biu)
    avail["CO2"]    += xi_hyd
    avail["H2O"]    -= xi_hyd

    # 3b. HYDRODYNAMIC EFFICIENCY KNOCKDOWN, derived from the bottom-temperature rise.
    #     The heat that dT_flood carries away as sensible warming is exactly the heat that did NOT
    #     go into dissociating carbamate, so the lost stripping fraction is that deficit measured
    #     against the carbamate endotherm the feed could have supplied.  n_carb_avail is taken from
    #     `avail` (pre-split) MINUS the CO2 sweep, which arrives already as gas and needs no
    #     dissociation heat -- so there is no circular dependence on the split this drives.
    #     At design dT_flood is exactly 0.0, hence g_flood is exactly 1.0.
    n_carb_avail = max(avail["CO2"] - co2_kmolh["CO2"], 1e-9)          # kmol/h liquid-borne CO2
    q_carb_avail = n_carb_avail * STRIP_DH_CARB_JMOL                   # kJ/h  (kmol/h * J/mol)
    q_flood_def  = m_feed_kgh * STRIP_CP_BOTTOM * dT_flood             # kJ/h, 0.0 at design
    g_flood      = clamp(1.0 - q_flood_def / q_carb_avail, STRIP_FLOOD_ETA_FLOOR, 1.0)

    # 4. strip-fraction modulation: thermal steam heat x CO2 strip-gas dilution x synthesis-pressure
    #    (=1.0 at design).  The N/C+H/C choke does NOT cut the thermal split; instead it forces
    #    volatile NH3/CO2 BREAKTHROUGH to the overhead (slip), raising the vapour load back to HPCC.
    eta_co2 = clamp(0.5 + 0.5 * co2_scale, 0.4, 1.05)
    eta_P   = clamp(2.0 - P_bara / STRIP_P_DES_BARA, 0.85, 1.15)
    # Feed-load (flood) choke g_T<1 CUTS the split -- steam-limited stripping leaves the volatiles in
    # the BOTTOMS (NH3 slip to LP via LV-322501), it does NOT lift them overhead.  min(g_T,1) keeps the
    # feed-lean branch (g_T>1, already rewarded through eta_T) and the design point (g_T=1) bit-exact.
    # g_flood multiplies the SPLIT only, never eta_T.  eta_T drives xi_hyd, and flooding does not
    # suppress hydrolysis -- Brouwer is explicit that a flooded tube's liquid residence time INCREASES
    # ("stagnation or upward dragging of the film"), so hydrolysis and biuret go UP, not down.  That
    # rise is already carried, without a new term: dT_flood raises T_bot, and xi_biu is Arrhenius in
    # T_bot_K.  Folding g_flood into eta_T would have cut hydrolysis, i.e. the wrong sign.
    mod = clamp(eta_T_steam * eta_co2 * eta_P, 0.0, 1.12) * min(g_T, 1.0) * g_flood
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

    # 6. PER-SPECIES ENTHALPY BALANCE (TD-006 second half).  Five terms, every constant sourced --
    #    see the STRIP_DH_CARB_JMOL block.  This is what the MP-steam header actually has to pay
    #    for, and unlike the feed-proportional stand-in it responds to COMPOSITION: a feed that is
    #    richer in carbamate costs more steam at the same tonnage.
    #      q_carb  carbamate dissociation, the dominant sink (~58 % of design duty)
    #      q_nh3   desorption of the NH3 that was NOT carbamate-bound (supercritical: no latent)
    #      q_h2o   the small water fraction that vaporises overhead (~7 %)
    #      q_hyd   urea hydrolysis, liquid step only -- NEGATIVE, it gives a little heat back
    #      q_sens  sensible heat of the two products relative to the feed temperature
    #    T_feed_C defaults to the design reactor-overflow temperature; the caller passes the live
    #    one so a hotter reactor genuinely reduces the stripper's steam demand.
    n_co2_desorb = max(top["CO2"] - co2_kmolh["CO2"], 0.0)             # kmol/h out of the liquid
    n_nh3_free   = max(top["NH3"] - co2_kmolh["NH3"] - 2.0 * n_co2_desorb, 0.0)   # 2:1 carbamate
    q_carb_kw = n_co2_desorb * STRIP_DH_CARB_JMOL / 3600.0
    q_nh3_kw  = n_nh3_free   * STRIP_DH_NH3_JMOL / 3600.0
    q_h2o_kw  = max(top["H2O"] - co2_kmolh["H2O"], 0.0) * STRIP_LAM_H2O_JMOL / 3600.0
    q_hyd_kw  = xi_hyd * STRIP_DH_HYD_JMOL / 3600.0
    q_sens_kw = (bot_m * STRIP_CP_BOTTOM * (T_bot_C - T_feed_C)
                 + top_m * STRIP_CP_GAS * (T_top_C - T_feed_C)) / 3600.0
    duty_raw_kw = q_carb_kw + q_nh3_kw + q_h2o_kw + q_hyd_kw + q_sens_kw

    return {
        "feed_kmolh": feed, "co2_feed_kmolh": co2_kmolh, "top_kmolh": top, "bot_kmolh": bot,
        "top_kgh": top_m, "bot_kgh": bot_m,
        "top_th": top_m / 1000.0, "bot_th": bot_m / 1000.0,
        "top_mol": top_n, "bot_mol": bot_n,
        "top_MW": (top_m / top_n if top_n else 0.0),
        "bot_MW": (bot_m / bot_n if bot_n else 0.0),
        "top_comp_pct": {k: (top[k] / top_n * 100.0 if top_n else 0.0) for k in MW_COMP},   # mol %
        "bot_mass_pct": {k: (bot_kgh[k] / bot_m * 100.0 if bot_m else 0.0) for k in MW_COMP},# mass %
        "T_top": T_top_C,   # TT-322013: steam-heat + feed-load (atten.) + G/L strip-cool (full); ≤ steam sat
        "T_bot": T_bot_C, "T_feed": T_feed_C,
        "xi_hyd": xi_hyd, "xi_biu": xi_biu, "eta_T": eta_T, "T_steam": T_steam_C,
        "eta_T_steam": eta_T_steam, "g_NC": g_NC, "g_HC": g_HC, "g_T": g_T,
        "dT_load": dT_load, "dT_bot": dT_bot, "dT_strip": dT_strip, "r_GL": r_GL, "m_feed_kgh": m_feed_kgh,  # energy-balance + G/L strip-cool diag
        "L_strip": L_strip, "W_strip": W_strip, "slip": slip,
        # TD-006 hydrodynamic flooding diagnostics (all inert at design: 0.7448 / 0.0 / 1.0 / 0.0)
        "flood_frac": flood_frac, "flood_x": flood_x, "g_flood": g_flood, "dT_flood": dT_flood,
        "flood_kgh_tube": m_feed_kgh / STRIP_N_TUBES,
        # TD-006 per-species enthalpy balance (kW).  duty_raw_kw is used only as a RATIO against
        # its own design value, so its 4 % offset from the licensor duty never reaches the model.
        "duty_raw_kw": duty_raw_kw, "q_carb_kw": q_carb_kw, "q_nh3_kw": q_nh3_kw,
        "q_h2o_kw": q_h2o_kw, "q_hyd_kw": q_hyd_kw, "q_sens_kw": q_sens_kw,
        "n_co2_desorb": n_co2_desorb, "n_nh3_free": n_nh3_free,
    }


# Design-point stripper top-gas molar flow + synthesis-pressure coupling gain (PT-329201).
# Higher steam Tsat -> higher stripping efficiency -> more overhead (off-gas) returned to the
# HP synthesis loop -> higher synthesis pressure (plant reference, carbamate-condenser path).
_STRIP_DES_FULL   = stripper_322e001(CO2_DES_KGH / 1000.0,
                                     STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA)
_STRIP_TOP_DES    = _STRIP_DES_FULL["top_kmolh"]
# Design value of the per-species enthalpy balance (TD-006).  The live duty is scaled by
# duty_raw_kw / STRIP_DUTY_RAW_DES_KW, so this is the denominator that makes the ratio exactly
# 1.0 at design.  It is ~37 831 kW, i.e. 96 % of the licensor STRIP_DUTY_DES_KW; that offset
# CANCELS in the ratio and never reaches the steam header.
STRIP_DUTY_RAW_DES_KW = _STRIP_DES_FULL["duty_raw_kw"]
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
HPCC_STEAM_P_BARA  = 5.01325     # shell-side LP steam pressure (5.01325 bar a == 4.0 barg)
HPCC_STEAM_TSAT_PFD_C = 146.3    # rounded licensor/PFD indicator value retained as provenance
HPCC_STEAM_TSAT_C  = tsat_steam(HPCC_STEAM_P_BARA)  # thermodynamic saturation state used in balances (~152.06 C)
HPCC_DH_CARB_KJMOL = 160.0       # carbamate exotherm 2NH3+CO2->NH2COONH4 (kJ/mol CO2 absorbed)
HPCC_CP_GAS        = 2.0         # mean strip-gas cp for sensible duty (kJ/kg.K)
HPCC_LATENT_4BAR   = 2120.0      # latent heat of 4.4 bar a steam (kJ/kg)
# ---- AUDIT F-6 / TD-007: the split fractions above are a calibration at ONE point --------------
# HPCC_FRAC_GAS_DES was measured at 170 C / 144.2 bar a.  Frozen, it makes the condenser
# thermodynamically INERT: raising the LP-steam pressure changes the shell duty and the NTU outlet
# temperature but not one mole of condensate, and a synthesis-pressure excursion moves nothing at
# all.  _hpcc_flash_split() below binds a real isothermal (T,P) flash on top of the calibration.
#
# Physics.  NH3/CO2 "condensation" here is not physical condensation -- it is the carbamate
# equilibrium   NH2COONH4(l) <-> 2 NH3(g) + CO2(g),  Kp = p_NH3^2 * p_CO2,  whose dissociation
# enthalpy is ~160 kJ/mol == HPCC_DH_CARB_KJMOL (already the exotherm constant).  Because Kp is a
# THIRD-order product, the measured temperature coefficient of the dissociation PRESSURE is one
# third of the reaction enthalpy -- ~12.8 kcal/mol == 53.5 kJ/mol (Bennett 1953; Ramachandran 1998).
# With y_NH3 ~ 2*y_CO2 the gas mole fraction of each partner scales as y_i ~ Kp(T)^(1/3)/P, i.e.
#       K_i(T,P) = K_i,des * exp[(dH/R)(1/T_des - 1/T)] * (P_des/P)
# H2O is ordinary Raoult condensation (its own latent heat, same 1/P).  N2 is a permanent gas held
# by Henry's law -> no temperature slope, still 1/P.  Components whose calibrated split is exactly
# 1 (O2/CH4/H2 -- never condense) or exactly 0 (Urea/Biuret -- never boil) are structurally
# non-distributing and stay OUT of the flash.
HPCC_FLASH_DH = {                # J/mol, Clausius-Clapeyron slope of each distributing K-value
    "CO2": HPCC_DH_CARB_KJMOL * 1000.0 / 3.0,   # carbamate cube-root slope (53 333 J/mol)
    "NH3": HPCC_DH_CARB_KJMOL * 1000.0 / 3.0,
    "H2O": 36900.0,              # 2049 kJ/kg * 18.015 g/mol -- water latent @170 C (steam tables)
    "N2":  0.0,                  # permanent gas: Henry's law, no temperature slope
}
HPCC_FLASH_ITERS = 60            # bisection sweeps on the monotone Rachford-Rice residual (2^-60)

# ===== FT-329403 / FT-329407 steam-transmitter PFD anchors (OEM 1750 MTPD 100% load) =========
#   Refer: References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data (streams 901/902/903/
#   911/963/917/932).  The lumped-capacitance steam model (steam_system.py) resolves ONLY the
#   total strip-steam supply -- at design m_supply == M_STRIP_DES (21.2973 kg/s) and every PFD
#   sub-flow (903/963/letdown/turbine/vent) settles to 0 -- so each transmitter is anchored to
#   its OEM 100%-load branch mass and live-normalized by the in-scope duty that physically drives
#   it (dynamic-vs-static rule: live equipment scales; 335 Granulation futures stay static 0).
#
#   FT-329403 sits on the 25-bar supply main (stream 901) = live BL steam to the four consumers
#     328C003(911) + 329D005(902) + 329D009(903) + 322D001A/B(963):
#       $FT_{329403} = \dot m_{911} + (\Phi_{902}+\Phi_{903})\cdot\frac{\dot m_{supply}}{M_{STRIP,des}} + \Phi_{963}$
#     -> 1105 + (57989+1754)*(21.2973/21.2973) + 0 = 60848 kg/h = 60.85 t/h  (bit-exact @design).
#   902 (329D005 strip condenser) & 903 (329D009 MP drum make-up) are LIVE equipment -> scale with
#   the live strip-steam ratio.  963 (322D001A/B) == 0 at 100% load -> static.
FT403_S902_DES   = 57989.0       # PFD stream 902  BL 25-bar -> 329D005 (dynamic, live strip load)
FT403_S903_DES   = 1754.0        # PFD stream 903  BL 25-bar -> 329D009 MP drum (dynamic, live)
FT403_S963_DES   = 0.0           # PFD stream 963  -> 322D001A/B (static 0 at 100% load)
M_STRIP_DES_KGS  = 39400.0 / 1850.0   # == steam_system.M_STRIP_DES (design strip-steam consumption, kg/s)
#
#   FT-329407 is the actual PV-329207B export from the 4-bar header to turbine 320MT02 (stream 932).
#   G8: the valve now carries the design 4-bar surplus at its anchored bias, so FT-329407 reads the
#   PFD 16 707 kg/h from the CONNECTED valve at design (not a shut-valve reference); the value emerges
#   from the header balance generation == M_USERS_LP + M_TURBINE_DES, not synthesis.
FT407_S932_DES   = 16707.0       # PFD stream 932  excess 4-bar -> PV-329207B -> 320MT02 turbine
M_HPCC_DES_LIVE  = None          # design LP steam-raising anchor (kg/s); set at boot ==
                                 #   M_USERS_LP + steam_system.M_TURBINE_DES == duty_des/HPCC_LATENT_4BAR (~29.774)

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
# The SAME correlation evaluated at the design stream-207 state (34.6 % urea, 183 C).  This -- not the
# raw PFD anchor -- is the datum the Darcy-Weisbach dP to the stripper is normalised by, so the ratio
# is exactly 1.0 at design.  urea_soln_rho() is a departure model about one global C10 reference,
# so it returns its `anchor` argument ONLY at that reference, which stream 207 is far from.
_REACT_OVF_M_DES_KGH   = sum(STRIP_FEED207_KMOLH.get(k, 0.0) * MW_COMP[k] for k in MW_COMP)
_REACT_OVF_W_UREA_DES  = STRIP_FEED207_KMOLH["Urea"] * MW_COMP["Urea"] / _REACT_OVF_M_DES_KGH
REACT_OVERFLOW_RHO_DES_LIVE = urea_soln_rho(_REACT_OVF_W_UREA_DES, STRIP_FEED207_T_C,
                                            REACT_OVERFLOW_RHO)
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
# --- PT-329201 lumped HP-loop mass accumulator: design boundary closure ------------------------
# The loop-pressure ODE at the foot of step_sim() integrates (in - out) over the loop's mass
# capacity.  Its five boundary terms are the model's OWN reconciled design flows, and two of them
# were deliberately moved off their PFD rows: the ejector motive NH3 was re-pinned 40756 ->
# 42762.05 kg/h (Path-B tear closure, to restore fresh N/C = 2.0) and the 322E003 vent vector was
# re-solved to close the SCRUBBER's component balance, which took its total mass from the PFD's
# 1708 kg/h to 5901.4 kg/h.  On the PFD rows the loop closes to 1 kg/h in 132 289
# (54618 + 40756 + 36915 in == 130582 + 1708 out); on the reconciled pins it leaves a CONSTANT
# -2168.1 kg/h that the ODE was integrating as though it were real accumulation.  That is the
# whole of the design-hold drift: PT-329201 bled ~0.30 bar per 600 s, LV-322501's letdown head
# fell with it (drain ~ sqrt(P_syn - P_down)), and the entire 323/324 train walked off its
# anchors -- v305 24.56 -> 24.45 t/h, v701 4.43 -> 4.41, evap 12.01 -> 11.79, TT-323005 106.0 ->
# 105.96, PT-323201 4.10 -> 4.07 over 3000 s, with 323F001/324E001 urea % ramping behind them.
# The residual is credited back in proportion to the live loop-mass fraction -- the same inventory
# gate the stripper forward-push (pb_push) already uses and for the same reason: the reconciliation
# tears ride the CIRCULATING inventory, so a design-full loop holds PT-329201 EXACTLY while an
# empty loop integrates the raw balance and zero feeds still create nothing (G4 null-feed rule).
SCRUB_OFFGAS_KGH_DES   = sum(SCRUB_OFFGAS_KMOLH_DES[k] * MW_COMP[k] for k in MW_COMP)   # 5901.4 kg/h
SYN_LOOP_IN_DES_KGH    = EJ_MOTIVE_NH3_DES + CO2_DES_KGH + R3232_E003_M308_DES      # 134215.2 kg/h
SYN_LOOP_OUT_DES_KGH   = STRIP_BOT_DES_KGH + SCRUB_OFFGAS_KGH_DES                   # 136383.4 kg/h
SYN_LOOP_RESID_DES_KGH = SYN_LOOP_IN_DES_KGH - SYN_LOOP_OUT_DES_KGH                 #  -2168.1 kg/h
SYN_LOOP_C_KG_PER_BAR  = 1500.0  # kg/bar, lumped HP-loop mass capacity (reactor + stripper + HPCC +
#   scrubber vapour space and dissolved-gas compressibility); sets the emergent cold-start
#   pressurisation rate together with k_loop_fill.
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


def _hpcc_flash_split(feed: dict, T_c: float, p_loop: float) -> dict:
    """AUDIT F-6 / TD-007 -- isothermal (T,P) flash of the 322E002 tube-side feed; returns phi_i.

    The calibrated design split HPCC_FRAC_GAS_DES is NOT discarded: K_i,des is back-solved from it
    against the LIVE feed composition every tick, so the activity coefficients of this strongly
    non-ideal electrolyte melt stay baked into the K-values exactly as measured.  Only the DEVIATION
    from the calibration point is model-driven, via the carbamate-equilibrium / Raoult / Henry
    slopes in HPCC_FLASH_DH.  Non-distributing components (phi_des of exactly 0 or 1) are returned
    untouched.  At the calibration point itself the routine short-circuits to the design vector, so
    no Rachford-Rice tolerance can ever reach the boot pin.

    Rachford-Rice is solved by BISECTION, not Newton: g(psi) is strictly decreasing on [0,1], so a
    fixed 60-sweep bracket is exact to 2^-60 with bounded cost and no possible convergence failure.
    An OTS tick must never miss its deadline -- this is the same argument that keeps the flowsheet
    Sequential-Modular (EQUATION_AUDIT Q2)."""
    p_rat = SYN_P_DES_BARA / max(p_loop, 1e-6)
    T_k   = T_c + 273.15
    if p_rat == 1.0 and T_k == _HPCC_BUB_T0_K:
        return dict(HPCC_FRAC_GAS_DES)       # exactly at the calibration point -> phi IS the design
    dist = [k for k in MW_COMP if 0.0 < HPCC_FRAC_GAS_DES.get(k, 0.0) < 1.0]
    f_d  = sum(feed.get(k, 0.0) for k in dist)
    if f_d <= 1e-12:
        return dict(HPCC_FRAC_GAS_DES)       # no distributing feed -> nothing to flash
    z = {k: feed.get(k, 0.0) / f_d for k in dist}
    psi_des = sum(z[k] * HPCC_FRAC_GAS_DES[k] for k in dist)     # split the CALIBRATION would give
    if not (1e-9 < psi_des < 1.0 - 1e-9):
        return dict(HPCC_FRAC_GAS_DES)       # degenerate feed (single phase already) -> hold design
    K = {}
    for k in dist:
        phi_d = HPCC_FRAC_GAS_DES[k]
        k_des = phi_d * (1.0 - psi_des) / (psi_des * (1.0 - phi_d))   # K = (phi/psi)/((1-phi)/(1-psi))
        # .get default 0.0 == Henry (no temperature slope): a distributing species with no listed
        # slope still flashes on pressure rather than raising KeyError if the vector is ever edited.
        K[k]  = max(k_des * math.exp((HPCC_FLASH_DH.get(k, 0.0) / reactor.R_GAS)
                                     * (1.0 / _HPCC_BUB_T0_K - 1.0 / T_k)) * p_rat, 0.0)

    def _g(p):                                # Rachford-Rice residual, strictly decreasing in p
        return sum(z[k] * (K[k] - 1.0) / (1.0 + p * (K[k] - 1.0)) for k in dist)

    lo, hi = 1e-12, 1.0 - 1e-12
    if _g(hi) >= 0.0:      psi = hi           # above the dew point -> everything leaves as gas
    elif _g(lo) <= 0.0:    psi = lo           # below the bubble point -> everything condenses
    else:
        for _ in range(HPCC_FLASH_ITERS):
            mid = 0.5 * (lo + hi)
            if _g(mid) > 0.0: lo = mid
            else:             hi = mid
        psi = 0.5 * (lo + hi)
    out = dict(HPCC_FRAC_GAS_DES)
    for k in dist:
        out[k] = clamp(K[k] * psi / (1.0 + psi * (K[k] - 1.0)), 0.0, 1.0)
    return out


def hpcc_322e002(gas_feed: dict, liq_feed: dict, t_shell: float = HPCC_STEAM_TSAT_C,
                 gate: float = 1.0, t_prod_prev: float = HPCC_T_PROD_DES_C,
                 p_loop: float = SYN_P_DES_BARA, phi_prev: dict = None,
                 dt: float = 0.0) -> dict:
    """HP Carbamate Condenser 322E002 reduced model.
    gas_feed = stripper_322e001() return (top gas -> TT-322013); liq_feed = ejector_322f001()
    return (carbamate liquid -> TT-322012).  Combines both tube-side feeds and condenses NH3/CO2
    into the liquid via calibrated component split fractions (carbamate reaction implicit), then
    returns the two-phase products to 322R001 plus shell-side LP-steam duty.  Reproduces the
    shared gas- and liquid-product HMB exactly at design conditions."""
    # 1. combined tube-side feed (kmol/h per comp): strip gas (kmol/h) + ejector liq (kg/h -> kmol/h)
    feed = {k: gas_feed["top_kmolh"].get(k, 0.0)
               + liq_feed["comp"].get(k, 0.0) / MW_COMP[k] for k in MW_COMP}
    # 2. phase split: phi_i -> gas product, (1-phi_i) -> liquid product.  AUDIT F-6/TD-007: phi is no
    #    longer the frozen calibration -- it is an isothermal (T,P) flash anchored ON that calibration.
    #    T_prod is an OUTPUT of step 4 below, so the split<->temperature algebraic loop is torn with
    #    the PRIOR tick's product temperature (SM discipline; dt=0.25 s << HPCC_T_TAU_S=240 s, and the
    #    coupling is negative-feedback: T^ -> K^ -> phi^ -> less CO2 absorbed -> q_carb v -> T v).
    #    Blended through the Option-1 disturbance gate exactly like T_prod below, so gate==0 (no
    #    operator/feed move) -> phi == HPCC_FRAC_GAS_DES BIT-EXACT and the design HMB is untouched.
    #    The flash is the EQUILIBRIUM TARGET, not the answer.  A pure equilibrium split is far too
    #    stiff for this vessel -- the K-values of the distributing set are tightly clustered, so a
    #    common factor moves the whole mixture together and a +/-10 C excursion alone drives phi_CO2
    #    from 0.001 to 1.0 (probe_322e002_flash.py Phase 0).  That is not how a falling-film
    #    condenser behaves: the reference (References/HPCC description.md, Sections 5.2-5.3) is
    #    explicit that 322E002 is INTERFACIAL MASS-TRANSFER limited -- the gas must diffuse to the
    #    film, cross the interface and react, so the achievable split lags equilibrium by the film's
    #    own residence time.  Relax phi toward the equilibrium target over the condenser holdup
    #    constant HPCC_TAU_FILL_MIN (the same 6 min that sets the sump inventory), making the split a
    #    genuine DYNAMIC STATE (s.hpcc_phi) instead of an instantaneous algebraic map.  This is the
    #    audit's "missing equation" for this tag: the condenser had no composition dynamics at all.
    #    dt == 0 (module-load / boot-pin calls) -> a_phi == 0 -> phi held at phi_prev, bit-exact.
    phi_eq  = _hpcc_flash_split(feed, t_prod_prev, p_loop)
    _base   = phi_prev if phi_prev is not None else HPCC_FRAC_GAS_DES
    a_phi   = clamp(dt / (HPCC_TAU_FILL_MIN * 60.0), 0.0, 1.0)
    phi_flm = {k: _base.get(k, HPCC_FRAC_GAS_DES.get(k, 0.0))
                  + a_phi * (phi_eq[k] - _base.get(k, HPCC_FRAC_GAS_DES.get(k, 0.0)))
               for k in MW_COMP}
    phi_gas = {k: HPCC_FRAC_GAS_DES.get(k, 0.0)
                  + gate * (phi_flm[k] - HPCC_FRAC_GAS_DES.get(k, 0.0)) for k in MW_COMP}
    gas = {k: feed[k] * phi_gas[k] for k in MW_COMP}
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
    # AUDIT F-6: the bubble point is evaluated at the LIVE melt temperature, not the frozen design
    #   constant -- a bubble pressure taken at a fixed temperature is not a bubble pressure.  T_prod
    #   is itself gated, so at design T_prod == HPCC_T_PROD_DES_C exactly -> cc == 1.0 -> 144.2 exact.
    #   P_bub is telemetry only (PI-322E002 / scrub["P_bub_hpcc"]); it does NOT enter pt_target, so
    #   this adds no loop.
    p_bub  = bubble_p_322e002(T_prod, L_hpcc, W_hpcc)
    return {
        "phi_gas": phi_gas, "phi_film": phi_flm, "phi_eq": phi_eq,
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
            "P_bara": round(state.p_syn_bara, 2), "P_offgas": REACT_OFFGAS_P_BARA,
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


# --- OEM liquid densities for the volumetric FIC migration (kg/m3, PFD 1750 MTPD 100% load) ---
#   The liquid flow controllers FIC-323401/328405/323418 run their loops in VOLUMETRIC units
#   (m3/h): the field flow element (FV + FT orifice/coriolis) meters volume, not mass, so the
#   controller must compare a volumetric PV against a volumetric SP.  _fic_flow divides the lagged
#   mass PV by rho BEFORE _ctrl_ipd (and converts any cascade cas_sp likewise); their dict seeds
#   (sp/pv/pv1/pv2) and sp_hi are pre-divided by rho, and each loop is retuned Kc_vol = Kc_mass*rho
#   so the closed-loop coefficient (1 - Kc*a*g) is held INVARIANT:  the open-loop gain scales
#   g_vol = g_mass/rho (PV now m3/h per unit op), hence Kc*g == (Kc*rho)*(g/rho) is unchanged; the
#   integral term Kc*(dt/Ti)*err == (Kc*rho)*(dt/Ti)*(err/rho) is likewise invariant, so Ti stays.
#   _fic_flow RETURNS kg/h (mass) unchanged, so every downstream HMB mass balance is byte-untouched
#   and the boot pin (design constants only, no FIC flow) is neutral by construction.
RHO_401_KGM3 = 992.4    # 328D003 Comp-II flush 734/401: Amm.Water (~992 kg/m3)
RHO_718_KGM3 = 1065.0   # 323D011 lean-carbamate 718A/718B: Carb.Liq (PFD stream 718, 7123 kg/h / 6.7 m3/h)
# 791 / 775 take the PFD's OWN "Density eff." row, NOT a mass/volume back-solve.  Both streams are
# printed at a 2-significant-figure volume of 1.5 m3/h, so back-solving would fabricate 1534/1.5 =
# 1022.7 and 1675/1.5 = 1116.7 -- 3.0 % and 2.0 % away from the tabulated densities.  (Stream 744
# tolerated a back-solve only because its volume carries 3 figures: 31478/31.4 = 1002.5 vs 1002.)
# Design volumes follow as 1534/992.4 = 1.546 and 1675/1095 = 1.530, both printing as the PFD's 1.5.
RHO_791_KGM3 = 992.4    # 328D003 Comp-II wash 791 -> 323E011: Amm.Water 56 C / 4.1 bar
RHO_775_KGM3 = 1095.0   # 328D001 carbamate reflux 775 -> 328C002: Carb.Liq 61 C / 2.6 bar (PFD col 775)


def _fic_flow(c: dict, design: float, op_des: float, store: dict, key: str,
              dt: float, tau_s: float = 5.0, cas_sp=None, rho=None) -> float:
    """Design-normalised flow-controller step.  Delivered flow = design*(op/op_des).

    The plant is a pure-gain flow element (valve stroke -> flow); its PV is the delivered
    flow lagged tau_s so the measurement forms a proper first-order loop (|z|<1, stable).
    `c["op"]` from the previous tick sets this tick's pre-lag flow, `_ctrl_ipd` then advances
    the controller.  Bit-exact at design:  op==op_des  ->  pre==design  ->  pv==design==sp
    ->  du==0  ->  op stays op_des  ->  flow==design.  Mutates `c` (velocity form) in place.

    A FIC in AUTO holds its leg at SP by integral action, so it REJECTS any upstream element
    placed in series with it -- do not model a series level valve by derating `design` here.
    An upstream level loop must instead cascade into this FIC via `cas_sp` (see LIC-323503 /
    FIC-328405), or it has no steady-state authority and winds up.

    `rho` (kg/m3, optional): VOLUMETRIC loop.  The lagged mass PV (and any cascade cas_sp) is
    divided by rho so the controller runs in m3/h.  The controller's own seeds/sp_hi/Kc are
    already in volumetric units (see the RHO_* block above).  The RETURN stays design*(op/op_des)
    in kg/h so the system-side mass balance is unchanged.  Bit-exact at design: pre==design ->
    pv_mass==design -> pv_vol==design/rho==sp -> du==0 -> return==design.
    """
    pre = design * (c["op"] / op_des)
    pv  = _lag1(store, key, pre, tau_s, dt)              # mass kg/h (lag on the physical mass flow)
    if rho is not None:                                  # volumetric loop: controller sees m3/h
        pv = pv / rho
        if cas_sp is not None:
            cas_sp = cas_sp / rho
    op  = _ctrl_ipd(c, pv, dt, cas_sp)
    return design * (op / op_des)


def step_uf85_cascade(s, m_402g_kgh: float, recycle: bool, dt: float) -> dict:
    """Step FFIC-335406 -> FIC-335405 and return delivered UF85 flow.

    The ratio master sees the slave's measured flow divided by live raw-melt flow. In CAS the
    master's output becomes the slave flow setpoint; AUTO retains the slave's local setpoint and MAN
    retains direct slave-stroke authority. LV-324501B is a hard permissive: it forces the dosing pump
    to zero regardless of controller mode, matching the documented granulator-trip interlock.
    """

    m_base = max(float(m_402g_kgh), 0.0)
    route_b = bool(recycle)
    measured_uf_kgh = max(float(s.FIC_335405.get("pv", 0.0)) * 1000.0, 0.0)
    measured_ratio = (
        measured_uf_kgh / m_base
        if m_base > 1.0e-12 and not route_b else 0.0
    )

    if route_b or m_base <= 1.0e-12:
        # Interlock override, including MAN: zero the physical stroke and measurement state so neither
        # faceplate claims additive flow while the recycle valve is selected. Freeze the ratio master
        # to avoid windup against a safety permissive.
        s.FIC_335405["op"] = 0.0
        pv_zero = _lag1(s.tlag, "R324_UF", 0.0, 5.0, dt)
        s.FIC_335405["pv2"] = s.FIC_335405["pv1"]
        s.FIC_335405["pv1"] = pv_zero
        s.FIC_335405["pv"] = pv_zero
        s.FFIC_335406["pv2"] = s.FFIC_335406["pv1"]
        s.FFIC_335406["pv1"] = 0.0
        s.FFIC_335406["pv"] = 0.0
        return {
            "measured_ratio": 0.0,
            "ratio_command": s.FFIC_335406["op"],
            "flow_setpoint_th": 0.0,
            "delivered_kgh": 0.0,
            "interlocked": True,
        }

    if s.FIC_335405["mode"] != "CAS":
        # External-reset feedback: while the slave is disconnected, an AUTO
        # master tracks the achieved ratio instead of winding up.  Preserve a
        # deliberate master-MAN command, but keep its PV history current.
        if s.FFIC_335406["mode"] == "AUTO":
            s.FFIC_335406["op"] = clamp(
                measured_ratio,
                s.FFIC_335406["op_lo"],
                s.FFIC_335406["op_hi"],
            )
        s.FFIC_335406["pv2"] = s.FFIC_335406["pv1"]
        s.FFIC_335406["pv1"] = measured_ratio
        s.FFIC_335406["pv"] = measured_ratio
        ratio_command = s.FFIC_335406["op"]
    else:
        ratio_command = _ctrl_ipd(s.FFIC_335406, measured_ratio, dt)
    flow_setpoint_th = max(ratio_command * m_base / 1000.0, 0.0)
    delivered_th = _fic_flow(
        s.FIC_335405,
        R324_M_UF_DES / 1000.0,
        R324_FIC405_OP_DES,
        s.tlag,
        "R324_UF",
        dt,
        cas_sp=flow_setpoint_th,
    )
    return {
        "measured_ratio": measured_ratio,
        "ratio_command": ratio_command,
        "flow_setpoint_th": flow_setpoint_th,
        "delivered_kgh": max(delivered_th * 1000.0, 0.0),
        "interlocked": False,
    }


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


# ==================================================================================================
#  INTER-VESSEL PROCESS TRANSPORT  (Scenarios4.md deduced dead time theta_p)
#
#  Every _lag1 / _foptd above acts on a PUBLISHED indicator.  What the flowsheet also needs -- and
#  did not have -- is the plug-flow dead time of the physical line BETWEEN two vessels.  Without it
#  a property step at one vessel's outlet is consumed by the next vessel on the SAME tick, i.e. the
#  parcel teleports: mass, temperature and composition all appear downstream with theta_p = 0.  That
#  contradicts every entry in the Scenarios4.md deduced-lag table, whose theta_p column is exactly
#  this transit time, and it is what backend/test_process_transport.py was written to catch.
#
#  Dead time is derived, not tuned:  td = rho * V / m_dot  (consequence.transport_time_s), so it
#  RISES as the plant slows and falls as it speeds up -- the behaviour a trainee must see after
#  cutting a feed.  V comes from the datasheet nozzle bore (References/323C003 323E002.md gives the
#  323C003 urea-solution nozzles as DN 200, pipe 219.1 x 16.0 mm -> 187.1 mm ID; the whole 323/324
#  product train is on that bore) and a per-route run length.  No isometric drawing exists under
#  References/, so the run lengths are plant-layout estimates and are labelled as such below; the
#  bore, the densities and the design carrier flows are all datasheet/PFD values.
#
#  A packet carries mass, temperature, cp and the component vector TOGETHER, so the three can never
#  cross an equipment boundary at different integration instants.  At a settled state the arrived
#  packet equals the departed packet, so the pinned design steady state is bit-exact.
# ==================================================================================================
PROC_LINE_ID_MM = 187.1          # mm ID, DN 200 urea-solution line (pipe 219.1 x 16.0, datasheet N1)


def _proc_route(source: str, destination: str, carrier_kgh: float,
                length_m: float, rho_kgm3: float) -> consequence.ConsequenceRoute:
    """Build one product-line route whose design dead time is rho*V/m_dot, not a fitted number."""
    td_s = consequence.transport_time_s(
        consequence.pipe_volume_m3(PROC_LINE_ID_MM, length_m), carrier_kgh, rho_kgm3)
    return consequence.ConsequenceRoute(source, destination, carrier_kgh, td_s)


PROCESS_ROUTES = {
    # 322E001 bottoms -> 323C003 N1.  HP synthesis structure down to the recirculation column.
    "322E001_TO_323C003": _proc_route("322E001", "323C003", R323_FEED_DES_KGH, 25.0, 1150.0),
    # 323C003 N4 -> 323F004.  Flash drum sits alongside the column; short run.
    "323C003_TO_323F004": _proc_route("323C003", "323F004", R323_M314_DES, 15.0, 1140.0),
    # 323F004 -> 323F010 via LV-323505.  Pre-evaporator alongside the flash drum.
    "323F004_TO_323F010": _proc_route("323F004", "323F010", R323_M319_DES, 15.0, 1145.0),
    # 323F010 -> 323D002.  Product run out to the intermediate-storage tank.
    "323F010_TO_323D002": _proc_route("323F010", "323D002", R323_M317_DES, 30.0, R323_D002_RHO),
    # 323D002 -> 324E001.  Tank pump discharge up to the evaporation structure (longest run).
    "323D002_TO_324E001": _proc_route("323D002", "324E001", R324_FEED_DES, 40.0, R323_D002_RHO),
}


def _cq_packet(mass_kgh: float, temperature_c: float, mass_fraction: dict,
               cp_kj_kgk: float) -> consequence.StreamPacket:
    """Mass fractions + total flow -> one closed consequence.StreamPacket.

    The component vector is rebuilt from the NORMALISED fractions so the packet's own total is the
    sum of its components by construction; make_stream_packet would otherwise reject a total that
    disagrees with the fractions by floating-point epsilon.
    """
    m = float(mass_kgh)
    if not math.isfinite(m) or m <= 0.0:
        return consequence.ZERO_PACKET
    tot_w = sum(v for v in mass_fraction.values() if v > 0.0)
    if tot_w <= 0.0:
        return consequence.ZERO_PACKET
    comp = {k: m * v / tot_w for k, v in mass_fraction.items() if v > 0.0}
    cp = float(cp_kj_kgk)
    if not math.isfinite(cp) or cp <= 0.0:
        cp = 0.1                                   # a packet must carry a positive heat capacity
    return consequence.make_stream_packet(sum(comp.values()), comp, temperature_c, cp)


def _transport_process(s, route_name: str, packet: consequence.StreamPacket,
                       live_carrier_kgh: float, dt: float) -> consequence.StreamPacket:
    """Move one packet down a named product line and publish the boundary diagnostics.

    Diagnostics are what makes the dead time auditable from telemetry: departure vs arrival on the
    same tick is the direct evidence that the boundary is no longer teleporting properties.
    """
    route = PROCESS_ROUTES[route_name]
    arrived = consequence.transport_process_packet(
        s.tlag, "PROCESS_" + route_name, packet, route, live_carrier_kgh, dt)
    diag = s.tlag.setdefault("PROCESS_DIAGNOSTICS", {})
    diag[route_name] = {
        "source": route.source,
        "destination": route.destination,
        "dead_time_s": route.dead_time_s(live_carrier_kgh),
        "design_dead_time_s": route.design_dead_time_s,
        "line_inventory_kg": route.line_inventory_kg,
        "departure_mass_kgh": packet.mass_kgh,
        "arrived_mass_kgh": arrived.mass_kgh,
        "departure_temperature_c": packet.temperature_c,
        "arrived_temperature_c": arrived.temperature_c,
        "mass_fraction": arrived.mass_fraction,
    }
    return arrived



def make_stream(comp_kmolh, T, P, name, src, dst, phase, rho=None, h_kjkg=None):
    """Uniform process-stream object. Derives BOTH mol % and mass % from the same
    per-component kmol/h vector, so the two bases can never drift.  Component
    flow vectors remain at calculation precision; rounded totals are display
    values. Unknown rho stays None (no fabricated properties).

    Enthalpy is published on the H0 tier (`gap_g6_h0_enthalpy`): formation + sensible
    + phase reference on the elements-at-298.15 K datum, ideal solution.  Because every
    constituent is referenced to its elements, the value is reaction-consistent and may be
    summed across a reacting node.  The excess (mixing) term H^E is NOT included, so this
    is not design-grade inside a strongly non-ideal liquid -- `enthalpy_basis` declares
    that per stream rather than leaving it implied.  An explicit `h_kjkg` overrides the
    calculation and is published as plant-reconciled (H2).

    This is a read-only diagnostic layer: it consumes converged state and feeds nothing
    back, so it cannot perturb the design anchors the mass solvers are pinned to."""
    n = {k: comp_kmolh.get(k, 0.0) for k in MW_COMP}
    m = {k: n[k] * MW_COMP[k] for k in MW_COMP}
    n_tot = sum(n.values()); m_tot = sum(m.values())
    if h_kjkg is not None:
        h_spec = h_kjkg
        H_kW = m_tot * h_kjkg / 3600.0
        basis = h0_enthalpy.EnthalpyBasis.H2.value
    else:
        h0 = h0_enthalpy.h0_stream(n, T, phase)
        H_kW = h0["enthalpy_flow_kW"]
        # Re-specify against this record's own mass total: MW_COMP is atom-consistent for the
        # reactor couples and differs in the last digits from the H0 module's molar masses.
        h_spec = H_kW * 3600.0 / m_tot if m_tot > 0.0 else None
        basis = h0["enthalpy_basis"]
    return {
        "name": name, "src": src, "dst": dst, "phase": phase,
        "T_C": round(T, 1), "P_bara": round(P, 1),
        "mass_kgh": round(m_tot, 1), "mass_th": round(m_tot / 1000.0, 3),
        "mol_kmolh": round(n_tot, 2),
        "MW": round(m_tot / n_tot, 3) if n_tot else 0.0,
        "rho": (round(rho, 1) if rho else None),
        "vol_m3h": (round(m_tot / rho, 2) if rho else None),
        "enthalpy_kJkg": (round(h_spec, 3) if h_spec is not None else None),
        "enthalpy_flow_kW": round(H_kW, 3),
        "enthalpy_basis": basis,
        "component_kmolh": dict(n),
        "component_kgh": dict(m),
        "mol_pct":  {k: round(n[k] / n_tot * 100.0, 3) if n_tot else 0.0 for k in MW_COMP},
        "mass_pct": {k: round(m[k] / m_tot * 100.0, 3) if m_tot else 0.0 for k in MW_COMP},
    }


def make_stream_mass_pct(mass_kgh, mass_pct, T, P, name, src, dst, phase,
                         rho=None, h_kjkg=None):
    """Build a canonical stream from an independently rounded PFD mass-percent row."""
    total_pct = sum(max(mass_pct.get(k, 0.0), 0.0) for k in MW_COMP)
    if mass_kgh <= 0.0 or total_pct <= 0.0:
        return make_stream({}, T, P, name, src, dst, phase, rho=rho, h_kjkg=h_kjkg)
    comp_kmolh = {
        k: mass_kgh * max(mass_pct.get(k, 0.0), 0.0) / total_pct / MW_COMP[k]
        for k in MW_COMP
    }
    return make_stream(comp_kmolh, T, P, name, src, dst, phase, rho=rho, h_kjkg=h_kjkg)


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
        self.r322_r001_P = 144.9  # HP loop pressure anchor (bar a)
        # tank
        self.tank_level_frac = 0.65
        self.tank_T_C        = 25.0
        self.tank_P_top_barG = 12.3
        self.F_in_BL_th      = 42.762   # t/h, BL NH3 makeup (seed; set live by LIC-321501 = pump draw)
        self.totalizer_t     = 0.0       # FQI-321401: NH3 delivered this run; starts at zero every program init
        # Plant clock (s since program init), advanced by step_sim in lock-step with the
        # physics. Distinct from wall clock: FAST pacing advances this 60x faster than
        # real time, and the historian/trends are keyed to it so a "1 hour" trend always
        # means one hour of PLANT behaviour regardless of sim_mode.
        self.sim_t           = 0.0
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
        # AUDIT F-6/TD-007: 322E002 interfacial phase-split state.  Seeded at the calibrated design
        # split, relaxed each tick toward the live (T,P) equilibrium flash over HPCC_TAU_FILL_MIN.
        self.hpcc_phi   = dict(HPCC_FRAC_GAS_DES)
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
        #   AUTO holds the design level (50 %) at the field-calibrated design opening (46.1 %);
        #   direct-acting.
        self.strip_level = STRIP_LEVEL_SP_DES
        self.strip_bot_kgh_lag = None
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
        # AUDIT F-8/TD-009: downstream component species states (mass fractions, Sum w == 1).
        # Seeded at the PFD design composition of each stage, so every species balance starts on
        # its own fixed point and the layer cannot disturb the total-mass/energy ODEs it rides on.
        self.w_c003 = dict(W_S314)                # 323C003 bottoms   (stream 314)
        self.w_f004 = dict(W_S319)                # 323F004 flash liq (stream 319)
        self.w_f010 = dict(W_S317)                # 323F010 product   (stream 315/317)
        self.w_d002 = dict(W_S317)                # 323D002 tank Comp-I (active)
        self.w_d002_II = dict(W_S317)             # 323D002 tank Comp-II (passive buffer)
        self.w_e001 = dict(W_S401)                # 324E001 melt      (stream 401)
        self.w_e003 = dict(W_S402)                # 324E003 melt      (stream 402, final product)
        self.r323_c003_M = R323_C003_M_DES        # 323C003 rectifier bottom holdup
        self.r323_c003_T = R323_C003_T_SP_C        # 135 C
        self.r323_c003_P = R323_C003_P_BARA        # PT-323201 column pressure (dynamic, hydraulic coupling)
        self.r323_f004_M = R323_F004_M_DES         # 323F004 flash-tank holdup
        self.r323_f004_T = R323_F004_T_SP_C        # 106 C
        self.r323_f004_P = R323_F004_P_BARA        # 323F004 flash pressure (dynamic, read by PIC-323203 LP node)
        self.r323_f010_M = R323_F010_M_DES         # 323F010 pre-evap separator holdup
        self.r323_f010_T = R323_F010_T_SP_C        # 99 C
        self.r323_f010_P = R323_F010_P_BARA        # bar a 323F010 vacuum (PT-323204, live off HV-323605/HV-329605)
        self.r323_d002_M_I  = R323_D002_M_I_DES    # 323D002 Compartment I (active, 80 m3)
        # Comp II is DRY in normal operation -- it is an emergency buffer that only fills when Comp I
        # spills over the internal baffle (References/323D002.md §3.3).  It used to seed at 50 %,
        # which quietly declared a 173 t inventory that the plant would treat as a high-level alarm.
        self.r323_d002_M_II = 0.0                  # Compartment II (passive buffer, 300 m3)
        self.r323_d002_T    = R323_F010_T_SP_C     # TI-323008 Comp-I bulk temperature (99 C)
        # Field tie-in spool between Comp I and Comp II.  A hand valve, not a DCS device: closed by
        # default, and when the operator opens it the two become connected vessels (see step_sim).
        self.HV_323D002_TIE = False

        # -- Stage 1 cascade: TIC-323007 (master, hold 135 C) -> PIC-329202 (steam pressure to 323E002).
        #    Master OP = steam-chest pressure demand (bar a, 0..P_sup); slave OP = steam valve stroke (%).
        self.TIC_323007 = {"mode": "AUTO", "op": R323_E002_PCHEST_DES,
                           "sp": R323_C003_T_SP_C, "pv": R323_C003_T_SP_C,
                           "pv1": R323_C003_T_SP_C, "pv2": R323_C003_T_SP_C,
                           "Kc": 2.0, "Ti": 500.0, "Td": -1.0, "act": +1.0,  # official Td=-1 (deriv disabled) -> 0.0
                           "op_lo": 0.0, "op_hi": R323_P_STEAM_SUP, "sp_lo": 50.0, "sp_hi": 160.0}
        self.PIC_329202 = {"mode": "CAS", "op": R323_E002_OP_DES,
                           "sp": R323_E002_PCHEST_DES, "pv": R323_E002_PCHEST_DES,
                           "pv1": R323_E002_PCHEST_DES, "pv2": R323_E002_PCHEST_DES,
                           "Kc": 0.65, "Ti": 30.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": R323_P_STEAM_SUP}
        # -- Stage 1/2 level loops -> LV-323501 / LV-323505 (DIRECT: level above SP -> drain more).
        self.LIC_323501 = {"mode": "AUTO", "op": R323_LV501_OP_DES,
                           "sp": R323_C003_LVL_SP, "pv": R323_C003_LVL_SP,
                           "pv1": R323_C003_LVL_SP, "pv2": R323_C003_LVL_SP,
                           "Kc": 1.2, "Ti": 100.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        self.LIC_323505 = {"mode": "AUTO", "op": R323_LV505_OP_DES,
                           "sp": R323_F004_LVL_SP, "pv": R323_F004_LVL_SP,
                           "pv1": R323_F004_LVL_SP, "pv2": R323_F004_LVL_SP,
                           "Kc": 1.0, "Ti": 100.0, "Td": 0.0, "act": -1.0,
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
                           "Kc": 0.2, "Ti": 60.0, "Td": 0.0, "act": +1.0,
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
                           "Kc": 0.4, "Ti": 30.0, "Td": -1.0, "act": +1.0,
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
                           # TD-015 RETUNE.  Kc = 2.0 / Ti = 120 was inherited from a plant whose
                           # temperature ODE was IDENTICALLY ZERO, so it carried no information about
                           # the real one.  With the bubble-point closure in, the process gain was
                           # measured by central difference over 1 h means (+-0.05 bar on the master
                           # in MAN, so the plant's own wander cancels): K_p = +8.3 C/bar on BOTH
                           # loops, positive, i.e. the REVERSE action is correct.  Kc = 2.0 therefore
                           # meant a loop gain of 16.7 and the measured result was a multi-hour limit
                           # cycle (T_e003 +-1.2 C, PV-329212 81-90 %).  Lambda-tuned on the
                           # separator's own dynamics -- tau ~ 360 s (180 s residence + the 180 s
                           # bubble-point holdup lag), lambda = 3*tau, theta ~ 0 since the chest-P
                           # slave is fast at Ti = 20 s:
                           #     Kc = tau / (K_p * (lambda + theta)) = 360 / (8.3 * 1080) = 0.04
                           # then HALVED to 0.02 (loop gain 0.17).  The halving originally fought a
                           # relay: `v_m = min(v_conc, v_duty)` with a FIXED concentration cap was a
                           # branch nonlinearity that sustained a slow limit cycle no linear tuning
                           # removed (16 h envelope T_e001 0.42/0.25, T_e003 1.33/0.88 at Kc 0.04/0.02).
                           # TD-016 removed that relay: the cap is now a smooth activity-model VLE
                           # equilibrium w_eq(T), so the melt tracks a continuous curve, TIC-324001
                           # never disengages, and the cycle is gone (16 h envelope -> 0.008/0.001 C).
                           # Kc = 0.02 is kept as conservatism -- the lambda value 0.04 could now be
                           # restored, but re-measuring K_p on the non-relay plant is the precondition.
                           # Velocity form, so pv == sp == pv1 still gives du == 0 and the design
                           # seed stays bit-exact at any Kc/Ti.
                           "Kc": 1.5, "Ti": 320.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": R323_P_STEAM_SUP,
                           "sp_lo": 0.0, "sp_hi": 200.0}
        self.PIC_329203 = {"mode": "CAS", "op": R324_E001_OP_DES,
                           "sp": R324_E001_PCHEST_DES, "pv": R324_E001_PCHEST_DES,
                           "pv1": R324_E001_PCHEST_DES, "pv2": R324_E001_PCHEST_DES,
                           "Kc": 0.3, "Ti": 75.0, "Td": -1.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0,
                           "sp_lo": 0.0, "sp_hi": R323_P_STEAM_SUP}
        # ---- Stage 2 steam : TIC-324002 (140 C) -> PIC-329212 (steam chest) ----
        self.TIC_324002 = {"mode": "AUTO", "op": R324_E003_PCHEST_DES,
                           "sp": R324_E003_T_SP_C, "pv": R324_E003_T_SP_C,
                           "pv1": R324_E003_T_SP_C, "pv2": R324_E003_T_SP_C,
                           # TD-015 retune, same measurement and rule as TIC-324001 above.
                           "Kc": 2.0, "Ti": 300.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": steam_system.P_MP_BARA,
                           "sp_lo": 0.0, "sp_hi": 200.0}
        self.PIC_329212 = {"mode": "CAS", "op": R324_E003_OP_DES,
                           "sp": R324_E003_PCHEST_DES, "pv": R324_E003_PCHEST_DES,
                           "pv1": R324_E003_PCHEST_DES, "pv2": R324_E003_PCHEST_DES,
                           "Kc": 0.65, "Ti": 130.0, "Td": -1.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0,
                           "sp_lo": 0.0, "sp_hi": steam_system.P_MP_BARA}
        # ---- Vacuum : PIC-324202 (324F001) / PIC-324203 (324F003) false air ----
        #      REVERSE acting: pressure below SP -> admit more false air (op up).
        self.PIC_324202 = {"mode": "AUTO", "op": R324_PV202_OP_DES,
                           "sp": R324_F001_P_BARA, "pv": R324_F001_P_BARA,
                           "pv1": R324_F001_P_BARA, "pv2": R324_F001_P_BARA,
                           "Kc": 2.0, "Ti": 200.0, "Td": -1.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 1.0}
        self.PIC_324203 = {"mode": "AUTO", "op": R324_PV203_OP_DES,
                           "sp": R324_F003_P_BARA, "pv": R324_F003_P_BARA,
                           "pv1": R324_F003_P_BARA, "pv2": R324_F003_P_BARA,
                           "Kc": 2.0, "Ti": 200.0, "Td": -1.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 1.0}
        # ---- LIC-324501 split-range 324F003 drain : LV-A forward / LV-B recycle
        #      DIRECT acting: level above SP -> drain more (op up).
        self.LIC_324501 = {"mode": "AUTO", "op": R324_LIC501_OP_DES,
                           "sp": R324_F003_LVL_SP, "pv": R324_F003_LVL_SP,
                           "pv1": R324_F003_LVL_SP, "pv2": R324_F003_LVL_SP,
                           "Kc": 0.85, "Ti": 200.0, "Td": -1.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # ---- LIC-329505 324E001 steam-side condensate ("active controlled steam
        #      trap"): LV-329505 drains the shell.  DIRECT: level above SP -> drain
        #      more (op up).  Tuning ex Master_PID_Tuning_Constants #9 (Dz=2% EU).
        self.LIC_329505 = {"mode": "AUTO", "op": R324_LV9505_OP_DES,
                           "sp": R324_E001_COND_LVL_SP, "pv": R324_E001_COND_LVL_SP,
                           "pv1": R324_E001_COND_LVL_SP, "pv2": R324_E001_COND_LVL_SP,
                           "Kc": 2.5, "Ti": 60.0, "Td": 0.0, "Tf": 0.0, "Dz": 2.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # ---- HIC-329605 324F002 motive LP steam hand valve (published HIC+HV 1:1)
        self.HIC_329605 = R324_HIC9605_DES_PCT       # % opening (operator hand valve, no controller mode)
        self.HIC_329606 = R324_HIC9606_DES_PCT       # % HV-329606 324F004/F005 motive-steam hand valve
        self.HIC_323605 = R323_HIC605_DES_PCT        # % HV-323605 323F010 gas-outlet hand valve (stream 790)
        self.PIC_335201 = R335_PIC201_DES_BARG       # bar g, 335 melt-header pressure (BL boundary input);
                                                     # LV-324501B opens (recycle to 323D002) when > R335_LVB_RELIEF_BARG
        # ---- FFIC-335406 UF85 ratio station -> FIC-335405 flow slave -----------
        self.FFIC_335406 = {"mode": "AUTO", "op": R324_UF_RATIO,
                            "sp": R324_UF_RATIO, "pv": R324_UF_RATIO,
                            "pv1": R324_UF_RATIO, "pv2": R324_UF_RATIO,
                            "Kc": 0.5, "Ti": 60.0, "Td": 0.0, "act": +1.0,
                            "op_lo": 0.0, "op_hi": 0.05, "sp_lo": 0.0, "sp_hi": 0.05}
        self.FIC_335405 = {"mode": "CAS", "op": R324_FIC405_OP_DES,
                           "sp": R324_M_UF_DES / 1000.0, "pv": R324_M_UF_DES / 1000.0,
                           "pv1": R324_M_UF_DES / 1000.0, "pv2": R324_M_UF_DES / 1000.0,
                           "Kc": 100.0, "Ti": 15.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 1.0}
        # ---- Unit 324 lumped physical state (seeded at design fixed point) -----
        self.r324_e001_T = R324_E001_T_SP_C          # C  324E001/F001 melt temp
        self.r324_f001_M = R324_F001_M_DES           # kg 324F001 melt holdup
        self.r324_f001_P = R324_F001_P_BARA          # bar a 324F001 vacuum
        self.r324_e001_cond_M = R324_E001_COND_M_DES # kg 324E001 shell steam-condensate holdup (LIC-329505)
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
        self.a328_c002_T = R328_C002_T_BOT_BOT
        self.a328_c002_P = R328_C002_P_TOP        # AUDIT C1: column OVHD pressure state (3.5 bar a)
        self.a328_d001_M = R328_D001_M_DES
        self.a328_d001_T = R328_D001_T
        self.a328_d001_P = R328_D001_P_BARA
        # ---- 328C003 Hydrolyser (200 C, 16.8 bar a) / 328C004 Desorber-II (143 C)
        self.a328_c003_M = R328_C003_M_DES
        self.a328_c003_T = R328_C003_T
        self.a328_c003_P = R328_C003_P_BARA
        self.a328_c004_M = R328_C004_M_DES
        self.a328_c004_T = R328_C004_T
        self.a328_c004_P = R328_C004_P_BARA       # AUDIT C1: column OVHD pressure state (3.7 bar a)
        # ---- AUDIT F-8: species vectors for the desorption train.  Seeded on the PFD bottoms
        #      composition of each section, which is exactly what its anchor was struck against, so
        #      dw/dt == 0 at the seed and the layer cannot move the heat-and-mass balance.
        self.w_328c002 = dict(W_S743)             # 328C002 bottoms  (stream 743 = 746)
        self.w_328c003 = dict(W_S747)             # 328C003 bottoms  (stream 747 = 749)
        self.w_328c004 = dict(W_S739)             # 328C004 bottoms  (stream 739 = 740, purified)
        # Torn vapour compositions: 328C003 and 328C004 both discharge overhead INTO 328C002, which
        # is solved first in the tick, so their compositions carry one step of lag -- exactly the
        # tear the flows already use (m748_prev / m750_prev).
        # Seeded on the BACK-SOLVED vapour, not the tabulated PFD row -- that is what the model
        # delivers from tick 1 onward, and seeding on anything else steps the 328C002 balance.
        self.y_328_748 = dict(DES_C003["y"])      # 328C003 OVHD -> 328C002
        self.y_328_750 = dict(DES_C004["y"])      # 328C004 OVHD -> 328C002
        # ---- 322C001 LP absorber (43 C, 3.9 bar a)
        self.a328_c001_M = A328_C001_M_DES
        self.a328_c001_T = A328_C001_T
        self.a328_c001_P = A328_C001_P_BARA
        self.a328_c001_w = dict(W_C001_DES)  # TD-009: liquor species (SOL_SPECIES); == design feed mix
        self.cpl_flow_kgh = A328_CPL_DES     # FT-322404 condensate (954) feed, operator-manipulable at runtime (kg/h)
        # ---- 323C005 vent scrub / 328D003 communicating compartments I, II, and III
        self.a323_c005_M  = A323_C005_M_DES
        self.a323_c005_T  = A323_C005_T
        self.a328_d003_MI  = A328_D003_MI_DES
        self.a328_d003_MII = A328_D003_MII_DES
        self.a328_d003_MIII = A328_D003_MIII_DES
        self.a328_d003_TI  = A328_D003_TI
        self.a328_d003_TII = A328_D003_TII
        self.a328_d003_TIII = A328_D003_TIII

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
                           "Kc": 0.6, "Ti": 100.0, "Td": -1.0, "act": -1.0,
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
                           "Kc": 1.1, "Ti": 30.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # SIC-323902 323P001 standby pump speed (MAN 0, spare).
        self.SIC_323902 = {"mode": "MAN", "op": 0.0,
                           "sp": 0.0, "pv": 0.0, "pv1": 0.0, "pv2": 0.0,
                           "Kc": 1.1, "Ti": 30.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # LIC-323503 323D011 flash-tank-condenser level tank (LT-323503) -> LV-323503 on the 323P008
        #   lean-carbamate pump discharge header.  DIRECT: level above SP -> op rises -> LV-503 opens ->
        #   less discharge resistance -> the pump runs out on its curve -> tank drains faster
        #   (323E011 323D011 323P008 Datasheets.md:54).  The tank is 323P008's NPSH buffer; OEM holds
        #   it at 50 % capacity.  This op is realised as the TOTAL DRAW DEMAND for the header rather
        #   than as a raw stroke: FIC-323418 holds the metered 718B slipstream and 718A is the
        #   UNMETERED REMAINDER (a transport lag, no controller of its own -- FIC-328405 belongs to
        #   PFD stream 793 off the 328D003 Comp-II header, not to this leg). See the 323D011 runtime
        #   block for why the series form cannot work.
        #   Tuning is the OEM DCS pair verbatim (Master_PID_Tuning_Constants.md:26, "323D011,ACA").
        #   Legal here (and NOT for the flow loops) because the PV is a level in percent, so the
        #   controller's engineering unit IS %span and no gain rescale applies.  Integrating level,
        #   k = 7123/(3600*1187.2) = 1.667e-3 %/s per %op (the demand form keeps the same DES/op_des
        #   slope the header stroke had); PI closes s^2 + k*Kc*s + k*Kc/Ti, giving
        #   wn = 5.0e-3 rad/s (period ~1257 s) and zeta = 0.30 -> stable, slow averaging control.
        #   Settling envelope is exp(-zeta*wn*t), i.e. tau = 667 s -> ~2700 s to settle; any dynamic
        #   acceptance test on this loop must run at least that long (scratchpad/dyn718r.py).
        self.LIC_323503 = {"mode": "AUTO", "op": R3232_LV503_OP_DES,
                           "sp": R3232_D011_LVL_SP, "pv": R3232_D011_LVL_SP,
                           "pv1": R3232_D011_LVL_SP, "pv2": R3232_D011_LVL_SP,
                           "Kc": 1.8, "Ti": 120.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # TIC-323013 323E003 tempered-water SUPPLY temp (stream 1102, 55 °C) -> split-range TV-323013A/B.
        #   DIRECT: PV above SP -> op rises -> TV-A opens (cold make-up in) and TV-B closes (hot bypass
        #   out); the two strokes are exact opposites.  sp span = the achievable supply band: 45 °C at
        #   TV-A wide open, 65 °C (= return temp) at TV-A shut / full bypass.
        self.TIC_323013 = {"mode": "CAS", "op": R3232_TV13_DES_PCT,
                           "sp": R3232_TW_SUP_T, "pv": R3232_TW_SUP_T,
                           "pv1": R3232_TW_SUP_T, "pv2": R3232_TW_SUP_T,
                           "Kc": 1.0, "Ti": 100.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 45.0, "sp_hi": R3232_TW_RET_T}
        # FIC-323401 328D003 Comp-II flush 401 -> FV-323401 (REVERSE flow). VOLUMETRIC loop (m3/h):
        #   seeds = M401_DES/RHO_401 (PFD stream 734: 1534/992.4 = 1.546 m3/h -> PFD 1.5), sp_hi
        #   2000/RHO_401, Kc 1.2*RHO_401 (=1190.9) so Kc*g invariant vs the mass loop;
        #   _fic_flow(rho=RHO_401_KGM3) returns kg/h.
        self.FIC_323401 = {"mode": "AUTO", "op": 50.0,
                           "sp": R3232_E011_M401_DES / RHO_401_KGM3, "pv": R3232_E011_M401_DES / RHO_401_KGM3,
                           "pv1": R3232_E011_M401_DES / RHO_401_KGM3, "pv2": R3232_E011_M401_DES / RHO_401_KGM3,
                           "Kc": 0.1 * RHO_401_KGM3, "Ti": 7.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 2000.0 / RHO_401_KGM3}
        # FIC-323402 328D003 Comp-II wash 402 -> FV-323402 (REVERSE flow).
        #   VOLUMETRIC loop (m3/h): the operator enters SP in m3/h, so the seeds are
        #   M402_DES/RHO_791 (1534/992.4 = 1.546 m3/h, PFD stream 791), sp_hi is the old 6000 kg/h
        #   span divided by rho, and Kc is scaled by rho so the loop coefficient 1-Kc*a*g is
        #   IDENTICAL to the mass-basis tune noted below.  _fic_flow(rho=RHO_791_KGM3) still
        #   returns kg/h, so the 323E011 / Comp-II mass balance is untouched.
        self.FIC_323402 = {"mode": "AUTO", "op": 50.0,
                           "sp": R3232_E011_M402_DES / RHO_791_KGM3, "pv": R3232_E011_M402_DES / RHO_791_KGM3,
                           "pv1": R3232_E011_M402_DES / RHO_791_KGM3, "pv2": R3232_E011_M402_DES / RHO_791_KGM3,
                           "Kc": 0.1 * RHO_791_KGM3, "Ti": 7.0, "Td": 0.0, "act": +1.0,   # Kc 1.2->0.5: loop coef 1-Kc*a*g, a=0.0196. On the PFD-791 design (M402_DES=1534) g=1534/50=30.68, so Kc=0.5 -> coef 0.699, monotone with margin (the old 2931 basis gave g=58.6, coef 0.43; Kc=1.2 there gave coef -0.38 and rang).  Kc*RHO_791 holds the vol-loop coef equal.
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 6000.0 / RHO_791_KGM3}
        # FIC-328405 ammonia-water stream 793, a normally-closed SPARE branch off the 328D003 Comp-II
        #   discharge header 343/733 (the same header that feeds 735 / 791 / 734) -> FV-328405.
        #   PFD-22 col 793: 0 kg/h, 0 m3/h, rho 992.4, 56 C -> the valve is SHUT at design, so the
        #   loop seeds at op 0 / sp 0 / pv 0.  It is NOT the 718A carbamate leg (that physics is
        #   stripped: 718A is now the LIC-323503 remainder, see stage 9), hence no CAS mode.
        #   VOLUMETRIC loop (m3/h) on the branch capacity, which is the twin of the 791/734 legs:
        #   design = S793_CAP_KGH at 100 % stroke, sp_hi = S793_CAP_KGH/RHO_401 (1.546 m3/h),
        #   Kc 1.2*RHO_401 as on FIC-323401 (same fluid, same rho) -> g = 1534/100 = 15.34 kg/h/%,
        #   loop coef 1-Kc*a*g = 0.639 with a = 0.0196: monotone.
        self.FIC_328405 = {"mode": "AUTO", "op": R3232_FIC405_OP_DES,
                           "sp": S793_M_DES / RHO_401_KGM3, "pv": S793_M_DES / RHO_401_KGM3,
                           "pv1": S793_M_DES / RHO_401_KGM3, "pv2": S793_M_DES / RHO_401_KGM3,
                           "Kc": 0.2 * RHO_401_KGM3, "Ti": 15.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": S793_CAP_KGH / RHO_401_KGM3}
        # FIC-323418 lean-carbamate 718B leg, 323D011/323P008 -> 323E003 -> FV-323418 (REVERSE).
        #   OEM service is "ACA FROM 323P8A/B" (Master_PID_Tuning_Constants.md:14), i.e. this leg.
        #   The ONLY metered 718 leg; 718A is the unmetered remainder of the LIC-323503 draw.
        #   VOLUMETRIC loop (m3/h): seeds M718B_DES/RHO_718 (3561.5/1065 = 3.344 m3/h -> PFD 718B
        #   3.3), sp_hi 8000/RHO_718, Kc 0.4*RHO_718; _fic_flow(rho=RHO_718_KGM3) returns kg/h.
        self.FIC_323418 = {"mode": "AUTO", "op": R3232_FIC418_OP_DES,
                           "sp": R3232_M718B_DES / RHO_718_KGM3, "pv": R3232_M718B_DES / RHO_718_KGM3,
                           "pv1": R3232_M718B_DES / RHO_718_KGM3, "pv2": R3232_M718B_DES / RHO_718_KGM3,
                           "Kc": 1.0 * RHO_718_KGM3, "Ti": 100.0, "Td": -1.0, "act": +1.0,   # mass basis g=M718B_DES/50=71.2, loop coef 1-Kc*a*g, a=0.0196. Kc=1.2 gives coef -0.674 (alternating). Kc=0.4 -> coef 0.442 monotone; brackets FIC-323402 (coef 0.70) and FIC-328404 (g=55.5, Kc=0.5, coef 0.46). Kc*RHO_718 holds the vol-loop coef equal.
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 8000.0 / RHO_718_KGM3}

        # -- 328-1 controllers (desorption / hydrolysis train) -----------------
        # LIC-328501 328D001 reflux-drum level -> LV-328501 (DIRECT, 776 -> 323E003).
        self.LIC_328501 = {"mode": "AUTO", "op": R328_D001_LV_OP_DES,
                           "sp": R328_D001_LVL_SP, "pv": R328_D001_LVL_SP,
                           "pv1": R328_D001_LVL_SP, "pv2": R328_D001_LVL_SP,
                           "Kc": 1.0, "Ti": 300.0, "Td": -1.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # PIC-328202 328C002 column pressure -> PV-328202 on the 328D001 786 vent -> 323E011.
        # AUDIT B5: transmitter is on the COLUMN (mapping doc line 5), final element on the drum vent
        # (line 41).  Re-seeded from the drum node (2.6) to the column node (3.5, PFD-22 stream 737)
        # with the span shifted to match.  pv == sp at design -> du == 0 for any Kc, so the pin holds.
        self.PIC_328202 = {"mode": "AUTO", "op": R328_D001_PV_OP_DES,
                           "sp": R328_C002_P_TOP, "pv": R328_C002_P_TOP,
                           "pv1": R328_C002_P_TOP, "pv2": R328_C002_P_TOP,
                           "Kc": 2.5, "Ti": 200.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 2.5, "sp_hi": 5.0}
        # TIC-328002 328E004 CW to condenser -> TV-328002 (DIRECT cooling, hold drum 61 C).
        self.TIC_328002 = {"mode": "AUTO", "op": R328_E004_TV_OP_DES,
                           "sp": R328_D001_T, "pv": R328_D001_T,
                           "pv1": R328_D001_T, "pv2": R328_D001_T,
                           "Kc": 3.0, "Ti": 500.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 45.0, "sp_hi": 80.0}
        # FIC-328404 328D001 reflux 775 -> FV-328404 (REVERSE flow, remote-CAS capable).
        #   VOLUMETRIC loop (m3/h): seeds are M775_DES/RHO_775 (1675/1095 = 1.530 m3/h, PFD stream
        #   775), sp_hi is the old 4000 kg/h span divided by rho, and Kc is scaled by rho so the
        #   loop coefficient is IDENTICAL to the mass-basis tune noted below.
        self.FIC_328404 = {"mode": "CAS", "op": R328_D001_FIC404_OP_DES,
                           "sp": R328_D001_M775_DES / RHO_775_KGM3, "pv": R328_D001_M775_DES / RHO_775_KGM3,
                           "pv1": R328_D001_M775_DES / RHO_775_KGM3, "pv2": R328_D001_M775_DES / RHO_775_KGM3,
                           "Kc": 0.5 * RHO_775_KGM3, "Ti": 25.0, "Td": 0.0, "act": +1.0,   # Kc 1.2->0.5: g=1675/30.2=55.5, loop coef 1-Kc*a*g, a=0.0196. Kc=1.2 gives M=67 (damped-oscillatory 51-102). Kc=0.5 -> M=27.7, coef 0.46 monotone.  Kc*RHO_775 holds the vol-loop coef equal.
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 4000.0 / RHO_775_KGM3}
        # FIC-329402 328C003 hydrolyser MP-steam 911 -> FV-329402 (REVERSE flow, CAS).
        self.FIC_329402 = {"mode": "CAS", "op": 50.0,
                           "sp": R328_C003_M911_DES, "pv": R328_C003_M911_DES,
                           "pv1": R328_C003_M911_DES, "pv2": R328_C003_M911_DES,
                           "Kc": 0.4, "Ti": 200.0, "Td": -1.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 3000.0}
        # PIC-328203 328C003 hydrolyser OVHD pressure -> PV-328203 (DIRECT, 16.8 bar a).
        self.PIC_328203 = {"mode": "AUTO", "op": R328_C003_PV_OP_DES,
                           "sp": R328_C003_P_BARA, "pv": R328_C003_P_BARA,
                           "pv1": R328_C003_P_BARA, "pv2": R328_C003_P_BARA,
                           "Kc": 1.5, "Ti": 50.0, "Td": -1.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 12.0, "sp_hi": 20.0}
        # FFIC-329401 328C004 desorber-II steam/feed RATIO master, T/M3: m931 in t/h over the
        # FIC-328402 leg (m744) in m3/h.  On CAS the FIC-329401 SP is FIC-328402 * this ratio.
        self.FFIC_329401 = {"mode": "AUTO", "op": R328_C004_M931_DES,
                            "sp": R328_FFIC_RATIO_DES, "pv": R328_FFIC_RATIO_DES,
                            "pv1": R328_FFIC_RATIO_DES, "pv2": R328_FFIC_RATIO_DES,
                            # Kc 0.8 -> 8.0e5.  This master's PV is a RATIO of order 0.2 while its
                            # output is an LP-steam demand of order 6495 kg/h, so the open-loop gain
                            # is tiny: g = d(ratio)/d(m931) = 1/(1000*S744_VOL_DES) = 3.185e-5 T/M3
                            # per kg/h.  With a = dt/(tau+dt) = 0.1/5.1 = 0.019608, Kc=0.8 gave a
                            # loop coefficient 1-Kc*a*g of 1 - 5e-7, i.e. the master was INERT --
                            # probe_ffic_gain.py measured a +5 % ratio SP step moving FV-329401 by
                            # 0.0009 % in 600 s.  Kc = 0.5/(a*g) = 8.0e5 puts the coefficient at
                            # 0.500, inside the 0.46-0.70 band the sibling flow loops use.
                            # Design fixed point is untouched: pv == sp == pv1 == pv2 -> du == 0
                            # for ANY Kc, so the boot pin cannot move.
                            "Kc": 8.0e5, "Ti": 40.0, "Td": 0.0, "act": +1.0,
                            "op_lo": 0.0, "op_hi": 12000.0, "sp_lo": 0.0, "sp_hi": 0.5}
        # FIC-329401 328C004 LP-steam 931 slave (REVERSE flow) <- FFIC-329401 demand.
        self.FIC_329401 = {"mode": "CAS", "op": 50.0,
                           "sp": R328_C004_M931_DES, "pv": R328_C004_M931_DES,
                           "pv1": R328_C004_M931_DES, "pv2": R328_C004_M931_DES,
                           "Kc": 0.3, "Ti": 100.0, "Td": 0.0, "act": +1.0,   # Kc 1.2->0.30: PV in kg/h, process gain g=6495/50=129.9; loop coef 1-Kc*a*g, a=dt/(tau+dt)=0.0196; Kc=1.2 gives coef -2.06 (unstable 0<->100 limit cycle). Kc<0.39 monotonic; 0.30 -> coef 0.24, 2.6x margin.
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 12000.0}
        # TIC-328008 inferential: offgas H2O content to reflux condenser 328E004 (mol%), from TT-328008 & PIC-328202.
        # TIC-328008 is the MASTER of FIC-328404 (TD-004): its PV is the inferential H2O content of
        # the gas leaving 328C002 to 328E004 (PFD 737), and it trims the 775 carbamate reflux to
        # hold it.  act=-1 (DIRECT) is already correct: wetter offgas -> MORE reflux.
        # Its OUTPUT is the slave's setpoint in kg/h (the FFIC-329401 convention -- _fic_flow
        # divides cas_sp by rho itself, so a master feeding a volumetric loop still emits MASS).
        # op therefore spans the slave's OLD mass span 0..4000 kg/h instead of 0..100 %, and Kc is
        # scaled by that 40x span change (3.0 -> 120.0) so the master keeps its former authority.
        # At design pv == sp == pv1 == pv2 -> du == 0 -> op holds R328_D001_M775_DES exactly, which
        # _fic_flow turns into M775_DES/RHO_775 -- bit-identical to the slave's seeded sp.
        self.TIC_328008 = {"mode": "AUTO", "op": R328_D001_M775_DES,
                           "sp": R328_D001_OFFGAS_H2O_DES, "pv": R328_D001_OFFGAS_H2O_DES,
                           "pv1": R328_D001_OFFGAS_H2O_DES, "pv2": R328_D001_OFFGAS_H2O_DES,
                           # Speed-up: Kc 120->240, Ti 250->110.  The inferential loop is heavily
                           # over-damped (monotone, 0% overshoot across Kc up to 900 in an isolated
                           # closed-loop step at the real dt=0.1); a +3 mol% SP step that never settled
                           # in 1200 s at 120/250 now settles in ~574 s with no overshoot.  du==0 at the
                           # design pin (pv==sp==pv1==pv2) for any Kc/Ti, so the boot fixed point and
                           # HPCC_UA pin are byte-preserved.
                           "Kc": 240.0, "Ti": 110.0, "Td": 0.0, "act": -1.0,
                           # (Update): The thermodynamic bug freezing T_737 to column pressure was fixed,
                           # granting FV-328404 massive physical authority over the offgas H2O content.
                           # The SP limits are now expanded to allow the operator full control.
                           "op_lo": 0.0, "op_hi": 4000.0, "sp_lo": 25.0, "sp_hi": 65.0}
        # TIC-328012 differential temp controller: TT-328013 (bottom 200) - TT-328012 (3rd tray 190) = 10 C.
        self.TIC_328012 = {"mode": "AUTO", "op": 50.0,
                           "sp": R328_C003_DT_DES, "pv": R328_C003_DT_DES,
                           "pv1": R328_C003_DT_DES, "pv2": R328_C003_DT_DES,
                           "Kc": 3.0, "Ti": 250.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 30.0}
        # LIC-328503 328C002 desorber-I bottoms level -> LV-328503 (DIRECT, 743 -> hydrolyser).
        self.LIC_328503 = {"mode": "AUTO", "op": 50.0,
                           "sp": 50.0, "pv": 50.0, "pv1": 50.0, "pv2": 50.0,
                           "Kc": 1.5, "Ti": 180.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # LIC-328504 328C003 hydrolyser level above the 1st top tray -> LV-328504 (DIRECT, 747/749 ->
        # desorber-II).  Mapping of Desorber Hydrolyzer unit.md:12,16; PFD-22 puts LV-328504 on the
        # 16.6 -> 3.7 bar letdown (747/749 @16.6, 779/780 @3.7), which is this valve.
        self.LIC_328504 = {"mode": "AUTO", "op": 50.0,
                           "sp": 50.0, "pv": 50.0, "pv1": 50.0, "pv2": 50.0,
                           "Kc": 0.2, "Ti": 300.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # LIC-328505 328C004 desorber-II bottoms level -> LV-328505 (DIRECT, 739 -> 328E007 -> 328P007
        # -> cooling-tower B.L.).  Mapping of Desorber Hydrolyzer unit.md:28,32; PFD-22 puts LV-328505
        # on the 739/740 export at 3.9 bar a.
        self.LIC_328505 = {"mode": "AUTO", "op": 50.0,
                           "sp": 50.0, "pv": 50.0, "pv1": 50.0, "pv2": 50.0,
                           "Kc": 1.45, "Ti": 180.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0}
        # FIC-328402 328D003 Comp-I absorber-feed draw 744 -> FV-328402 (REVERSE flow).
        #   VOLUMETRIC loop (m3/h): the operator enters SP in m3/h, so the seeds are
        #   M744_DES/RHO_744 (31478/1002.48 = 31.4 m3/h, PFD stream 744), sp_hi is the old
        #   60000 kg/h span divided by rho, and Kc is scaled by rho so the loop coefficient
        #   1-Kc*a*g is IDENTICAL to the mass-basis tune noted below.  _fic_flow(rho=RHO_744_KGM3)
        #   still returns kg/h, so the compartment-I and 323E003 mass balances are untouched.
        self.FIC_328402 = {"mode": "AUTO", "op": 50.0,
                           "sp": R3232_E003_M744_DES / RHO_744_KGM3, "pv": R3232_E003_M744_DES / RHO_744_KGM3,
                           "pv1": R3232_E003_M744_DES / RHO_744_KGM3, "pv2": R3232_E003_M744_DES / RHO_744_KGM3,
                           "Kc": 0.06 * RHO_744_KGM3, "Ti": 60.0, "Td": 0.0, "act": +1.0,   # AUDIT G16: restored from 0.75 to 0.06 per comment's stability analysis. Kc 1.2->0.06: design=31478 large, g=629.6, loop coef 1-Kc*a*g, a=0.0196. Kc=1.2 gives M=755 (VIOLENTLY unstable if perturbed; quiet only at bit-exact fixed-point seed). Kc=0.06 -> M=37.8, coef 0.26 monotone. Defends Domino live tie-ins.  Kc*RHO_744 holds the vol-loop coef equal.
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 60000.0 / RHO_744_KGM3}
        # FIC-328406 328D003 standby transfer pump flow (MAN 0, spare).
        # FIC-328406 indicates the PFD-741 process-condensate RECYCLE, 328E007 -> 328E001 ->
        # 328D003 Comp II (TD-005). Normally CLOSED at 100 % load (PFD 741 = 0 kg/h), so it is
        # MAN at 0 % stroke.  It is now a real VOLUMETRIC measurement through _fic_flow rather
        # than the controller being fed its own opening: design 0 -> pv 0, and stroking it in MAN
        # shows genuine m3/h.  op_des = 100 so 0 % stroke is exactly 0 flow.
        self.FIC_328406 = {"mode": "MAN", "op": 0.0,
                           "sp": 0.0, "pv": 0.0, "pv1": 0.0, "pv2": 0.0,
                           "Kc": 0.75 * RHO_741_KGM3, "Ti": 80.0, "Td": 0.0, "act": +1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": S741_CAP_KGH / RHO_741_KGM3}

        # -- 328-2 controllers (LP absorber 322C001) ---------------------------
        # PIC-322201 322C001 absorber vent pressure -> PV-322201 (DIRECT, 3.9 bar a).
        self.PIC_322201 = {"mode": "AUTO", "op": A328_PIC_OP_DES,
                           "sp": A328_C001_P_BARA, "pv": A328_C001_P_BARA,
                           "pv1": A328_C001_P_BARA, "pv2": A328_C001_P_BARA,
                           "Kc": 6.0, "Ti": 30.0, "Td": 0.0, "act": -1.0,
                           "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 2.5, "sp_hi": 5.5}
        # LIC-322502 322C001 sump level -> LV-322502 (DIRECT, 755 draw via 322P002).
        self.LIC_322502 = {"mode": "AUTO", "op": A328_LIC_OP_DES,
                           "sp": 50.0, "pv": 50.0, "pv1": 50.0, "pv2": 50.0,
                           "Kc": 1.0, "Ti": 100.0, "Td": 0.0, "act": -1.0,
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
        # L3 phase-boundary diagnostics (mushy-zone / solidification detection, Batch 2)
        self.flags = {"SCRUBBER_SOLIDIFICATION": False,
                      "STRIPPER_SOLIDIFICATION": False,
                      "CARBAMATE_DEPOSITION":    False,
                      "RATIO_PV_BAD":            False}   # L3-3 N/C measurement-validity (Batch 3)


state = State()
_ctrl_lock = threading.Lock()
clients: Set[WebSocket] = set()
last_packet: dict = {}

# Trend historian. Logging starts with the process, not with the first browser, so a pen
# opened an hour in still backfills the preceding hour.
hist = Historian()


# ----- Sim step -----
# ----- SM Flowsheet Setup -----
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.flowsheet import Flowsheet
from core.stream import Stream
from core.ejector import Ejector322F001
from core.stripper import Stripper322E001
from core.hpcc import Hpcc322E002
from core.scrubber import Scrubber322E003
from core.reactor import Reactor322R001
from core.valve import Valve322604
from core.vacuum import VacuumTrain324

_sm_flowsheet = Flowsheet("Urea HP Loop")
_ej_motive = Stream("Ejector_Motive_In")
_ej_disch = Stream("Ejector_Disch_Out")
_ej_unit = Ejector322F001("322F001_Ejector", _ej_motive, _ej_disch)

_strip_co2_in = Stream("Stripper_CO2_In")
_strip_overflow_in = Stream("Stripper_Overflow_In")
_strip_steam_in = Stream("Stripper_Steam_In")
_strip_top_gas_out = Stream("Stripper_Top_Gas_Out")
_strip_bottom_liq_out = Stream("Stripper_Bottom_Liq_Out")
_strip_unit = Stripper322E001("322E001_Stripper", _strip_co2_in, _strip_overflow_in, _strip_steam_in, _strip_top_gas_out, _strip_bottom_liq_out)

_hpcc_gas_in = Stream("HPCC_Gas_In")
_hpcc_liq_in = Stream("HPCC_Liq_In")
_hpcc_gas_out = Stream("HPCC_Gas_Out")
_hpcc_liq_out = Stream("HPCC_Liq_Out")
_hpcc_unit = Hpcc322E002("322E002_HPCC", _hpcc_gas_in, _hpcc_liq_in, _hpcc_gas_out, _hpcc_liq_out)

_scrub_offgas_in = Stream("Scrub_Offgas_In")
_scrub_wash_in = Stream("Scrub_Wash_In")
_scrub_ccw_in = Stream("Scrub_CCW_In")
_scrub_vent_out = Stream("Scrub_Vent_Out")
_scrub_carbamate_out = Stream("Scrub_Carbamate_Out")
_scrub_ccw_out = Stream("Scrub_CCW_Out")
_scrub_unit = Scrubber322E003("322E003_Scrubber", _scrub_offgas_in, _scrub_wash_in, _scrub_ccw_in, _scrub_vent_out, _scrub_carbamate_out, _scrub_ccw_out)

_react_feed_in = Stream("React_Feed_In")
_react_overflow_out = Stream("React_Overflow_Out")
_react_offgas_out = Stream("React_Offgas_Out")
_react_unit = Reactor322R001("322R001_Reactor", _react_feed_in, _react_overflow_out, _react_offgas_out)

_valve_og_in = Stream("Valve_Offgas_In")
_valve_purge_out = Stream("Valve_Purge_Out")
_valve_unit = Valve322604("HV_322604", _valve_og_in, _valve_purge_out)

_vac_evap_in = Stream("Vac_Evap_In")
_vac_v1_in = Stream("Vac_V1_In")
_vac_v2_in = Stream("Vac_V2_In")
_vac_fa1_in = Stream("Vac_FA1_In")
_vac_fa2_in = Stream("Vac_FA2_In")
_vac_mot924_in = Stream("Vac_Mot924_In")
_vac_mot927_in = Stream("Vac_Mot927_In")
_vac_mot929_in = Stream("Vac_Mot929_In")
_vac_cond_out = Stream("Vac_Cond_Out")
_vac_vent_out = Stream("Vac_Vent_Out")

# Set stream densities and viscosities for pressure drop MESH calculations
_react_feed_in.density = REACT_OVERFLOW_RHO
_react_feed_in.viscosity = 0.001
_strip_overflow_in.density = REACT_OVERFLOW_RHO
_strip_overflow_in.viscosity = 0.001
_hpcc_gas_in.density = STRIP_RHO_G_DES
_hpcc_gas_in.viscosity = 1.5e-5
_scrub_offgas_in.density = SCRUB_OFFGAS_RHO
_scrub_offgas_in.viscosity = 1.5e-5
_vac_unit = VacuumTrain324("324_VacuumTrain", _vac_evap_in, _vac_v1_in, _vac_v2_in, _vac_fa1_in, _vac_fa2_in, _vac_mot924_in, _vac_mot927_in, _vac_mot929_in, _vac_cond_out, _vac_vent_out)

_sm_flowsheet.add_unit(_ej_unit)
_sm_flowsheet.add_unit(_strip_unit)
_sm_flowsheet.add_unit(_hpcc_unit)
_sm_flowsheet.add_unit(_scrub_unit)
_sm_flowsheet.add_unit(_react_unit)
_sm_flowsheet.add_unit(_valve_unit)
_sm_flowsheet.add_unit(_vac_unit)
# ------------------------------

# ----- SM Flowsheet Setup -----
from core.flowsheet import Flowsheet
from core.stream import Stream
from core.ejector import Ejector322F001
from core.stripper import Stripper322E001
from core.hpcc import Hpcc322E002
from core.scrubber import Scrubber322E003
from core.reactor import Reactor322R001
from core.valve import Valve322604
from core.vacuum import VacuumTrain324

_sm_flowsheet = Flowsheet("Urea HP Loop")
_ej_motive = Stream("Ejector_Motive_In")
_ej_disch = Stream("Ejector_Disch_Out")
_ej_unit = Ejector322F001("322F001_Ejector", _ej_motive, _ej_disch)

_strip_co2_in = Stream("Stripper_CO2_In")
_strip_overflow_in = Stream("Stripper_Overflow_In")
_strip_steam_in = Stream("Stripper_Steam_In")
_strip_top_gas_out = Stream("Stripper_Top_Gas_Out")
_strip_bottom_liq_out = Stream("Stripper_Bottom_Liq_Out")
_strip_unit = Stripper322E001("322E001_Stripper", _strip_co2_in, _strip_overflow_in, _strip_steam_in, _strip_top_gas_out, _strip_bottom_liq_out)

_hpcc_gas_in = Stream("HPCC_Gas_In")
_hpcc_liq_in = Stream("HPCC_Liq_In")
_hpcc_gas_out = Stream("HPCC_Gas_Out")
_hpcc_liq_out = Stream("HPCC_Liq_Out")
_hpcc_unit = Hpcc322E002("322E002_HPCC", _hpcc_gas_in, _hpcc_liq_in, _hpcc_gas_out, _hpcc_liq_out)

_scrub_offgas_in = Stream("Scrub_Offgas_In")
_scrub_wash_in = Stream("Scrub_Wash_In")
_scrub_ccw_in = Stream("Scrub_CCW_In")
_scrub_vent_out = Stream("Scrub_Vent_Out")
_scrub_carbamate_out = Stream("Scrub_Carbamate_Out")
_scrub_ccw_out = Stream("Scrub_CCW_Out")
_scrub_unit = Scrubber322E003("322E003_Scrubber", _scrub_offgas_in, _scrub_wash_in, _scrub_ccw_in, _scrub_vent_out, _scrub_carbamate_out, _scrub_ccw_out)

_react_feed_in = Stream("React_Feed_In")
_react_overflow_out = Stream("React_Overflow_Out")
_react_offgas_out = Stream("React_Offgas_Out")
_react_unit = Reactor322R001("322R001_Reactor", _react_feed_in, _react_overflow_out, _react_offgas_out)

_valve_og_in = Stream("Valve_Offgas_In")
_valve_purge_out = Stream("Valve_Purge_Out")
_valve_unit = Valve322604("HV_322604", _valve_og_in, _valve_purge_out)

_vac_evap_in = Stream("Vac_Evap_In")
_vac_v1_in = Stream("Vac_V1_In")
_vac_v2_in = Stream("Vac_V2_In")
_vac_fa1_in = Stream("Vac_FA1_In")
_vac_fa2_in = Stream("Vac_FA2_In")
_vac_mot924_in = Stream("Vac_Mot924_In")
_vac_mot927_in = Stream("Vac_Mot927_In")
_vac_mot929_in = Stream("Vac_Mot929_In")
_vac_cond_out = Stream("Vac_Cond_Out")
_vac_vent_out = Stream("Vac_Vent_Out")
_vac_unit = VacuumTrain324("324_VacuumTrain", _vac_evap_in, _vac_v1_in, _vac_v2_in, _vac_fa1_in, _vac_fa2_in, _vac_mot924_in, _vac_mot927_in, _vac_mot929_in, _vac_cond_out, _vac_vent_out)

_sm_flowsheet.add_unit(_ej_unit)
_sm_flowsheet.add_unit(_strip_unit)
_sm_flowsheet.add_unit(_hpcc_unit)
_sm_flowsheet.add_unit(_scrub_unit)
_sm_flowsheet.add_unit(_react_unit)
_sm_flowsheet.add_unit(_valve_unit)
_sm_flowsheet.add_unit(_vac_unit)
# ------------------------------

def step_sim(dt: float) -> dict:
    s = state
    # Dynamic property evaluations for HP Loop
    _react_feed_in.viscosity = thermo.viscosity_liq_pas(s.react_T_overflow)
    _strip_overflow_in.viscosity = thermo.viscosity_liq_pas(s.react_T_overflow)
    _hpcc_gas_in.viscosity = thermo.viscosity_gas_pas(s.react_T_overflow)
    _scrub_offgas_in.viscosity = thermo.viscosity_gas_pas(s.a328_c001_T)

    s.sim_t += dt                        # plant clock advances with the physics, not the wall clock
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
    # DEAD-LEVER FIX (audit): P_bara was hardwired to the frozen STRIP_P_DES_BARA at every call
    # site, so eta_P evaluated to exactly 1.0 forever and synthesis pressure had NO effect on
    # stripping efficiency.  That is wrong in a way an operator would notice immediately -- raising
    # loop pressure suppresses carbamate dissociation (3 mol of gas from 1 of liquid, so Le
    # Chatelier pushes the equilibrium back) and the stripper visibly loses efficiency.
    # PT-329201 (s.p_syn_bara) is the live loop pressure; the stripper tube side sits a fixed
    # 3.3 bar above it (144.0 vs 140.7), so the live tube-side pressure is carried as a RATIO
    # anchored on each side's own design value.  At design s.p_syn_bara == SYN_P_DES_BARA exactly,
    # so the ratio is exactly 1.0 and X * 1.0 == X -- eta_P is bit-identical to the old constant.
    #
    # Gated on _STEAM_READY for the same reason step_steam is (see the steam handshake below).
    # This fix adds a feedback path that did not exist before -- loop pressure now reaches the
    # stripper split -- and the boot-pin settle would otherwise traverse a different transient and
    # capture HPCC_UA / HPCC_LIQ_DES_LIVE on a different basis (measured: +305 kg/h, 0.16 %).  Those
    # are CALIBRATION constants; they must not depend on which transient reached the design point.
    # At the settled design state s.p_syn_bara == SYN_P_DES_BARA, so gate open and gate closed give
    # the identical answer there -- the gate changes the path, never the fixed point.
    
    # Live reactor-overflow temperature feeds the stripper's sensible-heat term (TD-006), carried
    # as an offset from the reactor's own design anchor so it is exactly STRIP_FEED207_T_C at design.
    T_feed_live  = STRIP_FEED207_T_C + (s.react_T_overflow - reactor.T0_DES_C)
    
    # Dynamic Darcy-Weisbach pressure drop: dP scales with m^2 / rho
    dP_des_strip = STRIP_P_DES_BARA - SYN_P_DES_BARA
    m_strip_live = max(sum(s.react_overflow_kmolh.get(k, 0.0) * MW_COMP[k] for k in MW_COMP), 1e-6)
    m_strip_des  = max(sum(STRIP_FEED207_KMOLH.get(k, 0.0) * MW_COMP[k] for k in MW_COMP), 1e-6)
    w_urea_strip = (s.react_overflow_kmolh.get("Urea", 0.0) * MW_COMP["Urea"]) / m_strip_live
    rho_live_strip = urea_soln_rho(w_urea_strip, T_feed_live, REACT_OVERFLOW_RHO)
    # Normalise by the density the SAME correlation returns at the DESIGN overflow, not by the raw
    # PFD anchor.  urea_soln_rho() is a departure model about one global C10 reference (w,T), so it
    # only returns its `anchor` argument at that reference -- and stream 207 (34.6 % urea, 183 C)
    # is nowhere near it.  Dividing the anchor by the live value therefore gave 1.186 instead of 1.0
    # at design: dP_strip read 3.91 bar instead of 3.30, the stripper ran at 144.61 bar a instead of
    # its 144.0 design, and duty_raw/STRIP_DUTY_RAW_DES_KW -- which the MP header draw is scaled by
    # -- came out 0.9927 rather than the 1.0 the comment there asserts, opening 329D005 by
    # +0.155 kg/s at the design seed.  The off-design slope is untouched; only the datum moves.
    dP_strip_live = dP_des_strip * (REACT_OVERFLOW_RHO_DES_LIVE / max(rho_live_strip, 1e-6)) * (m_strip_live / m_strip_des)**2
    
    P_strip_live = (s.p_syn_bara + dP_strip_live if _STEAM_READY else STRIP_P_DES_BARA)
    strip = stripper_322e001(F_CO2_syn_th, T_steam_live, P_strip_live,
                             overflow_kmolh=s.react_overflow_kmolh,
                             L_feed=s.react_L_feed, W_feed=s.react_W_feed,
                             T_feed_C=T_feed_live)

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
    delayed_bot_kgh = _delay(s.tlag, "322E001_BOT_KGH_LAG", strip["bot_kgh"], 60.0, dt)
        
    # bottom-sump mass balance -> LT-322501 level (%)
    m_span_kg = STRIP_SUMP_AREA_M2 * STRIP_LEVEL_SPAN_M * STRIP_RHO_BOTTOM
    if s.strip_level <= 0.0 and drain_kgh > delayed_bot_kgh:
        drain_kgh = delayed_bot_kgh
    s.strip_level = clamp(s.strip_level
                          + k_loop_fill * (delayed_bot_kgh - drain_kgh) / 3600.0 * dt / m_span_kg * 100.0,
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
    # Internal header pressure is itself a thermodynamic disturbance.  The former exogenous-only
    # gate suppressed it, allowing the 4-bar header and HPCC shell to occupy incompatible states.
    # Keep the measured design offset (Antoine vs licensor steam-table basis), but always propagate
    # the live pressure departure.  At 4.4 bar a the bracket is exactly zero: design stays pinned.
    g_dist = 1.0
    P_LP_hpcc = s.steam.P_LP
    T_shell_lp = tsat_steam(P_LP_hpcc)
    #   AUDIT F-6/TD-007: the (T,P) phase split needs the product temperature it also produces and the
    #   live synthesis pressure -> both entered as prior-step tears (s.tlag / s.p_syn_bara), the same
    #   Sequential-Modular tearing every other recycle in this flowsheet uses.
    hpcc = hpcc_322e002(strip, ej, t_shell=T_shell_lp, gate=g_dist,
                        t_prod_prev=s.tlag.get("HPCC_TPROD", HPCC_T_PROD_DES_C),
                        p_loop=s.p_syn_bara, phi_prev=s.hpcc_phi, dt=dt)
    s.tlag["HPCC_TPROD"] = hpcc["T_prod"]        # tear for next tick's phase split
    s.hpcc_phi           = hpcc["phi_film"]      # interfacial-composition state (relaxed, pre-gate)

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
    
    # Dynamic Darcy-Weisbach pressure drop for Reactor
    dP_des_react = state.p_syn_bara - HPCC_P_DES_BARA
    m_react_live = max(sum(react["feed_kmolh"].get(k, 0.0) * MW_COMP[k] for k in MW_COMP), 1e-6)
    m_react_des  = HPCC_LIQ_DES_LIVE if HPCC_LIQ_DES_LIVE else HPCC_LIQ_DES_KGH
    w_urea_react = (react["feed_kmolh"].get("Urea", 0.0) * MW_COMP["Urea"]) / m_react_live
    rho_live_react = urea_soln_rho(w_urea_react, hpcc["T_prod"], REACT_OVERFLOW_RHO)
    dP_react_live = dP_des_react * (REACT_OVERFLOW_RHO / max(rho_live_react, 1e-6)) * (m_react_live / max(m_react_des, 1e-6))**2
    react["P_bara"] = hpcc["P_bub"] + dP_react_live
    
    # Dynamic Darcy-Weisbach pressure drop for Reactor Off-Gas: dP scales with m^2 / rho.
    # PARITY FIX (check-#2, stream-composition -> D/S pressure): the two sibling liquid lines above
    #   (stripper 5143, reactor 5285) already carry the (rho_des/rho_live) Darcy density factor, but this
    #   GAS line was m^2-only -- a change in off-gas composition (MW) or temperature did NOT move its D/S
    #   pressure drop.  rho of the compressible off-gas is ideal-gas: rho = P*MW/(R*T), so at a common line
    #   pressure  rho_des/rho_live = (MW_des/MW_live)*(T_live/T_des).  Density anchored to the reactor
    #   off-gas DESIGN vector (REACT_OFFGAS_DES) and REACT_OFFGAS_T_C: at the seed react["offgas_kmolh"]
    #   == REACT_OFFGAS_DES and s.react_T_offgas == REACT_OFFGAS_T_C -> rho_fac == 1.0 -> bit-exact pin.
    dP_des_og = REACT_OFFGAS_P_BARA - SYN_P_DES_BARA
    m_og_live = max(sum(react["offgas_kmolh"].get(k, 0.0) * MW_COMP[k] for k in MW_COMP), 1e-6)
    m_og_des  = max(sum(SCRUB_OFFGAS_KMOLH_DES.get(k, 0.0) * MW_COMP[k] for k in MW_COMP), 1e-6)
    _n_og_live = max(sum(react["offgas_kmolh"].get(k, 0.0) for k in MW_COMP), 1e-9)
    _n_og_des  = max(sum(REACT_OFFGAS_DES.get(k, 0.0) for k in MW_COMP), 1e-9)
    _mw_og_live = m_og_live / _n_og_live                                          # live off-gas mean MW
    _mw_og_des  = sum(REACT_OFFGAS_DES.get(k, 0.0) * MW_COMP[k] for k in MW_COMP) / _n_og_des
    _rho_fac_og = (_mw_og_des / max(_mw_og_live, 1e-9)) \
                  * ((s.react_T_offgas + 273.15) / (REACT_OFFGAS_T_C + 273.15))   # = rho_des/rho_live (ideal gas)
    react["P_offgas"] = s.p_syn_bara + dP_des_og * _rho_fac_og * (m_og_live / m_og_des)**2
    
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
    # TD-006 (second half) CLOSED.  This used to be duty proportional to feed MASS:
    #     strip_load  = m_feed / STRIP_FEED_DES_KGH ;  Q = STRIP_DUTY_DES_KW * strip_load * 3600
    # which was the minimum-viable fix for an earlier defect (the duty had been hardcoded, so
    # 76.7 t/h of MP steam was drawn even at zero feed).  It removed that bug but left a real one:
    # composition did not enter, so the same tonnage of pure water and of carbamate-rich reactor
    # liquor demanded identical steam, and the dominant heat sink in the unit -- carbamate
    # dissociation -- was invisible to the MP header.
    # Now the ratio comes from the per-species enthalpy balance computed inside the unit (q_carb +
    # q_nh3 + q_h2o + q_hyd + q_sens).  STRIP_DUTY_DES_KW remains the licensor anchor; only the
    # SHAPE of the off-design response comes from the balance, so the balance's 4 % absolute offset
    # cancels and never reaches the header.  At design duty_raw_kw == STRIP_DUTY_RAW_DES_KW by
    # construction (same function, same inputs), so the ratio is X/X == 1.0 and Q_strip_kjh is
    # bit-identical to the feed-proportional form it replaces.  Floored at 0.
    m_feed_strip = sum(strip["feed_kmolh"][k] * MW_COMP[k] for k in MW_COMP)   # live stripper feed (kg/h)
    strip_load   = max(m_feed_strip / STRIP_FEED_DES_KGH, 0.0)                 # 1.0 at design (kept: telemetry)
    duty_ratio   = max(strip["duty_raw_kw"] / STRIP_DUTY_RAW_DES_KW, 0.0)      # 1.0 at design (bit-exact)
    Q_strip_kjh = STRIP_DUTY_DES_KW * duty_ratio * 3600.0
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
        step_steam(s.steam, dt, m_strip, m_hpcc, s.steam.m_users9)

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
    if s.react_level_pct <= 0.0 and m_out_kgh > m_in_kgh:
        m_out_kgh = m_in_kgh
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
    # The gravity-head term the paragraph above specifies -- phi_out = phi_fwd*(L/NLL) -- had been
    # dropped, leaving phi_out level-INDEPENDENT and the level a pure integrator again: any residual
    # phi_in != 1 wound LT-322E002 to a rail at a constant rate instead of settling at L_eq.  At
    # design L == NLL so the ratio is a literal 1.0 and the design point stays bit-exact.
    phi_out_hpcc = phi_fwd * (s.hpcc_level_pct / HPCC_LEVEL_NLL_PCT)
    if s.hpcc_level_pct <= 0.0 and phi_out_hpcc > phi_in_hpcc:
        phi_out_hpcc = phi_in_hpcc
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
    live_syn_p_anchor = hpcc["P_bub"] - (HPCC_P_DES_BARA - SYN_P_DES_BARA)
    pass  # old pt_fwd block removed
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
    if s.scrub_level_pct <= 0.0 and ej["suction_kgh"] > m_cond_in:
        ej["suction_kgh"] = max(m_cond_in, 0.0)
    s.scrub_holdup_kg = clamp(s.scrub_holdup_kg + (m_cond_in - ej["suction_kgh"]) * (dt / 3600.0),
                              0.0, SCRUB_HOLDUP_MAX_KG)
    s.scrub_level_pct = clamp(s.scrub_holdup_kg / SCRUB_HOLDUP_NLL_KG * SCRUB_LEVEL_NLL_PCT,
                              0.0, 100.0)
    _valve_og_in.comp = scrub["offgas_kmolh"]
    _valve_og_in.set_state(T=scrub["T_offgas"], P=scrub["P_offgas"])
    _valve_unit.hic_pct = s.HIC_322604
    _valve_unit.solve()
    hv604 = _valve_unit.diagnostics
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
    # CP-5: the melt bubble-point can compute above the feed-supply head off-design (measured 221
    # bar a at 40 % load), but the 322E002 vessel physically cannot be pressurised past what the
    # CO2/HPCC/ejector feed delivers -- SYN_P_MAX_BARA (144.2), the ceiling main.py already declares
    # and enforces on the PT-329201 loop state.  Cap the PUBLISHED HPCC pressure at that head (raw
    # hpcc["P_bub"] is left untouched for any internal use).  At design P_bub == SYN_P_MAX_BARA
    # exactly, so min() binds at equality and the value is byte-identical -> pin unaffected.
    d_HPCC_P    = min(_lag1(s.tlag, "HPCCP", hpcc["P_bub"], HPCC_P_TAU_S, dt), SYN_P_MAX_BARA)
    d_TT322002  = _lag1(s.tlag, "TT322002", scrub["T_overflow"],                       SCRUB_T_TAU_S,   dt)
    d_TT322011  = _lag1(s.tlag, "TT322011", scrub["T_offgas"],                         OFFGAS_T_TAU_S,  dt)
    d_TT322011l = _lag1(s.tlag, "TT322011l", hv604["T_out"],                           OFFGAS_T_TAU_S,  dt)
    d_TT329125  = _lag1(s.tlag, "TT329125", scrub["t_ccw_out"],                        CCW_T_TAU_S,     dt)
    d_AT322701  = _lag1(s.tlag, "AT322701", react_nc_ratio(react["overflow_kmolh"]),  AT_322701_TAU_S, dt)

    # ==================================================================================
    #  UNIT 323 - LP RECIRCULATION & PRE-EVAPORATION  (rigorous state-space, conservative)
    #  Boundary feed = 322E001 letdown bottoms:  m_feed = drain_kgh (kg/h) at T = TT_323001
    #  (post-LV-322501 flash), transported down the letdown line as ONE packet so mass,
    #  temperature and composition arrive together after the line's plug-flow dead time.
    #  Four lumped liquid stages; each stage carries an
    #  inventory ODE  dM/dt = m_in - m_vap - m_out  and a well-mixed energy ODE
    #        M*cp*dT/dt = m_in*cp*(T_in - T) + Q - m_vap*lambda
    #  integrated with the live sub-step dt.  Vapor rates are the DESIGN mass split fractions
    #  of the live inflow, so mass closes every tick by construction:
    #        m_feed == SUM(vapor) + product_317 + d(inventory)/dt .
    #  All latent/duty coefficients were back-solved at the design seed, so at boot every
    #  dM/dt == dT/dt == 0 (the MB/PFD anchors are the exact fixed point).
    # ==================================================================================
    # AUDIT C10 — cp is a PROPERTY, not a constant.  One lumped 2.5 kJ/kg.K used to cover the 44 %
    # granulation return at 40 C, the 55.9 % stripper bottoms at 119 C and the 80 % product at 99 C.
    # Each stream now carries its own, as a departure from that lumped anchor so every back-solved
    # lambda and UA above stays exactly valid (see the R323_CP_*_DES block).  The feed composition is
    # hoisted above the energy terms because the FEED's cp is what the feed sensible duty needs.
    _cp = lambda w, T, des: R323_CP_SOLN + (urea_soln_cp(w, T) - des)   # noqa: E731 -- departure form
    # Departure state at the 322E001 nozzle, then plug-flow transport of the CLOSED packet down the
    # letdown line.  Mass, temperature and composition leave together and arrive together after
    # rho*V/m_dot, so a stripper split change can no longer reach 323C003 within the same tick.
    m_dep_323  = max(drain_kgh, 0.0)                       # live 322E001 bottoms leaving (kg/h)
    T_dep_323  = TT_323001                                 # C, post-LV-322501 flash
    w_dep_323  = _w_norm({k: strip["bot_mass_pct"].get(k, 0.0) for k in SOL_SPECIES})
    _pkt_dep_323 = _cq_packet(m_dep_323, T_dep_323, w_dep_323,
                              _cp(w_dep_323.get("Urea", 0.0), T_dep_323, R323_CP_S208_DES))
    _pkt_arr_323 = _transport_process(s, "322E001_TO_323C003", _pkt_dep_323, m_dep_323, dt)
    if _pkt_arr_323 == _pkt_dep_323:
        # Settled line: reuse the ORIGINAL scalars so no re-normalisation epsilon can move the
        # pinned design seed.  The arrived packet is equal by value, not merely close.
        m_feed_323, T_feed_323, w_feed_323 = m_dep_323, T_dep_323, w_dep_323
    else:
        m_feed_323 = _pkt_arr_323.mass_kgh
        T_feed_323 = _pkt_arr_323.temperature_c
        w_feed_323 = _w_norm(_pkt_arr_323.mass_fraction)
    cp_feed323 = _cp(w_feed_323.get("Urea", 0.0),          T_feed_323,        R323_CP_S208_DES)
    cp_c003    = _cp(s.w_c003.get("Urea", 0.0),            s.r323_c003_T,     R323_CP_C003_DES)
    cp_f004    = _cp(s.w_f004.get("Urea", 0.0),            s.r323_f004_T,     R323_CP_F004_DES)
    cp_f010    = _cp(s.w_f010.get("Urea", 0.0),            s.r323_f010_T,     R323_CP_F010_DES)
    cp_331     = _cp(W_S331["Urea"],                       R323_M331_T_C,     R323_CP_S331_DES)

    # ---- Stage 1: Rectifying Column 323C003 + Recirc Heater 323E002  (hold 135 C) ------------
    #  Cascade  TIC-323007 (temp master, EU) -> PIC-329202 (LP-steam chest-P slave) -> heater duty.
    tic07_op  = _ctrl_ipd(s.TIC_323007, s.r323_c003_T, dt)                        # steam-P demand (bar a)
    pic02_pv  = clamp(s.PIC_329202["op"] / 100.0 * s.steam.P_LP, 0.0, s.steam.P_LP)  # live LP-header chest P
    pic02_op  = _ctrl_ipd(s.PIC_329202, pic02_pv, dt, cas_sp=tic07_op)            # steam valve stroke (%)
    # AUDIT THERMO-3: Apply transport lag to steam header pressure before thermal calc.
    # Same rationale as 324E001 — steam header responds in ~1 s, but column liquid inventory
    # (323C003 holdup ~1800 kg, residence time 86-100 s measured) should not start moving in 1 s.
    # The lag constant is the LIQUID residence time R323_C003_M_TAU_S (120 s), not the 1 s gas-space
    # pressure constant: it is the liquid thermal capacitance that sets how fast TI-323003 moves.
    p_lp_lagged_c003 = _lag1(s.tlag, "323C003_P_LP_thermal", s.steam.P_LP, R323_C003_M_TAU_S, dt)
    p_chest_e002 = steam_chest_pressure(pic02_op, p_lp_lagged_c003)
    # AUDIT F-10 — a CONDENSING-STEAM chest can only ADD heat.  Un-floored, shutting PV-329202
    # clamps p_chest to 0.02 bar a (tsat ~17.5 C) and UA·(tsat − T) becomes a large NEGATIVE duty,
    # i.e. the heater turns into a refrigerator and drags the column to ~14 C.  Physically the
    # chest simply stops condensing and Q -> 0.  At design Q is strongly positive -> max() is the
    # identity -> bit-exact.  Same floor applied to 323E010, 324E001, 324E003.
    Q_e002_kw = max(R323_E002_UA_KW * (tsat_steam(p_chest_e002) - s.r323_c003_T), 0.0)  # heater duty (kW)
    # AUDIT F-2 — boil-up is ENERGY-LIMITED, not a frozen split fraction.  q_avail is the latent
    # duty actually left after the feed has been brought to the column temperature; the overhead
    # cannot exceed what that duty can vaporise.  min() with the composition split keeps the
    # design point bit-exact (both branches evaluate to R323_M305_DES) and makes the correct
    # failure mode appear: PV-329202 shut -> Q_e002 -> 0 -> boil-up collapses instead of the
    # temperature ODE absorbing an impossible latent load.
    # AUDIT TD-014 — the boil-up above used to consume the WHOLE available duty, and R323_LAMBDA_305
    # is back-solved as Q305_DES/(M305_DES/3600), so m_305·λ/3600 cancelled q_avail term for term and
    # the column-temperature ODE below evaluated to IDENTICALLY ZERO on this branch.  TIC-323007 was
    # then integrating against a plant of zero gain: whatever it did to the reboiler was exactly
    # undone by the boil-up it produced, T never moved off 135.00001 °C, and its velocity-form
    # integral walked the steam valve down forever at a rate set by Kc·dt/Ti — i.e. a LINEAR,
    # NEVER-ARRESTING, TICK-INVARIANT ramp.  That ramp is the whole of TD-014: measured −0.0041 pp/h
    # of urea here, −0.0044 at 323F004, −0.0067 at 323F010, with the stripper bottoms feeding it
    # bit-flat for 6 h.  It was one-sided because the split branch caps the other direction.
    #
    # The closure is the one 323F004 already uses and the one the physics demands: the liquid sits at
    # its BUBBLE POINT, so the duty that is not spent boiling walks the holdup toward it over the
    # stage's own residence time.  Substituting into the ODE gives exactly dT/dt = (T_bub − T)/τ, so
    # energy is still conserved and the temperature is a real state with a real driver.  323C003's
    # bubble point rides the live column pressure (PT-323201), which is itself driven by the live
    # top-vapour rate — so TIC-323007 now has a genuine, correctly-signed plant: more duty -> more
    # 305 -> higher P -> higher T_sat -> higher T.
    # Design: P == 4.1 -> the tsat bracket is a literal 0.0 -> T_bub == 135.0 == T -> q_relax == 0.0
    # -> q_avail − 0.0 == q_avail bit-identically -> m_305 == R323_M305_DES exactly (the min() ties).
    T_bub_c003 = R323_C003_T_SP_C + (tsat_steam(s.r323_c003_P) - _R323_TSAT_C003_DES)
    q305_relax_kw = (s.r323_c003_M * cp_c003 * (T_bub_c003 - s.r323_c003_T)
                     / R323_C003_M_TAU_S)                                         # kW retained to reach bubble point
    T_strip_bot = s.tlag.get("TT_322004", STRIP_T_BOTTOM_DES_C)
    T_flash_sat = TT_323001
    q_flash_avail_kw = (m_feed_323 / 3600.0 * cp_feed323 * (T_strip_bot - T_flash_sat))  # kW released by letdown flash
    m_flash_gas = max(R323_M305_DES * (q_flash_avail_kw / R323_Q305_DES_KW), 0.0)
    m_pool_vap  = max(R323_M305_DES * ((Q_e002_kw - q305_relax_kw) / R323_Q305_DES_KW), 0.0)
    m_305       = min(R323_PHI_V305 * m_feed_323, m_flash_gas + m_pool_vap)       # top vapor -> 323E003 LPCC (305, kg/h)
    s._debug_m_feed_323 = m_feed_323
    s._debug_m_305 = m_305
    s._debug_m_flash = m_flash_gas
    s._debug_m_pool  = m_pool_vap
    q305_avail_kw = q_flash_avail_kw + Q_e002_kw                                  # total available latent kW
    lvl_c003  = clamp(s.r323_c003_M / R323_C003_M_FULL * 100.0, 0.0, 100.0)
    lv501_op  = _ctrl_ipd(s.LIC_323501, lvl_c003, dt)                             # LV-323501 stroke (%)
    m_314     = max(R323_M314_DES * (lv501_op / R323_LV501_OP_DES), 0.0)          # bottom drain -> flash (kg/h)
    P_c003    = (q305_avail_kw - m_305 / 3600.0 * R323_LAMBDA_305)               # net kW on holdup

    M_c003_pre = s.r323_c003_M
    # Departure state of the 323C003 bottom drain, captured BEFORE the stage advances its own T and
    # composition: this is the state of the material actually leaving on this sub-step, and it is the
    # state cp_c003 was evaluated at.
    T_dep_314 = s.r323_c003_T
    w_dep_314 = s.w_c003
    s.r323_c003_T = s.r323_c003_T + P_c003 * dt / max(M_c003_pre * cp_c003, 1e-6)
    if M_c003_pre <= 1.0 and m_314 > (m_feed_323 - m_305):
        m_314 = max(m_feed_323 - m_305, 0.0)
    # ---- 323C003 -> 323F004 drain line: plug-flow transport of the CLOSED packet ---------------
    # m_314 stays the OUTFLOW in the 323C003 inventory and species ODEs below (the material has
    # left the column); only 323F004's inlet terms consume the ARRIVED packet, so the line
    # inventory legitimately absorbs the transient difference.
    _pkt_dep_314 = _cq_packet(m_314, T_dep_314, w_dep_314, cp_c003)
    _pkt_arr_314 = _transport_process(s, "323C003_TO_323F004", _pkt_dep_314, m_314, dt)
    if _pkt_arr_314 == _pkt_dep_314:
        m_314_in, T_314_in, w_314_in, cp_314_in = m_314, T_dep_314, w_dep_314, cp_c003
    else:
        m_314_in  = _pkt_arr_314.mass_kgh
        T_314_in  = _pkt_arr_314.temperature_c
        w_314_in  = _w_norm(_pkt_arr_314.mass_fraction)
        cp_314_in = _cp(w_314_in.get("Urea", 0.0), T_314_in, R323_CP_C003_DES)
    s.r323_c003_M = max(M_c003_pre + (m_feed_323 - m_305 - m_314) / 3600.0 * dt, 1.0)
    # AUDIT F-8/TD-009: species balance on the SAME flows the mass ODE above just used.  The feed
    # composition is the LIVE stripper bottoms (renormalised onto the six solution species), so a
    # change in strip efficiency now propagates all the way to the product -- previously the whole
    # downstream train was blind to it.  y_305 follows the live liquid through the relative
    # volatilities (C6 normalisation); the biuret extent is the real 2 Urea -> Biuret + NH3.
    y_305      = sol_vapour_y(s.w_c003, SOL_C003["alpha"])
    xi_c003    = sol_biuret_xi("C003", M_c003_pre, s.w_c003, s.r323_c003_T)
    s.w_c003   = sol_advance(s.w_c003, M_c003_pre, s.r323_c003_M, m_feed_323, w_feed_323,
                             m_305, y_305, m_314, xi_c003, dt)
    # PT-323201 two-path gas-load coupling.  The column is charged by TWO independent
    # carbamate-gas sources, and each gets its own ratio so neither is inferred from the other:
    #   stream 301  opening LV-322501 -> hotter//more bottoms flashing at 4.1 bar a -> more
    #               m_flash_gas.  Normalised by R323_M_FLASH_GAS_DES_KGH.
    #   stream 302  more 323E002 duty (PV-329202 -> chest pressure -> tsat) -> more gas evolved
    #               in the heater and returned below the bed -> more m_pool_vap.  Normalised by
    #               R323_M_POOL_VAP_DES_KGH.
    # m_305 is the column OUTLET (301 + 302 less what condenses on the bed), so driving an inlet
    # term with it would make the total feed back on itself.
    # The empirical field residual rides the VALVE ratio, which is exactly 1.0 at design, rather
    # than m_flash_gas: the latter carries a small steady-state offset from its live temperature
    # terms, and the 4.61 bar/ratio field gain would amplify that into a design-point error.
    # `s.r3232_d001_P` is the beginning-of-substep E003/D001 pressure; that state is advanced
    # later, preserving the explicit tear.
    r_flash_c003 = m_flash_gas / max(R323_M_FLASH_GAS_DES_KGH, 1e-6)
    r_e002_c003  = m_pool_vap  / max(R323_M_POOL_VAP_DES_KGH,  1e-6)
    r_lv_c003    = drain_kgh / STRIP_BOT_DES_KGH
    p_c003_tgt = c003_pressure_target_bara(r_flash_c003, r_e002_c003, s.r3232_d001_P,
                                           r_lv_c003)
    s.r323_c003_P = clamp(
        s.r323_c003_P + (p_c003_tgt - s.r323_c003_P) / R323_C003_P_TAU_S * dt,
        1.0,
        12.0,
    )

    # ---- Stage 2: Flash Tank 323F004  (adiabatic letdown 4.1 -> 1.13 bar, hold 106 C) --------
    # AUDIT F-1 — TRUE isenthalpic flash (was a frozen split fraction of m_314, so a ±30 °C swing
    # in the Stage-1 outlet produced identical vapour).  Two coupled statements:
    #   (a) saturation constraint  T_flash = Tsat(P_drum) anchored at the design bubble point;
    #   (b) enthalpy balance       m_701·λ_701 = m_314·cp·(T_in − T_flash) − M·cp·(T_sat − T)/τ
    #       i.e. the sensible surplus of the letdown flashes off, less whatever is needed to walk
    #       the drum to its bubble point over its own liquid residence time.  Substituting (b) into
    #       the energy ODE below yields exactly dT/dt = (T_sat − T)/τ, so energy stays conserved.
    # Design: P == 1.13 -> T_sat == 106.0 -> relax term ≡ 0 and q701_avail_kw == R323_Q701_DES_KW
    # bit-identically (same operand order) -> m_701 == R323_M701_DES exactly.
    T_sat_f004 = R323_F004_T_SP_C + (tsat_steam(s.r323_f004_P) - _R323_TSAT_F004_DES)
    q701_relax_kw = (s.r323_f004_M * cp_f004 * (T_sat_f004 - s.r323_f004_T)
                     / R323_F004_M_TAU_S)                                         # kW retained to reach bubble point
    q701_avail_kw = m_314_in / 3600.0 * cp_314_in * (T_314_in - s.r323_f004_T)      # kW released by the letdown
    m_701     = max(R323_M701_DES * ((q701_avail_kw - q701_relax_kw) / R323_Q701_DES_KW),
                    0.0)                                                          # flash vapor -> LPCC (701, kg/h)
    lvl_f004  = clamp(s.r323_f004_M / R323_F004_M_FULL * 100.0, 0.0, 100.0)
    lv505_op  = _ctrl_ipd(s.LIC_323505, lvl_f004, dt)                            # LV-323505 stroke (%)
    m_319     = max(R323_M319_DES * (lv505_op / R323_LV505_OP_DES), 0.0)          # drain -> pre-evaporator (kg/h)
    # ---- 323F004 -> 323F010 drain line (LV-323505): plug-flow transport of the CLOSED packet ----
    # Departure state is the pre-advance drum state, i.e. the state of the liquid actually leaving on
    # this sub-step and the state cp_f004 was evaluated at.
    _pkt_dep_319 = _cq_packet(m_319, s.r323_f004_T, s.w_f004, cp_f004)
    _pkt_arr_319 = _transport_process(s, "323F004_TO_323F010", _pkt_dep_319, m_319, dt)
    if _pkt_arr_319 == _pkt_dep_319:
        m_319_in, T_319_in, w_319_in, cp_319_in = m_319, s.r323_f004_T, s.w_f004, cp_f004
    else:
        m_319_in  = _pkt_arr_319.mass_kgh
        T_319_in  = _pkt_arr_319.temperature_c
        w_319_in  = _w_norm(_pkt_arr_319.mass_fraction)
        cp_319_in = _cp(w_319_in.get("Urea", 0.0), T_319_in, R323_CP_F004_DES)
    P_f004    = (m_314_in / 3600.0 * cp_314_in * (T_314_in - s.r323_f004_T)
                 - m_701 / 3600.0 * R323_LAMBDA_701)                              # adiabatic (no Q) kW
    M_f004_pre = s.r323_f004_M
    s.r323_f004_T = s.r323_f004_T + P_f004 * dt / max(M_f004_pre * cp_f004, 1e-6)
    s.r323_f004_M = max(M_f004_pre + (m_314_in - m_701 - m_319) / 3600.0 * dt, 1.0)
    y_701      = sol_vapour_y(s.w_f004, SOL_F004["alpha"])          # AUDIT F-8: flash vapour comp
    xi_f004    = sol_biuret_xi("F004", M_f004_pre, s.w_f004, s.r323_f004_T)
    s.w_f004   = sol_advance(s.w_f004, M_f004_pre, s.r323_f004_M, m_314_in, w_314_in,
                             m_701, y_701, m_319, xi_f004, dt)
    #  323F004 hydraulic coupling: forward pressure accumulation from live flash-vapour flow (701).
    #  Opening LV-323501 raises m_314 -> m_701 > design => flash-drum P relaxes UP (feeds PIC-323203 LP node).
    p_f004_tgt = R323_F004_P_BARA + R323_F004_P_GAIN * (m_701 - R323_M701_DES) / R323_M701_DES
    s.r323_f004_P = clamp(s.r323_f004_P + (p_f004_tgt - s.r323_f004_P) / R323_F004_P_TAU_S * dt, 0.3, 6.0)

    # ---- Stage 3: Pre-evaporator 323F010 + Heater 323E010  (vacuum 0.46 bar, hold 99 C) ------
    #  Cascade  TIC-323012 (temp master) -> PIC-329208 (LP-steam chest-P slave) -> heater duty.
    #  Uncontrolled separator -> design-anchored hydraulic outlet; holdup is a real state.
    #  AUDIT F-11: stream 331 (urea-recovery return from the granulation scrubber) joins stream 319
    #  ahead of 323E010.  It is a battery-limit inflow -- the granulation scrubber is outside the
    #  simulated boundary -- so it is a constant here, exactly like the 323C005 demin make-up
    #  (ui_guidelines.md §4).  It is COLD (40 C) and 55 % water, so it both loads the heater and
    #  feeds the vacuum vapour; without it the stage could not reach the PFD's 80 % product.
    m_331     = R323_M331_DES                                                     # kg/h, PFD stream 331
    tic12_op  = _ctrl_ipd(s.TIC_323012, s.r323_f010_T, dt)                        # steam-P demand (bar a)
    pic08_pv  = clamp(s.PIC_329208["op"] / 100.0 * s.steam.P_LP, 0.0, s.steam.P_LP)
    pic08_op  = _ctrl_ipd(s.PIC_329208, pic08_pv, dt, cas_sp=tic12_op)            # steam valve stroke (%)
    # AUDIT THERMO-3: the LP header moves in ~1 s, but the 323F010 liquid inventory (240 s residence)
    # cannot follow it that fast.  Same treatment as 323C003 and 324E001: lag the chest-supply
    # pressure through the stage's own liquid residence time before it becomes a duty.
    p_lp_lagged_f010 = _lag1(s.tlag, "323F010_P_LP_thermal", s.steam.P_LP, R323_F010_M_TAU_S, dt)
    p_chest_e010 = steam_chest_pressure(pic08_op, p_lp_lagged_f010)
    Q_e010_kw = max(R323_E010_UA_KW * (tsat_steam(p_chest_e010) - s.r323_f010_T), 0.0)  # heater duty (kW, F-10 floored)
    # AUDIT F-3 — same energy limit as Stage 1: the pre-evaporator cannot evaporate more water
    # than its live LP-steam duty (plus the feed's sensible surplus) can supply.
    qevap_avail_kw = (m_319_in / 3600.0 * cp_319_in * (T_319_in - s.r323_f010_T)
                      + m_331 / 3600.0 * cp_331 * (R323_M331_T_C - s.r323_f010_T)
                      + Q_e010_kw)                                                # kW available as latent
    # Flow cap in anchored-ratio form: at design the numerator and denominator are bit-identical, so
    # the ratio is exactly 1.0 and the cap reproduces R323_MEVAP_DES exactly (the min() then ties).
    # AUDIT TD-014 — same degeneracy as Stage 1, same closure, but the lever is different.  323F010
    # runs against a FIXED 0.46 bar a vacuum boundary, so its bubble point cannot move with pressure;
    # what moves it is CONCENTRATION.  That is the correct physics for a vacuum evaporator and it is
    # what TIC-323012 actually controls on the plant: more steam -> more water off -> higher urea
    # fraction -> lower water mole fraction -> higher boiling point -> higher T.  Raoult supplies
    # that slope with no fitted constant (see bubble_T_raoult); the departure form keeps the design
    # point exact.  Design: w == W_S317 -> the bracket is a literal 0.0 -> T_bub == 99.0 == T ->
    # q_relax == 0.0 -> the ratio is exactly 1.0 -> m_evap == R323_MEVAP_DES (the min() ties).
    T_bub_f010 = (R323_F010_T_SP_C
                  + (bubble_T_raoult(R323_F010_P_BARA, s.w_f010) - R323_F010_TBUB_DES))
    qevap_relax_kw = (s.r323_f010_M * cp_f010 * (T_bub_f010 - s.r323_f010_T)
                      / R323_F010_M_TAU_S)                                        # kW retained to reach bubble point
    m_evap    = min(R323_MEVAP_DES * ((m_319_in + m_331) / (R323_M319_DES + R323_M331_DES)),
                    max(R323_MEVAP_DES * ((qevap_avail_kw - qevap_relax_kw) / R323_QEVAP_DES_KW),
                        0.0))                                                     # vapour 790 -> vac (kg/h)
    m_317     = gravity_outflow_323f010(s.r323_f010_M)                              # gravity drain -> tank (kg/h)
    # ---- 323F010 -> 323D002 product line: plug-flow transport of the CLOSED packet --------------
    _pkt_dep_317 = _cq_packet(m_317, s.r323_f010_T, s.w_f010, cp_f010)
    _pkt_arr_317 = _transport_process(s, "323F010_TO_323D002", _pkt_dep_317, m_317, dt)
    if _pkt_arr_317 == _pkt_dep_317:
        m_317_in, T_317_in, w_317_in = m_317, s.r323_f010_T, s.w_f010
    else:
        m_317_in = _pkt_arr_317.mass_kgh
        T_317_in = _pkt_arr_317.temperature_c
        w_317_in = _w_norm(_pkt_arr_317.mass_fraction)
    P_f010    = (m_319_in / 3600.0 * cp_319_in * (T_319_in - s.r323_f010_T)
                 + m_331 / 3600.0 * cp_331 * (R323_M331_T_C - s.r323_f010_T)
                 + Q_e010_kw - m_evap / 3600.0 * R323_EVAP_LAMBDA)               # net kW on holdup
    M_f010_pre = s.r323_f010_M
    s.r323_f010_T = s.r323_f010_T + P_f010 * dt / max(M_f010_pre * cp_f010, 1e-6)
    s.r323_f010_M = max(M_f010_pre + (m_319_in + m_331 - m_evap - m_317) / 3600.0 * dt, 1.0)
    # Mapping — live 323F010 vacuum (PT-323204).  The evolved vapour m_evap is pulled out through
    # HV-323605 (gas outlet, HIC-323605) and evacuated by the 324F002 ejector on HV-329605; opening
    # either raises the pull and drops the pressure.  pull ∝ P/P_des is the ejector suction-pressure
    # capacity roll-off, which makes it a stable first-order node with no controller.  Anchored: at
    # design HIC-323605 == HIC-329605 == 50 %, P == P_des and m_evap == R323_MEVAP_DES, so
    # pull == R323_MEVAP_DES and dP/dt is a literal 0.0.  (The bubble point above stays on the DESIGN
    # vacuum -- TD-016 consistency; feeding live P into the concentration would reopen the P<->m_evap
    # oscillation this repo just closed on unit 324.)
    pull_f010  = (R323_MEVAP_DES * (s.r323_f010_P / R323_F010_P_BARA)
                  * (s.HIC_323605 / R323_HIC605_DES_PCT)
                  * (s.HIC_329605 / R324_HIC9605_DES_PCT))
    s.r323_f010_P = clamp(s.r323_f010_P + R323_F010_P_KP*(m_evap - pull_f010)/3600.0*dt, 0.05, 1.0)
    y_evap     = sol_vapour_y(s.w_f010, SOL_F010["alpha"])          # AUDIT F-8: vacuum vapour comp
    xi_f010    = sol_biuret_xi("F010", M_f010_pre, s.w_f010, s.r323_f010_T)
    s.w_f010   = sol_advance(s.w_f010, M_f010_pre, s.r323_f010_M, m_319_in, w_319_in,
                             m_evap, y_evap, m_317, xi_f010, dt, m_in2=m_331, w_in2=W_S331)

    # ---- Stage 4: Urea Solution Tank 323D002  (atmospheric, two compartments) -----------------
    #  TOPOLOGY (References/323D002.md §3, confirmed by operations 2026-07-23):
    #    Comp I  --  80 m3, ACTIVE.  Every feed and discharge nozzle lands here: in = m_317 from the
    #                323F010 separator, out = m_324 drawn by 323P003A/B via LIC-323507 -> FIC-324401
    #                -> FV-324401.  LIC-323507 is its level, TI-323008 its bulk temperature.
    #    Comp II -- 300 m3, PASSIVE, LI-323504 (indication and alarms only -- no control action).
    #                It has no nozzle of its own and is DRY in normal operation; liquid reaches it
    #                only by spilling over the 10 mm internal baffle that divides the shell.
    #    TIE-IN  --  a hand-operated spool in the field, not a DCS valve.  CLOSED (default) the two
    #                compartments are hydraulically independent and whatever spilled into Comp II is
    #                stranded there.  OPENED they become connected vessels: the levels equalise and
    #                323P003 draws the pooled inventory, recovering Comp II into the forward flow.
    #                Modelled as the boolean the operator actually has, HV-323D002-TIE, because that
    #                is what it is -- there is no licensor loop number for a field spool.
    #  Opening the tie against an EMPTY Comp II is a real hazard and the model reproduces it: the
    #  head redistributes over 380 m3 instead of 80, so a 10 % Comp-I level collapses to about 2 %
    #  and 323P003 is left near its cavitation limit.  That is the scenario the button exists for.
    flow_span_324 = R323_M324_DES / 1000.0 / (R323_FV401_OP_DES / 100.0)          # t/h at 100% stroke
    tie_open   = bool(s.HV_323D002_TIE)
    d002_recyc = max(s.tlag.get("R324_recyc", 0.0), 0.0)                         # LV-324501B, one-tick tear
    d002_recyc_T = s.tlag.get("R324_recyc_T", R324_E003_T_SP_C)
    d002_recyc_w = s.tlag.get("R324_recyc_comp", s.w_e003)
    M_I_pre    = s.r323_d002_M_I
    M_II_pre   = s.r323_d002_M_II
    # AUDIT C10 — a level gauge measures VOLUME, and volume is mass over a density that moves.  The
    # spans below were mass spans built on a frozen 1300 kg/m3, so a tank of thinner (hotter, weaker)
    # liquor read low on LIC-323507 by exactly the density error while the operator saw the same
    # inventory.  ρ is now live on composition and temperature, anchored on the PFD's own 1151 for
    # streams 315/317 so the design level is bit-exact.  The volumes (80 / 300 m3) are steel and do
    # not move; only what a kilogram occupies does.
    rho_d002   = urea_soln_rho(s.w_d002.get("Urea", R324_W_IN), s.r323_d002_T, R323_D002_RHO)
    v_I_full   = R323_D002_VOL_I_M3  * rho_d002        # kg that fills Comp I at the LIVE density
    v_II_full  = R323_D002_VOL_II_M3 * rho_d002
    v_tie_full = v_I_full + v_II_full
    # Connected vessels share a HEAD, not a mass.  Both compartments are cut from the same shell, so
    # they have the same height and an equal level FRACTION is an equal head; the pooled span is the
    # sum.  With the tie shut LIC-323507 sees Comp I alone, exactly as before.
    lvl_d002_I = clamp(((M_I_pre + M_II_pre) / v_tie_full if tie_open
                        else M_I_pre / v_I_full) * 100.0, 0.0, 100.0)
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
    d002_overflow = 0.0
    if tie_open:
        # One pooled inventory redistributed to a common level fraction.  Comp II now has an outlet
        # (through the spool, into Comp I's suction), which is the whole point of opening it.
        M_tot    = clamp(M_I_pre + M_II_pre + (m_317_in + d002_recyc - m_324) / 3600.0 * dt,
                         1.0, v_tie_full)
        frac     = M_tot / v_tie_full
        M_I_new  = frac * v_I_full
        M_II_new = frac * v_II_full
    else:
        M_I_new = M_I_pre + (m_317_in + d002_recyc - m_324) / 3600.0 * dt
        if M_I_new > v_I_full:                                                    # weir spill -> Comp II
            d002_overflow = M_I_new - v_I_full
            M_I_new = v_I_full
        M_II_new = clamp(M_II_pre + d002_overflow, 0.0, v_II_full)
    s.r323_d002_M_I  = max(M_I_new, 1.0)
    s.r323_d002_M_II = max(M_II_new, 0.0)
    # TI-323008 -- Comp-I bulk temperature, now a real state instead of an echo of the upstream
    # separator.  One inlet, one outlet, no duty and no reaction:  M·cp·dT/dt = m_317·cp_in·(T_in − T).
    # The alarm this instrument carries is a LOW-temperature alarm, because a cooling tank walks the
    # 80 % liquor toward its crystallisation boundary and blocks the 323P003 suction -- so the tank
    # needs its own thermal inertia to show that at all.  At design T_in == T == 99 C, so the bracket
    # is a literal 0.0 and the seed is bit-exact.  cp is live on both sides (audit C10).
    cp_d002_in  = urea_soln_cp(w_317_in.get("Urea", R324_W_IN), T_317_in)
    cp_d002_recyc = urea_soln_cp(d002_recyc_w.get("Urea", R324_W_EV2), d002_recyc_T)
    cp_d002     = urea_soln_cp(s.w_d002.get("Urea", R324_W_IN), s.r323_d002_T)
    M_d002_T    = (M_I_pre + M_II_pre) if tie_open else M_I_pre
    s.r323_d002_T = s.r323_d002_T + (
        m_317_in / 3600.0 * cp_d002_in * (T_317_in - s.r323_d002_T)
        + d002_recyc / 3600.0 * cp_d002_recyc * (d002_recyc_T - s.r323_d002_T)
    ) * dt / max(M_d002_T * cp_d002, 1e-6)
    # AUDIT F-8: the buffer tank is a well-mixed species blender -- no vapour, no reaction (99 C,
    # atmospheric).  This is what gives the 324 feed a real composition instead of a constant.
    #
    # AUDIT B1 (ripple) -- and until now the line below defeated exactly that claim.  The strength
    # was pinned to the CONSTANT R324_W_IN, so sol_pin_strength overwrote the urea/water pair with
    # 0.80 on every tick and every upstream composition disturbance died here.  Measured: a +4 %
    # NH3 step on the live reactor overflow moved 222 of 1162 telemetry leaves, but 0 of the 66
    # belonging to unit 324 -- the evaporators were composition-blind.  (w_e001 / w_e003 below are
    # pinned to w1_live / w2_live, which are live, so this was the only frozen one of the three.)
    #
    # ATTEMPTED FIX, REVERTED 2026-07-23 -- and the reason is a finding in its own right.
    # Replacing the constant authority with "design anchor + live deviation" DID restore the ripple
    # (unit 324 went from 0 to 13 of 66 responding leaves).  But it also walked D002's urea fraction
    # to 76.515 % against the PFD stream-317 anchor of 80.00, failing four design-point tests:
    # test_design_fixed_point_holds, test_design_point_does_not_drift,
    # test_design_compositions_sit_on_their_pfd_anchors, and
    # test_species_layer_does_not_perturb_the_mass_or_energy_balance.
    #
    # RETRACTION.  That was first written up as "the 323 balance misses 80.00 by 3.5 points and the
    # pin has been masking it".  FALSE -- it was the patch's own bug, and the correction matters
    # because it changes what a future fix is allowed to look like:
    #   * w_f010 (323F010's outlet, and this tank's ONLY inlet) measures 80.0014 % urea, i.e. ON the
    #     anchor.  One inlet, one outlet, no reaction, no vapour => the tank MUST converge to it.
    #   * Comp-I holds 67 600 kg against a 92 749 kg/h draw, so it exchanges only
    #     alpha = m*dt/M = 9.5e-5 of its holdup per tick.
    #   * The patch measured its deviation against a reference captured ONCE, then fed the result
    #     back into the state that produced it.  That recursion is
    #         w_n = (A - ref) + w_{n-1}(1 - alpha) + alpha*w_f010
    #     whose fixed point is  w* = (A - ref)/alpha + w_f010.  Any constant inside the loop is
    #     amplified by 1/alpha ~ 10 495; a capture error of 0.0003 percentage points reproduces the
    #     observed 76.5150 % to four decimals (scratchpad/probe_td013_recursion.py).
    #
    # So the amplification -- not a balance error -- is the real constraint, and it ruled out EVERY
    # additive or multiplicative correction applied inside this loop.  Only two forms survived:
    #   (b) a non-recursive assignment from upstream, auth = R324_W_IN + (w_f010 - W_F010_DES):
    #       stable and bit-exact at design, but the tank then tracks its inlet with no lag;
    #   (c) no pin at all: correct dynamics AND a real holdup lag, but w_d002 then follows whatever
    #       w_f010 does, including its slow drift.
    #
    # TD-013 CLOSED 2026-07-23, option (c) -- THE PIN IS GONE.  The objection to (c) was that
    # w_f010 was on an unbounded ramp, so an unpinned tank would wander with it.  That ramp was
    # TD-014 and it is now fixed: w_f010 settles, stationary, 0.037 pp under the PFD-317 anchor,
    # which is simply where the LIVE stripper bottoms put it.  With the inlet steady there is
    # nothing left for the pin to protect against, and every reason to drop it -- it was the last
    # composition-blind node between the reactor and the evaporators (audit B1), and it fabricated
    # +0.600 kg of urea per 1000 kg of holdup per call, a straight C2 violation.
    # The tank now does what a tank does: it tracks its inlet with its own residence-time lag.
    if tie_open:
        # Connected vessels are ONE well-mixed volume, so they carry one composition.  Blend the two
        # inventories first, then advance the pool on the same flows the mass balance just used.
        M_pool_pre = M_I_pre + M_II_pre
        w_pool = ({k: (M_I_pre * s.w_d002.get(k, 0.0) + M_II_pre * s.w_d002_II.get(k, 0.0))
                      / M_pool_pre for k in SOL_SPECIES}
                  if M_pool_pre > 1e-9 else dict(s.w_d002))
        w_pool = sol_advance(w_pool, M_pool_pre, s.r323_d002_M_I + s.r323_d002_M_II,
                             m_317_in, w_317_in, 0.0, w_pool, m_324, 0.0, dt,
                             m_in2=d002_recyc, w_in2=d002_recyc_w)
        s.w_d002    = w_pool
        s.w_d002_II = dict(w_pool)
    else:
        # Comp I loses mass through BOTH outlets: the pump draw and, when it is spilling, the weir.
        # The weir stream leaves at the bulk composition, so it cannot move w by itself -- passing it
        # here is a C2 bookkeeping statement, not a correction.
        w_I_new = sol_advance(s.w_d002, M_I_pre, s.r323_d002_M_I, m_317_in, w_317_in,
                              0.0, s.w_d002, m_324 + d002_overflow * 3600.0 / max(dt, 1e-9),
                              0.0, dt, m_in2=d002_recyc, w_in2=d002_recyc_w)
        if d002_overflow > 0.0 and s.r323_d002_M_II > 1e-9:      # the spill carries Comp-I liquor
            s.w_d002_II = {k: (M_II_pre * s.w_d002_II.get(k, 0.0)
                               + d002_overflow * s.w_d002.get(k, 0.0)) / s.r323_d002_M_II
                           for k in SOL_SPECIES}
        s.w_d002 = w_I_new

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
    # AUDIT C10, aqueous half -- the desorption and LP-absorber trains ran on ONE frozen cp each
    # (R328_CP = A328_CP = 4.0 kJ/kg.K) across 40-200 C.  These streams are >= 98 % water, so their
    # cp is water's, and water's cp is not flat: 4.18 at 40 C, 4.29 at 140, 4.49 at 200 -- the
    # constant is 4 % low at the cold end and 11 % low in the hydrolyser.  Each vessel now carries
    # aqueous_cp() anchored on ITS OWN design temperature, so every value equals the frozen constant
    # bit-exactly at the design seed (every back-solved lambda/UA and the boot-pinned
    # A328_LAMBDA_ABS are therefore untouched) and tracks IAPWS off design.
    cp_328c002 = aqueous_cp(R328_CP, R328_C002_T_BOT_BOT, s.a328_c002_T)
    cp_328c003 = aqueous_cp(R328_CP, R328_C003_T,     s.a328_c003_T)
    cp_328c004 = aqueous_cp(R328_CP, R328_C004_T,     s.a328_c004_T)
    cp_328d001 = aqueous_cp(R328_CP, R328_D001_T,     s.a328_d001_T)
    cp_328d3i  = aqueous_cp(A328_CP, A328_D003_TI,    s.a328_d003_TI)
    cp_328d3ii = aqueous_cp(A328_CP, A328_D003_TII,   s.a328_d003_TII)
    cp_322c001 = aqueous_cp(A328_CP, A328_C001_T,     s.a328_c001_T)
    m702_prev  = s.tlag.get("R3232_702", A323_C005_M702_DES)
    m756_prev  = s.tlag.get("R322_756", A323_C005_M756_DES)
    m708_prev  = s.tlag.get("R324_708", A323_C005_M708_DES)
    m748_prev  = s.tlag.get("R328_748",   R328_C002_M748_DES)
    m750_prev  = s.tlag.get("R328_750",   R328_C002_M750_DES)
    m775_prev  = s.tlag.get("R328_775",   R328_C002_M775_DES)
    m718A_prev = s.tlag.get("R3232_718A", R3232_M718A_DES)
    m744_prev  = s.tlag.get("R3232_744",  R3232_E003_M744_DES)
    m718B_prev = s.tlag.get("R3232_718B", R3232_M718B_DES)
    m931_prev  = s.tlag.get("R328_M931",  R328_C004_M931_DES)
    m739_prev  = s.tlag.get("R328_739",   R328_C004_M739_DES)   # 328C004 bottoms -> 328E007 -> 740

    # ----- Stage 1 : 323C005 vent scrub -> 328V001 -> Comp-II feed --------
    Tc005    = s.a323_c005_T
    gas_c005 = m702_prev + m708_prev
    m_341    = A323_C005_VENT_DES * gas_c005 / (A323_C005_M702_DES + A323_C005_M708_DES)
    abs_c005 = max(gas_c005 - m_341, 0.0)
    in_c005  = m756_prev + gas_c005
    bot_c005 = A323_C005_BOT_DES * (s.a323_c005_M / A323_C005_M_DES)
    P_c005   = ((m756_prev/3600.0*R3232_CP*(A328_C001_T - Tc005)
                 + m702_prev/3600.0*R3232_CP*(45.0 - Tc005)
                 + m708_prev/3600.0*R3232_CP*(121.0 - Tc005))
                + abs_c005/3600.0*A323_C005_LAM)
    s.a323_c005_T = Tc005 + P_c005*dt/max(s.a323_c005_M*R3232_CP, 1e-6)
    s.a323_c005_M = max(s.a323_c005_M + (m756_prev + abs_c005 - bot_c005)/3600.0*dt, 1.0)

    # ----- Stage 2 : 328D003 active bays I/II + communicating accumulation bay III ----
    TI       = s.a328_d003_TI
    m_401    = _fic_flow(s.FIC_323401, R3232_E011_M401_DES, 50.0, s.tlag, "F_323401", dt,
                         rho=RHO_401_KGM3)                        # volumetric loop, returns kg/h
    m_402    = _fic_flow(s.FIC_323402, R3232_E011_M402_DES, 50.0, s.tlag, "F_323402", dt,
                         rho=RHO_791_KGM3)         # SP in m3/h, returns kg/h
    # Stream 793: normally-closed spare off the same Comp-II discharge header as 735/791/734.
    # Design stroke 0 % -> 0 kg/h (PFD-22 col 793), full stroke = one branch capacity.  Opening it
    # draws real liquid out of Comp II, so it enters that holdup ODE as an export at TII (no enthalpy
    # term: an outflow at the bulk temperature contributes nothing to P_compII).
    m_793    = _fic_flow(s.FIC_328405, S793_CAP_KGH, 100.0, s.tlag, "F_328405", dt,
                         rho=RHO_401_KGM3)                        # volumetric loop, returns kg/h
    # Stream 741 (TD-005): purified process-condensate RECYCLE 328E007 -> 328E001 -> 328D003 Comp II.
    # It is a DIVERSION of the 740 boundary export, NOT new mass: the 328C004 bottoms (739) are
    # condensed in 328E007 to stream 740, and m_741 of that is taken back to Comp II while the
    # REMAINDER (m_740 = m739_prev - m_741) leaves the envelope.  So the plant balance closes:
    # Comp II gains m_741, the 740 export loses exactly m_741. The draw is therefore clamped to the
    # condensate that actually exists this tick (m739_prev, one-tick-delayed like every other tear).
    # Normally closed (PFD 741 = 0 kg/h at 100 % load), so at design m_741 == 0, m_740 == m_739 and
    # every term below is byte-identical to the pre-741 balance -- the boot pin cannot move.
    m_741_raw = _fic_flow(s.FIC_328406, S741_CAP_KGH, 100.0, s.tlag, "F_328406", dt,
                          rho=RHO_741_KGM3)                       # volumetric loop, returns kg/h
    m_741    = min(m_741_raw, m739_prev)                          # cannot recycle more than 740 carries
    run_p002 = s.aux_pumps["322P002A"]["on"] or s.aux_pumps["322P002B"]["on"]
    m_744_cmd = _fic_flow(s.FIC_328402, R3232_E003_M744_DES, 50.0, s.tlag, "F_328402", dt,
                          rho=RHO_744_KGM3)
    m_744    = m_744_cmd * (1.0 if run_p002 else 0.0)
    m_755    = m_744
    m_735    = R328_C002_M738_DES * (s.a328_d003_MII / A328_D003_MII_DES)   # -> 738 via 328E007
    # The four explicit vacuum-condenser returns are read one tick delayed because Unit 324 is solved
    # later in the tick.  Their distinct live flows and 45/40/41/55 C thermal nodes replace the former
    # aggregate proportional split.
    m_719    = s.tlag.get("R324_719", A328_D003_M719)
    m_720    = s.tlag.get("R324_720", A328_D003_M720)
    m_721    = s.tlag.get("R324_721", A328_D003_M721)
    m_759    = s.tlag.get("R324_759", A328_D003_M759)
    in_compI = m_719 + m_720 + m_721 + m_759 - A328_D003_COMP_I_ROUNDING_KGH
    out_compI= m_744
    P_compI  = ((m_719*(A328_D003_M719_T - TI)
                 + m_720*(A328_D003_M720_T - TI)
                 + m_721*(A328_D003_M721_T - TI)
                 + m_759*(A328_D003_M759_T - TI))/3600.0*cp_328d3i
                + (m_719 + m_720 + m_721 + m_759)/3600.0*A328_D003_LAM_I)
    TI_raw = TI + P_compI*dt/max(s.a328_d003_MI*cp_328d3i, 1e-6)
    MI_raw = max(s.a328_d003_MI + (in_compI - out_compI)/3600.0*dt, 1.0)
    TII      = s.a328_d003_TII
    in_compII = bot_c005 + m_741 + A328_D003_COMP_II_ROUNDING_KGH
    out_compII = m_735 + m_401 + m_402 + m_793
    P_compII = ((bot_c005 * (A328_D003_V001_T - TII)
                 + m_741 * (A328_M741_T - TII)) / 3600.0 * cp_328d3ii)
    TII_raw = TII + P_compII*dt/max(s.a328_d003_MII*cp_328d3ii, 1e-6)
    MII_raw = max(s.a328_d003_MII + (in_compII - out_compII)/3600.0*dt, 1.0)

    # The approved openings make compartment III the shared surge volume. With no opening areas or
    # elevations, enforce the parameter-free communicating-vessel limit after the external process
    # flows. This retains every external mass term and moves internal sensible energy at the donor
    # temperature; 429/490 of a net disturbance therefore accumulates in compartment III.
    d003_masses, d003_temperatures = redistribute_communicating_compartments(
        (MI_raw, MII_raw, s.a328_d003_MIII),
        (TI_raw, TII_raw, s.a328_d003_TIII),
        (A328_D003_MI_FULL, A328_D003_MII_FULL, A328_D003_MIII_FULL),
    )
    s.a328_d003_MI, s.a328_d003_MII, s.a328_d003_MIII = d003_masses
    s.a328_d003_TI, s.a328_d003_TII, s.a328_d003_TIII = d003_temperatures

    # ----- 328E007 feed/effluent interchanger (AUDIT C10) ----------------
    #  Cold: 328D003 Comp-II draw 735 (56 C) heated against the 328C004 bottoms 739 (143 C) -> 738.
    #  Hot : 739 giving up exactly the duty the cold side took, plus the design shell loss -> 740.
    #  The hot inlet s.a328_c004_T is last tick's value (328C004 is Stage 5), i.e. the same one-tick
    #  tear m739_prev already uses -- consistent with every other recycle in this engine.
    #  Pinch-bounded: a counter-current interchanger cannot drive either outlet past the opposite
    #  inlet, so T_740 is clamped between the two live inlet temperatures.
    T_738    = s.a328_d003_TII + R328_E007_EPS_T * (s.a328_c004_T - s.a328_d003_TII)
    T740_raw = s.a328_c004_T - (m_735 * (T_738 - s.a328_d003_TII)
                                + R328_E007_LOSS_DT) / max(m739_prev, 1e-6)
    T_740    = min(max(T740_raw, min(s.a328_d003_TII, s.a328_c004_T)),
                   max(s.a328_d003_TII, s.a328_c004_T))

    # ----- Stage 3 : 328C002  Desorber-I (bottoms 139°C, floats PIC-328202)
    Tc002    = s.a328_c002_T
    m_738    = m_735
    in_c002  = m_738 + m748_prev + m750_prev + m775_prev
    lvl_c002 = s.a328_c002_M / R328_C002_M_DES * 50.0
    lic503_op= _ctrl_ipd(s.LIC_328503, lvl_c002, dt)
    m_743    = R328_C002_M743_DES * (lic503_op / 50.0)                    # bottoms -> hydrolyser
    sens_c002= ((m_738*(T_738 - Tc002)                                    # AUDIT C10: live 328E007 outlet
                 + m775_prev*(R328_D001_T   - Tc002)
                 + m748_prev*(R328_C002_T_BOT748 - Tc002)
                 + m750_prev*(R328_C002_T_BOT750 - Tc002))/3600.0*cp_328c002)
    # AUDIT F-8: the overhead is ENERGY-limited, not a frozen fraction of the inflow.  What leaves
    # overhead is what the two condensing hot recycle vapours (748 @188, 750 @140) plus the sensible
    # net can actually boil, capped by the throughput ratio.  Anchored-ratio form: both caps evaluate
    # bit-exactly to R328_C002_M737_DES at the design seed, so the min() ties and P_c002 keeps the
    # exact expression -- and therefore the exact bits -- it had under the frozen split.
    q_c002   = (sens_c002 + m748_prev/3600.0*R328_C002_LAM748
                + m750_prev/3600.0*R328_C002_LAM750)
    # AUDIT C1 — GENERATION is what the net duty can boil (the old "energy cap", unchanged in form so
    # the seed ties exactly); FLOW OUT is what the overhead line to 328D001 passes at the live column
    # pressure across 328E004.  They are now two different quantities, which is precisely what the
    # old code collapsed: it set m_737 := generation, and with LAM737 back-solved as
    # Q_DES/(m737_DES/3600) that made dT/dt algebraically zero.  Their imbalance drives the pressure,
    # and the temperature is the bubble point at the bottom node.
    gen737   = max(R328_C002_M737_DES * (q_c002 / R328_C002_Q_DES), 0.0)  # boil-up (kg/h)
    # Dynamic pressure drop coupling: flow driven by column-to-drum dP
    _p001_lag = _lag1(s.tlag, 'P_D001_lag', s.a328_d001_P, 2.0, dt)
    _p002_lag_737 = _lag1(s.tlag, 'P_C002_lag_737', s.a328_c002_P, 2.0, dt)
    dP_737   = max(_p002_lag_737 - _p001_lag, 0.001)
    dP_737   = max(s.a328_c002_P - s.a328_d001_P, 0.001)
    m_737    = R328_C002_M737_DES * math.sqrt(dP_737 / R328_E004_DP)
    M_c002_pre = s.a328_c002_M
    s.a328_c002_P = max(s.a328_c002_P + R328_C002_P_KP*(gen737 - m_737)/3600.0*dt, 0.1)
    s.a328_c002_T = tsat_steam(s.a328_c002_P + R328_C002_DP_COL)          # bubble point at the bottom
    s.a328_c002_M = max(M_c002_pre + (in_c002 - m_737 - m_743)/3600.0*dt, 1.0)
    # Species: four inlets.  The two vapour recycles carry LAGGED compositions, the same tear the
    # flows already use (m748_prev / m750_prev) -- 328C003 and 328C004 are solved later in the tick.
    a_c002   = des_alpha_live("C002", Tc002, m748_prev + m750_prev, m_743)
    s.w_328c002, y_737 = des_advance(s.w_328c002, s.a328_c002_M,
                                     [(W_S738, m_738), (W_S775, m775_prev),
                                      (s.y_328_748, m748_prev), (s.y_328_750, m750_prev)],
                                     m_737, a_c002, m_743, 0.0, dt)

    # ----- Stage 4 : 328C003  Hydrolyser (200°C, MP-steam 911) -----------
    Tc003    = s.a328_c003_T
    m_746    = m_743                                                     # via 328E021
    # 328E021 cold outlet (stream 746, TT-328009): C002 bottoms 139 heated by C003 bottoms 200.
    #   eps in (0,1) => T_746 is a convex combination of the two live inlets and can never cross
    #   either, so no clamp is needed.  At design 139 + (51/61)*(200-139) = 190.0 exactly.
    T_746    = s.a328_c002_T + R328_E021_EPS_T * (Tc003 - s.a328_c002_T)
    m_911    = _fic_flow(s.FIC_329402, R328_C003_M911_DES, 50.0, s.tlag, "F_329402", dt)
    in_c003  = m_746 + m_911
    pic203b_op = _ctrl_ipd(s.PIC_328203, s.a328_c003_P, dt)
    m_748    = R328_C003_M748_DES * (pic203b_op / R328_C003_PV_OP_DES)    # OVHD relief -> 328C002
    # AUDIT F-7/TD-008 — the overhead generation is now the REACTION plus the strip, not a frozen
    # split fraction of the inflow.  gas_hyd is what urea hydrolysis actually makes; gas_str is what
    # the MP steam carries over and scales with the live 911 flow.  Both == design at the seed, so
    # gen748 == R328_C003_M748_DES bit-exact and the pressure ODE below stays stationary.
    x_hyd_328  = hydrolysis_x_328c003(
        Tc003, m_746,
        w_urea=s.w_328c002.get("Urea", R328_C003_W_UREA_746),
        w_h2o=s.w_328c002.get("H2O", W_S743["H2O"]),
    )
    # AUDIT F-8: the urea load is now READ OFF the live 328C002 bottoms vector instead of a hardcoded
    # fraction.  At the seed w_328c002["Urea"] == W_S743["Urea"] == R328_C003_W_UREA_746, so this is
    # bit-identical at design -- but off-design the hydrolyser now sees whatever 328C002 actually
    # passes it, which is the whole point of giving unit 328 a species balance.
    urea_in_328 = m_746 * s.w_328c002["Urea"]
    xi_hyd_328 = urea_in_328 / MW_SOL["Urea"] * x_hyd_328                 # kmol/h urea destroyed
    gas_hyd    = xi_hyd_328 * R328_HYD_GAS_MW                             # kg/h NH3 + CO2 produced
    gas_str    = R328_C003_GASSTR_DES * (m_911 / R328_C003_M911_DES)      # kg/h stripped by MP steam
    gen748   = gas_hyd + gas_str
    lvl_c003 = s.a328_c003_M / R328_C003_M_DES * 50.0
    lic504_op= _ctrl_ipd(s.LIC_328504, lvl_c003, dt)
    m_747    = R328_C003_M747_DES * (lic504_op / 50.0)                    # bottoms -> desorber-II
    # AUDIT F-7: urea slipping through unreacted -> AI-328701.  A MASS-BALANCE result now, not the
    # read-only ppm_infer_328701 soft sensor running alongside an unrelated split fraction.
    ppm_urea_747 = urea_in_328 * (1.0 - x_hyd_328) / max(m_747, 1e-6) * 1e6
    sens_c003= m_746/3600.0*cp_328c003*(T_746 - Tc003)
    q_hyd_328 = xi_hyd_328 * R328_HYD_DH_KJMOL * 1000.0 / 3600.0
    P_c003   = (sens_c003 + m_911/3600.0*R328_C003_M911_DH
                - m_748/3600.0*R328_C003_LAM748 - q_hyd_328)
    s.a328_c003_P = max(s.a328_c003_P + R328_C003_P_KP*(gen748 - m_748)/3600.0*dt, 0.1)
    M_c003_pre = s.a328_c003_M
    s.a328_c003_T = Tc003 + P_c003*dt/max(M_c003_pre*cp_328c003, 1e-6)
    s.a328_c003_M = max(M_c003_pre + (in_c003 - m_748 - m_747)/3600.0*dt, 1.0)
    # Species: the hydrolyser is a LIQUID-FILLED column (Stamicarbon, "Zero waste urea production"),
    # not a stripping cascade, so its volatilities stay at the design anchor -- no Kremser stage
    # correction.  The reaction extent is the live Arrhenius xi_hyd_328 computed above.
    s.w_328c003, y_748 = des_advance(s.w_328c003, s.a328_c003_M,
                                     [(s.w_328c002, m_746), (W_STEAM, m_911)],
                                     m_748, DES_C003["alpha"], m_747, xi_hyd_328, dt)
    s.y_328_748 = y_748

    # ----- Stage 5 : 328C004  Desorber-II (143°C, LP-steam 931, FFIC) -----
    Tc004    = s.a328_c004_T
    m_749    = m_747                                                     # via 328E021 (hot side)
    # 328E021 hot outlet (stream 749): C003 bottoms 200 giving up heat to the C002-bottoms cold side.
    #   CONSERVATION form, not a second independent effectiveness -- the duty the hot stream loses is
    #   exactly the duty the cold side took, m_746*(T_746 - T_c002), plus the design shell loss
    #   R328_E021_LOSS_DT, so the interchanger cannot create or destroy energy off-design.
    #   At design: 200 - (33769*51 + 49005)/34062 = 200 - 52 = 148.0 EXACTLY (every term is an
    #   integer-valued float), so switching sens_c004 off the frozen R328_C004_T749 is bit-identical
    #   at the design point and the boot pin cannot move.
    #   Bounded by the two live inlet temps: the raw balance diverges as m_749 -> 0, but a
    #   counter-current interchanger cannot cool the hot stream past the cold-side inlet (pinch).
    T749_raw = Tc003 - (m_746*(T_746 - s.a328_c002_T) + R328_E021_LOSS_DT) / max(m_749, 1e-6)
    T_749    = min(max(T749_raw, min(s.a328_c002_T, Tc003)), max(s.a328_c002_T, Tc003))
    # FFIC-329401 ratio master, T/M3 (the DCS basis).  The feed measurement is the FIC-328402
    # wash leg (m_744 into 323E003), NOT the 328C002 m_738 term, and it is read VOLUMETRICALLY
    # because that loop is now m3/h -- so on CAS the FIC-329401 slave SP is FIC-328402 * ratio
    # and FV-329401 strokes to hold it.  Same float operation order as R328_FFIC_RATIO_DES, so
    # at design ffic_pv == sp -> du == 0 and the LP-steam draw holds 6495 kg/h bit-exactly.
    # AUDIT G15: Remove double-lag that causes ratio hunting. Both m931_prev and m744_prev already
    # carry 5-second measurement lags from their respective _fic_flow calls (line 4076). Adding
    # another 5-second lag here (tau=5.0) creates a 10-second effective lag on the ratio PV, which
    # causes the cascade to oscillate when FIC-328402 SP changes. The ratio calculation itself is
    # instantaneous algebra on already-lagged measurements, so no additional lag is needed.
    # Changed tau from 5.0 to 0.0 to make the ratio measurement respond immediately to flow changes.
    ffic_pv  = _lag1(s.tlag, "FF_ratio",
                     (m931_prev / 1000.0) / max(m744_prev / RHO_744_KGM3, 1e-6), 0.0, dt)
    ffic_op  = _ctrl_ipd(s.FFIC_329401, ffic_pv, dt)                     # 931-flow demand (kg/h)
    m_931    = _fic_flow(s.FIC_329401, R328_C004_M931_DES, 50.0, s.tlag, "F_329401", dt, cas_sp=ffic_op)
    in_c004  = m_749 + m_931
    lvl_c004 = s.a328_c004_M / R328_C004_M_DES * 50.0
    lic505_op= _ctrl_ipd(s.LIC_328505, lvl_c004, dt)
    m_739    = R328_C004_M739_DES * (lic505_op / 50.0)                    # bottoms -> 328E007 boundary
    sens_c004= m_749/3600.0*cp_328c004*(T_749 - Tc004)
    # AUDIT F-8: energy-limited overhead, same anchored-ratio form as 328C002 -- what the LP strip
    # steam plus the sensible net can boil, capped by throughput.  Replaces R328_C004_PHI750.
    q_c004   = sens_c004 + m_931/3600.0*R328_C004_M931_DH
    # AUDIT C1 — same split as 328C002: boil-up from the net duty, outflow from the live column
    # pressure through the overhead line into the 328C002 bottom, temperature = bubble point.  This
    # is the column where it matters most for training: losing the LP strip steam must drop the
    # bottoms temperature and collapse the NH3 stripping, and under the old form it did neither.
    gen750   = max(R328_C004_M750_DES * (q_c004 / R328_C004_Q_DES), 0.0)  # boil-up (kg/h)
    # Dynamic pressure drop coupling: flow driven by 328C004 to 328C002 dP
    dP_750_des = R328_C004_P_BARA - R328_C002_P_TOP
    _p004_lag = _lag1(s.tlag, 'P_C004_lag', s.a328_c004_P, 2.0, dt)
    _p002_lag = _lag1(s.tlag, 'P_C002_lag', s.a328_c002_P, 2.0, dt)
    dP_750_live = max(_p004_lag - _p002_lag, 0.001)
    
    dP_750_live = max(s.a328_c004_P - s.a328_c002_P, 0.001)
    m_750    = R328_C004_M750_DES * math.sqrt(dP_750_live / dP_750_des)
    M_c004_pre = s.a328_c004_M
    s.a328_c004_P = max(s.a328_c004_P + R328_C004_P_KP*(gen750 - m_750)/3600.0*dt, 0.1)
    s.a328_c004_T = tsat_steam(s.a328_c004_P + R328_C004_DP_COL)          # bubble point at the bottom
    s.a328_c004_M = max(M_c004_pre + (in_c004 - m_750 - m_739)/3600.0*dt, 1.0)
    a_c004   = des_alpha_live("C004", Tc004, m_931, m_739)
    s.w_328c004, y_750 = des_advance(s.w_328c004, s.a328_c004_M,
                                     [(s.w_328c003, m_749), (W_STEAM, m_931)],
                                     m_750, a_c004, m_739, 0.0, dt)
    s.y_328_750 = y_750

    # ----- Stage 6 : 328D001  Desorber-I reflux drum (61°C, 328E004) -----
    Td001    = s.a328_d001_T
    # AUDIT B2 — stream 793 used to be drawn out of 328D003 Comp-II (Stage 2) and delivered
    # NOWHERE: up to S793_CAP_KGH = 1534 kg/h of mass was destroyed at full FV-328405 stroke, and the
    # leak was invisible at design only because the design stroke is 0 %.  Mapping of Desorber
    # Hydrolyzer unit.md:34-36 puts it in the 737 header ahead of 328E004, i.e. into this drum.
    # m_793 is settled in Stage 2, so this is a same-tick term, not a tear.  At design m_793 == 0.
    in_d001  = m_737 + m718A_prev + m_793
    # AUDIT B5 — the mapping doc (line 5) puts PIC-328202 on 328C002, not on the drum: the valve
    # PV-328202 does sit on the 786 vent off 328D001 (line 41, which the code already had right), but
    # the transmitter reads the column.  The PV was bound to s.a328_d001_P, i.e. wrong by exactly one
    # exchanger pressure drop (PFD-22: 737/738 = 3.5 bar a, 774/775/786 = 2.6), and the model's own
    # +R328_E004_DP fix-up inside the TIC-328008 inferential was the evidence it needed the column
    # value all along.  Now that 328C002 carries a live pressure state, bind the loop to it.
    pic202b_op = _ctrl_ipd(s.PIC_328202, s.a328_c002_P, dt)
    m_786_d001 = R328_D001_M786_DES * (pic202b_op / R328_D001_PV_OP_DES)  # vent -> 323E011
    tic002_op= _ctrl_ipd(s.TIC_328002, Td001, dt)
    Q_e004   = R328_E004_Q_DES_KW * (tic002_op / R328_E004_TV_OP_DES)
    # The more we cool, the more we condense, so less non-condensable/uncondensed gas reaches the drum vent
    condensation_factor = max(Q_e004 / R328_E004_Q_DES_KW, 0.1)
    gen786   = R328_D001_M786_DES * (m_737 / R328_D001_M737_DES) / condensation_factor
    # TIC-328008 MASTER -> FIC-328404 slave (TD-004).  PV is the inferential H2O mol% of the gas
    # leaving 328C002 to 328E004 (PFD 737), live on the drum pressure via PIC-328202 + 0.9 bar dP.
    # Stepped HERE, immediately before its slave, so the cascade is same-tick like every other
    # master in this engine; its PV depends only on constants and s.a328_d001_P, both already
    # settled at this point.  On CAS, FV-328404 strokes to hold TIC-328008.
    # AUDIT C31 — the doc specifies TWO inputs (TT-328008 and PIC-328202); the temperature leg was the
    # module constant R328_C002_T_BOT_TOP, so the PV was live on drum pressure and blind to the column.
    # psat(117)=1.8004 vs psat(120)=1.9854, i.e. 3 C swings the PV by 4.75 mol% -- twice the loop's
    # whole SP band.  Now rides the live 328C002 bottoms at the design top/bottom offset; at the seed
    # s.a328_c002_T - R328_C002_DT_TOP == 139 - 22 == 117.0 exactly, so the pin cannot move.
    dt_top_dynamic = 10.0 + (R328_C002_DT_TOP - 10.0) * (m775_prev / R328_D001_M775_DES)
    T_737      = s.a328_c002_T - dt_top_dynamic                             # TT-328008, column top (C)
    # AUDIT C1 — the VLE node pressure is now the LIVE 328C002 state, not the drum plus a frozen
    # R328_E004_DP.  At the seed s.a328_c002_P == R328_C002_P_TOP == 3.5, the same value the old
    # s.a328_d001_P + R328_E004_DP reconstructed, so the inferential is bit-exact at design.
    tic8008_op = _ctrl_ipd(s.TIC_328008,
                           100.0 * R328_D001_OFFGAS_PHI * psat_water_bara(T_737)
                           / max(s.a328_c002_P, 0.1), dt)                     # 775-reflux demand (kg/h)
    m_775    = _fic_flow(s.FIC_328404, R328_D001_M775_DES, R328_D001_FIC404_OP_DES, s.tlag, "F_328404", dt,
                         rho=RHO_775_KGM3, cas_sp=tic8008_op)   # SP in m3/h, returns kg/h
    lvl_d001_328 = s.a328_d001_M / R328_D001_M_DES * R328_D001_LVL_SP
    lic501_op= _ctrl_ipd(s.LIC_328501, lvl_d001_328, dt)
    m_776    = R328_D001_M776_DES * (lic501_op / R328_D001_LV_OP_DES)     # draw -> 323E003
    sens_d001= ((m_737*(T_737 - Td001)                                    # AUDIT C31: live column top
                 + m718A_prev*(R328_D001_T718A - Td001)
                 + m_793*(s.a328_d003_TII - Td001))/3600.0*cp_328d001)
    P_d001   = sens_d001 + m_737/3600.0*R328_D001_LAM737 - Q_e004
    s.a328_d001_P = max(s.a328_d001_P + R328_D001_P_KP*(gen786 - m_786_d001)/3600.0*dt, 0.1)
    s.a328_d001_T = Td001 + P_d001*dt/max(s.a328_d001_M*cp_328d001, 1e-6)
    s.a328_d001_M = max(s.a328_d001_M + (in_d001 - m_786_d001 - m_775 - m_776)/3600.0*dt, 1.0)

    # ----- AUDIT C4 : unit-328 ENERGY-CLOSURE DIAGNOSTIC -------------------
    #  Envelope = {328C002, 328C003, 328C004, 328D001, 328E021, 328E007}.  Reference 0 C, cp = R328_CP.
    #  Streams 775 (drum -> column reflux), 748 and 750 (column -> column) are INTERNAL and excluded.
    #
    #  Why this exists.  The audit reported that unit 328 "creates +413 kW at design, 9.1 % of its own
    #  steam input", on the grounds that every stream shared by two vessels carries two different
    #  back-solved latent heats -- 737 is generated in 328C002 at 1879.34 kJ/kg and condensed in
    #  328D001 at 2163.55, a +526 kW gap on its own.  That arithmetic is exact (re-verified by hand),
    #  but the conclusion drawn from it is NOT established, because the envelope check offered as
    #  independent confirmation treated unit 328 as NON-REACTING.  It is not: the columns strip NH3
    #  and CO2 out of solution (carbamate DECOMPOSITION, endothermic) and this drum re-absorbs them
    #  (carbamate FORMATION, exothermic).  Stream 737 delivers 39.46 kmol/h of CO2 into the drum
    #  liquid; at a realistic -100 to -130 kJ/mol that is 1096 to 1425 kW of genuine reaction
    #  enthalpy -- the 526 kW lambda gap sits comfortably INSIDE it.
    #
    #  So two different lambdas for one stream is correct physics here, not a bug: in 328C002 it is a
    #  BOIL-UP latent, in 328D001 it is CONDENSATION PLUS CARBAMATE FORMATION, which must be larger.
    #  The real defect is the same one finding C9 names for the hydrolyser: the reaction enthalpy is
    #  hidden inside a back-solved latent instead of being an explicit xi*dH term, so it scales with
    #  whatever drives that latent's stream rather than with the actual reaction extent.  Making the
    #  lambdas equal -- the fix the audit prescribed -- would DELETE a ~500 kW carbamate exotherm and
    #  run the drum cold.
    #
    #  This diagnostic measures the residual every tick instead of arguing it from constants, so the
    #  explicit-xi rework can be checked against a number.  It is read-only: nothing consumes it.
    #  328E007 is INSIDE the envelope, so the feed enters as stream 735 at the Comp-I bulk (56 C) and
    #  the export leaves as stream 740 at the E007 hot outlet (89 C); the interchanger duty cancels
    #  internally.  Taking the feed at T_738 instead would credit the 2005 kW E007 recovery to the
    #  inlet without ever debiting it -- the same boundary slip that made the audit's own envelope
    #  disagree with its lambda arithmetic.
    q328_in  = ((m_735 * s.a328_d003_TII
                 + m718A_prev * R328_D001_T718A
                 + m_793 * s.a328_d003_TII) / 3600.0 * R328_CP
                + m_911 / 3600.0 * R328_C003_M911_DH
                + m_931 / 3600.0 * R328_C004_M931_DH)
    q328_out = ((m739_prev * T_740
                 + m_786_d001 * s.a328_d001_T
                 + m_776 * s.a328_d001_T) / 3600.0 * R328_CP
                + Q_e004 + R328_E021_LOSS + R328_E007_LOSS)
    # AUDIT C4 / gap G5 — CLOSE the envelope by making the hidden carbamate-desorption enthalpy an
    # EXPLICIT term instead of leaving it buried in back-solved latents.  q328_react is the reaction
    # heat the MP+LP reboiler steam supplies to strip NH3/CO2 out of solution; its design magnitude is
    # captured once from the design seed (first tick from a fresh design State), so the residual is
    # bit-exact zero at design, and off-design it follows the live reboiler steam that drives
    # desorption (anchored-ratio form, the same idiom as gen748/gen750).  This is READ-ONLY: it enters
    # only the published residual below, never a state ODE, so every pinned dynamic balance is
    # untouched.  See the derivation block above and _A328_Q_REACT_DES_KW.
    global _A328_Q_REACT_DES_KW
    q328_raw = q328_in - q328_out              # kW; negative = more out than in (hidden reaction)
    if _A328_Q_REACT_DES_KW is None:
        _A328_Q_REACT_DES_KW = -q328_raw       # design net carbamate-desorption enthalpy (kW)
    steam_ratio_328 = ((m_911 + m_931)
                       / (R328_C003_M911_DES + R328_C004_M931_DES))
    q328_react = _A328_Q_REACT_DES_KW * steam_ratio_328
    q328_resid = q328_raw + q328_react         # kW; ~0 at design, bounded off-design departure

    # ----- Stage 7 : 322C001  LP absorber (43°C, live GCB off-gas) --------
    Tc001    = s.a328_c001_T
    gcb_m    = hv604["mass_kgh"]
    gcb_T    = hv604["T_out"]
    pic201_op= _ctrl_ipd(s.PIC_322201, s.a328_c001_P, dt)
    lvl_c001 = s.a328_c001_M / A328_C001_M_DES * 50.0
    lic502c_op = _ctrl_ipd(s.LIC_322502, lvl_c001, dt)
    m_756    = A328_M756_DES * (lic502c_op / A328_LIC_OP_DES)             # liquor draw -> 323E003
    Q_flood  = A328_QFLOOD_KW if s.XV_322915 else 0.0                     # trip 22.1 steam flood
    y_vent = None
    if A328_GCB_DES is None:                                              # pre-pin: design absorb, hold P
        abs_co2, abs_nh3 = A328_ABS_CO2_DES, A328_ABS_NH3_DES
        abs_c001  = A328_ABS_DES
        vent_c001 = max(gcb_m - abs_c001, 0.0)
    else:                                                                # post-pin: live off-gas
        # TD-009 remainder — reactive absorption CO2 + 2 NH3 -> carbamate.  The scalar recovered mass
        # abs_c001 is the SAME boot-pinned split as before (A328_PHI_ABS*gcb_m, so C1 and the energy
        # balance are byte-identical and the 15-key pin is untouched); the species layer splits it at
        # the frozen carbamate ratio 2 NH3 : 1 CO2, and the inerts N2/O2/CH4/H2 pass 100 % to the vent.
        # The vent then carries a LIVE per-species composition (gcb_i − absorbed_i), replacing the
        # composition-blind scalar — the atmospheric NH3 slip is now a real number, not a boot constant.
        abs_c001  = A328_PHI_ABS * gcb_m
        abs_co2   = abs_c001 * A328_ABS_CO2_DES / A328_ABS_DES            # frozen carbamate split
        abs_nh3   = abs_c001 * A328_ABS_NH3_DES / A328_ABS_DES
        vent_c001 = A328_VENT_DES * (pic201_op / A328_PIC_OP_DES)
        s.a328_c001_P = max(s.a328_c001_P
                            + A328_C001_P_KP*((gcb_m - abs_c001) - vent_c001)/3600.0*dt, 0.1)
        # vent gas composition y (mass fractions over MW_COMP): un-absorbed off-gas -> 328V001/323C005/atm
        gcb_i  = {k: hv604["comp_kmolh"].get(k, 0.0) * MW_COMP[k] for k in MW_COMP}    # kg/h per species
        vent_i = dict(gcb_i);  vent_i["CO2"] -= abs_co2;  vent_i["NH3"] -= abs_nh3
        _vt = sum(v for v in vent_i.values() if v > 0.0)
        if _vt > 1e-9:
            y_vent = {k: max(vent_i[k], 0.0) / _vt for k in MW_COMP}
    if A328_LAMBDA_ABS is not None:
        sens_c001 = ((m_755*(A328_M755_T - Tc001) + s.cpl_flow_kgh*(A328_CPL_T - Tc001))/3600.0*cp_322c001
                     + gcb_m*(gcb_T - Tc001)/3600.0*cp_322c001)
        P_c001    = sens_c001 + abs_c001/3600.0*A328_LAMBDA_ABS + Q_flood
        s.a328_c001_T = Tc001 + P_c001*dt/max(s.a328_c001_M*cp_322c001, 1e-6)
    s.a328_c001_M = max(s.a328_c001_M + (m_755 + s.cpl_flow_kgh + abs_c001 - m_756)/3600.0*dt, 1.0)
    # --- liquor species CSTR (TD-009 remainder): feeds 755 + CPL + absorbed(NH3/CO2), draw 756, no
    #     vapour off (the vent is un-absorbed gas that never entered the liquid).  des_advance with
    #     m_vap==0, xi==0 is a plain multi-feed CSTR; W_C001_DES == the design feed mix -> dw/dt==0.
    w_abs = {"CO2": (abs_co2 / abs_c001 if abs_c001 > 1e-9 else 0.0),
             "NH3": (abs_nh3 / abs_c001 if abs_c001 > 1e-9 else 0.0)}
    s.a328_c001_w, _ = des_advance(s.a328_c001_w, s.a328_c001_M,
                                   [(W_S755, m_755), (W_CPL, s.cpl_flow_kgh), (w_abs, abs_c001)],
                                   0.0, A328_C001_ALPHA, m_756, 0.0, dt)

    # ----- Stage 8 : 323E003 + 323D001  LPCC (74°C, tempered water) -------
    Te003    = s.r3232_e003_T
    in_e003  = m_305 + m718B_prev + m_776 + R3232_M797_DES
    pic202_op= _ctrl_ipd(s.PIC_323202, s.r3232_d001_P, dt)
    m_321    = R3232_E003_M321_DES * (pic202_op / R3232_E003_PV_OP_DES)   # vent -> 323E011
    gen321   = R3232_E003_PHI321 * (m_305 + R3232_M797_DES)
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
                 + R3232_M797_DES*(R3232_M797_T - Te003))/3600.0*R3232_CP)
    P_e003   = sens_e003 + m_cond/3600.0*R3232_E003_LAMC - Q_e003
    s.r3232_d001_P = max(s.r3232_d001_P + R3232_D001_P_KP*(gen321 - m_321)/3600.0*dt, 0.1)
    s.r3232_e003_T = Te003 + P_e003*dt/max(s.r3232_d001_M*R3232_CP, 1e-6)
    if s.r3232_d001_M <= 1.0 and m_308 > (in_e003 - m_321):
        m_308 = max(in_e003 - m_321, 0.0)
    s.r3232_d001_M = max(s.r3232_d001_M + (in_e003 - m_321 - m_308)/3600.0*dt, 1.0)

    # ----- Stage 9 : 323E011 + 323D011  LP carbamate condenser (45°C) -----
    Te011    = s.r3232_e011_T
    in_e011  = (R3232_E011_IN_DES + (m_701 - R3232_E011_M701_DES)
                + (m_786_d001 - R3232_E011_M786_DES)
                + (m_321 - R3232_E011_M321_DES)
                + (m_402 - R3232_E011_M402_DES))
    pic203_op= _ctrl_ipd(s.PIC_323203, s.r3232_e011_P, dt)
    dP_v011  = max(s.r3232_e011_P - 1.0, 0.001)   # C005 is approx 1.0 bar (atmospheric vent node)
    m_v011   = R3232_E011_MV_DES * (pic203_op / R3232_E011_PV_OP_DES) * math.sqrt(dP_v011 / (R3232_E011_P_BARA - 1.0))
    # 323E011's cooling surface is fixed, so its condensation rate saturates: only gas ABOVE
    # that capacity has to leave through PIC-323203.  A fixed vent fraction of the inlet made a
    # falling gas load still generate vent gas, which the condenser would in fact have absorbed.
    # m_402 is the stream-791 ammonia-water LIQUID feed, so it is excluded: it is absorbent, not
    # gas load.  At design 7563 - 1534 = 6029 kg/h of gas -> 440 kg/h vented (PFD stream 702).
    gen_v011 = e011_vent_generation_kgh(max(in_e011 - m_402, 0.0))
    # 323D011 level tank: condensed liquid (in_e011 - m_v011) + the FIC-323401 flush 401 (PFD stream
    # 734) fall in; the 323P008 lean-carbamate pumps draw out through LV-323503 on the common
    # discharge header, which then splits into the 718A and 718B legs (PFD 3562 / 3562 off 718 7123).
    # LIC-323503 -> LV-323503 sets the TOTAL draw; FIC-323418 holds the 718B slipstream ("regulates
    # the SPECIFIC recycle flow rate of lean carbamate", 328E021 328E007 328P003 328P006.md:369) and
    # 718A is the UNMETERED REMAINDER -- a transport lag on (total draw - 718B demand), no controller
    # of its own.  FIC-328405 used to be cascaded onto 718A; that binding is stripped, because the PFD
    # puts FIC-328405 on ammonia-water stream 793 off the 328D003 Comp-II header (see stage 2), not on
    # this carbamate leg.  The remainder form keeps one integrator per degree of freedom (inventory ->
    # LIC-323503; split -> FIC-323418) and removes a second flow integrator that was marginally stable
    # here.  Modelling a series LV-503 as a derate on both FVs instead was tried and REJECTED: two
    # AUTO FICs reject the header stroke by integral action, so LIC-323503 wound up to op_hi and level
    # parked off SP (see scratchpad/dyn503.py).
    lvl_d011 = s.r3232_e011_M / R3232_D011_M_DES * R3232_D011_LVL_SP      # LT-323503 (%)
    lic503_op= _ctrl_ipd(s.LIC_323503, lvl_d011, dt)                      # -> LV-323503 (total draw)
    m718_dmd = R3232_D011_M718_DES * (lic503_op / R3232_LV503_OP_DES)     # total draw demand (kg/h)
    m_718B   = _fic_flow(s.FIC_323418, R3232_M718B_DES, R3232_FIC418_OP_DES, s.tlag,
                         "F_323418", dt, tau_s=45.0, rho=RHO_718_KGM3)    # -> 323E003 (slipstream)
    # 718A/718B demand-split COORDINATOR (setpoint feed-forward decoupling).
    #   Old cas_sp = m718_dmd - m_718B (live PV) coupled the two loops through 718B's lagged flow:
    #   718A chased 718B's measured PV while both drew on the shared m718_dmd, giving a 2-tick
    #   bang-bang limit cycle (3.18<->3.50 m3/h).  Break the feedback -- derive 718A's remainder
    #   from 718B's DEMAND (its SP in AUTO/CAS), not its noisy measured flow.  Steady state is
    #   unchanged (718B AUTO settles to its SP), so the 323D011 718-split conservation still holds
    #   (m_718A + m_718B -> m718_dmd); only the oscillating transient is removed.  In MAN the op is
    #   operator-fixed so 718B is already non-oscillating and the live flow is a safe fallback.
    if s.FIC_323418["mode"] in ("AUTO", "CAS"):
        m718B_ff = s.FIC_323418["sp"] * RHO_718_KGM3     # feed-forward from setpoint (kg/h)
    else:
        m718B_ff = m_718B                                # MAN: op-fixed, live flow non-oscillating
    m718A_dmd = max(m718_dmd - m718B_ff, 0.0)            # remainder demand for 718A (kg/h)
    #   718A is the unmetered remainder, so it is a pure transport lag on that demand -- the 45 s
    #   time constant is the one the old FIC-328405 measurement filter carried (the leg's physical
    #   piping/inertia lag; the controller it belonged to is gone, the lag is not).  _lag1 has DC
    #   gain 1 and lazy-inits to its target, so the design seed is bit-exact and the steady-state
    #   718 split is unchanged: m_718A + m_718B -> m718_dmd.
    m_718A   = _lag1(s.tlag, "F_718A", m718A_dmd, R3232_M718A_TAU_S, dt)  # -> 328E004/328D001 (bal)
    m_718_tot= m_718A + m_718B                                            # -> 323D011 draw (kg/h)
    Q_e011   = R3232_E011_UA_KW * (Te011 - 35.0)
    sens_e011= (((m_701 + R3232_E011_RECON_KGH)*(R3232_E011_T701 - Te011)
                 + m_786_d001*(R3232_E011_T786    - Te011)
                 + m_321*(74.0 - Te011)
                 + m_402*(56.0 - Te011))/3600.0*R3232_CP)
    m_cond_e011 = max(in_e011 - m_402 - m_v011, 0.0)
    P_e011   = sens_e011 + m_cond_e011/3600.0*R3232_E011_LAMV - Q_e011
    s.r3232_e011_P = max(s.r3232_e011_P + R3232_E011_P_KP*(gen_v011 - m_v011)/3600.0*dt, 0.1)
    s.r3232_e011_T = Te011 + P_e011*dt/max(s.r3232_e011_M*R3232_CP, 1e-6)
    s.r3232_e011_M = max(s.r3232_e011_M + (in_e011 - m_v011 - m_718A - m_718B)/3600.0*dt, 1.0)

    # ----- recycle-tear writes (one-tick delay -> next step reads these) --
    s.tlag["R3232_v011"] = m_v011
    s.tlag["R3232_702"]  = m_v011
    s.tlag["R322_756"]   = m_756
    s.tlag["R328_748"]   = m_748
    s.tlag["R328_750"]   = m_750
    s.tlag["R328_775"]   = m_775
    s.tlag["R3232_718A"] = m_718A
    s.tlag["R3232_744"]  = m_744
    s.tlag["R3232_718B"] = m_718B
    s.tlag["R328_M931"]  = m_931
    s.tlag["R328_739"]   = m_739       # 328C004 bottoms this tick -> caps next tick's 741 recycle

    # ======================================================================
    #  UNIT 324 — TWO-STAGE VACUUM EVAPORATION  (rigorous, conservative)
    #  Feed = m_324 (kg/h, 80% urea, ~99 C) delivered by FIC-324401. LV-B
    #  recycle returns to 323D002 Compartment I on a one-tick tear; it is not
    #  an undocumented direct Stage-1 feed. Each stage runs a TIC->PIC steam cascade that sets the
    #  chest pressure -> Q = UA*(tsat(p_chest) - T); urea is conserved so the
    #  water evaporated is fixed exactly by the concentration anchor, and the
    #  energy/mass/pressure ODEs integrate the live sub-step dt.  UA/λ were
    #  back-solved at the seed so dM/dt = dT/dt = dP/dt = 0 at design.  Vacuum
    #  is held by a false-air PIC balanced against a fixed ejector pull.
    #      HARD anchors: Stage 1 0.33 bar a / 130 C / 80->95 % ;
    #                    Stage 2 0.131 bar a / 140 C / 95->98.6 %.
    # ======================================================================
    # AUDIT C10.  cp324 was one constant (2.5) for the feed AND both melts, across a train that
    # takes the solution from 80 % urea to 97.71 %.  Each use below now takes cp at its own local
    # composition and temperature; urea_soln_cp returns the design anchor bit-exactly at the design
    # composition, so the seed is untouched and only the off-design response changes.
    # ---- Stage 1 : Evaporator I 324E001 + separator 324F001 (0.33 bar a, 130 C) --
    # ---- 323D002 -> 324E001 feed line: plug-flow transport of the CLOSED packet ---------------
    # m_324 stays the 323D002 outflow in the tank balances above -- that material has left the tank.
    # Stage 1 consumes the ARRIVED packet instead, so the longest run in the train contributes its
    # own dead time and mass, temperature and composition reach the evaporator on the same sub-step.
    _m_dep_324   = max(m_324, 0.0)                                             # 323D002 pump discharge (kg/h)
    _pkt_dep_324 = _cq_packet(_m_dep_324, s.r323_d002_T, s.w_d002,
                              urea_soln_cp(s.w_d002.get("Urea", R324_W_IN), s.r323_d002_T))
    _pkt_arr_324 = _transport_process(s, "323D002_TO_324E001", _pkt_dep_324, _m_dep_324, dt)
    if _pkt_arr_324 == _pkt_dep_324:
        feed1_m, T_feed1, w_arr_324 = _m_dep_324, s.r323_d002_T, s.w_d002
    else:
        feed1_m   = _pkt_arr_324.mass_kgh
        T_feed1   = _pkt_arr_324.temperature_c
        w_arr_324 = _w_norm(_pkt_arr_324.mass_fraction)
    # AUDIT B1 (ripple).  This read the FROZEN R324_W_IN, so no composition change anywhere
    # upstream could reach the evaporators -- a measured 0 of 66 unit-324 telemetry leaves
    # responded to a reactor-overflow composition step.  It now reads the live 323D002 tank
    # vector.  (That vector is itself held at the design strength by sol_pin_strength; see the
    # note there -- both had to change for the ripple to actually flow.)
    w_tank     = w_arr_324.get("Urea", R324_W_IN)
    urea1_in   = w_tank * feed1_m                                             # urea into Stage 1 (kg/h)
    w_feed1    = w_tank
    # AUDIT C18 — the Stage-1 feed enthalpy term used the FROZEN R324_FEED_T_C = 99 C while the
    # 323D002 tank temperature is a live ODE state carrying (by the code's own note at the tank) a
    # LOW-temperature alarm.  A 10 K tank cooldown withholds 644 kW = 6.1 % of R324_E001_Q_DES_KW,
    # i.e. ~1067 kg/h less water evaporated -- and the model moved none of it.
    cp_feed1   = urea_soln_cp(w_feed1, T_feed1)
    cp_hold1   = urea_soln_cp(s.w_e001.get("Urea", R324_W_EV1), s.r324_e001_T)
    tic1_op    = _ctrl_ipd(s.TIC_324001, s.r324_e001_T, dt)                   # steam chest-P demand (bar a)
    pic203_pv  = clamp(s.PIC_329203["op"]/100.0*s.steam.P_LP, 0.0, s.steam.P_LP)
    pic203_op  = _ctrl_ipd(s.PIC_329203, pic203_pv, dt, cas_sp=tic1_op)       # steam valve stroke (%)
    # AUDIT THERMO-3: Apply transport lag to steam header pressure before thermal calc.
    # The shared steam header (s.steam.P_LP) responds in ~1 s to header-wide load changes,
    # but the 180 s-residence liquid inventory in 324E001 should not begin responding in 1 s.
    # Lag the steam-side pressure seen by the thermal calculation to prevent instantaneous
    # liquid-temperature response via the steam path while the material path correctly lags 28-72 s.
    p_lp_lagged = _lag1(s.tlag, "324E001_P_LP_thermal", s.steam.P_LP, R324_F001_M_TAU_S, dt)
    p_chest_e001 = steam_chest_pressure(pic203_op, p_lp_lagged)
    Q_e001_kw  = max(R324_E001_UA_KW*(tsat_steam(p_chest_e001) - s.r324_e001_T), 0.0)
    # AUDIT F-4 — evaporation is DUTY-LIMITED, and the melt strength FOLLOWS it (was pinned at
    # R324_W_EV1 by construction, so no operator action could dilute the product).  q1_avail is
    # the latent duty left after the feed has been carried to the stage temperature; the water
    # removed is whichever is smaller — the concentration target or what that duty can boil.
    # AUDIT TD-016 — the evaporator melt strength IS the smooth VLE equilibrium at the controlled
    # vacuum, and the water removed follows it continuously.  This closes the residual limit cycle
    # and replaces the whole TD-014/TD-015 min(concentration-cap, duty) two-branch closure.
    #
    # The old concentration cap was a FIXED 94.31 % ceiling — `urea_in / R324_W_EV1` — whose
    # d(conc)/dT is identically zero.  Once the melt hit it, more steam only raised T with no
    # concentration payoff, so TIC-324001 saw zero process gain, disengaged, let the melt drift and
    # then over-corrected: the relay chatter the Urea-Water VLE research (sec 2) blames for these
    # cycles.  Worse, the min()-switching fed straight into the 324F001 vacuum ODE and swung the
    # separator pressure. The continuous Extended-UNIQUAC departure w_eq(T,P) removes all of it:
    #   * a real, non-zero dCu/dT  -> TIC-324001 has genuine gain and never disengages;
    #   * v depends on TEMPERATURE only (the vacuum is regulated separately by PIC-324202), so the
    #     P -> v -> P coupling that destabilised the separator pressure is gone;
    #   * one branch, so no min(), no relay, no chatter.
    # Evaluated at the CONTROLLED design vacuum (0.33 bar a), not the live separator pressure, so the
    # melt target is a pure smooth function of temperature.  Anchored (w_eq(130,0.33) == R324_W_EV1)
    # so v == R324_V1_DES and P_e001 == 0 bit-exact at the design seed; TIC-324001 stays what TD-015
    # made it — a melt-strength controller acting through temperature — now without the relay.
    # Close the pressure/VLE algebraic tear inside the stage.  Pressure sets equilibrium vapour
    # generation; vapour load and ejector pull set pressure.  A bounded fixed-point solve prevents
    # the returned pressure and composition from belonging to different integration instants.
    fa202_m = R324_F001_FA_DES * (s.PIC_324202["op"] / max(R324_PV202_OP_DES, 1e-6))
    _ctrl_ipd(s.PIC_324202, s.r324_f001_P, dt)
    mot9605_m = s.HIC_329605 / 100.0 * R324_HV9605_SPAN
    M_f001_pre = s.r324_f001_M
    t1_old = s.r324_e001_T
    t1_solved = t1_old
    p1_old = s.r324_f001_P
    p1_solved = p1_old
    t1_fp_residual = math.inf
    t1_fp_converged = False
    t1_fp_iterations = 0
    for t1_fp_iterations in range(1, R324_PT_LOOP_MAXIT + 1):
        Q_e001_kw = max(R324_E001_UA_KW * (tsat_steam(p_chest_e001) - t1_solved), 0.0)
        w_eq1 = evap_w_eq(t1_solved, p1_solved,
                          R324_W_EV1, R324_E001_T_SP_C, R324_F001_P_BARA)
        v1_m = clamp(feed1_m - urea1_in / max(w_eq1, 1e-6), 0.0, feed1_m)
        pwr1 = (feed1_m/3600.0 * cp_feed1 * (T_feed1 - t1_solved)
                + Q_e001_kw - v1_m/3600.0 * R324_LAM_V1)
        t1_next = t1_old + pwr1 * dt / max(M_f001_pre * cp_hold1, 1e-6)
        m703_fp = (VACUUM_CONDENSERS["324E002"]["inlet_kgh"]
                   + (m_evap - R323_MEVAP_DES) + (v1_m - R324_V1_DES)
                   + (fa202_m - R324_F001_FA_DES))
        nc002_fp = max(72.0 - R324_F001_FA_DES + fa202_m, 0.0)
        vent002_fp = max(nc002_fp, m703_fp - VACUUM_CONDENSERS["324E002"]["condensate_kgh"])
        ejpull_live = (R324_F001_EJPULL_DES * (mot9605_m / R324_F002_MOTIVE_DES)
                       * (p1_solved / R324_F001_P_BARA))
        p1_next = clamp(p1_old
                        + R324_F001_P_KP * (vent002_fp - ejpull_live) / 3600.0 * dt,
                        0.05, 1.0)
        t1_fp_residual = max(abs(p1_next - p1_solved), abs(t1_next - t1_solved))
        if t1_fp_residual <= R324_PT_LOOP_TOL:
            p1_solved = p1_next
            t1_solved = t1_next
            t1_fp_converged = True
            break
        p1_solved = p1_next
        t1_solved = t1_next
    s.r324_e001_T = t1_solved
    s.r324_f001_P = p1_solved
    w_eq1 = evap_w_eq(s.r324_e001_T, s.r324_f001_P,
                      R324_W_EV1, R324_E001_T_SP_C, R324_F001_P_BARA)
    v1_m = clamp(feed1_m - urea1_in / max(w_eq1, 1e-6), 0.0, feed1_m)
    Q_e001_kw = max(R324_E001_UA_KW * (tsat_steam(p_chest_e001) - s.r324_e001_T), 0.0)
    _DIAG["E001"] = {
        "weq": w_eq1, "v": v1_m, "Q": Q_e001_kw,
        "T": s.r324_e001_T, "feed": feed1_m, "urea_in": urea1_in,
        "thermo_model": extended_uniquac.MODEL_NAME,
        "thermo_validity": extended_uniquac.validity_status(
            s.r324_e001_T + 273.15, s.r324_f001_P
        ),
        "thermo_px_residual_bara": extended_uniquac.px_equilibrium_residual(
            w_eq1, s.r324_e001_T + 273.15, s.r324_f001_P
        ),
        "iteration_count": t1_fp_iterations,
        "iteration_residual": t1_fp_residual,
        "converged": t1_fp_converged,
    }
    p1_m       = max(feed1_m - v1_m, 0.0)                                     # Stage-1 melt (kg/h)
    w1_live    = clamp(urea1_in / max(p1_m, 1e-6), 0.0, 1.0)                  # LIVE Stage-1 urea mass frac
    # AUDIT C3 — this was `m_p1 = p1_m`, i.e. outlet := inlet - vapour, which makes the holdup ODE
    # below (feed1_m - v1_m - m_p1) identically ZERO for every operating point: 324F001 was a
    # zero-capacity node whose level indicator could not move and whose mass was nevertheless the
    # denominator of the Stage-1 temperature ODE.  The drain is a barometric leg into the 324F003
    # deep vacuum, so the outflow is hydraulic (square-root in the liquid head), not a bookkeeping
    # identity.  Anchored: at the design holdup the ratio is exactly 1.0, sqrt(1.0) == 1.0, and
    # R324_P1_DES == R324_FEED_DES - R324_V1_DES == p1_m at design, so dM/dt is still exactly 0 at
    # the seed -- but the separator can now surge, drain and flood.
    m_p1       = R324_P1_DES * math.sqrt(max(M_f001_pre / R324_F001_M_DES, 0.0))   # barometric leg -> Stage 2 (kg/h)
    s.r324_f001_M = max(M_f001_pre + (feed1_m - v1_m - m_p1)/3600.0*dt, 1.0)
    # AUDIT F-8/TD-009: Stage-1 species balance.  The blended feed is the live tank composition plus
    # the live Stage-2 recycle, so the melt strength published by the SPECIES layer is derived from
    # a genuine component balance rather than the urea/W_EV bookkeeping.  Both are published: see
    # finding F-11 for why they differ by ~1.5 pp (the PFD's stream-317 composition is not reachable
    # from stream 319 by evaporation alone -- a source-data inconsistency, not a model defect).
    feed1_w    = dict(w_arr_324)
    y_v1       = sol_vapour_y(s.w_e001, SOL_E001["alpha"])
    xi_e001    = sol_biuret_xi("E001", M_f001_pre, s.w_e001, s.r324_e001_T)
    s.w_e001   = sol_pin_strength(
        sol_advance(s.w_e001, M_f001_pre, s.r324_f001_M, feed1_m, feed1_w,
                    v1_m, y_v1, m_p1, xi_e001, dt), w1_live)
    # Vacuum pressure and VLE were solved together above.
    # AUDIT C5 — the pull had NO suction-pressure term, so the vacuum ODE below was a pure open
    # integrator: nothing on its right-hand side depended on s.r324_f001_P.  Shutting HIC-329605 gave
    # dP/dt = 0.02*(14073+250)/3600 = 0.0796 bar/s and the state ramped to the 1.0 bar clamp in 8.4 s
    # and stayed pinned; with PIC-324202 in MAN any imbalance ran to a rail.  A steam-jet ejector's
    # entrainment capacity falls with suction pressure -- that roll-off is the only thing that makes
    # an uncontrolled vacuum node self-regulating, and 323F010 already carries exactly this factor.
    # Anchored: at design P == R324_F001_P_BARA -> ratio 1.0 -> pull == EJPULL_DES bit-exact.
    # ---- 324E001 steam-side condensate : LIC-329505 "active controlled steam trap"
    #  The chest condenses the LP steam it gives up as Q_e001 (cond_gen = Q/lambda);
    #  LV-329505 drains the shell to hold the level.  Steam-side only -> off the
    #  urea/water process network, so this loop is conservation-neutral: at design
    #  cond_gen == lv9505_m -> level parks at SP with zero drift.
    cond_gen   = Q_e001_kw / R324_E001_LAM_STEAM * 3600.0                     # steam condensed on shell (kg/h)
    lvl_e001c  = clamp(s.r324_e001_cond_M / R324_E001_COND_M_FULL * 100.0, 0.0, 100.0)
    lic9505_op = _ctrl_ipd(s.LIC_329505, lvl_e001c, dt)                      # LV-329505 drain stroke (%)
    lv9505_m   = lic9505_op/100.0 * R324_LV9505_SPAN                         # condensate discharge (kg/h)
    s.r324_e001_cond_M = max(s.r324_e001_cond_M + (cond_gen - lv9505_m)/3600.0*dt, 0.01)

    # ---- Stage 2 : Evaporator II 324E003 + separator 324F003 (0.131 bar a, 140 C) -
    feed2_m    = m_p1                                                         # Stage-1 melt (95%) -> Stage 2
    cp_feed2   = urea_soln_cp(w1_live, s.r324_e001_T)                         # LIVE Stage-1 melt cp
    cp_hold2   = urea_soln_cp(s.w_e003.get('Urea', R324_W_EV2), s.r324_e003_T)
    urea2_in   = w1_live * feed2_m                                            # urea into Stage 2 (kg/h, LIVE frac)
    tic2_op    = _ctrl_ipd(s.TIC_324002, s.r324_e003_T, dt)                   # steam chest-P demand (bar a)
    pic212_pv  = clamp(s.PIC_329212["op"]/100.0*s.steam.P_9, 0.0, s.steam.P_9)
    pic212_op  = _ctrl_ipd(s.PIC_329212, pic212_pv, dt, cas_sp=tic2_op)       # steam valve stroke (%)
    # AUDIT THERMO-3: the 9-bar header moves in ~1 s; the 324F003 liquid inventory (180 s residence)
    # cannot.  Same treatment as 324E001 -- lag the chest-supply pressure through the stage's own
    # liquid residence time before it becomes a duty, so TT-324002 cannot answer a header transient
    # faster than the melt it is measuring.
    p_9_lagged_e003 = _lag1(s.tlag, "324E003_P_9_thermal", s.steam.P_9, R324_F003_M_TAU_S, dt)
    p_chest_e003 = steam_chest_pressure(pic212_op, p_9_lagged_e003)
    Q_e003_kw  = max(R324_E003_UA_KW*(tsat_steam(p_chest_e003) - s.r324_e003_T), 0.0)  # Evap-II duty (kW, F-10 floored)
    # AUDIT TD-016 — Evaporator II, same smooth-equilibrium closure as Evaporator I: the melt
    # strength follows the continuous Extended-UNIQUAC departure at 0.131 bar a, so the
    # water removed follows temperature smoothly with no min()/duty relay.  Anchored bit-exact
    # (w_eq(140,0.131) == R324_W_EV2), T-driven at the PIC-324203-controlled vacuum.
    fa203_m = R324_F003_FA_DES * (s.PIC_324203["op"] / max(R324_PV203_OP_DES, 1e-6))
    _ctrl_ipd(s.PIC_324203, s.r324_f003_P, dt)
    M_f003_pre = s.r324_f003_M
    t2_old = s.r324_e003_T
    t2_solved = t2_old
    p2_old = s.r324_f003_P
    p2_solved = p2_old
    t2_fp_residual = math.inf
    t2_fp_converged = False
    t2_fp_iterations = 0
    for t2_fp_iterations in range(1, R324_PT_LOOP_MAXIT + 1):
        Q_e003_kw = max(R324_E003_UA_KW * (tsat_steam(p_chest_e003) - t2_solved), 0.0)
        w_eq2 = evap_w_eq(t2_solved, p2_solved,
                          R324_W_EV2, R324_E003_T_SP_C, R324_F003_P_BARA)
        v2_m = clamp(feed2_m - urea2_in / max(w_eq2, 1e-6), 0.0, feed2_m)
        pwr2 = (feed2_m/3600.0 * cp_feed2 * (s.r324_e001_T - t2_solved)
                + Q_e003_kw - v2_m/3600.0 * R324_LAM_V2)
        t2_next = t2_old + pwr2 * dt / max(M_f003_pre * cp_hold2, 1e-6)
        m709_fp = (VACUUM_CONDENSERS["324E005"]["inlet_kgh"]
                   + (v2_m - R324_V2_DES) + (fa203_m - R324_F003_FA_DES))
        nc005_fp = max(584.0 - R324_F003_FA_DES + fa203_m, 0.0)
        vent005_fp = max(nc005_fp, m709_fp - VACUUM_CONDENSERS["324E005"]["condensate_kgh"])
        ejpull2_live = (R324_F003_EJPULL_DES * (s.HIC_329606 / R324_HIC9606_DES_PCT)
                        * (p2_solved / R324_F003_P_BARA))
        p2_next = clamp(p2_old
                        + R324_F003_P_KP * (vent005_fp - ejpull2_live) / 3600.0 * dt,
                        0.02, 1.0)
        t2_fp_residual = max(abs(p2_next - p2_solved), abs(t2_next - t2_solved))
        if t2_fp_residual <= R324_PT_LOOP_TOL:
            p2_solved = p2_next
            t2_solved = t2_next
            t2_fp_converged = True
            break
        p2_solved = p2_next
        t2_solved = t2_next
    s.r324_e003_T = t2_solved
    s.r324_f003_P = p2_solved
    w_eq2 = evap_w_eq(s.r324_e003_T, s.r324_f003_P,
                      R324_W_EV2, R324_E003_T_SP_C, R324_F003_P_BARA)
    v2_m = clamp(feed2_m - urea2_in / max(w_eq2, 1e-6), 0.0, feed2_m)
    Q_e003_kw = max(R324_E003_UA_KW * (tsat_steam(p_chest_e003) - s.r324_e003_T), 0.0)
    # Reverse-pass utility handshake: actual 324E003 condensation demand reaches 329D009 next tick.
    s.steam.m_users9 = max(R324_9BAR_OTHER_DES + Q_e003_kw / R324_E003_LAM_STEAM, 0.0)
    _DIAG["E003"] = {
        "weq": w_eq2, "v": v2_m, "Q": Q_e003_kw,
        "T": s.r324_e003_T, "feed": feed2_m, "urea_in": urea2_in,
        "thermo_model": extended_uniquac.MODEL_NAME,
        "thermo_validity": extended_uniquac.validity_status(
            s.r324_e003_T + 273.15, s.r324_f003_P
        ),
        "thermo_px_residual_bara": extended_uniquac.px_equilibrium_residual(
            w_eq2, s.r324_e003_T + 273.15, s.r324_f003_P
        ),
        "iteration_count": t2_fp_iterations,
        "iteration_residual": t2_fp_residual,
        "converged": t2_fp_converged,
    }
    p2_gen     = max(feed2_m - v2_m, 0.0)                                     # Stage-2 melt produced (kg/h)
    w2_live    = clamp(urea2_in / max(p2_gen, 1e-6), 0.0, 1.0)                # LIVE final-product urea mass frac
    # LIC-324501 routed melt drain. Pump discharge is raw 402G. Route A enables UF85 stream 697
    # and sends conservative mixed stream 609 to Unit 335; route B interlocks UF85 off and sends
    # raw 402G to 323D002. The selector is exclusive, while 324F003 loses only its raw-melt part.
    lvl_f003   = clamp(s.r324_f003_M / R324_F003_M_FULL * 100.0, 0.0, 100.0)
    lic501_op  = _ctrl_ipd(s.LIC_324501, lvl_f003, dt)
    routed_op  = clamp(lic501_op, 0.0, 100.0)
    # G12 (approved operability): LV-324501A level-controls the drain and exports melt to BL;
    # LV-324501B is a NORMALLY-CLOSED overpressure relief that opens only when the 335 melt-header
    # PIC-335201 exceeds R335_LVB_RELIEF_BARG, diverting the melt to 323D002. UF85 injection is a
    # granulation (335) function and is deferred until that section is simulated, so the live path
    # carries no UF85 (uf_ratio = 0) and the forward export is the raw urea melt.
    recycle_selected = s.PIC_335201 > R335_LVB_RELIEF_BARG                    # LV-324501B relief trip
    lva_stroke = 0.0 if recycle_selected else routed_op
    lvb_stroke = routed_op if recycle_selected else 0.0
    m_402g     = routed_op/100.0 * R324_LVA_SPAN                              # melt drain from 324F003 (kg/h)
    uf_cascade = step_uf85_cascade(s, m_402g, True, dt)                       # UF85 deferred (granulation off) -> 0
    route501   = route_lv324501(m_402g, s.w_e003, s.r324_e003_T,
                                recycle_selected, uf_ratio=0.0)              # raw melt to BL / recycle, no UF85
    m_fwd      = route501["forward_kgh"]                                      # mixed 609 -> 335 on A
    m_recyc    = route501["recycle_kgh"]                                      # raw 402G -> 323D002 on B
    m_f003_out = m_402g                                                        # UF85 is external to 324F003
    s.r324_f003_M = max(M_f003_pre + (feed2_m - v2_m - m_f003_out)/3600.0*dt, 1.0)
    y_v2       = sol_vapour_y(s.w_e003, SOL_E003["alpha"])          # AUDIT F-8: Stage-2 species
    xi_e003    = sol_biuret_xi("E003", M_f003_pre, s.w_e003, s.r324_e003_T)
    s.w_e003   = sol_pin_strength(
        sol_advance(s.w_e003, M_f003_pre, s.r324_f003_M, feed2_m, s.w_e001,
                    v2_m, y_v2, m_f003_out, xi_e003, dt), w2_live)
    # vacuum: PIC-324203 deep-vacuum false-air bleed vs the 324F004/F005 ejector pull.  Mapping — the
    # pull is set by HV-329606 motive steam (HIC-329606): opening it harder drops 324F003 and the
    # 324E005 shell pressure.  Anchored: at design HIC-329606 == 50 % -> the pull == EJPULL_DES, so
    # the ODE is bit-identical at the seed.  (PIC-324203 trims 324F003 to SP in AUTO; the sign shows
    # directly with the loop in MAN.)
    # AUDIT C5 — same open-integrator defect and same anchored roll-off as the Stage-1 pull above.

    # ---- UF85 ratio injection (FFIC-335406 ratio station -> FIC-335405 flow) ------
    #  Physical mixing is already closed in route501 above. Datasheet-3 section 5.2 requires
    #  zero additive on B; therefore m_uf is part of forward stream 609, never recycle 402G.
    m_uf       = route501["uf85_kgh"]
    m_product  = m_fwd                                                        # stream 609 total -> 335

    # ---- four-condenser vacuum train ----------------------------------------------
    #  Each exchanger is an explicit mass/energy node with Q=UA*LMTD, a cooling-water
    #  branch, condensate return to 328D003 Comp I, and noncondensable derating.  The
    #  intervening ejectors are conservative mixing nodes on strict PFD anchors.
    motive_ratio_606 = max(s.HIC_329606 / R324_HIC9606_DES_PCT, 0.0)
    mot927_m = R324_F004_MOTIVE_DES * motive_ratio_606
    mot929_m = R324_F005_MOTIVE_DES * motive_ratio_606
    _vac_evap_in.set_state(mass_flow=m_evap)
    _vac_v1_in.set_state(mass_flow=v1_m)
    _vac_v2_in.set_state(mass_flow=v2_m)
    _vac_fa1_in.set_state(mass_flow=fa202_m)
    _vac_fa2_in.set_state(mass_flow=fa203_m)
    _vac_mot924_in.set_state(mass_flow=mot9605_m)
    _vac_mot927_in.set_state(mass_flow=mot927_m)
    _vac_mot929_in.set_state(mass_flow=mot929_m)
    _vac_unit.solve()
    vac324 = _vac_unit.diagnostics
    vac_stream = vac324["streams_kgh"]
    m_324_cond = vac_stream["719"] + vac_stream["720"] + vac_stream["721"] + vac_stream["759"]
    m_324_vent = vac_stream["722"]
    for _sid in ("719", "720", "721", "759", "708"):
        s.tlag["R324_" + _sid] = vac_stream[_sid]
    s.tlag["R324_COND"] = m_324_cond  # retained aggregate for backward-compatible diagnostics
    # ---- recycle tear write (one-tick delay -> next step reads it) ---------------
    s.tlag["R324_recyc"]   = m_recyc
    s.tlag["R324_recyc_w"] = route501["recycle_comp"]["Urea"]
    s.tlag["R324_recyc_T"] = route501["recycle_T_C"]
    s.tlag["R324_recyc_comp"] = dict(route501["recycle_comp"])

    # ----- auxiliary faceplate trims (stepped for liveness; off the network)
    #   FIC-328405 / LIC-323503 dropped from here: both now step on the live 718A/718B/323D011 network.
    # (TIC-328008 is stepped earlier, immediately before its FIC-328404 slave -- see TD-004.
    #  Stepping it a second time here would advance the controller twice per tick.)
    # AUDIT C32 — the differential PV subtracted the module constant R328_C003_T746, so only the
    # TT-328013 leg was live: a 328E021 fouling change or a 328C002 bottoms excursion moved the true
    # dT and left the PV flat, i.e. TIC-328012 could not see the upset it exists to detect.  T_746 is
    # the live 328E021 cold outlet already published as TT-328009; at design it is 190.0 exactly.
    _ctrl_ipd(s.TIC_328012, s.a328_c003_T - T_746, dt)                       # differential PV: TT-328013 (bottom) - TT-328012 (3rd tray)
    _ctrl_ipd(s.SIC_323902, s.SIC_323902["op"], dt)
    # (FIC-328406 is now stepped by its own _fic_flow call on the 741 recycle -- see TD-005.
    #  It used to be advanced here with its OWN opening as the PV, which made pv a percentage
    #  that the telemetry then divided by a density.  Stepping it again would double-advance it.)

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
            strip["co2_feed_kmolh"], CO2_T_FEED_C, P_line_bara,
            "CO2 feed gas", "320K002", "322E001", "gas"),
        "STRIP_TOP": make_stream(
            strip["top_kmolh"], strip["T_top"], P_strip_live,
            "Stripper top gas", "322E001", "322E002", "gas"),
        "STRIP_BOT": make_stream(
            strip["bot_kmolh"], strip["T_bot"], P_strip_live,
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

    # Numbered aliases from the supplied absorber/cooling-water maps.  PFD component rows are
    # independently rounded, so make_stream_mass_pct normalizes each row to the live total.
    mapped_m702 = 440.0 + (m_v011 - R3232_E011_MV_DES)
    mapped_m341 = m_341
    mapped_m343 = bot_c005
    streams.update({
        "S0204": make_stream(hv604["comp_kmolh"], hv604["T_out"], hv604["P_out"],
                              "204 HP off-gas", "HV-322604", "322C001", "vapor"),
        "S0341": make_stream_mass_pct(mapped_m341, PFD_324_MASS_PCT["341"], 43.0, 1.0,
                                       "341 absorber vent", "323C005", "328V001", "vapor"),
        "S0343": make_stream_mass_pct(mapped_m343, PFD_324_MASS_PCT["343"], 56.0, 1.0,
                                       "343 ammonia water", "323C005", "328D003 Comp II", "liquid", rho=992.2),
        "S0702": make_stream_mass_pct(mapped_m702, PFD_324_MASS_PCT["702"], 45.0, 1.0,
                                       "702 flash-condenser gas", "323D011", "323C005", "vapor"),
        "S0703": make_stream_mass_pct(vac_stream["703"], PFD_324_MASS_PCT["703"], 116.0, 0.3,
                                       "703 condenser-I inlet", "705 + 790", "324E002", "vapor"),
        "S0705": make_stream_mass_pct(vac_stream["705"], PFD_324_MASS_PCT["705"], 130.0, 0.3,
                                       "705 evaporator-I vapor", "324F001", "324E002", "vapor"),
        "S0706": make_stream_mass_pct(vac_stream["706"], PFD_324_MASS_PCT["706"], 45.0, 0.3,
                                       "706 condenser-I gas", "324E002", "324F002", "vapor"),
        "S0708": make_stream_mass_pct(vac_stream["708"], PFD_324_MASS_PCT["708"], 121.0, 1.0,
                                       "708 ejector-I discharge", "324F002", "323C005", "vapor"),
        "S0709": make_stream_mass_pct(vac_stream["709"], PFD_324_MASS_PCT["709"], 140.0, 0.1,
                                       "709 condenser-II inlet", "324F003", "324E005", "vapor"),
        "S0712": make_stream_mass_pct(vac_stream["712"], PFD_324_MASS_PCT["712"], 40.0, 0.1,
                                       "712 condenser-II gas", "324E005", "324F004", "vapor"),
        "S0714": make_stream_mass_pct(vac_stream["714"], PFD_324_MASS_PCT["714"], 104.0, 0.3,
                                       "714 ejector-II discharge", "324F004", "324E006", "vapor"),
        "S0715": make_stream_mass_pct(vac_stream["715"], PFD_324_MASS_PCT["715"], 41.0, 0.3,
                                       "715 condenser-III gas", "324E006", "324F005", "vapor"),
        "S0717": make_stream_mass_pct(vac_stream["717"], PFD_324_MASS_PCT["717"], 120.0, 1.0,
                                       "717 ejector-III discharge", "324F005", "324E007", "vapor"),
        "S0719": make_stream_mass_pct(vac_stream["719"], PFD_324_MASS_PCT["719"], 45.0, 0.3,
                                       "719 condenser-I condensate", "324E002", "328D003 Comp I", "liquid", rho=999.1),
        "S0720": make_stream_mass_pct(vac_stream["720"], PFD_324_MASS_PCT["720"], 40.0, 0.1,
                                       "720 condenser-II condensate", "324E005", "328D003 Comp I", "liquid", rho=1014.0),
        "S0721": make_stream_mass_pct(vac_stream["721"], PFD_324_MASS_PCT["721"], 41.0, 0.3,
                                       "721 condenser-III condensate", "324E006", "328D003 Comp I", "liquid", rho=1036.0),
        "S0722": make_stream_mass_pct(vac_stream["722"], PFD_324_MASS_PCT["722"], 55.0, 1.0,
                                       "722 final vacuum vent", "324E007", "atmosphere", "vapor"),
        "S0744": make_stream_mass_pct(m_744, PFD_324_MASS_PCT["744"], 44.0, 1.0,
                                       "744 absorber-pump suction", "328D003 Comp I", "322P002", "liquid", rho=1002.0),
        "S0755": make_stream_mass_pct(m_755, PFD_324_MASS_PCT["755"], 40.0, 3.9,
                                       "755 cooled absorber feed", "322E006", "322C001", "liquid", rho=1005.0),
        "S0756": make_stream_mass_pct(m_756, PFD_324_MASS_PCT["756"], 43.0, 3.9,
                                       "756 LP-absorber solution", "322C001", "323C005", "liquid", rho=1003.0),
        "S0759": make_stream_mass_pct(vac_stream["759"], PFD_324_MASS_PCT["759"], 55.0, 1.0,
                                       "759 condenser-IV condensate", "324E007", "328D003 Comp I", "liquid", rho=989.1),
        "S0783": make_stream_mass_pct(fa203_m, PFD_324_MASS_PCT["783"], 32.0, 1.0,
                                       "783 stage-II false air", "atmosphere", "PV-324203", "vapor"),
        "S0784": make_stream_mass_pct(fa202_m, PFD_324_MASS_PCT["784"], 32.0, 1.0,
                                       "784 stage-I false air", "atmosphere", "PV-324202", "vapor"),
        "S0797": make_stream_mass_pct(R3232_M797_DES, PFD_324_MASS_PCT["797"], 46.0, 3.9,
                                       "797 LP-absorber vent", "322C001", "PV-322201", "vapor"),
        "S0924": make_stream({"H2O": vac_stream["924"] / MW_COMP["H2O"]}, 146.0, 4.1,
                              "924 ejector motive", "LP steam", "324F002", "vapor"),
        "S0927": make_stream({"H2O": vac_stream["927"] / MW_COMP["H2O"]}, 146.0, 4.1,
                              "927 ejector motive", "LP steam", "324F004", "vapor"),
        "S0929": make_stream({"H2O": vac_stream["929"] / MW_COMP["H2O"]}, 146.0, 4.1,
                              "929 ejector motive", "LP steam", "324F005", "vapor"),
        "S0954": make_stream({"H2O": s.cpl_flow_kgh / MW_COMP["H2O"]}, 46.0, 12.0,
                              "954 process condensate", "process-condensate header", "322C001", "liquid", rho=990.32),
    })
    for _tag, _supply, _return in (
        ("324E002", "1014", "1015"), ("324E005", "1016", "1017"),
        ("324E006", "1018", "1019"), ("324E007", "1020", "1021"),
    ):
        _node = vac324["nodes"][_tag]
        streams["S" + _supply] = make_stream(
            {"H2O": _node["cw_flow_kgh"] / MW_COMP["H2O"]}, _node["cw_in_c"], 3.6,
            _supply + " cooling-water supply", "1001 header", _tag, "liquid")
        streams["S" + _return] = make_stream(
            {"H2O": _node["cw_flow_kgh"] / MW_COMP["H2O"]}, _node["cw_out_c"], 2.2,
            _return + " cooling-water return", _tag, "1051 header", "liquid")
    streams["S1001"] = make_stream({"H2O": 4_847_000.0 / MW_COMP["H2O"]}, 30.0, 4.7,
                                    "1001 main CW supply", "cooling towers", "CW consumers", "liquid")
    streams["S1051"] = make_stream({"H2O": 4_865_000.0 / MW_COMP["H2O"]}, 39.0, 2.2,
                                    "1051 main CW return", "CW consumers", "cooling towers", "liquid")

    # AI-328701 process-condensate conductivity soft sensor (stream 740, read-only)
    _nh3_740, _urea_740 = ppm_infer_328701(s.a328_c004_T, s.a328_c003_T)
    _ai701_uS = cond_infer_328701(_nh3_740, _urea_740, 0.0)                  # CO2 fully co-stripped with NH3
    _d003_levels = d003_level_telemetry(s)

    # Dynamic sequential-modular tear audit.  These recycle signals cross real vessel/line
    # inventories and therefore advance once per integration tick rather than being iterated to an
    # algebraic steady state.  Report their normalized closure explicitly so steady-state callers
    # can detect convergence and dynamic callers can distinguish transport lag from solver failure.
    _tear_pairs = {
        "328C003_overhead_748": (m748_prev, m_748),
        "328C004_overhead_750": (m750_prev, m_750),
        "328D001_reflux_775": (m775_prev, m_775),
        "323D011_return_718A": (m718A_prev, m_718A),
        "328C004_steam_931": (m931_prev, m_931),
    }
    _tear_resid = {
        key: abs(new - old) / max(abs(new), abs(old), 1.0)
        for key, (old, new) in _tear_pairs.items()
    }
    _tear_tol = 1.0e-6
    _tear_norm = max(_tear_resid.values(), default=0.0)

    # Dynamic Pressure Anchor (Mass Balance ODE) -- PT-329201 lumped HP-loop inventory.
    #   IN : fresh NH3 through the 321P002 A/B triplex pumps (ejector motive), fresh CO2 through
    #        322K001, and the 323P001 LP-carbamate recycle washed into 322E003.
    #   OUT: the LV-322501 bottoms letdown to 323C003 and the HV-322604 inert vent to 328.
    # The design residual SYN_LOOP_RESID_DES_KGH is the constant offset the model's own Path-B
    # reconciliations leave in this five-term boundary (see its definition); crediting it through the
    # live loop-mass fraction makes dP/dt EXACTLY zero at the design seed -- so PT-329201 holds 140.7
    # bar a and LV-322501's letdown head, which every 323/324 anchor rides on, stops bleeding -- while
    # leaving the raw balance intact on an empty loop (m_loop_frac -> 0), where zero feeds must still
    # create nothing.  m_loop_frac is clamped to 1.0, so surplus inventory cannot over-credit either.
    C_loop = SYN_LOOP_C_KG_PER_BAR
    m_in_loop = (F_pump_total_th * 1000.0) + F_CO2_feed_kgh + m_308
    m_out_loop = drain_kgh + hv604["mass_kgh"]
    m_net_loop = (m_in_loop - m_out_loop) - m_loop_frac * SYN_LOOP_RESID_DES_KGH

    s.p_syn_bara = clamp(s.p_syn_bara + m_net_loop / C_loop * (dt / 3600.0),
                         10.0, 180.0)
                         
    return {
        "t":           time.time(),      # desktop clock (epoch s)
        "t_sim":       s.sim_t,          # plant clock (s since program init); trend X axis
        "RECYCLE_TEAR_RESIDUAL": {
            "method": "observed_dynamic_transport_tears",
            "is_solver_convergence": False,
            "tolerance": _tear_tol,
            "max_relative_residual": _tear_norm,
            "settled": _tear_norm <= _tear_tol,
            "residuals": _tear_resid,
        },
        "sm_diagnostics": {
            "hpcc": locals().get("hpcc", {}),
            "ej": locals().get("ej", {}),
            "react": locals().get("react", {}),
            "hv604": locals().get("hv604", {}),
            "vac324": locals().get("vac324", {}),
        },
        "sm_diagnostics": {
            "hpcc": locals().get("hpcc", {}),
            "ej": locals().get("ej", {}),
            "react": locals().get("react", {}),
            "hv604": locals().get("hv604", {}),
            "vac324": locals().get("vac324", {}),
        },
        # G7: every recycle in the flowsheet is explicitly one of two kinds. ALGEBRAIC loops (the 324
        # vacuum P/T tears, no inter-stage holdup within a tick) are iterated to a declared residual by
        # a bounded Picard fixed-point each tick; DYNAMIC loops (328/synthesis tears crossing real
        # vessel/line inventories) advance once per tick as transport lag and report residence, not
        # convergence. This block classifies both so steady-state callers can read the algebraic
        # convergence and dynamic callers can distinguish transport lag from solver failure.
        "RECYCLE_CLASSIFICATION": {
            "algebraic_inner_solves": {
                "method": "bounded_picard_fixed_point",
                "is_solver_convergence": True,
                "tolerance": R324_PT_LOOP_TOL,
                "max_iterations": R324_PT_LOOP_MAXIT,
                "fallback": "last_iterate",
                "loops": {
                    tag: {
                        "iterations": _DIAG.get(tag, {}).get("iteration_count"),
                        "residual": _DIAG.get(tag, {}).get("iteration_residual"),
                        "converged": _DIAG.get(tag, {}).get("converged"),
                    }
                    for tag in ("E001", "E003")
                },
                "all_converged": all(_DIAG.get(tag, {}).get("converged", False)
                                     for tag in ("E001", "E003")),
            },
            "dynamic_transport_tears": {
                "method": "observed_dynamic_transport_tears",
                "is_solver_convergence": False,
                "tolerance": _tear_tol,
                "max_relative_residual": _tear_norm,
                "settled": _tear_norm <= _tear_tol,
                "loops": list(_tear_pairs.keys()),
            },
        },
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
                "kgh":      round(m_strip * 3600.0, 0),      # LIVE MP steam flow (kg/h), tracks load (G8)
                "duty_kW":  round(Q_strip_kjh / 3600.0, 0),  # LIVE strip duty (kW) = DES * feed-load ratio
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
                "P_bara":     round(s.r323_f010_P, 3),                       # PT-323204 (bar a, live off HV-323605/329605)
                "HV_323605":  round(s.HIC_323605, 1),                        # gas-outlet hand valve (%) — opening drops P
                "LI_323F010": round(s.r323_f010_M / R323_F010_M_FULL * 100.0, 1),
                "feed331_th": round(m_331 / 1000.0, 2),                      # urea-recovery return (t/h)
                "evap_th":    round(m_evap / 1000.0, 2),                     # vapour 790 -> vac (t/h)
                "product317_th": round(m_317 / 1000.0, 2),                   # product -> 323D002 (t/h)
                "Q_kW":       round(Q_e010_kw, 0),                           # heater 323E010 duty (kW)
                "TIC_323012": {"pv": round(s.TIC_323012["pv"], 1), "sp": round(s.TIC_323012["sp"], 1),
                               "op": round(s.TIC_323012["op"], 2), "mode": s.TIC_323012["mode"]},
                "PIC_329208": {"pv": round(s.PIC_329208["pv"], 2), "sp": round(s.PIC_329208["sp"], 2),
                               "op": round(s.PIC_329208["op"], 1), "mode": s.PIC_329208["mode"]},
            },
            "D002": {                            # Urea Solution Tank 323D002 (2-compartment, atm)
                "T_C":        round(s.r323_d002_T, 1),                       # kept for existing callers
                "TI_323008":  round(s.r323_d002_T, 1),                       # Comp I bulk temp (C, TAL)
                "LI_323507":  round(lvl_d002_I, 1),                          # Comp I level (%, live density)
                "LI_323504":  round(s.r323_d002_M_II / v_II_full * 100.0, 1),# Comp II level (%)
                "LI_comp2":   round(s.r323_d002_M_II / v_II_full * 100.0, 1),# legacy alias of LI-323504
                "HV_tie":     bool(s.HV_323D002_TIE),                        # field tie-in spool Comp I <-> Comp II
                "rho_kgm3":   round(rho_d002, 1),                            # live solution density (C10)
                "m3_comp1":   round(s.r323_d002_M_I / rho_d002, 1),          # Comp I inventory (m3)
                "m3_comp2":   round(s.r323_d002_M_II / rho_d002, 1),         # Comp II inventory (m3)
                "urea_pct":   round(s.w_d002.get("Urea", 0.0) * 100.0, 2),   # TD-013: live, no longer pinned
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
                # FIC-328402 is a VOLUMETRIC loop: pv/sp are m3/h (the operator enters SP in m3/h).
                "FIC_328402": {"pv": round(s.FIC_328402["pv"], 2), "sp": round(s.FIC_328402["sp"], 2),
                               "op": round(s.FIC_328402["op"], 1), "mode": s.FIC_328402["mode"],
                               "vol_m3h": round(m_744 / RHO_744_KGM3, 2),   # PFD stream 744 (raw, unlagged)
                               "kgh": round(m_744, 1)},
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
                "FIC_323401": {"pv": round(s.FIC_323401["pv"], 2), "sp": round(s.FIC_323401["sp"], 2),
                               "op": round(s.FIC_323401["op"], 1), "mode": s.FIC_323401["mode"],
                               "vol_m3h": round(m_401 / RHO_401_KGM3, 2),   # volumetric loop PV (m3/h), PFD 401 flush
                               "m_kgh": round(m_401, 1)},                   # delivered mass -> 328D003 (kg/h, HMB)
                # FIC-323402 is a VOLUMETRIC loop: pv/sp are m3/h (the operator enters SP in m3/h).
                "FIC_323402": {"pv": round(s.FIC_323402["pv"], 2), "sp": round(s.FIC_323402["sp"], 2),
                               "op": round(s.FIC_323402["op"], 1), "mode": s.FIC_323402["mode"],
                               "vol_m3h": round(m_402 / RHO_791_KGM3, 2),   # PFD stream 791 (raw, unlagged)
                               "m_kgh": round(m_402, 1)},                   # delivered mass -> 323E011 (kg/h, HMB)
            },
            "C005": {                            # 323C005 off-gas scrubber -> 328V001
                "TT_323C005": round(s.a323_c005_T, 1),                     # scrub liquid temp (C, hold 55)
                "LI_323503":  round(s.a323_c005_M / A323_C005_M_DES * 50.0, 1),
                "bot_th":     round(bot_c005 / 1000.0, 2),                 # bottoms -> 328V001 (t/h)
                "in756_kgh":  round(m756_prev, 1),
                "in702_kgh":  round(m702_prev, 1),
                "in708_kgh":  round(m708_prev, 1),
                "out343_kgh": round(mapped_m343, 1),
                "out341_kgh": round(mapped_m341, 1),
                "closure_kgh": round(m756_prev + m702_prev + m708_prev
                                     - mapped_m343 - mapped_m341, 6),
                "FIC_323418": {"pv": round(s.FIC_323418["pv"], 2), "sp": round(s.FIC_323418["sp"], 2),
                               "op": round(s.FIC_323418["op"], 1), "mode": s.FIC_323418["mode"],
                               "vol_m3h": round(m_718B / RHO_718_KGM3, 2),  # volumetric loop PV (m3/h), PFD 718B
                               "m_kgh": round(m_718B, 1)},                  # 718B slipstream -> 323E003 (kg/h)
                "FIC_328405": {"pv": round(s.FIC_328405["pv"], 2), "sp": round(s.FIC_328405["sp"], 2),
                               "op": round(s.FIC_328405["op"], 1), "mode": s.FIC_328405["mode"],
                               "vol_m3h": round(m_793 / RHO_401_KGM3, 2),   # volumetric loop PV (m3/h), PFD 793
                               "m_kgh": round(m_793, 1)},                   # 793 spare draw off 328D003 Comp-II (kg/h)
                "LIC_323503": {"pv": round(s.LIC_323503["pv"], 1), "sp": round(s.LIC_323503["sp"], 1),
                               "op": round(s.LIC_323503["op"], 1), "mode": s.LIC_323503["mode"]},
            },
        },
        "DESORB_328": {                          # Screen 328-1 : Desorption / Hydrolysis train
            "C002": {                            # 328C002 Desorber-I (bottoms 139°C)
                "R328_C002_T_BOT_BOT": round(s.a328_c002_T, 1),                     # bottom temp (C, hold 139)
                "TT_328007":  round(s.a328_c002_T, 1),                     # bottoms draw -> 328P006 (stream 743, 139C)
                # AUDIT B4: TT-328008 belongs on the 328C002 OVERHEAD (stream 737, 117 C -> 328E004),
                # per Mapping of Desorber Hydrolyzer unit.md:46.  It used to be published in the D001
                # block off the frozen 328E007 cold outlet (114 C) and aliased to TT-328010.
                "TT_328008":  round(s.a328_c002_T - R328_C002_DT_TOP, 1),  # column top / stream 737 (C, 117)
                "P_bara":     round(s.a328_c002_P, 2),                     # AUDIT C1: live column pressure (3.5 bar a)
                "TT_328010":  round(T_738, 1),                             # 328E007 cold out -> feed 738 (C, 114)
                "LI_328503":  round(s.a328_c002_M / R328_C002_M_DES * 50.0, 1),
                "feed738_th": round(m_738 / 1000.0, 2),                    # 328D003 feed via 328E007 (t/h)
                "ovhd737_th": round(m_737 / 1000.0, 2),                    # top vapour -> 328D001 (t/h)
                "bot743_th":  round(m_743 / 1000.0, 2),                    # bottoms -> 328C003 (t/h)
                "LIC_328503": {"pv": round(s.LIC_328503["pv"], 1), "sp": round(s.LIC_328503["sp"], 1),
                               "op": round(s.LIC_328503["op"], 1), "mode": s.LIC_328503["mode"]},
            },
            "C003": {                            # 328C003 Hydrolyser (200°C, MP steam)
                "TT_328C003": round(s.a328_c003_T, 1),                     # temp (C, hold 200)
                "TT_328012":  round(T_746, 1),                             # 3rd tray / 746 (C, 190) - AUDIT C32: live 328E021 cold outlet
                # AUDIT B6: TT-328011 is on the 328C003 OVERHEAD line (stream 748, 188 C) per
                # Mapping of Desorber Hydrolyzer unit.md:17.  It used to be aliased onto TT-328012's
                # frozen 3rd-tray value, so the operator had no independent hydrolyser-overhead read.
                "TT_328011":  round(s.a328_c003_T - R328_C003_DT_748, 1),  # OVHD 748 -> 328C002 (C, 188)
                "TT_328009":  round(T_746, 1),                             # 328E021 cold out -> C003 feed (stream 746, 190C)
                "P_bara":     round(s.a328_c003_P, 2),
                "LI_328504":  round(s.a328_c003_M / R328_C003_M_DES * 50.0, 1),
                "steam911_th":round(m_911 / 1000.0, 2),                    # FIC-329402 MP steam (t/h)
                "ovhd748_th": round(m_748 / 1000.0, 2),                    # relief -> 328C002 (t/h)
                "bot747_th":  round(m_747 / 1000.0, 2),                    # bottoms -> 328C004 (t/h)
                # AUDIT F-7/TD-008: the hydrolysis reaction is now IN the mass balance
                "X_hydrolysis": round(x_hyd_328 * 100.0, 4),               # urea conversion (%)
                "xi_urea_kmolh": round(xi_hyd_328, 4),                     # extent (kmol/h destroyed)
                "urea_in_kgh":  round(urea_in_328, 1),                     # urea fed with stream 746
                "urea_slip_ppm":round(ppm_urea_747, 3),                    # unreacted urea -> 328C004
                "gas_hyd_kgh":  round(gas_hyd, 1),                         # NH3+CO2 made by reaction
                "gas_strip_kgh":round(gas_str, 1),                         # carried over by MP steam
                "PIC_328203": {"pv": round(s.PIC_328203["pv"], 2), "sp": round(s.PIC_328203["sp"], 2),
                               "op": round(s.PIC_328203["op"], 1), "mode": s.PIC_328203["mode"]},
                "LIC_328504": {"pv": round(s.LIC_328504["pv"], 1), "sp": round(s.LIC_328504["sp"], 1),
                               "op": round(s.LIC_328504["op"], 1), "mode": s.LIC_328504["mode"]},
                "FIC_329402": {"pv": round(s.FIC_329402["pv"], 1), "sp": round(s.FIC_329402["sp"], 1),
                               "op": round(s.FIC_329402["op"], 1), "mode": s.FIC_329402["mode"]},
                "TIC_328012": {"pv": round(s.TIC_328012["pv"], 1), "sp": round(s.TIC_328012["sp"], 1),
                               "op": round(s.TIC_328012["op"], 2), "mode": s.TIC_328012["mode"]},
            },
            "C004": {                            # 328C004 Desorber-II (143°C, LP steam, FFIC ratio)
                "R328_C004_T": round(s.a328_c004_T, 1),                     # temp (C, hold 143)
                "TT_328005":  round(s.a328_c004_T, 1),                     # bottoms draw -> 328E007 (stream 739, 143C)
                "TT_328004":  round(s.a328_c004_T - R328_C004_DT_DES, 1),  # top tray = OVHD 750 (140C), tracks live bottoms
                "P_bara":     round(s.a328_c004_P, 2),                     # AUDIT C1: live column pressure (3.7 bar a)
                "LI_328505":  round(s.a328_c004_M / R328_C004_M_DES * 50.0, 1),
                "steam931_th":round(m_931 / 1000.0, 2),                    # FIC-329401 LP steam (t/h)
                "ovhd750_th": round(m_750 / 1000.0, 2),                    # relief -> 328C002 (t/h)
                "bot739_th":  round(m_739 / 1000.0, 2),                    # bottoms -> 328E007 (stream 739, t/h)
                "recyc741_th":round(m_741 / 1000.0, 2),                    # 740 condensate diverted back to Comp II (FIC-328406, t/h)
                "export740_th":round(max(m_739 - m_741, 0.0) / 1000.0, 2), # 740 leaving the envelope = 739 - 741 (t/h)
                "TT_328006":   round(T_740, 1),                            # stream 740 condensate temp (89C, 328E007 hot out) - AUDIT C10: live
                "AI_328701":   round(_ai701_uS, 2),                        # process-condensate conductivity (uS/cm @25C)
                "nh3_740_ppm": round(_nh3_740, 3),                        # derived trace NH3 slip (ppm mass)
                "urea_740_ppm":round(_urea_740, 3),                       # derived trace urea slip (ppm mass)
                "FFIC_329401":{"pv": round(s.FFIC_329401["pv"], 4), "sp": round(s.FFIC_329401["sp"], 4),
                               "op": round(s.FFIC_329401["op"], 1), "mode": s.FFIC_329401["mode"]},
                "FIC_329401": {"pv": round(s.FIC_329401["pv"], 1), "sp": round(s.FIC_329401["sp"], 1),
                               "op": round(s.FIC_329401["op"], 1), "mode": s.FIC_329401["mode"]},
                "LIC_328505": {"pv": round(s.LIC_328505["pv"], 1), "sp": round(s.LIC_328505["sp"], 1),
                               "op": round(s.LIC_328505["op"], 1), "mode": s.LIC_328505["mode"]},
            },
            "D001": {                            # 328D001 Desorber-I reflux drum (61°C, 328E004)
                "TT_328D001": round(s.a328_d001_T, 1),                     # temp (C, hold 61)
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
                # FIC-328404 is a VOLUMETRIC loop: pv/sp are m3/h (the operator enters SP in m3/h).
                "FIC_328404": {"pv": round(s.FIC_328404["pv"], 2), "sp": round(s.FIC_328404["sp"], 2),
                               "op": round(s.FIC_328404["op"], 1), "mode": s.FIC_328404["mode"],
                               "vol_m3h": round(m_775 / RHO_775_KGM3, 2),   # PFD stream 775 (raw, unlagged)
                               "m_kgh": round(m_775, 1)},                   # delivered mass -> 328C002 (kg/h, HMB)
                "TIC_328002": {"pv": round(s.TIC_328002["pv"], 1), "sp": round(s.TIC_328002["sp"], 1),
                               "op": round(s.TIC_328002["op"], 2), "mode": s.TIC_328002["mode"]},
                # TT-329007: 328E004 cooling-water return temp = PFD stream 1029 (C). 38 at the design
                # TV-328002 opening (50 %); INVERSE in CW flow so opening TV-328002 cools the return and
                # closing it heats the return (TIC-328002 sets the opening). Clamped at the flash ceiling.
                "TT_329007": round(min(R328_E004_CW_T_IN_C
                                       + (R328_E004_CW_T_OUT_DES_C - R328_E004_CW_T_IN_C)
                                         * (R328_E004_TV_OP_DES / max(s.TIC_328002["op"], 1.0)),
                                       R328_E004_CW_T_MAX_C), 1),
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
                "vent_th":    round(vent_c001 / 1000.0, 2),               # inert + slip vent -> 328V001 (t/h)
                # TD-009 remainder — live vent NH3 slip (was a boot-pinned split; now off the species balance)
                "vent_nh3_kgh": round(vent_c001 * (y_vent["NH3"] if y_vent else 0.0), 1),  # NH3 -> 328V001/atm (kg/h)
                "vent_nh3_pct": round((y_vent["NH3"] if y_vent else 0.0) * 100.0, 2),  # NH3 mass% in the atm vent
                "vent_co2_pct": round((y_vent["CO2"] if y_vent else 0.0) * 100.0, 2),  # CO2 mass% in the atm vent
                "liq_nh3_pct":  round(s.a328_c001_w.get("NH3", 0.0) * 100.0, 2),        # dissolved NH3 in the liquor
                "liq_co2_pct":  round(s.a328_c001_w.get("CO2", 0.0) * 100.0, 2),        # dissolved CO2 in the liquor
                "liquor756_th": round(m_756 / 1000.0, 2),                 # LV-322502 draw -> 323C005 (t/h)
                "cpl_kgh":    round(s.cpl_flow_kgh, 1),                    # FT-322404: condensate 954 in (kg/h, operator-set)
                "make_conc_pct": round(abs_c001 / max(m_756, 1e-6) * 100.0, 2),  # absorbed NH3/CO2 fraction of 756 draw (dilutes as CPL rises)
                "XV_322915":  bool(s.XV_322915),                          # steam-flood trip valve (22.1)
                "PIC_322201": {"pv": round(s.PIC_322201["pv"], 2), "sp": round(s.PIC_322201["sp"], 2),
                               "op": round(s.PIC_322201["op"], 1), "mode": s.PIC_322201["mode"]},
                "LIC_322502": {"pv": round(s.LIC_322502["pv"], 1), "sp": round(s.LIC_322502["sp"], 1),
                               "op": round(s.LIC_322502["op"], 1), "mode": s.LIC_322502["mode"]},
            },
            "D003": {                            # 328D003 active bays I/II + accumulation bay III
                "TT_328I":    round(s.a328_d003_TI, 1),
                "TT_328II":   round(s.a328_d003_TII, 1),
                "TT_328III":  round(s.a328_d003_TIII, 1),
                **_d003_levels,
                "capacities_m3": {"I": A328_D003_VOL_I_M3,
                                    "II": A328_D003_VOL_II_M3,
                                    "III": A328_D003_VOL_III_M3},
                "form735_th": round(m_735 / 1000.0, 2),                    # Comp-II -> 328C002
                "collect755_th": round(m_755 / 1000.0, 2),                 # Comp-I -> 322P002/E006/C001
                "flow755_m3h": round(m_755 / A328_M755_RHO, 2),            # FT-322402: 755 draw in m3/h (des 31.3)
                "compI_pfd_rounding_kgh": round((m_719 + m_720 + m_721 + m_759) - m_744, 3),
                "compII_pfd_rounding_kgh": round((bot_c005 + m_741)
                                                   - (m_735 + m_401 + m_402 + m_793), 3),
                # FIC-328406 is the PFD-741 process-condensate RECYCLE, 328E007 -> 328E001 -> Comp II
                # (TD-005).  Normally closed, so pv/sp read 0.00 m3/h at 100 % load.  It is now a
                # VOLUMETRIC loop: pv/sp are already m3/h, and m_kgh carries the delivered mass that
                # the Comp-II holdup ODE actually sees.
                "FIC_328406": {"pv": round(s.FIC_328406["pv"], 2), "sp": round(s.FIC_328406["sp"], 2),
                               "op": round(s.FIC_328406["op"], 1), "mode": s.FIC_328406["mode"],
                               "vol_m3h": round(m_741 / RHO_741_KGM3, 2),   # PFD stream 741 (raw, unlagged)
                               "m_kgh": round(m_741, 1)},                   # recycle -> 328D003 Comp II (kg/h)
                # AUDIT C4 / gap G5: unit-328 energy-closure ledger (kW).  Envelope {C002,C003,C004,
                # D001,E021,E007}, reference 0 C.  Q328_react_kW is the explicit carbamate-desorption
                # reaction enthalpy the reboiler steam supplies (previously hidden in back-solved
                # latents); with it made explicit the residual closes at design and stays bounded as
                # a true off-design departure -- see the derivation at the diagnostic itself.
                "Q328_in_kW":    round(q328_in, 1),
                "Q328_out_kW":   round(q328_out, 1),
                "Q328_react_kW": round(q328_react, 1),
                "Q328_resid_kW": round(q328_resid, 1),
                "P002A":      {"on": s.aux_pumps["322P002A"]["on"], "mode": s.aux_pumps["322P002A"]["mode"]},
                "P002B":      {"on": s.aux_pumps["322P002B"]["on"], "mode": s.aux_pumps["322P002B"]["mode"]},
            },
        },
        "EVAP_324": {                            # Screens 324-1 / 324-1B : two-stage vacuum evaporation
            "E001": {                            # Screen 324-1 : Evaporator I 324E001 / 324F001 (130 C, 0.33 bar a)
                "TT_324001":   round(s.r324_e001_T, 1),                       # melt temp (C, hold 130)
                # AUDIT B8 — PT-324201 is the 324F001 SEPARATOR transmitter (mapping doc line 11) and
                # is the pressure input to the PY-324201 concentration inferential; PIC-324202 is the
                # 324E002 SHELL controller (line 14).  The separator vacuum used to be published only
                # under the shell controller's tag, so PT-324201 was invisible on the HMI.  The shell
                # retains the PFD's rounded manifold pressure because no gas-side pressure-drop datum exists.
                "PT_324201":   round(s.r324_f001_P, 3),                       # 324F001 separator vacuum (bar a, hold 0.33)
                "PT_324202":   round(s.r324_f001_P, 3),                       # 324E002 shell pressure (shared rounded PFD manifold)
                "LI_324F001":  round(s.r324_f001_M / R324_F001_M_FULL * 100.0, 1),
                "feed_th":     round(feed1_m / 1000.0, 2),                    # blended Stage-1 feed (t/h)
                "vapour_th":   round(v1_m / 1000.0, 2),                       # water vapour -> 324E002 (t/h)
                "melt_th":     round(m_p1 / 1000.0, 2),                       # 95% melt -> Stage 2 (t/h)
                "urea_pct":    round(w1_live * 100.0, 1),                     # AUDIT F-4: LIVE melt conc (94.31 % @design)
                "PY_324201":   round(conc_infer_324(w1_live, R324_E001_T_SP_C, R324_F001_P_BARA,
                                                    s.r324_e001_T, s.r324_f001_P), 1),   # live conc soft-sensor (wt %)
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
                "LI_329505":   round(s.r324_e001_cond_M / R324_E001_COND_M_FULL * 100.0, 1),   # 324E001 shell condensate level (%)
                "cond_kgh":    round(cond_gen, 0),                            # 324E001 steam condensate generated (kg/h)
                "LIC_329505":  {"pv": round(s.LIC_329505["pv"], 1), "sp": round(s.LIC_329505["sp"], 1),
                                "op": round(s.LIC_329505["op"], 1), "mode": s.LIC_329505["mode"]},
                "HIC_329605":  round(s.HIC_329605, 1),                        # 324F002 motive-steam hand valve (%)
                "HV_329605":   round(s.HIC_329605, 1),                        # HV-329605 opening (tracks HIC 1:1)
                "motive_kgh":  round(mot9605_m, 0),                           # 324F002 motive LP steam flow (kg/h)
                "P_324E002_sh":round(s.r324_f001_P, 3),                       # 324E002 shell = 324F001 manifold (bar a); HV-329605 drops it
            },
            "E003": {                            # Screen 324-1B : Evaporator II 324E003 / 324F003 (140 C, 0.131 bar a)
                "TT_324002":   round(s.r324_e003_T, 1),                       # melt temp (C, hold 140)
                # AUDIT B8 — PT-324204 is the 324F003 separator transmitter (mapping doc line 20) and
                # feeds the AY-324701 inferential; PIC-324203 is the 324E005 shell controller (line 24).
                "PT_324204":   round(s.r324_f003_P, 3),                       # 324F003 separator vacuum (bar a, hold 0.131)
                "PT_324203":   round(s.r324_f003_P, 3),                       # 324E005 shell pressure (shared rounded PFD manifold)
                "LI_324F003":  round(s.r324_f003_M / R324_F003_M_FULL * 100.0, 1),
                "feed_th":     round(feed2_m / 1000.0, 2),                    # 95% melt from Stage 1 (t/h)
                "vapour_th":   round(v2_m / 1000.0, 2),                       # water vapour -> 324E005 (t/h)
                "melt_fwd_th": round(m_fwd / 1000.0, 2),                      # urea melt via LV-324501A -> BL (t/h)
                "recyc_th":    round(m_recyc / 1000.0, 2),                    # melt via LV-324501B relief -> 323D002 (t/h)
                "route":       route501["route"],
                "selector_stream": route501["selector_stream"],
                "selector_feed_th": round(route501["selector_feed_kgh"] / 1000.0, 3),
                "selector_feed_T_C": round(route501["selector_feed_T_C"], 3),
                "selector_feed_comp": {k: round(v, 8) for k, v in route501["selector_feed_comp"].items()},
                "UF85_interlocked": route501["uf85_interlocked"],
                "UF85_measured_ratio": round(uf_cascade["measured_ratio"], 8),
                "UF85_ratio_command": round(uf_cascade["ratio_command"], 8),
                "UF85_flow_setpoint_th": round(uf_cascade["flow_setpoint_th"], 6),
                "route_mass_residual_kgh": round(route501["mass_residual_kgh"], 9),
                "route_species_residual_kgh": {
                    k: round(v, 9) for k, v in route501["species_residual_kgh"].items()
                },
                "route_energy_residual_kw": round(route501["energy_residual_kw"], 9),
                "LV_324501A":  round(lva_stroke, 1),                          # level-controlled melt export to BL (%)
                "LV_324501B":  round(lvb_stroke, 1),                          # normally-closed relief -> 323D002 (%)
                "PIC_335201":  round(s.PIC_335201, 2),                        # 335 melt-header pressure (bar g, BL boundary)
                "LVB_relief_barg": R335_LVB_RELIEF_BARG,                      # LV-324501B opens above this (bar g)
                "recycle_selected": bool(recycle_selected),                  # True when PIC-335201 > relief (LV-B open)
                "urea_pct":    round(w2_live * 100.0, 1),                     # AUDIT F-5: LIVE product conc (97.71 % @design)
                "AY_324701":   round(conc_infer_324(w2_live, R324_E003_T_SP_C, R324_F003_P_BARA,
                                                    s.r324_e003_T, s.r324_f003_P), 1),   # live conc soft-sensor (wt %)
                "product_th":  round(m_product / 1000.0, 2),                  # urea melt -> BL (t/h; UF85 deferred)
                "uf85_kgh":    round(m_uf, 1),                                # UF85 injection (kg/h; 0 until 335 simulated)
                "uf85_m3h":    round(m_uf / R324_UF85_RHO, 2),                # UF85 injection (m3/h @1305 kg/m3)
                "p_chest_bara":round(p_chest_e003, 2),                        # steam chest press. (bar a)
                "Q_kW":        round(Q_e003_kw, 0),                           # Evap-II duty (kW)
                "HIC_329606":  round(s.HIC_329606, 1),                        # 324F004/F005 motive-steam hand valve (%)
                "HV_329606":   round(s.HIC_329606, 1),                        # HV-329606 opening (tracks HIC 1:1) — opening drops 324F003/E005 P
                "P_324E005_sh":round(s.r324_f003_P, 3),                       # 324E005 shell = 324F003 manifold (bar a)
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
                "condensate_th": round(m_324_cond / 1000.0, 2),              # 719+720+721+759 -> 328D003 Comp I (t/h)
                "vent_kgh":      round(m_324_vent, 1),                        # non-condensable vent -> atm (kg/h)
                "mix703_residual_kgh": round(vac324["mixing_residual_703_kgh"], 3),
                **{
                    _tag: {
                        "Q_kW": round(_node["q_kw"], 1),
                        "UA_kW_K": round(_node["ua_kw_k"], 3),
                        "UA_eff_kW_K": round(_node["ua_eff_kw_k"], 3),
                        "LMTD_K": round(_node["lmtd_k"], 3),
                        "cw_in_th": round(_node["cw_flow_kgh"] / 1000.0, 3),
                        "cw_in_C": round(_node["cw_in_c"], 2),
                        "cw_out_C": round(_node["cw_out_c"], 2),
                        "inlet_kgh": round(_node["inlet_kgh"], 1),
                        "condensate_kgh": round(_node["condensate_kgh"], 1),
                        "vent_kgh": round(_node["vent_kgh"], 1),
                        "mass_residual_kgh": round(_node["mass_residual_kgh"], 6),
                        "energy_residual_kW": round(_node["energy_residual_kw"], 6),
                        "area_m2": VACUUM_CONDENSERS[_tag]["area_m2"],
                        "tube_count": VACUUM_CONDENSERS[_tag]["tube_count"],
                    }
                    for _tag, _node in vac324["nodes"].items()
                },
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
            "phi_gas":     {k: hpcc["phi_gas"][k] for k in MW_COMP},   # AUDIT F-6: live (T,P) flash split (unrounded — diag/gate)
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
            # --- steam-network flow transmitters (PFD-anchored dynamic telemetry, t/h; see FT403/407
            #     anchor block above -- OEM 1750 MTPD 100% load, streams 901/902/903/911/963/932) ---
            # FT-329403 (stream 901 supply main): live BL steam to 328C003(911) + 329D005(902) +
            #   329D009(903) + 322D001A/B(963).  m_911 (kg/h, FIC-329402) + (902+903 PFD)*live strip
            #   ratio + 963(static 0) ; -> 60.85 t/h @design, scales with live strip-steam load.
            "FT_329403_th": round((m_911
                                   + (FT403_S902_DES + FT403_S903_DES)
                                     * (s.steam.m_supply / M_STRIP_DES_KGS)
                                   + FT403_S963_DES) / 1000.0, 2),
            # FT-329407 (stream 932): actual PV-329207B turbine export, kg/s -> t/h.
            "FT_329407_th": round(s.steam.m_turbine * 3.6, 2),
            "FT_329407_design_th": round(FT407_S932_DES / 1000.0, 2),
            "MP": {
                "P_bara":      round(s.steam.P_MP, 2),       # MP header pressure (bar a)
                "TI_sat":      round(tsat_steam(s.steam.P_MP), 1),  # MP sat temp (C)
                "supply_pct":  round(s.steam.valve_supply_pct, 1),  # MP supply valve opening (%)
                "m_supply_th": round(s.steam.m_supply * 3.6, 1),    # supply flow (t/h)
            },
            "LP": {
                "P_bara":      round(P_LP_hpcc, 2),          # pressure used by HPCC this SM pass
                "P_next_bara": round(s.steam.P_LP, 2),       # advanced header state for next pass
                # Same plant-anchored saturation basis used by the HPCC shell calculation.
                "TI_sat":      round(T_shell_lp, 1),
                "TI_HPCC_shell": round(T_shell_lp, 1),       # reduced-model shell T (may be gated)
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
                "m_flash_th":  round(s.steam.m_flash9 * 3.6, 2),    # 904 flash recovery -> vapour
                "m_users_th":  round(s.steam.m_users9 * 3.6, 2),    # actual 9-bar header demand
                "m_ld_th":     round(s.steam.m_ld * 3.6, 2),        # 9 -> 4 let-down (t/h)
            },
            "HP_VENT": {                         # 329D005 HV-329601 atmospheric vent
                "pct":  round(s.steam.hv_vent_hp_pct, 1),
                "m_th": round(s.steam.m_vent_hp * 3.6, 2),
            },
            "LP_MAKEUP": {                       # 4-bar make-up / vent balance
                "PV_329207C": round(s.steam.valve_963_pct, 1),      # BL -> 4-bar (stream 963)
                "HV_329602":  round(s.steam.hv_329602_pct, 1),      # BL -> 4-bar hand valve
                "m_963_th":   round(s.steam.m_963 * 3.6, 2),
                "m_pic_th":   round(s.steam.m_pic * 3.6, 2),        # PIC-329207A/B vent(+)/make-up(-)
            },
            "mass_residual_kg_s": {
                "d005_vapor": s.steam.mass_residual_d005_vapor,
                "d009_vapor": s.steam.mass_residual_d009_vapor,
                "lp_vapor": s.steam.mass_residual_lp_vapor,
                "d005_liquid": s.steam.mass_residual_d005_liquid,
                "d009_liquid": s.steam.mass_residual_d009_liquid,
                "lp_liquid": s.steam.mass_residual_lp_liquid,
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
            "PIC_329206": {                      # LP steam header master controller (4 barg == 5.013 bar a)
                "pv":   round(s.steam.P_LP - 1.01325, 2),            # barg
                "sp":   round(s.steam.master207_sp - 1.01325, 2),     # barg (4.0 barg)
                "op":   round(s.steam.m_pic * 3.6, 2),             # net vent(+)/make-up(-) t/h
                "mode": s.steam.pic207_mode,
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
            "PIC_329207B": {                     # turbine 320MT02 export PV-329207B (SP = master)
                "pv":   round(s.steam.P_LP, 2),
                "sp":   round(s.steam.pic207_sp, 2),
                "op":   round(s.steam.pv207b_pct, 1),              # valve %
                "m_turbine_th": round(s.steam.m_turbine * 3.6, 2),
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
        # AUDIT F-8/TD-009: downstream component species balance (mass %).  `sum` is the C6
        # summation residual per stage and must read 100.000 at all times; `vap` is the live
        # relative-volatility vapour composition leaving each stage.
        "SPECIES_323_324": {
            "liq": {tag: {k: round(w[k] * 100.0, 4) for k in SOL_SPECIES} for tag, w in (
                ("C003", s.w_c003), ("F004", s.w_f004), ("F010", s.w_f010),
                ("D002", s.w_d002), ("E001", s.w_e001), ("E003", s.w_e003))},
            "vap": {tag: {k: round(y[k] * 100.0, 4) for k in SOL_SPECIES} for tag, y in (
                ("305", y_305), ("701", y_701), ("evap", y_evap), ("v1", y_v1), ("v2", y_v2))},
            "sum": {tag: round(sum(w.values()) * 100.0, 6) for tag, w in (
                ("C003", s.w_c003), ("F004", s.w_f004), ("F010", s.w_f010),
                ("D002", s.w_d002), ("E001", s.w_e001), ("E003", s.w_e003))},
            "xi_biuret_kmolh": {"C003": round(xi_c003, 5), "F004": round(xi_f004, 5),
                                "F010": round(xi_f010, 5), "E001": round(xi_e001, 5),
                                "E003": round(xi_e003, 5)},
            # AUDIT C7 — _sol_stage_anchor's clip residual was computed and RETURNED but never read
            # by any caller, contradicting its own docstring ("The clip residual is reported, never
            # hidden").  It is the negative vapour flow the anchor had to clamp to zero and back-charge
            # to water, i.e. mass the PFD's own rounded stream table cannot produce.  E001 carries
            # -170.1 kg/h (1.21 % of the stage vapour) and E003 -126.8 kg/h (4.63 %), both far above
            # the "under 0.4 % everywhere else" the docstring claims.  Published so a future change
            # that widens the clip cannot do it silently.
            "clip_resid_kgh": {tag: round(st.get("resid", 0.0), 3) for tag, st in (
                ("C003", SOL_C003), ("F004", SOL_F004), ("F010", SOL_F010),
                ("E001", SOL_E001), ("E003", SOL_E003))},
            "urea_pct_species": {"E001": round(s.w_e001["Urea"] * 100.0, 2),
                                 "E003": round(s.w_e003["Urea"] * 100.0, 2)},
            # AUDIT F-8: the desorption train's own species vectors.  The two ppm figures are now a
            # MASS-BALANCE result rather than the read-only ppm_infer_328701 soft sensor -- AI-328701
            # can finally be read against something the plant model actually computes.
            "des_liq": {tag: {k: round(w[k] * 100.0, 6) for k in SOL_SPECIES} for tag, w in (
                ("C002", s.w_328c002), ("C003", s.w_328c003), ("C004", s.w_328c004))},
            "des_vap": {tag: {k: round(y[k] * 100.0, 4) for k in SOL_SPECIES} for tag, y in (
                ("737", y_737), ("748", y_748), ("750", y_750))},
            "des_sum": {tag: round(sum(w.values()) * 100.0, 6) for tag, w in (
                ("C002", s.w_328c002), ("C003", s.w_328c003), ("C004", s.w_328c004))},
            "condensate_ppm": {"NH3": round(s.w_328c004["NH3"] * 1e6, 3),
                               "Urea": round(s.w_328c004["Urea"] * 1e6, 3),
                               "CO2": round(s.w_328c004["CO2"] * 1e6, 3)},
            "xi_hydrolysis_kmolh": round(xi_hyd_328, 5),
        },
        "STREAMS": streams,
        "flags":   {k: v for k, v in s.flags.items()},
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
    "FIC_328405": ("MAN", "AUTO"),          # stream 793 spare; the LIC-323503 cascade is gone
    "FIC_323418": ("MAN", "AUTO"),
    # -- 328-1 (desorption / hydrolysis) -----------------------------------
    "LIC_328501": ("MAN", "AUTO"),
    "PIC_328202": ("MAN", "AUTO"),
    "TIC_328002": ("MAN", "AUTO"),
    "FIC_328404": ("MAN", "AUTO", "CAS"),
    "FIC_329402": ("MAN", "AUTO", "CAS"),
    "PIC_328203": ("MAN", "AUTO"),
    "FFIC_329401": ("MAN", "AUTO"),         # steam/feed ratio master (m931 / m744, FIC-328402 leg)
    "FIC_329401": ("MAN", "AUTO", "CAS"),   # LP-steam slave
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
    # -- 324-1 / 324-1b / 335 (evaporation + finishing) --------------------
    #    G7: these are dict controllers, stepped in step_sim and published in telemetry, but were
    #    absent from this whitelist AND the frontend R323 Set, so their faceplates routed to
    #    controller_set -> getattr(s,'TIC-324001') misses on the dash -> every operator write was
    #    silently discarded.  Adding them here + in app.js routes them through r323_ctrl_set, which
    #    applies mode/sp/op to the dict with the correct clamps.  Modes mirror the sibling pattern:
    #    a cascade master is MAN/AUTO, a CAS slave adds CAS.
    "TIC_324001": ("MAN", "AUTO"),          # 324E001 melt-temp master -> PIC-329203
    "PIC_329203": ("MAN", "AUTO", "CAS"),   # 324E001 chest steam-P slave
    "PIC_324202": ("MAN", "AUTO"),          # 324F001 vacuum via false-air PV-324202
    "TIC_324002": ("MAN", "AUTO"),          # 324E003 melt-temp master -> PIC-329212
    "PIC_329212": ("MAN", "AUTO", "CAS"),   # 324E003 chest steam-P slave
    "PIC_324203": ("MAN", "AUTO"),          # 324F003 deep vacuum via false-air PV-324203
    "LIC_324501": ("MAN", "AUTO"),          # 324F003 product level
    "FFIC_335406": ("MAN", "AUTO"),         # 335 UF85-to-product ratio master
    "FIC_335405": ("MAN", "AUTO", "CAS"),   # 335 UF85 inject slave
}

# Auxiliary running/standby pump pairs toggled from the 323-2/328 overlays.
AUX_PUMPS = ("323P001A", "323P001B", "322P002A", "322P002B",
             "328P001A", "328P001B", "328P003A", "328P003B")


def reset_simulation():
    """Return the plant to the fresh runtime seed and zero every accumulating counter.

    This reproduces the exact state the boot sequence itself ends on. Every dynamic
    quantity -- the plant clock (sim_t), all totalizers/holdups, and the MP/LP steam
    headers -- lives inside the State object, so a fresh State() zeroes them in one
    move. The PINNED design constants (HPCC_UA, A328_*, M_HPCC_DES_LIVE, REACT_MASS_DES,
    ...) are module globals set once during boot calibration and are NOT part of State,
    so they survive: none of the ~20 s warm-up reruns -- the dynamic transient is simply
    discarded, exactly as the boot's own trailing `state = State()` does.
    """
    global state, last_packet, hist
    state = State()                 # sim_t -> 0.0; totalizers, holdups, steam headers -> seed
    last_packet = {}                # drop the stale packet so no pre-reset frame is pushed
    hist = Historian()              # trends restart from t=0 (the sim clock just jumped back to 0)
    health["heartbeat"] = 0         # liveness + fault counters cleared for a clean slate
    health["last_step_wall"] = time.time()
    _clear_health_error()
    print("[reset_sim] simulation reset to fresh seed; counters zeroed", flush=True)


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
        elif cmd["id"] == "323D002TIE":
            # 323D002 Comp I <-> Comp II field tie-in spool.  A hand valve with no interlock: the
            # operator may open or close it at any time, and the consequence (a level that collapses
            # into a 380 m3 pool, or a stranded Comp-II inventory) is the training point.
            s.HV_323D002_TIE = not s.HV_323D002_TIE
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

    elif t == "reset_sim":
        # {"type":"reset_sim"}  -- operator reset button beside the backend status LED. Discards the
        #   dynamic transient and zeroes every counter (plant clock, totalizers, trends) without
        #   rerunning boot calibration. See reset_simulation() for why the pinned design constants
        #   survive. `s` above still aliases the OLD State; nothing below this branch reads it.
        reset_simulation()

    elif t == "controller_set":
        cid  = cmd["id"]
        ctrl = getattr(s, cid, None)
        if ctrl is None:
            # G7: do NOT swallow this.  controller_set handles the controllers.py OBJECT loops
            # (pumps, SIC, ratio); the inline DICT loops go through r323_ctrl_set.  A miss here
            # means the frontend routed a tag to the wrong handler (e.g. a dict loop absent from
            # the R323 whitelist), which used to look alive but discard every write.  Surface it.
            print(f"[controller_set] NAK: no object controller '{cid}' "
                  f"(dict loop missing from R323_CTRL_MODES / frontend R323 Set?)", flush=True)
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

    elif t == "cpl_set":                       # FT-322404 condensate 954 -> 322C001, operator-manipulable (kg/h)
        s.cpl_flow_kgh = clamp(_finite(cmd["value"], "cpl"), 0.0, 2.0 * A328_CPL_DES)

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

    elif t == "hic9605_set":                   # HIC-329605 -> HV-329605 324F002 motive-steam hand valve
        if "op" in cmd:
            s.HIC_329605 = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "hic9606_set":                   # HIC-329606 -> HV-329606 324F004/F005 motive-steam hand valve
        if "op" in cmd:
            s.HIC_329606 = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "hic323605_set":                 # HIC-323605 -> HV-323605 323F010 gas-outlet hand valve (790)
        if "op" in cmd:
            s.HIC_323605 = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "pic335201_set":                 # 335 melt-header pressure (bar g); LV-324501B relief input
        if "op" in cmd:
            s.PIC_335201 = clamp(_finite(cmd["op"], "op"), 0.0, 15.0)

    elif t == "lv324501_route_set":            # deprecated: A = normal export to BL; B = force relief recycle
        # Retained for the older UI/command API. LV-324501B is now the PIC-335201 overpressure relief,
        # so "route B" simulates the overpressure that opens it and "route A" restores the design header.
        if "route" in cmd:
            route = str(cmd["route"]).strip().upper()
            if route not in ("A", "B"):
                raise ValueError("LV-324501 route must be A or B")
            force_b = route == "B"
        else:                                   # backward-compatible API used by older layouts/tests
            force_b = bool(cmd.get("recycle", False))
        s.PIC_335201 = (R335_LVB_RELIEF_BARG + 0.5) if force_b else R335_PIC201_DES_BARG

    elif t == "steam_supply_set":              # MP supply valve (utility import -> MP header)
        if "op" in cmd:
            s.steam.valve_supply_pct = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "steam_letdown_set":             # PV-329205B 9->4 let-down (NB: split-range PIC-329205
        if "op" in cmd:                        #   AUTO-drives this each tick -> manual write is transient)
            s.steam.valve_letdown_pct = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "steam_hpvent_set":              # HV-329601 329D005 HP saturator atmospheric vent
        if "op" in cmd:
            s.steam.hv_vent_hp_pct = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "steam_963_set":                 # PV-329207C BL(25)->4-bar header make-up (963)
        if "op" in cmd:
            s.steam.valve_963_pct = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

    elif t == "hic329602_set":                 # HV-329602 BL(25)->4-bar header block
        if "op" in cmd:
            s.steam.hv_329602_pct = clamp(_finite(cmd["op"], "op"), 0.0, 100.0)

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
@asynccontextmanager
async def _lifespan(app):
    asyncio.create_task(sim_task())
    asyncio.create_task(push_task())
    yield

app = FastAPI(lifespan=_lifespan)


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


@app.get("/api/hist")
async def hist_query(paths: str, span: float = 3600.0,
                     max_points: int = Query(800, alias="max"),
                     end: Optional[float] = None):
    """Backfill trend history.

    ``paths`` is a comma-separated list of packet dot-paths (e.g. ``TI_top1``,
    ``controllers.SIC_321950.pv``). ``span`` is in PLANT seconds, and ``end`` is the plant
    time the window closes at (default: newest sample), so a scrolled-back trend can pull an
    older window. Values are decimated to at most ``max`` points with a min/max envelope, so
    spikes survive the reduction.

    REST rather than the WebSocket because backfill is a one-shot bulk pull; live values
    keep arriving on the packet the client already receives.
    """
    wanted = [p for p in (paths or "").split(",") if p]
    if not wanted:
        raise HTTPException(status_code=400, detail="paths is required")
    return hist.query(wanted, max(1.0, float(span)), max(2, int(max_points)), end_sim=end)


@app.get("/api/hist/paths")
async def hist_paths():
    """Every path the historian is recording, plus per-ring occupancy."""
    return {"paths": hist.paths(), "rings": hist.stats()}


@app.get("/api/health")
async def health_probe():
    """Backend fault probe. ok=True while the physics loop is stepping cleanly;
    ok=False with a message+traceback once a step has raised. age_s is seconds
    since the last successful step -- a rising age_s with ok=True means the step
    is HANGING (no exception) rather than crashed. Poll this or read the _health
    block on the /ws packet; both carry the same fault."""
    now = time.time()
    age = round(now - health["last_step_wall"], 2)
    return {
        "ok": health["ok"],
        "heartbeat": health["heartbeat"],
        "age_s": age,
        "stalled": age > 5.0,          # no successful step for 5 s -> loop wedged/crashed
        "error": health["error"],
        "type": health["type"],
        "traceback": health["traceback"],
        "sim_t": health["sim_t"],
        "since": health["since"],
        "count": health["count"],
        "server_wall": now,
    }


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


# -------------------------------------------------------------------------
#  Backend health / fault surface
#
#  Before this block a physics exception inside step_sim() killed the sim_task
#  coroutine outright: the WebSocket kept re-pushing the LAST good packet, so
#  the operator saw a plausible-looking screen that was silently frozen -- the
#  most dangerous failure mode for a training simulator. health now records the
#  fault, the loop stays alive (so the fault reaches every client and the REST
#  probe), and a monotonic heartbeat lets the browser detect a *hang* (step_sim
#  wedged, no exception) as distinct from a clean crash.
# -------------------------------------------------------------------------
health = {
    "ok": True,          # False once step_sim has raised and not yet recovered
    "heartbeat": 0,      # +1 per successful physics step; frozen value == stalled backend
    "last_step_wall": time.time(),   # epoch s of last successful step (browser staleness check)
    "error": None,       # short one-line message (exception type + str)
    "type": None,        # exception class name
    "traceback": None,   # full formatted traceback (last frames), for the fault page
    "sim_t": None,       # plant clock at the moment of failure
    "since": None,       # epoch s when the fault was first raised
    "count": 0,          # how many steps have thrown since the backend last ran clean
}


def _flag_health_error(exc: Exception) -> None:
    tb = traceback.format_exc()
    health["ok"] = False
    health["type"] = type(exc).__name__
    health["error"] = f"{type(exc).__name__}: {exc}"
    health["traceback"] = tb
    health["sim_t"] = getattr(state, "sim_t", None)
    health["count"] = health.get("count", 0) + 1
    if health.get("since") is None:
        health["since"] = time.time()
    # Loud on the server console too -- the operator's screen is not the only place this must show.
    print("=" * 72)
    print("BACKEND STEP FAILURE — physics step raised, simulation is frozen:")
    print(tb)
    print("=" * 72)


def _clear_health_error() -> None:
    if not health["ok"]:
        print("Backend recovered: physics step succeeded again after a fault.")
    health["ok"] = True
    health["error"] = None
    health["type"] = None
    health["traceback"] = None
    health["sim_t"] = None
    health["since"] = None
    health["count"] = 0


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
        try:
            while sim_advance > 1e-9:
                h = min(STEP_CAP, sim_advance)
                last_packet = step_sim(h)
                # Sample inside the sub-step loop, not once per real tick: under FAST one real
                # tick covers 6 plant-seconds, and sampling outside the loop would alias every
                # transient down to that resolution.
                hist.maybe_sample(last_packet, state.sim_t, now)
                sim_advance -= h
                health["heartbeat"] += 1
                health["last_step_wall"] = time.time()
            if not health["ok"]:
                _clear_health_error()
        except Exception as exc:
            # A physics step threw (NaN/blow-up/non-convergence). Record it, keep the
            # coroutine alive so the fault propagates, and back off so we don't spin at
            # 100% CPU re-raising the same exception thousands of times a second.
            _flag_health_error(exc)
            await asyncio.sleep(0.5)
        await asyncio.sleep(DT)


def _packet_with_health(packet: dict) -> str:
    """Serialise the outgoing packet with a fresh _health block stapled on.

    Written every push (not baked into step_sim's return) so that even a STALE
    last_packet -- which is exactly what you have after a crash -- still carries
    the live fault flag out to every connected browser."""
    now = time.time()
    payload = dict(packet)
    payload["_health"] = {
        "ok": health["ok"],
        "heartbeat": health["heartbeat"],
        "age_s": round(now - health["last_step_wall"], 2),  # since last good step
        "error": health["error"],
        "type": health["type"],
        "traceback": health["traceback"],
        "sim_t": health["sim_t"],
        "since": health["since"],
        "count": health["count"],
        "server_wall": now,
    }
    return json.dumps(payload)


async def push_task():
    while True:
        if clients and last_packet:
            msg = _packet_with_health(last_packet)
            dead = []
            for c in list(clients):
                try:
                    await c.send_text(msg)
                except Exception:
                    dead.append(c)
            for d in dead:
                clients.discard(d)
        await asyncio.sleep(0.1)


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
    _cap = {}
    print("[boot-pin] settling design fixed point — phase 1/3 (18 000 ticks) …", flush=True)
    for _ in range(18000):
        res = step_sim(0.1)
    _cap["r"] = res["sm_diagnostics"]["hpcc"]
    _cap["ejm"] = res["sm_diagnostics"]["ej"]["suction_kgh"] / res["sm_diagnostics"]["ej"]["mu"] if res["sm_diagnostics"]["ej"].get("mu", 0) else EJ_MOTIVE_NH3_DES

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
    print("[boot-pin] phase 1 done — phase 2/3 (reactor-mass capture) …", flush=True)
    _capf = {}
    res = step_sim(0.1)
    rr = res["sm_diagnostics"]["react"]
    _capf["feed"]    = rr["feed_kmolh"]
    _capf["xi_urea"] = rr["xi_urea"]; _capf["xi_biu"] = rr["xi_biu"]
    _capf["L"]       = rr["L_feed"];  _capf["W"]      = rr["W_feed"]
    _capf["X"]       = rr["X_conv"]
    _hf = res["sm_diagnostics"]["hpcc"].get("feed_kmolh", {})
    _co2 = _hf.get("CO2", 0.0)
    if _co2 > 1e-9:
        _capf["hpcc_L"] = _hf.get("NH3", 0.0) / _co2

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
    print("[boot-pin] phase 2 done — phase 3/3 (steam sizing, 3 000 ticks) …", flush=True)
    _cap2 = {}
    for _ in range(3000):
        res = step_sim(0.1)
    _cap2["r"] = res["sm_diagnostics"]["hpcc"]
    _duty_des    = _cap2["r"]["duty_kw"]             #   is garbage). Plateau duty is flat ticks 3000-6000.
    _m_hpcc_des    = _duty_des / HPCC_LATENT_4BAR
    global M_HPCC_DES_LIVE
    M_HPCC_DES_LIVE = _m_hpcc_des  # design LP steam-raising anchor (kg/s), == generation into the 4-bar header
    # G8: the 4-bar header exports the design surplus to turbine 320MT02 (PFD-26 stream 932); the H.Ex
    # user boundary gets the generation NOT exported, so generation == users + turbine + vent(0) holds
    # at design with P_LP=4.4 bit-exact and FT-329407 == 16 707 kg/h from the connected PV-329207B.
    _ss.M_USERS_LP = max(_m_hpcc_des - _ss.M_TURBINE_DES, 0.0)   # 4-bar H.Ex boundary = generation - turbine
    _ss.M_504_DES  = max(_m_hpcc_des - _ss.M_503_DES, 0.0)  # makeup is the LP boiloff not supplied by LV503
                                   #   so at the seed m_lv503 + m_valve == m_hpcc -> dm == 0 and
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
    _caphv = {}
    res = step_sim(0.1)
    rr = res["sm_diagnostics"]["hv604"]
    _caphv["m"] = rr["mass_kgh"]; _caphv["T"] = rr["T_out"]
    # ISSUE-c/e: pin the LT-322E002 inventory anchor on this SAME final MAN-seed step.  It belongs at
    # the runtime design seed for the reason the reactor and GCB refs do, and only here is every other
    # constant (reactor tear, HPCC_UA, steam sizing) already in force, so the captured liquid make is
    # exactly what `State(); step_sim()` produces.  Taken off the phase-1 CAS warm-up settle instead, it
    # sat above that value, phi_in started near 0.97 rather than 1.0, and -- with the gravity-head term
    # restored to phi_out -- LT-322E002 would still settle a full 3 % below NLL instead of holding it.
    HPCC_LIQ_DES_LIVE = res["sm_diagnostics"]["hpcc"]["liq_kgh"]
    # Same correction for the 4-bar header anchor.  M_USERS_LP / M_504_DES were sized off the phase-3
    # settle duty, so at the runtime seed the 322D001A/B balance opened by -0.123 kg/s (29.652 raised
    # against 29.774 booked) and P_LP integrated away from 4.0 barg -- which moves tsat in EVERY LP
    # chest (323E002, 323E010, 324E001) and walks the whole evaporation train.  Re-pin on this same
    # MAN-seed step: generation == users + turbine exactly, so residual_lp_vapor == 0 at design.
    #   q_steam_kw, NOT duty_kw: the header sees the steam actually RAISED (duty less the extra
    #   sensible heat leaving in the product above the T_prod pin), which is what step_sim books.
    _m_hpcc_seed = res["sm_diagnostics"]["hpcc"]["q_steam_kw"] / HPCC_LATENT_4BAR   # kg/s LP raised at the seed
    M_HPCC_DES_LIVE = _m_hpcc_seed
    _ss.M_USERS_LP  = max(_m_hpcc_seed - _ss.M_TURBINE_DES, 0.0)
    _ss.M_504_DES   = max(_m_hpcc_seed - _ss.M_503_DES, 0.0)
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
    print("[boot-pin] all phases complete — design constants pinned.", flush=True)


# ---- boot-pin result cache -----------------------------------------------------------------------
#   _pin_hpcc_ua() settles two design fixed points over 21,000 step_sim() ticks (~20 s) to compute a
#   handful of DETERMINISTIC calibration constants.  The result depends only on the simulation source,
#   so it is cached to disk keyed by a SHA-256 of the backend model files: an unchanged tree restores
#   the pinned constants in milliseconds; ANY model edit busts the key and forces a fresh settle.  The
#   exact computed constants are stored and restored -- the settle math is untouched -- so design
#   bit-exactness is preserved while the ~20 s import stall behind the desktop launch is removed.
_HERE           = os.path.dirname(os.path.abspath(__file__))
_PIN_CACHE_PATH = os.path.join(_HERE, ".boot_pin_cache.json")
_PIN_SRC_FILES  = (
    "main.py", "steam_system.py", "reactor.py", "controllers.py",
    "thermo_extended_uniquac.py",
)


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
    global HPCC_NC_DES_LIVE, M_HPCC_DES_LIVE
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
    # G8: the cache stores the design LP GENERATION (M_HPCC_DES_LIVE == users + turbine) separately
    # from the reduced 4-bar user boundary, so both the generation anchor and the 322D001 make-up
    # sizing (M_504_DES == boil-off replaced) match the fresh-boot path. Deriving them from the
    # turbine-reduced M_USERS_LP would undersize the make-up valve and mis-anchor FT-329407.
    _gen_des           = d.get("M_HPCC_DES_LIVE", d["M_USERS_LP"])   # fallback: pre-G8 cache (users==gen)
    _ss.M_USERS_LP     = d["M_USERS_LP"]
    _ss.M_504_DES      = max(_gen_des - _ss.M_503_DES, 0.0)
    M_HPCC_DES_LIVE    = _gen_des          # design LP generation anchor (cache path)
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
        "M_HPCC_DES_LIVE":    M_HPCC_DES_LIVE,   # design LP generation (== users + turbine); G8 cache key
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
        print("[boot-pin] cache hit — design constants restored instantly.", flush=True)
        _apply_pin(_cached)              # cache hit: skip the 21k-tick settle
    else:
        print("[boot-pin] cache miss — running full settle (~20 s). This only happens after a model change.", flush=True)
        _pin_hpcc_ua()                   # cache miss/stale: full settle, then persist for next launch
        try:
            with open(_PIN_CACHE_PATH, "w", encoding="utf-8") as _f:
                json.dump({"key": _key, "pin": _collect_pin()}, _f, indent=2)
        except OSError:
            pass                          # cache is an optimization; never fail import on a write error


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
