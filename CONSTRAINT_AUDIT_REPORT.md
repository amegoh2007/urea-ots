# Comprehensive Constraint & Boundary Audit Report
**Urea OTS - 1,750 MTPD Stamicarbon CO2-Stripping Process**  
**Principal Process Control & DCS Architect Assessment**  
**Date:** 2026-08-20  
**Auditor:** Principal Process Control & DCS Architect  
**Scope:** All automatic valves and PID controllers within process simulation

---

## Executive Summary

A rigorous constraint and boundary audit was conducted on the Urea OTS simulation to validate that mathematical models accurately enforce:
- **Phase 1:** Controller algorithmic constraints (SP/OP limits, rate-of-change)
- **Phase 2:** Valve physical & aerodynamic constraints (actuator delays, choked flow)
- **Phase 3:** Override control & safety interlocks (ESD, bad-PV detection)
- **Phase 4:** Diagnostic reporting with violation severity classification

**Overall Assessment:** The control system architecture is **COMPLIANT** with industrial DCS standards for algorithmic constraint enforcement. Four medium-to-low severity enhancements are recommended to improve training realism and handle off-design operating conditions.

---

## Phase 1: Controller Algorithmic Constraints

### 1.1 Setpoint (SP) Clamping
**Status:** ✓ PASS

Controllers correctly enforce `[sp_lo, sp_hi]` limits:
```python
def set_sp(self, v: float) -> None:
    self.sp = _clamp(v, self.sp_lo, self.sp_hi)
```

**Test Results:**
- SP = 150% clamped to 100% (HIGH limit)
- SP = -25% clamped to 0% (LOW limit)

**Verification:** [test_constraint_audit.py:102-117](backend/test_constraint_audit.py:102)

---

### 1.2 Output (OP) Saturation
**Status:** ✓ PASS

Controllers enforce `[op_lo, op_hi]` limits with clamp status flags:
```python
new_mv = _clamp(self.mv + delta, self.op_lo, self.op_hi)
self._mv_hi_clamp = (new_mv >= self.op_hi)
self._mv_lo_clamp = (new_mv <= self.op_lo)
```

**Test Results:**
- OP saturates at 100.000% (HIGH limit, `mv_hi_clamp=True`)
- OP saturates at 0.000% (LOW limit, `mv_lo_clamp=True`)
- Custom range: OP saturates at 95.000% (verified `op_hi=95%`)

**Verification:** [test_constraint_audit.py:120-157](backend/test_constraint_audit.py:120)

---

### 1.3 Rate-of-Change (Velocity) Limits
**Status:** ✓ PASS

Controllers enforce maximum slew rate (%/s) in AUTO/CAS/OOS modes:
```python
slew_max = self.rate * dt
delta = _clamp(raw, -slew_max, slew_max)
```

**Test Results:**
- Rate limit: Δmv = 10.000% ≤ 10.000%/step (enforced)
- Instantaneous jump prevented: Kc=1000, Δmv = 1.000% ≤ 1.0%/s (enforced)

**Verification:** [test_constraint_audit.py:160-193](backend/test_constraint_audit.py:160)

---

## Phase 2: Valve Physical & Aerodynamic Constraints

### 2.1 Actuator Slew Rate (Stroke Time)
**Status:** ⚠ PARTIAL (AUTO/CAS compliant, MAN bypassed)

**PASS:** AUTO mode enforces realistic 15-second full-stroke time:
```
0 -> 100% travel time: 14.9s (rate = 6.67%/s)
```

**VIOLATION:** MAN mode `set_op()` bypasses slew rate:
```python
def set_op(self, v: float) -> None:
    """Clamps to [op_lo, op_hi]. Legal in MAN only."""
    self.mv = _clamp(v, self.op_lo, self.op_hi)
```

**Impact:** Operator MAN commands are instantaneous (mv jumps 0→100% in single tick)

**Recommendation:** Implement separate valve position model:
```python
class ValveActuator:
    def step(self, op_demand: float, dt: float) -> float:
        delta = _clamp(op_demand - self.position, -self.rate * dt, self.rate * dt)
        self.position += delta
        return self.position
```

**Severity:** MEDIUM -- affects operator training realism, not safety-critical

**Verification:** [test_constraint_audit.py:200-249](backend/test_constraint_audit.py:200)

---

### 2.2 Hysteresis and Stiction (Mechanical Deadband)
**Status:** ⚠ LIMITATION

**Current Implementation:** Controller has error deadband `Dz` (ignores PV errors < Dz):
```python
err = sp - pv if abs(sp - pv) >= self.Dz else 0.0
```

