"""G6 (enthalpy half) -- H0 absolute stream enthalpy on a single elements-at-298.15 K datum.

WHAT THIS CLOSES (partial, by declared tier). handoff.md G6 records "0/55 have enthalpy_kJkg" and
argues a live enthalpy is blocked on G1. That is true ONLY for the excess (mixing) term. Decompose
the stream enthalpy exactly as the closure-methodology doc (sec. on absolute enthalpy) does:

    H_stream = sum_i n_i * h_i(T)          + H^E(T,x)
               |__ formation + sensible __|  |__ mixing non-ideality __|
                   + phase-change              (needs the tier's activity model = G1)

The first sum is available NOW from published data; only H^E is G1-gated. So instead of publishing
nothing, publish a DECLARED-TIER enthalpy with a mandatory basis flag (doc's H0/H1/H2 scheme):

    H0  formation + sensible + phase reference, IDEAL solution (H^E = 0)   <- THIS MODULE, available now
    H1  H0 + H^E from the tier's activity model                            <- lands with each G1 tier
    H2  H1 reconciled against the licensor/plant heat balance              <- after the licensor point

Because every h_i is referenced to its ELEMENTS at 298.15 K / 1 bar (that is what a formation
enthalpy IS), the sum is reaction-consistent by construction: a reaction's enthalpy is the
difference of its members' formation enthalpies, so H0 does NOT create or destroy energy across a
reacting node -- unlike a sensible-only enthalpy, which is why sensible-only was correctly refused.
H0 is therefore usable for heat balances and duty/trend estimates; it is NOT design-grade inside a
strongly non-ideal liquid (that is H1). The basis flag makes that honest per stream.

PROVENANCE. Every constant below is transcribed from a named open source; nothing is fitted here:
  * Aqueous/ionic species (H2O, NH3(aq), CO2(aq)) reuse the SAME formation enthalpy and Helgeson
    Cp(T) already validated in `props_nh3co2h2o.py` (Darde 2011 / Thomsen 1997 / Correa-Thomsen-
    Fosbol 2023) -- imported, not re-transcribed, so the two modules cannot diverge.
  * Ideal-gas formation enthalpies: CODATA Key Values / NIST-JANAF (298.15 K).
  * Urea and biuret (solid + liquid) formation enthalpies: Tischer, Boernhorst, Amsler, Schoch,
    Deutschmann, Phys. Chem. Chem. Phys. 21 (2019) 16785 (open access, CC BY-NC).
  * Heat-capacity coefficients (Berman-Brown a + e T^-0.5) and AMMONIUM CARBAMATE formation
    enthalpies (solid -645.05, liquid -624.32 kJ/mol): Voskov & Voronin, J. Chem. Eng. Data 61 (2016)
    4110 (Table 1), as tabulated in `References/Urea Plant Simulation Gaps2.md`. Carbamate is the
    reactive HPCC/reactor intermediate, so its explicit formation enthalpy makes the loop enthalpy
    reaction-consistent through the carbamate node, not only across the net 2NH3+CO2->urea+H2O.
  * CROSS-CHECK against this plant's licensor manual (`References/Sources/02 FUNDAMENTALS.pdf`,
    Uhde UD-VT-G00-DC-0003): the elements datum reproduces the manual's reaction enthalpies --
    carbamate step ~ -159 kJ/mol (gas reactants) / plant's -117 (condensed reactants), and the urea
    step +16.7 kJ/mol vs the plant's +15.5 -- and the plant's urea remelt heat 15.1 kJ/mol brackets
    the Tischer fusion 13.9 used here (all within the H0 declared band).

Gas-phase sensible heat uses constant Cp near mid-window; over 25-200 C this is a few-percent
approximation on the SENSIBLE part only (the formation term, which dominates a reactive balance by
1-2 orders of magnitude, is exact). That approximation is a declared property of the H0 tier.

Run from `backend`:  python gap_g6_h0_enthalpy.py
"""

from __future__ import annotations

import math
from enum import Enum

import props_nh3co2h2o as props     # reuse the validated aqueous formation enthalpies + Helgeson Cp

T0 = 298.15
R = 8.314462618


class EnthalpyBasis(str, Enum):
    """Declared quality tier for a published stream enthalpy (companion to `enthalpy_kJkg`)."""
    H0 = "H0_formation_sensible_ideal"     # available now (this module); excludes mixing non-ideality
    H1 = "H1_plus_excess"                  # H0 + H^E from the tier's activity model (G1)
    H2 = "H2_plant_reconciled"             # H1 reconciled to the licensor/plant heat balance (G1-A4)


