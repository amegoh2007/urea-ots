# Handoff: Open Gaps

**Last updated:** 2026-09-16 (A-6, A-7, A-11, A-17, A-13, B-2, B-9, B-13, D-4, D-11, D-12, D-14, D-15, D-16, E-2, MSPAN_504, the thermo-memo path dependence and the 323F010 urea carryover closed; A-2 step 1 closed, A-2 now PARTIAL)

---

## 0. Heuristic Eradication Report — open after the 2026-09-15 re-audit

`docs/analysis/HEURISTIC_ERADICATION_REPORT.md` §0a is now the authoritative per-finding status:
34 closed, 9 partial, 0 blocked, 2 reclassified, 28 open. The original body still carries
pre-Phase-1 anchors; do not act on them without the ledger. A byte-identical copy sits in
`References/Gaps Closure/`.

* **A-2 is PARTIAL: step 1 closed (As-Built *Phase 5i*), and every kg of the remaining tear is placed.**
  The 322E003 vent is its inerts saturated at PFD 204 (1 708.3 kg/h), the overflow is PFD 206, and
  the motive carries PFD 116's CH4/H2/N2/H2O. `REACT_TEAR_DES` is now +2 107.5 kg/h: the motive's
  surplus over PFD 116 (NH3 117.5 kmol/h, 2 004 kg/h -- the plant basis, 42 762 against 40 756 kg/h),
  the stripper top's 127 kg/h over PFD 201, and 4.6 kmol/h of mass-neutral urea-extent bookkeeping.
  The credit is +2 024.9 kg/h; its 82.6 kg/h gap to the tear is the scrubber washing with PFD 308
  (36 915) while the boundary counts the 323E003 draw (36 835.2), plus 2.7 kg/h of rounding. **Still
  do not delete the credit on its own** (measured before A-2: PT-329201 -1.45 bar/h). The surplus has
  no exit: the vent is saturation-limited, and the 323 section rides LV-322501 bottoms MASS at the
  PFD 208 composition, so a bottoms stream carrying 2 t/h of NH3 would reach it as 1.5 % more of
  everything. Closing the tear takes either a composition-live 323 feed or the PFD 116 motive (the
  user chose the plant basis on 2026-09-16, so the first).
* **322C001 needs an absorber law, and the data for a rate-based one is now in hand.** Its uptake is
  the boot-pinned `A328_PHI_ABS` fraction of the off-gas mass, split on PFD 204 - 797 (NH3 89.3 /
  CO2 62.0 / H2O -21.3 kg/h), so the slip is a ~2 % residual of two proportional terms. A saturated-
  inert vent was written, measured and reverted: it leaves no capacity for the CCW-failure breakthrough
  to SV-32253. **Geometry, verified on the scans 2026-09-17:** the as-built arrangement drawing
  (UD-AU-322-DZ-0007-001 rev 02) and the column datasheet (UD-AU-322-EC-0007) agree: lower bed
  1 500 mm in the ID 922 section, sprayer N4 (322P002 liquor, stream 755); upper bed 1 000 mm in the
  ID 576 section, sprayer N5 (CPL). The Rauschert packing datasheet (UD-AU-322-DZ-0008-001) gives
  Raflux 25-10 metal, a = 250 m2/m3, void 0.95, but no HETP. The purchase spec's 1.63 / 0.85 m
  layers are order quantities. That is enough for Onda (1968) transfer units per bed. What is still
  missing is the back-pressure: stream 755 is 4.17 % NH3 / 3.81 % CO2 at 40 C, and the gamma-phi grid
  starts at 80 C. The props module has Rumpf-Maurer Henry constants (273-433 K) and the speciation
  equilibria, so a dilute-speciation back-pressure is buildable. Without it a transfer-unit law
  absorbs a breakthrough it should not. PFD 797's H2O (2.28 mol%) is water's saturation at 46 C /
  3.9 bar a with activity ~0.89, so the vent water is a saturation law, not a split.
* **PFD 797 does not enter 323E003, and the engine's 323E003 inlet it stands in for is unidentified.**
  797 is 322C001's vent to atmosphere through PV-322201 (Mapping of Absorber unit.md:9; datasheet N3
  "to Atmosphere Vent"), 59.32 kmol/h x MW 26.6 = 1 578 kg/h (the printed 1 758 is a digit swap).
  The engine feeds `R3232_M797_DES = 1758` into 323E003 as "inert-laden recycle", while 322C001's
  live `vent_c001` leaves to nowhere. On the PFD rows 797 cannot be a 323E003 inlet: 305 brings
  0.79 kmol/h N2 and 321 vents 0.83, where 797 would add 44.6. PFD 321 is 1 323 kg/h (50.29 kmol/h x
  MW 26.3; the "132.3" in the 323E003 datasheet summary is the misprint, and 323E011 closes on
  1 323). Without 797, 323E003 is short **1 819 kg/h**: 305 + 718B + 776 = 36 419 against 308 + 321
  = 38 238. Per species that is NH3 366, H2O 1 380 and CO2 62 kg/h, an ammonia water of ~20 % NH3
  that no 1.5-2.2 t/h PFD row matches. So the phantom 797 carries roughly the right mass as the wrong
  substance (inerts that "condense" in the gas envelope). Removing it means finding that inlet first
  (a 328 / 323D002 recycle is the likeliest), then re-anchoring `R3232_E003_LAMC`, `M_COND_DES`, the
  envelope capacitance and the 321 split.
* **Smaller A-2 leftovers.** (1) `REACT_XI_UREA_DES` 1 302.27 is net of biuret, while the reactor's
  stoichiometry subtracts biuret again; PFD 205 -> 207 imply a gross 1 306.9 (the 4.6 kmol/h above).
  (2) SV-32201's relieved NH3 fraction and its API 520 MW are read off the 322E003 vent vector, which
  is now 5 % NH3 by mass; the PSV taps the loop's vapour space, which the reactor off-gas represents
  better. (3) `SCRUB_HV604_GAMMA` 1.30 was chosen for an NH3-rich gas; the PFD 204 vent is nearer 1.38
  (choked either way). (4) `reactor.L0_DES` 3.072961 is neither PFD 202+205 (3.031) nor the live
  seed (3.079); it only anchors `L_fresh`, so it was left.
