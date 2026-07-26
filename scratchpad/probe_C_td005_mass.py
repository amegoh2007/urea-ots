"""AGENT C: TD-005 -- does the 741 recycle CREATE mass?

The commit claims 741 'diverts liquid that would otherwise leave the modelled envelope as the
740 export'.  If that is true, opening FV-328406 must REDUCE some export by the same kg/h.
Grep shows no m_740 mass variable exists; m_739 (the 328C004 bottoms that feeds 328E007 -> 740)
is computed purely from LIC-328504.  So test it: stroke the valve and watch m_739 and Comp-I.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state if hasattr(main, "state") else main.STATE
DT = 0.1
def g(t,p):
    c=t
    for k in p.split("."):
        c = c[k] if isinstance(c,dict) and k in c else None
        if c is None: return None
    return c

for _ in range(6000): t = main.step_sim(DT)
def snap(t, tag):
    print(f"{tag:22s} m741={g(t,'ABSORB_328.D003.FIC_328406.m_kgh'):9.1f} kg/h   "
          f"LIC504_op={s.LIC_328504['op']:7.3f}  m739={main.R328_C004_M739_DES*(s.LIC_328504['op']/50.0):9.1f} kg/h   "
          f"CompI_M={s.a328_d003_MI:10.1f} kg  CompI_T={s.a328_d003_TI:7.3f} C  "
          f"CompII_M={getattr(s,'a328_d003_MII',float('nan')):.1f}")
snap(t, "design (valve shut)")
m739_0 = main.R328_C004_M739_DES*(s.LIC_328504['op']/50.0)
MI0 = s.a328_d003_MI

s.FIC_328406["mode"] = "MAN"; s.FIC_328406["op"] = 50.0
for k in range(1, 36001):
    t = main.step_sim(DT)
    if k in (6000, 18000, 36000):
        snap(t, f"MAN 50 % t={k*DT:.0f}s")
m741 = g(t,'ABSORB_328.D003.FIC_328406.m_kgh')
m739_1 = main.R328_C004_M739_DES*(s.LIC_328504['op']/50.0)
print(f"\n741 recycle injected      : {m741:9.1f} kg/h")
print(f"739/740 export change     : {m739_1 - m739_0:+9.1f} kg/h   (must be {-m741:+9.1f} if it is a real DIVERSION)")
print(f"Comp-I holdup change      : {s.a328_d003_MI - MI0:+9.1f} kg over 3600 s")
print("VERDICT:", "MASS CONSERVED" if abs((m739_1-m739_0) + m741) < 1.0 else "MASS CREATED FROM NOTHING")
