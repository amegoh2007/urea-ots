# Open Simulation Gaps Only

Updated: 2026-07-31 (source pass)
Strict source: `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`
Plant licensor manual (this plant): `References/Sources/02 FUNDAMENTALS.pdf` (Uhde UD-VT-G00-DC-0003)
Validated reactor kinetics: `References/Sources/Aspen urea.pdf` (AspenTech Stamicarbon loop, V7 2008)
CSTR-in-series corroboration: `References/Sources/Modeling the synthesis section...pdf` (Hamidipour 2005)
Audit: `FULL_SIMULATION_EXTENDED_UNIQUAC_AUDIT_2026-07-29.md`
Research passes applied: `References/Gaps solution.md`, `References/Urea Plant Simulation Gaps2.md`

Closed items are intentionally deleted from this file. Each item below is still open because the
remaining equation or datum cannot be supplied honestly by the current repository evidence. Each
carries the **Method** to apply and the exact **Blocking datum** that must arrive before that method can
close it. Fabricating closure is prohibited (CLAUDE.md 1). Under the 2026 source-pass directive, model
outputs within **10 %** of the plant design values are accepted (the strict-PFD-exact rule is relaxed).

Standalone, self-validated closure/analysis modules (the "validate on its own before wiring" pattern as
`props_nh3co2h2o.py`); each runs in <1 s and is cited line-by-line. What they closed is deleted below;
what they left open is sharpened. Modules: `gap_g6_static_catalogue.py`, `gap_g6_h0_enthalpy.py`,
`gap_g9a_ejector_envelope.py`, `gap_g2_reference_state_audit.py`, `gap_g4_conservation_harness.py`,
`gap_g4_reactor_kinetics.py` (new: the cited two-reaction Stamicarbon reactor kinetics).

## G1 - Runtime reactive thermodynamics is not plant-wide Extended UNIQUAC

**Evidence:** `backend/props_nh3co2h2o.py` implements the Thomsen/Darde NH3-CO2-H2O Extended-UNIQUAC/
SRK/speciation core (validated, off-25 C capable), but the HPCC, reactor, stripper, scrubber, LP
absorber and Unit-328 columns still use calibrated splits in `backend/main.py`, and urea is absent
from the reactive runtime phase set.

**Method -- two viable routes, both now partly de-risked by the 2026 source pass:**
  1. TIERED activity model (`Gaps solution.md` re-scope): Tier A (HP loop) molecular UNIQUAC + Voronin
     virial EoS (Voskov & Voronin, JCED 61 (2016) 4110 -- the neutral H2O/urea limit is already coded in
     `thermo_extended_uniquac.py` and now validated to <2 % against the plant's own evaporation VLE, see
     former G2); Tier B (LP/absorbers) the existing Extended UNIQUAC; Tier C (324 melt) delivered.
  2. SINGLE cubic EoS (the AspenTech route, `Aspen urea.pdf`): SR-POLAR (Soave + Peneloux-Rauzy volume +
     Schwartzentruber-Renon polar term) across the WHOLE loop, treating the system as molecular
     (ionization small at 160-200 C / low water) with a USURA-style kinetic block. This is the validated
     industrial standard and sidesteps the missing mixed-solvent dielectric that stalls the electrolyte
     Debye-Huckel term. The reaction kinetics for this route are now in hand (see G4 / Aspen k2).
  Interface either way = apparent-composition handover on the common elements-at-298.15 K enthalpy datum
  (`gap_g6_h0_enthalpy.py`, now including carbamate) with domain-flag propagation.

**Blocking datum:** the urea/ion reactive parameters (Voskov-Voronin set is OPEN and can seed the fit;
SR-POLAR binaries are fittable to the plant VLE) plus the licensor 100%-load HP design point
(user-supplied) for plant reconciliation only. Thermodynamic validation can use Voskov & Voronin's
conversion/bubble-point grids, the Aspen Gorlovskii-Kucheryavyi equilibrium map, and this plant's manual
(reactor CO2 efficiency 59 %, outlet 183 C, N/C 2.95). Full runtime integration into each HP/LP unit in
flow order is multi-week scope; it is the largest remaining build.

**Acceptance:** every process-mixture phase-equilibrium/enthalpy call reports model, domain status,
fugacity/energy residual, and closes MESH without an empirical split override.

## G4 - HP synthesis loop has signed/pinned surrogate flows

