import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main

def hold(dt, H=900.0):
    main.state = main.State()
    for _ in range(int(H/dt)): pk = main.step_sim(dt)
    d = pk["DESORB_328"]["D001"]
    return d.get("reflux775_th"), d.get("FIC_328404", {}), pk["DESORB_328"].get("TIC_328008", {})

print("%-6s %-10s %-30s %s" % ("dt", "reflux", "FIC_328404(pv/sp/op/mode)", "TIC_328008(pv/sp/op/mode)"))
for dt in (0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5):
    r, f, t = hold(dt)
    print("%-6s %-10s pv=%-7s sp=%-7s op=%-7s %-4s   pv=%-7s sp=%-7s op=%-8s %s"
          % (dt, r, f.get("pv"), f.get("sp"), f.get("op"), f.get("mode"),
             t.get("pv"), t.get("sp"), t.get("op"), t.get("mode")))

# exact FAST-mode emulation: DT=0.1 wall, x60 -> 12 sub-steps of STEP_CAP=0.5
main.state = main.State()
adv = 0.0
for wall in range(150):          # 15 s wall == 900 s sim
    a = main.DT * main.SIM_SPEED["FAST"]
    while a > 1e-9:
        h = min(main.STEP_CAP, a); pk = main.step_sim(h); a -= h
d = pk["DESORB_328"]["D001"]
print("\nFAST-mode path (STEP_CAP=0.5 substeps), 900 s sim, NO operator action:")
print("  reflux775_th =", d.get("reflux775_th"), " FIC_328404 =", d.get("FIC_328404"))
print("  TIC_328008 =", pk["DESORB_328"].get("TIC_328008"))
