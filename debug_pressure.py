import os
import sys

# add current dir to sys path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backend.main as main

def run_test():
    main.state = main.State()
    state = main.state
    
    # stabilize
    for _ in range(100):
        main.step_sim(1.0)
        
    print(f"Initial: PT-323201: {state.r323_c003_P:.3f} bar a, PIC-323202 PV: {state.r3232_d001_P:.3f} bar a, PV-323202 OP: {state.PIC_323202['op']:.1f}%")
    
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = 60.0  # Open LV-322501
    
    for i in range(1, 61):
        main.step_sim(1.0)
        if i % 10 == 0:
            print(f"Step {i}: PT-323201: {state.r323_c003_P:.3f} bar a, PIC-323202 PV: {state.r3232_d001_P:.3f} bar a, PV-323202 OP: {state.PIC_323202['op']:.1f}%")

if __name__ == "__main__":
    run_test()
