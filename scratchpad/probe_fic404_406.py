import sys
sys.path.insert(0, r"D:\Work\Urea Simulation\backend")
import main

snap = None
for _ in range(1200):
    snap = main.step_sim(0.5)

d001 = snap["DESORB_328"]["D001"]
d003 = snap["ABSORB_328"]["D003"]
f404 = d001["FIC_328404"]
f406 = d003["FIC_328406"]
print("FIC_328404:", f404, " reflux775_th=", d001["reflux775_th"])
print("FIC_328406:", f406, " flow755_m3h=", d003["flow755_m3h"])

ok = True
if abs(f404["vol_m3h"] - 1.5) > 1e-9:
    ok = False; print("FAIL 328404.vol_m3h != 1.5")
if abs(f406["vol_m3h"] - 0.0) > 1e-9:
    ok = False; print("FAIL 328406.vol_m3h != 0.0 (spare idle)")
print("PROBE", "OK" if ok else "FAIL")
sys.exit(0 if ok else 1)