* **The PT-329201 design bleed is closed (As-Built *Phase 5j*), and what it leaves.** It was a
  period-2 oscillation: TT-328008 was built from the previous tick's m_775 and TIC-328008 sets m_775
  off it, a one-tick loop with gain ~2.7 that railed the master at 4 000 kg/h and drained 328D001 ->
  m_776 -> 323D001 -> m_308 -> PT-329201 (-0.26 bar in 3 300 s on HEAD). The reflux term now lags on
  328C002's liquid residence; the hold is 140.7015 bar a at 3 300 s. Left: (1) a +1.4 mbar residual
  over 3 000 s at dt 0.1, just outside `test_ccw_loss_chain`'s 1 mbar gate. (2) `dt_top_dynamic =
  10 + 12 . reflux/design` is itself a correlation (the 10 C floor and the linearity are unsourced).
  (3) TIC-328008's Kc 240 / Ti 110 were tuned "heavily over-damped in an isolated step" without that
  coupling; with the lag it closes near critical damping, so re-check it against the DCS before any
  retune.
* **`test_ccw_loss_chain` now runs end to end: 37 of 41 checks.** Three crash sites on the CCW-loss
  path were fixed (stripper-bottoms composition, the D-16 drum density below the triple point, the
  Raoult bubble point past water's critical pressure). Remaining GAPs: the +1.4 mbar hold above;
  "per-pass conversion falls" reads X_conv on the single tick the trip latches, which gave 57.1 %
  at N/C 86 (an earlier run latched 12 600 s later and read 0 %) -- the check samples an instant, not
  a trend; "feed cut arrests the excursion" (PT 154.7 -> 156.3 after the ESD); and "venting relieves
  the synthesis pressure" (141.7 -> 142.8 with HV-322604 at 100 %, whose seat caps at ~11.7 t/h
  against ~13 t/h retained).
* **A-5 leaves a real authority finding.** PV-329212 peaks at 99.7 % on a +1 °C TIC-324002 step
  (HEAD: 92 %). With a physical chest, 324E003's 90 % design stroke has almost no headroom. Check
  against the DCS before tuning around it. A dynamic chest inventory is blocked: the four exchanger
  datasheets are image-only scans with no legible shell volume.
* **Closed 2026-09-16 (details in the As-Built under *Phase 5b*).** A-6 (324F001 on its drawing's
  70.5 m3), A-7 (323F004 rides the 323E011 envelope -- there is no valve in that line), A-11 (323C003
  and 323F004 off pure-water T_sat onto `thermo_service`), A-17 (323F010's barometric leg on
  `M.g/A + P_vessel`). Ledger now 23 closed / 8 partial / 0 blocked / 2 reclassified / 40 open.
* **The vendor archive is the place to look when `References/` is silent.**
  `D:\Work\Helwan Fertilizers Company (HFC)\A - Plant Documentation\Licensor and Vendor
  Documentation\Soft copy`, indexed by `TOC_UD_AM_G00_AB_0022_000_01_HL.pdf` (1730 text pages; the
  specs and drawings themselves are scans -- render and read them). It answered 324F001's volume,
  which two passes had recorded as unobtainable. Use the `/soft-copy-search` skill's routing: TOC row
  -> Document ID -> file. `pypdf` and `pymupdf` are installed for this.
* **D-14 / D-15 CLOSED, and the assumption they left behind is closed too.** Capacitances are
  V_vap.drho_sat/dP on IF97, with V_vap read at each drum's PRINTED normal liquid level:
  C_MP 3.39, C_9 1.97, C_LP 45.92 kg/bar (were 25.0, 53.2, 25.0). The x30 `F_lump` is gone because
  the header pressures now step SEMI-IMPLICITLY, `P' = P + res.dt/(C + g.dt)` with g = -dres/dP from
  the same valve laws -- so the stability limit that motivated the lumping no longer exists at any
  dt. "Half full" turned out to be a DATUM for 329D005 and 329D009 (both GAs draw NLL on the shell
  axis) and WRONG for 322D001, which carries 1.05 m of water in a 5.3 m vertical shell.
* **`MSPAN_504` CLOSED the same pass.** The 322D001 level span was 1.600 m x 2.000 m at rho 917.0
  (3 687 kg); the as-built GA UD-AU-322-DZ-0009-006 gives ID 3.470 m, TWO drums on the one
  LIC-329504, LICA-329504 taps N8B/N8A 1.500 m apart, rho 919.36 -> 26 083 kg. Both taps are in the
  cylindrical shell, so no head correction. Not design-pinned: `_level_loop` is seeded for
  dm/dt = 0 at design whatever `m_span` is, so only the level timescale moved.
* **A-13 / B-9 / B-13 closed (As-Built *Phase 5g*); what they leave open.** (1) The condensers'
  cooling water is still the PFD-28 constant: `VacuumTrain324.cw_factors` exists and nothing sets it,
  and the CCW / CW system is not wired to the 324 exchangers, so the new cold-end physics only moves
  with load and shell pressure until it is. (2) NH3 and CO2 in the vents follow water's saturation
  line (the activity model stops at 80 C). (3) 324F003 at a 2 s harness tick still walks off (0.131 ->
  0.096 bar a over 900 s with PV-324203 at 60 %); at 0.25 s and 1 s it settles to 0.13144. The previous
  model RAILED to the 0.020 clamp there, and the production loop never exceeds STEP_CAP = 0.25 s.
  (4) PIC-324202 / PIC-324203 have Kc 2 %/bar, so a +0.01 bar SP step moves PT-324204 by ~0.1 mbar in
  1 200 s, on the old model and the new -- check against the DCS tuning before relying on them.
  (5) Closed in *Phase 5h*: the vapour rows are now published as mole %. (6) A-14 is still open: the train's
  stream masses are design numbers plus deltas, though the species now cascade.
* **D-11 closed (As-Built *Phase 5h*); what it leaves open.** Stream 702's inert content is still its
  PFD composition scaled with the PIC-323203 flow -- 323E011 / 323D011 do not carry a live N2/O2
  inventory -- and A-16 (323C005 bottoms linear in holdup) is untouched: 343 gravity-drains to the
  328V001 base, whose N1 overflow fixes the downstream head, and no source gives the elevation
  difference that would set the drain law.
* **A-14's offsets hide a real mass gap, not a relabelling.** The engine's own design vapour flows are
  705 = 14 094 kg/h (V1_DES + false air) against PFD 14 799, 709 = 2 759 against 3 342, 703 = 26 107
  against 26 840. The PFD's 317 -> 401 melt rows lose 655 kg/h of urea where entrainment into 705
  (121 kg/h) and biuret formation (172 kg/h) explain 293 -- the tabulated inconsistency G3 reconciled
  away. Letting "the design numbers emerge" means reopening G3.
* **D-16 closed (As-Built *Phase 5f*), and the design flows it anchors on do not match PFD-26.**
  `M_502_DES` is `M_STRIP_DES` = 76 670 kg/h against stream 904's 57 989; `M_504_DES` is
  `M_HPCC_DES` = 10 800 kg/h against stream 916's 19 500. The level valves are anchored on the
  module's flows, so they are self-consistent, but the steam network's liquid split is not the PFD's.
  Reconciling it moves the stripper-steam and HPCC-raising anchors, so it is its own piece of work.
* **Two things the 322D001 datasheet disagrees with and were NOT changed.** Its operating pressure
  is 4.400 bar a, while `steam_system.P_LP_BARA` is 5.01325 (4.0 barg, the header the mapping
  documents call the 4-bar header). And its "max. fill lev. in oper. cond." is blank on all three
  DDSs -- the NLL used now comes from the GAs, not the DDSs.
* **Thermo memo closed (As-Built *Phase 5d*); what it leaves open.** (1) `flash` corrects for the
  caller's FEED but not for the caller's temperature inside a 0.02 C bin, so K still steps ~0.12 %
  per bin edge -- the same size the old memo had, and invisible in every trace taken, but it is the
  next thing to linearise if a flash-driven loop ever chatters. (2) `_A328_Q_REACT_DES_KW`
  (main.py 1315) is still captured on the first tick the process runs, which on a cold boot is a
  PRE-pin tick, and it is not in the pin cache; it only reaches the published packet, so it is a
  cosmetic cold/warm asymmetry. (3) 323F004 drifts slowly over hours -- 106.00 at 1 200 s, 105.84 at
  9 600 s -- identically on the old and new memo, so that one is the plant model, not numerics.
  (4) `test_equation_audit_td014::test_the_column_and_pre_evaporator_hold_their_setpoints` asserts
  323F010 within 1 mK of 99 C at exactly 7 200 s, and 323F010 is still ringing there: TIC-323012
  is in a lightly damped +/-10 mK, ~450 s swing (p-p 30 mK over 3 000-6 000 s at the 1 s harness
  tick, +/-5 mK by 7 900 s). The test reads its PHASE -- 1.01 mK on this commit (fail), 0.10 mK
  once D-12 lands (pass). It is not the memo: a 10x finer temperature quantum gives the same 30.5
  vs 31.0 mK. The loop's damping is the open item, not this test.
* **D-12 closed (As-Built *Phase 5e*); what it leaves open.** (1) Superseded -- A-13 / B-9 / B-13 are
  closed (*Phase 5g*), and the condenser node DID have a caller (`core/vacuum.py`); only
  `main.vacuum_train_324` was uncalled. (2) The stream
  790 carryover is a fixed 0.611 % of the overhead; its latent heat is still charged on the whole
  overhead (46 kW of 7 253). (3) 323F010's seed still gains 4.85 kg/h of biuret against 4.97 kg/h
  of water -- PFD rounding on a 101 t/h feed, left as it is.
* **`test_lv324501_routing.py` is 4 failed / 6 passed on BOTH trees** -- the handoff's recorded "3"
  was stale, not a regression from this work.
