"""G-VLE-3: the rebuilt parameter grid, the inert thermodynamics, and the 322 HP-loop wiring.

Three separable claims are pinned here, and they are pinned separately on purpose:

  1. the RE-INDEX is a coordinate change, not a new model -- the validated 323 bubble pressures
     survive it, and the logit weighting reduces to the old log-molality weighting in the dilute
     limit where the old table was actually valid;
  2. the SOLVER reach was an initial-guess failure, not a domain limit -- the same Newton that
     stalls at N = 50 from a cold start converges to 1e-13 at N = 869 from a neighbour;
  3. the loop is wired through an ANCHORED RATIO whose identity at design is exact arithmetic, not
     a tolerance and not a short-circuit -- which is the only reason an extrapolated parameter set
     is allowed anywhere near the licensor's calibrated splits.

What is deliberately NOT pinned anywhere below is an absolute HP-loop VLE number.  The model puts
the 322R001 overflow's bubble pressure 3.6x low; a test asserting that number would be pinning an
extrapolation.  `test_the_extrapolation_is_recorded_not_hidden` pins the FACT of it instead.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import iapws_if97                            # noqa: E402
import props_nh3co2h2o as props              # noqa: E402
import thermo_service as ts                  # noqa: E402
import vle_nh3co2h2o as vle                  # noqa: E402

#  The three stages whose bubble pressures `vle_nh3co2h2o` validates against the PFD.
W_C003 = {"Urea": 68.74, "Biuret": 0.36, "NH3": 2.13, "CO2": 1.05, "H2O": 27.72}
W_F004 = {"Urea": 71.74, "Biuret": 0.37, "NH3": 0.88, "CO2": 0.66, "H2O": 26.35}
W_F010 = {"Urea": 80.00, "Biuret": 0.42, "NH3": 0.08, "CO2": 0.02, "H2O": 19.48}
#  322R001 overflow = stream 207, from the design molar vector.
_R207_KMOLH = {"Urea": 1302.6, "Biuret": 2.414, "NH3": 4002.4, "CO2": 897.7, "H2O": 2222.0}
_m = {k: n * vle.MW[k] for k, n in _R207_KMOLH.items()}
W_R207 = {k: v / sum(_m.values()) for k, v in _m.items()}

_main = None


def _engine():
    global _main
    if _main is None:
        import main
        _main = main
    return _main


# ==================================================================================================
#  1.  Inert thermodynamics -- the half of G-VLE-3 that was missing DATA, not wiring
# ==================================================================================================
def test_the_inert_henry_constants_reproduce_the_textbook_25c_values():
    """IAPWS G7-04 against the classic mole-fraction Henry constants in water at 25 C.  This is the
    check that the transcribed (A, B, C) triples are the right ones for the right species."""
    lit = {"N2": 86500.0, "O2": 44000.0, "CH4": 41300.0, "H2": 71200.0}
    for sp, bar in lit.items():
        got = props.henry_inert_MPa(sp, 298.15) * 10.0
        assert abs(got / bar - 1.0) < 0.05, (sp, got, bar)


def test_the_inert_correlation_agrees_with_the_repos_own_co2_fit_at_the_loop_temperature():
    """The load-bearing validation.  CO2 is in the SAME published table as the four inerts and this
    repository ALSO holds an independent Rumpf & Maurer fit for it.  Two unrelated correlations
    agreeing at 183 C is what licenses the inert rows at 183 C, where no direct datum exists here.
    They agree to 0.2 % at 25 C and 5.0 % at 183 C, and the gap grows monotonically -- which is
    itself the honest statement of where the extrapolation starts to matter."""
    for t_c, tol in ((25.0, 0.01), (140.0, 0.03), (183.0, 0.06), (210.0, 0.08)):
        t_k = t_c + 273.15
        a = props.henry_inert_MPa("CO2", t_k)
        b = props.henry_co2_MPa(t_k)
        assert abs(a / b - 1.0) < tol, (t_c, a, b)


def test_permanent_gas_solubility_turns_around_which_is_why_a_vant_hoff_fit_was_refused():
    """Gas solubility in water passes through a MINIMUM near 80-100 C, i.e. the Henry constant
    through a MAXIMUM.  A two-parameter van't Hoff extrapolated from 25 C has it falling
    monotonically and is badly wrong by the loop's own 183 C.  G7-04 reproduces the turn."""
    for sp in ("N2", "O2", "CH4"):
        k = [props.henry_inert_MPa(sp, t + 273.15) for t in (25, 60, 100, 140, 183, 210)]
        assert k[2] > k[0], sp                      # still rising at 100 C
        assert k[-1] < k[2], sp                     # and falling again by 210 C
        assert max(k) == k[max(range(len(k)), key=lambda i: k[i])]


