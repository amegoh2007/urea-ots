"""AGENT C: is FFIC-329401 Kc=8.0e5 stable AWAY from the 100 % design point?

The Kc was derived as Kc = 0.5/(a*g) with g = 1/(1000*S744_VOL_DES) evaluated ONLY at the
design wash-leg volume 31.4 m3/h.  But g is inversely proportional to the LIVE 744 volume,
so turning the FIC-328402 wash leg down multiplies the loop gain by 31.4/V744.
Predicted loop coefficient  1 - Kc*a*g  =  1 - 0.5*(31.4/V744).

  V744=31.4 -> +0.50 (monotone)   15.7 -> 0.00   10.5 -> -0.50   7.85 -> -1.00 (marginal)
  V744<7.85 -> |coef|>1 -> UNSTABLE
"""
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state if hasattr(main, "state") else main.STATE
DT = 0.1
VDES = main.S744_VOL_DES
f402, ffic, f401 = s.FIC_328402, s.FFIC_329401, s.FIC_329401

print(f"{'V744_frac':>10} {'V744':>7} {'pred_coef':>10} {'ratio_min':>10} {'ratio_max':>10} "
      f"{'FFICop_min':>11} {'FFICop_max':>11} {'revs':>6} {'m931_end':>9} {'verdict':>12}")
for frac in (1.0, 0.5, 0.35, 0.25, 0.20):
    f402["sp"] = (main.R3232_E003_M744_DES / main.RHO_744_KGM3) * frac
    for _ in range(24000): main.step_sim(DT)      # 2400 s to re-settle the wash leg
    V744 = f402["pv"]
    pred = 1.0 - 0.5 * (VDES / max(V744, 1e-9))
    # nudge the ratio SP by +2 % and watch the master
    ffic["sp"] = main.R328_FFIC_RATIO_DES * 1.02
    rmin, rmax = 1e30, -1e30; omin, omax = 1e30, -1e30
    prev = ffic["pv"]; dprev = 0.0; rev = 0
    for _ in range(18000):                         # 1800 s
        main.step_sim(DT)
        v = ffic["pv"]; o = ffic["op"]
        rmin, rmax = min(rmin, v), max(rmax, v); omin, omax = min(omin, o), max(omax, o)
        d = v - prev
        if abs(d) > 1e-14:
            if dprev != 0.0 and (d > 0) != (dprev > 0): rev += 1
            dprev = d
        prev = v
    m931 = main.R328_C004_M931_DES * (f401["op"] / 50.0)
    verdict = "MONOTONE" if rev <= 2 else ("RINGING" if rev < 200 else "OSCILLATING")
    if omax >= ffic["op_hi"] - 1e-6 or omin <= ffic["op_lo"] + 1e-6: verdict += "/SAT"
    print(f"{frac:10.2f} {V744:7.3f} {pred:10.3f} {rmin:10.5f} {rmax:10.5f} "
          f"{omin:11.1f} {omax:11.1f} {rev:6d} {m931:9.1f} {verdict:>12}")
    ffic["sp"] = main.R328_FFIC_RATIO_DES
