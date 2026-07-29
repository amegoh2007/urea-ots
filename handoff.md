# Handoff: Open Gaps Only

Updated 2026-07-29. This file tracks ONLY what is still open. Closed/delivered work is recorded in
As-Built §§22.11-22.15, `C36_PROPERTY_BASIS_PROPOSAL.md`, `research_plan_324_vacuum_train.md`,
`research_plan_328d003_compartments.md`, `PID_EVIDENCE_AUDIT_2026-07-27.md`, and the commit history.

**Method gaps are closed.** Every closure model named in the owner references
(`Resolving Simulator Thermodynamics Gaps.docx`, `Urea Simulation Gaps Resolution1.md`) is implemented
from first principles and validated against independent anchors, delivered as standalone, test-gated
modules (see As-Built §22.15):
`backend/props_nh3co2h2o.py` (Extended UNIQUAC: Debye-Hückel, full activity, SRK-VLE, Newton speciation,
reaction enthalpy = C43 core, excess enthalpy = C34 excess part; 37/37),
`backend/reconcile_crowe.py` (Crowe reconciliation; 6/6),
`backend/ejector_huang.py` (Huang 1-D ejector; 11/11).

What remains below is narrowly one of two kinds only — a specific external datum that is paywalled,
vendor-proprietary, or a governance artifact (cannot be sourced or fabricated), or engine integration
into `main.py`. No property, sink, curve, covariance, or geometry was fabricated to force a closure.

## Open — engine integration (phases 2-5)

Wire the delivered engines into `main.py` behind a flag, preserving the bit-exact design seed:
- Feed `props_nh3co2h2o.py` speciation/activity into the LP/MP sections; replace lumped-mass transport in
  328D001/328D003/323C005 with live molecular vectors (extend the existing des_advance species layer).
- Replace the empirical `evap_w_eq` for the Unit-324 evaporators with the activity/fugacity VLE.
- **C43:** map the lumped NH3/CO2 flows into the speciated carbamate matrix in the Unit-328 vectors and
  replace the back-solved latents with explicit ξ·ΔH (from `dH_reaction`). Acceptance: the read-only
  `q328_resid` diagnostic in `step_sim` and the −1690.5 kW envelope (audit estimates the missing
  carbamate term at ~1096-1425 kW).
- **C34:** populate the `enthalpy_kJkg` field and complete the stream graph (163 PFD streams vs 55
  runtime records) once the absolute-enthalpy datum below exists.
- Explicitly approve or replace the frozen `RHO_744`/`RHO_741`/`R328_C002_RHO`/`R328_C004_RHO`.

## Open — external inputs (cannot be fabricated)

- **NH3(aq)/CO2(aq) standard-state Cp** (3-parameter Helgeson form; Thomsen & Rasmussen 1999, paywalled).
  Gates the R2/R3/R5 constants and `speciate` above 25 °C and the ABSOLUTE (vs excess) stream enthalpy
  that C34 needs. Web research 2026-07-29 (Plyasunov & Shock 2000) found no open, temperature-resolved
  Cp usable in that form without fitting unpublished data; the framework is already parametrized on the
  two rows and refuses to extrapolate rather than guess. At 298.15 K everything runs on the sourced dGf.
- **Approved sensor covariance Σ (C35).** Needed to certify the Unit-324 residuals (324F004 −1.917,
  324E001 −170.105, 324E003 −126.793 kg/h) with the delivered Crowe engine. A governance artifact, not
  derivable; do not introduce a fictitious urea sink.
- **Vendor ejector geometry + tie pressures (C40).** The throat/exit/mixing-loss geometry for
  324F002/F004/F005 and the firm downstream tie pressures (F004 discharge / E006), plus gas-line
  lengths/fittings/roughness and condenser/ejector gas-side pressure drops. These fix the normal-shock
  position and hence the true breakdown backpressure; the Huang core is ready to consume them. Until
  supplied, retain the PFD-anchored training surrogate and shared rounded manifold pressures.

## Open — product and repository follow-up

- Confirm the 321-1/323-1 overlay registration and FFIC-329401/TIC-328012 live-PV row assignment on a
  running HMI.
- Remove orphaned Git LFS objects and unreachable commits through repository recreation or GitHub
  Support if remote storage cleanup is still required.
