import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state if hasattr(main, "state") else main.STATE

print("=== ARB-1: FIC-328404 step-size dependence (Agent E blocker) ===")
print("STEP_CAP =", main.STEP_CAP)
for dt in (0.1, 0.25, 0.3, 0.4, 0.5):
    st = main.State()
    main.state = st
    n = int(900.0/dt)
    for i in range(n):
        pk = main.step_sim(dt)
    d = pk["DESORB_328"]["D001"]
    f = d["FIC_328404"]
    print(f"  dt={dt:<5} reflux775_th={d['reflux775_th']:<8} FIC404 pv={f['pv']:<7} sp={f['sp']:<7} op={f['op']:<7} mode={f['mode']}")
