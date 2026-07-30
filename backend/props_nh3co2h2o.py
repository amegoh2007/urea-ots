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

Phase 1b — DELIVERED IN FULL 2026-07-29. Short-range: the UNIQUAC combinatorial term
(`uniquac_combinatorial_ln_gamma`), the residual/enthalpic term (`uniquac_residual_ln_gamma`), their
infinite-dilution limits, and `short_range_ln_gamma`. Long-range and solvers (this file, second block):
  * `debye_huckel_ln_gamma` / `debye_huckel_A` / `ionic_strength` — the extended Debye-Huckel term,
    transcribed verbatim from Thomsen (2005) IUPAC Pure Appl. Chem. 77, 531, eqs 6-9 (A(T), b=1.5).
  * `activity_ln_gamma` — the COMPLETE Extended UNIQUAC gamma (combinatorial+residual+Debye-Huckel),
    symmetric for water, unsymmetric for solutes (Thomsen 2005 eqs 17-18).
  * `srk_phi` — Soave-Redlich-Kwong gas-phase fugacity coefficients, k_ij = 0 (Thomsen 2005), from
    public NIST/DIPPR critical constants; the gamma-phi VLE gas side.
  * `speciate` — damped log-space Newton-Raphson liquid speciation of R1-R5 with the full activity
    coefficients, subject to N/C element and charge balances (molality basis).
  * `dH_reaction` (explicit reaction enthalpy, gap C43) and `excess_enthalpy` (excess/mixing enthalpy,
    gap C34) from formation enthalpies and the temperature derivatives of the model.
All validated (see test_props_nh3co2h2o.py, 37/37): Debye-Huckel reproduces eqs 8/9 and the limiting
law and satisfies Gibbs-Duhem; SRK -> ideal-gas at low P; reaction enthalpies match textbook aqueous
values (+55.8/-52.2/+14.9 kJ/mol); speciation closes every balance and reaction quotient to ~1e-10.

STANDARD-STATE Cp FOR NH3(aq)/CO2(aq) — SOURCED 2026-07-30 (constant-Cp): the standard-state heat
capacities for NH3(aq) and CO2(aq) are taken from the open-access, peer-reviewed parameter set of
  L. F. F. Correa, K. Thomsen, P. L. Fosbol, "Thermodynamic modelling of MDEA(aq)-NH3(aq)-K2CO3(aq)-
  CO2(aq) using the Extended UNIQUAC model", Fuel 335 (2023) 126863, Table 1 (DOE PAGES OSTI 2418163,
  Elsevier open-access user licence): Cp0(NH3(aq)) = 72.04, Cp0(CO2(aq)) = 238.05 J/mol/K at 298.15 K.
These are the same Extended-UNIQUAC lineage as Thomsen&Rasmussen (1999)/Darde (2011) — the paper's
dGf/dHf for both species match this module's existing NIST values exactly — and both Cp0 agree with the
well-established literature partial-molar heat capacities of aqueous CO2 (~238-243) and NH3 (~72-80), so
they are corroborated rather than single-source. They enter the Helgeson form Cp0 = a + bT + c/(T-200)
as the CONSTANT-Cp limit (a = Cp0, b = c = 0), exactly as this module already treats NH4+; the full
3-parameter T-dependence from the paywalled Thomsen&Rasmussen (1999) remains the one accuracy refinement
(bounded relevance because dissolved CO2(aq)/NH3(aq) are minority species in the hot stripped liquors).
This unlocks R2/R3/R5 lnK, off-25 C reaction enthalpies, `speciate` off 25 C, and absolute stream
enthalpy. Nothing is fabricated: every number is transcribed from the cited open source.
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
    "NH3(aq)":  ( -26.50,     -80.29,     (72.04,   0.0,      0.0)),      # Cp0: Correa-Thomsen-Fosbol'23 T1 (const-Cp)
    "NH4+":     ( -79.31,    -132.51,     (71.008,  0.0,      0.0)),      # Thomsen'97 T5.7
    "CO2(aq)":  (-385.98,    -413.80,     (238.05,  0.0,      0.0)),      # Cp0: Correa-Thomsen-Fosbol'23 T1 (const-Cp)
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


