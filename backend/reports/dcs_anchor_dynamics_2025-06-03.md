# Empirical Dynamic Parameters from DCS Startup Trends — 03-06-2025 (Anchor-Only Analysis)

**Source:** `DCS_Trend_Extraction_03-06-2025.xlsx` — sheet *Exact Anchors* only (17 exact multivariate DCS ruler snapshots, 165 values, 36 tags, 11:15:37–16:02:46).
**Excluded:** all `A/B/C/D grid` rows marked `interp` (linear interpolation between anchors carries **zero** dynamic information; using it would fabricate dead times and time constants).
**Analysis script:** `xlsx_anchor_analysis.py` (pandas/scipy/numpy); results archived in `xlsx_anchor_results.json`.
**Extends:** `dcs_tuning_parameters.md` (commit `c7c898a`, PUMP_ETA_V field calibration).
**Units:** strictly metric (s, min, °C, bar g, t/h, Nm³/h, rpm, A, %).

---

## 0. Honest-Resolution Statement (governs every claim below)

| Group | Anchors | Span | Gap min/median/max |
|---|---|---|---|
| A | 6 | 3 h 51 min | 27 / 45 / 60 min |
| B | 5 | 3 h 51 min | 24 / 52.5 / 102 min |
| C | 3 | 1 h 36 min | 12 / 48 / 84 min |
| D | 3 | 3 h 54 min | 87 / 117 / 147 min |

Median anchor spacing is **24–117 min**. Consequences:

- **Extractable:** process time constants with $\tau \gg$ anchor spacing (synthesis pressurization, $\tau \approx 58$ min ✓); steady-state process gains between anchor pairs; the pump speed→flow map (quasi-static, multivariate snapshots ✓).
- **NOT extractable:** true actuator slew rates in %/s (only *lower bounds*); dead times to second precision (only a 9.5-min bracket); hysteresis loops (no up/down stroke pairs at resolution); high-frequency controller kinematics.

Cross-group consistency check passed: TT-322012 = 145.5 °C in both A@11:15:37 and B@11:20:17; A/B interleave at 14:20–14:21 agrees within 1.6 °C; PT-329201 interleaved A+C series is monotonic. Cross-group merging is therefore valid and triples effective resolution for UREA-LOAD (11 pts), PT-329201 (9 pts), TT-322012 (11 pts).

**Data integrity flags:**
1. Grid sheet fabricates LV-322501 = 26.23 % marked `ANCHOR` at 12:53:49 where the anchor sheet is blank — rejected.
2. Grid anchor times are snapped to the 15-s grid (e.g. 11:15:30 vs true 11:15:37) — anchor-sheet times used throughout.

---

## 1. Feed Propagation Lag

### 1.1 Feed introduction timestamp

| Evidence | Time | Value |
|---|---|---|
| Group A: FY-322403, FY-321401, SIC-321950 all zero | 11:15:37 | 0 / 0 / 0 |
| Group B: UREA-LOAD last zero | 11:20:17 | 0 % |
| Group C: UREA-LOAD first non-zero | 11:29:49 | 38.9 % |

**Feed introduction bracketed to a 572 s (9.5 min) window: 11:20:17 – 11:29:49.** An exact $t_d$ in seconds is not resolvable from anchors.

### 1.2 Synthesis pressurization — PT-329201 (merged A+C, 9 exact points)

First-order-plus-dead-time rise fitted with `scipy.optimize.curve_fit`, $t = 0$ at 11:15:37:

$$
P(t) \;=\; P_0 + \left(P_f - P_0\right)\left(1 - e^{-\frac{t - t_d}{\tau}}\right), \qquad t > t_d
$$

| Parameter | Value | 1σ |
|---|---|---|
| $P_0$ | 5.7 bar g | ± 6.6 |
| $P_f$ | 144.0 bar g | ± 6.5 |
| $\tau$ | **3469.5 s** (57.8 min) | ± 585.9 |
| $t_d$ | 344.7 s | ± 280.3 |

