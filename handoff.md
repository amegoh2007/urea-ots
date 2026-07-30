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
`backend/main.py`. The property package also lacks urea in the reactive runtime phase set and lacks
approved off-temperature aqueous NH3/CO2 standard-state heat capacities.

**Required solution:** construct one true-species gamma-phi MESH boundary: Extended UNIQUAC liquid,
SRK/PHS vapor fugacity, electroneutral speciation, chemical-equilibrium residuals, and explicit
reaction/excess enthalpy. Add urea and validate against the licensor design point plus independent
high-pressure data before replacing each empirical unit, one unit at a time.

**Missing evidence:** approved NH3(aq)/CO2(aq) heat-capacity functions and a validated parameter set
covering the plant composition, 99-200 C, and vacuum through 144 bar(a).

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

**Evidence:** `backend/audit_model_compliance.py` reports nonzero component corrections at 323F004,
324E001, and 324E003. `sol_pin_strength` overwrites urea/water after the conservative ODE to retain
rounded PFD strengths. This is a reconciliation action inside runtime physics.

**Required solution:** reconcile the strict design rows outside the ODE using documented uncertainty,
then initialize the conservative component states from the reconciled data. Use the documented
rounding interval as Type-B uncertainty (`variance = resolution^2 / 12`); use online-sensor weights
only after approved covariance is supplied.

**Acceptance:** every runtime component residual is below 1e-6 kg/h with no component overwrite,
while reconciled design rows remain inside their documented uncertainty intervals.

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

## G5 - Unit-328 absolute energy ledger is incomplete

**Evidence:** the executable audit baseline gives `Q_in=6653.8 kW`, `Q_out=8344.2 kW`, residual
`-1690.5 kW`. Several duties use back-solved latent heats, and stream records have no absolute
enthalpy. Adding the 101.5 kJ/mol hydrolysis heat or the 117 kJ/mol carbamate decomposition heat in
isolation does not establish a consistent reference state.

**Required solution:** implement a single reference-state enthalpy interface from G1, including
ideal/standard-state, excess, vapor, and reaction contributions. Replace one back-solved latent at a
time and retain an explicit boundary ledger.

**Acceptance:** Unit 328 total/component balances close and the independent energy residual is within
1 kW at design and remains bounded under a feed/steam perturbation.

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

## G7 - Recycle loops are observed, not solved

**Evidence:** Unit 328 and synthesis recycles are one-tick sequential-modular tears. Telemetry now
correctly reports `RECYCLE_TEAR_RESIDUAL` with `is_solver_convergence=false`; there is no inner
fixed-point or Newton solve. Unit-324 T/P loops are bounded Picard iterations, but the larger
flowsheet tears are dynamic states.

**Required solution:** retain dynamic tears for real transport delays. For algebraic recycles only,
add a bounded Wegstein/Anderson inner solve with scaling, maximum iterations, residual norm, and a
safe last-state fallback.

**Acceptance:** each recycle is classified dynamic or algebraic; algebraic loops meet a declared
residual tolerance and dynamic loops report residence/transport state rather than convergence.

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

**Evidence:** 322F001 and the 324 vacuum ejectors use reduced entrainment laws; no approved nozzle,
mixing-throat, diffuser geometry, or performance map exists. Several vessel/valve hydraulic models
lack verified Cv/elevation data. Unit 335 is only a melt-plus-UF85 boundary, not simulated equipment.

**Required solution:** obtain vendor ejector geometry/maps, valve Cv/trim and elevation data, plus
Unit-335 equipment/P&ID/datasheets. Then integrate the existing Huang ejector core and conservative
equipment inventories one tag at a time.

**Acceptance:** momentum/pressure residuals close against vendor duty points and Unit 335 exposes
mass, component, energy, hydraulic, and control states with connected streams.

## G10 - One mapping conflict remains unresolved

**Evidence:** the available 323 mapping gives internally conflicting direction/role evidence for
HV-323605 in the 323F010 vacuum path. Changing its sign or endpoints from code inspection alone
would risk reversing an operator action.

**Required solution:** resolve against the approved P&ID or field valve action sheet, then add a
directional perturbation test.

**Acceptance:** opening/closing action, upstream/downstream nodes, and fail position agree across
P&ID, DCS faceplate, telemetry, and pressure response.

## G12 - Melt-recycle dilution and Stream-609 identity need approved routing data

**Evidence:** the strict PFD table closes Stream 609 as Stream 402G melt plus Stream 697 UF85
(`85405 + 694 = 86099 kg/h`, rounded to `86100 kg/h`). A P&ID-oriented equipment narrative states
that UF85 injection stops when LV-324501A closes, which makes LV-324501B a raw-402G recycle. The
separate `References/323D002.md` narrative instead calls Stream 609 the recycle and requires cool
steam-condensate injection downstream of LV-324501B. No approved condensate stream number, flow,
temperature, valve/interlock, or endpoint is available. The simulator therefore routes the evidenced
raw melt conservatively but cannot yet model the dilution or resulting atmospheric flash. Sensible
mixing of the tabulated 140 C melt with 40 C UF85 predicts about 138.62 C for forward Stream 609,
whereas the rounded PFD row remains 140 C; no heat-tracing duty or heat-of-mixing datum explains the
difference, so the runtime does not inject compensating heat.

**Required solution:** resolve the branch order and Stream-609 endpoints from the approved P&ID/line
list, then obtain the condensate injection tag and operating envelope. Add the condensate as an
explicit water/enthalpy inlet and solve the tank flash through the shared Extended-UNIQUAC/pure-water
boundary; do not infer a dilution rate from a narrative.

**Acceptance:** A-forward and B-recycle selections each have one exclusive producer/consumer path;
UF85 follows its documented interlock; condensate mass and enthalpy are measured inputs; the
323D002 component and energy residuals close through a route toggle without a concentration pin.
