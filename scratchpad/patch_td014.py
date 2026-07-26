"""Record TD-014 (the 323 urea ramp) and audit section R-4, plus the pin's own mass fabrication."""
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


patch("TECH_DEBT.md",
      "### Dead constants found while auditing (2026-07-23)",
      """## TD-014 — the 323 train's urea fraction is on a linear ramp that never arrests

- **Status:** OPEN — measured and characterised 2026-07-23, origin not yet located
- **Severity:** B (limits fidelity on long runs; no operator action triggers it)
- **Found by:** adversarial verification of TD-013, which asked the question TD-013 itself had not:
  *does the inlet actually settle?*

`w_f010` (PFD stream 317, the 323F010 outlet feeding 323D002) does not converge. It falls on a
**perfectly linear ramp of −0.0067 pp/h** and shows no sign of stopping:

| t | w_f010 |
|---|---|
| 60 s | 80.0013 % |
| 600 s | 79.9759 % |
| 6 h | 79.9239 % |
| 9.5 h | 79.9008 % |
| 14 h | 79.8704 % |

It is a **model property, not an integration artefact**. The least-squares slope is constant to
0.12 % across 12 h (−0.006694 pp/h in the 1.5–2.5 h window, −0.006686 in the 10.5–13.9 h window),
and it is tick-invariant to 0.4 % (dt = 1.0 → −0.006775; dt = 0.5 → −0.006792; dt = 0.25 →
−0.006801). An exponential fitted to the residual decay implies τ ≈ 8500 h (about a year), i.e.
not a settling transient on any operational timescale.

**It breaks a live assertion, just beyond every test's horizon.** `test_equation_audit_species.py:85`
asserts `|w_f010 − 80.00| < 0.10` pp but settles only 600 s. The real trajectory crosses 0.10 pp at
**≈ 9.5 h** of simulated time. Nothing in the suite runs that long, which is why it has never fired.

**Where the urea goes.** Over 14 h urea falls 0.131 pp while H₂O rises 0.118, Biuret 0.010,
NH₃ 0.003 and CO₂ 0.001 — the four gains sum to 0.131, so the vector is internally consistent and
urea is being displaced **predominantly by water**, not by biuret. The inlet to 323F010 drifts too
(`w_f004`, PFD stream 319, at −0.0044 pp/h), so **the origin is at or upstream of 323F004** and was
not traced further.

**Why it matters now.** It is the deciding constraint on TD-013. Dropping the D002 strength pin
gives the tank correct dynamics, but the tank then tracks this ramp: unpinned D002 sits 0.071 pp
low at 6 h and ~0.131 pp low at 14 h. So the drift must be understood before the pin comes out,
or the OTS acquires a slowly-wandering product spec.

**Separately — the pin is itself a component-mass source.** `sol_pin_strength` rewrites the
urea/water pair at constant total mass, so it fabricates **+0.600 kg of urea per 1000 kg of holdup
per call**, violating C2. Tested as a cause of the ramp and **refuted** (−0.00199 pp/15 min pinned
vs −0.00168 unpinned — comparable), so it is a separate, smaller defect, not this one.

### Dead constants found while auditing (2026-07-23)""")

patch("EQUATION_AUDIT.md",
      """## R-2 — what already rippled correctly""",
      """## R-4 — the 323 urea ramp (new, 2026-07-23) — **OPEN, see TECH_DEBT TD-014**

Asking "does D002's inlet actually settle?" — which R-1's first write-up did not — found that it
does not. `w_f010` falls on a **perfectly linear −0.0067 pp/h ramp**: 80.0013 % at 60 s, 79.9239 %
at 6 h, 79.8704 % at 14 h. Slope constant to 0.12 % over 12 h and tick-invariant to 0.4 %, so it is
a model property rather than an integration artefact.

It breaks `test_equation_audit_species.py:85` (`|w_f010 − 80.00| < 0.10` pp) at **≈ 9.5 h**, which
no test reaches. Urea is displaced predominantly by **water** (over 14 h: urea −0.131 pp; H₂O
+0.118, Biuret +0.010, NH₃ +0.003, CO₂ +0.001, summing to +0.131). `w_f004` drifts too, so the
origin is at or upstream of **323F004**.

This is the deciding constraint on R-1: dropping the D002 pin gives correct tank dynamics but makes
the tank track this ramp (0.071 pp low at 6 h, 0.131 pp at 14 h). The ramp comes first.

## R-2 — what already rippled correctly""")

print("done")
