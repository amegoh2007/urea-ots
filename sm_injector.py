import re

with open('backend/main.py', 'r', encoding='utf-8') as f:
    code = f.read()

sm_setup = """# ----- SM Flowsheet Setup -----
from core.flowsheet import Flowsheet
from core.stream import Stream
from core.ejector import Ejector322F001
from core.stripper import Stripper322E001
from core.hpcc import Hpcc322E002
from core.scrubber import Scrubber322E003
from core.reactor import Reactor322R001
from core.valve import Valve322604
from core.vacuum import VacuumTrain324

_sm_flowsheet = Flowsheet("Urea HP Loop")
_ej_motive = Stream("Ejector_Motive_In")
_ej_disch = Stream("Ejector_Disch_Out")
_ej_unit = Ejector322F001("322F001_Ejector", _ej_motive, _ej_disch)

_strip_co2_in = Stream("Stripper_CO2_In")
_strip_overflow_in = Stream("Stripper_Overflow_In")
_strip_steam_in = Stream("Stripper_Steam_In")
_strip_top_gas_out = Stream("Stripper_Top_Gas_Out")
_strip_bottom_liq_out = Stream("Stripper_Bottom_Liq_Out")
_strip_unit = Stripper322E001("322E001_Stripper", _strip_co2_in, _strip_overflow_in, _strip_steam_in, _strip_top_gas_out, _strip_bottom_liq_out)

_hpcc_gas_in = Stream("HPCC_Gas_In")
_hpcc_liq_in = Stream("HPCC_Liq_In")
_hpcc_gas_out = Stream("HPCC_Gas_Out")
_hpcc_liq_out = Stream("HPCC_Liq_Out")
_hpcc_unit = Hpcc322E002("322E002_HPCC", _hpcc_gas_in, _hpcc_liq_in, _hpcc_gas_out, _hpcc_liq_out)

_scrub_offgas_in = Stream("Scrub_Offgas_In")
_scrub_wash_in = Stream("Scrub_Wash_In")
_scrub_ccw_in = Stream("Scrub_CCW_In")
_scrub_vent_out = Stream("Scrub_Vent_Out")
_scrub_carbamate_out = Stream("Scrub_Carbamate_Out")
_scrub_ccw_out = Stream("Scrub_CCW_Out")
_scrub_unit = Scrubber322E003("322E003_Scrubber", _scrub_offgas_in, _scrub_wash_in, _scrub_ccw_in, _scrub_vent_out, _scrub_carbamate_out, _scrub_ccw_out)

_react_feed_in = Stream("React_Feed_In")
_react_overflow_out = Stream("React_Overflow_Out")
_react_offgas_out = Stream("React_Offgas_Out")
_react_unit = Reactor322R001("322R001_Reactor", _react_feed_in, _react_overflow_out, _react_offgas_out)

_valve_og_in = Stream("Valve_Offgas_In")
_valve_purge_out = Stream("Valve_Purge_Out")
_valve_unit = Valve322604("HV_322604", _valve_og_in, _valve_purge_out)

_vac_evap_in = Stream("Vac_Evap_In")
_vac_v1_in = Stream("Vac_V1_In")
_vac_v2_in = Stream("Vac_V2_In")
_vac_fa1_in = Stream("Vac_FA1_In")
_vac_fa2_in = Stream("Vac_FA2_In")
_vac_mot924_in = Stream("Vac_Mot924_In")
_vac_mot927_in = Stream("Vac_Mot927_In")
_vac_mot929_in = Stream("Vac_Mot929_In")
_vac_cond_out = Stream("Vac_Cond_Out")
_vac_vent_out = Stream("Vac_Vent_Out")
_vac_unit = VacuumTrain324("324_VacuumTrain", _vac_evap_in, _vac_v1_in, _vac_v2_in, _vac_fa1_in, _vac_fa2_in, _vac_mot924_in, _vac_mot927_in, _vac_mot929_in, _vac_cond_out, _vac_vent_out)

_sm_flowsheet.add_unit(_ej_unit)
_sm_flowsheet.add_unit(_strip_unit)
_sm_flowsheet.add_unit(_hpcc_unit)
_sm_flowsheet.add_unit(_scrub_unit)
_sm_flowsheet.add_unit(_react_unit)
_sm_flowsheet.add_unit(_valve_unit)
_sm_flowsheet.add_unit(_vac_unit)
# ------------------------------

def step_sim(dt: float) -> dict:"""

