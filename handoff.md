# Handoff: Open Gaps

**Last updated:** 2026-09-02 (322E003 CCW-loss consequence chain closed end to end)

---

## 1. Documentation reconciliation — `project.md` §5.1

`project.md` §5.1 claims the Extended UNIQUAC electrolyte model (`props_nh3co2h2o.py`,
`vle_nh3co2h2o.py`) supplies the 323C003, 323F004 and 328D003 bubble points. Neither module is
imported at runtime: all ionic-section VLE uses IAPWS-IF97 pure-water `tsat` plus a frozen design
offset. Reclassify Extended UNIQUAC as a validated-but-unintegrated research module and document
the as-built method. No code risk.

## 2. Minor cleanups

- `backend/core/thermo.py` still carries a dead `EmpiricalThermo.bubble_p` placeholder with no
  caller. Remove it so it cannot be mistaken for a live fluid package.
- `backend/audit_model_compliance.py:103` asserts the CO2 feed-line pressure equals PIC-322203;
  the feed line legitimately sits behind that controller, so the assertion is wrong.

## 3. Test suite

`pytest` is **not** in `backend/requirements.txt` although all 64 `backend/test_*.py` files are
pytest modules. Install it separately (`python -m pip install pytest`) or add a dev-requirements
file.

Running the whole directory in one process (`pytest test_*.py`) aborts in pytest's teardown with
`ValueError: I/O operation on closed file` — some module closes a captured stream at import. The
per-file loop works and is what the numbers below come from. Pre-existing; reproduces on 60e7e24.

**Red list, 2026-09-02 (59 failures/errors across 64 files, 564 passing).** Every one of these also
fails on 60e7e24 — none is a regression from the drift work, which took the suite from 81
failures/525 passing to 59/564. Grouped by apparent cause:

*Re-swept 2026-09-03 after the §9 CCW work (65 files now, `test_ccw_loss_chain.py` added). Every
file produced an identical pass/fail line before and after that work — same failures, same counts —
except `test_3_scrubber_heat.py`, which moved from red to 6/6. The per-file loop is the method; the
one-process teardown abort below is unchanged.*

| group | files | note |
|---|---|---|
| `CONSEQUENCE_ROUTES` / `CONSEQUENCE_TRANSPORT` missing from `main` | `test_consequence_propagation.py` (10), `test_scenario_consequences.py` (collect) | names the transport-layer commit 60e7e24 introduced tests for but did not export |
| stale constant references | `test_equation_audit_c10_live_cp.py` (`R328_C002_T_BOT`), `test_reconcile_crowe.py` | tests reference symbols that no longer exist. `test_3_scrubber_heat.py` was in this row and is now **green** (6/6) — its failure was the CCW consequence gap, not a stale symbol; see §9 |
| missing dev dependency | `test_ctrl_routes.py` | `starlette.testclient` needs `httpx` |
| design-point residuals still open | `test_equation_audit_td014.py` (4), `test_equation_audit_desorption.py` (2), `test_equation_audit_species.py` (5), `test_equation_audit_td013_d002.py` (2), `test_scenario_coverage.py` (6), `test_g8_lp_turbine_export.py` (2), `test_transient_coldstart.py` (5), `test_hp_carbamate_recycle.py` (3), `test_lv324501_routing.py` (3), `test_trend_coverage.py` (2), plus singles in `test_c39_recycle_tears.py`, `test_equation_audit_322e002.py`, `test_g3_component_reconciliation.py`, `test_stripper_reaction_inventory.py`, `test_audit_stream_state.py`, `test_equation_audit_c10_props.py`, `test_321d003_level_switch.py` (2), `test_equation_audit_323_324.py` (2) | the same class of defect the drift work closed five of: an anchor computed on a different basis than the live path it normalises |

The last group is the productive one to work next. The method that closed the five in §4 applies
directly: probe the term at the design seed, find which side of the ratio is not 1.0, and move the
datum rather than the physics.

## 4. 323C003 two-path pressure model — open calibration question

The PT-323201 coupling now takes two independent gas sources (PFD stream 301 flash across
LV-322501, stream 302 evolved in 323E002) and carries the 2025-06-28 startup-trend field residual
on the LV-322501 valve signal at 0.122 bar per point of opening — five times the hydraulic-only
slope the model used before the retuning.

With that gain **and** the corrected 5858 kW 323E002 design duty (it was running 9127 kW at the
design seed against a stale LP-header pin), a 9-point LV-322501 opening now lifts the column ~0.5
bar, lifts the bubble point ~4 K above the 135 °C TIC-323007 setpoint, and the cascade cuts
PV-329202 hard enough that the **total overhead falls**: stream 301 rises 11.1 → 13.1 t/h while
stream 302 falls 13.5 → 6.5 t/h, so v305 goes 24.56 → 19.60 t/h.

