"""probe_wf_c10_aq3.py -- READ ONLY.
Candidate correlation forms for water rho(T)/cp(T), 0-250 C, plus IEEE-754 stress test.
"""
import sys, os, math, random, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_wf_if97 import sat_liq

TC = 647.096
RHOC = 322.0

# IAPWS supplementary equation for saturated liquid density
# (W. Wagner & A. Pruss, J.Phys.Chem.Ref.Data 22 (1993) 783, Eq. 2.6; also IAPWS R7-97 Sec. 8.1)
B = (1.99274064, 1.09965342, -0.510839303, -1.75493479, -45.5170352, -6.74694450e5)
EXP = (1.0 / 3, 2.0 / 3, 5.0 / 3, 16.0 / 3, 43.0 / 3, 110.0 / 3)


def rho_sat_wp(T_C):
    th = 1.0 - (T_C + 273.15) / TC
    return RHOC * (1.0 + sum(b * th ** e for b, e in zip(B, EXP)))


print("=" * 92)
print("G.  Wagner & Pruss (1993) Eq. 2.6 saturated-liquid density vs IF97, 0-250 C")
worst = 0.0
wT = 0.0
for i in range(0, 501):
    T = i * 0.5
    r = sat_liq(T)[0]
    e = abs(rho_sat_wp(T) / r - 1)
    if e > worst:
        worst, wT = e, T
print(f"  worst rel deviation {100*worst:.4f} %  at T = {wT} C")
for T in (0, 4, 20, 40, 56, 80, 99, 100, 139, 143, 148, 150, 190, 200, 220, 250):
    print(f"   T={T:>4} C  W&P {rho_sat_wp(float(T)):9.4f}   IF97 {sat_liq(float(T))[0]:9.4f}"
          f"   dev {100*(rho_sat_wp(float(T))/sat_liq(float(T))[0]-1):+.4f} %")

print()
print("=" * 92)
print("H.  Polynomial fits restricted to 20-250 C (drops the 4 C density maximum)")
Ts = [20.0 + i * 0.5 for i in range(0, 461)]
RHO = [sat_liq(t)[0] for t in Ts]
CP = [sat_liq(t)[1] for t in Ts]
X = [t / 100.0 for t in Ts]


def polyfit(x, y, deg):
    n = deg + 1
    A = [[sum(xi ** (i + j) for xi in x) for j in range(n)] for i in range(n)]
    Bv = [sum(yi * xi ** i for xi, yi in zip(x, y)) for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(A[r][i]))
        A[i], A[p] = A[p], A[i]
        Bv[i], Bv[p] = Bv[p], Bv[i]
        for r in range(i + 1, n):
            f = A[r][i] / A[i][i]
            for c in range(i, n):
                A[r][c] -= f * A[i][c]
            Bv[r] -= f * Bv[i]
    c = [0.0] * n
    for i in range(n - 1, -1, -1):
        c[i] = (Bv[i] - sum(A[i][j] * c[j] for j in range(i + 1, n))) / A[i][i]
    return c


def ev(c, x):
    return sum(ci * x ** i for i, ci in enumerate(c))


for name, y in (("rho", RHO), ("cp", CP)):
    for deg in (3, 4):
        c = polyfit(X, y, deg)
        wp = max(abs(ev(c, xi) / yi - 1) for xi, yi in zip(X, y)) * 100
        print(f"  {name} deg{deg} (20-250 C): worst rel {wp:.4f} %   " +
              " ".join(f"c{i}={ci:+.10e}" for i, ci in enumerate(c)))

print()
print("=" * 92)
print("I.  IEEE-754: is the un-parenthesised ratio safe?  10^6 random (anchor, ref) pairs")
random.seed(7)
bad_paren = bad_flat = 0
for _ in range(1000000):
    A_ = random.uniform(1.0, 1500.0)
    r = random.uniform(700.0, 1010.0)
    if A_ * (r / r) != A_:
        bad_paren += 1
    if A_ * r / r != A_:
        bad_flat += 1
print(f"  A*(ref/ref) != A   : {bad_paren} failures")
print(f"  A*ref/ref   != A   : {bad_flat} failures   <-- un-parenthesised form is NOT bit-safe")

print()
print("=" * 92)
print("J.  Multiplicative vs additive departure, applied to the model's aqueous anchors")
print("    (how the two forms differ when carried from the anchor T to 200 C)")
for nm, A_, Td in (("RHO_744_KGM3", 1002.48, 44.0), ("R328_C002_RHO", 933.0, 139.0),
                   ("R328_C004_RHO", 923.28, 143.0), ("RHO_401/791", 992.4, 56.0)):
    rd = rho_sat_wp(Td)
    for T in (Td, 148.0, 190.0, 200.0):
        mul = A_ * (rho_sat_wp(T) / rd)
        add = A_ + (rho_sat_wp(T) - rd)
        print(f"  {nm:<14} T_DES={Td:>5.0f}  T={T:>5.0f}: mult {mul:8.2f}  add {add:8.2f}"
              f"  diff {mul-add:+6.2f} kg/m3")
    print()

print("=" * 92)
print("K.  What the corrected model would give for the two disputed streams")
for sid, A_, Td, T, pfd in (("746 (from R328_C002_RHO@139C)", 933.0, 139.0, 190.0, 908.5),
                            ("747 (from R328_C002_RHO@139C)", 933.0, 139.0, 200.0, 897.7),
                            ("746 (from R328_C004_RHO@143C)", 923.28, 143.0, 190.0, 908.5),
                            ("747 (from R328_C004_RHO@143C)", 923.28, 143.0, 200.0, 897.7)):
    mul = A_ * (rho_sat_wp(T) / rho_sat_wp(Td))
    print(f"  {sid:<32} -> {mul:7.2f} kg/m3   PFD {pfd}  ({100*(mul/pfd-1):+.2f} %)"
          f"   IF97 pure water {sat_liq(T)[0]:.2f}")
