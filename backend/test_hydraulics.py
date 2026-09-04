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


# ==================================================================================================
#  Unit 328 wiring (Phase 2, second unit).  328C002 and 328C004 only -- see the two exclusion tests
#  below, which pin the REASONS the other two vessels were left alone so a later edit cannot quietly
#  "finish the job" and destabilise them.
# ==================================================================================================
def test_the_328_column_geometry_matches_the_vessel_datasheet():
    main = _main()
    assert (main.R328_C002_ID_M, main.R328_C002_SHELL_M) == (1.250, 10.470)
    assert (main.R328_C004_ID_M, main.R328_C004_SHELL_M) == (1.250, 13.030)
    assert abs(main.R328_C002_VOL_M3 - 12.849) < 0.001
    assert abs(main.R328_C004_VOL_M3 - 15.990) < 0.001


def test_the_328_columns_run_mostly_empty_so_their_coefficients_are_large():
    """A-6.  Both desorbers hold only a tray inventory, so most of the shell is vapour and the real
    RT/(V_v.Mbar) is several times the 0.02 they shared with a 62 m3 hydrolyser and a level tank."""
    main = _main()
    for vol, m_des, rho, kp in ((main.R328_C002_VOL_M3, main.R328_C002_M_DES, main.R328_C002_RHO,
                                 main.R328_C002_P_KP),
                                (main.R328_C004_VOL_M3, main.R328_C004_M_DES, main.R328_C004_RHO,
                                 main.R328_C004_P_KP)):
        vv = hy.vapour_volume_m3(vol, m_des, rho)
        assert vv > 0.8 * vol                       # under 20 % liquid-full at design
        k = hy.vessel_dpdt(3.5, 412.15, vv, 18.0, 3600.0 / 18.0, 0.0)
        assert k > 5.0 * kp, (k, kp)


def test_328d001_is_left_on_its_constant_because_its_geometry_conflicts():
    """NOT a gap -- a source conflict, pinned so nobody "fixes" it by inventing a volume.
    The datasheet narrative gives ID 1684 mm and T/T 1950 mm and then calls that 19 m3; the
    cylinder is 4.343 m3.  The engine's own design holdup is ~10.6 m3, which matches neither and is
    243 % of the computed shell -- so V_v would sit on its floor and the coefficient would be ~355x
    the present constant, far outside the unit circle at a 0.25 s tick."""
    main = _main()
    import math
    v_cyl = math.pi * 0.25 * 1.684 ** 2 * 1.950
    assert abs(v_cyl - 4.343) < 0.001                       # not the 19 m3 the same sentence claims
    assert main.R328_D001_M_DES / 1000.0 > 2.0 * v_cyl      # design holdup exceeds the whole shell
    assert not hasattr(main, "R328_D001_VOL_M3")            # so no geometry is asserted for it
    assert main.R328_D001_P_KP == 0.05                      # and it stays on the lumped constant


