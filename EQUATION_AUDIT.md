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
| HPCC component split φᵢ | `HPCC_FRAC_GAS_DES` → `_hpcc_flash_split` (main.py:1553 / 1971) | design HMB; now the **anchor** of a live (T,P) flash |
| Stripper split fᵢ + η modifiers | `STRIP_FRAC_DES`, `g_T/g_NC/g_HC` (main.py:1453) | design HMB |
| Reactor θᵢ vapour/liquid split | `REACT_THETA_OG` (main.py:1571) | design HMB |
| Scrubber pinned discharges | `SCRUB_*_KMOLH_DES` (main.py:2140) | design HMB |
| Modified Inoue–Kanai conversion | `reactor.inoue_kanai_X` | re-fitted to plant HMB |
| Back-solved latents λ / UA | 323/324/328 blocks | design fixed point |
| Ejector negative equal-% spindle law | `EJ_SPINDLE_R` (main.py:1152) | 322F001 datasheet |
| Soft sensors (`conc_infer_324`, `ppm_infer_328701`) | main.py:66 / 136 | PFD guarantees |

**Where hybrid variability was missing** is the substance of findings **F-1..F-6** below: the
empirical split fractions were *frozen at their design values* and carried **no state dependence**.
A split fraction is only a valid hybrid layer if it is a *function* — φᵢ(T, P, composition). As
originally coded, φᵢ was a constant, so the units they describe could not respond to the very
disturbances an OTS exists to train on. Both remediation slots in §5 close exactly this class: the
323/324 vaporisers now bind φ to the live duty, and 322E002 binds φᵢ to a live (T,P) flash. The
constants are not discarded — each becomes the *anchor* of the function, evaluating to itself at the
design seed, which is what keeps the HMB bit-exact.

---

## 1. Findings register

Severity: **A** = wrong physics an operator can trigger from the HMI · **B** = missing equation
that limits training fidelity · **C** = cosmetic / documentation.

