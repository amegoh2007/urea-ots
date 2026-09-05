# -*- coding: utf-8 -*-
"""Liquid-liquid constant-area jet pump (Phase 4, report D-6).

322F001 is a LIQUID-liquid jet ejector: high-pressure liquid ammonia from the 321P002 triplex
pumps drives a nozzle, entrains the 322E003 carbamate overflow, mixes with it in a constant-area
throat and recovers pressure in a diffuser.  `ejector_huang.py` is a COMPRESSIBLE double-choking
gas ejector -- Mach numbers, isentropic area ratios, normal shocks -- and none of that applies:
there is no sonic condition in a liquid, so the machine has no choked branch to sit on and its
entrainment does not rise on any motive/suction ratio below choking.

WHAT THIS REPLACES
------------------
The engine's entrainment law was

    capacity = m_suc_des . phi_m . phi_sp . f_stall
    f_stall  = clamp((phi_m - 0.20)/(0.35 - 0.20), 0, 1) ** 2

with `phi_sp` an equal-percentage characteristic applied directly to the CAPACITY.  Every part of
that is a curve fitted to the desired behaviour rather than a statement about the machine: the
entrainment ratio is asserted constant across the healthy band, the collapse on a motive fault is a
polynomial with three fitted constants and no physical meaning, and the spindle acts on the answer
instead of on the nozzle area.  The directions were right; nothing in it could be wrong in an
interesting way, because nothing in it was derived.

WHY THE FIRST CONSTANT-AREA ATTEMPT WAS BISTABLE, AND WHAT FIXES IT
-------------------------------------------------------------------
The previous incompressible attempt (recorded in the handoff, not committed) produced a discharge
pressure whose m_s^2 coefficient was

    1/(rho_s.A_s.A_m) - 0.625/(rho_m.A_m^2)

which is NET POSITIVE for any sensible area ratio, so the recovered pressure eventually RISES with
entrainment, the closure has two roots and the characteristic degenerates to a step.  The missing
term is the SUCTION-INLET ACCELERATION: the entrained stream does not arrive at the throat entry
plane at rest, it has been accelerated from the suction line to V_s = m_s/(rho_s.A_s), and that
costs a velocity head

    -(1 + K_en) . m_s^2 / (2 . rho_s . A_s^2)

which enters with 1/A_s^2 where the cross term enters with 1/(A_s.A_m).  Since A_s < A_m the missing
term is the LARGER of the two, and restoring it flips the sign of the group.  The result is not a
tuning: with the term in place the coefficient is provably non-positive for every area ratio
whenever

    rho_m / rho_s  <=  (2 + K_th - eta_d) / (1 - K_en)                       [MONOTONICITY]

because the positive group is largest as A_s -> A_m, where it is (1 - K_en)/(2.rho_s.A_m^2), and the
negative group is at least (2 + K_th - eta_d)/(2.rho_m.A_m^2).  At the 322F001 anchors
(rho_m 877.9, rho_s 1133.0, K_th 0.05, eta_d 0.80, K_en 0) the left side is 0.775 against 1.25 on
the right -- a factor of 1.6 of margin, and `monotonicity_margin` returns it so a call site can
assert on it rather than hope.  With the coefficient non-positive and the linear coefficient
strictly negative, the discharge is strictly DECREASING in entrainment over the whole physical
range, the closure is a downward parabola whose vertex lies at negative entrainment, and there is
exactly ONE non-negative root -- available in closed form, with no iteration and nothing to
converge to the wrong branch.

AGREEMENT WITH THE PUBLISHED N-M FORM
-------------------------------------
Non-dimensionalised at equal densities and zero losses (b = A_t/A_m, M = m_s/m_p, K = m_p^2/(rho
A_m^2)), the pressure rise below is

    (p_d - p_s)/K = 1/b + M^2/(1-b) - M^2/(2(1-b)^2) - (1+M)^2/2

and multiplying by 2b^2 gives

    2b + 2b^2.M^2/(1-b) - b^2.M^2/(1-b)^2 - b^2.(1+M)^2

which is the Cunningham / ESDU 85032 numerator of N = (p_d - p_s)/(p_p - p_d) term for term, with
the loss coefficients set to zero.  The convention difference is in the DENOMINATOR only: the
published form takes the nozzle velocity from the full (p_p - p_s), i.e. it puts the suction
acceleration entirely into the entry-loss coefficient, where the form here carries it explicitly
and lets the nozzle discharge into the actual throat-entry plane pressure.  At the 322F001 duty the
two differ by one suction velocity head, 0.27 bar against a 25 bar nozzle differential -- about
1 % -- so the model is directly comparable with a published N-M curve and the area convention is
the published one.

UNITS.  Flows kg/h, pressures bar a, areas m2, densities kg/m3.
"""

import math

_BAR = 1.0e5


