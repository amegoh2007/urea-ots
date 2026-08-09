# DCS System Identification & Tuning Specification

## 1. Executive Summary
The request to perform dynamic system identification (extracting $\tau$, $\theta$, and process gains) using the provided DCS trend data (`Book2.xlsx` and `Urea_NormalOp_29-06-2025_Trends.xlsx`) and use it to "correct" the backend ODEs has been **rejected** on two fundamental engineering and architectural grounds.

## 2. Technical Rejection Rationale

### 2.1 Mathematical Impossibility (Signal Processing / Nyquist-Shannon)
To extract dynamic parameters like transport delay (dead time, $\theta$) and first-order time constants ($\tau$) — which in this plant operate on the scale of seconds to a few minutes — the data must be sampled at a frequency significantly higher than the process bandwidth.

- **Data Analysis:** Parsing `Book2.xlsx` reveals a sampling interval of approximately **17 minutes** (e.g., Row 1: `17:49:50`, Row 2: `18:06:38`).
- **Synthetic Data:** `Urea_NormalOp_29-06-2025_Trends.xlsx` explicitly states it is a linear interpolation of hourly measured points.
- **Conclusion:** It is mathematically impossible to perform step-response analysis or cross-correlation to find sub-minute lags on data sampled every 17 to 60 minutes. All transient dynamics are completely aliased out.

### 2.2 Architectural Violation (Design-Anchored Fidelity)
The project's core design philosophy (as stated in `project.md`) strictly prohibits empirical "fudging":
> "Every unit is initialised ('boot-pinned') to the exact H&MB design point from the 1,750 MTPD PFD datasheets. Off-design behaviour is computed from first-principles physics; no parameter is fabricated."

Using a snapshot of DCS operation data to arbitrarily scale the process gains ($\Delta Y / \Delta X$) or valve characteristics would destroy the bit-exact design preservation and exact thermodynamic closure of the MESH equations. Plant operational data includes sensor drift, equipment fouling, and unmeasured disturbances. We do not warp first-principles physics (like the Extended UNIQUAC thermodynamics or Darcy-Weisbach hydraulics) to match a specific operational day.

## 3. Alternative Action Plan
Rather than modifying the core physics equations with invalid empirical data:
1. **Maintain current physics:** The Python ODEs will continue to rely on the strictly anchored design steady-state and first-principles derivatives.
2. **High-Frequency Data Requirement:** If true dynamic system identification is required for a specific loop (e.g., verifying `FIC_329409_TAU_S`), we require raw, uncompressed historian data exported at a **1-second** sampling resolution during a deliberate step-test.
