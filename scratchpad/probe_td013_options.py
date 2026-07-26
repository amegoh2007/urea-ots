"""TD-013 -- which ripple fix is actually viable, given the 1/alpha amplification.

The recursion analysis kills a whole class of fix.  323D002 exchanges alpha = 9.5e-5 of its holdup
per tick, so ANY additive correction applied INSIDE its own integration loop is integrated and
amplified by 1/alpha ~ 10 500.  That rules out:
    auth = w_bal + (A - ref)              <- the reverted patch
    auth = w_bal + constant_offset
    auth = w_bal * constant_ratio
all of which put a constant inside the loop.  Only two forms survive:

  (b) NON-RECURSIVE assignment from an upstream variable the pin does not touch:
          auth = A + (w_f010 - W_F010_DES)
      Stable and bit-exact at design, but the tank then tracks its inlet with no lag.

  (c) NO PIN -- let sol_advance run.  Correct dynamics AND correct lag, but D002 then inherits
      whatever w_f010 does, including any slow drift.

The deciding question is therefore: does w_f010 SETTLE, or does it drift secularly?  If it settles,
(c) is plainly right.  If it drifts without bound, (c) imports that drift into the product spec and
(b) or a reconciliation upstream is needed.  This measures it over a long run.
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

s = M.state
print("tracking 323F010 outlet composition (= 323D002 inlet) over 6 simulated hours")
print("  %8s  %14s  %14s  %14s" % ("sim min", "w_f010 %", "delta/15min", "d(delta)"))

prev = None
prev_d = None
hist = []
for minute in range(1, 361):
    for _ in range(MIN):
        M.step_sim(DT)
    w = 100.0 * s.w_f010.get("Urea", 0.0)
    hist.append(w)
    if minute % 15 == 0:
        d = (w - prev) if prev is not None else float("nan")
        dd = (d - prev_d) if prev_d is not None else float("nan")
        print("  %8d  %14.5f  %+14.5f  %+14.6f" % (minute, w, d, dd))
        prev, prev_d = w, d

print()
first_h = hist[59] - hist[0]
last_h = hist[359] - hist[299]
print("  drift in hour 1 : %+.5f points" % first_h)
print("  drift in hour 6 : %+.5f points" % last_h)
print("  total 6 h       : %+.5f points" % (hist[-1] - hist[0]))
print()
if abs(last_h) < 0.1 * abs(first_h) or abs(last_h) < 1e-3:
    print("VERDICT: w_f010 is SETTLING -- the drift decays, it is a slow transient not a leak.")
    print("  => option (c) (drop the pin) is safe; D002 follows its inlet to a real steady state.")
else:
    print("VERDICT: w_f010 is still drifting at %+.5f points/h in hour 6 -- NOT settled." % last_h)
    print("  => dropping the pin would import that drift into the 324 feed spec.")
    print("     The pin is doing real work, and the drift itself needs explaining first.")
print()
print("  PFD publishes urea to 2 decimal places, so its own precision is +-0.005 points.")
print("  Current test tolerance on D002 is 1e-6 points, i.e. 5000x tighter than the source.")