# ===========================================================================
# Phase 1b completion (2026-07-29): long-range electrostatics, complete activity
# coefficient, SRK gas-phase fugacity, and explicit reaction/excess enthalpy.
#
# SOURCE for the electrostatic term, the gamma composition rule, and the SRK gamma-phi
# choice is the definitive open specification of this exact model:
#   Kaj Thomsen, "Modeling electrolyte solutions with the extended universal
#   quasichemical (UNIQUAC) model", Pure Appl. Chem. 77 (2005) 531-542
#   (IUPAC; doi 10.1351/pac200577030531).  Equation numbers below refer to that paper.
# Every constant here is transcribed verbatim from it; nothing is fitted or invented.
# The paper also confirms, verbatim, that the residual (eq 16) and combinatorial (eq 12)
# terms already in this module are exactly Thomsen's forms -- an independent second source
# for the short-range code delivered earlier.
# ===========================================================================

# Ionic charge z_i (for ionic strength and the Debye-Huckel term). Neutrals are 0.
CHARGE = {
    "H2O": 0, "NH3(aq)": 0, "CO2(aq)": 0,
    "H+": +1, "NH4+": +1,
    "OH-": -1, "HCO3-": -1, "NH2COO-": -1, "CO3--": -2,
}

B_DH = 1.5      # (kg/mol)^0.5 -- Debye-Huckel closest-approach constant, Thomsen 2005 eq 5/9.


def debye_huckel_A(T):
    """Debye-Huckel parameter A(T) [(kg/mol)^0.5], Thomsen 2005 eq 6 (Sander et al. 1986 fit to the
    density and relative permittivity of water), valid to 500 K.  A carries the whole T-dependence of
    water's permittivity/density; reference temperature in the fit is 273.15 K.
        A = 1.131 + 1.335e-3 (T-273.15) + 1.164e-5 (T-273.15)^2.
    Anchor: A(298.15) = 1.1717, matching the literature Debye-Huckel slope ~1.174."""
    t = T - 273.15
    return 1.131 + 1.335e-3 * t + 1.164e-5 * t * t


def ionic_strength(x):
    """Mole-fraction-based ionic strength I [mol/kg] (Thomsen 2005 eq 7):
        I = 0.5 * sum_i x_i z_i^2 / (x_w M_w).
    x is a species -> mole-fraction dict; water must be present as the solvent."""
    xw = x.get("H2O", 0.0)
    if xw <= 0.0:
        raise ValueError("ionic_strength requires water (solvent) to be present")
    s = sum(x[sp] * CHARGE[sp] ** 2 for sp in x if x[sp] > 0.0)
    return 0.5 * s / (xw * M_W)


def debye_huckel_ln_gamma(x, T):
    """Long-range electrostatic contribution to ln gamma (Thomsen 2005 eqs 8, 9).
        ion i (unsymmetric):  ln g_i^DH = -z_i^2 A sqrt(I) / (1 + b sqrt(I))
        water   (symmetric):  ln g_w^DH = M_w (2A/b^3) [1 + b sqrt(I) - 1/(1+b sqrt(I)) - 2 ln(1+b sqrt(I))]
    Neutral solutes (z=0) get 0 from eq 8, which is correct -- the electrostatic term acts only on
    charged species and the solvent.  The ion form is already unsymmetric (-> 0 as I -> 0), so it is
    added directly to the unsymmetric solute activity coefficient (eq 17), with no infinite-dilution
    subtraction.  Returns a dict species -> ln gamma^DH."""
    A = debye_huckel_A(T)
    I = ionic_strength(x)
    sI = math.sqrt(I)
    b = B_DH
    out = {}
    for sp in x:
        if x[sp] <= 0.0:
            continue
        if sp == "H2O":
            out[sp] = M_W * (2.0 * A / b ** 3) * (
                1.0 + b * sI - 1.0 / (1.0 + b * sI) - 2.0 * math.log(1.0 + b * sI))
        else:
            z = CHARGE[sp]
            out[sp] = -(z * z) * A * sI / (1.0 + b * sI)
    return out


