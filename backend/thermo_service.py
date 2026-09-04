"""Unified rigorous VLE / flash service for the Urea OTS engine.

WHAT THIS IS
------------
One entry point for every phase boundary in the flowsheet, standing on the two activity models the
repository already owns and, until now, barely used:

    vle_nh3co2h2o        Extended UNIQUAC NH3-CO2-H2O electrolyte gamma-phi (Thomsen-Rasmussen /
                         Darde) with R1-R5 liquid speciation, Rumpf-Maurer Henry constants and the
                         IAPWS-IF97 water line.  Urea and biuret enter as non-volatile diluents.
    thermo_extended_uniquac
                         Neutral H2O/urea binary UNIQUAC (Voskov-Voronin).  The Debye-Huckel term is
                         identically zero for two neutral species, so this IS Extended UNIQUAC in the
                         urea/water limit -- and it is the only one of the two that sees urea as a
                         UNIQUAC species rather than a mole-fraction diluent.
    props_nh3co2h2o      Soave-Redlich-Kwong vapour fugacity coefficients (k_ij = 0, Thomsen 2005).
    gap_g6_h0_enthalpy   Absolute stream enthalpy on the elements-at-298.15 K datum, all nine engine
                         species, liquid and vapour columns.  This is what makes flash_PH possible.

The service exposes  flash(), flash_ph(), bubble_p(), bubble_t(), dew_t()  and solves the
Rachford-Rice equation on gamma-phi K-values with SRK vapour fugacity.

WHY THERE ARE TWO DOMAINS, NOT ONE
----------------------------------
The two liquid models are not interchangeable and neither covers the whole plant.  Dispatching on
composition is not a fudge -- it is the only honest reading of what each model was fitted to:

    DOMAIN_ELECTROLYTE   the volatiles carry the bubble point (NH3 + CO2 loading is significant).
                         Water activity comes from the electrolyte table.  Correct for the 323
                         recirculation / flash train.
    DOMAIN_NEUTRAL_UREA  a near-binary urea/water melt whose volatiles are traces.  Water activity
                         comes from the neutral binary, because at 94-98 wt% urea the electrolyte
                         model's "urea is a mole-fraction diluent" assumption fails hard: it reads
                         the 324E001 melt +30.6 % and the 324E003 melt +65.7 % on bubble pressure.
                         Trace NH3/CO2 still come from the electrolyte path, where they sit in its
                         dilute limit and are well behaved.

MEASURED, on the engine's own design vectors, bubble pressure against the PFD:

    stage      T (C)   P_PFD    electrolyte    neutral-hybrid    domain used
    323C003    135     4.10     +7.0 %         --                ELECTROLYTE
    323F004    106     1.13     +17.5 %        --                ELECTROLYTE
    323F010     99     0.46     +1.7 %         --                ELECTROLYTE
    324E001    130     0.330    +30.6 %        see test          NEUTRAL_UREA
    324E003    140     0.131    +65.7 %        see test          NEUTRAL_UREA

WHAT IT REFUSES, AND WHY THAT MATTERS MORE THAN WHAT IT ANSWERS
--------------------------------------------------------------
`vle_nh3co2h2o._bracket` CLAMPS at the table edges rather than extrapolating.  An out-of-envelope
call therefore does not fail loudly and does not extrapolate wildly -- it silently returns the edge
node, i.e. A FROZEN CONSTANT behind a call that looks like a solve.  That is strictly worse than an
honest hardcoded split vector, because the heuristic becomes invisible.

So this service refuses instead.  `classify()` returns None and `flash()` raises `OutOfDomain`
whenever the state leaves the tabulated envelope, and callers keep whatever anchored model they
have.  The HP synthesis loop is entirely in that category today -- see DOMAIN NOTES below.

DOMAIN NOTES -- the HP synthesis loop (322) is NOT covered
----------------------------------------------------------
Measured against the electrolyte table envelope (T 80-170 C, N <= 16, C <= 7 mol/kg water):

    322R001 overflow (stream 207, 183 C):   N = 100.0  (6.2x the top node)   C = 22.4  (3.2x)
    322E003 off-gas feed        (183 C):    N = 869.3  (54.3x)               C = 258.1 (36.9x)

and the 322E003 feed additionally carries N2, O2, CH4 and H2, for which this repository holds
neither Henry constants nor SRK critical constants -- `props_nh3co2h2o.SRK_CRIT` covers H2O, NH3 and
CO2 only.  The reactor melt is not an aqueous solution at all; the underlying parameter set is a
CO2-capture model fitted to dilute aqueous loadings below ~150 C.

Putting 322R001 / 322E001 / 322E002 / 322E003 on this service would replace a calibrated,
clearly-labelled split vector with a clamped edge lookup plus four species the model cannot see.
That is a regression dressed as rigour, so it is not done.  Closing it needs a rebuilt grid over a
molten-carbamate envelope and inert Henry/SRK data -- new source material, not new wiring.

BASIS CONVENTIONS
-----------------
* Compositions in and out are MASS fractions over `SOL_SPECIES`, matching the engine's species
  layer, unless a function name says otherwise.  Internals work in mole fractions.
* K-values are APPARENT, on a TOTAL-species basis: the electrolyte model speciates ammonia into
  NH3(aq)/NH4+/NH2COO- and CO2 into CO2(aq)/HCO3-/CO3--, but the engine's mass balance tracks total
  NH3 and total CO2.  K_i = p_i / (phi_i^V * P * x_i,total) is therefore the ratio the flowsheet
  needs, and it is the ratio this module returns.
* Urea, biuret and HCHO are non-volatile: K = 0 exactly.
"""

