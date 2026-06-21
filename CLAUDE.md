# Urea Plant OTS - Master Architecture & Directives

**Project:** High-fidelity Stamicarbon CO2-stripping Urea Operator Training Simulator (OTS).
**Stack:** Python (FastAPI/WebSockets) backend, HTML/CSS/JS frontend.

## 1. Core Physics & Dynamic Modeling Laws (STRICT)
* **The Domino Effect (Transient Propagation):** The simulation MUST run as a fully dynamic, coupled state-space system. Any local process perturbation (valve movement, pump trip, composition shift) must recursively calculate and propagate downstream (D/S) in real time, cascading updates to physical properties and multi-component compositions.
* **100% Conservation Accuracy:** Every module must strictly resolve simultaneous differential equations for mass, component, and energy balances. Mass or energy must NEVER be created, destroyed, or decoupled to bypass mathematical stiffness.
* **Rigorous Reaction Kinetics:** Forward and reverse reaction rates for carbamate synthesis and urea conversion must be derived using native temperature, pressure, and exact local activities/compositions. No linear or static shortcuts.
* **The Sourcing Law:** Base all thermodynamic equations, kinetic models, and fluid dynamics on verified sources (UreaKnowHow, Stamicarbon/Uhde patents, peer-reviewed literature). Do not fabricate physical constants.
* **The Design Anchor:** All off-design dynamic equations must resolve to be bit-exact with the provided 100% steady-state Heat and Material Balance (HMB).

## 2. Development Workflow & Active Skill Utilization
* **Tool & Skill Mandate:** You MUST actively use your available skills (Bash execution, file reading, `grep`, and MCP tools) to perform tasks. Never guess file paths, function names, or existing state variables. Prove your assumptions by searching the codebase before writing new logic.
* **Scope Lock:** Build strictly ONE unit at a time. Do not anticipate or stub downstream units.
* **UI Enforcement:** Upon receiving a DCS screenshot, you MUST automatically apply the rules defined in `ui_guidelines.md`.

## 3. Documentation & Version Control (STRICT)
* **Continuous Documentation:** You MUST always check and update the master architecture reference document in the root directory (`Urea OTS — As-Built Mathematical & System Architecture Reference`) to perfectly reflect any changes you make to modeling equations, instrument tags, or system architecture.
* **Remote Backup:** After achieving a stable milestone or verified fix, you MUST backup the software by pushing the commits to the remote repository: `https://github.com/amegoh2007/urea-ots.git`.

## 4. The "Checkout" Protocol (Upstream Integrity)
`plant_state.md` is the absolute source of truth for upstream variables. If you require an upstream output/property NOT listed in `plant_state.md`:
1. **HALT:** Do not hallucinate variables or create dummy inputs.
2. **REQUEST:** State: *"To proceed, I need to modify the upstream model. Please upload [Filename.py]."*
3. **DIFF-ONLY:** Once provided, output ONLY the specific class methods or code lines to replace/add. Do not rewrite the entire script.
4. **UPDATE:** Output the exact line the user must add to `plant_state.md`.
5. **RESUME:** Await user confirmation of the state update before proceeding with the current unit.