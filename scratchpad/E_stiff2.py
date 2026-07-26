import os, sys, time, math
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main

def flat(o, pre=""):
    out = {}
    if isinstance(o, dict):
        for k, v in o.items(): out.update(flat(v, pre+"/"+str(k)))
    elif isinstance(o, list):
        for i, v in enumerate(o): out.update(flat(v, pre+"/"+str(i)))
    elif isinstance(o, bool): pass
    elif isinstance(o, (int, float)): out[pre] = float(o)
    return out

HORIZON = 900.0
def run(dt):
    main.state = main.State()
    main.step_sim(dt)
    main.state.HIC_322203 = 35.0
    for _ in range(int(HORIZON/dt)):
        pk = main.step_sim(dt)
    return flat(pk)

ref = run(0.01)
keys = [k for k in ref if "wall" not in k.lower() and "time" not in k.lower()
        and abs(ref[k]) > 1e-6 and math.isfinite(ref[k])]
print("compared scalars:", len(keys))
print("%-6s %10s %12s %12s   %s" % ("dt","wall_s","maxRelErr","medRelErr","worst tag"))
for dt in (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0):
    t = time.perf_counter(); v = run(dt); w = time.perf_counter()-t
    errs = sorted((abs(v.get(k, float('nan'))-ref[k])/abs(ref[k]), k) for k in keys
                  if math.isfinite(v.get(k, float('nan'))))
    nonfin = sum(1 for k in keys if not math.isfinite(v.get(k, float('nan'))))
    med = errs[len(errs)//2][0]
    print("%-6s %10.2f %12.3e %12.3e   %s  (nonfinite=%d)" % (dt, w, errs[-1][0], med, errs[-1][1], nonfin))
