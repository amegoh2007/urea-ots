# Handoff: Open Gaps Only

Updated 2026-07-27. Closed work is recorded in As-Built §§22.11-22.13,
`research_plan_324_vacuum_train.md`, `research_plan_328d003_compartments.md`, and
`PID_EVIDENCE_AUDIT_2026-07-27.md`.

## Model-compliance gaps

### C34 — canonical stream graph and enthalpy

The in-scope PFD contains 163 unique stream numbers, while the runtime publishes 55 canonical stream
records. Complete the remaining stream graph with calculated `[T, P, phase, F_i, h, rho]` records
after the C36 thermodynamic basis is approved. None of the current records has calculated enthalpy.

### C35 — molecular conservation versus the PFD

Unreconciled Unit-324 design residuals remain: 324F004 −1.917, 324E001 −170.105, and 324E003
−126.793 kg/h. Molecular certification requires reconciled licensor stream data or approved
measurement weights and uncertainties; do not introduce a fictitious urea sink.

### C36 / TD-009 / TD-012 — property and species basis

- Obtain or approve a complete NH3-CO2-H2O-urea electrolyte EOS/activity parameter set for HP/MP/LP
  fugacity, speciation, density, heat capacity, and enthalpy.
- Replace the lumped-mass transport in 328D001, 328D003, and 323C005 with live molecular vectors.
- Replace or explicitly approve the frozen `RHO_744_KGM3`, `RHO_741_KGM3`, `R328_C002_RHO`, and
  `R328_C004_RHO` values. The PFD's hot ammonia-water densities conflict with ordinary water
  behavior, so a generic aqueous correlation is not an acceptable silent substitute.
- Replace the empirical Unit-324 evaporator VLE with a rigorous activity/fugacity model.

### C43 — Unit-328 energy and reaction closure

The compliance envelope remains 6653.8 kW in, 8344.2 kW out, residual −1690.5 kW. Close the balance
after C36 exposes carbamate reaction extents and phase enthalpies instead of embedding them in
back-solved latent terms.

### C39 — recycle tear classification and solve

Classify the one-tick tears for streams 748, 750, 775, 718A, and 931 as physical transport or
algebraic recycle. Use bounded direct substitution, Wegstein, or Broyden iteration for algebraic
tears; retain a dynamic lag only where residence-time or transport evidence exists.

## Equipment and source-data gaps

### C40 — ejector performance and gas-side pressure drop

Obtain certified suction/motive/discharge curves, critical backpressure, motive-steam dryness
corrections, breakdown/recovery hysteresis, acceptance points, and effective throat/exit/loss
geometry for 324F002/F004/F005. Also obtain F004 discharge/E006 pressure, complete gas-line
lengths/fittings/roughness, and condenser/ejector gas-side pressure drops. Until then, retain the
PFD-anchored training surrogate and shared rounded manifold pressures.

### 328D003 flashing and emissions

The approved 18/43/429 m³ communicating-compartment basis closes the physical-bay inventory gap.
Obtain plant survey data for dissolved-gas flashing and tank pressure/emissions only if those
behaviors are required for training.

### Unit 335

Obtain the matching 1,750-MTPD Unit-335 H&MB/PFD before extending the product boundary beyond the
currently mapped UF85 ratio and melt-feed interface. The available detailed PFD is for 2,000 MTPD.

## Product and repository follow-up

- Reconcile `Master_PID_Tuning_Constants.md`: 33 of 46 simulator controller settings intentionally
  differ from plant rows; Appendix A describes a mass-basis `_fic_flow` while the engine is
  volumetric, and some tags predate renames.
- Confirm the 321-1/323-1 overlay registration and FFIC-329401/TIC-328012 live-PV row assignment on a
  running HMI.
- Remove orphaned Git LFS objects and unreachable commits through repository recreation or GitHub
  Support if remote storage cleanup is still required.
