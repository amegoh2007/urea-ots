"""Verify 718A/718B bang-bang is dead after feed-forward decoupling.
Imports main (full settle), steps sim, prints FIC_328405 (718A) / FIC_323418 (718B)
volumetric PVs each tick.  Bang-bang => PV alternates every 2 ticks; settled => flat.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main  # settle

s = main.state
dt = 1.0
print("tick  718A_pv  718A_sp  718B_pv  718B_sp   718A_kgh   718B_kgh   sum_kgh")
RHO = main.RHO_718_KGM3
prev_a = None
amp = 0.0
for i in range(60):
    main.step_sim(dt)
    a = s.FIC_328405
    b = s.FIC_323418
    a_kg = a["pv"] * RHO
    b_kg = b["pv"] * RHO
    if i >= 40:  # measure amplitude over last 20 ticks (post any startup transient)
        if prev_a is not None:
            amp = max(amp, abs(a["pv"] - prev_a))
        prev_a = a["pv"]
    if i >= 50:
        print(f"{i:4d}  {a['pv']:7.4f}  {a['sp']:7.4f}  {b['pv']:7.4f}  {b['sp']:7.4f}  "
              f"{a_kg:9.2f}  {b_kg:9.2f}  {a_kg+b_kg:9.2f}")
print(f"\nmax |dPV_718A| over ticks 41-59 (limit-cycle amplitude): {amp:.6f} m3/h")
print("BANG-BANG DEAD" if amp < 1e-3 else "STILL OSCILLATING")