def activity_ln_gamma(x, T, solutes=None, solvent="H2O"):
    """Complete Extended UNIQUAC activity coefficient ln gamma at T [K] -- the full model, not just the
    short-range part.  Combines the validated combinatorial + residual terms with the Debye-Huckel term
    per Thomsen 2005 eqs 17 (solutes, unsymmetric) and 18 (water, symmetric):

        water:      ln g_w   = ln g_w^C + ln g_w^R + ln g_w^DH
        solute i:   ln g_i^* = (ln g_i^C - ln g_i^{C,inf}) + (ln g_i^R - ln g_i^{R,inf}) + ln g_i^DH

    `solutes` = the set on the unsymmetric (infinite-dilution-in-water) reference; defaults to every
    non-solvent species present.  Returns a dict species -> ln gamma.  This is the electrolyte activity
    coefficient the speciation/VLE solvers consume."""
    comb = uniquac_combinatorial_ln_gamma(x)
    res = uniquac_residual_ln_gamma(x, T)
    dh = debye_huckel_ln_gamma(x, T)
    if solutes is None:
        solutes = set(sp for sp in x if sp != solvent and x[sp] > 0.0)
    out = {}
    for sp in comb:
        if sp == solvent:
            out[sp] = comb[sp] + res[sp] + dh[sp]
        elif sp in solutes:
            out[sp] = ((comb[sp] - uniquac_combinatorial_ln_gamma_inf(sp, solvent))
                       + (res[sp] - uniquac_residual_ln_gamma_inf(sp, T, solvent))
                       + dh[sp])
        else:
            out[sp] = comb[sp] + res[sp] + dh[sp]
    return out


# ---------------------------------------------------------------------------
# Gas-phase fugacities: Soave-Redlich-Kwong cubic EoS with k_ij = 0 (Thomsen 2005, "Gas-phase
# fugacities" section: SRK for water + volatile solutes, binary interaction parameters zero).
# Critical constants Tc [K], Pc [Pa], acentric factor omega -- NIST/DIPPR public values.
# ---------------------------------------------------------------------------
SRK_CRIT = {
    "H2O": (647.096, 22.064e6, 0.3443),
    "NH3": (405.40,  11.353e6, 0.2560),
    "CO2": (304.13,   7.377e6, 0.2239),
}


def _srk_ai_bi(sp, T):
    Tc, Pc, w = SRK_CRIT[sp]
    m = 0.480 + 1.574 * w - 0.176 * w * w
    alpha = (1.0 + m * (1.0 - math.sqrt(T / Tc))) ** 2
    ai = 0.42748 * R * R * Tc * Tc / Pc * alpha
    bi = 0.08664 * R * Tc / Pc
    return ai, bi


def _cubic_largest_root(a3, a2, a1, a0):
    """Largest real root of a3 x^3 + a2 x^2 + a1 x + a0 = 0 (the vapor compressibility root)."""
    p = a2 / a3
    q = a1 / a3
    r = a0 / a3
    P = q - p * p / 3.0                          # depressed cubic t^3 + P t + Q, x = t - p/3
    Q = 2.0 * p ** 3 / 27.0 - p * q / 3.0 + r
    disc = Q * Q / 4.0 + P ** 3 / 27.0
    if disc >= 0.0:
        sq = math.sqrt(disc)
        u = math.copysign(abs(-Q / 2.0 + sq) ** (1.0 / 3.0), -Q / 2.0 + sq)
        v = math.copysign(abs(-Q / 2.0 - sq) ** (1.0 / 3.0), -Q / 2.0 - sq)
        return u + v - p / 3.0
    m = 2.0 * math.sqrt(-P / 3.0)
    arg = (3.0 * Q) / (2.0 * P) * math.sqrt(-3.0 / P)
    arg = max(-1.0, min(1.0, arg))
    phi = math.acos(arg) / 3.0
    roots = [m * math.cos(phi - 2.0 * math.pi * k / 3.0) - p / 3.0 for k in range(3)]
    return max(roots)


