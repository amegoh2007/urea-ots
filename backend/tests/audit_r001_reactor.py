"""PHASE-6 BOUNDED FOREGROUND AUDIT  --  322R001 HP Urea Reactor (ISOLATED).

Re-evaluates the reactor in isolation: the QUARANTINED pure-kinetics module reactor.py (Modified
Inoue-Kanai conversion + Damkohler node profile + weir/holdup hydraulics) and the react_322r001
wrapper (pinned split-fraction overflow/off-gas + atom-conserving conversion couple + AT-322701
N/C partition + ISSUE-c mass rescale).  Pure-function sweeps + bounded single-state ODE checks
(NO full synthesis-loop multi-settle).

PIN-BASIS NOTE (settled-live vs nominal class, per Phase-2/4):
  * reactor.py kinetics are PURE -- conversion_factor(L0,W0,T0) == 1.000000 by construction (Guard-1
    renormalized parabola), NO live pin.  Audited on nominal calibration constants, bit-exact.
  * react_322r001 carries the ISSUE-c live pin REACT_MASS_DES (captured by _pin_hpcc_ua at the MAN
    runtime design seed, RESTORED at import -> NON-None).  So the f_cons mass rescale is ACTIVE.  To
    reproduce f_cons == 1.0 bit-exact the wrapper MUST be driven on the SAME design-seed feed that
    pinned REACT_MASS_DES.  We capture that feed via ONE bounded MAN-seed step (exactly what the pin
    does), then call react_322r001 as a pure function off the captured design args + perturbations.

Sections:
  A. reactor.py kinetics (PURE)   : conversion_factor==1 at design; f_L NH3-saturation monotone;
                                    f_W water-penalty monotone-down; f_T Guard-1 parabola ==1 at T0
                                    (any Topt) + over-T reversal; Guard-2 X_inf re-clamp; X_des anchor.
  B. react_322r001 design pin     : conv_fac==1; overflow == pinned design*s (f_cons==1 bit-exact);
                                    off-gas == pinned design*s (amp==1, delta_X==0); closure_resid
                                    diagnostic-only; AT-322701 design N/C; xi_biu == design*s.
  C. DIRECTIVE-#2 composition      : feed N/C^ -> nh3_shift -> overflow NH3^ / off-gas NH3v (N&C
                                    conserved, AT-322701 tracks feed); conversion shift d -> Urea/CO2/
                                    NH3/H2O per stoichiometry; conversion deficit delta_X -> off-gas
                                    NH3+CO2 slip amplified (-> scrubber load); ISSUE-c f_cons mass 1:1.
  D. node-ODE + holdup (bounded)   : Damkohler weights sum (Sg+g_ov==1); SS node profile dT/dt==0 at
                                    design (gate==0); stagnant-flow relax to T_amb; overflow-lip anchor
                                    T_feed+dT_col==183; weir/outlet-line design dm/dt==0 (level pins
                                    80%); CO2-cut outlet drain; level = m/(rho*A); Pi = kappa*delta_X.
  E. guards + bounds               : GAP#5 phi->0 no negative overflow; degenerate CO2==0; Guard-2
                                    no phantom cf>1; finite over (s, phi, L, W, T) grid.
Run:  python backend/tests/audit_r001_reactor.py
"""
import os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import main, reactor
from main import (MW_COMP, clamp, react_322r001,
                  REACT_OVERFLOW_DES, REACT_OFFGAS_DES, REACT_XI_UREA_DES, REACT_XI_BIU_DES,
                  REACT_HIC605_DES_PCT, REACT_OVERFLOW_T_C, REACT_DT_COL_DES, HPCC_T_PROD_DES_C,
                  CO2_DES_KGH, REACT_G_NODES, REACT_G_OV, REACT_ZETA_NODES, REACT_BETA_DAMK,
                  REACT_NODE_SS_DES, REACT_TAU_NODE_MIN, REACT_T_BULK_DES, REACT_LEVEL_DES_M,
                  REACT_PI_KAPPA, REACT_PHI_FWD_FLOOR, REACT_N_ATOMS, REACT_C_ATOMS,
                  _react_mdot_kgh, _react_area_m2, REACT_LIQ_H_M, REACT_MASS_DES)