| ID | Sev | Unit | Category | Finding |
|----|-----|------|----------|---------|
| **F-1** | A | 323F004 | C4 Isenthalpic flash | Adiabatic-flash vapour is a **frozen split fraction** `m_701 = φ·m_314`, not an enthalpy balance. Feed temperature from Stage 1 can move ±30 °C and the flash produces identical vapour. **CLOSED** — see §5. |
| **F-2** | A | 323C003 / 323E002 | C1↔C3 | Boil-up `m_305 = φ·m_feed` is **independent of the live heater duty** `Q_e002_kw`. Shutting PV-329202 gives zero duty yet full design overhead vapour; the energy deficit is dumped into the temperature ODE. **CLOSED** — see §5. |
| **F-3** | A | 323F010 / 323E010 | C1↔C3 | Identical defect: `m_evap = φ·m_319` ignores `Q_e010_kw`. **CLOSED** — see §5. |
| **F-4** | A | 324E001 / 324F001 | C1↔C3, C10 | `p1_m = urea1_in / R324_W_EV1` pins the Stage-1 melt at **94.31 % hard**. Water removed is fixed by a constant, not by `Q_e001_kw`. Cutting Evap-I steam cannot dilute the product. **CLOSED** — see §5. |
| **F-5** | A | 324E003 / 324F003 | C1↔C3, C10 | Identical defect at Stage 2 (`R324_W_EV2` = 97.71 % hard). **CLOSED** — see §5. |
| **F-6** | B | 322E002 | C5 EoS/activity | HPCC condensation split `φᵢ = HPCC_FRAC_GAS_DES` is **invariant to shell temperature and loop pressure**. Raising LP-steam pressure changes duty and `T_prod` (via NTU) but not one mole of condensate. **CLOSED** — see §5. |
| **F-7** | B | 328C003 | C7 Kinetics | The hydrolyser carries **no reaction extent at all** — urea hydrolysis is lumped into the back-solved `R328_C003_LAM748`. Arrhenius hydrolysis kinetics exist only in the read-only `ppm_infer_328701` soft sensor, not in the mass balance. |
| **F-8** | B | 323/324/328/329 | C2 Component balance | Species tracking (`MW_COMP`, 9 components) exists **only in unit 322**. Everything downstream of LV-322501 is lumped-mass. No component balance, hence no C6 summation equations, downstream. **CLOSED for 323 + 324** — see §5; the 328 train remains (F-7 depends on it). |
| **F-11** | B | 323F010 | C2 / source data | **The PFD's stream-317 composition is not reachable from stream 319 by evaporation.** Removing 319's water, NH₃ and CO₂ at the tabulated percentages takes out 10 163 kg/h against a tabulated 8 750 kg/h total, so ≈1.4 t/h of urea would have to *appear* across 323F010, and no stream feeds it there (331, the urea-recovery return, enters 323D002 downstream and is only 1 451 kg/h of urea). Found by closing F-8 — the rigorous component balance exposed it. Needs a licensor data clarification, not a code change. |
| **F-9** | C | tooling | — | `scratchpad/regress.py` `os.chdir(BACKEND)` before writing `argv[1]`, so the relative gate command in CLAUDE.md §7 / handoff.md fails with `FileNotFoundError`. Gate must be invoked with an **absolute** output path. **CLOSED** — `regress.py` now resolves `argv[1]` before the chdir (TD-010). |
| **F-10** | A | 323E002, 323E010, 324E001, 324E003 | C3, C8 | **Condensing-steam heater duty is unbounded below.** `Q = UA·(Tsat(p_chest) − T)` with `p_chest` clamped to 0.02 bar a (Tsat ≈ 17.5 °C) makes a shut steam valve a *refrigerator*: probe measured the Evap-I melt driven to **22 °C** and the 323C003 column to **13.6 °C**. A condensing chest cannot remove heat — it simply stops condensing. Found by disturbance-probing the F-2..F-5 fixes; the defect pre-dates them but was masked while the boil-up ignored the duty. **CLOSED** — see §5. |

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
| **322E002** HPCC | ✔ | ✔ | ✔ carbamate exotherm + sensible, ε-NTU quench | ✔ anchored (T,P) Rachford-Rice, film-relaxed (**F-6 closed**) | ✔ carbamate K_p = p²_NH₃·p_CO₂, Raoult (H₂O), Henry (N₂) | ✔ ε-NTU + interfacial relaxation | ✔ | ✔ | — |
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
| C2 Component species balance | ~ rigorous in **322, 323 and 324** (9 species in the HP loop, 6 in the solution train); the 328 desorption/hydrolysis train is still lumped mass (F-8 remainder) |
| C3 Energy balance | ✔ **re-coupled to mass in 323/324** (F-2..F-5, F-10 closed); correct elsewhere |
| C4 Isenthalpic/isothermal flash | ✔ isenthalpic flash at 323F004 (F-1) and isothermal (T,P) Rachford-Rice at 322E002 (F-6). JT letdown elsewhere — appropriate |
| C5 EoS & activity | ~ Antoine (NH₃, H₂O), Clausius–Clapeyron carbamate bubble-P, carbamate K_p = p²_NH₃·p_CO₂ / Raoult / Henry K-values at 322E002, back-solved activity coefficients baked into the anchored K_des. No cubic EoS — reduced-order by design |
| C6 Summation equations | ✔ enforced explicitly where a phase split exists: the 322E002 Rachford-Rice root (Σy=1, Σx=1) and the 323/324 relative-volatility normalisation (Σw=1, Σy=1, asserted every tick in telemetry). Unit 328 outstanding |
| C7 Kinetics & reaction | ✔ reactor (Inoue–Kanai), stripper (hydrolysis + Arrhenius biuret), **323/324 biuret formation** (2 Urea → Biuret + NH₃, Arrhenius, 5 stages); ✗ hydrolyser (F-7) |
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

### Unit 322 — 322E002 HPCC live (T,P) phase split (F-6)

The calibrated vector `HPCC_FRAC_GAS_DES` was measured at one point (170 °C, 144.2 bar a) and then
frozen, so the condenser was thermodynamically **inert**. The fix does not discard the calibration —
it anchors a real flash on it.

**1. Back-solve the design K-values from the calibration, every tick, against the live feed.**
Over the distributing set `D = {k : 0 < φ_des,k < 1} = {CO₂, NH₃, H₂O, N₂}`:

$$\psi_{des}=\sum_{k\in D} z_k\,\varphi_{des,k},\qquad
K_{des,k}=\frac{\varphi_{des,k}\,(1-\psi_{des})}{\psi_{des}\,(1-\varphi_{des,k})}$$

This keeps the melt's measured activity coefficients baked into the K-values; only the *deviation*
from the calibration point is model-driven.

**2. Correct K to the live (T, P).** The NH₃/CO₂ "condensation" is not physical condensation — it is
the carbamate equilibrium NH₂COONH₄(l) ⇌ 2 NH₃(g) + CO₂(g), $K_p = p_{NH_3}^2\,p_{CO_2}$, with
ΔH_dis ≈ 160 kJ/mol — which is already in the code as `HPCC_DH_CARB_KJMOL`. Because K_p is a
**third-order** product, the measured temperature coefficient of the dissociation *pressure* is one
third of the reaction enthalpy (≈ 12.8 kcal/mol = 53.3 kJ/mol — Bennett 1953, Ramachandran 1998).
With y_NH₃ ≈ 2 y_CO₂ this gives y_i ∝ K_p(T)^{1/3}/P, so

