# Urea OTS — Project Documentation

> **Operator Training Simulator for a 1,750 MTPD Stamicarbon CO₂-Stripping Urea Plant**

---

## 1. Project Overview

This repository implements a **real-time, browser-based Operator Training Simulator (OTS)** for a full-scale industrial urea plant operating under the Stamicarbon CO₂-stripping process at 1,750 metric tons per day of urea production. The simulator reproduces the plant's high-pressure synthesis loop (Section 322), ammonia pumping station (Section 321), medium-pressure decomposition stage (Section 323), low-pressure decomposition and recirculation stage (Section 328), vacuum evaporation train (Section 324), steam/condensate network (Section 329), and the supporting utilities — all governed by rigorous mass, energy, and phase-equilibrium (MESH) equations anchored to the plant's as-built heat-and-mass-balance (H&MB) datasheets.

### 1.1 Purpose

- **Training:** DCS console operators rehearse normal startup, load changes, turndown, and malfunction/trip scenarios without touching the live plant.
- **Engineering validation:** The engineering team verifies controller tuning, interlock logic, and equipment sizing against the physical flowsheet and datasheets.
- **Process understanding:** The thermodynamic and kinetics models serve as a living reference for the plant's chemistry and energy integration.

### 1.2 Design Philosophy

| Principle | Implementation |
|---|---|
| **Design-anchored fidelity** | Every unit is initialised ("boot-pinned") to the exact H&MB design point from the 1,750 MTPD PFD datasheets. Off-design behaviour is computed from first-principles physics; no parameter is fabricated. |
| **Dynamic, not steady-state** | All holdups, levels, temperatures, and pressures are integrated by explicit Euler at 0.1 s tick rate. Controllers drive real transients. |
| **Sequential-Modular architecture** | Units are solved block-by-block along the directed flowsheet graph, with recycle loops resolved via tear-stream iteration. |
| **100 % backend authority** | The UI computes zero process values. Every indicator, valve position, and pump state is read from the physics engine's WebSocket packet. |
| **Bit-exact design preservation** | Guard functions and normalised conversion factors ensure the design steady state is reproduced to floating-point precision. |

### 1.3 Plant Capacity

| Parameter | Value |
|---|---|
| Design Urea Production | 1,750 MTPD (100 % load) |
| Uprated Capacity | 1,925 MTPD (verified at off-design) |
| HP Synthesis Loop Pressure | ~140 bar a |
| HP Stripper Shell Pressure | 19.7 bar a (HP steam) |
| LP Steam Header | 5.01 bar a (4.0 bar g) |
| Reactor Temperature | ~183 °C (design overflow) |
| NH₃/CO₂ Molar Ratio (N/C) | 3.073 (design) |

---

## 2. Technology Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.10+ (CPython), FastAPI + Uvicorn |
| **Frontend** | Vanilla HTML/CSS/JS, Chart.js (trends) |
| **Transport** | WebSocket (`/ws`, 10 Hz push), REST API (`/api/*`) |
| **Dependencies** | `fastapi ≥ 0.110`, `uvicorn[standard] ≥ 0.29`, `pydantic ≥ 2.0`, `openpyxl ≥ 3.1` |
| **Launch** | `launch.bat` — auto-resolves Python interpreter, installs deps, starts backend, waits for port 8000, opens Chrome |

---

## 3. Architecture

### 3.1 High-Level Data Flow

```
┌────────────────────┐       WebSocket /ws (0.1 s)       ┌──────────────────────┐
│   Backend (Python)  │ ──── JSON state packet ──────────▶│  Frontend (Browser)  │
│                     │                                    │                      │
│  main.py            │ ◀── JSON commands ────────────────│  app.js              │
│  ├── step_sim()     │     (pump_toggle, xv_toggle,      │  ├── overlays.js     │
│  │   ├── Section 321│      ctrl_set, hic_set …)         │  ├── trend.js        │
│  │   ├── Section 322│                                    │  └── co2_compressor.js│
│  │   ├── Section 323│       REST /api/*                  │                      │
│  │   ├── Section 324│ ◀── (ctrl routes, hist) ─────────│                      │
│  │   ├── Section 328│                                    │                      │
│  │   └── Section 329│                                    │                      │
│  ├── Historian       │                                    │                      │
│  ├── Controllers     │                                    │                      │
│  ├── Steam System    │                                    │                      │
│  └── Reactor Kinetics│                                    │                      │
└────────────────────┘                                    └──────────────────────┘
```

