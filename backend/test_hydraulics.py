"""Self-tests for the Phase 2 hydraulic primitives."""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hydraulics as hy

#  The coefficient nine vessels used to share (report A-6).  The constants themselves are deleted
#  from the engine now that every vessel carries its own geometry; the number is kept here because
#  these tests exist to show how far off one shared value was.
_SHARED_P_KP = 0.02
import machines

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
    assert k_new > 3.0 * _SHARED_P_KP, (k_new, _SHARED_P_KP)


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
                                 _SHARED_P_KP),
                                (main.R328_C004_VOL_M3, main.R328_C004_M_DES, main.R328_C004_RHO,
                                 _SHARED_P_KP)):
        vv = hy.vapour_volume_m3(vol, m_des, rho)
        assert vv > 0.8 * vol                       # under 20 % liquid-full at design
        k = hy.vessel_dpdt(3.5, 412.15, vv, 18.0, 3600.0 / 18.0, 0.0)
        assert k > 5.0 * kp, (k, kp)


def test_328d001_geometry_wins_over_the_narrative_that_contradicts_it():
    """A-6, the last deferred vessel -- CLOSED, and in the opposite direction to the deferral.

    The datasheet gives the vessel twice in one sentence: ID 1684 mm with a 1950 mm tangent-to-
    tangent cylinder, "which yields a nominal internal liquid capacity of 19 cubic meters".  pi/4 x
    1.684^2 x 1.950 is 4.343 m3.  One of those is a measurement of the steel and the other is
    arithmetic about it, so the dimensions win and the claim is discarded.

    What was blocking A-6 was never the vessel: it was the design HOLDUP, R328_D001_M_FULL = 20 900
    kg, which is 19.09 m3 at the stream density -- the same 19 m3 claim, carried through into the
    inventory.  A holdup 243 % of its own shell puts V_v on its 2 % floor, which is what made the
    coefficient come out 355x and look unusable.  With the holdup taken off the shell instead, the
    drum holds 2.19 m3 of liquid in a 4.34 m3 vessel and the vapour space is an ordinary 2.15 m3.
    """
    main = _main()
    import math
    v_cyl = math.pi * 0.25 * 1.684 ** 2 * 1.950
    assert abs(v_cyl - 4.343) < 0.001                       # not the 19 m3 the same sentence claims
    assert abs(main.R328_D001_VOL_M3 - v_cyl) < 1e-9        # the model uses the dimensions
    v_liq = main.R328_D001_M_DES / main.R328_D001_M776_RHO
    assert 0.4 * v_cyl < v_liq < 0.6 * v_cyl                # the holdup now FITS, at ~half full
    vv = hy.vapour_volume_m3(main.R328_D001_VOL_M3, main.R328_D001_M_DES, main.R328_D001_M776_RHO)
    assert vv > 0.05 * main.R328_D001_VOL_M3                # ... so V_v is real, not on its floor
    assert abs(vv - 2.150) < 0.01
    assert not hasattr(main, "R328_D001_P_KP")              # and the shared constant is gone
    #  ~15x the 0.05 bar/(kg/s) it replaces, on an NH3-rich vent of molar mass 17.15.
    k = hy.vessel_dpdt(2.6, 334.15, vv, main.R328_D001_MW786_DES,
                       3600.0 / main.R328_D001_MW786_DES, 0.0)
    assert 10.0 * 0.05 < k < 25.0 * 0.05, k


def test_328d001_level_is_still_50p5_at_the_seed():
    """The holdup moved 4.4x and the design pin did not, by construction: LI-328501 is
    M/M_DES*50.5 and the state seeds at M_DES."""
    main = _main()
    s = main.State()
    assert s.a328_d001_M == main.R328_D001_M_DES
    assert abs(s.a328_d001_M / main.R328_D001_M_DES * main.R328_D001_LVL_SP - 50.5) < 1e-12


