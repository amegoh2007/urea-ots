# Handoff — Open Gaps

Running list of *currently open* modelling gaps only. Delete an entry when closed.

## G-LOOP-1 — The static design seed is not the coupled-loop fixed point (PRE-EXISTING)
**Affects:** the whole HP synthesis loop, and through it every downstream section.
**Symptom:** integrating from a fresh `State()` — the seed the live server starts on, since
`_apply_pin` re-creates it after the boot settle — the loop does not stay at the design point. It
walks to a pressure clamp within ~10 min of plant time, together with the stripper sump, the HPCC
sump and the scrubber sump saturating.
**Measured 2026-08-11**, fresh `State()`, 600 s of plant time, no operator action:

| build | p_syn (bar a) | strip level | HPCC level | scrub level |
|---|---|---|---|---|
| committed baseline `f08149e` | **10.0** (lower clamp) | 99.9 % | 20.0 % | 43.0 % |
| current working tree | **180.0** (upper clamp) | 47.3 % | 100.0 % | 77.7 % |

Both builds diverge; the consequence-physics work changed the SIGN of the divergence, not its
existence. Each individual tick is stationary at the seed (verified: relative change < 1e-4 on
tick 1, so the design HMB and the boot pin are exact), so this is a slow accumulation in the coupled
tear structure, not a bad anchor.
**Not yet tried:** the likely candidates are the one-tick tear ordering around
`p_syn_bara ← (m_in_loop − m_out_loop)/C_loop` and the sump ODEs that feed it; a tear-convergence
sweep (iterate the synthesis tears to an algebraic residual within a tick, as unit 324 already does
for its P/T loop) would show whether the drift is a tear artefact or a genuine imbalance.
**Do not** paper over it with a lag or a clamp — the clamps at 10 and 180 bar a are what is
currently hiding it, and both are far outside `SYN_P_MAX_BARA = 144.2`.

## G-CW-1 — 323E011 has no cooling-water boundary
**Affects:** Scenarios3.md 1.4/1.5 as they apply to the 323E011 LP carbamate condenser.
**Missing:** a cooling-water supply temperature/flow handle. `Q_e011 = UA·(T − 35.0)` hardcodes the
sink. (The vessel the engine labels LPCC, 323E003, DOES carry the full tempered-water circuit —
TIC-323013, live 1102/1103 supply and return — so the scenario itself is modelled; this is the
second condenser.)
**Tried:** nothing yet; adding it means a plant cooling-water supply state shared with the 324
vacuum condensers, which currently take their inlet temperature from their own SM-port spec.

## G-CQ-1 — Ammonium-carbamate solubility curve
**Affects:** every carbamate-bearing line — 322E003 overflow, 323E003/323D011 LP carbamate
condensers, the 718A/718B lean-carbamate recycle, 328D001 reflux.
**Missing:** a measured solubility (crystallisation-temperature vs. concentration) curve for
ammonium carbamate in the plant's aqueous NH3/CO2 liquors.
**Tried:** `consequence.carbamate_crystallization_T` scales the one plant-anchored number the engine
already carried — 60 °C at the 322E003 design overflow strength (NH3 + CO2 = 77.19 wt%) — linearly
with carbamate loading. That reproduces the anchor exactly and orders the lines correctly, but the
curvature between the anchor and a lean liquor is assumed, not measured. The urea half of the same
boundary IS on a real solubility table (CRC/Perry), so only the carbamate half is open.

## G-CQ-2 — Barometric-leg elevations, 324F001 and 324F003
**Affects:** NPSH of 324P001 and 324P003; how far the Stage-1/Stage-2 levels must fall before the
melt pumps cavitate.
**Missing:** the plot/piping elevation of each melt leg. This is a piping datum, not a vessel
datasheet, so it is not in `References/Datasheets`.
**Tried:** `R324_BAROMETRIC_LEG_M = 10.0 m` for both — the head a leg must provide to seal a
0.03 bar node against atmosphere. The sign and the ordering of the consequence are unaffected; only
the level at which the knee is reached moves.

## G-CQ-3 — Pump NPSHr values
**Affects:** 323P001, 323P003, 323P008, 328P002, 322P002/328P006, 324P001, 324P003.
**Missing:** per-pump NPSHr from the pump curves. Only 328P003 is quoted in the References text
(3.10 m required against 11.0 m available at 28 m³/h).
**Tried:** a uniform `CQ_NPSHR_FRAC = 0.05` of each vessel's level span, with a 0.08-span margin
band — consistent with the one datasheet figure available (these pumps are sized with large
margins, so only a real inventory loss reaches them). Per-pump curves would replace it.

## G-CQ-4 — Vessel liquid-span heights
**Affects:** the pressure term of the NPSH calculation at every vessel except the four below.
**Missing:** cylindrical shell heights for most vessels. `References/Datasheets/*.pdf` cannot be
rendered in this environment (no poppler), so only the vessels described in the `References/*.md`
text carry real numbers: 323F004 1.800 m, 323F010 2.437 m, 323D011 1.800 m, plus the 322R001
elevations already in the engine.
**Tried:** `CQ_NPSH_H_REF_M = 2.0 m` nominal elsewhere. It scales the subcooling term only; the
static-head term is in level fraction and is exact.

## G-CQ-5 — Drain-nozzle bores
**Affects:** the width of the level band over which each liquid seal is progressively lost.
**Missing:** nozzle sizes and elevations relative to each level transmitter's range.
**Tried:** a uniform `CQ_SEAL_BAND_PCT = 3.0 %` of level span. 322R001 is exempt — its exit funnel
elevation is a real datasheet number and is used directly.

## G-VLE-1 — Urea is a diluent, not a UNIQUAC species
**Affects:** the 323C003 and 323F004 bubble points.
**Missing:** urea interaction parameters for the Extended UNIQUAC NH3-CO2-H2O parameter set (Darde's
set does not contain urea).
**Tried:** urea and biuret enter `vle_nh3co2h2o` as non-volatile mole-fraction diluents, which is
the same treatment `bubble_T_raoult` already gives them. This reproduces the PFD anchors to +1.7 %
(323F010), +7.0 % (323C003) and +17.5 % (323F004), and both call sites use the departure form so the
residual cancels at design — but urea's effect on the NH3/CO2 ACTIVITY COEFFICIENTS is not
represented, and that is where the residual comes from. It is worst at 323F004 because that is the
stage where the steep CO2/carbamate term dominates the bubble point.
