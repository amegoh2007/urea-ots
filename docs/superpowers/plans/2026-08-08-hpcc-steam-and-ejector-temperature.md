# HPCC Steam Export and Ejector Temperature Implementation Plan

> **Execution note:** Follow the test-driven-development and verification-before-completion skills. The user preauthorized execution and commit without an approval pause.

**Goal:** Make FT-329407 rise with plant load and a lower LP-steam master setpoint, and expose HV-322602's existing effect on TT-322002.

**Architecture:** Preserve the HPCC's pinned design NTU by scaling effective conductance with live process-gas flow. Keep the existing reaction, shell boiling, steam-header, master-controller, and turbine-export calculations. Replace the legacy TT-322002 constant with its existing live WebSocket field.

**Stack:** Python simulation and pytest; JavaScript legacy HMI; Markdown model documentation.

---

## Task 1: Lock the HPCC steam/export response with a failing test

**Files:**
- Create: `backend/test_hpcc_steam_export_response.py`
- Test: `backend/test_hpcc_steam_export_response.py`

1. Import `main`, reset to a fresh `State`, and settle the design point.
2. Record `HPCC_322E002.steam.kgh` and `STEAM_SYSTEM.FT_329407_th`.
3. Raise raw CO2 load by 20%, settle the load transient, and assert both values exceed their design baselines.
4. Fork the settled load state into matched trajectories, lower the active LP master setpoint by 0.5 bara in one, and assert the lower-pressure trajectory raises more steam while FT-329407 remains above design.
5. Run `python -m pytest backend/test_hpcc_steam_export_response.py -q`; confirm the load assertions fail before production edits.

## Task 2: Preserve HPCC NTU away from design

**Files:**
- Modify: `backend/main.py` in `hpcc_322e002`
- Test: `backend/test_hpcc_steam_export_response.py`

1. Calculate the flow-scaled conductance after guarding both flows from zero, then blend it from pinned `HPCC_UA` through the existing disturbance gate.
2. Use `ua_effective` in the existing exponential gas-temperature calculation.
3. Explain in the nearby comment why constant design `UA` caused NTU and absorbed CO2 to collapse at higher load.
4. Run the focused test and confirm all load and master-setpoint assertions pass.
5. Run `python -m pytest backend/test_equation_audit_322e002.py -q` to verify design pins, equilibrium signs, and disturbance stability.

## Task 3: Lock and repair the TT-322002 HMI binding

**Files:**
- Modify: `backend/test_ui_hand_valve_bindings.py`
- Modify: `frontend/app.js`

1. Add a source regression requiring `setPI('TI_322002', e.TI_322002, ...)` and rejecting the fixed 178.8°C value.
2. Run `python -m pytest backend/test_ui_hand_valve_bindings.py -q`; confirm the new test fails.
3. Replace the constant in `frontend/app.js` with `e.TI_322002`.
4. Rerun the test and `node --check frontend/app.js`; confirm both pass.
5. Run the ejector directional tests to verify HV-322602 still changes the backend temperature in the correct direction.

## Task 4: Repair related LP-header regression expectations

**Files:**
- Modify: `backend/test_g8_lp_turbine_export.py`

1. Replace the obsolete hardcoded 4.4-bara design assertion with `steam_system.P_LP_BARA`.
2. Inject overpressure relative to `P_LP_BARA` and assert recovery to `P_LP_SP_BARA`.
3. Update comments to distinguish the 4-barg header from absolute simulation pressure.
4. Run `python -m pytest backend/test_g8_lp_turbine_export.py -q`; confirm all tests pass.

## Task 5: Update model handoff and verify

**Files:**
- Modify: `handoff.md` only if open modeling gaps remain

1. Run focused tests:
   - `python -m pytest backend/test_hpcc_steam_export_response.py backend/test_equation_audit_322e002.py backend/test_g8_lp_turbine_export.py backend/test_ui_hand_valve_bindings.py -q`
   - `python backend/test_ejector_spindle.py`
2. Run syntax and repository checks:
   - `python -m py_compile backend/main.py`
   - `node --check frontend/app.js`
   - `git diff --check`
3. Record only unresolved modeling gaps in `handoff.md`; do not list completed work.
4. Inspect `git status`, exclude the pre-existing `backend/.boot_pin_cache.json` change, and review the complete staged diff.
5. Commit the implementation as an atomic bug fix with a concise conventional message.
