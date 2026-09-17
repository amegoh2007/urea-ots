"""322C001 LP absorber: two packed beds on rate-based transfer units.

    lower bed   1 500 mm in the ID 922 section, washed through sprayer N4 by stream 755
                (322P002 / 322E006) and by the CPL leaving the bed above
    upper bed   1 000 mm in the ID 576 section, washed through sprayer N5 by CPL (stream 954)
    packing     25 mm metal Pall rings, Raflux 25-10: a = 250 m2/m3, void 0.95
    sources     UD-AU-322-EC-0007 (column datasheet), UD-AU-322-DZ-0007-001 rev 02 (arrangement,
                as built), UD-AU-322-DZ-0008-001 (Rauschert packing datasheet)

Each bed, each volatile species, is the counter-current gas-film balance on a straight equilibrium
line (Colburn):

    (y_out - y*_in) / (y_in - y*_in) = (1 - lam) / (exp(NTU (1 - lam)) - lam),     lam = m G / L

    NTU      = c_i . k_G a_w P Z / G_m                          Onda, Takeuchi & Okumoto (1968)
    a_w / a  = 1 - exp(-1.45 (sig_c/sig)^0.75 Re_L^0.1 Fr_L^-0.05 We_L^0.2)
    k_G      = 5.23 (a D_G / R T) Re_G^0.7 Sc_G^(1/3) (a d_p)^-2

Lower bed.  y*_in is the NH3 / CO2 partial pressure over stream 755 at the live liquor temperature,
and the slope m is dp_NH3/dx over the LIVE column liquor.  Both come from the Extended UNIQUAC
speciation (`props_nh3co2h2o.speciate`, Thomsen & Rasmussen / Darde parameters, regressed 0-110 C)
times the Rumpf & Maurer Henry constant, so a liquor that has loaded up or warmed up takes less.
Upper bed.  CPL enters clean (y*_in = 0).  NH3 loads it along its Henry line, and the bed warms by
its own heat of absorption (`heat_of_absorption_j_mol`, the temperature slope of the same speciated
back-pressure, so CO2 is charged its carbamate heat and not its physical solution heat).  CO2 reacts
with that NH3 (lam = 0).

c_i is the one per-species number the sources do not supply.  Onda quotes k_G to about +/-30 %.  It is
solved at the boot pin so that the design uptake is the PFD 204 -> 797 split exactly: 0.80 for NH3,
0.83 for CO2.  Water is not a transfer-unit species: the vent leaves the CPL wash saturated,
y_w = a_w psat(T_top)/P, with a_w (0.88) solved the same way against PFD 797's 2.28 mol%.
"""
import math

import iapws_if97
import props_nh3co2h2o as pr

R_GAS = 8.314462618
G_ACC = 9.80665
MW = {"NH3": 17.0304, "CO2": 44.0098, "H2O": 18.0152, "N2": 28.0134, "O2": 31.9988,
      "CH4": 16.043, "H2": 2.0158, "Urea": 60.0554, "Biuret": 103.0804}      # == main.MW_COMP
VOLATILE = ("NH3", "CO2")

A_PACK = 250.0            # m2/m3, Raflux 25-10 metal
D_PACK = 0.025            # m, nominal size
SIGMA_C_STEEL = 0.075     # N/m, Onda's critical surface tension for steel packing
BED_LO = {"Z": 1.5, "ID": 0.922}
BED_UP = {"Z": 1.0, "ID": 0.576}
RHO_LIQ = 1005.0          # kg/m3, PFD 755
CP_LIQ = 4.18             # kJ/(kg K), the dilute wash
CP_GAS = 1.05             # kJ/(kg K), N2-rich vent

_FULLER_V = {"NH3": 20.7, "CO2": 26.9, "N2": 18.5}     # Fuller-Schettler-Giddings diffusion volumes

