"""probe_wf_c10_aq.py -- READ ONLY.  C10 remaining gap: aqueous/water rho and cp.
Uses probe_wf_if97 (IAPWS-IF97 R7-97 Region 1 + Region 4) as the authoritative reference.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_wf_if97 import sat_liq, liq_at_p, psat_MPa

MW = {"H2O": 18.0152, "NH3": 17.0304, "CO2": 44.0098, "urea": 60.056}

# ------------------------------------------------------------------ 1. reference table
print("=" * 100)
print("1.  IAPWS-IF97 saturated-liquid water (R7-97 Region 1 evaluated on the Region 4 sat line)")
print(f"{'T,C':>6} {'Psat,bar':>10} {'rho_f':>10} {'cp_f':>9}")
for T in [0, 20, 25, 40, 50, 60, 80, 100, 114, 120, 139, 140, 143, 148, 150, 160, 175,
          180, 188, 190, 200, 212, 220, 240, 250]:
    r, c, ps = sat_liq(float(T))
    print(f"{T:>6} {ps:>10.4f} {r:>10.3f} {c:>9.4f}")

# ------------------------------------------------------------------ 2. PFD streams
print()
print("=" * 100)
print("2.  PFD 'Density eff.' vs IF97   (PFD md line 79 = desorption table, line 34/115 = others)")
# id, desc, mol%: H2O urea NH3 CO2, T C, P bara, rho_PFD, md-line
S = [
    ("343", "Amm.Water", 90.24, 0.82, 5.23, 3.71,  56.0,  1.0,  992.2, 79),
    ("738", "Amm.Water", 90.24, 0.82, 5.23, 3.71, 114.0,  3.5,  959.7, 79),
    ("743", "Amm.Water", 98.50, 0.76, 0.63, 0.11, 139.0,  3.7,  933.0, 79),
    ("779", "Amm.Water", 99.16, 0.00, 0.83, 0.01, 139.0,  3.7,  928.9, 79),
    ("749", "Amm.Water", 99.02, 0.00, 0.97, 0.02, 148.0, 16.6,  924.1, 79),
    ("746", "Amm.Water", 98.50, 0.76, 0.63, 0.11, 190.0, 14.7,  908.5, 79),
    ("747", "Amm.Water", 99.02, 0.00, 0.97, 0.02, 200.0, 16.6,  897.7, 79),
    # pure-water streams in the SAME desorption table
    ("742G", "Pur.Pr.C", 100.0, 0.0, 0.0, 0.0,  88.0, 1.0, 966.40, 79),
    ("740", "Pur.Pr.C", 100.0, 0.0, 0.0, 0.0,  89.0, 3.9, 965.74, 79),
    ("739", "Pur.Pr.C", 100.0, 0.0, 0.0, 0.0, 143.0, 3.9, 923.28, 79),
    # pure-water streams from OTHER PFD sheets
    ("651C", "Cond.Water", 100.0, 0.0, 0.0, 0.0,  6.0,  1.0, 1000.00, 103),
    ("120", "Proc.Con.", 100.0, 0.0, 0.0, 0.0,  60.0,  3.0,  983.27, 34),
    ("954", "Condensate", 100.0, 0.0, 0.0, 0.0,  46.0, 12.0,  990.32, 34),
    ("940", "Condensate", 100.0, 0.0, 0.0, 0.0, 151.0,  4.9,  915.76, 115),
    ("905", "Condensate", 100.0, 0.0, 0.0, 0.0, 175.0,  9.0,  891.84, 115),
    ("913", "Condensate", 100.0, 0.0, 0.0, 0.0, 175.0,  9.0,  891.84, 115),
    ("904", "Condensate", 100.0, 0.0, 0.0, 0.0, 212.0, 19.7,  850.84, 115),
]
print(f"{'id':>6} {'desc':<11} {'T,C':>6} {'P,bara':>7} {'Psat':>7} {'rhoPFD':>8} "
      f"{'rho_sat':>8} {'rho@P':>8} {'d_sat%':>7} {'d_P%':>7} {'cp_f':>7} L")
res = {}
for sid, d, wH, wU, wN, wC, T, P, rho, ln in S:
    rs, cs, ps = sat_liq(T)
    Pu = max(P, ps)                      # IF97 R1 needs p >= Psat
    rp, cp_ = liq_at_p(T, Pu)
    res[sid] = (T, P, rho, rs, rp, cs, ps, wH, wU, wN, wC)
    print(f"{sid:>6} {d:<11} {T:>6.0f} {P:>7.1f} {ps:>7.3f} {rho:>8.2f} {rs:>8.2f} {rp:>8.2f} "
          f"{100*(rho/rs-1):>+7.2f} {100*(rho/rp-1):>+7.2f} {cs:>7.4f} {ln}")

# ------------------------------------------------------------------ 3. candidate explanations
print()
print("=" * 100)
print("3.  Candidate explanation A -- COMPRESSED LIQUID at the tabulated pressure")
for sid in ["749", "746", "747", "743"]:
    T, P, rho, rs, rp, cs, ps, wH, wU, wN, wC = res[sid]
    dP = P - ps
    print(f"  {sid}: T={T:.0f} C  Psat={ps:.3f} bar  P_tab={P} bar  dP={dP:+.2f} bar")
    print(f"        rho(sat)={rs:.3f}  rho(P_tab)={rp:.3f}  gain={100*(rp/rs-1):+.4f} %  "
          f"needed={100*(rho/rs-1):+.2f} %   -> covers {100*(rp/rs-1)/(rho/rs-1):.2f} % of gap")

print()
print("3b. Candidate explanation B -- DISSOLVED SOLUTES (urea + NH3 + CO2)")


def mass_fracs(wH, wU, wN, wC):
    mol = {"H2O": wH, "urea": wU, "NH3": wN, "CO2": wC}
    m = {k: mol[k] * MW[k] for k in mol}
    tot = sum(m.values())
    return {k: m[k] / tot for k in m}, tot / 100.0


# apparent-density coefficients, 20-25 C, from standard aqueous-solution density tables
#   urea : CRC / Perry aqueous urea, rho(w) ~ 998.2 + 288*w  (0-10 wt%)  -> +0.289 %/wt%
#   NH3  : Perry aqueous ammonia,   rho(w) ~ 998.2 - 435*w  (0-10 wt%)  -> -0.436 %/wt%
#   CO2 (as carbamate/carbonate, treat as ammonium carbamate) ~ +300*w  -> +0.30 %/wt% (upper bound)
K = {"urea": +288.0, "NH3": -435.0, "CO2": +300.0}
for sid in ["743", "746", "747", "749"]:
    T, P, rho, rs, rp, cs, ps, wH, wU, wN, wC = res[sid]
    mf, mwavg = mass_fracs(wH, wU, wN, wC)
    d = sum(K[k] * mf[k] for k in K)
    print(f"  {sid}: mol% H2O={wH} urea={wU} NH3={wN} CO2={wC}   MW_calc={mwavg:.3f}")
    print(f"        wt%: urea={100*mf['urea']:.3f}  NH3={100*mf['NH3']:.3f}  CO2={100*mf['CO2']:.3f}")
    print(f"        solute dRho = {d:+.2f} kg/m3 ({100*d/rs:+.3f} %)   needed {rho-rs:+.2f} kg/m3 "
          f"({100*(rho/rs-1):+.2f} %)  -> covers {100*d/(rho-rs):.1f} %")

print()
print("3c. Candidate explanation C -- the table's rho(T) is LINEAR (low-T slope extrapolated)")
pairs = [("343", "738", "90.24% H2O Amm.Water"), ("743", "746", "98.50% H2O Amm.Water"),
         ("749", "747", "99.02% H2O Amm.Water"), ("740", "739", "100% H2O Pur.Pr.Cond")]
for a, b, lbl in pairs:
    Ta, _, ra, rsa, _, _, _, *_ = res[a]
    Tb, _, rb, rsb, _, _, _, *_ = res[b]
    sl_pfd = (rb - ra) / (Tb - Ta)
    sl_if = (rsb - rsa) / (Tb - Ta)
    print(f"  {lbl:<22} {a}({Ta:.0f}C,{ra}) -> {b}({Tb:.0f}C,{rb}) : "
          f"dRho/dT PFD = {sl_pfd:+.4f}   IF97 = {sl_if:+.4f}   ratio {sl_pfd/sl_if:.3f}")

print()
print("3d. What temperature would give the tabulated density for REAL water?")
for sid in ["743", "749", "746", "747", "738"]:
    T, P, rho, rs, *_ = res[sid]
    lo, hi = 0.0, 300.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if sat_liq(mid)[0] > rho:
            lo = mid
        else:
            hi = mid
    print(f"  {sid}: rho_tab={rho} at T_tab={T:.0f} C  ==  real sat water at T={0.5*(lo+hi):.1f} C"
          f"   (offset {0.5*(lo+hi)-T:+.1f} K)")

# ------------------------------------------------------------------ 4. correlations
print()
print("=" * 100)
print("4.  CORRELATION FITS, 0-250 C, saturated liquid, reference = IF97")
Ts = [float(t) for t in range(0, 251, 2)]
RHO = [sat_liq(t)[0] for t in Ts]
CP = [sat_liq(t)[1] for t in Ts]


def polyfit(x, y, deg):
    n = deg + 1
    A = [[sum(xi ** (i + j) for xi in x) for j in range(n)] for i in range(n)]
    B = [sum(yi * xi ** i for xi, yi in zip(x, y)) for i in range(n)]
    for i in range(n):                       # gaussian elimination w/ partial pivot
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


for name, y in (("rho", RHO), ("cp", CP)):
    print(f"\n  --- {name}(T) ---")
    for deg in (2, 3, 4, 5):
        c = polyfit(Ts, y, deg)
        wa = max(abs(ev(c, t) - yi) for t, yi in zip(Ts, y))
        wp = max(abs(ev(c, t) / yi - 1) for t, yi in zip(Ts, y)) * 100
        # worst residual of the RATIO form used at the anchor T_DES
        print(f"    deg{deg}: worst abs {wa:.5g}   worst rel {wp:.4f} %")
        print(f"           coef (ascending powers of T_C): " +
              ", ".join(f"{ci:+.10e}" for ci in c))

# existing model cp correlation, checked over 0-250
print("\n  --- existing backend/main.py cp_water_kjkgk over 0-250 C ---")


def cp_model(T):
    return 4.209433 - 0.001320530 * T + 0.0000135795 * T * T


w = max(abs(cp_model(t) / c - 1) for t, c in zip(Ts, CP)) * 100
wt = max(zip(Ts, CP), key=lambda p: abs(cp_model(p[0]) / p[1] - 1))
print(f"    worst rel {w:.4f} %  at T={wt[0]} C (model {cp_model(wt[0]):.4f} vs IF97 {wt[1]:.4f})")
w2 = max(abs(cp_model(t) / c - 1) for t, c in zip(Ts, CP) if t <= 200) * 100
print(f"    worst rel over 0-200 C: {w2:.4f} %")

# ratio-form check: does the departure form stay accurate?
print("\n  --- RATIO form rho(T) = RHO_DES * rhoref(T)/rhoref(T_DES) : worst error is the fit's ---")
for deg in (3, 4):
    c = polyfit(Ts, RHO, deg)
    for Td in (44.0, 89.0, 148.0):
        e = max(abs((ev(c, t) / ev(c, Td)) / (yi / sat_liq(Td)[0]) - 1) for t, yi in zip(Ts, RHO))
        print(f"    deg{deg} T_DES={Td:>5.0f} C : worst rel error of the RATIO = {100*e:.4f} %")
