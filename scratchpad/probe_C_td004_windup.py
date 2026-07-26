"""AGENT C: is the TIC-328008 -> FIC-328404 'cascade' actually CLOSED-LOOP?

Test 1: does the manipulated variable (m_775 reflux) influence the master's PV at all?
Test 2: hold the SP step for 3 h and see whether the master settles or winds to its stop.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state if hasattr(main, "state") else main.STATE
DT = 0.1
tic, fic = s.TIC_328008, s.FIC_328404

# --- Test 1: force the slave to two very different strokes in MAN, watch master PV
for stroke in (10.0, 90.0):
    fic["mode"] = "MAN"; fic["op"] = stroke
    for _ in range(6000): main.step_sim(DT)   # 600 s
    print(f"MAN FV-328404 = {stroke:5.1f} %  -> m775 pv {fic['pv']:.4f} m3/h,"
          f"  TIC-328008 pv = {tic['pv']:.6f} mol%,  D001 P = {s.a328_d001_P:.5f} bar")

# --- restore
fic["mode"] = "CAS"; fic["op"] = main.R328_D001_FIC404_OP_DES
for _ in range(6000): main.step_sim(DT)
print(f"\nrestored: FV {fic['op']:.3f} %  TIC pv {tic['pv']:.6f}  op {tic['op']:.2f} kg/h  D001P {s.a328_d001_P:.5f}")

# --- Test 2: -5 % SP step, 3 hours
sp0 = tic["sp"]; tic["sp"] = sp0 * 0.95
print(f"\nSP {sp0:.4f} -> {tic['sp']:.4f} mol%   op_hi = {tic['op_hi']}")
print(f"{'t_s':>8} {'TIC_op_kgh':>12} {'FV404_%':>10} {'FIC404_sp':>11} {'FIC404_pv':>11} {'m775_kgh':>10}")
marks = {int(t/DT) for t in (60,300,900,1800,3600,5400,7200,9000,10800)}
for k in range(1, int(10800/DT)+1):
    main.step_sim(DT)
    if k in marks:
        print(f"{k*DT:8.0f} {tic['op']:12.2f} {fic['op']:10.3f} {fic['sp']:11.5f} {fic['pv']:11.5f}"
              f" {main.R328_D001_M775_DES*(fic['op']/main.R328_D001_FIC404_OP_DES):10.1f}")
print("\nSATURATED AT op_hi" if abs(tic['op']-tic['op_hi'])<1e-6 else "\nnot saturated")
