"""TD-013 CLOSED, and the 323D002 model rebuilt to the vessel's real topology."""
import io


def patch(path, old, new):
    raw = io.open(path, encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    s = raw.replace("\r\n", "\n")
    if s.count(old) != 1:
        raise SystemExit("FAILED %s: %d matches for %r" % (path, s.count(old), old[:70]))
    s = s.replace(old, new)
    if crlf:
        s = s.replace("\n", "\r\n")
    io.open(path, "w", encoding="utf-8", newline="").write(s)
    print("patched", path)


patch("TECH_DEBT.md",
      "### TD-014 — ROOT CAUSE FOUND AND FIXED for unit 323 (2026-07-23)",
      """### TD-013 — CLOSED 2026-07-23, option (c): the pin is gone and the tank is a real vessel

The blocker on option (c) was that `w_f010`, the tank's only inlet, was on an unbounded ramp — so an
unpinned tank would wander with it. That ramp was TD-014 and it is fixed. The inlet is stationary,
the pin has no remaining job, and it was costing two real things: it was the last composition-blind
node between the reactor and the evaporators (audit B1), and it fabricated **+0.600 kg of urea per
1000 kg of holdup per call**, a straight C2 violation. `s.w_d002` is now a plain `sol_advance` and
the tank tracks its inlet with its own residence-time lag.

The design-point test that asserted `|w_D002 − 80.00| < 1e-6` was **asserting the pin, not physics**
— nothing but a hard overwrite can hold a dynamic state to 1e-6. It now carries the same 0.10 pp
band as the inlet it tracks, plus a new and stronger assertion that the two agree to 1e-4.

**The vessel was also modelled as one compartment with a dead-end buffer. It is not.** Operations
supplied the topology and `References/323D002.md` corroborates it:

| | volume | role | instruments |
|---|---|---|---|
| Comp I | 80 m³ | **active** — every feed and discharge nozzle, 323P003A/B suction | LIC-323507, TI-323008 |
| Comp II | 300 m³ | **passive** — fills only by spilling the internal baffle | LI-323504 (indication + alarms only) |

and between them a **field tie-in spool**: a hand valve, not a DCS device, so it has no licensor loop
number. Closed (the default) the two compartments are hydraulically independent and whatever spilled
into Comp II is stranded there. Opened they are connected vessels — equal *head*, not equal mass, so
an equal level fraction — and 323P003 draws the pooled inventory, recovering Comp II into the
forward flow. Modelled as `s.HV_323D002_TIE`, published as `RECIRC_323.D002.HV_tie`, and driven from
screen 323-1 by a clickable OPEN/CLOSED element under the tank (`xv_toggle` id `323D002TIE`).

Opening it against a dry Comp II is a genuine hazard and the model reproduces it: the head
redistributes over 380 m³ instead of 80, so a 10 % Comp-I level collapses to **2.1 %** and 323P003
is left near its cavitation limit. Measured, tie open then shut again after an hour: Comp I refills
to setpoint while Comp II keeps 4.8 % with no way out. That is the scenario the button exists for.

Three constants were wrong and are now sourced:

* **`R323_D002_LVL_SP` 65 % → 10 %.** The small compartment exists to hold residence under ~6 min so
  biuret cannot form — 10 % of 80 m³ is 8 m³ against an 80.6 m³/h feed. At 65 % the model was
  declaring a 39-minute residence and roughly six times the biuret exposure the licensor designed
  for. Source: `References/323D002.md` §3.2.
* **`R323_D002_RHO` 1300 → 1151 kg/m³**, the PFD's own effective density for streams 315/317.
* **Comp II seeded at 50 % → 0 %.** Comp II is dry in normal operation; a 50 % seed silently
  declared a 173 t inventory that the plant would treat as a high-level alarm.

**TI-323008 is a real state now.** It used to publish the upstream separator's temperature verbatim,
so the tank had no thermal inertia and the LOW-temperature alarm it carries — the crystallisation
warning, because a cooling 80 % liquor blocks the 323P003 suction — could never lag or damp
anything. It is a one-inlet/one-outlet energy balance with live cp on both sides, and the bracket is
a literal 0.0 at design.

Gate: `backend/test_equation_audit_td013_d002.py` (11 tests).

---

### TD-014 — ROOT CAUSE FOUND AND FIXED for unit 323 (2026-07-23)""")

print("done")