def test_the_inerts_have_srk_constants_and_are_not_ideal_in_the_loop():
    """Before G-VLE-3 `SRK_CRIT` held H2O/NH3/CO2 only, so an inert in the vapour was returned
    phi = 1.0.  At 144.2 bar a and 183 C that is a 20-30 % error on the light gases, and it lands
    directly on their K-values."""
    for sp in vle.INERTS:
        assert sp in props.SRK_CRIT
    phi, z = props.srk_phi({"NH3": 0.6, "CO2": 0.2, "N2": 0.15, "H2": 0.05}, 456.15, 144.2e5)
    assert phi["N2"] > 1.15 and phi["H2"] > 1.15    # light gases: phi ABOVE unity in a dense mixture
    assert phi["NH3"] < 0.9 and phi["CO2"] < 0.95   # condensables: below
    assert 0.5 < z < 1.0
    assert props.SRK_CRIT["H2"][2] < 0.0            # H2's acentric factor is negative -- not a typo


# ==================================================================================================
#  2.  The solver reach was a basin failure, not a domain limit
# ==================================================================================================
def test_the_cold_solver_stalls_where_the_seeded_one_converges():
    """The diagnosis that unlocked the whole gap, pinned so nobody re-derives it.

    From its dilute ansatz the speciation Newton returns a residual of order 10 at N = 50 mol/kg
    water and STAYS there -- more iterations do not help, because it is not converging slowly, it is
    sitting on a non-solution.  Seeded from a converged neighbour the identical solver reaches the
    322E003 loading in a handful of steps at machine precision."""
    t_k = 456.15
    cold = props.speciate(50.0, 11.2, T=t_k)
    assert cold["resid"] > 1.0                                        # a non-solution, not a slow one
    assert props.speciate(50.0, 11.2, T=t_k, maxiter=4000)["resid"] > 1.0   # ... and iterations do not fix it

    seed = {s: props.speciate(40.0, 8.96, T=t_k)[s] for s in props._SOLUTES}
    assert props.speciate(40.0, 8.96, T=t_k)["resid"] < 1e-9          # the neighbour IS converged
    for n, c in ((50.0, 11.2), (100.0, 22.4), (300.0, 67.2), (869.3, 194.7)):
        md = props.speciate(n, c, T=t_k, m_guess=seed)
        assert md["resid"] < 1e-9, (n, md["resid"])
        seed = {s: md[s] for s in props._SOLUTES}


def test_every_node_of_the_rebuilt_grid_is_a_converged_solve():
    """1215/1215.  A node that failed would be STORED with its flag cleared rather than dropped, so
    this also pins that the marching order in `_build_table` is the one that works."""
    st = vle.build_stats()
    assert st["nodes"] == len(vle._T_NODES) * len(vle._S_NODES) * len(vle._F_NODES)
    assert st["failed"] == 0, st


