# Closure Plan for Open Simulation Gaps — 1750 MTPD CO?-Stripping Urea Plant

**Prepared:** 2026-07-31
**Input:** `handoff.md` ("Open Simulation Gaps Only", updated 2026-07-31) — sole project document supplied
**Method:** open-literature research pass + first-principles diagnosis
**Gaps addressed:** G1, G2, G4, G6, G9

---

## 0. Scope, method, and ground rules

### 0.1 What I had and did not have

| Available | Not available |
|---|---|
| The handoff file as attached | `References/Combined_1750_MTPD_100% load_PFD Tables…md` (strict source) |
| Open literature (searched 2026-07-31) | `FULL_SIMULATION_EXTENDED_UNIQUAC_AUDIT_2026-07-29.md` |
| | `Strategic Resolution of Thermodynamic and Topological Simulation Gaps…md` |
| | The codebase (`backend/main.py`, `props_nh3co2h2o.py`, `thermo_extended_uniquac.py`, `gap_g2_vacuum_vle_refit.py`) |
| | Vendor datasheets, P&IDs, licensor design point |

Everything below is therefore reasoned from the handoff's own statements plus published sources. Where a recommendation depends on something in the code or PFD that I cannot see, it is marked **[VERIFY IN REPO]**.

### 0.2 Tagging convention used throughout

- **[V]** — Verified: traceable to a cited published source or to an arithmetic check I performed and show.
- **[I]** — Inference: my engineering reasoning from [V] facts. Defeasible.
- **[A]** — Assumption: taken as true for the plan to proceed; must be confirmed.
- **[X]** — Cannot confirm: stated so explicitly rather than guessed.

No numeric value appears below unless it is either cited to a source or derived in a calculation shown in full. Nothing is fabricated to make a gap look closed — consistent with the handoff's own prohibition.

---

## 1. Executive summary

Four of the five gaps are **not blocked by the data the handoff identifies as blocking**. In three cases the blocker is an artefact of the *proposed solution method* rather than of the physics; changing the method dissolves the blocker. One gap (part of G9) is genuinely data-gated and stays open.

| Gap | Handoff's stated blocker | Finding | Revised status |
|---|---|---|---|
| **G1** | Urea/ion reactive Extended-UNIQUAC parameters + licensor HP design point | The published Thomsen–Rasmussen parameter set is **valid only to 110 °C and 100 bar** [V] — it cannot be the plant-wide HP model regardless of what parameters arrive. A different published model (Voskov–Voronin 2016) covers *exactly* the HP envelope with **fully published parameters** [V], and a **published validation grid** replaces the licensor design point for model validation [V]. | **Unblocked** — re-scope to a tiered property architecture |
| **G2** | Independent ebulliometric urea–water VLE at 130–140 °C, 90–99 wt% | The two design points **straddle the urea melting point (132.7 °C, verified two ways)** [V]. The error is 74× larger below the melt line than above it [V]. This is a reference-state signature, not a binary-parameter shape problem. Also, the melt is not a binary: it contains biuret and the vapour carries NH?/CO? [V]. | **Unblocked** for the dominant error term; residual refinement stays data-gated |
| **G4** | Blocked on G1 | Correct dependency, but a **fully published, plant-validated architecture** exists for exactly this technology (CO? stripping with pool condenser), with reproducible kinetics [V]. Biuret kinetics independently re-derived and confirmed here [V]. | **Unblocked** once G1 Tier A lands; template supplied |
| **G6** | Live enthalpy blocked on G1 | Static 163-row catalogue is executable now (agreed). The live-enthalpy half is **only partly** blocked: the absolute enthalpy datum (?_fH° + Cp + phase change) is fully available from published data [V]; only the excess term H^E needs G1. Use declared quality tiers. | **Partially unblocked** — publish tiered enthalpy now |
| **G9** | Second ejector duty point; valve Cv; Unit-335 P&ID | Ejector half: **three independent physics constraints** are available without vendor curves, giving a *bounded* pull-curve envelope rather than an unconstrained fit [V]. A second duty point may already exist in the DCS historian at a different plant load [I]. Unit 335 and valve Cv remain genuinely gated. | **Ejectors partially unblocked**; Unit 335 **stays open** |

---

## 2. Cross-cutting findings

These three findings reshape more than one gap and should be read before the gap-by-gap sections.

### F1 — The liquid-phase model family in the plan is mis-specified for the HP loop

**[V]** The Thomsen & Rasmussen (1999) Extended-UNIQUAC + SRK parameter set — the basis of `props_nh3co2h2o.py` — is published with parameters *"valid in the temperature range 0–110 °C, the pressure range from 0–100 bar"* and up to roughly 80 molal ammonia [S1, S2].

**[V]** The HP synthesis loop of a CO?-stripping plant operates at roughly 170–200 °C and 125–250 bar; the reference Aspen deck for this technology holds a reactor outlet near 183 °C [S3, S8].

**[I]** The HP loop therefore sits **60–90 K above and 40–150 bar beyond** the published validity envelope of that parameter set. "Plant-wide Extended UNIQUAC" as G1 states it is not attainable with the published parameters *no matter which urea parameters are later regressed*, because the ionic NH?–CO?–H?O sub-model itself is being extrapolated. The handoff's own honesty rule applies to this extrapolation exactly as it applies to G2's.

**[V]** Voskov & Voronin (2016) published a thermodynamic model of NH?–CO?–H?O–urea whose stated domain is *t* = 135–230 °C, *p* = 3.5–45 MPa, L = n_N/n_C = 2–5.5, W = n_O/n_C ? 2 = ?0.75 to 1.2 [S4]. That is the HP synthesis envelope, and the HFC loop sits inside it.

**[V]** Critically, Voskov & Voronin deliberately used the **non-electrolyte (molecular) UNIQUAC**, not the electrolyte form, giving three reasons: the electrolyte form needs more parameters than the available data support; there are no dielectric-constant data for the NH?–H?O–urea mixed solvent at synthesis conditions (urea hydrolyses and ammonia is supercritical there); and equilibrium constants are simpler to use for molten compounds [S4]. Their liquid phase is six *neutral* constituents — NH?, CO?, H?O, urea, ammonium carbamate, ammonium bicarbonate — coupled by three reactions [S4].

**[I]** This is a peer-reviewed argument *against* the specific route G1 proposes (electroneutral ionic speciation with Debye–Hückel plus a Huron-Vidal/MHV2-coupled SRK) for the HP loop. The Debye–Hückel term needs the solvent dielectric constant; that datum does not exist for this mixture at these conditions. G1's "blocking datum" is blocking because the plan asks for a parameter set nobody has regressed and cannot regress from available data.

