# READ-ONLY reconciliation probe (Path B tear closure). Computes mathematically-closed
# SCRUB_OVERFLOW / SCRUB_OFFGAS design vectors under the directive's strict constraints.
# No state mutation, no step_sim, no writes to main.py.
import main as M

MW = M.MW_COMP
COMPS = list(MW.keys())
INERTS = ["CH4", "H2", "N2", "O2"]
HEAVY  = ["Urea", "Biuret"]
NCH    = ["NH3", "CO2", "H2O"]

W0 = M.reactor.W0_DES
L0 = M.reactor.L0_DES

# atom counts
N_AT = {"NH3":1,"Urea":2,"Biuret":3,"N2":2}
C_AT = {"CO2":1,"Urea":1,"Biuret":2,"CH4":1}
H_AT = {"NH3":3,"Urea":4,"Biuret":5,"H2O":2,"CH4":4,"H2":2}
O_AT = {"CO2":2,"H2O":1,"Urea":1,"Biuret":2,"O2":2}
def atoms(v):
    return (sum(v.get(k,0.0)*N_AT.get(k,0) for k in COMPS),
            sum(v.get(k,0.0)*C_AT.get(k,0) for k in COMPS),
            sum(v.get(k,0.0)*H_AT.get(k,0) for k in COMPS),
            sum(v.get(k,0.0)*O_AT.get(k,0) for k in COMPS))
def mass(v): return sum(v.get(k,0.0)*MW[k] for k in COMPS)
def tot(v):  return sum(v.get(k,0.0) for k in COMPS)

# ---- immutable inputs (design, kmol/h) ----
react_offgas = {k: M.REACT_OFFGAS_DES.get(k,0.0) for k in COMPS}   # 322R001 -> scrubber gas
wash         = {k: M.SCRUB_CARB_KMOLH_DES.get(k,0.0) for k in COMPS}  # 323P001 wash
strip_top    = {k: M._STRIP_TOP_DES.get(k,0.0) for k in COMPS}     # 322E001 top -> HPCC
motive_NH3   = M.EJ_MOTIVE_NH3_DES / MW["NH3"]                     # pure NH3 motive (kmol/h)

IN = {k: react_offgas[k] + wash[k] for k in COMPS}                 # total scrubber inlet

print("="*108)
print("RECONCILIATION INPUTS (immutable, kmol/h)")
print("="*108)
print("  W0_DES=%.8f  L0_DES=%.8f  motive_NH3=%.6f kmol/h" % (W0, L0, motive_NH3))
print("  strip_top : CO2=%.6f  H2O=%.6f  NH3=%.6f" % (strip_top["CO2"], strip_top["H2O"], strip_top["NH3"]))
print("  IN(og+wash): " + "  ".join("%s=%.4f" % (k, IN[k]) for k in COMPS if IN[k] != 0.0))

# ---- reconciliation as a function of the free DOF ov_CO2 ----
def recon(ov_CO2):
    H = strip_top["CO2"] + ov_CO2          # hpcc_feed CO2 (ejector adds no CO2)
    ov_H2O = W0 * H - strip_top["H2O"]     # forces W_inst = W0
    ov_NH3 = L0 * H - strip_top["NH3"] - motive_NH3  # forces L_inst = L0
    overflow = {k: 0.0 for k in COMPS}
    overflow["CO2"], overflow["H2O"], overflow["NH3"] = ov_CO2, ov_H2O, ov_NH3
    for k in HEAVY:  overflow[k] = IN[k]   # 100% heavies -> liquid
    offgas = {k: 0.0 for k in COMPS}
    for k in INERTS: offgas[k] = IN[k]     # 100% inerts -> vent
    for k in NCH:    offgas[k] = IN[k] - overflow[k]   # balance
    return overflow, offgas, H, ov_H2O, ov_NH3

# ---- feasible band for ov_CO2 (all overflow>=0 AND all offgas>=0) ----
lo_bounds = []  # ov_CO2 >= ...
hi_bounds = []  # ov_CO2 <= ...
# ov_H2O>=0 -> W0*H >= strip_top.H2O
lo_bounds.append(("ov_H2O>=0", strip_top["H2O"]/W0 - strip_top["CO2"]))
# ov_NH3>=0 -> L0*H >= strip_top.NH3+motive
lo_bounds.append(("ov_NH3>=0", (strip_top["NH3"]+motive_NH3)/L0 - strip_top["CO2"]))
lo_bounds.append(("ov_CO2>=0", 0.0))
# vent_CO2>=0 -> ov_CO2 <= IN.CO2
hi_bounds.append(("vent_CO2>=0", IN["CO2"]))
# vent_H2O>=0 -> ov_H2O <= IN.H2O -> W0*H <= strip_top.H2O+IN.H2O
hi_bounds.append(("vent_H2O>=0", (strip_top["H2O"]+IN["H2O"])/W0 - strip_top["CO2"]))
# vent_NH3>=0 -> ov_NH3 <= IN.NH3 -> L0*H <= strip_top.NH3+motive+IN.NH3
hi_bounds.append(("vent_NH3>=0", (strip_top["NH3"]+motive_NH3+IN["NH3"])/L0 - strip_top["CO2"]))