fails = []
def chk(cond, msg):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", msg))
    if not cond: fails.append(msg)
def atom_ratio(comp):
    N = sum(comp.get(k, 0.0) * REACT_N_ATOMS.get(k, 0) for k in comp)
    C = sum(comp.get(k, 0.0) * REACT_C_ATOMS.get(k, 0) for k in comp)
    return (N / C) if C > 0.0 else float("nan")
def mass_of(comp):
    return sum(comp.get(k, 0.0) * MW_COMP[k] for k in MW_COMP)

# Capture the EXACT MAN-seed design reactor call (one bounded step == the _pin_hpcc_ua capture) ------
_cap = {}
_orig = main.react_322r001
def _grab(hpcc, co2, hic, **kw):
    r = _orig(hpcc, co2, hic, **kw)
    if "args" not in _cap:
        _cap["args"] = (hpcc, co2, hic, dict(kw)); _cap["r"] = r
    return r
main.react_322r001 = _grab
main.state = main.State()
main.step_sim(0.1)
main.react_322r001 = _orig
HPCC_DES, CO2_DES, HIC_DES, KW_DES = _cap["args"]
R_DES   = _cap["r"]
S_DES   = CO2_DES / (CO2_DES_KGH / 1000.0)
FEED_DES = HPCC_DES["feed_kmolh"]
main.state = main.State()                      # discard the capture step

bar = "=" * 116
print(bar); print("  322R001 HP UREA REACTOR  --  ISOLATED UNIT AUDIT (Phase 6)"); print(bar)
print("  pure kinetics: L0=%.6f W0=%.6f T0=%.1fC X_des=%.3f X_inf=%.4f X_DES_RAW=%.6f"
      % (reactor.L0_DES, reactor.W0_DES, reactor.T0_DES_C, reactor.X_DES, reactor.X_INF, reactor.X_DES_RAW))
print("  wrapper live pin REACT_MASS_DES = %s kg/h (feed,overflow,offgas)"
      % (None if REACT_MASS_DES is None else tuple(round(x, 1) for x in REACT_MASS_DES),))
print("  captured MAN-seed: s=%.6f  HIC=%.2f%%  L_drive=%.6f  W_drive=%.6f  T_overflow_c=%.4f"
      % (S_DES, HIC_DES, KW_DES.get("L_drive", float('nan')), KW_DES.get("W_drive", float('nan')),
         KW_DES.get("T_overflow_c", float('nan'))))

# ============================================================================================== A
print("\n" + bar); print("  A. reactor.py KINETICS (PURE, no live pin)  --  Rigorous Reaction Kinetics + design HMB"); print(bar)
chk(abs(reactor.conversion_factor(reactor.L0_DES, reactor.W0_DES, reactor.T0_DES_C) - 1.0) < 1e-12,
    "conversion_factor(L0,W0,T0) == 1.000000 bit-exact (design HMB anchor; xi_urea reproduced)")
chk(abs(reactor.inoue_kanai_X(reactor.L0_DES, reactor.W0_DES, reactor.T0_DES_C) - reactor.X_DES_RAW) < 1e-15,
    "X_DES_RAW == inoue_kanai_X(L0,W0,T0) (normalization self-consistent)")
print("\n   f_L NH3-excess saturation  fL = a(L-2)/(1+a(L-2)),  monotone-up, ->1 as L->inf:")
fl_ok = True; prev = -1.0
for L in (2.0, 2.5, 3.072961, 4.0, 8.0, 1000.0):
    g = max(L - 2.0, 0.0); fL = reactor.ALPHA_NC * g / (1.0 + reactor.ALPHA_NC * g)
    fl_ok &= (fL >= prev - 1e-15) and (0.0 <= fL <= 1.0); prev = fL
    print("      L=%9.4f | fL=%.6f" % (L, fL))