from __future__ import annotations

import math

import gap_g6_h0_enthalpy as _h0
import props_nh3co2h2o as _props
import thermo_extended_uniquac as _neutral
import vle_nh3co2h2o as _vle

MODEL_NAME = "unified gamma-phi (Extended UNIQUAC electrolyte + neutral urea/water) with SRK vapour"

MW = {"Urea": 60.056, "Biuret": 103.081, "NH3": 17.0304,
      "CO2": 44.0098, "H2O": 18.0152, "HCHO": 32.031}
SPECIES = tuple(MW)
NONVOLATILE = ("Urea", "Biuret", "HCHO")
VOLATILE = ("NH3", "CO2", "H2O")
_SRK_SPECIES = ("H2O", "NH3", "CO2")          # props_nh3co2h2o.SRK_CRIT keys

DOMAIN_ELECTROLYTE = "electrolyte_gamma_phi"
DOMAIN_NEUTRAL_UREA = "neutral_urea_water_uniquac"

#  Above this urea mass fraction the electrolyte model's non-volatile-diluent treatment of urea is
#  no longer defensible and the neutral binary takes the water activity.  0.90 sits between the
#  323F010 product (80.0 wt%, electrolyte, +1.7 %) and the 324E001 melt (94.3 wt%, where the
#  electrolyte model is already +30.6 %), so each stage lands on the model that was fitted for it.
UREA_NEUTRAL_THRESHOLD = 0.90
#  Below this total volatile loading the liquor has no meaningful NH3/CO2 bubble-point contribution.
VOLATILE_TRACE_LOADING = 1.0e-3           # mol/kg water
#  Mixing factor for the gamma-phi successive-substitution loop (see `flash`).
_SS_DAMPING = 0.5


class OutOfDomain(ValueError):
    """The requested state lies outside every fitted envelope this service owns."""


# ==================================================================================================
#  composition helpers
# ==================================================================================================

def _norm_mass(w: dict) -> dict:
    tot = sum(max(w.get(k, 0.0), 0.0) for k in SPECIES)
    if tot <= 0.0:
        return {k: (1.0 if k == "H2O" else 0.0) for k in SPECIES}
    return {k: max(w.get(k, 0.0), 0.0) / tot for k in SPECIES}


def mass_to_mole(w: dict) -> dict:
    """Mass fractions -> mole fractions over SPECIES (total-species basis, no speciation)."""
    n = {k: max(w.get(k, 0.0), 0.0) / MW[k] for k in SPECIES}
    tot = sum(n.values())
    if tot <= 0.0:
        return {k: (1.0 if k == "H2O" else 0.0) for k in SPECIES}
    return {k: n[k] / tot for k in SPECIES}


def mole_to_mass(x: dict) -> dict:
    m = {k: max(x.get(k, 0.0), 0.0) * MW[k] for k in SPECIES}
    tot = sum(m.values())
    if tot <= 0.0:
        return {k: (1.0 if k == "H2O" else 0.0) for k in SPECIES}
    return {k: m[k] / tot for k in SPECIES}


# ==================================================================================================
#  domain classification
# ==================================================================================================

