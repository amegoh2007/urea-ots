"""Self-tests for the 322F001 liquid-liquid constant-area jet pump (Phase 4, report D-6).

The property this file exists to pin is MONOTONICITY.  The previous constant-area attempt was
abandoned because its m_s^2 coefficient went net positive, which gave the closure two roots and
degenerated the characteristic into a step -- zero below a motive threshold, railed above it.  Every
test below is about that, or about the design anchor it must not cost.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jet_pump as jp

#  The 322F001 design point (PFD / reconciled HMB), repeated here so the module can be tested
#  without importing the whole engine.
MP, MS = 42762.05427809782, 53368.2848880754
RHO_P, RHO_S, RHO_M = 604.8, 1133.0, 877.9
P_MOT, P_SUCT, P_DISCH = 165.0, 140.0, 144.2


def _geom():
    return jp.solve_geometry(MP, MS, P_MOT, P_SUCT, P_DISCH, RHO_P, RHO_S, RHO_M)


# ==================================================================================================
#  Monotonicity -- the whole point
# ==================================================================================================
def test_the_density_pair_satisfies_the_monotonicity_bound():
    """Sufficient condition for the m_s^2 coefficient to be non-positive at EVERY area ratio, i.e.
    at every spindle position: rho_m/rho_s <= (2 + K_th - eta_d)/(1 - K_en)."""
    assert jp.monotonicity_margin(RHO_S, RHO_M) > 1.0
    assert abs(jp.monotonicity_margin(RHO_S, RHO_M) - 1.7925) < 0.001


def test_the_bound_actually_bites_when_it_is_violated():
    """Not a tautology: a mixture DENSER than its own suction breaks the bound, and the guard is
    the thing that would have caught the previous attempt."""
    assert jp.monotonicity_margin(700.0, 2000.0) < 1.0


def test_the_ms2_coefficient_is_non_positive_at_every_area_ratio():
    g = _geom()
    for b in (0.02, 0.05, 0.10, 0.2, 0.3, 0.5, 0.7, 0.9):
        a_m = g["a_t_m2"] / b
        r = jp.entrainment_kgh(MP, P_SUCT, P_DISCH, g["a_t_m2"], a_m, RHO_P, RHO_S, RHO_M)
        assert r["c2"] <= 0.0, (b, r["c2"])


def test_the_discharge_falls_strictly_with_entrainment():
    """The property the previous form lost: the recovered pressure must never RISE with the
    entrained flow, or the closure has two roots."""
    g = _geom()
    last = None
    for f in (0.0, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0):
        rise = jp.discharge_rise_bar(MP, MS * f, g["a_t_m2"], g["a_m_m2"], RHO_P, RHO_S, RHO_M)
        if last is not None:
            assert rise < last, (f, rise, last)
        last = rise


def test_the_root_is_the_only_non_negative_one():
    """Solve, then re-substitute: the returned flow reproduces the demanded lift, and the discharge
    is above it below that flow and under it above -- which is what single-rooted means."""
    g = _geom()
    r = jp.entrainment_kgh(MP, P_SUCT, P_DISCH, g["a_t_m2"], g["a_m_m2"], RHO_P, RHO_S, RHO_M)
    ms = r["kgh"]
    back = jp.discharge_rise_bar(MP, ms, g["a_t_m2"], g["a_m_m2"], RHO_P, RHO_S, RHO_M)
    assert abs(back - (P_DISCH - P_SUCT)) < 1e-9
    lo = jp.discharge_rise_bar(MP, ms * 0.9, g["a_t_m2"], g["a_m_m2"], RHO_P, RHO_S, RHO_M)
    hi = jp.discharge_rise_bar(MP, ms * 1.1, g["a_t_m2"], g["a_m_m2"], RHO_P, RHO_S, RHO_M)
    assert lo > P_DISCH - P_SUCT > hi


# ==================================================================================================
#  The design anchor and the geometry it back-solves
# ==================================================================================================
def test_the_design_duty_closes_on_the_back_solved_geometry():
    g = _geom()
    r = jp.entrainment_kgh(MP, P_SUCT, P_DISCH, g["a_t_m2"], g["a_m_m2"], RHO_P, RHO_S, RHO_M)
    assert abs(r["kgh"] - MS) < 1e-6
    assert abs(r["mu"] - MS / MP) < 1e-9


def test_the_geometry_is_a_plausible_jet_pump_not_an_erosion_rate():
    """The closure has two roots in the mixing area and they are separated on velocity: the
    rejected root puts 96 t/h of carbamate through the throat at ~96 m/s."""
    g = _geom()
    assert 0.05 < g["b"] < 0.30                       # published liquid jet-pump area-ratio band
    assert 5.0 < g["v_throat_ms"] < 25.0              # a throat, not a cutting jet
    assert 50.0 < g["v_nozzle_ms"] < 150.0            # a motive nozzle
    assert 10.0 < g["d_t_mm"] < 25.0
    assert 35.0 < g["d_m_mm"] < 75.0


def test_the_nozzle_area_falls_with_the_square_root_of_its_differential():
    a1 = jp.nozzle_area_m2(MP, 25.0, RHO_P)
    a4 = jp.nozzle_area_m2(MP, 100.0, RHO_P)
    assert math.isclose(a1 / a4, 2.0, rel_tol=1e-12)


# ==================================================================================================
#  Directions -- now derived rather than asserted
# ==================================================================================================
def test_closing_the_nozzle_raises_entrainment():
    """A positive-displacement motive pump fixes m_p, so a smaller nozzle raises the jet momentum
    m_p^2/(rho_p.A_t) and therefore the head the pump can develop.  The old model ASSERTED this
    through an equal-% curve on the capacity; here it falls out of the momentum balance."""
    g = _geom()
    f = lambda k: jp.entrainment_kgh(MP, P_SUCT, P_DISCH, g["a_t_m2"] * k, g["a_m_m2"],
                                     RHO_P, RHO_S, RHO_M)["kgh"]
    assert f(0.85) > f(0.95) > f(1.0) > f(1.05)


def test_a_deeper_lift_lowers_entrainment():
    g = _geom()
    f = lambda pd: jp.entrainment_kgh(MP, P_SUCT, pd, g["a_t_m2"], g["a_m_m2"],
                                      RHO_P, RHO_S, RHO_M)["kgh"]
    assert f(143.0) > f(144.2) > f(144.8)


def test_stall_is_a_consequence_not_a_polynomial():
    """The jet's shutoff head scales with m_p^2, so below sqrt(lift/C0_des) of the design motive it
    cannot cover the lift at all and the entrainment is exactly zero -- no knee, no recovery
    fraction, no convexity exponent."""
    g = _geom()
    r_des = jp.entrainment_kgh(MP, P_SUCT, P_DISCH, g["a_t_m2"], g["a_m_m2"], RHO_P, RHO_S, RHO_M)
    phi_stall = math.sqrt((P_DISCH - P_SUCT) / r_des["c0_bar"])
    assert 0.5 < phi_stall < 1.0
    below = jp.entrainment_kgh(MP * phi_stall * 0.99, P_SUCT, P_DISCH, g["a_t_m2"], g["a_m_m2"],
                               RHO_P, RHO_S, RHO_M)
    above = jp.entrainment_kgh(MP * phi_stall * 1.01, P_SUCT, P_DISCH, g["a_t_m2"], g["a_m_m2"],
                               RHO_P, RHO_S, RHO_M)
    assert below["stalled"] and below["kgh"] == 0.0
    assert (not above["stalled"]) and above["kgh"] > 0.0


def test_no_motive_gives_no_entrainment_rather_than_a_nan():
    g = _geom()
    r = jp.entrainment_kgh(0.0, P_SUCT, P_DISCH, g["a_t_m2"], g["a_m_m2"], RHO_P, RHO_S, RHO_M)
    assert r["kgh"] == 0.0 and r["stalled"]


def test_the_cavitation_ceiling_binds_only_when_the_npsh_says_so():
    """The throat-entry static pressure may not fall below the suction fluid's vapour pressure.
    At the design NPSH the ceiling is far above the duty; drive p_v up to the suction pressure and
    the entrainment is capped, then zeroed."""
    g = _geom()
    free = jp.entrainment_kgh(MP, P_SUCT, P_DISCH, g["a_t_m2"], g["a_m_m2"], RHO_P, RHO_S, RHO_M)
    assert not free["cavitating"]
    capped = jp.entrainment_kgh(MP, P_SUCT, P_DISCH, g["a_t_m2"], g["a_m_m2"],
                                RHO_P, RHO_S, RHO_M, pv_suct_bara=P_SUCT - 0.0005)
    assert capped["cavitating"] and 0.0 < capped["kgh"] < free["kgh"]
    dry = jp.entrainment_kgh(MP, P_SUCT, P_DISCH, g["a_t_m2"], g["a_m_m2"],
                             RHO_P, RHO_S, RHO_M, pv_suct_bara=P_SUCT)
    assert dry["cavitating"] and dry["kgh"] == 0.0


# ==================================================================================================
#  Agreement with the published N-M form
# ==================================================================================================
def test_the_non_dimensional_rise_matches_the_published_numerator():
    """At equal densities and zero losses, 2b^2.(p_d - p_s)/K must equal the Cunningham / ESDU
    numerator  2b + 2b^2.M^2/(1-b) - b^2.M^2/(1-b)^2 - b^2.(1+M)^2  term for term."""
    rho = 1000.0
    a_m = 2.0e-3
    for b in (0.08, 0.15, 0.25, 0.40):
        for mm in (0.0, 0.5, 1.0, 2.0):
            a_t = b * a_m
            m_p, m_s = 40000.0, 40000.0 * mm
            rise_pa = jp.discharge_rise_bar(m_p, m_s, a_t, a_m, rho, rho, rho,
                                            k_entry=0.0, k_throat=0.0, eta_d=1.0) * 1.0e5
            k = (m_p / 3600.0) ** 2 / (rho * a_m * a_m)
            lhs = 2.0 * b * b * rise_pa / k
            rhs = (2.0 * b + 2.0 * b * b * mm * mm / (1.0 - b)
                   - b * b * mm * mm / (1.0 - b) ** 2 - b * b * (1.0 + mm) ** 2)
            assert abs(lhs - rhs) < 1e-9, (b, mm, lhs, rhs)


# ==================================================================================================
#  The engine wiring
# ==================================================================================================
def _main():
    import main
    return main


def test_the_engine_reproduces_the_design_entrainment_bit_exactly():
    main = _main()
    ej = main.ejector_322f001(main.EJ_MOTIVE_NH3_DES, main.EJ_T_SUCTION_C, main.EJ_OPEN_DES)
    assert ej["suction_kgh"] == main.EJ_SUC_TOT_DES


def test_the_spindle_characteristic_is_exactly_one_at_the_design_opening():
    main = _main()
    assert main.ej_spindle_phi(main.EJ_OPEN_DES) == 1.0
    assert main.ej_spindle_phi(50.0) > 1.0 > main.ej_spindle_phi(95.0)


def test_the_spindle_runs_on_the_datasheet_free_area_map():
    """DDS Remarks 3-5: free area variable 40-100 % on a(theta) = 40 + 0.6.theta."""
    main = _main()
    assert abs(main.EJ_SPINDLE_A_FULL - 84.4) < 1e-9
    assert not hasattr(main, "EJ_SPINDLE_AREA_R")


def test_the_engine_asserts_its_own_monotonicity_bound():
    main = _main()
    assert jp.monotonicity_margin(main.EJ_RHO_SUCT, main.EJ_RHO_DISCH) > 1.0


def test_the_stall_margin_is_published_rather_than_discovered():
    main = _main()
    assert 0.5 < main.EJ_STALL_PHI_M < 1.0
    stalled = main.ejector_322f001(main.EJ_MOTIVE_NH3_DES * main.EJ_STALL_PHI_M * 0.98,
                                   main.EJ_T_SUCTION_C, main.EJ_OPEN_DES)
    assert stalled["stalled"] and stalled["suction_kgh"] == 0.0
