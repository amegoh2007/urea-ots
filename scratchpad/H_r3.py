import os,sys
HERE=os.path.dirname(os.path.abspath(__file__)); B=os.path.normpath(os.path.join(HERE,"..","backend"))
os.chdir(B); sys.path.insert(0,B)
import main, reactor
print("CO2_DES_KGH",main.CO2_DES_KGH,"CO2_DES_KMOLH",main.CO2_DES_KMOLH)
print("urea kmol/h in overflow", main.REACT_OVERFLOW_DES["Urea"])
print("overall urea/freshCO2 =", main.REACT_OVERFLOW_DES["Urea"]/main.CO2_DES_KMOLH)
print("REACT_X_DES(pinned) =", main.REACT_X_DES)
print("REACT_L_FEED_DES =", main.REACT_L_FEED_DES, " REACT_W_FEED_DES =", main.REACT_W_FEED_DES)
print("react feed CO2 implied = urea/X =", main.REACT_OVERFLOW_DES["Urea"]/main.REACT_X_DES)
print("tau_tot full 25m =", main.REACT_TAU_TOT_MIN)
print("tau at design 80%% level (20 m) =", main.REACT_TAU_TOT_MIN*0.8)
print("top node elev 21.7 m vs design liquid level", main.REACT_LEVEL_DES_M, "m")
print("REACT_ZETA_NODES", main.REACT_ZETA_NODES)
