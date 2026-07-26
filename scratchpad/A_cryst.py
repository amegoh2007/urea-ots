"""AGENT A probe 3 -- does the crystallization model actually detect a crystallization risk?

Tests:
  (1) baseline CRYST block: what does each monitored stream report at 100 % design?
  (2) Is any of it COUPLED to the plant, or is it a passive read-out?  (Does it throttle any flow?)
  (3) Cut the MP steam to the stripper (the classic route to a frozen carbamate line) and watch
      the STRIP_BOT margin + flags.
  (4) Cut the CO2 feed to zero (loop de-inventories, temperatures collapse) and watch.
  (5) Direct unit test of _carb_t_cryst_water / _cryst_assess: is the freezing line a function of
      CO2/H2O ratio at all, or only of free water?
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa
s = main.state if hasattr(main, "state") else main.STATE
DT = 0.5


def show(tag, t):
    c = t["CRYST"]; f = t["flags"]
    print(f"\n== {tag} ==")
    for k, v in c.items():
        print(f"   {k:16s} T_cryst={str(v['T_cryst']):>7} margin={str(v['margin']):>8} "
              f"h2o_wt={str(v['h2o_wt']):>7} co2_h2o={str(v['co2_h2o']):>7} nc={str(v['nc']):>7} {v['state']}")
    print(f"   flags: WARN={f['CARBAMATE_CRYST_WARN']} ALARM={f['CARBAMATE_CRYST_ALARM']} "
          f"STRIP_SOLID={f['STRIPPER_SOLIDIFICATION']} SCRUB_SOLID={f['SCRUBBER_SOLIDIFICATION']} "
          f"DEPOS={f['CARBAMATE_DEPOSITION']}")
    print(f"   TT-322004 strip bot = {t['STRIP_322E001']['TT_322004']}  "
          f"TT-322002 scrub ov = {t['SCRUB_322E003']['TT_322002']}  "
          f"drain = {t['STRIP_322E001']['drain_th']} t/h")


t = main.step_sim(DT)
show("BASELINE 100 % design", t)

# (5) unit-test the freezing line -- is it CO2/H2O or water-only?
print("\n== (5) _carb_t_cryst_water(w) -- is it a function of the CO2/H2O RATIO? ==")
for w in (0.0, 0.05, 0.10, 0.20, 0.30, 0.40, 0.60, 0.90):
    print(f"   w_H2O={w:5.2f} -> T_cryst = {main._carb_t_cryst_water(w):7.2f} C")
print("   NOTE: signature takes ONLY w_h2o.  CO2 mass fraction is NEVER an argument.")
st = {"T_C": 100.0, "mass_pct": {"CO2": 30.0, "H2O": 20.0, "NH3": 50.0},
      "mol_pct": {"CO2": 20.0, "H2O": 40.0, "NH3": 40.0}}
st2 = dict(st); st2["mass_pct"] = {"CO2": 5.0, "H2O": 20.0, "NH3": 75.0}
print("   same T, same H2O, CO2 30 % ->", main._cryst_assess(st))
print("   same T, same H2O, CO2  5 % ->", main._cryst_assess(st2))

# (3) kill the stripper MP steam
print("\n\n### (3) MP steam to 322E001 cut ###")
try:
    s.FIC_322403 if False else None
except Exception:
    pass
# find the steam valve
cands = [a for a in dir(s) if "329204" in a or "steam" in a.lower()]
print("   steam-related state attrs:", cands[:20])
s.steam.MP_users_open = getattr(s.steam, "MP_users_open", None)
# brute force: drive the stripper steam PIC to minimum
if hasattr(s, "PIC_329204"):
    s.PIC_329204["mode"] = "MAN"; s.PIC_329204["op"] = 0.0
for k in range(int(3600 / DT)):
    t = main.step_sim(DT)
    if k in (int(300 / DT), int(1800 / DT), int(3600 / DT) - 1):
        show(f"MP steam MAN 0, t={k*DT:.0f}s", t)

# (4) CO2 cut
print("\n\n### (4) CO2 feed cut to 0 (XV-322902 shut) ###")
s.XV_322902 = False
for k in range(int(7200 / DT)):
    t = main.step_sim(DT)
    if k in (int(600 / DT), int(3600 / DT), int(7200 / DT) - 1):
        show(f"CO2 cut, t={k*DT:.0f}s", t)
