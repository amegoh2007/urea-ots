"""READ-ONLY: faithful replay of the REVERTED fix at the real tick rate.

probe_wf_offline.py replayed it at the 60 s sample spacing, which UNDER-states the effect by 240x:
the (A - ref) term is added once PER TICK, so the walk rate scales with 1/dt.  Here w_f010(t) is
linearly interpolated from the recorded 6 h trajectory and the recursion is stepped at the test
harness's own dt (test_equation_audit_323_324.py DT = 0.25) and at dt = 0.5.

No backend import -- pure arithmetic on the recorded JSON, so this cannot perturb anything.
"""
import json, os, bisect
HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "probe_wf_settle.json"), encoding="utf-8"))
ts = [r["t_s"] for r in rows]
ws = [r["wf010"] for r in rows]
A = 0.80
SEED = rows[0]["wf010"]          # = W_S317['Urea'] = 0.8000162403296788
M = 67600.0                      # R323_D002_M_I_DES (holdup is flat to +-11 kg over the run)
MDOT = 92748.91822762709         # R323_M317_DES == R323_M324_DES


def w_in_at(t):
    if t <= ts[0]:
        return ws[0]
    if t >= ts[-1]:
        return ws[-1]
    i = bisect.bisect_right(ts, t) - 1
    f = (t - ts[i]) / (ts[i + 1] - ts[i])
    return ws[i] + f * (ws[i + 1] - ws[i])


def replay(dt, w_prev_at_capture, horizon_s):
    a = b = MDOT * dt / 3600.0
    tot = M + a - b
    lam = (M - b) / tot
    mu = 1.0 - lam
    ref = lam * w_prev_at_capture + mu * w_in_at(0.0)
    w = A
    marks = {}
    n = int(horizon_s / dt)
    for i in range(1, n + 1):
        t = i * dt
        w = A + (lam * w + mu * w_in_at(t)) - ref
        if abs(t - round(t)) < 1e-9 and int(round(t)) in (60, 300, 600, 900, 1200, 1800,
                                                          3600, 7200, 10800, 21540):
            marks[int(round(t))] = w
    return lam, mu, ref, marks


for dt in (0.25, 0.5):
    for label, wp in (("A: reference captured from the ALREADY-PINNED previous tick (0.800000)", A),
                      ("B: reference captured from the UNPINNED seed W_S317 (0.80001624)", SEED)):
        lam, mu, ref, marks = replay(dt, wp, 21540.0)
        print(f"\ndt={dt}   {label}")
        print(f"   lambda={lam:.12f}  mu={mu:.6e}  1/mu={1/mu:.1f}")
        print(f"   ref={ref!r}   A-ref={A-ref:+.6e}")
        for t in sorted(marks):
            print(f"     t={t:6d}s ({t/60.0:7.1f} min)   w_d002 = {marks[t]*100:9.4f} %"
                  f"    [w_f010 = {w_in_at(t)*100:.4f} %]")

print("\n--- reference: the UNPINNED tank on the same trajectory (no fix, no pin) ---")
for dt in (0.25,):
    a = b = MDOT * dt / 3600.0
    lam = (M - b) / (M + a - b)
    w = SEED
    for i in range(1, int(21540 / dt) + 1):
        w = lam * w + (1 - lam) * w_in_at(i * dt)
        t = i * dt
        if abs(t - round(t)) < 1e-9 and int(round(t)) in (600, 3600, 10800, 21540):
            print(f"   t={int(t):6d}s   unpinned w_d002 = {w*100:.4f} %   "
                  f"(w_f010 = {w_in_at(t)*100:.4f} %)")