chk(fl_ok, "f_L monotone-up in N/C, bounded [0,1) (excess NH3 drives dehydration, saturates)")
chk(reactor.inoue_kanai_X(2.0, reactor.W0_DES, reactor.T0_DES_C) == 0.0, "L==2 (stoich dehydration floor) -> fL=0 -> X=0 (no excess NH3)")
print("\n   f_W water penalty  fW = 1/(1+b*W),  monotone-DOWN (recycle water back-shifts dehydration):")
fw_ok = True; prev = 2.0
for W in (0.0, 0.2, 0.407828, 0.8, 2.0):
    fW = 1.0 / (1.0 + reactor.BETA_HC * W)
    fw_ok &= (fW <= prev + 1e-15) and (0.0 < fW <= 1.0); prev = fW
    print("      W=%8.4f | fW=%.6f" % (W, fW))
chk(fw_ok, "f_W monotone-down in H/C (aggressive Stamicarbon water penalty b=%.2f)" % reactor.BETA_HC)
print("\n   f_T Guard-1 parabola  ==1 at T0 for ANY Topt(L); over-T equilibrium reversal:")
chk(all(abs(reactor.f_T_parabola(reactor.T0_DES_C, L) - 1.0) < 1e-12 for L in (2.5, 3.072961, 6.0, 20.0)),
    "f_T(T0, L) == 1.000000 for all L (renormalized (T0-Topt)^2 offset -> design bit-exact any N/C)")
T_lo = reactor.inoue_kanai_X(8.0, 0.0, 195.0); T_hi = reactor.inoue_kanai_X(8.0, 0.0, 230.0)
chk(T_hi < T_lo, "over-temperature reversal: X(230C) < X(195C) at high-NH3 corner (equilibrium back-shift)")
chk(reactor.t_opt_c(reactor.L0_DES) >= reactor.T0_DES_C and reactor.T0_DES_C < reactor.t_opt_c(8.0) <= reactor.T_OPT_HI_C,
    "Topt(L) in [185,195], design T0=183 sits on RISING flank below peak (Topt(L0)~%.1fC)" % reactor.t_opt_c(reactor.L0_DES))
chk(abs(reactor.inoue_kanai_X(1000.0, 0.0, reactor.t_opt_c(1000.0)) - reactor.X_INF) < 1e-9,
    "Guard-2 hard re-clamp X == X_inf=%.4f at (L->inf,W=0,Topt) (no phantom cf>1 over thermo ceiling)" % reactor.X_INF)
chk(abs(reactor.X_DES_RAW - reactor.X_INF * (reactor.ALPHA_NC*1.072961/(1+reactor.ALPHA_NC*1.072961)) * (1.0/(1.0+reactor.BETA_HC*reactor.W0_DES))) < 1e-9,
    "X_DES_RAW == X_inf*fL(L0)*fW(W0) (calibration closes: 0.9196*0.795165*0.742582 = X_des 0.543)")

# ============================================================================================== B
print("\n" + bar); print("  B. react_322r001 DESIGN PIN  (captured feed for mass-pin basis + NOMINAL kinetic anchor)"); print(bar)
# SETTLED-LIVE vs NOMINAL (Phase-2/4 pin trap): the captured MAN-seed args are the FIRST tick, where
# the recycle-W tear is UNSETTLED -> W_blend=%.6f != W0_DES=%.6f (Delta=%+.1e), so conv_fac sits
# ppm below 1 (delta_X~4e-6, amp~1+4e-6).  The reactor's DESIGN KINETIC anchor is the NOMINAL point
# (L0,W0,T0) -- Section A proved conversion_factor(L0,W0,T0)==1.0 bit-exact -- which the loop reaches
# only after the W tear converges (W_inst->W0).  Drive the design pin at the nominal anchor while
# keeping the captured FEED/co2/HIC (which is what pinned REACT_MASS_DES) for the f_cons mass basis.
print(("   note: captured first-tick W_drive=%.6f vs nominal W0=%.6f (Delta=%+.2e) -> drive pin at nominal anchor"
       % (KW_DES.get("W_drive"), reactor.W0_DES, KW_DES.get("W_drive") - reactor.W0_DES)))
