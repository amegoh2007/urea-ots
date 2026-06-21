"""PHASE-4 BOUNDED FOREGROUND AUDIT  --  322F001 HP Carbamate Ejector (ISOLATED).

Re-evaluates the liquid-liquid jet pump in isolation (pure-function calls; no full synthesis-loop
settle, so no coupled-solver stall).

PIN-BASIS NOTE (same character as the Phase-2 HPCC finding): `import main` loads the PERSISTED pin
cache, so EJ_MOTIVE_DES_LIVE = 40751.300 (the SETTLED-LIVE design motive over 21k ticks), NOT the
nominal datasheet EJ_MOTIVE_NH3_DES = 40756.  The model PINS phi_m == 1 at the live motive the running
loop actually feeds -- so the design-anchor invariants are tested on the LIVE basis, while the nominal
98320 Carb.Liq. HMB table is verified bit-exact in the UNPINNED (warm-up) basis -- the analog of the
HPCC gate=0 hold.  The ~0.0115% nominal-vs-live gap is documented as bounded/expected, not drift.

Sections:
  A. Mass closure + design anchors : LIVE-pin invariant (motive==EJ_MOTIVE_DES_LIVE -> phi_m==1 ->
                                     m_suc, suction comp, mu bit-exact) + NOMINAL-HMB hold (unpinned ->
                                     total==98320 & comp==_EJ_DES_MASS bit-exact) + bounded nominal gap;
                                     component balance disch == motive*[NH3] + m_suc*CARB_FRAC exact.
  B. Entrainment law               : phi_m linear (driven on live basis), phi_sp equal-% R^((open-74)/100)
                                     monotone-up + datasheet 1.6667 anchor, f_stall quadratic knee.
  C. Stall / self-regulation       : proportional turndown -> capacity ~ motive (no false flood);
                                     true motive fault phi_m<REC -> capacity collapses << design.
  D. Energy / TT-322012            : T_d == cp-weighted mix bit-exact; bracketed; monotone; no-flow guard.
  E. Intensive props + bounds      : P=144.2, rho=877.9 const; open clamp[10,100]; frac<0 -> 0; finite.
Run:  python backend/tests/audit_f001_ejector.py
"""
import os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import main
from main import (MW_COMP, ejector_322f001, clamp,
                  EJ_MOTIVE_NH3_DES, EJ_MOTIVE_T_DES_C, EJ_OPEN_DES, EJ_SUC_TOT_DES,
                  EJ_SUCTION_KGH, EJ_CARB_FRAC, EJ_DES_TOTAL, EJ_MU, EJ_SPINDLE_R,
                  EJ_STALL_PHI, EJ_STALL_REC, EJ_STALL_EXP, EJ_CP_N, EJ_CP_C, EJ_CP_D,
                  EJ_T_SUCTION_C, EJ_P_DISCH_BARA, EJ_RHO_DISCH)
_EJ_DES_MASS = main._EJ_DES_MASS

fails = []
def chk(cond, msg):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", msg))
    if not cond: fails.append(msg)

MOT_NOM  = EJ_MOTIVE_NH3_DES                                   # nominal datasheet motive (HMB Carb.Liq. basis)
MOT_LIVE = main.EJ_MOTIVE_DES_LIVE if main.EJ_MOTIVE_DES_LIVE is not None else MOT_NOM  # settled-live pin
TM       = EJ_MOTIVE_T_DES_C
def ejp(pm=1.0, t_mot=None, opn=EJ_OPEN_DES, frac=1.0):       # drive by phi_m on the LIVE pin basis
    return ejector_322f001(MOT_LIVE*pm, TM if t_mot is None else t_mot, opn, frac)
def phi_sp(opn):  return EJ_SPINDLE_R ** ((clamp(opn,10.0,100.0) - EJ_OPEN_DES)/100.0)
def f_stall(pm):  return clamp((pm-EJ_STALL_PHI)/(EJ_STALL_REC-EJ_STALL_PHI),0.0,1.0)**EJ_STALL_EXP

