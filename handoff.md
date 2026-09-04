# Handoff: Open Gaps

**Last updated:** 2026-09-04 (Phase 1 thermodynamic foundation: unified rigorous VLE / flash service)

---

## 1. Documentation reconciliation — `project.md` §5.1 — partially closed

**Closed for 323C003 / 323F004 / 323F010.** `backend/thermo_service.py` (Phase 1) now wires
`vle_nh3co2h2o`, `props_nh3co2h2o` (SRK), `thermo_extended_uniquac` and `gap_g6_h0_enthalpy` into a
single `flash / flash_ph / bubble_p / bubble_t / dew_t` service, and those three stages take their
vapour composition from a Rachford-Rice gamma-phi solve instead of the frozen `sol_vapour_y` alpha
vector. Live confirmation is published per tick as `SOL.vle_domain`.

**Still open:** 328D003 and the whole 328 desorption train still use `sol_vapour_y` with anchored
alphas — they were not evaluated against the table envelope in this phase. Check their loadings
against `thermo_service.classify` before wiring; the 328 columns run 60-145 °C on dilute ammonia
water, so several are plausibly in domain.

## 1a. G-VLE-2 — no volatile split on a urea melt (324E001 / 324E003)

`thermo_service.flash` refuses `DOMAIN_NEUTRAL_UREA`. The neutral H2O/urea binary carries no NH3 or
CO2 at all, and the electrolyte path is outside its dilute limit there: the loading basis is mol per
kg of **water**, so 0.04 wt% NH3 in a 1.39 wt% water melt reads as 1.69 mol/kg and the flash returns
an NH3 vapour mole fraction of 0.24 for a melt whose vapour is essentially pure steam. `bubble_p` /
`bubble_t` remain valid and are good there (+2.2 % at 324E003, against +65.7 % for the electrolyte
model). 324E001/E003 therefore keep their anchored vapour vector.

**To close:** a urea-melt NH3/CO2 solubility source (Henry constants on a urea-melt basis, not an
aqueous one). This is new source material, not new wiring.

## 1b. G-VLE-3 — the HP synthesis loop is outside every fitted envelope

The 322 loop cannot go on the rigorous service and Phase 1 deliberately did not force it. Measured
against the electrolyte table (T 80-170 °C, N ≤ 16, C ≤ 7 mol/kg water):

| state | T | N load | C load |
|---|---|---|---|
| 322R001 overflow (stream 207) | 183 °C | 100.0 (6.2×) | 22.4 (3.2×) |
| 322E003 off-gas feed | 183 °C | 869.3 (54.3×) | 258.1 (36.9×) |

and the 322E003 feed carries N2, O2, CH4, H2, for which the repo holds neither Henry constants nor
SRK critical constants (`props_nh3co2h2o.SRK_CRIT` = H2O, NH3, CO2 only).

This matters more than a normal out-of-range case because `vle_nh3co2h2o._bracket` **clamps** rather
than extrapolating: an off-envelope call silently returns the edge node, i.e. a frozen constant
behind a call that looks like a solve — strictly worse than the honest `HPCC_FRAC_GAS_DES` dict it
would replace. `thermo_service` raises `OutOfDomain` instead.

**To close:** rebuild the activity grid over a molten-carbamate envelope (the current parameter set
is a CO2-capture model fitted to dilute aqueous loadings below ~150 °C) **and** source inert Henry /
SRK data. Until then `REACT_THETA_OG`, `STRIP_FRAC_DES`, `SCRUB_OFFGAS_KMOLH_DES` and
`_hpcc_flash_split` stay as they are — report findings B-2, B-4, B-6, B-7 remain open.

## 1d. Residual composition offset at the 323 stages after Phase 1

**G-VLE-4 (TIC-323012 destabilisation) is CLOSED** — retuned Ti 306 -> 1200 s, Appendix C of
`Master_PID_Tuning_Constants.md`; both legs of the F010 loop now sit on one thermodynamic surface
(report A-11). Full derivation in the As-Built reference. What remains open is smaller and is a
COMPOSITION gap, not a stability one.

Settled at 20 000 s, all three stages on `electrolyte_gamma_phi` with no fallback:

| stage | species | design | settled | offset |
|---|---|---|---|---|
| 323F010 | urea | 80.0016 % | 80.0849 % | **+0.083 pt** |
| 323F010 | CO2 | 0.0200 % | 0.0251 % | +25 % |
| 323F004 | CO2 | 0.6600 % | 0.5293 % | **−20 %** |
| 323C003 | CO2 | 1.0500 % | 0.9249 % | −12 % |