def classify(w: dict, t_c: float, p_bara: float = None) -> str | None:
    """Which fitted model owns this state, or None if neither does.

    Returning None is a first-class answer: the caller must then keep its own anchored model rather
    than take a clamped edge lookup for a solve (see the module note)."""
    w = _norm_mass(w)
    if not math.isfinite(t_c):
        return None
    n_load, c_load = _vle.loadings(w)
    if not (math.isfinite(n_load) and math.isfinite(c_load)):
        return None
    urea_like = w.get("Urea", 0.0) + w.get("Biuret", 0.0)
    if urea_like >= UREA_NEUTRAL_THRESHOLD:
        # Neutral binary owns the water activity.  Its own declared window governs.
        t_k = t_c + 273.15
        t_lo, t_hi = _neutral.VALID_TEMPERATURE_K
        if not (t_lo <= t_k <= t_hi):
            return None
        if p_bara is not None:
            p_lo, p_hi = _neutral.VALID_PRESSURE_BARA
            if not (p_lo <= p_bara <= p_hi):
                return None
        # trace volatiles still ride the electrolyte dilute limit -> its grid must also hold them
        if n_load > _vle._N_NODES[-1] or c_load > _vle._C_NODES[-1]:
            return None
        return DOMAIN_NEUTRAL_UREA
    if not (_vle._T_NODES[0] <= t_c <= _vle._T_NODES[-1]):
        return None
    if not (n_load <= _vle._N_NODES[-1] and c_load <= _vle._C_NODES[-1]):
        return None
    return DOMAIN_ELECTROLYTE


def domain_report(w: dict, t_c: float, p_bara: float = None) -> dict:
    """Diagnostic companion to `classify` -- says WHICH bound failed, for telemetry and tests."""
    w = _norm_mass(w)
    n_load, c_load = _vle.loadings(w)
    return {"domain": classify(w, t_c, p_bara),
            "t_c": t_c, "p_bara": p_bara,
            "n_load_mol_per_kg_water": n_load, "c_load_mol_per_kg_water": c_load,
            "t_envelope_c": (_vle._T_NODES[0], _vle._T_NODES[-1]),
            "n_envelope": (_vle._N_NODES[0], _vle._N_NODES[-1]),
            "c_envelope": (_vle._C_NODES[0], _vle._C_NODES[-1]),
            "urea_like_mass_frac": w.get("Urea", 0.0) + w.get("Biuret", 0.0),
            "model": MODEL_NAME}


# ==================================================================================================
#  partial pressures, fugacity, K-values
# ==================================================================================================

def partial_pressures(w: dict, t_c: float, domain: str = None) -> dict:
    """Volatile partial pressures (bar a) over a liquid of mass fractions `w` at `t_c`.

    ELECTROLYTE  : all three from the Extended UNIQUAC table + Henry / IF-97.
    NEUTRAL_UREA : water from the neutral urea/water binary (a_w * Psat), NH3/CO2 from the
                   electrolyte dilute limit.  This is the hybrid the module note justifies.
    """
    w = _norm_mass(w)
    if domain is None:
        domain = classify(w, t_c)
    if domain is None:
        raise OutOfDomain(f"no fitted model owns this state: {domain_report(w, t_c)}")
    p = _vle.partial_pressures_bara(w, t_c)
    out = {"NH3": p["NH3"], "CO2": p["CO2"], "H2O": p["H2O"]}
    if domain == DOMAIN_NEUTRAL_UREA:
        t_k = t_c + 273.15
        # urea/water binary on a water-free-of-volatiles basis: the traces do not shift the binary
        w_urea = w.get("Urea", 0.0)
        w_pair = w_urea + w.get("H2O", 0.0)
        if w_pair > 1e-12:
            a_w = _neutral.water_activity(min(max(w_urea / w_pair, 0.0), 0.999999), t_k)
            out["H2O"] = a_w * _neutral.water_psat_bara(t_k)
    return out


def vapour_fugacity(y_mole: dict, t_c: float, p_bara: float) -> dict:
    """SRK vapour fugacity coefficients for the volatile vapour, k_ij = 0 (Thomsen 2005).

    Species outside `props_nh3co2h2o.SRK_CRIT` (HCHO, and the inerts if a caller ever supplies them)
    are returned ideal, phi = 1.0, which is stated rather than hidden."""
    y = {s: max(y_mole.get(s, 0.0), 0.0) for s in _SRK_SPECIES}
    tot = sum(y.values())
    phi = {s: 1.0 for s in SPECIES}
    if tot <= 1e-12 or p_bara <= 0.0:
        return phi
    y = {s: v / tot for s, v in y.items()}
    try:
        phi_srk, _z = _props.srk_phi(y, t_c + 273.15, p_bara * 1.0e5)
    except (ValueError, ZeroDivisionError, OverflowError):
        return phi
    for s in _SRK_SPECIES:
        v = phi_srk.get(s)
        if v is not None and math.isfinite(v) and v > 0.0:
            phi[s] = v
    return phi


