# HP Scrubber (322E003) — LP/MP Recycle-Carbamate Wash Cascade

**Date:** 2026-08-10
**Unit:** 322E003 HP Scrubber + 322F001 HP Ejector + synthesis-loop pressure (PT-329201)
**Driver:** LP/MP weak-carbamate recycle wash flow (323P001 A/B → 322E003), live var `m_308`.

## Goal

Ensure the six-step process cascade triggered by **increasing the cold, water-rich LP/MP
recycle-carbamate wash into the HP Scrubber** is correctly modelled and simulated in the
live `step_sim` path of `backend/main.py`.

| # | Observation | Physical mechanism | Model lever |
|---|-------------|--------------------|-------------|
| 1 | Overflow level ↑ | Mass balance: surplus wash spills the weir into the sump | `overflow += carb_dev`; sump ODE `scrub_holdup_kg` |
| 2 | Vent-gas line temp ↓ | Cold liquid direct-contact cools rising off-gas | `t_offgas −= SCRUB_OFFGAS_WASH_COOLING·(wash−s)` |
| 3 | Overflow line temp ↓ | Cold wash quenches the ~178.8 °C pool | `q_ccw −= q_wash_sensible` → `t_overflow_cond ↓` |
| 4 | Conditioning-CW outlet temp ↓ | Colder pool ⇒ smaller LMTD ⇒ less duty to CW | same `q_ccw` reduction → `t_ccw_out ↓` |
| 5 | Synthesis pressure ↓ | Water-rich solvent absorbs NH₃/CO₂, collapses vapour | `p_syn −= SYN_P_WASH_COLLAPSE_GAIN·max(wash−s,0)` |
| 6 | NH₃ line after ejector → HPCC temp ↓ | Colder suction blends with motive NH₃ | ejector `T_d` on **live** suction temp |

## State found (commit c0054e0)

Six of seven wash edits from `patch_wash.py` landed. The **seventh** — defining
`wash_scale` inside `step_sim` — silently no-op'd (both patch anchors were stale: real
`step_sim` has no docstring). Net result: three live defects.

- **D1 (crash):** `wash_scale` used at `main.py:5757` and `:7315` but never assigned →
  `NameError` on every tick; the simulator does not boot.
- **D2 (latent crash):** `s.co2_scale` referenced at `:7315` is never set on `State` →
  `AttributeError` once D1 is fixed. The live load ratio is `react["co2_scale"]`.
- **D3 (Obs 6 missing):** `ejector_322f001` computes discharge `T_d` from a **frozen**
  `EJ_T_SUCTION_C = 178.8 °C`, not the live overflow temp — so a colder pool never
  propagates to the HPCC NH₃ line. The causal link is absent.

## Design

Three surgical edits to the **live function path** (`_sm_flowsheet` SM-port classes are
built but never `.solve()`d — not live).

1. **Define `wash_scale`** at the top of `step_sim`, from prior-tick `m_308` (tear that
   breaks the algebraic loop), normalised by **its own design** `R3232_E003_M308_DES`
   (≈36833 kg/h), **not** `SCRUB_CARB_KGH_DES` (36915). This makes `wash_scale ≡ 1.0` at
   design, so every deviation term `(wash_scale − s)` and `carb_dev` is identically 0 →
   boot pins stay bit-exact. Wrong denominator would offset design by ~0.22 %.

2. **Fix Obs-5 pressure ODE:** `s.co2_scale → react["co2_scale"]`. Semantics preserved:
   vapour collapses only when wash surplus exceeds the CO₂ load; zero at design.

3. **Obs 6 — live ejector suction temp:** add `T_suction_C` param to `ejector_322f001`
   (default `EJ_T_SUCTION_C`), use it in the energy balance and the no-flow return; pass
   the **prior-tick** overflow temp `s.tlag["SCRUB_TOVF"]` (stored after the scrubber
   solves) at the call site. At design prior-overflow = 178.8 = `EJ_T_SUCTION_C` → `T_d`
   bit-exact.

## MESH backing

- **Mass balance (Obs 1):** `Σin − Σout = 0`; `carb_dev` mass routed to `overflow`, integrated in the sump inventory ODE.
- **Component balance (Obs 5 absorption):** `d_co2 = SCRUB_CARB_ABS_GAIN·carb_dev_tot`, paired `d_nh3 = 2·d_co2` (carbamate 2 NH₃ : 1 CO₂), gas→liquid, mass-conserving.
- **Energy balance (Obs 2,3,4,6):** sensible/latent blends; ε-NTU condenser bridge bounds `t_overflow`, `t_ccw_out`; ejector cp-weighted mix sets `T_d`.
- **Pressure (Obs 5):** first-order loop-inventory ODE with a wash-driven vapour-collapse sink term.
- **D/S propagation (Sequential Modular):** wash → scrubber → overflow tear → ejector suction → HPCC feed → PT-329201, all via prior-tick tears (design-consistent fixed point).

## Verification

- Boot settles with no exception; publish tags hold design pins (TT-322002 178.8,
  TT-329125 95.0, TT-322011 114.0, PT-329201 140.7).
- Unit-level wash step-up (`wash_scale` 1.0→1.2, others fixed): confirm signs of Obs 1–6.

## Out of scope / gaps

- SM-port classes (`Scrubber322E003`, `Ejector322F001`) lack the wash coupling + live
  suction temp. Not live (never solved) → logged in `handoff.md`, not fixed here.
- Coupling gains (`SCRUB_WASH_SINK_KW`, `SYN_P_WASH_COLLAPSE_GAIN`,
  `SCRUB_OFFGAS_WASH_COOLING`) are calibrated magnitudes, not datasheet-derived → gap.
