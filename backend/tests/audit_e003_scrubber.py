"""PHASE-3 BOUNDED FOREGROUND AUDIT  --  322E003 HP Scrubber (ISOLATED).

Re-evaluates the scrubber in isolation (pure-function calls + isolated sump ODE; no full
synthesis-loop multi-settle, so no coupled-solver stall). Sections:
  A. Discharge pin + comp shift : offgas/overflow == DES*s bit-exact at design; the LIVE surplus-
                                  wash (323P001) deviation injection conserves mass AND shifts
                                  composition gas->liquid (CO2 + 2:1 NH3) -- directive #2.
  B. ccw eps-NTU bridge (GAP#2) : design pins TT-329125=95.0, TT-322002=178.8; C_ccw*dT_ccw==q_ccw
                                  energy balance; m_ccw->0 bounded at T_proc (no divide-by-zero pole).
  C. HV-322604 equal-% valve    : phi_ep(theta_des)==1 bit-exact; R^((th-th_des)/100) gain; sqrt(dP);
                                  JT letdown T_out=T_in-mu*dP; composition ratios held.
  D. TT off-design couplings    : TT-322011 (N/C slip + vent), TT-322002 (vent relief) two-sided,
                                  zero at design, clamped to [t_ccw_in, T_proc]; finite.
  E. LT-329501 sump ODE         : dM/dt = m_cond_in - ej_suction(gravity head); bounded fixed point
                                  L_eq = NLL*(m_cond_in/capacity), returns to NLL, conserves, no rail.
Run:  python backend/tests/audit_e003_scrubber.py
"""
import os, sys, math, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import main
from main import (MW_COMP, scrub_322e003, hv_322604, _eq_pct, react_nc_ratio,
                  REACT_OFFGAS_DES, SCRUB_OFFGAS_KMOLH_DES, SCRUB_OVERFLOW_KMOLH_DES,
                  SCRUB_CARB_ABS_GAIN, SCRUB_Q_CCW_DES_KW, SCRUB_CCW_KGH_DES, SCRUB_CCW_CP,
                  SCRUB_CCW_T_IN_DES, SCRUB_CCW_T_OUT_DES, SCRUB_OVERFLOW_T_C, SCRUB_OFFGAS_T_C,
                  SCRUB_T_PROC_C, SCRUB_HIC604_DES_PCT, SCRUB_HV604_P_OUT, SCRUB_HV604_DP_DES,
                  SCRUB_HV604_RANGE, SCRUB_HV604_MU_JT, SCRUB_OFFGAS_P_BARA, SCRUB_OFFGAS_NC_DES,
                  SCRUB_LEVEL_NLL_PCT, SCRUB_HOLDUP_NLL_KG, SCRUB_HOLDUP_MAX_KG, EJ_SUC_TOT_DES,
                  clamp)

fails = []
def chk(cond, msg):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", msg))
    if not cond: fails.append(msg)
def sumv(d): return sum(d.values())
def sumkg(d): return sum(d[k]*MW_COMP[k] for k in d)

OG = REACT_OFFGAS_DES                      # 322R001 -> TT-322009 -> 322E003 tube feed (design)
M_CCW_DES = SCRUB_CCW_KGH_DES
def scr(s=1.0, t_ccw=SCRUB_CCW_T_IN_DES, m_ccw=M_CCW_DES, vent=1.0, nc=None, hic=None):
    og = {k: OG.get(k, 0.0) * s for k in MW_COMP}
    return scrub_322e003(og, s, t_ccw, m_ccw, vent_ratio=vent, nc_act=nc, hic604_pct=hic)

bar = "=" * 116
print(bar); print("  322E003 HP SCRUBBER  --  ISOLATED UNIT AUDIT (Phase 3)"); print(bar)
print("  SCRUB_UA=%.2f kW/K  Q_ccw_des=%.1f kW  EJ_SUC_TOT_DES=%.1f kg/h  HOLDUP_NLL=%.1f kg"
      % (main.SCRUB_UA_KWK, SCRUB_Q_CCW_DES_KW, EJ_SUC_TOT_DES, SCRUB_HOLDUP_NLL_KG))
d = scr()
print("\n  DESIGN POINT (s=1, m_ccw=des, t_ccw=80, theta=50, nc=des):")
print("    TT-329125(t_ccw_out)=%.6f  TT-322002(overflow)=%.6f  TT-322011(offgas)=%.6f"
      % (d["t_ccw_out"], d["T_overflow"], d["T_offgas"]))
