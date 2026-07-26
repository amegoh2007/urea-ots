import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_wf_if97 import _R1, _P1s, _T1s, R

T, p = 500.0, 3.0
pi = p / _P1s
tau = _T1s / T
a = 7.1 - pi
b = tau - 1.222
terms = []
for I, J, n in _R1:
    t = -n * I * a ** (I - 1) * b ** J
    terms.append((abs(t), I, J, n, t))
terms.sort(reverse=True)
tot = sum(x[4] for x in terms)
print("gamma_pi =", tot)
target = 0.120241800e-2 * p * 1000.0 / (R * T * pi)
print("target   =", target, " diff =", tot - target)
print()
for m, I, J, n, t in terms[:14]:
    print(f"  I={I:>3} J={J:>4} n={n:>24.15e}  term={t:+.6e}")
