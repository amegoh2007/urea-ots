# Handoff — Urea OTS synthesis-loop calibration

_Last updated: 2026-07-03 (session 3) · branch `fix/reactor-level-drain-and-vent-coupling` · NOT pushed_

## Goal

Calibrate the `backend/main.py` state-space process engine against real DCS startup
trend data so its dynamic response matches the plant, **without ever violating mass or
energy conservation**. Two anchor datasets drive this:

1. **Pump volumetric efficiency** — from the 321P002 NH₃-pump rpm→flow field curve.
2. **Feed transport dead time** — from the 03-06-2025 synthesis-loop pressurization trend.

Hard constraints (standing user directives):
- **100% conservation** — mass/energy never created, destroyed, or decoupled to dodge stiffness.
- **Sourcing law** — thermodynamic equations from verified sources; no fabricated constants.
- **Design bit-exactness** — the pinned design steady state must stay bit-identical after any edit.
- Push to `https://github.com/amegoh2007/urea-ots.git` only on explicit request.

## Current state — 28-06 anchor analysis DONE, LV-322501 field-calibrated, verified, committed (unpushed)

Nothing is mid-edit. The feature branch has **local, unpushed** commits ahead of origin.

| Commit | Pushed | What |
|--------|--------|------|
| `c7c898a` | yes | Pump η_v calibrated 0.95 → 0.980 (matches field curve) |
| `487d4a1` | yes | Feed transport dead time `FEED_TD_S = 345 s` injected on feed tears + report |
| `8182420` | **no** | Prior session handoff doc |
| `e3ee4a6` | **no** | Fix MemoryError in `_delay` under variable sub-step dt |
| (latest) | **no** | **28-06-2025 anchor analysis + `LV322501_OPEN_DES` 82.0 → 46.1 (field)** (this session) |

### This session (2026-07-03, session 2) — 28-06-2025 DCS startup dataset

Full 10-target empirical extraction on `Urea_Startup_28-06-2025_Trends.xlsx`. Sheet is
self-labelled SYNTHETIC (30 s linear interp between hourly measured points); knot recovery
found **exactly 7 true hourly anchors** (10:01→16:01) — anchors-only analysis, same
honest-resolution rules as 03-06. Full findings:
`backend/reports/dcs_anchor_dynamics_2025-06-28.md`.

Headlines:
- **Pump map 3rd confirmation**: 0.34150 t/h/rpm through-origin vs committed **field** fit 0.34174
  (−0.07 %). No edit. NB engine mass map at design ρ is 0.33667 t/h/rpm (no 0.34174 in code);
  +1.4 % field gap = ρ-basis 613.5/604.8 (dcs_tuning_parameters §4.3a); 28-06 warm feed at same
  slope ⇒ FY-321401 likely fixed-ρ DCS compensation (see 28-06 report §T2 engine-side note).
- **PT-329201 FOPTD**: τ = 2246±500 s, outside band [2884,4055] — under-resolved (1st anchor
  at 76 % of span, t_d ±700 s trade-off) + τ is trajectory-dependent (faster load ramp).
  **Band unchanged**, stays tied to 03-06 scenario.
- **LIC-322501 direct action corroborated** on independent dataset (valve shut while level
  0.2→57 %, opens above SP) → 03-06 MV=102.8 % artifact verdict stands.
- **The ONE model edit**: `LV322501_OPEN_DES` 82.0 → **46.1 %** (main.py ~L335). Field: LV held
  45.4 % stable at 97 % load; dP+load-corrected → 46.1 (cross-checks 46.4/44.2). Datasheet 82 %
  stroke over-stated travel ~1.8× for installed flashing service. **Pin-safe ratio form**
  (seed + normalizer only) — A/B probe: boot pins bit-identical, hold pins ≤7e-7 %, no limit
  cycle at 1.78× loop gain.
