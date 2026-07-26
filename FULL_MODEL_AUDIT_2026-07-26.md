# Urea Plant Dynamic Simulator — Full Mathematical, Thermodynamic, and Connectivity Audit

Date: 2026-07-26  
Audited runtime: `backend/main.py`, `backend/reactor.py`, `backend/steam_system.py`, controllers, frontend stream registry, local tests, 1750 MTPD PFD/HMB tables, and unit mapping documents.

## Superseding PDF/research remediation update

This section supersedes the original 2-pass/8-fail execution snapshot below. The original text is
retained as the pre-remediation audit trail.

**2026-07-27 328D003 closure:** The historical findings below that compartment III was absent and
physical bay II was unmodeled are closed. Owner-approved capacities are I/II/III = 18/43/429 m³;
all three communicate and III is the common accumulation baffle. The runtime now has three inventory
states, maps external process streams to physical I and II, and maps LI-328508 to physical III. See
`research_plan_328d003_compartments.md` and `MAP_328D003.md`.

Current executable result: **6 passed / 4 failed**.

Closed with source-backed implementation:

1. `328C003` now uses the Inoue/Otsuka second-order liquid law
   `ln(k_H)=21.8-11100/T` and the analytical PFR integral in live urea/water concentration. The
   direct experimental correlation is extrapolated from its published range to the Helwan 200 C
   operating point; this limitation is explicit.
2. Hydrolysis heat is explicit: Helwan Fundamentals gives -117 kJ/mol for carbamate formation and
   +15.5 kJ/mol for dehydration to urea, hence +101.5 kJ/mol for the reverse overall hydrolysis.
3. LP-header pressure always reaches the HPCC shell thermodynamic state. The exogenous-only gate no
   longer suppresses internal utility disturbances.
4. Both Unit 324 evaporators solve live pressure, temperature, VLE concentration, and vapour load as
   one bounded algebraic fixed point per dynamic tick.
5. `329D009` now includes the PFD flash-recovery source and measured makeup: stream 907 = 6,687 kg/h,
   stream 903 = 1,754 kg/h, effective recovered vapour = 4,933 kg/h. Actual `324E003` heat demand is
   debited from the header on the reverse pass.
6. Dynamic recycle tears publish a normalized residual vector, tolerance, and convergence state.

PDF disposition:

| PDF | Audit use | Disposition |
|---|---|---|
| `02 FUNDAMENTALS.pdf` | Helwan/Uhde/Stamicarbon reactions, equipment topology, hydrolyzer/desorber internals and states, steam users, Unit 335 process and 1750-2000 MTPD range | **Plant-specific primary operating basis; materially closes gaps** |
| `2017-07-Chinda-Modelling-and-simulating-the-synthesis-section.pdf` | Generic synthesis reactions and tuned kinetics | **Supporting only; fitted to another plant and omits pressure drop** |
| `Aspen urea.pdf` | SR-POLAR formulation, equilibrium/rate equation structure | **Useful architecture; proprietary fitted parameters absent** |
| `Contribution_1428_final_a.pdf` | Automotive urea application | **Out of scope** |
| `ilovepdf_merged.pdf` | Concatenation of the other seven non-Helwan PDFs | **Duplicate, no independent evidence** |
| `Modeling the synthesis section of an industrial urea plant - ScienceDirect.pdf` | Abstract/landing pages | **Insufficient; not the full article** |
| `s42004-023-00990-7.pdf` | Solid-oxide co-electrolysis | **Out of scope for conventional urea production** |
| `ureamodeling.pdf` | Urea++ high/low-pressure species and activity-model architecture | **Useful architecture; binary interaction parameters withheld** |
| `viewcontent.pdf` | Open empirical high-pressure `K1/K2` correlations and validity ranges | **Usable HP correlation evidence; not a full low-pressure property package** |
| `324F002 Datasheet.pdf` | Ejector-I design state, mass balance, line sizes, materials, and external arrangement | **Closes the vendor design point (94 + 650 = 744 kg/h), but conflicts with PFD streams 706/924/708 (72 + 390 = 462 kg/h); no internal geometry or performance curve** |
| `324F004 Datasheet.pdf` / `324F005 Datasheet.pdf` | Ejector-II/III package topology, suction composition/capacity, motives, inter/after-condenser maximum flows, final discharge state | **Closes a vendor maximum-capacity package balance to 0.5 kg/h rounding; conflicts with PFD motive allocation and lacks critical backpressure/off-design maps. Its page-7 SUEZ II 01-3040 text is a user-confirmed copied template error.** |
| `324F002 datasheet 2.pdf` | Körting mechanical GA for Ejector I, UAN 01-3042, serial `115-4-9674-8` | **Closes manufacturer/designation/serial and external arrangement; does not expose hydraulic throat/exit geometry or a performance curve** |
| `324F004 Datasheet 2.pdf` / `324F005 Datasheet 2.pdf` | Körting `AS BUILT` sectional drawings for Ejectors II/III, UAN 01-3042, serials `232-4-503-1/-2` | **Closes package provenance, substantial fabrication geometry, F004 body 0.122 bar(a)/77 °C and F005 body 0.245 bar(a)/100 °C; no certified capacity/backpressure/stability curves or test points** |

