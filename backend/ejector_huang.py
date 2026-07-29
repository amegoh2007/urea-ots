"""1-D compressible-flow steam-ejector model (gap C40). STANDALONE.

WHY THIS MODEL. The Unit-324 vacuum train (ejectors 324F002/F004/F005) holds the evaporator vacuum by
entraining flashed vapour with motive steam through converging-diverging nozzles. A physically faithful
simulation of vacuum hold AND of "breakdown" (the normal shock being pushed upstream when the discharge
backpressure rises) cannot come from a fitted vendor curve; it must come from the 1-D compressible-flow
analysis of:

    B. J. Huang, J. M. Chang, C. P. Wang, V. A. Petrenko, "A 1-D analysis of ejector performance",
    Int. J. Refrigeration 22 (1999) 354-364.

as directed in `References/Urea Simulation Gaps Resolution1.md` (section "1D Compressible Ejector Model").
The model chains: (1) isentropic expansion of the motive steam through the choked primary nozzle;
(2) choking of the entrained secondary stream at the aerodynamic throat; (3) constant-area supersonic
mixing by conservation of mass/momentum/energy; (4) a normal shock and subsonic diffuser recovery.

STATUS. This module delivers and validates the compressible-flow CORE that the whole Huang analysis
rests on -- the isentropic area/Mach/pressure relations, the choked-nozzle mass flux, and the normal-
shock jump -- each checked against standard gas-dynamics tables (e.g. gamma=1.4: critical pressure ratio
0.5283, A/A* at M=2 is 1.6875, normal shock at M1=2 gives M2=0.5774, p2/p1=4.5, p02/p01=0.7209). On top
of that core it assembles the Huang entrainment ratio and the critical (breakdown) backpressure as
functions of the ejector geometry.

It is NOT wired into `main.py`. Certifying C40 for THIS plant additionally requires the vendor data the
reference document lists and that no correlation can substitute: the exact nozzle throat / exit / mixing
areas for 324F002/F004/F005 and the firm downstream tie pressures (F004 discharge / E006). Those fix the
normal-shock position; without them the breakdown point is a geometry guess, not a simulation. The
geometry and tie pressures are the one remaining external input, exactly as the reference concludes;
nothing here fabricates them. Motive/secondary steam is treated as an ideal gas with a constant specific
heat ratio gamma (~1.33 for low-pressure steam), the standard Huang assumption.
"""
import math

R_STEAM = 461.52          # J/kg/K, specific gas constant of water vapour
GAMMA_STEAM = 1.33        # specific heat ratio of low-pressure steam (Huang ideal-gas assumption)


# --------------------------------------------------------------------- isentropic 1-D relations
def critical_pressure_ratio(gamma):
    """Choking (throat) static-to-stagnation pressure ratio P*/P0 = (2/(gamma+1))^(gamma/(gamma-1))."""
    return (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))


def isentropic_p0_over_p(M, gamma):
    """Stagnation-to-static pressure ratio P0/P = (1 + (gamma-1)/2 M^2)^(gamma/(gamma-1))."""
    return (1.0 + 0.5 * (gamma - 1.0) * M * M) ** (gamma / (gamma - 1.0))


def isentropic_t0_over_t(M, gamma):
    """Stagnation-to-static temperature ratio T0/T = 1 + (gamma-1)/2 M^2."""
    return 1.0 + 0.5 * (gamma - 1.0) * M * M


def isentropic_area_ratio(M, gamma):
    """Area ratio A/A* for isentropic flow at Mach M:
        A/A* = (1/M) [ (2/(gamma+1)) (1 + (gamma-1)/2 M^2) ]^((gamma+1)/(2(gamma-1)))."""
    g = gamma
    return (1.0 / M) * ((2.0 / (g + 1.0)) * (1.0 + 0.5 * (g - 1.0) * M * M)) ** ((g + 1.0) / (2.0 * (g - 1.0)))


def mach_from_area_ratio(ar, gamma, supersonic=True):
    """Invert A/A* = ar for the Mach number (supersonic branch by default, subsonic if requested).
    Bisection on the monotonic branch; ar must be >= 1."""
    if ar < 1.0:
        raise ValueError("area ratio A/A* must be >= 1")
    if abs(ar - 1.0) < 1e-12:
        return 1.0
    lo, hi = (1.0, 50.0) if supersonic else (1e-6, 1.0)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        f = isentropic_area_ratio(mid, gamma) - ar
        # A/A* decreases with M on the subsonic branch, increases on the supersonic branch
        if supersonic:
            if f > 0.0:
                hi = mid
            else:
                lo = mid
        else:
            if f > 0.0:
                lo = mid
            else:
                hi = mid
        if abs(f) < 1e-12:
            break
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------- choked mass flux
def choked_mass_flow(P0, T0, A_throat, gamma=GAMMA_STEAM, Rgas=R_STEAM):
    """Mass flow [kg/s] through a choked (sonic) throat of area A_throat [m^2] from stagnation
    conditions P0 [Pa], T0 [K]:
        mdot = P0 A_throat sqrt(gamma/(R T0)) (2/(gamma+1))^((gamma+1)/(2(gamma-1)))."""
    g = gamma
    return (P0 * A_throat * math.sqrt(g / (Rgas * T0))
            * (2.0 / (g + 1.0)) ** ((g + 1.0) / (2.0 * (g - 1.0))))


