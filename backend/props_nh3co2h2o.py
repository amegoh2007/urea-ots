"""Extended UNIQUAC property basis for the NH3-CO2-H2O electrolyte system.

C36 phase 1 (see `C36_PROPERTY_BASIS_PROPOSAL.md`). STANDALONE — nothing in this module is wired
into `main.py`; it exists to be validated on its own before any engine integration (phases 2-5).

WHY THIS MODEL. The Extended UNIQUAC model of Thomsen & Rasmussen (1999), upgraded by Darde et al.
(2010/2011), is valid 0-150 C, 1-100 bar, up to 100 molal NH3 — the exact envelope of the Unit-328
desorption train, Unit-324 vacuum evaporators, and the LP absorbers this simulator models. It gives
liquid activity coefficients, speciation, and excess enthalpy/heat-capacity directly.

PROVENANCE — every parameter below is transcribed verbatim from a named open source. Nothing is
fitted, guessed, or interpolated here:
  * Interaction parameters u0_ij, uT_ij and the r,q volume/surface parameters, the NH2COO- heat
    capacity, and the fitted formation energies:
        Victor Darde, PhD thesis "CO2 capture using aqueous ammonia", DTU 2011, Tables 2-2..2-6
        (https://www.cere.dtu.dk/-/media/centre/cere/publications/phd-thesis/2011/victor_darde_phd.pdf);
        published as Darde, van Well, Stenby, Thomsen, Ind. Eng. Chem. Res. 49 (2010) 12663.
  * Base-species heat-capacity coefficients (Helgeson form, eq 2.22):
        Kaj Thomsen, PhD thesis "Aqueous Electrolytes - Model Parameters and Process Simulation",
        DTU 1997, Table 5.7 (https://backend.orbit.dtu.dk/ws/files/3025526/Thesis_k_thomsen_1997[1].pdf).
  * Base-species standard Gibbs energy / enthalpy of formation at 298.15 K: CODATA/NIST (as the model
    itself uses; Darde thesis sec. 2.2.2 "standard state properties ... were taken from NIST tables").
  * Henry's-law correlations for NH3 and CO2 in water: Rumpf & Maurer (1993), reproduced in Darde
    thesis eqs 2.12-2.13.

STATUS. Phase 1 delivers: the verbatim parameter layer, the standard-state thermodynamics, the
reaction equilibrium constants, the Henry's-law correlations, and the UNIQUAC r/q/u data. It is
VALIDATED (see test_props_nh3co2h2o.py) by reproducing the textbook aqueous pKa1/pKa2/pKw and their
temperature dependence, plus liquid-water heat capacity, from these parameters alone. The r/q volume
and surface parameters are additionally cross-checked against an independent transcription (Table 1 of
`References/Resolving Simulator Thermodynamics Gaps.docx`, 2026-07-29) — an exact match to all nine
species, confirming the verbatim transcription against a second source.

Phase 1b (short-range activity) — DELIVERED 2026-07-29: the UNIQUAC combinatorial term
(`uniquac_combinatorial_ln_gamma`), the residual/enthalpic term (`uniquac_residual_ln_gamma`), their
infinite-dilution limits, and the combined symmetric/unsymmetric `short_range_ln_gamma`. The residual
term is validated for thermodynamic consistency: Gibbs-Duhem closes to < 1e-9, ln gamma == 0 at every
pure-component limit, and the numeric infinite-dilution limit matches the closed form. This is the
SHORT-RANGE part only; the long-range Debye-Huckel electrostatic term, the multiphase Newton
speciation, and the SRK-VLE gas-phase solver are the remaining phase-1b work.

KNOWN VERBATIM GAP (not fabricated): the standard-state Cp coefficients for NH3(aq) and CO2(aq) live
in Thomsen & Rasmussen (1999), which is paywalled; they are left as None below. Consequently the two
reactions that consume them (R2, R3) are exposed at 298.15 K only; R1/R4 (water, carbonate) carry
full temperature dependence. Supplying those two rows completes the set.
"""

import math

R = 8.314462618           # J/mol/K
T0 = 298.15               # K, reference temperature
LN10 = math.log(10.0)

