"""TD-015 CLOSED -- the unit-324 half, including the retune the fix turned out to require.

Sequence worth recording, because it is the reason the 324 half could not stay deferred:
dropping the 323D002 strength pin (TD-013) removed an ACCIDENTAL CLAMP.  With the tank pinned at
exactly 0.80, urea1_in was constant and v1_conc sat within 0.4 kg/h of v1_duty, so the min() tie
gave TIC-324001 partial feedback and masked the degenerate ODE.  Unpinned, the two branches
separate by ~74 kg/h and the melt walks at ~0.5 pp/h -- far worse than the 0.0011 pp/h measured
while the pin was in place.  So TD-015 became the blocker on TD-013 rather than a follow-up.
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


# ------------------------------------------------------------------------------- TECH_DEBT.md
patch("TECH_DEBT.md",
"""## TD-015 — the unit-324 evaporators still carry the degenerate temperature ODE

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
no longer doing physical work.""",
"""## TD-015 — the unit-324 evaporators carried the same degenerate temperature ODE

- **Status: CLOSED 2026-07-23**, together with TD-013 — it turned out to be TD-013's blocker, not
  its follow-up
- **Severity on discovery:** B, revised to **A** once the D002 pin came out (see below)
- **Files:** `backend/main.py`, `v1_duty` / `v2_duty` in `step_sim`; `TIC_324001` / `TIC_324002`

`R324_Q1_DES_KW` is the design *latent* load and `R324_LAM_V1` its latent heat, so on the duty
branch `v1_m·λ/3600` cancelled `q1_avail` term for term and `P_e001` was identically zero — the same
identity TD-014 removed from 323. Both loops integrated against a plant of zero gain.

**Why it could not stay deferred.** With 323D002 pinned at exactly 0.80, `urea1_in` was constant and
`v1_conc` sat within **0.4 kg/h** of `v1_duty`, so the `min()` tie gave TIC-324001 partial feedback
and masked the defect — the melt drifted only −0.0011 pp/h. Dropping the pin (TD-013) removed that
accidental clamp: the branches separate by ~74 kg/h and the melt walks at **≈ 0.5 pp/h**, a
wandering product spec. So TD-013 and TD-015 are one change, not two.

**The fix, in two parts.**

*Part 1 — the closure.* Bubble-point relaxation, identical to 323F010: at a fixed vacuum the melt's
bubble point is set by **concentration**, so TIC-324001/324002 become what they are on the plant,
melt-strength controllers acting through temperature. A `_lag1` at the separator residence time is
required and load-bearing: `w1_live = urea_in/melt` is an *instantaneous algebraic ratio* that
`sol_pin_strength` writes over the species ODE, so a change in `v1` reaches the bubble point with no
holdup delay and closes a same-tick loop of gain ≈ 3 — explicit Euler answers that with a period-2
oscillation (±1e-4 K/tick, growing). The lag restores the dynamics the pinned strength threw away.

*Part 2 — the retune, which the closure made unavoidable.* Kc = 2.0 / Ti = 120 was inherited from a
plant whose temperature ODE was identically zero, so it described nothing. Two step tests were run;
**the first was contaminated** (the loops had already diverged in the same run) and gave
K_p ≈ −17.5 °C/bar for TIC-324002 — a *negative* gain, which would have meant the controller action
was backwards. That number is wrong and should not be reused. The clean measurement is a **central
difference over 1 h means**, ±0.05 bar on the master in MAN so the plant's own wander cancels:

    TIC-324001   base 130.0033   +step 130.4231   −step 129.5916   ->  K_p = +8.32 °C/bar
    TIC-324002   base 140.0169   +step 140.4353   −step 139.6000   ->  K_p = +8.35 °C/bar

Positive on both, so the REVERSE action was correct all along — and Kc = 2.0 meant a loop gain of
**16.7**, which is exactly the multi-hour limit cycle that was measured (T_e003 ±1.2 °C, PV-329212
swinging 81–90 %). Lambda-tuned on the separator's own dynamics — τ ≈ 360 s (180 s residence plus
the 180 s bubble-point holdup lag), λ = 3τ, θ ≈ 0 because the chest-pressure slave is fast at
Ti = 20 s:

    Kc = τ / (K_p·(λ + θ)) = 360 / (8.3 × 1080) = 0.04     ->  then halved to 0.02

The extra factor of two is not taste. `v_m = min(v_conc, v_duty)` is a **relay nonlinearity**, and
the branch switching sustains a slow limit cycle that no linear tuning removes. Halving the gain
measurably shrinks it — 16 h envelope T_e001 0.42 → 0.25 °C, T_e003 1.33 → 0.88 °C — which is itself
the evidence that the residual is controller-driven rather than a plant instability.

**The concentration cap stays, and that was tested rather than assumed.** Recommendation (d) of the
original entry — "with a bubble-point closure the melt is self-limiting, so drop `v_conc`" — is
**wrong**. Removing it makes the stage diverge: the melt runs away and `psat(T)` underflows to a
`ZeroDivisionError`. The cap is doing real work and must stay.

**Result.** Velocity form, so `pv == sp == pv1` still gives `du == 0` and the design seed is
bit-exact at any Kc/Ti — pin unmoved, `leaves 25 / keys 15 / diffs 0`. Over 16 h the valves sit
inside ±0.15 % of design (against an unbounded walk before) and the melts hold their targets.
Gates: `test_equation_audit_td014.py::test_the_unit_324_stages_carry_the_same_closure` and
`::test_the_324_evaporator_temperatures_stay_bounded`.

**Residual, recorded not hidden.** A slow limit cycle remains — 16 h envelope 0.25 °C on 324E001 and
0.88 °C on 324E003, from the `min()` branch switching. It is bounded and an order of magnitude below
what the old tuning produced, but it is not zero. Removing it means replacing the concentration cap
with a smooth equilibrium relation rather than deleting it, which is a modelling change of its own
and is **not** attempted here.

### One thing this changed downstream

`test_evap1_steam_cut_dilutes_product_and_never_cools` used to assert `vapour_th == 0.0` on a steam
cut. That encoded the old model's belief that a stage with no steam cannot boil. It can: with the
chest shut, 324E001 becomes an **adiabatic flash on its own 99 °C feed**, and as the melt dilutes
its bubble point collapses (130 → ~57 °C over 20 min), so the feed's sensible surplus keeps flashing
water off — 14.07 t/h of design falls to ~3.5 t/h at 8 min and settles near 4.5 t/h, with T tracking
T_bub down and landing on it (56.71 against 56.64 at 26 min). That convergence is itself the check
that the closure does what it claims. The assertion now bounds the collapse instead of demanding a
zero the physics does not produce.""")

print("done")