lo = max(b for _, b in lo_bounds); lo_name = max(lo_bounds, key=lambda x: x[1])[0]
hi = min(b for _, b in hi_bounds); hi_name = min(hi_bounds, key=lambda x: x[1])[0]
print("\n" + "="*108)
print("FREE DOF = ov_CO2  (W0/L0 give 2 eqns for 3 overflow unknowns -> rank-1 deficient)")
print("="*108)
for n,b in lo_bounds: print("  lower: %-12s ov_CO2 >= %12.6f" % (n,b))
for n,b in hi_bounds: print("  upper: %-12s ov_CO2 <= %12.6f" % (n,b))
print("  --> FEASIBLE BAND ov_CO2 in [%.6f , %.6f]  (binding: lo=%s hi=%s)" % (lo, lo_name, hi, hi_name) if False else
      "  --> FEASIBLE BAND ov_CO2 in [%.6f , %.6f]  (binding lo=%s, hi=%s)" % (lo, hi, lo_name, hi_name))

# ---- recommended anchor = feasible max (max CO2 recovery; driest vent) ----
anchor = hi
overflow, offgas, H, ov_H2O, ov_NH3 = recon(anchor)

hdr = "  %-9s" + "".join(" %12s" % k for k in COMPS)
def row(label, g): return "  %-9s" % label + "".join(" %12.5f" % g.get(k,0.0) for k in COMPS)
print("\n" + "="*108)
print("RECONCILED DESIGN VECTORS  @ anchor ov_CO2 = %.6f (feasible MAX, vent driest)" % anchor)
print("="*108)
print("  %-9s" % "comp" + "".join(" %12s" % k for k in COMPS))
print(row("OVERFLOW", overflow))
print(row("OFFGAS",   offgas))

# ---- verification ----
print("\n" + "-"*108)
print("VERIFICATION")
print("-"*108)
# scrubber component + atom closure (IN - overflow - offgas must be ~0 each comp)
gap = {k: IN[k] - overflow[k] - offgas[k] for k in COMPS}
print("  scrubber comp closure max|IN-ov-og| = %.3e" % max(abs(v) for v in gap.values()))
aN,aC,aH,aO = atoms(IN); bN,bC,bH,bO = atoms({k:overflow[k]+offgas[k] for k in COMPS})
print("  scrubber atom closure (N,C,H,O) = (%+.3e,%+.3e,%+.3e,%+.3e)" % (aN-bN,aC-bC,aH-bH,aO-bO))
print("  scrubber mass closure IN-out = %+.6f kg/h" % (mass(IN)-mass({k:overflow[k]+offgas[k] for k in COMPS})))
# inert conservation
print("  inert->vent 100%%: " + " ".join("%s og=%.4f IN=%.4f" % (k,offgas[k],IN[k]) for k in INERTS))
# heavy conservation
print("  heavy->liq 100%%:  " + " ".join("%s ov=%.4f IN=%.4f" % (k,overflow[k],IN[k]) for k in HEAVY))
# W_inst / L_inst at HPCC return leg
ej_disch = {k: overflow[k] for k in COMPS}; ej_disch["NH3"] += motive_NH3
hpcc = {k: strip_top[k] + ej_disch[k] for k in COMPS}
W_inst = hpcc["H2O"]/hpcc["CO2"]; L_inst = hpcc["NH3"]/hpcc["CO2"]
print("  W_inst=%.10f  W0=%.10f  dW=%+.3e" % (W_inst, W0, W_inst-W0))
print("  L_inst=%.10f  L0=%.10f  dL=%+.3e" % (L_inst, L0, L_inst-L0))
# forced vent reactant loss (NH3+CO2 lost to LP vent)
print("  forced vent loss: NH3=%.4f CO2=%.4f H2O=%.4f kmol/h (=%.1f kg/h reactant NH3+CO2)"
      % (offgas["NH3"], offgas["CO2"], offgas["H2O"],
         offgas["NH3"]*MW["NH3"]+offgas["CO2"]*MW["CO2"]))