def test_328c003_is_now_wired_and_its_controller_still_holds_the_node():
    """A-6, the deferred one.  328C002 and 328C004 self-regulate -- their overheads rise with
    sqrt(dP) against the next node, so stiffening the capacitance only makes a stable first-order
    node faster.  328C003 does not: its overhead is PV-328203B, whose opening comes from PIC-328203,
    so d(m_748)/dP through the hydraulics is identically zero and the WHOLE loop gain sits in the
    controller.  That is why this vessel was held back until the gain was measured rather than
    wired with the other two.

    It has now been measured.  The hydrolyser's own coefficient over its 62.27 m3 shell is 3.7x
    the constant it replaces -- close to the 4.3x first estimated but for a different reason than
    assumed: 328C003 is a LIQUID-FILLED column running 12.55 m deep, so only 24.8 m3 of it is
    vapour, and its overhead is lighter than the pure hydrolysis gas (the seed y_748 is 70 mol%
    steam, MW 21.4, not the 26.0 of 2 NH3 + CO2 alone).  A 6000 s settle from the design seed leaves
    the node inside a decaying +/-0.03 bar excursion about 16.80, so PIC-328203 at Kc 1.5 / Ti 50 s
    holds it and no retune was applied."""
    main = _main()
    assert (main.R328_C003_ID_M, main.R328_C003_SHELL_M) == (1.950, 20.850)
    assert abs(main.R328_C003_VOL_M3 - 62.269) < 0.001
    vv = hy.vapour_volume_m3(main.R328_C003_VOL_M3, main.R328_C003_M_DES,
                             main.R328_C003_RHO_746_KGM3)
    assert 0.35 * main.R328_C003_VOL_M3 < vv < 0.45 * main.R328_C003_VOL_M3   # ~60 % liquid-full
    # The MW the site actually uses is the LIVE y_748, 21.37 at the seed -- not the 26.02 of the
    # hydrolysis gas alone, because 70 mol% of that overhead is MP-steam carryover.
    mw = 1.0 / sum(main.State().y_328_748.get(k, 0.0) / main.MW_SOL[k] for k in main.SOL_SPECIES)
    assert 21.0 < mw < 21.7, mw
    k = hy.vessel_dpdt(16.8, 473.15, vv, mw, 3600.0 / mw, 0.0)                # 1 kg/s of overhead
    assert 3.4 * 0.02 < k < 4.0 * 0.02, k          # 3.72x the constant it replaces
    assert not hasattr(main, "R328_C003_P_KP")     # the lumped constant is gone
    # NOTE the engine seeds 1.5 while Appendix A of Master_PID_Tuning_Constants.md lists PIC-328203
    # at 4.0 -- one more of the 33-of-46 documented plant-vs-simulator divergences, not a bug, but
    # it is the simulator value the measurement above was taken against.
    assert main.State().PIC_328203["Kc"] == 1.5


def test_322c001_holdup_is_geometric_because_the_old_one_did_not_fit_the_vessel():
    """A-6, and a real finding rather than a wiring detail.  A328_C001_M_DES was an "indicative"
    600 s residence, which at the stream-755 density is 5.53 m3 of liquid inside a 3.27 m3 vessel --
    169 % of the shell containing it, so V_v = V_shell - M_l/rho_l is NEGATIVE and A-6 cannot be
    written at all.  The holdup is now half the lower cylindrical section, which is where LT-322502
    measures, and the emergent residence is 150 s."""
    main = _main()
    assert (main.A328_C001_ID_UP_M, main.A328_C001_SHELL_UP_M) == (0.576, 1.900)
    assert (main.A328_C001_ID_LO_M, main.A328_C001_SHELL_LO_M) == (0.922, 4.150)
    assert abs(main.A328_C001_VOL_M3 - 3.2658) < 0.001          # stepped: summed, not averaged
    v_liq = main.A328_C001_M_DES / main.A328_C001_RHO_L
    assert v_liq < main.A328_C001_VOL_M3                        # the inventory now FITS
    assert 140.0 < main.A328_C001_M_TAU_S < 160.0               # emergent, not assumed
    assert not hasattr(main, "A328_C001_P_KP")
    # LI-322502 is M/M_DES * 50, and the state seeds at M_DES, so the design pin cannot move.
    main.state = main.State()
    main.step_sim(0.25)
    assert abs(main.state.a328_c001_M / main.A328_C001_M_DES * 50.0 - 50.0) < 1e-6
    assert abs(main.state.a328_c001_P - main.A328_C001_P_BARA) < 1e-9


def test_323e011_and_323d011_are_one_gas_envelope():
    """A-6.  323E011 drains by gravity through its DN 100 N2 nozzle straight into 323D011 directly
    beneath it, with no valve between, so the two vapour spaces are one envelope at one pressure --
    which is how the engine already treats them (the mass state on this node is the DRUM's).  The
    condenser's share is the shell bore MINUS the bundle: 382 tubes at 25 mm OD over 5900 mm
    displace 1.106 m3 of a 2.966 m3 shell, and ignoring them would overstate the free volume by
    60 %."""
    main = _main()
    import math
    v_shell = math.pi * 0.25 * 0.800 ** 2 * 5.900
    v_tubes = 382 * math.pi * 0.25 * 0.025 ** 2 * 5.900
    v_drum = math.pi * 0.25 * 1.334 ** 2 * 1.800
    assert abs(main.R3232_E011_VOL_M3 - (v_shell - v_tubes + v_drum)) < 1e-9
    assert v_tubes > 0.35 * v_shell                             # the bundle is not negligible
    # Stream 702 is 89.4 wt% NH3 -> MW 17.4, half the CO2-rich vapour the same 0.05 was applied to.
    assert abs(main.R3232_E011_MW_VAP - 17.395) < 0.01
    assert not hasattr(main, "R3232_E011_P_KP")


