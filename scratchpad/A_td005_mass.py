"""AGENT A probe 1 -- TD-005 stream-741 recycle: does it CREATE MASS?

Claim under test (commit b678b1c): "The recycle diverts liquid that would otherwise leave the
modelled envelope as the 740 export and returns it to Comp I, so it enters the holdup ODE as an
INFLOW" with NO decrement anywhere.

That claim is only true if m_741 <= the 740 export actually available, i.e. m_739 (328C004
bottoms -> 328E007 -> 740).  m_739 is LIVE (LIC-328504 op / 50).  S741_CAP_KGH is the DESIGN
739 flow, a constant.  So: close LIC-328504 (or trip the C004 feed) so m_739 -> 0, then stroke
FIC-328406 to 100 % and see whether the model still injects ~33.7 t/h into Comp I.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa

s = main.state if hasattr(main, "state") else main.STATE
DT = 0.5


def tel():
    return main.step_sim(DT)


def snap(tag):
    t = tel()
    c4 = t["DESORB_328"]["C004"]
    d3 = t["ABSORB_328"]["D003"]
    print(f"{tag:26s} bot739_th={c4.get('bot739_th'):8.3f} t/h  "
          f"FIC406 m_kgh={d3['FIC_328406'].get('m_kgh'):10.1f}  vol={d3['FIC_328406'].get('vol_m3h'):8.2f}  "
          f"form735={d3.get('form735_th'):7.2f}  LI_328I={d3.get('LI_328I'):7.2f}  LI_328504={c4.get('LI_328504'):6.2f}")


print("S741_CAP_KGH =", main.S741_CAP_KGH, " R328_C004_M739_DES =", main.R328_C004_M739_DES)
print("FIC_328406 sp_hi =", s.FIC_328406["sp_hi"], " mode", s.FIC_328406["mode"])

snap("baseline")

# --- Step 1: stroke the recycle FULL OPEN in MAN while 739 is at design
s.FIC_328406["mode"] = "MAN"
s.FIC_328406["op"] = 100.0
for _ in range(600):
    tel()
snap("FIC-328406 @100%")

# --- Step 2: now KILL the 740 source.  LIC-328504 to MAN 0 -> m_739 -> 0.
s.LIC_328504["mode"] = "MAN"
s.LIC_328504["op"] = 0.0
for _ in range(1200):
    tel()
snap("+ LIC-328504 MAN 0")

# --- Step 3: also starve C004 entirely (FIC-329401 / 749 path) for good measure
for _ in range(2400):
    tel()
snap("+ 20 min more")

print("\nINTERPRETATION: if FIC406 m_kgh stays ~33724 kg/h while bot739_th ~ 0,")
print("the 741 recycle is drawing condensate that the plant never produced -> MASS CREATION.")