### 3.2 Simulation Loop

1. `step_sim(dt=0.1)` is called every 100 ms of wall-clock time (adjustable pacing).
2. The `State` object carries all integrator variables (holdups, temperatures, levels, pressures, controller states).
3. Each plant section is evaluated in sequence: 321 → 322 → 323 → 324 → 328 → 329.
4. Recycle tear streams use one-tick-delayed values (`tlag` dictionary).
5. The resulting state is serialised to a flat JSON packet and broadcast to all connected WebSocket clients.
6. The `Historian` records every numeric/boolean leaf (except `STREAMS`) into columnar ring buffers at two cadences: **fast** (1 plant-second, 1 h capacity) and **slow** (10 plant-seconds, 8 h capacity).

### 3.3 MESH Equation Framework

Every unit operation satisfies:

- **Mass Balance:** ΣF_in − ΣF_out = dm/dt
- **Component Balance:** ΣF_in·x_i − ΣF_out·x_i + r_i·V = 0
- **Energy Balance:** ΣF_in·H_in − ΣF_out·H_out + Q − W = dU/dt
- **Phase Equilibrium:** y_i = K_i · x_i (via Extended UNIQUAC or Antoine, depending on system)
- **Chemical Equilibrium / Kinetics:** Modified Inoue-Kanai for urea synthesis; Arrhenius rate law
- **Heat Transfer:** Q = UA · ΔT_lm (with design-anchored UA scaling)
- **Constitutive:** Σx_i = 1, Σy_i = 1, plus Darcy-Weisbach / Ergun pressure-drop correlations

---

## 4. Plant Sections Modelled

### 4.1 Section 321 — NH₃ Pumping Station

- **321P002 A/B** triplex reciprocating positive-displacement pumps with VOITH torque-converter scoop speed control
- **321D003** NH₃ buffer drum with level integration
- **SIC-321950/951** speed controllers (MAN / AUTO / CAS / OOS modes)
- **Ratio block:** SP_NH₃_flow = ratio_SP × F_CO₂ with operator N/C bias
- XV-321901, XV-322901 block valves with interlock 21.4 override

### 4.2 Section 322 — HP Synthesis Loop

- **322R001** HP Reactor — Modified Inoue-Kanai separable equilibrium kinetics (N/C, H/C, T dependencies)
- **322E001** HP Stripper — falling-film CO₂-stripped decomposition with shell-side HP steam heating
- **322E002** HP Carbamate Condenser (HPCC) — carbamate condensation exotherm → LP steam export
- **322E003** HP Scrubber — off-gas absorption with CCW cooling
- **322F001** HP Ejector — motive/suction/discharge with spindle-controlled entrainment
- **322D001 A/B** LP steam drums
- LV-322501, HV-322602, HV-322604, HV-322605 control/hand valves

### 4.3 Section 323 — MP Decomposition / Rectification

- **323C003** MP Rectifying Column with LP-steam reboiler 323E002
- **323F004** MP Flash Separator with integrated level controller
- **323E003** MP Condenser
- **323D001** LP Separator / Reflux Drum
- **323E010** Heater / Concentrator
- **323E011** Condensate Cooler
- **323D011** Condensate Drum
- **323C005** LP Vent Scrubber → 328V001 → Comp-II feed
- TIC-323007 → PIC-329202 cascade (column temperature master → steam chest slave)

### 4.4 Section 324 — Vacuum Evaporation

