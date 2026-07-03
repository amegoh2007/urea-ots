# DCS Anchor Dynamics — Urea Startup 28-06-2025

_Analysis date: 2026-07-03 · dataset `Urea_Startup_28-06-2025_Trends.xlsx` · companion to
`dcs_anchor_dynamics_2025-06-03.md` (same anchor-only methodology)._

## 1. Dataset provenance and honest resolution

Single sheet **"30s Interpolated (SYNTHETIC)"**, self-labelled:
*"SYNTHETIC - linear interpolation between hourly measured points. Sub-hour values are NOT
measured."* 721 rows at uniform 30 s, 10:01 → 16:01.

**Knot recovery** (piecewise-linearity breakpoint detection, midpoint residual > rounding
tolerance 0.011, plus full-series reconstruction check — max reconstruction error ≤ rounding
for **all 35 tags**): exactly **7 true measured anchors**, on the hourly grid
10:01, 11:01, …, 16:01. Every other row is pure linear interpolation and carries **zero
dynamic information**.

**Resolution statement (governs every claim below):**
- Anchor spacing = **3600 s**. No dead time, lag, or slew rate is extractable below this.
- Dead times: **brackets only** (≤ 3600 s).
- Slew rates: **lower bounds only**.
- Gains between anchors: **secants**, confounded by the simultaneous load ramp
  (0 → 97 %) and pressurization (3.3 → 135.7 bar g) — not clean partial derivatives.
- Extractable cleanly: quasi-static maps, steady-state lineups (last 3 anchors,
  load 92.2–97.0 %).

## 2. Anchor matrix (7 snapshots × 35 tags, verbatim)

```
ts           10:01  11:01  12:01  13:01  14:01  15:01  16:01
t_s              0   3600   7200  10800  14400  18000  21600
UREA-LOAD        0   60.7   65.3   80.8   92.2   93.9     97
PIC-322203   102.7  112.9  134.5  144.1  145.3  142.5  141.7
PV-322203     64.9     35     27     19      5      0      0
FY-322403        0  17501  18735  23013  26114  26595  27419
TT-322017    101.4  105.2  109.7  114.2    115  114.6  113.7
TT-322013    152.1  185.5  182.1  186.4  186.9  186.9  186.9
FY-321401        0  37.35  37.53  32.97  40.47  41.98  43.47
TT-321001     24.1   24.2   29.3   29.7     29   28.8   24.7
SIC-321951    -0.2    108  110.1   96.4  119.7  123.4  126.8
TT-321020     22.5   22.3   30.9   31.2   30.9   30.4   26.3
TT-322012    110.1  133.8  115.4  122.3  132.9  123.4  117.1
HV-322602        0     40     40     40     50     63     60
PT-329201      3.3  104.1    130  137.8  139.6  136.4  135.7
TT-322011    134.1  147.2  119.3  115.9    135  132.3  142.4
HIC-322604     100     50     60     80     85     83     80
TIC-329005   124.6  109.6    105  100.4   90.1     90   88.1
TDY-329125     0.2   18.5   13.3   14.8   19.6   21.4   15.1
TV-329005     24.4   30.9   30.5   30.4   33.3   33.6     32
TT-322010    142.1  164.8  167.2  169.9  170.5  170.6  170.1
TT-322008    147.3  167.2  167.4  173.3  173.9  173.1  171.7
TT-322007    146.2  167.8  168.3  175.3    177  176.6  174.5
TT-322006    147.1  169.2  171.8  178.6  181.1  181.3  179.5
TT-322005    155.9  174.1    174  179.6    183  183.5  182.3
TT-322009    154.8  177.9    179  182.4  185.1  185.5  184.1
TT-322014    114.9   99.3    173  181.1  183.5    184  182.5
AY-322701     3.71   3.77    3.5   3.14   3.02   3.08   3.14
LT-322504-3   0.03   9.55  72.25  83.66  99.73  99.94  99.94
HIC-322605       0      0   29.6   39.5   44.5     46     49
LIC-322501     0.2     57     67   63.7   67.5   61.1   73.2
LV-322501        0      0   17.6   37.1   42.8     42   45.4
PIC-329204    13.1   12.8   14.2   17.4     18   18.4   18.7
FY-329403     51.5     35   53.3   68.7   60.1   55.8   61.6
HIC-329601     100    100      0      0      0      0      0
PT-323201     0.06   1.04   2.27   4.75   5.29   4.19   5.01
PT-329251     21.9   21.9   21.5     22   21.9     22   21.9
```

