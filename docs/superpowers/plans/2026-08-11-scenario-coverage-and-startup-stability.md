# Scenario Coverage and Startup Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Repository instructions prohibit subagents.

**Goal:** Model every documented scenario through shared physical laws and hold a fresh PFD design state without false upsets for ten simulated minutes.

**Architecture:** Retain zoned thermodynamic packages and existing sequential-modular balances. Add a machine-readable scenario manifest, test each physical consequence family, correct design residuals in vacuum and HPCC balances, then prove sustained startup stability with the full engine.

**Tech Stack:** Python 3, pytest, FastAPI simulation engine, Extended UNIQUAC, IAPWS-IF97, existing reduced-order unit models

## Global Constraints

- Use `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md` as strict design source.
- Use equipment data from `References/Datasheets` before introducing equipment constants.
- Do not invent PSV setpoints, pump curves, vessel elevations, or electrolyte parameters.
- Preserve unrelated `scratch/` files.
- Update `docs/Urea OTS — As-Built Mathematical Reference.md` and `handoff.md`.
- Commit once after complete verification, per user instruction.

---

### Task 1: Scenario coverage manifest and thermodynamic routing

**Files:**
- Create: `backend/scenario_coverage.py`
- Create: `backend/test_scenario_coverage.py`

**Interfaces:**
- Produces: `ScenarioRequirement` dataclass and `SCENARIO_REQUIREMENTS: tuple[ScenarioRequirement, ...]`
- Produces: `thermo_package_for(section: str) -> str`
- Consumes: scenario subsection IDs from all three Markdown files

- [x] **Step 1: Write failing manifest tests**

Create tests that parse `References/scenarios/*.md`, collect every numeric subsection below unit
headings, and require each subsection ID in `SCENARIO_REQUIREMENTS`. Require every requirement to
name a driver, local observable, downstream observable, and test function. Require thermodynamic
routing:

```python
assert thermo_package_for("HP_SYNTHESIS") == "VOSKOV_VORONIN_HP_UNIQUAC_VIRIAL"
assert thermo_package_for("LP_NH3_CO2_H2O") == "DARDE_EXTENDED_UNIQUAC_SRK"
assert thermo_package_for("UREA_WATER_VACUUM") == "NEUTRAL_UNIQUAC_IAPWS_IF97"
assert thermo_package_for("STEAM_WATER") == "IAPWS_IF97"
```

- [x] **Step 2: Run tests and confirm failure**

Run: `python -m pytest backend/test_scenario_coverage.py -q`

Expected: import failure because `scenario_coverage.py` does not exist.

- [x] **Step 3: Implement manifest and router**

Use immutable entries:

```python
@dataclass(frozen=True)
class ScenarioRequirement:
    source: str
    section: str
    driver: str
    local_observable: str
    downstream_observable: str
    evidence_test: str
```

List each subsection in all three files. Group entries by shared laws, but do not omit repeated
equipment-specific requirements.

- [x] **Step 4: Run manifest tests**

Run: `python -m pytest backend/test_scenario_coverage.py -q`

Expected: pass.

### Task 2: Startup stability test and vacuum design residuals

**Files:**
- Create: `backend/test_startup_stability.py`
- Modify: `backend/main.py` near Unit 324 constants and Stage-1/Stage-2 pressure balances

**Interfaces:**
- Consumes: `main.State`, `main.step_sim`, design constants, state flags
- Produces: startup fixed-point acceptance test over 600 simulated seconds

- [x] **Step 1: Write failing startup test**

Initialize `main.state = main.State()`, sample design values, run 6000 ticks at 0.1 s, and assert:

```python
assert abs(s.p_syn_bara - main.SYN_P_DES_BARA) <= 0.15
assert abs(s.r324_f001_P / main.R324_F001_P_BARA - 1.0) <= 0.03
assert abs(s.r324_f003_P / main.R324_F003_P_BARA - 1.0) <= 0.03
assert abs(s.r324_e001_T - main.R324_E001_T_SP_C) <= 1.0
assert abs(s.r324_e003_T - main.R324_E003_T_SP_C) <= 1.0
assert not startup_upset_flags(s.flags)
```

Also check tracked numeric state fields for finite values and nonnegative inventories.

- [x] **Step 2: Run test and confirm physical failure**

Run: `python -m pytest backend/test_startup_stability.py -q`

Expected baseline: Stage-1 vacuum rises well above 0.33 bar(a), Stage-2 vacuum rises above 0.131
bar(a), and false vacuum/hydrolysis flags appear.

- [x] **Step 3: Anchor noncondensable departures**

Define design volatile loads from existing design flows and compositions:

```python
R324_NC_FLASH1_DES = R324_FEED_DES * (W_S317["NH3"] + W_S317["CO2"])
R324_NC_FLASH2_DES = R324_P1_DES * (W_S401["NH3"] + W_S401["CO2"])
```

In both vacuum balances, replace absolute live additions with design departures:

```python
d_nc_flash1 = nc_flash1 - R324_NC_FLASH1_DES
d_nc_flash2 = nc_flash2 - R324_NC_FLASH2_DES
```

Use departures in condenser inlet load and noncondensable vent calculations. PFD ejector pull already
contains design noncondensables; absolute additions double-count them.

- [x] **Step 4: Run startup test to reveal remaining residuals**

Run: `python -m pytest backend/test_startup_stability.py -q`

