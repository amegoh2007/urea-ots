# Level Integrator Design (Reactor, HPCC, Scrubber & All Vessels)

## Goal
Modify the simulation logic so **all** vessel levels act as pure mass accumulators (integrators). The discharge flow of each vessel must be strictly determined by its valve/ejector opening and independent of the vessel's liquid level. Additionally, all vessels must have an "empty guard" to ensure mass is conserved when a vessel hits 0% level.

## Audit Results
I audited all level-controlled vessels in the simulation:
1. **Reactor (322R001)**: Has artificial hydraulic head term.
2. **HPCC (322E002)**: Has artificial hydraulic head term.
3. **Scrubber (322E003)**: Has artificial hydraulic head term.
4. **Stripper (322E001)**: Already a pure integrator (no head term).
5. **Flash Drum (323C003)**: Already a pure integrator.
6. **LPCC (323D001)**: Already a pure integrator.
7. **Flash Tank Condenser (323D011)**: Already a pure integrator.
8. **Comp Tanks (323D002)**: Already pure integrators.

*None of the vessels currently have an empty guard.* When they hit 0%, the level is clamped to 0%, but the outgoing mass flow remains at the valve's full capacity, mathematically violating the mass balance.

## Proposed Changes

### 1. Remove Hydraulic "Spring" from HP Loop Vessels
- **Reactor (HV-322605)**: Remove the `(max(L,0) / L_des)` multiplier from `outlet_line_outflow_kgph` in `core/reactor.py`.
- **HPCC (322E002)**: Remove the `(s.hpcc_level_pct / HPCC_LEVEL_NLL_PCT)` factor from `phi_out_hpcc` in `main.py`.
- **Scrubber Sump (322E003)**: Remove the `scrub_level_frac` multiplier from `ejector_322f001` in `main.py`.

### 2. Apply "Empty Guard" to ALL Level-Controlled Vessels
In `main.py`, for every vessel, immediately before calculating the new level `dL`, we will add a strict outflow cap:
- If `level <= 0.0` and `m_out > m_in`, then hard-cap `m_out = m_in`.
This will be applied to:
- `m_out_kgh` (Reactor)
- `phi_out_hpcc` (HPCC)
- `ej["suction_kgh"]` (Scrubber)
- `drain_kgh` (Stripper)
- `drain_323_kgh` (Flash Drum 323C003)
- `m_liq_out` (LPCC 323D001)
- `m_liq_out` (Flash Condenser 323D011)

## Verification
- We will use `debug_hv605.py` to open `HV-322605` for a few steps, then return it to its original position.
- **Success Criteria:** The reactor level should fall while the valve is open, and when the valve closes back to its original position, the level should remain flat at the new lower value (it should not climb back up).
- If the valve is left open, the level will drop to 0% and stop, and the outflow will exactly match the inflow, preventing negative mass.
