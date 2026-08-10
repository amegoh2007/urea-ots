# Closed Tempering Loop Thermodynamic Cascade Design

## Objective
Model the paradoxical behavior in the HP Scrubber's conditioning cooling water (CCW) loop where increasing manual circulation flow without increasing tempering cooling capacity causes the entire closed loop to heat up, triggering a series of process deviations.

## Observations to Model
1. **CCW Inlet Temp Increases**: The tempering cooler becomes a bottleneck at higher flows.
2. **CCW Outlet Temp Increases**: The entire loop reaches a hotter equilibrium.
3. **Overflow Line Level Decreases**: Reduced condensation leaves less liquid to spill over.
4. **Overflow Line Temp Increases**: Pool runs hotter due to reduced cooling.
5. **Vent Line Temp Increases**: Hotter internal environment means gases reject less sensible heat.
6. **Synthesis Pressure Increases**: Less condensation leaves more mass in the vapor phase.
7. **NH3 Line to HPCC Temp Increases**: Ejector pulls a hotter suction stream from the overflow pool.

## Root Cause Analysis & Proposed Fixes
The existing model suffered from two design simplifications that broke this cascade:
1. **Asymmetric CW Temperature Response**: The `cw_dt_dev` calculations for condensation duty (`q_ccw_kw`), absorption (`d_co2`), and vent gas temperature (`t_offgas`) used a `max(cw_dt_dev, 0.0)` floor. This meant they correctly modeled the benefits of *colder* CW, but completely ignored the penalties of *hotter* CW.
   * **Fix**: Remove the `max(..., 0.0)` floors. A negative `cw_dt_dev` (hotter CW) will mathematically reduce condensation and absorption, and raise the vent temperature (Observations 3, 4, 5, and 6).
2. **Flow-Independent Tempering Cooler**: The steady-state temperature out of the tempering cooler (`T_ss`) was computed as an offset from the design constant `SCRUB_CCW_T_OUT_DES`, entirely decoupling it from the actual return temperature out of the scrubber. It also did not penalize the cooler's effectiveness at higher flows.
   * **Fix**: Model `T_ss` using the actual lagged return temperature (`t_ccw_out_prior = s.tlag.get("TT329125", SCRUB_CCW_T_OUT_DES)`).
   * Define the cooling delta-T as proportional to the LMTD driving force against the main CW (assumed 30 C) and inversely proportional to `flow_ratio ** 1.5` to strongly model the residence time penalty in the tempering exchanger.
   * This guarantees that at higher flows, the cooler sheds less heat than the scrubber adds until a new, much hotter equilibrium is reached (Observations 1 and 2).

The HP Ejector mixing logic is already dynamically sound; feeding it a hotter overflow pool will naturally yield a hotter discharge (Observation 7).

## Execution Plan
1. Edit `backend/main.py` -> `_scrub_thermo`: Remove the zero-floors on `cw_dt_dev` in `d_co2_cw`, `q_ccw_kw`, and `t_offgas`.
2. Edit `backend/main.py` -> `step_sim`: Update `T_ss` to explicitly model the cooler bottleneck and thermodynamic feedback loop.
3. Run `python -m pytest` to verify the syntax and that the design anchors haven't broken.
4. Commit immediately.
