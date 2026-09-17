def step_sim(dt: float) -> dict:
    s = state
    s.sim_t += dt                        # plant clock advances with the physics, not the wall clock
    suct_open  = bool(s.XV_321901) and (s.tank_level_frac > 0.05)
    disch_open = bool(s.XV_322901)

    # ----- CO2 feed line (320K002 -> XV-322902 -> 322E001), vent via PV-322203 -----
    #   PV-322203 effective opening = max(HIC-322203 min, PIC-322203 op).  PIC-322203
    #   (reverse-acting) opens the vent when CO2 line P rises above SP.  Venting bleeds
    #   CO2 to safe location so the feed to 322E001 drops -> N/C ratio + Load follow.
    pic = s.PIC_322203
    pic["pv_bad"] = not _pv_ok(pic["pv"], pic["sp"])        # L3-9 freeze-last-good on bad PV/SP
    if pic["mode"] == "AUTO" and not pic["pv_bad"]:
        # F2: velocity I-PD, DIRECT-acting (sigma=-1): rising line-P -> open vent.  P acts on PV
        # (no SP derivative kick), I acts on error.  Kc/Ti = 0.5 reproduces the old integral-only
        # gain; the added Kc·ΔPV proportional term damps the static-gain vent loop.  PV==SP & steady
        # -> du=0 (bumpless, design-preserving).
        du = PIC_322203_KC * ((pic["pv"] - pic["pv_prev"])
                              + (dt / PIC_322203_TI) * (pic["pv"] - pic["sp"]))
        pic["op"] = clamp(pic["op"] + du, 0.0, 100.0)
    pic["pv_prev"] = pic["pv"]                              # PV_{k-1} for next-tick velocity term
    pv_open = clamp(max(s.HIC_322203, pic["op"]), 0.0, 100.0)
    feed_factor = 1.0 if s.XV_322902 else 0.0          # isolation shut -> no feed
    # Pressure-driven delivery + split of the raw CO2 (bugs 1 & 4 are ONE defect: the feed
    # never respected the CO2-line vs synthesis dP).  s.p_syn_bara is the prev-tick synthesis
    # pressure (tear lag).  The CO2 line pressure (PIC-322203 PV) is modelled physically:
    #   * 320K002 is flow(load)-controlled, so it FLOATS its discharge to hold the design feed
    #     dP against synthesis backpressure -- there is ALWAYS a dP between the line and the
    #     loop (bug 1) -- up to the compressor's deliverable ceiling P_line_ceil (= the max
    #     synthesis pressure SYN_P_MAX it must still feed, plus the design feed dP; derived
    #     from existing constants, no fabricated head).  Within the normal band dP_HP holds at
    #     ~design so phi_HP=1 and feed stays at load (correct: feed is NOT pressure-throttled
    #     by small excursions).  Only when P_syn nears/exceeds the ceiling does dP_HP shrink ->
    #     phi_HP tapers -> check valve shuts (feed 0).
    #   * Opening PV-322203 sags the line by CO2_PV_DP_GAIN per % -- toward/below P_syn -- and
    #     raises g_vent, so f_to_HP -> 0: almost all CO2 leaves via the vent, not the HP loop
    #     even though it kept flowing before (bug 4).
    DP_HP_DES   = CO2_P_DES_BARA - SYN_P_DES_BARA            # 3.5 bar design feed dP
    P_line_ceil = SYN_P_MAX_BARA + DP_HP_DES                 # compressor deliverable ceiling (feed dP held at max-P synthesis)
    P_line_float = min(s.p_syn_bara + DP_HP_DES, P_line_ceil)  # discharge floats to hold the feed dP, capped at shutoff
    P_line_bara = P_line_float - CO2_PV_DP_GAIN * pv_open    # PV-322203 venting pulls the line down -> PIC-322203 PV (bar a)
    dP_HP   = max(P_line_bara - s.p_syn_bara, 0.0)           # drives CO2 INTO HP loop (>=0: check valve)
    dP_vent = max(P_line_bara - CO2_VENT_P_BARA, 0.0)        # drives CO2 OUT the vent
    phi_HP  = min(1.0, (dP_HP / DP_HP_DES) ** 0.5)          # bug 1: delivery taper (1.0 across band, shuts near ceiling)
    g_HP    = dP_HP ** 0.5
    g_vent  = (pv_open / 100.0) * CO2_VENT_COND * dP_vent ** 0.5
    f_to_HP = g_HP / (g_HP + g_vent) if (g_HP + g_vent) > 1e-12 else 0.0   # bug 4: vent-diversion split
    frac_HP = phi_HP * f_to_HP                               # net fraction of raw reaching the HP loop
    F_CO2_feed_kgh = s.F_CO2_raw_th * 1000.0 * feed_factor * frac_HP
    F_CO2_vent_kgh = s.F_CO2_raw_th * 1000.0 * feed_factor * (1.0 - frac_HP)  # all CO2 not delivered to HP -> vent/relief
    s.F_CO2_th = F_CO2_feed_kgh / 1000.0               # t/h actual feed -> drives ratio block
    s.F_CO2_vent_th = F_CO2_vent_kgh / 1000.0          # t/h vented via PV-322203
    CO2_feed_kmolh = F_CO2_feed_kgh / CO2_FEED_MW      # kmol/h
    FT_322403 = CO2_feed_kmolh * NM3_PER_KMOL          # Nm3/h  (FT-322403)
    FY_322403 = s.F_CO2_th                             # t/h    (FY-322403)
    # Empirical BL->loop transport dead time (FEED_TD_S): the CO2 the synthesis loop
    # (stripper strip-gas + reactor) receives NOW left the battery-limit meter 345 s ago.
    # FY/FT-322403, load % and the DCS ratio cascade/PV all read the LIVE BL meter above.
    F_CO2_syn_th = _delay(s.tlag, "FEED_CO2", s.F_CO2_th, FEED_TD_S, dt)
    Load_pct  = s.F_CO2_th / (CO2_DES_KGH / 1000.0) * 100.0   # % of design CO2 flow
    pic["pv"] = P_line_bara

    # Cascade opening setpoint (%) from ratio flow demand.
    #   ratio_SP is molar N/C -> NH3 mass demand = (N/C)*(M_NH3/M_CO2)*m_CO2.
    F_NH3_sp_th    = s.ratio_SP * NC_TO_MASS * s.F_CO2_th
    Q_total_sp_m3h = F_NH3_sp_th * 1000.0 / NH3_RHO
    n_active       = (1 if s.pumpA["on"] else 0) + (1 if s.pumpB["on"] else 0)
    Q_per_pump     = Q_total_sp_m3h / max(n_active, 1)
    rpm_req        = Q_per_pump / (PUMP_V_PER_REV * PUMP_ETA_V * 60.0)
    open_cas       = clamp(rpm_req / PUMP_RATED_RPM * 100.0, 0.0, 100.0)

    # Drive each pump's converter opening toward controller output
    for p, ctrl in [(s.pumpA, s.SIC_321950), (s.pumpB, s.SIC_321951)]:
        ctrl.step(p["open_act"], dt, cas_sp=open_cas)      # updates op + pv
        if (not p["on"]) or (not suct_open) or (not disch_open):
            target = 0.0
        else:
            target = ctrl.mv
        alpha = min(1.0, dt / 2.0)                         # tau ~ 2 s
        p["open_act"] += (target - p["open_act"]) * alpha
        p["open_act"]  = clamp(p["open_act"], 0.0, 100.0)
        p["speed_act"] = p["open_act"] / 100.0 * PUMP_RATED_RPM
        p["current"]   = pump_current_A(p["speed_act"], p["on"])
        p["mode"]      = mode_tag(ctrl)

    # Pump flows
    Q_A_m3h = pump_flow_m3h(s.pumpA["speed_act"]) if s.pumpA["on"] else 0.0
    Q_B_m3h = pump_flow_m3h(s.pumpB["speed_act"]) if s.pumpB["on"] else 0.0
    F_A_th  = Q_A_m3h * NH3_RHO / 1000.0                       # t/h NH3 pump A
    F_B_th  = Q_B_m3h * NH3_RHO / 1000.0                       # t/h NH3 pump B
    F_pump_total_th = F_A_th + F_B_th                          # t/h

    # LIC-321501 feed-drum makeup: BL import = live pump draw (feed-forward) + P level-restore term,
    #   clamped to the import-line capacity.  import == draw at SS -> level held at SP, no spurious trip.
    s.F_in_BL_th = clamp(F_pump_total_th + TANK_LIC_KP_TH * (TANK_LEVEL_SP_FRAC - s.tank_level_frac),
                         0.0, TANK_BL_MAX_TH)
    # Tank mass balance:  dM/dt = F_BL_in - F_pump_out   (BL makeup fills tank)
    dm_kg = (s.F_in_BL_th - F_pump_total_th) * 1000.0 / 3600.0 * dt
    V_new = clamp(s.tank_level_frac * TANK_VOL + dm_kg / NH3_RHO, 0.0, TANK_VOL)
    s.tank_level_frac = V_new / TANK_VOL
    s.totalizer_t += F_pump_total_th * dt / 3600.0          # FQI-321401: delivered NH3

    # 321D003 NH3 feed-drum energy balance -> TT-321001/TT-321002.
    #   M*cp*dT/dt = F_BL_in*cp*(T_BL - T_tank)   (adiabatic drum, Q_env ~ 0)
    # Subcooled liquid NH3 relaxes to the BL supply temp; sub-cooling held by PDY.
    M_tank_kg = s.tank_level_frac * TANK_VOL * NH3_RHO
    F_in_kgs  = s.F_in_BL_th * 1000.0 / 3600.0
    if M_tank_kg > 1.0:
        s.tank_T_C += (F_in_kgs * (T_BL_FEED_C - s.tank_T_C) / M_tank_kg) * dt

    # PT-321201/202 = NH3 feed (suction) pressure = upstream NH3 feed-stream
    #   pressure at tank 321D003 (= tank top operating pressure, bar g). Matches
    #   the AL feed-stream reading. Real suction head kept for physics + trips.
    P_suct_barG = (s.tank_P_top_barG
                   + (NH3_RHO * G * s.tank_level_frac * TANK_H) / 1e5
                   - 0.15)
    if not suct_open:
        P_suct_barG = 0.0
    PT_A = PT_B = s.tank_P_top_barG                          # bar g (feed-stream P)

    # PY-321201/202 = NH3 saturated vapour pressure at TT-321002 (bar a)
    PY = psat_nh3_bara(s.tank_T_C)
    # PDY-321203/204 = sub-cooling margin (bar) = P_feed(abs) - P_sat(abs); >0 => liquid
    PDY_A = (PT_A + P_ATM_BAR) - PY
    PDY_B = (PT_B + P_ATM_BAR) - PY

    # TI-321020 = common discharge temperature = T_suct + pump enthalpy rise
    #   dT = dP/(rho*cp) * ( beta*T + (1-eta_h)/eta_h )
    if (s.pumpA["on"] or s.pumpB["on"]) and disch_open:
        dP_pa   = max(0.0, P_SYN_DOWN_BAR - (P_suct_barG + P_ATM_BAR)) * 1e5
        T_K     = s.tank_T_C + 273.15
        dT_pump = dP_pa / (NH3_RHO * CP_NH3) * (BETA_NH3 * T_K + (1.0 - ETA_PUMP_HYD) / ETA_PUMP_HYD)
    else:
        dT_pump = 0.0
    TI_321020 = s.tank_T_C + dT_pump

    # 322F001 HP ejector: live motive NH3 (gated by XV-322901) + entrained carbamate
    #   -> discharge stream to 322E002 (TT-322012). Motive temp = TI-321020.
    motive_nh3_kgh = (F_pump_total_th * 1000.0) if disch_open else 0.0
    # Empirical BL->loop transport dead time (FEED_TD_S): NH3 leaving the pump discharge
    # header transits the BL->ejector line before the loop sees it.  Pure re-timing (ring
    # buffer) — the tank/pump balance above debits the LIVE flow; the difference is line
    # pack in transit.  FY-321401 / ratio-PV read the live pump-discharge transmitters.
    motive_nh3_kgh = _delay(s.tlag, "FEED_NH3", motive_nh3_kgh, FEED_TD_S, dt)
    # Option 3 coupling: ACTUAL entrainment = ejector capacity * gravity suction head (scrub level).
    #   scrub_lvl_frac = prior-step 322E003 level / NLL (loop tear: ejector runs BEFORE the scrubber
    #   block, so it sees last-tick level).  frac=1 at NLL -> design entrainment; frac self-regulates
    #   the sump to L_eq=NLL*(overflow/capacity) -> stable at NLL on turndown, floods on a true stall.
    scrub_lvl_frac = s.scrub_level_pct / SCRUB_LEVEL_NLL_PCT
    ej = ejector_322f001(motive_nh3_kgh, TI_321020, s.HIC_322602, scrub_level_frac=scrub_lvl_frac)
    # motive fraction (PD pump -> flow ~ speed) and ejector developed-head forward-flow fraction.
    # phi_fwd ~ phi_m^2 (affinity head curve): drives the HPCC->reactor liquid circulation and the
    # discharge-header pressure.  ==1 at design motive -> all hydraulic states hold design.
    phi_m   = clamp(motive_nh3_kgh / EJ_MOTIVE_NH3_DES, 0.0, 1.5)
    phi_fwd = phi_m * phi_m

    # Ratio block PV = molar N/C per feed-ratio eq:  N/C = (m_NH3/m_CO2)*2.584.
    # L3-3 measurement-validity gate: below 5% of design CO2 feed the divisor collapses and the molar
    #   N/C is numerically meaningless -> hold the last-good ratio and raise RATIO_PV_BAD to freeze the
    #   cascade (no garbage SP propagation on black-start / CO2-feed loss).
    NC_A = NC_B = 0.5 * s.ratio_PV            # telemetry default = held last-good split (gated branch)
    if s.F_CO2_th < 0.05 * (CO2_DES_KGH / 1000.0):
        s.flags["RATIO_PV_BAD"] = True        # s.ratio_PV / s.ratio_bal hold last-good (not recomputed)
    else:
        s.flags["RATIO_PV_BAD"] = False
        m_CO2 = max(s.F_CO2_th, 1e-6)
        NC_A  = (F_A_th / m_CO2) * NC_FACTOR      # N/C contributed by pump A
        NC_B  = (F_B_th / m_CO2) * NC_FACTOR      # N/C contributed by pump B
        s.ratio_PV  = NC_A + NC_B                 # total system N/C = (m_NH3_tot/m_CO2)*2.584
        s.ratio_bal = s.ratio_PV

    # ----- HP Stripper 322E001: reactor effluent + live CO2 strip gas -> top gas (322E002)
    #   + bottom solution (LV-322501).  Shell = condensing 329D005 MP steam (boundary T).
    # Stripper consumes the previous step's reactor overflow (tear stream of the synthesis
    # recycle); at design this equals the frozen STRIP_FEED207_KMOLH -> output unchanged.
    T_steam_live = tsat_steam(s.steam.P_MP)           # live sat-steam shell T from MP header pressure
    # DEAD-LEVER FIX (audit): P_bara was hardwired to the frozen STRIP_P_DES_BARA at every call
    # site, so eta_P evaluated to exactly 1.0 forever and synthesis pressure had NO effect on
    # stripping efficiency.  That is wrong in a way an operator would notice immediately -- raising
    # loop pressure suppresses carbamate dissociation (3 mol of gas from 1 of liquid, so Le
    # Chatelier pushes the equilibrium back) and the stripper visibly loses efficiency.
    # PT-329201 (s.p_syn_bara) is the live loop pressure; the stripper tube side sits a fixed
    # 3.3 bar above it (144.0 vs 140.7), so the live tube-side pressure is carried as a RATIO
    # anchored on each side's own design value.  At design s.p_syn_bara == SYN_P_DES_BARA exactly,
    # so the ratio is exactly 1.0 and X * 1.0 == X -- eta_P is bit-identical to the old constant.
    #
    # Gated on _STEAM_READY for the same reason step_steam is (see the steam handshake below).
    # This fix adds a feedback path that did not exist before -- loop pressure now reaches the
    # stripper split -- and the boot-pin settle would otherwise traverse a different transient and
    # capture HPCC_UA / HPCC_LIQ_DES_LIVE on a different basis (measured: +305 kg/h, 0.16 %).  Those
    # are CALIBRATION constants; they must not depend on which transient reached the design point.
    # At the settled design state s.p_syn_bara == SYN_P_DES_BARA, so gate open and gate closed give
    # the identical answer there -- the gate changes the path, never the fixed point.
    
    # Live reactor-overflow temperature feeds the stripper's sensible-heat term (TD-006), carried
    # as an offset from the reactor's own design anchor so it is exactly STRIP_FEED207_T_C at design.
    T_feed_live  = STRIP_FEED207_T_C + (s.react_T_overflow - reactor.T0_DES_C)
    
    # Dynamic Darcy-Weisbach pressure drop: dP scales with m^2 / rho
    dP_des_strip = STRIP_P_DES_BARA - SYN_P_DES_BARA
    m_strip_live = max(sum(s.react_overflow_kmolh.get(k, 0.0) * MW_COMP[k] for k in MW_COMP), 1e-6)
    m_strip_des  = max(sum(STRIP_FEED207_KMOLH.get(k, 0.0) * MW_COMP[k] for k in MW_COMP), 1e-6)
    w_urea_strip = (s.react_overflow_kmolh.get("Urea", 0.0) * MW_COMP["Urea"]) / m_strip_live
    rho_live_strip = urea_soln_rho(w_urea_strip, T_feed_live, REACT_OVERFLOW_RHO)
    dP_strip_live = dP_des_strip * (REACT_OVERFLOW_RHO / max(rho_live_strip, 1e-6)) * (m_strip_live / m_strip_des)**2
    
    P_strip_live = (s.p_syn_bara + dP_strip_live if _STEAM_READY else STRIP_P_DES_BARA)
    strip = stripper_322e001(F_CO2_syn_th, T_steam_live, P_strip_live,
                             overflow_kmolh=s.react_overflow_kmolh,
                             L_feed=s.react_L_feed, W_feed=s.react_W_feed,
                             T_feed_C=T_feed_live)

    # LIC-322501 bottom-solution level control, DIRECT-acting on the FC LV-322501:
    #   level^ -> op^ -> air-to-open valve opens -> drain^ -> level v  (neg. feedback).
    lic = s.LIC_322501
    lic["pv_bad"] = not _pv_ok(s.strip_level, lic["sp"])    # L3-9 freeze-last-good on bad PV/SP
    if lic["pv_bad"]:
        e_lvl = lic["e_prev"]                  # hold last-good error; op frozen (update skipped)
    else:
        e_lvl = s.strip_level - lic["sp"]      # direct-acting error (level above SP -> open)
        if lic["mode"] == "AUTO":              # velocity-form PI (proportional-dominant)
            lic["op"] = clamp(lic["op"]
                              + LIC_322501_KC * ((e_lvl - lic["e_prev"]) + (dt / LIC_322501_TI) * e_lvl),
                              0.0, 100.0)
    lic["e_prev"] = e_lvl                       # track for bumpless MAN->AUTO
    lv_open = clamp(lic["op"], 0.0, 100.0)
    # L3-1 LV-322501 letdown driven by the LIVE synthesis pressure (PT-329201 = s.p_syn_bara), not a
    #   frozen design ΔP.  As the loop depressurizes (black-start / blowdown) the drain head collapses
    #   -> drain -> 0, no spurious letdown from an empty vessel.  Uses prior-step p_syn (same loop-break
    #   convention as nu / dP_vent).  P_down = 4.0 bar a (LP loop downstream of LV-322501).
    #       m_drain = m_drain_des * (Op_LV/Op_LV_des) * sqrt(max(P_syn - P_down,0)/(P_syn_des - P_down))
    dP_lv = max(s.p_syn_bara - LV322501_P_DOWN_BARA, 0.0)
    drain_kgh = STRIP_BOT_DES_KGH * (lv_open / LV322501_OPEN_DES) \
                * (dP_lv / max(SYN_P_DES_BARA - LV322501_P_DOWN_BARA, 1e-6)) ** 0.5
    # L3-6 stripper-bottoms mushy-zone: urea-melt crystallization (T_cryst=132.7 C) throttles the
    #   LV-322501 drain as T_bot falls; the un-drained mass stays in the LT-322501 ODE -> level rises.
    f_drain = _f_flow(strip["T_bot"], 132.7)
    drain_kgh *= f_drain
    s.flags["STRIPPER_SOLIDIFICATION"] = (f_drain < 1.0)
    # --- cold-start HP-loop fill-rate scaling (SS-NEUTRAL).  Field PT-329201 pressurises over ~58 min
    #   (06-03 Section 1.2 FOPTD, tau=3469.5 s); the model's native mass-balance fills the three HP
    #   holdups in ~10 min, so the emergent tau under-shoots the Section 6.4 band.  Per the report's
    #   Section 6.1 mandate (tau must EMERGE from the physical inventory, never a fudge lag on the
    #   pressure state) we slow the loop-fill itself: scale each HP holdup's NET accumulation by
    #   k_loop_fill, tied to the aggregate loop-mass fraction so it -> 1.0 as the loop fills.  At/near
    #   design m_loop_frac == 1 -> k_loop_fill == 1 (fill untouched) AND every net rate == 0 (in==out),
    #   so the steady-state hold and the warm-start audits stay bit-exact regardless of the scaling.
    _mf_prev    = clamp((s.react_level_pct + s.hpcc_level_pct + s.strip_level)
                        / (REACT_LEVEL_NLL_PCT + HPCC_LEVEL_NLL_PCT + STRIP_LEVEL_SP_DES), 0.0, 1.0)
    #   _fc / _fe calibrated so the emergent cold-start pressurisation tau (model-free Smith 63.2%
    #   two-point ID in tests/coldstart_probe.py) lands inside the DCS-anchored FOPTD band
    #   tau in [2884, 4055] s (center 3469.5 s == SYN_P_TAU_FILL_MIN 57.8 min; dcs_anchor_dynamics
    #   Section 1.2).  _fe == 8 holds k_loop_fill ~= _fc (near-uniform slow fill) across most of the
    #   empty-loop transient; both revert to 1.0 as m_loop_frac -> 1 (design SS bit-exact, SS-neutral).
    _fc         = 0.06     # empty-loop net-rate scale (Smith-calibrated to Section 6.4 band)
    _fe         = 8.0      # gate exponent (Smith-calibrated to Section 6.4 band)
    k_loop_fill = _fc + (1.0 - _fc) * _mf_prev ** _fe
    
    if s.strip_bot_kgh_lag is None:
        s.strip_bot_kgh_lag = strip["bot_kgh"]
    else:
        tau_fall = 30.0  # seconds of transit delay
        s.strip_bot_kgh_lag += (strip["bot_kgh"] - s.strip_bot_kgh_lag) * (dt / tau_fall)
        
    # bottom-sump mass balance -> LT-322501 level (%)
    m_span_kg = STRIP_SUMP_AREA_M2 * STRIP_LEVEL_SPAN_M * STRIP_RHO_BOTTOM
    s.strip_level = clamp(s.strip_level
                          + k_loop_fill * (s.strip_bot_kgh_lag - drain_kgh) / 3600.0 * dt / m_span_kg * 100.0,
                          0.0, 100.0)
    lic["pv"] = s.strip_level
    # L3-7 bottoms-sump ENERGY BALANCE -> TT-322004 (stream 322E001 falling-film exit -> LV-322501):
    #   The bottom sump is a stirred buffer below the steam-heated falling-film tubes.  Steady-state sump
    #   energy balance (film enthalpy in = drain enthalpy out + heat loss to surroundings):
    #       ṁ·cp·T_film = ṁ·cp·T_out + UA·(T_out − T_amb)
    #   The rigorous stripper model's strip["T_bot"] already equals the DESIGN-drain sump outlet (design HMB
    #   anchor), so the film feeding the sump is  T_film = T_bot·(1+τ) − τ·T_amb  with the design sump-loss
    #   NTU  τ = UA/(ṁ_des·cp) = STRIP_SUMP_NTU_DES.  Eliminating T_film and writing r = ṁ_drain/ṁ_des
    #   (live drain / design drain) gives the closed-form sump outlet temperature:
    #       T_out = [ r·(1+τ)·T_bot + τ·(1−r)·T_amb ] / (r + τ)
    #   r=1 -> T_out = T_bot  (bit-exact design HMB);  r↑ (LV-322501 opened -> more bottoms flow, less sump
    #   residence) -> T_out -> (1+τ)·T_bot = T_film  (hotter, ≤ steam sat);  r↓ (throttled, long residence)
    #   -> T_out -> T_amb  (crystallization-pinned floor).  dT_out/dr = τ(1+τ)(T_bot−T_amb)/(r+τ)² > 0 since
    #   T_bot > T_amb, so opening LV-322501 raises the bottoms flow which raises TT-322004 (item 3) — now
    #   driven by the ACTUAL drain mass flow through the sump heat balance, not an empirical opening curve.
    #   drain_kgh keys off strip["T_bot"] (f_drain) only, never T_out -> no algebraic loop.
    T_amb_sump = STRIP_BOT_T_CRYST_C
    if strip["T_bot"] > T_amb_sump:
        r_drain    = drain_kgh / STRIP_BOT_DES_KGH
        tau_sump   = STRIP_SUMP_NTU_DES
        T_bot_disp = (r_drain * (1.0 + tau_sump) * strip["T_bot"] + tau_sump * (1.0 - r_drain) * T_amb_sump) \
                     / (r_drain + tau_sump)
        T_bot_disp = min(T_bot_disp, strip["T_steam"])   # bottoms can never out-heat the condensing shell
    else:
        T_bot_disp = strip["T_bot"]                      # cold start / solidified: no hot-film sump residence effect
    TT_323001 = STRIP_T_DOWN_DES_C + 0.7 * (T_bot_disp - STRIP_T_BOTTOM_DES_C)   # post-flash ripples the same bottoms T

    # HP carbamate condenser 322E002: strip gas + ejector liquid -> two-phase product to 322R001.
    #   Shell-side LP-steam saturation T tracks the live LP header, but as an OFFSET about the
    #   pinned design constant (HPCC_STEAM_TSAT_C=146.3 differs from Antoine tsat(4.4)~147.4); at
    #   design P_LP==HPCC_STEAM_P_BARA so the offset is 0 -> T_shell_lp==146.3 bit-exact.
    # Internal header pressure is itself a thermodynamic disturbance.  The former exogenous-only
    # gate suppressed it, allowing the 4-bar header and HPCC shell to occupy incompatible states.
    # Keep the measured design offset (Antoine vs licensor steam-table basis), but always propagate
    # the live pressure departure.  At 4.4 bar a the bracket is exactly zero: design stays pinned.
    g_dist = 1.0
    P_LP_hpcc = s.steam.P_LP
    T_shell_lp = tsat_steam(P_LP_hpcc)
    #   AUDIT F-6/TD-007: the (T,P) phase split needs the product temperature it also produces and the
    #   live synthesis pressure -> both entered as prior-step tears (s.tlag / s.p_syn_bara), the same
    #   Sequential-Modular tearing every other recycle in this flowsheet uses.
    hpcc = hpcc_322e002(strip, ej, t_shell=T_shell_lp, gate=g_dist,
                        t_prod_prev=s.tlag.get("HPCC_TPROD", HPCC_T_PROD_DES_C),
                        p_loop=s.p_syn_bara, phi_prev=s.hpcc_phi, dt=dt)
    s.tlag["HPCC_TPROD"] = hpcc["T_prod"]        # tear for next tick's phase split
    s.hpcc_phi           = hpcc["phi_film"]      # interfacial-composition state (relaxed, pre-gate)

    # 322R001 HP urea reactor: pinned products from hpcc feed, throughput s, valve φ.
    # f_L loop coupling: the reduced model pins the recycle overflow, so the endogenous feed N/C
    # (hpcc L_hpcc) is dominated by the atom-conserving ripple (conv^ -> NH3 -2d -> feed N/C v):
    # a strong NEGATIVE loop that cannot be amplified.  Drive f_L instead off the EXOGENOUS
    # fresh-feed N/C (s.ratio_PV, set by pump speeds — feedback-free): L_drive maps its deviation
    # onto the reactor-feed N/C, == L0 at design (ratio.PV=RATIO_PV_DES -> conv=1, bit-exact).
    # Drives Inoue-Kanai f_L only; overflow ripple keeps AT-322701 atom-invariant; PT-329201
    # (L_hpcc bubble-point) untouched.
    # Fix-3: genuine blended reactor feed with a first-order recycle lag (replaces the L_override
    # band-aid).  The EXOGENOUS fresh-feed N/C (pump speeds, feedback-free) is the disturbance target
    # L_fresh; the recycle leg L_rec chases it through a τ_rec first-order Euler lag, and the reactor
    # sees the φ_f-weighted blend.  W (reactor-feed H/C) blends the same way off the LIVE HPCC feed.
    # At design L_fresh==L0, W_inst==W0, L_rec/W_rec seeded at design -> blend == design (bit-exact);
    # at settled steady state (t >> τ_rec) the lag fully relaxes (L_rec->L_fresh, W_rec->W_inst) so
    # the blend -> the instantaneous feed and the prior settled conversion is recovered exactly.
    a_rec   = dt / (REACT_TAU_REC_MIN * 60.0)                 # per-tick first-order lag coefficient
    L_fresh = reactor.L0_DES * (1.0 + REACT_NC_LOOP_GAIN * (s.ratio_PV / RATIO_PV_DES - 1.0))
    co2_fd  = hpcc["feed_kmolh"].get("CO2", 0.0)
    W_inst  = (hpcc["feed_kmolh"].get("H2O", 0.0) / co2_fd) if co2_fd > 0.0 else reactor.W0_DES
    s.react_L_rec += a_rec * (L_fresh - s.react_L_rec)        # recycle N/C lags the fresh disturbance
    s.react_W_rec += a_rec * (W_inst  - s.react_W_rec)        # recycle H/C lags the live feed water
    L_blend = REACT_FRESH_FRAC * L_fresh + (1.0 - REACT_FRESH_FRAC) * s.react_L_rec
    W_blend = REACT_FRESH_FRAC * W_inst  + (1.0 - REACT_FRESH_FRAC) * s.react_W_rec
    # f_T bulk temp = design HPCC base + the reactor's OWN prior-step exotherm (NOT the live cascading
    #   lip). This keeps the deliberate conversion self-loop (gain ~0.16, stable) while CUTTING the
    #   conversion->composition->HPCC-N/C cliff return leg that closed an unstable G~-15 thermal recycle
    #   (the source of the TT-322010 161<->213 oscillation). conv_fac=1 -> 170+13=183=T0_DES (bit-exact).
    T_conv_c = HPCC_T_PROD_DES_C + REACT_DT_COL_DES * s.react_conv_fac
    react   = react_322r001(hpcc, F_CO2_syn_th, s.HIC_322605, L_drive=L_blend, W_drive=W_blend,
                            T_overflow_c=T_conv_c)
    
    # Dynamic Darcy-Weisbach pressure drop for Reactor
    dP_des_react = REACT_P_BARA - HPCC_P_DES_BARA
    m_react_live = max(sum(react["feed_kmolh"].get(k, 0.0) * MW_COMP[k] for k in MW_COMP), 1e-6)
    m_react_des  = HPCC_LIQ_DES_LIVE if HPCC_LIQ_DES_LIVE else HPCC_LIQ_DES_KGH
    w_urea_react = (react["feed_kmolh"].get("Urea", 0.0) * MW_COMP["Urea"]) / m_react_live
    rho_live_react = urea_soln_rho(w_urea_react, hpcc["T_prod"], REACT_OVERFLOW_RHO)
    dP_react_live = dP_des_react * (REACT_OVERFLOW_RHO / max(rho_live_react, 1e-6)) * (m_react_live / max(m_react_des, 1e-6))**2
    react["P_bara"] = hpcc["P_bub"] + dP_react_live
    
    # Dynamic Darcy-Weisbach pressure drop for Reactor Off-Gas: dP scales with m^2 / rho.
    # PARITY FIX (check-#2, stream-composition -> D/S pressure): the two sibling liquid lines above
    #   (stripper 5143, reactor 5285) already carry the (rho_des/rho_live) Darcy density factor, but this
    #   GAS line was m^2-only -- a change in off-gas composition (MW) or temperature did NOT move its D/S
    #   pressure drop.  rho of the compressible off-gas is ideal-gas: rho = P*MW/(R*T), so at a common line
    #   pressure  rho_des/rho_live = (MW_des/MW_live)*(T_live/T_des).  Density anchored to the reactor
    #   off-gas DESIGN vector (REACT_OFFGAS_DES) and REACT_OFFGAS_T_C: at the seed react["offgas_kmolh"]
    #   == REACT_OFFGAS_DES and s.react_T_offgas == REACT_OFFGAS_T_C -> rho_fac == 1.0 -> bit-exact pin.
    dP_des_og = REACT_OFFGAS_P_BARA - SYN_P_DES_BARA
    m_og_live = max(sum(react["offgas_kmolh"].get(k, 0.0) * MW_COMP[k] for k in MW_COMP), 1e-6)
    m_og_des  = max(sum(SCRUB_OFFGAS_KMOLH_DES.get(k, 0.0) * MW_COMP[k] for k in MW_COMP), 1e-6)
    _n_og_live = max(sum(react["offgas_kmolh"].get(k, 0.0) for k in MW_COMP), 1e-9)
    _n_og_des  = max(sum(REACT_OFFGAS_DES.get(k, 0.0) for k in MW_COMP), 1e-9)
    _mw_og_live = m_og_live / _n_og_live                                          # live off-gas mean MW
    _mw_og_des  = sum(REACT_OFFGAS_DES.get(k, 0.0) * MW_COMP[k] for k in MW_COMP) / _n_og_des
    _rho_fac_og = (_mw_og_des / max(_mw_og_live, 1e-9)) \
                  * ((s.react_T_offgas + 273.15) / (REACT_OFFGAS_T_C + 273.15))   # = rho_des/rho_live (ideal gas)
    react["P_offgas"] = s.p_syn_bara + dP_des_og * _rho_fac_og * (m_og_live / m_og_des)**2
    
    s.react_L_feed = react["L_feed"]                   # tear -> next step's stripper eta_T penalty
    s.react_W_feed = react["W_feed"]
    # NB: s.react_overflow_kmolh (the stripper-feed tear) is set BELOW in the reactor-inventory block —
    #     it is the HYDRAULIC bottom take-off m_out (HV-322605 × column head), NOT the raw split production.

    # Fix-1: integrate the distributed 4-node axial thermal profile (Damköhler-shaped exotherm).
    #   dT_n/dt = [ (T_{n-1} - T_n) + g_n·ΔT_col ] / τ_n ,  T_0 = T_feed (HPCC two-phase product),
    #   ΔT_col = ΔT_col,des · conversion_factor  (the profile FLEXES with the live per-pass conversion).
    # Explicit Euler; the upstream term uses the PREVIOUS-step node temps (T_old) so the cascade is
    # decoupled within a tick (steady state is identical: T_old[n-1]==T_new[n-1] -> telescopes to
    # T_n = T_feed + ΔT_col·G_raw(ζ_n), the as-built residence-time probe profile when conv_fac->1).
    conv_fac = react["X_conv"] / reactor.X_DES_RAW
    s.react_conv_fac = conv_fac                              # tear -> next step's design-anchored f_T base
    dT_col   = REACT_DT_COL_DES * conv_fac
    T_old     = list(s.react_T_node)
    T_up      = hpcc["T_prod"]                               # node-0 upstream = LIVE HPCC two-phase feed T (cascade)
    flow_frac = max(clamp(react["co2_scale"], 0.0, 1.0), 1.0e-3)  # m_dot/m_dot_des proxy (§7.6 P5-B: floor 1e-3>0 so tau_n=tau_des/flow_frac stays finite as load->0; bit-exact at design, co2_scale>>1e-3); tau-scale + loss gate
    new_T     = []
    for n in range(4):
        # Fix-1/2: flow-scaled residence  tau_n = tau_des/flow_frac  (-> +inf as flow collapses, zero-flow
        #   safe); node_dTdt adds the ANCHOR-GATED ambient wall loss (zero at design, full when stagnant)
        #   so a frozen reactor relaxes dT/dt = -(T_n - T_amb)/tau_loss -> ambient instead of sticking.
        tau_n = (REACT_TAU_NODE_MIN[n] * 60.0 / flow_frac) if flow_frac > 1.0e-9 else float("inf")
        Tn = T_old[n] + reactor.node_dTdt(T_old[n], T_up, REACT_G_NODES[n], dT_col,
                                          tau_n, flow_frac) * dt
        new_T.append(Tn)
        T_up = T_old[n]                                       # next node's upstream = this node (prev step)
    s.react_T_node     = new_T
    s.react_T_overflow = new_T[3] + REACT_G_OV * dT_col       # overflow lip off INERTIAL node-3 (Σ g_n + g_ov = 1 anchor)
    s.react_T_offgas   = new_T[3] + REACT_OFFGAS_GAMMA * (s.react_T_overflow - new_T[3])
    react["T_overflow"] = s.react_T_overflow                 # publish live profile to telemetry + scrubber
    react["T_offgas"]   = s.react_T_offgas

    # ----- Steam balance handshake (reverse pass): forward duties -> header mass draws -> Euler tick.
    #   Q [kJ/h] = duty_kW * 3600 ;  m [kg/s] = Q / lambda[kJ/kg] / 3600  ==  duty_kW / lambda.
    #   Stripper reboiler draws MP steam (fixed design duty); HPCC raises LP steam (live duty).
    # TD-006 (second half) CLOSED.  This used to be duty proportional to feed MASS:
    #     strip_load  = m_feed / STRIP_FEED_DES_KGH ;  Q = STRIP_DUTY_DES_KW * strip_load * 3600
    # which was the minimum-viable fix for an earlier defect (the duty had been hardcoded, so
    # 76.7 t/h of MP steam was drawn even at zero feed).  It removed that bug but left a real one:
    # composition did not enter, so the same tonnage of pure water and of carbamate-rich reactor
    # liquor demanded identical steam, and the dominant heat sink in the unit -- carbamate
    # dissociation -- was invisible to the MP header.
    # Now the ratio comes from the per-species enthalpy balance computed inside the unit (q_carb +
    # q_nh3 + q_h2o + q_hyd + q_sens).  STRIP_DUTY_DES_KW remains the licensor anchor; only the
    # SHAPE of the off-design response comes from the balance, so the balance's 4 % absolute offset
    # cancels and never reaches the header.  At design duty_raw_kw == STRIP_DUTY_RAW_DES_KW by
    # construction (same function, same inputs), so the ratio is X/X == 1.0 and Q_strip_kjh is
    # bit-identical to the feed-proportional form it replaces.  Floored at 0.
    m_feed_strip = sum(strip["feed_kmolh"][k] * MW_COMP[k] for k in MW_COMP)   # live stripper feed (kg/h)
    strip_load   = max(m_feed_strip / STRIP_FEED_DES_KGH, 0.0)                 # 1.0 at design (kept: telemetry)
    duty_ratio   = max(strip["duty_raw_kw"] / STRIP_DUTY_RAW_DES_KW, 0.0)      # 1.0 at design (bit-exact)
    Q_strip_kjh = STRIP_DUTY_DES_KW * duty_ratio * 3600.0
    Q_hpcc_kjh  = hpcc["q_steam_kw"]  * 3600.0   # LP steam RAISED, not the full process duty (see below)
    m_strip = Q_strip_kjh / 1850.0          / 3600.0   # MP steam consumed (kg/s)
    m_hpcc  = Q_hpcc_kjh  / HPCC_LATENT_4BAR / 3600.0  # LP steam generated (kg/s)
    # q_steam_kw (computed in hpcc_322e002) = process duty MINUS the extra sensible heat carried out in the
    #   product when it leaves above the design pin (T_prod>HPCC_T_PROD_DES_C at a higher shell P).  This is
    #   the physical shell back-pressure on steam-raising and the missing stabilizing feedback: as P_LP rises
    #   -> t_shell rises -> T_prod rises -> q_steam falls -> m_hpcc falls -> P_LP pulled back to design.  It
    #   references the PINNED 170 C (not live T_adb), so it does NOT self-defeat when the reactor heats.  At
    #   design T_prod==HPCC_T_PROD_DES_C -> q_steam==duty_kw bit-exact -> LP balance untouched.  WITHOUT it the
    #   loop P_LP^->t_shell^->T_prod^->reactor^->(tear)stripper/gas^->HPCC duty^->m_hpcc^->P_LP^ is a positive
    #   runaway (free t_shell -> P_LP runs to ~24 bar a / t_shell 220 C); this re-stabilizes the fixed point.
    if _STEAM_READY:                        # OFF during both boot-pin settles (headers frozen at design)
        step_steam(s.steam, dt, m_strip, m_hpcc, s.steam.m_users9)

    # LT-322504 dynamic level — DOMINO inventory (Option 2, Lead-Ops mandate): the reactor 322R001 is a
    #   true liquid HOLDUP and HV/HIC-322605 has STRICT HYDRAULIC authority over the BOTTOM take-off to the
    #   stripper (NOT over the molar off-gas split — vaporization happens DOWNSTREAM in the 322E001 tubes):
    #       m_in  = ṁ_ov,split                              (live urea-solution PRODUCTION; φ-independent)
    #       m_out = ṁ_des·(θ/θ_des)·(max(L,0)/L_des)        (HV-322605 gate × column head; capacity = ṁ_des)
    #       d(m_liq)/dt = m_in − m_out ;  L = m_liq/(rho(T_bulk)·A).
    #   m_out IS the liquid fed to the stripper (conservation through the holdup) — see f_strip below.  At
    #   design θ==θ_des, L==L_des and ṁ_ov,split==ṁ_des -> m_out==m_in==ṁ_des -> dm/dt=0, f_strip=1.0
    #   (bit-exact pin).  OPEN HV-322605: m_out>m_in -> reactor DRAINS (L↓) AND surges the stripper feed
    #   (transient); level re-settles at L_eq=L_des·(θ_des/θ) while steady feed returns to production.
    #   THROTTLE: m_out<m_in -> reactor FLOODS (L↑, see carryover below) and starves the stripper.  The
    #   take-off capacity is ṁ_des (production-independent), so a CO2-cut feed trip (m_in -> 0) drains the
    #   vessel CONTINUOUSLY toward empty — no φ_fwd FLOOR hack needed (Bug #4 safe by construction).
    T_bulk_react   = sum(new_T) / 4.0                          # live bulk temp (= node mean; design 179.7 C)
    level_m_react  = REACT_LIQ_H_M * s.react_level_pct / 100.0  # prev-step head feeding the discharge (explicit)
    m_ov_split_kgh = sum(react["overflow_kmolh"][k] * MW_COMP[k] for k in react["overflow_kmolh"])  # instantaneous production
    # HV-322605 ⟶ mass-balance timing fix.  The production surge above design (m_ov_split − ṁ_des) is the
    #   synthesis-loop recycle returning as urea solution; the reduced model returns it with ZERO transport
    #   delay (1-step tears), so production refilled the holdup as fast as HV-322605 drained it and LT-322504
    #   barely moved.  Split the surge exactly like the L/W composition lag above: the fresh fraction φ_f
    #   arrives PROMPT, the (1−φ_f) recycle leg buffers through the loop inventory τ_rec (same a_rec, φ_f).
    #   Result: m_out responds to HV-322605 at once while m_in refills over τ_rec -> HV-322605 has prompt,
    #   visible hydraulic authority over the level, re-settling at L_eq=L_des·(θ_des/θ).  At design the surge
    #   is 0 -> lag stays 0 -> m_in==ṁ_des==m_out -> dm/dt=0 (bit-exact pin preserved).
    m_surge_kgh       = m_ov_split_kgh - _react_mdot_kgh                    # production above design (0 at design)
    s.react_m_in_lag += a_rec * (m_surge_kgh - s.react_m_in_lag)           # recycle leg lags through τ_rec
    m_in_kgh          = (_react_mdot_kgh + REACT_FRESH_FRAC * m_surge_kgh
                         + (1.0 - REACT_FRESH_FRAC) * s.react_m_in_lag)    # prompt fresh + lagged recycle
    m_out_kgh      = reactor.outlet_line_outflow_kgph(level_m_react, _react_mdot_kgh, REACT_LEVEL_DES_M,
                                                      s.HIC_322605, REACT_HIC605_DES_PCT)  # HV-322605 take-off
    # DOMINO (Fix-4): ejector forward-carbamate coupling 322E003 -> 322F001 -> 322E002 -> 322R001.
    #   Closing HV-322602 raises the spindle momentum flux ṁ²/(ρA) -> the 322F001 ejector entrains MORE
    #   carbamate from the 322E003 sump (ej["suction_kgh"] climbs above its design draw EJ_SUC_TOT_DES); that
    #   surge is pumped forward through the HPCC (322E002) into the reactor as extra liquid make.  The reduced
    #   loop previously dead-ended this wave at the HPCC — reactor m_in carried no forward-flow term — so
    #   LT-322504 was stone-dead to HV-322602.  Inject the surge (kg/h above design) directly into the holdup
    #   (bypassing m_in_kgh's recycle-lag split — it is a prompt forward-pumped wave, not production).  The
    #   head then climbs above design -> LT-322504 RISES on closing / FALLS on opening.
    #   Driver = the SPINDLE-attributable part of the draw, ṁ_suc·(1 − 1/φ_sp(θ)) -> identically 0 at the design
    #   valve θ=74 (φ_sp=1) at ANY sump state, so the LT-322504 startup/relaxation NLL pin stays bit-exact (it is
    #   NOT keyed on raw suction, which is nonzero off-NLL during the sump fill).  The driver's SUSTAINED part is
    #   a counterfactual (at steady state the sump can only supply its inflow -> a constant forward term would
    #   INVENT mass), so wash it out: low-pass the driver (react_fwd_wash, τ_fwd ≈ sump-drain time) and inject
    #   only the HIGH-PASS residue (driver − wash) — the TRANSIENT pulse on an HV-322602 move that decays to 0
    #   at any steady θ.  Mass-conservative inventory REDISTRIBUTION sump->reactor->stripper; the higher
    #   head raises the level-servoed take-off m_out and the swell relaxes back.
    _phi_sp_theta    = EJ_SPINDLE_R ** ((EJ_OPEN_DES - s.HIC_322602) / 100.0)   # >1 closing, =1 @74, <1 opening
    _fwd_drive_kgh   = ej["suction_kgh"] * (1.0 - 1.0 / _phi_sp_theta)          # spindle-attributable draw (0 @74)
    _a_fwd           = dt / (REACT_FWD_TAU_MIN * 60.0)
    s.react_fwd_wash += _a_fwd * (_fwd_drive_kgh - s.react_fwd_wash)            # low-pass (sustained part)
    m_fwd_carb_kgh   = REACT_FWD_GAIN * (_fwd_drive_kgh - s.react_fwd_wash)     # high-pass: transient pulse, ->0 steady
    s.react_m_liq += k_loop_fill * (m_in_kgh - m_out_kgh + m_fwd_carb_kgh) * (dt / 3600.0)
    s.react_m_liq  = max(s.react_m_liq, reactor.M_HOLDUP_MIN)  # holdup floor -> guards level_from_holdup
    # DOMINO: the hydraulic take-off m_out IS this step's stripper liquid feed — scale the split-fraction
    #   overflow composition to the live outlet mass (f_strip=1 at design -> bit-exact).  The 322E001 native
    #   heat/CO2-strip equations then drive this liquid surge into the overhead gas at its own equilibrium.
    f_strip = (m_out_kgh / m_ov_split_kgh) if m_ov_split_kgh > 1.0e-9 else 1.0
    s.react_overflow_kmolh = {k: react["overflow_kmolh"][k] * f_strip for k in react["overflow_kmolh"]}
    # ISSUE (Phase A): OFF-GAS-LINE LIQUID CARRYOVER on flood.  Throttling the bottom take-off (HV-322605)
    #   cannot pass m_in, so holdup rises to the vessel-full mass M_full = rho(T_bulk)·A·H_liq (PHYSICAL
    #   vessel-full lip; the LT-322504 narrow band saturates 100% earlier, at overflow+1 m).  Liquid above
    #   M_full CANNOT accumulate in the reactor — it physically spills
    #   over the off-gas line (TT-322009) into the HP scrubber (322E003) as ENTRAINED MELT.  Capping m_liq
    #   at M_full simultaneously (a) closes a latent conservation leak (m_liq integrated unbounded above
    #   full while only the level DISPLAY was clamped, so m_out saturated < m_in forever) and (b) yields
    #   the carryover rate = the un-passable excess (m_in − m_out)|_full.  Carryover carries reactor-
    #   OVERFLOW composition + enthalpy (react_T_overflow).  Identically ZERO below the flood lip
    #   (m_liq < M_full at design 80% NLL) -> react_carry_kmolh is None -> scrubber HMB/TT pins bit-exact.
    M_full_react      = reactor.liquid_density(T_bulk_react) * _react_area_m2 * REACT_LIQ_H_M
    react_carry_kgh   = max(s.react_m_liq - M_full_react, 0.0) * (3600.0 / dt)   # spilled melt rate (kg/h)
    s.react_m_liq     = min(s.react_m_liq, M_full_react)                         # vessel cannot exceed full
    s.react_level_pct = clamp(reactor.level_from_holdup(s.react_m_liq, T_bulk_react,
                                                        area_m2=_react_area_m2) / REACT_LIQ_H_M * 100.0,
                              0.0, 100.0)
    # LT-322504 DISPLAY: direct N7 narrow band (datasheet 1.5 m span; top tap 1 m above overflow).  The
    #   transmitter reads the PHYSICAL liquid head through the fixed instrument geometry — LT-322504 tracks
    #   the 322R001 mass balance and NOTHING else (2026-07-03 order: no coupling/pinning to plant load; the
    #   former design-valve SHADOW reference + _load_gate machinery is DELETED).  At the design head
    #   L = REACT_LEVEL_DES_M = 20.0 m it reads exactly NLL 80 %, so the design boot and short holds stay
    #   bit-exact.  KNOWN CONSEQUENCE (was the shadow's raison d'etre): the static design seed is not the
    #   coupled-loop fixed point — over ~5 h the loop relaxes (reactor head −0.49 m / −1.9 %) and the 1.5 m
    #   band amplifies that sag 16.7x (80 % -> ~48 %); that drift is now the INTENDED mass-balance reading.
    #   Saturates 0/100 % off the 1.5 m band like the real transmitter.  HOLDUP, discharge hydraulics, flood
    #   guard and loop P_min all stay on the PHYSICAL head s.react_level_pct.
    _H_liq_react          = REACT_LIQ_H_M * s.react_level_pct / 100.0            # physical head, m
    s.react_lt322504_pct  = clamp(REACT_LEVEL_NLL_PCT
                                  + (_H_liq_react - REACT_LEVEL_DES_M) / REACT_LT_SPAN_M * 100.0,
                                  0.0, 100.0)
    # carryover molar vector = reactor-overflow composition scaled by (entrained mass / overflow mass):
    #   ν_carry,k = ṁ_carry · ν_ov,k / Σ_j ν_ov,j·MW_j  -> preserves overflow mole fractions exactly.
    _ov_mass_kgh      = sum(react["overflow_kmolh"][k] * MW_COMP[k] for k in react["overflow_kmolh"])
    react_carry_kmolh = ({k: react["overflow_kmolh"][k] * (react_carry_kgh / _ov_mass_kgh)
                          for k in react["overflow_kmolh"]}
                         if (react_carry_kgh > 0.0 and _ov_mass_kgh > 0.0) else None)

    # LT-322E002 HPCC liquid inventory (Euler): carbamate condensation make in - ejector fwd out.
    #   phi_in  = live HPCC liquid make / design make  (stripper-gas condensation is motive-indep)
    #   phi_fwd = phi_m^2 forward circulation out (ejector developed head)
    # ISSUE-c/e: the old outflow term was phi_fwd ALONE (level-independent) -> a pure integrator: any
    # in!=out mismatch wound the level to a rail (floods to 100 % at 70 % load, drifts even at design).
    # A condenser sump drains by gravity head, so make the outflow rise with level: phi_out =
    # phi_fwd·(L/NLL).  This closes the loop -> a stable first-order lag that SETTLES at the bounded
    # equilibrium L_eq = NLL·(phi_in/phi_fwd) instead of railing.  At design phi_in = phi_fwd = 1 and
    # L = NLL -> phi_out = phi_fwd -> dL = 0 (NLL is now an exact fixed point; bit-exact design).
    _hpcc_liq_des = HPCC_LIQ_DES_LIVE or HPCC_LIQ_DES_KGH      # live settled ref once pinned
    phi_in_hpcc  = (hpcc["liq_kgh"] / _hpcc_liq_des) if _hpcc_liq_des else phi_fwd
    phi_out_hpcc = phi_fwd * (s.hpcc_level_pct / HPCC_LEVEL_NLL_PCT)
    dL_hpcc      = k_loop_fill * (phi_in_hpcc - phi_out_hpcc) * 100.0 * dt / (HPCC_TAU_FILL_MIN * 60.0)
    s.hpcc_level_pct = clamp(s.hpcc_level_pct + dL_hpcc, 0.0, 100.0)

    # ----- 322E003 HP Scrubber: reactor off-gas + weak carbamate (323P001 A/B) -> off-gas line
    #   (322C001 via HV-322604) + overflow line (322F001).  Shell-side CCW loop (329P006 A/B
    #   circulation + 329E004 tempered-water cooler) removes the carbamate-formation exotherm.
    fic = s.FIC_329409                           # CCW circulation flow controller (FV-329409)
    tic = s.TIC_329005                           # CCW supply-temperature controller (TV-329005)
    fic["pv_bad"] = not _pv_ok(fic["sp"], fic["op"], fic["pv"])   # L3-9 freeze-last-good on bad PV
    if fic["pv_bad"]:                             # bad PV -> hold design CCW flow; op held last-good
        if not math.isfinite(fic["op"]):  fic["op"] = SCRUB_FV409_DES_PCT
        fic["pv"] = SCRUB_CCW_KGH_DES / 1000.0    # coerce finite so no NaN enters m_ccw below
    else:                                         # F4: first-order flow plant lag + AUTO velocity I-PD
        flow_ss = (SCRUB_CCW_KGH_DES / 1000.0) * (fic["op"] / max(SCRUB_FV409_DES_PCT, 1e-6))
        pv_prev = fic["pv_prev"]                   # PV_{k-1} for the velocity proportional term
        fic["pv"] += (dt / FIC_329409_TAU_S) * (flow_ss - fic["pv"])   # lag PV toward valve-char SS
        if fic["mode"] == "AUTO":                  # REVERSE-acting: PV below SP -> open FV-329409
            fic["op"] = clamp(fic["op"] + FIC_329409_KC * (-(fic["pv"] - pv_prev)
                              + (dt / FIC_329409_TI) * (fic["sp"] - fic["pv"])), 0.0, 100.0)
        fic["pv_prev"] = fic["pv"]                 # MAN: op held by operator, PV still lags valve char
    tic["pv_bad"] = not _pv_ok(tic["sp"], tic["op"], tic["pv"])   # L3-9 freeze-last-good on bad PV
    if tic["pv_bad"]:                             # bad PV -> hold design CCW supply T; op held last-good
        if not math.isfinite(tic["op"]):  tic["op"] = SCRUB_TV005_DES_PCT
        tic["pv"] = SCRUB_CCW_T_IN_DES            # coerce finite so no NaN propagates downstream
    else:                                         # F4: first-order supply-T plant lag + AUTO velocity I-PD
        #   T_ss = cooler valve char + exotherm load.  Load = gain·((s-1)+δ_X) -> 0 at design (bit-exact);
        #   a throughput/conversion-deficit rise warms the returning tempered water, which the loop rejects.
        t_load  = TIC_329005_LOAD_GAIN * ((react["co2_scale"] - 1.0) + react["delta_X"])
        T_ss    = clamp(SCRUB_CCW_T_OUT_DES
                        - (SCRUB_CCW_T_OUT_DES - SCRUB_CCW_T_IN_DES) * (tic["op"] / max(SCRUB_TV005_DES_PCT, 1e-6))
                        + t_load, 20.0, SCRUB_CCW_T_OUT_DES)
        pv_prev = tic["pv_prev"]                   # PV_{k-1} for the velocity proportional term
        tic["pv"] += (dt / TIC_329005_TAU_S) * (T_ss - tic["pv"])      # lag PV toward valve-char SS + load
        if tic["mode"] == "AUTO":                  # DIRECT-acting: PV above SP -> open TV-329005 (more cooling)
            tic["op"] = clamp(tic["op"] + TIC_329005_KC * ((tic["pv"] - pv_prev)
                              + (dt / TIC_329005_TI) * (tic["pv"] - tic["sp"])), 0.0, 100.0)
        tic["pv_prev"] = tic["pv"]                 # MAN: op held by operator, PV still lags valve char
    m_ccw_kgh  = max(fic["pv"], 1e-6) * 1000.0    # CCW circulation (t/h -> kg/h)
    top_ratio  = (strip["top_mol"] / STRIP_TOP_MOL_DES) if STRIP_TOP_MOL_DES else 1.0  # stripper overhead push
    nu = s.p_syn_bara / SYN_P_DES_BARA            # vent ratio = PT-329201/PT_des (prior-step state; breaks the algebraic loop)
    # HV-322604 back-pressure penalty — valve vent capacity vs the scrubber's required inert purge:
    #   vent_frac = m_og/(m_og_des·s) = R^((θ−θ_des)/100)·√(ΔP/ΔP_des);  θ_des = design opening (50%,
    #   demand-met), equal-% trim per datasheet (must match hv_322604 so the diagnostic vent flow and
    #   the back-pressure penalty use one characteristic).  Pinch below design (vent_frac<1) starves the
    #   inert vent -> uncondensed inerts accumulate and integrate PT-329201 up.  Prior-step p_syn for ΔP.
    dP_vent   = max(s.p_syn_bara - SCRUB_HV604_P_OUT, 0.0)
    vent_frac = _eq_pct(s.HIC_322604, SCRUB_HIC604_DES_PCT) * math.sqrt(dP_vent / SCRUB_HV604_DP_DES)
    scrub = scrub_322e003(react["offgas_kmolh"], react["co2_scale"], tic["pv"], m_ccw_kgh,
                          vent_ratio=nu, nc_act=react_nc_ratio(react["overflow_kmolh"]),
                          hic604_pct=s.HIC_322604,
                          liq_carry_kmolh=react_carry_kmolh, t_carry_c=s.react_T_overflow,
                          choke_level_pct=s.scrub_level_pct, spindle_phi=_phi_sp_theta)
    # PT-329201 reverse heat->pressure: condensation capacity (CCW flow) vs vent demand (s*nu).
    #   rho_cond < 1 (e.g. CCW throttled) -> off-gas under-condenses, accumulates, integrates PT up.
    #   Forward stripper push (top_ratio) sets the no-deficit target; first-order Euler accumulation
    #   over tau (min -> s).  Design: m_ccw=des, s=1, nu=1, top_ratio=1 -> rho=1 -> PT holds 140.7.
    #   Thermal factor f_th = (T_cond − T_ccw_in)/(T_cond − T_ccw_in,des): a WARMER CCW supply
    #   shrinks the condensation driving force -> capacity falls -> rho_cond drops -> PT-329201 rises.
    #   f_th ≡ 1 at design T_ccw_in=80 C, so a pure CCW-flow move reduces to the prior calibration.
    f_th      = (SCRUB_OVERFLOW_T_C - tic["pv"]) / max(SCRUB_OVERFLOW_T_C - SCRUB_CCW_T_IN_DES, 1e-6)
    rho_cond  = (m_ccw_kgh / SCRUB_CCW_KGH_DES) * max(f_th, 0.0) / max(react["co2_scale"] * nu, 1e-6)
    # PT-329201 vapour differentiation: NH3 + H2O overhead are CONDENSABLE solvents (absorbed into
    # carbamate/condensate, NOT pressure-building); only ACID CO2 unpaired by NH3 (free CO2 =
    # CO2 - NH3/2, from 2 NH3 + CO2 -> carbamate) plus NH3 that exceeds condensation capacity
    # (rho_cond < 1) builds synthesis pressure.  Normalised by TOTAL design overhead (not the small
    # free-CO2 anchor) for numerical stability.  Design: co2_free=98.6, slip=0 -> pb_push=0.
    n_top     = strip["top_kmolh"]
    co2_free  = max(n_top["CO2"] - 0.5 * n_top["NH3"], 0.0)                           # free acid CO2
    nh3_slip  = max(1.0 - rho_cond, 0.0) * max(n_top["NH3"] - STRIP_TOP_NH3_DES, 0.0)  # un-absorbed NH3
    n_pb      = co2_free + nh3_slip                                                   # pressure-building load
    pb_push   = (n_pb - STRIP_TOP_CO2FREE_DES) / STRIP_TOP_MOL_DES if STRIP_TOP_MOL_DES else 0.0
    # L3-2c cold-start fix: loop-mass fraction (mean of the three HP liquid inventories vs their design
    #   NLL) hoisted above pt_fwd so the BASE stripper forward-push deviation is ALSO inventory-gated.  An
    #   empty loop has no circulation to develop stripper overhead, so it must not push the PT target above
    #   design -- previously pt_fwd overshot to ~162 barg at cold start (pb_push ungated), which made the
    #   model-free pressurisation tau read short (§6.4).  == 1.0 at design (levels at NLL) AND pb_push == 0
    #   -> pt_fwd == SYN_P_DES_BARA exactly (design SS bit-exact); -> pure SYN_P_TAU_FILL_MIN lag toward
    #   design as the loop empties (§6.1 emergent tau, never a hard lag on the pressure state).
    m_loop_frac = clamp((s.react_level_pct + s.hpcc_level_pct + s.strip_level)
                        / (REACT_LEVEL_NLL_PCT + HPCC_LEVEL_NLL_PCT + STRIP_LEVEL_SP_DES), 0.0, 1.0)
    live_syn_p_anchor = hpcc["P_bub"] - (HPCC_P_DES_BARA - SYN_P_DES_BARA)
    pt_fwd    = live_syn_p_anchor * (1.0 + m_loop_frac * SYN_P_COUPLING * pb_push)
    # L3-2b inventory gate on the PT forcing offsets.  m_loop_frac (the same loop-mass fraction used
    #   for the PT floor below) multiplies EVERY additive forcing term so an empty / part-filled loop
    #   cannot saturate p_target: the deficit / vent / conversion push can only develop as the HP
    #   liquid inventories physically accumulate.  == 1.0 at design (levels at NLL) -> forcing
    #   unchanged -> design steady state stays bit-exact; -> 0 as the loop empties -> cold-start
    #   pressurisation tracks inventory fill (emergent tau), never a hard lag on the pressure state
    #   (report §6.1 / §6.4 remediation option 2).  m_loop_frac computed above (hoisted for pt_fwd gate).
    # Fix-2: dimensionless conversion-deficit forcing Π = κ·δ_X injected ADDITIVELY into the PT
    # target.  When the reactor under-converts (low N/C / high H/C), the unconverted NH3 + CO2 flash
    # to the synthesis loop and aggressively pressurise it: Π·P_des bar of extra forcing.  δ_X is
    # clamped >= 0 (Fix-2), so at/above design Π = 0 -> no spurious depressurisation at high N/C.
    Pi_conv   = REACT_PI_KAPPA * react["delta_X"]
    pt_target = pt_fwd + m_loop_frac * (
                         SYN_P_DEFICIT_GAIN * max(1.0 - rho_cond, 0.0) * live_syn_p_anchor
                       + SYN_P_VENT_GAIN * max(1.0 - vent_frac, 0.0) * live_syn_p_anchor
                       + Pi_conv * live_syn_p_anchor)  # HV-322604 vent: ONE-SIDED inert-purge deficit only
                                                    #   (close<des -> inerts accumulate -> PT up; open>=des
                                                    #   -> purge is supply-limited, no extra venting -> PT
                                                    #   unchanged).  Tiny purge valve cannot crash HP P.
    # L3-2 inventory-aware PT floor: a totally empty loop must be able to bottom out at atmospheric,
    #   not a hard 120 bar.  Loop-mass fraction = mean of the three HP liquid inventories vs their design
    #   NLL (LT-322504 80%, LT-322E002 50%, LT-322501 50%); == 1.0 at design -> P_min == 120 bar (the
    #   static SYN_P_MIN_BARA preserved exactly), -> 1.0 atm as the loop empties.
    #       P_min = 1.0 + 119.0 * clamp(M_loop / M_loop_des, 0, 1)
    #   (m_loop_frac computed above, at the forcing gate.)
    p_syn_min   = 1.0 + 119.0 * m_loop_frac
    # Inventory-emergent pressurisation tau: an EMPTY loop (m_loop_frac -> 0) has little condensable/
    #   vapour inventory to build head, so PT climbs on the sourced cold-start constant SYN_P_TAU_FILL_MIN
    #   (57.8 min, 06-03 Section 1.2 field FOPTD); as the three HP liquid inventories fill toward NLL the
    #   constant relaxes linearly to the warm op-pt SYN_P_TAU_MIN (4 min).  tau EMERGES from inventory fill
    #   -- NOT a hard lag on the pressure state (report Section 6.1: never a fudge lag; tune physical
    #   inventory).  At design m_loop_frac == 1 -> tau_eff == SYN_P_TAU_MIN and (pt_target - p_syn) == 0,
    #   so the steady-state hold is bit-exact regardless of tau_eff.
    _tre = 4.0   # relax-schedule shape (Smith-calibrated to Section 6.4 band); holds tau_eff at
                 #   SYN_P_TAU_FILL_MIN until m_loop_frac -> 1, then collapses to warm SYN_P_TAU_MIN
    tau_eff_min = SYN_P_TAU_FILL_MIN + m_loop_frac ** _tre * (SYN_P_TAU_MIN - SYN_P_TAU_FILL_MIN)
    s.p_syn_bara = clamp(s.p_syn_bara + (dt / (tau_eff_min * 60.0)) * (pt_target - s.p_syn_bara),
                         p_syn_min, SYN_P_MAX_BARA)
    scrub["P_overflow"] = s.p_syn_bara            # PT-329201 dynamic synthesis pressure (bar a)
    scrub["P_offgas"]   = s.p_syn_bara            # off-gas line rides the live synthesis P (HV-322604 P_up)
    scrub["vent_frac"]  = vent_frac               # HV-322604 vent capacity / required purge (<1 -> PT rises)
    scrub["rho_cond"]   = rho_cond                # condensation capacity/demand (diag; <1 -> PT rises)
    scrub["co2_free"]   = co2_free                # free acid CO2 overhead (pressure-building, kmol/h)
    scrub["pb_push"]    = pb_push                 # PT forward push (pressure-building overhead deviation)
    scrub["top_ratio"]  = top_ratio              # total overhead ratio (diag only; superseded by pb_push)
    scrub["P_bub_hpcc"] = hpcc["P_bub"]           # 322E002 bubble-point synthesis P (bar a, diag)
    # L3-5 scrubber-overflow mushy-zone: carbamate crystallization (T_cryst=60 C) throttles the
    #   322F001 overflow as T_overflow falls.  No vessel inventory ODE here (scrubber is a tear) ->
    #   raise SCRUBBER_SOLIDIFICATION as the accumulation proxy when flow is choked.
    f_ovf = _f_flow(scrub["T_overflow"], 60.0)
    scrub["overflow_kmolh"] = {k: v * f_ovf for k, v in scrub["overflow_kmolh"].items()}
    s.flags["SCRUBBER_SOLIDIFICATION"] = (f_ovf < 1.0)
    # --- Option 3: 322E003 sump inventory ODE (Euler) ---------------------------------------------
    #   dM/dt = ṁ_cond,in − ṁ_entrain.  ṁ_cond,in = the condensation/absorption make this tick
    #   (post-mushy-zone overflow mass); ṁ_entrain = what the ejector actually pulled this tick
    #   (ej["suction_kgh"], from the non-linear curve, computed earlier this step).  At design
    #   both == EJ_SUC_TOT_DES -> dM=0, level holds NLL.  Ejector stall -> entrain<<cond -> M rises.
    m_cond_in = sum(scrub["overflow_kmolh"][k] * MW_COMP[k] for k in scrub["overflow_kmolh"])
    s.scrub_holdup_kg = clamp(s.scrub_holdup_kg + (m_cond_in - ej["suction_kgh"]) * (dt / 3600.0),
                              0.0, SCRUB_HOLDUP_MAX_KG)
    s.scrub_level_pct = clamp(s.scrub_holdup_kg / SCRUB_HOLDUP_NLL_KG * SCRUB_LEVEL_NLL_PCT,
                              0.0, 100.0)
    _valve_og_in.comp = scrub["offgas_kmolh"]
    _valve_og_in.set_state(T=scrub["T_offgas"], P=scrub["P_offgas"])
    _valve_unit.hic_pct = s.HIC_322604
    _valve_unit.solve()
    hv604 = _valve_unit.diagnostics
    # L3-7 HV-322604 off-gas: external steam-tracing holds the 60 C baseline; flag only when extreme JT
    #   cooling overwhelms the jacket (T_out < 20 C).  Flow NOT restricted (gas line) -> fouling warning.
    s.flags["CARBAMATE_DEPOSITION"] = (hv604["T_out"] < 20.0)
    TDY_329125 = scrub["t_ccw_out"] - tic["pv"]   # TT-329125 − TIC-329005 (condensation quality)
    q_e004_kw  = scrub["q_ccw_kw"]                # 329E004 tempered-water-cooler duty (loop closure)

    # ----- Section-322 tear display lags (compute ONCE per tick -> shared by both telemetry views) -----
    #   Each published downstream temperature / level / analyzer is relaxed toward its algebraic target
    #   with a real time constant (see _lag1 + the TAU block) so an upstream stream-property or
    #   composition step RAMPS the indicator instead of snapping in a single 0.1 s tick.  Computed once
    #   here because several tags appear in two telemetry blocks; calling the relax twice would double-step.
    d_TT322012  = _lag1(s.tlag, "TT322012", ej["T_C"],                                 EJ_T_TAU_S,      dt)
    d_TT322013  = _lag1(s.tlag, "TT322013", strip["T_top"],                            STRIP_T_TAU_S,   dt)
    d_TT322004  = _lag1(s.tlag, "TT322004", T_bot_disp,                                STRIP_T_TAU_S,   dt)
    d_TT323001  = _lag1(s.tlag, "TT323001", TT_323001,                                 STRIP_T_TAU_S,   dt)
    d_TT322010  = _lag1(s.tlag, "TT322010", hpcc["T_prod"],                            HPCC_T_TAU_S,    dt)
    # CP-5: the melt bubble-point can compute above the feed-supply head off-design (measured 221
    # bar a at 40 % load), but the 322E002 vessel physically cannot be pressurised past what the
    # CO2/HPCC/ejector feed delivers -- SYN_P_MAX_BARA (144.2), the ceiling main.py already declares
    # and enforces on the PT-329201 loop state.  Cap the PUBLISHED HPCC pressure at that head (raw
    # hpcc["P_bub"] is left untouched for any internal use).  At design P_bub == SYN_P_MAX_BARA
    # exactly, so min() binds at equality and the value is byte-identical -> pin unaffected.
    d_HPCC_P    = min(_lag1(s.tlag, "HPCCP", hpcc["P_bub"], HPCC_P_TAU_S, dt), SYN_P_MAX_BARA)
    d_TT322002  = _lag1(s.tlag, "TT322002", scrub["T_overflow"],                       SCRUB_T_TAU_S,   dt)
    d_TT322011  = _lag1(s.tlag, "TT322011", scrub["T_offgas"],                         OFFGAS_T_TAU_S,  dt)
    d_TT322011l = _lag1(s.tlag, "TT322011l", hv604["T_out"],                           OFFGAS_T_TAU_S,  dt)
    d_TT329125  = _lag1(s.tlag, "TT329125", scrub["t_ccw_out"],                        CCW_T_TAU_S,     dt)
    d_AT322701  = _lag1(s.tlag, "AT322701", react_nc_ratio(react["overflow_kmolh"]),  AT_322701_TAU_S, dt)

    # ==================================================================================
    #  UNIT 323 - LP RECIRCULATION & PRE-EVAPORATION  (rigorous state-space, conservative)
    #  Boundary feed = 322E001 letdown bottoms:  m_feed = drain_kgh (kg/h) at T = TT_323001
    #  (post-LV-322501 flash, un-lagged).  Four lumped liquid stages; each stage carries an
    #  inventory ODE  dM/dt = m_in - m_vap - m_out  and a well-mixed energy ODE
    #        M*cp*dT/dt = m_in*cp*(T_in - T) + Q - m_vap*lambda
    #  integrated with the live sub-step dt.  Vapor rates are the DESIGN mass split fractions
    #  of the live inflow, so mass closes every tick by construction:
    #        m_feed == SUM(vapor) + product_317 + d(inventory)/dt .
    #  All latent/duty coefficients were back-solved at the design seed, so at boot every
    #  dM/dt == dT/dt == 0 (the MB/PFD anchors are the exact fixed point).
    # ==================================================================================
    m_feed_323 = max(drain_kgh, 0.0)                       # live 322E001 bottoms -> 323C003 (kg/h)
    T_feed_323 = TT_323001                                 # C, post-LV-322501 flash (un-lagged)
    # AUDIT C10 — cp is a PROPERTY, not a constant.  One lumped 2.5 kJ/kg.K used to cover the 44 %
    # granulation return at 40 C, the 55.9 % stripper bottoms at 119 C and the 80 % product at 99 C.
    # Each stream now carries its own, as a departure from that lumped anchor so every back-solved
    # lambda and UA above stays exactly valid (see the R323_CP_*_DES block).  The feed composition is
    # hoisted above the energy terms because the FEED's cp is what the feed sensible duty needs.
    w_feed_323 = _w_norm({k: strip["bot_mass_pct"].get(k, 0.0) for k in SOL_SPECIES})
    _cp = lambda w, T, des: R323_CP_SOLN + (urea_soln_cp(w, T) - des)   # noqa: E731 -- departure form
    cp_feed323 = _cp(w_feed_323.get("Urea", 0.0),          T_feed_323,        R323_CP_S208_DES)
    cp_c003    = _cp(s.w_c003.get("Urea", 0.0),            s.r323_c003_T,     R323_CP_C003_DES)
    cp_f004    = _cp(s.w_f004.get("Urea", 0.0),            s.r323_f004_T,     R323_CP_F004_DES)
    cp_f010    = _cp(s.w_f010.get("Urea", 0.0),            s.r323_f010_T,     R323_CP_F010_DES)
    cp_331     = _cp(W_S331["Urea"],                       R323_M331_T_C,     R323_CP_S331_DES)

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
    
    m_305       = min(R323_PHI_V305 * m_feed_323, m_flash_gas + m_pool_vap)       # top vapor -> 323E003 LPCC (305, kg/h)
    q305_avail_kw = q_flash_avail_kw + Q_e002_kw                                  # total available latent kW
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
    m739_prev  = s.tlag.get("R328_739",   R328_C004_M739_DES)   # 328C004 bottoms -> 328E007 -> 740

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
    # 718A/718B demand-split COORDINATOR (setpoint feed-forward decoupling).
    #   Old cas_sp = m718_dmd - m_718B (live PV) coupled the two loops through 718B's lagged flow:
    #   718A chased 718B's measured PV while both drew on the shared m718_dmd, giving a 2-tick
    #   bang-bang limit cycle (3.18<->3.50 m3/h).  Break the feedback -- derive 718A's remainder
    #   from 718B's DEMAND (its SP in AUTO/CAS), not its noisy measured flow.  Steady state is
    #   unchanged (718B AUTO settles to its SP), so the 323D011 718-split conservation still holds
    #   (m_718A + m_718B -> m718_dmd); only the oscillating transient is removed.  In MAN the op is
    #   operator-fixed so 718B is already non-oscillating and the live flow is a safe fallback.
    if s.FIC_323418["mode"] in ("AUTO", "CAS"):
        m718B_ff = s.FIC_323418["sp"] * RHO_718_KGM3     # feed-forward from setpoint (kg/h)
    else:
        m718B_ff = m_718B                                # MAN: op-fixed, live flow non-oscillating
    m718A_dmd = max(m718_dmd - m718B_ff, 0.0)            # remainder demand for 718A (kg/h)
    #   718A is the unmetered remainder, so it is a pure transport lag on that demand -- the 45 s
    #   time constant is the one the old FIC-328405 measurement filter carried (the leg's physical
    #   piping/inertia lag; the controller it belonged to is gone, the lag is not).  _lag1 has DC
    #   gain 1 and lazy-inits to its target, so the design seed is bit-exact and the steady-state
    #   718 split is unchanged: m_718A + m_718B -> m718_dmd.
    m_718A   = _lag1(s.tlag, "F_718A", m718A_dmd, R3232_M718A_TAU_S, dt)  # -> 328E004/328D001 (bal)
    m_718_tot= m_718A + m_718B                                            # -> 323D011 draw (kg/h)
    Q_e011   = R3232_E011_UA_KW * (Te011 - 35.0)
    sens_e011= (((m_701 + R3232_E011_RECON_KGH)*(R3232_E011_T701 - Te011)
                 + m_786_d001*(R3232_E011_T786    - Te011)
                 + m_321*(74.0 - Te011)
                 + m_402*(56.0 - Te011))/3600.0*R3232_CP)
    m_cond_e011 = max(in_e011 - m_402 - m_v011, 0.0)
    P_e011   = sens_e011 + m_cond_e011/3600.0*R3232_E011_LAMV - Q_e011
    s.r3232_e011_P = max(s.r3232_e011_P + R3232_E011_P_KP*(gen_v011 - m_v011)/3600.0*dt, 0.1)
    s.r3232_e011_T = Te011 + P_e011*dt/max(s.r3232_e011_M*R3232_CP, 1e-6)
    s.r3232_e011_M = max(s.r3232_e011_M + (in_e011 - m_v011 - m_718A - m_718B)/3600.0*dt, 1.0)

    # ----- recycle-tear writes (one-tick delay -> next step reads these) --
    s.tlag["R3232_v011"] = m_v011
    s.tlag["R3232_702"]  = m_v011
    s.tlag["R322_756"]   = m_756
    s.tlag["R328_748"]   = m_748
    s.tlag["R328_750"]   = m_750
    s.tlag["R328_775"]   = m_775
    s.tlag["R3232_718A"] = m_718A
    s.tlag["R3232_744"]  = m_744
    s.tlag["R3232_718B"] = m_718B
    s.tlag["R328_M931"]  = m_931
    s.tlag["R328_739"]   = m_739       # 328C004 bottoms this tick -> caps next tick's 741 recycle

    # ======================================================================
    #  UNIT 324 — TWO-STAGE VACUUM EVAPORATION  (rigorous, conservative)
    #  Feed = m_324 (kg/h, 80% urea, ~99 C) delivered by FIC-324401. LV-B
    #  recycle returns to 323D002 Compartment I on a one-tick tear; it is not
    #  an undocumented direct Stage-1 feed. Each stage runs a TIC->PIC steam cascade that sets the
    #  chest pressure -> Q = UA*(tsat(p_chest) - T); urea is conserved so the
    #  water evaporated is fixed exactly by the concentration anchor, and the
    #  energy/mass/pressure ODEs integrate the live sub-step dt.  UA/λ were
    #  back-solved at the seed so dM/dt = dT/dt = dP/dt = 0 at design.  Vacuum
    #  is held by a false-air PIC balanced against a fixed ejector pull.
    #      HARD anchors: Stage 1 0.33 bar a / 130 C / 80->95 % ;
    #                    Stage 2 0.131 bar a / 140 C / 95->98.6 %.
    # ======================================================================
    # AUDIT C10.  cp324 was one constant (2.5) for the feed AND both melts, across a train that
    # takes the solution from 80 % urea to 97.71 %.  Each use below now takes cp at its own local
    # composition and temperature; urea_soln_cp returns the design anchor bit-exactly at the design
    # composition, so the seed is untouched and only the off-design response changes.
    # ---- Stage 1 : Evaporator I 324E001 + separator 324F001 (0.33 bar a, 130 C) --
    feed1_m    = max(m_324, 0.0)                                               # 323D002 pump discharge (kg/h)
    # AUDIT B1 (ripple).  This read the FROZEN R324_W_IN, so no composition change anywhere
    # upstream could reach the evaporators -- a measured 0 of 66 unit-324 telemetry leaves
    # responded to a reactor-overflow composition step.  It now reads the live 323D002 tank
    # vector.  (That vector is itself held at the design strength by sol_pin_strength; see the
    # note there -- both had to change for the ripple to actually flow.)
    w_tank     = s.w_d002.get("Urea", R324_W_IN)
    urea1_in   = w_tank * feed1_m                                             # urea into Stage 1 (kg/h)
    w_feed1    = w_tank
    # AUDIT C18 — the Stage-1 feed enthalpy term used the FROZEN R324_FEED_T_C = 99 C while the
    # 323D002 tank temperature is a live ODE state carrying (by the code's own note at the tank) a
    # LOW-temperature alarm.  A 10 K tank cooldown withholds 644 kW = 6.1 % of R324_E001_Q_DES_KW,
    # i.e. ~1067 kg/h less water evaporated -- and the model moved none of it.
    T_feed1    = s.r323_d002_T
    cp_feed1   = urea_soln_cp(w_feed1, T_feed1)
    cp_hold1   = urea_soln_cp(s.w_e001.get("Urea", R324_W_EV1), s.r324_e001_T)
    tic1_op    = _ctrl_ipd(s.TIC_324001, s.r324_e001_T, dt)                   # steam chest-P demand (bar a)
    pic203_pv  = clamp(s.PIC_329203["op"]/100.0*s.steam.P_LP, 0.0, s.steam.P_LP)
    pic203_op  = _ctrl_ipd(s.PIC_329203, pic203_pv, dt, cas_sp=tic1_op)       # steam valve stroke (%)
    p_chest_e001 = steam_chest_pressure(pic203_op, s.steam.P_LP)
    Q_e001_kw  = max(R324_E001_UA_KW*(tsat_steam(p_chest_e001) - s.r324_e001_T), 0.0)
    # AUDIT F-4 — evaporation is DUTY-LIMITED, and the melt strength FOLLOWS it (was pinned at
    # R324_W_EV1 by construction, so no operator action could dilute the product).  q1_avail is
    # the latent duty left after the feed has been carried to the stage temperature; the water
    # removed is whichever is smaller — the concentration target or what that duty can boil.
    # AUDIT TD-016 — the evaporator melt strength IS the smooth VLE equilibrium at the controlled
    # vacuum, and the water removed follows it continuously.  This closes the residual limit cycle
    # and replaces the whole TD-014/TD-015 min(concentration-cap, duty) two-branch closure.
    #
    # The old concentration cap was a FIXED 94.31 % ceiling — `urea_in / R324_W_EV1` — whose
    # d(conc)/dT is identically zero.  Once the melt hit it, more steam only raised T with no
    # concentration payoff, so TIC-324001 saw zero process gain, disengaged, let the melt drift and
    # then over-corrected: the relay chatter the Urea-Water VLE research (sec 2) blames for these
    # cycles.  Worse, the min()-switching fed straight into the 324F001 vacuum ODE and swung the
    # separator pressure. The continuous Extended-UNIQUAC departure w_eq(T,P) removes all of it:
    #   * a real, non-zero dCu/dT  -> TIC-324001 has genuine gain and never disengages;
    #   * v depends on TEMPERATURE only (the vacuum is regulated separately by PIC-324202), so the
    #     P -> v -> P coupling that destabilised the separator pressure is gone;
    #   * one branch, so no min(), no relay, no chatter.
    # Evaluated at the CONTROLLED design vacuum (0.33 bar a), not the live separator pressure, so the
    # melt target is a pure smooth function of temperature.  Anchored (w_eq(130,0.33) == R324_W_EV1)
    # so v == R324_V1_DES and P_e001 == 0 bit-exact at the design seed; TIC-324001 stays what TD-015
    # made it — a melt-strength controller acting through temperature — now without the relay.
    # Close the pressure/VLE algebraic tear inside the stage.  Pressure sets equilibrium vapour
    # generation; vapour load and ejector pull set pressure.  A bounded fixed-point solve prevents
    # the returned pressure and composition from belonging to different integration instants.
    fa202_m = R324_F001_FA_DES * (s.PIC_324202["op"] / max(R324_PV202_OP_DES, 1e-6))
    _ctrl_ipd(s.PIC_324202, s.r324_f001_P, dt)
    mot9605_m = s.HIC_329605 / 100.0 * R324_HV9605_SPAN
    M_f001_pre = s.r324_f001_M
    t1_old = s.r324_e001_T
    t1_solved = t1_old
    p1_old = s.r324_f001_P
    p1_solved = p1_old
    t1_fp_residual = math.inf
    t1_fp_converged = False
    t1_fp_iterations = 0
    for t1_fp_iterations in range(1, R324_PT_LOOP_MAXIT + 1):
        Q_e001_kw = max(R324_E001_UA_KW * (tsat_steam(p_chest_e001) - t1_solved), 0.0)
        w_eq1 = evap_w_eq(t1_solved, p1_solved,
                          R324_W_EV1, R324_E001_T_SP_C, R324_F001_P_BARA)
        v1_m = clamp(feed1_m - urea1_in / max(w_eq1, 1e-6), 0.0, feed1_m)
        pwr1 = (feed1_m/3600.0 * cp_feed1 * (T_feed1 - t1_solved)
                + Q_e001_kw - v1_m/3600.0 * R324_LAM_V1)
        t1_next = t1_old + pwr1 * dt / max(M_f001_pre * cp_hold1, 1e-6)
        m703_fp = (VACUUM_CONDENSERS["324E002"]["inlet_kgh"]
                   + (m_evap - R323_MEVAP_DES) + (v1_m - R324_V1_DES)
                   + (fa202_m - R324_F001_FA_DES))
        nc002_fp = max(72.0 - R324_F001_FA_DES + fa202_m, 0.0)
        vent002_fp = max(nc002_fp, m703_fp - VACUUM_CONDENSERS["324E002"]["condensate_kgh"])
        ejpull_live = (R324_F001_EJPULL_DES * (mot9605_m / R324_F002_MOTIVE_DES)
                       * (p1_solved / R324_F001_P_BARA))
        p1_next = clamp(p1_old
                        + R324_F001_P_KP * (vent002_fp - ejpull_live) / 3600.0 * dt,
                        0.05, 1.0)
        t1_fp_residual = max(abs(p1_next - p1_solved), abs(t1_next - t1_solved))
        if t1_fp_residual <= R324_PT_LOOP_TOL:
            p1_solved = p1_next
            t1_solved = t1_next
            t1_fp_converged = True
            break
        p1_solved = p1_next
        t1_solved = t1_next
    s.r324_e001_T = t1_solved
    s.r324_f001_P = p1_solved
    w_eq1 = evap_w_eq(s.r324_e001_T, s.r324_f001_P,
                      R324_W_EV1, R324_E001_T_SP_C, R324_F001_P_BARA)
    v1_m = clamp(feed1_m - urea1_in / max(w_eq1, 1e-6), 0.0, feed1_m)
    Q_e001_kw = max(R324_E001_UA_KW * (tsat_steam(p_chest_e001) - s.r324_e001_T), 0.0)
    _DIAG["E001"] = {
        "weq": w_eq1, "v": v1_m, "Q": Q_e001_kw,
        "T": s.r324_e001_T, "feed": feed1_m, "urea_in": urea1_in,
        "thermo_model": extended_uniquac.MODEL_NAME,
        "thermo_validity": extended_uniquac.validity_status(
            s.r324_e001_T + 273.15, s.r324_f001_P
        ),
        "thermo_px_residual_bara": extended_uniquac.px_equilibrium_residual(
            w_eq1, s.r324_e001_T + 273.15, s.r324_f001_P
        ),
        "iteration_count": t1_fp_iterations,
        "iteration_residual": t1_fp_residual,
        "converged": t1_fp_converged,
    }
    p1_m       = max(feed1_m - v1_m, 0.0)                                     # Stage-1 melt (kg/h)
    w1_live    = clamp(urea1_in / max(p1_m, 1e-6), 0.0, 1.0)                  # LIVE Stage-1 urea mass frac
    # AUDIT C3 — this was `m_p1 = p1_m`, i.e. outlet := inlet - vapour, which makes the holdup ODE
    # below (feed1_m - v1_m - m_p1) identically ZERO for every operating point: 324F001 was a
    # zero-capacity node whose level indicator could not move and whose mass was nevertheless the
    # denominator of the Stage-1 temperature ODE.  The drain is a barometric leg into the 324F003
    # deep vacuum, so the outflow is hydraulic (square-root in the liquid head), not a bookkeeping
    # identity.  Anchored: at the design holdup the ratio is exactly 1.0, sqrt(1.0) == 1.0, and
    # R324_P1_DES == R324_FEED_DES - R324_V1_DES == p1_m at design, so dM/dt is still exactly 0 at
    # the seed -- but the separator can now surge, drain and flood.
    m_p1       = R324_P1_DES * math.sqrt(max(M_f001_pre / R324_F001_M_DES, 0.0))   # barometric leg -> Stage 2 (kg/h)
    s.r324_f001_M = max(M_f001_pre + (feed1_m - v1_m - m_p1)/3600.0*dt, 1.0)
    # AUDIT F-8/TD-009: Stage-1 species balance.  The blended feed is the live tank composition plus
    # the live Stage-2 recycle, so the melt strength published by the SPECIES layer is derived from
    # a genuine component balance rather than the urea/W_EV bookkeeping.  Both are published: see
    # finding F-11 for why they differ by ~1.5 pp (the PFD's stream-317 composition is not reachable
    # from stream 319 by evaporation alone -- a source-data inconsistency, not a model defect).
    feed1_w    = dict(s.w_d002)
    y_v1       = sol_vapour_y(s.w_e001, SOL_E001["alpha"])
    xi_e001    = sol_biuret_xi("E001", M_f001_pre, s.w_e001, s.r324_e001_T)
    s.w_e001   = sol_pin_strength(
        sol_advance(s.w_e001, M_f001_pre, s.r324_f001_M, feed1_m, feed1_w,
                    v1_m, y_v1, m_p1, xi_e001, dt), w1_live)
    # Vacuum pressure and VLE were solved together above.
    # AUDIT C5 — the pull had NO suction-pressure term, so the vacuum ODE below was a pure open
    # integrator: nothing on its right-hand side depended on s.r324_f001_P.  Shutting HIC-329605 gave
    # dP/dt = 0.02*(14073+250)/3600 = 0.0796 bar/s and the state ramped to the 1.0 bar clamp in 8.4 s
    # and stayed pinned; with PIC-324202 in MAN any imbalance ran to a rail.  A steam-jet ejector's
    # entrainment capacity falls with suction pressure -- that roll-off is the only thing that makes
    # an uncontrolled vacuum node self-regulating, and 323F010 already carries exactly this factor.
    # Anchored: at design P == R324_F001_P_BARA -> ratio 1.0 -> pull == EJPULL_DES bit-exact.
    # ---- 324E001 steam-side condensate : LIC-329505 "active controlled steam trap"
    #  The chest condenses the LP steam it gives up as Q_e001 (cond_gen = Q/lambda);
    #  LV-329505 drains the shell to hold the level.  Steam-side only -> off the
    #  urea/water process network, so this loop is conservation-neutral: at design
    #  cond_gen == lv9505_m -> level parks at SP with zero drift.
    cond_gen   = Q_e001_kw / R324_E001_LAM_STEAM * 3600.0                     # steam condensed on shell (kg/h)
    lvl_e001c  = clamp(s.r324_e001_cond_M / R324_E001_COND_M_FULL * 100.0, 0.0, 100.0)
    lic9505_op = _ctrl_ipd(s.LIC_329505, lvl_e001c, dt)                      # LV-329505 drain stroke (%)
    lv9505_m   = lic9505_op/100.0 * R324_LV9505_SPAN                         # condensate discharge (kg/h)
    s.r324_e001_cond_M = max(s.r324_e001_cond_M + (cond_gen - lv9505_m)/3600.0*dt, 0.01)

    # ---- Stage 2 : Evaporator II 324E003 + separator 324F003 (0.131 bar a, 140 C) -
    feed2_m    = m_p1                                                         # Stage-1 melt (95%) -> Stage 2
    cp_feed2   = urea_soln_cp(w1_live, s.r324_e001_T)                         # LIVE Stage-1 melt cp
    cp_hold2   = urea_soln_cp(s.w_e003.get('Urea', R324_W_EV2), s.r324_e003_T)
    urea2_in   = w1_live * feed2_m                                            # urea into Stage 2 (kg/h, LIVE frac)
    tic2_op    = _ctrl_ipd(s.TIC_324002, s.r324_e003_T, dt)                   # steam chest-P demand (bar a)
    pic212_pv  = clamp(s.PIC_329212["op"]/100.0*s.steam.P_9, 0.0, s.steam.P_9)
    pic212_op  = _ctrl_ipd(s.PIC_329212, pic212_pv, dt, cas_sp=tic2_op)       # steam valve stroke (%)
    p_chest_e003 = steam_chest_pressure(pic212_op, s.steam.P_9)
    Q_e003_kw  = max(R324_E003_UA_KW*(tsat_steam(p_chest_e003) - s.r324_e003_T), 0.0)  # Evap-II duty (kW, F-10 floored)
    # AUDIT TD-016 — Evaporator II, same smooth-equilibrium closure as Evaporator I: the melt
    # strength follows the continuous Extended-UNIQUAC departure at 0.131 bar a, so the
    # water removed follows temperature smoothly with no min()/duty relay.  Anchored bit-exact
    # (w_eq(140,0.131) == R324_W_EV2), T-driven at the PIC-324203-controlled vacuum.
    fa203_m = R324_F003_FA_DES * (s.PIC_324203["op"] / max(R324_PV203_OP_DES, 1e-6))
    _ctrl_ipd(s.PIC_324203, s.r324_f003_P, dt)
    M_f003_pre = s.r324_f003_M
    t2_old = s.r324_e003_T
    t2_solved = t2_old
    p2_old = s.r324_f003_P
    p2_solved = p2_old
    t2_fp_residual = math.inf
    t2_fp_converged = False
    t2_fp_iterations = 0
    for t2_fp_iterations in range(1, R324_PT_LOOP_MAXIT + 1):
        Q_e003_kw = max(R324_E003_UA_KW * (tsat_steam(p_chest_e003) - t2_solved), 0.0)
        w_eq2 = evap_w_eq(t2_solved, p2_solved,
                          R324_W_EV2, R324_E003_T_SP_C, R324_F003_P_BARA)
        v2_m = clamp(feed2_m - urea2_in / max(w_eq2, 1e-6), 0.0, feed2_m)
        pwr2 = (feed2_m/3600.0 * cp_feed2 * (s.r324_e001_T - t2_solved)
                + Q_e003_kw - v2_m/3600.0 * R324_LAM_V2)
        t2_next = t2_old + pwr2 * dt / max(M_f003_pre * cp_hold2, 1e-6)
        m709_fp = (VACUUM_CONDENSERS["324E005"]["inlet_kgh"]
                   + (v2_m - R324_V2_DES) + (fa203_m - R324_F003_FA_DES))
        nc005_fp = max(584.0 - R324_F003_FA_DES + fa203_m, 0.0)
        vent005_fp = max(nc005_fp, m709_fp - VACUUM_CONDENSERS["324E005"]["condensate_kgh"])
        ejpull2_live = (R324_F003_EJPULL_DES * (s.HIC_329606 / R324_HIC9606_DES_PCT)
                        * (p2_solved / R324_F003_P_BARA))
        p2_next = clamp(p2_old
                        + R324_F003_P_KP * (vent005_fp - ejpull2_live) / 3600.0 * dt,
                        0.02, 1.0)
        t2_fp_residual = max(abs(p2_next - p2_solved), abs(t2_next - t2_solved))
        if t2_fp_residual <= R324_PT_LOOP_TOL:
            p2_solved = p2_next
            t2_solved = t2_next
            t2_fp_converged = True
            break
        p2_solved = p2_next
        t2_solved = t2_next
    s.r324_e003_T = t2_solved
    s.r324_f003_P = p2_solved
    w_eq2 = evap_w_eq(s.r324_e003_T, s.r324_f003_P,
                      R324_W_EV2, R324_E003_T_SP_C, R324_F003_P_BARA)
    v2_m = clamp(feed2_m - urea2_in / max(w_eq2, 1e-6), 0.0, feed2_m)
    Q_e003_kw = max(R324_E003_UA_KW * (tsat_steam(p_chest_e003) - s.r324_e003_T), 0.0)
    # Reverse-pass utility handshake: actual 324E003 condensation demand reaches 329D009 next tick.
    s.steam.m_users9 = max(R324_9BAR_OTHER_DES + Q_e003_kw / R324_E003_LAM_STEAM, 0.0)
    _DIAG["E003"] = {
        "weq": w_eq2, "v": v2_m, "Q": Q_e003_kw,
        "T": s.r324_e003_T, "feed": feed2_m, "urea_in": urea2_in,
        "thermo_model": extended_uniquac.MODEL_NAME,
        "thermo_validity": extended_uniquac.validity_status(
            s.r324_e003_T + 273.15, s.r324_f003_P
        ),
        "thermo_px_residual_bara": extended_uniquac.px_equilibrium_residual(
            w_eq2, s.r324_e003_T + 273.15, s.r324_f003_P
        ),
        "iteration_count": t2_fp_iterations,
        "iteration_residual": t2_fp_residual,
        "converged": t2_fp_converged,
    }
    p2_gen     = max(feed2_m - v2_m, 0.0)                                     # Stage-2 melt produced (kg/h)
    w2_live    = clamp(urea2_in / max(p2_gen, 1e-6), 0.0, 1.0)                # LIVE final-product urea mass frac
    # LIC-324501 routed melt drain. Pump discharge is raw 402G. Route A enables UF85 stream 697
    # and sends conservative mixed stream 609 to Unit 335; route B interlocks UF85 off and sends
    # raw 402G to 323D002. The selector is exclusive, while 324F003 loses only its raw-melt part.
    lvl_f003   = clamp(s.r324_f003_M / R324_F003_M_FULL * 100.0, 0.0, 100.0)
    lic501_op  = _ctrl_ipd(s.LIC_324501, lvl_f003, dt)
    routed_op  = clamp(lic501_op, 0.0, 100.0)
    # G12 (approved operability): LV-324501A level-controls the drain and exports melt to BL;
    # LV-324501B is a NORMALLY-CLOSED overpressure relief that opens only when the 335 melt-header
    # PIC-335201 exceeds R335_LVB_RELIEF_BARG, diverting the melt to 323D002. UF85 injection is a
    # granulation (335) function and is deferred until that section is simulated, so the live path
    # carries no UF85 (uf_ratio = 0) and the forward export is the raw urea melt.
    recycle_selected = s.PIC_335201 > R335_LVB_RELIEF_BARG                    # LV-324501B relief trip
    lva_stroke = 0.0 if recycle_selected else routed_op
    lvb_stroke = routed_op if recycle_selected else 0.0
    m_402g     = routed_op/100.0 * R324_LVA_SPAN                              # melt drain from 324F003 (kg/h)
    uf_cascade = step_uf85_cascade(s, m_402g, True, dt)                       # UF85 deferred (granulation off) -> 0
    route501   = route_lv324501(m_402g, s.w_e003, s.r324_e003_T,
                                recycle_selected, uf_ratio=0.0)              # raw melt to BL / recycle, no UF85
    m_fwd      = route501["forward_kgh"]                                      # mixed 609 -> 335 on A
    m_recyc    = route501["recycle_kgh"]                                      # raw 402G -> 323D002 on B
    m_f003_out = m_402g                                                        # UF85 is external to 324F003
    s.r324_f003_M = max(M_f003_pre + (feed2_m - v2_m - m_f003_out)/3600.0*dt, 1.0)
    y_v2       = sol_vapour_y(s.w_e003, SOL_E003["alpha"])          # AUDIT F-8: Stage-2 species
    xi_e003    = sol_biuret_xi("E003", M_f003_pre, s.w_e003, s.r324_e003_T)
    s.w_e003   = sol_pin_strength(
        sol_advance(s.w_e003, M_f003_pre, s.r324_f003_M, feed2_m, s.w_e001,
                    v2_m, y_v2, m_f003_out, xi_e003, dt), w2_live)
    # vacuum: PIC-324203 deep-vacuum false-air bleed vs the 324F004/F005 ejector pull.  Mapping — the
    # pull is set by HV-329606 motive steam (HIC-329606): opening it harder drops 324F003 and the
    # 324E005 shell pressure.  Anchored: at design HIC-329606 == 50 % -> the pull == EJPULL_DES, so
    # the ODE is bit-identical at the seed.  (PIC-324203 trims 324F003 to SP in AUTO; the sign shows
    # directly with the loop in MAN.)
    # AUDIT C5 — same open-integrator defect and same anchored roll-off as the Stage-1 pull above.

    # ---- UF85 ratio injection (FFIC-335406 ratio station -> FIC-335405 flow) ------
    #  Physical mixing is already closed in route501 above. Datasheet-3 section 5.2 requires
    #  zero additive on B; therefore m_uf is part of forward stream 609, never recycle 402G.
    m_uf       = route501["uf85_kgh"]
    m_product  = m_fwd                                                        # stream 609 total -> 335

    # ---- four-condenser vacuum train ----------------------------------------------
    #  Each exchanger is an explicit mass/energy node with Q=UA*LMTD, a cooling-water
    #  branch, condensate return to 328D003 Comp I, and noncondensable derating.  The
    #  intervening ejectors are conservative mixing nodes on strict PFD anchors.
    motive_ratio_606 = max(s.HIC_329606 / R324_HIC9606_DES_PCT, 0.0)
    mot927_m = R324_F004_MOTIVE_DES * motive_ratio_606
    mot929_m = R324_F005_MOTIVE_DES * motive_ratio_606
    _vac_evap_in.set_state(mass_flow=m_evap)
    _vac_v1_in.set_state(mass_flow=v1_m)
    _vac_v2_in.set_state(mass_flow=v2_m)
    _vac_fa1_in.set_state(mass_flow=fa202_m)
    _vac_fa2_in.set_state(mass_flow=fa203_m)
    _vac_mot924_in.set_state(mass_flow=mot9605_m)
    _vac_mot927_in.set_state(mass_flow=mot927_m)
    _vac_mot929_in.set_state(mass_flow=mot929_m)
    _vac_unit.solve()
    vac324 = _vac_unit.diagnostics
    vac_stream = vac324["streams_kgh"]
    m_324_cond = vac_stream["719"] + vac_stream["720"] + vac_stream["721"] + vac_stream["759"]
    m_324_vent = vac_stream["722"]
    for _sid in ("719", "720", "721", "759", "708"):
        s.tlag["R324_" + _sid] = vac_stream[_sid]
    s.tlag["R324_COND"] = m_324_cond  # retained aggregate for backward-compatible diagnostics
    # ---- recycle tear write (one-tick delay -> next step reads it) ---------------
    s.tlag["R324_recyc"]   = m_recyc
    s.tlag["R324_recyc_w"] = route501["recycle_comp"]["Urea"]
    s.tlag["R324_recyc_T"] = route501["recycle_T_C"]
    s.tlag["R324_recyc_comp"] = dict(route501["recycle_comp"])

    # ----- auxiliary faceplate trims (stepped for liveness; off the network)
    #   FIC-328405 / LIC-323503 dropped from here: both now step on the live 718A/718B/323D011 network.
    # (TIC-328008 is stepped earlier, immediately before its FIC-328404 slave -- see TD-004.
    #  Stepping it a second time here would advance the controller twice per tick.)
    # AUDIT C32 — the differential PV subtracted the module constant R328_C003_T746, so only the
    # TT-328013 leg was live: a 328E021 fouling change or a 328C002 bottoms excursion moved the true
    # dT and left the PV flat, i.e. TIC-328012 could not see the upset it exists to detect.  T_746 is
    # the live 328E021 cold outlet already published as TT-328009; at design it is 190.0 exactly.
    _ctrl_ipd(s.TIC_328012, s.a328_c003_T - T_746, dt)                       # differential PV: TT-328013 (bottom) - TT-328012 (3rd tray)
    _ctrl_ipd(s.SIC_323902, s.SIC_323902["op"], dt)
    # (FIC-328406 is now stepped by its own _fic_flow call on the 741 recycle -- see TD-005.
    #  It used to be advanced here with its OWN opening as the PV, which made pv a percentage
    #  that the telemetry then divided by a density.  Stepping it again would double-advance it.)

    # ----- Trips (P1-2 stateful interlocks) -----
    # Live initiator conditions (instantaneous). 21_2 = Urea-Synthesis main trip; its initiators
    #   per the trip schedule include loss of NH3 supply head (tank empty here) and the
    #   pressure-vs-saturation margin PDYI321203/204 < 0.1 bar (cavitation guard).  21_8/21_10 =
    #   per-pump mechanical equipment-fault trips (PI 321211/321221 abstraction); armed only while
    #   the pump runs (a stopped pump cannot be faulted into a trip -> would otherwise self-latch).
    s.trips["21_2"]  = (s.tank_level_frac < 0.05) or (PDY_A < 0.1) or (PDY_B < 0.1)
    s.trips["21_8"]  = s.pumpA["on"] and s.pumpA["fault"]
    s.trips["21_10"] = s.pumpB["on"] and s.pumpB["fault"]
    # 21_4 = Loss-of-CO2-feed -> NH3 main interlock (Stamicarbon feed-ratio safeguard): a sustained loss
    #   of CO2 to 322E001 runs the reactor N/C away -> trip the NH3 feed to arrest it (the missing
    #   CO2->NH3 domino link).  Live RESET-BLOCK condition = low CO2 feed alone (cannot reset while CO2
    #   still lost).  The LATCH is ARMED only while synthesis is actually running (>=1 HP-NH3 pump on +
    #   NH3 shut-off XV-322901 open) so an idle / black-start plant valved out of CO2 does NOT self-latch.
    #   CO2 is full at design (XV-322902 open) -> condition False -> design steady state stays bit-exact.
    co2_lost_21_4   = s.F_CO2_th < 0.05 * (CO2_DES_KGH / 1000.0)     # < 5% design CO2 (== L3-3 ratio gate)
    syn_running_214 = disch_open and (s.pumpA["on"] or s.pumpB["on"])
    s.trips["21_4"] = co2_lost_21_4
    if co2_lost_21_4 and syn_running_214:
        s.trip_latched["21_4"] = True
    # Latch on any live condition; the latch holds until trip_reset (operator) clears it.
    for _tk in ("21_2", "21_8", "21_10"):
        if s.trips[_tk]:
            s.trip_latched[_tk] = True
    # Enforce latched actions. 21_2 main trip -> STOP both HP-NH3 pumps, close NH3 quick-closing
    #   XV-321901 + NH3 shut-off XV-322901, drive SIC-321950/951 to min speed (MAN, 0 %).
    if s.trip_latched["21_2"]:
        s.pumpA["on"] = False
        s.pumpB["on"] = False
        s.XV_321901   = False
        s.XV_322901   = False
        s.SIC_321950.set_mode("MAN"); s.SIC_321950.set_op(0.0)
        s.SIC_321951.set_mode("MAN"); s.SIC_321951.set_op(0.0)
    # 21_4 loss-of-CO2 trip -> cut the NH3 feed (mirror the 21_2 NH3 action): STOP both HP-NH3 pumps,
    #   force SIC-321950/951 to MAN 0 (overrides a hand-held MAN pump).  Ejector motive -> 0 via the
    #   TRIPPED PUMPS (motive_nh3 prop. pump flow), so the HPCC/reactor-feed cascade still collapses
    #   without slamming the valve.  XV-322901 is deliberately NOT force-closed here: the operator
    #   keeps manual control of the NH3 shut-off XV while latched (it opens with NO flow until the
    #   pumps are restarted).  The more severe 21_2 main trip still closes XV-322901.
    if s.trip_latched["21_4"]:
        s.pumpA["on"] = False
        s.pumpB["on"] = False
        s.SIC_321950.set_mode("MAN"); s.SIC_321950.set_op(0.0)
        s.SIC_321951.set_mode("MAN"); s.SIC_321951.set_op(0.0)
    if s.trip_latched["21_8"]:
        s.pumpA["on"] = False    # Trip 21.8: stop HP-NH3 pump 321P002A
    if s.trip_latched["21_10"]:
        s.pumpB["on"] = False    # Trip 21.10: stop HP-NH3 pump 321P002B

    # ----- Trip 22.1 (LP absorber 322C001 over-temperature steam-flood) -----
    #   TT-322015 > 57 C latches the steam-flood valve XV-322915 OPEN to inert/quench the
    #   absorber off-gas space.  Hysteretic self-clear once the bed cools below 55 C returns
    #   manual control of XV-322915 to the operator (no dedicated reset control on the overlay).
    #   The flood duty Q_FLOOD = A328_QFLOOD_KW is consumed one tick later in stage-7 physics
    #   (the flood valve is read at the top of the step).  At design Tc001 ~ 43 C the condition
    #   is False -> XV shut, Q_FLOOD = 0 -> steady state stays bit-exact.
    s.trips["22_1"] = s.a328_c001_T > 57.0
    if s.trips["22_1"]:
        s.trip_latched["22_1"] = True
    elif s.a328_c001_T < 55.0:
        s.trip_latched["22_1"] = False
    if s.trip_latched["22_1"]:
        s.XV_322915 = True

    # Discharge header
    # Discharge header: affinity-law developed head droops with motive (pump-speed) fraction.
    #   P = P_idle + (P_design - P_idle)·phi_m^2 ;  == 164.0 at design (phi_m=1), 7.5 idle (phi_m=0).
    P_disch_header_barG = (7.5 + ((P_SYN_DOWN_BAR - 1.0) - 7.5) * phi_fwd) \
        if (s.pumpA["on"] or s.pumpB["on"]) else 7.5

    # ---- uniform process-stream registry (clickable stream inspector) ----
    MW_NH3 = MW_COMP["NH3"]
    streams = {
        "NH3_FEED": make_stream(
            {"NH3": F_pump_total_th * 1000.0 / MW_NH3}, s.tank_T_C, s.tank_P_top_barG + 1.0,
            "NH3 ex 309E005", "309E005", "321D003", "liquid", rho=NH3_RHO),
        "PUMP_SUCT": make_stream(
            {"NH3": F_pump_total_th * 1000.0 / MW_NH3}, s.tank_T_C, PT_A + 1.0,
            "NH3 pump suction header", "321D003", "321P002 A/B", "liquid", rho=NH3_RHO),
        "HP_DISCH": make_stream(
            {"NH3": motive_nh3_kgh / MW_NH3}, TI_321020, P_SYN_DOWN_BAR,
            "HP NH3 discharge (motive)", "321P002 A/B", "322F001", "liquid", rho=NH3_RHO),
        "CARB_RECYCLE": make_stream(
            scrub["overflow_kmolh"], scrub["T_overflow"], scrub["P_overflow"],
            "Carbamate recycle (322E003 overflow)", "322E003", "322F001", "liquid"),
        "EJ_DISCH": make_stream(
            {k: ej["comp"][k] / MW_COMP[k] for k in MW_COMP}, ej["T_C"], ej["P_bara"],
            "Ejector discharge (carbamate liq.)", "322F001", "322E002", "liquid", rho=ej["rho"]),
        "CO2_FEED": make_stream(
            strip["co2_feed_kmolh"], CO2_T_FEED_C, P_line_bara,
            "CO2 feed gas", "320K002", "322E001", "gas"),
        "STRIP_TOP": make_stream(
            strip["top_kmolh"], strip["T_top"], P_strip_live,
            "Stripper top gas", "322E001", "322E002", "gas"),
        "STRIP_BOT": make_stream(
            strip["bot_kmolh"], strip["T_bot"], P_strip_live,
            "Stripper bottom solution", "322E001", "LV-322501", "liquid"),
        "HPCC_PROD": make_stream(
            hpcc["feed_kmolh"], hpcc["T_prod"], d_HPCC_P,
            "HPCC two-phase product", "322E002", "322R001", "two-phase"),
        "HPCC_STEAM": make_stream(
            {"H2O": hpcc["steam_kgh"] / MW_COMP["H2O"]}, HPCC_STEAM_TSAT_C, HPCC_STEAM_P_BARA,
            "LP steam (shell side)", "322E002 shell", "LP header", "vapor"),
        "HPCC_COND": make_stream(
            {"H2O": hpcc["steam_kgh"] / MW_COMP["H2O"]}, HPCC_STEAM_TSAT_C, HPCC_STEAM_P_BARA,
            "BFW/condensate feed", "322D001 A/B", "322E002 shell", "liquid"),
        "REACT_OVERFLOW": make_stream(
            react["overflow_kmolh"], react["T_overflow"], react["P_bara"],
            "Reactor overflow (urea soln.)", "322R001", "322E001", "liquid",
            rho=REACT_OVERFLOW_RHO),
        "REACT_OFFGAS": make_stream(
            react["offgas_kmolh"], react["T_offgas"], react["P_offgas"],
            "Reactor off-gas", "322R001", "322E003", "vapor",
            rho=REACT_OFFGAS_RHO),
        "SCRUB_OFFGAS": make_stream(
            scrub["offgas_kmolh"], scrub["T_offgas"], scrub["P_offgas"],
            "HP scrubber off-gas (to HV-322604)", "322E003", "HV-322604", "vapor",
            rho=SCRUB_OFFGAS_RHO),
        "SCRUB_OFFGAS_LP": make_stream(
            hv604["comp_kmolh"], hv604["T_out"], hv604["P_out"],
            "HP scrubber off-gas (LP, JT-cooled)", "HV-322604", "322C001", "vapor"),
        "CCW_SUPPLY": make_stream(
            {"H2O": m_ccw_kgh / MW_COMP["H2O"]}, tic["pv"], SCRUB_CCW_P_IN_BARA,
            "CCW supply (shell side, cold)", "329P006 A/B", "322E003", "liquid",
            rho=SCRUB_CCW_RHO_IN),
        "CCW_RETURN": make_stream(
            {"H2O": m_ccw_kgh / MW_COMP["H2O"]}, scrub["t_ccw_out"], SCRUB_CCW_P_OUT_BARA,
            "CCW return (shell side, warm)", "322E003", "329P006 A/B", "liquid",
            rho=SCRUB_CCW_RHO_OUT),
    }

    # Numbered aliases from the supplied absorber/cooling-water maps.  PFD component rows are
    # independently rounded, so make_stream_mass_pct normalizes each row to the live total.
    mapped_m702 = 440.0 + (m_v011 - R3232_E011_MV_DES)
    mapped_m341 = m_341
    mapped_m343 = bot_c005
    streams.update({
        "S0204": make_stream(hv604["comp_kmolh"], hv604["T_out"], hv604["P_out"],
                              "204 HP off-gas", "HV-322604", "322C001", "vapor"),
        "S0341": make_stream_mass_pct(mapped_m341, PFD_324_MASS_PCT["341"], 43.0, 1.0,
                                       "341 absorber vent", "323C005", "328V001", "vapor"),
        "S0343": make_stream_mass_pct(mapped_m343, PFD_324_MASS_PCT["343"], 56.0, 1.0,
                                       "343 ammonia water", "323C005", "328D003 Comp II", "liquid", rho=992.2),
        "S0702": make_stream_mass_pct(mapped_m702, PFD_324_MASS_PCT["702"], 45.0, 1.0,
                                       "702 flash-condenser gas", "323D011", "323C005", "vapor"),
        "S0703": make_stream_mass_pct(vac_stream["703"], PFD_324_MASS_PCT["703"], 116.0, 0.3,
                                       "703 condenser-I inlet", "705 + 790", "324E002", "vapor"),
        "S0705": make_stream_mass_pct(vac_stream["705"], PFD_324_MASS_PCT["705"], 130.0, 0.3,
                                       "705 evaporator-I vapor", "324F001", "324E002", "vapor"),
        "S0706": make_stream_mass_pct(vac_stream["706"], PFD_324_MASS_PCT["706"], 45.0, 0.3,
                                       "706 condenser-I gas", "324E002", "324F002", "vapor"),
        "S0708": make_stream_mass_pct(vac_stream["708"], PFD_324_MASS_PCT["708"], 121.0, 1.0,
                                       "708 ejector-I discharge", "324F002", "323C005", "vapor"),
        "S0709": make_stream_mass_pct(vac_stream["709"], PFD_324_MASS_PCT["709"], 140.0, 0.1,
                                       "709 condenser-II inlet", "324F003", "324E005", "vapor"),
        "S0712": make_stream_mass_pct(vac_stream["712"], PFD_324_MASS_PCT["712"], 40.0, 0.1,
                                       "712 condenser-II gas", "324E005", "324F004", "vapor"),
        "S0714": make_stream_mass_pct(vac_stream["714"], PFD_324_MASS_PCT["714"], 104.0, 0.3,
                                       "714 ejector-II discharge", "324F004", "324E006", "vapor"),
        "S0715": make_stream_mass_pct(vac_stream["715"], PFD_324_MASS_PCT["715"], 41.0, 0.3,
                                       "715 condenser-III gas", "324E006", "324F005", "vapor"),
        "S0717": make_stream_mass_pct(vac_stream["717"], PFD_324_MASS_PCT["717"], 120.0, 1.0,
                                       "717 ejector-III discharge", "324F005", "324E007", "vapor"),
        "S0719": make_stream_mass_pct(vac_stream["719"], PFD_324_MASS_PCT["719"], 45.0, 0.3,
                                       "719 condenser-I condensate", "324E002", "328D003 Comp I", "liquid", rho=999.1),
        "S0720": make_stream_mass_pct(vac_stream["720"], PFD_324_MASS_PCT["720"], 40.0, 0.1,
                                       "720 condenser-II condensate", "324E005", "328D003 Comp I", "liquid", rho=1014.0),
        "S0721": make_stream_mass_pct(vac_stream["721"], PFD_324_MASS_PCT["721"], 41.0, 0.3,
                                       "721 condenser-III condensate", "324E006", "328D003 Comp I", "liquid", rho=1036.0),
        "S0722": make_stream_mass_pct(vac_stream["722"], PFD_324_MASS_PCT["722"], 55.0, 1.0,
                                       "722 final vacuum vent", "324E007", "atmosphere", "vapor"),
        "S0744": make_stream_mass_pct(m_744, PFD_324_MASS_PCT["744"], 44.0, 1.0,
                                       "744 absorber-pump suction", "328D003 Comp I", "322P002", "liquid", rho=1002.0),
        "S0755": make_stream_mass_pct(m_755, PFD_324_MASS_PCT["755"], 40.0, 3.9,
                                       "755 cooled absorber feed", "322E006", "322C001", "liquid", rho=1005.0),
        "S0756": make_stream_mass_pct(m_756, PFD_324_MASS_PCT["756"], 43.0, 3.9,
                                       "756 LP-absorber solution", "322C001", "323C005", "liquid", rho=1003.0),
        "S0759": make_stream_mass_pct(vac_stream["759"], PFD_324_MASS_PCT["759"], 55.0, 1.0,
                                       "759 condenser-IV condensate", "324E007", "328D003 Comp I", "liquid", rho=989.1),
        "S0783": make_stream_mass_pct(fa203_m, PFD_324_MASS_PCT["783"], 32.0, 1.0,
                                       "783 stage-II false air", "atmosphere", "PV-324203", "vapor"),
        "S0784": make_stream_mass_pct(fa202_m, PFD_324_MASS_PCT["784"], 32.0, 1.0,
                                       "784 stage-I false air", "atmosphere", "PV-324202", "vapor"),
        "S0797": make_stream_mass_pct(R3232_M797_DES, PFD_324_MASS_PCT["797"], 46.0, 3.9,
                                       "797 LP-absorber vent", "322C001", "PV-322201", "vapor"),
        "S0924": make_stream({"H2O": vac_stream["924"] / MW_COMP["H2O"]}, 146.0, 4.1,
                              "924 ejector motive", "LP steam", "324F002", "vapor"),
        "S0927": make_stream({"H2O": vac_stream["927"] / MW_COMP["H2O"]}, 146.0, 4.1,
                              "927 ejector motive", "LP steam", "324F004", "vapor"),
        "S0929": make_stream({"H2O": vac_stream["929"] / MW_COMP["H2O"]}, 146.0, 4.1,
                              "929 ejector motive", "LP steam", "324F005", "vapor"),
        "S0954": make_stream({"H2O": s.cpl_flow_kgh / MW_COMP["H2O"]}, 46.0, 12.0,
                              "954 process condensate", "process-condensate header", "322C001", "liquid", rho=990.32),
    })
    for _tag, _supply, _return in (
        ("324E002", "1014", "1015"), ("324E005", "1016", "1017"),
        ("324E006", "1018", "1019"), ("324E007", "1020", "1021"),
    ):
        _node = vac324["nodes"][_tag]
        streams["S" + _supply] = make_stream(
            {"H2O": _node["cw_flow_kgh"] / MW_COMP["H2O"]}, _node["cw_in_c"], 3.6,
            _supply + " cooling-water supply", "1001 header", _tag, "liquid")
        streams["S" + _return] = make_stream(
            {"H2O": _node["cw_flow_kgh"] / MW_COMP["H2O"]}, _node["cw_out_c"], 2.2,
            _return + " cooling-water return", _tag, "1051 header", "liquid")
    streams["S1001"] = make_stream({"H2O": 4_847_000.0 / MW_COMP["H2O"]}, 30.0, 4.7,
                                    "1001 main CW supply", "cooling towers", "CW consumers", "liquid")
    streams["S1051"] = make_stream({"H2O": 4_865_000.0 / MW_COMP["H2O"]}, 39.0, 2.2,
                                    "1051 main CW return", "CW consumers", "cooling towers", "liquid")

    # AI-328701 process-condensate conductivity soft sensor (stream 740, read-only)
    _nh3_740, _urea_740 = ppm_infer_328701(s.a328_c004_T, s.a328_c003_T)
    _ai701_uS = cond_infer_328701(_nh3_740, _urea_740, 0.0)                  # CO2 fully co-stripped with NH3
    _d003_levels = d003_level_telemetry(s)

    # Dynamic sequential-modular tear audit.  These recycle signals cross real vessel/line
    # inventories and therefore advance once per integration tick rather than being iterated to an
    # algebraic steady state.  Report their normalized closure explicitly so steady-state callers
    # can detect convergence and dynamic callers can distinguish transport lag from solver failure.
    _tear_pairs = {
        "328C003_overhead_748": (m748_prev, m_748),
        "328C004_overhead_750": (m750_prev, m_750),
        "328D001_reflux_775": (m775_prev, m_775),
        "323D011_return_718A": (m718A_prev, m_718A),
        "328C004_steam_931": (m931_prev, m_931),
    }
    _tear_resid = {
        key: abs(new - old) / max(abs(new), abs(old), 1.0)
        for key, (old, new) in _tear_pairs.items()
    }
    _tear_tol = 1.0e-6
    _tear_norm = max(_tear_resid.values(), default=0.0)

    return {
        "t":           time.time(),      # desktop clock (epoch s)
        "t_sim":       s.sim_t,          # plant clock (s since program init); trend X axis
        "RECYCLE_TEAR_RESIDUAL": {
            "method": "observed_dynamic_transport_tears",
            "is_solver_convergence": False,
            "tolerance": _tear_tol,
            "max_relative_residual": _tear_norm,
            "settled": _tear_norm <= _tear_tol,
            "residuals": _tear_resid,
        },
        "sm_diagnostics": {
            "hpcc": locals().get("hpcc", {}),
            "ej": locals().get("ej", {}),
            "react": locals().get("react", {}),
            "hv604": locals().get("hv604", {}),
            "vac324": locals().get("vac324", {}),
        },
        # G7: every recycle in the flowsheet is explicitly one of two kinds. ALGEBRAIC loops (the 324
        # vacuum P/T tears, no inter-stage holdup within a tick) are iterated to a declared residual by
        # a bounded Picard fixed-point each tick; DYNAMIC loops (328/synthesis tears crossing real
        # vessel/line inventories) advance once per tick as transport lag and report residence, not
        # convergence. This block classifies both so steady-state callers can read the algebraic
        # convergence and dynamic callers can distinguish transport lag from solver failure.
        "RECYCLE_CLASSIFICATION": {
            "algebraic_inner_solves": {
                "method": "bounded_picard_fixed_point",
                "is_solver_convergence": True,
                "tolerance": R324_PT_LOOP_TOL,
                "max_iterations": R324_PT_LOOP_MAXIT,
                "fallback": "last_iterate",
                "loops": {
                    tag: {
                        "iterations": _DIAG.get(tag, {}).get("iteration_count"),
                        "residual": _DIAG.get(tag, {}).get("iteration_residual"),
                        "converged": _DIAG.get(tag, {}).get("converged"),
                    }
                    for tag in ("E001", "E003")
                },
                "all_converged": all(_DIAG.get(tag, {}).get("converged", False)
                                     for tag in ("E001", "E003")),
            },
            "dynamic_transport_tears": {
                "method": "observed_dynamic_transport_tears",
                "is_solver_convergence": False,
                "tolerance": _tear_tol,
                "max_relative_residual": _tear_norm,
                "settled": _tear_norm <= _tear_tol,
                "loops": list(_tear_pairs.keys()),
            },
        },
        "FI_321401":   round(F_pump_total_th, 2),   # FT-321401 live discharge flow
        "TI_top1":     round(s.tank_T_C, 1),         # TT-321001 tank temp (left)
        # F6: TT-321002 de-aliased — top-right thermowell reads a level-dependent stratification
        #     offset below TT-321001 (empties -> larger vapour-space gradient); tracks both live
        #     tank_T_C and tank_level_frac so boundary disturbances still ripple through.
        "TI_top2":     round(s.tank_T_C - 0.8 * (1.0 - s.tank_level_frac), 1),  # TT-321002 (right)
        "LSL_321501":  (s.tank_level_frac < 0.15),   # low-level switch (active=LO)
        "PI_top1":     round(s.tank_P_top_barG, 1),
        "PI_top2":     round(s.tank_P_top_barG, 1),
        "PI_header":   round(7.3 * phi_fwd, 1),      # F6: PI-321003 feed-header P de-pinned — affinity-law w/ pump motive (phi_fwd^=1 at design -> 7.3)
        "LI_321501":   round(s.tank_level_frac * 100.0, 1),
        "totalizer":   round(s.totalizer_t, 2),
        "XV_321901":   bool(s.XV_321901),
        "XV_322901":   bool(s.XV_322901),
        "PI_321201":   round(PT_A, 1),          # PT-321201 feed pressure (bar g = 321D003)
        "PI_321202":   round(PT_B, 1),          # PT-321202 feed pressure (bar g = 321D003)
        "PI_321201_alarm": bool(s.pumpA["fault"]),  # PI-321211 equipment-fault pre-alarm (lube abstraction)
        "PI_321202_alarm": bool(s.pumpB["fault"]),  # PI-321221 equipment-fault pre-alarm (lube abstraction)
        "PY_321201":   round(PY, 2),            # NH3 sat vapour P (bar a)
        "PY_321202":   round(PY, 2),
        "PDY_321203":  round(PDY_A, 2),         # sub-cooling margin (bar)
        "PDY_321204":  round(PDY_B, 2),
        "PDY_321203_alarm": PDY_A <= 0.0,
        "PDY_321204_alarm": PDY_B <= 0.0,
        "pumpA": {
            "on":      s.pumpA["on"],
            "speed":   round(s.pumpA["speed_act"], 1),
            "current": round(s.pumpA["current"], 1),
            "mode":    s.pumpA["mode"],
        },
        "pumpB": {
            "on":      s.pumpB["on"],
            "speed":   round(s.pumpB["speed_act"], 1),
            "current": round(s.pumpB["current"], 1),
            "mode":    s.pumpB["mode"],
        },
        "PI_disch": round(P_disch_header_barG if (s.pumpA["on"] or s.pumpB["on"]) else 7.5, 1),
        "TI_321020": round(TI_321020, 1),       # common discharge temperature
        "EJ_322F001": {                          # HP ejector discharge -> 322E002 (TT-322012)
            "motive_kgh":  round(motive_nh3_kgh, 1),
            "suction_kgh": round(ej["suction_kgh"], 1),
            "HIC_322602":  round(s.HIC_322602, 1),   # HV-322602 spindle opening (%)
            "mu":          round(ej["mu"], 4),       # entrainment ratio m_suc/m_motive
            "TT_322012":   round(d_TT322012, 1),     # discharge temp (C) -> 322E002 HPCC (lagged)
            "PI_disch":    round(ej["P_bara"], 1),   # discharge pressure (bar a)
            "TI_322002":   round(d_TT322002, 1), # TT-322002 = 322E003 overflow temp (C, lagged)
            "PI_329201":   round(scrub["P_overflow"], 1), # PT-329201 = 322E003 overflow line P (bar a, live)
            "total_kgh":   round(ej["total_kgh"], 1),
            "total_th":    round(ej["total_kgh"]/1000.0, 2),
            "mol_kmolh":   round(ej["mol_kmolh"], 2),
            "MW":          round(ej["MW"], 2),
            "rho":         round(ej["rho"], 1),
            "vol_m3h":     round(ej["vol_m3h"], 2),
            "comp_pct":    {k: (round(ej["comp"][k]/ej["total_kgh"]*100.0, 3)
                                if ej["total_kgh"] > 0 else 0.0) for k in MW_COMP},
        },
        "CO2_FEED": {                            # 320K002 -> XV-322902 -> 322E001 feed line
            "FT_322403":  round(FT_322403, 0),       # CO2 feed (Nm3/h)
            "FY_322403":  round(FY_322403, 2),       # CO2 feed (t/h, total stream)
            "TI_322017":  round(CO2_T_FEED_C, 1),    # CO2 feed temperature (C)
            "pure_th":    round(s.F_CO2_th * CO2_MASSFRAC_CO2, 2),  # t/h pure CO2 component
            "raw_th":     round(s.F_CO2_raw_th, 2),  # t/h raw from 320K002 (pre-vent)
            "vent_th":    round(s.F_CO2_vent_th, 2), # t/h CO2 diverted out PV-322203
            "Load":       round(Load_pct, 1),        # plant Load (% of design CO2 flow)
            "XV_322902":  bool(s.XV_322902),         # CO2 isolation to 322E001 (True=OPEN)
            "PV_322203":  round(pv_open, 1),         # vent valve opening (%)
            "HIC_322203": round(s.HIC_322203, 1),    # PV-322203 minimum opening (%)
            "PIC_322203": round(pic["pv"], 1),       # CO2 line pressure (bar a)
            "PIC_op":     round(pic["op"], 1),       # PIC-322203 output (vent demand %)
            "PIC_sp":     round(pic["sp"], 1),       # PIC-322203 setpoint (bar a)
            "PIC_mode":   pic["mode"],
        },
        "STRIP_322E001": {                       # HP Stripper 322E001 feeds -> products
            "TT_322014":   round(s.react_T_overflow, 1),  # 322R001 overflow feed temp (C, live cascade lip)
            "TT_322013":   round(d_TT322013, 1),      # top gas -> 322E002 (C, lagged)
            "TT_322004":   round(d_TT322004, 1),      # bottom soln -> LV-322501, pre-flash (C, lagged)
            "TT_323001":   round(d_TT323001, 1),          # post-LV flash -> 323C003 (C, lagged)
            "top_th":      round(strip["top_th"], 2),     # top gas (t/h)
            "top_MW":      round(strip["top_MW"], 2),
            "top_mol_pct": {k: round(strip["top_comp_pct"][k], 3) for k in MW_COMP},
            "bot_th":      round(strip["bot_th"], 2),     # bottom solution (t/h)
            "bot_MW":      round(strip["bot_MW"], 2),
            "bot_mass_pct":{k: round(strip["bot_mass_pct"][k], 3) for k in MW_COMP},
            "xi_hyd":      round(strip["xi_hyd"], 2),     # urea hydrolysis extent (kmol/h)
            "xi_biu":      round(strip["xi_biu"], 3),     # biuret formation extent (Arrhenius, kmol/h)
            "eta_T":       round(strip["eta_T"], 4),      # strip efficiency (steam x N/C x H/C penalty)
            "g_NC":        round(strip["g_NC"], 4),       # feed-N/C penalty factor (1.0 = no penalty)
            "g_HC":        round(strip["g_HC"], 4),       # feed-H/C penalty factor (1.0 = no penalty)
            "L_strip":     round(strip["L_strip"], 4),    # live stripper-feed N/C
            "W_strip":     round(strip["W_strip"], 4),    # live stripper-feed H/C
            "LI_322501":   round(s.strip_level, 1),       # LT-322501 bottom-sump level (%)
            "LV_322501":   round(lv_open, 1),             # LV-322501 opening (%)
            "drain_th":    round(drain_kgh / 1000.0, 2),  # bottom drain -> 323C003 (t/h)
            "LIC_322501": {
                "pv":   round(lic["pv"], 1),
                "sp":   round(lic["sp"], 1),
                "op":   round(lic["op"], 1),
                "mode": lic["mode"],
            },
            "steam": {                            # shell side: 329D005 MP steam (live MP header)
                "TI_shell": round(strip["T_steam"], 1),      # live sat-steam condensing temp (C)
                "P_bara":   round(s.steam.P_MP, 1),          # live MP header pressure (bar a)
                "kgh":      round(m_strip * 3600.0, 0),      # LIVE MP steam flow (kg/h), tracks load (G8)
                "duty_kW":  round(Q_strip_kjh / 3600.0, 0),  # LIVE strip duty (kW) = DES * feed-load ratio
            },
        },
        "RECIRC_323": {                          # Unit 323 - LP Recirculation & Pre-Evaporation
            "C003": {                            # Rectifying Column 323C003 + Recirc Heater 323E002
                "TT_323002":  round(s.r323_c003_T - (R323_C003_T_SP_C - R323_C003_T313_C), 1),  # stream 313 sump (PFD-20 121C = 314 drain 135 - reboiler rise)
                "P_bara":     round(s.r323_c003_P, 2),                       # PT-323201 column pressure (bar a, dynamic)
                "LI_323501":  round(s.r323_c003_M / R323_C003_M_FULL * 100.0, 1),  # level (%)
                "feed_th":    round(m_feed_323 / 1000.0, 2),                 # feed from 322E001 (t/h)
                "feed_T":     round(T_feed_323, 1),                          # feed temp (C, TT-323001)
                "v305_th":    round(m_305 / 1000.0, 2),                      # top vapor -> LPCC (t/h)
                "drain314_th":round(m_314 / 1000.0, 2),                      # bottom drain -> flash (t/h)
                "Q_kW":       round(Q_e002_kw, 0),                           # heater 323E002 duty (kW)
                "TIC_323007": {"pv": round(s.TIC_323007["pv"], 1), "sp": round(s.TIC_323007["sp"], 1),
                               "op": round(s.TIC_323007["op"], 2), "mode": s.TIC_323007["mode"]},
                "PIC_329202": {"pv": round(s.PIC_329202["pv"], 2), "sp": round(s.PIC_329202["sp"], 2),
                               "op": round(s.PIC_329202["op"], 1), "mode": s.PIC_329202["mode"]},
                "LIC_323501": {"pv": round(s.LIC_323501["pv"], 1), "sp": round(s.LIC_323501["sp"], 1),
                               "op": round(s.LIC_323501["op"], 1), "mode": s.LIC_323501["mode"]},
            },
            "F004": {                            # Flash Tank 323F004 (adiabatic 4.1 -> 1.13 bar)
                "TT_323005":  round(s.r323_f004_T, 1),                       # flash temp (C, hold 106)
                "P_bara":     round(s.r323_f004_P, 2),                       # flash pressure (bar a, dynamic)
                "LI_323505":  round(s.r323_f004_M / R323_F004_M_FULL * 100.0, 1),
                "v701_th":    round(m_701 / 1000.0, 2),                      # flash vapor -> LPCC (t/h)
                "drain319_th":round(m_319 / 1000.0, 2),                      # drain -> pre-evaporator (t/h)
                "LIC_323505": {"pv": round(s.LIC_323505["pv"], 1), "sp": round(s.LIC_323505["sp"], 1),
                               "op": round(s.LIC_323505["op"], 1), "mode": s.LIC_323505["mode"]},
            },
            "F010": {                            # Pre-evaporator 323F010 + Heater 323E010 (vacuum 0.46 bar)
                "TT_323010":  round(s.r323_f010_T, 1),                       # pre-evap temp (C, hold 99)
                "P_bara":     round(s.r323_f010_P, 3),                       # PT-323204 (bar a, live off HV-323605/329605)
                "HV_323605":  round(s.HIC_323605, 1),                        # gas-outlet hand valve (%) — opening drops P
                "LI_323F010": round(s.r323_f010_M / R323_F010_M_FULL * 100.0, 1),
                "feed331_th": round(m_331 / 1000.0, 2),                      # urea-recovery return (t/h)
                "evap_th":    round(m_evap / 1000.0, 2),                     # vapour 790 -> vac (t/h)
                "product317_th": round(m_317 / 1000.0, 2),                   # product -> 323D002 (t/h)
                "Q_kW":       round(Q_e010_kw, 0),                           # heater 323E010 duty (kW)
                "TIC_323012": {"pv": round(s.TIC_323012["pv"], 1), "sp": round(s.TIC_323012["sp"], 1),
                               "op": round(s.TIC_323012["op"], 2), "mode": s.TIC_323012["mode"]},
                "PIC_329208": {"pv": round(s.PIC_329208["pv"], 2), "sp": round(s.PIC_329208["sp"], 2),
                               "op": round(s.PIC_329208["op"], 1), "mode": s.PIC_329208["mode"]},
            },
            "D002": {                            # Urea Solution Tank 323D002 (2-compartment, atm)
                "T_C":        round(s.r323_d002_T, 1),                       # kept for existing callers
                "TI_323008":  round(s.r323_d002_T, 1),                       # Comp I bulk temp (C, TAL)
                "LI_323507":  round(lvl_d002_I, 1),                          # Comp I level (%, live density)
                "LI_323504":  round(s.r323_d002_M_II / v_II_full * 100.0, 1),# Comp II level (%)
                "LI_comp2":   round(s.r323_d002_M_II / v_II_full * 100.0, 1),# legacy alias of LI-323504
                "HV_tie":     bool(s.HV_323D002_TIE),                        # field tie-in spool Comp I <-> Comp II
                "rho_kgm3":   round(rho_d002, 1),                            # live solution density (C10)
                "m3_comp1":   round(s.r323_d002_M_I / rho_d002, 1),          # Comp I inventory (m3)
                "m3_comp2":   round(s.r323_d002_M_II / rho_d002, 1),         # Comp II inventory (m3)
                "urea_pct":   round(s.w_d002.get("Urea", 0.0) * 100.0, 2),   # TD-013: live, no longer pinned
                "product324_th": round(m_324 / 1000.0, 2),                   # product -> Unit 324 (t/h)
                "LIC_323507": {"pv": round(s.LIC_323507["pv"], 1), "sp": round(s.LIC_323507["sp"], 1),
                               "op": round(s.LIC_323507["op"], 1), "mode": s.LIC_323507["mode"]},
                "FIC_324401": {"pv": round(s.FIC_324401["pv"], 1), "sp": round(s.FIC_324401["sp"], 1),
                               "op": round(s.FIC_324401["op"], 1), "mode": s.FIC_324401["mode"]},
            },
        },
        "LPCC_3232": {                           # Screen 323-2 : LP Carbamate Condenser train
            "E003": {                            # 323E003 LPCC + 323D001 carbamate separator (74°C)
                "TT_323003":  round(s.r3232_e003_T, 1),                    # shell liquid temp (C, hold 74)
                "P_bara":     round(s.r3232_d001_P, 2),                    # 323D001 pressure (bar a)
                "LI_323502":  round(s.r3232_d001_M / R3232_D001_M_FULL * 100.0, 1),
                "in305_th":   round(m_305 / 1000.0, 2),                    # 323C003 vapour in (t/h)
                "carbamate308_th": round(m_308 / 1000.0, 2),              # 323P001 carbamate -> HP (t/h)
                "vent321_th": round(m_321 / 1000.0, 2),                    # PV-323202 vent -> 323E011 (t/h)
                "wash744_th": round(m_744 / 1000.0, 2),                    # FIC-328402 wash -> 328D003-II (t/h)
                "liquor756_th": round(m_756 / 1000.0, 2),                  # 322C001 liquor feed (t/h)
                "PIC_323202": {"pv": round(s.PIC_323202["pv"], 2), "sp": round(s.PIC_323202["sp"], 2),
                               "op": round(s.PIC_323202["op"], 1), "mode": s.PIC_323202["mode"]},
                "LIC_323502": {"pv": round(s.LIC_323502["pv"], 1), "sp": round(s.LIC_323502["sp"], 1),
                               "op": round(s.LIC_323502["op"], 1), "mode": s.LIC_323502["mode"]},
                "SIC_323901": {"pv": round(s.SIC_323901["pv"], 1), "sp": round(s.SIC_323901["sp"], 1),
                               "op": round(s.SIC_323901["op"], 1), "mode": s.SIC_323901["mode"]},
                "SIC_323902": {"pv": round(s.SIC_323902["pv"], 1), "sp": round(s.SIC_323902["sp"], 1),
                               "op": round(s.SIC_323902["op"], 1), "mode": s.SIC_323902["mode"]},
                "TIC_323013": {"pv": round(s.TIC_323013["pv"], 1), "sp": round(s.TIC_323013["sp"], 1),
                               "op": round(s.TIC_323013["op"], 2), "mode": s.TIC_323013["mode"]},
                "TV_323013A": round(tic13_op, 1),              # cold make-up : opens as PV rises above SP
                "TV_323013B": round(100.0 - tic13_op, 1),      # hot bypass : exact opposite of TV-323013A
                "TT_323015":  round(T_tw_ret, 1),              # TW return 323E003 -> 323P003 (1103, 65 °C)
                # FIC-328402 is a VOLUMETRIC loop: pv/sp are m3/h (the operator enters SP in m3/h).
                "FIC_328402": {"pv": round(s.FIC_328402["pv"], 2), "sp": round(s.FIC_328402["sp"], 2),
                               "op": round(s.FIC_328402["op"], 1), "mode": s.FIC_328402["mode"],
                               "vol_m3h": round(m_744 / RHO_744_KGM3, 2),   # PFD stream 744 (raw, unlagged)
                               "kgh": round(m_744, 1)},
            },
            "E011": {                            # 323E011 LP carbamate condenser + 323D011 (45°C)
                "TT_323011":  round(s.r3232_e011_T, 1),                    # shell liquid temp (C, hold 45)
                "P_bara":     round(s.r3232_e011_P, 2),                    # 323D011 pressure (bar a)
                "LI_323D011": round(s.r3232_e011_M / R3232_D011_M_DES * R3232_D011_LVL_SP, 1),
                "in701_th":   round(m_701 / 1000.0, 2),                    # 323F004 flash vapour in (t/h)
                "vap011_th":  round(m_v011 / 1000.0, 2),                   # PIC-323203 vapour -> 323C005 (t/h)
                "carb718A_th":round(m_718A / 1000.0, 2),                   # -> 328D001 (t/h)
                "carb718B_th":round(m_718B / 1000.0, 2),                   # -> 323E003 (t/h)
                "PIC_323203": {"pv": round(s.PIC_323203["pv"], 2), "sp": round(s.PIC_323203["sp"], 2),
                               "op": round(s.PIC_323203["op"], 1), "mode": s.PIC_323203["mode"]},
                "FIC_323401": {"pv": round(s.FIC_323401["pv"], 2), "sp": round(s.FIC_323401["sp"], 2),
                               "op": round(s.FIC_323401["op"], 1), "mode": s.FIC_323401["mode"],
                               "vol_m3h": round(m_401 / RHO_401_KGM3, 2),   # volumetric loop PV (m3/h), PFD 401 flush
                               "m_kgh": round(m_401, 1)},                   # delivered mass -> 328D003 (kg/h, HMB)
                # FIC-323402 is a VOLUMETRIC loop: pv/sp are m3/h (the operator enters SP in m3/h).
                "FIC_323402": {"pv": round(s.FIC_323402["pv"], 2), "sp": round(s.FIC_323402["sp"], 2),
                               "op": round(s.FIC_323402["op"], 1), "mode": s.FIC_323402["mode"],
                               "vol_m3h": round(m_402 / RHO_791_KGM3, 2),   # PFD stream 791 (raw, unlagged)
                               "m_kgh": round(m_402, 1)},                   # delivered mass -> 323E011 (kg/h, HMB)
            },
            "C005": {                            # 323C005 off-gas scrubber -> 328V001
                "TT_323C005": round(s.a323_c005_T, 1),                     # scrub liquid temp (C, hold 55)
                "LI_323503":  round(s.a323_c005_M / A323_C005_M_DES * 50.0, 1),
                "bot_th":     round(bot_c005 / 1000.0, 2),                 # bottoms -> 328V001 (t/h)
                "in756_kgh":  round(m756_prev, 1),
                "in702_kgh":  round(m702_prev, 1),
                "in708_kgh":  round(m708_prev, 1),
                "out343_kgh": round(mapped_m343, 1),
                "out341_kgh": round(mapped_m341, 1),
                "closure_kgh": round(m756_prev + m702_prev + m708_prev
                                     - mapped_m343 - mapped_m341, 6),
                "FIC_323418": {"pv": round(s.FIC_323418["pv"], 2), "sp": round(s.FIC_323418["sp"], 2),
                               "op": round(s.FIC_323418["op"], 1), "mode": s.FIC_323418["mode"],
                               "vol_m3h": round(m_718B / RHO_718_KGM3, 2),  # volumetric loop PV (m3/h), PFD 718B
                               "m_kgh": round(m_718B, 1)},                  # 718B slipstream -> 323E003 (kg/h)
                "FIC_328405": {"pv": round(s.FIC_328405["pv"], 2), "sp": round(s.FIC_328405["sp"], 2),
                               "op": round(s.FIC_328405["op"], 1), "mode": s.FIC_328405["mode"],
                               "vol_m3h": round(m_793 / RHO_401_KGM3, 2),   # volumetric loop PV (m3/h), PFD 793
                               "m_kgh": round(m_793, 1)},                   # 793 spare draw off 328D003 Comp-II (kg/h)
                "LIC_323503": {"pv": round(s.LIC_323503["pv"], 1), "sp": round(s.LIC_323503["sp"], 1),
                               "op": round(s.LIC_323503["op"], 1), "mode": s.LIC_323503["mode"]},
            },
        },
        "DESORB_328": {                          # Screen 328-1 : Desorption / Hydrolysis train
            "C002": {                            # 328C002 Desorber-I (bottoms 139°C)
                "TT_328C002": round(s.a328_c002_T, 1),                     # bottom temp (C, hold 139)
                "TT_328007":  round(s.a328_c002_T, 1),                     # bottoms draw -> 328P006 (stream 743, 139C)
                # AUDIT B4: TT-328008 belongs on the 328C002 OVERHEAD (stream 737, 117 C -> 328E004),
                # per Mapping of Desorber Hydrolyzer unit.md:46.  It used to be published in the D001
                # block off the frozen 328E007 cold outlet (114 C) and aliased to TT-328010.
                "TT_328008":  round(s.a328_c002_T - R328_C002_DT_TOP, 1),  # column top / stream 737 (C, 117)
                "P_bara":     round(s.a328_c002_P, 2),                     # AUDIT C1: live column pressure (3.5 bar a)
                "TT_328010":  round(T_738, 1),                             # 328E007 cold out -> feed 738 (C, 114)
                "LI_328503":  round(s.a328_c002_M / R328_C002_M_DES * 50.0, 1),
                "feed738_th": round(m_738 / 1000.0, 2),                    # 328D003 feed via 328E007 (t/h)
                "ovhd737_th": round(m_737 / 1000.0, 2),                    # top vapour -> 328D001 (t/h)
                "bot743_th":  round(m_743 / 1000.0, 2),                    # bottoms -> 328C003 (t/h)
                "LIC_328503": {"pv": round(s.LIC_328503["pv"], 1), "sp": round(s.LIC_328503["sp"], 1),
                               "op": round(s.LIC_328503["op"], 1), "mode": s.LIC_328503["mode"]},
            },
            "C003": {                            # 328C003 Hydrolyser (200°C, MP steam)
                "TT_328C003": round(s.a328_c003_T, 1),                     # temp (C, hold 200)
                "TT_328012":  round(T_746, 1),                             # 3rd tray / 746 (C, 190) - AUDIT C32: live 328E021 cold outlet
                # AUDIT B6: TT-328011 is on the 328C003 OVERHEAD line (stream 748, 188 C) per
                # Mapping of Desorber Hydrolyzer unit.md:17.  It used to be aliased onto TT-328012's
                # frozen 3rd-tray value, so the operator had no independent hydrolyser-overhead read.
                "TT_328011":  round(s.a328_c003_T - R328_C003_DT_748, 1),  # OVHD 748 -> 328C002 (C, 188)
                "TT_328009":  round(T_746, 1),                             # 328E021 cold out -> C003 feed (stream 746, 190C)
                "P_bara":     round(s.a328_c003_P, 2),
                "LI_328504":  round(s.a328_c003_M / R328_C003_M_DES * 50.0, 1),
                "steam911_th":round(m_911 / 1000.0, 2),                    # FIC-329402 MP steam (t/h)
                "ovhd748_th": round(m_748 / 1000.0, 2),                    # relief -> 328C002 (t/h)
                "bot747_th":  round(m_747 / 1000.0, 2),                    # bottoms -> 328C004 (t/h)
                # AUDIT F-7/TD-008: the hydrolysis reaction is now IN the mass balance
                "X_hydrolysis": round(x_hyd_328 * 100.0, 4),               # urea conversion (%)
                "xi_urea_kmolh": round(xi_hyd_328, 4),                     # extent (kmol/h destroyed)
                "urea_in_kgh":  round(urea_in_328, 1),                     # urea fed with stream 746
                "urea_slip_ppm":round(ppm_urea_747, 3),                    # unreacted urea -> 328C004
                "gas_hyd_kgh":  round(gas_hyd, 1),                         # NH3+CO2 made by reaction
                "gas_strip_kgh":round(gas_str, 1),                         # carried over by MP steam
                "PIC_328203": {"pv": round(s.PIC_328203["pv"], 2), "sp": round(s.PIC_328203["sp"], 2),
                               "op": round(s.PIC_328203["op"], 1), "mode": s.PIC_328203["mode"]},
                "LIC_328504": {"pv": round(s.LIC_328504["pv"], 1), "sp": round(s.LIC_328504["sp"], 1),
                               "op": round(s.LIC_328504["op"], 1), "mode": s.LIC_328504["mode"]},
                "FIC_329402": {"pv": round(s.FIC_329402["pv"], 1), "sp": round(s.FIC_329402["sp"], 1),
                               "op": round(s.FIC_329402["op"], 1), "mode": s.FIC_329402["mode"]},
                "TIC_328012": {"pv": round(s.TIC_328012["pv"], 1), "sp": round(s.TIC_328012["sp"], 1),
                               "op": round(s.TIC_328012["op"], 2), "mode": s.TIC_328012["mode"]},
            },
            "C004": {                            # 328C004 Desorber-II (143°C, LP steam, FFIC ratio)
                "TT_328C004": round(s.a328_c004_T, 1),                     # temp (C, hold 143)
                "TT_328005":  round(s.a328_c004_T, 1),                     # bottoms draw -> 328E007 (stream 739, 143C)
                "TT_328004":  round(s.a328_c004_T - R328_C004_DT_DES, 1),  # top tray = OVHD 750 (140C), tracks live bottoms
                "P_bara":     round(s.a328_c004_P, 2),                     # AUDIT C1: live column pressure (3.7 bar a)
                "LI_328505":  round(s.a328_c004_M / R328_C004_M_DES * 50.0, 1),
                "steam931_th":round(m_931 / 1000.0, 2),                    # FIC-329401 LP steam (t/h)
                "ovhd750_th": round(m_750 / 1000.0, 2),                    # relief -> 328C002 (t/h)
                "bot739_th":  round(m_739 / 1000.0, 2),                    # bottoms -> 328E007 (stream 739, t/h)
                "recyc741_th":round(m_741 / 1000.0, 2),                    # 740 condensate diverted back to Comp II (FIC-328406, t/h)
                "export740_th":round(max(m_739 - m_741, 0.0) / 1000.0, 2), # 740 leaving the envelope = 739 - 741 (t/h)
                "TT_328006":   round(T_740, 1),                            # stream 740 condensate temp (89C, 328E007 hot out) - AUDIT C10: live
                "AI_328701":   round(_ai701_uS, 2),                        # process-condensate conductivity (uS/cm @25C)
                "nh3_740_ppm": round(_nh3_740, 3),                        # derived trace NH3 slip (ppm mass)
                "urea_740_ppm":round(_urea_740, 3),                       # derived trace urea slip (ppm mass)
                "FFIC_329401":{"pv": round(s.FFIC_329401["pv"], 4), "sp": round(s.FFIC_329401["sp"], 4),
                               "op": round(s.FFIC_329401["op"], 1), "mode": s.FFIC_329401["mode"]},
                "FIC_329401": {"pv": round(s.FIC_329401["pv"], 1), "sp": round(s.FIC_329401["sp"], 1),
                               "op": round(s.FIC_329401["op"], 1), "mode": s.FIC_329401["mode"]},
                "LIC_328505": {"pv": round(s.LIC_328505["pv"], 1), "sp": round(s.LIC_328505["sp"], 1),
                               "op": round(s.LIC_328505["op"], 1), "mode": s.LIC_328505["mode"]},
            },
            "D001": {                            # 328D001 Desorber-I reflux drum (61°C, 328E004)
                "TT_328D001": round(s.a328_d001_T, 1),                     # temp (C, hold 61)
                "P_bara":     round(s.a328_d001_P, 2),
                "LI_328501":  round(s.a328_d001_M / R328_D001_M_DES * R328_D001_LVL_SP, 1),
                "vent786_th": round(m_786_d001 / 1000.0, 2),               # PIC-328202 vent -> 323E011 (t/h)
                "reflux775_th":round(m_775 / 1000.0, 2),                   # FIC-328404 reflux -> 328C002 (t/h)
                "draw776_th": round(m_776 / 1000.0, 2),                    # LV-328501 draw -> 323E003 (t/h)
                "flow776_m3h": round(m_776 / R328_D001_M776_RHO, 2),        # FT-328401: LV-328501 draw in m3/h (stream 776, des 7.6)
                "PIC_328202": {"pv": round(s.PIC_328202["pv"], 2), "sp": round(s.PIC_328202["sp"], 2),
                               "op": round(s.PIC_328202["op"], 1), "mode": s.PIC_328202["mode"]},
                "LIC_328501": {"pv": round(s.LIC_328501["pv"], 1), "sp": round(s.LIC_328501["sp"], 1),
                               "op": round(s.LIC_328501["op"], 1), "mode": s.LIC_328501["mode"]},
                # FIC-328404 is a VOLUMETRIC loop: pv/sp are m3/h (the operator enters SP in m3/h).
                "FIC_328404": {"pv": round(s.FIC_328404["pv"], 2), "sp": round(s.FIC_328404["sp"], 2),
                               "op": round(s.FIC_328404["op"], 1), "mode": s.FIC_328404["mode"],
                               "vol_m3h": round(m_775 / RHO_775_KGM3, 2),   # PFD stream 775 (raw, unlagged)
                               "m_kgh": round(m_775, 1)},                   # delivered mass -> 328C002 (kg/h, HMB)
                "TIC_328002": {"pv": round(s.TIC_328002["pv"], 1), "sp": round(s.TIC_328002["sp"], 1),
                               "op": round(s.TIC_328002["op"], 2), "mode": s.TIC_328002["mode"]},
                # TT-329007: 328E004 cooling-water return temp = PFD stream 1029 (C). 38 at the design
                # TV-328002 opening (50 %); INVERSE in CW flow so opening TV-328002 cools the return and
                # closing it heats the return (TIC-328002 sets the opening). Clamped at the flash ceiling.
                "TT_329007": round(min(R328_E004_CW_T_IN_C
                                       + (R328_E004_CW_T_OUT_DES_C - R328_E004_CW_T_IN_C)
                                         * (R328_E004_TV_OP_DES / max(s.TIC_328002["op"], 1.0)),
                                       R328_E004_CW_T_MAX_C), 1),
                "TIC_328008": {"pv": round(s.TIC_328008["pv"], 1), "sp": round(s.TIC_328008["sp"], 1),
                               "op": round(s.TIC_328008["op"], 2), "mode": s.TIC_328008["mode"]},
            },
        },
        "ABSORB_328": {                          # Screen 328-2 : LP Absorber + recirc collector
            "C001": {                            # 322C001 LP off-gas absorber (43°C, live GCB)
                "TT_322015":  round(s.a328_c001_T, 1),                     # liquid temp (C, hold 43; trip>57)
                "P_bara":     round(s.a328_c001_P, 2),
                "LI_322502":  round(s.a328_c001_M / A328_C001_M_DES * 50.0, 1),
                "gcb_th":     round(gcb_m / 1000.0, 2),                    # HV-322604 off-gas in (t/h)
                "gcb_T":      round(gcb_T, 1),                             # off-gas temp (C)
                "abs_th":     round(abs_c001 / 1000.0, 2),                 # NH3/CO2 absorbed (t/h)
                "vent_th":    round(vent_c001 / 1000.0, 2),               # inert + slip vent -> 328V001 (t/h)
                # TD-009 remainder — live vent NH3 slip (was a boot-pinned split; now off the species balance)
                "vent_nh3_kgh": round(vent_c001 * (y_vent["NH3"] if y_vent else 0.0), 1),  # NH3 -> 328V001/atm (kg/h)
                "vent_nh3_pct": round((y_vent["NH3"] if y_vent else 0.0) * 100.0, 2),  # NH3 mass% in the atm vent
                "vent_co2_pct": round((y_vent["CO2"] if y_vent else 0.0) * 100.0, 2),  # CO2 mass% in the atm vent
                "liq_nh3_pct":  round(s.a328_c001_w.get("NH3", 0.0) * 100.0, 2),        # dissolved NH3 in the liquor
                "liq_co2_pct":  round(s.a328_c001_w.get("CO2", 0.0) * 100.0, 2),        # dissolved CO2 in the liquor
                "liquor756_th": round(m_756 / 1000.0, 2),                 # LV-322502 draw -> 323C005 (t/h)
                "cpl_kgh":    round(s.cpl_flow_kgh, 1),                    # FT-322404: condensate 954 in (kg/h, operator-set)
                "make_conc_pct": round(abs_c001 / max(m_756, 1e-6) * 100.0, 2),  # absorbed NH3/CO2 fraction of 756 draw (dilutes as CPL rises)
                "XV_322915":  bool(s.XV_322915),                          # steam-flood trip valve (22.1)
                "PIC_322201": {"pv": round(s.PIC_322201["pv"], 2), "sp": round(s.PIC_322201["sp"], 2),
                               "op": round(s.PIC_322201["op"], 1), "mode": s.PIC_322201["mode"]},
                "LIC_322502": {"pv": round(s.LIC_322502["pv"], 1), "sp": round(s.LIC_322502["sp"], 1),
                               "op": round(s.LIC_322502["op"], 1), "mode": s.LIC_322502["mode"]},
            },
            "D003": {                            # 328D003 active bays I/II + accumulation bay III
                "TT_328I":    round(s.a328_d003_TI, 1),
                "TT_328II":   round(s.a328_d003_TII, 1),
                "TT_328III":  round(s.a328_d003_TIII, 1),
                **_d003_levels,
                "capacities_m3": {"I": A328_D003_VOL_I_M3,
                                    "II": A328_D003_VOL_II_M3,
                                    "III": A328_D003_VOL_III_M3},
                "form735_th": round(m_735 / 1000.0, 2),                    # Comp-II -> 328C002
                "collect755_th": round(m_755 / 1000.0, 2),                 # Comp-I -> 322P002/E006/C001
                "flow755_m3h": round(m_755 / A328_M755_RHO, 2),            # FT-322402: 755 draw in m3/h (des 31.3)
                "compI_pfd_rounding_kgh": round((m_719 + m_720 + m_721 + m_759) - m_744, 3),
                "compII_pfd_rounding_kgh": round((bot_c005 + m_741)
                                                   - (m_735 + m_401 + m_402 + m_793), 3),
                # FIC-328406 is the PFD-741 process-condensate RECYCLE, 328E007 -> 328E001 -> Comp II
                # (TD-005).  Normally closed, so pv/sp read 0.00 m3/h at 100 % load.  It is now a
                # VOLUMETRIC loop: pv/sp are already m3/h, and m_kgh carries the delivered mass that
                # the Comp-II holdup ODE actually sees.
                "FIC_328406": {"pv": round(s.FIC_328406["pv"], 2), "sp": round(s.FIC_328406["sp"], 2),
                               "op": round(s.FIC_328406["op"], 1), "mode": s.FIC_328406["mode"],
                               "vol_m3h": round(m_741 / RHO_741_KGM3, 2),   # PFD stream 741 (raw, unlagged)
                               "m_kgh": round(m_741, 1)},                   # recycle -> 328D003 Comp II (kg/h)
                # AUDIT C4 / gap G5: unit-328 energy-closure ledger (kW).  Envelope {C002,C003,C004,
                # D001,E021,E007}, reference 0 C.  Q328_react_kW is the explicit carbamate-desorption
                # reaction enthalpy the reboiler steam supplies (previously hidden in back-solved
                # latents); with it made explicit the residual closes at design and stays bounded as
                # a true off-design departure -- see the derivation at the diagnostic itself.
                "Q328_in_kW":    round(q328_in, 1),
                "Q328_out_kW":   round(q328_out, 1),
                "Q328_react_kW": round(q328_react, 1),
                "Q328_resid_kW": round(q328_resid, 1),
                "P002A":      {"on": s.aux_pumps["322P002A"]["on"], "mode": s.aux_pumps["322P002A"]["mode"]},
                "P002B":      {"on": s.aux_pumps["322P002B"]["on"], "mode": s.aux_pumps["322P002B"]["mode"]},
            },
        },
        "EVAP_324": {                            # Screens 324-1 / 324-1B : two-stage vacuum evaporation
            "E001": {                            # Screen 324-1 : Evaporator I 324E001 / 324F001 (130 C, 0.33 bar a)
                "TT_324001":   round(s.r324_e001_T, 1),                       # melt temp (C, hold 130)
                # AUDIT B8 — PT-324201 is the 324F001 SEPARATOR transmitter (mapping doc line 11) and
                # is the pressure input to the PY-324201 concentration inferential; PIC-324202 is the
                # 324E002 SHELL controller (line 14).  The separator vacuum used to be published only
                # under the shell controller's tag, so PT-324201 was invisible on the HMI.  The shell
                # retains the PFD's rounded manifold pressure because no gas-side pressure-drop datum exists.
                "PT_324201":   round(s.r324_f001_P, 3),                       # 324F001 separator vacuum (bar a, hold 0.33)
                "PT_324202":   round(s.r324_f001_P, 3),                       # 324E002 shell pressure (shared rounded PFD manifold)
                "LI_324F001":  round(s.r324_f001_M / R324_F001_M_FULL * 100.0, 1),
                "feed_th":     round(feed1_m / 1000.0, 2),                    # blended Stage-1 feed (t/h)
                "vapour_th":   round(v1_m / 1000.0, 2),                       # water vapour -> 324E002 (t/h)
                "melt_th":     round(m_p1 / 1000.0, 2),                       # 95% melt -> Stage 2 (t/h)
                "urea_pct":    round(w1_live * 100.0, 1),                     # AUDIT F-4: LIVE melt conc (94.31 % @design)
                "PY_324201":   round(conc_infer_324(w1_live, R324_E001_T_SP_C, R324_F001_P_BARA,
                                                    s.r324_e001_T, s.r324_f001_P), 1),   # live conc soft-sensor (wt %)
                "p_chest_bara":round(p_chest_e001, 2),                        # steam chest press. (bar a)
                "Q_kW":        round(Q_e001_kw, 0),                           # Evap-I duty (kW)
                "TIC_324001":  {"pv": round(s.TIC_324001["pv"], 1), "sp": round(s.TIC_324001["sp"], 1),
                                "op": round(s.TIC_324001["op"], 2), "mode": s.TIC_324001["mode"]},
                "PIC_329203":  {"pv": round(s.PIC_329203["pv"], 2), "sp": round(s.PIC_329203["sp"], 2),
                                "op": round(s.PIC_329203["op"], 1), "mode": s.PIC_329203["mode"]},
                "PIC_324202":  {"pv": round(s.PIC_324202["pv"], 3), "sp": round(s.PIC_324202["sp"], 3),
                                "op": round(s.PIC_324202["op"], 1), "mode": s.PIC_324202["mode"]},
                "FIC_324401":  {"pv": round(s.FIC_324401["pv"], 2), "sp": round(s.FIC_324401["sp"], 2),
                                "op": round(s.FIC_324401["op"], 1), "mode": s.FIC_324401["mode"]},
                "LI_329505":   round(s.r324_e001_cond_M / R324_E001_COND_M_FULL * 100.0, 1),   # 324E001 shell condensate level (%)
                "cond_kgh":    round(cond_gen, 0),                            # 324E001 steam condensate generated (kg/h)
                "LIC_329505":  {"pv": round(s.LIC_329505["pv"], 1), "sp": round(s.LIC_329505["sp"], 1),
                                "op": round(s.LIC_329505["op"], 1), "mode": s.LIC_329505["mode"]},
                "HIC_329605":  round(s.HIC_329605, 1),                        # 324F002 motive-steam hand valve (%)
                "HV_329605":   round(s.HIC_329605, 1),                        # HV-329605 opening (tracks HIC 1:1)
                "motive_kgh":  round(mot9605_m, 0),                           # 324F002 motive LP steam flow (kg/h)
                "P_324E002_sh":round(s.r324_f001_P, 3),                       # 324E002 shell = 324F001 manifold (bar a); HV-329605 drops it
            },
            "E003": {                            # Screen 324-1B : Evaporator II 324E003 / 324F003 (140 C, 0.131 bar a)
                "TT_324002":   round(s.r324_e003_T, 1),                       # melt temp (C, hold 140)
                # AUDIT B8 — PT-324204 is the 324F003 separator transmitter (mapping doc line 20) and
                # feeds the AY-324701 inferential; PIC-324203 is the 324E005 shell controller (line 24).
                "PT_324204":   round(s.r324_f003_P, 3),                       # 324F003 separator vacuum (bar a, hold 0.131)
                "PT_324203":   round(s.r324_f003_P, 3),                       # 324E005 shell pressure (shared rounded PFD manifold)
                "LI_324F003":  round(s.r324_f003_M / R324_F003_M_FULL * 100.0, 1),
                "feed_th":     round(feed2_m / 1000.0, 2),                    # 95% melt from Stage 1 (t/h)
                "vapour_th":   round(v2_m / 1000.0, 2),                       # water vapour -> 324E005 (t/h)
                "melt_fwd_th": round(m_fwd / 1000.0, 2),                      # urea melt via LV-324501A -> BL (t/h)
                "recyc_th":    round(m_recyc / 1000.0, 2),                    # melt via LV-324501B relief -> 323D002 (t/h)
                "route":       route501["route"],
                "selector_stream": route501["selector_stream"],
                "selector_feed_th": round(route501["selector_feed_kgh"] / 1000.0, 3),
                "selector_feed_T_C": round(route501["selector_feed_T_C"], 3),
                "selector_feed_comp": {k: round(v, 8) for k, v in route501["selector_feed_comp"].items()},
                "UF85_interlocked": route501["uf85_interlocked"],
                "UF85_measured_ratio": round(uf_cascade["measured_ratio"], 8),
                "UF85_ratio_command": round(uf_cascade["ratio_command"], 8),
                "UF85_flow_setpoint_th": round(uf_cascade["flow_setpoint_th"], 6),
                "route_mass_residual_kgh": round(route501["mass_residual_kgh"], 9),
                "route_species_residual_kgh": {
                    k: round(v, 9) for k, v in route501["species_residual_kgh"].items()
                },
                "route_energy_residual_kw": round(route501["energy_residual_kw"], 9),
                "LV_324501A":  round(lva_stroke, 1),                          # level-controlled melt export to BL (%)
                "LV_324501B":  round(lvb_stroke, 1),                          # normally-closed relief -> 323D002 (%)
                "PIC_335201":  round(s.PIC_335201, 2),                        # 335 melt-header pressure (bar g, BL boundary)
                "LVB_relief_barg": R335_LVB_RELIEF_BARG,                      # LV-324501B opens above this (bar g)
                "recycle_selected": bool(recycle_selected),                  # True when PIC-335201 > relief (LV-B open)
                "urea_pct":    round(w2_live * 100.0, 1),                     # AUDIT F-5: LIVE product conc (97.71 % @design)
                "AY_324701":   round(conc_infer_324(w2_live, R324_E003_T_SP_C, R324_F003_P_BARA,
                                                    s.r324_e003_T, s.r324_f003_P), 1),   # live conc soft-sensor (wt %)
                "product_th":  round(m_product / 1000.0, 2),                  # urea melt -> BL (t/h; UF85 deferred)
                "uf85_kgh":    round(m_uf, 1),                                # UF85 injection (kg/h; 0 until 335 simulated)
                "uf85_m3h":    round(m_uf / R324_UF85_RHO, 2),                # UF85 injection (m3/h @1305 kg/m3)
                "p_chest_bara":round(p_chest_e003, 2),                        # steam chest press. (bar a)
                "Q_kW":        round(Q_e003_kw, 0),                           # Evap-II duty (kW)
                "HIC_329606":  round(s.HIC_329606, 1),                        # 324F004/F005 motive-steam hand valve (%)
                "HV_329606":   round(s.HIC_329606, 1),                        # HV-329606 opening (tracks HIC 1:1) — opening drops 324F003/E005 P
                "P_324E005_sh":round(s.r324_f003_P, 3),                       # 324E005 shell = 324F003 manifold (bar a)
                "TIC_324002":  {"pv": round(s.TIC_324002["pv"], 1), "sp": round(s.TIC_324002["sp"], 1),
                                "op": round(s.TIC_324002["op"], 2), "mode": s.TIC_324002["mode"]},
                "PIC_329212":  {"pv": round(s.PIC_329212["pv"], 2), "sp": round(s.PIC_329212["sp"], 2),
                                "op": round(s.PIC_329212["op"], 1), "mode": s.PIC_329212["mode"]},
                "PIC_324203":  {"pv": round(s.PIC_324203["pv"], 3), "sp": round(s.PIC_324203["sp"], 3),
                                "op": round(s.PIC_324203["op"], 1), "mode": s.PIC_324203["mode"]},
                "LIC_324501":  {"pv": round(s.LIC_324501["pv"], 1), "sp": round(s.LIC_324501["sp"], 1),
                                "op": round(s.LIC_324501["op"], 1), "mode": s.LIC_324501["mode"]},
                "FFIC_335406": {"pv": round(s.FFIC_335406["pv"], 4), "sp": round(s.FFIC_335406["sp"], 4),
                                "op": round(s.FFIC_335406["op"], 4), "mode": s.FFIC_335406["mode"]},
                "FIC_335405":  {"pv": round(s.FIC_335405["pv"], 3), "sp": round(s.FIC_335405["sp"], 3),
                                "op": round(s.FIC_335405["op"], 1), "mode": s.FIC_335405["mode"]},
            },
            "VAC": {                             # vacuum condensation train (324E002/E005/E006/E007 + ejectors)
                "condensate_th": round(m_324_cond / 1000.0, 2),              # 719+720+721+759 -> 328D003 Comp I (t/h)
                "vent_kgh":      round(m_324_vent, 1),                        # non-condensable vent -> atm (kg/h)
                "mix703_residual_kgh": round(vac324["mixing_residual_703_kgh"], 3),
                **{
                    _tag: {
                        "Q_kW": round(_node["q_kw"], 1),
                        "UA_kW_K": round(_node["ua_kw_k"], 3),
                        "UA_eff_kW_K": round(_node["ua_eff_kw_k"], 3),
                        "LMTD_K": round(_node["lmtd_k"], 3),
                        "cw_in_th": round(_node["cw_flow_kgh"] / 1000.0, 3),
                        "cw_in_C": round(_node["cw_in_c"], 2),
                        "cw_out_C": round(_node["cw_out_c"], 2),
                        "inlet_kgh": round(_node["inlet_kgh"], 1),
                        "condensate_kgh": round(_node["condensate_kgh"], 1),
                        "vent_kgh": round(_node["vent_kgh"], 1),
                        "mass_residual_kgh": round(_node["mass_residual_kgh"], 6),
                        "energy_residual_kW": round(_node["energy_residual_kw"], 6),
                        "area_m2": VACUUM_CONDENSERS[_tag]["area_m2"],
                        "tube_count": VACUUM_CONDENSERS[_tag]["tube_count"],
                    }
                    for _tag, _node in vac324["nodes"].items()
                },
            },
        },
        "HPCC_322E002": {                        # HP Carbamate Condenser 322E002 -> 322R001
            "TT_322012":   round(d_TT322012, 1),         # tube feed 1: ejector-disch liquid temp (C, lagged)
            "TT_322013":   round(d_TT322013, 1),         # tube feed 2: stripper-top gas temp (C, lagged)
            "TT_322010":   round(d_TT322010, 1),         # liquid product -> 322R001 (C, lagged)
            "TT_329001":   round(T_shell_lp, 1),         # F6: shell BFW/condensate feed T de-pinned -> live LP-header sat T (==146.3 at design)
            "gas_th":      round(hpcc["gas_th"], 2),     # gas product (t/h)
            "gas_MW":      round(hpcc["gas_MW"], 2),
            "gas_mol_pct": {k: round(hpcc["gas_mol_pct"][k], 3) for k in MW_COMP},   # mol %
            "liq_th":      round(hpcc["liq_th"], 2),     # liquid product (t/h)
            "liq_MW":      round(hpcc["liq_MW"], 2),
            "liq_mass_pct":{k: round(hpcc["liq_mass_pct"][k], 3) for k in MW_COMP},  # mass %
            "phi_gas":     {k: hpcc["phi_gas"][k] for k in MW_COMP},   # AUDIT F-6: live (T,P) flash split (unrounded — diag/gate)
            "LT_322E002":  round(s.hpcc_level_pct, 1),   # liquid level (%) — DYNAMIC inventory (swells on stall)
            "P_bara":      round(d_HPCC_P, 1),
            "steam": {                            # shell side: LP steam (live LP header, heat recovery)
                "TI_shell": round(T_shell_lp, 1),            # live LP-header sat condensing temp (C)
                "P_bara":   round(s.steam.P_LP, 1),          # live LP header pressure (bar a)
                "kgh":      round(hpcc["steam_kgh"], 0),     # LP steam produced (kg/h)
                "duty_kW":  round(hpcc["duty_kw"], 0),       # condensation duty (kW)
            },
        },
        "STEAM_SYSTEM": {                        # MP/LP steam headers (lumped-capacitance dynamic)
            # --- steam-network flow transmitters (PFD-anchored dynamic telemetry, t/h; see FT403/407
            #     anchor block above -- OEM 1750 MTPD 100% load, streams 901/902/903/911/963/932) ---
            # FT-329403 (stream 901 supply main): live BL steam to 328C003(911) + 329D005(902) +
            #   329D009(903) + 322D001A/B(963).  m_911 (kg/h, FIC-329402) + (902+903 PFD)*live strip
            #   ratio + 963(static 0) ; -> 60.85 t/h @design, scales with live strip-steam load.
            "FT_329403_th": round((m_911
                                   + (FT403_S902_DES + FT403_S903_DES)
                                     * (s.steam.m_supply / M_STRIP_DES_KGS)
                                   + FT403_S963_DES) / 1000.0, 2),
            # FT-329407 (stream 932): actual PV-329207B turbine export, kg/s -> t/h.
            "FT_329407_th": round(s.steam.m_turbine * 3.6, 2),
            "FT_329407_design_th": round(FT407_S932_DES / 1000.0, 2),
            "MP": {
                "P_bara":      round(s.steam.P_MP, 2),       # MP header pressure (bar a)
                "TI_sat":      round(tsat_steam(s.steam.P_MP), 1),  # MP sat temp (C)
                "supply_pct":  round(s.steam.valve_supply_pct, 1),  # MP supply valve opening (%)
                "m_supply_th": round(s.steam.m_supply * 3.6, 1),    # supply flow (t/h)
            },
            "LP": {
                "P_bara":      round(P_LP_hpcc, 2),          # pressure used by HPCC this SM pass
                "P_next_bara": round(s.steam.P_LP, 2),       # advanced header state for next pass
                # Same plant-anchored saturation basis used by the HPCC shell calculation.
                "TI_sat":      round(T_shell_lp, 1),
                "TI_HPCC_shell": round(T_shell_lp, 1),       # reduced-model shell T (may be gated)
                "letdown_pct": round(s.steam.valve_letdown_pct, 1), # 9->4 let-down (PV-329205B) opening (%)
                "m_ld_th":     round(s.steam.m_ld * 3.6, 1),        # let-down flow (t/h)
                "m_water_th":  round(s.steam.m_water * 3.6, 1),     # desuperheat water (t/h)
            },
            "SUPPLY_25BAR": {                    # 25-bar site main (stream 901, boundary held)
                "P_bara":  round(s.steam.P_SUP, 2),
                "TI_sat":  round(tsat_steam(s.steam.P_SUP), 1),
            },
            "DRUM_9BAR": {                       # 329D009 MP drum (stream 903); split-range PIC-329205
                "P_bara":      round(s.steam.P_9, 2),
                "TI_sat":      round(tsat_steam(s.steam.P_9), 1),
                "admit_pct":   round(s.steam.valve_admit9_pct, 1),  # PV-329205A BL admit
                "letdown_pct": round(s.steam.valve_letdown_pct, 1), # PV-329205B 9->4 let-down
                "m_903_th":    round(s.steam.m_903 * 3.6, 2),       # BL -> 9-bar (t/h)
                "m_flash_th":  round(s.steam.m_flash9 * 3.6, 2),    # 904 flash recovery -> vapour
                "m_users_th":  round(s.steam.m_users9 * 3.6, 2),    # actual 9-bar header demand
                "m_ld_th":     round(s.steam.m_ld * 3.6, 2),        # 9 -> 4 let-down (t/h)
            },
            "HP_VENT": {                         # 329D005 HV-329601 atmospheric vent
                "pct":  round(s.steam.hv_vent_hp_pct, 1),
                "m_th": round(s.steam.m_vent_hp * 3.6, 2),
            },
            "LP_MAKEUP": {                       # 4-bar make-up / vent balance
                "PV_329207C": round(s.steam.valve_963_pct, 1),      # BL -> 4-bar (stream 963)
                "HV_329602":  round(s.steam.hv_329602_pct, 1),      # BL -> 4-bar hand valve
                "m_963_th":   round(s.steam.m_963 * 3.6, 2),
                "m_pic_th":   round(s.steam.m_pic * 3.6, 2),        # PIC-329207A/B vent(+)/make-up(-)
            },
            "mass_residual_kg_s": {
                "d005_vapor": s.steam.mass_residual_d005_vapor,
                "d009_vapor": s.steam.mass_residual_d009_vapor,
                "lp_vapor": s.steam.mass_residual_lp_vapor,
                "d005_liquid": s.steam.mass_residual_d005_liquid,
                "d009_liquid": s.steam.mass_residual_d009_liquid,
                "lp_liquid": s.steam.mass_residual_lp_liquid,
            },
            "PIC_329204": {                      # 329D005 HP-saturator faceplate (PV=MP header P)
                "pv":   round(s.steam.P_MP, 2),                     # bar a
                "sp":   round(s.steam.pic204_sp, 2),
                "op":   round(s.steam.valve_supply_pct, 1),        # PV-329204 opening (%)
                "mode": s.steam.pic204_mode,
            },
            "PIC_329205": {                      # 329D009 split-range faceplate (PV=9-bar drum P)
                "pv":   round(s.steam.P_9, 2),                      # bar a
                "sp":   round(s.steam.pic205_sp, 2),
                "op":   round(s.steam.valve_admit9_pct - s.steam.valve_letdown_pct, 1),  # net split % (+205A admit / -205B let-down)
                "mode": s.steam.pic205_mode,
            },
            "PIC_329207": {                      # 4-bar header (leg-B alias; PV=LP header P)
                "pv":   round(s.steam.P_LP, 2),                     # bar a
                "sp":   round(s.steam.pic207_sp, 2),
                "op":   round(s.steam.m_pic * 3.6, 2),             # net vent(+)/make-up(-) t/h
                "mode": s.steam.pic207_mode,
            },
            "MASTER_SP_329207": {                # 4-bar header MASTER SP faceplate (ON/OFF cascade)
                "on": s.steam.master207_on,
                "sp": round(s.steam.master207_sp, 2),              # bar a
                "pv": round(s.steam.P_LP, 2),
            },
            "PIC_329207A": {                     # vent PV-329207A (SP = master + 0.1)
                "pv":   round(s.steam.P_LP, 2),
                "sp":   round(s.steam.pic207a_sp, 2),
                "op":   round(s.steam.pv207a_pct, 1),              # valve %
                "mode": s.steam.pic207a_mode,
            },
            "PIC_329207B": {                     # turbine 320MT02 export PV-329207B (SP = master)
                "pv":   round(s.steam.P_LP, 2),
                "sp":   round(s.steam.pic207_sp, 2),
                "op":   round(s.steam.pv207b_pct, 1),              # valve %
                "m_turbine_th": round(s.steam.m_turbine * 3.6, 2),
                "mode": s.steam.pic207_mode,
            },
            "PIC_329207C": {                     # BL admit PV-329207C (SP = master - 0.1)
                "pv":   round(s.steam.P_LP, 2),
                "sp":   round(s.steam.pic207c_sp, 2),
                "op":   round(s.steam.valve_963_pct, 1),           # valve %
                "mode": s.steam.pic207c_mode,
            },
            "LIC_329502": {                      # 329D005 HP-saturator level -> LV-329502 drain to 329D009
                "pv":   round(s.steam.lic502_lvl, 1),              # level %
                "sp":   round(s.steam.lic502_sp, 1),
                "op":   round(s.steam.lic502_op, 1),               # LV-329502 %
                "mode": s.steam.lic502_mode,
            },
            "LIC_329503": {                      # 329D009 MP-drum level -> LV-329503 drain to 322D001A/B
                "pv":   round(s.steam.lic503_lvl, 1),              # level %
                "sp":   round(s.steam.lic503_sp, 1),
                "op":   round(s.steam.lic503_op, 1),               # LV-329503 %
                "mode": s.steam.lic503_mode,
            },
            "LIC_329504": {                      # 322D001A/B LP-drum level -> LV-329504 make-up f.329P001
                "pv":   round(s.steam.lic504_lvl, 1),              # level %
                "sp":   round(s.steam.lic504_sp, 1),
                "op":   round(s.steam.lic504_op, 1),               # LV-329504 %
                "mode": s.steam.lic504_mode,
            },
        },
        "REACT_322R001": {                       # HP Urea Reactor 322R001 -> 322E001 / 322E003
            "TT_322005":   round(s.react_T_node[3], 1),  # N6 A top (EL +21700) — node-4 DYNAMIC profile
            "TT_322006":   round(s.react_T_node[2], 1),  # N6 B     (EL +14800) — node-3 DYNAMIC profile
            "TT_322007":   round(s.react_T_node[1], 1),  # N6 C     (EL  +7900) — node-2 DYNAMIC profile
            "TT_322008":   round(s.react_T_node[0], 1),  # N6 D bot (EL  +1000) — node-1 DYNAMIC profile
            "TT_322009":   round(react["T_offgas"], 1),      # off-gas line -> 322E003 (C, live profile)
            "LT_322504":   round(s.react_lt322504_pct, 1),   # N7 narrow-band reading (1.5 m span, top tap 1 m above overflow) — DYNAMIC
            "AT_322701":   round(d_AT322701, 3),  # N/C molar ratio ->322E001 (lagged analyzer)
            "HIC_322605":  round(s.HIC_322605, 1),           # overflow valve controller (%)
            "HV_322605":   round(s.HIC_322605, 1),           # HV-322605 opening (tracks HIC 1:1)
            "P_bara":      round(react["P_bara"], 1),        # reactor pressure (bar a)
            "P_offgas":    round(react["P_offgas"], 1),      # off-gas line pressure (bar a)
            "closure_resid": round(react["closure_resid"], 2),  # mass-closure diag (kmol/h, not injected)
            "X_conv":      round(react["X_conv"] * 100.0, 2),    # per-pass CO2->urea conversion (%) — Inoue-Kanai
            "L_feed":      round(react["L_feed"], 3),            # reactor-feed N/C molar (NH3/CO2)
            "W_feed":      round(react["W_feed"], 4),            # reactor-feed H/C molar (H2O/CO2) — water-penalty driver
            "xi_urea":     round(react["xi_urea"], 2),           # urea-formation extent (kmol/h, conversion-coupled)
        },
        "SCRUB_322E003": {                       # HP Scrubber 322E003 -> 322C001 (off-gas) / 322F001 (overflow)
            "TT_322009":   round(react["T_offgas"], 1),      # reactor off-gas feed in (C)
            "TT_322011":   round(d_TT322011, 1),      # off-gas temp -> HV-322604 (C, lagged)
            "off_th":      streams["SCRUB_OFFGAS"]["mass_th"],   # off-gas mass flow (t/h)
            "off_mol":     streams["SCRUB_OFFGAS"]["mol_kmolh"], # off-gas molar flow (kmol/h)
            "off_MW":      streams["SCRUB_OFFGAS"]["MW"],        # off-gas mean MW
            "off_mol_pct": streams["SCRUB_OFFGAS"]["mol_pct"],   # off-gas composition (mol %)
            "ov_th":       streams["CARB_RECYCLE"]["mass_th"],   # overflow mass flow (t/h)
            "ov_mol":      streams["CARB_RECYCLE"]["mol_kmolh"], # overflow molar flow (kmol/h)
            "ov_MW":       streams["CARB_RECYCLE"]["MW"],        # overflow mean MW
            "ov_mass_pct": streams["CARB_RECYCLE"]["mass_pct"],  # overflow composition (mass %)
            "carb_th":     round(sum(scrub["carb_kmolh"][k] * MW_COMP[k] for k in MW_COMP) / 1000.0, 3),  # 323P001 wash (t/h)
            "closure_resid": round(scrub["closure_resid"], 2),  # tube-side mole-balance diag (kmol/h, not injected)
            "HV_322604":   round(s.HIC_322604, 1),           # HV-322604 opening (tracks HIC 1:1)
            "HIC_322604":  round(s.HIC_322604, 1),           # off-gas valve controller (%)
            "TT_322011_lp":round(d_TT322011l, 1),        # off-gas T after HV-322604 (JT-cooled, C, lagged)
            "og_lp_th":    round(hv604["mass_kgh"] / 1000.0, 3),  # HV-322604 vented off-gas mass flow (t/h, live)
            "vent_frac":   round(scrub["vent_frac"], 4),     # HV-322604 vent capacity / required purge (<1 -> PT rises)
            "P_offgas":    round(scrub["P_offgas"], 1),      # off-gas line P (bar a)
            "P_overflow":  round(scrub["P_overflow"], 1),    # PT-329201 overflow line P (bar a)
            "TT_322002":   round(d_TT322002, 1),    # overflow temp -> 322F001 (C, lagged)
            # Option 3: LT-329501 now reads the TRUE 322E003 sump inventory state (holdup ODE):
            #     50% design NLL when cond==entrain; RISES on ejector stall as entrainment collapses.
            "LT_329501":   round(s.scrub_level_pct, 1),  # 322E003 sump level (%, true dynamic inventory)
            "ccw": {                              # shell-side CCW loop (329P006 A/B pump + 329E004 cooler)
                "TT_329125":  round(d_TT329125, 2),     # CCW return temp out of shell (C, lagged)
                "TDY_329125": round(TDY_329125, 2),             # TT-329125 − TIC-329005 (cond. quality, C) — live PT-329201 cascade
                "vent_ratio": round(scrub["vent_ratio"], 4),    # synthesis-vent load PT-329201/PT_des (= nu, prior-step state)
                "rho_cond":   round(scrub["rho_cond"], 4),      # condensation capacity/demand (CCW flow / vent load); <1 -> PT-329201 rises
                "co2_free":   round(scrub["co2_free"], 1),      # free acid CO2 overhead (pressure-building, kmol/h)
                "pb_push":    round(scrub["pb_push"], 5),       # PT forward push = pressure-building overhead deviation (0 at design)
                "PI_322E002": round(d_HPCC_P, 1),    # 322E002 HPCC bubble-point synthesis P (bar a, lagged)
                "Q_ccw_kW":   round(scrub["q_ccw_kw"], 0),      # heat removed by CCW (kW)
                "Q_carb_kW":  round(scrub["q_carb_kw"], 0),     # carbamate exotherm (diag, kW)
                "co2_abs":    round(scrub["co2_abs"], 2),       # CO2 absorbed gas->carbamate (kmol/h)
                "FIC_329409": {"pv": round(fic["pv"], 1), "sp": round(fic["sp"], 1),
                               "op": round(fic["op"], 1), "mode": fic["mode"]},  # CCW flow (t/h) -> FV-329409
                "TIC_329005": {"pv": round(tic["pv"], 1), "sp": round(tic["sp"], 1),
                               "op": round(tic["op"], 1), "mode": tic["mode"]},  # CCW supply T (C) -> TV-329005
                "P329P006_in":  round(SCRUB_CCW_P_OUT_BARA, 1), # 329P006 A/B suction P (CCW return)
                "P329P006_out": round(SCRUB_CCW_P_IN_BARA, 1),  # 329P006 A/B discharge P (CCW supply)
                "E004_duty_kW": round(q_e004_kw, 0),            # 329E004 tempered-water-cooler duty (kW)
            },
        },
        # AUDIT F-8/TD-009: downstream component species balance (mass %).  `sum` is the C6
        # summation residual per stage and must read 100.000 at all times; `vap` is the live
        # relative-volatility vapour composition leaving each stage.
        "SPECIES_323_324": {
            "liq": {tag: {k: round(w[k] * 100.0, 4) for k in SOL_SPECIES} for tag, w in (
                ("C003", s.w_c003), ("F004", s.w_f004), ("F010", s.w_f010),
                ("D002", s.w_d002), ("E001", s.w_e001), ("E003", s.w_e003))},
            "vap": {tag: {k: round(y[k] * 100.0, 4) for k in SOL_SPECIES} for tag, y in (
                ("305", y_305), ("701", y_701), ("evap", y_evap), ("v1", y_v1), ("v2", y_v2))},
            "sum": {tag: round(sum(w.values()) * 100.0, 6) for tag, w in (
                ("C003", s.w_c003), ("F004", s.w_f004), ("F010", s.w_f010),
                ("D002", s.w_d002), ("E001", s.w_e001), ("E003", s.w_e003))},
            "xi_biuret_kmolh": {"C003": round(xi_c003, 5), "F004": round(xi_f004, 5),
                                "F010": round(xi_f010, 5), "E001": round(xi_e001, 5),
                                "E003": round(xi_e003, 5)},
            # AUDIT C7 — _sol_stage_anchor's clip residual was computed and RETURNED but never read
            # by any caller, contradicting its own docstring ("The clip residual is reported, never
            # hidden").  It is the negative vapour flow the anchor had to clamp to zero and back-charge
            # to water, i.e. mass the PFD's own rounded stream table cannot produce.  E001 carries
            # -170.1 kg/h (1.21 % of the stage vapour) and E003 -126.8 kg/h (4.63 %), both far above
            # the "under 0.4 % everywhere else" the docstring claims.  Published so a future change
            # that widens the clip cannot do it silently.
            "clip_resid_kgh": {tag: round(st.get("resid", 0.0), 3) for tag, st in (
                ("C003", SOL_C003), ("F004", SOL_F004), ("F010", SOL_F010),
                ("E001", SOL_E001), ("E003", SOL_E003))},
            "urea_pct_species": {"E001": round(s.w_e001["Urea"] * 100.0, 2),
                                 "E003": round(s.w_e003["Urea"] * 100.0, 2)},
            # AUDIT F-8: the desorption train's own species vectors.  The two ppm figures are now a
            # MASS-BALANCE result rather than the read-only ppm_infer_328701 soft sensor -- AI-328701
            # can finally be read against something the plant model actually computes.
            "des_liq": {tag: {k: round(w[k] * 100.0, 6) for k in SOL_SPECIES} for tag, w in (
                ("C002", s.w_328c002), ("C003", s.w_328c003), ("C004", s.w_328c004))},
            "des_vap": {tag: {k: round(y[k] * 100.0, 4) for k in SOL_SPECIES} for tag, y in (
                ("737", y_737), ("748", y_748), ("750", y_750))},
            "des_sum": {tag: round(sum(w.values()) * 100.0, 6) for tag, w in (
                ("C002", s.w_328c002), ("C003", s.w_328c003), ("C004", s.w_328c004))},
            "condensate_ppm": {"NH3": round(s.w_328c004["NH3"] * 1e6, 3),
                               "Urea": round(s.w_328c004["Urea"] * 1e6, 3),
                               "CO2": round(s.w_328c004["CO2"] * 1e6, 3)},
            "xi_hydrolysis_kmolh": round(xi_hyd_328, 5),
        },
        "STREAMS": streams,
        "flags":   {k: v for k, v in s.flags.items()},
        "ratio": {
            "SP":  round(s.ratio_SP, 3),
            "PV":  round(s.ratio_PV, 3),
            "bal": round(s.ratio_bal, 3),
            "NC_A": round(NC_A, 3),           # N/C ratio 321P002A (molar)
            "NC_B": round(NC_B, 3),           # N/C ratio 321P002B (molar)
        },
        "ext_override": s.ext_override,
        "sim_mode": s.sim_mode,                           # "SLOW" (real-time) | "FAST" (accelerated)
        "sim_speed": SIM_SPEED.get(s.sim_mode, 1.0),      # sim-s advanced per real-s in the active mode
        "trips": s.trips,
        "trip_latched": s.trip_latched,
        "controllers": {tag: ctrl.to_packet()
                        for tag, ctrl in s.controllers.items()},
    }