## 3. Target-by-target findings

### T1 — ~100 % load baseline lineup (16:01, UREA-LOAD 97.0 %)

Plant is effectively at design: NH₃ feed 43.47 t/h @ 126.8 rpm (model pin 43.4 t/h @
127.0131 rpm incl. flush), CO₂ 27 419 Nm³/h = 53.84 t/h = 98.6 % of design 54.618 t/h.

| Valve | Model `*_DES` | Field 16:01 | drift 14–16 h | Verdict |
|---|---|---|---|---|
| PV-322203 (vent) | op = 0 | 0 | 5.0 | **match** |
| HV-322602 | 74 | 60 | 13.0 (op-moved 40→63→60) | operator practice, no edit |
| HIC-322604 | 50 | 80 | 5.0 (85→80 drifting) | document only |
| HIC-322605 | 60 | 49 | 4.5 (still ramping 44.5→49) | unsettled anchor, no edit |
| TV-329005 | 50 | 32 | 1.6 | TIC SP off-design (88.1 vs 124.6 °C at t0), no edit |
| **LV-322501** | **82** | **45.4** | **3.4 (stable 42–45.4 over 3 h)** | **real discrepancy → §5** |

Hand-valve mismatches (HV-322602, HIC-322604/605, TV-329005) sit on operator-positioned or
off-design-setpoint services; attributing them to model error would fabricate constants
(sourcing law). Documented, not edited.

### T2 — NH₃ pump quasi-static map

SV-321950/SV-321951 **not in workbook** → torque-converter step dynamics not extractable.
Quasi-static map on the 6 non-zero anchors, through-origin OLS:

$$\dot m_{NH_3} = 0.34150\,N \quad \text{t/h per rpm},\qquad \text{RMSE}=0.273\ \text{t/h}$$

residuals (t/h): [+0.468, −0.070, +0.049, −0.408, −0.162, +0.167].
Committed **field** map (03-06 anchor fit) 0.34174 t/h/rpm → deviation **−0.07 %**. This is the
**third independent confirmation** of the DCS FY-321401 mass map (field curve → 03-06 anchors →
28-06 anchors). **No edit.**

Engine-side note (sim-verification 03-07): the engine's implemented mass map at design density is
$k_{eng} = V_{rev}\,\eta_v\,60\,\rho_{des}/1000 = 0.0094672 \times 0.980 \times 60 \times 604.8/1000
= 0.33667$ t/h/rpm — there is **no** 0.34174 constant in code. The +1.4 % field-vs-engine gap is
exactly the density-basis multiplier already documented in dcs_tuning_parameters.md §4.3(a):
$0.33667 \times 613.5/604.8 = 0.34152$ (+0.005 % vs the 28-06 fit). Caveat: 28-06 feed was *warm*
(TT-321001 24.1–29.7 °C, mean ≈ 27 °C) yet FY-321401 returned the same slope as the cold 03-06
startup (Δ −0.07 %); a true $\rho(T)$ mass flow would differ ≈ 2.3 % between the two startups.
This implies FY-321401 is computed with a **fixed** density in the DCS flow block, not live-T
compensation. Not resolvable from the workbook (no independent density/mass reference) → sourcing
law, documented only. Consequence: SIC-321951 rpm display will read ≈ 1.4 % high vs DCS at matched
mass flow; mass conservation unaffected (rpm↔mass mapping cancels in the CAS reconstruction).

### T3 — HV-322602 coupling (partial: TT-322002 absent)

Secant gains HV-322602 → TT-322012 across the four moves:

| span | ΔU (%) | ΔT (°C) | K (°C/%) |
|---|---|---|---|
| 0–3600 s | +40.0 | +23.7 | +0.593 |
| 10800–14400 s | +10.0 | +10.6 | +1.060 |
| 14400–18000 s | +13.0 | −9.5 | −0.731 |
| 18000–21600 s | −3.0 | −6.3 | +2.100 |

K ∈ [−0.73, +2.10] °C/% — **sign-unstable** (load/pressure confound dominates TT-322012).
Not usable as a transfer-function gain. TT-322002 not in workbook.

### T4 — HV-322603 coupling

**Tag absent from workbook.** Not extractable from this dataset.

### T5 — TIC-329005 cascade