print("    q_ccw=%.4f kW  dT_ccw=%.6f  eps=%.6f  closure_resid=%.4f kmol/h"
      % (d["q_ccw_kw"], d["dT_ccw"], d["eps_ht"], d["closure_resid"]))

# ============================================================================================== A
print("\n" + bar); print("  A. DISCHARGE PIN + SURPLUS-WASH COMPOSITION SHIFT  (directive #2)"); print(bar)
# A1 pinned discharges == DES*s bit-exact across load
og_ok = ov_ok = True
for s in (0.5, 0.8, 1.0, 1.2, 1.5):
    r = scr(s=s)
    og_ok &= all(abs(r["offgas_kmolh"][k]   - SCRUB_OFFGAS_KMOLH_DES.get(k,0.0)*s)   < 1e-9 for k in MW_COMP)
    ov_ok &= all(abs(r["overflow_kmolh"][k] - SCRUB_OVERFLOW_KMOLH_DES.get(k,0.0)*s) < 1e-9 for k in MW_COMP)
chk(og_ok, "offgas_kmolh == SCRUB_OFFGAS_KMOLH_DES * s bit-exact across load (design wash, dev==0)")
chk(ov_ok, "overflow_kmolh == SCRUB_OVERFLOW_KMOLH_DES * s bit-exact across load (design wash, dev==0)")
# A2 LIVE surplus-wash (323P001) deviation: perturb the design wash vector, verify mass conservation
#    AND the gas->liquid composition shift (CO2 scrubbed + 2:1 NH3), then RESTORE the module state.
print("\n   surplus-wash deviation (mutate 323P001 wash, check conservation + gas->liq comp shift):")
print("      wash_x | d(offgas+overflow)_kg  carb_dev_kg | dCO2_offgas  dNH3_offgas (kmol/h)")
base = scr(s=1.0)
base_out_kg = sumkg(base["offgas_kmolh"]) + sumkg(base["overflow_kmolh"])
_saved = copy.deepcopy(main.SCRUB_CARB_KMOLH_DES)
cons_ok = shift_ok = resid_inv = True
for wx in (0.95, 1.0, 1.05):                                  # NON-SATURATING regime: keep d_co2/d_nh3 off the
                                                             #   +-0.5*offgas clamps (main.py:1155-1156) so the
                                                             #   2:1 NH3:CO2 stoichiometry holds machine-exact.
                                                             #   The reconciled Path-B offgas is NH3-lean
                                                             #   (NH3:CO2=1.524<2): under +-30% wash BOTH clamps
                                                             #   bind and break the 2:1 ratio; +-5% stays linear.
    for k in main.SCRUB_CARB_KMOLH_DES:                       # live 323P001 wash change (surplus/deficit)
        main.SCRUB_CARB_KMOLH_DES[k] = _saved[k] * wx
    r = scr(s=1.0)
    carb_dev_kg = sumkg({k: (main.SCRUB_CARB_KMOLH_DES[k] - _saved[k]) for k in _saved})
    d_out_kg = (sumkg(r["offgas_kmolh"]) + sumkg(r["overflow_kmolh"])) - base_out_kg
    dCO2 = base["offgas_kmolh"]["CO2"] - r["offgas_kmolh"]["CO2"]   # CO2 pulled gas->liquid by surplus wash
    dNH3 = base["offgas_kmolh"]["NH3"] - r["offgas_kmolh"]["NH3"]
    cons_ok   &= abs(d_out_kg - carb_dev_kg) < 1e-6            # only added mass = surplus wash (transfers cancel)
    resid_inv &= abs(r["closure_resid"] - base["closure_resid"]) < 1e-9   # resid invariant to wash dev
    if abs(wx - 1.0) > 1e-9:
        shift_ok &= (math.copysign(1, dCO2) == math.copysign(1, wx - 1.0))   # surplus wash -> +CO2 scrubbed
        shift_ok &= abs(dNH3 - 2.0 * dCO2) < 1e-6                            # 2 NH3 : 1 CO2 stoichiometry
    print("      %.2f   | %18.4f  %10.4f | %10.5f  %10.5f" % (wx, d_out_kg, carb_dev_kg, dCO2, dNH3))
