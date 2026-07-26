# Research plan: unit 324 vacuum train and absorber mapping

Date: 2026-07-26

## Objective

Close the open 324E002, 324E005, 324E006, and 324E007 gaps; map every stream named in the supplied absorber and cooling-water notes; correct the connected 323C005/328D003 topology; and preserve every unresolved source-data limit in `handoff.md`.

## Evidence order

1. Use `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md` for the 1,750 MTPD operating point.
2. Use the four equipment datasheets for construction, geometry, nozzle service, and mechanical limits. Their process cases do not replace the PFD: 324E002 and 324E005 describe older vendor loads, and 324E006/E007 leave process data blank and refer to 324F004.
3. Use the supplied mapping notes for equipment connectivity.
4. Use primary literature only for model form. The DOE heat-exchanger handbook supports `Q = UA ΔT_lm`; NASA condensation work supports an explicit noncondensable-gas derating; Crowe's data-reconciliation paper supports retaining measured anchors while exposing reconciliation residuals.

Primary sources:

- U.S. Department of Energy, *DOE Fundamentals Handbook: Heat Exchangers*: https://www.energy.gov/sites/default/files/2026-04/DOE-HDBK-1012-92_VOL2.pdf
- NASA, *Effects of Non-Condensable Gas on Condensation*: https://ntrs.nasa.gov/api/citations/20250005911/downloads/SCW-May2025-ZBOT-NC_CFD-PAPER-V7-6-5-2025.pdf
- Crowe, *Reconciliation of Process Flow Rates by Matrix Projection*: https://aiche.onlinelibrary.wiley.com/doi/pdfdirect/10.1002/aic.690290602

## Resolved topology

The supplied absorber map and PFD totals resolve a previous topology error:

- 323C005 receives 756, 702, and 708. At design, `33,358 + 440 + 462 = 34,180 + 80 kg/h`, which closes exactly as streams 343 and 341.
- 328D003 Compartment I receives 719, 720, 721, and 759 and supplies 744 to 322P002. The PFD has a 1 kg/h rounding residual: `31,479 in` versus `31,478 out`.
- 322P002 and 322E006 turn 744 into 755 without changing mass.
- 328D003 Compartment II receives 343 and supplies 735, 734, and 791. The PFD has a 2 kg/h rounding residual: `34,180 in` versus `34,182 out`.
- Stream 702 is the 323D011 gas outlet to 323C005. It is not an inlet to 323E011. The corrected 323E011 node closes exactly: `701 + 786 + 321 + 791 = 718 + 702 = 7,563 kg/h`.

## Vacuum-train stream map

| Node | Inlet | Condensate | Gas outlet | Cooling water |
| --- | --- | --- | --- | --- |
| 324E002 | 703 = 705 + 790 | 719 | 706 | 1014 -> 1015 |
| 324F002 | 706 + motive 924 | — | 708 to 323C005 | — |
| 324E005 | 709 | 720 | 712 | 1016 -> 1017 |
| 324F004 | 712 + motive 927 | — | 714 | — |
| 324E006 | 714 | 721 | 715 | 1018 -> 1019 |
| 324F005 | 715 + motive 929 | — | 717 | — |
| 324E007 | 717 | 759 | 722 to atmosphere | 1020 -> 1021 |

At the PFD point, each condenser and ejector node closes exactly. The 705 + 790 mixing row differs from 703 by 1 kg/h because the PFD rounds stream totals independently; the model will publish this residual and will not invent a sink.

## Thermal model

Each condenser becomes a distinct stateful node. The reduced model uses:

- `Q = UA_eff ΔT_lm`;
- a counter-current LMTD from the PFD hot- and cooling-water terminal temperatures;
- an effective design `UA = Q_PFD / ΔT_lm,PFD`, derived from measured PFD duty and temperatures;
- a cooling-water energy balance, `T_cw,out = T_cw,in + 3600 Q/(m_cw Cp)`;
- a PFD-derived effective condensation enthalpy, `h_eff = 3600 Q_PFD/m_cond,PFD`;
- a bounded noncondensable derating normalized to one at the design gas fraction.

This approach reproduces the PFD exactly without inventing a film coefficient. The datasheet surface areas and tube geometry remain metadata. A rigorous multicomponent film-condensation correlation remains open because the available documents do not provide the required mixture-transfer coefficients or vendor performance curves.

## Data-reconciliation decision

Total-flow and thermal anchors govern the hydraulic model because every condenser and ejector node closes at the PFD point. The published component percentages do not conserve molecular species across the evaporation train. The implementation will keep PFD compositions in canonical stream records and publish component residuals; it will not add fictitious reactions or sinks. This closes the old hydraulic blocker while preserving the molecular-speciation gap.

## Execution sequence

