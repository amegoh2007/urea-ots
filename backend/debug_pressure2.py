import os
import sys

import main

def run_test():
    main.state = main.State()
    state = main.state
    
    # force TT-323001 to be 121.3 as in the user's trend
    # Actually, let's see how TT_323001 is calculated.
    for _ in range(100):
        main.step_sim(1.0)
    
    # Print variables before
    print(f"Initial: TT_323001: {state.tlag.get('TT_323001', 0):.1f}")
    
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = 60.0  # Open LV-322501
    
    for i in range(1, 10):
        packet = main.step_sim(1.0)
        v305_th = packet["RECIRC_323"]["C003"]["v305_th"]
        tt_323001 = state.tlag.get("TT_323001", 0)
        print(f"Step {i}: TT_323001: {tt_323001:.1f}, v305: {v305_th:.3f} t/h, PT-323201: {state.r323_c003_P:.3f} bar a, PIC-323202 PV: {state.r3232_d001_P:.3f} bar a")

if __name__ == "__main__":
    run_test()
