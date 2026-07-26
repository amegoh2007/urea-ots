# 324F002 / 324F004 / 324F005 Datasheet Audit

Date: 2026-07-26; plant P&ID addendum 2026-07-27
Plant: HFC Helwan NH3/Urea, UAN 01-3042  
Documents reviewed:

- `References/Sources/324F002 Datasheet.pdf`, 9 pages, Rev. 00, issue for order
- `References/Sources/324F004 Datasheet.pdf`, 11 pages, Rev. 00, issue for order
- `References/Sources/324F005 Datasheet.pdf`, 11 pages, Rev. 00, issue for order
- `References/Sources/324F002 datasheet 2.pdf`, 1-page mechanical general-arrangement drawing
- `References/Sources/324F004 Datasheet 2.pdf`, 1-page mechanical general-arrangement drawing,
  stamped `AS BUILT`
- `References/Sources/324F005 Datasheet 2.pdf`, 1-page mechanical general-arrangement drawing,
  stamped `AS BUILT`
- `References/Sources/Merged_Searchable_PIDs.pdf`, P&IDs 105/1 and 105/2

## Verdict

The reviewed drawing and P&ID set **materially assists** and closes several identity, provenance,
operating-state, and fabrication-geometry gaps. It still does **not** close the validated off-design
ejector-law gap.

Together they close the equipment identity, manufacturer, serial numbers, installed topology, line sizes,
design/max stream states, motive-steam requirements, two internally consistent package mass-balance
cases, the F004/F005 body operating states, and much of the F004/F005 fabrication geometry. They do
not include the certified performance curves or factory/field test results needed to derive and
validate a compressible momentum model over the plant operating envelope.

No active flow or pull constant was changed from these sheets. The issue-for-order flows still
conflict with the project's strict 1750-MTPD PFD source, while the mechanical drawings do not state
motive or suction capacity. Selecting one case or reverse-engineering a capacity curve from
fabrication dimensions would violate the no-assumption rule.

## 1. Extracted equipment evidence

### 324F002 — Ejector I

Source: design data sheet page 2; nozzle table page 3; principle sketch page 5.

| Quantity | Suction | Motive | Mixed discharge |
|---|---:|---:|---:|
| Flow, kg/h | 94 | 650 | 744 |
| Temperature, °C | 45 | 146 saturated | 123 |
| Pressure, bar(a) | 0.20 | 4.10 | 1.00 |
| Density, kg/m³ | 0.21 | 2.13 | 0.57 |
| Mean molecular weight, kg/kmol | 24.13 | — | — |

The stated balance is exact: `94 + 650 = 744 kg/h`. The suction gas is H2O/NH3/CO2/inerts.
The specified control range is 40–100%. The line connections are DN80 suction, DN50 motive, and
DN100 discharge. These are flange/pipe sizes, not the internal motive-nozzle throat or diffuser
geometry.

### 324F004 / 324F005 — Ejectors II and III package

Source: 324F004 design sheet page 2 and vacuum-unit description page 6; 324F005 design sheet page 2,
nozzle table page 3, and principle sketch page 5.

| Quantity | Value |
|---|---:|
| 324F004 suction stream 712 normal / maximum | 634 / 761 kg/h |
| 324F004 suction state | 40 °C, 0.122 bar(a), 0.101 kg/m³, MW 21.6 kg/kmol |
| Stream 712 composition, mass % | H2O 48.1, NH3 20.4, CO2 27.9, air 3.6 |
| 324F004 motive stream 927 | 600 kg/h, saturated LP steam, 146 °C, 4.1 bar(a) |
| 324F004 discharge stream 714 temperature | 77 °C |
| 324F005 motive stream 929 | 505 kg/h, saturated LP steam, 146 °C, 4.1 bar(a) |
| 324F005 discharge stream 717 state | 122 °C, 1.05 bar(a) |
| 324E006 condensate stream 721 maximum | 1,300 kg/h at 45 °C |
| 324E007 condensate stream 759 maximum | 535 kg/h at 50 °C |
| Final vent stream 722 maximum | 31.5 kg/h, max. 55 °C, 1.05 bar(a), 1.1 kg/m³ |

The vendor maximum-capacity package balance is recoverable to rounding:

