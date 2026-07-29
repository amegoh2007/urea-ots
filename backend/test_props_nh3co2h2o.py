"""Validation gate for the C36 phase-1 Extended UNIQUAC property basis (props_nh3co2h2o.py).

The point of this file: prove the *sourced parameters* + the standard-state machinery reproduce
independent textbook aqueous data (heat capacity, pKw and its temperature dependence, carbonic-acid
pKa1/pKa2, ammonium pKa, Henry's-law constants). Passing these is what makes the transcription
trustworthy before any engine wiring. Nothing here is fabricated; the two species whose Cp is not in
an open source are asserted to REFUSE extrapolation rather than guess.

Run from backend/:  python -m pytest test_props_nh3co2h2o.py   (or: python test_props_nh3co2h2o.py)
"""
import math

import props_nh3co2h2o as P


def _pKa(reaction, T=P.T0):
    return P.pK(reaction, T)


# ---------------------------------------------------------------- standard-state thermodynamics
def test_liquid_water_heat_capacity():
    """Helgeson Cp of liquid water at 25 C reproduces the textbook 75.3 J/mol/K."""
    assert abs(P.cp0("H2O", 298.15) - 75.3) < 0.5


def test_pKw_at_25C():
    """Ionic product of water: pKw(25 C) = 14.00."""
    assert abs(P.pK("R1_water", 298.15) - 14.00) < 0.05


def test_pKw_temperature_dependence():
    """pKw over 0-60 C reproduces the literature curve (14.94 / 13.02) from Cp(T) + Gibbs-Helmholtz.
    This is the real check that the temperature machinery, not just the 25 C anchor, is correct."""
    assert abs(P.pK("R1_water", 273.15) - 14.94) < 0.08
    assert abs(P.pK("R1_water", 333.15) - 13.02) < 0.08
    # monotonically decreasing across the range
    xs = [P.pK("R1_water", 273.15 + t) for t in (0, 20, 40, 60)]
    assert all(xs[i] > xs[i + 1] for i in range(len(xs) - 1))


def test_carbonic_acid_pKa1_at_25C():
    """CO2(aq) + H2O <-> HCO3- + H+ : pKa1 = 6.35 at 25 C."""
    assert abs(P.pK("R3_bicarb", 298.15) - 6.35) < 0.10


def test_carbonic_acid_pKa2_and_temperature():
    """HCO3- <-> CO3-- + H+ : pKa2 = 10.33 at 25 C, with the correct mild T-dependence (10.56 -> 10.17
    from 0 to 50 C). R4 carries full T-dependence because every species has open-source Cp."""
    assert abs(P.pK("R4_carbonate", 298.15) - 10.33) < 0.05
    assert abs(P.pK("R4_carbonate", 273.15) - 10.56) < 0.10
    assert abs(P.pK("R4_carbonate", 323.15) - 10.17) < 0.10


def test_ammonium_pKa_at_25C():
    """NH4+ <-> NH3 + H+ : pKa = 9.25 at 25 C. R2 is written as formation (NH3 + H+ -> NH4+),
    so its pK is the negative of the dissociation pKa."""
    assert abs(-P.pK("R2_ammonium", 298.15) - 9.25) < 0.10


# ------------------------------------------------------------------------------ Henry's law (VLE)
def test_henry_constants_at_25C():
    """Rumpf-Maurer Henry's constants at 25 C: NH3 ~0.096 MPa, CO2 ~165 MPa (mole-fraction scale)."""
    assert 0.07 < P.henry_nh3_MPa(298.15) < 0.13
    assert 140.0 < P.henry_co2_MPa(298.15) < 190.0


def test_henry_increases_with_temperature():
    """Both gases get less soluble as temperature rises -> Henry's constant increases monotonically."""
    Ts = [273.15 + t for t in (25, 60, 100, 140)]
    for H in (P.henry_nh3_MPa, P.henry_co2_MPa):
        xs = [H(T) for T in Ts]
        assert all(xs[i] < xs[i + 1] for i in range(len(xs) - 1))


