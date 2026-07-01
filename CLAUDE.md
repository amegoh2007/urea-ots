# Urea Plant OTS - Master Architecture & Directives

**Project:** High-fidelity Stamicarbon CO2-stripping Urea OTS.
**Stack:** Python (FastAPI/WebSockets) backend, HTML/CSS/JS frontend.

## 1. Core Physics & Dynamic Modeling Laws
* **The Domino Effect:** Fully dynamic, coupled state-space system. Perturbations must cascade downstream recursively in real time.
* **100% Conservation:** Strictly resolve simultaneous differential equations for mass/energy balances. Never decouple to bypass stiffness.
* **Rigorous Kinetics:** Forward/reverse rates derived from local T, P, and exact activities. No static shortcuts.
* **Sourcing Law:** Base all equations on verified sources (Stamicarbon/Uhde/literature).
* **Design Anchor:** Off-design dynamic equations must resolve bit-exact with the 100% HMB.

## 2. Autonomous Execution Workflow (STRICT MANDATE)
* **No Halting:** Do NOT halt for approval. Deep research, plan, execute, and write the correct code continuously.
* **Skill Mandate:** Mandatory to use the most appropriate skills in all phases (Bash, `grep`, plan-and-execute). Never guess paths or state variables; prove assumptions via search.
* **Baseline Regression:** Mathematically/programmatically test against the 100% design anchor before confirming code. Discard and recalculate if mass/energy drifts at steady state.
* **Scope Lock:** Build strictly ONE unit at a time.
* **UI Enforcement:** Automatically apply `ui_guidelines.md` upon receiving a DCS screenshot.

## 3. Documentation & Version Control
* **Continuous Docs:** Autonomously update `Urea OTS — As-Built Mathematical Reference` to reflect model changes.
* **Remote Backup:** Autonomously commit and push to `https://github.com/amegoh2007/urea-ots.git` after verified fixes.

## 4. Autonomous "Checkout" Protocol (Upstream Integrity)
`plant_state.md` is the absolute source of truth. If missing an upstream variable:
1. **Research & Plan:** Autonomously locate and read the required upstream `[Filename.py]`.
2. **Execute Update:** Autonomously write the required physical calculation into the upstream model.
3. **Update State:** Autonomously rewrite `plant_state.md` with the new variable.
4. **Resume:** Immediately proceed with the current unit construction. Do not await user confirmation.