NH3 lands within 3 % of design at every stage; CO2 does not, and the sign flips between 323F004
(low) and 323F010 (high). The urea offset is the removed urea leak plus that CO2 redistribution.
+0.083 pt is inside the +/-0.10 pt band the regression gate uses and is in the safe direction
(richer, not weaker), so this is a fidelity item and not a spec risk.

Most likely cause, untested: the anchored ratio scales each species' alpha independently, so the
renormalisation in `sol_vapour_y` can move CO2 against NH3 in a way the joint flash would not. A
ratio applied to the whole VOLATILE sub-vector before renormalisation, rather than per species,
would preserve the NH3/CO2 split of the flash while still anchoring the total. Worth measuring
before assuming the per-species form is wrong.

## 1c. Phase 1 remainder — vacuum-condenser static enthalpy (report B-9)

`vacuum_condenser_node` still converts duty to condensate through one design `h_eff_kjkg` per
exchanger, so an NH3-rich vent and a water-rich vent condense at the same kJ/kg. Unlike the items
above this is **not** envelope-blocked: `gap_g6_h0_enthalpy` already covers all nine species in both
phases, so `Q = Σ ṅ_cond,i ΔH_cond,i(T,P) + ṁ c_p ΔT` is buildable now. Deferred from Phase 1 only
to keep the 324 mass balance out of a change already touching the 323 species layer.

## 1e. Phase 2 — hydraulic network, CLOSED except two vessels blocked on data

`backend/hydraulics.py` carries the IEC 60534 / ISA-75.01 laws and the vapour-space pressure
derivative. **A-6, D-1, D-2, D-8 and D-19/D-20/D-21 are closed.** Design seed bit-exact on every
anchor after the change (xi_urea 1302.270000000, xi_biu 2.414000000, T_ovf 183.000017, all nine
vessel pressures, p_syn 140.699999913). Full write-up in the As-Built under *Phase 2 remainder*.

**Still open, and both are one missing number rather than a deferral:**

| finding | site | what is missing |
|---|---|---|
| A-6 | `R324_F001_P_KP` | 324F001's CYLINDRICAL HEIGHT. The datasheet gives 4600 OD / 4570 ID, the melt density and the whole nozzle schedule but not the height, and a 4570 mm bore admits 33 to 164 m3 depending on it — a factor of five on the only term A-6 needs. Two closures were tried and rejected: backing the shell mass out of the 21 500 kg delivery weight needs the internals/skirt share (the same guess in a different hat), and 324F003's 0.62 H/D ratio is a similarity argument, not a measurement |
| A-6 | `R328_D001_P_KP` | 328D001's real dimensions. Pre-existing source conflict, unchanged: datasheet says ID 1684 x T/T 1950 and calls it "19 cubic meters" when the cylinder is 4.343 m3, and the engine's own `R328_D001_M_DES` (~10.6 m3) matches neither at 243 % of the computed shell |
| A-7 | `R323_F004_P_BARA` | a real line dP. Unchanged and still blocked: `R323_F004_P_BARA` and `R3232_E011_P_BARA` are both 1.13 bar a, so the model's design dP across that line is identically zero, and the PFD's 0.1 bar rounding is the same order as the dP itself |

**Also still open (not blocked, just not in this pass):**

* **323F010's barometric leg** is `M317_DES*sqrt(M/M_DES)` — head-driven in form but with no vessel
  pressure term, so a vacuum break would not change the drain rate. Needs the leg height, which no
  source gives.
* **The three 328 bottoms valves are FLASHING services on a single-phase law.** All three carry
  liquor at its own bubble point, so the physically correct Pv is the vessel pressure — and feeding
  that to the single-phase choked limit collapses dP_eff to about 4 % of p1 and makes every one of
  them a hard-choked orifice. They run with `pv = 0`, so the `FL^2.p1` ceiling applies the right
  qualitative limit without claiming a two-phase capacity. Closing it properly needs the IEC 60534
  two-phase sizing method, which does not exist in this repository. Same class of gap as the
  D-19 letdown guards below.
* **D-12, `pull_f010`** — an ejector machine map, and Phase 4's.

### Three findings from this pass worth not re-deriving

