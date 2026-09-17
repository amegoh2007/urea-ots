import os
import sys

import main

def run_test():
    main.state = main.State()
    state = main.state
    
    for _ in range(100):
        main.step_sim(1.0)
        
    packet = main.step_sim(1.0)
    v305_initial = packet["RECIRC_323"]["C003"]["v305_th"]
    print(f"Initial v305: {v305_initial:.3f} t/h")
    
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = 60.0  # Open LV-322501
    
    for i in range(1, 10):
        packet = main.step_sim(1.0)
        v305_th = packet["RECIRC_323"]["C003"]["v305_th"]
        print(f"Step {i}: v305: {v305_th:.3f} t/h, PT-323201: {state.r323_c003_P:.3f}, PIC-323202: {state.r3232_d001_P:.3f}")

if __name__ == "__main__":
    run_test()
