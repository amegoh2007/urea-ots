# Architectural Refactor Design: Sequential Modular (SM) Simulator

## Goal
Transform the current Urea Simulator codebase from a monolithic tick-based explicit integration loop (`step_sim()`) into a True Sequential Modular (SM) architecture with encapsulated Thermodynamic models, rigorously enforcing MESH equations across all nodes.

## Architecture
We will implement an event-driven Object-Oriented SM architecture.
- **`Stream` Objects**: Will hold state vectors `[T, P, Mass Flow, Compositions, Enthalpy]`. They will broadcast an `is_dirty` flag whenever updated.
- **`Unit` Objects**: Will contain localized MESH (Mass, Equilibrium, Summation, Heat) solvers. They will subscribe to their input streams and re-evaluate when dirty, cascading the changes downstream.
- **Thermodynamic Package**: We will introduce a generalized `ThermoModel` interface. Initially, it will wrap the existing anchored empirical correlations (like `bubble_p_322e002`), but structured such that a rigorous Extended UNIQUAC or NRTL model can be dropped in later.

## Data Flow
1. A perturbation (e.g., feed change) updates a root `Stream`, setting `is_dirty = True`.
2. The connected `Unit` detects this, solves its MESH equations, updates its output `Stream`s.
3. This cascades through the directed graph of the plant.
4. Recycle loops will use a basic tearing mechanism (direct substitution for now).

## Error Handling & Testing
- Unit tests will verify that each `Unit` independently closes mass and energy balances to machine zero.
- Stream tests will verify that `is_dirty` triggers propagate correctly.

## Scope & Implementation Phases
- **Phase 1**: Core classes (`Stream`, `Unit`, `ThermoModel`).
- **Phase 2**: Migrate `322E003` (Scrubber) to the new SM pattern as a proof of concept.
- **Phase 3**: Migrate the rest of the synthesis loop and recycle tear convergence.
