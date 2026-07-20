# Urea Plant OTS - Master Architecture & Directives

**Project:** High-fidelity Stamicarbon CO2-stripping Urea Operator Training Simulator (OTS).
**Stack:** Python (FastAPI/WebSockets) backend, HTML/CSS/JS frontend.

## 0. Core Reference Documents (STRICT)
* **Primary HMB / stream authority:** `D:\Work\Urea Simulation\References\Combined_1750_MTPD_100% load_PFD TablesProcess_Data`
  (on disk as `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`).
  This document is the ruling source for **every mass-balance and stream-discrepancy resolution from now on**.
  When a coded constant disagrees with it, the PFD value wins and the surrounding network is re-derived to
  close around the PFD value — the coded value is never preserved for pin convenience.

## 1. Core Physics & Dynamic Modeling Laws (STRICT)
* **The Domino Effect (Transient Propagation):** The simulation MUST run as a fully dynamic, coupled state-space system. Any local process perturbation (e.g., valve movement, pump trip, composition shift) must recursively calculate and propagate downstream (D/S) in real time. Downstream streams and equipment must experience continuous, cascading updates to both their physical properties and multi-component compositions.
* **100% Conservation Accuracy:** Every module must strictly resolve simultaneous differential equations for mass, component, and energy balances. 
  * Mass & Component: $\frac{dM_i}{dt}=\sum\dot{m}_{in,i}-\sum\dot{m}_{out,i}\pm\mathcal{R}_i$
  * Energy: $\frac{dU}{dt}=\sum(\dot{m}h)_{in}-\sum(\dot{m}h)_{out}\pm\dot{Q}\pm\dot{W}$
  * Mass or energy must never be created, destroyed, or decoupled to bypass mathematical stiffness.
* **Rigorous Reaction Kinetics:** Forward and reverse reaction rates for carbamate synthesis and urea conversion must be derived using native temperature, pressure, and exact local activities/compositions. No linear or static shortcuts.
* **The Sourcing Law:** Base all thermodynamic equations, kinetic models, and fluid dynamics on verified sources (UreaKnowHow, Stamicarbon/Uhde patents, or peer-reviewed literature). Do not fabricate physical constants.
* **The Design Anchor:** All off-design dynamic equations must resolve to be bit-exact with the provided 100% steady-state Heat and Material Balance (HMB).

## 2. Autonomous Execution Workflow (STRICT MANDATE)
* **No Halting:** Do NOT halt for approval. Deep research, plan, execute, and write the correct code continuously. Autonomously commit and push once a task is complete and verified. Halt only on a hard blocker that requires external data you cannot derive or locate yourself (a missing datasheet, a field trend, a credential).
* **Tool & Skill Mandate:** You MUST actively use your available skills (Bash execution, file reading, `grep`, and MCP tools) to perform tasks. Never guess file paths, function names, or existing state variables. Prove your assumptions by searching the codebase before writing new logic.
* **The Baseline Regression Test (STRICT MANDATE):** Before confirming any code change (adding, editing, or deleting logic), you MUST mathematically and programmatically test the output against the 100% steady-state design values. If a change breaks the design anchor or introduces mass/energy drift at steady state, you must discard the approach and recalculate.
  * **Pin gate (CRITICAL, non-negotiable for any thermodynamic or physics-engine change):** the gate is TWO steps, not one. `scratchpad/regress.py` only *dumps* `_collect_pin()`; it does NOT diff. Run it, then leaf-wise `repr()`-diff the dump against `scratchpad/golden_pin.json`. Expected: `leaves: 25  keys: 15  diffs: 0`. A single non-zero diff blocks the commit.
  * The pin key SHA-256s exactly `("main.py", "steam_system.py", "reactor.py", "controllers.py")` (`_PIN_SRC_FILES`). Editing any of those four rehashes the pin and mandates a re-gate. Editing docs, tests, or frontend does not.
* **Scope Lock:** Build strictly ONE unit at a time. Do not anticipate or stub downstream units.
* **UI Enforcement (READ-FIRST MANDATE):** ALWAYS read `ui_guidelines.md` in full BEFORE generating, editing, or scaffolding ANY frontend page/screen/overlay/faceplate — not only on receiving a DCS screenshot. Every new page must conform to its stage (1366×720), typography (`--val-font` + Arial/Segoe/Consolas stacks and the px catalogue), `:root` color tokens, overlay element dimensions, and controller-faceplate pattern. Never introduce fonts, sizes, or colors outside the guideline; never hardcode a color that has a `:root` token.

## 3. Documentation & Version Control
* **Continuous Docs:** Autonomously update `Urea OTS — As-Built Mathematical Reference` to reflect model changes.
* **Remote Backup:** Autonomously commit and push to `https://github.com/amegoh2007/urea-ots.git` after verified fixes. This supersedes the former "push only on explicit request" rule.
* **Surgical Edits:** Diff-only. Replace the specific lines or methods; never rewrite a whole file for a local change.

## 4. Autonomous "Checkout" Protocol (Upstream Integrity)
`plant_state.md` is the absolute source of truth for upstream variables. If you require an upstream output/property NOT listed in `plant_state.md`:
1. **Research & Plan:** Autonomously locate and read the required upstream `[Filename.py]`. Do not hallucinate variables or create dummy inputs.
2. **Execute Update:** Autonomously write the required physical calculation into the upstream model, sourced per the Sourcing Law.
3. **Update State:** Autonomously rewrite `plant_state.md` with the new variable.
4. **Resume:** Immediately proceed with the current unit construction. Do not await user confirmation.

## 5. Mandatory Session Handoff Updates (STRICT)
At the end of EVERY session, automatically update `D:\Work\Urea Simulation\backend\handoff.md`. No exceptions, no prompting required. The update MUST carry these five sections explicitly:
1. **The Goal:** What we are currently working toward.
2. **Current State:** The exact operational state of the code.
3. **Active Files:** Which files are being actively edited.
4. **Failed Attempts:** Everything tried that failed — recorded to prevent future circular debugging.
5. **Next Steps:** The exact next step you would take.