code = code.replace("def step_sim(dt: float) -> dict:", sm_setup)

# 1. Ejector Replacement
ej_old = "    ej = ejector_322f001(m_ej, EJ_MOTIVE_T_DES_C, s.HIC_322F001)"
ej_new = """    _ej_motive.set_state(mass_flow=m_ej, T=EJ_MOTIVE_T_DES_C)
    _ej_unit.hv_open_pct = s.HIC_322F001
    _ej_unit.solve()
    ej = _ej_unit.diagnostics"""
code = code.replace(ej_old, ej_new)

# 2. Stripper Replacement
strip_old = """    strip = stripper_322e001(
        s.FIC_321101, s.T_CO2_in, p_strip,
        overflow_kmolh=m_705, L_feed=s.reactor_L, W_feed=s.reactor_W,
        level_pct=s.LIC_322001, t_shell=t_902_shell, 
        stripper_co2_bias=s.SIC_321950.pv
    )"""
strip_new = """    _strip_co2_in.set_state(mass_flow=s.FIC_321101, T=s.T_CO2_in, P=p_strip)
    _strip_co2_in.comp = {"CO2": s.FIC_321101 / MW_COMP["CO2"]}
    _strip_overflow_in.comp = m_705
    _strip_unit.l_feed = s.reactor_L
    _strip_unit.w_feed = s.reactor_W
    _strip_unit.level_pct = s.LIC_322001
    _strip_unit.t_shell = t_902_shell
    _strip_unit.stripper_co2_bias = s.SIC_321950.pv
    _strip_unit.solve()
    strip = _strip_unit.diagnostics"""
code = code.replace(strip_old, strip_new)

# 3. HPCC Replacement
hpcc_old = "    hpcc = hpcc_322e002(strip[\"gas_kmolh\"], ej[\"comp\"], t_shell=t_504_shell, gate=1.0)"
hpcc_new = """    _hpcc_gas_in.comp = strip["gas_kmolh"]
    _hpcc_liq_in.comp = ej["comp"]
    _hpcc_unit.t_shell = t_504_shell
    _hpcc_unit.gate = 1.0
    _hpcc_unit.solve()
    hpcc = _hpcc_unit.diagnostics"""
code = code.replace(hpcc_old, hpcc_new)

# 4. Scrubber Replacement
scrub_old = """    scrub = scrub_322e003(
        hpcc["gas_kmolh"], react["offgas_kmolh"],
        hpcc["T_out"], react["T_offgas"],
        m_718A, t_718A,
        p_up=p_cc,
        cw_t_in=cw_supply_t,
        nc_act=s.a328_c001_L, theta_dev=s.a328_c001_theta
    )"""
scrub_new = """    _scrub_offgas_in.comp = hpcc["gas_kmolh"]
    _scrub_offgas_in.set_state(T=hpcc["T_out"], P=p_cc)
    
    _scrub_wash_in.comp = react.get("offgas_kmolh", {k: 0.0 for k in MW_COMP})
    _scrub_wash_in.set_state(T=react.get("T_offgas", 185.0))
    _scrub_unit.m_718A = m_718A
    _scrub_unit.t_718A = t_718A
    _scrub_unit.cw_t_in = cw_supply_t
    _scrub_unit.nc_act = s.a328_c001_L
    _scrub_unit.theta_dev = s.a328_c001_theta
    _scrub_unit.solve()
    scrub = _scrub_unit.diagnostics"""
code = code.replace(scrub_old, scrub_new)

# 5. Reactor Replacement
react_old = """    react = react_322r001(
        hpcc, scrub,
        p_up=p_cc,
        w0_recon=s.reactor_W,
        tear_mass=REACT_TEAR_DES if (REACT_TEAR_DES and f_cons >= 1.0) else None,
        dt=dt
    )"""
react_new = """    _react_feed_in.comp = {k: hpcc.get("liq_kmolh", {}).get(k, 0.0) + scrub.get("overflow_kmolh", {}).get(k, 0.0) for k in MW_COMP}
    _react_unit.p_up = p_cc
    _react_unit.w0_recon = s.reactor_W
    _react_unit.tear_mass = REACT_TEAR_DES if (REACT_TEAR_DES and f_cons >= 1.0) else None
    _react_unit.dt = dt
    _react_unit.solve()
    react = _react_unit.diagnostics"""