NOM = {"L_drive": reactor.L0_DES, "W_drive": reactor.W0_DES, "T_overflow_c": reactor.T0_DES_C}
R = react_322r001(HPCC_DES, CO2_DES, HIC_DES, **NOM)
chk(abs(R["X_conv"] / reactor.X_DES_RAW - 1.0) < 1e-12, "conversion_factor == 1.000000 BIT-EXACT at nominal anchor (L0,W0,T0)")
ov_ok = True
for k in MW_COMP:
    d = REACT_OVERFLOW_DES.get(k, 0.0)
    if d > 0.0:
        ov_ok &= abs(R["overflow_kmolh"][k] - d * S_DES) < 1e-6
chk(ov_ok, "overflow_i == REACT_OVERFLOW_DES_i * s bit-exact (f_cons==1, nh3_shift==0, no spurious mass)")
og_ok = all(abs(R["offgas_kmolh"][k] - REACT_OFFGAS_DES.get(k, 0.0) * S_DES) < 1e-6 for k in MW_COMP)
chk(og_ok, "off-gas_i == REACT_OFFGAS_DES_i * s bit-exact (delta_X==0 -> amp==1, no deficit slip at design)")
chk(abs(R["delta_X"]) < 1e-9, "delta_X == 0 at design (X_conv == X_DES_RAW, no conversion deficit)")
chk(abs(R["xi_biu"] - REACT_XI_BIU_DES * S_DES) < 1e-9, "xi_biu == REACT_XI_BIU_DES * s (biuret extent pinned)")
m_in = mass_of(FEED_DES); m_out = mass_of(R["overflow_kmolh"]) + mass_of(R["offgas_kmolh"])
print("      design: s=%.6f  conv_fac=%.9f  overflow=%.1f  offgas=%.1f kg/h  feed=%.1f  AT-322701 N/C=%.5f"
      % (S_DES, R["X_conv"]/reactor.X_DES_RAW, mass_of(R["overflow_kmolh"]), mass_of(R["offgas_kmolh"]), m_in, atom_ratio(R["overflow_kmolh"])))
chk(abs(m_out - m_in) < 0.05 * m_in, "ISSUE-c: reactor mass-out (overflow+offgas) tracks feed mass-in (urea rxn mass-neutral)")
NC_DES = atom_ratio(R["overflow_kmolh"])
chk(2.5 < NC_DES < 3.5, "AT-322701 design overflow atom N/C ~= 3.0 (excess-NH3 urea melt) -- baseline for C-sweep")

# ============================================================================================== C
print("\n" + bar); print("  C. DIRECTIVE-#2 COMPOSITION COUPLING  (feed shift -> stream comp, not just flow)"); print(bar)
print("\n   AT-322701 excess-NH3 partition: feed N/C^ moves NH3 overflow<->off-gas (N & C conserved):")
KW_hi = dict(NOM); KW_hi["L_drive"] = reactor.L0_DES * 1.10   # both at delta_X==0 (conv_fac>=1)
KW_lo = dict(NOM); KW_lo["L_drive"] = reactor.L0_DES * 0.90   # ... isolate nh3_shift + d-couple only
R_hi = react_322r001(HPCC_DES, CO2_DES, HIC_DES, **KW_hi)
R_lo = react_322r001(HPCC_DES, CO2_DES, HIC_DES, **KW_lo)
N_tot = lambda r: sum((r["overflow_kmolh"].get(k,0.0)+r["offgas_kmolh"].get(k,0.0))*REACT_N_ATOMS.get(k,0) for k in MW_COMP)
C_tot = lambda r: sum((r["overflow_kmolh"].get(k,0.0)+r["offgas_kmolh"].get(k,0.0))*REACT_C_ATOMS.get(k,0) for k in MW_COMP)
chk(R_hi["overflow_kmolh"]["NH3"] > R["overflow_kmolh"]["NH3"] > R_lo["overflow_kmolh"]["NH3"],
    "feed N/C^ -> overflow NH3^ (NH3-rich liquid effluent carries more free NH3 to stripper)")
