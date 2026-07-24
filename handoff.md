# Handoff Summary

## The goal we're working toward
Calibrate the `backend/main.py` state-space process engine against real DCS behaviour without
violating mass/energy conservation, and keep the HMI overlay registered on the baked DCS
screenshots. The current thread is a **full modelling-equation audit of every equipment tag**
against the eleven equation categories (total mass, component species, energy, flash, EoS/activity,
summation, kinetics, transport, hydraulic, constitutive, control), answering four questions per
tag: are the equations bound correctly, is the solver engine right, is hybrid variability required,
and what equations are missing. Deliverable mode is **audit + auto-fix**, one unit at a time.

## Current state of the code
* Audit report: **`EQUATION_AUDIT.md`** — architecture verdicts, 11-item findings register (all closed),
  per-tag tables for units 320/321/322/323/324/328/329, category coverage summary, applied fixes.
* **Solver verdict: Sequential-Modular is CORRECT for all ~57 tags.** Recycles are torn with
  prior-step lags; the tear variables are real dynamic states, dt ≪ every process τ, and SM gives
  bounded per-tick cost with no convergence failure — an EO solve could stall the HMI mid-transient
  and would put solver tolerance inside a `diffs 0` contract. No tag needs EO.
* **Hybrid variability: required, already present, and now much less frozen.** Split fractions,
  calibrated η modifiers, back-solved λ/UA, Inoue-Kanai, the ejector spindle law and the soft
  sensors are all legitimate hybrid layers. Both remediation slots so far attacked the same defect
  class — *a split fraction is only a valid hybrid layer if it is a function*, and several were
  constants.

### Remediation slot 1 — units 323 + 324 (findings F-1..F-5, F-10), commits `7ac7455` / `93a2fd6`
Every vaporiser outside the HP loop had its vapour rate bound as a frozen design split fraction of
the live inflow, so the mass balance and the energy balance were solved independently and the live
heater duty had no authority over the boil-up. Now:
* boil-up is duty-limited — `m_vap = min(φ·m_in, m_vap_des·q_avail/Q_des)` on 323C003/323E002,
  323F010/323E010, 324E001, 324E003;
* 323F004 runs a **true isenthalpic flash**: saturation constraint
  `T_flash = 106 + [Tsat(P) − Tsat(1.13)]` plus the enthalpy balance
  `m_701·λ = m_314·cp·ΔT − M·cp·(T_sat−T)/τ`, which collapses the existing energy ODE to exactly
  `dT/dt = (T_sat − T)/τ` (energy conserved);
* the 324 melt strengths `w1_live`/`w2_live` are **outputs**, not the pinned `R324_W_EV*`
  constants, and drive `urea_pct` / `PY-324201` / `AY-324701`;
* **F-10** — all four condensing-steam chests floored at `max(Q, 0)`. Un-floored, a shut steam
  valve clamped `p_chest` to 0.02 bar a (Tsat ≈ 17.5 °C) and `UA·(Tsat − T)` turned every heater
  into a *refrigerator*: probe-measured 22 °C Evap-I melt and 13.6 °C in 323C003;
* `conc_infer_324` gained a band clamp on the reference mole fraction (`w_des` is now a live
  argument that legally reaches 0 on cold start and divided by zero there).

### Remediation slot 2 — 322E002 HPCC (finding F-6 / TD-007) — LANDED THIS SESSION
`HPCC_FRAC_GAS_DES` was a split measured at 170 °C / 144.2 bar a and then frozen, making the
condenser thermodynamically inert: shell temperature and synthesis pressure moved the duty and the
NTU outlet temperature but **not one mole of condensate**. The calibration is not discarded — it
becomes the anchor of a real flash.
* `_hpcc_flash_split()` back-solves `K_des,i` from `HPCC_FRAC_GAS_DES` and the LIVE feed every tick
  (so the melt's measured activity coefficients stay baked in), then corrects to live (T,P) via the
  carbamate equilibrium `Kp = p²_NH₃·p_CO₂`. Because Kp is a **third-order** product the
  dissociation-*pressure* slope is ΔH_carb/3 ≈ 53.3 kJ/mol — literature-confirmed (Bennett 1953;
  Ramachandran 1998) and derived from a constant already in the code. Raoult for H₂O
  (36 900 J/mol), Henry for N₂. φ_des ∈ {0,1} species sit outside the flash.
* Rachford-Rice by **bisection, not Newton**: g(ψ) is strictly decreasing, so 60 sweeps are exact to
  2⁻⁶⁰ at bounded cost with no possible convergence failure inside an OTS tick.
* **The equilibrium flash alone was wrong for this vessel** and this is the important part. The
  distributing K-values are tightly clustered, so a common factor moves the whole mixture together:
  the raw target swings φ_CO₂ 0.0009 → 1.0 across 150 → 190 °C. `References/HPCC description.md`
  §5.2–5.3 says 322E002 is interfacial **mass-transfer** limited, so φ is relaxed toward the target
  over `HPCC_TAU_FILL_MIN`, making the split a dynamic state `s.hpcc_phi`. That was the genuinely
  missing equation — the condenser had no composition dynamics at all.
* Three independent anchors keep the pin: the flash short-circuits to the calibration when the T
  and P ratios are exactly 1; `dt = 0` on module-load/boot-pin passes zeroes the relaxation; and the
  result is blended through `_disturbance_gate` exactly as `T_prod` is.
* `p_bub` de-pinned from the frozen `HPCC_T_PROD_DES_C` onto the live gated `T_prod` (telemetry
  only — it does not enter `pt_target`, so no new loop). `phi_gas` published in the packet.
* **Loop-gain check** against the `_disturbance_gate` runaway path came back **negative feedback**
  in both legs, verified not assumed: T_prod spans 0.0205 °C (shell disturbance) and 0.2329 °C
  (N/C disturbance) over the final five minutes — monotone convergence, no ringing.

New tests: `backend/test_equation_audit_322e002.py` (8). Probe: `scratchpad/probe_322e002_flash.py`.

### Remediation slot 3 — downstream species balance, 323 + 324 (F-8), commit `28c785f`
Species tracking stopped dead at LV-322501. A six-species layer (Urea, Biuret, NH3, CO2, H2O, HCHO)
now **rides on top of** the existing mass/energy ODEs — same flows, so C1 is untouched by
construction and the design anchors cannot move. Two pieces of real physics fell out of the data:
**biuret formation** (2 Urea -> Biuret + NH3, Arrhenius, extents back-solved from the PFD's
0.24 % -> 0.85 % rise; 338 kg/h total vs the 322 kg/h the stream flows imply) and
**relative-volatility vapour compositions** `y_i = a_i*w_i / sum(a_j*w_j)`, which IS the C6
summation. Sum w reads exactly 100.0000 at every stage, every tick. Feed composition is the LIVE
stripper bottoms, so strip efficiency now reaches the product.
Closing it exposed **F-11 / TD-011**, since resolved in slot 5.

### Remediation slot 4 — 328C003 hydrolyser reaction extent (F-7), commit `b60ffa5`
The hydrolyser had **no extent at all** — a frozen overhead split with the endotherm in a back-solved
latent, and the rate law only inside a read-only soft sensor. It is a trayed column, so **plug flow,
not a CSTR** — the only way the PFD's 0.82 % -> 1 ppm is reachable (CSTR at k.tau=10.14 gives 91 %;
plug flow gives 99.996 %). `tau` scales inversely with throughput. The 812 kg/h overhead now
decomposes into reaction (360.0) + strip (452.0), both exactly design at the seed.
Operator-visible now: 200 °C -> 0.32 ppm slip, 180 °C -> 88 ppm, 160 °C -> 1252 ppm, 140 °C ->
3994 ppm; 2× throughput -> 102 ppm, 3× -> 830 ppm. **Category C7 (kinetics) is now complete.**
It did NOT need the full 328 species vector — hydrolysis is a flow-through conversion.
Docs updated autonomously: As-Built gained **Revision Delta #16** and a rewritten §3.6 (the φ table
now states it is the anchor, not the answer) and §1.4; `TECH_DEBT.md` TD-007 marked **CLOSED**;
`EQUATION_AUDIT.md` §5 gained the 322E002 section and the C3/C4/C5/C6 category verdicts were
refreshed (they still described the pre-remediation state).

