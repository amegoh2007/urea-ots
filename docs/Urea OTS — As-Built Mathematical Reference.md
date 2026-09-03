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

The scrubber uses finite, component-wise absorption capacity derived from its design split:

```text
A_i,design = max(gas_feed_i,design - offgas_i,design, 0)  # NH3, CO2, H2O
capacity_ratio = max(wash_scale
                     + k_CW*(T_CCW,design - T_CCW)/A_CO2,design, 0)
A_i        = min(gas_feed_i, A_i,design * capacity_ratio)
offgas_i   = gas_feed_i - A_i
overflow_i = wash_i + A_i
closure_i  = gas_feed_i + wash_i - offgas_i - overflow_i = 0
dM_sump/dt = m_overflow - m_ejector,entrained
```

Cold wash also changes the energy balance:

```text
q_wash     = SCRUB_WASH_SINK_KW * (wash_scale - s)
Q_scrubber = max(Q_scrubber - q_wash, 0)
TT-322002  = clamp(T_CCW,in + Q_scrubber/UA_eff, ...)
TT-329125  = T_CCW,in + (TT-322002 - T_CCW,in)*epsilon
TT-322011  = clamp(... - K_wash,T*(wash_scale - s), ...)
TT-322012  = (m_motive*cpN*T_motive + m_suc*cpC*T_overflow,prior) / (m_disch*cpD)
```

HV-322604 has finite hydraulic capacity instead of multiplying whatever gas reaches it:

```text
m_capacity = m_vent,design * R^[(opening-opening_design)/100]
             * sqrt(ΔP/ΔP_design)
m_vented   = min(m_available, m_capacity)
m_retained = m_available - m_vented
LP_absorber_load = m_available / m_vent,design
m_relief/emission = max(m_available - 1.15*m_vent,design, 0)
```

Low wash raises NH3/CO2 breakthrough. Gas above valve capacity remains in the HP inventory and raises PT-329201; downstream absorber load and ammonia-emission diagnostics rise at the same time. High wash increases liquid traffic, reduces breakthrough, and cools ejector suction and HPCC feed. The ejector consumes prior-tick overflow temperature to break the algebraic loop.

## 323P001 LP Recycle Pump Speed Control (SIC-323901)

The LP weak-carbamate recycle pump 323P001 A/B is a variable-speed URACA KD 825-Carb triplex reciprocating pump. SIC-323901 is cascaded under the 323D001 drum-level master LIC-323502. The drive tracks demanded speed through a short first-order lag; the pump then follows its equipment-sheet displacement law:

```text
speed_demand = LIC-323502.op         (CAS  : drum-level cascade)
             = SIC-323901.sp         (AUTO : operator speed setpoint)
             = SIC-323901.op         (MAN  : operator manual output)
speed_actual = lag_1(speed_demand, tau = 3 s)
Q_323P001    = 0                                      if stopped
             = 0.5046 * clamp(speed_actual, 19, 81)   if running       [m3/h]
m_308        = rho_carbamate * Q_323P001 * f_NPSH
```

Discharge pressure is absent from the flow law. Head changes load the drive and relief protection; they do not create a centrifugal-pump head-flow curve. Suction availability remains active through the common NPSH/cavitation factor. At design, the displacement equation reproduces `m_308,design` exactly.

An earlier build controlled SIC-323901 with an inline I-PD whose PV was a lag of its **own** output — a degenerate self-referential loop with near-unity process gain, so a setpoint change in AUTO barely moved the speed and the operator could not command the pump. The follower model removes that; setpoint tracking is now prompt (≈ the 3 s VFD lag) with zero offset. Post-disturbance CAS recovery is governed by the master LIC-323502 (Ti = 300 s) and the coupled loop inventories, and returns to the design attractor.

## Deviation-Consequence Physics (`backend/consequence.py`)

Every level-, temperature- and pressure-driven consequence in the flowsheet is produced by **one law
per phenomenon**, applied at every vessel, valve and pump. Before this layer each written-up scenario
was wired into the single tag it had been written up against, with its own hand-picked constant, so
two identical events at two different vessels produced two different (or zero) consequences.

Each law is in *anchored departure form*: at the published design state it returns exactly zero extra
effect, so the boot pin and every steady-state audit stay bit-exact.

### Loss of liquid seal — gas blow-through

A control valve's flow coefficient is a property of the valve, so gas flow through a valve sized for
liquid is fixed by its own liquid design duty plus IEC 60534-2-1 / ISA-75.01 compressible flow:

```text
x       = dP/P1 ;  F_k = gamma/1.40 ;  x_choked = F_k * x_T
Y       = clamp(1 - x_eff/(3*x_choked), 2/3, 1)          # expansion factor
m_gas   = m_liq_des * theta * Y * sqrt( rho_gas*dP_eff / (rho_liq*dP_des) ) * (1 - seal_frac)
seal_frac = clamp((level - level_nozzle) / nozzle_bore, 0, 1)
```

The nozzle uncovers **progressively** across its bore, so both the gas escape and the liquid cut-off
are continuous — no step in the right-hand side of a level ODE, and the transition reverses when
level is restored. Beyond `x_choked` the escape is choked and cannot grow as the downstream section
depressurises. Applied at LV-322501, LV-323501, LV-323505, LV-328504, LV-328505, LV-322502 and the
322R001 bottom exit funnel.

### Liquid carry-over — Souders-Brown disengagement

```text
R_u = (m_vap/m_vap_des) * sqrt(P_des/P) * sqrt(T/T_des) * sqrt(rho_L_des/rho_L)
R_h = (1 - L_des)/(1 - L)                       # vertical vessel: h_disengagement ~ 1 - level
E   = min(E_des * R_u^3.2 * R_h, E_cap)
m_carry = m_vap * max(E - E_des, 0)             # == 0 at design, exactly
```

Rises with level, with vapour load, and with a **deepening vacuum** (a lighter vapour reaches the
settling velocity at a lower mass flow). Applied at 322R001, 322E003, 323C003, 323F004, 323F010,
324F001, 324F003, 328C002, 328C004, 328D001, 323D001 and 323D011.

### Pump NPSH — one equation for "level fell" and "temperature rose"

```text
NPSHa/H = (P_vessel - Psat(T,composition)) / (rho*g*H) + level_fraction
f_pump  = clamp((NPSHa/H - NPSHr_frac) / margin_frac, 0, 1)
```

A falling level removes static head; a rising liquid temperature raises the vapour pressure; a
collapsing vessel pressure removes the subcooling term. All three cavitate the same pump through the
same equation, and the flow ramps across the knee instead of switching off at a threshold. Applied at
323P001, 323P003, 323P008, 328P002/P003, 322P002/328P006, 324P001 and 324P003.

### Crystallisation — a solubility curve, not a constant

The urea-water solubility table (CRC/Perry, converted to mass fraction and anchored at the 132.7 °C
pure-urea melting point) plus a carbamate boundary anchored on the 322E003 overflow strength give
each stream its own boundary, taking whichever solid appears first:

| stream | urea | crystallisation boundary |
|---|---|---|
| 322E001 bottoms | 55.9 % | ≈ 30 °C |
| 323C003 liquor | 68.7 % | ≈ 57 °C |
| 323F010 / 323D002 | 80.0 % | ≈ 80 °C |
| 324E003 melt | 98.6 % | ≈ 132 °C |

Flow restriction begins one metastable-zone width below the boundary. The engine previously judged
every urea stream against 132.7 °C, which is right only for the final melt.

### Vacuum break — a load, not an assignment

A broken seal is delivered to the affected vacuum node as a **mass rate** that competes with the
ejector pull inside the node's existing pressure ODE, after a transport dead time. The pressure then
ramps at a rate set by the imbalance and recovers when the operator restores the seal. Where the
downstream side is atmosphere (the 324F003 barometric leg) the correct model is a choked orifice
drawing air inward — critical ratio 0.528 for air, so the ingress depends only on the open area.

