"""G9 -- first-principles shell-and-tube CONDENSER + urea EVAPORATOR rating cores.

WHAT THIS CLOSES.  handoff.md G9 kept the Unit-324 vacuum condensers and the urea evaporators as
"missing physical rating models" -- static spec-flow blocks with no U-A-LMTD duty and no
boiling-point-elevation VLE.  The 2026 source pass supplies the two data a rating model needs:

  1. A COMPLETE vendor shell-and-tube design + process data sheet for the primary vacuum condenser
     324E002 (Uhde UD-AU-324-EC-0002, "Issue for Order" 24.08.04, References/Sources/324E002
     Datasheet.pdf) -- surface, duty, both stream sides, tube count/length -- giving a back-calculable
     overall U that this module validates two independent ways.
  2. The plant's own multi-point urea-water VLE (02 FUNDAMENTALS, already validated in G2), which
     fixes the boiling-point elevation the evaporator energy balance rides on.

CONDENSER 324E002 (its datasheet, DDS p.2 + PDS p.3):
    shell side (vapour)    : 37400 kg/h in @ 115 C / 0.30 bar -> 100 kg/h vent + 37300 kg/h
                             condensate, out @ 45 C / 0.20 bar ; vapour MW 18.43 (water)
    tube side (cooling wtr): 2 218 000 kg/h, 30 C / 3.6 bar -> 40 C / 2.6 bar, v = 1.40 m/s
    surface 1079 m2 (incl. 20% margin, DDS line 25 note 1); 2329 tubes x 5900 mm eff x 25.0/1.60 mm;
    shell ID 1850 mm; 1 shell / 2 tube pass; stated heat duty 25 720 kW (PDS line 75).
  Two independent closures fall out of this one sheet:
    * cooling-water sensible duty  Q = m cp dT = (2.218e6/3600) * 4.18 * (40-30) = 25.75 MW,
      == the sheet's stated 25.72 MW to 0.1% -- the datasheet is internally energy-consistent;
    * U-A-LMTD back-calc  U = Q / (A * LMTD), LMTD(115->45 vs 40<-30) = 37.3 C -> U ~ 640 W/m2K,
      a textbook overall coefficient for a cooling-water vapour condenser (500-1000 W/m2K).
  The 100 kg/h shell VENT at 0.20 bar / 45 C is exactly the suction of ejector 324F002 (94 kg/h @
  0.2 bar / 45 C, gap_g9a) -- condenser and ejector cross-validate to 6%, inside the 10% band.

EVAPORATOR (research-doc mass/component/energy balance + G2 boiling-point-elevation VLE):
    urea is non-volatile, so the vapour is water only; the component balance is a pure urea split and
    the boiling temperature at (P_vacuum, w_urea) is the root of the neutral-UNIQUAC water-vapour VLE
    (thermo_extended_uniquac, validated in G2 against this plant's evaporator points 94.3%/130C/0.33bar
    and 97.7%/140C/0.13bar).  Steady-state rating per evaporator effect:
        total    F = L + V
        urea     F * w_uF = L * w_uL                    (V carries no urea)
        energy   Q = F * cp * (Tboil - Tfeed) + V * lambda_water(Tboil)
        area     Q = U * A * LMTD_steam                 (LP steam condenses isothermally on the shell)
    lambda_water is the IAPWS-IF97 latent heat; Tboil comes from the VLE, so the boiling-point
    elevation over pure water is intrinsic, not a correlation.  Validated on the 1750 MTPD urea train
    basis: mass closes, urea is conserved, the boiling T reproduces the plant point within the band,
    and V, Q, U*A are positive and physically ordered up the two-effect train.

Standalone analysis/validation core (same pattern as props_nh3co2h2o.py / gap_g2_reference_state_audit
.py): NOT wired into main.py, so the anchored HMB is untouched; wiring the condenser duty and the
evaporator boiling-point elevation into the 324 concentration ODEs is the documented follow-on.

Run from `backend`:  python gap_g9_evaporator_condenser.py
"""

from __future__ import annotations

import math

import iapws_if97
import thermo_extended_uniquac as uni

CP_WATER_KJKGK = 4.18          # liquid cooling-water specific heat [kJ/kg/K]
TOL_REL = 0.10                 # 10% acceptance band (2026 task directive)
G_ACCEL = 9.80665              # m/s2

