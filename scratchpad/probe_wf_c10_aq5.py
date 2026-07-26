"""probe_wf_c10_aq5.py -- READ ONLY.  Ratio-form accuracy + bit-exactness for the recommended
Wagner & Pruss (1993) Eq. 2.6 saturated-liquid density equation."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_wf_if97 import sat_liq

TC, RHOC = 647.096, 322.0
B = (1.99274064, 1.09965342, -0.510839303, -1.75493479, -45.5170352, -6.74694450e5)
E = (1 / 3, 2 / 3, 5 / 3, 16 / 3, 43 / 3, 110 / 3)


def wp(T_C):
    th = 1.0 - (T_C + 273.15) / TC
    return RHOC * (1.0 + sum(b * th ** e for b, e in zip(B, E)))


Ts = [i * 0.5 for i in range(0, 501)]
R = [sat_liq(t)[0] for t in Ts]
print("W&P Eq.2.6 RATIO form  rho(T) = RHO_DES * (wp(T)/wp(T_DES))")
print("worst relative error vs IF97 truth, i.e. |(wp(T)/wp(Td)) / (rho(T)/rho(Td)) - 1|:")
for Td in (40.0, 44.0, 56.0, 80.0, 99.0, 139.0, 143.0, 148.0):
    f = lambda hi: max(abs((wp(t) / wp(Td)) / (y / sat_liq(Td)[0]) - 1)
                       for t, y in zip(Ts, R) if t <= hi) * 100
    print(f"  T_DES={Td:>6.1f} C : 0-250 C {f(250):.4f} %   0-220 C {f(220):.4f} %   0-200 C {f(200):.4f} %")

print()
n = 0
for A in (1002.48, 992.42, 992.4, 1005.0, 933.0, 923.28, 971.8, 961.9):
    for Td in (40.0, 44.0, 56.0, 80.0, 95.0, 139.0, 143.0):
        r = wp(Td)
        assert A * (r / r) == A
        n += 1
print(f"bit-exactness: A*(wp(Td)/wp(Td)) == A for all {n} anchor/T_DES pairs tried (IEEE-754 exact)")
print()
print("anchor values the ratio form would produce at the two disputed streams:")
for nm, A, Td in (("R328_C002_RHO=933.0 @139C", 933.0, 139.0),
                  ("R328_C004_RHO=923.28 @143C", 923.28, 143.0)):
    for T, pfd in ((190.0, 908.5), (200.0, 897.7)):
        v = A * (wp(T) / wp(Td))
        print(f"  {nm:<28} T={T:.0f} C -> {v:7.2f}   PFD {pfd} ({100*(v/pfd-1):+.2f} %)"
              f"   IF97 pure water {sat_liq(T)[0]:.2f} ({100*(v/sat_liq(T)[0]-1):+.2f} %)")