### Remediation slot 5 — 323E010 / 323F010 missing second feed (F-11), commit `c669653`
**F-11 was not a data error — the model was missing a feed.** The licensor confirms the real
topology: **319 + 331 -> 323E010 (LP steam, shell side) -> 323F010 (vacuum) -> gas 790 + solution
315**, and 315 is 317 before the pump. Stream 331 is the granulation-scrubber urea-recovery return
(3270 kg/h, 44.37 % urea, 55 % water, **40 C**); the engine had it entering at 323D002, downstream
of the balance it closes. Three closures on the licensor's own flows: total mass 104 840 vs 104 860
(**0.019 %**), urea 0.06 %, and — decisively — **formaldehyde 7.52 kg/h in vs 7.39 out (1.7 %)**,
which settles it because HCHO is non-volatile and 331 is its ONLY source anywhere in the plant.
Before the fix the melt carried HCHO no stream fed; it lived only as a frozen number in `W_S317`.
Back-solved stage residual **-1414 kg/h -> exactly 0.000**; water closure term 1.4 t/h -> 1.2 kg/h.
323F010 still **un-pinned** but now lands on 79.963 % vs the PFD's 80.00 (was 78.444).
Design duty **5048 -> 7249 kW** — 331 arrives 59 C below the product, so it is a heat SINK.
`R323_MEVAP_DES` was written as a SUM deliberately so `R323_M317_DES` keeps its exact bits and every
unit-324 constant stays byte-identical. `_sol_stage_anchor` / `sol_advance` gained an optional
second inlet (adds 0.0 when absent, so the other four stages are bit-identical).
New tests: 3 in `backend/test_equation_audit_species.py`. Probe: `scratchpad/probe_f11_331.py`.

### Remediation slot 6 — unit 328 desorption train species layer (F-8 remainder / TD-009), commit `1271276`

The last lumped-mass island. 328C002 and 328C004 moved material with **frozen overhead split
constants** (`R328_C002_PHI737`, `R328_C004_PHI750`) and no composition existed anywhere in unit 328.

**The finding that made it anchorable.** Read as mass %, the PFD says carbon is not conserved across
328C002 — 1658 kg/h CO₂ in, 858 out. It is: **liquid rows are mass %, vapour/gas rows are MOLE %**,
and the tabulated `Average Molar Weight` row proves it (stream 737 reads 20.81 as mole %, 18.94 as
mass %; the PFD tabulates 20.81). Verified across ~90 streams in all four tables. Read correctly all
three columns close per component to **under 2 kg/h in 34–40 t/h**, nothing fitted.
*This also retired the stream-790 "accepted variance" recorded in slot 5 — same misreading; 790's
CO₂ closes to 0.25 kg/h.* Probe: `scratchpad/probe_f8_pfd_units.py`.

**From the Uhde datasheet UD-AU-328-EC-0001** (`Urea Simulation Docs/New folder/328-1/`, a scanned
PDF — render it with PyMuPDF, `pdftotext` returns nothing): 328C002 and 328C004 are **ONE 25.5 m
stacked tower**, corroborated independently by Stamicarbon's "top part / bottom part of the
desorber" wording. 15 and 22 executed trays, ID 1250 mm, 40 mm weir, 3125 × ⌀6 mm holes. Holdup went
from a 900 s guess (8442 / 8431 kg) to geometry (**1588 / 1436 kg**) — the real columns respond ~5×
faster. The tray counts drive a Kremser stage correction so the columns degrade like columns.

**Two defects it exposed.** `R328_C003_W_UREA_746` was hardcoded **0.0082 — stream 738's urea, not
stream 746's** (+7.9 % on the hydrolyser load; PFD says 0.76 %). And the trace-species ODE is stiff:
328C004 holds **1.4 grams** of NH₃ against 330 kg/h throughput, τ ≈ 0.015 s vs a 0.25 s tick —
explicit Euler walked 328C002 from 0.63 % to 2.2 % ammonia over four simulated hours. `des_advance`
is **implicit** (closed-form, no iteration, exactly stationary at design).

**Verification.** 4 h hold on the PFD compositions. LP strip steam 100/90/80/70/50 % → condensate
NH₃ **1.0 / 9.6 / 122 / 1108 / 16 035 ppm**. Hydrolyser 200→160 °C → urea slip **0.30 → 1161 ppm**,
matching the *Gap Resolution* study's independent "0.32 → over 1200 ppm" prediction.