$$K_k(T,P)=K_{des,k}\;\exp\!\left[\frac{\Delta H_k}{R}\!\left(\frac{1}{T_{des}}-\frac{1}{T}\right)\right]\frac{P_{des}}{P}$$

with ΔH = ΔH_carb/3 for CO₂ and NH₃, ΔH = 36 900 J/mol (water latent at 170 °C) for H₂O by Raoult,
and ΔH = 0 for N₂ (permanent gas, Henry). Species with φ_des exactly 1 (O₂/CH₄/H₂ — never condense)
or exactly 0 (Urea/Biuret — never boil) sit **outside** the flash.

**3. Solve Rachford-Rice by bisection, not Newton.** g(ψ) is strictly decreasing on [0,1], so a
fixed 60-sweep bracket is exact to 2⁻⁶⁰ at bounded cost and **cannot** fail to converge. This is the
same argument that keeps the flowsheet Sequential-Modular (§0 Q2): an OTS tick must never miss its
deadline.

**4. Rate-limit it — the equilibrium flash alone is wrong for this vessel.** The K-values of the
distributing set are tightly clustered, so a common factor moves the whole mixture together: the raw
equilibrium target swings φ_CO₂ from 0.0009 to 1.0 across 150 → 190 °C (probe Phase 0). That is not
how a falling-film condenser behaves. `References/HPCC description.md` §5.2–5.3 is explicit that
322E002 is **interfacial mass-transfer limited** — gas must diffuse to the film, cross the interface
and react. So φ is relaxed toward the equilibrium target over the condenser's own holdup constant
`HPCC_TAU_FILL_MIN` (6 min), making the split a genuine **dynamic state** `s.hpcc_phi`. This is the
audit's *missing equation* for this tag: the condenser had no composition dynamics at all.

**5. Anchoring.** Three independent guarantees, in order: the flash short-circuits to the
calibration when `p_rat == 1.0 and T_K == T_des_K` (so no Rachford-Rice tolerance ever reaches the
module-load or boot-pin passes); `dt = 0` on those passes makes the relaxation coefficient exactly
0; and the result is blended through the Option-1 `_disturbance_gate` exactly as `T_prod` is, so
`gate == 0` ⇒ φ ≡ `HPCC_FRAC_GAS_DES` bit-exact.

Also fixed in the same tag: `p_bub` was evaluated at the frozen `HPCC_T_PROD_DES_C` — a bubble
pressure taken at a fixed temperature is not a bubble pressure. It now uses the live (gated)
`T_prod`. `P_bub` is telemetry only (PI-322E002); it does **not** enter `pt_target`, so no new loop.

| Tag | Was | Now |
|---|---|---|
| 322E002 | `φᵢ = HPCC_FRAC_GAS_DES` (frozen constant) | anchored (T,P) Rachford-Rice flash, film-relaxed over `HPCC_TAU_FILL_MIN`, gate-blended |
| 322E002 | `p_bub = bubble_p(170.0, L, W)` | `p_bub = bubble_p(T_prod, L, W)` |
| 322E002 | no composition state | `s.hpcc_phi` — interfacial split, seeded at the calibration |

**Loop-gain check** (the `_disturbance_gate` self-excitation path, `main.py:1878`). The new coupling
is **negative feedback** in both legs: T↑ → K↑ → φ↑ → less CO₂ absorbed → q_carb↓ → T_adb↓ → T↓; and
P↑ → K↓ → more condensation → duty↑ → LP header↑ → shell↑ → T↑ → K↑ (opposing). Measured, not
assumed — see below.

**Verification** (`scratchpad/probe_322e002_flash.py`):

* *Design hold, 600 s* — gate 0.000000, T_prod drift **0.000e+00 °C**, and φ equals
  `HPCC_FRAC_GAS_DES` **exactly, every component** (identity comparison, not a tolerance).
* *MP supply valve 50 → 62 %* (PIC-329204 to MAN) — shell runs hotter, TT-322010 170.00 → 170.49 °C,
  and the split follows: φ_CO₂ **0.2036 → 0.2342**, φ_NH₃ 0.2977 → 0.3357, gas product
  **60.33 → 69.34 t/h**. Every one of these was *identically zero* before the fix.
