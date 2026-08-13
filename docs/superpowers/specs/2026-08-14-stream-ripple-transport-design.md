# Stream Ripple Transport Design

**Date:** 2026-08-14  
**Scope:** Normal-process stream changes from the Unit 322 stripper bottoms through Units 323 and 324

## Goal

Delay changes in a stream's flow, temperature, heat capacity, and composition until that stream reaches the next process vessel. Once the packet arrives, the receiving vessel's existing mass, species, and energy inventories must create the gradual response on every downstream indicator.

## Evidence and resolution limit

The two supplied trend workbooks contain 30-second rows, but each workbook states that those rows are synthetic linear interpolations between hourly measurements. The normal-operation workbook contains 17 independent hourly anchors; the startup workbook contains seven. The interpolated rows contain no independent subhour timing information.

Hourly-gradient checks support only a same-bin response:

- Normal operation: `UREA-LOAD` versus `FYM-322403` has zero-bin gradient correlation 0.9925; `FY-322403` has 0.7984.
- Startup: `UREA-LOAD` versus `FY-322403` has zero-bin gradient correlation 0.9999. Several Unit 322 temperatures have zero-bin correlations from 0.9817 to 0.9936.
- The startup series has only six independent gradients. Correlations at longer lags use as few as three pairs and cannot identify a reliable delay.

The workbooks therefore establish `dead time < 3600 s` for the observed feed response. They do not identify a minute-level dead time.

Plant documents establish the route but not its retained pipe volume:

- `Manual.pdf`, pages 61-62: 322E001 bottoms pass through LV-322501 to 323C003; rectifying-column bottoms pass through 323F004 and 323E010; the resulting solution enters 323D002.
- `PIDs.pdf`, pages 3, 4, 8, 15, and 26: the same Unit 322-323 equipment sequence and control-valve boundaries.
- Vendor sheets `UD-AU-323-EC-0001`, `UD-AU-323-EC-0011`, `UD-AU-323-EC-0012`, and `UD-AU-324-EC-0001`: vessel and exchanger dimensions, operating conditions, and liquid densities. They omit field pipe lengths, fittings, and retained line volume.

The simulator already uses a documented 20 s effective liquid-slug anchor. This design retains that reduced-order anchor and scales it by live flow. The trend bound validates its order of magnitude without pretending that the workbooks measured 20 s.

## Options considered

### 1. Whole-stream packet transport — selected

Construct one immutable packet from component mass rates, temperature, and heat capacity. Delay the packet through the process connection, then feed the arrived packet to the next vessel's existing balances. This preserves mass, composition, and sensible enthalpy and makes every downstream indicator respond through shared process state.

### 2. Independent delay for each stream property

Delay flow, temperature, and composition separately. This is easy to wire but can combine the flow from one parcel with the temperature or composition of another. It violates stream closure and is rejected.

### 3. Delay every displayed downstream indicator

Filter indicator values according to flowsheet distance. The HMI already has transmitter FOPDT dynamics; another display filter would double-count measurement response and would not affect controllers or material balances. It is rejected.

### 4. Distributed pipe and equipment model

Discretize every pipe and equipment passage. This needs field pipe geometry and axial-dispersion data that the available records do not contain. It would create false precision and is rejected.

## Selected architecture

### Process packet

Reuse `StreamPacket` for normal process flow. Component mass rates define total mass and mass fractions. Temperature and heat capacity define sensible-enthalpy rate. The packet remains indivisible in the FIFO.

Add `transport_process_packet`, separate from zero-background consequence transport. On first use, it seeds its output with the current packet, so a fresh design-state simulation remains at its design fixed point. Later changes remain behind the line dead time and then arrive as one packet.

### Route law

Each connection owns an effective line inventory:

`M_line = design_flow * design_dead_time / 3600`.

The live dead time is:

`theta = clamp(3600 * M_line / live_flow, 0, theta_max)`.

The design dead time is 20 s for liquid connections. Reduced flow increases transit time; increased flow decreases it. A 30-minute cap bounds a stalled line's history.

### Wired process boundaries

The first implementation covers the principal product path:

1. 322E001 stripper bottoms to 323C003.
2. 323C003 bottoms to 323F004.
3. 323F004 bottoms to 323F010.
4. 323F010 product to 323D002.
5. 323D002 pump discharge to 324E001.

Each source vessel consumes its departure rate immediately in its own inventory balance. Only the receiving vessel consumes the delayed arrival. This maintains conservation across the line inventory and prevents an instantaneous downstream response.

### Ripple behavior

The packet FIFO supplies pure transport dead time. Existing receiver states supply process time constants:

- liquid inventory: `dM/dt = m_in - m_out - m_vap`;
- component inventory: `d(M w_i)/dt = sum(m_in w_i) - sum(m_out w_i) + reaction_i`;
- energy inventory: `M cp dT/dt = sum(m_in cp_in (T_in - T)) + Q - m_vap lambda`.

For a well-mixed receiver, the local first-order scale is approximately `tau = M / m_throughput`. Successive vessels therefore create the requested downstream ripple without an arbitrary indicator cascade.

### Diagnostics

Publish `PROCESS_TRANSPORT` for every route with endpoints, live dead time, departure and arrival mass rates, temperatures, component rates, and mass fractions. The diagnostics report the exact packets used by physics.

## Invariants

- Fresh design state remains a fixed point; process lines never boot empty.
- Component rates sum to total packet flow.
- Flow, temperature, composition, and sensible enthalpy arrive on the same tick.
- A destination cannot respond to a new source packet before route dead time.
- Reduced live flow never shortens dead time.
- A settled sustained change reaches the same final packet independent of dead time.
- HMI transmitter FOPDT remains separate from process transport and vessel holdup.

## Acceptance tests

1. Unit tests prove boot seeding, exact delayed onset, whole-packet arrival, and inverse flow/dead-time scaling.
2. Route tests prove all five principal product boundaries exist with positive delays below the one-hour trend bound.
3. A dynamic test proves a source step changes route departure immediately, leaves arrival unchanged until dead time, and then changes the receiving state through its balance.
4. The generated workbook records the raw workbook limitation, hourly anchors, lag checks, route parameters, and formula-derived effective inventories.
5. Existing scenario, stability, and process-dynamics regressions remain green.

## Boundaries

- No new display-only lag.
- No invented field pipe length or diameter.
- No direct assignment of downstream temperature, composition, level, or pressure.
- The 20 s anchor remains a reduced-order assumption until field piping volumes or higher-resolution historian data become available.
