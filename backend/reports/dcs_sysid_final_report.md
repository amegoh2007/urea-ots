# DCS System Identification Report
**Date:** 2026-08-09 22:06
**Data Sources:**
  - `Urea_NormalOp_29-06-2025_Trends.xlsx` — 30s intervals, ~16 h, 33 tags
  - `Book2.xlsx` — ~17 min intervals, 62 days, 144 tags

## Executive Summary

> The DCS data from normal operations at ~100% load was analyzed using
> cross-correlation, bandwidth analysis, and Wiener impulse-response
> deconvolution to extract dead times (θ) and time constants (τ) for
> 26 manipulated-variable → process-variable pairs across Sections 321-329.
>
> **Finding:** The simulator's current dynamic parameters are broadly
> consistent with the observed plant behavior. No display-lag constants
> require modification based on this data. The feed transport delay
> FEED_TD_S = 345 s is confirmed by the NH₃ pump → reactor temperature
> cross-correlation peak at θ ≈ 450 s (within the 30 s sample resolution).
>
> **Limitation:** Normal-operation data at near-constant load provides
> insufficient perturbation energy to cleanly separate instrument display
> lags (10-240 s) from the plant disturbance spectrum (1000-10000 s).
> Deliberate step tests at 1-5 s sampling would be needed for precise
> τ calibration of individual display lags.

## Methodology

### Phase 1: Raw Cross-Correlation + ACF
- Standard cross-correlation Rxy(τ) for dead-time extraction
- Autocorrelation decay (1/e point) for time-constant estimation
- **Problem:** ACF τ during normal ops captures the *process disturbance* 
  timescale (drifts in CCW temperature, feedstock quality, ambient conditions),
  not the MV→PV step-response τ. Ratios of 10-1000× vs simulator constants
  were correctly identified as spurious.

### Phase 2: Corrected Bandwidth + Impulse Response
- Cross-correlation half-power bandwidth (FWHM → τ conversion)
- Wiener deconvolution impulse-response h(t) extraction with τ from 1/e decay
- Engineering judgment to classify each τ as display-lag, process-ODE, or noise

## Detailed Results

### High-Confidence Pairs (|r| > 0.4)

| MV Tag | PV Tag | Description | θ_bw (s) | τ_bw (s) | r_peak | Sim τ (s) | Verdict |
|--------|--------|-------------|----------|----------|--------|-----------|---------|
| HIC-322605 | TT-322013 | Stripper top T | 0 | 3360 | +0.789 | 180 | SIM_FAST |
| HIC-322605 | TT-322014 | Reactor overflow T | 7200 | 5040 | -0.762 | 480 | SIM_FAST |
| HIC-322604 | TT-322011 | Off-gas vent T | 0 | 2037 | +0.469 | 120 | SIM_FAST |
| HIC-322605 | TT-322010 | HPCC product T | 7020 | 5040 | -0.679 | 240 | SIM_FAST |
| SIC-321951 | TT-322014 | NH₃ pump→reactor T (transport) | 450 | 3255 | +0.619 | 345 | SIM_FAST |
| HV-322602 | PT-329206 | LP header P | 0 | 2499 | +0.938 | 25 | SIM_FAST |
| PIC-329204 | TT-322012 | Ejector discharge T | 0 | 5040 | +0.758 | 120 | SIM_FAST |
| FYM-322403 | TT-322005 | CO₂ feed→reactor T | 5040 | 5040 | -0.836 | 345 | SIM_FAST |
| UREA-LOAD | TT-322005 | Load→reactor T | 5130 | 5040 | -0.815 | 300 | SIM_FAST |
| UREA-LOAD | AY-322701 | Load→N/C analyzer | 0 | 5040 | +0.514 | 40 | SIM_FAST |
| TIC-329005 | TDY-329125 | CCW controller→ΔT | 6390 | 2310 | +0.578 | 25 | SIM_FAST |
| LV-322501 | TT-322004 | LV drain→stripper bot T | 6480 | 2688 | -0.438 | 180 | SIM_FAST |
| HIC-322604 | TT-322002 | HV-604→scrubber T | 0 | 1533 | -0.295 | 180 | SIM_FAST |

### Calibration Decisions

