# Control-Loop Architecture — Design Specification

**Date:** 2026-06-05
**Status:** Approved (design) — implementation gated behind plan (`writing-plans`).
**Component:** `backend/controllers.py` (new) + FastAPI REST routes + WebSocket payload contract.
**Context:** Reduced-OTS Stamicarbon urea-plant physics engine. `main.py` is the state router /
`step_sim` / WebSocket–FastAPI hub; `reactor.py` is the quarantined kinetics module. This spec
defines a third quarantined module, `controllers.py`, supplying DCS-style regulatory control, and
the JSON contract by which operator faceplates read controller state and issue commands.

---

## 1. Scope

**In scope**
- `controllers.py`: a reusable `PID` (velocity I-PD) + `Controller` (4-state) with output
  conditioning (direction, MV limits, slew-rate limit, fail position), zero physics dependency.
- Controller tick wiring inside `step_sim`.
- WebSocket **read** contract: a namespaced `controllers` block in the broadcast packet.
- FastAPI **write** contract: `POST /api/ctrl/{tag}` command envelope + `GET /api/ctrl[/{tag}]`,
  Pydantic-validated, with a concurrency lock shared with the step loop.
- TDD unit + route tests; full regression preservation.

**Out of scope (follow-on plans)**
- Frontend faceplate UI (rendering, widgets, interaction). This spec fixes only the data contract
  the faceplates consume; `frontend/*` stays untouched (currently stashed for a pristine slate).
- Multi-master cascade topologies beyond a single master→slave SP feed.
- Live tuning persistence to disk.

---

## 2. Locked architectural decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | PID algorithm form | **Velocity / incremental** | Bumpless-by-construction (output integrates off live MV, no integral state to reset); anti-windup is the MV clamp; lean payload (no integral term to telemeter). |
| 2 | Setpoint weighting | **I-PD** (P,D on PV; I on error) | SP step perturbs only the integral term — no proportional/derivative kick. Bumpless SP retune **and** bumpless cascade handoff with **zero** upward tracking signal. Smooth OTS response. |
| 3 | Mode set | **MAN / AUTO / CAS / OOS** (4-state) | OOS gives genuine isolation-drill realism (loop off, valve strokes to mechanical fail position). IMAN/Track dropped — redundant under velocity form (MV-ride gives it implicitly). |
| 4 | Output conditioning | **Rate-limited slew + clamp-only anti-windup** | Valve-stroke slew is mandated by the OOS drill ("watch the valve drive to fail-safe"). Velocity MV clamp already prevents windup; conditional integration is marginal and omitted. |
| 5 | Payload transport | **WS read-broadcast + REST POST writes** | High-frequency state streams over WS; discrete operator commands are REST transactions with native Pydantic validation and HTTP status acks — no hand-rolled request/ack correlation on the socket. |

---

## 3. Algorithm — velocity I-PD

Per scan $k$, with $\Delta t$ = sim step (default $2.0\ \text{s}$), $e_k = SP_k - PV_k$:

$$
\Delta u_k = \sigma\,K_c\!\left[\;\underbrace{-\big(PV_k - PV_{k-1}\big)}_{\text{proportional, on PV}}
\;+\; \underbrace{\frac{\Delta t}{T_i}\big(SP_k - PV_k\big)}_{\text{integral, on error}}
\;\underbrace{-\,T_d\,\frac{PV_k - 2\,PV_{k-1} + PV_{k-2}}{\Delta t}}_{\text{derivative, on PV}}\;\right]
$$

**Direction** $\sigma$:
$$
\sigma = \begin{cases} +1 & \text{REVERSE-acting } (\uparrow PV \Rightarrow \downarrow MV) \\ -1 & \text{DIRECT-acting } (\uparrow PV \Rightarrow \uparrow MV) \end{cases}
\qquad K_c > 0 \ \text{always (operator-friendly; sign carried by } \sigma).
$$

**Slew-rate limit** then **output clamp** (the anti-windup):
$$
\Delta u_k \;\leftarrow\; \mathrm{clamp}\!\big(\Delta u_k,\; -\dot u_{max}\,\Delta t,\; +\dot u_{max}\,\Delta t\big)
$$
$$
u_k \;=\; \mathrm{clamp}\!\big(u_{k-1} + \Delta u_k,\; u_{lo},\; u_{hi}\big)
$$

