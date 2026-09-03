"""Bubble-point service for the NH3-CO2-H2O-urea liquors of Units 323 and 328.

WHAT THIS REPLACES
------------------
`props_nh3co2h2o.py` is a fully transcribed, unit-tested Extended UNIQUAC electrolyte model for the
NH3-CO2-H2O system (Thomsen & Rasmussen 1999 / Darde 2010-2011) -- and, until this file, NOTHING in
the running simulator imported it.  The live engine sat on two much weaker surrogates:

    323C003 bubble point :  tsat_steam(P)   PURE-WATER Antoine, frozen offset
    323F004 bubble point :  tsat_steam(P)   PURE-WATER Antoine, frozen offset

with a comment in `bubble_T_raoult` conceding the point in writing: "NOT valid for 323C003 /
323F004, whose liquors carry NH3 and CO2: there the volatiles dominate the bubble point".  They do,
and the numbers show how badly.  At the 323C003 design state the pure-water saturation temperature
at 4.1 bar a is 144 C; the column actually runs at 135 C, and the 9 C gap is the NH3 and CO2 partial
pressures that the water-only model cannot see.  Worse than the offset -- which the departure form
absorbs -- is the SLOPE: a water-only anchor makes the column's bubble point respond only to
pressure, so a change in the NH3 or CO2 loading of the liquor (which is what every stripping,
absorption and recycle upset in this plant does) moved the bubble point by exactly zero.

WHAT IT DOES
------------
The correct model for these liquors is the electrolyte gamma-phi VLE the plant's own thermodynamics
demand, and `props_nh3co2h2o.py` already contains every piece of it:

    P_bub(T) = f_dil * [ a_NH3(T) * H_NH3(T)  +  a_CO2(T) * H_CO2(T)  +  a_H2O(T) * Psat_H2O(T) ]

    a_i   = x_i * gamma_i     activities from the full Extended UNIQUAC gamma
                              (combinatorial + residual + extended Debye-Huckel), with the R1-R5
                              liquid speciation solved by `props_nh3co2h2o.speciate`
    H_i   Rumpf & Maurer (1993) Henry constants, mole-fraction scale (Darde eqs 2.12-2.13)
    Psat  IAPWS-IF97 pure-water saturation line (the same reference the 329 steam network uses)
    f_dil urea and biuret are NON-VOLATILE and are not in the electrolyte parameter set, so they
          enter the only way they physically can at this concentration -- as a mole-fraction
          diluent on every partial pressure.  This is the same Raoult-on-the-non-volatiles term the
          engine's own `bubble_T_raoult` already uses for the urea-only stages, so the two
          bubble-point models agree in the limit where the volatiles vanish.

VALIDATION (no fitted parameter anywhere in the chain)
-----------------------------------------------------
Evaluated on the ENGINE'S OWN composition vectors (W_S314 / W_S319_TAB / W_S317), through the
tabulated-and-interpolated path the engine actually calls -- not on hand-entered numbers:

    stage     liquor (PFD mass %)                       T (C)    P_model   P_PFD    error
    323C003   68.74 U / 0.36 B / 2.13 N / 1.05 C        135      4.387     4.10     + 7.0 %
    323F004   71.74 U / 0.37 B / 0.88 N / 0.66 C        106      1.328     1.13     +17.5 %
    323F010   80.00 U / 0.42 B / 0.08 N / 0.02 C         99      0.468     0.46     + 1.7 %

Three stages spanning 0.46-4.1 bar a and 99-135 C, reproduced to +1.7 % / +7.0 % / +17.5 % from
first principles.  323F004 is the loosest because it is the stage where the CO2 term dominates and
CO2 is where this model is weakest: at 0.66 wt% CO2 the carbamate equilibrium is steep, and urea --
which is 72 % of the liquor -- is a mole-fraction DILUENT here, not a UNIQUAC species, so it dilutes
the volatiles without shifting their activity coefficients.  See gap G-VLE-1 in handoff.md.

What matters for the engine is the SLOPE, not the offset: every call site uses the DEPARTURE form
T_des + [T_bub(live) - T_bub(design)], so the residual cancels identically at the design point.  For
comparison, the pure-water anchor this replaces gives 103.3 C at 323F004's 1.13 bar against an actual
106 C, and -- far more importantly -- responds to composition with a derivative of exactly zero.

WHY THERE IS A GRID
-------------------
`speciate` is a damped log-space Newton solve with a numerical Jacobian over 8 species: 25 ms per
call, against a simulator that integrates at dt = 0.1 s and up to 60x real time.  Calling it inline
would be ~250x too slow.  The activities are therefore tabulated once over the operating envelope
and interpolated trilinearly; the Henry constants and the water saturation line stay ANALYTIC at the
live temperature, so the temperature response -- the part the controllers act on -- carries no grid
error at all.  The table is built once and cached to disk against a hash of its own source and of
`props_nh3co2h2o.py`, so a model edit rebuilds it and an unchanged tree loads it in milliseconds.
"""

