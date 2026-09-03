# HPCC Steam Export and Ejector Temperature Design

**Date:** 2026-08-08
**Scope:** 322E002 LP-steam generation/export and 322F002 ejector-temperature indication

## Problem

Two operator responses are wrong or invisible:

1. Raising plant load can reduce 322E002 steam generation and FT-329407, although additional carbamate formation should release more heat. Lowering the LP-steam master setpoint works, but does not correct the bad load response.
2. Moving HP ejector hand valve HV-322602 appears to have no effect on 322E003 overflow temperature TT-322002.

The user authorized research, planning, implementation, and commit without an approval pause. That authorization satisfies the brainstorming design gate.

## Reference Basis

- The combined 1750 MTPD PFD table defines the normal 322E002 steam-export stream at 16,707 kg/h and 3.9 bara.
- `References/Stamicarbon_Steam_Condensate_Network.md` identifies 322E002 as an LP-steam generator, PV-329207B as the turbine-export valve, and FT-329407 as the exported-steam measurement.
- `References/HPCC description.md` describes exothermic carbamate formation on the tube side and nucleate boiling on the shell side. The shell temperature follows steam saturation pressure.
- Startup and operating references show that ejector suction conditions respond to ejector-valve position.

## Root Causes

### 322E002 load response

The HPCC gas outlet uses a fixed overall conductance:

```text
T_product = T_shell + (T_adiabatic - T_shell)
            * exp(-UA / (mass_flow * Cp))
```

At higher load, gas mass flow rises while `UA` remains fixed. The resulting NTU falls, product temperature rises, and the sharp flash-equilibrium response sends more CO2 to gas. Calculated net CO2 absorption then falls enough to reduce carbamate heat and shell-side steam generation. A 20% CO2-load test reduced FT-329407 from about 16.8 to 8.7 t/h after 20 minutes. Lowering the LP master setpoint alone increased FT-329407, proving the pressure/export controller path works.

### TT-322002 response

The backend ejector model already couples HV-322602 to TT-322002. Opening the valve from 50% to 95% lowered the model temperature from 178.6°C to 132.2°C over 20 minutes. The legacy 322-2 panel hides this response by rendering a constant 178.8°C instead of the live telemetry field.

## Considered Solutions

### A. Preserve calibrated HPCC NTU and bind live telemetry — selected

Scale effective HPCC conductance by current process-gas mass flow relative to the pinned design flow:

```text
UA_load = UA_design * mass_flow / mass_flow_design
UA_effective = UA_design + disturbance_gate * (UA_load - UA_design)
```

This keeps the calibrated design NTU constant during genuine load changes while the existing disturbance gate preserves the undisturbed design pin. It adds no empirical coefficient and retains the existing shell-pressure, saturation-temperature, equilibrium, and energy-balance structure. Bind the legacy TT-322002 indicator to the backend `TI_322002` field.

### B. Add a load feed-forward multiplier to steam generation — rejected

A direct multiplier could force FT-329407 upward, but would disconnect generated steam from the HPCC reaction and sensible-heat balances.

### C. Clamp flash CO2 absorption at high load — rejected

A clamp would hide the fixed-NTU defect by overriding phase-equilibrium and mass-transfer results. It would also create a nonphysical discontinuity.

## Detailed Design

### Backend

In the 322E002 gas-temperature calculation:

1. Read the pinned design process-gas mass flow.
2. Calculate flow-scaled `UA` and blend it through the existing disturbance gate.
3. Use effective `UA` in the existing exponential heat-transfer relation.
4. Keep the existing product sensible-heat correction, shell heat balance, LP-steam drum dynamics, master-pressure controller, export valve, and FT-329407 calculation.

No new state, command, alarm, or operator setting is required. The design pin remains exact because effective `UA` equals pinned `UA` at design flow.

### Frontend

Replace the constant TT-322002 panel value with `e.TI_322002`. The WebSocket payload and ejector hand-valve command path already exist and need no protocol change.

### Related regression maintenance

Update LP-header regression tests that still hardcode the former 4.4-bara absolute-pressure expectation. The current reference-correct conversion is 4 barg plus atmospheric pressure.

## Verification

- Add a full-model regression proving a plant-load increase raises 322E002 steam generation and FT-329407. Compare matched load trajectories to prove a lower LP master setpoint raises generation while export remains above design; PV-329207B may reach its physical opening limit as the turbine pressure drop falls.
- Add a UI source regression proving the TT-322002 indicator uses live telemetry and contains no fixed design value.
- Run 322E002 equation audits, LP-turbine export tests, ejector directional tests, syntax checks, and diff checks.
- Compare the normal FT-329407 point with the 16,707 kg/h PFD value within the model's existing calibration tolerance.

## Expected Data Flow

```text
Plant load -> HPCC gas flow -> UA_effective -> product temperature
           -> CO2 absorption -> reaction duty -> generated LP steam
           -> LP header/master/export valve -> FT-329407

HV-322602 -> ejector entrainment/mixing -> TT-322002 backend telemetry
          -> legacy 322-2 live indicator
```
