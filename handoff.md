# Open Simulation Gaps Only

Updated: 2026-07-31
Strict source: `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`
Audit: `FULL_SIMULATION_EXTENDED_UNIQUAC_AUDIT_2026-07-29.md`
Closure methodology: `References/Strategic Resolution of Thermodynamic and Topological Simulation Gaps in High-Pressure Urea Synthesis.md`
Research pass applied 2026-07-31: `References/Gaps solution.md`

Closed items are intentionally deleted from this file. Each item below is still open because the
remaining equation or datum cannot be supplied honestly by the current repository evidence. Each
carries the peer-reviewed **Method** to apply and the exact **Blocking datum** that must arrive before
that method can close it. Fabricating closure is prohibited (CLAUDE.md 1).

The 2026-07-31 execution pass built five standalone, self-validated closure/analysis modules (the same
"validate on its own before wiring" pattern as `props_nh3co2h2o.py`); each runs in <1 s and is cited
line-by-line. What they closed is deleted below; what they left open is sharpened. New modules:
`gap_g6_static_catalogue.py`, `gap_g6_h0_enthalpy.py`, `gap_g9a_ejector_envelope.py`,
`gap_g2_reference_state_audit.py`, `gap_g4_conservation_harness.py`.

## G1 - Runtime reactive thermodynamics is not plant-wide Extended UNIQUAC

**Evidence:** `backend/props_nh3co2h2o.py` implements the Thomsen/Darde NH3-CO2-H2O Extended-UNIQUAC/
SRK/speciation core (validated, off-25 C capable), but the HPCC, reactor, stripper, scrubber, LP
absorber and Unit-328 columns still use calibrated splits in `backend/main.py`, and urea is absent
from the reactive runtime phase set.

**Method (doc sec.2 + Gaps-solution re-scope):** the `Gaps solution.md` pass argues for a TIERED
property architecture rather than one universal Extended UNIQUAC, because the Thomsen-Rasmussen ionic
parameters are published valid only to ~110 C / 100 bar and the Debye-Huckel term needs a mixed-solvent
dielectric constant that does not exist for NH3-H2O-urea at synthesis conditions:
  - Tier A (HP loop 150-230 C / 3.5-28 MPa): molecular UNIQUAC, 6 neutral constituents + 3 liquid
    reactions, Voronin virial EoS -- all parameters OPEN (Voskov & Voronin, JCED 61 (2016) 4110).
  - Tier B (LP/absorbers <=110 C / <=100 bar): the existing Extended UNIQUAC, domain-limited.
  - Tier C (324 melt): see G2.
  Interface = apparent-composition handover on a common elements-at-298.15 K enthalpy datum
  (now provided by `gap_g6_h0_enthalpy.py`) with domain-flag propagation.

**Blocking datum:** the urea/ion reactive parameters (Voskov-Voronin UNIQUAC set is OPEN and can seed
the fit) plus the licensor 100%-load HP design point (user-supplied) for plant reconciliation only.
Thermodynamic validation can instead use Voskov & Voronin's published conversion/bubble-point grids
and the saddle azeotrope. Full runtime integration into each HP/LP unit in flow order is multi-week
scope; it is the largest remaining build.

**Acceptance:** every process-mixture phase-equilibrium/enthalpy call reports model, domain status,
fugacity/energy residual, and closes MESH without an empirical split override.

## G2 - Unit-324 vacuum model off-design slope is not independently validated

**Re-diagnosed 2026-07-31** (`gap_g2_reference_state_audit.py`). The research-pass hypothesis that the
stage-1 error (raw 0.9209 vs PFD 0.9431 urea mass fraction at 130 C) is a urea STANDARD-STATE
(subcooled-liquid / missing dCp) discontinuity is **FALSIFIED**: `thermo_extended_uniquac` solves a
water-vapour-only equilibrium (`a_water(x,T) * Psat_water(T) = P`), urea is non-volatile, so the root
is fixed entirely by `gamma_water` and the pure-water reference -- urea's standard-state Gibbs energy
never enters (test reconstructs the root from `gamma_water * Psat` alone). The residual is genuinely in
the urea->water binary, as `gap_g2_vacuum_vle_refit.py` already showed. A published-anchor unit test
confirms the urea fusion point (dfusH/dfusS = 132.7 C, Tischer 2019), which the two design points do
straddle -- but that is a solvent-independent fact, not a reference-state defect in this model.

