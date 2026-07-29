"""LV-324501 route contract from strict PFD-21 and 323D002 evidence."""

from __future__ import annotations

import main
import pytest


PFD_402G_KGH = 85_405.0
PFD_697_KGH = 694.0
PFD_609_KGH = 86_100.0


def _species_inventory(state: main.State) -> dict[str, float]:
    return {
        species: state.r323_d002_M_I * state.w_d002[species]
        for species in main.SOL_SPECIES
    }


def test_forward_route_mixes_402g_and_697_before_lv_a() -> None:
    route = main.route_lv324501(
        PFD_402G_KGH,
        main.W_S402G,
        140.0,
        recycle=False,
        uf_ratio=PFD_697_KGH / PFD_402G_KGH,
    )

    assert route["route"] == "A"
    assert route["selector_stream"] == "609"
    assert route["uf85_interlocked"] is False
    assert route["uf85_kgh"] == pytest.approx(PFD_697_KGH)
    assert route["forward_kgh"] == pytest.approx(PFD_402G_KGH + PFD_697_KGH)
    assert route["forward_kgh"] == pytest.approx(PFD_609_KGH, abs=1.0)
    assert route["recycle_kgh"] == 0.0
    assert route["mass_residual_kgh"] == pytest.approx(0.0, abs=1.0e-9)
    assert max(abs(value) for value in route["species_residual_kgh"].values()) < 1.0e-9
    assert route["energy_residual_kw"] == pytest.approx(0.0, abs=1.0e-9)

    # Independent PFD mixture checks: UF85 supplies the extra water and HCHO.
    expected_water = (
        PFD_402G_KGH * main.W_S402G["H2O"]
        + PFD_697_KGH * main.W_S697["H2O"]
    ) / (PFD_402G_KGH + PFD_697_KGH)
    expected_hcho = (
        PFD_402G_KGH * main.W_S402G["HCHO"]
        + PFD_697_KGH * main.W_S697["HCHO"]
    ) / (PFD_402G_KGH + PFD_697_KGH)
    assert route["forward_comp"]["H2O"] == pytest.approx(expected_water)
    assert route["forward_comp"]["HCHO"] == pytest.approx(expected_hcho)
    assert route["forward_comp"]["H2O"] * 100.0 == pytest.approx(1.50, abs=0.01)
    assert route["forward_comp"]["HCHO"] * 100.0 == pytest.approx(0.49, abs=0.01)

    cp_402g = main.urea_soln_cp(main.W_S402G["Urea"], 140.0)
    cp_697 = main.urea_soln_cp(main.W_S697["Urea"], 40.0)
    expected_temperature = (
        PFD_402G_KGH * cp_402g * 140.0
        + PFD_697_KGH * cp_697 * 40.0
    ) / (PFD_402G_KGH * cp_402g + PFD_697_KGH * cp_697)
    assert route["forward_T_C"] == pytest.approx(expected_temperature)
    assert 138.0 < route["forward_T_C"] < 140.0


def test_recycle_route_sends_raw_402g_and_interlocks_uf85_off() -> None:
    route = main.route_lv324501(
        PFD_402G_KGH,
        main.W_S402G,
        140.0,
        recycle=True,
        uf_ratio=PFD_697_KGH / PFD_402G_KGH,
    )

    assert route["route"] == "B"
    assert route["selector_stream"] == "402G"
    assert route["uf85_interlocked"] is True
    assert route["uf85_kgh"] == 0.0
    assert route["forward_kgh"] == 0.0
    assert route["recycle_kgh"] == PFD_402G_KGH
    assert route["recycle_comp"] == main.W_S402G
    assert route["recycle_T_C"] == 140.0
    assert route["mass_residual_kgh"] == pytest.approx(0.0, abs=1.0e-9)
    assert max(abs(value) for value in route["species_residual_kgh"].values()) < 1.0e-9
    assert route["energy_residual_kw"] == pytest.approx(0.0, abs=1.0e-9)


def test_route_command_accepts_ui_a_and_b_labels() -> None:
    original_state = main.state
    try:
        main.state = main.State()
        main.handle_cmd({"type": "lv324501_route_set", "route": "B"})
        assert main.state.LV_324501_RECYCLE is True

        main.handle_cmd({"type": "lv324501_route_set", "route": "A"})
        assert main.state.LV_324501_RECYCLE is False
    finally:
        main.state = original_state


def test_uf85_slave_manual_stroke_changes_delivered_stream_697() -> None:
    low = main.State()
    low.FIC_335405["mode"] = "MAN"
    low.FIC_335405["op"] = 25.0
    low_flow = main.step_uf85_cascade(low, PFD_402G_KGH, False, 1.0)

    high = main.State()
    high.FIC_335405["mode"] = "MAN"
    high.FIC_335405["op"] = 75.0
    high_flow = main.step_uf85_cascade(high, PFD_402G_KGH, False, 1.0)

    assert low_flow["delivered_kgh"] == pytest.approx(0.5 * main.R324_M_UF_DES)
    assert high_flow["delivered_kgh"] == pytest.approx(1.5 * main.R324_M_UF_DES)
    assert high_flow["delivered_kgh"] == pytest.approx(3.0 * low_flow["delivered_kgh"])