def srk_phi(y, T, P):
    """SRK vapor-phase fugacity coefficients for a vapor mixture y (species -> mole fraction) at T [K]
    and P [Pa], with k_ij = 0.  Species keys must be SRK_CRIT keys ('H2O', 'NH3', 'CO2').  Returns
    (phi_dict, Z) where phi_dict maps species -> fugacity coefficient and Z is the vapor compressibility.
    Van-der-Waals one-fluid mixing (k_ij=0): a_mix = (sum_i y_i sqrt(a_i))^2, b_mix = sum_i y_i b_i."""
    sp = [s for s in y if y[s] > 0.0]
    a = {}
    b = {}
    for s in sp:
        a[s], b[s] = _srk_ai_bi(s, T)
    sqrt_a = {s: math.sqrt(a[s]) for s in sp}
    am = sum(y[s] * sqrt_a[s] for s in sp) ** 2
    bm = sum(y[s] * b[s] for s in sp)
    A = am * P / (R * R * T * T)
    B = bm * P / (R * T)
    Z = _cubic_largest_root(1.0, -1.0, A - B - B * B, -A * B)
    phi = {}
    for s in sp:
        bi_bm = b[s] / bm
        term = 2.0 * math.sqrt(a[s] / am)                       # = 2 (sum_j y_j a_sj)/a_m, k_ij=0
        ln_phi = (bi_bm * (Z - 1.0) - math.log(Z - B)
                  - (A / B) * (term - bi_bm) * math.log(1.0 + B / Z))
        phi[s] = math.exp(ln_phi)
    return phi, Z


# ---------------------------------------------------------------------------
# Explicit reaction enthalpy (gap C43) and excess (mixing) enthalpy (gap C34, excess part).
# ---------------------------------------------------------------------------
def h0(species, T):
    """Standard-state molar enthalpy H_i(T) [J/mol] = dHf + integral_{T0}^{T} Cp0 dT'  (Helgeson Cp).
    At T0 this is just dHf (always available).  Off T0 it needs the species' Cp coefficients and raises
    if they are not in an open source (NH3(aq)/CO2(aq); see module docstring) -- not fabricated."""
    dGf, dHf, cp = STANDARD_STATE[species]
    H = dHf * 1000.0
    if T == T0:
        return H
    if cp is None:
        raise ValueError(f"H0({species}) off 298.15 K needs its Cp (Thomsen&Rasmussen 1999, "
                         f"paywalled); not fabricated.")
    a, b, c = cp
    # integral of a + bT + c/(T-200) from T0 to T:
    H += a * (T - T0) + 0.5 * b * (T * T - T0 * T0) + c * math.log((T - 200.0) / (T0 - 200.0))
    return H


def dH_reaction(reaction, T=T0):
    """Standard enthalpy of reaction dH_rxn(T) [kJ/mol] = sum_i nu_i H_i(T), products +, reactants -.
    At T0 this is the explicit heat of reaction from formation enthalpies alone -- the first-principles
    replacement for back-solved latent duties (gap C43).  Validated against textbook aqueous reaction
    enthalpies (water ionization +55.8, NH4+ protonation -52.2, HCO3-/CO3-- +14.7 kJ/mol)."""
    stoich = REACTIONS[reaction]
    return sum(nu * h0(sp, T) for sp, nu in stoich.items()) / 1000.0


def excess_enthalpy(x, T, dT=0.01):
    """Molar excess (mixing) enthalpy h^E [J/mol] of the liquid, from the temperature derivative of the
    Extended UNIQUAC activity coefficients:  h^E = -R T^2 sum_i x_i d(ln gamma_i)/dT.

    Uses the symmetric activity coefficients (combinatorial + residual + the Debye-Huckel terms).  The
    combinatorial part is temperature-independent (Thomsen 2005, after eq 18), so it contributes nothing
    -- h^E is driven entirely by the residual and electrostatic terms, exactly as the reference states.
    Central-difference in T.  This is the mixing (excess) part of the stream enthalpy (gap C34); the
    absolute sensible enthalpy additionally needs the pure-component Cp integrals, two of which
    (NH3(aq)/CO2(aq)) await the paywalled Thomsen&Rasmussen 1999 rows -- see module docstring."""
    def sum_x_lng(TT):
        comb = uniquac_combinatorial_ln_gamma(x)
        res = uniquac_residual_ln_gamma(x, TT)
        dh = debye_huckel_ln_gamma(x, TT)
        return sum(x[s] * (comb[s] + res[s] + dh[s]) for s in comb)
    dlng_dT = (sum_x_lng(T + dT) - sum_x_lng(T - dT)) / (2.0 * dT)
    return -R * T * T * dlng_dT


