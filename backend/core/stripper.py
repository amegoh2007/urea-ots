import math
from typing import List, Optional
from core.unit import UnitOperation
from core.stream import Stream
import pressure_drop

import main as main_module
from main import (
    MW_COMP, STRIP_FEED207_KMOLH, STRIP_FEED207_T_C, CO2_DES_KGH, CO2_DES_KMOLH,
    CO2_FEED_MOLFRAC, STRIP_STEAM_T_DES_C, STRIP_DT_STEAM_DES_C, STRIP_FEED_DES_KGH,
    STRIP_T_BOTTOM_DES_C, STRIP_ETA_KT, STRIP_ETA_FLOOR, STRIP_T_FLOOD_ANCHOR_C,
    STRIP_N_TUBES, STRIP_FLOOD_KGH_TUBE, STRIP_FLOOD_T_K, STRIP_STRIPCOOL_MAX,
    STRIP_STRIPCOOL_KGL, STRIP_ETA_KN, STRIP_ETA_KW, STRIP_L0, STRIP_W0,
    STRIP_T_TOPGAS_DES_C, STRIP_T_TOP_LOAD_K, STRIP_XI_HYD_DES, STRIP_XI_BIU_DES,
    STRIP_BIU_EA, STRIP_R_GAS_J, STRIP_T_BIU_DES_K, STRIP_UREA0, STRIP_DH_CARB_JMOL,
    STRIP_CP_BOTTOM, STRIP_FLOOD_ETA_FLOOR, STRIP_P_DES_BARA, STRIP_FRAC_DES,
    STRIP_SLIP_GAIN, STRIP_DH_NH3_JMOL, STRIP_LAM_H2O_JMOL, STRIP_DH_HYD_JMOL,
    STRIP_CP_GAS, clamp
)