- **324E001 / 324E003** 1st and 2nd stage evaporators (steam-heated, UNIQUAC VLE)
- **324E002 / 324E005** 1st and 2nd stage vacuum condensers
- **324F002 / 324F004 / 324F005** Steam ejectors (1-D compressible-flow Huang model)
- **324E006 / 324E007** Pre-condensers
- TIC-324001, TIC-324002 evaporator temperature masters
- LIC-324501 level controller with LV-324501 routing logic

### 4.5 Section 328 — LP Decomposition / Hydrolyser / Recirculation

- **328D003** LP Decomposer compartments (Bay I, II, III with communicating levels)
- **328C002 / 328C004** LP Absorber columns
- **328C003** Hydrolyser with steam heating (PIC-328203)
- **328E001 / 328E007 / 328E021** LP heat exchangers and condensers
- **328D001** Inerts Accumulation Drum
- **328P002 / 328P003 / 328P006 / 328P007** Recirculation and drain pumps
- **328V001** Comp-II vapour receiver

### 4.6 Section 329 — Steam & Condensate Network

Four pressure levels modelled as lumped-capacitance headers:

| Header | Design Pressure | Source |
|---|---|---|
| BL Supply | 25.0 bar a | 320E006 (battery limit, held) |
| HP Saturator (329D005) | 19.7 bar a | HP stripper 322E001 shell |
| MP Drum (329D009) | 9.0 bar a | MP header + let-down |
| LP Drums (322D001A/B) | 5.01 bar a | HPCC steam-raising + let-down |

- Split-range PIC-329207 A/B/C for LP header master control
- PV-329207B turbine-export valve (FT-329407 = 16,707 kg/h at design)
- Desuperheating attemperator mass balances

---

## 5. Thermodynamic & Property Models

### 5.1 Extended UNIQUAC (NH₃-CO₂-H₂O Electrolyte System)

`props_nh3co2h2o.py` — Full implementation of the Thomsen-Rasmussen / Darde Extended UNIQUAC model:

- Combinatorial + Residual UNIQUAC terms
- Extended Debye-Hückel long-range ionic term
- SRK gas-phase fugacity coefficients
- Damped log-space Newton-Raphson speciation solver (R1–R5 reactions)
- Reaction enthalpies and excess enthalpies
- Valid 0–150 °C, 1–100 bar, up to 100 molal NH₃

Wired into the live engine through `vle_nh3co2h2o.py`, which turns it into the bubble-point service
for the 323C003 rectifying column and the 323F004 flash tank (both previously ran on a pure-water
saturation line with a frozen offset) and supplies the 328D003 ammonia-water vapour pressure. See
`docs/Urea OTS — As-Built Mathematical Reference.md` for the validation against the PFD anchors.

### 5.2 Neutral UNIQUAC (H₂O-Urea for Unit 324)

`thermo_extended_uniquac.py` — Voskov-Voronin binary UNIQUAC for the urea-water system:

- Activity coefficients, bubble-point, relative volatility
- IAPWS-IF97 pure-water saturation reference
- Design-anchored extrapolation for vacuum evaporator envelope (372–473 K, 0.02–1.00 bar)

### 5.3 IAPWS-IF97 Pure-Water Steam Tables

`iapws_if97.py` — Regions 1, 2, and 4 of IAPWS R7-97:

- Saturation temperature/pressure (forward and backward)
- Saturated liquid/vapour specific enthalpy and volume
- Latent heat
- Shared by all steam-heated shells and the 329 network

### 5.4 Modified Inoue-Kanai Reactor Kinetics

`reactor.py` — Separable equilibrium structure for CO₂-to-urea per-pass conversion:

- X(L, W, T) = X_inf · f_L(L) · f_W(W) · f_T(T) with thermodynamic ceiling guard
- N/C saturation, H/C water penalty, parabolic T-penalty
- Design-anchored (conversion factor = 1.000000 at design HMB by construction)

