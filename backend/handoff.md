# Handoff — Urea OTS synthesis-loop calibration

_Last updated: 2026-07-20 (session 13) · branch `master` · HEAD `0d3289f` (pushed, level with `origin/master`) · 718A/718B bang-bang limit cycle CLOSED + repo recovery + 328E021 hot side made live + sprint items 16/23/24 CLOSED and 27 dead faceplates rewired (session 13, logged below)_

## Session 13c (2026-07-20) — HMI tranche: sprint items 16 / 23 / 24 closed · HEAD `0d3289f` (pushed)

**No engine edit.** Both commits touch `frontend/` only, so `_PIN_SRC_FILES` did not rehash — the gate was
still re-run after each: **`leaves: 25  keys: 15  diffs: 0`**.

**Where the sprint list actually lives.** The 25-item PFD gap list is *inside this file* (session-9 block,
L697+), not a separate doc. Domain split at L704–707. Items **1, 23, 24** carry full surviving text at
L779–807; tranche map at L1096–1107.

**Item 24 — VERIFIED ALREADY LANDED (`af5fd2c`), not re-done.** Both halves present in `main.py`:
binding half `s.cpl_flow_kgh` (init L2736) → telemetry `cpl_kgh` (L4526) → handler `cpl_set` (L4994,
clamped `0 … 2·A328_CPL_DES`); anchor half `A328_CPL_DES = 1750.0`, `A328_CPL_T = 46.0` (L644) with the
900 kg/h conflict resolved in favour of 1750. Corroborated by the pin itself:
$$ A328\_ABS\_DES = A328\_M756\_DES - A328\_M755\_DES - A328\_CPL\_DES = 130 $$
matching the pinned `A328_GCB_DES − A328_VENT_DES = 130`.

**Item 23 — VERIFIED ALREADY LANDED (resolution R2), not re-done.** `main.py:4033–4054`: LV-324501**A**
is the dead leg (`lva_stroke = 0.0`), LV-324501**B** carries the melt
(`lvb_stroke = clamp(lic501_op, 0, 100)`, `m_fwd = lvb_stroke/100 · R324_LVB_SPAN`), and the underflow is
re-pointed onto the *active* valve (`m_uf = uf_ratio · m_fwd`). Telemetry `LV_324501A` / `LV_324501B` /
`melt_fwd_th` all emitted.