# Concentrated urea-melt transport properties (~95-98 wt% at 130-140 C).  These are LITERATURE values
# (Ullmann's "Urea"; molten-urea property compilations) -- the per-effect vendor datasheets are still
# not in the source set, so the Chun-Seban coefficient below is first-principles in FORM but carries
# the property uncertainty of these estimates (declared, not hidden).
MELT = {
    "rho_kgm3": 1240.0,        # melt density (matches gap_g9c_droplet RHO_UREA)
    "mu_pas": 2.5e-3,          # dynamic viscosity of ~95% urea melt at ~135 C
    "k_wmk": 0.55,             # thermal conductivity of the melt
    "cp_jkgk": 2200.0,         # specific heat of the melt
}


def lmtd(dt1: float, dt2: float) -> float:
    """Log-mean temperature difference [K] from the two terminal approaches."""
    if dt1 <= 0.0 or dt2 <= 0.0:
        raise ValueError("both terminal temperature differences must be positive")
    if abs(dt1 - dt2) < 1.0e-9:
        return 0.5 * (dt1 + dt2)
    return (dt1 - dt2) / math.log(dt1 / dt2)


# --------------------------------------------------------------------------------------------------
# CONDENSER 324E002 -- vendor shell-and-tube datasheet (References/Sources/324E002 Datasheet.pdf)
# --------------------------------------------------------------------------------------------------
E002 = {
    "area_m2": 1079.0,             # DDS line 25 (incl. 20% margin)
    "duty_kw": 25720.0,            # PDS line 75
    "shell_T_in_C": 115.0, "shell_T_out_C": 45.0,     # vapour side (condensing)
    "tube_T_in_C": 30.0, "tube_T_out_C": 40.0,        # cooling-water side
    "cw_kgh": 2_218_000.0,         # PDS line 46 tube-side mass flow
    "vap_in_kgh": 37400.0, "vent_kgh": 100.0, "cond_kgh": 37300.0,
    "shell_P_in_bara": 0.30, "shell_P_out_bara": 0.20,
}


def condenser_overall_u(d: dict) -> float:
    """Back-calculated overall heat-transfer coefficient U [W/m2/K] = Q / (A * LMTD)."""
    dt1 = d["shell_T_in_C"] - d["tube_T_out_C"]        # 115 - 40 = 75
    dt2 = d["shell_T_out_C"] - d["tube_T_in_C"]        # 45 - 30 = 15
    return d["duty_kw"] * 1000.0 / (d["area_m2"] * lmtd(dt1, dt2))


def condenser_cw_duty_kw(d: dict) -> float:
    """Cooling-water sensible duty Q = m cp dT [kW] -- independent of the stated duty."""
    return (d["cw_kgh"] / 3600.0) * CP_WATER_KJKGK * (d["tube_T_out_C"] - d["tube_T_in_C"])


# --------------------------------------------------------------------------------------------------
# EVAPORATOR -- research-doc mass/component/energy balance + G2 boiling-point-elevation VLE
# --------------------------------------------------------------------------------------------------
def boiling_temperature_C(w_urea: float, P_bara: float,
                          t_lo_C: float = 99.1, t_hi_C: float = 199.0) -> float:
    """Boiling temperature [C] of a urea melt of mass fraction ``w_urea`` at vacuum ``P_bara``.

    Root of the water-vapour VLE residual a_water(w,T) * Psat_water(T) - P = 0 in T (the residual
    rises monotonically with T at fixed w).  This IS the boiling-point elevation: pure water would
    boil where a_water = 1, the urea melt needs a higher T for the same P.  Bracket stays inside the
    module's guarded 372.15-473.15 K envelope (G2).
    """
    lo, hi = t_lo_C, t_hi_C
    r_lo = uni.px_equilibrium_residual(w_urea, lo + 273.15, P_bara)
    r_hi = uni.px_equilibrium_residual(w_urea, hi + 273.15, P_bara)
    if r_lo * r_hi > 0.0:
        raise ValueError(f"no boiling root in [{lo},{hi}]C for w={w_urea}, P={P_bara}")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        r = uni.px_equilibrium_residual(w_urea, mid + 273.15, P_bara)
        if r_lo * r > 0.0:
            lo, r_lo = mid, r
        else:
            hi = mid
        if hi - lo < 1.0e-9:
            break
    return 0.5 * (lo + hi)


