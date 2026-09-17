"""Saturated-vent vacuum condenser -- the 324 vacuum train's four surface condensers.

Reports A-13, B-9 and B-13.  What this replaces carried three stand-ins for one physical fact:

  * the gas outlet temperature was the design outlet plus whatever the inlet moved (A-13, a frozen
    approach), so cooling water could not change it;
  * duty became condensate through ONE design "effective enthalpy" per exchanger (B-9), so an NH3-rich
    and a water-rich vapour condensed at the same kJ/kg;
  * non-condensable gas derated UA by a linear ratio (B-13), and the two pressure loops that actually
    set PT-324201 and PT-324204 did not use the node at all -- they subtracted the DESIGN condensate
    as a constant, so the condenser could not respond to its own shell pressure.

THE PHYSICS.  Every PFD vent row off these condensers sits at water saturation at its own
temperature and pressure: stream 706 is 29.4 mol% H2O at 45 C / 0.33 bar a (p_H2O 0.097 against
psat 0.096), 712 is 57.9 % at 40 C / 0.131 (0.076 against 0.074), 722 is 15.2 % at 55 C / 1.0 (0.152
against 0.157).  That is what a surface condenser does: the gas leaving the cold end is the inert gas
plus whatever vapour it can hold at that end's temperature and the shell pressure.  So

    y_c(T_v, P) = Y_des . (P_des / P) . psat_w(T_v) / psat_w(T_v,des)          condensable mole fraction
    n_vent,c    = n_inert . y_c / (1 - y_c)          split among H2O / NH3 / CO2 as the PFD vent row

and the vent grows without bound -- until it is the whole inlet -- as the shell pressure falls towards
the vapour pressure at the cold end.

NH3 and CO2 used to ride WATER's saturation line with the PFD vent's fixed split, because the
engine's activity grid stops at 80 C and these cold ends are 40-55 C.  `packed_absorber.back_pressure`
covers 10-100 C (Extended UNIQUAC speciation x Rumpf-Maurer Henry constants), so each now carries its
own partial pressure over the condensate the exchanger is making, as a departure from design:

    p_w = Y_des s_w P_des . psat_w(T_v) / psat_w(T_v,des)
    p_k = Y_des s_k P_des . p*_k(w_cond, T_v) / p*_k(w_cond,des, T_v,des)            k = NH3, CO2
    y_c = (p_w + p_NH3 + p_CO2) / P,     n_vent,k = n_inert . y_c / (1 - y_c) . p_k / sum p

Unanchored, the speciation over PFD condensate 719 at 45 C gives p_NH3 0.054 and p_CO2 0.0085 bar
against PFD 706's 0.059 and 0.013.  The condensate is taken at the inlet's condensable composition,
which is what it is while the vent carries a few per cent of the condensables.  An ammonia-rich inlet
then raises p_NH3 more than in proportion, because less of it is bound to CO2.

The cold-end temperature T_v is not a constant.  It is where the energy the vapour gives up equals
what the surface can pass to the cooling water:

    Q_bal(T_v) = H_gas(inlet, T_in) - H_gas(vent, T_v) - H_liq(condensate, T_v)      (B-9)
    Q_UA(T_v)  = UA . LMTD(T_in, T_v ; T_cw,in, T_cw,in + Q/(m_cw.cp))                (A-13)

H is `gap_g6_h0_enthalpy`'s elements-at-298.15 K datum (NIST-JANAF vapour, Helgeson aqueous), so the
condensation heat is per species: 43.2 kJ/mol for water at 45 C, 33.6 for NH3, 16.3 for CO2.  Checked
on the PFD's own 703 / 706 / 719 rows it gives 18 019 kW against the 18 460 kW the cooling water
carries (-2.4 %, the H0 tier's missing mixing and carbamate heat).  UA is back-solved per exchanger
from that same balance at the PFD design point, so the design is reproduced by construction.

ANCHORING.  `vent_kgh()` returns the PFD vent times [model vent live / model vent at design]; the
design solve is the same deterministic function on the same operands, so at the design state the
bracket is exactly 1.0 and every downstream anchor, the boot pin included, is untouched.
"""
import math