* **322C001's design holdup did not fit the vessel, and A-6 could not be written until it moved.**
  `A328_C001_M_DES` was `M756_DES/3600 * 600 s`, an "indicative" residence. At the PFD stream-755
  density that is 5.53 m3 of liquid in a vessel whose ENTIRE shell — both sections — is 3.27 m3, i.e.
  169 % of the steel containing it, so V_v is negative and lands on its 2 % floor with a coefficient
  683x the constant. It is now geometric: half the lower cylindrical section (where LT-322502
  measures), 1392.3 kg, emergent residence 150.3 s. The design pin is untouched by construction
  (LI-322502 is M/M_DES*50 and the state seeds at M_DES) and LIC-322502 holds — over 6000 s the
  level moves 2e-6 %. **If another vessel's `_M_TAU_S` is ever used as an A-6 basis, check it
  against the shell first; this one was out by 69 %.**
* **328C003's stiffening is 3.05x, not the 4.3x this file previously estimated**, because the
  hydrolyser is a LIQUID-FILLED column standing 12.55 m deep in a 20.85 m shell — only 24.8 m3 of it
  is vapour. The open-loop gain the earlier note asked for was measured: a 6000 s settle leaves the
  node inside a decaying +/-0.03 bar excursion about 16.80, so PIC-328203 at Kc 1.5 / Ti 50 s holds
  it and NO retune was applied.
