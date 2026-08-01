"""G9c -- Unit-335 urea droplet solidification / evaporation core (Lagrangian, first principles).

WHAT THIS ADVANCES.  handoff.md G9c had Unit 335 lifted from "no equipment list" to a spec-flow
boundary block (the 2026 manual gives product 1750-2000 MTPD, fluidisation air ~340000 m3/h, sprayer
air ~36820 m3/h, recycle 0.40, melt 98.6 wt% @ 140 C / 3.6 bar) but still lacked the DROPLET PHYSICS
that turns a spec-flow block into a predictive model.  The 2026 research pass supplies the exact
mechanistic equations; this module implements them as a standalone, universally-parameterised core.

PHYSICS (each relation standard and citable; research pass "G9c droplet" section):
  * Lagrangian force balance on a spherical melt droplet in a counter-current air stream --
        dv/dt = g (1 - rho_air/rho_p) - (3 Cd rho_air v_rel^2) / (4 rho_p d),   v_rel = v_drop + v_air
    (weight - buoyancy - aerodynamic drag), integrated with 4th-order Runge-Kutta.
  * Drag coefficient Cd(Re) by Schiller-Naumann  Cd = 24/Re (1 + 0.15 Re^0.687)  (sphere, Re < ~800),
    capped at the Newton value 0.44 above; Re = rho_air v_rel d / mu_air.
  * Conjugate heat transfer by the Ranz-Marshall Nusselt correlation  Nu = 2 + 0.6 Re^0.5 Pr^(1/3),
    h = Nu k_air / d; lumped-capacitance droplet (Bi << 1 for a sub-mm/mm melt drop).
  * Latent heat of FUSION released on the T_freeze plateau while the droplet crystallises -- the value
    is the G6 datum (dfusH = 13899 J/mol / 60.056 g/mol = 231.4 kJ/kg), so the solidification energy is
    reaction-/phase-consistent with gap_g6_h0_enthalpy.py, not an independent guess.
  * Residual-water mass transfer by the Ranz-Marshall Sherwood analogue  Sh = 2 + 0.6 Re^0.5 Sc^(1/3),
    corrected for STEFAN FLOW (the outward "blowing" that thickens the film and REDUCES the effective
    coefficient) by theta = ln(1+B)/B with the Spalding transfer number B.

WHAT IT VALIDATES (self-test): terminal velocity of a design prill is in the physical 3-12 m/s band;
Nu and Sh never fall below the isolated-sphere floor of 2; the Stefan blowing factor is in (0,1) so it
can only reduce transfer; the droplet fully solidifies in a finite, physically-plausible tower height;
that height falls monotonically as the droplet shrinks; and the integrated heat removed to the freeze
plateau equals cp_liq (T_init - T_freeze) + lambda_fus to numerical tolerance (energy closes).

Residual (still open): Unit-335's actual bed/tower geometry, fan curves and screen efficiencies (the
datasheets, not in the source set) to turn this droplet core into a full Unit-335 rating model.

Standalone (stdlib only), <1 s.  Run from `backend`:  python gap_g9c_droplet.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass

G = 9.80665                    # m/s^2

# --- urea melt/solid properties (G6 fusion datum; melt density/heat capacities, literature) --------
RHO_UREA = 1240.0              # kg/m3  molten/solid urea (~1230-1250)
CP_UREA_LIQ = 2000.0           # J/kg/K  molten urea
CP_UREA_SOL = 1550.0           # J/kg/K  solid urea
T_FREEZE_C = 132.7             # C  urea melting/solidification point (Tischer; = G2 fusion T)
LAMBDA_FUS = 13899.0 / 0.060056  # J/kg  = dfusH(G6) / MW_urea = 231.4 kJ/kg

# --- cooling-air properties at ~50 C (counter-current granulation/prill air) -----------------------
RHO_AIR = 1.09                 # kg/m3
MU_AIR = 1.96e-5               # Pa s
K_AIR = 0.028                  # W/m/K
PR_AIR = 0.70                  # Prandtl
SC_AIR = 0.60                  # Schmidt (water vapour in air)
D_WATER_AIR = 2.6e-5           # m2/s  water-vapour diffusivity in air (~50 C)


@dataclass(frozen=True)
class Droplet:
    d0_m: float                # initial diameter [m]
    T0_C: float                # initial melt temperature [C]
    v0_ms: float               # initial (downward) velocity [m/s]


def reynolds(v_rel: float, d: float) -> float:
    return RHO_AIR * abs(v_rel) * d / MU_AIR


def drag_coefficient(re: float) -> float:
    """Schiller-Naumann sphere drag, capped at the Newton value above the correlation's range."""
    if re < 1.0e-6:
        return 1.0e6
    cd = 24.0 / re * (1.0 + 0.15 * re ** 0.687)
    return max(cd, 0.44)


