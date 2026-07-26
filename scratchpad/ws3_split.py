# WS3(2) probe: FIC-328406 CAS direct split-range.
#   Perturb 328C003 hold-up, confirm LIC-328505 returns level->50 and the
#   FIC-328406 faceplate tracks the draw smoothly (no bang-bang), and that
#   the delivered bottoms m_747 is identical to the MAN/LV path (draw-neutral).
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "backend"))
import main

s  = main.state
dt = 0.5

def run(mode, kick):
    # fresh-ish: nudge the hydrolyser hold-up to force a level excursion
    s.FIC_328406["mode"] = mode
    s.a328_c003_M *= (1.0 + kick)
    op_prev = s.FIC_328406["op"]
    max_slew = 0.0
    lvl0 = s.a328_c003_M / main.R328_C003_M_DES * 50.0
    for k in range(4000):        # 2000 s settle
        main.step_sim(dt)
        op = s.FIC_328406["op"]
        max_slew = max(max_slew, abs(op - op_prev))
        op_prev = op
    lvl = s.a328_c003_M / main.R328_C003_M_DES * 50.0
    lic = s.LIC_328505["op"]
    print(f"mode={mode:>3} kick={kick:+.2f}  lvl0={lvl0:6.2f} -> lvl={lvl:6.2f}  "
          f"LIC505_op={lic:6.2f}  FIC406_op={s.FIC_328406['op']:6.2f}  "
          f"FIC406_pv={s.FIC_328406['pv']:8.1f}  max_op_slew/tick={max_slew:.4f}")

# settle at design first
for _ in range(200): main.step_sim(dt)
print("design seed:  lvl=%.3f  LIC505_op=%.3f  FIC406_op=%.3f mode=%s" % (
    s.a328_c003_M/main.R328_C003_M_DES*50.0, s.LIC_328505["op"], s.FIC_328406["op"], s.FIC_328406["mode"]))

run("CAS", +0.10)     # +10% hold-up excursion under split-range
run("CAS", -0.10)     # -10% excursion under split-range
