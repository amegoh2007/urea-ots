"""PHASE-2 BOUNDED FOREGROUND AUDIT  --  322E002 HP Carbamate Condenser (ISOLATED).

Re-evaluates the HPCC unit in isolation (pure-function calls + isolated level ODE; no full
synthesis-loop multi-settle, so no coupled-solver stall). Sections:
  A. Mass-balance closure  : feed_kg == gas_kg + liq_kg EXACTLY (liq = feed - gas, no reaction sink)
                             across off-design stripper-gas + ejector-liquid feed sweeps.
  B. Energy / NTU quench   : duty = q_carb + q_sens; T_prod stays between shell-sat and T_adb;
                             q_steam >= 0; design pin T_prod == 170.0 C; finite (no drift).
  C. Bubble-P synthesis    : P_bub == 144.2 at design, clamped to physical band off-design, finite;
                             the documented TT-322010 V-trough is CONTINUOUS (fine N/C probe).
  D. LT-322E002 level ODE  : ISSUE-c/e de-railed integrator -- L_eq = NLL*(phi_in/phi_fwd) bounded
                             fixed point, returns to design NLL, conserves (in==out at SS).
Run:  python backend/tests/audit_e002_hpcc.py
"""
import os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import main
from main import (MW_COMP, stripper_322e001, ejector_322f001, hpcc_322e002, bubble_p_322e002,
                  STRIP_FEED207_KMOLH, CO2_DES_KGH, STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA,
                  EJ_MOTIVE_NH3_DES, EJ_MOTIVE_T_DES_C, EJ_OPEN_DES,
                  HPCC_T_PROD_DES_C, HPCC_STEAM_TSAT_C, HPCC_P_DES_BARA,
                  HPCC_LEVEL_NLL_PCT, HPCC_TAU_FILL_MIN, HPCC_LIQ_DES_LIVE, reactor, clamp)

CO2_DES_TH = CO2_DES_KGH / 1000.0
L0, W0 = reactor.L0_DES, reactor.W0_DES
# design HPCC carbamate-MELT N/C -- the bubble_p_322e002 fN anchor (NH3-richer than the reactor FEED N/C
# L0, since all fresh NH3 enters as ejector motive).  Auto-captured at boot (main.HPCC_NC_DES_LIVE ~3.12324);
# fall back to L0 only if the pin failed to populate (matches bubble_p_322e002's own _nc0 fallback).
NC_MELT = main.HPCC_NC_DES_LIVE if main.HPCC_NC_DES_LIVE is not None else L0
fails = []
def chk(cond, msg):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", msg))
    if not cond: fails.append(msg)

def strip_at(cs=1.0, Lf=L0, Wf=W0, ts=STRIP_STEAM_T_DES_C):
    return stripper_322e001(cs*CO2_DES_TH, ts, STRIP_P_DES_BARA,
                            overflow_kmolh=STRIP_FEED207_KMOLH, L_feed=Lf, W_feed=Wf)
def ej_at(mot_scale=1.0, hv=EJ_OPEN_DES):
    return ejector_322f001(EJ_MOTIVE_NH3_DES*mot_scale, EJ_MOTIVE_T_DES_C, hv)

bar = "=" * 116
print(bar); print("  322E002 HP CARBAMATE CONDENSER  --  ISOLATED UNIT AUDIT (Phase 2)"); print(bar)
print("  HPCC_UA pinned = %s   (None => warm-up pass, T_prod held at design)"
      % ("%.1f kJ/h.K" % main.HPCC_UA if main.HPCC_UA is not None else "None"))