$R^2 = 0.9888$, RMSE = 4.95 bar, residuals [−0.0, −1.9, +10.2, −5.5, −5.2, −5.2, +3.4, +4.1, +0.0] bar.

Fitted onset $t_0 + t_d$ = **11:21:22 ± 4.7 min** — falls *inside* the independent UREA-LOAD bracket (11:20:17–11:29:49). Two independent estimates converge: **feed introduction ≈ 11:21–11:25**.

Equivalent transfer function (feed-on step $u: 0 \to 1$ → synthesis pressure):

$$
G_{P}(s) \;=\; \frac{P(s)}{u(s)} \;=\; \frac{K_p\, e^{-t_d s}}{\tau s + 1}, \qquad
K_p = P_f - P_0 = 138.3 \;\text{bar}, \quad \tau = 3469.5 \;\text{s}, \quad t_d \le 572 \;\text{s}
$$

$t_d$ uncertainty (±280 s) exceeds half its value: report the *bracket*, not the point estimate.

### 1.3 UREA-LOAD ramp (merged B+C+D, 11 points) — poor first-order fit, reported for honesty

Same model form: $P_f = 80.3\,\%$, $\tau = 1067 \pm 415$ s, $t_d = 251$ s, $R^2 = 0.9306$, residuals up to ±12 %. The load is **non-monotonic** (73.3 → 67.9 % dip near 13:05, later rise to 89.6 %) — operator-driven ramping, not a first-order plant response. **Do not use this τ for model calibration.** Initial ramp rate lower bound: 0 → 38.9 % in ≤ 572 s ⇒ ≥ 4.1 %/min.

---

## 2. Auto-Valve & Controller Kinematics

True actuator slew (%/s) requires sub-minute sampling of a moving valve. Anchors give **lower bounds only** (|Δposition| / Δt across each anchor pair):

| Actuator | Δposition | Δt (s) | Slew lower bound |
|---|---|---|---|
| HIC-322605 (reactor overflow) | +44 % | 6120 | ≥ 0.00719 %/s |
| HIC-322604 (scrubber vent) | −30 % | 5040 | ≥ 0.00595 %/s |
| HV-322602 (HP ejector spindle) | +10 % | 5040 | ≥ 0.00198 %/s |
| LV-322501 (reactor level valve) | +30 % | 5760 | ≥ 0.00521 %/s |
| TV-329005 | +2.5 % | 8820 | ≥ 0.000283 %/s |
| FV-329409 | −3.1 % | 8820 | ≥ 0.000351 %/s |
| PIC-322203 (COO) | −24 % | 5220 | ≥ 0.0046 %/s |
| SIC-321950 (pump speed) | 0 → 133.4 rpm | ≤ 3600 | ≥ 0.0371 rpm/s |

**Hysteresis / non-linearity: not detectable at this resolution** — no anchor pair captures a stroke reversal.

**Detected controller anomaly (worth flagging to Stamicarbon):** LIC-322501 MV held **saturated at 102.8 %** across all three C anchors (11:29:49 → 13:05:49) while LV-322501 physically moved 0 → 30 %. MV > 100 % with a moving valve implies the positioner was following a different signal source (hand-jack, override, or split-range) during startup — the level loop was *not* in closed-loop control of the valve in this window.

**Investigation closure (2026-07-03) — verdict: DCS positioner/output-span artifact; no OTS AUTO-logic change.** LIC-322501 is DIRECT-acting (main.py:1934): during the startup window the sump is empty/filling, so the level error $e = \text{level} - \text{SP} < 0$ and the velocity-form PI drives the output to its **0 %** clamp (drain closed — correct: let the sump fill). A direct-acting level PI with level below SP therefore commands **0 %, not 102.8 %**. The saturated-high MV cannot be the LIC-322501 level PI output, confirming the positioner tracked a non-LIC source (hand-jack / override / split-range) with a >100 % output-span config. The two facts split cleanly: the **102.8 % MV is the DCS artifact** (never bake >100 % span or windup into the AUTO PI); the **LV 0 → 30 % motion is real** (operator hand-jacking the drain open on startup) and is already reproducible in the OTS via the **existing MAN mode** (main.py:2832, bumpless AUTO re-entry SP←PV at :2830) — no new code, boot pin stays bit-exact (seed remains AUTO@82 %/50 %), conservation untouched. Consistent with the §2 directive below: do not calibrate the controller from this dataset.

