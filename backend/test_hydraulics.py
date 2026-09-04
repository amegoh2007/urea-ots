"""Self-tests for the Phase 2 hydraulic primitives."""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hydraulics as hy

def test_liquid_design_is_bit_exact():
    for wd, h, p1, p2, rho in ((101490.0, 0.60, 4.10, 1.13, 1180.0),
                               (12013.3, 0.50, 1.13, 0.46, 1240.0),
                               (823.0, 0.50, 6.00, 4.10, 992.4)):
        assert hy.valve_liquid_anchored(wd, h, p1, p2, rho, h, p1, p2, rho) == wd

def test_gas_design_is_bit_exact():
    assert hy.valve_gas_anchored(24563.0, 0.5, 4.1, 3.9, 408.15, 0.5, 4.1, 3.9, 408.15, 25.0) == 24563.0

def test_gas_chokes_and_stops_following_p2():
    f = lambda p2: hy.valve_gas_anchored(24563.0, 0.5, 140.7, p2, 450.0, 0.5, 140.7, 4.0, 450.0, 25.0)
    assert f(20.0) == f(4.0) == f(0.5)          # below the critical ratio: upstream-only
    assert f(100.0) < f(60.0)                    # above it: still responds

def test_liquid_carries_density():
    f = lambda rho: hy.valve_liquid_anchored(101490.0, 0.6, 4.1, 1.13, rho, 0.6, 4.1, 1.13, 1180.0)
    assert f(1060.0) < f(1180.0) < f(1330.0)
    assert math.isclose(f(1180.0 * 4.0) / f(1180.0), 2.0, rel_tol=1e-12)   # w ~ sqrt(rho)

def test_reverse_dp_gives_zero_not_nan():
    assert hy.valve_liquid_anchored(1000.0, 0.5, 1.0, 2.0, 1000.0, 0.5, 2.0, 1.0, 1000.0) == 0.0
    assert hy.valve_gas_anchored(1000.0, 0.5, 1.0, 2.0, 400.0, 0.5, 2.0, 1.0, 400.0, 20.0) == 0.0

def test_shut_valve_passes_nothing():
    assert hy.valve_liquid_anchored(101490.0, 0.0, 4.1, 1.13, 1180.0, 0.6, 4.1, 1.13, 1180.0) == 0.0

def test_equal_pct_has_constant_gain():
    r = [hy.cv_fraction(h) for h in (0.2, 0.4, 0.6, 0.8)]
    g = [r[i+1] / r[i] for i in range(3)]
    assert all(math.isclose(x, g[0], rel_tol=1e-12) for x in g)   # equal ratio per equal lift

def test_vapour_space_shrinks_with_level():
    assert hy.vapour_volume_m3(23.16, 0.0, 1240.0) == 23.16
    assert hy.vapour_volume_m3(23.16, 10000.0, 1240.0) < 23.16
    assert hy.vapour_volume_m3(23.16, 1e9, 1240.0) > 0.0          # floored, never divides by zero

def test_dpdt_signs_and_zero():
    assert hy.vessel_dpdt(0.46, 372.15, 20.0, 18.0, 100.0, 100.0) == 0.0
    assert hy.vessel_dpdt(0.46, 372.15, 20.0, 18.0, 110.0, 100.0) > 0.0     # generate -> rise
    assert hy.vessel_dpdt(0.46, 372.15, 20.0, 18.0, 100.0, 110.0) < 0.0     # withdraw -> fall
    assert hy.vessel_dpdt(0.46, 372.15, 20.0, 18.0, 100.0, 100.0, dtdt_k_s=0.01) > 0.0   # heat -> rise
    assert hy.vessel_dpdt(0.46, 372.15, 20.0, 18.0, 100.0, 100.0, dvvdt_m3_s=-0.01) > 0.0 # swell -> rise

def test_dpdt_is_stiffer_in_a_smaller_vapour_space():
    big = hy.vessel_dpdt(0.46, 372.15, 20.0, 18.0, 110.0, 100.0)
    small = hy.vessel_dpdt(0.46, 372.15, 5.0, 18.0, 110.0, 100.0)
    assert math.isclose(small / big, 4.0, rel_tol=1e-12)

def test_the_universal_capacitance_was_wrong_by_an_order_of_magnitude():
    """A-6: nine vessels shared 0.02 bar/(kg/s).  The real coefficient is RT/(V_v.M)."""
    def k(T, V, M):        # bar per kg/s, from the molar form
        return hy.vessel_dpdt(1.0, T, V, M, 3600.0 / M, 0.0)     # 1 kg/s of vapour of mass M
    f010 = k(372.15, 20.0, 18.0)      # vacuum separator, steam
    hydr = k(478.15, 55.0, 18.0)      # hydrolyser, much bigger and hotter
    assert f010 / hydr > 2.0          # not remotely the same constant

def test_transport_time_scales_with_flow():
    assert hy.transport_time_s(2.0, 1000.0, 20000.0) == 360.0
    assert hy.transport_time_s(2.0, 1000.0, 10000.0) == 720.0     # 50 % load -> double the transit
    assert hy.transport_time_s(2.0, 1000.0, 0.0) == 3600.0        # capped, never infinite

def test_gravity_outflow_goes_to_zero_with_head():
    f = lambda lvl: hy.gravity_outflow_kgh(300.0, 1.0, lvl, 1240.0, 0.46, 0.46)
    assert f(0.0) == 0.0                       # D-19..21: the guard is unreachable, not deleted
    assert 0.0 < f(0.1) < f(1.0) < f(2.0)