Still open, and not safely inferable from the supplied PDFs:

- Full NH3-CO2-H2O-urea ionic/non-ionic interaction parameters and standard-state functions over
  high-, medium-, and low-pressure sections.
- Canonical 163-stream runtime graph with shared enthalpy-bearing state objects.
- Unit 328 reaction/speciation enthalpy closure; the missing ionic/carbamate speciation prevents a
  defensible replacement of the remaining back-solved latent terms.
- The revised ejector drawings close final manufacturer/provenance, substantial F004/F005 fabrication
  geometry, and the F005 body operating point. They still omit unambiguous effective hydraulic inputs
  for all stages, the F004/E006 interstage pressure chain, critical backpressures, pull/correction
  curves, dryness corrections, and acceptance-test points. The issue-for-order values also conflict
  with the strict PFD. See `EJECTOR_DATASHEET_AUDIT_2026-07-26.md`.
- Helwan condenser cooling-water allocation and pressure-drop/performance curves needed for validated
  off-design vacuum-train momentum and heat transfer.
- A conservative resolution of the Unit 324 PFD conflict and a consistent 1750-MTPD Unit 335 H&MB.

## Pre-remediation executive verdict (historical baseline)

**The software is not yet compliant with the requested plant-wide modelling rules and cannot be certified as a rigorous dynamic process simulator.** It is a useful, extensively calibrated operator-training surrogate with many real inventory ODEs and several locally conservative unit models. It is not presently equivalent to an Aspen/HYSYS/Pro/II-class thermodynamic flowsheet.

The decisive failures are:

1. **No plant-wide canonical material-stream graph.** The 1750 MTPD source tables contain 163 unique non-cooling/non-granulation stream numbers; the runtime publishes 17 stream records. All Unit 323/324/328 process connections remain local scalar variables or telemetry dictionaries.
2. **No stream enthalpy state.** All 17 canonical records now explicitly report enthalpy as unknown. Energy is therefore not propagated as one conserved stream property.
3. **Component conservation fails downstream.** At the design seed the simulator reports clipping/reconciliation residuals of −170.105 kg/h in 324E001, −126.793 kg/h in 324E003, and −1.917 kg/h in 323F004.
4. **Unit 328 energy does not close.** The published envelope reads 6,653.8 kW in, 8,344.2 kW out, residual −1,690.5 kW. Reaction enthalpies are embedded in separately back-solved latent terms rather than tied to reaction extents.
5. **There is no rigorous NH3–CO2–H2O–urea thermodynamic package.** The runtime uses Antoine water saturation, anchored relative volatilities, PFD-back-solved K-values, and fitted departure correlations. No EOS/activity/electrolyte fugacity model enforces equal chemical potential.
6. **Live thermodynamic states can be deliberately suppressed.** A 4.4→6.5 bar(a) LP-header pressure step gives a thermodynamic saturation temperature of 162.1 °C while the HPCC shell remains frozen at 146.3 °C because `_disturbance_gate()` returns zero.
7. **324 evaporation equilibrium ignores its live vacuum.** At a live 324F001 pressure of 0.59349 bar(a), the solver uses `w_eq=0.9431`, evaluated at fixed 0.33 bar(a); the same correlation evaluated at the live pressure gives `w_eq=0.884866`.
8. **Steam/utility connectivity is broken.** The implemented 324E003 consumes 2,111 kW, but actual stream 903 flow into the 9-bar header is 0 kg/h against the PFD design 1,754 kg/h. Many Unit 323/324/328 steam loads do not enter the steam-header mass balances.
9. **Recycle tears are delayed, not converged.** No residual norm, tolerance, iteration counter, Wegstein/direct-substitution loop, or simultaneous nonlinear solution exists.
10. **Vacuum condensers/ejectors and most pressure drops are reduced boundaries or heuristics.** The requested heat-transfer, momentum, and phase-equilibrium equations therefore cannot be verified on all equipment.

The executable audit is `backend/audit_model_compliance.py`. Pre-remediation result: **2 passed, 8 failed**.

## 1. Audit basis and method

### 1.1 Authoritative plant sources

- `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`
- `References/Mapping of Evaporation Section.md`
- `References/Mapping of Desorber Hydrolyzer unit.md`
- `References/329-1 mapping and description.md`
- `References/Unit_321_Mapping.md`
- Local mechanical/process references cited by the existing model and prior audits

The combined 1750 MTPD tables contain:

| Reference section | Stream columns |
|---|---:|
| Unit 20 synthesis/recovery | 37 |
| Unit 21 evaporation | 41 |
| Unit 22 desorption/hydrolysis | 44 |
| Unit 26 steam/condensate | 56 |
| Unit 27 steam annex | 13 |
| Unique, excluding cooling-water and 2000-MTPD granulation tables | **163** |

### 1.2 External technical benchmark

- IDAES control-volume documentation treats material, energy, and momentum balances, StateBlocks, property packages, ReactionBlocks, phase equilibrium, and dynamic holdup as the common foundation of unit models: <https://idaes-pse.readthedocs.io/en/stable/explanations/components/unit_model/control_volume.html>
- IAPWS-IF97 is the industrial water/steam formulation and provides internally consistent saturation, density, heat capacity, enthalpy, and entropy properties: <https://iapws.org/documents/release/IF97-Rev>
- Inoue, Otsuka, and Kanai's urea hydrolysis paper reports a **second-order** hydrolysis reaction and a rate constant approximately doubling per 10 °C: <https://www.jstage.jst.go.jp/article/kakoronbunshu1953/37/7/37_7_732/_article/-char/en>
- Inoue–Kanai's cited synthesis work is an equilibrium study, not the separable fitted correlation currently implemented: <https://doi.org/10.1246/bcsj.45.1339>

### 1.3 Verification performed

- Static trace from every source module through `step_sim()` and the returned telemetry packet.
- PFD and mapping cross-check of stream sources, destinations, flows, temperatures, pressures, and utility connections.
- Runtime design-point mass/component/energy probes.
- Off-design pressure, phase-equilibrium, and propagation probes.
- Existing regression-test collection and bounded test groups.
- Search for recycle iteration, convergence metrics, property-package interfaces, fugacity/activity equations, and canonical stream/equipment classes.

## 2. Solver and software architecture

