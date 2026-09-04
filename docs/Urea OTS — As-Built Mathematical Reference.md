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

## Unified Rigorous VLE / Flash Service (`backend/thermo_service.py`)

**Phase 1 of the Heuristic Eradication Report.** The bubble-point work above gave the 323 stages a
real activity model for *pressure*. It did not give them a *phase split*: the vapour composition
leaving 323C003, 323F004 and 323F010 was still `sol_vapour_y`, a set of relative volatilities
back-solved once from the PFD design rows and then held constant. The same frozen alpha vector
governed 323C003 at 135 °C / 4.1 bar a and 323F010 at 99 °C / 0.46 bar a, so the vapour composition
had a derivative of exactly zero in both temperature and pressure (report finding B-8).

`thermo_service` is the single entry point that replaces it. It stands on four modules that already
existed in this repository, three of which the engine had never called:

| module | contributes |
|---|---|
| `vle_nh3co2h2o` | Extended UNIQUAC electrolyte activities, Henry constants, IF-97 water line |
| `props_nh3co2h2o` | SRK vapour fugacity coefficients, k_ij = 0 (Thomsen 2005) |
| `thermo_extended_uniquac` | neutral H2O/urea binary UNIQUAC (Voskov-Voronin) |
| `gap_g6_h0_enthalpy` | absolute stream enthalpy, elements-at-298.15 K datum — this is what makes `flash_ph` possible |

### The equations

K-values are gamma-phi on an **apparent, total-species** basis — the electrolyte model speciates
ammonia into NH3(aq)/NH4+/NH2COO- and CO2 into CO2(aq)/HCO3-/CO3--, but the engine's mass balance
tracks total NH3 and total CO2, so the ratio the flowsheet needs is:

```text
K_i = p_i / (phi_i^V * P * x_i,total)        p_i from the activity model, phi_i^V from SRK
```

solved against Rachford-Rice by bisection, inside a damped successive-substitution outer loop on
(x, y) because K depends on both:

```text
sum_i  z_i (K_i - 1) / (1 + psi (K_i - 1))  =  0
```

The bubble point uses the **same** phi, `P = sum_i p_i / phi_i(y, T, P)` by fixed-point iteration on
y. With phi applied only inside `k_values` the two entry points sat on different surfaces and a
flash *at* the computed bubble temperature returned psi = 1.5e-3 instead of ~0; they now agree to
1e-9 or better. `bubble_p(..., srk=False)` still returns the ideal-vapour sum, which is what
`vle_nh3co2h2o.bubble_p_bara` reports and what the PFD comparison below was measured on.

| stage | T (°C) | ideal sum | gamma-phi | P PFD | gamma-phi error |
|---|---|---|---|---|---|
| 323C003 | 135 | 4.387 | 4.459 | 4.10 | +8.8 % |
| 323F004 | 106 | 1.328 | 1.337 | 1.13 | +18.3 % |
| 323F010 | 99 | 0.468 | 0.470 | 0.46 | +2.1 % |

Three further details are load-bearing, and all three were wrong in the first cut:

* **Non-volatiles stay in the Rachford-Rice sum at K = 0.** Their term is `-z_i/(1-psi)`, which
  diverges as psi → 1 and is the only thing that bounds the vapour fraction below total
  vaporisation. Filtering them out — the obvious move, since K = 0 contributes nothing at psi = 0 —
  returned psi_mass = 1.0 at all three 323 stages, i.e. a 69 wt% urea liquor flashing completely.
* **The substitution must be damped adaptively.** a_CO2 spans four decades across the envelope, so
  the undamped map oscillates: measured non-convergent in 40 sweeps at both 323C003 and 323F004. A
  fixed 0.5 factor converges but caps the contraction rate and dominates runtime. Full step while
  the residual falls, halve only on a sweep that made it worse.
* **The convergence test must include psi, not just the liquid.** Near the bubble point psi is tiny,
  so x ≈ z and an x-only criterion is met while psi is still moving — measured psi = 1.4e-4 at a
  state whose converged value is ~1e-10.

### Two domains, because neither model covers the plant

| domain | owns | why |
|---|---|---|
| `electrolyte_gamma_phi` | 323C003, 323F004, 323F010 | volatiles carry the bubble point |
| `neutral_urea_water_uniquac` | 324E001, 324E003 (bubble point only) | at 94–98 wt% urea the electrolyte model's "urea is a diluent" assumption fails: +30.6 % and +65.7 % on bubble pressure, against +2.2 % for the neutral binary at 324E003 |

### What it refuses, and why that matters more

`vle_nh3co2h2o._bracket` **clamps** at the table edges rather than extrapolating. An out-of-envelope
call therefore does not fail loudly and does not extrapolate wildly — it silently returns the edge
node, i.e. *a frozen constant behind a call that looks like a solve*. That is strictly worse than an
honest hardcoded split vector, because the heuristic becomes invisible.

So the service raises `OutOfDomain` instead, and the caller keeps whatever anchored model it has —
reported live in the tick packet as `SOL.vle_domain`, never assumed. Measured against the table
envelope (T 80–170 °C, N ≤ 16, C ≤ 7 mol/kg water):

| state | T | N load | C load | verdict |
|---|---|---|---|---|
| 322R001 overflow (stream 207) | 183 °C | 100.0 (6.2×) | 22.4 (3.2×) | refused |
| 322E003 off-gas feed | 183 °C | 869.3 (54.3×) | 258.1 (36.9×) | refused |

The 322E003 feed also carries N2, O2, CH4 and H2, for which this repository holds neither Henry
constants nor SRK critical constants (`props_nh3co2h2o.SRK_CRIT` covers H2O, NH3, CO2 only). The
reactor melt is not an aqueous solution at all; the underlying parameter set is a CO2-capture model
fitted to dilute aqueous loadings below ~150 °C. Tracked as **G-VLE-3**.

Likewise `flash()` is undefined on the neutral-urea domain: the binary carries no NH3/CO2, and in a
97.7 wt% urea / 1.4 wt% water melt the electrolyte path is not in its dilute limit — the loading
basis is *mol per kg of water*, so 0.04 wt% NH3 reads as 1.69 mol/kg and the flash returns an NH3
vapour mole fraction of 0.24 for a melt whose vapour is essentially pure steam. `bubble_p` /
`bubble_t` stay valid there. Tracked as **G-VLE-2**.

### Cost, and why the memo is not a heuristic

A converged flash costs ~12 ms: ~11 outer sweeps, each walking the electrolyte table and an SRK
cubic. Three per tick at dt = 0.1 s and up to 60× real time is far over budget — the same wall
`vle_nh3co2h2o` documents one level up for calling `speciate` inline.

It is also unnecessary. A flash is a **state function** of (T, P, z), and those inputs move on stage
residence times of 150–600 s, not on the 0.1 s tick. The result is therefore memoised against
quantised inputs — 0.02 °C, 1e-4 bar a, 100 ppm mass fraction, each far below both instrument
resolution and the model's own residual — so the solve repeats only once the state has actually
moved. This bounds a numerical convenience, never a physical response; `_FLASH_CACHE_SIZE = 0`
disables it and solves every call. Convergence tolerance is 1e-7 on liquid mass fraction, measured:

| tol | iters | ms | max &#124;dy&#124; vs a 1e-12 solve |
|---|---|---|---|
| 1e-9 | 16 | 14.0 | 4.1e-09 |
| 1e-7 | 11 | 8.6 | 5.3e-07 |
| 1e-5 | 6 | 5.1 | 6.8e-05 |

1e-7 sits seven orders below the model's own PFD residual, so tightening further buys nothing
physical and costs 60 % more on every cache miss.

### What the frozen alphas were actually doing: evaporating urea

The `sol_vapour_y` alpha vectors were back-solved from the PFD design rows by `_sol_stage_anchor`,
which infers a relative volatility for **every** species including urea. It did not come out zero:

| stage | alpha_Urea | y_Urea (frozen) | y_Urea (flash) |
|---|---|---|---|
| 323C003 | 0.000792 | 0.000332 | 0 |
| 323F010 | 0.001363 | 0.004887 | 0 |

So 0.49 % of the 323F010 overhead was urea, and at the ~14 t/h design evaporation rate that is
**≈68 kg/h of urea leaving as vapour**. Urea is non-volatile — it decomposes rather than boils at
these temperatures — and `sol_advance` removes `m_vap * y[k]` from the holdup, so this was a real
mass sink, not a reporting artefact. `thermo_service` gives every non-volatile K = 0 exactly, so the
loss is gone.

Removing the leak also CLOSES a feedback loop that the frozen vector had held open, and that is
the more consequential result. 323F010 runs:

```text
w_f010 -> T_bub -> qevap_relax -> m_evap -> energy balance -> T -> y_evap -> w_f010
```

The alpha vector had `dy/dT = 0` exactly, so the last leg did not exist. The flash gives it a real
gain (measured at 0.46 bar a): dy_H2O/dT = +0.0096 /K at 99 °C, +0.0159 /K at 101 °C. Hotter ->
more water leaves -> holdup more urea-rich -> higher bubble point -> less evaporative cooling ->
hotter. That positive feedback is physically real and is what TIC-323012 exists to control.

