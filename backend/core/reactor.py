from typing import List, Optional
from core.unit import UnitOperation
from core.stream import Stream
import pressure_drop

import main as main_module
from main import (
    MW_COMP, REACT_OVERFLOW_T_C, REACT_HIC605_DES_PCT, REACT_OVERFLOW_DES,
    REACT_XI_UREA_DES, REACT_XI_BIU_DES, REACT_TEAR_DES, REACT_THETA_OG,
    REACT_NC_OVERFLOW_GAIN, REACT_L_FEED_DES, REACT_X_DES, REACT_OFFGAS_DEFICIT_GAIN,
    REACT_OFFGAS_P_BARA, REACT_P_BARA, REACT_OFFGAS_T_C, CO2_DES_KGH, _react_delta
)

class Reactor322R001(UnitOperation):
    """
    322R001 High-Pressure Urea Reactor - Sequential Modular Port
    """
    def __init__(self, name: str, 
                 feed_in: Stream, 
                 overflow_out: Stream, offgas_out: Stream):
        super().__init__(name, inputs=[feed_in], outputs=[overflow_out, offgas_out])
        
        self.co2_feed_th = 0.0
        self.hic_322605_pct = REACT_HIC605_DES_PCT
        self.L_drive: Optional[float] = None
        self.W_drive: Optional[float] = None
        self.T_overflow_c = REACT_OVERFLOW_T_C
        
        self.diagnostics = {}

    def solve(self):
        feed_in = self.inputs[0]
        overflow_out = self.outputs[0]
        offgas_out = self.outputs[1]
        
        feed = feed_in.comp
        
        s = self.co2_feed_th / (CO2_DES_KGH / 1000.0) if CO2_DES_KGH > 0 else 0.0
        phi = self.hic_322605_pct / 100.0
        phi_des = REACT_HIC605_DES_PCT / 100.0
        
        reactor = main_module.reactor
        xi_urea, _ov_discard, X_conv, L_feed, W_feed = reactor.react_couple(
            feed, dict(REACT_OVERFLOW_DES), REACT_XI_UREA_DES * s, self.T_overflow_c,
            L_override=self.L_drive, W_override=self.W_drive)
            
        xi_biu = REACT_XI_BIU_DES * s
        
        s_tear = s if REACT_TEAR_DES is not None else 0.0
        fc = {k: feed.get(k, 0.0) - (REACT_TEAR_DES.get(k, 0.0) if REACT_TEAR_DES else 0.0) * s_tear for k in MW_COMP}
        
        xi_urea = max(min(xi_urea, fc.get("CO2", 0.0), 0.5 * fc.get("NH3", 0.0)), 0.0)
        xi_biu  = max(min(xi_biu, 0.5 * (fc.get("Urea", 0.0) + xi_urea)), 0.0)
        
        out_total = _react_delta(fc, xi_urea, xi_biu)
        
        overflow = {k: out_total.get(k, 0.0) * (1.0 - REACT_THETA_OG.get(k, 0.0)) for k in MW_COMP}
        offgas   = {k: out_total.get(k, 0.0) * REACT_THETA_OG.get(k, 0.0)         for k in MW_COMP}
        
        L_ref = REACT_L_FEED_DES if REACT_L_FEED_DES is not None else reactor.L0_DES
        nh3_shift = REACT_NC_OVERFLOW_GAIN * (L_feed / L_ref - 1.0) * REACT_OVERFLOW_DES.get("NH3", 0.0) * s
        nh3_shift = max(min(nh3_shift, 0.9 * offgas.get("NH3", 0.0)), -0.5 * overflow.get("NH3", 0.0))
        
        overflow["NH3"] = overflow.get("NH3", 0.0) + nh3_shift
        offgas["NH3"]   = offgas.get("NH3", 0.0)   - nh3_shift
        
        X_ref = REACT_X_DES if REACT_X_DES is not None else reactor.X_DES_RAW
        delta_X = max(1.0 - X_conv / X_ref, 0.0)
        g = REACT_OFFGAS_DEFICIT_GAIN * delta_X
        
        for k in ("NH3", "CO2"):
            sh = min(g * offgas.get(k, 0.0), overflow.get(k, 0.0))
            offgas[k]   = offgas.get(k, 0.0)   + sh
            overflow[k] = overflow.get(k, 0.0) - sh
            
        og_tot   = sum(offgas.values())
        p_nh3_og = (offgas.get("NH3", 0.0) / og_tot) * REACT_OFFGAS_P_BARA if og_tot > 0.0 else 0.0
        p_co2_og = (offgas.get("CO2", 0.0) / og_tot) * REACT_OFFGAS_P_BARA if og_tot > 0.0 else 0.0
        
        closure_resid = (sum(fc.values()) - xi_urea - (sum(overflow.values()) + sum(offgas.values())))
        tear_mass = sum((REACT_TEAR_DES.get(k, 0.0) if REACT_TEAR_DES else 0.0) * MW_COMP[k] for k in MW_COMP) * s_tear
        
        # DP Calculation
        mass_flow_in = sum(feed.get(k, 0.0) * MW_COMP[k] for k in MW_COMP)
        dp_bar = pressure_drop.reactor_r01.calc_pressure_drop(
            mass_flow_kg_s=mass_flow_in / 3600.0,
            density_kg_m3=feed_in.density,
            viscosity_pa_s=feed_in.viscosity
        )
        out_p = max(feed_in.P - dp_bar, 1.0)
        
        # Update output streams
        overflow_out.set_state(T=self.T_overflow_c, P=out_p, mass_flow=sum(overflow[k] * MW_COMP[k] for k in MW_COMP))
        overflow_out.comp = overflow
        
        offgas_out.set_state(T=REACT_OFFGAS_T_C, P=out_p, mass_flow=sum(offgas[k] * MW_COMP[k] for k in MW_COMP))
        offgas_out.comp = offgas
        
        for stream in self.inputs:
            stream.is_dirty = False
            
        self.diagnostics = {
            "overflow_kmolh": overflow, "offgas_kmolh": offgas, "feed_kmolh": feed,
            "feed_corrected_kmolh": fc, "tear_mass_kgh": tear_mass,
            "xi_urea": xi_urea, "xi_biu": xi_biu, "closure_resid": closure_resid,
            "T_overflow": self.T_overflow_c, "T_offgas": REACT_OFFGAS_T_C,
            "P_bara": REACT_P_BARA, "P_offgas": REACT_OFFGAS_P_BARA,
            "phi": phi, "phi_des": phi_des, "co2_scale": s,
            "X_conv": X_conv, "L_feed": L_feed, "W_feed": W_feed,
            "delta_X": delta_X, "p_nh3_og": p_nh3_og, "p_co2_og": p_co2_og
        }