### 5.5 Huang Ejector Model

`ejector_huang.py` — 1-D compressible-flow steam ejector:

- Isentropic area/Mach/pressure relations
- Choked nozzle mass flux, normal-shock jump
- Entrainment ratio and critical backpressure
- Validated against standard gas-dynamics tables

### 5.6 Crowe Data Reconciliation

`reconcile_crowe.py` — Steady-state data reconciliation by matrix projection:

- Weighted least squares with Crowe's projection for unmeasured streams
- Validated against hand-solvable mass-balance networks

---

## 6. Control System

### 6.1 PID Controllers

`controllers.py` implements velocity-form I-PD (integral on error, proportional and derivative on PV) with:

- Pre-direction sigma (REVERSE/DIRECT action)
- Slew-rate limiting
- Output clamping and anti-windup
- Error deadzone
- Derivative filter (1st-order)
- Modes: MAN / AUTO / CAS / OOS

46 controllers seeded in `State.__init__` with tuning constants documented in `Master_PID_Tuning_Constants.md`. Simulator tuning is independently re-derived for discrete-time stability — intentionally differs from the plant DCS table in 33 of 46 loops.

### 6.2 Controller Roster (Key Loops)

| Loop | Controls | Section |
|---|---|---|
| SIC-321950/951 | NH₃ pump speed (VOITH scoop) | 321 |
| LIC-322501 | Stripper bottoms level → LV-322501 | 322 |
| PIC-322201 | 322C001 pressure → GCB | 322 |
| TIC-323007 | 323C003 column temperature (cascade → PIC-329202) | 323 |
| PIC-323203 | 323F004 flash pressure → GCB | 323 |
| LIC-323501/505 | Column and flash levels | 323 |
| TIC-324001/002 | Evaporator temperatures | 324 |
| PIC-324202/203 | Vacuum pressures | 324 |
| LIC-328501/503/504/505 | LP section levels | 328 |
| PIC-329207 | LP steam header master (split-range A/B/C) | 329 |

---

## 7. Frontend / DCS Human-Machine Interface

### 7.1 Architecture

The UI replicates a **DCS console** with an image-backed overlay system:

- **Background:** Cleaned P&ID screenshots stretched to 1366 × 720 px
- **Overlay layer:** Absolute-positioned `.ov` elements over the static image
- **Live indicators:** Black boxes showing real-time process values (T, P, flow, level, %)
- **Dynamic equipment:** Pumps (ON/OFF icons), block valves (OPEN/CLOSED bowties), auto valves (0–100 %)
- **Unmodelled tags:** White-frame empty slots awaiting future binding

### 7.2 DCS Screens (10 Screens)

| Screen ID | Title | Section |
|---|---|---|
| `screen-321-1` | NH₃ Pumping Station | 321 |
| `screen-322-1` | HP Synthesis — Stripper Side | 322 |
| `screen-322-2` | HP Synthesis — HPCC/Scrubber/Ejector | 322 |
| `screen-323-1` | MP Decomposition (Upper) | 323 |
| `screen-323-2` | MP Decomposition (Lower) | 323 |
| `screen-324-1` | Vacuum Evaporation Stage 1 | 324 |
| `screen-324-1b` | Vacuum Evaporation Stage 2 | 324 |
| `screen-328-1` | LP Decomposition / Hydrolyser | 328 |
| `screen-328-2` | LP Recirculation / Absorbers | 328 |
| `screen-329-1` | Steam & Condensate Network | 329 |

### 7.3 Interactions

- **Left-click indicator** → Controller faceplate (SP, MV, mode selection)
- **Right-click indicator** → Trend context menu → opens 10-pen trend window
- **Left-click stream line** → Stream composition popup
- **Click pump/valve** → Toggle ON/OFF or OPEN/CLOSED
- **Drag indicator** → Cross-window drag to trend popup
- **Right-click stage** → Screen navigation dropdown

### 7.4 Trend System (`trend.js`)

