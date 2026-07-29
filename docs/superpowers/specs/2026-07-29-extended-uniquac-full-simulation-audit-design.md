# Extended-UNIQUAC Full-Simulation Audit Design

Date: 2026-07-29

## Objective

Audit every implemented unit against the strict 1750 MTPD PFD source, repair every defect that can be closed without invented plant data, route process-mixture phase equilibrium through a common Extended-UNIQUAC thermodynamic boundary, and leave only evidence-backed external-data gaps in `handoff.md`.

## Evidence and constraints

- The executable baseline has four failures: 55/163 canonical streams, 0/55 stream enthalpies, nonzero Unit-323/324 component residuals, and a -1690.5 kW Unit-328 energy residual.
- The active runtime does not import the delivered Extended-UNIQUAC package.
- Primary literature requires a gamma-phi formulation: Extended/modified UNIQUAC for the liquid, an EOS for vapor fugacity, MESH equations per equilibrium stage, and explicit chemical-equilibrium/kinetic terms. Pure steam remains an IAPWS property problem; calling it UNIQUAC would be physically wrong.
- The open Voskov-Voronin supplementary source provides a reproducible UNIQUAC urea-water interaction pair and high-pressure NH3-CO2-H2O-urea parameter set. For neutral urea-water, the Debye-Huckel contribution is identically zero, so Extended UNIQUAC reduces to ordinary UNIQUAC.
- Existing PFD rows are rounded. Where reconciliation is needed, rounding resolution is a source-derived Type-B uncertainty; it is not a substitute for an approved online-sensor covariance matrix.
- No vendor ejector geometry, undocumented valve Cv, exchanger geometry, aqueous NH3/CO2 off-temperature standard-state heat capacity, or Unit-335 equipment data will be fabricated.

## Audit verdict by subsystem

### Units 321/322

The pump/tank scalar balances exist, but stream publication confuses battery-limit import with pump suction. The stripper reaction extent is not reactant-bounded and can generate product from an empty feed. The HPCC, reactor, and scrubber use empirical or pinned phase splits; the reactor contains a signed correction vector rather than a physical stream; scrubber outputs do not close a perturbed feed; vessel scalar inventories are not paired with component holdups. These are model defects, not documentation gaps.

### Units 323/324/335 boundary

Mass, species, and energy states exist, but Unit-324 phase equilibrium is empirical, composition pinning introduces explicit component residuals, F010 has an algebraically dead level balance, E003 heats from the wrong header, A/B product routing is reversed, the documented recycle is disabled, and vacuum pressure does not consume the live condenser result. Unit 335 is only a boundary.

### Units 328/329 and utilities

Hydrolysis kinetics and several scalar balances exist. The train still uses back-solved latent heats instead of a common enthalpy interface, leaving -1690.5 kW unclosed. The LP turbine valve is reversed, two condensate inventory terms are missing, steam users are incomplete, and the reported recycle metric observes one-tick tears rather than solving them.

### Flowsheet registry

The registry is a telemetry subset, not a canonical flowsheet: numbered process streams, endpoints, live outlet vectors, and enthalpies are missing. A complete 163-stream live model cannot be honestly synthesized from stream tables alone because many endpoints/equipment details are absent or contradictory. The repair therefore separates `implemented live streams` from `strict-source design catalogue` and never labels an unresolved design row as a live connected stream.

## Chosen architecture

### 1. Common thermodynamic boundary

Add `thermo_extended_uniquac.py` with explicit regimes:

- `UREA_WATER`: binary UNIQUAC liquid activity plus water fugacity/VLE, using published open parameters. This replaces Fahmy-Nassar and ideal Raoult closures in Unit 324.
- `NH3_CO2_H2O_ELECTROLYTE`: the existing Darde/Thomsen Extended-UNIQUAC activity, speciation, and SRK vapor fugacity package within its validated range.
- `UREA_SYNTHESIS_HP`: a published high-pressure UNIQUAC parameter set and chemical-equilibrium residual interface. It may be used only inside its stated range; unsupported absolute enthalpy fails explicitly.
- `PURE_WATER_STEAM`: the current bounded Antoine pure-water calculation, recorded as a thermodynamic exception rather than misrepresented as UNIQUAC; IAPWS-IF97 replacement and validation remain an explicit gap.

Every phase-equilibrium call carries model name, validity status, and residual. Design anchors may preserve the licensor point, but off-design slopes must come from the selected thermodynamic model.

### 2. Conservative unit equations

Fix structural conservation defects before adding fidelity:

- bound reaction extents by available reactants and remove post-reaction clipping;
- publish actual vessel outlet streams, not gross make streams;
- use independent hydraulic outflow for dynamic holdups;
- correct steam-header directions and all missing condensate terms;
- correct Unit-324 header and A/B routing;
- expose nonlinear-solver residuals and convergence.

### 3. Reconciliation boundary

Never force a measured PFD point with component pinning. For rounded design rows, reconcile only inside a dedicated design-data layer with a covariance derived from the documented rounding interval (`variance = resolution^2 / 12`). Runtime component ODEs remain conservative. Approved sensor covariance remains required for operational certification.

### 4. Stream and equation manifests

Maintain two distinct artifacts:

- a strict-source design catalogue containing every in-scope numbered PFD row and its reported state;
- a live registry containing only implemented, connected streams with actual upstream/downstream equality.

Add an equation-coverage manifest per unit: total/component/energy/phase-equilibrium/summation/kinetics/heat-transfer/momentum/connectivity. A missing category must be either implemented or carried to `handoff.md` with its exact missing datum.

## Verification

Use narrow deterministic tests first:

1. property-model hand checks and design-point VLE anchors;
2. zero/starved-feed reaction conservation;
3. steam valve direction and per-drum inventory identities;
4. live-header perturbation propagation;
5. stream endpoint/component equality;
6. executable compliance audit.

The final verification is the smallest focused pytest set covering changed modules plus `audit_model_compliance.py`; no slow full-envelope sweep is required for this commit.

## Honest completion boundary

This change can close empirical Unit-324 VLE, reactant-free material generation, reversed/missing utility flows, wrong steam-header propagation, routing defects, and audit/documentation gaps. It cannot certify rigorous off-temperature NH3-CO2-H2O absolute enthalpy, replace every HP empirical split without validated high-pressure parameters beyond the published range, construct vendor ejector momentum models, or invent missing Unit-335 equipment. Those remain in `handoff.md` only if still open after implementation.
