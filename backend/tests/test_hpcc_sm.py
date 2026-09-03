from backend.core.stream import Stream
from backend.core.hpcc import Hpcc322E002

def test_hpcc_sm_cascade():
    # Setup Input Streams
    gas_in = Stream("Gas_In")
    gas_in.comp = {"NH3": 2000.0, "CO2": 1000.0, "H2O": 100.0, "UREA": 0.0, "BIU": 0.0}
    gas_in.set_state(T=185.0)
    
    liq_in = Stream("Liq_In")
    liq_in.comp = {"NH3": 500.0, "CO2": 250.0, "H2O": 50.0, "UREA": 10.0, "BIU": 1.0} # Mass input mapped internally
    liq_in.set_state(T=140.0)

    # Setup Output Streams
    gas_out = Stream("Gas_Out")
    liq_out = Stream("Liq_Out")

    # Instantiate HPCC
    hpcc = Hpcc322E002(
        name="322E002_HPCC",
        gas_in=gas_in, liq_in=liq_in,
        gas_out=gas_out, liq_out=liq_out
    )

    # Trigger a solve tick with dt=0 to hold steady state flash
    hpcc.dt = 0.0
    hpcc.solve()
    
    # Assert that the solve method updated the outputs and cleared the dirty flag
    assert gas_in.is_dirty is False
    assert liq_in.is_dirty is False
    assert gas_out.T > 0.0
    assert liq_out.T > 0.0
    assert gas_out.T == liq_out.T # Product equilibrium assumption
    
    # Assert mass flows and components were calculated
    assert "CO2" in gas_out.comp
    assert "CO2" in liq_out.comp
