"""Correct the four docs so they describe what SHIPPED, not what was attempted.

The ripple fix restored propagation but drove D002's urea fraction 3.5 points off the PFD anchor,
so it was reverted.  Docs written before that must not claim it closed.
"""
import io

EDITS = []

# ---------------------------------------------------------------- EQUATION_AUDIT.md
EDITS.append((
    "EQUATION_AUDIT.md",
    "## R-1 — unit 324 was composition-blind — **CLOSED 2026-07-23**",
    "## R-1 — unit 324 is composition-blind — **DIAGNOSED, fix reverted, needs its own slot**",
))
EDITS.append((
    "EQUATION_AUDIT.md",
    """**After:** 246 of 1162 leaves respond and **every unit group in the train** does, unit 324 included
(13 of 66, first at tick 39 — the 80 m³ buffer-tank holdup lag, which is physically right). Melt
strength PY-324201 now moves 94.2 → 93.8 % on that disturbance where it previously could not move
at all.""",
    """**The fix worked, and was reverted anyway.** With the deviation carried, 246 of 1162 leaves
responded and every unit group in the train did, unit 324 included (13 of 66, first at tick 39 —
the 80 m³ buffer-tank holdup lag, physically right); melt strength PY-324201 moved 94.2 → 93.8 %
where it previously could not move at all.

But it also walked D002's urea fraction to **76.515 % against the PFD stream-317 anchor of 80.00**,
failing four design-point tests (`test_design_fixed_point_holds`, `test_design_point_does_not_drift`,
`test_design_compositions_sit_on_their_pfd_anchors`,
`test_species_layer_does_not_perturb_the_mass_or_energy_balance`).

**That 3.5-point gap is the real finding.** The pin is documented as a guard against "residual
percentage rounding" — 3.5 points is not rounding. The 323 train's own mass balance does not land
on the PFD's 80.00, and the pin has been silently absorbing the difference for as long as it has
existed. The ripple break is therefore a *symptom*: un-freezing the pin without first reconciling
the upstream balance trades a hidden composition error for a visible one, and breaking the §0 PFD
anchor is the worse of the two.

Reverted to the hard pin deliberately — not because the fix is wrong in principle. Why this was
never seen: Comp-I holdup is ~92 t against ~93 t/h throughput, so the tank's time constant is about
an hour, and nothing in the suite runs long enough to watch it converge. **Needs its own slot**,
starting from the 323 balance rather than from the pin.""",
))

# ---------------------------------------------------------------- TECH_DEBT.md
EDITS.append((
    "TECH_DEBT.md",
    "### Dead constants found while auditing (2026-07-23)",
    """### TD-013 — the 323D002 strength pin masks a 3.5-point composition gap (opened 2026-07-23)

`s.w_d002 = sol_pin_strength(sol_advance(...), R324_W_IN)` overwrites the 323D002 urea/water pair
with the constant 0.80 every tick. Two consequences, and the second is the serious one:

1. **No upstream composition disturbance reaches unit 324** — measured 0 of its 66 telemetry leaves
   (`EQUATION_AUDIT.md` audit section R).
2. **The 323 mass balance does not actually land on 80.00.** Carrying the live deviation instead of
   overwriting drives D002 to **76.515 %**, a 3.5-point miss against PFD stream 317. The pin's
   docstring calls it a guard against "residual percentage rounding"; 3.5 points is not rounding.

The attempted fix (design anchor + live deviation, bit-exact at the seed) restored the ripple
correctly but failed four design-point tests on that anchor, and was **reverted** — breaking the §0
PFD anchor is worse than the ripple break it cures. The order of work matters: reconcile the 323
balance first, then un-freeze the pin.

Why it stayed hidden: Comp-I holdup is ~92 t against ~93 t/h throughput, so tau is about an hour and
no test runs long enough to see the tank converge.

### Dead constants found while auditing (2026-07-23)""",
))