Secants per span (confounded by the 0→97 % load ramp):

- → PT-329201: K ∈ {−6.72, −5.63, −1.696, −0.175} bar/°C
- → TDY-329125: K ∈ {−1.22, +1.13, −0.326, −0.466} (sign-unstable)
- → TT-322011: K ∈ {−0.873, +6.065, +0.739, −1.854} °C/°C (sign-unstable)

The monotone-looking PT secant is spurious: TIC-329005 PV fell 124.6→88.1 °C while P_syn
rose with load — correlation via the ramp, not causation. **No usable gains.**

### T6 — Reactor thermal dead time

Feed introduction lies in (10:01, 11:01]. **All** reactor temperatures already risen by the
11:01 anchor:

| tag | 10:01 → 11:01 (°C) | rise |
|---|---|---|
| TT-322005 | 155.9 → 174.1 | +18.2 |
| TT-322006 | 147.1 → 169.2 | +22.1 |
| TT-322007 | 146.2 → 167.8 | +21.6 |
| TT-322008 | 147.3 → 167.2 | +19.9 |
| TT-322009 | 154.8 → 177.9 | +23.1 |
| TT-322010 | 142.1 → 164.8 | +22.7 |
| TT-322014 | 114.9 → 99.3 | −15.6 (bottom inlet, cold-feed dip first) |

**t_d ≤ 3600 s is the only honest statement** — the requested "exact dead time in seconds"
does not exist in this dataset. The 03-06 dataset's tighter feed-introduction bracket
(≤ 572 s) and the committed `FEED_TD_S = 345 s` stand unchallenged.

### T7 — level lag (tag correction: LT-322504 is the REACTOR level, not HPCC)

The task labelled T7 "HPCC level lag — feed → LT-322504", but LT-322504 is the **reactor
322R001 narrow-band level** (model: `REACT_LEVEL_NLL_PCT`, datasheet UD-AU-322-EC-0006
nozzle N7; HPCC level is LT-322E002). The HPCC level tag is **absent from the workbook** →
HPCC level lag not extractable from this dataset.

Reactor fill, LT-322504-3: [0.03, 9.55, 72.25, 83.66, 99.73, 99.94, 99.94]. Fill onset
inside the first interval (9.55 % by 11:01); steep phase (9.6→72.3 %) inside the second.
**Dead-time bracket ≤ 3600 s; not finer.**

Observation (documented, no edit): the field reading plateaus at **99.94 %** through
92–97 % load, while the model design pin is **80 %** NLL on the N7 narrow band. A single
redundant transmitter (suffix -3) with possible span/zero configuration differing from the
datasheet band, and a narrow band that saturates near the top tap, make this ambiguous —
recalibrating the NLL pin from it would fabricate a constant (sourcing law).

### T8 — Steam system

**PT-329206 and TT-322004 both absent from workbook** → both sub-targets not extractable.
(PIC-329204 present, 13.1 → 18.7 bar g with load; its pair TT-322004 is missing.)

### T9 — N/C ratio vs reactor temperature profile

Loop analyzer AY-322701: [3.71, 3.77, 3.50, 3.14, 3.02, 3.08, 3.14] — settles 3.02–3.14 at
high load, consistent with model design values (offgas N/C ≈ 3.000, HPCC melt ≈ 3.123).
Secant gains ΔTT/ΔNC (anchors 2–7, spans with |ΔNC| ≥ 0.05):

| tag | K per span (°C per N/C unit) |
|---|---|
| TT-322005 | +0.4, −15.6, −28.3, +8.3, −20.0 |
| TT-322006 | −9.6, −18.9, −20.8, +3.3, −30.0 |
| TT-322007 | −1.9, −19.4, −14.2, −6.7, −35.0 |
| TT-322008 | −0.7, −16.4, −5.0, −13.3, −23.3 |
| TT-322009 | −4.1, −9.4, −22.5, +6.7, −23.3 |
| TT-322010 | −8.9, −7.5, −5.0, +1.7, −8.3 |
| TT-322014 | −273.0, −22.5, −20.0, +8.3, −25.0 |

Sign is predominantly negative (higher N/C → cooler profile, physically sensible: excess NH₃
quench + lower carbamate condensation duty per pass), but magnitudes scatter ±100 % because
load (60.7→97 %) and P_syn (104→140 bar g) move simultaneously. **Directional confirmation
only; no gain worth hard-coding.**

