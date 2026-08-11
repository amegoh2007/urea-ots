# Consequence Propagation and Lag Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transport every equivalent process consequence as one conservative mass/temperature/species packet and apply it to downstream balances after a flow-dependent residence delay.

**Architecture:** Add packet construction, mixing, and FIFO transport primitives to the shared consequence module. Define physical route anchors in the engine and replace scalar, scenario-specific seal-loss propagation with packets consumed by the existing destination mass, energy, pressure, and species balances. Publish the same packet as route diagnostics.

**Tech Stack:** Python 3, dataclasses, timestamped `collections.deque`, pytest, existing sequential-modular ODE engine

## Global Constraints

- Preserve the 0.1 s real-time simulation step and fresh-process design fixed point.
- Use the existing 8 s gas-front and 20 s liquid-slug design anchors; derive live lag from effective inventory divided by live carrier flow.
- Transport total mass, component mass, and sensible enthalpy together.
- Do not assign downstream pressure, temperature, or composition states directly.
- Preserve zoned thermodynamic-package routing and all untracked `scratch/` files.
- Do not invent pipe lengths, fitting losses, PSV settings, or vendor curves.

---

### Task 1: Conservative consequence packet and transport law

**Files:**
- Modify: `backend/consequence.py`
- Create: `backend/test_consequence_transport.py`

**Interfaces:**
- Consumes: mutable `dict` transport store, simulation `dt`, route design carrier flow, live carrier flow
- Produces: `StreamPacket`, `make_stream_packet`, `mix_stream_packets`, `transport_stream_packet`

- [x] **Step 1: Write failing packet closure and mixing tests**

```python
def test_packet_derives_total_and_fraction_from_components():
    packet = cq.make_stream_packet(100.0, {"NH3": 25.0, "CO2": 75.0}, 80.0, 2.2)
    assert packet.mass_kgh == pytest.approx(100.0)
    assert packet.mass_fraction == pytest.approx({"NH3": 0.25, "CO2": 0.75})

def test_mixing_conserves_components_and_sensible_enthalpy():
    cold = cq.make_stream_packet(100.0, {"H2O": 100.0}, 20.0, 4.0)
    hot = cq.make_stream_packet(100.0, {"H2O": 100.0}, 100.0, 4.0)
    mixed = cq.mix_stream_packets(cold, hot)
    assert mixed.component_kgh["H2O"] == pytest.approx(200.0)
    assert mixed.temperature_c == pytest.approx(60.0)
```

- [x] **Step 2: Run tests and verify RED**

Run: `python -m pytest backend/test_consequence_transport.py -q`
Expected: collection fails because the packet API does not exist.

- [x] **Step 3: Implement immutable packet construction and mixing**

```python
@dataclass(frozen=True)
class StreamPacket:
    mass_kgh: float
    temperature_c: float
    cp_kj_kgk: float
    component_kgh: dict[str, float]

    @property
    def sensible_kw(self) -> float:
        return self.mass_kgh * self.cp_kj_kgk * self.temperature_c / 3600.0

    @property
    def mass_fraction(self) -> dict[str, float]:
        return {name: flow / self.mass_kgh for name, flow in self.component_kgh.items()}
```

Construction must copy inputs, reject negative component rates, derive total from components, and return an exact zero packet when all components are zero. Mixing sums component and sensible-enthalpy rates before deriving temperature.

- [x] **Step 4: Write failing flow-dependent FIFO tests**

```python
def test_equivalent_sources_have_identical_delayed_packets():
    route = cq.ConsequenceRoute("A", "B", 3600.0, 10.0, 120.0)
    packet = cq.make_stream_packet(20.0, {"NH3": 5.0, "CO2": 15.0}, 120.0, 2.2)
    left, right = {}, {}
    for _ in range(200):
        cq.transport_stream_packet(left, "listed", cq.ZERO_PACKET, route, 3600.0, 0.1)
        cq.transport_stream_packet(right, "unlisted", cq.ZERO_PACKET, route, 3600.0, 0.1)
    a = cq.transport_stream_packet(left, "listed", packet, route, 3600.0, 0.1)
    b = cq.transport_stream_packet(right, "unlisted", packet, route, 3600.0, 0.1)
    assert a == b == cq.ZERO_PACKET

def test_lower_carrier_flow_lengthens_dead_time():
    route = cq.ConsequenceRoute("A", "B", 3600.0, 10.0, 120.0)
    assert route.dead_time_s(1800.0) == pytest.approx(20.0)
    assert route.dead_time_s(7200.0) == pytest.approx(5.0)
```

- [x] **Step 5: Run tests and verify RED**

Run: `python -m pytest backend/test_consequence_transport.py -q`
Expected: the transport and route APIs are missing.

- [x] **Step 6: Implement timestamped whole-packet FIFO transport**

Store copied packets in a `deque[(time_s, StreamPacket)]`. Keep the newest sample at or before `now - dead_time`, discard only superseded samples, and return the settled historical packet. Publish live `dead_time_s` without changing the packet.

- [x] **Step 7: Run transport unit tests and verify GREEN**

Run: `python -m pytest backend/test_consequence_transport.py -q`
Expected: all packet, mixing, delay, and source-independence tests pass.

### Task 2: Shared physical route registry and downstream gas-load application

**Files:**
- Modify: `backend/main.py`
- Create: `backend/test_consequence_propagation.py`

**Interfaces:**
- Consumes: `consequence.StreamPacket`, destination background streams, existing `State.tlag`
- Produces: `CONSEQUENCE_ROUTES`, `_consequence_packet_from_mass_fraction`, `_transport_consequence`, route diagnostics

