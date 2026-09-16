"""Real-gas isenthalpic letdown on the SRK equation of state (report D-4).

HV-322604 lets the 322E003 off-gas down from the synthesis loop (140.7 bar a) to the LP absorber
322C001 (4.0 bar a).  The engine carried that as a constant Joule-Thomson coefficient,

    T_out = T_in - 0.55 C/bar . dP          ->  114 - 0.55 . 136.7 = 38.8 C at design,

a number typical of an NH3/CO2-rich gas.  PFD stream 204 is not that gas: it is 68.8 mol% N2, 11.4 %
O2, 5.9 % CH4, 3.1 % H2 and only 8.3 % NH3 / 2.2 % CO2, and a constant coefficient cannot follow
either the composition or the inlet state anyway.  A letdown valve is isenthalpic, so

    h_ig(T_out) + h_res(T_out, P_out) = h_ig(T_in) + h_res(T_in, P_in)

with h_ig from `gap_g6_h0_enthalpy` (NIST-JANAF gas Cp, the datum every stream enthalpy in the engine
is published on) and the residual enthalpy from the SRK cubic already in `props_nh3co2h2o` (same
critical constants, same k_ij = 0 van der Waals mixing):

    h_res = R.T.(Z - 1) + (T.da_m/dT - a_m)/b_m . ln((Z + B)/Z)

On the PFD 204 composition that gives 94.8 C at the 322C001 inlet -- a mean coefficient of 0.14 K/bar,
a quarter of the constant, which is what a gas that is mostly nitrogen does.  No plant instrument sits
downstream of HV-322604, so there is no measurement to anchor to; the letdown is a first-principles
result.

SCOPE.  Single-phase gas.  At the design outlet the NH3 and water partial pressures (0.33 and 0.01 bar)
are far from saturation, so no liquid forms; `condensing` flags an outlet where water would, because
this routine does not do the two-phase flash that state would need.
"""
import math

import gap_g6_h0_enthalpy as h0
import iapws_if97
import props_nh3co2h2o as props

R = props.R
_GAS = h0._phase_map("vapour")
SPECIES = tuple(k for k in props.SRK_CRIT)              # H2O NH3 CO2 N2 O2 CH4 H2


def _mix(y: dict, t_k: float):
    """SRK a_m(T), b_m for mole fractions y (k_ij = 0)."""
    s = 0.0
    b = 0.0
    for k, v in y.items():
        a_i, b_i = props._srk_ai_bi(k, t_k)
        s += v * math.sqrt(a_i)
        b += v * b_i
    return s * s, b


def h_residual(y: dict, t_k: float, p_pa: float) -> float:
    """SRK residual molar enthalpy [J/mol] of a vapour mixture."""
    a_m, b_m = _mix(y, t_k)
    big_a = a_m * p_pa / (R * R * t_k * t_k)
    big_b = b_m * p_pa / (R * t_k)
    z = props._cubic_largest_root(1.0, -1.0, big_a - big_b - big_b * big_b, -big_a * big_b)
    h = 1.0e-3
    da_dt = (_mix(y, t_k + h)[0] - _mix(y, t_k - h)[0]) / (2.0 * h)
    return R * t_k * (z - 1.0) + (t_k * da_dt - a_m) / b_m * math.log((z + big_b) / z)


def h_molar(y: dict, t_k: float, p_pa: float) -> float:
    """Real-gas molar enthalpy [J/mol] on the elements-at-298.15 K datum."""
    return sum(v * h0.h_species(k, _GAS[k], t_k) for k, v in y.items()) + h_residual(y, t_k, p_pa)


def mole_fractions(comp_kmolh: dict) -> dict:
    n = {k: max(comp_kmolh.get(k, 0.0), 0.0) for k in SPECIES}
    tot = sum(n.values())
    return {k: v / tot for k, v in n.items() if v > 0.0} if tot > 0.0 else {}


def isenthalpic_letdown(comp_kmolh: dict, t_in_c: float, p_in_bara: float, p_out_bara: float) -> dict:
    """Outlet temperature of an adiabatic, isenthalpic letdown of a single-phase gas.

    Illinois regula falsi on T_out over (T_in - 150 K, T_in + 20 K): the lower end is far below any
    letdown this plant makes, the upper end covers the reverse (heating) effect of a hydrogen-rich
    gas.  Deterministic in its operands."""
    y = mole_fractions(comp_kmolh)
    if not y or p_out_bara >= p_in_bara:
        return {"t_out_c": t_in_c, "mu_jt_k_bar": 0.0, "condensing": False}
    t_in = t_in_c + 273.15
    h_in = h_molar(y, t_in, p_in_bara * 1.0e5)

    def f(t_k):
        return h_molar(y, t_k, p_out_bara * 1.0e5) - h_in

    lo, hi = t_in - 150.0, t_in + 20.0
    f_lo, f_hi = f(lo), f(hi)
    if f_lo >= 0.0:
        t_out = lo
    elif f_hi <= 0.0:
        t_out = hi
    else:
        side = 0
        t_out = t_in
        for _ in range(60):
            t_out = (lo * f_hi - hi * f_lo) / (f_hi - f_lo)
            r = f(t_out)
            if abs(r) <= 1.0e-6 or hi - lo <= 1.0e-9:
                break
            if r < 0.0:
                lo, f_lo = t_out, r
                if side == 1:
                    f_hi *= 0.5
                side = 1
            else:
                hi, f_hi = t_out, r
                if side == -1:
                    f_lo *= 0.5
                side = -1
    t_out_c = t_out - 273.15
    p_h2o = y.get("H2O", 0.0) * p_out_bara
    return {"t_out_c": t_out_c,
            "mu_jt_k_bar": (t_in_c - t_out_c) / (p_in_bara - p_out_bara),
            "condensing": p_h2o >= iapws_if97.psat_bara(max(t_out_c, 0.01))}