import gap_g6_h0_enthalpy as h0
import iapws_if97
import packed_absorber

CONDENSABLE = ("H2O", "NH3", "CO2")
INERT = ("N2", "O2")
CARRIED = ("Urea",)                     # entrained liquor: liquid on both sides of the exchanger
SPECIES = CONDENSABLE + INERT + CARRIED
MW = {k: h0.MOLAR_MASS[k] for k in SPECIES}
_Y_MAX = 1.0 - 1.0e-9

_GAS = h0._phase_map("vapour")
_LIQ = h0._phase_map("liquid")


#  The condenser solve evaluates each species' enthalpy at a dozen trial temperatures per tick, and the
#  aqueous ones are Helgeson integrals.  They are read off a lazily filled 0.05 K grid instead, linear
#  between nodes: a pure function of T (so the design solve stays reproducible), and with Cp varying by
#  well under 1 J/mol/K per K the interpolation error is below 1e-4 J/mol.
_H_STEP_K = 0.05
_H_GRID = {}


def _h_node(k: str, phase: str, i: int) -> float:
    key = (k, phase, i)
    v = _H_GRID.get(key)
    if v is None:
        v = h0.h_species(k, phase, i * _H_STEP_K)
        _H_GRID[key] = v
    return v


def _h(k: str, phase: str, t_c: float) -> float:
    x = (t_c + 273.15) / _H_STEP_K
    i = math.floor(x)
    f = x - i
    h_lo = _h_node(k, phase, i)
    return h_lo + f * (_h_node(k, phase, i + 1) - h_lo)             # J/mol


def _h_gas(k: str, t_c: float) -> float:
    return _h(k, _GAS[k], t_c)


def _h_liq(k: str, t_c: float) -> float:
    return _h(k, _LIQ[k], t_c)


def _lmtd(hot_in, hot_out, cold_in, cold_out):
    d1, d2 = hot_in - cold_out, hot_out - cold_in
    if d1 <= 0.0 or d2 <= 0.0:
        return 0.0
    if abs(d1 - d2) <= 1.0e-12:
        return 0.5 * (d1 + d2)
    return (d1 - d2) / math.log(d1 / d2)


def moles_from_mole_pct(total_kmolh: float, pct: dict) -> dict:
    """PFD vapour rows are MOLE per cent (see main.py, the F-8 unit convention)."""
    tot = sum(pct.get(k, 0.0) for k in SPECIES)
    return {k: total_kmolh * pct.get(k, 0.0) / tot for k in SPECIES}


def condensate_fractions(n_in: dict) -> dict:
    """Mass fractions of what a condenser makes, taken at its inlet's condensable composition."""
    m = {k: max(n_in.get(k, 0.0), 0.0) * MW[k] for k in CONDENSABLE + CARRIED}
    tot = sum(m.values())
    return {k: v / tot for k, v in m.items()} if tot > 0.0 else {}


BP_HALF_BAND_K = 2.0


def bp_bracket(w_cond: dict, t_c: float) -> tuple:
    """The speciated back-pressure at t_c and at +/- BP_HALF_BAND_K, to read inside a solver loop.

    `packed_absorber.back_pressure` interpolates a grid whose nodes cost three Extended-UNIQUAC
    speciations each (~10 ms) the first time a run reaches them.  Taking it at every trial temperature
    of a regula falsi walked that grid over the whole 15 K bracket and met new nodes all the way:
    ~5 speciations a tick off design (Phase 5q's cost note).  Three anchors that move only as the cold
    end itself moves are nodes the run almost always holds already."""
    return (t_c,
            packed_absorber.back_pressure(w_cond, t_c - BP_HALF_BAND_K),
            packed_absorber.back_pressure(w_cond, t_c),
            packed_absorber.back_pressure(w_cond, t_c + BP_HALF_BAND_K))


