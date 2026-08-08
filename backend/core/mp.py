import math
from typing import Dict, Any, List, Optional
from core.unit import UnitOperation
from core.stream import Stream

class MPSection323(UnitOperation):
    """
    323 Medium Pressure Section - Sequential Modular Port
    Groups Rectifying Column, Heater, Flash Tank, Pre-Evaporator, and Solution Tank.
    """
    def __init__(self, name: str):
        super().__init__(name, inputs=[], outputs=[])
        self.diagnostics = {}
        
    def solve(self, dt: float):
        import main as main_module
        from main import (R328_775, R323_LV501_OP_DES, R323_D002_VOL_I_M3, F010, DESORPTION, R323_D002_VOL_II_M3, FIC_324401, HIC, R328_C004_T, SOL_C003, LPCC, TIC_323007, R323_Q701_DES_KW, R3232_718B, IN, FRACTION, ZERO, Q305_DES, E003, R328_748, ONLY, R3232_M718B_DES, A323_C005_M708_DES, DESIGN, PT, R323_C003_M_FULL, R324_HIC9605_DES_PCT, DRY, R323_F010_P_KP, AUDIT, FIC, R323_M324_DES, ITS, A328_D003_TII, EU, R323_D002_RHO, R328_D001_T, R3232_M718A_DES, B1, LIVE, OWN, R328_C002_T_BOT, R323_F004_M_TAU_S, R323_M701_DES, HIC_323605, R323_M331_DES, R323_LAMBDA_305, MUST, W_S331, R323_PHI_V305, R323_M314_DES, D001, LIMITED, R323_F010_TBUB_DES, HIC_329605, DCS, CLOSED, A328_D003_TI, UA, A323_C005_M702_DES, C10, LIC_323501, R323_F004_P_GAIN, FIXED, R324_W_IN, HV_323D002_TIE, M305_DES, R323_HIC605_DES_PCT, UNITS, R3232_744, FT, F004, STEAM, C003, LIC_323507, R328_C004_M931_DES, R3232_E003_M744_DES, ONCE, SOL_SPECIES, R323_F004_T_SP_C, LI, IS, NEVER, R328_C002_M748_DES, R323_FV401_OP_DES, R322_756, COLD, C6, R323_E002_UA_KW, R324_708, THE, STRIP_BOT_DES_KGH, R323_MEVAP_DES, ONE, IDENTICALLY, SOL_F004, HEAD, BOTH, R323_QEVAP_DES_KW, A323_C005_M756_DES, R328_C002_M775_DES, A328_CP, IAPWS, R3232_702, TIC, P_LP, FIX, II, R324_E003_T_SP_C, ACTIVE, RECIRCULATION, R323_E010_UA_KW, W_S317, HV, R323_F004_P_BARA, A328_LAMBDA_ABS, LP, R324_W_EV2, R3232_718A, R323_M319_DES, PIC_329208, CONCENTRATION, R328_CP, EVERY, PIC, NEGATIVE, R323_LAMBDA_701, R328_C003_T, FV, TIE, ON, LIC_323505, AND, TI, R328_750, R323_EVAP_LAMBDA, LOW, INVARIANT, SOL_F010, R328_C002_M750_DES, LV, ENERGY, R323_Q305_DES_KW, R323_M331_T_C, R323_LV505_OP_DES, LIC, D002, PV, CONSTANT, TD, R328_M931, ODE, ADD, R323_F010_T_SP_C, PFD, NH3, R323_C003_M_TAU_S, VOLUME, UP, TIC_323012, SAME, DID, LINEAR, R323_C003_P_TAU_S, R323_F004_M_FULL, EMPTY, PIN, PIC_329202, R323_C003_T_SP_C, R323_F010_P_BARA, C2, A328_C001_T, R323_F004_P_TAU_S, R323_F010_M_TAU_S, R323_M305_DES, _ctrl_ipd, _fic_flow, _lag1, _eq_pct, tsat_steam, psat_water_bara, des_advance, des_alpha_live, sol_advance, urea_soln_cp, gravity_outflow_323f010, bubble_T_raoult, clamp)
        s = main_module.state
        
        m322_prev = s.tlag.get("F_322", 0.0)
        
        # Read inputs for MP section (using state to bridge the old variables for now)
        strip = getattr(s, "diagnostics", {}).get("strip", {})
        drain_kgh = strip.get("bot_kgh", 0.0) # approx
        T_bot_disp = strip.get("T_bot", 135.0) # approx
        w_bot = getattr(s, "w_bot", {}) # This needs to be correctly mapped from stripper
        if not w_bot: 
            w_bot = strip.get("bot_mass_pct", {})
        
        m_209 = drain_kgh
        T_209 = T_bot_disp
        
        # ---- Stage 1: Rectifying Column 323C003 + Recirc Heater 323E002  (hold 135 C) ------------
        #  Cascade  TIC-323007 (temp master, EU) -> PIC-329202 (LP-steam chest-P slave) -> heater duty.
        tic07_op  = _ctrl_ipd(s.TIC_323007, s.r323_c003_T, dt)                        # steam-P demand (bar a)
        pic02_pv  = clamp(s.PIC_329202["op"] / 100.0 * s.steam.P_LP, 0.0, s.steam.P_LP)  # live LP-header chest P
        pic02_op  = _ctrl_ipd(s.PIC_329202, pic02_pv, dt, cas_sp=tic07_op)            # steam valve stroke (%)
        p_chest_e002 = steam_chest_pressure(pic02_op, s.steam.P_LP)
        # AUDIT F-10 — a CONDENSING-STEAM chest can only ADD heat.  Un-floored, shutting PV-329202
        # clamps p_chest to 0.02 bar a (tsat ~17.5 C) and UA·(tsat − T) becomes a large NEGATIVE duty,
        # i.e. the heater turns into a refrigerator and drags the column to ~14 C.  Physically the
        # chest simply stops condensing and Q -> 0.  At design Q is strongly positive -> max() is the
        # identity -> bit-exact.  Same floor applied to 323E010, 324E001, 324E003.
        Q_e002_kw = max(R323_E002_UA_KW * (tsat_steam(p_chest_e002) - s.r323_c003_T), 0.0)  # heater duty (kW)
        # AUDIT F-2 — boil-up is ENERGY-LIMITED, not a frozen split fraction.  q_avail is the latent
        # duty actually left after the feed has been brought to the column temperature; the overhead
        # cannot exceed what that duty can vaporise.  min() with the composition split keeps the
        # design point bit-exact (both branches evaluate to R323_M305_DES) and makes the correct
        # failure mode appear: PV-329202 shut -> Q_e002 -> 0 -> boil-up collapses instead of the
        # temperature ODE absorbing an impossible latent load.
        # AUDIT TD-014 — the boil-up above used to consume the WHOLE available duty, and R323_LAMBDA_305
        # is back-solved as Q305_DES/(M305_DES/3600), so m_305·λ/3600 cancelled q_avail term for term and
        # the column-temperature ODE below evaluated to IDENTICALLY ZERO on this branch.  TIC-323007 was
        # then integrating against a plant of zero gain: whatever it did to the reboiler was exactly
        # undone by the boil-up it produced, T never moved off 135.00001 °C, and its velocity-form
        # integral walked the steam valve down forever at a rate set by Kc·dt/Ti — i.e. a LINEAR,
        # NEVER-ARRESTING, TICK-INVARIANT ramp.  That ramp is the whole of TD-014: measured −0.0041 pp/h
        # of urea here, −0.0044 at 323F004, −0.0067 at 323F010, with the stripper bottoms feeding it
        # bit-flat for 6 h.  It was one-sided because the split branch caps the other direction.
        #
        # The closure is the one 323F004 already uses and the one the physics demands: the liquid sits at
        # its BUBBLE POINT, so the duty that is not spent boiling walks the holdup toward it over the
        # stage's own residence time.  Substituting into the ODE gives exactly dT/dt = (T_bub − T)/τ, so
        # energy is still conserved and the temperature is a real state with a real driver.  323C003's
        # bubble point rides the live column pressure (PT-323201), which is itself driven by the live
        # top-vapour rate — so TIC-323007 now has a genuine, correctly-signed plant: more duty -> more
        # 305 -> higher P -> higher T_sat -> higher T.
        # Design: P == 4.1 -> the tsat bracket is a literal 0.0 -> T_bub == 135.0 == T -> q_relax == 0.0
        # -> q_avail − 0.0 == q_avail bit-identically -> m_305 == R323_M305_DES exactly (the min() ties).
        T_bub_c003 = R323_C003_T_SP_C + (tsat_steam(s.r323_c003_P) - _R323_TSAT_C003_DES)
        q305_relax_kw = (s.r323_c003_M * cp_c003 * (T_bub_c003 - s.r323_c003_T)
                         / R323_C003_M_TAU_S)                                         # kW retained to reach bubble point
        T_strip_bot = s.tlag.get("TT_322004", STRIP_T_BOTTOM_DES_C)
        T_flash_sat = TT_323001
        q_flash_avail_kw = (m_feed_323 / 3600.0 * cp_feed323 * (T_strip_bot - T_flash_sat))  # kW released by letdown flash
        
        # Flash gas bypasses the pool and directly becomes vapor
        m_flash_gas = max(R323_M305_DES * (q_flash_avail_kw / R323_Q305_DES_KW), 0.0)
        
        # The pool consumes reboiler duty to reach bubble point
        m_pool_vap  = max(R323_M305_DES * ((Q_e002_kw - q305_relax_kw) / R323_Q305_DES_KW), 0.0)
        
        m_305     = min(R323_PHI_V305 * m_feed_323, m_flash_gas + m_pool_vap)                 # top vapor -> 323E003 LPCC (305, kg/h)
        lvl_c003  = clamp(s.r323_c003_M / R323_C003_M_FULL * 100.0, 0.0, 100.0)
        lv501_op  = _ctrl_ipd(s.LIC_323501, lvl_c003, dt)                             # LV-323501 stroke (%)
        m_314     = max(R323_M314_DES * (lv501_op / R323_LV501_OP_DES), 0.0)          # bottom drain -> flash (kg/h)
        P_c003    = (q_flash_avail_kw + Q_e002_kw - m_305 / 3600.0 * R323_LAMBDA_305) # net kW on holdup

        M_c003_pre = s.r323_c003_M
        s.r323_c003_T = s.r323_c003_T + P_c003 * dt / max(M_c003_pre * cp_c003, 1e-6)
        s.r323_c003_M = max(M_c003_pre + (m_feed_323 - m_305 - m_314) / 3600.0 * dt, 1.0)
        # AUDIT F-8/TD-009: species balance on the SAME flows the mass ODE above just used.  The feed
        # composition is the LIVE stripper bottoms (renormalised onto the six solution species), so a
        # change in strip efficiency now propagates all the way to the product -- previously the whole
        # downstream train was blind to it.  y_305 follows the live liquid through the relative
        # volatilities (C6 normalisation); the biuret extent is the real 2 Urea -> Biuret + NH3.
        y_305      = sol_vapour_y(s.w_c003, SOL_C003["alpha"])
        xi_c003    = sol_biuret_xi("C003", M_c003_pre, s.w_c003, s.r323_c003_T)
        s.w_c003   = sol_advance(s.w_c003, M_c003_pre, s.r323_c003_M, m_feed_323, w_feed_323,
                                 m_305, y_305, m_314, xi_c003, dt)
        # PT-323201 reduced-order gas-load coupling. `s.r3232_d001_P` is the beginning-of-substep
        # E003/D001 pressure; that state is advanced later, preserving the explicit tear.
        r_lv_c003 = drain_kgh / STRIP_BOT_DES_KGH
        r_305_c003 = m_305 / R323_M305_DES
        p_c003_tgt = c003_pressure_target_bara(r_lv_c003, r_305_c003, s.r3232_d001_P)
        s.r323_c003_P = clamp(
            s.r323_c003_P + (p_c003_tgt - s.r323_c003_P) / R323_C003_P_TAU_S * dt,
            1.0,
            12.0,
        )
    
        # ---- Stage 2: Flash Tank 323F004  (adiabatic letdown 4.1 -> 1.13 bar, hold 106 C) --------
        # AUDIT F-1 — TRUE isenthalpic flash (was a frozen split fraction of m_314, so a ±30 °C swing
        # in the Stage-1 outlet produced identical vapour).  Two coupled statements:
        #   (a) saturation constraint  T_flash = Tsat(P_drum) anchored at the design bubble point;
        #   (b) enthalpy balance       m_701·λ_701 = m_314·cp·(T_in − T_flash) − M·cp·(T_sat − T)/τ
        #       i.e. the sensible surplus of the letdown flashes off, less whatever is needed to walk
        #       the drum to its bubble point over its own liquid residence time.  Substituting (b) into
        #       the energy ODE below yields exactly dT/dt = (T_sat − T)/τ, so energy stays conserved.
        # Design: P == 1.13 -> T_sat == 106.0 -> relax term ≡ 0 and q701_avail_kw == R323_Q701_DES_KW
        # bit-identically (same operand order) -> m_701 == R323_M701_DES exactly.
        T_sat_f004 = R323_F004_T_SP_C + (tsat_steam(s.r323_f004_P) - _R323_TSAT_F004_DES)
        q701_relax_kw = (s.r323_f004_M * cp_f004 * (T_sat_f004 - s.r323_f004_T)
                         / R323_F004_M_TAU_S)                                         # kW retained to reach bubble point
        q701_avail_kw = m_314 / 3600.0 * cp_c003 * (s.r323_c003_T - s.r323_f004_T)      # kW released by the letdown
        m_701     = max(R323_M701_DES * ((q701_avail_kw - q701_relax_kw) / R323_Q701_DES_KW),
                        0.0)                                                          # flash vapor -> LPCC (701, kg/h)
        lvl_f004  = clamp(s.r323_f004_M / R323_F004_M_FULL * 100.0, 0.0, 100.0)
        lv505_op  = _ctrl_ipd(s.LIC_323505, lvl_f004, dt)                            # LV-323505 stroke (%)
        m_319     = max(R323_M319_DES * (lv505_op / R323_LV505_OP_DES), 0.0)          # drain -> pre-evaporator (kg/h)
        P_f004    = (m_314 / 3600.0 * cp_c003 * (s.r323_c003_T - s.r323_f004_T)
                     - m_701 / 3600.0 * R323_LAMBDA_701)                              # adiabatic (no Q) kW
        M_f004_pre = s.r323_f004_M
        s.r323_f004_T = s.r323_f004_T + P_f004 * dt / max(M_f004_pre * cp_f004, 1e-6)
        s.r323_f004_M = max(M_f004_pre + (m_314 - m_701 - m_319) / 3600.0 * dt, 1.0)
        y_701      = sol_vapour_y(s.w_f004, SOL_F004["alpha"])          # AUDIT F-8: flash vapour comp
        xi_f004    = sol_biuret_xi("F004", M_f004_pre, s.w_f004, s.r323_f004_T)
        s.w_f004   = sol_advance(s.w_f004, M_f004_pre, s.r323_f004_M, m_314, s.w_c003,
                                 m_701, y_701, m_319, xi_f004, dt)
        #  323F004 hydraulic coupling: forward pressure accumulation from live flash-vapour flow (701).
        #  Opening LV-323501 raises m_314 -> m_701 > design => flash-drum P relaxes UP (feeds PIC-323203 LP node).
        p_f004_tgt = R323_F004_P_BARA + R323_F004_P_GAIN * (m_701 - R323_M701_DES) / R323_M701_DES
        s.r323_f004_P = clamp(s.r323_f004_P + (p_f004_tgt - s.r323_f004_P) / R323_F004_P_TAU_S * dt, 0.3, 6.0)
    
        # ---- Stage 3: Pre-evaporator 323F010 + Heater 323E010  (vacuum 0.46 bar, hold 99 C) ------
        #  Cascade  TIC-323012 (temp master) -> PIC-329208 (LP-steam chest-P slave) -> heater duty.
        #  Uncontrolled separator -> design-anchored hydraulic outlet; holdup is a real state.
        #  AUDIT F-11: stream 331 (urea-recovery return from the granulation scrubber) joins stream 319
        #  ahead of 323E010.  It is a battery-limit inflow -- the granulation scrubber is outside the
        #  simulated boundary -- so it is a constant here, exactly like the 323C005 demin make-up
        #  (ui_guidelines.md §4).  It is COLD (40 C) and 55 % water, so it both loads the heater and
        #  feeds the vacuum vapour; without it the stage could not reach the PFD's 80 % product.
        m_331     = R323_M331_DES                                                     # kg/h, PFD stream 331
        tic12_op  = _ctrl_ipd(s.TIC_323012, s.r323_f010_T, dt)                        # steam-P demand (bar a)
        pic08_pv  = clamp(s.PIC_329208["op"] / 100.0 * s.steam.P_LP, 0.0, s.steam.P_LP)
        pic08_op  = _ctrl_ipd(s.PIC_329208, pic08_pv, dt, cas_sp=tic12_op)            # steam valve stroke (%)
        p_chest_e010 = steam_chest_pressure(pic08_op, s.steam.P_LP)
        Q_e010_kw = max(R323_E010_UA_KW * (tsat_steam(p_chest_e010) - s.r323_f010_T), 0.0)  # heater duty (kW, F-10 floored)
        # AUDIT F-3 — same energy limit as Stage 1: the pre-evaporator cannot evaporate more water
        # than its live LP-steam duty (plus the feed's sensible surplus) can supply.
        qevap_avail_kw = (m_319 / 3600.0 * cp_f004 * (s.r323_f004_T - s.r323_f010_T)
                          + m_331 / 3600.0 * cp_331 * (R323_M331_T_C - s.r323_f010_T)
                          + Q_e010_kw)                                                # kW available as latent
        # Flow cap in anchored-ratio form: at design the numerator and denominator are bit-identical, so
        # the ratio is exactly 1.0 and the cap reproduces R323_MEVAP_DES exactly (the min() then ties).
        # AUDIT TD-014 — same degeneracy as Stage 1, same closure, but the lever is different.  323F010
        # runs against a FIXED 0.46 bar a vacuum boundary, so its bubble point cannot move with pressure;
        # what moves it is CONCENTRATION.  That is the correct physics for a vacuum evaporator and it is
        # what TIC-323012 actually controls on the plant: more steam -> more water off -> higher urea
        # fraction -> lower water mole fraction -> higher boiling point -> higher T.  Raoult supplies
        # that slope with no fitted constant (see bubble_T_raoult); the departure form keeps the design
        # point exact.  Design: w == W_S317 -> the bracket is a literal 0.0 -> T_bub == 99.0 == T ->
        # q_relax == 0.0 -> the ratio is exactly 1.0 -> m_evap == R323_MEVAP_DES (the min() ties).
        T_bub_f010 = (R323_F010_T_SP_C
                      + (bubble_T_raoult(R323_F010_P_BARA, s.w_f010) - R323_F010_TBUB_DES))
        qevap_relax_kw = (s.r323_f010_M * cp_f010 * (T_bub_f010 - s.r323_f010_T)
                          / R323_F010_M_TAU_S)                                        # kW retained to reach bubble point
        m_evap    = min(R323_MEVAP_DES * ((m_319 + m_331) / (R323_M319_DES + R323_M331_DES)),
                        max(R323_MEVAP_DES * ((qevap_avail_kw - qevap_relax_kw) / R323_QEVAP_DES_KW),
                            0.0))                                                     # vapour 790 -> vac (kg/h)
        m_317     = gravity_outflow_323f010(s.r323_f010_M)                              # gravity drain -> tank (kg/h)
        P_f010    = (m_319 / 3600.0 * cp_f004 * (s.r323_f004_T - s.r323_f010_T)
                     + m_331 / 3600.0 * cp_331 * (R323_M331_T_C - s.r323_f010_T)
                     + Q_e010_kw - m_evap / 3600.0 * R323_EVAP_LAMBDA)               # net kW on holdup
        M_f010_pre = s.r323_f010_M
        s.r323_f010_T = s.r323_f010_T + P_f010 * dt / max(M_f010_pre * cp_f010, 1e-6)
        s.r323_f010_M = max(M_f010_pre + (m_319 + m_331 - m_evap - m_317) / 3600.0 * dt, 1.0)
        # Mapping — live 323F010 vacuum (PT-323204).  The evolved vapour m_evap is pulled out through
        # HV-323605 (gas outlet, HIC-323605) and evacuated by the 324F002 ejector on HV-329605; opening
        # either raises the pull and drops the pressure.  pull ∝ P/P_des is the ejector suction-pressure
        # capacity roll-off, which makes it a stable first-order node with no controller.  Anchored: at
        # design HIC-323605 == HIC-329605 == 50 %, P == P_des and m_evap == R323_MEVAP_DES, so
        # pull == R323_MEVAP_DES and dP/dt is a literal 0.0.  (The bubble point above stays on the DESIGN
        # vacuum -- TD-016 consistency; feeding live P into the concentration would reopen the P<->m_evap
        # oscillation this repo just closed on unit 324.)
        pull_f010  = (R323_MEVAP_DES * (s.r323_f010_P / R323_F010_P_BARA)
                      * (s.HIC_323605 / R323_HIC605_DES_PCT)
                      * (s.HIC_329605 / R324_HIC9605_DES_PCT))
        s.r323_f010_P = clamp(s.r323_f010_P + R323_F010_P_KP*(m_evap - pull_f010)/3600.0*dt, 0.05, 1.0)
        y_evap     = sol_vapour_y(s.w_f010, SOL_F010["alpha"])          # AUDIT F-8: vacuum vapour comp
        xi_f010    = sol_biuret_xi("F010", M_f010_pre, s.w_f010, s.r323_f010_T)
        s.w_f010   = sol_advance(s.w_f010, M_f010_pre, s.r323_f010_M, m_319, s.w_f004,
                                 m_evap, y_evap, m_317, xi_f010, dt, m_in2=m_331, w_in2=W_S331)
    
        # ---- Stage 4: Urea Solution Tank 323D002  (atmospheric, two compartments) -----------------
        #  TOPOLOGY (References/323D002.md §3, confirmed by operations 2026-07-23):
        #    Comp I  --  80 m3, ACTIVE.  Every feed and discharge nozzle lands here: in = m_317 from the
        #                323F010 separator, out = m_324 drawn by 323P003A/B via LIC-323507 -> FIC-324401
        #                -> FV-324401.  LIC-323507 is its level, TI-323008 its bulk temperature.
        #    Comp II -- 300 m3, PASSIVE, LI-323504 (indication and alarms only -- no control action).
        #                It has no nozzle of its own and is DRY in normal operation; liquid reaches it
        #                only by spilling over the 10 mm internal baffle that divides the shell.
        #    TIE-IN  --  a hand-operated spool in the field, not a DCS valve.  CLOSED (default) the two
        #                compartments are hydraulically independent and whatever spilled into Comp II is
        #                stranded there.  OPENED they become connected vessels: the levels equalise and
        #                323P003 draws the pooled inventory, recovering Comp II into the forward flow.
        #                Modelled as the boolean the operator actually has, HV-323D002-TIE, because that
        #                is what it is -- there is no licensor loop number for a field spool.
        #  Opening the tie against an EMPTY Comp II is a real hazard and the model reproduces it: the
        #  head redistributes over 380 m3 instead of 80, so a 10 % Comp-I level collapses to about 2 %
        #  and 323P003 is left near its cavitation limit.  That is the scenario the button exists for.
        flow_span_324 = R323_M324_DES / 1000.0 / (R323_FV401_OP_DES / 100.0)          # t/h at 100% stroke
        tie_open   = bool(s.HV_323D002_TIE)
        d002_recyc = max(s.tlag.get("R324_recyc", 0.0), 0.0)                         # LV-324501B, one-tick tear
        d002_recyc_T = s.tlag.get("R324_recyc_T", R324_E003_T_SP_C)
        d002_recyc_w = s.tlag.get("R324_recyc_comp", s.w_e003)
        M_I_pre    = s.r323_d002_M_I
        M_II_pre   = s.r323_d002_M_II
        # AUDIT C10 — a level gauge measures VOLUME, and volume is mass over a density that moves.  The
        # spans below were mass spans built on a frozen 1300 kg/m3, so a tank of thinner (hotter, weaker)
        # liquor read low on LIC-323507 by exactly the density error while the operator saw the same
        # inventory.  ρ is now live on composition and temperature, anchored on the PFD's own 1151 for
        # streams 315/317 so the design level is bit-exact.  The volumes (80 / 300 m3) are steel and do
        # not move; only what a kilogram occupies does.
        rho_d002   = urea_soln_rho(s.w_d002.get("Urea", R324_W_IN), s.r323_d002_T, R323_D002_RHO)
        v_I_full   = R323_D002_VOL_I_M3  * rho_d002        # kg that fills Comp I at the LIVE density
        v_II_full  = R323_D002_VOL_II_M3 * rho_d002
        v_tie_full = v_I_full + v_II_full
        # Connected vessels share a HEAD, not a mass.  Both compartments are cut from the same shell, so
        # they have the same height and an equal level FRACTION is an equal head; the pooled span is the
        # sum.  With the tie shut LIC-323507 sees Comp I alone, exactly as before.
        lvl_d002_I = clamp(((M_I_pre + M_II_pre) / v_tie_full if tie_open
                            else M_I_pre / v_I_full) * 100.0, 0.0, 100.0)
        lic07_op  = _ctrl_ipd(s.LIC_323507, lvl_d002_I, dt)                           # product-flow demand (t/h)
        #  FT-324401 measured flow is a first-order lag of the delivered valve flow (tau=5 s transmitter
        #  + stroke dynamics).  Lagging the PV is physically real AND numerically essential: the valve is
        #  a pure-gain plant (flow = op/100*span, span=185.5 t/h => process gain 1.855 t/h per %), so an
        #  UNLAGGED velocity-form PV would give a discrete loop pole |z|=Kc*G=2.78>1 (bang-bang divergence).
        #  The lag makes -(pv-pv1) see gradual change, restoring a stable, bumpless (seed-exact) loop.
        prior_flow_324 = s.FIC_324401["op"] / 100.0 * flow_span_324                   # delivered flow last tick (t/h)
        fic01_pv  = _lag1(s.tlag, "R323_FIC324", prior_flow_324, 5.0, dt)             # measured flow (t/h, lagged)
        fic01_op  = _ctrl_ipd(s.FIC_324401, fic01_pv, dt, cas_sp=lic07_op)            # FV-324401 stroke (%)
        m_324     = max(fic01_op / 100.0 * flow_span_324, 0.0) * 1000.0               # product -> Unit 324 (kg/h)
        d002_overflow = 0.0
        if tie_open:
            # One pooled inventory redistributed to a common level fraction.  Comp II now has an outlet
            # (through the spool, into Comp I's suction), which is the whole point of opening it.
            M_tot    = clamp(M_I_pre + M_II_pre + (m_317 + d002_recyc - m_324) / 3600.0 * dt,
                             1.0, v_tie_full)
            frac     = M_tot / v_tie_full
            M_I_new  = frac * v_I_full
            M_II_new = frac * v_II_full
        else:
            M_I_new = M_I_pre + (m_317 + d002_recyc - m_324) / 3600.0 * dt
            if M_I_new > v_I_full:                                                    # weir spill -> Comp II
                d002_overflow = M_I_new - v_I_full
                M_I_new = v_I_full
            M_II_new = clamp(M_II_pre + d002_overflow, 0.0, v_II_full)
        s.r323_d002_M_I  = max(M_I_new, 1.0)
        s.r323_d002_M_II = max(M_II_new, 0.0)
        # TI-323008 -- Comp-I bulk temperature, now a real state instead of an echo of the upstream
        # separator.  One inlet, one outlet, no duty and no reaction:  M·cp·dT/dt = m_317·cp_in·(T_in − T).
        # The alarm this instrument carries is a LOW-temperature alarm, because a cooling tank walks the
        # 80 % liquor toward its crystallisation boundary and blocks the 323P003 suction -- so the tank
        # needs its own thermal inertia to show that at all.  At design T_in == T == 99 C, so the bracket
        # is a literal 0.0 and the seed is bit-exact.  cp is live on both sides (audit C10).
        cp_d002_in  = urea_soln_cp(s.w_f010.get("Urea", R324_W_IN), s.r323_f010_T)
        cp_d002_recyc = urea_soln_cp(d002_recyc_w.get("Urea", R324_W_EV2), d002_recyc_T)
        cp_d002     = urea_soln_cp(s.w_d002.get("Urea", R324_W_IN), s.r323_d002_T)
        M_d002_T    = (M_I_pre + M_II_pre) if tie_open else M_I_pre
        s.r323_d002_T = s.r323_d002_T + (
            m_317 / 3600.0 * cp_d002_in * (s.r323_f010_T - s.r323_d002_T)
            + d002_recyc / 3600.0 * cp_d002_recyc * (d002_recyc_T - s.r323_d002_T)
        ) * dt / max(M_d002_T * cp_d002, 1e-6)
        # AUDIT F-8: the buffer tank is a well-mixed species blender -- no vapour, no reaction (99 C,
        # atmospheric).  This is what gives the 324 feed a real composition instead of a constant.
        #
        # AUDIT B1 (ripple) -- and until now the line below defeated exactly that claim.  The strength
        # was pinned to the CONSTANT R324_W_IN, so sol_pin_strength overwrote the urea/water pair with
        # 0.80 on every tick and every upstream composition disturbance died here.  Measured: a +4 %
        # NH3 step on the live reactor overflow moved 222 of 1162 telemetry leaves, but 0 of the 66
        # belonging to unit 324 -- the evaporators were composition-blind.  (w_e001 / w_e003 below are
        # pinned to w1_live / w2_live, which are live, so this was the only frozen one of the three.)
        #
        # ATTEMPTED FIX, REVERTED 2026-07-23 -- and the reason is a finding in its own right.
        # Replacing the constant authority with "design anchor + live deviation" DID restore the ripple
        # (unit 324 went from 0 to 13 of 66 responding leaves).  But it also walked D002's urea fraction
        # to 76.515 % against the PFD stream-317 anchor of 80.00, failing four design-point tests:
        # test_design_fixed_point_holds, test_design_point_does_not_drift,
        # test_design_compositions_sit_on_their_pfd_anchors, and
        # test_species_layer_does_not_perturb_the_mass_or_energy_balance.
        #
        # RETRACTION.  That was first written up as "the 323 balance misses 80.00 by 3.5 points and the
        # pin has been masking it".  FALSE -- it was the patch's own bug, and the correction matters
        # because it changes what a future fix is allowed to look like:
        #   * w_f010 (323F010's outlet, and this tank's ONLY inlet) measures 80.0014 % urea, i.e. ON the
        #     anchor.  One inlet, one outlet, no reaction, no vapour => the tank MUST converge to it.
        #   * Comp-I holds 67 600 kg against a 92 749 kg/h draw, so it exchanges only
        #     alpha = m*dt/M = 9.5e-5 of its holdup per tick.
        #   * The patch measured its deviation against a reference captured ONCE, then fed the result
        #     back into the state that produced it.  That recursion is
        #         w_n = (A - ref) + w_{n-1}(1 - alpha) + alpha*w_f010
        #     whose fixed point is  w* = (A - ref)/alpha + w_f010.  Any constant inside the loop is
        #     amplified by 1/alpha ~ 10 495; a capture error of 0.0003 percentage points reproduces the
        #     observed 76.5150 % to four decimals (scratchpad/probe_td013_recursion.py).
        #
        # So the amplification -- not a balance error -- is the real constraint, and it ruled out EVERY
        # additive or multiplicative correction applied inside this loop.  Only two forms survived:
        #   (b) a non-recursive assignment from upstream, auth = R324_W_IN + (w_f010 - W_F010_DES):
        #       stable and bit-exact at design, but the tank then tracks its inlet with no lag;
        #   (c) no pin at all: correct dynamics AND a real holdup lag, but w_d002 then follows whatever
        #       w_f010 does, including its slow drift.
        #
        # TD-013 CLOSED 2026-07-23, option (c) -- THE PIN IS GONE.  The objection to (c) was that
        # w_f010 was on an unbounded ramp, so an unpinned tank would wander with it.  That ramp was
        # TD-014 and it is now fixed: w_f010 settles, stationary, 0.037 pp under the PFD-317 anchor,
        # which is simply where the LIVE stripper bottoms put it.  With the inlet steady there is
        # nothing left for the pin to protect against, and every reason to drop it -- it was the last
        # composition-blind node between the reactor and the evaporators (audit B1), and it fabricated
        # +0.600 kg of urea per 1000 kg of holdup per call, a straight C2 violation.
        # The tank now does what a tank does: it tracks its inlet with its own residence-time lag.
        if tie_open:
            # Connected vessels are ONE well-mixed volume, so they carry one composition.  Blend the two
            # inventories first, then advance the pool on the same flows the mass balance just used.
            M_pool_pre = M_I_pre + M_II_pre
            w_pool = ({k: (M_I_pre * s.w_d002.get(k, 0.0) + M_II_pre * s.w_d002_II.get(k, 0.0))
                          / M_pool_pre for k in SOL_SPECIES}
                      if M_pool_pre > 1e-9 else dict(s.w_d002))
            w_pool = sol_advance(w_pool, M_pool_pre, s.r323_d002_M_I + s.r323_d002_M_II,
                                 m_317, s.w_f010, 0.0, w_pool, m_324, 0.0, dt,
                                 m_in2=d002_recyc, w_in2=d002_recyc_w)
            s.w_d002    = w_pool
            s.w_d002_II = dict(w_pool)
        else:
            # Comp I loses mass through BOTH outlets: the pump draw and, when it is spilling, the weir.
            # The weir stream leaves at the bulk composition, so it cannot move w by itself -- passing it
            # here is a C2 bookkeeping statement, not a correction.
            w_I_new = sol_advance(s.w_d002, M_I_pre, s.r323_d002_M_I, m_317, s.w_f010,
                                  0.0, s.w_d002, m_324 + d002_overflow * 3600.0 / max(dt, 1e-9),
                                  0.0, dt, m_in2=d002_recyc, w_in2=d002_recyc_w)
            if d002_overflow > 0.0 and s.r323_d002_M_II > 1e-9:      # the spill carries Comp-I liquor
                s.w_d002_II = {k: (M_II_pre * s.w_d002_II.get(k, 0.0)
                                   + d002_overflow * s.w_d002.get(k, 0.0)) / s.r323_d002_M_II
                               for k in SOL_SPECIES}
            s.w_d002 = w_I_new
    
        # ======================================================================
        #  UNITS 323-2 / 328-1 / 328-2  — LP RECIRCULATION & DESORPTION
        #  Feed-forward 9-stage state-space model (dependency order).  Every
        #  holdup ODE  dM/dt = Σṁ_in − ṁ_vap − ṁ_out = 0 and every thermal ODE
        #  M·cp·dT/dt = Σṁ_in·cp·(T_in−T) + Q − ṁ_vap·λ = 0 at the design seed
        #  (λ / UA back-solved in the constants block above).  Seven recycle
        #  tears are read one-tick-delayed via s.tlag.get(key, design) and
        #  rewritten at the end -> stable, bit-exact at design.  Live upstream
        #  feeds: m_305 (323C003 top vapour), m_701 (323F004 flash vapour),
        #  hv604 (HV-322604 off-gas -> 322C001).
        # ======================================================================
        # AUDIT C10, aqueous half -- the desorption and LP-absorber trains ran on ONE frozen cp each
        # (R328_CP = A328_CP = 4.0 kJ/kg.K) across 40-200 C.  These streams are >= 98 % water, so their
        # cp is water's, and water's cp is not flat: 4.18 at 40 C, 4.29 at 140, 4.49 at 200 -- the
        # constant is 4 % low at the cold end and 11 % low in the hydrolyser.  Each vessel now carries
        # aqueous_cp() anchored on ITS OWN design temperature, so every value equals the frozen constant
        # bit-exactly at the design seed (every back-solved lambda/UA and the boot-pinned
        # A328_LAMBDA_ABS are therefore untouched) and tracks IAPWS off design.
        cp_328c002 = aqueous_cp(R328_CP, R328_C002_T_BOT, s.a328_c002_T)
        cp_328c003 = aqueous_cp(R328_CP, R328_C003_T,     s.a328_c003_T)
        cp_328c004 = aqueous_cp(R328_CP, R328_C004_T,     s.a328_c004_T)
        cp_328d001 = aqueous_cp(R328_CP, R328_D001_T,     s.a328_d001_T)
        cp_328d3i  = aqueous_cp(A328_CP, A328_D003_TI,    s.a328_d003_TI)
        cp_328d3ii = aqueous_cp(A328_CP, A328_D003_TII,   s.a328_d003_TII)
        cp_322c001 = aqueous_cp(A328_CP, A328_C001_T,     s.a328_c001_T)
        m702_prev  = s.tlag.get("R3232_702", A323_C005_M702_DES)
        m756_prev  = s.tlag.get("R322_756", A323_C005_M756_DES)
        m708_prev  = s.tlag.get("R324_708", A323_C005_M708_DES)
        m748_prev  = s.tlag.get("R328_748",   R328_C002_M748_DES)
        m750_prev  = s.tlag.get("R328_750",   R328_C002_M750_DES)
        m775_prev  = s.tlag.get("R328_775",   R328_C002_M775_DES)
        m718A_prev = s.tlag.get("R3232_718A", R3232_M718A_DES)
        m744_prev  = s.tlag.get("R3232_744",  R3232_E003_M744_DES)
        m718B_prev = s.tlag.get("R3232_718B", R3232_M718B_DES)
        m931_prev  = s.tlag.get("R328_M931",  R328_C004_M931_DES)
    
        self.diagnostics = {
            "m_718": m_718, "m_702": m_702, "m_706": m_706, "m_705": m_705,
            "m_715": m_715, "m_790": m_790
        }
