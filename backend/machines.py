# -*- coding: utf-8 -*-
"""Rotating-machine models (Phase 4, report D-5).

Centrifugal compressor performance on a rigorous polytropic map, with surge and stonewall limits
and the fan-law speed scaling, plus the pressure-node solve that decides how the discharge splits
between competing destinations.

What this replaces at 320K002
-----------------------------
The CO2 machine used to have no map at all.  Its discharge pressure was an algebraic assertion,

    P_line = min(P_syn + dP_des, P_ceiling)

i.e. "the compressor always delivers exactly the design feed differential, until it cannot".  That
is a statement about the DESIRED process outcome, not about a machine: it has no flow argument, so
the compressor could not be off its curve, could not surge, could not stonewall, and had no speed.
The split between the HP loop and the vent was then a normalised conductance ratio,

    f_to_HP = g_HP / (g_HP + g_vent),  g = sqrt(dP)

which forces the two branch flows to sum to the raw feed by construction.  A real line does not
work that way: the branches meet at a NODE, the node has one pressure, and that pressure is
whatever makes the machine's delivery equal the sum of what the branches can pass.  The ratio form
cannot represent a vent that is wide open while the loop is also drawing hard, and it cannot let
the node pressure fall below the loop pressure and shut the check valve on its own.

The model here is the ordinary one: a polytropic head/flow characteristic in fan-law-reduced
coordinates, and a node pressure solved so the mass balance closes.
"""

import math

R_GAS_J = 8314.462618          # J/(kmol.K)


# ==================================================================================================
#  Polytropic thermodynamics
# ==================================================================================================
def polytropic_exponent(k: float, eta_p: float) -> float:
    """Polytropic exponent n from the ratio of specific heats and the polytropic efficiency:

        (n - 1)/n = (k - 1)/(k . eta_p)
    """
    ratio = (k - 1.0) / (k * max(eta_p, 1.0e-6))
    return 1.0 / max(1.0 - ratio, 1.0e-9)


def polytropic_head_kjkg(p1_bara: float, p2_bara: float, t1_k: float, mw: float,
                         n_poly: float, z1: float = 1.0) -> float:
    """Polytropic head, kJ/kg:

        H_poly = (Z1 . R . T1 / M) . (n/(n-1)) . [ (P2/P1)^((n-1)/n) - 1 ]
    """
    if p1_bara <= 0.0 or p2_bara <= 0.0 or t1_k <= 0.0 or mw <= 0.0:
        return 0.0
    e = (n_poly - 1.0) / n_poly
    return (z1 * R_GAS_J * t1_k / mw) * (1.0 / e) * ((p2_bara / p1_bara) ** e - 1.0) / 1000.0


def discharge_t_k(t1_k: float, p1_bara: float, p2_bara: float, n_poly: float,
                  n_stages: int = 1) -> float:
    """Polytropic discharge temperature out of the LAST section, T2 = T1 (P2/P1)^((n-1)/(n.Ns)).

    With `n_stages` > 1 the machine is taken as equal-pressure-ratio sections intercooled back to
    the suction temperature, which is what any 90:1 CO2 machine actually is.  A single uncooled
    section from 1.6 to 144 bar would discharge above 870 C -- the arithmetic is right and the
    machine is wrong."""
    if p1_bara <= 0.0:
        return t1_k
    return t1_k * (p2_bara / p1_bara) ** ((n_poly - 1.0) / (n_poly * max(n_stages, 1)))