New tests: 10 in `backend/test_equation_audit_desorption.py`. Probes: `probe_f8_pfd_units.py`,
`probe_f8_328.py`.

### Remediation slot 12 — `R3232_CP` reconciled against the carbamate-cp reference, commit `4ab1514`

Documentation only; **no model change**, so the pin is unmoved by construction (`leaves 25 / keys
15 / diffs 0`) and the suite count is unchanged. The gap "`R3232_CP = 3.0` needs a *sourced*
carbamate cp" is closed as **un-sourceable by design**, not as a pending source, using the new
`References/Ammonium Carbamate Heat Capacity Data.md`.

The finding: there is **no single valid equation** for the reactive aqueous carbamate cp. The
rigorous e-NRTL / Extended UNIQUAC route is a full electrolyte package (six-equilibrium speciation,
per-species partial-molar cp, an excess term from ∂²G^E/∂T², fitted binary parameters; ion cp
tabulated only at 298.15 K) — out of scope for a frozen-enthalpy sequential-modular engine. The one
closed form (Chauhan cubic, ~2.08 kJ/kg·K @90 °C) is the **pure molten salt**, coefficients printed
as images, and the reference says a frozen polynomial "drastically underestimates" real duty. The
governing property is the **apparent (reactive) cp** — carbamate ⇌ NH₃ + CO₂, ~70–85 kJ/mol — which
no constant can carry ("cannot be accurately represented by a singular static value").

Where 3.0 lands: pure solid carbamate ~1.9–2.2; the frozen band for the **solution** is 3.2–3.8
(~3.64 mid at 40/25/35 wt % carbamate/NH₃/water, 80 °C); Stamicarbon CO₂-stripping runs lean in free
ammonia → the ~3.2 low end. So **3.0 is above pure-salt ~2.1 and ~6 % below the Stamicarbon floor** —
a defensible lean-liquor frozen value, on the low side, coherent rather than arbitrary. It is
**locked**: the back-solved `A323_C005_LAM` and the 323E003/323E011 duty integrators use 3.0 and
`test_equation_audit_c10_live_cp.py` pins `== 3.0`, so any change re-solves the anchor — a re-solve
of the 323 energy balance, not a constant swap.

Surgical edits: `backend/main.py` (comment at the definition), `test_equation_audit_c10_live_cp.py`
(docstring), `TECH_DEBT.md` (the "Still open" entry), `Urea OTS — As-Built … Reference.md`, and this
handoff. `aqueous_cp` remains the wrong correlation regardless — carbamate ion cp is negative
(electrostriction), the opposite sign of water's IAPWS slope.

### Remediation slot 11 — three housekeeping gaps closed (dead constants, PID doc, launcher), commit `69d459e`

Small, deliberately separate from slot 10. Pin unmoved: **`leaves 25 / keys 15 / diffs 0`**;
full suite **222 passed in 992.57 s**, the same count as before the change.

1. **Five dead density constants deleted** from `backend/main.py`: `CO2_RHO`, `SCRUB_CARB_RHO`,
   `R323_C003_RHO`, `R323_F004_RHO`, `R323_F010_RHO`. Each verified dead first — one hit apiece
   repo-wide, the definition itself. Two stale rows in the As-Built §6.7 table fell with them:
   `CO2_RHO`, and **`CO2_VENT_MAX_FRAC`, which never existed in `main.py` at all** (the vent model
   is `CO2_VENT_COND` / `CO2_VENT_P_BARA`) — replaced by the constants the engine actually reads.
   This does **not** close the density gap; it stops the codebase overstating it.
2. **`Master_PID_Tuning_Constants.md` — new Appendix B** for the unit-324 evaporator masters, with
   the measured K_p table (+8.32 / +8.35 °C/bar, central difference over 1 h means), the lambda
   derivation, the halving and why, the residual limit cycle, and the two do-not-repeat warnings
   (the contaminated −17.5 °C/bar step test; the `v_conc` cap cannot be deleted). The plant DCS rows
   are **unchanged** — they are correct for the plant — but now carry a `†` and a footnote saying
   the simulator does not use them. Found while writing it: **33 of 46 sim controllers differ from
   their plant row**, all intentionally, and Appendix A's `_fic_flow` Kc column is on the **mass**
   basis while those loops are now **volumetric** (`Kc_engine = Kc_doc · ρ`, so `Kc·g` and every
   stability conclusion are unchanged). Noted in Appendix A so nobody "corrects" the engine to it.
3. **`launch.bat` / `.claude/launch.json` pinned to a resolved interpreter.** launch.bat now tries
   pythoncore-3.14-64 → any `pythoncore-*` → `py -3` → `python`, each through a `:try` subroutine,
   and a rejected candidate **falls through to the next** so a stale `pythoncore-*` left by a version
   upgrade cannot dead-end the launcher. Failure lands on `:nopython`, which prints the actual
   Settings path for fixing an alias. Every use of the interpreter (`pip`, `main.py`) goes through
   the resolved `%PY%`.

   **The guard demands a printed token, not an exit code — and that came from a failed test.** The
   first version ran `-c "... raise SystemExit(...)"` and checked `errorlevel`. Probing it with a
   copy of `cmd.exe` renamed `python.exe` — which is exactly what the Store stub is, a thing that
   exists at that path and is not an interpreter — showed it **exits 0 and the guard accepted it**.
   So the check is now `... print('PY_OK' if ...) | find "PY_OK"`: only a process that really
   evaluated the expression can produce the token. (`range(310,600)` rather than `>=`, because `<`
   and `>` are redirection operators inside a `.bat`.)

   Verified: `scratchpad/probe_launch_resolve.bat` → `REJECT-OK / FALLTHROUGH-OK / NOPYTHON-OK`;
   `scratchpad/probe_launch_quoting.bat` → the `start … cmd /k ""%PY%" main.py"` form survives a
   path containing a space. The whole file was then dry-run with only the server/browser lines
   neutered, and reached the wait loop on the resolved interpreter.

   **See the correction under "Python on this machine": the alias is NOT currently broken.** The
   earlier claim that the launcher "may fail from this environment" was asserted without ever
   running it, and was wrong. The fix is still right — but for robustness against a Windows setting
   that lives outside this repo, not for a live defect.

