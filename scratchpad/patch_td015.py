"""Close TD-013 and the 323 half of TD-014; open TD-015 (the unit-324 half).

TD-014 root cause, found by walking the stream map the user supplied (207 -> 208 -> 301/311 -> 313
-> 302/314 -> 319 -> 317).  The stripper bottoms feeding 323C003 are BIT-FLAT for 6 h while
w_c003 falls at -0.0041 pp/h, so nothing rides in on the feed: the ramp is born in the stage.  It
is an open-loop temperature integrator -- see the patch text below for the identity.
"""
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


# ----------------------------------------------------------------- TECH_DEBT: TD-014 resolution
patch("TECH_DEBT.md",
      "### Dead constants found while auditing (2026-07-23)",
      """### TD-014 — ROOT CAUSE FOUND AND FIXED for unit 323 (2026-07-23)

**It was an open-loop temperature integrator, and the stream map the operator supplied is what
localised it.** Walking 207 → 208 → 301/311 → 313 → 302/314 → 319 → 317 with every node
instrumented showed the stripper bottoms feeding 323C003 **bit-flat for 6 h** while `w_c003` fell
at −0.0041 pp/h. Nothing rides in on the feed: the ramp is born inside the stage. A CSTR with a
2-minute residence and constant inputs cannot ramp for 14 hours, so an input to the stage had to be
moving — and it was the boil-up, falling 5.97 kg/h per hour, perfectly linearly.

**The identity.** Three stages take the energy-limited branch `m_vap = M_DES·(q_avail/Q_DES)`, and
each stage's latent constant is back-solved from that same design duty, `λ = Q_DES/(M_DES/3600)`,
so that dT/dt = 0 at the seed. Put the two together:

    P = q_avail − m_vap·λ/3600
      = q_avail·(1 − M_DES·λ/(3600·Q_DES))
      = q_avail·(1 − 1)
      = 0                       IDENTICALLY, for every q_avail, at every load.

The stage temperature had **no input at all**. Whatever TIC-323007 did to the reboiler was cancelled
exactly by the boil-up it produced, so the PV never moved off the 1e-5 °C residue left by the boot
settle, and its velocity-form integral walked PV-329202 down forever. A velocity increment is
Kc·(dt/Ti)·err, so the walk *rate* is independent of `dt` — which is exactly the tick-invariance
that made this look like a model property rather than an artefact. It was one-sided because the
composition-split branch caps the other direction, which is why the drift is monotone.

Measured, all four stages, over 4 h with the temperatures frozen to five decimals:

| valve | before | after 4 h | after the fix |
|---|---|---|---|
| PIC-329202 (323E002) | 89.99849 | 89.98296 | 89.99974 → 89.99974 (flat) |
| PIC-329208 (323E010) | 39.99900 | 39.98631 | 39.99975 → 39.99975 (flat) |
| PIC-329203 (324E001) | 89.99987 | 89.99687 | still walking — see TD-015 |
| PIC-329212 (324E003) | 89.99997 | 89.99918 | still walking — see TD-015 |

**The fix — a bubble-point relaxation, which 323F004 already used.** The liquid sits at its bubble
point, so the duty not spent boiling walks the holdup toward it over the stage's own residence time.
Substituted back into the ODE it gives exactly `dT/dt = (T_bub − T)/τ`: energy still conserved, and
the temperature is a real state with a real driver.

* **323C003** — bubble point rides the live column pressure PT-323201, which is itself driven by the
  live top-vapour rate, so TIC-323007 now has a correctly-signed plant: more duty → more 305 →
  higher P → higher T_sat → higher T. The composition offset stays frozen at its design value
  because this liquor's vapour is 33 % NH₃ / 50 % CO₂ — its bubble point is 9.8 °C *below* water's
  saturation temperature at 4.1 bar a, a depression Raoult-on-water cannot produce.
* **323F010** — fixed 0.46 bar a vacuum boundary, so pressure is not a lever and **concentration**
  is. That is the real physics of a vacuum evaporator and it makes TIC-323012 what it is on the
  plant: a concentration controller acting through temperature.

**The bubble-point model is Raoult's law on water, with nothing fitted.** `p_H2O = x_H2O·Psat(T)`,
and at the bubble point that equals the stage pressure, so `T_bub = Tsat(P/x_H2O)`. Urea, biuret and
HCHO raise the boiling point purely by diluting the water on a *mole* basis. Checked against the
licensor's own (composition, pressure, temperature) triplets:

| stage | composition | P | Raoult | PFD | error |
|---|---|---|---|---|---|
| 323F010 | 80.00 % urea | 0.46 bar a | 100.3 °C | 99 °C | +1.3 |
| 324E001 | 94.31 % urea | 0.33 bar a | 123.7 °C | 130 °C | −6.3 |
| 324E003 | 97.71 % urea | 0.131 bar a | 132.7 °C | 140 °C | −7.3 |

i.e. it reproduces 88–99 % of a 20–90 °C elevation with no adjustable parameter. The residual is
non-ideality (γ_H2O < 1 at these strengths) and is absorbed by the design anchor, because every call
site uses the **departure** `T_des + [T_bub(live) − T_bub(design)]`. What has to be right for a
control model is the *slope* with composition, and that is what Raoult supplies. It is explicitly
**not** used at 323C003/323F004, where it overshoots by 33 °C and 16 °C because the volatiles set
the bubble point; a test asserts that so nobody unifies the two forms later.

**Result.** Over 6 h with the feed held flat, the least-squares slope at every node of the 323 train
is now **exactly 0.0** in the second half: `w_f010` settles at 79.9635 % and stays there. The
0.037 pp under the PFD-317 anchor is simply where the *live* stripper bottoms put it (55.838 %
against the tabulated 55.867 %), not a drift. Gate: `backend/test_equation_audit_td014.py`.

**Not fixed here:** 324E001 and 324E003 carry the same identity. See TD-015.

---

## TD-015 — the unit-324 evaporators still carry the degenerate temperature ODE

- **Status:** OPEN — root cause identical to TD-014 and fully understood; the fix is blocked on
  controller tuning, not on physics
- **Severity:** B — a slow, bounded-in-practice composition drift; no operator action triggers it
- **Files:** `backend/main.py`, `v1_duty` / `v2_duty` in `step_sim`; `TIC_324001` / `TIC_324002`

`R324_Q1_DES_KW` is the design *latent* load and `R324_LAM_V1` its latent heat, so on the duty
branch `v1_m·λ/3600` cancels `q1_avail` term for term and `P_e001` is identically zero — the same
identity TD-014 removed from 323. Both loops therefore integrate against a plant of zero gain:
measured, PIC-329203 falls 0.00075 %/h and PIC-329212 0.00020 %/h without limit, and the 324E001
melt drifts −0.0011 pp/h.

**Why it is not fixed with TD-014.** Switching the bubble-point closure on gives these loops a real
process gain for the first time. Their tuning (Kc = 2.0 bar/°C, Ti = 120 s) was chosen against a
zero-gain plant, so it carries no information about the real one — and with the closure in, the
loops diverge: measured `T_e003` → 138.5 °C and PV-329212 → 86.6 % within 6 h. With both masters in
**MAN** the same stages are bounded and sit within 0.02 °C of design, which is the proof that this
is a tuning problem and not a model instability.

Two further things were established and should not be re-derived:

1. An explicit-Euler period-2 oscillation appears first (±1e-4 K/tick, growing envelope) because
   `w1_live = urea_in/melt` is an **instantaneous algebraic ratio** that `sol_pin_strength` writes
   straight over the species ODE — so a change in `v1` reaches the bubble point with no holdup delay
   and closes a same-tick loop of gain ≈ 3. A `_lag1` at the separator residence time removes that
   mode; it is not what causes the slow divergence.
2. A first open-loop step test gave K_p ≈ −17.5 °C/bar for TIC-324002 and +8.6 °C/bar for
   TIC-324001, but it was contaminated — the loops had already diverged in the same run — so those
   numbers are **not** usable for tuning.

**Recommended closure.** (a) Add the bubble-point relaxation to `v1_duty`/`v2_duty` exactly as
323C003/323F010 now have it — `R324_E001_TBUB_DES` / `R324_E003_TBUB_DES` already exist and the live
departure is published every tick as `_DIAG['E001']['dTbub']` / `_DIAG['E003']['dTbub']`. (b) From a
**clean** design-state boot, step each master's output in MAN and measure K_p and τ properly.
(c) Retune both masters by lambda tuning at λ ≈ 3τ and record the result in
`Master_PID_Tuning_Constants.md`. (d) Consider dropping the `v_conc` concentration cap at the same
time: with a bubble-point closure the melt strength is self-limiting through T_bub and the cap is
no longer doing physical work.

### Dead constants found while auditing (2026-07-23)""")

print("done")
