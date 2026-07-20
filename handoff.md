# Handoff Summary

## The goal we're working toward
Calibrate the `backend/main.py` state-space process engine against real DCS startup trend data
without violating mass/energy conservation. Immediate front: close the FFIC-329401 desorber-II
steam/feed ratio basis, and finish registering HMI overlay frames onto their baked DCS boxes.

## Current state of the code
* HEAD is `37504eb` on `master`. **Not pushed** — origin still at `b881480`.
* `37504eb` carries: 12 overlay frame nudges on 328-1 / 324-1b, the pending 329xxx rename
  (FIC-326402 -> FIC-329402, FFIC/FIC-328401 -> FFIC/FIC-329401), the FFIC ratio rebase onto
  stream 744, the FIC-328402 volumetric (m3/h) conversion, the CLAUDE.md rewrite, and the
  handoff.md move from `backend/` to the repo root.
* Rename verified coherent: overlay binds, telemetry keys, State attrs and `R323_CTRL_MODES`
  all carry the new names, zero stale references in `backend/main.py` or `frontend/`.
* **The pin gate has NOT been run against `37504eb`.** See blocker below.
* `launch.bat` has an unrelated uncommitted change (adds `pip install -r requirements.txt`).
  Left unstaged. `backend/requirements.txt` exists and the path resolves.

## HARD BLOCKER — no interpreter on this machine
There is no Python and no Node installed. `backend/main.py`, the pytest suite, and
`scratchpad/regress.py` + `scratchpad/pindiff.py` **cannot be run here**. Every backend
conclusion below is static analysis only. `scratchpad/pin_now.json` matches `golden_pin.json`
exactly but predates the current `main.py` (pin 19:26, main.py 20:38), so it proves nothing
about `37504eb`. Re-gate on a machine with Python before trusting the commit.

## Open decision — FFIC-329401 ratio basis (needs your ruling)
The rebase moved the denominator from stream 738 to stream 744. PFD says **744 is not the
desorber-II feed**: it is the 44 C / 1 bar Comp-II wash. The C004 feed is **stream 749**
(34062 kg/h, 148 C, 16.6 bar) — `main.py`'s own comment says so at `R328_C004_M749_DES`.

PFD 1750 MTPD, streams as read:

| stream | desc | kg/h | m3/h | rho | T | P |
|---|---|---|---|---|---|---|
| 735 | Amm. Water | 31114 | 31.4 | 992.4 | 56 | 4.1 |
| 738 | Amm. Water | 31114 | 32.4 | 959.7 | 114 | 3.5 |
| 744 | Amm. Water | 31478 | 31.4 | 1002 | 44 | 1 |
| 749 | Amm. Water | 34062 | 36.9 | 924.1 | 148 | 16.6 |
| 931 | LP Steam | 6495 | 3097.2 | 2.1 | 145 | 3.9 |

The baked DCS panel on screen 328-1 reads `SP 0.169 T/M3 / MV 0.168 T/M3`. Candidate bases,
as 931 in t/h over feed in m3/h:

* **749 -> 6.495/36.9 = 0.176 T/M3** — 4 % off the baked snapshot (which is off-design)
* 744 -> 0.2069 — 22 % off
* 738 -> 0.2004 — 19 % off

So the physical basis is almost certainly **931(t/h) / 749(m3/h), in T/M3**. The commit also
regressed the overlay unit from `T/M3` to `KG/KG`, which now contradicts the baked `T/M3` text
sitting uncovered beside the box.

Fix is mechanically easy — `m_749` is already computed upstream of the ratio line (it feeds
`T749_raw`) and does not depend on `m_931`, so there is no algebraic loop and no `_prev` lag is
needed. It was NOT applied because it changes physics constants and cannot be pin-gated here.

## Naming defect (physics is fine)
`RHO_735_KGM3 = 31478 / 31.4 = 1002.48` reproduces the PFD **stream-744** density (1002) to
0.05 %. It is not a fabricated constant. But it is 744's density, not 735's (992.4), and
FIC-328402 carries 31478 kg/h — i.e. stream 744. Streams 735 and 744 both happen to be
31.4 m3/h, which is what hid the mislabel. Rename to `RHO_744_KGM3` and fix the surrounding
comments and the overlay note when the ratio work is done (same pin-gate cycle).