1. Add failing tests for LMTD, four-node design closure, cooling-water energy closure, noncondensable derating, numerical stream aliases, corrected 323E011/C005/D003 topology, and zero-flow boundaries.
2. Implement the reusable condenser calculation and PFD-backed constants.
3. Route 703/706/708/709/712/714/715/717/719/720/721/722/759 and 924/927/929 through the four nodes.
4. Correct the 323C005, 323D011, 322C001, and 328D003 tears without hiding the 1–2 kg/h PFD rounding residuals.
5. Add cooling-water and absorber stream-number aliases to `STREAMS`.
6. Run focused tests, conservation audits, the backend suite, and startup/disturbance checks.
7. Update the As-Built model reference and replace `handoff.md` with open gaps only.

## Test strategy

```yaml
test_strategy:
  criticality: high
  selected_levels:
    - unit
    - integration
    - system
  selected_types:
    - positive
    - negative
    - boundary
    - error-handling
    - regression
    - state-transition
  rejected:
    - level: acceptance
      reason: No external operator acceptance contract exists for this backend-only correction.
    - type: exploratory
      reason: Deterministic PFD anchors and conservation invariants define the required behavior.
    - type: property-based
      reason: The reduced model is valid only inside a bounded process envelope; deterministic boundary sweeps cover that envelope without implying unsupported extrapolation.
  gates:
    security: off
    concurrency: off
    external_dependencies: off
    destructive_operations: off
    user_input: off
    numerical_domain: on
  edge_cases:
    - equal LMTD terminal differences
    - nonpositive temperature approach
    - zero cooling-water flow
    - cooling-water flow below design
    - noncondensable load above design
    - condenser duty above available condensable mass
    - one-tick tear initialization
    - independently rounded PFD totals
  quality_budget:
    selected_tests: 14
    max_tests: 18
```

## Completion gates

- All four condensers expose individual duty, UA, LMTD, cooling-water flow and temperatures, condensate, gas outlet, and closure residual.
- Streams 708, 714, and 717 equal suction plus motive steam at the PFD point.
- 323C005 and 323E011 close to machine precision at the PFD point.
- 328D003 exposes, rather than hides, its PFD rounding residuals.
- The design snapshot matches the PFD flow, temperature, pressure, and cooling-water anchors within display precision.
- No existing test regresses.

## Execution record

Implemented on 2026-07-26:

- Replaced the aggregate vacuum sink with four explicit condenser nodes and three conservative ejector mixers.
- Applied the PFD operating case to mass, temperature, pressure, duty, and cooling-water anchors; applied the four datasheets only to geometry and mechanical metadata.
- Corrected false-air flows to streams 784/783 = 21/21 kg/h and pressure pull to the post-condenser gas load.
- Mapped the absorber train as 744 -> 755 -> 756 -> 343, with gas feeds 702 and 708 and atmospheric vent 341.
- Mapped cooling-water branches 1014/1015, 1016/1017, 1018/1019, and 1020/1021, plus headers 1001/1051.
- Corrected 323E011 so stream 702 is its gas outlet, not an inlet, and corrected 328D003 Compartment I/II routing.
- Published all mapped numerical streams as canonical runtime aliases with PFD component records.

At the direct PFD point, all four exchangers have zero mass and cooling-water energy residual. The independently rounded stream-703 mixer remains visible as a 1 kg/h PFD residual. The PFD duties are 18.459, 1.926, 1.207, and 0.133 MW; the supplied cooling-water note labels these values as kW, but its flows and temperature rises prove the intended unit is MW.

## Research decisions for remaining gaps

1. The heat-transfer implementation uses the standard counter-current LMTD relation and `Q = UA*LMTD`, consistent with the [DOE Heat Exchangers handbook](https://www.energy.gov/sites/default/files/2026-04/DOE-HDBK-1012-92_VOL2.pdf). Single-point UA is an anchored training model, not a fouling/rating guarantee.
2. Noncondensable loading reduces effective condensation because diffusion and partial-pressure effects form a gas-side resistance; the qualitative direction is supported by [NASA's condensation study with noncondensable gas](https://ntrs.nasa.gov/api/citations/20250005911/downloads/SCW-May2025-ZBOT-NC_CFD-PAPER-V7-6-5-2025.pdf). The model uses a parameter-free departure normalized to unity at design because no plant off-design curve is available.
3. The Unit-324 PFD rows are not molecularly conservative. The adopted solution is constrained data reconciliation: preserve exact measured/topological mass and thermal nodes while retaining the engine's molecular conservation, and expose the residual instead of inventing a urea sink. This follows the conservation-constrained weighted-reconciliation method established by [Crowe et al.](https://aiche.onlinelibrary.wiley.com/doi/pdfdirect/10.1002/aic.690290602). Molecular certification remains open until the licensor thermodynamic/speciation basis is supplied.
4. No defensible public source closes the NH3-CO2-H2O-urea electrolyte property package, carbamate reaction enthalpy across the full pressure range, ejector break/recovery curves, or effective throat/loss coefficients. These remain evidence-blocked; generic correlations would add false precision.
5. The three apparent Unit-324 VLE paths now share `evap_w_eq()` for the evaporators. A rigorous fugacity/activity model remains part of the missing property package, not a second empirical patch.
6. One-tick recycle tears remain numerical wherever no physical line inventory is parameterized. They require classification and bounded algebraic iteration; only explicitly lagged transport paths can be treated as physical dynamic tears.