A dedicated **separate browser window** (`trend.html`) hosting:

- 10-pen trend with auto-scaling analog and stepped digital traces
- Plant-clock (t_sim) X-axis with dual desktop/plant time ticks
- 7 time spans: 1m, 5m, 30m, 1h, 2h, 4h, 8h
- Up to 10 draggable vertical rulers with colour-coded readings
- MIN / MAX / AVG statistics per visible window
- Editable display ranges (LOW / HIGH) per pen
- History scrolling with backfill from backend historian via `/api/hist`
- PNG export (`SAVE` button)
- Persistence in `localStorage` (slots, span, geometry)
- `TRENDS` toolbar button (screen-independent entry)

### 7.5 Backend Health / Fault Surface

Three fault classes are surfaced to the operator:

| Fault | Condition |
|---|---|
| **CRASH** | Server packet has `_health.ok === false` (physics step raised an exception) |
| **HANG** | Packets arrive but `_health.age_s` climbing (step wedged) |
| **LINK** | No packets for > 3 seconds (WebSocket dropped, server gone) |

System LED + fault overlay with traceback, sim-time, and error count.

---

## 8. Reports & Documentation

### 8.1 Generated Reports (`backend/reports/`)

| File | Content |
|---|---|
| `FULL_AUDIT_REPORT.md/html/pdf` | Plant-wide MESH compliance audit report |
| `G6_static_stream_catalogue.json/md` | Static stream catalogue (all PFD streams) |
| `VALVE_INDICATOR_AUDIT.md` | Hand-valve and indicator binding audit |
| `BUG8_STRIPPER_COUPLING_VERDICT.md` | Stripper-coupling bug analysis |
| `dcs_anchor_dynamics_*.md` | DCS anchor dynamics analysis (dated) |
| `dcs_tuning_parameters.md` | Controller tuning parameter export |

### 8.2 Design Documents (`docs/`)

| Document | Purpose |
|---|---|
| `Urea OTS — As-Built Mathematical Reference.md` | As-built mathematical equations and source anchors |
| `docs/superpowers/specs/` | Design specification documents (7 specs) |
| `docs/superpowers/plans/` | Implementation plans (5 plans) |

### 8.3 Key Project-Root Documents

| File | Purpose |
|---|---|
| `CLAUDE.md` | Agent directives: physics rules, workflow, documentation standards |
| `ui_guidelines.md` | Complete DCS UI generation guidelines (overlay system, typography, colours, faceplates, trend) |
| `Master_PID_Tuning_Constants.md` | Authoritative PID tuning table + simulator appendices |

---

## 9. Reference Library (`References/`)

### 9.1 Process Data

- `Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md` — **Primary strict source** for all H&MB design data
- `Combined_1925_MTPD_100% load_PFD TablesProcess_Data.md` — Uprated capacity data
- `Urea_Operating_Manual_Helwan.md` — Plant operating manual
- `3.6.2025 Synthesis startup.md` — Actual plant startup log
- `Urea_NormalOp_29-06-2025_Trends.md` — Normal operation DCS trends
- `Urea_Startup_28-06-2025_Trends.md` — Startup DCS trends

### 9.2 Equipment Descriptions & Mappings

- Unit-specific equipment description files (322R001, 322E003, 323C003, 323C005, 328E021, etc.)
- Section mapping files (Absorber, Desorber/Hydrolyser, Evaporation, Cooling Water, Steam)
- HV-322604 / LV-322501 valve descriptions

### 9.3 Thermodynamics & Modelling

- `fundamentals.md` / `mesh-equations.md` — Theory reference
- `Ammonium Carbamate Heat Capacity Data.md` — Literature heat capacity data
- `Urea-Water VLE Data Research.md` — VLE literature review
- `Strategic Resolution of Thermodynamic and Topological Simulation Gaps...md` — Gaps strategy
- `Gaps solution.md` / `Urea Simulator Gap Resolution.md` — Gap closure tracking