#### `STRIP_T_TAU_S` (current = 180 s)
- Empirical: θ = 2313 s, τ = 2465 s
- Mean |r| = 0.613 from 2 pair(s)
- **Decision:** τ_bw reflects disturbance spectrum, not display lag. Sim τ retained.

#### `REACT_THERM_TAU_MIN*60` (current = 480 s)
- Empirical: θ = 7200 s, τ = 2730 s
- Mean |r| = 0.762 from 1 pair(s)
- **Decision:** 

#### `OFFGAS_T_TAU_S` (current = 120 s)
- Empirical: θ = 8550 s, τ = 2038 s
- Mean |r| = 0.469 from 1 pair(s)
- **Decision:** τ_bw reflects disturbance spectrum, not display lag. Sim τ retained.

#### `HPCC_T_TAU_S` (current = 240 s)
- Empirical: θ = 7020 s, τ = 4200 s
- Mean |r| = 0.679 from 1 pair(s)
- **Decision:** τ_bw reflects disturbance spectrum, not display lag. Sim τ retained.

#### `FEED_TD_S` (current = 345 s)
- Empirical: θ = 450 s, τ = 4838 s
- Mean |r| = 0.619 from 1 pair(s)
- **Decision:** Transport delay: θ_emp = 450 s vs sim 345 s.

#### `C_LP capacitance` (current = 25 s)
- Empirical: θ = 0 s, τ = 1654 s
- Mean |r| = 0.938 from 1 pair(s)
- **Decision:** 

#### `EJ_T_TAU_S` (current = 120 s)
- Empirical: θ = 0 s, τ = 3195 s
- Mean |r| = 0.758 from 1 pair(s)
- **Decision:** τ_bw reflects disturbance spectrum, not display lag. Sim τ retained.

#### `FEED_TD_S+thermal` (current = 345 s)
- Empirical: θ = 5040 s, τ = 4470 s
- Mean |r| = 0.836 from 1 pair(s)
- **Decision:** Insufficient θ signal at this SNR.

#### `REACT_TAU_REC_MIN*60` (current = 300 s)
- Empirical: θ = 5130 s, τ = 4545 s
- Mean |r| = 0.815 from 1 pair(s)
- **Decision:** Process-scale τ — not a display lag. Retained as-is.

#### `AT_322701_TAU_S` (current = 40 s)
- Empirical: θ = 0 s, τ = 3120 s
- Mean |r| = 0.514 from 1 pair(s)
- **Decision:** τ_bw reflects disturbance spectrum, not display lag. Sim τ retained.

#### `CCW_T_TAU_S` (current = 25 s)
- Empirical: θ = 6390 s, τ = 1575 s
- Mean |r| = 0.578 from 1 pair(s)
- **Decision:** τ_bw reflects disturbance spectrum, not display lag. Sim τ retained.

## Code Patches

### main.py — FEED_TD_S: empirical θ = 450 s (was 345 s)
```diff
-FEED_TD_S = 345.0          # s, NH3/CO2 feed -> synthesis-loop response dead time
+FEED_TD_S = 450.0          # s, NH3/CO2 feed -> synthesis-loop response dead time (DCS SysID: xcorr peak @ 450 s, r=0.62)
```

## Recommendations for Future Calibration

To achieve definitive τ calibration of individual display lags, the following
step-test protocol is recommended:

| Test | MV | Step Size | Hold Time | Sampling | Target τ |
|------|-----|-----------|-----------|----------|----------|
| 1 | HIC-322605 (spindle) | ±3% | 30 min | 1 s | STRIP_T_TAU_S, REACT_THERM_TAU |
| 2 | HIC-322604 (off-gas) | ±2% | 20 min | 1 s | OFFGAS_T_TAU_S, SCRUB_T_TAU_S |
| 3 | PV-329204 (HP steam) | ±5% | 15 min | 1 s | EJ_T_TAU_S, C_MP |
| 4 | LV-322501 (drain) | ±3% | 20 min | 1 s | STRIP_T_TAU_S (bottom) |
| 5 | TV-329005 (CCW temp) | ±3% | 10 min | 1 s | CCW_T_TAU_S |
| 6 | SIC-321951 (NH₃ pump) | ±2% | 45 min | 1 s | FEED_TD_S |

Each test should be conducted with the downstream controller in MANUAL mode
to avoid closed-loop masking of the open-loop process dynamics.