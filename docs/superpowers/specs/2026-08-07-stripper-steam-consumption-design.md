# 322E001 Stripper Steam Consumption Correction Design

## Background
The simulator currently exhibits a non-physical behavior when the reactor overflow letdown valve (HV-322605) is opened. Opening the valve increases the mass flow of hot liquid from the 322R001 reactor to the 322E001 HP Stripper. In the real plant, feeding more liquid requires more heat, causing the steam pressure controller (PIC-329204) to open the MP steam supply valve, raising the total steam consumption (measured at FT-329403). Additionally, because the stripping process is limited by heat transfer surface area, the heavier liquid film retains more of its heat from the reactor, causing the bottom solution temperature (TT-322004) to rise towards the reactor feed temperature (~183 °C).

## The Defect
The model applies a "fixed steam duty" approximation to calculate a specific thermal efficiency penalty (`g_T`). When the liquid feed mass increases, `g_T` is heavily penalized by a steep constant (`STRIP_ETA_KT = 1.50`). This penalty forces the stripping fraction down so aggressively that the *absolute* amount of carbamate dissociated actually drops. Because the stripper's heat duty (`duty_raw_kw`) is calculated via a rigorous enthalpy balance driven primarily by the endothermic carbamate dissociation, the calculated required duty drops instead of rising. As a result, the dynamic steam header sees a *lower* duty requirement, which causes steam consumption to incorrectly drop.

## Design Changes

### 1. Re-calibrate Thermal Choke Penalty (`STRIP_ETA_KT`)
- **Current state**: `STRIP_ETA_KT = 1.50`
- **Change**: Reduce `STRIP_ETA_KT` to a much lower value (e.g., ~0.15 - 0.20) in `backend/main.py`. 
- **Effect**: During a feed surge, the stripping fraction will still drop slightly (representing heat transfer film resistance), but the absolute amount of stripped CO2/NH3 will now correctly increase, driving up the endothermic duty (`q_carb`) and increasing the total required steam heat, drawing more MP steam.

### 2. Verify and Adjust `T_bot` Surge Logic
- **Current state**: `dT_bot` is anchored to rise towards the reactor feed temperature during a flood.
- **Change**: Ensure that with the reduced `STRIP_ETA_KT` (which yields a smaller `dT_load`), the bottom temperature (`T_bot`) still noticeably rises on a feed surge as expected by the plant operators.

### 3. Verify Steam Network Response
- After correcting the stripper model, verify that the steam network propagates the increased MP steam demand correctly:
  - `PIC-329204` opens `PV-329204` to maintain MP header pressure.
  - Live BL steam flow `m_supply` increases.
  - The telemetry point `FT-329403` correctly registers the increased steam consumption.
