"""Phase 3 gate: the 322R001 reactor runs on rate laws, not on load multipliers.

WHY THIS FILE EXISTS
--------------------
Before Phase 3 the reactor's chemistry was two scaled constants:

    xi_urea = REACT_XI_UREA_DES * s * conversion_factor(L, W, T)
    xi_biu  = REACT_XI_BIU_DES  * s

`conversion_factor` is a separable correlation renormalised to return exactly 1.0 at design, so the
urea extent was independent of residence time, of holdup volume, and of concentration except through
two feed RATIOS.  Biuret -- the plant's principal product-quality specification -- carried no
temperature dependence whatsoever, so a hot reactor could not produce a quality excursion.

These tests assert the things that were previously IMPOSSIBLE, plus the anchor that must survive.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402
import reactor  # noqa: E402


def _feed():
    return dict(main._HPCC_DES["feed_kmolh"])


def _march(feed=None, t_top=None, level=0.8, vdot_scale=1.0):
    """Run the axial march, optionally shifting the whole node profile to a given top temperature."""
    nodes = list(main.REACT_NODE_SS_DES)
    if t_top is not None:
        nodes = [t_top - (main.REACT_NODE_SS_DES[-1] - t) for t in main.REACT_NODE_SS_DES]
    xi, per = reactor.urea_extent_pfr(
        feed if feed is not None else _feed(), nodes, main.REACT_ZETA_NODES,
        main._react_area_m2, main.REACT_LIQ_H_M, level, main._react_vdot_m3h * vdot_scale)
    return xi, per


# ------------------------------------------------------------------ the anchor that must survive
def test_the_design_extent_is_reproduced_by_the_rate_law():
    """A2 is back-solved so the march lands on the PFD extent -- and it is re-solved inside the boot
    pin against the LIVE settled feed, because the kinetic extent depends on the feed ABSOLUTELY
    where the old correlation depended only on its ratios.  Calibrating on the synthetic design feed
    instead put 2.5 % more urea through the reactor than the PFD allows."""
    main.state = main.State()
    pkt = main.step_sim(0.25)
    rr = pkt["sm_diagnostics"]["react"]
    assert math.isclose(rr["xi_urea"], main.REACT_XI_UREA_DES, rel_tol=1e-5), rr["xi_urea"]
    assert math.isclose(rr["xi_biu"], main.REACT_XI_BIU_DES, rel_tol=1e-5), rr["xi_biu"]


def test_the_conversion_factor_is_unity_on_the_design_seed():
    """conv_fac feeds the axial temperature profile, so an offset here shifts the whole column."""
    main.state = main.State()
    main.step_sim(0.25)
    assert math.isclose(main.state.react_conv_fac, 1.0, rel_tol=1e-5), main.state.react_conv_fac
    assert math.isclose(main.state.react_T_overflow, main.REACT_OVERFLOW_T_C, abs_tol=1e-4)


# --------------------------------------------------------- what the load multiplier could not do
def test_conversion_now_depends_on_residence_time():
    """THE finding.  `XI_UREA_DES * s * cf(L,W,T)` has no residence time in it at all: doubling the
    throughput through the same vessel changed the extent only through the load ratio, never through
    the time the liquid spends reacting."""
    base, _ = _march()
    slow, _ = _march(vdot_scale=0.6)
    fast, _ = _march(vdot_scale=1.4)
    assert slow > base > fast, (slow, base, fast)


def test_conversion_now_depends_on_holdup_volume():
    """Level sets the wetted volume the plug reacts in.  A level excursion had no effect on the old
    extent; it must have one now, and in the right direction."""
    lo, _ = _march(level=0.4)
    mid, _ = _march(level=0.6)
    hi, _ = _march(level=1.0)
    assert lo < mid < hi


def test_conversion_has_a_real_temperature_optimum_not_a_fitted_parabola():
    """The old model imposed the optimum as exp[-k((T-Topt)^2 - (T0-Topt)^2)] with Topt fitted.
    Here it EMERGES: the Arrhenius rate constant rises with temperature while the OVERALL reaction
    is exothermic (-117 + 15.5 = -101.5 kJ/mol) so its equilibrium conversion falls.  The turnover is
    where those cross, and nothing in the code names a peak temperature."""
    xs = {t: _march(t_top=t)[0] for t in (160.0, 180.0, 200.0, 230.0, 250.0)}
    assert xs[180.0] > xs[160.0]                 # rate-limited flank, rising
    assert xs[250.0] < xs[230.0] < xs[200.0]     # equilibrium-limited flank, falling
    peak = max(xs, key=xs.get)
    assert 180.0 < peak < 230.0, xs


def test_a_hotter_reactor_does_not_convert_more_without_limit():
    """The regression this guards against is specific and was briefly real during Phase 3: with the
    dehydration step's own (ENDOTHERMIC) equilibrium as the only constraint, the march gave X = 0.92
    at 200 C and X = 1.00 at 230 C -- a simulator that teaches operators to run the reactor hot.
    The overall equilibrium is what actually constrains it."""
    feed = _feed()
    for t in (215.0, 230.0, 250.0):
        xi, _ = _march(t_top=t)
        assert xi / feed["CO2"] < 0.90, (t, xi / feed["CO2"])


def test_biuret_now_responds_to_temperature():
    """C-2.  `REACT_XI_BIU_DES * s` had a temperature derivative of exactly zero on the plant's
    principal product-quality specification."""
    f = lambda t: reactor.biuret_extent(
        [t - (main.REACT_NODE_SS_DES[-1] - x) for x in main.REACT_NODE_SS_DES],
        main.REACT_ZETA_NODES, main._react_area_m2, main.REACT_LIQ_H_M, 0.8,
        main._react_vdot_m3h, main.REACT_OVERFLOW_DES["Urea"])
    assert f(200.0) > f(183.0) > f(170.0)
    #  Arrhenius at 85 kJ/mol: a 17 C rise near 183 C must roughly double it, not nudge it.
    assert f(200.0) / f(183.0) > 1.5


def test_biuret_is_second_order_in_urea():
    """r = A exp(-Ea/RT) C_urea^2, so quadrupling the urea concentration multiplies it by 16."""
    f = lambda u: reactor.biuret_extent(
        main.REACT_NODE_SS_DES, main.REACT_ZETA_NODES, main._react_area_m2, main.REACT_LIQ_H_M,
        0.8, main._react_vdot_m3h, u)
    base = main.REACT_OVERFLOW_DES["Urea"]
    assert math.isclose(f(4.0 * base) / f(base), 16.0, rel_tol=1e-9)


# ------------------------------------------------------------------------- the sourced constants
def test_the_activation_energy_is_derived_from_in_repo_sources():
    """Ea(dehydration) is NOT asserted from an outside table.  Inoue & Otsuka (1973) Eq. (6) gives
    the reverse step as ln k = 21.8 - 11100/T, i.e. R*11100 = 92.3 kJ/mol; for one elementary step
    run both ways the activation energies differ by the step enthalpy, and the Helwan dehydration
    enthalpy is +15.5 kJ/mol.  Both numbers already carry citations elsewhere in this repo."""
    assert reactor.EA_HYD_REV_K == main.R328_HYD_K_B_K
    assert reactor.DH_DEHYD_JMOL == -main.STRIP_DH_HYD_JMOL
    assert math.isclose(reactor.EA_DEHYD_JMOL,
                        main.R328_HYD_K_B_K * reactor.R_GAS_J - main.STRIP_DH_HYD_JMOL,
                        rel_tol=1e-12)
    #  ... and the overall enthalpy is the same -101.5 kJ/mol the desorption section already carries.
    assert math.isclose(-reactor.DH_OVERALL_JMOL / 1000.0, main.R328_HYD_DH_KJMOL, rel_tol=1e-12)
    #  Biuret shares the stripper's activation energy rather than inventing one.
    assert reactor.BIU_EA_JMOL == main.STRIP_BIU_EA


def test_only_two_scale_factors_are_back_solved():
    """Everything else in the rate law is sourced.  If a future edit adds a third fitted constant it
    should have to change this test and say why."""
    cal = main.REACT_KIN_CAL
    assert set(cal) == {"A2", "Keq_ov_ref", "T_ref_K", "biu_A"}
    assert cal["A2"] > 0.0 and cal["biu_A"] > 0.0
    #  A2 lands where an ordinary liquid-phase pre-exponential should for Ea = 107.8 kJ/mol.
    assert 1.0e10 < cal["A2"] < 1.0e15, cal["A2"]
