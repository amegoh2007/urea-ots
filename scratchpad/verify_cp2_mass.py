"""Independent check of the Red Team's CP-2: does the TD-005 stream-741 recycle create mass?

The claim: m_741 is added to in_compI (328D003 Comp-I) as an inflow, but the stream it recycles
(740 = 739 condensate) already left the modelled envelope from 328C004 and is NOT tracked as a
D003 outflow. So opening FIC-328406 injects mass with no matching source or decrement.

Method: instrument the Comp-I holdup ODE directly. At each tick the balance MUST be
    dM/dt == (in_compI - out_compI)/3600
If m_741 has no offsetting term, then opening FIC-328406 makes in_compI jump while out_compI and
the upstream feeds do not, and dM/dt turns positive out of nowhere -> unbounded accumulation.

Run two cases:
  A) FIC-328406 at 0 % (design)  -> must be byte-identical to pre-741 (m_741==0)
  B) FIC-328406 stroked in MAN    -> watch a328_d003_MI and whether any other term compensates
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa

s = main.state if hasattr(main, "state") else main.STATE
fic = s.FIC_328406

def settle(n=300, dt=0.1):
    for _ in range(n):
        main.step_sim(dt)

print("=== CASE A: FIC-328406 MAN 0 % (design) ===")
fic["mode"] = "MAN"; fic["op"] = 0.0
settle(600)
mi0 = s.a328_d003_MI
for _ in range(6000):            # 600 s
    main.step_sim(0.1)
print(f"  Comp-I holdup dM over 600 s at 0 % stroke: {s.a328_d003_MI - mi0:+.3f} kg  (expect ~0)")

print("\n=== CASE B: FIC-328406 MAN 40 % stroke ===")
fic["op"] = 40.0
mi1 = s.a328_d003_MI
pkt = main.step_sim(0.1)
# dig the published recycle out of the telemetry tree
d003 = pkt["units"]["328-2"]["D003"] if "328-2" in pkt.get("units", {}) else None
# fall back: just report state growth
t0 = s.a328_d003_MI
for k in range(1, 6001):
    main.step_sim(0.1)
    if k in (600, 3000, 6000):
        print(f"  t={k/10:6.1f}s  Comp-I holdup = {s.a328_d003_MI:12.1f} kg   "
              f"dM since 40% = {s.a328_d003_MI - mi1:+12.1f} kg   "
              f"rate = {(s.a328_d003_MI - mi1)/(k/10)*3600:+.0f} kg/h")

grew = s.a328_d003_MI - mi1
print(f"\nVERDICT: {'MASS CREATED — accumulates ' + format(grew/(6000*0.1)*3600, '+.0f') + ' kg/h with no source' if grew > 100 else 'balance holds'}")
