"""Regression gates for the 324 vacuum train and supplied stream maps."""

import math

import main


def test_lmtd_handles_equal_terminal_differences():
    assert main.lmtd_countercurrent(80.0, 60.0, 20.0, 40.0) == 40.0


def test_lmtd_rejects_a_temperature_cross():
    assert main.lmtd_countercurrent(40.0, 30.0, 30.0, 40.0) == 0.0


def test_condenser_design_points_close_mass_and_energy():
    for tag, spec in main.VACUUM_CONDENSERS.items():
        node = main.vacuum_condenser_node(
            spec,
            inlet_kgh=spec["inlet_kgh"],
            noncondensable_kgh=spec["vent_kgh"],
            hot_in_c=spec["hot_in_c"],
        )
        assert math.isclose(node["condensate_kgh"], spec["condensate_kgh"], abs_tol=1e-8), tag
        assert math.isclose(node["vent_kgh"], spec["vent_kgh"], abs_tol=1e-8), tag
        assert math.isclose(node["q_kw"], spec["q_kw"], abs_tol=1e-8), tag
        assert math.isclose(node["cw_out_c"], spec["cw_out_c"], abs_tol=1e-8), tag
        assert abs(node["mass_residual_kgh"]) <= 1e-9, tag
        assert abs(node["energy_residual_kw"]) <= 1e-9, tag


def test_zero_cooling_water_sends_the_inlet_to_the_gas_outlet():
    spec = main.VACUUM_CONDENSERS["324E002"]
    node = main.vacuum_condenser_node(
        spec,
        inlet_kgh=spec["inlet_kgh"],
        noncondensable_kgh=spec["vent_kgh"],
        hot_in_c=spec["hot_in_c"],
        cw_flow_kgh=0.0,
    )
    assert node["q_kw"] == 0.0
    assert node["condensate_kgh"] == 0.0
    assert node["vent_kgh"] == spec["inlet_kgh"]


def test_more_noncondensable_gas_derates_the_condenser():
    spec = main.VACUUM_CONDENSERS["324E002"]
    base = main.vacuum_condenser_node(
        spec, spec["inlet_kgh"], spec["vent_kgh"], spec["hot_in_c"],
    )
    loaded = main.vacuum_condenser_node(
        spec, spec["inlet_kgh"], 2.0 * spec["vent_kgh"], spec["hot_in_c"],
    )
    assert loaded["ua_eff_kw_k"] < base["ua_eff_kw_k"]
    assert loaded["condensate_kgh"] < base["condensate_kgh"]


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


def test_packet_exposes_each_condenser_and_numbered_stream():
    main.state = main.State()
    packet = main.step_sim(0.1)
    vacuum = packet["EVAP_324"]["VAC"]
    assert {"324E002", "324E005", "324E006", "324E007"} <= set(vacuum)
    for tag in ("324E002", "324E005", "324E006", "324E007"):
        assert {"Q_kW", "UA_kW_K", "LMTD_K", "cw_in_th", "cw_out_C",
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