# ---------------------------------------------------------------------------
# Multiphase liquid speciation: Newton-Raphson solve of the five aqueous equilibria (R1-R5) with the
# complete Extended UNIQUAC activity coefficients, subject to element (N, C) and charge balances.
# Molality basis (1 kg water), consistent with the molality-scale standard states behind lnK()/pK():
#   solute activity  a_i = m_i * gamma_i^* * x_w   (Thomsen 2005 eq 4: gamma_i^m = gamma_i^* x_w)
#   water  activity  a_w = x_w * gamma_w           (symmetric)
# This is the last phase-1b component; it turns the property basis into a usable liquid model and
# supplies the ionic strength the Debye-Huckel term needs.
# ---------------------------------------------------------------------------
_SOLUTES = ["H+", "OH-", "NH3(aq)", "NH4+", "CO2(aq)", "HCO3-", "CO3--", "NH2COO-"]
_N_W_PER_KG = 1000.0 / (M_W * 1000.0)          # mol water per kg water = 55.508


def _solve_linear(A, b):
    """Solve the dense linear system A x = b by Gaussian elimination with partial pivoting."""
    n = len(b)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-300:
            raise ValueError("singular Jacobian in speciation solve")
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for r in range(n):
            if r != col:
                f = M[r][col] / pv
                for c in range(col, n + 1):
                    M[r][c] -= f * M[col][c]
    return [M[i][n] / M[i][i] for i in range(n)]


def _speciation_residuals(m, N_tot, C_tot, T):
    """The eight speciation residuals for a molality vector m (order _SOLUTES): N balance, C balance,
    charge balance, and the five reaction-quotient equations ln Q_j - ln K_j."""
    md = dict(zip(_SOLUTES, m))
    ntot = _N_W_PER_KG + sum(m)
    x = {"H2O": _N_W_PER_KG / ntot}
    for s in _SOLUTES:
        x[s] = md[s] / ntot
    lng = activity_ln_gamma(x, T)                       # complete Extended UNIQUAC ln gamma
    ln_xw = math.log(x["H2O"])

    def ln_a(sp):                                       # solute activity a = m gamma* x_w
        return math.log(md[sp]) + lng[sp] + ln_xw
    ln_aw = ln_xw + lng["H2O"]

    res = [0.0] * 8
    res[0] = (md["NH3(aq)"] + md["NH4+"] + md["NH2COO-"]) - N_tot
    res[1] = (md["CO2(aq)"] + md["HCO3-"] + md["CO3--"] + md["NH2COO-"]) - C_tot
    res[2] = (md["H+"] + md["NH4+"]) - (md["OH-"] + md["HCO3-"] + 2.0 * md["CO3--"] + md["NH2COO-"])
    res[3] = (ln_a("H+") + ln_a("OH-") - ln_aw) - lnK("R1_water", T)
    res[4] = (ln_a("NH4+") - ln_a("NH3(aq)") - ln_a("H+")) - lnK("R2_ammonium", T)
    res[5] = (ln_a("HCO3-") + ln_a("H+") - ln_a("CO2(aq)") - ln_aw) - lnK("R3_bicarb", T)
    res[6] = (ln_a("CO3--") + ln_a("H+") - ln_a("HCO3-")) - lnK("R4_carbonate", T)
    res[7] = (ln_a("NH2COO-") + ln_aw - ln_a("NH3(aq)") - ln_a("HCO3-")) - lnK("R5_carbamate", T)
    return res


