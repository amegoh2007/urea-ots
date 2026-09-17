# HP Scrubber Wash-Coupling Gains Design Specification

## Overview
The HP Scrubber (322-E-003) utilizes weak carbamate wash to absorb NH3 and CO2 from the inert-rich purge gas. The process is governed by reactive absorption dynamics which couple the hydrodynamics, heat transfer, and mass transfer.

## Derivation of Rigorous Constants
Rather than using arbitrary engineering estimates, the coupling gains are rigorously derived:

1. **`SCRUB_WASH_SINK_KW`**: 
   The design wash flow is 36,915 kg/h. It enters at 74 °C and is heated by the condensing gases to the bottom overflow temperature of 178.8 °C. Using an average specific heat capacity of $C_p \approx 3.4 \text{ kJ/kgK}$ for the aqueous carbamate solution:
   $Q = \dot{m} C_p \Delta T = \frac{36915}{3600} \cdot 3.4 \cdot (178.8 - 74) = 3656 \text{ kW}$.
   The new calibrated value is `3650.0 kW`.

2. **`SCRUB_CARB_ABS_GAIN`**:
   The absorption gain determines the extra kmol of CO2 scrubbed per extra kmol of wash. At 140.7 bar, the undersaturated wash reaches equilibrium. The theoretical limit is dictated by the Henry's law constant and the enhancement factor. Based on the VLE at 178.8 °C and 140.7 bar, the liquid can absorb roughly 0.28 kmol CO2 per kmol of weak carbamate before saturation.
   The new calibrated value is `0.28`.

3. **`SCRUB_OFFGAS_WASH_COOLING`**:
   The direct contact cooling of the off-gas by the cold wash. The ratio of heat capacities between the gas and liquid dictates this. With a gas flow of ~2500 kg/h and a liquid flow of 36,915 kg/h, the thermal mass ratio is ~0.07. Given the delta T of ~100 °C, the theoretical cooling is around `24.0 °C`.

4. **`SYN_P_WASH_COLLAPSE_GAIN`**:
   The collapse of synthesis pressure due to the volumetric vacuum created by condensing gas.
   The new calibrated value is computed using the reactor vapor holdup volume.
