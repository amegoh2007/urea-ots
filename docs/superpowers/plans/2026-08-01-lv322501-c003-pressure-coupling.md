# LV-322501 to 323C003 Pressure Coupling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and verify a source-calibrated, directionally correct pressure response from LV-322501 liquid flow to 323C003 while preserving the field-calibrated 46.1% normal opening and existing live-overhead pressure response.

**Architecture:** Add one dependency-free pure Python module that converts normalized LV prompt-flash load, normalized remaining overhead load, and beginning-of-substep 323E003/323D001 pressure into a 323C003 target pressure. Wire that helper into the existing Unit 323 update after `drain_kgh` and `m_305` are known, retaining the current explicit update order, 90 s pressure lag, state bounds, public state, and telemetry.

**Tech Stack:** Python 3.14, standard-library `math`, pytest, existing FastAPI simulation backend.

## Global Constraints

- Keep `LV322501_OPEN_DES = 46.1`; do not replace it with the vendor-derived approximately 81.8% travel.
- Normalize live LV flow exactly as `drain_kgh / STRIP_BOT_DES_KGH`, where `STRIP_BOT_DES_KGH = 130482.0` kg/h.
- Treat 5,064.7 m3/h (stream 301) and 7,677.1 m3/h (stream 305) as design-condition-equivalent gas-load anchors at 119 C and 4.1 bara; do not directly add stream 302's 135 C actual-volume rate.
- Use `Q_eq = 5064.7 * r_lv + (7677.1 - 5064.7) * r_305`.
- Use the calibrated near-design surrogate `P_target = sqrt(P_E003_begin^2 + (Q_eq / K_eq)^2)`, with `K_eq = 7677.1 / sqrt(4.1^2 - 3.2^2)`.
- Preserve the current non-LV pressure driver through `r_305 = m_305 / R323_M305_DES`.
- Consume `s.r3232_d001_P` before its later update in the same substep; do not introduce an algebraic loop or a duplicate E003 pressure state.
- Retain `R323_C003_P_TAU_S = 90.0` and the existing 1.0-to-12.0 bara runtime clamp.
- Do not change the external state shape, API routes, controller tags, or telemetry keys.
- The helper must raise `ValueError` for non-finite inputs, negative flow ratios, or nonpositive downstream absolute pressure.
- Do not add a new dependency or wire the separate representative `gap_g9b_valve_hydraulics.py` model into this change.
- Run Python with `-B` and pytest with `-p no:cacheprovider` because the two existing `.pytest_cache` directories are inaccessible.

---

## File Structure

- Create `backend/c003_pressure_coupling.py`: source constants, validation, equivalent gas-load calculation, and pure target-pressure function.
- Create `backend/test_c003_pressure_coupling.py`: pure equation tests and focused public-`step_sim` integration tests.
- Modify `backend/main.py`: import the helper, replace the empirical pressure gain, preserve the explicit E003 pressure tear, and correct the stale state comment.
- Modify `backend/tests/run_valve_indicator_matrix.py`: replace its obsolete 82% LV baseline with the field-calibrated constant and a range that brackets it.
- Modify `backend/tests/run_full_audit.py`: replace its obsolete 82% label and sweep point with `main.LV322501_OPEN_DES`.

### Task 1: Pure C003 Gas-Load Pressure Target

**Files:**
- Create: `backend/c003_pressure_coupling.py`
- Create: `backend/test_c003_pressure_coupling.py`

**Interfaces:**
- Consumes: three floats: `lv_flow_ratio`, `overhead_flow_ratio`, and `downstream_pressure_bara`.
- Produces: `c003_pressure_target_bara(lv_flow_ratio: float, overhead_flow_ratio: float, downstream_pressure_bara: float) -> float`.

- [ ] **Step 1: Write the failing pure-equation tests**

Create `backend/test_c003_pressure_coupling.py` with:

```python
"""Source-calibrated LV-322501 to 323C003 pressure-coupling tests."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from c003_pressure_coupling import c003_pressure_target_bara  # noqa: E402


def test_design_point_closes_exactly():
    assert c003_pressure_target_bara(1.0, 1.0, 3.2) == pytest.approx(4.1, abs=1e-12)


def test_each_gas_load_driver_is_monotonic():
    design = c003_pressure_target_bara(1.0, 1.0, 3.2)
    assert c003_pressure_target_bara(1.1, 1.0, 3.2) > design
    assert c003_pressure_target_bara(1.0, 1.1, 3.2) > design
    assert c003_pressure_target_bara(0.9, 1.0, 3.2) < design
    assert c003_pressure_target_bara(1.0, 0.9, 3.2) < design


def test_vendor_maximum_flow_equivalent_is_4_20838_bara():
    vendor_flow_ratio = 126.10 / 114.58
    assert 46.1 * vendor_flow_ratio == pytest.approx(50.734945, abs=1e-6)
    assert c003_pressure_target_bara(vendor_flow_ratio, 1.0, 3.2) \
        == pytest.approx(4.208379859, abs=1e-9)


def test_local_lv_gain_is_0_0229317_bar_per_opening_point():
    opening_step = 1.0e-3
    ratio_step = opening_step / 46.1
    p_high = c003_pressure_target_bara(1.0 + ratio_step, 1.0, 3.2)
    p_low = c003_pressure_target_bara(1.0 - ratio_step, 1.0, 3.2)
    slope = (p_high - p_low) / (2.0 * opening_step)
    assert slope == pytest.approx(0.022931746, rel=1e-6)


def test_zero_total_gas_load_equals_downstream_pressure():
    assert c003_pressure_target_bara(0.0, 0.0, 3.2) == pytest.approx(3.2, abs=1e-12)


def test_downstream_backpressure_is_monotonic():
    assert c003_pressure_target_bara(1.0, 1.0, 3.0) \
        < c003_pressure_target_bara(1.0, 1.0, 3.2) \
        < c003_pressure_target_bara(1.0, 1.0, 3.5)


@pytest.mark.parametrize("args", [
    (math.nan, 1.0, 3.2),
    (1.0, math.inf, 3.2),
    (1.0, 1.0, math.nan),
    (-0.01, 1.0, 3.2),
    (1.0, -0.01, 3.2),
    (1.0, 1.0, 0.0),
    (1.0, 1.0, -1.0),
])
def test_invalid_inputs_raise_value_error(args):
    with pytest.raises(ValueError):
        c003_pressure_target_bara(*args)
```

- [ ] **Step 2: Run the pure tests and confirm the red state**

Run from `backend`:

```powershell
& 'C:\Users\ameel\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B -m pytest -q -p no:cacheprovider test_c003_pressure_coupling.py
```

Expected: collection fails with `ModuleNotFoundError: No module named 'c003_pressure_coupling'`.

- [ ] **Step 3: Implement the minimal pure pressure helper**

Create `backend/c003_pressure_coupling.py` with:

```python
"""Near-design LV-322501 gas-load coupling to 323C003 absolute pressure."""
from __future__ import annotations

import math


C003_Q301_DES_M3H = 5064.7
C003_Q305_DES_M3H = 7677.1
C003_QOTHER_DES_M3H = C003_Q305_DES_M3H - C003_Q301_DES_M3H
C003_P_DES_BARA = 4.1
E003_P_DES_BARA = 3.2
C003_GAS_LOAD_COEFF_M3H_PER_BAR = (
    C003_Q305_DES_M3H
    / math.sqrt(C003_P_DES_BARA ** 2 - E003_P_DES_BARA ** 2)
)


def c003_pressure_target_bara(
    lv_flow_ratio: float,
    overhead_flow_ratio: float,
    downstream_pressure_bara: float,
) -> float:
    """Return the reduced-order 323C003 target pressure in bar absolute.

    `lv_flow_ratio` drives PFD stream 301's prompt flash-gas contribution.
    `overhead_flow_ratio` preserves the remaining live stream-305/reboiler load.
    All volume anchors are equivalent loads at the stream-305 design state.
    """
    values = (lv_flow_ratio, overhead_flow_ratio, downstream_pressure_bara)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("pressure-coupling inputs must be finite")
    if lv_flow_ratio < 0.0 or overhead_flow_ratio < 0.0:
        raise ValueError("gas-load flow ratios must be nonnegative")
    if downstream_pressure_bara <= 0.0:
        raise ValueError("downstream absolute pressure must be positive")

    equivalent_gas_load_m3h = (
        C003_Q301_DES_M3H * lv_flow_ratio
        + C003_QOTHER_DES_M3H * overhead_flow_ratio
    )
    return math.sqrt(
        downstream_pressure_bara ** 2
        + (equivalent_gas_load_m3h / C003_GAS_LOAD_COEFF_M3H_PER_BAR) ** 2
    )
```

- [ ] **Step 4: Run the pure tests and confirm the green state**

Run:

```powershell
& 'C:\Users\ameel\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B -m pytest -q -p no:cacheprovider test_c003_pressure_coupling.py
```

Expected: all equation and validation cases pass.

- [ ] **Step 5: Check the task diff and commit the pure model**

Run from the repository root:

```powershell
git diff --check
git add backend/c003_pressure_coupling.py backend/test_c003_pressure_coupling.py
git diff --cached --check
git commit -m "✨ feat: add C003 gas-load pressure target"
```

Expected: one atomic commit containing only the pure model and its tests.

### Task 2: Runtime Coupling and Transient Regression Gates