**Stored state:** $PV_{k-1},\ PV_{k-2},\ u_{k-1}$. No integral accumulator exists — the clamp on
$u_k$ is the complete anti-windup; a saturated period cannot wind because there is nothing to wind.
Clamp flags `mv_hi_clamp` / `mv_lo_clamp` are raised when the respective limit is active this scan.

**Why no SP-kick (key I-PD property):** a setpoint step $\Delta SP$ appears only in the integral
term, contributing $\sigma K_c\frac{\Delta t}{T_i}\Delta SP$ to a single $\Delta u_k$ — a small,
one-scan, integral-paced nudge. The proportional and derivative terms see only $PV$, which is
continuous across the step. No proportional or derivative spike. This is what makes both SP retunes
and CAS handoffs bumpless without any master-side tracking signal.

---

## 4. Mode state machine

Four operator-visible modes. Bumpless continuity is intrinsic to the velocity form; entry actions
below only set SP/MV references.

| Mode | Output law (per scan) | On entry |
|------|-----------------------|----------|
| **MAN**  | $u_k = u_{k-1} + \mathrm{clamp}\big(u^{\text{op}} - u_{k-1},\ \pm\dot u_{max}\Delta t\big)$ — operator target $u^{\text{op}}$, slewed | freeze MV at current $u$ |
| **AUTO** | velocity I-PD (§3) on local $SP$ | $SP \leftarrow PV$ (zero initial error) |
| **CAS**  | velocity I-PD on $SP = \mathrm{clamp}\big(\text{cas\_sp} + n_c,\ sp_{lo},\ sp_{hi}\big)$ | $n_c \leftarrow 0$; SP taken from master MV |
| **OOS**  | $u_k = u_{k-1} + \mathrm{clamp}\big(u^\* - u_{k-1},\ \pm\dot u_{max}\Delta t\big)$ | stroke toward fail target $u^\*$ |

**Cascade bias** $n_c$: operator feedforward trim added to the master setpoint in CAS, default 0,
reset to 0 on CAS entry. Advanced-tuning affordance.

**Fail target** $u^\*$ (per-loop `fail_action`):
$$
u^\* = \begin{cases} 0 & \text{FC — fail-closed} \\ 100 & \text{FO — fail-open} \\ u_{k-1} & \text{FL — fail-last (freeze)} \end{cases}
$$

**Bad-PV fail-freeze.** PV is *bad* when it is `None`/`NaN` or outside $[-5,\,105]\%$. On bad PV the
controller forces **MAN**, freezes the last-good MV, and raises `pv_bad`. Recovery is operator-driven
(re-select AUTO/CAS once PV is good again).

**Transition legality** (enforced at the write API, §6):
- `set_op` accepted only in **MAN** → else `409`.
- `set_bias` accepted only in **CAS** → else `409`.
- `set_sp` accepted only in **AUTO** (where it moves the live setpoint) → else `409`. Rationale:
  AUTO entry adopts PV (SP←PV), so a MAN/OOS-staged SP would be discarded on transfer; in CAS the
  master owns SP. The operator walks the setpoint after selecting AUTO.
- `set_mode` to any of the four always legal; `set_tuning` always legal.

---

## 5. Output conditioning parameters (per loop)

| Param | Symbol | Meaning | Default |
|-------|--------|---------|---------|
| `action` | $\sigma$ | DIRECT / REVERSE | REVERSE |
| `op_lo` | $u_{lo}$ | MV low limit (%) | 0.0 |
| `op_hi` | $u_{hi}$ | MV high limit (%) | 100.0 |
| `sp_lo` | $sp_{lo}$ | setpoint low limit (%) | 0.0 |
| `sp_hi` | $sp_{hi}$ | setpoint high limit (%) | 100.0 |
| `rate`  | $\dot u_{max}$ | slew rate (%/s); full 0→100 stroke takes $100/\dot u_{max}$ s | 10.0 |
| `fail_action` | — | FC / FO / FL | FC |
| `Kc` | $K_c$ | proportional gain (>0) | per loop |
| `Ti` | $T_i$ | integral time (s) | per loop |
| `Td` | $T_d$ | derivative time (s); 0 ⇒ PI | 0.0 |

