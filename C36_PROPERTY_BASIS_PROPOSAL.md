# C36 property & species basis — sourced proposal (approvable path)

Date: 2026-07-29. Status: **proposal for approval**, not implemented. This document exists so the
C36 / TD-009 / TD-012 gap can be closed by *approving a specific, cited parameter basis* (the gap's
own "obtain **or approve**" branch) rather than by obtaining licensor data. It also records the
research finding that parts of C36 are already addressed with cited physics, and gives the phased,
design-pin-preserving integration plan for C34 and C43, which depend on this same basis.

Nothing here fabricates a parameter, a sink, or a curve. Where an exact coefficient set is required
but not reproduced here, the source and the specific table are named so a reviewer can transcribe and
approve them.

## 1. What C36 actually needs

The open bullets are: (a) a complete NH3-CO2-H2O-urea electrolyte fugacity/activity, speciation,
density, heat-capacity and enthalpy basis for HP/MP/LP; (b) live molecular vectors replacing the
lumped-mass transport in 328D001, 328D003 and 323C005; (c) replace-or-approve the frozen densities
`RHO_744_KGM3`, `RHO_741_KGM3`, `R328_C002_RHO`, `R328_C004_RHO`; (d) a rigorous VLE for the Unit-324
evaporators. C34 (stream enthalpy) and C43 (Unit-328 reaction/energy closure) are **downstream of the
same basis** — they cannot be done rigorously until the speciation and phase enthalpies exist, which
is why the current engine leaves stream enthalpy `None` ("no fabricated properties") and buries the
Unit-328 reaction enthalpy in back-solved latents.

## 2. Already addressed with cited physics (evidence, not fabrication)

- **Density temperature dependence.** `aqueous_rho` (main.py §"AUDIT C10") already takes the density
  *slope* from the IAPWS/Wagner & Pruss (1993) saturated-liquid equation — a published six-coefficient
  correlation, nothing fitted — anchored multiplicatively to each stream's PFD value. The C10 block
  also proves, with three independent checks, that the frozen anchors 933.0 (139 °C) and 923.28
  (143 °C) sit +0.64 % / −0.02 % from real water and are physically defensible, and that the licensor's
  two "impossible" Amm.Water entries (908.5, 897.7) are never used as constants. **Recommendation:**
  approve the existing anchors + Wagner-Pruss slope as the C36 density basis for the aqueous streams;
  the residual composition effect is < 1.3 % and is folded into item 4 below only if the electrolyte
  model is adopted.
- **Reaction enthalpies.** The stripper already uses Frejacques' process-condition values (Brouwer,
  *Thermodynamics of the Urea Process*, UreaKnowHow 2009): carbamate formation CO2 + 2 NH3 →
  NH2COONH4 ΔH = −117 kJ/mol at 110 atm/160 °C; urea dehydration +15.5 kJ/mol; NH3 desorption
  23 kJ/mol. These validate to 96 % of the licensor stripper duty with nothing fitted. **Recommendation:**
  adopt this same cited set for the Unit-328 explicit-ξ·ΔH rework (C43), since 328 runs the same two
  reactions at comparable conditions.
- **Hydrolysis kinetics.** 328C003 already uses the second-order Inoue/Otsuka law with an explicit
  +101.5 kJ/mol endotherm — cited and live (`xi_hyd_328`). This extent is already exposed for C43.

## 3. Recommended basis for the missing composition-aware physics

| Sub-system | Conditions | Recommended published model | Source |
| --- | --- | --- | --- |
| LP desorption/absorption speciation, VLE, excess enthalpy & cp (328C002/003/004, 328D001, 328D003, 323C005, 322C001) | 0–150 °C, 1–100 bar, high NH3 loading | **Extended UNIQUAC** (NH3/NH4+/CO2/HCO3−/CO3²−/NH2COO−/H2O). Gives activity coefficients, speciation, excess Gibbs/enthalpy/cp directly. | Darde, van Well, Stenby, Thomsen, *Ind. Eng. Chem. Res.* **49** (2010) 12663–12674; foundational form Thomsen & Rasmussen, *Chem. Eng. Sci.* **54** (1999) 1787–1802 |
| Unit-324 evaporator VLE (replace empirical `evap_w_eq`) | 0.03–0.6 bar, 100–140 °C, urea-rich | Same Extended UNIQUAC activity basis for the aqueous side + urea water-activity depression | Darde/Thomsen (above) |
| Reactor / HP equilibrium conversion (cross-check reactor.py) | 140–200 °C, 50–250 atm, N/C 2.4–6, H2O/CO2 ≤ 0.5 | **Gorlovskii–Kucheryavyi (1980)** explicit equilibrium-conversion correlation; **Isla–Irazoqui–Genoud (1993)** framework | Isla et al., *Ind. Eng. Chem. Res.* 32 (1993); Lemkowitz, *J. Chem. Tech. Biotechnol.* 30 (1980) |

The Extended UNIQUAC validity window (0–150 °C, 1–100 bar) covers every LP unit named in C36. Its
interaction-parameter matrix (species volume/surface `r,q` and binary energy `u⁰_ij, uᵀ_ij`) is the
one artefact that must be transcribed and approved — it is tabulated in Darde et al. (2010) and its
supporting information. **This is the single "obtain-or-approve" decision the gap turns on.**