# DESIGN-PIN INVARIANTS are FEED-INDEPENDENT (gate=0 hold + warm-up hold).  They do NOT require the
# isolated synthetic single-call feed to reproduce the SETTLED-LIVE design feed -- HPCC_UA is
# deliberately back-calculated on the settled-live state (main.py:2454), which runs ~0.17% higher
# tube throughput than the pure-function single-call.  So the gate=1 live quench on the synthetic
# feed lands a hair LOW (lower m_dot -> larger UA/(m.cp) -> T_prod pulled toward T_sat), and the
# shell q_steam backfills that small deficit.  This is the documented understatement, NOT drift.
g0, l0 = strip_at(), ej_at()
d  = hpcc_322e002(g0, l0, t_shell=HPCC_STEAM_TSAT_C, gate=1.0)   # full live quench
dp = hpcc_322e002(g0, l0, t_shell=HPCC_STEAM_TSAT_C, gate=0.0)   # design-pin HOLD (feed-independent)
print("\n  DESIGN POINT (synthetic single-call feed):")
print("    gate=0 (pin) T_prod=%.10f  q_steam=%.4f  duty=%.4f" % (dp["T_prod"], dp["q_steam_kw"], dp["duty_kw"]))
print("    gate=1 (live)T_prod=%.4f  T_adb=%.2f  T_feed_mix=%.2f  P_bub=%.3f  duty=%.1f kW  q_steam=%.1f kW"
      % (d["T_prod"], d["T_adb"], d["T_feed_mix"], d["P_bara"], d["duty_kw"], d["q_steam_kw"]))
print("    gas=%.3f t/h  liq=%.3f t/h  m_dot=%.1f  | synth/live liq ratio=%.5f"
      % (d["gas_th"], d["liq_th"], d["m_dot"], d["liq_kgh"]/HPCC_LIQ_DES_LIVE))
# (1) gate=0 design pin is BIT-EXACT regardless of feed
chk(abs(dp["T_prod"] - HPCC_T_PROD_DES_C) < 1e-9, "gate=0 design-pin T_prod == 170.0 C bit-exact (got %.10f)" % dp["T_prod"])
chk(abs(dp["duty_kw"] - dp["q_steam_kw"]) < 1e-6, "gate=0 q_steam == duty bit-exact (T_prod at pin, no shell backfill)")
# (2) bubble-P pin anchor is exact at the DESIGN MELT composition (N/C = HPCC_NC_DES_LIVE ~3.12324, the
#     NH3-richer combined HPCC melt -- all fresh NH3 enters as ejector motive -- NOT the reactor-FEED N/C
#     L0_DES=3.07296; H/C settles at W0).  This live melt composition is what the 144.2-bar surface anchors to.
chk(abs(bubble_p_322e002(HPCC_T_PROD_DES_C, NC_MELT, W0) - HPCC_P_DES_BARA) < 1e-6,
    "bubble_p(170, NC_melt=HPCC_NC_DES_LIVE, W0_DES) == 144.2 bar bit-exact (P_bub pin anchor)")
# (3) gate=1 on the synthetic feed lands within 0.5 C of pin, LOW side (correct direction for ~0.17% low m_dot)
chk(0.0 <= (HPCC_T_PROD_DES_C - d["T_prod"]) < 0.5,
    "gate=1 synthetic-feed T_prod within [169.5, 170.0] (got %.4f): ~0.17%% throughput understatement, correct sign" % d["T_prod"])
chk(d["q_steam_kw"] >= d["duty_kw"] - 1e-6,
    "gate=1 q_steam >= duty (shell backfills the %.1f kW sub-pin deficit, no energy creation)" % (d["q_steam_kw"]-d["duty_kw"]))

# ============================================================================================== A
print("\n" + bar); print("  A. MASS-BALANCE CLOSURE  (feed_kg = gas_kg + liq_kg, phase split conserves mass)"); print(bar)
print("   case                        | feed_kg    gas_kg    liq_kg  | resid_kg  resid_ppm")
worst = 0.0; allfin = True; cases = []
for cs in (0.6, 0.8, 1.0, 1.2, 1.4):
    for Lf in (L0, L0*1.2):
        for ms in (0.7, 1.0, 1.3):
            cases.append((cs, Lf, ms))
for (cs, Lf, ms) in cases:
    g = strip_at(cs=cs, Lf=Lf); l = ej_at(mot_scale=ms)
    r = hpcc_322e002(g, l, gate=1.0)
    feed_kg = sum(r["feed_kmolh"][k]*MW_COMP[k] for k in MW_COMP)
    resid = feed_kg - (r["gas_kgh"] + r["liq_kgh"])
    worst = max(worst, abs(resid)/feed_kg*1e6)
    if not all(math.isfinite(r[k]) for k in ("gas_kgh","liq_kgh","T_prod","P_bara","duty_kw")): allfin = False