### T10 — PV-322203 → FY-322403

| span | ΔU (%) | ΔF (Nm³/h) | K (Nm³/h/%) |
|---|---|---|---|
| 0–3600 s | −29.9 | +17 501 | −585 |
| 3600–7200 s | −8.0 | +1 234 | −154 |
| 7200–10800 s | −8.0 | +4 278 | −535 |
| 10800–14400 s | −14.0 | +3 101 | −222 |
| 14400–18000 s | −5.0 | +481 | −96 |

K scatters 6× (compressor loading, recycle, and suction-side moves are all inside each
3600 s span). **Lag not extractable; gain not separable from compressor operating point.**

## 4. Cross-validations

### X1 — PT-329201 FOPTD, τ cross-check

$$G(s) = \frac{K_p\,e^{-t_d s}}{\tau s + 1}$$

Fit on all 7 anchors (t₀ = 10:01): P₀ = 3.3 ± 2.1, P_f = 137.6 ± 1.2 bar g,
**τ = 2246 ± 500 s**, t_d = 488 ± 700 s, R² = 0.9991.

τ falls **outside** the 03-06 validation band [2884, 4055] s — but this fit is
under-resolved: the first anchor after feed-in (104.1 bar g) already sits at **76 % of the
pressure span**, so τ is set by a single rising point trading off against t_d (±700 s
uncertainty spans the whole feasible range). Physically, the apparent closed-startup τ is
**trajectory-dependent** (this startup loaded to 60.7 % inside the first hour — faster ramp
→ smaller apparent τ), not a plant constant. **Validation band stays [2884, 4055] s, tied
to replication of the better-resolved 03-06 scenario. No model change.**

### X2 — LV-322501 installed-capacity calibration

Model drain law (main.py):

$$\dot m_{drain} = \dot m_{des}\cdot\frac{op}{OPEN_{DES}}\cdot\sqrt{\frac{P_{syn}-4.0}{140.7-4.0}}$$

Inverting at the 16:01 anchor (op = 45.4 %, load = 0.97, P_syn = 136.7 bar a,
f_dp = 0.9853):

$$OPEN_{DES} = \frac{op \cdot f_{dp}}{load} = \frac{45.4 \times 0.9853}{0.97} = 46.1\ \%$$

Cross-checks: 46.4 % (14:01), 44.2 % (15:01). Level-drift imbalance over the window ≈ 0.4 %
of drain flow — negligible. Model constant was **82.0 %** (datasheet-predicted stroke at
norm flow). The installed flashing service passes design flow at ~46 % → datasheet
over-stated required travel ~1.8×. **This is the one real, robust model discrepancy in the
dataset → constant edited (§5).**

### X3 — LIC-322501 direct action (corroboration)

level PV: [0.2, 57, 67, 63.7, 67.5, 61.1, 73.2] · LV: [0, 0, 17.6, 37.1, 42.8, 42, 45.4].
Valve held shut while level rose 0.2 → 57 % (at/below SP), opened only after level exceeded
~57–67 % → **direct-acting closed loop confirmed on an independent dataset**; the
2026-07-03 verdict on the 03-06 anomaly (MV = 102.8 % is a DCS positioner/output-span
artifact, not the level PI) is corroborated.

## 5. Model consequence (the only edit)

`backend/main.py`: `LV322501_OPEN_DES` **82.0 → 46.1** (field-calibrated, X2).

Pin-safety: the constant has exactly two functional uses — boot seed
(`op = LV322501_OPEN_DES`, main.py ≈ L1699) and ratio normalizer (`op/LV322501_OPEN_DES`,
≈ L1947). At design boot the ratio is 1 regardless of the value → drain = design flow
exactly → **design steady state bit-identical**. Verified by A/B probe (pre/post edit,
full-precision repr): all process boot pins bit-identical; 600 s hold pins identical to
≤ 7·10⁻⁷ % (micro-trajectory of the level PI differs because drain sensitivity per %op is
1.78× — the intended physical change); no limit cycle at the higher loop gain (op drift
5.8·10⁻⁴ % post vs 1.0·10⁻³ % pre — tighter).

Not edited (rationale in §3): HV-322602, HIC-322604, HIC-322605, TV-329005 (operator
practice / off-design setpoints / unsettled anchors — editing would fabricate constants),
pump map (confirmed, −0.07 %), τ band (X1), FEED_TD_S (T6).