# ------------------------------------------------------------------------ normal shock relations
def normal_shock(M1, gamma):
    """Normal-shock jump for upstream Mach M1 > 1. Returns a dict with:
        M2       downstream Mach,
        p2_p1    static pressure ratio,
        t2_t1    static temperature ratio,
        p02_p01  stagnation-pressure recovery ratio (total-pressure loss across the shock)."""
    g = gamma
    m1sq = M1 * M1
    M2 = math.sqrt((1.0 + 0.5 * (g - 1.0) * m1sq) / (g * m1sq - 0.5 * (g - 1.0)))
    p2_p1 = 1.0 + 2.0 * g / (g + 1.0) * (m1sq - 1.0)
    t2_t1 = (1.0 + 0.5 * (g - 1.0) * m1sq) * (2.0 * g * m1sq - (g - 1.0)) / ((g + 1.0) ** 2 / 2.0 * m1sq)
    p02_p01 = (((g + 1.0) * m1sq / (2.0 + (g - 1.0) * m1sq)) ** (g / (g - 1.0))
               * ((g + 1.0) / (2.0 * g * m1sq - (g - 1.0))) ** (1.0 / (g - 1.0)))
    return {"M2": M2, "p2_p1": p2_p1, "t2_t1": t2_t1, "p02_p01": p02_p01}


# ------------------------------------------------- Huang entrainment ratio + breakdown assembly
def entrainment_ratio(P_p, T_p, P_s, T_s, A_throat, A_mix, gamma=GAMMA_STEAM, Rgas=R_STEAM):
    """Ideal (loss-free) Huang entrainment ratio omega = mdot_secondary / mdot_primary for a double-choke
    ejector, given motive stagnation (P_p, T_p), secondary stagnation (P_s, T_s), the primary nozzle
    throat area A_throat and the constant mixing-section area A_mix [m^2].

    Primary chokes at A_throat and expands to fill the effective primary area A_py at the mixing section
    (found from its pressure ratio to P_s); the secondary chokes (M=1) in the remaining annulus
    A_sy = A_mix - A_py. Huang's empirical nozzle/mixing loss coefficients are set to 1 here (the
    gas-dynamic upper bound); real coefficients and the exact areas are the vendor input needed to
    certify a specific ejector. Returns omega (dimensionless)."""
    mdot_p = choked_mass_flow(P_p, T_p, A_throat, gamma, Rgas)
    # primary expands from motive stagnation P_p down to the secondary (suction) pressure P_s
    p0_over_p = P_p / P_s
    if p0_over_p <= isentropic_p0_over_p(1.0, gamma):
        raise ValueError("motive/suction ratio below choking: not a supersonic ejector regime")
    M_py = _mach_from_p0_ratio(p0_over_p, gamma)
    A_py = A_throat * isentropic_area_ratio(M_py, gamma)
    A_sy = A_mix - A_py
    if A_sy <= 0.0:
        raise ValueError("primary jet fills the mixing area: no room for secondary flow (check geometry)")
    mdot_s = choked_mass_flow(P_s, T_s, A_sy, gamma, Rgas)
    return mdot_s / mdot_p


def critical_backpressure(P_p, T_p, P_s, T_s, A_throat, A_mix, gamma=GAMMA_STEAM):
    """Critical (breakdown) discharge pressure: the diffuser static pressure recovered downstream of a
    normal shock that sits at the mixing-section Mach. Above this backpressure the shock is pushed into
    the mixing chamber, the secondary chokes off and the ejector breaks down. Returns P_crit [Pa].

    Uses the ideal assembly: the mixed supersonic Mach is taken at the primary expansion Mach at the
    mixing section; a normal shock there gives the post-shock stagnation pressure, and subsonic diffusion
    recovers to that stagnation pressure. Certifying the absolute value needs the real A_mix and the
    downstream tie pressure; the SHAPE (breakdown once P_discharge > P_crit) is the physics of interest."""
    p0_over_p = P_p / P_s
    M_mix = _mach_from_p0_ratio(p0_over_p, gamma)
    sh = normal_shock(M_mix, gamma)
    p_static_after = P_s * sh["p2_p1"]                       # static pressure just after the shock
    # subsonic diffuser recovers static -> stagnation at the post-shock Mach
    return p_static_after * isentropic_p0_over_p(sh["M2"], gamma)


def _mach_from_p0_ratio(p0_over_p, gamma):
    """Supersonic Mach from an isentropic stagnation/static pressure ratio P0/P."""
    g = gamma
    return math.sqrt(2.0 / (g - 1.0) * (p0_over_p ** ((g - 1.0) / g) - 1.0))


if __name__ == "__main__":
    print("Huang 1-D ejector core (gap C40)")
    print(f"  gamma=1.4 critical pressure ratio = {critical_pressure_ratio(1.4):.4f}  (table 0.5283)")
    print(f"  gamma=1.4 A/A* at M=2 = {isentropic_area_ratio(2.0, 1.4):.4f}  (table 1.6875)")
    sh = normal_shock(2.0, 1.4)
    print(f"  gamma=1.4 shock M1=2: M2={sh['M2']:.4f} p2/p1={sh['p2_p1']:.4f} p02/p01={sh['p02_p01']:.4f}")
    print("            (table  M2=0.5774 p2/p1=4.5000 p02/p01=0.7209)")