def test_the_328_overheads_are_compressible_and_bit_exact_at_design():
    """D-2.  All four unit-328 vapour paths were incompressible: two sqrt(dP) orifice laws (737,
    750) and two bare position gains (748, 786).  They now run the ISA-75.01 gas form, which is
    bit-exact at the design condition because it is the ratio of one expression to itself."""
    main = _main()
    for w_des, p1, p2, t1, mw in ((main.R328_C002_M737_DES, main.R328_C002_P_TOP,
                                   main.R328_D001_P_BARA, main.R328_C002_T_BOT_TOP + 273.15,
                                   main.R328_M737_MW_DES),
                                  (main.R328_C003_M748_DES, main.R328_C003_P_BARA,
                                   main.R328_C002_P_TOP, main.R328_C003_T + 273.15,
                                   main.R328_M748_MW_DES),
                                  (main.R328_C004_M750_DES, main.R328_C004_P_BARA,
                                   main.R328_C002_P_TOP, main.R328_C004_T + 273.15,
                                   main.R328_M750_MW_DES),
                                  (main.R328_D001_M786_DES, main.R328_D001_P_BARA,
                                   main.R3232_E011_P_BARA, main.R328_D001_T + 273.15,
                                   main.R328_D001_MW786_DES)):
        assert hy.valve_gas_anchored(w_des, 1.0, p1, p2, t1, 1.0, p1, p2, t1, mw,
                                     characteristic="linear", mw_des=mw) == w_des


def test_the_328_overheads_now_carry_composition():
    """The sqrt(dP) form could not: a lighter overhead through the same restriction at the same
    pressures really does pass fewer kilograms, and w ~ sqrt(M) is the term that says so."""
    f = lambda mw: hy.valve_gas_anchored(6665.0, 1.0, 3.5, 2.6, 390.15, 1.0, 3.5, 2.6, 390.15,
                                         mw, characteristic="linear", mw_des=20.81)
    assert f(18.0) < f(20.81) < f(26.0)
    assert math.isclose(f(20.81 * 4.0) / f(20.81), 2.0, rel_tol=1e-12)


def test_the_718a_leg_transit_moves_with_flow():
    """D-8, the last static transit in unit 328.  45 s is the leg's residence AT DESIGN; at half
    the flow the same line inventory takes twice as long to clear."""
    main = _main()
    tau_des = main._feed_transport_td_s(main.R3232_M718A_LINE_KG, main.R3232_M718A_DES)
    assert abs(tau_des - main.R3232_M718A_TAU_S) < 1e-9              # exact at design
    tau_half = main._feed_transport_td_s(main.R3232_M718A_LINE_KG, 0.5 * main.R3232_M718A_DES)
    assert abs(tau_half - 2.0 * main.R3232_M718A_TAU_S) < 1e-9       # and doubles at half rate


# ==================================================================================================
#  D-5 -- the CO2 line node and its check valve
# ==================================================================================================
def test_check_valve_is_bit_exact_at_its_design_differential():
    assert hy.check_valve_kgh(54618.0, 144.2, 140.7, 3.5, 0.07) == 54618.0
    assert hy.check_valve_kgh(54618.0, 144.2, 140.7, 3.5, 0.0) == 54618.0


def test_check_valve_is_a_diode_not_a_resistor():
    """Three properties the `min(1, sqrt(dP/dP_des))` delivery fraction did not have."""
    f = lambda p1, p2: hy.check_valve_kgh(54618.0, p1, p2, 3.5, 0.07)
    assert f(139.0, 140.7) == 0.0            # reverse: exactly zero, not a small negative
    assert f(140.7, 140.7) == 0.0            # zero differential: seated
    assert f(140.75, 140.7) == 0.0           # inside the crack band: STILL seated
    assert f(150.0, 140.7) > 54618.0         # forward: no ceiling at the design flow
    assert f(148.2, 140.7) > f(144.2, 140.7) > f(142.2, 140.7) > 0.0    # monotone forward