**[V]** Voskov & Voronin also handle pressure without any mixing-rule surgery: the standard-state Gibbs energy of vaporisation carries a Poynting term ?_vG(p,T) = ?_vG(p?,T) + V_m,i(p ? p?), with molar-volume temperature polynomials given in the paper [S4]. The vapour phase uses the Voronin et al. (2015) virial EoS for NH?–CO?–H?O, stated valid for T = 423–573 K and p = 0.1–28 MPa, and reported as substantially more accurate than the Nakamura EoS commonly used in urea models [S4].

**Consequence:** G1 should become a **tiered property architecture**, not one universal model. See §3.

### F2 — Validation data assumed proprietary is already public

**[V]** Voskov & Voronin publish a calculated validation grid: equilibrium CO??urea conversion (their Table 8) and equilibrium bubble-point pressure (their Table 9), each across L = 2.5–5.5 and W = 0.0–1.0 at 160, 180 and 200 °C, with stated expanded uncertainties U(Y_CO?) = 0.03 and U(p) = 0.1 MPa [S4]. Model-vs-experiment performance is reported as 2.5 % standard / 7.5 % maximum absolute deviation on conversion and 0.89 MPa standard / 3.8 MPa maximum on bubble point [S4]. They further reproduce the saddle azeotrope measured by Lemkowitz et al., with tabulated calculated-vs-experimental coordinates at 160 and 180 °C [S4].

**[I]** A thermodynamic property package can therefore be **validated to publishable standard without the licensor's 100 %-load design point**. The licensor point is needed for *plant-specific reconciliation* — matching this reactor's actual approach to equilibrium, tray efficiency and heat losses — which is a different and later task. G1's acceptance criterion currently conflates the two, which is why it reads as blocked.

**[V]** The paper's Supporting Information contains the MATLAB/C++ source required to reproduce both the virial EoS and the parameter optimisation [S4].

### F3 — Reference-state discipline is the hidden failure mode

Both G1 and G2 show symptoms of standard-state handling rather than of missing interaction parameters. Two independent published datasets agree on urea's fusion properties, and the arithmetic is worth showing because it is the crux of G2.

**From Tischer et al. (2019), Table 2** [S5]: urea(s) ?_fH° = ?333.599 kJ/mol, S° = 105.9 J/(mol·K); urea(l) ?_fH° = ?319.7 kJ/mol, S° = 140.15 J/(mol·K), both with c_p = 93 J/(mol·K).

```
?_fusH(298.15) = ?319.7 ? (?333.599)   = 13.899 kJ/mol
?_fusS(298.15) = 140.15 ? 105.9        = 34.25  J/(mol·K)
?c_p = 0  ?  T_fus = 13 899 / 34.25    = 405.8 K = 132.7 °C
```

The paper independently states the two Gibbs-energy curves intersect at 133 °C [S5]. ?

**From Voskov & Voronin (2016), Table 2** [S4]: urea(s) ?_fH° = ?332.753 kJ/mol, S° = 104.6, c_p coefficient a = 253.64; urea(l) ?_fH° = ?321.827 kJ/mol, S° = 130.0, a = 287.59 J/(mol·K).

```
?_fusH(298.15) = 10.926 kJ/mol ,  ?_fusS(298.15) = 25.40 J/(mol·K) ,  ?c_p = 33.95 J/(mol·K)

Ignoring ?c_p:  T_fus = 10 926 / 25.40 = 430.2 K = 157.0 °C     ? wrong by 24 K
Including ?c_p, solving ?_fusH(T) ? T·?_fusS(T) = 0 with
  ?_fusH(T) = ?_fusH(298) + ?c_p (T ? 298.15)
  ?_fusS(T) = ?_fusS(298) + ?c_p ln(T/298.15)
              ? T_fus = 406.5 K = 133.4 °C                       ? matches
```

**[V]** Two independent datasets converge on T_fus(urea) ? 132.7–133.4 °C. **[I]** Dropping the ?c_p term moves the predicted fusion line by 24 K — which is larger than the entire 10 K span between the two evaporator stages. Any property routine that mishandles this in the 130–140 °C window will produce large, temperature-localised errors that look exactly like bad interaction parameters.

---

## 3. G1 — Runtime reactive thermodynamics

### 3.1 Restatement of the gap

Correct as written: the property core exists but the HPCC, reactor, stripper, scrubber, LP absorber and 328 columns still run on calibrated splits, and urea is absent from the reactive runtime phase set.

### 3.2 What changes

Replace "one universal Extended-UNIQUAC MESH boundary" with **three declared property tiers plus one enforced interface contract**. Each tier is used only inside its published domain; the interface carries apparent composition and a common enthalpy datum.

| Tier | Section / tags | Model | Published domain | Source |
|---|---|---|---|---|
| **A** | HP synthesis loop (322 R001, E001–E003, F001) | Molecular UNIQUAC, 6 neutral constituents, 3 liquid-phase reactions + Voronin virial EoS | 135–230 °C, 3.5–45 MPa (liquid); 423–573 K, 0.1–28 MPa (vapour) ? **use the intersection: 150–230 °C, 3.5–28 MPa** | [S4] |
| **B** | LP/MP recovery, absorbers, desorbers, 328 columns | Extended UNIQUAC (Thomsen/Darde) + SRK, ionic speciation, Debye–Hückel | 0–110 °C, 0–100 bar, ? ~80 m NH? | [S1, S2] |
| **C** | 324 evaporation / vacuum, 335 melt | Urea-melt model — see G2 (§4) | 130–140 °C, 0.13–0.33 bar(a) | §4 |

**Interface contract (the actual integration engineering).** Tier A speciates into neutral constituents; Tier B speciates into ions. They cannot exchange speciated compositions. Streams crossing a tier boundary must be handed over as **apparent (elemental / component) composition** — total NH?, CO?, H?O, urea, biuret, inerts — with each tier re-speciating on entry. Enforce:

1. **Common enthalpy datum.** All tiers reference elements at 298.15 K, 1 bar. Non-negotiable — without it, energy is created or destroyed at every tier boundary. This is also the G6 datum (§6).
2. **Atom conservation across the handover.** C, H, N, O closure to solver tolerance, asserted in code at every boundary, not merely at unit level.
3. **Domain flag propagation.** Every call returns `{model_id, domain_status, residual}`. A call outside its tier's published envelope returns `DOMAIN_EXCEEDED` and must not be silently accepted. The existing `DESIGN_ANCHORED_EXTRAPOLATION` marker is the right pattern — generalise it.

### 3.3 Implementation sequence (Tier A)

1. **Constituent thermochemistry.** Load ?_fH°(298.15), S°(298.15) and the c_p(T) forms for NH?(ig), CO?(ig), H?O(ig), H?O(liq), urea(s/liq), NH?COONH?(s/liq) from [S4, Tables 1–2]; biuret and by-products from [S5, Table 2]. Note that the Berman–Brown-type `e·T^?0.5` term is used for urea and carbamate and must be carried [S4].
2. **Reactions.** Three liquid-phase reactions in the neutral basis [S4]:
   - (I) 2 NH?(l) + CO?(l) ? urea(l) + H?O(l)
   - (II) 2 NH?(l) + CO?(l) ? NH?COONH?(l)
   - (III) NH?(l) + CO?(l) + H?O(l) ? NH?HCO?(l)
   K_I and K_II come from the Gibbs energies of the constituents; K_III is a two-parameter correlation because liquid NH?HCO? properties are unknown [S4].