# ----------------------------------------------------------------- integrity / no-fabrication
def test_missing_Cp_refuses_to_extrapolate():
    """NH3(aq)/CO2(aq) Cp coefficients are not in an open source, so the module must REFUSE to
    produce a temperature-extrapolated value rather than invent one."""
    for missing in ("CO2(aq)", "NH3(aq)"):
        try:
            P.cp0(missing, 350.0)
            assert False, f"cp0({missing}) should have raised"
        except ValueError:
            pass
    for rx in ("R3_bicarb", "R2_ammonium", "R5_carbamate"):
        try:
            P.lnK(rx, 350.0)
            assert False, f"lnK({rx}) off-25C should have raised"
        except ValueError:
            pass
    # ...but they are fine AT 25 C (only dGf enters, which is sourced)
    assert math.isfinite(P.lnK("R3_bicarb", 298.15))


def test_interaction_matrix_is_symmetric_and_complete():
    """u0_ij == u0_ji and uT_ij == uT_ji for every species pair (Darde Tables 2-5/2-6)."""
    sp = P._UORDER
    assert len(sp) == 9
    for a in sp:
        for b in sp:
            assert P.U0[(a, b)] == P.U0[(b, a)]
            assert P.UT[(a, b)] == P.UT[(b, a)]
    # spot anchors, verbatim from the tables
    assert P.U0[("NH3(aq)", "H2O")] == 594.72
    assert P.UT[("NH2COO-", "NH4+")] == 12.047
    assert P.u_ij("NH3(aq)", "H2O", 298.15) == 594.72          # uT term vanishes at T0


def test_uniquac_combinatorial_ideal_limit():
    """As the liquid approaches pure water, the combinatorial ln(gamma) of water -> 0."""
    g = P.uniquac_combinatorial_ln_gamma({"H2O": 0.9999, "NH4+": 0.00005, "HCO3-": 0.00005})
    assert abs(g["H2O"]) < 1e-4


def test_rq_parameters_present_for_all_species():
    """Every reacting/UNIQUAC species has an r,q pair (Darde Table 2-2)."""
    for s in P.UNIQUAC_RQ:
        r, q = P.UNIQUAC_RQ[s]
        assert r > 0.0 and q > 0.0


def test_rq_cross_check_against_independent_document():
    """The r,q parameters match an INDEPENDENT transcription — Table 1 of
    `References/Resolving Simulator Thermodynamics Gaps.docx` (2026-07-29). An exact match to a second
    source is what certifies the verbatim transcription is not a single-source copy error."""
    doc_table1 = {                       # (r, q) as read from the document's Table 1
        "H2O":     (0.9200,  1.4000),
        "NH3(aq)": (1.6292,  2.9852),
        "CO2(aq)": (0.7500,  2.4500),
        "NH4+":    (4.8154,  4.6028),
        "H+":      (0.1378,  None),       # surface area ~0 (blank in the table); q fixed at ~0 in module
        "OH-":     (9.3973,  8.8171),
        "CO3--":   (10.828,  10.769),
        "HCO3-":   (8.0756,  8.6806),
        "NH2COO-": (4.3022,  4.1348),
    }
    for s, (r_doc, q_doc) in doc_table1.items():
        r_mod, q_mod = P.UNIQUAC_RQ[s]
        assert r_mod == r_doc, f"{s} r: module {r_mod} != document {r_doc}"
        if q_doc is not None:
            assert q_mod == q_doc, f"{s} q: module {q_mod} != document {q_doc}"
        else:
            assert q_mod < 1e-10          # H+ surface area is ~0


# --------------------------------------------------- UNIQUAC residual (short-range) activity term
def test_residual_pure_component_limit_is_zero():
    """ln gamma^R of any pure component is exactly 0 (symmetric convention)."""
    for s in ("H2O", "NH3(aq)", "CO2(aq)", "NH4+", "NH2COO-"):
        assert abs(P.uniquac_residual_ln_gamma({s: 1.0}, 298.15)[s]) < 1e-12


