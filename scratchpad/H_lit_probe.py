import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main, reactor

print("REACT_TAU_TOT_MIN      =", main.REACT_TAU_TOT_MIN, "min =", main.REACT_TAU_TOT_MIN*60, "s")
print("REACT_THERM_TAU_MIN    =", main.REACT_THERM_TAU_MIN)
print("REACT_BETA_DAMK        =", main.REACT_BETA_DAMK)
print("REACT_TAU_NODE_MIN     =", main.REACT_TAU_NODE_MIN)
print("REACT_LIQ_H_MM         =", main.REACT_LIQ_H_MM)
print("FEED_TD_S              =", main.FEED_TD_S)
print("SYN_P_TAU_FILL_MIN     =", main.SYN_P_TAU_FILL_MIN, "->", main.SYN_P_TAU_FILL_MIN*60, "s")
print("reactor X_DES          =", reactor.X_DES, " X_DES_RAW=", reactor.X_DES_RAW)
print("L0_DES (N/C)           =", reactor.L0_DES)
print("W0_DES (H2O/CO2)       =", reactor.W0_DES)
print("X_INF                  =", reactor.X_INF)
print("RATIO_PV_DES fresh N/C =", main.RATIO_PV_DES)
for n in ("STRIP_XI_HYD_DES","STRIP_XI_BIU_DES","STRIP_BIU_EA","STRIP_T_BIU_DES_K",
          "STRIP_BOT_T_CRYST_C","CARB_MP_PURE_C","CARB_T_CRYST_LO","CARB_W_HI",
          "CARB_NC_LO","CARB_NC_HI","STRIP_T_BOTTOM_DES_C","R324_F001_P_BARA",
          "R324_E001_T_SP_C","R324_W_EV1","R324_W_EV2","R323_F010_P_BARA","R324_UF_RATIO"):
    print("%-22s =" % n, getattr(main, n, "<<MISSING>>"))
# reactor liquid holdup / volume
try:
    print("REACT_M_LIQ_DES        =", main.REACT_M_LIQ_DES)
    print("_react_area_m2         =", main._react_area_m2)
    print("_react_vdot_m3h        =", main._react_vdot_m3h)
    print("_react_mdot_kgh        =", main._react_mdot_kgh)
except Exception as e:
    print("holdup probe:", e)
# stripper efficiency at design + NH3 removal
main.step_sim(0.1)
s = main.state if hasattr(main,"state") else main.STATE
tel = main.telemetry() if hasattr(main,"telemetry") else {}
print("\n-- stripper block keys --")
try:
    st = main.stripper_block if hasattr(main,"stripper_block") else None
except Exception: pass