3. **Activity model.** Standard UNIQUAC with temperature-dependent binary parameters ?_ij = exp(?a_ij/T), a_ij = a_ij^(0) + a_ij^(1)(T ? T_ref); r_i and q_i for the six constituents in [S4, Table 3]; a_ij^(0) and a_ij^(1) in [S4, Tables 6–7]. Electrolyte constituents take r = r? + r?, q = q? + q? using Thomsen's ion parameters as group contributions [S4] — this is the legitimate bridge between the existing Tier B code and Tier A.
4. **Speciation solve.** Six unknowns ?_i = ln x_i, solved in logarithmic coordinates by Levenberg–Marquardt; the log substitution is stated as necessary for stable convergence [S4]. **[VERIFY IN REPO]** whether the existing speciation solver uses log coordinates — if not, this alone may explain convergence pathologies.
5. **VLE.** Equality of chemical potentials with the virial fugacity coefficient and the Poynting-corrected ?_vG [S4]. CO? uses a Henry's-constant (unsymmetric) reference; NH? and H?O use pure-liquid references.
6. **Urea is not in the vapour phase.** [V] Extrapolated urea vapour pressure at 453 K is ? 435 Pa, ? 5 × 10?? of the loop pressure [S4]. Exclude urea and ionic species from the vapour and record the justification. This removes a requirement, not a capability.

### 3.4 Revised acceptance criteria for G1

Replace the current single criterion with four separable ones:

- **A1 (thermodynamic validity).** Tier A reproduces the published conversion grid to within the paper's own reported deviation (2.5 % standard, 7.5 % maximum on Y_CO?) and the bubble-point grid to within 0.89 MPa standard / 3.8 MPa maximum [S4]. **No licensor data required.**
- **A2 (structural).** Tier A reproduces the saddle azeotrope coordinates at 160 and 180 °C within the published confidence intervals [S4]. This is a strong structural test — a model can hit conversions and still get the topology wrong.
- **A3 (interface).** Every tier-boundary handover closes C/H/N/O and total enthalpy to solver tolerance.
- **A4 (plant reconciliation).** Deviation from the licensor 100 %-load design point is reported as a *bias*, not corrected away. **This one remains user-supplied and stays open.**

### 3.5 What is still blocked in G1

**[V/X]** The licensor 100 %-load HP design point — for A4 only. Nothing else. **[I]** The multi-week scope estimate in the handoff stands; the tiering does not shrink the work, it makes it converge on a defensible target instead of an unreachable one.

---

## 4. G2 — Unit-324 vacuum extrapolation

This is the gap where the diagnosis changes most.

### 4.1 The handoff's own evidence, re-read

The handoff records: at 130 °C / 0.33 bar the model gives ? 0.9209 urea mass fraction against a PFD value of 0.9431; at 140 °C / 0.131 bar it gives ? 0.9768 against 0.9771.

```
Stage 1 (324E001/F001): 130 °C — error = 0.9209 ? 0.9431 = ?2.22 percentage points
Stage 2 (324E003/F003): 140 °C — error = 0.9768 ? 0.9771 = ?0.03 percentage points
Error magnitude ratio ? 74 : 1
```

**[V]** T_fus(urea) = 132.7 °C (§F3, verified from two independent datasets [S4, S5]).

```
Stage 1 sits  2.7 K BELOW the urea fusion line
Stage 2 sits  7.3 K ABOVE the urea fusion line
```

**[I]** A 74:1 error ratio that flips sharply across a pure-component phase-transition temperature is the signature of a **standard-state discontinuity**, not of a wrong interaction parameter. Interaction parameters are smooth in T; fusion lines are not.

**[I]** This also explains the refit pathology reported in the handoff. A two-parameter (u?, u¹) fit forced to absorb a step-like reference-state error will distort the temperature dependence — which is precisely the reported symptom (the fit reproduces both points but inverts the fixed-pressure temperature monotonicity, which is unphysical for vacuum boiling). The conclusion drawn in the handoff — that *no physically monotonic single urea–water binary reproduces both points* — is **correct**. But the inference that new ebulliometric data is therefore required does not follow: a mis-specified model is not repaired by more data for the wrong binary.

### 4.2 Second structural defect: the melt is not a binary

**[V]** Urea decomposition begins essentially at the melting point; Tischer et al. establish the initiating net reaction in the 140–180 °C interval as `2 urea(l) ? biuret(l) + NH?(g)`, ?_RH = 55.6 kJ/mol, as a surface process with A = 3.5 (SI units) and E_a = 99 kJ/mol [S5].

**[V]** Urea-plant patent literature describing exactly this equipment states that the vapour leaving a vacuum concentrator comprises water together with small amounts of ammonia and carbon dioxide [S6], and specifies melt purity as *"urea including biuret"* [S7].

**[I]** Two consequences follow. First, the PFD's "urea mass fraction" at these stages is very likely a **lumped urea + biuret** specification, in which case the model and the PFD are not reporting the same quantity — an accounting mismatch, not a thermodynamic error. Second, the vapour is not pure water, so a pure-water fugacity reference systematically misprices the water activity. **[VERIFY IN REPO / PFD]** which convention the strict source uses. This check costs nothing and may resolve a meaningful share of the 2.22 pp gap on its own.

### 4.3 Closure ladder for G2

Work these in order. Each step is independently testable, and the first two require **no new experimental data**.

**R1 — Reference-state audit (no new data).**
Confirm the urea standard state is the **subcooled liquid** at 130 °C, constructed as
`?°_urea(l, T) = ?°_urea(s, T) + ?_fusH(T) ? T·?_fusS(T)`
with the ?c_p correction carried (§F3 shows ?c_p moves T_fus by 24 K, so it is not optional). Re-run both design points. **[I]** Prediction: stage-1 error collapses substantially while stage-2 is barely perturbed. If it does not, R1 is falsified and the diagnosis is wrong — which is itself a clean, cheap result.

**R2 — Structural completion (open data only).**
Extend the 324 model from binary {urea, H?O} to {urea, H?O, biuret, NH?, CO?}:
- Biuret thermochemistry: biu(s) ?_fH° = ?563.70 kJ/mol, S° = 146.1 J/(mol·K), c_p = 131.3; biu(l) ?_fH° = ?537.06, S° = 203.27, c_p = 93 [S5, Table 2].
- Urea–biuret binary phase behaviour: eutectic system, assessed independently by Voskov et al. (2012) via a Margules excess-Gibbs description over T = 268–373 K, and reproduced by Tischer et al. [S5, S9].
- Biuret formation rate in the melt: from R4 below.
- Reconcile the reported "urea" figure against a urea + biuret lump per §4.2.