## 6. Non-extractables (explicit)

| Requested | Why not available |
|---|---|
| SV-321950/951 step dynamics (T2) | tags absent; 3600 s spacing ≫ actuator time scale |
| TT-322002 response (T3) | tag absent |
| HV-322603 couplings (T4) | tag absent |
| Exact reactor dead time in s (T6) | bracket ≤ 3600 s only |
| HPCC level lag (T7) | HPCC level tag (LT-322E002) absent; LT-322504 is the reactor level |
| Reactor fill dead time (T7, reinterpreted) | bracket ≤ 3600 s only |
| PT-329206, TT-322004 (T8) | tags absent |
| Any slew rate | lower bounds only at 3600 s spacing |
| PV-322203→FT-322403 lag (T10) | unresolvable; gain confounded 6× |

## 7. Rejected approaches (do not repeat)

- Fitting dynamics to the 30 s interpolated rows — synthetic, zero information, fabricated
  constants.
- Hard-coding X1's τ = 2246 s (or any τ) as a lag on synthesis pressure — double-counts the
  inventory ODEs; τ stays an emergent validation target.
- Editing hand-valve `*_DES` constants to match operator positions — operator practice ≠
  design basis.
- Treating T3/T5/T9/T10 secants as transfer-function gains — confounded, sign-unstable.

## 8. Gap-closure research addendum (2026-07-03, task 4)

Deep-research pass over every contradiction between the model equations and the 28-06
anchor values. Sources: NIST WebBook (REFPROP ammonia), ISA-5.1, Berthold radiometric
whitepaper, UreaKnowHow 2024 Gholipour radiometric paper. Verdict per item: **closed**
(root cause identified, no model change warranted) or **residual** (documented ambiguity).

### C1 — Pump mass map: engine 0.33667 vs field 0.34150/0.34174 t/h/rpm — CLOSED

**NIST saturated-liquid NH₃ density** (WebBook, REFPROP):

| T (°C) | 0 | 5 | 10 | 15 | 20 | 25 | 30 | 35 |
|---|---|---|---|---|---|---|---|---|
| ρ_sat (kg/m³) | 638.64 | 631.77 | 624.78 | 617.66 | 610.39 | 602.96 | 595.36 | 587.59 |

**NIST compressed-liquid isotherm at 298.15 K**: ρ = 602.96 (sat, 10.03 bar), 604.01
(21 bar), 604.95 (31 bar), 611.21 (101 bar), 614.56 (141 bar) kg/m³.

1. **Engine constant validated.** `NH3_RHO = 604.8` interpolates NIST 25 °C compressed
   liquid at ≈ 29 bar a — the pump-suction condition. It is not a mis-keyed saturated
   density (602.96); it is the design effective suction density. No edit.
2. **Live-density falsification.** If FY-321401 computed mass from live ρ(T), the 28-06
   warm feed (TT-321001 mean ≈ 27.6 °C at non-zero anchors → ρ ≈ 599–601 kg/m³) would
   give slope
   $$k_{live} = 5.5667\times10^{-4}\,\rho = 0.3345\ \text{t/h/rpm} \quad (-2.1\%\ \text{vs } 0.34174)$$
   Observed 28-06 fit: 0.34150 (−0.07 %). The −2.1 % shift is > 3× the slope tolerance
   (±0.0022) derived from the fit RMSE 0.273 t/h → **live-ρ hypothesis rejected;
   FY-321401 is a fixed-constant DCS computation** (consistent with ISA-5.1: suffix
   letter Y = relay/compute/convert function).
3. **Calibration degeneracy (flag).** With FY fixed-k, the 03-06 T-separated fit
   constrains only the product
   $$\eta_v\,\rho_{cfg} = \frac{0.34174\times1000}{0.0094672\times60} = 601.6\ \text{kg/m}^3$$
   The committed pair (η_v = 0.980, ρ_cfg = ρ_sat(17.6 °C) = 613.9) is one solution;
   (0.985, 610.4 = ρ_sat(20 °C), a common flow-computer reference) is another. The data
   cannot separate them. Conservation-neutral: only the SIC-321950/951 rpm display shifts
   between solutions. Documented as caveat at `PUMP_ETA_V` in `main.py`.
4. **Operator-facing consequence.** The DCS mass display is ≈ +1.4 % above true mass at
   design suction density (fixed-k ignores feed-T density change). The engine computes
   true mass — the residual +1.4 % display offset is a DCS artifact, not a model error.