### Remediation slot 10 — TD-013 / TD-014 / TD-015 closed, cp made a property, commit `7a2cb67`

**TD-014 was an open-loop temperature integrator, and the operator's stream map is what found it.**
Walking 207 -> 208 -> 301/311 -> 313 -> 302/314 -> 319 -> 317 with every node instrumented
(`scratchpad/probe_td014_trace.py`) showed the stripper bottoms **bit-flat for 6 h** while `w_c003`
fell -0.0041 pp/h. So nothing rides in on the feed -- the ramp is born in the stage. A CSTR with a
2-minute residence and constant inputs cannot ramp for 14 h, so an input had to be moving: the
boil-up, falling 5.97 kg/h per hour, perfectly linearly (`probe_td014_c003.py`).

The identity (`probe_td014_ops.py` asserts it, and `test_equation_audit_td014.py` keeps it asserted):

    m_vap = M_DES*(q_avail/Q_DES)   and   lambda = Q_DES/(M_DES/3600)
    =>  P = q_avail - m_vap*lambda/3600 = q_avail*(1 - 1) = 0   IDENTICALLY, at every load

The stage temperature had **no input**. TIC-323007 was integrating against zero gain and walked
PV-329202 down forever; because a velocity increment is Kc*(dt/Ti)*err the walk RATE is
dt-independent, which is exactly the "tick-invariance" that made this look like physics. It is
one-sided (hence monotone) because the composition-split branch of the `min()` caps the other way.

**Fix:** the bubble-point relaxation 323F004 already used, giving `dT/dt = (T_bub - T)/tau`.
323C003's bubble point rides the live column pressure; 323F010's rides **composition** via Raoult on
water -- the real physics of a fixed-vacuum evaporator, and it makes TIC-323012 the concentration
controller it is on the plant. Raoult is quoted, not fitted, and captures 89-107 % of a 20-90 C
elevation against the licensor's own (w, P, T) triplets. It is **excluded** at 323C003/323F004,
whose NH3/CO2-bearing liquors it overshoots by 33 C and 16 C -- a test asserts that overshoot so
nobody unifies the two forms later.

**Result:** every 323 node's least-squares slope is now **exactly 0.0** over the second half of a
6 h run; PIC-329202 and PIC-329208 are flat to five decimals. `w_f010` settles at 79.9635 % -- the
0.037 pp under the PFD-317 anchor is where the LIVE stripper bottoms put it (55.838 % against a
tabulated 55.867 %), not a drift.

**324E001 / 324E003 -- TD-015, also CLOSED, and it turned out to be TD-013's blocker not its
follow-up.** The D002 pin was an ACCIDENTAL CLAMP on it: pinned, urea1_in is constant and v1_conc
sits within 0.4 kg/h of v1_duty, so the min() tie gave TIC-324001 partial feedback and the melt
drifted only -0.0011 pp/h. Unpinned, the branches separate by ~74 kg/h and the melt walks at
**~0.5 pp/h** -- a wandering product spec, worse than anything TD-014 fixed. Same closure applied,
plus the retune it forced. **The first step test was contaminated** (the loops had already diverged
in the same run) and reported K_p = -17.5 C/bar for TIC-324002, a NEGATIVE gain that would have
meant the controller action was backwards -- do not reuse that number. The clean measurement is a
central difference over 1 h means, +-0.05 bar with the master in MAN so the plant's wander cancels:
**K_p = +8.32 and +8.35 C/bar**, positive on both. So Kc = 2.0 was a loop gain of 16.7, which is
exactly the multi-hour limit cycle observed. Lambda-tuned to 0.04 (tau ~ 360 s, lambda = 3 tau) then
**halved to 0.02** against the min(v_conc, v_duty) relay nonlinearity -- halving measurably shrinks
the residual cycle (16 h envelope 0.42 -> 0.25 C and 1.33 -> 0.88 C), which is the evidence it is
controller-driven. Ti 120 -> 360 s. Velocity form, so the seed stays bit-exact at any Kc/Ti.
**Do NOT delete the v_conc cap** -- tested, and the stage diverges without it (psat underflows).
Residual: a bounded ~0.25 / 0.88 C limit cycle, recorded in TD-015 rather than hidden.

**TD-013 CLOSED, option (c).** With the inlet stationary the only argument for the 323D002 strength
pin was gone. `s.w_d002` is a plain `sol_advance` now: the tank tracks 323F010 with its own
residence-time lag, the last composition-blind node between reactor and evaporators is open, and a
C2 violation goes with it (`sol_pin_strength` fabricated +0.600 kg urea per 1000 kg holdup per call).
The design-point test that asserted `|w_D002 - 80.00| < 1e-6` was **asserting the pin, not physics**
-- it now carries the inlet's 0.10 pp band plus a stronger assertion that the two agree to 1e-4.

**323D002 rebuilt to its real topology** (operator brief + `References/323D002.md`): Comp I 80 m3
active (every nozzle, LIC-323507, TI-323008, 323P003 suction), Comp II 300 m3 passive (LI-323504,
indication only, dry in normal operation), and the **field tie-in spool** between them as an
operator boolean -- `s.HV_323D002_TIE`, `xv_toggle` id `323D002TIE`, clickable on screen 323-1 under
the tank. Shut: independent, Comp II stranded. Open: connected vessels sharing a *head*, so an equal
level fraction, and 323P003 draws the pool. Opening against a dry Comp II collapses a 10 % head from
80 m3 into 380 m3 -- **10 % -> 2.1 %**, near the pump's cavitation limit. That is the scenario the
button exists for. Three constants corrected from source: LIC-323507 SP **65 % -> 10 %** (the
compartment exists to hold residence under ~6 min so biuret cannot form; 65 % declared a 39-minute
residence), rho **1300 -> 1151 kg/m3** (PFD stream 315/317), Comp II seed **50 % -> 0 %**.
TI-323008 became a real state instead of an echo of the upstream separator.

**cp is a property now, not a section constant.** One lumped 2.5 kJ/kg.K covered the whole 323 train
(44 % @ 40 C to 80 % @ 99 C -- design values 3.029 / 2.760 / 2.679 / 2.500 / 3.248, a 30 % spread)
and one 4.0 covered every aqueous vessel from 40 to 200 C. Both replaced by departures anchored on
their own design point, so each returns the licensor's constant **bit-exactly** at the seed and every
back-solved lambda/UA and the boot-pinned `A328_LAMBDA_ABS` are untouched. `R3232_CP = 3.0` is
deliberately **left alone**: 323E003/323E011 carry a strong ammonium-carbamate liquor, not water, so
`aqueous_cp` is the wrong correlation and converting it would be a fabrication.

