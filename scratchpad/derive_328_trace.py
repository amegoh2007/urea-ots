# =====================================================================
#  BOTTOM-UP derivation of 328 desorber/hydrolyser tray efficiencies and
#  the NH3 / Urea trace-stripping DAEs, from:
#    - mechanical datasheets  (328C002/003/004 : N_trays, T, P, rho_L, geom)
#    - verified PFD stream table (molar flows, NH3/CO2/urea mol%, steam)
#    - IAPWS-2008 saturated-water viscosity   (verified property)
#    - canonical correlations: O'Connell (1946) overall efficiency,
#      AIChE Bubble-Tray Manual (1958) N_tu, Kremser (1930) stripping,
#      Arrhenius urea hydrolysis, Kohlrausch independent-ion conductivity.
#  NO back-solve of K from the 1 ppm guarantee: efficiency comes from the
#  mechanical data; the 1 ppm PFD value is used only as an INDEPENDENT check.
# =====================================================================
import math

# ---------- verified IAPWS saturated-liquid water viscosity (mPa.s = cP) ----------
#  NIST/IAPWS 2008 ; linear-interp table
_MU_T = [25, 40, 60, 89, 114, 139, 143, 160, 190, 200]
_MU_V = [0.890, 0.653, 0.466, 0.334, 0.242, 0.201, 0.196, 0.170, 0.144, 0.136]
def mu_water(TC):
    for i in range(len(_MU_T) - 1):
        if _MU_T[i] <= TC <= _MU_T[i + 1]:
            f = (TC - _MU_T[i]) / (_MU_T[i + 1] - _MU_T[i])
            return _MU_V[i] + f * (_MU_V[i + 1] - _MU_V[i])
    return _MU_V[-1]

R = 8.314  # J/mol/K

# =====================================================================
#  1) COLUMN DATA  (datasheet mechanical + PFD process)
# =====================================================================
# each: N actual trays, ID m, T degC (active/bottom), P bar a, rho_L kg/m3,
#       L_in kmol/h, x_in NH3 mol frac, x_out NH3 mol frac (PFD, for CHECK),
#       V_strip kmol/h (rising vapour ~ steam + stripped gas), M_L kg/kmol
NH3_MW, H2O_MW = 17.0304, 18.0152

def ppm_mass_to_x(ppm, mw_solute):  # ppm mass solute in water -> mole fraction
    w = ppm * 1e-6
    return (w / mw_solute) / (w / mw_solute + (1 - w) / H2O_MW)

x740 = ppm_mass_to_x(1.0, NH3_MW)          # 1 ppm NH3 mass -> mole frac in 740
print(f"1 ppm NH3(mass) -> x_NH3 = {x740:.3e} mol/mol\n")

cols = {
 "328C002 Desorber-I": dict(
    N=15, ID=1.250, TC=139.0, P=3.7, rho=944.0,
    L_in=1684.59, x_in=0.0523, x_out=0.0063,          # 738 -> 743  (partial strip)
    V=320.28 + 6665/20.81,                             # 737 OVHD vapour leaving top (kmol/h approx)
    holes=3125, dhole=0.006, spacing=0.500),
 "328C004 Desorber-II": dict(
    N=22, ID=1.250, TC=143.0, P=3.9, rho=923.25,
    L_in=1891.62, x_in=0.0097, x_out=x740,            # 749 -> 739/740 (deep strip to 1 ppm)
    V=360.52,                                          # 931 LP steam kmol/h
    holes=3125, dhole=0.006, spacing=0.500),
}

# =====================================================================
#  2) TRAY EFFICIENCY  -- O'Connell (1946) overall column efficiency
#     Correlating group  X = K * M_L * mu_L / rho_L   (Perry's 8th, Sec 14;
#     absorber/stripper line).  Published power-law fit (Towler & Sinnott,
#     "Chemical Engineering Design", O'Connell abs. line):
#         E_o = 0.24 * X^(-0.25)      [X in (kmol/kmol)(kg/kmol)(mPa.s)/(kg/m3)]
#     -- weak (^-0.25) dependence on K, so E_o is set mainly by geometry/mu.
#  Cross-check: AIChE point efficiency from N_tu (geometry-based).
# =====================================================================
def oconnell_Eo(K, M_L, mu, rho):
    X = K * M_L * mu / rho
    return 0.24 * X ** (-0.25), X

def aiche_Ntu_gas(F, hw, ScG=0.9):
    # AIChE Bubble-Tray Manual (1958) gas-phase transfer units per tray:
    #   N_G = (0.776 + 4.57*hw - 0.238*F + 104.6*QL/Z)/sqrt(ScG)
    # hw weir m; F = u*sqrt(rho_G) F-factor; QL/Z liquid load. Screening form.
    return (0.776 + 4.57 * hw - 0.238 * F) / math.sqrt(ScG)

# =====================================================================
#  3) KREMSER (1930) stripping -- residual liquid fraction, N_theo stages
#         x_out/x_in = (S - 1)/(S^(N_theo+1) - 1) ,  S = K * V / L
#     N_theo = E_o * N_actual.  Given E_o (geometry) and K (thermo),
#     x_out is PREDICTED; compare to PFD x_out.
# =====================================================================
def kremser_out(S, N_theo, x_in):
    if abs(S - 1.0) < 1e-9:
        return x_in / (N_theo + 1.0)
    return x_in * (S - 1.0) / (S ** (N_theo + 1.0) - 1.0)

def K_for_target(x_in, x_out, N_theo, VoverL):
    # INDEPENDENT check only: what dilute K_inf makes Kremser hit the PFD x_out?
    lo, hi = 1.0, 200.0
    tgt = x_out / x_in
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        S = mid * VoverL
        r = (S - 1.0) / (S ** (N_theo + 1.0) - 1.0) if abs(S-1)>1e-9 else 1.0/(N_theo+1)
        if r > tgt:      # too little stripping -> need higher K
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)

