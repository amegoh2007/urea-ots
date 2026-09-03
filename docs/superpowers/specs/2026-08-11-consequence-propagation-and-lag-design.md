# Consequence Propagation and Lag Design

**Date:** 2026-08-11
**Scope:** Unlisted deviations that produce the same physical consequence classes as the 48 scenarios in
`References/scenarios/Scenarios.md`, `Scenarios2.md`, and `Scenarios3.md`

## Goal

Make equivalent physical consequences propagate through the same downstream equations, regardless of which
listed or unlisted disturbance caused them. Transport the affected mass, temperature, and species together and
delay their downstream arrival by a physically interpretable residence time.

## Research basis

- EPA EPANET 2.2 transports discrete fluid parcels through links, conserves their constituent mass, and mixes
  arriving parcels at downstream nodes. This is the selected model for a pipe dead time and stream composition.
- IDAES dynamic control volumes require material and energy holdup. This supports retaining the existing vessel
  mass and energy balances as the downstream response rather than adding scenario-specific output filters.
- NPTEL process-dynamics material identifies a first-order time constant as the time to reach 63.2% of the final
  response. This is the interpretation used for well-mixed receiver holdup.
- MIT residence-time-distribution notes distinguish plug flow from tanks in series. The simulator therefore uses
  plug-flow transit for lines and the existing mixed inventories for vessels.

Sources:

- EPA, *EPANET 2.2 User Manual*, https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=P10113EM.TXT
- IDAES, *Control Volume Classes*, https://idaes-pse.readthedocs.io/en/1.2.1/core/control_volume.html
- NPTEL, *Significance of First Order Process*,
  https://archive.nptel.ac.in/content/storage2/courses/103103037/module3/lec4/3.html
- MIT OpenCourseWare, *Reactor Tanks: Dispersed Flow, Tanks-in-series, Residence Time Distribution*,
  https://ocw.mit.edu/courses/1-85-water-and-wastewater-treatment-engineering-spring-2006/resources/l04_react_tank_2/

## Approaches considered

### 1. Conservative consequence packets on physical routes — selected

Represent each extra gas, liquid carryover, or contaminant load as one packet containing component mass rates,
temperature, and sensible-enthalpy rate. Delay the entire packet through the physical connection, then add it to
the receiving equipment's normal inlet. Existing receiver mass, energy, pressure, absorption, and species balances
produce the impact. The source scenario name never enters the calculation.

This approach is small enough for the real-time 0.1 s engine, preserves the current design fixed point, and gives
new unlisted causes the same downstream behavior automatically.

### 2. Independent lag for every displayed property

Lag flow, temperature, analyzer values, and composition separately. This is simple but can create a stream whose
total flow disagrees with the sum of its components or whose temperature represents a different fluid parcel.
Reject it because it violates the requested parity between stream properties and composition.

### 3. Full one-dimensional distributed flowsheet

Discretize every pipe and equipment volume. This is physically richer but the repository lacks validated pipe
lengths, fittings, exchanger channel volumes, and axial-dispersion data. It would turn assumptions into false
precision and is outside an operator-training simulator's runtime budget.

## Architecture

### Consequence packet

Add an immutable packet contract in `backend/consequence.py` with:

- total mass flow, kg/h;
- temperature, °C;
- per-component mass flow, kg/h;
- mass fractions derived only from the component vector;
- sensible-enthalpy rate, kW, using the route's phase heat capacity.

Packet construction rejects negative flow, normalizes nonnegative source fractions, and derives the total from
the component vector. Packet mixing sums component and enthalpy rates, then derives the mixed temperature and
composition. No source tag affects these calculations.

### Transport

Each route owns an effective line inventory. Its live dead time is:

`dead time = line inventory / live carrier mass flow`.

The design inventory is back-calculated from the already-established 8 s gas-front or 20 s liquid-slug travel
anchor. Therefore flow reduction lengthens the arrival time and flow increase shortens it. A timestamped FIFO
delays the complete packet without scaling or reordering its properties. Dead time is capped at 30 minutes when a
line stalls.

Receiving vessels are not given another arbitrary filter. Their existing component, mass, energy, and gas-inventory
balances provide first-order response with `tau = holdup / throughput`. This avoids double-counting lag.

### Shared downstream application

Route every seal-loss gas event through the same packet and transport functions. Apply the arrived packet as an
extra inlet or gas load at the destination:

- 322E001 drain seal loss -> 323C003/LP overhead system;
- 323C003 drain seal loss -> 323F004 and its overhead condenser;
- 323F004 drain seal loss -> 323F010/Unit 324 vacuum system;
- 328C003 drain seal loss -> 328C004 overhead and 328C002 recycle;
- 328C004 drain seal loss -> 328E007/process-condensate outlet;
- 322C001 drain seal loss -> 323E003/323D001 LPCC.

The same mechanism is reusable for entrained-liquid and contaminant packets. Existing Souders-Brown, IEC 60534,
NPSH, crystallization, absorption, VLE, and reaction laws remain the local consequence generators.

### Diagnostics

Publish route diagnostics with source, destination, live dead time, arrived mass, arrived temperature, and arrived
mass fractions. Diagnostics are observations of transported packets, not separate physics.

## Invariants

- A zero consequence produces exactly zero downstream addition at the design point.
- Component rates sum to total mass rate within floating-point tolerance.
- Mixing and transport preserve nonnegative components and normalized composition.
- Two identical consequence packets on two route-state keys produce identical downstream packets.
- No destination changes before its dead time after a settled design history.
- A sustained disturbance reaches the same final packet independent of dead time.
- Lower carrier flow never shortens transport time.
- Receiver state changes remain recoverable because consequences enter as rates, never state assignments.

## Acceptance tests

1. Unit tests prove packet closure, energy-consistent mixing, source-name independence, inverse flow/dead-time
   scaling, delayed onset, and exact sustained final value.
2. Dynamic tests drain previously unlisted vessels and prove the arrived gas packet changes downstream equipment
   only after the route delay.
3. Dynamic tests prove NH3/CO2/H2O composition and temperature arrive with the extra flow and alter the receiving
   balance, rather than only setting an alarm flag.
4. The 48-scenario manifest, HP recycle tests, consequence scenarios, and ten-minute startup test remain green.

## Boundaries

- No UI changes.
- No invented pipe lengths, fitting losses, PSV settings, or vendor response curves.
- The effective line inventory is a reduced-order calibration anchor, not a piping-design calculation.
- Detailed flashing inside a line remains the responsibility of the destination thermodynamic package.
- Existing untracked `scratch/` files remain untouched.
