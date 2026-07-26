import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state
pkt = main.step_sim(0.1)

for p in ["STEAM_SYSTEM.PIC_329204", "STEAM_SYSTEM.PIC_329205", "STEAM_SYSTEM.LIC_329502",
          "STEAM_SYSTEM.LIC_329503", "STEAM_SYSTEM.LIC_329504", "LPCC_3232.E011.PIC_323203",
          "EVAP_324.E001.PIC_324202", "CO2_FEED"]:
    d = pkt
    ok = True
    for part in p.split("."):
        if isinstance(d, dict) and part in d: d = d[part]
        else: ok = False; break
    if not ok: print(p, "MISSING"); continue
    if isinstance(d, dict):
        print(p, "-> keys:", sorted(d.keys())[:25], "| mode=", d.get("mode"))
    else:
        print(p, "->", d)

print()
print("PIC_322203 state:", s.PIC_322203)
print("HIC_322203 =", getattr(s, "HIC_322203", "N/A"))
print("CO2_FEED packet:", json.dumps(pkt.get("CO2_FEED"), indent=1)[:1500])
