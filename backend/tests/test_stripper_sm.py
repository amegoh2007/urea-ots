from backend.core.stream import Stream
from backend.core.stripper import Stripper322E001

def test_stripper_sm():
    co2_in = Stream("CO2_In")
    co2_in.set_state(mass_flow=73000.0) # 73 t/h
    
    overflow_in = Stream("Overflow_In")
    overflow_in.comp = {"NH3": 2500.0, "CO2": 1000.0, "H2O": 500.0, "Urea": 1500.0, "Biuret": 5.0}
    overflow_in.set_state(T=183.0)
    
    steam_in = Stream("Steam_In")
    steam_in.set_state(T=210.0)
    
    top_gas_out = Stream("Top_Gas_Out")
    bottom_liq_out = Stream("Bottom_Liq_Out")
    
    stripper = Stripper322E001("322E001_Stripper", co2_in, overflow_in, steam_in, top_gas_out, bottom_liq_out)
    stripper.solve()
    
    assert top_gas_out.mass_flow > 0.0
    assert bottom_liq_out.mass_flow > 0.0
    assert "Urea" in bottom_liq_out.comp
    
    # Ensure dirty flags are cleared
    assert not co2_in.is_dirty
