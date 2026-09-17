# HP Carbamate Recycle Thermodynamics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make 323P001 recycle-flow deviations produce physically correct HP-scrubber, synthesis-loop, reactor-conversion, stripper-duty, and downstream-overload responses.

**Architecture:** Add a focused high-pressure urea-equilibrium module and keep the existing LP/MP electrolyte property package in its validated service. Refactor the live scrubber and vent equations into mass-conserving capacity and valve-flow helpers, then couple retained gas and recycle composition to existing state inventories. Preserve the PFD-anchored design point through departure-form equations.

**Tech Stack:** Python 3, existing sequential-modular dynamic engine, `pytest`, plant PFD/equipment-sheet anchors

## Global Constraints

- `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md` is the design-point authority.
- A running 323P001 pump uses `Q = 0.5046 * rpm * eta_suction` m3/h and a 19-81 rpm operating range.
- Make each new departure term zero at the design seed.
- Preserve non-negative component flows and component mass closure.
- Keep Extended UNIQUAC/SRK out of the 141-bar HP loop.
- Preserve the user's unrelated untracked files under `scratch/`.

---

### Task 1: High-pressure urea equilibrium package

**Files:**
- Create: `backend/thermo_urea_hp.py`
- Modify: `backend/reactor.py`
- Test: `backend/test_hp_carbamate_recycle.py`

**Interfaces:**
- Produces: `synthesis_ratios(comp_kmolh: dict[str, float]) -> tuple[float, float]`
- Produces: `equilibrium_conversion(nc: float, hc: float, t_c: float) -> float`
- Produces: `conversion_factor(nc: float, hc: float, t_c: float) -> float`
- Consumes: component kmol/h and the existing design anchors in `backend/reactor.py`

- [x] **Step 1: Write failing monotonicity and design-anchor tests**

```python
def test_hp_equilibrium_water_penalty_and_anchor():
    assert hp.conversion_factor(hp.NC_DES, hp.HC_DES, hp.T_DES_C) == pytest.approx(1.0)
    assert hp.equilibrium_conversion(3.1, 0.8, 183.0) < hp.equilibrium_conversion(3.1, 0.4, 183.0)

def test_synthesis_ratios_include_products():
    nc, hc = hp.synthesis_ratios({"NH3": 300.0, "CO2": 50.0, "H2O": 80.0, "Urea": 50.0})
    assert nc == pytest.approx(4.0)
    assert hc == pytest.approx(0.3)
```

- [x] **Step 2: Run `python -m pytest backend/test_hp_carbamate_recycle.py -q` and confirm the new module is missing**

- [x] **Step 3: Implement the published correlation**

```python
def equilibrium_conversion(nc, hc, t_c):
    t_k = clamp(t_c + 273.15, 408.15, 503.15)
    nc = clamp(nc, 2.0, 5.5)
    hc = clamp(hc, -0.75, 1.2)
    base = -121.1458 - 5.1135e-5 * t_k**2 + 21.6826 * math.log(t_k)
    exponent = (-2.1908 / nc**2 - 4.1059e-3 * nc**2) * hc - 2.8380 / nc**2
    return clamp(base * math.exp(exponent), 0.0, 1.0)
```

- [x] **Step 4: Replace `reactor.py`'s fabricated Modified Inoue-Kanai curve with calls to the new package; retain `inoue_kanai_X` as a compatibility alias**

- [x] **Step 5: Run the focused tests and confirm they pass**

### Task 2: Positive-displacement pump law

**Files:**
- Modify: `backend/main.py`
- Test: `backend/test_hp_carbamate_recycle.py`

**Interfaces:**
- Produces: `pump_323p001_flow_m3h(rpm: float, suction_factor: float = 1.0) -> float`
- Consumes: existing `SIC_323901` speed demand and `_cq_pump` suction factor

- [x] **Step 1: Write failing tests for speed proportionality and pressure independence**

```python
def test_323p001_is_positive_displacement():
    q40 = main.pump_323p001_flow_m3h(40.0)
    q80 = main.pump_323p001_flow_m3h(80.0)
    assert q80 == pytest.approx(2.0 * q40)
    assert "pressure" not in inspect.signature(main.pump_323p001_flow_m3h).parameters
```

- [x] **Step 2: Run the focused test and confirm it fails because the helper is missing**

- [x] **Step 3: Implement the displacement law with stopped-pump zero flow and 19-81 rpm running limits**

```python
def pump_323p001_flow_m3h(rpm, suction_factor=1.0):
    if rpm <= 0.0:
        return 0.0
    n = clamp(rpm, 19.0, 81.0)
    return 0.5046 * n * clamp(suction_factor, 0.0, 1.0)
```

- [x] **Step 4: Use the helper in the live 323P001 path and keep discharge pressure out of the flow calculation**

- [x] **Step 5: Run the focused tests and confirm they pass**

### Task 3: Mass-conserving HP scrubber and capacity-limited vent

