"""probe_wf_c10_aq2.py -- READ ONLY.  Follow-up: property-model diagnosis + conditioned fits."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_wf_if97 import sat_liq, liq_at_p

print("=" * 96)
print("A.  Constant-beta (linearised thermal expansion) hypothesis for the PFD 'Amm. Water' row")
print("    rho_tab(T2)/rho_tab(T1) = exp(-beta*(T2-T1))  ->  solve beta, then find the water")
print("    temperature whose true expansivity equals it.")


def beta_water(T):
    h = 0.5
    r1 = sat_liq(T - h)[0]
    r2 = sat_liq(T + h)[0]
    return -(r2 - r1) / (2 * h) / sat_liq(T)[0]


def T_of_beta(b):
    lo, hi = 5.0, 300.0
    for _ in range(200):
        m = 0.5 * (lo + hi)
        if beta_water(m) < b:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


pairs = [("343->738  90.24%H2O", 56.0, 992.2, 114.0, 959.7),
         ("743->746  98.50%H2O", 139.0, 933.0, 190.0, 908.5),
         ("749->747  99.02%H2O", 148.0, 924.1, 200.0, 897.7),
         ("740->739  100%  H2O", 89.0, 965.74, 143.0, 923.28)]
for lbl, T1, r1, T2, r2 in pairs:
    b = -math.log(r2 / r1) / (T2 - T1)
    print(f"  {lbl}: beta_tab = {b:.4e} /K  ==  real water expansivity at T = {T_of_beta(b):5.1f} C"
          f"   | real beta at T1={T1:.0f} C is {beta_water(T1):.4e}, at T2={T2:.0f} C is {beta_water(T2):.4e}")

print()
print("  Predict the high-T member from the low-T member with a SINGLE beta = 5.5e-4 /K:")
B = 5.5e-4
for lbl, T1, r1, T2, r2 in pairs[:3]:
    pred = r1 * math.exp(-B * (T2 - T1))
    print(f"    {lbl}: pred {pred:8.2f}  tabulated {r2:8.2f}  err {100*(pred/r2-1):+.2f} %"
          f"   (IF97 sat water at T2 = {sat_liq(T2)[0]:.2f})")

print()
print("=" * 96)
print("B.  Consequence: the PFD volume flow for 746/747 is wrong by the same factor")
for sid, m, V, T in [("746", 33769.0, 37.2, 190.0), ("747", 34062.0, 37.9, 200.0),
                     ("749", 34062.0, 36.9, 148.0), ("743", 33769.0, 36.2, 139.0)]:
    r = sat_liq(T)[0]
    print(f"  {sid}: m={m} kg/h  V_PFD={V} m3/h (rho {m/V:.1f})  ->  V_IF97 = {m/r:.2f} m3/h"
          f"  ({100*(m/r/V-1):+.2f} %)")

print()
print("=" * 96)
print("C.  Every aqueous/water density anchor now in backend/main.py vs IF97")
anch = [("RHO_744_KGM3", 1191, 1002.48, 44.0, 1.0, "PFD 744, 91.13%H2O +15.8wt% solute"),
        ("RHO_741_KGM3", 1262, 992.42, 40.0, 0.3, "PFD 741"),
        ("RHO_401_KGM3", 3337, 992.4, 56.0, 4.1, "PFD 735/791 Amm.Water"),
        ("RHO_791_KGM3", 3344, 992.4, 56.0, 4.1, "PFD 791 Amm.Water"),
        ("A328_M755_RHO", 1151, 1005.0, 40.0, 3.9, "PFD 755 Amm.Water"),
        ("R328_C002_RHO", 1042, 933.0, 139.0, 3.7, "PFD 743 Amm.Water 98.5%H2O"),
        ("R328_C004_RHO", 1043, 923.28, 143.0, 3.9, "PFD 739 pure process condensate"),
        ("SCRUB_CCW_RHO_IN", 2687, 971.8, 80.0, 1.0, "cooling water"),
        ("SCRUB_CCW_RHO_OUT", 2688, 961.9, 95.0, 1.0, "cooling water")]
print(f"{'name':<20} {'line':>5} {'value':>9} {'T,C':>6} {'IF97sat':>9} {'dev%':>7}  note")
for n, ln, v, T, P, note in anch:
    r = sat_liq(T)[0]
    print(f"{n:<20} {ln:>5} {v:>9.2f} {T:>6.0f} {r:>9.3f} {100*(v/r-1):>+7.2f}  {note}")

print()
print("=" * 96)
print("D.  WELL-CONDITIONED FITS over 0-250 C in x = T_C/100  (reference: IAPWS-IF97 sat. liquid)")
Ts = [i * 0.5 for i in range(0, 501)]        # 0..250 C in 0.5 C steps
RHO = [sat_liq(t)[0] for t in Ts]
CP = [sat_liq(t)[1] for t in Ts]


def polyfit(x, y, deg):
    n = deg + 1
    A = [[sum(xi ** (i + j) for xi in x) for j in range(n)] for i in range(n)]
    B = [sum(yi * xi ** i for xi, yi in zip(x, y)) for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(A[r][i]))
        A[i], A[p] = A[p], A[i]
        B[i], B[p] = B[p], B[i]
        for r in range(i + 1, n):
            f = A[r][i] / A[i][i]
            for c in range(i, n):
                A[r][c] -= f * A[i][c]
            B[r] -= f * B[i]
    c = [0.0] * n
    for i in range(n - 1, -1, -1):
        c[i] = (B[i] - sum(A[i][j] * c[j] for j in range(i + 1, n))) / A[i][i]
    return c


def ev(c, x):
    return sum(ci * x ** i for i, ci in enumerate(c))


X = [t / 100.0 for t in Ts]
for name, y, unit in (("rho_ref", RHO, "kg/m3"), ("cp_ref", CP, "kJ/kg.K")):
    print(f"\n  --- {name}(x), x = T_C/100, {unit} ---")
    for deg in (3, 4, 5, 6):
        c = polyfit(X, y, deg)
        wa = max(abs(ev(c, xi) - yi) for xi, yi in zip(X, y))
        wp = max(abs(ev(c, xi) / yi - 1) for xi, yi in zip(X, y)) * 100
        wt = max(zip(Ts, X, y), key=lambda p: abs(ev(c, p[1]) / p[2] - 1))[0]
        print(f"    deg{deg}: worst abs {wa:.6g}  worst rel {wp:.4f} % (at T={wt:.0f} C)")
        print("           " + ",\n           ".join(f"c{i} = {ci:+.12e}" for i, ci in enumerate(c)))

print()
print("=" * 96)
print("E.  Ratio-form accuracy and IEEE-754 bit-exactness of  RHO_DES * (ref(T)/ref(T_DES))")
c4r = polyfit(X, RHO, 4)
c4c = polyfit(X, CP, 4)
for Td in (40.0, 44.0, 56.0, 80.0, 139.0, 143.0):
    e = max(abs((ev(c4r, t / 100.0) / ev(c4r, Td / 100.0)) / (yi / sat_liq(Td)[0]) - 1)
            for t, yi in zip(Ts, RHO)) * 100
    print(f"  rho deg4, T_DES={Td:>6.1f} C : worst rel error of ratio over 0-250 C = {e:.4f} %")
for Td in (99.0, 139.0):
    e = max(abs((ev(c4c, t / 100.0) / ev(c4c, Td / 100.0)) / (yi / sat_liq(Td)[1]) - 1)
            for t, yi in zip(Ts, CP)) * 100
    print(f"  cp  deg4, T_DES={Td:>6.1f} C : worst rel error of ratio over 0-250 C = {e:.4f} %")

print()
for A in (1002.48, 992.42, 933.0, 923.28, 4.2183):
    for Td in (44.0, 139.0, 99.0):
        r = ev(c4r, Td / 100.0)
        got = A * (r / r)
        bad = A * r / r
        print(f"  anchor={A!r:>10} T_DES={Td:>5}: A*(ref/ref) == A ? {got == A}   "
              f"A*ref/ref == A ? {bad == A}")
    break
print("  (parenthesise the ratio: x/x is exactly 1.0 in IEEE-754 and A*1.0 == A;")
print("   A*ref(T)/ref(T_DES) evaluated left-to-right is NOT guaranteed exact.)")

print()
print("=" * 96)
print("F.  Existing cp_water_kjkgk (main.py:705) extended range check")


def cp_model(T):
    return 4.209433 - 0.001320530 * T + 0.0000135795 * T * T


for T in (0, 50, 100, 150, 200, 220, 250):
    c = sat_liq(float(T))[1]
    print(f"  T={T:>4} C  model {cp_model(T):.4f}  IF97 {c:.4f}  dev {100*(cp_model(T)/c-1):+.3f} %")
