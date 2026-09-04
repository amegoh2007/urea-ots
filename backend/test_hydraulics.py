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


# ==================================================================================================
#  Unit 323 wiring (Phase 2, first unit).  These import `main`, so they are slower than the
#  primitive tests above; they assert the two things that matter for a wiring change: the design
#  seed does not move, and the terms that were MISSING are now present with the right sign.
# ==================================================================================================
def _main():
    import main
    return main


def test_the_323_letdown_valves_are_bit_exact_at_the_design_seed():
    """The whole point of the anchored ratio: swapping in IEC 60534 must not move the pin."""
    main = _main()
    m314 = hy.valve_liquid_anchored(
        main.R323_M314_DES, main.R323_LV501_OP_DES / 100.0,
        main.R323_C003_P_BARA, main.R323_F004_P_BARA, main.R323_RHO_C003_DES,
        main.R323_LV501_OP_DES / 100.0, main.R323_C003_P_BARA, main.R323_F004_P_BARA,
        main.R323_RHO_C003_DES, characteristic=main.R323_LV_CHAR)
    assert m314 == main.R323_M314_DES
    m319 = hy.valve_liquid_anchored(
        main.R323_M319_DES, main.R323_LV505_OP_DES / 100.0,
        main.R323_F004_P_BARA, main.R323_F010_P_BARA, main.R323_RHO_F004_DES,
        main.R323_LV505_OP_DES / 100.0, main.R323_F004_P_BARA, main.R323_F010_P_BARA,
        main.R323_RHO_F004_DES, characteristic=main.R323_LV_CHAR)
    assert m319 == main.R323_M319_DES


def test_the_letdown_valves_now_see_downstream_pressure():
    """Report D-1's core complaint: `design x (op/op_des)` has NO dP term, so backing the flash drum
    up moved the letdown flow by exactly nothing.  It must move now, and downward."""
    main = _main()
    f = lambda p2: hy.valve_liquid_anchored(
        main.R323_M314_DES, 0.5, main.R323_C003_P_BARA, p2, main.R323_RHO_C003_DES,
        0.5, main.R323_C003_P_BARA, main.R323_F004_P_BARA, main.R323_RHO_C003_DES,
        characteristic=main.R323_LV_CHAR)
    assert f(2.5) < f(main.R323_F004_P_BARA) < f(0.5)
    assert f(main.R323_C003_P_BARA) == 0.0            # no dP, no flow


def test_the_323f010_vapour_space_is_not_on_the_shared_capacitance():
    """A-6.  The engine shared 0.02 bar/(kg/s) across nine vessels.  323F010's own coefficient,
    from its real 23.15 m3 shell and its design holdup, is several times that -- which is the whole
    finding, and is why one constant could not have been right for all of them."""
    main = _main()
    vv = hy.vapour_volume_m3(main.R323_F010_VOL_M3, main.R323_F010_M_DES, main.R323_D002_RHO)
    assert 0.0 < vv < main.R323_F010_VOL_M3          # the melt really does occupy part of the shell
    k_new = hy.vessel_dpdt(main.R323_F010_P_BARA, main.R323_F010_T_SP_C + 273.15, vv, 18.54,
                           3600.0 / 18.54, 0.0)      # 1 kg/s of steam
    assert k_new > 3.0 * main.R323_F010_P_KP, (k_new, main.R323_F010_P_KP)


def test_the_323_geometry_matches_the_vessel_datasheet():
    """Sourced, not fitted: References/323F004 323E010 323F010.md gives both vessels' ID and shell
    height directly.  Asserted so a future edit cannot quietly turn them into tuning knobs."""
    main = _main()
    assert (main.R323_F004_ID_M, main.R323_F004_SHELL_M) == (1.384, 1.800)
    assert (main.R323_F010_ID_M, main.R323_F010_SHELL_M) == (3.478, 2.437)
    assert abs(main.R323_F004_VOL_M3 - 2.708) < 0.001
    assert abs(main.R323_F010_VOL_M3 - 23.153) < 0.001


def test_the_design_seed_holds_after_one_tick():
    """End to end: a fresh State stepped once must still sit on every 323 design boundary."""
    main = _main()
    main.state = main.State()
    main.step_sim(0.25)
    s = main.state
    assert s.r323_f004_P == main.R323_F004_P_BARA
    assert s.r323_f010_P == main.R323_F010_P_BARA
    assert s.r323_f010_T == main.R323_F010_T_SP_C
    assert s.r323_f010_M == main.R323_F010_M_DES
    assert s.r323_f004_M == main.R323_F004_M_DES
    assert s.r323_c003_M == main.R323_C003_M_DES