* *N/C setpoint cut to 92 %* — φ_CO₂ → 0.2105, level swells 49.7 → 55.3 %, duty 63 122 → 66 706 kW.
* *Self-excitation* — T_prod spans **0.0205 °C** (steam disturbance) and **0.2329 °C** (N/C
  disturbance) over the final five minutes: monotone convergence, no ringing, no runaway.

Gates: pin `leaves 25 / keys 15 / diffs 0` · suite `123 passed`.

### Units 323 + 324 — downstream component species balance (F-8, and F-11 found while closing it)

Species tracking stopped dead at LV-322501. Everything downstream was lumped mass moved by design
split fractions: no C2 component balance, therefore no C6 summation equation, and the only
composition-aware objects were read-only soft sensors that could not feed back.

The layer **rides on top of** the existing total-mass and energy ODEs — it does not touch one of
them, which is why C1 is untouched by construction and the design anchors cannot move:

$$\frac{d(M w_i)}{dt}=\dot m_{in}w_{in,i}-\dot m_{liq}w_i-\dot m_{vap}y_i+\nu_i\xi,\qquad \sum w_i=\sum y_i=1$$

Six species (Urea, Biuret, NH₃, CO₂, H₂O, HCHO) across 323C003 → 323F004 → 323F010 → 323D002 →
324E001 → 324E003. Two pieces of real physics fell out of the design data and had to be modelled:

**Biuret formation, 2 Urea → Biuret + NH₃.** Back-solving the PFD biuret rise (0.24 % at stream 208
to 0.85 % at stream 402) gives design extents of 0.660 / 0.000 / 0.136 / 1.487 / 0.996 kmol/h across
C003/F004/F010/E001/E003 — 3.28 kmol/h ≈ 338 kg/h total, against the 322 kg/h the PFD stream flows
imply. The extents rise with temperature exactly as expected, the two hot evaporators dominating,
which is *why* UF-85 is dosed at all. Arrhenius, second order in the urea fraction, sharing the
stripper's own activation energy — one biuret reaction, one Eₐ.

**Vapour composition by relative volatility.** y is not a free vector; it is set by the live liquid
through αᵢ (volatility relative to water), back-solved at the design point *after* the reaction
extent is removed, so the component balance closes exactly:

$$y_i=\frac{\alpha_i w_i}{\sum_j \alpha_j w_j}$$

— and that normalisation **is** the C6 summation equation. Biuret and HCHO are forced non-volatile;
water is the reference (α = 1) and carries the closure residual, which is what a balance closer
should do.

**Finding F-11, and the reconciliation it forced.** Closing the balance immediately exposed that the
PFD's stream-317 composition is not reachable from stream 319: the tabulated percentages remove
10 163 kg/h against a tabulated 8 750 kg/h total, so ≈1.4 t/h of urea must appear across 323F010 and
nothing feeds it there. Left free, that deficit propagates and walks the 324 melt ≈1.8 pp below its
PFD anchor — two disagreeing urea numbers on one HMI screen, which would be worse than the constant
being replaced. So `sol_pin_strength` takes the **urea/water pair** from the mass-and-energy-
validated evaporation path (`w1_live` / `w2_live` / `R324_W_IN` — the anchors F-4/F-5 already made
live, and CLAUDE.md §0 says PFD values override derived ones) while Biuret, NH₃, CO₂ and HCHO stay
exactly where the component balance put them. **323F010 is deliberately left un-pinned**, so the
discrepancy stays visible at the stage that causes it instead of being smeared across the train.

**Verification** (`scratchpad/probe_species_323_324.py`):

| stage | species Urea % | PFD | Biuret % | PFD |
|---|---|---|---|---|
| 323C003 | 68.705 | 68.74 | 0.364 | 0.36 |
| 323F004 | 71.702 | 71.74 | 0.380 | 0.37 |
| 323F010 | **78.444** | 80.00 | 0.430 | 0.42 |
| 323D002 | 80.000 | 80.00 | 0.425 | 0.42 |
| 324E001 | 94.309 | 94.31 | 0.696 | 0.69 |
| 324E003 | 97.709 | 97.71 | 0.856 | 0.85 |

Σw reads exactly `100.0000` at every stage on every tick; Σy likewise. The species and scalar urea
figures agree to the published resolution. The single off-anchor cell is 323F010 — F-11, by design.

Gates: pin `leaves 25 / keys 15 / diffs 0` · suite `133 passed`.

### Still open

F-7 (hydrolyser kinetics) and the **328 remainder of F-8** are not landed: the desorption/hydrolysis
train is still lumped mass, and a reaction extent needs species to act on, so F-7 stays blocked on
extending the same layer through 328. F-9 is closed in `regress.py` itself. F-11 needs a licensor
data clarification rather than a code change.
