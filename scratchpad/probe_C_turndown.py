"""AGENT C turndown probe: walk 100 -> 70 -> 50 -> 30 % load, log every step statistically."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state if hasattr(main, "state") else main.STATE
DES = 54.618; DT = 0.1

def g(t, path):
    cur = t
    for k in path.split("."):
        if isinstance(cur, dict) and k in cur: cur = cur[k]
        else: return None
    return cur

SIG = {
 "Load":"CO2_FEED.Load","P_syn":"REACT_322R001.P_bara","NC":"ratio.PV","X":"REACT_322R001.X_conv",
 "T_react":"REACT_322R001.TT_322005","L_react":"REACT_322R001.LT_322504",
 "eta_T":"STRIP_322E001.eta_T","T_bot":"STRIP_322E001.TT_322004",
 "LI_501":"STRIP_322E001.LI_322501","LV_501":"STRIP_322E001.LV_322501",
 "HPCC_L":"HPCC_322E002.LT_322E002","HPCC_T":"HPCC_322E002.TT_322010",
 "EJ_suct":"EJ_322F001.suction_kgh","SCR_L":"SCRUB_322E003.LT_329501",
 "urea_bot":"STRIP_322E001.bot_th","pumpB":"pumpB.speed",
 "C002_T":"DESORB_328.C002.TT_328002" ,
}
RAW = {
 "FFIC_pv": lambda: s.FFIC_329401["pv"], "FFIC_op": lambda: s.FFIC_329401["op"],
 "F329401_op": lambda: s.FIC_329401["op"], "F329401_pv": lambda: s.FIC_329401["pv"],
 "T328008_pv": lambda: s.TIC_328008["pv"], "T328008_op": lambda: s.TIC_328008["op"],
 "F328404_op": lambda: s.FIC_328404["op"], "F328404_pv": lambda: s.FIC_328404["pv"],
 "F328404_sp": lambda: s.FIC_328404["sp"],
 "F328402_op": lambda: s.FIC_328402["op"], "F323402_op": lambda: s.FIC_323402["op"],
 "CompI_M":  lambda: s.a328_d003_MI, "CompI_T": lambda: s.a328_d003_TI,
 "D001_P":   lambda: s.a328_d001_P,
}
NAMES = list(SIG) + list(RAW)

def read(t):
    d = {k: g(t, p) for k, p in SIG.items()}
    for k, fn in RAW.items(): d[k] = fn()
    return d

phases = []
def run(dur_s, target=None, ramp_s=0.0, start=None, label=""):
    n = int(dur_s / DT)
    st = {k: {"min": 1e30, "max": -1e30, "rev": 0, "prev": None, "dprev": 0.0} for k in NAMES}
    trace = []
    flags = set()
    for i in range(n):
        if target is not None:
            f = min(1.0, (i*DT)/ramp_s) if ramp_s > 0 else 1.0
            s.F_CO2_raw_th = (start + (target-start)*f) if ramp_s > 0 else target
        t = main.step_sim(DT)
        d = read(t)
        for k in NAMES:
            v = d[k]
            if not isinstance(v, (int, float)): continue
            a = st[k]
            a["min"] = min(a["min"], v); a["max"] = max(a["max"], v)
            if a["prev"] is not None:
                dv = v - a["prev"]
                if abs(dv) > 1e-12 and a["dprev"] != 0.0 and (dv > 0) != (a["dprev"] > 0):
                    a["rev"] += 1
                if abs(dv) > 1e-12: a["dprev"] = dv
            a["prev"] = v
        for k, v in (t.get("flags") or {}).items():
            if v: flags.add(k)
        for k, v in (t.get("trips") or {}).items():
            if v: flags.add("TRIP_"+k)
        if i % 3000 == 0:
            d2 = dict(d); d2["t"] = round(i*DT,1); trace.append(d2)
    end = read(main.step_sim(DT))
    phases.append({"label": label, "stats": {k: {"min": st[k]["min"], "max": st[k]["max"], "rev": st[k]["rev"]} for k in NAMES},
                   "end": end, "flags": sorted(flags), "trace": trace})

run(600, label="hold 100%")
for pct, lab in ((0.70,"70"), (0.50,"50"), (0.30,"30")):
    cur = s.F_CO2_raw_th
    run(1800, target=DES*pct, ramp_s=600.0, start=cur, label=f"ramp->{lab}%")
    run(3600, target=DES*pct, label=f"hold {lab}%")

json.dump(phases, open(os.path.join(HERE,"agentC_turndown.json"),"w"), indent=1)
for p in phases:
    print("="*90); print(p["label"], " FLAGS:", p["flags"])
    print(f"{'sig':12s} {'min':>12s} {'max':>12s} {'end':>12s} {'revs':>7s}")
    for k in NAMES:
        st = p["stats"][k]; e = p["end"].get(k)
        if st["min"] > 1e29: continue
        print(f"{k:12s} {st['min']:12.4f} {st['max']:12.4f} {(e if isinstance(e,(int,float)) else float('nan')):12.4f} {st['rev']:7d}")
