# Stripper Steam Consumption Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the simulator defect where opening the reactor letdown valve (HV-322605) causes the calculated stripper steam consumption (and FT-329403) to drop instead of rise.

**Architecture:** We will re-calibrate the thermal choke penalty `STRIP_ETA_KT` in `backend/main.py`. Reducing it from the steep `1.50` down to `0.15` ensures that during a feed surge, the absolute mass of stripped carbamate (and thus the endothermic duty) correctly increases, properly drawing more MP steam from the dynamic header. The bottom temperature (`T_bot`) surge logic will continue to anchor against the hot reactor feed as intended.

**Tech Stack:** Python 3, `pytest` for verification.

## Global Constraints

- No structural architectural changes; modify the existing constant in `backend/main.py` and verify via test scripts.
- Code should be compatible with existing models and not break the design-point steady-state output.

---

### Task 1: Re-calibrate `STRIP_ETA_KT`

**Files:**
- Modify: `backend/main.py`
- Test: `backend/test_steam_consumption_surge.py` (New file)

**Interfaces:**
- Consumes: The existing `stripper_322e001` function in `backend/main.py`.
- Produces: Updated behavior where increased feed results in increased `duty_raw_kw`.

- [ ] **Step 1: Write the failing test**

```python
# backend/test_steam_consumption_surge.py
import pytest
from main import stripper_322e001, STRIP_DUTY_RAW_DES_KW, CO2_DES_KGH, STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA, STRIP_FEED207_KMOLH, STRIP_FEED207_T_C

def test_steam_consumption_increases_on_surge():
    feed_base = STRIP_FEED207_KMOLH.copy()
    base = stripper_322e001(CO2_DES_KGH/1000.0, STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA, feed_base, None, None, STRIP_FEED207_T_C)
    
    # 20% surge in feed
    feed_surge = {k: v * 1.2 for k, v in feed_base.items()}
    surge = stripper_322e001(CO2_DES_KGH/1000.0, STRIP_STEAM_T_DES_C, STRIP_P_DES_BARA, feed_surge, None, None, STRIP_FEED207_T_C)
    
    base_ratio = base['duty_raw_kw'] / STRIP_DUTY_RAW_DES_KW
    surge_ratio = surge['duty_raw_kw'] / STRIP_DUTY_RAW_DES_KW
    
    # The absolute duty (and thus steam consumption) must INCREASE during a surge
    assert surge_ratio > base_ratio, f"Expected duty to increase on surge, but got {surge_ratio} <= {base_ratio}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/test_steam_consumption_surge.py -v`
Expected: FAIL with "Expected duty to increase on surge"

- [ ] **Step 3: Write minimal implementation**

```python
# In backend/main.py
# Locate STRIP_ETA_KT (around line 619) and change it:
STRIP_ETA_KT = 0.15     # eta_T penalty per unit fractional bottom-T deficit (feed-load cooling chokes strip)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/test_steam_consumption_surge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/test_steam_consumption_surge.py backend/main.py
git commit -m "fix(stripper): re-calibrate STRIP_ETA_KT to ensure steam duty rises on feed surge"
```