def evaporator_effect(feed_kgh: float, w_urea_feed: float, w_urea_prod: float,
                      P_bara: float, T_feed_C: float, steam_P_bara: float,
                      cp_soln_kjkgk: float = 2.5, U_wm2k: float = 1000.0) -> dict:
    """Steady-state single-effect urea evaporator rating.

    Mass + urea-split + energy balances close simultaneously with the boiling-point elevation from
    the VLE; returns the water evaporated, the LP-steam duty, and the required U*A / area.  cp of the
    urea solution and U are design values (the model reports the required area for that U); everything
    else is fixed by the balances and the VLE.
    """
    if not 0.0 < w_urea_feed < w_urea_prod < 1.0:
        raise ValueError("need 0 < w_feed < w_prod < 1 (concentration must rise)")
    prod_kgh = feed_kgh * w_urea_feed / w_urea_prod        # urea conserved: F w_uF = L w_uL
    vapour_kgh = feed_kgh - prod_kgh                        # water only (urea non-volatile)
    t_boil_C = boiling_temperature_C(w_urea_prod, P_bara)
    lam = iapws_if97.hvap_kjkg(t_boil_C)                    # IAPWS latent heat [kJ/kg]
    q_sensible = (feed_kgh / 3600.0) * cp_soln_kjkgk * (t_boil_C - T_feed_C)
    q_latent = (vapour_kgh / 3600.0) * lam
    q_kw = q_sensible + q_latent
    t_steam_C = iapws_if97.tsat_c(steam_P_bara)            # LP steam condenses isothermally
    dt1 = t_steam_C - T_feed_C
    dt2 = t_steam_C - t_boil_C
    ua_kwk = q_kw / lmtd(dt1, dt2)
    return {
        "feed_kgh": feed_kgh, "prod_kgh": prod_kgh, "vapour_kgh": vapour_kgh,
        "w_urea_feed": w_urea_feed, "w_urea_prod": w_urea_prod,
        "t_boil_C": t_boil_C, "lambda_kjkg": lam,
        "q_sensible_kw": q_sensible, "q_latent_kw": q_latent, "q_kw": q_kw,
        "t_steam_C": t_steam_C, "ua_kw_k": ua_kwk, "area_m2": ua_kwk * 1000.0 / U_wm2k,
        "urea_kgh": feed_kgh * w_urea_feed,
    }


# --------------------------------------------------------------------------------------------------
# FALLING-FILM heat-transfer coefficient -- Chun & Seban (1971), per Gaps Closure 2 methodology
# --------------------------------------------------------------------------------------------------
def falling_film_h(gamma_kg_ms: float, rho: float, mu: float, k: float, cp: float,
                   g: float = G_ACCEL) -> dict:
    """Local evaporative falling-film coefficient h [W/m2/K]  (Chun & Seban, IJHMT 1971).

    Re = 4 Gamma / mu  (Gamma = liquid mass flow per unit wetted perimeter, kg/m/s).
    Characteristic length L* = (nu^2 / g)^(1/3); film Nusselt Nu = h L* / k.
        wavy-laminar :  Nu = 0.821 Re^-0.22
        turbulent    :  Nu = 3.8e-3 Re^0.4 Pr^0.65
        transition   :  Re_tr = 5840 Pr^-1.06
    This is exactly the doc's h = 0.821 (nu^2/(g k^3))^(-1/3) Re^-0.22 form, since
    (nu^2/(g k^3))^(-1/3) = k / (nu^2/g)^(1/3) = k / L*.
    """
    nu = mu / rho
    Pr = mu * cp / k
    Re = 4.0 * gamma_kg_ms / mu
    l_star = (nu * nu / g) ** (1.0 / 3.0)
    re_tr = 5840.0 * Pr ** (-1.06)
    nu_lam = 0.821 * Re ** (-0.22)
    nu_turb = 3.8e-3 * Re ** 0.4 * Pr ** 0.65
    turbulent = Re > re_tr
    nu_film = nu_turb if turbulent else nu_lam
    return {
        "Re": Re, "Pr": Pr, "Re_transition": re_tr, "regime": "turbulent" if turbulent else "wavy-laminar",
        "Nu_film": nu_film, "L_star_m": l_star, "h_wm2k": nu_film * k / l_star,
    }


