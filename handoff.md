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

## Trend / Historian Gaps (2026-08-07)

Delivered this session: `historian.py` (914 paths, ~23.8 MB, dual-rate rings) + `trend.js`
(persistent 10-pen window). Design: `docs/superpowers/specs/2026-08-07-trend-system-design.md`.
Open items only:

- **Gap**: 31 indicator slots remain WHITE FRAME, so they cannot be trended — 24 are Unit-335
  (melt/prilling: `335D004`, `335P001A/B`, `335P002`, `335P006`, `335R001A/B`, `FFY-335406`,
  `FIC-335401/335405B/335407`, `FV-335407`, `HIC/HV-335602`, `HV-335609/335610`, `LT-335507`),
  the rest `322E003`, `322P002`, `323P003A/B`, `328P002/P003/P006/P007`, `329P003`,
  `IT-329007`, `IT-329008`, `LT-323506`, `MASTER-SP`, `PY-329207B`, `STARTUP SW`.
  **Method**: bind each tag once its unit is modelled; the historian already records every
  packet leaf, so no trend-side work is needed. **Blocking datum**: the unit models themselves.
- **Gap**: 15 pump/XV overlay elements are client-side toggles with no backend state
  (`329P002A/B`, `329P004A/B`, `329P006A/B`, `329U001-M01/M02`, `XV-322903`, the `EXT-OVR`
  pushbuttons, `TRIP_35_3`), so they carry no digital pen. **Method**: add backend state and a
  `bind`. **Blocking datum**: the 329/335 unit models.
- **Gap**: `Urea OTS — As-Built Mathematical & System Architecture Reference` does not exist in
  this working tree (only inside the stale `backend/.claude/worktrees/` copy), so the CLAUDE.md
  auto-update directive could not be honoured for this change. **Method**: restore or recreate
  the document at repo root. **Blocking datum**: decision on which worktree copy is canonical.
- **Note (not a gap)**: `STREAMS` is excluded from the historian by design — 2346 of 3213
  numeric leaves, composition tables read through the stream popup. One-line change to
  `PATH_EXCLUDE` in `historian.py` if stream trending is ever wanted.