## Files actively edited
* `frontend/overlays.js` (committed)
* `handoff.md`, `CLAUDE.md` (committed)
* `backend/main.py` (committed, UNGATED)
* Verification tooling lives in the session scratchpad, not the repo: `boxlib.ps1`
  (baked-DCS-box locator, .NET System.Drawing), `audit_overlay.ps1`, `crop.ps1`, `rowprof.ps1`,
  `sheet.ps1`. Rebuild if needed — they are not tracked.

## Everything tried that failed
* Running anything Python: no interpreter. Not a PATH problem — no install exists.
* `python`/`python3` on PATH resolve to the Microsoft Store alias stub, which exits non-zero.
* Judging overlay placement from the whole black blob centroid: the baked DCS indicator is a
  flag (wide value BAR + narrower TAB below), so the centroid sits ~5 px low. Isolate the BAR.
* Isolating the bar by "longest contiguous run of rows at >=90 % of max width": the green value
  text erodes row extent and truncates the run, landing on the box's top edge. Use first..last
  row at >=60 % of max width instead — the tab is ~40 % of bar width, so 60 % separates cleanly.
* Committing only `frontend/` to avoid the ungated `main.py`: impossible. The overlay binds and
  the backend rename are one atomic change; a frontend-only commit leaves dead binds.
* The audit workflow (52 agents): hit the session usage limit at 14/52 done. 38 refuters died,
  so most raised findings were never adversarially checked. Re-run after reset if needed.
* Making HIC/HV-329606 live: no motive-steam physics exists and a live draw would double-count
  a golden-pin key (the 1400 kg/h is already inside lumped `M_USERS_LP`).
* Deriving `MV_DES` by subtraction and `PHIV` by division: breaks the PIC-323203 fixed point by
  round-off. `PHIV` must be defined first.
* Judging the D011 balance from telemetry `m_kgh`: rounds to 1 dp, manufacturing a phantom
  steady residual. Use dM/dt.
* Short horizons (600/1200/1800 s) to demand Comp I "settle": Comp I's own tau is 16,098 s.
* `ff718_perturb.py`: obsolete, kicks the wrong leg. Superseded by `dyn718r.py`.

## Next steps
1. Get to a machine with Python. Run `scratchpad/regress.py` then `scratchpad/pindiff.py` against
   `37504eb`. Expected `leaves: 25  keys: 15  diffs: 0`. Nothing else should be trusted first.
2. Rule on the FFIC-329401 ratio basis above (749 in T/M3 is the evidenced answer). Apply with
   the `RHO_744_KGM3` rename and the overlay unit restored to `T/M3` in one gated change.
3. Push `master` to origin once gated.
4. Unresolved overlay registration, measured but NOT fixed:
   * `screen-323-1` — all 24 overlays share a uniform `dY ~ +21 px`. Whole-screen vertical
     registration error, not per-element drift.
   * `screen-321-1` — progressive `dY` from -2.6 at y=178 to -19.5 at y=587, i.e. a ~4 % y-scale
     error; its header comment claims native 1287x612 but the PNG is 1355x644.
   * Both may be masked in the live HMI by drag positions in localStorage `ots_ov_pos_v3`, which
     override the seed coords. Confirm against the running HMI before editing the seed.
   * `FFIC-329401` and `TIC-328012` sit on two-box SP/MV ratio panels; which row the live PV
     should cover is a design decision, left alone.
5. Unverified audit findings whose refuters died with the session limit: `overlays.js:313`
   FV-326402 not renamed to FV-329402 (main.py agrees with the current spelling, so verify
   against the P&ID before touching), and `Master_PID_Tuning_Constants.md:618` still naming the
   loops by pre-rename tags.
6. Decide whether to build the ejector motive-steam model.
7. Still blocked on you: sprint items 7, 22, 25, and item 3a (#17) pending a 328D003 level
   controller.