def test_a_cell_touching_an_unconverged_node_is_reported_out_of_grid():
    """The clamp is visible now.  `in_grid` is not just an axis test: clear one node's flag and
    every cell that uses it must stop claiming to be a solve."""
    tab = vle._ensure_table()
    i_t, i_s, i_f = 3, 6, 3
    keep = tab[i_t][i_s][i_f][4]
    try:
        tab[i_t][i_s][i_f][4] = 0.0
        t = 0.5 * (vle._T_NODES[i_t] + vle._T_NODES[i_t + 1])
        s = math.sqrt(vle._S_NODES[i_s] * vle._S_NODES[i_s + 1])
        f = math.sqrt(vle._F_NODES[i_f] * vle._F_NODES[i_f + 1])
        assert vle._interp(t, s, f)[4] is False
    finally:
        tab[i_t][i_s][i_f][4] = keep


# ==================================================================================================
#  3.  The re-index is a coordinate change
# ==================================================================================================
def test_the_coordinate_pair_round_trips_exactly():
    for s in (1e-5, 1e-3, 0.05, 0.3, 0.688, 0.953, 0.98):
        for f in (0.002, 0.05, 0.1832, 0.5, 0.78):
            n, c = vle.sf_to_loadings(s, f)
            s2, f2 = vle.loadings_to_sf(n, c)
            assert abs(s2 - s) < 1e-12 and abs(f2 - f) < 1e-12, (s, f, s2, f2)


def test_the_coordinates_stay_finite_where_the_molalities_diverge():
    """The whole reason for the re-index.  A liquor with no water has an INFINITE molality and a
    perfectly ordinary mole fraction, and the second is what the table is indexed on now."""
    dry = {"NH3": 0.8, "CO2": 0.2, "H2O": 0.0}
    n, c = vle.loadings(dry)
    assert n > 1e8 and c > 1e8                       # the old coordinate: unusable
    s, f = vle.coords(dry)
    assert math.isfinite(s) and math.isfinite(f)
    assert abs(s - 1.0) < 1e-12                      # the new one: on the boundary, and finite
    assert vle.partial_pressures_bara(dry, 183.0)["in_grid"] is False   # ... and honestly refused


def test_the_validated_323_bubble_pressures_survive_the_re_index():
    """The regression that proves this is a coordinate change.  These three stages are the module's
    published validation against the PFD; the re-index moves them by under a point of percentage
    and, at two of the three, TOWARD the plant."""
    for w, t_c, p_pfd, tol in ((W_C003, 135.0, 4.10, 0.10),
                               (W_F004, 106.0, 1.13, 0.20),
                               (W_F010, 99.0, 0.46, 0.05)):
        p = vle.bubble_p_bara(w, t_c)
        assert abs(p / p_pfd - 1.0) < tol, (t_c, p, p_pfd)
        assert vle.partial_pressures_bara(w, t_c)["in_grid"] is True


def test_the_s_axis_weighting_is_the_old_log_molality_weighting():
    """logit(s) = ln(s/(1-s)) = ln(N + C) - ln(55.508) exactly, so in the dilute limit -- the only
    place the old molality table was valid -- the new grid interpolates on the identical
    coordinate.  That identity is what makes the re-index reviewable."""
    for n, c in ((1e-4, 1e-5), (0.5, 0.1), (4.51, 0.86), (16.0, 7.0)):
        s, _ = vle.loadings_to_sf(n, c)
        assert abs(math.log(s / (1.0 - s)) - (math.log(n + c) - math.log(vle._N_W_PER_KG))) < 1e-12


def test_the_bubble_pressure_is_monotone_over_the_whole_widened_band():
    """`bubble_t_c` bisects on the assumption that P_bub rises with T, and the band now runs to
    210 C.  If a grid re-grade ever broke monotonicity the root-finder would return silently wrong
    temperatures, so it is asserted rather than assumed."""
    prev = None
    for t in range(80, 211, 5):
        p = vle.bubble_p_bara(W_C003, float(t))
        assert prev is None or p > prev, (t, p, prev)
        prev = p


