"""AGENT A probe 5 -- does HV/PV-322203 (the CO2 vent) reach LT-322504?

The chain that SHOULD exist:
  HIC-322203 opens -> line sags -> CO2 feed to 322E001 falls -> co2_scale s falls ->
  reactor production m_ov_split falls -> reactor m_in falls -> but m_out is
  mdot_des*(theta/theta_des)*(L/L_des), PRODUCTION-INDEPENDENT -> holdup drains -> LT-322504 falls.

Run three cases side by side to isolate what LT-322504 actually responds to:
  A: HIC-322203 = 0   (control)
  B: HIC-322203 = 10 %  (feed 54.6 -> ~18 t/h, Load ~34 %)
  C: HIC-322203 = 14 %  (feed -> 0, total CO2 cut)
and print LT-322504, the physical head, m_in/m_out proxies and the CO2 feed each minute.
"""
import os, sys, importlib
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa

DT = 0.5
MINUTES = 30


def run(hic, label):
    importlib.reload(main)
    s = main.state if hasattr(main, "state") else main.STATE
    t = main.step_sim(DT)
    R = t["REACT_322R001"]
    print(f"\n--- {label} ---")
    print(f"  t=  0 min  LT504={R['LT_322504']:6.2f}%  head={s.react_level_pct:6.2f}%  "
          f"m_liq={s.react_m_liq:11.0f} kg  CO2={t['CO2_FEED']['FY_322403']:7.3f} t/h  "
          f"Load={t['CO2_FEED']['Load']:6.1f}")
    s.HIC_322203 = hic
    for m in range(1, MINUTES + 1):
        for _ in range(int(60 / DT)):
            t = main.step_sim(DT)
        R = t["REACT_322R001"]
        if m in (1, 2, 5, 10, 20, 30):
            print(f"  t={m:3d} min  LT504={R['LT_322504']:6.2f}%  head={s.react_level_pct:6.2f}%  "
                  f"m_liq={s.react_m_liq:11.0f} kg  CO2={t['CO2_FEED']['FY_322403']:7.3f} t/h  "
                  f"Load={t['CO2_FEED']['Load']:6.1f}  xi_urea={R['xi_urea']:8.1f}")
    return R["LT_322504"], s.react_level_pct


a = run(0.0, "A: HIC-322203 = 0 % (control)")
b = run(10.0, "B: HIC-322203 = 10 % (CO2 feed ~18 t/h, Load ~34 %)")
c = run(14.0, "C: HIC-322203 = 14 % (CO2 feed = 0, total cut)")

print("\n=== SUMMARY after 30 min ===")
print(f"  A control   LT-322504 = {a[0]:6.2f} %   physical head = {a[1]:6.2f} %")
print(f"  B 10 % vent LT-322504 = {b[0]:6.2f} %   physical head = {b[1]:6.2f} %")
print(f"  C 14 % vent LT-322504 = {c[0]:6.2f} %   physical head = {c[1]:6.2f} %")
print("\n  If B and C land on the SAME reading as A, LT-322504 does not see the CO2 vent at all.")
