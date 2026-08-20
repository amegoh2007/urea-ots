"""PHASE-1 BOUNDED FOREGROUND AUDIT  --  322E001 HP Stripper (ISOLATED).

Re-evaluates the stripper unit model in isolation (no full synthesis-loop settle, so no
coupled-solver stall). Three sections:
  A. Mass-balance closure   : feed_kg == top_kg + bot_kg (+/- reaction rearrangement) across
                              off-design steam-T / CO2-strip / feed-N-C / H-C / pressure sweeps.
  B. eta_T + volatile slip  : thermal strip efficiency and NH3/CO2 breakthrough behave monotone,
                              bounded, finite (no numerical drift / blow-up) off-design.
  C. LIC-322501 sump drain  : isolated bottom-sump ODE -- conservation (in==out at SS), level
                              self-regulates to SP, drain flow non-negative & bounded.
Run:  python backend/tests/audit_e001_stripper.py
"""
import os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import main
from main import (MW_COMP, stripper_322e001, STRIP_FEED207_KMOLH, CO2_DES_KGH,
                  STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA, STRIP_BOT_DES_KGH,
                  STRIP_FEED_DES_KGH, reactor, clamp)

CO2_DES_TH = CO2_DES_KGH / 1000.0
L0, W0 = reactor.L0_DES, reactor.W0_DES
fails = []
def chk(cond, msg):
    tag = "PASS" if cond else "FAIL"
    if not cond: fails.append(msg)
    print("   [%s] %s" % (tag, msg))

def feed_mass(d):  return sum(d[k] * MW_COMP[k] for k in MW_COMP)

bar = "=" * 116
print(bar); print("  322E001 HP STRIPPER  --  ISOLATED UNIT AUDIT (Phase 1)"); print(bar)

# ---- design reference -------------------------------------------------------------------------
d = stripper_322e001(CO2_DES_TH, STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA,
                     overflow_kmolh=STRIP_FEED207_KMOLH, L_feed=L0, W_feed=W0)
mf_des = d["m_feed_kgh"]
print("\n  DESIGN POINT:  T_steam=%.1f C  P=%.1f bar  CO2=%.2f t/h" %
      (STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA, CO2_DES_TH))
print("    eta_T=%.4f  T_bot=%.2f C  T_top=%.2f C  top=%.3f t/h  bot=%.3f t/h  slip=%.4f" %
      (d["eta_T"], d["T_bot"], d["T_top"], d["top_th"], d["bot_th"], d["slip"]))
chk(abs(d["eta_T"] - 1.0) < 1e-9,        "eta_T == 1.0 at design (got %.6f)" % d["eta_T"])
chk(abs(d["slip"]) < 1e-9,               "slip  == 0   at design (got %.6f)" % d["slip"])
chk(abs(d["bot_th"]*1000 - STRIP_BOT_DES_KGH) < 600.0,
    "bot flow ~= design %.0f kg/h (got %.0f)" % (STRIP_BOT_DES_KGH, d["bot_th"]*1000))

# ============================================================================================== A
print("\n" + bar); print("  A. MASS-BALANCE CLOSURE  (feed_kg = top_kg + bot_kg +/- reaction rearrangement)"); print(bar)
print("   case                     | feed_kg    top_kg    bot_kg   |  resid_kg   resid_ppm")
sweep = []
for ts in (STRIP_STEAM_T_DES_C-15, STRIP_STEAM_T_DES_C, STRIP_STEAM_T_DES_C+8):
    for cs in (0.6, 0.8, 1.0, 1.2, 1.4):
        for (Lf, Wf, P) in ((L0,W0,STRIP_P_DES_BARA), (L0*1.15,W0,STRIP_P_DES_BARA),
                            (L0,W0*1.20,STRIP_P_DES_BARA), (L0,W0,STRIP_P_DES_BARA*1.05)):
            sweep.append((ts, cs, Lf, Wf, P))
worst_ppm = 0.0
for (ts, cs, Lf, Wf, P) in sweep:
    r = stripper_322e001(cs*CO2_DES_TH, ts, P, overflow_kmolh=STRIP_FEED207_KMOLH, L_feed=Lf, W_feed=Wf)
    mfk = r["m_feed_kgh"]; mtk = r["top_kgh"]; mbk = r["bot_kgh"]
    resid = mfk - (mtk + mbk)               # reactions conserve element mass -> ~0 unless clamp fires
    ppm = abs(resid) / mfk * 1e6
    worst_ppm = max(worst_ppm, ppm)