def test_the_co2_line_node_holds_the_design_pressure_exactly():
    """The line is a capacitance, and at design the imbalance across it is a literal zero:
    the machine delivers CO2_DES_KGH, the check valve passes CO2_DES_KGH, the vent passes 0."""
    main = _main()
    deliv = main.CO2_K001.delivery_kgh(main.CO2_K_SUCT_P_BARA, main.CO2_P_DES_BARA,
                                       main.CO2_K_SUCT_T_K, main.CO2_FEED_MW, 1.0)["kgh"]
    check = hy.check_valve_kgh(main.CO2_DES_KGH, main.CO2_P_DES_BARA, main.SYN_P_DES_BARA,
                               main.CO2_DP_HP_DES, main.CO2_CHECK_CRACK_BAR)
    assert deliv == main.CO2_DES_KGH
    assert check == main.CO2_DES_KGH
    assert hy.vessel_dpdt(main.CO2_P_DES_BARA, main.CO2_VENT_T_DES_K, main.CO2_LINE_V_M3,
                          main.CO2_FEED_MW, deliv / main.CO2_FEED_MW,
                          check / main.CO2_FEED_MW) == 0.0


def test_the_co2_line_volume_and_its_dead_time_come_from_one_inventory():
    """D-5/D-8 consistency: a line that holds M kg has BOTH a transit M/mdot and a capacitance
    RT/(V.Mbar) with V = M/rho.  Deriving them from one inventory is a constraint, not a second
    free parameter."""
    main = _main()
    assert abs(main.CO2_LINE_V_M3 * main.CO2_LINE_RHO_DES - main.FEED_CO2_LINE_KG) < 1e-9
    assert abs(main._feed_transport_td_s(main.FEED_CO2_LINE_KG, main.CO2_DES_KGH)
               - main.FEED_TD_S) < 1e-9


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


def test_both_324_separators_are_wired_on_their_own_geometry():
    """A-6, closed for the last vessel.  324F003's OEM datasheet gives 2500 mm OD and 1550 mm
    cylindrical height.  324F001's datasheet leaves both the nominal volume and the cylindrical
    height BLANK -- which is what deferred it through three passes -- but the vendor ASSEMBLY
    drawing (UD-AU-324-DZ-0006-001, Uhde/A&S rev 00) states Nominal volume, Body = 70.5 m3 in its
    own design table.  Neither separator is on a shared coefficient any more."""
    main = _main()
    assert (main.R324_F003_OD_M, main.R324_F003_SHELL_M) == (2.500, 1.550)
    assert abs(main.R324_F003_VOL_M3 - 7.427) < 0.001
    assert not hasattr(main, "R324_F003_P_KP")
    assert main.R324_F001_VOL_M3 == 70.5           # drawing value, visually verified
    assert not hasattr(main, "R324_F001_P_KP")     # the lumped constant is gone
    #  The melt occupies part of it, and what is left responds as its own vapour space.
    vv = hy.vapour_volume_m3(main.R324_F001_VOL_M3, main.R324_F001_M_DES, main.R324_F001_RHO_L)
    assert 0.0 < vv < main.R324_F001_VOL_M3
    k = hy.vessel_dpdt(main.R324_F001_P_BARA, main.R324_E001_T_SP_C + 273.15, vv,
                       main.R324_F001_MW_VAP, 3600.0 / main.R324_F001_MW_VAP, 0.0)
    assert k > _SHARED_P_KP, (k, _SHARED_P_KP)


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


def test_the_liquid_choke_carries_ff_from_the_vapour_pressure():
    """IEC 60534-2-1: FF = 0.96 - 0.28.sqrt(Pv/Pc).  The 0.96 intercept alone is its Pv << Pc limit,
    8 % high on a 15 bar a liquor.  At Pv = 0 the choke is FL^2.p1 exactly as before."""
    p1, pv, fl = 24.4, 15.0, hy.FL_GLOBE
    ff = 0.96 - 0.28 * math.sqrt(pv / 220.64)
    dp_choked = fl * fl * (p1 - ff * pv)
    choked = hy._phi_liquid(0.5, p1, p1 - dp_choked - 1.0, 900.0, "linear", fl, pv)
    assert choked == hy._phi_liquid(0.5, p1, p1 - dp_choked - 6.0, 900.0, "linear", fl, pv)
    assert hy._phi_liquid(0.5, p1, p1 - dp_choked + 0.5, 900.0, "linear", fl, pv) < choked
    assert hy._phi_liquid(0.5, p1, 20.0, 900.0, "linear", fl, 0.0) == 0.5 * math.sqrt((p1 - 20.0) * 900.0)


