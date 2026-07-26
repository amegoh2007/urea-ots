"""AGENT D probe 4 -- FFIC-329401 ratio blindness to the real 328C004 feed (m_749),
plus the low-grade heat-rejection inventory."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state if hasattr(main, "state") else main.STATE
DT = 0.1
def settle(n):
    p = None
    for _ in range(n): p = main.step_sim(DT)
    return p

p = settle(6000)
d = (p.get("DESORB_328") or {})
print("DESORB_328 keys:", list(d.keys()))
print(json.dumps({k: v for k, v in d.items() if not isinstance(v, dict)}, indent=1)[:2000])

def show(tag):
    ff = s.FFIC_329401; fi = s.FIC_329401; lic = s.LIC_328505
    print(f"\n[{tag}]")
    print(f"  LIC-328505 op={lic['op']:.3f}%  (sets m_747 -> m_749, the REAL 328C004 feed)")
    print(f"  FFIC-329401 pv={ff['pv']:.6f} sp={ff['sp']:.6f} op={ff['op']:.2f} kg/h  mode={ff['mode']}")
    print(f"  FIC-329401  pv={fi['pv']:.2f} sp={fi['sp']:.2f} op={fi['op']:.3f}%  mode={fi['mode']}")

show("baseline")
lic0 = s.LIC_328505["op"]
# force the REAL desorber-II feed down 25% via LIC-328505 in MAN
s.LIC_328505["mode"] = "MAN"
s.LIC_328505["op"] = lic0 * 0.75
print(f"\n>>> LIC-328505 to MAN, op {lic0:.2f} -> {s.LIC_328505['op']:.2f} "
      f"(m_749 feed to 328C004 cut 25%)")
for t in (300, 900, 1800):
    settle(int(300/DT) if t == 300 else int(600/DT))
    show(f"t={t}s")

print("\n--- energy rejection inventory (low-grade heat dumped to cooling/tempered water) ---")
sc = (p.get("SCRUB_322E003") or {}).get("ccw") or {}
print("  329E004 tempered-water cooler duty  =", sc.get("E004_duty_kW"), "kW")
print("  322E003 CCW removed Q_ccw           =", sc.get("Q_ccw_kW"), "kW")
print("  323E003 LPCC tempered-water design  =", main.R3232_E003_Q_DES_KW, "kW  (55/65 C)")
print("  328E007 recovered (datasheet)       = 2649 kW")
print("  328E021 recovered (datasheet)       = 1423 kW")
print("  328E001 rejected to CW (datasheet)  = 2834 kW")
print("  HPCC LP raised                      =", main.M_HPCC_DES_LIVE*main.HPCC_LATENT_4BAR, "kW")
print("  PFD 918 LP steam raised             =", 68928/3600*2130.5, "kW")
