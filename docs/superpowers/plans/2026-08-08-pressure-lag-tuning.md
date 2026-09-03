# Pressure Lag Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decrease lag times between `LV-322501` opening, `PT-323201` increasing, and `PIC-323202` increasing to 1-2 seconds.

**Architecture:** We will adjust two dynamic constants in the simulation core (`main.py`): the first-order lag time constant for `PT-323201` and the integrator gain for `PIC-323202`.

**Tech Stack:** Python

## Global Constraints

- Must maintain numerical stability (no instant spikes).
- Target response time: 1-2 seconds.

---

### Task 1: Update Pressure Constants

**Files:**
- Modify: `backend/main.py`

**Interfaces:**
- Consumes: Existing dynamic configuration.
- Produces: Updated constants `R323_C003_P_TAU_S` and `R3232_D001_P_KP`.

- [ ] **Step 1: Modify Flash Drum Pressure Lag**

```python
# In backend/main.py (around line 869)
# Change R323_C003_P_TAU_S = 5.0 to 1.0
R323_C003_P_TAU_S = 1.0
```

- [ ] **Step 2: Modify LPCC Integrator Gain**

```python
# In backend/main.py (around line 1363)
# Change R3232_D001_P_KP = 0.03 to 0.30
R3232_D001_P_BARA = 3.2 ; R3232_D001_P_KP = 0.30
```

- [ ] **Step 3: Run debug script to verify fast response**

Run: `python backend/debug_hv605.py`
Expected: When `m_feed` increases (at step 80), `PT-323201` and `PIC-323202` should reach their new elevated pressures within 1-2 simulation steps.

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "Decrease PT-323201 tau to 1.0s and increase PIC-323202 KP to 0.30"
```
