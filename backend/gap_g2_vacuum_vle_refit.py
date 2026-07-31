"""G2 -- executed ebulliometric-refit test (doc sec.3.2).

Applies the closure method the strategy doc prescribes for the Unit-324 vacuum evaporation binary:
refit the urea->water UNIQUAC interaction (`tau_uw = exp(-(u0 + u1(T-298.15))/T)`) so the raw
Extended-UNIQUAC root reproduces the licensor's two vacuum design points instead of extrapolating the
high-pressure Voskov-Voronin parameters. Self-contained: imports only thermo_extended_uniquac +
iapws_if97 (no `main`), runs in <1 s.  Run from `backend`:  python gap_g2_vacuum_vle_refit.py

Finding (see __main__): NO physically-monotonic single urea-water binary reproduces BOTH licensor
vacuum design points --
  * a two-parameter (u0,u1) fit hits both points exactly but FLIPS the fixed-pressure temperature
    monotonicity (urea mass fraction decreases with T -- unphysical for vacuum boiling), and
  * a one-parameter (u0) fit that preserves monotonicity nails stage 1 (0.9431) but pushes stage 2 to
    ~0.9838 (0.67 pp off the PFD 0.9771, degrading Voskov's already-good 0.9768).
Two design points at different (T,P) under-constrain a T-dependent binary. Per doc sec.3.2 this
requires INDEPENDENT multi-point ebulliometric urea-water VLE at 130-140 C to fix the interaction
shape. A 2026-07-31 literature pass found only dilute (<=32 wt%) urea BPE/VLE public; the concentrated
(90-99 wt%) vacuum melt data is not available. G2 therefore stays OPEN (data-gated), and the current
anchored-departure model -- which keeps Voskov physics and pins the design strength -- remains the best
honest choice until that data arrives. Do NOT commit either refit: both degrade the model.
"""

from __future__ import annotations

import math

import thermo_extended_uniquac as t

# licensor vacuum design points (w_urea, T_K, P_bara)
P1 = (0.9431, 403.15, 0.33)      # 324E001/F001
P2 = (0.9771, 413.15, 0.131)     # 324E003/F003
VOSKOV = (-211.9567785927018, 0.0)


def _set(a0, a1):
    t._A0 = ((0.0, 0.0), (a0, 0.0))
    t._A1 = ((0.0, 0.0), (a1, 0.0))
    t.solve_urea_mass_fraction.cache_clear()
    t.fast_solver_cache_clear()


def _lngw(w, T):
    xw, xu = t.mole_fractions_from_urea_mass_fraction(w)
    return t.ln_gamma(xw, xu, T)[0]


def _target(w, T, P):
    xw, _ = t.mole_fractions_from_urea_mass_fraction(w)
    return math.log(P / (t.water_psat_bara(T) * xw))


def _fit_two_param():
    tgt1, tgt2 = _target(*P1), _target(*P2)
    p = [VOSKOV[0], 0.0]
    for _ in range(80):
        _set(*p)
        r = [_lngw(P1[0], P1[1]) - tgt1, _lngw(P2[0], P2[1]) - tgt2]
        if max(abs(r[0]), abs(r[1])) < 1e-13:
            break
        _set(p[0] + 1e-3, p[1]); r0 = [_lngw(P1[0], P1[1]) - tgt1, _lngw(P2[0], P2[1]) - tgt2]
        _set(p[0], p[1] + 1e-6); r1 = [_lngw(P1[0], P1[1]) - tgt1, _lngw(P2[0], P2[1]) - tgt2]
        J00, J10 = (r0[0] - r[0]) / 1e-3, (r0[1] - r[1]) / 1e-3
        J01, J11 = (r1[0] - r[0]) / 1e-6, (r1[1] - r[1]) / 1e-6
        det = J00 * J11 - J01 * J10
        p = [p[0] - (r[0] * J11 - r[1] * J01) / det, p[1] - (r[1] * J00 - r[0] * J10) / det]
    return p


def _fit_one_param():
    tgt1 = _target(*P1)
    a0 = VOSKOV[0]
    for _ in range(80):
        _set(a0, 0.0); r = _lngw(P1[0], P1[1]) - tgt1
        if abs(r) < 1e-13:
            break
        _set(a0 + 1e-2, 0.0); J = (_lngw(P1[0], P1[1]) - tgt1 - r) / 1e-2
        a0 = a0 - r / J
    return a0


def _report(label, a0, a1):
    _set(a0, a1)
    f = t.solve_urea_mass_fraction
    w1, w2 = f(403.15, 0.33), f(413.15, 0.131)
    t_inc = f(413.15, 0.20) > f(403.15, 0.20)      # urea should RISE with T at fixed P
    p_dec = f(403.15, 0.40) < f(403.15, 0.20)      # urea should FALL with P at fixed T
    print(f"\n  {label}: a0_uw={a0:.4f} a1_uw={a1:.4f}")
    print(f"      stage1 w={w1:.4f} (PFD 0.9431, err {(w1-0.9431)*100:+.2f} pp)")
    print(f"      stage2 w={w2:.4f} (PFD 0.9771, err {(w2-0.9771)*100:+.2f} pp)")
    print(f"      monotonicity: dW/dT>0 {t_inc}  dW/dP<0 {p_dec}  -> "
          f"{'PHYSICAL' if (t_inc and p_dec) else 'UNPHYSICAL'}")
    return t_inc and p_dec, w1, w2


if __name__ == "__main__":
    print("=" * 78)
    print("  G2 -- ebulliometric refit test (doc sec.3.2): can a urea-water binary reproduce")
    print("        BOTH licensor vacuum design points with physical monotonicity?")
    print("=" * 78)
    _report("Voskov-Voronin (current, extrapolated)", *VOSKOV)
    two = _fit_two_param(); ph2, _, _ = _report("Two-parameter refit (u0,u1)", two[0], two[1])
    one = _fit_one_param(); ph1, w1a, w2a = _report("One-parameter refit (u0, u1=0)", one, 0.0)

    print("\n" + "=" * 78)
    ok_two = ph2 and True
    print("  Two-param fit matches both points but is " + ("PHYSICAL" if ph2 else "UNPHYSICAL (monotonicity flips)"))
    print("  One-param fit is " + ("PHYSICAL" if ph1 else "UNPHYSICAL") +
          f" but stage-2 error is {abs(w2a-0.9771)*100:.2f} pp (Voskov: 0.03 pp)")
    print("  => No physical single binary reproduces both design points. G2 needs INDEPENDENT")
    print("     multi-point ebulliometric urea-water VLE at 130-140 C (not publicly available).")
    print("     Keep the anchored-departure model until that data is supplied. G2 stays OPEN.")
    print("=" * 78)
