# Pressure Tuning Design (PT-323201 and PIC-323202)

## Goal
The user requested that the lag times between `LV-322501` opening, `PT-323201` increasing, and `PIC-323202` increasing be reduced to 1-2 seconds in the simulation. This ensures they appear visually linked on the trend UI while maintaining enough smoothing to prevent numerical spikes.

## Background
- `PT-323201` (Flash Drum Pressure) is governed by a first-order lag with time constant `R323_C003_P_TAU_S`. I recently changed this from 90.0s to 5.0s, but it's still slightly too slow for the user's visual preference.
- `PIC-323202` (LPCC Condenser Pressure) is governed by an integrator with gain `R3232_D001_P_KP = 0.03`. It builds up slowly over time based on the mass balance error.

## Implementation Plan
1. **Flash Drum (`PT-323201`)**: Decrease `R323_C003_P_TAU_S` in `main.py` from `5.0` to `1.0`. A 1.0 second time constant means the pressure will reach ~63% of its target in 1 second, providing the fast 1-2 second visual response requested.
2. **LPCC (`PIC-323202`)**: Increase `R3232_D001_P_KP` in `main.py` from `0.03` to `0.30` (a 10x increase). This allows the downstream pressure to accumulate much more rapidly when gas surges into the condenser, tightly coupling it visually to the flash drum surge.

## Verification
- We will monitor `debug_hv605.py` to ensure that when `m_feed` increases, both `PT-323201` and `PIC-323202` ramp up substantially within 1-2 simulation steps.
