# Open Simulation Gaps Only

Updated: 2026-08-01 (datasheet pass)
Strict source: `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`
Plant licensor manual (this plant): `References/Sources/02 FUNDAMENTALS.pdf` (Uhde UD-VT-G00-DC-0003)
Validated reactor kinetics: `References/Sources/Aspen urea.pdf` (AspenTech Stamicarbon loop, V7 2008)
CSTR-in-series corroboration: `References/Sources/Modeling the synthesis section...pdf` (Hamidipour 2005)
Vendor equipment datasheets (this plant, Uhde/Koerting 2004): `References/Sources/324F002/F004/F005
Datasheet.pdf` (steam-jet ejectors, complete duty points), `324E002 Datasheet.pdf` (primary vacuum
condenser, full shell-and-tube DDS/PDS), `Merged_Searchable_PIDs.pdf` (P&IDs).
Audit: `FULL_SIMULATION_EXTENDED_UNIQUAC_AUDIT_2026-07-29.md`
Research passes applied: `References/Gaps solution.md`, `References/Urea Plant Simulation Gaps2.md`,
`References/Gaps Closure/Gaps Closure .docx` (evaporator/droplet/SR-POLAR closure methodology)

Closed items are intentionally deleted from this file. Each item below is still open because the
remaining equation or datum cannot be supplied honestly by the current repository evidence. Each
carries the **Method** to apply and the exact **Blocking datum** that must arrive before that method can
close it. Fabricating closure is prohibited (CLAUDE.md 1). Under the 2026 source-pass directive, model
outputs within **10 %** of the plant design values are accepted (the strict-PFD-exact rule is relaxed).

Standalone, self-validated closure/analysis modules (the "validate on its own before wiring" pattern as
`props_nh3co2h2o.py`); each runs in <1 s and is cited line-by-line. What they closed is deleted below;
what they left open is sharpened. Modules: `gap_g6_static_catalogue.py`, `gap_g6_h0_enthalpy.py`,
`gap_g9a_ejector_envelope.py`, `gap_g2_reference_state_audit.py`, `gap_g4_conservation_harness.py`,
`gap_g4_reactor_kinetics.py`, `gap_g9_evaporator_condenser.py` (new: datasheet-validated condenser +
urea-evaporator rating), `gap_g9c_droplet.py` (new: Unit-335 Lagrangian droplet solidification).

## Open gaps at a glance -- what each is, and the equipment it touches (tag -> name)

Plain-language summary of every still-open gap and the exact equipment (tag number + name) it affects.
Tags are verified against the strict-source PFD, the licensor equipment descriptions, and `backend/
main.py`. Units: 322 = HP synthesis loop (~140-150 bar); 323 = LP recirculation + pre-evaporation;
324 = vacuum evaporation + vacuum system; 328 = desorption/hydrolysis; 329 = steam/vacuum utilities;
335 = finishing/granulation.

**G1 -- one plant-wide reactive-property model.** *What:* the runtime still uses locally-calibrated
phase/reaction splits instead of one reactive thermodynamic package (Extended-UNIQUAC or SR-POLAR) that
closes every phase-equilibrium and enthalpy call across the loop. This is the largest remaining build
and G4/G6's remaining pieces ride on it. *Equipment (every unit that makes a reactive phase/enthalpy
call):*

| Tag | Name | Role in G1 |
|-----|------|-----------|
| 322R001 | Urea Reactor (11 sieve trays) | reactive VLE + kinetics |
| 322E001 | HP Stripper (CO2 stripper) | reactive VLE |
| 322E002 | HP Carbamate Condenser (HPCC / pool condenser) | reactive VLE + enthalpy |
| 322E003 | HP Scrubber | reactive VLE |
| 322F001 | HP Carbamate Ejector (liquid-liquid jet pump) | carbamate stream property |
| 322C001 | Atmospheric / LP Absorber | Tier-B Extended UNIQUAC |
| 323C003 | LP Rectifying Column (stage-1 decomposer) | Tier-B VLE |
| 323E002 / 323E003 / 323E011 | Stage-1 heater / LP Carbamate Condenser (LPCC) / LP condenser | Tier-B VLE + enthalpy |
| 323F004 | LP Flash Tank | flash VLE |
| 323E010 + 323F010 | Pre-evaporator heater + separator | Tier-C melt VLE (delivered) |
| 324E001 + 324F001 | Evaporator I (falling-film) + separator | Tier-C melt VLE (delivered) |
| 324E003 + 324F003 | Evaporator II + separator | Tier-C melt VLE (delivered) |
| 328C002 / 328C003 / 328C004 | Desorber I / Hydrolyser / Desorber II | Tier-B VLE + hydrolysis kinetics |

