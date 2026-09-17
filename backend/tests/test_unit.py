from backend.core.stream import Stream
from backend.core.unit import UnitOperation

class DummyMixer(UnitOperation):
    def solve(self):
        # MESH Mass balance: Output = sum(Inputs)
        total_mass = sum(s.mass_flow for s in self.inputs)
        self.outputs[0].set_state(mass_flow=total_mass)
        # Clear dirty flags
        for s in self.inputs: s.is_dirty = False

def test_unit_cascade():
    s_in1 = Stream("In1")
    s_in2 = Stream("In2")
    s_out = Stream("Out")
    
    mixer = DummyMixer("Mixer1", inputs=[s_in1, s_in2], outputs=[s_out])
    
    # Trigger cascade
    s_in1.set_state(mass_flow=100.0)
    s_in2.set_state(mass_flow=50.0)
    
    assert s_out.mass_flow == 150.0
    assert s_in1.is_dirty is False
