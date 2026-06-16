"""322R001 HP urea-reactor conversion kinetics — quarantined Modified Inoue-Kanai model.

main.py is the state router / WebSocket hub; the per-pass CO2->urea conversion math lives
here, isolated and unit-testable, with ZERO dependency on main.py.

Modified Inoue-Kanai separable equilibrium structure (re-fitted to plant HMB, NOT a
transcription of published I-K polynomial coefficients):

    X(L, W, T) = min( X_inf * f_L(L) * f_W(W) * f_T(T),  X_inf )      # Guard 2 thermo re-clamp

        f_L(L) = a*(L-2) / (1 + a*(L-2))                # NH3-excess saturation (L = N/C molar)
        f_W(W) = 1 / (1 + b*W)                          # water penalty  (W = H/C molar) -- Stamicarbon
        f_T(T) = exp[ -k ( (T-Topt)^2 - (T0-Topt)^2 ) ] # Guard 1 renormalized parabola, = 1 at T0
                 Topt = Topt(L) in [185, 195] C         # N/C-dependent optimum (excess NH3 lifts it)

L = 2 is the dehydration stoichiometric floor (2 NH3 + 1 CO2 -> 1 urea + 1 H2O); excess NH3
drives the second (dehydration) step forward and saturates at high L. Product / recycle water
back-shifts the dehydration equilibrium -> the H/C "water penalty" the stripping loop is
sensitive to.

CALIBRATION (anchored to as-built design HMB, no fabrication):
    L0 = 3.072961   (live reactor-feed NH3/CO2 molar at design steady state)
    W0 = 0.407828   (live reactor-feed H2O/CO2 molar at design steady state)
    T0 = 183.0 C    (REACT_OVERFLOW_T_C)
    X_des = 0.543   (xi_urea / CO2_feed = 1302.27 / 2397.7, CO2 per-pass)
    a = 3.6180      NH3-excess saturation coeff -- FROZEN: sets the f_L N/C slope (test_1_nc_shift).
                    f_L(L0) = a*(L0-2)/(1+a*(L0-2))          = 0.795165
    b = 0.85        water-penalty strength -- calibrated UP from 0.60 for an aggressive Stamicarbon
                    H/C penalty.  f_W(W0) = 1/(1+0.85*0.407828) = 0.742582
    X_inf = 0.9196  high-NH3 low-water ceiling -- now SOLVED (was 0.85) to hold the anchor with a,b
                    fixed, giving f_W the headroom a stronger b needs (else f_L/f_W fight one budget):
                    X_inf = X_des/(f_L(L0)*f_W(W0)) = 0.543/(0.795165*0.742582) = 0.9196
    k = 0.0015      parabolic T-penalty curvature, 1/C^2.  f_T peaks at Topt(L) and falls either
       (1/C^2)      side -> over-temperature equilibrium REVERSAL.  At the (L=1000,W=0) corner the
                    conversion holds ~91.96% (X_inf ceiling) up to ~207 C, then drops to ~30% by
                    225 C and collapses past 250 C -> a noticeable drop is already visible by 210 C.
    Topt(L)         N/C-dependent optimum = clip(185 + 2*(L-2), 185, 195) C.  Excess NH3 drives the
                    endothermic dehydration step, lifting the optimum; design L0 -> ~187 C, so the
                    design T0 = 183 C sits on the RISING flank (below the peak), not on it.
    GUARD 1         the (T0-Topt)^2 offset pins f_T(T0) = 1.0 for ANY Topt -> design HMB bit-exact
                    (conversion_factor == 1.000000 at design, downstream stripper init cannot drift).
    GUARD 2         hard re-clamp X = min(X_inf*fL*fW*fT, X_inf): the thermodynamic ceiling is
                    honored even where the parabola peak pushes f_T > 1 near Topt.  This closes the
                    old unbounded-Arrhenius hole (X > X_inf -> cf > 1.0 -> phantom conversion).

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
X_INF      = 0.9196         # thermodynamic conversion ceiling -- SOLVED to hold X_des with a,b fixed (was 0.85)
ALPHA_NC   = 3.6180         # NH3-excess saturation coefficient  (FROZEN -- sets f_L slope, see test_1)
BETA_HC    = 0.85           # water-penalty coefficient (aggressive Stamicarbon H/C penalty; was 0.60)
K_TOPT     = 0.0015         # parabolic T-penalty curvature, 1/C^2 (noticeable conversion drop by 210 C)
T_OPT_LO_C = 185.0          # lower bound of the N/C-dependent conversion optimum, C
T_OPT_HI_C = 195.0          # upper bound of the conversion optimum, C
T_OPT_GAMMA = 2.0           # dTopt / d(N/C) above the dehydration floor L=2, C per N/C unit (pre-clip)
X_DES      = 0.543          # as-built design per-pass CO2 conversion (display anchor)

def t_opt_c(L: float) -> float:
    """N/C-dependent optimum reactor temperature, deg C, clamped to [T_OPT_LO_C, T_OPT_HI_C].

    Excess NH3 (higher N/C = higher L) drives the endothermic dehydration step, lifting the
    conversion optimum; clipped to the physical band.  Design L0 -> ~187 C, so the design point
    T0 = 183 C sits on the RISING flank below the peak (not on it).
    """
    return min(max(T_OPT_LO_C + T_OPT_GAMMA * (L - 2.0), T_OPT_LO_C), T_OPT_HI_C)


def f_T_parabola(T_c: float, L: float) -> float:
    """Guard 1 -- renormalized parabolic temperature penalty (replaces the unbounded Arrhenius f_T).

        f_T(T) = exp[ -k ( (T - Topt)^2 - (T0 - Topt)^2 ) ]

    Peaks at T = Topt(L) (bounded value exp[k (T0 - Topt)^2]) and falls symmetrically either side
    -> over-temperature equilibrium reversal.  The (T0 - Topt)^2 offset pins f_T(T0) = 1.0 for ANY
    Topt, so the design HMB anchor (conversion_factor = 1.0 at T0) is bit-exact regardless of L.
    """
    topt = t_opt_c(L)
    return math.exp(-K_TOPT * ((T_c - topt) ** 2 - (T0_DES_C - topt) ** 2))


def inoue_kanai_X(L: float, W: float, T_c: float = T0_DES_C) -> float:
    """Absolute per-pass CO2->urea conversion X(L, W, T).

    L   = reactor-feed N/C molar (NH3/CO2)
    W   = reactor-feed H/C molar (H2O/CO2)
    T_c = reactor bulk temperature, deg C
    """
    g  = max(L - 2.0, 0.0)                                    # excess NH3 above dehydration floor
    fL = (ALPHA_NC * g) / (1.0 + ALPHA_NC * g)               # saturation
    fW = 1.0 / (1.0 + BETA_HC * W)                           # water penalty
    fT = f_T_parabola(T_c, L)                                # Guard 1: renormalized T-optimum parabola
    return min(X_INF * fL * fW * fT, X_INF)                  # Guard 2: hard thermodynamic re-clamp


# normalization anchor: X at the exact design feed -> ratio is 1.000000 at design SS
X_DES_RAW = inoue_kanai_X(L0_DES, W0_DES, T0_DES_C)


def conversion_factor(L: float, W: float, T_c: float = T0_DES_C) -> float:
    """X(L,W,T) / X(L0,W0,T0). Exactly 1.0 at the design feed; HMB-preserving."""
    return inoue_kanai_X(L, W, T_c) / X_DES_RAW


def react_couple(feed: dict, overflow_scaled: dict, xi_urea_scaled: float,
                 T_c: float = T0_DES_C, L_override: float = None, W_override: float = None):
    """Couple conversion to the pinned split-fraction overflow, atom-conserving.

    Inputs (from react_322r001):
        feed            : reactor-feed composition, kmol/h  (hpcc["feed_kmolh"])
        overflow_scaled : pinned overflow = REACT_OVERFLOW_DES * s * (phi/phi_des), kmol/h
        xi_urea_scaled  : pinned urea extent = REACT_XI_UREA_DES * s, kmol/h
        T_c             : reactor bulk temperature, deg C (design-pinned today)
        L_override      : if given, drive f_L off this N/C (loop-coupled, blended L) instead of the
                          raw feed N/C. None -> pure feed N/C (unit-test path).
        W_override      : if given, drive f_W off this H/C (loop-coupled, blended W) instead of the
                          raw feed H/C. None -> pure feed H/C (unit-test path).

    Returns (xi_urea, overflow_adjusted, X, L, W):
        xi_urea          = xi_urea_scaled * conversion_factor(L, W, T)
        overflow_adjusted shifts by d = xi_urea - xi_urea_scaled per
            CO2 + 2 NH3 -> Urea + H2O :  Urea +d,  CO2 -d,  NH3 -2d,  H2O +d
        (total-mole closure_resid is invariant under this shift)
    """
    co2 = feed.get("CO2", 0.0)
    if co2 <= 0.0:                                            # degenerate guard
        return xi_urea_scaled, dict(overflow_scaled), X_DES_RAW, L0_DES, W0_DES
    L = (feed.get("NH3", 0.0) / co2) if L_override is None else L_override
    W = (feed.get("H2O", 0.0) / co2) if W_override is None else W_override
    xi_urea = xi_urea_scaled * conversion_factor(L, W, T_c)
    d = xi_urea - xi_urea_scaled                             # extra urea vs pinned design
    ov = dict(overflow_scaled)
    # GAP #5 fix: bound the stoichiometric shift by what the overflow tear stream actually holds.
    # overflow_scaled shrinks with phi (HV-322605), but d scales only with co2_scale -> at phi -> 0
    # the unclamped shift drove ov["NH3"]/ov["CO2"] NEGATIVE (phantom mass into the stripper feed).
    # The shift consumes CO2 + 2 NH3 when d>0 (forward) or Urea + H2O when d<0 (reverse): cap d so
    # every touched component stays >= 0.  Atom closure is preserved (same stoichiometric vector).
    if d > 0.0:
        d = min(d, ov.get("CO2", 0.0), 0.5 * ov.get("NH3", 0.0))
    elif d < 0.0:
        d = max(d, -ov.get("Urea", 0.0), -ov.get("H2O", 0.0))
    xi_urea = xi_urea_scaled + d                             # report the extent actually realized
    ov["Urea"] = ov.get("Urea", 0.0) + d
    ov["CO2"]  = ov.get("CO2",  0.0) - d
    ov["NH3"]  = ov.get("NH3",  0.0) - 2.0 * d
    ov["H2O"]  = ov.get("H2O",  0.0) + d
    return xi_urea, ov, inoue_kanai_X(L, W, T_c), L, W


# --- Fix-1: distributed 4-node axial thermal profile (Damköhler-shaped carbamate exotherm) -----
# The reactor is a vertical liquid plug-flow column: cold HPCC two-phase product enters the bottom
# (T_feed) and the carbamate condensation exotherm (2 NH3 + CO2 -> NH2COONH4, exothermic) is
# released as the plug rises, against the mildly endothermic dehydration (-> urea + H2O), giving a
# STRICTLY MONOTONE bottom->top temperature rise that anchors at the overflow lip (T_overflow).
#
# The engine integrates the lumped node energy balance (main.py.step_sim):
#
#     dT_n/dt = [ (T_{n-1} - T_n) + g_n * ΔT_col ] / τ_n ,   T_0 = T_feed ,   n = 1..N
#
# whose steady state collapses to  T_n = T_feed + ΔT_col * G_raw(ζ_n)  (telescoping the g_n), where
# ΔT_col = (T_overflow_des - T_feed_des) * conversion_factor  (-> the profile FLEXES with conversion)
# and G_raw is the cumulative Damköhler heat-release fraction below the dimensionless elevation ζ.
#
# G_raw is the UN-normalised first-order approach  G_raw(ζ) = 1 - exp(-β ζ):  this reproduces the
# as-built residence-time probe temperatures bit-exact (β = τ_tot/τ_therm), while the top-node->lip
# freeboard residual  g_ov = 1 - G_raw(ζ_top) = exp(-β ζ_top)  carries the remaining release so that
# Σ_n g_n + g_ov = 1  ==>  T_overflow = T_feed + ΔT_col exactly (HMB-anchored).  Normalising to
# G(1)=1 would lift the interior probes ~0.1 C off the as-built profile, so it is deliberately NOT
# applied (the top thermowell sits at ζ_top < 1, below the overflow lip).

def damkohler_G(zeta: float, beta: float) -> float:
    """Cumulative Damköhler heat-release fraction below dimensionless elevation ζ (0..1).

    G_raw(ζ) = 1 - exp(-β ζ).  Monotone increasing, G(0)=0; UN-normalised (G(1)<1) so the node
    temperatures match the as-built residence-time probe bit-exact and the freeboard residual is
    carried by g_ov (see module note).  β = τ_tot/τ_therm (column residence / exotherm time const).
    """
    return 1.0 - math.exp(-beta * zeta)


def node_heat_weights(zeta_nodes, beta):
    """Per-node fractional heat-release weights for the distributed exotherm.

    Returns (g_nodes, g_ov):
        g_nodes[n] = G_raw(ζ_n) - G_raw(ζ_{n-1})   (release between node n-1 and node n; ζ_0 = 0)
        g_ov       = 1 - G_raw(ζ_top)              (top-node -> overflow-lip freeboard release)
    All strictly positive (G_raw monotone), and Σ g_nodes + g_ov = 1 (anchors T_overflow).
    """
    g_nodes = []
    prev = 0.0
    for z in zeta_nodes:
        gz = damkohler_G(z, beta)
        g_nodes.append(gz - prev)
        prev = gz
    g_ov = 1.0 - prev
    return g_nodes, g_ov


def node_profile_ss(t_feed: float, t_overflow: float, zeta_nodes, beta):
    """Steady-state node temperatures  T_n = t_feed + (t_overflow - t_feed) * G_raw(ζ_n).

    Used to seed the dynamic react_T_node state at the as-built design profile (bit-exact to the
    old static residence-time probe), so the design steady state is reproduced on init.
    """
    dT = t_overflow - t_feed
    return [t_feed + dT * damkohler_G(z, beta) for z in zeta_nodes]


# === Fix-2: stagnant-flow thermal & hydraulic decoupling =======================================
# Stagnant Flow Freeze fix.  The bare adiabatic node RHS (dT/dt -> 0 at m_dot -> 0) and the
# algebraic level pass-through (m_out == m_in) lacked two ALWAYS-physical mechanisms:
#   (A) ambient wall heat loss              -> a no-flow reactor relaxes to T_ambient (un-freezes T)
#   (B) hydraulic weir + thermal contraction-> outlet decoupled from inlet; cold liquid shrinks
#                                              below the weir lip (un-freezes level)
# Both are ANCHOR-SAFE: zero contribution at design steady state, so the pinned design HMB (profile
# 172->183, design level) stays bit-exact; they only wake up off-design / at low flow.

T_AMBIENT_C   = 40.0      # plant-frame ambient seen by the reactor shell, deg C (tunable)
TAU_LOSS_S    = 21600.0   # bulk wall-loss time constant tau_loss = m c_p/(U A), s (~6 h, insulated HP shell)
M_HOLDUP_MIN  = 1.0       # kg, holdup floor -> guards 1/m_n divide-by-zero on an emptied node

# hydraulic weir / liquid inventory (Francis weir, exponent 3/2) -- defaults ILLUSTRATIVE, match to plant geometry
TANK_AREA_M2  = 5.31      # reactor liquid cross-section, m^2 (Ø ~2.6 m)                    (tunable)
WEIR_CREST_M  = 18.0      # overflow-lip elevation above the level datum, m == UI "100 %" lip (tunable)
WEIR_CW       = 9.0e3     # lumped Francis coeff Cd*(2/3)*sqrt(2g)*b, m^3/h per m^1.5 (sets design head; tunable)

# melt density rho(T) = rho_ref [1 - beta (T - T_ref)]  (carbamate / urea / NH3 melt)
RHO_REF       = 990.0     # kg/m^3 at T_ref (= T0_DES_C, design bulk); == REACT_OVERFLOW_RHO (urea soln)
BETA_THERMAL  = 7.0e-4    # 1/K volumetric thermal-expansion coeff (cooling -> contraction -> level drop)


def liquid_density(T_c: float, rho_ref: float = RHO_REF,
                   beta: float = BETA_THERMAL, T_ref: float = T0_DES_C) -> float:
    """Melt density rho(T) = rho_ref [1 - beta (T - T_ref)], kg/m^3, guarded strictly positive.

    Cooling (T < T_ref) RAISES rho -> a fixed liquid mass occupies LESS volume -> the level drops:
    the mechanism that pulls a stagnant reactor's level below the weir lip as it cools.
    """
    return max(rho_ref * (1.0 - beta * (T_c - T_ref)), 1.0e-3)


def node_tau_s(holdup_kg: float, m_dot_kgph: float) -> float:
    """Flow residence time tau_n = holdup / m_dot, seconds.

    ZERO-FLOW GUARD: m_dot <= 0 returns +inf (NOT a divide-by-zero); node_dTdt reads +inf as
    'no advective / exotherm coupling' and zeroes the flow term.  Holdup floored by M_HOLDUP_MIN.
    """
    if m_dot_kgph <= 0.0:
        return float("inf")
    return 3600.0 * max(holdup_kg, M_HOLDUP_MIN) / m_dot_kgph


def node_dTdt(T_n: float, T_below: float, g_n: float, dT_col: float,
              tau_n: float, flow_frac: float,
              T_amb: float = T_AMBIENT_C, tau_loss: float = TAU_LOSS_S) -> float:
    """4-node energy-balance RHS with the Fix-2 ambient-loss term (replaces the bare adiabatic RHS).

        dT_n/dt = [ (T_below - T_n) + g_n * dT_col ] / tau_n        # flow-driven, -> 0 as m_dot -> 0
                  - (1 - flow_frac) * (T_n - T_amb) / tau_loss      # always-on wall loss, GATED

    flow_frac = clip(m_dot / m_dot_des, 0, 1).  The gate (1 - flow_frac) is EXACTLY 0 at design flow
    -> the as-built profile (exotherm fit already nets out design-flow wall loss) is bit-exact; it
    opens to FULL strength as flow collapses, so a stagnant reactor (flow term -> 0) relaxes
    dT_n/dt = -(T_n - T_amb)/tau_loss -> T_amb.  Zero-flow safe: tau_n = +inf zeroes the flow term.
    """
    if math.isfinite(tau_n) and tau_n > 0.0:
        flow_term = ((T_below - T_n) + g_n * dT_col) / tau_n
    else:
        flow_term = 0.0
    gate = min(max(1.0 - flow_frac, 0.0), 1.0)
    loss_term = gate * (T_n - T_amb) / tau_loss
    return flow_term - loss_term


def weir_outflow_kgph(level_m: float, T_bulk_c: float,
                      crest_m: float = WEIR_CREST_M, cw: float = WEIR_CW) -> float:
    """Francis-weir overflow mass rate, kg/h, DECOUPLED from the inlet.

        H     = max(0, level_m - crest_m)     # head over the lip (no backflow below it)
        Q_out = cw * H^{3/2}                   # m^3/h  (Francis: Cd*(2/3)*sqrt(2g)*b)
        m_out = rho(T_bulk) * Q_out            # kg/h

    Below the lip (H = 0) the reactor cannot discharge -> m_out = 0, so when inflow stops the level
    parks AT the lip and the holdup freezes; subsequent cooling (rho up) drops it below.  At design
    the level self-seeks the head where m_out == m_in -> steady overflow == inlet EMERGES, not imposed.
    """
    head = max(0.0, level_m - crest_m)
    q_vol = cw * head ** 1.5
    return liquid_density(T_bulk_c) * q_vol


def level_from_holdup(m_liq_kg: float, T_bulk_c: float, area_m2: float = TANK_AREA_M2) -> float:
    """Liquid level, m, from conserved holdup mass and temperature-dependent density:

        level = V / A = m_liq / ( rho(T_bulk) * A )

    Level is a state of the CONSERVED holdup mass (not a flow pass-through): as rho(T) rises on
    cooling, the same mass reads a LOWER level -> thermal contraction drops it below the weir lip.
    """
    return m_liq_kg / (liquid_density(T_bulk_c) * max(area_m2, 1.0e-6))


def holdup_dmdt_kgph(m_in_kgph: float, level_m: float, T_bulk_c: float,
                     crest_m: float = WEIR_CREST_M, cw: float = WEIR_CW) -> float:
    """Liquid-inventory mass-balance RHS, kg/h:  d(m_liq)/dt = m_in - m_weir_out(level, T).

    OUTLET is the level-driven weir, NOT the inlet -> inlet and outlet decoupled.  Euler in step_sim:
        m_liq += holdup_dmdt_kgph(m_in, level, T_bulk, crest_m, cw) * dt_h
        level  = level_from_holdup(m_liq, T_bulk)
    crest_m / cw are threaded through to weir_outflow_kgph so the caller can supply the plant-anchored
    weir geometry (design head -> design overflow == inlet -> dm/dt = 0, bit-exact at design).
    Reaction mass change is interior to the closed column atom balance and omitted here.
    """
    return m_in_kgph - weir_outflow_kgph(level_m, T_bulk_c, crest_m=crest_m, cw=cw)