## HP Urea-Synthesis Equilibrium (`backend/thermo_urea_hp.py`)

The HP reactor and the LP/MP recovery section use different thermodynamic services. Extended UNIQUAC/SRK remains on the lower-pressure aqueous-carbamate flashes inside its validated range. The 141-bar, 165–183 °C synthesis loop uses the Voskov-Voronin high-pressure urea-equilibrium correlation, whose published domain is 135–230 °C, N/C 2–5.5, and H/C −0.75–1.2:

```text
X_corr = (-121.1458 - 5.1135e-5*T_K^2 + 21.6826*ln(T_K))
         * exp[-2.1908*L^-2*W - 4.1059e-3*L^2*W - 2.8380*L^-2]
X_plant = 0.543 * X_corr(L,W,T) / X_corr(L_design,W_design,T_design)
```

Inputs are clamped at the published domain boundary and raise `HP_UREA_THERMO_EXTRAPOLATED`. The plant normalization preserves the verified 0.543 design conversion; it does not alter the off-design slopes.

The synthesis ratios count reacted products as original feed equivalents:

```text
C = n_CO2 + n_urea + 2*n_biuret
N = n_NH3 + 2*n_urea + 3*n_biuret
L = N/C
W = (n_H2O - n_urea - 2*n_biuret)/C
```

Increasing recycle water raises `W` and lowers `X_plant`. The atom-conserving reactor shift leaves more NH3/CO2 for the stripper and HPCC. Telemetry reports the lost-conversion recycle mass and the carbamate-dissociation steam equivalent. A recycle shortage reports `sustainable_production_factor = min(wash_scale/synthesis_load, 1)`, flags `FRONT_END_CUTBACK_REQUIRED` below 0.95, and lets the live HPCC composition and reactor inventory disturb N/C and level.

## Bubble Points of the NH3-CO2-H2O Liquors (`backend/vle_nh3co2h2o.py`)

323C003 and 323F004 hold liquors whose vapour is roughly a third ammonia and half CO2, so their
bubble points are governed by NH3 and CO2 partial pressures, not water's. Both stages previously used
a pure-water saturation line with a frozen offset, i.e. they responded to pressure and to nothing
else. They now use the Extended UNIQUAC electrolyte model already present in
`backend/props_nh3co2h2o.py` (Thomsen-Rasmussen / Darde), which had never been wired into the engine:

```text
P_bub(T) = f_dil * [ a_NH3*H_NH3(T) + a_CO2*H_CO2(T) + a_H2O*Psat_H2O(T) ]
```

with activities from the full gamma (combinatorial + residual + extended Debye-Hückel) over the R1–R5
speciation, Rumpf-Maurer Henry constants, IAPWS-IF97 water saturation, and urea/biuret as
non-volatile diluents. Validated against this plant's own PFD with **no fitted parameter**, on the
engine's own composition vectors and through the interpolated path the engine actually calls:

| stage | T (°C) | P model | P PFD | error |
|---|---|---|---|---|
| 323C003 | 135 | 4.387 | 4.10 | +7.0 % |
| 323F004 | 106 | 1.328 | 1.13 | +17.5 % |
| 323F010 | 99 | 0.468 | 0.46 | +1.7 % |

323F004 is the loosest of the three because it is the stage where the CO2 term dominates and CO2 is
where this model is weakest — at 0.66 wt% CO2 the carbamate equilibrium is steep, and urea (72 % of
that liquor) enters as a mole-fraction diluent rather than a UNIQUAC species. Tracked as G-VLE-1.
The offset is absorbed by the departure form; what reaches the engine is the slope. For scale, the
pure-water anchor this replaces returns 103.3 °C at 323F004's 1.13 bar against an actual 106 °C —
and responds to composition with a derivative of exactly zero.

Activities are tabulated over the operating envelope and interpolated (log-space in the two loadings,
which span four decades); Henry constants and the water saturation line stay analytic at the live
temperature, so the temperature response the controllers act on carries no grid error. Both call
sites use the departure form `T_des + [T_bub(live) − T_bub(design)]`, so the residual model offset
cancels identically at design and only the slope reaches the engine.

## Consequence Transport Lag

A consequence arrives when its fluid parcel arrives. `consequence.StreamPacket` carries one closed
set of total mass rate, per-component mass rates, temperature, heat capacity, and sensible-enthalpy
rate. Total flow and mass fractions are derived from the component vector, so flow, temperature, and
composition cannot be delayed on different clocks.

Packets mix by component and sensible-enthalpy balances:

```text
m_mix,i = sum_j(m_j,i)
m_mix   = sum_i(m_mix,i)
Cp_mix  = sum_j(m_j Cp_j) / m_mix
T_mix   = sum_j(m_j Cp_j T_j) / (m_mix Cp_mix)
w_mix,i = m_mix,i / m_mix
```

`ConsequenceRoute` treats a connection as plug flow. Its effective line inventory is struck from the
established design travel-time anchor, then its live delay varies with the live carrier:

```text
M_line = m_design * theta_design / 3600
theta_live = clamp(3600 M_line / m_live, 0, 1800 s)
```

Gas fronts use the 8 s design anchor and liquid slugs use 20 s. A timestamped FIFO delays the whole
packet; the downstream vessel's existing mass, energy, species, and gas-inventory ODEs supply the
additional mixed-holdup response. No second output filter is added, so residence time is not counted
twice. For example, the relatively small 322C001 seal-loss gas rate gives about 83 s live transit
through a line sized for 33 t/h of liquid, while higher gas loads arrive sooner.

The physical route registry covers:

| source | destination | downstream balances consuming the arrived packet |
|---|---|---|
| 322E001 | 323C003 / LP overhead | overhead mass, temperature, components, LPCC duty |
| 323C003 | 323F004 | flash pressure and LPCC overhead mass/energy/species |
| 323F004 | 323F010 | pre-evaporator vacuum gas inventory |
| 323F010 | 324E002 | Stage-1 condenser/ejector non-condensable load |
| 328C003 | 328C004 | desorber-II sensible load, gas inventory, and recycle species |
| 328C004 | stream 740 | process-condensate flow, temperature, composition, and AI-328701 |
| 322C001 | 323E003/323D001 | LPCC mass, energy, condensation, and pressure load |

`CONSEQUENCE_TRANSPORT` publishes the exact arrived packets consumed by physics, including live dead
time and component closure. Route names describe topology only. The generating scenario's name is
never an input, so an unlisted seal loss uses the same downstream equations as a listed one.

## Normal Process Stream Transport and Ripple

Normal liquid traffic through the finishing train uses the same conserved packet definition and
plug-flow law as consequence transport, but a separate boot-seeded FIFO. Its first packet fills the
route history, so design operation starts at the receiver's design inlet rather than with a false
empty-line transient. Every subsequent parcel keeps flow, temperature, heat capacity, sensible
enthalpy, and all component rates on one timestamp:

```text
packet = {m_i, T, Cp};  m = sum_i(m_i);  H_sens = m Cp T
M_line = m_design theta_design / 3600
theta_live = clamp(3600 M_line / m_live, 0, 1800 s)
d(M_receiver w_i)/dt = m_in w_i,in - m_out w_i,out + generation_i
d(M_receiver Cp T)/dt = sum(m_in Cp_in T_in) - sum(m_out Cp T) + Q
tau_receiver approximately M_receiver / m_throughput
```

The route registry follows the PFD/PID sequence:

| source | destination | design-flow anchor | design dead time |
|---|---|---:|---:|
| 322E001 | 323C003 | stripper bottoms | 20 s |
| 323C003 | 323F004 | stream 314 | 20 s |
| 323F004 | 323F010 | stream 319 | 20 s |
| 323F010 | 323D002 | stream 317 | 20 s |
| 323D002 | 324E001 | stream 324 | 20 s |