Expected: vacuum drift removed; HPCC level still fails until Task 3.

### Task 3: Pin HPCC inventory at runtime design state

**Files:**
- Modify: `backend/main.py` in `_pin_hpcc_ua`, pin-cache functions, and comments
- Modify: `backend/.boot_pin_cache.json` through normal cache rebuild
- Test: `backend/test_startup_stability.py`

**Interfaces:**
- Produces: `HPCC_LIQ_DES_LIVE` equal to runtime design-seed `hpcc["liq_kgh"]`
- Consumes: final pinned steam and reactor constants

- [x] **Step 1: Add focused failing assertion**

After one design tick, assert:

```python
hpcc = packet["sm_diagnostics"]["hpcc"]
assert hpcc["liq_kgh"] == pytest.approx(main.HPCC_LIQ_DES_LIVE, rel=1e-6)
```

Expected baseline: roughly 185,628 kg/h live versus 214,563 kg/h pinned.

- [x] **Step 2: Move HPCC liquid pin to runtime capture**

During the runtime design-seed capture after reactor and steam constants exist, assign:

```python
HPCC_LIQ_DES_LIVE = res["sm_diagnostics"]["hpcc"]["liq_kgh"]
```

Do not retain the earlier CAS-warm-up liquid value as the runtime inventory anchor. Preserve the
CAS warm-up only where needed for HPCC UA calculation.

- [x] **Step 3: Rebuild deterministic cache**

Remove no files manually. Import `main` after the source hash changes; allow `_pin_hpcc_ua()` to
recompute and write `.boot_pin_cache.json`.

- [x] **Step 4: Run focused and sustained startup tests**

Run:

```powershell
python -m pytest backend/test_startup_stability.py -q
```

Expected: one-tick pin and ten-minute stability pass.

### Task 4: Shared-law and dynamic scenario acceptance

**Files:**
- Modify: `backend/test_scenario_coverage.py`
- Modify: `backend/test_scenario_consequences.py`
- Modify: `backend/main.py`, `backend/consequence.py`, `backend/hp_recycle.py`, or thermodynamic modules only when a failing scenario proves a missing physical path

**Interfaces:**
- Consumes: manifest `evidence_test` names and live operator controls
- Produces: assertions for every scenario family and downstream propagation

- [x] **Step 1: Add fast shared-law tests**

Cover monotonic behavior for:

- seal loss, blow-through, entrainment, NPSH, and crystallization;
- HP wash absorption, breakthrough, pressure retention, H/C conversion loss;
- urea-water equilibrium response to temperature and pressure;
- NH3-CO2-H2O bubble point response to composition and pressure;
- Arrhenius biuret/hydrolysis response to temperature and residence time.

- [x] **Step 2: Add representative dynamic tests**

Drive actual controls for each equipment family:

- reactor and stripper levels/valves;
- HP scrubber vent, ejector, wash, and tempered water;
- LPCC and rectifier solvent, pressure, cooling, level, pump, and steam;
- atmospheric flash and two vacuum evaporator stages;
- desorber, hydrolyzer, reflux condenser, and storage tanks.

Each test must assert one local response and one downstream response after a finite transport lag.

- [x] **Step 3: Run tests and record failures**

Run:

```powershell
python -m pytest backend/test_scenario_coverage.py -q
python backend/test_scenario_consequences.py
```

Expected: failures identify missing paths, not mere missing flags.

- [x] **Step 4: Implement minimal physical corrections**

For each failure, edit the shared governing law or unit balance. Keep all new terms zero at design
through design ratios or departures. Reject direct assignments such as `pressure = alarm_value`.

- [x] **Step 5: Re-run focused tests**

Expected: all manifest, law, dynamic, and startup tests pass.

### Task 5: Documentation, regression, and final commit

**Files:**
- Modify: `docs/Urea OTS — As-Built Mathematical Reference.md`
- Modify: `handoff.md`
- Modify: this plan's checkboxes

- [x] **Step 1: Update mathematical reference**

Document thermodynamic routing, vacuum design-departure equations, HPCC runtime pin, startup
acceptance, and scenario manifest.

- [x] **Step 2: Update open gaps**

Delete startup and scenario gaps that are closed. Retain source-data, full HP speciation, missing
equipment geometry, and validation-range gaps that remain.

- [x] **Step 3: Run full verification**

Run:

```powershell
python -m pytest backend/test_scenario_coverage.py backend/test_startup_stability.py backend/test_hp_carbamate_recycle.py -q
python backend/test_scenario_consequences.py
python backend/test_lv322501_pressure_retuning.py
python -m py_compile backend/main.py backend/scenario_coverage.py backend/consequence.py backend/hp_recycle.py backend/thermo_urea_hp.py backend/thermo_extended_uniquac.py backend/vle_nh3co2h2o.py
```

- [x] **Step 4: Inspect repository scope**

Run `git diff --check`, `git diff --stat`, `git status --short`, and `git diff --cached --name-only`.
Keep `scratch/` unstaged.

- [x] **Step 5: Commit verified work**

Stage only in-scope source, tests, cache, specs, plan, mathematical reference, and handoff. Commit:

```text
✨ fix: stabilize startup and verify process scenarios
```

## Self-review

- Spec coverage: each design section maps to a task and assertion family.
- Placeholder scan: no deferred implementation markers.
- Interface check: scenario manifest names, startup state fields, pin constants, and test commands match repository symbols.
