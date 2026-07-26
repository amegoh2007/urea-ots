"""READ-ONLY probe: density-error arithmetic for every frozen volumetric-controller rho.
Uses the engine's OWN IAPWS saturated-liquid equation (main.water_rho_sat, Wagner & Pruss 1993)
for the steam-table slope, and cross-checks against the PFD's own internal same-composition pair.
Writes nothing under backend/.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main

W = main.water_rho_sat

def dwdT(T, h=0.05):
    return (W(T + h) - W(T - h)) / (2 * h)

print("=" * 100)
print("A. IAPWS (Wagner&Pruss, main.water_rho_sat) local slope and expansivity")
print("%6s %12s %14s %14s" % ("T (C)", "rho_w", "drho/dT", "beta=-1/r dr/dT"))
for T in (40, 44, 45, 56, 61, 74, 139, 143):
    r = W(T); d = dwdT(T)
    print("%6.0f %12.3f %14.4f %14.3e" % (T, r, d, -d / r))

print()
print("=" * 100)
print("B. PFD-INTERNAL derivative for the 'Amm. Water' family")
print("   Streams 755 and 744 are the SAME fluid: identical composition (CO2 3.81 / H2O 91.13 /")
print("   NH3 4.17 / urea 0.89 mol%), identical mass 31478 kg/h, identical molar 1701.32 kmol/h,")
print("   identical MW 18.50 -- differing ONLY in temperature.  PFD-22 line 79/80.")
r40, r44 = 1005.0, 1002.0
slope_pfd = (r44 - r40) / (44.0 - 40.0)
beta_pfd = -slope_pfd / r40
print("     755 @ 40 C  rho = %.1f" % r40)
print("     744 @ 44 C  rho = %.1f" % r44)
print("     -> drho/dT = %+.4f kg/m3.K    beta = %.3e /K" % (slope_pfd, beta_pfd))
print("     IAPWS water at 42 C          = %+.4f kg/m3.K    beta = %.3e /K"
      % (dwdT(42.0), -dwdT(42.0) / W(42.0)))
print("     PFD amm-water family is %.2fx steeper than pure water." % (slope_pfd / dwdT(42.0)))
print()
print("   Urea-solution regression (main.C10_RHO_C, PFD-regressed over 12 urea streams):")
print("     drho/dT = %+.6f kg/m3.K  -- applies to unit 323/324 urea streams, NOT to any of the")
print("     volumetric-FIC streams below (all are <1 mol%% urea)." % main.C10_RHO_C)

# ---------------------------------------------------------------------------
# site table:  (tag, const name, value, stream, family, T_des, T_lo, T_hi)
SITES = [
    ("FIC-328402", "RHO_744_KGM3",       main.RHO_744_KGM3,      "744",  "amm",  44.0),
    ("FIC-323401", "RHO_401_KGM3",       main.RHO_401_KGM3,      "734",  "amm",  56.0),
    ("FIC-323402", "RHO_791_KGM3",       main.RHO_791_KGM3,      "791",  "amm",  56.0),
    ("FIC-328405", "RHO_401_KGM3",       main.RHO_401_KGM3,      "793",  "amm",  56.0),
    ("FIC-328406", "RHO_741_KGM3",       main.RHO_741_KGM3,      "741",  "wat",  40.0),
    ("FIC-323418", "RHO_718_KGM3",       main.RHO_718_KGM3,      "718B", "carb", 45.0),
    ("FIC-328404", "RHO_775_KGM3",       main.RHO_775_KGM3,      "775",  "carb", 61.0),
    ("FT-328401",  "R328_D001_M776_RHO", main.R328_D001_M776_RHO,"776",  "carb", 61.0),
    ("FT-322402",  "A328_M755_RHO",      main.A328_M755_RHO,     "755",  "amm",  40.0),
]

def rel_err_per_K(family, T_des, rho_frozen):
    """fractional density error per K of temperature deviation, at the design point."""
    if family == "amm":
        return abs(slope_pfd_scaled(rho_frozen)) / rho_frozen, abs(dwdT(T_des)) / W(T_des)
    d_iapws = abs(dwdT(T_des)) / W(T_des)     # multiplicative aqueous_rho slope
    return d_iapws, d_iapws

def slope_pfd_scaled(rho_frozen):
    return -beta_pfd * rho_frozen

print()
print("=" * 100)
print("C. PER-SITE fractional flow error per K, and over a +/-10 K excursion")
print("%-11s %-20s %9s %6s %6s %11s %11s %11s"
      % ("tag", "constant", "rho", "strm", "T_des", "%/K IAPWS", "%/K PFD-amm", "% @ 10K"))
for tag, name, rho, strm, fam, Td in SITES:
    iapws_pk = abs(dwdT(Td)) / W(Td) * 100.0
    pfd_pk = beta_pfd * 100.0 if fam == "amm" else iapws_pk
    print("%-11s %-20s %9.2f %6s %6.0f %10.4f%% %10.4f%% %10.3f%%"
          % (tag, name, rho, strm, Td, iapws_pk, pfd_pk, pfd_pk * 10.0))
print()
print("   'amm' family uses the PFD-internal 755/744 pair (beta=%.3e/K); 'carb' and 'wat' use IAPWS."
      % beta_pfd)
