import sys
import os

# Add backend to path so we can import props
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

import props_nh3co2h2o as props

# Wash mass fractions
mass_pct = {"CO2": 38.49, "H2O": 30.83, "NH3": 30.61, "Urea": 0.07}

# Normalize without Urea for the ternary model
tot = mass_pct["CO2"] + mass_pct["H2O"] + mass_pct["NH3"]
w_co2 = mass_pct["CO2"] / tot
w_h2o = mass_pct["H2O"] / tot
w_nh3 = mass_pct["NH3"] / tot

T_in = 74.0
T_out = 178.8
P = 140.7

# Get liquid enthalpies
# props.liquid_enthalpy_kjkg(T_C, P_bar, w_nh3, w_co2, w_h2o)
try:
    h_in = props.liquid_enthalpy_kjkg(T_in, P, w_nh3, w_co2, w_h2o)
    h_out = props.liquid_enthalpy_kjkg(T_out, P, w_nh3, w_co2, w_h2o)

    dh = h_out - h_in # kJ/kg
    
    # 36915 kg/h design flow
    m_flow = 36915.0 # kg/h
    
    Q_kW = (m_flow * dh) / 3600.0
    
    print(f"Enthalpy at {T_in} C: {h_in:.2f} kJ/kg")
    print(f"Enthalpy at {T_out} C: {h_out:.2f} kJ/kg")
    print(f"Delta H: {dh:.2f} kJ/kg")
    print(f"Total Sensible Sink for 36915 kg/h: {Q_kW:.2f} kW")
    print(f"-> SCRUB_WASH_SINK_KW = {Q_kW:.2f}")

except Exception as e:
    print(f"Error: {e}")
