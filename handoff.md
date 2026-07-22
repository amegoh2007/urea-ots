# Handoff Summary

## The goal we're working toward
Calibrate the `backend/main.py` state-space process engine against real DCS behaviour without
violating mass/energy conservation, and keep the HMI overlay registered on the baked DCS
screenshots. The current thread is a **full modelling-equation audit of every equipment tag**
against the eleven equation categories (total mass, component species, energy, flash, EoS/activity,
summation, kinetics, transport, hydraulic, constitutive, control), answering four questions per
tag: are the equations bound correctly, is the solver engine right, is hybrid variability required,
and what equations are missing. Deliverable mode is **audit + auto-fix**, one unit at a time.

## Current state of the code
* Audit report: **`EQUATION_AUDIT.md`** (new) — architecture verdicts, 10-item findings register,
  per-tag tables for units 320/321/322/323/324/328/329, category coverage summary.
* **Solver verdict: Sequential-Modular is CORRECT for all ~57 tags.** Recycles are torn with
  prior-step lags; the tear variables are real dynamic states, dt ≪ every process τ, and SM gives
  bounded per-tick cost with no convergence failure — an EO solve could stall the HMI mid-transient
  and would put solver tolerance inside a `diffs 0` contract. No tag needs EO.
* **Hybrid variability: required, already present, but uneven.** Split fractions, calibrated η
  modifiers, back-solved λ/UA, Inoue-Kanai, the ejector spindle law and the soft sensors are all
  legitimate hybrid layers. The gap is that several of them are *frozen constants* rather than
  functions of state (finding F-6).
* **LANDED this session — units 323 + 324 (findings F-1..F-5, F-10):** every vaporiser outside the
  HP loop had its vapour rate bound as a frozen design split fraction of the live inflow, so the
  mass balance and the energy balance were solved independently and the live heater duty had no
  authority over the boil-up. Now:
  * boil-up is duty-limited — `m_vap = min(φ·m_in, m_vap_des·q_avail/Q_des)` on 323C003/323E002,
    323F010/323E010, 324E001, 324E003;
  * 323F004 runs a **true isenthalpic flash**: saturation constraint
    `T_flash = 106 + [Tsat(P) − Tsat(1.13)]` plus the enthalpy balance
    `m_701·λ = m_314·cp·ΔT − M·cp·(T_sat−T)/τ`, which collapses the existing energy ODE to exactly
    `dT/dt = (T_sat − T)/τ` (energy conserved);
  * the 324 melt strengths `w1_live`/`w2_live` are **outputs**, not the pinned `R324_W_EV*`
    constants, and drive `urea_pct` / `PY-324201` / `AY-324701`; Stage-2 feed enthalpy uses the live
    Stage-1 outlet temperature; the recycle carries its live strength via `s.tlag["R324_recyc_w"]`;
  * **F-10** — all four condensing-steam chests floored at `max(Q, 0)`. Un-floored, a shut steam
    valve clamps `p_chest` to 0.02 bar a (Tsat ≈ 17.5 °C) and `UA·(Tsat − T)` turned every heater
    into a *refrigerator*: probe-measured 22 °C Evap-I melt and 13.6 °C in 323C003;
  * `conc_infer_324` gained a band clamp on the reference mole fraction — `w_des` is now a live
    argument that legally reaches 0 on cold start and previously divided by zero there (this is
    what broke the four `test_transient_coldstart` tests mid-pass).
* New tests: `backend/test_equation_audit_323_324.py` (5). Suite 110 -> **115**.
* Docs updated autonomously: As-Built reference gained **Revision Delta #15** (and its stale
  "328E021 hot side is static" gap note marked CLOSED — stream 749 has been a live energy-balance
  closure for some time). `TECH_DEBT.md` gained **TD-007..TD-010**.
* `scratchpad/regress.py` fixed (TD-010): `argv[1]` is now resolved against the original cwd, so
  the gate command as written in CLAUDE.md §7 finally works.

## How to gate
```
set PY=%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe
%PY% scratchpad\regress.py scratchpad\pin_now.json
%PY% scratchpad\pindiff.py scratchpad\pin_now.json scratchpad\golden_pin.json   ->  25 / 15 / 0
cd backend && %PY% -m pytest -q -p no:cacheprovider                             ->  115 passed
```
Use `-p no:cacheprovider` — `backend/.pytest_cache` holds stale dirs that raise `WinError 183`.
**The suite takes 4–6 minutes and the pin settle takes ~2** — run them with a raised timeout or in
the background; the default 2-minute Bash timeout kills both before they print anything.

## Python on this machine (do NOT re-derive — this cost an earlier session dearly)
The bare `python` alias is a Microsoft Store stub that errors. **Python 3.14.6 IS installed:**
```
%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe      # MSIX alias
%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe   # real binary
```
Never conclude an interpreter is absent from one alias. Never pipe a heredoc into the stub alias.

