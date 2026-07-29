# Handoff: Open Gaps Only

Updated 2026-07-29. Closed/delivered work is recorded in As-Built §§22.11-22.15,
`research_plan_324_vacuum_train.md`, `research_plan_328d003_compartments.md`,
`PID_EVIDENCE_AUDIT_2026-07-27.md`, `C36_PROPERTY_BASIS_PROPOSAL.md`, and the standalone,
test-gated modules delivered on 2026-07-29:
`backend/props_nh3co2h2o.py` (+`test_props_nh3co2h2o.py`, 37/37),
`backend/reconcile_crowe.py` (+`test_reconcile_crowe.py`, 6/6),
`backend/ejector_huang.py` (+`test_ejector_huang.py`, 11/11).

The five gaps below no longer lack a *method* — every closure model named in the two owner-supplied
references (`Resolving Simulator Thermodynamics Gaps.docx`,
`Urea Simulation Gaps Resolution1.md`) is now implemented from first principles and validated against
independent anchors. What remains for each is narrowly one of two things: (a) a specific external datum
that is paywalled, vendor-proprietary, or a governance artifact and therefore cannot be sourced or
fabricated, or (b) engine integration into `main.py` (phases 2-5), which is deliberately deferred to
keep the bit-exact design pin intact until the property basis is wired in behind a flag. No property,
sink, curve, covariance, or geometry was fabricated to force a closure.

## C36 / TD-009 / TD-012 — property and species basis  [ENGINE COMPLETE; wiring + Cp rows remain]

DELIVERED — the complete Extended UNIQUAC property basis as a validated standalone module
(`backend/props_nh3co2h2o.py`), all parameters/equations transcribed verbatim from the definitive open
source (Thomsen 2005, IUPAC Pure Appl. Chem. 77, 531) and cross-checked against the Darde 2011 thesis
and the owner references:
- combinatorial + residual short-range activity (Gibbs-Duhem < 1e-9, pure/inf-dilution limits exact);
- **long-range Debye-Huckel term** `debye_huckel_ln_gamma` (A(T) eq 6, b=1.5; reproduces eqs 8/9, the
  DH limiting law, and its own Gibbs-Duhem);
- **complete activity coefficient** `activity_ln_gamma` (symmetric water / unsymmetric solutes, eqs 17-18);
- **SRK gas-phase fugacity** `srk_phi` (k_ij=0; -> ideal gas at low P, correct real-gas Z);
- **Newton speciation solver** `speciate` (R1-R5 + N/C/charge balances with full activities; closes every
  balance and reaction quotient to ~1e-14; reproduces Le Chatelier and the pH 9-11 carbamate window).

REMAINING:
1. *Engine integration (phases 2-5).* Wire the module into `main.py` behind a flag: live molecular
   vectors replacing lumped-mass transport in 328D001/328D003/323C005; explicit approval or replacement
   of the frozen `RHO_744`/`RHO_741`/`R328_C002_RHO`/`R328_C004_RHO`; and the rigorous activity/fugacity
   VLE for the Unit-324 evaporators (replacing empirical `evap_w_eq`). Must preserve the design seed.
2. *One paywalled datum.* The NH3(aq)/CO2(aq) standard-state Cp coefficients (Thomsen & Rasmussen 1999,
   3-parameter Helgeson form) gate the R2/R3/R5 constants above 25 C, `speciate` above 25 C, and the
   absolute (vs excess) stream enthalpy. Deep web research on 2026-07-29 (Plyasunov & Shock 2000;
   Thomsen & Rasmussen 1999) did not surface an open, temperature-resolved Cp usable in that form without
   fitting unpublished data, so it is left as the one documented external input — the framework is
   already parametrized on it. At 298.15 K everything runs on the sourced dGf alone.

## C34 — canonical stream graph and enthalpy  [excess machinery delivered; absolute datum blocked]

DELIVERED — the excess (mixing) enthalpy machinery `excess_enthalpy` (h^E from the temperature
derivative of the model; combinatorial part contributes exactly zero, pure-water h^E = 0), ready to
supply the composition-aware enthalpy deviation.

REMAINING — the PFD has 163 unique stream numbers vs 55 canonical runtime records; the `enthalpy_kJkg`
field is `None` on purpose. Populating it (and completing the stream graph) needs the ABSOLUTE stream
enthalpy = sensible (pure-component Cp integrals) + excess + formation. The excess and formation parts
exist now; the pure-component sensible part is blocked on the same two paywalled Cp rows as C36 item 2.
This is phase 2 of `C36_PROPERTY_BASIS_PROPOSAL.md`.

## C43 — Unit-328 energy and reaction closure  [reaction-enthalpy core delivered; wiring remains]

DELIVERED — `dH_reaction` computes the explicit standard enthalpy of reaction from formation enthalpies,
validated against textbook aqueous values (water ionization +55.8, NH4+ formation -52.2, CO2 first
ionization ~+7.6, bicarbonate ionization +14.9 kJ/mol). This is the first-principles replacement for the
back-solved latent duties.

REMAINING — map the lumped analytical NH3/CO2 mass flows into the speciated carbamate matrix inside the
Unit-328 vectors and replace the embedded latent terms with explicit xi*dH. The compliance envelope
(6653.8 kW in / 8344.2 kW out / residual -1690.5 kW) and the read-only `q328_resid` diagnostic in
`step_sim` remain the acceptance check; the audit comment there estimates the missing carbamate term at
~1096-1425 kW, consistent with unaccounted reaction enthalpy rather than a leak. Phase 4 of the proposal.

## C35 — molecular conservation / steady-state reconciliation  [engine delivered; covariance remains]

DELIVERED — the Crowe (1983) projection-matrix reconciliation engine `backend/reconcile_crowe.py`
(WLS closed form + unmeasured-variable projection + back-calculation), validated on hand-solvable
mass-balance networks (6/6).

REMAINING — certifying the Unit-324 residuals (324F004 -1.917, 324E001 -170.105, 324E003 -126.793 kg/h)
needs an APPROVED measurement-error covariance matrix Sigma (sensor precisions). Without an approved
Sigma the WLS weights are arbitrary and the reconciled vector is numerically valid but operationally
meaningless. Do not introduce a fictitious urea sink. Sigma is a governance artifact, not a web-sourceable
or derivable quantity.

## C40 — ejector performance and gas-side pressure drop  [physics core delivered; vendor data remains]

DELIVERED — the Huang (1999) 1-D compressible-flow core `backend/ejector_huang.py` (isentropic
area/Mach/pressure relations, choked-nozzle mass flux, normal-shock jump, entrainment ratio, and
critical-backpressure/breakdown assembly), validated against standard gas-dynamics tables (11/11).

REMAINING — resolving the shock position (hence the true breakdown backpressure) for 324F002/F004/F005
needs the vendor throat/exit/mixing-loss geometry and the firm downstream tie pressures (F004 discharge /
E006), plus the gas-line lengths/fittings/roughness and condenser/ejector gas-side pressure drops. These
are plant-/vendor-specific and cannot be substituted by a correlation. Until they are supplied, retain
the PFD-anchored training surrogate and shared rounded manifold pressures; the physics core is ready to
consume the geometry the moment it is available.

## Product and repository follow-up

- Confirm the 321-1/323-1 overlay registration and FFIC-329401/TIC-328012 live-PV row assignment on a
  running HMI.
- Remove orphaned Git LFS objects and unreachable commits through repository recreation or GitHub
  Support if remote storage cleanup is still required.