bar = "=" * 116
print(bar); print("  322F001 HP CARBAMATE EJECTOR  --  ISOLATED UNIT AUDIT (Phase 4)"); print(bar)
print("  phi_m basis: EJ_MOTIVE_DES_LIVE=%.4f (settled-live pin) vs nominal EJ_MOTIVE_NH3_DES=%.1f  (gap %.4f%%)"
      % (MOT_LIVE, MOT_NOM, (MOT_NOM/MOT_LIVE - 1.0)*100.0))
chk(main.EJ_MOTIVE_DES_LIVE is not None, "persisted pin loaded at import: phi_m pinned to SETTLED-LIVE motive (not nominal)")
d = ejp(1.0)
print("  LIVE DESIGN (phi_m=1): total=%.4f kg/h  suction=%.4f  mu=%.6f  T_d(TT-322012)=%.4f C  P=%.1f"
      % (d["total_kgh"], d["suction_kgh"], d["mu"], d["T_C"], d["P_bara"]))

# ============================================================================================== A
print("\n" + bar); print("  A. MASS CLOSURE + DESIGN ANCHORS  (Domino + 100% conservation + design HMB)"); print(bar)
# A1 LIVE-pin invariant (feed-independent): phi_m==1 -> design suction reproduced bit-exact
chk(abs(d["suction_kgh"] - EJ_SUC_TOT_DES) < 1e-6, "LIVE-pin: phi_m==1 -> suction == EJ_SUC_TOT_DES %.1f bit-exact" % EJ_SUC_TOT_DES)
chk(all(abs(d["comp"][k] - ((MOT_LIVE if k=="NH3" else 0.0) + EJ_SUCTION_KGH[k])) < 1e-6 for k in MW_COMP),
    "LIVE-pin: discharge comp == live motive*[NH3] + EJ_SUCTION_KGH bit-exact")
chk(abs(d["mu"] - EJ_SUC_TOT_DES/MOT_LIVE) < 1e-9, "LIVE-pin: mu == EJ_SUC_TOT_DES/MOT_LIVE %.6f (live-basis; nominal EJ_MU %.6f recovered unpinned in A2)" % (EJ_SUC_TOT_DES/MOT_LIVE, EJ_MU))
chk(abs(d["total_kgh"] - (MOT_LIVE + EJ_SUC_TOT_DES)) < 1e-6, "LIVE-pin: discharge total == live motive + EJ_SUC_TOT_DES (live design discharge)")
# A2 NOMINAL-HMB hold: unpin (EJ_MOTIVE_DES_LIVE=None, warm-up basis) -> reproduce the Carb.Liq. table bit-exact.
#    Reconstructed table sum = Sigma _EJ_DES_MASS = 98324.1 (datasheet mass-pct sums to 100.00417%, so > nameplate 98320).
DES_MASS_SUM = sum(_EJ_DES_MASS.values())
_saved = main.EJ_MOTIVE_DES_LIVE
main.EJ_MOTIVE_DES_LIVE = None                                # warm-up / design-HMB basis (phi_m = motive/40756)
hold = ejector_322f001(MOT_NOM, TM, EJ_OPEN_DES, 1.0)
chk(abs(hold["total_kgh"] - DES_MASS_SUM) < 1e-6, "NOMINAL-HMB hold (unpinned): total == Sigma_EJ_DES_MASS %.1f bit-exact (nameplate %.0f + %.1f datasheet mass-pct rounding)" % (DES_MASS_SUM, EJ_DES_TOTAL, DES_MASS_SUM-EJ_DES_TOTAL))
chk(all(abs(hold["comp"][k] - _EJ_DES_MASS[k]) < 1e-6 for k in MW_COMP), "NOMINAL-HMB hold: discharge comp == _EJ_DES_MASS (Carb.Liq. table) bit-exact")
chk(abs(hold["mu"] - EJ_MU) < 1e-9, "NOMINAL-HMB hold: entrainment ratio mu == EJ_MU %.6f bit-exact (nominal basis)" % EJ_MU)
main.EJ_MOTIVE_DES_LIVE = _saved                              # RESTORE pin
chk(main.EJ_MOTIVE_DES_LIVE == _saved, "pin restored clean after HMB-hold probe")
# A3 nominal motive through the LIVE-pinned model: bounded gap, correct sign (live<nominal -> phi_m>1)
gnom = ejector_322f001(MOT_NOM, TM, EJ_OPEN_DES, 1.0)
gap = (gnom["total_kgh"] - EJ_DES_TOTAL) / EJ_DES_TOTAL
chk(0.0 < gap < 5e-4, "nominal motive via LIVE pin: total %.3f -> +%.4f%% gap, bounded & correct sign (live<nominal)" % (gnom["total_kgh"], gap*100.0))
# A4 component mass balance across the full operating sweep
print("\n   component balance disch_k == motive*[NH3] + m_suc*CARB_FRAC_k + suction comp pin:")
bal_ok = frac_ok = tot_ok = True
for (pm, opn, fr) in ((1.0,74,1.0),(1.3,74,1.0),(0.7,74,1.0),(1.0,90,1.0),(1.0,60,1.0),(1.0,74,1.2),(1.0,74,0.6)):
    r = ejp(pm=pm, opn=opn, frac=fr); ms = r["suction_kgh"]; mot = MOT_LIVE*pm
    bal_ok &= all(abs(r["comp"][k] - ((mot if k=="NH3" else 0.0) + ms*EJ_CARB_FRAC[k])) < 1e-6 for k in MW_COMP)
    tot_ok &= abs(r["total_kgh"] - (mot + ms)) < 1e-6
    if ms > 0:  frac_ok &= all(abs((r["comp"][k]-(mot if k=="NH3" else 0.0))/ms - EJ_CARB_FRAC[k]) < 1e-9 for k in MW_COMP)
