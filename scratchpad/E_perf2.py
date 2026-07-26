import os, sys, time, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state

# ---------- 1. FAST-mode budget ----------
for _ in range(20): main.step_sim(0.5)
N = 400; t = time.perf_counter()
for _ in range(N): main.step_sim(0.5)
big = (time.perf_counter() - t) / N
print("step_sim(0.5) mean_ms = %.3f" % (1000*big))
print("SIM_SPEED FAST=%s  STEP_CAP=%s  DT=%s" % (main.SIM_SPEED, main.STEP_CAP, main.DT))
sub = main.DT * main.SIM_SPEED["FAST"] / main.STEP_CAP
print("FAST: substeps per wall tick = %.1f -> CPU %.1f ms per %.0f ms wall  => %.2fx REAL-TIME BUDGET"
      % (sub, 1000*big*sub, 1000*main.DT, big*sub/main.DT))
print("SLOW: CPU %.2f ms per 100 ms wall => %.3fx budget" % (1000*big*1, big/main.DT))

# ---------- 2. transient delta ----------
def flat(o, pre=""):
    out = {}
    if isinstance(o, dict):
        for k, v in o.items(): out.update(flat(v, pre+"/"+str(k)))
    elif isinstance(o, list):
        for i, v in enumerate(o): out.update(flat(v, pre+"/"+str(i)))
    else: out[pre] = o
    return out

# kick a real transient: drop load / open a vent
try:
    main.handle_cmd({"type": "set_hic", "tag": "HIC-322203", "value": 40.0})
except Exception as e:
    try:
        s.HIC_322203 = 40.0
    except Exception as e2:
        print("kick failed", e, e2)
prev = flat(main.step_sim(0.1))
mx = 0; tot = 0; n = 0
for i in range(300):
    cur = flat(main.step_sim(0.1))
    chg = {k: cur[k] for k in cur if prev.get(k) != cur[k]}
    b = len(json.dumps(chg).encode())
    mx = max(mx, b); tot += b; n += 1
    prev = cur
full = len(json.dumps(main.step_sim(0.1)).encode())
print("TRANSIENT (HIC-322203 40%%): delta bytes mean=%.0f max=%d ; full packet=%d ; mean saving=%.1f%%"
      % (tot/n, mx, full, 100*(1-(tot/n)/full)))

# ---------- 3. rounding already applied? ----------
pkt = main.step_sim(0.1)
fl = [v for v in flat(pkt).values() if isinstance(v, float)]
long = [v for v in fl if len(repr(v)) > 8]
print("float leaves=%d, with >8-char repr=%d (e.g. %s)" % (len(fl), len(long), long[:5]))

# ---------- 4. stiffness ----------
import re
src = open("main.py", encoding="utf-8", errors="replace").read()
for pat in ["TAU_S *= *[0-9.]+", "tau_s *= *[0-9.]+"]:
    pass
taus = sorted(set(float(m) for m in re.findall(r"TAU_S\s*=\s*([0-9]+\.?[0-9]*)", src)))
print("declared TAU_S constants (s):", taus)
print("min=%s max=%s ratio=%.0f" % (min(taus), max(taus), max(taus)/min(taus)))
for m in re.finditer(r"^(\w*TAU\w*)\s*=\s*([0-9][0-9_.eE+-]*)", src, re.M):
    pass
names = re.findall(r"^(\w*(?:TAU|tau)\w*)\s*=\s*([0-9][0-9_.eE+-]*)", src, re.M)
print("all *TAU* module constants:")
for nm, v in names: print("   %-24s %s" % (nm, v))
