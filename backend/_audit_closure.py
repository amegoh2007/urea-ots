# Closure Audit (Path B, Option A): strict READ-ONLY numerical mass-balance audit of the
# 322E003 scrubber + 322E001 stripper nodes and the HPCC return-leg W_inst(0) fixed point,
# using ONLY the pinned in-code design vectors as the authoritative HMB.  No state mutation,
# no step_sim, no writes to main.py.  All design streams are module constants (or design-arg
# function calls) evaluated at import.
import main as M

MW = M.MW_COMP
COMPS = list(MW.keys())

# atom counts per component (for atom-closure checks)
N_AT = {"NH3":1,"Urea":2,"Biuret":3,"N2":2}
C_AT = {"CO2":1,"Urea":1,"Biuret":2,"CH4":1}
H_AT = {"NH3":3,"Urea":4,"Biuret":5,"H2O":2,"CH4":4,"H2":2}
O_AT = {"CO2":2,"H2O":1,"Urea":1,"Biuret":2,"O2":2}

def atoms(v):
    return (sum(v.get(k,0.0)*N_AT.get(k,0) for k in COMPS),
            sum(v.get(k,0.0)*C_AT.get(k,0) for k in COMPS),
            sum(v.get(k,0.0)*H_AT.get(k,0) for k in COMPS),
            sum(v.get(k,0.0)*O_AT.get(k,0) for k in COMPS))

def mass(v):
    return sum(v.get(k,0.0)*MW[k] for k in COMPS)

def tot(v):
    return sum(v.get(k,0.0) for k in COMPS)

def row(label, g):
    s = "  %-9s" % label
    for k in COMPS:
        s += " %11.4f" % g.get(k,0.0)
    return s

hdr = "  %-9s" % "comp" + "".join(" %11s" % k for k in COMPS)

W0 = M.reactor.W0_DES; L0 = M.reactor.L0_DES

print("="*150)
print("CLOSURE AUDIT  (design HMB = pinned in-code vectors; READ-ONLY)")
print("="*150)
print("  W0_DES = %.8f   L0_DES = %.8f" % (W0, L0))

# ---------------------------------------------------------------------------
# Design stream vectors (kmol/h)
# ---------------------------------------------------------------------------
react_offgas = {k: M.REACT_OFFGAS_DES.get(k,0.0) for k in COMPS}        # 322R001 -> 322E003 (gas in)
scrub_wash   = {k: M.SCRUB_CARB_KMOLH_DES.get(k,0.0) for k in COMPS}     # 323P001 weak carbamate wash
scrub_offgas = {k: M.SCRUB_OFFGAS_KMOLH_DES.get(k,0.0) for k in COMPS}   # 322E003 -> 322C001 (vent out)
scrub_over   = {k: M.SCRUB_OVERFLOW_KMOLH_DES.get(k,0.0) for k in COMPS} # 322E003 overflow -> ejector (= EJ_SUCTION)
react_over   = {k: M.REACT_OVERFLOW_DES.get(k,0.0) for k in COMPS}       # 322R001 overflow stream 207
strip_top    = {k: M._STRIP_TOP_DES.get(k,0.0) for k in COMPS}           # 322E001 top gas -> HPCC

# CO2 strip gas into stripper (design)
co2_strip = {k: M.CO2_FEED_MOLFRAC.get(k,0.0) * M.CO2_DES_KMOLH for k in COMPS}

# full design stripper result (top + bot) at design args
strip_des = M.stripper_322e001(M.CO2_DES_KGH/1000.0, M.STRIP_STEAM_T_DES_C, M.STRIP_P_DES_BARA)
strip_topf = {k: strip_des["top_kmolh"].get(k,0.0) for k in COMPS}
strip_botf = {k: strip_des["bot_kmolh"].get(k,0.0) for k in COMPS}
strip_feed = {k: strip_des["feed_kmolh"].get(k,0.0) for k in COMPS}
xi_hyd = strip_des["xi_hyd"]; xi_biu = strip_des["xi_biu"]

# ejector design discharge (motive NH3 + suction).  Suction = design overflow (EJ_SUCTION) exactly.
ej_disch = {k: scrub_over.get(k,0.0) for k in COMPS}
ej_disch["NH3"] += M.EJ_MOTIVE_NH3_DES / MW["NH3"]

# HPCC design feed = stripper top + ejector discharge
hpcc_feed = {k: strip_top.get(k,0.0) + ej_disch.get(k,0.0) for k in COMPS}

# ===========================================================================
# AUDIT 1 — 322E003 SCRUBBER component balance:  offgas_in + wash = overflow + offgas_out
# ===========================================================================
print("\n" + "-"*150)
print("AUDIT 1 — 322E003 SCRUBBER  :  (react_offgas + wash)  -  (overflow + scrub_offgas)")
print("-"*150)
print(hdr)
s_in  = {k: react_offgas[k] + scrub_wash[k] for k in COMPS}
s_out = {k: scrub_over[k] + scrub_offgas[k] for k in COMPS}
s_gap = {k: s_in[k] - s_out[k] for k in COMPS}
print(row("IN(og+wsh)", s_in))
print(row("OUT(ov+og)", s_out))
print(row("GAP", s_gap))
print("  IN  totals : mol=%.4f  mass=%.4f kg/h   atoms(N,C,H,O)=%s" % (tot(s_in), mass(s_in), tuple(round(a,4) for a in atoms(s_in))))
print("  OUT totals : mol=%.4f  mass=%.4f kg/h   atoms(N,C,H,O)=%s" % (tot(s_out), mass(s_out), tuple(round(a,4) for a in atoms(s_out))))
aN,aC,aH,aO = atoms(s_in); bN,bC,bH,bO = atoms(s_out)
print("  GAP  totals: mol=%+.4f mass=%+.4f kg/h  atomgap(N,C,H,O)=(%+.4f,%+.4f,%+.4f,%+.4f)"
      % (tot(s_in)-tot(s_out), mass(s_in)-mass(s_out), aN-bN, aC-bC, aH-bH, aO-bO))

