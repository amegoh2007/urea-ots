# Plant-Wide Thermodynamic, MESH and Ripple-Effect Audit

**Date:** 2026-08-27
**Subject:** Urea OTS — 1,750 MTPD Stamicarbon CO₂-stripping plant simulator
**Method:** All findings below were produced by executing the live engine (`backend/main.py`) and reading the source. Nothing is inferred from module docstrings or from prior audit reports.

---

## Executive Summary

The simulator's conservation mathematics are sound: component balances, energy closure, composition constraints and recycle tears all hold at or near machine precision, including under extreme off-design perturbation. Reaction kinetics respond correctly and stay bounded by their thermodynamic ceiling. A +5 % CO₂ feed step propagates through all six sections with the correct sign and magnitude.

Three findings require action. In order of severity:

1. **The Extended UNIQUAC electrolyte model is not in the running engine.** `props_nh3co2h2o.py` and `vle_nh3co2h2o.py` are never imported at runtime. Every ionic-section bubble point (323C003, 323F004, 328C002, 328C004) is computed from the **pure-water IAPWS saturation line plus a frozen design offset** — the exact scheme `project.md` claims was replaced. This is a documentation defect, not a physics regression: the simulator is internally consistent and design-anchored. But the project documentation currently overstates the thermodynamic rigour of five unit operations.

2. **Stream enthalpy is not populated.** All 55 canonical streams carry the `enthalpy_kJkg` and `enthalpy_flow_kW` keys, and all 55 are `None`. A per-stream enthalpy balance — explicitly requested in this audit's Phase 2 — cannot be computed. Section-level energy closure is unaffected and does close.

3. **One timing path bypasses transport lag.** The 324E001 evaporator liquid temperature begins moving 1 s after a CO₂ feed step, reached through the shared steam header rather than through the liquid path. The liquid path itself lags correctly (28–72 s). A 180 s-residence liquid inventory should not begin responding in 1 s.

No mass or energy is created or destroyed anywhere in the flowsheet, and no solver divergence or oscillation was observed.

---

## Phase 1 — Thermodynamic Model Verification

### 1.1 What is actually loaded

Runtime module check after `import main`:

```
vle_nh3co2h2o loaded at runtime:        False
props_nh3co2h2o loaded at runtime:      False
thermo_extended_uniquac loaded:         True
iapws_if97 loaded:                      True
```

`props_nh3co2h2o.py` (the full Thomsen-Rasmussen / Darde Extended UNIQUAC electrolyte model — combinatorial, residual, extended Debye-Hückel, SRK fugacity, R1–R5 speciation) is referenced exactly once in `main.py`, in a comment at line 1058. It has no live caller. Its own docstring is candid about this: *"STANDALONE — nothing in this module is wired into `main.py`."*

`vle_nh3co2h2o.py` has no caller anywhere outside its own test file.

### 1.2 Unit-to-model matrix (as built)

| Unit | Regime | Method actually used | Source |
|---|---|---|---|
| 322R001 reactor | 140–145 bar, 172–183 °C | Modified Inoue-Kanai separable conversion kinetics | `reactor.py` |
| 322E001 HP stripper | 141 bar, 187 °C | `eta_T` thermal-efficiency factor + Arrhenius biuret/hydrolysis extents; no VLE flash | `main.py` |
| 322E002 HPCC | 144 bar, 170 °C | `bubble_p_322e002()` — hand-rolled correlation, fN-anchored so P_bub = 144.2 bar at design | [main.py:3478](backend/main.py:3478) |
| 322E003 HP scrubber | 141 bar | Component-wise absorption capacity from design split | `main.py` |
| 322F001 ejector | 144 bar | Normalised equal-percentage spindle entrainment | `main.py` / `ejector_huang.py` |
| 323C003 MP column | 4.1 bar, 122 °C | `T_bub = T_design + (tsat_steam(P_live) − tsat_steam(P_design))` | [main.py:5887](backend/main.py:5887) |
| 323F004 MP flash | 3.2 bar, 106 °C | Same pure-water form | [main.py:5940](backend/main.py:5940) |
| 328C002 / 328C004 | 1–4.1 bar | `tsat_steam(P + ΔP_col,design)` | [main.py:6337](backend/main.py:6337), [main.py:6450](backend/main.py:6450) |
| 324E001 / 324E003 evaporators | 0.02–1.0 bar, 130–140 °C | Neutral H₂O/urea UNIQUAC (Voskov-Voronin), anchored-departure form | [main.py:113](backend/main.py:113) |
| 329 steam network, all steam shells | 5–25 bar | IAPWS-IF97 R7-97 Regions 1/2/4 | `iapws_if97.py` |

