r"""_probe_tt322010_322012.py -- transient of TT-322012 (ej T_C) & TT-322010 (hpcc T_prod) on pump trip.

Trips the running HP-NH3 pump (B) via mechanical fault, then logs both temperatures plus the
internal drivers each 5 s for 90 s.  Confirms WHERE the 0 deg C comes from before any fix:
  - TT-322012 = ejector discharge T_C  (suspected 0.0 no-flow sentinel, main.py:284)
  - TT-322010 = hpcc T_prod            (NTU quench -> t_shell as m_dot->0, main.py:770)
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


def find(flat, needle):
    return {k: v for k, v in flat.items() if needle in k}


main.state = main.State()
s = main.state
tank_pin = s.tank_level_frac

pkt = None
for _ in range(3000):           # 5 min settle
    pkt = main.step_sim(DT)
    s.tank_level_frac = tank_pin
flat = flatten(pkt)

# discover the exact dotted keys once
print("KEYS 322012:", list(find(flat, "322012").keys()))
print("KEYS 322010:", list(find(flat, "322010").keys()))
print("KEYS T_prod/T_feed/T_adb/m_dot:", list(find(flat, "T_prod").keys()),
      list(find(flat, "T_feed").keys()), list(find(flat, "T_adb").keys()),
      list(find(flat, "m_dot").keys()))
print("KEYS TI_shell/T_steam/P_bara:", list(find(flat, "TI_shell").keys()),
      list(find(flat, "T_steam").keys()))

K10 = next((k for k in flat if k.endswith("TT_322010")), None)
K12 = next((k for k in flat if k.endswith("TT_322012")), None)
KSH = next((k for k in flat if k.endswith("TI_shell")), None)
print(f"\nbaseline  TT-322010={flat.get(K10)}  TT-322012={flat.get(K12)}  "
      f"pumpB_on={s.pumpB['on']}")

# trip the running pump
main.handle_cmd({"type": "trigger_fault", "id": "B", "value": True})

print(f"\n{'t(s)':>6} | {'TT-322012':>10} | {'TT-322010':>10} | {'TI_shell':>9} | "
      f"{'pumpB_on':>8} | {'latch10':>7}")
print("-" * 70)
for i in range(901):            # 90 s
    pkt = main.step_sim(DT)
    s.tank_level_frac = tank_pin
    if i % 50 == 0:
        f = flatten(pkt)
        print(f"{i*DT:6.1f} | {f.get(K12, float('nan')):10.2f} | "
              f"{f.get(K10, float('nan')):10.2f} | {f.get(KSH, float('nan')):9.2f} | "
              f"{int(s.pumpB['on']):8d} | {int(s.trip_latched['21_10']):7d}")