def test_324f003_is_wired_and_324f001_is_blocked_on_a_missing_height():
    """A-6.  324F003's OEM datasheet gives 2500 mm OD and 1550 mm cylindrical height, so its
    vapour space is computable.  324F001's gives the bore (4570 mm) and the melt density but NOT
    the cylindrical height, and a 4570 mm bore admits 33 to 164 m3 depending on it -- five times
    the uncertainty on the only term A-6 needs.  Pinned so nobody closes that gap by estimating."""
    main = _main()
    assert (main.R324_F003_OD_M, main.R324_F003_SHELL_M) == (2.500, 1.550)
    assert abs(main.R324_F003_VOL_M3 - 7.427) < 0.001
    assert not hasattr(main, "R324_F003_P_KP")
    assert not hasattr(main, "R324_F001_VOL_M3")   # no geometry is asserted for it
    assert main.R324_F001_P_KP == 0.02             # so it stays on the lumped constant


def test_the_328_bottoms_valves_see_both_node_pressures_and_the_live_head():
    """Report D-1.  All three were `design * (op/op_des)` -- a bare position gain with no dP term,
    so backing up the receiving vessel moved them by exactly nothing.  LV-328504 is the clearest
    case: it lets a 200 C liquid down 16.8 -> 3.7 bar into a column whose pressure is now a live
    state, and the old form was blind to it."""
    main = _main()
    p1_des = main.R328_C003_P_BARA + main.R328_C003_HEAD_DES
    f = lambda p2: hy.valve_liquid_anchored(
        main.R328_C003_M747_DES, 0.5, p1_des, p2, main.R328_C003_RHO_746_KGM3,
        0.5, p1_des, main.R328_C004_P_BARA, main.R328_C003_RHO_746_KGM3,
        characteristic=main.R328_LV_CHAR)
    assert f(8.0) < f(main.R328_C004_P_BARA) < f(1.5)     # downstream pressure now matters
    assert f(p1_des) == 0.0                               # no dP, no flow
    # And the HYDROSTATIC head matters: draining the hydrolyser drops the driving dP on its own.
    g = lambda h_m: hy.valve_liquid_anchored(
        main.R328_C003_M747_DES, 0.5,
        main.R328_C003_P_BARA + main.R328_C003_RHO_746_KGM3 * 9.80665 * h_m / 1.0e5,
        main.R328_C004_P_BARA, main.R328_C003_RHO_746_KGM3,
        0.5, p1_des, main.R328_C004_P_BARA, main.R328_C003_RHO_746_KGM3,
        characteristic=main.R328_LV_CHAR)
    assert g(0.0) < g(main.R328_C003_H_DES_M) < g(2.0 * main.R328_C003_H_DES_M)


def test_the_328p006_elevation_is_back_solved_from_the_pump_datasheet():
    """D-1.  LV-328503 sits on a PUMP DISCHARGE, so p1 is not the column pressure.  The 328P006
    datasheet gives the whole line -- 4.7 bar a suction, 24.4 bar a discharge, 19.7 bar differential
    -- and the fixed elevation from the column nozzle down to the pump centreline is what closes
    the design suction exactly.  It must be separate from the level, which moves."""
    main = _main()
    p_suct = (main.R328_C002_P_TOP
              + main.R328_C002_RHO * 9.80665
              * (main.R328_C002_H_DES_M + main.R328_P006_Z_DROP_M) / 1.0e5)
    assert abs(p_suct - main.R328_P006_SUCT_DES_BARA) < 1e-9      # 4.7 bar a, bit-exact
    assert abs(main.R328_LV503_P1_DES - 24.4) < 1e-9              # datasheet discharge
    assert main.R328_P006_Z_DROP_M > main.R328_C002_H_DES_M       # elevation dominates the level