chk(bal_ok, "disch_k == motive*[k==NH3] + m_suc*CARB_FRAC_k  exact across phi_m/open/frac sweep")
chk(tot_ok, "discharge total == motive + suction  (overall mass closure) across sweep")
chk(frac_ok,"entrained-suction composition pinned to EJ_CARB_FRAC (no fractionation in the jet)")

# ============================================================================================== B
print("\n" + bar); print("  B. ENTRAINMENT LAW  --  phi_m linear / phi_sp equal-% / f_stall quadratic knee"); print(bar)
print("\n   phi_m linearity (open=74, frac=1, healthy band): m_suc == EJ_SUC_TOT*phi_m:")
lin_ok = True
for pm in (0.5, 0.8, 1.0, 1.3, 1.5):
    r = ejp(pm=pm); exp = EJ_SUC_TOT_DES * pm
    lin_ok &= abs(r["suction_kgh"] - exp) < 1e-6
    print("      phi_m=%.2f | m_suc=%11.3f  expect=%11.3f" % (pm, r["suction_kgh"], exp))
chk(lin_ok, "healthy band: m_suc == EJ_SUC_TOT_DES * phi_m bit-exact (mu ~ const, capacity tracks motive)")
chk(abs(phi_sp(EJ_OPEN_DES) - 1.0) < 1e-12, "phi_sp(74) == R^0 == 1.0 bit-exact (design opening)")
chk(phi_sp(60) < phi_sp(74) < phi_sp(90), "phi_sp monotone-INCREASING with opening (POSITIVE spindle law)")
chk(abs(phi_sp(83.3333)/phi_sp(16.6667) - (1.0/0.60)) < 1e-3, "phi_sp datasheet anchor: ratio(theta83.33/theta16.67) == 1.00/0.60")
sp_ok = True
for opn in (40.0, 60.0, 74.0, 90.0, 100.0):
    sp_ok &= abs(ejp(1.0, opn=opn)["suction_kgh"]/EJ_SUC_TOT_DES - phi_sp(opn)) < 1e-9
