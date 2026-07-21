"""TD-004 probe: with FIC-328404 on CAS, does TIC-328008 actually stroke FV-328404?

TIC-328008's PV is the inferential H2O content of the gas leaving 328C002 to 328E004 (PFD 737).
Its output is the 775 carbamate-reflux demand in kg/h, handed to FIC-328404 as cas_sp; _fic_flow
divides by RHO_775 so the slave runs in m3/h.  act=-1 (DIRECT): wetter offgas -> more reflux.

Steps the master's SP DOWN 5 % (demanding drier offgas) and reports where FV-328404 travels.

Usage:  python probe_td004_cascade.py [seconds]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)

import main  # noqa: E402

SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 900.0
DT = 0.1

s = main.state if hasattr(main, "state") else main.STATE
tic = s.TIC_328008
fic = s.FIC_328404

print(f"FIC-328404 mode   = {fic['mode']}   (must be CAS for the cascade to act)")
print(f"TIC-328008 sp/pv  = {tic['sp']:.4f} / {tic['pv']:.4f} mol%")
print(f"TIC-328008 op     = {tic['op']:.2f} kg/h   (= 775 reflux demand)")
print(f"FIC-328404 sp     = {fic['sp']:.6f} m3/h")
print(f"FV-328404 op      = {fic['op']:.4f} %   (start)")

op0 = fic["op"]
sp0 = tic["sp"]
tic["sp"] = sp0 * 0.95                       # demand 5 % drier offgas
print(f"\n-> TIC-328008 sp stepped {sp0:.4f} -> {tic['sp']:.4f} mol% (-5 %)\n")

marks = {int(t / DT) for t in (30, 120, 300, 600, SECONDS)}
for k in range(1, int(SECONDS / DT) + 1):
    main.step_sim(DT)
    if k in marks:
        print(f"  t={k * DT:7.1f}s   FV-328404 op = {fic['op']:8.4f} %"
              f"   (moved {fic['op'] - op0:+8.4f})"
              f"   TIC op = {tic['op']:9.2f} kg/h"
              f"   FIC sp = {fic['sp']:.5f} m3/h")

moved = fic["op"] - op0
print(f"\nTOTAL FV-328404 movement over {SECONDS:.0f}s: {moved:+.4f} %")
print("VERDICT:", "cascade is LIVE" if abs(moved) > 0.1 else "CASCADE INERT")