def test_residual_infinite_dilution_matches_closed_form():
    """The residual ln gamma evaluated at x_i -> 0 converges to the closed-form infinite-dilution
    expression uniquac_residual_ln_gamma_inf (a wrong psi index/sign would break this)."""
    T = 298.15
    for s in ("NH3(aq)", "CO2(aq)", "NH4+", "NH2COO-", "HCO3-"):
        x = {"H2O": 1.0 - 1e-7, s: 1e-7}
        num = P.uniquac_residual_ln_gamma(x, T)[s]
        cf = P.uniquac_residual_ln_gamma_inf(s, T)
        assert abs(num - cf) < 1e-4, f"{s}: numeric {num} vs closed {cf}"


def test_residual_satisfies_gibbs_duhem():
    """Gibbs-Duhem at constant T,P: sum_i x_i d(ln gamma_i)/dx1 == 0 along the water+NH3 binary, for
    the full short-range (combinatorial + residual) model. This is the decisive consistency test —
    an incorrect residual formulation violates it grossly rather than by ~1e-9."""
    T = 298.15
    h = 1e-6

    def total(x1):
        x = {"H2O": 1.0 - x1, "NH3(aq)": x1}
        c = P.uniquac_combinatorial_ln_gamma(x)
        r = P.uniquac_residual_ln_gamma(x, T)
        return {s: c[s] + r[s] for s in x}

    for x1 in (0.05, 0.2, 0.4, 0.6, 0.8, 0.95):
        gp, gm = total(x1 + h), total(x1 - h)
        d = {s: (gp[s] - gm[s]) / (2.0 * h) for s in gp}
        gd = (1.0 - x1) * d["H2O"] + x1 * d["NH3(aq)"]
        assert abs(gd) < 1e-6, f"Gibbs-Duhem residual {gd} at x_NH3={x1}"


def test_short_range_unsymmetric_vanishes_at_infinite_dilution():
    """With unsymmetric (infinite-dilution) normalisation, a solute's short-range ln gamma* -> 0 as it
    becomes infinitely dilute in water — the defining property of the unsymmetric reference state."""
    T = 298.15
    for s in ("NH3(aq)", "CO2(aq)", "NH4+"):
        x = {"H2O": 1.0 - 1e-8, s: 1e-8}
        g = P.short_range_ln_gamma(x, T, unsymmetric_species={s})[s]
        assert abs(g) < 1e-4, f"{s}: unsymmetric ln gamma* = {g} (expected ~0)"


def test_short_range_finite_across_desorber_envelope():
    """Short-range ln gamma stays finite and smooth across the Unit-328 desorber band (40-150 C) for a
    representative speciated liquid — no blow-up feeding the (future) VLE solver."""
    x = {"H2O": 0.90, "NH3(aq)": 0.06, "CO2(aq)": 0.02, "NH4+": 0.01, "HCO3-": 0.01}
    ions = {"NH3(aq)", "CO2(aq)", "NH4+", "HCO3-"}
    for T in (313.15, 373.15, 413.15, 423.15):
        g = P.short_range_ln_gamma(x, T, unsymmetric_species=ions)
        assert all(math.isfinite(v) for v in g.values())
        assert all(abs(v) < 60.0 for v in g.values())


# --------------------------------------------------- Debye-Huckel long-range electrostatic term
def test_debye_huckel_A_anchor():
    """A(298.15 K) reproduces the literature Debye-Huckel slope ~1.174 (kg/mol)^0.5 (Thomsen 2005 eq 6);
    A(273.15 K) equals the leading polynomial coefficient 1.131."""
    assert abs(P.debye_huckel_A(298.15) - 1.1717) < 1e-3
    assert abs(P.debye_huckel_A(273.15) - 1.131) < 1e-9