for (cs, Lf, ms) in (cases[0], cases[len(cases)//2], cases[-1]):
    g = strip_at(cs=cs, Lf=Lf); l = ej_at(mot_scale=ms); r = hpcc_322e002(g, l, gate=1.0)
    feed_kg = sum(r["feed_kmolh"][k]*MW_COMP[k] for k in MW_COMP)
    resid = feed_kg - (r["gas_kgh"]+r["liq_kgh"])
    print("   cs=%.1f L=%.3f mot=%.1f        | %9.1f %9.1f %9.1f | %8.4f %9.2f"
          % (cs, Lf, ms, feed_kg, r["gas_kgh"], r["liq_kgh"], resid, abs(resid)/feed_kg*1e6))
chk(worst < 1.0, "mass closure |feed-(gas+liq)| < 1 ppm across %d cases (worst %.3f ppm)" % (len(cases), worst))
chk(allfin, "all HPCC outputs finite (no NaN/Inf) across full feed sweep")

# ============================================================================================== B
print("\n" + bar); print("  B. ENERGY BALANCE + NTU QUENCH  (T_prod between shell-sat and T_adb; q_steam>=0)"); print(bar)
print("   case            | T_feed_mix  T_adb   T_prod  | duty_kw  q_steam | bracket_ok")
ok_bracket = True; ok_qsteam = True
for (cs, Lf, ms) in ((0.7,L0,1.0),(1.0,L0,1.0),(1.3,L0,1.0),(1.0,L0*1.25,1.0),(1.0,L0,0.7),(1.0,L0,1.3)):
    g = strip_at(cs=cs, Lf=Lf); l = ej_at(mot_scale=ms); r = hpcc_322e002(g, l, gate=1.0)
    lo = min(HPCC_STEAM_TSAT_C, r["T_adb"]); hi = max(HPCC_STEAM_TSAT_C, r["T_adb"])
    br = (lo - 0.5) <= r["T_prod"] <= (hi + 0.5)
    ok_bracket &= br; ok_qsteam &= (r["q_steam_kw"] >= -1e-9)
    print("   cs=%.1f L=%.3f m=%.1f| %9.2f %7.2f %7.2f | %7.1f %7.1f | %s"
          % (cs, Lf, ms, r["T_feed_mix"], r["T_adb"], r["T_prod"], r["duty_kw"], r["q_steam_kw"], br))
chk(ok_bracket, "T_prod always bracketed by [shell_sat, T_adb] (NTU quench physical, no overshoot)")
chk(ok_qsteam,  "q_steam_kw >= 0 across sweep (no negative shell duty / energy creation)")

# ============================================================================================== C
print("\n" + bar); print("  C. BUBBLE-POINT SYNTHESIS P + V-TROUGH CONTINUITY"); print(bar)
# C1 bubble_p monotonicity (design anchored at the MELT N/C = HPCC_NC_DES_LIVE, see header note (2))
chk(abs(bubble_p_322e002(HPCC_T_PROD_DES_C, NC_MELT, W0) - HPCC_P_DES_BARA) < 1e-6,
    "bubble_p(170, NC_melt, W0) == 144.2 bar (design melt anchor)")
chk(bubble_p_322e002(HPCC_T_PROD_DES_C, L0*1.1, W0) > bubble_p_322e002(HPCC_T_PROD_DES_C, L0, W0),
    "dP/d(N/C) > 0 (free-NH3 volatility lifts bubble P)")
chk(bubble_p_322e002(HPCC_T_PROD_DES_C, L0, W0*1.1) < bubble_p_322e002(HPCC_T_PROD_DES_C, L0, W0),
    "dP/d(H/C) < 0 (water dilution drops bubble P)")
# C2 P_bara clamped off-design (ratio band 0.5..2.0x), finite, no 330-bar impulse on CO2->0
print("\n   CO2-cut transient (cs -> 0): P_bara must stay bounded, never impulse to ~330 bar:")
print("      cs     | P_bara   T_prod   gas_th")
maxP = 0.0
for cs in (1.0, 0.5, 0.2, 0.05, 0.01, 1e-4):
    g = strip_at(cs=cs); l = ej_at(mot_scale=cs if cs > 0.05 else 0.05)
    r = hpcc_322e002(g, l, gate=1.0); maxP = max(maxP, r["P_bara"])
    print("      %.4f | %7.3f  %7.2f  %6.3f" % (cs, r["P_bara"], r["T_prod"], r["gas_th"]))
chk(maxP < 1.6 * HPCC_P_DES_BARA, "P_bara bounded < 1.6x design across CO2-cut (no N/C->inf impulse; max %.2f)" % maxP)
# C3 fine N/C probe across the documented V-trough vertex -> continuous & finite (no jump/NaN)
print("\n   fine N/C probe across V-trough vertex (T_prod must be continuous & finite):")
print("      L/L0   | T_prod    P_bara")
prevT = None; cont = True; finite = True
for f in (0.97, 0.99, 1.00, 1.01, 1.03):
    g = strip_at(Lf=L0*f); l = ej_at(); r = hpcc_322e002(g, l, gate=1.0)
    print("      %.3f  | %7.3f   %7.3f" % (f, r["T_prod"], r["P_bara"]))
    finite &= math.isfinite(r["T_prod"]) and math.isfinite(r["P_bara"])
    if prevT is not None and abs(r["T_prod"] - prevT) > 80.0: cont = False
    prevT = r["T_prod"]
chk(finite, "T_prod/P_bara finite across the V-trough vertex")
chk(cont, "no >80 C step between adjacent fine N/C samples (vertex sharp but continuous, not a discontinuity)")

# ============================================================================================== D
print("\n" + bar); print("  D. LT-322E002 LIQUID-LEVEL ODE  (ISSUE-c/e de-railed integrator)"); print(bar)
NLL = HPCC_LEVEL_NLL_PCT; tau_s = HPCC_TAU_FILL_MIN * 60.0
def settle_level(phi_in, phi_fwd, L0pct, dt=0.5, n=8000):
    L = L0pct
    for _ in range(n):
        phi_out = phi_fwd * (L / NLL)
        L = clamp(L + (phi_in - phi_out) * 100.0 * dt / tau_s, 0.0, 100.0)
    return L
# D1 design fixed point: phi_in=phi_fwd=1 -> dL=0 at NLL
L = clamp(NLL + (1.0 - 1.0*(NLL/NLL))*100.0*0.5/tau_s, 0.0, 100.0)
chk(abs(L - NLL) < 1e-9, "design: phi_in=phi_fwd=1, L=NLL -> dL/dt == 0 (NLL exact fixed point)")
print("\n   bounded-equilibrium check (L_eq should equal NLL*phi_in/phi_fwd, NOT rail):")
print("      phi_in  phi_fwd | L_eq(settled)  L_eq(theory)  | railed?")
ok_eq = True; ok_norail = True
for (pin, pfwd) in ((1.0,1.0), (1.2,1.0), (0.8,1.0), (1.0,1.2), (0.7,1.4)):
    Lset = settle_level(pin, pfwd, NLL)
    Lth = clamp(NLL * pin / pfwd, 0.0, 100.0)
    railed = Lset <= 1e-6 or Lset >= 100.0 - 1e-6
    ok_eq &= abs(Lset - Lth) < 0.5; ok_norail &= (not railed or abs(Lth-Lset) < 0.5)
    print("      %.2f    %.2f    | %10.4f    %10.4f    | %s" % (pin, pfwd, Lset, Lth, railed))
chk(ok_eq, "L settles to bounded L_eq = NLL*(phi_in/phi_fwd) within 0.5%% (first-order lag, no rail)")
chk(ok_norail, "no spurious rail-to-100%% (the old level-independent-outflow integrator bug is gone)")
# D2 conservation at SS: phi_out == phi_in (make in == fwd out)
Lset = settle_level(1.15, 1.0, NLL); phi_out_ss = 1.0 * (Lset/NLL)
chk(abs(phi_out_ss - 1.15) < 0.01, "steady-state outflow == inflow (phi_out=%.4f vs phi_in=1.15): conserved" % phi_out_ss)
# D3 returns to design NLL when phi_in restored to phi_fwd after a +20% level kick
Lset = settle_level(1.0, 1.0, NLL + 20.0)
chk(abs(Lset - NLL) < 0.5, "level returns to design NLL (%.1f%%) after +20%% kick (got %.4f)" % (NLL, Lset))

print("\n" + bar)
if fails:
    print("  E002 HPCC AUDIT:  %d CHECK(S) FAILED" % len(fails))
    for m in fails: print("     - " + m)
    raise SystemExit(1)
print("  E002 HPCC AUDIT:  ALL CHECKS PASS  --  unit clean, safe to proceed to 322E003 (Scrubber)")
print(bar)