The two supplied trend exports contain 30-second rows, but their own notices identify those rows as
synthetic linear interpolation between hourly measurements. Only 17 normal-operation and 7 startup
anchors are independent. Feed and multiple Unit 322 gradients occur in the same hourly bin, so the
data support only `theta < 3600 s`; they cannot identify a 20-second or any other subhour delay.
Accordingly, 20 seconds is retained as the existing reduced-order liquid-slug engineering anchor,
not presented as a fitted historian result. Field line inventories or raw higher-resolution
historian data are required to calibrate it.

`PROCESS_TRANSPORT` publishes departure and arrived mass, temperature, components, and live dead
time for all five boundaries. The receiving vessels' existing mass, component, and energy ODEs own
the downstream gradient and process time constant. Adding another output lag would delay the same
physical inventory twice.

## PT-329201 Synthesis-Loop Pressure

The loop pressure is a lumped mass balance over the HP envelope: reactor 322R001, stripper
322E001, HP carbamate condenser 322E002, HP scrubber 322E003 and ejector 322F001. Five streams
cross that boundary.

```text
m_in   = m_NH3,motive(321P002 A/B) + m_CO2,feed(322K001) + m_308(323P001 LP carbamate)
m_out  = m_drain(LV-322501 bottoms) + m_vent(HV-322604 inert purge)
R_des  = (NH3_des + CO2_des + m308_des) - (bot_des + vent_des)        = -2168.1 kg/h
f_loop = clamp((L_react + L_hpcc + L_strip)/(NLL_react + NLL_hpcc + SP_strip), 0, 1)
dP/dt  = [ (m_in - m_out) - f_loop * R_des ] / C_loop,   C_loop = 1500 kg/bar
```

`R_des` is a constant fixed entirely by design pins. It exists because two boundary terms were
deliberately moved off their PFD rows by the model's own Path-B reconciliations: the ejector motive
NH3 was re-pinned 40 756 -> 42 762.05 kg/h to restore fresh N/C = 2.0, and the 322E003 vent vector
was re-solved to close the *scrubber's component* balance, taking its total mass from the PFD's
1 708 kg/h to 5 901.4 kg/h. On the PFD rows the envelope closes to 1 kg/h in 132 289; on the
reconciled pins it does not, and the raw balance integrated that offset as though it were real
accumulation.

Crediting `R_des` through the live loop-mass fraction is the same inventory gate the stripper
forward-push `pb_push` already uses, for the same reason: the reconciliation tears ride the
*circulating* inventory. At design `f_loop == 1` so `dP/dt` is exactly zero and PT-329201 holds
140.700 bar a; on an empty loop `f_loop -> 0` so the raw balance integrates and zero feeds still
create nothing (G4 null-feed rule). `f_loop` is clamped at 1, so surplus inventory cannot
over-credit either.

### Why it drifted (2026-09-02)

From a fresh design seed, with nothing touched, PT-329201 bled about 0.30 bar per 600 s. Because
the LV-322501 letdown is driven by that head (`m_drain ~ sqrt(P_syn - P_down)`), the bleed pulled
the entire 323/324 train off its anchors. Five design-point residuals were found, all of the same
kind -- an anchor computed on a different basis than the live path it normalises:

| # | residual at the design seed | measured |
|---|---|---|
| 1 | HP-loop boundary summed **absolute** flows over an envelope whose anchors do not reconcile | open by -2 168.1 kg/h |
| 2 | LP-steam chest pins computed against a stale 4.4 bar a header while the live header is 5.01325 bar a (4.0 barg) | 323E002 chest 4.494 instead of 3.96 bar a -> 9 127 kW design duty against the 5 858 kW datasheet |
| 3 | `phi_out = phi_fwd` in the 322E002 sump -- the documented gravity-head term `phi_fwd*(L/NLL)` was missing | LT-322E002 a pure integrator; fell 0.55 %/min once the loop pressure stopped masking it |
| 4 | `M_USERS_LP` sized off the phase-3 settle duty rather than the runtime seed | 4-bar header open by -0.123 kg/s -> P_LP walked every LP chest tsat |
| 5 | Darcy-Weisbach dP to the stripper normalised by the raw PFD density anchor, but `urea_soln_rho()` is a departure model about one global C10 reference that stream 207 is nowhere near | ratio 1.186 instead of 1.0 -> stripper at 144.61 instead of 144.0 bar a -> `duty_raw/STRIP_DUTY_RAW_DES_KW` 0.9927 instead of 1.0 -> 329D005 open by +0.155 kg/s |

Residual 2 was the largest single error and the one the two-path PT-323201 coupling exposed: the
chest *pressures* are the physical anchors (equipment DDS), so each design stroke is now derived
from the chest pressure and the live header rather than the reverse. Residuals 3 and 4 were masked
while the loop pressure was itself drifting -- fixing 1 made them visible.

Result, fresh design seed, 3 000 s of plant time, nothing touched:

| tag | design | before | after |
|---|---|---|---|
| PT-329201 | 140.700 bar a | 139.596 and falling | 140.700, flat |
| PT-323201 | 4.10 bar a | 4.07 | 4.100, flat |
| FT v305 | 24.563 t/h | 24.45 | 24.56, flat |
| FT v701 | 4.427 t/h | 4.41 | 4.43, flat |
| 323F010 evap | 12.013 t/h | 11.79 | 12.01, flat |
| TT-323005 | 106.0 C | 105.96 | 106.00, flat |
| TT-324001 | 130.0 C | 130.1 (after a 132.9 excursion) | 130.0, flat |
| PT-324201 | 0.330 bar a | 0.352-0.370 | 0.3317 |
| LT-322E002 | 50.0 % | 50.0 (masked) | 50.0, flat |

All three steam headers now close to machine zero at the seed: MP 3.6e-15, LP 0.0, 9-bar 0.0 kg/s.

An earlier attempt (G-LOOP-1, 2026-08-11) replaced this balance with a `gas_space_frac` capacity
and a `vapour_collapse` term carrying bar/h-per-K gains on the live header saturation temperatures.
That work was reverted at 2ce4869 and is not in the build; residual 1 above is the same defect it
diagnosed, closed here without the extra gains.

## Loss of 322E003 Condensation: the CCW Consequence Chain

Cutting the shell-side cooling water to the HP scrubber used to move nothing on the pressure side.
`scrub_322e003` computed its off-gas / overflow split from wash stoichiometry alone and never read
`m_ccw_kgh`, so with the CCW at zero the module still condensed the design make. The only symptom
was `TT-329125` running from its 95 C pin up to the 185 C process ceiling. The chain now runs end to
end, in four links.

### 1. The cooling-limited condensation gate

`rho_cond` already existed and was already right — condensation capacity over vent demand — but it
was computed *after* the scrubber call and fed only `nh3_slip`, whose second factor
`max(n_top[NH3] - STRIP_TOP_NH3_DES, 0)` is identically zero at the design overhead. It is now
hoisted above the call and passed in as `cool_frac`, which is what makes it a physical gate rather
than a diagnostic:

```text
f_th      = (T_cond - T_ccw,in) / (T_cond - T_ccw,in,des)      (warmer supply -> less driving force)
rho_cond  = (m_ccw/m_ccw,des) * f_th / (s*nu)                   nu = PT-329201 / PT_des
cool_frac = 1  if rho_cond >= 1 - 1e-6  else clamp(rho_cond, 0, 1)
```

Below unity the fraction `(1 - cool_frac)` of what design would have condensed stays in the vapour
phase. It is moved kmol for kmol from the bottom overflow back into the off-gas, so the node's
closure residual is untouched, and only the *condensed* part can flash — the 323P001 wash liquid
stays liquid, so the sump cannot be artificially dried out.