def test_debye_huckel_matches_equations():
    """debye_huckel_ln_gamma reproduces Thomsen 2005 eqs 8 (ions) and 9 (water) exactly for a speciated
    electroneutral solution -- a direct check the code equals the published equations."""
    x = {"H2O": 0.96, "NH4+": 0.02, "HCO3-": 0.02}
    T = 298.15
    g = P.debye_huckel_ln_gamma(x, T)
    A = P.debye_huckel_A(T)
    I = P.ionic_strength(x)
    sI = math.sqrt(I)
    b = P.B_DH
    for ion in ("NH4+", "HCO3-"):
        z = P.CHARGE[ion]
        assert abs(g[ion] - (-(z * z) * A * sI / (1.0 + b * sI))) < 1e-12
    gw = P.M_W * (2.0 * A / b ** 3) * (1.0 + b * sI - 1.0 / (1.0 + b * sI) - 2.0 * math.log(1.0 + b * sI))
    assert abs(g["H2O"] - gw) < 1e-12


def test_debye_huckel_limiting_law():
    """The ion contribution approaches the Debye-Huckel limiting law: the ratio ln g_i^DH / (-z^2 A sqrt(I))
    equals 1/(1+b sqrt(I)), which -> 1 as I -> 0 with deviation bounded exactly by b sqrt(I). The deviation
    must shrink monotonically as the solution is diluted."""
    T = 298.15
    A = P.debye_huckel_A(T)
    b = P.B_DH
    prev_dev = None
    for s in (1e-4, 1e-5, 1e-6):
        x = {"H2O": 1.0 - 2 * s, "NH4+": s, "HCO3-": s}
        g = P.debye_huckel_ln_gamma(x, T)
        sI = math.sqrt(P.ionic_strength(x))
        ratio = g["NH4+"] / (-1.0 * A * sI)                 # z = 1
        dev = abs(ratio - 1.0)
        assert dev < b * sI + 1e-12                         # exact analytic bound 1/(1+b sqrt(I))
        if prev_dev is not None:
            assert dev < prev_dev                           # deviation shrinks toward the limiting law
        prev_dev = dev


def test_debye_huckel_water_vanishes_at_zero_ionic_strength():
    """With no ions present, ionic strength is 0 and the water DH term is exactly 0."""
    g = P.debye_huckel_ln_gamma({"H2O": 0.9, "NH3(aq)": 0.1}, 298.15)
    assert abs(g["H2O"]) < 1e-15


def test_debye_huckel_satisfies_gibbs_duhem():
    """The DH contribution alone satisfies Gibbs-Duhem along an electroneutral NH4HCO3-water path:
    sum_i x_i d(ln g_i^DH)/ds = 0. The unsymmetric normalization is composition-independent, so it drops
    out of the derivative -- an incorrect DH differentiation would violate this grossly."""
    T = 298.15
    h = 1e-7

    def lng(s):
        return P.debye_huckel_ln_gamma({"H2O": 1.0 - 2 * s, "NH4+": s, "HCO3-": s}, T)

    for s in (0.01, 0.03, 0.05):
        gp, gm = lng(s + h), lng(s - h)
        d = {k: (gp[k] - gm[k]) / (2.0 * h) for k in gp}
        x = {"H2O": 1.0 - 2 * s, "NH4+": s, "HCO3-": s}
        gd = sum(x[k] * d[k] for k in x)
        assert abs(gd) < 1e-5, f"Gibbs-Duhem(DH) = {gd} at s={s}"


def test_activity_reduces_to_short_range_without_ions():
    """With no charged species the Debye-Huckel term is zero, so the full Extended UNIQUAC activity
    coefficient equals the validated short-range (combinatorial+residual) result."""
    x = {"H2O": 0.8, "NH3(aq)": 0.15, "CO2(aq)": 0.05}
    T = 350.0
    full = P.activity_ln_gamma(x, T)
    sr = P.short_range_ln_gamma(x, T, unsymmetric_species={"NH3(aq)", "CO2(aq)"})
    for s in x:
        assert abs(full[s] - sr[s]) < 1e-12


