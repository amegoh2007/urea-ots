"""AUDIT probe: 323/324 design fixed-point invariance + off-design duty response.

Phase 1  boot -> step at design -> the 323 flash / 324 evaporator anchors must not drift.
Phase 2  cut the Evap-I steam (PIC-329203 MAN 0 %) -> the melt MUST dilute (was impossible).
Phase 3  restore, then cut 323E002 steam (PIC-329202 MAN 0 %) -> 305 boil-up MUST collapse.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main  # noqa: E402

s = main.state


def run(seconds, dt=0.25):
    out = None
    for _ in range(int(seconds / dt)):
        out = main.step_sim(dt)
    return out


def row(tag, t):
    e1, e3 = t["EVAP_324"]["E001"], t["EVAP_324"]["E003"]
    c3, f4, f10 = t["RECIRC_323"]["C003"], t["RECIRC_323"]["F004"], t["RECIRC_323"]["F010"]
    print(f"{tag:<12} | 324 E1 w%={e1['urea_pct']:<6} v={e1['vapour_th']:<7} Q={e1['Q_kW']:<7} "
          f"T={e1['TT_324001']:<6} | E3 w%={e3['urea_pct']:<6} v={e3['vapour_th']:<6} T={e3['TT_324002']:<6} "
          f"| 323 C003 T={c3['TT_323002']:<6} v305={c3['v305_th']:<7} Q={c3['Q_kW']:<6} "
          f"F004 T={f4['TT_323005']:<6} v701={f4['v701_th']:<6} F010 ev={f10['evap_th']}")


print("=== Phase 1 : design fixed point ===")
for i in range(8):
    row(f"t={(i+1)*60:>4}s", run(60.0))

print("\n=== Phase 2 : Evap-I steam cut (PIC-329203 MAN 0 %) ===")
s.PIC_329203["mode"] = "MAN"; s.PIC_329203["op"] = 0.0
s.TIC_324001["mode"] = "MAN"
for i in range(8):
    row(f"cut+{(i+1)*60:>4}s", run(60.0))

print("\n=== Phase 3 : restore 324, then 323E002 steam cut (PIC-329202 MAN 0 %) ===")
s.PIC_329203["mode"] = "AUTO"; s.TIC_324001["mode"] = "AUTO"
run(300.0)
s.PIC_329202["mode"] = "MAN"; s.PIC_329202["op"] = 0.0
s.TIC_323007["mode"] = "MAN"
for i in range(8):
    row(f"cut+{(i+1)*60:>4}s", run(60.0))