**Item 16 (Tranche A3) — CLOSED. `5b77e91`, `frontend/overlays.js`, +3/−3.** The session-12 volumetric
migration left three loops rendering m³/h under a `T/H` label. Proof (`scratchpad/volfp.py`, 20 000-tick
settle): `FIC_323401 pv 0.83 == vol_m3h 0.83` (`m_kgh 823.0`), `FIC_323418 pv 3.34 == vol_m3h 3.34`
(`m_kgh 3560.4`), `FIC_328405 pv 3.34 == vol_m3h 3.34` (`m_kgh 3560.3`). Fix = `u: 'T/H' → 'M3/H'` plus
corrected notes (FIC-323418's stale "64.2 t/h" text killed).
**Deliberate: the `bind` stayed on `.pv`, NOT re-pointed to `.vol_m3h`.** `app.js:472` derives a loop's
authoritative `{pv,sp,op,mode}` block *only* when the bind ends in `.pv`
(`gp(window.OTS_LAST||{}, o.bind.slice(0,-3))`); re-pointing would have silently demoted those three
faceplates to the localStorage fallback store. Change the label, never the bind.

**Systemic HMI defect found in passing — FIXED. `0d3289f`, `frontend/app.js` + new tracked test, +81/−2.**
27 of the 36 loops in `main.py`'s `R323_CTRL_MODES` whitelist (L4842–4873) were **unreachable from the
faceplate**: `app.js` only routed 9 bespoke tags via its `T` map and dumped everything else on
`controller_set` (`main.py:4967`), whose `getattr(s, "FIC-323401")` misses on the dash tag and **silently
discards every mode/SP/OP write** — faceplate looked alive, plant never moved. Fix makes the frontend a
router mirroring the backend whitelist (`const R323 = new Set([...36 tags...])` → `r323_ctrl_set`); the
backend stays sole authority (it re-checks the whitelist *and* the per-loop legal mode tuple), so an
over-broad frontend set is inert, never unsafe.

**Acceptance — `scratchpad/fpwire.py` (new, tracked), FAILURES 0.** Parses the `T` map and `R323` set
straight out of `app.js` and drives `main.handle_cmd()` as the websocket would:
```
gate 1 - routing   : 36 whitelisted, 36 routed, 0 unreachable  OK
gate 2 - liveness  : 36/36 loops take a MAN op write via r323_ctrl_set  OK
           control : the OLD controller_set path is a no-op for these tags (op stayed 50.0)  OK
gate 3 - guard     : MAN-only spares ['SIC-323902', 'FIC-328406'] reject AUTO  OK

FAILURES 0
```

**Failed attempts (session 13c):** `fpwire.py` gate 2 first reported `34/36 FAIL ['TIC-323007',
'TIC-323012']` — probe bug, not engine bug: both loops command a chest **pressure**
(`op_hi = R323_P_STEAM_SUP` < 12), so the hard-coded op target 12.0 clamped. Fixed by aiming
`lo + 0.25·(hi − lo)` inside each loop's own span. Also searched `docs/urea-project-conversation.md` for
sprint items 7/8/9/22/25 — only the OLD unit-321 numbering is there (item 7 = pump discharge ΔT, item 8 =
AUTO SP as RPM, item 9 = 321D003 mass balance), a different scheme. Do not re-grep.

**Active files (session 13c):** `frontend/overlays.js`, `frontend/app.js`, `backend/handoff.md` (this
block). New tracked test `scratchpad/fpwire.py`; new untracked probe `scratchpad/volfp.py`.

**Next steps (session 13c) — the backend batch is now out of actionable items:**
- Items **7, 8, 9, 22, 25 BLOCKED — no surviving definition** anywhere in the repo, and the harness task
  list is empty. The user must supply the item text (or point at the source doc) before any of them opens.
- Item **3a (#17) still BLOCKED** — needs a 328D003 level controller cascading into FIC-328402; the
  `avail`/derate escape hatch is empirically disproven, do not re-attempt.
- Items **16, 19, 21, 23, 24 CLOSED.** Remaining openable-with-text: 1, 2, 3b–3d, 5, 6, 10–15, 17, 18, 20.

## Session 13 (2026-07-20) — limit-cycle closure reconciled + repo recovery · HEAD `f48dd27` (pushed)

**No engine edit this session.** Session 12's handoff was stale by one substantive commit; this block
reconciles it and re-verifies HEAD from a clean boot.

**Reconciliation — `f48dd27` closes the session-12 Scope-Lock item:**
`fix(R3232): kill FIC-328405/FIC-323418 718A/718B bang-bang limit cycle` (`backend/main.py`, +30/−3).
Two changes, both inside the 718 demand split:
1. **Feed-forward from DEMAND, not live PV.** In AUTO/CAS the coordinator now takes
   `m718B_ff = s.FIC_323418["sp"] * RHO_718_KGM3` (MAN falls back to live `m_718B`, which is op-fixed
   and non-oscillating), so `cas718A_raw = max(m718_dmd − m718B_ff, 0)` no longer closes a loop through
   718B's own lagged measurement.
2. **Measurement filter `tau_s` 5 → 45 s on both legs** (`F_323418`, `F_328405`). `Kc`/`Ti` byte-identical.
   Stability law: 2-tick growth factor is `Kc·a·g`, `a = dt/(tau_s+dt)`, `g = (design/op_des)/ρ = 0.0669`.
   Design tune at `tau_s=5 s`: `426·(1/6)·0.0669 = 4.75 ≫ 1` → bang-bang. At `tau_s=45 s`,
   `a: 0.167 → 0.0217` → `Kc·a·g = 0.62 < 1` → flat. Filter DC gain is 1, so the steady-state 718 split
   is invariant in `tau_s` — fixed point (and therefore the pin) untouched. 45 s is still 28× faster than
   the 1257 s level loop, so the cascade reference needs no extra filter — 718A tracks true level demand.

**Fresh verification at HEAD `f48dd27` (clean boot, both green):**
- Pin gate (two-step `regress.py` → `pindiff.py`): **`leaves: 25  keys: 15  diffs: 0`**.
- `scratchpad/ff718.py`: ticks 50–59 all `718A_pv 3.3431 / 718B_pv 3.3431 m³/h` = `3560.36 kg/h` each,
  sum `7120.73 kg/h` (design 718 split, conservation intact).
  `max |dPV_718A| over ticks 41-59 (limit-cycle amplitude): 0.000000 m3/h` → **BANG-BANG DEAD**.

**Operational lesson — `.git/config` NUL-byte corruption.** Every git command failed with
`fatal: bad config line 18 in file .git/config`; line 18 held ~430 `\x00` bytes (filesystem/crash
corruption, NOT whitespace — a `l.strip()==''` filter does not remove it). Fix: rewrite `.git/config`
from scratch with the known-good `[core]/[user]/[remote "origin"]/[branch "master"]` content, then
`git fetch` to confirm. `config.bak` was equally corrupt and was deleted. Repo healthy after: `master`
level with `origin/master`, working tree clean apart from the ~40 known untracked paths (must stay
untracked — **stage selectively by path, never `git add -A`**).

**Item — 328E021 HOT side made live (the session-8 "obvious next 328 item", now CLOSED).**
The mirror of item 3c, on stream 749: `m_749 = m_747  # via 328E021 (148 °C)` fed `sens_c004` off the
frozen `R328_C004_T749 = 148.0`, so the 328C004 energy balance could not see the hydrolyser at all.

- **Conservation form, NOT a second effectiveness.** A hot-side ε would let 328E021 create/destroy
  energy off-design (the two ε's only close at the design flows). The duty the hot stream gives up is
  the duty the cold side took plus the shell loss:
  $$ m_{749}\,c_p\,(T_{c003}-T_{749}) \;=\; m_{746}\,c_p\,(T_{746}-T_{c002}) \;+\; Q_{loss} $$
  $$ T_{749} \;=\; T_{c003} \;-\; \frac{m_{746}\,(T_{746}-T_{c002}) \;+\; \Delta T_{loss}}{m_{749}},
     \qquad \Delta T_{loss} \equiv \frac{3600\,Q_{loss}}{c_p} $$
- **`R328_E021_LOSS_DT` back-solved from the plant's own design state, no fabricated constant:**
  $$ \Delta T_{loss} = 34062\cdot(200-148) \;-\; 33769\cdot(190-139) = 1771224 - 1722219 = 49005\ \mathrm{kg\,K/h} $$
  $$ Q_{loss} = \frac{49005}{3600}\cdot 4.0 = 54.45\ \mathrm{kW} \;\approx\; \texttt{R328\_E021\_LOSS} = 54.4\ \mathrm{kW} $$
  — it reconstructs the datasheet loss, exactly as `R328_E021_EPS_T` reconstructed the datasheet ε.
- **Bit-exact at design by construction.** Every term is an integer-valued float, so
  $200-(33769\cdot 51+49005)/34062 = 200-52 = 148.0$ **exactly** (`scratchpad/e021h.py`: `exact: True`
  for `T_746`, `T_749`, and the composed pair) ⇒ swapping `sens_c004` onto the live value cannot move
  the pin. Gate re-run: **`leaves: 25  keys: 15  diffs: 0`**.
- **Pinch clamp, unlike 3c.** 3c needed none (convex combination); here the raw balance diverges as
  `m_749 → 0`, so `T_749` is bounded by the two live inlet temps — a counter-current interchanger
  cannot cool the hot stream past the cold-side inlet. Inactive at design (139 < 148 < 200) ⇒ exactness
  preserved.
- **`R328_C004_T749 = 148.0` RETAINED** — still the design datum behind `R328_C004_LAM750` and the loss
  anchor. No live path reads it (grep-confirmed: L713 def, L717 LAM750, L912 loss anchor, comment).
- **No display bind:** screen 328-1 has no TT element on stream 749 (grep `TT-328` in `overlays.js`),
  so no telemetry key was invented. This is a §1 physics fix, not a display gap.
- **Acceptance — `scratchpad/dyn749.py`, FAILURES 0:**
  gate 1 design hold (6000 s) TT-328C003 200.0 / TT-328009 190.0 / TT-328005 143.0 / TT-328004 140.0 /
  TT-328007 139.0; gate 2 dynamism, hydrolyser clamped 200 → 210 °C ⇒ `dT_c004 = 1.7092` vs closed form
  $1-m_{746}\varepsilon_T/m_{749} = 0.17113$ ⇒ 1.7113 (the frozen constant gave **0**); gate 3 pinch
  guard, LIC-328505 driven shut ⇒ C004 stays finite (346.8 °C, 8527 kg — steam-on/draw-off runaway, the
  pre-existing behaviour, no NaN/inf from the divergent balance).

**Active files (session 13):** `backend/main.py` (328E021 hot side), `backend/handoff.md` (this block),
`.git/config` (repaired). New tracked acceptance tests: `scratchpad/e021h.py`, `scratchpad/dyn749.py`.
Re-run, not modified: `scratchpad/regress.py`, `scratchpad/pindiff.py`, `scratchpad/golden_pin.json`,
`scratchpad/ff718.py`.

**Failed attempts (session 13):** repairing `.git/config` by filtering blank lines
(`[l for l in lines if l.strip()]`) — no-op, because `\x00` is not whitespace. Full rewrite required.

**Next steps (unchanged from session 12 except the closure above):**
- Backend tranche batch, each rehashing the pin ⇒ re-gate to `25/15/0` before commit:
  items **3a, 7, 8, 9, 17, 18, 22, 23, 24 (binding half only), 25**. Item 16 (Tranche A3, m³/h
  migration) done in session 12.
- ~~Before items 19/21: grep the `main.py` 324 section for `PY_324201` / `AY_324701`.~~ **DONE
  (session 13) — items 19/21 are ALREADY LANDED, do not re-do.** `conc_infer_324()` exists at
  `main.py:66` (isobaric VLE at the vacuum separator, water activity $a_w = P/p^{sat}_w(T)$, design
  $\gamma$ back-solved from the plant's own hard design state, frozen-$\gamma$ inversion
  $x_w^{live} = x_w^{des}\,(a_w^{live}/a_w^{des})$, emitted in anchored-correction form) and both
  readouts are wired: `PY_324201` (`main.py:4541`), `AY_324701` (`main.py:4572`).
- Item 3a (#17) **blocked**: needs a 328D003 level controller cascading into FIC-328402. The
  `avail`/derate escape hatch is empirically disproven — do not re-attempt.
- **OPEN:** OEM stream 793 for FIC-328405 is "Amm. Water" (ρ 992.4, mass 0 @100 % load), conflicting
  with the loop's carbamate-718A physics (ρ 1065, 3560.4 kg/h). Re-anchor deferred pending explicit
  direction (would disturb the 323D011 mass balance).
- **FLAG (`1eb48ca`):** FIC-323402 leg `R3232_E011_M402_DES = 2931 kg/h` ≈ 1.9× PFD stream-791
  (1534 kg/h). Reconciliation deferred — pin-breaking.

## Session 12 (2026-07-19) — volumetric migration + steam FT telemetry · HEAD `f59c313` (pushed)

**Done, verified, committed+pushed (`f59c313`):**
- Structural volumetric migration of all three liquid loops (FIC-323401 / -323405 / -323418).
  `_fic_flow` gains `rho=` param; inside `_fic_flow`, BEFORE `_ctrl_ipd`: `pv/=rho`, `cas_sp/=rho`,
  control on m³/h, **return stays kg/h** → steady-state mass balance byte-identical.
  Retune `Kc_vol=Kc_mass·ρ`, `Ti` unchanged, `sp_hi/=ρ` (closed-loop coeff `1−Kc·a·g` invariant).
  ρ: 401=992.4, 718A/718B=1065. Export adds `vol_m3h`+`m_kgh`, pv/sp→2dp.
- Steam FT dynamic telemetry (OEM 1750 MTPD 100% load, PFD-anchored):
  `FT-329403 → 60.85 t/h`, `FT-329407 → 16.71 t/h`. Bound in `frontend/overlays.js` (already published).
- **Pin gate: keys 15 / leaves 25 / diffs 0** — core HMB untouched.
- Settle verified: 323401 0.83 m³/h/823 kg/h · 323418 3.34 m³/h/3560.4 kg/h · FT 60.85 / 16.71 t/h.

**KNOWN / OUT-OF-SCOPE at the time (Scope-Lock — NOT silently fixed) — since CLOSED by `f48dd27`,
see session 13 above:** FIC-328405 (was FIC-323405, renamed —
see below) CAS loop 2-tick bang-bang limit cycle. Proven **pre-existing at HEAD**: HEAD mass loop
cycles pv 3390.82↔3729.90 kg/h; migrated cycles 3.1839↔3.5023 m³/h (== HEAD/ρ exactly) → migration is
a faithful rescale, did not introduce it. Root cause: 718A/718B shared-demand split
`cas_sp=max(m718_dmd−m_718B,0)` fighting the 718B loop — control-architecture defect independent of
this task. Needs separate retune/re-architecture.

**Tag correction (`3df375e`, pushed):** loop **FIC-323405 → FIC-328405** (also FV-323405 → FV-328405).
The leg terminates in unit 328 (328E004/328D001) so the 328- prefix is the correct OEM unit. Pure
identifier/tag renumber across `backend/main.py` (dict, exports, mode table, tlag key F_323405→F_328405)
and `frontend/overlays.js` (tags + `LPCC_3232.C005.FIC_328405` bind paths). Pin 15/25/0, physics
untouched. **OPEN:** OEM stream 793 for this tag is "Amm. Water" (ρ 992.4, mass 0 @100% load), which
conflicts with the loop's carbamate-718A physics (ρ 1065, 3560.4 kg/h). Density/service re-anchor
deferred pending explicit direction (would disturb the 323D011 mass balance).

## Goal

Calibrate the `backend/main.py` state-space process engine against real DCS startup
trend data so its dynamic response matches the plant, **without ever violating mass or
energy conservation**. Two anchor datasets drive this:

1. **Pump volumetric efficiency** — from the 321P002 NH₃-pump rpm→flow field curve.
2. **Feed transport dead time** — from the 03-06-2025 synthesis-loop pressurization trend.

Hard constraints (standing user directives):
- **100% conservation** — mass/energy never created, destroyed, or decoupled to dodge stiffness.
- **Sourcing law** — thermodynamic equations from verified sources; no fabricated constants.
- **Design bit-exactness** — the pinned design steady state must stay bit-identical after any edit.
- **Autonomous push** — commit and push to `https://github.com/amegoh2007/urea-ots.git` once a task is
  complete and verified; do not halt for approval. This **reverses** the former "push only on explicit
  request" rule, superseded by `CLAUDE.md` §3 (Remote Backup) as of commit `e300f17`.
- **Mandatory handoff** — `CLAUDE.md` §5 requires this file be updated at the end of every session with
  the five sections: Goal, Current State, Active Files, Failed Attempts, Next Steps.

## Current state — six-pillar audit CLOSED, all gaps remediated, committed and pushed

Nothing is mid-edit. The feature branch is **level with origin** at `ff41027` and now tracks
`origin/fix/reactor-level-drain-and-vent-coupling`. All 21 audit tasks closed.

| Commit | Pushed | What |
|--------|--------|------|
| `c7c898a` | yes | Pump η_v calibrated 0.95 → 0.980 (matches field curve) |
| `487d4a1` | yes | Feed transport dead time `FEED_TD_S = 345 s` injected on feed tears + report |
| `8182420` | yes | Prior session handoff doc |
| `e3ee4a6` | yes | Fix MemoryError in `_delay` under variable sub-step dt |
| `aec3160` | yes | 329-1 steam-drum level loops LIC/LV-329502/503/504 wired to sim (session 5) |
| `411080c` | yes | Unit 324 two-stage vacuum evaporation + DCS overlays 324-1 / 324-1b (session 6) |
| `7b384dc` | yes | **Six-pillar audit gap closure** — ejector suction sign, gas-phase couplings, indicator binds (this session) |
| `ff41027` | yes | **Audit artifacts** — pin gate + verification instruments + audit report (this session) |

### This session (2026-07-03, session 2) — 28-06-2025 DCS startup dataset

Full 10-target empirical extraction on `Urea_Startup_28-06-2025_Trends.xlsx`. Sheet is
self-labelled SYNTHETIC (30 s linear interp between hourly measured points); knot recovery
found **exactly 7 true hourly anchors** (10:01→16:01) — anchors-only analysis, same
honest-resolution rules as 03-06. Full findings:
`backend/reports/dcs_anchor_dynamics_2025-06-28.md`.

Headlines:
- **Pump map 3rd confirmation**: 0.34150 t/h/rpm through-origin vs committed **field** fit 0.34174
  (−0.07 %). No edit. NB engine mass map at design ρ is 0.33667 t/h/rpm (no 0.34174 in code);
  +1.4 % field gap = ρ-basis 613.5/604.8 (dcs_tuning_parameters §4.3a); 28-06 warm feed at same
  slope ⇒ FY-321401 likely fixed-ρ DCS compensation (see 28-06 report §T2 engine-side note).
- **PT-329201 FOPTD**: τ = 2246±500 s, outside band [2884,4055] — under-resolved (1st anchor
  at 76 % of span, t_d ±700 s trade-off) + τ is trajectory-dependent (faster load ramp).
  **Band unchanged**, stays tied to 03-06 scenario.
- **LIC-322501 direct action corroborated** on independent dataset (valve shut while level
  0.2→57 %, opens above SP) → 03-06 MV=102.8 % artifact verdict stands.
- **The ONE model edit**: `LV322501_OPEN_DES` 82.0 → **46.1 %** (main.py ~L335). Field: LV held
  45.4 % stable at 97 % load; dP+load-corrected → 46.1 (cross-checks 46.4/44.2). Datasheet 82 %
  stroke over-stated travel ~1.8× for installed flashing service. **Pin-safe ratio form**
  (seed + normalizer only) — A/B probe: boot pins bit-identical, hold pins ≤7e-7 %, no limit
  cycle at 1.78× loop gain.
- **Not edited** (would fabricate constants): HV-322602 (74 vs 60, operator-moved), HIC-322604
  (50 vs 80), HIC-322605 (60 vs 49, still ramping), TV-329005 (50 vs 32, TIC SP off-design 88 °C).
- **Not extractable at 3600 s spacing** (10-target requests): exact reactor dead times
  (brackets ≤3600 s only), all slew rates (lower bounds), SV-321950/951 + HV-322603 + TT-322002
  + PT-329206 + TT-322004 (tags absent), T3/T5/T9/T10 gains (confounded, sign-unstable secants).
- **Tag correction (user, 2026-07-03): LT-322504 = REACTOR level, not HPCC** (HPCC = LT-322E002,
  absent from workbook → T7 HPCC lag not extractable). LT-322504-3 fill = reactor: onset ≤3600 s,
  plateau 99.94 % at 92–97 % load vs model N7 NLL pin 80 % — documented, NOT edited (single
  transmitter, span/zero config ambiguity vs datasheet; report §3-T7).

## 2026-07-03 (later): sim-vs-28-06 verification + contradiction gap-closure (task 4)

**Verification (4-gate probe, scratchpad `verify_sim_vs_2806.py`): 4/4 PASS.**
- A design hold 600 s: all pins exact (LV 46.0994, strip 50.0, P 140.7, CO2 54.618, pump 127.0131).
- B 97 % load: LV settles 44.85 % (field 45.4, band [44.2,46.4]); drain-law self-consistency exact:
  op = 46.1×0.97512/1.00231 = 44.85.
- C pump map: engine internally exact (1e-16); ρ-basis 613.5/604.8 closes field gap to +0.005 %.
- D LIC-322501 direct action signs correct (−4.2/+8.3 % on ∓5 % level steps).

**Gap-closure research (report §8, 28-06 report). Register C1–C5, all resolved:**
- **C1 pump map CLOSED**: NIST compressed-liquid isotherm → `NH3_RHO=604.8` = ρ(25 °C, ~29 bar a)
  at pump suction — validated, not an error. Live-ρ falsified: 28-06 warm feed (T̄≈27.6 °C) predicts
  slope −2.1 % if FY-321401 tracked density; observed −0.07 % ⇒ **fixed-constant DCS compute tag**
  (ISA-5.1 letter Y). η_v fit degeneracy flagged: only η_v·ρ_cfg = 601.6 kg/m³ constrained;
  committed (0.980, 613.9) is one solution — conservation-neutral. Caveat comments added at
  `NH3_RHO` / `PUMP_ETA_V` in main.py (comment-only; Gate-A probe re-run post-edit: bit-exact).
- **C2 reactor level — CLOSED session 3 (user directive)**: 28-06 window 15:23–16:01 declared
  steady state. LT-322504-3 = 99.94 dead flat at load 95–97 %, HIC-322605 = 48.05. Post-Task-5
  engine reproduces it emergently: L_eq = 20·0.96·(60/48.05) = 23.98 m > top tap 20.3 m ⇒ LT
  clamps 100.0 (probe: LT 100.000 by 1800 s, head 23.36 m @15000 s, LV op 43.87 vs field 44.32).
  Verdict = liquid-full above top tap under field lineup; NLL 80 % stays the DESIGN point; no edit.
  Report §8-C2 + §9.3. (Earlier 29-06 re-export request moot.)
- **C3 lineup deltas CLOSED**: operator inputs, not equations.
- **C4 P_syn CLOSED**: PT-329201 in bar g ⇒ 14:01 peak 139.6 barg = 140.6 bara ≈ design 140.7;
  16:01 easing follows PIC SP (operator causality), sim floats on vent capacity. No edit.
- **C5 N/C→T CLOSED**: audit 1a upper range reproduces field-negative gain (TT-322010
  186.6→182.7 over AT701 3.08→4.01); radiometric N/C meter span 2.6–3.4 (UreaKnowHow 2024)
  brackets design 3.0, field AY rides top of span.

No numeric edit met the sourcing bar (validated / degenerate / design-doc-sourced / operator
input). Design steady state bit-exact by construction + probe.

### The bug fixed this session (`e3ee4a6`)

**Symptom (user report):** desktop shortcut "Start Urea Simulation" not starting the software.

**Root cause:** launcher chain is fine — 3 desktop `.lnk`s → `D:\Work\Urea Simulation\launch.bat`
→ `python main.py`. Python 3.14.3 resolves; uvicorn boots and serves HTTP 200. But the
**simulation task crashed on the very first tick** with `MemoryError`, so the browser opened
on a frozen sim → looked like "not starting."

Crash was in the `_delay` transport-delay helper added in `487d4a1`. Original code:
```python
n = max(1, int(round(td_s / dt)))
buf = deque([target] * n, maxlen=n)   # MemoryError
```
It sized the ring buffer from the **live sub-step `dt`**. But `sim_task` (main.py ~L2982)
subdivides each real tick into `STEP_CAP`(=0.5 s)-bounded sub-steps:
```python
sim_advance = dt * SIM_SPEED[mode]
while sim_advance > 1e-9:
    h = min(STEP_CAP, sim_advance)
    last_packet = step_sim(h)
    sim_advance -= h
```
The **remainder sub-step `h` is a tiny float crumb** (~1e-8 s) on nearly every tick →
`n = round(345 / 1e-8) ≈ 3.5e10` → `[target]*n` → out-of-memory. My injection wrongly
assumed a fixed `dt = 0.1` grid.

**Fix:** rewrote `_delay` (main.py ~L1485) as a **timestamp-tagged FIFO** — a continuous-time
transport delay, zero-order-held on a per-sub-step sim clock. Buffer length is no longer tied
to `dt`, so any sub-step size (incl. crumbs) is safe. New internal state shape is
`{"t": float, "buf": deque[(entry_time, value)]}` stored in `s.tlag[key]` (was a bare deque).
Still:
- **conservation-safe** — every input sample emitted exactly once (FIFO), only re-timed;
- **pin bit-exact** — until `td` s of history accrue the input passes through; constant input
  → constant output for all t.

`_foptd` (composes `_delay` + `_lag1`) unchanged and still unused.

### Wiring (unchanged from `487d4a1`)

- **CO₂**: `F_CO2_syn_th = _delay(s.tlag, "FEED_CO2", s.F_CO2_th, FEED_TD_S, dt)` (~L1792)
  → stripper 322E001 (~L1910), reactor 322R001 (~L2012). Live BL meter `s.F_CO2_th` still
  drives FY/FT-322403 display, load %, DCS ratio cascade, ratio-PV validity gate.
- **NH₃**: `motive_nh3_kgh = _delay(s.tlag, "FEED_NH3", motive_nh3_kgh, FEED_TD_S, dt)` (~L1877)
  → ejector, phi_m, downstream telemetry. Tank/pump balance debits the **live** flow.

The loop's ~3470 s pressurization τ stays **emergent** from the inventory ODEs (validation
target τ_sim ∈ [2884, 4055] s), never hard-coded.

### Verification evidence (fresh, this session)

- **Backend boot**: `python main.py` → port up 7 s, uvicorn running, **15 s sustained run,
  0 exceptions** (was: `MemoryError` on tick 1, `sim_task` dead while uvicorn served 200).
- `scratchpad/probe_verify_calibration.py` — **4/4 gates GREEN**: 11 boot pins bit-identical
  (max |Δ|=0.0), LT-322504=80.0000%, strip_level=50.0000%, rpm display shift correct,
  bumpless CAS |Δ|=0.0000%.
- `backend/tests/run_full_audit.py` — **exit 0, 0 FAIL** (5-campaign suite ran to END OF CAMPAIGN).

## 2026-07-03 (session 3): Task 5 — LT-322504 decoupled from load + stripper slip-direction fix

**User order:** "reactor level LT-322504 should not be coupled and pinned to plant load, change in
LT-322504 should be according to mass balance on 332R001" (typo for 322R001). **Overrides** the
earlier Lead-Ops Option-2 shadow-display mandate.

### main.py edits (uncommitted at time of writing → this session's commit)

**Display decoupling (6 edits):** deleted `self.react_m_liq_shadow`, `_load_gate()`, and the
SHADOW holdup block. LT-322504 now reads the PHYSICAL head through fixed N7 transmitter
geometry (~L2140):

```python
_H_liq_react         = REACT_LIQ_H_M * s.react_level_pct / 100.0          # physical head, m
s.react_lt322504_pct = clamp(REACT_LEVEL_NLL_PCT
                             + (_H_liq_react - REACT_LEVEL_DES_M) / REACT_LT_SPAN_M * 100.0,
                             0.0, 100.0)                                  # span 1.5 m, 20.0 m = 80 %
```

`react_level_pct` is the DOMINO physical inventory: dm/dt = ṁ_in − ṁ_out + ṁ_fwd with
ṁ_out = ṁ_des·(θ/θ_des)·(max(L,0)/L_des), L = m/(ρ(T_bulk)·A) → L_eq = L_des·(θ_des/θ).

**S2 stripper slip-direction fix (root cause of level-rise-on-vent-open):** in
`stripper_322e001` the feed-load choke `g_T` fed the `slip` term, routing unstripped volatiles
OVERHEAD (loop return) instead of BOTTOMS (loop exit via LV-322501) — wrong physics sign for a
flooded steam-limited stripper (classic NH₃ slip goes to the LP section). Combined with the
g_HC 1.05 clamp it made the dynamic return gain ≥ 1, so opening HV-322605 60→75 % RAISED the
physical level. Fix (one functional line + comments, ~L640):

```python
mod  = clamp(eta_T_steam * eta_co2 * eta_P, 0.0, 1.12) * min(g_T, 1.0)
slip = max(1.0 - g_NC, 0.0) + max(1.0 - g_HC, 0.0)   # composition (N/C, H/C) breakthrough only
```

Design g_T = 1 and feed-lean g_T > 1 ⇒ min(g_T, 1) = 1 ⇒ design point AND turndown
byte-identical; only the flood branch (g_T < 1) changes, cutting the split so volatiles leave
with the bottoms. Per-component conservation exact (split loop untouched).

### Verification (all green, this session)

- 5-gate probe `scratchpad/verify_task5_lt322504.py` **OVERALL PASS**:
  Gate A design hold — all pins bit-exact, LT = 80.0;
  S1 feed cut to 90 % — LT 31.198, level 77.072 (d_vs_ctrl −48.80);
  S2 HV-322605 +15 % — LT 0.0, level 69.647 falling (d −80.0; pre-fix FAIL at +17.48);
  S3 HV-322602 close 74→60 — LT peak 87.884 (d_peak +7.884).
- S2 settle trace (`scratchpad/s2_settle_trace.py`): level → **16.008 m at t = 10800 s**,
  exactly L_eq = 20·(60/75) = 16.0 m; LV op returns 46.14 %, P_syn 140.692 — loop inventory
  shed via bottoms/letdown, conservation intact.
- `tests/audit_e001_stripper.py` ALL PASS: mass closure worst 0.00 ppm across 60 cases;
  B2 slip monotone 0→0.4609→0.5; B3 extremes finite; LIC sump returns to SP 50.000 %.
- Regression: valve-indicator matrix `HV-322605 → LT_322504 d=−100 [OK]` (open→fall restored);
  flood scenario close→LT 100.000; pillar4 flood LT pegged 100, closure resid ~3e-9;
  test_reactor 14/14; ejector stall + spindle suites PASS; `run_full_audit.py` exit 0;
  28-06 4-gate probe (`verify_sim_vs_2806.py`) OVERALL PASS.
- Turndown A/B vs HEAD (git stash): rows 70–95 % byte-identical to HEAD; 100 % row IMPROVED
  (f_cons 1.10602→1.03705, dPsyn 0.0110→0.0, CHECK→OK) — old g_T slip term was an asymmetric
  ripple amplifier at design.

### §C2 status — CLOSED (user directive, 28-06 window 15:23–16:01)

29-06 normal-op export (`Urea_NormalOp_29-06-2025_Trends.xlsx`) had no LT-322504/LIC/level tag;
user then ordered the **28-06 15:23:00–16:01:00 window** used as the steady-state discriminator.
Window: LT-322504-3 = 99.94 **dead flat** (range 0.00), load 95.0–97.0, HIC-322605 47.1–49.0
(mean 48.05), LV-322501 44.32 (43.25–45.40), PT-329201 135.92 bar g. Post-Task-5 engine
reproduces the plateau with **no constant changed**:
L_eq = L_des·(ṁ_in/ṁ_des)·(θ_des/θ) = 20·0.96·(60/48.05) = 23.98 m > 20.3 m top tap ⇒ LT
clamps 100.0. Probe `scratchpad/probe_c2_close.py`: design hold LT 80.0000 bit-exact; field
lineup → LT 100.000 by 1800 s, head 23.359 m @15000 s (→23.98), LV op 43.87 vs field 44.32.
Verdict: hypothesis 1, genuinely liquid-full above top tap under field lineup; density
cross-sensitivity rejected (can't give dead-flat 99.94 across 2 % load swing; clamped
transmitter can). NLL 80 % pin = design point, untouched. 29-06 steady anchors retained in
28-06 report §9.3 as normal-op reference.

## 2026-07-05 (session 4): MASTER SP 329207 faceplate + 329-1 overlay rescan/reorg

Two tasks, both green, committed **and pushed** as `ea07608` (`e2dae58..ea07608`). Touched only
frontend + steam telemetry — reactor/stripper engine untouched, all prior pins preserved.

### Task 1 — MASTER SP 329207 faceplate (4-bar LP header control)

ON/OFF master over the three LP-header pressure controllers (PIC-329207A/B/C):
- **OFF:** each leg operator-owned — PIC-329207A→PV-329207A, B→PV-329207B, C→PV-329207C set/tuned
  individually.
- **ON:** user sets ONE master SP; leg SPs derive and lock (no individual edit):
  $\text{SP}_A=\text{SP}_M+0.1$ (vent), $\text{SP}_B=\text{SP}_M$ (320MT02 turbine make-up),
  $\text{SP}_C=\text{SP}_M-0.1$ (BL make-up, stream 963). Sub-controller writes ignored while ON.
- Staggered $\pm0.1$ bar deadband ⇒ header floats in $[\text{SP}_M-0.1,\ \text{SP}_M+0.1]$;
  $\uparrow P_{LP}\Rightarrow$ leg A vents, $\downarrow P_{LP}\Rightarrow$ legs B/C admit make-up.
- Constants: `DB_LP=0.1`, `K_207A=3.0`, `K_207B=2.0`, `K_PIC_207=120.0`, `KI_PIC_207=6.0`,
  `I207_CLAMP=100.0/KI_PIC_207`. Defaults (master 4.4, all AUTO) reproduce the design fixed point
  bit-for-bit.
- **Backend** (`main.py` ~L2681, `steam_system.py`): emits `STEAM_SYSTEM.MASTER_SP_329207 {on,sp}`
  + `PIC_329207A/B/C {pv,sp,op,mode}` (A.op=`pv207a_pct`, B.op=`pv207b_pct`, C.op=`valve_963_pct`).
- **Frontend** (`app.js`, `index.html`, `overlays.js`): `OTS_FACE.msp` faceplate; dispatch in
  `overlays.js activate()` routes `fp==='MASTER_SP_329207'` to it BEFORE the generic `CTRL_RE`.

### Task 2 — deep rescan of tagged 329-1 DCS shot → reorganise + complete overlays

Rescanned `New folder/329-1/329-1 tagged.PNG` (1056×502). Overlay transform:
STAGE px = tagged px × (**1.2936**, **1.4343**) — `.screen.shot{background-size:100% 100%}` stretches
the backdrop to the 1366×720 stage. Rewrote `OV['screen-329-1']` (single logical block) →
**36 entries** (11 bound ind, 7 avalve, 2 pump, 12 white-frame ind, 4 nav):
- Repositioned every tile to its rescanned value-box centre; fixed grossly mislocated
  HV-329601 (410,533 → 140,438) and LIC-329502 (847,540 → 744,625).
- **Relabelled `PIC-329207` → `PI-329207`** — plain 2nd header-P indicator (bind `LP.P_bara`);
  faceplate/mode/note dropped (`PI-` doesn't match `CTRL_RE` so no controller pop-up).
- Added controller trio **PIC-329207A@(983,112) / B@(1184,75) / C@(317,143)**, all
  `fp:'MASTER_SP_329207'`.
- **Added missing tags:** HIC-329601, HIC-329602, HV-329602, LV-329502, STARTUP SW, O₂-scavenger
  dosing pumps 329U001-M01/M02.
- PV-329207A/B/C now bind `PIC_329207A/B/C.op` (C was `LP_MAKEUP.PV_329207C`).
- `AS_BUILT_screen-329-1.md` synced: entry counts, bind map, MASTER-SP physics.

### Verification (all green)

- `node --check frontend/overlays.js` clean; 36 unique keys; every avalve has a bind, every nav a
  goto.
- On-disk `main.py` emits the PIC_329207A/B/C trio `{pv,sp,op,mode}` (L2681-2698) → all 20
  screen-329-1 binds code-backed. (Prior session: port-8011 test-server probe `probe_msp.py` passed
  ALL master-SP assertions — A.sp=4.5/B=4.4/C=4.3, sub-writes locked while ON, OFF→independent;
  `run_full_audit` EXIT 0.)
- **Caveat:** user's live server (PID 5764, port 8000) predates these edits — its packet lacks
  `PIC_329207A/B/C` (bind probe MISS on 9 keys). NOT a code defect; new tiles render live only after
  that server restarts (barred from restarting it).

## 2026-07-08 (session 5): 329-1 steam-drum level loops LIC/LV-329502/503/504 wired to sim

Commit `aec3160` (**pushed**). The three page-329-1 level controllers/valves were bare
display tags (no bind, no backend state); they now form closed condensate-level loops that
drive their valves in the engine, per `329-1 mapping and description.md` (authoritative spec).

### The three loops (mapping-faithful)

| Loop | Vessel | Valve action | Inflow → Outflow | Sense |
|------|--------|-------------|------------------|-------|
| LIC-329502 | 329D005 HP saturator | LV-329502 drain → 329D009 | in = HP-stripper condensate return (`m_strip_consume`) ; out = LV-329502 | DIRECT |
| LIC-329503 | 329D009 MP 9-bar drum | LV-329503 drain → 322D001A/B | in = LV-329502 drain (cascade) ; out = LV-329503 | DIRECT |
| LIC-329504 | 322D001A/B LP drums | LV-329504 make-up ← 329P001A/B | in = LV-329504 ; out = LP boil-off (`m_hpcc_gen`) | REVERSE |

### main.py / steam_system.py edits (all in commit `aec3160`)

- `steam_system.py`: velocity-form PI helper `_level_loop(mode,sp,lvl,op,ep,dt,m_span,m_des,direct,m_ext,valve_out)`
  — bumpless, clamped 0-100, `op += KC[(e-ep)+dt/TI·e]`, `e=lvl-sp` (direct) / `sp-lvl` (reverse).
  Design-seeded valve flow `m_valve = m_des·(op/LV_OPEN_DES)`: at seed op=50, sp=50, m_ext=M_DES ⇒ dm=0.
  Constants block (`LIC_KC=2.5`, `LIC_TI=90`, `M_502/503/504_DES`, `MSPAN_502/503/504` from datasheet
  geometry), 6 SteamState fields/loop, 3 calls in `step_steam` before `return state`.
- `m_span` (timescale only, NOT design-pinned): 329D005 horiz ID 1.760 L 5.000 span 1.500 ρ850.25 → 11223 kg;
  329D009 horiz ID 1.776 L 2.600 span 0.750 ρ892.15 → 3090 kg; 322D001 vert ID 1.600 span 2.000 ρ917 → 3688 kg.
- `main.py`: `LIC_329502/503/504` telemetry `{pv,sp,op,mode}` in STEAM_SYSTEM block; `lic329502/503/504_set`
  handlers (uppercase mode; bumpless SP←PV on AUTO entry; op writable only in MAN).
- `frontend/overlays.js`: LIC tags → `.pv`+`.mode` faceplate (`t:'ind'`); LV tags → `.op` valve (`t:'avalve'`).
  `frontend/app.js`: T-map routes `LIC-329502/503/504` → `lic329502/503/504_set`.

### Conservation (Resolution B — resolves the negative-makeup contradiction)

Full stripper condensate cascade (~21.3 kg/s) ≫ LP boil-off (3.0 kg/s), so 329D009 drain does NOT feed
322D001's boiling inventory — it routes to the 329P001 condensate-pump suction/collection. LV-329504
admits only make-up replacing the 3.0 boil-off. Each loop is a LOCAL conservation-honest balance; every
stream maps to a real source/sink → 100% conservation, no fabricated flow.

### Bit-exactness argument (holds)

Level loops live in `step_steam`, GATED OFF during both boot-pins (`_STEAM_READY=False`) → level states
stay at init 50. Post-pin they run but NEVER write P_MP/P_9/P_LP (liquid decoupled from the vapor-pressure
ODEs). At the design seed all dm/dt=0 → pinned pressure fixed point bit-identical.

### Verification (all green)

- A/B via `git stash`: design fixed point **bit-identical** pre/post edit — P_MP=19.700, P_9=9.000, P_LP=4.400.
- Isolated `_level_loop` probe: all three loops park at **exactly `lvl=50.0 op=50.0` over 20000 ticks** (dm/dt=0).
- Disturbance response correct: 502 +20% inflow → re-parks 50.0, op→60% (drains more, DIRECT); 504 +20%
  boil-off → re-parks ~50, op→60% (refills more, REVERSE). MAN freezes op, ep tracks → bumpless re-AUTO.
- `main.py` / `overlays.js` / `app.js` syntax clean.
- Pre-existing baseline `[2]` (PV-329204→0%) + `OVERALL: FAIL` in `steam_system.py` self-test are UNCHANGED
  by this edit (confirmed A/B) — unrelated to level loops.

## 2026-07-12 (session 6): Unit 324 two-stage vacuum evaporation — backend + DCS overlays 324-1 / 324-1b

Commit `411080c` (**pushed**, `92c6bbe..411080c` on `fix/reactor-level-drain-and-vent-coupling`). New
end-of-plant evaporation section: 80 % urea melt → 98.6 % prilling-grade product across two vacuum
stages + a vacuum-condensation train, tied into the existing Unit 323 recirculation effluent. Fully
dynamic, mass/energy-conserving; all prior 322/323/328/329 pins preserved (additive `+298` diff, 194
lines 324-tagged, zero collateral edits to existing engine).

### Backend physics (`main.py`, EVAP_324 block)

Two falling-film vacuum evaporators in series, each an equilibrium flash pinned to a HARD thermal +
concentration boundary; boundaries are the **discard gate** (any drift ⇒ iteration rejected).

| Stage | Vessel(s) | Vacuum | Temp | Urea in→out | Heat |
|-------|-----------|--------|------|-------------|------|
| Evap I  | 324E001 heater / 324F001 separator | 0.330 bar a | **EXACTLY 130 °C** | 80 % → 95 % | LP steam chest, UA·ΔT |
| Evap II | 324E003 heater / 324F003 separator | 0.131 bar a | **EXACTLY 140 °C** | 95 % → 98.6 % | LP steam chest, UA·ΔT |

- **Water removal** = flash of the excess H₂O to hit target urea mass-fraction at the stage `T`;
  vapour load sets the condenser/ejector duty. Overhead vapours → vacuum-condensation train
  **324E002 / 324E005 / 324E006 / 324E007** + steam-jet ejectors **324F002 / 324F004 / 324F005**
  (inter/after-condensers). Condensate collected, non-condensables vented. 100 % conservation:
  feed(+UF85) in ≡ condensate + product out (recycle internal).
- **UF85 injection**: 0.3763 t/h (376.3 kg/h) urea-formaldehyde 85 % into Evap II product as
  anti-caking / crushing-strength additive — ratio-controlled (below).
- Design anchors (kg/h): held bit-exact at boot; `smoke_324.py` regression envelope closes to
  machine precision (packet display shows −3.7 kg/h = 0.004 %, pure round-1/2-dec artifact of 5
  telemetry fields, NOT model drift).

### Controls (I-PD + cascade)

- **TIC-324001 → PIC-329203** (Evap I temp master → LP chest-pressure slave, cascade).
- **TIC-324002 → PIC-329212** (Evap II temp master → LP chest-pressure slave, cascade).
- **PIC-324202 / PIC-324203** vacuum control via **false-air bleed** — PV-324202 / PV-324203 admit
  atmospheric air to hold separator pressure at 0.330 / 0.131 bar a (raise P ⇒ crack bleed).
- **LIC-324501 split-range**: single `.op` drives **LV-324501A** (forward to product, x711 y347) +
  **LV-324501B** (recycle back, x598 y622) — 324F003 sump level.
- **Ratio FFIC-335406 → FIC-335405**: UF85 injection ratioed to product flow (FFIC ratio-SP ×
  product ⇒ FIC-335405 flow SP = 0.3763 t/h).

### UI overlays (`overlays.js`, `index.html`)

Image-backed DCS overlays, 1366×720 stage. Native shots: 324-1 = 1357×647 (sx ×1.006632, sy ×1.112828);
324-1b = 1359×648 (sx ×1.005151, sy ×1.111111). Backdrops `frontend/img/screen-324-1.png` (177498 B) /
`screen-324-1b.png` (267971 B), both committed. Tabs auto-register from DOM.

- **screen-324-1** (Evap I): **26 boxes** — bound readouts TT-324001/PT-324202/LI-324F001, controllers
  TIC-324001 & cascade slave PIC-329203, vacuum PIC-324202, cross-refs to Unit 323 (FIC-324401,
  LT-323507, PT-323204, TIC-323012, PIC-329208), 4 nav hotspots, WHITE frames for unmodelled tags.
- **screen-324-1b** (Evap II): **34 boxes** — TT-324002/PT-324203/PT-324204/LI-324F003, controllers
  TIC-324002 & slave PIC-329212, vacuum PIC-324203, LIC-324501 split-range (both LV bind `.op`),
  FFIC-335406 (RATIO dec4) → FIC-335405A (T/H), OVRD boxes (EXT-OVR LV-A/LV-B, HV-335602, TRIP_35_3),
  3 nav hotspots, WHITE frames.
- **WHITE frames** (tag-only, unmodelled downstream/analyzers): 324-1 = PY-324201, LIC/LV-329505,
  HIC/HV-323605, HIC/HV-329605, PIC-323203, 323P003A/B. 324-1b = AY-324701, FIC-335401, HIC/HV-335602,
  FFY-335406, FIC-335405B, HV-335609/610, LT-335507, 335R001A/B, 335D004, 335P001A/B, 335P002, 335P006.

### Unit 323 tie-in (domino)

No `plant_state.md` in repo — tie-in wired directly and captured in commit body. Unit 324 feed = existing
Unit 323 recirculation effluent via **`RECIRC_323.D002.FIC_324401`** (92.70 t/h, cross-ref not duplicated
into EVAP_324). Level/pressure/temp cross-refs bind to proven-live `RECIRC_323.D002` / `RECIRC_323.F010`
keys (verified against existing 323-1 rows) rather than shadow keys — no double state, conservation intact.

### Verification (all green)

- `smoke_324.py` (200×0.1 s): **Stage1 130.000000 °C** (drift +6.3e-11), **Stage2 140.000000 °C**
  (drift +1.4e-11), F001 0.330000 bara, F003 0.131000 bara, urea **95.0 / 98.6 exact**, envelope
  closure −3.7 kg/h (display rounding). No iteration discarded — anchors held to ~1e-11.
- Controller boot: all 9 (TIC/PIC/LIC/FFIC/FIC) park at seed `op` (bumpless).
- `node --check overlays.js` clean; browser live-validated 26/34 boxes at exact stage coords, values
  streaming over `/ws`; native image dims confirmed 1357×647 / 1359×648.
- Prior pins (322/323/328/329) untouched — additive diff only.

### Not staged (intentional)

`CLAUDE.md`, `ui_guidelines.md`, and probe/scratch files left unstaged. Only 5 files committed by path:
`backend/main.py`, `frontend/overlays.js`, `frontend/index.html`, `frontend/img/screen-324-1.png`,
`frontend/img/screen-324-1b.png`.

## 2026-07-15 (session 7): six-pillar audit — gap closure, indicator scope, hydraulic couplings

Commits `7b384dc` (audit, 11 files, +485/−106) and `ff41027` (artifacts, 8 files, +1185), both
**pushed** (`411080c..ff41027`). Autonomous execution of the audit gap-closure plan under a standing
**boot-pin gate**: every code edit re-run through `scratchpad/regress.py` against
`scratchpad/golden_pin.json` and only confirmed at **25/25 leaves bit-exact**.

### The pin gate (now a committed, repeatable instrument)

`_collect_pin()` (`main.py:5116`) returns a FIXED 15-key / 25-leaf dict of back-solved design
constants; `_pin_cache_key()` (`main.py:5076`) = SHA-256 over **backend source only** — so editing a
frontend or doc file cannot perturb it, and the pin is trivially bit-exact for those. Key this
session: `e151c924579ea4b72cbf16ecbe4aa92f3a7afcbf8311277554a04288cf54c6a9`.
`regress.py` deletes the cache, imports `main` (forces settle + back-solve), dumps `_collect_pin()`
to `pin_out.json`, diffs against golden. Final gate run: **leaves: 25  keys: 15  diffs: 0**.

### C2 — ejector design point RE-ANCHORED (the 98 320 kg/h datasheet is superseded)

The published "Carb. Liq." HMB (suction 57 564 + motive 40 756 = discharge 98 320 kg/h, MW 20.01,
109 °C) balances only around the **OLD** motive, which implied fresh molar N/C = 1.928 < 2.0 —
sub-stoichiometric, a proven non-steady free-run. Path-B tear closure re-anchored the whole design
point on the reconciled 322E003 overflow vector, which `main.py:158` declares the source of truth
(`EJ_SUCTION = overflow × MW`). Hand-verified arithmetic:

$$\Sigma_{suc} = 53\,368.2849\ \mathrm{kg/h},\qquad
\dot m_{mot} = 42\,762.05427809782\ \mathrm{kg/h},\qquad
\Sigma_{disch} = 96\,130.339\ \mathrm{kg/h}$$

$$T_d = \frac{\dot m_{mot} c_{p,N} T_{mot} + \Sigma_{suc} c_{p,C} T_{suc}}{\Sigma_{disch}\, c_{p,D}}
      = \frac{42\,762.05 \cdot 4.74 \cdot 29 + 53\,368.28 \cdot 3.10 \cdot 178.8}{96\,130.34 \cdot 3.50}
      = 105.39\ ^\circ\mathrm{C}$$

MW_disch = 19.705, MW_carb = 22.542, discharge NH₃ = 63 785.52 kg/h (66.353 mass %). Inerts read 0 in
the suction because the reconciliation routes 100 % of N₂/O₂/CH₄/H₂ to the reactor off-gas — exactly
as the 322R001 spec states, consistent with both shared HMBs.

**Stale-comment note (not fixed — would rehash the pin key):** the `~94124` comment on `EJ_DES_TOTAL`
(`main.py:162`) is arithmetic from the OLD motive (40 756 + 53 368 = 94 124). Live value computes to
**96 130.34**. Comment only; no numeric effect.

### The ejector suction-sign fix (`EJ_SPINDLE_R = 2.1517`)

For a constant-ṁ PD-pump-fed jet, motive **momentum** — not free area — sets capacity, so **closing
the spindle RAISES suction**. Negative equal-% law:

$$\phi_{sp}(\theta) = R^{\left(\frac{\theta_{des} - \theta}{100}\right)},\qquad
R = 2.1517,\qquad \theta_{des} = 74\ \%\ \Rightarrow\ \phi_{sp}(74) = R^0 = 1$$

Design opening returns unity ⇒ pin bit-exact by construction. Stall guard
`f_{stall} = \mathrm{clamp}\!\left(\frac{\phi_m - \Phi}{REC - \Phi},0,1\right)^{2}` with
`EJ_STALL_PHI = 0.20`, `EJ_STALL_REC = 0.35`; `EJ_HYD_FRAC_MAX = 1.25` (throat-choke ceiling set > 1
so it never engages at design).

### Items 1–4 (indicator scope) — root causes and fixes

1. **Dynamic indicator behavior.** Root cause `app.js:464` — `const v = o.bind ? gp(window.OTS_LAST||{}, o.bind) : null;`
   with `app.js:59` `if(v==null||isNaN(v)) return '--';`. A `t:'ind'` entry **with no `bind`** renders
   `--` forever; nothing is hardcoded or refresh-gated, so the defect set is exactly the unbound
   entries. Census (`scratchpad/audit_indicators.py`): **327 tagged, 101 unbound**
   (`ovrd` 6, `ind` 51, `pump` 8, `xv` 1, `strm` 16, `nav` 18, `?` 1). Binds added in `overlays.js`
   (+69): FT-322403, PT-329206, PIC-329204, HIC-329601, PT-323201, PIC-323203 (both screens),
   TT-323004, HIC/HV-323605, PV-323203, PIC-324202, TT-323005.
2. **PT-323201 proportionality** — coupled to the 305 gas path:
   $$P_{tgt} = P_{des} + K_P\frac{\dot m_{305} - \dot m_{305,des}}{\dot m_{305,des}},\qquad
     \frac{dP}{dt} = \frac{P_{tgt} - P}{\tau_P}$$
   `R323_C003_P_GAIN` $K_P = 1.20$, $\tau_P = 90$ s, $P_{des} = 4.1$ bar a, `R323_M305_DES` = 24 563.18 kg/h.
3. **PIC-323203 visibility + proportionality** — added to UI; 323F004 node is a **pure accumulator**:
   $$\frac{dP_{e011}}{dt} = K_P\frac{\dot m_{gen,v011} - \dot m_{v011}}{3600},\qquad
     K_P = 0.05,\ \ \Phi_V = \tfrac{3100}{9400} = 0.329787$$
   Chain: LV-323501 stroke → `m_314` → `m_701 = 0.041792 · m_314` → `in_e011` → `gen_v011 = Φ_V · in_e011`.
   `m_701` is 4426.6 of `R3232_E011_IN_DES` = 9396.6 (≈47 %, dominant). 323F004 header uses the same
   FOPTD form with `R323_F004_P_GAIN` = 0.45, $P_{des} = 1.13$ bar a.
4. **Global pressure audit** — every PT/PIC/PIT swept via `audit_indicators.py --press`. Two
   deliberate non-bindings recorded under *Failed / rejected* below.

### CAS boot-mode test resolution (the only red suite this session)

Three `backend/test_ctrl_routes.py` tests failed `assert 'CAS' == 'MAN'` / `409 != 200`. Proven
**pre-existing** on clean HEAD in a throwaway worktree (identical `3 failed, 13 passed`), and
`git log -S 'self.SIC_321951.set_mode("CAS")'` traced the CAS default to **`b96f9be` ("Bug-6 boot
mode")** — deliberate: the running pump-B speed controller boots on CASCADE as slave to the N/C ratio
master; `SIC_321950` stays MAN because pump A is an OFF standby (`pv = open_act = 0`, and CAS on a
stopped pump would wind `mv` up toward `cas_sp`). **Verdict: tests stale, model correct.** Fixed the
tests (assert CAS in the schema test; explicit `set_mode: MAN` in the two MAN-contract tests). Model
untouched ⇒ pin unperturbed.

### Verification (all green)

- Full suite **98 passed, 2 warnings in 48.35 s** (was `3 failed, 95 passed`).
- Boot-pin gate: **25 leaves / 15 keys / 0 diffs**.
- C2 species trace (`test_composition_trace.py`): PASS — every HP-loop species within published
  PFD/HMB precision; 328 lumped-mass abstraction asserted, not fabricated.
- Items 2+3 (`test_gas_phase_prop.py`): PT-323201 dP/frac = 1.1988 / 1.2004 / 1.2001 / 1.2000
  recovers $K_P = 1.20$; PIC-323203 MAN ramps +1.21828 / +3.04514 / +4.86923 bar/300 s at LV-323501
  60/75/90 % vs analytic 1.2092 / 3.0368 / 4.8644; AUTO op 25.01 / 27.36 / 30.90 / 34.43 vs predicted
  25.00 / 27.34 / 30.88 / 34.42.
- C5 domino (`test_couplings.py`): LV-322501↑ ⇒ dPT-323201 **+1.0114**, dPT-323203 **+0.0241**;
  LV-323501↑ ⇒ dF004_P **+0.3607**, dPT-323203 **+0.0531**. Both directions correct.

### Staging (selective, by path — no `git add -A`)

`7b384dc` = the 11 tracked modified files (`main.py` 143, `ui_guidelines.md` 99, `handoff.md` 80,
`test_controllers.py` 72, `overlays.js` 69, `controllers.py` 42, `app.js` 33,
`tests/audit_f001_ejector.py` 31, `index.html` 14, `test_ctrl_routes.py` 6, `CLAUDE.md` 2).
`ff41027` = 8 audit artifacts. **22 untracked junk paths deliberately left untracked** (probe scripts
`backend/_probe_c1*.py` / `_audit_closure.py` / `_creep_probe.py` / `_recon_scrub.py` / `_probe_h1.py`,
`out_*.json`, `backend/pin_out.json`, the nested `Urea Simulation/` Obsidian vault, `graphify-out/`,
`TECH_DEBT.md`, `Master_PID_Tuning_Constants.md`, `PROMPT_329-1_UI.md`,
`simulation_audit_and_remediation_plan.md`, `resume_task_b_prompt.md`, `backend/tests/pillar4_audit.py`,
`backend/tests/repro_bugs_1_4_co2.py`, `backend/tests/_spot_329_1.py`, `backend/test_foptd_fingerprint.py`).

## 2026-07-15 (session 8): §6.4 transient gate, master merge, CLAUDE.md reconciliation

First session governed by the `CLAUDE.md` §5 five-section handoff mandate.

**The Goal.** Close the "Audit Finalization & Transient Merge Gate Protocol", then reconcile the
divergent `CLAUDE.md` into one authoritative directive set.

**Current State.** Fully operational, nothing mid-edit. Suite **103 passed** (98 + 5 new). Pin gate
`leaves: 25  keys: 15  diffs: 0` at every checkpoint. All refs level with origin. 22 untracked paths
deliberately preserved and never staged.
- §6.4 transient gate **SATISFIED**: τ = **3396.9 s** ∈ [2884, 4055] ✓ (2.1 % under the 3469.5 s centre);
  t_d = **39.6 s** ≤ 572 ✓; P_f = **143.19 barg** ∈ [137.5, 150.5] ✓. Smith intermediates t28 = 1171.8 s,
  t63 = 3436.4 s, n = 534 samples. Design hold bit-exact: `140.700000 -> 140.700000 bara (|d| = 0.00e+00)`.
- **Caveat, flagged not buried:** the plateau `P_f = 144.200 bara` is exactly `SYN_P_MAX_BARA` — clamped at
  the ceiling, not freely settled. Field `P_f = 144.0 barg` = 145.01 bara **exceeds** the 144.2 bara ceiling,
  so the sim structurally cannot reach the field value; it lands 0.81 bar low but inside the band. The clamp
  also truncates the tail the Smith ID reads. Documented model law (`main.py:1531`), not a defect.
- `a66c532` is the repo's **first merge commit** — history was 100 % linear before it.

**Active Files.**
- `CLAUDE.md` — rewritten this session to the synthesized rule set (`e300f17`). Now the authority.
- `backend/handoff.md` — this file; §5 mandates it every session.
- `backend/test_transient_coldstart.py` — new, 161 lines, 5 tests, committed `ad30d31`.
- `backend/main.py` — untouched this session (last edit `0ce6dda`, the stale `~94124` comment at `:161`).

**Failed Attempts.**
- **Trusted `origin/master` without fetching.** Read `4390433` from a stale remote-tracking ref, concluded
  master was level, pushed → **rejected, non-fast-forward**. `git fetch` then revealed `4390433..59eb9c0`.
  **Always `git fetch` before trusting any `origin/*` ref.** Did not force-push; investigated and asked.
- **`git diff --no-index --quiet <(git show …) CLAUDE.md`** → `error: Could not access '/proc/38/fd/63'`,
  printed a misleading "DIFFERS -- stop". Process substitution is unusable with git here — **not** a real
  content difference. Verify by blob hash instead (`git rev-parse`, `git ls-files -s`).
- **Rebase rejected** as the divergence fix: the 43 audit commits are already published on
  `origin/fix/reactor-level-drain-and-vent-coupling` at `5d7c5ad`; rebasing rewrites published history.
- **Nearly built a duplicate cold-start driver** — `handoff.md:627` claimed none existed, but
  `backend/tests/coldstart_probe.py` was tracked all along and cited from `main.py:2882-2883`. The doc was
  stale. Promoted the existing probe instead of duplicating it.
- **`regress.py` produced no diff output** — it only *dumps* the pin, never diffs. The gate is TWO steps.
- Prior-session traps that still bite: PowerShell here-strings `@'…'@` break the Bash tool (use `-F <file>`
  for multi-line commit messages); always set `PYTHONIOENCODING=utf-8` (else `UnicodeEncodeError` on `→`);
  never put regex metacharacters in a bash heredoc (`re.PatternError: nothing to repeat`) — write a file;
  native Windows `python.exe` cannot resolve MSYS `/d/...` paths; `git status` has no `--cached`.

**Next Steps.** No open work item. On resume, re-read `CLAUDE.md` first — the operating directives changed
materially this session (autonomous push is now ON; the HALT/await-confirmation protocol is GONE).

## 2026-07-16 (session 9): 25-item PFD gap-closure sprint — items 1 + 2 closed (323E003 tempered water)

**The Goal.** User order (verbatim framing): *"Role: Senior Process Control & Automation Engineer. Task:
Execute a massive gap-closure and UI-wiring sprint across the simulation's backend physics, control logic,
and frontend faceplates based on the master PFD design values."* Source material is **mandated**, not
advisory: `D:\Work\Urea Simulation\References\` for all equipment description/datasheets, and — *"For all
composition and properties of streams at 100% load, strictly refer to"* —
`Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`. 25 items across four domains: control-loop logic
& valve actions (1, 22, 23), UI overlays & missing indicators (2, 3c, 3d, 5, 12, 18, 20), stream properties
& volumetric bindings (3a, 3b, 6, 10, 11, 13, 14, 15, 16, 17, 24, 25), and dynamic/inferential calculated
variables (4, 7, 8, 9, 19, 21).

**Current State.** **2 of 25 items closed** (1 and 2), code-complete, gate-green, behaviourally verified,
documented in the as-built reference as **Rev 9 / Revision Delta #13**, and committed. Nothing is mid-edit.
The other 23 items are researched to varying depth (see Next Steps) but **not started in code**.

Items 1 + 2 were one physical defect cluster — four faults on the single TIC-323013 loop:
1. **Wrong PV node.** `_ctrl_ipd(s.TIC_323013, Te003, dt)` fed the controller the 323E003 **shell**
   temperature (74 °C). TIC-323013 is the tempered-water **supply** controller; its PFD anchor is
   **stream 1102 = 55 °C**.
2. **The SP span forbade the design SP.** `sp_lo = 60.0` made the mandated 55 °C unreachable from the
   faceplate. Span re-cut to **45–65 °C** = the physically achievable supply band.
3. **No split range existed at all.** `overlays.js` bound TV-323013A *and* TV-323013B to the same
   `LPCC_3232.E003.TIC_323013.op`, so both valves read identically. Now true opposites off one `op`:
   $\theta_A = \text{op}$, $\theta_B = 100 - \text{op}$ ⇒ $\theta_A + \theta_B \equiv 100$ **exactly**.
4. **A linear duty fudge.** `Q = UA·(T_shell − R3232_TW_T)·(op/50)` — an `op`-proportional shortcut with no
   driving force, which `CLAUDE.md` §1 (Rigorous Kinetics, "no linear or static shortcuts") forbids.
   Replaced by the physical form $Q = UA\cdot\bigl(T_{shell} - \tfrac12(T_{sup}+T_{ret})\bigr)$, with
   $T_{ret}$ read from the prior-step state to break the algebraic loop (same idiom as `recyc_prev`).

Item 2 (`TT-323015`, stream 1103, 65 °C) falls out of the same block for free: it is the tempered-water
return, $T_{ret} = T_{sup} + (T_{ret}^{des} - T_{sup}^{des})\cdot Q/Q_{des}$.

**Design anchor — bit-exact, not merely close.** `R3232_E003_UA_KW = 14000.0/(74.0−60.0) = 1000.0` exactly.
Old: `1000.0*(74.0−60.0)*(50.0/50.0) = 14000.0`. New: `55.0+65.0 = 120.0 → 0.5*120.0 = 60.0 →
74.0−60.0 = 14.0 → 1000.0*14.0 = 14000.0`. **Bit-identical in IEEE-754**, every intermediate exact.
Return closes on itself: `55.0 + 10.0*(14000.0/14000.0) = 65.0` ⇒ tick n+1 reads the same mean ⇒ fixed
point preserved. Dropping `(op/50)` is therefore *simultaneously* IEEE-exact **and** a §1 compliance fix.

The 45 °C band edge is **not fitted** — two independent derivations agree: the valve char at $\theta_A=100$
gives $65 - 10\cdot2 = 45$ °C, and the mixing law $55 = \tfrac12 T_{cold} + \tfrac12\cdot 65$ back-solves
$T_{cold} = 45$ °C.

**Verification (all green).**
- Pin gate, both steps: **`leaves: 25  keys: 15  diffs: 0`**.
- Design probe (6000 ticks @ 0.1 s): `TIC_323013 {pv 55.0, sp 55.0, op 50.0, CAS}`, `TV_323013A 50.0`,
  `TV_323013B 50.0`, `TT_323015 65.0`, `TT_323003 74.0` **unchanged** (shell untouched — Scope Lock).
- Split-range acceptance (item 1's literal requirement): SP 55→**50** ⇒ TV-A 50.0→**68.8** (opens) /
  TV-B 50.0→**31.2** (closes); SP→**60** ⇒ TV-A→**35.8** (closes) / TV-B→**64.2** (opens). `sum ≡ 100.0`
  at every operating point ⇒ "opposite" is exact, not approximate.
- Offset-free integral action (SP 50 step): err +4.40 → +3.80 → +2.80 → +1.50 → +0.40 → **0.00** at
  t = 100/200/400/800/1600/3000 s, TV-A → **74.8** — matching the valve char's *independent* prediction
  $T_{ss} = 65 - 10(75/50) = 50 \Rightarrow \theta_{A,\infty} = 75.0$. Closed-loop integral time
  $T_i/(K_c|K_p|) = 250/(3\cdot 0.2) = 417$ s ⇒ $4\tau \approx 1670$ s, which is the observed trace.

**Active Files.**
- `backend/main.py` — 4 edits, all in the LPCC 323E003 block: constants (`R3232_TW_SUP_T`,
  `R3232_TW_RET_T`, `R3232_TV13_DES_PCT`, `R3232_TW_TAU_S`); `State.TIC_323013` init (PV/SP → 55,
  `sp_lo` 60→45, `sp_hi` 90→65); the runtime block (`T_tw_ss` / `T_tw_sup` / `T_tw_ret` / physical
  `Q_e003`); `LPCC_3232.E003` telemetry (`TV_323013A`, `TV_323013B`, `TT_323015`).
- `frontend/overlays.js` — screen-323-2: `tv013a`/`tv013b` split to distinct binds; `tt015w` → bound
  `tt015`. (The `w` key suffix means "white frame / unbound"; drop it when a tag gets bound.)
- `Urea OTS — As-Built Mathematical & System Architecture Reference.md` — **Rev 9** history row +
  **Revision Delta #13**. Note this is the **first Unit-323 entry** in that document; its header is scoped
  "Units 321 / 322 / 329" and Sections 1–6 remain HP-loop-only. Standing up a new §1.9/§3.x Unit-323
  section would breach §3 Surgical Edits, so the Rev+Delta convention was used instead.
- `scratchpad/pindiff.py` — **untracked, must stay untracked** (with `scratchpad/pin_now.json`).

**Failed Attempts / rejected approaches (this session).**
- **Mirroring the `TIC_329005` loop wholesale for item 1 — REJECTED (near-miss, caught before writing).**
  **Two controller idioms coexist in `main.py` and must never be conflated:** (a) `_ctrl_ipd` dicts, full
  14-key schema `{mode,op,sp,pv,pv1,pv2,Kc,Ti,Td,act,op_lo,op_hi,sp_lo,sp_hi}`, stepped by the shared
  `_ctrl_ipd(c, pv, dt, cas_sp=None)` helper — used by LIC-322501 and **all of Unit 323 incl. TIC-323013**;
  (b) hand-rolled inline velocity-PI dicts, minimal 5-key `{mode,op,sp,pv,pv_prev}`, stepped by bespoke
  inline code in the 322E003 CCW block — used by `FIC_329409` / `TIC_329005`. Take the *physics* from a
  neighbouring loop, never the controller plumbing.
- **Adding `s.r3232_tw_sup_T` / `s.r3232_tw_ret_T` to `State.__init__` — REJECTED.** `_lag1` lazy-inits to
  target and keeps state in `s.tlag` keyed by string ⇒ no new `__init__` attributes, no boot transient.
- **Deleting `R3232_TW_T = 60.0` — REJECTED.** It is the design *mean* ½(55+65) that the `UA` back-solve
  keys off. Retained with a comment; must never be replaced by a live value.
- **Changing `R3232_E003_Q_DES_KW` (14 000) to reconcile PFD 1102/1103 — REJECTED (see the open gap below).**

**Deliberately-unclosed findings (documented, NOT fixed — Scope Lock). Do not silently "fix" these.**
1. **Item 1 — the 14 000 vs 12 703 kW cross-source gap.** PFD streams 1102/1103 give 1094 t/h over a 10 K
   rise ⇒ $Q = 1094000\cdot4.18\cdot10/3600 = \mathbf{12\,703}$ kW, but the engine's LPCC-datasheet anchor
   is $Q_{des} = \mathbf{14\,000}$ kW (reconciling would need 1206 t/h, 10 % off the PFD). Changing it
   cascades `R3232_E003_LAMC` → the 323E003 energy balance → `m_744`/`m_756` → the **pinned** A328
   back-solves. Both anchors are internally consistent; only their cross-source ratio is not. Also recorded
   in Delta #13's ⚠ sub-paragraph.
2. **Item 24 — the CPL/GCB anchor conflict; the item is SPLIT.** The *binding* half (point FT-322404 at the
   live CPL feed) is lawful and lands with the normal batch. The *anchor* half cannot: moving
   `A328_CPL_DES` 900 → 1750 breaks `A328_M756_DES = A328_M755_DES + A328_CPL_DES + A328_ABS_DES`
   (34 208 ≠ 33 358) and forces `A328_ABS_DES` 980 → 130, moving **three golden-pin keys**. Worse, the 322
   datasheet's vent is ~1578 kg/h while the column balance forces GCB − vent = 130 ⟹ GCB = 1708, against
   pinned `A328_GCB_DES = 5901.35` — a **3.5× discrepancy**. **Regenerating `golden_pin.json` to absorb
   this is REJECTED**: it would defeat the gate protecting the rest of the model.
   Still open: whether `A328_CPL_DES` (900 kg/h @ 30 °C) *is* PFD stream 954 (1750 kg/h @ 46 °C). For:
   the name, the 322C001 destination, the code's own balance comment. Against: both the temperature and
   the flow. **Confirm before touching it.**
3. **Item 23 — resolution R2 deviates from datasheet §5.2, on purpose.** The literal order ("LV-B is the
   only valve controlling LIC-324501 until granulation is added") is a **numerical runaway** as written:
   at design `R324_LIC501_OP_DES = 75` ⇒ `lva_stroke = 50 %` ⇒ `m_fwd = P2_DES`, `lvb_stroke = 0` — i.e.
   the design case *is* granulation running with zero recycle and LV-B shut. Forcing "LV-B only" with the
   existing recycle semantics gives `m_fwd = 0`, so urea enters at 74 199 kg/h and never exits.
   **R1 REJECTED — do not re-attempt.** **R2 (chosen):** LV-B carries melt to the 335 boundary until
   granulation exists; LIC-324501 direct-acting on LV-B; LV-A parked at 0 %; UF85 still dosed into the
   335P001 suction (upstream of both valves). **Consequence to honour when implementing:** §5.2's "if
   LV-324501A closes, drop the 335P002A/B stroke to zero" is currently implicit in
   `m_uf = uf_ratio * m_fwd` — under R2 that coupling must be re-pointed at the **active** forward valve.
   `PIC-335401`'s 3.8 barg override is **out of scope by the user's own conditional** ("*once granulation
   is added*"); unit 335 is unbuilt under Scope Lock. It is **not** a hard blocker.

**Operational lessons (cost real time this session — preserve).**
- **`regress.py` does `os.chdir(BACKEND)`, so argv[1] MUST be absolute.** A relative path dies with
  `FileNotFoundError: [Errno 2] No such file or directory: 'scratchpad/pin_now.json'` *after* the
  import/settle already succeeded — only the write step fails. Use
  `python scratchpad/regress.py "D:\Work\Urea Simulation\scratchpad\pin_now.json"`.
- **The global State instance is `main.state`** (`main.py:2666  state = State()`), **not** `main.S`.
- **`step_sim(dt)` RETURNS the telemetry dict** (`main.py:2673`) ⇒ a probe is
  `t = main.step_sim(0.1); t['LPCC_3232']['E003']`.
- **The pin gate is TWO steps and `pindiff.py` is untracked** — `regress.py` only *dumps* `_collect_pin()`;
  it never diffs. Recreate `pindiff.py` if absent (it was, once). Its `leaves()` must be **list-aware**:
  `REACT_MASS_DES` is a 3-element list, and the mandated count treats list elements as leaves —
  13 scalars + 3 + 9 = **25**. A dict-only recursion reports 23 and reads like drift when nothing drifted.
- **The pin key is SHA-256 over exactly `("main.py", "steam_system.py", "reactor.py", "controllers.py")`**
  (`_PIN_SRC_FILES`). Editing any of those four rehashes the pin ⇒ re-gate. Editing docs/tests/frontend
  does not.
- **Summaries are not line-exact.** Re-read or grep the target region before every edit and match on exact
  strings, never line numbers. The telemetry block landed at 4020 vs a summary's 4001 (shift ≈ +19).
- **`Grep` prefixes hits with the primary cwd** (`C:\Program Files\Git\...`) because the working directory
  is on `C:` and the repo is on `D:`. Cosmetic — **line numbers are still correct**.
- **PFD composition units (proven, not assumed): gas streams are mol%, liquid streams are wt%.** Proven by
  exact average-MW reconstruction: 737 → 0.1232·44.0098 + 0.4621·18.0152 + 0.4147·17.0304 = **20.81** =
  listed; 776 → 100/(23.63/44.0098 + 47.1/18.0152 + 29.21/17.0304 + 0.06/60.056) = **20.54** = listed.
  ⇒ the narrative doc `328E004 328D001 328P002 Datasheets.md:60` calling stream 786 "93.08 **weight**
  percent" is **WRONG**.
- **Overlay `--` root cause** (`app.js:464` + `app.js:59`): an `OV` entry with `t:'ind'` and **no `bind`**
  renders `--` forever. The defect set is exactly the unbound entries — nothing is refresh-gated.

### Session 9 (cont.) — sprint items 3b / 3c / 3d / 5: the 328-1 temperature indicators

**Goal.** Second batch of the 25-item gap-closure sprint. Four 328-1 TTs: TT-328009 (stream 746, 190 °C),
TT-328005 (stream 739, 143 °C), TT-328004 (328C004 top tray), and TT-328007 (stream 743, 139 °C).

**Current state — CODE-COMPLETE, ALL GATES GREEN, SHIPPED.** Delta #14 + Rev 10 in the as-built doc.

- **Item 3c was NOT a display gap — it was a §1 physics defect.** The C003 runtime hard-coded
  `m_746 = m_743  # via 328E021 (190 °C)` and the energy balance read `sens_c003` off the frozen
  `R328_C003_T746 = 190.0`. Any TT-328009 bound there would read 190 forever. Now
  `T_746 = s.a328_c002_T + R328_E021_EPS_T*(Tc003 - s.a328_c002_T)`.
- **Use the design-implied ε, never the datasheet ε.** `R328_E021_EPS = 1913.6/(37.52*61.0)` =
  0.836100527805935 → `139 + ε·61 = 190.00213219616205` ≠ 190.0 ⇒ **breaks the Design Anchor**. That is
  *why* the original author froze the constant. `R328_E021_EPS_T = (190-139)/(200-139) = 51/61` is exact
  **and reconstructs the datasheet's own provenance**: Q_cold = 33769/3600·4·51 = **1913.577** ≈ its
  1913.6; closure 1968.027 − 1913.577 = **54.45** ≈ its `R328_E021_LOSS` = 54.4. No constant fabricated.
- **`R328_E021_EPS` / `R328_E021_LOSS` / `R328_E007_EPS` / `R328_E007_LOSS` are DEAD** — grep proves
  definition lines only, zero consumers. A design-basis reconciliation record never wired live.
- **`sens_c003` had to move with the display** (conservation, not preference): `T_746` is the *same
  physical node*. A live TT-328009 over a constant-fed energy balance = display/physics decoupling,
  forbidden by §1. Substituting is **bit-identical at design** (`repr()`-equal, −375.2111111111111 kW).
- **No clamp on `T_746`** — ε ∈ (0,1) ⇒ convex combination of the two live inlets ⇒ cannot cross either.
  Proven empirically, reversed case included (`T_c003 100 → T_746 106.4`, still bracketed).
- **Item 3b was a wrong-node bind** (Δ#13(i) class): `TT_328007` published `R328_E007_TH_OUT = 89.0`,
  the 328E007 **hot outlet** to the 740 boundary. The tag is the C002 bottoms draw to 328P006 = 743 = 139.
- **Item 5 used the house derived-offset idiom** (the `R328_C003_DT_DES` precedent, L564):
  `R328_C004_DT_DES = R328_C004_T - R328_C002_T750` = 143 − 140 = 3 K, anchored on the PFD's own
  stream 750 (the C004 overhead **is** the top-tray vapour) ⇒ TT-328004 tracks the live bottoms.

**Verified.** Pin gate `leaves: 25  keys: 15  diffs: 0` (no `R328_*` key is pinned, but `main.py` ∈
`_PIN_SRC_FILES` ⇒ re-gated). `probe328.py` (6000 ticks @ 0.1 s): all four TTs on their PFD anchors,
**`TT_328C003` held at 200.0** (the live `sens_c003` does not move the C003 fixed point — the central risk),
`bot747_th 34.06` t/h = design 34,062, `bot743_th 33.77` = 33,769, `LI_328505 50.00`.
`dyn328.py` (the item's actual point — dynamism, which neither the pin nor the probe can prove):
`T_c003 +10 K → T_746 +8.4` vs closed-form ε·10 = 8.361; `T_c002 +10 K → T_746 +1.6` vs (1−ε)·10 = 1.639.
**The ~0.04 residual is the telemetry's `round(x,1)`, not physics** — hence the 0.06 tolerance.

**Deliberately unclosed (Scope Lock — do NOT silently "fix" these).**
- **The E021 HOT side is still static**: `m_749 = m_747  # via 328E021 (148 °C)` + `R328_C004_T749 = 148.0`
  is the exact mirror of the defect fixed here, on stream 749. Item 3c is scoped to the cold outlet.
  **This is the obvious next 328 item.**
- **`TT_328012`/`TIC_328012` stay on the constant `R328_C003_T746`.** The C003 **3rd tray** is a *different
  physical node* from the 746 feed; the model conflates them (its own comment: "3rd-tray / 746 absolute").
  Making the tray track E021's ε would be **wrong physics dressed as a fix**. TIC-328012's `_ctrl_ipd`
  return is discarded at L3694 (display-only) ⇒ pin-safe either way.
- **`R328_E007_TH_OUT = 89.0` is now orphaned but RETAINED** — the `R3232_TW_T = 60.0` precedent
  (deleting a boundary design datum is a rejected approach). Its L751 comment already documents it.
- **`tt8011w` + `tt8012w` both bind `DESORB_328.C003.TT_328012`** — duplicate-bind, same class as the
  TV-323013A/B defect fixed in `c538831` and the still-open LV-324501A/B one.

**Overlay `w`-suffix convention** ("white frame / unbound"): dropped the `w` on `tt8004`/`tt8009`/`tt8005`
when binding them, and retro-fixed `tt8007w`→`tt8007` (bound but still carrying the `w`, and its comment
still claimed "328E007 process outlet 89C"). ⚠ Still inconsistent elsewhere: `tt8011w`/`tt8012w`/`tt8013w`
are all **bound** yet retain the `w`.

**Next steps.** Corrected sprint sequencing — **the earlier "3b/3c/3d/5 are frontend-only" claim was WRONG**
(grep proved `TT_328009`/`TT_328005`/`TT_328004` did not exist in `main.py` ⇒ new telemetry keys ⇒ backend
⇒ pin rehash). Frontend-only batch (no rehash): item 12, item 15, the m³/hr unit fixes on 10/11/16/17, and
the duplicate-bind defects. Backend batch (rehash ⇒ gate before commit): 3a, 4, 6, 7, 8, 9, 13, 14, 17, 18,
19, 20, 21, 22, 23, 24 (**binding half only**), 25.

## Files

**Committed / active source:**
- `backend/main.py` — the engine. `LV322501_OPEN_DES` 82.0→46.1 (session 2, ~L335); session 3:
  LT-322504 display decoupling (shadow machinery deleted, ~L2140) + stripper slip-direction fix
  (`mod × min(g_T,1)`, ~L640).
- `backend/handoff.md` — this file.
- `backend/steam_system.py` — 4-level steam network; session 4: MASTER SP 329207 ON/OFF + ±0.1
  staggered leg handlers.
- `frontend/overlays.js` — session 4: `OV['screen-329-1']` 36-entry rescan/reorg + MASTER-SP trio.
- `frontend/app.js`, `frontend/index.html` — session 4: `MASTER_SP_329207` faceplate + dispatch.
- `AS_BUILT_screen-329-1.md` (repo root) — 329-1 as-built (session 4 sync).
- `backend/reports/dcs_anchor_dynamics_2025-06-03.md` — 03-06 anchor report (+LIC closure note).
- `backend/reports/dcs_anchor_dynamics_2025-06-28.md` — **28-06 anchor report (this session)**.
- `launch.bat` (repo root) — the launcher the desktop shortcuts target. Fine, unchanged.

**Verification instruments (session 7: now COMMITTED under `scratchpad/`, no longer temp-dir):**
- `scratchpad/regress.py` + `scratchpad/golden_pin.json` — **the boot-pin gate**. Run before
  confirming ANY backend edit. Golden is the anchor and IS versioned; the run output
  (`pin_out.json`, `pin_after_coupling.json`, `pin_err.txt`) is `.gitignore`d — it regenerates every
  run and would churn forever.
- `scratchpad/test_composition_trace.py` — C2 species-level trace, HP loop vs extracted PFD/HMB.
  Anchors quoted verbatim from `main.py:158-159`, **not imported**, to avoid circular self-comparison.
- `scratchpad/test_gas_phase_prop.py` — items 2+3 (PT-323201 / PIC-323203 proportionality).
- `scratchpad/test_couplings.py` — C5 hydraulic-domino direction test.
- `scratchpad/audit_indicators.py` — indicator census; `--press` sweeps all pressure tags. Path is
  now `__file__`-relative (the hardcoded `D:\` path was fixed before tracking).
- `scratchpad/audit_report.html` — the six-pillar audit report (761 lines).

**Analysis / verification (older session scratchpad, not committed, temp-dir — recreate if needed):**
- `probe_pins_2806.py` — boot-pin + 600 s hold A/B probe (pre/post edit bit-exactness).
- `explore_2806.py`, `knots_2806.py`, `anchors_2806.py`, `analysis_2806.py`,
  `anchors_2806.json`, `analysis_2806_results.json` — 28-06 anchor extraction + 10-target analysis.
- `verify_sim_vs_2806.py` — 4-gate sim-vs-28-06 harness (session 3 re-run: OVERALL PASS).
- `verify_task5_lt322504.py`, `s2_settle_trace.py` — Task-5 5-gate probe + S2 long settle.
- `c2_window_2806.py`, `probe_c2_close.py` — C2 closure: 15:23–16:01 window stats + sim probe.

**Untracked in repo root/backend (NOT mine, left alone — do not commit blindly):**
`Gemini/`, `Urea Simulation/`, `TECH_DEBT.md`, `fundamentals.md`, several `Combined_*_PFD*.md`,
`backend/_audit_closure.py`, `backend/_creep_probe.py`, `backend/_probe_c1*.py`, `backend/_probe_h1.py`,
`backend/_recon_scrub.py`, `backend/tests/pillar4_audit.py`, `backend/tests/repro_bugs_1_4_co2.py`.

## Key verified numbers (preserve)

- PT-329201 FOPTD (03-06): P₀=5.7, P_f=144.0 bar g, τ=3469.5±585.9 s, t_d=344.7±280.3 s, R²=0.9888.
  28-06 fit τ=2246±500 s is under-resolved + trajectory-dependent → band stays [2884,4055] s.
- Pump map (field, FY-321401): 0.34174 t/h/rpm through-origin, η_v=0.980 (28-06: 0.34150, −0.07 %,
  3rd confirmation). Engine mass map at design ρ 604.8: 0.33667 t/h/rpm; ×613.5/604.8 = 0.34152.
- `LV322501_OPEN_DES` = 46.1 % (field, 28-06 anchors; was datasheet 82.0).
- Pinned state: LT-322504=80.0000%, strip_level=50.0000%, F_CO2_th=54.618 t/h, F_in_BL_th=42.762 t/h,
  pumpB speed_act=127.0131 rpm, open_act=83.5612 %. Sim tick DT=0.1 s, STEP_CAP=0.5 s, FAST=×60.
- Gate-A 600 s hold pins (re-verified post Task-5, bit-exact): LV_op 46.099420016307754,
  strip_level 49.99999990296993, p_syn 140.7, F_CO2_th 54.618, pumpB_rpm 127.01306122448977,
  react_level_pct 80.0, react_lt322504_pct 80.0.
- LT-322504 display law (session 3): LT = clamp(80 + (H_liq − 20.0)/1.5 × 100, 0, 100),
  H_liq = 25·react_level_pct/100. Equilibrium head L_eq = 20·(60/HIC605) m — verified 16.008 m
  at HIC605 = 75.

## Failed / rejected approaches (don't repeat)

- **`_delay` buffer length `n = td/dt` from the LIVE sub-step — REJECTED (this session's bug).**
  The live sub-step is variable and its remainder is a ~1e-8 s crumb → `n` explodes →
  MemoryError. Delay must be timestamp/clock based, independent of sub-step size.
- **UREA-LOAD fit for τ calibration — REJECTED.** Non-monotonic, operator-driven
  (τ=1067±415 s, R²=0.9306). Used only to bracket the feed-introduction window.
- **Hard-coding τ=3470 s as a lag on synthesis pressure — REJECTED.** Double-counts inventory
  ODE dynamics, violates conservation. τ is a validation target only.
- **Interpolated grid rows from the xlsx — REJECTED.** Zero dynamic information; anchors only.
- **Flow derating from hydraulic resistance — REJECTED.** I/ṁ rises with P_syn but flow stays
  on the PD line → motor-load only, no flow penalty.
- **Editing hand-valve `*_DES` to operator positions (HV-322602/HIC-322604/605/TV-329005) —
  REJECTED.** Operator practice ≠ design basis; would fabricate constants.
- **Adopting 28-06 τ=2246 s or T3/T5/T9/T10 secants as model gains — REJECTED.** Under-resolved
  / confounded / sign-unstable (report §3–4).
- **Shadow-holdup / `_load_gate` LT-322504 display (Option-2 mandate) — DELETED (session 3, user
  order).** Display pinned to plant load hid real inventory motion; LT must track physical head.
- **g_T (feed-load) term inside stripper `slip` — REJECTED (session 3, the S2 bug).** Routes
  unstripped volatiles overhead → positive loop-return gain → level RISES on vent open. Feed-load
  choke must CUT the split (`mod × min(g_T,1)`) so volatiles exit with bottoms via LV-322501.
- **Binding PT-328401 to invent a 328 pressure — REJECTED (session 7), disposition RATIFIED by user
  (session 8): "Unmodeled 328P002 reflux pump discharge; no engine state exists."** The 328 recovery
  section carries LUMPED MASS only (`m_735` / `m_738` / `m_755` / `m_775`, no species vector, no
  pressure state) — an intentional abstraction, proven empirically by `test_composition_trace.py`
  (`328 streams w/ species vec : none -- lumped mass only`). Binding it means fabricating physics the
  model deliberately abstracts. Left unbound (`overlays.js:297`) on purpose, under the
  `WHITE FRAMES : unmodelled boundary / analyzer / downstream` header where it already sits.
  A session-8 directive to bind it to Stream 735 "using the mass flow and density data extracted
  earlier" was refused on evidence: no `FT-328401` exists anywhere in the repo (grep `328401` returns
  only `PT-328401` plus the `FIC/FFIC/FV-328401` 328C004 desorber-II LP-steam loop, already bound at
  `overlays.js:319-321`), `m_735` is lumped mass with **no density term anywhere**, and PT is a
  *pressure* transmitter — mass flow and density cannot produce a pressure without inventing a
  hydraulic model. **Status: unbound, permanent, by design.**
- **Throttling the 324E002 vent to make HIC-323605 "do something" — REJECTED (session 7).**
  `m_324_vent = fa202_m + fa203_m` (`main.py:3665`) is a **boundary sink**, display-only via
  `VAC.vent_kgh` (`main.py:4171`). Throttling it destroys mass at the boundary → violates the 100 %
  conservation constraint.
- **Anchoring the ejector to the 98 320 kg/h "Carb. Liq." datasheet — REJECTED (session 7).**
  Superseded: it closes only around the OLD 40 756 kg/h motive, which implies fresh N/C = 1.928 < 2.0
  (sub-stoichiometric ⇒ non-steady free-run). Reconciled Path-B point is
  53 368.28 + 42 762.05 = **96 130.34 kg/h**; `main.py:158` (`EJ_SUCTION = overflow × MW`) is the
  source of truth. Making the model agree with the old table would fabricate agreement with a
  falsified datasheet.

## 2026-07-17 (session 10): Tranche A2 — LIC-323503 given real authority via a cascade onto the 718A leg

Commit `7c2adf9` (**pushed**, `f66dac9..7c2adf9` on `master`). Closes sprint items **11, 14, 16** (kg/h
tranche only; the m³/h faceplate migration is deferred to a separate commit — task #16). Two files by path:
`backend/main.py` (+141/−24 incl. the two prior sprint commits already in HEAD) and the new acceptance test
`scratchpad/dyn503.py`. Nothing mid-edit; all four gates green at commit time.

**The Goal.** LIC-323503 was noded onto **323D003**, which `main.py:71` records as *unit 323-2 auxiliary
drum (off-envelope, no HMB stream)* — the controller had no plant to act on. Re-node it onto **323D011**,
the flash-tank-condenser level tank it is actually named for (`328E021 328E007 328P003 328P006.md:359`,
"maintains the flash tank condenser level tank at 50% capacity"), and give it genuine steady-state
authority over the 323P008 common-discharge header feeding the two lean-carbamate recycle legs (718A/718B).

**The load-bearing law discovered: DOF accounting beats plausible topology.** LV-323503 sits on the common
discharge header, physically upstream of both 718 legs, so the intuitive model is a *series* stroke derating
both FVs. That puts **three integrators** (LIC-323503, FIC-323405, FIC-323418) on **two degrees of freedom**
(tank inventory, A/B split). A FIC in AUTO holds its leg at SP by integral action and therefore *rejects*
anything placed in series with it — so the level loop is left with no steady-state authority and winds up to
`op_hi`. **Proven empirically, not argued:** a 12,000 s step test (drain 10 % of the tank) drove LIC-323503
to op=100 with the level parked at **51.05 %**, never returning to SP. This is the same failure mode as the
rejected `avail`/derate approach, and it is why that approach was abandoned (see Rejected register).

**The fix — one integrator per DOF (a cascade, realizing the OEM "runs out on its curve" narrative,
`323E011 323D011 323P008 Datasheets.md:54`):**
- **LIC-323503 (master)** outputs a *total draw demand* for the header:
  `m718_dmd = R3232_D011_M718_DES * (lic503_op / R3232_LV503_OP_DES)`.
- **FIC-323418 stays independent AUTO** on the 718B slipstream — the OEM's "specific recycle flow rate"
  (`328E021…:369`), with a real tuning row (`Master_PID_Tuning_Constants.md:14`, "ACA FROM 323P8A/B").
- **FIC-323405 becomes the CAS slave**, `cas_sp = max(m718_dmd − m_718B, 0.0)`. 718A is the balance leg,
  so the level loop's authority lands *on* it instead of being *rejected by* it. **FIC-323405 has zero hits
  anywhere in `References/`** — no OEM row claims it as an independent controller — which is precisely why
  it, and not FIC-323418, is the correct slave.

Same step test on the cascade returns the level to SP with the op off the rail, and FIC-323418's op stays
flat at **exactly 50.000** throughout — proof the split DOF is now decoupled from the inventory DOF.

**The tick-1 design-anchor test (methodology, reusable).** Design bit-exactness was verified **at the raw
float on tick 1, not at a settled value**: the boot seed *is* the design point, so if the network is exact
the first tick must leave every state bitwise untouched. This sidesteps the loop-specific settle-time
problem entirely — the D011 loop's natural period is ~1257 s, so the house 600 s settle reads a transient
and an inexact result there proves *nothing*. All five states bit-exact at tick 1, including `cas_sp`
landing on `R3232_M718A_DES` by the **exact-halving lemma** (`D − 0.5*D == 0.5*D` exactly for a binary
float; `m_718B == 0.5*D` at design, so `cas_sp = D − 0.5*D = 0.5*D` bitwise). `sp_hi = 8000 > 3560.4` ⇒
the CAS clamp is inert at design. ⚠ **Display-precision probes cannot prove bit-exactness** (telemetry does
`round(x,1)`); `dyn503.py` gate 1 tests it at the raw float and ships with the code, so the commit message
legitimately claims bit-exactness.

**Tuning.** LIC-323503 keeps the OEM DCS pair **verbatim** (Kc 1.80 / Ti 120 s,
`Master_PID_Tuning_Constants.md:26`) — legal here, and *not* for flow loops, because `_ctrl_ipd` works in
engineering units and a level's EU already is %span. Process gain unchanged: `k = 7120.8/(3600·1186.8) =
1.667e-3 %/s per %op`, `wn = 5.0e-3`, `zeta = 0.30`. FIC-323405/418 retuned **Kc 1.2 → 0.4** by the house
criterion (`g = 3560.4/50 = 71.2`, `a = 0.0196`; Kc 1.2 → loop coef −0.674, alternating; Kc 0.4 → 0.442,
bracketing FIC-323402's 0.43 and FIC-328404's 0.46 precedents).

**Modelling-gap notes recorded in-code.** `m_makeup` was freed from FIC-323418 (a false binding — the OEM
service for that tag is the 718B leg) to the plain constant `A323_C005_MAKEUP`, a back-solved closure
artifact rather than a PFD stream, lawful under `ui_guidelines.md §4` with the missing-controller gap
recorded in-code. Units unchanged (kg/h).

**Current State.** Level with origin at `7c2adf9` on `master` (0/0). **Six of 25 sprint items closed**
(1, 2, 3b, 3c, 3d, 5, plus Tranche A2's 11/14/16). Tracker rescoped this session: #6 marked completed
(Tranche A2); three durable follow-on tasks created — **#16** (Tranche A3, m³/h migration), **#17**
(Tranche B, item 3a), **#18** (Tranche C, items 10/13/17). Nothing mid-edit.

**Active Files.**
- `backend/main.py` — the cascade runtime block (~L3631), `R3232_D011_*` constants (~L613), the
  `LIC_323503` init comment block (~L2517), `_fic_flow` (`avail` fully reverted; series-rejection warning
  docstring retained), `FIC_323405` boots CAS.
- `scratchpad/dyn503.py` — NEW, tracked as of this commit. The acceptance test carrying both gates
  (tick-1 raw-float anchor + 12,000 s step test); the reproduction case for both the rejection and the
  acceptance; cited from the 323D011 runtime block.
- `scratchpad/regress.py` + `scratchpad/pindiff.py` + `scratchpad/golden_pin.json` — pin gate (unchanged).

**Failed Attempts / lessons (this session + carried, still load-bearing).**
- **Series level-valve modelled as an `avail`/derate multiplier on two AUTO FICs — REJECTED empirically**
  (see Rejected register; step test: op→100, level parked 51.05 %). `avail` removed from `_fic_flow`
  entirely. Do **not** reach for it for item 3a / 328D003 either.
- **Reading tick N settle instead of tick 1 for a bit-exact claim** — a loop with a long natural period
  (D011 ~1257 s) shows a transient at the house 600 s settle; an inexact read there proves nothing. Read
  tick 1 against the boot seed instead.
- **The `avail` half-landing lesson:** a design-neutral parameter (`avail` defaulted 1.0 = 1.0 at design)
  hides its own bugs — a partial wiring left every static probe green while the bug was live off-design.
  Only a dynamic *step* test catches it.
- **Float residue is real but controller-arrested:** at 30,000 s `M_D011` sits rel −1.2e-11 off
  `R3232_D011_M_DES`; LIC-323503 now holds it to 1e-11 of SP (pre-sprint that drift had no controller).
- **IEEE-754 association is not algebra** — never re-associate an existing float expression (the
  `s.r3232_e011_M` integrand line was left byte-identical; dead `liq_e011` deleted outright rather than
  folded in).
- **`awk` range-print terminates inside a Python docstring** — use `grep -n` then `sed -n 'START,ENDp'`.
- **Error-C refined:** scratchpad helpers may not survive sessions — `ls` first (`pfd.py`/`pindiff.py`
  survived; `dyn503.py` is now tracked, so it will).
- Carried commit-mechanics traps still bite: `-F <file>` for multi-line messages (PowerShell here-strings
  break the Bash tool); always `PYTHONIOENCODING=utf-8`; `regress.py` only *dumps* the pin (gate is two
  steps); always `git fetch` before trusting `origin/*`; stage selectively by path, never `git add -A`
  (26 untracked paths must stay untouched).

**Next Steps (Tranche map, sequenced).** ~~Frontend-only batch first (no pin rehash): item 12 overlay half +
`overlays.js` duplicate-bind defects (task #15).~~ **DONE session 11** (see session-11 block). Remaining
backend batch (rehashes the pin; require `leaves: 25  keys: 15  diffs: 0` at each checkpoint): 3a, 7, 8, 9,
17, 18, 22, 23, 24(binding), 25, plus Tranche A3 (#16). **Reconciled done between sessions 10 and 11:**
items 4 (partial, m³/h flow indicators 328404/328406/328402/323402), 10, 13, 20 (AI-328701 conductivity
soft-sensor). **Likely also landed (verify before re-doing):** items 19/21 — `overlays.js` now binds
`EVAP_324.E001.PY_324201` (PY-324201) and `EVAP_324.E003.AY_324701` (AY-324701) as live VLE-inversion
soft-sensors; grep `main.py` 324 section for `PY_324201`/`AY_324701` to confirm the BPE routine exists
before treating 19/21 as open. Item 3a (#17) is blocked: it needs a 328D003 level controller cascading into
FIC-328402 (the `avail` escape hatch is disproven), still open on what drives `m_744`. **FLAG carried from
`1eb48ca`:** FIC-323402 leg `R3232_E011_M402_DES = 2931 kg/h` is ~1.9× the PFD stream-791 1534 kg/h;
reconciliation deferred (pin-breaking).

**Verification (all four gates green, re-run fresh this session before commit).**

| gate | command | result |
|---|---|---|
| Design anchor (raw float, tick 1) | `python ../scratchpad/dyn503.py` (gate 1) | **5/5 `exact True`** |
| Steady-state authority (12,000 s step) | `python ../scratchpad/dyn503.py` (gate 2) | **level → 50.0000 %, op → 50.000 off rail, FIC418 flat 50.000; FAILURES 0** |
| House design probe (8 keys, rounded) | `python …/probe328.py` | **FAILURES 0** |
| Golden pin | `regress.py <abs>` → `pindiff.py` | **leaves 25, keys 15, diffs 0** |

## 2026-07-19 (session 11): stale-handoff reconciliation + task #15 frontend faceplate hygiene

**Reconciliation — the session-10 handoff was 3 commits stale.** Session 10 recorded HEAD `7c2adf9`, but
local `master` (level with `origin/master`, tree clean apart from the ~40 known untracked paths) was already
at `cddb77d`. The three intervening commits, reverse-engineered from their messages and diffs and now
folded into the sprint ledger:

| Commit | Sprint item(s) | What |
|--------|----------------|------|
| `84315f3` | 20 | AI-328701 process-condensate conductivity soft-sensor. Inferential κ₂₅ via O'Connell / Kremser / Clausius-Clapeyron / Arrhenius / Kohlrausch; design κ₂₅ = 6.96 µS/cm. Pin `25/15/0`. |
| `1eb48ca` | 10, 13 | FIC-328402 / FIC-323402 volumetric `vol_m3h` streams + FT-329403 / FT-329407 wiring. **FLAG:** FIC-323402 leg `R3232_E011_M402_DES = 2931 kg/h` ≈ 1.9× PFD stream-791 (1534 kg/h); reconciliation deferred (pin-breaking). |
| `cddb77d` | 4 (partial) | FIC-328404 / FIC-328406 m³/h flow indicators; `vol = 1.5·(m_775 / M775_DES)`. Directive item-4 flow-to-stream verification. Pin `25/15/0`. |

The session-10 "frontend-first" sequencing was overtaken — the operator did backend items 4/10/13/20 instead.

**Task #15 (frontend-only, no pin rehash — `overlays.js` only, none of the 4 `_PIN_SRC_FILES` touched).**

- **w-suffix hygiene (the tracked "bound yet retain `w`" defect).** The `w` key-suffix convention means
  "white frame / unbound"; app.js has **no** `w`-suffix render logic (grep-confirmed) so it is a pure
  documentary label. 14 elements had been bound over sessions 3b–5 + the reconciled commits yet kept the
  stale `w`. Dropped it on all 14: `tt8008 tt8010 tt8013 ai8701 ft2404 tt3010 tt3009 tt8015 py4201 hic3605
  hv3605 pic3203 ay4701`, and `tt005w → tt3005` (de-`w`'d form `tt005` collides with the TT-322005 key on
  screen-322-1; renamed to match the TT-323005 tag + `tt3xxx` 323 convention). Each key had exactly one ref
  (its own def); collision-checked; `del:` is runtime localStorage, not static source.
- **Duplicate-bind audit (per-screen scan, `scratchpad/dupbind.js`).** 11 groups, all resolved or
  intentional — **no open defect**: the genuine two-distinct-valves class (TV-323013A/B) was already fixed
  in `c538831`; LV-324501A/B now bind distinct `.LV_324501A` / `.LV_324501B` (R2 rework); the rest are
  deliberate — explicit `// dup readout` / `// dup valve symbol` (LIC/LV-323501 recycle-line pair),
  HIC+HV faceplate pairs on one modelled handswitch value (322602, 329601/602, 323605), or documented
  single-modelled-node conflations (tt8011/tt8012 → `TT_328012`; tt8008/tt8010 → `TT_328008`; tt001/tt004
  → `C003.feed_T`). Those conflations stay under Scope-Lock (splitting them = inventing physics).

**Verification.** `node --check overlays.js` OK; re-scan → **0** bound-`w` keys remain; no new duplicate
`k` within any screen. Pin gate **not** re-run and **not required** — `overlays.js ∉ _PIN_SRC_FILES`, so
the boot-pin hash is unchanged (no backend edit this session).

**Next.** Backend batch per the reconciled Tranche map above. Before item 19/21, first grep `main.py` 324
section for `PY_324201`/`AY_324701` — the frontend already binds them as live VLE-inversion soft-sensors, so
the BPE routine may already exist. Confirm the sequence with the user given the session-10 order was
overtaken by the reconciled commits.

## Next steps (if work resumes)

1. ~~**Push** the unpushed commits to origin~~ — **DONE (session 4): pushed `e2dae58..ea07608`.**
2. ~~**Optional transient acceptance check (report §6.4)**~~ — **DONE (session 8): gate built, run,
   PASSED.** `backend/test_transient_coldstart.py` (commit `ad30d31`) drives the engine headless from
   a cold, empty, depressurised loop with the design feed lineup ON, and asserts all three criteria:

   | criterion | band | measured | |
   |---|---|---|---|
   | τ_sim | [2884, 4055] s | **3396.9 s** | PASS (2.1 % below the 3469.5 s centre) |
   | t_d,sim | ≤ 572 s | **39.6 s** | PASS |
   | P_f | [137.5, 150.5] bar g | **143.19 bar g** | PASS |

   Smith intermediates: t₂₈ = 1171.8 s, t₆₃ = 3436.4 s, n = 534 samples. Design hold stayed
   bit-exact through the harness (140.700000 → 140.700000 bar a, |Δ| = 0.00e+00).

   **CORRECTION — the line previously here ("No cold-start driver harness exists yet") was STALE and
   wrong.** `backend/tests/coldstart_probe.py` existed all along, is tracked, is a complete external
   driver, and is cited from `main.py:2882-2883`. The real gap was that it only *printed* its
   measurements and exited 0 regardless, and pytest never collected it — so the 98-test suite scrolled
   past §6.4 rather than gating on it. Session 8 *promoted* the probe (same scenario, same numbers)
   into an asserting, collected gate rather than duplicating it. Suite now **103 passed** (98 + 5).

   **Caveat, recorded not buried:** the plateau sits at 144.200 bar a = exactly `SYN_P_MAX_BARA`, so
   the trajectory is **clamped at the feed-supply-head ceiling, not freely settled**. The field
   P_f = 144.0 bar g = 145.01 bar a lies *above* that ceiling, so the sim structurally cannot reach the
   field value; it lands 0.81 bar low, comfortably inside the band. The clamp also truncates the tail
   of the approach the Smith ID reads. This is documented model law (`main.py:1531`, "PT ceiling =
   feed-supply head"), not a tuning artifact — flagged for whoever revisits the ceiling.
3. ~~**Investigate LIC-322501 startup anomaly**~~ — **RESOLVED 2026-07-03: DCS positioner/output-span
   artifact, no AUTO-logic change.** Direct-acting LIC (main.py:1934) with level below SP during
   startup commands the 0% clamp, not 102.8% → saturated-high MV is not the level PI (positioner on
   hand-jack/override/split-range). Real LV 0→30% motion already reproducible via existing MAN mode
   (main.py:2832). Bit-exact pin + conservation untouched. Closure written to report §2.
4. ~~**Merge** `fix/reactor-level-drain-and-vent-coupling` once §6.4 transient check passes~~ —
   **DONE (session 8):** gate passed (item 2 above) and was committed to the branch first, per the
   documented precondition. Merged into `master`. Working tree "clean" was defined by the user as
   *clean apart from untracked files* — the 22 untracked paths (`TECH_DEBT.md`, `_probe_*.py`,
   `graphify-out/`, Obsidian vault) were left completely alone and uncommitted, by explicit order.
5. ~~**UNRECONCILED census delta (327 tagged / 101 unbound / `ind` 51 vs the earlier 103 / `ind` 53)**~~
   — **DROPPED (session 8, user order): "Acknowledged as a non-regression tightening of the codebase.
   Drop this issue entirely. Do not spend any token overhead investigating the two ghost tags."**
   The census got *tighter*, not looser, so nothing regressed. Not investigated, by direction.
6. ~~**Cosmetic:** stale `~94124` comment on `EJ_DES_TOTAL`~~ — **DONE (session 8), commit `0ce6dda`.**
   Corrected to `~96130` at `main.py:161` (the doc's old `:162` was off by one) with a NOTE recording
   that the figure was arithmetic off the OLD 40 756 kg/h motive and is superseded by the Path-B
   tear-closure reconciliation. Comment-only; pin key rehashed as predicted, pin values did not move:
   **25 leaves / 15 keys / 0 diffs**. Note `regress.py` only *dumps* the pin — it does **not** diff.
   The gate is two steps: run `regress.py`, then diff the dump against `golden_pin.json` yourself.

## Environment

- Python 3.14.3, pandas 3.0.3, scipy 1.17.1, numpy 2.4.2. Windows 10.
- PowerShell primary (no `&&` — use `;`); Bash tool for POSIX.
- Run audits/backend from `D:\Work\Urea Simulation\backend`.
- Launcher: `launch.bat` starts `python main.py`, polls `http://127.0.0.1:8000/`, opens Chrome.
- Desktop shortcuts (OneDrive desktop): "Start Urea Simulation.lnk", "Helwan Urea Simulator.lnk",
  "urea simulation.lnk" — all target the same `launch.bat`.