def test_uf85_ratio_master_auto_sp_moves_cascade_delivered_flow() -> None:
    cascade = main.State()
    initial_flow = main.step_uf85_cascade(cascade, PFD_402G_KGH, False, 1.0)[
        "delivered_kgh"
    ]
    cascade.FFIC_335406["sp"] = 1.5 * main.R324_UF_RATIO

    result = None
    # One minute is enough to prove both cascade links without asserting an
    # undocumented closed-loop settling time for the vendor controller.
    for _ in range(60):
        result = main.step_uf85_cascade(cascade, PFD_402G_KGH, False, 1.0)

    assert result is not None
    assert initial_flow == pytest.approx(main.R324_M_UF_DES)
    assert result["delivered_kgh"] > initial_flow
    assert cascade.FFIC_335406["pv"] > main.R324_UF_RATIO
    assert cascade.FIC_335405["sp"] > main.R324_M_UF_DES / 1000.0


def test_uf85_recycle_interlock_overrides_slave_manual_mode() -> None:
    cascade = main.State()
    cascade.FIC_335405["mode"] = "MAN"
    cascade.FIC_335405["op"] = 100.0

    result = main.step_uf85_cascade(cascade, PFD_402G_KGH, True, 1.0)

    assert result["interlocked"] is True
    assert result["delivered_kgh"] == 0.0
    assert cascade.FIC_335405["op"] == 0.0
    assert cascade.FFIC_335406["pv"] == 0.0


@pytest.mark.parametrize("local_mode", ["MAN", "AUTO"])
def test_uf85_master_tracks_disconnected_slave_for_bumpless_cas_return(
    local_mode: str,
) -> None:
    cascade = main.State()
    cascade.FIC_335405["mode"] = local_mode
    cascade.FIC_335405["op"] = 25.0
    cascade.FIC_335405["sp"] = 0.347
    cascade.FFIC_335406["sp"] = cascade.FFIC_335406["sp_hi"]

    result = None
    for _ in range(600):
        result = main.step_uf85_cascade(cascade, PFD_402G_KGH, False, 1.0)

    assert result is not None
    local_flow = result["delivered_kgh"]
    assert cascade.FFIC_335406["op"] == pytest.approx(
        result["measured_ratio"], rel=2.0e-3
    )

    cascade.FIC_335405["mode"] = "CAS"
    returned = main.step_uf85_cascade(cascade, PFD_402G_KGH, False, 1.0)

    assert returned["delivered_kgh"] == pytest.approx(local_flow, rel=2.0e-3)


def test_recycle_arrives_at_d002_next_tick_with_total_species_and_energy() -> None:
    original_state = main.state
    dt = 0.1
    try:
        forward = main.State()
        main.state = forward
        main.handle_cmd({"type": "lv324501_route_set", "route": "A"})
        main.step_sim(dt)
        common_mass = forward.r323_d002_M_I
        common_temperature = forward.r323_d002_T
        common_comp = dict(forward.w_d002)
        main.step_sim(dt)
        forward_mass = forward.r323_d002_M_I
        forward_temperature = forward.r323_d002_T
        forward_inventory = _species_inventory(forward)

        recycle = main.State()
        main.state = recycle
        main.handle_cmd({"type": "lv324501_route_set", "route": "B"})
        pre_step_recycle_comp = dict(recycle.w_e003)
        main.step_sim(dt)
        assert recycle.r323_d002_M_I == pytest.approx(common_mass, abs=1.0e-9)
        assert recycle.r323_d002_T == pytest.approx(common_temperature, abs=1.0e-12)
        assert recycle.w_d002 == pytest.approx(common_comp, abs=1.0e-12)

        recycle_kgh = recycle.tlag["R324_recyc"]
        recycle_temperature = recycle.tlag["R324_recyc_T"]
        recycle_comp = dict(recycle.tlag["R324_recyc_comp"])
        assert recycle_kgh > 0.0
        assert recycle_comp == pytest.approx(pre_step_recycle_comp, abs=1.0e-12)

        main.step_sim(dt)
        recycle_inventory = _species_inventory(recycle)
        added_mass = recycle_kgh * dt / 3600.0
        assert recycle.r323_d002_M_I - forward_mass == pytest.approx(added_mass, abs=2.0e-9)
        for species in main.SOL_SPECIES:
            assert recycle_inventory[species] - forward_inventory[species] == pytest.approx(
                added_mass * recycle_comp[species], abs=2.0e-9
            )

        cp_recycle = main.urea_soln_cp(recycle_comp["Urea"], recycle_temperature)
        cp_bulk = main.urea_soln_cp(common_comp["Urea"], common_temperature)
        expected_extra_temperature = (
            recycle_kgh / 3600.0
            * cp_recycle
            * (recycle_temperature - common_temperature)
            * dt
            / (common_mass * cp_bulk)
        )
        assert recycle.r323_d002_T - forward_temperature == pytest.approx(
            expected_extra_temperature, abs=2.0e-12
        )
    finally:
        main.state = original_state