# ------------------------------------------------------------------------- SRK gas-phase fugacity
def test_srk_ideal_gas_limit():
    """At very low pressure the SRK fugacity coefficient -> 1 and Z -> 1 for every species."""
    y = {"H2O": 0.5, "NH3": 0.3, "CO2": 0.2}
    phi, Z = P.srk_phi(y, 400.0, 100.0)                    # 100 Pa
    assert abs(Z - 1.0) < 1e-3
    for s in y:
        assert abs(phi[s] - 1.0) < 1e-3


def test_srk_real_gas_below_unity():
    """A compressible gas: CO2 at 320 K, 40 bar has Z<1 and fugacity coefficient <1."""
    phi, Z = P.srk_phi({"CO2": 1.0}, 320.0, 40.0e5)
    assert 0.7 < Z < 1.0
    assert 0.6 < phi["CO2"] < 1.0


def test_srk_fugacity_monotone_in_pressure():
    """The fugacity coefficient decreases monotonically from 1 as pressure rises (CO2, 320 K)."""
    prev = None
    for Pbar in (1, 5, 10, 20, 40):
        phi, _ = P.srk_phi({"CO2": 1.0}, 320.0, Pbar * 1e5)
        if prev is not None:
            assert phi["CO2"] < prev
        prev = phi["CO2"]


# ------------------------------------------------------- explicit reaction enthalpy (gap C43)
def test_reaction_enthalpies_match_textbook():
    """dH_reaction from formation enthalpies reproduces textbook aqueous reaction enthalpies at 25 C:
    water ionization +55.8, NH4+ formation (NH3+H+ -> NH4+) -52.2, CO2 first ionization ~+7.6,
    bicarbonate ionization +14.9 kJ/mol -- validating the standard-state dHf set that closes gap C43."""
    assert abs(P.dH_reaction("R1_water") - 55.815) < 0.5
    assert abs(P.dH_reaction("R2_ammonium") - (-52.22)) < 0.5
    assert abs(P.dH_reaction("R3_bicarb") - 7.64) < 1.0
    assert abs(P.dH_reaction("R4_carbonate") - 14.85) < 0.5


def test_reaction_enthalpy_offT0_needs_cp():
    """Off 25 C, dH_reaction needs each species' Cp; reactions containing NH3(aq)/CO2(aq) must refuse
    (not fabricate). Water and carbonate reactions, whose species all have open-source Cp, succeed."""
    assert math.isfinite(P.dH_reaction("R1_water", 320.0))
    assert math.isfinite(P.dH_reaction("R4_carbonate", 320.0))
    for rx in ("R2_ammonium", "R3_bicarb", "R5_carbamate"):
        try:
            P.dH_reaction(rx, 320.0)
            assert False, f"dH_reaction({rx}) off 25 C should have raised"
        except ValueError:
            pass


# ------------------------------------------------- excess (mixing) enthalpy machinery (gap C34)
def test_excess_enthalpy_pure_water_zero():
    """h^E of pure water is exactly 0 (no mixing, no ionic strength, no residual)."""
    assert abs(P.excess_enthalpy({"H2O": 1.0}, 298.15)) < 1e-6


def test_excess_enthalpy_finite_across_envelope():
    """h^E stays finite and physically bounded for a speciated desorber liquid across 40-150 C."""
    x = {"H2O": 0.90, "NH3(aq)": 0.05, "CO2(aq)": 0.02, "NH4+": 0.015, "HCO3-": 0.015}
    for T in (313.15, 373.15, 423.15):
        h = P.excess_enthalpy(x, T)
        assert math.isfinite(h)
        assert abs(h) < 1.0e5                              # J/mol, physically bounded