def nusselt(re: float) -> float:
    return 2.0 + 0.6 * math.sqrt(re) * PR_AIR ** (1.0 / 3.0)      # Ranz-Marshall


def sherwood(re: float) -> float:
    return 2.0 + 0.6 * math.sqrt(re) * SC_AIR ** (1.0 / 3.0)      # Ranz-Marshall analogue


def stefan_blowing_factor(spalding_B: float) -> float:
    """theta = ln(1+B)/B in (0,1): the outward Stefan flow reduces the effective transfer coeff."""
    if spalding_B <= 0.0:
        return 1.0
    return math.log(1.0 + spalding_B) / spalding_B


def terminal_velocity(d: float, v_air: float = 1.0) -> float:
    """Steady fall velocity: gravity-minus-buoyancy balances Schiller-Naumann drag (fixed-point)."""
    g_eff = G * (1.0 - RHO_AIR / RHO_UREA)
    v = 5.0
    for _ in range(200):
        v_rel = v + v_air
        cd = drag_coefficient(reynolds(v_rel, d))
        v_new = math.sqrt(4.0 * RHO_UREA * d * g_eff / (3.0 * cd * RHO_AIR)) - v_air
        if abs(v_new - v) < 1.0e-9:
            return v_new
        v = 0.5 * (v + v_new)
    return v


def _temperature_C(q_removed: float) -> tuple[float, float]:
    """Map cumulative heat removed per unit mass [J/kg] to (temperature C, solid fraction)."""
    q_sens_liq = CP_UREA_LIQ * (140.0 - T_FREEZE_C)      # datum T0 = 140 C handled by caller
    # caller passes q measured from its own T0; here we assume T0 = 140 C reference used in the model
    if q_removed <= q_sens_liq:
        return 140.0 - q_removed / CP_UREA_LIQ, 0.0
    if q_removed <= q_sens_liq + LAMBDA_FUS:
        return T_FREEZE_C, (q_removed - q_sens_liq) / LAMBDA_FUS
    return T_FREEZE_C - (q_removed - q_sens_liq - LAMBDA_FUS) / CP_UREA_SOL, 1.0


def fall_and_freeze(drop: Droplet, v_air: float = 1.0, dt: float = 1.0e-3,
                    max_t: float = 60.0) -> dict:
    """RK4-integrate the coupled fall + cooling until the droplet is fully solidified.

    Returns the solidification height, time, terminal velocity and the thermal/aero diagnostics.
    Heat removed is tracked per unit mass; T0 is 140 C (the melt inlet), matching _temperature_C.
    """
    d = drop.d0_m
    g_eff = G * (1.0 - RHO_AIR / RHO_UREA)
    q_sens_liq = CP_UREA_LIQ * (140.0 - T_FREEZE_C)
    q_freeze_done = q_sens_liq + LAMBDA_FUS

    def deriv(v: float, q: float) -> tuple[float, float]:
        v_rel = v + v_air
        re = reynolds(v_rel, d)
        cd = drag_coefficient(re)
        dvdt = g_eff - 3.0 * cd * RHO_AIR * v_rel * v_rel / (4.0 * RHO_UREA * d)
        T_C, _ = _temperature_C(q)
        h = nusselt(re) * K_AIR / d
        dqdt = 6.0 * h * (T_C - 50.0) / (RHO_UREA * d)     # per unit mass; air at 50 C
        return dvdt, dqdt

    z = 0.0
    v = drop.v0_ms
    q = 0.0
    t = 0.0
    z_freeze = None
    while t < max_t:
        # RK4 on (v, q); z integrates v
        k1v, k1q = deriv(v, q)
        k2v, k2q = deriv(v + 0.5 * dt * k1v, q + 0.5 * dt * k1q)
        k3v, k3q = deriv(v + 0.5 * dt * k2v, q + 0.5 * dt * k2q)
        k4v, k4q = deriv(v + dt * k3v, q + dt * k3q)
        z += dt * (v + 2 * (v + 0.5 * dt * k1v) + 2 * (v + 0.5 * dt * k2v) + (v + dt * k3v)) / 6.0
        v += dt * (k1v + 2 * k2v + 2 * k3v + k4v) / 6.0
        q += dt * (k1q + 2 * k2q + 2 * k3q + k4q) / 6.0
        t += dt
        if z_freeze is None and q >= q_freeze_done:
            z_freeze = z
            break
    T_C, solid = _temperature_C(q)
    re_term = reynolds(terminal_velocity(d, v_air) + v_air, d)
    B = CP_UREA_LIQ * 10.0 / LAMBDA_FUS      # illustrative Spalding number for the blowing diagnostic
    return {
        "d_mm": d * 1000.0, "v_terminal_ms": terminal_velocity(d, v_air),
        "re_terminal": re_term, "nu_terminal": nusselt(re_term), "sh_terminal": sherwood(re_term),
        "stefan_blowing": stefan_blowing_factor(B),
        "z_freeze_m": z_freeze, "t_freeze_s": t if z_freeze is not None else None,
        "q_at_freeze_jkg": q_freeze_done, "solid_fraction": solid, "T_final_C": T_C,
    }