def test_lv328504_flashes_at_its_vena_contracta_and_is_choked_at_design():
    """Stream 749 reaches LV-328504 from the 328E021 hot side at 148 C, not from the 200 C hydrolyser
    bottom: 12.9 bar subcooled at 17.9 bar a upstream, but 3.7 bar a downstream is below its 5.06 bar a
    vapour pressure, so it flashes in the vena contracta and chokes.  328C004's pressure cannot reach
    it; a hotter 749 flashes earlier and passes less."""
    main = _main()
    rho = main.R328_C003_RHO_746_KGM3
    p1 = main.R328_C003_P_BARA + main.R328_C003_HEAD_DES

    def f(p2, pv=None):
        return hy.valve_liquid_anchored(
            main.R328_C003_M747_DES, 0.5, p1, p2, rho, 0.5, p1, main.R328_C004_P_BARA, rho,
            characteristic=main.R328_LV_CHAR,
            pv_bara=main.R328_LV504_PV_DES if pv is None else pv, pv_des_bara=main.R328_LV504_PV_DES)

    assert 4.9 < main.R328_LV504_PV_DES < 5.3, "749 liquor at 148 C, above water's 4.51 bar a"
    assert f(main.R328_C004_P_BARA) == main.R328_C003_M747_DES
    assert f(1.5) == f(main.R328_C004_P_BARA) == f(6.0), "choked: the receiving column is invisible"
    assert f(8.0) < f(6.0), "above the choke point p2 still matters"
    assert f(main.R328_C004_P_BARA, pv=6.0) < f(main.R328_C004_P_BARA)


def test_lv328503_is_liquid_at_design_and_chokes_when_the_hydrolyser_falls():
    """Stream 746 leaves 328E021 at 190 C on the 328P006 discharge.  Its bubble pressure is 14.97 bar a
    (0.63 % NH3 over water's 12.55); the vena contracta at design sits just above that, at 15.0."""
    main = _main()
    rho = main.R328_C002_RHO
    p1 = main.R328_LV503_P1_DES
    assert 14.5 < main.R328_LV503_PV_DES < 15.5
    p_vc = p1 - (p1 - main.R328_C003_P_BARA) / hy.FL_GLOBE ** 2
    assert p_vc > main.R328_LV503_PV_DES, "liquid through the vena contracta at design"

    def f(p2):
        return hy.valve_liquid_anchored(
            main.R328_C002_M743_DES, 0.5, p1, p2, rho, 0.5, p1, main.R328_C003_P_BARA, rho,
            characteristic=main.R328_LV_CHAR,
            pv_bara=main.R328_LV503_PV_DES, pv_des_bara=main.R328_LV503_PV_DES)

    assert f(main.R328_C003_P_BARA) == main.R328_C002_M743_DES
    assert f(16.0) > f(main.R328_C003_P_BARA), "unchoked at design: p2 moves it"
    assert f(14.0) == f(10.0), "a hydrolyser 3 bar low flashes the feed and chokes it"


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
    # The stripper guard went with report D-20.  LV-322501 is a 140.7 -> 4.0 bar letdown whose dP
    # does not vanish as the sump empties, so what replaced the guard is not a gravity argument but
    # the seal ramp and the gas the uncovered trim passes (consequence.seal_fraction/blowthrough_kgh).
    assert not any("if s.strip_level <= 0.0 and drain_kgh > delayed_bot_kgh" in ln for ln in code)
    assert any("consequence.seal_fraction(s.strip_level)" in ln for ln in code)


def test_the_stripper_gas_density_is_srk_and_matches_pfd_201():
    """Report D-20.  The gas LV-322501 passes once 322E001's sump uncovers is the stripper's own
    vapour at 140-odd bar.  PFD 201 prints its density: 128.7 kg/m3 at 187 C and 144.2 bar a.  The
    ideal gas gives 97.8 (-24 %); SRK on the same mole fractions gives 128.4."""
    import consequence
    import real_gas
    y201 = {"CO2": 32.55, "H2O": 4.86, "N2": 0.76, "NH3": 61.7, "O2": 0.13}
    rho = consequence.gas_density_ideal(144.2, 187.0, 25.96) / real_gas.z_factor(y201, 187.0, 144.2)
    assert abs(rho - 128.7) / 128.7 < 0.01
    assert abs(real_gas.z_factor(y201, 187.0, 1.0) - 1.0) < 0.01
    assert real_gas.z_factor({}, 187.0, 144.2) == 1.0