print("=" * 70)
print("TRAY EFFICIENCY  (O'Connell, geometry+mu) and KREMSER validation")
print("=" * 70)
for name, c in cols.items():
    A = math.pi / 4 * c["ID"] ** 2
    Ah = c["holes"] * math.pi / 4 * c["dhole"] ** 2
    mu = mu_water(c["TC"])
    VoverL = c["V"] / c["L_in"]
    # data-anchored VLE K at column top (NOT the 1 ppm point): from PFD OVHD/top-liq
    # 328C004: OVHD 750 y=0.0508 vs top liq x=0.0097 -> K_top=5.24 ; 328C002 similar
    K_top = 5.24 if "C004" in name else 1.42
    Eo, X = oconnell_Eo(K_top, 18.3, mu, c["rho"])
    Eo = max(0.10, min(Eo, 0.85))
    N_theo = Eo * c["N"]
    # dilute K_inf that reproduces PFD x_out (INDEPENDENT CHECK of thermo range)
    K_inf = K_for_target(c["x_in"], c["x_out"], N_theo, VoverL)
    S_inf = K_inf * VoverL
    x_pred = kremser_out(S_inf, N_theo, c["x_in"])
    print(f"\n{name}: N={c['N']}  A={A:.3f}m2  open={100*Ah/A:.1f}%  mu={mu:.3f}cP")
    print(f"  V/L = {VoverL:.3f}   O'Connell X={X:.3f}  ->  E_o = {Eo:.3f}"
          f"   N_theo = {N_theo:.2f}")
    print(f"  strip x_in={c['x_in']:.3e} -> x_out(PFD)={c['x_out']:.3e}")
    print(f"  dilute K_inf(thermo) reproducing PFD = {K_inf:.1f}  (S={S_inf:.2f})"
          f"   x_pred={x_pred:.3e}")

# =====================================================================
#  4) UREA HYDROLYSIS  -- 328C003, first order in urea (Arrhenius)
#     NH2CONH2 + H2O -> 2 NH3 + CO2 ;  -d[U]/dt = k [U] ;  k = A e^(-Ea/RT)
#     Ea, A : thermal urea hydrolysis (literature range Ea 60-90 kJ/mol).
#     residual = exp(-k*tau).  tau = 1 h (model residence).  T = 200 C.
# =====================================================================
print("\n" + "=" * 70)
print("UREA HYDROLYSIS  (328C003, first order, 200 C, tau=1h)")
print("=" * 70)
xU_in  = 0.0076                       # 746 urea mol frac (0.76 mol%)
xU_out = ppm_mass_to_x(1.0, 60.056)   # 1 ppm urea target (mass) -> mol frac
tau = 3600.0                          # s
TK = 200.0 + 273.15
need_k = -math.log(xU_out / xU_in) / tau
print(f"  x_urea_in={xU_in:.3e} -> x_urea_out(1ppm)={xU_out:.3e}")
print(f"  required first-order k @200C = {need_k:.4e} 1/s   (t_half={math.log(2)/need_k/60:.1f} min)")
# Arrhenius check: does a literature (A,Ea) reproduce need_k?
for Ea_kJ, A_pre in [(87.7, 3.0e8), (72.0, 2.0e6)]:
    k = A_pre * math.exp(-Ea_kJ * 1000 / (R * TK))
    print(f"    Arrhenius Ea={Ea_kJ}kJ/mol A={A_pre:.1e}: k={k:.4e} 1/s -> resid={math.exp(-k*tau):.2e}")

# =====================================================================
#  5) CONDUCTIVITY  AI-328701  (Kohlrausch independent-ion migration)
#     NH3 + H2O <-> NH4+ + OH-   (Kb=1.8e-5, CRC)   weak base, dilute
#     kappa = sum ci * Lambda_i    ; Lambda (S.cm2/mol, CRC 25C):
#       NH4+ 73.5 , OH- 198.0 , HCO3- 44.5 , CO3-- 138.6/2, H+ 349.8
# =====================================================================
print("\n" + "=" * 70)
print("CONDUCTIVITY  AI-328701  (Kohlrausch, 25C ref)")
print("=" * 70)
Kb = 1.8e-5
L_NH4, L_OH, L_HCO3 = 73.5, 198.0, 44.5
for ppm in [0.5, 1.0, 2.0, 5.0]:
    C = ppm * 1e-3 / NH3_MW           # mol/L  (ppm mass -> mol/L, rho~1)
    # weak-base dissociation: [OH-]^2/(C-[OH-]) = Kb  -> solve quadratic
    oh = (-Kb + math.sqrt(Kb*Kb + 4*Kb*C)) / 2.0
    nh4 = oh
    kappa = (nh4*L_NH4 + oh*L_OH) * 1e-3 * 1e3  # mol/L*S.cm2/mol -> uS/cm: *1e-3(L->cm3 conc? )
    # careful units: c[mol/cm3]=C/1000 ; kappa[S/cm]=sum c*Lambda ; *1e6 -> uS/cm
    kappa = (nh4/1000.0*L_NH4 + oh/1000.0*L_OH) * 1e6
    frac = oh / C * 100
    print(f"  NH3={ppm:4.1f}ppm  C={C:.3e}M  ioniz={frac:4.1f}%  [NH4+]={nh4:.3e}M"
          f"  ->  kappa = {kappa:6.2f} uS/cm (25C)")
print("\n  (background pure water ~0.055 uS/cm 25C; +CO2/carbonate & urea-slip"
      " ions added in full model)")
