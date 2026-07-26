import os, sys, time, json, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
t0 = time.perf_counter()
import main
t_import = time.perf_counter() - t0
s = main.state if hasattr(main, "state") else main.STATE
print("import_s = %.3f" % t_import)

# warm
for _ in range(50):
    pkt = main.step_sim(0.1)

N = 2000
ts = []
for _ in range(N):
    a = time.perf_counter()
    pkt = main.step_sim(0.1)
    ts.append(time.perf_counter() - a)
ts.sort()
print("tick_ms  mean=%.3f  p50=%.3f  p95=%.3f  p99=%.3f  max=%.3f"
      % (1000*sum(ts)/N, 1000*ts[N//2], 1000*ts[int(.95*N)], 1000*ts[int(.99*N)], 1000*ts[-1]))
print("ticks_per_real_sec_budget @DT=0.1 -> need 10/s ; FAST x60 -> need 120 substeps/s")
print("max sustainable ticks/s = %.0f" % (1.0/(sum(ts)/N)))

msg = json.dumps(pkt)
print("packet_bytes = %d  (%.1f KB)" % (len(msg.encode()), len(msg.encode())/1024))
print("top-level keys = %d" % len(pkt))
# byte cost per key
sizes = sorted(((len(json.dumps({k: v}).encode()), k) for k, v in pkt.items()), reverse=True)
print("top 15 keys by bytes:")
for b, k in sizes[:15]:
    print("   %8d  %s" % (b, k))
# how many are floats with full repr
def count(o):
    if isinstance(o, dict): return sum(count(v) for v in o.values())
    if isinstance(o, list): return sum(count(v) for v in o)
    return 1
print("scalar leaf count = %d" % count(pkt))
# rounding experiment
def rnd(o, n=4):
    if isinstance(o, dict): return {k: rnd(v, n) for k, v in o.items()}
    if isinstance(o, list): return [rnd(v, n) for v in o]
    if isinstance(o, float): return round(o, n)
    return o
m4 = json.dumps(rnd(pkt, 4))
print("packet_bytes rounded-4dp = %d  (-%.1f%%)" % (len(m4.encode()), 100*(1-len(m4.encode())/len(msg.encode()))))
print("push rate 10 Hz -> %.1f KB/s raw, %.1f KB/s rounded"
      % (10*len(msg.encode())/1024, 10*len(m4.encode())/1024))

# delta payload: how many leaves actually change per tick?
p1 = main.step_sim(0.1)
import copy
a = json.loads(json.dumps(p1)); b = json.loads(json.dumps(main.step_sim(0.1)))
def flat(o, pre=""):
    out = {}
    if isinstance(o, dict):
        for k, v in o.items(): out.update(flat(v, pre+"/"+str(k)))
    elif isinstance(o, list):
        for i, v in enumerate(o): out.update(flat(v, pre+"/"+str(i)))
    else: out[pre] = o
    return out
fa, fb = flat(a), flat(b)
chg = {k: fb[k] for k in fb if fa.get(k) != fb[k]}
print("leaves changed in one 0.1 s tick: %d / %d (%.1f%%)" % (len(chg), len(fb), 100*len(chg)/len(fb)))
print("delta-json bytes = %d" % len(json.dumps(chg).encode()))
# steady-state (no operator action) change count after settle
for _ in range(500): main.step_sim(0.1)
c = flat(json.loads(json.dumps(main.step_sim(0.1))))
d = flat(json.loads(json.dumps(main.step_sim(0.1))))
chg2 = {k: d[k] for k in d if c.get(k) != d[k]}
print("settled: leaves changed per tick = %d (%.1f%%), delta bytes=%d"
      % (len(chg2), 100*len(chg2)/len(d), len(json.dumps(chg2).encode())))
