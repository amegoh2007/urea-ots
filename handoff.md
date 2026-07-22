# Handoff Summary

## The goal we're working toward
Calibrate the `backend/main.py` state-space process engine against real DCS startup trend data
without violating mass/energy conservation, and keep the HMI overlay registered on the baked DCS
screenshots. A full Mixture-of-Experts Red Team (`Expert_Interrogation_Log.md`) interrogated the
engine and produced an 8-item consensus plan (Agent G); that plan is now fully implemented, gated,
and pushed. Every Red Team critical-path finding (CP-1..CP-5, CP-7) and TD-002..TD-005 are closed.

## Current state of the code
* HEAD `efcca71` on `master`; **`origin/master` is level — everything is pushed.**
* All gates GREEN after every change: pin `leaves 25 / keys 15 / diffs 0`, suite **110 passed**.
* Red Team plan (Agent G), each item individually gated:
  * `40abe51` G1 — `STEP_CAP` 0.5 -> 0.25 (CP-1: FAST-mode integrator diverged above ~0.389 s).
  * `40abe51` G3 — stream-741 recycle made a true 740-diversion + exotherm un-fabricated (CP-2/CP-3).
  * `a4ed821` G4 — TIC-328008 SP constrained to its reachable band (CP-4). `_ctrl_ipd` is velocity
    form, proven anti-windup, so no controller change was needed.
  * `a4ed821` G5 — HPCC published pressure clamped to the feed-supply head (CP-5, 221 -> 144.2 bar).
  * `a6a88a6` G6 — `backend/test_session_regression_gate.py` (7 tests) covering what the boot pin
    cannot: step-cap guard, step-invariance, runtime-loops-at-design, 740-node conservation, HPCC
    ceiling, master fixed points. Suite 103 -> 110.
  * `bf77691` G7 — routed the nine 324/335 faceplates (were silently discarding writes), extended
    the crystallization banner into a general annunciator (4 hidden process flags + OOR rows),
    `cas:true` on FIC-328404, restored `CAS_UNWIRED` for TIC-323013/FIC-329402, LSK v3 -> v4.
  * `412c9d3` G8 — stripper MP-steam duty now tracks feed load (CP-7); bit-exact at design against
    `STRIP_FEED_DES_KGH`, no pin-contract change. Full enthalpy balance deferred as TD-006.
* Earlier this session (also pushed): `37504eb` 12 frames + 329xxx rename + FIC-328402 volumetric;
  `26d35de` FFIC T/M3 ratio + FV-326402->329402; `76b97b7` 321-1/323-1 registration (46 overlays) +
  RHO_744 rename + FV-328401->329401; plus TD-002 (volumetric faceplates) and TD-003 (FFIC Kc
  0.8 -> 8.0e5) which are RESOLVED in TECH_DEBT.
* `launch.bat` has an unrelated uncommitted change (adds `pip install -r requirements.txt`); left
  unstaged. `backend/requirements.txt` exists untracked and the path resolves.

## Python on this machine (do NOT re-derive — this cost the session dearly)
The bare `python` alias is a Microsoft Store stub that errors; testing only it (and `where.exe
python`) led to a wrong "no interpreter" conclusion and five commits shipped with false NOT-GATED
warnings, all since retracted. **Python 3.14.6 IS installed** — use `python3` or `py`:

```
%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe      # MSIX alias
%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe   # real binary
```

`pymanager list` shows runtimes. Never conclude an interpreter is absent from one alias. Never pipe
a heredoc into the stub alias — it hangs for the full timeout. `fastapi/uvicorn/pydantic/openpyxl`
were present; `pytest`/`httpx` were installed this session.

## How to gate
```
set PY=%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe
%PY% scratchpad\regress.py scratchpad\pin_now.json
%PY% scratchpad\pindiff.py scratchpad\pin_now.json scratchpad\golden_pin.json   ->  25 / 15 / 0
cd backend && %PY% -m pytest -q -p no:cacheprovider                             ->  110 passed
```
Use `-p no:cacheprovider` — `backend/.pytest_cache` holds stale dirs that raise `WinError 183`.