### 9.4 Datasheets (`References/Datasheets/`)

**57 equipment datasheet PDFs** covering:
- Vessels: 321D003, 322D001, 323D001/D002, 328D001, 329D005, 329D009, 335D007
- Exchangers: 322E001–E006, 323E002–E011, 324E001–E007, 328E001/E007, 329E002/E004
- Columns: 322C001, 323C003/C005, 328C002/C003/C004
- Pumps: 321P002, 322P002, 323P003, 328P003/P006/P007, 329P006, 335P001/P002
- Ejectors: 324F001–F005 (incl. design calculations)
- Valves: HV-322604, HV-322605, LV-322501

### 9.5 Source Literature (`References/Sources/`)

22 PDF files including:
- Chinda (2017) — Modelling and simulating the synthesis section
- Aspen urea simulation reference
- Contribution papers on urea equilibrium
- PFDs and P&IDs (64 MB merged searchable PIDs)
- Phase diagrams

---

## 10. Complete Filesystem Tree

```
D:\Work\Urea Simulation\
│
├── CLAUDE.md                              # Agent directives (physics, workflow, docs)
├── Master_PID_Tuning_Constants.md         # PID tuning table + OTS appendices
├── ui_guidelines.md                       # DCS UI overlay system specification
├── launch.bat                             # One-click launcher (Python→deps→backend→Chrome)
├── simulate.py                            # Standalone pressure-drop simulation runner
├── pressure_drop.py                       # Equipment pressure-drop classes (Reactor, S&T)
├── lp_stage.py                            # LP decomposition stage equations
├── mp_stage.py                            # MP decomposition stage equations
├── sm_injector.py                         # SM flowsheet injector script
├── .gitignore                             # Git ignore rules
│
├── backend/                               # ══════ PYTHON BACKEND ══════
│   ├── main.py                            # ★ MONOLITH: FastAPI app, all plant sections,
│   │                                      #   State class, step_sim(), WebSocket hub
│   │                                      #   (~9,100 lines, ~669 KB)
│   ├── requirements.txt                   # fastapi, uvicorn, pydantic, openpyxl
│   │
│   ├── # ── Thermodynamics & Properties ──
│   ├── props_nh3co2h2o.py                 # Extended UNIQUAC (NH₃-CO₂-H₂O electrolyte)
│   ├── thermo_extended_uniquac.py         # Neutral UNIQUAC (H₂O-urea for Unit 324)
│   ├── iapws_if97.py                      # IAPWS-IF97 pure-water steam tables
│   │
│   ├── # ── Physics Modules ──
│   ├── reactor.py                         # 322R001 Modified Inoue-Kanai kinetics
│   ├── steam_system.py                    # 329 steam/condensate network dynamics
│   ├── controllers.py                     # Velocity I-PD controller engine
│   ├── ejector_huang.py                   # 1-D compressible-flow ejector (Huang 1999)
│   ├── reconcile_crowe.py                 # Crowe projection data reconciliation
│   ├── historian.py                       # Process historian (ring buffers, backfill)
│   ├── c003_pressure_coupling.py          # C003 pressure target coupling
│   ├── patch_levels.py                    # Level integrator patches
│   ├── patch_levels2.py                   # Level integrator patches (variant)
│   ├── update_pids.py                     # PID tuning update utility
│   ├── audit_model_compliance.py          # Plant-wide MESH compliance audit
│   │
│   ├── # ── Gap-Closure Research Modules ──
│   ├── gap_g2_reference_state_audit.py    # G2: Reference state audit
│   ├── gap_g2_vacuum_vle_refit.py         # G2: Vacuum VLE re-fit
│   ├── gap_g3_data_reconciliation.py      # G3: Data reconciliation
│   ├── gap_g4_conservation_harness.py     # G4: Conservation test harness
│   ├── gap_g4_reactor_kinetics.py         # G4: Reactor kinetics calibration
│   ├── gap_g6_h0_enthalpy.py             # G6: Enthalpy reference state
│   ├── gap_g6_static_catalogue.py         # G6: Static stream catalogue builder
│   ├── gap_g9_evaporator_condenser.py     # G9: Evaporator/condenser model
│   ├── gap_g9a_ejector_envelope.py        # G9a: Ejector operating envelope
│   ├── gap_g9b_valve_hydraulics.py        # G9b: Valve hydraulics model
│   ├── gap_g9c_droplet.py                # G9c: Droplet entrainment model
│   │
│   ├── # ── Debug Scripts ──
│   ├── debug_hv605.py                     # HV-605 debug probe
│   ├── debug_pressure.py … debug_pressure12.py  # Pressure iteration debug (12 scripts)
│   ├── trace_import.py                    # Import tracer
│   │
│   ├── # ── Backup Copies ──
│   ├── main.py.bak / main_backup.py / main_debug.py / main_orig.py / main_test_fix.py
│   │
│   ├── core/                              # ── SM Flowsheet Framework ──
│   │   ├── flowsheet.py                   # Topology manager (SM solve loop)
│   │   ├── unit.py                        # UnitOperation base class
│   │   ├── stream.py                      # Stream state vector + dirty flag
│   │   ├── thermo.py                      # EmpiricalThermo property wrapper
│   │   ├── ejector.py                     # 322F001 ejector unit operation
│   │   ├── stripper.py                    # 322E001 stripper unit operation
│   │   ├── hpcc.py                        # 322E002 HPCC unit operation
│   │   ├── scrubber.py                    # 322E003 scrubber unit operation
│   │   ├── reactor.py                     # 322R001 reactor unit operation
│   │   ├── valve.py                       # HV-322604 valve unit operation
│   │   ├── vacuum.py                      # 324 vacuum train unit operation
│   │   ├── lp.py                          # LP stage unit operations
│   │   └── mp.py                          # MP stage unit operations
│   │
│   └── reports/                           # ── Generated Reports ──
│       ├── FULL_AUDIT_REPORT.md/html/pdf  # Plant-wide audit
│       ├── G6_static_stream_catalogue.json/md  # Stream catalogue
│       ├── VALVE_INDICATOR_AUDIT.md       # Valve/indicator audit
│       ├── BUG8_STRIPPER_COUPLING_VERDICT.md   # Bug verdict
│       ├── dcs_anchor_dynamics_*.md       # DCS anchor dynamics
│       ├── dcs_tuning_parameters.md       # Tuning export
│       └── md_to_pdf.py                   # Report PDF converter
│
├── frontend/                              # ══════ BROWSER UI ══════
│   ├── index.html                         # Main DCS page (10 screens, CSS, modals)
│   ├── app.js                             # WebSocket, health, renders, faceplates
│   ├── overlays.js                        # Rev2 overlay engine (OV config, bind map, editing)
│   ├── trend.js                           # 10-pen trend window (popup + launcher roles)
│   ├── trend.html                         # Trend popup host page
│   ├── co2_compressor.js                  # CO₂ compressor HMI logic
│   ├── lv324501_route.js                  # LV-324501 routing UI
│   │
│   └── img/                               # ── DCS Screen Backgrounds ──
│       ├── screen-321-1.png               # NH₃ pumping station
│       ├── screen-322-1.png               # HP synthesis (stripper)
│       ├── screen-322-2.png               # HP synthesis (HPCC/scrubber)
│       ├── screen-323-1.png               # MP decomposition (upper)
│       ├── screen-323-2.png               # MP decomposition (lower)
│       ├── screen-324-1.png               # Vacuum evaporation stage 1
│       ├── screen-324-1b.png              # Vacuum evaporation stage 2
│       ├── screen-328-1.png               # LP decomposition
│       ├── screen-328-2.png               # LP recirculation
│       └── screen-329-1.png               # Steam & condensate network
│
├── docs/                                  # ══════ DOCUMENTATION ══════
│   ├── Urea OTS — As-Built Mathematical Reference.md
│   └── superpowers/
│       ├── specs/                          # Design specifications (7 files)
│       │   ├── 2026-08-07-architectural-refactor-design.md
│       │   ├── 2026-08-07-stripper-steam-consumption-design.md
│       │   ├── 2026-08-07-trend-system-design.md
│       │   ├── 2026-08-08-hpcc-steam-and-ejector-temperature-design.md
│       │   ├── 2026-08-08-level-integrator-design.md
│       │   ├── 2026-08-08-pressure-lag-tuning-design.md
│       │   └── 2026-08-08-recirculation-pressure-coupling-design.md
│       └── plans/                          # Implementation plans (5 files)
│           ├── 2026-08-07-sm-architecture.md
│           ├── 2026-08-07-stripper-steam-consumption.md
│           ├── 2026-08-08-hpcc-steam-and-ejector-temperature.md
│           ├── 2026-08-08-pressure-lag-tuning.md
│           └── 2026-08-08-recirculation-pressure-coupling.md
│
├── References/                            # ══════ ENGINEERING REFERENCES ══════
│   ├── Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md  ★ PRIMARY SOURCE
│   ├── Combined_1925_MTPD_100% load_PFD TablesProcess_Data.md
│   ├── Urea_Operating_Manual_Helwan.md
│   ├── fundamentals.md / mesh-equations.md
│   ├── Stamicarbon_Steam_Condensate_Network.md
│   ├── [40+ equipment description / mapping / gap / trend files]
│   │
│   ├── Datasheets/                        # 57 equipment datasheet PDFs
│   │   ├── 321D003, 321P002               # Section 321
│   │   ├── 322C001..322R001               # Section 322
│   │   ├── 323C003..323P003               # Section 323
│   │   ├── 324E001..324F005               # Section 324
│   │   ├── 328C002..328P007               # Section 328
│   │   ├── 329D005..329P006               # Section 329
│   │   ├── 335D007..335P002               # Section 335
│   │   └── HV-322604, HV-322605, LV-322501  # Control valves
│   │
│   ├── Sources/                           # 22 reference PDF papers
│   │   ├── Chinda 2017, Aspen urea, PFDs, PIDs, Phase Diagrams, etc.
│   │   └── [Academic papers on urea synthesis modelling]
│   │
│   └── Gaps Closure/                      # Gap closure documents (2 Word docs)
│
├── .superpowers/sdd/                      # ══════ STRUCTURED DESIGN DOCS ══════
│   ├── 2026-08-01-lv322501-c003-pressure-coupling/
│   │   ├── task-1-brief.md / task-1-report.md
│   │   ├── task-2-brief.md / task-2-report.md
│   │   ├── progress.md
│   │   └── review-*.diff
│   └── 2026-08-08-recirculation-pressure-coupling/
│       ├── task-1-brief.md
│       └── progress.md
│
├── # ── Root Debug & Diagnostic Files ──
├── debug_pressure.py / debug_pressure13.py
├── flow_lines.txt / lines.txt / main_defs.txt
├── sim_assignments.txt / step_sim_body.txt / step_sim_source.py
├── import_lp.txt / import_mp.txt
└── temp_output.txt / test_out.txt / debug_import*.txt
```

---

## 11. How to Run

### 11.1 One-Click Launch

```batch
D:\Work\Urea Simulation\launch.bat
```

This will:
1. Auto-detect a working Python 3.10+ interpreter
2. Install/update pip dependencies from `backend/requirements.txt`
3. Kill any previous backend instance on port 8000
4. Start the FastAPI/Uvicorn backend server
5. Poll until the server responds on `http://127.0.0.1:8000`
6. Open Chrome (or default browser) at the DCS UI

### 11.2 Manual Launch

```bash
cd backend
pip install -r requirements.txt
python main.py
# Open http://127.0.0.1:8000 in browser
```
