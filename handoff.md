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
The bare `python` alias is a Microsoft Store stub that errors. **Python 3.14.6 IS installed:**
```
%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe      # MSIX alias
%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe   # real binary
```
Never conclude an interpreter is absent from one alias. Never pipe a heredoc into the stub alias.

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

### Remediation slot 9 — C10 properties + the ripple break, commit `SLOT9SHA`
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

Carrying the live deviation instead **did** restore the ripple (324 → 13 of 66, first at tick 39,
the 80 m³ tank lag) — but it also walked D002 to **76.515 % urea against the PFD stream-317 anchor
of 80.00**, failing four design-point tests. **That 3.5-point gap is the real finding**: the pin is
documented as a rounding guard, and 3.5 points is not rounding — the 323 balance genuinely does not
land on 80.00 and the pin has been absorbing the difference. **Reverted**, because breaking the §0
PFD anchor is worse than the ripple break. Now TD-013; reconcile the 323 balance first, then
un-freeze the pin. It stayed hidden because Comp-I tau is ~1 h and no test runs that long.

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
3a. **TD-012 / C10 — PARTIALLY closed 2026-07-23.** Urea-solution cp and density are live
   correlations and unit 324 uses them per-location. Still open: the **aqueous/water** side (the
   PFD's >150 °C density row runs ~4 % above physical water — analysed in TD-012, unchanged) and
   the volumetric-controller densities. `urea_soln_rho` is in place as the vehicle for that work.
4. Refresh the graphify graph once semantic extraction is available (do not AST-only-merge).
5. `Master_PID_Tuning_Constants.md` still names loops by pre-rename tags / the retired ratio basis.
6. Confirm the 321-1 / 323-1 registration on the RUNNING HMI (LSK was bumped v3 -> v4).
7. `FFIC-329401` / `TIC-328012` sit on two-box SP/MV ratio panels; which row the live PV covers is a
   design decision, left alone.
8. Decide whether to build the ejector motive-steam model.
9. Blocked on you: sprint items 7, 22, 25, and item 3a (#17) pending a 328D003 level controller.