* **Regression, measured against HEAD in a side worktree.**
  `test_equation_audit_323_324.py`: HEAD 3 failed, this tree 2 failed
  (`test_design_fixed_point_holds` now passes). `test_equation_audit_td014.py`: 3 failed / 8 passed
  on BOTH trees, same names, so the recorded 4/7 was stale. Its PIC-329202 walk grows −0.035 → −0.185 %,
  but that is the ×5.87 slave Kc: in chest pressure both are ≈0.0017 bar. The harness also runs at
  DT = 1.0 s, above STEP_CAP. `test_transient_coldstart.py`: 3 failed / 2 passed on both trees. With
  A-3 removed, τ moves 504.7 → 2 318 s (band 2 884–4 055). P_f is ~30 barg on both, so the loop never
  pressurises from cold, and that predates this work. Unchanged green: hydraulics 56, c003 coupling
  20, startup 5, reactor 14, kinetics 10, stripper 4, foptd 3, trend 9, totalizer 5.
* **Python on this machine** now lives at `%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe`
  (PyManager, 3.14.7) with the requirements and pytest installed. Bare `python` on PATH may still
  resolve to the Store stub.

## 1. Documentation reconciliation — `project.md` §5.1 — partially closed

**Closed for 323C003 / 323F004 / 323F010.** `backend/thermo_service.py` (Phase 1) now wires
`vle_nh3co2h2o`, `props_nh3co2h2o` (SRK), `thermo_extended_uniquac` and `gap_g6_h0_enthalpy` into a
single `flash / flash_ph / bubble_p / bubble_t / dew_t` service, and those three stages take their
vapour composition from a Rachford-Rice gamma-phi solve instead of the frozen `sol_vapour_y` alpha
vector. Live confirmation is published per tick as `SOL.vle_domain`.

**328C002 / 328C003 / 328C004 closed (As-Built *Phase 5k*).** Their volatilities move on
`thermo_service.k_ratio` (live liquor, T and P derivative), inside the Kremser form for the two
desorbers. The Perry's van't Hoff bracket had no pressure term and the wrong sign along the columns'
saturation line. **Still anchored:** 328D003, 328D001 and 322C001 run at 40-61 C, below the grid's
80 C bottom node, which stays a deliberate bound (`vle_nh3co2h2o._in_box`). The 328 temperature is
clamped to 80.05-209.95 C for the ratio, so a column crossing an edge goes flat instead of snapping
back onto its design volatility.

## 1a. G-VLE-2 — no volatile split on a urea melt (324E001 / 324E003)

`thermo_service.flash` refuses `DOMAIN_NEUTRAL_UREA`. The neutral H2O/urea binary carries no NH3 or
CO2 at all, and the electrolyte path is outside its dilute limit there: the loading basis is mol per
kg of **water**, so 0.04 wt% NH3 in a 1.39 wt% water melt reads as 1.69 mol/kg and the flash returns
an NH3 vapour mole fraction of 0.24 for a melt whose vapour is essentially pure steam. `bubble_p` /
`bubble_t` remain valid and are good there (+2.2 % at 324E003, against +65.7 % for the electrolyte
model). 324E001/E003 therefore keep their anchored vapour vector.

**To close:** a urea-melt NH3/CO2 solubility source (Henry constants on a urea-melt basis, not an
aqueous one). This is new source material, not new wiring.

## 1b. G-VLE-3 — CLOSED (Phase 5)

Three of the four nominated 322 sites are wired to the rigorous boundary: the reactor
disengagement, the stripper split and the scrubber vent. **322E002 is deliberately NOT**, and that
is the single most important thing to carry forward. Full derivation in the As-Built under
*Phase 5*. What is worth carrying forward is only what is still OPEN or still surprising:

* **DO NOT re-wire `_hpcc_flash_split` to `k_ratio` without reading § *Why 322E002 keeps its
  calibration* first.** It was wired, it passed every static check including a 103/103 bit-identical
  boot pin, and it broke the synthesis loop's ability to recover from a disturbance —
  `test_3_scrubber_heat`'s CCW-restore leg went from `+0.200 → +0.100 bar` (decaying) to
  `+0.400 → +1.200` (still climbing). The rigorous form is an order of magnitude *gentler* than the
  Clausius-Clapeyron law it replaced (total-vapour span 0.062 vs 0.683 over the scenario), so this
  is not a stiffness problem and damping it will not help. The failure is that
  `HPCC_FLASH_DH` is common-mode — the same enthalpy for NH3 and CO2, so it moves how much vapour
  leaves and not what leaves — while the rigorous ratio is differential: at 175.7 °C it raises NH3
  to 1.154 and halves CO2 to 0.483. That re-orders the carbamate recycle's N/C, which moves reactor
  conversion, which moves loop pressure. The loop has a restoring force against an inventory shift
  and **none against a composition shift**. Re-opening this needs a parameter set refitted for the
  loop, not a code change.

* **The design seed is NOT an acceptance criterion for HP-loop split work.** Every form involved,
  old and new, is exactly 1.0 at design by construction, so the boot pin stayed 103/103
  bit-identical in the configuration that broke the plant. It is necessary and nearly
  uninformative. Judge these changes on a transient — `test_3_scrubber_heat` is the cheapest one
  that discriminates (~10 min from a cold pin).

* **The 322E003 vent total now follows its inerts (As-Built *Phase 5i*), not a renormalised pin.**
  The positive feedback that forced composition-only (higher P -> lower K -> less vented -> more
  retained -> higher P, -24.2 kg/h per bar on the old NH3-rich vent) was re-measured on the
  saturated-inert law: -0.072 % of vent per bar, -1.1 kg/h per bar, against HV-322604's choked
  +12.1 kg/h per bar. If the vent ever becomes condensable-rich again (a CCW failure does it), the
  K-ratio share grows with it.
* **The stripper lost ~8.6× of its pressure damping** (−0.081 %/bar on the design NH3 split against
  `eta_P`'s −0.694 %/bar). The new number is right for an *equilibrium* split fraction — at φ = 0.85
  saturation compresses the response, and the old law applied the full −0.69 % onto φ regardless,
  which is how N2 reached 1.148 before the clamp. But 322E001 is a rate-limited falling-film
  contactor, so the truth is likely between the two. It passes today; if loop damping ever looks
  thin in a training scenario, this is the first place to look.

* **The parameter set is EXTRAPOLATED in the loop and that has not changed.** The re-index fixed the
  coordinate and the seeded solver fixed the reach; neither touches the fit, which is a
  dilute-aqueous CO2-capture regression below ~150 °C being evaluated at *x*_H2O = 0.047 and 183 °C.
  The number to remember: **the model puts 322R001's overflow bubble pressure at 40.4 bar a at
  183 °C against a loop that runs at 144.2 — a factor of 3.6 low.** Nothing in the engine uses an
  absolute HP-loop VLE number; every 322 split runs on `thermo_service.k_ratio`, which is exactly
  1.0 at its own reference by identical-argument arithmetic. **If anyone ever wires an absolute
  number out of this table in the 322 loop, that is a regression, not an improvement.**

* **No Poynting correction.** At 144 bar the partial-molar-volume term is worth roughly +15 % on an
  NH3 or CO2 partial pressure. This repository holds no sourced infinite-dilution partial molar
  volumes, so it is not computed; it is nearly constant across the loop's band and is absorbed by
  the ratio form. If a source ever appears, this is the first thing to add.

* **Inert Henry constants are for WATER as the solvent**, applied to a solvent that in the synthesis
  loop is mostly ammonia and carbamate. IAPWS G7-04 is genuine standard-state data and it
  cross-validates against this repo's own independent Rumpf & Maurer CO2 fit to 5.0 % at 183 °C, but
  the solvent substitution is a stated approximation with no datum behind it.

* **`REACT_THETA_OG` still keeps the four inerts structurally at theta = 1.** That is correct as
  written — `REACT_OVERFLOW_DES` has them at exactly 0, so they are non-distributing by
  construction, not by exception — but it means the reactor dissolves no nitrogen at all. Real
  synthesis melts do dissolve a little. Closing it needs an inert solubility datum in molten
  carbamate, which is the same missing source as the bullet above.

* **The stripper's ratio carries PRESSURE ONLY.** Its reference temperature is its live temperature,
  so the T terms cancel identically. This is deliberate: the stripper is a steam-driven contactor
  whose bottoms temperature is an OUTPUT of the duty chain, already carried by `eta_T_steam`, and
  putting the live temperature into the ratio as well would double-count the same steam heat. If
  anyone later wants a thermal term there, `eta_T_steam` has to come out at the same time.

**Two things measured in this phase that are worth not re-deriving:**

* **The speciation solver's ceiling was an INITIAL GUESS, not a domain limit.** From its dilute
  ansatz `props_nh3co2h2o.speciate` returns a residual of 9.9 at N = 50 mol/kg water and 200, 2 000
  and 20 000 iterations all return the identical non-solution. Seeded from a converged neighbour the
  same solver reaches N = 869 / C = 195 in five Newton steps at 8.5e-14. Every future "the model
  cannot reach there" claim about this module should be tested against a seeded call first.

* **Do NOT drive an anchored K-ratio from a CORRELATED input.** The 322E003 vent split was wired to
  TT-322011 first, on the reasoning that a live temperature is better than a design constant. It is
  not, when the "temperature" is `114 + 120*(AT-322701 - N/C_des) + 20*theta_dev` -- a correlation
  whose 120 C per N/C unit is a fitted gain. A rigorous derivative applied to a fitted gain AMPLIFIES
  the gain: it drove the 322C001 design liquor's stationarity residual from 8.1e-9 to 3.7e-4 (45
  000x) and reversed the sign of the vent NH3 slip against off-gas throughput. The vent now rides
  PT-329201 alone, which is a real measurement. **The same trap exists anywhere else in this engine
  where a "TT" is actually a correlation** -- check before feeding one into a thermodynamic ratio.

