"""Regression gates for the 324 vacuum train and supplied stream maps."""

import math

import main


def test_lmtd_handles_equal_terminal_differences():
    assert main.lmtd_countercurrent(80.0, 60.0, 20.0, 40.0) == 40.0


def test_lmtd_rejects_a_temperature_cross():
    assert main.lmtd_countercurrent(40.0, 30.0, 30.0, 40.0) == 0.0


def test_condenser_design_points_close_mass_and_energy():
    """Every condenser reproduces its PFD condensate, vent and gas-outlet temperature at design, and
    its duty is the H0 enthalpy balance that UA was back-solved from (reports A-13 / B-9 / B-13)."""
    for tag, spec in main.VACUUM_CONDENSER_SPECS.items():
        pfd = main.VACUUM_CONDENSERS[tag]
        node = main.vacuum_condenser_node(tag, pfd["inlet_kgh"], spec["n_in_des"], spec["p_des"])
        assert math.isclose(node["condensate_kgh"], pfd["condensate_kgh"], abs_tol=1e-8), tag
        assert math.isclose(node["vent_kgh"], pfd["vent_kgh"], abs_tol=1e-8), tag
        assert abs(node["t_vent_c"] - pfd["hot_out_c"]) < 1e-6, tag
        assert math.isclose(node["q_kw"], spec["q_des_kw"], abs_tol=1e-6), tag
        assert abs(node["mass_residual_kgh"]) <= 1e-9, tag
        assert abs(node["energy_residual_kw"]) <= 1e-3, tag
    # the H0 balance on the PFD rows against the duty the PFD's cooling water carries
    e002 = main.VACUUM_CONDENSER_SPECS["324E002"]
    assert abs(e002["q_des_kw"] / main.VACUUM_CONDENSERS["324E002"]["q_kw"] - 1.0) < 0.03


def test_zero_cooling_water_sends_the_inlet_to_the_gas_outlet():
    spec = main.VACUUM_CONDENSER_SPECS["324E002"]
    node = main.vacuum_condenser_node("324E002", spec["inlet_kgh"], spec["n_in_des"], spec["p_des"],
                                      cw_flow_kgh=0.0)
    assert node["q_kw"] == 0.0
    assert node["condensate_kgh"] == 0.0
    assert node["vent_kgh"] == spec["inlet_kgh"]


def test_more_noncondensable_gas_carries_more_vapour_to_the_ejector():
    """Inert gas leaves saturated with vapour, so doubling it roughly doubles the vent (B-13)."""
    spec = main.VACUUM_CONDENSER_SPECS["324E002"]
    base = main.vacuum_condenser_node("324E002", spec["inlet_kgh"], spec["n_in_des"], spec["p_des"])
    n2 = dict(spec["n_in_des"])
    for k in ("N2", "O2"):
        n2[k] *= 2.0
    loaded = main.vacuum_condenser_node("324E002", spec["inlet_kgh"], n2, spec["p_des"])
    assert 1.8 * base["vent_kgh"] < loaded["vent_kgh"] < 2.2 * base["vent_kgh"]
    assert loaded["condensate_kgh"] < base["condensate_kgh"]


def test_a_lower_shell_pressure_leaves_more_vapour_uncondensed():
    for tag in ("324E002", "324E005"):
        spec = main.VACUUM_CONDENSER_SPECS[tag]
        hi = main.vacuum_condenser_node(tag, spec["inlet_kgh"], spec["n_in_des"], spec["p_des"] * 1.1)
        lo = main.vacuum_condenser_node(tag, spec["inlet_kgh"], spec["n_in_des"], spec["p_des"] * 0.9)
        assert lo["vent_kgh"] > spec["vent_kgh"] > hi["vent_kgh"], tag


def test_warmer_cooling_water_warms_the_cold_end_and_loads_the_ejector():
    """A-13: the gas outlet follows the cooling water; it used to be a frozen design approach."""
    spec = main.VACUUM_CONDENSER_SPECS["324E002"]
    warm = main.vacuum_condenser_node("324E002", spec["inlet_kgh"], spec["n_in_des"], spec["p_des"],
                                      cw_in_c=spec["cw_in_c"] + 5.0)
    assert warm["t_vent_c"] > spec["t_v_des"] + 3.0
    assert warm["vent_kgh"] > 1.3 * spec["vent_kgh"]


