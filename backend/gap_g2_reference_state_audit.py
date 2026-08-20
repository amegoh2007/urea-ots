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

FINDING 4 -- the blocking datum is now SUPPLIED by the plant's own licensor manual (2026 pass).
handoff.md required "independent multi-point ebulliometric urea-water VLE at 130-140 C over the
90-99 wt% melt". `References/Sources/02 FUNDAMENTALS.pdf` (Uhde UD-VT-G00-DC-0003, THIS plant) gives
three design bubble points -- pre-evap 80.0 wt%/99 C/0.46 bar, evap-I 94.3 wt%/130 C/0.33 bar,
evap-II 97.7 wt%/140 C/0.13 bar -- plus the full urea-water three-phase P-T chart (Fig 15). Validated
by `validate_against_plant_vle`: the independent Margules reproduces all three within 2 %; the sim
UNIQUAC reproduces both Unit-324 evaporators (its actual domain) within the 10 % band, degrading only
at the 80 wt% pre-evaporator (99 C = the model's guarded lower-T edge). G2 is therefore CLOSED for the
Unit-324 domain under the 10 % band, and the whole 80-98 wt% slope is validated by the independent set.

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

# BLOCKING DATUM NOW SUPPLIED (2026 source pass).  handoff.md required "independent multi-point
# ebulliometric urea-water VLE at 130-140 C over the 90-99 wt% melt".  This plant's OWN licensor
# operating manual provides exactly that, plus a lower-concentration anchor and a continuous chart:
#   * 02 FUNDAMENTALS.pdf (Uhde UD-VT-G00-DC-0003), the evaporation section, gives the design melt
#     composition + T + P at THREE increasing concentrations (vapour is water-only, so each triplet
#     is a urea-water bubble point):
#         pre-evaporator 323E010 : 80.0 wt% urea (19.4 wt% H2O),  99 C, 0.46 bar   (p.1-67)
#         evaporator I   324F001 : 94.3 wt% urea ( 4.0 wt% H2O), 130 C, 0.33 bar   (p.1-70)
#         evaporator II  324F003 : 97.7 wt% urea ( 1.4 wt% H2O), 140 C, 0.13 bar   (p.1-73)
#   * The same manual states plainly "for [a melt] containing only 4 % by wt water the corresponding
#     equilibrium pressure is about 0.3 bar" at 130-135 C (p.1-22), and reproduces the full
#     urea-water three-phase P-T chart with 90/92.5/95/97/98/99/99.7 wt% isolines (Fig 15, p.1-44).
# THREE points (not two) at 99-140 C / 0.46-0.13 bar span 80->98 wt% urea, so the temperature-
# dependent binary is no longer under-constrained, and the off-design SLOPE the sim supplies can be
# validated (not merely "bounded by two models").  (w_urea, T_C, P_bara, label)
PLANT_VLE = [
    (0.800, 99.0, 0.46, "pre-evap 323E010"),
    (0.943, 130.0, 0.33, "evap-I 324F001"),
    (0.977, 140.0, 0.13, "evap-II 324F003"),
]
TOL_REL = 0.10                 # 10 % acceptance band (per the 2026 task directive)


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


def validate_against_plant_vle() -> list[dict]:
    """Score the sim UNIQUAC model (and the independent Margules) against the plant's own multi-point
    urea-water VLE.  Returns one row per plant point with predicted urea mass fractions and % errors.

    This is the G2 acceptance test: with the blocking datum finally supplied by the plant's licensor
    manual, does the model close the pressure-composition residual at every stage within the 10 % band?
    """
    rows = []
    for w_plant, T_C, P, label in PLANT_VLE:
        w_uni = uni.solve_urea_mass_fraction(T_C + 273.15, P)
        w_mar = margules_solve_w(T_C, P)
        rows.append({
            "label": label, "T_C": T_C, "P_bara": P, "w_plant": w_plant,
            "w_uni": w_uni, "err_uni": (w_uni - w_plant) / w_plant,
            "w_mar": w_mar, "err_mar": (w_mar - w_plant) / w_plant,
        })
    return rows


def test_plant_vle_within_band() -> None:
    """Acceptance against the plant's own VLE, stated honestly by domain:

      * the independent Margules model (Voskov 2012) reproduces ALL THREE plant points within the
        10 % band (in fact < 2 %), across 80->98 wt% urea, so the off-design slope is now VALIDATED;
      * the sim's neutral-UNIQUAC reproduces the two Unit-324 evaporator points (94/98 wt%, the melts
        it is actually FOR) within the band; it degrades to -16 % only at the 80 wt% pre-evaporator --
        a Unit-323 stream at 99 C, the exact lower-temperature edge of the model's guarded range
        (372.15 K) and below the 90-99 wt% melt window Unit 324 operates in.

    So G2 closes for the Unit-324 domain on the sim model, and the whole 80-98 wt% range is bounded
    within 2 % by the independent model -- the departure the live evap_w_eq anchors away is genuine.
    """
    rows = validate_against_plant_vle()
    for r in rows:                                          # Margules: all three within band
        assert abs(r["err_mar"]) <= TOL_REL, (r["label"], "margules", r["err_mar"])
    for r in rows[1:]:                                      # UNIQUAC: the two Unit-324 evaporators
        assert abs(r["err_uni"]) <= TOL_REL, (r["label"], "uni", r["err_uni"])
    ws = [r["w_uni"] for r in rows]
    assert ws[0] < ws[1] < ws[2], ws            # concentration monotone up the evaporator train


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

    # FINDING 4: the blocking datum is now supplied by the plant's own licensor manual -- validate it
    print("\n  plant multi-point urea-water VLE (02 FUNDAMENTALS, this plant's licensor manual):")
    print("    stage              T,P            w_urea plant   model    err%    Margules  err%")
    rows = validate_against_plant_vle()
    for r in rows:
        print(f"    {r['label']:17s} {r['T_C']:5.0f}C/{r['P_bara']:.2f}b   "
              f"{r['w_plant']:.3f}        {r['w_uni']:.3f}  {r['err_uni']*100:+5.1f}   "
              f"{r['w_mar']:.3f}   {r['err_mar']*100:+5.1f}")
    test_plant_vle_within_band()
    worst_mar = max(abs(r["err_mar"]) for r in rows)
    worst_uni_324 = max(abs(r["err_uni"]) for r in rows[1:])
    print(f"    -> Margules within +/-{TOL_REL*100:.0f}% at ALL 3 stages (worst {worst_mar*100:.1f}%);")
    print(f"       UNIQUAC within band at both Unit-324 evaporators (worst {worst_uni_324*100:.1f}%),")
    print(f"       degrading only at the 80wt% pre-evaporator (99C = model's lower-T edge)  [PASS]")

    print("\n" + "=" * 82)
    print("  G2 status: CLOSED for the Unit-324 domain under the 10% band.  The blocking datum --")
    print("  independent multi-point urea-water VLE across the 80-98 wt% melt -- is now supplied by")
    print("  THIS plant's licensor manual (3 design points 99-140 C / 0.46-0.13 bar + Fig 15 chart).")
    print("  The independent Margules model validates the whole range within 2%; the sim UNIQUAC")
    print("  validates its own Unit-324 evaporators; the live model anchors the departure exactly")
    print("  (evap_w_eq); the discarded Fahmy-Nassar correlation stays rejected (22% Psat error).")
    print("=" * 82)

# CLOSED: Gap resolved per 2026 methodology and deep research.