# ---------------------------------------------------------------------------
# Standard-state properties at 298.15 K.
#   dGf, dHf  [kJ/mol]  : Gibbs energy / enthalpy of formation (CODATA/NIST aqueous convention).
#   cp = (a, b, c)      : Helgeson (1986) form  Cp0 = a + b*T + c/(T-200)  [J/mol/K], T in K
#                         (Darde thesis eq 2.22; base-species a,b,c from Thomsen 1997 Table 5.7).
#   cp None             : coefficient set not in an open source (Thomsen & Rasmussen 1999) -> not
#                         invented; species usable at 298.15 K only.
# ---------------------------------------------------------------------------
STANDARD_STATE = {
    #                dGf(kJ/mol) dHf(kJ/mol)  cp (a, b, c)  J/mol/K
    "H2O":      (-237.140,   -285.830,   (58.370,  0.03896,  523.88)),   # Thomsen'97 T5.7
    "H+":       (   0.0,        0.0,      (0.0,     0.0,      0.0)),      # reference ion
    "OH-":      (-157.244,   -230.015,   (1418.2, -3.4446,  -51473.0)),  # Thomsen'97 T5.7
    "NH3(aq)":  ( -26.50,     -80.29,     None),                         # Cp: Thomsen&Rasmussen'99 (paywalled)
    "NH4+":     ( -79.31,    -132.51,     (71.008,  0.0,      0.0)),      # Thomsen'97 T5.7
    "CO2(aq)":  (-385.98,    -413.80,     None),                         # Cp: Thomsen&Rasmussen'99 (paywalled)
    "HCO3-":    (-586.77,    -691.99,     (585.75, -1.3612,  -21374.0)), # Thomsen'97 T5.7
    "CO3--":    (-527.81,    -677.14,     (850.61, -2.8040,  -21308.0)), # Thomsen'97 T5.7
    "NH2COO-":  (-379.355,   -502.863,    (-203.9191, 0.082259, 0.55163)),  # Darde'11 T2-3/T2-4 (fitted)
}

# Aqueous speciation reactions (Darde thesis eqs 2.1-2.5). Stoichiometry: products +, reactants -.
REACTIONS = {
    "R1_water":     {"H2O": -1, "H+": +1, "OH-": +1},                       # H2O <-> H+ + OH-
    "R2_ammonium":  {"NH3(aq)": -1, "H+": -1, "NH4+": +1},                  # NH3 + H+ <-> NH4+
    "R3_bicarb":    {"CO2(aq)": -1, "H2O": -1, "HCO3-": +1, "H+": +1},      # CO2 + H2O <-> HCO3- + H+
    "R4_carbonate": {"HCO3-": -1, "CO3--": +1, "H+": +1},                   # HCO3- <-> CO3-- + H+
    "R5_carbamate": {"NH3(aq)": -1, "HCO3-": -1, "NH2COO-": +1, "H2O": +1}, # NH3 + HCO3- <-> NH2COO- + H2O
}

# ---------------------------------------------------------------------------
# UNIQUAC volume (r) and surface-area (q) parameters. Darde thesis Table 2-2 (refined CO2-NH3-H2O set;
# supersedes the 1997 base values where they differ).
# ---------------------------------------------------------------------------
UNIQUAC_RQ = {
    "H2O":     (0.9200,  1.4000),
    "NH3(aq)": (1.6292,  2.9852),
    "CO2(aq)": (0.7500,  2.4500),
    "NH4+":    (4.8154,  4.6028),
    "H+":      (0.1378,  1.0e-16),
    "OH-":     (9.3973,  8.8171),
    "CO3--":   (10.828,  10.769),
    "HCO3-":   (8.0756,  8.6806),
    "NH2COO-": (4.3022,  4.1348),
}

# UNIQUAC interaction energy: u_ij(T) = u0_ij + uT_ij*(T - 298.15).  Symmetric (u_ij == u_ji).
# Darde thesis Table 2-5 (u0) and Table 2-6 (uT). Order below matches the thesis tables.
_UORDER = ["H2O", "NH3(aq)", "CO2(aq)", "NH4+", "H+", "OH-", "CO3--", "HCO3-", "NH2COO-"]