def k_values(w_liq: dict, t_c: float, p_bara: float,
             y_mole: dict = None, domain: str = None) -> dict:
    """Apparent K_i = y_i / x_i on the TOTAL-species basis (see module note).

    K_i = p_i / (phi_i^V * P * x_i).  Non-volatiles return exactly 0.0.
    `y_mole` seeds the SRK mixture; None means ideal vapour on the first pass."""
    w_liq = _norm_mass(w_liq)
    if domain is None:
        domain = classify(w_liq, t_c, p_bara)
    p_i = partial_pressures(w_liq, t_c, domain)
    x = mass_to_mole(w_liq)
    phi = vapour_fugacity(y_mole, t_c, p_bara) if y_mole else {s: 1.0 for s in SPECIES}
    k = {s: 0.0 for s in SPECIES}
    for s in VOLATILE:
        xs = x.get(s, 0.0)
        if xs <= 1e-14:
            continue
        k[s] = max(p_i[s] / (max(phi[s], 1e-9) * max(p_bara, 1e-9) * xs), 0.0)
    return k


# ==================================================================================================
#  bubble / dew
# ==================================================================================================

def bubble_p(w: dict, t_c: float, srk: bool = True, iters: int = 30) -> float:
    """Bubble-point pressure (bar a) of liquid `w` at `t_c`.  Raises OutOfDomain off-envelope.

    Full gamma-phi definition -- the pressure at which sum_i y_i = 1 with y_i phi_i P = p_i:

        P = sum_i p_i / phi_i(y, T, P)

    solved by fixed-point iteration on y.  Passing `srk=False` returns the ideal-vapour sum
    sum_i p_i, which is what `vle_nh3co2h2o.bubble_p_bara` computes and what the +7.0 / +17.5 /
    +1.7 % PFD comparison in that module was measured against.

    The phi correction is NOT cosmetic: with phi = 1 here and phi applied inside `k_values`, the
    bubble point and the flash sat on two different surfaces, and a flash AT the computed bubble
    temperature returned psi = 1.5e-3 instead of ~0.  Both entry points now use the same phi."""
    p = partial_pressures(w, t_c)
    p_ideal = max(p["NH3"] + p["CO2"] + p["H2O"], 1.0e-9)
    if not srk:
        return p_ideal
    p_bub = p_ideal
    phi = {s: 1.0 for s in SPECIES}
    for _ in range(iters):
        #  y_i is proportional to p_i/phi_i, NOT to p_i: with per-species phi the vapour composition
        #  itself shifts, so it has to be recomputed each sweep alongside the pressure.  (p_i are
        #  already mole-basis partial pressures, so no molar-mass conversion enters here.)
        num = {s: p[s] / max(phi[s], 1e-9) for s in VOLATILE}
        tot = sum(num.values())
        y_mole = {s: (num[s] / tot if tot > 0.0 else 0.0) for s in VOLATILE}
        phi = vapour_fugacity(y_mole, t_c, p_bub)
        p_new = sum(p[s] / max(phi[s], 1e-9) for s in VOLATILE)
        if abs(p_new - p_bub) <= 1e-12 * max(p_new, 1.0):
            p_bub = p_new
            break
        p_bub = p_new
    return max(p_bub, 1.0e-9)