Also confirmed from the strict PFD: streams 401/402 report urea (94.31/97.71) and biuret (0.69/0.85)
SEPARATELY, so the PFD "urea" target is urea-only, not a urea+biuret lump (resolves the accounting
question the research pass raised). The live 324 model already anchors the departure (`evap_w_eq` =
`w_des + (w_model - w_model_des)`), so the raw -2.22 pp is not carried in the sim; only the off-design
SLOPE is model-supplied.

**Method:** the OPEN item is that off-design slope. It is now BOUNDED by two independent activity
models: the Voskov-Voronin UNIQUAC in the sim and the sub-regular Margules with Voskov et al. (2012,
JCED 57, 3225) water-urea parameters (a0=128, a1=521 J/mol, fitted below 135 C independently of the two
vacuum points) agree in SIGN at both stages (dw/dT>0, dw/dP<0) and within a factor ~2 in magnitude.

**Blocking datum:** INDEPENDENT multi-point ebulliometric urea-water VLE at 130-140 C over the 90-99
wt% melt, to tighten the slope from "bounded by two models" to "validated". Not publicly available
(the 2026-07-31 pass re-confirmed this). NOT USED: `References/Urea-Water VLE Data Research.md`
proposes a "Fahmy-Nassar" explicit correlation, but its own pure-water Psat (2.10 bar at 130 C) is
22% below IAPWS-IF97 (2.70 bar) -- an internal physical inconsistency -- and it carries synthetic-source
markers, so it is recorded as an unverified lead, not adopted.

**Acceptance:** independent vacuum VLE points bound the prediction error at both stages and the model
closes pressure-composition residuals without an additive PFD correction.

## G4 - HP synthesis loop has signed/pinned surrogate flows

**Evidence:** 322R001 applies `REACT_TEAR_DES`, including signed component corrections, to reconcile
its reduced conversion surrogate. 322E002 uses an anchored flash rather than the reactive Extended-
UNIQUAC package. 322E003 scrubber discharges remain pinned; scalar HPCC/scrubber inventories are not
paired with full component holdups.

**Method (doc sec.2.4 + Gaps-solution sec.5):** convert HPCC + reactor + stripper + scrubber to a
simultaneous (equation-oriented) solve with the four atom balances as explicit constraints and
homotopy continuation on recycle gain, retiring `REACT_TEAR_DES` because an explicitly connected
recycle conserves C/H/N/O by construction. Architecture is templated on the published, plant-validated
CO2-stripping model (Chinda et al. 2017: pool condenser as conversion-specified reactor; reactor as
CSTRs-in-series per sieve tray + flash; staged stripper and 5-stage scrubber with carbamate
equilibrium). Biuret kinetics in the sim (Ea = 85 kJ/mol, `STRIP_BIU_EA`) are corroborated by Chinda's
second-order value (Ea = 80.0 kJ/mol, A = 5.84 m3/mol/s), so no change is needed there.
The conservation proof battery this needs is now built: `gap_g4_conservation_harness.py` implements
the atom-balance, null-feed and Jacobian-sparsity tests (fast self-test PASSES; the engine-backed
suite is gated behind `--engine` since main.py is a ~13 min load).

**Blocked on:** G1 Tier A (needs the reactive phase set + urea kinetic rate constants) -- cannot
precede it. Carbamate/urea rate constants must be read from Chinda et al. eqs (1)-(2) directly; the
PDF text layer garbled them.

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
mandatory `EnthalpyBasis` flag: H0 (now) / H1 (+H^E, per G1 tier) / H2 (plant-reconciled). Validated
against first principles (water formation datum, latent 44.0 kJ/mol, urea fusion 13.9 kJ/mol).

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

**Blocking datum (G9a):** a SECOND ejector duty point (or nozzle/mixing geometry) per 324F002/F004/F005
to pin A3/At independently and validate the pull-curve shape. The residual uncertainty is now
quantified (one free geometric parameter) rather than asserted.

**G9b valve hydraulics:** C_v back-calculable from rated flow and dP with declared single-point
provenance; elevation heads from the P&ID; trim characteristic remains open. Not built this pass.

**G9c Unit 335 - fully data-gated:** no equipment list, P&ID or datasheets. Interim recommendation
(doc sec.7.3): a declared boundary block closing mass/atom/energy with exposed states and visible
degrees of freedom. **Blocking datum:** Unit-335 equipment list / P&ID / datasheets.

**Acceptance:** momentum/pressure residuals close against vendor duty points and Unit 335 exposes mass,
component, energy, hydraulic and control states with connected streams.