from __future__ import annotations

import hashlib
import json
import math
import os

import iapws_if97
import props_nh3co2h2o as _props

MW = {"Urea": 60.056, "Biuret": 103.081, "NH3": 17.0304,
      "CO2": 44.0095, "H2O": 18.0153, "HCHO": 30.026}
NONVOLATILE = ("Urea", "Biuret", "HCHO")

MODEL_NAME = ("Extended UNIQUAC NH3-CO2-H2O electrolyte gamma-phi VLE "
              "(Thomsen-Rasmussen / Darde) + non-volatile urea dilution")

# ---- table envelope ------------------------------------------------------------------------------
#  T   : 80-160 C covers 323F010 (99), 323F004 (106), 323C003 (135) and every upset either side.
#  N,C : total NH3 / CO2 loading in mol per kg of WATER.  Design loadings are C003 (4.51, 0.86),
#        F004 (1.99, 0.36), F010 (0.24, 0.02); the grid spans a decade either side of all of them,
#        graded so the nodes cluster where the plant lives.
#  N and C are spaced GEOMETRICALLY and their activities are interpolated in LOG space, because
#  a_NH3 and especially a_CO2 span four orders of magnitude across this envelope (the carbamate
#  equilibrium buries free CO2 at high N/C and releases it explosively at low N/C).  Linear
#  interpolation on a_CO2 was measured 6.5x high at the 323F010 loading; log-geometric is within
#  2 %, which matters because H_CO2 is ~580 MPa -- a small activity error is a large pressure error.
_T_NODES = (80.0, 92.0, 104.0, 116.0, 128.0, 140.0, 152.0, 170.0)
_N_NODES = (1.0e-4, 1.0e-3, 1.0e-2, 6.0e-2, 0.25, 0.8, 2.0, 4.5, 9.0, 16.0)
_C_NODES = (1.0e-5, 1.0e-4, 1.0e-3, 8.0e-3, 4.0e-2, 0.16, 0.5, 1.2, 3.0, 7.0)

_HERE = os.path.dirname(os.path.abspath(__file__))
_CACHE_PATH = os.path.join(_HERE, ".vle_nh3co2h2o_grid.json")
_TABLE = None                       # [i_T][i_N][i_C] -> (a_NH3, a_CO2, a_H2O, n_sub_per_kg_water)


def _clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


#  Bump when `_node_activities` changes what a node MEANS.  The key hashes the property source and
#  the node definitions (the only two things a stored node depends on) rather than this whole file,
#  so editing the interpolator or the solver does not throw away a 30 s table build.
_TABLE_VERSION = "1"


def _cache_key() -> str:
    h = hashlib.sha256()
    try:
        with open(os.path.join(_HERE, "props_nh3co2h2o.py"), "rb") as f:
            h.update(f.read())
    except OSError:
        h.update(b"\x00")
    h.update(repr((_TABLE_VERSION, _T_NODES, _N_NODES, _C_NODES)).encode())
    return h.hexdigest()