def bubble_t(w: dict, p_bara: float, t_lo: float = None, t_hi: float = None,
             tol: float = 1.0e-6) -> float:
    """Bubble-point temperature (C) of liquid `w` at `p_bara`, by bisection on bubble_p - P.

    Brackets default to the owning model's own envelope, so the answer can never be reported from
    outside the fitted range."""
    w = _norm_mass(w)
    dom = classify(w, 0.5 * (_vle._T_NODES[0] + _vle._T_NODES[-1]), p_bara)
    if dom == DOMAIN_NEUTRAL_UREA:
        lo_d, hi_d = (_neutral.VALID_TEMPERATURE_K[0] - 273.15,
                      _neutral.VALID_TEMPERATURE_K[1] - 273.15)
    else:
        lo_d, hi_d = _vle._T_NODES[0], _vle._T_NODES[-1]
    lo = lo_d if t_lo is None else max(t_lo, lo_d)
    hi = hi_d if t_hi is None else min(t_hi, hi_d)
    if lo >= hi:
        raise OutOfDomain(f"empty bracket for bubble_t: {domain_report(w, lo, p_bara)}")
    if bubble_p(w, lo) >= p_bara:
        return lo
    if bubble_p(w, hi) <= p_bara:
        return hi
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if bubble_p(w, mid) < p_bara:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def dew_t(y_mass: dict, p_bara: float, tol: float = 1.0e-5) -> float:
    """Dew-point temperature (C) of vapour `y_mass` at `p_bara`.

    Solved as the temperature at which a flash of this overall composition first produces liquid:
    sum_i z_i / K_i(T) = 1 with the liquid taken as the incipient drop.  Bisection on the residual
    keeps it inside the owning model's envelope, same as `bubble_t`."""
    z = _norm_mass(y_mass)
    lo, hi = _vle._T_NODES[0], _vle._T_NODES[-1]

    def _resid(t_c):
        # incipient liquid: iterate x until self-consistent at vapour-fraction -> 1
        x = dict(z)
        for _ in range(40):
            k = k_values(x, t_c, p_bara, y_mole=mass_to_mole(z))
            zz = mass_to_mole(z)
            denom = sum(zz[s] / k[s] for s in VOLATILE if k[s] > 1e-12)
            if denom <= 0.0:
                return -1.0
            x_new_mole = {s: (zz[s] / k[s] / denom if k[s] > 1e-12 else 0.0) for s in VOLATILE}
            for s in NONVOLATILE:
                x_new_mole[s] = 0.0
            nv = sum(zz[s] for s in NONVOLATILE)
            if nv > 0.0:                     # non-volatiles are all in the liquid at the dew point
                for s in NONVOLATILE:
                    x_new_mole[s] = zz[s]
                tot = sum(x_new_mole.values())
                x_new_mole = {s: v / tot for s, v in x_new_mole.items()}
            x_new = mole_to_mass(x_new_mole)
            if max(abs(x_new[s] - x[s]) for s in SPECIES) < 1e-10:
                x = x_new
                break
            x = x_new
        return denom - 1.0

    r_lo, r_hi = _resid(lo), _resid(hi)
    if r_lo * r_hi > 0.0:
        raise OutOfDomain(f"dew point not bracketed in [{lo}, {hi}] C at {p_bara} bar a")
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if _resid(mid) * r_lo > 0.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


# ==================================================================================================
#  Rachford-Rice isothermal flash
# ==================================================================================================

class FlashResult:
    """One converged isothermal flash.  Mass fractions out, to match the engine's species layer."""

    __slots__ = ("psi_mole", "psi_mass", "x", "y", "k", "t_c", "p_bara", "domain",
                 "iterations", "residual", "converged")

    def __init__(self, psi_mole, psi_mass, x, y, k, t_c, p_bara, domain,
                 iterations, residual, converged):
        self.psi_mole = psi_mole
        self.psi_mass = psi_mass
        self.x = x
        self.y = y
        self.k = k
        self.t_c = t_c
        self.p_bara = p_bara
        self.domain = domain
        self.iterations = iterations
        self.residual = residual
        self.converged = converged

    def as_dict(self) -> dict:
        return {"psi_mole": self.psi_mole, "psi_mass": self.psi_mass,
                "x": dict(self.x), "y": dict(self.y), "k": dict(self.k),
                "T_C": self.t_c, "P_bara": self.p_bara, "domain": self.domain,
                "iterations": self.iterations, "residual": self.residual,
                "converged": self.converged, "model": MODEL_NAME}