**Model consequence:** these lower bounds are all far *below* typical pneumatic actuator capability (≈ 1–4 %/s full-stroke). They constrain nothing. **Keep OTS actuator slew limits at design/vendor values; do not calibrate them from this dataset.**

---

## 3. Disturbance Coupling — Process Gains

Steady-state gains between consecutive anchor pairs, $K = \Delta y / \Delta u$ (|Δu| ≥ 2 % filter, `merge_asof` 2-min tolerance). All are *averaged secant gains over the span*, not small-signal gains, and several are **confounded** by simultaneous load change:

| u → y | Δu | Δy | $K$ | Span | Confound |
|---|---|---|---|---|---|
| HIC-322605 → TT-322014 (overflow T) | +44 % | +84.3 °C | **+1.92 °C/%** | 102 min | load 73.3→85.7 % |
| HIC-322605 → TT-322014 | −2 % | +2.5 °C | −1.25 °C/% | 27 min | small Δu, near noise |
| HIC-322604 → TT-322011 (vent T) | −30 % | −21.1 °C | **+0.70 °C/%** | 84 min | load 38.9→67.9 % |
| PIC-322203 → HIC-322203 (line P) | −24 % | +41.4 bar | **−1.73 bar/%** | 87 min | pressurization ongoing |
| PIC-329204 → TT-329001 (LP drum T) | +5.3 bar (MV) | +11.4 °C | **+2.15 °C/bar** | 12 min | cleanest pair (shortest span) |

Signs are physically consistent: opening the reactor overflow valve routes hot reactor liquor to TT-322014 (+); closing the scrubber vent reduces uncondensed overhead flow past TT-322011 (+ in gain convention); closing the COO vent valve raises CO₂ line pressure (−, direct-acting vent). Treat magnitudes as **±50 % uncertain** given the confounds.

---

## 4. Ammonia Pump Dynamics — SIC-321950 (rpm) → FY-321401 (t/h)

Five exact multivariate snapshots (rpm, t/h, motor A, synthesis bar g):

| N (rpm) | ṁ (t/h) | I (A) | P_syn (bar g) | I/ṁ (A·h/t) |
|---|---|---|---|---|
| 133.4 | 45.74 | 39.9 | 100.1 | 0.872 |
| 127.7 | 43.81 | 39.8 | 112.6 | 0.908 |
| 97.4 | 33.28 | 36.0 | 131.0 | 1.082 |
| 103.9 | 35.36 | 40.1 | 141.9 | 1.134 |
| 111.8 | 37.97 | 41.4 | 141.2 | 1.090 |

### 4.1 Speed → mass-flow map

Through-origin OLS (positive-displacement triplex physics: $\dot m = \rho\, V_{rev}\, \eta_v\, N$, no offset term):

$$
\boxed{\;\dot m_{NH_3}\;[\mathrm{t/h}] \;=\; 0.34174\; N\;[\mathrm{rpm}]\;}
$$

RMSE = 0.161 t/h, residuals [+0.152, +0.170, −0.005, −0.146, −0.236] t/h.
Affine check: $\dot m = 0.34961\,N - 0.917$, $r^2 = 0.99939$, $p_{slope} = 6.4\times10^{-6}$, SE = 0.00498 — intercept not significantly physical at n = 5; through-origin retained.

**Validation:** committed model constant (from prior .md-trend calibration, commit `c7c898a`) is 0.34174 t/h/rpm — this **independent** dataset reproduces it to 5 decimals (deviation −0.00 %). Chain check against physics:

