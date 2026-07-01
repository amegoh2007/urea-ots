# DCS Tuning Parameters — Empirical System Dynamics

**Source:** `New folder/Trends/3.6.2025 Synthesis startup.md` (real DCS synthesis-startup trend, 2025-06-03, ~11:00–16:00).
**Method:** `scratchpad/dcs_analysis.py` (pandas / numpy / scipy 1.17.1).
**Scope:** Extract dead times, time constants, process gains, and the HP-NH3 pump speed→flow curve to calibrate OTS transient response.

---

## 0. DATA-AUTHENTICITY GATE (read first)

The file has two parts:

| Part | Rows | Status |
|---|---|---|
| **"Exact Anchors"** (4 group tables) | 6 / 5 / 3 / 3 per group | **REAL** ruler read-outs from zoomed DCS photos — ground truth |
| **"Combined Time Grid (15-s)"** | 1156 | **1137 flagged `interp`, 19 `ANCHOR`** |

The dense 15-s grid is **linear interpolation between the anchors** (verified: `Source_GroupX == interp`, and consecutive values increment by a constant, e.g. FY-322403 `20039.9 → 20073.2 → 20106.5` = +33.3/step). **It carries zero sub-anchor information.**

**Consequence (governs every result below):**
- Real temporal resolution = **anchor spacing**, not 15 s.
- Anchor gaps: Group A 27–60 min · B 24–102 min · C 12–84 min · D 87–147 min.
- Any cross-correlation "dead time" finer than these gaps would be an **interpolation artefact, not a measurement**. Per the project Sourcing Law and statistical false-precision caution, such numbers are **not reported**.

---

## 1. Feed-Propagation Lag  *(Analysis #1 — NOT RESOLVABLE)*

Requested: cross-correlation time delay (s) feed → downstream response.

**Finding:** cannot be extracted from this dataset.

- CO2 feed FY-322403 steps $0 \rightarrow 20082\ \mathrm{Nm^3/h}$ between the only two bracketing anchors 11:15:37 and 12:15:37; synthesis pressure PT-329201 rises $5.7 \rightarrow 100.1\ \mathrm{barg}$ across the *same* 60-min gap.
- All that can be stated rigorously:

$$\tau_{dead}^{\;feed\rightarrow pressure} < 3600\ \mathrm{s}\quad(\text{one anchor gap; true value buried in interpolation})$$

- Physical HP-loop transport lags are seconds-to-minutes; the sampling floor here is **tens of minutes**. No numeric dead time is defensible. **Do not tune OTS transport delays from this file.**

---

## 2. Controller Kinetics / Actuator Slew  *(Analysis #2 — LOWER BOUNDS ONLY)*

Requested: actuator slew rates, loop lag.

Each valve move is only bracketed by two anchors, so only a **lower bound** on slew is available (move may have completed anywhere in the gap):

| Valve | Move | Window (≤) | Slew lower bound |
|---|---|---|---|
| HIC-322605 (reactor outlet) | 0→44 % | 102 min | ≥ 0.43 %/min |
| HIC-322604 (LP steam) | 100→70 % | 84 min | ≥ 0.36 %/min |
| HV-322602 (ejector spindle) | 50→60 % | 84 min | ≥ 0.12 %/min |
| LV-322501 (level valve) | 0→30 % | 96 min | ≥ 0.31 %/min |
| HIC-322203 (vent) | 101→142 | 87 min | ≥ 0.48 /min |

**True actuator slew (%/s) is NOT recoverable.** These bounds are ~3 orders of magnitude slower than real valve strokes → they constrain nothing useful for OTS tuning. **No change to controller/actuator dynamics recommended.**

---

## 3. Valve → Process Coupling  *(Analysis #3 — GAINS confounded)*

Requested: dead time + magnitude of valve% → downstream indicator.

Dead time: not resolvable (§1). Quasi-steady gains $\Delta\text{indicator}/\Delta\text{valve}$ between anchors:

| Pair | Segment gain | Verdict |
|---|---|---|
| FV-329409 → FIC-329409 | +7.5, +1.9 (m³/h)/% | plausible but valve barely moved (46–49 %); low signal |
| HIC-322604 → TT-322011 | +0.70 °C/% | **confounded** — temp tracks plant load, not the valve |
| HV-322602 → PT-329201 | +8.79 bar/% | **confounded** — pressure built from feed ramp, not the 10 % spindle move |
| TV-329005 → TT-322004 | −113 °C/% | **spurious** — valve ±1 %, temp rose 60→173 °C from loading |

The large "gains" are **correlation≠causation**: during startup nearly everything rises together with UREA-LOAD, so single-pair regressions attribute load-driven change to whichever valve happens to have moved. **No process-gain retuning is justified from these.**