**G4 -- equation-oriented HP synthesis loop.** *What:* the HP loop is reconciled by a sequential tear
(`REACT_TEAR_DES`) with signed component corrections; it must become a simultaneous atom-balanced solve.
The reactor kinetics themselves are now supplied (closed); only the EO integration remains, and it rides
on G1. *Equipment (the four HP loop units + the ejector that feeds them):*

| Tag | Name | Role in G4 |
|-----|------|-----------|
| 322R001 | Urea Reactor | `REACT_TEAR_DES` + reduced-conversion surrogate to retire |
| 322E002 | HP Carbamate Condenser (HPCC) | anchored flash to replace with reactive package |
| 322E001 | HP Stripper | atom-balance node in the simultaneous solve |
| 322E003 | HP Scrubber | pinned discharges to free |
| 322F001 | HP Carbamate Ejector | recycle carbamate feed into the loop |

**G6 -- live registry coverage + tiered enthalpy.** *What:* H0 absolute-enthalpy datum is delivered
(incl. ammonium carbamate); still open is wiring it into the live stream registry and raising live
coverage above 55/163 streams as G1/G4/G9 model the currently-unmodelled units. *Equipment:* plant-wide
(all 264 catalogued streams / ~163 in-scope). The carbamate reaction-consistency node specifically
spans 322R001 (reactor) and 322E002 (HPCC); coverage grows as every tag above and below gets modelled.

**G9a -- vacuum steam-jet ejectors (design duty MET; off-design shape open).** *What:* the three-stage
vacuum ejector train that holds the evaporator vacuum. Design-duty acceptance is met against the vendor
datasheets; the residual is the off-design pull-curve shape (mixing bore not independently pinned) and
wiring into main.py. *Equipment:*

| Tag | Name | Role in G9a |
|-----|------|-----------|
| 324F002 | Steam-jet Ejector I | pulls Condenser I; vendor duty 650/94/744 kg/h |
| 324F004 | Steam-jet Ejector II | pulls Condenser II -> Condenser III; duty 600/634 kg/h |
| 324F005 | Steam-jet Ejector III | pulls Condenser III -> Condenser IV; motive 505 kg/h |
| 324E002 | Vacuum Condenser I (primary) | back-pressure ~0.2-0.3 bar; vent = F002 suction |
| 324E005 / 324E006 / 324E007 | Vacuum Condenser II / III / IV | interstage back-pressures 0.12 / 0.33 / atm |

**G9 -- vacuum condensers + urea evaporators (rating cores BUILT; per-effect U*A + wiring open).**
*What:* datasheet-validated condenser U-A-LMTD rating and a urea-evaporator mass/energy + boiling-point-
elevation rating exist as standalone cores; the residual is the per-effect evaporator U*A datasheets and
wiring into the 324 concentration ODEs. *Equipment:*

| Tag | Name | Role in G9 evap/condenser |
|-----|------|-----------|
| 324E002 | Vacuum Condenser I | full DDS (1079 m2, 25.72 MW) -> validated U ~ 640 W/m2K |
| 324E005 / 324E006 / 324E007 | Vacuum Condenser II / III / IV | interstage condensers (rating cores; datasheets partial) |
| 324E001 + 324F001 | Evaporator I (falling-film) + separator | 94.3 wt% / 130 C / 0.33 bar effect |
| 324E003 + 324F003 | Evaporator II + separator | 97.7 wt% / 140 C / 0.13 bar effect |
| 323E010 + 323F010 | Pre-evaporator heater + separator | 80 wt% / 99 C / 0.46 bar effect |
| 323E003 / 323E011 | LP Carbamate Condenser (LPCC) / LP condenser | LP-side condensation duty |

**G9b -- control-valve hydraulics (not built this pass).** *What:* C_v back-calculable from rated flow
and dP; elevation heads from the P&ID; trim characteristic still open. *Equipment (control valves, not
vessels):* HV-322602 (322F001 NH3-nozzle spindle), HV-322605 (322R001 reactor overflow), LV-322501
(322E001 stripper bottoms letdown), LV-323501 (323F004 flash drain), HV-323605 / HIC-323605 (323F010
vent 790), HV-329605 (324F002 ejector motive), XV-322902 (CO2 feed isolation to 322E001), TV-329005.

**G9c -- Unit-335 granulation (droplet physics BUILT; tower geometry open).** *What:* the finishing
section that turns the 98.6 wt% melt into product. Droplet solidification/evaporation physics is built;
the residual is the bed/tower geometry, fan curves and screen efficiencies for a full rating model, plus
wiring. *Equipment:*

