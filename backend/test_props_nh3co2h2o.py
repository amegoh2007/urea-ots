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