code = code.replace(react_old, react_new)

# 6. Valve Replacement
valve_old = "    hv604 = hv_322604(scrub[\"offgas_kmolh\"], scrub[\"T_offgas\"], s.HIC_322604, scrub[\"P_offgas\"])"
valve_new = """    _valve_og_in.comp = scrub["offgas_kmolh"]
    _valve_og_in.set_state(T=scrub["T_offgas"], P=scrub["P_offgas"])
    _valve_unit.hic_pct = s.HIC_322604
    _valve_unit.solve()
    hv604 = _valve_unit.diagnostics"""
code = code.replace(valve_old, valve_new)

# 7. Vacuum Train Replacement
vac_old = """    vac324 = vacuum_train_324(
        m_evap, v1_m, v2_m, fa202_m, fa203_m,
        mot9605_m, mot927_m, mot929_m,
    )"""
vac_new = """    _vac_evap_in.set_state(mass_flow=m_evap)
    _vac_v1_in.set_state(mass_flow=v1_m)
    _vac_v2_in.set_state(mass_flow=v2_m)
    _vac_fa1_in.set_state(mass_flow=fa202_m)
    _vac_fa2_in.set_state(mass_flow=fa203_m)
    _vac_mot924_in.set_state(mass_flow=mot9605_m)
    _vac_mot927_in.set_state(mass_flow=mot927_m)
    _vac_mot929_in.set_state(mass_flow=mot929_m)
    _vac_unit.solve()
    vac324 = _vac_unit.diagnostics"""
code = code.replace(vac_old, vac_new)

# Insert sm_diagnostics into step_sim return
old_ret = '''        "RECYCLE_TEAR_RESIDUAL": {
            "method": "observed_dynamic_transport_tears",
            "is_solver_convergence": False,
            "tolerance": _tear_tol,
            "max_relative_residual": _tear_norm,
            "settled": _tear_norm <= _tear_tol,
            "residuals": _tear_resid,
        },'''

new_ret = '''        "RECYCLE_TEAR_RESIDUAL": {
            "method": "observed_dynamic_transport_tears",
            "is_solver_convergence": False,
            "tolerance": _tear_tol,
            "max_relative_residual": _tear_norm,
            "settled": _tear_norm <= _tear_tol,
            "residuals": _tear_resid,
        },
        "sm_diagnostics": {
            "hpcc": locals().get("hpcc", {}),
            "ej": locals().get("ej", {}),
            "react": locals().get("react", {}),
            "hv604": locals().get("hv604", {}),
            "vac324": locals().get("vac324", {}),
        },'''
code = code.replace(old_ret, new_ret)

# Fix pin hooks
old_pin = '''    _orig = hpcc_322e002                             # capture the settled HPCC product (HPCC_UA back-calc)
    _orig_ej = ejector_322f001                       #   and the settled design motive NH3 for the
    _cap = {}                                        #   EJ_MOTIVE_DES_LIVE -> phi_m bit-exact pin
    def _cap_hpcc(gas_feed, liq_feed, **kw):
        r = _orig(gas_feed, liq_feed, **kw)
        _cap["r"] = r
        return r
    def _cap_ej(motive, *a, **kw):
        rr = _orig_ej(motive, *a, **kw)
        _cap["ejm"] = motive
        return rr
    hpcc_322e002 = _cap_hpcc
    ejector_322f001 = _cap_ej
    for _ in range(18000):                           # 30 sim-min @ dt=0.1 s -> settled design steady state
        step_sim(0.1)
    hpcc_322e002 = _orig
    ejector_322f001 = _orig_ej'''

new_pin = '''    _cap = {}
    for _ in range(18000):
        res = step_sim(0.1)
    _cap["r"] = res["sm_diagnostics"]["hpcc"]
    _cap["ejm"] = res["sm_diagnostics"]["ej"]["suction_kgh"] / res["sm_diagnostics"]["ej"]["mu"] if res["sm_diagnostics"]["ej"].get("mu", 0) else EJ_MOTIVE_NH3_DES
'''
code = code.replace(old_pin, new_pin)