class Stripper322E001(UnitOperation):
    """
    322E001 High-Pressure Stripper - Sequential Modular Port
    """
    def __init__(self, name: str, 
                 co2_in: Stream, overflow_in: Stream, steam_in: Stream, 
                 top_gas_out: Stream, bottom_liq_out: Stream):
        super().__init__(name, inputs=[co2_in, overflow_in, steam_in], 
                         outputs=[top_gas_out, bottom_liq_out])
        
        self.diagnostics = {}
        self.p_bara = STRIP_P_DES_BARA

    def solve(self):
        co2_in = self.inputs[0]
        overflow_in = self.inputs[1]
        steam_in = self.inputs[2]
        
        top_gas_out = self.outputs[0]
        bottom_liq_out = self.outputs[1]
        
        # 1. Component molar feed
        co2_feed_th = co2_in.mass_flow / 1000.0  # Stream mass is in kg/h
        co2_scale = co2_feed_th / (CO2_DES_KGH / 1000.0) if CO2_DES_KGH > 0 else 0.0
        
        co2_kmolh = {k: CO2_FEED_MOLFRAC.get(k, 0.0) * CO2_DES_KMOLH * co2_scale for k in MW_COMP}
        feed = {k: overflow_in.comp.get(k, 0.0) + co2_kmolh.get(k, 0.0) for k in MW_COMP}
        
        T_steam_C = steam_in.T
        T_feed_C = overflow_in.T
        
        # 2. Stripping efficiency
        dTs = T_steam_C - STRIP_STEAM_T_DES_C
        eta_T_steam = clamp(T_steam_C / STRIP_STEAM_T_DES_C, 0.0, 1.15)
        
        m_feed_kgh = sum(feed[k] * MW_COMP[k] for k in MW_COMP)
        raw_load = STRIP_DT_STEAM_DES_C * (STRIP_FEED_DES_KGH / max(m_feed_kgh, 1e-6) - 1.0)
        cap = max(STRIP_STEAM_T_DES_C - STRIP_T_BOTTOM_DES_C + 0.3 * dTs, 1e-6)
        dT_load = cap * (1.0 - math.exp(-raw_load / cap)) if raw_load > 0.0 else raw_load
        g_T = clamp(1.0 + STRIP_ETA_KT * dT_load / STRIP_T_BOTTOM_DES_C, STRIP_ETA_FLOOR, 1.05)
        
        strip_flood_gap = max(STRIP_T_FLOOD_ANCHOR_C - STRIP_T_BOTTOM_DES_C, 1e-6)
        dT_bot = dT_load if raw_load > 0.0 else strip_flood_gap * (1.0 - math.exp(raw_load / strip_flood_gap))
        
        flood_frac = m_feed_kgh / STRIP_N_TUBES / STRIP_FLOOD_KGH_TUBE
        flood_x = max(flood_frac - 1.0, 0.0)
        dT_flood = strip_flood_gap * (1.0 - math.exp(-STRIP_FLOOD_T_K * flood_x))
        dT_bot = dT_bot + dT_flood
        
        r_GL = co2_scale * STRIP_FEED_DES_KGH / max(m_feed_kgh, 1e-6) - 1.0
        dT_strip = -STRIP_STRIPCOOL_MAX * (1.0 - math.exp(-STRIP_STRIPCOOL_KGL * max(r_GL, 0.0)))
        
        # Use reactor constants natively
        reactor = main_module.reactor
        _co2 = feed.get("CO2", 0.0)
        
        L_react = self.L_feed if hasattr(self, "L_feed") and self.L_feed is not None else ((feed.get("NH3", 0.0) / _co2) if _co2 > 1e-9 else reactor.L0_DES)
        W_react = self.W_feed if hasattr(self, "W_feed") and self.W_feed is not None else ((feed.get("H2O", 0.0) / _co2) if _co2 > 1e-9 else reactor.W0_DES)
        
        g_NC = clamp(1.0 - STRIP_ETA_KN * (L_react - reactor.L0_DES), STRIP_ETA_FLOOR, 1.05)
        g_HC = clamp(1.0 - STRIP_ETA_KW * (W_react - reactor.W0_DES), STRIP_ETA_FLOOR, 1.05)
        eta_T = clamp(eta_T_steam * g_NC * g_HC * g_T, 0.0, 1.15)
        
        L_strip = (feed["NH3"] / feed["CO2"]) if feed["CO2"] else STRIP_L0
        W_strip = (feed["H2O"] / feed["CO2"]) if feed["CO2"] else STRIP_W0
        
        # 3. Reactions
        T_bot_C = min(STRIP_T_BOTTOM_DES_C + 0.7 * dTs + dT_bot + dT_strip, T_steam_C)
        T_bot_K = T_bot_C + 273.15
        T_top_C = min(STRIP_T_TOPGAS_DES_C + 0.6 * dTs + STRIP_T_TOP_LOAD_K * dT_bot + dT_strip, T_steam_C)
        
        xi_hyd_raw = STRIP_XI_HYD_DES * eta_T
        xi_hyd = max(min(xi_hyd_raw, feed["Urea"], feed["H2O"]), 0.0)
        urea_after_hyd = max(feed["Urea"] - xi_hyd, 0.0)
        xi_biu_raw = (STRIP_XI_BIU_DES * math.exp((STRIP_BIU_EA / STRIP_R_GAS_J) * (1.0 / STRIP_T_BIU_DES_K - 1.0 / T_bot_K))
                      * (feed["Urea"] / STRIP_UREA0))
        xi_biu = max(min(xi_biu_raw, 0.5 * urea_after_hyd), 0.0)
        
        avail = dict(feed)
        avail["Urea"]   -= (xi_hyd + 2.0 * xi_biu)
        avail["Biuret"] += xi_biu
        avail["NH3"]    += (2.0 * xi_hyd + xi_biu)
        avail["CO2"]    += xi_hyd
        avail["H2O"]    -= xi_hyd
        
        # 3b. Hydrodynamic efficiency knockdown
        n_carb_avail = max(avail["CO2"] - co2_kmolh.get("CO2", 0.0), 1e-9)
        q_carb_avail = n_carb_avail * STRIP_DH_CARB_JMOL
        q_flood_def  = m_feed_kgh * STRIP_CP_BOTTOM * dT_flood
        g_flood      = clamp(1.0 - q_flood_def / q_carb_avail, STRIP_FLOOD_ETA_FLOOR, 1.0)
        
        # 4. Strip-fraction modulation
        eta_co2 = clamp(0.5 + 0.5 * co2_scale, 0.4, 1.05)
        eta_P   = clamp(2.0 - self.p_bara / STRIP_P_DES_BARA, 0.85, 1.15)
        mod = clamp(eta_T_steam * eta_co2 * eta_P, 0.0, 1.12) * min(g_T, 1.0) * g_flood
        slip = max(1.0 - g_NC, 0.0) + max(1.0 - g_HC, 0.0)
        
        top = {}; bot = {}
        for k in MW_COMP:
            f = clamp(STRIP_FRAC_DES.get(k, 0.0) * mod, 0.0, 0.999)
            if k in ("NH3", "CO2"):
                f = clamp(f + STRIP_SLIP_GAIN * slip * (1.0 - f), 0.0, 0.999)
            top[k] = avail[k] * f
            bot[k] = avail[k] * (1.0 - f)
            
        top_kgh = {k: top[k] * MW_COMP[k] for k in MW_COMP}
        bot_kgh = {k: bot[k] * MW_COMP[k] for k in MW_COMP}
        top_m = sum(top_kgh.values()); top_n = sum(top.values())
        bot_m = sum(bot_kgh.values()); bot_n = sum(bot.values())
        
        # 6. Enthalpy balance
        n_co2_desorb = max(top["CO2"] - co2_kmolh.get("CO2", 0.0), 0.0)
        n_nh3_free   = max(top["NH3"] - co2_kmolh.get("NH3", 0.0) - 2.0 * n_co2_desorb, 0.0)
        q_carb_kw = n_co2_desorb * STRIP_DH_CARB_JMOL / 3600.0
        q_nh3_kw  = n_nh3_free   * STRIP_DH_NH3_JMOL / 3600.0
        q_h2o_kw  = max(top["H2O"] - co2_kmolh.get("H2O", 0.0), 0.0) * STRIP_LAM_H2O_JMOL / 3600.0
        q_hyd_kw  = xi_hyd * STRIP_DH_HYD_JMOL / 3600.0
        q_sens_kw = (bot_m * STRIP_CP_BOTTOM * (T_bot_C - T_feed_C) + top_m * STRIP_CP_GAS * (T_top_C - T_feed_C)) / 3600.0
        duty_raw_kw = q_carb_kw + q_nh3_kw + q_h2o_kw + q_hyd_kw + q_sens_kw
        
        # 7. Pressure Drop
        dp_bar = pressure_drop.stripper_e01.calc_tube_side_dp(
            mass_flow_kg_s=m_feed_kgh / 3600.0,
            density_kg_m3=overflow_in.density,
            viscosity_pa_s=overflow_in.viscosity
        )
        out_p = max(overflow_in.P - dp_bar, 1.0)
        
        # Update output streams
        top_gas_out.set_state(T=T_top_C, P=out_p, mass_flow=top_m)
        top_gas_out.comp = top
        
        bottom_liq_out.set_state(T=T_bot_C, P=out_p, mass_flow=bot_m)
        bottom_liq_out.comp = bot
        
        for stream in self.inputs:
            stream.is_dirty = False
            
        # Store diagnostics matching old function
        self.diagnostics = {
            "top_kmolh": top, "bot_kmolh": bot, "feed_kmolh": feed,
            "T_top": T_top_C, "T_bot": T_bot_C, "dT_bot": dT_bot, "T_steam": T_steam_C,
            "top_kgh": top_m, "bot_kgh": bot_m, "top_mol": top_n, "bot_mol": bot_n,
            "top_MW": (top_m / top_n if top_n else 0.0), "bot_MW": (bot_m / bot_n if bot_n else 0.0),
            "top_mass_pct": {k: (top_kgh[k] / top_m * 100.0 if top_m else 0.0) for k in MW_COMP},
            "bot_mass_pct": {k: (bot_kgh[k] / bot_m * 100.0 if bot_m else 0.0) for k in MW_COMP},
            "duty_kw": duty_raw_kw, "q_carb_kw": q_carb_kw, "q_nh3_kw": q_nh3_kw,
            "q_h2o_kw": q_h2o_kw, "q_hyd_kw": q_hyd_kw, "q_sens_kw": q_sens_kw,
            "L_strip": L_strip, "W_strip": W_strip, "eta_T": eta_T, "g_T": g_T, "mod": mod,
            "xi_hyd": xi_hyd, "xi_biu": xi_biu, "urea_feed": feed["Urea"],
            "flood_frac": flood_frac, "g_flood": g_flood, "dT_flood": dT_flood,
            "co2_scale": co2_scale, "r_GL": r_GL, "dT_strip": dT_strip
        }