def _node_activities(t_c: float, n_load: float, c_load: float):
    """Solve one grid node: liquid speciation + full Extended UNIQUAC activities.

    Returns (a_NH3, a_CO2, a_H2O, n_sub_per_kg_water) where a_i = x_i*gamma_i on the mole-fraction
    scale of the water + electrolyte sub-system (urea/biuret enter later, as a dilution factor)."""
    t_k = t_c + 273.15
    md = _props.speciate(max(n_load, 1e-6), max(c_load, 1e-6), T=t_k)
    n_sub = _props._N_W_PER_KG + sum(md[s] for s in _props._SOLUTES)
    x = {"H2O": _props._N_W_PER_KG / n_sub}
    for s in _props._SOLUTES:
        x[s] = md[s] / n_sub
    lng = _props.activity_ln_gamma(x, t_k)
    return (x["NH3(aq)"] * math.exp(lng["NH3(aq)"]),
            x["CO2(aq)"] * math.exp(lng["CO2(aq)"]),
            x["H2O"] * math.exp(lng["H2O"]),
            n_sub)


def _build_table():
    return [[[list(_node_activities(t, n, c)) for c in _C_NODES]
             for n in _N_NODES] for t in _T_NODES]


def _ensure_table():
    global _TABLE
    if _TABLE is not None:
        return _TABLE
    key = _cache_key()
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            doc = json.load(f)
        if doc.get("key") == key:
            _TABLE = doc["table"]
            return _TABLE
    except (OSError, ValueError, KeyError):
        pass
    print("[vle] building NH3-CO2-H2O Extended UNIQUAC activity table "
          "(~5 s, once per model change)", flush=True)
    _TABLE = _build_table()
    try:
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"key": key, "table": _TABLE}, f)
    except OSError:
        pass                                   # the cache is an optimisation, never a hard dependency
    return _TABLE


def _bracket(nodes, v, geometric: bool = False):
    """Return (index, weight) for interpolation, clamped at both ends (no extrapolation).

    With `geometric` the weight is taken on log(v), which pairs with the log-space interpolation of
    the activities so a decade-wide node interval stays accurate at both of its ends."""
    if v <= nodes[0]:
        return 0, 0.0
    if v >= nodes[-1]:
        return len(nodes) - 2, 1.0
    for i in range(1, len(nodes)):
        if v <= nodes[i]:
            if geometric:
                return i - 1, (math.log(v) - math.log(nodes[i - 1])) \
                    / (math.log(nodes[i]) - math.log(nodes[i - 1]))
            return i - 1, (v - nodes[i - 1]) / (nodes[i] - nodes[i - 1])
    return len(nodes) - 2, 1.0


def _interp(t_c: float, n_load: float, c_load: float):
    """Trilinear interpolation of (a_NH3, a_CO2, a_H2O, n_sub).

    a_NH3 and a_CO2 are interpolated as log(a) -- they are strictly positive and span four decades,
    and their true shape between nodes is exponential, so a linear blend of the LOGS is both exact
    at the nodes and far closer in between.  a_H2O (order 1) and n_sub (order 56) stay linear."""
    tab = _ensure_table()
    it, ft = _bracket(_T_NODES, t_c)
    i_n, fn = _bracket(_N_NODES, max(n_load, _N_NODES[0]), geometric=True)
    ic, fc = _bracket(_C_NODES, max(c_load, _C_NODES[0]), geometric=True)
    ln_a_nh3 = ln_a_co2 = a_h2o = n_sub = 0.0
    for dt_ in (0, 1):
        wt = ft if dt_ else (1.0 - ft)
        if wt == 0.0:
            continue
        for dn in (0, 1):
            wn = fn if dn else (1.0 - fn)
            if wn == 0.0:
                continue
            for dc in (0, 1):
                wc = fc if dc else (1.0 - fc)
                if wc == 0.0:
                    continue
                node = tab[it + dt_][i_n + dn][ic + dc]
                w = wt * wn * wc
                ln_a_nh3 += w * math.log(max(node[0], 1e-300))
                ln_a_co2 += w * math.log(max(node[1], 1e-300))
                a_h2o += w * node[2]
                n_sub += w * node[3]
    return [math.exp(ln_a_nh3), math.exp(ln_a_co2), a_h2o, n_sub]


def loadings(w: dict):
    """Total NH3 and CO2 loading of a liquor, mol per kg of WATER, from its mass fractions.

    `w` is the engine's six-species mass-fraction vector (values in 0-1 OR in %; both are accepted
    because the ratios below are scale-free)."""
    w_h2o = max(w.get("H2O", 0.0), 1e-9)
    n_load = (w.get("NH3", 0.0) / MW["NH3"]) / (w_h2o / MW["H2O"]) * (1000.0 / MW["H2O"])
    c_load = (w.get("CO2", 0.0) / MW["CO2"]) / (w_h2o / MW["H2O"]) * (1000.0 / MW["H2O"])
    return n_load, c_load


