"""Second correction to TD-013.  My retraction was right about the headline and wrong in detail.

Adversarial verification (workflow run wf_2f2b4963-b57) confirmed the headline -- there is no
3.5-point gap -- but refuted three things I wrote, and it found something I missed.

REFUTED IN MY RETRACTION
  1. "w_f010 delivers 80.00 %."  That was a 60-SECOND reading.  probe_td013.py settles only 240
     ticks before sampling.  w_f010 never stops moving: 80.0013 % at 60 s, 79.9239 % at 6 h,
     79.8704 % at 14 h.
  2. "positive feedback runaway."  Wrong mechanism.  The recursion is a STABLE contraction --
     lambda = 0.999905 < 1 for every dt > 0, so nothing diverges.  The correct description is
     DC-gain amplification of a frozen constant: w* = w_f010 + (A - ref)/mu, 1/mu = tau/dt.
     Because mu = dt/tau, HALVING THE TICK DOUBLES THE ERROR -- which is itself the proof that the
     construction was numerical rather than physical.
  3. My back-solved "0.0003 pp capture error" was fitted to match the observed number, so its
     agreement was circular.  The properly sourced value is the _w_norm residue on the PFD-317 row:
     that row sums to 99.99797, so _w_norm lifts 80.00 to W_S317['Urea'] = 0.8000162403296788 while
     R324_W_IN is exactly 0.80.  A - ref = -1.624e-05, which replayed gives 76.5137 % against the
     reported 76.515 % -- 0.0013 pp, and derived independently rather than back-solved.

DEFECT IN MY OWN EVIDENCE
  The "unpinned" column of scratchpad/probe_td013.py is INERT and proved nothing.  It drives the
  shadow tank with m_in = s.tlag.get("R323_m317", 0.0), and no such tlag key exists, so m_in = 0;
  with m_in = m_vap = m_liq = 0, sol_advance returns its input bit-identically.  I cited that probe
  in three documents.

WHAT WAS MISSED -- and it is the finding that matters
  w_f010 is on a PERFECTLY LINEAR ramp of -0.0067 pp/h that does not arrest: slope constant to
  0.12 % over 12 h, and dt-invariant to 0.4 % (so not numerical).  Its own inlet w_f004 drifts too
  at -0.0044 pp/h, so the origin is at or upstream of 323F004.  Over 14 h urea falls 0.131 pp while
  H2O rises 0.118, Biuret 0.010, NH3 0.003, CO2 0.001 -- urea is being displaced predominantly by
  WATER.  It breaks a live assertion: test_equation_audit_species.py:85 asserts
  |w_f010 - 80.00| < 0.10 pp but settles only 600 s; the real trajectory crosses that at ~9.5 h.

  A separate probe of mine (probe_pin_leak.py) tested whether the pin itself causes the ramp.
  REFUTED: -0.00199 pp/15min pinned vs -0.00168 unpinned, comparable.  The pin is not the cause.
  It IS however a component-mass source in its own right -- it rewrites the urea/water split at
  constant total mass, fabricating +0.600 kg of urea per 1000 kg of holdup per call.
"""
import io

def patch(path, old, new):
    raw = io.open(path, encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    s = raw.replace("\r\n", "\n")
    if s.count(old) != 1:
        raise SystemExit(f"FAILED {path}: {s.count(old)} matches for {old[:70]!r}")
    s = s.replace(old, new)
    if crlf:
        s = s.replace("\n", "\r\n")
    io.open(path, "w", encoding="utf-8", newline="").write(s)
    print("patched", path)


# ---------------------------------------------------------------- TECH_DEBT.md
patch("TECH_DEBT.md",
"""* `w_f010` — the 323F010 outlet, which is 323D002 Comp-I's **only** inlet — measures
  **80.0014 % urea**, i.e. on the PFD stream-317 anchor of 80.00. The tank has one inlet, one
  outlet, no reaction and no vapour, so at steady state it *must* equal that inlet.""",
"""* `w_f010` — the 323F010 outlet, which is 323D002 Comp-I's **only** inlet — reads
  **80.0014 % urea** after 60 s. **Caveat, added after adversarial review: that is a transient
  reading, not a steady state** (see "Second correction" below). The tank structure is confirmed
  exactly single-inlet / single-outlet / no reaction / no vapour, and `w = w_in` is an exact fixed
  point of `sol_advance` for every holdup, flow and `dt` — so the tank tracks its inlet. What it
  does *not* do is converge to 80.00, because the inlet itself never settles.""")

patch("TECH_DEBT.md",
"""Only the last two survive. Choosing between them is a modelling decision, not a bug fix — see
"Open question" below.""",
"""Only the last two survive. Choosing between them is a modelling decision, not a bug fix.

### Second correction — the mechanism, and the drift that was missed

Adversarial verification confirmed the headline (no 3.5-point gap) but refuted three details:

1. **"positive feedback runaway" is the wrong mechanism.** The recursion is a *stable contraction*
   — λ = 0.999905 < 1 for every `dt` > 0, so nothing diverges. The right description is **DC-gain
   amplification of a frozen constant**: `w* = w_f010 + (A − ref)/μ` with `1/μ = τ/dt`. Because
   μ = dt/τ, **halving the tick doubles the error** (1/μ = 10 495 at dt = 0.25, 5 248 at 0.5,
   2 624 at 1.0) — which is itself the proof that the construction was numerical, not physical.
2. **The capture error is properly sourced, not back-solved.** My "0.0003 pp" was fitted to match
   the observed value, so its agreement was circular. The real figure is the `_w_norm` residue on
   the PFD-317 row: that row sums to 99.99797, so `_w_norm` lifts 80.00 to
   `W_S317['Urea'] = 0.8000162403296788` while `R324_W_IN` is exactly 0.80. A − ref = −1.624e-05,
   which replayed reproduces **76.5137 %** against the reported 76.515 — 0.0013 pp, derived
   independently.
3. **`scratchpad/probe_td013.py`'s "unpinned" column is inert and proved nothing.** It drives its
   shadow tank with `m_in = s.tlag.get("R323_m317", 0.0)`; no such key exists, so m_in = 0 and
   `sol_advance` returns its input unchanged. That probe was cited as evidence in three documents.

**And the finding that was missed — see TD-014.** `w_f010` is on a perfectly linear ramp of
**−0.0067 pp/h that never arrests**. That is what actually governs the choice above.""")

# ---------------------------------------------------------------- EQUATION_AUDIT.md
patch("EQUATION_AUDIT.md",
"""* `w_f010` — 323F010's outlet, and 323D002 Comp-I's *only* inlet — is **80.0014 % urea**, on the
  PFD anchor. One inlet, one outlet, no reaction, no vapour ⇒ the tank must converge to it.""",
"""* `w_f010` — 323F010's outlet, and 323D002 Comp-I's *only* inlet — reads **80.0014 % urea** at
  60 s. **That is a transient, not a steady state** (adversarial review; see R-4). The tank
  structure is confirmed single-inlet / single-outlet / no reaction / no vapour, and `w = w_in` is
  an exact fixed point of `sol_advance`, so the tank tracks its inlet — but the inlet never
  settles, so "it must converge to 80.00" does not follow.""")

print("done")