The dead band exists because `rho_cond` is built from live controller PVs and TIC-329005 settles on
80.00000005 C, not a bit-exact 80.0, leaving `rho_cond` at `1 - 5.3e-10`. That is the supply-T
loop's own residual, four orders below any instrument resolution, and treating it as a real deficit
would put a non-zero forcing term into the design fixed point.

### 2. HV-322604 is not a relief path

The gate hands the off-gas stream up to ~16.5 t/h of un-condensed vapour against the 5.9 t/h
reconciled inert purge. The valve model scales what it is offered (`m = offered * valve_factor`),
which is correct near design and wrong here: a DN-24 / Kvs 2.1 seat passes what its Kv, dP and
upstream density allow, and offering it three times the gas does not make it pass three times the
gas. Left uncapped it would simply vent the excess to 322C001, the boundary balance would close, and
the excursion would vanish — the retained vapour *is* the event. `Valve322604` therefore carries a
hydraulic ceiling:

```text
cap        = m_offgas,offered - m_uncond      (the purge the shell would have made at full CCW)
pass_frac  = min(1, cap / m_offgas,offered)
m_vent     = offered * valve_factor * pass_frac
```

Composition is untouched — the seat passes the live mixture, it does not fractionate. At design
`m_uncond = 0`, so `cap` equals the offered mass to the last bit, `pass_frac` is exactly 1.0, and
every downstream 328 anchor is unchanged.

The field description of this valve makes the point more strongly than the ceiling does. The
pressure ratio across it is ~4/140 = 0.028, far below the critical ~0.5, so the flow is **choked**:
"once sonic velocity is reached, the mass flow rate becomes independent of downstream pressure
fluctuations... material transfer is strictly a function of upstream pressure, valve opening area,
and fluid density." A choked seat categorically cannot pass more because more was offered. The model
still uses the sub-critical `sqrt(dP)` form (the ISA 75.01.01 choked model in `consequence.py` is
written but not wired into `main.py` — see the handoff), so the ceiling is what carries that physics
for now.

The valve is also *not* under automatic pressure control: the reference calls it the "HP Scrubber
Off-Gas Automatic Hand Valve... operated via the DCS as a remote-manual throttling or pressure
control valve". Opening it on a rising synthesis pressure is the operator's move, which is why it is
driven by HIC-322604 and exercised as an operator action in the test rather than by a controller.

### 3. The retained vapour is an inventory, and the pressure ODE reads its rate

The five-term boundary balance in the section above cannot see this event at all. 322E003 sits
*inside* the HP envelope, so mass that fails to condense crosses no boundary: `(m_in - m_out)` holds
its design value and `dP/dt` reads zero while the loop fills with vapour. What changes is the
specific volume of the retained mass. A kilogram held as vapour at 140.7 bar a occupies 1/111.0 m3
instead of the 1/1133 m3 it would occupy as carbamate liquid, and in an isochoric loop that
frustrated expansion is pressure. Converting the volume demand back onto the mass basis `C_loop`
already integrates:

```text
V_dot     = m_uncond * (1/rho_v - 1/rho_l)
m_pseudo  = V_dot * rho_v = m_uncond * (1 - rho_v/rho_l) = m_uncond * 0.90203
```

Both densities are PFD rows, not calibration: stream 204 is the 322E003 off-gas at 140.7 bar a
(111.0 kg/m3) and stream 206 the 322E003 overflow to 322F001 at the same pressure (1133 kg/m3) —
the two phases the mass is choosing between.

The state that carries this is an **inventory**, not a rate. The HP loop recirculates, so the
backlog comes back past the shell at `M/tau` and the fraction `cool_frac` of it condenses on that
pass. `tau` is `SYN_P_TAU_MIN` = 4 min, the loop's own declared vapour-inventory constant:

```text
dM/dt          = m_uncond - cool_frac * M / tau
m_phase_shift  = 0.90203 * dM/dt
dP/dt          = [ (m_in - m_out) - f_loop*R_des + m_phase_shift ] / C_loop
```

Forcing the ODE with the *net* rate makes the integral of the phase-shift term exactly
`0.90203 * M / C_loop`, so it adds nothing permanent: restore the CCW, `cool_frac` returns to 1, the
backlog condenses out over `tau`, and the pressure it was holding up comes back off. A partial
deficit settles at `M* = (1-cf)/cf * make * tau`; a total loss (`cool_frac = 0`) condenses nothing on
any pass and `M` ramps until the feed is cut.

### 4. LT-329501 reads a two-phase column, not a mass

`s.scrub_level_pct` is the true inventory from the sump mass ODE. It is what the condensation choke
and the ejector suction head see, and during a CCW loss it *falls* — the drain to 322F001 keeps
pulling while the condensate make collapses. LT-329501 is a DP cell and does not read mass; it reads
the hydrostatic head `rho_mix * g * h` of whatever column stands between its taps. Off-gas that is
no longer being condensed heats the pool, it flashes, `rho_mix = (1-alpha)*rho_l + alpha*rho_v`
collapses with the void fraction, and the column swells upward to hold the same mass. Over a fast
transient the swell beats the density loss, so the cell reads high while the vessel is draining:

The reading is not only high, it is **unsteady**. Slugs and bubbles passing the taps make the head
fluctuate, so the cell hunts — which is half of why operators mistrust it at exactly the moment it
matters. Two incommensurate periods (17 s slug, 7.3 s bubble) off the plant clock keep that
deterministic and reproducible rather than pseudo-random: a training simulator has to replay the
same excursion the same way. Both terms carry the same void fraction:

```text
alpha      = 1 - cool_frac
swell_pct  = SCRUB_SWELL_PCT_MAX * alpha                                SCRUB_SWELL_PCT_MAX = 18.0
noise_pct  = SCRUB_SWELL_NOISE_PCT * alpha
             * (sin(2*pi*t/17.0) + 0.6*sin(2*pi*t/7.3)) / 1.6           SCRUB_SWELL_NOISE_PCT = 2.0
LT-329501  = clamp(L_true + swell_pct + noise_pct, 0, 100)              (published indication)
```

`LT_329501_true`, `LT_329501_swell` and `LT_329501_noise` are published alongside it so the split is
inspectable. At design `cool_frac` is exactly 1, so `alpha` is exactly 0, both overlays vanish, and
the indication *is* the true level.

### Trip 22.2 — synthesis high-high

A latching boolean state machine alongside 21.2 / 21.4 / 22.1. `SYN_P_TRIP_BARA = 155.0 bar a` is an
**assumption, not a plant document** — no trip schedule in `References/` carries a synthesis
high-high setpoint, and neither the 322E003 nor the 322R001 datasheet PDF yields machine-readable
text. It sits ~10 % above the 140.7 design and above the 151.2 bar a PIC-322203 over-pressure SP, so
the CO2-line relief still acts first. `SYN_P_TRIP_RESET_BARA = 148.0 bar a` is the hysteresis floor.

```text
latched:      trips[22_2] = P_syn >= 148.0     (reset-block band; the latch does not self-clear)
not latched:  trips[22_2] = P_syn >= 155.0     (initiator -> latch)
action while latched: XV-322902 shut, 321P002 A/B stopped, SIC-321950/951 -> MAN 0
```

Cutting XV-322902 and both HP-NH3 pumps takes `m_in` to zero, so the boundary balance goes sharply
negative and the off-gas make collapses with `co2_scale`.

### 5. What was blocking the last two links: the CO2 delivery ceiling

With links 1–4 in place the excursion still could not reach the interlock, and the reason was not
in this chain at all. `phi_HP`, the CO2 feed's delivery taper, is driven by the head the 320K002
compressor can develop over the loop:

```text
P_line_ceil  = <compressor deliverable ceiling>
P_line_float = min(P_syn + dP_HP_des, P_line_ceil)
phi_HP       = min(1, sqrt(max(P_line - P_syn, 0) / dP_HP_des))
```

