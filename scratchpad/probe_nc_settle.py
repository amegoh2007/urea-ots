"""Does the eta_P coupling merely SLOW the N/C settle, or destabilise it?

test_split_does_not_self_excite_on_an_nc_disturbance passed at HEAD and fails now.  That test
exists to catch exactly this: a new feedback path whose loop gain is too high.  Waking eta_P added
a path that did not exist before -- p_syn -> stripper split -> overhead -> HPCC -> loop -> p_syn --
so the test is doing its job and the burden is on the change, not the test.

Distinguishing the two possibilities is the whole point:
  * converging but slower  -> extra physical lag, legitimate; the 10-minute window is now too short
  * diverging or ringing   -> the coupling is wrong and must be reworked, not accommodated

Relaxing a stability threshold to make a change pass is only defensible if the first case is shown
to hold, so this runs the same disturbance far past the test window and reports the trend.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main  # noqa: E402


def run(seconds, dt=0.25):
    t = None
    for _ in range(int(seconds / dt)):
        t = main.step_sim(dt)
    return t


run(300.0)
s = main.state
s.ratio_SP = 0.92 * main.RATIO_SP_DES
print("N/C disturbance applied: ratio_SP = 0.92 * design\n")
print("  %6s  %12s  %10s  %10s" % ("min", "T_prod", "delta", "p_syn"))
tp = []
prev = None
for i in range(1, 41):                      # 40 minutes, 4x the test window
    run(60.0)
    v = s.tlag["HPCC_TPROD"]
    tp.append(v)
    d = (v - prev) if prev is not None else float("nan")
    prev = v
    if i <= 12 or i % 4 == 0:
        print("  %6d  %12.5f  %+10.5f  %10.4f" % (i, v, d, s.p_syn_bara))

w = 5
print("\n  rolling %d-sample span (the quantity the test asserts < 0.5):" % w)
for i in range(w, len(tp) + 1, 5):
    seg = tp[i - w:i]
    print("     minutes %2d-%2d : %.5f" % (i - w + 1, i, max(seg) - min(seg)))

final = tp[-w:]
span = max(final) - min(final)
print("\n  final %d-sample span: %.5f" % (w, span))
deltas = [abs(tp[i] - tp[i - 1]) for i in range(1, len(tp))]
print("  |delta| first 5: %s" % ["%.4f" % d for d in deltas[:5]])
print("  |delta| last  5: %s" % ["%.4f" % d for d in deltas[-5:]])
shrinking = sum(deltas[-5:]) < sum(deltas[:5])
print("\n  VERDICT: %s" % ("CONVERGING (step sizes shrinking) -- extra lag, not instability"
                           if shrinking and span < 0.5 else
                           "converging but still outside 0.5 at 40 min" if shrinking else
                           "NOT CONVERGING -- the coupling is wrong, rework it"))