# ---- also report the OLD frozen vectors for diff context ----
print("\n" + "-"*108)
print("OLD (broken) frozen vectors for comparison")
print("-"*108)
old_og = {k: M.SCRUB_OFFGAS_KMOLH_DES.get(k,0.0) for k in COMPS}
old_ov = {k: M.SCRUB_OVERFLOW_KMOLH_DES.get(k,0.0) for k in COMPS}
print(row("old OG", old_og))
print(row("old OV", old_ov))
oN,oC,oH,oO = atoms(IN); pN,pC,pH,pO = atoms({k:old_og[k]+old_ov[k] for k in COMPS})
print("  OLD scrubber atom gap (N,C,H,O) = (%+.4f,%+.4f,%+.4f,%+.4f)" % (oN-pN,oC-pC,oH-pH,oO-pO))
print("  OLD inert creation: " + " ".join("%s og=%.4f vs IN=%.4f (x%.2f)" % (k,old_og[k],IN[k], old_og[k]/IN[k] if IN[k] else 0.0) for k in INERTS))

# ---- emit copy-paste-ready python dict literals for the diff ----
print("\n" + "="*108)
print("DICT LITERALS FOR main.py DIFF (anchor ov_CO2 = %.6f)" % anchor)
print("="*108)
def lit(name, g):
    items = ", ".join('"%s": %.8f' % (k, g[k]) for k in COMPS if abs(g.get(k,0.0))>1e-12)
    print("%s = {%s}" % (name, items))
lit("SCRUB_OVERFLOW_KMOLH_DES", overflow)
lit("SCRUB_OFFGAS_KMOLH_DES", offgas)

# ============================================================================
# EJECTOR SUCTION = single source of truth for overflow (line 751 mirrors it,
# line 162 EJ_CARB_FRAC drives the LIVE ejector->HPCC discharge comp).  Recompute
# EJ_SUCTION_KGH from reconciled overflow so the LIVE tear actually closes.
# ============================================================================
ej_suction_kgh = {k: overflow[k]*MW[k] for k in COMPS}
suc_tot = sum(ej_suction_kgh.values())
new_des_total = M.EJ_MOTIVE_NH3_DES + suc_tot
new_mu  = suc_tot / M.EJ_MOTIVE_NH3_DES
print("\n" + "="*108)
print("RECONCILED EJECTOR SUCTION SPEC (EJ_MOTIVE immutable; suction = overflow result)")
print("="*108)
print("  old EJ_SUC_TOT_DES=%.4f  EJ_DES_TOTAL=%.1f  EJ_MU=%.6f" % (M.EJ_SUC_TOT_DES, M.EJ_DES_TOTAL, M.EJ_MU))
print("  new EJ_SUC_TOT_DES=%.4f  EJ_DES_TOTAL=%.1f  EJ_MU=%.6f" % (suc_tot, new_des_total, new_mu))
items = ", ".join('"%s": %.6f' % (k, ej_suction_kgh[k]) for k in COMPS if abs(ej_suction_kgh.get(k,0.0))>1e-9)
print("EJ_SUCTION_KGH = {%s}" % items)

# ---- LIVE-PATH verification: rebuild EJ_CARB_FRAC, run design-point ejector discharge, HPCC W/L ----
ej_carb_frac = {k: ej_suction_kgh[k]/suc_tot for k in COMPS}
m_suc = suc_tot                                            # design: phi_m=phi_sp=frac=1
suction_live = {k: m_suc*ej_carb_frac[k] for k in COMPS}   # kg/h, ejector line 368
disch_kgh = {k: (M.EJ_MOTIVE_NH3_DES if k=="NH3" else 0.0)+suction_live[k] for k in COMPS}
ej_disch_kmol = {k: disch_kgh[k]/MW[k] for k in COMPS}
hpcc2 = {k: strip_top[k] + ej_disch_kmol[k] for k in COMPS}
print("\n  LIVE design-point ejector->HPCC (m_suc=EJ_SUC_TOT_DES, phi=1):")
print("    W_inst=%.10f  W0=%.10f  dW=%+.3e" % (hpcc2["H2O"]/hpcc2["CO2"], W0, hpcc2["H2O"]/hpcc2["CO2"]-W0))
print("    L_inst=%.10f  L0=%.10f  dL=%+.3e" % (hpcc2["NH3"]/hpcc2["CO2"], L0, hpcc2["NH3"]/hpcc2["CO2"]-L0))
# ---- sump dM/dt at design: cond_in = Σ overflow*MW ; entrain = m_suc ----
cond_in = sum(overflow[k]*MW[k] for k in COMPS)
print("    sump dM/dt = cond_in - entrain = %.4f - %.4f = %+.3e kg/h" % (cond_in, m_suc, cond_in-m_suc))