def bp_at(bracket: tuple, t_c: float) -> tuple:
    """A bracket read at a temperature: ln-linear through its anchors, same slope outside them.

    These partial pressures are very nearly exponential in T, so over 2 K the interpolation is good to
    a few parts in 1e5, and at the centre it returns that anchor itself -- which is what keeps the
    design point bit-exact when the bracket is centred on the design cold end.  Outside the band the
    same slope carries on: a solver that walks out of the band gets the trend, not a frozen value."""
    t0, lo, mid, hi = bracket
    if t_c == t0:
        return mid
    if t_c > t0:
        f, a, b = (t_c - t0) / BP_HALF_BAND_K, mid, hi
    else:
        f, a, b = (t0 - t_c) / BP_HALF_BAND_K, mid, lo
    return tuple(a[i] * (b[i] / a[i]) ** f for i in range(len(a)))


def vent_moles(spec: dict, p_bara: float, t_v_c: float, n_in: dict, bp: tuple = None) -> dict:
    """Gas leaving the cold end: every inert, plus the condensables it holds saturated at T_v and P.

    A condenser spec (one carrying `bp_des`) gives NH3 and CO2 their own partial pressures over the
    condensate; a bare saturated-gas spec keeps the fixed split on water's line.  `bp` is that
    back-pressure when the caller has already paid for it -- a pressure loop holding T_v, or a falsi
    reading its bracket; without one it is taken here at this call's own temperature."""
    n_i = sum(n_in.get(k, 0.0) for k in INERT)
    y = spec["y_des"] * (spec["p_des"] / max(p_bara, 1.0e-9)) \
        * (iapws_if97.psat_bara(t_v_c) / spec["psat_v_des"])
    split = spec["split"]
    w_cond = condensate_fractions(n_in) if "bp_des" in spec else {}
    if w_cond:
        if bp is None:
            bp = packed_absorber.back_pressure(w_cond, t_v_c)
        rel = {"H2O": y * split["H2O"],
               "NH3": spec["y_des"] * split["NH3"] * (spec["p_des"] / max(p_bara, 1.0e-9))
               * (bp[0] / spec["bp_des"][0]),
               "CO2": spec["y_des"] * split["CO2"] * (spec["p_des"] / max(p_bara, 1.0e-9))
               * (bp[1] / spec["bp_des"][1])}
        y = sum(rel.values())
        split = {k: rel[k] / y for k in CONDENSABLE} if y > 0.0 else split
    y = min(max(y, 0.0), _Y_MAX)
    n_c = n_i * y / (1.0 - y)
    vent = {k: min(n_c * split[k], n_in.get(k, 0.0)) for k in CONDENSABLE}
    for k in INERT:
        vent[k] = n_in.get(k, 0.0)
    vent["Urea"] = 0.0
    return vent


def _q_balance(spec, p_bara, t_v, n_in, h_in, bracket=None):
    vent = vent_moles(spec, p_bara, t_v, n_in, bp_at(bracket, t_v) if bracket else None)
    q = h_in
    for k in SPECIES:
        nv = vent.get(k, 0.0)
        nc = n_in.get(k, 0.0) - nv
        if nv:
            q -= nv * _h_gas(k, t_v)
        if nc:
            q -= nc * _h_liq(k, t_v)
    return q * 1000.0 / 3600.0 / 1000.0, vent                        # kW


def _inlet_enthalpy(n_in: dict, t_in: float) -> float:
    """kmol/h . J/mol, vapour species as gas and entrained liquor as liquid."""
    return sum(n * (_h_liq(k, t_in) if k in CARRIED else _h_gas(k, t_in))
               for k, n in n_in.items() if n)


