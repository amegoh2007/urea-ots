# Open Simulation Gaps Only

Updated: 2026-07-31
Strict source: `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`
Audit: `FULL_SIMULATION_EXTENDED_UNIQUAC_AUDIT_2026-07-29.md`
Closure methodology: `References/Strategic Resolution of Thermodynamic and Topological Simulation Gaps in High-Pressure Urea Synthesis.md`

Closed items are intentionally deleted from this file. Each item below is still open because the
remaining equation or datum cannot be supplied honestly by the current repository evidence. Each now
carries the peer-reviewed **Method** to apply (from the closure-methodology doc above) and the exact
**Blocking datum** that must arrive before that method can close it. A 2026-07-31 research pass
(open literature + the doc's own cited sources) confirmed the blocking data below is either flagged
by the doc itself as user-supplied (G2) or is not publicly available (G9 pull curves / Unit-335),
so these are genuinely gated, not oversights. Fabricating closure is prohibited (CLAUDE.md 1).

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

**Method (doc sec.2):** universal Extended UNIQUAC liquid (Thomsen/Darde combinatorial + residual
`u_ij = u_ij^0 + u_ij^T(T-298.15)` + Debye-Huckel, b=1.5) coupled to SRK with **Huron-Vidal (or MHV2)
mixing rules** so the activity model sets the EoS a-parameter at infinite pressure, giving vapour
fugacities that satisfy `f_i^V = f_i^L` across 140-250 bar; electroneutral speciation over the
carbamate/bicarbonate/protonation set; urea + biuret formation kinetics via the Kaasenbrood (1963)
HNCO route to retire `REACT_TEAR_DES` (see G4). Integrate one unit at a time in flow order.

**Blocking datum:** the urea/ion `r_i,q_i` and `u_ij^0,u_ij^T` reactive parameters plus the licensor
100%-load HP synthesis design point. The Voskov-Voronin (2016) UNIQUAC urea/carbamate parameters are
OPEN (ureaknowhow.com PDF, JCED 61 4110) and can seed the fit, but the licensor HP design point for
this specific 1750 MTPD loop is user-supplied. Full universal MESH integration is multi-week scope,
not a single session; it is the largest remaining build.

**Acceptance:** every process-mixture phase-equilibrium/enthalpy call reports model, domain status,
fugacity/energy residual, and closes MESH without an empirical split override.

## G2 - Unit-324 UNIQUAC vacuum use is a design-anchored extrapolation

**Evidence:** the new `backend/thermo_extended_uniquac.py` uses the open Voskov-Voronin binary
H2O/urea parameters (standard UNIQUAC; the neutral-species Extended-UNIQUAC limit). Its pure-water
fugacity reference now comes from the shared IAPWS-IF97 saturation line. The published
full-model validation envelope is 135-230 C and 3.5-45 MPa; 324E001/F001 and 324E003/F003 operate at
130/140 C and 0.33/0.131 bar(a). The implementation marks this `DESIGN_ANCHORED_EXTRAPOLATION`. At
130 C/0.33 bar the raw model root is about 0.9209 urea mass fraction versus the PFD's 0.9431; at
140 C/0.131 bar it is about 0.9768 versus 0.9771.

**Method (doc sec.3.2):** refit only the urea-water binary residual interactions
`tau_ij = exp(-(u_ij^0 + u_ij^T(T-298.15))/T)` against primary ebulliometric vapour-pressure data at
sub-atmospheric conditions, inside a versioned data-reconciliation layer; keep the high-pressure
Voskov-Voronin parameters intact for the synthesis loop (do not globally overwrite).

**Method EXECUTED (doc sec.3.2):** `backend/gap_g2_vacuum_vle_refit.py` actually performs the refit.
A two-parameter (u0,u1) fit reproduces BOTH design points exactly but FLIPS the fixed-pressure
temperature monotonicity (urea mass fraction falls with T -- unphysical for vacuum boiling); a
one-parameter fit that preserves monotonicity nails stage 1 (0.9431) but drives stage 2 to 0.9838
(+0.67 pp vs the PFD 0.9771, worse than Voskov's -0.03 pp). So NO physically-monotonic single
urea-water binary reproduces both licensor vacuum points -- two points at different (T,P)
under-constrain a T-dependent binary. Neither refit is committed (both degrade the model); the
anchored-departure model (Voskov physics + pinned design strength) stays as the best honest choice.

**Blocking datum (2026-07-31 research pass):** INDEPENDENT multi-point ebulliometric urea-water VLE at
130-140 C over the 90-99 wt% melt, to fix the interaction SHAPE the two design points cannot. Searched
the doc's cited sources + open literature: accessible urea-water BPE/VLE (Brouwer phase diagrams;
SCR/AdBlue BPE, e.g. J.Mech.Sci.Tech 2016) covers only DILUTE urea (<=32 wt%); Voskov-Voronin is
validated 3.5-45 MPa only (its vacuum use IS this gap). The concentrated-melt vacuum data is not
publicly available and must be measured/obtained. The first-stage 0.9209 vs 0.9431 discrepancy is a
systemic extrapolation error, not rounding, so no additive PFD correction is permitted.

**Acceptance:** independent vacuum VLE points bound the prediction error at both stages and the
model closes pressure-composition residuals without an additive PFD correction.

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

**Method (doc sec.2.4):** model 322R001 as a CSTR/plug-flow network with explicit carbamate-dehydration
kinetics driven by the local L (NH3/CO2) and W (H2O/CO2) ratios, plus Kaasenbrood (1963) biuret
kinetics via the HNCO isomerization route (`urea <-> HNCO + NH3`; `urea + HNCO <-> biuret`). The signed
`REACT_TEAR_DES` correction is then unnecessary because the explicitly connected recycle conserves
C/H/N/O by construction. **Blocked on G1** (needs the reactive Extended-UNIQUAC phase set + urea kinetic
rate constants) -- cannot precede it.

**Acceptance:** zero and perturbed feeds cannot create matter; C/H/N/O close to numerical tolerance;
all outlet vectors respond to inlet changes; no signed correction stream remains.

## G6 - Live flowsheet registry is incomplete and carries no absolute enthalpy

**Evidence:** the executable baseline publishes 55 live records versus 163 unique in-scope
strict-source stream numbers; 0/55 have `enthalpy_kJkg`. Some vessel registries publish gross make or
pump flow rather than actual outlet state. Numbered rows also lack a complete endpoint catalogue.

**Required solution:** maintain two artifacts: (1) a strict-source design catalogue for all numbered
rows, explicitly marked static/unresolved, and (2) a live registry only for implemented producer-
consumer edges. Add live streams from actual state vectors and use G1 for enthalpy; never promote
a PFD row to a live stream without known endpoints.

**Method (doc sec.4.4) + split:** the 163-row STATIC catalogue is executable now from the strict PFD
source (no external data) and closes the catalogue-coverage half. The LIVE-enthalpy half (`enthalpy_kJkg`
for every live stream) is **blocked on G1**: a defensible reaction-consistent absolute enthalpy needs the
universal Extended-UNIQUAC basis propagated plant-wide (doc sec.2). A sensible-only enthalpy would game
the audit metric rather than close it, so it is deliberately NOT applied. `make_stream` already exposes
the `h_kjkg` hook for when G1 lands. Registry coverage (55/163) also rises only as G1/G4/G9 implement
the currently-unmodelled units.

**Acceptance:** every implemented outlet has exactly one producing state, declared consumers,
conserved splits, and calculated enthalpy; catalogue coverage is reported separately from live
connectivity coverage.

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

**Method (doc sec.6) + why one point is not enough:** the doc proposes Huang's 1D constant-pressure-
mixing model -- choked primary `m_p = P_g A_t/sqrt(T_g) * sqrt(gamma/R*(2/(gamma+1))^((gamma+1)/(gamma-1)))`,
a hypothetical-throat where the secondary also chokes (constant critical entrainment ratio omega), and
a normal shock for recompression. The current 324 ejector model already encodes the critical-regime
essence (constant omega + suction-pressure roll-off). Huang adds the critical-vs-subcritical
backpressure transition, which needs the nozzle throat area `A_t` AND the mixing-area ratio `A_3/A_t`
AND the isentropic efficiencies. From the SINGLE vendor duty point per ejector these are
under-determined (same failure mode proven for G2): a lone point fixes `A_t` and the design omega but
not the off-design curve -- fitting the remainder reproduces the point while leaving the pull curve
unconstrained (and liable to unphysical off-design shape). The datasheets state outright a curve
"cannot be identified from one point".

**Blocking datum:** a SECOND ejector duty point (or nozzle/mixing geometry) per 324F002/F004/F005 to
constrain the pull curve, valve Cv/trim + elevation heads for the hydraulic residuals, and Unit-335
equipment/P&ID/datasheets (335 is currently only a melt+UF85 boundary, no simulated equipment). None
exist in the repository; the ejector half is design-anchored to its single point and Unit 335 is fully
data-gated.

**Acceptance:** momentum/pressure residuals close against vendor duty points and Unit 335 exposes
mass, component, energy, hydraulic, and control states with connected streams.
