# Urea OTS — Full Modelling-Equation Audit (all equipment tags)

Audit date: 2026-07-22 · Baseline `9025aa3` (master) · Engine `backend/main.py` (5831 L),
`backend/reactor.py`, `backend/controllers.py`, `backend/steam_system.py`.
STRICT source: `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md` (CLAUDE.md §0).

For every equipment tag the four mandated questions are answered:

| # | Question |
|---|----------|
| Q1 | Are the bound equations bound **correctly**? |
| Q2 | Is the **solver engine** (Sequential-Modular vs Equation-Oriented) the right one? |
| Q3 | Is **hybrid-modelling variability** required? |
| Q4 | Are there modelling equations **missing** that should be added and working? |

Equation categories audited per tag:
**C1** Total mass balance · **C2** Component species balance · **C3** Energy balance (enthalpy) ·
**C4** Isenthalpic / isothermal flash · **C5** EoS & activity models · **C6** Summation equations ·
**C7** Kinetics & reaction · **C8** Transport phenomena · **C9** Hydraulic & equipment-specific ·
**C10** Constitutive & physical property · **C11** Control & instrumentation (dynamic).

---

## 0. Architecture-level answers (apply to every tag)

### Q2 — Solver engine: Sequential-Modular is **CORRECT** and should stay

The engine is a strict **Sequential-Modular (SM)** flowsheet: each equipment tag is a Python
function evaluated once per tick, in physical flow order, inside `step_sim(dt)`
(`backend/main.py:3098`). Every recycle / algebraic loop is **torn with a prior-step lagged
value** — `s.tlag[...]`, `recyc_prev`, `m718B_prev`, `s.p_syn_bara`, the shadow holdups — so no
simultaneous system is ever assembled and no Newton–Raphson solve exists anywhere.

This is the right choice, and Equation-Oriented (EO) would be the wrong one here:

* The deliverable is a **real-time Operator Training Simulator**. SM gives a bounded, constant
  cost per tick with no convergence failure mode. An EO solve can fail to converge mid-transient
  and would stall the HMI — unacceptable for an OTS.
* The tear variables are **physically real dynamic states** (vessel holdups, thermal inertia,
  header pressures), not numerical artefacts. Integrating them explicitly is the physics, not a
  shortcut. dt is small relative to every process time constant (τ ≈ 6–45 min vs dt ≤ 0.25 s
  after the `STEP_CAP` fix), so the one-tick tear lag is far below instrument resolution.
* The design-anchor requirement (bit-exact reproduction of the 100 % HMB) is satisfiable in SM
  by construction — every module is calibrated so its residual is exactly zero at the seed. An EO
  formulation would reintroduce solver tolerance into a contract that demands `diffs 0`.

**Verdict: SM confirmed for all 57 tags. No tag requires EO.** The only defensible EO candidate
would be the HP synthesis loop (322E001/E002/R001/E003/F001), whose recycle is stiff — but the
`_disturbance_gate` + boot-pin mechanism already delivers the fixed point EO would compute, at
zero convergence risk.

### Q3 — Hybrid-modelling variability: **REQUIRED, and already present** — but unevenly

The engine is already a hybrid: first-principles conservation laws wrapped around calibrated
empirical layers. That is correct for a urea plant, where the NH₃–CO₂–H₂O–urea system has no
tractable closed-form VLE.

Empirical / data-driven layers currently in place:

| Layer | Where | Anchor |
|---|---|---|
| HPCC component split φᵢ | `HPCC_FRAC_GAS_DES` (main.py:1515) | design HMB |
| Stripper split fᵢ + η modifiers | `STRIP_FRAC_DES`, `g_T/g_NC/g_HC` (main.py:1453) | design HMB |
| Reactor θᵢ vapour/liquid split | `REACT_THETA_OG` (main.py:1571) | design HMB |
| Scrubber pinned discharges | `SCRUB_*_KMOLH_DES` (main.py:2140) | design HMB |
| Modified Inoue–Kanai conversion | `reactor.inoue_kanai_X` | re-fitted to plant HMB |
| Back-solved latents λ / UA | 323/324/328 blocks | design fixed point |
| Ejector negative equal-% spindle law | `EJ_SPINDLE_R` (main.py:1152) | 322F001 datasheet |
| Soft sensors (`conc_infer_324`, `ppm_infer_328701`) | main.py:66 / 136 | PFD guarantees |

