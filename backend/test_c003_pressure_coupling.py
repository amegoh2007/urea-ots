"""Source-calibrated LV-322501 to 323C003 pressure-coupling tests."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from c003_pressure_coupling import c003_pressure_target_bara  # noqa: E402

import main  # noqa: E402


def test_design_point_closes_exactly():
    assert c003_pressure_target_bara(1.0, 1.0, 3.2) == pytest.approx(4.1, abs=1e-12)


def test_each_gas_load_driver_is_monotonic():
    design = c003_pressure_target_bara(1.0, 1.0, 3.2)
    assert c003_pressure_target_bara(1.1, 1.0, 3.2) > design
    assert c003_pressure_target_bara(1.0, 1.1, 3.2) > design
    assert c003_pressure_target_bara(0.9, 1.0, 3.2) < design
    assert c003_pressure_target_bara(1.0, 0.9, 3.2) < design


def test_vendor_maximum_flow_equivalent_is_4_20838_bara():
    vendor_flow_ratio = 126.10 / 114.58
    assert 46.1 * vendor_flow_ratio == pytest.approx(50.734945, abs=1e-6)
    assert c003_pressure_target_bara(vendor_flow_ratio, 1.0, 3.2) \
        == pytest.approx(4.208379859, abs=1e-9)


def test_local_lv_gain_is_0_0229317_bar_per_opening_point():
    opening_step = 1.0e-3
    ratio_step = opening_step / 46.1
    p_high = c003_pressure_target_bara(1.0 + ratio_step, 1.0, 3.2)
    p_low = c003_pressure_target_bara(1.0 - ratio_step, 1.0, 3.2)
    slope = (p_high - p_low) / (2.0 * opening_step)
    assert slope == pytest.approx(0.022931746, rel=1e-6)


def test_zero_total_gas_load_equals_downstream_pressure():
    assert c003_pressure_target_bara(0.0, 0.0, 3.2) == pytest.approx(3.2, abs=1e-12)


def test_downstream_backpressure_is_monotonic():
    assert c003_pressure_target_bara(1.0, 1.0, 3.0) \
        < c003_pressure_target_bara(1.0, 1.0, 3.2) \
        < c003_pressure_target_bara(1.0, 1.0, 3.5)


@pytest.mark.parametrize("args", [
    (math.nan, 1.0, 3.2),
    (1.0, math.inf, 3.2),
    (1.0, 1.0, math.nan),
    (-0.01, 1.0, 3.2),
    (1.0, -0.01, 3.2),
    (1.0, 1.0, 0.0),
    (1.0, 1.0, -1.0),
])
def test_invalid_inputs_raise_value_error(args):
    with pytest.raises(ValueError):
        c003_pressure_target_bara(*args)


def _one_step_from_fresh(lv_open_pct=46.1, downstream_pressure_bara=3.2):
    main.state = main.State()
    state = main.state
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = lv_open_pct
    state.r3232_d001_P = downstream_pressure_bara
    pressure_before = state.r323_c003_P
    packet = main.step_sim(0.1)
    return pressure_before, state.r323_c003_P, packet


def test_runtime_normalizes_design_lv_flow_to_one(monkeypatch):
    captured = []
    real_target = main.c003_pressure_target_bara

    def capture(lv_flow_ratio, overhead_flow_ratio, downstream_pressure_bara):
        captured.append((lv_flow_ratio, overhead_flow_ratio, downstream_pressure_bara))
        return real_target(lv_flow_ratio, overhead_flow_ratio, downstream_pressure_bara)

    monkeypatch.setattr(main, "c003_pressure_target_bara", capture)
    main.state = main.State()
    main.step_sim(0.1)
    assert captured
    assert captured[0][0] == pytest.approx(1.0, abs=1e-12)


def test_opening_and_closing_lv_give_prompt_signed_pressure_response():
    p0_open, p_open, _ = _one_step_from_fresh(lv_open_pct=60.0)
    p0_close, p_close, _ = _one_step_from_fresh(lv_open_pct=30.0)
    assert p_open > p0_open
    assert p_close < p0_close


def test_runtime_consumes_beginning_of_substep_e003_backpressure():
    _, p_low, _ = _one_step_from_fresh(downstream_pressure_bara=3.0)
    _, p_design, _ = _one_step_from_fresh(downstream_pressure_bara=3.2)
    _, p_high, _ = _one_step_from_fresh(downstream_pressure_bara=3.5)
    assert p_low < p_design < p_high


def test_zero_reboiler_overhead_still_uses_prompt_flash_load():
    main.state = main.State()
    state = main.state
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = main.LV322501_OPEN_DES
    state.PIC_329202["mode"] = "MAN"
    state.PIC_329202["op"] = 0.0
    state.TIC_323007["mode"] = "MAN"
    pressure_before = state.r323_c003_P

    packet = main.step_sim(0.1)

    assert packet["RECIRC_323"]["C003"]["v305_th"] == 0.0
    target = c003_pressure_target_bara(1.0, 0.0, 3.2)
    expected = pressure_before + (target - pressure_before) / main.R323_C003_P_TAU_S * 0.1
    assert state.r323_c003_P == pytest.approx(expected, abs=1e-10)


def _advance_opening(dt, seconds=2.0):
    main.state = main.State()
    state = main.state
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = 60.0
    for _ in range(round(seconds / dt)):
        main.step_sim(dt)
    return state.r323_c003_P


def test_opening_response_is_consistent_across_supported_steps():
    fine = _advance_opening(0.1)
    coarse = _advance_opening(main.STEP_CAP)
    assert coarse == pytest.approx(fine, abs=2.0e-4)


def test_opening_lv322501_increases_top_vapor_and_opens_pv323202():
    main.state = main.State()
    state = main.state
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = 55.0  # open from 46.1% design

    for _ in range(60):
        packet = main.step_sim(1.0)

    assert packet["RECIRC_323"]["C003"]["v305_th"] > 24.58
    assert state.r3232_d001_P >= 3.20
    assert state.PIC_323202["op"] > 25.0


def test_increasing_323e002_steam_increases_c003_pressure_and_pv323202():
    main.state = main.State()
    state = main.state
    state.TIC_323007["mode"] = "MAN"
    state.TIC_323007["op"] = 3.5  # higher steam chest demand

    for _ in range(30):
        packet = main.step_sim(1.0)

    assert packet["RECIRC_323"]["C003"]["v305_th"] > 24.58
    assert state.r323_c003_P > 4.10
    assert state.PIC_323202["op"] > 25.0