- **Not edited** (would fabricate constants): HV-322602 (74 vs 60, operator-moved), HIC-322604
  (50 vs 80), HIC-322605 (60 vs 49, still ramping), TV-329005 (50 vs 32, TIC SP off-design 88 °C).
- **Not extractable at 3600 s spacing** (10-target requests): exact reactor dead times
  (brackets ≤3600 s only), all slew rates (lower bounds), SV-321950/951 + HV-322603 + TT-322002
  + PT-329206 + TT-322004 (tags absent), T3/T5/T9/T10 gains (confounded, sign-unstable secants).
- **Tag correction (user, 2026-07-03): LT-322504 = REACTOR level, not HPCC** (HPCC = LT-322E002,
  absent from workbook → T7 HPCC lag not extractable). LT-322504-3 fill = reactor: onset ≤3600 s,
  plateau 99.94 % at 92–97 % load vs model N7 NLL pin 80 % — documented, NOT edited (single
  transmitter, span/zero config ambiguity vs datasheet; report §3-T7).

## 2026-07-03 (later): sim-vs-28-06 verification + contradiction gap-closure (task 4)

**Verification (4-gate probe, scratchpad `verify_sim_vs_2806.py`): 4/4 PASS.**
- A design hold 600 s: all pins exact (LV 46.0994, strip 50.0, P 140.7, CO2 54.618, pump 127.0131).
- B 97 % load: LV settles 44.85 % (field 45.4, band [44.2,46.4]); drain-law self-consistency exact:
  op = 46.1×0.97512/1.00231 = 44.85.
- C pump map: engine internally exact (1e-16); ρ-basis 613.5/604.8 closes field gap to +0.005 %.
- D LIC-322501 direct action signs correct (−4.2/+8.3 % on ∓5 % level steps).

**Gap-closure research (report §8, 28-06 report). Register C1–C5, all resolved:**
- **C1 pump map CLOSED**: NIST compressed-liquid isotherm → `NH3_RHO=604.8` = ρ(25 °C, ~29 bar a)
  at pump suction — validated, not an error. Live-ρ falsified: 28-06 warm feed (T̄≈27.6 °C) predicts
  slope −2.1 % if FY-321401 tracked density; observed −0.07 % ⇒ **fixed-constant DCS compute tag**
  (ISA-5.1 letter Y). η_v fit degeneracy flagged: only η_v·ρ_cfg = 601.6 kg/m³ constrained;
  committed (0.980, 613.9) is one solution — conservation-neutral. Caveat comments added at
  `NH3_RHO` / `PUMP_ETA_V` in main.py (comment-only; Gate-A probe re-run post-edit: bit-exact).
- **C2 reactor level RESIDUAL**: 99.94 % plateau = liquid-full-to-top-tap OR radiometric density
  cross-sensitivity (Beer–Lambert, Berthold) — not separable from synthetic anchors; datasheet
  NLL 80 % pin stands. Discriminator: steady 100 %-load LT-322504 trend. **Update session 3:**
  29-06 normal-op export received — NO LT-322504 column → still open, re-export requested
  (same window + LT-322504-3 + LIC-322501). See Task-5 section §C2 below.
- **C3 lineup deltas CLOSED**: operator inputs, not equations.
- **C4 P_syn CLOSED**: PT-329201 in bar g ⇒ 14:01 peak 139.6 barg = 140.6 bara ≈ design 140.7;
  16:01 easing follows PIC SP (operator causality), sim floats on vent capacity. No edit.
- **C5 N/C→T CLOSED**: audit 1a upper range reproduces field-negative gain (TT-322010
  186.6→182.7 over AT701 3.08→4.01); radiometric N/C meter span 2.6–3.4 (UreaKnowHow 2024)
  brackets design 3.0, field AY rides top of span.

No numeric edit met the sourcing bar (validated / degenerate / design-doc-sourced / operator
input). Design steady state bit-exact by construction + probe.

### The bug fixed this session (`e3ee4a6`)

**Symptom (user report):** desktop shortcut "Start Urea Simulation" not starting the software.