**One density went live too.** 323D002's level was a MASS span on a frozen 1300 kg/m3, but a level
gauge measures VOLUME -- a tank of thinner liquor read low by exactly the density error while the
operator saw the same inventory. LIC-323507, LI-323504, the weir threshold and the tie-in pooling now
run on `urea_soln_rho(w_live, T_live, 1151)`. At design the active volume comes out at exactly the
licensor's **8.00 m3**, an independent check that the 10 % setpoint and the 1151 kg/m3 agree.

**Equipment tags verified, and the brief had two digit slips.** The references are unambiguous:
**322**E003 is the HP Scrubber (`References/322E003 HP Scrubber Describtion.md`;
`Urea_Operating_Manual_Helwan.md`), **323**E003 is the LP Carbamate Condenser
(`References/323E003 323D001 323P001 Datasheets.md`; `328E021 ...` table), and **322**C001 is the LP
Absorber (`References/322P002 322E006 322C001 Datasheets.md`). There is no 323C001 anywhere in the
reference set. The code already matches the references -- nothing was changed.

**Verified on the RUNNING HMI**, not just structurally. Backend started with the real interpreter
(`%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe main.py` -- note `.claude/launch.json` and
`launch.bat` both invoke the bare `python` alias, which is the MS Store stub, CLAUDE.md sec 7).
Screen 323-1, element at (815, 702), 34x34, no clipping and no overlap with TT-323103 / TI-323008 /
LI-323504. Clicking it: CLOSED (red) -> OPEN (green), LIC-323507 **10 % -> 2.1 %** with LI-323504
reading the same 2.1 %, and the 8.00 m3 active inventory redistributing to 1.7 + 6.3 m3 -- **8.0 m3
conserved across the pooling**. Clicking again: shut, and Comp II's 6.3 m3 is stranded exactly as
the plant would leave it.

**New gates:** `test_equation_audit_td014.py` (9), `test_equation_audit_td013_d002.py` (12),
`test_equation_audit_c10_live_cp.py` (7). Pin unmoved throughout: `leaves 25 / keys 15 / diffs 0`.

## How to gate
```
set PY=%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe
%PY% scratchpad\regress.py scratchpad\pin_now.json
%PY% scratchpad\pindiff.py scratchpad\pin_now.json scratchpad\golden_pin.json   ->  25 / 15 / 0
cd backend && %PY% -m pytest -q -p no:cacheprovider                             ->  149 passed
```
Use `-p no:cacheprovider` — `backend/.pytest_cache` holds stale dirs that raise `WinError 183`.
**The suite takes 5–8 minutes and the pin settle takes ~2** — run them with a raised timeout or in
the background; the default 2-minute Bash timeout kills both before they print anything. `pytest -q`
buffers, so a background output file stays EMPTY until the run finishes — that is not a hang.

## Python on this machine (do NOT re-derive — this cost an earlier session dearly)
**Python 3.14.6 IS installed:**
```
%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe      # MSIX / App Execution Alias
%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe   # real binary  <- always safe
```
Never conclude an interpreter is absent from one alias. Never pipe a heredoc into an alias.

### Correction, measured 2026-07-23 — the alias is NOT currently broken

CLAUDE.md §7 and this section said "the bare `python` alias is a Microsoft Store stub that errors."
**That is no longer true on this machine and should not be repeated as fact.** Measured under
`cmd.exe`, PowerShell and the Bash tool:

```
where python  -> %LOCALAPPDATA%\Microsoft\WindowsApps\python.exe     (wins the PATH race)
                 %LOCALAPPDATA%\Python\bin\python.exe
python -V     -> Python 3.14.6                            exit 0
sys.executable-> %LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe
python -m pip -> pip 26.1.2                               exit 0
```

The WindowsApps entry is now the **PyManager app-execution alias forwarding to the real 3.14.6
install**, not the Store stub. It was a stub once — that is why the warning exists — but repeating
the warning as present-tense fact cost this session a **fabricated bug report**: the launcher was
reported as "may fail from this environment" without ever being run.

The advice still stands for a different reason. Which of the two `python.exe` wins is decided by
PATH order plus a per-user **Settings ▸ Apps ▸ Advanced app settings ▸ App execution aliases**
toggle that lives outside this repo. Flip it, or uninstall PyManager, and the same command becomes
the Store stub again. So keep using `%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe` — because
it is *pinned*, not because the alias is *broken*. `launch.bat` now resolves it that way explicitly
and proves the interpreter runs before using it (see slot 11).

## OPEN items (in TECH_DEBT.md)

**All eleven audit findings are closed.** What is left is the two remaining category gaps:

