import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
sys.stdout.reconfigure(line_buffering=True)
import main
s = main.state if hasattr(main, "state") else main.STATE
DT = 0.1
def settle(n):
    p = None
    for _ in range(n): p = main.step_sim(DT)
    return p
p = settle(6000)
def rep(tag, p):
    ss_ = p["STEAM_SYSTEM"]; st = s.steam
    print(f"\n[{tag}] load {s.F_CO2_th/54.618*100:.1f}%")
    print("  FT_329403_th (indicated BL 25-bar supply) =", ss_["FT_329403_th"], "t/h")
    print("  ACTUAL BL draw  m_supply+m_911+m_turb+m_963 =",
          round((st.m_supply + st.m_turbine + st.m_963)*3.6 + 1.105, 2), "t/h")
    print("  FT_329407_th (indicated LP EXPORT to 320MT02) =", ss_["FT_329407_th"], "t/h")
    print("  PHYSICS PV-329207B: pv207b_pct =", round(st.pv207b_pct,2), "%  m_turbine =",
          round(st.m_turbine*3.6,2), "t/h  (POSITIVE = 25-bar IMPORT into the 4-bar header)")
    print("  PV-329207C(963)", round(st.valve_963_pct,2), "%  m_963", round(st.m_963*3.6,2), "t/h")
rep("100%", p)
s.F_CO2_raw_th *= 0.70
p = settle(int(4000/DT))
rep("70%", main.step_sim(DT))
