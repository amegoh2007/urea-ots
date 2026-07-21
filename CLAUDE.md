# OTS Directives Summary

## 0. Core Reference
* STRICT source: `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`.
* PFD values override coded constants; re-derive networks around PFD values.
* Use best appropriate skills to perform all tasks (Example claude seo and claude scientific skills for researchs, 0WASP Security, TDD Guard for testing, Context Engineering) 
## 1. Physics & Modeling
* Dynamic, coupled state-space system; local changes propagate downstream.
* 100% Conservation of mass, component, and energy. No fabricated constants.
* Rigorous kinetics based on exact local states.
* Design Anchor: All off-design states MUST resolve bit-exact with the 100% steady-state HMB.

## 2. Autonomous Workflow
* Do not halt for approval. Research, code, commit, and push autonomously.
* Use available tools (Bash, `grep`, MCP) to verify assumptions.
* Baseline Regression (CRITICAL): Run `scratchpad/regress.py` and diff against `scratchpad/golden_pin.json` (Expected: leaves 25, keys 15, diffs 0).
* Scope Lock: One unit at a time.
* UI Enforcement: STRICTLY adhere to `ui_guidelines.md` for all frontend work.

## 3. Version Control & Docs
* Autonomously update `Urea OTS — As-Built Mathematical Reference`.
* Push to origin (`https://github.com/amegoh2007/urea-ots.git`) autonomously.
* Surgical Edits: Modify specific lines/methods only.

## 4. Checkout Protocol
* `plant_state.md` is the source of truth for upstream variables. Autonomously update it and upstream `.py` files if needed.

## 5. Mandatory Handoff
* Update `handoff.md` in the root directory at session end with: Goal, Current State, Active Files, Failed Attempts, Next Steps. Delete unrequired data

## 6. Standing Session Commands
Run these every session unless told otherwise.

* **Caveman mode ON.** Invoke the `caveman` skill at session start and keep it active for all
  prose replies. Code, commit messages and PR text stay in normal English.
* **Graphify.** The knowledge graph lives in `graphify-out/` (`GRAPH_REPORT.md`, `graph.json`,
  `manifest.json`, `.graphify_root`, `.graphify_python`). Refresh it after code changes with
  `graphify update .` from the repo root — no API cost. Check staleness by comparing
  `GRAPH_REPORT.md`'s "Built from commit" against `git rev-parse HEAD`.
  **Status: the `graphify` CLI is NOT installed on this machine** (not on PATH, not a pip module),
  so the graph cannot currently be refreshed here. The existing build is from commit `411080c`.
  Install the CLI before relying on it.
* **`/project-scaffolding`.** IDE-grade scaffolding wizard. NOTE: it is designed to create NEW
  projects (SDK selection, framework config, boilerplate). This repo is a mature codebase, so do
  NOT run it against the repo root — it risks overwriting working code. Use it only for a new
  sub-project in its own empty directory, and confirm the target path first.

## 7. Python on this machine (do not re-derive)
The bare `python` alias is a Microsoft Store stub and errors. Python 3.14.6 IS installed:

```
%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe      # or py.exe -- MSIX alias
%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe   # the real binary
```

`pymanager list` shows installed runtimes. Never conclude "no Python" from `python --version` or
`where.exe python` alone. Never pipe a heredoc into the stub alias — it hangs until timeout.

Gate commands:
```
%PY% scratchpad\regress.py scratchpad\pin_now.json
%PY% scratchpad\pindiff.py scratchpad\pin_now.json scratchpad\golden_pin.json   -> 25 / 15 / 0
cd backend && %PY% -m pytest -q -p no:cacheprovider                             -> 103 passed
```
Use `-p no:cacheprovider`: `backend/.pytest_cache` holds stale dirs that raise `WinError 183`.