### C2 — LT-322504 plateau 99.94 % vs model NLL pin 80 % — RESIDUAL

Field level saturates at 99.94 % from 92 % load onward; model pins NLL at 80 % of the
1.5 m span (datasheet UD-AU-322-EC-0006, nozzle N7, top tap 1 m above overflow).
Two hypotheses, not separable from the synthetic anchors:

1. **Genuinely liquid-full to the top tap.** Overflow entry sits 0.5 m above the bottom
   tap (33 % of span); sustained operation ≥ 99.9 % implies liquid ≥ 1 m above the
   overflow lip — possible if the central downcomer entry is submerged and the level
   rides on the reactor pressure balance during ramp-up.
2. **Radiometric density cross-sensitivity.** Gamma level gauges infer level from
   Beer–Lambert attenuation, which depends on ρ·path (Berthold whitepaper). Startup
   carbamate/melt density above the calibration density biases the reading high.
   LT-322504-3 suffix indicates a redundant radiometric transmitter.

The datasheet pin (80 %) outranks a synthetic startup anchor under the sourcing law —
**no pin change**. Discriminator if plant data becomes available: a steady 100 %-load
trend of LT-322504 (design NLL should read ≈ 80 % if hypothesis 2, ≈ 100 % if 1).

**Update 2026-07-03 (session 3):** user supplied `Urea_NormalOp_29-06-2025_Trends.xlsx`
(29-06 normal op, 08:59 → 00:59 30-06, 1921 rows @30 s, sheet self-labelled SYNTHETIC)
as the discriminator — **the export contains no LT-322504 / LIC-322501 / level tag**, so
C2 remains open. Re-export of the same window including LT-322504-3 (and LIC-322501)
requested. 29-06 steady anchors logged in §9. Note also that the LT-322504 display law
changed in session 3 (§9): it now tracks the physical 322R001 head, no load pin — the
discriminator question (transmitter span/zero vs liquid-full) is unchanged.

### C3 — Hand-valve / SP lineup deltas — CLOSED (not a model contradiction)

HV-322602 74→60 %, HIC-322604 50→80 %, HIC-322605 60→49 %, TIC-329005 SP 88.1 vs design
124.6: startup-day operator lineup at 97 % load ≠ design 100 % basis. These are inputs,
not equations; editing `*_DES` constants to match them would fabricate design data
(§7 already rejects this). No edit.

### C4 — P_syn at 97 % load: field 135.7 vs sim 141.3 — CLOSED (unit convention + causality)

PT-329201 anchors peak at 139.6 at 14:01 (92 % load). Read as **bar g** (DCS custom for
PT tags), that is 140.6 bar a — matching design 140.7 bar a to 0.1 bar. The 16:01 value
135.7 bar g = 136.7 bar a then reflects the operator easing pressure late in ramp-up
(PIC-322203 SP trace falls 145.3 → 141.7 over the same anchors). The sim's 141.33 bar a
at 97 % is the free-floating vent-capacity response with no operator SP action — a
causality difference, not an equation error. Both sit within 3 % of design. No edit.

### C5 — N/C → reactor-T gain direction — CLOSED (directionally verified)

Field secants T9: predominantly negative over AY-322701 = 3.77 → 3.02. Audit test 1a
upper range (AT-322701 3.08 → 4.01): TT-322010 186.6 → 182.7 °C — **negative gain,
matching field direction** in the overlapping N/C window. Magnitude untestable (±100 %
field scatter, §3-T9). Cross-check: the radiometric N/C meter span 2.6–3.4 (Gholipour
2024, UreaKnowHow) brackets the sim design value 3.0; field AY 3.02–3.77 rides the top
of that span during ramp — consistent with an instrument near range limit, further
degrading the field secants. No edit.

### Outcome

| ID | Contradiction | Verdict | Model change |
|---|---|---|---|
| C1 | pump map −1.4 % | closed (fixed-k DCS compute tag; NH3_RHO NIST-validated) | comments only |
| C2 | reactor level 99.94 vs 80 % | residual (2 hypotheses; datasheet outranks anchor) | none |
| C3 | lineup deltas | closed (operator practice ≠ design) | none |
| C4 | P_syn deviation direction | closed (bar g convention + SP causality) | none |
| C5 | N/C→T direction | closed (sim reproduces negative gain in field window) | none |

