from backend.core.stream import Stream
from backend.core.reactor import Reactor322R001

def test_reactor_sm():
    feed_in = Stream("Feed_In")
    feed_in.comp = {"NH3": 3000.0, "CO2": 1000.0, "H2O": 500.0, "Urea": 50.0, "Biuret": 1.0}
    feed_in.set_state(T=170.0)
    
    overflow_out = Stream("Overflow_Out")
    offgas_out = Stream("Offgas_Out")
    
    reactor = Reactor322R001("322R001_Reactor", feed_in, overflow_out, offgas_out)
    reactor.co2_feed_th = 73.0
    reactor.solve()
    
    assert overflow_out.mass_flow > 0.0
    assert offgas_out.mass_flow > 0.0
    assert overflow_out.comp.get("Urea", 0.0) > 50.0 # Urea produced
    
    # Ensure dirty flags are cleared
    assert not feed_in.is_dirty
