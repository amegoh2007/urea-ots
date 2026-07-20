# Handoff Summary

## The goal we're working toward
Calibrate the `backend/main.py` state-space process engine against real DCS startup trend data without violating mass/energy conservation. The immediate goals are missing-tag placement (TT-328006 on 328-1 and HIC/HV-329606 on 324-1B) and closing open stream contradictions using strict PFD tables.

## Current state of the code
* Six-pillar audit CLOSED, all gaps remediated, committed and pushed. Branch `master` is level with origin.
* TT-328006 placed live. HIC/HV-329606 placed as white frames (unmodelled).
* FIC-328405 / FIC-323402 strict PFD stream values have been ruled on and closed. Limit-cycle closure reconciled.
* All gates are green (Pin gate: leaves 25, keys 15, diffs 0).

## Files you're actively editing
* `frontend/overlays.js`
* `backend/handoff.md`
* `CLAUDE.md`
* `backend/main.py`
* Active scratchpads: `dyn718r.py` (tracked acceptance test) and `probe_d011_bal.py` (probe).

## Everything you've tried that failed
* Making HIC/HV-329606 live: Fails because no motive-steam physics exists and a live draw would double-count a golden-pin key.
* Deriving `MV_DES` by subtraction and `PHIV` by division: Breaks the PIC-323203 fixed point by round-off. `PHIV` must be defined first.
* Judging the D011 balance from telemetry `m_kgh`: Rounds to 1 dp, manufacturing a phantom steady residual. Use dM/dt instead.
* Using short horizons (600s/1200s/1800s) to demand Comp I "settle": Fails because Comp I's own tau is 16,098 s.
* Using `ff718_perturb.py`: Now obsolete as it kicks the wrong leg. Superseded by `dyn718r.py`.
* Baseline extraction via `git archive HEAD backend`: Crashes on `app.mount`.

## The next step you'd take
* Verify the three frames land correctly against the screenshots on the running HMI and drag-nudge if needed.
* Decide whether to build the ejector motive-steam model.
* Await user definitions for sprint items 7, 22, and 25 (currently blocked).
* Address item 3a (#17) which is still BLOCKED on a 328D003 level controller.