def solve(spec: dict, p_bara: float, n_in: dict, t_in_c: float,
          cw_flow_kgh: float, cw_in_c: float, ua_kw_k: float = None,
          t_v_prev: float = None) -> dict:
    """Cold-end temperature, vent and condensate of one condenser at a live shell pressure.

    Regula falsi (Illinois) on R(T_v) = Q_bal - UA.LMTD over (T_cw,in, T_in): R > 0 at the cold end,
    where the LMTD vanishes, and R < 0 at the hot end, where the vent holds everything.  Deterministic
    in its operands, which is what lets the anchored vent be bit-exact at design."""
    ua = spec["ua_kw_k"] if ua_kw_k is None else ua_kw_k
    h_in = _inlet_enthalpy(n_in, t_in_c)
    cp = spec["cw_cp"]
    #  One back-pressure bracket for the whole falsi, centred on the cold end this condenser last
    #  settled at -- the design outlet on the first tick, which is what keeps the design point exact.
    #  If the falsi answers outside the band the bracket is re-centred on that answer and the solve
    #  repeats, at most four times; measured against the per-trial evaluation it replaces, the cold
    #  end agrees to 2e-5 K and the vent to 4e-4 of itself.
    w_cond = condensate_fractions(n_in) if "bp_des" in spec else {}
    bracket = bp_bracket(w_cond, spec["t_v_des"] if t_v_prev is None else t_v_prev) if w_cond else None
    if cw_flow_kgh <= 0.0 or ua <= 0.0 or t_in_c <= cw_in_c:
        vent = {k: n_in.get(k, 0.0) for k in CONDENSABLE + INERT}
        vent["Urea"] = 0.0
        return _pack(spec, n_in, vent, t_in_c, 0.0, cw_in_c, cw_in_c, 0.0, cw_flow_kgh, t_in_c)

    def resid(t_v):
        q, vent = _q_balance(spec, p_bara, t_v, n_in, h_in, bracket)
        cw_out = cw_in_c + max(q, 0.0) * 3600.0 / (cw_flow_kgh * cp)
        return q - ua * _lmtd(t_in_c, t_v, cw_in_c, cw_out), q, vent, cw_out

    for _attempt in range(4):
        lo, hi = cw_in_c + 1.0e-6, t_in_c - 1.0e-6
        r_lo = resid(lo)[0]
        r_hi = resid(hi)[0]
        if r_lo <= 0.0:                 # the surface cools the vent to the water inlet
            t_v = lo
        elif r_hi >= 0.0:
            t_v = hi
        else:
            side = 0
            t_v = lo
            for _ in range(60):
                t_v = (lo * r_hi - hi * r_lo) / (r_hi - r_lo)
                r = resid(t_v)[0]
                if abs(r) <= 1.0e-6 or hi - lo <= 1.0e-8:       # kW, K
                    break
                if r > 0.0:
                    lo, r_lo = t_v, r
                    if side == 1:
                        r_hi *= 0.5
                    side = 1
                else:
                    hi, r_hi = t_v, r
                    if side == -1:
                        r_lo *= 0.5
                    side = -1
        if bracket is None or abs(t_v - bracket[0]) <= BP_HALF_BAND_K:
            break
        bracket = bp_bracket(w_cond, t_v)                        # the cold end left the band
    r, q, vent, cw_out = resid(t_v)
    return _pack(spec, n_in, vent, t_v, q, cw_in_c, cw_out, ua * _lmtd(t_in_c, t_v, cw_in_c, cw_out),
                 cw_flow_kgh, t_in_c)


def _pack(spec, n_in, vent, t_v, q, cw_in, cw_out, q_ua, cw_flow, t_in):
    vent_kgh = sum(vent.get(k, 0.0) * MW[k] for k in SPECIES)
    in_kgh = sum(n_in.get(k, 0.0) * MW[k] for k in SPECIES)
    return {"t_vent_c": t_v, "q_kw": q, "q_ua_kw": q_ua, "cw_in_c": cw_in, "cw_out_c": cw_out,
            "cw_flow_kgh": cw_flow, "vent_kmolh": vent, "vent_model_kgh": vent_kgh,
            "inlet_model_kgh": in_kgh, "condensate_model_kgh": in_kgh - vent_kgh,
            "lmtd_k": _lmtd(t_in, t_v, cw_in, cw_out) if q else 0.0}