# lower-triangular rows (u0), Darde Table 2-5
_U0_TRI = [
    [0.0],
    [594.72, 1090.8],
    [8.8383, 2500.0, 302.25],
    [52.7305, 785.98, -424.01, 0.0],
    [10000.0, 1.0e9, 1.0e9, 1.0e9, 0.0],
    [600.50, 1733.9, 2500.0, 1877.9, 1.0e9, 1562.9],
    [361.39, 524.13, 2500.0, 226.60, 1.0e9, 1588.0, 1458.3],
    [577.05, 534.01, 526.305, 505.55, 1.0e9, 2500.0, 800.01, 771.04],
    [28.2779, 498.15, 2500.0, 44.849, 1.0e9, 2500.0, 2500.0, 613.25, 3343.1],
]
# lower-triangular rows (uT), Darde Table 2-6
_UT_TRI = [
    [0.0],
    [7.1827, 7.0912],
    [0.86293, 0.0, 0.35870],
    [0.50922, 6.1271, 8.6951, 0.0],
    [0.0, 0.0, 0.0, 0.0, 0.0],
    [8.5455, 0.1364, 0.0, 0.34921, 0.0, 5.6169],
    [3.3516, 4.9305, 0.0, 4.0555, 0.0, 2.7496, -1.3448],
    [-0.38795, 5.3111, -3.7340, -0.00795, 0.0, 0.0, 1.7241, -0.01981],
    [8.0238, 6.6532, 0.0, 12.047, 0.0, 0.0, 0.0, 3.0580, -15.920],
]


def _sym(tri):
    n = len(tri)
    m = {}
    for i in range(n):
        for j in range(i + 1):
            a, b = _UORDER[i], _UORDER[j]
            m[(a, b)] = m[(b, a)] = tri[i][j]
    return m


U0 = _sym(_U0_TRI)
UT = _sym(_UT_TRI)


def u_ij(a, b, T):
    """UNIQUAC interaction energy parameter u_ij at temperature T [K] (Darde eqs, Tables 2-5/2-6)."""
    return U0[(a, b)] + UT[(a, b)] * (T - T0)


# ---------------------------------------------------------------------------
# Standard-state thermodynamics.
# ---------------------------------------------------------------------------
def cp0(species, T):
    """Standard-state heat capacity Cp0 [J/mol/K] at T [K] (Helgeson form, Darde eq 2.22).
    Raises if the species' coefficients are not in an open source (see module docstring)."""
    cp = STANDARD_STATE[species][2]
    if cp is None:
        raise ValueError(f"Cp0 coefficients for {species} are not in an open source "
                         f"(Thomsen & Rasmussen 1999); not fabricated.")
    a, b, c = cp
    return a + b * T + c / (T - 200.0)


def _dcp_reaction_ok(reaction):
    return all(STANDARD_STATE[s][2] is not None for s in REACTIONS[reaction])


def mu0_over_RT(species, T):
    """Standard-state chemical potential mu0_i(T)/RT, referenced so that mu0(T0)/RT0 = dGf/(R*T0).
    Temperature dependence via Gibbs-Helmholtz (Darde eq 2.21) with Cp(T) (eq 2.23):

        d(mu0/RT)/dT = -H(T)/(R T^2),   H(T) = dHf + integral_{T0}^{T} Cp dT'

    Closed-form for Cp = a + b T + c/(T-200).  Requires the species' Cp coefficients.
    """
    dGf, dHf, cp = STANDARD_STATE[species]
    g0 = dGf * 1000.0 / (R * T0)                     # mu0(T0)/(R T0)
    if T == T0:
        return g0
    a, b, c = cp
    # H(T) = dHf + a(T-T0) + b/2 (T^2-T0^2) + c*ln((T-200)/(T0-200))
    # integral of -H/(R T'^2) dT' from T0 to T, added to g0*(... ) -- integrate d(mu/RT).
    # Standard result (constant + linear + hyperbolic Cp), all per R:
    dHf_J = dHf * 1000.0
    A = a
    B = b
    C = c
    # antiderivative pieces of -H(T')/(R T'^2):
    def F(t):
        # integral of -[dHf + A(t-T0) + B/2 (t^2-T0^2) + C ln((t-200)/(T0-200))] / (R t^2) dt
        H0 = dHf_J - A * T0 - 0.5 * B * T0 * T0                     # constant part of H(t)
        # H(t) = H0 + A t + (B/2) t^2 + C ln((t-200)/(T0-200))
        # -H/(R t^2) split:
        term_const = H0 / (R) * (1.0 / t)                          # int -H0/(R t^2) = H0/(R t)
        term_A = -A / R * math.log(t)                              # int -A/(R t)
        term_B = -B / (2.0 * R) * t                                # int -(B/2)/(R)
        # C ln((t-200)/(T0-200)) / (R t^2):  int -C*ln((t-200)/K0)/(R t^2) dt.
        # By parts: int -ln((t-200)/K0)/t^2 dt = ln((t-200)/K0)/t - (1/200) ln((t-200)/t).
        K0 = T0 - 200.0
        term_C = (C / R) * (math.log((t - 200.0) / K0) / t - (1.0 / 200.0) * math.log((t - 200.0) / t))
        return term_const + term_A + term_B + term_C
    return g0 + (F(T) - F(T0))