# ==================================================================================================
#  4.  The HP loop is in domain -- and the extrapolation is on the record
# ==================================================================================================
def test_the_hp_loop_states_are_now_inside_the_envelope():
    """322R001's overflow used to read N = 100 against a top node of 16 and was refused.  The same
    liquor is an unremarkable point in mole fractions."""
    n, c = vle.loadings(W_R207)
    assert n > 90.0 and c > 20.0                            # the old coordinate, unchanged
    s, f = vle.coords(W_R207)
    assert 0.60 < s < 0.75 and 0.15 < f < 0.22
    assert vle.partial_pressures_bara(W_R207, 183.0)["in_grid"] is True
    assert ts.classify(W_R207, 183.0, 144.2) == ts.DOMAIN_ELECTROLYTE


def test_the_extrapolation_is_recorded_not_hidden():
    """The parameter set is a dilute-aqueous CO2-capture fit and the synthesis loop is far outside
    it.  The model puts 322R001's bubble pressure several-fold below the pressure the loop actually
    runs at, and that is exactly why no absolute number from it reaches the engine.  Pinned as a
    BAND, not a value: the point is the order of the error, not its third digit."""
    p = vle.bubble_p_bara(W_R207, 183.0)
    assert 10.0 < p < 90.0                                  # against a loop at 144.2 bar a
    assert p < 0.5 * 144.2


def test_the_inerts_generate_real_k_values_instead_of_a_refusal():
    """`SCRUB_OFFGAS_KMOLH_DES` is 84 mol% inert and they are the only species with a route out of
    the plant.  Their K-values must be large -- they are permanent gases over a hot melt -- finite,
    and ordered by solubility (H2 and N2 less soluble than CH4 -> larger K)."""
    w = {"NH3": 0.30, "CO2": 0.38, "H2O": 0.30, "N2": 0.015, "O2": 0.003,
         "CH4": 0.0015, "H2": 0.0005}
    k = ts.k_values(w, 114.0, 144.2)
    for sp in vle.INERTS:
        assert math.isfinite(k[sp]) and k[sp] > 1.0, (sp, k[sp])
    assert k["N2"] > k["CH4"]                               # N2 is the least soluble of the four
    assert k["H2O"] < k["NH3"]                              # and water still the heaviest volatile


# ==================================================================================================
#  5.  The anchored ratio -- exactness, direction, and the refusal path
# ==================================================================================================
def test_the_ratio_is_exactly_one_at_its_own_reference():
    """Not `isclose`.  With no reference composition the two K-value calls take identical
    arguments, so they are the same float and the quotient is the IEEE 1.0 -- which is what carries
    the design seed, with no identity short-circuit hiding a residual."""
    r = ts.k_ratio(W_C003, 135.0, 4.10, 135.0, 4.10)
    for sp in ts.DISTRIBUTING:
        assert r[sp] == 1.0, (sp, r[sp])
    r2 = ts.k_ratio(W_R207, 183.0, 144.2, 183.0, 144.2)
    assert all(v == 1.0 for v in r2.values())


def test_the_ratio_separates_nh3_from_co2_which_the_frozen_slope_could_not():
    """`HPCC_FLASH_DH` pinned dH_NH3 == dH_CO2 == 53 333 J/mol on the carbamate cube-root argument,
    so the two moved together BY CONSTRUCTION and the condensate N/C could not respond to
    temperature at all.  The gamma-phi derivative separates their MOVEMENT by a factor of ~3: over
    a +10 C step K_CO2 rises 75.6 % against K_NH3's 24.1 %."""
    r = ts.k_ratio(W_C003, 145.0, 4.10, 135.0, 4.10)
    assert r["CO2"] > 1.0 and r["NH3"] > 1.0
    assert (r["CO2"] - 1.0) > 2.5 * (r["NH3"] - 1.0)


