# Open Simulation Gaps Only

Updated: 2026-07-30
Strict source: `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`
Audit: `FULL_SIMULATION_EXTENDED_UNIQUAC_AUDIT_2026-07-29.md`

Closed items are intentionally deleted from this file. Each item below is still open because the
remaining equation or datum cannot be supplied honestly by the current repository evidence.

## G1 - Runtime reactive thermodynamics is not plant-wide Extended UNIQUAC

**Evidence:** `backend/props_nh3co2h2o.py` implements the Thomsen/Darde
NH3-CO2-H2O Extended-UNIQUAC/SRK/speciation core, but the HPCC, reactor, stripper, scrubber,
LP absorber, and Unit-328 columns still use calibrated splits or reduced correlations in
`backend/main.py`. The property package still lacks urea in the reactive runtime phase set. The
off-temperature aqueous NH3(aq)/CO2(aq) standard-state heat capacities were the one documented data
blocker; they are now sourced (Correa-Thomsen-Fosbol, Fuel 2023, Table 1: 72.04 / 238.05 J/mol/K,
constant-Cp limit), so the property basis now solves speciation and reaction/absolute enthalpy off
25 C. The full 3-parameter Cp(T) from the paywalled Thomsen&Rasmussen 1999 remains an accuracy
refinement, not a blocker.

**Required solution:** construct one true-species gamma-phi MESH boundary: Extended UNIQUAC liquid,
SRK/PHS vapor fugacity, electroneutral speciation, chemical-equilibrium residuals, and explicit
reaction/excess enthalpy. Add urea and validate against the licensor design point plus independent
high-pressure data before replacing each empirical unit, one unit at a time.

**Remaining work:** runtime integration of the (now off-T-capable) property basis into each HP/LP/
absorber/desorber unit in flow order, urea added to the reactive phase set, and validation against
the licensor design point. No open data blocker remains for the aqueous NH3-CO2-H2O sub-model;
the urea reactive parameters and the licensor high-pressure design point are the integration inputs.

**Acceptance:** every process-mixture phase-equilibrium/enthalpy call reports model, domain status,
fugacity/energy residual, and closes MESH without an empirical split override.

## G2 - Unit-324 UNIQUAC vacuum use is a design-anchored extrapolation

**Evidence:** the new `backend/thermo_extended_uniquac.py` uses the open Voskov-Voronin binary
H2O/urea parameters (standard UNIQUAC; the neutral-species Extended-UNIQUAC limit). Its pure-water
fugacity reference now comes from the shared IAPWS-IF97 saturation line (G11 closed). The published
full-model validation envelope is 135-230 C and 3.5-45 MPa; 324E001/F001 and 324E003/F003 operate at
130/140 C and 0.33/0.131 bar(a). The implementation marks this `DESIGN_ANCHORED_EXTRAPOLATION`. At
130 C/0.33 bar the raw model root is about 0.9209 urea mass fraction versus the PFD's 0.9431; at
140 C/0.131 bar it is about 0.9768 versus 0.9771.

**Required solution:** obtain primary ebulliometric/VLE data or a validated parameter regression at
the two vacuum-stage domains, fit only inside a versioned data-reconciliation layer, and rerun the
same monotonicity/residual tests. Do not remove the design anchor until the first-stage discrepancy
is explained.

**Acceptance:** independent vacuum VLE points bound the prediction error at both stages and the
model closes pressure-composition residuals without an additive PFD correction.

## G3 - Three downstream design-strength pins violate component conservation

**Evidence:** the audited `clip_resid_kgh` is the DESIGN-ANCHOR back-solve clip from
`_sol_stage_anchor` (`vapour = inlet - melt_outlet + reaction`, per species; components that come out
negative -- species the tabulated melt holds but the tabulated feed cannot supply -- are clamped to
zero and back-charged to water). Confirmed magnitudes: 323C003 and 323F010 are exact identities
(0.0), 323F004 = -1.92 kg/h (0.4 % of stage vapour), **324E001 = -170.11 kg/h (1.2 %)**, **324E003 =
-126.79 kg/h (4.6 %)**. `sol_pin_strength` separately re-pins the runtime urea/water pair onto the
mass-energy strength each tick; removing it makes the runtime species layer close by construction but
does NOT touch this static anchor clip.