#  Speciation grid.  Evaluated lazily, one node at a time.  The partial pressures span decades across
#  the NH3:CO2 stoichiometric line, so the grid is geometric in both molalities and the interpolation
#  is trilinear in (ln m_N, ln m_C, T) on the LOGARITHMS of the pressures and slopes: a dilute CPL
#  effluent at 0.06 mol/kg CO2 must not borrow the pressure of an acidic 0.25 mol/kg neighbour.
GRID_RATIO, GRID_DT = 1.2, 1.0
N_FLOOR, C_FLOOR = 0.01, 0.001                        # mol/kg water
T_SPEC_LO_K, T_SPEC_HI_K = 283.15, 373.15            # speciation grid 10-100 C; van 't Hoff beyond
_LN_R = math.log(GRID_RATIO)


def area_m2(bed):
    return math.pi * 0.25 * bed["ID"] ** 2


def water_mu_pas(t_k):
    """Vogel equation for liquid water."""
    return 2.414e-5 * 10.0 ** (247.8 / (t_k - 140.0))


def water_sigma_nm(t_k):
    """IAPWS R1-76 surface tension of water."""
    tau = max(1.0 - t_k / 647.096, 1e-9)
    return 0.2358 * tau ** 1.256 * (1.0 - 0.625 * tau)


def gas_mu_pas(t_k):
    """Sutherland for N2, the carrier gas (75 mol% of stream 797)."""
    return 1.781e-5 * (300.55 + 111.0) / (t_k + 111.0) * (t_k / 300.55) ** 1.5


def diffusivity_m2s(species, t_k, p_pa):
    """Fuller-Schettler-Giddings (1966), species in N2."""
    va, vb = _FULLER_V[species], _FULLER_V["N2"]
    root = math.sqrt(1.0 / MW[species] + 1.0 / MW["N2"])
    return 1.0e-7 * t_k ** 1.75 * root / ((p_pa / 101325.0) * (va ** (1 / 3) + vb ** (1 / 3)) ** 2)


def wetted_fraction(l_kgm2s, t_k):
    """Onda's wetted fraction of the packing surface."""
    if l_kgm2s <= 0.0:
        return 0.0
    mu, sig = water_mu_pas(t_k), water_sigma_nm(t_k)
    re = l_kgm2s / (A_PACK * mu)
    fr = l_kgm2s ** 2 * A_PACK / (RHO_LIQ ** 2 * G_ACC)
    we = l_kgm2s ** 2 / (RHO_LIQ * sig * A_PACK)
    return 1.0 - math.exp(-1.45 * (SIGMA_C_STEEL / sig) ** 0.75 * re ** 0.1 * fr ** -0.05 * we ** 0.2)


def onda_ntu(species, bed, m_liq_kgh, m_gas_kgh, n_gas_kmolh, t_k, p_pa):
    """Gas-film transfer units of one bed, k_G a_w P Z / G_m, before the per-species factor."""
    if m_gas_kgh <= 0.0 or n_gas_kmolh <= 0.0 or m_liq_kgh <= 0.0:
        return 0.0
    area = area_m2(bed)
    l_flux = m_liq_kgh / 3600.0 / area
    v_flux = m_gas_kgh / 3600.0 / area
    gm = n_gas_kmolh * 1000.0 / 3600.0 / area                     # mol/(m2 s)
    rho_g = p_pa * (m_gas_kgh / n_gas_kmolh / 1000.0) / (R_GAS * t_k)
    mu_g = gas_mu_pas(t_k)
    d_g = diffusivity_m2s(species, t_k, p_pa)
    k_g = (5.23 * (A_PACK * d_g / (R_GAS * t_k)) * (v_flux / (A_PACK * mu_g)) ** 0.7
           * (mu_g / (rho_g * d_g)) ** (1.0 / 3.0) * (A_PACK * D_PACK) ** -2.0)   # mol/(m2 s Pa)
    return k_g * A_PACK * wetted_fraction(l_flux, t_k) * p_pa * bed["Z"] / gm


