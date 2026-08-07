from core.unit import UnitOperation
from core.stream import Stream

class Ejector322F001(UnitOperation):
    """
    322F001 High-Pressure Ejector - Sequential Modular Port
    """
    def __init__(self, name: str, motive_in: Stream, discharge_out: Stream):
        super().__init__(name, inputs=[motive_in], outputs=[discharge_out])
        
        from main import EJ_OPEN_DES
        self.hv_open_pct = EJ_OPEN_DES
        self.scrub_level_frac = 1.0
        
        self.diagnostics = {}

    def solve(self):
        import main as main_module
        from main import (
            MW_COMP, EJ_T_SUCTION_C, EJ_SPINDLE_R, EJ_OPEN_DES, EJ_STALL_PHI,
            EJ_STALL_REC, EJ_STALL_EXP, EJ_SUC_TOT_DES, EJ_HYD_FRAC_MAX,
            EJ_CARB_FRAC, EJ_CP_N, EJ_CP_C, EJ_CP_D, EJ_P_DISCH_BARA, EJ_RHO_DISCH,
            EJ_MOTIVE_NH3_DES, clamp
        )
        motive_in = self.inputs[0]
        discharge_out = self.outputs[0]
        
        motive_nh3_kgh = motive_in.mass_flow
        T_motive_C = motive_in.T
        
        if motive_nh3_kgh <= 1e-6:
            comp = {k: 0.0 for k in MW_COMP}
            discharge_out.set_state(T=EJ_T_SUCTION_C, P=0.0, mass_flow=0.0)
            discharge_out.comp = comp
            
            for stream in self.inputs:
                stream.is_dirty = False
                
            self.diagnostics = {
                "comp": comp, "total_kgh": 0.0, "suction_kgh": 0.0,
                "mol_kmolh": 0.0, "MW": 0.0, "T_C": EJ_T_SUCTION_C, "P_bara": 0.0,
                "rho": 0.0, "vol_m3h": 0.0, "mu": 0.0
            }
            return

        open_eff = clamp(self.hv_open_pct, 10.0, 100.0)
        
        _ej_mot_des = main_module.EJ_MOTIVE_DES_LIVE if hasattr(main_module, 'EJ_MOTIVE_DES_LIVE') and main_module.EJ_MOTIVE_DES_LIVE is not None else EJ_MOTIVE_NH3_DES
        
        phi_m = motive_nh3_kgh / _ej_mot_des
        phi_sp = EJ_SPINDLE_R ** ((EJ_OPEN_DES - open_eff) / 100.0)
        f_stall = clamp((phi_m - EJ_STALL_PHI) / (EJ_STALL_REC - EJ_STALL_PHI), 0.0, 1.0) ** EJ_STALL_EXP
        capacity = EJ_SUC_TOT_DES * phi_m * phi_sp * f_stall
        
        frac_eff = min(max(self.scrub_level_frac, 0.0), EJ_HYD_FRAC_MAX)
        m_suc = capacity * frac_eff
        
        suction = {k: m_suc * EJ_CARB_FRAC.get(k, 0.0) for k in MW_COMP}
        disch = {k: (motive_nh3_kgh if k == "NH3" else 0.0) + suction[k] for k in MW_COMP}
        
        m_d = sum(disch.values())
        n_d = sum(disch[k] / MW_COMP[k] for k in MW_COMP)
        
        T_d = (motive_nh3_kgh * EJ_CP_N * T_motive_C + m_suc * EJ_CP_C * EJ_T_SUCTION_C) / (m_d * EJ_CP_D)
        
        discharge_out.set_state(T=T_d, P=EJ_P_DISCH_BARA, mass_flow=m_d)
        # Assuming Stream comp is in kmol/h generally, but ejector returns kg/h in disch.
        # However, main.py ejector returns kg/h in `disch`. I will preserve the diagnostic dict.
        # Stream comp standard is kmol/h.
        discharge_out.comp = {k: disch[k] / MW_COMP[k] for k in MW_COMP}
        
        for stream in self.inputs:
            stream.is_dirty = False
            
        self.diagnostics = {
            "comp": disch, "total_kgh": m_d, "suction_kgh": m_suc, "mol_kmolh": n_d,
            "MW": (m_d/n_d if n_d else 0.0), "T_C": T_d, "P_bara": EJ_P_DISCH_BARA,
            "rho": EJ_RHO_DISCH, "vol_m3h": m_d/EJ_RHO_DISCH, "mu": m_suc/motive_nh3_kgh
        }