* **TD-006** — **half closed 2026-07-23.** The **hydrodynamic flooding limit is coded, gated and
  pushed**; the per-species enthalpy balance is what remains.

  *What landed.* The unit had no tube geometry at all — every "flood" term in `stripper_322e001`
  was a thermal metaphor for the steam-dilution branch, not a hydraulic limit. The licensor DDS
  (Uhde UD-AU-322-DZ-0003-003 p.3) supplies **2600 tubes, 31 × 3.0 mm → ID 25.0 mm, 6000 mm eff.**,
  and the sheet is self-consistent: N·π·d_o·L = 1519.27 m² against its own tabulated 1519.00
  (+0.018 %), so the tube count is confirmed rather than trusted. Three documents then agree —
  the bore is **0.984″**, so the 145 kg/h "1-inch tube" limit applies unscaled; the 6.000 m
  effective length is exactly what Brouwer ties to 80 % design efficiency; and the quoted 183 °C
  reference *is* `STRIP_FEED207_T_C`.

  *The key structural result.* 280 797 / 2600 / 145 = **0.7448** — the plant runs at 74.5 % of its
  flooding limit, onset at 134 % load. So the constraint is **one-sided and does not bind at the
  design seed**: `max(φ−1, 0)` returns the literal `0.0`, making `1−e⁰ = 0` and `1/(1+Kx) = 1`
  exact identities. **No anchored ratio was needed** — the pin guarantee rests on a physical fact,
  not on float operand ordering, which is a stronger contract than the plan had assumed.

  *Calibration from the literature, not fitted.* Brouwer's 3–4 °C-in-15-min bottom signature fixes
  `STRIP_FLOOD_T_K` = 3.83, capped by the same 11 °C reactor-liquor ceiling the steam-dilution
  branch already uses; the model returns 3.50 °C at 10 % over the limit. Measured cascade: overhead
  NH₃ recovery 89 % → 56 % at onset → 30 % at 180 % load, volatiles held in the bottoms and
  slipping to LP, exactly as described.

  *One sign trap, avoided on purpose:* `g_flood` reaches the **split only, never `eta_T`** —
  flooding *increases* residence time, so hydrolysis and biuret rise; `eta_T` scales `xi_hyd`, so
  folding it in would have cut hydrolysis the wrong way. A regression test pins this.

  *Deliberately not modelled:* the corrosion/lifetime drift (110 → 120 % as the bore grows) and the
  active-corrosion metallurgy — both multi-year effects with no place in a shift-length scenario.
  *One unsourced number:* `STRIP_FLOOD_ETA_K`; Brouwer publishes no efficiency-vs-flooding curve, so
  it reuses the unit's existing choke scale (`STRIP_ETA_KT` = 1.50) rather than invent a fit.

  **Still open — the per-species enthalpy half.** The bit-exactness contract is mapped in
  TECH_DEBT TD-006 so it need not be re-derived: the replacement must sit at
  `STRIP_DUTY_DES_KW * <factor> * 3600.0` with `<factor>` evaluating to a bare `1.0`, which an
  enthalpy ratio `H_live/H_des` computed by one shared function gives as `X/X`. It needs a
  carbamate dissociation enthalpy and NH₃/CO₂ latents at ~183 °C/140 bar — **none exist in the
  codebase**, and the literature sweep that would have sourced them did not complete (the subagent
  fleet hit the session limit). Per CLAUDE.md §1 they must be sourced or back-solved, not guessed.

  **Incidental finding, not fixed:** `eta_P` is a **dead lever** — `P_bara` is always passed the
  frozen `STRIP_P_DES_BARA`, so synthesis pressure has *no* effect on stripping efficiency. That is
  physically wrong and worth its own slot.
* **C10 constitutive properties** — densities and cp are still constants with no T-dependence
  (`tsat_steam`, `psat_water_bara`, `psat_nh3_bara` are live). The 328 datasheet work supplied two
  hard anchors: **PFD stream 739 = 923.28 kg/m³ @ 143 °C and the datasheet's 923.25 @ 143 °C**, both
  of which are simply *water at 143 °C* — direct evidence that the desorption train's liquid can ride
  a water correlation (Kell) with a urea-fraction correction. Implement as
  `rho(T) = RHO_DES * (1 + beta*(T - T_DES))`-style anchored corrections so every property is
  bit-exactly its present constant at the design temperature and the pin cannot move.
* ~~TD-001~~ RESOLVED (log was stale — the helper already uses the negative law, real `chk`).
* ~~TD-002..TD-005, TD-007..TD-011~~ RESOLVED.

**Durable lesson from TD-011:** a component balance that will not close is evidence of a **missing
stream** at least as often as it is evidence of bad source data. Check the topology against the
licensor before concluding the numbers are wrong — and argue it with a conserved tracer (here,
formaldehyde), because a species with exactly one source in the plant cannot be explained away as
rounding. `sol_pin_strength` survives as a rounding guard on the 324 melt only; it is an identity at
323F010 now.

**Durable lesson from TD-009 (328 half), two of them:**
1. **Check the units on the source table before believing a violated conservation law.** The PFD
   mixes mass % (liquid rows) and mole % (vapour rows). Read uniformly it destroys 800 kg/h of
   carbon across 328C002 and appears to contradict itself at stream 790. The `Average Molar Weight`
   row is the discriminator and it is unambiguous. We spent a whole finding on stream 790 as an
   "accepted licensor variance" that never existed.
2. **A species layer that works at percent concentrations does not automatically work at ppm.**
   Integrator choice is set by the *smallest* inventory in the vessel, not the largest — check
   τ = M·wᵢ/flow for the trace species before reusing an explicit scheme. 328C004 holds 1.4 grams of
   ammonia; explicit Euler at a 0.25 s tick overshoots it 16-fold.

### Remediation slot 8 — 322E001 enthalpy + eta_P (TD-006 CLOSED), commit `1da9280`
The MP-steam duty was proportional to feed **mass**, so composition never entered — identical
tonnages of water and of carbamate-rich liquor demanded identical steam, and carbamate dissociation
(58 % of the duty) was invisible to the header. Now a five-term per-species balance.

**The previous handoff said this was blocked on sourcing a carbamate enthalpy. It was not.**
`HPCC_DH_CARB_KJMOL = 160.0` was already at `main.py:2187`, and one search found the better value:
Frejacques via Brouwer (UreaKnowHow June 2009, p.12) publishes BOTH reactions at *process*
conditions — −117 kJ/mol at 110 atm/160 °C for carbamate, +15.5 kJ/mol at 160–180 °C for urea —
which sit far closer to 144 bar / 172–183 °C than the 159–160 quoted for *solid* carbamate at 25 °C.
NH₃ needs no latent heat at all: it is supercritical here (Tc = 132.4 °C).
**Validation: 37 831 kW against the licensor's 39 400 — 96.0 %, nothing fitted.** Only the ratio is
applied, so the offset cancels and the PFD duty stays the anchor.

That balance then *retired* `STRIP_FLOOD_ETA_K = 1.50` — flagged last session as the one unsourced
number — with **no replacement constant**, because ΔT_flood and the efficiency loss are the same
event measured twice. Three independent cross-checks put the knockdown at 0.8–2.9 %, not the 15 %
the fit gave; it was also double-counting the thermal collapse `g_T` already carries.

`eta_P` was dead because every call site passed the frozen design pressure. Now rides PT-329201,
gated on `_STEAM_READY` — the new feedback path would otherwise have the boot settle capture
`HPCC_UA`/`HPCC_LIQ_DES_LIVE` off a different transient (+305 kg/h, 0.16 %). Waking it also slowed
the N/C settle in `test_equation_audit_322e002`; measured over 40 min it converges monotonically
(span 0.027 by minute 40), and the old 10-minute window straddled the p_syn saturation at minute 6.
Window widened to 25 min **and** a step-decay assertion added, so that test is now stronger.