**Missing:** Valve mechanical stiction (Coulomb+viscous friction requiring threshold force)

**Impact:** Small OP changes produce immediate flow response; real valves require ~0.5-2% OP change to overcome static friction

**Recommendation:** Add Kano stiction model:
```python
# Kano two-parameter model: S (static friction), J (dynamic friction)
if abs(op - op_prev) < S and valve_at_rest:
    valve_position_unchanged()
elif valve_moving:
    valve_position += sign(op - op_prev) * (abs(op - op_prev) - J)
```

**Severity:** LOW -- minor fidelity enhancement for operator training

**Verification:** [test_constraint_audit.py:252-272](backend/test_constraint_audit.py:252)

---

### 2.3 Choked Flow (Critical Flow Limits)
**Status:** ⚠ FORM COMPLETE, awaiting runtime integration

**Achievement:** ISA 75.01.01 choked flow model BUILT and validated in `gap_g9b_valve_hydraulics.py`:
```python
def valve_flow_isa_75_01_01(Cv, x, P1_bara, P2_bara, Pv_bara, rho_kgm3):
    dP = P1_bara - P2_bara
    FF = 0.96 - 0.28 * sqrt(Pv_bara / Pc_bara)  # Liquid critical pressure ratio
    dP_choked = FF * (P1_bara - FF * Pv_bara)
    dP_eff = min(dP, dP_choked)
    return N1 * Cv * x * sqrt(dP_eff / rho_kgm3)
```

**Test Results:**
- LV-322501: dP=136.0 bar > dP_allow=111.7 bar (CHOKED, limit applied)
- LV-323501: dP=2.0 bar < dP_allow=2.5 bar (UNCHOKED, full dP used)

**Gap:** Not integrated into `main.py` runtime. Current valve models use simplified `√(dP/dP_des)` without choke detection.

**Recommendation:** Wire `gap_g9b` valve models into `main.py` pressure balances after SR-POLAR Pv/Pc integration

**Severity:** MEDIUM -- affects letdown capacity under off-design conditions (startup, turndown)

**Verification:** [test_constraint_audit.py:275-323](backend/test_constraint_audit.py:275)

---

## Phase 3: Override Control & Safety Interlocks

### 3.1 Override Selectors (High/Low Auctioneering)
**Status:** ⚠ CONCEPT VERIFIED, explicit blocks not implemented

**Test Results:**
- Normal operation: primary mv=61.0%, override mv=100.0%, selected=61.0% (min)
- Override active: primary mv=67.0%, override mv=34.0%, selected=34.0% (min, more restrictive)

**Current Architecture:** Individual controllers step independently; constraint overrides handled via mode switching

**Gap:** No explicit `Selector` class with bumpless transfer and anti-windup sync

**Recommendation:** Implement reusable selector blocks:
```python
class Selector:
    def __init__(self, logic: str):  # "HIGH", "LOW", "MEDIAN"
        self.logic = logic
    
    def select(self, *mvs: float) -> float:
        if self.logic == "HIGH": return min(mvs)  # min MV = more closing
        if self.logic == "LOW": return max(mvs)   # max MV = more opening
```

**Severity:** LOW -- current mode-switching architecture handles constraints adequately

**Verification:** [test_constraint_audit.py:326-347](backend/test_constraint_audit.py:326)

---

### 3.2 ESD Interlocks & Fail-Safe Actions
**Status:** ✓ PASS

**OOS Mode Behavior:** Controller drives to fail-safe position at max slew rate:
```python
elif self.mode == "OOS":
    target = self._fail_target()  # FC=0%, FO=100%, FL=freeze
    delta = _clamp(target - self.mv, -slew_max, slew_max)
    self.mv = _clamp(self.mv + delta, self.op_lo, self.op_hi)
```

**Test Results:**
- Pre-trip: LIC in AUTO, mv=63.0%
- ESD triggered: mode=OOS, valve strokes to FC=0.0% with slew rate
- Faceplate status: mode=OOS (locked/interlocked indication)

**Bumpless Transfer on Reset:**
- OOS → MAN: mv held at 20.0% (no jump)
- MAN → AUTO: SP adopts PV=55.0% (bumpless initialization)

**Verification:** [test_constraint_audit.py:350-382](backend/test_constraint_audit.py:350)

---

### 3.3 Bad PV Detection & Fail-Freeze
**Status:** ✓ PASS

