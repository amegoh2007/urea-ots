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
* **D-12, `pull_f010`** — CLOSED in *Phase 5e*, and not as a machine map: 323F010's overhead is a
  valve into a condenser.

## Phase 4a: the CCW chain's design seed, and two of the three machines

### Part A — eight design-seed gaps that were one gap and a stale anchor

`test_ccw_loss_chain.py` recorded eight places where a term introduced by the CCW wiring was not
inert at the design seed: `cool_frac` reading 0.9951 instead of 1, 0.08 t/h of uncondensed off-gas,
5.2 kg of retained loop vapour, 0.1 % of level swell, an indication reading 50.0 % against a true
49.9 %, the composite "every new term stays zero for 6000 s" flag, `cool_frac` failing to reach
exactly 0 at total CCW loss, and the loop failing to hold 140.700 bar a over a 3000 s design run.

Measured at $t = 0$ every one of them is exactly zero. They are not seed leakage; they are what a
**drifting** seed does to terms that are correctly anchored. Two causes, and neither is a tolerance.

#### The condensation gate had the pressure dependence backwards

$$\rho_{cond} = \frac{\dot m_{CCW}}{\dot m_{CCW,des}}\cdot\frac{f_{th}}{s\cdot\nu},
\qquad \nu = \frac{P_{329201}}{P_{des}}$$

The $\nu$ divisor says a **higher** loop pressure makes the 322E003 shell a **weaker** condenser.
For a condensing service that is the wrong sign: raising the pressure raises the condensing
temperature and therefore the driving force $T_{cond} - T_{ccw}$. It also double-counted the
throughput demand, which $s$ (the CO₂ scale) already carries.

With the sign wrong, the term closed a positive-feedback loop around the loop's own settled-attractor
drift: $P \uparrow \Rightarrow \rho_{cond} \downarrow \Rightarrow$ off-gas goes uncondensed
$\Rightarrow$ the retained vapour pushes $P$ higher $\Rightarrow \rho_{cond}$ falls further. Six of
the eight gaps were that one loop, in series.

The fix puts the pressure where it belongs — in the condensing temperature — through
Clausius–Clapeyron on the carbamate-formation exotherm the model already carries
(`SCRUB_DH_CARB_KJMOL` = 160 kJ/mol):

$$\frac{1}{T_{cond}(P)} = \frac{1}{T_{des}} - \frac{R}{\Delta H_{carb}}\ln\!\frac{P}{P_{des}}$$

written as an increment on $T_{des}$ so that $P = P_{des}$ gives a literal $\ln(1) = 0$, an identical
reciprocal, and a bracket of exactly $0.0$. The slope at the anchor is
$RT^2/(\Delta H\,P) = 0.0754$ K/bar, so the 0.7 bar the loop wanders over 6000 s is worth +0.05 °C of
driving force — a $10^{-4}$ effect on $\rho_{cond}$, floored out by `SCRUB_COOL_FRAC_EPS`, against
the $-5\times10^{-3}$ the wrong-signed term was producing. And the sign is now stabilising.

The eighth-gap mirror image, `cool_frac` = 0.0033 rather than 0 at total CCW loss, was the same
term read off the wrong quantity: the capacity was taken from `FIC-329409["pv"]`, which is the
**transmitter** reading and carries a 25 s plant lag. The circulation itself stops with the pumps —
the 329P006 discharge check valves shut — so the capacity is now gated on `ccw_pump_frac`, a literal
1.0 at design. `cool_frac` reaches exactly 0.0000 on the first tick after both pumps stop.

#### A design anchor that was solved against a superseded profile

`REACT_NODE_SS_DES` is assigned three times: an import-time seed from `node_profile_ss`, the A-8
`thermal_kinetic_fixed_point`, and the boot-pin cache restore. The bulk-melt anchors derived from
it — `REACT_T_BULK_DES`, `REACT_RHO_BULK_DES`, `REACT_WEIR_CW` and `REACT_M_LIQ_DES` — were computed
once, against the **first** of the three, and never re-solved. They have to be defined there because
the weir geometry must exist before the A-8 point can be solved; nothing then went back.

So `State()` seeded `react_m_liq` = $\rho(T_{bulk,seed})\,A\,L_{des}$ while seeding `react_T_node`
from the *pinned* profile, and the two disagree by 0.9 °C of bulk temperature. On the first tick
`level_from_holdup` evaluated that holdup at the pinned temperature and the level **stepped**
−0.156 % of span. Not a drift — a one-tick reconciliation of two different design points.

Since Phase 3 the reactor runs on residence time, so the step went straight into $X_{conv}$
(−0.15 %) and from there into

$$\delta_X = \max\!\left(1 - \frac{X_{conv}}{X_{ref}},\ 0\right)$$

which is **one-sided**. A rectifier turns a zero-mean numerical wobble into a strictly non-negative
bias, and $\delta_X$ feeds TIC-329005's load term at a gain of 10 °C per unit — so the CCW supply
temperature could only ratchet one way. `_rederive_react_bulk_anchors()` re-solves the derived block
against whichever profile is current, on both the fresh-pin and cache-restore paths.

Result: at tick 1 `X_conv` equals `X_ref` to the last bit and $\delta_X$ is exactly 0; the reactor
level holds 79.999998 % and moves $6\times10^{-5}$ % over 40 ticks where it used to step 0.156 % in
one. The chain goes from **28/36 to 35/36**, with all five Phase-1b inertness checks and the Phase-2
total-loss check passing. The one that remains is the 3000 s design hold, and it improved 3.4×
(140.71826 → 140.70544 bar a against a 1e-3 tolerance).

### Part B, D-9 — SV-32201 on API 520 Part I

The synthesis-loop PSV was a linear over-pressure ramp,
`m_psv = CAP · min(over/accum, 1)`: zero at the set pressure, rated capacity at 10 % accumulation.
A spring relief valve does neither of those things. It is a fixed orifice with a **pop** action — it
passes nothing below set, pops at set, and from there passes a **choked** jet whose capacity is
linear in the *absolute* upstream pressure, not in the over-pressure.

API 520 Part I §5.6.3.1 in the USC form solves for the area,
$A = W\sqrt{TZ/M}\,/\,(C\,K_d K_b K_c P_1)$ with
$C = 520\sqrt{k\,(2/(k+1))^{(k+1)/(k-1)}}$. That $C$ is the isentropic choked mass-flux group
carried in USC units; `hydraulics.psv_api520_choked_kgh` evaluates the same equation in SI:

$$W = K_d K_b K_c\,A\,P_1 \sqrt{\frac{k M}{Z R T}\left(\frac{2}{k+1}\right)^{\frac{k+1}{k-1}}}$$

The orifice is **back-solved from the documented 200 t/h rating through the same function**, which
is the ISA-ratio methodology applied to a relief valve: every coefficient that does not move during
an event ($K_d$, $K_b$, $K_c$, $k$, $Z$) cancels, so the rated point is reproduced exactly whatever
is assumed for them, and only $P_1$, $M$ and $T$ change the answer. The area it returns on the
design relief composition (MW 27.48) is **2.558 in²** — 90 % of API letter orifice "L" (2.853 in²)
and 1.4× letter "K". An L-orifice valve carrying ~10 % sizing margin is exactly what a DN 100 relief
valve on this service is, and landing *between* two adjacent letter orifices rather than on a round
number is the check that the rating was documented rather than invented.

Lift is a discrete mechanical state with a 7 % blowdown (API 527, conventional spring valve): it
latches open on pop and relatches shut only below $0.93 \times$ set, so a loop parked at the set
pressure chatters the way the real valve does instead of settling into a throttled equilibrium.

**Capacity against the ramp it replaces**, at the loop conditions the chain actually reaches:

| $P_1$ (bar a) | accumulation | old linear ramp | API 520 choked | ratio |
|---|---|---|---|---|
| 161.01 (set) | 0 % | **0 t/h** | 181.8 t/h | — |
| 165.0 | 2.5 % | 49.5 t/h | 186.3 t/h | 3.76× |
| 168.84 (chain Phase 4) | 4.9 % | 97.2 t/h | **190.7 t/h** | **1.96×** |
| 177.11 (rated) | 10 % | 200.0 t/h | 200.0 t/h | 1.00× |

The two ends are the point. At rated accumulation the two agree by construction — that is the
anchor. At the set pressure the ramp credits the valve with **nothing**, which is the one number a
relief study can least afford to get wrong: it is the capacity available at the moment the device
first opens. In the chain's own Phase 4 the relieved rate roughly doubles, 99.0 → 190.8 t/h, and the
ammonia carried to atmosphere with it goes 27 082 → 52 174 kg/h.

### Part B, D-5 — 320K002 has a curve; the node solve is written but NOT wired

`machines.py` carries the polytropic thermodynamics and a normalised centrifugal characteristic:

$$H_{poly} = N_s\,\frac{Z_1 R T_1}{M}\,\frac{n}{n-1}
\left[\left(\frac{P_2}{P_1}\right)^{\frac{n-1}{n N_s}} - 1\right],
\qquad \frac{n-1}{n} = \frac{k-1}{k\,\eta_p}$$

evaluated over $N_s = 4$ equal-ratio intercooled sections. The stage count is not cosmetic: a 90:1
machine on one uncooled section discharges above **870 °C**, which is correct arithmetic about a
machine that does not exist. Four sections put the last-stage discharge at 160 °C and the
aftercooler takes it to the 120 °C feed anchor.

The map is the standard head-rise-to-surge parabola in fan-law-reduced coordinates,
$q = (Q_{in}/Q_{des})/(N/N_{des})$ and $\psi = (H/H_{des})/(N/N_{des})^2$, fitted to the two numbers
a datasheet states even without a full curve — the surge flow (0.68) and the head rise to surge
(12 %). The design point is $(q, \psi) = (1, 1)$ by construction and the machine returns
`CO2_DES_KGH` **bit-exactly** there. It now surges when the head demand passes the peak and
stonewalls at $q = 1.20$, and both flags are published. A **speed governor** closes the flow loop,
because 320K002 is flow-controlled: the governor trims speed to hold the demanded rate against
whatever discharge pressure the loop presents.

**The pressure-node solve is written, unit-tested and deliberately left unwired.** It replaces
`f_{HP} = g_{HP}/(g_{HP}+g_{vent})` with a real node balance — machine delivery = HP-loop draw +
vent draw, bisected on a strictly monotonic residual, returning a zero-residual design seed
untouched so the pin cannot move. Its design residual here is a literal 0.0. It is not wired because
it is measurably worse than the heuristic on the thing that matters most. Measured over 16 000 s on
the 2 s harness tick, everything else in this commit held constant:

| configuration | PT-329201 at 16 000 s | character |
|---|---|---|
| HEAD baseline | 140.70 → **142.54** | bounded ±2 bar wander |
| with the node solve | 140.70 → **135.16** | monotonic, accelerating (−0.81 bar/ks) |
| node solve out (this commit) | 140.70 → **142.26** | back on the baseline curve |

The third row is this code path, and it isolates the cause: not the map, not the governor, not the
API 520 valve, not the Part A work — all of those are present in all three runs. It is the node
solve, through the branch law $\dot m_{HP} = \dot m_{des}\sqrt{(P_{node}-P_{syn})/\Delta P_{des}}$,
which makes the CO₂-line differential a live function of the loop pressure where it used to be
pinned at the design 3.5 bar. That is the right physics and it is what D-5 asks for; what is missing
is the rest of the network the real line has — the check valve's own resistance, the 322E001 inlet,
and the line inventory as a capacitance rather than a massless node. Without those the branch is far
stiffer than the plant and the loop's pressure integrator picks up a slow one-way term from it.
Wiring it in that state would trade an honest heuristic for a dishonest first-principles model.

### Part B, D-6 — not attempted, and why

322F001 is a **liquid-liquid** jet ejector. `ejector_huang.py` is a compressible double-choking gas
ejector: it computes Mach numbers, isentropic area ratios and normal shocks, and its
`entrainment_ratio` raises on any motive/suction ratio below choking. There is no Mach number in a
liquid jet and nothing chokes, so that module cannot describe 322F001 as it stands — wiring it in
would raise on the first tick.

The right answer is the same three control-volume balances in their incompressible form (the
standard constant-area jet-pump analysis, Cunningham / ESDU 85032), and that was written and
exercised against the plant design point. It reproduces the design duty exactly and gives the right
qualitative directions — closing the spindle raises entrainment, losing motive stalls it, with no
`f_stall` polynomial anywhere. It was **not** committed, because the closure it produces is
non-monotonic in the entrained flow and therefore bistable. The mixing-chamber momentum balance
gives a discharge pressure whose $\dot m_s^2$ coefficient is

$$\frac{1}{\rho_s A_s A_m} - \frac{0.625}{\rho_2 A_m^2}$$

and with the anchored densities ($\rho_s = 1340$, $\rho_2 = 878$ kg/m³) and any physically sensible
area ratio that group is **net positive**: the recovered discharge pressure eventually *rises* with
entrainment, so the solve has two roots and the characteristic degenerates into a step — zero below
a motive threshold, railed above it. A jet pump's real $N$–$M$ curve is monotonic; getting there
needs the mixture density carried live through the mixing section and the area convention checked
against a published $N$–$M$ curve, which is more than a wiring job. Shipping the step function would
have been strictly worse than the `f_stall` polynomial it was meant to delete.

## Melt-Temperature Integration in Unit 324: Why a Draining Evaporator Killed the Engine

Both 324 stages advanced their melt temperature with an explicit Euler step over the liquid
inventory alone:

$$T' = T + \frac{\dot P\,\Delta t}{\max(M\,c_p,\ 10^{-6})}$$

The `1e-6` floor looks like the defect and is not: `s.r324_f001_M` is written back as
`max(..., 1.0)`, so $M \geq 1$ kg always and that floor is unreachable dead code at every one of
these integrators. The defect is the scheme. Written out, the step is

$$T' = T + \frac{\Delta t}{M c_p}\Big[\underbrace{\tfrac{\dot m_{feed}}{3600}c_{p,f}(T_f - T) + UA\,(T_{sat} - T)}_{\text{depends on the } T \text{ being solved for}} - \tfrac{\dot v}{3600}\lambda\Big]$$

