# Urea Plant Operator Training Simulator (OTS) - Master Architecture

## Project Overview
You are building a custom OTS for a urea synthesis and granulation plant. 
* **Target Directory:** `D:\Work\Urea Simulation`
* **Architecture:** Split-stack. 
  * Backend: Python (FastAPI/WebSockets) for physics, mass balance, and control loop logic.
  * Frontend: HTML/CSS/JS (using standard web technologies) for the DCS mimic interface.
* **Execution Rule:** Build strictly ONE UNIT at a time. Do not anticipate or code downstream units until instructed.

## Workflow
1. I will provide unit definitions, equipment datasheets, P&IDs, and mapping illustrations.
2. I will provide a DCS screenshot for the visual layout.
3. Upon receiving a DCS screenshot, you MUST automatically read and strictly apply the UI generation rules defined in `ui_guidelines.md`.
4. You will build the mathematical backend to match the design parameters, then bind it to the frontend via WebSockets.

## STRICT RULE: Upstream Modification & The "Checkout" Protocol

Because we are keeping our context window lean, you do not have access to previously completed upstream `.py` files. You only have `plant_state.md` as your source of truth for upstream variables. 

If you are building a unit and realize you absolutely need a specific output, variable, or physical property from an upstream unit that is NOT listed in `plant_state.md`, you must follow this protocol:

1. **STOP GENERATING THE CURRENT UNIT.** Do not hallucinate the variable. Do not create a "dummy" input. 
2. **REQUEST A FILE CHECKOUT:** State clearly: "To proceed, I need to modify the upstream model. Please upload `[Name of the specific Python file]` so I can add the missing calculation."
3. **DIFF-ONLY UPDATES:** Once I upload the requested file, do not rewrite the entire script. Provide ONLY the specific class method, equation, or lines of code that need to be added or replaced. 
4. **UPDATE THE STATE:** Instruct me on exactly what new variable line to add to `plant_state.md`. 
5. **RESUME:** Only after the upstream file and state are updated will we resume building the current unit.