**Where hybrid variability is still missing** is the substance of finding **F-6** below: the
empirical split fractions are *frozen at their design values* and carry **no state dependence**.
A split fraction is only a valid hybrid layer if it is a *function* — φᵢ(T, P, composition). As
coded, φᵢ is a constant, so the units they describe cannot respond to the very disturbances an
OTS exists to train on.

---

## 1. Findings register

Severity: **A** = wrong physics an operator can trigger from the HMI · **B** = missing equation
that limits training fidelity · **C** = cosmetic / documentation.

| ID | Sev | Unit | Category | Finding |
|----|-----|------|----------|---------|
| **F-1** | A | 323F004 | C4 Isenthalpic flash | Adiabatic-flash vapour is a **frozen split fraction** `m_701 = φ·m_314`, not an enthalpy balance. Feed temperature from Stage 1 can move ±30 °C and the flash produces identical vapour. |
| **F-2** | A | 323C003 / 323E002 | C1↔C3 | Boil-up `m_305 = φ·m_feed` is **independent of the live heater duty** `Q_e002_kw`. Shutting PV-329202 gives zero duty yet full design overhead vapour; the energy deficit is dumped into the temperature ODE. |
| **F-3** | A | 323F010 / 323E010 | C1↔C3 | Identical defect: `m_evap = φ·m_319` ignores `Q_e010_kw`. |
| **F-4** | A | 324E001 / 324F001 | C1↔C3, C10 | `p1_m = urea1_in / R324_W_EV1` pins the Stage-1 melt at **94.31 % hard**. Water removed is fixed by a constant, not by `Q_e001_kw`. Cutting Evap-I steam cannot dilute the product. |
| **F-5** | A | 324E003 / 324F003 | C1↔C3, C10 | Identical defect at Stage 2 (`R324_W_EV2` = 97.71 % hard). |
| **F-6** | B | 322E002 | C5 EoS/activity | HPCC condensation split `φᵢ = HPCC_FRAC_GAS_DES` is **invariant to shell temperature and loop pressure**. Raising LP-steam pressure changes duty and `T_prod` (via NTU) but not one mole of condensate. |
| **F-7** | B | 328C003 | C7 Kinetics | The hydrolyser carries **no reaction extent at all** — urea hydrolysis is lumped into the back-solved `R328_C003_LAM748`. Arrhenius hydrolysis kinetics exist only in the read-only `ppm_infer_328701` soft sensor, not in the mass balance. |
| **F-8** | B | 323/324/328/329 | C2 Component balance | Species tracking (`MW_COMP`, 9 components) exists **only in unit 322**. Everything downstream of LV-322501 is lumped-mass. No component balance, hence no C6 summation equations, downstream. |
| **F-9** | C | tooling | — | `scratchpad/regress.py` `os.chdir(BACKEND)` before writing `argv[1]`, so the relative gate command in CLAUDE.md §7 / handoff.md fails with `FileNotFoundError`. Gate must be invoked with an **absolute** output path. |
| **F-10** | A | 323E002, 323E010, 324E001, 324E003 | C3, C8 | **Condensing-steam heater duty is unbounded below.** `Q = UA·(Tsat(p_chest) − T)` with `p_chest` clamped to 0.02 bar a (Tsat ≈ 17.5 °C) makes a shut steam valve a *refrigerator*: probe measured the Evap-I melt driven to **22 °C** and the 323C003 column to **13.6 °C**. A condensing chest cannot remove heat — it simply stops condensing. Found by disturbance-probing the F-2..F-5 fixes; the defect pre-dates them but was masked while the boil-up ignored the duty. |

Findings previously documented but **already closed in code** (audit re-verified — do not re-report):

* 328E021 hot side is **no longer static**. `T_749` is a live energy-balance closure bounded by
  the two inlet temperatures (`main.py:3960`), using `R328_E021_LOSS_DT`. The As-Built reference
  section describing this as an open gap is stale.

---

## 2. Per-tag audit

Legend: ✔ bound correctly · ~ bound, reduced/empirical (acceptable) · ✗ defect or missing.

### Unit 321 — NH₃ feed

| Tag | C1 | C3 | C9 | C11 | Q1 | Q4 |
|---|---|---|---|---|---|---|
| 321D003 feed drum | ✔ `dM/dt = F_BL − F_pump` | ✔ adiabatic `M·cp·dT/dt` | ✔ level→volume | ✔ LIC-321501 | ✔ | none material |
| 321P002 A/B HP PD pumps | ✔ | — | ✔ `Q = V_rev·N·η_v`, affinity power, current | ✔ SIC-321950/951 CAS | ✔ | NPSH-available / cavitation trip absent (training nicety, not a defect) |
| XV-321901 / XV-322901 | ✔ boolean gate on suction/discharge | — | ✔ | ✔ | ✔ | none |

