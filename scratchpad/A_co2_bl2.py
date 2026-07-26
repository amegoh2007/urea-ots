"""AGENT A probe 2b -- clean CO2 BL transfer function with PIC-322203 in MAN (no windup)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa
s = main.state if hasattr(main, "state") else main.STATE
s.PIC_322203["mode"] = "MAN"; s.PIC_322203["op"] = 0.0; s.HIC_322203 = 0.0
DT = 0.5
print(f"{'p_syn':>8} {'P_line':>9} {'feed t/h':>10} {'vent t/h':>10} {'Load %':>8}")
for psyn in (100.0, 120.0, 135.0, 140.7, 143.0, 144.2, 146.0, 147.7, 149.0, 155.0):
    for _ in range(4):
        s.p_syn_bara = psyn
        t = main.step_sim(DT)
    c = t["CO2_FEED"]
    print(f"{psyn:8.1f} {c['PIC_322203']:9.2f} {c['FY_322403']:10.3f} {c['vent_th']:10.3f} {c['Load']:8.2f}")

print("\n--- vent authority: HIC-322203 sweep at design p_syn ---")
s.p_syn_bara = 140.7
for hic in (0.0, 5.0, 10.0, 14.0, 20.0, 50.0, 100.0):
    s.HIC_322203 = hic
    for _ in range(4):
        s.p_syn_bara = 140.7
        t = main.step_sim(DT)
    c = t["CO2_FEED"]
    print(f"  HIC={hic:6.1f} % -> P_line={c['PIC_322203']:8.2f}  feed={c['FY_322403']:8.3f}  "
          f"vent={c['vent_th']:8.3f}  Load={c['Load']:7.2f}")
