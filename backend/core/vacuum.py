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
        import main as main_module
        from main import (
            R324_V1_DES, R324_F001_FA_DES, R323_MEVAP_DES, R324_V2_DES, R324_F003_FA_DES,
            VACUUM_CONDENSERS, vacuum_condenser_node
        )
        m_evap_kgh = self.inputs[0].mass_flow
        vapour1_kgh = self.inputs[1].mass_flow
        vapour2_kgh = self.inputs[2].mass_flow
        false_air1_kgh = self.inputs[3].mass_flow
        false_air2_kgh = self.inputs[4].mass_flow
        motive924_kgh = self.inputs[5].mass_flow
        motive927_kgh = self.inputs[6].mass_flow
        motive929_kgh = self.inputs[7].mass_flow
        
        condensate_out = self.outputs[0]
        vent_out = self.outputs[1]

        streams = {
            "705": 14799.0 + (vapour1_kgh - R324_V1_DES) + (false_air1_kgh - R324_F001_FA_DES),
            "790": 12040.0 + (m_evap_kgh - R323_MEVAP_DES),
            "709": 3342.0 + (vapour2_kgh - R324_V2_DES) + (false_air2_kgh - R324_F003_FA_DES),
            "924": motive924_kgh, "927": motive927_kgh, "929": motive929_kgh,
        }
        streams["703"] = 26840.0 + (streams["705"] - 14799.0) + (streams["790"] - 12040.0)
        
        e002 = vacuum_condenser_node(
            VACUUM_CONDENSERS["324E002"], streams["703"],
            max(72.0 - R324_F001_FA_DES + false_air1_kgh, 0.0), 116.0,
            VACUUM_CONDENSERS["324E002"]["cw_flow_kgh"] * self.cw_factors.get("324E002", 1.0),
        )
        streams["719"], streams["706"] = e002["condensate_kgh"], e002["vent_kgh"]
        streams["708"] = streams["706"] + streams["924"]
        
        e005 = vacuum_condenser_node(
            VACUUM_CONDENSERS["324E005"], streams["709"],
            max(584.0 - R324_F003_FA_DES + false_air2_kgh, 0.0), 140.0,
            VACUUM_CONDENSERS["324E005"]["cw_flow_kgh"] * self.cw_factors.get("324E005", 1.0),
        )
        streams["720"], streams["712"] = e005["condensate_kgh"], e005["vent_kgh"]
        streams["714"] = streams["712"] + streams["927"]
        
        e006 = vacuum_condenser_node(
            VACUUM_CONDENSERS["324E006"], streams["714"],
            41.0 + max(streams["712"] - 584.0, 0.0), 104.0,
            VACUUM_CONDENSERS["324E006"]["cw_flow_kgh"] * self.cw_factors.get("324E006", 1.0),
        )
        streams["721"], streams["715"] = e006["condensate_kgh"], e006["vent_kgh"]
        streams["717"] = streams["715"] + streams["929"]
        
        e007 = vacuum_condenser_node(
            VACUUM_CONDENSERS["324E007"], streams["717"],
            31.0 + max(streams["715"] - 41.0, 0.0), 120.0,
            VACUUM_CONDENSERS["324E007"]["cw_flow_kgh"] * self.cw_factors.get("324E007", 1.0),
        )
        streams["759"], streams["722"] = e007["condensate_kgh"], e007["vent_kgh"]
        
        total_condensate = streams["719"] + streams["720"] + streams["721"] + streams["759"]
        
        condensate_out.set_state(mass_flow=total_condensate)
        vent_out.set_state(mass_flow=streams["722"])
        
        for stream in self.inputs:
            stream.is_dirty = False
            
        self.diagnostics = {
            "streams_kgh": streams,
            "nodes": {"324E002": e002, "324E005": e005, "324E006": e006, "324E007": e007},
            "mixing_residual_703_kgh": streams["703"] - streams["705"] - streams["790"]
        }
