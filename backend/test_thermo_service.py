"""Phase 1 -- unit tests for the unified rigorous VLE / flash service.

These test the SERVICE, not the engine: no `import main`, so they run in ~1 s and are not gated on
the 18 000-tick boot pin.  Engine-level consequences are covered by the existing equation audits.
"""
import math

import pytest

import thermo_service as ts
import vle_nh3co2h2o as vle


def _norm(d):
    tot = sum(d.values())
    return {k: v / tot for k, v in d.items()}


#  The engine's own design vectors (main.py W_S314 / W_S319_TAB / W_S317 / W_S401_TAB / W_S402_TAB)
#  transcribed as literals so this file does not import main.
W_C003 = _norm(dict(Urea=68.74, Biuret=0.36, NH3=2.13, CO2=1.05, H2O=27.72))
W_F004 = _norm(dict(Urea=71.74, Biuret=0.37, NH3=0.88, CO2=0.66, H2O=26.35))
W_F010 = _norm(dict(Urea=80.00, Biuret=0.42, NH3=0.08, CO2=0.02, H2O=19.47))
W_E001 = _norm(dict(Urea=94.31, Biuret=0.69, NH3=0.03, H2O=4.97))
W_E003 = _norm(dict(Urea=97.71, Biuret=0.85, NH3=0.04, H2O=1.39))

#  Reactor overflow (stream 207) as mass fractions -- the HP-loop state that MUST be refused.
_MW = {"Urea": 60.056, "Biuret": 103.081, "NH3": 17.0304, "CO2": 44.0098, "H2O": 18.0152}
_R207_KMOLH = {"Urea": 1302.6, "Biuret": 2.414, "NH3": 4002.4, "CO2": 897.7, "H2O": 2222.0}
W_R207 = _norm({k: v * _MW[k] for k, v in _R207_KMOLH.items()})

STAGES_323 = [("323C003", W_C003, 135.0, 4.10),
              ("323F004", W_F004, 106.0, 1.13),
              ("323F010", W_F010, 99.0, 0.46)]


# ---------------------------------------------------------------- domain classification / refusal

def test_323_stages_are_on_the_electrolyte_domain():
    for tag, w, t_c, p in STAGES_323:
        assert ts.classify(w, t_c, p) == ts.DOMAIN_ELECTROLYTE, tag


def test_324_melts_are_on_the_neutral_urea_domain():
    assert ts.classify(W_E001, 130.0, 0.330) == ts.DOMAIN_NEUTRAL_UREA
    assert ts.classify(W_E003, 140.0, 0.131) == ts.DOMAIN_NEUTRAL_UREA


def test_the_hp_synthesis_loop_is_owned_now_but_only_through_the_ratio():
    """G-VLE-3, replacing `test_hp_synthesis_loop_is_refused_not_extrapolated`.

    That test pinned the refusal, and the refusal was right at the time: the table was indexed in
    mol per kg of WATER, the loop has almost none, `_bracket` CLAMPS, and a silent answer would have
    been a frozen edge node wearing a rigorous-looking call.  Both halves of that are now fixed --
    bounded mole-fraction coordinates, and a speciation solver that reaches the loading -- so the
    service ANSWERS here.

    What has not changed is that the parameter set is extrapolated in this loop, so the test that
    replaces the refusal pins the two things that keep it honest: the state is genuinely solved
    rather than clamped, and no absolute number from it reaches the engine.  See
    test_gvle3_hp_loop.py for the ratio machinery itself."""
    assert ts.classify(W_R207, 183.0, 144.9) == ts.DOMAIN_ELECTROLYTE
    assert vle.partial_pressures_bara(W_R207, 183.0)["in_grid"] is True
    fr = ts.flash(W_R207, 183.0, 144.9)
    assert fr.converged and 0.0 <= fr.psi_mole <= 1.0
    #  ... and the absolute answer is several-fold off the loop's real pressure, which is the whole
    #  reason the engine takes only the RATIO from here.
    assert ts.bubble_p(W_R207, 183.0) < 0.5 * 144.2


