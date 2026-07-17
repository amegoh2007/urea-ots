"""LIC-323503 / 323D011 level-loop acceptance test.

Two gates, both of which the REJECTED series architecture failed or could not see:

  1. Design anchor (tick 1, raw float).  The boot seed IS the design point, so the first
     tick must leave every state bitwise untouched.  Read tick 1, not a settled value:
     the loop's natural period is ~1257 s, so any shorter settle reads a transient and
     an `exact False` there proves nothing either way.

  2. Steady-state authority (12,000 s step test).  Drain 10 % of the tank; the level MUST
     return to SP and LIC-323503's op MUST come off the rail.  Modelling LV-323503 as a
     series derate on both 718 legs put three integrators on two degrees of freedom -- the
     two AUTO FICs rejected the header stroke by integral action, so LIC-323503 wound up to
     op_hi=100 and the level parked at 51.05 % indefinitely.  This gate is what caught it;
     the design-anchor gate above could not, because the derate was inert at design.

Run:  cd backend && python ../scratchpad/dyn503.py
"""
import sys, os
BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, BACKEND); os.chdir(BACKEND)
import main

s = main.state
bad = 0

# ---- gate 1: design anchor at tick 1, raw float ----------------------------------
print("--- gate 1: design fixed point, tick 1 (raw float) ---")
main.step_sim(0.1)
checks = [
    ("M_D011   ", s.r3232_e011_M,       main.R3232_D011_M_DES),
    ("LIC503 op", s.LIC_323503["op"],   main.R3232_LV503_OP_DES),
    ("FIC405 sp", s.FIC_323405["sp"],   main.R3232_M718A_DES),
    ("FIC405 op", s.FIC_323405["op"],   main.R3232_FIC405_OP_DES),
    ("FIC418 op", s.FIC_323418["op"],   main.R3232_FIC418_OP_DES),
]
for name, got, want in checks:
    ok = got == want
    bad += 0 if ok else 1
    print(f"{name} {got!r:24} | des {want!r:24} | exact {ok}")

# ---- gate 2: does LIC-323503 actually have authority? -----------------------------
print("\n--- gate 2: step test, M -= 10% , expect level back to 50.0 and op off the rail ---")
s.r3232_e011_M *= 0.9
t = 0.0
marks = {60.0: None, 600.0: None, 3000.0: None, 6000.0: None, 12000.0: None}
for _ in range(120000):          # 12000 s
    main.step_sim(0.1); t += 0.1
    for m in marks:
        if marks[m] is None and t >= m:
            marks[m] = (s.r3232_e011_M / main.R3232_D011_M_DES * main.R3232_D011_LVL_SP,
                        s.LIC_323503["op"], s.FIC_323405["op"], s.FIC_323418["op"])
for m in sorted(marks):
    lvl, op503, op405, op418 = marks[m]
    print(f"t={m:7.0f}s  lvl={lvl:8.4f}%  LIC503.op={op503:7.3f}  "
          f"FIC405.op={op405:7.3f}  FIC418.op={op418:7.3f}")

lvl_f, op503_f, _, _ = marks[12000.0]
if abs(lvl_f - main.R3232_D011_LVL_SP) > 0.01:
    print(f"FAIL: level parked at {lvl_f:.4f}%, never returned to SP"); bad += 1
if op503_f >= 99.9 or op503_f <= 0.1:
    print(f"FAIL: LIC-323503 saturated at op={op503_f:.3f} (no steady-state authority)"); bad += 1

print(f"\nFAILURES: {bad}")
sys.exit(1 if bad else 0)