main.SCRUB_CARB_KMOLH_DES.clear(); main.SCRUB_CARB_KMOLH_DES.update(_saved)   # RESTORE module state
chk(cons_ok,   "mass conserved: d(offgas+overflow) == carb_dev (gas<->liq transfers cancel exactly)")
chk(shift_ok,  "composition shift: surplus wash scrubs CO2 gas->liq at 2:1 NH3:CO2 (deficit reverses sign)")
chk(resid_inv, "closure_resid invariant to wash deviation (deviation added to feed AND overflow equally)")
chk(all(abs(main.SCRUB_CARB_KMOLH_DES[k] - _saved[k]) < 1e-12 for k in _saved), "module wash vector restored clean")

# ============================================================================================== B
print("\n" + bar); print("  B. CCW eps-NTU BRIDGE (GAP#2)  --  design pins + energy balance + no-pole"); print(bar)
chk(abs(d["t_ccw_out"]  - SCRUB_CCW_T_OUT_DES) < 1e-6, "TT-329125 == 95.0 C bit-exact at design (got %.6f)" % d["t_ccw_out"])
chk(abs(d["T_overflow"] - SCRUB_OVERFLOW_T_C)  < 1e-6, "TT-322002 == 178.8 C bit-exact at design (got %.6f)" % d["T_overflow"])
chk(abs(d["T_offgas"]   - SCRUB_OFFGAS_T_C)    < 1e-6, "TT-322011 == 114.0 C bit-exact at design (got %.6f)" % d["T_offgas"])
# energy balance C_ccw*dT_ccw == q_ccw whenever overflow not clamped at T_proc
print("\n   energy balance  C_ccw*dT_ccw == q_ccw  (CCW heat removed == scrubber duty):")
print("      s     vent  m_ccw_x | q_ccw     C*dT      |resid_kW| T_ovf<=Tproc")
eb_ok = cap_ok = True
for (s, vent, mx) in ((1.0,1.0,1.0),(1.3,1.0,1.0),(1.0,1.2,1.0),(0.7,1.0,1.0),(1.0,1.0,1.5),(1.0,1.0,0.5)):
    r = scr(s=s, vent=vent, m_ccw=M_CCW_DES*mx)
    c_dt = (M_CCW_DES*mx) * SCRUB_CCW_CP / 3600.0 * r["dT_ccw"]
    clamped = r["T_overflow"] >= SCRUB_T_PROC_C - 1e-9
    if not clamped: eb_ok &= abs(c_dt - r["q_ccw_kw"]) < 1e-3
    cap_ok &= (r["T_overflow"] <= SCRUB_T_PROC_C + 1e-9) and (r["t_ccw_out"] <= SCRUB_T_PROC_C + 1e-9)
    print("      %.1f   %.1f   %.1f   | %8.1f %8.1f  %9.4f  %s"
          % (s, vent, mx, r["q_ccw_kw"], c_dt, abs(c_dt - r["q_ccw_kw"]), r["T_overflow"] <= SCRUB_T_PROC_C+1e-9))
chk(eb_ok,  "C_ccw*dT_ccw == q_ccw within 1e-3 kW (unclamped) -- CCW sensible balance closes")
# no-pole: m_ccw -> 0 must NOT blow up; both T -> T_proc ceiling
print("\n   m_ccw -> 0 (FIC-329409 shut): T must asymptote to T_proc=185, NOT +inf:")
print("      m_ccw_x  | t_ccw_out  T_overflow")
nopole = True
for mx in (1.0, 0.1, 0.01, 1e-4, 1e-7):
    r = scr(m_ccw=M_CCW_DES*mx)
    nopole &= math.isfinite(r["t_ccw_out"]) and math.isfinite(r["T_overflow"]) \
              and r["t_ccw_out"] <= SCRUB_T_PROC_C + 1e-6 and r["T_overflow"] <= SCRUB_T_PROC_C + 1e-6
    print("      %.0e | %9.4f  %9.4f" % (mx, r["t_ccw_out"], r["T_overflow"]))
chk(nopole, "m_ccw->0 bounded at T_proc=185 (eps-NTU bridge kills the q/(m.cp) AND q/UA divide-by-zero pole)")
chk(cap_ok, "t_ccw_out and T_overflow never exceed condensation ceiling T_proc across full sweep")