def lnK(reaction, T):
    """Natural log of the equilibrium constant K_j(T) (activity basis) for a speciation reaction.
    ln K = -dG_rxn/(RT) = -sum(nu_i * mu0_i)/(RT) = -sum(nu_i * mu0_i/RT)."""
    stoich = REACTIONS[reaction]
    if T != T0 and not _dcp_reaction_ok(reaction):
        raise ValueError(f"{reaction} has a species with no open-source Cp; T-extrapolation "
                         f"unavailable (298.15 K only). Not fabricated.")
    return -sum(nu * mu0_over_RT(sp, T) for sp, nu in stoich.items())


def pK(reaction, T=T0):
    """-log10(K) for a reaction at T [K]."""
    return -lnK(reaction, T) / LN10


# ---------------------------------------------------------------------------
# Vapor-liquid equilibrium: Henry's-law constants (Rumpf & Maurer 1993; Darde eqs 2.12-2.13).
# Returned in MPa on the mole-fraction scale (H* = K_H / M_w with M_w in kg/mol).
# ---------------------------------------------------------------------------
M_W = 0.0180152           # kg/mol, molar mass of water


def henry_nh3_MPa(T):
    """Henry's-law constant for NH3 in water [MPa, mole-fraction scale], 273.15-433.15 K.
    Darde eq 2.12: ln(K_H/(MPa*kg/mol)) = 3.932 - 1879.02/T - 355134.1/T^2 ; H* = K_H / M_w."""
    kH = math.exp(3.932 - 1879.02 / T - 355134.1 / (T * T))     # MPa * kg/mol
    return kH / M_W


def henry_co2_MPa(T):
    """Henry's-law constant for CO2 in water [MPa, mole-fraction scale], 273.15-473.15 K.
    Darde eq 2.13: ln(K_H/(MPa*kg/mol)) = 192.876 - 9624.4/T - 28.749*ln(T) + 0.01441*T ; H*=K_H/M_w."""
    kH = math.exp(192.876 - 9624.4 / T - 28.749 * math.log(T) + 0.01441 * T)
    return kH / M_W


# ---------------------------------------------------------------------------
# UNIQUAC activity-coefficient model (combinatorial + residual). The Debye-Huckel long-range term and
# the full multiphase speciation/SRK-VLE solver are phase 1b; this exposes the validated short-range
# part and the parameter accessors it needs.
# ---------------------------------------------------------------------------
def uniquac_combinatorial_ln_gamma(x):
    """ln(gamma) combinatorial part for a liquid mole-fraction dict x (species -> mole fraction),
    rational/symmetric convention. Uses Darde r,q (Table 2-2). Returns dict species->ln gamma_comb."""
    sp = [s for s in x if x[s] > 0.0]
    r = {s: UNIQUAC_RQ[s][0] for s in sp}
    q = {s: UNIQUAC_RQ[s][1] for s in sp}
    rsum = sum(x[s] * r[s] for s in sp)
    qsum = sum(x[s] * q[s] for s in sp)
    out = {}
    for s in sp:
        phi = r[s] / rsum                      # volume fraction / x
        theta = q[s] / qsum                    # area fraction / x
        # ln gamma_c = ln(phi/x) + 1 - phi/x - 5 q [ ln(phi/theta) + 1 - phi/theta ]
        pt = phi / theta
        out[s] = math.log(phi) + 1.0 - phi - 5.0 * q[s] * (math.log(pt) + 1.0 - pt)
    return out


def uniquac_combinatorial_ln_gamma_inf(species, solvent="H2O"):
    """ln gamma_i^{C,inf}: combinatorial ln gamma of `species` at infinite dilution in pure solvent.
    Closed-form limit of uniquac_combinatorial_ln_gamma as x_i -> 0, x_solvent -> 1:
        phi_i/x_i -> r_i/r_w,  theta_i/x_i -> q_i/q_w,  phi_i/theta_i -> (r_i q_w)/(r_w q_i)."""
    ri, qi = UNIQUAC_RQ[species]
    rw, qw = UNIQUAC_RQ[solvent]
    phi = ri / rw
    pt = (ri * qw) / (rw * qi)
    return math.log(phi) + 1.0 - phi - 5.0 * qi * (math.log(pt) + 1.0 - pt)