**Root cause:** launcher chain is fine — 3 desktop `.lnk`s → `D:\Work\Urea Simulation\launch.bat`
→ `python main.py`. Python 3.14.3 resolves; uvicorn boots and serves HTTP 200. But the
**simulation task crashed on the very first tick** with `MemoryError`, so the browser opened
on a frozen sim → looked like "not starting."

Crash was in the `_delay` transport-delay helper added in `487d4a1`. Original code:
```python
n = max(1, int(round(td_s / dt)))
buf = deque([target] * n, maxlen=n)   # MemoryError
```
It sized the ring buffer from the **live sub-step `dt`**. But `sim_task` (main.py ~L2982)
subdivides each real tick into `STEP_CAP`(=0.5 s)-bounded sub-steps:
```python
sim_advance = dt * SIM_SPEED[mode]
while sim_advance > 1e-9:
    h = min(STEP_CAP, sim_advance)
    last_packet = step_sim(h)
    sim_advance -= h
```
The **remainder sub-step `h` is a tiny float crumb** (~1e-8 s) on nearly every tick →
`n = round(345 / 1e-8) ≈ 3.5e10` → `[target]*n` → out-of-memory. My injection wrongly
assumed a fixed `dt = 0.1` grid.

**Fix:** rewrote `_delay` (main.py ~L1485) as a **timestamp-tagged FIFO** — a continuous-time
transport delay, zero-order-held on a per-sub-step sim clock. Buffer length is no longer tied
to `dt`, so any sub-step size (incl. crumbs) is safe. New internal state shape is
`{"t": float, "buf": deque[(entry_time, value)]}` stored in `s.tlag[key]` (was a bare deque).
Still:
- **conservation-safe** — every input sample emitted exactly once (FIFO), only re-timed;
- **pin bit-exact** — until `td` s of history accrue the input passes through; constant input
  → constant output for all t.

`_foptd` (composes `_delay` + `_lag1`) unchanged and still unused.

### Wiring (unchanged from `487d4a1`)

- **CO₂**: `F_CO2_syn_th = _delay(s.tlag, "FEED_CO2", s.F_CO2_th, FEED_TD_S, dt)` (~L1792)
  → stripper 322E001 (~L1910), reactor 322R001 (~L2012). Live BL meter `s.F_CO2_th` still
  drives FY/FT-322403 display, load %, DCS ratio cascade, ratio-PV validity gate.
- **NH₃**: `motive_nh3_kgh = _delay(s.tlag, "FEED_NH3", motive_nh3_kgh, FEED_TD_S, dt)` (~L1877)
  → ejector, phi_m, downstream telemetry. Tank/pump balance debits the **live** flow.

The loop's ~3470 s pressurization τ stays **emergent** from the inventory ODEs (validation
target τ_sim ∈ [2884, 4055] s), never hard-coded.

### Verification evidence (fresh, this session)

- **Backend boot**: `python main.py` → port up 7 s, uvicorn running, **15 s sustained run,
  0 exceptions** (was: `MemoryError` on tick 1, `sim_task` dead while uvicorn served 200).
- `scratchpad/probe_verify_calibration.py` — **4/4 gates GREEN**: 11 boot pins bit-identical
  (max |Δ|=0.0), LT-322504=80.0000%, strip_level=50.0000%, rpm display shift correct,
  bumpless CAS |Δ|=0.0000%.
- `backend/tests/run_full_audit.py` — **exit 0, 0 FAIL** (5-campaign suite ran to END OF CAMPAIGN).

## 2026-07-03 (session 3): Task 5 — LT-322504 decoupled from load + stripper slip-direction fix

**User order:** "reactor level LT-322504 should not be coupled and pinned to plant load, change in
LT-322504 should be according to mass balance on 332R001" (typo for 322R001). **Overrides** the
earlier Lead-Ops Option-2 shadow-display mandate.

### main.py edits (uncommitted at time of writing → this session's commit)

