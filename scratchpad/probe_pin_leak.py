"""Is the strength pin ITSELF the source of the linear composition drift?

The 6-hour run showed w_f010 falling at a dead-constant -0.00167 points per 15 min, with the second
difference exactly 0.000000.  A perfectly linear drift is not a settling transient -- it is a
constant rate imbalance.

Hypothesis: sol_pin_strength is a COMPONENT MASS SOURCE.  It does

    share = 1 - sum(minor species)
    out["Urea"] = w_urea_auth
    out["H2O"]  = share - out["Urea"]

which preserves sum(w) = 1 but REWRITES the urea/water split.  At constant total mass that creates
urea and destroys water (or the reverse) on every tick, in every vessel where it is applied --
D002, E001 and E003.  Fabricated urea then leaves as product and the water deficit propagates
around the recycle, which would show up exactly as a slow linear composition drift.

If that is right, then dropping the pin does NOT import the drift -- it REMOVES its cause.

Test: run the same measurement with the pins neutralised and compare the slopes.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main as M  # noqa: E402

DT = 0.25
MIN = int(60.0 / DT)
MINUTES = 90


def measure(tag):
    for _ in range(MIN * 5):          # settle
        M.step_sim(DT)
    s = M.state
    marks = []
    for minute in range(1, MINUTES + 1):
        for _ in range(MIN):
            M.step_sim(DT)
        if minute % 15 == 0:
            marks.append(100.0 * s.w_f010.get("Urea", 0.0))
    slopes = [marks[i] - marks[i - 1] for i in range(1, len(marks))]
    print("  %-22s marks %s" % (tag, ["%.5f" % m for m in marks]))
    print("  %-22s slope/15min %s" % ("", ["%+.5f" % d for d in slopes]))
    return sum(slopes) / len(slopes)


print("how much urea mass does the pin fabricate per call?")
w = {"Urea": 0.7994, "H2O": 0.1953, "Biuret": 0.0042, "NH3": 0.0006,
     "CO2": 0.0003, "HCHO": 0.0002}
before = dict(w)
after = M.sol_pin_strength(w, 0.80)
d_urea = after["Urea"] - before["Urea"]
d_h2o = after["H2O"] - before["H2O"]
print("  in  Urea %.6f  H2O %.6f  (sum %.9f)" % (before["Urea"], before["H2O"], sum(before.values())))
print("  out Urea %.6f  H2O %.6f  (sum %.9f)" % (after["Urea"], after["H2O"], sum(after.values())))
print("  delta Urea %+.6f   delta H2O %+.6f   net %+.9f" % (d_urea, d_h2o, d_urea + d_h2o))
print("  -> sum(w) is preserved, but urea is CONVERTED TO/FROM water.  At a fixed vessel mass that")
print("     is a component-balance source: %+.3f kg of urea per 1000 kg of holdup, per call."
      % (d_urea * 1000.0))
print()

print("BASELINE -- pins active (current shipped behaviour):")
base = measure("pinned")

print()
print("PINS NEUTRALISED -- sol_pin_strength becomes the identity:")
M.sol_pin_strength = lambda w, a: dict(w)
free = measure("unpinned")

print()
print("  mean slope pinned   : %+.6f points / 15 min" % base)
print("  mean slope unpinned : %+.6f points / 15 min" % free)
print()
if abs(free) < 0.25 * abs(base):
    print("VERDICT: the drift LARGELY DISAPPEARS without the pin.")
    print("  => the pin was CAUSING the drift, not protecting against it.  Dropping it removes the")
    print("     cause rather than importing the symptom, which is what the user asked for.")
elif abs(free) > 1.5 * abs(base):
    print("VERDICT: the drift gets WORSE without the pin -- the pin really was holding a real leak.")
    print("  => find the upstream leak before dropping the pin.")
else:
    print("VERDICT: comparable slopes -- the pin is not the dominant cause; the leak is elsewhere.")