* **Do NOT memoise `k_ratio` on the quantised grid `flash` and `bubble_t` use.** It was written,
  measured (9.6 us warm against 176 us cold, a 6.7 % tick saving) and removed. A ratio is not a
  flash: every call has a reference that must return exactly 1.0, and the engine spends thousands of
  consecutive ticks NEAR that reference -- the whole boot settle does -- so on the 100 ppm
  composition quantum a settle tick keyed identically to the design state and answered for it. It
  moved the pinned 322E003 vent vector by 1.1e-4 kmol/h, and ONLY when the boot-pin cache missed:
  exact on a warm tree, broken on a cold one. If it ever needs to be fast, the fix is an
  EXACT-argument key, not a finer quantum -- a finer quantum shrinks the window without closing it.

* **The boot penalty is NEGATIVE.** The grid is 52 % larger (800 -> 1215 nodes) and builds 6.9 s
  FASTER (26.7 s -> 19.8 s), because continuation seeding replaces the cold ansatz at every node:
  16.3 ms/node against 33.4. The old docstring claimed "~5 s" for a build that took 26.7.

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

## 1e. Phase 2 — hydraulic network, CLOSED

`backend/hydraulics.py` carries the IEC 60534 / ISA-75.01 laws and the vapour-space pressure
derivative. **A-6, D-1, D-2, D-8 and D-19/D-20/D-21 are closed.** Design seed bit-exact on every
anchor after the change (xi_urea 1302.270000000, xi_biu 2.414000000, T_ovf 183.000017, all nine
vessel pressures, p_syn 140.699999913). Full write-up in the As-Built under *Phase 2 remainder*.

**328D001 IS NOW CLOSED** (Phase 4b) and the closure went the opposite way to the deferral: the
vessel could always be sized, and what could not be trusted was the design HOLDUP. Full argument in
the As-Built under *Phase 4b*; the short version is that `R328_D001_M_FULL` was 19.09 m3 at the
stream density, i.e. the datasheet narrative's disputed "19 cubic meters" carried straight into the
inventory, and a holdup 243 % of its own shell is what put V_v on its 2 % floor and made the
coefficient look like 355x. Off the shell instead, the drum holds 2.19 m3 in a 4.34 m3 vessel, V_v
is an ordinary 2.150 m3 and the coefficient is 15x. **That is the second time a design holdup has
failed to fit its own vessel** (322C001 was out by 69 % the other way) — the standing advice to
check any `_M_TAU_S`-style holdup against the shell before using it as an A-6 basis has now paid
twice.

**The three 328 bottoms valves CLOSED (As-Built *Phase 5l*).** None is a flashing service: each sits
after a cooler or on a pump discharge, so its inlet is subcooled and the IEC liquid choke with the
liquor's own Pv at the inlet temperature is the right law. LV-328504 (749 at 148 C) flashes in its
vena contracta and is choked at design. LV-328503 (746 at 190 C, Pv 14.97 bar a) chokes when
the hydrolyser falls below ~15.4 bar a. LV-328505 keeps pv = 0: the model's p1 omits the 328P007
head. **LV-322501 (report D-20) is the one genuine two-phase letdown left.** It lets 322E001 bottoms
down 140.7 -> 4 bar straight off the sump.

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

### Regression status

SUPERSEDED by the Phase 4b table in section 1g, which re-ran every one of these files against a HEAD
side worktree on the corrected harness step. Two entries there differ from what this section used to
record, and both are the harness rather than the physics: `test_hydraulics.py` is 56 passed (was 38,
then 47+1 once the 328D001 deferral pin went stale), and `test_c003_pressure_coupling.py` is
20 passed on BOTH trees at 0.25 s where it read 1 failed / 19 passed at the old step.

### test_ccw_loss_chain.py was ALREADY failing at dae861d, every gate -- measured, not assumed

Phase 1b's seven "new terms inert at design" gaps fail **identically** on `dae861d` and on this
branch (cool_frac 0.9958 / 0.9951, uncond 0.07 / 0.08 t/h, retained vapour 4.5 / 5.2 kg, swell
0.1 / 0.1 %), and Phase 2 crashes identically on both. One line moves in the right direction: over
the 6000 s Phase 1b hold, LT-329501 drifts 50.000 -> **49.400** on `dae861d` and holds **50.000**
flat on this branch, which is the restored D-19 head term.


Its first gate is `abs(pt_prod - 140.7) < 1e-3` after 3000 s at the production tick. Running the
identical hold on **dae861d in a side worktree** and on this branch:

| t (s) | dae861d | with Phase 2 | delta | scrub sump, base -> new |
|---|---|---|---|---|
| 500 | 140.705274 | 140.705202 | -7.2e-5 | 49.9990 -> 49.9996 |
| 1000 | 140.707908 | 140.707843 | -6.5e-5 | 49.9976 -> 49.9993 |
| 1500 | 140.710084 | 140.709985 | -9.9e-5 | 49.9956 -> 49.9990 |
| 2000 | 140.712724 | 140.712596 | -1.3e-4 | 49.9929 -> 49.9987 |
| 2500 | 140.715573 | 140.715442 | -1.3e-4 | 49.9897 -> 49.9984 |
| 3000 | **140.718363** | **140.718261** | -1.0e-4 | 49.9858 -> **49.9981** |

The +0.018 bar that fails the gate is **inherited from Phase 3**, and this branch is fractionally
LOWER at every sample. The origin is the A-8 thermal-loop closure whose settled drift section 1f
already records as open: before A-8 the reactor temperature was imposed and the loop drift could not
reach it. The handoff's older quote of "140.70024 after 3000 s" predates Phase 3.

Worth noticing in the same table: the **322E003 sump holds NLL seven times tighter** on this branch
(0.002 points off at 3000 s against 0.014). That is the D-19 head term making it a genuine
attractor instead of an integrator, and it is a design-hold IMPROVEMENT, not a cost.

### An engine-killing crash on the transport path -- PRE-EXISTING, and now fixed

`_w_norm` divided by the sum of a packet's mass fractions with no guard, and
`consequence.ZERO_PACKET` carries an EMPTY component vector -- so the moment a transported line
delivered an empty packet while its departure carried mass (the line dry for longer than its dead
time, then flow resuming), the tick died with `ZeroDivisionError`. All five transport sites had it.

**Attributed, not assumed: `dae861d` crashes identically** -- same file, same line
(`w_314_in = _w_norm(_pkt_arr_314.mass_fraction)`), same Phase 2, same `H.run(300)`. It is
reachable from any upset that takes a transported line to exactly zero flow, and a total 322E003 CCW
loss does it at the 323C003 bottom drain. Nothing in Phase 2 caused it or made it reachable.

