import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main, reactor
for _ in range(50):
    main.step_sim(0.1)
st = main.stripper_322e001()
print("keys:", sorted(st.keys()))
feed = st.get("feed") or main._STRIP_FEED_DES
print("eta_T =", st.get("eta_T"), " eta_T_steam=", st.get("eta_T_steam"))
print("T_bot =", st.get("T_bot"), " T_steam=", st.get("T_steam"))
print("xi_hyd=", st.get("xi_hyd"), " xi_biu=", st.get("xi_biu"))
for k in ("gas","liq","bottom","top"):
    if k in st and isinstance(st[k], dict):
        print(k, {c: round(v,2) for c,v in st[k].items()})
# NH3 removal fraction
try:
    g = st["gas"]; l = st["liq"]
    fin = main.STRIP_FEED207_KMOLH
    print("\nNH3 in feed kmol/h =", fin["NH3"])
    print("NH3 to gas   kmol/h =", g.get("NH3"))
    print("NH3 removal frac    =", g.get("NH3",0)/fin["NH3"])
    print("CO2 in feed =", fin["CO2"], " CO2 to gas =", g.get("CO2"),
          " CO2 removal =", g.get("CO2",0)/fin["CO2"])
    print("Urea in bottoms kmol/h =", l.get("Urea"), " Biuret =", l.get("Biuret"))
except Exception as e:
    print("removal calc:", e)