def test_the_pressure_leg_of_the_ratio_is_not_the_naive_one_over_p():
    """At low pressure the ideal 1/P is recovered; at 144 bar the SRK fugacity pulls it away, which
    is the term `p_rat = P_des/P` never had."""
    r_lo = ts.k_ratio(W_C003, 135.0, 3.60, 135.0, 4.10)
    assert abs(r_lo["NH3"] - 4.10 / 3.60) < 0.02             # ~ideal down here
    r_hi = ts.k_ratio(W_R207, 183.0, 130.0, 183.0, 144.2)
    assert abs(r_hi["NH3"] - 144.2 / 130.0) > 0.01           # ... and demonstrably not up there


def test_the_ratio_falls_back_to_one_rather_than_raising_or_freezing():
    """Safety requirement: a true non-convergent or off-envelope state must degrade to the
    licensor's own split, not throw and not freeze the state."""
    dry = {"NH3": 0.8, "CO2": 0.2, "H2O": 0.0}
    assert ts.classify(dry, 183.0, 144.2) is None           # genuinely off-envelope
    r = ts.k_ratio(dry, 183.0, 144.2, 183.0, 140.7)         # ... and it still answers
    assert all(v == 1.0 for v in r.values())
    r2 = ts.k_ratio(W_C003, 400.0, 4.10, 135.0, 4.10)       # off the top of the temperature grid
    assert all(math.isfinite(v) for v in r2.values())


def test_the_ratio_is_bounded_so_an_extrapolation_cannot_run_away():
    """A 50x move in a condenser split is the model leaving its useful range, not a real event.  The
    band is a stated limit, not a tuning knob: outside it the anchored vector is the better answer."""
    r = ts.k_ratio(W_C003, 210.0, 0.5, 80.0, 40.0)
    for v in r.values():
        assert 0.02 <= v <= 50.0


# ==================================================================================================
#  6.  The two split transforms
# ==================================================================================================
def test_the_fraction_shift_is_an_exact_identity_at_unit_ratio():
    """theta' = r.theta/(1 + (r-1).theta).  At r == 1.0 the term (r-1.0) is exactly 0.0, so this is
    theta/1.0 -- by the arithmetic, with no branch to review."""
    main = _engine()
    for th in (0.0450, 0.2036, 0.2977, 0.8546, 0.999, 1e-9):
        assert main._ratio_shift_frac(th, 1.0) == th


def test_the_fraction_shift_cannot_leave_the_unit_interval():
    """The failure mode of the `* eta_P` multiply it replaces: at eta_P = 1.15 the N2 strip fraction
    went to 1.148 and was silently clamped, i.e. the column stripped more than it was fed."""
    main = _engine()
    for th in (0.01, 0.2, 0.5, 0.8546, 0.9987):
        for r in (0.02, 0.5, 1.0, 2.0, 10.0, 50.0):
            v = main._ratio_shift_frac(th, r)
            assert 0.0 < v < 1.0, (th, r, v)
        assert (main._ratio_shift_frac(th, 2.0) > main._ratio_shift_frac(th, 1.0)
                > main._ratio_shift_frac(th, 0.5))          # monotone in r


def test_the_structural_species_are_never_moved_by_either_transform():
    """theta of exactly 0 (urea: never boils) or exactly 1 (O2/CH4/H2 in the reactor: never
    dissolve) are STRUCTURAL, not calibrated.  Moving them would be a new claim with no datum."""
    main = _engine()
    assert main._ratio_shift_frac(0.0, 5.0) == 0.0
    assert main._ratio_shift_frac(1.0, 5.0) == 1.0
    feed = {k: 100.0 for k in main.MW_COMP}
    out = main._anchored_split(main.REACT_THETA_OG, feed, {k: 3.0 for k in main.MW_COMP})
    for k in ("O2", "CH4", "H2"):
        assert out[k] == main.REACT_THETA_OG[k] == 1.0
    for k in ("Urea", "Biuret"):
        assert out[k] == main.REACT_THETA_OG[k] == 0.0


