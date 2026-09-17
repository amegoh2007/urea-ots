# Architectural Refactor: Sequential Modular (SM) Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation of a True Sequential Modular (SM) simulator by implementing event-driven `Stream`, `Unit`, and `ThermoModel` classes.

**Architecture:** We are replacing a monolithic tick loop with a directed graph of objects. Streams hold state and broadcast `is_dirty` flags when mutated. Units subscribe to input streams, re-evaluate their internal MESH equations when triggered, and mutate output streams, cascading the ripple effect.

**Tech Stack:** Python 3.x, Pytest

## Global Constraints

- No external thermodynamic libraries (e.g., CoolProp) are permitted yet; stub the interfaces.
- Strictly type-hint all core classes.
- All mass and energy balances must close to machine epsilon in tests.

---

### Task 1: Create Thermodynamic Model Interface

**Files:**
- Create: `backend/core/thermo.py`
- Test: `backend/tests/test_thermo.py`

**Interfaces:**
- Produces: `ThermoModel` base class, `EmpiricalThermo` subclass implementing stubbed vapor pressure (`bubble_p`).

- [ ] **Step 1: Write the failing test**

```python
from backend.core.thermo import EmpiricalThermo

def test_thermo_bubble_p():
    thermo = EmpiricalThermo()
    # Stubbed values for N/C, H/C
    p = thermo.bubble_p(170.0, 3.1, 0.5)
    assert p > 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_thermo.py -v`
Expected: FAIL with "ModuleNotFoundError" or similar.

- [ ] **Step 3: Write minimal implementation**

```python
class ThermoModel:
    def bubble_p(self, T_c: float, nc_ratio: float, hc_ratio: float) -> float:
        raise NotImplementedError

class EmpiricalThermo(ThermoModel):
    def bubble_p(self, T_c: float, nc_ratio: float, hc_ratio: float) -> float:
        # Placeholder empirical logic to return a positive pressure
        return 140.0 + (T_c - 170.0) * 0.5
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_thermo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/thermo.py backend/tests/test_thermo.py
git commit -m "feat: implement baseline thermo interface"
```

---

### Task 2: Create Event-Driven Stream Class

**Files:**
- Create: `backend/core/stream.py`
- Test: `backend/tests/test_stream.py`

**Interfaces:**
- Consumes: None
- Produces: `Stream` class holding properties `[T, P, mass_flow, comp, enthalpy]` with `is_dirty` flagging and observer subscription.

- [ ] **Step 1: Write the failing test**

```python
from backend.core.stream import Stream

def test_stream_dirty_flag():
    s = Stream(name="S1")
    flag_triggered = False
    
    def callback(stream):
        nonlocal flag_triggered
        flag_triggered = True
        
    s.subscribe(callback)
    s.set_state(T=150.0, P=140.0)
    
    assert s.is_dirty is True
    assert flag_triggered is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_stream.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
from typing import Callable, Dict, List

class Stream:
    def __init__(self, name: str):
        self.name = name
        self.T = 25.0
        self.P = 1.0
        self.mass_flow = 0.0
        self.comp: Dict[str, float] = {}
        self.enthalpy = 0.0
        self.is_dirty = False
        self._subscribers: List[Callable[['Stream'], None]] = []

    def subscribe(self, callback: Callable[['Stream'], None]):
        self._subscribers.append(callback)

    def set_state(self, T: float = None, P: float = None, mass_flow: float = None):
        if T is not None: self.T = T
        if P is not None: self.P = P
        if mass_flow is not None: self.mass_flow = mass_flow
        self.is_dirty = True
        self._notify()

    def _notify(self):
        for callback in self._subscribers:
            callback(self)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_stream.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/stream.py backend/tests/test_stream.py
git commit -m "feat: implement Stream class with observer pattern"
```

---

### Task 3: Create Base Unit Operation Class

**Files:**
- Create: `backend/core/unit.py`
- Test: `backend/tests/test_unit.py`

**Interfaces:**
- Consumes: `Stream` from Task 2
- Produces: `UnitOperation` base class with input/output linking and automatic evaluation.

- [ ] **Step 1: Write the failing test**

```python
from backend.core.stream import Stream
from backend.core.unit import UnitOperation

class DummyMixer(UnitOperation):
    def solve(self):
        # MESH Mass balance: Output = sum(Inputs)
        total_mass = sum(s.mass_flow for s in self.inputs)
        self.outputs[0].set_state(mass_flow=total_mass)
        # Clear dirty flags
        for s in self.inputs: s.is_dirty = False

def test_unit_cascade():
    s_in1 = Stream("In1")
    s_in2 = Stream("In2")
    s_out = Stream("Out")
    
    mixer = DummyMixer("Mixer1", inputs=[s_in1, s_in2], outputs=[s_out])
    
    # Trigger cascade
    s_in1.set_state(mass_flow=100.0)
    s_in2.set_state(mass_flow=50.0)
    
    assert s_out.mass_flow == 150.0
    assert s_in1.is_dirty is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_unit.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
from typing import List
from backend.core.stream import Stream

class UnitOperation:
    def __init__(self, name: str, inputs: List[Stream], outputs: List[Stream]):
        self.name = name
        self.inputs = inputs
        self.outputs = outputs
        
        for stream in self.inputs:
            stream.subscribe(self._on_input_changed)
            
    def _on_input_changed(self, stream: Stream):
        if stream.is_dirty:
            self.solve()
            
    def solve(self):
        raise NotImplementedError("Subclasses must implement MESH equations")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_unit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/unit.py backend/tests/test_unit.py
git commit -m "feat: implement UnitOperation base class with cascade logic"
```