### Unit 320/322 — CO₂ feed line

| Tag | Bound | Q1 | Q4 |
|---|---|---|---|
| 320K002 → XV-322902 → PV-322203 | ✔ pressure-driven delivery: floating discharge, `√ΔP` conductances, vent-diversion split `f_to_HP = g_HP/(g_HP+g_vent)`, check-valve clamp, `FEED_TD_S = 345 s` transport lag | ✔ correct — this is a genuine hydraulic network, not a ratio | none |

### Unit 322 — HP synthesis loop

| Tag | C1 | C2 | C3 | C5 | C7 | C8 | C9 | Q1 | Q4 |
|---|---|---|---|---|---|---|---|---|---|
| **322F001** ejector | ✔ | ✔ 9-species | ✔ cp-weighted mix `T_d` | — | — | — | ✔ negative equal-% spindle `φ_sp = R^((θ_des−θ)/100)`, stall factor, gravity-head term, throat-choke cap | ✔ | motive-steam model absent (deliberate, handoff item 6) |
| **322E001** stripper | ✔ | ✔ | ~ feed-proportional duty (TD-006) | — | ✔ hydrolysis ξ_hyd, Arrhenius biuret | ✔ NTU thermal ceiling, G/L strip-cool endotherm | ✔ | ✔ | TD-006: rigorous per-species enthalpy balance + steam-limited flood regime |
| **322E002** HPCC | ✔ | ✔ | ✔ carbamate exotherm + sensible, ε-NTU quench | ✗ **F-6** frozen φᵢ | implicit carbamate | ✔ ε-NTU | ✔ | ~ | **F-6** — φᵢ must become φᵢ(T_prod, P) |
| **322R001** reactor | ✔ | ✔ exact atom conservation, `closure_resid` diagnostic | ✔ Damköhler 4-node axial profile | — | ✔ Modified Inoue–Kanai `X = X∞·f_L·f_W·f_T`, biuret | ✔ | ✔ Francis weir, narrow-band LT-322504 | ✔ **best-modelled tag in the plant** | θ(φ) HIC-322605 split modulation deferred (documented) |
| **322E003** scrubber | ✔ | ✔ | ✔ ε-NTU CCW bridge, spindle & flood chokes | — | carbamate 2:1 stoich | ✔ | ✔ | ✔ | none material |
| HV-322604 | ✔ | ✔ | ✔ | — | — | — | ✔ IEC 60534 equal-% `R^((θ−θ_des)/100)·√ΔP`, JT letdown `μ_JT·ΔP` | ✔ | none |
| HV-322602 / HV-322605 | ✔ | — | — | — | — | — | ✔ | ✔ | none |
| LV-322501 | ✔ | ✔ | ✔ post-valve flash | — | — | — | ✔ | ✔ | none |
| 322C001 LP absorber | ✔ | ✗ lumped | ✔ back-solved λ_abs | — | — | — | ✔ | ~ | see **F-8** |

### Unit 323 — LP recirculation & pre-evaporation

| Tag | C1 | C3 | C4 | Q1 | Q4 |
|---|---|---|---|---|---|
| **323C003 + 323E002** | ✔ `dM/dt` | ✗ **F-2** duty decoupled | — | ✗ | duty-limited boil-up |
| **323F004** | ✔ | ✔ ODE closes | ✗ **F-1** no flash equation | ✗ | isenthalpic flash |
| **323F010 + 323E010** | ✔ | ✗ **F-3** duty decoupled | — | ✗ | duty-limited evaporation |
| 323D002 tank | ✔ two-compartment weir spill | — | — | ✔ | none |
| 323E003 LPCC + 323D001 + 323P001 | ✔ | ✔ back-solved λ_cond, UA vs tempered water | — | ~ | `R3232_E003_Q_DES_KW = 14000` kW vs PFD 1102/1103 (55/65 °C) implying ≈ 12 703 kW — anchor conflict, left as documented |
| 323E011 + 323D011 | ✔ vapour split back-solved off PFD 718 | ✔ | — | ✔ | none |
| 323C005 + 328V001 | ✔ makeup back-solved to close 328D003 Comp I | ✔ | — | ✔ | none |

### Unit 324 — Two-stage vacuum evaporation