## OPEN items (in TECH_DEBT.md)
* **TD-001** — `phi_sp` ejector-spindle test helper still encodes the superseded positive law
  (model side correct; only the audit helper is stale). Directive was "leave phi_sp alone".
* **TD-006** — G8 stripper duty is feed-PROPORTIONAL, not a rigorous per-species enthalpy balance,
  and there is no steam-limited flood regime. Needs a species-enthalpy layer.
* **TD-007** (audit F-6) — HPCC 322E002 condensation split `HPCC_FRAC_GAS_DES` is invariant to
  shell temperature and loop pressure. Must become φᵢ(T_prod, P) in anchored-correction form, and
  the new loop gain must be checked against the `_disturbance_gate` self-excitation path.
* **TD-008** (audit F-7) — 328C003 hydrolyser has no reaction extent; the Arrhenius rate law
  already exists but only inside the read-only `ppm_infer_328701` soft sensor. Depends on TD-009.
* **TD-009** (audit F-8) — component species balance exists **only in unit 322**. Everything
  downstream of LV-322501 is lumped mass, so there is no C2 balance and no C6 summation equation
  downstream. Largest remaining architectural gap; needs its own project, not a fix slot.

## Standing session commands (CLAUDE.md sections 6/7)
* **Caveman mode ON** — invoke the `caveman` skill at session start; prose only, code/commits normal.
* **Graphify** — CLI installed (`graphifyy` 0.9.22; `graphify.exe` in
  `%LOCALAPPDATA%\Python\pythoncore-3.14-64\Scripts\`, NOT on PATH). Graph is `graphify-out/`, 6080
  nodes / 6355 edges, still built from `411080c` (many commits stale). NOT refreshed: a
  `graphify update .` needs LLM semantic extraction of 58 changed doc/image files (0 cache hits),
  which needs subagents or a Gemini key. **Do NOT run AST-only and merge** — one doc file supplies
  4487 of 6080 nodes and `build_merge`'s dedup collapses the graph to ~1858 (the `to_json` shrink
  guard rejects the write, so it just wastes a run). If a run is aborted after `save_manifest`, drop
  the stamped code entries from `manifest.json` so the next `--update` re-extracts them.
* **`/project-scaffolding`** — wizard for NEW projects. Do NOT point at this repo root.

## Durable gotchas (things that wasted time — don't repeat)
* **Subagent/workflow capacity is a real blocker.** A 12-agent audit workflow was launched and
  every agent died on "You've hit your session limit"; the workflow returned `[]` with
  `agents_done 0, agents_error 12`. Zero results were cached, so resuming would re-run everything.
  The audit was then done **inline in the main loop**, unit by unit, which is also what Scope Lock
  wants. Prefer inline for this repo.
* Workflow audits: a dead/limit-killed refuter returns a NULL verdict; the script bucketed null as
  "refuted", so a "0 survived" headline was an artifact. Count nulls separately and Read the journal.
* Overlay placement: the baked DCS indicator is a flag (wide value BAR + narrower TAB below), so the
  black-blob centroid sits ~5 px low. Isolate the BAR as first..last row at >=60 % of max width.
* Rewriting `overlays.js` from PowerShell: `Get-Content`/`Set-Content` default to the ANSI codepage,
  which mojibakes the em dashes and prepends a BOM. Use `[System.IO.File]::ReadAllLines/WriteAllLines`
  with `New-Object System.Text.UTF8Encoding $false`.
* Backend changes to any of the four pin-hashed files invalidate the pin CACHE (forces a re-settle)
  but do NOT change the 15 pin VALUES — expect `diffs 0` still.
* The pin is a **unit-322 contract only** (HPCC_UA, REACT_TEAR_DES, GCB pins …). It is blind to
  323/324/328 behaviour, so `diffs 0` alone does NOT prove a downstream change is safe — probe it.

## Next steps
1. **TD-007** (HPCC φᵢ(T,P)) — highest-value remaining fix; pin-sensitive, needs anchored-correction
   form and a `_disturbance_gate` loop-gain check.
2. **TD-009** then **TD-008** — species layer downstream of 322, then real hydrolyser kinetics.
3. Refresh the graphify graph once semantic extraction is available (do not AST-only-merge).
4. `Master_PID_Tuning_Constants.md` still names loops by pre-rename tags / the retired ratio basis.
5. Confirm the 321-1 / 323-1 registration on the RUNNING HMI (LSK was bumped v3 -> v4).
6. `FFIC-329401` / `TIC-328012` sit on two-box SP/MV ratio panels; which row the live PV covers is a
   design decision, left alone.
7. Decide whether to build the ejector motive-steam model.
8. Blocked on you: sprint items 7, 22, 25, and item 3a (#17) pending a 328D003 level controller.