### Remediation slot 9 — C10 properties + the ripple break, commit `219cb45`
One cp (2.5 kJ/kg·K) covered every urea solution from 44 % urea to 97.71 % melt — 14–18 % high at
the evaporator ends, 23 % low at the LP end, i.e. most wrong exactly where the model does its most
important work, since the evaporation train's purpose *is* to change composition. cp is
**back-solved** (steam-table cp_water + the model's own anchor) and yields 2.072 kJ/kg·K against a
published molten-urea 2.0–2.1 — corroboration, not assumption. Density is **regressed from the PFD**
(§0 strict source): rho = 972.08 + 255.95·w − 0.4659·(T−100), both signs emergent from the fit.
Both applied as a departure from the anchor, so `ANCHOR + 0.0 == ANCHOR` holds to the bit.

**The ripple audit is the finding worth carrying forward — and it is NOT fixed.** Perturbing
live state and counting moving telemetry leaves showed unit 324 responding to an upstream
composition step in **0 of its 66 leaves**: `s.w_d002 = sol_pin_strength(..., R324_W_IN)` pins the
tank strength to a CONSTANT, so every upstream disturbance dies in the buffer tank. The block's own
comment claims the opposite.

Carrying the live deviation instead **did** restore the ripple (324 -> 13 of 66) — but it walked
D002 to 76.515 % urea against the PFD anchor of 80.00 and was reverted.

**RETRACTED: I first read that as "the 323 balance misses 80.00 by 3.5 points". It was my own bug.**
`w_f010` (323F010's outlet, and D002 Comp-I's ONLY inlet) measures **80.0014 %** — on the anchor —
and a one-in / one-out tank with no reaction must converge to its inlet. Comp-I turns over only
**alpha = 9.5e-5 of its holdup per tick**, so the patch's fixed reference inside its own feedback
loop was amplified by **1/alpha ~ 10 495**; replaying that recursion with a 0.0003-point capture
error lands on 76.5150 %, the observed value to four decimals. Arithmetic in
`scratchpad/probe_td013.py` and `probe_td013_recursion.py`.

**The ripple break is real and still open — only my explanation was wrong.** Adversarial review
then corrected the retraction too, on three points worth carrying:

* **"w_f010 delivers 80.00 %" was a 60-SECOND reading.** probe_td013.py settles only 240 ticks.
  The real trajectory is 80.0013 % at 60 s, 79.9239 % at 6 h, 79.8704 % at 14 h.
* **"positive feedback runaway" is the wrong mechanism.** The recursion is a STABLE contraction
  (lambda = 0.999905 < 1); nothing diverges. It is DC-gain amplification of a frozen constant,
  w* = w_f010 + (A-ref)/mu with 1/mu = tau/dt. Because mu = dt/tau, HALVING THE TICK DOUBLES THE
  ERROR — which is itself the proof the construction was numerical, not physical.
* **My "0.0003 pp capture error" was back-solved to match, so it was circular.** The sourced value
  is the _w_norm residue on the PFD-317 row: that row sums to 99.99797, so _w_norm lifts 80.00 to
  W_S317['Urea'] = 0.8000162403296788 against R324_W_IN = 0.80 exactly. A-ref = -1.624e-05
  reproduces 76.5137 % vs the reported 76.515 — independently derived, not fitted.
* **And a defect in my own evidence:** the "unpinned" column of scratchpad/probe_td013.py is INERT.
  It drives its shadow tank with m_in = s.tlag.get("R323_m317", 0.0) and no such key exists, so
  sol_advance returns its input unchanged. That probe was cited in three documents.

**TD-014 is the finding that actually governs TD-013.** w_f010 is on a perfectly linear
-0.0067 pp/h ramp that never arrests (slope constant to 0.12 % over 12 h, tick-invariant to 0.4 %).
It breaks test_equation_audit_species.py:85 at ~9.5 h, which no test reaches. Urea is displaced
predominantly by WATER, and w_f004 drifts too, so the origin is at or upstream of 323F004.

So the pin CANNOT come out yet, even though dropping it is the agreed target: the tank would then
track that ramp (0.071 pp low at 6 h, 0.131 pp at 14 h). Fix TD-014 first, then drop the pin.
Separately, sol_pin_strength is itself a C2 violation — it fabricates +0.600 kg urea per 1000 kg
of holdup per call — but that was tested as the ramp's cause and REFUTED.

**Durable lesson (slots 8-9), and it is the same one three times:**
1. **A dead term passes every gate.** `eta_P` was recomputed each tick from an argument every caller
   froze; `sol_pin_strength` erased the very composition it was documented to preserve. Neither
   showed up in the pin, the suite, or a code read. **Reading code cannot distinguish a live term
   from a dead one — perturb it and count what moves.** `scratchpad/audit_ripple_live.py` is the
   harness; it flattens the telemetry packet to ~1162 scalar leaves and diffs them.
2. **"Blocked on sourcing X" deserves one grep before it is believed.** TD-006's enthalpy half sat
   blocked for a session on a constant that was already in the file.
3. **Check the probe handle is on the live path.** The first ripple pass perturbed
   `STRIP_FEED207_KMOLH` and saw zero response — but that is a *default argument* the live tick
   never reads. A null result from a broken probe looks identical to one from a broken model.

**Large binaries push via Git LFS, not a plain pack (2026-07-24).** `References/` is now versioned
(slot-12 follow-on, commits `ffe7974` + `e65edcc`): 38 markdown sources normally, and the two source
PDFs (`Merged_Searchable_PIDs.pdf` ~61 MB, `Helwan PFDs meged.pdf`) through **Git LFS** (`git-lfs
3.7.1`; `.gitattributes` routes `*.pdf` through the filter). A direct HTTPS pack push of the 61 MB
blob returned **HTTP 408** from the remote twice — the uplink is ~176 KB/s, past the git smart-HTTP
server window — and neither `http.version HTTP/1.1` nor a raised `postBuffer` helped; LFS's chunked
upload cleared it. The `.gitignore` `*.pdf` "not versioned" rule is left intact, so these two are
`-f` exceptions added by explicit owner decision; any other `*.pdf` stays excluded. Future >~50 MB
binary: `git lfs track` it before the first `git add -f`.

## Standing session commands (CLAUDE.md sections 6/7)
* **Caveman mode ON** — invoke the `caveman` skill at session start; prose only, code/commits normal.
* **Graphify** — CLI installed (`graphifyy` 0.9.22; `graphify.exe` in
  `%LOCALAPPDATA%\Python\pythoncore-3.14-64\Scripts\`, NOT on PATH). Graph is `graphify-out/`, 6080
  nodes / 6355 edges, still built from `411080c` (many commits stale). NOT refreshed: a
  `graphify update .` needs LLM semantic extraction of 58 changed doc/image files (0 cache hits),
  which needs subagents or a Gemini key. **Do NOT run AST-only and merge** — one doc file supplies
  4487 of 6080 nodes and `build_merge`'s dedup collapses the graph to ~1858 (the `to_json` shrink
  guard rejects the write, so it just wastes a run). If a run is aborted after `save_manifest`, drop
  the stamped code entries from `manifest.json` so the next `--update` re-extracts them.
* **`/project-scaffolding`** — wizard for NEW projects. Do NOT point at this repo root.

## Durable gotchas (things that wasted time — don't repeat)
* **Subagent/workflow capacity is a real blocker.** A 12-agent audit workflow was launched and
  every agent died on "You've hit your session limit"; the workflow returned `[]` with
  `agents_done 0, agents_error 12`. Zero results were cached. The audit was then done **inline in
  the main loop**, unit by unit, which is also what Scope Lock wants. Prefer inline for this repo.
* **`s.F_CO2_th` is NOT an operator handle** — `step_sim` recomputes it every tick from the feed
  line (main.py:3277), so assigning it in a probe does nothing and the disturbance gate stays 0.
  Use `s.ratio_SP`, `s.HIC_322602`, `s.HIC_322605` or `s.steam.valve_supply_pct`.
* **`s.steam.valve_supply_pct` needs `s.steam.pic204_mode = "MAN"` first** — PIC-329204 in AUTO
  drags the valve straight back to its seed and the gate never opens.
* **The pin is a unit-322 contract only** (HPCC_UA, REACT_TEAR_DES, GCB pins …). It is blind to
  323/324/328 behaviour, so `diffs 0` alone does NOT prove a downstream change is safe — probe it.
  Conversely it IS sensitive to 322 changes, which is why 322E002 work needs the triple anchor.
* Workflow audits: a dead/limit-killed refuter returns a NULL verdict; the script bucketed null as
  "refuted", so a "0 survived" headline was an artifact. Count nulls separately and Read the journal.
* Overlay placement: the baked DCS indicator is a flag (wide value BAR + narrower TAB below), so the
  black-blob centroid sits ~5 px low. Isolate the BAR as first..last row at >=60 % of max width.
* Rewriting `overlays.js` from PowerShell: `Get-Content`/`Set-Content` default to the ANSI codepage,
  which mojibakes the em dashes and prepends a BOM. Use `[System.IO.File]::ReadAllLines/WriteAllLines`
  with `New-Object System.Text.UTF8Encoding $false`.
* Backend changes to any of the four pin-hashed files invalidate the pin CACHE (forces a re-settle)
  but do NOT change the 15 pin VALUES — expect `diffs 0` still.

## Next steps
1. **TD-009** — component species layer downstream of unit 322. Largest remaining gap and the
   blocker for TD-008; needs its own project, not a fix slot.
2. **TD-008** — real 328C003 hydrolyser kinetics, once TD-009 gives it species to work on.
3. **TD-006 — CLOSED 2026-07-23** (`1da9280`), both halves. So is the `eta_P` dead lever, and so
   is the unsourced `STRIP_FLOOD_ETA_K`. See "Remediation slot 8" above.
3a. **TD-012 / C10 — cp side CLOSED, density side still open.** Every cp in units 323, 324 and
   328 and at 322C001 is now a per-stream / per-vessel departure. Still open: the **density** work —
   the PFD's >150 °C row runs ~4 % above physical water (analysed in TD-012, unchanged), the
   volumetric-controller densities (`RHO_744_KGM3`, `RHO_741_KGM3`, `R328_C002_RHO`,
   `R328_C004_RHO`). `urea_soln_rho` / `aqueous_rho` are the vehicles. `R3232_CP` is **no longer on
   this list** — reconciled 2026-07-24 (slot 12): it is un-sourceable to any single equation by the
   physics, not merely awaiting a source, so it stays 3.0, documented and pinned. The five **dead**
   density constants that used to be listed here are **deleted** (slot 11) — they were never part of
   this gap, only noise in it.
3b. **TD-015 — CLOSED 2026-07-23** with TD-013/TD-014; it was TD-013's blocker, not a follow-up.
   324E001/324E003 got the same bubble-point closure plus a measured retune (K_p = +8.3 C/bar on
   both, Kc 2.0 -> 0.02, Ti 120 -> 360 s). Residual: a bounded limit cycle, 16 h envelope 0.25 C on
   E001 and 0.88 C on E003, from the `min(v_conc, v_duty)` branch switching. Removing THAT means
   replacing the concentration cap with a smooth equilibrium relation — deleting the cap outright was
   tested and the stage diverges. Not attempted; it is a modelling change of its own.
3c. **`Master_PID_Tuning_Constants.md` — DONE 2026-07-23 (slot 11).** The TIC-324001 / TIC-324002
   retune is now **Appendix B**, with the measured gains and the derivation; the plant rows carry a
   `†` pointing at it.
4. Refresh the graphify graph once semantic extraction is available (do not AST-only-merge).
5. `Master_PID_Tuning_Constants.md` still names loops by pre-rename tags / the retired ratio basis.
   Still open, and now scoped by measurement: **33 of 46 sim controllers differ from their plant
   row** (all intentional), and Appendix A's `_fic_flow` Kc column is on the mass basis while the
   engine runs those loops volumetrically. Neither is a tuning error — both are documentation drift.
6. Confirm the 321-1 / 323-1 registration on the RUNNING HMI (LSK was bumped v3 -> v4).
7. `FFIC-329401` / `TIC-328012` sit on two-box SP/MV ratio panels; which row the live PV covers is a
   design decision, left alone.
8. Decide whether to build the ejector motive-steam model.
9. Blocked on you: sprint items 7, 22, 25, and item 3a (#17) pending a 328D003 level controller.
