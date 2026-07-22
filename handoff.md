# Handoff Summary

## The goal we're working toward
Calibrate the `backend/main.py` state-space process engine against real DCS startup trend data
without violating mass/energy conservation, and keep the HMI overlay registered on the baked DCS
screenshots. A full Mixture-of-Experts Red Team (Expert_Interrogation_Log.md) then interrogated the
engine; its consensus plan (Agent G, 8 items) is now fully implemented and gated. The 328/329
rename, the FFIC-329401 ratio basis, TD-002..TD-005, and Red Team CP-1..CP-5 + CP-7 are all closed.
Open: TD-001 (ejector helper), TD-006 (rigorous stripper enthalpy balance — G8 shipped the
feed-proportional increment), the stale `graphify` graph, and `Master_PID_Tuning_Constants.md`.

## Current state of the code
* HEAD `412c9d3` on `master`. `origin/master` is at `a6a88a6` — **G7 (`bf77691`) and G8 (`412c9d3`)
  are committed locally but NOT yet pushed** (see Next steps).
* Red Team consensus plan (Agent G) — ALL of it landed, each gated pin 25/15/0 + suite 110 passed:
  * `40abe51` G1 — `STEP_CAP` 0.5 -> 0.25 (CP-1: FAST-mode integrator diverged above ~0.389 s).
  * `40abe51` G3 — stream-741 recycle made a true 740-diversion, exotherm un-fabricated (CP-2/CP-3).
  * `a4ed821` G4 — TIC-328008 SP constrained to its reachable band (CP-4). _ctrl_ipd is velocity
    form, proven anti-windup, so no controller change was needed.
  * `a4ed821` G5 — HPCC published pressure clamped to the feed-supply head (CP-5, 221 bar -> 144.2).
  * `a6a88a6` G6 — new `backend/test_session_regression_gate.py` (7 tests) covering what the boot
    pin structurally cannot: step-cap guard, step-invariance, runtime-loop-at-design, 740-node
    conservation, HPCC ceiling, master fixed points. Suite 103 -> 110.
  * `bf77691` G7 — routed the nine 324/335 faceplates (were silently discarding writes), extended
    the crystallization banner into a general annunciator surfacing the 4 hidden process flags +
    OOR rows, cas:true on FIC-328404, restored CAS_UNWIRED for TIC-323013/FIC-329402, LSK v3->v4.
  * `412c9d3` G8 — stripper MP-steam duty now tracks feed load (CP-7); bit-exact at design against
    STRIP_FEED_DES_KGH, no pin-contract change. Full enthalpy balance deferred as TD-006.
* Earlier this session (pushed at `a6a88a6` and before): `37504eb` 12 frames + 329xxx rename +
  FIC-328402 volumetric; `26d35de` FFIC T/M3 ratio + FV-326402->329402; `76b97b7` 321-1/323-1
  registration + RHO_744 rename + FV-328401->329401.
* `launch.bat` carries an unrelated uncommitted change (adds `pip install -r requirements.txt`).
* Expert_Interrogation_Log.md (repo root) holds all 81 panel findings + Agent G's arbitration.
* `launch.bat` carries an unrelated uncommitted change (adds `pip install -r requirements.txt`).
  Left unstaged deliberately. `backend/requirements.txt` exists and the path resolves.

## RETRACTED — "no interpreter on this machine" was WRONG
An earlier revision of this file, and the "NOT GATED" notes in commits `37504eb`, `26d35de`,
`76b97b7` and `c063485`, claimed no Python existed here. That was a bad inference from testing
only the bare `python` alias (which IS a Store stub and errors) plus `where.exe python`.

**Python 3.14.6 is installed and works.** Use `python3` or `py`:

```
%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe      # MSIX alias, PythonSoftwareFoundation.PythonManager
%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe   # the real binary
```

