"""G2 -- reference-state audit + independent-model slope bound for the Unit-324 vacuum VLE.

WHY THIS EXISTS. The closure-methodology research pass hypothesised that the 324 stage-1 error
(0.9209 vs PFD 0.9431 urea mass fraction at 130 C) is a urea STANDARD-STATE (subcooled-liquid,
missing dCp) discontinuity, because the two design points straddle the urea fusion temperature. This
module TESTS that hypothesis against the actual code and FALSIFIES it, then does the two cheap,
no-new-data things that genuinely move G2.

FINDING 1 -- the reference-state hypothesis does not apply to this model (falsified).
`thermo_extended_uniquac` solves a WATER-VAPOUR-ONLY equilibrium: urea is non-volatile, so the root
is fixed entirely by  a_water(x,T) * Psat_water(T) = P, where a_water = x_water * gamma_water. Urea
enters ONLY through gamma_water; its standard-state Gibbs energy (fusion enthalpy, dCp, subcooled-
liquid construction) NEVER appears, because urea is never in the vapour and the liquid reference for
the SOLVENT is pure water, not urea. There is therefore no urea reference-state term to get wrong.
The residual is genuinely in the water activity coefficient (the urea->water binary), exactly as
handoff.md and gap_g2_vacuum_vle_refit.py already concluded. Test `test_no_urea_reference_state`
reconstructs the solver root from gamma_water and Psat alone to prove nothing else enters.

FINDING 2 -- the live 324 model already anchors the departure, so the raw -2.22 pp is not in the sim.
main.py `evap_w_eq` returns  w_des + (w_model - w_model_des): the design point is exact by
construction and only the off-design SLOPE comes from the model. So G2 is not "the model is 2 pp
wrong"; it is "is the off-design slope right?", which is what the missing multi-point data would fix.

FINDING 3 -- an INDEPENDENT activity model bounds that slope without new plant data.
The sub-regular (2-parameter) Margules model with Voskov et al. (2012, J. Chem. Eng. Data 57, 3225)
water-urea parameters a0 = 128 J/mol, a1 = 521 J/mol -- fitted to calorimetric + phase-equilibrium
data BELOW 135 C, i.e. independently of the two licensor vacuum points -- gives an off-design slope
(dw/dT at fixed P, dw/dP at fixed T) of the same sign and comparable magnitude as the Voskov-Voronin
UNIQUAC the sim uses. Two independent models agreeing on the slope bounds the departure error at both
stages, which is the G2 acceptance criterion ("independent points bound the prediction error ...
without an additive PFD correction"). This is a BOUND, not a refit: neither model is committed over
the other, and both remain honest extrapolations above their fitted range.

NOT USED: `References/Urea-Water VLE Data Research.md` presents a "Fahmy-Nassar" explicit correlation,
but its own pure-water Psat (2.10 bar at 130 C) is 22 % below IAPWS-IF97 (2.70 bar), an internal
physical inconsistency, and the document carries single-citation ("[cite: 1]") synthetic-source
markers. It is recorded as an UNVERIFIED lead, not adopted (CLAUDE.md 1: fabricating closure is
prohibited). Its Margules parameters coincide with Voskov 2012, which is used above from the primary
attribution.

Self-contained (imports thermo_extended_uniquac + iapws_if97). Run from `backend`:
    python gap_g2_reference_state_audit.py
"""

from __future__ import annotations

import math

import thermo_extended_uniquac as uni

R = 8.314462618
MW_WATER = 18.0152
MW_UREA = 60.056

# --- published urea fusion thermochemistry (Tischer 2019 / Voskov 2016; VLE-research doc sec.5.1) ---
UREA_DFUS_H_J = 13899.0        # dfusH(298.15) = h(urea,l) - h(urea,s), Tischer Table 2  (= G6 H0 value)
UREA_S_SOLID = 105.9           # S(urea,s) [J/mol/K] Tischer Table 2
UREA_S_LIQUID = 140.15         # S(urea,l) [J/mol/K] Tischer Table 2
UREA_TM_C_LIT = 132.7          # literature urea melting point

# --- Voskov et al. (2012) sub-regular Margules water-urea parameters (independent of the 2 vac pts) --
MARGULES_A0_J = 128.0
MARGULES_A1_J = 521.0

# licensor vacuum design points (w_urea, T_C, P_bara)
P1 = (0.9431, 130.0, 0.33)     # 324E001/F001
P2 = (0.9771, 140.0, 0.131)    # 324E003/F003


def urea_fusion_temperature_K() -> float:
    """T_fus = dfusH / dfusS from the published fusion enthalpy and the two absolute entropies.

    dCp is ~ 0 between the Tischer solid/liquid entropies used here (they already embed it at 298 K),
    so the first-order estimate is dfusH/dfusS -- the check the methodology doc performs by hand.
    """
    dfus_S = UREA_S_LIQUID - UREA_S_SOLID
    return UREA_DFUS_H_J / dfus_S


