
import os, sys, json, time
BACKEND = r"D:\Work\Urea Simulation\backend"
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