No numeric constant met the sourcing bar for change: every candidate was either
validated (NH3_RHO), degenerate (η_v·ρ_cfg), design-doc-sourced (NLL 80 %), or an
operator input (C3/C4). Design steady state untouched → bit-exactness preserved by
construction; verified by Gate-A probe post-edit.

## 9. Task-5 addendum (2026-07-03, session 3) — LT-322504 display law + 29-06 dataset

### 9.1 Display law change (user order)

Order: "reactor level LT-322504 should not be coupled and pinned to plant load, change in
LT-322504 should be according to mass balance on 332R001" (typo for 322R001). The shadow-holdup
/ `_load_gate` display machinery was deleted; LT-322504 now reads the physical 322R001 head
through the fixed N7 transmitter geometry (datasheet UD-AU-322-EC-0006):

$$LT = \mathrm{clamp}\!\left(80 + \frac{H_{liq} - 20.0}{1.5}\times 100,\; 0,\; 100\right),
\qquad H_{liq} = 25\,\frac{\text{react\_level\_pct}}{100}\ \text{m}$$

driven by the physical inventory ODE
$\frac{dm_{liq}}{dt} = \dot m_{in} - \dot m_{out} + \dot m_{fwd}$,
$\dot m_{out} = \dot m_{des}\cdot\frac{\theta}{\theta_{des}}\cdot\frac{\max(L,0)}{L_{des}}$,
$L = m_{liq}/(\rho(T_{bulk})\,A)$, equilibrium $L_{eq} = L_{des}\,\theta_{des}/\theta$.

### 9.2 Stripper slip-direction fix (S2 root cause)

Pre-fix, opening HV-322605 60→75 % RAISED the level: `stripper_322e001`'s feed-load choke
g_T fed the overhead `slip` term, routing unstripped volatiles back around the loop instead
of out through the bottoms (LV-322501) — wrong physics sign for a flooded steam-limited
stripper. Fix: `mod = clamp(eta_T_steam·eta_co2·eta_P, 0, 1.12) × min(g_T, 1)`;
`slip = max(1−g_NC,0) + max(1−g_HC,0)` (composition terms only). Design (g_T=1) and
turndown (g_T>1) byte-identical; per-component mass closure exact (worst 0.00 ppm / 60
audit cases). Verified: S2 settles at 16.008 m ≡ L_eq = 20·(60/75) = 16.0 m; 5-gate probe,
valve-indicator matrix (HV-322605→LT d=−100), flood, pillar4, reactor 14/14, ejector,
full audit, turndown A/B (70–95 % byte-identical vs HEAD, 100 % row improved CHECK→OK),
and the 4-gate 28-06 harness all PASS. Gate-A pins bit-exact, LT-322504 = 80.0 at design.

### 9.3 29-06-2025 normal-op steady anchors (C2 discriminator attempt)

`Urea_NormalOp_29-06-2025_Trends.xlsx`, sheet "30s Interpolated (SYNTHETIC)", 1921 rows
@30 s, 08:59 29-06 → 00:59 30-06, load 99.1–101.3 %. **No LT-322504 / LIC-322501 / level
tag → C2 discriminator absent; re-export requested.** Steady means (hourly anchors):

| Tag | Steady value | Design / reference |
|---|---|---|
| UREA-LOAD | 99.1–101.3 % | 100 % |
| LV-322501 | ≈ 44.6 % (43.6–45.5) | `LV322501_OPEN_DES` 46.1 % — within 3 % |
| HIC-322605 | ≈ 55.2 % | 49 % at 16:01 startup (still ramping then) |
| PT-329201 | ≈ 130.5 bar g steady | 139.6 bar g startup peak (C4: bar g convention) |
| PIC-322203 | 144.4–145.7 bar g | SP eased post-startup |
| AY-322701 | 3.19–3.34 | design N/C 3.0; meter span 2.6–3.4 (C5) |
| FY-322403 | ≈ 28.4 t/h | 27.4 t/h at 97 % startup anchor |
| HV-322602 | 65–66 % | design 74 % (C3: operator lineup) |
| TT-322013 | 187.1–187.6 °C | 186.9 °C at 97 % startup anchor |

LV-322501 steady 44.6 % at ~100 % load independently corroborates the X2 calibration
(46.1 % design pin; sim settles 44.85 % at 97 % load, field band 44.2–46.4).