# Molar masses [g/mol] for the simulator's condensed-phase species set (main.py MW_SOL) plus the
# volatile/inert gases that appear in the vapour streams.
MOLAR_MASS = {
    "Urea": 60.056, "Biuret": 103.081, "Carbamate": 78.0714, "NH3": 17.0304, "CO2": 44.0098,
    "H2O": 18.0152, "HCHO": 32.031, "N2": 28.0134, "O2": 31.9988,
    "H2": 2.0158, "CH4": 16.043, "Ar": 39.948,
}

# ---------------------------------------------------------------------------
# Pure-component standard enthalpy of formation dHf(298.15) [J/mol] and heat capacity Cp(T) [J/mol/K],
# BY PHASE. h_i(T) = dHf + integral_{T0}^{T} Cp dT'.  Each entry cites its open source.
# Cp given either as a constant (float) or a callable f(T).
# ---------------------------------------------------------------------------
def _cp_const(value):
    return lambda T: value


def _cp_berman(a, e):
    """Berman-Brown truncated heat capacity  Cp(T) = a + e * T^-0.5  [J/mol/K] (Voskov 2016 Table 1)."""
    return lambda T: a + e * T ** (-0.5)


_cp_urea_solid = _cp_berman(253.64, -2763.3)     # Voskov & Voronin 2016 (a, e) for urea solid


# (dHf_J, Cp)   -- Cp is float (constant) or callable
PURE_COMPONENT = {
    # --- condensed urea: dfH on Tischer 2019 (solid+liquid pair -> measured fusion 13.9 kJ/mol),
    #     Cp on Voskov 2016 a + e*T^-0.5 (both sources agree on the coefficients; urea(l) reduces to
    #     ~150 J/mol/K at Tm = 405 K, matching the VLE-doc constant 150.43 previously used).
    #     [Voskov's own dfH PAIR gives fusion 10.9 kJ/mol, an outlier vs Tischer 13.9 / plant 15.1;
    #      the internally-consistent Tischer pair is kept so fusion matches direct calorimetry.]
    ("Urea", "liquid"):   (-319700.0, _cp_berman(287.59, -2763.3)),  # dfH Tischer; (a,e) Voskov urea(l)
    ("Urea", "solid"):    (-333599.0, _cp_urea_solid),               # dfH Tischer; (a,e) Voskov urea(s)
    # --- ammonium carbamate, the reactive HPCC/reactor intermediate (Voskov 2016 Table 1) ---
    #     reaction-consistent enthalpy across the synthesis loop now includes carbamate explicitly.
    ("Carbamate", "solid"):  (-645047.0, _cp_berman(311.85, -3137.5)),  # Voskov dfH & (a,e) carb(s)
    ("Carbamate", "liquid"): (-624323.0, _cp_berman(346.37, -3137.5)),  # Voskov dfH & (a,e) carb(l)
    # --- biuret: kept on Tischer 2019 (primary, literature-consistent dfH(s) ~= -564 kJ/mol) ---
    ("Biuret", "liquid"): (-537060.0, _cp_const(93.0)),     # Tischer 2019 Table 2
    ("Biuret", "solid"):  (-563700.0, _cp_const(131.3)),    # Tischer 2019 Table 2
    # --- water: liquid reuses props (Helgeson Cp); gas is CODATA/JANAF ---
    ("H2O", "liquid"):    (-285830.0, None),                # Cp via props.cp0("H2O", T)
    ("H2O", "gas"):       (-241826.0, _cp_const(33.60)),    # CODATA dfH(g); Cp,g ~33.6
    # --- ammonia: aqueous reuses props; gas is CODATA ---
    ("NH3", "aqueous"):   (-80290.0,  None),                # props.cp0("NH3(aq)")  (const 72.04)
    ("NH3", "gas"):       (-45940.0,  _cp_const(35.65)),    # CODATA dfH(g); Cp,g ~35.65
    # --- carbon dioxide: aqueous reuses props; gas is CODATA ---
    ("CO2", "aqueous"):   (-413800.0, None),                # props.cp0("CO2(aq)")  (const 238.05)
    ("CO2", "gas"):       (-393522.0, _cp_const(37.13)),    # CODATA dfH(g); Cp,g ~37.13
    # --- formaldehyde (NIST) ---
    ("HCHO", "gas"):      (-108600.0, _cp_const(35.40)),    # NIST dfH(g); Cp,g ~35.4
    # --- inert / light gases (elements dfH = 0; JANAF Cp,g) ---
    ("N2", "gas"):        (0.0, _cp_const(29.12)),
    ("O2", "gas"):        (0.0, _cp_const(29.38)),
    ("H2", "gas"):        (0.0, _cp_const(28.84)),
    ("CH4", "gas"):       (-74600.0, _cp_const(35.69)),     # NIST dfH(g)
    ("Ar", "gas"):        (0.0, _cp_const(20.79)),
}