def test_the_anchored_split_returns_the_design_vector_at_unit_ratio():
    """Not bit-exact and deliberately so -- this path re-solves Rachford-Rice by bisection at the
    design point instead of short-circuiting to the answer (Phase 1 finding A-15), so the residual
    of the K-value model there stays visible.  2^-60 is what that costs."""
    main = _engine()
    feed = {k: main.REACT_OVERFLOW_DES.get(k, 0.0) + main.REACT_OFFGAS_DES.get(k, 0.0)
            for k in main.MW_COMP}
    out = main._anchored_split(main.REACT_THETA_OG, feed, {k: 1.0 for k in main.MW_COMP})
    for k in main.MW_COMP:
        assert abs(out[k] - main.REACT_THETA_OG[k]) < 1e-9, (k, out[k])


# ==================================================================================================
#  7.  The four wirings are live
# ==================================================================================================
def test_the_hpcc_split_moves_with_temperature_and_pressure():
    """It had a Clausius-Clapeyron slope already (AUDIT F-6), so the claim here is only that the
    slope is now the rigorous one -- and that it still lands on the calibration at design."""
    main = _engine()
    feed = {k: main.HPCC_FRAC_GAS_DES.get(k, 0.0) * 0.0 + 100.0 for k in main.MW_COMP}
    #  The reference PAIR is (HPCC_T_PROD_DES_C, SYN_P_DES_BARA) and NOT this exchanger's own
    #  HPCC_P_DES_BARA -- `p_loop` is s.p_syn_bara, so anchoring to 144.2 would put a permanent
    #  3.5 bar offset into the ratio.  It did, and it cost the design seed by 3.4e-4 on phi_CO2
    #  before the reference was corrected, which is why the pair is asserted here and not assumed.
    p_ref = main.SYN_P_DES_BARA
    des = main._hpcc_flash_split(feed, main.HPCC_T_PROD_DES_C, p_ref)
    for k in ("CO2", "NH3", "H2O"):
        assert abs(des[k] - main.HPCC_FRAC_GAS_DES[k]) < 1e-9, (k, des[k])
    off = main._hpcc_flash_split(feed, main.HPCC_T_PROD_DES_C, main.HPCC_P_DES_BARA)
    assert abs(off["CO2"] - main.HPCC_FRAC_GAS_DES["CO2"]) > 1e-4      # the WRONG anchor is visible
    hot = main._hpcc_flash_split(feed, main.HPCC_T_PROD_DES_C + 12.0, p_ref)
    low = main._hpcc_flash_split(feed, main.HPCC_T_PROD_DES_C, p_ref - 12.0)
    assert hot["CO2"] > des["CO2"] and hot["NH3"] > des["NH3"]      # hotter -> less condensed
    assert low["CO2"] > des["CO2"]                                  # lower P -> less condensed
    assert hot["CO2"] / des["CO2"] != hot["NH3"] / des["NH3"]       # ... and no longer in lockstep


def test_the_reactor_disengagement_is_no_longer_frozen():
    """`REACT_THETA_OG` responded to the loop pressure with a derivative of exactly zero."""
    main = _engine()
    out_total = {k: main.REACT_OVERFLOW_DES.get(k, 0.0) + main.REACT_OFFGAS_DES.get(k, 0.0)
                 for k in main.MW_COMP}
    base = main._anchored_split(main.REACT_THETA_OG, out_total,
                                main._hp_k_ratio(out_total, main.REACT_OVERFLOW_T_C,
                                                 main.SYN_P_DES_BARA, main.REACT_OVERFLOW_T_C,
                                                 main.SYN_P_DES_BARA))
    low = main._anchored_split(main.REACT_THETA_OG, out_total,
                               main._hp_k_ratio(out_total, main.REACT_OVERFLOW_T_C,
                                                main.SYN_P_DES_BARA - 15.0,
                                                main.REACT_OVERFLOW_T_C, main.SYN_P_DES_BARA))
    assert abs(base["NH3"] - main.REACT_THETA_OG["NH3"]) < 1e-9     # design: the published vector
    assert low["NH3"] > base["NH3"] and low["CO2"] > base["CO2"]    # depressurise -> more off-gas


