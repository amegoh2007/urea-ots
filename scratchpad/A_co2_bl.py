"""AGENT A probe 2 -- is the CO2 battery-limit an infinite pressure sink?

Tests:
  (a) Is P_line an independent state, or does it just track p_syn + 3.5 bar?
  (b) Does the delivered CO2 mass depend AT ALL on the synthesis backpressure across the
      normal band?  (If phi_HP == 1 for every reachable p_syn, the compressor delivers
      the same mass into ANY pressure -> infinite pressure sink.)
  (c) Is there a compressor curve (head vs flow)?  Raise the raw BL flow 3x and see whether
      the discharge pressure sags at all.
  (d) Suction-side: is there a CO2 supply inventory that can run out?
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa

s = main.state if hasattr(main, "state") else main.STATE
DT = 0.5

print("SYN_P_DES_BARA =", main.SYN_P_DES_BARA, " SYN_P_MAX_BARA =", main.SYN_P_MAX_BARA)
print("DP_HP_DES =", main.CO2_P_DES_BARA - main.SYN_P_DES_BARA,
      " P_line_ceil =", main.SYN_P_MAX_BARA + (main.CO2_P_DES_BARA - main.SYN_P_DES_BARA))
print()

# (a)+(b) sweep the synthesis pressure directly and read what the BL delivers.
print("--- (b) forced p_syn sweep, PV shut, one tick each (open-loop transfer) ---")
print(f"{'p_syn':>8} {'P_line':>9} {'dP_HP':>8} {'phi_HP':>8} {'feed t/h':>10} {'vent t/h':>10} {'Load %':>8}")
for psyn in (120.0, 135.0, 140.7, 144.0, 147.0, 150.0, 155.0, 160.0, 175.0):
    s.p_syn_bara = psyn
    t = main.step_sim(DT)
    c = t["CO2_FEED"]
    DP_HP_DES = main.CO2_P_DES_BARA - main.SYN_P_DES_BARA
    P_line_ceil = main.SYN_P_MAX_BARA + DP_HP_DES
    P_line = min(psyn + DP_HP_DES, P_line_ceil)
    dP = max(P_line - psyn, 0.0)
    print(f"{psyn:8.1f} {c['PIC_322203']:9.2f} {dP:8.3f} {min(1.0,(dP/DP_HP_DES)**0.5):8.4f} "
          f"{c['FY_322403']:10.3f} {c['vent_th']:10.3f} {c['Load']:8.2f}")

# (c) compressor curve? triple the raw flow, look at discharge pressure.
print("\n--- (c) raw BL flow step: does the discharge pressure sag with flow? ---")
s.p_syn_bara = 140.7
for raw in (10.0, 54.618, 150.0, 500.0):
    s.F_CO2_raw_th = raw
    for _ in range(20):
        t = main.step_sim(DT)
    c = t["CO2_FEED"]
    print(f"  raw={raw:7.2f} t/h -> P_line(PIC-322203 PV)={c['PIC_322203']:8.3f} bara   "
          f"feed={c['FY_322403']:8.3f} t/h   Load={c['Load']:8.2f} %")

print("\n--- (d) is there a finite CO2 source inventory? ---")
inv = [a for a in dir(s) if "co2" in a.lower()]
print("  state attrs containing 'co2':", inv)
print("  F_CO2_raw_th is a plain float set only by the operator command handler ->",
      "NO source inventory, NO compressor map, NO suction pressure.")