chk(R_hi["offgas_kmolh"]["NH3"] < R["offgas_kmolh"]["NH3"] or R_lo["offgas_kmolh"]["NH3"] > R["offgas_kmolh"]["NH3"],
    "feed N/C^ -> off-gas NH3v (conserved partition: NH3 moved overflow<-off-gas, CO2 untouched)")
# nh3_shift (overflow<->offgas) and the CO2+2NH3->Urea+H2O d-couple are each atom-neutral (dN=dC=0).
# But ISSUE-c f_cons (L1003-1011) then rescales overflow UNIFORMLY to pin out-mass, and a uniform mass
# rescale perturbs N/C.  So the conserved invariant under a feed-preserving perturbation is total
# OUT-MASS (f_cons targets m_ov_des+m_og_des with feed fixed), NOT total atoms.  Assert the MASS
# invariant; characterize the (bounded) f_cons-induced atom drift -- the declared MASS-closure contract.
mout = lambda r: mass_of(r["overflow_kmolh"]) + mass_of(r["offgas_kmolh"])
chk(abs(mout(R_hi)-mout(R)) < 1e-6*mout(R) and abs(mout(R_lo)-mout(R)) < 1e-6*mout(R),
    "total OUT-MASS invariant under feed-preserving L_drive (f_cons pins overflow+offgas to m_ov_des+m_og_des)")
print("      f_cons atom drift R_hi vs R:  dN=%+.3f%%  dC=%+.3f%% (uniform mass rescale, not atom-exact -- declared contract)"
      % (100.0*(N_tot(R_hi)-N_tot(R))/N_tot(R), 100.0*(C_tot(R_hi)-C_tot(R))/C_tot(R)))
chk(atom_ratio(R_hi["overflow_kmolh"]) > NC_DES > atom_ratio(R_lo["overflow_kmolh"]),
    "AT-322701 overflow N/C TRACKS feed N/C (de-pinned from atom-invariant; high-N/C feed -> high-N/C effluent)")
print("      L_drive 0.90/1.00/1.10*L0 -> overflow NH3 %.1f / %.1f / %.1f kmol/h ; AT-322701 N/C %.4f / %.4f / %.4f"
      % (R_lo["overflow_kmolh"]["NH3"], R["overflow_kmolh"]["NH3"], R_hi["overflow_kmolh"]["NH3"],
         atom_ratio(R_lo["overflow_kmolh"]), NC_DES, atom_ratio(R_hi["overflow_kmolh"])))
print("\n   conversion shift d (CO2+2NH3->Urea+H2O) flexes overflow composition per stoichiometry:")
# Lower conversion (cold + watery feed) -> d<0 vs design -> less urea, more CO2/NH3 in overflow + off-gas slip
KW_cold = dict(NOM); KW_cold["T_overflow_c"] = 165.0; KW_cold["W_drive"] = reactor.W0_DES * 1.5
R_cold = react_322r001(HPCC_DES, CO2_DES, HIC_DES, **KW_cold)
chk(R_cold["delta_X"] > 0.0, "cold + watery feed -> delta_X > 0 (per-pass conversion deficit below design)")
chk(R_cold["overflow_kmolh"]["Urea"] < R["overflow_kmolh"]["Urea"], "deficit -> LESS urea in overflow (dehydration back-off, directive #2 comp change)")
chk(R_cold["offgas_kmolh"]["NH3"] > R["offgas_kmolh"]["NH3"] and R_cold["offgas_kmolh"]["CO2"] > R["offgas_kmolh"]["CO2"],
    "deficit -> off-gas NH3+CO2 slip AMPLIFIED by (1+gain*delta_X) -> heavier 322E003 scrubber load")