def test_domain_report_names_the_bound_that_failed():
    """Off-envelope reporting still has to name WHICH bound failed.  The molality is retained in the
    report even though nothing interpolates on it any more, because "N = 869 against a 16 top node"
    is the most legible statement of the failure this gap was about."""
    dry = {"NH3": 0.8, "CO2": 0.2, "H2O": 0.0}                        # no water at all
    rep = ts.domain_report(dry, 183.0, 144.9)
    assert rep["domain"] is None
    assert rep["in_grid"] is False
    assert rep["s_volatile_mole_frac"] > rep["s_envelope"][1]         # off the top of the s axis
    assert rep["n_load_mol_per_kg_water"] > 1e8                       # the old coordinate: divergent
    hot = ts.domain_report(W_C003, 260.0, 4.10)
    assert hot["domain"] is None and hot["t_c"] > hot["t_envelope_c"][1]


def test_flash_refuses_a_volatile_split_on_a_urea_melt():
    """The neutral binary carries no NH3/CO2 and the electrolyte path is outside its dilute limit in
    a 98 wt% urea melt -- bubble_p stays valid there, a volatile split does not."""
    with pytest.raises(ts.OutOfDomain):
        ts.flash(W_E003, 140.0, 0.131)
    assert ts.bubble_p(W_E003, 140.0) > 0.0


# ---------------------------------------------------------------------------- bubble / dew points

def test_bubble_p_reproduces_the_pfd_within_the_models_stated_accuracy():
    """The model's honest residual against the PFD -- not a fitted anchor.  The test pins the
    ENVELOPE of that residual so a regression in the activity path is caught.

    Ideal-vapour (what `vle_nh3co2h2o.bubble_p_bara` reports): +7.0 / +17.5 / +1.7 %.
    Full gamma-phi (what this service reports, phi < 1 raises P): +8.8 / +18.3 / +2.1 %."""
    expected = {"323C003": (4.10, 0.12), "323F004": (1.13, 0.20), "323F010": (0.46, 0.05)}
    for tag, w, t_c, _p in STAGES_323:
        p_pfd, rel_tol = expected[tag]
        p_model = ts.bubble_p(w, t_c)
        assert math.isclose(p_model, p_pfd, rel_tol=rel_tol), f"{tag}: {p_model} vs {p_pfd}"


def test_ideal_bubble_p_equals_the_sum_of_its_partial_pressures():
    for tag, w, t_c, _p in STAGES_323:
        parts = ts.partial_pressures(w, t_c)
        assert math.isclose(ts.bubble_p(w, t_c, srk=False), sum(parts[s] for s in ts.VOLATILE),
                            rel_tol=1e-12), tag


def test_srk_raises_the_bubble_point_above_the_ideal_sum():
    """phi < 1 for all three volatiles at these states, so P = sum p_i/phi_i must exceed sum p_i.
    If the correction were silently skipped the two would be identical."""
    for tag, w, t_c, _p in STAGES_323:
        assert ts.bubble_p(w, t_c) > ts.bubble_p(w, t_c, srk=False) * (1.0 + 1e-4), tag


def test_bubble_t_inverts_bubble_p():
    """The SOLVER inverts bubble_p to 1 mK.  The memoised `bubble_t` answers for its quantisation
    bin, solved at the bin's canonical point, so it is allowed the bin's own error and no more:
    measured worst 4.6 mK across these stages (323F010, where 1e-4 of water fraction moves the bubble
    point most), held to 10 mK here -- an order below any TT in the plant."""
    for tag, w, t_c, _p in STAGES_323:
        p = ts.bubble_p(w, t_c)
        assert math.isclose(ts._bubble_t_solve(w, p), t_c, abs_tol=1e-3), tag
        assert math.isclose(ts.bubble_t(w, p), t_c, abs_tol=1e-2), tag


def test_bubble_t_rises_with_pressure():
    for tag, w, t_c, _p in STAGES_323:
        p = ts.bubble_p(w, t_c)
        assert ts.bubble_t(w, 1.3 * p) > ts.bubble_t(w, 0.8 * p), tag


# --------------------------------------------------------------------------------- the flash itself

