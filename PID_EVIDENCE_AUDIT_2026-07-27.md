# Plant P&ID evidence audit

Date: 2026-07-27
Source: `References/Sources/Merged_Searchable_PIDs.pdf`
Source size: 64,376,867 bytes; 33 pages
SHA-256: `5B963440116DC73B1FDF2B8FD190E6F99CD2A42DEB5651735575FC1ABC9B6DE1`

## Objective and evidence rule

Use the newly supplied plant P&IDs to close topology, nozzle-routing, and instrumentation gaps without
promoting a line drawing into an unsupported hydraulic or thermodynamic model. The evidence precedence
remains:

1. The 1,750-MTPD PFD/process-data table governs stream number, flow, composition, temperature,
   pressure, and duty.
2. The plant P&IDs govern installed equipment connectivity, nozzle identity, line class/nominal size,
   instruments, valves, and drawing-to-drawing continuations.
3. The operator mapping notes connect the PFD stream numbers to the installed P&ID routes.
4. Secondary equipment summaries are informative only where a primary drawing or datasheet supports
   them.

The execution plan was to index all 33 searchable pages, render the sheets containing the open-gap
tags, reconcile those sheets with the PFD and operator maps, and change the model only where the
P&ID supplied every parameter needed by the governing equation.

## Reviewed sheets and dispositions

| PDF page | Plant drawing | Relevant evidence | Disposition |
|---:|---|---|---|
| 4 | P&ID 103/1, `UD-VT-323-FB-0001` | Draws 328V001 and the continuation from its N1 liquid outlet to 328D003 on P&ID 104. | Closes the missing installed intermediate route between 323C005 and 328D003. |
| 5 | P&ID 103/2, `UD-VT-323-FB-0002` | Draws the 323C005 N4 liquid outlet as line `150-AW5-323058` to 328V001 on P&ID 103/1. | Refines the PFD-level shorthand: stream 343 reaches 328D003 through 328V001; it is not a direct pipe from 323C005 to the tank. |
| 7 | P&ID 104, `UD-VT-328-FB-0003` | Draws 328D003 with physical bays `I`, `II`, and `III`; LI-328507 is on bay I and LI-328508 is on bay III. It also shows the N23/N24 hand-valved connection between bays III and II, the pump connections to 322P002/328P003/328P007, and the continuations to 328V001 and the Unit-324 condensers. | Closes the existence, numbering, instrument-location, and installed-nozzle-topology questions. It does **not** provide bay capacities, normal liquid allocation for unnumbered internal transfers, or flash/emissions data. |
| 8 | P&ID 105/1, `UD-VT-324-FB-0003` | Draws 324F002/324E002 and condensate return `150-VPC1-324010` to 328D003; shows the installed barometric-leg/elevation arrangement. | Confirms the implemented E002/ejector topology and return destination. No performance curve or gas-side loss coefficient is present. |
| 9 | P&ID 105/2, `UD-VT-324-FB-0004` | Draws the 324F004-E006-F005-E007 train and the E005/E006/E007 condensate returns `324012`, `324013`, and `324014` to 328D003, including nominal line sizes and minimum vertical arrangements. | Closes line-order, destination, and installed-size/elevation ambiguity. It does not close C40 pressure loss or off-design ejector performance. |
| 10, 19, 26-32 | Unit-335 P&ID sheets, including `UD-VT-335-FB-0002` through `-0010` | Supplies plant equipment, piping, valves, and instrumentation for Unit 335. | Useful for later topology implementation, but a P&ID is not a 1,750-MTPD heat-and-material balance. The quantitative Unit-335 boundary remains open. |

## 328D003 reconciliation

The P&ID resolves the apparent conflict between the two-compartment operating map and the
three-compartment secondary summary:

- 328D003 physically has three labeled bays.
- The two mapped live level inventories correspond to LI-328507 on physical bay I and LI-328508 on
  physical bay III. Physical bay II has no dedicated level indication on P&ID 104.
- Therefore the existing model's `Comp I` is the P&ID bay I. Its historical `Comp II` name means the
  *second mapped live inventory* and must not be read as proof that it is physical bay II; P&ID 104
  associates the second mapped indicator with physical bay III.
- P&IDs 103/1 and 103/2 show the atmospheric-absorber liquid path as
  `323C005 N4 -> 328V001 -> 328D003`. The strict PFD still governs the aggregate stream-343 mass and
  composition across that route. Stream 341 remains the unabsorbed-gas/stack boundary, not a liquid
  feed or a dedicated third-bay stream.
- LI-328507/508 are indications with alarms, not level controllers. No level-control valve is drawn
  for either inventory, so the model's open-loop status remains correct.

The P&ID does **not** validate the secondary report's theoretical 50/30/20 volume split or its
112.2 m3 “vapour disengagement compartment.” Those values remain deductions. Adding a third dynamic
inventory would still require the vessel GA/mechanical drawing or an approved operating-volume basis,
plus the normal state of the N23/N24 connection and any overflow/weir elevations.

## Unit-324 vacuum-train reconciliation

P&IDs 105/1 and 105/2 independently corroborate the implemented sequence and all four individual
condensate returns. They also add installed nominal sizes and minimum vertical/barometric-leg
arrangements. Those facts close topology and static-arrangement uncertainty only.

They do not supply:

- ejector suction-capacity or critical-backpressure curves;
- motive-steam pressure/dryness correction curves or breakdown/recovery hysteresis;
- effective nozzle/mixing loss coefficients;
- complete pipe lengths, fittings, roughness, or measured gas-side pressure drops; or
- plant acceptance points over load.

Consequently, no ejector pull constant or condenser gas-side pressure was changed. The current
PFD-anchored training surrogate remains the most defensible model until vendor or plant-test data are
available.

## Result

The supplied P&IDs close three documentary gaps: the existence and numbering of all 328D003 bays,
the actual 323C005-to-328D003 route through 328V001, and the installed Unit-324
ejector/condenser/condensate-return topology. They narrow, but do not close, the remaining 328D003
dynamic-volume and C40 performance gaps. They also establish Unit-335 plant topology without
supplying the missing 1,750-MTPD quantitative basis.