def test_the_steam_letdowns_choke_instead_of_accelerating():
    """Report D-2.  Four of the eight 329 valves run above the critical pressure ratio at their own
    design point, and under the old incompressible sqrt(dP) law their flow kept climbing as the
    downstream pressure fell.  A choked valve is a function of UPSTREAM conditions only."""
    import steam_system as ss
    # PV-329207C, 25 -> 5.01 bar a, dP/P1 = 0.80 against a critical F_gamma.xT = 0.696.
    hi = ss._valve_flow(ss.K_963, 50.0, 25.0, 5.01325, ss.P_SUP_BARA, ss.P_LP_BARA)
    lo = ss._valve_flow(ss.K_963, 50.0, 25.0, 1.01325, ss.P_SUP_BARA, ss.P_LP_BARA)
    assert abs(lo - hi) < 1e-12                     # choked: p2 does not matter at all
    # The old law would have raised it by sqrt(23.99/19.99) = +9.5 %.
    assert ss.K_963 * 0.5 * (25.0 - 1.01325) ** 0.5 > 1.09 * ss.K_963 * 0.5 * (25.0 - 5.01325) ** 0.5
    # Sub-critical valves still respond to p2, and every valve is bit-exact at its design condition.
    assert (ss._valve_flow(ss.K_902, 50.0, 25.0, 21.0, ss.P_SUP_BARA, ss.P_HP_BARA)
            < ss._valve_flow(ss.K_902, 50.0, 25.0, ss.P_HP_BARA, ss.P_SUP_BARA, ss.P_HP_BARA))
    for K, p1, p2 in ((ss.K_902, ss.P_SUP_BARA, ss.P_HP_BARA),
                      (ss.K_903, ss.P_SUP_BARA, ss.P_MP_BARA),
                      (ss.K_LD9, ss.P_MP_BARA, ss.P_LP_BARA),
                      (ss.K_207A, ss.P_LP_BARA, 1.01325),
                      (ss.K_207B, ss.P_LP_BARA, ss.P_TURBINE_OUT_BARA),
                      (ss.K_963, ss.P_SUP_BARA, ss.P_LP_BARA)):
        for op in (0.0, 17.3, 50.0, 100.0):
            assert (ss._valve_flow(K, op, p1, p2, p1, p2)
                    == K * (op / 100.0) * (p1 - p2) ** 0.5)


def test_a_shut_hv322604_passes_nothing_on_the_sm_port_too():
    """D-2.  main.hv_322604 was moved onto the ISA law in the HV-322604 pass; core.valve.Valve322604
    is the Sequential-Modular port of the same valve and was left behind on `_eq_pct * sqrt(dP)`.
    _eq_pct(0, 50) is 50^-0.5 = 0.1414, so a valve commanded fully SHUT still passed 14 % of the
    design off-gas out of a 140.7 bar loop.  The two ports now share one law."""
    main = _main()
    from core.stream import Stream
    from core.valve import Valve322604
    og = Stream("og"); pg = Stream("pg")
    og.set_state(T=main.SCRUB_OFFGAS_T_C, P=main.SCRUB_OFFGAS_P_BARA, mass_flow=0.0)
    og.comp = dict(main.SCRUB_OFFGAS_KMOLH_DES)
    v = Valve322604("HV_322604", og, pg)
    v.hic_pct = 0.0
    v.solve()
    assert v.diagnostics["mass_kgh"] == 0.0
    assert v.diagnostics["valve_frac"] == 0.0
    v.hic_pct = main.SCRUB_HIC604_DES_PCT
    v.solve()
    assert abs(v.diagnostics["valve_frac"] - 1.0) < 1e-12       # bit-exact at design


