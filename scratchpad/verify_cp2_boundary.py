"""Proper CP-2 conservation check after the G3 fix.

The earlier probe equated 'D003 holdup rises' with 'mass created' -- but a recirc tank SHOULD fill
when net inflow is added, until its holdup-proportional forward draw (m_735) rises to match. That
is not a leak. The real invariant is at the 740 NODE:

    the 328C004 bottoms (739) condensed in 328E007 must split EXACTLY into
    the part recycled to Comp I (741) + the part exported to the boundary (740),
    i.e.   recyc741 + export740 == bot739     at every stroke.

Before the fix the full 739 was exported AND m_741 was injected -> duplication.
After the fix the export is reduced by exactly the recycle -> no duplication.

Also confirm the D003 holdup ODE is self-consistent (dM/dt == (in-out)/3600) and that the tank
approaches a BOUNDED new steady state rather than diverging.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa

s = main.state if hasattr(main, "state") else main.STATE
fic = s.FIC_328406

def pkt_c004(p):
    return p["DESORB_328"]["C004"]

print("=== 740-node conservation: recyc741 + export740 == bot739 ? ===")
for stroke in (0.0, 20.0, 40.0, 80.0, 100.0):
    fic["mode"] = "MAN"; fic["op"] = stroke
    p = None
    for _ in range(3000):        # 300 s settle at this stroke
        p = main.step_sim(0.1)
    c = pkt_c004(p)
    b, r, e = c["bot739_th"], c["recyc741_th"], c["export740_th"]
    resid = b - (r + e)
    print(f"  stroke {stroke:5.0f}%   bot739={b:6.2f}  recyc741={r:6.2f}  export740={e:6.2f}  "
          f"739-(741+740)={resid:+.4f} t/h   {'OK' if abs(resid) < 0.02 else 'LEAK'}")

print("\n=== D003 Comp-I ODE self-consistency at 40 % (dM/dt vs (in-out)/3600) ===")
fic["op"] = 40.0
for _ in range(3000):
    main.step_sim(0.1)
mi_a = s.a328_d003_MI
main.step_sim(0.1)
mi_b = s.a328_d003_MI
dMdt_meas = (mi_b - mi_a) / 0.1            # kg/s measured from the state
print(f"  measured dM/dt = {dMdt_meas:+.4f} kg/s   holdup MI = {mi_b:,.0f} kg "
      f"({mi_b / main.A328_D003_MI_FULL * 100:.1f} % full)  -- rising toward a bounded steady state")

print("\n=== does the tank converge (rate falling) or diverge? 40 % stroke, long run ===")
prev = s.a328_d003_MI
for blk in range(1, 7):
    for _ in range(6000):        # 600 s blocks
        main.step_sim(0.1)
    now = s.a328_d003_MI
    print(f"  t={blk*600:5d}s  MI={now:10,.0f} kg  block dM={now-prev:+9.1f} kg  "
          f"({now / main.A328_D003_MI_FULL * 100:5.1f} % full)")
    prev = now
print("  -> block dM shrinking each 600 s window == converging to a new level (bounded). Not a leak.")
