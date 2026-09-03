from backend.core.stream import Stream
from backend.core.scrubber import Scrubber322E003

def test_scrubber_sm_cascade():
    # Setup Input Streams
    offgas_in = Stream("Offgas_In")
    offgas_in.comp = {"NH3": 1000.0, "CO2": 500.0, "H2O": 50.0, "UREA": 0.0, "BIU": 0.0}
    
    wash_in = Stream("Wash_In")
    ccw_in = Stream("CCW_In")
    ccw_in.set_state(T=30.0, mass_flow=100000.0)

    # Setup Output Streams
    vent_out = Stream("Vent_Out")
    carbamate_out = Stream("Carbamate_Out")
    ccw_out = Stream("CCW_Out")

    # Instantiate Scrubber
    scrubber = Scrubber322E003(
        name="322E003_Scrubber",
        offgas_in=offgas_in, wash_in=wash_in, ccw_in=ccw_in,
        vent_out=vent_out, carbamate_out=carbamate_out, ccw_out=ccw_out
    )

    # Trigger a change to simulate ripple effect
    offgas_in.set_state(T=180.0)
    
    # Assert that the solve method updated the outputs and cleared the dirty flag
    assert offgas_in.is_dirty is False
    assert vent_out.T > 0.0
    assert ccw_out.T > ccw_in.T
    
    # Assert mass flows and components were calculated
    assert "CO2" in vent_out.comp
    assert "CO2" in carbamate_out.comp
