"""Bubble-point / partial-pressure service for the NH3-CO2-H2O-urea liquors of the whole flowsheet.

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
    P_bub(T) = f_dil * [ a_NH3(T) H_NH3(T) + a_CO2(T) H_CO2(T) + a_H2O(T) Psat_H2O(T) ]
                     + sum_inerts  x_j H_j(T)

    a_i   = x_i * gamma_i     activities from the full Extended UNIQUAC gamma
                              (combinatorial + residual + extended Debye-Huckel), with the R1-R5
                              liquid speciation solved by `props_nh3co2h2o.speciate`
    H_i   Rumpf & Maurer (1993) Henry constants for NH3/CO2, mole-fraction scale (Darde 2.12-2.13);
          IAPWS G7-04 for the four permanent gases (see the INERTS section below)
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
    323C003   68.74 U / 0.36 B / 2.13 N / 1.05 C        135      4.3516    4.10     + 6.1 %
    323F004   71.74 U / 0.37 B / 0.88 N / 0.66 C        106      1.2993    1.13     +15.0 %
    323F010   80.00 U / 0.42 B / 0.08 N / 0.02 C         99      0.4683    0.46     + 1.8 %

Three stages spanning 0.46-4.1 bar a and 99-135 C, reproduced to +1.8 % / +6.1 % / +15.0 % from
first principles.  (On the pre-G-VLE-3 molality grid the same three read 4.387 / 1.328 / 0.468,
i.e. +7.0 % / +17.5 % / +1.7 %.  The re-index moved them by under a point of percentage and, at two
of the three, TOWARD the plant -- see the note below on why that is the evidence it is a coordinate
transform and not a new model.)

323F004 is the loosest because it is the stage where the CO2 term dominates and CO2 is where this
model is weakest: at 0.66 wt% CO2 the carbamate equilibrium is steep, and urea --
which is 72 % of the liquor -- is a mole-fraction DILUENT here, not a UNIQUAC species, so it dilutes
the volatiles without shifting their activity coefficients.  See gap G-VLE-1 in handoff.md.

What matters for the engine is the SLOPE, not the offset: every call site uses the DEPARTURE form
T_des + [T_bub(live) - T_bub(design)], so the residual cancels identically at the design point.  For
comparison, the pure-water anchor this replaces gives 103.3 C at 323F004's 1.13 bar against an actual
106 C, and -- far more importantly -- responds to composition with a derivative of exactly zero.


=====================================================================================================
G-VLE-3 -- WHY THE GRID IS INDEXED IN MOLE FRACTIONS AND NOT IN MOLALITIES
=====================================================================================================
The first version of this table was indexed by (T, N, C) with N and C the total NH3 and CO2 loading
in mol per kg of WATER.  That is the natural coordinate of the underlying model -- Extended UNIQUAC
is a molality-referenced electrolyte model and `speciate` takes molalities -- and it is fine
everywhere the solvent is water.  In the HP synthesis loop it is not a coordinate at all:

    stage                          T        N (mol/kg water)      C (mol/kg water)
    322R001 overflow (stream 207)  183 C          100.0                 22.4
    322E003 off-gas feed           183 C          869.3                258.1

against a table that stopped at N = 16 and C = 7.  Those are not large numbers because the liquor is
exotic; they are large because the DENOMINATOR is vanishing.  The molality of a liquor with no water
in it is infinite, so no molality grid can ever be wide enough, and every finite one silently
CLAMPS -- returning its edge node, i.e. a frozen constant wearing a rigorous-looking call.

In mole fractions the same two states are unremarkable:

    stage                          x_NH3     x_CO2     x_H2O
    322R001 overflow               0.562     0.126     0.312
    322E003 off-gas feed           0.735     0.218     0.047

so the table is now indexed by two BOUNDED coordinates on the water + volatile sub-system:

    s = (n_NH3 + n_CO2) / (n_NH3 + n_CO2 + n_H2O)      total volatile mole fraction, [0, 1)
    f =  n_CO2         / (n_NH3 + n_CO2)               CO2 fraction of the volatiles, [0, 1]

s is the "how little water is left" axis and f is the N/C axis (N/C = (1-f)/f).  Every physically
realisable liquor maps into the rectangle, which is the property the molality pair never had, and
the rectangle is FULL -- unlike an (x_NH3, x_CO2) pair, whose upper triangle is unreachable and
whose interpolation cells would straddle the hypotenuse.

The molalities are recovered exactly, so the model underneath is untouched:

    N = 55.508 s (1-f) / (1-s)          C = 55.508 s f / (1-s)

and s is BRACKETED on logit(s) = ln(s/(1-s)) = ln(N + C) - ln(55.508), which is the same log-molality
weighting the previous table used -- so in the dilute limit the new grid interpolates identically to
the old one.  That is the point of the change: it is a coordinate transform, not a new model.  The
323 validation numbers above move by under a point of percentage across it, and at two of the
three toward the PFD: the interpolation WEIGHTING is provably identical in the dilute limit,
so what is left is the node placement, which was re-graded at the same time.

WHAT IS AND IS NOT NOW CLAIMED IN THE HP LOOP
---------------------------------------------
Two separate things limited the old table and only ONE of them is fixed here.

    FIXED -- the SOLVE.  `props_nh3co2h2o.speciate` stopped converging above N ~ 40 mol/kg water:
    at N = 50 it returns a residual of 9.9 and 200, 2 000 and 20 000 iterations all return the same
    non-solution.  That was a basin-of-attraction failure of the dilute initial guess, nothing more.
    Seeded from a converged neighbour it reaches N = 869 / C = 195 in five Newton steps at a
    residual of 8.5e-14, so `_build_table` marches the grid by continuation (temperature first,
    then s, then f, with a temperature bisection fallback) and every node it stores is a genuine
    converged solve.  Nodes that do NOT converge are stored with their flag cleared and any
    interpolation cell touching one reports `in_grid = False` -- the clamp is now visible.

    NOT FIXED -- the FIT.  The Extended UNIQUAC interaction parameters are a CO2-capture parameter
    set regressed on dilute aqueous loadings below ~150 C.  At x_H2O = 0.047 and 183 C the model is
    being evaluated far outside the data it was regressed on, and the extended Debye-Huckel term in
    particular is being asked for an ionic strength of ~130 mol/kg.  The numbers it returns there
    are a smooth, thermodynamically consistent EXTRAPOLATION, not a prediction.

That distinction is what governs how the HP loop is allowed to use this table, and the engine
obeys it: every 322 split runs on the anchored RATIO form

    alpha_live = alpha_PFD * [ alpha_model(live) / alpha_model(design) ]

so the licensor's absolute split is preserved bit-exactly at the design point and the table supplies
only the DERIVATIVE -- how the split moves when temperature, pressure or composition move.  A
systematic offset in an extrapolated activity coefficient cancels in that ratio; its slope does not,
and the slope is the thing the old frozen vectors reported as exactly zero.

INERTS
------
N2, O2, CH4 and H2 have no Extended UNIQUAC rows and never will -- they are not electrolytes and
they do not speciate.  They enter the only way a permanent gas can: Henry's law on the mole-fraction
scale with an infinite-dilution reference (gamma* = 1), using the IAPWS G7-04 constants added to
`props_nh3co2h2o`.  Two stated approximations come with that, and neither is hidden:

  * G7-04 is a Henry constant in WATER, applied here to a solvent that in the synthesis loop is
    mostly ammonia and carbamate.  There is no published inert solubility in molten carbamate in
    this repository, and the directive is not to invent one.
  * No Poynting correction is applied.  At 144 bar the partial molar volume term is worth roughly
    +15 % on an NH3 or CO2 partial pressure, and this repository holds no sourced infinite-dilution
    partial molar volumes to compute it with.  It is very nearly constant across the loop's
    operating band, so it cancels in the ratio form above -- which is where it is absorbed.

WHY THERE IS A GRID
-------------------
`speciate` is a damped log-space Newton solve with a numerical Jacobian over 8 species: ~15-25 ms
per call, against a simulator that integrates at dt = 0.25 s and up to 60x real time.  Calling it
inline would be ~250x too slow.  The activities are therefore tabulated once over the operating
envelope and interpolated; the Henry constants and the water saturation line stay ANALYTIC at the
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
      "CO2": 44.0095, "H2O": 18.0153, "HCHO": 30.026,
      "N2": 28.0134, "O2": 31.9988, "CH4": 16.0425, "H2": 2.01588}
NONVOLATILE = ("Urea", "Biuret", "HCHO")
INERTS = ("N2", "O2", "CH4", "H2")

MODEL_NAME = ("Extended UNIQUAC NH3-CO2-H2O electrolyte gamma-phi VLE "
              "(Thomsen-Rasmussen / Darde) + non-volatile urea dilution "
              "+ IAPWS G7-04 Henry inerts")

_N_W_PER_KG = _props._N_W_PER_KG                       # 55.508 mol water per kg water

# ---- table envelope ------------------------------------------------------------------------------
#  T : 80-210 C.  Was 80-170; the top was raised for the synthesis loop (183 C at the reactor
#      overflow) and for the 328C004 reboiler band.  Nodes sit ON the three stages whose bubble
#      pressures are validated above (99 / 135) and on the reactor (183), so those states are read
#      off a solved node in the temperature direction instead of between two.
#  s : total volatile mole fraction (n_NH3 + n_CO2)/(n_NH3 + n_CO2 + n_H2O).  Design values are
#      F010 0.0047, C003 0.088, R207 0.688, E003 0.953.  Spaced so the nodes cluster where the
#      plant lives at BOTH ends, and bracketed on logit(s) -- see the module note.
#  f : CO2 fraction of the volatiles n_CO2/(n_NH3 + n_CO2), i.e. 1/(1 + N/C).  Design values are
#      F010 0.077, C003 0.160, R207 0.183, E003 0.229; the band spans N/C from 500 down to 0.28.
_T_NODES = (80.0, 99.0, 118.0, 135.0, 152.0, 168.0, 183.0, 197.0, 210.0)
_S_NODES = (1.0e-5, 1.0e-4, 1.0e-3, 5.0e-3, 0.02, 0.06, 0.13, 0.24,
            0.38, 0.53, 0.67, 0.79, 0.88, 0.94, 0.98)
_F_NODES = (0.002, 0.01, 0.03, 0.07, 0.14, 0.24, 0.38, 0.56, 0.78)

_HERE = os.path.dirname(os.path.abspath(__file__))
_CACHE_PATH = os.path.join(_HERE, ".vle_nh3co2h2o_grid.json")
_TABLE = None                # [i_T][i_s][i_f] -> [a_NH3, a_CO2, a_H2O, n_sub_per_kg_water, ok]
_BUILD_SECONDS = None        # wall time of the last table BUILD (None if the cache was hit)
_BUILD_STATS = None          # {"nodes":, "failed":, "seconds":, "cached":}

#  A node is accepted only if the speciation residual is at or below this.  `speciate`'s own loop
#  tolerance is 1e-11; 1e-8 leaves three decades of slack for the hardest nodes without letting a
#  non-solution (residual of order 1-200, which is what a basin failure returns) through.
_NODE_RESID_TOL = 1.0e-8


def _clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


#  Bump when `_node_activities` changes what a node MEANS.  The key hashes the property source and
#  the node definitions (the only two things a stored node depends on) rather than this whole file,
#  so editing the interpolator or the solver does not throw away the table build.
#  "3" == the G-VLE-3 re-index from (T, N, C) molalities to (T, s, f) mole fractions.
_TABLE_VERSION = "3"


def _cache_key() -> str:
    h = hashlib.sha256()
    try:
        with open(os.path.join(_HERE, "props_nh3co2h2o.py"), "rb") as f:
            h.update(f.read())
    except OSError:
        h.update(b"\x00")
    h.update(repr((_TABLE_VERSION, _T_NODES, _S_NODES, _F_NODES, _NODE_RESID_TOL)).encode())
    return h.hexdigest()


# ==================================================================================================
#  coordinates
# ==================================================================================================

def sf_to_loadings(s: float, f: float):
    """(s, f) -> (N, C) in mol per kg of water.  Exact inverse of `loadings_to_sf`."""
    s = _clamp(s, 0.0, 1.0 - 1e-12)
    r = _N_W_PER_KG * s / (1.0 - s)                    # total volatile mol per kg water
    return r * (1.0 - f), r * f


def loadings_to_sf(n_load: float, c_load: float):
    """(N, C) in mol/kg water -> (s, f).  Finite for every finite loading, including C = 0."""
    tot = max(n_load, 0.0) + max(c_load, 0.0)
    if tot <= 0.0:
        return 0.0, 0.0
    return tot / (_N_W_PER_KG + tot), max(c_load, 0.0) / tot


def loadings(w: dict):
    """Total NH3 and CO2 loading of a liquor, mol per kg of WATER, from its mass fractions.

    RETAINED as the diagnostic that names the old failure: for the 322E003 feed it returns 869 and
    258 against a table that used to stop at 16 and 7.  Nothing in the interpolation path calls it
    any more -- `coords` does -- but `thermo_service.domain_report` still reports it, because
    "N = 54x the top node" is a far more legible way to say "no water left" than "s = 0.953".

    `w` is a mass-fraction vector (values in 0-1 OR in %; both are accepted because the ratios below
    are scale-free)."""
    w_h2o = max(w.get("H2O", 0.0), 1e-9)
    n_load = (w.get("NH3", 0.0) / MW["NH3"]) / (w_h2o / MW["H2O"]) * (1000.0 / MW["H2O"])
    c_load = (w.get("CO2", 0.0) / MW["CO2"]) / (w_h2o / MW["H2O"]) * (1000.0 / MW["H2O"])
    return n_load, c_load


def coords(w: dict):
    """Grid coordinates (s, f) of a liquor from its mass fractions.

    Computed from the MOLE COUNTS directly rather than through `loadings`, so a liquor with no water
    at all returns s = 1.0 instead of dividing by zero.  That state is off the top of the grid and
    `in_grid` says so -- but it says so by comparing 1.0 with 0.98, not by propagating an inf."""
    n_n = max(w.get("NH3", 0.0), 0.0) / MW["NH3"]
    n_c = max(w.get("CO2", 0.0), 0.0) / MW["CO2"]
    n_w = max(w.get("H2O", 0.0), 0.0) / MW["H2O"]
    tot = n_n + n_c + n_w
    if tot <= 0.0:
        return 0.0, 0.0
    return (n_n + n_c) / tot, (n_c / (n_n + n_c)) if (n_n + n_c) > 0.0 else 0.0


#  Pressure range this module is usable over.  There is deliberately NO pressure AXIS on the table:
#  the Extended UNIQUAC activity model has no pressure dependence at all, and the one term that
#  would give it one -- the Poynting factor exp(v_inf (P - P_sat)/RT) -- needs infinite-dilution
#  partial molar volumes that this repository does not hold from any source.  So the liquid side is
#  pressure-independent by construction and the bound below is a statement about the VAPOUR side and
#  about honesty, not about a grid:
#    * the SRK fugacity is an equation of state and is valid across the whole band (it returns
#      Z = 0.80 and phi_N2 = 1.31 at 144 bar a, i.e. it is doing real work up there);
#    * the missing Poynting term is worth roughly +15 % on an NH3 or CO2 partial pressure at 144 bar
#      and is very nearly constant across the loop's operating band, so it is absorbed by the
#      anchored RATIO form the 322 loop uses and cancels there.  It does NOT cancel for an absolute
#      bubble pressure, which is one more reason no absolute HP-loop number reaches the engine.
VALID_PRESSURE_BARA = (0.02, 180.0)


def envelope() -> dict:
    """The tabulated envelope, as bounds a caller can test or report without importing the nodes."""
    return {"t_c": (_T_NODES[0], _T_NODES[-1]),
            "s": (_S_NODES[0], _S_NODES[-1]),
            "f": (_F_NODES[0], _F_NODES[-1]),
            "p_bara": VALID_PRESSURE_BARA,
            "n_load_at_s_max": sf_to_loadings(_S_NODES[-1], _F_NODES[0])[0],
            "c_load_at_s_max": sf_to_loadings(_S_NODES[-1], _F_NODES[-1])[1]}


# ==================================================================================================
#  table build -- continuation, because the dilute initial guess does not reach the HP loop
# ==================================================================================================

def _node_activities(t_c: float, s: float, f: float, seed=None):
    """Solve one grid node: liquid speciation + full Extended UNIQUAC activities.

    Returns (a_NH3, a_CO2, a_H2O, n_sub_per_kg_water, ok, molalities) where a_i = x_i*gamma_i on the
    mole-fraction scale of the water + electrolyte sub-system (urea/biuret enter later, as a
    dilution factor), `ok` is True only if the speciation residual met `_NODE_RESID_TOL`, and
    `molalities` is the raw solution vector so the next node can be seeded from it."""
    t_k = t_c + 273.15
    n_load, c_load = sf_to_loadings(s, f)
    md = _props.speciate(max(n_load, 1e-6), max(c_load, 1e-6), T=t_k, m_guess=seed)
    ok = md.get("resid", float("inf")) <= _NODE_RESID_TOL
    n_sub = _N_W_PER_KG + sum(md[sp] for sp in _props._SOLUTES)
    x = {"H2O": _N_W_PER_KG / n_sub}
    for sp in _props._SOLUTES:
        x[sp] = md[sp] / n_sub
    lng = _props.activity_ln_gamma(x, t_k)
    return (x["NH3(aq)"] * math.exp(lng["NH3(aq)"]),
            x["CO2(aq)"] * math.exp(lng["CO2(aq)"]),
            x["H2O"] * math.exp(lng["H2O"]),
            n_sub, ok, {sp: md[sp] for sp in _props._SOLUTES})


def _march_temperature(t_from, t_to, s, f, seed, depth=0):
    """Solve (t_to, s, f) seeded from a solution at (t_from, s, f), bisecting T on failure.

    Temperature is the smoothest continuation direction of the three -- the speciation moves
    continuously along it and the activity coefficients with it -- so this is the fallback that
    rescues the handful of nodes a single jump cannot reach."""
    res = _node_activities(t_to, s, f, seed)
    if res[4] or depth >= 6 or t_from is None:
        return res
    t_mid = 0.5 * (t_from + t_to)
    mid = _march_temperature(t_from, t_mid, s, f, seed, depth + 1)
    if not mid[4]:
        return res
    return _march_temperature(t_mid, t_to, s, f, mid[5], depth + 1)


def _build_table():
    """Build the whole (T, s, f) table by continuation.

    Marching order is TEMPERATURE outermost, then s, then f.  Each node is attempted from the
    converged node one step back in T first (measured: that seed alone carries 958 of 960 probe
    nodes and cuts the mean solve from 84 ms to 15 ms), then from its s-neighbour, then from its
    f-neighbour, then cold.  A node that survives none of those is STORED WITH ITS FLAG CLEARED
    rather than dropped, so the interpolator can refuse cells that touch it instead of silently
    interpolating through a non-solution."""
    nt, ns, nf = len(_T_NODES), len(_S_NODES), len(_F_NODES)
    table = [[[None] * nf for _ in range(ns)] for _ in range(nt)]
    seeds = [[[None] * nf for _ in range(ns)] for _ in range(nt)]
    failed = 0
    for it in range(nt):
        t_c = _T_NODES[it]
        t_prev = _T_NODES[it - 1] if it else None
        for i_s in range(ns):
            for i_f in range(nf):
                cands = []
                if it and seeds[it - 1][i_s][i_f] is not None:
                    cands.append((seeds[it - 1][i_s][i_f], t_prev))
                if i_s and seeds[it][i_s - 1][i_f] is not None:
                    cands.append((seeds[it][i_s - 1][i_f], None))
                if i_f and seeds[it][i_s][i_f - 1] is not None:
                    cands.append((seeds[it][i_s][i_f - 1], None))
                cands.append((None, None))                       # cold, the original ansatz
                best = None
                for seed, t_from in cands:
                    res = (_march_temperature(t_from, t_c, _S_NODES[i_s], _F_NODES[i_f], seed)
                           if t_from is not None
                           else _node_activities(t_c, _S_NODES[i_s], _F_NODES[i_f], seed))
                    if res[4]:
                        best = res
                        break
                    if best is None:
                        best = res
                if not best[4]:
                    failed += 1
                table[it][i_s][i_f] = [best[0], best[1], best[2], best[3],
                                       1.0 if best[4] else 0.0]
                seeds[it][i_s][i_f] = best[5] if best[4] else None
    return table, failed


def _ensure_table():
    global _TABLE, _BUILD_SECONDS, _BUILD_STATS
    if _TABLE is not None:
        return _TABLE
    key = _cache_key()
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            doc = json.load(f)
        if doc.get("key") == key:
            _TABLE = doc["table"]
            _BUILD_STATS = {"nodes": len(_T_NODES) * len(_S_NODES) * len(_F_NODES),
                            "failed": doc.get("failed", 0),
                            "seconds": doc.get("seconds", 0.0), "cached": True}
            return _TABLE
    except (OSError, ValueError, KeyError):
        pass
    import time
    n_nodes = len(_T_NODES) * len(_S_NODES) * len(_F_NODES)
    print("[vle] building NH3-CO2-H2O Extended UNIQUAC activity table by continuation "
          "(%d nodes, ~20 s, once per model change)" % n_nodes, flush=True)
    t0 = time.time()
    _TABLE, failed = _build_table()
    _BUILD_SECONDS = time.time() - t0
    _BUILD_STATS = {"nodes": n_nodes, "failed": failed,
                    "seconds": _BUILD_SECONDS, "cached": False}
    print("[vle] table built in %.1f s (%d/%d nodes converged)"
          % (_BUILD_SECONDS, n_nodes - failed, n_nodes), flush=True)
    try:
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"key": key, "table": _TABLE,
                       "failed": failed, "seconds": _BUILD_SECONDS}, f)
    except OSError:
        pass                                   # the cache is an optimisation, never a hard dependency
    return _TABLE


def build_stats() -> dict:
    """Node count, failure count and build wall time -- for the boot report and for tests."""
    _ensure_table()
    return dict(_BUILD_STATS or {})


# ==================================================================================================
#  interpolation
# ==================================================================================================

def _bracket(nodes, v, mode: str = "linear"):
    """Return (index, weight) for interpolation, clamped at both ends (no extrapolation).

    `mode` selects the coordinate the weight is taken on:
      linear  -- v itself.
      log     -- ln(v).  For f, whose activities span decades across the band.
      logit   -- ln(v/(1-v)).  For s.  This is exactly ln(N + C) up to the constant ln(55.508), so
                 in the dilute limit the weighting is IDENTICAL to the log-molality weighting the
                 pre-G-VLE-3 table used -- which is what makes the re-index a coordinate change
                 rather than a new interpolation error."""
    if v <= nodes[0]:
        return 0, 0.0
    if v >= nodes[-1]:
        return len(nodes) - 2, 1.0
    if mode == "logit":
        def g(u):
            return math.log(u / (1.0 - u)) if 0.0 < u < 1.0 else (-745.0 if u <= 0.0 else 745.0)
    elif mode == "log":
        def g(u):
            return math.log(max(u, 1e-300))
    else:
        def g(u):
            return u
    for i in range(1, len(nodes)):
        if v <= nodes[i]:
            lo, hi = g(nodes[i - 1]), g(nodes[i])
            return i - 1, (g(v) - lo) / (hi - lo) if hi > lo else 0.0
    return len(nodes) - 2, 1.0


def _interp(t_c: float, s: float, f: float):
    """Trilinear interpolation of (a_NH3, a_CO2, a_H2O, n_sub) plus a corners-converged flag.

    a_NH3 and a_CO2 are interpolated as log(a) -- they are strictly positive and span many decades,
    and their true shape between nodes is exponential, so a linear blend of the LOGS is both exact
    at the nodes and far closer in between.  a_H2O (order 1) and n_sub (order 56) stay linear.

    The fifth return value is False if ANY of the eight corner nodes actually used failed to
    converge.  That is the honest form of the clamp warning: a cell that touches a non-solution is
    not a solve, whatever its coordinates say."""
    tab = _ensure_table()
    it, ft = _bracket(_T_NODES, t_c)
    i_s, fs = _bracket(_S_NODES, s, mode="logit")
    i_f, ff = _bracket(_F_NODES, f, mode="log")
    ln_a_nh3 = ln_a_co2 = a_h2o = n_sub = 0.0
    corners_ok = True
    for dt_ in (0, 1):
        wt = ft if dt_ else (1.0 - ft)
        if wt == 0.0:
            continue
        for ds in (0, 1):
            ws = fs if ds else (1.0 - fs)
            if ws == 0.0:
                continue
            for df in (0, 1):
                wf = ff if df else (1.0 - ff)
                if wf == 0.0:
                    continue
                node = tab[it + dt_][i_s + ds][i_f + df]
                w = wt * ws * wf
                ln_a_nh3 += w * math.log(max(node[0], 1e-300))
                ln_a_co2 += w * math.log(max(node[1], 1e-300))
                a_h2o += w * node[2]
                n_sub += w * node[3]
                if node[4] < 0.5:
                    corners_ok = False
    return math.exp(ln_a_nh3), math.exp(ln_a_co2), a_h2o, n_sub, corners_ok


# ==================================================================================================
#  partial pressures / bubble point
# ==================================================================================================

def _in_box(t_c: float, s: float, f: float) -> bool:
    """Axis test for the tabulated envelope.  The two composition axes are bounded from ABOVE only,
    and that asymmetry is the physics, not a slip.

    Clamping at the TOP of s or f fabricates a frozen constant: the true activity keeps rising past
    the last node and the table hands back the node instead, which is exactly the failure mode this
    module exists to make visible.  Clamping at the BOTTOM lands in the dilute limit, where every
    volatile term is vanishing anyway -- at the floor nodes (s = 1e-5, f = 0.002) the tabulated CO2
    loading is 1.1e-6 mol per kg of water and a_CO2 is of order 1e-8, so treating a liquor with
    LESS CO2 than that as though it had exactly that much moves its bubble pressure by far below
    any pressure this plant resolves.  Refusing there instead would put pure steam, and every 324
    urea melt whose volatiles are traces, outside every fitted model in the repository -- which is
    not what the fit says, and is not what the pre-G-VLE-3 envelope test said either (it bounded
    the loadings from above only, for the same reason).

    TEMPERATURE is bounded on BOTH sides and stays that way: below the 80 C node the activities are
    not vanishing, they are simply untabulated, and `_bubble_t_solve` already refuses rather than
    clamping there -- a 323F010 liquor carrying 1.6 wt% NH3 has a real bubble point below 80 C at
    0.46 bar a, and a clamped 80.0 came back looking like an answer."""
    return (_T_NODES[0] <= t_c <= _T_NODES[-1]
            and s <= _S_NODES[-1] and f <= _F_NODES[-1]
            and s >= 0.0 and f >= 0.0)


def in_grid(w: dict, t_c: float) -> bool:
    """Is this state actually SOLVED here, or would it be clamped?

    The same test `partial_pressures_bara` reports, but without the Henry constants and the IF-97
    saturation line -- the coordinates and the corner flags are all it needs.  `thermo_service`
    calls this once per K-value evaluation, so paying for a full partial-pressure vector to answer a
    yes/no question showed up directly in the tick budget: it is the difference between 35 us and
    9 us, four times per tick per wired unit."""
    s, f = coords(w)
    if not _in_box(t_c, s, f):
        return False
    return _interp(t_c, s, f)[4]


def partial_pressures_bara(w: dict, t_c: float) -> dict:
    """Per-volatile partial pressures (bar a) of an NH3-CO2-H2O-urea liquor at `t_c`.

    Returns {"NH3": p, "CO2": p, "H2O": p, "N2": p, ..., "f_dil": f, "in_grid": bool} where each
    partial pressure already carries the non-volatile dilution factor, so their SUM is exactly
    `bubble_p_bara`.  Splitting the sum out is what lets a flash form per-species K-values
    (K_i = p_i /(x_i P)) instead of only a bubble point; `bubble_p_bara` is now the sum of this
    vector and cannot drift from it.

    `in_grid` reports whether this state was actually SOLVED rather than clamped: the coordinates
    must lie inside the tabulated envelope AND every corner node used must have converged.
    `_bracket` clamps at the ends rather than extrapolating, so an out-of-envelope call silently
    returns the edge node -- a frozen constant wearing a rigorous-looking call.  Callers that would
    otherwise mistake that for a solve must check this flag; `thermo_service` refuses on it."""
    s, f = coords(w)
    in_box = _in_box(t_c, s, f)
    a_nh3, a_co2, a_h2o, n_sub_per_kgw, corners_ok = _interp(t_c, s, f)
    w_h2o = max(w.get("H2O", 0.0), 1e-9)
    # sub-system moles carried by this liquor's water, and everything alongside them that is NOT in
    # the electrolyte sub-system: the non-volatiles, and the four permanent gases.
    n_sub = n_sub_per_kgw * (w_h2o / MW["H2O"]) * (MW["H2O"] / 1000.0)
    n_nv = sum(max(w.get(k, 0.0), 0.0) / MW[k] for k in NONVOLATILE)
    n_in = {k: max(w.get(k, 0.0), 0.0) / MW[k] for k in INERTS}
    n_in_tot = sum(n_in.values())
    n_all = max(n_sub + n_nv + n_in_tot, 1e-12)
    f_dil = n_sub / n_all
    t_k = t_c + 273.15
    out = {"NH3": f_dil * a_nh3 * _props.henry_nh3_MPa(t_k) * 10.0,     # MPa -> bar
           "CO2": f_dil * a_co2 * _props.henry_co2_MPa(t_k) * 10.0,
           "H2O": f_dil * a_h2o * iapws_if97.psat_bara(_clamp(t_c, 0.05, 370.0)),
           "f_dil": f_dil, "in_grid": bool(in_box and corners_ok)}
    #  Permanent gases: Henry's law with an infinite-dilution reference, gamma* = 1.  They are not
    #  UNIQUAC species and there is no parameter row to give them an activity coefficient; gamma* = 1
    #  is the standard state itself, not a stand-in for a missing number.  x_j is on the TOTAL liquid
    #  mole basis, which is the same basis f_dil puts the three volatiles above onto.
    t_lo, t_hi = _props.G704_VALID_T_K
    t_h = _clamp(t_k, t_lo, t_hi)
    for k in INERTS:
        out[k] = (n_in[k] / n_all) * _props.henry_inert_MPa(k, t_h) * 10.0
    return out


def bubble_p_bara(w: dict, t_c: float) -> float:
    """Bubble-point pressure (bar a) of an NH3-CO2-H2O-urea liquor at temperature `t_c`.

    P = f_dil * [ a_NH3*H_NH3(T) + a_CO2*H_CO2(T) + a_H2O*Psat_H2O(T) ] + sum_j x_j*H_j(T)
    with the activities interpolated from the Extended UNIQUAC table and both Henry constants and
    the water saturation line evaluated ANALYTICALLY at the live temperature.  The terms come from
    `partial_pressures_bara` so the bubble point and the flash K-values cannot disagree."""
    p = partial_pressures_bara(w, t_c)
    tot = p["NH3"] + p["CO2"] + p["H2O"] + sum(p[k] for k in INERTS)
    return max(tot, 1e-6)


#  Warm-start acceptance band, expressed on ln P.  A guess whose bubble pressure is within this
#  relative tolerance is returned UNCHANGED, which is what makes the design point bit-exact: the
#  design anchors below are computed by cold bisection to 1e-7 K, so on a design-state tick the
#  residual is ~2e-9 and the solver hands back the anchor itself -- departure identically 0.0.
#  1e-6 in pressure is ~5e-5 K in temperature: far below anything the engine or an operator resolves.
_WARM_LNP_TOL = 1.0e-6


def bubble_t_c(w: dict, p_bara: float, t_guess: float = None,
               t_lo: float = 40.0, t_hi: float = 240.0, tol: float = 1e-7) -> float:
    """Bubble-point TEMPERATURE (C) of the liquor at pressure `p_bara`.

    `bubble_p_bara` is strictly increasing in T (every one of its terms is), so the root is unique.
    Two solvers share this entry point:

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
