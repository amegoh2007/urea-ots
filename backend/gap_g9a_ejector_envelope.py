"""G9a -- first-principles 324 steam-jet ejector core (choked primary + double-choke secondary).

WHAT THIS ADVANCES. handoff.md G9 keeps the 324 vacuum ejectors (324F002/F004/F005) on a reduced
"constant entrainment ratio + suction-pressure roll-off" surrogate and calls the pull curve
"data-gated -- a polynomial cannot be identified from one point". The closure-methodology doc (its
ejector section) proposes recovering the physics without a vendor curve via: (1) the primary nozzle
throat area from CHOKED motive flow -- first principles, not a fit; (2) the universal critical-mode
structure; (3) a bounded mixing-area ratio; (4) a molecular-weight entrainment response.

This module implements (1), (2) and (4) rigorously and REPORTS a correction to (3): the doc's
A3/At in [6.44, 10.64] is measured on small REFRIGERATION ejectors (Huang 1999, R141b, suction near
40-80 kPa). The 324 units are DEEP-VACUUM STEAM ejectors (suction 0.1-0.3 bar). Solving the ideal
double-choke model for the area ratio that reproduces each unit's strict-PFD design entrainment ratio
gives A3/At = 4.4 (324F002), 20.6 (324F004), 4.7 (324F005) -- a span of ~4.4-20.6 that STRADDLES the
refrigeration band: 324F004 (deepest vacuum) sits ABOVE it, while 324F002/F005 sit BELOW it. All three
land OUTSIDE [6.44, 10.64] on one side or the other, so that band does not bound these units and
blindly applying it would misstate the envelope. The honest result is therefore a DESIGN-ANCHORED
off-design pull curve whose single free geometric parameter (A3/At) is pinned by the one strict-PFD
duty point, with its residual uncertainty explicitly gated on a SECOND duty point -- the same gate
handoff.md already states, now quantified rather than asserted.

STRICT-SOURCE DUTY POINTS (PFD_21 / PFD_26; CLAUDE.md 2 -- PFD strictly overrides the Koerting
datasheet, which conflicts on BOTH ports: it lists 324F004 motive 927=600 / suction 712=634 kg/h
(omega ~ 1.06) vs the PFD's motive 1220 / suction 584 (omega ~ 0.48), and 929=505 vs 180 kg/h. These
are materially different operating points; the PFD is used because it is mass-consistent -- motive +
suction = discharge closes EXACTLY for all three units (see asserts) -- and could not be independently
reconciled with the datasheet from the materials to hand. The suction MW (21.59) matches the
datasheet's 21.6 kg/kmol, so composition provenance is common even where the flows disagree.

    324F002 : motive 924 = 390 kg/h @ 4.1 bar/146 C ; suction 706 = 72 kg/h @ 0.3 bar ; disch 708 = 462 @ 1.0
    324F004 : motive 927 = 1220 kg/h @ 4.1 bar/146 C; suction 712 = 584 kg/h @ 0.1 bar ; disch 714 = 1804 @ 0.3
    324F005 : motive 929 = 180 kg/h @ 4.1 bar/146 C ; suction 715 = 41 kg/h @ 0.3 bar  ; disch 717 = 221 @ 1.0

PHYSICS (all standard compressible-flow, each relation citable):
  * choked mass flux  G* = P0 sqrt(gamma/(R T0)) (2/(gamma+1))^((gamma+1)/(2(gamma-1)))   (isentropic throat)
  * primary expands isentropically to the mixing pressure ~ suction pressure; its Mach and expanded
    area from the area-Mach relation A/A* = (1/M)[(2/(gamma+1))(1+(gamma-1)/2 M^2)]^((gamma+1)/(2(gamma-1)))
  * critical (double-choke) entrainment (Munday & Bagster hypothetical throat; Huang 1999
    constant-pressure mixing, unit efficiencies):  omega = (A3/At - Apy/At) * (Gs*/Gp*)
  * molecular-weight response is INTRINSIC: Gs* ~ P0s sqrt(gamma_s M_s/(Ru T0s)), so a heavier suction
    gas raises the mass entrainment -- the HEI molecular-weight correlation, derived not fitted.

This is a standalone validation/analysis core (same pattern as props_nh3co2h2o.py and
gap_g2_vacuum_vle_refit.py): it is NOT wired into main.py, so the anchored HMB is untouched; wiring
the off-design pull curve into the 324 ejector suction ODE is the documented follow-on.

Run from `backend`:  python gap_g9a_ejector_envelope.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass

RU = 8.314462618          # J/mol/K universal gas constant
BAR = 1.0e5               # Pa per bar


@dataclass(frozen=True)
class GasState:
    """Stagnation state of a stream at an ejector port."""
    P0_bar: float          # stagnation pressure [bar a]
    T0_C: float            # stagnation temperature [C]
    gamma: float           # ratio of specific heats
    M_g_mol: float         # molar mass [g/mol]
    mdot_kgh: float        # mass flow [kg/h]

    @property
    def R_specific(self) -> float:
        return RU / (self.M_g_mol / 1000.0)      # J/kg/K

    @property
    def T0_K(self) -> float:
        return self.T0_C + 273.15


def choked_mass_flux(P0_bar: float, T0_K: float, gamma: float, M_g_mol: float) -> float:
    """Isentropic choked (sonic-throat) mass flux G* [kg/s/m^2]."""
    R = RU / (M_g_mol / 1000.0)
    return (P0_bar * BAR) * math.sqrt(gamma / (R * T0_K)) * \
        (2.0 / (gamma + 1.0)) ** ((gamma + 1.0) / (2.0 * (gamma - 1.0)))


def throat_area_m2(g: GasState) -> float:
    """Primary-nozzle throat area from the CHOKED motive flow -- first principles, not a fit."""
    G = choked_mass_flux(g.P0_bar, g.T0_K, g.gamma, g.M_g_mol)
    return (g.mdot_kgh / 3600.0) / G


def throat_diameter_mm(g: GasState) -> float:
    return math.sqrt(4.0 * throat_area_m2(g) / math.pi) * 1000.0


def mach_from_pressure_ratio(P0_over_P: float, gamma: float) -> float:
    """Isentropic Mach from stagnation/static pressure ratio."""
    return math.sqrt((P0_over_P ** ((gamma - 1.0) / gamma) - 1.0) * 2.0 / (gamma - 1.0))


def area_ratio_from_mach(M: float, gamma: float) -> float:
    """Isentropic area ratio A/A* for supersonic Mach M."""
    return (1.0 / M) * ((2.0 / (gamma + 1.0)) * (1.0 + (gamma - 1.0) / 2.0 * M * M)) \
        ** ((gamma + 1.0) / (2.0 * (gamma - 1.0)))


def primary_expanded_area_ratio(motive: GasState, P_mix_bar: float) -> float:
    """A_py/A_pt: the primary jet's area at the mixing plane, expanded to the mixing pressure."""
    M_py = mach_from_pressure_ratio(motive.P0_bar / P_mix_bar, motive.gamma)
    return area_ratio_from_mach(M_py, motive.gamma)


