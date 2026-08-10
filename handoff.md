# Handoff — Open Gaps

Running list of *currently open* modelling gaps only. Delete an entry when closed.

## G-WASH-1 — SM-port modules diverge from the live function path
- **Node:** `backend/core/scrubber.py` `Scrubber322E003.solve()`, `backend/core/ejector.py`
  `Ejector322F001`, `backend/core/lp.py` (LP stage, SIC-323901 speed loop).
- **Missing:** live-path physics that the `core/` SM-port modules do not carry —
  (a) the LP/MP recycle-wash coupling (Obs 1–6: `wash_scale`, `q_wash_sensible`, off-gas
  direct-contact cooling, live ejector suction temp);
  (b) the SIC-323901 direct VFD speed-follower — `core/lp.py:431-432` still runs the old
  degenerate self-referential I-PD (`rpm_pv = lag(SIC.op)` then `_ctrl_ipd`) that the live
  `main.py` path replaced.
- **Impact:** none on the running simulation — nothing imports `core.lp` and `_sm_flowsheet`
  is assembled but never `.solve()`d, so all `core/` unit modules are dead scaffolding.
  Divergence matters only if the SM port is ever activated for audits/tests.
- **Tried:** grep confirms no `_sm_flowsheet.solve/run` in `step_sim` and no live import of
  `core.lp`.
- **To close:** mirror the live-path models into the `core/` modules (or delete the dead
  SM-port if it will not be used).

## G-WASH-2 — Wash-coupling gains are calibrated, not datasheet-derived
- **Node:** `backend/main.py` constants `SCRUB_WASH_SINK_KW` (2500 kW), `SYN_P_WASH_COLLAPSE_GAIN`
  (8000 bar/h), `SCRUB_OFFGAS_WASH_COOLING` (15 °C), `SCRUB_CARB_ABS_GAIN` (0.15 kmol/kmol).
- **Missing:** these set the *magnitude* of Obs 2/3/4/5 response to a wash step. The direction
  is datasheet-correct (`References/322E003 HP Scrubber Describtion.md`), but the numeric gains
  are engineering estimates, not backed by a plant step-test or a rigorous two-film absorption
  model (§5 of the datasheet: `K_G`, enhancement factor `E`, Henry constants).
- **Impact:** transient/steady magnitudes of the six responses may be off; signs and pins are
  correct.
- **To close:** need plant step-test data (wash-flow bump → TT-322002/329125/322011/322012,
  PT-329201 deltas) or the rigorous distributed-parameter absorption model with real VLE/kinetics.
