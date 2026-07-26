"""Item 20 acceptance: HIC-329605 / HV-329605 = 324F002 vacuum-ejector motive LP steam hand valve.
Motive drives the 324F001 ejector pull; pull scales linearly with motive, anchored so at the design
stroke the live pull == R324_F001_EJPULL_DES bit-exact -> Stage-1 vacuum unchanged at steady state.
Red before edit (HIC_329605 absent), green after.  Run: cd backend && python ../scratchpad/probe_hic9605.py
"""
import sys, os
BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, BACKEND); os.chdir(BACKEND)
import main

telem = main.step_sim(0.1)                                   # tick 1 = design point
e001  = telem["EVAP_324"]["E001"]
hic   = e001["HIC_329605"]
hv    = e001["HV_329605"]
mot   = e001["motive_kgh"]
P0    = e001["PT_324202"]                                    # separator vacuum (bar a)
mdes  = main.R324_F002_MOTIVE_DES
sp    = main.R324_F001_P_BARA

print(f"R324_F002_MOTIVE_DES  = {mdes:.1f} kg/h")
print(f"HIC_329605 / HV_329605= {hic} / {hv} %   (design stroke {main.R324_HIC9605_DES_PCT})")
print(f"motive_kgh (live)     = {mot} kg/h   (must == {mdes:.0f} at design)")
print(f"PT_324202 (vacuum)    = {P0} bar a   (SP {sp})")

# --- design bit-exact: settle 200 s at design stroke, vacuum must hold at SP ------
for _ in range(2000):
    telem = main.step_sim(0.1)
P_des = telem["EVAP_324"]["E001"]["PT_324202"]
print(f"PT_324202 after 200 s @design = {P_des} bar a   (must stay ~{sp})")

# --- operator action has an effect: throttle motive to 25 %, pull drops, P rises ---
main.handle_cmd({"type": "hic9605_set", "op": 25.0})
for _ in range(2000):
    telem = main.step_sim(0.1)
e001b = telem["EVAP_324"]["E001"]
P_lo  = e001b["PT_324202"]
mot_lo= e001b["motive_kgh"]
print(f"after throttle to 25 %: motive={mot_lo} kg/h, PT_324202={P_lo} bar a (vacuum degrades -> P up)")

bad = 0
if abs(mot - mdes) > 0.5:
    print("FAIL: design motive != MOTIVE_DES"); bad += 1
if abs(hv - hic) > 1e-6:
    print("FAIL: HV does not track HIC 1:1"); bad += 1
if abs(P_des - sp) > 0.01:
    print("FAIL: Stage-1 vacuum drifted off SP at design stroke (pull not bit-exact)"); bad += 1
if not (mot_lo < mdes*0.6):
    print("FAIL: throttling HIC did not cut motive flow"); bad += 1
if not (P_lo > P_des + 0.005):
    print("FAIL: cutting motive did not degrade vacuum (P should rise)"); bad += 1

print(f"\nFAILURES: {bad}")
sys.exit(1 if bad else 0)