| Tag | C1 | C3 | C9 | C10 | Q1 | Q4 |
|---|---|---|---|---|---|---|
| **324E001 + 324F001** | ✔ urea conserved | ✗ **F-4** | ✔ false-air vs ejector-pull vacuum ODE | ✗ conc. pinned | ✗ | duty-limited evaporation + live concentration |
| **324E003 + 324F003** | ✔ | ✗ **F-5** | ✔ | ✗ | ✗ | same |
| 324F002 / 324F004 ejectors | ✔ pull ∝ motive (HIC-329605) | — | ✔ | — | ✔ | none |
| 324E002/E005/E006/E007 | ✔ boundary sinks, envelope closes | — | — | — | ~ | condensate sub-cooling not modelled (cosmetic) |
| LIC-324501 / LV-A/B | ✔ | — | ✔ span from design stroke | — | ✔ | none |
| FFIC-335406 / FIC-335405 | ✔ ratio feed-forward, off-network additive | — | ✔ | — | ✔ | none |
| PY-324201 / AY-324701 | — | — | — | ✔ frozen-γ activity inversion on `psat_water` | ✔ | **inconsistent with F-4/F-5**: the soft sensor moves off-design while the mass balance holds concentration fixed |

### Unit 328 — Desorption / hydrolysis

| Tag | C1 | C3 | C7 | C8 | Q1 | Q4 |
|---|---|---|---|---|---|---|
| 328C002 Desorber-I | ✔ | ✔ λ₇₃₇ back-solved; reboil = latent of condensing 748+750 | — | — | ~ φ₇₃₇ frozen but inflow-coupled | split should track reboil duty |
| **328C003** Hydrolyser | ✔ | ✔ λ₇₄₈ back-solved incl. endotherm | ✗ **F-7** no extent | — | ~ | Arrhenius hydrolysis extent + residence time |
| 328C004 Desorber-II | ✔ | ✔ λ₇₅₀ back-solved | — | — | ~ φ₇₅₀ frozen but steam-coupled | Kremser stripping factor (already derived for the soft sensor) |
| 328D001 + 328E004 | ✔ | ✔ λ₇₃₇_cond | — | — | ✔ | none |
| **328E021 A/B** | ✔ | ✔ ε-NTU cold side **and live hot-side energy closure** (`R328_E021_LOSS_DT`), bounded by inlet temps | — | ✔ | ✔ | **none — previously-documented gap is CLOSED** |
| 328E007 | ✔ | ✔ ε = 0.6667, loss 18.3 kW | — | ✔ | ✔ | none |
| 328D003 Comp I/II | ✔ | ✔ carbamate exotherm λ_I back-solved | — | — | ✔ | none |
| 328P003/006/007 | ✔ | — | — | — | ✔ | none |
| AI-328701 soft sensor | — | — | ✔ O'Connell E_o, Kremser, Arrhenius, Kohlrausch conductivity | — | ✔ **exemplary** | none |
| TIC-328008 inferential | — | — | — | — | ✔ Raoult at the true 3.5 bar VLE node + back-solved γ | none |

### Unit 329 — Steam, condensate, cooling water

| Tag | Bound | Q1 | Q4 |
|---|---|---|---|
| Steam header (`steam_system.py`) | ✔ lumped-capacitance drums, `_valve_flow`, `_level_loop`, split-range letdown | ✔ | none |
| 329D005 / 329D009 drums | ✔ | ✔ | none |
| FT-329403 / FT-329407 | ✔ PFD-anchored, live-normalised by in-scope duty | ✔ | none |
| 329P006 A/B CCW + 329E004 | ✔ ε-NTU bridge (see 322E003) | ✔ | none |
| PV-329202/203/205B/207B/208/212 | ✔ stroke→chest pressure→`tsat_steam` | ✔ | none |

### Control & instrumentation (C11) — plant-wide

`_ctrl_ipd` (main.py:1215) is a velocity-form **I-PD**: P on PV (no setpoint derivative kick),
I on error with optional deadzone `Dz`, D on PV with optional first-order filter `Tf`, negative-Td
sentinel decode, bumpless CAS setpoint transfer, and structural anti-windup (the velocity form
clamps `op`, so no integral state can wind). Instrument dynamics are available as `_lag1`,
`_delay` (transport), `_foptd`. Bad-PV handling freezes at last-good.

**Verdict: C11 is complete and correct across all loops. No finding.**

---

## 3. Category coverage summary

