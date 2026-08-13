# Stream Ripple Transport Implementation Plan

> **Execution:** Use the `executing-plans` skill inline. Project instructions forbid subagents and require completion without approval pauses.

**Goal:** Delay normal-process stream changes between major vessels as conserved packets, then let existing receiver inventories create downstream gradients.

**Architecture:** Add a boot-seeded packet FIFO beside consequence transport. Register five Unit 322-324 liquid routes. Replace each receiver's direct source reads with the arrived packet while leaving each source balance on the departure rate. Generate a reproducible trend-lag workbook and document equations and evidence.

**Tech stack:** Python 3, dataclasses, `collections.deque`, pytest, openpyxl, existing sequential-modular ODE engine

## Constraints

- Preserve unrelated working-tree changes.
- Preserve the 0.1 s simulation step and design fixed point.
- Use the 20 s reduced-order liquid anchor and inverse-flow scaling; do not infer subhour delay from interpolated trend rows.
- Transport the complete component/temperature/heat-capacity packet.
- Keep transmitter FOPDT separate from process transport.

### Task 1: Boot-seeded process transport

**Files:**

- Modify `backend/consequence.py`.
- Modify `backend/test_consequence_transport.py`.

- [ ] Add a failing test that the first process packet appears at the destination immediately at boot.
- [ ] Add a failing test that a later step remains at baseline until dead time and then arrives with flow, temperature, and composition synchronized.
- [ ] Run `python -m pytest backend/test_consequence_transport.py -q` and confirm the new tests fail.
- [ ] Implement `transport_process_packet` with a timestamped zero-order-held FIFO seeded from the initial packet.
- [ ] Run the focused tests and confirm they pass.

### Task 2: Product-train route integration

**Files:**

- Modify `backend/main.py`.
- Create `backend/test_process_transport.py`.

- [ ] Add failing registry tests for the five principal product routes and the `<3600 s` workbook bound.
- [ ] Add a failing dynamic test for delayed 322E001-to-323C003 arrival and receiver response.
- [ ] Run `python -m pytest backend/test_process_transport.py -q` and confirm failure.
- [ ] Add `PROCESS_ROUTES` and `_transport_process` diagnostics.
- [ ] Wire arrived packets into the C003, F004, F010, D002, and 324E001 inlet balances. Keep departure packets in source balances.
- [ ] Run process-transport, consequence-transport, and propagation tests.

### Task 3: Reproducible trend analysis workbook

**Files:**

- Create `tools/analyze_stream_lag.py`.
- Create `docs/analysis/urea_stream_lag_analysis.xlsx`.

- [ ] Read only the hourly measured anchors from both supplied workbooks.
- [ ] Compute gradient correlations by integer-hour lag with overlap counts.
- [ ] Write Summary, Hourly Anchors, Lag Estimates, and Route Parameters sheets.
- [ ] Use formulas for effective line inventory and formula-check columns.
- [ ] Recalculate the workbook with the bundled spreadsheet runtime and inspect formulas and errors.

### Task 4: Mathematical reference and model gaps

**Files:**

- Modify `docs/Urea OTS — As-Built Mathematical Reference.md`.
- Modify `C:/Users/ameel/.codex/skills/chemical-modelling/references/mesh-equations.md`.
- Modify `handoff.md` only if the open pipe-volume gap needs correction.

- [ ] Document the packet FIFO, route law, route table, trend-resolution limit, and receiver time-constant ownership.
- [ ] Record the same equations and source hierarchy in the chemical-model mesh.
- [ ] Retain the open field-pipe-volume gap and identify higher-resolution historian data as the calibration need.

### Task 5: Verification, graph, and commit

- [ ] Run focused pytest suites and the scenario scripts.
- [ ] Run Python compilation and `git diff --check`.
- [ ] Validate workbook formulas and reload calculated values.
- [ ] Update the project knowledge graph without subagents.
- [ ] Read the verification and branch-finishing skills, inspect staged scope, and commit only task files and selected `main.py` hunks.