That ceiling was `SYN_P_MAX_BARA + DP_HP_DES` = 147.7 bar a — the HPCC's *normal-operating* PFD
pressure used as a *machine* limit. Two things followed from it, and neither was intended:

- the model's own CO2-line relief (PIC-322203, SP 151.2 bar a) could never open, because the line
  it protects could never get there — a dead protection layer; and
- a total loss of 322E003 condensation self-choked its own CO2 feed at 147.7 bar a. The scrubber's
  condensable make scales with `co2_scale`, so killing the CO2 feed kills the very off-gas that is
  building the pressure. The excursion stalled 7 bar below the high-high, **trip 21.4 (loss of CO2
  feed)** latched instead, and the last two links of the chain were unreachable.

The ceiling is now the loop's **mechanical design pressure** plus the design feed dP: a machine
feeding a loop rated 160 bar g must be able to deliver against that rating — which is the entire
reason the loop carries a high-high trip at 155.0 and a safety valve at 161.0. PIC-322203's setpoint
was written as a *rule* ("one design feed-dP above the ceiling", so it never fires inside the band
the compressor can legitimately deliver), not as the literal 151.2, so it moves with the ceiling and
stays dormant as its author intended. Leaving the literal behind would have made an
intentionally-dormant controller the plant's dominant protection: it opened at `P_syn` 147.7, dumped
the CO2 feed to the vent, and arrested the excursion — protection by accident, from a setpoint
written never to act.

### 6. SV-32201 — the synthesis-loop safety valve

The layer below the trip in protection order and above it in pressure, and the one whose lifting
*is* the hazard: it discharges the loop's NH3/CO2 inventory to atmosphere.

```text
SYN_PSV_SET_BARA = 160.0 barg + 1.013 = 161.01 bar a     (322E003 / 322R001 mechanical design)
m_psv = SYN_PSV_CAP_KGH * min((P_syn - P_set)/(0.10*P_set), 1)   linear to full lift at 10 % accumulation
```

It enters the pressure ODE as a real outflow and raises `SYN_PSV_LIFT` + `TOXIC_RELEASE`, with the
relieved NH3 rate published (`SV_32201_nh3_kgh`, composition taken from the loop's own off-gas
vector). In a correctly-layered plant it never opens, because the ESD at 155.0 cuts the feeds first
— `test_ccw_loss_chain.py` asserts exactly that in Phase 2, and exercises the valve itself in
Phase 4 by driving the pressure past it.

### 7. The LP section: 322C001 is not sized for the HP loop

HV-322604 at its design 50 % opening passes 5.9 t/h and retains the rest (link 2). Open it — which
is what an operator watching the synthesis pressure climb will do — and its equal-percentage trim
(R = 50) gives a factor of `50^0.5 * sqrt(dP/dP_des)` ≈ 7.5, so it dumps ~42 t/h of hot uncondensed
NH3/CO2 into a column that runs at 3.9 bar a. PIC-322201 opens PV-322201 fully and still passes only
`A328_VENT_DES * 100/67.8` ≈ 8.7 t/h. The rest pressurises the column:

```text
dP_c001/dt = A328_C001_P_KP * ((m_gcb - m_abs) - m_vent) / 3600
SV-32253:  set 30 barg + 1.013 = 31.01 bar a (322C001 datasheet), DN 100 on nozzle N11,
           linear to full capacity at 10 % accumulation; what it passes leaves with the vent
```

The 322C001 datasheet names this valve and names this upset — "a failure of the upstream HP Scrubber
cooling system leading to a massive breakthrough of hot, unreacted ammonia and carbon dioxide". Two
flags mark the two stages: `LP_ABSORBER_OVERLOAD` when the un-absorbed gas exceeds what PV-322201 can
pass at full stroke, `LP_ABSORBER_RELIEF` when SV-32253 actually lifts. Everything the SV passes
leaves through the atmospheric stack at the vent's live composition, so the published NH3 slip
(`vent_nh3_kgh`) *is* the release rate.

### Measured, from the design seed

Both 329P006 pumps stopped, HV-322604 left at its design opening, `dt = 2 s`:

| | design | measured |
|---|---|---|
| `cool_frac` | 1.0 | 0.0 |
| uncondensed off-gas | 0 t/h | 16.453 t/h retained in the loop |
| HV-322604 vent | 5.9 t/h | 5.9-6.1 t/h (seat-limited; it never carries the excess) |
| TT-322002 overflow | 178.1 C | 185.0 C (the `SCRUB_T_PROC_C` condensation ceiling) |
| LT-329501 indication | 50.0 % | spikes to 69.3 %, hunts, then falls with the drain |
| LT-329501 true level | 50.0 % | 0.0 % (sump empty in ~900 s) |
| indication minus true | 0.0 | 19.9 % peak (18.0 % swell + up to 2.0 % froth hunt) |
| AT-322701 reactor N/C | 2.977 | 3.130 (+5.1 %) |
| per-pass conversion | 54.454 % | 53.458 % |
| PT-329201 | 140.700 bar a | ramps ~3.9 bar/h to 154.9 bar a |
| trip 22.2 | clear | **latches at ~13 800 s (3 h 50 min)** |
| after the ESD | — | CO2 feed 0, both HP-NH3 pumps stopped, PT falls 154.9 -> 127.3 bar a |
| SV-32201 | shut | never lifts — the ESD acts 6 bar below it |

Same loss with HV-322604 driven to 100 %:

| | design | measured |
|---|---|---|
| HV-322604 vent | 5.8 t/h | 41.8 t/h into 322C001 |
| 322C001 pressure | 3.90 bar a | 32.68 bar a in ~200 s |
| SV-32253 | shut | lifts, 32.2 t/h |
| atmospheric NH3 slip | 1 557 kg/h | 20 718 kg/h |
| PT-329201 | — | 141.1 -> 137.1 bar a — venting *does* relieve the loop |

That last row is the trade the scenario exists to teach: the operator can arrest the synthesis
excursion with the inert vent, and the price is an order-of-magnitude ammonia release through the
LP stack and a safety valve lifting on a column rated for a twentieth of the flow.

**The 3 h 50 min to trip is the one number worth arguing with.** The ramp rate is
`SYN_P_PHASE_GAIN * m_uncond / C_loop` less the boundary terms' pushback, and `C_loop` = 1500 kg/bar
dominates it. That constant is calibrated to the *cold-start fill* dynamics (it sets the emergent
FOPTD `tau` that the 2025-06-03 field trend anchors at 57.8 min) and is roughly 25x a vapour-space
-only estimate for the loop (~75 m3 of vapour at `d(rho)/dP` ≈ 0.8 kg/m3/bar gives ~60 kg/bar). If
the real excursion should be minutes rather than hours, `C_loop` is the single number to revisit —
but it cannot be moved without re-deriving the cold-start anchor, so it is left alone and the
emergent time is reported as it stands.

### Consequence coverage

Every consequence the scenario brief lists, where it lives, and what asserts it. Phase numbers are
`test_ccw_loss_chain.py`.