| Tag | Name | Role in G9c |
|-----|------|-----------|
| 335 (unit) | Granulation / prilling section -- tower, melt sprayers, fluidisation fans, screens, recycle | droplet fall + solidification + moisture evaporation |
| 324E003 + 324F003 | Evaporator II (upstream) | supplies the 98.6 wt% / 140 C / 3.6 bar melt feed |
| 335D007 | Unit-335 auxiliary drum | off-envelope boundary |

## G1 - Runtime reactive thermodynamics is not plant-wide Extended UNIQUAC

**Evidence:** `backend/props_nh3co2h2o.py` implements the Thomsen/Darde NH3-CO2-H2O Extended-UNIQUAC/
SRK/speciation core (validated, off-25 C capable), but the HPCC, reactor, stripper, scrubber, LP
absorber and Unit-328 columns still use calibrated splits in `backend/main.py`, and urea is absent
from the reactive runtime phase set.

**Method -- two viable routes, both now partly de-risked by the 2026 source pass:**
  1. TIERED activity model (`Gaps solution.md` re-scope): Tier A (HP loop) molecular UNIQUAC + Voronin
     virial EoS (Voskov & Voronin, JCED 61 (2016) 4110 -- the neutral H2O/urea limit is already coded in
     `thermo_extended_uniquac.py` and now validated to <2 % against the plant's own evaporation VLE, see
     former G2); Tier B (LP/absorbers) the existing Extended UNIQUAC; Tier C (324 melt) delivered.
  2. SINGLE cubic EoS (the AspenTech route, `Aspen urea.pdf`): SR-POLAR (Soave + Peneloux-Rauzy volume +
     Schwartzentruber-Renon polar term) across the WHOLE loop, treating the system as molecular
     (ionization small at 160-200 C / low water) with a USURA-style kinetic block. This is the validated
     industrial standard and sidesteps the missing mixed-solvent dielectric that stalls the electrolyte
     Debye-Huckel term. The reaction kinetics for this route are now in hand (see G4 / Aspen k2).
  Interface either way = apparent-composition handover on the common elements-at-298.15 K enthalpy datum
  (`gap_g6_h0_enthalpy.py`, now including carbamate) with domain-flag propagation.

**Blocking datum:** the urea/ion reactive parameters. The 2026 closure methodology (`Gaps Closure.docx`)
QUANTIFIES the SR-POLAR route's parameter set and its validity box: the Voskov-Voronin (2016) SR-POLAR
binaries for the NH3/CO2/H2O/urea quaternary are regressed at urea-synthesis conditions and bound the
target plant exactly -- T 135-230 C, P 3.5-45 MPa, N/C 2.0-5.5, W/C -0.75..1.2 (covers reactor 180-185 C
/ 140-150 bar / N-C 2.95 and the evaporators). Biuret pure-component data from NIST/DECHEMA with its
vapour pressure + binaries assumed equal to urea's (thermodynamically consistent, no unavailable data).
Pure-component data for NH3/CO2/H2O/urea/carbamate/N2/O2/H2 from the standard AspenPlus databank. So the
route is no longer datum-gated -- the set is OPEN and bounded; what remains is the licensor 100%-load HP
design point (user-supplied) for reconciliation only. Full runtime integration into each HP/LP unit in
flow order is multi-week scope; it is the largest remaining build.

**Acceptance:** every process-mixture phase-equilibrium/enthalpy call reports model, domain status,
fugacity/energy residual, and closes MESH without an empirical split override.

## G4 - HP synthesis loop has signed/pinned surrogate flows

**Evidence:** 322R001 applies `REACT_TEAR_DES`, including signed component corrections, to reconcile
its reduced conversion surrogate. 322E002 uses an anchored flash rather than the reactive Extended-
UNIQUAC package. 322E003 scrubber discharges remain pinned; scalar HPCC/scrubber inventories are not
paired with full component holdups.

