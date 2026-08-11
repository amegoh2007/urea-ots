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

A consequence arrives when the fluid arrives. Gas fronts carry `CQ_BLOW_TD_S`, liquid slugs carry
`CQ_CARRY_TD_S`, and `consequence.transport_time_s(V, m_dot, rho)` derives a line's plug-flow transit
from its own inventory where the geometry is known. A seal loss at 323F004 therefore reaches 323F010
before it reaches 324F001, and 324F003 last — the ordering an operator sees on the trends.

## PT-329201 Synthesis-Loop Pressure

The loop pressure is a gas-inventory balance over the HP envelope. Liquid wash no longer enters the gas equation directly; its effect arrives through absorbed or retained vapour:

```text
gas_space_frac = clamp((1 - L_react) / (1 - L_react,design), 0.05, 1.5)
C_loop         = 1500 kg/bar * gas_space_frac
dP/dt          = [ (Δm_NH3 + Δm_CO2 + m_scrubber,retained)
                   - (Δm_bottoms + m_blowthrough)
                   - vapour_collapse ] / C_loop
vapour_collapse = max(m_absorbed - m_absorbed,design*s, 0)
                   + k_HPCC*(T_sat,HPCC,des - T_sat(P_LP)) - k_strip*(T_sat(P_MP) - T_sat,strip,des)
```

Every term is a vapour mass rate in kg/h through the same `C_loop`, bounded by `SYN_P_COLLAPSE_MAX_KGH`. Less wash raises `m_scrubber,retained`; more wash raises absorbed mass. This corrects the former wrong-sign result in which less liquid wash appeared as an immediate loss of HP gas inventory.

### Why it was rewritten (G-LOOP-1, 2026-08-11)

The previous form could not hold its own design point: from a fresh seed, with no operator action,
the loop railed to a pressure clamp inside 600 s. Three measured defects:

| # | defect | measured |
|---|---|---|
| 1 | balance summed **absolute** flows over an envelope whose anchors do not reconcile | open by −2 168 kg/h at design |
| 2 | `gas_space_frac` divided by `(100 − REACT_LEVEL_NLL_PCT)` = 20 while being fed the *physical head* %, design 97.52 | `C_loop` = 186 instead of 1500 — every imbalance amplified 8× |
| 3 | three of four collapse gains were **bar/h per K** applied to live steam-header saturation temperatures, at 5000 and 2000 | at t = 200 s: HPCC +1287, strip −1395, mass −27 bar/h |

Defect 3 is why the direction of the drift flipped between builds: two terms ~50× the mass balance,
opposite in sign, cancelling only by accident, and diverging when the steam headers moved. The loop
pressure was effectively decided by sub-degree LP/MP header noise. (A fourth gain,
`SYN_P_CW_COLLAPSE_GAIN`, was documented in kg/h and summed with the other three as bar/h.)

Result, fresh design seed, 6 000 s of plant time, nothing touched:

| | before | after |
|---|---|---|
| p_syn | rails to a clamp in 600 s | 140.700 → 140.463, turning back up |
| HPCC level | 50 → 100 % (railed) | 50 → 52.4 %, steady |
| stripper level | 99.9 % / 47.3 % depending on build | 50.00 %, flat |

Step response is preserved: −20 % CO2 → −1.31 bar; HV-322604 opened 50→90 % → −1.74 bar; pinched
50→20 % → +0.20 bar; CCW −10 K → −0.20 bar; LV-322501 wide open → −4.68 bar. Magnitudes are much
smaller than the old gains produced — those values could not be retained, because they rail the loop
unprompted.

The 322E002 sump was the second symptom: the comment block there describes a gravity-head outflow
`phi_out = phi_fwd·(L/NLL)` that "settles at a bounded equilibrium instead of railing", but the code
under it read `phi_out = phi_fwd` — the level term was missing, leaving exactly the pure integrator
the comment says was fixed. Restored as documented.

## Assumptions and Limits

- The model is reduced order: calibrated design conductance scales with process flow because no off-design exchanger datasheet is available.
- LP steam is saturated at live header pressure; detailed two-phase bundle hydraulics are outside scope.
- PV-329207B uses a lumped incompressible square-root pressure-drop law.
- Ejector and scrubber relationships preserve the design point and reproduce training-response direction, not nozzle-resolved CFD.

## Source Anchors

- `backend/main.py`: `hpcc_322e002`, `ejector_322f001`, 322E003 scrubber energy model, telemetry packet.
- `backend/thermo_urea_hp.py`: Voskov-Voronin HP equilibrium correlation and synthesis-ratio definitions.
- `backend/hp_recycle.py`: 323P001 displacement, finite scrubber capacity, valve retention, and recycle-burden laws.
- `backend/steam_system.py`: LP-header balances, PIC-329207 master logic, PV-329207B export.
- `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`: design mass, pressure, and temperature points.
- `References/HPCC description.md`: carbamate exotherm and shell-side nucleate boiling.
- `References/Stamicarbon_Steam_Condensate_Network.md`: steam generation, control, and turbine-export topology.
- Voskov and Voronin, *J. Chem. Eng. Data* 61 (2016) 4110–4125, DOI `10.1021/acs.jced.6b00557`.
- Zhang et al., *Computers & Chemical Engineering* 29 (2005) 983–992, DOI `10.1016/j.compchemeng.2004.10.004`.
