"""Load turndown: does the synthesis pressure track load the way the real DCS trend does?

Real Urea_Startup_28-06-2025 (row 11:01): UREA-LOAD 60.7 %, PT-329201 104.1 bar a,
PIC-322203 112.9, PV-322203 35 %, TT-322013 185.5, AY-322701 ~3.1.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state
for _ in range(50):
    t = main.step_sim(0.1)

print(f"{'load%':>7} {'CO2 t/h':>8} {'React P':>8} {'PI-329201':>10} {'HPCC P':>8} "
      f"{'PIC-322203':>11} {'PV-322203':>10} {'TT-322013':>10} {'TT-322009':>10} {'AT-322701':>10}")


def show(tag):
    print(f"{tag:>7} {t['CO2_FEED']['FY_322403']:8.2f} {t['REACT_322R001']['P_bara']:8.2f} "
          f"{t['EJ_322F001']['PI_329201']:10.2f} {t['HPCC_322E002']['P_bara']:8.2f} "
          f"{t['CO2_FEED']['PIC_322203']:11.2f} {t['CO2_FEED']['PV_322203']:10.2f} "
          f"{t['STRIP_322E001']['TT_322013']:10.2f} {t['REACT_322R001']['TT_322009']:10.2f} "
          f"{t['REACT_322R001']['AT_322701']:10.3f}")


show("100")
for load in (90, 80, 70, 60, 50, 40):
    main.handle_cmd({"type": "co2_set", "value": main.CO2_DES_KGH / 1000.0 * load / 100.0})
    for _ in range(18000):          # 30 min settle per step
        t = main.step_sim(0.1)
    show(str(load))