which is $T' - T = (1 - \Delta t/\tau)(T - T_\infty)$ with $\tau = Mc_p/k_{cap}$ and

$$k_{cap} = \frac{\dot m_{feed}}{3600}c_{p,f} + UA .$$

$k_{cap}$ is a property of the **flows**, not of the inventory, so as the separator drains $\tau$
collapses while the driver does not. The step amplifies whenever $\Delta t/\tau > 2$, i.e. below

$$M_{crit} = \frac{k_{cap}\,\Delta t}{2\,c_{p,hold}}$$

| stage | $\dot m_{feed}$ (kg/h) | $k_{cap}$ (kW/K) | $M_{des}$ (kg) | $M_{crit}$ @ 0.1 s | $M_{crit}$ @ 2 s |
|---|---|---|---|---|---|
| 324F001 | 92 748.9 | 856.47 | 3933.8 | 19.5 kg (0.50 %) | 389.9 kg (9.91 %) |
| 324F003 | 78 675.8 | 116.25 | 3796.9 | 2.7 kg (0.07 %) | 54.8 kg (1.44 %) |

That second column is the finding. On the **harness** tick, $\Delta t = 2$ s, 324F001 is already
unstable at one tenth of its design inventory — a normal deep level excursion, not an empty vessel.
At 100 kg of holdup the per-step amplification is 6.8×; at the 1 kg floor it is 779×. On the
production tick it takes a true drain, amplifying 38× per step at the floor. The observed failure
is the arithmetic of that table:

* a CCW loss trips the plant and 324F001 draws down past $M_{crit}$;
* $T$ starts alternating sign about $T_\infty$ and **doubles every tick** — the textbook explicit
  Euler instability at $|1 - \Delta t/\tau| \gg 1$;
* about 340 doublings later `cp_water_kjkgk` evaluates $T^3$ on a number above $5.6\times10^{102}$
  and the tick dies with `OverflowError: Result too large`.

An `OverflowError` inside a heat-capacity correlation looks like a property-range problem and is
not one. Clamping `cp_water_kjkgk` would have hidden a diverging state behind a plausible-looking
number, which is worse than the crash — the trainee would see a running plant with a fictional
evaporator.

### The fix is a better integration scheme, not a limiter

Treat the $T$-dependent terms implicitly. Backward Euler on them, rearranged so the increment keeps
its explicit numerator:

$$\frac{M c_p}{\Delta t}(T' - T) = \dot P(T) - k_{cap}(T' - T)
\qquad\Longrightarrow\qquad
T' = T + \frac{\dot P\,\Delta t}{M c_p + k_{cap}\,\Delta t}$$

$$k_{cap} = \frac{\dot m_{feed}}{3600}c_{p,feed} + \begin{cases} UA & Q > 0\ 0 & Q = 0\end{cases}$$

The $UA$ term is gated on $Q > 0$ because the chest duty is itself clamped at zero once the melt
runs above saturation; past that point $UA$ no longer resists a change in $T$ and including it
would over-damp.

Three properties make this the right answer rather than a patch:

* **Unconditionally stable** in both stiff terms. The amplification factor is
  $Mc_p/(Mc_p + k_{cap}\Delta t) \in (0, 1]$ for any $\Delta t$ and any $M$, so $M_{crit}$ ceases
  to exist.
* **Correct in the limit it used to break.** As $M \to 0$ the step becomes
  $T' \to T + \dot P/k_{cap}$, which is the algebraic solution — a vessel with no thermal inertia
  whose outlet simply follows its inlet. That *is* the physics of a drained evaporator; the old
  form asserted the opposite, that a vessel holding almost nothing could still integrate heat over
  a 2-second step.
* **Bit-exact at the design seed.** $\dot P$ is identically zero there by construction (the UA and
  $\lambda$ anchors are back-solved for it), so $T' = T + 0$ regardless of the denominator. The
  boot pin cannot move. This is why the increment form is used instead of the algebraically
  equivalent $(Mc_pT/\Delta t + k_{cap}T_f + Q)/(Mc_p/\Delta t + k_{cap})$, which is correct in
  exact arithmetic but relies on a cancellation that floating point does not deliver.

The `max(..., 1e-6)` stays for shape, but it was never load-bearing and is less so now: the
denominator is bounded below by $k_{cap}\Delta t$ whenever anything is flowing, and by the 1 kg
mass floor when nothing is.

### The same shape sat at eleven more integrators — all now swept

`grep` finds thirteen `dt / max(M*cp, 1e-6)` steps in `main.py`. Ten of the remaining eleven now
carry the same semi-implicit denominator; the eleventh is deliberately left alone and the reason is
the more interesting half of the result.

$k_{cap}$ is **per vessel** — it is that vessel's own inlet heat-capacity rate, plus a $UA$ only
where the duty is genuinely temperature-driven:

| node | $k_{cap}$ | $UA$ in $k_{cap}$? |
|---|---|---|
| 323F004 | $\dot m_{314}c_{p,314}/3600$ | no duty |
| 323F010 | $(\dot m_{319}c_{p,319} + \dot m_{331}c_{p,331})/3600$ | yes, 323E010 while $Q>0$ |
| 323D002 | $(\dot m_{317}c_{p,317} + \dot m_{recyc}c_{p,recyc})/3600$ | no duty |
| 323C005 | $(\dot m_{756} + \dot m_{702} + \dot m_{708})c_p/3600$ | no duty |
| 328D003-I | $(\dot m_{719} + \dot m_{720} + \dot m_{721} + \dot m_{759})c_p/3600$ | no duty |
| 328D003-II | $(\dot m_{bot,C005} + \dot m_{741})c_p/3600$ | no duty |
| 328C003 | $\dot m_{746}c_p/3600$ | no duty |
| 328D001 | $(\dot m_{737} + \dot m_{718A} + \dot m_{793})c_p/3600$ | **no** — see below |
| 322C001 | $(\dot m_{755} + \dot m_{CPL} + \dot m_{GCB})c_p/3600$ | no duty |
| 323E003 | $(\dot m_{305} + \dot m_{718B} + \dot m_{776} + \dot m_{797})c_p/3600$ | **yes** |
| 323E011 | $(\dot m_{701} + \dot m_{786} + \dot m_{321} + \dot m_{402})c_p/3600$ | **yes** |

The $UA$ column is not bookkeeping. A duty belongs in $k_{cap}$ only if it *resists a change in the
temperature being solved for*. 323E003's $Q = UA(T_{E003} - T_{tw})$ and 323E011's
$Q = UA(T_{E011} - 35)$ both do. 328D001's $Q_{E004}$ does not: it is
`R328_E004_Q_DES_KW * (tic002_op / R328_E004_TV_OP_DES)`, a *stroke*-driven duty off TV-328002 with
no $T_{D001}$ in it at all, so putting its $UA$ in the denominator would damp a resistance that does
not exist. Same for the 328C003 hydrolyser: the 911 steam injection, the 748 latent draw and the
hydrolysis endotherm are all independent of $T_{C003}$, leaving the 746 feed as the only term.

### 323C003 is the exception, and it shows what the defect actually was

323C003 keeps its explicit step. It is the one vessel in the engine whose energy balance is written
in **relaxation** form rather than in-minus-out:

$$\dot q_{relax} = \frac{M c_p (T_{bub} - T)}{\tau_{res}}
\qquad\Longrightarrow\qquad
\frac{\partial \dot P}{\partial T} = -\frac{M c_p}{\tau_{res}}$$

The heat-capacity rate that resists the change is $Mc_p/\tau_{res}$, which carries $M$ itself. So
$\Delta t/\tau$ collapses to the constant $\Delta t/\tau_{res}$ — 0.1 s against a 300 s residence
time — *no matter how far the column drains*. There is no $M_{crit}$; the step is already
unconditionally stable, and adding a $k_{cap}$ would only over-damp a bubble-point relaxation that
is correct as it stands.

That contrast is the whole finding stated cleanly. The instability was never about small numbers or
a division guard. It was about **where the heat-capacity rate lives**: when it belongs to the flows
it survives the inventory going away, and explicit Euler divides a surviving driver by a vanishing
capacity. When it belongs to the inventory, as at 323C003, it vanishes with it and the ratio is
constant. 323F004 sits on the boundary and shows the rule works either way — it carries *both* a
relaxation term and a real letdown sensible load, and only the second one goes into $k_{cap}$.

### Verification

* **All 20 pinned boot constants are byte-identical** before and after the sweep
  (`.boot_pin_cache.json`, compared entry by entry against `HEAD`).
* **The design seed is bit-identical** at $t = 0$ across all 29 probed states, every anchor landing
  on its exact PFD value: 322C001 3.900000000, 328C003 16.800000000, 324F001 0.330000000,
  324F003 0.131000000, 323F010 0.460000000, 323D002 99.000000000, TT-322014 183.000000000.
* After **200 production ticks** the nodes that were *not* touched are still bit-identical, and the
  ten that were differ by at most $1.5\times10^{-6}$ °C and $3\times10^{-8}$ bar — last-digit motion
  on states that already carry a small non-zero $\dot P$ at the settled attractor, not a moved
  design point.
* **`test_3_scrubber_heat` is 8/8**, the CCW-restore leg relaxing $+0.300 \to +0.100$ bar against
  HEAD's $+0.200 \to +0.100$. This is the check that caught the HPCC wiring, and it is the reason
  the design seed alone is not an acceptance criterion for this work: the seed was 103/103
  bit-identical in the failing configuration too. Any future change to an HP-loop split should be
  judged on a transient, not on $t = 0$.

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

### Where `R_des` actually comes from (heuristic re-audit, 2026-09-15)

`R_des` is not itself a mass source. It is the loop-level **mirror** of one. Against the PFD rows the
boundary pins decompose exactly:

| Term | Pin (kg/h) | PFD (kg/h) | Δ |
|---|---|---|---|
| Motive NH3 | 42 762.05 | 40 756 | +2 006.05 |
| CO2 feed | 54 618.0 | 54 618 | 0 |
| m308 | 36 835.15 | 36 915 | −79.85 |
| LV-322501 bottoms | 130 482.0 | 130 582 | −100.0 |
| HV-322604 vent | 5 901.4 | 1 708 | +4 193.4 |
| in − out | −2 168.2 | −1 | |

At steady state the loop's internal units must therefore **create** 2 168.2 kg/h. The creation site
is the reactor recycle tear, applied as `fc_i = feed_i − REACT_TEAR_DES_i · s` inside `react_322r001`.
Multiplied through by molar mass, the boot-pinned tear gives +2 085.7 kg/h, 96.2 % of the residual:

```text
CO2 +2416.3   Urea +283.9   H2O +122.5   CH4 +61.9   H2 +4.1   O2 +0.8
NH3  -795.9   N2   -7.9                                         sum +2085.7 kg/h
```

The CH4 and H2 it creates (3.86 and 2.02 kmol/h) equal the reconciled vent vector's CH4 and H2 to the
last digit, and no feed carries either species. The remaining 82.5 kg/h has not been located.

**Deleting `R_des` alone is wrong, and was measured.** With the credit removed and nothing else
changed, a fresh design seed at `STEP_CAP` gives PT-329201 = 140.700 → 139.477 bar a after 2 750 s.
That is −1.45 bar/h, which is `R_des/C_loop` exactly, and the reactor and HPCC levels bleed with it.
The credit stays until the 322E003 vent is re-reconciled on its PFD row and the re-pin drives
`REACT_TEAR_DES` to zero.

### Loop-fill multiplier removed (report A-3)

The reactor, stripper-sump and HPCC holdups integrated `k_loop_fill·(in − out)` with
`k_loop_fill = 0.06 + 0.94·m_loop_frac^8`, a gate Smith-fitted so that the cold-start
pressurisation τ landed inside the DCS FOPTD band. At `k = 0.06` it deleted 94 % of every net inflow.
Each holdup now integrates its actual net flow:

```text
dM_react/dt = m_in − m_out + m_fwd        dL_strip/dt ∝ m_bot,delayed − m_drain        dL_hpcc/dt ∝ φ_in − φ_out
```

At design `m_loop_frac = 1` gave `k = 1` exactly, so the design seed does not move. The 3 000 s hold
reads 140.479560 bar a, against HEAD's 140.479578. PT-329201 itself was never multiplied by `k`: it
integrates the lumped boundary balance above, so the cold-start pressure response is governed by
`C_loop` and the feed ramp (report A-1), not by the holdup fill rate.

### Steam-chest pressure solved, not assigned (report A-5)

The four condensing-steam chests (323E002, 323E010, 324E001, 324E003) used
`P_chest = (op/100)·P_header`. The chest is now the pressure at which the steam the valve admits equals
the steam the tube wall condenses:

```text
R(P) = Q_des · [Phi_gas(h, P_hdr, P, Tsat(P_hdr)) / Phi_gas(h_des, P_hdr,des, P_des, Tsat(P_hdr,des))]
             · lambda(P)/lambda(P_des)  −  UA·(Tsat(P) − T_process) = 0

Phi_gas = P1 · Y · sqrt(x·M/(T1·Z)),  x = min(dP/P1, F_gamma·x_T),  Y = 1 − x/(3·F_gamma·x_T)
```

The valve law is ISA-75.01 compressible with a linear trim, anchored on the DDS chest pressure and
design duty. λ comes from IAPWS-IF97.

`R` is written without a floor, so it decreases strictly in P and the root is unique. A shut valve
puts the chest on the process saturation pressure (`Q = 0`, replacing the old AUDIT F-10 floor
physically). A process hotter than the header's saturation drives the chest to the header. The
solver is a bracketed Newton from the previous tick's chest; at an unchanged operating point the
first residual is zero and the stored value returns unchanged.

