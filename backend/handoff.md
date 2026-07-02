# Handoff — Urea OTS synthesis-loop calibration

_Last updated: 2026-07-02 · branch `fix/reactor-level-drain-and-vent-coupling` · HEAD `487d4a1` (pushed to origin)_

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
- Push to `https://github.com/amegoh2007/urea-ots.git` only on explicit request (done this session).

## Current state — COMPLETE and verified

Both calibrations are committed and pushed. Nothing is mid-edit.

| Commit | What |
|--------|------|
| `c7c898a` | Pump η_v calibrated 0.95 → 0.980 (matches field curve, prior session) |
| `487d4a1` | Feed transport dead time `FEED_TD_S = 345 s` injected on feed tears + full report |

### What `487d4a1` did (this session)

Injected empirical transport dead time on the **two feed tear streams only**. Derivation:
PT-329201 FOPTD fit, R²=0.9888, dead time bracketed ≤572 s by the UREA-LOAD
feed-introduction window; best estimate 345 s.

New code in `backend/main.py` (after `_lag1`, ~L1476):
- `FEED_TD_S = 345.0`
- `_delay(store, key, target, td_s, dt)` — pure ring-buffer transport delay via
  `collections.deque(maxlen=n)`, O(1)/tick. Lazy-inits filled with `target` so any
  constant input passes through unchanged → **design pin bit-exact**. Values are
  re-timed, never scaled: material absent downstream during a transient equals the
  line pack held in transit → **conservation-safe**.
- `_foptd(...)` — `e^(−td·s)/(τ·s+1)` helper composing `_delay` + `_lag1`
  (currently unused; available for future published-signal validation).

Wiring:
- **CO₂** (`F_CO2_syn_th = _delay(s.tlag, "FEED_CO2", s.F_CO2_th, FEED_TD_S, dt)`, ~L1792)
  → feeds stripper 322E001 (~L1910) and reactor 322R001 (~L2012).
  Live BL meter `s.F_CO2_th` still drives FY/FT-322403 display, load %, DCS ratio
  cascade, and the ratio-PV validity gate (transmitters physically sit at the battery
  limit, not inside the loop).
- **NH₃** (`motive_nh3_kgh = _delay(s.tlag, "FEED_NH3", motive_nh3_kgh, FEED_TD_S, dt)`,
  ~L1875) → ejector, phi_m, and all downstream discharge composition/telemetry.
  Tank/pump balance debits the **live** flow; the difference is BL→ejector line pack.

Key design decision: the loop's **~3470 s pressurization time constant is NOT
hard-coded**. It stays an emergent property of the inventory ODEs and serves as the
validation target (τ_sim ∈ [2884, 4055] s per report §6.4). Hard-coding a lag on
pressure would double-count inventory dynamics and break conservation.

### Verification evidence (fresh, this session)

- `scratchpad/probe_verify_calibration.py` — **4/4 gates PASS**: 11 boot pins
  bit-identical (max |Δ|=0.0), design fixed points held (LT-322504=80.0000%,
  strip_level=50.0000%), rpm display shift correct, bumpless CAS |Δ|=0.0000%.
- `backend/tests/run_full_audit.py` — **exit 0, 20 PASS / 0 FAIL** (5 campaign tests).
- `backend/tests/audit_p002_pumps.py` — **exit 0, ALL PASS** (categories A–E).

## Files

**Committed / active source:**
- `backend/main.py` — the engine. Edited this session (dead-time injection). Clean, committed.
- `backend/reports/dcs_anchor_dynamics_2025-06-03.md` — full anchor-analysis report
  with LaTeX transfer functions, honest-resolution gating, and the §6 injection design.

**Analysis / verification (scratchpad, not committed):**
- `scratchpad/xlsx_anchor_analysis.py` — anchor-only DCS analysis (exact ruler anchors
  only; interpolated grid rows excluded — they carry no dynamics).
- `scratchpad/xlsx_anchor_results.json` — its output.
- `scratchpad/probe_verify_calibration.py` — the 4-gate red/green conservation probe.

**Input data (read-only, analysis complete):**
- `D:\Work\Urea Simulation\New folder\Trends\321 322 Trends 3.6.2025\Trends To Excel\DCS_Trend_Extraction_03-06-2025.xlsx`

## Key verified numbers (preserve)

- PT-329201 FOPTD: P₀=5.7, P_f=144.0 bar g, τ=3469.5±585.9 s, t_d=344.7±280.3 s, R²=0.9888.
- Pump map: 0.34174 t/h/rpm through-origin (matches committed constant to 5 dp), η_v=0.980.
- Pinned state: LT-322504=80.0000%, F_CO2_th=54.618 t/h, F_in_BL_th=42.762 t/h,
  pumpB speed_act=127.0131 rpm, EJ_MOTIVE_NH3_DES=42762.05 kg/h. Sim tick dt=0.1 s.
- Anomaly flagged (not yet actioned): LIC-322501 MV saturated 102.8% while LV-322501
  moved 0→30% during startup — level loop not in closed-loop control in that window.

## Failed / rejected approaches (don't repeat)

- **UREA-LOAD fit for τ calibration — REJECTED.** Non-monotonic, operator-driven
  (τ=1067±415 s, R²=0.9306, ±12% residuals). Used only to bracket the feed-introduction
  window, never as a process time constant.
- **Hard-coding τ=3470 s as a lag on synthesis pressure — REJECTED.** Would double-count
  the inventory ODE dynamics and violate conservation. τ is a validation target only.
- **Using interpolated grid rows from the xlsx — REJECTED.** Linear interpolation between
  anchors carries zero dynamic information; only exact ruler anchors were used.
- **Flow derating from hydraulic resistance — REJECTED.** I/ṁ rises with P_syn (r=0.975)
  but flow stays on the PD line, so it's motor-load only (not simulated). No flow penalty.
- Initial `git push`/audit path used `tests/run_full_audit.py` (wrong) — real path is
  `backend/tests/run_full_audit.py`.

## Next steps (if work resumes)

1. **Optional transient acceptance check (report §6.4):** run a sim cold-start and confirm
   the emergent pressurization τ_sim lands in [2884, 4055] s and t_d,sim ≤ 572 s,
   P_f ∈ [137.5, 150.5] bar g. This is the empirical validation of the injection — the
   suites above only prove conservation/bit-exactness, not that the delay reproduces the
   observed dynamics. No harness for this exists yet; would need a cold-start driver.
2. **Investigate the LIC-322501 startup anomaly** — determine whether the model should
   represent the open-loop level window or whether it's purely a DCS-tuning artifact.
3. **Merge** `fix/reactor-level-drain-and-vent-coupling` once §6.4 transient check passes.

## Environment

- Python 3.14, pandas 3.0.3, scipy 1.17.1, numpy 2.4.2.
- Windows; PowerShell primary (no `&&` — use `;`), Bash tool for POSIX.
- Run audits from `D:\Work\Urea Simulation\backend`.
