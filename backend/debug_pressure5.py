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
    
    # Overwrite the lag for TT_323001 to keep it at 121.3 as in the user's trend
    original_lag = main._lag1
    def mock_lag(d, k, v, t, dt):
        if k == "TT_323001_raw":
            d["TT_323001"] = 121.3
            return 121.3
        return original_lag(d, k, v, t, dt)
    main._lag1 = mock_lag
    
    for i in range(1, 10):
        packet = main.step_sim(1.0)
        m_feed_323 = packet["RECIRC_323"]["C003"].get("m_feed_323", 0)  # We might need to print it from state or packet
        # Wait, step_sim_source doesn't export m_feed_323 in packet.
        # Let's just print variables from main if possible.
        pass

if __name__ == "__main__":
    run_test()
