import pytest
import main
import steam_system

def test_lp_steam_initializes_at_4barg():
    state = main.State()
    # Initial LP steam pressure
    assert state.steam.P_LP == pytest.approx(5.01325, abs=1e-3)
    assert (state.steam.P_LP - 1.01325) == pytest.approx(4.0, abs=1e-3)
    
    # Master controller SP
    assert state.steam.master207_sp == pytest.approx(5.01325, abs=1e-3)
    assert (state.steam.master207_sp - 1.01325) == pytest.approx(4.0, abs=1e-3)
    
    # Telemetry PIC_329206 faceplate
    packet = main.step_sim(1.0)
    pic206 = packet["STEAM_SYSTEM"]["PIC_329206"]
    assert pic206["sp"] == pytest.approx(4.0, abs=1e-2)
    assert pic206["pv"] == pytest.approx(4.0, abs=1e-2)
    
    # Saturation temperature Tsat(P_LP)
    tsat = main.tsat_steam(state.steam.P_LP)
    assert tsat == pytest.approx(152.06, abs=0.5)
