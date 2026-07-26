# Handoff: Open Gaps Only

Updated 2026-07-27 after reconciling the 33-page plant P&ID set with the Unit-324/328 mappings.
Closed work is recorded in As-Built §§22.11-22.12, `research_plan_324_vacuum_train.md`, and
`PID_EVIDENCE_AUDIT_2026-07-27.md`.

## Model-compliance gaps

### C34 — canonical stream graph and enthalpy

The runtime now publishes 55 canonical stream records, including every numbered stream needed by the
supplied absorber and Unit-324 cooling-water maps, but the in-scope PFD contains 163 unique stream
numbers. None of the 55 records has a calculated enthalpy. Complete the remaining
`[T, P, phase, F_i, h, rho]` graph after the thermodynamic basis in C36 is approved.

### C35 — molecular conservation versus the PFD

The strict PFD is not molecularly conservative through Unit 324. The implemented reconciliation keeps
PFD hydraulic/thermal nodes exact and preserves molecular conservation in live departures; it exposes
the mismatch instead of inventing a urea sink. Remaining design residuals are 324F004 −1.917,
324E001 −170.105, and 324E003 −126.793 kg/h. Molecular certification requires reconciled licensor
stream data or approved measurement weights/uncertainties.

### C36 / TD-009 / TD-012 — property and species basis

- No complete NH3-CO2-H2O-urea electrolyte EOS/activity parameter set is available for HP/MP/LP
  fugacity, speciation, density, heat capacity, and enthalpy.
- 328D001, 328D003, and 323C005 still transport lumped mass rather than a live molecular vector.
- `RHO_744_KGM3`, `RHO_741_KGM3`, `R328_C002_RHO`, and `R328_C004_RHO` remain frozen. The PFD's hot
  ammonia-water densities conflict with ordinary water behavior, so use licensor densities or an
  explicitly approved replacement basis; do not silently fit a generic aqueous correlation.
- The empirical Unit-324 evaporator VLE is now centralized in `evap_w_eq()`, but it is not a rigorous
  activity/fugacity model.

### C43 — Unit-328 energy and reaction closure

The compliance envelope remains 6653.8 kW in, 8344.2 kW out, residual −1690.5 kW. Hydrolysis heat is
explicit, but carbamate association/dissociation enthalpy remains embedded in back-solved latent terms.
Close this only after C36 exposes reaction extents and phase enthalpies.

### C39 — recycle tear classification and solve

Residuals and convergence status are published, but the one-tick tears for streams 748, 750, 775,
718A, and 931 are not all backed by parameterized line inventory. Classify each as physical transport
or algebraic recycle. Algebraic tears need bounded direct substitution, Wegstein, or Broyden iteration;
retain a dynamic lag only where residence/transport evidence exists.

## Equipment and source-data gaps

### C40 — ejector performance and gas-side pressure drop

The four condensers now have individual live mass, `Q`, `UA`, LMTD, cooling-water, phase-outlet, and
geometry states. P&IDs 105/1-105/2 close installed line order, destinations, nominal sizes, and minimum
vertical/barometric-leg arrangements. Still missing are the ejectors' certified
suction/motive/discharge curves, critical backpressure, dryness corrections, breakdown/recovery
hysteresis, acceptance points, and unambiguous effective throat/exit/loss geometry. F004
discharge/E006 pressure, complete pipe runs/fittings/roughness, and condenser/ejector gas-side
pressure drops are also absent. Until vendor or plant-test data arrive, retain the PFD-anchored
training surrogate and shared rounded manifold pressures.

### 328D003 physical-bay dynamics

P&ID 104 now confirms physical bays I/II/III, places LI-328507 on bay I and LI-328508 on bay III, and
shows the N23/N24 hand-valved connection between bays III and II. P&IDs 103/1-103/2 also close the
installed `323C005 -> 328V001 -> 328D003` liquid route. The two existing model inventories correspond
to physical bays I and III; the historical `Comp II` identifier is only the second mapped-inventory
alias. Physical bay II remains unmodeled because the P&ID supplies no bay capacities, baffle/weir
elevations, normal N23/N24 valve state, or separate 1,750-MTPD operating stream. Obtain the vessel
GA/mechanical drawing and operating basis before adding that inventory. Dissolved-gas flashing and
tank pressure/emissions also need plant survey data if required for training. `LT-328507/508` remain
intentional open-loop indications; no level-control valves are drawn.

### Unit 335

The plant P&ID set now supplies Unit-335 equipment, piping, valve, and instrumentation topology, but
the available detailed Unit-335 PFD is for 2000 MTPD while this simulator's target is 1750 MTPD. A
P&ID is not a quantitative heat-and-material balance. Obtain the matching 1750-MTPD H&MB/PFD before
extending the product boundary beyond the currently mapped UF85 ratio and melt-feed interface.

## Product and repository follow-up

- Reconcile `Master_PID_Tuning_Constants.md`: 33 of 46 simulator controller settings intentionally
  differ from plant rows; Appendix A still describes a mass-basis `_fic_flow` while the engine is
  volumetric, and some tags predate renames.
- Confirm the 321-1/323-1 overlay registration and FFIC-329401/TIC-328012 live-PV row assignment on a
  running HMI.
- Orphaned Git LFS objects and unreachable commits remain after the historical PDF purge; repository
  recreation or GitHub Support is required if remote storage cleanup is still desired.

## Verification state

- `test_vacuum_condenser_mapping.py` + `test_vacuum_valve_rules.py`: **13 passed**.
- Coupled regression set (`test_equation_audit_323_324.py`, `test_session_regression_gate.py`,
  `test_streams.py`, `test_full_audit_closures.py`): **25 passed**.
- Repository collection: **264 tests**. The all-suite run reached its 15-minute command limit without
  emitting a failure; record this as a timeout, not a pass.
- `audit_model_compliance.py`: **6 passed / 4 failed**. The four failures correspond to C34, C35,
  C36 enthalpy, and C43 above. Do not certify full mathematical compliance until they close.
