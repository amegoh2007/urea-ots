# LV-322501 Pressure-Impact Retuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retune the `LV-322501` disturbance so `PT-323201` follows the measured startup sensitivity and `PIC-323203` sees the PFD-supported incremental gas load.

**Architecture:** Extend the dependency-free pressure-coupling helper with a field residual and an E011 condenser-capacity closure. Wire the E011 helper into the active monolith and its sequential-modular duplicate while preserving all controller tuning and external state.

**Tech Stack:** Python 3.14, pytest, FastAPI simulation backend, standard-library `math`.

## Global Constraints

- Keep `LV322501_OPEN_DES = 46.1`.
- Keep `PIC-323203` at `Kc = 0.60`, `Ti = 100 s`, and `Td = -1.0 s`.
- Keep `R323_C003_P_TAU_S = 1.0 s`.
- Preserve exact design targets: `PT-323201 = 4.1 bara`, E011 gas feed `6,029 kg/h`, condensation `5,589 kg/h`, and vent `440 kg/h`.
- Preserve all public state, telemetry keys, API routes, and saved-state fields.
- Add no dependency.
- Do not restore, stage, or commit the user's deleted test files or untracked `project.md`.
- Stage and commit only the files listed in this plan.

---

## File structure

- Modify `backend/c003_pressure_coupling.py`: field-calibrated C003 target and pure E011 vent-generation function.
- Modify `backend/main.py`: active E011 runtime call.
- Modify `backend/core/lp.py`: sequential-modular parity call.
- Create `backend/test_lv322501_pressure_retuning.py`: pure and integrated regression gates.
- Add the design and plan documents under `docs/superpowers`.

## Test strategy

```yaml
test_strategy:
  artifact: "LV-322501 pressure-impact retuning"
  rationale: "Numeric process closures affect operator-training behavior across the C003, F004, and E011 dynamic stages."
  criticality: "MEDIUM-HIGH"

  selected_types:
    - rationale: "The two dependency-free helpers contain validation, nonlinear math, a floor, and a capacity boundary."
      type: "unit"
      size: "small"
      framework: "pytest"
      dependencies: []
      gate: "Gate 1"
    - rationale: "The requested behavior crosses valve hydraulics, process inventories, pressure ODEs, and a live PID; doubles would distort the response."
      type: "integration"
      size: "medium"
      framework: "pytest"
      dependencies: ["in-process backend/main.py simulation"]
      gate: "Gate 2"

  rejected_types:
    - reason: "This change has no UI surface; Gate 3 is OFF."
      type: "component"
    - reason: "A focused in-process simulation covers the behavior without a browser or deployed service; Gate 3 is OFF."
      type: "e2e"
    - reason: "Backend and browser ship together, so there is no independent consumer cadence; Gate 4 is OFF."
      type: "contract"
    - reason: "No post-deploy pipeline is in scope; Gate 5 is OFF."
      type: "smoke"

  deliberately_skipped:
    - why: "The numeric domain is broad, but exact design, boundary, invalid-input, and monotonic cases cover the stable invariants without adding Hypothesis."
      what: "Property-based fuzzing of all finite flow ratios and gas feeds"
```

### Test cases to cover

- [unit] exact design ratios return `PT-323201 = 4.1 bara`.
- [unit] central-difference sensitivity at design equals `0.122932 bar per opening point`.
- [unit] a full closure cannot set upstream target pressure below downstream pressure.
- [unit] E011 gas feed at 5,589, 6,029, and 7,029 kg/h yields 0, 440, and 1,440 kg/h vent generation [BVA around condenser capacity plus design and overload partitions].
- [unit] NaN, infinity, and negative E011 gas feed raise `ValueError` [invalid partition].
- [integration] a 60% LV case separates `PT-323201` from a 30% case by more than 2.5 bar after 60 seconds.
- [integration] the same cases separate `PIC-323203` output by more than 2.0 opening points after 60 seconds.

### Task 1: Pure pressure and condenser closures