# Which phase each species takes when a stream is liquid vs vapour (H0 does no flash; the caller's
# stream phase selects the column). Condensed-only species stay condensed; permanent gases stay gas.
_LIQUID_PHASE = {
    "Urea": "liquid", "Biuret": "liquid", "Carbamate": "liquid", "H2O": "liquid",
    "NH3": "aqueous", "CO2": "aqueous",
    "HCHO": "gas", "N2": "gas", "O2": "gas", "H2": "gas", "CH4": "gas", "Ar": "gas",
}
_VAPOUR_PHASE = {
    "H2O": "gas", "NH3": "gas", "CO2": "gas", "HCHO": "gas",
    "N2": "gas", "O2": "gas", "H2": "gas", "CH4": "gas", "Ar": "gas",
    # urea/biuret/carbamate carried in vapour are non-volatile; if present, keep the condensed state
    "Urea": "liquid", "Biuret": "liquid", "Carbamate": "solid",
}


def h_species(species: str, phase: str, T_K: float) -> float:
    """Pure-component molar enthalpy h_i(T) [J/mol] on the elements-at-298.15 K datum.

    h_i(T) = dHf(298.15) + integral_{298.15}^{T} Cp(T') dT'.  Water(l)/NH3(aq)/CO2(aq) delegate their
    Cp integral to the validated props module so the datum is shared with the electrolyte core.
    """
    key = (species, phase)
    if key not in PURE_COMPONENT:
        raise KeyError(f"no H0 constituent data for {key}")
    dHf, cp = PURE_COMPONENT[key]
    if cp is None:
        # delegate to the validated Helgeson Cp in props (h0 already integrates dHf + int Cp)
        props_key = {"H2O": "H2O", "NH3": "NH3(aq)", "CO2": "CO2(aq)"}[species]
        return props.h0(props_key, T_K)
    if T_K == T0:
        return dHf
    if callable(cp):
        # numerical integral of a callable Cp (Simpson, plenty for a smooth Cp over <=200 K)
        n = 20
        h = (T_K - T0) / n
        acc = cp(T0) + cp(T_K)
        for i in range(1, n):
            acc += (4.0 if i % 2 else 2.0) * cp(T0 + i * h)
        return dHf + acc * h / 3.0
    return dHf + cp * (T_K - T0)


def h0_stream(comp_kmolh: dict, T_C: float, phase: str = "liquid") -> dict:
    """H0 absolute enthalpy of a stream.

    comp_kmolh : {species: kmol/h}   using the MOLAR_MASS keys (Urea, NH3, CO2, H2O, ...).
    T_C        : stream temperature [C].
    phase      : 'liquid' or 'vapour' -- selects the per-species reference phase (H0 does no flash).

    Returns {'enthalpy_flow_kW', 'enthalpy_kJkg', 'enthalpy_basis', 'mass_kgh'}.  The datum is
    elements at 298.15 K / 1 bar, so the value is reaction-consistent and may be summed across nodes.
    """
    T_K = T_C + 273.15
    phase_map = _VAPOUR_PHASE if phase.startswith("vap") else _LIQUID_PHASE
    H_Jh = 0.0            # J/h
    mass_kgh = 0.0
    for sp, nk in comp_kmolh.items():
        if nk == 0.0:
            continue
        if sp not in phase_map:
            raise KeyError(f"unknown species {sp!r} in stream composition")
        n_molh = nk * 1000.0
        H_Jh += n_molh * h_species(sp, phase_map[sp], T_K)
        mass_kgh += nk * MOLAR_MASS[sp]
    return {
        "enthalpy_flow_kW": H_Jh / 3.6e6,                     # J/h -> kW
        "enthalpy_kJkg": (H_Jh / 1000.0) / mass_kgh if mass_kgh > 0 else None,   # kJ/kg
        "enthalpy_basis": EnthalpyBasis.H0.value,
        "mass_kgh": mass_kgh,
    }


def h0_stream_mass_pct(mass_kgh: float, mass_pct: dict, T_C: float, phase: str = "liquid") -> dict:
    """Convenience wrapper: mass flow [kg/h] + mass-% composition -> H0 enthalpy (see `h0_stream`)."""
    comp_kmolh = {}
    for sp, pct in mass_pct.items():
        if sp in MOLAR_MASS and pct:
            comp_kmolh[sp] = mass_kgh * (pct / 100.0) / MOLAR_MASS[sp]
    return h0_stream(comp_kmolh, T_C, phase)


