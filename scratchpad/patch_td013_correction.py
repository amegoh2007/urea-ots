"""Retract the false half of TD-013 across every document that carries it.

Published last turn: "the 323 mass balance genuinely does not land on 80.00, so the pin has been
masking a 3.5-point gap."  That is WRONG and must not stand.

Measured since:
  * w_f010 (323F010 outlet = 323D002's only inlet) = 80.0014 % urea -- ON the PFD anchor.
  * 323D002 Comp-I exchanges alpha = 9.5e-5 of its holdup per tick, so any additive correction
    applied inside its own integration loop is amplified by 1/alpha = 10 495.
  * Replaying the reverted recursion with a capture error of 0.0003 percentage points converges to
    76.5150 % -- the observed number, to four decimals.

So the 3.5 points were manufactured by the patch, not found in the plant.  The ripple break itself
(0 of unit 324's 66 leaves responding) is real and stands.
"""
import io

FALSE_CLAIM_SNIPPETS = []
EDITS = []

# ------------------------------------------------------------------ TECH_DEBT.md
EDITS.append((
    "TECH_DEBT.md",
    """2. **The 323 mass balance does not actually land on 80.00.** Carrying the live deviation instead of
   overwriting drives D002 to **76.515 %**, a 3.5-point miss against PFD stream 317. The pin's
   docstring calls it a guard against "residual percentage rounding"; 3.5 points is not rounding.

The attempted fix (design anchor + live deviation, bit-exact at the seed) restored the ripple
correctly but failed four design-point tests on that anchor, and was **reverted** — breaking the §0
PFD anchor is worse than the ripple break it cures. The order of work matters: reconcile the 323
balance first, then un-freeze the pin.

Why it stayed hidden: Comp-I holdup is ~92 t against ~93 t/h throughput, so tau is about an hour and
no test runs long enough to see the tank converge.""",
    """2. ~~The 323 mass balance does not land on 80.00 — a 3.5-point gap.~~ **RETRACTED 2026-07-23.**

### Retraction — the "3.5-point gap" was my own bug, not a plant defect

The first write-up of this item claimed the 323 balance misses the PFD anchor by 3.5 points and
that the pin had been masking it. **That is false.** Three measurements settle it:

* `w_f010` — the 323F010 outlet, which is 323D002 Comp-I's **only** inlet — measures
  **80.0014 % urea**, i.e. on the PFD stream-317 anchor of 80.00. The tank has one inlet, one
  outlet, no reaction and no vapour, so at steady state it *must* equal that inlet.
* Comp-I holds 67 600 kg against a 92 749 kg/h draw, so it exchanges only
  **α = 9.5 × 10⁻⁵ of its holdup per tick**. The reverted patch measured its deviation against a
  reference captured *once*, then fed the result back into the state that produced it — a linear
  recursion whose fixed point is `w* = (A − ref)/α + w_f010`. **Any** constant inside that loop is
  amplified by **1/α ≈ 10 495**.
* Replaying that recursion with a capture error of **0.0003 percentage points** converges to
  **76.5150 %** — the observed failure value, to four decimals.

So the 3.5 points were manufactured by the patch. `scratchpad/probe_td013.py` and
`probe_td013_recursion.py` carry the arithmetic.

### What this rules out

The amplification is the real constraint on any fix, and it eliminates a whole class:

| form | fixed point | verdict |
|---|---|---|
| `auth = w_bal + (A − ref)` (the reverted patch) | `w_f010 + (A−ref)/α` | **amplified ×10 495** |
| `auth = w_bal + constant_offset` | `w_f010 + offset/α` | **amplified** |
| `auth = w_bal · constant_ratio` | badly offset | **amplified** |
| `auth = A + (w_f010 − W_F010_DES)` | `A` at design, tracks inlet | stable, but no tank lag |
| no pin at all | `w_f010` | stable, correct lag |

Only the last two survive. Choosing between them is a modelling decision, not a bug fix — see
"Open question" below.

Why the ripple break stayed hidden: Comp-I's time constant is ~44 min and no test runs long enough
to watch the tank converge.""",
))

# ------------------------------------------------------------------ EQUATION_AUDIT.md
EDITS.append((
    "EQUATION_AUDIT.md",
    """But it also walked D002's urea fraction to **76.515 % against the PFD stream-317 anchor of 80.00**,
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
    """But it also walked D002's urea fraction to **76.515 %** against the PFD stream-317 anchor of
80.00, failing four design-point tests (`test_design_fixed_point_holds`,
`test_design_point_does_not_drift`, `test_design_compositions_sit_on_their_pfd_anchors`,
`test_species_layer_does_not_perturb_the_mass_or_energy_balance`), and was reverted.

**RETRACTION.** The first write-up read that as "the 323 balance genuinely misses 80.00 by 3.5
points, and the pin has been masking it". **That was wrong, and it was my own bug.** Measurements:

* `w_f010` — 323F010's outlet, and 323D002 Comp-I's *only* inlet — is **80.0014 % urea**, on the
  PFD anchor. One inlet, one outlet, no reaction, no vapour ⇒ the tank must converge to it.
* Comp-I holds 67 600 kg against a 92 749 kg/h draw, so it turns over only **α = 9.5 × 10⁻⁵ per
  tick**. The patch measured its deviation against a reference captured once and then fed the
  result back into the state that produced it. That recursion has fixed point
  `w* = (A − ref)/α + w_f010`, so **any** constant inside the loop is amplified by **1/α ≈ 10 495**.
* Replaying it with a capture error of **0.0003 percentage points** lands on **76.5150 %** — the
  observed number to four decimals.

The 3.5 points were manufactured by the patch. **The ripple break itself is real and still open**;
only the explanation was wrong. The amplification is the genuine constraint on any fix: it rules
out every additive or multiplicative in-loop correction, leaving only a non-recursive assignment
from an upstream variable (stable, but the tank then tracks its inlet with no lag) or dropping the
pin entirely (correct dynamics and lag, but D002 inherits whatever `w_f010` does). Choosing between
those is a modelling decision, not a bug fix.""",
))

for path, old, new in EDITS:
    raw = io.open(path, encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    s = raw.replace("\r\n", "\n")
    if s.count(old) != 1:
        raise SystemExit(f"FAILED {path}: matched {s.count(old)} times")
    s = s.replace(old, new)
    if crlf:
        s = s.replace("\n", "\r\n")
    io.open(path, "w", encoding="utf-8", newline="").write(s)
    print("corrected", path)

print("done")
