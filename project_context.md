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