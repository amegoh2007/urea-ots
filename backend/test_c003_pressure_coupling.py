"""Source-calibrated LV-322501 to 323C003 pressure-coupling tests."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from c003_pressure_coupling import c003_pressure_target_bara  # noqa: E402


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
