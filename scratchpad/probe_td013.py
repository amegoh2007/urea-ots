"""TD-013 -- does the 323 balance really miss the PFD's 80.00 % urea, or did I mis-measure?

Last turn I concluded "the 323 balance converges to 76.515 %".  That number came from a test run
of a few simulated minutes while the pin carried a live deviation off a reference captured on the
first post-boot tick.  323D002 Comp-I holds ~92 t against ~93 t/h throughput, so its time constant
is about an HOUR -- a few minutes is nowhere near converged, and the reference may itself have been
captured mid-transient.  So 76.515 could be drift, not a converged balance, and the whole TD-013
finding could be an artefact of my own measurement.

Decisive test.  323D002 Comp-I has ONE inlet (m_317 carrying w_f010) and one outlet (m_324), with
no reaction and no vapour.  A well-mixed tank like that must satisfy, at steady state,

        w_D002  ==  w_f010

So the question is not "what does D002 converge to" but "what is 323F010 actually producing".
Read w_f010 directly and compare with the PFD stream-317 anchor of 80.00 %.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main as M  # noqa: E402

DT = 0.25


def run(seconds):
    n = int(seconds / DT)
    for _ in range(n):
        M.step_sim(DT)


s = M.state
print("PFD stream 317 anchor            : 80.00 %% urea")
print("R324_W_IN (the pin's authority)  : %.4f" % M.R324_W_IN)
print()

run(120.0)
print("after 2 min settle:")
print("  w_f010['Urea']  (323F010 out, = D002 inlet) : %.4f  -> %.3f %%"
      % (s.w_f010.get("Urea", 0.0), 100.0 * s.w_f010.get("Urea", 0.0)))
print("  w_d002['Urea']  (tank, PINNED)              : %.4f  -> %.3f %%"
      % (s.w_d002.get("Urea", 0.0), 100.0 * s.w_d002.get("Urea", 0.0)))

# The pin overwrites w_d002 every tick, so read what the BALANCE would have produced by running
# sol_advance exactly as the tick does, but without the pin on top.
print()
print("what the unpinned balance produces, followed out to convergence")
print("(tank tau ~1 h, so this is the run the test suite never does):")
print("  %8s  %12s  %12s  %12s" % ("sim min", "w_f010 %", "unpinned %", "pinned %"))

w_unpinned = dict(s.w_d002)
for minute in range(1, 121):
    for _ in range(int(60.0 / DT)):
        M.step_sim(DT)
        # mirror the tick's own balance on a shadow vector, with NO pin applied
        w_unpinned = M.sol_advance(w_unpinned, s.r323_d002_M_I, s.r323_d002_M_I,
                                   s.tlag.get("R323_m317", 0.0) or 0.0, s.w_f010,
                                   0.0, w_unpinned, 0.0, 0.0, DT)
    if minute in (1, 2, 5, 10, 20, 30, 45, 60, 90, 120):
        print("  %8d  %12.4f  %12.4f  %12.4f"
              % (minute, 100.0 * s.w_f010.get("Urea", 0.0),
                 100.0 * w_unpinned.get("Urea", 0.0),
                 100.0 * s.w_d002.get("Urea", 0.0)))

f010 = 100.0 * s.w_f010.get("Urea", 0.0)
print()
print("VERDICT")
if abs(f010 - 80.0) < 0.10:
    print("  323F010 delivers %.3f %% urea, i.e. ON the PFD anchor." % f010)
    print("  => TD-013 as I wrote it is WRONG.  The tank's inlet is correct, so the tank must")
    print("     converge to 80.00 too, and 76.515 was my capture reference taken mid-transient.")
    print("     The ripple fix is salvageable: anchor the deviation on w_f010, not on a snapshot.")
else:
    print("  323F010 delivers %.3f %% urea against the PFD's 80.00 -- a %.3f point gap." % (f010, f010 - 80.0))
    print("  => TD-013 is REAL and sits upstream of the tank, in the 323F010 flash / 323E010 feed.")
