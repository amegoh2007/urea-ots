"""322R001 HP urea-reactor conversion kinetics — quarantined Modified Inoue-Kanai model.

main.py is the state router / WebSocket hub; the per-pass CO2->urea conversion math lives
here, isolated and unit-testable, with ZERO dependency on main.py.

Modified Inoue-Kanai separable equilibrium structure (re-fitted to plant HMB, NOT a
transcription of published I-K polynomial coefficients):

    X(L, W, T) = X_inf * f_L(L) * f_W(W) * f_T(T)

        f_L(L) = a*(L-2) / (1 + a*(L-2))                # NH3-excess saturation (L = N/C molar)
        f_W(W) = 1 / (1 + b*W)                          # water penalty  (W = H/C molar) -- Stamicarbon
        f_T(T) = exp[ -(Ea/R) * (1/T - 1/T0) ]          # Arrhenius, = 1 at design T0

L = 2 is the dehydration stoichiometric floor (2 NH3 + 1 CO2 -> 1 urea + 1 H2O); excess NH3
drives the second (dehydration) step forward and saturates at high L. Product / recycle water
back-shifts the dehydration equilibrium -> the H/C "water penalty" the stripping loop is
sensitive to.

CALIBRATION (anchored to as-built design HMB, no fabrication):
    L0 = 3.072961   (live reactor-feed NH3/CO2 molar at design steady state)
    W0 = 0.407828   (live reactor-feed H2O/CO2 molar at design steady state)
    T0 = 183.0 C    (REACT_OVERFLOW_T_C)
    X_des = 0.543   (xi_urea / CO2_feed = 1302.27 / 2397.7, CO2 per-pass)
    X_inf = 0.85    (high-NH3 low-water equilibrium ceiling)
    b = 0.60        (water-penalty strength)
    a = 3.6180      solved so X(L0,W0,T0) = X_des exactly:
                    f_W(W0) = 1/(1+0.60*0.407828)           = 0.803405
                    f_L(L0) = (X_des/X_inf)/f_W(W0)          = 0.795144
                    a = (1/(L0-2)) * f_L(L0)/(1-f_L(L0))     = 3.6180
    Ea = 10 kJ/mol  gentle T-sensitivity; real conversion has a T-optimum -> parabolic cap is
                    future scope (YAGNI now). T0-pinned in engine (no live bulk-T), so f_T == 1
                    today; Ea is a forward hook for when live bulk-T is wired.

The engine consumes the DIMENSIONLESS ratio X(L,W,T)/X(L0,W0,T0): it equals 1.000000 at design
by construction, so the pinned design HMB (xi_urea = 1302.27) is reproduced bit-exact and the
downstream stripper initialization cannot drift. Off-design, f_L / f_W supply the N/C and H/C
slopes.
"""
import math

# --- calibration constants (tunable; see module docstring) -----------------------------------
R_GAS      = 8.314          # J/(mol*K)
L0_DES     = 3.072961       # design reactor-feed N/C molar  (NH3/CO2), live-probed
W0_DES     = 0.407828       # design reactor-feed H/C molar  (H2O/CO2), live-probed
T0_DES_C   = 183.0          # design reactor bulk temperature, C  (REACT_OVERFLOW_T_C)
X_INF      = 0.85           # thermodynamic conversion ceiling (high NH3, low water)
ALPHA_NC   = 3.6180         # NH3-excess saturation coefficient  (solved to anchor X_des)
BETA_HC    = 0.60           # water-penalty coefficient
EA_JMOL    = 10_000.0       # apparent activation energy, J/mol (gentle f_T; forward hook)
X_DES      = 0.543          # as-built design per-pass CO2 conversion (display anchor)

_T0_K = T0_DES_C + 273.15


def inoue_kanai_X(L: float, W: float, T_c: float = T0_DES_C) -> float:
    """Absolute per-pass CO2->urea conversion X(L, W, T).

    L   = reactor-feed N/C molar (NH3/CO2)
    W   = reactor-feed H/C molar (H2O/CO2)
    T_c = reactor bulk temperature, deg C
    """
    g  = max(L - 2.0, 0.0)                                    # excess NH3 above dehydration floor
    fL = (ALPHA_NC * g) / (1.0 + ALPHA_NC * g)               # saturation
    fW = 1.0 / (1.0 + BETA_HC * W)                           # water penalty
    fT = math.exp(-(EA_JMOL / R_GAS) * (1.0 / (T_c + 273.15) - 1.0 / _T0_K))
    return X_INF * fL * fW * fT


# normalization anchor: X at the exact design feed -> ratio is 1.000000 at design SS
X_DES_RAW = inoue_kanai_X(L0_DES, W0_DES, T0_DES_C)


def conversion_factor(L: float, W: float, T_c: float = T0_DES_C) -> float:
    """X(L,W,T) / X(L0,W0,T0). Exactly 1.0 at the design feed; HMB-preserving."""
    return inoue_kanai_X(L, W, T_c) / X_DES_RAW


def react_couple(feed: dict, overflow_scaled: dict, xi_urea_scaled: float,
                 T_c: float = T0_DES_C):
    """Couple conversion to the pinned split-fraction overflow, atom-conserving.

    Inputs (from react_322r001):
        feed            : reactor-feed composition, kmol/h  (hpcc["feed_kmolh"])
        overflow_scaled : pinned overflow = REACT_OVERFLOW_DES * s * (phi/phi_des), kmol/h
        xi_urea_scaled  : pinned urea extent = REACT_XI_UREA_DES * s, kmol/h
        T_c             : reactor bulk temperature, deg C (design-pinned today)

    Returns (xi_urea, overflow_adjusted, X, L, W):
        xi_urea          = xi_urea_scaled * conversion_factor(L, W, T)
        overflow_adjusted shifts by d = xi_urea - xi_urea_scaled per
            CO2 + 2 NH3 -> Urea + H2O :  Urea +d,  CO2 -d,  NH3 -2d,  H2O +d
        (total-mole closure_resid is invariant under this shift)
    """
    co2 = feed.get("CO2", 0.0)
    if co2 <= 0.0:                                            # degenerate guard
        return xi_urea_scaled, dict(overflow_scaled), X_DES_RAW, L0_DES, W0_DES
    L = feed.get("NH3", 0.0) / co2
    W = feed.get("H2O", 0.0) / co2
    xi_urea = xi_urea_scaled * conversion_factor(L, W, T_c)
    d = xi_urea - xi_urea_scaled                             # extra urea vs pinned design
    ov = dict(overflow_scaled)
    ov["Urea"] = ov.get("Urea", 0.0) + d
    ov["CO2"]  = ov.get("CO2",  0.0) - d
    ov["NH3"]  = ov.get("NH3",  0.0) - 2.0 * d
    ov["H2O"]  = ov.get("H2O",  0.0) + d
    return xi_urea, ov, inoue_kanai_X(L, W, T_c), L, W