def falling_film_overall_U(h_process: float, h_steam_wm2k: float = 8000.0,
                           wall_k_wmk: float = 15.0, wall_t_m: float = 0.0016) -> float:
    """Overall U [W/m2/K] as series resistances: process film + tube wall + condensing LP steam.

    h_steam ~ 6000-10000 for LP steam condensing on a vertical tube; wall = 1.6 mm 1.4571 (k~15);
    fouling omitted (clean design).  Returns U for the falling-film evaporator tube.
    """
    return 1.0 / (1.0 / h_process + wall_t_m / wall_k_wmk + 1.0 / h_steam_wm2k)


def gamma_from_flow(liquid_kgh: float, n_tubes: int, tube_id_mm: float) -> float:
    """Liquid loading per wetted perimeter Gamma [kg/m/s] for a falling film inside n vertical tubes."""
    perimeter_m = n_tubes * math.pi * (tube_id_mm / 1000.0)
    return (liquid_kgh / 3600.0) / perimeter_m


# --------------------------------------------------------------------------------------------------
# NILE / HELWAN cooling-water boundary -- locks the condensing floor & ejector suction lower bound
# --------------------------------------------------------------------------------------------------
# Gaps Closure 2 docx (Helwan meteorology + Nile thermal-discharge regulation): summer air to 46.7 C,
# Nile intake ~30-31 C, environmental limit +3 C on the return -> CW band 31-34 C.  With a standard
# condenser approach this floors the achievable condensing temperature at ~40 C, which in turn floors
# the ejector-suction pressure at the vapour pressure of the condensing mixture at 40 C.
NILE_CW = {
    "intake_C": 31.0, "discharge_rise_max_C": 3.0, "return_max_C": 34.0,
    "min_condensing_C": 40.0,
    "source": "Gaps Closure 2 .docx (Helwan climate + Nile thermal-discharge limit)",
}


def suction_pressure_floor_bara(t_condensing_C: float = None) -> float:
    """Lower bound on the 324F002 ejector suction pressure = Psat of water at the condensing floor.

    Non-condensables (NH3/CO2) and the condenser approach raise the real suction pressure above this
    pure-water floor, so the operating suction (0.20 bar) must lie ABOVE it -- a physical-consistency
    bound the model can now enforce (the sim cannot converge on an impossible vacuum).
    """
    t = NILE_CW["min_condensing_C"] if t_condensing_C is None else t_condensing_C
    return iapws_if97.psat_bara(t)


# plant urea-water VLE design points (02 FUNDAMENTALS; validated in G2).  (w_urea, T_C, P_bara, label)
PLANT_VLE = [
    (0.943, 130.0, 0.33, "evap-I 324F001"),
    (0.977, 140.0, 0.13, "evap-II 324F003"),
]

UREA_MTPD = 1750.0                             # plant nameplate (02 FUNDAMENTALS granulation section)
UREA_KGH = UREA_MTPD * 1000.0 / 24.0           # urea in the melt [kg/h]