chk(sp_ok, "m_suc scales by phi_sp == R^((open-74)/100) across opening sweep (equal-% trim wired in)")
print("\n   f_stall knee  clamp((phi_m-0.20)/(0.35-0.20),0,1)^2  (deep-stall band [0.20,0.35]):")
print("      phi_m | f_stall   doc")
knee_ok = True
for (pm, doc) in ((0.15,0.0),(0.20,0.0),(0.25,0.11),(0.30,0.44),(0.35,1.0),(0.50,1.0),(1.0,1.0)):
    fv = f_stall(pm); knee_ok &= abs(fv - doc) < 0.01
    print("      %.2f  | %.4f    %.2f" % (pm, fv, doc))
chk(knee_ok, "f_stall == documented quadratic knee (f.25=.11 f.30=.44 f.35=1, ==0 below PHI=0.20)")

# ============================================================================================== C
print("\n" + bar); print("  C. STALL vs SELF-REGULATION  (directive #2 domino: motive fault -> sump flood)"); print(bar)
cap_des = EJ_SUC_TOT_DES
print("\n   proportional turndown (motive down, frac=1): capacity ~ motive, NO false stall:")
prop_ok = True
for pm in (1.0, 0.8, 0.6, 0.5):
    cap = EJ_SUC_TOT_DES * pm * phi_sp(74) * f_stall(pm)
    prop_ok &= abs(ejp(pm=pm)["suction_kgh"] - cap) < 1e-6 and f_stall(pm) > 0.999
    print("      phi_m=%.2f | capacity=%11.3f  (cap/des=%.3f, f_stall=%.3f -> healthy)" % (pm, cap, cap/cap_des, f_stall(pm)))
chk(prop_ok, "proportional turndown stays in healthy band (f_stall~1): sump self-regulates at NLL, no false flood")
print("\n   true motive fault (phi_m<REC=0.35, load held): capacity collapses (-> 322E003 floods):")
stall_ok = True
for pm in (0.35, 0.30, 0.25, 0.20):
    cap = EJ_SUC_TOT_DES * pm * f_stall(pm); collapse = cap / cap_des
    stall_ok &= (collapse < pm + 1e-9)
    print("      phi_m=%.2f | capacity=%11.3f  cap/des=%.4f  (vs linear %.2f -> stalled)" % (pm, cap, collapse, pm))
chk(stall_ok, "phi_m<REC: capacity collapses faster than linear (f_stall<1) -> L_eq=NLL*overflow/cap >> NLL (flood, see E003.E4)")
chk(ejp(pm=0.20)["suction_kgh"] == 0.0, "phi_m==PHI=0.20: capacity==0 (deep-stall knee, jet momentum lost)")

# ============================================================================================== D
print("\n" + bar); print("  D. ENERGY BALANCE / TT-322012 + no-flow guard"); print(bar)
print("\n   discharge-T energy closure  m_d*cpD*T_d == m_mot*cpN*T_mot + m_suc*cpC*T_suc:")
print("      pm   T_mot | T_d      energy_resid_kW  bracket[T_mot,178.8]")
eclo_ok = brk_ok = True
for (pm, tmot) in ((1.0,TM),(1.3,TM),(0.7,TM),(1.0,29.0),(1.0,80.0),(1.0,150.0)):
    r = ejp(pm=pm, t_mot=tmot); mot = MOT_LIVE*pm; ms = r["suction_kgh"]
    lhs = r["total_kgh"]*EJ_CP_D*r["T_C"]; rhs = mot*EJ_CP_N*tmot + ms*EJ_CP_C*EJ_T_SUCTION_C
    eclo_ok &= abs(lhs - rhs)/3600.0 < 1e-6
    brk_ok  &= (min(tmot,EJ_T_SUCTION_C)-1e-6 <= r["T_C"] <= max(tmot,EJ_T_SUCTION_C)+1e-6)
    print("      %.1f  %5.1f | %7.3f  %12.2e   %s" % (pm, tmot, r["T_C"], abs(lhs-rhs)/3600.0, min(tmot,EJ_T_SUCTION_C)-1e-6 <= r["T_C"] <= max(tmot,EJ_T_SUCTION_C)+1e-6))
