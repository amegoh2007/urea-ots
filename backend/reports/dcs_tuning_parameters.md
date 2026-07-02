# DCS Tuning Parameters — Empirical System Dynamics

**Source:** `New folder/Trends/3.6.2025 Synthesis startup.md` (real DCS synthesis-startup trend, 2025-06-03, ≈11:00–16:00).
**Method:** `scratchpad/dcs_startup_analysis.py` + `scratchpad/probe_pump_eta.py` (pandas 3.0.3 / numpy 2.4.2 / scipy 1.17.1, Python 3.14).
**Scope:** Extract dead times, time constants, process gains, and the HP-NH₃ pump speed→flow curve to calibrate OTS transient response.
**Verdict:** ONE tuning parameter contradicted the field and was corrected — `PUMP_ETA_V` `0.95 → 0.980`. Change is mass/energy conservation-neutral (proven bit-identical, §6). All other couplings within data resolution.

---

## 0. DATA-AUTHENTICITY GATE (read first)

The source file has two parts with different epistemic weight:

| Part | Rows | Status |
|---|---|---|
| **"Exact Anchors"** (4 group tables) | 6 / 5 / 3 / 3 per group | **REAL** ruler read-outs from zoomed DCS photos — ground truth |
| **15-s combined grid** | 1201 rows (5.0 h scaffold) | **INTERPOLATED** between anchors — smooth, NOT independent samples |

**Consequence for dynamics.** The interpolated grid has a fine 15 s spacing but carries **no information between anchors**. True temporal resolution is set by the anchor gaps, not the grid:

$$\Delta t_{\text{Nyquist}} = 2 \cdot \min(\text{anchor gap})$$

| Group | Anchors | Span | Min gap | Median gap | Nyquist floor $\Delta t_{\text{Nyq}}$ |
|---|---|---|---|---|---|
| A | 6 | 231 min | 27.0 min | 45.0 min | **54 min** |
| B | 5 | 231 min | 24.0 min | 52.5 min | 48 min |
| C | 3 | 96 min | 12.0 min | 48.0 min | **24 min** |
| D | 3 | 234 min | 87.0 min | 117.0 min | 174 min |

**Any dead time or time constant shorter than $\Delta t_{\text{Nyq}}$ (24–174 min depending on group) is physically UNRESOLVABLE from this dataset.** Physical process dead times in an HP urea loop are seconds-to-minutes → they live entirely below this floor. This governs the honesty of §1–§3 below.

---

## 1. Feed Propagation Lag (cross-correlation dead time)

**Method.** Discrete cross-correlation of feed signals against downstream indicators on the 15-s grid; lag at peak $|R_{xy}(\tau)|$:

$$\hat\tau = \arg\max_{\tau}\; \left| \sum_{k} \big(x_k-\bar x\big)\big(y_{k+\tau}-\bar y\big) \right|,\qquad \text{lag}_s = \hat\tau \cdot \Delta t_{\text{grid}},\ \ \Delta t_{\text{grid}}=15\,\text{s}$$

| Feed → Indicator | Peak-xcorr lag | n |
|---|---|---|
| FY-322403 (CO₂ NM³/H) → LT-322504-3 (reactor level) | +0 s | 685 |
| FY-321401 (NH₃ T/H) → LT-322504-3 | +6750 s | 685 |
| FY-322403 → TT-322014 (°C) | +495 s | 906 |
| FY-321401 → TT-322014 | +4575 s | 906 |
| FY-322403 → HIC-322605 (%) | +165 s | 906 |
| FY-321401 → HIC-322605 | +4545 s | 906 |
| FY-322403 → PT-329201 (syn. pressure) | +0 s | 925 |
| FY-321401 → PT-329201 | +0 s | 925 |

**Honest verdict — NOT usable as dead times.** Two independent reasons:

1. **Resolution floor (§0).** All values are quantized to the 15-s *grid*, but the *information* resolution is the anchor Nyquist floor (24–54 min). The `+0 s`, `+165 s`, `+495 s` results are all **below the floor** → indistinguishable from zero dead time. Reporting them as seconds-precise would be false precision.
2. **Ramp co-trending artifact.** The large lags (+4545 s to +6750 s ≈ 76–113 min) are **monotone-ramp artifacts**: during startup both feed and indicator rise monotonically, so cross-correlation peaks at whatever shift best overlaps the two ramps — this measures *ramp overlap*, not *transport delay*.