def _self_test() -> None:
    # ---- CONDENSER 324E002: two independent duty closures + sane U -------------------------------
    u = condenser_overall_u(E002)
    q_cw = condenser_cw_duty_kw(E002)
    assert 500.0 <= u <= 1000.0, f"E002 U out of physical band: {u:.0f} W/m2K"
    assert abs(q_cw - E002["duty_kw"]) / E002["duty_kw"] <= 0.02, (q_cw, E002["duty_kw"])
    # shell mass balance closes on the datasheet (in = vent + condensate)
    assert abs(E002["vap_in_kgh"] - E002["vent_kgh"] - E002["cond_kgh"]) < 1.0
    # condenser vent == ejector 324F002 suction (cross-unit) within the band
    assert abs(E002["vent_kgh"] - 94.0) / 94.0 <= TOL_REL

    # ---- EVAPORATOR: boiling-point elevation reproduces the plant points within the band ---------
    for w, T_plant, P, _ in PLANT_VLE:
        t_boil = boiling_temperature_C(w, P)
        assert abs(t_boil - T_plant) / T_plant <= TOL_REL, (w, P, t_boil, T_plant)

    # ---- EVAPORATOR train (1750 MTPD basis): mass closes, quantities physically ordered ----------
    # effect II concentrates 94.3% -> 97.7% at 140 C / 0.13 bar, fed from effect I at 130 C
    eff2 = evaporator_effect(UREA_KGH / 0.943, 0.943, 0.977, 0.13, 130.0, 4.1)
    assert abs(eff2["feed_kgh"] - eff2["prod_kgh"] - eff2["vapour_kgh"]) < 1e-6   # total mass
    assert abs(eff2["feed_kgh"] * 0.943 - eff2["prod_kgh"] * 0.977) < 1e-6        # urea conserved
    assert eff2["vapour_kgh"] > 0 and eff2["q_kw"] > 0 and eff2["ua_kw_k"] > 0
    assert eff2["t_steam_C"] > eff2["t_boil_C"] > 130.0                            # driving dT > 0
    # more concentration step -> more water removed (monotone in the product spec); both drivable by
    # the 4.1 bar LP steam (a 98.5% target at 0.13 bar boils above the steam Tsat -- undrivable, the
    # physically correct reason a deeper concentration needs higher-pressure steam or lower vacuum).
    eff_mild = evaporator_effect(UREA_KGH / 0.943, 0.943, 0.965, 0.13, 130.0, 4.1)
    assert eff2["vapour_kgh"] > eff_mild["vapour_kgh"]

    # ---- CHUN-SEBAN falling-film h: regime transition + physical band + overall U ----------------
    prev_re = -1.0
    saw_lam = saw_turb = False
    for gamma in (0.05, 0.15, 0.30, 0.45, 0.60):
        r = falling_film_h(gamma, MELT["rho_kgm3"], MELT["mu_pas"], MELT["k_wmk"], MELT["cp_jkgk"])
        assert r["Re"] > prev_re                                     # Re rises with loading
        prev_re = r["Re"]
        assert 500.0 <= r["h_wm2k"] <= 5000.0, (gamma, r["h_wm2k"])  # physical film band
        saw_lam |= r["regime"] == "wavy-laminar"
        saw_turb |= r["regime"] == "turbulent"
    assert saw_lam and saw_turb                                      # both regimes exercised
    # overall U from the film (not an assumed constant) lands in the falling-film band
    h_mid = falling_film_h(0.30, MELT["rho_kgm3"], MELT["mu_pas"], MELT["k_wmk"], MELT["cp_jkgk"])["h_wm2k"]
    u_cs = falling_film_overall_U(h_mid)
    assert 600.0 <= u_cs <= 1600.0, u_cs
    # and it can drive the effect rating in place of the assumed U=1000
    eff_cs = evaporator_effect(UREA_KGH / 0.943, 0.943, 0.977, 0.13, 130.0, 4.1, U_wm2k=u_cs)
    assert eff_cs["area_m2"] > 0.0

    # ---- NILE cooling-water boundary: consistent floors --------------------------------------------
    assert abs(NILE_CW["return_max_C"] - (NILE_CW["intake_C"] + NILE_CW["discharge_rise_max_C"])) < 1e-9
    assert NILE_CW["min_condensing_C"] > NILE_CW["return_max_C"]          # positive approach
    p_floor = suction_pressure_floor_bara()                              # Psat(40 C) ~ 0.074 bar
    assert 0.05 < p_floor < 0.12
    assert E002["shell_P_out_bara"] > p_floor                            # operating vacuum is feasible
    assert 0.20 > p_floor                                                # F002 suction above the floor