## 4. Phased integration plan (design-pin-preserving)

Each phase keeps the bit-exact design fixed point (departure-from-anchor form, as the engine already
does for cp/rho) and lands behind tests, exactly like the C10 aqueous work.

1. **Property module** `props_nh3co2h2o.py` — **DELIVERED 2026-07-29** (`backend/props_nh3co2h2o.py`,
   `backend/test_props_nh3co2h2o.py`, 12/12 pass). The full Extended UNIQUAC parameter matrix is
   transcribed verbatim from open sources (Darde 2011 thesis Tables 2-2…2-6 for r/q + u0/uT interaction
   + fitted formation/Cp; Thomsen 1997 thesis Table 5.7 for base-species Cp; CODATA/NIST for base
   ΔGf/ΔHf; Rumpf-Maurer 1993 Henry's law). The standard-state thermodynamics, reaction equilibrium
   constants and Henry's law are **validated against independent textbook data**: liquid-water Cp
   (75.3 J/mol/K), pKw and its temperature curve (14.94 @0 °C, 14.00 @25 °C, 13.03 @60 °C), carbonic-acid
   pKa1 (6.35) and pKa2 with T-dependence (10.56→10.17, 0→50 °C), ammonium pKa (9.25), and the NH3/CO2
   Henry constants — all reproduced from the parameters alone. Nothing is wired into the engine.
   *Two honest residuals, not fabricated:* the standard-state Cp coefficients for NH3(aq) and CO2(aq)
   live in Thomsen & Rasmussen (1999, paywalled) and are left `None`, so the two reactions consuming
   them are exposed at 25 °C only; the module refuses to extrapolate them (asserted by a test). The full
   Newton speciation + SRK-VLE solver, plus the Debye-Hückel long-range term, are **phase 1b**.
2. **Enthalpy datum (C34):** derive per-stream specific enthalpy = sensible (existing cited cp) +
   excess (UNIQUAC) + formation/reaction terms, on one declared datum. Populate the `enthalpy_kJkg`
   field the records already carry. Only after phase 1 validates — a sensible-only enthalpy now would
   contradict the codebase's "no partial/misleading properties" rule.
3. **Live molecular vectors:** replace lumped-mass transport in 328D001, 328D003, 323C005 with the
   speciated vectors (the des_advance species layer already exists for 328C00x; extend it).
4. **Unit-328 energy closure (C43):** replace the back-solved latents (LAM737/748/750) with explicit
   ξ·ΔH terms using the §2 cited enthalpies and the now-speciated carbamate extents; re-pin so
   dT/dt = 0 at design. Target: the `q328_resid` diagnostic collapses from −1690.5 kW toward the
   stripper-equivalent shell-loss level (~4 %).
5. **Unit-324 VLE:** replace `evap_w_eq` with the activity-based bubble point; keep the PFD anchor.

## 5. C35 and C40 — honest status (not closed by this proposal)

- **C35** (molecular conservation): once the speciation basis exists, run the **Crowe (1986)
  projection-matrix reconciliation** already named in `research_plan_324_vacuum_train.md`. It still
  requires an **approved measurement-uncertainty basis** (instrument accuracy classes or licensor
  weights). A defensible default (e.g. orifice/coriolis class accuracies) can be *proposed* but the
  reconciled residuals are only *certified* once those weights are approved. Not fabricatable.
- **C40** (ejector performance): unchanged. A first-principles compressible steam-jet model still
  needs the 324F004-discharge / 324E006 pressures and the effective throat/loss geometry — the exact
  data the gap lists as missing. Producing off-design breakdown/critical-backpressure behaviour without
  them would be generic correlation standing in for plant-specific data ("false precision"). Retain the
  PFD-anchored surrogate until vendor/plant-test data arrive.

## 6. The decision this asks for

Approve (or amend) the §3 model selection and the Darde-et-al.-2010 Extended UNIQUAC parameter matrix
as the C36 basis. On approval, phases 1–5 close C36, then C34 and C43, in that dependency order. C35
additionally needs approved measurement uncertainties; C40 remains data-blocked.

## Sources

- Darde, van Well, Stenby, Thomsen, "Modeling of CO2 absorption by aqueous ammonia solutions using
  the Extended UNIQUAC model," *Ind. Eng. Chem. Res.* 49 (2010) 12663–12674.
- Thomsen & Rasmussen, "Modeling of vapor–liquid–solid equilibrium in gas–aqueous electrolyte
  systems," *Chem. Eng. Sci.* 54 (1999) 1787–1802.
- Gorlovskii & Kucheryavyi, "Equation for determination of the equilibrium degree of CO2 conversion
  during synthesis of urea" (1980).
- Isla, Irazoqui, Genoud, "Simulation of a urea synthesis reactor. 1. Thermodynamic framework,"
  *Ind. Eng. Chem. Res.* 32 (1993).
- Lemkowitz et al., "Phase equilibria in ammonia–carbon dioxide systems at and above urea synthesis
  conditions," *J. Chem. Tech. Biotechnol.* 30 (1980).
- Brouwer, "Thermodynamics of the Urea Process," UreaKnowHow.com Process Paper, June 2009.
- Wagner & Pruss, *J. Phys. Chem. Ref. Data* 22 (1993) 783 (saturated-liquid density; IAPWS R7-97).
