# Live Indicator Faceplates Implementation Plan

> Execute test-first in the existing working tree. Stage only this feature's hunks because unrelated local edits are present.

**Goal:** Show every clicked indicator in a controller-style live faceplate, with numeric PVs at three decimal places and discrete PV text unchanged.

**Architecture:** Add a browser/Node-compatible live-value registry. The legacy and overlay rendering paths publish their final post-dynamics values, and all faceplates read the current PV from that registry.

**Tech stack:** Vanilla JavaScript, HTML/CSS, Node's built-in test runner, Graphify project graph.

---

## Task 1: Specify the registry and integration contract

**Files:**

- Create: `frontend/test_indicator_faceplate.js`
- Modify: `frontend/test_indicator_dynamics.js`

1. Add failing unit tests for numeric values at exactly three decimals, preserved digital strings, missing values, and latest-value registry lookup.
2. Add failing source-integration assertions for module load order, publication in both rendering paths, the generic indicator faceplate route, and controller use of the registry formatter.
3. Run both Node test files and confirm the new assertions fail for the expected missing implementation.

## Task 2: Implement the shared live-value registry

**Files:**

- Create: `frontend/indicator_faceplate.js`
- Modify: `frontend/index.html`

1. Implement `publish`, `read`, `display`, and `reset` as a browser global and CommonJS module.
2. Load it after `indicator_dynamics.js` and before `app.js`/`overlays.js`.
3. Add the controller-style read-only indicator modal with tag, PV, unit, and close controls.
4. Run the registry tests and confirm they pass.

## Task 3: Publish and open legacy indicator values

**Files:**

- Modify: `frontend/app.js`

1. Publish each `setPI` value after FOPDT sampling, together with the resolved tag and unit.
2. Store the resolved tag on each legacy `.pi` element.
3. Route legacy non-controller clicks to the generic indicator modal while retaining dedicated SIC routes.
4. Keep an open indicator modal synchronized on every simulation packet.

## Task 4: Publish and open overlay indicator values

**Files:**

- Modify: `frontend/overlays.js`

1. Publish numeric values after FOPDT sampling and pressure-unit conversion.
2. Publish level-switch text as `ON` or `LOW` without numeric coercion.
3. Route every non-specialized overlay indicator to the generic faceplate.
4. Mark all overlay indicators as faceplate-capable while preserving trend and alarm behavior.

## Task 5: Use the shared PV in controller faceplates

**Files:**

- Modify: `frontend/app.js`

1. Refresh overlays before open faceplates so the registry contains the current simulation sample.
2. Format generic controller PVs through the shared three-decimal formatter and refresh them while open.
3. Apply the shared live PV to PIC-322203, SIC-321950, SIC-321951, and the clicked master-steam controller indicator.
4. Format read-only hand-valve live openings to three decimals without changing their control semantics.

## Task 6: Verify, graph, and commit

**Files:**

- Modify generated Graphify artifacts under `graphify-out/` as produced by the repository workflow.

1. Run `node frontend/test_indicator_faceplate.js` and `node frontend/test_indicator_dynamics.js`.
2. Run `node --check` on every changed JavaScript file and `git diff --check` on the feature paths.
3. Update the frontend knowledge graph and verify generated output.
4. Review the staged diff, confirm unrelated working-tree changes are excluded, and commit with an emoji conventional commit message.