**Display decoupling (6 edits):** deleted `self.react_m_liq_shadow`, `_load_gate()`, and the
SHADOW holdup block. LT-322504 now reads the PHYSICAL head through fixed N7 transmitter
geometry (~L2140):

```python
_H_liq_react         = REACT_LIQ_H_M * s.react_level_pct / 100.0          # physical head, m
s.react_lt322504_pct = clamp(REACT_LEVEL_NLL_PCT
                             + (_H_liq_react - REACT_LEVEL_DES_M) / REACT_LT_SPAN_M * 100.0,
                             0.0, 100.0)                                  # span 1.5 m, 20.0 m = 80 %
```

`react_level_pct` is the DOMINO physical inventory: dm/dt = ṁ_in − ṁ_out + ṁ_fwd with
ṁ_out = ṁ_des·(θ/θ_des)·(max(L,0)/L_des), L = m/(ρ(T_bulk)·A) → L_eq = L_des·(θ_des/θ).

**S2 stripper slip-direction fix (root cause of level-rise-on-vent-open):** in
`stripper_322e001` the feed-load choke `g_T` fed the `slip` term, routing unstripped volatiles
OVERHEAD (loop return) instead of BOTTOMS (loop exit via LV-322501) — wrong physics sign for a
flooded steam-limited stripper (classic NH₃ slip goes to the LP section). Combined with the
g_HC 1.05 clamp it made the dynamic return gain ≥ 1, so opening HV-322605 60→75 % RAISED the
physical level. Fix (one functional line + comments, ~L640):

```python
mod  = clamp(eta_T_steam * eta_co2 * eta_P, 0.0, 1.12) * min(g_T, 1.0)
slip = max(1.0 - g_NC, 0.0) + max(1.0 - g_HC, 0.0)   # composition (N/C, H/C) breakthrough only
```

Design g_T = 1 and feed-lean g_T > 1 ⇒ min(g_T, 1) = 1 ⇒ design point AND turndown
byte-identical; only the flood branch (g_T < 1) changes, cutting the split so volatiles leave
with the bottoms. Per-component conservation exact (split loop untouched).

### Verification (all green, this session)

- 5-gate probe `scratchpad/verify_task5_lt322504.py` **OVERALL PASS**:
  Gate A design hold — all pins bit-exact, LT = 80.0;
  S1 feed cut to 90 % — LT 31.198, level 77.072 (d_vs_ctrl −48.80);
  S2 HV-322605 +15 % — LT 0.0, level 69.647 falling (d −80.0; pre-fix FAIL at +17.48);
  S3 HV-322602 close 74→60 — LT peak 87.884 (d_peak +7.884).
- S2 settle trace (`scratchpad/s2_settle_trace.py`): level → **16.008 m at t = 10800 s**,
  exactly L_eq = 20·(60/75) = 16.0 m; LV op returns 46.14 %, P_syn 140.692 — loop inventory
  shed via bottoms/letdown, conservation intact.
- `tests/audit_e001_stripper.py` ALL PASS: mass closure worst 0.00 ppm across 60 cases;
  B2 slip monotone 0→0.4609→0.5; B3 extremes finite; LIC sump returns to SP 50.000 %.
- Regression: valve-indicator matrix `HV-322605 → LT_322504 d=−100 [OK]` (open→fall restored);
  flood scenario close→LT 100.000; pillar4 flood LT pegged 100, closure resid ~3e-9;
  test_reactor 14/14; ejector stall + spindle suites PASS; `run_full_audit.py` exit 0;
  28-06 4-gate probe (`verify_sim_vs_2806.py`) OVERALL PASS.
- Turndown A/B vs HEAD (git stash): rows 70–95 % byte-identical to HEAD; 100 % row IMPROVED
  (f_cons 1.10602→1.03705, dPsyn 0.0110→0.0, CHECK→OK) — old g_T slip term was an asymmetric
  ripple amplifier at design.

### §C2 status (Task 6, still open)