**Files:**
- Modify: `backend/test_c003_pressure_coupling.py`
- Modify: `backend/main.py:39-52, 854-861, 4375-4379, 5716-5719`
- Modify: `backend/tests/run_valve_indicator_matrix.py:81-90`
- Modify: `backend/tests/run_full_audit.py:220-230`

**Interfaces:**
- Consumes: `c003_pressure_target_bara()` from Task 1, existing `drain_kgh`, `m_305`, `STRIP_BOT_DES_KGH`, `R323_M305_DES`, and beginning-of-substep `s.r3232_d001_P`.
- Produces: the existing `s.r323_c003_P` state and `RECIRC_323.C003.P_bara` telemetry with corrected causal behavior; no new public field.

- [ ] **Step 1: Add failing runtime integration tests**

Append the following import and tests to `backend/test_c003_pressure_coupling.py`:

```python
import main  # noqa: E402


def _one_step_from_fresh(lv_open_pct=46.1, downstream_pressure_bara=3.2):
    main.state = main.State()
    state = main.state
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = lv_open_pct
    state.r3232_d001_P = downstream_pressure_bara
    pressure_before = state.r323_c003_P
    packet = main.step_sim(0.1)
    return pressure_before, state.r323_c003_P, packet


def test_runtime_normalizes_design_lv_flow_to_one(monkeypatch):
    captured = []
    real_target = main.c003_pressure_target_bara

    def capture(lv_flow_ratio, overhead_flow_ratio, downstream_pressure_bara):
        captured.append((lv_flow_ratio, overhead_flow_ratio, downstream_pressure_bara))
        return real_target(lv_flow_ratio, overhead_flow_ratio, downstream_pressure_bara)

    monkeypatch.setattr(main, "c003_pressure_target_bara", capture)
    main.state = main.State()
    main.step_sim(0.1)
    assert captured
    assert captured[0][0] == pytest.approx(1.0, abs=1e-12)


def test_opening_and_closing_lv_give_prompt_signed_pressure_response():
    p0_open, p_open, _ = _one_step_from_fresh(lv_open_pct=60.0)
    p0_close, p_close, _ = _one_step_from_fresh(lv_open_pct=30.0)
    assert p_open > p0_open
    assert p_close < p0_close


def test_runtime_consumes_beginning_of_substep_e003_backpressure():
    _, p_low, _ = _one_step_from_fresh(downstream_pressure_bara=3.0)
    _, p_design, _ = _one_step_from_fresh(downstream_pressure_bara=3.2)
    _, p_high, _ = _one_step_from_fresh(downstream_pressure_bara=3.5)
    assert p_low < p_design < p_high


def test_zero_reboiler_overhead_still_uses_prompt_flash_load():
    main.state = main.State()
    state = main.state
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = main.LV322501_OPEN_DES
    state.PIC_329202["mode"] = "MAN"
    state.PIC_329202["op"] = 0.0
    state.TIC_323007["mode"] = "MAN"
    pressure_before = state.r323_c003_P

    packet = main.step_sim(0.1)

    assert packet["RECIRC_323"]["C003"]["v305_th"] == 0.0
    target = c003_pressure_target_bara(1.0, 0.0, 3.2)
    expected = pressure_before + (target - pressure_before) / main.R323_C003_P_TAU_S * 0.1
    assert state.r323_c003_P == pytest.approx(expected, abs=1e-10)


def _advance_opening(dt, seconds=2.0):
    main.state = main.State()
    state = main.state
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = 60.0
    for _ in range(round(seconds / dt)):
        main.step_sim(dt)
    return state.r323_c003_P


def test_opening_response_is_consistent_across_supported_steps():
    fine = _advance_opening(0.1)
    coarse = _advance_opening(main.STEP_CAP)
    assert coarse == pytest.approx(fine, abs=2.0e-4)
```

- [ ] **Step 2: Run the runtime tests and confirm the red state**

Run from `backend`:

```powershell
& 'C:\Users\ameel\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B -m pytest -q -p no:cacheprovider test_c003_pressure_coupling.py::test_runtime_normalizes_design_lv_flow_to_one test_c003_pressure_coupling.py::test_opening_and_closing_lv_give_prompt_signed_pressure_response test_c003_pressure_coupling.py::test_runtime_consumes_beginning_of_substep_e003_backpressure
```

Expected: failure because `main.c003_pressure_target_bara` is not wired; the old model also moves pressure downward after a 60% opening and ignores E003 backpressure.

- [ ] **Step 3: Import the helper and replace the empirical target**

Add this import beside the other backend-local imports in `backend/main.py`:

```python
from c003_pressure_coupling import c003_pressure_target_bara
```

Replace the empirical pressure-gain constant and comment with:

