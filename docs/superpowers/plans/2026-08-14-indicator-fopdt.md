# Indicator FOPDT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every numeric HMI indicator a deterministic process time constant and dead time derived from the supplied plant procedure.

**Architecture:** A dependency-free JavaScript service classifies instrument tags and applies a simulation-clock FOPDT response. Both legacy `setPI()` readouts and image-backed overlays call the same service, so repeated tags share one measurement state without modifying backend balances or controller loops.

**Tech Stack:** Browser JavaScript, Node.js built-in `assert`, Python/pytest regression suite.

## Global Constraints

- Preserve all pre-existing dirty-worktree edits.
- Use `sim_t`, never wall time, so SLOW and FAST modes have identical plant dynamics.
- Seed first observations from the raw value; design startup remains bumpless.
- Apply the layer only to numeric indicators, not commands, setpoints, digital states, alarms, or stream-inspector balances.
- Every overlay `t: 'ind'` tag must resolve to positive `tauS` and `deadTimeS`.

---

### Task 1: FOPDT service and classification

**Files:**
- Create: `frontend/indicator_dynamics.js`
- Create: `frontend/test_indicator_dynamics.js`

**Interfaces:**
- Consumes: instrument tag, raw numeric value, `sim_t`, optional profile override.
- Produces: `IndicatorDynamics.profile()`, `.sample()`, `.describe()`, and `.reset()`.

- [ ] **Step 1: Write failing profile and response tests**

```javascript
const d = require('./indicator_dynamics.js');
assert.deepStrictEqual(d.profile('TT-322010').tauS, 30);
d.sample('TT-1', 'TT-1', 0, 0);
assert.strictEqual(d.sample('TT-1', 'TT-1', 100, 1, {tauS:10, deadTimeS:2}), 0);
assert.ok(Math.abs(d.sample('TT-1', 'TT-1', 100, 12, {tauS:10, deadTimeS:2}) - 63.212) < 0.1);
```

- [ ] **Step 2: Run test and verify missing-module failure**

Run: `node frontend/test_indicator_dynamics.js`

Expected: FAIL because `frontend/indicator_dynamics.js` does not exist.

- [ ] **Step 3: Implement profile classification and exact FOPDT sampling**

Implement the parameter matrix from the design, a timestamped zero-order-hold queue, exact exponential lag, duplicate-timestamp idempotence, and reset-on-clock-rewind behavior.

- [ ] **Step 4: Run focused tests**

Run: `node frontend/test_indicator_dynamics.js`

Expected: PASS with a test-count summary.

### Task 2: Complete indicator integration

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/app.js`
- Modify: `frontend/overlays.js`
- Modify: `frontend/test_indicator_dynamics.js`

**Interfaces:**
- Consumes: `window.IndicatorDynamics`, `lastState.sim_t`, overlay tag/bind records.
- Produces: delayed/lagged displayed values and τ/θ tooltips on both rendering paths.

- [ ] **Step 1: Add failing source-integration and coverage assertions**

Parse `overlays.js` and assert at least 227 `t: 'ind'` records, every tag has a positive profile, overlay rendering calls `IndicatorDynamics.sample`, legacy `setPI` calls it, and `index.html` loads the service before `app.js`.

- [ ] **Step 2: Run test and verify integration assertions fail**

Run: `node frontend/test_indicator_dynamics.js`

Expected: FAIL because neither render path calls the service.

- [ ] **Step 3: Wire both render paths and tooltip metadata**

Load `indicator_dynamics.js` before `app.js`; resolve legacy packet keys through `TAG_MAP`; sample overlay values before unit conversion; append `describe()` output to hover text.

- [ ] **Step 4: Run focused tests and syntax checks**

Run:

```powershell
node frontend/test_indicator_dynamics.js
node --check frontend/indicator_dynamics.js
node --check frontend/app.js
node --check frontend/overlays.js
```

Expected: all exit 0.

### Task 3: Mathematical and gap documentation

**Files:**
- Modify: `docs/Urea OTS — As-Built Mathematical Reference.md`
- Modify: `handoff.md`
- Modify: `C:/Users/ameel/.codex/skills/chemical-modelling/references/mesh-equations.md` (skill knowledge; not repository commit)

**Interfaces:**
- Consumes: final parameter matrix and FOPDT equations.
- Produces: as-built model description, current-only gap state, reusable modelling reference.

- [ ] **Step 1: Document equation, numerical update, parameter matrix, scope, and sources**

Record that the layer is measurement-only and does not replace equipment mass/energy holdup dynamics.

- [ ] **Step 2: Remove any closed indicator-dynamics gap and retain unrelated open gaps**

Search `handoff.md` for timing/delay entries; delete only entries closed by this work.

- [ ] **Step 3: Run documentation consistency searches**

Run:

```powershell
rg -n "FOPDT|dead time|time constant|IndicatorDynamics" frontend docs handoff.md
rg -n "T[B]D|T[O]DO|implement l[a]ter|fill in det[a]ils" docs/superpowers/specs/2026-08-14-indicator-fopdt-design.md docs/superpowers/plans/2026-08-14-indicator-fopdt.md
```

Expected: FOPDT references exist; placeholder scan has no output.

### Task 4: Regression, graph update, and commit

**Files:**
- Update: `graphify-out/*`
- Stage only files created or modified by this task.

**Interfaces:**
- Consumes: completed implementation and docs.
- Produces: verified project graph and Git commit.

- [ ] **Step 1: Run frontend tests and full backend regression**

Run:

```powershell
node frontend/test_indicator_dynamics.js
$env:PYTHONPATH='backend'; python -m pytest backend -q
```

Expected: all tests pass.

- [ ] **Step 2: Update the project graph**

Run graphify against the changed frontend source and record the generated graph artifacts without using multi-agent semantic extraction.

- [ ] **Step 3: Review status and staged diff**

Confirm pre-existing changes remain unstaged unless a touched file necessarily contains both sets; inspect the full staged patch before commit.

- [ ] **Step 4: Commit**

```powershell
git commit -m "feat: add FOPDT dynamics to all indicators"
```