# ==================================================================================================
#  Loss coefficients
# ==================================================================================================
#  `References/Datasheets/322F001 Design Calculations.pdf` is a 12-page SCAN with no text layer, so
#  no nozzle, throat or diffuser geometry and no vendor loss coefficients can be read out of this
#  repository.  These are the representative values for a machined jet pump quoted in the open
#  literature (Cunningham; ESDU 85032), applied openly and uniformly -- the same class of stated
#  assumption as FL_GLOBE and XT_GLOBE in hydraulics.py, not fitted constants.  What they are NOT
#  is free parameters standing in for the design point: the geometry is back-solved THROUGH them
#  from the licensor's own duty, so a different set of coefficients moves the back-solved areas and
#  leaves the design point exactly where it is.
K_NOZZLE  = 0.05      # motive-nozzle loss coefficient
K_ENTRY   = 0.10      # suction-inlet (annulus acceleration) loss coefficient
K_THROAT  = 0.05      # constant-area mixing-throat wall friction
ETA_DIFF  = 0.80      # diffuser pressure-recovery efficiency


def monotonicity_margin(rho_s: float, rho_m: float,
                        k_entry: float = K_ENTRY, k_throat: float = K_THROAT,
                        eta_d: float = ETA_DIFF) -> float:
    """Ratio of the monotonicity bound to the density ratio it must dominate.

        margin = [ (2 + K_th - eta_d) / (1 - K_en) ] / (rho_m / rho_s)

    > 1 means the m_s^2 coefficient is non-positive for EVERY area ratio, so the closure is
    strictly monotonic and single-rooted whatever the spindle does.  This is the property the
    previous attempt did not have, and it is checkable rather than hoped for."""
    if rho_s <= 0.0 or rho_m <= 0.0 or k_entry >= 1.0:
        return 0.0
    bound = (2.0 + k_throat - eta_d) / (1.0 - k_entry)
    return bound / (rho_m / rho_s)


# ==================================================================================================
#  The constant-area closure
# ==================================================================================================
def _coefficients(m_p_kgs: float, a_t_m2: float, a_m_m2: float,
                  rho_p: float, rho_s: float, rho_m: float,
                  k_entry: float, k_throat: float, eta_d: float):
    """Quadratic coefficients of  p_d - p_s = C0 + C1.m_s + C2.m_s^2   (SI: Pa, kg/s, m2).

    Assembled from three balances, in this order:

      nozzle           V_p = m_p / (rho_p.A_t)                       (motive mass flow is set by the
                                                                      PD pumps, so the nozzle area
                                                                      fixes the jet velocity)
      suction inlet    p_1 = p_s - (1 + K_en).m_s^2/(2.rho_s.A_s^2)
      throat momentum  (p_2 - p_1).A_m = m_p.V_p + m_s.V_s - m_m.V_m - K_th.(m_m^2)/(2.rho_m.A_m)
      diffuser         p_d = p_2 + eta_d.m_m^2/(2.rho_m.A_m^2)
    """
    a_s = a_m_m2 - a_t_m2
    if a_t_m2 <= 0.0 or a_s <= 0.0 or rho_p <= 0.0 or rho_s <= 0.0 or rho_m <= 0.0:
        return None
    b_grp = (-1.0 - 0.5 * k_throat + 0.5 * eta_d) / (rho_m * a_m_m2 * a_m_m2)      # of m_m^2, < 0
    a_grp = (1.0 / (rho_s * a_s * a_m_m2)
             - (1.0 + k_entry) / (2.0 * rho_s * a_s * a_s))                        # of m_s^2
    c0 = m_p_kgs * m_p_kgs / (rho_p * a_t_m2 * a_m_m2) + b_grp * m_p_kgs * m_p_kgs
    c1 = 2.0 * b_grp * m_p_kgs
    c2 = a_grp + b_grp
    return c0, c1, c2


def discharge_rise_bar(m_p_kgh: float, m_s_kgh: float, a_t_m2: float, a_m_m2: float,
                       rho_p: float, rho_s: float, rho_m: float,
                       k_entry: float = K_ENTRY, k_throat: float = K_THROAT,
                       eta_d: float = ETA_DIFF) -> float:
    """Pressure rise p_d - p_s (bar) the jet pump develops at a GIVEN entrainment."""
    c = _coefficients(m_p_kgh / 3600.0, a_t_m2, a_m_m2, rho_p, rho_s, rho_m,
                      k_entry, k_throat, eta_d)
    if c is None:
        return 0.0
    c0, c1, c2 = c
    ms = m_s_kgh / 3600.0
    return (c0 + c1 * ms + c2 * ms * ms) / _BAR