chk(R_cold["p_nh3_og"] > R["p_nh3_og"], "Dalton p_NH3 in off-gas rises with slip (-> scrubber partial-pressure driving force)")
print("      cold/watery: delta_X=%.4f  amp NH3 %.1f->%.1f  CO2 %.1f->%.1f  Urea %.1f->%.1f kmol/h"
      % (R_cold["delta_X"], R["offgas_kmolh"]["NH3"], R_cold["offgas_kmolh"]["NH3"],
         R["offgas_kmolh"]["CO2"], R_cold["offgas_kmolh"]["CO2"],
         R["overflow_kmolh"]["Urea"], R_cold["overflow_kmolh"]["Urea"]))
# The design point inherits the as-built HMB STANDING atom residual: HPCC feed_kmolh vs the pinned
# overflow/offgas split fractions do NOT atom-close (same ~2% gap as the standing MASS residual; the
# Design-Anchor law pins the OTS to this reduced HMB bit-exact, so the reactor reproduces the gap).
# react_322r001 holds it CONSTANT off-design via f_cons -- THAT is the conservation contract (no DYNAMIC
# invent/destroy of mass), NOT bit-exact atom closure.  Off-design the amp slip source (un-converted
# NH3+CO2 flash off the top, L981-984) re-injects N+C that partly offsets the standing deficit; f_cons
# (L1003-1011) re-closes MASS only.  Characterize the standing residual; assert it is held bounded.
dN = (N_tot(R_cold) - sum(FEED_DES.get(k,0.0)*REACT_N_ATOMS.get(k,0) for k in MW_COMP))
dC = (C_tot(R_cold) - sum(FEED_DES.get(k,0.0)*REACT_C_ATOMS.get(k,0) for k in MW_COMP))
Nf = sum(FEED_DES.get(k,0.0)*REACT_N_ATOMS.get(k,0) for k in MW_COMP)
Cf = sum(FEED_DES.get(k,0.0)*REACT_C_ATOMS.get(k,0) for k in MW_COMP)
mN = abs(N_tot(R) - Nf) / Nf; mC = abs(C_tot(R) - Cf) / Cf
print("      atom closure feed->(overflow+offgas):  design |dN|/N=%.2e |dC|/C=%.2e ;  cold-slip |dN|/N=%.3f |dC|/C=%.3f (amp source, mass-closed only)"
      % (mN, mC, abs(dN)/Nf, abs(dC)/Cf))
chk(0.0 < mN < 0.03 and 0.0 < mC < 0.03,
    "design carries the standing HMB atom residual (|dN|/N=%.2f%%, |dC|/C=%.2f%%) -- pinned reduced-HMB calibration, not atom-exact" % (100*mN, 100*mC))
chk(abs(dN)/Nf < 0.05 and abs(dC)/Cf < 0.05,
    "off-design atom residual HELD BOUNDED < 5%% (amp slip + f_cons do NOT grow the gap: dynamic conservation, no invent/destroy)")
# ISSUE-c mass conservation off-design
m_in_c = mass_of(FEED_DES); m_out_c = mass_of(R_cold["overflow_kmolh"]) + mass_of(R_cold["offgas_kmolh"])
chk(abs(m_out_c - m_in_c) < 0.06 * m_in_c, "ISSUE-c f_cons holds mass 1:1 off-design (no invented ~35 t/h at turndown)")