## OPEN items (in TECH_DEBT.md)
* **TD-001** — `phi_sp` ejector-spindle test helper still encodes the superseded positive law
  (model side is correct; only the audit helper is stale). Directive was "leave phi_sp alone".
* **TD-006** — the G8 stripper duty is feed-PROPORTIONAL, not the rigorous per-species enthalpy
  balance (Agent A: +30 % feed demands ~+12 %, not +30 %), and there is no steam-limited flood
  regime. Needs a species-enthalpy layer the model lacks (only a mean `STRIP_CP_BOTTOM`); larger,
  pin-sensitive, deferred deliberately.

## Standing session commands (CLAUDE.md section 6/7)
* **Caveman mode ON** — invoke the `caveman` skill at session start; prose only, code/commits normal.
* **Graphify** — CLI now INSTALLED (`graphifyy` 0.9.22; `graphify.exe` in
  `%LOCALAPPDATA%\Python\pythoncore-3.14-64\Scripts\`, NOT on PATH). Graph is `graphify-out/`, 6080
  nodes / 6355 edges, still built from `411080c` (many commits stale). NOT refreshed this session:
  a `graphify update .` needs LLM semantic extraction of 58 changed doc/image files (0 cache hits),
  which needs subagents or a Gemini key. **Do NOT run AST-only and merge** — one doc file supplies
  4487 of 6080 nodes and `build_merge`'s dedup collapses the graph to ~1858 (the `to_json` shrink
  guard rejects the write, so it just wastes a run). If a run is aborted after `save_manifest`, drop
  the stamped code entries from `manifest.json` so the next `--update` re-extracts them.
* **`/project-scaffolding`** — wizard for NEW projects. Do NOT point at this repo root; use only for
  a new sub-project in an empty directory, confirming the path first.

## Durable gotchas (things that wasted time — don't repeat)
* Overlay placement: the baked DCS indicator is a flag (wide value BAR + narrower TAB below), so the
  black-blob centroid sits ~5 px low. Isolate the BAR as first..last row at >=60 % of max width (the
  tab is ~40 % of bar width). Tooling in scratchpad (untracked): `boxlib.ps1`, `audit_overlay.ps1`,
  `sheet2.ps1`, `apply_coords.ps1`, `crop.ps1`, `rowprof.ps1`.
* Rewriting `overlays.js` from PowerShell: `Get-Content`/`Set-Content` default to the ANSI codepage,
  which mojibakes the 16 em dashes and prepends a BOM. Use `[System.IO.File]::ReadAllLines/
  WriteAllLines` with `New-Object System.Text.UTF8Encoding $false`.
* Workflow audits: a dead/limit-killed refuter returns a NULL verdict; the script bucketed null as
  "refuted", so a "0 survived" headline was an artifact. Count null verdicts separately and Read the
  journal before trusting a workflow's summary.
* Backend changes to R323_CTRL_MODES / any of the four pin-hashed files invalidate the pin CACHE
  (forces a re-settle) but do NOT change the 15 pin VALUES — expect `diffs 0` still.

## Next steps
1. Refresh the graphify graph (CLI is installed; run the full `/graphify` pipeline once semantic
   extraction — subagents or a Gemini key — is available; do not AST-only-merge).
2. `Master_PID_Tuning_Constants.md` still names loops by pre-rename tags / the retired ratio basis.
3. Confirm the 321-1 / 323-1 registration on the RUNNING HMI. LSK was bumped v3 -> v4 (G7) so stale
   drag positions should be discarded, but verify in a browser.
4. `FFIC-329401` / `TIC-328012` sit on two-box SP/MV ratio panels; which row the live PV covers is a
   design decision, left alone.
5. TD-006 (rigorous stripper enthalpy balance + flood regime) when a species-enthalpy layer is in.
6. Decide whether to build the ejector motive-steam model.
7. Blocked on you: sprint items 7, 22, 25, and item 3a (#17) pending a 328D003 level controller.
