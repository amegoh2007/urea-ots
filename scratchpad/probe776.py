"""Item 12 acceptance: FT-328401 -> stream 776 volumetric flow (m3/h) at design.
PFD (Combined_1750): 776 mass 8275 kg/h, vol 7.6 m3/h, rho 1095.  Run: cd backend && python ../scratchpad/probe776.py
"""
import sys, os
BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, BACKEND); os.chdir(BACKEND)
import main

telem = main.step_sim(0.1)                      # tick 1 = design point
d001 = telem["DESORB_328"]["D001"]
d003 = telem["ABSORB_328"]["D003"]

bad = 0
flow = d001["flow776_m3h"]
draw = d001["draw776_th"]
print(f"flow776_m3h = {flow}  (PFD 7.6)")
print(f"draw776_th  = {draw}  t/h")
print(f"const rho    = {main.R328_D001_M776_RHO}")
if not (7.5 <= flow <= 7.7):
    print("FAIL: flow776_m3h off PFD 7.6"); bad += 1
if "FIC_323401" in d003:
    print("FAIL: stray FIC_323401 still in ABSORB_328.D003"); bad += 1
else:
    print("OK: ABSORB_328.D003 no longer publishes FIC_323401")
if "FIC_323401" not in telem["LPCC_3232"]["E011"]:
    print("FAIL: FIC_323401 missing from its real home E011"); bad += 1
else:
    print("OK: FIC_323401 still published under LPCC_3232.E011")

print(f"\nFAILURES: {bad}")
sys.exit(1 if bad else 0)
