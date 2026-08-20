"""Regression checks for source-safe stream-state corrections from the full model audit."""

import main


def test_stream_retains_component_flows_and_marks_unknown_enthalpy():
    stream = main.make_stream(
        {"NH3": 10.0, "CO2": 2.0}, 100.0, 144.2,
        "audit", "A", "B", "gas",
    )
    assert stream["component_kmolh"]["NH3"] == 10.0
    assert stream["component_kgh"]["CO2"] == 2.0 * main.MW_COMP["CO2"]
    assert stream["enthalpy_kJkg"] is None
    assert stream["enthalpy_flow_kW"] is None


def test_registry_uses_live_co2_line_and_stripper_pressures():
    main.state = main.State()
    main.state.p_syn_bara = 130.0
    expected_strip_p = main.STRIP_P_DES_BARA * 130.0 / main.SYN_P_DES_BARA

    packet = main.step_sim(0.1)
    streams = packet["STREAMS"]

    assert streams["CO2_FEED"]["P_bara"] == round(packet["CO2_FEED"]["PIC_322203"], 1)
    assert streams["STRIP_TOP"]["P_bara"] == round(expected_strip_p, 1)
    assert streams["STRIP_BOT"]["P_bara"] == round(expected_strip_p, 1)


def test_lp_header_temperature_is_thermodynamically_tied_to_live_pressure():
    main.state = main.State()
    main.state.steam.P_LP = 6.5

    packet = main.step_sim(0.1)
    lp = packet["STEAM_SYSTEM"]["LP"]

    assert lp["TI_sat"] == round(main.tsat_steam(lp["P_bara"]), 1)
    assert "TI_HPCC_shell" in lp