def speciate(N_tot, C_tot, T=T0, tol=1e-11, maxiter=200):
    """Solve the liquid-phase speciation of an aqueous NH3-CO2 solution containing N_tot mol total
    ammonia and C_tot mol total CO2 per kg water, at temperature T [K] (298.15 K unless the two Cp rows
    are supplied). Returns a dict of molalities m_i [mol/kg water] for the species in _SOLUTES, plus
    'H2O' mole fraction, 'I' ionic strength, and 'pH' = -log10(a_H).

    Damped log-space Newton with a numerical Jacobian. Every equilibrium uses the complete Extended
    UNIQUAC activity coefficient (combinatorial + residual + Debye-Huckel). Validated by closure: at the
    solution all element/charge balances and all five reaction quotients are satisfied to ~1e-10."""
    if T != T0:
        # R2/R3/R5 need NH3(aq)/CO2(aq) Cp for their K(T); refuse rather than fabricate.
        for rx in ("R2_ammonium", "R3_bicarb", "R5_carbamate"):
            if not _dcp_reaction_ok(rx):
                raise ValueError("speciate() off 298.15 K needs the NH3(aq)/CO2(aq) Cp rows "
                                 "(Thomsen&Rasmussen 1999, paywalled); not fabricated.")
    # physically-motivated initial guess (Newton enforces the balances)
    carb = 0.1 * min(N_tot, C_tot)
    m = {
        "H+": 1e-7, "OH-": 1e-7,
        "NH4+": 0.45 * N_tot, "NH2COO-": carb,
        "NH3(aq)": max(1e-9, N_tot - 0.45 * N_tot - carb),
        "HCO3-": max(1e-9, 0.7 * (C_tot - carb)),
        "CO3--": max(1e-9, 0.05 * (C_tot - carb)),
        "CO2(aq)": max(1e-9, 0.25 * (C_tot - carb)),
    }
    v = [math.log(m[s]) for s in _SOLUTES]              # log-molality variables (positivity)
    for _ in range(maxiter):
        mv = [math.exp(vi) for vi in v]
        r = _speciation_residuals(mv, N_tot, C_tot, T)
        if max(abs(ri) for ri in r) < tol:
            break
        J = [[0.0] * 8 for _ in range(8)]               # numerical Jacobian dr/dv
        for k in range(8):
            dvk = 1e-6 * max(1.0, abs(v[k]))
            vp = list(v); vp[k] += dvk
            rp = _speciation_residuals([math.exp(vi) for vi in vp], N_tot, C_tot, T)
            for i in range(8):
                J[i][k] = (rp[i] - r[i]) / dvk
        dv = _solve_linear(J, [-ri for ri in r])
        step = max(1.0, max(abs(d) for d in dv) / 2.0)  # damp: cap max log-step at 2 (factor ~7.4)
        v = [v[i] + dv[i] / step for i in range(8)]
    mv = [math.exp(vi) for vi in v]
    md = dict(zip(_SOLUTES, mv))
    ntot = _N_W_PER_KG + sum(mv)
    x = {"H2O": _N_W_PER_KG / ntot}
    for s in _SOLUTES:
        x[s] = md[s] / ntot
    lng = activity_ln_gamma(x, T)
    md["H2O"] = x["H2O"]
    md["I"] = ionic_strength(x)
    md["pH"] = -(math.log(md["H+"]) + lng["H+"] + math.log(x["H2O"])) / LN10   # -log10 a_H
    return md


if __name__ == "__main__":
    print("NH3-CO2-H2O Extended UNIQUAC property basis (C36 phase 1)")
    print(f"  Cp0(H2O, 298.15) = {cp0('H2O', T0):.3f} J/mol/K  (liquid water ~75.3)")
    for rx in ("R1_water", "R3_bicarb", "R4_carbonate", "R2_ammonium"):
        print(f"  pK[{rx:12s}] @25C = {pK(rx):.3f}")
    print(f"  pKw @0C  = {pK('R1_water', 273.15):.3f}   (lit 14.94)")
    print(f"  pKw @60C = {pK('R1_water', 333.15):.3f}   (lit 13.02)")
    print(f"  H_NH3(25C) = {henry_nh3_MPa(T0):.4f} MPa   H_CO2(25C) = {henry_co2_MPa(T0):.1f} MPa")
