# Handoff — Urea OTS synthesis-loop calibration

_Last updated: 2026-07-03 (session 2) · branch `fix/reactor-level-drain-and-vent-coupling` · NOT pushed_

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
- **Pump map 3rd confirmation**: 0.34150 t/h/rpm through-origin vs committed 0.34174 (−0.07 %). No edit.
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

## Files

**Committed / active source:**
- `backend/main.py` — the engine. `LV322501_OPEN_DES` 82.0→46.1 this session (~L335).
- `backend/handoff.md` — this file.
- `backend/reports/dcs_anchor_dynamics_2025-06-03.md` — 03-06 anchor report (+LIC closure note).
- `backend/reports/dcs_anchor_dynamics_2025-06-28.md` — **28-06 anchor report (this session)**.
- `launch.bat` (repo root) — the launcher the desktop shortcuts target. Fine, unchanged.

**Analysis / verification (session scratchpad, not committed, temp-dir — recreate if needed):**
- `probe_pins_2806.py` — boot-pin + 600 s hold A/B probe (pre/post edit bit-exactness).
- `explore_2806.py`, `knots_2806.py`, `anchors_2806.py`, `analysis_2806.py`,
  `anchors_2806.json`, `analysis_2806_results.json` — 28-06 anchor extraction + 10-target analysis.

**Untracked in repo root/backend (NOT mine, left alone — do not commit blindly):**
`Gemini/`, `Urea Simulation/`, `TECH_DEBT.md`, `fundamentals.md`, several `Combined_*_PFD*.md`,
`backend/_audit_closure.py`, `backend/_creep_probe.py`, `backend/_probe_c1*.py`, `backend/_probe_h1.py`,
`backend/_recon_scrub.py`, `backend/tests/pillar4_audit.py`, `backend/tests/repro_bugs_1_4_co2.py`.

## Key verified numbers (preserve)

- PT-329201 FOPTD (03-06): P₀=5.7, P_f=144.0 bar g, τ=3469.5±585.9 s, t_d=344.7±280.3 s, R²=0.9888.
  28-06 fit τ=2246±500 s is under-resolved + trajectory-dependent → band stays [2884,4055] s.
- Pump map: 0.34174 t/h/rpm through-origin, η_v=0.980 (28-06: 0.34150, −0.07 %, 3rd confirmation).
- `LV322501_OPEN_DES` = 46.1 % (field, 28-06 anchors; was datasheet 82.0).
- Pinned state: LT-322504=80.0000%, strip_level=50.0000%, F_CO2_th=54.618 t/h, F_in_BL_th=42.762 t/h,
  pumpB speed_act=127.0131 rpm, open_act=83.5612 %. Sim tick DT=0.1 s, STEP_CAP=0.5 s, FAST=×60.

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
