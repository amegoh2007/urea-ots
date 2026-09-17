import os
import sys

# We'll mock the specific change in a copy of main.py
def run_test():
    with open('d:\\Work\\Urea Simulation\\backend\\main.py', 'r', encoding='utf-8') as f:
        code = f.read()
    
    old_code = """    q305_avail_kw = q_flash_avail_kw + Q_e002_kw                                           # total available latent kW
    m_305     = min(R323_PHI_V305 * m_feed_323,
                    max(R323_M305_DES * ((q305_avail_kw - q305_relax_kw) / R323_Q305_DES_KW),
                        0.0))                                                     # top vapor -> 323E003 LPCC (305, kg/h)"""
                        
    new_code = """    m_flash_gas = max(R323_M305_DES * (q_flash_avail_kw / R323_Q305_DES_KW), 0.0)
    m_pool_vap  = max(R323_M305_DES * ((Q_e002_kw - q305_relax_kw) / R323_Q305_DES_KW), 0.0)
    m_305       = min(R323_PHI_V305 * m_feed_323, m_flash_gas + m_pool_vap)       # top vapor -> 323E003 LPCC (305, kg/h)
    q305_avail_kw = q_flash_avail_kw + Q_e002_kw                                  # total available latent kW"""

    code = code.replace(old_code, new_code)
    with open('d:\\Work\\Urea Simulation\\backend\\main_test_fix.py', 'w', encoding='utf-8') as f:
        f.write(code)

if __name__ == "__main__":
    run_test()
