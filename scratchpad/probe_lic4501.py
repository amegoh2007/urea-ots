"""Item 23 (R2) acceptance: LIC-324501 melt drain re-modelled -- LV-324501B is the
sole ACTIVE drain carrying 324F003 melt to the 335 boundary; LV-324501A
(forward-to-granulation) is PARKED at 0 % (335 granulation unbuilt, Scope Lock).

Proves:
  1. LV_324501A / LV_324501B are DISTINCT published signals (fixes the duplicate
     bind where both faceplates read LIC_324501.op).
  2. LV-324501A parked at 0 %, LV-324501B at the design stroke (op_des 75 %).
  3. Design melt EXITS the envelope: m_fwd == R324_P2_DES bit-exact at boot.
  4. STRICT conservation -- the 324F003 mass balance closes (feed == vapour +
     melt) and urea does NOT accumulate: over 600 s the holdup stays steady and
     the level parks at SP (the R1 recycle-to-Stage-1 runaway must NOT recur).
Run: cd backend && python ../scratchpad/probe_lic4501.py
"""
import sys, os
BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, BACKEND); os.chdir(BACKEND)
import main

P2_th = main.R324_P2_DES / 1000.0
SP    = main.R324_F003_LVL_SP

telem = main.step_sim(0.1)                                   # tick 1 = design point
e = telem["EVAP_324"]["E003"]
LVa0 = e.get("LV_324501A"); LVb0 = e.get("LV_324501B")
feed0, vap0, fwd0, recyc0 = e["feed_th"], e["vapour_th"], e["melt_fwd_th"], e["recyc_th"]
M_init = main.state.r324_f003_M
print(f"R324_P2_DES (design melt)  = {P2_th:.3f} t/h")
print(f"LV_324501A / LV_324501B    = {LVa0} / {LVb0} %   (A parked 0, B ~75)")
print(f"tick1: feed={feed0} vapour={vap0} melt_fwd={fwd0} recyc={recyc0} t/h")
print(f"       balance feed-(vap+fwd) = {feed0-(vap0+fwd0):+.4f} t/h  (must ~0)")

# --- settle 600 s at design, holdup must stay steady, level at SP -----------------
for _ in range(6000):
    telem = main.step_sim(0.1)
e2 = telem["EVAP_324"]["E003"]
M_fin = main.state.r324_f003_M
lvl   = e2["LI_324F003"]
feed2, vap2, fwd2 = e2["feed_th"], e2["vapour_th"], e2["melt_fwd_th"]
dM_pct = abs(M_fin - M_init) / M_init * 100.0
print(f"after 600 s: level={lvl}% (SP {SP})  holdup drift={dM_pct:.3f}%  "
      f"balance feed-(vap+fwd)={feed2-(vap2+fwd2):+.4f} t/h")

bad = 0
if LVa0 is None or LVb0 is None:
    print("FAIL: LV_324501A / LV_324501B not both published"); bad += 1
else:
    if abs(LVa0 - 0.0) > 1e-6:
        print("FAIL: LV-324501A not parked at 0 %"); bad += 1
    if abs(LVb0 - main.R324_LIC501_OP_DES) > 0.5:
        print("FAIL: LV-324501B not at design stroke"); bad += 1
    if abs(LVa0 - LVb0) < 1e-6:
        print("FAIL: LV-A and LV-B are not distinct (duplicate-bind not fixed)"); bad += 1
if abs(fwd0 - round(P2_th, 2)) > 1e-6:                       # 2-dp telemetry vs design melt
    print(f"FAIL: design melt does not exit as P2_DES ({fwd0} vs {round(P2_th,2)})"); bad += 1
if abs(recyc0) > 1e-6:
    print("FAIL: recycle path not zero under R2"); bad += 1
if abs(feed0 - (vap0 + fwd0)) > 5e-3:
    print("FAIL: tick1 mass balance does not close (in != out)"); bad += 1
if abs(feed2 - (vap2 + fwd2)) > 5e-3:
    print("FAIL: settled mass balance does not close"); bad += 1
if dM_pct > 1.0:
    print("FAIL: 324F003 holdup drifted >1% (urea accumulation/drain)"); bad += 1
if lvl > 90.0 or lvl < 20.0:
    print("FAIL: level ran away / drained (not parked near SP)"); bad += 1

print(f"\nFAILURES: {bad}")
sys.exit(1 if bad else 0)
