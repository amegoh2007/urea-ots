r"""_probe_tt322010_co2cut.py -- TT-322010 (hpcc T_prod) transient when CO2 feed is isolated.

Cuts CO2 to 322E001 (XV-322902 shut) and logs TT-322010 plus the NTU-quench drivers
(shell sat temp t_shell, LP-steam pressure/duty, tube throughput m_dot) to locate the
3 deg C collapse before any fix.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import main

DT = 0.1


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        elif isinstance(v, bool):
            out[key] = float(v)
        elif isinstance(v, (int, float)):
            out[key] = float(v)
    return out


main.state = main.State()
s = main.state
tank_pin = s.tank_level_frac

pkt = None
for _ in range(3000):
    pkt = main.step_sim(DT)
    s.tank_level_frac = tank_pin
flat = flatten(pkt)

print("HPCC subtree keys:", [k for k in flat if k.startswith("HPCC_322E002")])

K10  = next((k for k in flat if k.endswith("TT_322010")), None)
KSH  = next((k for k in flat if k == "HPCC_322E002.steam.TI_shell"), None)
KPLP = next((k for k in flat if k == "HPCC_322E002.steam.P_bara"), None)
KMD  = next((k for k in flat if k.endswith("m_dot")), None)
KDUTY= next((k for k in flat if k == "HPCC_322E002.steam.duty_kw"
             or k.endswith("duty_kw") and "HPCC" in k), None)
print(f"keys -> T_prod={K10} t_shell={KSH} P_LP={KPLP} m_dot={KMD} duty={KDUTY}\n")

print(f"baseline TT-322010={flat.get(K10)}  t_shell={flat.get(KSH)}  "
      f"P_LP={flat.get(KPLP)}  m_dot={flat.get(KMD)}")

s.XV_322902 = False          # CUT CO2 feed (isolation shut)

print(f"\n{'t(s)':>6} | {'TT-322010':>9} | {'t_shell':>8} | {'P_LP':>7} | {'m_dot':>10} | "
      f"{'duty_kw':>9} | {'F_CO2_th':>8} | {'pAon':>4} {'pBon':>4} {'lat214':>6}")
print("-" * 90)
for i in range(1801):        # 180 s
    pkt = main.step_sim(DT)
    s.tank_level_frac = tank_pin
    if i % 100 == 0:
        f = flatten(pkt)
        print(f"{i*DT:6.1f} | {f.get(K10, float('nan')):9.2f} | {f.get(KSH, float('nan')):8.2f} | "
              f"{f.get(KPLP, float('nan')):7.3f} | {f.get(KMD, float('nan')):10.1f} | "
              f"{f.get(KDUTY, float('nan')):9.1f} | {s.F_CO2_th:8.3f} | "
              f"{int(s.pumpA['on']):4d} {int(s.pumpB['on']):4d} {int(s.trip_latched['21_4']):6d}")
