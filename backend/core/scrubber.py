import math
import hp_recycle
from typing import List, Optional
from core.unit import UnitOperation
from core.stream import Stream

# Importing required constants from main. We assume main won't have a circular dependency 
# if we import scrubber at the bottom or inside step_sim.
from main import (
    MW_COMP, SCRUB_CARB_KMOLH_DES, SCRUB_OFFGAS_KMOLH_DES, SCRUB_OVERFLOW_KMOLH_DES,
    SCRUB_ABS_CAP_KMOLH_DES, SCRUB_CW_ABS_GAIN, SCRUB_CCW_T_IN_DES,
    SCRUB_DH_CARB_KJMOL, SCRUB_Q_CCW_DES_KW,
    SCRUB_COND_SPINDLE_GAIN, SCRUB_COND_CHOKE_MIN, SCRUB_LEVEL_NLL_PCT, SCRUB_CCW_CP,
    SCRUB_UA_KWK, SCRUB_HIC604_DES_PCT, SCRUB_T_PROC_C, SCRUB_OVERFLOW_T_VENT_GAIN,
    SCRUB_OFFGAS_NC_DES, SCRUB_OFFGAS_T_C, SCRUB_OFFGAS_T_GAIN, SCRUB_OFFGAS_T_VENT_GAIN,
    SCRUB_OFFGAS_P_BARA, SCRUB_OVERFLOW_P_BARA, clamp
)
import pressure_drop