`pymanager list` shows the installed runtimes. `fastapi`/`uvicorn`/`pydantic`/`openpyxl` were
already present; `pytest` and `httpx` were installed this session. Run the suite with
`-p no:cacheprovider` — `backend/.pytest_cache` holds stale dirs that raise `WinError 183`.

**All gates are GREEN and every earlier NOT-GATED warning is retracted:**
* Pin gate at `c063485` and after every change since: `leaves: 25  keys: 15  diffs: 0`.
* Test suite: **103 passed**, unchanged from the pre-change baseline.

## CLOSED this session
* **FFIC-329401 ratio basis.** Ruled by the plant control narrative: on CAS, FIC-329401's SP is
  `FIC-328402 * ratio` and FV-329401 strokes to hold it. The denominator is therefore the
  FIC-328402 wash leg (stream 744) — the earlier rebase off stream 738 was correct. Because
  FIC-328402 is a VOLUMETRIC (m3/h) loop, the ratio must be **T/M3**, which is exactly what the
  baked 328-1 panel reads (`SP 0.169 T/M3 / MV 0.168 T/M3`). It had been coded as dimensionless
  kg/kg. Now `R328_FFIC_RATIO_DES = (M931_DES/1000)/(M744_DES/RHO_744_KGM3) = 6.495/31.4 =
  0.20685 T/M3`, with `ffic_pv` written in the SAME float operation order so the design point stays
  bit-exact (`m744_prev`/`m931_prev` both default to design on tick 0 -> `pv == sp` -> `du == 0`).
  * An earlier analysis in this file argued for stream 749. **That was wrong and has been removed.**
    749 is the C004 feed, but the DCS ratio station measures the FIC-328402 leg, not the feed.
* **CAS chain verified** by reading it end to end: `ffic_op` -> `_fic_flow(FIC_329401, cas_sp=ffic_op)`
  -> `_ctrl_ipd` sets `c["sp"] = cas_sp` when `mode == "CAS"` -> `c["op"]`, which the FV-329401
  avalve overlay binds. `FIC_328402`'s own `_fic_flow` call passes no `cas_sp`, so FFIC-329401 has
  no authority over it.
* **Constant naming.** `RHO_744_KGM3` / `S744_VOL_DES`. The FIC-328402 leg carries 31478 kg/h =
  stream 744 (44 C, 1 bar, rho 1002), not 735 (31114 kg/h, 56 C, 4.1 bar, rho 992.4); both have a
  PFD volume flow of 31.4 m3/h, which is what hid it. The back-solved 1002.48 matches the PFD's own
  744 density to 0.05 %, so it was the right number under the wrong name. Genuine stream-735
  references elsewhere (`m_735`, `R328_C002_M738_DES`, `RHO_401_KGM3 = 992.4`) are correct, untouched.
* **Tag typos:** `FV-326402` -> `FV-329402`, `FV-328401` -> `FV-329401`. Zero `326402` or `FV-328401`
  references remain in `backend/main.py` or `frontend/`.
* **Overlay registration.** 58 overlays moved in total across four screens, all now within ~1 px of
  their baked value-bar centre:
  * 328-1 / 324-1b (12): `TT-328006` was on bare pipe with no box at all; `FIC-328402` was parked on
    the FV-328402 valve symbol instead of its own flow box; a `dX ~ -25` cluster of eight was real
    drift, not convention.
  * 323-1 (29): uniform `dY ~ +21 px` on EVERY overlay — a whole-screen vertical registration error.
  * 321-1 (17): progressive `dY`, -2.6 px at y=178 growing to -19.5 px at y=587 — a y-SCALE error of
    about 4 %. Its header comment claims native 1287x612 while the PNG is 1355x644.
  * Every match was eyeballed on a contact sheet before rewriting; each box's baked unit label agrees
    with the overlay's declared unit. `LSL-321501` (a lamp) and `FT-322403` (a label) have no value
    box and were correctly skipped.