| consequence | where | asserted |
|---|---|---|
| Condensation reduces or stops | `scrub_322e003` cooling-limited gate (`cool_frac`) | Phase 2: `cool_frac -> 0` |
| Synthesis pressure rises sharply | retained-vapour inventory + phase-shift term in the loop ODE | Phase 2: PT 140.7 -> 154.9 bar a |
| Overflow temperature rises | epsilon-NTU bridge; `T_overflow` -> `SCRUB_T_PROC_C` with no heat sink | Phase 2: TT-322002 -> 185.0 C |
| Actual sump level falls | 322E003 sump mass ODE (condensate make collapses, drain keeps pulling) | Phase 2: `LT_329501_true` 50 -> 0 % |
| Level transmitter reads high and erratic | two-phase swell + froth-hunt overlay on the DP indication | Phase 2: spike to 69.3 %, peak gap 19.9 %, hunt > 0.5 % of span |
| Inert vent opens, dumps to the LP section | HV-322604 equal-% capacity (`R^((theta-theta_des)/100) * sqrt(dP/dP_des)`) | Phase 3: 5.9 -> 41.8 t/h into 322C001 |
| LP section overloads | 322C001 pressure ODE vs PV-322201 at full stroke; `LP_ABSORBER_OVERLOAD` | Phase 3: flag raised, column 3.9 -> 32.7 bar a |
| Massive atmospheric ammonia slip | live vent composition `y_vent` x `vent_c001` (incl. what SV-32253 passes) | Phase 3: 1 557 -> 20 737 kg/h |
| PSV lift / uncontrolled NH3 release | SV-32253 on 322C001 (31.01 bar a); SV-32201 on the loop (161.01 bar a) | Phase 3: SV-32253 lifts 32.2 t/h. Phase 4: SV-32201 lifts 99.0 t/h carrying 27 087 kg/h NH3, `TOXIC_RELEASE` raised |
| Emergency plant trip on high-high | trip 22.2 latch -> XV-322902 shut, both 321P002 stopped, SIC-321950/951 MAN 0 | Phase 2: latches at 155.0 bar a. Phase 4: latch/hysteresis/reset |
| Reactor / HPCC imbalance, N/C and conversion | hot overflow -> ejector -> HPCC -> reactor; AT-322701 and `X_conv` | Phase 2: N/C 2.977 -> 3.130, conversion 54.454 -> 53.458 % |

Two of the brief's statements are **not** reproduced, and deliberately:

- *"the pressure control valves cannot relieve fast enough, so the loop PSVs lift"* — in this model
  they never need to, because the ESD at 155.0 bar a cuts both feeds 6 bar below SV-32201. That is
  correct protection layering and Phase 2 asserts it. SV-32201 is exercised directly in Phase 4 by
  driving the pressure past it, i.e. by assuming the ESD has failed.
- *"quickly"* — see the note on `C_loop` above. The excursion takes 3 h 50 min to reach the trip at
  full load, and the capacitance that sets that is calibrated to a different transient.

### Activity-model domain guard


The same collapse walks the 324 evaporator past the Extended-UNIQUAC validity window
(372.15-473.15 K, 0.02-1.00 bar a), and `solve_urea_mass_fraction_fast` *raises* outside it, which
killed the whole engine tick. `evap_w_eq` now saturates its arguments at the window edge — the
standard treatment for a correlation outside its range, and the reason the returned equilibrium
freezes at the nearest valid state instead of being extrapolated into nonsense — and
`evap_thermo_diag` reports `OUTSIDE_MODEL_DOMAIN` in the telemetry rather than throwing from the
diagnostics path. The design point sits inside the window, so every anchored value is untouched.

## PT-323201 / PIC-323202: One Gas Node, No Valve

Stream 305 runs from the 323C003 overhead straight into 323E003; there is no valve on it. The
323E003/323D001 datasheet says the same thing in words -- PIC-323202 "maintains the tank, and by
extension the entire recirculation stage, at a setpoint of 3.2 bar a" -- and the PFD tabulates the
two ends of that node: stream 305 at 4.1 bar a leaving the column, streams 308/310/321 at 3.2 bar a
in the tank. The rectifier vapour space, the condenser shell and the level tank therefore hold ONE
gas inventory at ONE pressure, and the two transmitters are two ends of it.

### The envelope balance

```text
generated  = m_flash_gas + m_pool_vap + m_797            (301 + 302 + inert recycle)
T_dew      = 74 + [ Tsat(P_d001) - Tsat(3.2) ]           frozen-offset dew point
condensed  = min( M_cond,des * (T_dew - T_tw,mean) / (74 - 60),  generated )
vented     = m_321,des * (op/op_des) * sqrt((P_d001 - P_e011) / (3.2 - 1.13))
dP_d001/dt = (generated - condensed - vented) / C_gas,   C_gas = 11.10 * 2.99 / 3.2 = 10.37 kg/bar
P_c003     = sqrt(P_d001^2 + (Q_load / C)^2)             C = Q_in,des / sqrt(4.1^2 - 3.2^2)
```

At design: generated == M305_des + M797, condensed == M_cond,des (dew point on its anchor, tempered
water at its 60 C mean), vented == M321_des, and those three sum to zero by the definition of
`R3232_E003_M_COND_DES` -- the node holds 3.2 bar a and the column 4.1, bit-exactly.

Three things had to be true at once and none of them were:

| # | what was wrong | what it did |
|---|---|---|
| 1 | the tank pressure was integrated from a fixed vent split of stream 305 (`gen321 - m_321`), not from the envelope | it tracked the column OUTLET, so when the 323E002 heater cut, the tank fell while the column rose |
| 2 | PV-323202 had no valve law -- flow was `(op/op_des)` alone | no restoring path: at 50 % stroke it pinned 323D001 to its 0.1 bar floor while 323C003 read 2.73 bar a, a 2.6 bar drop across a plain line |
| 3 | the startup-trend residual was added to PT-323201 as a bar offset, outside the line law | the head implied -100 % to +101 % of the flow actually passing; at 30 % opening it drove the column BELOW the tank it feeds |

Condensation now rides the **dew point** rather than a fixed split. That is where the node gets its
restoring path -- more gas, higher pressure, higher dew point, bigger driving force to the tempered
water, more condensed -- and it is also what makes TIC-323013 the fine trim on PIC-323202 that the
datasheet describes. Same frozen-offset idiom as `T_bub` at 323C003 and 323F004: the liquor is not
water, so only the slope comes from the steam table and the design point is the anchor.

### The 0.100 bar/% "field gain" was the startup ramp

Defect 3's residual came from reading the 2025-06-28 startup trend as 0.100 bar of PT-323201 per
point of LV-322501 opening. Regressing that trend's own 721 rows:

| window | slope | r |
|---|---|---|
| whole startup, LV 0.00-45.40 % | +0.0980 bar/% | +0.983 |
| near design, LV 35-50 %, n = 373 | **-0.0099 bar/%** | **-0.072** |

Over the ramp LV-322501 and PT-323201 rise together because the whole recirculation section is
filling and coming up to load -- the regression captures the ramp, not the lever. At load the field
data shows no dependence at all, because 323E003 absorbs the extra gas for a few hundredths of a bar.
That is exactly what the closed balance produces: **0.0222 bar/%** at design, the hydraulic slope,
which is also what the model asserted before the residual was ever introduced. So the residual is
gone; the envelope balance is the whole model.

### Verification

Line-law closure, `Q_line = C*sqrt(P_c003^2 - P_d001^2)` against the actual gas load, swept on all
three levers:

| | before | after |
|---|---|---|
| LV-322501 30-60 % | -100 % … +101 % | 0.0 % |
| PV-323202 10-80 % | 0.0-0.3 % | 0.0 % |
| PV-329202 40-98 % | -0.5 % … 0 % | 0.0 % |
| gap PT-323201 - PIC-323202 | -0.003 … +2.63 bar | +0.52 … +0.98 bar, monotone in flow |
| Pearson r on the pair | 0.877 | 0.984 |

Every lever now moves both pressures the same way, including LV-322501 above design where the
323E002 heater cut used to send them in opposite directions. The residual r < 1 is not decoupling:
`P_c003^2 - P_d001^2 = (Q/C)^2` is exactly linear in the squares and non-linear in the pressures
whenever the load moves, which is what a line does. Design hold over 3000 s is unchanged: PT-329201
140.700, PT-323201 4.100, v305 24.56, v701 4.43, evap 12.01, TT-323005 106.00, TT-324001 130.0.