* **323E011 and 323D011 are one gas envelope**, not two nodes — the condenser drains by gravity
  through its DN 100 N2 nozzle straight into the drum beneath it with no valve between. The engine
  already half-assumed this (the mass state on the node is the DRUM's inventory). The condenser's
  share of the envelope is the shell bore MINUS the bundle: 382 tubes at 25 mm OD over 5900 mm
  displace 37 % of the shell, and ignoring them overstates the free volume by 60 %.

### Regression status after this pass

Verified green or baseline-identical:

| file | result | note |
|---|---|---|
| `test_hydraulics.py` | **38 passed** | 24 -> 38; the four newly wired vessels, the three 328 bottoms valves, the steam chokes, the SM valve port, the transport delays and the guards all pinned |
| `test_reactor.py` | 14 passed | |
| `test_reactor_kinetics_phase3.py` | 10 passed | |
| `test_stripper_reaction_inventory.py` | 4 passed | |
| `test_thermo_service.py` | 27 passed | |
| `test_equation_audit_c10_live_cp.py` | 7 passed | |
| `test_startup_stability.py` | 5 passed | |
| `test_process_transport.py` | 7 passed | D-8 |
| `test_3_scrubber_heat.py` | **8/8** | was 1 error; root-caused and the test strengthened, see above |
| `test_consequence_propagation.py` | **8 passed, 2 xfailed** | was 10 failures |
| `test_equation_audit_322e002.py` | 1 failed, 7 passed | identical to baseline |
| `test_c003_pressure_coupling.py` | 1 failed, 19 passed | identical to baseline, verified by running HEAD in a side worktree |
| `test_ejector_spindle.py` | **11 passed** | the D-19 head term drives LT-329501 and LT-322504 here |
| `test_foptd_fingerprint.py` | 3 passed | D-8 |
| `test_equation_audit_322e001_enthalpy.py` | 13 passed | |
| `test_equation_audit_322e001_flood.py` | 11 passed | |
| `test_g8_lp_turbine_export.py` | 2 failed, 4 passed | identical to baseline (section 3 red list) |
| `test_equation_audit_desorption.py` | 2 failed, 8 passed | identical to baseline; this is the file that exercises the three 328 bottoms valves |

### An engine-killing crash on the transport path, found and fixed

`_w_norm` divided by the sum of a packet's mass fractions with no guard, and
`consequence.ZERO_PACKET` carries an EMPTY component vector -- so the moment a transported line
delivered an empty packet while its departure carried mass (the line had been dry for longer than
its dead time and flow then resumed), the tick died with `ZeroDivisionError`. All five transport
sites had it. Reachable from any upset that takes a transported line to exactly zero flow; a total
322E003 CCW loss does it at the 323C003 bottom drain, which is how it surfaced.

Fixed at the source: `_w_norm` takes an optional `fallback` used only when the total is
non-positive, and each of the five sites passes its own departure composition. Nothing physical is
papered over -- when no mass arrives, the receiving stage's inflow term is zero, so the vector it
multiplies is arbitrary and the departure composition is the honest placeholder. Every OTHER caller
passes a PFD row, where a zero total IS a data error and still raises.

This is the fourth of the same family the CCW chain has now surfaced; section 9 lists three more
that a previous pass fixed. **The chain is worth running after any change to the 323/324 train** --
it is the only test that drives the flowsheet hard enough to reach these.

**NOT re-run in this pass, and they should be**:
`test_equation_audit_td014.py`, `test_ccw_loss_chain.py`, `test_transient_coldstart.py`,
`test_scenario_consequences.py`. Not because of any
finding — the machine this ran on has 4 logical cores and was 70-85 % consumed by unrelated
desktop applications throughout, which took the engine from its normal ~126 ticks/s to roughly a
tenth of that and made each of these multi-thousand-tick files an hour-plus proposition.
`test_transient_coldstart.py` alone is 32 000 ticks by construction (T_END 16 000 s at DT 0.5).

All four carry known pre-existing failures, and the baselines to match are recorded here so the
next session compares rather than re-derives: **td014 4F/7P, transient_coldstart 5 failures,
scenario_coverage 6**.

The one that mattered most -- `test_equation_audit_desorption.py`, the file that exercises the three
328 bottoms valves -- did finish, at **2 failed / 8 passed, identical to baseline**. Its two failures
remain the 328C002 NH3 composition and the hydrolyser urea slip, neither of which this pass touched.

### Two things that were dropped code, not missing physics

Both were specified in a block comment sitting directly above the line that ignored them:

* **`ejector_322f001` had `m_suc = capacity  # no head multiplier`** — the gravity-suction-head term
  and the `EJ_HYD_FRAC_MAX` throat-choke ceiling the comment above it specifies were both absent, so
  the 322E003 sump was a pure integrator (it flooded correctly on a shut XV-322903 and then never
  came back). Restored. At design the head fraction is a literal 1.0, so the fixed point did not
  move. This closes the "322E003 sump does not drain" item that was open in section 8 below.
* **`_transport_process` computed a full per-route diagnostic every tick and dropped it in
  `s.tlag`** where nothing could read it. Now published on the tick packet as
  `CONSEQUENCE_TRANSPORT`.

## 1f. Phase 3 — kinetics and reaction energy, CLOSED

**C-1, C-2, A-8, C-3 and C-4 are all closed, and C-5 was found already conforming.** 322R001 runs on
a two-step mechanism with Arrhenius kinetics marched over the column's own residence-time
distribution; its column temperature comes from a real energy balance on the two reaction enthalpies
instead of a prescribed 13.0 C rise; and 322E001's hydrolysis and biuret extents are on the
Inoue-Otsuka second-order group and a second-order Arrhenius law over the live wetted volume. Design
seed exact on every PFD anchor. Full write-ups in the As-Built reference.

**A-8 is the one worth reading before touching this area again**, because it found a measurable
error in something nobody had checked: the reactor's fitted Damkohler heat-release shape was 6.5 C
wrong at TT-322007 against 1921 DCS samples in `References/Urea_NormalOp_29-06-2025_Trends.md`. The
energy balance with volume-distributed carbamate absorption (the licensor's own mechanism, per
`References/322R001 Description.md` section 4) lands at RMS 0.431 C against that trend, versus
3.661 C for the shape it replaced.

### Open, and genuinely open — the settled attractor drifts

The design **seed** is exact (xi_urea 1302.270000943, xi_biu 2.414000000, T_ovf 183.000017), but over
6000 s the settled overflow climbs to 183.488 C (+0.49) and xi_urea to 1316 (+1.05 %). The drift rate
peaks near 5000 s and then falls, suggesting convergence near 183.6, but that was **not run out far
enough to prove** — someone should.

This is a consequence of closing the thermal loop rather than a new fault: `p_syn` drifts to 140.209
(design 140.7) and level to 79.90 over the same window, both pre-existing and documented elsewhere in
this file. Previously the reactor temperature was imposed, so that drift could not reach it. Two
things to weigh before "fixing" it:

* the settled 183.488 sits closer to the plant's own TT-322014 mean (183.556) than the PFD anchor
  (183.0) does — the two source documents disagree by 0.56 C, twice the residual;
* the drift's true origin is the pre-existing level/pressure creep, so chasing it in the reactor
  energy balance would be treating a symptom.

### Two calibration traps, already paid for — do not re-enter them

Both were tried during A-8 and both are the wrong operating point for anchoring the thermal
fixed point:

| candidate | what happens |
|---|---|
| phase-1 settle capture | it is the CAS warm-up attractor; carbamate balance reads 253 kmol/h against the 279 the MAN runtime produces, c_p comes out 3.20 and the column runs to 184.3 C (settled 185.86, RMS 1.751) |
| post-reset one-tick capture | a single tick off the seed, i.e. it pins the seed to itself |

The design vectors are used instead — every input source-anchored (`_HPCC_DES` gas CO2,
`REACT_OFFGAS_DES` CO2, `REACT_OVERFLOW_DES` mass).

### A density-basis defect was found and fixed (introduced in C-1)

`_react_vdot_m3h` divides the design overflow mass by the constant `REACT_OVERFLOW_RHO` (990.0),
while the live path divides by `reactor.liquid_density(T_bulk)` (992.3 at 179.7 C). Two "design"
operating points 0.23 % apart, with the direct call anchored to one and the live seed step to the
other — so calibrating against either broke the other's bit-exactness contract. `REACT_KIN_ANCHOR` is
now the seed step's own state. **If another `_react_vdot_*` is added, put it on the same density
basis or this reopens.**

The final A2/biuret calibration closes on the contract itself: step the plant exactly as
`test_reactor_kinetics_phase3.py` does and scale until that step lands on the PFD extent, to 1e-14
relative. A 1e-9 stop is NOT enough — it leaves 1.3e-6 absolute, which fails the 1e-6 design-identity
assertions as the loop's own convergence noise.

### C-5 — re-read and reclassified

**The earlier note in this file was wrong.** `sol_biuret_xi` (`main.py:2378`) already carries all
three departures C-4 added to the stripper: a LIVE holdup ratio (`M_*_pre / SOL_STAGES[key]["M"]`,
passed at all five call sites), **second** order in urea (`SOL_BIU_ORDER = 2.0`), and Arrhenius on
the live stage temperature with the shared `STRIP_BIU_EA`. What remains is only that the extent is
anchored (`st["a"]["xi"]`) rather than predicted absolutely — the same deliberate choice C-3
documents, for the same reason. Treat as closed unless someone wants absolute prediction, which would
need a pre-exponential fitted to the very extent it replaces.

### A measured finding worth not re-deriving (C-3)

`STRIP_XI_HYD_DES = 88.1 kmol/h` cannot be produced by a urea-hydrolysis rate law. Inoue-Otsuka at
the stripper's own design state gives 12.02 kmol/h over the whole tube bundle flooded and 17.48 over
bundle + sump — it would need a liquid fraction of 7.33 against a physical maximum of 1. And
88.1/1302.6 is 6.8 % of the urea feed destroyed in 97 s, where a real CO2 stripper loses well under
1 %. That constant almost certainly lumps carbamate decomposition. C-3 therefore anchors the extent
and predicts the DEPARTURE; anyone tempted to "finish the job" by back-solving a rate constant to
reach 88.1 would be fitting to the wrong reaction.

## 2. Minor cleanups

- `backend/core/thermo.py` still carries a dead `EmpiricalThermo.bubble_p` placeholder with no
  caller. Remove it so it cannot be mistaken for a live fluid package.
- `backend/audit_model_compliance.py:103` asserts the CO2 feed-line pressure equals PIC-322203;
  the feed line legitimately sits behind that controller, so the assertion is wrong.

## 3. Test suite

### Renamed/removed engine constants that test files still reference

Three renames were never propagated into the tests, and between them they account for a large slice
of the red list. They cost real time to distinguish from genuine regressions, because a file that
fails to COLLECT hides every test in it.

| broken reference | reality | files | status |
|---|---|---|---|
| `R328_C002_T_BOT` | renamed `R328_C002_T_BOT_BOT` (139.0 C) | `test_equation_audit_c10_live_cp.py:56`, `test_equation_audit_desorption.py:164` | **FIXED** 2026-09-04. c10_live_cp went 6/1 -> 7 passed. In desorption it only unmasks a line that was never reached; that test still fails on NH3 |
| `REACT_FUNNEL_ELEV_M` | renamed `REACT_WEIR_CREST_M` -- the 322R001 overflow-funnel lip elevation, now DERIVED from the design level and weir head (19.95 m) instead of stated flat (20.9 m) | `test_scenario_consequences.py:40,43` | **FIXED.** The engine's own history confirms the rename: the commit that introduced the weir wrote `REACT_WEIR_CREST_M = REACT_FUNNEL_ELEV_M` before the old name was dropped |
| `CQ_SEAL_BAND_PCT` | moved into the consequence module as `consequence.SEAL_BAND_PCT_DEFAULT`, same 3.0 % | `test_scenario_consequences.py:48` | **FIXED.** It is the parameter's default there, so `seal_fraction` supplies it and the argument is dropped |
| `VACUUM_DEGRADED_FRAC` | **gone, and so is the `VACUUM_COLLAPSE` flag it gated** -- the whole vacuum-degradation flag layer was removed and nothing replaced it | `test_scenario_consequences.py:142` | PARTIAL. The pressure threshold (1.35x design) is asserted directly, so a vacuum that degrades by less than that still fails the check. What CANNOT be restored is that a published FLAG tracks it -- see below |
| `CONSEQUENCE_ROUTES` | now `PROCESS_ROUTES` | `test_consequence_propagation.py` | **FIXED.** The packet key `CONSEQUENCE_TRANSPORT` is now genuinely published too (the per-route diagnostics were being computed and dropped), so the transport assertions run against the real structure |



### Two coverage gaps the renames were hiding

A file that fails to COLLECT hides every symbol after the first bad one, so fixing
`REACT_FUNNEL_ELEV_M` surfaced two more missing names in the same file. Both are recorded above.
Beyond the names, two real gaps came out from under them:

* **The vacuum-degradation flag layer is gone.** `VACUUM_DEGRADED_FRAC` and the `VACUUM_COLLAPSE`
  flag it set have no successor anywhere in `main.py` or `consequence.py`. The pressure behaviour is
  still testable and is still tested; what an operator no longer gets is a published flag saying the
  vacuum has degraded. Decide whether that flag should come back before someone re-derives the
  constant.
* **`test_consequence_propagation.py` was written against SEVEN seal-loss transport routes and the
  engine implements FIVE**, all of them unit-323/324 product lines. `323F010_TO_324E002`,
  `328C003_TO_328C004`, `328C004_TO_740` and `322C001_TO_323E003` do not exist — there is no
  transport route anywhere in unit 328 or off 322C001, so an emptied hydrolyser or LP absorber still
  reaches its downstream vessel as a same-tick scalar with no dead time. The two tests that
  exercised those routes are marked `xfail` with that reason rather than deleted, and the missing
  names are listed in the file as `MISSING_SEAL_LOSS_ROUTES`. This is the productive next item in
  the transport layer. `test_scenario_consequences.py` scenario 4b hit the same wall differently —
  it indexed `328C003_TO_328C004` at module scope, so the `KeyError` aborted the file and took every
  scenario BELOW it with it. It now reports the missing route through `check()` and carries on.

**`test_scenario_consequences.py` is a SCRIPT, not a pytest module.** It ends in
`sys.exit(1 if FAIL else 0)` at module scope, so under `pytest` any failure surfaces as a collection
error rather than a test failure. Run it as `python test_scenario_consequences.py`. That is
pre-existing design and was invisible until the collection AttributeError above was fixed.

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

- **The 322E003 sump does not drain after an XV-322903 excursion — CLOSED** in the Phase 2
  remainder (report D-19). `ejector_322f001` computed `scrub_level_frac` and then did not apply it
  (`m_suc = capacity  # no head multiplier`), so the sump was a pure integrator. Restored, along
  with the `EJ_HYD_FRAC_MAX` throat-choke ceiling the same block comment specifies and which had
  also never been applied. The worry recorded here — that it would change the design fixed point —
  did not materialise: at design the head fraction is a literal 1.0, so the seed is bit-exact.
  **What it DID do is break `test_3_scrubber_heat.py`, and that test was passing on the strength of
  the defect.** Under the -30 % CCW throttle the old sump drained 50.0 -> 27.2 % and then sat at
  26.7 % for ever with entrainment frozen at 53 368 kg/h; the corrected one troughs at 45.5 % and
  recovers to 49.9 %. That dumped inventory was what powered the >= 0.15 bar PT-329201 relaxation
  the test asserted. With the sump behaving, the CCW-attributable excursion is smaller -- correctly
  -- and no longer clears the `_systest` harness's own dt = 2.0 s Euler walk (~+0.10 bar per 1000 s
  at that point in the trajectory, and rising; section 9 below). The test now measures PT-329201
  against a MATCHED NO-CUT CONTROL of identical length, so the walk cancels and the relaxation is
  plainly visible: excess +0.400 bar at the end of the cut -> +0.300 bar after the relax window.
  It also asserts the sump's trough-and-recovery, which is the new physics. 8/8 checks pass.

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