The slew is applied at the **output stage for every mode** (PID, MAN, OOS), so all MV motion strokes
at the same actuator rate — one realized `mv` value, no separate target/position split.

---

## 6. Data flow

### 6.1 Tick (read side, in `step_sim(dt)`)
Order each step: physics computes process variables → **controller tick** → packet assembly.
For each registered loop:
1. read $PV$ from the relevant state field,
2. `mv = ctrl.step(pv, dt, cas_sp)` (with `cas_sp` supplied for CAS loops, else `None`),
3. write `mv` to the loop's manipulated state variable (e.g. `SIC_321951` MV → torque-converter
   valve opening) — consumed by physics on the **next** step (one-scan actuation delay, realistic).

The mutation in step 3 and all REST writes (§6.3) are serialized by a shared `threading.Lock`.

### 6.2 Read contract (WebSocket broadcast packet)
A namespaced block, one object per loop:

```json
"controllers": {
  "SIC_321951": {
    "mode": "AUTO",                       // MAN | AUTO | CAS | OOS
    "pv":   78.4,                         // %  process variable
    "sp":   80.0,                         // %  active setpoint
    "mv":   42.1,                         // %  realized valve position (post-slew)
    "cas_sp": null,                       // %  master MV when CAS, else null
    "bias":  0.0,                         // %  CAS feedforward bias n_c
    "action": "REVERSE",                  // DIRECT | REVERSE
    "tuning": { "Kc": 2.0, "Ti": 8.0, "Td": 0.0 },
    "limits": { "op_lo": 0.0, "op_hi": 100.0, "sp_lo": 0.0, "sp_hi": 100.0, "rate": 10.0 },
    "fail_action": "FC",                  // FC | FO | FL
    "status": { "pv_bad": false, "mv_hi_clamp": false, "mv_lo_clamp": false }
  }
}
```

All values rounded for transport (1 decimal on PV/SP/MV/cas_sp/bias; tuning/limits as configured).

### 6.3 Write contract (FastAPI REST)
`POST /api/ctrl/{tag}` — body is a discriminated command envelope (Pydantic `CtrlCommand`):

```json
{ "cmd": "set_mode",   "value": "AUTO" }            // value ∈ {MAN,AUTO,CAS,OOS}
{ "cmd": "set_sp",     "value": 82.0  }             // float, AUTO only, clamped to [sp_lo, sp_hi]
{ "cmd": "set_op",     "value": 35.0  }             // float, MAN only, clamped to [op_lo, op_hi]
{ "cmd": "set_bias",   "value": 1.5   }             // float, CAS only
{ "cmd": "set_tuning", "value": { "Kc": 2.5, "Ti": 7.0, "Td": 0.0 } }
```

**Ack** (JSON body):
```json
{ "ok": true,  "tag": "SIC_321951", "mode": "AUTO", "reason": null }
{ "ok": false, "tag": "SIC_321951", "mode": "MAN",  "reason": "set_op valid only in MAN" }
```

**Status codes / validation**
| Condition | Code | Body `reason` |
|-----------|------|---------------|
| unknown `tag` | **404** | `"unknown controller tag"` |
| malformed body / bad enum | **422** | Pydantic detail |
| mode-illegal command (e.g. `set_op` outside MAN) | **409** | rule text |
| `set_sp` / `set_op` out of limits | **200** | `ok:true`, value **clamped**, `reason` echoes clamp |
| valid | **200** | `ok:true` |

`GET /api/ctrl` → all blocks (same schema as §6.2); `GET /api/ctrl/{tag}` → one block (404 if
unknown). GET exists for REST completeness and as a test hook; the WS stream remains the live path.

**Concurrency.** REST handlers acquire the shared `threading.Lock` before mutating controller state,
the same lock the tick (§6.1) holds while stepping. Writes and ticks never interleave.

---

## 7. Module layout & files