def test_flash_converges_at_every_323_design_state():
    ts.flash_cache_clear()
    for tag, w, t_c, p in STAGES_323:
        fr = ts.flash(w, t_c, p)
        assert fr.converged, f"{tag}: residual {fr.residual}"
        assert fr.domain == ts.DOMAIN_ELECTROLYTE, tag


def test_flash_conserves_mass_across_the_phase_split():
    """z = (1-psi)x + psi*y per species, on the mass basis the engine's species layer uses."""
    for tag, w, t_c, p in STAGES_323:
        fr = ts.flash(w, t_c, p)
        for s in ts.SPECIES:
            recon = (1.0 - fr.psi_mass) * fr.x[s] + fr.psi_mass * fr.y[s]
            assert math.isclose(recon, w.get(s, 0.0), abs_tol=2e-3), f"{tag}/{s}"


def test_non_volatiles_never_enter_the_vapour():
    for tag, w, t_c, p in STAGES_323:
        fr = ts.flash(w, t_c, p)
        for s in ts.NONVOLATILE:
            assert fr.y[s] == 0.0, f"{tag}/{s}"
            assert fr.k[s] == 0.0, f"{tag}/{s}"


def test_vapour_fraction_is_bounded_below_total_vaporisation():
    """A liquor that is 69-80 wt% non-volatile urea CANNOT flash to psi = 1.  The non-volatile term
    -z_i/(1-psi) in the Rachford-Rice residual is the only thing that enforces it; dropping those
    species from the sum (the obvious filter, since K = 0 contributes nothing at psi = 0) returned
    psi_mass = 1.0 at all three stages."""
    for tag, w, t_c, p in STAGES_323:
        fr = ts.flash(w, t_c, p)
        assert 0.0 <= fr.psi_mass < 1.0, tag
        assert fr.psi_mass < 1.0 - w["Urea"] + 1e-6, tag


def test_flash_responds_to_temperature_and_pressure():
    """The whole point of Phase 1: the frozen alpha vector this replaces had a derivative of exactly
    zero in both T and P.  More heat -> more vapour; more pressure -> less."""
    w, t_c, p = W_C003, 135.0, 4.10
    assert ts.flash(w, t_c + 6.0, p).psi_mass > ts.flash(w, t_c, p).psi_mass
    assert ts.flash(w, t_c, p * 1.25).psi_mass < ts.flash(w, t_c, p).psi_mass


def test_k_values_order_the_volatiles_physically():
    """At 323F010 (99 C, deep-ish vacuum, near-stripped liquor) the vapour is overwhelmingly water."""
    fr = ts.flash(W_F010, 99.0, 0.46)
    assert fr.y["H2O"] > 0.85
    assert fr.y["H2O"] > fr.y["NH3"] > 0.0


def test_srk_fugacity_is_applied_and_moves_the_answer():
    """phi != 1 at 4.1 bar a: if SRK were silently ideal the K-values would be unchanged."""
    fr = ts.flash(W_C003, 135.0, 4.10)
    y_mole = ts.mass_to_mole(fr.y)
    phi = ts.vapour_fugacity(y_mole, 135.0, 4.10)
    assert any(abs(phi[s] - 1.0) > 1e-3 for s in ("H2O", "NH3", "CO2"))
    for s in ("H2O", "NH3", "CO2"):
        assert 0.5 < phi[s] <= 1.0


# ------------------------------------------------------------------------------------- PH flash

def test_flash_ph_inverts_the_isothermal_flash():
    """h(T) from a converged flash, fed back through flash_ph, must return the same T."""
    for tag, w, t_c, p in STAGES_323:
        fr = ts.flash(w, t_c, p)
        h = ts.mixture_enthalpy_kj_per_kg(fr)
        back = ts.flash_ph(w, h, p)
        assert math.isclose(back.t_c, t_c, abs_tol=0.05), f"{tag}: {back.t_c} vs {t_c}"


def test_mixture_enthalpy_rises_with_temperature():
    w, p = W_C003, 4.10
    h_lo = ts.mixture_enthalpy_kj_per_kg(ts.flash(w, 120.0, p))
    h_hi = ts.mixture_enthalpy_kj_per_kg(ts.flash(w, 145.0, p))
    assert h_hi > h_lo