**Files:**
- Modify: `backend/main.py`
- Test: `backend/test_hp_carbamate_recycle.py`

**Interfaces:**
- Extends: `scrub_322e003(...) -> dict` with `breakthrough_kmolh` and `closure_kmolh`
- Changes: `hv_322604(...) -> dict` to return `available_mass_kgh`, `capacity_mass_kgh`, and `retained_kmolh`

- [x] **Step 1: Write failing unit tests for wash gradients and component closure**

```python
def test_scrubber_wash_gradient_and_closure():
    low = scrub(wash_scale=0.6)
    design = scrub(wash_scale=1.0)
    high = scrub(wash_scale=1.4)
    assert gas_nh3_co2(high) < gas_nh3_co2(design) < gas_nh3_co2(low)
    assert liquid_mass(high) > liquid_mass(design) > liquid_mass(low)
    assert high["T_offgas"] < design["T_offgas"] < low["T_offgas"]
    assert max(abs(v) for v in low["closure_kmolh"].values()) < 1e-9
```

- [x] **Step 2: Run the focused tests and confirm the existing fixed-split/gain model fails at least one assertion**

- [x] **Step 3: Derive the design absorbed vector from reactor off-gas plus wash minus design outlets, then scale absorbable capacity with wash and cooling effectiveness**

- [x] **Step 4: Route every input component to either gas or liquid and assert non-negative outputs**

- [x] **Step 5: Convert HV-322604 from an unlimited supply multiplier to `min(available, Cv * opening * sqrt(deltaP))`; return the unvented vector**

- [x] **Step 6: Run the focused tests and confirm wash signs, design pins, and closure pass**

### Task 4: Loop pressure, downstream overload, and energy consequences

**Files:**
- Modify: `backend/main.py`
- Test: `backend/test_hp_carbamate_recycle.py`

**Interfaces:**
- Adds state/telemetry: `SCRUB_BREAKTHROUGH_KGH`, `SCRUB_RETAINED_GAS_KGH`, `LP_ABSORBER_LOAD_RATIO`, `LP_ABSORBER_RELIEF_KGH`
- Adds telemetry: reactor H/C, equilibrium conversion, stripper steam increment, HPCC recycle increment, sustainable production factor

- [x] **Step 1: Write a failing low-wash dynamic scenario**

```python
def test_low_wash_pressurizes_and_overloads_downstream():
    state = settled_state()
    p0 = state.p_syn_bara
    set_323p001_manual_rpm(state, 32.0)
    result = run_seconds(300.0)
    assert state.p_syn_bara > p0
    assert result["SCRUB_322E003"]["retained_gas_th"] > 0.0
    assert result["SCRUB_322E003"]["lp_absorber_load_ratio"] > 1.0
```

- [x] **Step 2: Run the scenario and confirm current pressure moves in the wrong direction**

- [x] **Step 3: Remove wash mass from the HP pressure inlet/outlet departure balance; add only retained scrubber gas to the HP gas inventory**

- [x] **Step 4: Add finite downstream absorber capacity, overload relief/emission indication, and pressure-derived escalation**

- [x] **Step 5: Couple high H/C conversion loss to extra unconverted reactor load, stripper steam, and HPCC recycle; couple severe recycle deficit to N/C, reactor inventory, and sustainable production**

- [x] **Step 6: Add high-wash and severe-low-wash scenarios and run the focused suite**

### Task 5: Documentation, full verification, and commit

**Files:**
- Modify: `docs/Urea OTS — As-Built Mathematical Reference.md`
- Modify: `handoff.md`
- Modify: `docs/superpowers/plans/2026-08-11-hp-carbamate-recycle-thermodynamics.md`

**Interfaces:**
- Documents the formulas, validity ranges, design anchors, telemetry, and remaining gaps

- [x] **Step 1: Document the two thermodynamic service envelopes and all new equations in the as-built reference**

- [x] **Step 2: Update `handoff.md` only with evidence-backed residual gaps**

- [x] **Step 3: Mark each completed checkbox in this plan**

- [x] **Step 4: Run `python -m pytest backend/test_hp_carbamate_recycle.py -q`**

- [x] **Step 5: Run the repository's existing scenario and focused regression scripts**

```powershell
python backend/test_scenario_consequences.py
python backend/test_lv322501_pressure_retuning.py
```

- [x] **Step 6: Inspect `git diff --check`, `git diff --stat`, and `git status --short`; exclude `scratch/` and temporary research files**

- [x] **Step 7: Commit the verified source, tests, specification, plan, and documentation with a conventional commit message**

## Self-review

- Spec coverage: every pump, scrubber, pressure, thermodynamic, energy, mass-balance, and low-recycle consequence has a task and an assertion.
- Placeholder scan: no deferred implementation markers remain.
- Type consistency: Task 4 consumes the scrubber and valve diagnostics defined in Task 3; all public helper names match their tests.