def test_the_stripper_pressure_term_is_per_species_and_replaced_not_stacked():
    """`eta_P` is GONE from `mod`, not multiplied by the ratio -- both modelled the same physics and
    keeping both would count the loop pressure twice."""
    main = _engine()
    import inspect
    body = inspect.getsource(main.stripper_322e001)
    #  The name survives in the comment that explains its removal -- which is the point of the
    #  comment.  What must be gone is the ASSIGNMENT and the multiply.
    code = [ln for ln in body.splitlines() if not ln.lstrip().startswith("#")]
    code = " ".join(code)
    assert "eta_P" not in code, "eta_P is still executed, not just documented"
    assert "_strip_ratio" in code and "_ratio_shift_frac" in code
    des = main.stripper_322e001(main.CO2_DES_KGH / 1000.0, main.STRIP_STEAM_T_DES_C,
                                main.STRIP_P_DES_BARA)
    low = main.stripper_322e001(main.CO2_DES_KGH / 1000.0, main.STRIP_STEAM_T_DES_C,
                                main.STRIP_P_DES_BARA - 12.0)
    f_des = des["top_kmolh"]["NH3"] / (des["top_kmolh"]["NH3"] + des["bot_kmolh"]["NH3"])
    f_low = low["top_kmolh"]["NH3"] / (low["top_kmolh"]["NH3"] + low["bot_kmolh"]["NH3"])
    assert f_low > f_des                                             # lower P strips harder
    #  species-specific, which one scalar eta_P could never be
    g_des = des["top_kmolh"]["CO2"] / (des["top_kmolh"]["CO2"] + des["bot_kmolh"]["CO2"])
    g_low = low["top_kmolh"]["CO2"] / (low["top_kmolh"]["CO2"] + low["bot_kmolh"]["CO2"])
    assert abs((f_low / f_des) - (g_low / g_des)) > 1e-6


def test_the_scrubber_vent_composition_is_no_longer_pinned():
    """`SCRUB_OFFGAS_KMOLH_DES * s` made the vent composition a constant: it is the plant's only
    inert route and it could not respond to anything.  It now rides PT-329201 -- and only
    PT-329201, because TT-322011 is a fitted correlation and not a state (see the note above the
    ratio call in `scrub_322e003`).  Two properties are asserted together because the fix for one
    of them broke the other once already:

      * the COMPOSITION responds to loop pressure, and
      * the vented TOTAL does not.

    The second is what keeps the vent out of a positive feedback with loop inventory: a higher
    PT-329201 lowers every K, and if that were allowed to lower the vented moles the loop would
    retain inventory and raise PT-329201 again.  Measured at -0.41 % of vent per bar, which is
    weak per tick and integrates over a transient."""
    main = _engine()
    fd = {k: main.REACT_OFFGAS_DES.get(k, 0.0) for k in main.MW_COMP}
    p0 = main.state.p_syn_bara
    try:
        base = main.scrub_322e003(fd, 1.0, 80.0, 300000.0)
        main.state.p_syn_bara = p0 + 1.0
        off = main.scrub_322e003(fd, 1.0, 80.0, 300000.0)
    finally:
        main.state.p_syn_bara = p0
    n0 = sum(base["offgas_kmolh"].values())
    n1 = sum(off["offgas_kmolh"].values())
    y0 = base["offgas_kmolh"]["NH3"] / max(n0, 1e-9)
    y1 = off["offgas_kmolh"]["NH3"] / max(n1, 1e-9)
    assert abs(y1 - y0) > 1e-9, ("vent composition did not respond to PT-329201", y0, y1)

    #  The vented TOTAL must stay nearly pressure-insensitive, and this is a regression guard with a
    #  measured number behind it rather than a round figure.  Without the renormalisation in
    #  `scrub_322e003` the ratio moved the vent by -0.41 % per bar; with it the residual is -0.11 %,
    #  which arrives indirectly -- the block itself is total-preserving by construction, but the
    #  flash-back stage downstream re-derives a total from the composition the ratio changed.  A
    #  pressure-driven vent total is a POSITIVE feedback on loop inventory (higher P -> lower K ->
    #  fewer moles vented -> more inventory retained -> higher P), weak per tick and integrating over
    #  a transient, so the bound matters more than its exact value.  Neutralising the ratio gives
    #  exactly 0.0, so this measures the ratio's whole contribution.
    _real = main._hp_k_ratio
    main._hp_k_ratio = lambda *a, **k: {s: 1.0 for s in main.MW_COMP}
    try:
        flat0 = main.scrub_322e003(fd, 1.0, 80.0, 300000.0)
        main.state.p_syn_bara = p0 + 1.0
        flat1 = main.scrub_322e003(fd, 1.0, 80.0, 300000.0)
    finally:
        main._hp_k_ratio = _real
        main.state.p_syn_bara = p0
    d_ratio = n1 - n0
    d_flat = sum(flat1["offgas_kmolh"].values()) - sum(flat0["offgas_kmolh"].values())
    assert abs(d_flat) < 1e-9, ("neutralising the ratio must leave the vent total flat", d_flat)
    pct_per_bar = 100.0 * abs(d_ratio) / max(n0, 1e-9)
    assert pct_per_bar < 0.20, (
        "the vent total's pressure sensitivity regressed toward the un-renormalised -0.41 %/bar",
        pct_per_bar)

    for r in (base, off):
        tot_in = sum(r["feed_kmolh"].values())
        tot_out = sum(r["offgas_kmolh"].values()) + sum(r["overflow_kmolh"].values())
        assert abs(tot_in - tot_out) < 1e-6 * max(tot_in, 1.0)