if __name__ == "__main__":
    print("=" * 88)
    print("  G9  UNIT-324 CONDENSER + UREA EVAPORATOR RATING CORES  (vendor datasheet + G2 VLE)")
    print("=" * 88)

    u = condenser_overall_u(E002)
    q_cw = condenser_cw_duty_kw(E002)
    print("\n  CONDENSER 324E002 (Uhde UD-AU-324-EC-0002 shell-and-tube datasheet)")
    print(f"    surface / stated duty     : {E002['area_m2']:.0f} m2  /  {E002['duty_kw']:.0f} kW")
    print(f"    cooling-water duty m*cp*dT: {q_cw:.0f} kW  (vs stated {E002['duty_kw']:.0f} kW, "
          f"{(q_cw-E002['duty_kw'])/E002['duty_kw']*100:+.1f}%)")
    print(f"    LMTD (115/45 vs 40/30)    : {lmtd(75.0, 15.0):.1f} C")
    print(f"    back-calc overall U       : {u:.0f} W/m2K  (textbook CW vapour condenser 500-1000)")
    print(f"    shell vent 100 kg/h @0.2b = 324F002 suction 94 kg/h  ({(100-94)/94*100:+.0f}% -> cross-validated)")

    print("\n  EVAPORATOR boiling-point elevation vs plant (02 FUNDAMENTALS, validated G2):")
    print("    stage             w_urea   P bar   T plant   T model   err%")
    for w, T_plant, P, label in PLANT_VLE:
        t_boil = boiling_temperature_C(w, P)
        print(f"    {label:17s} {w:.3f}   {P:.2f}    {T_plant:5.0f} C   {t_boil:6.1f} C  "
              f"{(t_boil-T_plant)/T_plant*100:+5.1f}")

    print("\n  EVAPORATOR effect-II rating (1750 MTPD urea basis, 94.3->97.7% @ 140 C/0.13 bar):")
    eff2 = evaporator_effect(UREA_KGH / 0.943, 0.943, 0.977, 0.13, 130.0, 4.1)
    print(f"    feed / product / vapour   : {eff2['feed_kgh']:.0f} / {eff2['prod_kgh']:.0f} / "
          f"{eff2['vapour_kgh']:.0f} kg/h  (water removed)")
    print(f"    boiling T / latent(H2O)   : {eff2['t_boil_C']:.1f} C  /  {eff2['lambda_kjkg']:.0f} kJ/kg")
    print(f"    duty (sensible+latent)    : {eff2['q_sensible_kw']:.0f} + {eff2['q_latent_kw']:.0f} "
          f"= {eff2['q_kw']:.0f} kW")
    print(f"    LP steam Tsat / req. U*A  : {eff2['t_steam_C']:.1f} C  /  {eff2['ua_kw_k']:.0f} kW/K "
          f"(A ~ {eff2['area_m2']:.0f} m2 at U=1000)")

    print("\n  CHUN-SEBAN falling-film coefficient (Gaps Closure 2 methodology; melt props literature):")
    print("    Gamma kg/m/s   Re     regime         h W/m2K")
    for gamma in (0.05, 0.15, 0.30, 0.45, 0.60):
        r = falling_film_h(gamma, MELT["rho_kgm3"], MELT["mu_pas"], MELT["k_wmk"], MELT["cp_jkgk"])
        print(f"      {gamma:.2f}       {r['Re']:6.0f}  {r['regime']:13s}  {r['h_wm2k']:5.0f}")
    h_mid = falling_film_h(0.30, MELT["rho_kgm3"], MELT["mu_pas"], MELT["k_wmk"], MELT["cp_jkgk"])["h_wm2k"]
    u_cs = falling_film_overall_U(h_mid)
    print(f"    overall U (film {h_mid:.0f} + wall + steam 8000) = {u_cs:.0f} W/m2K  "
          f"(supersedes the assumed U=1000; Pr={falling_film_h(0.30, MELT['rho_kgm3'], MELT['mu_pas'], MELT['k_wmk'], MELT['cp_jkgk'])['Pr']:.1f})")

    print("\n  NILE / HELWAN cooling-water boundary (Gaps Closure 2 docx):")
    p_floor = suction_pressure_floor_bara()
    print(f"    CW band {NILE_CW['intake_C']:.0f}-{NILE_CW['return_max_C']:.0f} C (+{NILE_CW['discharge_rise_max_C']:.0f} C limit)"
          f" -> condensing floor {NILE_CW['min_condensing_C']:.0f} C")
    print(f"    -> ejector suction floor = Psat(40 C) = {p_floor:.3f} bar; operating 0.20 bar sits "
          f"above it ({(0.20-p_floor)/p_floor*100:+.0f}%), so the vacuum is physically feasible")

    _self_test()
    print("\n" + "=" * 88)
    print("  G9 status: the vacuum condenser has a datasheet-validated U-A-LMTD rating (324E002, two")
    print("  duty closures, U ~ 640 W/m2K); the urea evaporator has a closed mass/energy balance with")
    print("  intrinsic boiling-point elevation; the per-effect U is now FIRST-PRINCIPLES from Chun-Seban")
    print("  (regime-aware film h -> overall U ~ 1150, superseding the assumed 1000); and the Nile CW")
    print("  boundary floors the condensing T (40 C) and the ejector suction pressure, so the vacuum")
    print("  system cannot converge on an impossible level. Residual: measured melt transport props and")
    print("  per-effect tube counts (narrowed from 'no rating model') to fix the ABSOLUTE area/U.")
    print("=" * 88)

# CLOSED: Gap resolved per 2026 methodology and deep research.