**Detection Logic:** Controller monitors PV for `None`, `NaN`, or out-of-range:
```python
bad = (pv is None or math.isnan(pv) or pv < BAD_PV_LO or pv > BAD_PV_HI)
if bad:
    self._pv_bad = True
    if self.mode != "MAN":
        self.mode = "MAN"
        self._pid.reset()
    return self.mv  # freeze last-good MV
```

**Test Results:**
- PV = None → mode=MAN, pv_bad=True (freeze MV)
- PV = 150% > 105% → mode=MAN (out-of-range detection)

**Verification:** [test_constraint_audit.py:385-417](backend/test_constraint_audit.py:385)

---

## Phase 4: Violation Summary & Recommendations

### Violations Identified

| # | Issue | Location | Severity | Status |
|---|-------|----------|----------|--------|
| 1 | MAN mode bypasses slew rate | `controllers.py:171` | MEDIUM | Enhancement |
| 2 | Valve stiction not modeled | N/A | LOW | Enhancement |
| 3 | Choked flow not integrated | `main.py` valve models | MEDIUM | Pending integration |
| 4 | Explicit selectors not implemented | `main.py` | LOW | Architecture decision |

---

### Constraints CORRECTLY Implemented

- ✓ SP clamping at `[sp_lo, sp_hi]`
- ✓ OP saturation at `[op_lo, op_hi]` with clamp flags
- ✓ Rate-of-change (slew) limits in AUTO/CAS/OOS modes
- ✓ Bad PV detection → fail-freeze in MAN mode
- ✓ Bumpless transfer (AUTO entry adopts PV, CAS entry zeros bias)
- ✓ Anti-windup protection (velocity I-PD has no integral accumulator to wind up)
- ✓ Fail-safe actions (OOS mode strokes to FC/FO/FL at max slew rate)
- ✓ Choked flow detection (BUILT in gap_g9b, ISA 75.01.01 compliant)

---

## Recommendations

### Priority 1: Choked Flow Integration (MEDIUM severity)
**Action:** Wire `gap_g9b_valve_hydraulics.py` models into `main.py` after SR-POLAR Pv/Pc integration  
**Rationale:** High-ΔP valves (LV-322501, HV-322605) currently use simplified `√(dP)` without choke detection, affecting letdown capacity under off-design conditions  
**Effort:** 2-3 days (pending thermodynamic package completion)

### Priority 2: MAN Mode Actuator Dynamics (MEDIUM severity)
**Action:** Implement separate `ValveActuator` class with slew rate enforcement independent of controller mode  
**Rationale:** Improves operator training realism; prevents instantaneous valve jumps in MAN mode  
**Effort:** 1 day

### Priority 3: Valve Stiction Model (LOW severity)
**Action:** Add Kano or Choudhury stiction model for deadband hysteresis  
**Rationale:** Minor fidelity enhancement for operator training; real valves require threshold force  
**Effort:** 1-2 days

### Priority 4: Explicit Selector Blocks (LOW severity)
**Action:** Implement reusable `Selector` class with bumpless transfer and anti-windup sync  
**Rationale:** Current mode-switching architecture adequate; explicit blocks reduce hand-coding for future constraint additions  
**Effort:** 1 day

---

## Test Suite Documentation

**Test Script:** `backend/test_constraint_audit.py` (528 lines)  
**Execution Command:** `python test_constraint_audit.py`  
**Test Coverage:**
- Phase 1: 7 algorithmic constraint tests (ALL PASS)
- Phase 2: 6 physical constraint tests (3 PASS, 3 LIMITATION documented)
- Phase 3: 5 interlock/safety tests (ALL PASS)
- Phase 4: Diagnostic report generation (COMPLETE)

**Test Framework:**
```python
def approx(a: float, b: float, tol: float = 0.1) -> bool:
    """Floating-point comparison with tolerance."""
    return abs(a - b) <= tol
```

---

## Audit Trail

**Methodology:**
1. Created unit tests for each constraint category per ISA-5.1/IEC 61131-3 standards
2. Executed tests against production `controllers.py` implementation
3. Documented PASS/FAIL status with root-cause analysis
4. Classified violations by severity (CRITICAL/HIGH/MEDIUM/LOW)
5. Generated actionable recommendations with effort estimates

**Compliance Standards:**
- ISA-5.1: Instrumentation Symbols and Identification
- ISA-75.01.01: Control Valve Sizing Equations (choked flow)
- IEC 61131-3: PLC Programming Standards (bumpless transfer, anti-windup)
- IEC 61508: Functional Safety (fail-safe actions, bad-PV detection)

**Sign-Off:**  
Principal Process Control & DCS Architect  
Date: 2026-08-20

---

**End of Report**
