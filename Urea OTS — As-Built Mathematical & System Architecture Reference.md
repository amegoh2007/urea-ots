# Urea Plant Operator Training Simulator
## As-Built Mathematical & System Architecture Reference Document

**Project:** HP Synthesis Loop OTS — Units 321 / 322 / 329
**Classification:** Engineering Reference — Not for Process Guarantee
**Equation source:** `backend/main.py`, `backend/reactor.py`, `backend/steam_system.py`, `backend/controllers.py`

> **Format note.** This Markdown master supersedes the binary PDF of the same name (git-ignored, no editable source). Equations are expressed in LaTeX for fidelity. Numeric constants are bit-identical to the engine pins.

### Revision History

| Rev | Date | Snapshot | Notes |
|-----|------|----------|-------|
| 1 | 2026-06-05 | Gemini HTML export | Original as-built (Sections 1–6 below). |
| 2 | 2026-06-22 | commit `a0a9180` (branch `fix/reactor-level-drain-and-vent-coupling`) | Add Revision Delta + PART F (full-loop turndown multi-settle audit). Sections 1–6 transcribed faithfully from Rev 1; see Revision Delta for post-snapshot model changes. |
| 3 | 2026-06-24 | branch `fix/reactor-level-drain-and-vent-coupling` | Reactor 322R001 dynamic liquid-inventory (Domino) coupling: HV/HIC-322605 given strict hydraulic authority over the bottom take-off, which IS the 322E001 stripper feed. Fixes stale HP-stripper level (excess reactor flow / valve had zero authority over 322E001 mass balance). See Revision Delta #7. |
| 4 | 2026-06-24 | branch `fix/reactor-level-drain-and-vent-coupling` | Reactor 322R001 mass-balance recycle-mass transport lag: the production In term `\dot m_{in}` now lags the synthesis-loop recycle surge through τ_rec (φ_f prompt + (1−φ_f) lagged), so HV-322605 has PROMPT hydraulic authority over LT-322504 (was sluggish — zero-delay recycle refilled the holdup as fast as the valve drained it). See Revision Delta #8. |
| 5 | 2026-06-24 | branch `fix/reactor-level-drain-and-vent-coupling` | LT-322504 re-scoped from the full 25 m column to the datasheet N7 narrow band (1.5 m span; top tap 1.0 m above the overflow line) per UD-AU-322-EC-0006. Display referenced to a design-valve SHADOW holdup so the slow off-seed loop relaxation cancels (design pins 80.0000 % bit-exact) while an HV-322605 move opens a properly-damped narrow-band response. Documents the discovered (out-of-scope) latent HPCC/loop seed-vs-fixed-point drift. See Revision Delta #9. |
| 6 | 2026-06-25 | branch `fix/reactor-level-drain-and-vent-coupling` | 322F001 HP-ejector spindle characteristic `phi_sp` direction INVERTED (positive → negative equal-%). The motive NH₃ is supplied by 321P002 A/B positive-displacement (triplex) pumps ⇒ motive mass flow is constant; closing the converging HV-322602 nozzle raises jet momentum `ṁ²/(ρA)` ⇒ raises entrainment ⇒ drains the 322E003 sump ⇒ LT-329501 FALLS on closing. Design anchor (74 %) bit-exact; sump attractor re-stabilises. See Revision Delta #10. |
| 7 | 2026-06-25 | branch `fix/reactor-level-drain-and-vent-coupling` | 322F001 → 322E002 → 322R001 forward-carbamate domino: an HV-322602 move now feeds the reactor holdup. Spindle-attributable draw `ṁ_suc·(1−1/φ_sp(θ))` (≡0 at θ=74) is washed-out (τ_fwd = 8 min) and its high-pass injected into the ACTUAL holdup only — a mass-conservative transient swell that raises LT-322504 on closing, falls on opening, and decays to 0 at steady valve. Design pin 80.0000 % bit-exact (shadow excluded from `ṁ_fwd`). See Revision Delta #11. |
| 8 | 2026-06-25 | branch `fix/reactor-level-drain-and-vent-coupling` | 322E003 carbamate-condensation spindle-intensity coupling: HV-322602 now drives TT-322002 (bottom carbamate-overflow temp) and the full 322E003 thermo. Condensation duty scaled `q_ccw·χ_sp`, `χ_sp = 1 + 0.25·(1−1/φ_sp(θ))` (same negative equal-% driver as Δ#11), composed before the one-sided flood-choke. Closing → χ_sp>1 → more condensation → TT-322002 rises; opening → falls (+flood-choke). φ_sp-keyed ⇒ pin bit-exact at θ=74 (χ_sp≡1) independent of the off-NLL sump level. See Revision Delta #12. |
| 9 | 2026-07-16 | branch `master` | 323E003 tempered-water circuit built out (first Unit-323 entry in this document; Sections 1–6 remain scoped to the 321/322 HP loop). TIC-323013 re-anchored from the 323E003 shell outlet (74 °C) onto the tempered-water **supply** (PFD stream 1102, 55 °C) and its SP span re-cut to 45–65 °C, which had previously *forbidden* the design SP. TV-323013A/B given true split-range opposites off one `op` (`θ_B = 100 − θ_A`, sum ≡ 100). The `(op/50)` linear duty fudge retired for the physical driving force `Q = UA·(T_shell − ½(T_sup+T_ret))` — bit-identical at design. TT-323015 (stream 1103, 65 °C) published from the new return state. See Revision Delta #13. |
| 10 | 2026-07-17 | branch `master` | 328 desorption train (first Unit-328 entry; Sections 1–6 remain scoped to the 321/322 HP loop). Stream 746 freed from a static constant: the 328E021 cold outlet now tracks both live inlets as `T_746 = T_c002 + ε·(T_c003 − T_c002)`, ε = (190−139)/(200−139) = 51/61 — the *design-implied* effectiveness, since the rounded datasheet ε back-solves to 190.0021 °C and breaks the anchor. `sens_c003` re-pointed onto the same live node so display and energy balance cannot decouple (bit-identical at design). TT-328009 published off it. TT-328007 re-pointed from `R328_E007_TH_OUT` (89 °C, the 328E007 hot outlet — wrong node) onto the C002 bottoms draw (stream 743, 139 °C). TT-328005 (stream 739, 143 °C) and TT-328004 (C004 top tray = OVHD stream 750, 140 °C, via a derived 3 K offset) published. See Revision Delta #14. |

| 11 | 2026-07-22 | branch `master` | Full modelling-equation audit of every equipment tag against the 11 equation categories (`EQUATION_AUDIT.md`). Units 323 + 324: vapour generation was a frozen design split fraction of the live inflow in every vaporiser, so the mass and energy balances were solved independently — the live heater duty had no authority over the boil-up, and the 324 melt strength was pinned by construction. Boil-up is now duty-limited, 323F004 runs a true isenthalpic flash (saturation constraint + enthalpy balance), the 324 melt strengths are live outputs, and all four condensing-steam chests are floored at zero duty (a shut valve had been turning them into refrigerators, dragging the melt to 22 °C). See Revision Delta #15. |
| 12 | 2026-07-22 | branch `master` | Equation audit remediation, slot 2 — 322E002 HPCC (finding F-6 / TD-007). The condensation split `HPCC_FRAC_GAS_DES` was a point calibration frozen into a constant, so the condenser was thermodynamically inert: shell temperature and synthesis pressure moved the duty and the NTU outlet temperature but not one mole of condensate. The calibration is now the *anchor* of an isothermal (T,P) Rachford-Rice flash — design K back-solved from it every tick, corrected by the carbamate equilibrium Kp = p²_NH₃·p_CO₂ (dissociation-pressure slope ΔH_carb/3, Bennett 1953), Raoult for H₂O, Henry for N₂ — solved by bisection and rate-limited through the interfacial film over `HPCC_TAU_FILL_MIN`, making the split a dynamic state `s.hpcc_phi`. `P_bub` de-pinned from the frozen design temperature onto the live `T_prod`. See Revision Delta #16. |
| 13 | 2026-07-22 | branch `master` | Equation audit remediation, slot 5 — 323E010 / 323F010 (finding F-11 / TD-011). The pre-evaporator was modelled with **one feed** when it has two: PFD stream 331, the granulation-scrubber urea-recovery return (3270 kg/h, 44.37 % urea, 40 °C), joins stream 319 ahead of 323E010 and flashes with it in 323F010 under vacuum (gas 790, solution 315 ≡ 317 after the pump). The engine had 331 entering at 323D002, downstream of the balance it closes, which is why stream 317's composition was unreachable from 319 and ≈1.4 t/h of urea had to appear from nowhere. Raised as a suspected source-data error; confirmed instead as a model topology error — the total mass balance closes to 0.019 % on the licensor's own flows, and the formaldehyde tracer (331 is its only source in the plant) closes to 1.7 %. Severity raised B → A: it was a missing term in C1 and C3, not just C2. Design duty 5048 → 7249 kW for the 40 °C feed's sensible load; unit-324 constants deliberately left byte-identical. See Revision Delta #17. |
| 14 | 2026-07-22 | branch `master` | Equation audit remediation, slot 6 — unit 328 desorption train (finding F-8 remainder / TD-009). The last lumped-mass island: 328C002 and 328C004 moved material with **frozen overhead split constants** and no composition existed anywhere in the unit. Closing it required first settling the PFD's composition-unit convention — **liquid rows are mass %, vapour rows are mole %** — without which the licensor's table appears to destroy 800 kg/h of carbon across 328C002; the tabulated `Average Molar Weight` row is the discriminator, verified across ~90 streams. Read correctly, all three columns close per component to under 2 kg/h in 34–40 t/h. The Uhde mechanical datasheet UD-AU-328-EC-0001 supplied the geometry (328C002 and 328C004 are ONE 25.5 m stacked tower; 15 and 22 executed trays; ID 1250 mm; 40 mm weir; 3125 × ⌀6 mm holes), replacing a 900 s residence-time guess with real holdup and making the tray count load-bearing through a Kremser stage correction. Two defects surfaced: the hydrolyser was fed **stream 738's urea fraction instead of stream 746's** (+7.9 %), and the trace-species ODE is stiff enough (1.4 g of NH₃ inventory against 330 kg/h throughput) that explicit Euler walked the train off its design point — `des_advance` is implicit. The same units finding retired the stream-790 "accepted variance" recorded under Delta #17. See Revision Delta #18. |
| 15 | 2026-07-23 | branch `master` | Equation audit remediation, slot 7 — 322E001 HP stripper, hydrodynamic flooding (TD-006, first half). The unit carried **no tube geometry whatsoever**; every term whose comment read "flood" was a *thermal* metaphor for the steam-dilution branch, which asks only whether the shell steam keeps up with the liquid. A falling-film stripper's real ceiling is the independent question of whether the tube can physically carry the film — a liquid-load limit. Licensor DDS UD-AU-322-DZ-0003-003 p.3 supplies 2600 tubes, 31 × 3.0 mm (ID 25.0 mm), 6000 mm effective, and is self-consistent: N·π·d_o·L = 1519.27 m² against its own tabulated 1519.00 (+0.018 %), so the tube count is confirmed rather than trusted. Three documents then agree — the bore is 0.984″ so the IFS-166 "145 kg/h per 1-inch tube" limit applies unscaled; the 6.000 m effective length is exactly what Brouwer ties to 80 % design efficiency; and the quoted 183 °C reference *is* `STRIP_FEED207_T_C`. The design point computes to **74.5 % of the limit** (108.0 of 145 kg/h per tube, onset at 134 % load), so the constraint is one-sided and **does not bind at the seed** — no anchored ratio was required, and the pin guarantee rests on a physical fact rather than float operand ordering. See Revision Delta #19. |
| 16 | 2026-07-23 | branch `master` | Equation audit remediation, slot 8 — 322E001 per-species enthalpy balance (TD-006 second half, **closing TD-006**), the retirement of its last unsourced constant, and the `eta_P` dead lever. The MP-steam duty was proportional to feed **mass**, so composition never entered: the same tonnage of pure water and of carbamate-rich reactor liquor demanded identical steam, and the unit's largest heat sink — carbamate dissociation — was invisible to the header. The previous session recorded this as *blocked* on sourcing a carbamate enthalpy; that was wrong twice over — `HPCC_DH_CARB_KJMOL` was already in the module, and Frejacques (via Brouwer, UreaKnowHow June 2009 p.12) publishes both reactions at **process** conditions: −117 kJ/mol at 110 atm / 160 °C for carbamate, +15.5 kJ/mol at 160–180 °C for urea. Those sit close to this stripper's 144 bar / 172–183 °C, so 117 is used, not the 159–160 quoted for *solid* carbamate at 25 °C. NH₃ is supercritical here (Tc = 132.4 °C) so there is no latent heat to look up at all. **Validation: the five terms summed over the design streams, with nothing fitted, give 37 831 kW against the licensor's 39 400 — 96.0 %**; only the ratio is applied, so the 4 % offset cancels and the PFD duty stays the anchor. The same balance then *retired* `STRIP_FLOOD_ETA_K = 1.50`, flagged in Delta #19 as the one number to replace: the bottom-temperature rise and the efficiency loss are the same event measured twice, so `g_flood` is now derived from ΔT_flood with **no new constant**, and the old fit proves ~10× too aggressive and double-counting against `g_T`. Finally `eta_P`, dead because every call site passed the frozen design pressure, now rides PT-329201 — gated on `_STEAM_READY` exactly as `step_steam` is, since the new feedback path would otherwise have the boot settle capture `HPCC_UA`/`HPCC_LIQ_DES_LIVE` off a different transient (+305 kg/h, 0.16 %). See Revision Delta #20. |
| 17 | 2026-07-23 | branch `master` | Equation audit remediation, slot 9 — **C10 urea-solution properties** (TD-012, partial) and the **ripple break** it shared a root cause with (new audit section R). One cp of 2.5 kJ/kg·K covered every urea solution from 44 % urea to 97.71 % melt, which is most wrong exactly where the model does its most important work, since the evaporation train's purpose *is* to change composition (14–18 % high at the Evaporator ends, 23 % low at the LP end). cp is **back-solved** — cp_water from steam tables, cp_urea fixed by requiring the mixing rule to reproduce the model's own design anchor — and yields 2.072 kJ/kg·K against a published molten-urea 2.0–2.1, an independent corroboration since nothing forced the answer to be physical. Density is **regressed from the PFD** (§0 strict source; 12 urea streams, 34–98 % urea, 40–183 °C) to ρ = 972.08 + 255.95·w − 0.4659·(T−100); both signs came *out* of the fit rather than being imposed. Both are applied as a departure from the existing anchor, so `ANCHOR + 0.0 == ANCHOR` holds to the bit. Separately, a **measured** ripple audit (perturb live state, count moving telemetry leaves) found unit 324 responding to an upstream composition step in **0 of its 66 leaves**: 323D002's strength was pinned to the constant `R324_W_IN`, so `sol_pin_strength` erased every upstream disturbance in the buffer tank — the block's own comment claimed the opposite. The attempted fix carried the live deviation and did restore the ripple (324 -> 13 of 66, first at tick 39, the 80 m³ tank lag) — but it drove D002 to 76.515 % urea against the PFD stream-317 anchor of 80.00 and was **reverted**: the pin's "rounding guard" docstring is masking a real 3.5-point gap in the 323 balance, and breaking §0 is the worse trade. Carried as TD-013. See Revision Delta #21. |

### Revision Delta — changes since the Rev-1 (2026-06-05) snapshot

The Rev-1 equation set below reflects the engine at the 2026-06-05 commit. The following verified changes have since landed and are documented in full (math + verification) in `backend/reports/FULL_AUDIT_REPORT.md`. Where the live engine now differs from Sections 1–6, that report is authoritative.

1. **Stripper strip-efficiency (§3.4.1) extended** — live `eta_T` now includes a thermal-load NTU term `g_T` and a feed-load `dT_load` ceiling, plus split-fraction modulators `eta_co2`, `eta_P`: `eta_T = clamp(eta_T_steam * g_NC * g_HC * g_T, 0, 1.15)`. See FULL_AUDIT_REPORT §B4.
2. **Scrubber carbamate-recycle dead input — FIXED** (Test-4 gap) — 323P001 weak-carbamate wash now drives a mass-conserving deviation-injection model (surplus wash leaves with overflow + scrubs paired CO₂/NH₃ at 2:1). Design-rate deviations all 0 ⇒ HMB bit-exact. See FULL_AUDIT_REPORT §B7, §C.
3. **Phase A — reactor-flood off-gas liquid carryover** coupling added (off-gas entrains overflow droplets above a level threshold). Verified isolated + in full loop.
4. **Phase B — HP ejector hydraulic-capacity (throat-choke) ceiling** added (suction capped at throat-choke limit). See FULL_AUDIT_REPORT §B3 note.
5. **TDY-329125 choke-condensation coupling** between scrubber carryover and CCW condensation quality.
6. **`f_cons` reactor overflow mass-rescale** (global mass-closure enforcement) characterised across the turndown envelope — see PART F.
7. **Reactor 322R001 dynamic liquid-inventory (Domino coupling) — HP-stripper feed FIXED** (stale 322E001 level). Root cause: line-975 φ-scaling of the reactor overflow was annihilated by the §B `f_cons` mass-rescale, so the stripper feed tear `react_overflow_kmolh` was pinned to `m_ov_tgt` independent of HV/HIC-322605 ⇒ `∂\dot m_{bot}/∂\theta = 0` ⇒ frozen 322E001 level. Fix: the reactor is now a true liquid holdup whose **hydraulic bottom take-off IS the stripper feed**. Standard accumulation ODE with HV-322605 (θ) authority over the outlet:
$$\frac{dM_{liq}}{dt} = \dot m_{in} - \dot m_{out},\qquad \dot m_{in} = \dot m_{ov,split},\qquad \dot m_{out} = \dot m_{des}\cdot\frac{\theta}{\theta_{des}}\cdot\frac{\max(L,0)}{L_{des}}$$
   The split-overflow tear is scaled to the live outlet, $f_{strip} = \dot m_{out}/\dot m_{ov,split}$ (guarded; $=1$ at design ⇒ bit-exact pin, $\dot m_{out}=\dot m_{in}=\dot m_{des}$, $dM/dt=0$). Stripper `322e001` is **untouched** — its native heat/CO₂ equations strip the introduced liquid surge to overhead at its own thermal/chemical equilibrium. Capacity anchor $\dot m_{des}$ is production-independent ⇒ a CO₂-cut feed trip ($\dot m_{in}\to0$) drains the vessel continuously toward empty (no φ_fwd FLOOR hack). Verified (matched-baseline probe): HV-322605 +20 pts → 322E001 feed `d_bot_kgh = +17315.7` (was `−0.0`, dead) + reactor LT-322504 drains 79.98→79.37 % (m_liq −1632 kg); steady feed returns to production at $L_{eq}=L_{des}\cdot(\theta_{des}/\theta)$; design baseline flat (bit-exact). Replaces the decoupled cosmetic-level path of Delta #3. `main.py` reactor level/holdup block.
8. **Reactor 322R001 mass-balance recycle-mass transport lag — LT-322504 responsiveness FIXED.** Root cause (data-backed A/B isolation): the holdup In term used the *instantaneous* production mass $\dot m_{ov,split}$, but in the reduced model the synthesis-loop recycle returns to the reactor with **zero transport delay** (1-step tear streams). Opening HV-322605 surged the stripper feed → off-gas → HP-carbamate-condenser recycle → reactor feed → production, all within one tick, so production refilled the holdup nearly as fast as the valve drained it and LT-322504 barely moved. Freezing the recycle (`m_in≡\dot m_{des}`) made the level drain **5.3×** faster (0.58→3.08 pts/5 min), isolating the recycle as the attenuator. Delta #7's ODE and HV-322605 outlet authority are correct; the defect was the **missing recycle inventory lag on the production In term**. Fix mirrors the existing §Fix-3 composition lag (same τ_rec, same fresh fraction φ_f): the production surge above design is split into a prompt fresh leg and a τ_rec-buffered recycle leg —
$$\Delta\dot m \equiv \dot m_{ov,split} - \dot m_{des},\qquad \dot m_{in,lag}^{\,n} = \dot m_{in,lag}^{\,n-1} + \frac{\Delta t}{\tau_{rec}}\!\left(\Delta\dot m - \dot m_{in,lag}^{\,n-1}\right),$$
$$\dot m_{in} = \dot m_{des} + \underbrace{\phi_f\,\Delta\dot m}_{\text{fresh, prompt}} + \underbrace{(1-\phi_f)\,\dot m_{in,lag}}_{\text{recycle, }\tau_{rec}\text{ lag}},\qquad \tau_{rec}=5\ \text{min},\ \phi_f=0.30.$$
   At design $\Delta\dot m=0 \Rightarrow \dot m_{in,lag}=0 \Rightarrow \dot m_{in}=\dot m_{des}=\dot m_{out} \Rightarrow dM/dt=0$ (bit-exact pin preserved); $\dot m_{in,lag}$ only feeds the holdup integration, so the published HMB flows/T/P are untouched. The stripper-feed tear $f_{strip}=\dot m_{out}/\dot m_{ov,split}$ keeps the **instantaneous** production denominator (the hydraulic take-off is unchanged). Verified (matched-baseline probe, HV-322605 +20 pts): LT-322504 drops 0.19 / 0.38 / 0.76 / **1.70** pts at 30 / 60 / 120 / **300** s (was **0.58** pts at 300 s → **2.9×** prompter), with $\dot m_{in,lag}$ climbing 5.4 k → 44 k kg/h over 600 s as the recycle refill physically arrives; level re-settles toward $L_{eq}=L_{des}\cdot(\theta_{des}/\theta)=60\%$; design baseline flat (bit-exact). `main.py` reactor level/holdup block + `State.react_m_in_lag`.
9. **LT-322504 re-scoped to the datasheet N7 narrow band (shadow-referenced) — instrument geometry FIXED.** Per reactor datasheet UD-AU-322-EC-0006 (322R001), nozzle **N7 = "LT 322504"** is a narrow-span head transmitter near the vessel top, **not** a full-column gauge: datasheet p6 measuring span **1500 mm**, p14 top connection **1000 mm above the overflow pipe**. The engine previously mapped LT-322504 linearly across the full $H_{col}=25.0$ m shell, so a 1.5 m surface excursion read as only $\sim 6\%$ — far too coarse for the real instrument. The liquid HOLDUP and all hydraulics (overflow head, flood, $P_{min}$) remain on the true physical head $H_{liq}=H_{col}\cdot \text{react\_level\_pct}/100$ (Scope Lock — physical consumers untouched); **only the displayed transmitter reading** is re-scoped to the 1.5 m band, which **saturates** at 0 %/100 % once the surface leaves range (real narrow-band behaviour). Span constants: `REACT_LT_SPAN_M = 1.5`, `REACT_LT_ABOVE_OVF_M = 1.0`; band anchored at NLL `REACT_LEVEL_NLL_PCT = 80.0` % at the design head.
   **Shadow-holdup reference (the key construct).** A naïve narrow band referenced to the *production datum* humps badly on startup: the HP-carbamate-condenser production/recycle sags with $\tau\!\approx\!300$ s while the reactor head relaxes far slower ($\tau\!\approx\!2160$ s), so a production-only datum over-rejects and LT spuriously climbs to **96 %** before recovering. Fix: reference the reading to a parallel **shadow holdup** $M^{\*}$ integrated with the **same** production In term but with **HV-322605 PINNED at its design position** $\theta_{des}$ (explicit Euler, prev-step shadow head):
$$\dot m_{out}^{\*} = \dot m_{des}\cdot\frac{\theta_{des}}{\theta_{des}}\cdot\frac{\max(L^{\*},0)}{L_{des}},\qquad M^{\*}_{n}=M^{\*}_{n-1}+\bigl(\dot m_{in}-\dot m_{out}^{\*}\bigr)\frac{\Delta t}{3600},\qquad M^{\*}\ge M_{min}.$$
   The shadow shares the actual holdup's *own* slow dynamics (same $\dot m_{in}$, same $L_{des}$ scaling), so the off-seed loop relaxation moves $M^{\*}$ and $M_{liq}$ **together** and cancels in the difference; an operator HV-322605 move (which touches only the actual $\dot m_{out}$, not the shadow's) opens a **sustained, properly-damped** gap that IS the take-off deviation. The displayed reading:
$$H^{\*}_{ref}=H_{col}\cdot\frac{L^{\*}}{H_{col}},\qquad \text{LT\%}=\mathrm{clamp}\!\left(\text{NLL}+\frac{H_{liq}-H^{\*}_{ref}}{\text{SPAN}}\cdot100,\ 0,\ 100\right).$$
   Seeded $M^{\*}=M_{liq}=M_{des}$ ⇒ deviation $\equiv 0$ on init ⇒ **bit-exact 80.0000 %** at the design valve. Verified (probe, DT = 0.1 s): design pin **LT = 80.0000** at every checkpoint $t=0\to30000$ s while `react_level_pct` relaxes 80→78.056 % (shadow cancels the drift exactly); HV-322605 +20 pts step → LT **73.9 %** at 30 s, **56.2 %** at 120 s, saturating **0 %** by 600 s (prompt, monotonic, realistic for a 1.5 m band). `main.py` constants block + LT-322504 DISPLAY block + `State.react_m_liq_shadow`.
   **⚠ Out-of-scope latent finding (documented, NOT fixed — Scope Lock).** The probe exposed that the static design seed is **not** the coupled-loop dynamic fixed point: with the valve untouched the whole loop relaxes asymptotically over $\sim\!5$ h — **HPCC −4.8 %** (dominant driver), reactor head **−0.49 m / −1.9 %** (80→78.06 %), stripper $\approx\!0$. Bounded/asymptotic (not a leak/mass error); the shadow reference makes LT-322504 immune to it, but the underlying **HPCC seed-vs-fixed-point mismatch** is a separate pre-existing defect. Flagged for a dedicated investigation; deliberately excluded here to keep this change surgical.
10. **322F001 HP-ejector spindle characteristic `phi_sp` direction INVERTED (positive → negative equal-%) — HV-322602 ↔ LT-329501 coupling FIXED.** Root cause: `phi_sp` used a POSITIVE equal-% exponent that implicitly assumed the HV-322602 needle throttles the motive *throughput* (more open ⇒ more motive ⇒ more suction). That boundary condition is wrong for this loop. The motive HP NH₃ is delivered by the **321P002 A/B positive-displacement (triplex) pumps**, so the motive **mass flow is constant** (set by pump speed, not valve opening). HV-322602 is the **converging parabolic NH₃-nozzle needle**: closing it shrinks the throat area $A$, and at constant $\dot m$ the jet velocity and momentum flux rise inversely with $A$ —
$$v=\frac{\dot m}{\rho A},\qquad \text{momentum flux}=\dot m\,v=\frac{\dot m^{2}}{\rho A}\ \propto\ \frac{1}{A}.$$
   Higher motive momentum ⇒ higher entrainment capacity ⇒ the ejector drains the 322E003 sump ⇒ **LT-329501 FALLS on closing** (and rises on opening). The fix flips the equal-% exponent sign about the design opening, retaining the DDS free-area rangeability magnitude $R=2.1517$:
$$\phi_{sp}(\theta)=R^{\,(\theta_{des}-\theta)/100},\qquad \theta_{des}=\text{EJ\_OPEN\_DES}=74\ \%,\qquad \phi_{sp}(74)=R^{0}=1\ \text{(design bit-exact)}.$$
   With $\theta<74$ (closing) $\Rightarrow \phi_{sp}>1$; $\theta>74$ (opening) $\Rightarrow \phi_{sp}<1$. The downstream chain is unchanged — capacity $= \text{EJ\_SUC\_TOT\_DES}\cdot\phi_m\cdot\phi_{sp}\cdot f_{stall}$, $\dot m_{suc}=\text{capacity}\cdot\text{frac}_{eff}$, sump ODE $dM/dt=\dot m_{cond,in}-\dot m_{entrain}$ with steady fixed point $L_{eq}=\text{NLL}\cdot(\text{overflow}/\text{capacity})$ — so the self-regulating attractor simply re-stabilises at the mirrored level. The `f_stall` deep-stall factor keys on $\phi_m$ (motive mass fraction = genuine motive fault), independent of the spindle sign, so it is unaffected. Verified: `test_ejector_spindle.py` 5/5 (design anchor `suction_kgh == EJ_SUC_TOT_DES` bit-exact at 74 %; negative-characteristic `s_close > s_des > s_open`; integration `hic_set 50` ⇒ LT falls, `hic_set 95` ⇒ LT rises, `74` holds $|\Delta|<0.5$); `test_scrubber.py` 13/13 (design anchor + closure preserved). `main.py` constants block (lines 126-133) + `ejector_322f001` `phi_sp` (line 351). Restores the inverse direction a prior edit had wrongly positivised under an implicit constant-pressure assumption.