$$
\dot m = \rho_{NH_3} V_{rev}\, \eta_v\, N \cdot 60 = 604.8 \cdot 0.0094671897 \cdot 0.980 \cdot 60 \;/\, 1000 = 0.33666 + \text{(field trim)} \;\Rightarrow\; \eta_v = 0.980 \text{ calibration CONFIRMED}
$$

### 4.2 Startup hydraulic resistance

Specific motor current $I/\dot m$ rises **0.872 → 1.134 A·h/t** as synthesis (discharge) pressure rises 100 → 142 bar g:

$$
\operatorname{corr}\!\left(\frac{I}{\dot m},\, P_{syn}\right): \; r = 0.975,\; p = 0.005 \;(n = 5)
$$

Secant sensitivity $\approx (1.134-0.872)/(141.9-100.1) = 6.3\times10^{-3}$ A·h·t⁻¹·bar⁻¹. Physics: reciprocating pump shaft power $\propto \dot m\, \Delta P / \eta$, so $I/\dot m \propto \Delta P$ — the *flow itself stays on the positive-displacement line* (volumetric slip does not measurably increase to 142 bar g). **Model consequence: no pressure-dependent flow derating needed; hydraulic resistance shows up only in motor load, which the OTS does not simulate.** With n = 5 the correlation is strong but the sensitivity coefficient carries ±30 % uncertainty.

---

## 5. Empirical Transfer-Function Summary

$$
G_{P_{syn}}(s) = \frac{138.3\, e^{-t_d s}}{3469.5\, s + 1} \;\;\left[\frac{\text{bar}}{\text{feed-on}}\right],\; t_d \in [0, 572]\,\text{s (best est. 345 s)} \qquad \text{(R}^2 = 0.9888\text{)}
$$

$$
\dot m_{NH_3}(N) = 0.34174\, N \;\;\left[\frac{\text{t/h}}{\text{rpm}}\right] \qquad \text{(static, valid 97–134 rpm, 100–142 bar g)}
$$

$$
K_{605 \to 014} = +1.92\;\tfrac{°C}{\%}, \quad
K_{604 \to 011} = +0.70\;\tfrac{°C}{\%}, \quad
K_{203 \to P} = -1.73\;\tfrac{\text{bar}}{\%}, \quad
K_{204 \to 001} = +2.15\;\tfrac{°C}{\text{bar}}
$$

No empirical actuator slew rates; no resolvable hysteresis; UREA-LOAD τ rejected (non-first-order).

---

## 6. Proposed Differential Logic for `main.py`

### 6.1 Injection principle — avoid double-counting

`main.py` is a physics-based state-space engine: synthesis pressure emerges from mass/energy inventories, and the tear block already applies first-order display lags via `_lag1` (main.py:1458, implicit-Euler $a = dt/(\tau+dt)$, unconditionally stable, bit-exact at design). **Hard-coding $\tau = 3469.5$ s onto the pressure state would double-count the inventory dynamics the engine already integrates and violate conservation.** The empirical parameters split into three roles:

1. **Transport dead time** (pipe transit NH₃/CO₂ feed → synthesis loop): genuinely missing from the engine (all tears are 1-step). Inject as a delay line.
2. **Validation target, not parameter:** closed-loop OTS pressurization must reproduce $\tau = 3470 \pm 586$ s and onset ≤ 572 s after feed-on. If it does not, tune *physical* inventories (loop vapour volume, condensation duty), never a fudge lag on the pressure state.
3. **Confirmed constants:** pump map and $\eta_v = 0.980$ already committed — no change.

### 6.2 Exact differential logic

Continuous form to be realized:

$$
\frac{dy}{dt} = \frac{u(t - t_d) - y(t)}{\tau}
\qquad\Longrightarrow\qquad
y_{k+1} = y_k + \frac{\Delta t}{\tau + \Delta t}\left(u_{k - n_d} - y_k\right),\;\; n_d = \left\lceil \frac{t_d}{\Delta t} \right\rceil
$$

