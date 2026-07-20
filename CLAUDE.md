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