**Why it cannot be closed by rounding reconciliation:** the PFD tabulates compositions to 2 dp
(+/-0.005 wt%) and flows to ~1 kg/h, so the Type-B rounding budget (`variance = resolution^2/12`) per
species per row is only a few kg/h. The E001/E003 clips are 170/127 kg/h -- 30-900x that budget --
so the tabulated 317 -> 401 -> 402 rows are mutually inconsistent at the ~1-5 % level (the F-11 class:
the melt composition is not reachable from the feed by the tabulated evaporation). A data
reconciliation that forced closure would have to move licensor values by 200-1000x their stated
precision, i.e. replace the PFD data, which CLAUDE.md 1 forbids. F004's -1.92 kg/h is near the
rounding budget and would reconcile; E001/E003 will not.

**Required data (only the user can supply):** the licensor's UNROUNDED stream-317/401/402 rows (or a
corrected PFD-21 evaporation balance). With component-consistent design rows the anchor clip goes to
zero and the runtime pin can be retired.

**Acceptance:** every runtime component residual is below 1e-6 kg/h with no component overwrite, and
the design-anchor clip closes to <1 kg/h once the reconciled (unrounded) rows are in place.

## G4 - HP synthesis loop has signed/pinned surrogate flows

**Evidence:** 322R001 applies `REACT_TEAR_DES`, including signed component corrections, to reconcile
its reduced conversion surrogate. 322E002 uses an anchored flash rather than the available reactive
Extended-UNIQUAC package. 322E003 scrubber discharges remain pinned: a perturbed wash/feed is not
reflected conservatively in its outlets. Scalar HPCC/scrubber inventories are not paired with full
component holdups.

**Required solution:** after G1, replace one tag at a time in flow order: HPCC MESH/component
inventory, reactor rate/species/energy equations, then scrubber reactive absorption/component
inventory. Remove `REACT_TEAR_DES` only when an explicitly connected recycle closes the atoms and
mass.

**Acceptance:** zero and perturbed feeds cannot create matter; C/H/N/O close to numerical tolerance;
all outlet vectors respond to inlet changes; no signed correction stream remains.

## G6 - Live flowsheet registry is incomplete and carries no absolute enthalpy

**Evidence:** the executable baseline publishes 55 live records versus 163 unique in-scope
strict-source stream numbers; 0/55 have `enthalpy_kJkg`. Some vessel registries publish gross make or
pump flow rather than actual outlet state. Numbered rows also lack a complete endpoint catalogue.

**Required solution:** maintain two artifacts: (1) a strict-source design catalogue for all numbered
rows, explicitly marked static/unresolved, and (2) a live registry only for implemented producer-
consumer edges. Add live streams from actual state vectors and use G1/G5 for enthalpy; never promote
a PFD row to a live stream without known endpoints.

**Acceptance:** every implemented outlet has exactly one producing state, declared consumers,
conserved splits, and calculated enthalpy; catalogue coverage is reported separately from live
connectivity coverage.

## G8 - Steam-network user ledger is still partial

**Evidence:** PV-329207B/C directions, D009 flashing, and liquid transfers are corrected, and
FT-329407 now reports the actual B-valve export. However, `M_USERS_LP` remains an aggregate boot
calibration rather than the sum of every live LP heater/ejector draw. The model design state can
therefore show zero actual turbine export while PFD stream 932 is 16.707 t/h.

**Required solution:** connect each LP consumer's condensate/motive flow to a named header edge,
derive the residual unimplemented-user boundary from the PFD once, and remove the boot-time
load-following aggregate.

**Acceptance:** HP, 9-bar, and LP vapor/liquid node residuals close independently; actual
FT-329407 equals connected stream 932 and reproduces the PFD design value without synthesis.

## G9 - Vendor/equipment equations are data-gated

**Evidence:** 322F001 and the 324 vacuum ejectors use reduced entrainment laws. The 324 evaporation
datasheets supply a single design point per ejector (324F002 motive 650 / suction 94 kg/h @ 0.2 bar,
discharge 744 kg/h @ 1.0 bar 123 C; 324F004 motive 927=600 / suction 712=634 kg/h @ 0.122 bar;
324F005 motive 929=505 kg/h) but explicitly confirm that no pull curve, shut-off/overload point,
critical backpressure, motive-pressure correction, or nozzle/mixing/diffuser geometry exists -- "a
polynomial cannot be identified from one point". Several vessel/valve hydraulic models still lack
verified Cv/elevation data, and Unit 335 is only a melt-plus-UF85 boundary, not simulated equipment.

**Required solution:** obtain vendor ejector geometry/maps, valve Cv/trim and elevation data, plus
Unit-335 equipment/P&ID/datasheets. Then integrate the existing Huang ejector core and conservative
equipment inventories one tag at a time.

**Acceptance:** momentum/pressure residuals close against vendor duty points and Unit 335 exposes
mass, component, energy, hydraulic, and control states with connected streams.
