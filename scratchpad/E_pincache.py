"""Decisive test: is the .boot_pin_cache.json path BIT-EXACT with a fresh 21k-tick settle?"""
import os, sys, json, time, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))

CHILD = r'''
import os, sys, json, time
BACKEND = r"%s"
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
t=time.perf_counter()
import main
imp = time.perf_counter()-t
import steam_system as ss
d = main._collect_pin()
d["_M_HPCC_DES_LIVE"] = main.M_HPCC_DES_LIVE
d["_M_504_DES"]       = ss.M_504_DES
d["_import_s"]        = imp
# 500-tick fingerprint of the live packet
for _ in range(500): pk = main.step_sim(0.1)
d["_pk"] = pk
print("@@@" + json.dumps(d, sort_keys=True))
''' % BACKEND

PY = r"C:/Users/ameel/AppData/Local/Microsoft/WindowsApps/python3.exe"
CACHE = os.path.join(BACKEND, ".boot_pin_cache.json")
SAVE  = os.path.join(HERE, "_pin_cache_backup.json")

def child():
    p = os.path.join(HERE, "_pin_child.py")
    open(p, "w").write(CHILD)
    r = subprocess.run([PY, p], capture_output=True, text=True)
    for ln in r.stdout.splitlines():
        if ln.startswith("@@@"): return json.loads(ln[3:])
    print(r.stdout[-2000:], r.stderr[-2000:]); raise SystemExit("child failed")

assert os.path.exists(CACHE)
open(SAVE, "w").write(open(CACHE).read())
print("A) cache-hit path ...")
a = child()
print("   import_s = %.2f" % a["_import_s"])
os.remove(CACHE)
print("B) fresh 21k-tick settle path ...")
b = child()
print("   import_s = %.2f" % b["_import_s"])
# restore original cache exactly
open(CACHE, "w").write(open(SAVE).read())

ka = a.pop("_import_s"); kb = b.pop("_import_s")
pa = a.pop("_pk"); pb = b.pop("_pk")
diff = [k for k in a if json.dumps(a[k], sort_keys=True) != json.dumps(b.get(k), sort_keys=True)]
print("\nPIN CONSTANTS: %d compared, %d DIFFER -> %s" % (len(a), len(diff), diff))
for k in diff:
    print("   %-22s cache=%r  settle=%r" % (k, a[k], b.get(k)))
def flat(o, pre=""):
    out={}
    if isinstance(o,dict):
        for k,v in o.items(): out.update(flat(v,pre+"/"+str(k)))
    elif isinstance(o,list):
        for i,v in enumerate(o): out.update(flat(v,pre+"/"+str(i)))
    else: out[pre]=o
    return out
fa, fb = flat(pa), flat(pb)
d2 = [k for k in fa if fa[k] != fb.get(k)]
print("PACKET after 500 ticks: %d leaves, %d DIFFER -> %s" % (len(fa), len(d2), d2[:12]))
print("\nspeedup: settle %.2f s vs cache %.2f s  (saves %.2f s)" % (kb, ka, kb-ka))
print("cache restored, sha ok:", open(CACHE).read() == open(SAVE).read())
