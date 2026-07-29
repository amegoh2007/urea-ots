# Handoff: Open Gaps Only

Updated 2026-07-29. Closed work is recorded in As-Built §§22.11-22.14,
`research_plan_324_vacuum_train.md`, `research_plan_328d003_compartments.md`,
`PID_EVIDENCE_AUDIT_2026-07-27.md`, and — for the C39 tear classification and the
Master_PID tag reconciliation closed on 2026-07-29 — As-Built §22.14 with
`backend/test_c39_recycle_tears.py` and Appendix A of `Master_PID_Tuning_Constants.md`.

The C34/C35/C36/C43 gaps below are ONE coupled cluster that all need the electrolyte property/
speciation/enthalpy basis. `C36_PROPERTY_BASIS_PROPOSAL.md` (2026-07-29) is the sourced, cited,
approvable path for that basis; on approval it closes C36, then C34 and C43 in dependency order.
No property, sink, or curve was fabricated to force closure. The owner-supplied
`References/Resolving Simulator Thermodynamics Gaps.docx` independently corroborates the whole model
selection (Extended UNIQUAC / Gorlovskii-Kucheryavyi / Huang / Crowe) and its Table 1 `r,q` values
match `props_nh3co2h2o.py` exactly — a second-source check now locked by a test.

**Phase 1 + the short-range activity term are delivered** (`backend/props_nh3co2h2o.py` +
`test_props_nh3co2h2o.py`, 18/18 pass): the Extended UNIQUAC parameter matrix
(Darde 2011 / Thomsen 1997 / CODATA / Rumpf-Maurer) is transcribed verbatim (cross-checked vs the
document), the standard-state thermodynamics are validated against textbook pKw(T)/pKa1/pKa2(T)/
pKa(NH4+)/Cp/Henry data, and the UNIQUAC combinatorial + residual short-range activity coefficients
are validated for thermodynamic consistency (Gibbs-Duhem < 1e-9, pure-limit = 0, infinite-dilution
limits exact). Standalone — not yet wired into the engine. Remaining to finish C36: source the
NH3(aq)/CO2(aq) Cp coefficients (Thomsen & Rasmussen 1999); complete phase 1b (the Debye-Hückel
long-range term + Newton speciation + SRK-VLE solver); then phases 2-5 (engine integration).

## Model-compliance gaps

### C34 — canonical stream graph and enthalpy

The in-scope PFD contains 163 unique stream numbers, while the runtime publishes 55 canonical stream
records. Complete the remaining stream graph with calculated `[T, P, phase, F_i, h, rho]` records
after the C36 thermodynamic basis is approved. None of the current records has calculated enthalpy;
the records already carry an `enthalpy_kJkg` field left `None` on purpose (no partial/misleading
property). It is populated in phase 2 of `C36_PROPERTY_BASIS_PROPOSAL.md`, once the enthalpy datum
(sensible + excess + formation) exists.

### C35 — molecular conservation versus the PFD

Unreconciled Unit-324 design residuals remain: 324F004 −1.917, 324E001 −170.105, and 324E003
−126.793 kg/h. Molecular certification requires reconciled licensor stream data or approved
measurement weights and uncertainties; do not introduce a fictitious urea sink.

### C36 / TD-009 / TD-012 — property and species basis

Sourced approvable path now written up in `C36_PROPERTY_BASIS_PROPOSAL.md` (2026-07-29). It recommends
the **Darde–Thomsen Extended UNIQUAC** basis (valid 0–150 °C / 1–100 bar, covering every LP unit here)
and gives the phased, design-pin-preserving integration plan for C36 → C34 → C43. The one decision it
turns on is approving the Extended UNIQUAC interaction-parameter matrix from Darde et al. (2010). The
proposal also records what is already cited-and-addressed so it is not re-litigated:

- Density *slopes* already come from IAPWS/Wagner-Pruss (`aqueous_rho`), and the frozen anchors 933.0 /
  923.28 are proven physical (±0.6 % of water) with the "impossible" 908.5/897.7 values never used.
- The carbamate/urea/NH3 reaction enthalpies (Frejacques/Brouwer 117 / 15.5 / 23 kJ/mol) are already
  cited and validated in the stripper and are the recommended set for the C43 rework.

Still open (needs the approval above, then implementation): a complete electrolyte activity/speciation
basis; live molecular vectors replacing lumped-mass transport in 328D001/328D003/323C005; explicit
approval or replacement of the frozen `RHO_744`/`RHO_741`/`R328_C002_RHO`/`R328_C004_RHO`; and a
rigorous activity/fugacity VLE for the Unit-324 evaporators (replacing empirical `evap_w_eq`).

### C43 — Unit-328 energy and reaction closure

The compliance envelope remains 6653.8 kW in, 8344.2 kW out, residual −1690.5 kW. Close the balance
after C36 exposes carbamate reaction extents and phase enthalpies instead of embedding them in
back-solved latent terms. (The `q328_resid` diagnostic in `step_sim` already measures this residual
every tick; it is read-only until the explicit-ξ·ΔH rework lands.) This is phase 4 of
`C36_PROPERTY_BASIS_PROPOSAL.md`, using the already-cited Frejacques/Brouwer enthalpies; the audit
comment at `step_sim` estimates the missing carbamate term at ~1096–1425 kW, consistent with the
residual being unaccounted reaction enthalpy rather than a leak.

## Equipment and source-data gaps

### C40 — ejector performance and gas-side pressure drop

Obtain certified suction/motive/discharge curves, critical backpressure, motive-steam dryness
corrections, breakdown/recovery hysteresis, acceptance points, and effective throat/exit/loss
geometry for 324F002/F004/F005. Also obtain F004 discharge/E006 pressure, complete gas-line
lengths/fittings/roughness, and condenser/ejector gas-side pressure drops. Until then, retain the
PFD-anchored training surrogate and shared rounded manifold pressures.

## Product and repository follow-up

- Confirm the 321-1/323-1 overlay registration and FFIC-329401/TIC-328012 live-PV row assignment on a
  running HMI.
- Remove orphaned Git LFS objects and unreachable commits through repository recreation or GitHub
  Support if remote storage cleanup is still required.
