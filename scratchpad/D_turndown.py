"""AGENT D probe 2 -- turndown: specific steam, crystallization margins, loop response."""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
import steam_system as ss
s = main.state if hasattr(main, "state") else main.STATE

DT = 0.1
def run(n):
    for _ in range(n): main.step_sim(DT)

def snap(tag):
    t = main.step_sim(DT)
    st = s.steam
    cry = t.get("CRYST", {})
    u = t.get("U322", {}) or {}
    row = {
        "tag": tag,
        "F_CO2_th": round(s.F_CO2_th, 3),
        "m_supply_kgs": round(st.m_supply, 4),
        "m_hpcc_kgs": None,
        "P_MP": round(st.P_MP, 3), "P_9": round(st.P_9, 3), "P_LP": round(st.P_LP, 3),
        "FT403": t.get("U329", {}).get("FT_329403_th"),
        "FT407": t.get("U329", {}).get("FT_329407_th"),
    }
    return row, cry, t

print("### settling baseline")
run(6000)
r0, c0, t0 = snap("100% load")
print(json.dumps(r0, indent=1))
print("CRYST @100%:")
for k, v in c0.items():
    print(f"   {k:16s} {v}")

# find urea production telemetry
def prod(t):
    for grp in ("U324", "U323", "U335", "U322"):
        g = t.get(grp) or {}
        for k in g:
            if "prod" in k.lower() or "MTPD" in k or "urea" in k.lower():
                pass
    return None

print("\n### telemetry group keys:", list(t0.keys()))
u329 = t0.get("U329") or {}
print("U329 steam keys:", {k: v for k, v in u329.items() if "329" in k})

# ---------- TURNDOWN: vent CO2 via HIC-322203 ----------
print("\n### TURNDOWN to ~70% load (HIC-322203 vent 30%)")
s.HIC_322203 = 30.0
marks = {int(x/DT) for x in (60, 300, 900, 1800, 3600)}
for k in range(1, int(3600/DT)+1):
    main.step_sim(DT)
    if k in marks:
        r, c, t = snap("x")
        print(f" t={k*DT:6.0f}s CO2={s.F_CO2_th:6.3f} t/h  m_supply={s.steam.m_supply:.4f} kg/s"
              f"  P_MP={s.steam.P_MP:.3f} P_LP={s.steam.P_LP:.3f}"
              f"  FT403={t.get('U329',{}).get('FT_329403_th')}"
              f"  FT407={t.get('U329',{}).get('FT_329407_th')}")

r1, c1, t1 = snap("turndown")
print("\nCRYST @ turndown:")
for k, v in c1.items():
    print(f"   {k:16s} {v}")
print("flags:", {k: v for k, v in s.flags.items() if "CRYST" in k})

load_frac = s.F_CO2_th / 54.618
print(f"\nload fraction = {load_frac:.4f}")
print(f"MP steam at turndown  = {s.steam.m_supply*3.6:.3f} t/h "
      f"(design 76.670 t/h)  ratio {s.steam.m_supply/ss.M_STRIP_DES:.4f}")
print(f"specific MP steam vs load: {(s.steam.m_supply/ss.M_STRIP_DES)/max(load_frac,1e-9):.4f}"
      "  (1.0 = perfectly load-following; >1 = steam wasted at turndown)")
