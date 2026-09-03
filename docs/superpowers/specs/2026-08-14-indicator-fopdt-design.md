# Indicator Process Time Constant and Dead-Time Design

## Goal

Apply a first-order-plus-dead-time (FOPDT) response to every numeric HMI indicator in the Urea OTS, using the class ranges in `References/Sources/Plant PID Simulation Sequence.md`, while preserving existing process balances, controller calculations, and steady-state pins.

## Context and source findings

- `frontend/overlays.js` defines 227 `t: 'ind'` records across the image-backed DCS screens. The legacy 321/322 readouts use `setPI()` in `frontend/app.js`.
- `backend/main.py` already contains `_foptd()`, but it is unused. Many process states already have physical holdup, heat-capacity, or hydraulic dynamics; adding another process lag inside those balances would double-count inertia.
- P&ID pages 3, 13, and 20 confirm representative analyzer, pressure, and level tags (`322701`, `329501`, `322501`). `Manual.pdf` page 83 confirms the flushed HP-ejector level, pressure, and N/C measurements but contains no transmitter timing values.
- The vendor archive TOC routes the installed CO2 compressor as `320K002`, not `320K001`; its technical specification is `UD-AU-320-EC-0001`. That document exposes no searchable transmitter-response value, and no anti-surge indicator is currently rendered by the simulator.
- MathWorks documents the FOPDT form as a first-order transfer function with input delay. The Rosemount 3051 manual confirms configurable transmitter damping in seconds. These support a delayed first-order measurement block.

## Options considered

### 1. Shared HMI measurement service — selected

Create a small browser-side service that classifies each instrument tag, applies dead time followed by a first-order lag on plant simulation time, and is called by both `setPI()` and overlay rendering. Duplicate tags share one state. Advantages: complete coverage by construction, no 200-entry backend whitelist, no change to conservation laws, no retuning of existing PID loops, and testability with Node's built-in assertions. Limitation: this is the transmitter/HMI measurement layer; existing controller PV dynamics remain owned by the backend.

### 2. Backend telemetry-path whitelist

Map every overlay binding path to a backend FOPDT state and filter the outgoing packet. This would also feed the historian, but duplicates the frontend's tag-to-path catalog, risks omissions whenever screens change, and still does not automatically alter controller input signals.

### 3. Per-equipment dynamic edits

Insert bespoke lag and delay equations at every process-variable calculation and every controller input. This can be highest fidelity but requires equipment-specific inventories and line lengths for hundreds of tags, creates a large retuning surface, and would double-count many dynamics already represented by vessel and exchanger states.

## Selected architecture

Add `frontend/indicator_dynamics.js` as a dependency-free UMD module. It exposes:

- `profile(tag, override)` returning the assigned instrument class, process time constant `tauS`, and dead time `deadTimeS`.
- `sample(key, tag, rawValue, simTime, override)` returning the FOPDT measurement.
- `describe(tag, override)` for the HMI tooltip.
- `reset()` for tests and explicit reset handling.

The transfer model is:

`G(s) = exp(-theta*s) / (tau*s + 1)`

with zero-order-held delayed input and exact first-order update:

`y(k) = y(k-1) + [1 - exp(-delta_t/tau)] * [u(t-theta) - y(k-1)]`.

First observation seeds output from the raw value, preventing a boot transient. A decreasing `sim_t` clears all history, matching simulator reset. Repeated reads of the same tag at one simulation timestamp return one shared value.

## Parameter matrix

Values use the procedure's recommended midpoints where it provides a range. Small nonzero transport/scan delays are assigned where the procedure describes fast DCS acquisition but gives no separate value.

| Service | tau (s) | dead time (s) | Basis |
|---|---:|---:|---|
| Anti-surge pressure/flow | 0.05 | 0.002 | `<0.1 s` response and `<2 ms` loop scan |
| Standard pressure | 0.75 | 0.10 | midpoint of 0.5–1.0 s response; fast scan |
| Standard flow | 2.0 | 0.10 | midpoint of 1.0–3.0 s damping; fast scan |
| Turbulent level | 7.5 | 0.50 | midpoint of 5.0–10.0 s heavy damping |
| Calm level | 3.5 | 0.50 | midpoint of 2.0–5.0 s damping |
| Temperature | 30.0 | 1.0 | midpoint of 15.0–45.0 s thermowell response |
| Composition analyzer | 60.0 | 600.0 | explicit analyzer dead-time midpoint; finite analyzer response |
| Speed/current | 1.0 | 0.10 | fast electromechanical measurement |
| Valve/hand-station position | 3.5 | 0.25 | midpoint of 2–5 s actuator stroke guidance |
| Totalizer | 0.5 | 0.10 | acquisition smoothing without materially distorting accumulation |
| Generic numeric indicator | 1.0 | 0.10 | conservative fallback guaranteeing coverage |

Turbulent level overrides cover the reactor, HP stripper, and HP scrubber tags currently rendered: `LT-322504`, `LIC-322501`, and `LT-329501`.

## Data flow and UI behavior

1. WebSocket packet becomes `lastState`; packet field `t_sim` supplies plant time.
2. Legacy `setPI()` resolves the displayed tag and samples the shared FOPDT service.
3. Overlay `renderOne()` samples the same service for every bound numeric `ind` record.
4. Gauge-pressure conversion and numeric formatting occur after dynamics.
5. Hover text includes the instrument class, `tau`, and `theta`.

Unbound white-frame indicators retain their tag only. Digital pumps, block valves, alarm booleans, editable setpoints, and stream-inspector engineering data are not numeric process indicators and are unchanged.

## Verification

- Unit tests prove dead-time hold, 63.2% one-time-constant response, duplicate-read idempotence, clock-reset behavior, and tag classification.
- A coverage test parses `overlays.js`, verifies the expected indicator population, and proves every tagged indicator receives positive `tau` and `theta`.
- Syntax checks cover all changed JavaScript.
- Existing Python regression suite verifies backend process behavior remains intact.

## Error handling and boundaries

Non-finite inputs display through existing `--` handling and do not corrupt FOPDT state. Missing/invalid simulation time seeds or returns the raw measurement. Profile overrides must contain finite nonnegative numbers; invalid overrides fall back to the class profile.