- [x] **Step 1: Write failing route-parity tests**

```python
@pytest.mark.parametrize("route_name", [
    "322E001_TO_323C003", "323C003_TO_323F004", "323F004_TO_323F010",
    "328C003_TO_328C004", "328C004_TO_740", "322C001_TO_323E003",
])
def test_every_seal_loss_connection_uses_a_consequence_route(route_name):
    assert route_name in main.CONSEQUENCE_ROUTES

def test_route_design_dead_times_are_positive_and_bounded():
    for route in main.CONSEQUENCE_ROUTES.values():
        assert 2.0 <= route.design_dead_time_s <= 120.0
```

- [x] **Step 2: Run route tests and verify RED**

Run: `python -m pytest backend/test_consequence_propagation.py -q`
Expected: `CONSEQUENCE_ROUTES` is absent.

- [x] **Step 3: Add route registry and engine adapters**

Define each source/destination connection once. Use design carrier flow and gas-front anchor to construct its effective inventory. Build source packets from live vapor mass fractions and temperature. Store the arrived packet and route diagnostics in `State.tlag`.

- [x] **Step 4: Write failing destination-effect tests**

```python
def test_unlisted_hydrolyser_seal_loss_reaches_desorber_after_dead_time():
    state = fresh_and_settle(20.0)
    state.a328_c003_M = 1.0
    before = state.a328_c004_P
    early = run_for(4.0)
    assert early["CONSEQUENCE_TRANSPORT"]["328C003_TO_328C004"]["arrived_mass_kgh"] == 0.0
    late = run_for(20.0)
    diag = late["CONSEQUENCE_TRANSPORT"]["328C003_TO_328C004"]
    assert diag["arrived_mass_kgh"] > 0.0
    assert state.a328_c004_P > before
    assert sum(diag["component_kgh"].values()) == pytest.approx(diag["arrived_mass_kgh"])

def test_lp_absorber_seal_loss_adds_delayed_gas_load_to_lpcc():
    state = fresh_and_settle(20.0)
    state.a328_c001_M = 1.0
    early = run_for(4.0)
    assert early["CONSEQUENCE_TRANSPORT"]["322C001_TO_323E003"]["arrived_mass_kgh"] == 0.0
    late = run_for(20.0)
    assert late["CONSEQUENCE_TRANSPORT"]["322C001_TO_323E003"]["arrived_mass_kgh"] > 0.0
```

- [x] **Step 5: Run destination tests and verify RED**

Run: `python -m pytest backend/test_consequence_propagation.py -q`
Expected: scalar flags exist, but no delayed packet reaches these downstream balances.

- [x] **Step 6: Replace scalar propagation with arrived packets**

For every route, add arrived mass to the destination gas load, arrived sensible heat to its energy balance where
the destination has one, and arrived component rates to the destination species mix. Keep liquid inventory
balances separate when the consequence is gas bypassing a liquid outlet. Replace raw scalar use with arrived
mass so no destination responds before transport.

- [x] **Step 7: Publish conservative route diagnostics**

Add `CONSEQUENCE_TRANSPORT` to the step result with route endpoints, live dead time, mass, temperature,
component rates, and mass fractions. Build diagnostics from the same arrived packet consumed by physics.

- [x] **Step 8: Run propagation tests and verify GREEN**

Run: `python -m pytest backend/test_consequence_propagation.py -q`
Expected: all route, lag, equipment, property, and composition assertions pass.

### Task 3: Scenario regressions, startup stability, and documentation

**Files:**
- Modify: `backend/test_scenario_consequences.py`
- Modify: `backend/test_scenario_coverage.py`
- Modify: `docs/Urea OTS — As-Built Mathematical Reference.md`
- Modify: `handoff.md`

**Interfaces:**
- Consumes: route diagnostics and existing 48-entry scenario manifest
- Produces: regression evidence and documented model limitations

- [x] **Step 1: Extend scenario evidence for unlisted equivalent causes**

Assert that low-level seal losses on 328C003, 328C004, and 322C001 generate the shared class, arrive after a
positive dead time, carry a closing component vector, and affect their physical destinations.

- [x] **Step 2: Run focused scenario tests**

Run: `python backend/test_scenario_consequences.py`
Expected: all legacy and new consequence checks pass.

- [x] **Step 3: Update the mathematical reference and handoff**

Document packet equations, effective-inventory lag, the six wired routes, thermodynamic ownership at each
destination, validation evidence, and the explicit lack of field pipe-volume data.

- [x] **Step 4: Run the complete relevant verification suite**

Run:

```powershell
python -m pytest backend/test_consequence_transport.py backend/test_consequence_propagation.py backend/test_scenario_coverage.py backend/test_startup_stability.py backend/test_hp_carbamate_recycle.py -q
python backend/test_scenario_consequences.py
python backend/test_lv322501_pressure_retuning.py
python -m py_compile backend/consequence.py backend/main.py backend/scenario_coverage.py
git diff --check
```

Expected: zero failures, zero syntax errors, and no whitespace errors.

- [x] **Step 5: Review the staged diff and commit**

```powershell
git status --short
git diff --stat
git add backend/consequence.py backend/main.py backend/test_consequence_transport.py backend/test_consequence_propagation.py backend/test_scenario_consequences.py backend/test_scenario_coverage.py 'docs/Urea OTS — As-Built Mathematical Reference.md' handoff.md docs/superpowers/plans/2026-08-11-consequence-propagation-and-lag.md docs/superpowers/specs/2026-08-11-consequence-propagation-and-lag-design.md
git commit -m "✨ feat: propagate process consequences with physical lag"
```