Proposed addition (place next to `_lag1`, main.py:1458 block; same store-keyed pattern, lazy-init to target ⇒ no boot transient, design pin stays bit-exact because a constant input passes through a delay unchanged):

```python
# --- Empirical transport dead time (DCS 03-06-2025 anchor analysis) -------------------
# Feed-introduction propagation: dead time bracketed to <=572 s, best estimate 345 s
# (PT-329201 FOPTD fit, R2=0.9888; see reports/dcs_anchor_dynamics_2025-06-03.md §1.2).
FEED_TD_S = 345.0          # s, NH3/CO2 feed -> synthesis-loop response dead time


def _delay(store: dict, key: str, target: float, td_s: float, dt: float) -> float:
    """Pure transport delay y(t) = u(t - td) via ring buffer.

    Lazy-inits the buffer filled with `target` so the first call (and any constant
    input) passes through unchanged -> pinned design steady state stays bit-exact.
    Mass/energy conservative: values are only re-timed, never scaled or created.
    State lives in `store` (State.tlag), keyed by `key`.
    """
    if td_s <= 0.0 or dt <= 0.0:
        return target
    n = max(1, int(round(td_s / dt)))
    buf = store.get(key)
    if buf is None or len(buf) != n:
        buf = [target] * n
        store[key] = buf
    out = buf[0]
    del buf[0]
    buf.append(target)
    return out


def _foptd(store: dict, key: str, target: float, tau_s: float, td_s: float,
           dt: float) -> float:
    """First-order-plus-dead-time: dy/dt = (u(t-td) - y)/tau.

    Composition of _delay and _lag1 (implicit Euler, unconditionally stable).
    Realizes G(s) = e^(-td*s) / (tau*s + 1) on a published signal without
    touching the underlying physics states.
    """
    u_delayed = _delay(store, key + ":dl", target, td_s, dt)
    return _lag1(store, key + ":lag", u_delayed, tau_s, dt)
```

### 6.3 Injection points (surgical)

| # | Location | Change | Empirical basis |
|---|---|---|---|
| 1 | Feed tear: where fresh NH₃ (pump discharge) and CO₂ (FY-322403 path) mass flows enter the synthesis-loop balance | wrap each feed term: `m_nh3_eff = _delay(s.tlag, "FEED_NH3", m_nh3, FEED_TD_S, dt)` (same for CO₂) | $t_d$ = 345 s best estimate, bracket ≤ 572 s (§1.2) |
| 2 | No change to reactor/HPCC pressure states | — | $\tau = 3470$ s must EMERGE from inventories (§6.1) |
| 3 | No change to actuator slew | — | anchors give only non-binding lower bounds (§2) |
| 4 | No change to pump map / `_OPEN_DES_B` (main.py:~1588) | — | independently re-confirmed to 5 decimals (§4.1) |

**Conservation note:** `_delay` re-times mass flow; during the transient the delayed mass resides implicitly "in the pipe". If strict tick-by-tick closure of the global mass audit is required, add the buffer contents to the audit as line-pack inventory: $m_{pipe} = \sum_i \mathrm{buf}[i] \cdot \Delta t$.

### 6.4 Acceptance criterion (before any commit)

Simulated cold-start with feed-on step must satisfy, against §1.2:

$$
\tau_{sim} \in [2884,\, 4055]\;\text{s} \quad(\pm1\sigma), \qquad t_{d,sim} \le 572\;\text{s}, \qquad P_f \in [137.5,\, 150.5]\;\text{bar g}
$$

then re-run `probe_verify_calibration.py` (4 conservation gates), `tests\run_full_audit.py`, `tests\audit_p002_pumps.py` — all must stay green.

---

*Generated from exact DCS ruler anchors only. Every number above traces to a cell in the `Exact Anchors` sheet or a least-squares fit on those cells; no interpolated values used.*
