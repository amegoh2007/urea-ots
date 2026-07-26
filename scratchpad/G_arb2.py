import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state if hasattr(main, "state") else main.STATE
for i in range(600): pk = main.step_sim(0.1)
print("=== ARB-2: TD-005 stream-741 mass conservation ===")
c4 = pk["DESORB_328"]["C004"]
print("  baseline bot739_th=%s  MI=%.1f" % (c4.get("bot739_th"), s.a328_d003_MI))
s.FIC_328406["mode"]="MAN"; s.FIC_328406["op"]=100.0
for i in range(600): pk = main.step_sim(0.1)   # settle 60 s
c4 = pk["DESORB_328"]["C004"]
MI0 = s.a328_d003_MI
for i in range(3000): pk = main.step_sim(0.1)  # 300 s
c4b = pk["DESORB_328"]["C004"]
rate = (s.a328_d003_MI - MI0)/300.0*3600.0
print("  @100%% stroke: bot739_th=%s (740 export)  FIC406=%s" % (c4b.get("bot739_th"), c4b.get("FIC_328406")))
print("  Comp-I accumulation rate = %+.1f kg/h   <-- >0 means net mass appearing" % rate)
print("\n  --- H2: LIC-328504 MAN 0 %, recycle still wide open ---")
s.LIC_328504["mode"]="MAN"; s.LIC_328504["op"]=0.0
for i in range(6000): pk = main.step_sim(0.1)
MI2 = s.a328_d003_MI
for i in range(3000): pk = main.step_sim(0.1)
c4c = pk["DESORB_328"]["C004"]
rate2 = (s.a328_d003_MI - MI2)/300.0*3600.0
print("  bot739_th=%s  FIC406=%s" % (c4c.get("bot739_th"), c4c.get("FIC_328406")))
print("  Comp-I accumulation = %+.1f kg/h with ZERO condensate source" % rate2)