| Requirement | Implemented state | Verdict |
|---|---|---|
| Sequential-modular directed graph | A fixed procedural order exists inside the ~2,600-line `step_sim()` function. No explicit graph object exists. | **Partial** |
| Stream as conserved state carrier | `make_stream()` creates display dictionaries after the process calculation. They do not drive downstream units. | **Fail** |
| Stream vector `[T,P,F,x,H]` | T, P, totals, component flows, and fractions are exposed for 17 records; enthalpy is unavailable. | **Fail** |
| Unit-operation object with equations and ports | No common unit interface. Unit equations are interleaved local expressions in `step_sim()`. | **Fail** |
| Dirty/listener propagation | No `is_dirty`, event listeners, dependency scheduler, or invalidation graph. Every tick recomputes the procedure. | **Fail** |
| Sequential recycle convergence | One-tick values in `s.tlag`; no within-tick tear iteration or convergence test. | **Fail** |
| Equation-oriented DAE solve | No assembled residual vector, Jacobian, sparse nonlinear solver, or algebraic constraint solve. | **Not implemented** |
| Dynamic inventories | Many vessels integrate total mass and temperature with explicit Euler; some pressure and composition states are also integrated. | **Partial pass** |
| Numerical conservation accounting | Several clamps, floors, and normalization steps do not publish the mass/energy source they introduce. | **Fail** |

Sequential modular is an appropriate architecture for this trainer, but only if each module consumes and produces a canonical state and every algebraic recycle is converged or explicitly represented as physical transport inventory. A previous-tick value is not a convergence algorithm.

## 3. Core-equation compliance

| Rule | Evidence | Verdict |
|---|---|---|
| Overall dynamic mass balance | Many vessels use `dM/dt = Σm_in − Σm_out`. Floors such as `max(M,1)` can add mass without a residual. Several utility/ejector streams disappear from the connected envelope. | **Partial / fail plant-wide** |
| Component balance | Unit 322 reactions are atom-conserving. Downstream species are advanced separately from total mass, clipped, normalized, and sometimes pinned by `sol_pin_strength()`. Measured residuals remain. | **Fail** |
| Energy/enthalpy balance | Local `m·cp·ΔT + Q − m_vap·λ` ODEs exist. Shared stream enthalpy is absent; reaction heat is often implicit; Unit 328 residual is −1.6905 MW. | **Fail** |
| Phase equilibrium `fᵢᴠ=fᵢᴸ` / `yᵢ=Kᵢxᵢ` | Relative-volatility and Rachford–Rice forms exist, but K-values are design-back-solved and no fugacity/activity package enforces chemical-potential equality. Some VLE calls use fixed design pressure. | **Fail** |
| EOS/activity model | No Peng–Robinson, SRK, NRTL, UNIQUAC, electrolyte-NRTL, or equivalent package for the reacting carbamate solution. | **Fail** |
| Chemical equilibrium | No Gibbs minimization or temperature-dependent equilibrium-constant constraints for carbamate/urea reactions. | **Fail** |
| Reaction kinetics | Biuret/hydrolysis Arrhenius-like terms exist. Reactor conversion is a refitted equilibrium surrogate, not a rate law. 328C003 uses first-order PFR conversion without documenting or validating a pseudo-first-order reduction from the cited second-order source. | **Fail** |
| Heat transfer | Several heaters use `Q=UA(Tsat−T)` and some exchangers use effectiveness/NTU. No LMTD models for the required train; vacuum condensers are missing; several UAs are single-point back-solves. | **Partial / fail plant-wide** |
| Momentum/pressure drop | Some valves/pumps use head or `√ΔP`. Steam valves use an incompressible orifice law; columns/pipes/ejectors lack rigorous compressible, packed-bed, Darcy, or choked-flow models. | **Fail** |
| Fraction summation | Published fraction vectors generally sum to one. Normalization can hide an underlying component imbalance and therefore is not proof of conservation. | **Pass summation only** |
| Property correlations | Water `cp` and steam saturation correlations plus urea-solution `cp/ρ` departures exist. Viscosity, conductivity, mixture enthalpy, fugacity, and most live densities are absent. | **Partial** |

## 4. Equipment-by-equipment disposition

