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


def test_vendor_maximum_flow_equivalent_is_4_20472_bara():
    """LV-322501 datasheet maximum flow (126.10 against the 114.58 m3/h normal).

    4.208380 before the startup-trend retuning, 4.668215 with that residual as a bar offset,
    4.719504 with it as equivalent load.  Now 4.204720: the residual is gone (the trend band was
    the startup ramp, not a process gain -- see test_lv322501_pressure_retuning.py), so this is
    the pure line-law head.  It differs from the original 4.208380 only because the gas-load
    coefficient is now anchored on 301 + 302 = 7940.4 m3/h rather than on stream 305's 7677.1.
    """
    vendor_flow_ratio = 126.10 / 114.58
    assert 46.1 * vendor_flow_ratio == pytest.approx(50.734945, abs=1e-6)
    p_max = c003_pressure_target_bara(vendor_flow_ratio, 1.0, 3.2)
    assert p_max == pytest.approx(4.204720619, abs=1e-9)


def test_local_lv_gain_is_the_hydraulic_slope():
    """0.02217 bar per point of LV-322501 opening at design -- the flash path, nothing else.

    0.022931746 was this same hydraulic slope against the old stream-305 coefficient; the two-path
    split re-anchored it on 301 + 302.  The 0.1222 that sat here in between came from the
    startup-trend residual, which the trend regression in test_lv322501_pressure_retuning.py
    retires as a ramp correlation rather than a process gain.
    """
    opening_step = 1.0e-3
    ratio_step = opening_step / 46.1
    p_high = c003_pressure_target_bara(1.0 + ratio_step, 1.0, 3.2)
    p_low = c003_pressure_target_bara(1.0 - ratio_step, 1.0, 3.2)
    slope = (p_high - p_low) / (2.0 * opening_step)
    assert slope == pytest.approx(0.022171340, rel=1e-5)
    assert 0.0 < slope < 0.05


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
    """The LV-322501 throughput ratio -- the signal the field residual rides -- is exactly 1.0.

    The two source ratios are NOT: the flash ratio carries a 0.26 % offset because
    q_flash_avail_kw uses the live C10 solution cp (2.5064) while R323_Q305_DES_KW is anchored
    on the lumped design cp (2.5).  That is why the 4.61 bar/ratio field gain was moved onto the
    valve signal, which is design-exact, instead of the back-computed gas rate.
    """
    captured = []
    real_target = main.c003_pressure_target_bara

    def capture(*args):
        captured.append(args)
        return real_target(*args)

    monkeypatch.setattr(main, "c003_pressure_target_bara", capture)
    main.state = main.State()
    main.step_sim(0.1)
    assert captured
    flash_ratio, e002_ratio, _p_down = captured[0]
    assert flash_ratio == pytest.approx(1.0, rel=5e-3)
    assert e002_ratio == pytest.approx(1.0, rel=5e-3)


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


def test_zero_reboiler_overhead_still_uses_prompt_flash_load(monkeypatch):
    """PV-329202 shut: the 323E002 source collapses and the flash path alone holds the column.

    The expected target is rebuilt from the ratios the runtime actually passed, not from
    v305_th: stream 305 is the column OUTLET and is no longer an input to the coupling.
    """
    captured = []
    real_target = main.c003_pressure_target_bara

    def capture(*args):
        captured.append(args)
        return real_target(*args)

    monkeypatch.setattr(main, "c003_pressure_target_bara", capture)
    main.state = main.State()
    state = main.state
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = main.LV322501_OPEN_DES
    state.PIC_329202["mode"] = "MAN"
    state.PIC_329202["op"] = 0.0
    state.TIC_323007["mode"] = "MAN"
    pressure_before = state.r323_c003_P

    packet = main.step_sim(0.1)

    assert packet["RECIRC_323"]["C003"]["v305_th"] > 0.0
    flash_ratio, e002_ratio, p_down = captured[0]
    assert e002_ratio == pytest.approx(0.0, abs=1e-12)   # heater source gone
    assert flash_ratio > 0.9                             # flash source still charging
    target = real_target(flash_ratio, e002_ratio, p_down)
    expected = pressure_before + (target - pressure_before) / main.R323_C003_P_TAU_S * 0.1
    assert state.r323_c003_P == pytest.approx(expected, abs=2e-5)