def entrainment_ratio(a3_over_at: float, P_suction_bar: float,
                      motive: GasState, suction: GasState) -> float:
    """Critical-mode (double-choke) mass entrainment ratio omega = m_s/m_p.

    Ideal Munday-Bagster / Huang constant-pressure-mixing form with unit efficiencies. The secondary
    chokes at the hypothetical throat (stagnation ~ suction pressure); the primary occupies A_py of
    the mixing area A3, leaving (A3 - A_py) for the secondary.
    """
    Gp = choked_mass_flux(motive.P0_bar, motive.T0_K, motive.gamma, motive.M_g_mol)
    Gs = choked_mass_flux(P_suction_bar, suction.T0_K, suction.gamma, suction.M_g_mol)
    apy_over_at = primary_expanded_area_ratio(motive, P_suction_bar)
    return (a3_over_at - apy_over_at) * (Gs / Gp)


def fit_area_ratio(motive: GasState, suction: GasState, omega_design: float) -> float:
    """Solve for the mixing-area ratio A3/At that reproduces the design entrainment ratio."""
    Gp = choked_mass_flux(motive.P0_bar, motive.T0_K, motive.gamma, motive.M_g_mol)
    Gs = choked_mass_flux(suction.P0_bar, suction.T0_K, suction.gamma, suction.M_g_mol)
    apy_over_at = primary_expanded_area_ratio(motive, suction.P0_bar)
    return apy_over_at + omega_design * (Gp / Gs)


def pull_curve(motive: GasState, suction: GasState, a3_over_at: float,
               p_lo_bar: float, p_hi_bar: float, n: int = 9) -> list[tuple[float, float]]:
    """Off-design pull curve: (suction pressure [bar a], entrainment ratio omega) at fixed geometry.

    omega rises with suction pressure (denser secondary), the physically correct roll-off the current
    constant-omega surrogate cannot represent.
    """
    out = []
    for i in range(n):
        p = p_lo_bar + (p_hi_bar - p_lo_bar) * i / (n - 1)
        out.append((p, entrainment_ratio(a3_over_at, p, motive, suction)))
    return out


def mw_response(motive: GasState, suction: GasState, a3_over_at: float,
                m_shift_g_mol: float) -> float:
    """Relative change in entrainment when the suction-gas molar mass shifts (HEI MW correlation).

    Returns omega(M+dM)/omega(M) - 1 at the design suction pressure. Positive: a heavier suction gas
    entrains more mass -- exactly the composition response the constant-omega model omits.
    """
    base = entrainment_ratio(a3_over_at, suction.P0_bar, motive, suction)
    shifted = GasState(suction.P0_bar, suction.T0_C, suction.gamma,
                       suction.M_g_mol + m_shift_g_mol, suction.mdot_kgh)
    new = entrainment_ratio(a3_over_at, suction.P0_bar, motive, shifted)
    return new / base - 1.0