Legend: **P** = adequate for present reduced scope; **R** = reduced/calibrated; **F** = missing or invalid against the requested rule.

| Equipment / connection | Mass/components | Energy/thermo | Momentum/rate | Connectivity | Disposition |
|---|---|---|---|---|---|
| 321D003 NH3 drum | Total inventory ODE; effectively pure NH3 | Adiabatic sensible-energy ODE; Antoine NH3 vapor pressure | No full two-phase equilibrium | Feed/suction canonical | **R** |
| 321P002 A/B | Flow derived from displacement and speed | Pump temperature/power surrogate | Positive-displacement model; limited cavitation physics | Connected to ratio/ejector path | **R/P** |
| XV-321901 / XV-322901 | Boolean mass gates | No enthalpy loss | No valve characteristic | Connected | **R** |
| 320K002 CO2 line / PV-322203 | PFD impurity composition and total flow | Fixed feed temperature | `√ΔP` delivery/vent split; no compressor map | Connected to stripper; live registry pressure fixed by this audit | **R** |
| 322F001 HP ejector | Motive/suction/output mass constructed | Mixed-temperature surrogate | Momentum-flux/equal-percentage correlations, not a full ejector map | Connected within synthesis loop | **R** |
| 322E002 HPCC | Component split and sump level | Calibrated flash and ε-NTU-like duty | Pressure is bubble surrogate/state lag | Connected in HP loop; LP utility response can be gated | **R/F** |
| 322R001 reactor | Atom-conserving urea/biuret stoichiometry | Four-node fitted temperature profile; no explicit `ξΔH` balance | No rigorous reaction-rate/residence distribution | Recycle tear and hydraulic outlet present | **R/F** |
| 322E001 stripper | Total/component balances and extents | Per-species duty proxy with fixed/reference heats | Flood/level/valve surrogates; no rigorous column MESH stages | Connected to Unit 323 | **R** |
| 322E003 HP scrubber | Conservative split at anchor | CCW effectiveness and reaction-duty surrogate | Vent/back-pressure heuristic | Connected to ejector and 322C001 | **R** |
| LV-322501 / HV-322602/604/605 | Flow authority exists | Simplified JT/sump effects | Empirical valve laws | Connected | **R** |
| 323C003 + 323E002 | Total/species/level ODEs | UA duty and bubble-point departure | Pressure target is a calibrated flow relation | Connected from stripper | **R** |
| 323F004 | Flash total/species ODE | Adiabatic flash proxy | Pressure target from vapor flow | −1.917 kg/h component residual | **F** |
| 323E010 + 323F010 | Two feeds (319 + 331), duty-limited evaporation | UA duty; bubble target uses fixed 0.46 bar(a) | Vacuum heuristic | Connected to 323D002 | **R/F** |
| 323D002 | Two-compartment total/species inventory | Temperature ODE | Pump draws simplified | Feeds Unit 324 | **R** |
| 323E003 / E011 / D011 / C005 | Lumped balances and several recycle paths | Back-solved latent/UA terms | Calibrated pressure lags | 324F002 discharge stream 708 is not an inlet to C005 | **F** |
| 324E001 + 324F001 | Total and species ODEs | UA duty; equilibrium evaluated at fixed 0.33 bar(a) | Hydraulic drain and heuristic ejector pull | −170.105 kg/h component residual | **F** |
| 324E003 + 324F003 | Total and species ODEs | UA duty; equilibrium evaluated at fixed 0.131 bar(a) | Heuristic vacuum | −126.793 kg/h component residual; 9-bar steam draw disconnected | **F** |
| 324E002 / E005 / E006 / E007 | Aggregate condensate sink only | No individual Q, UA, LMTD, phase split, or CW state | No pressure-drop model | Aggregate lag to 328D003 only | **F** |
| 324F002 / F004 / F005 | Motive handles influence pull | No mixing/condensation enthalpy | Pull proportional to motive and suction pressure; no entrainment/compression map | Motive/discharge masses not closed through downstream train | **F** |
| LIC-324501 / UF85 / 335 boundary | Outlet/additive totals exist | No downstream thermal state | Valve-span surrogate | Unit 335 is not modeled; stream 331 return is an external constant | **F plant-wide** |
| 328D003 / 328V001 | Compartments I/II total and reduced species | Back-solved formation heat | Pump/flow-controller surrogates | Compartment III and stream 341 absent | **F** |
| 328E007 | Total pass-through | Fixed effectiveness/loss, bounded temperatures | No pressure drop | Internal hot/cold scalar link | **R** |
| 328C002 | Total/species ODE, overhead/bottoms | Lumped volatility and bubble-temperature surrogate | Pressure gain calibrated | Four scalar inlet tears, no recycle convergence | **R/F** |
| 328C003 hydrolyzer | Urea extent enters species balance | Reaction heat hidden in latent term | First-order PFR Arrhenius form is unreconciled with the cited second-order source | Connected to C002/C004 | **F** |
| 328E021 A/B | Balanced hot/cold sensible duty | Effectiveness plus fixed shell loss | No LMTD/pressure drop | Connected | **R** |
| 328C004 | Total/species ODE | Lumped volatility and steam duty | Pressure gain calibrated | Connected by delayed tears | **R/F** |
| 328D001 + 328E004 | Drum mass and pressure states | Condenser duty linear in TIC stroke; implicit reaction/condensation heat | No condenser UA/LMTD | Connected to C002/323E011 | **F** |
| 322C001 absorber | Total/species inventory and vent split | Back-solved absorption enthalpy | Pressure/vent surrogate | Connected to D003/V001 but incomplete species recovery | **R/F** |
| 328P002/003/004/006/007/008 | Mostly pass-through/flow-control scalars | No shaft-energy coupling | No pump curves/NPSH | Routes partly represented | **R/F** |
| 329D005 HP steam system | Header/level mass ODEs | Fixed steam enthalpy constants; no header enthalpy ODE | Incompressible steam-valve flow | Stripper draw coupled | **R/F** |
| 329D009 9-bar system | Header/level ODE | Saturation T from P | Incompressible valves | Implemented 324E003 demand absent; stream 903 = 0 | **F** |
| 322D001 LP steam system | Header/level ODE | HPCC generation coupled; many downstream loads absent | Incompressible valves and calibrated capacitance | Unit 323/324/328 loads not mass-connected | **F** |
| Cooling-water consumers | 322E003 loop modeled | Reduced ε-NTU | Pump/header network incomplete | Only two canonical CCW records vs 39 PFD cooling streams | **F plant-wide** |