That is a coherent closed-loop response — TIC-323007's only pressure lever is the 36 % heater
share, so it saturates against a flash-path disturbance it cannot offset — but it is worth
checking against the field trend before it is relied on. The affected assertions in
`test_c003_pressure_coupling.py` were rewritten to gate the flash path, the column pressure and
the PV-329202 cut instead of the overhead total; the reasoning is in their docstrings.

Related: the two ratios are not both exactly 1.0 at design. The flash ratio carries a 0.26 %
offset because `q_flash_avail_kw` uses the live C10 solution cp (2.5064) while `R323_Q305_DES_KW`
is anchored on the lumped design cp (2.5). PT-323201 therefore settles at 4.1000 rather than a
bit-exact 4.1; closing it means re-pinning `R323_Q305_DES_KW` on the live cp, which ripples into
`R323_LAMBDA_305` and the whole 323 design.

## 5. PT-323201 / PIC-323202 node — closed

Stream 305 has no valve on it, so 323C003 + 323E003 + 323D001 are one gas envelope. That envelope
now has a single gas-inventory ODE (generated − condensed − vented) and the column rides above the
node through the line-law head. Line-law closure is exact (0.0 %) on every lever, the gap is always
a real friction head (0.52–0.98 bar), and both pressures move together everywhere — including
LV-322501 above design, where they used to diverge. See the As-Built reference for the equations,
the three defects and the verification table.

**Consequence worth knowing about.** Closing it retired the 0.100 bar/% LV-322501 "field gain".
Regressing the 2025-06-28 trend's own 721 rows shows that number is the startup ramp, not a process
gain: whole startup (LV 0.00–45.40 %) slope +0.0980 bar/%, r = +0.983; near design (LV 35–50 %,
n = 373) slope −0.0099 bar/%, r = −0.072. PT-323201's design sensitivity to the LV stroke is now
0.0222 bar/%, the hydraulic slope. If there is a controlled step test in the DCS archive that
isolates LV-322501 at load, it would settle this properly — the ramp regression cannot.

**Still open from §4:** the 323E002 heater collapse on a large LV-322501 opening. Both pressures
now fall together when it happens, so the node is consistent, but whether the overhead *should*
fall is still the open question there.

## 6. PT-329206 retagged to PT-329207 — closed

Every 329206 tag in the simulation is now 329207: `PT-329206` on screen-322-1, `PI-329206` on
screen-329-1, and the backend `PIC_329206` faceplate (which published the same loop a second time
in barg off the same `P_LP` / `master207_sp` / `pic207_mode`, and is now merged into `PIC_329207`
as `pv_barg` / `sp_barg`).

The field references list two transmitters on the 4-bar header — `329-1 mapping and
description.md` ("2 pressure indicators PI-329206 and PI-329207"), `Mapping of the steam
system.md`, and `Urea_NormalOp_29-06-2025_Trends.md` which logs PT-329206 over 1921 samples. The
OTS does not need both: two indicators showing the same parameter add nothing to train on. Do not
"restore" PT-329206 on the strength of those documents — the single tag is the intended state.

`backend/reports/dcs_anchor_dynamics_2025-06-28.md` still says PT-329206 deliberately: it records
what the DCS workbook contained, not simulation code.

Two follow-ons, neither a defect:

- **Screen 329-1 box at x 625.** The background is a tagged HMI screenshot; that box printed
  `PI-329206` and now has no overlay, so the printed label shows with no live value. Cosmetic —
  clears whenever the screen is re-captured.
- **`BOUND_TAG_FLOOR` in `test_trend_coverage.py`.** Collapsing two tags to one dropped the bound
  count 213 → 212 by intent. The floor (217) is left untouched because that test is already red
  for unrelated reasons; reconcile both together rather than lowering it now.

### Related, and a real gap: field tags aliased to one modelled value

Sweeping `overlays.js` for indicators sharing a packet path turns up 12. Most are legitimate —
a controller and its valve (`HIC-329601`/`HV-329601`, `HIC-322602`/`HV-322602`,
`HIC-323605`/`HV-323605`, `HIC-329602`/`HV-329602`), a controller and the transmitter feeding it
(`LIC-323507`/`LT-323507`), or one parameter shown on two different screens
(`PI-329201`/`PT-329201`, `TI-321020`/`TT-321020`, and now `PI-329207`/`PT-329207`).

Four are not, and are worth a look: `TT-328011`/`TT-328012`, `TT-323009`/`TT-323C005`,
`TT-323001`/`TT-323004` and `TT-323005`/`TT-323014` are pairs of DISTINCT field thermocouples at
different points, both drawing the same modelled temperature. They will always read identically,
so any scenario that should separate them cannot. That is a modelling gap, not an HMI choice.

## 8. UI-page migration — open items on 321-1 / 322-1 / 322-2

