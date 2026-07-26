"""READ-ONLY: is the w_f010 motion a SETTLING TRANSIENT or an unbounded secular RAMP?
Least-squares slope in successive windows; if the slope is constant the motion is a ramp, if it
decays geometrically it is an exponential with the implied time constant.  Pure arithmetic on the
recorded JSON."""
import json, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "probe_wf_settle.json")
rows = json.load(open(path, encoding="utf-8"))
print(os.path.basename(path), len(rows), "samples,", rows[-1]["t_s"] / 3600.0, "h")


def slope(key, t0, t1):
    xs = [(r["t_s"] / 3600.0, r[key] * 100.0) for r in rows if t0 <= r["t_s"] / 3600.0 <= t1]
    n = len(xs)
    if n < 3:
        return float("nan")
    mx = sum(x for x, _ in xs) / n
    my = sum(y for _, y in xs) / n
    num = sum((x - mx) * (y - my) for x, y in xs)
    den = sum((x - mx) ** 2 for x, _ in xs)
    return num / den


tmax = rows[-1]["t_s"] / 3600.0
wins = [(0.5, 1.5), (1.5, 2.5), (2.5, 3.5), (3.5, 4.5), (4.5, 5.5)]
wins += [(w0, w1) for w0, w1 in ((5.5, 6.5), (6.5, 8.5), (8.5, 10.5), (10.5, 13.9)) if w1 <= tmax]
print(f"\n{'window (h)':>14} {'w_f010 pp/h':>14} {'w_f004 pp/h':>14}")
for a, b in wins:
    print(f"  {a:5.1f}-{b:5.1f}   {slope('wf010', a, b):+14.8f} {slope('wf004', a, b):+14.8f}")

# geometric decay of the slope -> implied exponential time constant
s1, s2 = slope("wf010", 0.5, 1.5), slope("wf010", min(4.5, tmax - 1), min(5.5, tmax))
mid1, mid2 = 1.0, (min(4.5, tmax - 1) + min(5.5, tmax)) / 2.0
if s1 and s2 and s1 * s2 > 0 and abs(s1) != abs(s2):
    tau = (mid2 - mid1) / math.log(abs(s1 / s2))
    print(f"\nslope decayed {abs(s1):.8f} -> {abs(s2):.8f} pp/h between t={mid1} h and t={mid2} h")
    print(f"  implied exponential time constant tau = {tau:.0f} h ({tau/24:.0f} days)")
    print(f"  implied remaining excursion = slope*tau = {abs(s2)*tau:.3f} pp  "
          f"(EXTRAPOLATION FROM 6 h OF CURVATURE -- treat as unknown, not a measurement)")

print("\nspecies of w_f010 (mass %), first vs last sample:")
for k in ("wf010", "wf010_h2o", "wf010_biu", "wf010_nh3", "wf010_co2", "wf010_hcho"):
    a, b = rows[0][k] * 100.0, rows[-1][k] * 100.0
    print(f"  {k:12s} {a:12.7f} -> {b:12.7f}   ({b-a:+.7f} pp, {(b-a)/tmax:+.7f} pp/h)")
print(f"\nM_I  {rows[0]['M_I']:.1f} -> {rows[-1]['M_I']:.1f} kg   "
      f"m317 {rows[0]['m317']:.0f} -> {rows[-1]['m317']:.0f} kg/h   "
      f"T010 {rows[0]['T010']} -> {rows[-1]['T010']} C")