# ------------------------------------------------------------------------------------- the cache

def test_quantised_cache_does_not_change_the_answer():
    ts.flash_cache_clear()
    cold = ts.flash(W_C003, 135.0, 4.10)
    warm = ts.flash(W_C003, 135.0, 4.10)
    assert ts.flash_cache_stats()["hit"] == 1               # served from the memo...
    for s in ts.SPECIES:                                     # ...and identical to the solve
        assert warm.y[s] == cold.y[s] and warm.x[s] == cold.x[s], s
    ts.flash_cache_clear()
    fresh = ts.flash(W_C003, 135.0, 4.10)
    for s in ts.SPECIES:
        assert math.isclose(fresh.y[s], cold.y[s], rel_tol=1e-12, abs_tol=1e-12), s
    assert math.isclose(fresh.psi_mass, cold.psi_mass, rel_tol=1e-12)


def test_cache_quantum_is_far_below_instrument_resolution():
    """The memo may only hide changes smaller than anything the plant can see."""
    assert ts._T_QUANTUM_C <= 0.05          # C -- finer than any TT
    assert ts._P_QUANTUM_BARA <= 1.0e-3     # bar a -- finer than any PT


def test_memo_answer_does_not_depend_on_which_point_filled_the_bin():
    """Regression for the path dependence found 2026-09-16.  Both memos used to solve at the CALLER's
    point and serve that answer to the whole bin, so a value depended on what the process had asked
    before.  It moved 323F010 by 10 mK over 1 200 s in the engine, and a cold boot-pin cache took the
    worst branch.  Two points inside one bin, filled in either order, must now return the same
    float -- and the flash must not inherit a warm start from an unrelated earlier solve."""
    p = ts.bubble_p(W_F010, 99.0)
    nudged = dict(W_F010, H2O=W_F010["H2O"] + 0.3 * ts._W_QUANTUM)
    ts.flash_cache_clear()
    first = ts.bubble_t(W_F010, p)
    ts.flash_cache_clear()
    ts.bubble_t(nudged, p)
    assert ts.bubble_t(W_F010, p) == first

    #  Flash: the memo stores the canonical K; x, y and psi are re-solved on the caller's own feed.
    #  So a nudged point shares the unnudged point's K exactly, and its own answer does not depend
    #  on what filled the bin or on a warm start left behind by an unrelated solve.
    nudged_c003 = dict(W_C003, H2O=W_C003["H2O"] + 0.3 * ts._W_QUANTUM)
    ts.flash_cache_clear()
    fr_a = ts.flash(W_C003, 135.0, 4.10)
    fr_b_first = ts.flash(nudged_c003, 135.004, 4.10)
    ts.flash_cache_clear()
    ts._flash_solve(W_C003, 128.0, 4.10)          # leaves a warm start in the same coarse bucket
    fr_b = ts.flash(nudged_c003, 135.004, 4.10)
    assert fr_b.k == fr_a.k
    for slot in ts.FlashResult.__slots__:
        assert getattr(fr_b, slot) == getattr(fr_b_first, slot), slot


def test_memo_answers_for_the_callers_point_not_the_bins():
    """The bin's canonical value served flat was a relay: 323F004's liquor carries 0.665 wt% CO2,
    a 1e-4 bin is 1.5 % of that, and the electrolyte bubble point moves 0.19 C across it.  The F004
    pressure loop chattered on the edge.  Both memos now answer for the caller: bubble_t to within a
    millikelvin of the exact solve, flash alpha within 0.3 %, and neither steps at the bin edge."""
    base = dict(Urea=0.717279, Biuret=0.00377431, NH3=0.00883245, CO2=0.00664998, H2O=0.263464)
    ts.flash_cache_clear()
    prev = None
    for i in range(-8, 9):
        z = ts._norm_mass(dict(base, CO2=0.00665 + i * 1.0e-5))
        exact = ts._bubble_t_solve(z, 1.13)
        memo = ts.bubble_t(z, 1.13)
        assert abs(memo - exact) < 1.0e-3, (i, memo, exact)
        if prev is not None:                               # exact slope is -19.3 mK per step
            assert -0.021 < memo - prev < -0.018, (i, memo - prev)
        prev = memo
        fm = ts.flash(z, 106.0, 1.13)
        fe = ts._flash_solve(z, 106.0, 1.13, warm=False)
        assert abs(fm.y["CO2"] / fe.y["CO2"] - 1.0) < 3.0e-3, i


