import math
import hp_recycle
from core.unit import UnitOperation
from core.stream import Stream
class Valve322604(UnitOperation):
    """
    HV-322604 HP-Scrubber Off-gas Valve - Sequential Modular Port
    Dynamic isenthalpic letdown with equal-percentage trim.
    """
    def __init__(self, name: str, offgas_in: Stream, purge_out: Stream):
        super().__init__(name, inputs=[offgas_in], outputs=[purge_out])
        
        from main import SCRUB_HIC604_DES_PCT
        self.hic_pct = SCRUB_HIC604_DES_PCT
        self.diagnostics = {}

    def solve(self):
        from main import (
            MW_COMP, SCRUB_HV604_P_OUT, SCRUB_HIC604_DES_PCT,
            SCRUB_HV604_DP_DES, SCRUB_HV604_MU_JT, SCRUB_OFFGAS_DES_KGH, _eq_pct
        )
        offgas_in = self.inputs[0]
        purge_out = self.outputs[0]
        
        p_up = offgas_in.P
        T_in = offgas_in.T
        offgas_comp = offgas_in.comp
        
        dP = max(p_up - SCRUB_HV604_P_OUT, 0.0)
        valve = _eq_pct(self.hic_pct, SCRUB_HIC604_DES_PCT) * math.sqrt(dP / SCRUB_HV604_DP_DES)
        
        vent = hp_recycle.capacity_limited_vent(
            offgas_comp, MW_COMP, SCRUB_OFFGAS_DES_KGH * valve
        )
        comp = {k: vent["vented"].get(k, 0.0) for k in MW_COMP}
        T_out = T_in - SCRUB_HV604_MU_JT * dP
        m_kgh = vent["vented_kgh"]
        
        purge_out.set_state(T=T_out, P=SCRUB_HV604_P_OUT, mass_flow=m_kgh)
        purge_out.comp = comp
        
        for stream in self.inputs:
            stream.is_dirty = False
            
        self.diagnostics = {
            "comp_kmolh": comp, "T_out": round(T_out, 1),
            "P_out": SCRUB_HV604_P_OUT, "P_in": round(p_up, 1), "open_pct": self.hic_pct,
            "mass_kgh": m_kgh, "valve_frac": valve, "dP": round(dP, 1),
            "available_mass_kgh": vent["available_kgh"],
            "capacity_mass_kgh": vent["capacity_kgh"],
            "retained_kmolh": vent["retained"], "retained_mass_kgh": vent["retained_kgh"]
        }
