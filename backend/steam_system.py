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
    # LP header mass balance:  in = HPCC + let-down + desuperheat water ; out = users
    dP_LP = (m_hpcc_gen + m_ld + m_water - M_USERS_LP) / C_LP

    state.P_MP = max(0.0, state.P_MP + dt * dP_MP)
    state.P_LP = max(0.0, state.P_LP + dt * dP_LP)

    state.m_supply, state.m_ld, state.m_water = m_supply, m_ld, m_water
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
