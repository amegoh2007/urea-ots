import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(B); sys.path.insert(0, B)
import main
st = main.stripper_322e001(main.CO2_DES_KGH/1000.0, main.STRIP_STEAM_T_DES_C, main.STRIP_P_DES_BARA)
top = st["top_kmolh"]; bot = st["bot_kmolh"]
feed = {k: main.STRIP_FEED207_KMOLH.get(k,0.0) + main.CO2_FEED_MOLFRAC.get(k,0.0)*main.CO2_DES_KMOLH for k in main.MW_COMP}
print("eta_T=%.5f  T_bot=%.2f  T_steam=%.2f" % (st["eta_T"], st["T_bot"], st["T_steam"]))
print("xi_hyd=%.3f xi_biu=%.4f" % (st["xi_hyd"], st["xi_biu"]))
for k in ("NH3","CO2","H2O","Urea","Biuret"):
    f=feed.get(k,0.0); t=top.get(k,0.0); b=bot.get(k,0.0)
    print("%-7s feed=%9.2f  top=%9.2f  bot=%9.2f  removed=%6.3f" % (k,f,t,b,(t/f if f else 0)))
print("STRIP_FRAC_DES =", main.STRIP_FRAC_DES)
print("bot mass%% urea =", round(st["bot_mass_pct"]["Urea"],3), " biuret=", round(st["bot_mass_pct"]["Biuret"],4))
print("bot mass%% NH3 =", round(st["bot_mass_pct"]["NH3"],3), " CO2=", round(st["bot_mass_pct"]["CO2"],3))