def entrainment_kgh(m_p_kgh: float, p_suct_bara: float, p_disch_bara: float,
                    a_t_m2: float, a_m_m2: float,
                    rho_p: float, rho_s: float, rho_m: float,
                    k_entry: float = K_ENTRY, k_throat: float = K_THROAT,
                    eta_d: float = ETA_DIFF, pv_suct_bara: float = 0.0) -> dict:
    """Entrained (suction) mass flow that closes the constant-area balance against p_disch.

    Solves  C2.m_s^2 + C1.m_s + (C0 - dP) = 0  for the unique non-negative root.  With C2 <= 0 and
    C1 < 0 the parabola's vertex sits at NEGATIVE m_s, so on m_s >= 0 the discharge is strictly
    decreasing and the root below is the only one -- there is no branch to pick and no bistability.

    Physical bounds, both hard rather than smoothed:
      * m_s >= 0.  A jet pump that cannot lift its own discharge entrains NOTHING; it does not
        entrain backwards.  Reverse flow through the suction is a different flow path and would
        need its own model, not a sign flip here.
      * the throat-entry static pressure may not fall below the suction fluid's vapour pressure.
        That is the cavitation limit, and it is the real ceiling on a jet pump's entrainment --
        p_1 = p_s - (1+K_en).m_s^2/(2.rho_s.A_s^2) >= p_v caps m_s at
        rho_s.A_s.sqrt(2.(p_s - p_v)/(rho_s.(1+K_en))).  With pv_suct_bara left at its 0.0 default
        this degrades to the absolute-pressure floor (a static pressure cannot go negative), which
        is still a strict thermodynamic bound and is the one that applies when the available NPSH
        is not known from a source.

    Returns the flow plus the entrainment ratio, the closure coefficients and the two bound flags,
    because which bound is active is a different plant event from merely running off design.
    """
    m_p_kgs = m_p_kgh / 3600.0
    if m_p_kgs <= 0.0:
        return {"kgh": 0.0, "mu": 0.0, "cavitating": False, "stalled": True,
                "c0_bar": 0.0, "c2": 0.0}
    c = _coefficients(m_p_kgs, a_t_m2, a_m_m2, rho_p, rho_s, rho_m, k_entry, k_throat, eta_d)
    if c is None:
        return {"kgh": 0.0, "mu": 0.0, "cavitating": False, "stalled": True,
                "c0_bar": 0.0, "c2": 0.0}
    c0, c1, c2 = c
    dp_pa = (p_disch_bara - p_suct_bara) * _BAR
    cc = c0 - dp_pa
    if cc <= 0.0:
        #  The jet cannot develop the required lift even at zero entrainment: STALL.  This is the
        #  physical statement the f_stall polynomial was standing in for, and it arrives with no
        #  fitted knee, no recovery fraction and no convexity exponent -- it is simply the point at
        #  which the momentum the nozzle can deliver stops covering the discharge.
        return {"kgh": 0.0, "mu": 0.0, "cavitating": False, "stalled": True,
                "c0_bar": c0 / _BAR, "c2": c2}
    if c2 >= 0.0:
        #  Guard, not a fallback: `monotonicity_margin` is asserted > 1 at the call site, so this
        #  branch is unreachable for the anchored densities.  If a future density pair ever breaks
        #  the bound, degrade to the LINEAR closure rather than silently returning a root off the
        #  wrong branch of a parabola that now curves upward.
        ms = -cc / c1 if c1 < 0.0 else 0.0
    else:
        disc = c1 * c1 - 4.0 * c2 * cc
        ms = (-c1 - math.sqrt(max(disc, 0.0))) / (2.0 * c2)
    ms = max(ms, 0.0)
    #  Cavitation ceiling on the suction annulus.
    a_s = a_m_m2 - a_t_m2
    npsh_pa = (p_suct_bara - pv_suct_bara) * _BAR
    cavitating = False
    if npsh_pa > 0.0 and a_s > 0.0:
        ms_max = rho_s * a_s * math.sqrt(2.0 * npsh_pa / (rho_s * (1.0 + k_entry)))
        if ms > ms_max:
            ms, cavitating = ms_max, True
    else:
        ms, cavitating = 0.0, True
    return {"kgh": ms * 3600.0, "mu": ms / m_p_kgs, "cavitating": cavitating,
            "stalled": False, "c0_bar": c0 / _BAR, "c2": c2}


# ==================================================================================================
#  Geometry back-solve from the licensor's design duty
# ==================================================================================================
def nozzle_area_m2(m_p_kgh: float, dp_nozzle_bar: float, rho_p: float,
                   k_nozzle: float = K_NOZZLE) -> float:
    """Motive-nozzle exit area that passes m_p at the design nozzle differential.

        V_p = sqrt( 2.dP / (rho_p.(1 + K_n)) ),      A_t = m_p / (rho_p.V_p)
    """
    if dp_nozzle_bar <= 0.0 or rho_p <= 0.0 or m_p_kgh <= 0.0:
        return 0.0
    v_p = math.sqrt(2.0 * dp_nozzle_bar * _BAR / (rho_p * (1.0 + k_nozzle)))
    return m_p_kgh / 3600.0 / (rho_p * v_p)