def liquid_residence_s(bed, m_liq_kgh, t_k):
    """Time the liquid takes to cross a bed: operating holdup over volumetric flow.

    Holdup is the laminar film on the packing surface, h_L = (12 mu_L a^2 u_L / (rho_L g))^(1/3)
    (Billet & Schultes' pre-loading form with the whole surface wetted, an upper bound), so the
    residence is Z h_L / u_L.  The CPL wash at design: h_L 0.044, 24 s."""
    area = area_m2(bed)
    u_l = m_liq_kgh / RHO_LIQ / 3600.0 / area                    # m/s superficial
    if u_l <= 1e-12:
        return 3600.0
    h_l = (12.0 * water_mu_pas(t_k) * A_PACK ** 2 * u_l / (RHO_LIQ * G_ACC)) ** (1.0 / 3.0)
    return min(bed["Z"] * h_l / u_l, 3600.0)


def colburn(y_in, y_star, ntu, lam):
    """Counter-current gas outlet on a straight equilibrium line through y_star."""
    if ntu <= 0.0:
        return y_in
    if abs(1.0 - lam) < 1.0e-9:
        f = 1.0 / (1.0 + ntu)
    else:
        f = (1.0 - lam) / (math.exp(min(ntu * (1.0 - lam), 700.0)) - lam)
    return y_star + (y_in - y_star) * f


def henry_nh3_pa(t_k):
    return pr.henry_nh3_MPa(t_k) * 1.0e6


def heat_of_absorption_j_mol(w, t_c):
    """(NH3, CO2) differential heat released per mol taken up by a liquid of composition w, J/mol.

    -R dln(p_i)/d(1/T) at fixed liquid composition, on the speciated back-pressure the beds use.  The
    apparent partial pressure already carries the chemistry, so this is the whole heat: NH3 31-36 and
    CO2 80-99 kJ/mol over the 322C001 liquor, where the bare Henry constants give 34 and 16 (CO2's
    physical solution heat, without the carbamate and bicarbonate it forms).  Held 1 K inside the
    speciation's range so the difference never straddles its flat edge."""
    t_k = min(max(t_c + 273.15, T_SPEC_LO_K + 1.0), T_SPEC_HI_K - 1.0)
    lo = _grid_pressure(w, t_k - 1.0)
    hi = _grid_pressure(w, t_k + 1.0)
    x = 1.0 / (t_k + 1.0) - 1.0 / (t_k - 1.0)
    return tuple(-R_GAS * (math.log(hi[i]) - math.log(lo[i])) / x for i in (0, 1))


# ---- back-pressure over ammonia water -----------------------------------------------------------
_NODES = {}


def molalities(w):
    ww = max(w.get("H2O", 0.0), 1e-9)
    return (max(w.get("NH3", 0.0) / (MW["NH3"] / 1000.0) / ww, N_FLOOR),
            max(w.get("CO2", 0.0) / (MW["CO2"] / 1000.0) / ww, C_FLOOR))


def _partials(n_tot, c_tot, t_k):
    sp = pr.speciate(n_tot, c_tot, t_k)
    ntot = pr._N_W_PER_KG + sum(sp[s] for s in pr._SOLUTES)
    x = {"H2O": pr._N_W_PER_KG / ntot}
    for s in pr._SOLUTES:
        x[s] = sp[s] / ntot
    lng = pr.activity_ln_gamma(x, t_k)
    return (henry_nh3_pa(t_k) * x["NH3(aq)"] * math.exp(lng["NH3(aq)"]),
            pr.henry_co2_MPa(t_k) * 1.0e6 * x["CO2(aq)"] * math.exp(lng["CO2(aq)"]))


def _node(i, j, k):
    key = (i, j, k)
    if key not in _NODES:
        n_tot, c_tot, t_k = N_FLOOR * GRID_RATIO ** i, C_FLOOR * GRID_RATIO ** j, k * GRID_DT
        p_n, p_c = _partials(n_tot, c_tot, t_k)
        dn, dc = 0.02 * n_tot, 0.02 * c_tot
        p_n2, _ = _partials(n_tot + dn, c_tot, t_k)
        _, p_c2 = _partials(n_tot, c_tot + dc, t_k)
        # ln of: Pa, Pa, and the equilibrium slopes in Pa per unit liquid mole fraction (dx = dm . M_w)
        vals = (p_n, p_c, (p_n2 - p_n) / (dn * pr.M_W), (p_c2 - p_c) / (dc * pr.M_W))
        _NODES[key] = tuple(math.log(max(v, 1e-12)) for v in vals)
    return _NODES[key]


