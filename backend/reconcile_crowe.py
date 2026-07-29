"""Steady-state data reconciliation by Crowe's projection-matrix method (gap C35). STANDALONE.

WHY THIS METHOD. Raw plant measurements never satisfy the conservation laws exactly (sensor noise,
drift). Data reconciliation adjusts the measured vector by the smallest weighted amount that makes it
satisfy the linear/bilinear mass and energy balances. The standard, peer-reviewed approach for networks
that also contain UNMEASURED streams is the matrix-projection method of:

    C. M. Crowe, Y. A. Garcia Campos, A. Hrymak, "Reconciliation of process flow rates by matrix
    projection. Part I: Linear case", AIChE J. 29 (1983) 881-888.

The unmeasured variables are eliminated by pre-multiplying the constraint set with a projection matrix
P whose rows span the left null space of the unmeasured submatrix (P Au = 0). What remains is a reduced,
fully-measured weighted-least-squares problem with a closed-form solution; the unmeasured variables are
then back-calculated. This is exactly the formulation described in `References/Urea Simulation Gaps
Resolution1.md` (section "Rigorous Data Reconciliation: Crowe's Projection Matrix").

STATUS. This module delivers and validates the reconciliation ENGINE (WLS closed form + Crowe
projection + unmeasured back-calculation), tested against hand-solvable mass-balance networks. It is NOT
wired into `main.py`. Certifying the C35 Unit-324 residuals (324F004 -1.917, 324E001 -170.105,
324E003 -126.793 kg/h) additionally requires an APPROVED measurement-error covariance matrix Sigma
(sensor precisions). Without an approved Sigma the objective function weights are arbitrary and the
reconciled vector, while numerically valid, is not operationally meaningful. Sigma is the one remaining
external input, exactly as the reference document concludes; nothing here fabricates it.
"""
import numpy as np

_RANK_TOL = 1e-10


def wls_reconcile(y, Sigma, A, c=None):
    """Weighted-least-squares reconciliation with every variable measured.

        minimise (x - y)^T Sigma^{-1} (x - y)   subject to   A x = c.

    Closed-form Lagrangian solution (Crowe 1983 eq for the measured case):
        x_hat = y - Sigma A^T (A Sigma A^T)^{-1} (A y - c).
    `y` measurement vector (n,), `Sigma` covariance (n,n), `A` constraint incidence (m,n), `c` the
    balance right-hand side (m,) defaulting to 0. Returns the reconciled vector x_hat (n,)."""
    y = np.asarray(y, float)
    A = np.atleast_2d(np.asarray(A, float))
    S = np.asarray(Sigma, float)
    c = np.zeros(A.shape[0]) if c is None else np.asarray(c, float)
    r = A @ y - c
    lam = np.linalg.solve(A @ S @ A.T, r)
    return y - S @ A.T @ lam


def projection_matrix(Au):
    """Crowe projection P with P Au = 0: rows are an orthonormal basis of the LEFT null space of the
    unmeasured submatrix Au (m, u), obtained from the SVD. If Au has full row rank (every balance
    touches an independent unmeasured variable) there is no redundancy and P has zero rows."""
    Au = np.atleast_2d(np.asarray(Au, float))
    U, s, _ = np.linalg.svd(Au)
    rank = int((s > _RANK_TOL).sum())
    return U[:, rank:].T                       # (m-rank, m); each row p satisfies p Au = 0


def crowe_reconcile(y_m, Sigma_m, Ax, Au, c=None):
    """Full Crowe (1983) reconciliation for a network with unmeasured variables.

    Balances:      Ax x_m + Au x_u = c        (Ax: m x nm measured incidence, Au: m x nu unmeasured)
    Step 1 -- project out the unmeasured variables with P (P Au = 0):
                   (P Ax) x_m = P c
    Step 2 -- reconcile the measured variables by WLS on the reduced, redundant constraint set.
    Step 3 -- back-calculate the unmeasured variables by least squares:  Au x_u = c - Ax x_hat_m.

    Returns (x_hat_m, x_hat_u). If P has zero rows the measured data are not redundant and pass through
    unchanged (the balances are absorbed entirely by the unmeasured variables)."""
    y_m = np.asarray(y_m, float)
    Ax = np.atleast_2d(np.asarray(Ax, float))
    Au = np.atleast_2d(np.asarray(Au, float))
    Sm = np.asarray(Sigma_m, float)
    c = np.zeros(Ax.shape[0]) if c is None else np.asarray(c, float)

    P = projection_matrix(Au)
    if P.shape[0] == 0:                        # no redundancy: measured data unchanged
        x_hat_m = y_m.copy()
    else:
        Ar = P @ Ax                            # reduced constraints on the measured variables only
        cr = P @ c
        x_hat_m = wls_reconcile(y_m, Sm, Ar, cr)

    rhs = c - Ax @ x_hat_m                      # back-calculate unmeasured by least squares
    x_hat_u, *_ = np.linalg.lstsq(Au, rhs, rcond=None)
    return x_hat_m, x_hat_u


def balance_residual(x, A, c=None):
    """Constraint residual A x - c (should be ~0 for a reconciled vector). Diagnostic helper."""
    A = np.atleast_2d(np.asarray(A, float))
    c = np.zeros(A.shape[0]) if c is None else np.asarray(c, float)
    return A @ np.asarray(x, float) - c


if __name__ == "__main__":
    # single mixing node F1 + F2 = F3, equal variances: the 0.3 imbalance splits evenly.
    xh = wls_reconcile([10.1, 5.0, 14.8], np.eye(3), [[1.0, 1.0, -1.0]])
    print("all-measured reconciled:", np.round(xh, 4), " balance:", round(float(xh @ [1, 1, -1]), 12))
