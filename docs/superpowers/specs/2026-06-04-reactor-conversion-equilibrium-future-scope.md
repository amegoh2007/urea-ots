# Future Scope — 322R001 Reactor Conversion Equilibrium Coupling

> **Status:** SCOPE ONLY (not built). Promote via brainstorm → spec → plan when prioritized.
> **Date:** 2026-06-04
> **Trigger:** Closed-loop physics_check flagged reactor conversion as the last isolated variable
> in the built HP synthesis loop (recycle-loop penalty, boundary rule #2).

---

## 1. The Isolated Variable

`react_322r001()` is a **pinned split-fraction model**: product/off-gas vectors = design vectors
× `co2_scale` × (φ/φ_des). CO₂→urea conversion is therefore **frozen at the design point** and does
NOT respond to feed composition. Every other built coupling is live (steam P → η_T → overhead →
PT-329201 → vent → Q_scrubber → TDY-329125; overhead → HPCC duty → LP steam). The reactor is the
remaining open boundary.

**Dropped feedback:** unconverted NH₃/CO₂ and recycle **water** returning from HPCC liquid +
scrubber overflow + LP recycle re-enter the reactor feed. More recycle water raises the H₂O/CO₂
ratio, which **thermodynamically depresses** urea equilibrium conversion. The current model cannot
express this penalty.

---

## 2. Governing Physics (to encode)

Feed molar ratios (reactor inlet, kmol/h):

$$L=\frac{\dot n_{NH_3}}{\dot n_{CO_2}}\qquad(\text{N/C ratio, Stamicarbon design }\approx 2.95)$$

$$W=\frac{\dot n_{H_2O}}{\dot n_{CO_2}}\qquad(\text{H/C ratio, recycle-water driven})$$

Equilibrium CO₂ conversion as function of feed ratios and temperature:

$$X_{CO_2}^{eq}=f\!\left(L,\;W,\;T_{react}\right)$$

Use a published urea-synthesis equilibrium correlation — **Gorlovskii–Kucheryavyi** or **Mavrovic**
chart form:

$$X_{CO_2}^{eq}=a_0+a_1 L+a_2 L^2+a_3 W+a_4 (T-T_{ref})+\dots$$

> **Coefficient fidelity:** $a_i$ MUST be sourced from the plant datasheet / Stamicarbon HMB /
> literature (Gorlovskii & Kucheryavyi 1980; Mavrovic 1971) at build time. **Do NOT invent
> coefficients.** Calibrate so $X^{eq}(L_{des},W_{des},T_{des})$ reproduces the design HMB conversion
> exactly (zero regression — same pin-at-design discipline as every prior unit).

Approach-to-equilibrium (residence-time / kinetic limit):

$$X_{CO_2}=\eta_{app}\,X_{CO_2}^{eq},\qquad \eta_{app}=f(\tau),\;\;\tau=\frac{V_{react}}{\dot V_{feed}}$$

Per-pass component balance from $X_{CO_2}$:

$$\dot n_{urea}=X_{CO_2}\,\dot n_{CO_2}^{in},\qquad
\dot n_{H_2O}^{out}=\dot n_{H_2O}^{in}+\dot n_{urea},\qquad
\dot n_{CO_2}^{out}=\dot n_{CO_2}^{in}(1-X_{CO_2})$$

Heat coupling (rule #3, exo/endo): net reactor enthalpy = carbamate formation exotherm
(ΔH≈ −117 kJ/mol CO₂) − urea dehydration endotherm (ΔH≈ +15.5 kJ/mol). Couple the net to reactor
temperature / effluent T rather than pinning $T_{react}$.

---

## 3. Recycle-Loop Closure (the boundary to wire)

```
reactor effluent → HP stripper → overhead → HPCC → {liquid carbamate + off-gas}
                                                  ↘ scrubber overflow / LP recycle
                                                       ↘ recycle H2O + NH3 + CO2
                                                          → reactor feed  (CLOSES W, L)
```

- Reactor feed `L`, `W` computed from live HPCC liquid + ejector + recycle vectors (already
  partially available: `hpcc["liq_kmolh"]`, scrubber `overflow_kmolh`).
- Downstream **bypass / LP-recycle water makeup** → raises `W` → lowers `X_CO2` → lowers urea,
  raises unconverted off-gas → **amplifies** stripper overhead → cascades into the already-live
  PT-329201 / HPCC / TDY chain. The loop becomes self-consistent (iterate to convergence per step,
  or 1-step lag as the existing overflow coupling already does).

---

## 4. Approach Options

| # | Approach | Trade-off |
|---|---|---|
| A (rec.) | Empirical $X^{eq}(L,W,T)$ + approach factor, **pinned at design**, 1-step recycle lag | Surgical-ish, matches existing reduced-model style, zero-regression provable |
| B | Full equilibrium-constant ($K_{eq}$) carbamate-dehydration solve per step | Rigorous, heavier, needs activity model (non-ideal e-NRTL) — overkill for OTS |
| C | Lookup table from plant HMB cases (Mavrovic chart digitized) | Cheap, accurate at design, poor extrapolation off-design |

Recommend **A** — consistent with the "pinned + coupled" discipline used for every built unit.

---

## 5. Acceptance Criteria (build time)

1. Design-exact: `X_CO2(des)` reproduces committed reactor HMB conversion (zero regression, all
   reactor + scrubber tests stay green).
2. Monotone recycle penalty: ↑ recycle-water makeup ⇒ ↑ W ⇒ ↓ X_CO2 ⇒ ↑ off-gas (verifiable sweep).
3. Loop self-consistency: PT-329201 / HPCC duty / TDY-329125 respond to the new conversion feedback
   without oscillation (1-step lag stable).
4. Coefficients cited to source; none fabricated.

---

## 6. Out of Scope Here (separate future units)

Granulator ΔH_cryst · vacuum-evaporator BPE curves · LP absorber · vacuum↔CW-return coupling.
Each gets its own brainstorm → spec → plan when built (one unit at a time).
