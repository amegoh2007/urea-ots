"""READ-ONLY analysis probe: is  auth = A + (f(w_prev) - ref)  with  w_prev <- auth
a STABLE or an UNSTABLE recursion, and how big an amplification does it apply?

f() is exactly what sol_advance does to the Urea component of 323D002 Comp-I:
    out_k = M*w_k + (m_in*w_in_k - m_out*w_k)*dt/3600      (m_vap = 0, xi = 0)
    tot   = M     + (m_in        - m_out       )*dt/3600
    f(w)  = out_Urea/tot = lambda*w + (1-lambda)*w_in ,  lambda = (M - m_out*dt/3600)/tot
So f is an affine CONTRACTION toward w_in with pole lambda < 1.  Nothing here is imported
from backend/ except the design constants, so this file cannot perturb the sim.
"""
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa

M     = main.R323_D002_M_I_DES
m_in  = main.R323_M317_DES
m_out = main.R323_M324_DES
A     = main.R324_W_IN
W317  = main.W_S317["Urea"]

print(f"M_I_DES   = {M:.3f} kg")
print(f"m_317_DES = {m_in:.3f} kg/h   m_324_DES = {m_out:.3f} kg/h")
print(f"tau       = M/m = {M/m_in:.4f} h = {M/m_in*3600:.1f} s")
print(f"A = R324_W_IN = {A!r}   W_S317['Urea'] (normalised) = {W317!r}")
print(f"W_S317['Urea'] - R324_W_IN = {W317-A:.6e}  ({(W317-A)*100:+.6f} pp)")
print()


def pole(dt):
    a = m_in * dt / 3600.0
    b = m_out * dt / 3600.0
    tot = M + a - b
    lam = (M - b) / tot
    return lam, 1.0 - lam


for dt in (0.25, 0.5, 1.0):
    lam, mu = pole(dt)
    print(f"dt={dt:<5} lambda={lam!r}  mu=1-lambda={mu:.6e}  amplification 1/mu={1/mu:.1f}")
print()
print("lambda < 1 for every dt > 0  ->  the recursion is STABLE (a contraction), NOT divergent.")
print("But the FIXED POINT is  w* = w_in + (A - ref)/mu , so a frozen-reference mismatch is")
print("amplified by 1/mu = tau/dt ~ thousands.")
print()

# ---------------- numerical demonstration -------------------------------------------------
def run(dt, w_in, ref, n, w0):
    """Replay auth = A + (f(w_prev) - ref) ; w_prev <- auth."""
    lam, mu = pole(dt)
    w = w0
    traj = []
    for i in range(n):
        wbal = lam * w + (1.0 - lam) * w_in
        w = A + (wbal - ref)
        if i % max(1, n // 10) == 0:
            traj.append((i * dt, w))
    return w, traj, lam, mu


DT = 0.25
lam, mu = pole(DT)
w_in = W317                                  # 323F010 delivers the PFD stream-317 anchor

print("=== case 1: reference captured from an ALREADY-PINNED previous tick (w_prev = 0.80) ===")
ref1 = lam * A + (1 - lam) * w_in
w1, tr1, _, _ = run(DT, w_in, ref1, int(6 * 3600 / DT), A)
print(f"ref = {ref1!r}   A - ref = {A-ref1:.6e}")
print(f"predicted w* = w_in + (A-ref)/mu = {w_in + (A-ref1)/mu:.9f}")
print(f"after 6 h: w_d002 = {w1*100:.6f} %   -> stays on the anchor")
print()

print("=== case 2: reference captured ONE TICK EARLIER, i.e. from the UNPINNED seed ===")
print("    (w_prev = W_S317['Urea'] = 0.80001624, the value State() seeds w_d002 with)")
ref2 = lam * W317 + (1 - lam) * w_in
print(f"ref = {ref2!r}   A - ref = {A-ref2:.6e}   (= -(W317-A) = -1.62e-5)")
print(f"predicted w* = {w_in + (A-ref2)/mu:.9f}  ({(w_in + (A-ref2)/mu)*100:.4f} %)")
w2, tr2, _, _ = run(DT, w_in, ref2, int(6 * 3600 / DT), A)
print("   t[s]      w_d002 %")
for t, w in tr2:
    print(f"  {t:8.0f}   {w*100:.4f}")
print(f"after 6 h: {w2*100:.4f} %")
# when does it pass 76.515 ?
w = A
t = 0.0
hit = None
for i in range(int(24 * 3600 / DT)):
    w = A + (lam * w + (1 - lam) * w_in) - ref2
    t += DT
    if hit is None and w <= 0.76515:
        hit = t
print(f"crosses 76.515 % at t = {hit} s of sim time ({hit/60.0 if hit else float('nan'):.1f} min)")
print()
print("REQUIRED reference error to explain 76.515 % at full convergence:")
print(f"   (A-ref) = (0.76515 - w_in)*mu = {(0.76515 - w_in)*mu:.6e}   "
      f"i.e. {abs((0.76515-w_in)*mu)*100:.7f} pp  -- FIVE parts per million.")