Fixed at the source: `_w_norm` takes an optional `fallback` used only when the total is
non-positive, and each of the five sites passes its own departure composition. Nothing physical is
papered over -- when no mass arrives, the receiving stage's inflow term is zero, so the vector it
multiplies is arbitrary and the departure composition is the honest placeholder. Every OTHER caller
passes a PFD row, where a zero total IS a data error and still raises.

This is the fourth of the same family the CCW chain has surfaced; section 9 lists three more that a
previous pass fixed. **The chain is worth running after any change to the 323/324 train** -- it is
the only test that drives the flowsheet hard enough to reach these.

### ...and behind it, a FIFTH: 324E001's temperature diverged on the post-trip plant -- FIXED

With the transport crash fixed the chain got past Phase 2 for the first time. Phase 2 itself now
runs to completion and passes **12 of its 13 checks**:

```
  LT-329501 TRUE min (%)          50.000 ->      34.600     -30.8%  [DOWN]
  AT-322701 reactor N/C            3.002 ->      99.990   (analyzer span)
  X_conv per-pass (%)             54.634 ->      23.456     -57.1%  [DOWN]
  trip 22.2 latched at           3600 s   (setpoint 155.0 bar a)
  [GAP ] CCW loss collapses cool_frac to 0  --> cool_frac=0.0033
  [PASS] x12 -- condensate returns to off-gas, HV-322604 seat-limited, overflow T at the ceiling,
         retained vapour integrates PT up, LT-329501 spikes and hunts on the froth, true sump drains
         underneath the indication, N/C off anchor, conversion falls, PT reaches high-high,
         SV-32201 does not lift, trip cuts CO2 and stops both HP-NH3 pumps
```

The single GAP is an exact-zero assertion (`cool_min == 0.0`) against a measured 0.0033 -- a
tolerance question, not a physics one.