```python
# Dynamic PT-323201 pressure response. The pure target helper separates prompt flash gas from
# LV-322501 (`drain_kgh`) from the remaining live overhead/reboiler load (`m_305`), consumes the
# beginning-of-substep 323E003/323D001 pressure, and closes exactly at the PFD design point.
# The retained 90 s lag is a simulator dynamic calibration, not a datasheet-derived gas inventory.
R323_C003_P_TAU_S = 90.0
```

Replace the pressure target at the end of the C003 stage with:

```python
    # PT-323201 reduced-order gas-load coupling. `s.r3232_d001_P` is the beginning-of-substep
    # E003/D001 pressure; that state is advanced later, preserving the explicit tear.
    r_lv_c003 = drain_kgh / STRIP_BOT_DES_KGH
    r_305_c003 = m_305 / R323_M305_DES
    p_c003_tgt = c003_pressure_target_bara(r_lv_c003, r_305_c003, s.r3232_d001_P)
    s.r323_c003_P = clamp(
        s.r323_c003_P + (p_c003_tgt - s.r323_c003_P) / R323_C003_P_TAU_S * dt,
        1.0,
        12.0,
    )
```

Remove `R323_C003_P_GAIN`; no caller should remain.

- [ ] **Step 4: Correct stale 82% baseline comments and audit inputs**

In the `State` initialization comment in `backend/main.py`, use:

```python
        #   AUTO holds the design level (50 %) at the field-calibrated design opening (46.1 %);
        #   direct-acting.
```

In `backend/tests/run_valve_indicator_matrix.py`, use the shared constant and bracket it:

```python
    ("LV-322501 stripper drain", main.LV322501_OPEN_DES, 30.0, 65.0,
     lambda v: _man("LIC_322501", v)),
```

In `backend/tests/run_full_audit.py`, use:

```python
    print(f"\n  2d  LV-322501 stripper-bottoms drain  "
          f"(LIC-322501 MAN; design op {main.LV322501_OPEN_DES:.1f} %)")
    print(f"   {'LV op':>7} | {'LI501':>6} {'drain':>6} | {'tt004':>6}")
    rows = []
    for v in [30.0, main.LV322501_OPEN_DES, 60.0, 90.0]:
```

- [ ] **Step 5: Run the new focused tests and confirm the green state**

Run from `backend`:

```powershell
& 'C:\Users\ameel\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B -m pytest -q -p no:cacheprovider test_c003_pressure_coupling.py
```

Expected: all pure and runtime coupling tests pass.

- [ ] **Step 6: Run focused Unit 323 and session regressions**

Run:

```powershell
& 'C:\Users\ameel\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B -m pytest -q -p no:cacheprovider test_c003_pressure_coupling.py test_equation_audit_323_324.py test_equation_audit_td014.py test_session_regression_gate.py
& 'C:\Users\ameel\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B tests\audit_e001_stripper.py
```

Expected: all selected pytest cases and the standalone stripper audit pass. If an unrelated pre-existing failure appears, record its exact test and verify it also fails on the parent commit before classifying it as pre-existing.

- [ ] **Step 7: Verify syntax, stale-baseline removal, and repository scope**

Run from the repository root:

```powershell
& 'C:\Users\ameel\AppData\Local\Python\pythoncore-3.14-64\python.exe' -B -c "import ast,pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8')) for p in ('backend/c003_pressure_coupling.py','backend/main.py','backend/tests/run_valve_indicator_matrix.py','backend/tests/run_full_audit.py')]"
rg -n 'design opening \(82 %\)|design op 82 %|stripper drain".*, *82\.0' backend/main.py backend/tests
git diff --check
git status --short --untracked-files=all
```

Expected: syntax parsing succeeds, the stale-baseline search returns no matches, diff checks pass, and only the planned files are modified.

- [ ] **Step 8: Review and commit the runtime coupling**

Run:

```powershell
git add backend/main.py backend/test_c003_pressure_coupling.py backend/tests/run_valve_indicator_matrix.py backend/tests/run_full_audit.py
git diff --cached --check
git diff --cached --stat
git commit -m "🐛 fix: couple LV-322501 to C003 pressure"
```

Expected: one atomic runtime commit containing the wiring, integration tests, and field-baseline consistency corrections.

## Final Acceptance

- `c003_pressure_target_bara(1.0, 1.0, 3.2)` returns 4.1 bara.
- A 60% LV opening causes a positive first-substep 323C003 pressure response; 30% causes a negative response.
- The local design sensitivity is approximately +0.022931746 bara per opening percentage point.
- The 50.734945% vendor maximum-flow equivalent gives approximately 4.208379859 bara for the immediate LV-only response.
- Live `m_305` and beginning-of-substep 323E003/323D001 pressure remain active target drivers.
- Fresh design, supported step sizes, Unit 323/324 equation audits, and the standalone LV hydraulics audit remain green.
- The public API and state/telemetry schema are unchanged.
