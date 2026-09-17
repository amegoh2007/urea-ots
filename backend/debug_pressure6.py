import os
import sys

import main

def run_test():
    main.state = main.State()
    state = main.state
    
    for _ in range(100):
        main.step_sim(1.0)
        
    packet = main.step_sim(1.0)
    
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = 60.0  # Open LV-322501
    
    for i in range(1, 4):
        packet = main.step_sim(1.0)
        
        # We need to compute arg1 and arg2 ourselves
        # m_feed_323 is m_322e001_bot (drain_kgh) + m_321e001_bot + m_323f004_liq
        # In main.py:
        # T_bot = main._lag1(state.tlag, "T_bot_322", ...)
        # drain_kgh is in packet?
        # Actually, let's just copy the logic for arg1 and arg2 roughly to see what's dominating.
        pass
        
    print("Test run complete.")

if __name__ == "__main__":
    run_test()
