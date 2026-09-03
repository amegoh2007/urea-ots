# Scenario Coverage and Startup Stability

**Date:** 2026-08-11
**Scope:** `References/scenarios/Scenarios.md`, `Scenarios2.md`, `Scenarios3.md`, and fresh program initialization

## Goal

Make every documented process deviation produce the correct causal direction, downstream propagation,
and recoverable dynamic response. Start each fresh process at the PFD design state without false alarms
or material drift during the first ten simulated minutes.

## Evidence and thermodynamic selection

Use thermodynamics by operating region:

- HP synthesis, 135-230 °C and 35-450 bar: use the Voskov-Voronin urea-equilibrium model and its
  published N/C and H/C definitions. Its liquid model is UNIQUAC with urea, ammonium carbamate, and
  ammonium bicarbonate; its gas model is a virial EOS. The OTS uses its published conversion
  correlation, normalized at the PFD design state.
- HP unit-operation validation: Zhang et al. support extended electrolyte UNIQUAC for the liquid and
  a perturbed-hard-sphere EOS for gas fugacity. A full port requires plant-specific parameters and is
  outside this task; the real-time OTS retains its component-closing reduced units.
- LP absorption, rectification, and desorption, 0-150 °C: use Darde's Extended UNIQUAC
  NH3-CO2-H2O electrolyte model. Urea and biuret remain nonvolatile diluents where their interaction
  parameters are unavailable. Preserve PFD values through departure anchoring.
- Urea-water vacuum evaporation: use the neutral H2O/urea UNIQUAC limit for water activity and
  IAPWS-IF97 Region 4 for pure-water saturation. Mark this application as design-anchored
  extrapolation because the source's full urea model was fitted in the HP range.
- Steam and condensate: use IAPWS-IF97.

Selected sources:

- Voskov and Voronin, *Thermodynamic Model of the Urea Synthesis Process*,
  https://doi.org/10.1021/acs.jced.6b00557
- Zhang et al., *Modeling and simulation of high-pressure urea synthesis loop*,
  https://doi.org/10.1016/j.compchemeng.2004.10.004
- Darde et al., *Modeling of Carbon Dioxide Absorption by Aqueous Ammonia Solutions Using the
  Extended UNIQUAC Model*, https://doi.org/10.1021/ie1009519
- IAPWS, *Industrial Formulation 1997*, https://iapws.org/relguide/IF97-Rev.pdf

## Approaches considered

### 1. Zoned thermodynamics and anchored dynamics — selected

Keep each model inside its defensible process region. Use component, energy, pressure, and inventory
balances for propagation. Add scenario tests at unit boundaries and a full-flowsheet startup test.
This gives causal OTS behavior without pretending one incomplete parameter set covers the plant.

### 2. One rigorous electrolyte EOS across the plant

This would support redesign work, but the repository lacks validated quaternary interaction
parameters, absorber geometry, and vendor ejector curves. Runtime cost also conflicts with 0.1 s OTS
ticks. Reject for this task.

### 3. PFD-only empirical response curves

This would run quickly and hold the design point, but it would not conserve components or extrapolate
reliably. Reject except for documented design anchors where source data are incomplete.

## Scenario architecture

Use existing manipulated variables and inventories. Do not add scenario-specific state assignments.
Each deviation must act through a shared physical law:

- level: vessel mass balance, liquid seal, Souders-Brown entrainment, NPSH;
- pressure and vacuum: gas inventory, condensation, ejector pull, false-air ingress;
- heat: `Q = UA ΔT`, phase equilibrium, latent load, and thermal holdup;
- absorption and recycle: finite component capacity, solvent flow, and transport lag;
- reactions: equilibrium conversion, Arrhenius biuret formation, and hydrolysis inhibition;
- crystallization: composition-dependent urea/carbamate saturation and a continuous mushy-flow zone.

## Coverage contract

### HP synthesis and recovery

