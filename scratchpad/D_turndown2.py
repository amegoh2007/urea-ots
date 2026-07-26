"""AGENT D probe 3 -- clean 100% -> 70% -> 50% turndown on the CO2 BL feed."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main, steam_system as ss
s = main.state if hasattr(main, "state") else main.STATE
DT = 0.1

def settle(n):
    p = None
    for _ in range(n): p = main.step_sim(DT)
    return p

def line(tag, p):
    st = s.steam
    stm = p.get("STEAM_SYSTEM") or {}
    cry = p.get("CRYST") or {}
    print(f"\n--- {tag} ---")
    print(f"  CO2 raw {s.F_CO2_raw_th:.3f}  feed {s.F_CO2_th:.3f} t/h  load {s.F_CO2_th/54.618*100:.1f}%")
    print(f"  m_supply {st.m_supply:.4f} kg/s = {st.m_supply*3.6:.2f} t/h   P_MP {st.P_MP:.3f}"
          f"  P_9 {st.P_9:.3f}  P_LP {st.P_LP:.3f}")
    print(f"  m_ld9 {st.m_ld:.4f}  m_963 {st.m_963:.4f}  m_turb {st.m_turbine:.4f}  m_vent {st.m_vent:.4f}")
    print("  STEAM_SYSTEM tel:", json.dumps(stm)[:500])
    for k, v in cry.items():
        print(f"   {k:16s} Tc={v['T_cryst']}  margin={v['margin']}  co2h2o={v['co2_h2o']}"
              f"  h2o={v['h2o_wt']}  nc={v['nc']}  {v['state']}")
    print("  flags:", {k: v for k, v in s.flags.items() if "CRYST" in k})

p = settle(6000); line("BASELINE 100%", p)
raw0 = s.F_CO2_raw_th
print("\nraw0 =", raw0)

for frac in (0.85, 0.70, 0.50):
    s.F_CO2_raw_th = raw0 * frac
    p = settle(int(4000/DT))          # 4000 s to settle the slow loop
    line(f"TURNDOWN raw x{frac:.2f}", p)
    st = s.steam
    lf = s.F_CO2_th / 54.618
    print(f"  >> specific MP steam index = {(st.m_supply/ss.M_STRIP_DES)/max(lf,1e-9):.3f}"
          f"   (1.0 ideal; value = t steam per t urea vs design)")