**Usable conclusion:** feed→pressure and feed→reactor-level dead times are **< 1 resolution interval (effectively instantaneous at this data's resolution)**. This is consistent with, and does not contradict, the OTS's existing sub-minute transport lags. **No `main.py` change warranted.**

---

## 2. Controller Kinetics (actuator slew, loop lag)

**Method.** Anchor-to-anchor bound on automatic-valve travel rate:

$$\dot{u}_{\max} \le \frac{\Delta(\text{valve }\%)}{\Delta t_{\text{anchor}}}$$

| Loop | Observed travel | Interval | Slew bound |
|---|---|---|---|
| LV-322501 (reactor-level LV) | +30.0 % | 96 min | **≤ 0.312 %/min** |

**Honest verdict.** This is an **upper bound**, not a rate constant. The valve moved ≤ 0.312 %/min *averaged over 96 min*; the instantaneous DCS ramp/slew limit is faster and unresolved. Loop lag (PV settling after SP step) requires an SP-step event sampled faster than the loop time constant — **absent** in this startup record (SP was ramped, not stepped). No defensible $K_c$/$T_i$ can be back-fitted. **Existing controller tunings retained; no change warranted.**

---

## 3. Valve-to-Process Coupling (dead time + static gain)

**Method.** Anchor-differenced static gain $K = \Delta(\text{indicator}) / \Delta(\text{valve }\%)$; dead time via §1 xcorr.

**Honest verdict.** Static gains are anchor-differenced (2–6 points/valve); dynamic dead time is anchor-limited (§0 floor). No valve→indicator coupling resolves a dead time above the Nyquist floor, and no static gain has enough anchor points to beat the ±ruler read error. **Within resolution of the existing model; no change warranted.**

---

## 4. Ammonia Pump Flow Mapping ★ (the one quantitative result)

The HP-NH₃ triplex pump (321P002A/B) speed→flow map is the **only** relationship with enough clean anchor points (n = 5, all at SIC-321950 > 0) to calibrate against.

### 4.1 Empirical curve

Five valid pump anchors $(N\,[\text{rpm}],\ \dot m\,[\text{t/h}],\ T_{\text{feed}}\,[^\circ\text{C}],\ P_{\text{disch}}\,[\text{bar g}])$:

$$(133.4,\,45.74,\,15.7,\,100.1),\ (127.7,\,43.81,\,15.7,\,112.6),\ (97.4,\,33.28,\,18.1,\,131.0),\ (103.9,\,35.36,\,19.1,\,141.9),\ (111.8,\,37.97,\,19.4,\,141.2)$$

**Through-origin fit** (physically correct — zero rpm ⇒ zero flow):

$$\boxed{\ \dot m_{\text{NH}_3}\,[\text{t/h}] = 0.34174\; N\,[\text{rpm}]\ }$$

**Affine cross-check:** $\dot m = 0.34961\,N - 0.917$, $\ R^2 = 0.999392$. Intercept $-0.917$ t/h is within ruler read-error of zero ⇒ through-origin confirmed.
**Pointwise ratio:** $\overline{\dot m / N} = 0.34152 \pm 0.00152$ t/h/rpm (n = 5, CV = 0.44%).

### 4.2 Model comparison — the +4.7% gap

Pre-calibration model slope, from module constants:

$$k_{\text{model}} = \frac{V_{\text{rev}}\,\eta_v\,\rho\cdot 60}{1000}
= \frac{0.0094672 \cdot 0.95 \cdot 604.8 \cdot 60}{1000} = 0.32637\ \text{t/h/rpm}$$

$$\frac{k_{\text{emp}}}{k_{\text{model}}} = \frac{0.34174}{0.32637} = 1.0471\quad(+4.7\%)$$

### 4.3 Root-cause decomposition (systematic-debugging Phase 1–2)

The +4.7% gap factors **exactly** into two independent, physically-sourced multipliers:

$$\underbrace{1.0471}_{\text{total}} = \underbrace{1.0144}_{\text{cold feed density}} \times \underbrace{1.0316}_{\eta_v \text{ underestimate}}$$

**(a) Cold-startup feed density — +1.4% — TRANSIENT, do NOT change design constant.**
Mean startup feed temperature $\overline{T}_{\text{feed}} = 17.6^\circ\text{C}$ (TT-321001), vs 25 °C design. Liquid-NH₃ density (linear fit on $T=[0,10,20,25,30]^\circ\text{C}$, $\rho=[638.6,624.8,610.3,602.8,595.2]$ kg/m³):

$$\rho_{\text{NH}_3}(17.6^\circ\text{C}) = 613.5\ \text{kg/m}^3\quad\Rightarrow\quad \frac{613.5}{604.8}=1.0144$$

This is a **startup transient** (feed warms to design as the plant lines out) → the design-basis $\rho_{\text{NH}_3}=604.8$ kg/m³ @25 °C is **correct**; not touched.

**(b) Volumetric efficiency — +3.2% — DESIGN error, CORRECTED.**
Temperature-corrected model slope $k_{\text{model}}^{T}=0.33105$ t/h/rpm still leaves a residual:

$$\frac{k_{\text{emp}}}{k_{\text{model}}^{T}} = \frac{0.34174}{0.33105}=1.0323\quad(+3.2\%)\ \Rightarrow\ \eta_v^{\text{field}} = 0.95 \times 1.0323 = 0.9807$$

### 4.4 η_v field fit + slip-hypothesis falsification

**T-separated per-point fit** (removes cold-density confound by dividing each point by its own $\rho(T_{\text{feed},i})$):

$$\eta_{v,i} = \frac{\dot m_i \cdot 1000}{N_i \cdot V_{\text{rev}} \cdot 60 \cdot \rho(T_{\text{feed},i})}\quad\Rightarrow\quad \boxed{\ \eta_v = 0.9800 \pm 0.0011\ (n=5,\ \text{CV }0.1\%)\ }$$

**Slip hypothesis FALSIFIED (why 0.980 is a DESIGN value, not a low-pressure artifact).** A plunger pump's $\eta_v$ falls at high discharge pressure (back-leakage/slip). If 0.980 were a low-pressure startup artifact it would *decay* toward design pressure. It does not:

| Point | $P_{\text{disch}}$ (bar g) | $\eta_{v,i}$ |
|---|---|---|
| 1 | 100.1 | ≈0.980 |
| 2 | 112.6 | ≈0.980 |
| 3 | 131.0 | ≈0.980 |
| 4 | **141.9** (≥ design 141) | ≈0.980 |
| 5 | **141.2** (≥ design 141) | ≈0.980 |

$\eta_v$ is **flat across 100 → 142 bar g**, including the two points **at/above design discharge pressure (141 bar)**. ⇒ 0.980 is the **true design volumetric efficiency**; the assumed 0.95 was 3.2% low.

### 4.5 Correction applied

```
main.py L61:  PUMP_ETA_V = 0.95  →  PUMP_ETA_V = 0.980
```

Post-calibration slope $k_{\text{model}}=0.33667$ t/h/rpm; residual vs field $\dot m$ is the cold-density transient only (expected, correctly not modelled as a design constant).

---

## 5. Conservation-neutrality proof (why changing η_v moves no mass)

The NH₃ pump runs **closed-loop ratio control**, not open-loop displacement. $\eta_v$ enters and cancels:

**Demand (mass, ratio-driven):**
$$\dot m_{\text{NH}_3}^{sp} = r_{sp}\cdot \text{NC\_TO\_MASS}\cdot \dot m_{\text{CO}_2}$$

**Speed back-computed (η_v appears in denominator):**
$$N_{\text{req}} = \frac{Q_{\text{per pump}}}{V_{\text{rev}}\,\eta_v\,60},\qquad Q_{\text{per pump}}=\frac{\dot m_{\text{NH}_3}^{sp}/\rho}{n_{\text{pumps}}}$$

**Mass reconstructed from actual speed (η_v appears in numerator):**
$$\dot m_{\text{NH}_3} = \frac{\text{pump\_flow\_m}^3\text{h}(N_{\text{act}})\cdot \rho}{1000},\qquad \text{pump\_flow\_m}^3\text{h}(N)=V_{\text{rev}}\,\eta_v\,60\,N$$

At steady state $N_{\text{act}}=N_{\text{req}}$, so:
$$\dot m_{\text{NH}_3} = \frac{\big(V_{\text{rev}}\,\eta_v\,60\big)\cdot \dfrac{\dot m_{\text{NH}_3}^{sp}/\rho}{n_{\text{pumps}}\,V_{\text{rev}}\,\eta_v\,60}\cdot \rho \cdot n_{\text{pumps}}}{1000}\cdot 1000 = \dot m_{\text{NH}_3}^{sp}$$

$V_{\text{rev}}$, $\eta_v$, and $\rho$ **all cancel identically**. $\eta_v$ is **display-only**: it rescales the SIC-321950 rpm read-out and valve-open %, never the delivered mass. Correcting 0.95→0.980 makes the *displayed pump speed* match the field DCS curve without perturbing the mass balance.

**Design hardening.** The pump-B seed `_OPEN_DES_B` was a hardcoded magic literal `86.2` (an inverse of the cascade flow law computed at $\eta_v=0.95$). It is now **derived** so it can never desync from $\eta_v$:

$$\text{\_OPEN\_DES\_B} = \frac{\text{EJ\_MOTIVE\_NH3\_DES}/\rho}{V_{\text{rev}}\,\eta_v\,60\cdot N_{\text{rated}}}\times 100$$

Evaluates to 86.200% at $\eta_v=0.95$ (bit-matches old literal) and **83.561%** at $\eta_v=0.980$.

---

## 6. Red/Green verification (verification-before-completion)

Boot of the edited model busts the boot-pin SHA key (`f1f9ab0a… → a4e20a5f…`) → fresh 21 000-tick settle → rewrites `.boot_pin_cache.json`. Fresh evidence:

| Gate | Check | Result |
|---|---|---|
| **1 — Conservation-neutral** | all 11 boot-pinned mass/energy constants bit-identical to η_v=0.95 baseline | **PASS** (max \|Δ\| = 0.0) |
| **2 — Design fixed points** | LT-322504 = 80.0000 %, strip_level = 50.0000 % | **PASS** |
| **3 — Display shift** | SIC-321950 rpm 131.02 → **127.01**; open 86.2 → **83.56 %** | **PASS** |
| **4 — Bumpless CAS** | derived seed 83.5612 % == settled open_act 83.5612 % (\|Δ\|=0.0000) | **PASS** |

`F_CO2_th = 54.6180 t/h` and `F_in_BL_th = 42.762 t/h` (== EJ_MOTIVE_NH3_DES mass anchor) — both unchanged, confirming mass invariance under the η_v edit.

---

## 7. Summary — parameters derived vs. applied

| # | Analysis | Derived value | Data quality | main.py action |
|---|---|---|---|---|
| 1 | Feed propagation lag | dead time < resolution floor (24–54 min) | resolution-limited | none (consistent) |
| 2 | Controller kinetics | LV-322501 slew ≤ 0.312 %/min (bound) | anchor-limited, no SP step | none |
| 3 | Valve→process coupling | gains within ruler error | anchor-limited | none |
| 4 | **NH₃ pump map** | $\dot m = 0.34174\,N$ (R²=0.9994); $\eta_v=0.980\pm0.001$ | **5 clean anchors** | **`PUMP_ETA_V` 0.95→0.980** + derived `_OPEN_DES_B` |

**Bottom line.** The startup record's temporal resolution is too coarse to recalibrate dead times / time constants (they sit below the Nyquist floor), so those couplings are retained. The one quantitatively defensible finding — a +3.2% pump volumetric-efficiency underestimate, isolated from the +1.4% cold-density transient and confirmed pressure-independent — was corrected. The correction is provably mass/energy conservation-neutral (§5–§6).
