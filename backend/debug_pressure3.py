import os
import sys

import main

def run_test():
    main.state = main.State()
    state = main.state
    
    for _ in range(100):
        main.step_sim(1.0)
        
    state.tlag["TT_323001"] = 121.3
    state.tlag["TT_323001_raw"] = 121.3
    
    # Overwrite the lag function for TT_323001 to keep it at 121.3
    original_lag = main._lag1
    def mock_lag(d, k, v, t, dt):
        if k == "TT_323001_raw":
            d["TT_323001"] = 121.3
            return 121.3
        return original_lag(d, k, v, t, dt)
    main._lag1 = mock_lag
    
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = 60.0  # Open LV-322501
    
    for i in range(1, 20):
        packet = main.step_sim(1.0)
        v305_th = packet["RECIRC_323"]["C003"]["v305_th"]
        print(f"Step {i}: TT_323001: {state.tlag.get('TT_323001')}, v305: {v305_th:.3f} t/h, PT-323201: {state.r323_c003_P:.3f} bar a, PIC-323202 PV: {state.r3232_d001_P:.3f} bar a")

if __name__ == "__main__":
    run_test()
