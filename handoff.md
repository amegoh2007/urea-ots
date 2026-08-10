# Handoff — Open Gaps

Running list of *currently open* modelling gaps only. Delete an entry when closed.


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