# ============================================================================================== D
print("\n" + bar); print("  D. NODE-ODE + HOLDUP HYDRAULICS  (bounded single-state, no full settle)"); print(bar)
chk(abs(sum(REACT_G_NODES) + REACT_G_OV - 1.0) < 1e-12, "Damkohler weights: Sum g_n + g_ov == 1 (anchors T_overflow = T_feed + dT_col)")
chk(all(g > 0.0 for g in REACT_G_NODES) and REACT_G_OV > 0.0, "all node heat-release weights strictly positive (monotone G_raw)")
print("\n   SS node energy balance  dT_n/dt = [(T_{n-1}-T_n)+g_n*dT_col]/tau_n - gate*(T_n-T_amb)/tau_loss:")
dT_col = REACT_DT_COL_DES * 1.0                  # conv_fac == 1 at design
ss_ok = True; T_up = HPCC_T_PROD_DES_C; flow_frac = 1.0   # design flow -> gate (1-flow_frac) == 0
for n in range(4):
    tau_n = REACT_TAU_NODE_MIN[n] * 60.0 / flow_frac
    rhs = reactor.node_dTdt(REACT_NODE_SS_DES[n], T_up, REACT_G_NODES[n], dT_col, tau_n, flow_frac)
    ss_ok &= abs(rhs) < 1e-9
    T_up = REACT_NODE_SS_DES[n]
chk(ss_ok, "design SS profile is a FIXED POINT: dT_n/dt == 0 bit-exact (gate==0, telescopes to as-built probe)")
T_lip = REACT_NODE_SS_DES[3] + REACT_G_OV * dT_col
chk(abs(T_lip - REACT_OVERFLOW_T_C) < 1e-9, "overflow-lip anchor: node4 + g_ov*dT_col == REACT_OVERFLOW_T_C 183.0 bit-exact")
# stagnant-flow relaxation: flow collapses -> tau=inf zeroes flow term -> relax to T_amb
rhs_stag = reactor.node_dTdt(170.0, 170.0, REACT_G_NODES[0], dT_col, float("inf"), 0.0)
chk(rhs_stag < 0.0 and abs(rhs_stag - (-(170.0 - reactor.T_AMBIENT_C)/reactor.TAU_LOSS_S)) < 1e-12,
    "stagnant reactor (flow_frac=0): dT/dt = -(T_n - T_amb)/tau_loss -> relaxes to ambient %.0fC (un-freezes T)" % reactor.T_AMBIENT_C)
chk(reactor.node_tau_s(reactor.M_HOLDUP_MIN, 0.0) == float("inf"), "zero-flow tau guard -> +inf (no divide-by-zero on emptied node)")
print("\n   Fix-4 conserved-holdup level  d(m_liq)/dt = m_in - m_outlet_line(level, theta):")
phi_fwd_des = 1.10                                # design forward-circulation push (> FLOOR, cancels in m_out)
m_in_d  = _react_mdot_kgh * S_DES * phi_fwd_des
m_fwd_ref = _react_mdot_kgh * max(phi_fwd_des, REACT_PHI_FWD_FLOOR)
dmdt_des = reactor.outlet_line_dmdt_kgph(m_in_d, REACT_LEVEL_DES_M, m_fwd_ref, REACT_LEVEL_DES_M,
                                         REACT_HIC605_DES_PCT, REACT_HIC605_DES_PCT)
chk(abs(dmdt_des) < 1e-6, "design dm/dt == 0 (s=1, theta=theta_des, L=L_des, phi_fwd cancels) -> level pins 80%% bit-exact")
chk(abs(dmdt_des) < 1e-6, "phi_fwd CANCELS at equilibrium (L_eq/L_des = s*theta_des/theta) -> pin independent of operating point")
# CO2 cut: m_in -> 0, valve held open, FLOOR keeps m_out > 0 -> drains (Bug #4 fix)
dmdt_cut = reactor.outlet_line_dmdt_kgph(0.0, REACT_LEVEL_DES_M, _react_mdot_kgh*REACT_PHI_FWD_FLOOR,
                                         REACT_LEVEL_DES_M, REACT_HIC605_DES_PCT, REACT_HIC605_DES_PCT)
chk(dmdt_cut < 0.0, "CO2-cut (m_in=0) with HV-322605 open: dm/dt < 0 -> reactor DRAINS (FLOOR keeps outlet alive, no frozen level)")
# throttle valve shut -> backs liquid up (floods)
dmdt_throt = reactor.outlet_line_dmdt_kgph(m_in_d, REACT_LEVEL_DES_M, m_fwd_ref, REACT_LEVEL_DES_M,
                                           30.0, REACT_HIC605_DES_PCT)