def test_the_scrubber_holds_its_pinned_design_vectors_exactly():
    """The re-partition is a DEVIATION: at the design N/C, the design vent opening and the design
    loop pressure every delta is a literal 0.0 and the two pinned HMB vectors are untouched."""
    main = _engine()
    fd = {k: main.REACT_OFFGAS_DES.get(k, 0.0) for k in main.MW_COMP}
    r = main.scrub_322e003(fd, 1.0, 80.0, 300000.0)
    for k in main.MW_COMP:
        assert r["offgas_kmolh"][k] == main.SCRUB_OFFGAS_KMOLH_DES.get(k, 0.0), k


def test_the_engine_reports_the_grid_and_its_build_cost():
    """The boot penalty is a number the operator can see, not folklore."""
    st = vle.build_stats()
    assert st["nodes"] > 1000 and "seconds" in st and "cached" in st
    assert "G7-04" in vle.MODEL_NAME or "Henry" in vle.MODEL_NAME


def test_the_pressure_band_is_declared_and_covers_the_loop():
    """There is no pressure AXIS on the table and there should not be -- the Extended UNIQUAC
    activity model has no pressure dependence, and the one term that would give it one (Poynting)
    needs infinite-dilution partial molar volumes this repository does not hold.  So the band is a
    DECLARATION: 0.02 to 180 bar a, covering the 144.2 bar synthesis loop and the 0.05 bar vacuum
    stages, enforced by `classify` so that a wild transient refuses instead of being answered by a
    model with no opinion about pressure."""
    lo, hi = vle.VALID_PRESSURE_BARA
    assert lo <= 0.05 and hi >= 180.0
    assert ts.classify(W_C003, 135.0, 144.2) == ts.DOMAIN_ELECTROLYTE
    assert ts.classify(W_C003, 135.0, 179.0) == ts.DOMAIN_ELECTROLYTE
    assert ts.classify(W_C003, 135.0, hi + 20.0) is None
    assert ts.classify(W_C003, 135.0) == ts.DOMAIN_ELECTROLYTE       # p unknown -> not a bound
    #  ... and the refusal reaches the engine as the licensor's own split, not as an exception
    r = ts.k_ratio(W_C003, 135.0, hi + 20.0, 135.0, 4.10)
    assert all(v == 1.0 for v in r.values())