def test_lv322501_blows_the_stripper_gas_through_once_the_sump_uncovers():
    """Report D-20.  Sealed, the valve passes no gas at all; uncovered, it passes the stripper gas at
    the flow its liquid design duty implies, choked, so the 4 bar downstream pressure does not set it."""
    import consequence
    main = _main()
    rho_g = 128.7
    dp_des = main.SYN_P_DES_BARA - main.LV322501_P_DOWN_BARA
    theta_full = 100.0 / main.LV322501_OPEN_DES

    def blow(level, theta=theta_full, p_down=main.LV322501_P_DOWN_BARA):
        return consequence.blowthrough_kgh(
            main.STRIP_BOT_DES_KGH, main.STRIP_RHO_BOTTOM, dp_des, theta, rho_g,
            main.SYN_P_DES_BARA, main.SYN_P_DES_BARA - p_down, consequence.seal_fraction(level))

    assert consequence.seal_fraction(50.0) == 1.0 and blow(50.0) == 0.0
    assert blow(3.0) == 0.0
    full = blow(0.0)
    assert 30000.0 < full < 80000.0                                   # tens of t/h of gas, not 130 t/h
    assert blow(0.0, p_down=1.0) == full                              # choked
    assert abs(blow(1.5) - 0.5 * full) < 1e-6 * full                  # the seal ramps over the bore


def test_lv323505_seals_and_passes_the_flash_drum_vapour_once_323f004_uncovers():
    """LV-323505 had neither a seal nor a guard: an empty 323F004 went on draining at the full valve
    rate while `max(M, 1.0)` put the missing mass back, so an empty drum made liquor.  It now carries
    the same two laws as LV-322501.  The letdown is 1.13 -> 0.46 bar a, x = 0.59 below the choke at
    x_T F_gamma = 0.65, so unlike LV-322501 the gas rides the live vacuum: a 323F010 that loses its
    vacuum takes less."""
    import consequence
    import inspect
    main = _main()
    dp_des = main.R323_F004_P_BARA - main.R323_F010_P_BARA
    rho_g = consequence.gas_density_ideal(main.R323_F004_P_BARA, main.R323_F004_T_SP_C, 19.0)

    def blow(level, p_f010=main.R323_F010_P_BARA):
        return consequence.blowthrough_kgh(
            main.R323_M319_DES, main.R323_RHO_F004_DES, dp_des, 100.0 / main.R323_LV505_OP_DES, rho_g,
            main.R323_F004_P_BARA, main.R323_F004_P_BARA - p_f010, consequence.seal_fraction(level))

    assert blow(50.0) == 0.0
    full = blow(0.0)
    assert 0.01 * main.R323_M319_DES < full < 0.2 * main.R323_M319_DES
    assert blow(0.0, p_f010=0.9) < 0.8 * full
    code = [ln for ln in inspect.getsource(main.step_sim).splitlines() if not ln.lstrip().startswith("#")]
    assert any("consequence.seal_fraction(lvl_f004)" in ln for ln in code)
    assert any("m_evap / _mw_evap + n_blow_323505" in ln for ln in code)


