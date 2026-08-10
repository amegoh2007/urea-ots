import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from c003_pressure_coupling import (  # noqa: E402
    c003_pressure_target_bara,
    e011_vent_generation_kgh,
)


def test_c003_design_point_closes_exactly():
    assert c003_pressure_target_bara(1.0, 1.0, 3.2) == pytest.approx(4.1, abs=1.0e-12)


def test_c003_local_lv_sensitivity_matches_startup_band():
    opening_step = 1.0e-3
    ratio_step = opening_step / 46.1
    p_hi = c003_pressure_target_bara(1.0 + ratio_step, 1.0, 3.2)
    p_lo = c003_pressure_target_bara(1.0 - ratio_step, 1.0, 3.2)
    slope = (p_hi - p_lo) / (2.0 * opening_step)
    assert slope == pytest.approx(0.122931746, rel=1.0e-5)
    assert 0.10 <= slope <= 0.13


def test_e011_design_gas_closes_pfd_balance():
    assert e011_vent_generation_kgh(6029.0) == pytest.approx(440.0)


def test_e011_incremental_gas_exceeds_fixed_condensation_capacity():
    assert e011_vent_generation_kgh(7029.0) == pytest.approx(1440.0)
    assert e011_vent_generation_kgh(5029.0) == 0.0


def test_c003_target_never_falls_below_downstream_pressure():
    assert c003_pressure_target_bara(0.0, 1.0, 3.2) == pytest.approx(3.2)


@pytest.mark.parametrize("gas_inlet", [math.nan, math.inf, -0.01])
def test_e011_rejects_invalid_gas_inlet(gas_inlet):
    with pytest.raises(ValueError):
        e011_vent_generation_kgh(gas_inlet)


from typing import NamedTuple

import main  # noqa: E402


class LvCase(NamedTuple):
    pt323201_bara: float
    pic323203_pv_bara: float
    pic323203_op: float


def _run_lv_case(opening_pct: float) -> LvCase:
    main.state = main.State()
    state = main.state
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = opening_pct
    for _ in range(round(60.0 / main.STEP_CAP)):
        main.step_sim(main.STEP_CAP)
    return LvCase(
        pt323201_bara=state.r323_c003_P,
        pic323203_pv_bara=state.r3232_e011_P,
        pic323203_op=state.PIC_323203["op"],
    )


def test_lv_opening_materially_separates_pt323201():
    closed = _run_lv_case(30.0)
    opened = _run_lv_case(60.0)
    assert opened.pt323201_bara - closed.pt323201_bara > 2.5


def test_lv_opening_materially_separates_pic323203():
    closed = _run_lv_case(30.0)
    opened = _run_lv_case(60.0)
    assert opened.pic323203_op - closed.pic323203_op > 2.0
