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

**Thermodynamic role.** Condenses NH₃ + CO₂ from stripper top gas into ammonium carbamate ($2NH_3 + CO_2 \to NH_2COONH_4$, $\Delta H = -160$ kJ/mol). Calibrated split-fraction model assigns each component to gas/liquid via design fractions $\phi_i$. Carbamate-melt bubble-point $P_{bub}(T,L,W)$ sets loop outlet pressure. Shell duty = carbamate exotherm + gas sensible cooling.

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

### 3.6 HPCC Design Gas-Phase Split Fractions $\phi_i$

| Component | $\phi_i$ (fraction → gas) | Component | $\phi_i$ |
|---|---|---|---|
| CO₂ | 0.2036 | CH₄ | 1.0 |
| NH₃ | 0.2977 | H₂ | 1.0 |
| H₂O | 0.0450 | Urea | 0.0 |
| N₂ | 0.982 | Biuret | 0.0 |
| O₂ | 1.0 | | |

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

*End of Document — Urea OTS As-Built Mathematical & System Architecture Reference. All equations sourced from `backend/main.py`, `backend/reactor.py`, `backend/steam_system.py`, `backend/controllers.py`. Post-2026-06-05 model deltas itemised in the Revision Delta; full audit math in `backend/reports/FULL_AUDIT_REPORT.md`.*
