"""Functional test of the two hydraulic couplings.
  1. LV-322501 open  -> PT-323201 (r323_c003_P) up  AND PT-323203 (r3232_e011_P) up
  2. LV-323501 open  -> 323F004 pressure (r323_f004_P) up AND PT-323203 up
"""
import os, sys
BACKEND = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main

s = main.state
def settle(n=600):
    for _ in range(n): main.step_sim(1.0)

settle(300)
base = (s.r323_c003_P, s.r3232_e011_P, s.r323_f004_P)
print(f"baseline   PT-323201={base[0]:.4f}  PT-323203={base[1]:.4f}  F004_P={base[2]:.4f}")

# --- Coupling 1: open LV-322501 (LIC-322501 manual, 46.1 -> 85 %) ---
s.LIC_322501["mode"] = "MAN"; s.LIC_322501["op"] = 85.0
settle(600)
c1 = (s.r323_c003_P, s.r3232_e011_P, s.r323_f004_P)
print(f"LV-322501^ PT-323201={c1[0]:.4f}  PT-323203={c1[1]:.4f}  F004_P={c1[2]:.4f}")
print(f"  dPT-323201={c1[0]-base[0]:+.4f}  dPT-323203={c1[1]-base[1]:+.4f}")

# reset LV-322501, resettle
s.LIC_322501["mode"] = "MAN"; s.LIC_322501["op"] = main.LV322501_OPEN_DES
settle(600)
mid = (s.r323_c003_P, s.r3232_e011_P, s.r323_f004_P)
print(f"reset      PT-323201={mid[0]:.4f}  PT-323203={mid[1]:.4f}  F004_P={mid[2]:.4f}")

# --- Coupling 2: open LV-323501 (LIC-323501 manual, up) ---
s.LIC_323501["mode"] = "MAN"; s.LIC_323501["op"] = 90.0
settle(600)
c2 = (s.r323_c003_P, s.r3232_e011_P, s.r323_f004_P)
print(f"LV-323501^ PT-323201={c2[0]:.4f}  PT-323203={c2[1]:.4f}  F004_P={c2[2]:.4f}")
print(f"  dF004_P={c2[2]-mid[2]:+.4f}  dPT-323203={c2[1]-mid[1]:+.4f}")
