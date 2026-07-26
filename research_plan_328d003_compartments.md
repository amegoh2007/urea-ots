# 328D003 approved compartment basis and implementation plan

Date: 2026-07-27

## Approved design basis

The owner-supplied values below supersede the theoretical 561 m3 and 50/30/20 allocation previously
used by the simulator and secondary notes:

| Physical compartment | Approved capacity | Process role used by the model |
|---|---:|---|
| 1 | 18 m3 | Unit-324 condensate collection and 322P002 absorber-feed suction |
| 2 | 43 m3 | 323C005/328V001 return and 328P003 desorber-feed suction |
| 3 | 429 m3 | Common accumulation/surge compartment for compartments 1 and 2 |
| **Total** | **490 m3** | Communicating liquid inventory |

All three compartments have openings between them. Compartment 3 therefore receives the net
inventory imbalance of the two smaller process compartments. The mapping sources continue to govern
which external stream belongs to compartment 1 or 2; the new approved information governs physical
capacity and internal communication.

## Alternatives considered

1. Retain the old two-inventory model: rejected because it omits an approved physical compartment.
2. Treat the old second model inventory as physical compartment 3: rejected because the absorber map
   explicitly routes stream 343 to the second compartment and the approved role makes compartment 3
   the accumulator.
3. Add compartment 3 as an isolated inventory: rejected because it contradicts the approved openings.
4. Use orifice equations between bays: rejected because opening areas and elevations are unavailable.
5. Use overflow-only transfers: rejected because it would invent unprovided weir elevations.
6. Use algebraic equal-head redistribution: selected. It is parameter-free, conserves mass, and assigns
   429/490 of every net inventory disturbance to the accumulation compartment.

The reduced model keeps separate compartment-1 and compartment-2 process temperatures. Internal
transfer energy is moved at the donor compartment temperature, so redistribution conserves the
three-compartment sensible-energy inventory without assuming instant thermal homogenization.

## Verification strategy

```yaml
artifact: backend/main.py 328D003 communicating-compartment state
rationale: High-criticality process inventory change; mass, energy, mapping, and telemetry must remain auditable.
criticality: HIGH
selected_levels:
  unit:
    justification: Pure redistribution helper can prove capacity ratios and conservation directly.
  integration:
    justification: A real simulation tick must expose all three physical inventories and correct LI tags.
rejected_levels:
  component:
    justification: No isolated UI component changes are required.
  contract:
    justification: Runtime packet assertions cover the local telemetry contract.
  e2e:
    justification: Browser workflow adds no evidence for the inventory equations.
  smoke:
    justification: Stronger focused and regression tests already exercise startup.
property_based:
  status: on
  properties:
    - Total mass is invariant under internal redistribution.
    - Final level fraction is equal in all three communicating compartments.
    - Sensible-energy inventory is invariant under internal redistribution.
    - Equal-temperature inputs retain that temperature.
  framework: deterministic pytest parameter sweep (no new runtime dependency)
mutation_testing:
  status: off
  reason: No mutation framework is configured; explicit conservation assertions target the arithmetic mutations.
assertion_count_target: 20
cases:
  - requirement: Approved capacities replace the theoretical allocation.
    level: unit
    assertion: Constants are 18, 43, and 429 m3 and sum to 490 m3.
  - requirement: Compartment 3 is the accumulation baffle.
    level: unit
    assertion: A disturbance is redistributed in the 18:43:429 capacity ratio.
  - requirement: Openings communicate the three inventories.
    level: property
    assertion: Final mass/full-mass ratios match for varied positive inventories.
  - requirement: Internal communication creates no material or sensible energy.
    level: property
    assertion: Total mass and sum(mass*temperature) close within floating-point tolerance.
  - requirement: Physical instrument placement remains explicit.
    level: integration
    assertion: LI-328507 reports compartment 1 and LI-328508 reports accumulation compartment 3.
  - requirement: Design startup remains pinned.
    level: integration
    assertion: Initial levels are 50 percent and mapped design streams retain their PFD values.
```

## Execution sequence

1. Add failing focused tests for the approved constants, communicating-volume invariants, state, and
   telemetry.
2. Replace the theoretical capacities and add compartment-3 mass and temperature state.
3. Redistribute the post-process inventory through a conservative communicating-baffle helper.
4. Correct the 328D003 map, evidence audit, as-built reference, and open-gap handoff.
5. Run focused tests, the full backend suite, syntax checks, and inspect the final diff before commit.