def test_the_transport_delays_stretch_when_the_flow_falls():
    """Report D-8.  The 345 s feed dead time and the 60 s stripper-bottoms FIFO were both fixed, so
    a plant at 50 % load still saw its feed arrive in 345 s.  A transport lag is rho.V/m_dot: halve
    the flow and it doubles.  The measured anchors are kept -- only the departure is made physical
    -- so each is exact at its own design flow."""
    main = _main()
    assert abs(main._feed_transport_td_s(main.FEED_CO2_LINE_KG, main.CO2_DES_KGH)
               - main.FEED_TD_S) < 1e-9
    assert abs(main._feed_transport_td_s(main.FEED_CO2_LINE_KG, main.CO2_DES_KGH / 2.0)
               - 2.0 * main.FEED_TD_S) < 1e-9
    assert abs(main._feed_transport_td_s(main.FEED_NH3_LINE_KG, main.EJ_MOTIVE_NH3_DES)
               - main.FEED_TD_S) < 1e-9
    td_strip = hy.transport_time_s(main.STRIP_BOT_LINE_M3, main.STRIP_RHO_BOTTOM,
                                   main.STRIP_BOT_DES_KGH)
    assert abs(td_strip - main.STRIP_BOT_TD_DES_S) < 1e-9
    assert abs(hy.transport_time_s(main.STRIP_BOT_LINE_M3, main.STRIP_RHO_BOTTOM,
                                   main.STRIP_BOT_DES_KGH / 4.0)
               - 4.0 * main.STRIP_BOT_TD_DES_S) < 1e-9
    # A dead feed gives a long-but-finite transit, never an infinity.
    assert main._feed_transport_td_s(main.FEED_CO2_LINE_KG, 0.0) == main.FEED_TD_MAX_S


def test_the_hpcc_empty_vessel_guard_was_dead_code_before_it_was_deleted():
    """Reports D-20 / D-21.  The claim is that a head-driven discharge makes an empty-vessel
    limiter unreachable.  For the HPCC that is provable rather than merely plausible: the outflow
    is phi_fwd * (L/NLL), so at L = 0 it is identically 0.0, and the deleted guard's condition
    asked whether 0.0 > phi_in for a phi_in that is a ratio of two non-negative liquid makes."""
    main = _main()
    for phi_fwd in (0.0, 0.5, 1.0, 3.7):
        assert phi_fwd * (0.0 / main.HPCC_LEVEL_NLL_PCT) == 0.0
    import inspect
    # Executable lines only -- the deletion is recorded verbatim in a comment right where it stood,
    # so a plain substring search over the source would match its own tombstone.
    code = [ln for ln in inspect.getsource(main.step_sim).splitlines()
            if not ln.lstrip().startswith("#")]
    assert not any("hpcc_level_pct <= 0.0" in ln for ln in code)
    # The stripper guard is KEPT and must stay: LV-322501 is a 140.7 -> 4.0 bar letdown whose dP
    # does NOT vanish as the sump empties, and there is no two-phase valve model to replace it.
    assert any("if s.strip_level <= 0.0 and drain_kgh > delayed_bot_kgh" in ln for ln in code)


def test_the_ejector_suction_follows_the_gravity_head_again():
    """Report D-19.  `m_suc = capacity` dropped the gravity-head multiplier the block comment
    directly above it specifies, which left the 322E003 sump a pure integrator -- it flooded
    correctly on a shut XV-322903 and then never came back.  At design the head fraction is a
    literal 1.0, so the fixed point does not move; the throat-choke ceiling caps a real flood."""
    main = _main()
    des = main.ejector_322f001(main.EJ_MOTIVE_NH3_DES, main.EJ_MOTIVE_T_DES_C,
                               main.EJ_OPEN_DES, scrub_level_frac=1.0)
    assert abs(des["suction_kgh"] - main.EJ_SUC_TOT_DES) < 1e-6      # design untouched
    low = main.ejector_322f001(main.EJ_MOTIVE_NH3_DES, main.EJ_MOTIVE_T_DES_C,
                               main.EJ_OPEN_DES, scrub_level_frac=0.4)
    assert low["suction_kgh"] < des["suction_kgh"]                   # head drives it down
    empty = main.ejector_322f001(main.EJ_MOTIVE_NH3_DES, main.EJ_MOTIVE_T_DES_C,
                                 main.EJ_OPEN_DES, scrub_level_frac=0.0)
    assert empty["suction_kgh"] == 0.0                               # zero head, zero flow
    flood = main.ejector_322f001(main.EJ_MOTIVE_NH3_DES, main.EJ_MOTIVE_T_DES_C,
                                 main.EJ_OPEN_DES, scrub_level_frac=2.0)
    assert flood["suction_kgh"] <= des["suction_kgh"] * main.EJ_HYD_FRAC_MAX + 1e-6


