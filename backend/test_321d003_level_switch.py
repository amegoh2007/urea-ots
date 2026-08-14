"""321D003 discrete level-switch behavior."""

from __future__ import annotations

import main


def test_lsl_321501_changes_at_the_upper_1200_mm_connection():
    threshold = main.LSL_321501_HIGH_M / main.TANK_H

    assert main.lsl_321501_low(threshold) is False
    assert main.lsl_321501_low(threshold - 1.0e-6) is True


def test_fresh_full_tank_lights_the_switch_green():
    state = main.State()

    assert state.tank_level_frac == 1.0
    assert main.lsl_321501_low(state.tank_level_frac) is False