def test_cache_misses_when_the_state_actually_moves():
    ts.flash_cache_clear()
    ts.flash(W_C003, 135.0, 4.10)
    ts.flash(W_C003, 135.0 + 10.0 * ts._T_QUANTUM_C, 4.10)
    assert ts.flash_cache_stats()["miss"] == 2


# ------------------------------------------------------------------------- underlying-module wiring

def test_partial_pressure_split_did_not_move_the_legacy_bubble_point():
    """`vle_nh3co2h2o.bubble_p_bara` was refactored to sum `partial_pressures_bara`.  Its documented
    323C003 value was 4.387 on the molality grid and is 4.3516 on the G-VLE-3 mole-fraction grid --
    a 0.8 % move, TOWARD the 4.10 bar a PFD value, from re-indexing and re-grading the same nodes of
    the same model.  That number is the whole evidence that the re-index is a coordinate change:
    the interpolation weighting is provably identical in the dilute limit (see
    test_gvle3_hp_loop.py::test_the_s_axis_weighting_is_the_old_log_molality_weighting) and what
    is left is the node placement."""
    assert math.isclose(vle.bubble_p_bara(W_C003, 135.0), 4.3516, abs_tol=2e-3)


def test_out_of_grid_is_flagged_by_the_underlying_module():
    """The flag now carries strictly more than an axis test: it is False if any of the eight corner
    nodes the interpolation actually uses failed to converge, so a clamp can no longer hide."""
    assert vle.partial_pressures_bara(W_C003, 135.0)["in_grid"] is True
    assert vle.partial_pressures_bara(W_R207, 183.0)["in_grid"] is True        # G-VLE-3: was False
    assert vle.partial_pressures_bara({"NH3": 0.8, "CO2": 0.2, "H2O": 0.0},
                                      183.0)["in_grid"] is False               # no water: off the top


# ------------------------------------------------------------------------------------- dew point

def test_dew_t_of_pure_steam_is_the_water_saturation_line():
    """Pressures chosen so T_sat lands INSIDE the table's 80-170 C span; at 0.46 bar a T_sat is
    ~79 C, below the bottom node, and the service correctly refuses rather than clamping to it."""
    assert math.isclose(ts.dew_t({"H2O": 1.0}, 1.0), 100.0, abs_tol=1.0)
    assert math.isclose(ts.dew_t({"H2O": 1.0}, 4.0), 143.6, abs_tol=1.5)
    with pytest.raises(ts.OutOfDomain):
        ts.dew_t({"H2O": 1.0}, 0.46)              # T_sat ~79 C -> below the table floor


def test_dew_t_refuses_a_carbamate_rich_vapour():
    """The incipient liquid of a 48 wt% CO2 vapour is a concentrated carbamate solution at N ~ 39,
    C ~ 35 mol/kg water -- the same high-loading data the HP loop needs and this repo does not have.
    Refusing is correct; returning a clamped edge node would not be."""
    y_c003 = ts.flash(W_C003, 135.0, 4.10).y
    with pytest.raises(ts.OutOfDomain):
        ts.dew_t(y_c003, 4.10)


def test_flash_and_bubble_point_are_mutually_consistent():
    """At T = bubble_t(P) the flash must return essentially zero vapour.  This ties the two entry
    points to ONE thermodynamic surface -- a bubble point computed from partial pressures and a
    vapour fraction computed from Rachford-Rice cannot disagree about where boiling starts."""
    for tag, w, _t, _p in STAGES_323:
        p = 2.0
        t_bub = ts.bubble_t(w, p)
        assert ts.flash(w, t_bub, p).psi_mole < 1e-8, tag
        assert ts.flash(w, t_bub + 3.0, p).psi_mole > 1e-6, tag     # and above it, vapour appears