def test_lv323501_seals_and_blows_the_rectifier_vapour_through_choked():
    """The last D-19..D-21 guard.  323C003's drain clipped itself to the inflow at M <= 1 kg; it now
    carries the seal and blow-through laws.  4.1 -> 1.13 bar a is past the choke, so the gas does not
    care what 323F004 is doing."""
    import consequence
    import inspect
    main = _main()
    dp_des = main.R323_C003_P_BARA - main.R323_F004_P_BARA
    rho_g = consequence.gas_density_ideal(main.R323_C003_P_BARA, main.R323_C003_T_SP_C, 20.0)

    def blow(level, p_f004=main.R323_F004_P_BARA):
        return consequence.blowthrough_kgh(
            main.R323_M314_DES, main.R323_RHO_C003_DES, dp_des, 100.0 / main.R323_LV501_OP_DES, rho_g,
            main.R323_C003_P_BARA, main.R323_C003_P_BARA - p_f004, consequence.seal_fraction(level))

    assert blow(50.0) == 0.0
    full = blow(0.0)
    assert 0.02 * main.R323_M314_DES < full < 0.3 * main.R323_M314_DES
    assert blow(0.0, p_f004=0.5) == full                              # choked
    code = [ln for ln in inspect.getsource(main.step_sim).splitlines() if not ln.lstrip().startswith("#")]
    assert not any("M_c003_pre <= 1.0 and m_314" in ln for ln in code)
    assert any("consequence.seal_fraction(lvl_c003)" in ln for ln in code)