def back_pressure(w, t_c):
    """(p_NH3, p_CO2, dp_NH3/dx_NH3, dp_CO2/dx_CO2) in Pa over an ammonia-water liquid.

    Inside 10-100 C, the speciation grid.  Beyond it the pressures carry on along van 't Hoff at the
    edge's own heat of absorption, ln p = ln p_edge - dH/R (1/T - 1/T_edge), continuous at the edge.
    Held flat instead, a CCW-loss dump that took the liquor to 150 C kept the back-pressure of a
    100 C liquor, so the column went on absorbing 80 % of the loop's gas while it boiled."""
    t_k = t_c + 273.15
    if T_SPEC_LO_K <= t_k <= T_SPEC_HI_K:
        return _grid_pressure(w, t_k)
    t_e = T_SPEC_HI_K if t_k > T_SPEC_HI_K else T_SPEC_LO_K
    edge = _grid_pressure(w, t_e)
    dh_n, dh_c = heat_of_absorption_j_mol(w, t_e - 273.15)
    f_n = math.exp(-dh_n / R_GAS * (1.0 / t_k - 1.0 / t_e))
    f_c = math.exp(-dh_c / R_GAS * (1.0 / t_k - 1.0 / t_e))
    return edge[0] * f_n, edge[1] * f_c, edge[2] * f_n, edge[3] * f_c


def _grid_pressure(w, t_k):
    n_tot, c_tot = molalities(w)
    t_k = min(max(t_k, T_SPEC_LO_K), T_SPEC_HI_K)
    fi, fj, fk = math.log(n_tot / N_FLOOR) / _LN_R, math.log(c_tot / C_FLOOR) / _LN_R, t_k / GRID_DT
    i0, j0, k0 = int(math.floor(fi)), int(math.floor(fj)), int(math.floor(fk))
    di, dj, dk = fi - i0, fj - j0, fk - k0
    out = [0.0, 0.0, 0.0, 0.0]
    for a, wa in ((i0, 1.0 - di), (i0 + 1, di)):
        for b, wb in ((j0, 1.0 - dj), (j0 + 1, dj)):
            for c, wc in ((k0, 1.0 - dk), (k0 + 1, dk)):
                wt = wa * wb * wc
                if wt == 0.0:
                    continue
                node = _node(a, b, c)
                for n in range(4):
                    out[n] += wt * node[n]
    return tuple(math.exp(v) for v in out)