**Quasi-steady, and why.** The chest holds about V·ρ_g ≈ 10 m³ × 2.2 kg/m³ against about 2.8 kg/s,
a few seconds of residence, while the melts it heats have 100–400 s. The shell volumes that would
size a dynamic state are not legible: the four exchanger datasheets in `References/Datasheets` are
image-only scans (0 fonts, 15 images each). The V → 0 limit needs no volume, and it is the correct
limit at this separation of time scales.

**The PICs now read their own chest.** Previously PIC-329202/208/203/212 read `op·P_hdr/100`, a PV
computed from their own output. Against the physical chest the plant gain is much smaller, because
the wall condenses more as the pressure rises:

```text
dP/d(op) = −(∂R/∂op)/(∂R/∂P)
Kc_new = Kc_old · (P_hdr,des/100) / (dP/d(op))_des        (IMC: Kc ∝ 1/K_p)
```

The scale factor is computed at import from the closure itself: 5.87 (PIC-329202), 1.86 (329208),
4.23 (329203), 5.46 (329212). This keeps each slave's loop gain Kc·K_p, and so its speed against its
TIC master, exactly where it was tuned.

**Measured.** Design hold over 3 000 s: identical to HEAD within 1.8e-5 bar on PT-329201 and 0.01 °C
on every stage temperature. On a step of all four TIC masters (+2/+2/+1/+1 °C), neither tree
oscillates, the settled temperatures agree within 0.03 °C, and 324E001 overshoots less (131.07 °C
against 131.21). The physical chests need more stroke for the same chest pressure: PV-329202 settles
at 87.0 % against 83.5 %, and PV-329212 peaks at 99.7 % against 92 %. That is a real finding. With
324E003's design stroke at 90 %, the loop has almost no authority above design duty.
`test_equation_audit_323_324::test_design_fixed_point_holds` goes from failing on HEAD to passing.

## Phase 5b — the four findings the vendor archive closed (2026-09-16)

Three of these had been deferred as "blocked on a missing number". Two of the numbers exist in the
licensor/vendor documentation set (`Licensor and Vendor Documentation/Soft copy`, indexed by
`TOC_UD_AM_G00_AB_0022_000_01_HL.pdf`); the third was never a number problem.

### A-6 — 324F001, the last vessel on the shared capacitance

The process datasheet is genuinely silent: UD-AU-324-EC-0006 page 2 leaves line 19 (nominal volume)
and line 22 (height of shell, cyl.) blank, which is why two earlier passes recorded "a 4570 mm bore
admits 33 to 164 m3" and stopped. The vendor **assembly drawing** answers it directly —
UD-AU-324-DZ-0006-001 (Uhde / Aguilar y Salas, rev 00), design table: **Nominal volume, Body =
70.5 m3**, tracing coil 0.083 m3, operating 0.3 bar a / 130 C, delivery weight 21 500 kg. The value
was read from a rendered page and visually verified.

```text
V_v  = 70.5 - M_melt/1200                       (rho_l line 8 of the DDS)
MW_v = rho_v.R.T/P = 0.14 * 8314 * 403.15 / 0.3e5 = 15.6 kg/kmol   (DDS lines 9, 14, 15)
dP/dt = (R.T/V_v)(n_vent - n_ejector)
```

The MW comes out below water's 18.02 because the vapour carries the NH3/CO2 the melt still holds —
which is the whole argument against one shared `K.(gen - out)` coefficient. At design the vent and
the ejector pull are equal, so dP/dt is identically zero and PT-324201 holds 0.330 bar a.
`R324_F001_P_KP` and the three other dead `*_P_KP` constants are deleted.

### A-7 — 323F004 was never missing a line dP

It was missing a topology. Twice deferred as "the design dP across the F004 -> 323E011 line is
identically zero and the PFD rounding is the same order", the real situation is that **there is no
valve in that line**:

* "non-condensed gases from the flash tank condenser (323E011) and the level tank (323D011) are
  routed to the Atmospheric Absorber under the strict regulation of pressure controller PIC323203,
  which maintains the upstream flash tank system at approximately 1.13 bar"
  (`References/323C005 328V001 Datasheets.md`);
* PIC-323203's valve "is located further downstream in the vapour discharge line connecting the
  Flash Tank Condenser (323E011) to the atmospheric absorber"
  (`References/323F004 323E010 323F010.md`).

So the drum shares the 323E011/323D011 gas envelope, which has carried a real vapour-space ODE on
its measured 3.14 m3 since A-6, and whose inflow list already includes the drum's own flash vapour.
`s.r323_f004_P = s.r3232_e011_P` replaces

```text
p_tgt = 1.13 + 0.45 bar per unit of relative flash-vapour excess ;  dP/dt = (p_tgt - P)/90 s
```

i.e. pressure chasing flow through an invented gain and an invented lag. The feedback that gain was
imitating is now the real one: more flash raises the node, which raises the bubble point, which cuts
the next flash. `R323_F004_P_GAIN` and `R323_F004_P_TAU_S` are deleted.

### A-11 — both remaining 323 stages onto one thermodynamic surface