**R3 — Binary re-fit anchored on low-temperature data (open data only).**
The handoff correctly notes that the two design points under-constrain a temperature-dependent binary. The fix is to **constrain the shape at low temperature and extrapolate thermodynamically**, rather than to fit shape from two high-temperature points:
- **[V]** Roughly 1000 experimental points exist for the H?O–urea binary, reviewed and used for thermodynamic modelling by Kosova et al. (2016), which also performed a reassessment of the H?O–(NH?)?CO system — all below 135 °C [S4, S10].
- **[V]** Isopiestic activity-coefficient measurements for water–urea at 25 °C over a wide concentration range are published [S11]; heat-of-solution, heat-capacity and density data for aqueous urea at 25 °C likewise [S12].
- **[V]** The temperature dependence is not free: in the UNIQUAC family the excess-enthalpy and excess-heat-capacity contributions are proportional to the surface parameter *q*, which is why heat-of-dilution and heat-capacity data are the efficient way to determine it [S2]. Formally, H^E = ?RT² ? x_i (? ln ?_i/?T), so calorimetric data pin ?/?T directly.
- **[I]** Therefore: fit u? against isopiestic/VLE data at 25–100 °C, fit u¹ against calorimetric H^E and c_p data over the same range, then **extrapolate to 130–140 °C with a physically constrained temperature derivative** instead of a free parameter. Monotonicity is then an outcome, not a constraint you have to impose.

**R4 — Melt kinetics (open data).** Include biuret formation in the 324 melt using the kinetics in §5.3, which I verified independently.

### 4.4 Revised acceptance for G2

