r"""_probe_hv604_overflow.py -- HV-322604 opening vs HP-scrubber overflow temp (TT-322002 -> 322F001).

Multi-point sweep of HIC-322604 across [0..100] %.  Settles each point and records the
overflow-stream temperature to the HP ejector 322F001, plus the pressure/vent chain that
drives it.  Confirms (a) closing has the OPPOSITE sign to opening, and (b) the relation is
RECTIFIED about the design opening (theta_des = 50 %): below design the vent deficit lifts
PT-329201 and heats the overflow; at/above design max(1-vent_frac,0)=0 -> flat.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import main

DT          = 0.1
SETTLE_MIN  = float(os.environ.get("SETTLE_MIN", "20"))
SETTLE_TICK = int(SETTLE_MIN * 60.0 / DT)
THETAS      = [0.0, 10.0, 25.0, 40.0, 50.0, 60.0, 80.0, 100.0]

# leaves of interest (dotted paths into the flattened packet)
KEYS = {
    "TT-322002 overflow->322F001": "SCRUB_322E003.TT_322002",
    "EJ TI-322002 (ejector side)": "EJ_322F001.TI_322002",
    "PT-329201 synth P (bara)":    "SCRUB_322E003.P_overflow",
    "vent_frac":                   "SCRUB_322E003.vent_frac",
    "Q_ccw (kW)":                  "SCRUB_322E003.ccw.Q_ccw_kW",
    "TT-322011 top off-gas (STALL)": "SCRUB_322E003.TT_322011",
    "TT-322011_lp post-valve JT":  "SCRUB_322E003.TT_322011_lp",
}


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


def settle(theta):
    main.state = main.State()
    s = main.state
    tank_pin = s.tank_level_frac
    pkt = None
    for _ in range(SETTLE_TICK):
        pkt = main.step_sim(DT)
        s.tank_level_frac = tank_pin
        s.HIC_322604 = theta          # force valve opening every tick
    return flatten(pkt)


def main_run():
    print(f"HV-322604 sweep | settle {SETTLE_MIN:.0f} min/pt, dt={DT}s | theta_des=50%")
    rows = []
    for th in THETAS:
        f = settle(th)
        rows.append((th, {lab: f.get(key, float("nan")) for lab, key in KEYS.items()}))

    labels = list(KEYS.keys())
    hdr = "  theta% | " + " | ".join(f"{l[:14]:>14s}" for l in labels)
    print("\n" + hdr)
    print("  " + "-" * (len(hdr) - 2))
    for th, vals in rows:
        cells = " | ".join(f"{vals[l]:14.3f}" for l in labels)
        print(f"  {th:6.0f} | {cells}")

    # delta vs design (theta=50)
    base = dict(rows[[r[0] for r in rows].index(50.0)][1])
    print("\n  delta vs design (theta=50):")
    print(f"  {'theta%':>7s} | {'dTT-322002':>12s} | {'dPT-329201':>12s} | {'dvent_frac':>12s}")
    for th, vals in rows:
        print(f"  {th:7.0f} | "
              f"{vals['TT-322002 overflow->322F001']-base['TT-322002 overflow->322F001']:12.3f} | "
              f"{vals['PT-329201 synth P (bara)']-base['PT-329201 synth P (bara)']:12.3f} | "
              f"{vals['vent_frac']-base['vent_frac']:12.4f}")


if __name__ == "__main__":
    main_run()