`core/thermo.py EmpiricalThermo.bubble_p` returns the placeholder `140.0 + (T_c − 170.0) * 0.5` and is **never called** — a grep for `.bubble_p(` across `core/` and `main.py` returns no live call site. Only its two viscosity methods are used ([main.py:5128](backend/main.py:5128)). The placeholder is dead code and should be deleted or raised to `NotImplementedError` so it cannot be mistaken for an active fluid package.

### 1.3 Documentation conflict

`project.md` §5.1 states that `vle_nh3co2h2o.py` is *"Wired into the live engine … turns it into the bubble-point service for the 323C003 rectifying column and the 323F004 flash tank (both previously ran on a pure-water saturation line with a frozen offset) and supplies the 328D003 ammonia-water vapour pressure."*

Verified against source: all three still run the pure-water saturation line with a frozen offset. The claimed replacement did not happen. `handoff.md` compounds this by asserting "3 fluid packages validated" and citing `COMPREHENSIVE_AUDIT_REPORT.md`, which is deleted from the working tree.

### 1.4 Package boundary integrity

The only genuine package transition is 323 MP → 324 vacuum, where the method changes from IAPWS-anchored to neutral UNIQUAC. This coincides with a real chemistry change: after MP/LP decomposition, PFD stream 314 is ~80 mol % urea / 19 % H₂O with under 1 % NH₃ and CO₂ — a neutral binary, so the Debye-Hückel term is legitimately zero. Both sides use anchored-departure form, so the design state is bit-exact on both sides of the handoff and no enthalpy or mass is created there. The Unit 324 application (0.02–1.0 bar) sits 35–1750× below the published 35–450 bar validation floor; the code labels this honestly and machine-readably as `DESIGN_ANCHORED_EXTRAPOLATION` ([thermo_extended_uniquac.py:69](backend/thermo_extended_uniquac.py:69)).

**Verdict:** model assignment is internally consistent, design-anchored, and adequate for operator training. It is *not* the rigorous electrolyte-EoS architecture the documentation describes.

---

## Phase 2 — MESH Equation and Conservation Validation

### 2.1 Component and energy balance closure

Design steady state, live packet:

```
Component balance residuals, 323/324 (clip_resid_kgh)
  C003  +0.000e+00 kg/h      F004  +0.000e+00 kg/h
  E001  +0.000e+00 kg/h      F010  +0.000e+00 kg/h
  E003  +0.000e+00 kg/h
  Max abs 0.0  ->  PASS (tolerance 1e-6)

Unit 328 energy ledger (kW, reference 0 °C, envelope C002/C003/C004/D001/E021/E007)
  Q328_in    6653.8
  Q328_out   8344.2
  Q328_react (explicit carbamate-desorption enthalpy, separate ledger term)
  Q328_resid    0.0  ->  PASS (tolerance 1.0 kW)
```

The in/out figures do not appear to sum because the residual is `q328_raw + q328_react` ([main.py:6564](backend/main.py:6564)) — reaction enthalpy is a third term. The ledger closes; the two emitted tags are a subset of it, which is worth noting for anyone reading those tags in isolation.

**A per-stream enthalpy balance could not be run.** All 55 streams report `enthalpy_kJkg = None` and `enthalpy_flow_kW = None`, while `T_C`, `P_bara`, `mass_kgh` and `mol_kmolh` are populated 55/55. The compliance harness flags this as a hard fail.

### 2.2 Recycle tear convergence

```
method:                 observed_dynamic_transport_tears
settled:                True
max relative residual:  1.4932e-15
is_solver_convergence:  False        <- honest label
  323D011_return_718A    0.000e+00
  328C003_overhead_748   0.000e+00
  328C004_overhead_750   0.000e+00
  328C004_steam_931      0.000e+00
  328D001_reflux_775     1.493e-15
```