## Scenario Coverage and Startup Fixed Point

`backend/scenario_coverage.py` is the executable traceability contract for all 48 actionable
subsections in `References/scenarios/Scenarios.md`, `Scenarios2.md`, and `Scenarios3.md`. Every entry
names the operator/process driver, the local response, the downstream response, and the test family
that proves its governing law. The coverage test parses the Markdown files, so adding a scenario
without adding evidence fails the build.

Thermodynamic services are routed by process envelope rather than forced through one package:

| domain | thermodynamic service |
|---|---|
| 141-bar synthesis reactor and HP recycle | Voskov-Voronin HP UNIQUAC/virial correlation |
| LP aqueous NH3-CO2-H2O recovery and absorption | Darde Extended UNIQUAC with SRK gas phase |
| urea-water vacuum concentration | neutral UNIQUAC departure with IAPWS-IF97 water properties |
| steam and condensate network | IAPWS-IF97 |

The two vacuum evaporator balances previously counted the design NH3/CO2 flash load twice: once in
the PFD ejector pull and again as an absolute live addition. They now add only the live departure:

```text
d_nc,1 = m_feed,1 * (w_NH3 + w_CO2) - m_feed,1,des * (w_NH3,des + w_CO2,des)
d_nc,2 = m_feed,2 * (w_NH3 + w_CO2) - m_feed,2,des * (w_NH3,des + w_CO2,des)
```

The HPCC liquid-inventory anchor is captured after the final reactor/steam pin, from the same runtime
state used by `step_sim`; the discarded CAS warm-up state no longer supplies that anchor. The three
LP steam users are seeded against the live 5.01325 bar(a) header, not a separate 4.4 bar value.

A fresh process is accepted only after 600 simulated seconds with no false consequence alarm, finite
states, nonnegative inventories, synthesis pressure within 0.15 bar, HP levels within 1 percentage
point, controlled temperatures within 1 C, and both vacuum pressures within 3% of their PFD values.
The deterministic boot-pin cache is rebuilt whenever its source hash changes, then restores these
design constants on subsequent launches.

## HMI Indicator Time Constants and Dead Time

Every bound numeric `t: 'ind'` record in `frontend/overlays.js`, plus every legacy `.pi` readout
updated through `frontend/app.js::setPI`, passes through one shared measurement block in
`frontend/indicator_dynamics.js`. Duplicate tags on different screens share the same state and
therefore display the same delayed value. The independent variable is packet field `t_sim` (plant
simulation time), not wall time, so FAST and SLOW pacing produce identical plant-time responses.

The measurement transfer function is first-order plus dead time (FOPDT):

```text
G(s) = exp(-theta*s) / (tau*s + 1)
y(k) = y(k-1) + [1 - exp(-delta_t/tau)] * [u(t-theta) - y(k-1)]
```

`u(t-theta)` is a zero-order-held value from a timestamped FIFO. The exact exponential update makes
the discrete first-order response independent of packet rate: one `tau` after a delayed step arrives,
the indication has completed `1 - exp(-1) = 63.212%` of its final change. First use seeds `y=u`, so
the design point has no artificial startup transient. A backward jump in `t_sim` clears every FIFO,
matching a simulator reset.

| instrument service | tau (s) | theta (s) |
|---|---:|---:|
| anti-surge pressure/flow profile | 0.05 | 0.002 |
| standard pressure | 0.75 | 0.10 |
| standard flow | 2.0 | 0.10 |
| turbulent level (`LT-322504`, `LIC-322501`, `LT-329501`) | 7.5 | 0.50 |
| calm level | 3.5 | 0.50 |
| thermowell temperature | 30.0 | 1.0 |
| composition analyzer | 60.0 | 600.0 |
| speed/current | 1.0 | 0.10 |
| valve/hand-station position | 3.5 | 0.25 |
| totalizer | 0.5 | 0.10 |
| generic numeric fallback | 1.0 | 0.10 |

The values use the midpoint of each range in `Plant PID Simulation Sequence.md`; small nonzero scan
delays are used where that procedure specifies fast DCS acquisition but no separate transport value.
The fallback is intentional: a newly added numeric indicator cannot silently bypass dynamics.
Tooltips publish the selected service, `tau`, and `theta` for operator/auditor inspection.

`LSL-321501` is a discrete level switch, not a numeric level transmitter and therefore does not use
the FOPDT indicator block. Vendor drawing `UD-AU-321-EC-0001`, sheet 5, places its two vessel
connections at +200 mm (N7B) and +1200 mm (N7A). The HMI is green `ON` while the 321D003 liquid
height reaches the upper +1200 mm connection and red `LOW` below it. The normal model seed is a
liquid-full 321D003, consistent with the unit mapping; telemetry also publishes the calculated
liquid height in millimetres for audit.

This is a transmitter/HMI measurement layer. It does not replace or feed back into equipment mass,
component, energy, pressure, or holdup equations and does not retune PID controllers. Vessel residence
times, exchanger thermal masses, hydraulic inventories, and existing backend controller-PV filters
remain the owners of physical process dynamics; applying those same lags again inside the equipment
balances would double-count inertia.

## HMI Page Geometry and the Level Bargraph

Screens 321-1, 322-1 and 322-2 are generated from the PowerPoint page drawings in
`Urea Simulation Docs/Equipment Drawing/UI Pages`. Each background PNG is that slide with the
overlay-supplied shapes deleted (indicator tag boxes, pump and XV icons, hand-switch buttons,
level bargraphs) and exported at exactly 1366x720. Overlay coordinates are the deleted shapes'
own centres, so an overlay always lands where its symbol was drawn. The slide canvas is
12192000 x 6858000 EMU, giving

```text
x_stage = (x_emu + cx_emu/2) * 1366 / 12192000
y_stage = (y_emu + cy_emu/2) *  720 /  6858000
```

The 16:9 slide is stretched, not letterboxed, onto the 1366x720 stage (`background-size:100% 100%`),
which is why the two axes carry different scale factors. Nested group shapes are resolved through
the group's `chOff`/`chExt` child-space transform before the mapping is applied.

Icon overlays (pumps, XVs) also carry the slide's rotation. The slide is rendered rotate-then-
stretch, so the overlay reproduces that order rather than rotating the already-stretched box:
the image is drawn at its un-stretched size `(w/R, h)`, rotated, then scaled back in x by
`R = (1366/12192000)/(720/6858000) = 1.06719`. For a 90-degree icon this yields an on-stage
footprint of `cy*sx` by `cx*sy`, which is what PowerPoint exports; at 0 degrees it collapses to the
plain `w` by `h` box. 322-2's XV-322901 is drawn at 90 degrees on the vertical leg and the two
329P006 pumps at 180 degrees.

`t: 'bar'` renders the vertical level bargraph drawn on 322R001, 322E001 and 322E003. It is a pure
display of an already-published percentage - it introduces no state and no equation of its own:

```text
h_fill / h_box = clamp(PV, 0, 100) / 100
```

`PV` is the same packet leaf its paired numeric indicator reads (`REACT_322R001.LT_322504`,
`STRIP_322E001.LIC_322501.pv`, `SCRUB_322E003.LT_329501`), so the bar and the number can never
disagree, and both inherit the turbulent-level FOPDT constants tabulated above. An unresolved or
non-numeric bind renders the empty white frame at zero fill rather than a misleading full bar.

## 329P006 A/B: CCW Circulation Availability

The 322E003 shell-side tempered-water loop has one motive source, the 329P006 A/B pumps. FV-329409
is a throttle across the pump head, not a source, so the flow the loop actually delivers is the
valve's characteristic gated by pump availability:

```text
frac_pump = 1  if (P329P006A or P329P006B) else 0
F_ss      = F_des * (OP_FV329409 / OP_des) * frac_pump
dF/dt     = (F_ss - F) / tau        tau = FIC_329409_TAU_S = 3 s
```