def solve_geometry(m_p_kgh: float, m_s_kgh: float, p_mot_bara: float, p_suct_bara: float,
                   p_disch_bara: float, rho_p: float, rho_s: float, rho_m: float,
                   k_nozzle: float = K_NOZZLE, k_entry: float = K_ENTRY,
                   k_throat: float = K_THROAT, eta_d: float = ETA_DIFF,
                   b_lo: float = 0.02, b_hi: float = 0.30, tol: float = 1.0e-12) -> dict:
    """Back-solve (A_t, A_m) from the design point -- the only two geometric numbers the model needs.

    Two equations, two unknowns:
      * the MOTIVE NOZZLE passes the design motive flow at the design nozzle differential
        (p_mot - p_1, with p_1 the throat-entry plane pressure the suction acceleration sets), and
      * the CONSTANT-AREA closure develops exactly the design discharge rise at the design
        entrainment.

    The second equation has TWO roots in A_m -- a small chamber with a large area ratio and a large
    one with a small ratio -- and they are separated on a physical ground rather than a numerical
    one: the mixing-throat VELOCITY.  At the 322F001 duty the large-ratio root puts 96 t/h of
    carbamate through the throat at 54 m/s, which is an erosion rate rather than an operating point,
    while the small-ratio root gives about 15 m/s, squarely in the 10-20 m/s band a liquid jet pump
    is drawn for.  `b_hi` brackets the search below the large-ratio root; the returned dict carries
    both velocities so the choice can be re-checked rather than trusted.

    Returns A_t, A_m, the area ratio b, the throat and nozzle velocities and the design N and M, so
    the back-solve can be compared against a published N-M chart.
    """
    def _areas(b):
        #  A_t depends on the throat-entry pressure, which depends on A_s = A_m - A_t: fixed-point
        #  iterate, which converges in a handful of passes because the suction velocity head is
        #  ~1 % of the nozzle differential.
        a_t = nozzle_area_m2(m_p_kgh, p_mot_bara - p_suct_bara, rho_p, k_nozzle)
        for _ in range(60):
            a_m = a_t / b
            a_s = a_m - a_t
            if a_s <= 0.0:
                return None
            v_s = (m_s_kgh / 3600.0) / (rho_s * a_s)
            p1 = p_suct_bara - (1.0 + k_entry) * rho_s * v_s * v_s / 2.0 / _BAR
            a_t_new = nozzle_area_m2(m_p_kgh, p_mot_bara - p1, rho_p, k_nozzle)
            if abs(a_t_new - a_t) <= tol * max(a_t, 1.0e-9):
                a_t = a_t_new
                break
            a_t = a_t_new
        return a_t, a_t / b

    def _residual(b):
        ar = _areas(b)
        if ar is None:
            return None
        a_t, a_m = ar
        return discharge_rise_bar(m_p_kgh, m_s_kgh, a_t, a_m, rho_p, rho_s, rho_m,
                                  k_entry, k_throat, eta_d) - (p_disch_bara - p_suct_bara)

    lo, hi = b_lo, b_hi
    r_lo, r_hi = _residual(lo), _residual(hi)
    if r_lo is None or r_hi is None or r_lo * r_hi > 0.0:
        raise ValueError("design duty does not bracket a constant-area geometry in [%g, %g]"
                         % (b_lo, b_hi))
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        r = _residual(mid)
        if r == 0.0 or (hi - lo) < 1.0e-14:
            lo = hi = mid
            break
        if (r > 0.0) == (r_lo > 0.0):
            lo, r_lo = mid, r
        else:
            hi, r_hi = mid, r
    b = 0.5 * (lo + hi)
    a_t, a_m = _areas(b)
    m_m = m_p_kgh + m_s_kgh
    v_m = (m_m / 3600.0) / (rho_m * a_m)
    v_p = (m_p_kgh / 3600.0) / (rho_p * a_t)
    n_head = ((p_disch_bara - p_suct_bara) / (p_mot_bara - p_disch_bara)
              if p_mot_bara > p_disch_bara else float("inf"))
    m_vol = ((m_s_kgh / rho_s) / (m_p_kgh / rho_p)) if m_p_kgh > 0.0 else 0.0
    return {"a_t_m2": a_t, "a_m_m2": a_m, "b": b,
            "d_t_mm": 1000.0 * math.sqrt(4.0 * a_t / math.pi),
            "d_m_mm": 1000.0 * math.sqrt(4.0 * a_m / math.pi),
            "v_nozzle_ms": v_p, "v_throat_ms": v_m,
            "N": n_head, "M_vol": m_vol, "efficiency": n_head * m_vol}
