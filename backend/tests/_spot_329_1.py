"""§6.3 spot-check for screen-329-1 binds + §4 PIC handler bit-exactness. External driver, no engine edits."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main

def settle(n=6000, dt=0.5):
    snap = None
    for _ in range(n):
        snap = main.step_sim(dt)
    return snap

def gp(d, path):
    for k in path.split("."):
        d = d[k]
    return d

snap = settle()
checks = [
    ("STRIP_322E001.steam.TI_shell", 211.6, 0.5),
    ("HPCC_322E002.TT_329001",       146.3, 0.5),
    ("STEAM_SYSTEM.SUPPLY_25BAR.P_bara", 25.00, 0.05),
    ("STEAM_SYSTEM.MP.P_bara",        19.70, 0.05),
    ("STEAM_SYSTEM.DRUM_9BAR.P_bara",  9.00, 0.05),
    ("STEAM_SYSTEM.LP.P_bara",         4.40, 0.05),
    ("STEAM_SYSTEM.PIC_329205.pv",     9.00, 0.05),
    ("STEAM_SYSTEM.PIC_329205.sp",     9.00, 0.001),
    ("STEAM_SYSTEM.PIC_329207.pv",     4.40, 0.05),
    ("STEAM_SYSTEM.PIC_329207.sp",     4.40, 0.001),
]
allok = True
print("=== screen-329-1 bind spot-check (design steady state) ===")
for path, exp, tol in checks:
    v = gp(snap, path)
    ok = abs(v - exp) <= tol
    allok &= ok
    print(f"  {'PASS' if ok else 'FAIL'}  {path:38s} = {v:8.3f}  (exp {exp})")

# default mode must be AUTO on both PICs
for path, exp in [("STEAM_SYSTEM.PIC_329205.mode","AUTO"),("STEAM_SYSTEM.PIC_329207.mode","AUTO")]:
    v = gp(snap, path); ok = (v==exp); allok &= ok
    print(f"  {'PASS' if ok else 'FAIL'}  {path:38s} = {v}  (exp {exp})")

# --- §4 bit-exactness: MAN freeze then bumpless AUTO return holds design fixed point ---
p9_a, plp_a = gp(snap,"STEAM_SYSTEM.DRUM_9BAR.P_bara"), gp(snap,"STEAM_SYSTEM.LP.P_bara")
main.state.steam.pic205_mode = "MAN"; main.state.steam.pic207_mode = "MAN"
for _ in range(1200): main.step_sim(0.5)
main.state.steam.pic205_mode = "AUTO"; main.state.steam.pic207_mode = "AUTO"
snap2 = settle(2000)
p9_b, plp_b = gp(snap2,"STEAM_SYSTEM.DRUM_9BAR.P_bara"), gp(snap2,"STEAM_SYSTEM.LP.P_bara")
d9, dlp = abs(p9_b-p9_a), abs(plp_b-plp_a)
okr = d9 <= 0.05 and dlp <= 0.05
allok &= okr
print(f"  {'PASS' if okr else 'FAIL'}  MAN->AUTO bumpless return: dP9={d9:.3e} dP_LP={dlp:.3e}")

print("OVERALL:", "PASS" if allok else "FAIL")
sys.exit(0 if allok else 1)
