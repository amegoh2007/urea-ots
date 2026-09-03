import math
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
        # Hydraulic throughput ceiling, kg/h of OFFERED off-gas (pre-valve basis).  A DN-24 / Kvs 2.1
        # trim passes what its Kv, dP and upstream density allow; offering it more gas does not make
        # it pass more.  Left None the valve keeps its historical "pass everything offered x valve
        # factor" behaviour.  step_sim sets it to the purge mass the shell would have produced with
        # full CCW, so vapour the 322E003 failed to condense is RETAINED in the loop instead of
        # venting to 322C001 through a valve sized for the inert purge.  Composition is untouched --
        # the seat passes the live mixture, it does not fractionate.  At design the ceiling equals
        # the offered mass exactly -> pass fraction 1.0 -> bit-exact.
        self.vent_cap_kgh = None
        self.diagnostics = {}

    def solve(self):
        from main import (
            MW_COMP, SCRUB_HV604_P_OUT, SCRUB_HIC604_DES_PCT, 
            SCRUB_HV604_DP_DES, SCRUB_HV604_MU_JT, _eq_pct
        )
        offgas_in = self.inputs[0]
        purge_out = self.outputs[0]
        
        p_up = offgas_in.P
        T_in = offgas_in.T
        offgas_comp = offgas_in.comp
        
        dP = max(p_up - SCRUB_HV604_P_OUT, 0.0)
        valve = _eq_pct(self.hic_pct, SCRUB_HIC604_DES_PCT) * math.sqrt(dP / SCRUB_HV604_DP_DES)
        
        off_kgh = sum(offgas_comp.get(k, 0.0) * MW_COMP[k] for k in MW_COMP)
        cap     = self.vent_cap_kgh
        # Capacity ceiling: what the seat cannot pass stays upstream (the loop), it does not vent.
        pass_frac = 1.0 if (cap is None or off_kgh <= 0.0) else min(1.0, max(cap, 0.0) / off_kgh)
        comp = {k: offgas_comp.get(k, 0.0) * valve * pass_frac for k in MW_COMP}
        T_out = T_in - SCRUB_HV604_MU_JT * dP
        m_kgh = sum(comp.get(k, 0.0) * MW_COMP[k] for k in MW_COMP)
        
        purge_out.set_state(T=T_out, P=SCRUB_HV604_P_OUT, mass_flow=m_kgh)
        purge_out.comp = comp
        
        for stream in self.inputs:
            stream.is_dirty = False
            
        self.diagnostics = {
            "comp_kmolh": comp, "T_out": round(T_out, 1),
            "P_out": SCRUB_HV604_P_OUT, "P_in": round(p_up, 1), "open_pct": self.hic_pct,
            "mass_kgh": m_kgh, "valve_frac": valve, "dP": round(dP, 1),
            "pass_frac": pass_frac
        }
