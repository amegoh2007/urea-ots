# WS3(2): prove CAS split-range is level-dynamics-neutral vs MAN, and non-banging.
#   m_747 = R328_C003_M747_DES*(lic505_op/50) in BOTH branches -> level ODE identical.
#   CAS only additionally mirrors the draw onto the FIC-328406 faceplate.
# Run: MODE=MAN python ws3_cmp.py ; MODE=CAS python ws3_cmp.py  (compare printed trace)
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "backend"))
import main
s, dt = main.state, 0.5
mode = os.environ.get("MODE", "CAS")

for _ in range(400): main.step_sim(dt)                 # settle at design
s.FIC_328406["mode"] = mode
s.a328_c003_M *= 1.10                                   # +10% hold-up excursion

op_prev = s.FIC_328406["op"]; max_slew = 0.0; bang = 0
trace = []
for k in range(8000):                                   # 4000 s
    main.step_sim(dt)
    op = s.FIC_328406["op"]
    d  = abs(op - op_prev)
    if k > 2 and d > 50.0: bang += 1                     # count post-entry hard swings
    max_slew = max(max_slew, d if k > 2 else 0.0)
    op_prev = op
    if k % 800 == 0:
        trace.append(s.a328_c003_M/main.R328_C003_M_DES*50.0)
lvl = s.a328_c003_M/main.R328_C003_M_DES*50.0
print(f"MODE={mode}  lvl_end={lvl:.4f}  LIC505_op={s.LIC_328505['op']:.4f}  "
      f"FIC406_op={s.FIC_328406['op']:.4f}  post-entry_bangs(>50/tick)={bang}  "
      f"max_slew(k>2)={max_slew:.4f}")
print("  lvl_trace:", " ".join(f"{x:.3f}" for x in trace))