Then `test_ccw_loss_chain.py:192`, the **post-trip** continuation (`H.run(600)`, "1200 s with the
feed cut"), dies:

```
  File "main.py", line 8418, in step_sim
    cp_feed2   = urea_soln_cp(w1_live, s.r324_e001_T)     # LIVE Stage-1 melt cp
  File "main.py", line 820, in cp_water_kjkgk
    + 0.000008708461 * T_C * T_C + 0.00000001809921 * T_C ** 3)
OverflowError: (34, 'Result too large')
```

**Attribution: pre-existing.** Nothing in the Phase 2 remainder touches `urea_soln_cp` or the 324
temperature integrator; it was simply unreachable while the transport crash stopped the chain one
phase earlier.

### ...and the fifth is FIXED: the melt-temperature step is now semi-implicit

Root-caused rather than clamped, and the first diagnosis written here was WRONG in a way that would
have misdirected the sweep below, so it is corrected in place. Both 324 stages advanced their melt
temperature with `T' = T + pwr*dt / max(M*cp, 1e-6)`. **The `1e-6` is not the defect.**
`s.r324_f001_M` is written back as `max(..., 1.0)`, so M >= 1 kg and that floor is unreachable dead
code -- and the same is true at every one of the thirteen sites, because every one of these vessels
is mass-floored at 1.0 kg.

The defect is explicit Euler itself. The T-dependent terms give a time constant `tau = M.cp/k_cap`
with `k_cap = m_feed/3600*cp_f + UA`, and k_cap is a property of the FLOWS, not of the inventory --
so as the separator draws down, tau collapses while the driver does not. The step amplifies once
`dt/tau > 2`, i.e. below `M_crit = k_cap*dt / (2*cp_hold)`:

| stage   | m_feed (kg/h) | k_cap (kW/K) | M_des (kg) | M_crit @ dt=0.1 s | M_crit @ dt=2 s |
|---------|---------------|--------------|------------|-------------------|-----------------|
| 324F001 | 92 748.9      | 856.47       | 3933.8     | 19.5 kg (0.50 %)  | 389.9 kg (9.91 %) |
| 324F003 | 78 675.8      | 116.25       | 3796.9     | 2.7 kg (0.07 %)   | 54.8 kg (1.44 %)  |

The last column is the finding. On the 2 s HARNESS tick 324F001 is unstable at one tenth of design
inventory -- a deep level excursion, not an empty vessel. Per-step amplification is 6.8x at 100 kg
of holdup and 779x at the 1 kg floor; on the production tick it is 38x at the floor. A CCW trip took
324F001 through that threshold, T then alternated sign about T_inf and DOUBLED every tick until
`cp_water_kjkgk` evaluated T^3 above 5.6e102 and the tick died. An `OverflowError` inside a
heat-capacity correlation looks like a property-range problem and is not one -- clamping the
correlation would have hidden a diverging state behind a plausible number, which is worse than the
crash.

The stiff terms are the ones that depend on the temperature being solved for, so they are now
treated implicitly:

    (M.cp/dt)(T' - T) = pwr(T) - k_cap.(T' - T)   ->   T' = T + pwr.dt / (M.cp + k_cap.dt)
    k_cap = m_feed/3600 * cp_feed  +  UA  (the latter only while Q > 0)

Unconditionally stable (the amplification factor is `M.cp/(M.cp + k_cap.dt)`, always in (0,1] for
ANY dt and ANY M, so M_crit ceases to exist); correct in the limit that used to break it (as M -> 0
the step becomes the algebraic `T' = T + pwr/k_cap`, a vessel with no thermal inertia whose outlet
follows its inlet); and **bit-exact at the design seed**, because `pwr` is identically 0 there so
`T' = T + 0` whatever the denominator is. That last point is why the INCREMENT form is used rather
than the algebraically equivalent `(M.cp.T/dt + k_cap.T_f + Q)/(M.cp/dt + k_cap)` -- the latter is
right in exact arithmetic but leans on a cancellation floating point does not deliver, and the boot
pin asserts the design point to the last bit. Full derivation in the As-Built under
*Melt-Temperature Integration in Unit 324*.

### The same construct sat at ELEVEN more integrators -- SWEPT, ten changed and one deliberately not

`grep -n "dt / max(.*cp.*1e-6" backend/main.py` finds thirteen. Ten of the remaining eleven now
carry the same semi-implicit denominator: **323F004, 323F010, 323D002, 323C005, 328D003 (both
compartments), 328C003, 328D001, 322C001, 323E003 and 323E011**. `k_cap` is that vessel's own inlet
heat-capacity rate, plus a UA only where the duty actually resists a change in the temperature being
solved for -- 323E003's `UA*(Te003 - T_tw)` and 323E011's `UA*(Te011 - 35)` do and are included;
328D001's `Q_e004` does NOT (it is stroke-driven off TV-328002 with no Td001 in it) and is excluded.
Per-site table in the As-Built.

**323C003 is deliberately left explicit**, and that exception is the clean statement of what the
defect was. It is the one vessel whose balance is written in RELAXATION form, `q_relax =
M*cp*(T_bub - T)/tau_res`, so the resisting heat-capacity rate is `M*cp/tau_res` -- it carries M
itself, `dt/tau` reduces to the constant `dt/tau_res` (0.1 s against 300 s), and there is no M_crit
at all. The instability was never about small numbers or a division guard; it was about WHERE the
heat-capacity rate lives. When it belongs to the flows it outlives the inventory and explicit Euler
divides a surviving driver by a vanishing capacity. 323F004 sits on the boundary and proves the
rule: it carries both a relaxation term and a real letdown sensible load, and only the second goes
into k_cap.

**Verified.** All 20 pinned boot constants byte-identical to HEAD (`.boot_pin_cache.json` compared
entry by entry). The design seed is bit-identical at t = 0 across all 29 probed states, every anchor
on its exact PFD value (322C001 3.900000000, 328C003 16.800000000, 324F001 0.330000000, 324F003
0.131000000, 323F010 0.460000000, 323D002 99.000000000, TT-322014 183.000000000). After 200
production ticks the untouched nodes are still bit-identical and the ten touched ones differ by at
most 1.5e-6 C and 3e-8 bar -- last-digit motion on states that already carry a small non-zero pwr at
the settled attractor.

### The CCW chain now clears Phases 3 and 4 -- FIRST EXECUTION EVER

With the transport crash and the stiffness crash both cleared, `test_ccw_loss_chain.py` ran end to
end for the first time: **28 of 36 physical expectations met.** Phases 3 and 4 had never been
reached before, so their result is new information rather than a regression, and **all 14 of their
checks PASS**: opening HV-322604 dumps the loop into 322C001 (vent 5.9 -> 37.1 t/h), 322C001 is
flagged overloaded at 31.1 bar a, SV-32253 lifts at its 31.01 bar a set, atmospheric NH3 slip goes
1557 -> 34 857 kg/h, PT-329201 relieves 141.3 -> 139.0; trip 22.2 latches at 155.0, cuts CO2, stops
both HP-NH3 pumps, holds inside its hysteresis band and clears on operator reset; SV-32201 lifts at
168.91 bar a passing 99.0 t/h with 27 081.9 kg/h of ammonia and flags the toxic release.

The 8 remaining gaps are all in Phase 1 (7) plus one in Phase 2, and all are the same class: the new
terms are not exactly inert at the design seed. `cool_frac = 0.9951` rather than 1, 0.08 t/h of
uncondensed off-gas, 5.2 kg of retained loop vapour, 0.1 % of swell, and an indication reading
50.0 % against a true 49.9 %. Phase 2's single gap is the mirror image -- `cool_frac = 0.0033` at
total CCW loss against an exact-zero assertion. The file's closing assert also still fails on
`PT-329201 = 140.71826` against a 1e-3 tolerance on 140.700; that +0.018 bar over 3000 s is the
inherited A-8 design-hold drift (baseline at dae861d reads 140.718363, this branch 140.718261, i.e.
this branch is marginally TIGHTER), not anything introduced here.

**Long-run regression, as measured (not estimated).** All four of the multi-thousand-tick files
were run: **`test_equation_audit_td014.py` 4 failed / 7 passed** (its recorded baseline, unchanged);
**`test_transient_coldstart.py` 3 failed / 2 passed** (measured at 7a6b605; the recorded baseline was 5 failed, so two assertions now pass — not attributed, 83f48c9 landed in the same window); **`test_ccw_loss_chain.py`
28/36 with the closing design-hold assert failing on the inherited +0.018 bar** (see above -- the
run before the two crash fixes could not get past Phase 2 at all); and
`test_scenario_consequences.py` at its **scenario_coverage 6** baseline. Compare against those
numbers next session rather than re-deriving them.

Timing caveat, because it shapes what is worth attempting in one session: the machine this ran on
has 4 logical cores and was 70-85 % consumed by unrelated desktop applications throughout, which
took the engine from its normal ~126 ticks/s to roughly a tenth of that. `test_transient_coldstart.py`
alone is 32 000 ticks by construction (T_END 16 000 s at DT 0.5) and took 6 min; the desorption file
took 9 min 44 s. Budget accordingly.

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

## 1g. Phase 4a — CCW seed cleanup, API 520 relief, 320K002 map

### Part A — CLOSED: 7 of the 8 CCW design-seed gaps

At t = 0 all eight terms were already exactly zero. What the chain was recording was a drifting seed
feeding terms that were correctly anchored. Two causes:

* **`rho_cond` divided by `nu = PT-329201/PT_des`** -- the WRONG SIGN for a condenser (more pressure
  means a higher condensing temperature and MORE driving force) and a double count of the throughput
  demand `s` already carries. It closed a positive-feedback loop on the settled-attractor drift.
  Replaced with the live condensing temperature through Clausius-Clapeyron on the carbamate exotherm
  already in the model (`scrub_cond_t_c`, 0.0754 K/bar at the anchor, bit-exact at P_des). The
  capacity is also gated on `ccw_pump_frac` rather than the FIC's 25 s-lagged transmitter reading,
  so a total CCW loss gives `cool_frac` exactly 0 on the first tick instead of 0.0033.
* **`REACT_M_LIQ_DES` and the bulk-melt block were solved against a SUPERSEDED node profile.**
  `REACT_NODE_SS_DES` is assigned three times (import seed, A-8 fixed point, cache restore) and the
  derived anchors were computed once against the first. `State()` seeded the holdup off one design
  point and the node temperatures off another -- 0.9 C apart -- so the first tick STEPPED the reactor
  level -0.156 % of span. Since Phase 3 the reactor runs on residence time, so that went into
  `X_conv` and then into `delta_X = max(1 - X/X_ref, 0)`, which is one-sided and therefore ratchets.
  `_rederive_react_bulk_anchors()` re-solves the block on both pin paths.

**Chain: 28/36 -> 35/36** (39/41 with the new PSV checks). The one gap left is the 3000 s design
hold, improved 3.4x: PT-329201 140.71826 -> **140.70544** against a 1e-3 tolerance. Still open.
[Phase 4b re-measured this on the corrected 0.25 s harness step, where HEAD itself reads 140.5408
and this branch 140.4768 — the chain scores **36/41 on both**, with the same five gaps. The four
gaps besides the design hold are the Phase 1b "new terms inert at design" set, and all three of
their numbers are about 10x closer to zero than the values section 1e quotes: cool_frac 0.9995
against 0.9951, uncondensed 0.008 t/h against 0.08, retained vapour 0.5 kg against 5.2.]

Design seed verified bit-identical to HEAD across all 29 probed states after every step of this
work. The boot pin DID move on the settled live references (EJ_MOTIVE_DES_LIVE -0.12 %, REACT_X_DES
-0.024 %, HPCC_UA +0.016 %) -- correct, since the reconciliation moved the settled fixed point;
`test_hydraulics.py::test_the_ejector_suction_follows_the_gravity_head_again` was riding on
EJ_MOTIVE_DES_LIVE happening to equal the nameplate and now calls with the live value.

### Part B, D-9 — CLOSED: SV-32201 on API 520 Part I

`hydraulics.psv_api520_choked_kgh` / `psv_area_from_rated_m2` / `psv_choked_ratio`. Orifice
back-solved from the documented 200 t/h rating through the same equation, so Kd/Kb/Kc/k/Z cancel:
**2.558 in^2**, 90 % of API letter "L". Pop at set, 7 % blowdown reseat (API 527), full choked flow
whenever open. Capacity vs the linear ramp it replaces: **0 -> 181.8 t/h at the set pressure**,
97.2 -> **190.7 t/h** at the 168.84 bar a the chain reaches (x1.96), identical at rated accumulation
by construction. Chain Phase 4 relief 99.0 -> 190.8 t/h, NH3 to atmosphere 27 082 -> 52 174 kg/h.

### Part B, D-5 and D-6 — CLOSED in Phase 4b

Both are wired, both are bit-exact at the design seed, and the write-ups are in the As-Built under
*Phase 4b*. What is worth carrying forward is only what is still OPEN, and that is one thing:

* **322F001 runs at 84 % of its own shutoff head, so it stalls below ~92 % motive flow.** This is a
  property of the licensor's design duty and not of any assumption in the model: N = 0.202 with
  M_vol = 0.666 puts the machine low on its own flow curve and therefore high on its head curve, and
  the ratio lift/C0 comes out between 0.78 and 0.95 for EVERY plausible motive pressure and suction
  head that was tried. It is nonetheless a far more brittle machine than the retired `f_stall` knee
  at phi_m 0.35 implied. HV-322602 has the authority to hold it alive — the DDS free-area band
  (40-100 %, a = 40 + 0.6.theta) keeps it running to about 80 % motive at a 41 % opening — but
  **any scenario that reduces NH3 rate without closing the spindle will now stall the ejector**, and
  none of them close it. `EJ_STALL_PHI_M` (0.918) is published so a scenario can read it instead of
  discovering it. Two things could move it if a source ever turns up: the 322E003 seal-leg height
  (which would raise the suction pressure and shorten the lift) and a static/friction split of the
  4.2 bar design lift (friction falls with mdot^2 on turndown, so the margin above is pessimistic if
  the lift is mostly friction).

* The same operating point makes entrainment about **ten times** as sensitive to motive flow as the
  retired linear `phi_m` was. The engine's seeded pump flow and its settled pump flow differ by
  ~0.1 %, which used to be invisible; it now shows as a ~0.7 % steady offset on the 322E003 sump
  level. The anchor is deliberately on the licensor's design PAIR rather than on the boot-pinned
  settled motive, so that offset lands on the settled sump rather than on the first tick from a
  fresh `State()` — which is where the boot pin and every unit test measure the design point.

* `p_crack` on the CO2 tie-in (2 % of the design differential) and the four jet-pump loss
  coefficients are stated representative values in the class of `FL_GLOBE` / `XT_GLOBE`, not vendor
  data. The geometry is back-solved THROUGH them, so a different set moves the back-solved areas and
  leaves the design point exactly where it is. The geometry the back-solve predicts — a 16.73 mm
  nozzle in a 50.81 mm throat, b = 0.1085, 89.3 m/s and 15.0 m/s — is the model's falsifiable claim
  about what is inside `References/Datasheets/322F001 Design Calculations.pdf`, which is a 12-page
  scan with no text layer. If that scan is ever OCR'd, check those four numbers first.

* 328D001's heads are excluded from V_v because their type is stated nowhere, so V_v is a LOWER
  bound and the modelled pressure response is if anything slightly stiffer than the drum's.

### The harness step was wrong, and it had to be fixed before any of this could be graded

`main.STEP_CAP` is 0.25 s and `sim_task` bounds every physical sub-step by it; the constant's own
comment records that 0.5 s "is UNSTABLE". Three test harnesses were integrating ABOVE it —
`_systest.run` at 2.0 s, `test_ejector_spindle._settle` at 1.0 s, and
`test_equation_audit_c10_live_cp`'s seed hold at 1.0 s — i.e. four and eight times a step the engine
declares unstable at two. All three now advance the same plant time in STEP_CAP-bounded sub-steps.
**No tolerance was relaxed anywhere.**

The mechanism is PRE-EXISTING and is in none of the code Phase 4b touched: SIC-321951's actuator lag
is `alpha = min(1, dt/2)`, so at dt >= 2 s the lag COLLAPSES, the pump-speed loop becomes a pure
algebraic feedback whose characteristic roots are {1, -2}, and the NH3 motive flow rings at +/-20 %
of stroke. It was invisible while the CO2 feed and the ejector capacity were pinned constants that
could not propagate it. Measured on `test_3_scrubber_heat`'s own CCW cut:

| step | 322E003 sump | PT-329201 after relax |
|---|---|---|
| 0.25 s (the engine's own) | 50.0 -> 45.8 -> **49.8 %**, troughs and recovers as report D-19 says | 140.75 |
| 2.0 s (the old harness) | 50.0 -> **100.0 -> 100.0 %**, saturated | 145.53 |

**If a test ever shows a new instability, check its integration step before checking the physics.**
Three of the four regressions this pass produced were this and nothing else.

### Phase 4b regression status — every file at or better than HEAD, measured on the same harness

HEAD was re-run in a side worktree with the corrected `_systest` so the comparison is like for like.

| file | HEAD | Phase 4b |
|---|---|---|
| `test_hydraulics.py` | 47 passed, 1 failed | **56 passed** |
| `test_jet_pump.py` | — | **19 passed** (new) |
| `test_ejector_spindle.py` | 11 passed | 11 passed |
| `test_3_scrubber_heat.py` | 8/8 | 8/8 |
| `test_reactor.py` | 14 passed | 14 passed |
| `test_reactor_kinetics_phase3.py` | 10 passed | 10 passed |
| `test_stripper_reaction_inventory.py` | 4 passed | 4 passed |
| `test_thermo_service.py` | 27 passed | 27 passed |
| `test_equation_audit_c10_live_cp.py` | 7 passed | 7 passed |
| `test_startup_stability.py` | 5 passed | 5 passed |
| `test_process_transport.py` | 7 passed | 7 passed |
| `test_consequence_propagation.py` | 8 passed, 2 xfailed | 8 passed, 2 xfailed |
| `test_foptd_fingerprint.py` | 3 passed | 3 passed |
| `test_equation_audit_322e001_enthalpy.py` | 13 passed | 13 passed |
| `test_equation_audit_322e001_flood.py` | 11 passed | 11 passed |
| `test_c003_pressure_coupling.py` | 20 passed | 20 passed |
| `test_equation_audit_desorption.py` | 2 failed, 8 passed | identical, same two names |
| `test_equation_audit_322e002.py` | 1 failed, 7 passed | identical |
| `test_g8_lp_turbine_export.py` | 2 failed, 4 passed | identical |
| `test_ccw_loss_chain.py` | 36/41 | **36/41, the same five gaps** |
| `test_1_nc_shift.py` | 1/4 | 1/4 |
| `test_2_ejector_stall.py` | 1/4 | 1/4 |
| `test_4_water_penalty.py` | 1/3 | 1/3 |

The one test that was DELETED rather than fixed is
`test_hydraulics.py::test_328d001_is_left_on_its_constant_because_its_geometry_conflicts`, which
pinned the deferral this pass closes. It is replaced by two that pin the closure instead.

`test_4_water_penalty`'s LEVER had to be re-pointed: it perturbed `EJ_CARB_FRAC`, which used to BE
the entrained composition and is now only its seed, because the ejector entrains the live 322E003
sump vector. It perturbs `state.y_scrub_ovf` instead and gets its PASS back.

### Two things measured that are worth not re-deriving

* **The 24 000 s free-run drift is 43 % SMALLER, not larger.** The settled-attractor drift that
  section 1f records as open moves PT-329201 140.70 -> 138.117 at HEAD and 140.70 -> **139.229** with
  the whole of Phase 4b in; the reactor overflow temperature moves +2.605 C against +1.614 C. That
  was not the expected direction and it is worth knowing before anyone attributes a future drift to
  this work.
* **The design seed after one tick is BIT-IDENTICAL to HEAD** on every probed state except the one
  deliberately re-derived: p_syn 140.69999999999902, T_ovf 183.00001718447572, react level
  79.99999971759262, all four 328 node pressures, both 328 column holdups, scrub level 50.0.
  `a328_d001_M` moves 10554.5 -> 2401.674596319621, which IS the A-6 closure, and it holds its own
  M_DES exactly so LI-328501 still reads 50.5.

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
| design-point residuals still open | `test_equation_audit_td014.py` (4), `test_equation_audit_desorption.py` (2), `test_equation_audit_species.py` (5), `test_equation_audit_td013_d002.py` (2), `test_scenario_coverage.py` (6), `test_g8_lp_turbine_export.py` (2), `test_transient_coldstart.py` (3, was 5 — re-measured at 7a6b605), `test_hp_carbamate_recycle.py` (3), `test_lv324501_routing.py` (3), `test_trend_coverage.py` (1, was 2 — re-measured at 7a6b605), plus singles in `test_c39_recycle_tears.py`, `test_equation_audit_322e002.py`, `test_g3_component_reconciliation.py`, `test_stripper_reaction_inventory.py`, `test_audit_stream_state.py`, `test_equation_audit_c10_props.py`, `test_321d003_level_switch.py` (2), `test_equation_audit_323_324.py` (3, was recorded as 2 -- re-measured on HEAD this session) | the same class of defect the drift work closed five of: an anchor computed on a different basis than the live path it normalises |

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

## 8. UI-page migration — open items

All ten screens are now generated from `Urea Simulation Docs/Equipment Drawing/UI Pages/*.pptx`:
the background is the slide minus the shapes the overlay supplies, and every overlay's position,
size, rotation and mirror are that shape's own transform. 321-1 / 322-1 / 322-2 came off the
2026-09-02 revision; 324-1 / 324-1b off the 2026-09-05 revision; 323-2 and 329-1 off the
2026-09-15 15:43-16:10 reissue that restored sixteen forgotten indicators; 323-1, 328-1 and
328-2 off the 2026-09-15 16:36-16:44 reissue that added four more. The procedure and the scripts
that run it are in `UI pages migration.md`.

**Closed since the last pass:** two 2026-09-15 drawing reissues put twenty previously undrawn
indicators back, and every one recovered its original binding without being retyped --
`harvest_binds.py` takes ordered sources, so the live `overlays.js` supplies current bindings and
`git show HEAD:frontend/overlays.js` fills in tags an earlier revision had dropped. The 15:43-16:10
pass restored sixteen (`PV-322201`, `FV-328404`, `FV-328406`, `FV-329401`, `FV-329402`,
`LV-328504`, `LV-329502`, `TT-328004/5/6/9`, `TT-323005`, `TT-323015`, `AI-328701`, `FT-329407`,
`LIC-328504`), fixed 328-1 shape 214 (it printed `LIC-328503` on the 328C003 leg) and retagged the
duplicate `TT-328007` to `TT-328009`; the generator's `RETAG` table is empty again. The 16:36-16:44
pass added `FIC-328402` + `FV-328402` (the 323E003 Comp-II wash draw, PFD stream 744), turned the
`TIC-328013` white frame into a bound `TT-328013`, and gave 328-2 a `TT-323009`. It also retagged
two 323-1 boxes: `TT-323004` -> `TT-323002` and `TT-323103` -> `TT-323008`, the latter needing one
`EXTRA` row because `RECIRC_323.D002` publishes the same `s.r323_d002_T` under both `.T_C` and
`.TI_323008`. `BOUND_TAG_FLOOR` is 203, the `t:'ind'` floor 199, the avalve floor 46 and the
white-frame ceiling 17 -- all four guard again rather than sitting stale.
`test_328d003_compartments.py` no longer pins an overlay key that the generator owns; icon
overlays honour `flipH`/`flipV` as well as rotation. Measured in the live page after every
reissue: **zero overlay-on-overlay collisions on all ten screens**, zero tag mismatches.

Still open:

- **No measurement is absent from the HMI.** The last one was the 323E003 shell-liquid
  temperature: the packet published it as `LPCC_3232.E003.TT_323003` while 323-2 labels the
  instrument `TT-323006`. The key is now `TT_323006` and the 323-2 box is bound, so it is no
  longer a white frame either. Down from 26 after the first re-seed.

  Five other paths read as missing against the pre-migration table but are same-value twins of
  something already on screen, so nothing is actually hidden:
  `RECIRC_323.D002.T_C` (the old `TT-323103`; `TT-323008` binds `.TI_323008`, and both leaves
  publish `round(s.r323_d002_T, 1)`), `STEAM_SYSTEM.LP.TI_sat` (`TT-329001` binds
  `HPCC_322E002.TT_329001`, the same `T_shell_lp`), `EVAP_324.E003.LI_324F003` (`LT-324501`
  binds `LIC_324501.pv`, and `_ctrl_ipd` is fed `lvl_f003` -- the identical percentage),
  `DESORB_328.D001.FIC_328404.vol_m3h` (the raw unlagged twin of the `FIC-328404` `.pv` that
  328-1 and 323-2 both show in m3/h) and `DESORB_328.C004.FFIC_329401.pv` (displayed as the
  SP/MV readout pair on 328-1).

- **Fifteen slots are white frames** -- drawn on a slide, nothing bound behind them. All are the
  unmodelled Unit-335 finishing side: `FT`/`FY`/`FQ-335401`, `FT`/`FY`/`FQ-335405`,
  `HIC`/`HV-335602`, `HIC-335609`, `HIC-335610`, `FIC-335405B`, `LT-335507` and its bargraph and
  `FFY-335406` on 324-1b, plus `FIC-335407` / `FV-335407` on 323-1. (`FQT-321401` now binds the
  packet's `totalizer`; `FFIC-329401 SP` / `MV` open FFIC-329401's own faceplate through the new
  overlay `ctl` route -- both 2026-09-17.)

- **324-1b lost its four external-override pushbuttons** (`EXT-OVR LV-324501A`, `EXT-OVR
  LV-324501B`, `TRIP_35_3`, `EXT-OVR HV-335602`): the 2026-09 slide draws no squares for them, so
  they would have floated over empty background. The exclusive A/B discharge-route selector is
  unaffected — it lives on the `LV-324501A` / `LV-324501B` overlays, which still carry
  `route:'A'` / `route:'B'` and still drive `OTS_LV324501_ROUTE`.

- **Eleven of the thirteen pump pairs have no backend state**, so their icons are display-only:
  A is drawn running, B stopped (`def:false`), and a click does nothing. They are
  `323P001`, `323P003`, `323P008`, `328P002`, `328P003`, `328P006`, `328P007`, `329P003`,
  `322P002`, `335P001`, `335P002`. Only `321P002 A/B` and `329P006 A/B` are commandable. The
  deck also never annotated the two 328-2 pumps (shape ids 119/120); they are recognised from
  the identical picture and the labels beside them, via the generator's `ADD_PUMP` table.

- **`img/pump-off.png` was re-coloured grey on this machine only (2026-09-17).** It was dark green
  (mean RGB 36/86/2 against ON's green); it is now the luminance of the same picture, alpha untouched.
  `*.png` is gitignored and neither pump icon has ever been committed, so a fresh clone has no pump
  icons at all. Decide whether the icons belong in the repository (`git add -f`) before relying on it.

- **Three overlays on 323-2 are nudged off their slide centres**, because an `.ov.ind` is sized
  by its value rather than by the label it replaces: `PIC-323203` (1189 -> 1183, it clipped the
  323F004 nav block), `SIC-323901` (128,573 -> 120,578) and `SIC-323902` (261,574 -> 266,578),
  both of which sat on the 323P001 A/B pump icons. The offsets and their reasons live in the
  generator's `NUDGE` table so a re-seed cannot silently undo them.

- **Six stream hotspots were dropped from 322-1**, because the 2026-08 drawing does not show the
  lines they sat on: `NH3_FEED`, `HP_DISCH`, `CARB_RECYCLE`, `HPCC_PROD` plus two with no
  identifiable line. The eight that remain each sit on a line carrying a tag that proves its
  identity. `HPCC_STEAM` (red, y 294) vs `HPCC_COND` (green, y 329) was resolved from
  `TT-329001` — worth a second pair of eyes. **No stream hotspots exist on the seven 2026-09
  screens at all**: the deck gives no way to identify which drawn line is which stream, and
  guessing would put a composition popup on the wrong pipe.

- **The 322-1 compressor-speed widget does not sit on its marker.** The slide reserves a 63 x 54
  box centred (96.7, 421.5); the widget is 196 x 53 and at that origin its right edge lands on
  the `AT-322701` indicator (187..266) and its bottom on the `AE-322801` chip (441..465). It is
  placed at (6, 352) instead. Either widen the marker on the slide or narrow the widget.

- **322-1 and 322-2 carry overlay-on-overlay collisions that predate this pass** and were left
  alone rather than changed without being asked. Four are permanent: on 322-1 the `LP STEAM` and
  `BFW/COND` stream hotspots each overlap `STRIP TOP GAS` (14 x 14 px) and `STRIP BOTTOM SOLN`
  overlaps the `323C003` nav block (31 x 16); on 322-2 the `OFF-GAS LP` hotspot overlaps the
  `322C001` nav block (11 x 16). Those four steal clicks from each other. Two more come and go
  with the plant state, because an `.ov.ind` is sized by its value: at some operating points
  `LV-322501` grows into `PT-323201` (7 x 9) and the `AE-322802` chip (3 x 9). Measured 6 at one
  sample and 4 at another, on the same build.

Not a gap, but worth knowing: `ots_ov_pos` went v5 -> v6 and `ots_ov_tags` v4 -> v5. Element keys
on the seven re-seeded screens are now derived from the DCS tag (`lt8508` -> `lt328508`), so their
stored drag positions and tag edits are dropped; 321-1 / 322-1 / 322-2 keep theirs, via the same
`carryOver()` rule the previous bump used.

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

- **The As-Built section *322E003 LP/MP Recycle-Carbamate Wash Cascade* describes a scrubber that is
  not the one in `main.py`.** Its `capacity_ratio` component-wise absorption model, the `q_wash`
  cold-wash energy sink and the `LP_absorber_load` diagnostic have no counterpart in
  `scrub_322e003`; the HV-322604 capacity model in that section is the only part now implemented
  (this work). Pre-existing. Reconcile the section with the code, or implement the rest.

## 7. Enhancement opportunities (optional)

- Integrate the Extended UNIQUAC electrolyte model for rigorous HP synthesis VLE.
- Experimental validation of the Unit 324 vacuum VLE (0.02–1.0 bar, far below the published
  35 bar floor).
- Extend stream coverage beyond the 55 of 163 PFD streams currently published.
