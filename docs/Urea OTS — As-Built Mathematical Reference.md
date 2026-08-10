# Urea OTS — As-Built Mathematical Reference

## 322E002 HP Carbamate Condenser and LP-Steam Export

### Reference point

The 1750 MTPD PFD identifies stream 932 as 16,707 kg/h exported LP steam. The model uses 5.01325 bara for the 4-barg LP header and calculates shell temperature from steam saturation pressure.

### Tube-side energy and phase model

The combined gas and liquid feed closes component mass balances in kmol/h. A live `(T, P)` flash supplies gas split `phi_i`; absorbed CO2 sets carbamate heat:

```text
n_CO2,absorbed = max(n_CO2,feed - n_CO2,gas, 0)
Q_carbamate = n_CO2,absorbed * ΔH_carbamate
Q_process = Q_carbamate + Q_sensible,feed
```

The adiabatic and heat-transfer outlet temperatures are:

```text
T_ad = T_mix + Q_carbamate / (m_process * Cp_process)
UA_load = UA_design * m_process / m_process,design
UA_effective = UA_design + gate * (UA_load - UA_design)
T_live = T_shell + (T_ad - T_shell)
         * exp[-UA_effective / (m_process * Cp_process)]
T_product = T_design + gate * (T_live - T_design)
```

`gate` is the existing normalized operator/feed-disturbance signal. It preserves the exact design pin at zero and applies constant design NTU at full load disturbance. This prevents the former high-load artifact: fixed `UA` reduced NTU, overheated product, increased CO2 flash, and reduced reaction heat.

Shell-side steam generation closes the energy split:

```text
Q_steam = max[Q_process
              - m_process * Cp_process * (T_product - T_product,design), 0]
m_steam = Q_steam / h_fg(P_LP)
```

The steam network advances the LP-header inventory and pressure, applies the PIC-329207 master split-range logic, and calculates FT-329407 from the PV-329207B turbine-export edge:

```text
FT-329407 = 3.6 * m_turbine                       [t/h]
m_turbine = K_207B * opening * sqrt(P_LP - P_turbine)
```

PV-329207B is calibrated to pass 16,707 kg/h at the PFD point. At reduced LP pressure and high load, the valve may reach 100% because its turbine pressure drop falls; the combined load-plus-low-pressure case must still export more than design.

## 322F001 HP Ejector and TT-322002

HV-322602 changes ejector spindle momentum and entrainment through the normalized equal-percentage factor:

```text
phi_spindle = R_spindle^[(opening_design - opening) / 100]
m_suction,capacity = m_suction,design
                     * phi_motive * phi_spindle * f_stall
```

Closing the spindle increases jet momentum and entrainment; opening it reduces both. The same spindle driver changes 322E003 condensation duty:

```text
chi_spindle = 1 + K_cond * (1 - 1 / phi_spindle)
Q_scrubber = Q_scrubber,base * max(chi_spindle, chi_min)
epsilon = 1 - exp[-UA_scrubber / C_CCW]
UA_effective = max(epsilon * C_CCW, epsilon_min)
TT-322002,target = clamp(T_CCW,in + Q_scrubber / UA_effective,
                         T_CCW,in, T_process)
```

TT-322002 is published through a 180-second first-order measurement/holdup lag. The 322-2 HMI reads this live `TI_322002` telemetry; it does not substitute the design value.

## 322E003 LP/MP Recycle-Carbamate Wash Cascade

The cold (70–90 °C), water-rich weak-carbamate wash recycled from the LP recirculation stage (323P001 A/B → 322E003, live flow `m_308` = 323E003 condensate draw) is the master driver of the scrubber cascade. Its live deviation from design is a single dimensionless lever:

```text
wash_scale = m_308(prior tick) / m_308,design        # ≡ 1.0 at design (bit-exact pins)
```

`m_308,design` (its OWN design draw, not the nominal wash spec `SCRUB_CARB_KGH_DES`) is the denominator so every deviation term below is identically zero at design. Increasing the wash produces the observed six-step response:

```text
# Obs 1  overflow level: surplus wash spills the weir into the sump inventory ODE
carb_dev   = carb - carb_design*s ;  overflow += carb_dev
dM_sump/dt = m_overflow_in - m_ejector_entrain          # level rises

# Obs 5a  reactive absorption (2 NH3 : 1 CO2), gas -> liquid, mass-conserving
d_CO2 = SCRUB_CARB_ABS_GAIN * sum(carb_dev)
d_NH3 = 2 * d_CO2 ;   offgas -= (d_CO2,d_NH3) ;  overflow += (d_CO2,d_NH3)

# Obs 3,4  cold wash steals sensible duty from the pool -> both temps fall
q_wash        = SCRUB_WASH_SINK_KW * (wash_scale - s)
Q_scrubber    = max(Q_scrubber - q_wash, 0)
TT-322002     = clamp(T_CCW,in + Q_scrubber/UA_eff, ...)      # overflow temp down
TT-329125     = T_CCW,in + (TT-322002 - T_CCW,in)*epsilon     # CW outlet down

# Obs 2  direct-contact vent cooling
TT-322011     = clamp(... - SCRUB_OFFGAS_WASH_COOLING*(wash_scale - s), ...)

# Obs 5b  water-rich solvent collapses the vapour space -> synthesis P falls
dP_collapse   = SYN_P_WASH_COLLAPSE_GAIN * max(wash_scale - s, 0)   # s = react co2_scale
d(PT-329201)/dt += (m_in - m_out)/C_loop - dP_collapse

# Obs 6  colder pool -> colder ejector suction -> colder NH3 line to HPCC
TT-322012     = (m_motive*cpN*T_motive + m_suc*cpC*T_overflow,prior) / (m_disch*cpD)
```

The ejector entrains the prior-tick overflow at its live temperature `T_overflow,prior` (a tear that breaks the algebraic loop); at design it equals `EJ_T_SUCTION_C` (178.8 °C) so TT-322012 is bit-exact. Direction is datasheet-anchored (`References/322E003 HP Scrubber Describtion.md`); the coupling gains are calibrated magnitudes (see `handoff.md`).

## Assumptions and Limits

- The model is reduced order: calibrated design conductance scales with process flow because no off-design exchanger datasheet is available.
- LP steam is saturated at live header pressure; detailed two-phase bundle hydraulics are outside scope.
- PV-329207B uses a lumped incompressible square-root pressure-drop law.
- Ejector and scrubber relationships preserve the design point and reproduce training-response direction, not nozzle-resolved CFD.

## Source Anchors

- `backend/main.py`: `hpcc_322e002`, `ejector_322f001`, 322E003 scrubber energy model, telemetry packet.
- `backend/steam_system.py`: LP-header balances, PIC-329207 master logic, PV-329207B export.
- `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`: design mass, pressure, and temperature points.
- `References/HPCC description.md`: carbamate exotherm and shell-side nucleate boiling.
- `References/Stamicarbon_Steam_Condensate_Network.md`: steam generation, control, and turbine-export topology.