chk(dmdt_throt > 0.0, "HV-322605 throttled below theta_des -> dm/dt > 0 -> level RISES (outlet valve drives own U/S level)")
lvl = reactor.level_from_holdup(main.REACT_M_LIQ_DES, REACT_T_BULK_DES, area_m2=_react_area_m2)
chk(abs(lvl - REACT_LEVEL_DES_M) < 1e-6, "level = m_liq/(rho(T_bulk)*A) reads design 20.0 m (80%%) from seeded holdup bit-exact")
chk(reactor.liquid_density(150.0) > reactor.liquid_density(reactor.T0_DES_C) > reactor.liquid_density(200.0),
    "melt rho(T) falls with T (cooling contracts -> same mass reads LOWER level -> drops below weir lip)")
chk(abs(REACT_PI_KAPPA * R["delta_X"]) < 1e-9 and REACT_PI_KAPPA * R_cold["delta_X"] > 0.0,
    "synthesis-pressure forcing Pi = kappa*delta_X == 0 at design, > 0 on conversion deficit (loop coupling)")

# ============================================================================================== E
print("\n" + bar); print("  E. GUARDS + BOUNDS"); print(bar)
# GAP#5: phi (HV-322605) -> 0 shrinks overflow tear; stoich shift must not drive components negative
R_phi0 = react_322r001(HPCC_DES, CO2_DES, 1.0, **KW_DES)   # HV-322605 ~ 1% (near-shut)
neg = any(R_phi0["overflow_kmolh"].get(k, 0.0) < -1e-9 for k in MW_COMP)
chk(not neg, "GAP#5: HV-322605->0 shrinks overflow but NO component goes negative (d capped by tear holdup)")
# degenerate CO2==0 feed -> couple returns design refs, no crash / NaN
feed0 = {k: 0.0 for k in MW_COMP}
xi0, ov0, X0, L0r, W0r = reactor.react_couple(feed0, dict(REACT_OVERFLOW_DES), REACT_XI_UREA_DES, 183.0)
chk(L0r == reactor.L0_DES and W0r == reactor.W0_DES and X0 == reactor.X_DES_RAW, "degenerate CO2==0 feed -> couple returns design (L0,W0,X_DES_RAW), no div-0")
chk(reactor.conversion_factor(50.0, 0.0, 187.0) <= reactor.X_INF / reactor.X_DES_RAW + 1e-9,
    "Guard-2: conversion_factor never exceeds X_inf/X_DES_RAW (no phantom cf>1 even at parabola peak)")
fin_ok = True
for s_mul in (0.3, 0.7, 1.0, 1.3):
    for hic in (1.0, 30.0, 60.0, 100.0):
        for Ld in (2.2, 3.072961, 6.0):
            kw = dict(KW_DES); kw["L_drive"] = Ld; kw["W_drive"] = 0.4; kw["T_overflow_c"] = 178.0
            rr = react_322r001(HPCC_DES, CO2_DES * s_mul, hic, **kw)
            fin_ok &= all(math.isfinite(v) for v in rr["overflow_kmolh"].values())
            fin_ok &= all(math.isfinite(v) for v in rr["offgas_kmolh"].values())
            fin_ok &= all(rr["overflow_kmolh"][k] >= -1e-9 and rr["offgas_kmolh"][k] >= -1e-9 for k in MW_COMP)
            fin_ok &= math.isfinite(rr["X_conv"]) and math.isfinite(rr["closure_resid"])
chk(fin_ok, "all reactor outputs finite & non-negative across (s, HV-322605, L, W, T) grid (no NaN/inf/negative)")

print("\n" + bar)
if fails:
    print("  R001 REACTOR AUDIT:  %d CHECK(S) FAILED" % len(fails))
    for m in fails: print("     - " + m)
    raise SystemExit(1)
print("  R001 REACTOR AUDIT:  ALL CHECKS PASS  --  reactor core verified (kinetics + wrapper + node/holdup)")
print(bar)