def test_condensation_heat_is_per_species():
    """B-9: one design kJ/kg per condenser is gone; NH3 and CO2 give up less than water per mole."""
    vc = main.vacuum_condenser
    lat = {k: vc._h_gas(k, 45.0) - vc._h_liq(k, 45.0) for k in ("H2O", "NH3", "CO2")}
    assert abs(lat["H2O"] / 1000.0 - 43.1) < 0.3            # IAPWS-IF97 at 45 C: 43.13 kJ/mol
    assert lat["H2O"] > lat["NH3"] > lat["CO2"] > 0.0
    assert "h_eff_kjkg" not in main.VACUUM_CONDENSERS["324E002"]


def test_the_vent_ammonia_and_co2_ride_their_own_back_pressure():
    """NH3 and CO2 used to follow water's saturation line on a fixed split.  The speciated
    back-pressure over the PFD's own 324E002 condensate (719) at 45 C, with no anchor, lands on the
    PFD 706 vent: p_NH3 0.054 against 0.059 bar, p_CO2 0.0085 against 0.013."""
    import packed_absorber
    w719 = {k: v / 100.0 for k, v in main.PFD_324_MASS_PCT["719"].items()}
    p_nh3, p_co2 = (x / 1e5 for x in packed_absorber.back_pressure(w719, 45.0)[:2])
    row = main.PFD_324_MASS_PCT["706"]
    assert abs(p_nh3 / (row["NH3"] / 100.0 * 0.33) - 1.0) < 0.15
    assert abs(p_co2 / (row["CO2"] / 100.0 * 0.33) - 1.0) < 0.40
    assert "bp_des" in main.VACUUM_CONDENSER_SPECS["324E002"]


def test_an_ammonia_rich_inlet_vents_more_ammonia_than_in_proportion():
    """More NH3 in what 324E002 condenses raises the NH3 back-pressure over the condensate faster than
    the NH3 itself, because less of it is bound to CO2: the vent carries it to the ejector."""
    spec = main.VACUUM_CONDENSER_SPECS["324E002"]
    base = main.vacuum_condenser_node("324E002", spec["inlet_kgh"], spec["n_in_des"], spec["p_des"])
    rich = dict(spec["n_in_des"])
    rich["NH3"] *= 1.3
    loaded = main.vacuum_condenser_node("324E002", spec["inlet_kgh"], rich, spec["p_des"])
    r_vent = loaded["vent_kmolh"]["NH3"] / base["vent_kmolh"]["NH3"]
    assert r_vent > 1.3
    assert loaded["vent_kgh"] > base["vent_kgh"]


def test_the_324e002_inlet_swaps_in_a_known_composition():
    """LV-323505's blow-through gas reaches 324E002 at its own composition, not the PFD row's."""
    spec = main.VACUUM_CONDENSER_SPECS["324E002"]
    fa = main.R324_F001_FA_DES
    base = main.vacuum_inlet_kmolh("324E002", spec["inlet_kgh"], fa, fa)
    assert main.vacuum_inlet_kmolh("324E002", spec["inlet_kgh"], fa, fa, (0.0, {"NH3": 1.0})) == base
    y = {"NH3": 0.31, "CO2": 0.10, "H2O": 0.59}
    swap = main.vacuum_inlet_kmolh("324E002", spec["inlet_kgh"], fa, fa, (1000.0, y))
    assert swap["NH3"] > base["NH3"] + 10.0
    assert swap["N2"] == base["N2"] and swap["O2"] == base["O2"]
    m = lambda n: sum(n[k] * main.vacuum_condenser.MW[k] for k in main.vacuum_condenser.SPECIES)
    assert abs(m(swap) - m(base)) < 1e-6 * m(base)                     # same mass, new composition


def test_vacuum_train_pfd_nodes_close_exactly():
    train = main.vacuum_train_324(
        main.R323_MEVAP_DES,
        main.R324_V1_DES,
        main.R324_V2_DES,
        main.R324_F001_FA_DES,
        main.R324_F003_FA_DES,
        main.R324_F002_MOTIVE_DES,
        main.R324_F004_MOTIVE_DES,
        main.R324_F005_MOTIVE_DES,
    )
    expected = {
        "703": 26840.0, "706": 72.0, "708": 462.0,
        "709": 3342.0, "712": 584.0, "714": 1804.0,
        "715": 41.0, "717": 221.0, "719": 26768.0,
        "720": 2758.0, "721": 1763.0, "722": 31.0,
        "759": 190.0,
    }
    for stream, mass in expected.items():
        assert math.isclose(train["streams_kgh"][stream], mass, abs_tol=1e-8), stream
    for name, inlet, outlets in (
        ("324E002", "703", ("719", "706")),
        ("324F002", "708", ("706", "924")),
        ("324E005", "709", ("720", "712")),
        ("324F004", "714", ("712", "927")),
        ("324E006", "714", ("721", "715")),
        ("324F005", "717", ("715", "929")),
        ("324E007", "717", ("759", "722")),
    ):
        lhs = train["streams_kgh"][inlet]
        rhs = sum(train["streams_kgh"][stream] for stream in outlets)
        assert math.isclose(lhs, rhs, abs_tol=1e-8), name


