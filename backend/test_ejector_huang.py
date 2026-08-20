"""Validation gate for the Huang 1-D ejector compressible-flow core (ejector_huang.py, gap C40).

The isentropic, choked-flow and normal-shock relations are checked against standard gas-dynamics tables
(gamma=1.4 air-standard) -- values every compressible-flow text lists -- so passing proves the physics
core is correct. The entrainment/breakdown assembly is checked for the right qualitative behaviour. What
is NOT asserted (and cannot be, without fabrication) is a specific plant entrainment number: that needs
the vendor throat/exit/mixing areas and downstream tie pressures.

Run from backend/:  python -m pytest test_ejector_huang.py   (or: python test_ejector_huang.py)
"""
import math

import ejector_huang as E


# ------------------------------------------------------------- isentropic relations vs gas tables
def test_critical_pressure_ratio():
    """P*/P0 = 0.5283 for gamma=1.4 (air) and 0.5399 for gamma=1.3 -- standard table values."""
    assert abs(E.critical_pressure_ratio(1.4) - 0.5283) < 1e-3
    assert abs(E.critical_pressure_ratio(1.3) - 0.5457) < 1e-3


def test_isentropic_area_ratio_table():
    """A/A* at M=2 is 1.6875 and at M=3 is 4.2346 for gamma=1.4 (gas tables)."""
    assert abs(E.isentropic_area_ratio(2.0, 1.4) - 1.6875) < 1e-3
    assert abs(E.isentropic_area_ratio(3.0, 1.4) - 4.2346) < 1e-3
    assert abs(E.isentropic_area_ratio(1.0, 1.4) - 1.0) < 1e-9      # throat


def test_area_ratio_inversion_round_trips():
    """mach_from_area_ratio inverts isentropic_area_ratio on both branches."""
    for M in (1.5, 2.0, 3.5):
        ar = E.isentropic_area_ratio(M, 1.4)
        assert abs(E.mach_from_area_ratio(ar, 1.4, supersonic=True) - M) < 1e-4
    for M in (0.2, 0.5, 0.8):
        ar = E.isentropic_area_ratio(M, 1.4)
        assert abs(E.mach_from_area_ratio(ar, 1.4, supersonic=False) - M) < 1e-4


def test_isentropic_pressure_ratio_consistent_with_choking():
    """P*/P0 from the choking formula equals 1/(P0/P) evaluated at M=1."""
    assert abs(E.critical_pressure_ratio(1.4) - 1.0 / E.isentropic_p0_over_p(1.0, 1.4)) < 1e-12


# ----------------------------------------------------------------------- choked-nozzle mass flow
def test_choked_mass_flow_matches_air_rule():
    """Choked mass flow for air (gamma=1.4, R=287) matches the standard mdot = 0.0404 P0 A / sqrt(T0):
    at 101325 Pa, 288 K, 1 m^2 this is ~241 kg/s."""
    mdot = E.choked_mass_flow(101325.0, 288.0, 1.0, gamma=1.4, Rgas=287.0)
    rule = 0.0404 * 101325.0 * 1.0 / math.sqrt(288.0)
    assert abs(mdot - rule) / rule < 5e-3


def test_choked_mass_flow_linear_in_P0_and_area():
    """Choked mass flow is linear in stagnation pressure and in throat area."""
    base = E.choked_mass_flow(2.0e5, 400.0, 1e-3)
    assert abs(E.choked_mass_flow(4.0e5, 400.0, 1e-3) - 2.0 * base) < 1e-9
    assert abs(E.choked_mass_flow(2.0e5, 400.0, 2e-3) - 2.0 * base) < 1e-9


# ------------------------------------------------------------------------ normal-shock relations
def test_normal_shock_table_values():
    """Normal shock at M1=2, gamma=1.4: M2=0.5774, p2/p1=4.5, T2/T1=1.6875, p02/p01=0.7209 (gas tables)."""
    sh = E.normal_shock(2.0, 1.4)
    assert abs(sh["M2"] - 0.5774) < 1e-3
    assert abs(sh["p2_p1"] - 4.5) < 1e-3
    assert abs(sh["t2_t1"] - 1.6875) < 1e-3
    assert abs(sh["p02_p01"] - 0.7209) < 1e-3


def test_normal_shock_vanishes_at_mach_one():
    """A shock at M1=1 is infinitesimal: M2=1 and all ratios are 1."""
    sh = E.normal_shock(1.0, 1.4)
    assert abs(sh["M2"] - 1.0) < 1e-9
    assert abs(sh["p2_p1"] - 1.0) < 1e-9
    assert abs(sh["p02_p01"] - 1.0) < 1e-9


def test_normal_shock_entropy_increases():
    """Across any shock (M1>1) the stagnation pressure falls: p02/p01 < 1 (second law)."""
    for M1 in (1.5, 2.0, 3.0):
        assert E.normal_shock(M1, 1.33)["p02_p01"] < 1.0


# --------------------------------------------------- entrainment / breakdown assembly behaviour
def test_entrainment_ratio_positive_and_finite():
    """For a plausible LP steam-jet vacuum ejector (motive 8 bar, suction 0.1 bar) the ideal entrainment
    ratio is positive and finite."""
    w = E.entrainment_ratio(P_p=8.0e5, T_p=445.0, P_s=0.10e5, T_s=320.0,
                            A_throat=1.0e-4, A_mix=2.5e-3)
    assert math.isfinite(w) and w > 0.0


def test_critical_backpressure_above_suction():
    """Breakdown backpressure exceeds the suction pressure (the ejector compresses the entrained vapour),
    and rises when the motive pressure rises (a stronger jet tolerates more backpressure)."""
    args = dict(T_p=445.0, P_s=0.10e5, T_s=320.0, A_throat=1.0e-4, A_mix=2.5e-3)
    pc_low = E.critical_backpressure(P_p=6.0e5, **args)
    pc_high = E.critical_backpressure(P_p=10.0e5, **args)
    assert pc_low > 0.10e5
    assert pc_high > pc_low


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fails = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            fails += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - fails}/{len(fns)} passed")
    raise SystemExit(1 if fails else 0)
