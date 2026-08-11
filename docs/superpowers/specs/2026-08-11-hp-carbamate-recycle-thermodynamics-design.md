# HP Carbamate Recycle, Scrubbing, and Urea Equilibrium

**Date:** 2026-08-11
**Units:** 323P001 A/B, 322E003, HV-322604, 322R001, 322E001, and 322E002
**Driver:** Weak-carbamate recycle flow from the LP section to the HP scrubber

## Goal

Model both directions of the 323P001 recycle-flow gradient with the correct causal signs:

- A running reciprocating pump delivers displacement flow proportional to shaft speed. Discharge
  pressure does not define flow; suction availability, slip, speed limits, and a relief path do.
- More cold weak carbamate increases NH3/CO2 absorption, cools the scrubber outlet, and sends more
  liquid to the HP carbamate condenser.
- Less wash reduces absorption. Gas above the finite vent capacity remains in the HP inventory,
  raises synthesis pressure, and overloads the downstream absorber/relief path.
- More recycle water raises the reactor H/C ratio and lowers equilibrium urea conversion. Less
  recycle water improves equilibrium only until recycle-component loss disturbs N/C, reactor
  inventory, and sustainable production.

## Evidence and thermodynamic choice

The plant PFD and equipment sheets remain the design-point authority. Public research supplies the
off-design laws:

- The DOE positive-displacement-pump handbook defines nearly vertical head-flow behavior and flow
  by displacement per cycle, with slip and mandatory overpressure protection.
- Zhang et al. model the industrial HP urea loop with an electrolyte UNIQUAC liquid phase and a
  real-gas equation of state, including the reactor, stripper, condenser, and scrubber.
- Voskov and Voronin publish a urea-synthesis equilibrium model covering 135-230 deg C and
  3.5-45 MPa. Their supplementary code includes a fitted equilibrium-conversion correlation in
  temperature, N/C, and H/C.
- The existing Extended UNIQUAC NH3-CO2-H2O module is suitable for the lower-pressure recovery
  section. Its published validation envelope does not cover the 141-bar, 165-183 deg C HP loop.

The OTS will therefore use two packages by service:

1. Keep Extended UNIQUAC/SRK for LP and MP aqueous-carbamate flashes inside its validity envelope.
2. Use the Voskov-Voronin high-pressure urea-equilibrium correlation for 322R001 conversion,
   normalized to the verified plant design conversion. Use PFD-anchored reactive capacity and
   component balances for 322E003. This is a real-time surrogate of the published HP
   UNIQUAC/virial framework, not a claim that the OTS solves full ionic speciation each tick.

## Model design

### 323P001 A/B

For an available running pump:

`Q = 0.5046 * n * eta_suction` m3/h

where `n` is rpm, from the equipment sheet, and `eta_suction` is the existing NPSH/cavitation
factor. Permit zero speed for a stopped pump. Clamp positive running speed to the equipment range
19-81 rpm. Do not pass discharge pressure into the flow law. Expose a high-discharge-pressure
condition through the simulator's existing pressure protections; do not invent an unverified pump
relief setpoint or bend the pump curve into a centrifugal-pump law.

### 322E003 absorption and HP gas inventory

Start from the design component split. For each tick:

1. Scale reactor off-gas by current synthesis load.
2. Scale weak-carbamate solvent by actual 323P001 flow.
3. Compute an absorption-capacity multiplier from solvent flow, cooling-water temperature and flow,
   and sump flooding/choke. Apply it only to absorbable NH3 and CO2.
4. Route absorbed NH3/CO2 and all wash components to liquid overflow. Route inerts and unabsorbed
   NH3/CO2 to the scrubber gas space. Close every component balance.
5. Limit HV-322604 flow by its design coefficient and live pressure drop. Vent the available gas up
   to that capacity. Retain the excess in the HP-loop gas inventory.

At the design point, the capacity law reproduces the present plant anchor exactly. A wash increase
lowers NH3/CO2 gas flow and temperatures and raises overflow. A wash decrease raises breakthrough;
the valve initially vents at its finite capacity, and the retained excess raises loop pressure.

Publish breakthrough NH3+CO2, retained gas, downstream absorber load ratio, and an absorber-overload
relief/emission rate. These values drive alarms and tests; they do not invent an unverified relief
set pressure for a named plant valve.

### 322R001 equilibrium and loop consequences

Compute synthesis ratios from conserved equivalents:

- `C = n_CO2 + n_urea + 2*n_biuret`
- `N = n_NH3 + 2*n_urea + 3*n_biuret`
- `H/C = (n_H2O - n_urea - 2*n_biuret) / C`
- `N/C = N / C`

Use the published Voskov-Voronin conversion correlation within its stated N/C, H/C, and temperature
domain. Clamp inputs at the domain boundary and publish an extrapolation flag. Normalize the result
to 0.543 at the verified plant point so the design heat and material balance remains stationary.

Conversion changes alter the stripper load. Calculate an additional steam demand and HPCC recycle
load from the unconverted CO2/NH3 increment. Low recycle also creates a recycle-deficit index from
missing NH3, CO2, and liquid inventory; use it to reduce sustainable production and perturb loop
N/C and reactor level through the existing dynamic balances.

## Safety and numerical behavior

- Preserve non-negative component flows and atom-conserving reaction shifts.
- Keep one-tick tears where the flowsheet already uses them; avoid a new algebraic loop.
- Make every departure term zero at the design seed.
- Bound pressure, inventory, and temperature updates with existing physical limits.
- Keep the legacy low-pressure property package out of HP-loop calls.

## Verification

Automated checks will prove:

- 323P001 volumetric flow is linear in rpm and unchanged by discharge pressure.
- The design first tick remains stationary.
- More wash increases overflow, reduces NH3/CO2 breakthrough, and cools scrubber/HPCC feed.
- Less wash increases breakthrough, retained gas, loop pressure, downstream load, and relief/emission
  indication.
- Higher H/C lowers equilibrium conversion, raises stripper steam demand, and raises HPCC recycle.
- Severe low recycle disturbs N/C and reactor level and reduces sustainable production.
- Unit component balances and the reaction stoichiometric shift close within numerical tolerance.