User attached `Urea_NormalOp_29-06-2025_Trends.xlsx` (29-06 normal op, 08:59→00:59 30-06,
1921 rows @30 s, sheet self-labelled SYNTHETIC) as the C2 discriminator — **the export has no
LT-322504 / LIC-322501 / level tag** → C2 stays open. Re-export of the same window including
LT-322504-3 (and LIC-322501) requested from user. 29-06 steady anchors logged in the 28-06
report (§9): LV-322501 ≈ 44.6 %, HIC-322605 ≈ 55.2, PT-329201 ≈ 130.5 barg, AY-322701
3.19–3.34, FY-322403 ≈ 28.4 t/h, PIC-322203 144.4–145.7 barg, HV-322602 65–66,
TT-322013 187.1–187.6.

## Files

**Committed / active source:**
- `backend/main.py` — the engine. `LV322501_OPEN_DES` 82.0→46.1 (session 2, ~L335); session 3:
  LT-322504 display decoupling (shadow machinery deleted, ~L2140) + stripper slip-direction fix
  (`mod × min(g_T,1)`, ~L640).
- `backend/handoff.md` — this file.
- `backend/reports/dcs_anchor_dynamics_2025-06-03.md` — 03-06 anchor report (+LIC closure note).
- `backend/reports/dcs_anchor_dynamics_2025-06-28.md` — **28-06 anchor report (this session)**.
- `launch.bat` (repo root) — the launcher the desktop shortcuts target. Fine, unchanged.

**Analysis / verification (session scratchpad, not committed, temp-dir — recreate if needed):**
- `probe_pins_2806.py` — boot-pin + 600 s hold A/B probe (pre/post edit bit-exactness).
- `explore_2806.py`, `knots_2806.py`, `anchors_2806.py`, `analysis_2806.py`,
  `anchors_2806.json`, `analysis_2806_results.json` — 28-06 anchor extraction + 10-target analysis.
- `verify_sim_vs_2806.py` — 4-gate sim-vs-28-06 harness (session 3 re-run: OVERALL PASS).
- `verify_task5_lt322504.py`, `s2_settle_trace.py` — Task-5 5-gate probe + S2 long settle.

**Untracked in repo root/backend (NOT mine, left alone — do not commit blindly):**
`Gemini/`, `Urea Simulation/`, `TECH_DEBT.md`, `fundamentals.md`, several `Combined_*_PFD*.md`,
`backend/_audit_closure.py`, `backend/_creep_probe.py`, `backend/_probe_c1*.py`, `backend/_probe_h1.py`,
`backend/_recon_scrub.py`, `backend/tests/pillar4_audit.py`, `backend/tests/repro_bugs_1_4_co2.py`.

## Key verified numbers (preserve)

- PT-329201 FOPTD (03-06): P₀=5.7, P_f=144.0 bar g, τ=3469.5±585.9 s, t_d=344.7±280.3 s, R²=0.9888.
  28-06 fit τ=2246±500 s is under-resolved + trajectory-dependent → band stays [2884,4055] s.
- Pump map (field, FY-321401): 0.34174 t/h/rpm through-origin, η_v=0.980 (28-06: 0.34150, −0.07 %,
  3rd confirmation). Engine mass map at design ρ 604.8: 0.33667 t/h/rpm; ×613.5/604.8 = 0.34152.
- `LV322501_OPEN_DES` = 46.1 % (field, 28-06 anchors; was datasheet 82.0).
- Pinned state: LT-322504=80.0000%, strip_level=50.0000%, F_CO2_th=54.618 t/h, F_in_BL_th=42.762 t/h,
  pumpB speed_act=127.0131 rpm, open_act=83.5612 %. Sim tick DT=0.1 s, STEP_CAP=0.5 s, FAST=×60.
- Gate-A 600 s hold pins (re-verified post Task-5, bit-exact): LV_op 46.099420016307754,
  strip_level 49.99999990296993, p_syn 140.7, F_CO2_th 54.618, pumpB_rpm 127.01306122448977,
  react_level_pct 80.0, react_lt322504_pct 80.0.
