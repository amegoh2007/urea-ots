"""322E003 HP Scrubber self-test (binds 322E003, HV-322604, 329P006 A/B, 329E004).
Saturated-inert vent, overflow by difference (report A-2): design lands on PFD 204 / 206.
Plain asserts (repo has no pytest). Run:  python backend/test_scrubber.py"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
from main import MW_COMP


def test_constants_present():
    for name in ("SCRUB_CARB_KGH_DES", "SCRUB_CARB_MASSPCT", "SCRUB_CARB_KMOLH_DES",
                 "SCRUB_OFFGAS_MOLPCT", "SCRUB_OFFGAS_MOL_DES", "SCRUB_OFFGAS_KMOLH_DES",
                 "SCRUB_OVERFLOW_KMOLH_DES", "SCRUB_OFFGAS_T_C", "SCRUB_OFFGAS_P_BARA",
                 "SCRUB_OVERFLOW_T_C", "SCRUB_OVERFLOW_P_BARA", "SCRUB_OFFGAS_RHO",
                 "SCRUB_DH_CARB_KJMOL", "SCRUB_HIC604_DES_PCT", "SCRUB_HV604_P_OUT",
                 "SCRUB_HV604_MU_JT", "SCRUB_CCW_KGH_DES", "SCRUB_CCW_CP",
                 "SCRUB_CCW_T_IN_DES", "SCRUB_CCW_T_OUT_DES", "SCRUB_CCW_P_IN_BARA",
                 "SCRUB_CCW_P_OUT_BARA", "SCRUB_FV409_DES_PCT", "SCRUB_TV005_DES_PCT",
                 "SCRUB_Q_CCW_DES_KW"):
        assert hasattr(main, name), "missing constant %s" % name
    # overflow design vector IS the ejector-suction stream (kg/h -> kmol/h, single source)
    for k in MW_COMP:
        assert abs(main.SCRUB_OVERFLOW_KMOLH_DES[k]
                   - main.EJ_SUCTION_KGH[k] / MW_COMP[k]) < 1e-9, k
    # CCW design duty Q = m·cp·ΔT = 306000·4.18·15/3600 = 5329.5 kW
    assert abs(main.SCRUB_Q_CCW_DES_KW - 5329.5) < 0.5, main.SCRUB_Q_CCW_DES_KW
    # State defaults
    assert abs(main.state.HIC_322604 - 50.0) < 1e-9
    assert main.state.FIC_329409["mode"] == "AUTO"
    assert main.state.TIC_329005["mode"] == "AUTO"
    assert abs(main.state.FIC_329409["sp"] - 306.0) < 1e-9
    assert abs(main.state.TIC_329005["sp"] - 80.0) < 1e-9


def _design():
    """Scrubber at design: live reactor off-gas feed, s=1, CCW 80 C / 306 t/h."""
    return main.scrub_322e003(main.REACT_OFFGAS_DES, 1.0,
                              main.SCRUB_CCW_T_IN_DES, main.SCRUB_CCW_KGH_DES)


def test_design_identity_discharges():
    sc = _design()
    # off-gas pinned -> img1 (322E003 -> 322C001); overflow pinned -> ejector suction
    for k in MW_COMP:
        assert abs(sc["offgas_kmolh"][k] - main.SCRUB_OFFGAS_KMOLH_DES[k]) < 1e-9, k
        assert abs(sc["overflow_kmolh"][k] - main.SCRUB_OVERFLOW_KMOLH_DES[k]) < 1e-9, k
    assert abs(sc["co2_scale"] - 1.0) < 1e-9
    assert abs(sc["T_offgas"] - 114.0) < 1e-9 and abs(sc["P_offgas"] - 140.7) < 1e-9
    assert abs(sc["T_overflow"] - 178.8) < 1e-9 and abs(sc["P_overflow"] - 140.7) < 1e-9


def test_offgas_hmb():
    sc = _design()
    og = sc["offgas_kmolh"]
    n_tot = sum(og.values())
    # Report A-2: every inert of the PFD 203 off-gas, saturated with NH3/CO2/H2O at the PFD 204 mole
    # fractions -- so the design vent IS stream 204 (64.78 kmol/h, 1708 kg/h, MW 26.36), not the
    # Path-B 214.8 kmol/h / 5901 kg/h vent that carried 89 NH3 + 61 CO2 kmol/h of the overflow.
    assert abs(n_tot - 64.78) < 0.05, n_tot                       # PFD 204 molar flow
    mass = sum(og[k] * MW_COMP[k] for k in MW_COMP)
    assert abs(mass - 1708.0) < 1.0, mass                         # PFD 204 mass flow
    assert abs(mass / n_tot - 26.36) < 0.05, mass / n_tot         # PFD 204 mean MW
    for k, pct in main.SCRUB_OFFGAS_MOLPCT.items():               # PFD 204 mol %
        assert abs(og[k] / n_tot * 100.0 - pct) < 0.1, (k, og[k] / n_tot * 100.0)
    for k in main.SCRUB_VENT_INERTS:                              # no inert is retained
        assert og[k] == sc["feed_kmolh"][k] and sc["overflow_kmolh"][k] == 0.0, k


def test_vent_is_the_inerts_saturated():
    """Double the inerts offered and the vent doubles, condensable slip included; the rest condenses."""
    feed = dict(main.REACT_OFFGAS_DES)
    for k in main.SCRUB_VENT_INERTS:
        feed[k] *= 2.0
    base, rich = _design(), main.scrub_322e003(feed, 1.0, main.SCRUB_CCW_T_IN_DES, main.SCRUB_CCW_KGH_DES)
    for k in MW_COMP:
        assert abs(rich["offgas_kmolh"][k] - 2.0 * base["offgas_kmolh"][k]) < 1e-9, k
        assert abs(rich["feed_kmolh"][k] - rich["offgas_kmolh"][k] - rich["overflow_kmolh"][k]) < 1e-9, k
    assert abs(rich["overflow_kmolh"]["NH3"]
               - (base["overflow_kmolh"]["NH3"] - base["offgas_kmolh"]["NH3"])) < 1e-9
    assert abs(rich["closure_resid"]) < 1e-9


def test_overflow_equals_ej_suction():
    sc = _design()
    mass = sum(sc["overflow_kmolh"][k] * MW_COMP[k] for k in MW_COMP)
    assert abs(mass - sum(main.EJ_SUCTION_KGH.values())) < 1e-6, mass  # 57 561.3 kg/h
    assert abs(mass - 57564.0) < 5.0, mass                              # PFD 206 mass flow
    assert abs(sum(sc["overflow_kmolh"].values()) - 2517.69) < 0.3      # PFD 206 molar flow


def test_closure_resid():
    sc = _design()
    cr = sc["closure_resid"]                                      # feed − off-gas − overflow
    assert abs(cr) < 1e-6, cr                                     # ≈ 0 (Path-B reconciled: node closes machine-exact)
    feed_tot = sum(sc["feed_kmolh"].values())
    assert abs(cr) / feed_tot < 0.002                             # bounded < 0.2 %


def test_ccw_energy_balance():
    sc = _design()
    assert abs(sc["q_ccw_kw"] - 5329.5) < 0.5, sc["q_ccw_kw"]     # Q_ccw at design
    assert abs(sc["dT_ccw"] - 15.0) < 0.05, sc["dT_ccw"]         # ΔT = Q·3600/(m·cp)
    assert abs(sc["t_ccw_out"] - 95.0) < 0.05, sc["t_ccw_out"]    # TT-329125 return
    # TDY-329125 = TT-329125 − TIC-329005 (condensation-quality indication)
    assert abs((sc["t_ccw_out"] - sc["t_ccw_in"]) - 15.0) < 0.05


def test_ccw_flow_throttle():
    # halve CCW circulation -> ΔT climbs, but GAP #2 ε-NTU bounds it (NOT the old linear
    # q/(ṁ·cp) doubling to 30.0, which was the ṁ_ccw -> 0 divide-by-zero pole). At m/2:
    #   ε = 1−exp(−UA/C_ccw) = 0.2806 ; t_overflow = min(80+q/ua_eff, 185) = 185 (hits ceiling)
    #   t_ccw_out = 80 + (185−80)·0.2806 = 109.46 ; ΔT = 29.46 (just shy of the linear 30.0)
    sc = main.scrub_322e003(main.REACT_OFFGAS_DES, 1.0,
                            main.SCRUB_CCW_T_IN_DES, main.SCRUB_CCW_KGH_DES / 2.0)
    assert abs(sc["dT_ccw"] - 29.46) < 0.1, sc["dT_ccw"]
    assert abs(sc["t_ccw_out"] - 109.46) < 0.1, sc["t_ccw_out"]
    assert abs(sc["T_overflow"] - 185.0) < 0.1, sc["T_overflow"]   # process ceiling reached


def test_scale_s080():
    # a consistent 80 % turndown: the off-gas offered AND the wash both at 0.8 (the vent follows the
    # inerts it is offered, so scaling s alone no longer scales it)
    sc = main.scrub_322e003({k: v * 0.8 for k, v in main.REACT_OFFGAS_DES.items()}, 0.8,
                            main.SCRUB_CCW_T_IN_DES, main.SCRUB_CCW_KGH_DES)
    assert abs(sc["co2_scale"] - 0.8) < 1e-9
    assert abs(sc["offgas_kmolh"]["N2"] - main.SCRUB_OFFGAS_KMOLH_DES["N2"] * 0.8) < 1e-9
    assert abs(sc["overflow_kmolh"]["NH3"] - main.SCRUB_OVERFLOW_KMOLH_DES["NH3"] * 0.8) < 1e-9
    assert abs(sc["q_ccw_kw"] - 5329.5 * 0.8) < 0.5                # Q scales with throughput


def test_hv322604_jt():
    sc = _design()
    hv = main.hv_322604(sc["offgas_kmolh"], sc["T_offgas"], main.SCRUB_HIC604_DES_PCT, sc["P_offgas"])
    # isenthalpic JT: T_out = T_in − μ_JT·ΔP = 114 − 0.55·(140.7−4) = 38.8 C
    assert abs(hv["T_out"] - 38.8) < 0.05, hv["T_out"]
    assert abs(hv["P_out"] - 4.0) < 1e-9                          # 322C001 LP-absorber P
    assert abs(hv["open_pct"] - 50.0) < 1e-9                      # HIC sets opening 1:1
    # composition preserved across the valve (steam-traced, no desublimation)
    for k in MW_COMP:
        assert abs(hv["comp_kmolh"][k] - sc["offgas_kmolh"][k]) < 1e-12, k
    assert abs(hv["mass_kgh"] - sum(sc["offgas_kmolh"][k] * MW_COMP[k] for k in MW_COMP)) < 1e-6


def test_packet_tags_and_streams():
    main.state = main.State()                 # fresh design SS (sibling tests integrate PT/state)
    pkt = main.step_sim(1.0)
    assert "SCRUB_322E003" in pkt
    blk = pkt["SCRUB_322E003"]
    for tag in ("TT_322009", "TT_322011", "off_th", "off_mol", "off_MW", "off_mol_pct",
                "ov_th", "ov_mol", "ov_MW", "ov_mass_pct", "carb_th", "closure_resid",
                "HV_322604", "HIC_322604", "TT_322011_lp", "P_offgas", "P_overflow",
                "TT_322002", "LT_329501", "ccw"):
        assert tag in blk, tag
    for tag in ("TT_329125", "TDY_329125", "Q_ccw_kW", "Q_carb_kW", "co2_abs",
                "FIC_329409", "TIC_329005", "P329P006_in", "P329P006_out", "E004_duty_kW"):
        assert tag in blk["ccw"], tag
    # off-gas composition closes; design point pins MW / mol% / temps
    assert abs(sum(blk["off_mol_pct"].values()) - 100.0) < 0.2
    assert abs(blk["off_MW"] - 26.36) < 0.05                      # PFD 204 off-gas mean MW (A-2)
    assert abs(blk["TT_322011"] - 114.0) < 0.1
    assert abs(blk["TT_322011_lp"] - 38.8) < 0.1                  # JT-cooled off-gas to 322C001
    assert abs(blk["TT_322002"] - 178.8) < 0.1
    assert abs(blk["P_offgas"] - 140.7) < 0.1 and abs(blk["P_overflow"] - 140.7) < 0.1
    assert abs(blk["HV_322604"] - blk["HIC_322604"]) < 1e-9       # valve tracks controller 1:1
    # CCW shell-side at design: TT-329125 = 95, TDY = 15, loop closure E004 == Q_ccw
    assert abs(blk["ccw"]["TT_329125"] - 95.0) < 0.5
    assert abs(blk["ccw"]["TDY_329125"] - 15.0) < 0.5
    assert abs(blk["ccw"]["E004_duty_kW"] - blk["ccw"]["Q_ccw_kW"]) < 1.0   # 329E004 duty = CCW pickup
    # PT-329201 / TT-322002 re-pointed to live scrubber overflow (in ejector group)
    ej = pkt["EJ_322F001"]
    assert abs(ej["TI_322002"] - 178.8) < 0.1
    assert abs(ej["PI_329201"] - 140.7) < 0.1
    # new stream hotspots registered with correct src/dst
    st = pkt["STREAMS"]
    for key in ("SCRUB_OFFGAS", "SCRUB_OFFGAS_LP", "CCW_SUPPLY", "CCW_RETURN"):
        assert key in st, key
    assert st["SCRUB_OFFGAS"]["dst"] == "HV-322604"
    assert st["SCRUB_OFFGAS_LP"]["src"] == "HV-322604" and st["SCRUB_OFFGAS_LP"]["dst"] == "322C001"
    assert st["CCW_SUPPLY"]["src"] == "329P006 A/B" and st["CCW_SUPPLY"]["dst"] == "322E003"
    assert st["CCW_RETURN"]["src"] == "322E003" and st["CCW_RETURN"]["dst"] == "329P006 A/B"
    # CARB_RECYCLE re-pointed to live scrubber overflow (322E003 -> 322F001)
    assert st["CARB_RECYCLE"]["src"] == "322E003" and st["CARB_RECYCLE"]["dst"] == "322F001"
    assert abs(st["CARB_RECYCLE"]["mol_kmolh"] - 2517.69) < 0.5    # PFD 206 molar flow (A-2)


def test_hic604_command():
    main.state.HIC_322604 = 50.0
    main.handle_cmd({"type": "hic604_set", "id": "HIC-322604", "mode": "MAN", "op": 70.0})
    assert abs(main.state.HIC_322604 - 70.0) < 1e-9
    main.handle_cmd({"type": "hic604_set", "id": "HIC-322604", "mode": "MAN", "op": 130.0})
    assert abs(main.state.HIC_322604 - 100.0) < 1e-9              # clamp high
    main.handle_cmd({"type": "hic604_set", "id": "HIC-322604", "mode": "MAN", "op": -5.0})
    assert abs(main.state.HIC_322604 - 0.0) < 1e-9               # clamp low
    main.state.HIC_322604 = 50.0                                  # restore design default


def test_fic_tic_man_modes():
    s = main.state
    # FIC-329409 MAN: CCW flow follows FV-329409 opening (30 % of 60 % design -> 153 t/h)
    main.handle_cmd({"type": "fic_set", "id": "FIC-329409", "mode": "MAN", "op": 30.0})
    # TIC-329005 MAN: supply T follows TV-329005 (25 % of 50 % design -> 95−15·0.5 = 87.5 C)
    main.handle_cmd({"type": "tic_set", "id": "TIC-329005", "mode": "MAN", "op": 25.0})
    for _ in range(150):                         # F4: PV is now a first-order plant lag — settle it
        blk = main.step_sim(1.0)["SCRUB_322E003"]["ccw"]
    assert abs(blk["FIC_329409"]["pv"] - 153.0) < 0.5, blk["FIC_329409"]["pv"]
    assert blk["FIC_329409"]["mode"] == "MAN"
    assert abs(blk["TIC_329005"]["pv"] - 87.5) < 0.5, blk["TIC_329005"]["pv"]
    # restore AUTO + design defaults for later tests
    main.handle_cmd({"type": "fic_set", "id": "FIC-329409", "mode": "AUTO"})
    main.handle_cmd({"type": "tic_set", "id": "TIC-329005", "mode": "AUTO"})
    s.FIC_329409["op"] = main.SCRUB_FV409_DES_PCT
    s.TIC_329005["op"] = main.SCRUB_TV005_DES_PCT


def test_fic_tic_auto_valve_tracks_sp():
    """AUTO regression: changing SP must move the valve opening (inverse of MAN char.).
    Guards the bug where boundary loops held pv=sp but left op frozen at design %."""
    main.state = main.State()    # isolate on fresh design SS so the exotherm load (t_load) is 0
    s = main.state
    ccw_des_th = main.SCRUB_CCW_KGH_DES / 1000.0
    dT_des     = main.SCRUB_CCW_T_OUT_DES - main.SCRUB_CCW_T_IN_DES
    # FIC-329409 AUTO: op = FV_DES · sp / ccw_des  (linear valve inverse)
    main.handle_cmd({"type": "fic_set", "id": "FIC-329409", "mode": "AUTO"})
    main.handle_cmd({"type": "fic_set", "id": "FIC-329409", "sp": 1.2 * ccw_des_th})
    for _ in range(400):                          # F4: settle velocity I-PD + plant lag to SS
        fic = main.step_sim(1.0)["SCRUB_322E003"]["ccw"]["FIC_329409"]
    assert abs(fic["op"] - 1.2 * main.SCRUB_FV409_DES_PCT) < 0.5, fic["op"]
    assert abs(fic["pv"] - 1.2 * ccw_des_th) < 0.5, fic["pv"]          # boundary: pv==sp preserved
    # TIC-329005 AUTO: op = TV_DES · (T_OUT_DES − sp)/dT  (cooler valve inverse)
    main.handle_cmd({"type": "tic_set", "id": "TIC-329005", "mode": "AUTO"})
    main.handle_cmd({"type": "tic_set", "id": "TIC-329005", "sp": main.SCRUB_CCW_T_IN_DES + 5.0})
    for _ in range(400):                          # F4: settle velocity I-PD + plant lag to SS
        tic = main.step_sim(1.0)["SCRUB_322E003"]["ccw"]["TIC_329005"]
    exp = main.SCRUB_TV005_DES_PCT * (main.SCRUB_CCW_T_OUT_DES - (main.SCRUB_CCW_T_IN_DES + 5.0)) / dT_des
    assert abs(tic["op"] - exp) < 0.5, tic["op"]
    assert abs(tic["pv"] - (main.SCRUB_CCW_T_IN_DES + 5.0)) < 0.5, tic["pv"]
    # design-point identity: at design SP the valve returns to its design opening
    main.handle_cmd({"type": "fic_set", "id": "FIC-329409", "sp": ccw_des_th})
    main.handle_cmd({"type": "tic_set", "id": "TIC-329005", "sp": main.SCRUB_CCW_T_IN_DES})
    for _ in range(400):                          # F4: settle back to design opening at design SP
        ccw = main.step_sim(1.0)["SCRUB_322E003"]["ccw"]
    assert abs(ccw["FIC_329409"]["op"] - main.SCRUB_FV409_DES_PCT) < 0.5, ccw["FIC_329409"]["op"]
    assert abs(ccw["TIC_329005"]["op"] - main.SCRUB_TV005_DES_PCT) < 0.5, ccw["TIC_329005"]["op"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    fails = 0
    for t in tests:
        try:
            t(); print("PASS", t.__name__)
        except Exception:
            fails += 1; print("FAIL", t.__name__); traceback.print_exc()
    raise SystemExit(1 if fails else 0)
