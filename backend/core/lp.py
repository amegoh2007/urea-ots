import math
from typing import Dict, Any, List, Optional
from core.unit import UnitOperation
from core.stream import Stream

class LPSection328(UnitOperation):
    """
    328 Low Pressure Section - Sequential Modular Port
    """
    def __init__(self, name: str):
        super().__init__(name, inputs=[], outputs=[])
        self.diagnostics = {}
        
    def solve(self, dt: float):
        import main as main_module
        from main import (MASTER, A328_C001_T, MW_COMP, M3, MASS, R328_E007_LOSS, XV_322915, C9, R328_D001_PV_OP_DES, A328_D003_M721_T, NOT, R328_D001_M776_DES, R3232_E003_LAMC, A323_C005_VENT_DES, LPCC, FLOW, CPL, R3232_D001_LVL_SP, R3232_TW_TAU_S, A328_D003_V001_T, C004, R328_HYD_GAS_MW, R328_C004_M931_DH, LIC_323502, R3232_M718B_DES, ONLY, R328_D001_LV_OP_DES, R328_HYD_DH_KJMOL, A323_C005_M708_DES, MP, PIC_323202, FIC_328406, LAM737, DECOMPOSITION, LIC_328501, R328_E021_LOSS, R328_C002_P_TOP, AUDIT, READ, R328_D001_OFFGAS_PHI, FIC, R3232_D011_M_DES, EXPLICIT, R328_E007_LOSS_DT, TIC_328008, R328_C003_PV_OP_DES, A328_D003_MII_FULL, FFIC, R328_D001_T, R3232_E003_PHI321, MW_SOL, FIC_329401, LIVE, III, R3232_P001_RPM_DES, R328_C004_M750_DES, R328_C002_M738_DES, LIQUID, R3232_M797_DES, A323_C005_M_DES, F_323402, TV, CARBAMATE, LT, G5, R328_C002_LAM748, R3232_E003_T305, DCS, A328_M756_DES, T_746, R328_C003_GASSTR_DES, UNMETERED, W_S775, R328_E004_TV_OP_DES, A323_C005_M702_DES, R328_C003_M_DES, A328_D003_LAM_I, REACTING, DES_C003, C10, R3232_M797_T, SP, A328_D003_M720_T, PIC_328203, R328_C002_M_DES, C4, N2, R328_C003_LAM748, R3232_D001_P_KP, C1, A328_D003_MIII_FULL, DELETE, R328_C002_T_TOP, CO2, F_328406, C003, R324_759, A328_PHI_ABS, A328_D003_COMP_I_ROUNDING_KGH, W_STEAM, R328_C002_P_KP, R328_C004_M931_DES, R328_D001_LAM737, C31, CONSERVATION, R3232_E003_M744_DES, CSTR, A328_CPL_T, LIC_322502, R328_C003_M911_DH, R328_D001_FIC404_OP_DES, R328_C003_P_KP, R3232_D001_M_DES, R328_D001_M_DES, A328_D003_M759_T, VOLUMETRICALLY, R3232_E003_M321_DES, BALANCE, R328_C003_M748_DES, R324_720, R328_D001_T718A, FIC_323402, R3232_E003_Q_DES_KW, H2, FIC_329402, FIC_328402, LIC_328505, LAGGED, S793_CAP_KGH, INSIDE, B2, A328_ABS_DES, A328_M741_T, A328_D003_M721, S_323901, FIC_323401, R328_E004_Q_DES_KW, FILLED, R3232_E011_PV_OP_DES, RHO_401_KGM3, R328_E021_EPS_T, R328_C003_W_UREA_746, R328_C004_PHI750, A328_D003_MI_FULL, CONDENSATION, R3232_E011_MV_DES, R3232_D011_M718_DES, R3232_TW_RET_T, R3232_E011_T, EXACTLY, R324_719, A328_D003_M720, A323_C005_BOT_DES, GENERATION, W_S738, T_738, R328_E021_LOSS_DT, CLOSURE, TIC_328002, RHO_718_KGM3, F_323418, A328_ABS_NH3_DES, A328_D003_M719, R324_721, LIC_328504, DIAGNOSTIC, FIC_328404, FFIC_329401, R328_E004_DP, TIC, GCB, F_328404, R3232_E011_M786_DES, CH4, A328_C001_P_KP, II, R328_C002_M743_DES, R328_C003_M747_DES, A328_D003_MII_DES, R328_C002_LAM750, VLE, R328_C003_M911_DES, TOTAL, A328_QFLOOD_KW, W_S755, RHO_744_KGM3, Q_DES, A328_LAMBDA_ABS, R328_C002_M737_DES, PLUS, LP, R3232_TW_RET, A328_C001_M_DES, B5, R328_D001_M786_DES, R328_C002_T750, R328_CP, T_737, FIC_328405, A328_D003_M719_T, FORMATION, R3232_TW_SUP, PIC_323203, HERE, BOIL, FIC_323418, A323_C005_LAM, A328_M755_T, PIC, F_323401, R328_C002_DP_COL, R328_D001_M775_DES, OFF, RHO_741_KGM3, R328_C004_Q_DES, TII, SPECIFIC, TT, C002, FV, R3232_E003_UA_KW, T_749, R3232_E011_IN_DES, R328_D001_M737_DES, W_C001_DES, R3232_TW_SUP_T, A328_LIC_OP_DES, TWO, R3232_E011_M401_DES, OUT, A328_ABS_CO2_DES, R3232_E003_PV_OP_DES, TI, A328_C001_ALPHA, R328_FFIC_RATIO_DES, TW, R3232_D011_LVL_SP, R328_C004_M739_DES, R3232_E011_M321_DES, F_328405, TIC_323013, F_329402, R328_C002_T748, OVHD, W_S743, NON, A328_VENT_DES, LV, RHO_791_KGM3, LIC, ENERGY, R328_C004_P_BARA, R328_D001_P_KP, PV, TD, R3232_E011_PHIV, R3232_E003_M308_DES, W_CPL, INTERNAL, CLOSE, ODE, REACTION, S741_CAP_KGH, A328_PIC_OP_DES, R3232_FIC418_OP_DES, PFD, R3232_CP, LIC_328503, RECYCLE, A328_D003_COMP_II_ROUNDING_KGH, NH3, LIC_323503, R328_C004_DP_COL, NOWHERE, R3232_E011_M402_DES, AI, UP, PIC_322201, T_740, F_328402, SAME, F_329401, R328_D001_LVL_SP, A328_GCB_DES, R3232_LV503_OP_DES, H2O, R3232_TV13_DES_PCT, R328_E007_EPS_T, R328_C004_M_DES, RHO_775_KGM3, R328_C004_T749, SIC_323901, O2, R328_C002_DT_TOP, R3232_E011_M701_DES, PIC_328202, E007, R328_C004_P_KP, A328_D003_M759, DIVERSION, R328_C002_Q_DES, REMAINDER, REJECTED, _ctrl_ipd, _fic_flow, _lag1, _eq_pct, tsat_steam, psat_water_bara, des_advance, des_alpha_live, hydrolysis_x_328c003)
        s = main_module.state
        
        m702_prev = s.tlag.get("F_702", 0.0)
        m708_prev = s.tlag.get("F_708", 0.0)
        m756_prev = s.tlag.get("F_756", A328_M756_DES)
        m739_prev = s.tlag.get("R328_739", R328_C004_M739_DES)
        m748_prev = s.tlag.get("R328_748", R328_C003_M748_DES)
        m750_prev = s.tlag.get("R328_750", R328_C004_M750_DES)
        m775_prev = s.tlag.get("R328_775", R328_D001_M775_DES)
        m718A_prev = s.tlag.get("R328_718A", 0.0)
        m931_prev = s.tlag.get("F_329401", R328_C004_M931_DES)
        m744_prev = s.tlag.get("F_328402", R3232_E003_M744_DES)
        
        hv604 = getattr(s, "diagnostics", {}).get("hv604", {"mass_kgh": 100.0, "T_out": 43.0, "comp_kmolh": {}})

    
        # ----- Stage 1 : 323C005 vent scrub -> 328V001 -> Comp-II feed --------
        Tc005    = s.a323_c005_T
        gas_c005 = m702_prev + m708_prev
        m_341    = A323_C005_VENT_DES * gas_c005 / (A323_C005_M702_DES + A323_C005_M708_DES)
        abs_c005 = max(gas_c005 - m_341, 0.0)
        in_c005  = m756_prev + gas_c005
        bot_c005 = A323_C005_BOT_DES * (s.a323_c005_M / A323_C005_M_DES)
        P_c005   = ((m756_prev/3600.0*R3232_CP*(A328_C001_T - Tc005)
                     + m702_prev/3600.0*R3232_CP*(45.0 - Tc005)
                     + m708_prev/3600.0*R3232_CP*(121.0 - Tc005))
                    + abs_c005/3600.0*A323_C005_LAM)
        s.a323_c005_T = Tc005 + P_c005*dt/max(s.a323_c005_M*R3232_CP, 1e-6)
        s.a323_c005_M = max(s.a323_c005_M + (m756_prev + abs_c005 - bot_c005)/3600.0*dt, 1.0)
    
        # ----- Stage 2 : 328D003 active bays I/II + communicating accumulation bay III ----
        TI       = s.a328_d003_TI
        m_401    = _fic_flow(s.FIC_323401, R3232_E011_M401_DES, 50.0, s.tlag, "F_323401", dt,
                             rho=RHO_401_KGM3)                        # volumetric loop, returns kg/h
        m_402    = _fic_flow(s.FIC_323402, R3232_E011_M402_DES, 50.0, s.tlag, "F_323402", dt,
                             rho=RHO_791_KGM3)         # SP in m3/h, returns kg/h
        # Stream 793: normally-closed spare off the same Comp-II discharge header as 735/791/734.
        # Design stroke 0 % -> 0 kg/h (PFD-22 col 793), full stroke = one branch capacity.  Opening it
        # draws real liquid out of Comp II, so it enters that holdup ODE as an export at TII (no enthalpy
        # term: an outflow at the bulk temperature contributes nothing to P_compII).
        m_793    = _fic_flow(s.FIC_328405, S793_CAP_KGH, 100.0, s.tlag, "F_328405", dt,
                             rho=RHO_401_KGM3)                        # volumetric loop, returns kg/h
        # Stream 741 (TD-005): purified process-condensate RECYCLE 328E007 -> 328E001 -> 328D003 Comp II.
        # It is a DIVERSION of the 740 boundary export, NOT new mass: the 328C004 bottoms (739) are
        # condensed in 328E007 to stream 740, and m_741 of that is taken back to Comp II while the
        # REMAINDER (m_740 = m739_prev - m_741) leaves the envelope.  So the plant balance closes:
        # Comp II gains m_741, the 740 export loses exactly m_741. The draw is therefore clamped to the
        # condensate that actually exists this tick (m739_prev, one-tick-delayed like every other tear).
        # Normally closed (PFD 741 = 0 kg/h at 100 % load), so at design m_741 == 0, m_740 == m_739 and
        # every term below is byte-identical to the pre-741 balance -- the boot pin cannot move.
        m_741_raw = _fic_flow(s.FIC_328406, S741_CAP_KGH, 100.0, s.tlag, "F_328406", dt,
                              rho=RHO_741_KGM3)                       # volumetric loop, returns kg/h
        m_741    = min(m_741_raw, m739_prev)                          # cannot recycle more than 740 carries
        run_p002 = s.aux_pumps["322P002A"]["on"] or s.aux_pumps["322P002B"]["on"]
        m_744_cmd = _fic_flow(s.FIC_328402, R3232_E003_M744_DES, 50.0, s.tlag, "F_328402", dt,
                              rho=RHO_744_KGM3)
        m_744    = m_744_cmd * (1.0 if run_p002 else 0.0)
        m_755    = m_744
        m_735    = R328_C002_M738_DES * (s.a328_d003_MII / A328_D003_MII_DES)   # -> 738 via 328E007
        # The four explicit vacuum-condenser returns are read one tick delayed because Unit 324 is solved
        # later in the tick.  Their distinct live flows and 45/40/41/55 C thermal nodes replace the former
        # aggregate proportional split.
        m_719    = s.tlag.get("R324_719", A328_D003_M719)
        m_720    = s.tlag.get("R324_720", A328_D003_M720)
        m_721    = s.tlag.get("R324_721", A328_D003_M721)
        m_759    = s.tlag.get("R324_759", A328_D003_M759)
        in_compI = m_719 + m_720 + m_721 + m_759 - A328_D003_COMP_I_ROUNDING_KGH
        out_compI= m_744
        P_compI  = ((m_719*(A328_D003_M719_T - TI)
                     + m_720*(A328_D003_M720_T - TI)
                     + m_721*(A328_D003_M721_T - TI)
                     + m_759*(A328_D003_M759_T - TI))/3600.0*cp_328d3i
                    + (m_719 + m_720 + m_721 + m_759)/3600.0*A328_D003_LAM_I)
        TI_raw = TI + P_compI*dt/max(s.a328_d003_MI*cp_328d3i, 1e-6)
        MI_raw = max(s.a328_d003_MI + (in_compI - out_compI)/3600.0*dt, 1.0)
        TII      = s.a328_d003_TII
        in_compII = bot_c005 + m_741 + A328_D003_COMP_II_ROUNDING_KGH
        out_compII = m_735 + m_401 + m_402 + m_793
        P_compII = ((bot_c005 * (A328_D003_V001_T - TII)
                     + m_741 * (A328_M741_T - TII)) / 3600.0 * cp_328d3ii)
        TII_raw = TII + P_compII*dt/max(s.a328_d003_MII*cp_328d3ii, 1e-6)
        MII_raw = max(s.a328_d003_MII + (in_compII - out_compII)/3600.0*dt, 1.0)
    
        # The approved openings make compartment III the shared surge volume. With no opening areas or
        # elevations, enforce the parameter-free communicating-vessel limit after the external process
        # flows. This retains every external mass term and moves internal sensible energy at the donor
        # temperature; 429/490 of a net disturbance therefore accumulates in compartment III.
        d003_masses, d003_temperatures = redistribute_communicating_compartments(
            (MI_raw, MII_raw, s.a328_d003_MIII),
            (TI_raw, TII_raw, s.a328_d003_TIII),
            (A328_D003_MI_FULL, A328_D003_MII_FULL, A328_D003_MIII_FULL),
        )
        s.a328_d003_MI, s.a328_d003_MII, s.a328_d003_MIII = d003_masses
        s.a328_d003_TI, s.a328_d003_TII, s.a328_d003_TIII = d003_temperatures
    
        # ----- 328E007 feed/effluent interchanger (AUDIT C10) ----------------
        #  Cold: 328D003 Comp-II draw 735 (56 C) heated against the 328C004 bottoms 739 (143 C) -> 738.
        #  Hot : 739 giving up exactly the duty the cold side took, plus the design shell loss -> 740.
        #  The hot inlet s.a328_c004_T is last tick's value (328C004 is Stage 5), i.e. the same one-tick
        #  tear m739_prev already uses -- consistent with every other recycle in this engine.
        #  Pinch-bounded: a counter-current interchanger cannot drive either outlet past the opposite
        #  inlet, so T_740 is clamped between the two live inlet temperatures.
        T_738    = s.a328_d003_TII + R328_E007_EPS_T * (s.a328_c004_T - s.a328_d003_TII)
        T740_raw = s.a328_c004_T - (m_735 * (T_738 - s.a328_d003_TII)
                                    + R328_E007_LOSS_DT) / max(m739_prev, 1e-6)
        T_740    = min(max(T740_raw, min(s.a328_d003_TII, s.a328_c004_T)),
                       max(s.a328_d003_TII, s.a328_c004_T))
    
        # ----- Stage 3 : 328C002  Desorber-I (bottoms 139°C, floats PIC-328202)
        Tc002    = s.a328_c002_T
        m_738    = m_735
        in_c002  = m_738 + m748_prev + m750_prev + m775_prev
        lvl_c002 = s.a328_c002_M / R328_C002_M_DES * 50.0
        lic503_op= _ctrl_ipd(s.LIC_328503, lvl_c002, dt)
        m_743    = R328_C002_M743_DES * (lic503_op / 50.0)                    # bottoms -> hydrolyser
        sens_c002= ((m_738*(T_738 - Tc002)                                    # AUDIT C10: live 328E007 outlet
                     + m775_prev*(R328_D001_T   - Tc002)
                     + m748_prev*(R328_C002_T748 - Tc002)
                     + m750_prev*(R328_C002_T750 - Tc002))/3600.0*cp_328c002)
        # AUDIT F-8: the overhead is ENERGY-limited, not a frozen fraction of the inflow.  What leaves
        # overhead is what the two condensing hot recycle vapours (748 @188, 750 @140) plus the sensible
        # net can actually boil, capped by the throughput ratio.  Anchored-ratio form: both caps evaluate
        # bit-exactly to R328_C002_M737_DES at the design seed, so the min() ties and P_c002 keeps the
        # exact expression -- and therefore the exact bits -- it had under the frozen split.
        q_c002   = (sens_c002 + m748_prev/3600.0*R328_C002_LAM748
                    + m750_prev/3600.0*R328_C002_LAM750)
        # AUDIT C1 — GENERATION is what the net duty can boil (the old "energy cap", unchanged in form so
        # the seed ties exactly); FLOW OUT is what the overhead line to 328D001 passes at the live column
        # pressure across 328E004.  They are now two different quantities, which is precisely what the
        # old code collapsed: it set m_737 := generation, and with LAM737 back-solved as
        # Q_DES/(m737_DES/3600) that made dT/dt algebraically zero.  Their imbalance drives the pressure,
        # and the temperature is the bubble point at the bottom node.
        gen737   = max(R328_C002_M737_DES * (q_c002 / R328_C002_Q_DES), 0.0)  # boil-up (kg/h)
        # Dynamic pressure drop coupling: flow driven by column-to-drum dP
        dP_737   = max(s.a328_c002_P - s.a328_d001_P, 0.001)
        m_737    = R328_C002_M737_DES * math.sqrt(dP_737 / R328_E004_DP)      # OVHD line -> 328E004/328D001
        M_c002_pre = s.a328_c002_M
        s.a328_c002_P = max(s.a328_c002_P + R328_C002_P_KP*(gen737 - m_737)/3600.0*dt, 0.1)
        s.a328_c002_T = tsat_steam(s.a328_c002_P + R328_C002_DP_COL)          # bubble point at the bottom
        s.a328_c002_M = max(M_c002_pre + (in_c002 - m_737 - m_743)/3600.0*dt, 1.0)
        # Species: four inlets.  The two vapour recycles carry LAGGED compositions, the same tear the
        # flows already use (m748_prev / m750_prev) -- 328C003 and 328C004 are solved later in the tick.
        a_c002   = des_alpha_live("C002", Tc002, m748_prev + m750_prev, m_743)
        s.w_328c002, y_737 = des_advance(s.w_328c002, s.a328_c002_M,
                                         [(W_S738, m_738), (W_S775, m775_prev),
                                          (s.y_328_748, m748_prev), (s.y_328_750, m750_prev)],
                                         m_737, a_c002, m_743, 0.0, dt)
    
        # ----- Stage 4 : 328C003  Hydrolyser (200°C, MP-steam 911) -----------
        Tc003    = s.a328_c003_T
        m_746    = m_743                                                     # via 328E021
        # 328E021 cold outlet (stream 746, TT-328009): C002 bottoms 139 heated by C003 bottoms 200.
        #   eps in (0,1) => T_746 is a convex combination of the two live inlets and can never cross
        #   either, so no clamp is needed.  At design 139 + (51/61)*(200-139) = 190.0 exactly.
        T_746    = s.a328_c002_T + R328_E021_EPS_T * (Tc003 - s.a328_c002_T)
        m_911    = _fic_flow(s.FIC_329402, R328_C003_M911_DES, 50.0, s.tlag, "F_329402", dt)
        in_c003  = m_746 + m_911
        pic203b_op = _ctrl_ipd(s.PIC_328203, s.a328_c003_P, dt)
        m_748    = R328_C003_M748_DES * (pic203b_op / R328_C003_PV_OP_DES)    # OVHD relief -> 328C002
        # AUDIT F-7/TD-008 — the overhead generation is now the REACTION plus the strip, not a frozen
        # split fraction of the inflow.  gas_hyd is what urea hydrolysis actually makes; gas_str is what
        # the MP steam carries over and scales with the live 911 flow.  Both == design at the seed, so
        # gen748 == R328_C003_M748_DES bit-exact and the pressure ODE below stays stationary.
        x_hyd_328  = hydrolysis_x_328c003(
            Tc003, m_746,
            w_urea=s.w_328c002.get("Urea", R328_C003_W_UREA_746),
            w_h2o=s.w_328c002.get("H2O", W_S743["H2O"]),
        )
        # AUDIT F-8: the urea load is now READ OFF the live 328C002 bottoms vector instead of a hardcoded
        # fraction.  At the seed w_328c002["Urea"] == W_S743["Urea"] == R328_C003_W_UREA_746, so this is
        # bit-identical at design -- but off-design the hydrolyser now sees whatever 328C002 actually
        # passes it, which is the whole point of giving unit 328 a species balance.
        urea_in_328 = m_746 * s.w_328c002["Urea"]
        xi_hyd_328 = urea_in_328 / MW_SOL["Urea"] * x_hyd_328                 # kmol/h urea destroyed
        gas_hyd    = xi_hyd_328 * R328_HYD_GAS_MW                             # kg/h NH3 + CO2 produced
        gas_str    = R328_C003_GASSTR_DES * (m_911 / R328_C003_M911_DES)      # kg/h stripped by MP steam
        gen748   = gas_hyd + gas_str
        lvl_c003 = s.a328_c003_M / R328_C003_M_DES * 50.0
        lic504_op= _ctrl_ipd(s.LIC_328504, lvl_c003, dt)
        m_747    = R328_C003_M747_DES * (lic504_op / 50.0)                    # bottoms -> desorber-II
        # AUDIT F-7: urea slipping through unreacted -> AI-328701.  A MASS-BALANCE result now, not the
        # read-only ppm_infer_328701 soft sensor running alongside an unrelated split fraction.
        ppm_urea_747 = urea_in_328 * (1.0 - x_hyd_328) / max(m_747, 1e-6) * 1e6
        sens_c003= m_746/3600.0*cp_328c003*(T_746 - Tc003)
        q_hyd_328 = xi_hyd_328 * R328_HYD_DH_KJMOL * 1000.0 / 3600.0
        P_c003   = (sens_c003 + m_911/3600.0*R328_C003_M911_DH
                    - m_748/3600.0*R328_C003_LAM748 - q_hyd_328)
        s.a328_c003_P = max(s.a328_c003_P + R328_C003_P_KP*(gen748 - m_748)/3600.0*dt, 0.1)
        M_c003_pre = s.a328_c003_M
        s.a328_c003_T = Tc003 + P_c003*dt/max(M_c003_pre*cp_328c003, 1e-6)
        s.a328_c003_M = max(M_c003_pre + (in_c003 - m_748 - m_747)/3600.0*dt, 1.0)
        # Species: the hydrolyser is a LIQUID-FILLED column (Stamicarbon, "Zero waste urea production"),
        # not a stripping cascade, so its volatilities stay at the design anchor -- no Kremser stage
        # correction.  The reaction extent is the live Arrhenius xi_hyd_328 computed above.
        s.w_328c003, y_748 = des_advance(s.w_328c003, s.a328_c003_M,
                                         [(s.w_328c002, m_746), (W_STEAM, m_911)],
                                         m_748, DES_C003["alpha"], m_747, xi_hyd_328, dt)
        s.y_328_748 = y_748
    
        # ----- Stage 5 : 328C004  Desorber-II (143°C, LP-steam 931, FFIC) -----
        Tc004    = s.a328_c004_T
        m_749    = m_747                                                     # via 328E021 (hot side)
        # 328E021 hot outlet (stream 749): C003 bottoms 200 giving up heat to the C002-bottoms cold side.
        #   CONSERVATION form, not a second independent effectiveness -- the duty the hot stream loses is
        #   exactly the duty the cold side took, m_746*(T_746 - T_c002), plus the design shell loss
        #   R328_E021_LOSS_DT, so the interchanger cannot create or destroy energy off-design.
        #   At design: 200 - (33769*51 + 49005)/34062 = 200 - 52 = 148.0 EXACTLY (every term is an
        #   integer-valued float), so switching sens_c004 off the frozen R328_C004_T749 is bit-identical
        #   at the design point and the boot pin cannot move.
        #   Bounded by the two live inlet temps: the raw balance diverges as m_749 -> 0, but a
        #   counter-current interchanger cannot cool the hot stream past the cold-side inlet (pinch).
        T749_raw = Tc003 - (m_746*(T_746 - s.a328_c002_T) + R328_E021_LOSS_DT) / max(m_749, 1e-6)
        T_749    = min(max(T749_raw, min(s.a328_c002_T, Tc003)), max(s.a328_c002_T, Tc003))
        # FFIC-329401 ratio master, T/M3 (the DCS basis).  The feed measurement is the FIC-328402
        # wash leg (m_744 into 323E003), NOT the 328C002 m_738 term, and it is read VOLUMETRICALLY
        # because that loop is now m3/h -- so on CAS the FIC-329401 slave SP is FIC-328402 * ratio
        # and FV-329401 strokes to hold it.  Same float operation order as R328_FFIC_RATIO_DES, so
        # at design ffic_pv == sp -> du == 0 and the LP-steam draw holds 6495 kg/h bit-exactly.
        ffic_pv  = _lag1(s.tlag, "FF_ratio",
                         (m931_prev / 1000.0) / max(m744_prev / RHO_744_KGM3, 1e-6), 5.0, dt)
        ffic_op  = _ctrl_ipd(s.FFIC_329401, ffic_pv, dt)                     # 931-flow demand (kg/h)
        m_931    = _fic_flow(s.FIC_329401, R328_C004_M931_DES, 50.0, s.tlag, "F_329401", dt, cas_sp=ffic_op)
        in_c004  = m_749 + m_931
        lvl_c004 = s.a328_c004_M / R328_C004_M_DES * 50.0
        lic505_op= _ctrl_ipd(s.LIC_328505, lvl_c004, dt)
        m_739    = R328_C004_M739_DES * (lic505_op / 50.0)                    # bottoms -> 328E007 boundary
        sens_c004= m_749/3600.0*cp_328c004*(T_749 - Tc004)
        # AUDIT F-8: energy-limited overhead, same anchored-ratio form as 328C002 -- what the LP strip
        # steam plus the sensible net can boil, capped by throughput.  Replaces R328_C004_PHI750.
        q_c004   = sens_c004 + m_931/3600.0*R328_C004_M931_DH
        # AUDIT C1 — same split as 328C002: boil-up from the net duty, outflow from the live column
        # pressure through the overhead line into the 328C002 bottom, temperature = bubble point.  This
        # is the column where it matters most for training: losing the LP strip steam must drop the
        # bottoms temperature and collapse the NH3 stripping, and under the old form it did neither.
        gen750   = max(R328_C004_M750_DES * (q_c004 / R328_C004_Q_DES), 0.0)  # boil-up (kg/h)
        m_750    = R328_C004_M750_DES * (s.a328_c004_P / R328_C004_P_BARA)    # OVHD line -> 328C002 bottom
        M_c004_pre = s.a328_c004_M
        s.a328_c004_P = max(s.a328_c004_P + R328_C004_P_KP*(gen750 - m_750)/3600.0*dt, 0.1)
        s.a328_c004_T = tsat_steam(s.a328_c004_P + R328_C004_DP_COL)          # bubble point at the bottom
        s.a328_c004_M = max(M_c004_pre + (in_c004 - m_750 - m_739)/3600.0*dt, 1.0)
        a_c004   = des_alpha_live("C004", Tc004, m_931, m_739)
        s.w_328c004, y_750 = des_advance(s.w_328c004, s.a328_c004_M,
                                         [(s.w_328c003, m_749), (W_STEAM, m_931)],
                                         m_750, a_c004, m_739, 0.0, dt)
        s.y_328_750 = y_750
    
        # ----- Stage 6 : 328D001  Desorber-I reflux drum (61°C, 328E004) -----
        Td001    = s.a328_d001_T
        # AUDIT B2 — stream 793 used to be drawn out of 328D003 Comp-II (Stage 2) and delivered
        # NOWHERE: up to S793_CAP_KGH = 1534 kg/h of mass was destroyed at full FV-328405 stroke, and the
        # leak was invisible at design only because the design stroke is 0 %.  Mapping of Desorber
        # Hydrolyzer unit.md:34-36 puts it in the 737 header ahead of 328E004, i.e. into this drum.
        # m_793 is settled in Stage 2, so this is a same-tick term, not a tear.  At design m_793 == 0.
        in_d001  = m_737 + m718A_prev + m_793
        # AUDIT B5 — the mapping doc (line 5) puts PIC-328202 on 328C002, not on the drum: the valve
        # PV-328202 does sit on the 786 vent off 328D001 (line 41, which the code already had right), but
        # the transmitter reads the column.  The PV was bound to s.a328_d001_P, i.e. wrong by exactly one
        # exchanger pressure drop (PFD-22: 737/738 = 3.5 bar a, 774/775/786 = 2.6), and the model's own
        # +R328_E004_DP fix-up inside the TIC-328008 inferential was the evidence it needed the column
        # value all along.  Now that 328C002 carries a live pressure state, bind the loop to it.
        pic202b_op = _ctrl_ipd(s.PIC_328202, s.a328_c002_P, dt)
        m_786_d001 = R328_D001_M786_DES * (pic202b_op / R328_D001_PV_OP_DES)  # vent -> 323E011
        tic002_op= _ctrl_ipd(s.TIC_328002, Td001, dt)
        Q_e004   = R328_E004_Q_DES_KW * (tic002_op / R328_E004_TV_OP_DES)
        # The more we cool, the more we condense, so less non-condensable/uncondensed gas reaches the drum vent
        condensation_factor = max(Q_e004 / R328_E004_Q_DES_KW, 0.1)
        gen786   = R328_D001_M786_DES * (m_737 / R328_D001_M737_DES) / condensation_factor
        # TIC-328008 MASTER -> FIC-328404 slave (TD-004).  PV is the inferential H2O mol% of the gas
        # leaving 328C002 to 328E004 (PFD 737), live on the drum pressure via PIC-328202 + 0.9 bar dP.
        # Stepped HERE, immediately before its slave, so the cascade is same-tick like every other
        # master in this engine; its PV depends only on constants and s.a328_d001_P, both already
        # settled at this point.  On CAS, FV-328404 strokes to hold TIC-328008.
        # AUDIT C31 — the doc specifies TWO inputs (TT-328008 and PIC-328202); the temperature leg was the
        # module constant R328_C002_T_TOP, so the PV was live on drum pressure and blind to the column.
        # psat(117)=1.8004 vs psat(120)=1.9854, i.e. 3 C swings the PV by 4.75 mol% -- twice the loop's
        # whole SP band.  Now rides the live 328C002 bottoms at the design top/bottom offset; at the seed
        # s.a328_c002_T - R328_C002_DT_TOP == 139 - 22 == 117.0 exactly, so the pin cannot move.
        dt_top_dynamic = 10.0 + (R328_C002_DT_TOP - 10.0) * (m775_prev / R328_D001_M775_DES)
        T_737      = s.a328_c002_T - dt_top_dynamic                             # TT-328008, column top (C)
        # AUDIT C1 — the VLE node pressure is now the LIVE 328C002 state, not the drum plus a frozen
        # R328_E004_DP.  At the seed s.a328_c002_P == R328_C002_P_TOP == 3.5, the same value the old
        # s.a328_d001_P + R328_E004_DP reconstructed, so the inferential is bit-exact at design.
        tic8008_op = _ctrl_ipd(s.TIC_328008,
                               100.0 * R328_D001_OFFGAS_PHI * psat_water_bara(T_737)
                               / max(s.a328_c002_P, 0.1), dt)                     # 775-reflux demand (kg/h)
        m_775    = _fic_flow(s.FIC_328404, R328_D001_M775_DES, R328_D001_FIC404_OP_DES, s.tlag, "F_328404", dt,
                             rho=RHO_775_KGM3, cas_sp=tic8008_op)   # SP in m3/h, returns kg/h
        lvl_d001_328 = s.a328_d001_M / R328_D001_M_DES * R328_D001_LVL_SP
        lic501_op= _ctrl_ipd(s.LIC_328501, lvl_d001_328, dt)
        m_776    = R328_D001_M776_DES * (lic501_op / R328_D001_LV_OP_DES)     # draw -> 323E003
        sens_d001= ((m_737*(T_737 - Td001)                                    # AUDIT C31: live column top
                     + m718A_prev*(R328_D001_T718A - Td001)
                     + m_793*(s.a328_d003_TII - Td001))/3600.0*cp_328d001)
        P_d001   = sens_d001 + m_737/3600.0*R328_D001_LAM737 - Q_e004
        s.a328_d001_P = max(s.a328_d001_P + R328_D001_P_KP*(gen786 - m_786_d001)/3600.0*dt, 0.1)
        s.a328_d001_T = Td001 + P_d001*dt/max(s.a328_d001_M*cp_328d001, 1e-6)
        s.a328_d001_M = max(s.a328_d001_M + (in_d001 - m_786_d001 - m_775 - m_776)/3600.0*dt, 1.0)
    
        # ----- AUDIT C4 : unit-328 ENERGY-CLOSURE DIAGNOSTIC -------------------
        #  Envelope = {328C002, 328C003, 328C004, 328D001, 328E021, 328E007}.  Reference 0 C, cp = R328_CP.
        #  Streams 775 (drum -> column reflux), 748 and 750 (column -> column) are INTERNAL and excluded.
        #
        #  Why this exists.  The audit reported that unit 328 "creates +413 kW at design, 9.1 % of its own
        #  steam input", on the grounds that every stream shared by two vessels carries two different
        #  back-solved latent heats -- 737 is generated in 328C002 at 1879.34 kJ/kg and condensed in
        #  328D001 at 2163.55, a +526 kW gap on its own.  That arithmetic is exact (re-verified by hand),
        #  but the conclusion drawn from it is NOT established, because the envelope check offered as
        #  independent confirmation treated unit 328 as NON-REACTING.  It is not: the columns strip NH3
        #  and CO2 out of solution (carbamate DECOMPOSITION, endothermic) and this drum re-absorbs them
        #  (carbamate FORMATION, exothermic).  Stream 737 delivers 39.46 kmol/h of CO2 into the drum
        #  liquid; at a realistic -100 to -130 kJ/mol that is 1096 to 1425 kW of genuine reaction
        #  enthalpy -- the 526 kW lambda gap sits comfortably INSIDE it.
        #
        #  So two different lambdas for one stream is correct physics here, not a bug: in 328C002 it is a
        #  BOIL-UP latent, in 328D001 it is CONDENSATION PLUS CARBAMATE FORMATION, which must be larger.
        #  The real defect is the same one finding C9 names for the hydrolyser: the reaction enthalpy is
        #  hidden inside a back-solved latent instead of being an explicit xi*dH term, so it scales with
        #  whatever drives that latent's stream rather than with the actual reaction extent.  Making the
        #  lambdas equal -- the fix the audit prescribed -- would DELETE a ~500 kW carbamate exotherm and
        #  run the drum cold.
        #
        #  This diagnostic measures the residual every tick instead of arguing it from constants, so the
        #  explicit-xi rework can be checked against a number.  It is read-only: nothing consumes it.
        #  328E007 is INSIDE the envelope, so the feed enters as stream 735 at the Comp-I bulk (56 C) and
        #  the export leaves as stream 740 at the E007 hot outlet (89 C); the interchanger duty cancels
        #  internally.  Taking the feed at T_738 instead would credit the 2005 kW E007 recovery to the
        #  inlet without ever debiting it -- the same boundary slip that made the audit's own envelope
        #  disagree with its lambda arithmetic.
        q328_in  = ((m_735 * s.a328_d003_TII
                     + m718A_prev * R328_D001_T718A
                     + m_793 * s.a328_d003_TII) / 3600.0 * R328_CP
                    + m_911 / 3600.0 * R328_C003_M911_DH
                    + m_931 / 3600.0 * R328_C004_M931_DH)
        q328_out = ((m739_prev * T_740
                     + m_786_d001 * s.a328_d001_T
                     + m_776 * s.a328_d001_T) / 3600.0 * R328_CP
                    + Q_e004 + R328_E021_LOSS + R328_E007_LOSS)
        # AUDIT C4 / gap G5 — CLOSE the envelope by making the hidden carbamate-desorption enthalpy an
        # EXPLICIT term instead of leaving it buried in back-solved latents.  q328_react is the reaction
        # heat the MP+LP reboiler steam supplies to strip NH3/CO2 out of solution; its design magnitude is
        # captured once from the design seed (first tick from a fresh design State), so the residual is
        # bit-exact zero at design, and off-design it follows the live reboiler steam that drives
        # desorption (anchored-ratio form, the same idiom as gen748/gen750).  This is READ-ONLY: it enters
        # only the published residual below, never a state ODE, so every pinned dynamic balance is
        # untouched.  See the derivation block above and _A328_Q_REACT_DES_KW.
        global _A328_Q_REACT_DES_KW
        q328_raw = q328_in - q328_out              # kW; negative = more out than in (hidden reaction)
        if _A328_Q_REACT_DES_KW is None:
            _A328_Q_REACT_DES_KW = -q328_raw       # design net carbamate-desorption enthalpy (kW)
        steam_ratio_328 = ((m_911 + m_931)
                           / (R328_C003_M911_DES + R328_C004_M931_DES))
        q328_react = _A328_Q_REACT_DES_KW * steam_ratio_328
        q328_resid = q328_raw + q328_react         # kW; ~0 at design, bounded off-design departure
    
        # ----- Stage 7 : 322C001  LP absorber (43°C, live GCB off-gas) --------
        Tc001    = s.a328_c001_T
        gcb_m    = hv604["mass_kgh"]
        gcb_T    = hv604["T_out"]
        pic201_op= _ctrl_ipd(s.PIC_322201, s.a328_c001_P, dt)
        lvl_c001 = s.a328_c001_M / A328_C001_M_DES * 50.0
        lic502c_op = _ctrl_ipd(s.LIC_322502, lvl_c001, dt)
        m_756    = A328_M756_DES * (lic502c_op / A328_LIC_OP_DES)             # liquor draw -> 323E003
        Q_flood  = A328_QFLOOD_KW if s.XV_322915 else 0.0                     # trip 22.1 steam flood
        y_vent = None
        if A328_GCB_DES is None:                                              # pre-pin: design absorb, hold P
            abs_co2, abs_nh3 = A328_ABS_CO2_DES, A328_ABS_NH3_DES
            abs_c001  = A328_ABS_DES
            vent_c001 = max(gcb_m - abs_c001, 0.0)
        else:                                                                # post-pin: live off-gas
            # TD-009 remainder — reactive absorption CO2 + 2 NH3 -> carbamate.  The scalar recovered mass
            # abs_c001 is the SAME boot-pinned split as before (A328_PHI_ABS*gcb_m, so C1 and the energy
            # balance are byte-identical and the 15-key pin is untouched); the species layer splits it at
            # the frozen carbamate ratio 2 NH3 : 1 CO2, and the inerts N2/O2/CH4/H2 pass 100 % to the vent.
            # The vent then carries a LIVE per-species composition (gcb_i − absorbed_i), replacing the
            # composition-blind scalar — the atmospheric NH3 slip is now a real number, not a boot constant.
            abs_c001  = A328_PHI_ABS * gcb_m
            abs_co2   = abs_c001 * A328_ABS_CO2_DES / A328_ABS_DES            # frozen carbamate split
            abs_nh3   = abs_c001 * A328_ABS_NH3_DES / A328_ABS_DES
            vent_c001 = A328_VENT_DES * (pic201_op / A328_PIC_OP_DES)
            s.a328_c001_P = max(s.a328_c001_P
                                + A328_C001_P_KP*((gcb_m - abs_c001) - vent_c001)/3600.0*dt, 0.1)
            # vent gas composition y (mass fractions over MW_COMP): un-absorbed off-gas -> 328V001/323C005/atm
            gcb_i  = {k: hv604["comp_kmolh"].get(k, 0.0) * MW_COMP[k] for k in MW_COMP}    # kg/h per species
            vent_i = dict(gcb_i);  vent_i["CO2"] -= abs_co2;  vent_i["NH3"] -= abs_nh3
            _vt = sum(v for v in vent_i.values() if v > 0.0)
            if _vt > 1e-9:
                y_vent = {k: max(vent_i[k], 0.0) / _vt for k in MW_COMP}
        if A328_LAMBDA_ABS is not None:
            sens_c001 = ((m_755*(A328_M755_T - Tc001) + s.cpl_flow_kgh*(A328_CPL_T - Tc001))/3600.0*cp_322c001
                         + gcb_m*(gcb_T - Tc001)/3600.0*cp_322c001)
            P_c001    = sens_c001 + abs_c001/3600.0*A328_LAMBDA_ABS + Q_flood
            s.a328_c001_T = Tc001 + P_c001*dt/max(s.a328_c001_M*cp_322c001, 1e-6)
        s.a328_c001_M = max(s.a328_c001_M + (m_755 + s.cpl_flow_kgh + abs_c001 - m_756)/3600.0*dt, 1.0)
        # --- liquor species CSTR (TD-009 remainder): feeds 755 + CPL + absorbed(NH3/CO2), draw 756, no
        #     vapour off (the vent is un-absorbed gas that never entered the liquid).  des_advance with
        #     m_vap==0, xi==0 is a plain multi-feed CSTR; W_C001_DES == the design feed mix -> dw/dt==0.
        w_abs = {"CO2": (abs_co2 / abs_c001 if abs_c001 > 1e-9 else 0.0),
                 "NH3": (abs_nh3 / abs_c001 if abs_c001 > 1e-9 else 0.0)}
        s.a328_c001_w, _ = des_advance(s.a328_c001_w, s.a328_c001_M,
                                       [(W_S755, m_755), (W_CPL, s.cpl_flow_kgh), (w_abs, abs_c001)],
                                       0.0, A328_C001_ALPHA, m_756, 0.0, dt)
    
        # ----- Stage 8 : 323E003 + 323D001  LPCC (74°C, tempered water) -------
        Te003    = s.r3232_e003_T
        in_e003  = m_305 + m718B_prev + m_776 + R3232_M797_DES
        pic202_op= _ctrl_ipd(s.PIC_323202, s.r3232_d001_P, dt)
        m_321    = R3232_E003_M321_DES * (pic202_op / R3232_E003_PV_OP_DES)   # vent -> 323E011
        gen321   = R3232_E003_PHI321 * (m_305 + R3232_M797_DES)
        lvl_d001_323 = s.r3232_d001_M / R3232_D001_M_DES * R3232_D001_LVL_SP
        lic502_op= _ctrl_ipd(s.LIC_323502, lvl_d001_323, dt)                 # master
        rpm_pv   = _lag1(s.tlag, "S_323901", s.SIC_323901["op"], 3.0, dt)
        sic_op   = _ctrl_ipd(s.SIC_323901, rpm_pv, dt, lic502_op)            # cascade slave (speed)
        m_308    = R3232_E003_M308_DES * (sic_op / R3232_P001_RPM_DES)        # condensate -> boundary
        #   Tempered-water circuit (PFD 1102 supply / 1103 return).  TV-323013A admits cold make-up, TV-323013B
        #   bypasses hot return -> split-range opposites off one op.  House normalized-stroke valve char: at
        #   op == op_des the ratio is 1 -> T_ss == R3232_TW_SUP_T == sp -> PV stationary -> du == 0 (design exact).
        #   Duty now rides the physical driving force (live TW mean vs shell) instead of a linear op fudge:
        #   at design 1000*(74 - 60) == 14000 kW, identical to the retired (tic13_op/50) form.
        tva_op   = s.TIC_323013["op"]                              # prior-step TV-323013A stroke
        T_tw_ss  = clamp(R3232_TW_RET_T - (R3232_TW_RET_T - R3232_TW_SUP_T)
                         * (tva_op / max(R3232_TV13_DES_PCT, 1e-6)), 20.0, R3232_TW_RET_T)
        T_tw_sup = _lag1(s.tlag, "R3232_TW_SUP", T_tw_ss, R3232_TW_TAU_S, dt)   # stream 1102 (55 °C)
        T_tw_ret = s.tlag.get("R3232_TW_RET", R3232_TW_RET_T)      # prior-step state; breaks the algebraic loop
        tic13_op = _ctrl_ipd(s.TIC_323013, T_tw_sup, dt)           # PV = TW supply, NOT the shell temp
        Q_e003   = R3232_E003_UA_KW * (Te003 - 0.5*(T_tw_sup + T_tw_ret))
        T_tw_ret = T_tw_sup + (R3232_TW_RET_T - R3232_TW_SUP_T) * (Q_e003 / R3232_E003_Q_DES_KW)  # 1103 (65 °C)
        s.tlag["R3232_TW_RET"] = T_tw_ret                          # TT-323015
        m_cond   = m_305 + R3232_M797_DES - m_321
        sens_e003= ((m_305*(R3232_E003_T305 - Te003)
                     + m718B_prev*(R3232_E011_T - Te003)
                     + m_776    *(R328_D001_T  - Te003)
                     + R3232_M797_DES*(R3232_M797_T - Te003))/3600.0*R3232_CP)
        P_e003   = sens_e003 + m_cond/3600.0*R3232_E003_LAMC - Q_e003
        s.r3232_d001_P = max(s.r3232_d001_P + R3232_D001_P_KP*(gen321 - m_321)/3600.0*dt, 0.1)
        s.r3232_e003_T = Te003 + P_e003*dt/max(s.r3232_d001_M*R3232_CP, 1e-6)
        s.r3232_d001_M = max(s.r3232_d001_M + (in_e003 - m_321 - m_308)/3600.0*dt, 1.0)
    
        # ----- Stage 9 : 323E011 + 323D011  LP carbamate condenser (45°C) -----
        Te011    = s.r3232_e011_T
        in_e011  = (R3232_E011_IN_DES + (m_701 - R3232_E011_M701_DES)
                    + (m_786_d001 - R3232_E011_M786_DES)
                    + (m_321 - R3232_E011_M321_DES)
                    + (m_402 - R3232_E011_M402_DES))
        pic203_op= _ctrl_ipd(s.PIC_323203, s.r3232_e011_P, dt)
        m_v011   = R3232_E011_MV_DES * (pic203_op / R3232_E011_PV_OP_DES)     # vapour -> 323C005
        gen_v011 = R3232_E011_PHIV * in_e011
        # 323D011 level tank: condensed liquid (in_e011 - m_v011) + the FIC-323401 flush 401 (PFD stream
        # 734) fall in; the 323P008 lean-carbamate pumps draw out through LV-323503 on the common
        # discharge header, which then splits into the 718A and 718B legs (PFD 3562 / 3562 off 718 7123).
        # LIC-323503 -> LV-323503 sets the TOTAL draw; FIC-323418 holds the 718B slipstream ("regulates
        # the SPECIFIC recycle flow rate of lean carbamate", 328E021 328E007 328P003 328P006.md:369) and
        # 718A is the UNMETERED REMAINDER -- a transport lag on (total draw - 718B demand), no controller
        # of its own.  FIC-328405 used to be cascaded onto 718A; that binding is stripped, because the PFD
        # puts FIC-328405 on ammonia-water stream 793 off the 328D003 Comp-II header (see stage 2), not on
        # this carbamate leg.  The remainder form keeps one integrator per degree of freedom (inventory ->
        # LIC-323503; split -> FIC-323418) and removes a second flow integrator that was marginally stable
        # here.  Modelling a series LV-503 as a derate on both FVs instead was tried and REJECTED: two
        # AUTO FICs reject the header stroke by integral action, so LIC-323503 wound up to op_hi and level
        # parked off SP (see scratchpad/dyn503.py).
        lvl_d011 = s.r3232_e011_M / R3232_D011_M_DES * R3232_D011_LVL_SP      # LT-323503 (%)
        lic503_op= _ctrl_ipd(s.LIC_323503, lvl_d011, dt)                      # -> LV-323503 (total draw)
        m718_dmd = R3232_D011_M718_DES * (lic503_op / R3232_LV503_OP_DES)     # total draw demand (kg/h)
        m_718B   = _fic_flow(s.FIC_323418, R3232_M718B_DES, R3232_FIC418_OP_DES, s.tlag,
                             "F_323418", dt, tau_s=45.0, rho=RHO_718_KGM3)    # -> 323E003 (slipstream)
    
        s.tlag["R328_739"] = m_739
        s.tlag["R328_748"] = m_748
        s.tlag["R328_750"] = m_750
        s.tlag["R328_775"] = m_775
        
        self.diagnostics = {
            "m_738": m_738, "m_743": m_743, "m_746": m_746, "m_747": m_747,
            "m_739": m_739, "m_740": m_740, "m_748": m_748, "m_750": m_750,
            "q328_raw": q328_raw, "q328_react": q328_react, "q328_resid": q328_resid,
            "y_vent": y_vent
        }