323C003 and 323F004 kept `T_sp + (tsat(P_live) - tsat(P_des))`: the bubble point of a 55-69 wt%
urea / ammonium-carbamate / NH3 liquor taken as **steam's**, with the whole boiling-point elevation
frozen into the anchor. Both already took their vapour composition from `thermo_service`, so each
stage's two legs stood on different surfaces — the defect A-11 closed at 323F010 and left open where
the liquors carry volatiles. Both now use `sol_bubble_t_dep` in the same departure form. The
rigorous bubble points at the design compositions are 133.03 C (C003, against the PFD's 135) and
102.66 C (F004, against 106), so the surface is close before anchoring, and the anchor keeps each
design point exact.

### A-17 — the barometric leg, and the sister leg that nearly misled it

`M317_DES*sqrt(M/M_DES)` is Torricelli on a mass ratio: no vessel pressure, so breaking the vacuum
changed nothing, and the settled holdup was pinned to M_DES by construction (sqrt(M/M_DES) = 1 is
its only steady state).

The first attempt sized the leg on its own differential, by analogy with the note the sources give
for 324F001's leg ("compute the liquid column height based strictly on the 0.20 bar differential
pressure"). That is right for **that** leg, which runs between two vacuum vessels. 323F010 drains to
323D002, which is **atmospheric**, so its leg is barometric in the strict sense and its column is
sized to balance atmosphere. The distinction is worth 10x in sensitivity, and it was caught by
measurement: the differential form made a 0.5 mbar vacuum deviation move the drain 0.2 %.

```text
rho.g.h_leg = P_atm   ->   dP_drive = M.g/A + P_atm - (P_atm - P_vessel) = M.g/A + P_vessel
m_317 = M317_DES . sqrt(dP_drive / dP_drive,des)
```

Density cancels twice (liquid column and leg), which matters because no source pins this stream's
density; A is the datasheet bore (ID 3478 mm). Design-exact, and a vacuum break raises the drain by
about 43 %.

**A real consequence, recorded rather than tuned away.** With a head-driven leg the settled holdup
is no longer pinned to M_DES: it satisfies `M.g/A + P = M_des.g/A + P_des`, so the 323F010 node's
pre-existing 0.5 mbar deficit (report D-12 — the 324F002 ejector pull is still linear in suction
pressure) now backs the column up by about 48 kg and trims evaporation 0.19 % through `q_relax`.
`test_equation_audit_323_324::test_design_fixed_point_holds` was re-based from 6e-3 to 3e-2 t/h with
that measurement written into it, plus a new assertion that the leg law returns the PFD drain
exactly at the seed. Closing D-12 should put it back inside 6e-3. **It did not** -- the deficit was
never the pull law. *Phase 5e* found the cause (a 58.7 kg/h urea hole in the stage's species
balance) and the gate is back at 6e-3.

### Measured

Design hold, 3 000 s from a fresh seed at STEP_CAP: PT-329201 140.476115 bar a, against 140.479560
before this work (3.4e-3 bar, the F004 envelope and the F010 leg now interacting), every stage
temperature within 0.01 C of its setpoint. Seed checks: m_317 equals R323_M317_DES exactly,
PT-324201 0.330000000, PT-323204 0.460000000. Regression: `test_equation_audit_323_324` 2 failed /
3 passed, identical to the commit before; `test_hydraulics` 56 passed (three tests rewritten — two
referenced deleted constants, one pinned the 324F001 deferral the drawing closes);
`test_scenario_lag_table` all checks pass with the flash-drum lag check replaced by a structural one.

## Phase 5c — the steam drums get their real geometry (D-14 / D-15 / MSPAN_504)

The three header pressures integrated `dP/dt = residual/C` on constants that were openly labelled:
`C_MP = C_LP = 25.0` ("lumped, calibrated" -- one number for two different headers) and
`C_9 = 8.16 * 0.2174 * 30.0`, a derived capacitance multiplied by a stated x30 lumping factor whose
own comment gave the reason: it "keeps the 9-bar node ... Euler-stable at the host dt".

That reason is a property of the INTEGRATOR, not of the drum, so the closure is two independent
pieces.

### The capacitance

```text
C = V_vapour . drho_sat/dP |_P        (IAPWS-IF97 on the saturation line)
```

V_vapour is the drum volume ABOVE its printed normal liquid level. The DDSs leave "max. fill lev.
in oper. cond." blank on all three, so the level comes from the as-built general arrangements:

| header | vessel | total volume | NLL | V_vapour | C (kg/bar) | was |
|---|---|---|---|---|---|---|
| MP | 329D005 horiz, 1 off | 13.8 m3 (as-built CAPACITY) | on the shell axis | 6.90 m3 | **3.39** | 25.0 |
| 9-bar | 329D009 horiz, 1 off | 8 m3 (nameplate) | on the shell axis | 4.00 m3 | **1.97** | 53.2 |
| LP | 322D001A/B vert, 2 off | 61.06 m3 each | 1.050 m above the bottom t.l. | 91.32 m3 | **45.92** | 25.0 |

Sources: UD-AU-329-EC-0001 p2 and UD-AU-329-DZ-0001-005 rev 02 (329D005); UD-AU-329-DZ-0003-005
rev 04 (329D009, manufacturer's nameplate block); UD-AU-322-EC-0009 p2 and UD-AU-322-DZ-0009-006
rev 05 (322D001A/B). All scans, rendered and read.

The LP drums are the interesting ones, twice over. The calibrated 25.0 looked vindicated when the
shell was taken as half vapour -- two 3.47 m drums give 25.2 kg/bar that way -- but their GA prints
NLL at 1050 mm in a 5300 mm shell, so they run about a FIFTH full and the real figure is 45.9. The
MP header is seven times stiffer than its constant claimed and the 9-bar drum twenty-seven times.

322D001's geometry is worth stating because three independent numbers agree on it. Cylinder
pi/4 x 3.470^2 x 5.300 = 50.13 m3 plus two 2:1 ellipsoidal heads at pi.D^3/24 = 5.47 m3 each gives
61.06 m3; the GA's own design block states CAPACITY 62 m3; and the DDS hydrostatic-test weight
(80 065 - 19 065 = 61 000 kg of cold water) gives 61.0 m3. That agreement also settles the head
shape -- torispherical heads would give 58.5 m3 and miss all three.

The half-full assumption this section used to flag is therefore half retired and half promoted: it
was a DATUM for the two horizontal drums, whose GAs both draw the NLL flag on the shell axis, and
wrong for the vertical ones.

### The integration

Every term that resists a header pressure change is a valve whose flow depends on that same
pressure, so the resisting conductance is available from the laws already in the module:

```text
g = -d(residual)/dP            (evaluated by re-running the same _valve_flow calls at P + 1e-3 bar)
(C/dt)(P' - P) = res(P) - g.(P' - P)   ->   P' = P + res.dt/(C + g.dt)
```

Amplification is C/(C + g.dt), in (0, 1] for any dt and any C, so the stability limit that forced
the lumping ceases to exist -- the same argument, and the same fix, as the unit-324 melt
temperatures. At the design seed every residual is zero, so P' == P whatever the denominator is and
all three headers stay bit-exact.

### The same drawing fixes the level span (MSPAN_504)

`MSPAN_504` is the liquid mass between 0 % and 100 % on LICA-329504, and it read

```text
MSPAN_504 = 917.0 * (pi/4 * 1.600^2) * 2.000        = 3 687 kg
```

Every one of those four numbers was wrong. The drums are ID 3.470 m, there are TWO of them on the
one controller, the LICA-329504 tappings N8B and N8A sit 300 mm and 1800 mm above the bottom tangent
line so the transmitter spans 1.500 m, and the liquid is 919.36 kg/m3:

```text
MSPAN_504 = RHO_D001_L * (N_D001 * A_D001_M2) * LT504_SPAN_M
          = 919.36 * (2 * 9.4575) * 1.500       = 26 083 kg
```

Seven times the inventory the loop thought it was moving, so LIC-329504 was swinging about seven
times too fast for the make-up flow driving it. Both tappings are in the cylindrical shell, so the
area is the plain cross-section and there is no head correction anywhere in the span. Nothing is
design-pinned to it: `_level_loop` is seeded so that dm/dt = 0 at the design point for any `m_span`,
so what moved is the level TIMESCALE and nothing else.

The same chain also confirms the 50 % design level rather than assuming it. NLL is printed at
1050 mm, which is exactly mid-way between the 300 mm and 1800 mm tappings, so `LEVEL_SP_DES = 50.0`
is what the vendor drew.

### Measured

`steam_system.py`'s own four-scenario self-check: OVERALL PASS (including the HPCC-generation-to-zero
case, where P_LP lands on 4.913 against its 3.5 floor). Run file-by-file: `test_lp_steam_4barg` 1
passed, `test_steam_consumption_surge` 1 passed, `test_steam_system_pfd_mass_paths` 6 passed,
`test_equation_audit_c10_live_cp` 7 passed, `test_hydraulics` + `test_equation_audit_323_324` +
`test_main_extended_uniquac_integration` 67 passed / 2 failed, the same two names as the commit
before.

Design hold, 3 000 s from a fresh seed at STEP_CAP, against the previous commit run the same way:

| | this commit | previous | delta |
|---|---|---|---|
| PT-329201 (bar a) | 140.475882 | 140.475889 | 7e-6 |
| P_LP (bar a) | 5.012255 | 5.012255 | 0 |
| P_MP (bar a) | 19.694155 | 19.694157 | 2e-6 |
| P_9 (bar a) | 9.006478 | 9.005833 | 6.5e-4 |
| LIC-329504 (%) | 50.0156 | 50.0128 | 0.003 |
| 323F010 T (C) | 98.9854 | 98.9902 | 0.005 |
| 323C003 T (C) | 135.000453 | 135.000453 | 0 |

### One thing this exposed and did not cause

`test_equation_audit_c10_live_cp::test_the_design_seed_is_undisturbed_by_any_of_it` holds 323F010 to
0.01 C of 99.0 after 1 200 s, and it broke here -- but on a COLD `.boot_pin_cache.json` only, and it
turns out the gate was never sound.

The chase is worth recording because most of it was elimination. The design seed is NOT the
difference: a fresh `State()` is bit-identical on the cold and warm boot paths, all 108 float
fields. Nor is any pinned constant: of 1 256 module globals compared across `main`, `steam_system`,
`reactor` and `controllers`, exactly four differ -- `SOL_VLE_DOMAIN`, `_DIAG`, `_cached` and
`health.last_step_wall` -- and all four are write-only diagnostics. (`_A328_Q_REACT_DES_KW` is a
genuine cold/warm asymmetry, captured on a pre-pin tick and absent from the cache, but it reaches
only the published packet.)

What does it is the thermo memo. `thermo_service.bubble_t` and `flash` memoise on a quantised key --
`_W_QUANTUM` 1e-4 mass fraction, `_P_QUANTUM_BARA` 1e-4 bar -- so every point falling in a bin gets
the value of whichever point filled that bin FIRST. The answer therefore depends on what the process
computed earlier. In one process, with identical globals and an identical seed:

| memo state | d925a24 | with the drum geometry |
|---|---|---|
| as imported (3 entries) | 99.008098 | 99.000257 |
| after `flash_cache_clear()` | **99.013365** | 99.010351 |
| after a boot settle filled it | -- | 99.005956 |

d925a24 fails the same 0.01 gate as soon as the memo is cleared; it was passing by 1.9 mK against a
5-10 mK spread. A cold boot-pin cache -- forced by every source edit, exactly once -- fills the memo
from the settle and lands on the bottom branch. That is the whole of "it fails the first run after a
model change and passes afterwards".

For one commit that assertion was re-based to 0.05. The memo is fixed in the next section and the
gate is back at 0.01.

## Phase 5d — the thermo memo answers for the caller, not for whoever filled the bin

`thermo_service.bubble_t` and `thermo_service.flash` are memoised, because an unmemoised engine is
several hundred times over its real-time budget. The key is quantised: 1e-4 mass fraction per
species, 1e-4 bar, 0.02 C. Until this phase, a miss solved at the CALLER's point and stored that
answer for the whole bin.

### What was wrong with it

Two things, and the second was found while fixing the first.

**It was history-dependent.** A bin returned whatever point had filled it first. In one process,
with every module global identical and a bit-identical `State()`, 1 200 s from the design seed put
323F010 at 99.000257 C with the memo as imported, 99.010351 after `flash_cache_clear()`, and
99.005956 after a boot settle had filled it. A cold `.boot_pin_cache.json` takes the last branch,
so the engine answered differently after a model change than after a cached boot, and the
generational `clear()` at 4 096 entries re-rolled it inside any long run. The departure form made
it bite: `SOL_TBUB_DES` / `SOL_ALPHA_MODEL_DES` store the design value once at import, the live call
reads the bin, and once a live point refills the design bin the "zero at design" bracket becomes a
constant offset.

**The bin is not small for a trace volatile.** 1e-4 mass fraction is 1.5 % of the 0.665 wt% CO2 in
the 323F004 liquor, and the electrolyte bubble point moves **0.19 C** across it (measured: 102.669
vs 102.475 C either side of the CO2 = 0.00665 edge). The first attempt at a fix -- solve at the bin's
canonical point and serve that flat -- made the memo deterministic and turned every bin edge into a
0.19 C relay. The F004 pressure loop sat on one: T_sat flipped 105.87 <-> 106.06 C every two seconds
and the flash vapour chattered 4.40 <-> 4.45 t/h. The first-filler memo had the same 0.19 C inside
every such bin; it hid it as history-dependent bias instead of showing it as a step.

### The closure

Each entry is solved at its bin's canonical point -- the integer key times the quantum -- from a cold
start, so it is a pure function of the key. What it stores is enough to answer for the caller:

```text
bubble_t:  T(w, P) = T_c + [ (P - P_c) - sum_s g_s (w_s - w_c,s) ] / (dP_bub/dT)
           g_s = grad(P_bub) . (e_s - w_c)          (normalised perturbation of species s)

flash:     K from the canonical solve;  psi, x, y from Rachford-Rice on the CALLER's feed
```

Because w and w_c both sum to one, sum_s g_s dw_s equals grad(P_bub) . dw with nothing missing.
K = y/x is the slowly-varying part of a gamma-phi flash; x, y and psi are not, and y of a trace
volatile is close to proportional to its own feed fraction, so re-solving the material balance on
the caller's feed is what makes alpha = y/w continuous.

### Measured

| check | before | after |
|---|---|---|
| 323F010 T at 1 200 s, memo as imported / cleared / cold-boot-filled | 99.000257 / 99.010351 / 99.005956 | **98.998990 all three** |
| bubble_t error vs exact solve, CO2 swept through the F004 bin edge | -122 to +72 mK (flat canonical) | **0.64 mK** worst |
| step in bubble_t at that edge | 194 mK | **0.8 mK** |
| flash alpha_CO2 vs exact, same sweep | -- | within 0.2 % |
| 323F004 T_sat / vapour, 200-330 s | 105.87 <-> 106.06 C, 4.40 <-> 4.45 t/h | 105.9826 -> 105.9814 monotone, 4.430 steady |
| 323F010 excursion over 9 600 s | 34 mK | 5.5 mK |
| 1 200 s wall time (both trees under identical load) | 25.39 s, 47.3x real time | 26.88 s, 44.6x |
| memo misses in that run, flash / bubble_t | 228 / 163 | 167 / 145 |

The long-horizon wander the engine used to show on 323F010 was the memo, not the plant: every
4 096-entry clear re-rolled every bin. `test_equation_audit_c10_live_cp`'s 323F010 gate is back at
0.01 C. Two regression tests pin the new contract in `test_thermo_service.py`: the answer does not
depend on which point filled a bin, and it answers for the caller's point across a bin edge.

One file moves the other way and is not a regression.
`test_equation_audit_td014::test_the_column_and_pre_evaporator_hold_their_setpoints` wants 323F010
within 1 mK of setpoint at exactly 7 200 s, and TIC-323012 is still in a lightly damped +/-10 mK,
~450 s swing there. The test samples its phase: 1.01 mK on this commit, 0.10 mK after the next one.
A 10x finer memo temperature quantum leaves the swing unchanged (p-p 30.5 vs 31.0 mK), so the swing
is the loop, not the memo.

Suite, every `backend/test_*.py` in its own process, against the previous commit:

| | previous commit (ffb07d3) | this commit |
|---|---|---|
| files run | 70 | 70 |
| failing test ids | 49 | 50 |
| files whose failures differ | -- | **1**: `test_equation_audit_td014::test_the_column_and_pre_evaporator_hold_their_setpoints` (the phase-sampled 1 mK check above) |
| `test_equation_audit_323_324`, `test_equation_audit_td014` otherwise | 2 / 3 failed | identical ids -- the three tests the flat-canonical attempt broke are back |
| `test_equation_audit_c10_live_cp` | 7 passed at a 0.05 C gate | 7 passed at **0.01 C** |
| `test_thermo_service` | 27 passed | 29 passed |

The 20 files failing on both are pre-existing and unchanged id for id.

## Phase 5e — 323F010's overhead: a valve into a condenser, and the liquor it carries (D-12)

### D-12: the pull was written for the wrong machine

```text
was:   pull_f010 = MEVAP_DES . (P/P_des) . (HIC-323605/50) . (HIC-329605/50)
```

That is the suction roll-off of a steam-jet ejector, and the report's own "required" column asked
for the 324F002 suction curve. The flowsheet says the ejector is not what pulls this stream. PFD
stream 790 (12 040 kg/h, 0.5 bar a, 99 C) joins the 324F001 vapour in stream 703 on the shell side
of the **324E002 condenser**; what leaves that shell for 324F002 is stream 706, 72 kg/h and 38.6 mol%
N2, and the 324F002 design data sheet (UD-AU-324-EC-0007 p2, rendered and read) sizes the ejector for
94 kg/h of suction at 0.2 bar a on 650 kg/h of LP motive steam. The ejector moves 0.6 % of stream
790; the condenser takes the rest. Its 6-page design calculation (UD-AU-324-DZ-0007-004) is AD 2000
wall-thickness checks with no performance curve, and no control-valve data sheet for HV-323605 exists
in `References/` or in the vendor TOC, which indexes package-unit valves only.

So the pull is the flow HV-323605 passes between two live pressures, ISA-75.01 compressible, anchored
on stream 790 at the 50 % design stroke across the 0.46 -> 0.33 bar a design differential:

```text
w_790 = w_des . Phi(h, P_F010, P_E002, T, M) / Phi(0.5, 0.46, 0.33, 99 C, M_des)
Phi   = frac(h) . P1 . Y . sqrt(x.M/T1),   x = (P1 - P2)/P1 = 0.28 at design (choke at 0.70)
```

`hv323605_flow_kgh` in `main.py`. The trim is linear, the same stated choice and reason as
`R323_LV_CHAR`: it keeps the per-cent-of-stroke gain the operator already had. The 324E002 shell
(`r324_f001_P`) is read from the previous tick because unit 324 advances later. HV-329605 no
longer multiplies this flow; it acts through the shell pressure the ejector holds, which is where
it physically is. What enters the 324E002 inlet balance is now the flow the valve passed, not the
evaporation rate.

The law is stiffer in P than the one it replaces -- dw/dP is 4.07 w per bar against 2.17 -- so on
the 17.8 m3 design vapour space the node's time constant falls from 1.47 s to 0.78 s. The pressure
therefore steps semi-implicitly, as the steam headers do:

```text
P' = P + f(P).dt / (1 - J.dt),     J = df/dP <= 0 (numerical, same valve law)
```

f is a literal 0.0 at the seed, so the pin is untouched.

### What the ejector law allowed that the valve law does not

| probe (from a 300 s settle) | ejector law | valve law |
|---|---|---|
| HV-323605 50 -> 80 %, 323F010 after 300 s | 0.2773 bar a, **below** the 0.3483 shell it drains into | 0.3927 (shell 0.3431) |
| HV-323605 -> 25 % | 0.8743 | 0.7523 |
| HV-329605 50 -> 85 %, PIC-324202 MAN, 400 s: 324F001 | 0.3300 -> 0.2953 | 0.3301 -> 0.3273 |
| same, 323F010 | 0.4592 -> **0.2616**, below 324F001 again | 0.4601 -> 0.4581 |
| HV-323605 50 -> 60 %, 323F010 at 0.5 / 2 / 10 s | 0.4309 / 0.3948 / 0.3835 | 0.4418 / 0.4304 / 0.4286 |

Under the old law both hand valves could pull the separator below the pressure of the vessel it
discharges into, which needs vapour to flow uphill. The HV-329605 row is smaller now for a reason
that is not this valve: the 324F001 / 324E002 node still condenses the DESIGN condensate (26 768
kg/h, a constant in the pressure loop -- `vacuum_condenser_node` and `vacuum_train_324` exist but
nothing calls them; open findings A-13 / B-9 / B-13), so every extra kilogram 324F001 boils goes to a
72 kg/h vent. A real condenser would also hold that shell stiffly -- at 0.3 bar a the water dew point
moves 81 K per bar (IF97 at the 0.28 bar water partial pressure), worth roughly 70 kg/h of condensate per mbar on an 18.5 MW duty -- but the
number should come from condensation, not from a constant. The old law's 35 mbar was one swing of a
+/-4 % evaporation oscillation it set off, not a steady answer.

### The deficit D-12 was blamed for, and what it actually was

With the valve law in, 323F010 still settled 0.8 mbar low and evaporated 11.97 t/h at 600 s -- so
the pull law was never the cause. Tracing it: the liquor CONCENTRATES in the first 250 s (w_urea
0.80013 -> 0.80030), its bubble point rises, TIC-323012 answers by trimming PIC-329208, and
evaporation settles low. The design seed's own species balance says why:

| species | in - out at the seed, before | after |
|---|---|---|
| Urea | **+58.713** kg/h | 0.000 |
| H2O | -56.781 | -4.974 |
| NH3 | -4.022 | 0.000 |
| CO2 | -3.199 | 0.000 |
| Biuret | +5.160 | +4.852 |

Phase 1 was right that urea does not evaporate at 99 C and set its K to zero -- but the 58.7 kg/h
it removed from the vapour is real. **PFD stream 790 lists 0.14 mol% urea** (54.4 kg/h on the
rounded mole-% row), and it leaves as liquor entrained into the DN 600 overhead. With no other way
out it accumulated in the holdup. `_sol_stage_anchor(..., entrain=True)` now closes it as carryover:

```text
urea:    m_in,U - 2.MW_U.xi - m_liq.w_U - f.m_vap.w_U = 0       (biuret jointly, xi >= 0)
y_790  = (1 - f).y_vapour + f.w_liquor,        f = 0.611 % of the overhead
```

and `alpha` is back-solved on the (1 - f).m_vap that really is vapour. 323F010's biuret rows leave
no room for formation (5 kg/h more in than out, inside the 0.005 wt% rounding of a 101 t/h feed), so
xi stays 0 as before and f closes urea alone. Stream 305 lists no urea, so 323C003's 8 kg/h remainder
is rounding and is not treated as carryover. The carryover is proportional to vapour load, the
first-order behaviour of droplet entrainment; nothing in the sources gives more. Its latent heat is
still charged on all of m_evap: 46 kW of the 7 253 kW duty, inside the uncertainty of the 2 280 kJ/kg
itself (IF97: 2 310 at 79.3 C, 2 259 at 99 C).

### Measured

| 600 s from the seed | before | valve law only | valve law + carryover |
|---|---|---|---|
| PT-323204 | 0.459086 | 0.459186 | **0.459918** |
| 323F010 evaporation | 11.99 t/h | 11.97 | **12.01** (design 12.013) |
| holdup | 6 196.2 kg | 6 195.0 | 6 184.0 (seed 6 183.3) |

`test_equation_audit_323_324`'s F-3 gate is back at 6e-3 t/h. `test_equation_audit_species` now
asserts that 323F010's urea alpha is zero and its carryover fraction is positive, instead of reading
the carryover as a volatility.

Test files, each in its own process, against the previous commit:

| file | previous commit | this commit |
|---|---|---|
| `test_equation_audit_323_324` | 2 failed / 3 passed, F-3 gate at 3e-2 | same 2 failed, **F-3 gate at 6e-3** |
| `test_equation_audit_species` | 7 failed / 9 passed | **6 failed / 10 passed** -- `test_species_layer_does_not_perturb_the_mass_or_energy_balance` (its own 6e-3 F-3 check) now passes |
| `test_equation_audit_td014` | 4 failed | 3 failed -- the phase-sampled 1 mK check reads 0.10 mK here |
| `test_vacuum_valve_rules` | 5 passed | 5 passed |
| `test_hydraulics` | 56 passed | 56 passed |
| `test_g3_component_reconciliation` | 1 failed / 9 passed | same id |
| `test_equation_audit_c10_live_cp` | 7 passed | 7 passed |
| `test_session_regression_gate` / `test_startup_stability` (run with the D-16 commit on top) | 7 / 5 passed | 7 / 5 passed |
| `test_equation_audit_322e002`, `test_lv322501_pressure_retuning`, `test_reactor`, `test_scrubber` (same) | 1 failed / 17 / 14 / 13 passed | identical |

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

All ten screens are generated from the PowerPoint page drawings in
`Urea Simulation Docs/Equipment Drawing/UI Pages` - 321-1, 322-1 and 322-2 from the 2026-09-02
revision, 324-1 and 324-1b from 2026-09-05, 323-2 and 329-1 from the first 2026-09-15 reissue,
and 323-1, 328-1 and 328-2 from the second.  The two reissues together restored twenty
previously undrawn indicators.
Each background PNG is that slide with the overlay-supplied shapes deleted (indicator tag boxes,
pump and XV icons, hand-switch buttons, level bargraphs, nav blocks) and exported at exactly
1366x720. Overlay coordinates are the deleted shapes' own centres, so an overlay always lands
where its symbol was drawn. The slide canvas is 12192000 x 6858000 EMU, giving

```text
x_stage = (x_emu + cx_emu/2) * 1366 / 12192000
y_stage = (y_emu + cy_emu/2) *  720 /  6858000
```

The 16:9 slide is stretched, not letterboxed, onto the 1366x720 stage (`background-size:100% 100%`),
which is why the two axes carry different scale factors. Nested group shapes are resolved through
the group's `chOff`/`chExt` child-space transform before the mapping is applied.

Icon overlays (pumps, XVs) also carry the slide's rotation and mirror. The slide is rendered
mirror-then-rotate-then-stretch, so the overlay reproduces that order rather than rotating the
already-stretched box: the image is drawn at its un-stretched size `(w/R, h)` and carries
`scaleX(R) rotate(theta) scale(+-1, +-1)`, right-most first, with
`R = (1366/12192000)/(720/6858000) = 1.06719`. For a 90-degree icon this yields an on-stage
footprint of `cy*sx` by `cx*sy`, which is what PowerPoint exports; at 0 degrees with no flip it
collapses to the plain `w` by `h` box. 322-2's XV-322901 is drawn at 90 degrees on the vertical
leg and the two 329P006 pumps at 180 degrees; 323-2 draws six pumps at 90 and two at 180, and
328P006, 322P002 and 335P002 A/B are mirrored (`flipH`) rather than rotated.

`t: 'bar'` renders the vertical level bargraph the drawings slot into a vessel. It is a pure
display of an already-published percentage - it introduces no state and no equation of its own:

```text
h_fill / h_box = clamp(PV, 0, 100) / 100
```

`PV` is the same packet leaf its paired numeric indicator reads, so the bar and the number can
never disagree, and both inherit the FOPDT constants tabulated above. An unresolved or
non-numeric bind renders the empty white frame at zero fill rather than a misleading full bar.
Twenty-two bargraphs are drawn across the ten screens: 322R001 (`LT-322504`), 322E001
(`LIC-322501`), 322E003 (`LT-329501`), 323C003 (`LIC-323501`), 323F004 (`LIC-323505`), 323D002
(`LT-323504`, `LIC-323507`), 323D001 (`LT-323502`), 323C005 (`LIC-323503`), 328D001
(`LIC-328501`), 328C002/C003/C004 (`LIC-328503`, `LIC-328504`, `LIC-328505`), 322C001
(`LIC-322502`), 328D003 compartments I and II (`LT-328507`, `LT-328508`), 324F003
(`LIC-324501`), 324E001 (`LIC-329505`), 329D005/D009/322D001 (`LIC-329502`, `LIC-329503`,
`LIC-329504`), and 335D004 (`LT-335507`, unbound - Unit 335 is not modelled).

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

## Phase 4b — the CO2 Compressor Node, the HP Jet Pump, and the Unit-328 Remainder

Three structural gaps closed together, and one measurement that turned out to underlie all three.

### D-5 — 320K002 delivers into a line that has a volume, through a valve that is a diode

**What it replaced.** The CO2 feed line carried two algebraic assertions. The line pressure was

```text
P_line = min(P_syn + dP_des, P_ceiling) - K_pv . theta_pv
```

— a statement about the desired process outcome, not about a machine — and the split between the
HP loop and the PV-322203 vent was a normalised conductance ratio `g_HP / (g_HP + g_vent)` that
forces the two branch flows to sum to the raw feed by construction. Phase 4a replaced the machine
half of that with a real polytropic map and wrote the algebraic node solve
(`machines.solve_node_pressure`), then measured the node solve **diverging** — 140.70 to 135.16
bar a over 16 000 s, monotonic and accelerating — and shipped without it. The diagnosis recorded at
the time was that a massless node is far stiffer than the plant.

**Two things were missing, and both are physical.**

*Line capacitance.* The discharge line holds gas, and that inventory is a state:

```text
dP_line/dt = (R . T_line / V_line) . (n_machine - n_check - n_vent)
```

through the same `hydraulics.vessel_dpdt` every vessel now uses. `T_line` is the aftercooled feed
temperature, a boundary, so its thermal term is a literal 0.0, and the line holds no liquid, so the
swell term is a literal 0.0. The volume is **not a new number.** The engine already carries this
line's inventory — `FEED_CO2_LINE_KG`, back-solved in the D-8 block from the DCS-measured 345 s
feed dead time at the design flow — and a line that holds *M* kg of gas has *both* a transit
*M*/ṁ and a capacitance *RT*/(*V M̄*) with *V* = *M*/ρ. Deriving the two from one inventory is a
**constraint between them**, not a second free parameter: `CO2_LINE_V_M3 = 5234.2 / 242.70 =
21.566 m³` at the PFD's own design line density, and `test_hydraulics.py` pins the identity.

*Check-valve resistance.* The HP branch was `m_des · sqrt(dP/dP_des)` behind a `min(1, ·)` delivery
fraction — a resistance that saturates at design, so a line pushing harder than design could not
pass more, and one with no seat, so at dP = 0⁺ it still passed flow. `hydraulics.check_valve_kgh`
is the diode:

```text
w = w_des . sqrt( (p_up - p_down - p_crack) / (dP_des - p_crack) )   forward, disc lifted
w = 0                                                                otherwise
```

Forward flow follows sqrt(dP) with no ceiling; the crack band and reverse flow are both **exactly**
zero, and zero because the disc is seated rather than because a square root went imaginary. The
check valve's own seat resistance and the 322E001 inlet resistance are in series and both follow
sqrt(dP), so they lump into one anchored resistance and only their sum was ever observable from a
single design point — the model carries one and says so. `p_crack` is a stated assumption of the
same class as `FL_GLOBE` and `XT_GLOBE` (there is no check-valve datasheet in the repository),
expressed as 2 % of the licensor's own design tie-in differential rather than as a fabricated
absolute; it cancels exactly at design and moves the passed flow by under 0.1 % anywhere above half
the design differential. What it fixes, and what nothing else fixes, is **where the valve slams
shut**.

**The steady state is now an outcome rather than an axiom.** The check valve passes the machine's
delivery when *P*_line − *p*_syn is the design differential, so *P*_line tracks *p*_syn + 3.5 bar —
the same statement the algebraic float used to assert. Three behaviours the axiom could not produce
come with it: the line lags on its own time constant (τ ≈ 13 s, from the check valve's gain
7962 kg/h/bar against the node's 0.0351 bar/(kg/s)); the tie-in shuts on reversal instead of merely
passing zero; and the deliverable ceiling is the compressor running out of head rather than a
`min()` against a process design pressure — which un-deadens the 151.2 bar a PIC-322203 line relief
and the last two links of the loss-of-condensation chain.

**Design closure is a literal zero.** Delivery 54 618, check valve 54 618 (its ratio is 1.0 at the
design differential by construction), vent 0. `CO2_PV_DP_GAIN` is superseded: the vent now sags the
line by taking mass out of the node, which is where the sag comes from on the plant.

### D-6 — 322F001 is a constant-area jet pump, and the closure is provably single-rooted

**What it replaced.**

```text
capacity = m_suc_des . phi_m . phi_sp . f_stall
f_stall  = clamp((phi_m - 0.20)/(0.35 - 0.20), 0, 1) ** 2
```

The entrainment ratio asserted constant across the healthy band; an equal-percentage characteristic
applied to the **answer** instead of to the nozzle; and stall a three-constant polynomial. The
directions were right and nothing in it could be wrong in an interesting way, because nothing in it
was derived.

**Why the first constant-area attempt was bistable.** The previous incompressible form (recorded in
the handoff, never committed) produced a discharge pressure whose ṁ_s² coefficient was

```text
1/(rho_s . A_s . A_m) - 0.625/(rho_m . A_m^2)
```

which is net positive for any sensible area ratio, so the recovered pressure eventually **rises**
with entrainment, the closure has two roots and the characteristic degenerates to a step. The
missing term is the **suction-inlet acceleration**: the entrained stream does not arrive at the
throat entry plane at rest, it has been accelerated to *V*_s = ṁ_s/(ρ_s *A*_s), and that costs a
velocity head −(1 + *K*_en)·ṁ_s²/(2 ρ_s *A*_s²) which enters with 1/*A*_s² where the cross term
enters with 1/(*A*_s *A*_m). Since *A*_s < *A*_m the missing term is the larger of the two.

**It is a theorem, not a tuning.** Write the closure as *p*_d − *p*_s = *C*₀ + *C*₁ṁ_s + *C*₂ṁ_s²
from the nozzle, the suction inlet, the constant-area throat momentum balance and the diffuser. The
positive part of *C*₂ is largest as *A*_s → *A*_m, where it is (1 − *K*_en)/(2ρ_s *A*_m²), and the
negative part is at least (2 + *K*_th − η_d)/(2ρ_m *A*_m²). So

```text
rho_m / rho_s  <=  (2 + K_th - eta_d) / (1 - K_en)        =>  C2 <= 0 at EVERY area ratio
```

At the 322F001 anchors (ρ_m 877.9, ρ_s 1133.0, *K*_th 0.05, η_d 0.80, *K*_en 0.10) the margin is
**1.79**. `jet_pump.monotonicity_margin` returns it and `main.py` asserts it at import, so a future
change to either density that would re-open the degeneracy fails at import rather than shipping a
step characteristic. With *C*₂ ≤ 0 and *C*₁ < 0 the parabola's vertex lies at negative entrainment,
the discharge is strictly decreasing over the whole physical range, and the single non-negative root
is available in closed form — no iteration, no branch to pick.

**Agreement with the published form.** Non-dimensionalised at equal densities and zero losses
(*b* = *A*_t/*A*_m, *M* = ṁ_s/ṁ_p, *K* = ṁ_p²/(ρ*A*_m²)), 2*b*²(*p*_d − *p*_s)/*K* is

```text
2b + 2b^2.M^2/(1-b) - b^2.M^2/(1-b)^2 - b^2.(1+M)^2
```

which is the Cunningham / ESDU 85032 numerator of *N* = (*p*_d − *p*_s)/(*p*_p − *p*_d) term for
term. The convention difference is in the denominator only: the published form takes the nozzle
velocity from the full (*p*_p − *p*_s), putting the suction acceleration entirely into the entry
loss, where the form here carries it explicitly. At this duty the two differ by one suction velocity
head, 0.27 bar against a 25 bar nozzle differential — about 1 %. `test_jet_pump.py` pins the
identity across four area ratios and four flow ratios.

**Geometry, and which root.** `References/Datasheets/322F001 Design Calculations.pdf` is a 12-page
scan with no text layer, so the areas are back-solved from the licensor's design point through the
same equations the model runs forward. The closure has **two** roots in the mixing area, and they
separate on throat velocity rather than on anything numerical: the large-area-ratio root puts 96 t/h
of carbamate through the throat at 96 m/s, which is an erosion rate. The root taken:

| quantity | value |
|---|---|
| nozzle throat *A*_t | 2.199 × 10⁻⁴ m² (**16.73 mm** dia) |
| mixing throat *A*_m | 2.028 × 10⁻³ m² (**50.81 mm** dia) |
| area ratio *b* | **0.1085** |
| nozzle velocity | 89.3 m/s |
| throat velocity | **15.0 m/s** |
| design *N* / *M*_vol / η | 0.2019 / 0.6662 / 13.45 % |

Those four numbers are the model's falsifiable prediction of the geometry inside that scan.

**The spindle acts on the nozzle, and the datasheet gives its law.** The 322F001 DDS (Remarks 3–5)
states the nozzle free area directly — variable over 40–100 % on a linear instrument map
*a*(θ) = 40 + 0.6θ, so the 74 % design opening sits at 84.4 % of full free area — and it is used
unchanged. `EJ_SPINDLE_R` (2.1517) was **not** an independent measurement of the same thing: the
engine's own comment records it as a suction-capacity rangeability back-solved from this same free
area turndown through the linear-ish capacity relation the old model assumed, and that assumed
relation is exactly what the momentum balance replaces. So a derived number is superseded by the
measured one it was derived from. The direction the old law asserted — closing raises entrainment —
is now derived, because a smaller area at constant motive mass raises ṁ_p²/(ρ_p *A*_t).

**Stall is a consequence.** The jet's shutoff head scales with ṁ_p², so the motive fraction at which
the pump can no longer make the design lift is √(lift/*C*₀). At this geometry *C*₀ = **4.988 bar**
against a 4.2 bar lift, i.e. the machine runs at **84 % of its own shutoff head**, and
`EJ_STALL_PHI_M` = **0.918**. That is far above the 0.20/0.35 knee `f_stall` carried, and it is a
property of the licensor's own duty numbers rather than of any assumption here — see *Weak spots*
below.

**Wiring.** Suction and discharge ride the live loop, anchored on their own design offsets from
PT-329201 (140.0 = 140.7 − 0.7 and 144.2 = 140.7 + 3.5), so the **lift** is the design 4.2 bar at
design and moves only when the two ends move apart; the old call passed no pressure at all. The
entrained stream carries the **live 322E003 sump composition** on a one-tick tear
(`s.y_scrub_ovf`), the same convention the 328 columns use on `y_737`/`y_748`, instead of the frozen
`EJ_CARB_FRAC`. The anchor is the licensor's design **pair** (`EJ_MOTIVE_NH3_DES`,
`EJ_SUC_TOT_DES`) — the same pair the geometry is back-solved from — not the boot-pinned settled
motive the retired `phi_m` normalised on; that choice decides where the residual ~0.1 % motive
inconsistency lands, and it lands on the settled sump level rather than on the first tick from a
fresh `State()`.

`ej_spindle_phi(θ)` is a **spindle-only** characteristic — the entrainment at the live nozzle area
over the entrainment at the design nozzle area, both at design motive. The domino terms that consume
it (the forward-carbamate draw into 322R001, the scrubber's `chi_sp` duty scaling) are attributing
an effect *to the spindle*, so feeding them the ejector's total capacity ratio would let a 0.1 %
motive deviation appear as a spindle move.

### A-6 — 328D001: the holdup did not fit the vessel

The handoff deferred this vessel on a source conflict. The conflict is real but it is not
symmetric. `References/328E004 328D001 328P002 Datasheets.md` gives the drum twice in one sentence:
inside diameter 1684 mm with a 1950 mm tangent-to-tangent cylinder, *"which yields a nominal
internal liquid capacity of 19 cubic meters"*. π/4 × 1.684² × 1.950 is **4.343 m³**. One of those is
a measurement of the steel and the other is arithmetic about it, and the arithmetic is out by 4.4×.

Two independent checks side with the dimensions:

* **Residence.** The drum passes 9950 kg/h at 1095 kg/m³, i.e. 9.09 m³/h. Half a 4.343 m³ shell is
  14.5 minutes of holdup, a normal reflux-drum inventory; half of 19 m³ would be 63 minutes.
* **The level taps.** The same datasheet puts LT-328501 on N6A *"near the bottom tangent line"* and
  N6B on the vertical shell. A DP cell reads the column between its taps, so 0–100 % of LT-328501
  **is** the tangent-to-tangent cylinder — which is why the heads are excluded here rather than
  guessed at. Their type is stated nowhere, so omitting them makes *V*_v a lower bound, i.e. the
  modelled response is if anything slightly stiffer than the drum's.

What was blocking A-6 was never the vessel: it was `R328_D001_M_FULL = 20 900 kg`, which is
19.09 m³ at the stream density — the same 19 m³ claim carried through into the inventory. A holdup
243 % of its own shell puts *V*_v on its 2 % floor, which is what made the coefficient come out 355×
and look unusable. With the holdup taken off the shell, the drum holds 2.19 m³ in a 4.34 m³ vessel,
*V*_v is an ordinary **2.150 m³**, and the coefficient is **≈15×** the shared 0.05 bar/(kg/s) it
replaces, not 355×. **This is the second time a design holdup has failed to fit its own vessel**
(322C001 was out by 69 % the other way).

The design pin does not move by construction — level is *M*/*M*_des × 50.5 and the state seeds at
*M*_des — and one tick from a fresh `State()` leaves `a328_d001_M` bit-identical and the node at
2.6 bar a exactly. What changes is the transient: the drum is 4.4× smaller and therefore 4.4× faster.

The node is self-regulating on two counts, which is why this stiffening is safe where the handoff
had to measure 328C003's first: PV-328202 passes more as the drum rises, and the 737 inlet passes
less, since its own driving differential is *P*_c002 − *P*_d001. Together those give a pole near
−0.03 /s — a 30 s node against a 0.25 s tick.

### D-2 — the four unit-328 vapour paths were all incompressible

| stream | was | is |
|---|---|---|
| 737, 328C002 OVHD → 328E004 → 328D001 | `M_des · sqrt(dP/dP_des)` | ISA-75.01 gas, fixed restriction |
| 748, PV-328203B relief → 328C002 | `M_des · (op/50)` | ISA-75.01 gas, linear trim |
| 750, 328C004 OVHD → 328C002 | `M_des · sqrt(dP/dP_des)` | ISA-75.01 gas, fixed restriction |
| 786, PV-328202 vent → 323E011 | `M_des · (op/50)` | ISA-75.01 gas, linear trim |

Three terms the incompressible forms could not carry: the **expansion factor** *Y* (a vapour is less
dense at the vena contracta than at the tap, so the same dP passes less mass than sqrt(dP) claims),
the **choke** (once dP/*p*₁ reaches *F*_γ·*x*_T the flow stops responding to the downstream node at
all — the property that matters if 328D001 is ever blown down; 786 runs at dP/*p*₁ = 0.57 against an
*F*_γ·*x*_T of 0.70, not choked at design but close, and the incompressible form had no way to find
that out), and the **composition** dependence ṁ ~ √*M*.

That last one is why the design molar masses are passed explicitly rather than allowed to cancel,
and why they are taken off the **back-solved** stage vectors `DES_C00x["y"]` rather than the PFD's
tabulated rows: the states seed on the back-solved vectors, so anchoring the flow law on the
tabulated ones would make the design point a slow leak. For the same reason `y_328_737`'s seed moved
from pure steam to `DES_C002["y"]` — that seed was inert while the flow was sqrt(dP), because
composition entered only through the molar accumulation term where generation and outflow are equal
at design and it cancelled; with √*M* in the flow itself the seed has to be the design vapour.

Both control valves take **linear** trim, which is the module's stated choice for vent duty and is
also what keeps the two controllers' loop gains exactly where they were: at the design stroke the
linear characteristic ratio *is* op/op_des, so PIC-328203 and PIC-328202 see the same first-order
gain they were tuned against and everything the change adds is pressure feedback, expansion and
choke. That resolves the handoff's specific worry about 328C003 in the opposite direction to the one
it feared: d(ṁ_748)/dP was **identically zero**, which is why the hydrolyser was called a node with
no self-regulation, and it now has some.

### D-8 — the last static transit, and it was in unit 328

`R3232_M718A_TAU_S = 45.0` was a flat first-order time constant on the 718A leg into 328D001,
labelled a transport lag and motionless from turndown to trip. The 45 s is a measurement and stays
exactly where it is; the line **inventory** is back-solved from it at the design flow
(*M* = ṁ_des·τ_des/3600 = 44.5 kg) and the live constant is that inventory over the live flow, so a
leg running at half rate lags twice as long. The first-order form is kept rather than swapped for a
pure dead time because a well-mixed line of holdup *M* passing ṁ obeys d*y*/d*t* = (*u* − *y*)ṁ/*M*
— which *is* this equation, with τ = *M*/ṁ. Making τ physical is the whole of D-8 here; changing the
shape of the response would be a separate claim and is not made.

With that, every transport path in the engine is flow-dependent: three `_delay` feed lines, five
`PROCESS_ROUTES` on `ConsequenceRoute.dead_time_s`, and this leg. `_foptd` has no callers.

### The harness step, and why it had to be fixed before any of this could be graded

`main.STEP_CAP` is 0.25 s and `sim_task` bounds every physical sub-step by it whatever the wall tick
or the speed multiplier; the constant's own comment records that 0.5 s *"is UNSTABLE"*. Two test
harnesses were integrating at 1.0 s (`test_ejector_spindle._settle`) and 2.0 s
(`_systest.run`) — four and eight times a step the engine declares unstable at two.

The mechanism is not new and is not in anything Phase 4b touched. SIC-321951's actuator lag is
`alpha = min(1, dt/2)`, so at dt ≥ 2 s the lag **collapses**, the speed loop becomes a pure
algebraic feedback whose characteristic roots are {1, −2}, and the NH3 motive flow rings at ±20 % of
stroke. That ringing was invisible while the CO2 feed and the ejector capacity were both pinned
constants that could not propagate it. D-5 and D-6 make both live, and the jet-pump closure amplifies
a motive deviation about tenfold at this machine's operating point, so it stopped being invisible.

Measured on `test_3_scrubber_heat`'s own CCW-cut scenario:

| step | 322E003 sump | PT-329201 after relax |
|---|---|---|
| 0.25 s (engine's own) | 50.0 → 45.8 → **49.8 %** — troughs and recovers, as report D-19 says | 140.75 |
| 2.0 s (old harness) | 50.0 → **100.0 → 100.0 %** — saturated | 145.53 |

Both harnesses now advance the same plant time in `STEP_CAP`-bounded sub-steps, exactly as
`sim_task` does. No tolerance was relaxed.

### Measured — 24 000 s free run from the design seed, dt = 0.25 s

The loop's settled-attractor drift (open since Phase 3, handoff §1f) is **materially smaller**, not
larger, with the whole of Phase 4b in:

| tag | HEAD at 24 ks | Phase 4b at 24 ks | change |
|---|---|---|---|
| PT-329201 | 140.70 → **138.117** (−2.583) | 140.70 → **139.229** (−1.471) | drift **−43 %** |
| 322R001 T_overflow | 183.00 → **185.605** (+2.605) | 183.00 → **184.614** (+1.614) | drift **−38 %** |
| 322E002 level | 50.00 → 49.139 | 50.00 → 49.435 | drift −31 % |
| 322E003 sump | 50.00 → 49.970 | 50.00 → 49.932 (at 8 ks) | comparable |
| 322R001 level | 80.00 → 80.616 | 80.00 → 80.102 (at 8 ks) | comparable, same sign |

No limit cycle appears anywhere in the 328 train despite the 15× stiffer 328D001 node and the four
new compressible overheads: over the same run 328C002/C003/C004/D001 stay inside the same bounded
±0.6 bar wander they had at HEAD.

### Weak spots, stated

* **322F001 runs at 84 % of its own shutoff head**, so it stalls below ~92 % motive flow unless
  HV-322602 is closed to compensate — which is what the spindle is for, and the datasheet's 40–100 %
  free-area band gives enough authority to hold it alive to about 80 % motive at a 41 % opening. This
  is a *property of the licensor's design duty*, not of an assumption: *N* = 0.202 with
  *M*_vol = 0.666 puts the machine low on its own flow curve and therefore high on its head curve,
  and the ratio lift/*C*₀ comes out between 0.78 and 0.95 for every plausible motive pressure. It is
  nonetheless a much more brittle machine than the `f_stall` knee at 0.35 implied, and any scenario
  that reduces NH3 rate without closing the spindle will now stall the ejector. `EJ_STALL_PHI_M` is
  published so a scenario can read it instead of discovering it.
* The same operating point makes entrainment about **ten times** as sensitive to motive flow as the
  linear `phi_m` was. The engine's seeded pump flow and its settled pump flow differ by ~0.1 %, which
  used to be invisible and now shows as a ~0.7 % steady offset on the 322E003 sump level.
* `p_crack` on the CO2 tie-in and the four jet-pump loss coefficients are stated representative
  values, not vendor data. The geometry is back-solved *through* them, so a different set moves the
  back-solved areas and leaves the design point exactly where it is.
* 328D001's heads are excluded from *V*_v because their type is not stated. *V*_v is therefore a
  lower bound.
* The required jet-pump lift is held at the design 4.2 bar rather than split into static and
  friction components, because no source gives the split. If it is largely friction it falls with
  ṁ² on turndown and the stall margin above is pessimistic.

## Phase 5 — G-VLE-3: the rigorous thermodynamic boundary reaches the HP synthesis loop

Phase 1 built a unified gamma-phi VLE service and then explicitly refused to put the 322 loop on it.
That refusal was correct at the time and is documented in `thermo_service`'s own module note: the
activity table was indexed in molalities, `_bracket` clamps rather than extrapolates, and the four
inerts had no property data at all — so a 322 call would have returned a frozen edge node wearing a
rigorous-looking call, which is strictly worse than an honest hardcoded vector.

This phase removes both blockers and wires the loop, and it separates very carefully what that does
and does not buy. Two things limited the old table. **One of them is fixed here and one is not.**

### The coordinate: a molality grid can never be wide enough

The loading basis was mol per kg of **water**, and the synthesis loop is where the water runs out:

| state | *T* | *N* (mol/kg water) | *C* (mol/kg water) |
|---|---|---|---|
| 322R001 overflow (stream 207) | 183 °C | 100.0 — 6.2× the top node | 22.4 — 3.2× |
| 322E003 off-gas feed | 183 °C | 869.3 — **54.3×** | 258.1 — 36.9× |

Those numbers are not large because the liquor is exotic. They are large because the denominator is
vanishing: a liquor with no water in it has an *infinite* molality. No finite molality grid can
cover that, and every one of them clamps silently at the edge.

In mole fractions the same two states are unremarkable — *x*<sub>H2O</sub> = 0.312 and 0.047 — so
the table is re-indexed on two **bounded** coordinates over the water + volatile sub-system:

$$s=\frac{n_{\mathrm{NH_3}}+n_{\mathrm{CO_2}}}{n_{\mathrm{NH_3}}+n_{\mathrm{CO_2}}+n_{\mathrm{H_2O}}}
\qquad f=\frac{n_{\mathrm{CO_2}}}{n_{\mathrm{NH_3}}+n_{\mathrm{CO_2}}}$$

with the molalities recovered exactly as *N* = 55.508·*s*(1−*f*)/(1−*s*) and *C* = 55.508·*s f*/(1−*s*).
The (*s*, *f*) rectangle is **full** — every physically realisable liquor maps into it — which an
(*x*<sub>NH3</sub>, *x*<sub>CO2</sub>) pair is not, since its upper triangle is unreachable and its
interpolation cells would straddle the hypotenuse.

`s` is bracketed on **logit**(*s*) = ln(*s*/(1−*s*)), and that is not an arbitrary choice:

$$\operatorname{logit}(s)=\ln (N+C)-\ln 55.508$$

identically. In the dilute limit — the only region where the old grid was ever valid — the new table
interpolates on **exactly the old coordinate**. That identity is what makes the re-index reviewable
as a coordinate transform rather than a new model, and it is pinned as a test.

The evidence that it *is* a coordinate transform is the module's own published validation, which
survives it and at two of three stages moves *toward* the plant:

| stage | *T* | *P*<sub>PFD</sub> | before (molality grid) | after (mole-fraction grid) |
|---|---|---|---|---|
| 323C003 | 135 °C | 4.10 bar a | 4.387 (+7.0 %) | **4.3516 (+6.1 %)** |
| 323F004 | 106 °C | 1.13 bar a | 1.328 (+17.5 %) | **1.2993 (+15.0 %)** |
| 323F010 | 99 °C | 0.46 bar a | 0.468 (+1.7 %) | **0.4683 (+1.8 %)** |

Envelope: *T* ∈ [80, 210] °C (was [80, 170]), *s* ∈ [10⁻⁵, 0.98], *f* ∈ [0.002, 0.78] — i.e. N/C from
500 down to 0.28. 9 × 15 × 9 = **1215 nodes**.

The two composition axes are bounded from **above only**, and that asymmetry is the physics rather
than a slip. Clamping at the top of *s* or *f* fabricates a frozen constant — the true activity keeps
rising past the last node and the table hands back the node instead, which is the exact failure mode
this whole phase exists to remove. Clamping at the bottom lands in the dilute limit, where every
volatile term is vanishing anyway: at the floor nodes the tabulated CO2 loading is 1.1 × 10⁻⁶ mol per
kg of water and *a*<sub>CO2</sub> is of order 10⁻⁸, so treating a liquor with less CO2 than that as
though it had exactly that much moves its bubble pressure far below anything this plant resolves.
Refusing there instead would put pure steam — and every 324 melt whose volatiles are traces — outside
every fitted model in the repository, which is not what the fit says and is not what the
pre-G-VLE-3 envelope test said either. **Temperature stays bounded on both sides**: below 80 °C the
activities are not vanishing, merely untabulated, and `_bubble_t_solve` already refuses there.

**Pressure is a declared band, not an axis**, and deliberately so: the Extended UNIQUAC activity
model has no pressure dependence at all, and the one term that would give it one — the Poynting
factor exp(*v*<sub>∞</sub>(*P* − *P*<sub>sat</sub>)/*RT*) — needs infinite-dilution partial molar
volumes this repository holds from no source. `VALID_PRESSURE_BARA = (0.02, 180.0)` therefore covers
the 144.2 bar synthesis loop and the 0.05 bar vacuum stages, and `classify` enforces it so that a
wild transient pressure **refuses** — and `k_ratio` degrades to the licensor's split — rather than
being answered by a model that has no opinion about pressure. The vapour side genuinely is valid
across that band: SRK returns *Z* = 0.80 and φ<sub>N2</sub> = 1.31 at 144 bar a, so it is doing real
work up there.

### The solver: it was an initial guess, not a domain limit

This is the finding that unlocked the gap, and it is worth not re-deriving.
`props_nh3co2h2o.speciate` is a damped log-space Newton on the R1–R5 speciation. Measured at 183 °C
along the N/C = 4.46 ray:

| *N* (mol/kg water) | residual from the stock guess |
|---|---|
| 16 – 40 | 10⁻¹² … 10⁻¹⁵ — converged |
| 50 | **9.9** |
| 100 | 17.5 |
| 869 | 122.6 |

and 200, 2 000 and 20 000 iterations return the **identical** non-solution at *N* = 50. That is a
basin-of-attraction failure of the dilute-solution ansatz, not a tolerance, not an iteration budget,
and not the model refusing. Seeded from a converged neighbour, the same solver — same equations,
same damping, same tolerance — reaches *N* = 869 / *C* = 195 in **five Newton steps at a residual of
8.5 × 10⁻¹⁴**.

So `speciate` gained one optional argument, `m_guess`, and `_build_table` marches:

* temperature outermost, seeding each node from the same (*s*, *f*) node one step back in *T*;
* then the *s*-neighbour, then the *f*-neighbour, then cold;
* with a **temperature bisection** fallback that halves the *T* step up to six times.

Marching order matters and was measured. A naive *s*-first march leaves 22 of 960 probe nodes
unconverged at 84 ms/node; temperature-first carries 958 of 960 at 15 ms/node, and the bisection
fallback takes it to 959. On the final graded grid the build is **1215/1215 converged**.

A node that fails is **stored with its flag cleared**, not dropped, and `_interp` reports
`corners_ok = False` if any of the eight corners it actually uses carries a cleared flag. That is
what turns the clamp from invisible into reportable: `in_grid` is now stricter than an axis test.

### The inerts: SRK constants and IAPWS G7-04 Henry constants

N2, O2, CH4 and H2 have no Extended UNIQUAC rows and never will — they are not electrolytes and
they do not speciate. They enter the only way a permanent gas can, and both halves are established
standard-state data rather than fitted parameters:

* **SRK critical constants** (`SRK_CRIT`) — the same class of public NIST/DIPPR values as the three
  rows already there, under the same *k*<sub>ij</sub> = 0 mixing rule that was already the stated
  choice precisely because no binary interaction data exists.
* **Henry's constants** — IAPWS Guideline **G7-04**, ln(*k*<sub>H</sub>/*p*₁\*) = *A*/*T*<sub>R</sub> +
  *B*(1−*T*<sub>R</sub>)<sup>0.355</sup>/*T*<sub>R</sub> + *C* e<sup>1−*T*R</sup>*T*<sub>R</sub><sup>−0.41</sup>,
  mole-fraction scale — the same scale as the existing Rumpf & Maurer NH3/CO2 constants, so they drop
  into the same partial-pressure sum with no basis conversion.

A van't Hoff fit was **refused** for a specific reason: permanent-gas solubility in water passes
through a minimum near 80–100 °C and rises again above it. A two-parameter fit anchored at 25 °C has
the solubility falling monotonically and is badly wrong by 183 °C — the loop's own temperature.
G7-04's three-term form reproduces the turn, which is why it exists.

**Validation, twice, neither of it circular:**

| gas | *k*<sub>H</sub> at 25 °C, model | literature (mole-fraction, bar) | error |
|---|---|---|---|
| N2 | 85 598 | 86 500 | −1.0 % |
| O2 | 43 640 | 44 000 | −0.8 % |
| CH4 | 39 479 | 41 300 | −4.4 % |
| H2 | 70 960 | 71 200 | −0.3 % |

and — the load-bearing one, because there is no direct inert datum at 183 °C anywhere in this
repository — CO2 is in the **same published table**, and this repository holds an **independent**
Rumpf & Maurer fit for it:

| *T* | G7-04 | Rumpf & Maurer (in-repo) | ratio |
|---|---|---|---|
| 25 °C | 165.6 MPa | 165.4 MPa | 1.0015 |
| 140 °C | 599.0 | 585.4 | 1.023 |
| 183 °C | 595.9 | 567.6 | **1.050** |
| 210 °C | 555.5 | 521.3 | 1.065 |

Two unrelated correlations agreeing to 5 % at the synthesis temperature is what licenses the four
inert rows at that temperature. The gap growing monotonically with *T* is the honest statement of
where the extrapolation begins to matter.

The SRK correction is not cosmetic here. At 144.2 bar a and 183 °C, φ<sub>N2</sub> = 1.224 and
φ<sub>H2</sub> = 1.291 against φ<sub>NH3</sub> = 0.758 and φ<sub>CO2</sub> = 0.889 (*Z* = 0.866) —
the light gases are 20–30 % from ideal *in the direction that makes them less soluble*, and every one
of those percent lands directly on an inert K-value.

### What is NOT fixed: the fit

The Extended UNIQUAC interaction parameters are a CO2-capture set regressed on **dilute aqueous
loadings below ~150 °C**. At *x*<sub>H2O</sub> = 0.047 and 183 °C the model is being evaluated far
outside its regression data, and the extended Debye–Hückel term in particular is being asked for an
ionic strength of ~130 mol/kg. The numbers it returns there are a smooth, thermodynamically
consistent **extrapolation**, not a prediction.

The measurement that says so plainly, and the one number in this section worth remembering:

> The model puts the 322R001 overflow's bubble pressure at **40.4 bar a at 183 °C**, against a loop
> that actually runs at **144.2**. A factor of 3.6 low.

Nothing in the engine uses that number, and the test suite deliberately pins the *fact* of the error
as a band rather than the value, so that a test never becomes an endorsement of an extrapolation.

### How the loop is wired: the anchored ratio

Every 322 split keeps the licensor's calibrated vector and multiplies it by a ratio of the model to
itself:

$$\alpha_{\text{live},i}=\alpha_{\mathrm{PFD},i}\cdot\frac{K_{i,\text{model}}(\text{live})}{K_{i,\text{model}}(\text{reference})}$$

A systematic offset in an extrapolated activity coefficient **divides out** of that ratio. Its slope
does not — and the slope is exactly what the frozen vectors reported as zero.

`thermo_service.k_ratio` evaluates the reference on the **same composition** as the live point unless
a constant design composition is supplied. So at the reference (*T*, *P*) every argument of the two
K-value calls is identical, the two K-values are the same IEEE double, and the quotient is **exactly
1.0** — not 1.0 within a tolerance, and with no identity short-circuit hiding a residual. That is
what carries the design seed, and it is the reason this default was chosen: the HP splits are
anchored to vectors calibrated at a stated (*T*, *P*), and their design *composition* is assembled
from live streams and is not a constant anywhere in the engine.

`k_ratio` does **not** call `k_values` bare. That was a defect caught in this phase: `k_values` with
no vapour composition returns φ = 1.0 — documented, and correct as the first pass of the flash's
successive substitution, which then feeds the converged vapour back in. `k_ratio` has no such loop,
so calling it bare silently made the pressure leg the naive *P*<sub>ref</sub>/*P*; measured, it
reproduced 144.2/130 **to the last bit**. `_k_srk` seeds the vapour from the partial pressures
themselves (the same ideal seed `bubble_p` uses) and takes the fugacity once on it.

Two transforms consume the ratio. They are the same algebra at two limits, not two models:

| transform | form | where |
|---|---|---|
| `_ratio_shift_frac` | θ′ = *r*θ/(1 + (*r*−1)θ) | units that are not flashes — a stripping column, an absorber |
| `_anchored_split` | back-solve *K* from θ, scale by *r*, **re-solve Rachford–Rice** | units that are flashes — the condenser, the reactor top |

The first is the second with the phase ratio cancelled: back-solving *K* from θ = *K*ψ/(1+ψ(*K*−1))
and re-inserting *K r*, the (1−ψ) cancels and ψ drops out entirely. Both are exact identities at
*r* = 1.0 **with no branch** — (*r*−1.0) is exactly 0.0 there, so the first returns θ/1.0.

`_ratio_shift_frac` also fixes a real defect it inherited: it maps [0,1] onto [0,1] for any *r* > 0,
where the `× eta_P` multiply it replaces could not. At η<sub>P</sub> = 1.15 the N2 strip fraction
went to **1.148** before the clamp caught it — the column was asked to strip more nitrogen than it
was fed, and the excess was silently truncated.

### The three wirings, and the one that was refused

Four sites were nominated. Three are wired; 322E002 is not, and the reason is in the next section.

| target | was | now | reference pair |
|---|---|---|---|
| `REACT_THETA_OG` | frozen vector | `_anchored_split` at the live overflow *T* and loop *P* | (183 °C, 140.7 bar a) |
| `STRIP_FRAC_DES` | scalar `eta_P = clamp(2 − P/P_des, 0.85, 1.15)` | per-species pressure ratio through `_ratio_shift_frac` | (183 °C, 144.0 bar a) |
| `SCRUB_OFFGAS_KMOLH_DES` | frozen vector × one scalar | composition-only re-partition on PT-329201 | (114 °C, 140.7 bar a) |
| `_hpcc_flash_split` | Clausius–Clapeyron `exp[(ΔH/R)Δ(1/T)] × P_des/P` | **unchanged — see below** | — |

Two of the four were not frozen vectors at all. `_hpcc_flash_split` already carried a live
Clausius–Clapeyron response in both *T* and *P*, and `STRIP_FRAC_DES` was already modulated by
`eta_T_steam · eta_co2 · eta_P` with `eta_P` an explicit pressure law. On those two sites the work
was replacing one slope with another, not connecting a constant to thermodynamics — which matters,
because a replacement can be *worse* in a way that adding a derivative to a constant cannot.

**The design seed cannot audit this work.** Every form involved, old and new, at all four sites, is
exactly 1.0 at the design point by construction. The boot pin stayed 103/103 bit-identical through
every configuration tried, including the one that broke the loop. Bit-exactness at *t* = 0 is a
necessary condition here and an almost uninformative one; the transient is what carries the signal.

* **The scrubber re-partition is composition-only.** `offgas` is the sole stream among these sites
  that *leaves* the HP loop (HV-322604 → 322C001); the others partition material that recirculates.
  Letting a K-ratio move the vented **total** closes a positive feedback through loop inventory — a
  higher PT-329201 lowers every *K*, lowers the vented moles, retains more inventory, and raises
  PT-329201 again. Measured at −0.41 % of vent per bar: weak per tick, but it integrates. The vent
  rate is not a thermodynamic quantity in any case — HV-322604 and the pressure controller set it,
  and a real valve passes *more* at higher upstream pressure, the opposite sign to the one an
  equilibrium *K* supplies. So the total is renormalised back to the licensor's pinned value and
  only the composition rides the ratio.
* **`eta_P` is replaced, not stacked.** Both it and the ratio model the pressure dependence of the
  strip split; multiplying both would count the loop pressure twice. Both are exactly 1.0 at
  `STRIP_P_DES_BARA`, so the swap is bit-exact.
* **The scrubber vent rides PT-329201 and deliberately not TT-322011**, and that is a measured
  result rather than caution. TT-322011 in this model is not a state: it is the correlation
  `114 + 120·(AT-322701 − N/C_des) + 20·θ_dev`, whose 120 °C per N/C unit is a *fitted* gain.
  Feeding it into a rigorous K-ratio multiplies that fitted gain by a thermodynamic derivative, and
  the product is not a better model of anything. It was tried first, and it drove the 322C001 design
  liquor's stationarity residual from 8.1 × 10⁻⁹ to 3.7 × 10⁻⁴ — 45 000× — and **reversed the sign**
  of the vent NH3 slip against off-gas throughput. A derivative is only as good as the input it
  differentiates; a correlated input is the wrong one. PT-329201 is a real measurement, so the vent
  split rides that and nothing else.
* **Only the pressure moves in the stripper's ratio.** Its reference temperature *is* its live
  temperature, so the *T* terms of the two K-values cancel identically. The stripper is a
  steam-driven contactor whose bottoms temperature is an **output** of the duty chain; that thermal
  response is already carried by `eta_T_steam`, and putting the live temperature into the ratio as
  well would double-count the same steam heat.

Structurally non-distributing species are never moved by either transform. θ of exactly 0 (urea:
never boils) or exactly 1 (O2/CH4/H2 at the reactor top: never dissolve) are *structural*, not
calibrated, and moving them would be a new claim with no datum behind it.

### Why 322E002 keeps its calibration: common mode versus selectivity

The HPCC was wired to the rigorous ratio first, and it broke the synthesis loop's ability to
recover from a disturbance. `test_3_scrubber_heat` cuts CCW to 322E003, lets PT-329201 rise, then
restores CCW and requires the excess over a matched no-cut control to decay. It went from
`+0.200 → +0.100 bar` (decaying) to `+0.400 → +1.200 bar` — still climbing after the disturbance
had been removed. The cause was isolated by running the scenario with each wiring individually
inert:

| configuration | excess₁ → excess₂ | verdict |
|---|---|---|
| HEAD | +0.200 → +0.100 | 8/8 |
| all four wirings live | +0.400 → +1.200 | 7/8 |
| reactor inert | +0.400 → +1.300 | 7/8 |
| scrubber vent total conserved | +0.400 → +1.200 | 7/8 |
| all four inert | +0.300 → +0.100 | 8/8 |
| **HPCC inert, other three live** | **+0.300 → +0.000** | **8/8** |

The rigorous form is not *rougher* than the one it replaced. Traced over the scenario — 15 120
samples spanning 169.8–179.8 °C and 140.6–141.8 bar a — it moved total vapour fraction over a span
of 0.062 against Clausius–Clapeyron's 0.683, with a largest tick-to-tick step of 3.3 × 10⁻² against
6.5 × 10⁻¹, and left the grid on 3 samples out of 15 120. It is an order of magnitude gentler on
every aggregate measure and it is the one that fails. The difference is per species. At
175.7 °C / 141.2 bar a:

| form | NH3 multiplier | CO2 multiplier |
|---|---|---|
| Clausius–Clapeyron | 1.1990 | 1.1990 |
| rigorous *K*-ratio | 1.1540 | 0.4829 |

`HPCC_FLASH_DH` carries the same enthalpy for NH3 and CO2, so the calibrated form is **common
mode**: it changes *how much* vapour leaves the condenser and not *what* leaves it. The rigorous
ratio is **differential**: it halves the CO2 multiplier while raising NH3, which changes the N/C of
the carbamate recycle returning to 322R001, which changes reactor conversion, which feeds back to
loop pressure. The loop has a restoring force against an inventory shift and none against a
composition shift, so it settles on a new operating point instead of returning.

The differential is also the least defensible number this surface produces. The Extended UNIQUAC
set is extrapolated in the synthesis loop — it puts the 322R001 overflow bubble pressure 3.6× low —
and a ratio cancels a systematic offset only where that offset is multiplicative and
*T*-independent. For CO2 over a carbamate melt at 140 bar it is neither. A factor-2 change in the
CO2 multiplier across 5.7 °C is the extrapolation talking, not the chemistry. So 322E002 keeps the
calibration whose selectivity was measured, `HPCC_FLASH_DH` stays load-bearing, and this site is
the first candidate to revisit if the parameter set is ever refitted for the loop (§ *What is NOT
fixed: the fit*).

### The K-values the inerts actually generate

Apparent *K*<sub>i</sub> = *y*<sub>i</sub>/*x*<sub>i</sub> on the total-species basis, at each wired
unit's design state, through `_k_srk` (i.e. with the SRK fugacity applied):

| state | *T* °C | *P* bar a | *K*<sub>N2</sub> | *K*<sub>O2</sub> | *K*<sub>CH4</sub> | *K*<sub>H2</sub> | *K*<sub>NH3</sub> | *K*<sub>CO2</sub> | *K*<sub>H2O</sub> |
|---|---|---|---|---|---|---|---|---|---|
| 322R001 product (reactor top) | 183 | 140.7 | 499.4 | 354.2 | 323.9 | 307 | 0.560 | 0.125 | 0.184 |
| 322E001 feed (stripper) | 183 | 144.0 | — | — | — | — | 0.658 | 0.141 | 0.308 |
| 322E002 feed (HPCC) | 170 | 140.7 | 601.8 | 419.4 | — | — | 0.365 | 0.375 | 0.197 |
| 322E003 feed (scrubber) | 114 | 140.7 | 815.9 | 523 | 494.6 | 484 | 0.071 | 0.416 | 0.022 |

A dash is a species absent from that feed vector — *x*<sub>i</sub> = 0 makes *K* undefined and the
guard returns 0 — not a solver failure. Stream 207 carries no inerts at all, which is why the
stripper row is empty.

Three things in that table are worth reading rather than skipping:

* the inerts sit **three orders of magnitude** above the condensables (300–800 against 0.07–0.66),
  which is the whole point: a permanent gas over a hot carbamate melt goes to the vapour and stays
  there. Before this phase they had no *K*-value at all;
* they get **more** volatile as the temperature falls (*K*<sub>N2</sub> 499 at 183 °C against 816 at
  114 °C), because the Henry constant is still on the far side of its own maximum — this is the
  solubility turn that a van't Hoff fit would have got backwards;
* the ordering N2 > O2 > CH4 > H2 follows the Henry constants at 183 °C (68 740 / 46 958 / 42 155 /
  42 474 bar), with CH4 and H2 nearly tied, exactly as the correlation puts them.

The supporting SRK coefficients on a representative loop vapour at 183 °C and 144.2 bar a are
φ<sub>N2</sub> = 1.310, φ<sub>O2</sub> = 1.201, φ<sub>CH4</sub> = 1.084, φ<sub>H2</sub> = 1.399, at
*Z* = 0.801.

### Safeties

`k_ratio` falls back to **1.0 per species** — i.e. to the licensor's own split — on `OutOfDomain`, a
non-convergent solve, a non-finite value, or any of `ValueError` / `ZeroDivisionError` /
`OverflowError` / `KeyError`. It never raises into the tick and never returns a NaN, so a true
non-convergent transient degrades to the calibrated vector rather than freezing the state. Each
species is additionally bounded to [0.02, 50]: a 50× move in a condenser split is the model leaving
its useful range, not a real event, and the anchored vector is the better answer there.

### Cost

| | before | after |
|---|---|---|
| activity-table nodes | 800 | **1215** (+52 %) |
| table build (cold) | 26.7 s | **19.8 s** |
| ms per node | 33.4 | **16.3** |
| cached load at boot | 0.004 s | 0.044 s |
| cache file | 67.4 kB | 107.7 kB |
| `k_ratio` | — | 176 µs, three sites per tick |
| engine tick | 10.51 ms (24× real time) | ≤ ~11.2 ms (+6.7 %) |

The tick figure was measured with all four sites calling `k_ratio`; 322E002 no longer does, so
+6.7 % is now an upper bound rather than the current cost.

**The boot penalty is negative.** The rebuilt grid is 52 % larger and builds 6.9 s *faster*, because
continuation seeding replaces the cold dilute ansatz at every node: 16.3 ms/node against 33.4. The
module's own docstring had claimed "~5 s" for the old build; it was 26.7 s.

### The memo that was written, measured, and then removed

`k_ratio` is the obvious candidate for the quantised memo `flash` and `bubble_t` both use — the
engine calls it once per wired unit per tick with arguments that have barely moved. It was written,
and it worked: 9.6 µs warm against 176 µs cold, a 6.7 % tick saving. **It is gone, and the reason it
is gone matters more than the microseconds.**

A ratio is not a flash. Every one of these calls has a reference point that must return exactly 1.0,
and the engine spends *thousands* of consecutive ticks near that point — the entire boot settle does.
On the quantisation grid (0.02 °C, 10⁻⁴ bar, 100 ppm) a settle tick 60 ppm away in composition keys
**identically** to the design state, so whichever of the two ran first answered for both.

Measured: it moved the pinned 322E003 vent vector by 1.1 × 10⁻⁴ kmol/h on CO2 — and it did so **only
when the boot-pin cache missed and the full settle ran**. On a warm tree the design pin was exact and
the test passed; on a cold tree it failed. A memo that silently breaks a design pin depending on
whether a cache file exists on disk is worse than 700 µs a tick, so it was removed rather than tuned.

If this ever needs to be fast, the correct fix is an **exact-argument key** — which hits every tick at
a fixed point and misses honestly during a transient — not a finer quantum. A finer quantum shrinks
the window without closing it.

### Verification

* Design seed after one tick: **103 of 103 probed state fields bit-identical to HEAD**.
* Grid: 1215/1215 nodes converged, residual ≤ 10⁻⁸.
* The three validated 323 bubble pressures survive the re-index (table above).
* `k_ratio` identity at all three wired HP design states is the exact IEEE 1.0 (and was also
  exact at the HPCC state before that site was reverted — see § *Why 322E002 keeps its
  calibration*; the identity holding is what makes the design seed unable to audit this).

## Assumptions and Limits

- The model is reduced order: calibrated design conductance scales with process flow because no off-design exchanger datasheet is available.
- LP steam is saturated at live header pressure; detailed two-phase bundle hydraulics are outside scope.
- PV-329207B uses a lumped incompressible square-root pressure-drop law.
- Ejector and scrubber relationships preserve the design point and reproduce training-response direction, not nozzle-resolved CFD.
- **G-VLE-3**: the Extended UNIQUAC parameter set is *extrapolated* in the 322 loop (a dilute-aqueous CO2-capture regression, below ~150 °C, evaluated at *x*<sub>H2O</sub> = 0.047 and 183 °C). Absolute HP-loop VLE numbers are not used anywhere; only the anchored ratio is.
- **G-VLE-3**: inert Henry constants are for water as the solvent, applied to a solvent that in the synthesis loop is mostly ammonia and carbamate. No published inert solubility in molten carbamate exists in this repository.
- **G-VLE-3**: 322E002 is deliberately NOT on the rigorous boundary. The extrapolated set's per-species *T*-derivative reorganises the HPCC vapour composition rather than its quantity, and the synthesis loop has no restoring force against a composition shift. Measured, isolated and recorded in § *Why 322E002 keeps its calibration*.
- **G-VLE-3**: the stripper's pressure sensitivity is now ~8.6× weaker than the `eta_P` law it replaced (−0.081 %/bar on the design NH3 split against −0.694 %/bar). This is the correct behaviour for an equilibrium split fraction — at φ = 0.85 a −0.69 % change in *K* moves the split by −0.09 %, and the old form applied the full −0.69 % straight onto φ regardless of saturation, which is how N2 reached 1.148 before the 0.999 clamp caught it. But 322E001 is a rate-limited falling-film contactor, not an equilibrium stage, so the true sensitivity is likely between the two. The loop's damping is correspondingly lighter than at HEAD; `test_3_scrubber_heat` still relaxes (+0.300 → +0.100 bar against HEAD's +0.200 → +0.100).
- **G-VLE-3**: no Poynting correction is applied. At 144 bar the partial-molar-volume term is worth roughly +15 % on an NH3 or CO2 partial pressure, and no sourced infinite-dilution partial molar volumes are held here to compute it with. It is very nearly constant across the loop's operating band, so it is absorbed by the ratio form.

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
- IAPWS Guideline G7-04, *Guideline on the Henry's Constant and Vapor-Liquid Distribution Constant for Gases in H2O and D2O at High Temperatures* (2004) — the four inert Henry correlations, and the CO2 row used to cross-validate them against the in-repo Rumpf & Maurer fit.
- Voskov and Voronin, *J. Chem. Eng. Data* 61 (2016) 4110–4125, DOI `10.1021/acs.jced.6b00557`.
- Zhang et al., *Computers & Chemical Engineering* 29 (2005) 983–992, DOI `10.1016/j.compchemeng.2004.10.004`.