## 5. Flowsheet and ripple-effect audit

### 5.1 Connections that propagate

- NH3/CO2 feed → HP synthesis loop → stripper → Unit 323 is procedurally ordered.
- Unit 323 product composition reaches Unit 324.
- Aggregate Unit 324 condensable load reaches 328D003 one tick later.
- Unit 328 internal C002/C003/C004/D001 scalar tears exchange flow and composition.
- A one-tick reactor-overflow composition pulse touched telemetry in every unit group within 60 simulated seconds.

Measured pulse result:

| Group | Numeric leaves moved | Total leaves |
|---|---:|---:|
| Unit 322 | 151 | 431 |
| Unit 323 | 61 | 249 |
| Unit 324 | 3 | 72 |
| Unit 328 | 6 | 113 |
| Unit 329 | 8 | 53 |
| Entire packet | 231 | 1,192 |

This proves some forward sensitivity, not accurate whole-plant propagation. Only 19.4% of numeric leaves moved, Unit 324 had 3/72 responding leaves, and utility/thermodynamic gates can suppress valid internal disturbances.

### 5.2 Broken or reduced connections

1. **Steam users:** Unit 323 heaters, 324E001/E003, vacuum ejector motives, 328C004 steam, and other loads do not all enter the appropriate 9-bar/4-bar header balance.
2. **324 vacuum train:** per-condenser condensate, vent, motive steam, cooling water, and pressure nodes are collapsed into one boundary.
3. **Stream 708:** the PFD closes 706 (72 kg/h) + motive 924 (390 kg/h) = 708 (462 kg/h) to 323C005. The runtime C005 inlet is `mv011_prev + makeup`; stream 708 is absent.
4. **Unit 335:** final finishing/granulation is a boundary. Stream 331 is injected as a fixed external recovery stream rather than produced by a modeled downstream unit.
5. **328D003:** compartment III and stream 341 remain absent.
6. **Canonical stream graph:** scalar/local-variable transfer prevents automatic route validation, conservation traversal, and dirty propagation.

