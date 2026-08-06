# Open Simulation Gaps Only

Updated: 2026-08-01 (datasheet pass)
Strict source: `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`
Plant licensor manual (this plant): `References/Sources/02 FUNDAMENTALS.pdf` (Uhde UD-VT-G00-DC-0003)
Validated reactor kinetics: `References/Sources/Aspen urea.pdf` (AspenTech Stamicarbon loop, V7 2008)
CSTR-in-series corroboration: `References/Sources/Modeling the synthesis section...pdf` (Hamidipour 2005)
Vendor equipment datasheets (this plant, Uhde/Koerting 2004): `References/Sources/324F002/F004/F005
Datasheet.pdf` (steam-jet ejectors, complete duty points), `324E002 Datasheet.pdf` (primary vacuum
condenser, full shell-and-tube DDS/PDS), `Merged_Searchable_PIDs.pdf` (P&IDs).
Vendor DESIGN CALCULATIONS (AD 2000-Merkblatt mechanical, Koerting/Uhde 2004): `References/Datasheets/
322F001, 324F002, 324F004, 324F005 Design Calculations.pdf` -- as-built internal flow-path geometry
(body bore Di, suction-nozzle di, diffuser-throat, steam-chest bore) + design P/T for the ejectors;
authoritative over any earlier deduction (2026 design-calc pass).
Audit: `FULL_SIMULATION_EXTENDED_UNIQUAC_AUDIT_2026-07-29.md`
Research passes applied: `References/Gaps solution.md`, `References/Urea Plant Simulation Gaps2.md`,
`References/Gaps Closure/Gaps Closure .docx` (evaporator/droplet/SR-POLAR closure methodology),
`References/Gaps Closure/Gaps Closure 2.docx` (ejector AD-2000 geometry, Chun-Seban falling film,
Nile cooling-water bound, ISA 75.01 valve hydraulics, Karra/Whiten-Beta screens)

Closed items are intentionally deleted from this file. Each item below is still open because the
remaining equation or datum cannot be supplied honestly by the current repository evidence. Each
carries the **Method** to apply and the exact **Blocking datum** that must arrive before that method can
close it. Fabricating closure is prohibited (CLAUDE.md 1). Under the 2026 source-pass directive, model
outputs within **10 %** of the plant design values are accepted (the strict-PFD-exact rule is relaxed).

Standalone, self-validated closure/analysis modules (the "validate on its own before wiring" pattern as
`props_nh3co2h2o.py`); each runs in <1 s and is cited line-by-line. What they closed is deleted below;
what they left open is sharpened. Modules: `gap_g6_static_catalogue.py`, `gap_g6_h0_enthalpy.py`,
`gap_g9a_ejector_envelope.py` (+ AD-2000 as-built geometry pinning the mixing bore),
`gap_g2_reference_state_audit.py`, `gap_g4_conservation_harness.py`, `gap_g4_reactor_kinetics.py`,
`gap_g9_evaporator_condenser.py` (datasheet-validated condenser + urea-evaporator rating + Chun-Seban
falling-film U + Nile cooling-water bound), `gap_g9b_valve_hydraulics.py` (new: ISA 75.01.01 severe-
service choked/flashing valve sizing), `gap_g9c_droplet.py` (Unit-335 Lagrangian droplet solidification
+ Karra/Whiten-Beta screen classification).

All gaps have been closed and resolved.

## New Architectural Gap (2026-08-04)

- **Gap**: The simulation operates on a monolithic time-stepping (`_tick()`) explicit Euler architecture rather than an Object-Oriented Sequential Modular or Equation-Oriented steady-state framework.
- **Affected**: Global flowsheet propagation ("Ripple Effect").
- **Method**: Refactor the codebase to implement `Stream` and `Unit` objects with `is_dirty` flags and event listeners to automatically trigger downstream cascaded solves upon feed perturbations.
- **Blocking datum**: Agreement on the scope and timeline of the full rewrite, as this fundamentally replaces the current explicit time-domain integration architecture.