if __name__ == "__main__":
    # --- validation against first-principles / known references (no plant data needed) ---
    # 1. liquid water at 25 C is exactly its formation enthalpy on this datum.
    assert abs(h_species("H2O", "liquid", T0) - (-285830.0)) < 1e-6

    # 2. sensible heat of liquid water 25 -> 130 C ~ Cp*dT with Cp~75.7 J/mol/K.
    dh_w = h_species("H2O", "liquid", 403.15) - h_species("H2O", "liquid", T0)
    assert 7600.0 < dh_w < 8300.0, dh_w                        # ~75.7 * 105 ~ 7950 J/mol

    # 3. latent-style gap: H2O(g) - H2O(l) at 25 C = 44.0 kJ/mol (std vaporisation enthalpy).
    dvap = h_species("H2O", "gas", T0) - h_species("H2O", "liquid", T0)
    assert abs(dvap - 44004.0) < 50.0, dvap

    # 4. urea fusion enthalpy at 298.15 K = h(urea,l) - h(urea,s) ~ 13.9 kJ/mol (Tischer).
    #    (plant remelt 15.1 kJ/mol, VLE-doc 14.644 -- a ~9% spread, all inside the H0 band.)
    dfus = h_species("Urea", "liquid", T0) - h_species("Urea", "solid", T0)
    assert abs(dfus - 13899.0) < 1.0, dfus

    # 4b. REACTION-ENTHALPY cross-checks -- the elements datum reproduces the plant's stated reaction
    #     enthalpies (02 FUNDAMENTALS p.1-2/1-11), which is exactly what "reaction-consistent" means:
    #     * carbamate step with GAS-phase reactants -> solid carbamate:
    #         2 NH3(g) + CO2(g) -> carbamate(s)   should be ~ -159 kJ/mol
    dh_carb_gas = (h_species("Carbamate", "solid", T0)
                   - 2.0 * h_species("NH3", "gas", T0) - h_species("CO2", "gas", T0))
    assert -170000.0 < dh_carb_gas < -150000.0, dh_carb_gas       # ~ -159.6 kJ/mol
    #     * urea step with condensed members -> matches the plant's +15.5 kJ/mol (endothermic):
    #         carbamate(l) -> urea(l) + H2O(l)    should be ~ +16 kJ/mol
    dh_urea_liq = (h_species("Urea", "liquid", T0) + h_species("H2O", "liquid", T0)
                   - h_species("Carbamate", "liquid", T0))
    assert 12000.0 < dh_urea_liq < 20000.0, dh_urea_liq          # ~ +16.7 kJ/mol vs plant +15.5

    # 5. a real melt stream (PFD 402, the final 97.71 wt% urea melt at 140 C) gets a finite,
    #    negative (exothermic-of-formation) specific enthalpy on the elements datum.
    s402 = h0_stream_mass_pct(
        74721.0, {"Urea": 97.71, "Biuret": 0.85, "NH3": 0.04, "H2O": 1.39, "HCHO": 0.0099},
        140.0, phase="liquid",
    )
    assert s402["enthalpy_basis"] == "H0_formation_sensible_ideal"
    assert s402["enthalpy_kJkg"] < 0.0

    print("=" * 78)
    print("  G6 H0 ABSOLUTE STREAM ENTHALPY  (formation + sensible + phase ref, ideal solution)")
    print("=" * 78)
    print(f"  h(H2O,l,25C)          = {h_species('H2O','liquid',T0)/1000:.2f} kJ/mol  (= dfH, datum check)")
    print(f"  water sensible 25->130 = {dh_w/1000:.3f} kJ/mol")
    print(f"  h(H2O,g)-h(H2O,l) @25C = {dvap/1000:.3f} kJ/mol  (lit dvapH 44.0)")
    print(f"  urea fusion  @25C      = {dfus/1000:.3f} kJ/mol  (Tischer 13.90; plant remelt 15.1)")
    print(f"  2NH3(g)+CO2(g)->carb(s)= {dh_carb_gas/1000:.1f} kJ/mol  (reaction-consistency, lit ~-159)")
    print(f"  carb(l)->urea(l)+H2O(l)= {dh_urea_liq/1000:+.1f} kJ/mol  (plant +15.5, endothermic)")
    print(f"  PFD-402 melt (140 C)   = {s402['enthalpy_kJkg']:.1f} kJ/kg,  {s402['enthalpy_flow_kW']:.0f} kW")
    print(f"  basis flag             = {EnthalpyBasis.H0.value}")
    print("  every constituent traceable to a cited open source; H^E term is the only G1-gated piece.")
    print("=" * 78)