### 5.3 Recycles

The runtime reads prior-tick values such as `R328_748`, `R328_750`, `R328_775`, `R3232_718A/B`, `R3232_744`, `R324_COND`, and `R324_recyc`. It never iterates these algebraic tears inside a flowsheet solve. There is no convergence packet or norm.

For a true physical inventory with a documented transport residence time, a dynamic delay can be correct. For an algebraic recycle, the required implementation is:

1. Guess tear state `[F,T,P,z,h]`.
2. Execute the directed loop.
3. Form scaled component/temperature/pressure/enthalpy residuals.
4. Update by direct substitution/Wegstein/Broyden/Newton.
5. Stop only when all residuals meet tolerance; publish iteration count and failure state.

## 6. Numerical evidence

Run:

```powershell
cd backend
python audit_model_compliance.py
```

Pre-remediation evidence:

| Probe | Result |
|---|---|
| Required stream schema fields present | Pass |
| Canonical record coverage | 17 runtime records vs 163 unique in-scope reference stream numbers — fail |
| Stream enthalpy | 0/17 calculated — fail |
| Downstream component closure | C003 0; F004 −1.917; F010 0; E001 −170.105; E003 −126.793 kg/h — fail |
| Unit 328 energy closure | 6,653.8 in; 8,344.2 out; −1,690.5 kW residual — fail |
| Recycle convergence metric | Absent — fail |
| Live CO2/stripper registry pressure | Pass after source-safe correction |
| LP-pressure → HPCC-shell propagation | `g=0`, 6.47 bar(a), `Tsat=162.1 °C`, shell `146.3 °C` — fail |
| 324E001 live-pressure VLE | live P 0.59349, used 0.9431, live-P result 0.884866 — fail |
| 9-bar implemented demand | stream 903 actual 0 vs PFD 1,754 kg/h while 324E003 duty is 2,111 kW — fail |

## 7. Source-safe corrections applied during this audit

1. `make_stream()` now retains calculation-precision component molar/mass flow vectors.
2. Stream enthalpy fields are explicit and nullable; the UI displays “not modelled” instead of implying the state is complete.
3. Canonical CO2 feed pressure now uses the solved live line pressure.
4. Canonical stripper top/bottom pressures now use the live stripper pressure already calculated by the unit.
5. LP-header `TI_sat` now comes from the live pressure; the disturbance-gated HPCC shell temperature is published separately as `TI_HPCC_shell`.
6. Regression tests protect those corrections in `backend/test_audit_stream_state.py`.
7. `backend/audit_model_compliance.py` provides a repeatable red/green closure gate for the open mathematical requirements.

No property constants, reaction parameters, exchanger/ejector performance, or missing plant streams were invented.

## 8. Required remediation plan

### Phase 0 — Resolve authoritative data and scope

Required before physical implementation:

- Decision on Unit 324 urea conservation versus rounded PFD stream rows.
- Licensor species/phase basis and NH3–CO2–H2O–urea thermodynamic package or validated parameter set.
- Urea synthesis equilibrium/rate model and heat-of-reaction data over the operating range.
- 328C003 second-order rate expression, concentration basis, parameters, and residence/dispersion model.
- 324 vacuum-condenser duties/UA/areas/CW flows, ejector motive/suction/discharge performance maps, and non-condensable load data.
- Pipe/valve/pump/column pressure-drop data and equipment geometry where absent.
- Unit 335 scope and a consistent 1750-MTPD source, or an explicit validated boundary contract.

