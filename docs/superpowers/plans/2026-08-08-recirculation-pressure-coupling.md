# Recirculation Stage Pressure & Heat Coupling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the inverted enthalpy calculation in 323C003 feed flash so opening `LV-322501` or increasing `323E002` LP steam duty increases 323C003 top vapor $m_{305}$, increases 323C003 pressure $P_{\text{c003}}$, increases 323D001 pressure $P_{\text{d001}}$, and forces `PIC-323202` to open `PV-323202` wider.

**Architecture:** Update `q305_avail_kw` in `backend/main.py` (and `backend/core/mp.py`) to use the positive stripper bottom letdown enthalpy driving force $(T_{\text{strip\_bot}} - T_{\text{flash,sat}})$. Ensure single-source physics parity across main and core modules and audit downstream propagation across `323F004` and `323E011`.

**Tech Stack:** Python 3.14, FastAPI backend, pytest.

## Global Constraints
- All existing design point closures must remain exact ($m_{305} = 24,582\text{ kg/h}$ at design).
- `c003_pressure_target_bara` must maintain finite input validation and non-negative monotonicity.
- All test runs must set `PYTHONPATH=backend`.

---

### Task 1: Add Unit Tests for LV-322501 & 323E002 Monotonic Response

**Files:**
- Modify: `backend/test_c003_pressure_coupling.py`

**Interfaces:**
- Consumes: `main.step_sim`, `c003_pressure_target_bara`
- Produces: Test suite validating `LV-322501` opening $\rightarrow$ `PV-323202` opening.

- [ ] **Step 1: Write the failing tests in `backend/test_c003_pressure_coupling.py`**

```python
def test_opening_lv322501_increases_top_vapor_and_opens_pv323202():
    main.state = main.State()
    state = main.state
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = 55.0  # open from 46.1% design
    
    # Run 60 seconds
    for _ in range(60):
        packet = main.step_sim(1.0)

    # v305_th should increase from 24.58 t/h design
    assert packet["RECIRC_323"]["C003"]["v305_th"] > 24.58
    # 323D001 pressure should be >= 3.20 bar a
    assert state.r3232_d001_P >= 3.20
    # PV-323202 valve stroke should increase above 25.0%
    assert state.PIC_323202["op"] > 25.0


def test_increasing_323e002_steam_increases_c003_pressure_and_pv323202():
    main.state = main.State()
    state = main.state
    state.TIC_323007["mode"] = "MAN"
    state.TIC_323007["op"] = 3.5  # higher steam chest demand
    
    for _ in range(30):
        packet = main.step_sim(1.0)

    assert packet["RECIRC_323"]["C003"]["v305_th"] > 24.58
    assert state.r323_c003_P > 4.10
    assert state.PIC_323202["op"] > 25.0
```

- [ ] **Step 2: Run pytest to verify tests fail on current codebase**

Run: `$env:PYTHONPATH="backend"; python -m pytest backend/test_c003_pressure_coupling.py -k test_opening_lv322501_increases_top_vapor_and_opens_pv323202`  
Expected: FAIL (assertion error: `v305_th` is 23.05 <= 24.58, `PV-323202` is 24.64 <= 25.0).

- [ ] **Step 3: Commit test file**

```bash
git add backend/test_c003_pressure_coupling.py
git commit -m "test: add failing tests for LV-322501 and 323E002 steam coupling to PV-323202"
```

---

### Task 2: Implement Enthalpy-Driven Flash Balance in `backend/main.py`

**Files:**
- Modify: `backend/main.py:5750-5840`

**Interfaces:**
- Consumes: `TT_322004` (stripper bottom temp $\approx 177.5\ ^\circ\text{C}$), `TT_323001` (flash temp $\approx 119.0\ ^\circ\text{C}$), `m_feed_323`, `Q_e002_kw`
- Produces: Corrected `q305_avail_kw` and $m_{305}$ in `backend/main.py`.

- [ ] **Step 1: Update `q305_avail_kw` calculation in `backend/main.py`**

