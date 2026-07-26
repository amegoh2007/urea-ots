"""READ-ONLY: pin down the 76.515 %.  Replays the reverted fix's recursion at the TEST harness's
own dt (test_equation_audit_323_324.py DT = 0.25) and reports the value at the exact horizons the
failing tests use (_fresh(300.0) / _fresh(600.0))."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa

M, m_in, m_out = main.R323_D002_M_I_DES, main.R323_M317_DES, main.R323_M324_DES
A, W317 = main.R324_W_IN, main.W_S317["Urea"]
print("PFD row 317 raw sum =",
      80.00 + 0.42 + 0.08 + 0.02 + 19.47 + 0.00797, " -> _w_norm lifts 80.00 to", repr(W317))

for DT in (0.25, 0.5):
    a, b = m_in * DT / 3600.0, m_out * DT / 3600.0
    tot = M + a - b
    lam = (M - b) / tot
    mu = 1.0 - lam
    w_in = W317
    ref = lam * W317 + (1 - lam) * w_in          # reference frozen on the UNPINNED seed
    print(f"\n--- dt={DT}  lambda={lam:.12f}  1/mu={1/mu:.1f}  ref-error A-ref={A-ref:.6e} ---")
    w = A
    marks = {}
    for i in range(1, int(4 * 3600 / DT) + 1):
        w = A + (lam * w + (1 - lam) * w_in) - ref
        t = i * DT
        if t in (60.0, 120.0, 300.0, 600.0, 900.0, 1200.0, 1800.0, 3600.0, 7200.0, 14400.0):
            marks[t] = w
    for t in sorted(marks):
        print(f"   t={t:8.0f}s   w_d002 = {marks[t]*100:.4f} %")
    print(f"   converged w* = {(w_in + (A-ref)/mu)*100:.4f} %")

# invert: what frozen-reference error reproduces 76.515 % at t = 600 s, dt = 0.25 ?
DT = 0.25
a, b = m_in * DT / 3600.0, m_out * DT / 3600.0
tot = M + a - b
lam = (M - b) / tot
n = int(600.0 / DT)
# w_n = A + lam*w_{n-1} + (1-lam)*w_in - ref ; solve for (A-ref) given w_n
# closed form: w_n = w* + lam^n (w0 - w*), w* = w_in + (A-ref)/mu, w0 = A
mu = 1 - lam
target = 0.76515
w_in = W317
# target = w* + lam^n (A - w*)  ->  w*(1-lam^n) = target - lam^n*A
wstar = (target - lam**n * A) / (1 - lam**n)
print(f"\nto read {target*100:.3f} % at t=600 s (dt=0.25) the recursion needs "
      f"w* = {wstar*100:.4f} %  ->  (A-ref) = {(wstar-w_in)*mu:.6e}")
print(f"   compare: the seed/pin mismatch  0.80 - W_S317['Urea'] = {A-W317:.6e}")