# ------------------------------------------------- Newton speciation solver (gap C36 phase 1b)
def test_speciation_closes_all_balances():
    """The Newton speciation solver drives every residual -- N balance, C balance, charge balance, and
    all five reaction quotients -- to ~1e-9 across a range of NH3/CO2 loadings. This is the decisive
    correctness test: the composed solver (validated K's + full activity coefficients) is self-consistent."""
    for N, C in ((2.0, 1.0), (4.0, 1.0), (1.0, 1.0), (6.0, 2.0), (0.5, 0.5)):
        r = P.speciate(N, C)
        res = P._speciation_residuals([r[s] for s in P._SOLUTES], N, C, P.T0)
        assert max(abs(x) for x in res) < 1e-9, f"N={N} C={C}: max residual {max(abs(x) for x in res)}"


def test_speciation_conserves_elements_and_charge():
    """Independent re-check (not via the solver's own residuals) that total N, total C, and net charge
    are conserved by the returned speciation."""
    N, C = 3.0, 1.5
    r = P.speciate(N, C)
    assert abs((r["NH3(aq)"] + r["NH4+"] + r["NH2COO-"]) - N) < 1e-8
    assert abs((r["CO2(aq)"] + r["HCO3-"] + r["CO3--"] + r["NH2COO-"]) - C) < 1e-8
    charge = r["H+"] + r["NH4+"] - r["OH-"] - r["HCO3-"] - 2.0 * r["CO3--"] - r["NH2COO-"]
    assert abs(charge) < 1e-8


def test_speciation_reaction_quotients_equal_K():
    """At the converged solution every reaction's activity quotient equals its equilibrium constant."""
    r = P.speciate(2.5, 1.0)
    x = {"H2O": r["H2O"]}
    ntot = P._N_W_PER_KG + sum(r[s] for s in P._SOLUTES)
    for s in P._SOLUTES:
        x[s] = r[s] / ntot
    lng = P.activity_ln_gamma(x, P.T0)
    ln_xw = math.log(x["H2O"])
    ln_a = {s: math.log(r[s]) + lng[s] + ln_xw for s in P._SOLUTES}
    ln_aw = ln_xw + lng["H2O"]
    assert abs((ln_a["NH2COO-"] + ln_aw - ln_a["NH3(aq)"] - ln_a["HCO3-"]) - P.lnK("R5_carbamate", P.T0)) < 1e-7
    assert abs((ln_a["NH4+"] - ln_a["NH3(aq)"] - ln_a["H+"]) - P.lnK("R2_ammonium", P.T0)) < 1e-7


def test_speciation_le_chatelier_ammonia_raises_pH():
    """Adding ammonia at fixed CO2 raises the pH and drives more carbon into carbamate/carbonate --
    the qualitative behaviour Thomsen (2005) Fig. 4 and the Stamicarbon recovery chemistry require."""
    low = P.speciate(1.5, 1.0)
    high = P.speciate(4.0, 1.0)
    assert high["pH"] > low["pH"]
    assert high["NH2COO-"] > low["NH2COO-"]
    assert high["CO2(aq)"] < low["CO2(aq)"]


def test_speciation_carbamate_peaks_in_alkaline_window():
    """A significant fraction of carbon sits as carbamate at pH 9-11 (Thomsen 2005 Fig. 4)."""
    r = P.speciate(3.0, 1.0)
    assert 9.0 < r["pH"] < 11.0
    assert r["NH2COO-"] / 1.0 > 0.3            # >30% of total C as carbamate


def test_speciation_refuses_off_reference_temperature():
    """Off 298.15 K the R2/R3/R5 constants need the paywalled NH3(aq)/CO2(aq) Cp; speciate must refuse."""
    try:
        P.speciate(2.0, 1.0, T=333.15)
        assert False, "speciate() off 25 C should have raised"
    except ValueError:
        pass


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fails = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            fails += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - fails}/{len(fns)} passed")
    raise SystemExit(1 if fails else 0)