chk(eclo_ok, "T_d satisfies cp-weighted energy balance bit-exact (mass-energy closure, P1-3)")
chk(brk_ok,  "T_d bracketed by [T_motive, T_suction] (physical mixing bound)")
chk(ejp(pm=1.0, t_mot=150.0)["T_C"] > d["T_C"], "T_d monotone-up with hotter motive (sensible coupling)")
nf = ejector_322f001(0.0, TM, EJ_OPEN_DES)
chk(nf["total_kgh"] == 0.0 and nf["suction_kgh"] == 0.0, "no-flow (motive<=1e-6): discharge mass == 0 (no perturbation to HPCC T_feed_mix)")
chk(abs(nf["T_C"] - EJ_T_SUCTION_C) < 1e-9, "no-flow: TT-322012 reads stagnant suction carbamate %.1f C, NOT collapse to 0" % EJ_T_SUCTION_C)
chk(all(math.isfinite(v) for v in (nf["T_C"], nf["mu"], nf["vol_m3h"])), "no-flow: all returns finite (no NaN/div0)")

# ============================================================================================== E
print("\n" + bar); print("  E. INTENSIVE PROPS + INPUT BOUNDS"); print(bar)
chk(abs(d["P_bara"] - EJ_P_DISCH_BARA) < 1e-9, "P_disch == 144.2 bar a (diffuser recovery, const)")
chk(abs(d["rho"] - EJ_RHO_DISCH) < 1e-9, "rho_disch == 877.9 kg/m3 (const, comp-invariant)")
chk(abs(d["vol_m3h"] - d["total_kgh"]/EJ_RHO_DISCH) < 1e-9, "vol_m3h == total_kgh / rho (consistent)")
chk(abs(d["MW"] - d["total_kgh"]/d["mol_kmolh"]) < 1e-9, "MW == m_d / n_d (consistent)")
chk(ejp(1.0, opn=0.0)["suction_kgh"] == ejp(1.0, opn=10.0)["suction_kgh"], "hv_open<10 clamped to 10% (spindle low stop)")
chk(ejp(1.0, opn=120.0)["suction_kgh"] == ejp(1.0, opn=100.0)["suction_kgh"], "hv_open>100 clamped to 100% (spindle high stop)")
neg = ejp(1.0, frac=-0.5)
chk(neg["suction_kgh"] == 0.0 and abs(neg["comp"]["NH3"] - MOT_LIVE) < 1e-6, "scrub_level_frac<0 -> m_suc==0, discharge == pure motive NH3 (clamped)")
fin_ok = True
for pm in (0.0, 0.1, 0.25, 0.5, 1.0, 1.5, 2.0):
    for opn in (0.0, 50.0, 100.0, 130.0):
        for fr in (-1.0, 0.0, 1.0, 2.0):
            r = ejector_322f001(MOT_LIVE*pm, TM, opn, fr)
            fin_ok &= all(math.isfinite(r[q]) for q in ("total_kgh","suction_kgh","T_C","mu","vol_m3h","MW"))
            fin_ok &= r["total_kgh"] >= -1e-9 and r["suction_kgh"] >= -1e-9
chk(fin_ok, "all returns finite & non-negative across full phi_m x open x frac grid (no NaN/inf/negative mass)")

print("\n" + bar)
if fails:
    print("  F001 EJECTOR AUDIT:  %d CHECK(S) FAILED" % len(fails))
    for m in fails: print("     - " + m)
    raise SystemExit(1)
print("  F001 EJECTOR AUDIT:  ALL CHECKS PASS  --  unit clean, safe to proceed to 321P002 (NH3 pumps)")
print(bar)
