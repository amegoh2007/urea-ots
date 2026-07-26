import os, sys, time, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main

# ---- reactor holdup tau ----
M = sum(main.REACT_MASS_DES)
print("REACT_MASS_DES =", main.REACT_MASS_DES, " sum=%.1f kg" % M)
p = main.step_sim(0.1)
# find reactor outlet flow
r = p.get("REACT_322R001", {})
print("REACT keys:", list(r)[:30])
for k, v in r.items():
    if isinstance(v, (int, float)) and 1e4 < abs(v) < 1e6:
        print("   cand flow %s = %s -> tau = %.0f s" % (k, v, M/(v/3600.0)))

TAGS = [("REACT_322R001","T_out"),("REACT_322R001","conv"),("STRIP_322E001","T_bot"),
        ("HPCC_322E002","T"),("SCRUB_322E003","T")]
def probe(pk):
    out = []
    for grp, key in TAGS:
        v = pk.get(grp, {})
        out.append(float(v.get(key, float("nan"))) if isinstance(v, dict) else float("nan"))
    # plus a few generic scalars
    for grp in ("REACT_322R001","STRIP_322E001","RECIRC_323","EVAP_324"):
        d = pk.get(grp, {})
        if isinstance(d, dict):
            for k in sorted(d):
                if isinstance(d[k], (int, float)) and not isinstance(d[k], bool):
                    out.append(float(d[k]))
    return out

HORIZON = 900.0   # sim seconds
def run(dt, kick=True):
    main.state = main.State()
    main.step_sim(dt)
    if kick:
        main.state.HIC_322203 = 35.0
    n = int(HORIZON/dt)
    t0 = time.perf_counter()
    for _ in range(n):
        pk = main.step_sim(dt)
    return probe(pk), time.perf_counter()-t0, n

ref, tref, nref = run(0.01)
print("\nref dt=0.01: %d steps, %.2f s wall (%.1fx real-time)" % (nref, tref, HORIZON/tref))
print("%-8s %10s %10s %10s %8s" % ("dt", "wall_s", "xRT", "maxRelErr", "steps"))
for dt in (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0):
    try:
        v, w, n = run(dt)
        err = 0.0
        for a, b in zip(ref, v):
            if not (math.isfinite(a) and math.isfinite(b)):
                err = float("nan"); break
            d = abs(a-b)/max(abs(a), 1e-6)
            err = max(err, d)
        print("%-8s %10.2f %10.1f %10.3e %8d" % (dt, w, HORIZON/w, err, n))
    except Exception as e:
        print("%-8s BLEW UP: %s: %s" % (dt, type(e).__name__, e))

# ---- explicit stability check: any NaN/inf in packet at large dt? ----
for dt in (0.5, 1.0, 5.0, 20.0, 60.0):
    main.state = main.State(); main.state.HIC_322203 = 35.0
    bad = None
    for i in range(int(600/dt)):
        pk = main.step_sim(dt)
    def scan(o, pre=""):
        r = []
        if isinstance(o, dict):
            for k, v in o.items(): r += scan(v, pre+"/"+str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o): r += scan(v, pre+"/"+str(i))
        elif isinstance(o, float) and not math.isfinite(o): r.append(pre)
        return r
    nb = scan(pk)
    print("dt=%-5s non-finite leaves after 600 s: %d %s" % (dt, len(nb), nb[:4]))