In `backend/main.py` around line 5808:
```python
    T_strip_bot = s.tlag.get("TT_322004", 177.5)   # HP Stripper 322E001 bottom temp (C)
    T_flash_sat = TT_323001                        # Post-LV-322501 flash saturation temp (C)
    q_flash_avail_kw = (m_feed_323 / 3600.0 * cp_feed323 * (T_strip_bot - T_flash_sat))  # kW released by letdown flash
    q305_avail_kw = q_flash_avail_kw + Q_e002_kw                                           # total available latent kW
```

- [ ] **Step 2: Run test to verify `test_opening_lv322501_increases_top_vapor_and_opens_pv323202` passes**

Run: `$env:PYTHONPATH="backend"; python -m pytest backend/test_c003_pressure_coupling.py -v`  
Expected: PASS.

- [ ] **Step 3: Commit changes in `backend/main.py`**

```bash
git add backend/main.py
git commit -m "fix(simulation): correct 323C003 feed flash enthalpy driving force"
```

---

### Task 3: Sync `backend/core/mp.py` and `backend/core/lp.py` Core Modules

**Files:**
- Modify: `backend/core/mp.py:70-85`
- Modify: `backend/core/lp.py:410-455`

**Interfaces:**
- Consumes: `m_feed_323`, `T_strip_bot`, `T_flash_sat`, `Q_e002_kw`
- Produces: Synchronized core simulation logic in `mp.py` and `lp.py`.

- [ ] **Step 1: Update `backend/core/mp.py` with corrected `q305_avail_kw` formulation**

In `backend/core/mp.py` around line 73:
```python
        T_strip_bot = s.tlag.get("TT_322004", 177.5)
        T_flash_sat = T_feed_323
        q_flash_avail_kw = (m_feed_323 / 3600.0 * cp_feed323 * (T_strip_bot - T_flash_sat))
        q305_avail_kw = q_flash_avail_kw + Q_e002_kw
```

- [ ] **Step 2: Run pytest to verify all tests in `test_c003_pressure_coupling.py` pass**

Run: `$env:PYTHONPATH="backend"; python -m pytest backend/test_c003_pressure_coupling.py`  
Expected: PASS (all tests pass).

- [ ] **Step 3: Commit changes in `backend/core/mp.py` and `backend/core/lp.py`**

```bash
git add backend/core/mp.py backend/core/lp.py
git commit -m "fix(core): sync 323C003 letdown flash enthalpy in modular core solver"
```

---

### Task 4: Flowsheet Propagation Audit for 323F004, 323E011 & Downstream Units

**Files:**
- Modify: `backend/main.py:5840-5900`
- Modify: `backend/main.py:6550-6600`

**Interfaces:**
- Consumes: `m_314` (323C003 bottom drain), `m_321` (PV-323202 vent)
- Produces: Confirmed positive monotonicity across Stage 2 (`323F004`) and Stage 9 (`323E011`).

- [ ] **Step 1: Verify Stage 2 (`323F004`) flash gas $m_{701}$ scales positively with $m_{314}$**

In `backend/main.py` around line 5854:
Confirm `q701_avail_kw = m_314 / 3600.0 * cp_c003 * (s.r323_c003_T - s.r323_f004_T)` uses $(135.0 - 106.0) = +29.0\ ^\circ\text{C}$ (positive driving force).

- [ ] **Step 2: Verify Stage 9 (`323E011`) gas inlet $in_{\text{e011}}$ receives $m_{321}$**

In `backend/main.py` line 6556:
Confirm `in_e011` includes `(m_321 - R3232_E011_M321_DES)`.

- [ ] **Step 3: Run pytest across full backend suite**

Run: `$env:PYTHONPATH="backend"; python -m pytest backend/test_c003_pressure_coupling.py`  
Expected: PASS.

- [ ] **Step 4: Commit audit verification**

```bash
git add backend/main.py
git commit -m "audit(flowsheet): verify 323F004 and 323E011 positive downstream gas propagation"
```