# ---- the column ---------------------------------------------------------------------------------
def solve(gas_kmolh, t_liq_c, t_cpl_c, p_bara, m_755_kgh, w_755, m_cpl_kgh, w_liquor, cal,
          abs_up=None, passes=1):
    """The gas up both beds.  `cal` = {"NH3": c, "CO2": c, "a_w": activity}.

    Returns kmol/h absorbed and vented per species (absorbed H2O < 0: the gas leaves wetter), the
    transfer units, the lower-bed back-pressure and the upper bed's temperature rise.

    The beds couple through the liquid: the lower bed is washed by the CPL leaving the upper bed with
    what it took up.  `abs_up` is that uptake as the lower bed sees it, and the result's `abs_up` is
    the new one.  The engine passes one pass a tick and lags it over the upper bed's liquid residence,
    the time the CPL effluent takes to trickle down.  `passes` > 1 relaxes the two to a steady state,
    which is what the calibration uses."""
    p_pa = p_bara * 1.0e5
    n_in = {k: max(v, 0.0) for k, v in gas_kmolh.items()}
    g_in = sum(n_in.values())
    out = {"absorbed_kmolh": {k: 0.0 for k in n_in}, "vent_kmolh": dict(n_in), "ntu": {},
           "y_star_lo": {"NH3": 0.0, "CO2": 0.0}, "dT_up": 0.0}
    if g_in <= 1e-12:
        # No gas: the CPL leaves the upper bed as clean as it came, so the tear the engine lags
        # toward is zero uptake (a shut HV-322604 must not leave the lower bed washed by old ammonia).
        out["abs_up"] = {"NH3": 0.0, "CO2": 0.0, "dT": 0.0}
        return out
    m_gas = sum(n_in[k] * MW.get(k, 28.0) for k in n_in)

    # The beds are coupled by the liquid: the lower bed is washed by stream 755 AND by the CPL leaving
    # the upper bed with what it took up, so its back-pressure depends on the upper bed's uptake.
    # A few passes settle it (the upper bed moves the lower bed's inlet by well under 1 % at design).
    t_lo_k, t_cpl_k = t_liq_c + 273.15, t_cpl_c + 273.15
    m_lo = m_755_kgh + m_cpl_kgh
    l_lo, l_up = m_lo / MW["H2O"], m_cpl_kgh / MW["H2O"]
    _, _, dpdx_liq_n, dpdx_liq_c = back_pressure(w_liquor, t_liq_c)
    dT = abs_up.get("dT", 0.0) if abs_up else 0.0
    abs_up = {"NH3": abs_up["NH3"], "CO2": abs_up["CO2"]} if abs_up else {"NH3": 0.0, "CO2": 0.0}
    new_up = dict(abs_up)
    for _outer in range(max(int(passes), 1)):
        m_up_nh3, m_up_co2 = abs_up["NH3"] * MW["NH3"], abs_up["CO2"] * MW["CO2"]
        m_mix = m_755_kgh + m_cpl_kgh + m_up_nh3 + m_up_co2
        if m_mix > 1e-9:
            w_lo_in = {k: m_755_kgh * w_755.get(k, 0.0) / m_mix for k in ("NH3", "CO2", "H2O", "Urea")}
            w_lo_in["NH3"] += m_up_nh3 / m_mix
            w_lo_in["CO2"] += m_up_co2 / m_mix
            w_lo_in["H2O"] += m_cpl_kgh / m_mix
        else:
            w_lo_in = dict(w_755)
        p_nlo, p_clo, _, _ = back_pressure(w_lo_in, t_liq_c)

        # ---- lower bed -------------------------------------------------------------------------
        n_mid = dict(n_in)
        for sp in VOLATILE:
            ntu = cal[sp] * onda_ntu(sp, BED_LO, m_lo, m_gas, g_in, t_lo_k, p_pa)
            y_star = min((p_nlo if sp == "NH3" else p_clo) / p_pa, 1.0)
            lam = ((dpdx_liq_n if sp == "NH3" else dpdx_liq_c) / p_pa) * g_in / max(l_lo, 1e-9)
            y_in = n_in.get(sp, 0.0) / g_in
            # a liquid can give up (desorb) no more of a species than it brings into the bed
            liq_in = (m_755_kgh * w_755.get(sp, 0.0)
                      + (m_up_nh3 if sp == "NH3" else m_up_co2)) / MW[sp]
            n_out = n_in.get(sp, 0.0) - (y_in - colburn(y_in, y_star, ntu, lam)) * g_in
            n_mid[sp] = min(max(n_out, 0.0), n_in.get(sp, 0.0) + liq_in)
            out["ntu"]["lo_" + sp] = ntu
            out["y_star_lo"][sp] = y_star
        g_mid = sum(n_mid.values())
        m_mid = sum(n_mid[k] * MW.get(k, 28.0) for k in n_mid)

        # ---- upper bed: CPL enters clean and warms by what it takes up -------------------------
        # The CPL leaves the bed carrying what it absorbed; the equilibrium line's slope is taken
        # over that effluent, so CO2 is only taken up while there is NH3 in the wash to bind it.
        if m_cpl_kgh > 1e-9:
            w_up_out = {"H2O": m_cpl_kgh, "NH3": abs_up["NH3"] * MW["NH3"], "CO2": abs_up["CO2"] * MW["CO2"]}
            m_up_out = sum(w_up_out.values())
            w_up_out = {k: v / m_up_out for k, v in w_up_out.items()}
        else:
            w_up_out = {"H2O": 1.0}
        n_top = dict(n_mid)
        for _inner in range(8):
            t_up_k = t_cpl_k + 0.5 * dT
            _, _, s_n, s_c = back_pressure(w_up_out, t_up_k - 273.15)
            n_top = dict(n_mid)
            for sp in VOLATILE:
                ntu = cal[sp] * onda_ntu(sp, BED_UP, m_cpl_kgh, m_mid, g_mid, t_up_k, p_pa)
                lam = ((s_n if sp == "NH3" else s_c) / p_pa) * g_mid / max(l_up, 1e-9)
                y_in = n_mid.get(sp, 0.0) / max(g_mid, 1e-12)
                n_top[sp] = max(n_mid.get(sp, 0.0) - (y_in - colburn(y_in, 0.0, ntu, lam)) * g_mid, 0.0)
                out["ntu"]["up_" + sp] = ntu
            dh_n, dh_c = heat_of_absorption_j_mol(w_up_out, t_up_k - 273.15)
            q_kw = ((n_mid["NH3"] - n_top["NH3"]) * dh_n
                    + (n_mid["CO2"] - n_top["CO2"]) * dh_c) * 1000.0 / 3.6e6
            cap = (m_cpl_kgh * CP_LIQ + m_mid * CP_GAS) / 3600.0
            dT_new = q_kw / cap if cap > 1e-9 else 0.0
            done = abs(dT_new - dT) < 1e-6
            dT = dT_new
            if done:
                break
        new_up = {sp: n_mid[sp] - n_top[sp] for sp in VOLATILE}
        if passes <= 1 or max(abs(new_up[sp] - abs_up[sp]) for sp in VOLATILE) < 1e-12:
            break
        abs_up = {sp: 0.5 * (abs_up[sp] + new_up[sp]) for sp in VOLATILE}   # relaxed steady state
    out["dT_up"] = dT
    out["abs_up"] = {"NH3": new_up["NH3"], "CO2": new_up["CO2"], "dT": dT}

    # ---- vent water: saturated at the top of the CPL wash ---------------------------------------
    y_w = min(cal["a_w"] * iapws_if97.psat_bara(t_cpl_c) / p_bara, 0.9)
    dry = sum(v for k, v in n_top.items() if k != "H2O")
    n_top["H2O"] = dry * y_w / (1.0 - y_w)

    out["vent_kmolh"] = n_top
    out["absorbed_kmolh"] = {k: n_in.get(k, 0.0) - n_top.get(k, 0.0) for k in set(n_in) | set(n_top)}
    return out