old_react = '''    _orig_r2 = react_322r001
    _capf = {}
    def _cap_react2(*a, **kw):
        rr = _orig_r2(*a, **kw)
        _capf["feed"]    = rr["feed_kmolh"]
        _capf["xi_urea"] = rr["xi_urea"]; _capf["xi_biu"] = rr["xi_biu"]
        _capf["L"]       = rr["L_feed"];  _capf["W"]      = rr["W_feed"]
        _capf["X"]       = rr["X_conv"]
        # design HPCC carbamate-MELT N/C (NH3/CO2) for the bubble_p_322e002 fN anchor.  a[0] is the
        #   hpcc dict (positional); hpcc_322e002 runs BEFORE react_322r001 this step so its raw combined
        #   melt feed is populated.  This is the NH3-richer melt N/C (~3.12324), DISTINCT from the
        #   reactor-feed N/C L (3.07296) captured above.  Guard a zero/absent CO2 (pre-warm pathological).
        _hf  = a[0].get("feed_kmolh", {}) if a else {}
        _co2 = _hf.get("CO2", 0.0)
        if _co2 > 1e-9:
            _capf["hpcc_L"] = _hf.get("NH3", 0.0) / _co2
        return rr
    react_322r001 = _cap_react2
    step_sim(0.1)                                    # one MAN-seed step (REACT_TEAR_DES still None ->
    react_322r001 = _orig_r2                          #   tear inactive -> feed_corrected == raw feed)'''

new_react = '''    _capf = {}
    res = step_sim(0.1)
    rr = res["sm_diagnostics"]["react"]
    _capf["feed"]    = rr["feed_kmolh"]
    _capf["xi_urea"] = rr["xi_urea"]; _capf["xi_biu"] = rr["xi_biu"]
    _capf["L"]       = rr["L_feed"];  _capf["W"]      = rr["W_feed"]
    _capf["X"]       = rr["X_conv"]
    _hf = res["sm_diagnostics"]["hpcc"].get("feed_kmolh", {})
    _co2 = _hf.get("CO2", 0.0)
    if _co2 > 1e-9:
        _capf["hpcc_L"] = _hf.get("NH3", 0.0) / _co2
'''
code = code.replace(old_react, new_react)

old_hpcc2 = '''    _orig2 = hpcc_322e002
    _cap2 = {}
    def _cap_hpcc2(gas_feed, liq_feed, **kw):
        rr = _orig2(gas_feed, liq_feed, **kw)
        _cap2["r"] = rr
        return rr
    hpcc_322e002 = _cap_hpcc2
    for _ in range(3000):                            # 5 sim-min: STOP on the stable MAN design plateau,
        step_sim(0.1)                                #   BEFORE the NH3-inventory main trip (21_2 latches
    hpcc_322e002 = _orig2                            #   ~tick 6500 in free-running MAN -> post-trip duty
    _duty_des    = _cap2["r"]["duty_kw"]'''

new_hpcc2 = '''    _cap2 = {}
    for _ in range(3000):
        res = step_sim(0.1)
    _cap2["r"] = res["sm_diagnostics"]["hpcc"]
    _duty_des    = _cap2["r"]["duty_kw"]'''
code = code.replace(old_hpcc2, new_hpcc2)

old_hv = '''    _orig_hv = hv_322604
    _caphv   = {}
    def _cap_hv(offgas, T_in, hic_pct, p_up):
        rr = _orig_hv(offgas, T_in, hic_pct, p_up)
        _caphv["m"] = rr["mass_kgh"]; _caphv["T"] = rr["T_out"]
        return rr
    hv_322604 = _cap_hv
    step_sim(0.1)                                    # one MAN-seed step (absorber pre-pin -> holds)
    hv_322604 = _orig_hv'''

new_hv = '''    _caphv = {}
    res = step_sim(0.1)
    rr = res["sm_diagnostics"]["hv604"]
    _caphv["m"] = rr["mass_kgh"]; _caphv["T"] = rr["T_out"]'''
code = code.replace(old_hv, new_hv)

# add sys.modules hack at top
code = code.replace('import math', 'import math\nimport sys\nif __name__ == "__main__":\n    sys.modules["main"] = sys.modules["__main__"]')


with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(code)