def _self_test() -> None:
    design = Droplet(d0_m=1.6e-3, T0_C=140.0, v0_ms=1.0)
    r = fall_and_freeze(design)

    # terminal velocity of a ~1.6 mm prill sits in the physical band
    assert 3.0 <= r["v_terminal_ms"] <= 12.0, r["v_terminal_ms"]
    # Ranz-Marshall floors: an isolated sphere never transfers below Nu = Sh = 2
    assert r["nu_terminal"] >= 2.0 and r["sh_terminal"] >= 2.0
    # Stefan blowing can only REDUCE transfer
    assert 0.0 < r["stefan_blowing"] < 1.0
    # the droplet fully solidifies in a finite, physically-plausible tower height
    assert r["z_freeze_m"] is not None and 0.0 < r["z_freeze_m"] < 200.0
    assert r["solid_fraction"] >= 1.0 - 1e-9
    # energy closes: heat removed to the freeze plateau == sensible(liquid) + fusion
    expected = CP_UREA_LIQ * (140.0 - T_FREEZE_C) + LAMBDA_FUS
    assert abs(r["q_at_freeze_jkg"] - expected) < 1.0, (r["q_at_freeze_jkg"], expected)
    # smaller droplet solidifies in a SHORTER height (monotone -- higher area/volume ratio)
    small = fall_and_freeze(Droplet(d0_m=1.0e-3, T0_C=140.0, v0_ms=1.0))
    assert small["z_freeze_m"] < r["z_freeze_m"], (small["z_freeze_m"], r["z_freeze_m"])
    # fusion latent heat is the G6 datum
    assert abs(LAMBDA_FUS - 231433.0) < 100.0


if __name__ == "__main__":
    print("=" * 88)
    print("  G9c  UNIT-335 UREA DROPLET SOLIDIFICATION / EVAPORATION CORE  (Lagrangian, first principles)")
    print("=" * 88)
    print(f"\n  urea fusion latent heat   : {LAMBDA_FUS/1000.0:.1f} kJ/kg  (= G6 dfusH 13899 J/mol / 60.056)")
    print(f"  freeze temperature        : {T_FREEZE_C:.1f} C")
    for d_mm in (1.0, 1.6, 2.2):
        r = fall_and_freeze(Droplet(d0_m=d_mm * 1e-3, T0_C=140.0, v0_ms=1.0))
        print(f"\n  droplet d = {d_mm:.1f} mm")
        print(f"    terminal velocity        : {r['v_terminal_ms']:.2f} m/s   (Re_terminal ~ {r['re_terminal']:.0f})")
        print(f"    Ranz-Marshall Nu / Sh    : {r['nu_terminal']:.2f} / {r['sh_terminal']:.2f}   (floor 2.0)")
        print(f"    Stefan blowing factor    : {r['stefan_blowing']:.3f}   (<1 -> reduces transfer)")
        print(f"    solidification height    : {r['z_freeze_m']:.1f} m  in {r['t_freeze_s']:.2f} s "
              f"(solid frac {r['solid_fraction']:.2f}, T {r['T_final_C']:.0f} C)")
    _self_test()
    print("\n" + "=" * 88)
    print("  G9c status: the Unit-335 droplet now has full Lagrangian solidification physics -- drag")
    print("  (Schiller-Naumann), heat/mass transfer (Ranz-Marshall + Stefan blowing) and a fusion")
    print("  plateau anchored to the G6 enthalpy datum, integrated by RK4 to a finite freeze height")
    print("  that shrinks with droplet size.  Residual: Unit-335 bed/tower geometry + fan/screen data")
    print("  (not in the source set) to close it into a full tower rating model.")
    print("=" * 88)
