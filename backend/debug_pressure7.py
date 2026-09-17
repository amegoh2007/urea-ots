import os
import sys

import main

def run_test():
    main.state = main.State()
    state = main.state
    
    for _ in range(100):
        main.step_sim(1.0)
        
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = 60.0  # Open LV-322501
    
    for i in range(1, 4):
        packet = main.step_sim(1.0)
        m_feed = packet["RECIRC_323"]["C003"]["in305_th"] * 1000.0  # approximate
        # Wait, the exact args:
        # arg1 = main.R323_PHI_V305 * m_feed_323
        # In step_sim, m_feed_323 = drain_kgh
        pass

if __name__ == "__main__":
    run_test()
