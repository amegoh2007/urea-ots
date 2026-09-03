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
    
    # Telemetry PIC_329207 faceplate.  Both LP-header transmitters are tagged 329207, so the
    # former PIC_329206 faceplate (the same loop in barg) is merged in as pv_barg / sp_barg.
    packet = main.step_sim(1.0)
    pic207 = packet["STEAM_SYSTEM"]["PIC_329207"]
    assert "PIC_329206" not in packet["STEAM_SYSTEM"]
    assert pic207["sp_barg"] == pytest.approx(4.0, abs=1e-2)
    assert pic207["pv_barg"] == pytest.approx(4.0, abs=1e-2)
    assert pic207["pv"] == pytest.approx(5.01325, abs=1e-2)
    
    # Saturation temperature Tsat(P_LP)
    tsat = main.tsat_steam(state.steam.P_LP)
    assert tsat == pytest.approx(152.06, abs=0.5)