**Create `backend/controllers.py`** — no import of `main`. Public surface:
- `class PID` — velocity I-PD core, holds $PV_{k-1},PV_{k-2}$: `__init__(Kc, Ti, Td=0.0)`, `reset()`,
  `step(sp, pv, dt) -> Δ`, returning $Δ = K_c\!\left[-(PV_k{-}PV_{k-1}) + \frac{\Delta t}{T_i}e_k - T_d\frac{PV_k-2PV_{k-1}+PV_{k-2}}{\Delta t}\right]$
  (pre-direction, pre-slew). Direction $\sigma$, slew, clamp, accumulation, and mode laws live in `Controller`.
- `class Controller` — wraps a `PID`, holds mode/SP/MV/bias/limits/action/fail_action/status; methods
  `set_mode(mode)`, `set_sp(v)`, `set_op(v)`, `set_bias(v)`, `set_tuning(**kw)`, `step(pv, dt, cas_sp=None) -> mv`,
  `to_packet() -> dict`. Encapsulates slew, clamp, bad-PV fail-freeze, mode laws.
- helpers: `clamp`, `BAD_PV_LO=-5.0`, `BAD_PV_HI=105.0`, fail-target resolution.

**Modify `backend/main.py`**
- delete inline `PID` (L676-690) and `Controller` (L692-741); import from `controllers`.
- build a registry `state.controllers = { tag: Controller(...) }`.
- in `step_sim`: tick each loop (§6.1) under the lock.
- emit `packet["controllers"] = { tag: c.to_packet() }`.
- add `CtrlCommand` Pydantic model + `POST /api/ctrl/{tag}`, `GET /api/ctrl`, `GET /api/ctrl/{tag}`.
- instantiate the shared `threading.Lock`.

**Create `backend/test_controllers.py`** — §8.

---

## 8. Testing (TDD, plain-assert + FastAPI `TestClient`)

**PID / algorithm**
- **No SP-kick:** step SP up; assert the single-scan $\Delta MV = \sigma K_c \frac{\Delta t}{T_i}\Delta SP$
  (integral-only); no proportional/derivative spike.
- **Bumpless MAN→AUTO:** MV continuous across the switch (|Δ| within slew bound).
- **Bumpless CAS handoff:** with `cas_sp` ≠ local SP, MV continuous on CAS entry.
- **Slew limit:** for a large command, $|MV_k - MV_{k-1}| \le \dot u_{max}\Delta t$ each scan.
- **Anti-windup:** drive MV to a clamp, then reverse the error sign; MV leaves the limit on the
  next scan (no wind-down lag).
- **Direction:** REVERSE vs DIRECT produce opposite-sign $\Delta MV$ for the same error.

**Modes**
- **OOS strokes to fail target** at the slew rate: FC→0, FO→100, FL→freeze.
- **Bad PV:** inject `None`/`NaN`/out-of-range PV → mode forced MAN, MV frozen, `pv_bad` true.

**Routes**
- each `cmd` happy path → `200`, `ok:true`, expected state mutation.
- `404` unknown tag; `422` malformed/bad enum; `409` mode-illegal (`set_op` in AUTO, `set_bias` in MAN, `set_sp` in OOS).
- limit clamp path: `set_op 130` in MAN → `200`, MV clamped to `op_hi`, `reason` notes clamp.

**Regression**
- all existing suites stay green (physics design point untouched).
- `SIC_321951` behavior at the design operating point is identical after the class moves from
  `main.py` into `controllers.py` (no functional drift from the relocation).

---

## 9. Initial loop roster

- **`SIC_321951`** — exists today (speed/torque-converter valve). Migrated to the new `Controller`.
- **Cascade demo (natural given the new inventory states):** level loops on **`LT_322E002`** (HPCC)
  and **`LT_322504`** (reactor), enabling a master→slave CAS demonstration against the Euler levels
  built in the hydraulics phase.

The `Controller` class is generic; the exact roster is a configuration concern. Final roster +
per-loop tuning/limits/action/fail_action values are fixed during plan execution against the live
engine (no fabricated constants — anchored to design operating points, per project convention).

---

## 10. Future scope (not now — YAGNI)

- Two-DOF setpoint weighting (exposed $b, c$) if faster SP tracking is ever wanted.
- Conditional-integration anti-windup if a loop shows clamp-recovery lag in practice.
- Multi-level / multi-master cascade trees.
- Tuning persistence and per-trainee scenario snapshots.