for (ts, cs, Lf, Wf, P) in (sweep[0], sweep[len(sweep)//2], sweep[-1]):
    r = stripper_322e001(cs*CO2_DES_TH, ts, P, overflow_kmolh=STRIP_FEED207_KMOLH, L_feed=Lf, W_feed=Wf)
    mfk = r["m_feed_kgh"]; resid = mfk - (r["top_kgh"]+r["bot_kgh"])
    print("   Ts=%5.1f cs=%.1f L=%.3f W=%.3f | %9.1f %9.1f %9.1f | %9.4f %8.2f"
          % (ts, cs, Lf, Wf, mfk, r["top_kgh"], r["bot_kgh"], resid, abs(resid)/mfk*1e6))
chk(worst_ppm < 50.0, "mass closure |feed-(top+bot)| < 50 ppm across %d off-design cases (worst %.2f ppm)"
    % (len(sweep), worst_ppm))
allfin = all(math.isfinite(v) for (ts,cs,Lf,Wf,P) in sweep
             for v in (lambda r:(r["top_kgh"],r["bot_kgh"],r["eta_T"],r["T_bot"],r["slip"]))(
                 stripper_322e001(cs*CO2_DES_TH,ts,P,overflow_kmolh=STRIP_FEED207_KMOLH,L_feed=Lf,W_feed=Wf)))
chk(allfin, "all stripper outputs finite (no NaN/Inf) across full sweep")

# ============================================================================================== B
print("\n" + bar); print("  B. THERMAL STRIP EFFICIENCY (eta_T) + VOLATILE SLIP  vs  off-design drivers"); print(bar)

print("\n  B1. steam T sweep (CO2=des, feed=des) -- eta_T tracks steam heat, slip stays 0:")
print("      T_steam | eta_T  eta_Tst  g_T    | T_bot   T_top  | top_th  | slip")
prev_eta = None; mono_eta = True
for ts in (STRIP_STEAM_T_DES_C-20, STRIP_STEAM_T_DES_C-10, STRIP_STEAM_T_DES_C,
           STRIP_STEAM_T_DES_C+5, STRIP_STEAM_T_DES_C+10):
    r = stripper_322e001(CO2_DES_TH, ts, STRIP_P_DES_BARA, overflow_kmolh=STRIP_FEED207_KMOLH, L_feed=L0, W_feed=W0)
    print("      %6.1f  | %.4f %.4f %.4f | %6.2f %6.2f | %6.3f | %.4f"
          % (ts, r["eta_T"], r["eta_T_steam"], r["g_T"], r["T_bot"], r["T_top"], r["top_th"], r["slip"]))
    if prev_eta is not None and r["eta_T"] < prev_eta - 1e-9: mono_eta = False
    prev_eta = r["eta_T"]
chk(mono_eta, "eta_T monotonically non-decreasing with steam T (more heat -> better strip)")

print("\n  B2. feed N/C choke sweep (excess NH3 -> g_NC chokes -> slip rises, eta_T falls):")
print("      L/L0  | g_NC   eta_T  | slip   | top_NH3%  top_CO2%")
prev_slip = None; mono_slip = True; prev_e = None; mono_ed = True
for f in (1.0, 1.10, 1.25, 1.45, 1.70):
    r = stripper_322e001(CO2_DES_TH, STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA,
                         overflow_kmolh=STRIP_FEED207_KMOLH, L_feed=L0*f, W_feed=W0)
    print("      %.2f  | %.4f %.4f | %.4f | %7.3f  %7.3f"
          % (f, r["g_NC"], r["eta_T"], r["slip"], r["top_comp_pct"]["NH3"], r["top_comp_pct"]["CO2"]))
    if prev_slip is not None and r["slip"] < prev_slip - 1e-9: mono_slip = False
    if prev_e   is not None and r["eta_T"] > prev_e + 1e-9:    mono_ed = False
    prev_slip = r["slip"]; prev_e = r["eta_T"]
chk(mono_slip, "volatile slip monotonically rises as feed N/C chokes the strip")
chk(mono_ed,   "eta_T monotonically falls as feed N/C chokes the strip")

print("\n  B3. bounds/drift guard -- extreme off-design must stay clamped & finite:")
rlo = stripper_322e001(0.2*CO2_DES_TH, STRIP_STEAM_T_DES_C-40, STRIP_P_DES_BARA,
                       overflow_kmolh=STRIP_FEED207_KMOLH, L_feed=L0*2.0, W_feed=W0*2.0)
rhi = stripper_322e001(2.5*CO2_DES_TH, STRIP_STEAM_T_DES_C+30, STRIP_P_DES_BARA*1.1,
                       overflow_kmolh=STRIP_FEED207_KMOLH, L_feed=L0*0.5, W_feed=W0*0.5)
for tag, r in (("lean/cold/dilute", rlo), ("flood/hot/conc", rhi)):
    print("      %-16s eta_T=%.4f  slip=%.4f  T_bot=%.2f  T_top=%.2f  bot_th=%.3f"
          % (tag, r["eta_T"], r["slip"], r["T_bot"], r["T_top"], r["bot_th"]))
chk(0.0 <= rlo["eta_T"] <= 1.15 and 0.0 <= rhi["eta_T"] <= 1.15, "eta_T clamped to [0,1.15] at extremes")
chk(rlo["T_bot"] <= rlo["T_steam"]+1e-6 and rhi["T_bot"] <= rhi["T_steam"]+1e-6,
    "T_bot never exceeds steam saturation T (NTU ceiling holds, no sign blow-up)")
chk(all(math.isfinite(rlo[k]) and math.isfinite(rhi[k]) for k in
        ("eta_T","slip","T_bot","T_top","top_th","bot_th")), "extreme-case outputs finite")

# ============================================================================================== C
print("\n" + bar); print("  C. LIC-322501 BOTTOM-SUMP  --  isolated drain-conservation ODE"); print(bar)
from main import (STRIP_SUMP_AREA_M2, STRIP_LEVEL_SPAN_M, STRIP_RHO_BOTTOM,
                  STRIP_LEVEL_SP_DES, LV322501_OPEN_DES, LV322501_P_DOWN_BARA,
                  SYN_P_DES_BARA, LIC_322501_KC, LIC_322501_TI)
m_span_kg = STRIP_SUMP_AREA_M2 * STRIP_LEVEL_SPAN_M * STRIP_RHO_BOTTOM
bot_in_kgh = d["bot_kgh"]                              # steady design bottoms inflow
p_syn = SYN_P_DES_BARA

def drain(level, op):
    """LV-322501 letdown (isolated): design-anchored sqrt(dP) law, no crystallization throttle here."""
    dP = max(p_syn - LV322501_P_DOWN_BARA, 0.0)
    return STRIP_BOT_DES_KGH * (clamp(op,0,100)/LV322501_OPEN_DES) \
           * (dP / max(SYN_P_DES_BARA - LV322501_P_DOWN_BARA, 1e-6))**0.5

# C1: design steady state -- find the op that makes drain == inflow, confirm level holds
op_ss = LV322501_OPEN_DES * (bot_in_kgh / STRIP_BOT_DES_KGH)   # exact balance op
print("\n  C1. steady-state conservation: bot_in=%.1f kg/h  op_ss=%.2f%%  drain(op_ss)=%.1f kg/h"
      % (bot_in_kgh, op_ss, drain(STRIP_LEVEL_SP_DES, op_ss)))
chk(abs(drain(STRIP_LEVEL_SP_DES, op_ss) - bot_in_kgh) < 1.0,
    "drain(op_ss) conserves design bottoms inflow (|in-out| < 1 kg/h)")

# C2: closed-loop LIC-322501 regulation -- perturb level +15%, confirm it returns to SP, bounded ticks
lvl = STRIP_LEVEL_SP_DES + 15.0
op  = LV322501_OPEN_DES
e_prev = lvl - STRIP_LEVEL_SP_DES
dt = 0.5; mn=lvl; mx=lvl; drain_min=1e18; drain_max=-1e18
for k in range(1, 4001):                                # bounded 2000 s, no full-loop coupling
    e = lvl - STRIP_LEVEL_SP_DES                        # direct-acting
    op = clamp(op + LIC_322501_KC*((e - e_prev) + (dt/LIC_322501_TI)*e), 0.0, 100.0)
    e_prev = e
    dr = drain(lvl, op); drain_min=min(drain_min,dr); drain_max=max(drain_max,dr)
    lvl = clamp(lvl + (bot_in_kgh - dr)/3600.0*dt/m_span_kg*100.0, 0.0, 100.0)
    mn=min(mn,lvl); mx=max(mx,lvl)
print("\n  C2. step +15%% on level, 2000 s PI loop: final level=%.3f%%  op=%.2f%%  drain in[%.0f, %.0f]"
      % (lvl, op, drain_min, drain_max))
print("       level excursion band: [%.2f, %.2f]%%" % (mn, mx))
chk(abs(lvl - STRIP_LEVEL_SP_DES) < 1.0, "LIC-322501 returns level to SP (%.1f%%) within +/-1%% (got %.3f)"
    % (STRIP_LEVEL_SP_DES, lvl))
chk(drain_min >= -1e-9, "drain flow never negative (no reverse flow / mass creation)")
chk(0.0 <= lvl <= 100.0 and 0.0 <= op <= 100.0, "level & valve op stay in physical [0,100] bounds")

print("\n" + bar)
if fails:
    print("  E001 STRIPPER AUDIT:  %d CHECK(S) FAILED" % len(fails))
    for m in fails: print("     - " + m)
    raise SystemExit(1)
print("  E001 STRIPPER AUDIT:  ALL CHECKS PASS  --  unit clean, safe to proceed to 322E002 (HPCC)")
print(bar)