## OPEN — logged in TECH_DEBT.md
* **TD-002 (blocker-grade, pre-existing):** `FIC-323402`, `FIC-328404`, `FIC-328406` bind `.vol_m3h`.
  `app.js:471` only takes the backend-authoritative branch when a bind ends in `.pv`, so these three
  fall back to localStorage for SP/OP/mode. The faceplate shows m3/h but writes the typed number
  straight into a kg/h controller, the "bumpless" MAN->AUTO handler injects the same unit error on a
  plain mode click, and the displayed mode is fabricated (`FIC_328404` is seeded CAS and gets kicked
  to AUTO; `FIC_328406` is pinned MAN and displays AUTO). `FIC-328402` had this exact defect and was
  fixed by converting the loop to genuinely volumetric — repeat that pattern, but only on a machine
  that can re-gate. Densities already exist: `S791_VOL_DES`, `S775_VOL_DES`, `A328_M755_RHO`.
* **TD-003 (pre-existing tuning):** `FFIC-329401` `Kc = 0.8` gives a loop coefficient of
  `1 - 5e-7`, i.e. the ratio master is effectively inert — moving the ratio SP will not move
  FV-329401 on any useful timescale. Needs roughly 3e4 kg/h per T/M3, so `Kc` is four to five orders
  low. NOT introduced by the T/M3 change (the old kg/kg basis had the same gain to within 0.25 %).
  Design fixed point is unaffected, so the pin is safe; only operator SP moves expose it.

## Files actively edited
`backend/main.py`, `frontend/overlays.js`, `handoff.md`, `TECH_DEBT.md`, `CLAUDE.md` — all committed.

Verification tooling lives in the session scratchpad and is NOT tracked; rebuild if needed:
`boxlib.ps1` (baked-DCS-box locator via .NET System.Drawing), `audit_overlay.ps1` (per-screen
placement table), `sheet2.ps1` (contact sheet for eyeballing box identity), `apply_coords.ps1`
(rewrites overlay x/y to measured bar centres), `crop.ps1`, `rowprof.ps1`.

## Everything tried that failed
* Concluding "no Python on this machine" from `python --version` plus `where.exe python`. The bare
  `python` alias is a Store stub that errors, but `python3` and `py` both work (3.14.6). Testing one
  alias and generalising cost this session five ungated commits and a large amount of unnecessary
  static-only analysis. Check `pymanager list` before ever concluding an interpreter is absent.
* Piping a heredoc into the `python` Store stub: it HANGS for the full command timeout. Never
  `python - <<EOF` against the stub alias.
* Judging overlay placement from the whole black blob centroid: the baked DCS indicator is a flag
  (wide value BAR plus a narrower TAB below), so the centroid sits about 5 px low. Isolate the BAR.
* Isolating the bar as the "longest contiguous run of rows at >=90 % of max width": the green value
  text erodes row extent and truncates the run, landing on the box's top edge. Use first..last row
  at >=60 % of max width — the tab is about 40 % of bar width, so 60 % separates cleanly.
* Rewriting `overlays.js` with PowerShell `Get-Content` / `Set-Content`: both default to the system
  ANSI codepage here, which MOJIBAKED all 16 em dashes and prepended a BOM. Caught by the diff being
  91 lines when only 46 were expected. Use `[System.IO.File]::ReadAllLines/WriteAllLines` with
  `New-Object System.Text.UTF8Encoding $false`.
* Naming a PowerShell loop variable `$e`-vs-`$r` carelessly: `$r` collides with a `-R` parameter
  (PowerShell is case-insensitive) and throws a type-conversion error.
* Committing only `frontend/` to dodge the ungated `main.py`: impossible, the overlay binds and the
  backend rename are one atomic change; a frontend-only commit leaves dead binds.
* Two audit workflows: the first hit the session limit at 14/52 agents, the second hit the WEEKLY
  limit at 12/27 (resets Jul 22, 2am Africa/Cairo). In both, dead refuters returned a null verdict
  which the script bucketed as "refuted", so its "0 survived" headline was an artifact — the 15
  unjudged findings had to be triaged by hand. If re-running, count null verdicts separately.
