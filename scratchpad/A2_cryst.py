"""AGENT A (2nd pass) -- crystallization model interrogation.

Q1 Does the equilibrium model actually flag crystallization risk, and for WHICH streams?
Q2 Is T_cryst a function of the CO2/H2O ratio (as the comment claims) or only of free water?
Q3 Is the monitor COUPLED to the hydraulics, or a passive read-out?
Q4 Does it fire on a real freeze scenario (MP steam loss / CO2 loss)?
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa
s = main.state if hasattr(main, "state") else main.STATE
DT = 0.5

def settle(n):
    for _ in range(n): main.step_sim(DT)

def show(tag):
    tel = main.step_sim(DT)
    C = tel.get("CRYST") or tel.get("cryst")
    F = tel.get("flags", {})
    print(f"\n--- {tag} ---")
    if C is None:
        # search
        def deep(o, key, p=""):
            r=[]
            if isinstance(o,dict):
                for k,v in o.items():
                    if k.upper()=="CRYST": r.append((p+"/"+k,v))
                    r+=deep(v,key,p+"/"+k)
            return r
        hits = deep(tel,"CRYST")
        print("  CRYST hits:", [h[0] for h in hits])
        C = hits[0][1] if hits else {}
    for k, v in C.items():
        print(f"  {k:16s} {v}")
    print(f"  WARN={F.get('CARBAMATE_CRYST_WARN')} ALARM={F.get('CARBAMATE_CRYST_ALARM')} "
          f"SOLIDIF={F.get('STRIPPER_SOLIDIFICATION')}")
    return C, F

settle(600)
show("BASELINE 100 % design")

# --- Q2: is the freezing line CO2-sensitive at all? -------------------------
print("\n=== Q2: T_cryst vs composition (unit test of _cryst_assess) ===")
base = {"T_C": 100.0,
        "mass_pct": {"CO2": 20.0, "H2O": 30.0, "NH3": 25.0, "Urea": 25.0},
        "mol_pct":  {"CO2": 20.0, "H2O": 30.0, "NH3": 25.0, "Urea": 25.0}}
for co2 in (5.0, 20.0, 40.0):
    st = json.loads(json.dumps(base))
    st["mass_pct"]["CO2"] = co2          # CO2/H2O ratio 0.17 -> 1.33 (8x), H2O held FIXED
    st["mol_pct"]["CO2"]  = co2
    r = main._cryst_assess(st)
    print(f"  CO2 {co2:5.1f} wt% (H2O held 30 wt%)  CO2/H2O={r['co2_h2o']}  "
          f"T_cryst={r['T_cryst']}  margin={r['margin']}  state={r['state']}")
for h2o in (5.0, 20.0, 30.0, 45.0):
    st = json.loads(json.dumps(base)); st["mass_pct"]["H2O"] = h2o; st["mol_pct"]["H2O"] = h2o
    r = main._cryst_assess(st)
    print(f"  H2O {h2o:5.1f} wt%  T_cryst={r['T_cryst']}  margin={r['margin']}  state={r['state']}")

# --- Q3: coupling test.  Force an ALARM state and see if any FLOW changes ---
print("\n=== Q4: MP steam collapse (stripper freeze route) ===")
print("  P_MP before:", round(s.steam.P_MP, 3), " Tsat", round(main.tsat_steam(s.steam.P_MP), 1))
for frac in (0.6, 0.35, 0.20):
    s.steam.P_MP = 19.7 * frac
    settle(400)
    tel = main.step_sim(DT)
    C = tel.get("CRYST", {})
    F = tel.get("flags", {})
    sb = C.get("STRIP_BOT", {})
    print(f"  P_MP={s.steam.P_MP:5.2f} bar (Tsat {main.tsat_steam(s.steam.P_MP):5.1f}) "
          f"STRIP_BOT T_cryst={sb.get('T_cryst')} margin={sb.get('margin')} state={sb.get('state')} "
          f"| WARN={F.get('CARBAMATE_CRYST_WARN')} ALARM={F.get('CARBAMATE_CRYST_ALARM')} "
          f"SOLID={F.get('STRIPPER_SOLIDIFICATION')}")
    for k in ("CARB_RECYCLE", "EJ_DISCH", "HPCC_PROD", "REACT_OVERFLOW"):
        d = C.get(k, {})
        print(f"      {k:15s} T_cryst={d.get('T_cryst')} margin={d.get('margin')} "
              f"nc={d.get('nc')} h2o={d.get('h2o_wt')} state={d.get('state')}")