- LT-322504 display law (session 3): LT = clamp(80 + (H_liq − 20.0)/1.5 × 100, 0, 100),
  H_liq = 25·react_level_pct/100. Equilibrium head L_eq = 20·(60/HIC605) m — verified 16.008 m
  at HIC605 = 75.

## Failed / rejected approaches (don't repeat)

- **`_delay` buffer length `n = td/dt` from the LIVE sub-step — REJECTED (this session's bug).**
  The live sub-step is variable and its remainder is a ~1e-8 s crumb → `n` explodes →
  MemoryError. Delay must be timestamp/clock based, independent of sub-step size.
- **UREA-LOAD fit for τ calibration — REJECTED.** Non-monotonic, operator-driven
  (τ=1067±415 s, R²=0.9306). Used only to bracket the feed-introduction window.
- **Hard-coding τ=3470 s as a lag on synthesis pressure — REJECTED.** Double-counts inventory
  ODE dynamics, violates conservation. τ is a validation target only.
- **Interpolated grid rows from the xlsx — REJECTED.** Zero dynamic information; anchors only.
- **Flow derating from hydraulic resistance — REJECTED.** I/ṁ rises with P_syn but flow stays
  on the PD line → motor-load only, no flow penalty.
- **Editing hand-valve `*_DES` to operator positions (HV-322602/HIC-322604/605/TV-329005) —
  REJECTED.** Operator practice ≠ design basis; would fabricate constants.
- **Adopting 28-06 τ=2246 s or T3/T5/T9/T10 secants as model gains — REJECTED.** Under-resolved
  / confounded / sign-unstable (report §3–4).
- **Shadow-holdup / `_load_gate` LT-322504 display (Option-2 mandate) — DELETED (session 3, user
  order).** Display pinned to plant load hid real inventory motion; LT must track physical head.
- **g_T (feed-load) term inside stripper `slip` — REJECTED (session 3, the S2 bug).** Routes
  unstripped volatiles overhead → positive loop-return gain → level RISES on vent open. Feed-load
  choke must CUT the split (`mod × min(g_T,1)`) so volatiles exit with bottoms via LV-322501.

## Next steps (if work resumes)

1. **Push** the unpushed commits to origin — only on explicit user request.
2. **Optional transient acceptance check (report §6.4):** cold-start sim, confirm emergent
   τ_sim ∈ [2884, 4055] s, t_d,sim ≤ 572 s, P_f ∈ [137.5, 150.5] bar g. Proves the delay
   reproduces observed dynamics (suites above only prove conservation/bit-exactness/no-crash).
   No cold-start driver harness exists yet.
3. ~~**Investigate LIC-322501 startup anomaly**~~ — **RESOLVED 2026-07-03: DCS positioner/output-span
   artifact, no AUTO-logic change.** Direct-acting LIC (main.py:1934) with level below SP during
   startup commands the 0% clamp, not 102.8% → saturated-high MV is not the level PI (positioner on
   hand-jack/override/split-range). Real LV 0→30% motion already reproducible via existing MAN mode
   (main.py:2832). Bit-exact pin + conservation untouched. Closure written to report §2.
4. **Merge** `fix/reactor-level-drain-and-vent-coupling` once §6.4 transient check passes.

## Environment

- Python 3.14.3, pandas 3.0.3, scipy 1.17.1, numpy 2.4.2. Windows 10.
- PowerShell primary (no `&&` — use `;`); Bash tool for POSIX.
- Run audits/backend from `D:\Work\Urea Simulation\backend`.
- Launcher: `launch.bat` starts `python main.py`, polls `http://127.0.0.1:8000/`, opens Chrome.
- Desktop shortcuts (OneDrive desktop): "Start Urea Simulation.lnk", "Helwan Urea Simulator.lnk",
  "urea simulation.lnk" — all target the same `launch.bat`.