This is architecturally significant and correct. `CLAUDE.md` describes Sequential-Modular tearing with iterative convergence, but this is a *dynamic* simulator: tears are one-tick transport delays and steady state is reached by ODE integration, not by an inner Newton loop. The engine does not claim otherwise — `is_solver_convergence: False` is deliberate. No divergence or sustained oscillation was observed in any run.

### 2.3 Reaction kinetics response to T, N/C and H/C

Inoue-Kanai conversion, design N/C = 3.072961, H/C = 0.407828, T_opt(L_des) = 187.15 °C:

```
T (°C)    163      173      178      183      188      193      203
X (%)   23.24    41.27    49.15    54.30    55.66    52.93    38.22
```

The parabola peaks at T_opt and falls on **both** sides — correct, and the failure mode a monotone stand-in would have produced is absent. Conversion rises monotonically with N/C (+4.78 % at N/C × 1.1) and falls monotonically with H/C water penalty (−4.90 % at H/C × 1.2).

Thermodynamic ceiling guard under extreme drive: `X(N/C × 3, H/C × 0.1, T = T_opt) = 91.9600 %`, exactly `X_INF = 0.9196`. The ceiling is enforced, not merely approached.

Arrhenius path (`STRIP_BIU_EA = 85 000 J/mol`, R = 8.314): 328C003 hydrolysis conversion is monotone increasing in temperature — 0.6609 at 160 °C, 0.9649 at 180 °C, 0.99992 at 200 °C, 1.0000 at 220 °C.

### 2.4 Constitutive constraints (Σxᵢ = 1) under off-design stress

Four states tested, 55 composition-bearing streams each:

| State | Max \|Σxᵢ − 1\| | Streams over 1e-12 |
|---|---|---|
| Design steady state | 1.11e-16 | 0 |
| CO₂ feed collapsed to 10 % (200 s) | 2.22e-16 | 0 |
| CO₂ feed +40 % overload (200 s) | 1.11e-16 | 0 |
| HV-322605 shut, reactor drain blocked (300 s) | 2.22e-16 | 0 |

Composition normalisation holds at floating-point epsilon in every case, including with the reactor drain valve fully closed. Off-design, some packet percentage dictionaries display 99.999 or 100.001 — that is `round(..., 3)` display rounding on the emitted tag, not a balance error, since the underlying component sums remain at 1e-16.

---

## Phase 3 — Ripple Effect and Dynamic Lag

### 3.1 Feed perturbation

+5 % CO₂ feed step, 54.62 → 57.35 t/h:

| Quantity | Design | After step | Change |
|---|---|---|---|
| Load | 100.0 % | 105.0 % | +5.0 % (exact 1:1) |
| Reactor X_conv | 54.27 % | 53.83 % | −0.8 % (dilution) |
| Stripper TT-322013 | 187.0 °C | 183.0 °C | −4.0 °C (more mass, same duty) |
| Stripper bottoms | 130.90 t/h | 129.55 t/h | −1.0 % |
| 324E001 TT-324001 | 132.6 °C | 129.7 °C | −2.9 °C |
| 324E001 urea | 94.20 % | 93.80 % | −0.40 % |

Every sign is physically correct. The NH₃-side counterpart of this test already exists as `backend/test_1_nc_shift.py`.

### 3.2 Measured lag at downstream nodes

Step applied at t = 0, dt = 1.0 s, 900 s window. Dead time = first excursion past 2 % of the total step; τ63 and t95 as usual.

| Node | Δ | dead time (s) | τ63 (s) | t95 (s) |
|---|---|---|---|---|
| CO₂ FY-322403 | +2.730 t/h | 1 | 1 | 1 |
| Reactor TT-322008 (bottom) | +0.40 °C | 4 | 10 | 13 |
| Reactor X_conv | +0.17 % | 1 | 346 | 893 |
| Reactor LT-322504 | +6.20 % | 16 | 700 | 870 |
| Stripper bottoms flow | −1.35 t/h | 1 | 1 | 1 |
| Stripper TT-322013 | −4.00 °C | 4 | 505 | 734 |
| HPCC TT-322010 | +0.50 °C | 5 | 27 | 41 |
| 323C003 TT-323002 | −0.90 °C | 2 | 86 | 100 |
| 323F004 TT-323005 | −0.50 °C | 163 | 700 | 837 |
| 324E001 TT-324001 | −2.90 °C | 1 | 402 | 590 |
| 324E001 urea % | −0.40 % | 5 | 50 | 53 |
| 324E003 TT-324002 | −1.80 °C | 38 | 248 | 439 |
| 328D003 TT-328I | +0.10 °C | 550 | 550 | 550 |

