from typing import Dict, Any
from core.unit import UnitOperation
from core.stream import Stream

class VacuumTrain324(UnitOperation):
    """
    324 Vacuum Train - Sequential Modular Port
    Simulates the cascading condensers (324E002, 324E005, 324E006, 324E007)
    and intermediate ejector mixing nodes.
    """
    def __init__(self, name: str, 
                 evap_in: Stream, 
                 vapour1_in: Stream, vapour2_in: Stream,
                 false_air1_in: Stream, false_air2_in: Stream,
                 motive924_in: Stream, motive927_in: Stream, motive929_in: Stream,
                 condensate_out: Stream, vent_out: Stream):
        # We model the collective condensates as one aggregate output, and the final vent.
        super().__init__(name, 
                         inputs=[evap_in, vapour1_in, vapour2_in, false_air1_in, false_air2_in,
                                 motive924_in, motive927_in, motive929_in],
                         outputs=[condensate_out, vent_out])
        
        self.cw_factors: Dict[str, float] = {}
        self.diagnostics: Dict[str, Any] = {}

    def solve(self):
        #  One implementation of the train, in main.vacuum_train_324 (reports A-13 / B-9 / B-13): this
        #  unit used to carry its own copy of it, and two copies of a condenser model drift.
        import main as main_module
        m_evap_kgh = self.inputs[0].mass_flow
        vapour1_kgh = self.inputs[1].mass_flow
        vapour2_kgh = self.inputs[2].mass_flow
        false_air1_kgh = self.inputs[3].mass_flow
        false_air2_kgh = self.inputs[4].mass_flow
        motive924_kgh = self.inputs[5].mass_flow
        motive927_kgh = self.inputs[6].mass_flow
        motive929_kgh = self.inputs[7].mass_flow
        p_shell = getattr(self, "p_shell", {}) or {}
        train = main_module.vacuum_train_324(
            m_evap_kgh, vapour1_kgh, vapour2_kgh, false_air1_kgh, false_air2_kgh,
            motive924_kgh, motive927_kgh, motive929_kgh, cw_factors=self.cw_factors,
            p_e002_bara=p_shell.get("324E002"), p_e005_bara=p_shell.get("324E005"),
            sub_703=getattr(self, "sub_703", None))
        streams = train["streams_kgh"]
        condensate_out, vent_out = self.outputs[0], self.outputs[1]
        condensate_out.set_state(mass_flow=streams["719"] + streams["720"] + streams["721"] + streams["759"])
        vent_out.set_state(mass_flow=streams["722"])
        for stream in self.inputs:
            stream.is_dirty = False
        self.diagnostics = train