- Reactor high level causes liquid carryover, scrubber flooding/cooling, higher downstream load, and
  pressure escalation. Reactor low level causes seal loss, gas blow-through, lower residence-time
  conversion, pressure loss, and heavier recycle.
- Scrubber vent opening lowers pressure and raises hot-gas/condensation load. Ejector restriction,
  recycle wash, and tempered-water changes move sump level, absorption, temperatures, and pressure in
  the directions stated by `Scenarios2.md`.
- Stripper steam, level, and level-valve steps move stripping efficiency, bottoms temperature,
  HPCC vapor load, LP load, corrosion, erosion, and seal-loss flags causally.
- Reactor downcomer steps and passivation-air loss propagate through stripper, HPCC, scrubber, and LP
  absorber balances.

### LP recovery and wastewater

- LPCC solvent, level, pressure, cooling, reflux, and lean-carbamate pump changes move absorption,
  vent load, crystallization margin, NPSH, recycle H/C, and reactor conversion.
- Rectifier pressure, steam, level, and drain-valve changes move separation, carryover, downstream feed,
  vacuum load, and crystallization risk.
- Reflux condenser and flash-condenser solvent, level, pressure, and lean-carbamate changes move
  absorption, venting, upstream backpressure, pump NPSH, and wastewater load.
- Desorber/hydrolyzer feed and steam changes move residence time, column load, NH3 stripping,
  hydrolysis conversion, reflux-condenser load, and final NH3/urea slip.

### Evaporation, vacuum, and storage

- Atmospheric flash-tank level, heat, pressure, and temperature changes move carryover, vacuum,
  downstream temperature, biuret, crystallization, and pump NPSH.
- Both vacuum stages respond to steam, pressure, temperature, and level through continuous VLE,
  energy balance, gas inventory, entrainment, crystallization, and hydraulic-seal laws.
- Ammonia-water and urea-solution tank level and temperature changes move overflow, pump NPSH,
  ammonia flashing, biuret, crystallization, and downstream feed availability.

## Startup fixed point

Pre-change initialization was not stationary. After 60 simulated seconds from a fresh `State`, Stage-1
vacuum rises from 0.330 to 0.381 bar(a), 323F010 rises 3.6 °C, HPCC level falls 3.65 percentage
points, and false consequence flags appear.

Correct initialization at equations, not by freezing outputs:

1. Remove double-counted design noncondensables from both vacuum pressure balances. Add only departure
   from the design volatile load because PFD ejector-pull anchors already include that load.
2. Pin HPCC liquid make from the final runtime design seed, not an earlier CAS warm-up state.
3. Measure remaining design residuals for every integrated state after these corrections. Correct
   mismatched design anchors at their source; do not subtract opaque per-state drift constants.
4. Cache deterministic pins by source hash. Restore a fresh `State` after pinning.

Startup acceptance over 600 simulated seconds:

- no consequence, trip, crystallization, carryover, cavitation, flooding, or vacuum-collapse flag;
- HP synthesis pressure within 0.15 bar of design (about 0.1% of loop pressure);
- vessel levels within 1.0 percentage point of design;
- process temperatures within 1.0 °C of design;
- vacuum pressures within 3% of design;
- controller outputs remain finite and within limits;
- every tracked state remains finite and nonnegative where physically required.

## Testing

Create two layers:

1. Fast law tests verify monotonic thermodynamic, hydraulic, absorption, reaction, and crystallization
   behavior without running the full flowsheet.
2. Dynamic scenario tests manipulate actual operator controls, run through transport lags, and assert
   local and downstream effects. A coverage manifest maps every subsection in all three scenario files
   to at least one assertion.

Keep existing regressions. Add a sustained startup test before changing initialization, prove it
fails, then make the smallest physical corrections that pass it.

## Boundaries

- No UI changes.
- No invented PSV setpoints, pump curves, vessel elevations, or electrolyte parameters.
- Quantitative redesign accuracy outside published validity ranges remains an explicit gap.
- Preserve unrelated `scratch/` files and current branch history.