Three nodes need interpretation rather than a number:

- **Stripper LI-322501** ends at exactly its starting value, which looks like no response but is not. A finer probe shows it dipped to 49.9 % at t = 72 s and LIC-322501 (AUTO, SP 50.0) drove it back to setpoint. The controller is working; the endpoint simply hides the excursion. LV-322501 opened from 46.3 % to 45.6 %.
- **Reactor TT-322005 (top node)** and **HPCC TT-322012** showed no movement at the 0.1 °C resolution of the emitted tag. Whether the underlying state moved by less than that quantum was not determined and would need an unrounded probe.
- **328D003 TT-328I** moved by exactly one 0.1 °C display quantum, so its three timing figures collapse to the same number and none of them is meaningful.

### 3.3 Causal ordering — where the fast response comes from

First-movement times, same step:

```
324E001 steam-chest pressure    1 s     4.25 -> 3.91 bar
324E001 liquid temperature      1 s   132.60 -> 129.80 °C
323C003 feed                   11 s   130.94 -> 128.98 t/h
324E001 feed                   28 s    92.75 ->  92.87 t/h
LV-322501 opening              62 s    46.30 ->  45.60 %
LI-322501                      72 s    50.00 ->  49.90 %
```

The **material path lags correctly**: the disturbance takes 28–72 s to reach the 324 feed and the stripper drain valve, which is consistent with the modelled inventories (reactor total residence `REACT_TAU_TOT_MIN` ≈ 44.9 min, separator holdups `R324_F001_M_TAU_S` = 180 s, and the `FEED_TD_S` = 345 s feed dead time at [main.py:4163](backend/main.py:4163)).

The 1 s response at 324E001 arrives by a different route: the increased stripper steam draw perturbs the **shared steam header**, whose chest pressure falls immediately. A header pressure transient in about 1 s is physically defensible — pressure propagates at acoustic speed and the header is modelled as a lumped capacitance.

What is not defensible is the **liquid** temperature inheriting that 1 s dead time. TT-324001 represents a 180 s-residence liquid inventory behind a tube film; it should show a dead time on the order of the film and inventory response, not zero. The mechanism to fix this already exists in the codebase (`_delay(...)`, and `FEED_TD_S` is applied on the synthesis feed path) — it is simply not applied on the steam-coupled leg. Same pattern, smaller magnitude, at 323C003 TT-323002 (2 s dead time two sections downstream).

### 3.4 Recycle stability

Across every perturbation run — +5 %, +40 %, −90 % CO₂, and reactor drain shut for 300 s — the five tear streams stayed settled with maximum relative residual at 1e-15. No divergence, no limit cycle, no runaway integrator.

---

## Phase 4 — Diagnostics and Compliance

### 4.1 Compliance harness

`python backend/audit_model_compliance.py` → **9 of 12 checks pass.**

Passing: stream schema fields present; downstream component balances close; Unit 324 VLE routed through its declared thermodynamic boundary; 322E001 reaction extents bounded by available reactants (zero feed gives zero extent); Unit 328 energy closure; recycle tear residual observed without claiming an inner solve; LP-header pressure perturbation reaches HPCC shell temperature; 324E001 equilibrium uses the live separator pressure; 9-bar header includes implemented downstream demand.

Failing:

| Check | Evidence | Assessment |
|---|---|---|
| All in-scope PFD streams have canonical records | 55 records vs 163 PFD stream numbers | Implementation scope, not a physics violation. 34 % coverage. |
| All canonical streams carry calculated enthalpy | keys present 55/55, non-null **0/55** | **Real gap.** Blocks per-stream enthalpy balance. |
| CO₂ and stripper pressures use live solved nodes | CO2_FEED 133.5, STRIP 133.9 | Test-expectation mismatch. The CO₂ feed line legitimately sits behind PIC-322203, so it should not equal synthesis pressure. The assertion, not the model, is wrong. |

`backend/gap_g4_conservation_harness.py` fast self-test passes (atom-balance primitives, created-matter catch, null-feed pass, Jacobian live/pinned discrimination). **The engine-backed suite was not run** — it requires `--engine` and roughly 13 minutes. Anyone needing the full atom-balance sweep should run it separately.

