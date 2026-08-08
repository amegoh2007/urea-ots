"""Integrated response gates for 322E002 LP-steam generation and FT-329407."""

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402


DT = 1.0


def _run(seconds: float):
    packet = None
    for _ in range(int(seconds / DT)):
        packet = main.step_sim(DT)
    return packet


def test_load_and_lower_master_sp_raise_hpcc_steam_export():
    main.state = main.State()
    design = _run(400.0)
    design_generation = design["HPCC_322E002"]["steam"]["kgh"]
    design_export = design["STEAM_SYSTEM"]["FT_329407_th"]

    main.handle_cmd({
        "type": "co2_set",
        "value": 1.20 * main.state.F_CO2_raw_th,
    })
    loaded = _run(1200.0)
    loaded_generation = loaded["HPCC_322E002"]["steam"]["kgh"]
    loaded_export = loaded["STEAM_SYSTEM"]["FT_329407_th"]

    assert loaded_generation > design_generation
    assert loaded_export > design_export

    loaded_state = copy.deepcopy(main.state)
    unchanged_pressure = _run(600.0)
    unchanged_pressure_generation = unchanged_pressure["HPCC_322E002"]["steam"]["kgh"]

    main.state = copy.deepcopy(loaded_state)
    main.handle_cmd({
        "type": "master207_set",
        "sp": main.state.steam.master207_sp - 0.5,
    })
    lower_pressure = _run(600.0)
    lower_pressure_generation = lower_pressure["HPCC_322E002"]["steam"]["kgh"]
    lower_pressure_export = lower_pressure["STEAM_SYSTEM"]["FT_329407_th"]

    assert lower_pressure_generation > unchanged_pressure_generation
    assert lower_pressure_export > design_export
