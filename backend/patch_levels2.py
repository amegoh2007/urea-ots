import re

def apply_patches(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 4. Scrubber empty guard
    old_scrub = 's.scrub_holdup_kg = clamp(s.scrub_holdup_kg + (m_cond_in - ej["suction_kgh"]) * (dt / 3600.0),\n                              0.0, SCRUB_HOLDUP_NLL_KG * 1.5)'
    new_scrub = '''if s.scrub_level_pct <= 0.0 and ej["suction_kgh"] > m_cond_in:
        ej["suction_kgh"] = max(m_cond_in, 0.0)
    s.scrub_holdup_kg = clamp(s.scrub_holdup_kg + (m_cond_in - ej["suction_kgh"]) * (dt / 3600.0),
                              0.0, SCRUB_HOLDUP_NLL_KG * 1.5)'''
    if old_scrub in content:
        content = content.replace(old_scrub, new_scrub)
        print("Patched Scrubber")
    else:
        print("Scrubber not found!")

    # 5. Flash Drum (323C003) empty guard
    # m_314 is the outflow, m_feed_323 is inflow, m_305 is gas outflow
    old_c003 = 's.r323_c003_M = max(M_c003_pre + (m_feed_323 - m_305 - m_314) / 3600.0 * dt, 1.0)'
    new_c003 = '''if M_c003_pre <= 1.0 and m_314 > (m_feed_323 - m_305):
        m_314 = max(m_feed_323 - m_305, 0.0)
    s.r323_c003_M = max(M_c003_pre + (m_feed_323 - m_305 - m_314) / 3600.0 * dt, 1.0)'''
    if old_c003 in content:
        content = content.replace(old_c003, new_c003)
        print("Patched C003")
    else:
        print("C003 not found!")

    # 6. LPCC (323D001) empty guard
    # s.r3232_d001_M = max(s.r3232_d001_M + (in_e003 - m_321 - m_308)/3600.0*dt, 1.0)
    # m_308 is outflow. in_e003 is inflow. m_321 is gas.
    old_d001 = 's.r3232_d001_M = max(s.r3232_d001_M + (in_e003 - m_321 - m_308)/3600.0*dt, 1.0)'
    new_d001 = '''if s.r3232_d001_M <= 1.0 and m_308 > (in_e003 - m_321):
        m_308 = max(in_e003 - m_321, 0.0)
    s.r3232_d001_M = max(s.r3232_d001_M + (in_e003 - m_321 - m_308)/3600.0*dt, 1.0)'''
    if old_d001 in content:
        content = content.replace(old_d001, new_d001)
        print("Patched D001")
    else:
        print("D001 not found!")

    # 7. Comp Tank II (323D002_M_II)
    # s.r323_d002_M_II = max(M_II_new, 0.0)
    # This one is tricky, M_II_new = M_II_pre + (feed - m_out). Let's see how m_out is defined.
    # It's better to just leave D002 alone unless it's explicitly failing, because the calculation is complex.
    # I will stick to these 3 for now, which covers all the major loop vessels.

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    apply_patches(r"d:\Work\Urea Simulation\backend\main.py")