def polytropic_head_staged_kjkg(p1_bara: float, p2_bara: float, t1_k: float, mw: float,
                                n_poly: float, n_stages: int = 1, z1: float = 1.0) -> float:
    """Total polytropic head of `n_stages` equal-ratio sections intercooled back to T1.

        H = Ns . (Z1 R T1 / M) . (n/(n-1)) . [ (P2/P1)^((n-1)/(n.Ns)) - 1 ]

    Reduces to `polytropic_head_kjkg` at Ns = 1.  Intercooling is what makes the head sum linear in
    the stage count instead of exponential in the overall ratio, and it is also what fixes the
    machine's sensitivity to discharge pressure -- an uncooled single section is far stiffer
    against back pressure than the real train."""
    ns = max(int(n_stages), 1)
    if p1_bara <= 0.0 or p2_bara <= 0.0 or t1_k <= 0.0 or mw <= 0.0:
        return 0.0
    e = (n_poly - 1.0) / (n_poly * ns)
    return ns * (z1 * R_GAS_J * t1_k / mw) * ((n_poly / (n_poly - 1.0))
                                              * ((p2_bara / p1_bara) ** e - 1.0)) / 1000.0


# ==================================================================================================
#  Normalised centrifugal characteristic
# ==================================================================================================
#  Reduced coordinates (fan / affinity laws at fixed impeller diameter):
#
#      q   = (Q_in / Q_in,des) / (N / N_des)        reduced inlet volumetric flow
#      psi = (H_poly / H_des)  / (N / N_des)^2      reduced polytropic head
#
#  In these coordinates one curve describes every speed, and the design point is (q, psi) = (1, 1)
#  by construction.  The curve itself is the standard head-rise-to-surge parabola
#
#      psi(q) = 1 + a1 (q - 1) + a2 (q - 1)^2
#
#  fitted to two facts a machine datasheet always states even when the full curve is not available:
#  the head rise to surge, and the surge flow.  a1 < 0 gives the negatively-sloped (stable) branch
#  at and above design; the peak of the parabola IS the surge line.
class CentrifugalMap:
    """Normalised polytropic head/flow characteristic with surge and stonewall limits."""

    def __init__(self, q_surge: float = 0.68, head_rise_to_surge: float = 0.12,
                 q_stonewall: float = 1.20):
        if not 0.0 < q_surge < 1.0:
            raise ValueError("surge must sit below the design flow")
        if q_stonewall <= 1.0:
            raise ValueError("stonewall must sit above the design flow")
        self.q_surge = q_surge
        self.q_stonewall = q_stonewall
        self.head_rise = head_rise_to_surge
        # peak at q_surge  ->  a1 = -2 a2 (q_surge - 1)
        # psi(q_surge) = 1 + head_rise
        u = q_surge - 1.0
        self.a2 = head_rise_to_surge / (-u * u)
        self.a1 = -2.0 * self.a2 * u

    def psi(self, q: float) -> float:
        """Reduced head at reduced flow.  Flat at the surge peak below the surge line (the machine
        cannot sit there; the caller flags it), zero at and beyond stonewall."""
        if q >= self.q_stonewall:
            return 0.0
        qq = max(q, self.q_surge)
        u = qq - 1.0
        return 1.0 + self.a1 * u + self.a2 * u * u

    def q_from_psi(self, psi_target: float) -> float:
        """Invert the characteristic on its STABLE (negatively-sloped) branch: the larger root of
        psi(q) = psi_target, clipped into [q_surge, q_stonewall]."""
        if psi_target <= 0.0:
            return self.q_stonewall
        # a2 u^2 + a1 u + (1 - psi) = 0
        c = 1.0 - psi_target
        disc = self.a1 * self.a1 - 4.0 * self.a2 * c
        if disc < 0.0:                       # demanded head above the surge peak: machine surges
            return self.q_surge
        root = math.sqrt(disc)
        # a2 < 0, so the stable (larger-q) root is the one with the minus sign on the numerator
        u1 = (-self.a1 + root) / (2.0 * self.a2)
        u2 = (-self.a1 - root) / (2.0 * self.a2)
        u = max(u1, u2)
        return min(max(1.0 + u, self.q_surge), self.q_stonewall)