# --- strict-PFD duty points (motive steam gamma=1.30; suction-gas gamma/M from the PFD rows) -------
GAMMA_STEAM = 1.30
MW_STEAM = 18.0152

EJECTORS = {
    # name: (motive, suction, discharge_pressure_bar, disch_mass_kgh)
    "324F002": (
        GasState(4.1, 146.0, GAMMA_STEAM, MW_STEAM, 390.0),      # motive 924
        GasState(0.3, 45.0, 1.33, 24.13, 72.0),                  # suction 706 (MW 24.13 PFD)
        1.0, 462.0,
    ),
    "324F004": (
        GasState(4.1, 146.0, GAMMA_STEAM, MW_STEAM, 1220.0),     # motive 927
        GasState(0.1, 40.0, 1.33, 21.59, 584.0),                 # suction 712 (MW 21.59 PFD)
        0.3, 1804.0,
    ),
    "324F005": (
        GasState(4.1, 146.0, GAMMA_STEAM, MW_STEAM, 180.0),      # motive 929
        GasState(0.3, 41.0, 1.33, 27.79, 41.0),                  # suction 715 (MW 27.79 PFD)
        1.0, 221.0,
    ),
}


def analyse(name: str) -> dict:
    motive, suction, p_disch, m_disch = EJECTORS[name]
    omega_des = suction.mdot_kgh / motive.mdot_kgh
    a3_over_at = fit_area_ratio(motive, suction, omega_des)
    return {
        "name": name,
        "throat_mm": throat_diameter_mm(motive),
        "throat_area_mm2": throat_area_m2(motive) * 1.0e6,
        "omega_design": omega_des,
        "compression_ratio": p_disch / suction.P0_bar,
        "a3_over_at_fit": a3_over_at,
        "mach_primary_exit": mach_from_pressure_ratio(motive.P0_bar / suction.P0_bar, motive.gamma),
        "mass_closes": abs(motive.mdot_kgh + suction.mdot_kgh - m_disch) < 1.0,
        "pull_curve": pull_curve(motive, suction, a3_over_at,
                                 suction.P0_bar * 0.6, suction.P0_bar * 1.6),
        "mw_plus4_response": mw_response(motive, suction, a3_over_at, 4.0),
    }


if __name__ == "__main__":
    print("=" * 84)
    print("  G9a  324 STEAM-JET EJECTOR CORE  (choked primary + double-choke secondary, strict PFD)")
    print("=" * 84)
    HUANG_LO, HUANG_HI = 6.44, 10.64
    for name in EJECTORS:
        r = analyse(name)
        assert r["mass_closes"], f"{name} mass balance must close on the strict PFD"
        # fitted A3/At must reproduce design omega exactly
        motive, suction, _, _ = EJECTORS[name]
        omega_check = entrainment_ratio(r["a3_over_at_fit"], suction.P0_bar, motive, suction)
        assert abs(omega_check - r["omega_design"]) < 1e-9, (name, omega_check, r["omega_design"])
        # pull curve must be monotone increasing in suction pressure
        ys = [w for _, w in r["pull_curve"]]
        assert all(ys[i + 1] > ys[i] for i in range(len(ys) - 1)), f"{name} pull curve not monotone"
        # heavier suction gas must entrain MORE mass
        assert r["mw_plus4_response"] > 0.0, name
        outside = "OUTSIDE" if not (HUANG_LO <= r["a3_over_at_fit"] <= HUANG_HI) else "within"
        print(f"\n  {name}")
        print(f"    primary throat (choked)  : d = {r['throat_mm']:.1f} mm  (A_t = {r['throat_area_mm2']:.0f} mm^2)")
        print(f"    primary exit Mach        : {r['mach_primary_exit']:.2f}   (datasheet 'Mach 3-4')")
        print(f"    design omega = m_s/m_p   : {r['omega_design']:.4f}")
        print(f"    compression P_d/P_s      : {r['compression_ratio']:.2f}")
        print(f"    fitted A3/At             : {r['a3_over_at_fit']:.1f}  ({outside} Huang refrig. band {HUANG_LO}-{HUANG_HI})")
        print(f"    MW +4 g/mol -> d(omega)  : {r['mw_plus4_response']*100:+.1f} %   (heavier gas entrains more)")
        print(f"    off-design pull curve (P_s bar -> omega):")
        print("      " + "  ".join(f"{p:.3f}:{w:.3f}" for p, w in r["pull_curve"]))
    print("\n" + "=" * 84)
    print("  A_t is now FIRST-PRINCIPLES for all three units (removed as a fitted parameter).")
    print("  Fitted A3/At straddles Huang's refrigeration band (6.44-10.64): 324F004 above (20.6),")
    print("  324F002/F005 below (4.4/4.7) -- all three OUTSIDE it, so that band does NOT bound these")
    print("  deep-vacuum steam ejectors. The off-design curve is design-anchored with A3/At pinned by")
    print("  the single strict-PFD point; residual uncertainty is gated on a SECOND duty point (G9).")
    print("=" * 84)