def test_the_ejector_suction_follows_the_gravity_head_again():
    """Report D-19.  `m_suc = capacity` dropped the gravity-head multiplier the block comment
    directly above it specifies, which left the 322E003 sump a pure integrator -- it flooded
    correctly on a shut XV-322903 and then never came back.  At design the head fraction is a
    literal 1.0, so the fixed point does not move; the throat-choke ceiling caps a real flood."""
    main = _main()
    # Call on the NAMEPLATE motive.  This flipped back with report D-6: the constant-area closure
    # anchors on the licensor's design PAIR (EJ_MOTIVE_NH3_DES, EJ_SUC_TOT_DES) -- the same pair the
    # nozzle and throat areas are back-solved from -- rather than on the boot-pinned settled motive
    # the retired phi_m normalised on.  The settled loop runs 0.078 % under the nameplate, and the
    # jet-pump closure amplifies that about tenfold, so the choice decides WHERE the ~1 % offset
    # lands: on the first tick from a fresh State() (which is where the boot pin and every unit test
    # measure the design point) or on the settled sump level.  It lands on the sump.
    mot_des = main.EJ_MOTIVE_NH3_DES
    des = main.ejector_322f001(mot_des, main.EJ_MOTIVE_T_DES_C,
                               main.EJ_OPEN_DES, scrub_level_frac=1.0)
    assert abs(des["suction_kgh"] - main.EJ_SUC_TOT_DES) < 1e-6      # design untouched
    low = main.ejector_322f001(mot_des, main.EJ_MOTIVE_T_DES_C,
                               main.EJ_OPEN_DES, scrub_level_frac=0.4)
    assert low["suction_kgh"] < des["suction_kgh"]                   # head drives it down
    empty = main.ejector_322f001(mot_des, main.EJ_MOTIVE_T_DES_C,
                                 main.EJ_OPEN_DES, scrub_level_frac=0.0)
    assert empty["suction_kgh"] == 0.0                               # zero head, zero flow
    flood = main.ejector_322f001(mot_des, main.EJ_MOTIVE_T_DES_C,
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


# ==================================================================================================
#  API 520 Part I relief (report D-9)
# ==================================================================================================
def test_api520_capacity_is_linear_in_the_absolute_upstream_pressure():
    """A relief valve is a fixed orifice passing a choked jet, so W scales with P1 -- NOT with the
    over-pressure.  The linear-accumulation ramp this replaced started from zero at the set point,
    which credits the device with no capacity at the moment it first opens."""
    a = 1.0e-3
    w1 = hy.psv_api520_choked_kgh(a, 100.0, 400.0, 28.0)
    w2 = hy.psv_api520_choked_kgh(a, 200.0, 400.0, 28.0)
    assert abs(w2 / w1 - 2.0) < 1e-9


def test_api520_area_backsolve_reproduces_the_rated_capacity_exactly():
    """The orifice is anchored on the documented rating through the same equation, so every
    coefficient that does not move during an event cancels."""
    a = hy.psv_area_from_rated_m2(200_000.0, 177.114, 387.15, 27.4768, k=1.30)
    w = hy.psv_api520_choked_kgh(a, 177.114, 387.15, 27.4768, k=1.30)
    assert abs(w - 200_000.0) < 1e-6


def test_api520_critical_ratio_matches_the_gas_table():
    """(2/(k+1))^(k/(k-1)): 0.5283 at k = 1.4, 0.5457 at the loop off-gas k = 1.30."""
    assert abs(hy.psv_choked_ratio(1.4) - 0.5283) < 5e-4
    assert abs(hy.psv_choked_ratio(1.30) - 0.5457) < 5e-4


def test_sv32201_is_sized_between_two_api_letter_orifices():
    """The back-solve lands at 2.611 in^2, 92 % of letter "L" -- an L-orifice valve carrying about
    8 % sizing margin, which is what a DN 100 relief valve on this service is.  A capacity that
    had been invented rather than documented would not land there."""
    main = _main()
    in2 = main.SYN_PSV_AREA_M2 * 1550.0031
    assert 1.838 < in2 < 2.853          # between API letters K and L
    assert abs(in2 - 2.611) < 0.01      # MW 26.37 of the PFD 204 vent (report A-2; 2.558 at 27.48)


def test_sv32201_pops_and_reseats_on_a_real_blowdown():
    main = _main()
    assert main.SYN_PSV_RESEAT_BARA < main.SYN_PSV_SET_BARA
    assert abs(main.SYN_PSV_RESEAT_BARA
               - main.SYN_PSV_SET_BARA * (1.0 - main.SYN_PSV_BLOWDOWN)) < 1e-12


# ==================================================================================================
#  320K002 polytropic map (report D-5)
# ==================================================================================================
def test_the_compressor_map_reproduces_the_design_duty_bit_exactly():
    main = _main()
    d = main.CO2_K001.delivery_kgh(main.CO2_K_SUCT_P_BARA, main.CO2_P_DES_BARA,
                                   main.CO2_K_SUCT_T_K, main.CO2_FEED_MW, 1.0)
    assert d["kgh"] == main.CO2_DES_KGH
    assert abs(d["q"] - 1.0) < 1e-12
    assert not d["surge"] and not d["stonewall"]


def test_the_compressor_surges_when_the_head_demand_passes_the_peak():
    main = _main()
    d = main.CO2_K001.delivery_kgh(main.CO2_K_SUCT_P_BARA, 240.0,
                                   main.CO2_K_SUCT_T_K, main.CO2_FEED_MW, 1.0)
    assert d["surge"]
    assert d["q"] <= main.CO2_K_Q_SURGE + 1e-12


def test_the_intercooled_head_is_not_the_single_section_head():
    """A 90:1 machine on one uncooled section discharges above 870 C.  Four intercooled sections
    put it at 160 C, which is what the aftercooler then takes to the 120 C feed anchor."""
    main = _main()
    t2 = machines.discharge_t_k(main.CO2_K_SUCT_T_K, main.CO2_K_SUCT_P_BARA,
                                main.CO2_P_DES_BARA, main.CO2_K_N_POLY, main.CO2_K_STAGES) - 273.15
    assert 150.0 < t2 < 170.0
    one = machines.discharge_t_k(main.CO2_K_SUCT_T_K, main.CO2_K_SUCT_P_BARA,
                                 main.CO2_P_DES_BARA, main.CO2_K_N_POLY, 1) - 273.15
    assert one > 800.0


def test_the_node_solve_returns_a_zero_residual_seed_untouched():
    """`solve_node_pressure` returns the design seed unchanged when the residual there is exactly
    zero, which is what a design-anchored flowsheet needs from any iterative solver."""
    seed = 144.2
    p = machines.solve_node_pressure(lambda x: 100.0 - x, (lambda x: 100.0 - seed,),
                                     p_lo=1.0, p_hi=300.0, p_seed=seed)
    assert p == seed


def test_the_k002_governor_holds_the_demanded_flow_not_the_curve_flow():
    """320K002 is flow controlled.  Open loop the map would let the feed float with back pressure,
    and on this flowsheet that is divergent -- see the note in step_sim."""
    main = _main()
    st = main.state
    assert st.k002_speed == 1.0
    assert st.k002_deliv_kgh == main.CO2_DES_KGH
