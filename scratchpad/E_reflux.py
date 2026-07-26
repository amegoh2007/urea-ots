import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main

def run(dt, H=900.0, kick=True):
    main.state = main.State(); main.step_sim(dt)
    if kick: main.state.HIC_322203 = 35.0
    for _ in range(int(H/dt)): pk = main.step_sim(dt)
    return pk

for dt in (0.01, 0.1, 0.5, 1.0):
    pk = run(dt)
    d = pk["DESORB_328"]["D001"]
    print("dt=%-5s reflux775_th=%-22r  FIC_328404.pv=%-12r op=%-8r"
          % (dt, d.get("reflux775_th"), d.get("FIC_328404", {}).get("pv"),
             d.get("FIC_328404", {}).get("op")))
    e = pk["EVAP_324"]["E001"]
    print("        PT_324202=%r  PIC pv=%r" % (e.get("PT_324202"), e.get("PIC_324202", {}).get("pv")))

# no-kick (pure design hold) -- does the design anchor survive dt change?
print("\n--- NO DISTURBANCE, 900 s hold ---")
base = None
for dt in (0.01, 0.1, 0.5):
    pk = run(dt, kick=False)
    d = pk["DESORB_328"]["D001"]
    print("dt=%-5s reflux775_th=%r" % (dt, d.get("reflux775_th")))