### Why the absolute flash split could not be used, and what replaced it

The first cut of `sol_vapour_y_vle` returned the flash's `y` **outright**. That does not survive
contact with the licensor's own design rows. Evaluated at the PFD design composition, temperature
and pressure of each stage — i.e. at exactly the point the alpha vector was back-solved from — the
model's absolute split is wrong by far more than its slope is:

| stage | NH3 to vapour, PFD anchor | NH3 to vapour, raw flash | error |
|---|---|---|---|
| 323C003 | 8 092 kg/h | 5 107 kg/h | −37 % |
| 323F004 | 1 363 kg/h | 609 kg/h | −55 % |
| 323F010 | 819 kg/h | 497 kg/h | −39 % |

This is the same bias `vle_nh3co2h2o` already records against the PFD triplets (+1.7 to +17.5 % on
bubble pressure), surfacing on the split instead of on the pressure. Open loop it **compounds down
the train**: the ammonia not stripped at 323C003 arrives at 323F004, and so on. Measured settled
state was NH3 1.64 wt% / CO2 1.14 wt% in the 323F010 liquor against a design 0.08 / 0.02 — 20x and
57x over. Dissolved ammonia elevates the boiling point hard, so the stage reached its 99 °C setpoint
at **76.56 % urea instead of 80.00 %**: a 3.44-point miss on the product spec the 324 vacuum train
depends on. Urea was not being lost — ammonia was taking its place. The mass balance closed; the
product did not.

The replacement keeps the PFD as the anchor and takes only the derivative from the model:

$$\alpha_i(\text{live}) = \alpha_{i,\text{PFD}} \times
\frac{\alpha_{i,\text{model}}(T, P, w_{\text{live}})}{\alpha_{i,\text{model}}(\text{design})},
\qquad \alpha_{i,\text{model}} = y_i/w_i \ \text{from the flash}$$

At the design state the bracket is exactly 1.0, so the split is the licensor's own, bit-exact, and
the boot pin and every back-solved lambda are untouched. Off design the Extended UNIQUAC + SRK
K-values supply how the split moves — the thing the frozen vector could not do at all. This is the
same departure construction the rest of the engine uses for cp, UA and the bubble points.

