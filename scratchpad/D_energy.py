"""AGENT D probe 1 -- steam-network energy audit + turndown specific-steam."""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
import steam_system as ss

s = main.state if hasattr(main, "state") else main.STATE
for _ in range(600):
    main.step_sim(0.1)

st = s.steam
print("=== [1] design steam node state ===")
print(f" P_SUP {st.P_SUP:.3f}  P_MP {st.P_MP:.4f}  P_9 {st.P_9:.4f}  P_LP {st.P_LP:.4f}")
print(f" m_supply {st.m_supply:.4f}  m_903 {st.m_903:.5f}  m_ld(9->4) {st.m_ld:.5f}"
      f"  m_963 {st.m_963:.5f}  m_vent {st.m_vent:.5f}  m_turbine {st.m_turbine:.5f}")
print(f" M_STRIP_DES {ss.M_STRIP_DES:.4f} kg/s   M_USERS_LP {ss.M_USERS_LP:.4f} kg/s")
print(f" M_HPCC_DES_LIVE {main.M_HPCC_DES_LIVE!r}")

tel = main.build_telemetry() if hasattr(main, "build_telemetry") else None

print()
print("=== [2] duties driving the headers ===")
print(f" STRIP_DUTY_DES_KW      {main.STRIP_DUTY_DES_KW}")
print(f" HPCC_LATENT_4BAR       {main.HPCC_LATENT_4BAR}")
m_hpcc_des = main.M_HPCC_DES_LIVE
print(f" HPCC LP steam raised   {m_hpcc_des:.4f} kg/s = {m_hpcc_des*3600/1000:.2f} t/h"
      f"   duty = {m_hpcc_des*main.HPCC_LATENT_4BAR:.0f} kW")
print(f" MP steam to stripper   {ss.M_STRIP_DES:.4f} kg/s = {ss.M_STRIP_DES*3600/1000:.2f} t/h"
      f"   duty = {main.STRIP_DUTY_DES_KW:.0f} kW")

# ---- flash-recovery arithmetic (IF97 sat table, sourced) ----
# h_f / h_fg at the three levels
TAB = {  # P bar a : (Tsat C, h_f kJ/kg, h_fg kJ/kg)
    19.7: (211.4, 903.9, 1889.0),
    9.0:  (175.4, 742.8, 2030.5),
    4.4:  (146.3, 616.3, 2130.5),
}
m_cond = ss.M_STRIP_DES            # condensate cascading 329D005 -> 329D009 (LV-329502)
x9 = (TAB[19.7][1] - TAB[9.0][1]) / TAB[9.0][2]
m_flash9 = m_cond * x9
print()
print("=== [3] MISSING flash recovery, 329D005 condensate -> 329D009 ===")
print(f" condensate cascade   {m_cond:.4f} kg/s @ {TAB[19.7][0]} C (h_f {TAB[19.7][1]})")
print(f" flash fraction to 9 bar a  x = {x9:.5f}")
print(f" 9-bar flash steam    {m_flash9:.4f} kg/s = {m_flash9*3600/1000:.2f} t/h")
print(f" recovered duty       {m_flash9*TAB[9.0][2]:.0f} kW")
print(f" model m_903 (BL admit, kg/s)  {st.m_903:.5f}   <-- 9-bar node has NO flash inlet")
print(f" PFD stream 903 design admit   {ss.M_903_DES:.5f} kg/s = 1754 kg/h")

m_cond2 = m_cond - m_flash9
x4 = (TAB[9.0][1] - TAB[4.4][1]) / TAB[4.4][2]
m_flash4 = m_cond2 * x4
print()
print("=== [4] MISSING flash recovery, 329D009 condensate -> 322D001 ===")
print(f" condensate cascade   {m_cond2:.4f} kg/s @ {TAB[9.0][0]} C")
print(f" flash fraction to 4.4 bar a  x = {x4:.5f}")
print(f" 4-bar flash steam    {m_flash4:.4f} kg/s = {m_flash4*3600/1000:.2f} t/h")
print(f" recovered duty       {m_flash4*TAB[4.4][2]:.0f} kW")
print(f" model LP inlets: HPCC {m_hpcc_des:.4f} + ld {st.m_ld:.5f} + 963 {st.m_963:.5f}")
print(f" flash as % of LP header generation: {100*m_flash4/m_hpcc_des:.2f} %")

print()
print("=== [5] TURNDOWN: is stripper MP steam load-following? ===")
def co2_now():
    return main.CO2_DES_KGH
print(" STRIP duty is hard-wired:  Q_strip_kjh = STRIP_DUTY_DES_KW*3600  (main.py:3415)")
print(f" -> m_strip is CONSTANT {ss.M_STRIP_DES:.4f} kg/s at ALL loads")