### Phase 1 — Canonical model kernel

- Introduce a `MaterialStream` state with unrounded `[T,P,phase,F_i,h,ρ]`, derived fractions, validity flags, and source provenance.
- Introduce unit ports and a directed flowsheet graph.
- Make every downstream unit consume the same stream object produced upstream.
- Keep telemetry as a view of states, not the states themselves.
- Build a plant-wide stream registry covering every in-scope PFD stream and explicit battery-limit boundary.

### Phase 2 — Thermodynamics and reactions

- Implement one validated property interface for fugacity/activity, phase enthalpy, density, `cp`, viscosity, and thermal conductivity.
- Use IAPWS-IF97 for water/steam properties.
- Use the approved electrolyte/reactive model for the urea synthesis/recovery solution.
- Replace fitted “equilibrium-like” reactor conversion with approved chemical equilibrium or kinetic equations.
- Tie every reaction enthalpy to the same extent used by the component balance.

### Phase 3 — Conservation closure

- Replace `sol_pin_strength()` and unaccounted normalization with a constrained component balance.
- Convert every clamp/floor to a bounded physical event plus a published numerical source/sink residual.
- Close Unit 328 energy with explicit carbamate formation/decomposition and hydrolysis heats.
- Require plant-wide total mass, elemental/component mass, and energy residuals at every tick.

### Phase 4 — Equipment and utility completion

- Model the four vacuum condensers and three ejectors as connected mass/energy/momentum units.
- Connect all 9-bar/4-bar steam users and condensate returns to Unit 329.
- Add LMTD/ε-NTU models with live two-side states and pressure drop to every exchanger.
- Add compressible/choked steam-valve equations and validated ejector maps.
- Complete 328D003 compartment III, stream 341, and the missing 708→323C005 route.
- Complete Unit 335 or formalize the boundary and recycle contract.

### Phase 5 — Solver and ripple assurance

- Retain sequential modular for deterministic OTS timing.
- Topologically order acyclic modules.
- Add tear-stream iteration with scaled residuals, tolerances, iteration limits, acceleration, and failure handling.
- Distinguish physical transport lags from numerical tear delays.
- Remove `_disturbance_gate()` after stabilizing the actual coupled physics; no valid state variable may be ignored because operator handles did not move.
- Add steady-state initialization of the dynamic DAE/ODE state before scenarios.

### Phase 6 — Verification and acceptance

- Design-point stream-by-stream PFD comparison on mass, components, T, P, phase, density, and enthalpy.
- Unit and plant envelope residual tests at design, turndown, trips, and recovery.
- Finite-difference sensitivity matrix proving each upstream disturbance reaches every physically dependent downstream state with correct sign and time scale.
- Recycle-convergence tests and non-convergence alarms.
- Independent thermo-package regression against published/reference calculations.
- Long-horizon inventory and energy-drift tests.

## 9. Test status

- Pytest collection before the three new audit tests: 231 tests in ~22 s.
- Confirmed passing bounded groups: 159 existing tests.
- New source-safe stream-state tests: 3 passed.
- Unique confirmed pass count: **162**.
- Full suite: exceeded the 244 s hard limit twice without producing a final result.
- Warnings: deprecated FastAPI `on_event`, deprecated TestClient/httpx path, and pytest cache-path collision.

Existing passing tests demonstrate that many calibrated anchors and local dynamics behave as coded. They do not establish MESH compliance because several tests assert the fitted surrogate itself rather than an independent physical/property reference.

## 10. Certification statement

The present release may be described as a **calibrated dynamic operator-training model with partial conservation and partial flowsheet propagation**. It must not be described as fully MESH-compliant, thermodynamically rigorous, globally conservative, or fully connected until the eight executable compliance failures and the data-blocked gaps in `handoff.md` are closed.