- The 324 model reports urea and biuret separately and states which convention the PFD comparison uses.
- Stage-1 and stage-2 residuals are explained by the same physical model without any additive PFD correction (the handoff's prohibition is retained).
- Reference-state construction for urea below its fusion temperature is unit-tested against the published fusion point (132.7 °C) — a test that requires no plant data at all.
- Any remaining bias is reported as a bounded extrapolation error with a declared domain flag.

### 4.5 What is still blocked in G2

**[V/X]** Independent multi-point ebulliometric urea–water VLE at 130–140 °C over 90–99 wt% remains unavailable in open literature, exactly as the handoff states. **[I]** After R1–R4 it should no longer be *load-bearing* — it becomes an accuracy refinement rather than a correctness blocker. Whether that holds is decided empirically by R1.

---

## 5. G4 — HP synthesis loop surrogate flows

### 5.1 Dependency confirmed

G4 genuinely follows G1 Tier A. Nothing below should be attempted before A1/A2 pass. What changes is that a **validated architectural template for this exact technology** is available, so the design work is largely done.

### 5.2 Published template for a CO?-stripping synthesis section

**[V]** Chinda et al. (2017) modelled and validated the synthesis section of an industrial CO?-stripping urea plant with a pool condenser, against plant data over 86.45–98.21 % capacity, using 22 process variables; reported mean absolute deviations were below 6 % on mass fractions and below 8 % on temperatures and utility flows [S3]. Their unit decomposition maps one-to-one onto the tags in G4:

| Plant unit | Modelling approach [S3] | Maps to |
|---|---|---|
| Pool condenser | Stoichiometric reactor with conversion specified from outlet composition; justified because reactor residence time is ~3× that of the condenser | 322E002 (HPCC) |
| Reactor | **10 CSTRs in series, one per sieve tray**, constant P, linear T profile, followed by a flash to split the phases (mirroring the industrial overflow separation) | 322R001 |
| Scrubber | 5 equilibrium stages, carbamate-formation equilibrium on each stage, all heat removed at the last stage | 322E003 |
| Stripper | 11 stages; heat supplied from stage 2 to the penultimate stage; carbamate-decomposition equilibrium on stages 1 to n?1; biuret formation on the last stage | 322E001 |

**[V]** An independent Aspen reference deck for the same technology uses a plug-flow reactor with user kinetics, a 5-stage rigorous scrubber carrying both carbamate equilibrium and VLE per stage, and a stoichiometric HP condenser with a design specification driving reactor outlet temperature to 183 °C [S8].

**[I]** The two independent sources agree on the 5-stage scrubber and on treating the HP condenser as conversion-specified. That convergence is a reasonable basis for the HFC model. Note that both **retain a specification on the condenser** — meaning the goal of eliminating every specified quantity from the loop is stricter than published practice. Aim instead at eliminating the *signed correction*, which is a different and achievable thing (§5.4).

### 5.3 Kinetics — one scheme verified here

**[V]** Chinda et al. derive biuret kinetics from Shen's (1959) second-order data via an Arrhenius regression they report as slope ?9624.4 and intercept 1.7654 on ln k vs 1/T [S3]. I checked that regression against their stated parameters:

```
E_a = ?slope × R = 9624.4 × 8.314462 = 80 022 J/mol = 80.0 kJ/mol
A   = exp(1.7654)                    = 5.844 m³/(mol·s)
Paper states: E_a = 8 × 10? J/kmol (= 80.0 kJ/mol), A = 5.84 m³/(mol·s)   ? consistent
```

So the biuret rate is usable as `r_biuret = 5.84 · exp(?80 022 / RT) · C_urea²` with C in mol/m³. **[V]** Independently, Tischer et al. give the melt-phase route `2 urea(l) ? biu(l) + NH?(g)` with E_a = 99 kJ/mol as a surface reaction and ?_RH = 55.6 kJ/mol [S5] — a different mechanism and regime (SCR deposits, not synthesis), so treat the two as bounding cases rather than interchangeable.

**[X]** The carbamate-formation and urea-formation rate expressions in the same paper are power-law with non-integer orders (indicating non-elementary kinetics), but **the numeric constants did not extract cleanly from the PDF text layer and I will not transcribe them**. Read equations (1) and (2) of [S3] directly from the source before coding.

**[V]** Reaction enthalpies as used in that work: carbamate formation ?27.99 kcal/mol (?117.1 kJ/mol), carbamate dehydration +5.19 kcal/mol (+21.7 kJ/mol), overall ?22.8 kcal/mol (?95.4 kJ/mol), biuret formation +4.28 kcal/mol (+17.9 kJ/mol) [S3].

**Do not hard-code those.** Derive them from the ?_fH° basis so they stay consistent with G6. Cross-check, using Voskov Table 2 and Table 1 values at 298.15 K [S4]:

```
NH?COONH?(liq) ? urea(liq) + H?O(liq)
?_rH = (?321 827) + (?285 830) ? (?624 323) = +16 666 J/mol = +16.7 kJ/mol
Literature value quoted above:                                   +21.7 kJ/mol
Discrepancy ? 5 kJ/mol
```

**[I]** A 5 kJ/mol spread on a reaction of this size is not alarming, but it is exactly why reaction enthalpies must be *computed* from a single formation-enthalpy datum rather than pasted in from a paper — otherwise the reactor energy balance and the stream enthalpies disagree by a few kJ/mol everywhere, invisibly. The carbamate-formation enthalpy is even more standard-state sensitive (it depends on whether NH? is referenced as liquid or ideal gas), which reinforces the point.

### 5.4 Removing `REACT_TEAR_DES`

The signed correction exists because the recycle is a **specification** rather than a **variable**. Two viable routes:

**Route A — Equation-oriented (preferred).** Compile HPCC + reactor + stripper + scrubber into one residual vector and solve simultaneously by Newton–Raphson with an analytic or AD Jacobian, adding the four atom balances (C, H, N, O) as explicit equality constraints rather than as post-hoc checks. Use homotopy continuation on reaction extent, or on a recycle-gain parameter ? from 0 (open loop) to 1 (closed loop), to get from a cold start into the basin of attraction. This is the paradigm that makes the correction structurally unnecessary — a perturbation anywhere propagates through the Jacobian with no cascade to police.

**Route B — Sequential-modular with a real tear.** Tear the carbamate recycle (not the reactor outlet), converge with damped Wegstein or Broyden, and require the tear residual — not a component correction — to go to tolerance. Simpler to retrofit; slower and less robust near the pressure/temperature interaction that the loop exhibits.

**[I]** Given that the handoff already reports pinned scrubber outlets and scalar inventories not paired with component holdups, Route A is the better investment: those are both symptoms of unit-level solving that Route B preserves.

### 5.5 Revised acceptance for G4

Keep the handoff's four criteria — they are well posed — and add two mechanical tests that can be automated:

- **Null-feed test.** Zeroing any feed must drive all dependent outlets to zero. Catches matter creation.
- **Jacobian sparsity test.** For every outlet variable, ?(outlet)/?(inlet) must be non-zero for at least one inlet. A structurally zero row is a pinned stream, wherever it hides.

---

## 6. G6 — Live flowsheet registry and absolute enthalpy

### 6.1 What the handoff gets right

The two-artifact split (static 163-row strict-source catalogue vs. live producer–consumer registry) is correct and should be kept. So is the refusal to promote a PFD row to a live stream without known endpoints, and the refusal to report catalogue coverage and connectivity coverage as one number.

### 6.2 Where I disagree: the enthalpy half is only partly blocked

The handoff rejects a sensible-only enthalpy on the grounds that it would game the audit metric. **That is right about sensible-only enthalpy** — an enthalpy without formation terms cannot close a reactive energy balance, so publishing it would be worse than publishing nothing.

But that is not the only option below full G1. Decompose the stream enthalpy:

```
H_stream = ?_i n_i · h_i(T,P)  +  H^E(T,P,x)

h_i(T,P) = ?_fH°_i(298.15)                     ? published, available now
         + ????? c_p,i dT                       ? published, available now
         + phase-change terms (?_fusH, ?_vapH)  ? published, available now
         + Poynting / pressure correction        ? available now [S4, eq. for ?_vG]

H^E      = ?RT² ?_i x_i (? ln ?_i / ?T)         ? needs the tier's activity model (G1)
```

**[V]** Every species in scope has published ?_fH°, S° and c_p: NH?, CO?, H?O in [S4, Table 1]; urea and ammonium carbamate, solid and liquid, in [S4, Table 2]; urea (s/l/g), biuret (s/l/g), triuret, cyanuric acid, HNCO, ammelide, ammeline in [S5, Table 2].

**[I]** For a reactive loop the formation terms are of order 10²–10³ kJ/mol while excess enthalpies of this solution family are of order 10?–10¹ kJ/mol. So the term that G1 gates is the *smaller* one. This is an order-of-magnitude argument, not a measurement — but it means a formation-based enthalpy is a defensible engineering quantity, not a metric game.

### 6.3 Recommendation: declared enthalpy quality tiers

Publish `enthalpy_kJkg` for every live stream now, with a mandatory companion field `enthalpy_basis`:

| Tier | Contents | Available | Honest use |
|---|---|---|---|
| **H0** | Formation + sensible + phase change + Poynting; ideal solution | **Now** | Heat balances, duty estimates, trending; explicitly excludes mixing non-ideality |
| **H1** | H0 + H^E from that tier's activity model | As each G1 tier lands | Design-grade balances within the tier domain |
| **H2** | H1 reconciled against licensor/plant heat balance | After G1-A4 | Reconciled plant model |

The audit metric then reports `n(H0)/n(H1)/n(H2)` rather than a single "has enthalpy" count. That closes the coverage gap *and* keeps the honesty property, because the basis is declared per stream rather than implied. `make_stream`'s existing `h_kjkg` hook is the right place; add the basis enum alongside it.

### 6.4 Immediate actions for G6

1. Emit the 163-row static catalogue from the strict PFD source, every row tagged `static` / `unresolved`. No external data needed — do this first; it is the cheapest large win in the whole list.
2. Build the H0 enthalpy datum (elements at 298.15 K) as a shared service consumed by all three property tiers.
3. Add the `enthalpy_basis` enum and backfill H0 across the 55 live streams.
4. Audit the vessel registries that publish gross make or pump flow rather than actual outlet state — that is a data-model defect, independent of G1, and fixable now.

**Still blocked:** raising live coverage above 55/163 tracks G1/G4/G9 implementation, exactly as the handoff says.

---

## 7. G9 — Vendor/equipment equations

Split this gap. The two halves have very different prognoses.

### 7.1 G9a — the 324 ejectors: partially closable

The datasheets say a polynomial cannot be identified from one point. **That is true and remains true.** But three independent physics constraints exist that do not require a pull curve, and together they bound the answer instead of leaving it free.

**Constraint 1 — the motive nozzle throat is calculable, not fitted.**
Choked flow through the primary nozzle fixes A_t from motive stagnation pressure, temperature and ? alone:

```
?_p = (P_g · A_t / ?T_g) · ?( ?/R · (2/(?+1))^((?+1)/(??1)) )
```

This is first-principles. **[VERIFY IN DATASHEET]** the handoff quotes motive *flows* but not motive *pressures* for 324F002/F004/F005; if motive P and T are on the datasheets, A_t is determined exactly and stops being a fitted parameter.

**Constraint 2 — the curve shape class is universal.**
**[V]** Fabri & Siestrunck established that for given primary and secondary stagnation pressures there is a threshold back pressure below which entrainment ratio is constant, and that the secondary flow reaches a critical condition in the mixing region [S13]. **[V]** Munday & Bagster's hypothetical-throat concept, built on by Huang et al., locates a plane inside the constant-area section where primary and secondary pressures equalise and mixing begins, followed by a shock and diffuser recompression [S13, S14]. **[V]** Above the critical back pressure the entrainment ratio falls off rapidly as the shock migrates toward the nozzle exit; below it the effect is negligible [S15].

So the model does not need a curve *shape* from the vendor — the shape class is fixed physics. What the single point cannot fix is *where* the critical transition sits.

**Constraint 3 — the free parameter is bounded, not unbounded.**
**[V]** Huang et al. tested eleven ejectors and reported effective area ratios A?/A_t spanning 6.44 to 10.64 [S14] — a factor of 1.65, not an open range.

**[I]** Combining these: with A_t fixed by Constraint 1 and the design point fixing ?_design, the remaining freedom is essentially A?/A_t plus the isentropic efficiencies. Sweeping A?/A_t across the published range generates a **bounded family of pull curves** all of which pass through the vendor duty point. Report that family as a P5/P50/P95 envelope with a declared assumption, rather than picking one curve and calling it the answer. That is honest *and* usable — the simulator gets physically-correct off-design behaviour with quantified uncertainty, instead of a constant-? roll-off with none.

**Declared assumption to state explicitly:** **[A]** the vendor duty point is at or just below the critical back pressure — standard sizing practice with margin. If that is wrong the envelope shifts; say so in the model card.

**Constraint 4 — composition response is predictable from open correlation.**
**[V]** A Heat Exchange Institute research programme pumped 13 pure gases and 12 gas mixtures through small commercial single- and two-stage steam-jet ejectors from two manufacturers; entrainment ratios were found to correlate with molecular weight, on a curve reported as independent of pressure and of ejector design characteristics, and applicable to gas mixtures [S16].

**[I]** This matters more than it looks. The 324 ejectors handle a suction gas whose composition shifts with evaporator operation (water plus NH?, CO? and inerts [S6]). The molecular-weight correlation lets the model respond correctly to that shift *without any vendor data at all*. A constant-? model cannot.

**Consistency check on the one point you do have** (arithmetic mine, from the handoff's own figures for 324F002):

```
motive 650 kg/h + suction 94 kg/h = 744 kg/h  vs  stated discharge 744 kg/h   ? closes exactly
design entrainment ratio ? = 94/650 = 0.1446
compression ratio P_d/P_s = 1.0/0.2 = 5.0
```

The F002 point is internally consistent and usable as an anchor. **[X]** The 324F004 and 324F005 figures as transcribed in the handoff ("motive 927 = 600 / suction 712 = 634 kg/h"; "motive 929 = 505 kg/h") are ambiguous to me and do not obviously close; check them against the datasheets before use.

**The second duty point may already exist.** **[I]** The handoff treats the second point as vendor-supplied. But an ejector operating at a different plant load *is* a second duty point: motive steam flow and pressure, suction pressure and discharge pressure at a distinct throughput give exactly the additional constraint needed. If the DCS historian carries those tags for the 324 ejectors at two well-separated steady loads, the pull curve becomes constrained from plant data rather than from the vendor. This is worth checking before treating G9a as gated — it converts an external dependency into an internal one.

### 7.2 G9b — valve hydraulics: closable to first order

**[I]** Valve C_v can be back-calculated from the rated design flow and pressure drop (`C_v = Q?(SG/?P)` in the usual units), giving a design-anchored hydraulic model with a declared single-point provenance — the same honest pattern already used for the 324 UNIQUAC extrapolation. Elevation heads come from the P&ID/plot plan. Trim characteristic (linear / equal-percentage) cannot be inferred and stays open; assume linear and flag it, or omit the characteristic and model only the rated point.

### 7.3 G9c — Unit 335: genuinely open

**[V/X]** No equipment list, P&ID or datasheets. Nothing in the open literature substitutes for a specific unit's equipment.

**Interim model that is still worth building:** a **declared boundary block** that (a) closes total mass, C/H/N/O and energy across the boundary, (b) exposes its state vector and connected streams, (c) carries an explicit `DATA_GATED: no equipment model` flag, and (d) exposes its degrees of freedom so the specifications a user must supply are visible rather than buried. Rewrite the acceptance criterion accordingly: Unit 335 exposes states and closes balances *as a declared boundary* until equipment data arrives. The current criterion ("exposes mass, component, energy, hydraulic and control states with connected streams") cannot be met without the data and so permanently reads as failure — which hides the fact that the boundary itself could be correct.

---

## 8. Sequenced work plan

Ordered by (value ÷ dependency), not by gap number.

### Phase 0 — No new data required (days)

| # | Task | Gap | Why first |
|---|---|---|---|
| 0.1 | Reference-state audit of urea in the 324 model; unit-test against T_fus = 132.7 °C | G2 | Cheapest test of the highest-value hypothesis. Falsifiable in hours. |
| 0.2 | Emit the 163-row static catalogue from the strict PFD source | G6 | Largest coverage gain in the list, zero external dependency |
| 0.3 | Build the H0 absolute-enthalpy datum + `enthalpy_basis` enum | G6, G1, G4 | Shared service every later phase consumes |
| 0.4 | Check whether the PFD "urea" spec is urea-only or urea+biuret | G2 | May be an accounting mismatch, not a physics error |
| 0.5 | Ejector envelope: A_t from choked flow, A?/A_t sweep 6.44–10.64, MW correction | G9a | Turns an unconstrained fit into a bounded envelope |
| 0.6 | Query the DCS historian for 324 ejector tags at two separated loads | G9a | May supply the "missing" second duty point internally |
| 0.7 | Build the atom-balance / null-feed / Jacobian-sparsity test harness | G4 | Needed to *prove* G4 later; write it before you need it |

### Phase 1 — Tier A property package (weeks)

1.1 Implement constituent thermochemistry, three-reaction speciation (log coordinates), UNIQUAC activity model, virial EoS, Poynting-corrected standard states, per §3.3.
1.2 Validate against the published conversion and bubble-point grids (acceptance A1).
1.3 Validate the saddle azeotrope (acceptance A2) — the structural test.
1.4 Implement the tier-interface contract: apparent-composition handover, common enthalpy datum, domain flags (acceptance A3).

### Phase 2 — Unit replacement in flow order (weeks)

2.1 HPCC 322E002 — conversion-specified reactor with full component inventory, per the published template.
2.2 Reactor 322R001 — CSTRs in series, one per sieve tray, plus outlet flash.
2.3 Stripper 322E001 — staged model with carbamate-decomposition equilibrium and terminal biuret formation.
2.4 Scrubber 322E003 — 5 stages with carbamate equilibrium, heat removed at the last stage.
2.5 Convert the loop to a simultaneous solve (Route A) and delete `REACT_TEAR_DES`. Run the Phase-0.7 harness as the gate.

### Phase 3 — Evaporation, enthalpy, coverage

3.1 G2 R2/R3/R4: multicomponent melt model with biuret; low-temperature-anchored binary re-fit.
3.2 Promote live streams from H0 to H1 as each tier's activity model lands.
3.3 Re-report catalogue vs connectivity coverage separately.

### Phase 4 — Data-gated remainder

4.1 Licensor design point ? G1 acceptance A4 (bias reporting).
4.2 Second ejector duty point (vendor or historian) ? collapse the G9a envelope.
4.3 Unit-335 equipment data ? replace the boundary block.
4.4 Independent vacuum VLE ? tighten G2 beyond R1–R4.

---

## 9. Proposed rewritten handoff entries

Drop-in replacements consistent with the handoff's own rule that closed items are deleted and open items carry method plus blocking datum.

> **G1 — HP-loop reactive thermodynamics not implemented (re-scoped 2026-07-31)**
> **Method:** three-tier property architecture. Tier A = molecular UNIQUAC (6 neutral constituents, 3 liquid reactions) + Voronin virial EoS, domain 150–230 °C / 3.5–28 MPa, all parameters published [Voskov & Voronin, *J. Chem. Eng. Data* 61 (2016) 4110]. Tier B = existing Extended UNIQUAC, domain-limited to ?110 °C / ?100 bar per its published validity. Tier C = 324 melt model (see G2). Interface = apparent-composition handover on a common elements-at-298.15 K enthalpy datum with domain-flag propagation.
> **Superseded:** the plant-wide ionic Extended-UNIQUAC + Huron-Vidal/MHV2 route. The Thomsen–Rasmussen parameters are published valid only to 110 °C / 100 bar, and the Debye–Hückel term requires a mixed-solvent dielectric constant that does not exist for NH?–H?O–urea at synthesis conditions.
> **Blocking datum:** licensor 100 %-load HP design point — **required for plant reconciliation (acceptance A4) only**. Thermodynamic validation (A1–A3) uses the published conversion grid, bubble-point grid and saddle azeotrope and is not blocked.

> **G2 — Unit-324 vacuum model (re-diagnosed 2026-07-31)**
> **Finding:** the two design points straddle the urea fusion temperature (132.7 °C, verified from two independent published datasets). The stage-1 error (130 °C, ?2.22 pp) is 74× the stage-2 error (140 °C, ?0.03 pp). This is a standard-state signature, not a binary-parameter shape problem, and explains why the two-parameter refit inverts temperature monotonicity. Independently, the melt is not a binary: biuret forms from the melting point onward and the vapour carries NH?/CO?.
> **Method:** R1 subcooled-liquid reference state for urea with ?c_p carried (no new data); R2 extend to {urea, H?O, biuret, NH?, CO?}; R3 re-fit u? from isopiestic/VLE data and u¹ from calorimetric H^E and c_p below 135 °C, then extrapolate with a constrained temperature derivative; R4 melt-phase biuret kinetics.
> **Blocking datum:** independent multi-point ebulliometric urea–water VLE at 130–140 °C, 90–99 wt% — **demoted to accuracy refinement pending the R1 result**. If R1 does not collapse the stage-1 residual, restore it to blocking.

> **G4 — HP loop signed/pinned surrogate flows**
> **Method:** unchanged in intent; architecture now templated on a published, plant-validated CO?-stripping synthesis model (pool condenser as conversion-specified reactor; reactor as CSTRs-in-series per sieve tray + flash; staged stripper and 5-stage scrubber with carbamate equilibrium). Biuret kinetics verified: second order in urea, A = 5.84 m³/(mol·s), E_a = 80.0 kJ/mol. Remove `REACT_TEAR_DES` by simultaneous (equation-oriented) solve with atom balances as explicit constraints and homotopy continuation on recycle gain.
> **Blocked on:** G1 Tier A (A1–A3). **Note:** carbamate/urea rate constants must be read from the source publication — not transcribable from its PDF text layer.

> **G6 — Registry coverage and absolute enthalpy**
> **Method:** static 163-row catalogue is executable now. Enthalpy publishes in declared tiers: H0 (formation + sensible + phase change + Poynting, ideal solution) is available now from published ?_fH°/S°/c_p for every species in scope; H1 adds H^E as each property tier lands; H2 adds plant reconciliation. Audit reports n(H0)/n(H1)/n(H2), not a single count.
> **Blocked on:** live coverage above 55/163 tracks G1/G4/G9 implementation. H1 tracks G1.

> **G9 — Vendor/equipment equations (split 2026-07-31)**
> **G9a ejectors — partially closable.** A_t from choked motive flow (first principles); critical/subcritical structure is universal physics; A?/A_t bounded 6.44–10.64 from published measurements on 11 ejectors; suction-composition response from the HEI molecular-weight entrainment correlation, published as independent of ejector design. Deliver a P5/P50/P95 pull-curve envelope through the vendor duty point with the declared assumption that the duty point is at/near critical back pressure. **Blocking datum:** a second duty point to collapse the envelope — check the DCS historian at a second plant load before assuming this is vendor-gated.
> **G9b valve hydraulics.** C_v back-calculated from rated flow and ?P, declared design-anchored; elevation heads from P&ID. Trim characteristic remains open.
> **G9c Unit 335 — fully data-gated.** Interim: declared boundary block closing mass/atom/energy with exposed states, connected streams and visible degrees of freedom. **Blocking datum:** equipment list, P&ID, datasheets.

---

## 10. Source register

| ID | Source | Used for |
|---|---|---|
| S1 | Thomsen K., Rasmussen P., *Chem. Eng. Sci.* **54** (1999) 1787–1802 — VLSE in gas–aqueous electrolyte systems; parameters stated valid 0–110 °C, 0–100 bar, ?~80 m NH? | Tier B domain limits (F1) |
| S2 | phasediagram.dk — Extended UNIQUAC model description (Thomsen 1997 form); notes that heat-of-dilution and heat-capacity data efficiently determine *q*, and that temperature dependence is built into the model | Model form; G2-R3 mechanism |
| S3 | Chinda R.C., Yamamoto C.I., Lima D.F.B., Pessoa F.L.P. (2017), "Modeling and simulating the synthesis section of an industrial urea plant analyzing the biuret formation" — CO?-stripping plant with pool condenser, validated on plant data | G4 architecture, kinetics, reaction enthalpies |
| S4 | Voskov A.L., Voronin G.F., *J. Chem. Eng. Data* **61** (2016) 4110–4122, DOI 10.1021/acs.jced.6b00557 — thermodynamic model of NH?–CO?–H?O–urea; open PDF; SI contains MATLAB/C++ source | Tier A model, parameters, validation grids, urea thermochemistry |
| S5 | Tischer S., Börnhorst M., Amsler J., Schoch G., Deutschmann O., *Phys. Chem. Chem. Phys.* **21** (2019) 16785–16797, DOI 10.1039/C9CP01529A — open access (CC BY-NC 3.0) | Urea fusion point; biuret/triuret thermochemistry; melt decomposition scheme |
| S6 | US 9,000,215 — urea process patent; describes vacuum-concentrator vapour as water with small amounts of ammonia and carbon dioxide | G2 structural argument |
| S7 | US 12,319,646 — low-biuret urea production; melt specified as wt % "urea including biuret" | G2 accounting convention |
| S8 | Aspen Plus urea synthesis loop reference model (via ureaknowhow.com) — RPLUG reactor with user kinetics, 5-stage scrubber, stoichiometric HP condenser, design spec on 183 °C reactor outlet | G4 architecture corroboration |
| S9 | Voskov A.L., Babkina T.S., Kuznetsov A.V., Uspenskaya I.A., *J. Chem. Eng. Data* **57** (2012) 3225–3232 — urea–biuret–water phase equilibria, Margules excess Gibbs, 268–373 K | G2-R2 |
| S10 | Kosova D.A., Voskov A.L., Kovalenko N.A., Uspenskaya I.A., *Fluid Phase Equilib.* **425** (2016) 312–323 — includes a reassessment of the H?O–(NH?)?CO binary | G2-R3 |
| S11 | Isopiestic activity coefficients for water–urea at 25 °C (*J. Phys. Chem.*, classic isopiestic series) | G2-R3 (u? anchor) |
| S12 | Heat of solution, heat capacity and density of aqueous urea solutions at 25 °C (*J. Chem. Eng. Data*) | G2-R3 (u¹ anchor via H^E) |
| S13 | Fabri & Siestrunck (1958) threshold-back-pressure behaviour; Munday & Bagster (1977) hypothetical throat — as reviewed in the ejector 1-D modelling literature | G9a curve-shape class |
| S14 | Huang B.J. et al., *Int. J. Refrigeration* **22** (1999) 354–364 — 1-D constant-pressure-mixing analysis; 11 ejectors tested, A?/A_t = 6.44–10.64 | G9a bounded parameter |
| S15 | El-Dessouky H. et al., *Chem. Eng. Process.* (2002) — evaluation of steam jet ejectors; critical-condition behaviour and design correlations | G9a critical transition |
| S16 | Heat Exchange Institute research programme — 13 pure gases and 12 mixtures on commercial single/two-stage steam-jet ejectors; entrainment ratio vs molecular weight, reported independent of pressure and ejector design | G9a composition response |

**Note on S11/S12:** these appeared consistently as cited works in the citation networks of S4/S9/S10, and their titles and journals are confirmed. **[X]** I did not open the primary articles themselves, so I have not verified their concentration and temperature coverage in detail. Confirm coverage before relying on them for the G2-R3 fit.

---

## 11. Confidence, caveats, and what would change my mind

### 11.1 Confidence by claim

| # | Claim | Confidence | Basis |
|---|---|---|---|
| 1 | Thomsen–Rasmussen parameters are published valid only to 110 °C / 100 bar, so a plant-wide Extended UNIQUAC cannot cover the HP loop | **0.93** | Directly stated in the source abstract [S1] and corroborated [S2] |
| 2 | Voskov–Voronin covers the HP envelope with fully published parameters and is a defensible Tier A | **0.90** | Full paper read; domain, parameter tables, validation and SI code all confirmed [S4] |
| 3 | The published conversion/bubble-point grids can substitute for the licensor point in *thermodynamic* validation | **0.88** | Grids and uncertainties published [S4]; residual risk is that your acceptance process requires licensor traceability for institutional reasons |
| 4 | T_fus(urea) = 132.7 °C, and the 324 design points straddle it | **0.97** | Computed two independent ways, agreeing to 0.7 K, and matching the value stated in [S5] |
| 5 | The 74:1 stage-1/stage-2 error ratio is a reference-state signature | **0.72** | Strong circumstantial fit, but I cannot see `thermo_extended_uniquac.py` to confirm how the urea standard state is actually built. **Below 0.8 — treat as the leading hypothesis, not a finding.** Test 0.1 settles it. |
| 6 | The 324 melt is not a binary (biuret present, vapour carries NH?/CO?) | **0.88** | Patent process descriptions [S6, S7] plus melt decomposition chemistry [S5]; specific to *this* PFD's convention, which I cannot see |
| 7 | Biuret kinetics: second order in urea, A = 5.84 m³/(mol·s), E_a = 80.0 kJ/mol | **0.90** | Re-derived from the published regression and matches the paper's stated values to 3 significant figures |
| 8 | H0 absolute enthalpy is a defensible tier, not a metric game | **0.85** | Formation data availability is verified; the "H^E is the smaller term" argument is an order-of-magnitude inference, not a measurement |
| 9 | The G9a envelope approach is sound | **0.82** | Each constraint is individually verified [S13–S16]; combining them into a P5/P50/P95 envelope is my synthesis and has not been validated against a real pull curve |
| 10 | A second ejector duty point may be recoverable from the DCS historian | **0.55** | Physically sound, but entirely dependent on which tags are actually historised. **Below 0.8 — check before planning around it.** |
| 11 | Unit 335 remains genuinely blocked | **0.95** | No substitute exists for a specific unit's equipment data |

### 11.2 The two weakest points, stated plainly

**Claim 5 (0.72)** is the load-bearing one for G2, and it is an inference from an error pattern, not an inspection of your code. If `thermo_extended_uniquac.py` already builds the urea standard state as a subcooled liquid with the ?c_p term, my diagnosis is wrong and G2 reverts to the handoff's original reading. **Run task 0.1 before committing anything else in G2.** It is a few hours of work and it either unlocks the gap or cleanly eliminates my hypothesis.

**Claim 10 (0.55)** is speculative about your tag list. Do not let Phase 4 planning depend on it until someone has actually queried the historian.

### 11.3 What I could not confirm

- **[X]** Whether the strict-source PFD reports urea alone or urea + biuret at 324E001/E003. Decisive for §4.2.
- **[X]** How the urea standard state is currently constructed in the repo. Decisive for §4.1.
- **[X]** Motive pressures and temperatures for 324F002/F004/F005. Without them A_t stays fitted rather than calculated.
- **[X]** The F004/F005 duty figures as transcribed in the handoff — the notation did not parse for me and the numbers do not obviously close.
- **[X]** The exact carbamate-formation and urea-formation rate constants in [S3] — the PDF text layer garbled them. Read them from the source.
- **[X]** The concentration/temperature coverage of S11 and S12 in detail.
- **[X]** Anything in the three referenced project documents I was not given. If the closure-methodology document already anticipates the tiering argument in §3, treat §3 as corroboration rather than as new.

### 11.4 Method notes

- The `chemical-modelling` skill's compatibility note calls for the `graphify` and `caveman` skills alongside it. Neither is available in this environment, so the project graph has **not** been updated — do that separately after accepting any of this.
- Nothing here has been committed to the repo; this is a plan document only.
- No PFD row, stream value, vendor figure or plant measurement has been invented. Where a number was needed and not available, the gap is stated rather than filled.