"""Steam-system dynamics — quarantined utility module (HP-loop steam balance).

Zero dependency on main.py / reactor.py / controllers.py.

Two lumped steam headers integrated by explicit Euler at the host dt:

    MP header (25 bar):  supply (utility import) -> stripper reboiler + MP->LP let-down
    LP header (4.4 bar): HPCC-generated steam + let-down + desuperheat water -> LP users

Valve flows use the standard incompressible orifice law shared by the rest of the
sim (LV-322501 drain, HV-322604 vent):

    m_dot = K * (valve%/100) * sqrt(max(P_up - P_down, 0))      [kg/s]

Header pressure is a lumped capacitance C [ (kg/s) per bar ]:

    dP/dt = (sum m_in - sum m_out) / C                          [bar/s]

Desuperheating water on the let-down (MP attemperator to saturated LP):

    m_water = m_ld * (h_MP - h_LP) / (h_LP - h_w)
"""
from dataclasses import dataclass

# ---------------------------------------------------------------- enthalpies (kJ/kg)
H_MP = 2800.0     # superheated MP steam (~25 bar supply header)
H_W  = 420.0      # desuperheating condensate water (~100 C, BFW)
H_LP = 2740.0     # saturated LP steam (~4.4 bar)

# ---------------------------------------------------------------- network boundary + valve sizing
P_EXT_MP_BARA = 40.0    # utility/import MP header upstream of the main supply valve (bar a)
K_SUPPLY      = 5.0     # MP supply valve flow coeff   [ (kg/s) / sqrt(bar) ]
K_LETDOWN     = 2.0     # MP->LP let-down valve coeff   [ (kg/s) / sqrt(bar) ]

# ---------------------------------------------------------------- header capacitance ( (kg/s)/bar )
C_MP = 25.0       # MP header lumped capacitance (vapour inventory) -> slow accumulation
C_LP = 25.0       # LP header lumped capacitance

# ---------------------------------------------------------------- LP make-up floor (site LP-main tie-in)
#   The LP header is backed by the plant LP steam main through a low-pressure make-up PIC: when local
#   generation (HPCC steam raising) collapses -- e.g. a CO2-feed cut zeroes the carbamate condensation
#   duty -> m_hpcc_gen=0 -- the make-up station imports steam from the site main and CLAMPS the header
#   at its setpoint.  Without it the header (with the let-down held at a fixed opening and a fixed
#   stripper draw on MP) drains to vacuum, dragging the HPCC shell saturation temp -- and hence
#   TT-322010 -- to ~4 C, which is unphysical.  Set just below design (HPCC_STEAM_P_BARA=4.4) so the
#   make-up only acts on a genuine deficit and the design steady state is untouched.
P_LP_MIN_BARA = 3.5     # bar a, minimum LP header pressure held by the make-up PIC (Tsat ~= 138.6 C)

# ---------------------------------------------------------------- LP header pressure regulation (PIC)
#   The two headers are pure capacitive integrators (dP/dt = net_flow / C).  With FIXED manual valve
#   openings and a fixed user draw, any residual net-flow offset integrates without bound -- the LP
#   header drifts open-loop to the let-down choke (~24 bar), so once a disturbance un-gates the shell
#   coupling, t_shell = Tsat(P_LP) jumps to ~221 C and re-arms the reactor runaway.  A real LP header
#   is held at setpoint by a pressure controller that VENTS excess to flare/condenser when high and
#   pulls MAKE-UP from the site LP main when low.  Modelled here as a proportional vent/make-up flow:
#
#       m_pic = K_PIC_LP * (P_LP - P_LP_SP_BARA)  +  KI_PIC_LP * INT(P_LP - P_LP_SP_BARA) dt   [kg/s]
#                                                                       (>0 vent excess, <0 make-up)
#
#   PROPORTIONAL term: at the design pressure (P_LP == P_LP_SP_BARA) it is identically 0, and the
#   integral accumulator starts at 0, so the FIRST-tick design mass balance -- and the published HMB --
#   is bit-for-bit unchanged (Option-1 calibration point).  Closed P-loop tau = C_LP / K_PIC_LP ~= 3.1s.
#   INTEGRAL term: a proportional-only PIC leaves a steady offset against any standing imbalance (here a
#   small ~0.85 kg/s HPCC-duty mismatch between the boot-pin frozen-steam capture and the live steady
#   state), which would settle P_LP ~= 4.29 and round the telemetry to 4.3.  The integral trim nulls
#   that offset so the header is held at EXACTLY 4.4 -- a real LP pressure controller is PI, not P.
#   Tuned slightly over-damped (Ki < Kp^2/(4*C_LP)=0.64 -> no overshoot); anti-windup clamps the
#   integral contribution to +/- M_PIC_CLAMP so a sustained generation collapse cannot wind it up.
P_LP_SP_BARA = 4.4      # bar a, LP header pressure setpoint (== design HPCC_STEAM_P_BARA)
K_PIC_LP     = 8.0      # proportional vent/make-up gain   [ (kg/s) / bar ]
KI_PIC_LP    = 0.4      # integral vent/make-up gain        [ (kg/s) / (bar.s) ]
M_PIC_CLAMP  = 10.0     # anti-windup clamp on the integral contribution [ kg/s ]

# ---------------------------------------------------------------- fixed LP design consumer
M_USERS_LP = 7.66       # kg/s, lumped LP-steam users (held constant for now)