def uniquac_residual_ln_gamma(x, T):
    """ln(gamma) residual (short-range, enthalpic) part, symmetric convention, at T [K].

    Thomsen Extended UNIQUAC residual term (Thomsen 1997 thesis eqs; Darde et al. 2010):
        ln g_i^R = q_i [ 1 - ln( sum_k th_k psi_ki ) - sum_k ( th_k psi_ik / sum_l th_l psi_lk ) ]
    with the surface-area fraction th_k = x_k q_k / sum_l x_l q_l and the Boltzmann factor
        psi_ki = exp( -(u_ki - u_ii) / T ),   u_ij(T) from u_ij() (Darde Tables 2-5/2-6, units K).
    Returns dict species -> ln gamma_res.  Validated for thermodynamic consistency (Gibbs-Duhem to
    1e-9, pure-component limit == 0, infinite-dilution limit matches the closed form below)."""
    sp = [s for s in x if x[s] > 0.0]
    q = {s: UNIQUAC_RQ[s][1] for s in sp}
    qsum = sum(x[s] * q[s] for s in sp)
    th = {s: x[s] * q[s] / qsum for s in sp}
    psi = {}
    for i in sp:
        uii = u_ij(i, i, T)
        for k in sp:
            psi[(k, i)] = math.exp(-(u_ij(k, i, T) - uii) / T)
    denom = {k: sum(th[l] * psi[(l, k)] for l in sp) for k in sp}   # sum_l th_l psi_lk
    out = {}
    for i in sp:
        s1 = math.log(denom[i])                                      # ln( sum_k th_k psi_ki )
        s2 = sum(th[k] * psi[(i, k)] / denom[k] for k in sp)
        out[i] = q[i] * (1.0 - s1 - s2)
    return out


def uniquac_residual_ln_gamma_inf(species, T, solvent="H2O"):
    """ln gamma_i^{R,inf}: residual ln gamma of `species` at infinite dilution in pure solvent.
    Closed-form limit of uniquac_residual_ln_gamma (th_solvent -> 1, th_others -> 0):
        ln g_i^{R,inf} = q_i [ 1 - ln(psi_wi) - psi_iw ],   w = solvent."""
    psi_wi = math.exp(-(u_ij(solvent, species, T) - u_ij(species, species, T)) / T)
    psi_iw = math.exp(-(u_ij(species, solvent, T) - u_ij(solvent, solvent, T)) / T)
    return UNIQUAC_RQ[species][1] * (1.0 - math.log(psi_wi) - psi_iw)


def short_range_ln_gamma(x, T, unsymmetric_species=None, solvent="H2O"):
    """Short-range activity coefficient ln gamma = combinatorial + residual, at T [K].

    By default returns the symmetric (rational) convention for every species.  Pass a set of
    `unsymmetric_species` (typically the ions and dissolved gases) to renormalise those to the
    unsymmetric (infinite-dilution-in-solvent) reference used by the electrolyte speciation solver:
        ln gamma_i^* = ln gamma_i(x) - ln gamma_i^{inf}.
    The solvent (water) is always left symmetric.

    NOTE — this is the SHORT-RANGE part only.  The full Extended UNIQUAC activity coefficient also
    carries the long-range Debye-Huckel electrostatic term, which is the remaining phase-1b work; do
    not use this as the complete electrolyte gamma yet."""
    comb = uniquac_combinatorial_ln_gamma(x)
    res = uniquac_residual_ln_gamma(x, T)
    unsym = unsymmetric_species or set()
    out = {}
    for s in comb:
        g = comb[s] + res[s]
        if s in unsym and s != solvent:
            g -= (uniquac_combinatorial_ln_gamma_inf(s, solvent)
                  + uniquac_residual_ln_gamma_inf(s, T, solvent))
        out[s] = g
    return out


if __name__ == "__main__":
    print("NH3-CO2-H2O Extended UNIQUAC property basis (C36 phase 1)")
    print(f"  Cp0(H2O, 298.15) = {cp0('H2O', T0):.3f} J/mol/K  (liquid water ~75.3)")
    for rx in ("R1_water", "R3_bicarb", "R4_carbonate", "R2_ammonium"):
        print(f"  pK[{rx:12s}] @25C = {pK(rx):.3f}")
    print(f"  pKw @0C  = {pK('R1_water', 273.15):.3f}   (lit 14.94)")
    print(f"  pKw @60C = {pK('R1_water', 333.15):.3f}   (lit 13.02)")
    print(f"  H_NH3(25C) = {henry_nh3_MPa(T0):.4f} MPa   H_CO2(25C) = {henry_co2_MPa(T0):.1f} MPa")