def bubble_p_bara(w: dict, t_c: float) -> float:
    """Bubble-point pressure (bar a) of an NH3-CO2-H2O-urea liquor at temperature `t_c`.

    P = f_dil * [ a_NH3*H_NH3(T) + a_CO2*H_CO2(T) + a_H2O*Psat_H2O(T) ]
    with the activities interpolated from the Extended UNIQUAC table and both Henry constants and
    the water saturation line evaluated ANALYTICALLY at the live temperature."""
    n_load, c_load = loadings(w)
    a_nh3, a_co2, a_h2o, n_sub_per_kgw = _interp(t_c, n_load, c_load)
    w_h2o = max(w.get("H2O", 0.0), 1e-9)
    # sub-system moles carried by this liquor's water, and the non-volatile moles alongside them
    n_sub = n_sub_per_kgw * (w_h2o / MW["H2O"]) * (MW["H2O"] / 1000.0)
    n_nv = sum(w.get(k, 0.0) / MW[k] for k in NONVOLATILE)
    f_dil = n_sub / max(n_sub + n_nv, 1e-12)
    t_k = t_c + 273.15
    p_nh3 = a_nh3 * _props.henry_nh3_MPa(t_k) * 10.0            # MPa -> bar
    p_co2 = a_co2 * _props.henry_co2_MPa(t_k) * 10.0
    p_h2o = a_h2o * iapws_if97.psat_bara(_clamp(t_c, 0.05, 370.0))
    return max(f_dil * (p_nh3 + p_co2 + p_h2o), 1e-6)


#  Warm-start acceptance band, expressed on ln P.  A guess whose bubble pressure is within this
#  relative tolerance is returned UNCHANGED, which is what makes the design point bit-exact: the
#  design anchors below are computed by cold bisection to 1e-7 K, so on a design-state tick the
#  residual is ~2e-9 and the solver hands back the anchor itself -- departure identically 0.0.
#  1e-6 in pressure is ~5e-5 K in temperature: far below anything the engine or an operator resolves.
_WARM_LNP_TOL = 1.0e-6


def bubble_t_c(w: dict, p_bara: float, t_guess: float = None,
               t_lo: float = 40.0, t_hi: float = 200.0, tol: float = 1e-7) -> float:
    """Bubble-point TEMPERATURE (C) of the liquor at pressure `p_bara`.

    `bubble_p_bara` is strictly increasing in T (every one of its three terms is), so the root is
    unique.  Two solvers share this entry point:

      * WARM START -- pass last tick's answer as `t_guess` and the root is found by Newton on
        ln P (the bubble pressure is very nearly exponential in T, so ln P is nearly linear and
        Newton converges in 2-3 steps).  This is the path the engine takes every tick: ~10 us.
      * COLD START -- with no guess, bisect.  Used at import to establish the design anchors, where
        40 halvings at ~0.7 ms is irrelevant.
    """
    if t_guess is not None and t_lo < t_guess < t_hi:
        t = _clamp(t_guess, t_lo, t_hi)
        ln_target = math.log(max(p_bara, 1e-9))
        for _ in range(6):
            p0 = bubble_p_bara(w, t)
            f = math.log(max(p0, 1e-12)) - ln_target
            if abs(f) < _WARM_LNP_TOL:
                return t
            h = 0.25
            p1 = bubble_p_bara(w, min(t + h, t_hi))
            slope = (math.log(max(p1, 1e-12)) - math.log(max(p0, 1e-12))) / h
            if slope <= 1.0e-9:
                break
            t_new = _clamp(t - f / slope, t_lo, t_hi)
            if abs(t_new - t) < 1.0e-6:
                return t_new
            t = t_new
        else:
            return t
    lo, hi = t_lo, t_hi
    if bubble_p_bara(w, lo) >= p_bara:
        return lo
    if bubble_p_bara(w, hi) <= p_bara:
        return hi
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if bubble_p_bara(w, mid) < p_bara:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def prime():
    """Force the table to be built/loaded now (called at engine import so the first tick is fast)."""
    _ensure_table()
    return MODEL_NAME