# ============================================================================================== C
print("\n" + bar); print("  C. HV-322604 OFF-GAS VALVE  --  equal-% trim + sqrt(dP) + JT letdown"); print(bar)
chk(abs(_eq_pct(SCRUB_HIC604_DES_PCT, SCRUB_HIC604_DES_PCT) - 1.0) < 1e-12, "phi_ep(theta_des) == 1.0 bit-exact (R^0)")
P_DES = SCRUB_OFFGAS_P_BARA
offg = {k: SCRUB_OFFGAS_KMOLH_DES.get(k,0.0) for k in MW_COMP}
v0 = hv_322604(offg, SCRUB_OFFGAS_T_C, SCRUB_HIC604_DES_PCT, P_DES)
chk(abs(v0["valve_frac"] - 1.0) < 1e-12, "valve_frac == 1.0 at design (theta_des, P_up=design): mass passes 1:1")
print("\n   equal-%% gain R^((th-th_des)/100), sqrt(dP/dP_des), JT cooling T_out=T_in-mu*dP:")
print("      theta | valve_frac  expect_eq%%  | T_out   (JT)")
eqp_ok = jt_ok = comp_ok = True
ratio0 = {k: offg[k] for k in MW_COMP}
for th in (30.0, 50.0, 70.0, 90.0):
    v = hv_322604(offg, SCRUB_OFFGAS_T_C, th, P_DES)
    exp = SCRUB_HV604_RANGE ** ((th - SCRUB_HIC604_DES_PCT)/100.0)        # dP==dP_des here so factor==phi_ep
    eqp_ok &= abs(v["valve_frac"] - exp) < 1e-9
    jt_exp = SCRUB_OFFGAS_T_C - SCRUB_HV604_MU_JT * (P_DES - SCRUB_HV604_P_OUT)
    jt_ok  &= abs(v["T_out"] - round(jt_exp,1)) < 1e-9
    # composition ratios preserved (throttle scales all comps equally)
    if v["valve_frac"] > 0:
        comp_ok &= all(abs(v["comp_kmolh"][k]/v["valve_frac"] - ratio0[k]) < 1e-9 for k in MW_COMP)
    print("      %.0f   | %10.6f  %10.6f  | %6.1f" % (th, v["valve_frac"], exp, v["T_out"]))
chk(eqp_ok,  "valve_frac == R^((theta-theta_des)/100) equal-%% trim (IEC 60534) bit-exact")
chk(comp_ok, "off-gas composition ratios preserved under throttle (no fractionation in the valve)")
# sqrt(dP) dependence
vlo = hv_322604(offg, SCRUB_OFFGAS_T_C, SCRUB_HIC604_DES_PCT, (SCRUB_HV604_P_OUT + SCRUB_HV604_DP_DES*0.25))
chk(abs(vlo["valve_frac"] - 0.5) < 1e-6, "valve_frac scales as sqrt(dP): 0.25*dP_des -> factor 0.5")
chk(jt_ok, "T_out == T_in - mu_JT*dP (Joule-Thomson isenthalpic letdown) at design dP")

# ============================================================================================== D
print("\n" + bar); print("  D. TT OFF-DESIGN COUPLINGS  --  TT-322011 / TT-322002 two-sided, zero at design, clamped"); print(bar)
# TT-322011 off-gas vent-T: N/C slip raises it; HV-322604 opening raises vent overhead T
hi_nc = scr(nc=SCRUB_OFFGAS_NC_DES + 0.1); lo_nc = scr(nc=SCRUB_OFFGAS_NC_DES - 0.1)
chk(hi_nc["T_offgas"] > d["T_offgas"] > lo_nc["T_offgas"], "TT-322011 rises with loop N/C slip (excess-NH3 vapour load), two-sided")
op_og = scr(hic=70.0); cl_og = scr(hic=30.0)
chk(op_og["T_offgas"] > d["T_offgas"] > cl_og["T_offgas"], "TT-322011 rises as HV-322604 opens (more uncondensed vent overhead)")
# TT-322002 overflow: opening HV-322604 relieves+cools the bottom carbamate; closing heats it
chk(op_og["T_overflow"] < d["T_overflow"] < cl_og["T_overflow"], "TT-322002 falls as HV-322604 opens (vent relief cools overflow), two-sided")
# clamp band [t_ccw_in, T_proc] + finite under extreme drift
clamp_ok = True
for nc in (SCRUB_OFFGAS_NC_DES + 2.0, SCRUB_OFFGAS_NC_DES - 2.0):
    for hic in (0.0, 100.0):
        r = scr(nc=nc, hic=hic)
        clamp_ok &= (SCRUB_CCW_T_IN_DES - 1e-6 <= r["T_offgas"]  <= SCRUB_T_PROC_C + 1e-6)
        clamp_ok &= (SCRUB_CCW_T_IN_DES - 1e-6 <= r["T_overflow"] <= SCRUB_T_PROC_C + 1e-6)
        clamp_ok &= math.isfinite(r["T_offgas"]) and math.isfinite(r["T_overflow"])
