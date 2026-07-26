# WS2 probe: HV-329605 motive step -> PIC-324202 false-air transient.
# Compares instant coupling (tau->0, old) vs establishment lag (tau=60, new).
# Run twice:  WS2_TAU=0.0001 python scratchpad/ws2_pull.py   (baseline)
#             WS2_TAU=60     python scratchpad/ws2_pull.py   (new)
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "backend"))
import main

tau = float(os.environ.get("WS2_TAU", "60"))
main.R324_F002_PULL_TAU_S = tau

s = main.state
dt = 0.5
op0 = s.PIC_324202["op"]
p0  = s.r324_f001_P

# motive step on the HV-329605 hand valve (default 50 -> 55 %)
s.HIC_329605 = float(os.environ.get("WS2_HIC", "55"))

op_prev = op0
max_dev  = 0.0      # peak |op - op0|  (how far the false-air loop swings)
max_slew = 0.0      # peak |op step per tick|  (how aggressive)
p_min    = p0
for k in range(1200):            # 600 s
    main.step_sim(dt)
    op = s.PIC_324202["op"]
    max_dev  = max(max_dev,  abs(op - op0))
    max_slew = max(max_slew, abs(op - op_prev))
    p_min    = min(p_min, s.r324_f001_P)
    op_prev = op
op_end = s.PIC_324202["op"]
print(f"tau={tau:>7}  op0={op0:.3f}  op_end={op_end:.3f}  "
      f"max_dev={max_dev:.4f}  max_slew_per_tick={max_slew:.5f}  "
      f"p0={p0:.4f} p_min={p_min:.4f}  pull_end={s.r324_f002_pull:.1f}")