# ---------------------------------------------------------------- handoff.md
EDITS.append((
    "handoff.md",
    """**The ripple audit is the finding worth carrying forward.** Perturbing live state and counting
moving telemetry leaves showed unit 324 responding to an upstream composition step in **0 of its 66
leaves**: `s.w_d002 = sol_pin_strength(..., R324_W_IN)` pinned the tank strength to a CONSTANT, so
every upstream disturbance died in the buffer tank. The block's own comment claimed the opposite.
Fixed by carrying the live deviation off the design anchor; 324 now responds in 13 of 66, first at
tick 39 (the 80 m³ tank lag). Full method and numbers in `EQUATION_AUDIT.md`, audit section R.""",
    """**The ripple audit is the finding worth carrying forward — and it is NOT fixed.** Perturbing
live state and counting moving telemetry leaves showed unit 324 responding to an upstream
composition step in **0 of its 66 leaves**: `s.w_d002 = sol_pin_strength(..., R324_W_IN)` pins the
tank strength to a CONSTANT, so every upstream disturbance dies in the buffer tank. The block's own
comment claims the opposite.

Carrying the live deviation instead **did** restore the ripple (324 → 13 of 66, first at tick 39,
the 80 m³ tank lag) — but it also walked D002 to **76.515 % urea against the PFD stream-317 anchor
of 80.00**, failing four design-point tests. **That 3.5-point gap is the real finding**: the pin is
documented as a rounding guard, and 3.5 points is not rounding — the 323 balance genuinely does not
land on 80.00 and the pin has been absorbing the difference. **Reverted**, because breaking the §0
PFD anchor is worse than the ripple break. Now TD-013; reconcile the 323 balance first, then
un-freeze the pin. It stayed hidden because Comp-I tau is ~1 h and no test runs that long.""",
))

# ---------------------------------------------------------------- As-Built reference
AB = "Urea OTS — As-Built Mathematical & System Architecture Reference.md"
EDITS.append((
    AB,
    """which is exactly $W_{IN}$ at the seed. After the fix 246 leaves respond and **every unit group in
the train** does, unit 324 included at 13 of 66, first responding at tick 39 — the 80 m³ buffer-tank
holdup lag, which is physically correct.""",
    """which is exactly $W_{IN}$ at the seed. With it, 246 leaves respond and **every unit group in the
train** does, unit 324 included at 13 of 66, first responding at tick 39 — the 80 m³ buffer-tank
holdup lag, which is physically correct.

**This change was REVERTED, and the reason is the finding.** It also drove $w^{urea}_{D002}$ to
76.515 % against the PFD stream-317 anchor of 80.00, failing four design-point tests. The pin is
documented as a guard against *residual percentage rounding* — 3.5 points is not rounding. The 323
train's mass balance does not land on 80.00, and the pin has been silently absorbing the gap. So
the ripple break is a **symptom**: un-freezing the pin without first reconciling the upstream
balance merely trades a hidden composition error for a visible one, and violating §0 at the design
point is the worse trade. Carried as **TD-013**; the 323 balance is the place to start. It stayed
hidden because Comp-I holdup is ~92 t against ~93 t/h, so the tank's time constant is about an hour
and no test in the suite runs long enough to watch it converge.""",
))
EDITS.append((
    AB,
    """pin is kept for its §0 job but now carries the live deviation; 324 responds in 13 of 66, first at
tick 39 (the 80 m³ tank lag). See Revision Delta #21. |""",
    """attempted fix carried the live deviation and did restore the ripple (324 → 13 of 66, first at tick
39, the 80 m³ tank lag) — but it drove D002 to 76.515 % urea against the PFD stream-317 anchor of
80.00 and was **reverted**: the pin's "rounding guard" docstring is masking a real 3.5-point gap in
the 323 balance, and breaking §0 is the worse trade. Carried as TD-013. See Revision Delta #21. |""",
))

for path, old, new in EDITS:
    raw = io.open(path, encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    s = raw.replace("\r\n", "\n")
    if s.count(old) != 1:
        raise SystemExit(f"FAILED {path}: matched {s.count(old)} times for {old[:60]!r}")
    s = s.replace(old, new)
    if crlf:
        s = s.replace("\n", "\r\n")
    io.open(path, "w", encoding="utf-8", newline="").write(s)
    print("patched", path)
print("all docs corrected")
