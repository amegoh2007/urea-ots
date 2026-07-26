"""AGENT D probe 5 -- 100% -> 70% CO2 turndown, unbuffered output."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
sys.stdout.reconfigure(line_buffering=True)
import main, steam_system as ss
s = main.state if hasattr(main, "state") else main.STATE
DT = 0.1
def settle(n):
    p = None
    for _ in range(n): p = main.step_sim(DT)
    return p

def line(tag, p):
    st = s.steam; cry = p.get("CRYST") or {}
    print(f"\n--- {tag} ---")
    print(f"  CO2raw {s.F_CO2_raw_th:.3f} feed {s.F_CO2_th:.3f} t/h load {s.F_CO2_th/54.618*100:.1f}%")
    print(f"  m_supply {st.m_supply:.4f} kg/s ({st.m_supply*3.6:.2f} t/h)  P_MP {st.P_MP:.3f}"
          f" P_9 {st.P_9:.3f} P_LP {st.P_LP:.3f}  m_ld9 {st.m_ld:.4f} m_turb {st.m_turbine:.4f}"
          f" m_963 {st.m_963:.4f} m_vent {st.m_vent:.4f}")
    for k, v in cry.items():
        print(f"    {k:16s} Tc={v['T_cryst']} margin={v['margin']} co2h2o={v['co2_h2o']}"
              f" h2o={v['h2o_wt']} nc={v['nc']} {v['state']}")
    lf = max(s.F_CO2_th/54.618, 1e-9)
    print(f"  >> specific-MP-steam index {(st.m_supply/ss.M_STRIP_DES)/lf:.3f}")

p = settle(6000); line("BASELINE", p)
raw0 = s.F_CO2_raw_th
s.F_CO2_raw_th = raw0 * 0.70
print(f"\n>>> BL CO2 raw {raw0:.3f} -> {s.F_CO2_raw_th:.3f} t/h  (70% turndown)")
for t in (600, 1200, 2400, 4000):
    settle(int(600/DT) if t == 600 else int(600/DT) if t == 1200 else int(1200/DT) if t == 2400 else int(1600/DT))
    line(f"t={t}s", main.step_sim(DT))