The three screens are generated from `Urea Simulation Docs/Equipment Drawing/UI Pages/*.pptx`
(background = the slide minus the overlay-supplied shapes; overlay coords, sizes and rotations =
those shapes' own transforms). 322-1 and 322-2 were re-cut from the 2026-09-02 16:29/16:34 revision.

**Closed since the first pass:** XV-322903 is now a real backend valve (§ As-Built); the CCW pumps
carry the 329P006 A/B tags the updated slide prints, with A running and B standby; HIC-322203 is
back on 322-1 as the slide-drawn HS-322203 button; every icon overlay now lands exactly on its
symbol.

**Pump clicks now open a faceplate, they do not command the machine.** Every pump symbol in the OTS
— the 321P002 A/B button and icon on 321-1, and the 329P006 A/B overlays on 322-1 — opens one shared
START/STOP faceplate. Exactly one button is live (START while stopped, STOP while running); the
other is transparent, dim and carries a real `disabled` attribute, so the operator can never command
the state the plant is already in. The buttons send an explicit
`{"type":"pump_toggle","id":...,"on":true|false}`; `handle_cmd` reads a present `on` as START/STOP
and an absent one as the legacy toggle, so every existing caller and probe is unchanged. A third
line shows the interlock, mirroring exactly what a START will do (`CLEAR` / `TRIP 21.4 LATCHED
(clears on START)` / `TRIP 21.4 ACTIVE`). Equations and the state table are in the As-Built under
*Pump Faceplate*.

Still open:

- **The 322E003 sump does not drain after an XV-322903 excursion.** Shutting the valve floods the
  sump correctly (50.0 -> 62.5 % in 60 s), but re-opening restores design entrainment only, so the
  level holds at wherever it got to. `ejector_322f001` computes `scrub_level_frac` (the gravity
  suction head) and then does not apply it — `m_suc = capacity  # no head multiplier`. That predates
  this work; the valve just makes it easy to reach. Re-enabling the multiplier would make the sump
  a self-regulating attractor again, but it changes the design fixed point, so it needs its own pass.

- **Six stream hotspots were dropped from 322-1**, because the new drawing does not show the lines
  they sat on: `NH3_FEED`, `HP_DISCH`, `CARB_RECYCLE`, `HPCC_PROD` plus two with no identifiable
  line. The eight that remain each sit on a line carrying a tag that proves its identity.
  `HPCC_STEAM` (red, y 294) vs `HPCC_COND` (green, y 329) was resolved from `TT-329001`, which
  `main.py` documents as the shell BFW/condensate feed temperature and which leads onto the green
  line — worth a second pair of eyes.

- **The 322-1 compressor-speed widget does not sit on its marker.** The slide reserves a 63 x 54 box
  centred (96.7, 421.5); the widget is 196 x 53 and at that origin its right edge lands on the
  `AT-322701` indicator (187..266) and its bottom on the `AE-322801` chip (441..465). It is placed
  at (6, 352) instead. Either widen the marker on the slide or narrow the widget.

- **`BOUND_TAG_FLOOR` is still 217 against a live 210.** The full 212 -> 210 accounting is in the
  header comment of `backend/test_trend_coverage.py`; every difference is a slide-driven tag rename,
  nothing was lost. The floor is left untouched for the same reason as §6 — reconcile once, with
  that test's other failures.

Not a gap, but worth knowing: `ots_ov_pos` went v4 -> v5 and `ots_ov_tags` v3 -> v4, with a
carry-over that keeps operator drag positions and tag edits for the seven screens this migration did
not touch and drops them only for the three that moved (`carryOver()` in `overlays.js`).

## 9. 322E003 CCW-loss consequence chain — closed end to end

The chain now runs from the lost heat sink to the ESD and to the atmosphere, and covers both the
direct scrubber effects and the plant-wide ones. Equations, sourced constants and the measured
excursion are in the As-Built reference under *Loss of 322E003 Condensation*.
`test_ccw_loss_chain.py` covers it in four phases; `test_3_scrubber_heat.py` is back to 6/6.

What landed, beyond the four algorithmic resolutions the reference asked for:

- **HV-322604 given its hydraulic ceiling.** The valve model passed `offered x valve_factor`, so it
  would have vented all 16.5 t/h of uncondensed gas through a DN-24 / Kvs 2.1 seat and the excursion
  would have closed the boundary balance and vanished. This matches the capacity model the As-Built
  already specified for this valve (`m_vented = min(m_available, m_capacity)`), which the code had
  not implemented.
- **The CO2 delivery ceiling re-anchored.** `P_line_ceil` was `SYN_P_MAX_BARA + DP_HP_DES` = 147.7
  bar a — the HPCC's normal-operating PFD pressure used as a compressor limit. It made the model's
  own 151.2 bar a CO2-line relief unreachable (dead layer), and it self-choked the CCW excursion at
  147.7 (the scrubber's condensable make scales with `co2_scale`, so cutting CO2 cuts the pressure
  source), so trip 21.4 fired instead and the last two links were unreachable. It is now the loop's
  160 bar g mechanical rating plus the design feed dP. PIC-322203's setpoint was written as a rule
  ("one feed-dP above the ceiling"), so it moved with it and stays dormant as intended.
- **SV-32201**, the synthesis-loop safety valve at the 160 bar g mechanical design, as a real
  outflow with `SYN_PSV_LIFT` / `TOXIC_RELEASE` flags and a published NH3 release rate.
- **A froth-hunt overlay on LT-329501** alongside the swell: the DP cell reads high *and* unsteady
  while the column boils (two incommensurate periods off the plant clock, so it is deterministic and
  replays identically), both scaled by the same void fraction and both identically 0 at design.
- **SV-32253 and LP-section overload on 322C001** — the 322C001 datasheet names both this valve
  (N11, DN 100, 30 barg design) and this exact upset. `LP_ABSORBER_OVERLOAD` when the un-absorbed
  gas exceeds what PV-322201 can pass at full stroke, `LP_ABSORBER_RELIEF` when the SV lifts.
- **Three engine-killing raises fixed**, all made reachable by the excursion and all pre-existing:
  `evap_w_eq` handing the Extended-UNIQUAC solver an out-of-window state (and a second failure mode
  *inside* the window — "no root within urea mass fraction [0,1]"); `_cq_packet` passing a
  non-finite temperature into `consequence.make_stream_packet`; and `react_nc_ratio` returning 6.1e9
  on a post-trip loop with the carbon gone (now saturated at the AT-322701 analyzer span).

Still open, and worth a decision:

- **Time to trip is 3 h 50 min, and `C_loop` is the only number that sets it.** The ramp is
  `SYN_P_PHASE_GAIN * m_uncond / C_loop` less the boundary pushback; `SYN_LOOP_C_KG_PER_BAR` = 1500
  kg/bar dominates. That constant is calibrated to the *cold-start fill* (it sets the emergent FOPTD
  tau the 2025-06-03 field trend anchors at 57.8 min) and is ~25x a vapour-space-only estimate for
  the loop (~75 m3 at d(rho)/dP ~ 0.8 kg/m3/bar gives ~60 kg/bar). A real total loss of condensation
  is minutes, not hours. Moving it means re-deriving the cold-start anchor and re-checking
  `test_transient_coldstart.py` and section 6.4, so it is left alone and the emergent time reported
  as it stands.

- **The design hold is only exact at the production tick.** At `dt = 0.1 s` PT-329201 reads
  140.70024 bar a after 3000 s. On the `_systest` default of `dt = 2.0 s` the same seed walks a
  ~1 bar, ~6000 s wobble from the 322E002 level integrator's Euler truncation. Not from this work —
  with `SYN_P_PHASE_GAIN` forced to 0 and the HV-322604 ceiling forced off the trajectory is
  bit-identical, and the new terms read exactly zero at every sample. But every `dt = 2 s` system
  test is grading a trajectory the plant never runs, and any test wanting a tight PT band has to say
  which tick it means. Worth a pass over the harness before more design-point residuals are chased
  at section 3.

- **HV-322604 is modelled sub-critical, and the field description says it is choked.** Its pressure
  ratio is ~4/140 = 0.028 against a critical ~0.5, so "mass flow becomes independent of downstream
  pressure fluctuations... strictly a function of upstream pressure, valve opening area, and fluid
  density" (`References/HV-322604 description.md`). The model uses the sub-critical `sqrt(dP)` form
  and the new hydraulic ceiling carries the "cannot pass more than its capacity" half of that
  physics. The ISA 75.01.01 choked model already exists in `consequence.py` and is on the §7
  enhancement list; wiring it here is the proper close.

- **The As-Built section *322E003 LP/MP Recycle-Carbamate Wash Cascade* describes a scrubber that is
  not the one in `main.py`.** Its `capacity_ratio` component-wise absorption model, the `q_wash`
  cold-wash energy sink and the `LP_absorber_load` diagnostic have no counterpart in
  `scrub_322e003`; the HV-322604 capacity model in that section is the only part now implemented
  (this work). Pre-existing. Reconcile the section with the code, or implement the rest.

## 7. Enhancement opportunities (optional)

- Integrate the Extended UNIQUAC electrolyte model for rigorous HP synthesis VLE.
- Wire the choked-flow model (`consequence.py`, ISA 75.01.01) into `main.py`.
- Experimental validation of the Unit 324 vacuum VLE (0.02–1.0 bar, far below the published
  35 bar floor).
- Extend stream coverage beyond the 55 of 163 PFD streams currently published.
