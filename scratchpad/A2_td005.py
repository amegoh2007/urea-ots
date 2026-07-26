"""AGENT A (2nd pass) -- TD-005 stream-741 recycle: does it CREATE MASS?

Hypotheses under test
  H1  m_741 is added to in_compI with no decrement anywhere -> the modelled envelope gains mass.
  H2  m_741 capacity (33724 kg/h) is INDEPENDENT of the live 739 bottoms it claims to come from,
      so with LIC-328504 shut (739 = 0) the recycle still delivers full flow = mass from nowhere.
  H3  m_741 is pure water (PFD 741 = 100 % H2O) but is multiplied by the Comp-I carbamate-formation
      exotherm LAM_I, which is a per-kg-of-total-inflow reaction heat -> fabricated exotherm.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa
s = main.state if hasattr(main, "state") else main.STATE
DT = 0.5

def settle(n):
    for _ in range(n):
        main.step_sim(DT)

def snap(tag):
    t = main.telemetry() if hasattr(main, "telemetry") else None
    print(f"[{tag}] MI={s.a328_d003_MI:12.1f} kg  TI={s.a328_d003_TI:7.3f} C  "
          f"C004_M={s.a328_c004_M:9.1f}  FIC406.op={s.FIC_328406['op']:6.2f}")
    return s.a328_d003_MI, s.a328_d003_TI

print("=== constants ===")
print("S741_CAP_KGH =", main.S741_CAP_KGH, " RHO_741 =", main.RHO_741_KGM3,
      " T741 =", main.A328_M741_T)
print("LAM_I =", main.A328_D003_LAM_I, " A328_CP =", main.A328_CP)
print("R328_C004_M739_DES =", main.R328_C004_M739_DES)

settle(600)          # 5 min settle
snap("baseline")
MI0 = s.a328_d003_MI

# ---------- H1/H2: open FIC-328406 to 100 % in MAN, LIC-328504 untouched -------------
s.FIC_328406["mode"] = "MAN"
s.FIC_328406["op"]   = 100.0
settle(20)
tel = main.step_sim(DT)
d = tel["u328_2"] if "u328_2" in tel else None
# find the 328406 telemetry block
def deep_find(o, key, path=""):
    out = []
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key: out.append((path + "/" + k, v))
            out += deep_find(v, key, path + "/" + k)
    elif isinstance(o, list):
        for i, v in enumerate(o): out += deep_find(v, key, f"{path}[{i}]")
    return out
print("\n--- telemetry hits for FIC_328406 / bot739 ---")
for k in ("FIC_328406", "bot739_th", "LI_328504"):
    for p, v in deep_find(tel, k):
        print(f"  {k:12s} {p} = {v}")

MI_a = s.a328_d003_MI
settle(1200)   # 10 min at full recycle
MI_b = s.a328_d003_MI
print(f"\nH1: Comp-I holdup {MI0:.1f} -> {MI_b:.1f} kg   dM = {MI_b-MI0:+.1f} kg")
print(f"    accumulation rate ~ {(MI_b-MI_a)/ (1200*DT) * 3600.0:+.1f} kg/h over the 10-min window")
print(f"    TI now {s.a328_d003_TI:.3f} C")

# ---------- H2: shut the source. LIC-328504 -> 0 %, so m_739 = 0 --------------
lic = s.LIC_328504
print("\n=== H2: shut LIC-328504 (m_739 -> 0) while 741 stays wide open ===")
lic["mode"] = "MAN"; lic["op"] = 0.0
settle(1200)
tel = main.step_sim(DT)
for k in ("bot739_th", "LI_328504", "FIC_328406"):
    for p, v in deep_find(tel, k):
        print(f"  {k:12s} {p} = {v}")
print(f"  C004 holdup = {s.a328_c004_M:.1f} kg (floor 1.0)   Comp-I MI = {s.a328_d003_MI:.1f} kg")
MI_c = s.a328_d003_MI
settle(1200)
print(f"  10 more min: MI {MI_c:.1f} -> {s.a328_d003_MI:.1f}  "
      f"({(s.a328_d003_MI-MI_c)/(1200*DT)*3600.0:+.1f} kg/h)  "
      f"C004_M={s.a328_c004_M:.1f}")

# ---------- H3: the fabricated exotherm ------------------------------------
m741 = main.S741_CAP_KGH
q_exo = m741 / 3600.0 * main.A328_D003_LAM_I               # kW of reaction heat applied to pure water
q_sens = m741 / 3600.0 * main.A328_CP * (main.A328_M741_T - 56.0)
print(f"\nH3: at full stroke m_741 = {m741:.0f} kg/h of PFD 100 %-H2O condensate")
print(f"    fabricated carbamate exotherm = {q_exo:+.1f} kW   (LAM_I x m_741)")
print(f"    legitimate sensible term      = {q_sens:+.1f} kW   (40 C vs TI 56 C)")
print(f"    net                            = {q_exo+q_sens:+.1f} kW")