| Category | Verdict |
|---|---|
| C1 Total mass balance | ✔ closes everywhere; `closure_resid` diagnostics in 322R001/322E003 |
| C2 Component species balance | ✗ **unit 322 only** (F-8) |
| C3 Energy balance | ✗ **decoupled from mass in 323/324** (F-2..F-5); correct elsewhere |
| C4 Isenthalpic/isothermal flash | ✗ **no flash equation anywhere** (F-1); JT letdown only |
| C5 EoS & activity | ~ Antoine (NH₃, H₂O), Clausius–Clapeyron carbamate bubble-P, two back-solved activity coefficients. No EoS. **F-6** frozen splits |
| C6 Summation equations | ~ satisfied by construction (fractions computed as nᵢ/Σn); no independent Σy=1 residual because no flash exists |
| C7 Kinetics & reaction | ✔ reactor (Inoue–Kanai), stripper (hydrolysis + Arrhenius biuret); ✗ hydrolyser (F-7) |
| C8 Transport phenomena | ✔ ε-NTU throughout, Damköhler axial profile, Kremser, O'Connell |
| C9 Hydraulic & equipment | ✔ IEC 60534 equal-%, √ΔP, Francis weir, affinity laws, ejector momentum law |
| C10 Constitutive & properties | ~ densities and cp are **constants** (no T-dependence); `tsat_steam`, `psat_water_bara`, `psat_nh3_bara` are live |
| C11 Control & instrumentation | ✔ complete |

---

## 4. Remediation status

See section 5 for what landed. Fixes are applied **one unit at a time** (CLAUDE.md §2 Scope
Lock), each gated on `leaves 25 / keys 15 / diffs 0` plus the full pytest suite before commit.

## 5. Applied fixes

### Units 323 + 324 — energy/mass re-coupling (F-1, F-2, F-3, F-4, F-5, F-10)

All bit-exact at the design seed by construction: each duty ratio `q_avail / Q_DES` is written in
the **same float operand order** as its design constant, so it evaluates to exactly `1.0`, and
every `min()` / `max()` guard is non-binding at design.

| Tag | Was | Now |
|---|---|---|
| 323C003 / 323E002 | `m_305 = φ·m_feed` | `m_305 = min(φ·m_feed, M305_DES·q_avail/Q305_DES)` — boil-up energy-limited |
| 323F004 | `m_701 = φ·m_314` | true isenthalpic flash: `T_flash = 106 + [Tsat(P) − Tsat(1.13)]` (saturation constraint) and `m_701·λ = m_314·cp·ΔT − M·cp·(T_sat−T)/τ`. Substituting into the energy ODE yields exactly `dT/dt = (T_sat − T)/τ`, so energy stays conserved |
| 323F010 / 323E010 | `m_evap = φ·m_319` | `min(φ·m_319, MEVAP_DES·q_avail/QEVAP_DES)` |
| 324E001 | `p1_m = urea_in / 0.9431` (strength pinned) | `v1 = min(v_conc, V1_DES·q_avail/Q1_DES)`; `w1_live` published to `urea_pct` and `PY-324201` |
| 324E003 | `p2_gen = urea_in / 0.9771` (strength pinned) | same shape; `w2_live` published to `urea_pct` and `AY-324701`; Stage-2 feed enthalpy now uses the **live** Stage-1 outlet temperature, and the recycle carries its live strength through `s.tlag["R324_recyc_w"]` |
| all four steam chests | `Q = UA·(Tsat − T)` | `Q = max(UA·(Tsat − T), 0)` (F-10) |
| `conc_infer_324` | `w_des` assumed a constant in (0,1) | reference mole fraction clamped to the same physical band as the live one — `w_des` is now a live argument that legally reaches 0 on cold start |

**Verification** (`scratchpad/probe_323_324.py`):

* *Design fixed point, 480 s* — 94.3 % / 97.7 % / 106.0 °C / 24.56 / 4.43 / 8.74 t/h, **zero drift**.
* *Evap-I steam cut* — `Q → 0`, evaporation → 0, product falls **94.3 % → 80.0 %** (pass-through),
  melt coasts 130 → 100 °C asymptoting to its 99 °C feed. Previously the product strength could
  not move at all and the melt crashed to 22 °C.
* *323E002 steam cut* — `Q → 0`, overhead 305 collapses to 0, column decays 121 → 105 °C, and the
  downstream flash correctly produces **less** vapour (4.43 → 3.10 t/h) on its now-colder feed.

Gates: pin `leaves 25 / keys 15 / diffs 0` · suite `110 passed`.

### Still open

F-6 (HPCC φᵢ(T,P)), F-7 (hydrolyser kinetics), F-8 (downstream component balance) are **not**
landed — each is a unit-322 / cross-unit change that must take its own Scope-Lock slot. F-9 is a
tooling note: invoke the gate with an absolute output path.