def design_spec(tag: str, p_des: float, n_in_des: dict, t_in_des: float, vent_row: dict,
                t_v_des: float, cw_flow_kgh: float, cw_in_c: float, cw_cp: float,
                inlet_kgh_pfd: float, vent_kgh_pfd: float) -> dict:
    """Anchor one condenser on its PFD rows; back-solve UA from the H0 balance at design."""
    y_c = sum(vent_row[k] for k in CONDENSABLE)
    spec = {"tag": tag, "p_des": p_des, "t_in_des": t_in_des, "t_v_des": t_v_des,
            "y_des": y_c / sum(vent_row[k] for k in CONDENSABLE + INERT),
            "split": {k: vent_row[k] / y_c for k in CONDENSABLE},
            "psat_v_des": iapws_if97.psat_bara(t_v_des),
            "cw_flow_kgh": cw_flow_kgh, "cw_in_c": cw_in_c, "cw_cp": cw_cp,
            "n_in_des": dict(n_in_des), "inlet_kgh": inlet_kgh_pfd, "vent_kgh": vent_kgh_pfd}
    spec["bp_des"] = packed_absorber.back_pressure(condensate_fractions(n_in_des), t_v_des)
    h_in = _inlet_enthalpy(n_in_des, t_in_des)
    q_des, _ = _q_balance(spec, p_des, t_v_des, n_in_des, h_in)
    cw_out = cw_in_c + q_des * 3600.0 / (cw_flow_kgh * cw_cp)
    spec["ua_kw_k"] = q_des / _lmtd(t_in_des, t_v_des, cw_in_c, cw_out)
    spec["q_des_kw"] = q_des
    des = solve(spec, p_des, n_in_des, t_in_des, cw_flow_kgh, cw_in_c)
    spec["vent_model_des_kgh"] = des["vent_model_kgh"]
    spec["t_v_solved_des"] = des["t_vent_c"]
    return spec


def saturated_gas_spec(vent_row: dict, p_des: float, t_des: float) -> dict:
    """The saturation part of a condenser spec, for any gas outlet that leaves in equilibrium with a
    cold liquid: a scrubber or absorber top as much as a condenser's cold end."""
    y_c = sum(vent_row.get(k, 0.0) for k in CONDENSABLE)
    return {"p_des": p_des, "t_v_des": t_des, "psat_v_des": iapws_if97.psat_bara(t_des),
            "y_des": y_c / sum(vent_row.get(k, 0.0) for k in CONDENSABLE + INERT),
            "split": {k: vent_row.get(k, 0.0) / y_c for k in CONDENSABLE}}


def vent_mass_kgh(vent: dict) -> float:
    return sum(vent.get(k, 0.0) * MW[k] for k in SPECIES)


def vent_kgh(spec: dict, result: dict) -> float:
    """PFD vent anchored on the model: bit-exact PFD value at the design state."""
    return spec["vent_kgh"] * (result["vent_model_kgh"] / spec["vent_model_des_kgh"])


def condensate_back_pressure(n_in: dict, t_v_c: float):
    """The speciated back-pressure over what a condenser is condensing, or None if it has none."""
    w_cond = condensate_fractions(n_in)
    return packed_absorber.back_pressure(w_cond, t_v_c) if w_cond else None


def vent_kgh_at(spec: dict, p_bara: float, t_v_c: float, n_in: dict, bp: tuple = None) -> float:
    """The anchored vent at a trial shell pressure with T_v held -- the cheap inner evaluation the
    pressure loops iterate on, because T_v moves on the exchanger's thermal time scale, not P's.

    Those loops hold T_v and the composition, so the back-pressure is the same at every trial
    pressure: they take it once (`packed_absorber.back_pressure`) and pass it in."""
    v = vent_moles(spec, p_bara, t_v_c, n_in, bp)
    return spec["vent_kgh"] * (sum(v[k] * MW[k] for k in SPECIES) / spec["vent_model_des_kgh"])
