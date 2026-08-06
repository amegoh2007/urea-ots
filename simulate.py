from pressure_drop import reactor_r01, stripper_e01, condenser_e02, scrubber_e03

def run_simulation(r01_flow, r01_den, e01_flow, e01_den, e02_flow, e02_den, e03_flow, e03_den):
    print("================================================================")
    print("      Urea Synthesis Loop Rigorous Pressure Drop Simulation     ")
    print("================================================================\n")
    
    # 1. Reactor R01
    m_dot_r01 = r01_flow / 3600.0  # convert kg/h to kg/s
    dp_r01 = reactor_r01.calc_pressure_drop(m_dot_r01, density_kg_m3=r01_den, viscosity_pa_s=0.001)
    print(f"[{reactor_r01.name}]")
    print(f"  Dimensions : D={reactor_r01.diameter}m, H={reactor_r01.height}m, Trays={reactor_r01.num_trays}")
    print(f"  Feed       : {r01_flow} kg/h, Density = {r01_den} kg/m3")
    print(f"  Delta P    : {dp_r01:.4f} bar\n")

    # 2. Stripper E01
    m_dot_e01 = e01_flow / 3600.0
    dp_e01 = stripper_e01.calc_tube_side_dp(m_dot_e01, density_kg_m3=e01_den, viscosity_pa_s=2e-5)
    print(f"[{stripper_e01.name}]")
    print(f"  Dimensions : {stripper_e01.num_tubes} tubes, L={stripper_e01.tube_length}m, ID={stripper_e01.tube_id*1000}mm")
    print(f"  Feed       : {e01_flow} kg/h, Density = {e01_den} kg/m3")
    print(f"  Delta P    : {dp_e01:.4f} bar\n")

    # 3. Condenser E02
    m_dot_e02 = e02_flow / 3600.0
    dp_e02 = condenser_e02.calc_tube_side_dp(m_dot_e02, density_kg_m3=e02_den, viscosity_pa_s=1e-3)
    print(f"[{condenser_e02.name}]")
    print(f"  Dimensions : {condenser_e02.num_tubes} tubes, L={condenser_e02.tube_length}m, ID={condenser_e02.tube_id*1000}mm")
    print(f"  Feed       : {e02_flow} kg/h, Density = {e02_den} kg/m3")
    print(f"  Delta P    : {dp_e02:.4f} bar\n")

    # 4. Scrubber E03
    m_dot_e03 = e03_flow / 3600.0
    dp_e03 = scrubber_e03.calc_tube_side_dp(m_dot_e03, density_kg_m3=e03_den, viscosity_pa_s=2e-5)
    print(f"[{scrubber_e03.name}]")
    print(f"  Dimensions : {scrubber_e03.num_tubes} tubes, L={scrubber_e03.tube_length}m, ID={scrubber_e03.tube_id*1000}mm")
    print(f"  Feed       : {e03_flow} kg/h, Density = {e03_den} kg/m3")
    print(f"  Delta P    : {dp_e03:.4f} bar\n")

if __name__ == "__main__":
    # Standard Flow Condition Example (from Aspen Manual/Datasheets)
    print("--- BASE CASE SCENARIO ---")
    run_simulation(
        r01_flow=42000,   r01_den=900,
        e01_flow=83239,   e01_den=10.28,
        e02_flow=2774000, e02_den=919.55,
        e03_flow=1606,    e03_den=100.0
    )
    
    # Increased Capacity Example (e.g. +20% gas flow)
    print("--- 20% CAPACITY INCREASE SCENARIO ---")
    run_simulation(
        r01_flow=42000*1.2,   r01_den=900,
        e01_flow=83239*1.2,   e01_den=10.28,
        e02_flow=2774000*1.2, e02_den=919.55,
        e03_flow=1606*1.2,    e03_den=100.0
    )