1. `324F004`: `761 + 600 = 1,361 kg/h`.
2. `324E006`: `1,361 - 1,300 = 61 kg/h` remains for 324F005.
3. `324F005`: `61 + 505 = 566 kg/h`.
4. `324E007`: `535 + 31.5 = 566.5 kg/h`; residual is 0.5 kg/h from tabular rounding.

This confirms the physical sequence
`712 → 324F004 → 714 → 324E006 → 715 → 324F005 → 717 → 324E007 → 722`, with condensate drains
721 and 759. It also proves that motive steam must enter the condenser mass and energy balances;
the current aggregate pull boundary is not a complete equipment balance.

### As-built mechanical-drawing evidence

| Tag | Verified identity | Operating data added by drawing | Mechanical evidence |
|---|---|---|---|
| 324F002 | Körting Hannover AG; Steam Ejector / Ejector I; serial `115-4-9674-8`; manufacturer drawing `121000 634010 B`; project UAN `01-3042`; year 2005 | No separate operating point on this drawing | DN80 suction, DN50 motive, DN100 discharge; external arrangement and materials. The motive-nozzle and jet-pump assemblies are identified, but their hydraulic throat/exit dimensions are not detailed. |
| 324F004 | Körting Hannover AG; Ejector II; serial `232-4-503-1`; manufacturer drawing `121000 633375 D`; UAN `01-3042`; `AS BUILT`; year 2005 | Ejector body `0.122 bar(a), 77 °C`; steam chest/nozzle `4.1 bar(a), 145 °C`; motive-steam density `2.2 kg/m³` | DN250 suction, DN100 motive, DN250 discharge; sectional fabrication drawing includes the motive-nozzle assembly and diffuser contour/length/diameter/angle markings. |
| 324F005 | Körting Hannover AG; Ejector III; serial `232-4-503-2`; manufacturer drawing `121000 633377 D`; UAN `01-3042`; `AS BUILT`; year 2005 | Ejector body `0.245 bar(a), 100 °C`; steam chest/nozzle `4.1 bar(a), 145 °C`; motive-steam density `2.2 kg/m³` | DN80 suction, DN80 motive, DN80 discharge; sectional fabrication drawing includes the motive-nozzle assembly and diffuser contour/length/diameter/angle markings. |

The F004/F005 drawings materially improve the geometry evidence, but a fabrication dimension is not
automatically an effective one-dimensional flow area. The drawings do not label nozzle throat,
nozzle exit, nozzle-exit position, effective mixing area, roughness, or loss coefficients as hydraulic
model inputs, and they provide no tolerances or performance correlation tying those dimensions to a
measured capacity. The `0.245 bar(a)` value closes the F005 body operating-pressure point. It does not
explicitly state the F004 discharge, 324E006 shell pressure, or the pressure loss from E006 to F005.

### Plant P&ID evidence

P&ID 105/1 (`UD-VT-324-FB-0003`) and P&ID 105/2 (`UD-VT-324-FB-0004`) independently confirm the
installed F002/E002 and F004/E006/F005/E007 sequence, the individual condensate returns to 328D003,
their nominal line sizes, and the minimum vertical/barometric-leg arrangements. This closes installed
route and destination ambiguity. The drawings do not give complete pipe lengths/fittings/roughness,
effective ejector loss coefficients, or measured pressure drops, so they do not close the gas-side
hydraulic or ejector-performance model.

File-integrity identifiers for the reviewed drawing set:

- F002 drawing SHA-256: `F9426BA161F8C4F1ED9BE921F76FE715A5941D36187EE70C17E872240104B672`
- F004 drawing SHA-256: `7BE6C23F53E04EFA5E83BD7EA727BC5726FE946CDEB58D4EAFA129CC0129B101`
- F005 drawing SHA-256: `16FB8DAA2C8D507A712E6875CCBABD4ECC2D7AE733EF1913E3BBFF433C1605B9`

## 2. Conflict with the strict 1750-MTPD PFD

The PFD case is also internally mass-conservative, but it is not the same design case as the
issue-for-order datasheets.

The user has confirmed that the page-7 **SUEZ II (01-3040)** text is a copied template error. The
revised Körting drawings independently identify UAN `01-3042`, tags 324F002/F004/F005, and the
Helwan ammonia/urea project; F004 and F005 are stamped `AS BUILT`. The SUEZ provenance gap is
therefore closed and the erroneous text is not a model input.