def _rachford_rice(z_mole: dict, k: dict, iters: int = 80) -> float:
    """Vapour mole fraction psi solving sum_i z_i(K_i-1)/(1+psi(K_i-1)) = 0.

    Bisection on the strictly-decreasing residual: bounded cost, no convergence failure.  An OTS
    tick must never miss its deadline -- the same argument the engine's own HPCC flash uses.

    EVERY species with z_i > 0 enters the sum, INCLUDING the non-volatiles at K_i = 0.  Their term
    is -z_i/(1-psi), which diverges as psi -> 1 and is the only thing that bounds the vapour
    fraction below total vaporisation.  Dropping them (the obvious filter, since K=0 contributes
    nothing at psi=0) let a liquor that is 69 wt% urea flash to psi_mass = 1.0 -- urea cannot
    leave, so the true psi is pinned well below 1 by that term alone."""
    dist = [s for s in SPECIES if z_mole.get(s, 0.0) > 0.0]
    if not dist or all(k.get(s, 0.0) <= 0.0 for s in dist):
        return 0.0

    def g(p):
        return sum(z_mole[s] * (k[s] - 1.0) / (1.0 + p * (k[s] - 1.0)) for s in dist)

    #  psi is capped strictly below 1 whenever a non-volatile is present: at psi = 1 the liquid
    #  vanishes and a non-volatile has nowhere to be, so the residual is singular there.
    z_nv = sum(z_mole.get(s, 0.0) for s in NONVOLATILE)
    hi_cap = (1.0 - 1.0e-9) if z_nv <= 0.0 else (1.0 - max(z_nv * 1.0e-6, 1.0e-9))
    lo, hi = 1.0e-12, hi_cap
    if g(hi) >= 0.0:
        return hi
    if g(lo) <= 0.0:
        return lo
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if g(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


#  ---- quantised flash memo -------------------------------------------------------------------
#  A converged flash costs ~17 ms: the gamma-phi outer loop runs ~20 sweeps and each sweep walks the
#  electrolyte table and an SRK cubic.  The engine integrates at dt = 0.1 s and up to 60x real time,
#  so re-solving three of them every tick is ~500x over budget -- the same wall `vle_nh3co2h2o`
#  documents for calling `speciate` inline, one level up.
#
#  It is also pointless.  A flash is a STATE function of (T, P, z), and those inputs move on stage
#  residence times of 150-600 s, not on the 0.1 s tick.  So the result is memoised against QUANTISED
#  inputs: the solve repeats only once the state has actually moved by more than the quantum.  The
#  quanta are far below both instrument resolution and the model's own accuracy (the electrolyte
#  bubble point carries +1.7 to +17.5 % at these stages), so this bounds a numerical convenience,
#  never a physical response.  Set _FLASH_CACHE_SIZE = 0 to disable and solve every call.
_T_QUANTUM_C = 0.02          # C     -- 25x finer than any TT resolution in the plant
_P_QUANTUM_BARA = 1.0e-4     # bar a -- 100x finer than any PT resolution
_W_QUANTUM = 1.0e-4          # mass fraction -- 100 ppm, ~100x below any composition analyser
_FLASH_CACHE_SIZE = 4096
_flash_cache: dict = {}
#  Warm-start buckets: coarse enough that one stage keeps one entry across its whole operating
#  excursion, fine enough that two different stages never share one.
_WARM_T_BUCKET_C = 10.0
_WARM_P_BUCKET_BARA = 0.5
_warm_start: dict = {}
_flash_cache_stats = {"hit": 0, "miss": 0}


def flash_cache_stats() -> dict:
    """Hit/miss counters for the quantised flash memo (telemetry + tests)."""
    total = _flash_cache_stats["hit"] + _flash_cache_stats["miss"]
    return {"hit": _flash_cache_stats["hit"], "miss": _flash_cache_stats["miss"],
            "entries": len(_flash_cache),
            "hit_rate": (_flash_cache_stats["hit"] / total) if total else 0.0}


def flash_cache_clear() -> None:
    _flash_cache.clear()
    _warm_start.clear()
    _flash_cache_stats["hit"] = 0
    _flash_cache_stats["miss"] = 0


#  Convergence tolerance on the liquid mass fraction.  MEASURED cost/accuracy at 323C003:
#      tol      iters     ms     max |dy| vs a 1e-12 solve
#      1e-9      16      14.0     4.1e-09
#      1e-7      11       8.6     5.3e-07
#      1e-5       6       5.1     6.8e-05
#  1e-7 is seven orders below the model's OWN residual against the PFD (+1.7 to +17.5 % on bubble
#  pressure) and below any composition analyser in the plant, so tightening it further buys nothing
#  physical and costs 60 % more solve time on every miss.
_FLASH_TOL = 1.0e-7


def flash(z_mass: dict, t_c: float, p_bara: float,
          outer_iters: int = 40, tol: float = _FLASH_TOL) -> FlashResult:
    """Memoised isothermal flash -- see `_flash_solve` for the solver itself."""
    if _FLASH_CACHE_SIZE <= 0:
        return _flash_solve(z_mass, t_c, p_bara, outer_iters, tol)
    z = _norm_mass(z_mass)
    key = (round(t_c / _T_QUANTUM_C), round(p_bara / _P_QUANTUM_BARA),
           tuple(round(z[s] / _W_QUANTUM) for s in SPECIES))
    hit = _flash_cache.get(key)
    if hit is not None:
        _flash_cache_stats["hit"] += 1
        return hit
    _flash_cache_stats["miss"] += 1
    fr = _flash_solve(z, t_c, p_bara, outer_iters, tol)
    if len(_flash_cache) >= _FLASH_CACHE_SIZE:
        _flash_cache.clear()                 # cheap generational evict; the working set is tiny
    _flash_cache[key] = fr
    return fr


def _flash_solve(z_mass: dict, t_c: float, p_bara: float,
                 outer_iters: int = 40, tol: float = _FLASH_TOL) -> FlashResult:
    """Isothermal (T, P) flash of overall mass composition `z_mass`.

    gamma-phi outer loop: K depends on the liquid composition through the activity model and on the
    vapour composition through SRK, so the Rachford-Rice solve is wrapped in a successive-
    substitution loop on (x, y) until both are stationary.  Raises OutOfDomain off-envelope.
    """
    z = _norm_mass(z_mass)
    domain = classify(z, t_c, p_bara)
    if domain is None:
        raise OutOfDomain(f"no fitted model owns this state: {domain_report(z, t_c, p_bara)}")
    if domain == DOMAIN_NEUTRAL_UREA:
        #  The neutral binary owns WATER activity in a urea melt and nothing else -- it has no NH3
        #  or CO2 at all.  Their partial pressures would have to come from the electrolyte path, and
        #  in a 97.7 wt% urea / 1.4 wt% water melt that path is not in its dilute limit: the loading
        #  basis is mol per kg of WATER, so 0.04 wt% NH3 reads as 1.69 mol/kg and the flash returns
        #  an NH3 vapour mole fraction of 0.24 for a melt whose vapour is essentially pure steam.
        #  bubble_p / bubble_t stay available here (water-only duty, +2.2 % at 324E003); a VOLATILE
        #  SPLIT does not, so 324E001/E003 keep their anchored vapour vector until a urea-melt
        #  NH3/CO2 solubility source exists.  See gap G-VLE-2 in handoff.md.
        raise OutOfDomain(
            "flash() is not defined on DOMAIN_NEUTRAL_UREA: the neutral binary carries no NH3/CO2 "
            "and the electrolyte path is outside its dilute limit in a urea melt. "
            f"bubble_p/bubble_t remain valid here. {domain_report(z, t_c, p_bara)}")
    z_mole = mass_to_mole(z)
    #  WARM START.  Successive substitution from x = z needs ~22 damped sweeps; from a nearby
    #  converged liquid it needs 2-4.  The engine calls each stage every tick with a composition
    #  that has barely moved, so the previous answer for that stage is an excellent guess.  The
    #  warm cache is keyed on a COARSE (T, P) bucket, which separates the stages from one another
    #  without needing the call site to carry any state.  It changes iteration count only -- the
    #  fixed point of the map is unchanged, and a cold key simply falls back to x = z.
    warm_key = (round(t_c / _WARM_T_BUCKET_C), round(p_bara / _WARM_P_BUCKET_BARA))
    x = dict(_warm_start.get(warm_key) or z)
    if abs(sum(x.values()) - 1.0) > 1.0e-6:                   # guard a corrupt warm entry
        x = dict(z)
    y_mole = None
    psi = 0.0
    psi_prev = float("inf")
    resid = float("inf")
    prev_resid = float("inf")
    damping = _SS_DAMPING
    it = 0
    for it in range(1, outer_iters + 1):
        k = k_values(x, t_c, p_bara, y_mole=y_mole, domain=domain)
        psi = _rachford_rice(z_mole, k)
        x_mole = {}
        y_mole_new = {}
        for s in SPECIES:
            denom = 1.0 + psi * (k[s] - 1.0)
            xs = z_mole[s] / denom if denom > 1e-12 else z_mole[s]
            x_mole[s] = max(xs, 0.0)
            y_mole_new[s] = max(k[s] * xs, 0.0)
        sx = sum(x_mole.values())
        sy = sum(y_mole_new.values())
        if sx > 0.0:
            x_mole = {s: v / sx for s, v in x_mole.items()}
        if sy > 0.0:
            y_mole_new = {s: v / sy for s, v in y_mole_new.items()}
        x_new = mole_to_mass(x_mole)
        #  The residual must include PSI, not only the liquid.  Near the bubble point psi is tiny,
        #  so x ~= z and an x-only criterion is satisfied while psi is still moving -- measured
        #  psi = 1.4e-4 at a state whose true value is ~1e-10.  x alone converges; the pair does not
        #  until the vapour fraction has settled too.
        resid = max(max(abs(x_new[s] - x[s]) for s in SPECIES), abs(psi - psi_prev))
        psi_prev = psi
        #  ADAPTIVE damping.  K depends on x through a speciating electrolyte model whose a_CO2
        #  spans four decades, so the UNDAMPED map oscillates instead of contracting -- measured
        #  non-convergent in 40 sweeps at both 323C003 and 323F004.  But a FIXED 0.5 factor caps the
        #  contraction rate at 0.5 per sweep, which costs ~30 sweeps to reach tol and dominates the
        #  runtime.  So: take the full step while the residual is falling, and halve the factor only
        #  on a sweep that made it worse, relaxing back toward 1 afterwards.  The fixed point of the
        #  map is untouched either way -- this changes iteration count, not the answer.
        if resid > prev_resid:
            damping = max(damping * 0.5, 0.05)
        else:
            damping = min(damping * 1.5, 1.0)
        prev_resid = resid
        x = {s: x[s] + damping * (x_new[s] - x[s]) for s in SPECIES}
        y_mole = y_mole_new
        if resid < tol:
            break
    if resid < tol:
        _warm_start[warm_key] = dict(x)                       # only cache a CONVERGED liquid
    y = mole_to_mass(y_mole) if y_mole else {s: 0.0 for s in SPECIES}
    # mole -> mass vapour fraction
    mw_x = sum(mass_to_mole(x)[s] * MW[s] for s in SPECIES)
    mw_y = sum((y_mole or {}).get(s, 0.0) * MW[s] for s in SPECIES)
    denom = (1.0 - psi) * mw_x + psi * mw_y
    psi_mass = (psi * mw_y / denom) if denom > 0.0 else 0.0
    return FlashResult(psi, psi_mass, x, y, k, t_c, p_bara, domain, it, resid, resid < tol)


# ==================================================================================================
#  isenthalpic (P, H) flash
# ==================================================================================================

def stream_enthalpy_kj_per_kg(w_mass: dict, t_c: float, phase: str) -> float:
    """Absolute specific enthalpy (kJ/kg) on the gap_g6 elements-at-298.15 K datum."""
    w = _norm_mass(w_mass)
    #  1 kg basis: kmol/h numerically equals kmol per kg here, and h0_stream returns an INTENSIVE
    #  kJ/kg, so the arbitrary basis cancels exactly.
    n = {k: w[k] / MW[k] for k in SPECIES if w[k] > 0.0}
    if not n:
        return 0.0
    res = _h0.h0_stream(n, t_c, phase)
    h = res.get("enthalpy_kJkg")
    return float(h) if h is not None else 0.0


def mixture_enthalpy_kj_per_kg(fr: "FlashResult") -> float:
    """Two-phase specific enthalpy of a converged flash, mass-weighted across the phases."""
    h_l = stream_enthalpy_kj_per_kg(fr.x, fr.t_c, "liquid")
    h_v = stream_enthalpy_kj_per_kg(fr.y, fr.t_c, "vapor") if fr.psi_mass > 0.0 else 0.0
    return (1.0 - fr.psi_mass) * h_l + fr.psi_mass * h_v


def flash_ph(z_mass: dict, h_kj_per_kg: float, p_bara: float,
             t_lo: float = None, t_hi: float = None, tol: float = 1.0e-4) -> FlashResult:
    """Isenthalpic (P, H) flash: find T such that the two-phase mixture enthalpy equals `h`.

    This is the letdown-valve boundary -- h_in(T1,P1) = h_out(T2,P2) -- and the replacement for
    every constant Joule-Thomson coefficient in the engine.  Enthalpy is the gap_g6 H0 tier, the
    same datum `make_stream` already publishes, so a PH flash and a published stream enthalpy
    cannot disagree.  Bisection on h(T) - h, which is monotone increasing in T.
    """
    z = _norm_mass(z_mass)
    dom_mid = classify(z, 0.5 * (_vle._T_NODES[0] + _vle._T_NODES[-1]), p_bara)
    if dom_mid == DOMAIN_NEUTRAL_UREA:
        lo_d, hi_d = (_neutral.VALID_TEMPERATURE_K[0] - 273.15,
                      _neutral.VALID_TEMPERATURE_K[1] - 273.15)
    else:
        lo_d, hi_d = _vle._T_NODES[0], _vle._T_NODES[-1]
    lo = lo_d if t_lo is None else max(t_lo, lo_d)
    hi = hi_d if t_hi is None else min(t_hi, hi_d)
    if lo >= hi:
        raise OutOfDomain(f"empty bracket for flash_ph: {domain_report(z, lo, p_bara)}")

    def _h(t_c):
        return mixture_enthalpy_kj_per_kg(flash(z, t_c, p_bara))

    h_lo, h_hi = _h(lo), _h(hi)
    if h_kj_per_kg <= h_lo:
        return flash(z, lo, p_bara)
    if h_kj_per_kg >= h_hi:
        return flash(z, hi, p_bara)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if _h(mid) < h_kj_per_kg:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return flash(z, 0.5 * (lo + hi), p_bara)


def prime():
    """Force the electrolyte table to build/load now so the first engine tick is not charged for it."""
    _vle.prime()
    return MODEL_NAME
