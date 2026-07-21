"""TD-003 probe: does moving the FFIC-329401 ratio SP actually move the FV-329401 opening?

Steps the ratio SP by +5 % and runs the engine, reporting how far FIC-329401's op (which is
exactly what the FV-329401 avalve overlay binds) travels.  Run before and after a Kc change.

Usage:  python probe_ffic_gain.py [seconds]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)

import main  # noqa: E402

SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 600.0
DT = 0.1

s = main.state if hasattr(main, "state") else main.STATE
ffic = s.FFIC_329401
fic = s.FIC_329401

print(f"Kc(FFIC-329401)   = {ffic['Kc']:.6g}")
print(f"ratio sp (design) = {ffic['sp']:.6f} T/M3")
print(f"FV-329401 op      = {fic['op']:.4f} %   (start)")
print(f"FIC-329401 sp     = {fic['sp']:.2f} kg/h (start)")

op0 = fic["op"]
sp0 = ffic["sp"]
ffic["sp"] = sp0 * 1.05                      # +5 % ratio setpoint step
print(f"\n-> ratio sp stepped {sp0:.6f} -> {ffic['sp']:.6f} T/M3 (+5 %)\n")

marks = {int(t / DT) for t in (10, 30, 60, 120, 300, SECONDS)}
for k in range(1, int(SECONDS / DT) + 1):
    main.step_sim(DT)
    if k in marks:
        print(f"  t={k * DT:7.1f}s   FV-329401 op = {fic['op']:8.4f} %"
              f"   (moved {fic['op'] - op0:+8.4f})"
              f"   FIC-329401 sp = {fic['sp']:9.2f} kg/h"
              f"   ratio pv = {ffic['pv']:.6f}")

moved = fic["op"] - op0
print(f"\nTOTAL FV-329401 movement over {SECONDS:.0f}s: {moved:+.4f} %")
print("VERDICT:", "master has authority" if abs(moved) > 0.5 else "MASTER IS INERT")