class CentrifugalCompressor:
    """A centrifugal machine anchored on one design point.

    q_des_m3h / h_des_kjkg / p1/t1/mw fix the design duty; the map supplies the shape.  Everything
    the process sees -- delivered mass flow, discharge temperature, surge and stonewall flags --
    comes out of the same two equations (polytropic head, reduced characteristic), so the machine
    can be off its curve and the flowsheet finds out about it.
    """

    def __init__(self, q_in_des_m3h: float, h_des_kjkg: float, rho_in_des_kgm3: float,
                 n_poly: float, map_: CentrifugalMap = None, n_stages: int = 1):
        self.q_in_des = q_in_des_m3h
        self.h_des = h_des_kjkg
        self.rho_in_des = rho_in_des_kgm3
        self.n_poly = n_poly
        self.n_stages = max(int(n_stages), 1)
        self.map = map_ or CentrifugalMap()

    def delivery_kgh(self, p1_bara: float, p2_bara: float, t1_k: float, mw: float,
                     speed_frac: float, z1: float = 1.0) -> dict:
        """Mass flow the machine delivers into a discharge pressure p2 at reduced speed.

        Returns the flow plus the map coordinates and the two limit flags, because the flags are
        the whole reason for having a map: a compressor that has been pushed to its surge line is a
        different plant event from one that is merely running off design.
        """
        if speed_frac <= 1.0e-6 or p1_bara <= 0.0:
            return {"kgh": 0.0, "q": 0.0, "psi": 0.0, "head_kjkg": 0.0,
                    "surge": False, "stonewall": False, "t2_k": t1_k}
        h_req = polytropic_head_staged_kjkg(p1_bara, p2_bara, t1_k, mw, self.n_poly,
                                            self.n_stages, z1)
        psi = (h_req / self.h_des) / (speed_frac * speed_frac)
        q = self.map.q_from_psi(psi)
        surge = psi > self.map.psi(self.map.q_surge) or q <= self.map.q_surge
        stonewall = q >= self.map.q_stonewall
        q_in_m3h = q * speed_frac * self.q_in_des
        rho_in = rho_in_des_from_state(p1_bara, t1_k, mw, z1)
        return {"kgh": max(q_in_m3h * rho_in, 0.0), "q": q, "psi": psi, "head_kjkg": h_req,
                "surge": bool(surge), "stonewall": bool(stonewall),
                "t2_k": discharge_t_k(t1_k, p1_bara, p2_bara, self.n_poly, self.n_stages)}


def rho_in_des_from_state(p_bara: float, t_k: float, mw: float, z: float = 1.0) -> float:
    """Ideal-gas (Z-corrected) inlet density, kg/m3."""
    return p_bara * 1.0e5 * mw / max(z * R_GAS_J * t_k, 1.0e-9)


# ==================================================================================================
#  Pressure-node network solve
# ==================================================================================================
def solve_node_pressure(supply, branches, p_lo: float, p_hi: float,
                        p_seed: float = None, tol: float = 1.0e-10, max_iter: int = 80) -> float:
    """Find the node pressure at which a supply balances the sum of its branch draws.

        residual(P) = supply(P) - sum_i branch_i(P) = 0

    `supply` is monotonically DECREASING in P (a compressor delivers less against more back
    pressure) and each branch is monotonically INCREASING, so the residual is strictly decreasing
    and a bracketed bisection is unconditionally convergent -- no Jacobian, no initial-guess
    sensitivity, and no chance of landing on the wrong root.

    `p_seed` is the design node pressure.  If the residual there is EXACTLY zero the seed is
    returned unchanged, which is what keeps a design-anchored flowsheet bit-exact: bisection would
    otherwise return a value a few ulp away and unpin every constant downstream of it.
    """
    def residual(p):
        return supply(p) - sum(b(p) for b in branches)

    if p_seed is not None:
        r_seed = residual(p_seed)
        if r_seed == 0.0:
            return p_seed

    lo, hi = p_lo, p_hi
    r_lo, r_hi = residual(lo), residual(hi)
    if r_lo <= 0.0:                    # supply cannot even hold the low end
        return lo
    if r_hi >= 0.0:                    # supply outruns every branch at the high end
        return hi
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        r = residual(mid)
        if r == 0.0 or (hi - lo) < tol:
            return mid
        if r > 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)
