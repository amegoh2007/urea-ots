"""Validation gate for the Crowe projection-matrix reconciliation engine (reconcile_crowe.py, gap C35).

Every case here is a mass-balance network whose reconciled answer can be worked out by hand, so passing
proves the engine is correct -- not merely that it runs. Nothing is fabricated; the sensor covariance is
supplied explicitly as an input (the very datum the real Unit-324 certification still needs approved).

Run from backend/:  python -m pytest test_reconcile_crowe.py   (or: python test_reconcile_crowe.py)
"""
import numpy as np

import reconcile_crowe as RC


# ------------------------------------------------------------- all-measured WLS reconciliation
def test_wls_equal_variance_splits_imbalance_evenly():
    """Single node F1+F2=F3, y=(10.1,5.0,14.8) imbalance 0.3, equal variances -> correction (0.1,0.1,-0.1)."""
    x = RC.wls_reconcile([10.1, 5.0, 14.8], np.eye(3), [[1.0, 1.0, -1.0]])
    assert np.allclose(x, [10.0, 4.9, 14.9], atol=1e-9)
    assert abs(float(x @ [1, 1, -1])) < 1e-10                      # balance closes exactly


def test_wls_variance_weighting_moves_noisy_sensor_most():
    """With variances (4,1,1) the noisiest stream F1 absorbs the largest share of the correction."""
    S = np.diag([4.0, 1.0, 1.0])
    x = RC.wls_reconcile([10.1, 5.0, 14.8], S, [[1.0, 1.0, -1.0]])
    assert np.allclose(x, [9.9, 4.95, 14.85], atol=1e-9)
    assert abs(float(x @ [1, 1, -1])) < 1e-10


def test_wls_reconciled_satisfies_constraints_multinode():
    """A two-node all-measured network: the reconciled vector satisfies both balances to machine zero and
    the weighted objective is not increased by any feasible perturbation (checked via the normal equations)."""
    A = np.array([[1.0, -1.0, -1.0, 0.0, 0.0],       # F1 = F2 + F3
                  [0.0, 0.0, 1.0, -1.0, -1.0]])       # F3 = F4 + F5
    y = np.array([10.0, 4.1, 5.7, 3.9, 2.1])
    S = np.diag([1.0, 2.0, 1.0, 1.0, 3.0])
    x = RC.wls_reconcile(y, S, A)
    assert np.allclose(A @ x, 0.0, atol=1e-9)
    # Lagrange optimality: Sigma^{-1}(x-y) must lie in the row space of A (i.e. = A^T mu for some mu)
    resid = np.linalg.solve(S, x - y)
    mu, *_ = np.linalg.lstsq(A.T, resid, rcond=None)
    assert np.allclose(A.T @ mu, resid, atol=1e-9)


# ------------------------------------------------------- Crowe projection with unmeasured streams
def test_projection_kills_unmeasured_submatrix():
    """projection_matrix(Au) returns rows p with p Au = 0, and its row count equals the number of
    redundant balances (m - rank Au)."""
    Au = np.array([[-1.0], [1.0]])                    # one unmeasured stream across two balances
    P = RC.projection_matrix(Au)
    assert P.shape[0] == 1                             # 2 balances - rank 1 = 1 redundant equation
    assert np.allclose(P @ Au, 0.0, atol=1e-12)


def test_crowe_no_redundancy_passes_measured_through():
    """Mixer F1+F2=F3 with F2 unmeasured: the single balance is fully absorbed by F2, so the measured
    F1,F3 are not redundant and must pass through unchanged, with F2 back-calculated as F3-F1."""
    Ax = np.array([[1.0, -1.0]])                       # measured (F1, F3)
    Au = np.array([[1.0]])                             # unmeasured F2
    xm, xu = RC.crowe_reconcile([10.2, 14.8], np.eye(2), Ax, Au)
    assert np.allclose(xm, [10.2, 14.8], atol=1e-12)   # unchanged
    assert abs(xu[0] - (14.8 - 10.2)) < 1e-9           # F2 = F3 - F1


def test_crowe_projection_reconciles_and_backcalcs_consistently():
    """Two nodes with the shared stream F3 unmeasured:
        (1) F1 - F2 - F3 = 0     (2) F3 - F4 - F5 = 0
    Projection eliminates F3 -> overall balance F1-F2-F4-F5=0. y=(10.2,4.0,3.9,2.0), imbalance 0.3, equal
    variance -> each measured stream corrected by +/-0.075; F3 back-calculated identically from BOTH nodes."""
    Ax = np.array([[1.0, -1.0, 0.0, 0.0],              # measured (F1, F2, F4, F5)
                   [0.0, 0.0, -1.0, -1.0]])
    Au = np.array([[-1.0], [1.0]])                     # unmeasured F3
    y = [10.2, 4.0, 3.9, 2.0]
    xm, xu = RC.crowe_reconcile(y, np.eye(4), Ax, Au)
    assert np.allclose(xm, [10.125, 4.075, 3.975, 2.075], atol=1e-9)
    # unmeasured F3 consistent from node 1 (F1-F2) and node 2 (F4+F5)
    f3_node1 = xm[0] - xm[1]
    f3_node2 = xm[2] + xm[3]
    assert abs(f3_node1 - f3_node2) < 1e-9
    assert abs(xu[0] - f3_node1) < 1e-9
    # both original balances now close with the reconciled + back-calculated values
    assert abs(xm[0] - xm[1] - xu[0]) < 1e-9
    assert abs(xu[0] - xm[2] - xm[3]) < 1e-9


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fails = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            fails += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - fails}/{len(fns)} passed")
    raise SystemExit(1 if fails else 0)
