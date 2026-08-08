import re
import sys

def apply_patches(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. HPCC: remove hydraulic head and add empty guard
    old_hpcc = '''    phi_in_hpcc  = (hpcc["liq_kgh"] / _hpcc_liq_des) if _hpcc_liq_des else phi_fwd
    phi_out_hpcc = phi_fwd * (s.hpcc_level_pct / HPCC_LEVEL_NLL_PCT)
    dL_hpcc      = k_loop_fill * (phi_in_hpcc - phi_out_hpcc) * 100.0 * dt / (HPCC_TAU_FILL_MIN * 60.0)
    s.hpcc_level_pct = clamp(s.hpcc_level_pct + dL_hpcc, 0.0, 100.0)'''
    
    new_hpcc = '''    phi_in_hpcc  = (hpcc["liq_kgh"] / _hpcc_liq_des) if _hpcc_liq_des else phi_fwd
    phi_out_hpcc = phi_fwd
    if s.hpcc_level_pct <= 0.0 and phi_out_hpcc > phi_in_hpcc:
        phi_out_hpcc = phi_in_hpcc
    dL_hpcc      = k_loop_fill * (phi_in_hpcc - phi_out_hpcc) * 100.0 * dt / (HPCC_TAU_FILL_MIN * 60.0)
    s.hpcc_level_pct = clamp(s.hpcc_level_pct + dL_hpcc, 0.0, 100.0)'''
    
    if old_hpcc in content:
        content = content.replace(old_hpcc, new_hpcc)
        print("Patched HPCC outflow")
    else:
        print("HPCC text not found!")

    # 2. Reactor empty guard
    old_reactor = '''    m_out_kgh      = reactor.outlet_line_outflow_kgph(level_m_react, _react_mdot_kgh, REACT_LEVEL_DES_M,
                                                      s.HIC_322605, REACT_HIC605_DES_PCT)  # HV-322605 take-off'''
    
    new_reactor = '''    m_out_kgh      = reactor.outlet_line_outflow_kgph(level_m_react, _react_mdot_kgh, REACT_LEVEL_DES_M,
                                                      s.HIC_322605, REACT_HIC605_DES_PCT)  # HV-322605 take-off
    if s.react_level_pct <= 0.0 and m_out_kgh > m_in_kgh:
        m_out_kgh = m_in_kgh'''
        
    if old_reactor in content:
        content = content.replace(old_reactor, new_reactor)
        print("Patched Reactor outflow")
    else:
        print("Reactor text not found!")

    # 3. Stripper empty guard
    old_strip = '''    m_span_kg = STRIP_SUMP_AREA_M2 * STRIP_LEVEL_SPAN_M * STRIP_RHO_BOTTOM
    s.strip_level = clamp(s.strip_level
                          + k_loop_fill * (delayed_bot_kgh - drain_kgh) / 3600.0 * dt / m_span_kg * 100.0,
                          0.0, 100.0)'''
                          
    new_strip = '''    m_span_kg = STRIP_SUMP_AREA_M2 * STRIP_LEVEL_SPAN_M * STRIP_RHO_BOTTOM
    if s.strip_level <= 0.0 and drain_kgh > delayed_bot_kgh:
        drain_kgh = delayed_bot_kgh
    s.strip_level = clamp(s.strip_level
                          + k_loop_fill * (delayed_bot_kgh - drain_kgh) / 3600.0 * dt / m_span_kg * 100.0,
                          0.0, 100.0)'''
                          
    if old_strip in content:
        content = content.replace(old_strip, new_strip)
        print("Patched Stripper outflow")
    else:
        print("Stripper text not found!")
        
    # 4. Scrubber empty guard
    # Let's just use regex to insert the guard before the scrubber mass update
    old_scrub = 's.scrub_holdup_kg += k_loop_fill * (condensed_kgh - ej["suction_kgh"]) * (dt / 3600.0)'
    new_scrub = '''if s.scrub_level_pct <= 0.0 and ej["suction_kgh"] > condensed_kgh:
        ej["suction_kgh"] = max(condensed_kgh, 0.0)
    s.scrub_holdup_kg += k_loop_fill * (condensed_kgh - ej["suction_kgh"]) * (dt / 3600.0)'''
    
    if old_scrub in content:
        content = content.replace(old_scrub, new_scrub)
        print("Patched Scrubber outflow")
    else:
        print("Scrubber text not found!")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    apply_patches(r"d:\Work\Urea Simulation\backend\main.py")