def _advance_opening(dt, seconds=2.0):
    main.state = main.State()
    state = main.state
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = 60.0
    for _ in range(round(seconds / dt)):
        main.step_sim(dt)
    return state.r323_c003_P


def test_opening_response_is_consistent_across_supported_steps():
    """Step-size independence of the LV-322501 opening transient.

    RELATIVE, not absolute: r323_c003_P is an explicit-Euler state on a 1 s time constant, so at
    the 0.25 s STEP_CAP the per-step truncation is ~0.6 % of the excursion regardless of its
    size (measured 5.5209 / 5.5321 / 5.5666 bar a at dt = 0.05 / 0.1 / 0.25 -- converging).  The
    former 2e-2 bar absolute bound was that same 0.6 % when the pre-retuning gain made a 60 %
    opening worth ~0.3 bar; the retuned gain makes it ~1.4 bar, so the bound has to scale.
    """
    fine = _advance_opening(0.1)
    coarse = _advance_opening(main.STEP_CAP)
    assert coarse == pytest.approx(fine, rel=1.0e-2)


def test_opening_lv322501_raises_the_flash_path_and_the_column_pressure():
    """Opening LV-322501 charges 323C003 through the stream-301 flash path.

    This used to assert that the OVERHEAD total rises (v305_th > 24.58, and the 323D001
    back-pressure with it).  Two fixes retired that expectation, neither of them the two-path
    split itself:

      * the retuned field gain is 0.122 bar per point of opening, five times the hydraulic-only
        slope this file used to assert, so a 9-point opening lifts the column ~0.5 bar and the
        bubble point ~4 K above the 135 C TIC-323007 setpoint.  The cascade then cuts PV-329202
        and the 323E002 source falls faster than the flash source rises.
      * 323E002 previously ran a 9127 kW duty at the design seed (the chest pins were computed
        against a stale 4.4 bar a LP header) -- 56 % above its 5858 kW datasheet duty, enough
        headroom to absorb that cut.  At the correct duty it cannot.

    What the opening must still do is raise the flash source and the column pressure, and drive
    TIC-323007 to cut the heater.  (v305_th also depended on the design-hold drift lifting the
    R323_PHI_V305*m_feed_323 cap; with the loop closed at design that cap is exactly 24.5632.)
    """
    main.state = main.State()
    state = main.state
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = 55.0  # open from 46.1% design

    for _ in range(60):
        packet = main.step_sim(1.0)

    assert state._debug_m_flash > main.R323_M_FLASH_GAS_DES_KGH * 1.05
    assert state.r323_c003_P > main.R323_C003_P_BARA
    assert state.PIC_329202["op"] < main.R323_E002_OP_DES
    assert packet["RECIRC_323"]["C003"]["feed_th"] * 1000.0 > main.R323_FEED_DES_KGH


def test_increasing_323e002_steam_raises_the_heater_path_and_the_column_pressure():
    """More PV-329202 opening charges 323C003 through the stream-302 heater path.

    v305_th cannot rise here and never could: with LV-322501 at design the overhead is capped by
    the composition split R323_PHI_V305 * m_feed_323 == 24.5632 t/h, and extra steam only pushes
    the energy branch of that min() further above the cap.  The former `> 24.58` assertion passed
    only while the design-hold drift was lifting m_feed_323 above its design value.
    """
    main.state = main.State()
    state = main.state
    state.PIC_329202["mode"] = "MAN"
    state.PIC_329202["op"] = 98.0  # higher steam valve opening

    for _ in range(60):
        packet = main.step_sim(1.0)

    assert state._debug_m_pool > main.R323_M_POOL_VAP_DES_KGH * 1.05
    assert state.r323_c003_P > main.R323_C003_P_BARA
    assert packet["RECIRC_323"]["C003"]["v305_th"] == pytest.approx(
        main.R323_M305_DES / 1000.0, abs=0.01)


