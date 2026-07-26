"""Item 25 acceptance: FT-322402 -> stream 755 volumetric flow (m3/h) at design.
PFD (Combined_1750): 755 mass 31478 kg/h, vol 31.3 m3/h, rho 1005.  Run: cd backend && python ../scratchpad/probe755.py
"""
import sys, os
BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, BACKEND); os.chdir(BACKEND)
import main

telem = main.step_sim(0.1)                      # tick 1 = design point
d003 = telem["ABSORB_328"]["D003"]

bad = 0
flow = d003["flow755_m3h"]
draw = d003["collect755_th"]
print(f"flow755_m3h = {flow}  (PFD 31.3)")
print(f"collect755_th = {draw}  t/h  (PFD 31.478)")
print(f"const rho    = {main.A328_M755_RHO}  (PFD 1005)")
if not (31.2 <= flow <= 31.4):
    print("FAIL: flow755_m3h off PFD 31.3"); bad += 1
if not (31.4 <= draw <= 31.55):
    print("FAIL: collect755_th off PFD 31.478 t/h"); bad += 1

print(f"\nFAILURES: {bad}")
sys.exit(1 if bad else 0)