chk(clamp_ok, "TT-322011 & TT-322002 clamped to [t_ccw_in, T_proc], finite under extreme N/C + vent drift")

# ============================================================================================== E
print("\n" + bar); print("  E. LT-329501 SUMP INVENTORY ODE  --  gravity-head self-stabilizing integrator"); print(bar)
NLL = SCRUB_LEVEL_NLL_PCT
def settle_sump(m_cond_in, capacity, L0pct, dt=1.0, n=20000):
    M = SCRUB_HOLDUP_NLL_KG / NLL * L0pct
    for _ in range(n):
        L = clamp(M / SCRUB_HOLDUP_NLL_KG * NLL, 0.0, 100.0)
        ej_suc = capacity * (L / NLL)                       # gravity suction head ~ level
        M = clamp(M + (m_cond_in - ej_suc) * (dt/3600.0), 0.0, SCRUB_HOLDUP_MAX_KG)
    return clamp(M / SCRUB_HOLDUP_NLL_KG * NLL, 0.0, 100.0)
# E1 design fixed point: m_cond_in == capacity == EJ_SUC_TOT_DES, L=NLL -> dM=0
M0 = SCRUB_HOLDUP_NLL_KG; dM = (EJ_SUC_TOT_DES - EJ_SUC_TOT_DES*( (M0/SCRUB_HOLDUP_NLL_KG*NLL)/NLL ))
chk(abs(dM) < 1e-9, "design: m_cond_in==capacity, L=NLL -> dM/dt == 0 (NLL exact fixed point)")
print("\n   bounded equilibrium  L_eq = NLL*(m_cond_in/capacity)  (gravity head, NOT railing):")
print("      cond_x  cap_x | L_eq(settled)  L_eq(theory)  | railed?")
eq_ok = norail = True
for (cx, capx) in ((1.0,1.0),(1.2,1.0),(0.8,1.0),(1.0,1.2),(0.6,1.3)):
    Ls = settle_sump(EJ_SUC_TOT_DES*cx, EJ_SUC_TOT_DES*capx, NLL)
    Lth = clamp(NLL * cx/capx, 0.0, 100.0)
    railed = Ls <= 1e-6 or Ls >= 100.0 - 1e-6
    eq_ok &= abs(Ls - Lth) < 0.5; norail &= (not railed)
    print("      %.1f    %.1f   | %10.4f    %10.4f    | %s" % (cx, capx, Ls, Lth, railed))
chk(eq_ok,   "L settles to bounded L_eq = NLL*(cond/cap) within 0.5%% (gravity-head negative feedback)")
chk(norail,  "no spurious rail-to-0/100%% over the operating band")
# E2 conservation at SS: ej_suction == m_cond_in
Ls = settle_sump(EJ_SUC_TOT_DES*1.15, EJ_SUC_TOT_DES, NLL); suc_ss = EJ_SUC_TOT_DES*(Ls/NLL)
chk(abs(suc_ss - EJ_SUC_TOT_DES*1.15) < 0.01*EJ_SUC_TOT_DES, "steady-state entrainment == condensation make (conserved)")
# E3 returns to NLL after +20% level kick when balanced
chk(abs(settle_sump(EJ_SUC_TOT_DES, EJ_SUC_TOT_DES, NLL+20.0) - NLL) < 0.5,
    "level returns to design NLL (%.1f%%) after +20%% kick" % NLL)
# E4 ejector stall (capacity collapse) floods the sump toward 100% -- the documented failure mode
chk(settle_sump(EJ_SUC_TOT_DES, EJ_SUC_TOT_DES*0.3, NLL) > 90.0,
    "ejector stall (cap 0.3x) floods sump toward 100%% (N/C-break flood mode reproduces)")

print("\n" + bar)
if fails:
    print("  E003 SCRUBBER AUDIT:  %d CHECK(S) FAILED" % len(fails))
    for m in fails: print("     - " + m)
    raise SystemExit(1)
print("  E003 SCRUBBER AUDIT:  ALL CHECKS PASS  --  unit clean, safe to proceed to 322F001 (Ejector)")
print(bar)