11. **322F001 → 322E002 → 322R001 forward-carbamate domino — HV-322602 ↔ LT-322504 coupling FIXED (washout-injected transient swell).** Root cause: the reactor holdup ODE (Deltas #7/#8) was **stone-dead to HV-322602**. The user-reported chain — closing HV-322602 drives more entrainment, so more condensed carbamate is pumped from the 322E003 sump through the 322F001 ejector into 322E002 (HP carbamate condenser) and on to 322R001, **raising LT-322504** — had no path into `react_m_liq`. Two structural facts blocked a naïve fix: (i) the published reactor inlet $\dot m_{in}$ carries no ejector-forward term, and (ii) the LT-322504 *display* is shadow-referenced (Delta #9) with the shadow integrated on the **same** $\dot m_{in}$, so **any term added to $\dot m_{in}$ cancels in the displayed difference**. The reading can therefore only move if a term is injected into the **actual** holdup integration alone. A sustained inflow is also non-physical: 322R001 is level-servoed (Delta #7, $\dot m_{out}\propto L$), so at steady valve the sump can supply only its own inflow — a constant source would invent mass and flood. The faithful coupling is a **conservative transient swell** during the sump→ejector→HPCC→reactor redistribution, decaying to zero at any steady opening.
   **Driver — spindle-attributable draw.** Key the forward term on the part of the suction *attributable to the spindle move*, using the same negative equal-% characteristic as Delta #10:
$$\phi_{sp}(\theta)=R^{\,(\theta_{des}-\theta)/100},\quad R=\text{EJ\_SPINDLE\_R}=2.1517,\ \theta_{des}=74,\qquad \dot m_{drv}(\theta)=\dot m_{suc}\Bigl(1-\tfrac{1}{\phi_{sp}(\theta)}\Bigr).$$
   At the design valve $\theta=74\Rightarrow\phi_{sp}=1\Rightarrow\dot m_{drv}\equiv0$ **for any sump state** (it does not key on the raw, off-NLL-nonzero suction), so the engineered LT-322504 startup/relaxation pin (Delta #9) is preserved bit-exact. $\theta<74$ (closing) $\Rightarrow\dot m_{drv}>0$; $\theta>74$ (opening) $\Rightarrow\dot m_{drv}<0$.
   **Washout (high-pass) to enforce mass conservation.** $\dot m_{drv}$ alone is constant at fixed $\theta$ → a sustained fictitious source (verified failure mode: $M_{liq}$ climbed $135\text{k}\!\to\!140\text{k}$ unbounded, LT saturated 100 %). Low-pass it into a state and inject only the **high-pass residue**, which is non-zero only while $\theta$ is *changing* and dies to 0 at any steady opening:
$$w^{\,n}=w^{\,n-1}+\frac{\Delta t}{\tau_{fwd}\cdot 60}\bigl(\dot m_{drv}-w^{\,n-1}\bigr),\qquad \dot m_{fwd}=G_{fwd}\,\bigl(\dot m_{drv}-w\bigr),\qquad \tau_{fwd}=8\ \text{min},\ G_{fwd}=1.0,$$
$$M_{liq}^{\,n}=M_{liq}^{\,n-1}+\bigl(\dot m_{in}-\dot m_{out}+\dot m_{fwd}\bigr)\frac{\Delta t}{3600},\qquad M^{\*}_{n}=M^{\*}_{n-1}+\bigl(\dot m_{in}-\dot m_{out}^{\*}\bigr)\frac{\Delta t}{3600}\ \ (\text{shadow: }\textbf{no }\dot m_{fwd}).$$
   $w$ (state `react_fwd_wash`) is seeded 0; at $\theta=74$ the driver is identically 0 so $w\equiv0$ and $\dot m_{fwd}\equiv0$ ⇒ design pin bit-exact. Because $\dot m_{fwd}$ enters **only** the actual holdup (not $\dot m_{in}$, not the shadow $M^{\*}$), the shadow-referenced display gap opens on a valve move and the swell is visible; mass-conservation holds because $\int\dot m_{fwd}\,dt\to0$ as the high-pass relaxes. Signs: $\dot m_{fwd}>0$ on closing (LT rises), $<0$ on opening (LT falls). Verified (matched-baseline transient probe, DT = 0.1 s, close-50 vs held-74): $t=0$ LT-322504 $=\textbf{80.0000}$ (pin bit-exact); swell peaks $\approx\!+8.3\%$ at $t\approx900$ s, relaxes to $+3.9\%$ by $t=3000$ s; $M_{liq}$ $135317\!\to\!136245\!\to\!134771$ kg (rises then returns — conservative, no runaway). `test_ejector_spindle.py` 8/8 (3 new domino tests `test_lt322504_rises_on_close` / `_falls_on_open` / `_design_holds` FAIL→PASS); `test_scrubber.py` 13/13. `main.py` constants block (`REACT_FWD_GAIN`, `REACT_FWD_TAU_MIN`) + reactor holdup block + `State.react_fwd_wash`.
12. **322E003 carbamate-condensation spindle-intensity coupling — HV-322602 ↔ TT-322002 ↔ 322E003 thermodynamics FIXED.** Root cause: TT-322002 (the 322E003 bottom enriched-carbamate overflow temperature) was coupled to HV-322602 through **one path only** — the existing flood-choke factor $\chi_{choke}$, which keys on sump level *above* NLL. But CLOSING HV-322602 (the dominant operator action) raises ejector entrainment and **drains** the sump *below* NLL, so $\max(L-\text{NLL},0)=0\Rightarrow\chi_{choke}\equiv1$ and the carbamate-condensation duty $q_{ccw}$ was left completely unscaled. The bottom-overflow energy balance $t_{overflow,cond}=\min(t_{ccw,in}+q_{ccw}/UA_{eff},\,T_{proc})$ therefore never saw the spindle move ⇒ **TT-322002 was dead on closing** (the user-reported defect: "change in HV-322602 not coupled with TT-322002, therefore not coupled with 322E003 thermodynamics"). The motive jet sets how vigorously the off-gas is drawn through the bottom condensation zone, so the condensation *duty* itself must scale with spindle intensity, not merely the flood surface.
   **Spindle-intensity duty factor.** Reuse the **same** negative equal-% spindle driver $(1-1/\phi_{sp})$ as the Delta #11 forward-carbamate domino, applied multiplicatively to the condensation duty:
$$\phi_{sp}(\theta)=R^{\,(\theta_{des}-\theta)/100},\quad R=\text{EJ\_SPINDLE\_R}=2.1517,\ \theta_{des}=74,\qquad \chi_{sp}(\theta)=1+G_{cond}\Bigl(1-\tfrac{1}{\phi_{sp}(\theta)}\Bigr),\ \ G_{cond}=\text{SCRUB\_COND\_SPINDLE\_GAIN}=0.25,$$
$$q_{ccw}'=q_{ccw}\cdot\max\!\bigl(\chi_{sp},\,\text{SCRUB\_COND\_CHOKE\_MIN}\bigr),\qquad \text{SCRUB\_COND\_CHOKE\_MIN}=0.30,$$
   inserted **before** the pre-existing one-sided flood-choke (which is left untouched — Scope Lock), so the two effects compose on opening. The scaled duty then propagates through the **full 322E003 thermo unchanged**: $t_{overflow,cond}=\min(t_{ccw,in}+q_{ccw}'/UA_{eff},\,T_{proc})\!\to\!$ TT-322002, and $t_{ccw,out},\,\Delta T_{ccw}\!\to\!$ TT-329125 / TDY-329125. Signs are anchored by the accepted flood-choke symmetry: closing $\Rightarrow\phi_{sp}>1\Rightarrow\chi_{sp}>1\Rightarrow$ more condensation $\Rightarrow$ TT-322002 **rises**; opening $\Rightarrow\phi_{sp}<1\Rightarrow\chi_{sp}<1\Rightarrow$ TT-322002 **falls** (and the flood-choke adds further cooling).
   **Design pin by construction.** At $\theta=74\Rightarrow\phi_{sp}=R^{0}=1\Rightarrow\chi_{sp}=1+G_{cond}(1-1)=1$ **exactly**, so $q_{ccw}'\equiv q_{ccw}$ and TT-322002 holds 178.8 °C / TDY-329125 holds 15.0 K bit-exact. The pin is **$\phi_{sp}$-keyed, not level-keyed**: the self-regulating sump settles at $L_{eq}\approx47.7\%$ (below the 50 % NLL) at the design valve, so any NLL-anchored term would break the pin — the $\phi_{sp}$ form is exact regardless of sump state. $\chi_{sp}(50)=1.0420$, $\chi_{sp}(95)=0.9564$. The unit-test / audit direct calls to `scrub_322e003` omit `spindle_phi` (default $1.0\Rightarrow\chi_{sp}=1$) so all design contracts are preserved bit-exact. Verified (matched-baseline, settled): TT-322002 $\theta{=}50\Rightarrow 178.8\!\to\!\textbf{183.0}$ ($+4.20$), $\theta{=}95\Rightarrow 178.8\!\to\!\textbf{167.0}$ ($-11.8$, spindle-duty $\oplus$ flood-choke), $\theta{=}74\Rightarrow |\Delta|=0.30<0.5$ (display settling residual; **equation** pin bit-exact, audit $|T_{overflow}-178.8|<10^{-6}$). `test_ejector_spindle.py` 11/11 (3 new `test_tt322002_rises_on_close` / `_falls_on_open` / `_design_holds` FAIL→PASS); `test_scrubber.py` 13/13; `tests/audit_e003_scrubber.py` ALL PASS. `main.py` constants block (`SCRUB_COND_SPINDLE_GAIN`) + `scrub_322e003` (`spindle_phi` param + $q_{ccw}$ scaling) + call site (`spindle_phi=_phi_sp_theta`).
13. **323E003 tempered-water circuit — TIC-323013 re-anchored to the wrong-node PV, TV-323013A/B split range built, linear duty fudge retired, TT-323015 published.** Root cause (four defects on one loop, all in the 323E003 LPCC block): (i) **wrong PV node** — `_ctrl_ipd(s.TIC_323013, Te003, dt)` fed the controller the 323E003 **shell** temperature (74 °C), but TIC-323013 is the tempered-water **supply** controller, whose PFD anchor is **stream 1102 = 55 °C**; (ii) **the SP span forbade the design SP** — `sp_lo = 60.0` made the mandated 55 °C physically unreachable through the faceplate; (iii) **no split range** — `overlays.js` bound TV-323013A *and* TV-323013B to the same `LPCC_3232.E003.TIC_323013.op`, so the two valves read identically and the mandated opposite action did not exist at all; (iv) **a linear duty shortcut** — `Q = UA·(T_shell − T_tw_mean_des)·(op/50)`, an `op`-proportional fudge with no physical driving force, which §1 (Rigorous Kinetics, "no linear or static shortcuts") forbids.
   **Split-range valve characteristic.** TV-323013A admits cold make-up, TV-323013B bypasses hot return; both strokes come off the single controller output, exact opposites by construction:
$$\theta_A=\text{op},\qquad \theta_B=100-\text{op}\quad\Longrightarrow\quad \theta_A+\theta_B\equiv100\ \text{(exact, every operating point)}.$$
   The house normalized-stroke linear-interpolation form then maps stroke to the achievable supply band, clamped and first-order lagged into the PV:
$$T_{tw}^{ss}(\theta_A)=\mathrm{clamp}\!\left(T_{ret}^{des}-\bigl(T_{ret}^{des}-T_{sup}^{des}\bigr)\frac{\theta_A}{\theta_{A,des}},\ 20,\ T_{ret}^{des}\right),\qquad T_{sup}^{des}=55,\ T_{ret}^{des}=65,\ \theta_{A,des}=50,$$
$$T_{sup}^{\,n}=T_{sup}^{\,n-1}+\frac{\Delta t}{\tau_{tw}+\Delta t}\bigl(T_{tw}^{ss}-T_{sup}^{\,n-1}\bigr),\qquad \tau_{tw}=\text{R3232\_TW\_TAU\_S}=25\ \text{s}\ \ (\texttt{\_lag1}\text{, implicit Euler, lazy-init}\Rightarrow\text{no boot transient}).$$
   The band is **not** fitted: at $\theta_A=100$ the form gives $T_{tw}^{ss}=65-10\cdot2=\textbf{45}$ °C, which reproduces exactly the cold make-up temperature back-solved independently from the mixing law $55=\tfrac12 T_{cold}+\tfrac12\cdot65 \Rightarrow T_{cold}=45$ °C — two derivations, one number.
   **Physical duty (replacing the fudge).** Duty now rides the true driving force between the shell and the live tempered-water mean, with the return read from the prior-step state to break the algebraic loop (same idiom as `recyc_prev` / `m718B_prev`):
$$Q_{E003}=UA\cdot\Bigl(T_{shell}-\tfrac12\bigl(T_{sup}+T_{ret}^{\,n-1}\bigr)\Bigr),\qquad UA=\text{R3232\_E003\_UA\_KW}=\frac{14000}{74-60}=1000\ \text{kW/K},$$
$$T_{ret}=T_{sup}+\bigl(T_{ret}^{des}-T_{sup}^{des}\bigr)\frac{Q_{E003}}{Q_{des}},\qquad Q_{des}=\text{R3232\_E003\_Q\_DES\_KW}=14000\ \text{kW}\quad\rightarrow\ \text{TT-323015 (stream 1103)}.$$
   `R3232_TW_T = 60.0` is deliberately **retained**: it is the design *mean* $\tfrac12(55+65)$ that the $UA$ back-solve keys off, and must never be replaced by a live value.
   **Design pin by construction (bit-exact, IEEE-level).** At $\theta_A=\theta_{A,des}=50$ the stroke ratio is $1$, so $T_{tw}^{ss}=65-10\cdot1=55=\text{SP}$ **exactly** ⇒ PV stationary ⇒ $du=0$. The duty chain is exact in binary throughout: $55.0+65.0=120.0 \Rightarrow \tfrac12(120.0)=60.0 \Rightarrow 74.0-60.0=14.0 \Rightarrow 1000.0\cdot14.0=\textbf{14000.0}$ — **bit-identical** to the retired $1000.0\cdot(74.0-60.0)\cdot(50.0/50.0)$. The return closes on itself: $T_{ret}=55.0+10.0\cdot(14000.0/14000.0)=\textbf{65.0}$ exactly, so tick $n+1$ reads the same mean and the fixed point is preserved. Dropping $(op/50)$ is therefore simultaneously **IEEE-exact and** a §1 compliance fix.
   Verified — **pin gate `leaves: 25  keys: 15  diffs: 0`** (mandated count; no `R3232_*` key is pinned, but the gate is re-run because `main.py` is in `_PIN_SRC_FILES`). Design probe (6000 ticks @ 0.1 s): `TIC_323013 = {pv: 55.0, sp: 55.0, op: 50.0, mode: CAS}`, `TV_323013A = 50.0`, `TV_323013B = 50.0`, `TT_323015 = 65.0` (stream 1103), `TT_323003 = 74.0` **unchanged** (shell untouched — Scope Lock). Split-range acceptance (the literal requirement): SP 55→**50** ⇒ TV-A 50.0→**68.8** (opens) / TV-B 50.0→**31.2** (closes); SP→**60** ⇒ TV-A→**35.8** (closes) / TV-B→**64.2** (opens); `sum ≡ 100.0` at every point ⇒ "opposite" is exact, not approximate. Offset-free integral action confirmed (SP 50 step): err $+4.40\to+3.80\to+2.80\to+1.50\to+0.40\to\textbf{0.00}$ at $t=100/200/400/800/1600/3000$ s with TV-A → **74.8**, matching the valve char's independent prediction $T_{ss}=65-10\cdot(75/50)=50\Rightarrow \theta_{A,\infty}=75.0$; closed-loop integral time $T_i/(K_c|K_p|)=250/(3\cdot0.2)=417$ s ⇒ $4\tau\approx1670$ s, which is the observed trace.
   **⚠ Documented open gap (NOT fixed — Scope Lock).** PFD 1102/1103 give a circulation of 1094 t/h over a 10 K rise ⇒ $Q=1094000\cdot4.18\cdot10/3600=\textbf{12{,}703}$ kW, but the engine's LPCC-datasheet anchor is $Q_{des}=\textbf{14{,}000}$ kW (reconciling would need 1206 t/h, 10 % off the PFD). Changing it cascades through `R3232_E003_LAMC` → the 323E003 energy balance → `m_744`/`m_756` → the **pinned** A328 back-solves, so it is deliberately excluded here. Both anchors are internally consistent; only their cross-source ratio is not.
   `main.py` constants block (`R3232_TW_SUP_T`, `R3232_TW_RET_T`, `R3232_TV13_DES_PCT`, `R3232_TW_TAU_S`) + `State.TIC_323013` init (PV/SP → 55, `sp_lo` 60→45, `sp_hi` 90→65) + the LPCC 323E003 runtime block (`T_tw_ss` / `T_tw_sup` / `T_tw_ret` / physical `Q_e003`) + `LPCC_3232.E003` telemetry (`TV_323013A`, `TV_323013B`, `TT_323015`) + `frontend/overlays.js` screen-323-2 (`tv013a`/`tv013b` split to distinct binds; `tt015w` → bound `tt015`).

14. **328 desorption train — stream 746 (TT-328009) freed from a static constant, TT-328007 re-pointed off the wrong node, TT-328005/TT-328004 published.** Four missing or mis-bound 328-1 temperature indicators; one of them turned out to be a §1 physics defect rather than a display gap. Root causes: (i) **stream 746 was a static constant** — the C003 runtime hard-coded `m_746 = m_743  # via 328E021 (190 °C)` and the energy balance read `sens_c003 = m_746/3600·Cp·(R328_C003_T746 − T_c003)` off the frozen `R328_C003_T746 = 190.0`. The 328E021 interchanger *does* carry an effectiveness model in the constants block (`R328_E021_EPS`, `R328_E021_LOSS`), but a consumer grep proved both are **dead constants — zero consumers**: a design-basis reconciliation record that was never wired live. A TT-328009 bound to that node would have read a frozen 190 forever regardless of plant state, violating §1 ("no linear or static shortcuts") and the Domino Effect; (ii) **wrong-node bind** (same class as Δ#13(i)) — `TT_328007` published `R328_E007_TH_OUT = 89.0`, the 328E007 *hot* outlet to the stream-740 boundary, but TT-328007 is the 328C002 bottoms draw to the 328P006 suction ⇒ **PFD stream 743 = 139 °C**; (iii)/(iv) TT-328005 (stream 739, 143 °C) and TT-328004 (328C004 top tray) had no telemetry key at all.
   **Why the datasheet effectiveness cannot be used.** The stored NTU effectiveness is the *rounded* datasheet projection, and it does not close on the design point:
$$\varepsilon_{DS}=\frac{\dot Q}{C_{min}\Delta T_{max}}=\frac{1913.6}{37.52\cdot 61.0}=0.836100527805935\ \Longrightarrow\ 139+\varepsilon_{DS}\cdot 61=190.0021\ \text{°C}\ \neq\ 190.0,$$
   which breaks the Design Anchor — precisely why the original author froze the constant instead. The **design-implied** effectiveness is exact *and* reconstructs the datasheet's own provenance:
$$\varepsilon=\frac{T_{746}^{des}-T_{C002}^{des}}{T_{C003}^{des}-T_{C002}^{des}}=\frac{190-139}{200-139}=\frac{51}{61}=0.8360655737704918\quad(\texttt{R328\_E021\_EPS\_T}).$$
   Cross-checked against the engine's own $C_p=\text{R328\_CP}=4.0$: $\dot Q_{cold}=\tfrac{33769}{3600}\cdot4.0\cdot51=\textbf{1913.577}$ kW ≈ its **1913.6**; $\dot Q_{hot}=\tfrac{34062}{3600}\cdot4.0\cdot52=1968.027$ kW; closure $1968.027-1913.577=\textbf{54.45}$ kW ≈ its `R328_E021_LOSS` = **54.4**. The datasheet pair *is* the rounded projection of this exact design point ⇒ **no constant fabricated** (Sourcing Law satisfied by derivation from the OEM design temperatures, not by fitting).
   **Live cold outlet (stream 746 → TT-328009).** Both live E021 inlets now drive the node:
$$T_{746}=T_{C002}+\varepsilon\bigl(T_{C003}-T_{C002}\bigr),\qquad \frac{\partial T_{746}}{\partial T_{C003}}=\varepsilon=0.8361,\quad \frac{\partial T_{746}}{\partial T_{C002}}=1-\varepsilon=0.1639.$$
   **No clamp is needed** — $\varepsilon\in(0,1)$ makes $T_{746}$ a **convex combination** of the two inlets, so it can never cross either, in *either* flow direction.
   **Why the energy balance had to move with it** (conservation, not preference): $T_{746}$ is the **same physical node** as the display. Publishing a live TT-328009 while `sens_c003` kept reading the constant would **decouple** display from physics — forbidden by §1 ("mass or energy must never be created, destroyed, or decoupled"). Substituting the live form into the C003 balance also supplies correct negative feedback:
$$\dot Q_{sens,c003}=\frac{\dot m_{746}}{3600}C_p\bigl(T_{746}-T_{C003}\bigr)=\frac{\dot m_{746}}{3600}C_p(1-\varepsilon)\bigl(T_{C002}-T_{C003}\bigr)\ \xrightarrow{\ des\ }\ 0.16393\cdot(139-200)=\textbf{−10.0 K},$$
   **bit-identical** to the retired constant form ($\texttt{repr}$-equal at $-375.2111111111111$ kW) ⇒ the C003 fixed point is untouched and the change is a strict improvement at zero anchor cost.
   **328C004 top tray (TT-328004).** House derived-offset idiom (the `R328_C003_DT_DES` precedent, line 564) — anchored on the PFD's **stream 750 = 140 °C**, the C004 overhead, which *is* the top-tray vapour: `R328_C004_DT_DES = R328_C004_T − R328_C002_T750 = 143 − 140 = 3` K, so `TT_328004 = T_{C004} − 3` **tracks the live bottoms** rather than standing as a second constant.
   Verified — **pin gate `leaves: 25  keys: 15  diffs: 0`** (no `R328_*` key is pinned, but `main.py` ∈ `_PIN_SRC_FILES` ⇒ re-gated). Design probe (6000 ticks @ 0.1 s): `TT_328007 = 139.0`, `TT_328009 = 190.0`, `TT_328005 = 143.0`, `TT_328004 = 140.0`, all four on their PFD anchors; `TT_328C003 = 200.0` **unchanged** (the live `sens_c003` does not move the C003 fixed point), `TT_328012 = 190.0`, `bot747 = 34.06` t/h (design 34,062), `bot743 = 33.77` t/h (design 33,769) ⇒ the mass states are undisturbed. Dynamic acceptance (**the actual point of the item** — the old code could not have moved at all): $T_{C003}$ +10 K ⇒ $T_{746}$ **+8.4** vs the closed form $\varepsilon\cdot10=8.361$; $T_{C002}$ +10 K ⇒ $T_{746}$ **+1.6** vs $(1-\varepsilon)\cdot10=1.639$ — residual is the 1-dp telemetry rounding, not model error. Convexity sweep $T_{C003}\in\{100,139,170,200,260\}$ ⇒ $T_{746}\in\{106.4,\,139.0,\,164.9,\,190.0,\,240.2\}$, every point inside $[\min,\max]$ of the two inlets **including the reversed-ΔT case** ⇒ clamp-free by construction, as claimed.
   **⚠ Documented open gaps (NOT fixed — Scope Lock).** (a) ~~The E021 **hot** side is still static~~ — **CLOSED** (re-verified by the 2026-07-22 equation audit, Δ#15). Stream 749 is now a live energy-balance closure, `T749_raw = T_{C003} − (ṁ_{746}(T_{746}−T_{C002}) + \texttt{R328\_E021\_LOSS\_DT})/ṁ_{749}`, bounded by the two live inlet temperatures, so 328E021 can neither create nor destroy energy off-design. `R328_C004_T749 = 148.0` survives only as the design datum feeding `R328_E021_LOSS_DT`. (b) `TT_328012`/`TIC_328012` are **deliberately** left on the constant `R328_C003_T746`: the C003 **3rd tray** is a *different physical node* from the 746 feed and the model conflates the two (its own comment reads "3rd-tray / 746 absolute"), so making the tray track E021's effectiveness would be *wrong* physics dressed as a fix. TIC-328012's `_ctrl_ipd` return is discarded (display-only) ⇒ pin-safe either way. (c) `R328_E007_TH_OUT = 89.0` is **orphaned** by (ii) but deliberately **retained** as the stream-740 boundary design datum — the `R3232_TW_T` precedent (deleting such a datum is a rejected approach). (d) `tt8011w`/`tt8012w` both bind `DESORB_328.C003.TT_328012` — a duplicate-bind of the Δ#13(iii) class, noted and not yet addressed.
   `main.py` constants (`R328_C004_DT_DES`; `R328_E021_EPS_T` + its provenance comment) + the 328C003 runtime (live `T_746`, re-pointed `sens_c003`) + `DESORB_328` telemetry (`TT_328007` re-pointed to `s.a328_c002_T`; new `TT_328009`, `TT_328005`, `TT_328004`) + `frontend/overlays.js` screen-328-1 (`tt8009w`/`tt8005w`/`tt8004w` → bound `tt8009`/`tt8005`/`tt8004`; `tt8007w` → `tt8007`, its stale `// 328E007 process outlet 89C` comment corrected to the 743 draw).

15. **Units 323 + 324 — energy ↔ mass re-coupling (equation audit F-1..F-5, F-10).** Full audit
    in `EQUATION_AUDIT.md`. Every vapour rate outside the HP loop was a **frozen design split
    fraction of the live inflow**, so the total-mass balance and the energy balance were solved
    *independently*: the live heater duty entered only the temperature ODE and had no authority
    over the boil-up. Shutting PV-329202 gave $Q_{E002}\to0$ while 323C003 still produced the full
    design overhead, and the whole latent deficit was dumped into $dT/dt$. In Unit 324 the melt
    strength was pinned outright by `p_m = ṁ_{urea,in}/w_{EV}`, so no operator action could dilute
    the product — while the `conc_infer_324` soft sensors *did* move off design, showing the HMI a
    strength the mass balance refused to produce.

    **(i) Duty-limited vaporisation.** Each vaporiser now takes the smaller of the composition
    demand and what its live duty can actually boil:
    $$\dot m_{vap} = \min\!\Big(\phi\,\dot m_{in},\; \dot m_{vap,des}\cdot\frac{q_{avail}}{Q_{des}}\Big),
      \qquad q_{avail} = \dot m_{in} c_p (T_{in}-T) + Q_{live}$$
    applied to 323C003/323E002 ($\phi_{305}$), 323F010/323E010 ($\phi_{evap}$), 324E001 and 324E003.
    Each $Q_{des}$ constant is written in the **same float operand order** as its runtime
    $q_{avail}$, so the ratio is exactly $1.0$ at the seed and both `min()` branches evaluate
    identically ⇒ design bit-exact.

    **(ii) True isenthalpic flash at 323F004.** $\dot m_{701}=\phi_{701}\dot m_{314}$ was blind to
    feed temperature. Replaced by the pair of statements a flash actually obeys — a **saturation
    constraint** (the liquid sits at its bubble point; the urea boiling-point elevation is held at
    its design value, the same frozen-activity assumption `conc_infer_324` makes)
    $$T_{flash} = 106 + \big[T_{sat}(P_{drum}) - T_{sat}(1.13)\big]$$
    and the **enthalpy balance**
    $$\dot m_{701}\lambda_{701} = \dot m_{314}c_p(T_{in}-T) - \frac{M c_p (T_{sat}-T)}{\tau}.$$
    Because $\lambda_{701}$ was itself back-solved at the design point, substituting this into the
    existing energy ODE collapses it to exactly $dT/dt = (T_{sat}-T)/\tau$ — energy is conserved and
    the drum now walks to its bubble point instead of standing frozen at 106 °C.

    **(iii) Live melt strength (324).** $w_1, w_2$ are now *outputs*: $w = \dot m_{urea,in}/\dot m_{melt}$,
    published to `urea_pct`, `PY-324201` and `AY-324701`; the Stage-2 feed enthalpy uses the live
    Stage-1 outlet temperature; the recycle carries its live strength through `s.tlag["R324_recyc_w"]`.
    `conc_infer_324` gained a band clamp on the reference mole fraction — `w_des` is now a live
    argument that legally reaches 0 on a cold start (it previously divided by zero there).

    **(iv) F-10 — a condensing chest cannot refrigerate.** $Q = UA\,(T_{sat}(p_{chest}) - T)$ was
    unbounded below; with $p_{chest}$ clamped to 0.02 bar a ($T_{sat}\approx17.5$ °C) a shut steam
    valve turned every heater into a cooler — probe-measured **22 °C** melt in Evap-I and **13.6 °C**
    in 323C003. Floored at zero on all four chests (323E002, 323E010, 324E001, 324E003); strongly
    positive at design ⇒ identity ⇒ bit-exact.

    Verified — pin gate `leaves: 25  keys: 15  diffs: 0`; suite **115 passed** (5 new tests in
    `backend/test_equation_audit_323_324.py`). Design probe (480 s): 94.3 % / 97.7 % / 106.0 °C /
    24.56 / 4.43 / 8.74 t/h, **zero drift**. Dynamic acceptance — Evap-I steam cut: evaporation → 0,
    product **94.3 % → 80.0 %**, melt coasts 130 → 100 °C toward its 99 °C feed; 323E002 steam cut:
    overhead 305 → 0, column 121 → 105 °C, and the downstream flash correctly makes **less** vapour
    (4.43 → 3.10 t/h) on its colder feed. All three were impossible before.

16. **322E002 HPCC — live (T,P) phase split (equation audit F-6 / TD-007).** $\phi_i$ was the
    calibrated vector `HPCC_FRAC_GAS_DES`, measured at 170 °C / 144.2 bar a and then **frozen**,
    which made the condenser thermodynamically inert: the duty, the adiabatic exotherm spike and the
    ε-NTU quench all tracked the live shell temperature, but not one mole of condensate moved. The
    calibration is not discarded — it becomes the *anchor* of a real flash.

    **(i) Design K back-solved from the calibration, every tick, against the live feed.** Over the
    distributing set $D=\{k: 0<\phi_{des,k}<1\}=\{CO_2, NH_3, H_2O, N_2\}$,
    $$\psi_{des}=\sum_{k\in D} z_k\phi_{des,k},\qquad
      K_{des,k}=\frac{\phi_{des,k}(1-\psi_{des})}{\psi_{des}(1-\phi_{des,k})}$$
    so the melt's measured activity coefficients stay baked into $K$; only the *deviation* from the
    calibration point is model-driven.

    **(ii) Correction to live $(T,P)$.** NH₃/CO₂ uptake here is not physical condensation but the
    carbamate equilibrium $\mathrm{NH_2COONH_4(l)}\rightleftharpoons 2\,\mathrm{NH_3(g)}+\mathrm{CO_2(g)}$,
    $K_p=p_{NH_3}^2 p_{CO_2}$, $\Delta H_{dis}\approx160$ kJ/mol — already in the code as
    `HPCC_DH_CARB_KJMOL`. Because $K_p$ is a **third-order** product, the measured temperature
    coefficient of the dissociation *pressure* is one third of the reaction enthalpy (≈ 12.8 kcal/mol
    = 53.3 kJ/mol; Bennett 1953, Ramachandran 1998). With $y_{NH_3}\approx 2y_{CO_2}$,
    $y_i\propto K_p(T)^{1/3}/P$, giving
    $$K_k(T,P)=K_{des,k}\exp\!\Big[\tfrac{\Delta H_k}{R}\Big(\tfrac{1}{T_{des}}-\tfrac{1}{T}\Big)\Big]\frac{P_{des}}{P}$$
    with $\Delta H=\Delta H_{carb}/3$ for CO₂ and NH₃, $\Delta H = 36\,900$ J/mol (water latent at
    170 °C) for H₂O by Raoult, and $\Delta H = 0$ for N₂ (permanent gas, Henry). Species with
    $\phi_{des}$ exactly 1 (O₂/CH₄/H₂) or exactly 0 (Urea/Biuret) are structurally non-distributing
    and sit outside the flash.

    **(iii) Rachford-Rice by bisection, not Newton.** $g(\psi)=\sum_k z_k(K_k-1)/[1+\psi(K_k-1)]$ is
    strictly decreasing on $[0,1]$, so a fixed 60-sweep bracket is exact to $2^{-60}$ at bounded cost
    and **cannot** fail to converge. Same argument that keeps the flowsheet Sequential-Modular: an
    OTS tick must never miss its deadline.

    **(iv) Interfacial rate limit — the missing equation.** The raw equilibrium target is far too
    stiff for this vessel: the distributing $K$'s are tightly clustered, so a common factor moves the
    whole mixture together and $\phi_{CO_2}$ swings 0.0009 → 1.0 across 150 → 190 °C. That is a true
    property of the flash but not of a falling-film condenser — `References/HPCC description.md`
    §5.2–5.3 is explicit that 322E002 is **interfacial mass-transfer limited**. $\phi$ is therefore
    relaxed toward the target over the condenser holdup constant `HPCC_TAU_FILL_MIN` (6 min),
    $$\phi_k \leftarrow \phi_k + \tfrac{\Delta t}{\tau_{film}}\big(\phi^{eq}_k-\phi_k\big),$$
    making the split a genuine **dynamic state** `s.hpcc_phi`. The condenser previously had no
    composition dynamics at all.

    **(v) Anchoring — three independent guarantees.** The flash short-circuits to the calibration
    when the $T$ and $P$ ratios are exactly 1 (module-load and boot-pin passes never enter the
    solver); $\Delta t = 0$ on those passes zeroes the relaxation coefficient; and the result is
    blended through the Option-1 `_disturbance_gate` exactly as $T_{prod}$ is, so gate $=0\Rightarrow
    \phi\equiv$ `HPCC_FRAC_GAS_DES` bit-exact. Also fixed: $P_{bub}$ was evaluated at the frozen
    `HPCC_T_PROD_DES_C` — a bubble pressure at a fixed temperature is not a bubble pressure — and now
    uses the live gated $T_{prod}$ (telemetry only; it does not enter `pt_target`, so no new loop).

    **Loop-gain check** against the `_disturbance_gate` self-excitation path: both new legs are
    **negative feedback** ($T\uparrow \Rightarrow K\uparrow \Rightarrow \phi\uparrow \Rightarrow$ less
    CO₂ absorbed $\Rightarrow q_{carb}\downarrow \Rightarrow T\downarrow$), verified rather than
    assumed.

    Verified — pin gate `leaves: 25  keys: 15  diffs: 0`; suite **123 passed** (8 new tests in
    `backend/test_equation_audit_322e002.py`). Design hold 600 s: gate 0.000000, $T_{prod}$ drift
    **0.000e+00 °C**, $\phi$ identical to `HPCC_FRAC_GAS_DES` on every component by identity
    comparison. Dynamic acceptance — MP supply valve 50 → 62 % (PIC-329204 in MAN): TT-322010
    170.00 → 170.49 °C and the split follows, $\phi_{CO_2}$ **0.2036 → 0.2342**, gas product
    **60.33 → 69.34 t/h**; N/C setpoint cut to 92 %: $\phi_{CO_2}\to0.2105$, level swells 49.7 →
    55.3 %, duty 63 122 → 66 706 kW. Self-excitation check: $T_{prod}$ spans **0.0205 °C** and
    **0.2329 °C** respectively over the final five minutes — monotone convergence, no ringing.

17. **323E010 / 323F010 — the pre-evaporator was missing a feed (equation audit F-11 / TD-011).**
    Raised while closing the 323/324 component balance as a suspected *source-data* inconsistency:
    stream 317's tabulated composition is not reachable from stream 319 by evaporation. Removing
    319's water, NH₃ and CO₂ at the PFD's own percentages takes out
    $8692 + 820 + 651 = 10\,163$ kg/h against a tabulated total loss of
    $101\,570 - 92\,820 = 8750$ kg/h, so $\approx 1.4$ t/h of urea has to *appear* across the stage.
    It was **not** a data error. The licensor confirms the real topology is a **two-feed** stage:

    $$\underbrace{319}_{\text{323F004 liquid}} + \underbrace{331}_{\text{urea-recovery return}}
      \;\longrightarrow\; \text{323E010 (LP steam, shell side)}
      \;\longrightarrow\; \text{323F010 (vacuum)}
      \;\longrightarrow\; \underbrace{790}_{\text{gas}} + \underbrace{315}_{\text{solution}}$$

    Stream 331 is the granulation-scrubber return — 3270 kg/h, 44.37 % urea, 55 % water, **40 °C**.
    The engine had it entering at 323D002, *downstream* of the balance it closes. Stream 315 is the
    separator discharge and 317 is the same stream after the pump (0.5 → 3 bar a), which is why the
    PFD gives them one composition column.

    **(i) Evidence.** Three independent closures on the licensor's own tabulated flows: total mass
    $319+331 = 104\,840$ against $315+790 = 104\,860$ (**0.019 %**); urea $74\,317$ against $74\,273$
    (0.06 %); and — decisively — **formaldehyde**, $7.52$ kg/h in via 331 against $7.39$ kg/h out via
    315 (1.7 %). HCHO is non-volatile and stream 331 is its *only* source anywhere in the plant
    (UF-85 is dosed into the granulation scrubber), so it cannot be argued away as rounding. Before
    this fix the melt carried formaldehyde that no stream fed — it existed only as a frozen number
    inside `W_S317`.

    **(ii) Mass.** `R323_M331_DES` $=3270$ and `R323_M331_T_C` $=40$ enter as new PFD anchors. The
    vapour constant becomes a **sum**, $\dot m_{evap,des} = \phi_{evap}\dot m_{319,des} + \dot
    m_{331,des}$, written that way deliberately so `R323_M317_DES` keeps its exact bits and every
    unit-324 constant stays byte-identical. The runtime flow cap moves to anchored-ratio form,
    $\dot m_{evap,des}\cdot\frac{\dot m_{319}+\dot m_{331}}{\dot m_{319,des}+\dot m_{331,des}}$, so
    numerator and denominator are bit-identical at the seed and the ratio is exactly 1.

    **(iii) Energy.** The stage balance gains the cold feed's sensible term:
    $$\dot m_{319}c_p(T_{319}-T) \;+\; \dot m_{331}c_p(T_{331}-T) \;+\; Q_{E010}
      \;=\; \dot m_{evap}\lambda_{evap}$$
    331 lands 59 °C below the product, so it is a heat **sink** — the back-solved design duty rises
    $5048 \to \mathbf{7249}$ kW and `R323_E010_UA_KW` with it. The pre-evaporator now pays both to
    bring the return stream to boiling and to evaporate the extra water it carries.

    **(iv) Species.** `_sol_stage_anchor` and `sol_advance` take an optional second inlet, summed
    component-wise before the balance is struck (adding $0.0$ when absent, so the other four stages
    stay bit-identical). The back-solved stage residual — the negative vapour the old anchor had to
    clip — falls from $\mathbf{-1414}$ kg/h to **exactly 0.000**, and the water closure term from
    $\approx 1.4$ t/h to **1.2 kg/h in 12 020** (0.01 %). Urea gains a real relative volatility
    $\alpha = 0.0014$ (a small carryover matching the PFD's 0.14 % urea in stream 790) where it had
    been clipped to zero.

    Verified — pin gate `leaves: 25  keys: 15  diffs: 0`; suite **139 passed** (3 new tests in
    `backend/test_equation_audit_species.py`). Design hold 600 s: C1 closure residual
    **0.000e+00 kg/h**, and zero drift on `evap_th`, `product317_th` and TT-323010 across a second
    600 s window. 323F010 — still **un-pinned** — now reaches **79.963 %** urea against the PFD's
    80.00, where it published 78.444 and needed `sol_pin_strength` to hide the gap; HCHO traces
    331 → 315/317 → 401 → 402 at 0.0081 / 0.0094 / 0.0098 % against the PFD's 0.00797 / 0.00948 /
    0.0099. Total biuret formation lands at **324.6 kg/h** against the 322 kg/h the PFD flows imply
    (0.8 %, down from 5 %), because 331 carries biuret in and the 323F010 extent drops
    $0.136 \to 0.006$ kmol/h.

    **Correction, made while closing Delta #18.** This entry previously recorded "one residual PFD
    inconsistency, noted not fixed": stream 790's tabulated 2.29 % CO₂ read as 276 kg/h against the
    651 kg/h the balance forces. That was a **units misreading on our side**, not licensor data.
    Stream 790 is tabulated as `Vapour`, and the PFD gives vapour compositions in **mole %** —
    2.29 mol % of 646.9 kmol/h is **652.0 kg/h**, the 651 the balance forces. All four species close
    across the stage (CO₂ −0.25, H₂O −4.33, NH₃ +3.12, urea +6.82 kg/h in 104 840). There is no
    accepted variance at 323F010.

18. **Unit 328 — the desorption train's own species layer (equation audit F-8 remainder / TD-009).**
    The last lumped-mass island. 328C002 and 328C004 moved material with frozen overhead split
    constants — a fixed fraction of the inflow leaving overhead — and no composition existed
    anywhere in the unit.

    **The PFD composition-unit convention.** Nothing was anchorable until this was settled. Read as
    mass %, the licensor's table says carbon is not conserved across 328C002: 1658 kg/h of CO₂ in,
    858 out. It is conserved. **Liquid rows are mass %, vapour/gas rows are mole %**, and the
    tabulated `Average Molar Weight` is the discriminator:

    $$\overline{M}_{\text{mole}} = \sum_i y_i M_i, \qquad
      \overline{M}_{\text{mass}} = \Big(\sum_i w_i / M_i\Big)^{-1}$$

    For stream 737 the PFD tabulates 20.81; the mole reading gives 20.81, the mass reading 18.94.
    Verified across ~90 streams in all four process-stream tables. Read correctly, every column
    closes per component to under 2 kg/h against 34–40 t/h throughputs, with nothing fitted.

    **Geometry from the mechanical datasheet** (Uhde UD-AU-328-EC-0001 rev 01). 328C002 and 328C004
    are **one 25.5 m tower**, C002 stacked on C004 on a common skirt — corroborated independently by
    Stamicarbon's "top part / bottom part of the desorber" description, in which the bottom part's
    off-gas is the top part's stripping agent (exactly PFD stream 750 → 328C002). The sheet gives 15
    and 22 executed trays, ID 1250 mm, 500 mm spacing, 40 mm weir, 3125 × ⌀6 mm perforation. Holdup
    stopped being a 900 s residence-time guess and became

    $$M_\text{des} \;=\; \Big(N_\text{tray}\,A_\text{act}\,h_w\,\phi_\text{froth} \;+\; A_\text{col}\,h_\text{NLL}\Big)\rho$$

    giving 1588 kg (C002) and 1436 kg (C004) against the previous 8442 / 8431 — the real columns
    respond ~5× faster. Level is $M/M_\text{des}\times 50$, so the design point is untouched.

    **The tray count is load-bearing.** The back-solved $\alpha$ are lumped single-stage
    equivalents ($\alpha_{\text{NH}_3} = 5.1\times10^4$ in 328C004, because one well-mixed stage must
    reproduce 22 real trays). Left static the columns would separate identically whatever the
    operator did to the steam, so $\alpha$ moves with the Kremser residual $r(S,N)$, $N$ from the
    executed tray count. For a trace species on one well-mixed stage the overhead fraction is
    $m_v\alpha/(m_v\alpha + m_l)$; setting that equal to $1-r$ inverts exactly:

    $$\alpha_\text{eff} \;=\; \frac{L}{V}\cdot\frac{1-r}{r}$$

    an identity of the lumped form, not a fitted correction, and written as a live-over-design ratio
    so it is bit-exactly 1.0 at the seed.

    **Two defects this exposed.** (i) `R328_C003_W_UREA_746` was hardcoded 0.0082 — stream **738**'s
    urea, the feed to 328C002 — where the PFD gives 743/746 as 0.76 %. 328C002 dilutes 31 114 kg/h
    into 33 769 kg/h of bottoms, so the hydrolyser was handed 276.9 kg/h of urea against 256.6,
    **+7.9 %**. (ii) The trace-species ODE is stiff: 328C004 holds 1436 kg of liquid at 1 ppm
    ammonia — 1.4 **grams** — while 330 kg/h flows through, giving $\tau \approx 0.015$ s against a
    0.25 s tick. Explicit Euler overshoots ~16×, clamps at zero, and walked 328C002 from 0.63 % to
    2.2 % ammonia over four simulated hours. `des_advance` is implicit; lagging the summation
    denominator makes the removal linear in $w_k$, so

    $$m_k^{n+1} \;=\; \frac{m_k^{n} + \big(\dot m_\text{in,k} + \nu_k\xi\big)h}
                            {1 + \big(m_v c_k + m_l\big)h/M}, \qquad c_k = \frac{\alpha_k}{\sum_j \alpha_j w_j}$$

    is closed-form, needs no iteration, cannot go negative, and is exactly stationary when source
    equals sink — which is what makes the design point a genuine fixed point.

    **Verification.** After 4 simulated hours the train sits on its PFD compositions (328C002 NH₃
    0.630 % vs 0.630, CO₂ 0.110 vs 0.110; 328C004 NH₃ 0.998 ppm vs the 1 ppm guarantee). Cutting
    FIC-329401 LP strip steam to 90 / 80 / 70 / 50 % drives the condensate ammonia to
    9.6 / 122 / 1108 / 16 035 ppm. Dropping the hydrolyser from 200 °C to 160 °C drives the urea slip
    0.30 → 1161 ppm — independently corroborating the *Urea Simulator Gap Resolution* study's
    prediction of "0.32 ppm to over 1200 ppm", from an Arrhenius fitted to neither.

19. **322E001 HP stripper — hydrodynamic flooding limit** (TD-006, first half; audit slot 7).

    The unit carried **no tube geometry at all**. Every term in `stripper_322e001` whose comment
    read "flood" was a *thermal* metaphor for the steam-dilution branch $(\text{raw\_load} < 0)$:
    it asks whether the shell steam can keep up with the liquid. A falling-film stripper's real
    ceiling is an independent question — **can the tube physically carry the film?** Once the
    rising gas core shears the descending film off the wall, the film thickens, liquid is dragged
    upward, and stripping stops regardless of available steam. That is a liquid-load limit.

    **Geometry, and why the tube count can be trusted.** Licensor DDS 322E001
    (Uhde UD-AU-322-DZ-0003-003 rev 00, page 3) gives $N = 2600$, $d_o \times t = 31 \times 3.0$ mm,
    $L_{\text{eff}} = 6000$ mm. The sheet is self-consistent — its own tabulated exchange surface
    confirms the count, so the number is not a single cell read on trust:

    $$N\,\pi\,d_o\,L = 2600 \times \pi \times 0.031 \times 6.000 = 1519.27\ \mathrm{m^2}
      \qquad\text{vs line 25: } 1519.00\ \mathrm{m^2} \quad (+0.018\,\%)$$

    **Three documents agree, so nothing is fabricated.** The limit is 145 kg/h of solution per 1″
    tube at 183 °C / 140 bar (Brouwer, *UreaKnowHow* 2025, citing IFS Proceeding 166). It applies
    here directly because the DDS bore is $d_i = 0.031 - 2(0.003) = 0.025$ m $= 0.984''$; because
    the DDS effective length 6.000 m is exactly the length the same paper ties to a Stamicarbon
    stripper's 80 % design efficiency; and because the quoted 183 °C reference *is*
    `STRIP_FEED207_T_C`, this stripper's own feed temperature.

    **The design point, computed rather than tuned:**

    $$\phi_{\text{flood}} = \frac{\dot m_{\text{feed}}}{N\,\dot m_{\text{flood,tube}}}
      = \frac{280\,797}{2600 \times 145} = 0.7448$$

    i.e. 108.0 kg/h per tube, **74.5 % of the limit**, with flooding onset at 134 % of design plant
    load — the same order as the literature's "110 % when new, 120 % at end of life".

    **The pin argument is structural, not an anchored ratio — and that is stronger.** Because
    $\phi_{\text{des}} < 1$ the constraint is one-sided and does not bind at the seed. With
    $x = \max(\phi - 1,\, 0)$ returning the literal $0.0$:

    $$\Delta T_{\text{flood}} = \Delta T_{\text{gap}}\left(1 - e^{-K_T x}\right) \;\big|_{x=0} = 0,
      \qquad
      g_{\text{flood}} = \frac{1}{1 + K_\eta x}\;\Big|_{x=0} = 1$$

    are *exact identities*, not near-misses. No float operand ordering is involved: the guarantee
    rests on the physical fact that the plant operates below its flooding limit. Verified by
    equality — `g_flood == 1.0`, `dT_flood == 0.0` — with the gate at `diffs: 0`.

    **Calibration from the literature, not fitted.** The bottom-temperature signature Brouwer gives
    for flooding onset — +3–4 °C in 15 minutes — fixes $K_T$, capped by the *same* ceiling the
    steam-dilution branch already uses, $\Delta T_{\text{gap}} = 183 - 172 = 11$ °C, since both
    describe one end state (unstripped reactor liquor falling through untouched):

    $$11.0\left(1 - e^{-K_T (0.10)}\right) = 3.5 \;\Rightarrow\; K_T = 3.83
      \qquad\text{model returns } 3.50\ ^\circ\mathrm{C}$$

    **One sign trap, avoided deliberately.** $g_{\text{flood}}$ multiplies the **split only, never
    $\eta_T$**. Flooding *increases* liquid residence time — Brouwer's "stagnation or upward
    dragging of the film" — so hydrolysis and biuret rise. Since $\eta_T$ scales $\xi_{\text{hyd}}$,
    folding $g_{\text{flood}}$ into it would have *cut* hydrolysis, the wrong sign. The rise is
    already carried without any new term, because $\Delta T_{\text{flood}}$ raises $T_{\text{bot}}$
    and $\xi_{\text{biu}}$ is Arrhenius in $T_{\text{bot}}$.

    **Verification.** Inert below onset (`g_flood` exactly 1.0 at 50–130 % load). Above it, the
    cascade Brouwer describes appears as an *output*: overhead NH₃ recovery 89 % at design → 56 % at
    onset → 30 % at 180 % load, the volatiles held in the bottoms and slipping to the LP section via
    LV-322501, with $T_{\text{bot}}$ rising and staying bounded by the condensing shell steam.

    **Deliberately not modelled:** the corrosion/lifetime drift (the limit rising 110 → 120 % as the
    bore grows) and the active-corrosion metallurgy — multi-year effects with no place in a
    shift-length scenario. **One unsourced constant:** $K_\eta$; the source states efficiency drops
    but publishes no curve, so it reuses the unit's existing choke scale (`STRIP_ETA_KT` = 1.50)
    rather than invent a fit.

---

## 1. Equipment & Node Mapping

### 1.1 321D003 — NH₃ Feed Drum
Vertical cylindrical liquid-ammonia buffer drum receiving battery-limit (BL) NH₃ feed from 309E005 sub-cooler. NPSH reservoir for triplex pumps 321P002 A/B.

| Parameter | Value | Unit |
|---|---|---|
| Inside Diameter | 0.970 | m |
| Cylindrical Height | 1.400 | m |
| Working Volume | 1.0345 | m³ |
| Design Feed Rate | 40,756 | kg/h |
| NH₃ Density (25 °C) | 604.8 | kg/m³ |
| Design Pressure (top) | 12.3 | bar g |
| Feed Temperature | 25.0 | °C |

**Thermodynamic role.** Mass-balance integrating node. Liquid inventory Euler-integrated; temperature relaxes to BL supply via energy balance:
$$\frac{dM}{dt} = \dot m_{BL} - \dot m_{pump}, \qquad M c_p \frac{dT}{dt} = \dot m_{BL}\,c_p\,(T_{BL} - T_{tank})$$
NH₃ saturation pressure via NIST Antoine determines sub-cooling margin PDY.

### 1.2 321P002 A/B — HP NH₃ Triplex Pumps
Three-plunger positive-displacement reciprocating pumps driven through VOITH torque-converter scoops; speed via converter valve opening (SIC-321950/951).

| Parameter | Symbol | Value | Unit |
|---|---|---|---|
| Plunger Diameter | $D$ | 140 | mm |
| Stroke Length | $L$ | 205 | mm |
| Number of Plungers | $n_p$ | 3 | — |
| Volumetric Efficiency | $\eta_v$ | 0.95 | — |
| Mechanical Efficiency | $\eta_m$ | 0.915 | — |
| Rated Speed | | 152 | rpm |
| Normal Speed | | 124 | rpm |
| Minimum Speed | | 37 | rpm |
| Rated Motor Current | | 51 | A |

**Hydraulic role.** Motive-fluid source for the HP synthesis loop; combined discharge is the motive stream for the 322F001 ejector. Flow is strictly proportional to speed (PD pump): $Q = N \cdot V_{rev} \cdot \eta_v \cdot 60$.

### 1.3 322F001 — HP Ejector (Liquid-Liquid Jet Pump)
Single-nozzle liquid-liquid ejector. Motive: pure HP NH₃ from 321P002 A/B. Suction: enriched carbamate from 322E003 overflow. Discharge → 322E002 HPCC.

| Parameter | Symbol | Value | Unit |
|---|---|---|---|
| Design Motive Flow | $\dot m_{mot,des}$ | 40,756 | kg/h |
| Design Discharge Total | $\dot m_{disch,des}$ | 98,320 | kg/h |
| Design Entrainment Ratio | $\mu$ | 1.4125 | — |
| Design HV-322602 Opening | $O_{des}$ | 74 | % |
| Jet-Stall Motive Knee | $\phi_{stall}$ | 0.35 | — |
| Discharge Pressure | | 144.2 | bar a |
| Suction Temperature | | 178.8 | °C |
| $c_{p,motive}/c_{p,carb}/c_{p,disch}$ | | 4.74 / 3.10 / 3.50 | kJ/kg·K |

**Hydraulic role.** Synthesis-loop circulator. Entrains carbamate from 322E003 by HP-NH₃ motive momentum; controls forward flow (HPCC→Reactor) via affinity-law head $\phi_{fwd}=\phi_m^2$. Motive-linked stall curve enforces a physical minimum motive fraction.

### 1.4 322E002 — HP Carbamate Condenser (HPCC)
Vertical shell-and-tube falling-film condenser. Tube side: co-current downward stripper top gas + ejector carbamate liquid. Shell side: BFW from 322D001 A/B raises 4.4 bar a LP steam.

| Parameter | Value | Unit |
|---|---|---|
| Product Temperature (TT-322010) | 170 | °C |
| Design Pressure | 144.2 | bar a |
| Shell LP Steam Pressure | 4.4 | bar a |
| Shell $T_{sat}$ | 146.3 | °C |
| Carbamate Exotherm $\Delta H$ | 160 | kJ/mol CO₂ |
| Gas $c_p$ (sensible) | 2.0 | kJ/kg·K |
| LP Steam Latent Heat | 2120 | kJ/kg |
| Normal Liquid Level (NLL) | 50 | % |
| Liquid Holdup Time Constant $\tau_{fill}$ | 6.0 | min |

**Thermodynamic role.** Condenses NH₃ + CO₂ from stripper top gas into ammonium carbamate ($2NH_3 + CO_2 \to NH_2COONH_4$, $\Delta H = -160$ kJ/mol). The phase split is an isothermal $(T,P)$ Rachford-Rice flash **anchored on** the design fractions $\phi_i$ (§3.6) and rate-limited through the interfacial film over $\tau_{fill}$ — the same holdup constant that sets the sump inventory — so the split is a dynamic state, not an algebraic map. Carbamate-melt bubble-point $P_{bub}(T_{prod},L,W)$ sets loop outlet pressure. Shell duty = carbamate exotherm + gas sensible cooling.

### 1.5 322R001 — HP Urea Reactor
Vertical autoclave, 11 sieve trays, liquid plug-flow. Carbamate dehydration $NH_2COONH_4 \to CO(NH_2)_2 + H_2O$ at ~54.3 % per-pass CO₂ conversion via Modified Inoue-Kanai kinetics.

| Parameter | Symbol | Value | Unit |
|---|---|---|---|
| Inside Diameter | | 2950 | mm |
| Liquid Height (bot T.L → top T.L) | | 25,000 | mm |
| Volume | | ~191 | m³ |
| Operating Pressure | | 144.9 | bar a |
| Overflow Temperature (TT-322014) | | 183 | °C |
| Design Conversion | $X_{des}$ | 54.3 | % |
| Urea Formation Extent | $\xi_{urea,des}$ | 1302.27 | kmol/h |
| Biuret Formation Extent | $\xi_{biu,des}$ | 2.414 | kmol/h |
| Design NLL (LT-322504) | | 80 | % |
| HV-322605 Design Opening | $\varphi_{des}$ | 60 | % |
| Total Residence Time | $\tau_{tot}$ | ~44.9 | min |
| Thermal Time Constant | $\tau_T$ | 8.0 | min |

### 1.6 322E001 — HP Stripper (Falling-Film Shell & Tube)
Vertical falling-film counter-current S&T exchanger. Tube side: reactor overflow (stream 207, top) + CO₂ strip gas (bottom). Shell side: condensing MP steam from 329D005.

| Parameter | Value | Unit |
|---|---|---|
| Tubes | 2600 × 6 m, OD 31×3 (ID 25) | — |
| Heat Transfer Area | 1519 | m² |
| Design Heat Duty | 39,400 | kW |
| Design Steam Flow | 75,300 | kg/h |
| Steam Pressure (329D005) | 19.7 | bar a |
| Top Gas Temperature (TT-322013) | 187 | °C |
| Bottom Solution Temperature (TT-322004) | 172 | °C |
| Tube-Side Pressure | 144 | bar a |
| Bottom Sump Area | 4.638 | m² |
| Level Span (LT-322501) | 1.5 | m |
| Bottom Solution Density | 1134.64 | kg/m³ |
| Design Bottom Flow | 130,482 | kg/h |

### 1.7 322E003 — HP Scrubber (Reactive Falling-Film Absorber)
Vertical tube-side counter-current absorber. Inert-rich reactor off-gas rises; cold weak-carbamate wash (323P001 A/B) falls as film; NH₃/CO₂ recovered by carbamate formation. Shell-side CCW loop (329P006 A/B) removes exotherm.

| Parameter | Value | Unit |
|---|---|---|
| Design Carbamate Wash | 36,915 | kg/h |
| Wash Temperature | 74 | °C |
| Design Off-Gas (→ 322C001) | 64.78 | kmol/h |
| Off-Gas Temperature (TT-322011) | 114 | °C |
| Overflow Temperature (TT-322002) | 178.8 | °C |
| CCW Design Flow (329P006 A/B) | 306,000 | kg/h |
| CCW Supply Temperature (TIC-329005) | 80 | °C |
| CCW Return Temperature (TT-329125) | 95 | °C |
| CCW Design Duty | ~5,329 | kW |

**Thermodynamic role.** Recovers volatile NH₃/CO₂ from reactor off-gas purge before venting inerts to 322C001. Overflow (enriched carbamate) is suction for 322F001 ejector, closing the recycle. CCW duty coupled to synthesis-vent pressure: $Q_{scrubber} = Q_{ccw,des}\cdot s \cdot \nu$, $\nu = \text{PT-329201}/P_{des}$.

### 1.8 Component Molar Mass Table

| Component | MW (g/mol) | Component | MW (g/mol) |
|---|---|---|---|
| CO₂ | 44.0098 | Biuret | 103.081 |
| NH₃ | 17.0304 | N₂ | 28.0134 |
| H₂O | 18.0152 | O₂ | 31.9988 |
| Urea | 60.056 | CH₄ | 16.043 |
| | | H₂ | 2.0158 |

---

## 2. Instrument Tag Dictionary

PV = read-only; MV = manipulatable; SP = setpoint.

### NH₃ Feed / Pumps
| Tag | Description | Units | Type |
|---|---|---|---|
| FI-321401 | NH₃ total pump discharge flow | t/h | PV |
| FQI-321401 | NH₃ delivered totalizer | t | PV |
| TT-321001 / TT-321002 | 321D003 tank temperature (L/R) | °C | PV |
| LI-321501 | 321D003 NH₃ drum level | % | PV |
| LSL-321501 | Low-level switch (active = LO) | bool | PV |
| PI-321201 / PI-321202 | NH₃ feed pressure (pump A/B) | bar g | PV |
| PY-321201 / PY-321202 | NH₃ sat. vapour pressure (Antoine) | bar a | PV |
| PDY-321203 / PDY-321204 | Sub-cooling margin (pump A/B) | bar | PV |
| TI-321020 | Common pump discharge temperature | °C | PV |
| PI-DISCH | HP discharge header pressure | bar g | PV |
| SIC-321950 / SIC-321951 | Pump A/B torque-converter opening | % | MV/SP |
| XV-321901 / XV-322901 | NH₃ suction / discharge block valve | bool | MV |
| RATIO.SP / RATIO.PV / RATIO.BAL | Molar N/C ratio SP / actual / balance | mol/mol | SP/PV/PV |

### CO₂ Feed Line (320K002 → 322E001)
| Tag | Description | Units | Type |
|---|---|---|---|
| FT-322403 | CO₂ feed flow (normal volume) | Nm³/h | PV |
| FY-322403 | CO₂ feed flow (mass) | t/h | PV |
| TI-322017 | CO₂ feed temperature | °C | PV |
| XV-322902 | CO₂ feed isolation to 322E001 | bool | MV |
| PV-322203 | CO₂ vent valve (opening) | % | PV |
| HIC-322203 | PV-322203 minimum opening | % | MV |
| PIC-322203 | CO₂ line pressure controller | bar a | MV/SP |

### 322F001 Ejector
| Tag | Description | Units | Type |
|---|---|---|---|
| HIC-322602 | Ejector spindle opening (HV-322602) | % | MV |
| TT-322012 | Ejector discharge temperature → 322E002 | °C | PV |
| TI-322002 | 322E003 overflow (suction) temperature | °C | PV |
| PT-329201 | Synthesis-loop top pressure (dynamic) | bar a | PV |

### 322E001 Stripper
| Tag | Description | Units | Type |
|---|---|---|---|
| TT-322014 | Reactor overflow feed temperature | °C | PV |
| TT-322013 | Stripper top gas temperature → 322E002 | °C | PV |
| TT-322004 | Bottom solution temperature (pre-flash) | °C | PV |
| TT-323001 | Post-LV flash temperature → 323C003 | °C | PV |
| LT-322501 | Bottom sump liquid level | % | PV |
| LIC-322501 | Bottom sump level controller → LV-322501 | % | MV/SP |
| LV-322501 | Bottom drain control valve (FC, linear) | % | MV |

### 322E002 HPCC
| Tag | Description | Units | Type |
|---|---|---|---|
| TT-322010 | HPCC liquid product temperature → 322R001 | °C | PV |
| TT-329001 | Shell BFW/condensate feed temperature | °C | PV |
| LT-322E002 | HPCC liquid level (dynamic inventory) | % | PV |

### 322R001 Reactor
| Tag | Description | Units | Type |
|---|---|---|---|
| TT-322005 | Axial temp N6 A (EL +21700 mm) | °C | PV |
| TT-322006 | Axial temp N6 B (EL +14800 mm) | °C | PV |
| TT-322007 | Axial temp N6 C (EL +7900 mm) | °C | PV |
| TT-322008 | Axial temp N6 D (EL +1000 mm) | °C | PV |
| TT-322009 | Reactor off-gas temperature → 322E003 | °C | PV |
| LT-322504 | Reactor top liquid level (dynamic) | % | PV |
| AT-322701 | Reactor overflow N/C ratio (atom-basis) | mol/mol | PV |
| HIC-322605 / HV-322605 | Reactor overflow valve controller / opening | % | MV/PV |

### 322E003 Scrubber
| Tag | Description | Units | Type |
|---|---|---|---|
| TT-322011 | Off-gas temperature → HV-322604 | °C | PV |
| HIC-322604 / HV-322604 | Off-gas valve controller / opening | % | MV/PV |
| LT-329501 | Overflow seal-leg level | % | PV |
| TT-329125 | CCW return temperature (shell out) | °C | PV |
| TDY-329125 | CCW ΔT (condensation quality) | °C | PV |
| FIC-329409 | CCW circulation flow controller → FV-329409 | t/h | MV/SP |
| TIC-329005 | CCW supply temperature controller → TV-329005 | °C | MV/SP |

---

## 3. Core Thermodynamic & Kinetic Equations

### 3.1 Modified Inoue-Kanai Conversion Model (322R001)
Separable equilibrium structure re-fitted to the plant HMB (not a transcription of published polynomial coefficients; calibrated to the as-built design point):
$$X(L,W,T) = X_\infty \cdot f_L(L) \cdot f_W(W) \cdot f_T(T)$$
where $L = N/C_{molar} = n_{NH_3}/n_{CO_2}$, $W = H/C_{molar} = n_{H_2O}/n_{CO_2}$, and $T$ is reactor bulk temperature (°C).

**3.1.1 NH₃-Excess Saturation $f_L$.** $L=2$ is the dehydration stoichiometric floor ($2NH_3 + CO_2 \to urea + H_2O$); excess NH₃ drives dehydration forward with Michaelis-Menten saturation:
$$f_L(L) = \frac{\alpha\,(L-2)}{1 + \alpha\,(L-2)}, \qquad \alpha = 3.6180$$
At design feed $L_0 = 3.072961$:
$$f_L(L_0) = \frac{3.618 \times 1.072961}{1 + 3.618 \times 1.072961} = 0.795165$$

**3.1.2 Water Penalty $f_W$ (Stamicarbon H/C).** Product/recycle water back-shifts the dehydration equilibrium:
$$f_W(W) = \frac{1}{1 + \beta W}, \qquad \beta = 0.85$$
At design feed $W_0 = 0.407828$:
$$f_W(W_0) = \frac{1}{1 + 0.85 \times 0.407828} = 0.742582$$

**3.1.3 Arrhenius Temperature Hook $f_T$.**
$$f_T(T) = \exp\!\left[-\frac{E_a}{R}\left(\frac{1}{T+273.15} - \frac{1}{T_0+273.15}\right)\right], \qquad E_a = 10{,}000\ \text{J/mol},\ T_0 = 183\ \text{°C}$$
Because the current engine pins $T$ at $T_0$, $f_T \equiv 1.0$ today; $f_T$ is a forward hook (parabolic $T$-optimum is future scope).

**3.1.4 Thermodynamic Ceiling $X_\infty$.** Solved to hold the design anchor with $\alpha, \beta$ fixed:
$$X_\infty = \frac{X_{des}}{f_L(L_0)\,f_W(W_0)} = \frac{0.543}{0.795165 \times 0.742582} = 0.9196$$

**3.1.5 Normalized Conversion Factor (Engine Interface).** The engine consumes the dimensionless ratio so the pinned design HMB ($\xi_{urea}=1302.27$ kmol/h) is reproduced bit-exact:
$$CF(L,W,T) = \frac{X(L,W,T)}{X(L_0,W_0,T_0)} = 1.000000 \text{ at design}$$
$$\xi_{urea} = \xi_{urea,des}\cdot s \cdot CF(L,W,T), \qquad s = \dot m_{CO_2}/\dot m_{CO_2,des}$$
Overflow then atom-conserved with $d = \xi_{urea} - \xi_{urea,scaled}$:
$$\Delta \text{Urea} = +d, \quad \Delta \text{CO}_2 = -d, \quad \Delta \text{NH}_3 = -2d, \quad \Delta \text{H}_2\text{O} = +d$$

**3.1.6 $L_{drive}$ Loop Coupling.** Exogenous fresh-feed N/C (ratio.PV, set by pump speeds) mapped onto reactor-feed N/C that drives $f_L$:
$$L_{drive} = L_0 \cdot \left(1 + K_{NC,loop}\cdot\left(\frac{\text{ratio.PV}}{\text{ratio.PV}_{des}} - 1\right)\right), \qquad K_{NC,loop} = 0.50$$
At design (ratio.PV = 2.0231): $L_{drive} = L_0$ exactly → CF = 1, AT-322701 invariant.

### 3.2 Reactor Axial Temperature Profile
Liquid plug-flow rising from bottom tangent line; first-order thermal approach to outlet:
$$T(z) = T_{out} - (T_{out} - T_{in})\exp\!\left(-\frac{\tau(z)}{\tau_T}\right), \qquad \tau(z) = (z/H_L)\,\tau_{tot}$$
with $T_{in} = 170$ °C (HPCC product, TT-322010), $T_{out} = 183$ °C (overflow, TT-322014), $\tau_T = 8.0$ min.

| Tag | Elevation (mm) | $\tau$ (min) | Temperature (°C) |
|---|---|---|---|
| TT-322005 | 21,700 | 38.9 | 182.9 |
| TT-322006 | 14,800 | 26.6 | 182.5 |
| TT-322007 | 7,900 | 14.2 | 180.8 |
| TT-322008 | 1,000 | 1.8 | 172.6 |

### 3.3 AT-322701 Reactor Overflow N/C Ratio (Atom-Basis)
$$\text{AT-322701} = \frac{\sum_i \dot n_i \cdot \#N_i}{\sum_i \dot n_i \cdot \#C_i}$$

| Species | #N atoms | #C atoms |
|---|---|---|
| NH₃ | 1 | 0 |
| Urea | 2 | 1 |
| Biuret | 3 | 2 |
| N₂ | 2 | 0 |
| CO₂ | 0 | 1 |
| CH₄ | 0 | 1 |

### 3.4 HP Stripper 322E001 — Strip Efficiency & Reactions

**3.4.1 Stripping Efficiency $\eta_T$** *(Rev-1 form; see Revision Delta #1 for live extension)*
$$\eta_T = \eta_{T,steam}\cdot g_{NC}\cdot g_{HC}$$
$$\eta_{T,steam} = \text{clamp}\!\left(\frac{T_{steam}}{T_{steam,des}}, 0, 1.15\right)$$
$$g_{NC} = \text{clamp}\big(1 - K_{\eta,N}\,(L_{react} - L_{0,des}),\ 0.50,\ 1.05\big), \qquad K_{\eta,N} = 1.50$$
$$g_{HC} = \text{clamp}\big(1 - K_{\eta,W}\,(W_{react} - W_{0,des}),\ 0.50,\ 1.05\big), \qquad K_{\eta,W} = 1.50$$
$\eta_T$ clamped to $[0, 1.15]$. At design ($T_{steam}=211.6$ °C, $L=L_0$, $W=W_0$): $\eta_T = 1.0$ exactly.

**3.4.2 Volatile Breakthrough (Slip).** Excess NH₃/water force volatile NH₃/CO₂ breakthrough to overhead (do not cut the thermal split fraction):
$$\text{slip} = \max(1 - g_{NC}, 0) + \max(1 - g_{HC}, 0)$$
$$f'_i = f_i + K_{slip}\cdot\text{slip}\cdot(1 - f_i), \qquad K_{slip} = 4.0 \quad (\text{NH}_3, \text{CO}_2 \text{ only})$$

**3.4.3 Strip Fraction Modulation.**
$$f_i = \text{clamp}\big(\underbrace{f_{i,des}\cdot\eta_{T,steam}\cdot\eta_{CO_2}\cdot\eta_P}_{\text{mod}},\ 0,\ 0.999\big)$$
$$\eta_{CO_2} = \text{clamp}(0.5 + 0.5\,s,\ 0.4,\ 1.05), \qquad \eta_P = \text{clamp}\!\left(2 - \frac{P}{P_{des}},\ 0.85,\ 1.15\right)$$

**3.4.4 Urea Hydrolysis & Biuret Formation.**
$$\xi_{hyd} = \xi_{hyd,des}\cdot\eta_T = 88.1\,\eta_T \quad [\text{kmol/h}]$$
$$\xi_{biu} = \xi_{biu,des}\cdot\exp\!\left[\frac{E_{a,biu}}{R}\left(\frac{1}{T_{biu,des}} - \frac{1}{T_{bot}}\right)\right]\cdot\frac{\dot n_{Urea,feed}}{\dot n_{Urea,0}}$$
with $\xi_{biu,des} = 0.667$ kmol/h, $E_{a,biu} = 85{,}000$ J/mol, $T_{biu,des} = 445.15$ K, $T_{bot} = (172 + 0.7\,\Delta T_s) + 273.15$ K.

**3.4.5 Stoichiometric Bookkeeping (Post-Reaction Available Moles).**
$$\text{Urea}_{avail} = \text{Urea}_{feed} - \xi_{hyd} - 2\,\xi_{biu}$$
$$\text{Biuret}_{avail} = \text{Biuret}_{feed} + \xi_{biu}$$
$$\text{H}_2\text{O}_{avail} = \text{H}_2\text{O}_{feed} - \xi_{hyd}$$

**3.4.6 Design Strip Fractions (Fraction to Top Gas) $f_{i,des}$.**

| Component | $f_{i,des}$ | Component | $f_{i,des}$ |
|---|---|---|---|
| NH₃ | 0.8546 | O₂ | 0.975 |
| CO₂ | 0.8606 | Urea | 0.0 (100 % bottom) |
| H₂O | 0.1313 | Biuret | 0.0 (100 % bottom) |
| N₂ | 0.9987 | CH₄ | 0.999 |
| | | H₂ | 0.999 |

### 3.5 HPCC 322E002 — Bubble-Point Pressure (Clausius-Clapeyron)
Loop outlet pressure set by carbamate-melt bubble-point at the HPCC combined-feed composition:
$$P_{bub}(T,L,W) = P_{des}\cdot\underbrace{\exp\!\left[\frac{\Delta H_{vap}}{R}\left(\frac{1}{T_0} - \frac{1}{T+273.15}\right)\right]}_{\text{Clausius-Clapeyron}}\cdot k_N(L)\cdot k_W(W)$$
$$k_N(L) = 1 + K_N\,(L - L_{0,des}), \quad K_N = +0.18 \ (\text{free-NH}_3 \text{ volatility})$$
$$k_W(W) = 1 + K_W\,(W - W_{0,des}), \quad K_W = -0.25 \ (\text{water dilution})$$
Both floored at zero ($\max(k,0)$). Design-anchored bit-exact: $P_{bub}(170, L_{0,des}, W_{0,des}) = 144.2$ bar a $= P_{des}$.

| Constant | Symbol | Value | Unit |
|---|---|---|---|
| HPCC_BUB_DHVAP_JMOL | $\Delta H_{vap}$ | 23,000 | J/mol |
| HPCC_BUB_KN | $K_N$ | +0.18 | 1/(N/C) |
| HPCC_BUB_KW | $K_W$ | −0.25 | 1/(H/C) |
| HPCC_T_PROD_DES_C | $T_0$ | 170 (443.15 K) | °C (K) |
| HPCC_P_DES_BARA | $P_{des}$ | 144.2 | bar a |

### 3.6 HPCC Gas-Phase Split Fractions $\phi_i$ — calibration and live flash

The vector below is the **calibration**, measured at 170 °C / 144.2 bar a. It is no longer the
answer: it is the anchor from which $K_{des,i}$ is back-solved each tick, and the live split is an
isothermal $(T,P)$ Rachford-Rice flash relaxed through the interfacial film (Revision Delta #16).
At the design seed the flash short-circuits and the gate is shut, so $\phi_i$ *equals* this table
bit-exact.

| Component | $\phi_i$ (fraction → gas) | Component | $\phi_i$ |
|---|---|---|---|
| CO₂ | 0.2036 | CH₄ | 1.0 |
| NH₃ | 0.2977 | H₂ | 1.0 |
| H₂O | 0.0450 | Urea | 0.0 |
| N₂ | 0.982 | Biuret | 0.0 |
| O₂ | 1.0 | | |

**Distributing set** $D=\{k:0<\phi_{des,k}<1\}=\{CO_2, NH_3, H_2O, N_2\}$. O₂/CH₄/H₂ never condense
and Urea/Biuret never boil, so both sets sit structurally outside the flash.

$$\psi_{des}=\sum_{k\in D} z_k\phi_{des,k},\qquad
  K_{des,k}=\frac{\phi_{des,k}(1-\psi_{des})}{\psi_{des}(1-\phi_{des,k})}$$

$$K_k(T,P)=K_{des,k}\exp\!\Big[\frac{\Delta H_k}{R}\Big(\frac{1}{T_{des}}-\frac{1}{T}\Big)\Big]\frac{P_{des}}{P},
\qquad
\Delta H_k=\begin{cases}
\Delta H_{carb}/3 = 53\,333 & k\in\{CO_2, NH_3\}\ \text{(carbamate } K_p=p^2_{NH_3}p_{CO_2}\text{)}\\
36\,900 & k=H_2O\ \text{(Raoult, water latent @170 °C)}\\
0 & k=N_2\ \text{(Henry, permanent gas)}
\end{cases}$$

$$\sum_{k\in D}\frac{z_k(K_k-1)}{1+\psi(K_k-1)}=0
\;\xrightarrow{\text{bisection}}\;\psi,
\qquad \phi^{eq}_k=\frac{K_k\psi}{1+\psi(K_k-1)}$$

$$\phi_k \leftarrow \underbrace{\phi_k+\frac{\Delta t}{\tau_{film}}\big(\phi^{eq}_k-\phi_k\big)}_{\text{interfacial relaxation, } \tau_{film}=\texttt{HPCC\_TAU\_FILL\_MIN}},
\qquad
\phi^{pub}_k=\phi_{des,k}+g\big(\phi_k-\phi_{des,k}\big)$$

with $g$ the Option-1 `_disturbance_gate`. The film relaxation is what makes the split physical: the
bare equilibrium target swings $\phi_{CO_2}$ from 0.0009 to 1.0 across 150 → 190 °C, because the
distributing $K$'s are tightly clustered and move together — 322E002 is mass-transfer limited, not
equilibrium limited (`References/HPCC description.md` §5.2–5.3).

### 3.7 HPCC Shell-Side Duty & LP Steam Generation
$$Q_{HPCC} = \underbrace{\dot n_{CO_2,abs}\cdot\Delta H_{carb}}_{Q_{carbamate}} + \underbrace{\dot m_{gas}\cdot c_{p,gas}\cdot(T_{strip,top} - T_{prod})}_{Q_{sensible}}$$
$$\dot m_{steam} = \frac{Q_{HPCC}\times 3600}{\lambda_{4.4\,bar}}$$
with $\Delta H_{carb} = 160$ kJ/mol, $c_{p,gas} = 2.0$ kJ/kg·K, $\lambda_{4.4\,bar} = 2120$ kJ/kg.

### 3.8 322E003 HP Scrubber — Condensation Deficit & Dynamic Pressure

**3.8.1 Condensation Capacity Ratio $\rho_{cond}$.**
$$\rho_{cond} = \frac{\dot m_{ccw}/\dot m_{ccw,des}}{s\cdot\nu}, \qquad \nu = \frac{\text{PT-329201}}{P_{des}}$$
When $\rho_{cond} < 1$ (CCW throttled or high vent load), off-gas under-condenses, vapour accumulates, PT-329201 rises.

**3.8.2 Pressure-Building Load (Vapour Differentiation).** Only free (acid) CO₂ and uncondensed NH₃ build synthesis pressure; NH₃ paired into carbamate ($2NH_3 + CO_2$) is absorbed:
$$\dot n_{CO_2,free} = \max\!\left(\dot n_{CO_2,top} - \tfrac{1}{2}\dot n_{NH_3,top},\ 0\right)$$
$$\dot n_{NH_3,slip} = \max(1 - \rho_{cond}, 0)\cdot\max(\dot n_{NH_3,top} - \dot n_{NH_3,top,des},\ 0)$$
$$n_{pb} = \dot n_{CO_2,free} + \dot n_{NH_3,slip}$$

**3.8.3 PT-329201 Dynamic Accumulation ($\tau_P$).**
$$P_{fwd} = P_{des}\cdot\left(1 + K_P\cdot\frac{n_{pb} - n_{pb,des}}{\dot n_{top,des}}\right)$$
$$P_{target} = P_{fwd} + K_{def}\cdot\max(1 - \rho_{cond}, 0)\cdot P_{des}$$
$$\tau_P\frac{d\,\text{PT}}{dt} = P_{target} - \text{PT} \;\Rightarrow\; \text{PT}_{n+1} = \text{PT}_n + \frac{\Delta t}{\tau_P\times 60}\,(P_{target} - \text{PT}_n)$$
clamped to $[P_{min}, P_{max}] = [120, 175]$ bar a.

| Symbol | Code Name | Value | Unit |
|---|---|---|---|
| $P_{des}$ | SYN_P_DES_BARA | 140.7 | bar a |
| $K_P$ | SYN_P_COUPLING | 1.0 | — |
| $K_{def}$ | SYN_P_DEFICIT_GAIN | 0.30 | bar/bar |
| $\tau_P$ | SYN_P_TAU_MIN | 4.0 | min |

### 3.9 CCW Thermal Balance (322E003 Shell Side)
$$Q_{scrubber} = Q_{ccw,des}\cdot s \cdot \nu \quad [\text{kW}]$$
$$\text{TT-329125} = T_{ccw,in} + \frac{Q_{scrubber}\times 3600}{\dot m_{ccw}\cdot c_{p,w}}, \qquad \text{TDY-329125} = \text{TT-329125} - \text{TIC-329005}$$
with $Q_{ccw,des} = 5329$ kW, $c_{p,w} = 4.18$ kJ/kg·K.

### 3.10 HV-322604 Off-Gas Valve — Joule-Thomson Letdown
$$T_{out} = T_{in} - \mu_{JT}\cdot\Delta P, \qquad \mu_{JT} = 0.55\ \text{°C/bar}, \quad \Delta P = 140.7 - 4.0 = 136.7\ \text{bar (choked, isenthalpic)}$$
Composition unchanged across the valve.

### 3.11 NH₃ Saturated Vapour Pressure (NIST Antoine)
Valid ~239–372 K; used for sub-cooling margin PDY:
$$\log_{10}(P_{bar}) = A - \frac{B}{T_K + C}, \qquad A = 4.86886,\ B = 1113.928,\ C = -10.409$$

### 3.12 Saturated Steam Temperature (Antoine for Water)
Valid 100–374 °C; $P$ in bar a, converted to mmHg internally:
$$T_{sat}(P) = \frac{1810.94}{8.14019 - \log_{10}(P\times 750.0617)} - 244.485 \quad [\text{°C}]$$

---

## 4. Hydraulic & Inventory Dynamics

### 4.1 321P002 A/B — Triplex Pump Hydraulics
**Swept volume & flow:**
$$V_{rev} = \frac{\pi}{4}D^2 L\,n_p = \frac{\pi}{4}(0.140)^2(0.205)(3) = 9.465\times 10^{-3}\ \text{m}^3/\text{rev}$$
$$Q\,[\text{m}^3/\text{h}] = N\,[\text{rpm}]\times V_{rev}\times \eta_v\times 60$$
Verification: $N=124 \Rightarrow Q = 66.91$ m³/h (datasheet 67.1); $N=152 \Rightarrow Q = 82.02$ m³/h (datasheet 82).

**Shaft power:**
$$P_{shaft}\,[\text{kW}] = \frac{Q\,[\text{m}^3/\text{s}]\times \Delta P\,[\text{Pa}]}{\eta_m\times 1000}$$

**Discharge temperature rise:**
$$\Delta T_{pump} = \frac{\Delta P}{\rho\cdot c_p}\left(\beta_{NH_3}\,T_K + \frac{1 - \eta_h}{\eta_h}\right)$$
with $\rho = 604.8$ kg/m³, $c_p = 4740$ J/kg·K, $\beta = 1.9\times 10^{-3}$ 1/K, $\eta_h = 0.85$.

### 4.2 322F001 HP Ejector — Affinity Head & Stall Curve
**Motive fraction & developed head:**
$$\phi_m = \frac{\dot m_{motive}}{\dot m_{motive,des}}, \qquad \phi_{fwd} = \phi_m^2$$
Affinity-law square ⇒ forward flow collapses quadratically as motive drops.

**Entrainment stall curve:**
$$f_{stall} = \text{clamp}\!\left(\frac{\phi_m - \phi_{stall}}{1 - \phi_{stall}},\ 0,\ 1\right), \qquad \phi_{stall} = 0.35$$
$$\mu = \mu_{des}\cdot\frac{O_{des}}{O_{eff}}\cdot f_{stall}$$
Below $\phi_m = 0.35$ the jet pump can no longer entrain → $\mu \to 0$ → synthesis loop stalls. The HV-322602 spindle opening $O_{eff}$ inversely modulates suction (reduce opening → more 322E003 suction).

**Ejector energy balance:**
$$T_d = \frac{\dot m_{mot}\,c_{p,N}\,T_{mot} + \dot m_{suc}\,c_{p,C}\,T_{suc}}{\dot m_d\,c_{p,D}}$$

**Discharge header pressure (affinity-law droop):**
$$P_{disch} = P_{idle} + (P_{design} - P_{idle})\cdot\phi_{fwd}$$
with $P_{idle} = 7.5$ bar g, $P_{design} = 164.0$ bar g. At design ($\phi_m = 1$): $P_{disch} = 164.0$; at zero motive: $P_{disch} = 7.5$.

### 4.3 HPCC 322E002 Liquid Level (Euler Integration)
$$\frac{dL_{HPCC}}{dt} = \frac{(\phi_{in} - \phi_{fwd})\times 100}{\tau_{fill}\times 60} \quad [\%/\text{s}]$$
$$\phi_{in} = \frac{\dot m_{liq,HPCC}}{\dot m_{liq,HPCC,des}} \ (\text{condensation make, motive-independent}), \qquad \phi_{fwd} = \phi_m^2$$
Stall: when ejector stalls ($\phi_{fwd}\ll 1$) condensation inflow continues ($\phi_{in}\approx 1$) → $dL/dt > 0$ → HPCC level swells.

### 4.4 322R001 Reactor Level (Euler Integration)
$$\dot V_{in} = \dot V_{des}\cdot s\cdot\phi_{fwd} \ (\text{ejector-driven forward feed from HPCC})$$
$$\dot V_{out} = \dot V_{des}\cdot s\cdot\frac{\varphi}{\varphi_{des}} \ (\text{gravity overflow through HV-322605})$$
$$\frac{dV}{dt} = \dot V_{in} - \dot V_{out} = \dot V_{des}\cdot s\cdot\left(\phi_{fwd} - \frac{\varphi}{\varphi_{des}}\right)$$
$$L^{n+1}_{react} = L^n_{react} + \frac{\Delta V}{V_{span}}\times 100 \quad [\%]$$
with $V_{span} = (\pi/4)(2.95)^2\times 25 = 170.8$ m³, $\varphi = \text{HIC-322605}/100$, $\varphi_{des} = 0.60$.

### 4.5 322E001 Stripper Bottom Sump Level
$$\frac{dL_{strip}}{dt} = \frac{(\dot m_{bot} - \dot m_{drain})}{3600\cdot m_{span}}\times 100 \quad [\%/\text{s}]$$
$$m_{span} = A_{sump}\times H_{span}\times \rho_{bot} = 4.638\times 1.5\times 1134.64 = 7892\ \text{kg}$$
**LV-322501 drain flow (linear characteristic):**
$$\dot m_{drain} = \dot m_{drain,des}\cdot\frac{O_{LV}}{O_{LV,des}}\cdot\sqrt{\frac{\Delta P}{\Delta P_{des}}}$$
with $\dot m_{drain,des} = 130{,}482$ kg/h, $O_{LV,des} = 82$ %, $\Delta P_{des} = 139.8$ bar.

### 4.6 321D003 NH₃ Tank Mass Balance
$$\frac{dM}{dt} = \dot m_{BL} - \dot m_{pump}, \qquad V^{n+1} = \text{clamp}\!\left(L_f\cdot V_{tank} + \frac{\Delta M}{\rho},\ 0,\ V_{tank}\right)$$

### 4.7 Hydraulic Cascade
```
321D003 NH3 Drum --Q(N)--> 321P002 A/B Triplex Pumps --NH3 motive (phi_m)-->
322F001 HP Ejector <--carbamate suction (mu*m_mot)-- 322E003 HP Scrubber
   |  phi_fwd = phi_m^2
   v
322E002 HPCC --Liq->Reactor (level state)--> 322R001 HP Reactor
   |  overflow (HV-322605 phi)              |  off-gas --> 322E003
   v                                        
322E001 HP Stripper:  top gas --> 322E002 HPCC ;  bot soln --> LV-322501 --> 323C003
322E003 HP Scrubber:  off-gas --> HV-322604 --> 322C001 LP
```

---

## 5. Process Control Architecture

### 5.1 Velocity-Form I-PD Controller Algorithm
All PID-class controllers use the velocity (incremental) form with anti-windup output clamping. Core algorithm for step $n$:
$$OP_{n+1} = OP_n + K_c\left[(e_n - e_{n-1}) + \frac{\Delta t}{T_i}e_n\right], \qquad e_n = SP - PV$$
Integral accumulator clamped independently:
$$I_{n+1} = \text{clamp}\!\left(I_n + \frac{e_n\cdot\Delta t}{T_i},\ -OP_{max},\ +OP_{max}\right)$$
PID object (SIC controllers) adds positional derivative:
$$OP = K_c\left(e + I + T_d\cdot\frac{e_n - e_{n-1}}{\Delta t}\right), \quad \text{clamped to } [OP_{min}, OP_{max}]$$

> **Live-engine note** (`controllers.py`): the implemented PID is a velocity I-PD where P and D act on **PV** (not error) and only I acts on error — $\Delta u = K_c[-(PV_n - PV_{n-1}) + \frac{\Delta t}{T_i}(SP-PV) - T_d\frac{PV_n - 2PV_{n-1}+PV_{n-2}}{\Delta t}]$ — then direction $\sigma$ ($+1$ REVERSE, $-1$ DIRECT), slew clamp $\pm\,\text{rate}\cdot\Delta t$, output clamp. No integral accumulator stored (velocity form), so no wind-up.

### 5.2 Controller Mode Logic Matrix

| Mode | Abbrev | SP Source | OP Source | Behaviour |
|---|---|---|---|---|
| MANUAL | MAN / M | n/a | Operator-entered | OP held at last value. No PID action. Direct manipulation via set_op. |
| AUTO | AUTO / A | Operator SP | PID output | PID tracks SP vs PV. Bumpless MAN→AUTO: SP adopts current PV. |
| CASCADE | CAS / C | Upstream block + bias | PID output | SP = cascade demand + operator N/C bias. Bias reset to 0 on CAS entry; master ratio block auto-tracks. |
| OOS | OOS | n/a | Frozen | Out-of-service; reserved for future trip/interlock integration. |

### 5.3 Slew-Rate Limiting
$$O^{n+1}_{act} = O^n_{act} + (O_{target} - O^n_{act})\cdot\alpha, \qquad \alpha = \min\!\left(1, \frac{\Delta t}{\tau_{act}}\right), \quad \tau_{act} = 2\ \text{s}$$

### 5.4 Anti-Windup Clamping
Integral accumulator hard-clamped symmetrically at $[-OP_{max}, +OP_{max}]$; final output separately clamped to $[OP_{min}, OP_{max}]$ (typically $[0, 100]$ %). Dual clamp prevents wind-up during sustained saturation.

### 5.5 Controller Tuning Parameters

| Controller Tag | $K_c$ | $T_i$ (s) | $T_d$ (s) | OP Range | Action |
|---|---|---|---|---|---|
| SIC-321950 (Pump A) | 2.0 | 8.0 | 0.0 | 0–100 % | Direct |
| SIC-321951 (Pump B) | 2.0 | 8.0 | 0.0 | 0–100 % | Direct |
| LIC-322501 (Strip Level) | 2.5 | 90.0 | — | 0–100 % | Direct (FC valve → air-to-open) |
| PIC-322203 (CO₂ Pressure) | — | — | — | 0–100 % | Reverse (integrating; gain 0.5 %/bar·s) |
| FIC-329409 (CCW Flow) | — | — | — | 0–100 % | Boundary-controlled (PV=SP in AUTO) |
| TIC-329005 (CCW Temp) | — | — | — | 0–100 % | Boundary-controlled (PV=SP in AUTO) |

### 5.6 Cascade Architecture (N/C Ratio Block)
$$\dot m_{NH_3,sp} = \text{ratio.SP}\cdot\frac{M_{NH_3}}{M_{CO_2}}\cdot\dot m_{CO_2}$$
$$Q_{sp} = \frac{\dot m_{NH_3,sp}\times 1000}{\rho_{NH_3}}, \qquad N_{req} = \frac{Q_{sp}/n_{active}}{V_{rev}\cdot\eta_v\cdot 60}, \qquad O_{CAS} = \frac{N_{req}}{N_{rated}}\times 100$$

### 5.7 Trip Logic

| Trip ID | Condition | Description |
|---|---|---|
| 21_2 | Tank level < 5 % | 321D003 low-low level |
| 21_8 | Suction P < 17 bar g AND Pump A ON | Low suction pressure (Pump A) |
| 21_10 | Suction P < 17 bar g AND Pump B ON | Low suction pressure (Pump B) |

---

## 6. Calibration Constants — Master Table

### 6.1 Physical Properties & Feed Constants
| Symbol | Code Name | Value | Unit | Description |
|---|---|---|---|---|
| $\rho_{NH_3}$ | NH3_RHO | 604.8 | kg/m³ | Liquid NH₃ density at 25 °C |
| $g$ | G | 9.81 | m/s² | Gravitational acceleration |
| $c_{p,NH_3}$ | CP_NH3 | 4740 | J/kg·K | Liquid NH₃ specific heat |
| $\beta_{NH_3}$ | BETA_NH3 | 1.9×10⁻³ | 1/K | Isobaric expansivity |
| $\eta_h$ | ETA_PUMP_HYD | 0.85 | — | Pump hydraulic efficiency |
| $M_{NH_3}$ | M_NH3 | 17.031 | g/mol | NH₃ molar mass |
| $M_{CO_2}$ | M_CO2 | 44.009 | g/mol | CO₂ molar mass |
| $M_{CO_2}/M_{NH_3}$ | NC_FACTOR | 2.584 | — | N/C mass→molar factor |
| $\Delta t$ | DT | 0.1 | s | Simulation tick |
| $P_{atm}$ | P_ATM_BAR | 1.013 | bar | Atmospheric pressure |
| $P_{syn,down}$ | P_SYN_DOWN_BAR | 165.0 | bar a | Downstream synthesis nominal P |

### 6.2 Reactor Kinetics (Modified Inoue-Kanai)
| Symbol | Code Name | Value | Unit |
|---|---|---|---|
| $R$ | R_GAS | 8.314 | J/(mol·K) |
| $L_0$ | L0_DES | 3.072961 | mol/mol |
| $W_0$ | W0_DES | 0.407828 | mol/mol |
| $T_0$ | T0_DES_C | 183.0 | °C |
| $X_\infty$ | X_INF | 0.9196 | — |
| $\alpha$ | ALPHA_NC | 3.6180 | — |
| $\beta$ | BETA_HC | 0.85 | — |
| $E_a$ | EA_JMOL | 10,000 | J/mol |
| $X_{des}$ | X_DES | 0.543 | — |
| $K_{NC,loop}$ | REACT_NC_LOOP_GAIN | 0.50 | — |
| ratio.PV | RATIO_PV_DES | 2.0231 | mol/mol |

### 6.3 Ejector 322F001
| Symbol | Code Name | Value | Unit |
|---|---|---|---|
| $\dot m_{mot,des}$ | EJ_MOTIVE_NH3_DES | 40,756 | kg/h |
| $\dot m_{disch,des}$ | EJ_DES_TOTAL | 98,320 | kg/h |
| $\mu_{des}$ | EJ_MU | 1.4125 | — |
| $O_{des}$ | EJ_OPEN_DES | 74 | % |
| $\phi_{stall}$ | EJ_STALL_PHI | 0.35 | — |
| $c_{p,N}$ | EJ_CP_N | 4.74 | kJ/kg·K |
| $c_{p,C}$ | EJ_CP_C | 3.10 | kJ/kg·K |
| $c_{p,D}$ | EJ_CP_D | 3.50 | kJ/kg·K |
| $T_{suc}$ | EJ_T_SUCTION_C | 178.8 | °C |
| $P_{idle}$ | (inline) | 7.5 | bar g |

### 6.4 Stripper 322E001
| Symbol | Code Name | Value | Unit |
|---|---|---|---|
| $\xi_{hyd,des}$ | STRIP_XI_HYD_DES | 88.1 | kmol/h |
| $\xi_{biu,des}$ | STRIP_XI_BIU_DES | 0.667 | kmol/h |
| $K_{\eta,N}$ | STRIP_ETA_KN | 1.50 | — |
| $K_{\eta,W}$ | STRIP_ETA_KW | 1.50 | — |
| $\eta_{floor}$ | STRIP_ETA_FLOOR | 0.50 | — |
| $K_{slip}$ | STRIP_SLIP_GAIN | 4.0 | — |
| $E_{a,biu}$ | STRIP_BIU_EA | 85,000 | J/mol |
| $L_0$ (strip feed) | STRIP_L0 | 1.9045 | mol/mol |
| $W_0$ (strip feed) | STRIP_W0 | 1.0610 | mol/mol |
| $T_{steam,des}$ | STRIP_STEAM_T_DES_C | 211.6 | °C |
| $K_c$ (LIC-322501) | LIC_322501_KC | 2.5 | %/% |
| $T_i$ (LIC-322501) | LIC_322501_TI | 90 | s |

### 6.5 HPCC 322E002 & Bubble-Point
| Symbol | Code Name | Value | Unit |
|---|---|---|---|
| $\Delta H_{vap}$ | HPCC_BUB_DHVAP_JMOL | 23,000 | J/mol |
| $K_N$ | HPCC_BUB_KN | +0.18 | 1/(N/C) |
| $K_W$ | HPCC_BUB_KW | −0.25 | 1/(H/C) |
| $\Delta H_{carb}$ | HPCC_DH_CARB_KJMOL | 160 | kJ/mol |
| $c_{p,gas}$ | HPCC_CP_GAS | 2.0 | kJ/kg·K |
| $\lambda_{4.4\,bar}$ | HPCC_LATENT_4BAR | 2120 | kJ/kg |
| $\tau_{fill}$ | HPCC_TAU_FILL_MIN | 6.0 | min |
| NLL | HPCC_LEVEL_NLL_PCT | 50 | % |

### 6.6 Synthesis-Loop Pressure Dynamics
| Symbol | Code Name | Value | Unit |
|---|---|---|---|
| $P_{des}$ | SYN_P_DES_BARA | 140.7 | bar a |
| $K_P$ | SYN_P_COUPLING | 1.0 | — |
| $K_{def}$ | SYN_P_DEFICIT_GAIN | 0.30 | bar/bar |
| $\tau_P$ | SYN_P_TAU_MIN | 4.0 | min |
| $P_{min}$ | SYN_P_MIN_BARA | 120 | bar a |
| $P_{max}$ | SYN_P_MAX_BARA | 175 | bar a |

### 6.7 CO₂ Feed Line
| Symbol | Code Name | Value | Unit |
|---|---|---|---|
| $\dot m_{CO_2,des}$ | CO2_DES_KGH | 54,618 | kg/h |
| $\dot n_{CO_2,des}$ | CO2_DES_KMOLH | 1,264 | kmol/h |
| MW (stream) | CO2_FEED_MW | 43.21 | g/mol |
| $\rho$ | CO2_RHO | 242.70 | kg/m³ |
| $T_{feed}$ | CO2_T_FEED_C | 120 | °C |
| $P_{des}$ | CO2_P_DES_BARA | 144.2 | bar a |
| Max vent fraction | CO2_VENT_MAX_FRAC | 0.15 | — |
| PV ΔP gain | CO2_PV_DP_GAIN | 0.25 | bar/% |
| Nm³/kmol | NM3_PER_KMOL | 22.414 | Nm³/kmol |

### 6.8 Scrubber 322E003 & CCW
| Symbol | Code Name | Value | Unit |
|---|---|---|---|
| $\dot m_{ccw,des}$ | SCRUB_CCW_KGH_DES | 306,000 | kg/h |
| $c_{p,w}$ | SCRUB_CCW_CP | 4.18 | kJ/kg·K |
| $T_{ccw,in}$ | SCRUB_CCW_T_IN_DES | 80 | °C |
| $T_{ccw,out}$ | SCRUB_CCW_T_OUT_DES | 95 | °C |
| $Q_{ccw,des}$ | SCRUB_Q_CCW_DES_KW | ~5,329 | kW |
| $\mu_{JT}$ | SCRUB_HV604_MU_JT | 0.55 | °C/bar |
| $\Delta H_{carb}$ | SCRUB_DH_CARB_KJMOL | 160 | kJ/mol |
| FV-329409 des opening | SCRUB_FV409_DES_PCT | 60 | % |
| TV-329005 des opening | SCRUB_TV005_DES_PCT | 50 | % |
| HIC-322604 des opening | SCRUB_HIC604_DES_PCT | 50 | % |

### 6.9 LV-322501 Control Valve
| Symbol | Code Name | Value | Unit |
|---|---|---|---|
| $K_{vs}$ | LV322501_KVS | 36.0 | m³/h |
| Design opening | LV322501_OPEN_DES | 82 | % |
| Design ΔP | LV322501_DP_DES_BAR | 139.8 | bar |
| $P_{downstream}$ | STRIP_P_DOWN_BARA | 4.2 | bar a |

---

## PART F — Full-Loop Turndown Multi-Settle Audit (100 % → 70 %)

**Date:** 2026-06-22 · **Harness:** `backend/tests/run_turndown_envelope.py` · **Commit:** `a0a9180`
**Scope:** integrated HP synthesis loop 322R001 + 322E001 + 322E002 + 322E003 + 322F001, settled at 7 load setpoints. Settle = 60 sim-min/point ($\text{SETTLE\_TICK}=36000$, $\Delta t = 0.1$ s); convergence sampled over the final $\text{CONV\_WIN}=1000$ ticks. Cross-reference: `backend/reports/FULL_AUDIT_REPORT.md` PART F.

### F.1 Actuation — proportional turndown (design-anchored)
Both feeds scaled by the same fraction $\text{frac}\in\{1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70\}$ each tick:
$$\dot m_{CO_2,raw} = \text{frac}\times 54.618\ \text{t/h}, \qquad \text{SIC-321951}.set\_op(86.2\times\text{frac})\ \%\ (\text{pump-B opening, MAN})$$
$$s.\text{tank\_level\_frac} = \text{tank\_pin}\ (\text{continuous-makeup} \Rightarrow \text{trip 21\_2 dormant})$$
MAN opening-scaling was chosen over CAS ratio control: CAS settles pump-B to $O_{act}=82.147$ (not the design 86.2), breaking the anchor (CAS @100 %: $f_{cons}=0.96226$, closure $=-142.733$ vs MAN baseline $f_{cons}=0.97571$, closure $=+6.986$). MAN @frac=1.0 reproduces the verified design baseline $f_{cons}=0.97571$ bit-identical. Reactor N/C (AT-322701) holds **3.0000 at every load** ⇒ true proportional turndown (recycle-inclusive N/C, not the fresh-feed ratio.PV $= 2.0231$).

### F.2 Global mass conservation — `f_cons` and the decisive metric
`f_cons` is the reactor-overflow mass-rescale factor inside `react_322r001` (LOCAL, never telemetered; reconstructed bit-identically in the harness spy):
$$f_{cons} = \frac{m_{ov}^{tgt}}{m_{ov}^{pre}}, \qquad m_{ov}^{tgt} = m_{ov,des} + (m_{feed} - m_{feed,des}) - (m_{og} - m_{og,des}), \qquad m_{ov}^{pre} = m_{ov,des}\cdot s\cdot\frac{\phi}{\phi_{des}}$$
Design pins (live at module import):
$$\text{REACT\_MASS\_DES} = (m_{feed,des},\ m_{ov,des},\ m_{og,des}) = (253486.24766399845,\ 226177.627954,\ 22354.6374)\ \text{kg/h}$$
With $\phi/\phi_{des}=1$ and $\text{co2\_scale}=\text{frac}=s$, the numerator collapses onto a standing pin residual:
$$m_{ov}^{tgt} = m_{feed} - m_{og} + (m_{ov,des} - m_{feed,des} + m_{og,des}) = m_{feed} - m_{og} + (226177.627954 - 253486.24766399845 + 22354.6374)$$
$$= m_{feed} - m_{og} - 4953.98231\ \text{kg/h} \;\Rightarrow\; f_{cons} = \frac{m_{feed} - m_{og} - 4954}{s\cdot m_{ov,des}}$$
The fixed $-4954$ kg/h is the pre-existing design-pin mass-closure residual. As $s$ shrinks it becomes a larger fraction of a shrinking overflow, and $m_{ov}^{pre}$ is forced linear in $s$ while the pumped feed scales sub-linearly (opening 0.70 → flow ≈ 0.62). Hence $f_{cons}$ sags 0.9757 → 0.8426 **without any mass loss.**

**Proof — `clos_abs` (post-rescale absolute non-closure):**
$$\text{clos\_abs} = \frac{m_{ov}^{post} - (m_{feed} - m_{og})}{1000} = -4.9540\ \text{t/h at } \{100, 95, 90, 85, 80, 75, 70\}\,\% \quad (\text{span}=0.0000)$$
Invariant across the whole envelope ⇒ no new mass created or destroyed during turndown. The `f_cons` sag is pure arithmetic of a fixed offset over a shrinking overflow, not a leak. **No model fix applied** (Iron Law: root-caused, behaves as designed).

### F.3 Envelope Closure Table

| Load % | frac | AT-322701 (N/C) | $f_{cons}$ | clos_abs t/h | TT-322014 °C | dTT014/100 s |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 1.00 | 3.0000 | 0.97569 | −4.9540 | 183.1 | <0.05 (OK) |
| 95 | 0.95 | 3.0000 | 0.95022 | −4.9540 | 177.8 | <0.05 (OK) |
| 90 | 0.90 | 3.0000 | 0.92467 | −4.9540 | 173.8 | 0.2 (tail) |
| 85 | 0.85 | 3.0000 | 0.90197 | −4.9540 | 170.7 | 0.2 (tail) |
| 80 | 0.80 | 3.0000 | 0.88141 | −4.9540 | 168.3 | 0.3 (tail) |
| 75 | 0.75 | 3.0000 | 0.86175 | −4.9540 | 166.5 | 0.4 (tail) |
| 70 | 0.70 | 3.0000 | 0.84264 | −4.9540 | 164.5 | 0.4 (tail) |

$f_{cons}$ span $[0.842642, 0.975692]$; clos_abs span $[-4.9540, -4.9540]$ (span $= 0.0000$); reactor T span $[164.50, 183.10]$ °C (runaway guard 230 °C never approached); N/C span $[3.0000, 3.0000]$.

### F.4 Per-Unit Steady Response (100 % → 70 %)

| Unit | Indicator | 100 % | 70 % | Behaviour |
|---|---|---:|---:|---|
| 322R001 | X_conv % / TT-322014 | 54.6 / 183.1 | 53.9 / 164.5 | conversion ~flat; reactor cools (lower exotherm density) |
| 322E001 | TT-322004 / $\eta_T$ | 172.8 / ~1.04 | 192.5 / ~1.04 | bottom T rises toward steam sat (low-feed flood branch) |
| 322E002 | LT-322E002 % | 45.2 | 57.3 | level swells as vapour load drops ($\phi_m^2$ forward flow) |
| 322E003 | LT-329501 / TDY-329125 | 47.6 / 15.08 | 47.6 / 10.74 | level held; condensation duty scales down |
| 322F001 | $\mu$ / total_th | 1.346 / 100.33 | 1.346 / 70.23 | entrainment ratio invariant; throughput scales with motive |

PT-329201 = 141.5 bar a @100 % → mild rise at turndown (less CO₂ consumption). All responses monotone, physical, design-consistent.

### F.5 Guards & One Open Item
- **Thermal runaway:** none. Reactor T monotone-decreasing 183.1 → 164.5 °C, bounded well below the 230 °C gate.
- **Vanishing mass:** none. $f_{cons}\in(0.5, 1.5)$ throughout; overflow positive (220.7 → 133.4 t/h); clos_abs flat.
- **Trip 21_2:** dormant (continuous-makeup pin).
- **OPEN — low-load thermal tail:** loads ≤90 % retain residual dTT-322014 $= 0.2$–$0.4$ °C over the final 100 s (was 0.7 at 30-min settle; halved at 60-min). Decelerating, monotone, non-oscillatory — the ≈ $1/\text{throughput}$ residence-time stretch at reduced load. Mass/level/pressure states dead-flat alongside (dfcons $= 0.000000$, clos_abs constant). Converged for engineering purposes; clearing the last 0.4 °C would need ~150 min/point for no physical gain.

### F.6 Verdict
**ENVELOPE CLOSED.** Loop converges smoothly 100 % → 70 %; global mass conserved (clos_abs flat at the standing design-pin residual, zero new loss); no un-gated thermal runaway; no vanishing mass; reactor N/C locked at design 3.0000 (true proportional turndown). No new model defect surfaced. The previously verified Phase A (off-gas liquid carryover) and Phase B (ejector hydraulic-capacity ceiling) couplings were exercised in the full loop without regression.

---

## Revision Delta #20 — 322E001 per-species enthalpy balance, derived flooding knockdown, live $\eta_P$ (2026-07-23)

### 20.1 The duty was blind to composition

Superseded form — duty proportional to feed **mass**:

$$Q_{strip} = Q_{des}\cdot\frac{\dot m_{feed}}{\dot m_{feed,des}}$$

Identical tonnages of pure water and of carbamate-rich reactor liquor therefore demanded identical
steam, and the largest heat sink in the unit was invisible to the MP header. Replaced by a
five-term balance, every constant sourced:

$$Q_{raw} = \underbrace{n_{CO_2}^{des}\,\Delta H_{carb}}_{\text{dissociation}}
          + \underbrace{n_{NH_3}^{free}\,\Delta H_{NH_3}}_{\text{desorption}}
          + \underbrace{n_{H_2O}^{top}\,\lambda_{H_2O}}_{\text{latent}}
          + \underbrace{\xi_{hyd}\,\Delta H_{hyd}}_{\text{hydrolysis}}
          + \underbrace{\dot m_{bot}c_{p,b}(T_b-T_f)+\dot m_{top}c_{p,g}(T_t-T_f)}_{\text{sensible}}$$

with $n_{CO_2}^{des}=y_{CO_2}^{top}-y_{CO_2}^{sweep}$ — the CO₂ sweep enters already as gas and
needs no dissociation heat — and $n_{NH_3}^{free}=y_{NH_3}^{top}-y_{NH_3}^{sweep}-2\,n_{CO_2}^{des}$
from the 2:1 carbamate stoichiometry.

**Constants.** Frejacques, quoted in Brouwer, *Thermodynamics of the Urea Process*, UreaKnowHow
Process Paper June 2009 p.12, at **process** conditions rather than the 25 °C standard state:
$\Delta H_{carb}=+117$ kJ/mol (110 atm, 160 °C) and $\Delta H_{hyd}=-15.5$ kJ/mol (160–180 °C).
NH₃ is supercritical at stripper temperature ($T_c=132.4$ °C), so $\Delta H_{NH_3}$ is a
*desorption* enthalpy — the loop's own `HPCC_BUB_DHVAP_JMOL` — and not a latent heat at all.

**Validation.** The five terms summed over the design streams, with nothing fitted and no free
parameter, give $37\,831$ kW against the licensor's $Q_{des}=39\,400$ kW — **96.0 %**. Only the
ratio is applied:

$$Q_{strip} = Q_{des}\cdot\frac{Q_{raw}}{Q_{raw,des}},\qquad
\left.\frac{Q_{raw}}{Q_{raw,des}}\right|_{des} = \frac{X}{X} = 1.0\ \text{(bit-exact)}$$

so the 4 % absolute offset cancels, never reaches the steam header, and the PFD duty remains the
anchor rather than a computed quantity.

| term | kW | share |
|---|---:|---:|
| carbamate dissociation | 22 118 | 58 % |
| free-NH₃ desorption | 14 123 | 37 % |
| water latent | 2 803 | 7 % |
| urea hydrolysis (liquid step) | −379 | — |
| sensible, both products | −834 | — |

### 20.2 The unsourced constant, retired

Delta #19 flagged `STRIP_FLOOD_ETA_K = 1.50` as the single number in the unit without a source. It
required no replacement constant, because $\Delta T_{flood}$ and the efficiency loss are the same
event measured two ways — the bottom runs hotter *precisely because* the dissociation endotherm did
not happen:

$$g_{flood} = 1 - \frac{\dot m_{feed}\,c_p\,\Delta T_{flood}}{n_{carb}\,\Delta H_{carb}}$$

$\Delta T_{flood}\equiv 0.0$ below the flooding limit, so $g_{flood}\equiv 1.0$ at design — a
structural identity, not a float-operand-ordering argument. Cross-checks at 10 % over the limit:
this energy balance **2.9 %**, Brouwer's Shangdong Hualu Hengsheng case study (a 3 °C bottom-
temperature shift alongside a 79 % → 81 % efficiency change) **2.5 %**, and the licensor length
correlation from the same paper (6 m eff. → 80 %, 8 m → 82 %) **0.8 %** — against **15 %** from the
retired fit, which was additionally double-counting the thermal collapse $g_T$ already carries.

### 20.3 $\eta_P$ — a dead lever

$\eta_P = \mathrm{clamp}\!\left(2-P/P_{des},\,0.85,\,1.15\right)$ was recomputed on every tick from
an argument that every call site passed as the frozen $P_{des}$. It was therefore identically 1.0,
and synthesis pressure had **no** effect on stripping efficiency — physically wrong, and invisible
to the pin gate precisely because a dead lever perturbs nothing. Now

$$P_{live} = P_{des}\cdot\frac{p_{syn}}{p_{syn,des}}$$

which is exactly $P_{des}$ at design since $p_{syn}\equiv p_{syn,des}$ there. Gated on
`_STEAM_READY` exactly as `step_steam` is: the fix introduces a feedback path that did not
previously exist, and the boot-pin settle would otherwise capture `HPCC_UA` and `HPCC_LIQ_DES_LIVE`
off a different transient (measured +305 kg/h, 0.16 %). Those are *calibration* constants; they
must not depend on which transient reached the design point.

---

## Revision Delta #21 — C10 urea-solution properties, and the ripple break (2026-07-23)

### 21.1 Properties as a departure from the anchor

Both correlations are applied as a *departure*, never as an absolute. That is what preserves every
licensor-published design value to the bit:

$$\phi(w,T) = \phi_{anchor} + \big[\phi_{raw}(w,T) - \phi_{raw}(w_{des},T_{des})\big]$$

At the design composition the bracket is a literal $0.0$, and $\phi_{anchor}+0.0=\phi_{anchor}$
exactly in IEEE-754.

**Heat capacity — back-solved, not guessed.** With $c_{p,w}$ from steam tables (quadratic least
squares over 20–200 °C, worst residual 0.0085 kJ/kg·K), $c_{p,u}$ follows from requiring the
mass-weighted mixing rule to reproduce the model's own design anchor:

$$c_{p,u} = \frac{c_{p,des} - (1-w_{des})\,c_{p,w}(T_{des})}{w_{des}} = 2.072\ \text{kJ/kg·K}$$

The published value for molten urea is 2.0–2.1 kJ/kg·K. Nothing in the derivation forced the answer
to be physical, so that agreement is an *independent* corroboration rather than a restatement. The
solution property is then $c_p(w,T)=w\,c_{p,u}+(1-w)\,c_{p,w}(T)$.

**Density — regressed from the PFD**, which §0 makes the strict source (12 urea-solution streams,
34–98 % urea, 40–183 °C):

$$\rho = 972.08 + 255.95\,w_{urea} - 0.4659\,(T-100)\quad\text{kg/m}^3$$

Both signs came *out* of the regression rather than being imposed — denser with urea, thinner when
hot — which makes the fit its own evidence. Worst residual 6.2 %, on streams 207 and 208, the HP
synthesis streams carrying dissolved NH₃/CO₂ that are not urea/water binaries at all.

**Unit 324** now evaluates $c_p$ at each location's own composition — feed 80 %, Stage-1 melt
94.31 %, Stage-2 melt 97.71 % — where a single 2.5 kJ/kg·K previously ran 14–18 % high at the
evaporator ends and 23 % low at the LP end. The *feed* $c_p$ appears in both the back-solved design
duty and the tick and was changed in both, so $dT/dt=0$ still holds at the seed **by construction**.
The *holdup* $c_p$ enters only as the denominator of the temperature ODE, where the design numerator
is exactly 0 — so no value of it can move the fixed point, only the speed of approach.

### 21.2 The ripple break

$$\text{was:}\quad w_{D002} \leftarrow \mathrm{pin}\big(\mathrm{advance}(\cdot),\ W_{IN}\big)
\qquad\Longrightarrow\qquad w^{urea}_{D002} \equiv 0.80\ \text{on every tick}$$

The 323D002 tank strength was pinned to the **constant** $W_{IN}$, so `sol_pin_strength` overwrote
the urea/water pair each tick and every upstream composition disturbance died in the buffer tank.
Measured: a +4 % NH₃ step on the live reactor overflow (water traded down, total moles held) moved
222 of 1162 telemetry leaves — and **0 of unit 324's 66**. The block's own comment claimed it gave
324 "a real composition instead of a constant"; the next line took it away.

The pin retains its §0 job — holding the PFD-published strength against percentage-rounding creep
across 324E001/E003 — but now carries the live deviation rather than overwriting it:

$$w_{auth} = W_{IN} + \big(w^{urea}_{bal} - w^{urea}_{bal,des}\big)$$

which is exactly $W_{IN}$ at the seed. With it, 246 leaves respond and **every unit group in the
train** does, unit 324 included at 13 of 66, first responding at tick 39 — the 80 m³ buffer-tank
holdup lag, which is physically correct.

**This change was REVERTED, and the reason is the finding.** It also drove $w^{urea}_{D002}$ to
76.515 % against the PFD stream-317 anchor of 80.00, failing four design-point tests. The pin is
documented as a guard against *residual percentage rounding* — 3.5 points is not rounding. The 323
train's mass balance does not land on 80.00, and the pin has been silently absorbing the gap. So
the ripple break is a **symptom**: un-freezing the pin without first reconciling the upstream
balance merely trades a hidden composition error for a visible one, and violating §0 at the design
point is the worse trade. Carried as **TD-013**; the 323 balance is the place to start. It stayed
hidden because Comp-I holdup is ~92 t against ~93 t/h, so the tank's time constant is about an hour
and no test in the suite runs long enough to watch it converge.

---

*End of Document — Urea OTS As-Built Mathematical & System Architecture Reference. All equations sourced from `backend/main.py`, `backend/reactor.py`, `backend/steam_system.py`, `backend/controllers.py`. Post-2026-06-05 model deltas itemised in the Revision Delta; full audit math in `backend/reports/FULL_AUDIT_REPORT.md`.*
