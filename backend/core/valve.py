import math
import hydraulics
from core.unit import UnitOperation
from core.stream import Stream
class Valve322604(UnitOperation):
    """
    HV-322604 HP-Scrubber Off-gas Valve - Sequential Modular Port
    Dynamic isenthalpic letdown with equal-percentage trim.

    PHASE 2, report D-2.  This class is the Sequential-Modular port of `main.hv_322604` and it had
    been left behind when that function moved onto the ISA-75.01 compressible law: it still carried
    `_eq_pct(theta) * sqrt(dP/dP_des)`, an INCOMPRESSIBLE orifice on a service running at a pressure
    ratio of 0.028 against a critical ~0.7, i.e. deeply choked.  Two consequences, both real:
      * flow responded to the DOWNSTREAM pressure while choked, which cannot happen;
      * `_eq_pct(0, 50)` is 50^-0.5 = 0.1414, so a HIC-322604 commanded fully SHUT still passed
        14 % of the design off-gas -- roughly 835 kg/h of NH3/CO2 out of a 140.7 bar loop the
        operator believes is isolated.  `hydraulics.cv_fraction` returns a hard 0.0 at zero travel.
    The two ports now call the same anchored law on the same anchors, so the SM flowsheet and the
    tick engine cannot disagree about this valve again.
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
            SCRUB_HV604_DP_DES, SCRUB_HV604_MU_JT, SCRUB_HV604_GAMMA,
            SCRUB_HV604_MW_DES, SCRUB_OFFGAS_P_BARA, SCRUB_OFFGAS_T_C
        )
        offgas_in = self.inputs[0]
        purge_out = self.outputs[0]
        
        p_up = offgas_in.P
        T_in = offgas_in.T
        offgas_comp = offgas_in.comp
        
        dP = max(p_up - SCRUB_HV604_P_OUT, 0.0)
        # The design MW is passed explicitly so composition does NOT cancel out of the ratio: a
        # heavier off-gas puts more kilograms through the same trim, m ~ sqrt(M).
        _n_og = sum(offgas_comp.get(k, 0.0) for k in MW_COMP)
        _mw_og = (sum(offgas_comp.get(k, 0.0) * MW_COMP[k] for k in MW_COMP) / _n_og)             if _n_og > 1e-12 else SCRUB_HV604_MW_DES
        valve = hydraulics.valve_gas_anchored(
            1.0, self.hic_pct / 100.0, p_up, SCRUB_HV604_P_OUT, T_in + 273.15,
            SCRUB_HIC604_DES_PCT / 100.0, SCRUB_OFFGAS_P_BARA, SCRUB_HV604_P_OUT,
            SCRUB_OFFGAS_T_C + 273.15, _mw_og, gamma=SCRUB_HV604_GAMMA,
            characteristic="equal_pct", mw_des=SCRUB_HV604_MW_DES)

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
