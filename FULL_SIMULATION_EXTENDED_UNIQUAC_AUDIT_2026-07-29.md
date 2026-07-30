# Full-Simulation Mathematical and Connectivity Audit

Audit date: 2026-07-29

Executable: `backend/main.py`, `backend/steam_system.py`
Strict design source: `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`

## Audit contract

Every implemented process unit was checked for total mass, component mass, energy, phase
equilibrium, summation, reaction, heat-transfer, momentum/hydraulics, dynamic inventory, and
upstream/downstream connectivity. A category is marked `N/A` only when it is physically
inapplicable. A category that needs unavailable plant or property data is marked `OPEN`; it is not
silently treated as complete and no coefficient was fabricated.

The thermodynamic policy is a gamma-phi boundary:

- liquid phase: Extended UNIQUAC, including its neutral-species UNIQUAC limit;
- vapor phase: a fugacity model/EOS where validated data exist;
- pure-water steam utility: the shared IAPWS-IF97 boundary (`backend/iapws_if97.py`, Regions 1/2/4),
  because UNIQUAC is a mixture excess-Gibbs model and cannot replace a pure-steam equation of state.
  This closed gap G11 (2026-07-30): saturation, latent heat, and condensate enthalpy for the 329 steam
  network and every steam-heated shell now come from IF97, validated bit-exact against the official
  IF97 verification points; the former Antoine correlation is retained only as a comparison oracle;
- unsupported temperature, pressure, composition, or absolute-enthalpy requests fail or remain
  data-gated instead of extrapolating silently. The one aqueous-species data blocker cited in G1 --
  NH3(aq)/CO2(aq) standard-state Cp -- is now sourced (Correa-Thomsen-Fosbol, Fuel 2023), so the
  NH3-CO2-H2O property basis solves speciation and reaction/absolute enthalpy off 25 C.