def test_a_deeper_324f003_vacuum_reaches_the_second_and_third_condensers_by_composition():
    base = main.vacuum_train_324(
        main.R323_MEVAP_DES, main.R324_V1_DES, main.R324_V2_DES, main.R324_F001_FA_DES,
        main.R324_F003_FA_DES, main.R324_F002_MOTIVE_DES, main.R324_F004_MOTIVE_DES,
        main.R324_F005_MOTIVE_DES)
    deep = main.vacuum_train_324(
        main.R323_MEVAP_DES, main.R324_V1_DES, main.R324_V2_DES, main.R324_F001_FA_DES,
        main.R324_F003_FA_DES, main.R324_F002_MOTIVE_DES, main.R324_F004_MOTIVE_DES,
        main.R324_F005_MOTIVE_DES, p_e005_bara=0.95 * main.R324_F003_P_BARA)
    assert deep["streams_kgh"]["712"] > base["streams_kgh"]["712"]
    assert deep["streams_kgh"]["714"] > base["streams_kgh"]["714"]
    assert deep["nodes"]["324E006"]["q_kw"] > base["nodes"]["324E006"]["q_kw"]


def test_packet_exposes_each_condenser_and_numbered_stream():
    main.state = main.State()
    packet = main.step_sim(0.1)
    vacuum = packet["EVAP_324"]["VAC"]
    assert {"324E002", "324E005", "324E006", "324E007"} <= set(vacuum)
    for tag in ("324E002", "324E005", "324E006", "324E007"):
        assert {"Q_kW", "UA_kW_K", "LMTD_K", "cw_in_th", "cw_out_C", "T_vent_C",
                "condensate_kgh", "vent_kgh", "mass_residual_kgh"} <= set(vacuum[tag])
    required = {
        "S0204", "S0341", "S0343", "S0702", "S0703", "S0705", "S0706",
        "S0708", "S0709", "S0712", "S0714", "S0715", "S0717", "S0719",
        "S0720", "S0721", "S0722", "S0744", "S0755", "S0756", "S0759",
        "S0783", "S0784", "S0797", "S0924", "S0927", "S0929", "S0954", "S1001", "S1014",
        "S1015", "S1016", "S1017", "S1018", "S1019", "S1020", "S1021", "S1051",
    }
    assert required <= set(packet["STREAMS"])


def test_absorber_mapping_reports_the_pfd_closure():
    main.state = main.State()
    packet = main.step_sim(0.1)
    c005 = packet["LPCC_3232"]["C005"]
    assert c005["in756_kgh"] == 33358.0
    assert c005["in702_kgh"] == 440.0
    assert c005["in708_kgh"] == 462.0
    assert c005["out343_kgh"] == 34180.0
    assert c005["out341_kgh"] == 80.0
    assert c005["closure_kgh"] == 0.0


def test_pfd_component_records_preserve_stream_total():
    stream = main.make_stream_mass_pct(
        72.0,
        main.PFD_324_MASS_PCT["706"],
        45.0,
        0.3,
        "706",
        "324E002",
        "324F002",
        "vapor",
    )
    assert stream["mass_kgh"] == 72.0
    assert abs(sum(stream["component_kgh"].values()) - 72.0) <= 1e-9


def test_vapour_rows_are_read_as_mole_percent():
    """PFD vapour rows are MOLE %: stream 706's published molar weight must be the PFD's 24.13, and
    the live vent carries the model's composition at the model's cold-end temperature."""
    main.state = main.State()
    packet = main.step_sim(0.1)
    s706 = packet["STREAMS"]["S0706"]
    assert abs(s706["MW"] - 24.13) < 0.15, s706["MW"]
    s703 = main.make_stream_mole_pct(26840.0, main.PFD_324_MASS_PCT["703"], 116.0, 0.3,
                                     "703", "a", "b", "vapor")
    assert abs(s703["MW"] - 18.45) < 0.05, s703["MW"]
    assert abs(sum(s703["component_kgh"].values()) - 26840.0) < 1e-6