The one term **not** scaled is the structurally non-volatile set (`SOL_NONVOLATILE` = urea, biuret,
HCHO): there K = 0 is structure, not model bias, so those are zeroed outright. That is what removes
the urea leak above, and it is the only reason the 323C003 and 323F010 design splits move at all
(323F004's alpha_Urea was already zero, so its design split is unchanged to the last bit).

### A clamped bubble point, and why it had to be made to refuse

`thermo_service.bubble_t` originally returned the **bracket edge** when the root was not bracketed.
At the ammonia-laden composition above, the true bubble point at 0.46 bar a lies below the activity
model's own 80 °C grid floor, so the function silently handed back `80.0` as though it were an
answer — precisely the clamped-lookup failure the service exists to refuse (the reason the HP loop
was quarantined in the first place). It now raises `OutOfDomain` on either unbracketed end.

This mattered, and not only in principle. With the clamp in place the 323F010 stage was pushed off
its bubble-point branch onto the `min()` flow cap, where TIC-323012 *does* have direct gain: the run
settled at 80.21 % urea with a 0.0002 °C envelope and looked like a clean result. It was the right
answer for the wrong reason, resting on an off-envelope clamp of 87.9 °C. Refusing exposes it.

### Both legs of the loop on one surface (finding A-11)

`T_bub_f010` used `bubble_T_raoult` (ideal, water-only) while `y_evap` came from the electrolyte +
SRK service — two thermodynamic models on the two legs of one feedback loop, disagreeing by 2.02 °C
at the design composition (Raoult 100.4618, gamma-phi 98.4389) and by ~13 % in slope. `sol_bubble_t_dep`
now takes both from the service, in the same departure form:

$$T_{bub} = T_{sp} + \left[\,T_{bub}(w_{live}, P) - T_{bub}(w_{des}, P)\,\right]$$

anchored by `_sol_tbub_anchor`, so the bracket is a literal 0.0 at design and the PFD boundary is
still exact. Raoult survives as the off-envelope fallback only, and is used as a **matched pair**
(its own live value against its own anchor) so a fallback evaluation stays internally consistent.

### Measured result

20 000 s from the design seed, all three stages reporting `electrolyte_gamma_phi` with no fallback
and no refusal:

| quantity | design | settled (t = 20 000 s) | error |
|---|---|---|---|
| TT-323012 | 99.0 °C | 99.0000 | 0.0000 |
| stream 317 rate | 92.7489 t/h | 92.6148 | −0.14 % |
| stream 317 urea | 80.0016 % | 80.0849 | +0.083 pt |
| 323F010 NH3 | 0.0800 % | 0.0850 | — |
| 323F004 NH3 | 0.8800 % | 0.8350 | — |
| 323C003 NH3 | 2.1300 % | 2.0733 | — |

against 76.56 % urea and NH3 1.64 % on the absolute-flash form. The residual envelope over the
settled band is 0.026 °C at the retuned Ti (Appendix C of `Master_PID_Tuning_Constants.md`); it is a
real limit cycle around a real positive-feedback loop, not a walk, and the pre-Phase-1 model reached
a bit-stationary point only because that loop had been deleted.

Memo cost, measured over the run: `bubble_t` 99.93 % hit rate (59 solves in 80 006 calls), flash
99.64 % (855 in 240 003). A `bubble_t` miss is 9.7 ms and a hit 0.031 ms — 310x — which is what makes
a per-tick rigorous bubble point affordable at all.

### Design-point identity short-circuits removed

Two `if (at design) return design` branches are deleted (report finding A-15):

* `vacuum_condenser_node` returned its spec verbatim when every argument equalled its design value.
* `_hpcc_flash_split` returned `HPCC_FRAC_GAS_DES` when `p_rat == 1.0 and T_k == T_0`.

Both now run their own solve at the design point and land on it by converging. Two further guards in
`_hpcc_flash_split` are deliberately **kept** — they protect a division on the very next line (no
distributing feed, or a feed already single-phase) and are degenerate-input answers, not a bypass of
the maths at design.

## Hydraulic Network: IEC 60534 Valves and Vapour-Space Pressure States (`backend/hydraulics.py`)

Phase 2 of the eradication report. The module carries the equations; wiring is done one unit at a
time so the boot pin can be re-proved after each. **All of Phase 2 is now done except two A-6
vessels, and both of those are blocked on a specific missing number rather than deferred by choice:
324F001's cylindrical height and 328D001's contradictory volume.** Findings A-6, D-1, D-2, D-8 and
D-19/D-20/D-21 are otherwise closed; A-7 remains blocked on data.

### Why the engine calls a ratio and not the absolute ISA law

`References/Datasheets` holds equipment datasheets — vessels, exchangers, pumps. It contains **no
control-valve datasheets**, so there is no vendor `Cv`, `FL` or `xT` anywhere in this repository, and
asserting one would be inventing data. Rather than back-solve a `Cv` and pretend to it, every site
calls the ratio of the ISA law to itself at the design condition:

$$\dot m = \dot m_{des}\cdot\frac{\Phi(\text{live})}{\Phi(\text{design})},\qquad
\Phi_{liq}=f(h)\sqrt{\Delta P_{eff}\,\rho_1},\qquad
\Phi_{gas}=f(h)\,P_1 Y\sqrt{\frac{xM}{T_1Z}}$$

$N_6/N_8$, $F_p$ and $C_{v,max}$ appear identically in numerator and denominator and cancel
**algebraically**, so the answer never depended on the `Cv` we do not have. What survives is exactly
what the frozen `design × stroke/stroke_des` form was missing: the installed characteristic, the live
density, the live $\Delta P$ from node pressures on both sides, and the choke.

There is also a numerical reason. Back-solving `Cv` and multiplying straight back through is **not**
bit-exact — measured `101490.00000000001` against `101490.0` — and this engine's pin asserts the
design point to the last bit. A 1-ulp drift at every valve on every tick walks a long run off its
anchor. In the ratio form the design bracket is exactly 1.0.

`FL = 0.90`, `FF = 0.96` and `xT = 0.75` are IEC 60534-2-1 Table-1 representative values for a globe
valve with a contoured plug, applied uniformly and stated as assumptions. They set only *where*
choking begins; every 323 liquid service runs well below that point at design.

### Choking, which the old form could not represent at all

For compressible service $x=\min(\Delta P/P_1,\;F_\gamma x_T)$ and $Y = 1-x/(3F_\gamma x_T)$, floored
at 2/3. The `min()` **is** the choke: past the critical ratio the flow depends on downstream pressure
not at all. Verified on a 140.7 bar a service — flow flat at 24 563 kg/h for $p_2$ = 20, 4 and
0.5 bar a. The incompressible $\sqrt{\Delta P}$ law it replaces had flow still climbing as the
downstream pressure fell, which is not a thing that happens.

### Unit 323, what changed

| finding | site | was | is |
|---|---|---|---|
| D-1 | LV-323501 | `M314_DES × (op/op_des)` — no ΔP term at all | IEC 60534 liquid on live `r323_c003_P` → `r323_f004_P` |
| D-1 | LV-323505 | `M319_DES × (op/op_des)` | same, on `r323_f004_P` → `r323_f010_P` |
| A-6 | 323F010 vapour space | shared `0.02 bar/(kg/s)` | $RT/(V_v\overline M)$ + thermal term + level swell |

Geometry is sourced, not fitted: `References/323F004 323E010 323F010.md` gives 323F004 as ID 1384 mm
× 1800 mm shell (2.708 m³) and 323F010 as ID 3478 mm × 2437 mm (23.153 m³). Densities 1106 and
1130 kg/m³ are the PFD-21 "Density eff." row for streams 314 and 319.

The installed characteristic for both letdown valves is set **linear** (`R323_LV_CHAR`), and that is
a deliberate, conservative choice rather than a physical claim: with no valve datasheet, equal-%
would roughly double LIC-323501/505 loop gain at the 50 % design stroke, which is a retune wearing a
physics costume. Linear preserves the gain basis those loops were tuned against while still
delivering the terms that were genuinely absent.

### The shared capacitance was wrong by 4.69× at this vessel

323F010's own coefficient, from its real shell and its design holdup:

$$V_v = 23.153 - \frac{M_l}{\rho_l} = 17.781\ \text{m}^3,\qquad
K = \frac{RT}{V_v\overline M} = 0.0939\ \text{bar}/(\text{kg/s})$$

against the `0.02` it shared with eight other vessels — among them the 16.8 bar a hydrolyser. The
lumped form also had no molar basis (1 kg/s of steam and 1 kg/s of CO₂ are not the same dP/dt), no
thermal term, and no level swell.

**This is not a stability risk, and the reason is worth recording.** `pull_f010` is linear in P, so
the node is first-order: $d\delta P/dt = -K\,(\partial \dot m_{pull}/\partial P)\,\delta P$ with
$\partial \dot m_{pull}/\partial P = \dot m_{evap,des}/P_{des} = 7.254$ kg/s/bar. Stiffening $K$ can
only make it faster, never oscillatory:

| | K | pole | τ | discrete pole at dt = 0.25 s |
|---|---|---|---|---|
| old shared 0.02 | 0.02000 | −0.1451 /s | 6.89 s | 0.9637 |
| new RT/(V_v·M̄) | 0.09386 | −0.6809 /s | **1.47 s** | 0.8298 |

Both are well inside the unit circle. A 17.8 m³ vapour space really does respond in about 1.5 s; the
old constant was over-damping it by a factor of five with no physical basis.

### Measured, 30 000 s from the design seed

Design invariance first: after one tick `r323_f004_P` = 1.1300000000, `r323_f010_P` = 0.4600000000,
`r323_f010_T` = 99.0000000000, and all three 323 holdups are bit-exact at design.

Envelope per 3 000 s window, to show the wider ripple is bounded rather than slowly growing:

| window (s) | T span (°C) | P span (bar) | urea (%) |
|---|---|---|---|
| 0 – 3 000 | 0.0228 | 0.00237 | 80.048 |
| 3 000 – 6 000 | 0.0700 | 0.00506 | 80.071 |
| 6 000 – 9 000 | 0.0318 | 0.00308 | 80.065 |
| 9 000 – 12 000 | 0.0416 | 0.00271 | 80.075 |
| 12 000 – 15 000 | 0.0809 | 0.00333 | 80.070 |
| 15 000 – 18 000 | 0.0099 | 0.00132 | 80.075 |
| 18 000 – 21 000 | 0.0747 | 0.00345 | 80.064 |
| 21 000 – 24 000 | 0.0412 | 0.00243 | 80.066 |
| 24 000 – 27 000 | 0.0267 | 0.00210 | 80.065 |
| 27 000 – 30 000 | **0.0072** | 0.00075 | 80.065 |

Aperiodic and bounded, with no trend across 8.3 h of sim time and the tightest window last. Pressure
moves at most 0.005 bar on a 0.46 bar node (1 %). Product urea sits in 80.064–80.075 % throughout —
unchanged by Phase 2, against 80.085 % before it.

### Unit 328, what changed

| finding | site | was | is |
|---|---|---|---|
| A-6 | 328C002 vapour space | shared `0.02 bar/(kg/s)` | $RT/(V_v\overline M)$ on a real 12.849 m³ shell — **8.5×** |
| A-6 | 328C004 vapour space | shared `0.02 bar/(kg/s)` | same, 15.990 m³ shell — **6.7×** |
| — | `dP_737`, `dP_750_live` | assigned twice, lagged form dead | dead stores removed, no number changed |

Geometry from the vessel datasheet narratives: 328C002 ID 1250 × 10 470 mm, 328C004 ID 1250 ×
13 030 mm. Both desorbers carry only a tray inventory — 13.2 % and 9.7 % liquid-full at design — so
most of the shell is vapour and the real coefficient is far above the constant they shared with a
62 m³ hydrolyser and a level tank.

Both are **self-regulating**, which is why they were safe to stiffen: each overhead rises with
$\sqrt{\Delta P}$ against the next node, so $\partial\dot m/\partial P > 0$ and the node stays
first-order. 328C002 pole −0.176 /s (discrete 0.956), 328C004 −0.632 /s (discrete 0.842).

Measured over 24 000 s, the envelopes **decay** rather than settling into a cycle:

| window | P_c002 span | P_c004 span | T_c002 span (°C) | T_c004 span (°C) |
|---|---|---|---|---|
| 3 000 s | 0.0540 | 0.0542 | 0.540 | 0.495 |
| 9 000 s | 0.0333 | 0.0311 | 0.334 | 0.284 |
| 15 000 s | 0.0102 | 0.0087 | 0.102 | 0.079 |
| 24 000 s | 0.0102 | 0.0081 | 0.102 | 0.074 |

Settled: P_c002 3.5021 (design 3.500), P_c004 3.7034 (3.700), T_c002 139.021, T_c004 143.031, with
unit 323 unmoved (urea 80.075 %, TT-323012 99.0007).

### HV-322604, the choked inert purge (report D-2)

The site the eradication brief named explicitly, and the one where the incompressible law was most
plainly wrong. HV-322604 lets carbamate off-gas down from the synthesis loop at 140.7 bar a to the
LP absorber at 4.0 bar a — a pressure ratio of 0.028. With $\gamma \approx 1.30$ the choke threshold is
$F_\gamma x_T = 0.696$ while $\Delta P/P_1 = 0.9716$, so **the valve is choked at its own design
point**, and stays choked until the downstream node rises above about 42.7 bar a. It is choked for
every plausible $\gamma$ from 1.20 to 1.40, so this is not a marginal call.

It was modelled as `_eq_pct(θ) · √(ΔP/ΔP_des)`. Two separate things were wrong with that:

**Flow responded to downstream pressure while choked.** Choked flow is a function of upstream
conditions only. Under the ISA-75.01 law the mass flow is now exactly linear in $P_1$ — measured
5901.4/140.7 = 5033.1/120 = 4194.3/100 = 1887.4/45 = 41.94 kg/h per bar, identical to twelve
significant figures — and $p_2$ does not enter at all.

**A fully closed valve passed 14 % of design.** `_eq_pct(0, 50)` is $50^{-0.5} = 0.1414$: the bare
equal-percentage exponential $R^{h-1}$ never reaches zero and nothing clamped it. So driving
HIC-322604 to 0 % still vented ≈ 835 kg/h of NH₃/CO₂ out of a 140.7 bar loop the operator believes
they have isolated — an operator trained on that learns that closing the vent does not stop the
vent. `hydraulics.cv_fraction` returns a hard 0.0 at zero travel.

The design molecular weight is passed explicitly (`mw_des`), so composition does **not** cancel out
of the anchored ratio: $\dot m \propto \sqrt{M}$ survives, and a heavier off-gas puts proportionally
more kilograms through the same trim. Verified to 1e-12 against $\sqrt{33.0/27.4768}$.

Design invariance is preserved exactly — `valve_frac` is 1.0 to the bit at
(HIC 50 %, 140.7 bar a, 114 °C), because the anchored ratio evaluates the same expression on the
same operands in numerator and denominator.

### The unit-328 vessel that is still NOT wired

**328D001 — a source conflict, not a gap.** `References/328E004 328D001 328P002 Datasheets.md` gives
inside diameter 1684 mm and tangent-to-tangent 1950 mm, *"which yields a nominal internal liquid
capacity of 19 cubic meters"*. But $\pi/4 \times 1.684^2 \times 1.950 = 4.343$ m³ — the two figures in
one sentence differ by 4.4×. The engine's own `R328_D001_M_DES` is 10 554 kg ≈ 10.6 m³, matching
neither and standing at **243 % of the computed shell**. On the computed volume $V_v$ would sit on
its 2 % floor and $K$ would be ≈ 17.8 bar/(kg/s), **355×** the present constant and far outside the
unit circle at a 0.25 s tick. It keeps `R328_D001_P_KP` until the real dimensions are established.

(328C003 was the other exclusion here. Its open-loop gain has since been measured and it is now
wired — see *Phase 2 remainder* below.) The exclusion is pinned by a test, so a later edit cannot
quietly "finish the job".

### Phase 2 remainder: the last four vessels, the 328 bottoms, the steam headers and the delays

The four vessels that could be closed on sourced geometry are closed. Two remain on the lumped
constant and both are blocked on a specific missing number, recorded below rather than estimated.

| vessel | $V_{shell}$ m³ | $V_{liq}$ m³ | $V_v$ m³ | $\bar M$ | $T$ °C | $K_{new}$ bar/(kg/s) | vs. shared |
|---|---|---|---|---|---|---|---|
| 322C001 LP absorber | 3.2659 | 1.3854 | 1.8805 | 27.51 | 43 | 0.50810 | **25.4×** 0.02 |
| 323E011 + 323D011 | 4.3751 | 1.2353 | 3.1398 | 17.40 | 45 | 0.48433 | **9.7×** 0.05 |
| 328C003 hydrolyser | 62.2680 | 37.4926 | 24.7755 | 21.37 | 200 | 0.07431 | **3.72×** 0.02 |
| 324F003 separator II | 7.4270 | 3.1122 | 4.3148 | 28.96 | 140 | 0.27486 | **13.7×** 0.02 |

$ar M$ is the seed value of whatever the site actually uses — the live vent vector at 322C001 and
the live `y_748` at 328C003, the sourced stream composition at the other two.

The spread is the finding. One coefficient was carrying a 3.27 m³ absorber and a 62 m³ hydrolyser,
and the correct values differ between them by a factor of seven — in the opposite direction to the
volumes, because the hydrolyser is 60 % liquid-full while the absorber's vent is nearly pure air.

#### 322C001: the holdup did not fit the vessel

The datasheet gives a **stepped** column — upper part 576 mm ID over 1900 mm, lower part 922 mm ID
over 4150 mm — so the two sections are summed, not averaged; the narrower top exists to accelerate
the gas through the steam-condensate polishing bed.

A-6 could not be written at all until an engine constant moved. `A328_C001_M_DES` was
`M756_DES/3600 × 600 s`, an *indicative* residence time. At the PFD stream-755 density that is
**5.53 m³ of liquid inside a 3.27 m³ vessel — 169 % of the shell containing it**, so
$V_v = V_{shell} - M_l/\rho_l$ is negative and lands on its 2 % floor, returning a coefficient 683×
the constant it was replacing.

The holdup is now geometric: half the lower cylindrical section, which is where LT-322502 measures
across the N9A/N9B pad flanges and where the datasheet describes the loop as holding "a steady 50
percent holdup in the sump". That is 1392.3 kg and an **emergent** 150.3 s residence — four times
shorter, and the honest number for a 922 mm column passing 33.4 t/h. The design pin is untouched by
construction (LI-322502 is $M/M_{des}\times 50$ and the state seeds at $M_{des}$). What changes is
the level *rate*, four times faster, because the old constant made this column four times more
sluggish than the steel allows. LIC-322502 (Kc 1.0, Ti 100 s) was re-measured against the new gain
and holds: over a 6000 s settle LI-322502 moves 2×10⁻⁶ %, and PT-322201 stays inside
3.89984–3.90002 bar a.

The vent MW is the **live** vector, not a frozen mean — 27.51 at the seed against the datasheet's
29.45 design emission figure, the difference being that the engine tracks N₂/O₂/CH₄/H₂ where the
datasheet counts argon. On an HP-scrubber cooling failure this vent stops being air altogether and
becomes NH₃/CO₂, and the moles a kilogram of it carries nearly double.

#### 323E011 and 323D011 are one gas envelope

323E011 discharges its condensate by gravity through the DN 100 N2 nozzle straight into 323D011
mounted directly beneath it, with no valve between — so the two vapour spaces are one envelope at
one pressure. This is the same topology finding that closed the PT-323201 node, and the engine
already half-assumed it: `s.r3232_e011_M` holds the **drum** inventory while `s.r3232_e011_P` is the
shared pressure.

The condenser's share is the shell bore **minus the bundle**: 382 tubes at 25 mm OD over a 5900 mm
effective length displace 1.106 m³ of a 2.966 m³ shell, 37 % of it. Ignoring the bundle would
overstate the free volume by 60 % and soften the node by the same factor. The seven 25 %-cut baffles
are thin plates and are not deducted.

Stream 702 is 89.4 wt% NH₃, giving $\bar M = 17.395$. That is what the shared coefficient could not
know: at 17.4 kg/kmol a kilogram of this vent carries 2.5× the moles — and 2.5× the pressure — of a
kilogram of the CO₂-rich vapour the same 0.05 was applied to elsewhere.

#### 328C003: the deferred one, now measured

328C002 and 328C004 self-regulate — their overheads rise with $\sqrt{\Delta P}$ against the next
node, so stiffening the capacitance only makes a stable first-order node faster. 328C003 does not.
Its overhead is PV-328203B, a pressure-**controlled** valve, so $d\dot m_{748}/dP$ through the
hydraulics is identically zero and the whole loop gain sits in PIC-328203. That is why it was held
back with an explicit "measure the open-loop gain first" note rather than wired with the other two.

Measured, it is **3.7×** — close to the 4.3× first estimated but for a different reason than
assumed: the hydrolyser is a liquid-filled column standing 12.55 m deep in a 20.85 m shell, so only
24.8 m³ of it is vapour, and its overhead is lighter than the pure hydrolysis gas (the seed `y_748`
is 70 mol% steam, $ar M$ 21.4, not the 26.0 of 2 NH₃ + CO₂ alone). A 6000 s settle
from the design seed leaves the node inside a decaying ±0.03 bar excursion about 16.80 bar a.
PIC-328203 at Kc 1.5 / Ti 50 s holds it, so **no retune was applied**.

#### 324F003 wired; 324F001 blocked on one number

324F003's OEM datasheet (UD-AU-324-EC-0008) gives 2500 mm OD and a 1550 mm cylindrical height. It
gives no wall, so the 15 mm of the same OEM series is used — 324F001 is quoted 4600 OD / 4570 ID in
its own datasheet. That is a stated assumption and a small one: taking the bore at the full OD
instead moves the shell volume by 2.4 %, well inside the level swell this term exists to capture.
Its ODE is solved *inside* the existing P/T Picard fixed point, so the 13.7× stiffer state is
marched implicitly and the ejector's own $p_2$-proportional pull closes the loop.

The vacuum ODE balances **non-condensables**, not boil-up: the condensables leave by condensing in
324E005, and PIC-324203's entire control mechanism is admitting atmospheric air through PV-324203 to
blanket that condenser. So the molecular weight on this balance is dry air, 28.9647.

**324F001 is not wired.** Everything else it needs is sourced — 4600 mm OD / 4570 mm ID, the melt
density, the full nozzle schedule — but no document in this repository states its **cylindrical
height**, and that is the only term A-6 needs. A 4570 mm bore admits anything from 2 to 10 m, i.e.
33 to 164 m³, so the coefficient is undetermined by a factor of five. Estimating it from the
21 500 kg delivery weight was tried and rejected: backing out the shell mass needs the
internals/skirt/nozzle share, which is the same guess wearing a different hat. Nor does the sibling
help — 324F003's 0.62 height/diameter ratio is a similarity argument, not a measurement. It keeps
the constant, the same standing 328D001 has.

### D-1: the three unit-328 bottoms valves

All three were `design × (op/op_des)` — a bare position gain with no ΔP term, no density and a linear
installed characteristic whatever the trim. LV-328504 is the clearest case: it lets a 200 °C liquid
down from 16.8 bar into a column whose pressure is now a live state, and the old form was blind to
it.

Each valve now takes $p_1$ from its own vessel: the live node pressure plus the hydrostatic head of
the liquid standing on the nozzle, $h = M_l/(\rho A_{col})$, so the head collapses as the column
empties. That is the same term that makes the empty-vessel guards of D-19 to D-21 unreachable.

| valve | $p_1$ bar a | $p_2$ bar a | $\Delta P$ | head | basis |
|---|---|---|---|---|---|
| LV-328503 | 24.4000 | 16.8000 | 7.6000 | 0.1269 bar over 1.387 m | 328P006 discharge |
| LV-328504 | 17.9185 | 3.7000 | 14.2185 | 1.1185 bar over 12.554 m | gravity letdown |
| LV-328505 | 3.8148 | 1.0000 | 2.8148 | 0.1148 bar over 1.268 m | 740 boundary |

**LV-328503 sits on a pump discharge**, so $p_1$ is not the column pressure, and the 328P006A/B
datasheet gives the whole hydraulic line: 4.7 bar a suction, 24.4 bar a discharge, 19.7 bar
differential, 215 m head, 52 m³/h rated. So
$p_1 = P_{c002} + \rho g(h_{level} + Z)/10^5 + \Delta P_{pump}$, with $Z$ back-solved to make the
design suction read the datasheet's 4.7 bar a **exactly**. It comes out 11.728 m — the fixed
elevation from the column bottom nozzle down to the pump centreline, which is separate from the
level and must not move with it. $\Delta P_{pump}$ is held at its rated value: the datasheet gives
one point on the curve and no curve shape, so a head-versus-flow law here would be invented.

**No vapour pressure is passed to any of the three**, and that is deliberate rather than an
omission. All three carry liquor sitting at its own bubble point in the vessel above, so the
physically correct $P_v$ is the vessel pressure itself — and feeding that to the single-phase choked
limit collapses $\Delta P_{eff}$ to $F_L^2(1-F_F)p_1$, about 4 % of $p_1$, turning every one of them
into a hard-choked orifice. These are **flashing** services; sizing them properly needs the IEC
60534 two-phase method, which this repository does not have. With $P_v = 0$ the $F_L^2 p_1$ ceiling
still applies the right qualitative limit without pretending to a two-phase capacity the model
cannot compute. Left as a stated gap.

Installed characteristic is **linear**, the same choice and the same reason as `R323_LV_CHAR`: no
control-valve datasheets exist for these three, and linear reproduces the gain basis
LIC-328503/504/505 were tuned against. This change delivers the terms that were *missing*; switching
to equal-% is a retune, not a drop-in.

### D-2: four of the eight steam-header valves were choked all along

`steam_system._valve_flow` was the incompressible orifice law, which is wrong on saturated steam and
wrong in a way that matters here. At their own design node pressures, against a critical
$F_\gamma x_T = 0.6964$:

| valve | $P_1 \to P_2$ bar a | $x = \Delta P/P_1$ | |
|---|---|---|---|
| PV-329204 | 25.00 → 19.70 | 0.2120 | sub-critical |
| **HV-329601** | 19.70 → 1.01 | **0.9486** | **choked** |
| PV-329205A | 25.00 → 9.00 | 0.6400 | sub-critical |
| PV-329205B | 9.00 → 5.01 | 0.4430 | sub-critical |
| **PV-329207A** | 5.01 → 1.01 | **0.7979** | **choked** |
| PV-329207B | 5.01 → 3.90 | 0.2221 | sub-critical |
| **PV-329207C** | 25.00 → 5.01 | **0.7995** | **choked** |
| **HV-329602** | 25.00 → 5.01 | **0.7995** | **choked** |

Under $\sqrt{\Delta P}$ the flow through all four kept climbing as the downstream pressure fell,
without limit. A choked valve passes a flow that is a function of **upstream conditions only**. The
law is now

$$\dot m = K\cdot\frac{op}{100}\sqrt{\Delta P_{des}}\cdot\frac{\Phi_{gas}(\text{live})}{\Phi_{gas}(\text{design})},\qquad
\Phi_{gas}=P_1 Y\sqrt{\frac{xM}{T_1 Z}},\quad x=\min\!\left(\frac{\Delta P}{P_1}, F_\gamma x_T\right)$$

with $T_1$ the **live** saturation temperature of the upstream header, from the same IF97 boundary
`main.tsat_steam` uses. Anchoring rather than back-solving a $C_v$ keeps every $K$ seeding in the
module untouched: at the design node pressures the bracket is the same expression on the same
operands, exactly 1.0, so the law returns $K(op/100)\sqrt{\Delta P_{des}}$ for **any** opening — the
identical value the incompressible form returned there. Verified bit-exact at 0, 17.3, 50 and 100 %
stroke on all six anchored valves.

`core/valve.py:Valve322604` — the Sequential-Modular port of `main.hv_322604` — had been left behind
when that function moved onto the ISA law in the HV-322604 pass. It still carried
`_eq_pct(θ) × √(ΔP/ΔP_des)` on a service running at a pressure ratio of 0.028, and
`_eq_pct(0, 50) = 50^{-0.5} = 0.1414`, so a HIC-322604 commanded fully **shut** still passed 14 % of
the design off-gas — about 835 kg/h of NH₃/CO₂ out of a 140.7 bar loop the operator believes is
isolated. Both ports now call the same anchored law on the same anchors, so the SM flowsheet and the
tick engine cannot disagree about this valve again.

### D-8: transport delays that move with flow

Three fixed FIFOs remained: `FEED_TD_S` = 345 s on the CO₂ and NH₃ feed tears, and 60 s on the
322E001 bottoms.

The 345 s is a **measurement** and it stays exactly where it is — the PT-329201 FOPTD fit from the
03-06-2025 DCS anchor set (R² = 0.9888, bracketed ≤ 572 s). What was wrong is that it did not
*move*. A transport dead time is $t_d = \rho V_{line}/\dot m$, so at 50 % load it **doubles**, and
the fixed FIFO held it at 345 s from turndown to trip.

No nozzle table in this repository gives the battery-limit run lengths, so the line inventory is
back-solved from the measurement instead of the geometry, $M_{line} = \dot m_{des}t_{d,des}/3600$ —
the same anchored-departure form the valves use. Exact at the design flow by construction; if the
real line D and L ever turn up they replace the back-solve, and the design point is unchanged if
they agree with it.

| line | inventory | design $t_d$ | at 50 % flow |
|---|---|---|---|
| BL → loop, CO₂ | 5234.2 kg | 345 s | 690 s |
| BL → ejector, NH₃ | 4098.0 kg | 345 s | 690 s |
| 322E001 bottoms → LT-322501 | 1.9166 m³ (2174.7 kg) | 60 s | 120 s |

Capped at 3600 s so a dead feed gives a long-but-finite transit rather than an infinity.

Separately, `_transport_process` had been computing a full per-route diagnostic every tick and
dropping it into `s.tlag` where nothing could read it. It is now published on the tick packet as
`CONSEQUENCE_TRANSPORT`, which is what makes the plug-flow boundary auditable from telemetry: a
departure and an arrival differing on the same tick is the direct evidence that properties are no
longer teleporting across an equipment boundary.

### D-19 / D-20 / D-21: one deleted, one restored, two kept

The reports argue that an empty-vessel limiter becomes unreachable once the discharge is driven by
head. That is true for a **gravity** drain and false for a pressure letdown, so each of the four
sites was checked for which kind it is.

* **HPCC level (deleted).** Provably dead code, not merely redundant. The outflow is
  $\varphi_{fwd}(L/NLL)$, so at $L = 0$ it is identically 0.0, and the guard's second condition asked
  whether $0.0 > \varphi_{in}$ for a $\varphi_{in}$ that is a ratio of two non-negative liquid makes.
  The branch was unreachable on every path.
* **322F001 ejector suction (restored).** Not a guard — a *dropped* term. `m_suc = capacity`
  discarded the gravity-head multiplier the block comment directly above it specifies, leaving the
  322E003 sump a pure integrator: shutting XV-322903 flooded it correctly (50.0 → 62.5 % in 60 s) but
  re-opening restored design entrainment only, so the level held wherever it got to and never came
  back. With the head term restored the sump is a self-regulating attractor again, settling at
  $L_{eq} = NLL(\text{overflow}/\text{capacity})$. At design $L = NLL$, so the fraction is a literal
  1.0 and the fixed point does not move. `EJ_HYD_FRAC_MAX` — the throat-choke ceiling the same
  comment specifies and which had also never been applied — now caps a real flood at 1.25×, inactive
  at design.

  Measured against the -30 % CCW throttle in `test_3_scrubber_heat.py`, the difference is stark.
  Before, the sump drained 50.0 -> 27.2 % over the cut and then sat at 26.7 % **for ever**, with the
  entrainment frozen at its design 53 368 kg/h the whole time. Now it troughs at 45.5 %, because the
  falling head throttles the entrainment (53 368 -> 48 432 kg/h) and the shortfall is self-limiting,
  and it recovers to 49.9 % within about 1400 s of the CCW being restored.

  **This corrected one test by breaking another, and the second was passing on the strength of the
  defect.** `test_3_scrubber_heat.py` asserted that PT-329201 relaxes by at least 0.15 bar within
  1000 s of CCW restoration. That relaxation had been powered by the sump dumping 23 % of its
  inventory into the synthesis loop during the cut; with the sump behaving, the CCW-attributable
  excursion is smaller -- correctly so -- and it no longer clears the harness's own numerical noise.
  That noise is documented and pre-existing: the `_systest` harness runs at $dt = 2.0$ s, where the
  design seed itself walks about +0.10 bar per 1000 s by the time the test reaches its relax window,
  and rising. The test was grading a raw pressure against a threshold smaller than the walk.

  It now grades PT-329201 against a **matched no-cut control trajectory of identical length**, so the
  walk cancels by construction and only the CCW effect survives. The relaxation is then perfectly
  visible -- the CCW-attributable excess falls from +0.400 bar at the end of the cut to +0.300 bar
  after the relax window -- and the sump's trough-and-recovery is asserted alongside it. Verified
  separately: the free $dt = 2.0$ s walk is unchanged by any of Phase 2's work, tracking the
  pre-change baseline within 0.03 bar over 4600 s (140.7125 vs 140.7118 at 1000 s; 141.1102 vs
  141.1271 at 4400 s).
* **Stripper drain and 323C003 (kept).** LV-322501 is a 140.7 → 4.0 bar letdown and LV-323501 a
  4.1 → 1.13 bar letdown. Neither ΔP vanishes when the vessel empties. What happens on the plant is
  that the valve starts passing vapour instead of liquid, and this engine has no two-phase valve
  model; deleting either guard drains its vessel below empty at full letdown rate. Keeping them is
  the honest floor until that model exists.

### What is still open after this pass

* **324F001's cylindrical height** and **328D001's volume** — the two A-6 vessels still on the lumped
  constant. The first is a missing number, the second a source conflict (the datasheet says ID
  1684 mm × T/T 1950 mm and calls it 19 m³; the cylinder is 4.343 m³, and the engine's own design
  holdup matches neither at 243 % of the computed shell).
* **A-7, the 323F004 pressure state.** Unchanged and still blocked on data: the design ΔP across the
  F004 → 323E011 line is identically zero in the model, and the PFD rounding is the same order as the
  ΔP itself.
* **323F010's barometric leg**, still `M317_DES·√(M/M_DES)` — head-driven in form but with no vessel
  pressure term, so a vacuum break would not change the drain rate. Needs the leg height.
* **The 328 bottoms valves are flashing services on a single-phase law.** See D-1 above.
* **D-12, `pull_f010`** — a machine map, and Phase 4's.

## Melt-Temperature Integration in Unit 324: Why an Empty Evaporator Killed the Engine

Both 324 stages advanced their melt temperature with an explicit Euler step over the liquid
inventory alone:

$$T' = T + \frac{\dot P\,\Delta t}{\max(M\,c_p,\ 10^{-6})}$$

The floor is the defect. It exists to stop a division by zero, but what it actually does is convert
a drained stage into an amplifier of gain $10^{6}$. The failure is not subtle:

* a CCW loss trips the plant and the feed is cut;
* 324F001 drains, so $M \to$ its floor;
* one tick with the chest still above the melt temperature puts $Q\,\Delta t/10^{-6}$ into the step
  and throws $T$ past $10^{10}$;
* from there the sensible term $-\dot m\,c_{p,f}\,T$ dominates, alternates sign and **doubles every
  tick** — the textbook explicit-Euler instability at $|1 - \lambda \Delta t| \gg 1$;
* about 340 doublings later `cp_water_kjkgk` evaluates $T^3$ on a number above $5.6\times10^{102}$
  and the tick dies with `OverflowError: Result too large`.

An `OverflowError` inside a heat-capacity correlation looks like a property-range problem and is
not one. Clamping `cp_water_kjkgk` would have hidden a diverging state behind a plausible-looking
number, which is worse than the crash — the trainee would see a running plant with a fictional
evaporator.

### The fix is a better integration scheme, not a limiter

The terms that make this ODE stiff are the ones that depend on the temperature being solved for:
the feed sensible term, and the chest duty while it is still driving heat in. Treat those
implicitly. Backward Euler on them, rearranged so the increment keeps its explicit numerator:

$$\frac{M c_p}{\Delta t}(T' - T) = \dot P(T) - k_{cap}(T' - T)
\qquad\Longrightarrow\qquad
T' = T + \frac{\dot P\,\Delta t}{M c_p + k_{cap}\,\Delta t}$$

$$k_{cap} = \frac{\dot m_{feed}}{3600}c_{p,feed} + \begin{cases} UA & Q > 0\\ 0 & Q = 0\end{cases}$$

Three properties make this the right answer rather than a patch:

* **Unconditionally stable** in both stiff terms. The amplification factor is
  $Mc_p/(Mc_p + k_{cap}\Delta t) \in (0, 1]$ for any $\Delta t$, so the oscillation cannot grow.
* **Correct in the limit it used to break.** As $M \to 0$ the step becomes
  $T' \to T + \dot P/k_{cap}$, which is the algebraic solution — a vessel with no thermal inertia
  whose outlet simply follows its inlet. That *is* the physics of an empty evaporator; the old form
  asserted the opposite, that a vessel holding nothing could still integrate heat.
* **Bit-exact at the design seed.** $\dot P$ is identically zero there by construction (the UA and
  $\lambda$ anchors are back-solved for it), so $T' = T + 0$ regardless of the denominator. The
  boot pin cannot move. This is why the increment form is used instead of the algebraically
  equivalent $(Mc_pT/\Delta t + k_{cap}T_f + Q)/(Mc_p/\Delta t + k_{cap})$, which is correct in
  exact arithmetic but relies on a cancellation that floating point does not deliver.

The `max(..., 1e-6)` stays, but it is no longer load-bearing: the denominator is now bounded away
from zero by the flow term whenever anything is moving, and the only state that still reaches the
floor — no inventory and no flow — has $\dot P = 0$ as well.

### The same shape exists at nine more integrators

`grep` finds eleven `dt / max(M*cp, 1e-6)` steps in `main.py`. The two 324 stages are fixed here
because they are where the crash was demonstrated; **323C003, 323F004, 323F010, 323D002, 328D003
(both compartments), 328C003, 328D001 and 322C001 carry the identical construct** and the identical
latent instability, reachable by whatever upset drains each of them. The transformation is the same
one line and the same bit-exactness argument at each; what differs per vessel is only the
heat-capacity rate that goes into $k_{cap}$. Listed in the handoff rather than swept, because each
site's flow terms need reading before its denominator is changed.

## 322R001 Reactor Kinetics: Rate Laws, Not Load Multipliers (`backend/reactor.py`)

Phase 3, report findings C-1 and C-2. **All of Phase 3 is now done: C-1, C-2, A-8, C-3, C-4; C-5 was found already conforming.**

### What this replaced

```python
xi_urea = REACT_XI_UREA_DES * s * conversion_factor(L, W, T)     # design extent x load x correlation
xi_biu  = REACT_XI_BIU_DES  * s                                  # design extent x load
```

`conversion_factor` is a separable correlation renormalised to return exactly 1.0 at design, so the
urea extent was independent of residence time, of holdup volume, and of concentration except through
two feed **ratios**. Biuret — the plant's principal product-quality specification — had a temperature
derivative of exactly zero, so a hot reactor could not produce a quality excursion at all.

### The mechanism

Two steps, the second rate-controlling. Step 1 is taken as fast in the liquid, which is the standard
assumption at 140 bar a and N/C ≈ 3, so the CO₂ the axial march carries **is** the carbamate:

$$r_2=k_2(T)\left(C_{carb}-\frac{C_{urea}C_{H_2O}}{K_{ov}(T)\,C_{NH_3}^2}\right),\qquad
k_2=A_2\exp\!\left(\frac{-E_{a,2}}{RT}\right)$$

marched node by node up the column, $dN_i/dz=\nu_i r_2 A_{cs}$, with each node's own temperature and
its own residence time $\tau_n = V_{wetted,n}/\dot V$ from the **live level and live throughput**.

Within a node the rate is linear in its own driving force, so the integration is exact rather than
$r_2 V_n$:  $\xi_n=\xi_{eq,n}\left(1-e^{-k_2\tau_n}\right)$. This matters — multiplying the rate by the
node volume let a large $k_2$ overshoot equilibrium inside one node and reverse in the next, which
made the extent non-monotone in $A_2$ and left the design back-solve with nothing to converge on.

### Which equilibrium constrains it — this was got wrong once

The rate-controlling step is dehydration, which is **endothermic** (+15.5 kJ/mol), so its own
equilibrium constant *rises* with temperature. Constraining the march with that alone gave X = 0.92
at 200 °C and **X = 1.00 at 230 °C**: the model taught that a hotter reactor converts more, which is
the opposite of the truth and actively dangerous in a training simulator.

The reaction conversion is actually limited by is the **overall** one,

$$2\,\mathrm{NH_3}+\mathrm{CO_2}\rightleftharpoons\mathrm{NH_2CONH_2}+\mathrm{H_2O},\qquad
\Delta H=-117+15.5=-101.5\ \text{kJ/mol}$$

which is **exothermic** — the same −101.5 the desorption section already carries as
`R328_HYD_DH_KJMOL` for the reverse direction. Its equilibrium conversion therefore falls with
temperature, and that against a rate constant that rises with temperature is what produces a
conversion optimum. The optimum now **emerges at ≈ 200 °C**; nothing in the code names a peak
temperature, where the old model fitted one as `exp[-k((T-Topt)² - (T0-Topt)²)]`.

### Provenance: two back-solved numbers, everything else sourced

No vendor kinetics exist for this reactor and one design point determines one parameter, so `A2` and
`Keq_ov_ref` are back-solved — the same treatment the Phase 2 valve coefficients got, for the same
reason. `Keq_ov_ref` is anchored so the equilibrium conversion at design is `X_INF`, the
plant-anchored ceiling the module already carried.

The activation energy is **derived, not asserted**. Inoue & Otsuka (1973) Eq. (6) gives urea
hydrolysis as $\ln k = 21.8 - 11100/T$, i.e. $R\times 11100 = 92.3$ kJ/mol for the rate-controlling
**reverse** step. For one elementary step run both ways the activation energies differ by the step
enthalpy, and the Helwan dehydration enthalpy is +15.5 kJ/mol, so

$$E_{a}(\text{carbamate}\to\text{urea}+\mathrm{H_2O}) = 92.3+15.5 = 107.8\ \text{kJ/mol}$$

Both numbers already carry citations elsewhere in this repo (`R328_HYD_K_B_K`, `STRIP_DH_HYD_JMOL`).
Biuret uses `STRIP_BIU_EA` = 85 kJ/mol, the value the stripper already uses, with
$r_{biu}=A e^{-E_a/RT}C_{urea}^2$ integrated over the wetted volume. The measured $A_2 = 3.8\times10^{12}$ /h
is an ordinary liquid-phase pre-exponential for that activation energy, and $k_2 = 1.39$ /h at design
gives a Damköhler of order 1 at τ = 35.9 min — right for a reactor at 55 % conversion.

### Activity basis — stated, not hidden

The brief asks for $a_i=\gamma_i x_i$ from the Phase 1 VLE service. **That service refuses here, and
correctly**: G-VLE-3 measured the HP loop at 54× outside the Extended UNIQUAC loading grid, so asking
it for γ at 183 °C and 140 bar a would return a clamped edge lookup dressed as an activity. The rate
law therefore uses concentrations (γ = 1) and says so. That is a real limitation and the right place
for an HP activity package when one exists — but it does not weaken what C-1 was about: temperature,
concentration, holdup volume and residence time now drive the extent, where previously none did.

### Anchoring: the calibration lives in the boot pin

The kinetic extent depends on the feed **absolutely**, where the old correlation depended only on its
ratios. Calibrating on the synthetic `_HPCC_DES` feed therefore put **2.5 % more urea** through the
reactor than the PFD allows (`REACT_X_DES` pinned at 0.5567 against the as-built 0.543). `A2` and the
biuret pre-exponential are now re-solved inside the boot pin against the **live settled** feed, node
temperatures, level and throughput, and `REACT_KIN_ANCHOR` stores that state so
`react_322r001(design_feed)` with no extra arguments still reproduces the design extent — the
identity contract `test_reactor.py` asserts. Both are carried in the pin cache, or a warm boot would
silently run the import-time calibration.

`REACT_TEAR_DES` is built from the **recalibrated** extents (the PFD values, guaranteed by the
calibration) rather than the captured pre-recalibration ones; using the captured values left the
design overflow 1.6–3.4 kmol/h off its published vector even though the extents were exact.

### Measured

Design point: ξ_urea and ξ_biu reproduce the PFD to 3.6e-12 and 0.0; worst overflow and off-gas
deviation 3.6e-12 against the 1e-6 identity tolerance; conv_fac 0.9999996, TT-322014 182.99999996.

What the multiplier could not represent, all now measured:

| response | result |
|---|---|
| residence time | ξ 1754 → 1071 kmol/h as τ goes 59.8 → 27.6 min |
| holdup volume | ξ rises monotonically with level 40 → 100 % |
| turndown | per-pass conversion 0.556 → 0.674 at 70 % load |
| temperature optimum | emerges at ≈ 200 °C, falls either side |
| biuret vs temperature | was **bit-flat** over 2 h; now ×1.5+ per 17 °C |
| biuret at turndown | 2.414 → 3.12 kmol/h — quality gets **worse**, a scenario the model could not teach |
| AT-322701 N/C | 3.000 → 2.968 at 70 % load |

The slow level and synthesis-pressure drift over 2 h is **pre-existing and unchanged** (level 80.21 %
baseline vs 80.20 % here). ξ_urea drifts more than baseline (+0.27 % vs +0.073 %) precisely because
it now follows the level and temperature that are drifting instead of ignoring them.

### Test assertions rewritten, and why

Four assertions in `test_reactor.py` encoded the defect and had to change. A stashed baseline
confirmed the file was **14 passed / 0 failed** beforehand, so these are consequences of this work
and not pre-existing rot:

* `xi_urea` and `xi_biu` scaling **exactly linearly** with load to 1e-6 — that is `xi = XI_DES * s`
  asserted as a contract. Now: extent falls with load but **sublinearly**, and conversion rises.
* overflow and off-gas NH₃ scaling linearly — both now fall **below** linear at turndown, because the
  higher conversion consumes more ammonia (overflow −6.0 %, off-gas −7.5 % at 80 % load).
* overflow N/C **invariant** to throughput scaling to 1e-6 — it now falls 3.000 → 2.968 at 70 % load,
  a real AT-322701 behaviour.

## 322E001 Stripper Reactions: Inoue-Otsuka, and Why the Extent Stays Anchored

Phase 3, report findings C-3 and C-4.

### What this replaced

```python
xi_hyd_raw = STRIP_XI_HYD_DES * eta_T                       # eta_T = eta_steam . g_NC . g_HC . g_T
xi_biu_raw = STRIP_XI_BIU_DES * exp(Ea/R (1/T_des - 1/T)) * (Urea/UREA0)   # FIRST order, no holdup
```

`eta_T` is a product of a steam-temperature ratio and two fabricated penalties on the reactor-feed
N/C and H/C ratios (`STRIP_ETA_KN = 1.50`, `STRIP_ETA_KW = 1.50`, both dimensionless slopes with no
provenance). It contains **no rate constant, no residence time, and no water concentration** — and
water is the other reactant. Biuret carried the right Arrhenius form but was **first** order in urea
where `2 Urea -> Biuret + NH3` is second, and had no holdup term at all.

### The measurement that decided the form

`urea_hydrolysis_k_m3_kmol_h` is Inoue & Otsuka (1973) Eq. (6), $\ln k = 21.8 - 11100/T$ — the same
law 328C003 already runs on. Evaluated at the stripper's **own** design state it cannot reach
`STRIP_XI_HYD_DES`, and not marginally:

| | |
|---|---|
| tube bundle, from the DDS lines | 7.658 m³ |
| feed 283.7 m³/h -> full-bore residence | 97.2 s (a falling *film* is less) |
| k(172 °C) | 0.043482 m³/(kmol·h) |
| C_urea, C_H₂O | 4.592, 7.860 kmol/m³ |
| ξ over the **whole bundle flooded** | 12.02 kmol/h |
| ξ over bundle **+ sump, both flooded** | 17.48 kmol/h |
| `STRIP_XI_HYD_DES` | **88.10 kmol/h** |

It needs a liquid fraction of **7.33** where the physical maximum is 1, and the entire vessel full of
liquid still delivers a fifth of it. Independently: 88.1 / 1302.6 is **6.8 % of the urea feed
destroyed in 97 seconds**, where a real CO₂ stripper loses well under 1 %.

So `STRIP_XI_HYD_DES` is **not urea hydrolysis alone**. It almost certainly lumps carbamate
decomposition, which is what the stripper is actually for. Predicting it from a hydrolysis rate law
would mean fitting a rate constant to a quantity that is not that reaction — a heuristic wearing a
citation. The PFD extent therefore stays the anchor (CLAUDE.md strict source) and Inoue-Otsuka
supplies the **departure**:

$$\xi_{hyd}=\xi_{hyd,des}\cdot\frac{k(T)\,C_{urea}C_{H_2O}V_{liq}}{\left[k(T)\,C_{urea}C_{H_2O}V_{liq}\right]_{des}},
\qquad V_{liq}=V_{tubes}+V_{sump}\cdot\frac{L}{100}$$

with $C_i = \dot n_i/\dot V$ from the live feed and the live volumetric flow. The departure is the
part `eta_T` was getting wrong; the anchor was never in dispute.

Biuret takes the same volume and the same live throughput, second order:

$$\xi_{biu}=\xi_{biu,des}\,e^{\frac{E_a}{R}\left(\frac{1}{T_{des}}-\frac{1}{T}\right)}
\left(\frac{C_{urea}}{C_{urea,des}}\right)^{2}\frac{V_{liq}}{V_{liq,des}}$$

`V_tubes` = 7.658 m³ from the tube count, bore and effective length already quoted above;
`V_sump` = 6.957 m³ from `STRIP_SUMP_AREA_M2 x STRIP_LEVEL_SPAN_M`, i.e. 0 -> 100 % of LT-322501.

### Measured

Design point exact — ξ_hyd = 88.100000000, ξ_biu = 0.667000000 — and the engine holds p_syn 140.7000,
T_ovf 183.0000, level 80.0000, T_f010 99.0000.

What `eta_T` could not represent:

| response | before | after |
|---|---|---|
| steam temperature | ratio penalties, no rate constant | ξ_hyd 55.4 -> 177.5 over T_steam 200 -> 230 °C (T_bot 163.9 -> 184.9 °C) |
| sump holdup | **no term at all** | ξ_hyd 71.6 -> 115.6 over level 20 -> 100 % |
| water concentration | absent | second order, C_urea·C_H₂O |
| biuret order in urea | **first** | **second** — 2 Urea -> Biuret + NH3 |
| biuret holdup | absent | ξ_biu 0.542 -> 0.875 over level 20 -> 100 % |

The flooded-tube argument the split logic already carried is now represented rather than asserted:
Brouwer's "stagnation or upward dragging of the film" raises residence time, and `V_liq` tracking the
live level is what makes hydrolysis and biuret rise under flooding instead of merely being described
as doing so.

`eta_T` survives as a **reported** strip-efficiency diagnostic on the tick packet. It drives no
extent; the split fractions use `eta_T_steam . eta_co2 . eta_P . min(g_T,1) . g_flood`, which is a
separate quantity and out of C-3's scope.

### One test assertion rewritten, and why

`test_biuret_is_limited_by_urea_remaining_after_hydrolysis` asserted `xi_hyd == 92.505` on a feed of
`Urea = 92.51, H2O = 200.0`. That number was not an invariant: it is `88.1 x eta_T` with
`eta_T = 1.0500`, landing 0.005 below the feed urea by coincidence, and the test then checked the
urea clamp. Under a rate law that feed is simply urea-limited, so the assertion stopped exercising
the clamp it exists for. The feed moved to `Urea = 200.5, H2O = 200.0`, where the test asserts
`xi_hyd == 200.0` (**water**-limited — a bound `eta_T` never had) and `xi_biu == 0.25`, i.e. half the
0.5 kmol/h of urea left standing. The invariant is preserved; the number was not re-tuned to match.

## 322R001 Column Energy Balance: Real Enthalpies, and the Profile the Plant Actually Has

Phase 3, report finding A-8.

### What this replaced

```python
dT_col = REACT_DT_COL_DES * conv_fac                  # 13.0 C PRESCRIBED, scaled by conversion
dT_n   = REACT_G_NODES[n] * dT_col                    # fitted Damkohler shape, beta fitted too
```

No energy anywhere in it, and the **sign was wrong**: a reactor making twice the urea got twice the
temperature rise, when dehydration is endothermic and more urea means *less* net heat. The axial
shape `g_n = G(zeta_n) - G(zeta_{n-1})`, `G = 1 - exp(-beta.zeta)`, came from an exponential probe
correlation — a fit to a fit, never checked against a measurement.

### It was checkable all along, and it was wrong

`References/Urea_NormalOp_29-06-2025_Trends.md` holds 1921 DCS samples of the four reactor
thermowells. Against them the fitted shape is **6.5 °C out at TT-322007**: it puts nearly the whole
column rise below the second thermowell, where the real profile is very nearly linear.

### The balance

$$\rho_n V_n c_p \frac{dT_n}{dt}= \dot m c_p (T_{n-1}-T_n) + Q_n - U_nA_n(T_n-T_\infty),
\qquad Q_n = \xi_{carb,n}\cdot 117\,000 - \xi_{dehyd,n}\cdot 15\,500\ \ [\text{kJ/h}]$$

Dividing by $\dot m c_p$ and writing $\tau_n=\rho_nV_n/\dot m$ leaves the integrator's RHS in the
same form it already had — what changed is that the second term is energy, and the two contributions
**oppose**.

**ξ_carb is a stream balance, not a second kinetic model.** The free CO₂ the HPCC hands over as gas
(476.99 kmol/h) minus the CO₂ leaving in the published off-gas vector (197.69) is, by definition,
what formed carbamate in this vessel: **279.30 kmol/h**. Taking it from the streams keeps it
consistent with the off-gas split instead of letting two mechanisms disagree about one quantity.

**The axial distribution is the licensor's own mechanism.** `References/322R001 Description.md` §4:
the endothermic reaction locally cools the liquid, which "induces further physical absorption and
condensation of these gases from the bubbles ... maintaining a steady, slightly rising temperature
profile". That is distributed gas-liquid transfer up the whole column — the $J_ia_iA$ term of the
profile equation the same document quotes — not a bottom-loaded exotherm. For a bubbling column the
interfacial area per unit liquid volume is uniform, so the release is proportional to each node's
**liquid volume**: no fitted shape parameter at all, where the Damköhler form needed β.

**The two routes agree independently.** Working backwards from the measured profile, the carbamate
needed per node sums to 278.3 kmol/h. The stream balance gives 279.30. Two unrelated derivations,
0.4 % apart.

### Measured against the plant

| | TT-322008 | TT-322007 | TT-322006 | TT-322005 | RMS |
|---|---|---|---|---|---|
| plant, 1921 DCS samples | 171.134 | 174.303 | 179.697 | 183.084 | — |
| **A-8 energy balance** | **170.716** | **174.812** | **179.147** | **183.000** | **0.431 °C** |
| retired Damköhler fit | 172.613 | 180.791 | 182.530 | 182.900 | 3.661 °C |

Design seed exact on both PFD anchors: ξ_urea = 1302.270000943 (rel. 7e-10), ξ_biu = 2.414000000,
conv_fac = 1.000000001, T_overflow = 183.000017.

A one-parameter first-order absorption march was also tried and reaches RMS 0.373 °C, but its node
shares land within 3 % of the volume-proportional ones. 0.06 °C of RMS does not buy a fitted
constant.

### c_p is fixed by the PFD rise — and is not a free parameter

The repository has no heat capacity for a 140 bar a ammoniacal melt; `urea_soln_cp` is anchored on an
**aqueous** 323-section value and gives 3.6096 kJ/(kg·K), which lands the rise at 15.30 °C against
the PFD's 13.0. `REACT_CP_MELT` = 4.2487 kJ/(kg·K) is ordinary for a melt ~29 % ammonia by mass
(liquid NH₃ alone exceeds 5). It does not fight the other anchors: once A2 is calibrated so the
extent is the PFD's 1302.27, Q_total is determined by the two anchored extents and
$c_p=Q/(\dot m\,\Delta T)$ closes on itself — the joint solve converges straight back to it.

The alternatives were rejected on evidence: a wall-loss $U$ closing the same gap implies
18 W/(m²·K) on an insulated HP shell, and an effective desorption enthalpy would be a fudge on a
stream that mostly arrives already gaseous.

### Closing the loop needed a joint solve, and needed one operating point

The reactor temperature is no longer imposed — it has to *find* 183 °C — so the profile and the
dehydration pre-exponential are solved **together** against the two plant anchors
(`reactor.thermal_kinetic_fixed_point`). A2 had been back-solved at the retired Damköhler seed, which
is a different set of temperatures from the ones the energy balance runs at; left alone it settled
the column at 184.42 °C and 1236 kmol/h.

Two live calibration references were tried and both are the wrong operating point, which is worth
recording so they are not tried again:

* the **phase-1 settle** is the CAS warm-up attractor — its carbamate balance reads 253 kmol/h
  against the 279 the MAN runtime produces; c_p came out 3.20 and the column ran to 184.3 °C;
* the **post-reset capture** is a single tick off the seed, i.e. the seed itself.

The design vectors are used instead: every input is source-anchored (`_HPCC_DES` gas CO₂,
`REACT_OFFGAS_DES` CO₂, `REACT_OVERFLOW_DES` mass).

**A density-basis defect surfaced here, introduced in C-1.** `_react_vdot_m3h` divides the design
overflow mass by the constant `REACT_OVERFLOW_RHO` (990.0); the live path divides by
`reactor.liquid_density(T_bulk)` (992.3 at 179.7 °C). Two "design" operating points 0.23 % apart,
with the direct call anchored to one and the live seed step to the other — so calibrating against
either broke the other's bit-exactness contract (overflow CO₂ 1.29 kmol/h off). `REACT_KIN_ANCHOR`
is now the seed step's own state, and the final calibration closes on the **contract itself**:
step the plant exactly as the test does and scale A2 until that step lands on the PFD extent, to
1e-14 relative. A 1e-9 stop was not enough — it left 1.3e-6 absolute, which failed a 1e-6 assertion
as the loop's own convergence noise.

### The honest caveat: the settled attractor drifts

The design **seed** is exact, but over 6000 s the settled overflow climbs 183.000 → 183.488
(+0.49 °C) with ξ_urea 1302 → 1316 (+1.05 %). The drift rate peaks near 5000 s and then falls, so it
appears to be converging near 183.6, but that was not run out far enough to prove.

This is a consequence of closing the loop, not a new fault. `p_syn` drifts to 140.209 (design 140.7)
and level to 79.90 over the same window, both **pre-existing and documented**. Previously the
reactor temperature was imposed, so that drift could not reach it; now temperature follows the
pressure and level that were already moving. Note also that the settled 183.488 sits close to the
plant's own TT-322014 mean of 183.556, while the PFD anchor is 183.0 — the two source documents
disagree by 0.56 °C, twice the residual.

### What the prescribed rise could not represent

| response | before | after |
|---|---|---|
| sign vs conversion | more urea → **hotter** | more urea → more endothermic drain → cooler, correctly |
| axial shape | one fitted β | two opposing profiles, neither fitted |
| carbamate supply | absent | HPCC gas split moves the column temperature |
| against plant data | RMS 3.661 °C | **RMS 0.431 °C** |

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
