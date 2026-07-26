import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main

# --- analytic dt_crit for every _fic_flow loop: |1 - Kc*a*g| < 1,  a = dt/(tau+dt) ---
# g = design/op_des in the SAME units the controller sees (vol loops: Kc already *rho, g /rho)
import re
src = open("main.py", encoding="utf-8", errors="replace").read()
print("=== _fic_flow call sites ===")
calls = re.findall(r"_fic_flow\(\s*s\.(\w+),\s*([A-Za-z0-9_]+),\s*([A-Za-z0-9_]+)", src)
rows = []
for tag, dname, oname in calls:
    try:
        design = getattr(main, dname); op_des = getattr(main, oname)
        c = getattr(main.state, tag)
        Kc = c["Kc"]; g = design/op_des
        # find rho= on that call line
        m = re.search(r"_fic_flow\(\s*s\.%s\b.*?\)" % tag, src, re.S)
        seg = m.group(0) if m else ""
        rm = re.search(r"rho=([A-Za-z0-9_]+)", seg)
        if rm:
            rho = getattr(main, rm.group(1)); g = g/rho
        tm = re.search(r"tau_s=([0-9.]+)", seg); tau = float(tm.group(1)) if tm else 5.0
        # |1 - Kc*a*g| < 1  ->  a < 2/(Kc*g)
        K = Kc*g
        acrit = 2.0/K if K > 0 else float("inf")
        dtc = (acrit*tau)/(1-acrit) if acrit < 1 else float("inf")
        rows.append((dtc, tag, Kc, g, tau, K))
    except Exception as e:
        rows.append((float("nan"), tag, None, None, None, str(e)))
rows.sort(key=lambda r: (math.isnan(r[0]) and 1e9) or r[0])
print("%-16s %12s %10s %10s %6s  %10s" % ("tag","Kc","g","Kc*g","tau_s","dt_crit_s"))
for dtc, tag, Kc, g, tau, K in rows:
    print("%-16s %12s %10s %10s %6s  %10s" %
          (tag, ("%.4g"%Kc) if Kc is not None else "-", ("%.4g"%g) if g is not None else "-",
           ("%.4g"%K) if isinstance(K,float) else "-", tau, ("%.3f"%dtc) if dtc==dtc else "?"))
print("\nSTEP_CAP = %s   -> loops with dt_crit < STEP_CAP are UNSTABLE in FAST mode / on a wall-clock stall"
      % main.STEP_CAP)
bad = [r for r in rows if r[0] == r[0] and r[0] < main.STEP_CAP]
print("EXPOSED: %d loops -> %s" % (len(bad), [r[1] for r in bad]))