The two machines are duty/standby on a common header: either alone develops the full design head,
so `frac_pump` is 1.0 for one **or** both and is deliberately not additive - two centrifugal pumps
in parallel on this system curve do not double the flow. With neither running there is no head,
`F_ss = 0`, and FIC-329409 decays to zero over the 3 s flow lag (the coast-down).

Only the *thermal* half of the consequence chain was in the model when the pumps were wired in.
`m_ccw -> 0` drives the single-stream effectiveness to unity, so the CCW leaves at the condensing
temperature instead of its 95 C design pin, and the condensation capacity ratio collapses:

```text
C_ccw   = max(m_ccw*cp/3600, 1e-6)      eps = 1 - exp(-UA/C_ccw)  ->  1
T_ccw,out -> T_overflow -> T_proc                (bounded at 185 C, not +inf)
rho_cond  = (m_ccw/m_ccw,des) * f_th / (s*nu)  ->  0
```

The pressure half did not follow. `rho_cond` reached the pressure term only through
`nh3_slip = max(1-rho_cond,0) * max(n_top[NH3] - STRIP_TOP_NH3_DES, 0)`, whose second factor is
identically zero at the design overhead, so `rho_cond -> 0` multiplied by nothing and PT-329201 sat
flat through the entire excursion. That is closed in *Loss of 322E003 Condensation: the CCW
Consequence Chain* above: `rho_cond` now enters `scrub_322e003` as the condensation gate, the
un-condensed make is retained rather than vented, and the phase-shift term integrates it into
PT-329201. FIC-329409 in AUTO is reverse-acting and drives FV-329409 to 100 % chasing a flow no valve
can produce - correct controller behaviour, and the reason a restart surges before settling.

Neither pump carries a trip latch or a start interlock. Stopping both is a legitimate operator
action and is one of the instructive ones, so nothing in `handle_cmd` blocks it.

## XV-322903: 322E003 Sump-Overflow Isolation

`XV-322903` is a block valve on the 322E003 sump overflow line, downstream of the LT-329501 level
leg and upstream of the 322F001 ejector suction. It is not a throttle, so it enters
`ejector_322f001` as a boolean gate on the entrainment rather than as an opening:

```text
m_suc = capacity                     (XV-322903 open)
m_suc = 0                            (XV-322903 shut)
```

`capacity` is unchanged - the jet pump still develops its suction, there is simply nothing on the
line to entrain. The consequence propagates through the sump inventory ODE that was already there:

```text
d(M_scrub)/dt = m_cond_in - m_suc
```

With the valve shut, `m_suc = 0` and the whole condensation make accumulates. Measured from the
design seed: `LT-329501` rises 50.0 -> 62.5 % in 60 s of plant time, and `TT-322012` falls
105.3 -> 79.3 C because the ejector discharge is then motive NH3 alone (~29 C) with none of the hot
suction carbamate blended into it. The default is OPEN, so every design and reference call to
`ejector_322f001` is bit-exact and the design hold is unaffected.

The sump has no level controller, so re-opening the valve restores design entrainment but does not
drain the accumulated inventory: at design, entrainment equals overflow and `dM/dt` returns to zero
at the new level. That is the existing model's behaviour - the gravity-head multiplier
(`scrub_level_frac`) is computed but deliberately not applied to `m_suc` - not a property of this
valve.

## Pump Faceplate: START / STOP, One Live Button

No pump anywhere in the OTS starts or stops on a click. Every pump symbol -- the 321P002 A/B button
and icon on 321-1, and the 329P006 A/B overlays on 322-1 -- opens the same faceplate, and the
command is issued from there.

Exactly one of the two buttons is ever live:

```text
pump STOPPED  ->  START green (.primary) and clickable, STOP transparent, dim and disabled
pump RUNNING  ->  STOP  green (.primary) and clickable, START transparent, dim and disabled
```

The disabled half is a real `disabled` attribute, not a style: it cannot be clicked, and its
handler returns early even if something dispatches one. So the operator can never command the state
the plant is already in, and the faceplate cannot issue a command that contradicts what it displays.

The buttons send an **explicit** `{"type":"pump_toggle","id":...,"on":true|false}` rather than a
flip. `handle_cmd` treats a present `on` as START/STOP and an absent one as the legacy toggle, so
every existing caller and probe is unchanged. The reason for the explicit form is that the faceplate
renders from the last telemetry packet and is therefore up to one tick behind the engine: a toggle
issued from a stale view can invert the operator's intent, an explicit command cannot.

Interlock gating is untouched and is now *visible*. The faceplate's third line mirrors what
`handle_cmd` will actually do with a START on 321P002 A/B:

| trip state | line reads | what START does |
|---|---|---|
| no latch | `CLEAR` | starts |
| latched, cause recovered | `TRIP 21.4 LATCHED (clears on START)` | auto-acknowledges the latch, then starts |
| latched, cause still live | `TRIP 21.4 ACTIVE` | refused; the pump stays stopped and the latch holds |

START stays green and clickable in all three cases -- availability follows the *pump state*, per
spec -- and the interlock line is what tells the operator why a START did nothing. The 329P006 A/B
CCW pumps carry no trip latch, so their line reads `n/a`.

## Assumptions and Limits

- The model is reduced order: calibrated design conductance scales with process flow because no off-design exchanger datasheet is available.
- LP steam is saturated at live header pressure; detailed two-phase bundle hydraulics are outside scope.
- PV-329207B uses a lumped incompressible square-root pressure-drop law.
- Ejector and scrubber relationships preserve the design point and reproduce training-response direction, not nozzle-resolved CFD.

## Source Anchors

- `backend/main.py`: `hpcc_322e002`, `ejector_322f001`, 322E003 scrubber energy model, telemetry packet.
- `backend/thermo_urea_hp.py`: Voskov-Voronin HP equilibrium correlation and synthesis-ratio definitions.
- `backend/hp_recycle.py`: 323P001 displacement, finite scrubber capacity, valve retention, and recycle-burden laws.
- `backend/scenario_coverage.py`: 48-scenario traceability manifest and thermodynamic-domain router.
- `backend/steam_system.py`: LP-header balances, PIC-329207 master logic, PV-329207B export.
- `frontend/indicator_dynamics.js`: tag-class measurement profiles, timestamped dead-time FIFO, and exact first-order update.
- `tools/analyze_stream_lag.py` and `docs/analysis/urea_stream_lag_analysis.xlsx`: reproducible hourly-anchor extraction, gradient-lag correlations, route inventories, and evidence limits.
- `Urea_NormalOp_29-06-2025_Trends.xlsx` and `Urea_Startup_28-06-2025_Trends.xlsx`: hourly measured anchors and synthetic-interpolation notices.
- `References/Sources/Plant PID Simulation Sequence.md`: transmitter response/dead-time ranges and service classifications.
- `References/Sources/PIDs.pdf`, pages 3, 13, and 20: representative analyzer, pressure, and level instrument tags.
- `References/Sources/Manual.pdf`, page 83: flushed LI-329501, PI-329201, and N/C measurement service.
- Vendor sheet `UD-AU-321-EC-0001`, page 5: 321D003 dimensions and LSL-321501 connections N7A (+1200 mm) and N7B (+200 mm).
- `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`: design mass, pressure, and temperature points.
- `References/HPCC description.md`: carbamate exotherm and shell-side nucleate boiling.
- `References/Stamicarbon_Steam_Condensate_Network.md`: steam generation, control, and turbine-export topology.
- Voskov and Voronin, *J. Chem. Eng. Data* 61 (2016) 4110–4125, DOI `10.1021/acs.jced.6b00557`.
- Zhang et al., *Computers & Chemical Engineering* 29 (2005) 983–992, DOI `10.1016/j.compchemeng.2004.10.004`.