**Kinetic core NO LONGER BLOCKED** (`gap_g4_reactor_kinetics.py`). The urea rate constant that was the
blocking datum is now cited from the validated AspenTech Stamicarbon loop model (Aspen urea.pdf sec.5):
the two-reaction scheme `2NH3+CO2<=>CARB` (fast, equilibrium) and `CARB<=>UREA+H2O` (slow) with
`Rate2 = k2{x_CARB - x_UREA x_H2O/K2}`, `k2 = 15e8 exp(-100e6/RT)/V_L` (Arrhenius A=1.5e9, Ea=100
kJ/mol). The standalone module implements the CSTR-in-series / marched-PFR idealisation (11 sieve trays
per this plant's manual; 8 stages Aspen; 10 CSTRs Hamidipour 2005) and VALIDATES against the licensor
data within the 10 % band: equilibrium CO2->urea = 59.0 % at the design point (plant CO2 efficiency
~59 %, Aspen Fig 2 ~57-60 %); conversion RISES with NH3/CO2 and FALLS with H2O/CO2 quantitatively
tracking the manual's conversion charts (Fundamentals Fig 6/8, Aspen Fig 2) with no re-tuning; the
cited k2 reaches equilibrium at reactor residence ("path covered 95 %"); atom balance closes. K2 is
anchored to the strict-source 59 % design conversion; K1 fixes the (secondary) carbamate/free-gas split.
Biuret kinetics in the sim (Ea = 85 kJ/mol, `STRIP_BIU_EA`) are corroborated by the Kaasenbrood
mechanism/data (Gaps2.md) and Chinda et al. 2017 (Ea = 80 kJ/mol), so no change is needed there.
The conservation proof battery is built (`gap_g4_conservation_harness.py`: atom-balance, null-feed,
Jacobian-sparsity; fast self-test PASSES; engine suite gated behind `--engine`, main.py ~13 min load).

**Still open (integration, not data):** convert HPCC + reactor + stripper + scrubber to a simultaneous
(equation-oriented) solve with the four atom balances as explicit constraints, retiring `REACT_TEAR_DES`.
That step needs K1/K2 derived LIVE from SR-POLAR/EOS fugacities (Aspen's method) rather than the
design-anchored calibration used standalone -- i.e. it rides on the G1 plant-wide reactive phase set.
Note the Aspen model itself uses **SR-POLAR EOS**, not electrolyte Extended-UNIQUAC, arguing ionization
is small at 160-200 C / low water; that is the validated industrial alternative to G1's tiered UNIQUAC.

**Acceptance:** zero and perturbed feeds cannot create matter; C/H/N/O close to numerical tolerance;
all outlet vectors respond to inlet changes; no signed correction stream remains.

## G6 - Live registry coverage and H1 enthalpy

**Catalogue half CLOSED** (`gap_g6_static_catalogue.py`): the strict-source design catalogue for every
numbered row is emitted by PARSING (not transcribing) the strict PFD -- 264 unique streams (161 with
mass-% composition, matching the ~163 in-scope), every row tagged `status=static, resolved=False`,
written to `reports/G6_static_stream_catalogue.{json,md}` and kept SEPARATE from the live registry.

**Enthalpy H0 tier DELIVERED** (`gap_g6_h0_enthalpy.py`): the sensible-only enthalpy was correctly
refused (it games the metric), but only the EXCESS term H^E is G1-gated. The formation + sensible +
phase-reference part (ideal solution) is available now from published thermochemistry, on a single
elements-at-298.15 K datum so it is reaction-consistent by construction. Declared-tier enthalpy with a
mandatory `EnthalpyBasis` flag: H0 (now) / H1 (+H^E, per G1 tier) / H2 (plant-reconciled). The 2026
source pass ADDED ammonium carbamate (Voskov 2016 dfH: solid -645.05, liquid -624.32 kJ/mol; Cp as
a+e T^-0.5), so the loop enthalpy is now reaction-consistent through the carbamate node, not only across
the net reaction; and upgraded urea Cp to the Voskov temperature-dependent form (-> ~150 J/mol/K at Tm,
matching the prior constant). Validated against first principles (water datum, latent 44.0, urea fusion
13.9 kJ/mol) AND against this plant's licensor manual: the datum reproduces the manual's reaction
enthalpies -- 2NH3(g)+CO2(g)->carbamate(s) = -159.6 kJ/mol, carbamate(l)->urea(l)+H2O(l) = +18.8 vs the
plant's +15.5 -- confirming reaction-consistency to a few kJ/mol across mixed reference states.

**Still open:** wire H0 into the live registry via the existing `make_stream` `h_kjkg` hook and add the
basis enum field; promote H0 -> H1 as each G1 tier lands; raise live coverage above 55/163 as G1/G4/G9
implement the currently-unmodelled units. Audit reports n(H0)/n(H1)/n(H2), not a single count.

**Acceptance:** every implemented outlet has one producing state, declared consumers, conserved splits,
and a basis-tagged enthalpy; catalogue coverage is reported separately from live connectivity coverage.

## G9 - Vendor/equipment equations

**G9a ejectors - design-duty acceptance now MET against vendor datasheets** (`gap_g9a_ejector_envelope.py`).
The primary-nozzle throat area is FIRST-PRINCIPLES for all units from choked motive flow (A_t not a fit);
the model carries an off-design pull curve (double-choke Munday-Bagster/Huang) and a molecular-weight
entrainment response the constant-omega surrogate lacks. The 2026 datasheet pass LIFTS the former
blocking datum: this plant's Uhde vendor design data sheets (`324F002 Datasheet.pdf` DDS p.2, `324F004
Datasheet.pdf` vacuum-unit stream table p.6) supply complete, mass-consistent duty points, and TWO
independent vendor documents (Uhde DDS + Koerting) AGREE on the motive flows the PFD disputed
(927=600, 929=505 kg/h), so that conflict is resolved in the datasheet's favour under the relaxed-PFD
directive. Adopted vendor duties: 324F002 motive 650 / suction 94 @ 0.20 bar (MW 24.13) / disch 744 @
1.0 bar (650+94=744 exact, omega 0.145); 324F004 motive 600 / suction 634 @ 0.12 bar (MW 21.6) / disch
0.33 bar (omega 1.06). The 324F002 suction (94 kg/h @ 0.20 bar/45 C) equals the vent of primary
condenser 324E002 (100 kg/h, its datasheet) to 6% -- an independent cross-unit validation. Fitted A3/At
= 5.5 (F002) / 32.9 (F004) still STRADDLES/EXCEEDS Huang's refrigeration band (6.44-10.64), confirming
that band does not bound these deep-vacuum steam ejectors.
**Residual (G9a):** only the off-design curve SHAPE -- the mixing bore A3/At wants a second suction-
PRESSURE load (the DDS gives one design point + a 40-100% control range, and 324F005's internal suction
is vendor-optimised/unspecified), so the pull curve stays design-anchored. Not yet wired into main.py's
324 ejector suction ODE -- the documented follow-on.

**G9 condensers + urea evaporators - rating cores BUILT and datasheet-validated** (`gap_g9_evaporator_
condenser.py`, new). The primary vacuum condenser 324E002 has a complete vendor shell-and-tube DDS/PDS
(`324E002 Datasheet.pdf`: surface 1079 m2, duty 25 720 kW, both stream sides, 2329 tubes). Two
independent duty closures fall out of the one sheet: the cooling-water sensible duty m cp dT = 25.75 MW
matches the stated 25.72 MW to 0.1%, and the U-A-LMTD back-calc gives U ~ 640 W/m2K (textbook CW vapour
condenser). The urea evaporator now has a closed mass/component/energy balance (F=L+V, urea non-volatile
so the vapour is water-only and urea is conserved) with an INTRINSIC boiling-point elevation from the
G2-validated neutral-UNIQUAC VLE (reproduces the plant evaporator points within the band) plus the IAPWS
latent heat and LP-steam LMTD, returning water evaporated, steam duty and required U*A per effect.
**Residual (G9 evap):** the per-effect evaporator U*A datasheets (only the condenser sheet 324E002 is in
the source set) to turn the design-U rating into a rating-mode model; and wiring both into the 324
concentration ODEs.

**G9b valve hydraulics:** C_v back-calculable from rated flow and dP with declared single-point
provenance; elevation heads from the P&ID (`Merged_Searchable_PIDs.pdf` now in the source set); trim
characteristic remains open. Not built this pass.

**G9c Unit 335 - droplet solidification physics BUILT** (`gap_g9c_droplet.py`, new). The manual already
lifted Unit 335 to a spec-flow boundary block (product 1750-2000 MTPD; fluidisation air ~340000 m3/h;
sprayer air ~36820 m3/h; recycle 0.40; melt 98.6 wt% @ 140 C / 3.6 bar). This pass adds the droplet
PHYSICS the research methodology specifies: a Lagrangian force balance (weight-buoyancy-drag, Schiller-
Naumann Cd) integrated by RK4, Ranz-Marshall Nu/Sh heat-and-mass transfer with a Stefan-flow blowing
correction, and a fusion plateau anchored to the G6 enthalpy datum (231.4 kJ/kg). Validated: terminal
velocity 3.5-7.6 m/s over 1.0-2.2 mm prills, Nu/Sh >= 2, blowing factor in (0,1), and full solidification
in a finite tower height (6.8-39.7 m) that shrinks monotonically with droplet size. **Residual:** Unit-335
bed/tower geometry, fan curves and screen efficiencies (datasheets not in the source set) for a full
tower rating model, plus wiring.

**Acceptance:** momentum/pressure residuals close against vendor duty points and Unit 335 exposes mass,
component, energy, hydraulic and control states with connected streams.