class Scrubber322E003(UnitOperation):
    """
    322E003 HP Scrubber - Sequential Modular Port
    """
    def __init__(self, name: str, 
                 offgas_in: Stream, wash_in: Stream, ccw_in: Stream,
                 vent_out: Stream, carbamate_out: Stream, ccw_out: Stream):
        super().__init__(name, inputs=[offgas_in, wash_in, ccw_in], outputs=[vent_out, carbamate_out, ccw_out])
        
        # We can store external diagnostic or control variables here
        self.co2_scale = 1.0
        self.vent_ratio = 1.0
        self.nc_act: Optional[float] = None
        self.hic604_pct: Optional[float] = None
        self.liq_carry_kmolh: Optional[dict] = None
        self.t_carry_c: Optional[float] = None
        self.choke_level_pct: Optional[float] = None
        self.spindle_phi = 1.0
        
        self.diagnostics = {}

    def solve(self):
        s = self.co2_scale
        
        # Streams
        offgas_in = self.inputs[0]
        wash_in = self.inputs[1]
        ccw_in = self.inputs[2]
        
        vent_out = self.outputs[0]
        carbamate_out = self.outputs[1]
        ccw_out = self.outputs[2]
        
        # Mapping Stream compositions/properties to the solver logic
        offgas_feed = offgas_in.comp
        t_ccw_in = ccw_in.T
        m_ccw_kgh = ccw_in.mass_flow
        
        # Same finite-capacity, component-closing split as main.scrub_322e003.
        carb = {k: wash_in.comp.get(k, 0.0) for k in MW_COMP}
        wash_scale = sum(carb.values()) / max(sum(SCRUB_CARB_KMOLH_DES.values()), 1e-9)
        co2_capacity = max(SCRUB_ABS_CAP_KMOLH_DES.get("CO2", 0.0), 1e-9)
        capacity_ratio = max(
            wash_scale + SCRUB_CW_ABS_GAIN * (SCRUB_CCW_T_IN_DES - t_ccw_in) / co2_capacity,
            0.0,
        )
        split = hp_recycle.reactive_scrubber_split(
            offgas_feed, carb, SCRUB_ABS_CAP_KMOLH_DES, capacity_ratio
        )
        feed = {k: offgas_feed.get(k, 0.0) + carb[k] for k in MW_COMP}
        offgas = {k: split["gas"].get(k, 0.0) for k in MW_COMP}
        overflow = {k: split["liquid"].get(k, 0.0) for k in MW_COMP}

        carry_mass_kgh = 0.0
        if self.liq_carry_kmolh:
            for k in MW_COMP:
                c = self.liq_carry_kmolh.get(k, 0.0)
                feed[k]        += c
                overflow[k]    += c
                carry_mass_kgh += c * MW_COMP[k]
                
        closure_kmolh = {k: feed[k] - offgas[k] - overflow[k] for k in MW_COMP}
        closure_resid = sum(closure_kmolh.values())
        co2_abs   = max(offgas_feed.get("CO2", 0.0) - offgas["CO2"], 0.0)
        q_carb_kw = co2_abs * 1000.0 * SCRUB_DH_CARB_KJMOL / 3600.0
        
        # PHYSICAL CONDENSATION HEAT TRANSFER:
        # Instead of rigidly forcing q_ccw_kw to a design scaling factor (SCRUB_Q_CCW_DES_KW * s * vent),
        # we calculate it directly from the true physical condensation (q_carb_kw).
        # We add the design sensible cooling gap (5329.5 - 5325.27 = ~4.23 kW) scaled by load
        # to ensure bit-exact parity at design conditions.
        q_sens_des_kw = SCRUB_Q_CCW_DES_KW - (125.137 * 1000.0 * SCRUB_DH_CARB_KJMOL / 3600.0)
        q_ccw_kw  = q_carb_kw + q_sens_des_kw * s * self.vent_ratio

        chi_sp    = 1.0 + SCRUB_COND_SPINDLE_GAIN * (1.0 - 1.0 / max(self.spindle_phi, 1e-6))
        q_ccw_kw *= max(chi_sp, SCRUB_COND_CHOKE_MIN)

        if self.choke_level_pct is not None:
            chi_choke = 1.0 - (1.0 - SCRUB_COND_CHOKE_MIN) * max(self.choke_level_pct - SCRUB_LEVEL_NLL_PCT, 0.0) \
                              / max(100.0 - SCRUB_LEVEL_NLL_PCT, 1e-6)
            q_ccw_kw *= clamp(chi_choke, SCRUB_COND_CHOKE_MIN, 1.0)

        C_ccw_kwk  = max(m_ccw_kgh * SCRUB_CCW_CP / 3600.0, 1e-6)
        eps_ht     = 1.0 - math.exp(-SCRUB_UA_KWK / C_ccw_kwk)
        ua_eff_kwk = max(eps_ht * C_ccw_kwk, 1e-6)

        theta_dev  = (self.hic604_pct if self.hic604_pct is not None else SCRUB_HIC604_DES_PCT) / SCRUB_HIC604_DES_PCT - 1.0
        t_overflow_cond = min(t_ccw_in + q_ccw_kw / ua_eff_kwk, SCRUB_T_PROC_C)
        t_ccw_out  = t_ccw_in + (t_overflow_cond - t_ccw_in) * eps_ht
        
        t_overflow = min(max(t_overflow_cond - SCRUB_OVERFLOW_T_VENT_GAIN * theta_dev, t_ccw_in),
                         SCRUB_T_PROC_C)
                         
        if carry_mass_kgh > 0.0 and self.t_carry_c is not None:
            m_ov_tot = sum(overflow[k] * MW_COMP[k] for k in MW_COMP)
            if m_ov_tot > 0.0:
                w_carry    = carry_mass_kgh / m_ov_tot
                t_overflow = min(t_overflow + w_carry * (self.t_carry_c - t_overflow), SCRUB_T_PROC_C)
                
        dT_ccw     = t_ccw_out - t_ccw_in
        
        nc = self.nc_act if self.nc_act is not None else SCRUB_OFFGAS_NC_DES
        t_offgas   = min(max(SCRUB_OFFGAS_T_C + SCRUB_OFFGAS_T_GAIN * (nc - SCRUB_OFFGAS_NC_DES)
                             + SCRUB_OFFGAS_T_VENT_GAIN * theta_dev,
                             t_ccw_in), SCRUB_T_PROC_C)

        # Pressure Drop calculation
        mass_flow_in = sum(feed[k] * MW_COMP[k] for k in MW_COMP)
        dp_bar = pressure_drop.scrubber_e03.calc_tube_side_dp(
            mass_flow_kg_s=mass_flow_in / 3600.0,
            density_kg_m3=offgas_in.density,
            viscosity_pa_s=offgas_in.viscosity
        )
        out_p = max(offgas_in.P - dp_bar, 1.0)
        
        # Map back to output streams
        vent_out.set_state(T=t_offgas, P=out_p)
        vent_out.comp = offgas
        
        carbamate_out.set_state(T=t_overflow, P=out_p)
        carbamate_out.comp = overflow
        
        ccw_out.set_state(T=t_ccw_out, mass_flow=m_ccw_kgh)
        
        # Clear input dirty flags
        for stream in self.inputs:
            stream.is_dirty = False
            
        # Store diagnostics
        self.diagnostics = {
            "feed_kmolh": feed, "carb_kmolh": carb,
            "offgas_kmolh": offgas, "overflow_kmolh": overflow,
            "closure_resid": closure_resid, "closure_kmolh": closure_kmolh,
            "capacity_ratio": capacity_ratio, "absorbed_kmolh": split["absorbed"],
            "breakthrough_kmolh": offgas.get("NH3", 0.0) + offgas.get("CO2", 0.0),
            "co2_abs": co2_abs,
            "q_carb_kw": q_carb_kw, "q_ccw_kw": q_ccw_kw,
            "t_ccw_in": t_ccw_in, "t_ccw_out": t_ccw_out, "dT_ccw": dT_ccw,
            "m_ccw_kgh": m_ccw_kgh, "co2_scale": s, "vent_ratio": self.vent_ratio,
            "eps_ht": eps_ht, "ua_eff_kwk": ua_eff_kwk,
            "T_offgas": t_offgas, "P_offgas": SCRUB_OFFGAS_P_BARA,
            "T_overflow": t_overflow, "P_overflow": SCRUB_OVERFLOW_P_BARA
        }