# ===========================================================================
# AUDIT 2 — 322E001 STRIPPER component + atom balance:  (overflow + CO2 strip) -> (top + bot)
#   internal reactions: hydrolysis xi_hyd, biuret xi_biu (atom-conserving) -> atoms must close.
# ===========================================================================
print("\n" + "-"*150)
print("AUDIT 2 — 322E001 STRIPPER  :  feed(207+CO2)  ->  top + bot   (xi_hyd=%.4f  xi_biu=%.4f)" % (xi_hyd, xi_biu))
print("-"*150)
print(hdr)
st_feed = {k: react_over[k] + co2_strip[k] for k in COMPS}
st_out  = {k: strip_topf[k] + strip_botf[k] for k in COMPS}
# expected reaction delta (hydrolysis: Urea+H2O->2NH3+CO2 ; biuret: 2Urea->Biuret+NH3)
st_rxn  = {k: 0.0 for k in COMPS}
st_rxn["Urea"]   -= (xi_hyd + 2.0*xi_biu)
st_rxn["Biuret"] += xi_biu
st_rxn["NH3"]    += (2.0*xi_hyd + xi_biu)
st_rxn["CO2"]    += xi_hyd
st_rxn["H2O"]    -= xi_hyd
st_gap  = {k: (st_feed[k] + st_rxn[k]) - st_out[k] for k in COMPS}
print(row("FEED", st_feed))
print(row("RXN_delta", st_rxn))
print(row("TOP+BOT", st_out))
print(row("GAP", st_gap))
print("  FEED      : mol=%.4f mass=%.4f   atoms(N,C,H,O)=%s" % (tot(st_feed), mass(st_feed), tuple(round(a,4) for a in atoms(st_feed))))
print("  TOP+BOT   : mol=%.4f mass=%.4f   atoms(N,C,H,O)=%s" % (tot(st_out), mass(st_out), tuple(round(a,4) for a in atoms(st_out))))
aN,aC,aH,aO = atoms(st_feed); bN,bC,bH,bO = atoms(st_out)
print("  ATOM CLOSURE (feed - out, must be ~0): (N,C,H,O)=(%+.6f,%+.6f,%+.6f,%+.6f)" % (aN-bN, aC-bC, aH-bH, aO-bO))
print("  MASS CLOSURE (feed - out, must be ~0): %+.6f kg/h" % (mass(st_feed)-mass(st_out)))

# ===========================================================================
# AUDIT 3 — HPCC RETURN-LEG W_inst(0) fixed-point check
#   W_inst = hpcc_feed[H2O]/hpcc_feed[CO2] ;  hpcc_feed = strip_top + ej_disch
# ===========================================================================
print("\n" + "-"*150)
print("AUDIT 3 — HPCC feed W_inst(0) FIXED-POINT  :  strip_top + ejector_discharge")
print("-"*150)
print(hdr)
print(row("strip_top", strip_top))
print(row("ej_disch", ej_disch))
print(row("hpcc_feed", hpcc_feed))
co2_fd = hpcc_feed["CO2"]; h2o_fd = hpcc_feed["H2O"]; nh3_fd = hpcc_feed["NH3"]
W_inst = h2o_fd / co2_fd
L_inst = nh3_fd / co2_fd
print("\n  hpcc_feed CO2 = %.6f   H2O = %.6f   NH3 = %.6f  (kmol/h)" % (co2_fd, h2o_fd, nh3_fd))
print("  W_inst(0) = H2O/CO2 = %.8f   W0_DES = %.8f   Delta = %+.3e" % (W_inst, W0, W_inst - W0))
print("  L_inst(0) = NH3/CO2 = %.8f   L0_DES = %.8f   Delta = %+.3e" % (L_inst, L0, L_inst - L0))

# ===========================================================================
# AUDIT 4 — REACTOR-NODE inventory balance (dM/dt source)
#   in = hpcc total product (= hpcc_feed, HPCC conserves) ; out = overflow + offgas
# ===========================================================================
print("\n" + "-"*150)
print("AUDIT 4 — 322R001 REACTOR node mass balance (dM/dt source):  hpcc_feed  -  (overflow + offgas)")
print("-"*150)
r_out = {k: react_over[k] + react_offgas[k] for k in COMPS}
r_gap = {k: hpcc_feed[k] - r_out[k] for k in COMPS}
print(hdr)
print(row("IN hpcc", hpcc_feed))
print(row("OUT ov+og", r_out))
print(row("GAP", r_gap))
aN,aC,aH,aO = atoms(hpcc_feed); bN,bC,bH,bO = atoms(r_out)
print("  IN  : mol=%.4f mass=%.4f   atoms(N,C,H,O)=%s" % (tot(hpcc_feed), mass(hpcc_feed), tuple(round(a,4) for a in atoms(hpcc_feed))))
print("  OUT : mol=%.4f mass=%.4f   atoms(N,C,H,O)=%s" % (tot(r_out), mass(r_out), tuple(round(a,4) for a in atoms(r_out))))
print("  MASS dM/dt source (in - out) = %+.4f kg/h   atomgap(N,C,H,O)=(%+.4f,%+.4f,%+.4f,%+.4f)"
      % (mass(hpcc_feed)-mass(r_out), aN-bN, aC-bC, aH-bH, aO-bO))
print("="*150)