**Files:**
- Modify: `backend/c003_pressure_coupling.py`
- Create: `backend/test_lv322501_pressure_retuning.py`

**Interfaces:**
- Consumes: `c003_pressure_target_bara(lv_flow_ratio: float, overhead_flow_ratio: float, downstream_pressure_bara: float) -> float`.
- Produces: `e011_vent_generation_kgh(gas_inlet_kgh: float) -> float`.

- [ ] **Step 1: Write failing pure tests**

Create the test module with these imports and pure cases:

```python
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from c003_pressure_coupling import (  # noqa: E402
    c003_pressure_target_bara,
    e011_vent_generation_kgh,
)


def test_c003_design_point_closes_exactly():
    assert c003_pressure_target_bara(1.0, 1.0, 3.2) == pytest.approx(4.1, abs=1.0e-12)


def test_c003_local_lv_sensitivity_matches_startup_band():
    opening_step = 1.0e-3
    ratio_step = opening_step / 46.1
    p_hi = c003_pressure_target_bara(1.0 + ratio_step, 1.0, 3.2)
    p_lo = c003_pressure_target_bara(1.0 - ratio_step, 1.0, 3.2)
    slope = (p_hi - p_lo) / (2.0 * opening_step)
    assert slope == pytest.approx(0.122931746, rel=1.0e-5)
    assert 0.10 <= slope <= 0.13


def test_e011_design_gas_closes_pfd_balance():
    assert e011_vent_generation_kgh(6029.0) == pytest.approx(440.0)


def test_e011_incremental_gas_exceeds_fixed_condensation_capacity():
    assert e011_vent_generation_kgh(7029.0) == pytest.approx(1440.0)
    assert e011_vent_generation_kgh(5029.0) == 0.0


def test_c003_target_never_falls_below_downstream_pressure():
    assert c003_pressure_target_bara(0.0, 1.0, 3.2) == pytest.approx(3.2)


@pytest.mark.parametrize("gas_inlet", [math.nan, math.inf, -0.01])
def test_e011_rejects_invalid_gas_inlet(gas_inlet):
    with pytest.raises(ValueError):
        e011_vent_generation_kgh(gas_inlet)
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run:

```powershell
python -B -m pytest -q -p no:cacheprovider backend/test_lv322501_pressure_retuning.py
```

Expected: collection fails because `e011_vent_generation_kgh` does not exist, or the slope assertion fails at the current `0.022932 bar per point` response.

- [ ] **Step 3: Implement the field residual and E011 helper**

Add these source constants to `backend/c003_pressure_coupling.py`:

```python
C003_LV_FIELD_GAIN_BARA_PER_RATIO = 4.61
E011_GAS_FEED_DES_KGH = 6029.0
E011_CONDENSATION_CAPACITY_DES_KGH = 5589.0
```

Update the C003 return path:

```python
hydraulic_target_bara = math.sqrt(
    downstream_pressure_bara ** 2
    + (equivalent_gas_load_m3h / C003_GAS_LOAD_COEFF_M3H_PER_BAR) ** 2
)
field_residual_bara = C003_LV_FIELD_GAIN_BARA_PER_RATIO * (lv_flow_ratio - 1.0)
return max(downstream_pressure_bara, hydraulic_target_bara + field_residual_bara)
```

Add the E011 function:

```python
def e011_vent_generation_kgh(gas_inlet_kgh: float) -> float:
    if not math.isfinite(gas_inlet_kgh):
        raise ValueError("E011 gas inlet must be finite")
    if gas_inlet_kgh < 0.0:
        raise ValueError("E011 gas inlet must be nonnegative")
    return max(gas_inlet_kgh - E011_CONDENSATION_CAPACITY_DES_KGH, 0.0)