def calibrate(gas_kmolh, t_liq_c, t_cpl_c, p_bara, m_755_kgh, w_755, m_cpl_kgh, w_liquor,
              target_abs_kmolh):
    """c_NH3, c_CO2 and the vent water activity that make the design uptake `target_abs_kmolh`."""
    cal = {"NH3": 1.0, "CO2": 1.0, "a_w": 0.88}

    def absorbed(c):
        return solve(gas_kmolh, t_liq_c, t_cpl_c, p_bara, m_755_kgh, w_755, m_cpl_kgh, w_liquor,
                     c, passes=200)["absorbed_kmolh"]

    for _ in range(3):                          # the two species couple weakly through the bed heat
        for sp in VOLATILE:
            lo, hi = 1e-4, 1e3
            for _ in range(200):
                mid = math.sqrt(lo * hi)
                c = dict(cal)
                c[sp] = mid
                if absorbed(c)[sp] < target_abs_kmolh[sp]:
                    lo = mid
                else:
                    hi = mid
                if hi / lo - 1.0 < 1e-15:
                    break
            cal[sp] = math.sqrt(lo * hi)
    base = solve(gas_kmolh, t_liq_c, t_cpl_c, p_bara, m_755_kgh, w_755, m_cpl_kgh, w_liquor, cal,
                 passes=200)
    dry = sum(v for k, v in base["vent_kmolh"].items() if k != "H2O")
    vent_w = gas_kmolh.get("H2O", 0.0) - target_abs_kmolh["H2O"]
    cal["a_w"] = (vent_w / (dry + vent_w)) * p_bara / iapws_if97.psat_bara(t_cpl_c)
    cal["abs_up"] = dict(base["abs_up"])            # the steady bed-coupling tear, to seed the lag
    return cal
