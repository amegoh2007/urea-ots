# Extended-UNIQUAC Full-Simulation Audit Implementation Plan

Date: 2026-07-29

## Task 1: Preserve the audit baseline

- Record the four executable compliance failures and the three unit-audit matrices.
- Add focused failing tests for each confirmed structural defect before production edits.

## Task 2: Add the common thermodynamic boundary

- Add a dependency-free binary urea-water UNIQUAC implementation from the open Voskov-Voronin supplementary source.
- Test activity-coefficient limits, material conversion, bubble residual, monotonic pressure/temperature response, and unsupported-domain errors using hand-derived expectations.
- Route Unit-324 equilibrium and bubble-temperature calls through it while retaining exact design anchors.
- Publish model provenance and nonlinear residual in diagnostics.

## Task 3: Repair Unit 321/322 conservation

- Add zero-feed and reactant-starvation tests for 322E001.
- Bound hydrolysis/biuret extents by actual Urea/H2O availability; remove componentwise reaction clipping.
- Correct NH3 battery-limit and dynamic-vessel outlet stream publication where state already exists.
- Add explicit unresolved findings for signed reactor correction, HP flash, scrubber inventory, and missing high-pressure kinetics if they cannot be closed without a larger validated model.

## Task 4: Repair Unit 323/324 connectivity

- Test live LP/9-bar header perturbations.
- Use live LP pressure for E010/E001 and live 9-bar pressure for E003.
- Correct LV324501A forward / B recycle semantics and propagate the recycle tear to 323D002.
- Replace the algebraic F010 pass-through with a conservative design-anchored hydraulic outflow.
- Remove authoritative component-strength pinning from runtime or reconcile its design input outside the ODE.
- Publish Unit-324 nonlinear iteration residual/convergence.

## Task 5: Repair Unit 329 steam/condensate balances

- Test PV329207B as LP-header export and PV329207C as make-up.
- Reverse B flow/control action; bind FT329407 to the actual B flow.
- Deduct D009 flash vapor from liquid inventory and include LV329503 inflow in the LP drum.
- Add node residual diagnostics and verify strict-source design identities.

## Task 6: Improve flowsheet and energy audit truthfulness

- Separate the strict-source PFD catalogue count from the implemented live-stream count.
- Add missing live numbered streams for touched units with real endpoints and actual component vectors.
- Do not populate absolute enthalpy when the thermodynamic datum is unsupported; change compliance checks to distinguish `unsupported with named datum` from `silently missing`.
- Replace the false recycle-convergence claim with `tear residual observed` unless an inner fixed-point solve is implemented.

## Task 7: Reconcile documentation and graph

- Update the As-Built mathematical reference and Chemical_Modelling equation mesh with confirmed equations, domains, and exceptions.
- Rewrite `handoff.md` to open gaps only; delete every closed item.
- Incrementally update graphify after code/docs changes.

## Task 8: Fast verification, review, commit

- Run only focused changed-module tests and the executable compliance audit.
- Dispatch an independent code review; resolve Critical/Important findings.
- Inspect the final diff, commit once, and report remaining open gaps without claiming unsupported rigor.