### 4.2 Propagation trace with measured lag

```
CO2 feed +5 %  (FY-322403, t=0, dead 1 s)
   |
   |-- STEAM PATH (fast, ~1 s) ------------------------------------.
   |     stripper steam draw up                                    |
   |     -> shared header                                          |
   |     -> 324E001 p_chest  4.25->3.91 bar   dead 1 s             |
   |     -> 324E001 TT-324001  tau63 402 s    dead 1 s  <-- GAP    |
   |        (liquid T should not start moving in 1 s)              |
   |                                                               |
   '-- MATERIAL PATH (correct transport lag) ----------------------'
         322R001 reactor   TT-322008 dead 4 s, tau63 10 s
                           LT-322504 dead 16 s, tau63 700 s
                           X_conv    tau63 346 s   [tau_tot 44.9 min]
             |
             v  reactor overflow (tear, 1-tick)
         322E001 stripper  TT-322013 dead 4 s, tau63 505 s
                           bottoms flow -1.35 t/h
             |
             +--> 322E002 HPCC  TT-322010 dead 5 s, tau63 27 s
             |         |
             |         '--> recycle back to 322R001  (tear resid 1e-15, settled)
             |
             v  LV-322501 moves at 62 s  (LIC-322501 AUTO, LI back to SP by 900 s)
         323C003 column    feed at 11 s, TT-323002 dead 2 s, tau63 86 s
             |
             v
         323F004 flash     TT-323005 dead 163 s, tau63 700 s
             |
             v
         324E001 evaporator  feed at 28 s, urea% dead 5 s tau63 50 s
             |
             v
         324E003 evaporator  TT-324002 dead 38 s, tau63 248 s
             |
             v
         328D003            TT-328I +0.1 °C  (one display quantum, unresolvable)
```

---

## Corrective Actions

**1 — Reconcile documentation with the running engine (highest priority, no code risk).**
`project.md` §5.1 must stop claiming `vle_nh3co2h2o.py` supplies the 323C003, 323F004 and 328D003 bubble points. Record the as-built method: pure-water IAPWS-IF97 saturation plus frozen design offset. Reclassify `props_nh3co2h2o.py` and `vle_nh3co2h2o.py` as validated-but-unintegrated research modules. Remove the "3 fluid packages validated" claim from `handoff.md`, which also cites a report no longer in the tree.

**2 — Populate stream enthalpy.** Serialise the enthalpy the engine already computes internally into `STREAMS[*].enthalpy_kJkg` / `enthalpy_flow_kW`, or explicitly declare the fields unimplemented and drop them from the schema. Leaving 55 declared-but-null fields makes the schema check pass while the data check fails, which is the worst of both.

**3 — Apply transport lag on the steam-coupled leg.** Route the 324E001 (and 323C003) liquid-temperature response through the existing `_delay(...)` mechanism so liquid inventories cannot begin responding in 1 s. Keep the header pressure transient fast — that part is right.

**4 — Remove the dead `bubble_p` placeholder.** `EmpiricalThermo.bubble_p` returns a linear stand-in and has no caller. Delete it or raise `NotImplementedError` so it cannot be mistaken for a live fluid package.

**5 — Fix the CO₂ pressure assertion in the harness.** `audit_model_compliance.py` expects `CO2_FEED.P_bara` to track synthesis pressure. The feed line sits behind PIC-322203 and should not. Correct the test, not the model.

**6 — Lower priority.** Extend stream coverage beyond 55/163 as scenarios require; run the `--engine` conservation suite; obtain experimental validation for the Unit 324 vacuum VLE extrapolation.

---

## Verdict

Conservation mathematics, kinetics and ripple propagation are **compliant**. Balances close at machine precision, composition constraints survive extreme off-design, the reaction ceiling is enforced exactly, and recycle loops converge without oscillation.

The simulator remains fit for purpose as an operator training system. The material defects are one genuine physics-fidelity gap (instantaneous liquid-temperature response on the steam-coupled path), one missing diagnostic (stream enthalpy), and — most importantly — documentation that describes a rigorous electrolyte-EoS architecture the running engine does not have.

---

*Audit performed against the live engine on 2026-08-27. Test transcripts are reproducible from the commands recorded in each section.*