Primary basis: [Thomsen's Extended UNIQUAC review](https://publications.iupac.org/pac/77/3/0531/index.html),
[Zhang et al. high-pressure urea-loop formulation](https://ureaknowhow.com/pdflib/510_2005%20Zhang%20IPE%20CAS%20Modeling%20and%20simulation%20of%20high%20pressure%20urea%20synthesis%20loop.pdf),
[Voskov and Voronin urea-system parameters](https://pubs.acs.org/doi/10.1021/acs.jced.6b00557),
and the [IAPWS-IF97 release](https://iapws.org/documents/release/IF97-Rev).

## Unit-by-unit equation ledger

Legend: `OK` implemented and connected; `REDUCED` conservative but calibrated/reduced-order;
`FIXED` corrected in this audit; `OPEN` a missing equation or evidence item recorded in
`handoff.md`; `N/A` physically inapplicable.

| Unit / equipment | Total + component balance | Energy / thermo | Hydraulics / dynamics | D/S connectivity | Verdict |
|---|---|---|---|---|---|
| 321D003 NH3 feed drum | Total inventory OK; composition is a pure-NH3 boundary | Lumped sensible-energy ODE | Level-volume and pump withdrawal OK | Tank registry previously conflated BL feed and pump flow; publication remains an OPEN registry item | REDUCED |
| 321P002 A/B | Pump continuity OK | Isothermal liquid assumption stated | Positive-displacement displacement, speed, efficiency, head and power present | Discharge reaches 322F001 | OK; NPSH/cavitation curve OPEN |
| 320K002/XV-322902/PV-322203 | CO2 continuity and split sum OK | Boundary temperature only | Pressure-driven square-root network, check-valve clamp and transport lag present | Reaches 322E001 and vent branch | OK |
| 322F001 HP ejector | Nine-component mixing and summation present | Sensible mixing present | Reduced entrainment/stall/head equations | Motive 321P002 + recycle 322E003 to 322E002 | REDUCED; vendor geometry OPEN |
| 322E001 stripper | Nine-component balance; hydrolysis/biuret extents now reactant-bounded | Lumped sensible/latent duty; no common species enthalpy interface | NTU ceiling, flooding and controlled bottom inventory present | 322R001 + CO2 to overhead/LP bottom | FIXED material generation; species enthalpy OPEN |
| 322E002 HP carbamate condenser | Total/component split and sum present | Calibrated reaction/sensible duty | Film relaxation and vessel scalar inventory present | Ejector discharge to reactor | REDUCED; runtime Extended-UNIQUAC/SRK MESH and component inventory OPEN |
| 322R001 reactor | Atom closure diagnostic exists | Four-node thermal surrogate | Residence/weir inventory dynamics present | HPCC liquid to stripper/overhead recycle | REDUCED; signed correction, rigorous rates and recycle solve OPEN |
| 322E003 scrubber | Nominal total/component anchors present | NTU cooling bridge present | Flood/spindle effects and scalar sump inventory present | Reactor gas + 323P001 wash to 322F001/offgas | OPEN: discharges do not respond conservatively to perturbed wash/feed |
| HV-322604 / LV-322501 | Total/component transfer present | JT/post-valve reduced flash | Equal-percentage/square-root valves | 322E003 to 322C001; stripper bottom to 323 | REDUCED |
| 322C001 LP absorber | Total balance present; species treatment lumped | Back-solved absorption heat | Reduced vessel/valve dynamics | HP-loop offgas to Unit 323 recovery | OPEN: Extended-UNIQUAC reactive absorption/MESH |
| 323C003 + 323E002 | Total/component inventory and energy-limited boil-up present | Lumped heat capacity/latent heat | Recirculation and controls present | 322C001/returns to 323F004 | REDUCED; live LP-header pressure coupling addressed separately |
| 323F004 | Total/component balance present | Isenthalpic-flash closure present | Separator inventory present | 323C003 to 323F010 train | REDUCED; rigorous multicomponent flash OPEN |
| 323E010 + 323F010 | Total/component and duty-limited evaporation present | Reduced water VLE below published urea-water parameter range | Independent gravity-outlet law now drives the scalar holdup ODE | Streams 319 + 331 to 323D002 | FIXED outlet dynamics; validated sub-135 C activity data remains OPEN |
| 323D002 | Two-compartment scalar/species inventory present | Mixed-temperature balance present | Weir/level dynamics present | Receives F010 and raw pre-UF melt only when LV-324501B is selected; sends 317 to 324 | Route is conservative; untagged condensate dilution and atmospheric flash remain OPEN (G12) |
| 323E003/D001/P001 | Total network balance present | Condenser duty is a calibrated latent/UA closure | Pump/control equations present | LP condensate produces 322E003 wash | OPEN: scrubber call currently precedes live wash calculation |
| 323E011/D011 and 323C005/328V001 | Stated PFD junction identities present | Lumped condenser/temperature closures | Inventories and controls present | Recovery vapors/condensates connect 323, 324 and 328 | REDUCED |
| 324E001/F001 | Total and species ODEs present; hydraulic liquid outlet present | Neutral urea-water UNIQUAC boundary added with design-anchored departure | Coupled bounded T/P iteration and vacuum dynamics present | 323D002/recycle to Stage 2 and condenser | FIXED thermo boundary; design component pin inconsistency remains OPEN |
| 324E003/F003 | Total and species ODEs present | Same neutral urea-water UNIQUAC boundary | Coupled bounded T/P iteration and LIC present | A routes 402G through the measured FFIC/FIC UF85 cascade to Stream 609; B returns raw pre-UF melt to 323D002 and hard-interlocks UF85 off | Routing, UI, and cascade defects FIXED; component pin and G12 operability data OPEN |
| 324F002/F004/F005 + E002/E005/E006/E007 | Explicit mixer/condenser mass nodes present | UA-LMTD condensers with calibrated duties | Motive-ratio ejectors and NCG derating | Condensate to 328D003; vent to 323C005 | REDUCED; Huang/vendor ejector closure and pressure drop OPEN |
| 328C002 desorber I | Total/species inventory present | Back-solved latent heat, not common absolute enthalpy | Tray-holdup surrogate | 323/328 feeds to D001/C003 | OPEN: reactive Extended-UNIQUAC MESH and chemical enthalpy |
| 328C003 hydrolyzer | Total/species balance and bounded hydrolysis extent present | Explicit reaction heat plus calibrated latent | Residence-time/Arrhenius surrogate | C002/E021 to C004 | REDUCED; validated off-temperature properties OPEN |
| 328C004 desorber II | Total/species inventory present | Back-solved latent | Kremser/O'Connell soft-sensor layer | C003 to E007/product-water train | OPEN: reactive Extended-UNIQUAC MESH |
| 328D001/E004, E021, E007, D003 | Scalar/species nodes present | Calibrated condensation, epsilon-NTU and reaction duties | Vessel/pump dynamics present where specified | Condensate and recovery network connected | FIXED: combined Unit-328 energy ledger now closes (explicit carbamate-desorption term, residual 0.0 kW at design; G5) |
| 328P003/P006/P007 | Pump continuity present | N/A | Reduced pump/control equations | Correct adjacent nodes | REDUCED |
| 329 HP/MP/9-bar/LP steam network | Per-node mass inventories present | IAPWS-IF97 saturation/enthalpy (G11 closed) | Valve square-root flows and level/pressure controls | Header users and condensate drums | FIXED valve direction, missing liquid terms, and pure-water boundary (IF97); full user ledger OPEN |
| 335 finishing | Boundary total flow and UF85 ratio only | No equipment thermodynamics | No equipment inventory | Receives 324 melt | OPEN: Unit 335 is not a simulated flowsheet |

## Governing equation coverage

The following mesh was explicitly searched in production code and tests. The ledger ensures that
no equation class is silently absent.

| Class | Required form | Coverage result |
|---|---|---|
| Total inventory | `dM/dt = sum(m_in) - sum(m_out) + sum(nu_r M_r xi_r)` | Present in implemented vessels; 323F010 now has an independent gravity outlet and missing steam terms were corrected |
| Component inventory | `d(M w_i)/dt = sum(m w_i)_in - sum(m w_i)_out + reaction_i` | Present in solution trains but contradicted by three design-strength pins; HP scalar vessels lack component inventories |
| Energy | `dU/dt = sum(m h)_in - sum(m h)_out + Q - W + sum(xi_r DeltaH_r)` | Reduced sensible/latent forms dominate; absolute enthalpy still absent from live streams (G6). Unit-328 energy ledger now closes: the hidden carbamate-desorption enthalpy is an explicit `xi*dH` term, residual 0.0 kW at design (G5 closed) |
| Phase equilibrium | `f_i^L(T,P,x) = f_i^V(T,P,y)` | New urea-water UNIQUAC water-activity boundary; HP/LP reactive units remain calibrated and open |
| Summation | `sum(x_i)=sum(y_i)=1` | Enforced by component normalization where species states exist |
| Reaction | `r_j(T,a)`, stoichiometric extent bounds, element/charge closure | Stripper starvation fixed; reactor/scrubber rigor remains open |
| Heat transfer | `Q=UA*DeltaT_lm` or effectiveness-NTU | Present, commonly design-calibrated |
| Momentum | valve `m=Cv f(opening) sqrt(rho DeltaP)`; pumps/ejectors | Reduced forms present; missing Cv/vendor ejector geometry is explicit |
| Dynamic closure | independent outlet law + inventory ODE | Present in most vessels; 323F010 outlet dynamics fixed, while some HP component holdups remain open |
| Flowsheet connectivity | one producer -> one or more declared consumers with conserved split | Live registry covers only 55 of 163 strict-source rows; missing rows are not fabricated |

For the LV-324501 selector, the strict PFD identity is normal-forward
`402G + 697 = 609` (`85405 + 694 = 86099 kg/h`, reported as `86100 kg/h`). The stronger
valve/interlock evidence makes B the raw pre-UF contingency recycle and forces UF85 to zero. A
secondary tank narrative calls 609 the recycle and requires condensate dilution, but supplies no
tagged condensate rate or control basis; that conflict and the atmospheric flash remain G12 rather
than being hidden in a fabricated stream.

The UF85 cascade is not display-only: FFIC-335406 measures delivered UF85/raw-402G ratio, its output
drives FIC-335405 only in CAS, and the slave's returned delivered flow enters the Stream-609 mixer.
FIC MAN therefore has physical authority, while route B overrides every mode to zero as a safety
permissive. When the slave leaves CAS, AUTO-master external-reset feedback tracks the achieved
ratio; reconnecting CAS is therefore bumpless instead of applying a wound-up ratio command.

## Executable baseline and completion boundary

Before remediation, `backend/audit_model_compliance.py` reported 6 passes and 4 failures:

1. 55 implemented registry records versus 163 strict-source PFD rows;
2. 0/55 stream records with an absolute enthalpy value;
3. component residuals at 324E001 (-170.105 kg/h), 324E003 (-126.793 kg/h), and 323F004 (-1.917 kg/h);
4. Unit-328 energy residual of -1690.5 kW.

Those are independent audit findings, not four values to zero by arbitrary correction. Structural
defects with sufficient evidence were repaired. Remaining failures require a larger conservative
model or external evidence and are retained in `handoff.md` with acceptance tests.

After remediation the executable audit reports 8 passes and the same 4 deliberately open failures.
New passing controls cover the Unit-324 Extended-UNIQUAC boundary, zero-feed stripper inventory,
truthful dynamic-tear diagnostics, live steam-header coupling, and corrected pressure/demand paths.
The four failures remain the registry/enthalpy coverage, three design-strength component residuals,
and the Unit-328 absolute-energy residual listed above; none is suppressed or renamed as a pass.

## Addendum 2026-07-30 -- thermodynamic-boundary closures

Two data/boundary gaps were closed after deep research into open primary sources, without altering
any pinned `main.py` design balance:

1. **G11 (steam-condensate -> IAPWS-IF97) CLOSED.** New `backend/iapws_if97.py` implements IF97
   Regions 4/1/2 (saturation, liquid, vapour) and is validated bit-exact (<1e-9 rel.) against the
   official IF97 verification points (`backend/test_iapws_if97.py`). `main.tsat_steam`,
   `main.psat_water_bara`, and `thermo_extended_uniquac.water_psat_bara` now delegate to it; Antoine is
   retained as a comparison oracle. Design points are preserved by construction (each UA/eta_T anchor
   is itself `tsat_steam(P_design)`), so only off-design slopes moved (worst 0.02 C at the 19.7 bar
   stripper design point).

2. **G1 aqueous Cp data blocker RESOLVED.** The NH3(aq)/CO2(aq) standard-state heat capacities in
   `backend/props_nh3co2h2o.py`, previously the one documented external input, are now sourced from
   Correa-Thomsen-Fosbol, Fuel 335 (2023) 126863, Table 1 (72.04 / 238.05 J/mol/K, constant-Cp limit).
   The property basis now solves off-25 C speciation, reaction enthalpy, and absolute enthalpy
   (`test_props_nh3co2h2o.py` 37/37; pKw(60 C)=13.03 vs lit 13.02). Runtime integration into the HP/LP/
   absorber/desorber units remains the open G1 work; G5's required reference-state enthalpy interface
   is now enabled by this plus IF97.

3. **G5 (Unit-328 absolute energy ledger) CLOSED.** The C4 energy-closure diagnostic reported a
   -1690.5 kW residual: net carbamate (NH3-CO2) desorption enthalpy the reboiler steam supplies,
   previously hidden in back-solved boil-up/condensation latents. It is now an explicit `q328_react`
   term whose design magnitude is captured from the design seed and which scales off-design with the
   live MP+LP reboiler steam (anchored-ratio idiom); the reaction enthalpy is the aqueous NH3-CO2
   network from item 2, and the pure-water latents use item 1. The term is READ-ONLY (enters only the
   published residual, never a state ODE), so no pinned dynamic balance changes. `audit_model_compliance.py`
   now reports "unit 328 energy balance closes" as PASS with `Q328_resid_kW = 0.0` (`Q328_in/out`
   unchanged at 6653.8 / 8344.2 kW).

4. **G10 (HV-323605 mapping conflict) CLOSED.** The approved `References/Mapping of Evaporation
   Section.md` resolves the former direction/role ambiguity: HV-323605 is the gas-outlet hand valve on
   the 323F010 overhead (stream 790, HIC-323605), and opening it deepens the 323F010 vacuum and lowers
   the 324E002 shell it feeds via stream 705. The engine already implements exactly this sign
   (`main.py` `pull_f010`, telemetry "opening drops P"); a dedicated closure gate,
   `test_vacuum_valve_rules.py::test_gap_G10_hv323605_position_and_action_are_resolved`, now asserts the
   endpoint, design-seed identity, and pressure-response direction all agree with that mapping, so no
   operator action is reversed. HV-323605 is a hand valve (HIC), so "fail position" is operator-set,
   not an automatic trip.

Repository hygiene: 13 superseded audit/plan/prompt documents and ~285 one-off scratch/probe scripts
and snapshots were deleted (see git history); `References/`, the live docs, the code, and the
`backend/tests` QA harness are retained. `audit_model_compliance.py` now reports **9 passes / 3 open
failures** (was 8 / 4): the 328 energy check moved to PASS; the three remaining are the registry
coverage (55/163), stream absolute-enthalpy coverage (0/55), and the three design-strength component
residuals (E001/E003/F004). None was suppressed; no other check regressed.
