import math
from typing import List, Optional
from core.unit import UnitOperation
from core.stream import Stream

# Importing required constants and helpers from main
from main import (
    MW_COMP, HPCC_STEAM_TSAT_C, HPCC_T_PROD_DES_C, SYN_P_DES_BARA,
    HPCC_FRAC_GAS_DES, HPCC_TAU_FILL_MIN, HPCC_DH_CARB_KJMOL, HPCC_CP_GAS,
    HPCC_LATENT_4BAR, HPCC_UA, bubble_p_322e002, _hpcc_flash_split, clamp
)
import main as main_module # For reactor constants
import pressure_drop

class Hpcc322E002(UnitOperation):
    """
    322E002 High-Pressure Carbamate Condenser - Sequential Modular Port
    """
    def __init__(self, name: str, 
                 gas_in: Stream, liq_in: Stream, 
                 gas_out: Stream, liq_out: Stream):
        super().__init__(name, inputs=[gas_in, liq_in], outputs=[gas_out, liq_out])
        
        # State variables for SM relaxation
        self._t_prod_prev = HPCC_T_PROD_DES_C
        self._phi_prev: Optional[dict] = None
        self.dt = 0.0  # Dynamic time step. If 0, stays at equilibrium target
        
        # External disturbances/parameters
        self.t_shell = HPCC_STEAM_TSAT_C
        self.gate = 1.0
        self.p_loop = SYN_P_DES_BARA
        
        self.diagnostics = {}

    def solve(self):
        # Streams
        gas_in = self.inputs[0]
        liq_in = self.inputs[1]
        
        gas_out = self.outputs[0]
        liq_out = self.outputs[1]
        
        # Logic ported from main.py's hpcc_322e002
        gas_feed = {
            "top_kmolh": gas_in.comp,
            "T_top": gas_in.T
        }
        
        liq_feed = {
            "comp": {k: liq_in.comp.get(k, 0.0) * MW_COMP[k] for k in MW_COMP}, # main uses mass for liq_feed input? Wait, liq_feed is ejector return in kg/h in main.
            "T_C": liq_in.T
        }
        
        # 1. combined tube-side feed (kmol/h per comp)
        feed = {k: gas_feed["top_kmolh"].get(k, 0.0) + liq_in.comp.get(k, 0.0) for k in MW_COMP}
        
        # 2. phase split
        phi_eq  = _hpcc_flash_split(feed, self._t_prod_prev, self.p_loop)
        _base   = self._phi_prev if self._phi_prev is not None else HPCC_FRAC_GAS_DES
        a_phi   = clamp(self.dt / (HPCC_TAU_FILL_MIN * 60.0), 0.0, 1.0)
        phi_flm = {k: _base.get(k, HPCC_FRAC_GAS_DES.get(k, 0.0))
                      + a_phi * (phi_eq[k] - _base.get(k, HPCC_FRAC_GAS_DES.get(k, 0.0)))
                   for k in MW_COMP}
        
        phi_gas = {k: HPCC_FRAC_GAS_DES.get(k, 0.0)
                      + self.gate * (phi_flm[k] - HPCC_FRAC_GAS_DES.get(k, 0.0)) for k in MW_COMP}
                      
        gas = {k: feed[k] * phi_gas[k] for k in MW_COMP}
        liq = {k: feed[k] - gas[k] for k in MW_COMP}
        
        gas_kgh = {k: gas[k] * MW_COMP[k] for k in MW_COMP}
        liq_kgh = {k: liq[k] * MW_COMP[k] for k in MW_COMP}
        
        gas_n = sum(gas.values());     liq_n = sum(liq.values())
        gas_m = sum(gas_kgh.values()); liq_m = sum(liq_kgh.values())
        
        # 3. shell-side duty
        co2_abs   = max(gas_feed["top_kmolh"].get("CO2", 0.0) - gas["CO2"], 0.0)
        q_carb_kw = co2_abs * 1000.0 * HPCC_DH_CARB_KJMOL / 3600.0
        q_sens_kw = gas_m * HPCC_CP_GAS * max(gas_feed["T_top"] - HPCC_T_PROD_DES_C, 0.0) / 3600.0
        duty_kw   = q_carb_kw + q_sens_kw
        steam_kgh = duty_kw * 3600.0 / HPCC_LATENT_4BAR
        
        # 4. adiabatic carbamate-exotherm spike
        m_gas_in   = sum(gas_feed["top_kmolh"].get(k, 0.0) * MW_COMP[k] for k in MW_COMP)
        m_liq_in   = sum(liq_feed["comp"].get(k, 0.0) for k in MW_COMP)
        m_dot      = m_gas_in + m_liq_in
        
        T_feed_mix = ((m_gas_in * gas_feed["T_top"] + m_liq_in * liq_feed["T_C"]) / m_dot
                      if m_dot > 1e-9 else self.t_shell)
                      
        T_adb      = T_feed_mix + q_carb_kw * 3600.0 / max(m_dot * HPCC_CP_GAS, 1e-9)
        
        if HPCC_UA is None:
            T_prod = HPCC_T_PROD_DES_C
        else:
            T_prod_live = self.t_shell + (T_adb - self.t_shell) \
                          * math.exp(-HPCC_UA / max(m_dot * HPCC_CP_GAS, 1e-9))
            T_prod = HPCC_T_PROD_DES_C + self.gate * (T_prod_live - HPCC_T_PROD_DES_C)
            
        q_steam_kw = max(duty_kw - m_dot * HPCC_CP_GAS * (T_prod - HPCC_T_PROD_DES_C) / 3600.0, 0.0)
        
        _co2   = feed.get("CO2", 0.0)
        L0_DES = main_module.reactor.L0_DES
        W0_DES = main_module.reactor.W0_DES
        
        L_hpcc = (clamp(feed.get("NH3", 0.0) / _co2, 0.5 * L0_DES, 2.0 * L0_DES)
                  if _co2 > 1e-9 else L0_DES)
        W_hpcc = (clamp(feed.get("H2O", 0.0) / _co2, 0.5 * W0_DES, 2.0 * W0_DES)
                  if _co2 > 1e-9 else W0_DES)
                  
        p_bub  = bubble_p_322e002(T_prod, L_hpcc, W_hpcc)
        
        # Pressure Drop calculation
        dp_bar = pressure_drop.condenser_e02.calc_tube_side_dp(
            mass_flow_kg_s=m_dot / 3600.0,
            density_kg_m3=gas_in.density,
            viscosity_pa_s=gas_in.viscosity
        )
        
        # Determine output pressure. 
        # Using the thermodynamic bubble pressure, reduced by hydraulic losses.
        out_p = max(p_bub - dp_bar, 1.0)
        
        # Update output streams
        gas_out.set_state(T=T_prod, P=out_p, mass_flow=gas_m)
        gas_out.comp = gas
        
        liq_out.set_state(T=T_prod, P=out_p, mass_flow=liq_m)
        liq_out.comp = liq
        
        # Clear dirty flags
        for stream in self.inputs:
            stream.is_dirty = False
            
        # Update states for next tick
        self._t_prod_prev = T_prod
        self._phi_prev = phi_flm
        
        # Store diagnostics matching old function return
        self.diagnostics = {
            "phi_gas": phi_gas, "phi_film": phi_flm, "phi_eq": phi_eq,
            "feed_kmolh": feed,
            "gas_kmolh": gas, "liq_kmolh": liq,
            "gas_kgh": gas_m, "liq_kgh": liq_m,
            "gas_th": gas_m / 1000.0, "liq_th": liq_m / 1000.0,
            "gas_mol": gas_n, "liq_mol": liq_n,
            "gas_MW": (gas_m / gas_n if gas_n else 0.0),
            "liq_MW": (liq_m / liq_n if liq_n else 0.0),
            "gas_mol_pct":  {k: (gas[k] / gas_n * 100.0 if gas_n else 0.0) for k in MW_COMP},
            "liq_mass_pct": {k: (liq_kgh[k] / liq_m * 100.0 if liq_m else 0.0) for k in MW_COMP},
            "T_prod": T_prod, "T_feed_mix": T_feed_mix, "T_adb": T_adb, "m_dot": m_dot, "P_bara": p_bub,
            "P_bub": p_bub, "L_hpcc": L_hpcc, "W_hpcc": W_hpcc,
            "duty_kw": duty_kw, "steam_kgh": steam_kgh, "q_steam_kw": q_steam_kw,
        }
