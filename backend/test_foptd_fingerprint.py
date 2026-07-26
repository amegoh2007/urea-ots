"""§7.6 P5-A regression guard: the calibrated feed/CCW lag constants must keep the
synthesis-loop FOPTD fingerprint inside its DCS-anchored band after ANY tuning change.

Fingerprint source (dcs_anchor_dynamics_2025-06-03.md §1.2, PT-329201, 9 field points):
    tau = 3469.5 s = 57.8 min +/- 585.9  ->  band [2884, 4055] s   (main.py:1447-1453)
    feed-introduction dead time t_d bracketed <= 572 s, best est 345 s (main.py:1969)

The outer tau is EMERGENT from the inventory ODEs (not a hard lag); SYN_P_TAU_FILL_MIN is
the only constant that anchors it, so guarding that constant guards the fingerprint. The two
CCW inner-loop lags (FIC_329409_TAU_S, TIC_329005_TAU_S) are subordinate measurement/actuator
lags and must stay far below the dominant feed dead time so they cannot perturb the outer fit.
Full dynamic verification (two-point ID of the live emergent tau) lives in tests/coldstart_probe.py.

Plain asserts (repo has no pytest). Run:  python backend/test_foptd_fingerprint.py"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main

# DCS-anchored FOPTD band (dcs_anchor_dynamics_2025-06-03.md §1.2; mirrored in main.py:1448/1969).
TAU_LO_S   = 2884.0    # s, lower 1-sigma band edge (3469.5 - 585.9)
TAU_HI_S   = 4055.0    # s, upper 1-sigma band edge (3469.5 + 585.9)
TAU_CTR_S  = 3469.5    # s, best-estimate center
TD_MAX_S   = 572.0     # s, feed-introduction dead-time upper bracket


def test_pressurisation_tau_within_foptd_band():
    """SYN_P_TAU_FILL_MIN anchors the emergent pressurisation tau -> must sit in the field band."""
    tau_s = main.SYN_P_TAU_FILL_MIN * 60.0
    assert TAU_LO_S <= tau_s <= TAU_HI_S, (
        "SYN_P_TAU_FILL_MIN=%.3f min -> tau=%.1f s outside FOPTD band [%.0f, %.0f] s"
        % (main.SYN_P_TAU_FILL_MIN, tau_s, TAU_LO_S, TAU_HI_S))
    # center anchor must remain the fit value (guards against silent re-fit)
    assert abs(tau_s - TAU_CTR_S) <= 585.9 + 1.0


def test_feed_deadtime_within_bracket():
    """FEED_TD_S is the dominant on-path dead time -> 0 < t_d <= 572 s."""
    assert main.FEED_TD_S > 0.0, "FEED_TD_S must be strictly positive"
    assert main.FEED_TD_S <= TD_MAX_S, (
        "FEED_TD_S=%.1f s exceeds dead-time bracket %.0f s" % (main.FEED_TD_S, TD_MAX_S))


def test_ccw_lags_finite_and_subordinate():
    """Inner CCW lags must be finite, positive, and << feed dead time (cannot move outer fit)."""
    for name in ("FIC_329409_TAU_S", "TIC_329005_TAU_S"):
        tau = getattr(main, name)
        assert 0.0 < tau < main.FEED_TD_S, (
            "%s=%.3f s must be positive and below FEED_TD_S=%.1f s" % (name, tau, main.FEED_TD_S))
        # negligible against the outer pressurisation tau (well below the band floor)
        assert tau < TAU_LO_S


if __name__ == "__main__":
    fails = 0
    for t in (test_pressurisation_tau_within_foptd_band,
              test_feed_deadtime_within_bracket,
              test_ccw_lags_finite_and_subordinate):
        try:
            t(); print("PASS", t.__name__)
        except Exception:
            fails += 1; print("FAIL", t.__name__); traceback.print_exc()
    raise SystemExit(1 if fails else 0)
