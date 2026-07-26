"""Item 7 acceptance: TIC-328008 offgas H2O inferential -> PFD stream 737 = 46.21 mol% @117C/3.5bara.
Red before edit (drum-node Raoult ~62.9), green after (46.2). Run: cd backend && python ../scratchpad/probe_offgas.py
"""
import sys, os
BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, BACKEND); os.chdir(BACKEND)
import main

telem = main.step_sim(0.1)                       # tick 1 = design point
pv   = telem["DESORB_328"]["D001"]["TIC_328008"]["pv"]
des  = main.R328_D001_OFFGAS_H2O_DES
psat117 = main.psat_water_bara(117.0)
psat114 = main.psat_water_bara(114.0)
print(f"psat(117)            = {psat117:.4f} bara  (PFD ~1.80)")
print(f"psat(114)            = {psat114:.4f} bara")
print(f"OFFGAS_H2O_DES       = {des:.4f} mol%  (PFD 737 = 46.21)")
print(f"TIC_328008.pv (live) = {pv} mol%  (design)")

bad = 0
if not (46.15 <= des <= 46.27):
    print("FAIL: OFFGAS_H2O_DES off PFD 46.21"); bad += 1
if not (46.1 <= pv <= 46.3):
    print("FAIL: live TIC_328008.pv off PFD 46.2"); bad += 1

print(f"\nFAILURES: {bad}")
sys.exit(1 if bad else 0)