```

- [ ] **Step 4: Run pure tests and confirm success**

Run the same focused pytest command. Expected: all pure tests pass.

### Task 2: Runtime wiring and integrated response

**Files:**
- Modify: `backend/main.py:39-55, 6651-6661`
- Modify: `backend/core/lp.py:1-6, 454-463`
- Modify: `backend/test_lv322501_pressure_retuning.py`

**Interfaces:**
- Consumes: `e011_vent_generation_kgh(gas_inlet_kgh: float) -> float` from Task 1.
- Produces: stronger `PT-323201` and `PIC-323203` responses with unchanged packet schema.

- [ ] **Step 1: Add the failing integrated response test**

Add a named result and helper that creates a fresh `main.State`, puts `LIC_322501` in manual, applies an opening, and advances 60 seconds at `dt = 0.25 s`. Compare 60% open with 30% open:

```python
from typing import NamedTuple

import main  # noqa: E402


class LvCase(NamedTuple):
    pt323201_bara: float
    pic323203_pv_bara: float
    pic323203_op: float


def _run_lv_case(opening_pct: float) -> LvCase:
    main.state = main.State()
    state = main.state
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = opening_pct
    for _ in range(round(60.0 / main.STEP_CAP)):
        main.step_sim(main.STEP_CAP)
    return LvCase(
        pt323201_bara=state.r323_c003_P,
        pic323203_pv_bara=state.r3232_e011_P,
        pic323203_op=state.PIC_323203["op"],
    )


def test_lv_opening_materially_separates_pt323201():
    closed = _run_lv_case(30.0)
    opened = _run_lv_case(60.0)
    assert opened.pt323201_bara - closed.pt323201_bara > 2.5


def test_lv_opening_materially_separates_pic323203():
    closed = _run_lv_case(30.0)
    opened = _run_lv_case(60.0)
    assert opened.pic323203_op - closed.pic323203_op > 2.0
```

The current code should fail the PIC output assertion; its measured separation is about `0.025` opening point after 60 seconds.

- [ ] **Step 2: Run the integrated test and confirm failure**

Run:

```powershell
python -B -m pytest -q -p no:cacheprovider backend/test_lv322501_pressure_retuning.py -k materially
```

Expected: failure on the `PIC_323203["op"]` separation.

- [ ] **Step 3: Wire the helper into the active model**

Import both helpers in `backend/main.py`:

```python
from c003_pressure_coupling import (
    c003_pressure_target_bara,
    e011_vent_generation_kgh,
)
```

Replace the proportional generation equation with:

```python
gas_in_e011 = max(in_e011 - m_402, 0.0)
gen_v011 = e011_vent_generation_kgh(gas_in_e011)
```

Leave `PIC_323203`, `m_v011`, and the pressure ODE unchanged.

- [ ] **Step 4: Keep the sequential-modular duplicate consistent**

Import `e011_vent_generation_kgh` at the top of `backend/core/lp.py` and replace its proportional generation equation with the same `gas_in_e011` and helper call.

- [ ] **Step 5: Run focused tests and adjust only evidence-backed thresholds**

Run the full new test file. If the physical closure produces a stable response smaller than the planned acceptance threshold, inspect the measured outputs. Do not change controller tuning or source constants to satisfy the test.

- [ ] **Step 6: Run regression verification**

Run:

```powershell
python -B -m pytest -q -p no:cacheprovider backend/test_lv322501_pressure_retuning.py
python -B -m py_compile backend/c003_pressure_coupling.py backend/main.py backend/core/lp.py backend/test_lv322501_pressure_retuning.py
python -B backend/debug_hv605.py
git diff --check
```

Also run any surviving focused Section 323 tests discoverable without restoring the user's deleted test files.

- [ ] **Step 7: Review and commit the scoped change**

Inspect `git diff` and stage only:

```powershell
git add -- backend/c003_pressure_coupling.py backend/main.py backend/core/lp.py backend/test_lv322501_pressure_retuning.py docs/superpowers/specs/2026-08-09-lv322501-pressure-impact-retuning-design.md docs/superpowers/plans/2026-08-09-lv322501-pressure-impact-retuning.md
git diff --cached --check
git commit -m "fix(323): strengthen LV-322501 pressure response"
```

Expected: one commit containing only the retuning, focused tests, design, and plan.
