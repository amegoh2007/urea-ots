"""Unit tests for reactor.py Modified Inoue-Kanai conversion model (kinetic coupling layer).
Separate from test_reactor.py (split-fraction HMB suite). Plain-assert, run directly:
    python test_reactor_kinetics.py
"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reactor as R
import main


def approx(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_design_anchor():
    """Factor == 1.0 at the exact design feed; absolute X == X_des (0.543)."""
    f = R.conversion_factor(R.L0_DES, R.W0_DES, R.T0_DES_C)
    assert approx(f, 1.0, 1e-12), "factor at design = %r, want 1.0" % f
    x = R.inoue_kanai_X(R.L0_DES, R.W0_DES, R.T0_DES_C)
    assert approx(x, 0.543, 2e-3), "X_des = %.5f, want 0.543" % x


def test_water_penalty():
    """X drops as H/C (W) rises -- the Stamicarbon water penalty."""
    x0 = R.inoue_kanai_X(R.L0_DES, R.W0_DES, R.T0_DES_C)
    x1 = R.inoue_kanai_X(R.L0_DES, R.W0_DES * 1.10, R.T0_DES_C)
    assert x1 < x0, "X must fall with water: %.5f !< %.5f" % (x1, x0)


def test_nh3_excess():
    """X rises as N/C (L) rises, bounded above by X_inf."""
    x0 = R.inoue_kanai_X(R.L0_DES, R.W0_DES, R.T0_DES_C)
    x1 = R.inoue_kanai_X(R.L0_DES * 1.05, R.W0_DES, R.T0_DES_C)
    assert x1 > x0, "X must rise with NH3: %.5f !> %.5f" % (x1, x0)
    assert R.inoue_kanai_X(50.0, R.W0_DES, R.T0_DES_C) < R.X_INF, "X must stay < X_inf"


def test_couple_design_identity():
    """At the design feed, react_couple reproduces pinned xi and leaves overflow unchanged."""
    feed = {"NH3": 7464.673, "CO2": 2429.147, "H2O": 990.675}
    ov0  = {k: main.REACT_OVERFLOW_DES.get(k, 0.0) for k in main.MW_COMP}
    xi, ov, X, L, W = R.react_couple(feed, ov0, main.REACT_XI_UREA_DES, R.T0_DES_C)
    assert approx(xi, main.REACT_XI_UREA_DES, 1e-6), "xi=%r" % xi
    for k in ov0:
        assert approx(ov[k], ov0[k], 1e-6), "overflow[%s] drifted: %r vs %r" % (k, ov[k], ov0[k])


def test_couple_atom_balance():
    """Off-design (+20% feed water): xi falls; overflow shift conserves atoms & mole-closure."""
    feed = {"NH3": 7464.673, "CO2": 2429.147, "H2O": 990.675 * 1.20}
    ov0  = {k: main.REACT_OVERFLOW_DES.get(k, 0.0) for k in main.MW_COMP}
    xi0  = main.REACT_XI_UREA_DES
    xi, ov, X, L, W = R.react_couple(feed, ov0, xi0, R.T0_DES_C)
    d = xi - xi0
    assert d < 0.0, "water up must drop xi: d=%.4f" % d
    assert approx(ov["Urea"], ov0["Urea"] + d, 1e-9)
    assert approx(ov["CO2"],  ov0["CO2"]  - d, 1e-9)
    assert approx(ov["NH3"],  ov0["NH3"]  - 2.0 * d, 1e-9)
    assert approx(ov["H2O"],  ov0["H2O"]  + d, 1e-9)
    assert approx(sum(ov.values()) + xi, sum(ov0.values()) + xi0, 1e-6), "closure drifted"


def test_degenerate_guard():
    """Zero-CO2 feed (split-fraction unit-test stand-in) -> identity, no divide-by-zero."""
    feed = {k: 0.0 for k in main.MW_COMP}
    ov0  = {k: main.REACT_OVERFLOW_DES.get(k, 0.0) for k in main.MW_COMP}
    xi, ov, X, L, W = R.react_couple(feed, ov0, main.REACT_XI_UREA_DES, R.T0_DES_C)
    assert approx(xi, main.REACT_XI_UREA_DES, 1e-9)
    for k in ov0:
        assert approx(ov[k], ov0[k], 1e-9)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    fails = 0
    for t in tests:
        try:
            t(); print("PASS", t.__name__)
        except Exception:
            fails += 1; print("FAIL", t.__name__); traceback.print_exc()
    raise SystemExit(1 if fails else 0)