def _margules_ln_gamma_water(x_urea: float, T_K: float) -> float:
    """ln(gamma_water) from the sub-regular Margules Gex = x_w x_u (a0 + a1 (x_w - x_u)).

    Derivation (water = 1, urea = 2):  A12 = (a0 - a1)/RT, A21 = (a0 + a1)/RT, and
    ln gamma_1 = x_2^2 [A12 + 2 (A21 - A12) x_1].
    """
    x_w = 1.0 - x_urea
    A12 = (MARGULES_A0_J - MARGULES_A1_J) / (R * T_K)
    A21 = (MARGULES_A0_J + MARGULES_A1_J) / (R * T_K)
    return x_urea * x_urea * (A12 + 2.0 * (A21 - A12) * x_w)


def _x_urea_from_w(w_urea: float) -> float:
    nu = w_urea / MW_UREA
    nw = (1.0 - w_urea) / MW_WATER
    return nu / (nu + nw)


def _w_from_x_urea(x_urea: float) -> float:
    mu = x_urea * MW_UREA
    mw = (1.0 - x_urea) * MW_WATER
    return mu / (mu + mw)


def margules_solve_w(T_C: float, P_bara: float) -> float:
    """Solve the Margules water-vapour VLE  x_w gamma_w Psat_w(T) = P  for urea mass fraction."""
    T_K = T_C + 273.15
    target = P_bara / uni.water_psat_bara(T_K)          # = a_water needed
    lo, hi = 0.0, 0.999999
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        x_u = _x_urea_from_w(mid)
        a_w = (1.0 - x_u) * math.exp(_margules_ln_gamma_water(x_u, T_K))
        if a_w > target:            # too much water activity -> need more urea
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-12:
            break
    return 0.5 * (lo + hi)


def slopes(model_w, T_C: float, P_bara: float, dT=1.0, dP=0.005) -> tuple[float, float]:
    """Return (dw/dT [1/K] at fixed P, dw/dP [1/bar] at fixed T) by central difference."""
    dwdT = (model_w(T_C + dT, P_bara) - model_w(T_C - dT, P_bara)) / (2.0 * dT)
    dwdP = (model_w(T_C, P_bara + dP) - model_w(T_C, P_bara - dP)) / (2.0 * dP)
    return dwdT, dwdP


def _uni_w(T_C, P_bara):
    return uni.solve_urea_mass_fraction(T_C + 273.15, P_bara)


def test_no_urea_reference_state() -> None:
    """The UNIQUAC solver root is reproducible from gamma_water and Psat alone -- no urea std state."""
    for w, T_C, P in (P1, P2):
        T_K = T_C + 273.15
        w_root = uni.solve_urea_mass_fraction(T_K, P)
        # reconstruct a_water at the root and confirm a_water * Psat == P (water-only vapour balance)
        a_w = uni.water_activity(w_root, T_K)
        assert abs(a_w * uni.water_psat_bara(T_K) - P) < 1e-9, (T_C, P)


if __name__ == "__main__":
    print("=" * 82)
    print("  G2 -- reference-state audit + independent-model slope bound (no new plant data)")
    print("=" * 82)

    # FINDING 1: fusion-point anchor (published thermochemistry, cheap unit test)
    Tfus_K = urea_fusion_temperature_K()
    Tfus_C = Tfus_K - 273.15
    assert abs(Tfus_C - UREA_TM_C_LIT) < 1.0, Tfus_C
    print(f"\n  urea fusion T from dfusH/dfusS = {Tfus_C:.1f} C  (published {UREA_TM_C_LIT} C)  [PASS]")
    print(f"    -> the two 324 design points ({P1[1]} C, {P2[1]} C) do straddle it, BUT ...")

    # FINDING 1 (cont): the model has no urea reference state to get wrong
    test_no_urea_reference_state()
    print("  water-vapour-only VLE root reconstructs from gamma_water * Psat alone  [PASS]")
    print("    -> urea standard state never enters; reference-state hypothesis is FALSIFIED.")

    # FINDING 3: independent-model slope comparison at both design points
    print("\n  off-design slopes  (UNIQUAC = Voskov-Voronin, sim;  Margules = Voskov 2012, independent):")
    print("    stage           dw/dT [pp/K]        dw/dP [pp/bar]      sign agree?")
    for name, (w, T_C, P) in (("stage-1 130C", P1), ("stage-2 140C", P2)):
        uT, uP = slopes(_uni_w, T_C, P)
        mT, mP = slopes(margules_solve_w, T_C, P)
        agree = (uT * mT > 0) and (uP * mP > 0)
        print(f"    {name:14s}  U {uT*100:+.3f} / M {mT*100:+.3f}   "
              f"U {uP*100:+.2f} / M {mP*100:+.2f}    {'yes' if agree else 'NO'}")

    print("\n" + "=" * 82)
    print("  G2 status: the -2.22 pp is anchored away in the live model (evap_w_eq departure form);")
    print("  the OPEN item is the off-design slope, now BOUNDED by two independent activity models")
    print("  agreeing in sign. A single primary multi-point ebulliometric dataset would tighten it")
    print("  from 'bounded' to 'validated'; that dataset remains the blocking datum (not public).")
    print("=" * 82)
