import os
import sys
import main

def run_test():
    main.state = main.State()
    state = main.state
    
    for _ in range(100):
        main.step_sim(1.0)
        
    print(f"Initial: PT-323201: {state.r323_c003_P:.3f} bar a, PIC-323202 PV: {state.r3232_d001_P:.3f} bar a, LIC-322501: {state.strip_level:.1f}%, LV-322501: {state.LIC_322501['op']:.1f}%")
    
    state.HIC_322605 = 80.0  # Open HV-322605 from design 60% to 80%
    
    for i in range(1, 121):
        packet = main.step_sim(1.0)
        if i % 20 == 0:
            T_bot = state.tlag.get("TT_322004", 166.0)
            print(f"Step {i}: PT-323201: {state.r323_c003_P:.3f}, PIC-323202: {state.r3232_d001_P:.3f}, m_feed: {getattr(state, '_debug_m_feed_323', 0):.1f}, m_flash: {getattr(state, '_debug_m_flash', 0):.1f}, m_305: {getattr(state, '_debug_m_305', 0):.1f}")

if __name__ == "__main__":
    run_test()