# ---------------------------------------------------------------- design throughputs (probe / seed)
M_STRIP_DES = 5.0       # kg/s, design MP steam consumed by HP-stripper reboiler
M_HPCC_DES  = 3.0       # kg/s, design LP steam raised in the HP carbamate condenser


@dataclass
class SteamState:
    P_MP: float = 25.0              # MP header pressure (bar a)
    P_LP: float = 4.4               # LP header pressure (bar a)
    valve_supply_pct: float = 50.0  # main MP supply valve opening (%)
    valve_letdown_pct: float = 50.0 # MP->LP let-down valve opening (%)
    # last-tick diagnostics (telemetry / probe read-back)
    m_supply: float = 0.0           # kg/s
    m_ld: float = 0.0               # kg/s
    m_water: float = 0.0            # kg/s
    m_pic: float = 0.0              # kg/s, LP PIC vent(+)/make-up(-) flow
    i_pic: float = 0.0              # bar.s, LP PIC integral accumulator


def _valve_flow(K: float, opening_pct: float, p_up: float, p_down: float) -> float:
    """Incompressible orifice flow (kg/s). Clamps opening to [0,100] and dP to >=0."""
    op = max(0.0, min(100.0, opening_pct))
    dP = max(p_up - p_down, 0.0)
    return K * (op / 100.0) * dP ** 0.5


def step_steam(state: SteamState, dt: float,
               m_strip_consume: float, m_hpcc_gen: float) -> SteamState:
    """Advance the MP/LP steam headers one Euler tick.

    Args:
        state            : SteamState (mutated in place and returned).
        dt               : timestep (s).
        m_strip_consume  : MP steam drawn by the stripper reboiler (kg/s).
        m_hpcc_gen       : LP steam raised in the HPCC (kg/s).
    """
    # forward MP supply (utility header -> MP) and MP->LP let-down
    m_supply = _valve_flow(K_SUPPLY,  state.valve_supply_pct,  P_EXT_MP_BARA, state.P_MP)
    m_ld     = _valve_flow(K_LETDOWN, state.valve_letdown_pct, state.P_MP,    state.P_LP)

    # desuperheating water needed to bring let-down MP steam to saturated LP
    m_water = m_ld * (H_MP - H_LP) / (H_LP - H_W)

    # MP header mass balance:  in = supply ; out = stripper + let-down
    dP_MP = (m_supply - m_strip_consume - m_ld) / C_MP
    # LP header PIC: PI vent/make-up that drives the header back to setpoint. The proportional part is
    #   zero -- and the integral starts at zero -- at the design pressure (P_LP == P_LP_SP_BARA), so the
    #   calibrated design balance is untouched; the integral nulls any standing offset to hold 4.4 exact.
    err = state.P_LP - P_LP_SP_BARA
    state.i_pic += err * dt
    # anti-windup: clamp the integral so its contribution stays within +/- M_PIC_CLAMP
    state.i_pic = max(-M_PIC_CLAMP / KI_PIC_LP, min(M_PIC_CLAMP / KI_PIC_LP, state.i_pic))
    m_pic = K_PIC_LP * err + KI_PIC_LP * state.i_pic
    # LP header mass balance:  in = HPCC + let-down + desuperheat water ; out = users + PIC vent
    dP_LP = (m_hpcc_gen + m_ld + m_water - M_USERS_LP - m_pic) / C_LP

    state.P_MP = max(0.0, state.P_MP + dt * dP_MP)
    # LP make-up PIC: header cannot fall below P_LP_MIN_BARA -- the site LP-main tie-in imports
    #   steam to hold the floor when local HPCC generation collapses (e.g. CO2-feed cut), so the
    #   HPCC shell saturation temp (-> TT-322010) stays physical instead of crashing toward vacuum.
    state.P_LP = max(P_LP_MIN_BARA, state.P_LP + dt * dP_LP)

    state.m_supply, state.m_ld, state.m_water, state.m_pic = m_supply, m_ld, m_water, m_pic
    return state


# ==================================================================== isolated probe
if __name__ == "__main__":
    DT = 0.1

    def run(label, valve_supply, n=3000):
        st = SteamState()
        st.valve_supply_pct = valve_supply
        traj = []
        for k in range(n):
            step_steam(st, DT, M_STRIP_DES, M_HPCC_DES)
            if k % 300 == 0:
                traj.append((round(k * DT, 1), round(st.P_MP, 3), round(st.P_LP, 3)))
        print(f"\n  {label}  (valve_supply={valve_supply}%)")
        print(f"    {'t [s]':>8}{'P_MP':>10}{'P_LP':>10}")
        for t, pmp, plp in traj:
            print(f"    {t:>8}{pmp:>10}{plp:>10}")
        print(f"    final: P_MP={st.P_MP:.3f}  P_LP={st.P_LP:.3f}  "
              f"m_supply={st.m_supply:.3f}  m_ld={st.m_ld:.3f}")
        return st

    print("=" * 40)
    print("  STEAM-SYSTEM ISOLATED PROBE")
    print("=" * 40)

    base = run("baseline 50% supply", 50.0)
    crash = run("supply valve -> 0%", 0.0)

    assert crash.P_MP < 1.0, f"FAIL: P_MP did not crash (={crash.P_MP:.3f})"
    assert crash.P_MP < base.P_MP, "FAIL: closing supply did not lower P_MP"
    print("\n  PASS: supply valve 0% -> P_MP crashes toward 0.")
    print("=" * 40)