**Reactor outlet valve → level (relevant to OTS Bug 7/8):** field confirms the coupling *direction* — HIC-322605 opened to 44 % (~14:20) while reactor level LT-322504 peaked 100.2 % then drained to 78.8 % by 15:06 (≈ −21.5 % over 45 min at ~42 % open). Qualitatively consistent with "open bottom valve → level falls," but feed-confounded → magnitude not usable as a gain. Use as a **sign check**, not a calibration.

---

## 4. HP Ammonia Pump  speed → flow  *(Analysis #4 — SOLID RESULT)*

Requested: SIC-321950 (pump speed) → FY-321401 (NH3 flow); empirical coefficient/curve.

Six anchors incl. origin (RPM, T/H): (0,0) (133.4,45.74) (127.7,43.81) (97.4,33.28) (103.9,35.36) (111.8,37.97).

Per-point ratios: `0.3429 0.3431 0.3417 0.3403 0.3396` → essentially constant ⇒ linear through origin.

$$\boxed{\dot m_{NH_3}\,[\mathrm{t/h}] = 0.3417 \cdot N\,[\mathrm{rpm}]}\qquad R^2 = 0.99991,\;\; \text{max resid} = 0.24\ \mathrm{t/h}$$

Inverse: $N = 2.926 \cdot \dot m_{NH_3}$ rpm per t/h. Free-intercept fit gives slope 0.34225, intercept −0.06 (∼0) — origin confirmed.

### Comparison to `main.py`

Model (`pump_flow_m3h`, positive-displacement):

$$Q = N \cdot V_{rev}\cdot \eta_v \cdot 60,\qquad V_{rev}=\tfrac{\pi}{4}D^2 L\,n_{plgr}=0.009467\ \mathrm{m^3/rev}$$
$$\dot m_{model} = Q\cdot\frac{\rho_{NH_3}}{1000} = 0.32637\cdot N\ \ [\mathrm{t/h}]\quad(\rho=604.8\ \mathrm{kg/m^3})$$

| | t/h per rpm |
|---|---|
| Model (ρ=604.8, per pump) | 0.32637 |
| **Empirical** | **0.34174** |
| Model / empirical | 0.955 (**model −4.5 %**) |

**The pump-law FORM is VALIDATED** — field data is linear-through-origin exactly as the PD model assumes (R²=0.99991). This is a strong positive confirmation of the existing OTS pump structure.

**The −4.5 % magnitude gap reconciles to effective feed density:**

$$\rho_{implied} = \frac{0.34174}{0.53963}\times1000 = 633.3\ \mathrm{kg/m^3}$$

i.e. BL NH3 at ~5 °C (chilled) rather than the design $604.8\ \mathrm{kg/m^3}$ @ 25 °C. Liquid NH3: ρ(0 °C)≈638, ρ(25 °C)≈603 — 633 ⇒ feed ~5 °C.

---

## 5. Verdict on `main.py` changes — **NONE APPLIED**

Per systematic-debugging (no fix without confirmed root cause) and the project **Sourcing Law** (do not overwrite sourced physical constants with values back-fitted from ambiguous data):

1. **Pump law** — validated, not contradicted. No change.
2. **ρ = 604.8 → ~633** — *candidate only, NOT applied.* The 4.5 % gap is ambiguous: assumes (a) single pump feeding FY-321401, (b) FY-321401 is mass t/h, (c) actual feed temp — none verified. `NH3_RHO` is a sourced design constant @25 °C wired into the bit-exact boot pin (motive NH3, ejector, mass balance). Overwriting it on this evidence risks conservation breakage for a cosmetic gain. **Requires confirmed feed temperature before any change.**
3. **IT-321961 current proxy** — field current does **not** track rpm (err ±5 A, rises while speed falls) because it follows discharge ΔP, not modeled (`pump_current_A` is linear-in-rpm, explicitly a "display proxy"). Cosmetic; flag only.
4. **Dead times / slew / valve gains (§1–3)** — not resolvable / confounded. No target.

**No verification suite run, no commit** — because no code changed. (Any commit would also require milestone approval per the remote-backup rule.)

## 6. Actionable, if the user wants to pursue
- Confirm BL NH3 feed temperature at 321D003. If ~5 °C, `NH3_RHO` → ~633 is defensible; then re-pin and run `tests/audit_p002_pumps.py`.
- Confirm pump count feeding FY-321401 during the trend (1 vs 2) — changes the per-pump coefficient.
- To improve `pump_current_A`, add a ΔP-dependent term: $I \propto a\,N + b\,N\Delta P$.
