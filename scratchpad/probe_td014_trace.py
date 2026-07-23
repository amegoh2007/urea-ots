"""TD-014 -- localise the -0.0067 pp/h urea ramp by walking the chain the user described.

Chain (user's stream map, 2026-07-23):
    322R001 overflow (207) -> 322E001 -> bottoms (208) -> LV-322501
      -> 323C003 (301 liq / 311 gas), recirc 313 -> 323E002 -> 302 gas back / 314 liq
      -> LV-323501 -> 323F004 -> 319 -> 323E010 -> 323F010 -> 317 -> 323D002

A ramp that never arrests cannot originate in a stage whose residence time is minutes; C003/F004/
F010 have tau of 2/3/4 min.  So the ramp must be RIDING IN on the feed.  This probe reads the
urea/water fraction at every node of the chain and reports the per-node slope.  The first node in
flow order with a non-zero slope is the origin.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main as M  # noqa: E402

DT = float(os.environ.get("PROBE_DT", "1.0"))
HOURS = float(os.environ.get("PROBE_H", "6.0"))
SAMPLE_MIN = 15.0

s = M.state


def sample(tel):
    bot = tel["STRIP_322E001"]["bot_mass_pct"]
    return {
        "react_L_feed": s.react_L_feed,
        "react_W_feed": s.react_W_feed,
        "react_L_rec": s.react_L_rec,
        "react_W_rec": s.react_W_rec,
        "react_conv": s.react_conv_fac,
        "react_T_ov": s.react_T_overflow,
        "s208_urea": bot.get("Urea", 0.0),
        "s208_h2o": bot.get("H2O", 0.0),
        "s208_nh3": bot.get("NH3", 0.0),
        "s208_co2": bot.get("CO2", 0.0),
        "c003_urea": 100.0 * s.w_c003["Urea"],
        "c003_h2o": 100.0 * s.w_c003["H2O"],
        "f004_urea": 100.0 * s.w_f004["Urea"],
        "f010_urea": 100.0 * s.w_f010["Urea"],
        "f010_h2o": 100.0 * s.w_f010["H2O"],
        "f010_biu": 100.0 * s.w_f010["Biuret"],
        "d002_urea": 100.0 * s.w_d002["Urea"],
    }


KEYS = None
rows = []
t0 = time.time()
tel = M.step_sim(DT)
n_per_sample = int(SAMPLE_MIN * 60.0 / DT)
n_total = int(HOURS * 3600.0 / DT)
done = 0
while done < n_total:
    for _ in range(n_per_sample):
        tel = M.step_sim(DT)
    done += n_per_sample
    r = sample(tel)
    r["t_h"] = done * DT / 3600.0
    rows.append(r)
    if KEYS is None:
        KEYS = [k for k in r if k != "t_h"]

print("dt = %.2f s   horizon = %.1f h   wall = %.1f s" % (DT, HOURS, time.time() - t0))
print()

# print the trajectory of the headline signals
print("%6s %10s %10s %10s %10s %10s" % ("t_h", "s208_ure", "c003_ure", "f004_ure", "f010_ure", "f010_h2o"))
for r in rows:
    print("%6.2f %10.4f %10.4f %10.4f %10.4f %10.4f"
          % (r["t_h"], r["s208_urea"], r["c003_urea"], r["f004_urea"], r["f010_urea"], r["f010_h2o"]))
print()


def slope(key, lo_h, hi_h):
    pts = [(r["t_h"], r[key]) for r in rows if lo_h <= r["t_h"] <= hi_h]
    if len(pts) < 3:
        return 0.0
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    num = sum((p[0] - mx) * (p[1] - my) for p in pts)
    den = sum((p[0] - mx) ** 2 for p in pts)
    return num / den if den else 0.0


half = HOURS / 2.0
print("per-node least-squares slope (units of the signal per HOUR)")
print("%-16s %14s %14s %10s" % ("signal", "early half", "late half", "value@end"))
for k in KEYS:
    a = slope(k, 0.25, half)
    b = slope(k, half, HOURS)
    print("%-16s %14.6g %14.6g %10.5f" % (k, a, b, rows[-1][k]))
