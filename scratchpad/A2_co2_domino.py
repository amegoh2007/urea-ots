"""AGENT A (2nd pass) -- CO2 battery-limit boundary condition + the HV-322203 -> LT-322504 domino.

Q2  Is the CO2 BL an infinite pressure sink/source?
Q4  Why does HV-322203 bypass the domino on LT-322504?
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa
s = main.state if hasattr(main, "state") else main.STATE
DT = 0.5
def settle(n):
    for _ in range(n): main.step_sim(DT)

print("=== Q2a: analytic structure of the BL ===")
print(f"  SYN_P_MAX_BARA = {main.SYN_P_MAX_BARA}   CO2_P_DES = {main.CO2_P_DES_BARA}  "
      f"SYN_P_DES = {main.SYN_P_DES_BARA}")
DP = main.CO2_P_DES_BARA - main.SYN_P_DES_BARA
ceil = main.SYN_P_MAX_BARA + DP
print(f"  DP_HP_DES = {DP}   P_line_ceil = {ceil}")
for psyn in (90.0, 120.0, 140.7, 144.0, 144.2):
    P_line = min(psyn + DP, ceil)
    dP_HP  = max(P_line - psyn, 0.0)
    phi    = min(1.0, (dP_HP/DP)**0.5)
    print(f"    P_syn={psyn:7.2f} -> P_line={P_line:7.2f}  dP_HP={dP_HP:5.3f}  phi_HP={phi:.6f}")
print("  p_syn_bara is hard-clamped to SYN_P_MAX_BARA (main.py:3654), so dP_HP == DP_HP_DES")
print("  for EVERY reachable loop pressure -> phi_HP is identically 1.0; the 'delivery taper' is dead code.")

settle(600)
tel = main.step_sim(DT)
def co2blk(t):
    for k, v in t.items():
        if isinstance(v, dict) and "raw_th" in v: return v
        if isinstance(v, dict):
            for k2, v2 in v.items():
                if isinstance(v2, dict) and "raw_th" in v2: return v2
    return {}
c = co2blk(tel)
print("\n=== baseline CO2 block ===")
print(" ", {k: c.get(k) for k in ("raw_th","feed_th","vent_th","PV_322203","PIC_322203","load_pct")})

print("\n=== Q2b: raise the synthesis pressure by hand; does the BL feed care? ===")
for p in (120.0, 135.0, 144.2):
    s.p_syn_bara = p
    main.step_sim(DT)
    tel = main.step_sim(DT); c = co2blk(tel)
    print(f"  p_syn forced {p:6.2f} -> line P {c.get('PIC_322203')}  feed_th {c.get('feed_th')} "
          f"vent_th {c.get('vent_th')}")
settle(600)

print("\n=== Q4: HIC-322203 vent sweep -> full domino chain ===")
hdr = ("  HIC   PV%   lineP   raw   feed   vent  Load%   p_syn   react_lvl%  LT322504  "
       "strip_lvl  TT322004  P_MP")
print(hdr)
def row(hic):
    tel = main.step_sim(DT); c = co2blk(tel)
    tt = None
    def deep(o, key):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == key: return v
                r = deep(v, key)
                if r is not None: return r
        return None
    tt = deep(tel, "TT_322004")
    print(f"  {hic:4.0f} {c.get('PV_322203'):5.1f} {c.get('PIC_322203'):7.2f} "
          f"{c.get('raw_th'):6.2f} {c.get('feed_th'):6.2f} {c.get('vent_th'):6.2f} "
          f"{c.get('load_pct') if c.get('load_pct') is not None else float('nan'):6} "
          f"{s.p_syn_bara:8.3f} {s.react_level_pct:10.2f} {s.react_lt322504_pct:9.1f} "
          f"{s.strip_level:9.2f}  {tt}  {s.steam.P_MP:.3f}")
row(0)
for hic in (5.0, 10.0, 14.0, 20.0, 50.0, 100.0):
    s.HIC_322203 = hic
    settle(1200)      # 10 min each (BL->loop dead time is 345 s)
    row(hic)
print("\n  ... hold 100 % vent for another 30 min ...")
settle(3600)
row(100.0)

print("\n=== conservation check: raw == feed + vent ? ===")
tel = main.step_sim(DT); c = co2blk(tel)
print(f"  raw={c.get('raw_th')}  feed+vent={round(c.get('feed_th')+c.get('vent_th'),3)}")
