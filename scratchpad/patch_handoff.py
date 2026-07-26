"""Patch handoff.md.  Read as text, normalise CRLF -> LF for matching, restore on write."""
import io

p = "handoff.md"
raw = io.open(p, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")

old_next = """3. **TD-006 second half** — rigorous stripper per-species enthalpy balance. The flooding half is
   done; the enthalpy half is blocked only on sourcing a carbamate dissociation enthalpy and
   NH₃/CO₂ latents at ~183 °C/140 bar. The bit-exactness contract is already written down.
3a. `eta_P` dead lever in `stripper_322e001` — synthesis pressure currently has zero effect on
   stripping efficiency. Small, self-contained, physically wrong; good candidate for a fix slot."""

new_next = """3. **TD-006 — CLOSED 2026-07-23** (`1da9280`), both halves. So is the `eta_P` dead lever, and so
   is the unsourced `STRIP_FLOOD_ETA_K`. See "Remediation slot 8" above.
3a. **TD-012 / C10 — PARTIALLY closed 2026-07-23.** Urea-solution cp and density are live
   correlations and unit 324 uses them per-location. Still open: the **aqueous/water** side (the
   PFD's >150 °C density row runs ~4 % above physical water — analysed in TD-012, unchanged) and
   the volumetric-controller densities. `urea_soln_rho` is in place as the vehicle for that work."""

assert s.count(old_next) == 1, "next-steps block not found"
s = s.replace(old_next, new_next)

marker = "## Standing session commands (CLAUDE.md sections 6/7)"
assert s.count(marker) == 1, "standing-commands marker not found"

slot = """### Remediation slot 8 — 322E001 enthalpy + eta_P (TD-006 CLOSED), commit `1da9280`
The MP-steam duty was proportional to feed **mass**, so composition never entered — identical
tonnages of water and of carbamate-rich liquor demanded identical steam, and carbamate dissociation
(58 % of the duty) was invisible to the header. Now a five-term per-species balance.

**The previous handoff said this was blocked on sourcing a carbamate enthalpy. It was not.**
`HPCC_DH_CARB_KJMOL = 160.0` was already at `main.py:2187`, and one search found the better value:
Frejacques via Brouwer (UreaKnowHow June 2009, p.12) publishes BOTH reactions at *process*
conditions — −117 kJ/mol at 110 atm/160 °C for carbamate, +15.5 kJ/mol at 160–180 °C for urea —
which sit far closer to 144 bar / 172–183 °C than the 159–160 quoted for *solid* carbamate at 25 °C.
NH₃ needs no latent heat at all: it is supercritical here (Tc = 132.4 °C).
**Validation: 37 831 kW against the licensor's 39 400 — 96.0 %, nothing fitted.** Only the ratio is
applied, so the offset cancels and the PFD duty stays the anchor.

That balance then *retired* `STRIP_FLOOD_ETA_K = 1.50` — flagged last session as the one unsourced
number — with **no replacement constant**, because ΔT_flood and the efficiency loss are the same
event measured twice. Three independent cross-checks put the knockdown at 0.8–2.9 %, not the 15 %
the fit gave; it was also double-counting the thermal collapse `g_T` already carries.

`eta_P` was dead because every call site passed the frozen design pressure. Now rides PT-329201,
gated on `_STEAM_READY` — the new feedback path would otherwise have the boot settle capture
`HPCC_UA`/`HPCC_LIQ_DES_LIVE` off a different transient (+305 kg/h, 0.16 %). Waking it also slowed
the N/C settle in `test_equation_audit_322e002`; measured over 40 min it converges monotonically
(span 0.027 by minute 40), and the old 10-minute window straddled the p_syn saturation at minute 6.
Window widened to 25 min **and** a step-decay assertion added, so that test is now stronger.

### Remediation slot 9 — C10 properties + the ripple break, commit `SLOT9SHA`
One cp (2.5 kJ/kg·K) covered every urea solution from 44 % urea to 97.71 % melt — 14–18 % high at
the evaporator ends, 23 % low at the LP end, i.e. most wrong exactly where the model does its most
important work, since the evaporation train's purpose *is* to change composition. cp is
**back-solved** (steam-table cp_water + the model's own anchor) and yields 2.072 kJ/kg·K against a
published molten-urea 2.0–2.1 — corroboration, not assumption. Density is **regressed from the PFD**
(§0 strict source): rho = 972.08 + 255.95·w − 0.4659·(T−100), both signs emergent from the fit.
Both applied as a departure from the anchor, so `ANCHOR + 0.0 == ANCHOR` holds to the bit.

**The ripple audit is the finding worth carrying forward.** Perturbing live state and counting
moving telemetry leaves showed unit 324 responding to an upstream composition step in **0 of its 66
leaves**: `s.w_d002 = sol_pin_strength(..., R324_W_IN)` pinned the tank strength to a CONSTANT, so
every upstream disturbance died in the buffer tank. The block's own comment claimed the opposite.
Fixed by carrying the live deviation off the design anchor; 324 now responds in 13 of 66, first at
tick 39 (the 80 m³ tank lag). Full method and numbers in `EQUATION_AUDIT.md`, audit section R.

**Durable lesson (slots 8-9), and it is the same one three times:**
1. **A dead term passes every gate.** `eta_P` was recomputed each tick from an argument every caller
   froze; `sol_pin_strength` erased the very composition it was documented to preserve. Neither
   showed up in the pin, the suite, or a code read. **Reading code cannot distinguish a live term
   from a dead one — perturb it and count what moves.** `scratchpad/audit_ripple_live.py` is the
   harness; it flattens the telemetry packet to ~1162 scalar leaves and diffs them.
2. **"Blocked on sourcing X" deserves one grep before it is believed.** TD-006's enthalpy half sat
   blocked for a session on a constant that was already in the file.
3. **Check the probe handle is on the live path.** The first ripple pass perturbed
   `STRIP_FEED207_KMOLH` and saw zero response — but that is a *default argument* the live tick
   never reads. A null result from a broken probe looks identical to one from a broken model.

"""
s = s.replace(marker, slot + marker)

if crlf:
    s = s.replace("\n", "\r\n")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("handoff.md updated")