**Evidence:** 322R001 applies `REACT_TEAR_DES`, including signed component corrections, to reconcile
its reduced conversion surrogate. 322E002 uses an anchored flash rather than the reactive Extended-
UNIQUAC package. 322E003 scrubber discharges remain pinned; scalar HPCC/scrubber inventories are not
paired with full component holdups.

**Kinetic core NO LONGER BLOCKED** (`gap_g4_reactor_kinetics.py`). The urea rate constant that was the
blocking datum is now cited from the validated AspenTech Stamicarbon loop model (Aspen urea.pdf sec.5):
the two-reaction scheme `2NH3+CO2<=>CARB` (fast, equilibrium) and `CARB<=>UREA+H2O` (slow) with
`Rate2 = k2{x_CARB - x_UREA x_H2O/K2}`, `k2 = 15e8 exp(-100e6/RT)/V_L` (Arrhenius A=1.5e9, Ea=100
kJ/mol). The standalone module implements the CSTR-in-series / marched-PFR idealisation (11 sieve trays
per this plant's manual; 8 stages Aspen; 10 CSTRs Hamidipour 2005) and VALIDATES against the licensor
data within the 10 % band: equilibrium CO2->urea = 59.0 % at the design point (plant CO2 efficiency
~59 %, Aspen Fig 2 ~57-60 %); conversion RISES with NH3/CO2 and FALLS with H2O/CO2 quantitatively
tracking the manual's conversion charts (Fundamentals Fig 6/8, Aspen Fig 2) with no re-tuning; the
cited k2 reaches equilibrium at reactor residence ("path covered 95 %"); atom balance closes. K2 is
anchored to the strict-source 59 % design conversion; K1 fixes the (secondary) carbamate/free-gas split.
Biuret kinetics in the sim (Ea = 85 kJ/mol, `STRIP_BIU_EA`) are corroborated by the Kaasenbrood
mechanism/data (Gaps2.md) and Chinda et al. 2017 (Ea = 80 kJ/mol), so no change is needed there.
The conservation proof battery is built (`gap_g4_conservation_harness.py`: atom-balance, null-feed,
Jacobian-sparsity; fast self-test PASSES; engine suite gated behind `--engine`, main.py ~13 min load).

**Still open (integration, not data):** convert HPCC + reactor + stripper + scrubber to a simultaneous
(equation-oriented) solve with the four atom balances as explicit constraints, retiring `REACT_TEAR_DES`.
That step needs K1/K2 derived LIVE from SR-POLAR/EOS fugacities (Aspen's method) rather than the
design-anchored calibration used standalone -- i.e. it rides on the G1 plant-wide reactive phase set.
Note the Aspen model itself uses **SR-POLAR EOS**, not electrolyte Extended-UNIQUAC, arguing ionization
is small at 160-200 C / low water; that is the validated industrial alternative to G1's tiered UNIQUAC.

**Acceptance:** zero and perturbed feeds cannot create matter; C/H/N/O close to numerical tolerance;
all outlet vectors respond to inlet changes; no signed correction stream remains.

## G6 - Live registry coverage and H1 enthalpy

**Catalogue half CLOSED** (`gap_g6_static_catalogue.py`): the strict-source design catalogue for every
numbered row is emitted by PARSING (not transcribing) the strict PFD -- 264 unique streams (161 with
mass-% composition, matching the ~163 in-scope), every row tagged `status=static, resolved=False`,
written to `reports/G6_static_stream_catalogue.{json,md}` and kept SEPARATE from the live registry.

**Enthalpy H0 tier DELIVERED** (`gap_g6_h0_enthalpy.py`): the sensible-only enthalpy was correctly
refused (it games the metric), but only the EXCESS term H^E is G1-gated. The formation + sensible +
phase-reference part (ideal solution) is available now from published thermochemistry, on a single
elements-at-298.15 K datum so it is reaction-consistent by construction. Declared-tier enthalpy with a
mandatory `EnthalpyBasis` flag: H0 (now) / H1 (+H^E, per G1 tier) / H2 (plant-reconciled). The 2026
source pass ADDED ammonium carbamate (Voskov 2016 dfH: solid -645.05, liquid -624.32 kJ/mol; Cp as
a+e T^-0.5), so the loop enthalpy is now reaction-consistent through the carbamate node, not only across
the net reaction; and upgraded urea Cp to the Voskov temperature-dependent form (-> ~150 J/mol/K at Tm,
matching the prior constant). Validated against first principles (water datum, latent 44.0, urea fusion
13.9 kJ/mol) AND against this plant's licensor manual: the datum reproduces the manual's reaction
enthalpies -- 2NH3(g)+CO2(g)->carbamate(s) = -159.6 kJ/mol, carbamate(l)->urea(l)+H2O(l) = +18.8 vs the
plant's +15.5 -- confirming reaction-consistency to a few kJ/mol across mixed reference states.

**Still open:** wire H0 into the live registry via the existing `make_stream` `h_kjkg` hook and add the
basis enum field; promote H0 -> H1 as each G1 tier lands; raise live coverage above 55/163 as G1/G4/G9
implement the currently-unmodelled units. Audit reports n(H0)/n(H1)/n(H2), not a single count.

**Acceptance:** every implemented outlet has one producing state, declared consumers, conserved splits,
and a basis-tagged enthalpy; catalogue coverage is reported separately from live connectivity coverage.

## G9 - Vendor/equipment equations

**G9a ejectors - materially advanced** (`gap_g9a_ejector_envelope.py`). The primary-nozzle throat area
is now FIRST-PRINCIPLES for all three units (324F002/F004/F005) from the strict-PFD motive states via
choked flow (d = 14.9 / 26.3 / 10.1 mm; primary-exit Mach matches the datasheet's "Mach 3-4"), so A_t
is no longer a fitted parameter. The model adds an off-design pull curve (double-choke Munday-Bagster/
Huang idealisation) and a molecular-weight entrainment response (heavier suction gas entrains more
mass, derived from the choked secondary flux) that the constant-omega surrogate lacks. All three duty
points close mass on the strict PFD (motive+suction=discharge, exact). Correction to the research pass:
solving for the mixing-area ratio that reproduces each design entrainment ratio gives A3/At ~ 4.4-20.6,
which STRADDLES/EXCEEDS Huang's refrigeration band (6.44-10.64), so that band does not bound these
deep-vacuum steam ejectors and cannot be used to draw an envelope. The off-design curve is instead
design-anchored with A3/At pinned by the single strict-PFD point.
Provenance note: the Koerting datasheet motive flows (927=600, 929=505 kg/h) conflict with the strict
PFD (927=1220, 929=180 kg/h); per CLAUDE.md 2 the PFD is used (it is mass-consistent). This module is
NOT yet wired into main.py's 324 ejector suction ODE -- that is the documented follow-on.

The condenser-train staging is now corroborated by this plant's manual (02 FUNDAMENTALS p.1-70/72):
324F002 pulls condenser 324E002 (0.31 bar) to the atmospheric absorber; 324F004 pulls condenser II
(0.13 bar system) to condenser III (0.33 bar); 324F005 pulls condenser III (0.33 bar) to condenser IV
(atmospheric). These fix the real per-ejector compression ratios (corroboration, not a 2nd duty point).

**Blocking datum (G9a):** a SECOND ejector duty point (or nozzle/mixing geometry) per 324F002/F004/F005
to pin A3/At independently and validate the pull-curve shape. The residual uncertainty is now
quantified (one free geometric parameter) rather than asserted.

**G9b valve hydraulics:** C_v back-calculable from rated flow and dP with declared single-point
provenance; elevation heads from the P&ID; trim characteristic remains open. Not built this pass.

**G9c Unit 335 - data gate PARTIALLY lifted (2026 source pass):** this plant's licensor manual
(02 FUNDAMENTALS pp.1-85..1-109) now supplies the full granulation equipment name list, the process
description, and many design flows (product 1750-2000 MTPD; fluidisation air ~340000 m3/h; sprayer air
~36820 m3/h; recycle ratio ~0.40; UF at 0.5 wt%; melt 98.6 wt% at 140 C / 3.6 bar). So Unit 335 is no
longer "no equipment list" -- a declared boundary block closing mass/atom/energy with exposed states can
now be built from the manual. **Still missing:** the equipment DATASHEETS / P&ID sizing (heat-transfer
areas, fan curves, screen efficiencies) needed to make it a rating model rather than a spec-flow block.

**Acceptance:** momentum/pressure residuals close against vendor duty points and Unit 335 exposes mass,
component, energy, hydraulic and control states with connected streams.