* Making HIC/HV-329606 live: no motive-steam physics exists and a live draw would double-count a
  golden-pin key (the 1400 kg/h is already inside lumped `M_USERS_LP`).
* Deriving `MV_DES` by subtraction and `PHIV` by division: breaks the PIC-323203 fixed point by
  round-off. `PHIV` must be defined first.
* Judging the D011 balance from telemetry `m_kgh`: rounds to 1 dp, manufacturing a phantom steady
  residual. Use dM/dt.
* Short horizons (600/1200/1800 s) to demand Comp I "settle": Comp I's own tau is 16,098 s.
* `ff718_perturb.py`: obsolete, kicks the wrong leg. Superseded by `dyn718r.py`.

## How to gate (works on this machine — see the retraction above)
```
set PY=%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe
%PY% scratchpad\regress.py scratchpad\pin_now.json
%PY% scratchpad\pindiff.py scratchpad\pin_now.json scratchpad\golden_pin.json   ->  25 / 15 / 0
cd backend && %PY% -m pytest -q -p no:cacheprovider                             ->  103 passed
%PY% scratchpad\probe_ffic_gain.py 600        # TD-003 authority probe, expect FV-329401 +2.5 %
```

## Standing session commands (see CLAUDE.md section 6)
* **Caveman mode ON** — invoke the `caveman` skill at session start, keep it active for prose.
  Code, commit messages and PR text stay in normal English.
* **Graphify** — knowledge graph in `graphify-out/`, currently 6080 nodes / 6355 edges built from
  `411080c`, i.e. many commits stale. The CLI is now INSTALLED (`graphifyy` 0.9.22); `graphify.exe`
  is in `%LOCALAPPDATA%\Python\pythoncore-3.14-64\Scripts\` and is NOT on PATH.
  **The refresh could not be completed this session and the graph was deliberately left untouched:**
  * `detect_incremental` finds 131 changed files (73 code, 52 docs, 6 images) + 1 deleted.
  * The 58 doc/image files have ZERO cache hits, so they need LLM semantic extraction — which needs
    subagents (blocked: agent weekly limit, resets Jul 22 2am Africa/Cairo) or a Gemini key.
  * Running AST-only and merging is actively HARMFUL: `docs/urea-project-conversation.md` alone
    supplies 4487 of the 6080 nodes, and `build_merge`'s dedup collapses 4327 of them, shrinking the
    graph to ~1858. graphify's `to_json` shrink guard (#479) refuses the write, so nothing was lost,
    but the run is wasted. `graph.json` was verified intact at 6080 afterwards.
  * The manifest WAS advanced by `save_manifest` before that was understood; its 73 code entries
    were then dropped again so the next `--update` re-extracts them. Do the same if you abort a run
    partway — otherwise files are marked done while the graph still holds their stale nodes.
  * Re-run the full `/graphify` pipeline once semantic extraction is available.
* **`/project-scaffolding`** — scaffolding wizard for NEW projects. Do NOT point it at this repo
  root; it would scaffold over a mature codebase. Use only for a new sub-project in an empty
  directory, confirming the target path first.

## Next steps
1. Install the `graphify` CLI, then `graphify update .` to bring the graph up from `411080c`.
2. `Master_PID_Tuning_Constants.md` still names the loops by their pre-rename tags and the retired
   ratio basis — refresh it.
4. Confirm the 321-1 / 323-1 registration against the RUNNING HMI. Drag positions in localStorage
   `ots_ov_pos_v3` override the seed coords, so a browser that has been drag-nudged before will not
   show the corrected seeds until those keys are reset.
5. `FFIC-329401` and `TIC-328012` sit on two-box SP/MV ratio panels; which row the live PV should
   cover is a design decision, left alone.
6. Decide whether to build the ejector motive-steam model.
7. Still blocked on you: sprint items 7, 22, 25, and item 3a (#17) pending a 328D003 level controller.
