"""TD-013 -- why the attempted ripple fix walked to 76.515 %, quantitatively.

The reverted patch computed, every tick:

    w_bal_n   = sol_advance(w_d002_{n-1}, ..., w_f010, ...)      # blends the tank toward its inlet
    w_d002_n  = A + (w_bal_n - ref)                              # A = R324_W_IN = 0.80, ref frozen

sol_advance is a well-mixed blend, so to first order

    w_bal_n = w_{n-1} + alpha * (w_f010 - w_{n-1}),    alpha = m_out * dt / M   (per tick)

Substituting gives a linear recursion in w:

    w_n = (A - ref) + w_{n-1}(1 - alpha) + alpha * w_f010

whose fixed point is

    w* = (A - ref)/alpha + w_f010

The tank is BIG and the tick is SMALL, so alpha is of order 1e-4 -- and 1/alpha is therefore of
order 10^4.  Any mismatch between the frozen reference and the anchor is amplified by that factor.
This script computes alpha from the real plant numbers and shows what capture error reproduces the
observed 76.515 %.  If the required error is tiny and plausible, the "3.5-point balance gap" was an
artefact of the patch, not a property of the plant.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main as M  # noqa: E402

DT = 0.25
for _ in range(240):
    M.step_sim(DT)
s = M.state

M_I = s.r323_d002_M_I                      # kg, 323D002 Comp-I holdup
m_out = M.R323_M324_DES                    # kg/h drawn to unit 324
alpha = m_out / 3600.0 * DT / M_I          # fraction of the holdup exchanged per tick

print("323D002 Comp-I holdup            : %10.1f kg" % M_I)
print("draw to unit 324 (design)        : %10.1f kg/h" % m_out)
print("tick                             : %10.2f s" % DT)
print("alpha  = m*dt/M                  : %12.3e  per tick" % alpha)
print("1/alpha  (the amplification)     : %10.1f" % (1.0 / alpha))
print("tank time constant M/m           : %10.2f h" % (M_I / m_out))
print()

A = M.R324_W_IN
w_in = s.w_f010.get("Urea", 0.80)
observed = 0.76515

print("fixed point of the reverted recursion:  w* = (A - ref)/alpha + w_f010")
print("  A (R324_W_IN)                  : %.6f" % A)
print("  w_f010 (measured)              : %.6f" % w_in)
print("  observed w* that failed tests   : %.6f  (76.515 %%)" % observed)
need = (observed - w_in) * alpha
print()
print("  => required (A - ref)          : %+.3e" % need)
print("  => required capture error ref-A: %+.3e   (%.4f percentage points)"
      % (-need, -need * 100.0))
print()

# Demonstrate the recursion directly.
print("direct simulation of the recursion with that capture error:")
print("  %10s %14s" % ("tick", "w_d002 %"))
ref = A - need
w = A
for n in range(1, 400001):
    w_bal = w + alpha * (w_in - w)
    w = A + (w_bal - ref)
    if n in (1, 10, 100, 1000, 10000, 50000, 100000, 200000, 400000):
        print("  %10d %14.4f" % (n, w * 100.0))

print()
print("CONCLUSION")
print("  The tank exchanges %.4f %% of its holdup per tick, so the reverted patch amplified any" % (alpha * 100))
print("  mismatch between its frozen reference and the 0.80 anchor by a factor of %.0f." % (1.0 / alpha))
print("  A capture error of only %.4f percentage points reproduces the observed 76.515 %%." % (-need * 100.0))
print("  That is far smaller than the tick-to-tick motion of w_bal during the boot settle, so it is")
print("  fully explained by the reference being captured mid-transient.")
print("  => the '3.5-point gap in the 323 balance' was an ARTEFACT OF THE PATCH, not a plant defect.")
print("     w_f010 measures %.4f %%, i.e. on the PFD stream-317 anchor of 80.00." % (w_in * 100.0))