| Stream/equipment | Datasheet | Strict PFD | Difference |
|---|---:|---:|---:|
| 324F002 suction | 94 kg/h | stream 706 = 72 kg/h | +22 kg/h |
| 324F002 motive | 650 kg/h | stream 924 = 390 kg/h | +260 kg/h |
| 324F002 discharge | 744 kg/h | stream 708 = 462 kg/h | +282 kg/h |
| 324F004 suction | 634 normal / 761 max kg/h | stream 712 = 584 kg/h | +50 / +177 kg/h |
| 324F004 motive | stream 927 = 600 kg/h | stream 927 = 1,220 kg/h | −620 kg/h |
| 324F005 motive | stream 929 = 505 kg/h | stream 929 = 180 kg/h | +325 kg/h |
| F004/F005 total motive | 1,105 kg/h | 1,400 kg/h | −295 kg/h |
| 324F004 discharge temperature | 77 °C | stream 714 = 104 °C | −27 K |
| 324F005 discharge temperature | 122 °C | stream 717 = 120 °C | +2 K |

The PFD train closes exactly:

- `584 + 1,220 = 1,804` (stream 714)
- `1,804 = 1,763 + 41` (streams 721 + 715)
- `41 + 180 = 221` (stream 717)
- `221 = 190 + 31` (streams 759 + 722)

The issue-for-order sheets therefore cannot silently replace the PFD anchors. The remaining decision
is whether the simulator represents the final 1750-MTPD PFD case, the earlier vendor guarantee case,
or exposes both as named configurations.

## 3. Gaps these sheets close

- Equipment-specific design and maximum suction loads.
- Motive-steam design flows and thermodynamic states for all three ejectors.
- F002 suction/discharge states and exact single-ejector mass balance.
- F004/F005 package topology and the correct identities of condensate streams 721/759 and vent 722.
- Stream-712 mass composition and molecular weight.
- F005 final discharge pressure and temperature.
- Process connection sizes and external envelope dimensions.
- Evidence that 324E006 and 324E007 must explicitly condense motive steam as well as process vapour.
- Final manufacturer, equipment designation, manufacturer drawing number, serial number, and year.
- Confirmation that `SUEZ II 01-3040` is an erroneous copied scope statement, not this package's
  plant identity.
- As-built F004/F005 sectional fabrication geometry and their body/steam-chest operating states.
- F005 body operating pressure (`0.245 bar(a)`) and temperature (`100 °C`).

## 4. Still missing — required before a validated dynamic law

- Unambiguous effective hydraulic geometry for all three stages: motive-nozzle throat and exit,
  effective area ratio, nozzle-exit position, mixing-plane/mixing-chamber dimensions, flow-path
  roughness, and loss coefficients. F004/F005 now have fabrication contours; F002 still does not.
- 324F004 discharge / 324E006 shell pressure and the E006-to-F005 line pressure drop. F005's body
  point is now known (`0.245 bar(a)`), but the upstream pressure chain is not explicitly guaranteed.
- Critical backpressure or maximum discharge pressure for 324F002, 324F004, and 324F005.
- Pull curves: suction pressure versus equivalent vapour load at several motive pressures.
- Motive-steam consumption/capacity correction curves for pressure, temperature, dryness, and
  molecular-weight changes.
- Motive-steam dryness/quality at the ejector boundary; `saturated LP steam` alone does not establish
  the dry-steam condition required by standard performance testing.
- Guaranteed turndown, break/stall boundary, and restart hysteresis.
- Acceptance-test or plant-test points confirming performance after installation.
- Source-authority decision for the datasheet/PFD conflicts above.
- E006/E007 gas-side pressure loss and condensate/non-condensable separation performance over load.
  Cooling-water states and design duties/UA are now closed separately by the 1,750-MTPD PFD,
  cooling-water map, condenser datasheets, and explicit condenser implementation.

Without these inputs, a law such as `pull ∝ motive × suction pressure` is only a design-anchored
surrogate. It is not a validated compressible-flow or momentum equation and cannot certify C40.

## 5. Deep-research conclusion

The remaining performance gap is equipment-specific, not a missing generic equation:

1. Körting states that ejector performance depends principally on the motive-nozzle and diffuser
   design, and that its ejectors are individually designed for the application. Its staged surface-
   condenser description also confirms that upstream motive steam is condensed so the next ejector
   handles the residual non-condensables. See [Körting jet ejectors](https://www.koerting.de/en/jet-ejectors.html)
   and [Körting multi-stage systems with surface condensers](https://www.koerting.de/en/multi-stage-steam-jet-vacuum-systems-with-surface-condensers.html).
2. ASME PTC 24 identifies the acceptance quantities needed for a steam ejector: capacity versus
   suction pressure, discharge pressure versus suction pressure, motive flow at stated pressure and
   temperature, and breakdown/recovery stability. Those are exactly the serial-specific data absent
   from the supplied drawings. See [ASME PTC 24 - Ejectors](https://www.asme.org/codes-standards/find-codes-standards/ejectors).
3. A modern unsteady 1-D ejector formulation solves mass, momentum, and energy on the primary,
   secondary, and mixing passages, but still calibrates mixing efficiency and passage-loss
   coefficients against experimental or numerical data. See [Van den Berghe et al., 1-D unsteady
   ejector model](https://arxiv.org/abs/2208.07687).
4. For condensing steam, primary research shows that real-fluid/two-phase treatment changes the
   predicted temperature and critical condenser pressure relative to an ideal-gas law. See
   [Kitrattana et al., real-fluid 1-D steam-ejector model](https://www.sciencedirect.com/science/article/abs/pii/S2451904921001773).

No public record was found for Körting serials `115-4-9674-8`, `232-4-503-1`, or `232-4-503-2`, or
for manufacturer drawings `121000 634010 B`, `121000 633375 D`, and `121000 633377 D`. A generic
correlation or another ejector's calibrated coefficients cannot close the Helwan guarantee envelope.
For this NH3/CO2/H2O/inert suction mixture, applying a wet-steam-only model would also require an
unsupported thermodynamic simplification.

## 6. Safe software action

1. Keep the strict PFD case as the active design anchor until source authority is resolved.
2. Preserve the datasheet values as a separate vendor-guarantee evidence set; do not average them.
3. Build the distinct E002/E005/E006/E007 condenser nodes first, because the datasheets prove that
   only uncondensed gas reaches each ejector.
4. Add the explicit F002/F004/F005 mass and enthalpy mixers after the condenser nodes exist.
5. Implement the off-design ejector law only when a vendor curve, internal geometry, or accepted
   plant-test dataset is supplied.

## 7. Exact data request to close C40

Request the following against Körting project `2/115/4/09674` / serial `115-4-9674-8` and project
`2/232/4/00503` / serials `232-4-503-1` and `232-4-503-2`:

- certified ASME-PTC-24-equivalent capacity curves at the actual suction composition;
- suction load versus suction pressure at multiple motive-steam pressures/temperatures/qualities;
- discharge pressure versus suction pressure, including critical backpressure;
- breakdown and recovery points, restart hysteresis, and guaranteed turndown;
- measured motive-steam consumption and its pressure/temperature/dryness corrections;
- the hydraulic flow-path drawing or vendor effective areas: throat, exit, area ratio, nozzle-exit
  position, mixing section, diffuser, roughness, and calibrated loss/efficiency coefficients;
- factory acceptance and commissioning test sheets;
- E006/E007 performance sheets with shell pressure, duty/UA, cooling-water states, condensate load,
  residual-gas load, and gas-side pressure drop.

If the vendor dossier is unavailable, the minimum replacement is a controlled plant test that records
each stage's suction/discharge pressure and temperature, motive pressure/temperature/flow, suction
component flow, cooling-water states, condensate flow, and the breakdown/recovery sweep. Until one of
those datasets is supplied, the current proportional pull law must remain labelled `surrogate`.

## 8. Reference-document corrections made

- `References/324-1 Equipment Descriprion and Datasheet 2.md` contained a synthetic 324F002 pull
  curve derived from assumed shut-off and overload points. The curve was withdrawn because the
  datasheet supplies only one operating point.
- `References/324-1b Equipment Descriprion and Datasheet 2.md` had streams 721 and 722 reversed and
  assigned stream 759 to the wrong condenser. It now matches the vendor package sketch: 721 is the
  324E006 condensate, 759 is the 324E007 condensate, and 722 is the final vent.
- `References/Mapping of Evaporation Section.md` incorrectly reused stream 705 at the 324E002 vent
  and stream 717 at the 324F002 discharge. The PFD-consistent route is 705 into 324E002, 706 into
  324F002, and 708 from 324F002 to 323C005.
