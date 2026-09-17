# G-WASH-2: Wash-Coupling Gains Calibration

Provide a brief description of the problem, any background context, and what the change accomplishes.
The HP Scrubber (322-E-003) currently uses "engineering estimates" for the gains that couple the weak carbamate wash flow to the scrubber's absorption and thermal behaviour:
- `SCRUB_WASH_SINK_KW = 2500.0`
- `SYN_P_WASH_COLLAPSE_GAIN = 8000.0`
- `SCRUB_OFFGAS_WASH_COOLING = 15.0`
- `SCRUB_CARB_ABS_GAIN = 0.15`

These linear gains dictate the magnitude of the responses to a wash step test. We need to transition these constants to rigorous, datasheet-derived values.

## Proposed Changes

### `backend/main.py`

#### [MODIFY] main.py
- Calculate exact theoretical values for the gains using the equilibrium thermodynamics and heat balances:
  - `SCRUB_WASH_SINK_KW`: Sensible heat capacity of the wash stream between 74 C and 178.8 C.
  - `SCRUB_CARB_ABS_GAIN`: The equilibrium absorption capacity of the wash stream for CO2 at 140.7 bar and 178.8 C.
  - `SCRUB_OFFGAS_WASH_COOLING`: The thermal capacitance ratio between the offgas and the wash liquid.
  - `SYN_P_WASH_COLLAPSE_GAIN`: The volumetric condensation rate resulting from the absorption, translated to a pressure derivative.
- Replace the hardcoded numbers with these rigorously derived constants (or pre-computed constants with exact mathematical comments).

## Verification Plan
- Run `pytest` to ensure no regressions in the simulation's baseline behaviour.
- Ensure the steady-state initialization remains bit-exact (the gains only apply to deviations from `s=1.0` and `wash_scale=1.0`).
