import os
import sys

import main

def run_test():
    main.state = main.State()
    state = main.state
    
    for _ in range(100):
        main.step_sim(1.0)
        
    state.PIC_329202["mode"] = "MAN"
    state.PIC_329202["op"] = 98.0  # higher steam valve opening
    
    for i in range(1, 61):
        packet = main.step_sim(1.0)
        v305_th = packet["RECIRC_323"]["C003"]["v305_th"]
        if i % 10 == 0:
            print(f"Step {i}: v305: {v305_th:.3f} t/h")

if __name__ == "__main__":
    run_test()
