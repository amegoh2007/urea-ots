"""Recon: steam design point for items 8/9. Dump SteamState flows + any 329 steam telemetry subtree."""
import sys, os, json
BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, BACKEND); os.chdir(BACKEND)
import main

telem = main.step_sim(0.1)
st = main.state.steam

def g(o, *names):
    return {n: round(getattr(o, n), 4) for n in names if hasattr(o, n)}

print("--- SteamState flows (kg/s) ---")
print(g(st, "m_supply", "m_903", "m_963", "m_turbine", "m_ld", "m_vent", "m_pic", "m_water", "m_hpcc_gen",
        "P_SUP", "P_MP", "P_9", "P_LP",
        "valve_supply_pct", "valve_admit9_pct", "valve_963_pct", "pv207b_pct"))

# sum of BL consumers -> compare 60848 kg/h
comps = {}
for n in ("m_supply", "m_903", "m_963", "m_turbine"):
    if hasattr(st, n):
        comps[n] = getattr(st, n) * 3600.0
print("\n--- kg/h ---")
for k, v in comps.items():
    print(f"  {k:12s} {v:10.1f}")
print(f"  SUM(902+903+963)   {sum(comps[n] for n in ('m_supply','m_903','m_963') if n in comps):10.1f}  (anchor 901 = 60848 incl 911)")
print(f"  m_turbine          {comps.get('m_turbine',0):10.1f}  (932 anchor = 16707)")

# locate 329 steam telemetry
for parent, sub in telem.items():
    if isinstance(sub, dict):
        blob = json.dumps(sub)
        if "supply" in blob or "329207" in blob or "901" in blob or "steam" in blob.lower():
            print(f"\n--- telem[{parent}] keys: {list(sub.keys())}")