def test_the_328_design_seed_holds_after_one_tick():
    main = _main()
    main.state = main.State()
    main.step_sim(0.25)
    s = main.state
    assert s.a328_c002_P == main.R328_C002_P_TOP
    assert s.a328_c004_P == main.R328_C004_P_BARA
    assert s.a328_c002_M == main.R328_C002_M_DES
    assert s.a328_c004_M == main.R328_C004_M_DES
    assert abs(s.a328_c002_T - main.R328_C002_T_BOT_BOT) < 1e-9
    assert abs(s.a328_c004_T - main.R328_C004_T) < 1e-9
    # ... and unit 323 is untouched by the unit-328 change
    assert s.r323_f010_P == main.R323_F010_P_BARA
    assert s.r323_f010_T == main.R323_F010_T_SP_C


# ==================================================================================================
#  HV-322604 (Phase 2, report D-2).  The one site the brief named explicitly: an inert purge letting
#  carbamate off-gas down 140.7 -> 4.0 bar a, previously modelled as an incompressible orifice.
# ==================================================================================================
def test_hv322604_is_choked_at_its_own_design_point():
    """dP/P1 = 0.9716 against F_gamma.xT = 0.696 at gamma 1.30 -- and choked for ANY plausible
    gamma, so this is not a marginal call.  That is why the sqrt(dP) law was wrong here rather than
    merely imprecise."""
    main = _main()
    x_ratio = main.SCRUB_HV604_DP_DES / main.SCRUB_OFFGAS_P_BARA
    assert abs(x_ratio - 0.9716) < 0.001
    for gamma in (1.20, 1.30, 1.40):
        assert x_ratio > (gamma / 1.40) * hy.XT_GLOBE, gamma


def test_hv322604_flow_is_linear_in_upstream_pressure_while_choked():
    """The signature of choked flow: m ~ P1 exactly, and p2 does not enter at all.  The law it
    replaces had m ~ sqrt(P1 - 4.0), which keeps responding to the downstream node."""
    main = _main()
    og, T = main.SCRUB_OFFGAS_KMOLH_DES, main.SCRUB_OFFGAS_T_C
    pts = [(pu, main.hv_322604(og, T, 50.0, pu)["mass_kgh"]) for pu in (140.7, 120.0, 100.0, 60.0, 45.0)]
    ratios = [m / pu for pu, m in pts]
    for r in ratios[1:]:
        assert math.isclose(r, ratios[0], rel_tol=1e-12), ratios


def test_hv322604_is_bit_exact_at_design():
    main = _main()
    hv = main.hv_322604(main.SCRUB_OFFGAS_KMOLH_DES, main.SCRUB_OFFGAS_T_C,
                        main.SCRUB_HIC604_DES_PCT, main.SCRUB_OFFGAS_P_BARA)
    assert hv["valve_frac"] == 1.0


def test_a_closed_hv322604_passes_nothing():
    """It used to pass 14 %.  `_eq_pct(0, 50)` is 50^-0.5 = 0.1414, so a fully shut HIC-322604 still
    vented about 835 kg/h of NH3/CO2 from a 140.7 bar loop -- and an operator trained on that learns
    that closing the vent does not stop the vent.  The bare equal-% exponential never reaches zero;
    `cv_fraction` clamps it."""
    main = _main()
    hv = main.hv_322604(main.SCRUB_OFFGAS_KMOLH_DES, main.SCRUB_OFFGAS_T_C, 0.0,
                        main.SCRUB_OFFGAS_P_BARA)
    assert hv["mass_kgh"] == 0.0
    assert hv["valve_frac"] == 0.0
    assert 50.0 ** -0.5 > 0.14                      # what the old characteristic returned there


def test_hv322604_carries_the_offgas_molecular_weight():
    """m ~ sqrt(M): a heavier off-gas puts more kilograms through the same trim at the same
    pressures.  Passing mw_des explicitly is what keeps composition from cancelling in the ratio."""
    f = lambda mw: hy.valve_gas_anchored(5901.35, 0.5, 140.7, 4.0, 387.15,
                                         0.5, 140.7, 4.0, 387.15, mw, mw_des=27.4768)
    assert math.isclose(f(33.0) / f(27.4768), (33.0 / 27.4768) ** 0.5, rel_tol=1e-12)
    assert f(27.4768) == 5901.35
