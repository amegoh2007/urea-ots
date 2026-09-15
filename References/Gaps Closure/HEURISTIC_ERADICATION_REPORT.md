# Heuristic Eradication Report — Urea OTS Backend Physics Engine

**Audit date:** 2026-09-14
**Auditor role:** Lead Process Simulation Auditor / Chemical Engineer
**Scope:** `backend/main.py` (9 869 lines, the live engine), `backend/core/*.py`, `backend/reactor.py`,
`backend/consequence.py`, `backend/steam_system.py`, `backend/controllers.py`,
`backend/c003_pressure_coupling.py`, `backend/thermo_extended_uniquac.py`.
**Excluded:** `main.py.bak`, `main_backup.py`, `main_debug.py`, `main_orig.py`, `main_test_fix.py`
(dead snapshots), `backend/test_*.py`, `backend/gap_g*.py` (offline studies), `.claude/worktrees/`.

**Re-audit, 2026-09-15 — read this before anything below.** The 2026-09-14 continuation notes that
used to stand here said the line references "were checked against the live files" and that the
findings "were rechecked against the current working tree". **Neither was true.** Sections A–G are
the ORIGINAL audit text, and their anchors predate the Phase 1–5 remediation (commits `01e9cfa`
through `7a6b605`). `main.py` has grown from 9 869 to 11 900+ lines since, so a quoted
`main.py:NNNN` is typically 1 000–2 000 lines off. 25 of the 73 findings had already been closed or
partly closed by those phases while the report still listed them as live.

Sections A–H below are kept verbatim for provenance. **The authoritative status of every finding
is the ledger in §0a**, re-verified finding by finding against the tree committed with this revision
by direct source reads, with each live anchor regenerated after the last source edit. The engine
was run for the three findings this revision changes (A-2, A-3, A-5), and the ledger records those
measurements.

`backend/core`: of the thirteen modules, `main.py` imports eight, but only `Valve322604.solve()` is
ever stepped (see §F). `core/lp.py` and `core/mp.py` are never imported.

## 0. Executive summary

The engine is not a first-principles process simulator. It is a **design-point interpolator**: a
pinned steady-state solution of the 1750 MTPD PFD, surrounded by hand-built dimensionless departure
functions that make the published tags move in plausible directions when an operator turns something.

The architecture is stated explicitly and repeatedly in the source itself — the phrases
*"anchored-correction form"*, *"design bit-exact"*, *"bit-exact at design"*, *"calibrated EXACT to
the shared design HMB"*, *"pinned"* and *"reduced calibrated split-fraction"* appear over 200 times
in `main.py` alone. Every one of those phrases marks a place where a state is **not solved** but
**assigned as `design_value × Π(dimensionless ratios)`**.

The boot sequence makes this structural, not incidental. `_pin_hpcc_ua()`
([main.py:9590](../../backend/main.py#L9590)) runs the model for 18 000 ticks, then **back-solves**
`HPCC_UA`, `REACT_TEAR_DES`, `REACT_L_FEED_DES`, `REACT_W_FEED_DES`, `REACT_X_DES`,
`HPCC_LIQ_DES_LIVE`, `EJ_MOTIVE_DES_LIVE` and `HPCC_NC_DES_LIVE` so that the design point reproduces
itself. Physical parameters are therefore *outputs* of the design pin rather than *inputs* from
datasheets.

### Findings by category

| Category | Confirmed violations | Severity |
|---|---|---|
| A. Algebraic state hacks (P, T, L assigned, not integrated) | 19 | Critical |
| B. Empirical phase splits (no rigorous VLE boundary) | 14 | Critical |
| C. Scripted kinetics (load multipliers, not rate laws) | 6 | Critical |
| D. Synthetic hydraulics (no Cv, no compressible flow) | 22 | High |
| E. Fabricated consequence gains / synthetic instrument signals | 12 | High |
| **Total** | **73** | |

---

## 0a. Status ledger — re-verified 2026-09-15

**Totals: 19 CLOSED · 10 PARTIAL · 2 BLOCKED on a missing datum · 2 RECLASSIFIED · 40 OPEN.**

| Category | Closed | Partial | Blocked | Reclassified | Open |
|---|---|---|---|---|---|
| A. Algebraic state | 6 | 2 | 2 | 0 | 9 |
| B. Phase splits | 0 | 5 | 0 | 0 | 9 |
| C. Kinetics | 4 | 0 | 0 | 1 | 1 |
| D. Hydraulics | 8 | 3 | 0 | 0 | 11 |
| E. Gains / signals | 1 | 0 | 0 | 1 | 10 |

Status key. **CLOSED**: the live path now solves the first-principles relationship. Where it is written
as an anchored departure (`design × law(live)/law(design)`), the departure carries the physics and the
anchor only fixes a design datum the repository cannot supply. **PARTIAL**: some sites or terms
closed, others still scripted. **BLOCKED**: the replacement is written down, but the one number it
needs is not in `References/`. **RECLASSIFIED**: the original finding misread the code. Anchors are
`file:line` in the tree committed with this revision.

### A. Algebraic state hacks

| # | Status | Live anchor | Evidence |
|---|---|---|---|
| A-1 | OPEN | [main.py:9839](../../backend/main.py#L9839) | `C_loop = SYN_LOOP_C_KG_PER_BAR` (1500 kg/bar) still integrates PT-329201; no vapour-space EOS |
| A-2 | OPEN — **root cause traced** | credit [main.py:9892](../../backend/main.py#L9892); source [main.py:5191](../../backend/main.py#L5191), [main.py:4433](../../backend/main.py#L4433) | See *A-2 trace* below. The credit is the loop-level mirror of the reactor recycle tear, not the source itself. Deleting only the credit was tried and measured: PT-329201 fell 140.700 → 139.477 bar a in 2 750 s (−1.45 bar/h = R_des/C_loop), with reactor and HPCC levels bleeding. Reverted |
| A-3 | **CLOSED** (this revision) | [main.py:7298](../../backend/main.py#L7298) | `k_loop_fill` deleted; the reactor, stripper-sump and HPCC holdups integrate their real net flow. Design-neutral by construction (k was exactly 1 at `m_loop_frac` = 1). Measured 3 000 s hold: PT-329201 140.479560 against HEAD 140.479578 |
| A-4 | OPEN | [main.py:7655](../../backend/main.py#L7655) | LT-322E002 still a %-per-τ ODE, drain linear in level |
| A-5 | **CLOSED** (this revision, quasi-steady) | [main.py:3352](../../backend/main.py#L3352) | Chest pressure solved from steam admitted (ISA-75.01 compressible, [hydraulics.py:258](../../backend/hydraulics.py#L258)) = steam condensed (UA·ΔT), with λ from IAPWS-IF97. All four PICs now read the solved chest pressure, not `op × header`. Slave Kc scaled by the design gain ratio (5.87 / 1.86 / 4.23 / 5.46), so the tuned closed-loop speed is kept. A dynamic chest inventory is **BLOCKED**: the four exchanger datasheets are image-only scans with no legible shell volume |
| A-6 | PARTIAL | [main.py:9305](../../backend/main.py#L9305) | 8 of 9 vessels on `hydraulics.vessel_dpdt` (Phase 2 / 4b). 324F001 BLOCKED on cylindrical height. `R323_F010_P_KP`, `R328_C002_P_KP` and `R328_C004_P_KP` remain defined with no reader |
| A-7 | BLOCKED | [main.py:8117](../../backend/main.py#L8117) | Needs a real F004 → 323E011 line ΔP; both design pressures are 1.13 bar a |
| A-8 | CLOSED (`dae861d`) | energy balance per As-Built *322R001 Column Energy Balance* | Column T from reaction enthalpies. `T_conv_c` ([main.py:7403](../../backend/main.py#L7403)) still computes the old 13 °C rise, but `react_322r001` never reads its `T_overflow_c` argument: dead, delete-candidate |
| A-9 | OPEN | [main.py:4003](../../backend/main.py#L4003) | TT-322004 = design + 0.7·ΔT_steam + shaped corrections |
| A-10 | OPEN | [main.py:4450](../../backend/main.py#L4450) | `SCRUB_OFFGAS_T_GAIN = 120 °C per N/C` still live |
| A-11 | PARTIAL | F010 [main.py:8158](../../backend/main.py#L8158); C003 [main.py:7963](../../backend/main.py#L7963); F004 [main.py:8072](../../backend/main.py#L8072) | 323F010 on the rigorous `thermo_service.bubble_t` departure (Phase 1). 323C003 and 323F004 still pure-water T_sat offsets |
| A-12 | OPEN | [reactor.py:730](../../backend/reactor.py#L730) | `level_m` is still ignored; the empty-vessel guard sits on the caller at [main.py:7554](../../backend/main.py#L7554) |
| A-13 | OPEN | [main.py:3630](../../backend/main.py#L3630) | Frozen approach temperature |
| A-14 | OPEN | [main.py:3663](../../backend/main.py#L3663) | PFD literals plus offsets |
| A-15 | CLOSED (Phase 1) | [main.py:3609](../../backend/main.py#L3609), [main.py:4829](../../backend/main.py#L4829) | Both identity short-circuits deleted |
| A-16 | OPEN | [main.py:8423](../../backend/main.py#L8423) | 323C005 bottoms linear in holdup |
| A-17 | BLOCKED | [main.py:3421](../../backend/main.py#L3421) | Torricelli on a mass ratio; needs the barometric-leg height |
| A-18 | CLOSED (Phase 4b, D-5) | [main.py:7024](../../backend/main.py#L7024) | CO2 line on a check-valve node; `CO2_PV_DP_GAIN` superseded ([main.py:7003](../../backend/main.py#L7003)) |
| A-19 | CLOSED (Phase 4b, D-5) | as A-18 | 320K002 map with surge/stonewall flags |

**A-2 trace.** The boundary residual decomposes exactly against the PFD rows (kg/h):

| Boundary term | Model design pin | PFD row | Δ |
|---|---|---|---|
| Motive NH3, 321P002 A/B | 42 762.05 | 40 756 | +2 006.05 (N/C = 2.0 re-pin) |
| CO2 feed, 322K001 | 54 618.0 | 54 618 | 0 |
| LP carbamate m308 | 36 835.15 | 36 915 | −79.85 |
| Stripper bottoms, LV-322501 | 130 482.0 | 130 582 | −100.0 |
| Vent, HV-322604 | 5 901.4 | 1 708 | **+4 193.4** (156.95 kmol/h of forced NH3/CO2 slip) |
| **in − out** | **−2 168.2** | −1 | |

At steady state the internal units must therefore create 2 168.2 kg/h. The creation site is
`REACT_TEAR_DES`, subtracted from the reactor feed at [main.py:5191](../../backend/main.py#L5191)
(`fc = feed − tear·s`). With the boot-pinned tear that puts +2 085.7 kg/h into 322R001 that never
arrived: CO2 +2 416.3, urea +283.9, H2O +122.5, CH4 +61.9, H2 +4.1 and O2 +0.8, against NH3 −795.9
and N2 −7.9. That is 96.2 % of the residual. The CH4 (3.86 kmol/h) and H2 (2.02 kmol/h) it creates
are exactly the vent vector's CH4 and H2, and no feed carries either. The remaining 82.5 kg/h is
not yet located. **Closure order:** re-reconcile the 322E003 vent on its PFD row, re-pin until
`REACT_TEAR_DES` ≡ 0, and only then delete the credit.

### B. Empirical phase splits

| # | Status | Live anchor | Evidence |
|---|---|---|---|
| B-1 | PARTIAL | [main.py:43](../../backend/main.py#L43) | `thermo_service` (γ-φ flash, bubble/dew) is wired into the 323 stages and into the reactor disengagement, stripper split and scrubber vent (anchored `k_ratio`, Phase 5). The 328 train is not; 324 melt flashes are refused (G-VLE-2) |
| B-2 | PARTIAL | [main.py:5297](../../backend/main.py#L5297) | Vent *composition* re-partitioned by `k_ratio`; totals are still design vector × s |
| B-3 | OPEN | [main.py:5407](../../backend/main.py#L5407) | Species-uniform flash-back `(1 − cf)` |
| B-4 | OPEN — retained deliberately | [main.py:4812](../../backend/main.py#L4812) | Wiring `k_ratio` here broke loop recovery (handoff §1b); needs a loop-refitted parameter set |
| B-5 | OPEN | [main.py:4743](../../backend/main.py#L4743) | `HPCC_BUB_KN/KW` still `-- calib` |
| B-6 | PARTIAL | [main.py:4251](../../backend/main.py#L4251) | θ vector moved by anchored `k_ratio`; inerts structurally θ = 1 |
| B-7 | PARTIAL | [main.py:4055](../../backend/main.py#L4055) | `eta_P` replaced by the rigorous pressure ratio; `eta_co2`, `eta_T_steam` and `g_flood` remain |
| B-8 | PARTIAL | [main.py:2640](../../backend/main.py#L2640) / [main.py:2584](../../backend/main.py#L2584) | 323C003/F004/F010 on `sol_vapour_y_vle`; the 328 train and 324 still on frozen α |
| B-9 | OPEN | [main.py:3531](../../backend/main.py#L3531) | One `h_eff_kjkg` per condenser |
| B-10 | OPEN | [consequence.py:329](../../backend/consequence.py#L329) | Linear in NH3 + CO2 loading |
| B-11 | OPEN | [main.py:7971](../../backend/main.py#L7971) | `R323_PHI_V305` cap plus duty ratio at fixed λ |
| B-12 | OPEN | [main.py:8162](../../backend/main.py#L8162) | min of two design ratios |
| B-13 | OPEN | [main.py:3629](../../backend/main.py#L3629) | Linear NC derate |
| B-14 | OPEN | [main.py:2990](../../backend/main.py#L2990) | One scalar for all volatiles (328) |

### C. Scripted kinetics

| # | Status | Live anchor | Evidence |
|---|---|---|---|
| C-1 | CLOSED (`2e909ee`) | [main.py:5186](../../backend/main.py#L5186) | `reactor.urea_extent_pfr` over live level, Vdot and node T |
| C-2 | CLOSED (`2e909ee`) | [main.py:5199](../../backend/main.py#L5199) | Second-order Arrhenius biuret over the column |
| C-3 | CLOSED, anchored (`74cf3ee`) | [main.py:4019](../../backend/main.py#L4019) | Inoue-Otsuka departure; the 88.1 kmol/h anchor lumps carbamate decomposition (handoff §1f) |
| C-4 | CLOSED (`74cf3ee`) | [main.py:4028](../../backend/main.py#L4028) | Second order over the live wetted volume |
| C-5 | RECLASSIFIED — conforming | [main.py:2727](../../backend/main.py#L2727) | Already live holdup, second order and live-T Arrhenius |
| C-6 | OPEN | [main.py:5239](../../backend/main.py#L5239) | `REACT_OFFGAS_DEFICIT_GAIN = 1.0` still moves NH3/CO2 overhead |

### D. Synthetic hydraulics

| # | Status | Live anchor | Evidence |
|---|---|---|---|
| D-1 | PARTIAL | [main.py:5620](../../backend/main.py#L5620) | Every listed LV/PV now IEC 60534. `_fic_flow` is still `design × op/op_des` with no ΔP |
| D-2 | CLOSED (Phase 2) | [main.py:5498](../../backend/main.py#L5498), [core/valve.py:55](../../backend/core/valve.py#L55), [steam_system.py:225](../../backend/steam_system.py#L225) | ISA-75.01 compressible with choke on HV-322604 (both ports) and the steam let-downs |
| D-3 | PARTIAL | [core/valve.py:65](../../backend/core/valve.py#L65) | A capacity ceiling now retains what the seat cannot pass. The composition vector is still multiplied by the anchored valve ratio, which exceeds 1 above design upstream pressure |
| D-4 | OPEN | [main.py:5534](../../backend/main.py#L5534), [core/valve.py:66](../../backend/core/valve.py#L66) | Constant μ_JT |
| D-5 | CLOSED (Phase 4b) | [main.py:7024](../../backend/main.py#L7024) | Compressor node and check-valve diode |
| D-6 | CLOSED (Phase 4b) | [main.py:3203](../../backend/main.py#L3203) | `jet_pump` momentum closure; `f_stall` retired |
| D-7 | OPEN | [main.py:7262](../../backend/main.py#L7262) | ṁ²/ρ ratio, no friction factor |
| D-8 | CLOSED, anchored (Phase 2) | [main.py:5729](../../backend/main.py#L5729) | Line inventory back-solved from the design transit; delay ∝ ρV/ṁ |
| D-9 | CLOSED (Phase 4a) | [main.py:9863](../../backend/main.py#L9863) | API 520 choked orifice with pop/blowdown latch |
| D-10 | CLOSED (Phase 4b) | As-Built *Phase 4b, D-2* | 328 vapour paths compressible |
| D-11 | OPEN | [main.py:8420](../../backend/main.py#L8420) | Fixed vent split |
| D-12 | OPEN | [main.py:8192](../../backend/main.py#L8192) | Linear in suction P; `ejector_huang.py` is the candidate |
| D-13 | OPEN | [steam_system.py:74](../../backend/steam_system.py#L74) | K back-sized at a 50 % opening |
| D-14 | OPEN | [steam_system.py:89](../../backend/steam_system.py#L89) | `C_MP = C_LP = 25` |
| D-15 | OPEN | [steam_system.py:95](../../backend/steam_system.py#L95) | ×30 `F_lump` |
| D-16 | OPEN | [steam_system.py:287](../../backend/steam_system.py#L287) | `m_des × op/op_des` |
| D-17 | OPEN | [main.py:6013](../../backend/main.py#L6013) | Constant η_v |
| D-18 | OPEN | [main.py:6022](../../backend/main.py#L6022) | Current linear in rpm |
| D-19 | CLOSED (Phase 2) | As-Built *D-19/D-20/D-21* | The report's site was the 322F001 suction: head term restored |
| D-20 | PARTIAL — kept deliberately | stripper drain | LV-322501 is a 140.7 → 4 bar letdown whose ΔP does not vanish on empty; needs a two-phase valve model |
| D-21 | CLOSED (Phase 2) | — | HPCC guard proven unreachable and deleted |
| D-22 | OPEN | [main.py:4089](../../backend/main.py#L4089) | The `0.999` clamp is kept on the `STRIP_SLIP_GAIN` path |

### E. Fabricated gains and synthetic signals

| # | Status | Live anchor | Evidence |
|---|---|---|---|
| E-1 | OPEN | [main.py:7825](../../backend/main.py#L7825) | Two-sine froth noise |
| E-2 | OPEN | [main.py:5309](../../backend/main.py#L5309) | `SCRUB_CARB_ABS_GAIN` |
| E-3 | OPEN | [main.py:4720](../../backend/main.py#L4720) | `SCRUB_COND_SPINDLE_GAIN` |
| E-4 | CLOSED — dead | [main.py:4535](../../backend/main.py#L4535) | `SYN_P_DEFICIT_GAIN`/`SYN_P_VENT_GAIN` have no reader; delete |
| E-5 | RECLASSIFIED | [main.py:4672](../../backend/main.py#L4672) | Not fictitious: 1 − ρ_v/ρ_l from PFD streams 204/206, a specific-volume term. Its fidelity is bounded by A-1 |
| E-6 | OPEN | [main.py:786](../../backend/main.py#L786) | `STRIP_SLIP_GAIN = 4.0`, live at [main.py:4089](../../backend/main.py#L4089) |
| E-7 | OPEN | [main.py:7392](../../backend/main.py#L7392) | `REACT_NC_LOOP_GAIN` |
| E-8 | OPEN | [main.py:4387](../../backend/main.py#L4387) | `REACT_NC_OVERFLOW_GAIN` |
| E-9 | OPEN | [main.py:7585](../../backend/main.py#L7585) | High-pass forward pulse |
| E-10 | OPEN | [main.py:4394](../../backend/main.py#L4394) | `REACT_FRESH_FRAC` |
| E-11 | OPEN | [main.py:7687](../../backend/main.py#L7687) | `TIC_329005_LOAD_GAIN` |
| E-12 | OPEN | [consequence.py:192](../../backend/consequence.py#L192) | Entrainment power law |

**Measured this revision** (engine run, dt = STEP_CAP 0.25 s, fresh `State()`, HEAD in a side worktree):
the 3 000 s design hold matches HEAD to 1.8e-5 bar on PT-329201 and 0.01 °C on every stage
temperature. On a step of all four chest-TIC masters (+2/+2/+1/+1 °C), neither tree oscillates and
settled temperatures agree within 0.03 °C. The physical chests need more valve travel for the same
chest pressure (PV-329202 settles at 87.0 % against 83.5 %), and PV-329212 peaks at 99.7 % against
HEAD's 92 %: the 90 % design stroke leaves 324E003 little authority.

### The three findings that invalidate the model as a physics engine

> **Status 2026-09-15 (see §0a).** (1) still stands, but its source is now located: the credit
> mirrors the `REACT_TEAR_DES` reactor-feed tear. (2) is **no longer true**: `thermo_service` wires
> `vle_nh3co2h2o` + SRK + Extended UNIQUAC into the 323 stages and, through the anchored `k_ratio`,
> into the reactor, stripper and scrubber. Only 322E002 keeps its calibration, and it does so
> deliberately. (3) is **no longer true**: C-1, C-2 and A-8 closed in Phase 3.

1. **A fabricated mass source keeps the HP loop pressure on its design value.**
   [main.py:7956](../../backend/main.py#L7956) subtracts `SYN_LOOP_RESID_DES_KGH = −2168.1 kg/h` from
   the synthesis-loop mass balance so that `dP/dt` is exactly zero at design. The loop is **not**
   mass-conservative; it has a 2.17 t/h phantom source wired in by construction.

2. **No rigorous thermodynamic boundary exists anywhere in the HP synthesis loop.**
   `thermo_extended_uniquac` is imported at [main.py:42](../../backend/main.py#L42) but is called
   **only** from `evap_w_eq()` (the 324 evaporators). `vle_nh3co2h2o.py` is never imported at all.
   The reactor, stripper, HPCC and scrubber — the entire 322 unit — run on frozen split-fraction
   vectors measured at one point.

3. **The reactor has no kinetics and no reaction energy balance.**
   Urea extent is `ξ_des × load × f(N/C, H/C, T)`
   ([main.py:3979](../../backend/main.py#L3979)); biuret extent is `ξ_des × load`
   ([main.py:3981](../../backend/main.py#L3981)). Reactor temperature is a prescribed axial ΔT
   profile scaled by the conversion factor, not `ρVc_p dT/dt = ΣṁH + (−ΔH_rxn)r V − Q_loss`.

---

## A. Algebraic State Hacks

> *Criterion: pressure, temperature or level assigned algebraically instead of integrated from
> dM/dt and dH/dt.*

### A-1 — HP synthesis loop pressure from a lumped linear "kg per bar" capacitance
**File / line:** [`backend/main.py:7959`](../../backend/main.py#L7959), constant at
[`main.py:3648`](../../backend/main.py#L3648)

```python
C_loop = SYN_LOOP_C_KG_PER_BAR          # 1500.0 kg/bar
s.p_syn_bara = clamp(s.p_syn_bara + m_net_loop / C_loop * (dt / 3600.0), 10.0, 180.0)
```

**Heuristic:** PT-329201 is `P += Δm / 1500`. A single scalar linearises the pressure–inventory
relation of a two-phase NH₃/CO₂/H₂O/urea system across 10–180 bar a. It carries no volume, no
temperature, no composition and no phase behaviour. `dP/dT|_V = 0` — heating the loop at constant
mass cannot raise its pressure.

**Required replacement:** integrate vapour-space mass and energy and close on an EOS.

$$\frac{dM_v}{dt}=\sum \dot m_{in}^v-\sum \dot m_{out}^v+\dot m_{vap}-\dot m_{cond},\qquad
\frac{dU}{dt}=\sum \dot m_{in}h_{in}-\sum \dot m_{out}h_{out}+Q$$

$$P=P\!\left(\frac{M_v}{V_v},T,\mathbf{y}\right)\ \text{via SRK/PR:}\quad
P=\frac{RT}{v-b}-\frac{a\alpha(T)}{v(v+b)+b(v-b)}$$

with $V_v = V_{vessel} - M_l/\rho_l(T,\mathbf{x})$ so that a rising liquid level compresses the
vapour space — the mechanism the constant `C_loop` deletes.

---

### A-2 — Fabricated mass source term in the synthesis-loop balance
**File / line:** [`backend/main.py:7956`](../../backend/main.py#L7956), constant at
[`main.py:3647`](../../backend/main.py#L3647)

```python
SYN_LOOP_RESID_DES_KGH = SYN_LOOP_IN_DES_KGH - SYN_LOOP_OUT_DES_KGH    # −2168.1 kg/h
...
m_net_loop = ((m_in_loop - m_out_loop) - m_loop_frac * SYN_LOOP_RESID_DES_KGH
              + m_phase_shift - m_psv_kgh)
```

**Heuristic:** the model's own five-term boundary balance does not close, so the −2168.1 kg/h
residual is credited back into `dM/dt` to force `dP/dt = 0` at design. This is a **2.17 t/h phantom
mass source** (0.75 % of loop throughput) permanently wired into the flowsheet, gated by the
level-derived `m_loop_frac`.

**Required replacement:** the residual is a symptom of unclosed component balances upstream. Solve
the recycle by tearing to convergence rather than papering over the gap:

$$\mathbf{R}(\mathbf{z}_{tear})=\mathbf{z}_{tear}-\mathbf{G}(\mathbf{z}_{tear})=\mathbf{0}$$

iterated by Wegstein or Newton until $\|\mathbf{R}\|_\infty<10^{-6}$, then
$\sum_{in}\dot m-\sum_{out}\dot m=dM/dt$ with **no** residual term. Component-wise:
$\sum_{in}\dot n_i-\sum_{out}\dot n_i+\sum_r\nu_{i,r}\xi_r=dN_i/dt$.

---

### A-3 — Tuned "loop-fill" multiplier applied directly to every HP accumulation rate
**File / line:** [`backend/main.py:5802-5804`](../../backend/main.py#L5802); applied at
[`main.py:5811`](../../backend/main.py#L5811), [`main.py:6102`](../../backend/main.py#L6102),
[`main.py:6037`](../../backend/main.py#L6037)

```python
_fc         = 0.06     # empty-loop net-rate scale (Smith-calibrated to Section 6.4 band)
_fe         = 8.0      # gate exponent (Smith-calibrated to Section 6.4 band)
k_loop_fill = _fc + (1.0 - _fc) * _mf_prev ** _fe
```

**Heuristic:** the net accumulation of the reactor, stripper sump and HPCC is **multiplied by up to
16×-slower** so that the emergent cold-start pressurisation time constant lands in a DCS-fitted band.
Mass is destroyed and created by a curve-fit: when `k_loop_fill = 0.06`, 94 % of the net inflow to
the reactor holdup simply vanishes.

**Required replacement:** the fill time constant must emerge from real geometry. Remove the factor
and let

$$\frac{dM_j}{dt}=\sum_{in}\dot m-\sum_{out}\dot m ,\qquad L_j=\frac{M_j}{\rho_j(T,\mathbf{x})A_j}$$

with $A_j$ and $V_j$ from the datasheets in `References/Datasheets`. If the emergent τ then
disagrees with the 3.6.2025 trend, the discrepancy is in the vessel volumes, the vapour-space EOS
(A-1) or the fill-line hydraulics (D-*), and belongs there — not in a rate scaler.

---

### A-4 — HPCC level as a dimensionless-ratio ODE on a prescribed time constant
**File / line:** [`backend/main.py:6099-6103`](../../backend/main.py#L6099)

```python
phi_in_hpcc  = hpcc["liq_kgh"] / _hpcc_liq_des
phi_out_hpcc = phi_fwd * (s.hpcc_level_pct / HPCC_LEVEL_NLL_PCT)
dL_hpcc      = k_loop_fill * (phi_in_hpcc - phi_out_hpcc) * 100.0 * dt / (HPCC_TAU_FILL_MIN * 60.0)
```

**Heuristic:** LT-322E002 is integrated in **percent**, not mass. Inflow and outflow are
dimensionless ratios to design; the drain is *linear* in level; the rate is divided by a
hand-chosen `HPCC_TAU_FILL_MIN`. There is no vessel cross-section, no density, no head.

**Required replacement:**

$$\frac{dM}{dt}=\dot m_{cond}-\dot m_{drain},\qquad
\dot m_{drain}=C_v\,N_6\,Y\sqrt{\rho_l\,\Delta P},\quad
\Delta P=P_{shell}+\rho_l g h-P_{down}$$

$$h=\frac{M}{\rho_l(T,\mathbf x)A_{shell}},\qquad L\%=100\,\frac{h-h_{LRV}}{h_{URV}-h_{LRV}}$$

Note the gravity term makes drain $\propto\sqrt{h}$, not $\propto h$.

---

### A-5 — Steam chest pressure tied directly to valve position
**File / line:** [`backend/main.py:2614-2622`](../../backend/main.py#L2614); called at
[`main.py:6340`](../../backend/main.py#L6340), [`main.py:6512`](../../backend/main.py#L6512),
[`main.py:6577`](../../backend/main.py#L6577), [`main.py:7395`](../../backend/main.py#L7395)

```python
def steam_chest_pressure(valve_open_pct, header_pressure_bara):
    """Valve-position chest pressure driven by the connected live header."""
    return clamp(valve_open_pct / 100.0 * header_pressure_bara, 0.02, header_pressure_bara)
```

**Heuristic:** the textbook example of the defect named in the audit brief — chest pressure is
**literally** `opening% × header pressure`. A 50 % open valve halves the chest pressure regardless
of steam flow, condensing duty, or chest volume. Every downstream `tsat_steam(p_chest)` inherits it,
so 323E002, 323E010, 324E001 and 324E003 shell temperatures are all valve-position lookups.

**Required replacement:** the chest is a condensing vapour space. Integrate it:

$$\frac{dM_{chest}}{dt}=\dot m_{valve}(P_{hdr},P_{chest},h)-\dot m_{cond},\qquad
\dot m_{cond}=\frac{UA\,\big(T_{sat}(P_{chest})-T_{proc}\big)}{\lambda(P_{chest})}$$

$$\dot m_{valve}=C_v\,N_9\,F_p\,P_1\,Y\sqrt{\frac{x}{\gamma\,T_1\,Z\,M}},\qquad
Y=1-\frac{x}{3F_\gamma x_T},\quad x=\min\!\left(\frac{\Delta P}{P_1},F_\gamma x_T\right)$$

$P_{chest}$ then follows from $M_{chest}/V_{chest}$ on the steam tables (`iapws_if97.py` is already
present and unused for this).

---

### A-6 — Column and drum pressures on a universal, copy-pasted capacitance
**File / line:** [`main.py:6877`](../../backend/main.py#L6877),
[`main.py:6990`](../../backend/main.py#L6990), [`main.py:6558`](../../backend/main.py#L6558);
constants at [`main.py:986`](../../backend/main.py#L986),
[`1177`](../../backend/main.py#L1177), [`1298`](../../backend/main.py#L1298),
[`1341`](../../backend/main.py#L1341), [`1371`](../../backend/main.py#L1371),
[`1631`](../../backend/main.py#L1631), [`1634`](../../backend/main.py#L1634),
[`1728`](../../backend/main.py#L1728), [`1785`](../../backend/main.py#L1785)

```python
R323_F010_P_KP = 0.02 ; R328_C003_P_KP = 0.02 ; R328_C002_P_KP = 0.02
R328_C004_P_KP = 0.02 ; A328_C001_P_KP = 0.02 ; R324_F001_P_KP = 0.02
R324_F003_P_KP = 0.02 ; R328_D001_P_KP = 0.05 ; R3232_E011_P_KP = 0.05
...
s.a328_c002_P = max(s.a328_c002_P + R328_C002_P_KP*(gen737 - m_737)/3600.0*dt, 0.1)
```

**Heuristic:** nine vessels of wildly different volume, temperature and vapour molecular weight —
a 0.46 bar a vacuum pre-evaporator, a 16.8 bar a hydrolyser, a 2.6 bar a reflux drum — share the
**same** `0.02 bar per kg/s` coefficient. The physical coefficient is $RT/(V M)$ and varies by more
than an order of magnitude across this set.

**Required replacement:** per-vessel, from geometry and state:

$$\frac{dP}{dt}=\frac{RT}{V_v \overline{M}}\left(\dot n_{gen}-\dot n_{out}\right)
+\frac{P}{T}\frac{dT}{dt}-\frac{P}{V_v}\frac{dV_v}{dt}$$

with $V_v = V_{vessel}-M_l/\rho_l$ (so level swell compresses the vapour space) and $\overline M$
the live vapour mixture molecular weight.

---

### A-7 — Flash-drum pressure chased toward a flow-proportional target
**File / line:** [`backend/main.py:6488-6489`](../../backend/main.py#L6488); gain at
[`main.py:933`](../../backend/main.py#L933)

```python
R323_F004_P_GAIN = 0.45     # bar a per unit fractional flash-vapour excess
p_f004_tgt = R323_F004_P_BARA + R323_F004_P_GAIN * (m_701 - R323_M701_DES) / R323_M701_DES
s.r323_f004_P = clamp(s.r323_f004_P + (p_f004_tgt - s.r323_f004_P) / R323_F004_P_TAU_S * dt, 0.3, 6.0)
```

**Heuristic:** 323F004 pressure is an **algebraic setpoint** (design + 0.45 bar per unit of relative
vapour excess) that the state chases with an arbitrary first-order lag. Pressure is a follower of
flow, when physically flow is a follower of pressure.

**Required replacement:** as A-6 for the drum's own vapour space, with the outlet line to the LPCC
carrying a real conductance:

$$\dot m_{701}=C\sqrt{\frac{P_{F004}^2-P_{LPCC}^2}{Z\,T\,\overline M}},\qquad
\frac{dP_{F004}}{dt}=\frac{RT}{V_v\overline M}\left(\dot n_{flash}-\dot n_{701}\right)$$

The correct pattern is already implemented once in this repo —
[`c003_pressure_coupling.py:47`](../../backend/c003_pressure_coupling.py#L47) uses
$Q=C\sqrt{P_1^2-P_2^2}$ — and should be generalised rather than left as a one-off.

---

### A-8 — Reactor temperature profile prescribed, not solved from the reaction enthalpy
**File / line:** [`backend/reactor.py:176-206`](../../backend/reactor.py#L176); constants
[`main.py:3352-3356`](../../backend/main.py#L3352); integration
[`main.py:5940-6000`](../../backend/main.py#L5940)

```python
REACT_THERM_TAU_MIN  = 8.0       # carbamate-exotherm thermal time constant (min)
REACT_DT_COL_DES     = REACT_OVERFLOW_T_C - HPCC_T_PROD_DES_C     # 13.0 C
#   dT_n/dt = [ (T_{n-1} - T_n) + g_n·ΔT_col ] / τ_n
#   ΔT_col = REACT_DT_COL_DES · conversion_factor
```

**Heuristic:** the column temperature rise is **imposed** as a fixed 13.0 °C scaled by a
dimensionless conversion factor, distributed over four nodes by an exponential
$G(\zeta)=1-e^{-\beta\zeta}$ shape function. The exotherm never enters as an energy quantity.
Consequently: reactor temperature cannot respond to feed enthalpy changes, to the NH₃/CO₂ ratio's
effect on heat of solution, or to the true balance between carbamate formation (−117 kJ/mol) and
dehydration (+15.5 kJ/mol) — only to the ratio $X/X_{des}$.

**Required replacement:** a genuine node energy balance,

$$\rho_n V_n c_{p,n}\frac{dT_n}{dt}
=\dot m\,c_p\,(T_{n-1}-T_n)
+V_n\!\!\sum_{r}\left(-\Delta H_{r}(T_n)\right) r_{r,n}
-U_nA_n(T_n-T_\infty)-\dot m_{vap,n}\lambda_n$$

with $\Delta H_{carb}=-117$ kJ/mol and $\Delta H_{dehyd}=+15.5$ kJ/mol (already sourced in this repo
at [`main.py:2478`](../../backend/main.py#L2478)) and $r_{r,n}$ from the kinetics required in C-1.

---

### A-9 — Stripper bottom and top temperatures from anchored sensitivity coefficients
**File / line:** [`backend/main.py:3092-3095`](../../backend/main.py#L3092)

```python
T_bot_C = min(STRIP_T_BOTTOM_DES_C + 0.7 * dTs + dT_bot + dT_strip, T_steam_C)
T_top_C = min(STRIP_T_TOPGAS_DES_C + 0.6 * dTs + STRIP_T_TOP_LOAD_K * dT_bot + dT_strip, T_steam_C)
```

**Heuristic:** TT-322004 and TT-322013 are `design_temperature + 0.7·ΔT_steam + Σ(shaped exponential
corrections)`. The coefficients 0.7 and 0.6 are unsourced. `dT_bot`, `dT_strip` and `dT_flood` are
each `gap × (1 − e^{−K·x})` shapes with hand-chosen `K`
([`main.py:3061`](../../backend/main.py#L3061), [`3079`](../../backend/main.py#L3079),
[`3088`](../../backend/main.py#L3088)).

**Required replacement:** falling-film tube energy balance per axial increment,

$$\dot m_l c_{p,l}\frac{dT_l}{dz}=U\pi d_i\big(T_{sat}(P_{shell})-T_l\big)
-\sum_i \dot n_{i,desorb}(z)\,\Delta H_{vap,i}
-\dot n_{carb}(z)\,\Delta H_{carb}$$

integrated over the DDS 6.000 m tube length with the geometry already transcribed at
[`main.py:3532-3538`](../../backend/main.py#L3532) (2600 tubes, 25.0 mm ID, 1519 m²).

---

### A-10 — Scrubber off-gas and overflow temperatures from linear gain tables
**File / line:** [`backend/main.py:4162-4164`](../../backend/main.py#L4162),
[`main.py:4145`](../../backend/main.py#L4145); gains at
[`main.py:3488-3490`](../../backend/main.py#L3488)

```python
SCRUB_OFFGAS_T_GAIN       = 120.0  # C / (N/C unit)
SCRUB_OFFGAS_T_VENT_GAIN  = 20.0   # C / (theta/theta_des - 1)
SCRUB_OVERFLOW_T_VENT_GAIN = 12.0  # C / (theta/theta_des - 1)
...
t_offgas = min(max(SCRUB_OFFGAS_T_C + SCRUB_OFFGAS_T_GAIN * (nc - SCRUB_OFFGAS_NC_DES)
                   + SCRUB_OFFGAS_T_VENT_GAIN * theta_dev, t_ccw_in), SCRUB_T_PROC_C)
```

**Heuristic:** TT-322011 = 114.0 °C + 120 °C per unit of loop N/C deviation + 20 °C per unit of
HV-322604 opening deviation, clamped between the CCW inlet and a fixed ceiling. There is no vapour
enthalpy, no dew point and no condensation.

**Required replacement:** a condensing-vapour energy balance closed on the mixture dew point,

$$\dot m_{og}h_{og}(T_{out},P,\mathbf y)=\dot m_{in}h_{in}-Q_{cond},\qquad
Q_{cond}=UA\,\Delta T_{lm},\qquad T_{out}\ge T_{dew}(P,\mathbf y)$$

with $T_{dew}$ from the same VLE model required in B-1.

---

### A-11 — 323C003 / 323F004 bubble points from pure-water saturation offsets
**File / line:** [`backend/main.py:6372`](../../backend/main.py#L6372),
[`main.py:6456`](../../backend/main.py#L6456)

```python
T_bub_c003 = R323_C003_T_SP_C + (tsat_steam(s.r323_c003_P) - _R323_TSAT_C003_DES)
T_sat_f004 = R323_F004_T_SP_C + (tsat_steam(s.r323_f004_P) - _R323_TSAT_F004_DES)
```

**Heuristic:** the bubble point of a 55–69 wt % urea / ammonium-carbamate / NH₃ liquor is taken as
the **pure-water** saturation temperature, shifted so it hits the design value. Boiling-point
elevation, which is 8–20 °C over this concentration range and is exactly what the evaporation train
must model, is a frozen constant.

**Required replacement:**

$$\sum_i y_i=\sum_i \frac{\gamma_i(T,\mathbf x)\,x_i\,P_i^{sat}(T)\,\phi_i^{sat}}{\phi_i(T,P,\mathbf y)\,P}=1$$

solved for $T$. `bubble_T_raoult()` at [`main.py:1985`](../../backend/main.py#L1985) exists but is
ideal-solution (γ = 1) and is bypassed here.

---

### A-12 — Reactor discharge outflow ignores its own head argument
**File / line:** [`backend/reactor.py:325-347`](../../backend/reactor.py#L325)

```python
def outlet_line_outflow_kgph(level_m, m_fwd_ref_kgph, level_des_m, theta_pct, theta_des_pct):
    """... m_out = m_fwd_ref · (θ / θ_des) · ( max(level_m, 0) / level_des_m )"""
    theta_ratio = max(theta_pct, 0.0) / max(theta_des_pct, 1.0e-6)
    return m_fwd_ref_kgph * theta_ratio
```

**Heuristic:** two defects in nine lines. (a) The documented law is linear in level; the code
**silently drops the level term entirely** — `level_m` and `level_des_m` are dead parameters, so the
322R001 discharge is a pure valve-stroke lookup with no hydraulic feedback at all. (b) Even the
documented law is wrong: a bottom take-off under a 20 m column drains as $\sqrt{h}$, not $h$.

**Required replacement:**

$$\dot m_{out}=C_v N_6 f(\theta)\sqrt{\rho_l\Big(P_{react}+\rho_l g h-P_{strip}-\Delta P_{line}\Big)}$$

with $f(\theta)$ the HV-322605 installed characteristic and $\Delta P_{line}$ from D-1.

---

### A-13 — Vacuum-condenser hot outlet as a fixed approach to design
**File / line:** [`backend/main.py:2840`](../../backend/main.py#L2840)

```python
hot_out = spec["hot_out_c"] + (hot_in_c - spec["hot_in_c"])
```

**Heuristic:** every 324 vacuum condenser's process outlet temperature is the design outlet plus
whatever the inlet moved — a frozen approach temperature. Cooling-water flow, fouling and
non-condensable blanketing cannot change it.

**Required replacement:** ε-NTU on the live streams,

$$\varepsilon=\frac{1-e^{-NTU(1-C_r)}}{1-C_re^{-NTU(1-C_r)}},\quad NTU=\frac{UA}{C_{min}},\quad
T_{h,out}=T_{h,in}-\varepsilon\frac{C_{min}}{C_h}(T_{h,in}-T_{c,in})$$

with $T_{h,out}$ floored at the mixture dew point at the live partial pressure of the condensables.

---

### A-14 — Vacuum-train stream flows as hardcoded design numbers plus deltas
**File / line:** [`backend/main.py:2872-2879`](../../backend/main.py#L2872)

```python
streams = {
    "705": 14799.0 + (vapour1_kgh - R324_V1_DES) + (false_air1_kgh - R324_F001_FA_DES),
    "790": 12040.0 + (m_evap_kgh - R323_MEVAP_DES),
    "709": 3342.0 + (vapour2_kgh - R324_V2_DES) + (false_air2_kgh - R324_F003_FA_DES),
}
streams["703"] = 26840.0 + (streams["705"] - 14799.0) + (streams["790"] - 12040.0)
```

**Heuristic:** PFD table values as literals in executable code, with live behaviour expressed as an
additive offset. There is no flow calculation of any kind.

**Required replacement:** mix the actual packets — $\dot m_{703}=\dot m_{705}+\dot m_{790}$,
$\dot n_{i,703}=\dot n_{i,705}+\dot n_{i,790}$, $h_{703}\dot m_{703}=\sum h_j\dot m_j$ — and let the
design numbers emerge as the converged result at design inputs rather than being typed in.

---

### A-15 — Design-point identity short circuits
**File / line:** [`backend/main.py:2811-2823`](../../backend/main.py#L2811),
[`main.py:3750`](../../backend/main.py#L3750),
[`main.py:3756`](../../backend/main.py#L3756), [`main.py:3760`](../../backend/main.py#L3760)

```python
if (inlet == spec["inlet_kgh"] and nc == spec["vent_kgh"] and hot_in_c == spec["hot_in_c"] ...):
    return { ...spec design values verbatim... }
...
if p_rat == 1.0 and T_k == _HPCC_BUB_T0_K:
    return dict(HPCC_FRAC_GAS_DES)       # exactly at the calibration point -> phi IS the design
```

**Heuristic:** explicit `if (at design) return design` branches. The model's headline accuracy claim
at the design point is a lookup table, not a solve, and any residual of the underlying model at that
point is invisible.

**Required replacement:** delete the branches. A correct model reproduces the design point *because
it converges there*; if it does not, that is the defect to fix.

---

### A-16 to A-19 — further algebraic assignments (summary)

| # | File:line | Heuristic | Required |
|---|---|---|---|
| A-16 | [`main.py:6759`](../../backend/main.py#L6759) | `bot_c005 = A323_C005_BOT_DES * (M / M_DES)` — 323C005 bottoms linear in holdup | $\dot m=C_vN_6\sqrt{\rho\,(\rho g h+\Delta P)}$ |
| A-17 | [`main.py:2627`](../../backend/main.py#L2627) | `gravity_outflow_323f010 = M_DES*sqrt(M/M_DES)` — Torricelli on *mass ratio*, design-anchored | $\dot m=C_dA\rho\sqrt{2g h}$, $h=M/(\rho A_{tank})$ |
| A-18 | [`main.py:5568`](../../backend/main.py#L5568) | `P_line_bara = P_line_float - 0.25 * pv_open` — CO₂ line pressure directly proportional to PV-322203 stroke | Compressor map + vapour-space ODE; see D-2 |
| A-19 | [`main.py:5567`](../../backend/main.py#L5567) | `P_line_float = min(p_syn + DP_HP_DES, ceil)` — 322K001 discharge *defined* as loop P + 3.5 bar | Polytropic head map $H(Q_{in},N)$, $P_2=P_1\big(1+\frac{H\,\eta_p (n-1)}{n\,Z R T_1/M}\big)^{n/(n-1)}$ with surge/stonewall limits |

---

## B. Empirical Phase Splits

> *Criterion: flash tanks, condensers and strippers bypassing a rigorous thermodynamic boundary
> (Extended UNIQUAC / SRK) via fixed V/L ratios, hardcoded solubility limits, or static enthalpy
> offsets.*

### B-1 — The rigorous thermodynamic model is imported but structurally unused
**File / line:** [`backend/main.py:42`](../../backend/main.py#L42); the only call sites are
[`main.py:140-142`](../../backend/main.py#L140) inside `evap_w_eq()`, plus telemetry strings at
[`main.py:7434`](../../backend/main.py#L7434) and [`main.py:7549`](../../backend/main.py#L7549).

**Heuristic:** `thermo_extended_uniquac` (429 lines) touches **only** the urea/water binary in the
324 evaporators, and even there it is used in departure form:

```python
return clamp(w_des + (w_model - w_model_des), 1e-9, 1 - 1e-9)
```

i.e. `design + (model − model_at_design)`, not the model's absolute answer.
`vle_nh3co2h2o.py` (315 lines, with a 69 kB pre-computed grid at `.vle_nh3co2h2o_grid.json`) is
**never imported by the engine at all**. The entire 322 HP synthesis loop — reactor, stripper, HPCC,
scrubber — runs without any thermodynamic model.

**Required replacement:** every phase boundary in the flowsheet must close on

$$\ln\gamma_i=\ln\gamma_i^{C}+\ln\gamma_i^{R}+\ln\gamma_i^{DH},\qquad
K_i=\frac{\gamma_i\,\phi_i^{sat}P_i^{sat}\,\text{PF}_i}{\phi_i^{V}P}$$

with the Debye–Hückel term active for the ionic carbamate/bicarbonate species, feeding a
Rachford–Rice isothermal flash

$$\sum_i\frac{z_i(K_i-1)}{1+\psi(K_i-1)}=0$$

and an isenthalpic (PH) flash wherever a letdown valve appears.

---

### B-2 — HP scrubber products are the design vectors scaled by load
**File / line:** [`backend/main.py:4052-4053`](../../backend/main.py#L4052)

```python
offgas   = {k: SCRUB_OFFGAS_KMOLH_DES.get(k, 0.0) * s for k in MW_COMP}    # pinned
overflow = {k: SCRUB_OVERFLOW_KMOLH_DES.get(k, 0.0) * s for k in MW_COMP}  # pinned
```

**Heuristic:** 322E003's two product streams are **not computed**. They are the PFD design vectors
multiplied by the CO₂ load ratio `s`. Composition is invariant with temperature, pressure, CCW duty
and wash rate; deviations are then grafted on by the gain terms in B-3, E-2 and E-3.

**Required replacement:** a rate-based absorber with the carbamate reaction in the liquid film,

$$N_i=k_L^0 E_i\,a\,\big(c_i^*-c_i\big),\qquad
E_i=f(\mathrm{Ha}),\quad \mathrm{Ha}=\frac{\sqrt{k_2 c_{NH_3}D_i}}{k_L^0}$$

with $c_i^*=p_i/H_i(T)$, closed simultaneously with the shell-side energy balance
$Q=UA\,\Delta T_{lm}$ and the carbamate equilibrium $K_p=p_{NH_3}^2p_{CO_2}$.

---

### B-3 — "Cooling-limited condensation" flashes already-condensed material back by a scalar
**File / line:** [`backend/main.py:4093-4101`](../../backend/main.py#L4093); driver at
[`main.py:6166`](../../backend/main.py#L6166)

```python
rho_cond = (m_ccw_kgh / SCRUB_CCW_KGH_DES) * max(f_th, 0.0) / max(react["co2_scale"] * nu, 1e-6)
...
back = (1.0 - cf) * max(overflow[k] - carb[k], 0.0)
overflow[k] -= back ; offgas[k] += back
```

**Heuristic:** the condensation deficit is a **ratio of ratios** — (CCW flow ratio × thermal driving
ratio) ÷ (load ratio × pressure ratio). A fraction `(1 − ρ_cond)` of what design would have condensed
is then moved back to the vapour, *uniformly across all species*. NH₃, CO₂ and H₂O — with vapour
pressures differing by orders of magnitude at 140 bar a — flash back in identical proportion.

**Required replacement:** solve the condenser as a coupled heat-and-mass-transfer unit,

$$\dot n_{cond,i}=\frac{K_{G,i}\,a\,V\,(p_i-p_i^{int})}{RT},\qquad
Q=UA\Delta T_{lm}=\sum_i\dot n_{cond,i}\Delta H_{cond,i}+\dot m c_p\Delta T$$

with the interface composition from the VLE of B-1. The species split then emerges from relative
volatility, not from a common scalar.

---

### B-4 — HPCC condensation from frozen split fractions with a bolt-on K-value correction
**File / line:** [`backend/main.py:3224-3229`](../../backend/main.py#L3224),
[`main.py:3733-3785`](../../backend/main.py#L3733)

```python
HPCC_FRAC_GAS_DES = {"CO2": 0.2036, "NH3": 0.2977, "H2O": 0.0450,
                     "N2": 0.982, "O2": 1.0, "CH4": 1.0, "H2": 1.0, "Urea": 0.0, "Biuret": 0.0}
...
k_des = phi_d * (1.0 - psi_des) / (psi_des * (1.0 - phi_d))
K[k]  = k_des * math.exp((HPCC_FLASH_DH[k]/R) * (1/T_des - 1/T)) * (P_des/P)
```

**Heuristic:** K-values are **back-solved from a measured split at one point** and corrected by a
Clausius–Clapeyron slope and a `1/P` ideal-gas factor. The comment at
[`main.py:3237`](../../backend/main.py#L3237) is candid that "the split fractions above are a
calibration at ONE point". Activity coefficients are frozen inside `k_des`, so the strongly
non-ideal electrolyte melt has *zero* composition dependence — changing N/C or H/C at fixed T and P
moves no moles.

**Required replacement:** replace `_hpcc_flash_split()` with a genuine isothermal flash on the
Extended-UNIQUAC K-values of B-1, and close the outlet temperature on the **isenthalpic** condition
$h_{feed}(T_{in},P_{in})=\psi h^V(T,P,\mathbf y)+(1-\psi)h^L(T,P,\mathbf x)$ rather than on the
back-calculated `HPCC_UA`.

---

### B-5 — HPCC bubble pressure from two calibrated sensitivity coefficients
**File / line:** [`backend/main.py:3538-3539`](../../backend/main.py#L3538),
[`main.py:3681`](../../backend/main.py#L3681)

```python
HPCC_BUB_KN = 0.18   # 1/(N/C), bubble-P sensitivity to feed N/C (free NH3)  -- calib
HPCC_BUB_KW = -0.25  # 1/(H/C), bubble-P sensitivity to feed H/C (dilution)  -- calib
```

**Heuristic:** the bubble pressure of the carbamate melt is `P_des × (1 + 0.18·ΔL − 0.25·ΔW)`. Both
coefficients are labelled `-- calib` in the source.

**Required replacement:** $P_{bub}=\sum_i\gamma_i x_i P_i^{sat}\phi_i^{sat}/\phi_i^V$ solved on the
live melt composition.

---

### B-6 — Reactor vapour/liquid split as a frozen θ vector
**File / line:** [`backend/main.py:3303-3309`](../../backend/main.py#L3303), applied at
[`main.py:3987-3988`](../../backend/main.py#L3987)

```python
REACT_THETA_OG = {k: OGd_i / (OVd_i + OGd_i) ...}    # from the design vectors
overflow = {k: out_total[k] * (1.0 - REACT_THETA_OG[k]) for k in MW_COMP}
offgas   = {k: out_total[k] * REACT_THETA_OG[k]         for k in MW_COMP}
```

**Heuristic:** the reactor's off-gas/liquid partition is a constant fraction per species, computed
once from the PFD. Raising reactor pressure or temperature moves not one mole between phases.

**Required replacement:** flash the reactor effluent at $(T_{react},P_{react})$ on the VLE of B-1.
The design θ then falls out as the converged result.

---

### B-7 — Stripper split as design fractions × three ad-hoc efficiency ratios
**File / line:** [`backend/main.py:3125-3143`](../../backend/main.py#L3125); design fractions at
[`main.py:487`](../../backend/main.py#L487)

```python
STRIP_FRAC_DES = {"NH3": 0.8546, "CO2": 0.8606, "H2O": 0.1313, "N2": 0.9987, ...}
eta_co2 = clamp(0.5 + 0.5 * co2_scale, 0.4, 1.05)
eta_P   = clamp(2.0 - P_bara / STRIP_P_DES_BARA, 0.85, 1.15)
mod = clamp(eta_T_steam * eta_co2 * eta_P, 0.0, 1.12) * min(g_T, 1.0) * g_flood
f = clamp(STRIP_FRAC_DES.get(k, 0.0) * mod, 0.0, 0.999)
```

**Heuristic:** `eta_co2 = 0.5 + 0.5·load` and `eta_P = 2 − P/P_des` are invented linear maps with
invented clamps. `eta_T_steam = T_steam/T_des` is a bare temperature ratio in °C — not even a
driving force. The product of five such ratios multiplies a frozen split fraction.

**Required replacement:** stage-wise rate-based stripping down the tube,

$$\frac{d\dot n_{i,l}}{dz}=-K_{OG,i}\,a\,A\,\big(p_i-p_i^*(\mathbf x,T)\big),\qquad
p_i^*=\gamma_i x_i P_i^{sat}$$

with carbamate decomposition $\mathrm{NH_2COONH_4}\rightleftharpoons 2\mathrm{NH_3}+\mathrm{CO_2}$
at its equilibrium $K_p(T)$, and the tube energy balance of A-9 supplying the decomposition endotherm.

---

### B-8 — 323/324 flash vapour compositions from back-solved, T- and P-independent volatilities
**File / line:** [`backend/main.py:2062-2065`](../../backend/main.py#L2062),
[`main.py:2088-2096`](../../backend/main.py#L2088); applied at
[`main.py:6419`](../../backend/main.py#L6419), [`6482`](../../backend/main.py#L6482),
[`6559`](../../backend/main.py#L6559)

```python
aw = y["H2O"] / w_out["H2O"]
alpha = {k: ((y[k] / w_out[k]) / aw ...) for k in SOL_SPECIES}
alpha["H2O"] = 1.0
...
def sol_vapour_y(w, alpha):
    num = {k: alpha[k] * w.get(k, 0.0) for k in SOL_SPECIES}
    return {k: num[k] / sum(num.values()) for k in SOL_SPECIES}
```

**Heuristic:** relative volatilities are back-solved from the PFD design rows and then held
**constant**. The same frozen α vector governs 323C003 (135 °C, 4.1 bar a), 323F004 (106 °C,
1.13 bar a) and 323F010 (99 °C, 0.46 bar a) — three stages spanning an order of magnitude in
pressure. Additionally at [`main.py:2060`](../../backend/main.py#L2060) water is used as a **slack
variable** (`vap["H2O"] += m_vap - sum(vap.values())`) to absorb whatever the balance fails to close.

**Required replacement:** $y_i=K_i(T,P,\mathbf x)\,x_i$ with $K_i$ from B-1, and $\sum y_i=1$ as a
solved constraint rather than an imposed normalisation.

---

### B-9 — Static enthalpy offsets in the vacuum condensers
**File / line:** [`backend/main.py:2733`](../../backend/main.py#L2733), used at
[`main.py:2851, 2855`](../../backend/main.py#L2851)

```python
"h_eff_kjkg": q_kw * 3600.0 / condensate,          # design lumped enthalpy
...
cond = min(max(inlet - nc, 0.0), q_cap * 3600.0 / spec["h_eff_kjkg"])
```

**Heuristic:** a single design "effective enthalpy" per condenser converts duty to condensate for
all operating points and all compositions — the static enthalpy offset named in the audit brief.
An NH₃-rich vent and a water-rich vent condense at the same kJ/kg.

**Required replacement:** $Q=\sum_i\dot n_{cond,i}\Delta H_{cond,i}(T,P)+\dot m c_p\Delta T_{sub}$
with per-species latent heats and the condensate split from the dew-point calculation.

---

### B-10 — Crystallization temperature as a linear scaling of mass loading
**File / line:** [`backend/consequence.py:325-330`](../../backend/consequence.py#L325)

```python
def carbamate_crystallization_T(w_nh3, w_co2, w_ref=CARBAMATE_W_REF, t_ref=CARBAMATE_CRYST_T_C):
    return t_ref * clamp((max(w_nh3,0.0) + max(w_co2,0.0)) / max(w_ref,1e-9), 0.0, 1.5)
```

**Heuristic:** the carbamate saturation temperature is **directly proportional** to total NH₃+CO₂
mass fraction, anchored so a 60 °C reference stream returns 60 °C. That is a hardcoded solubility
limit in the exact sense the audit brief names.

**Required replacement:** solid–liquid equilibrium,

$$\ln\!\big(\gamma_\pm^{\nu}\,m_{NH_4^+}^{\nu_+}m_{NH_2COO^-}^{\nu_-}\big)=\ln K_{sp}(T),\qquad
\frac{d\ln K_{sp}}{dT}=\frac{\Delta H_{sol}}{RT^2}$$

Extended UNIQUAC already carries the solid phase for ammonium carbamate; this call should route to
it. Urea SLE (`urea_crystallization_T`, a linear interpolation of a solubility table) is acceptable
as a correlation but should carry the same activity basis.

---

### B-11 to B-14 — further phase-split violations (summary)

| # | File:line | Heuristic | Required |
|---|---|---|---|
| B-11 | [`main.py:6380`](../../backend/main.py#L6380) | `m_305 = min(R323_PHI_V305·m_feed, m_flash+m_pool)` with `m_flash = M305_DES·(q/q_des)` — vapour rate as a duty ratio at fixed λ | PH flash: solve ψ from $h_{in}=\psi h^V+(1-\psi)h^L$ at $P_{col}$ |
| B-12 | [`main.py:6528`](../../backend/main.py#L6528) | `m_evap = min(MEVAP_DES·(feed ratio), MEVAP_DES·(duty ratio))` — evaporation as the lesser of two design-normalised ratios | Same PH flash with $P_i^{sat}$ over the live urea liquor and BPE from A-11 |
| B-13 | [`main.py:2842`](../../backend/main.py#L2842) | `ua_eff = UA_des · (1−x_nc)/(1−x_nc,des)` — non-condensable derate as a linear ratio | Colburn–Hougen: solve $T_{int}$ from $h_g(T_g-T_{int})+K_G\Delta H(p_g-p_{int})=U_o(T_{int}-T_c)$ |
| B-14 | [`main.py:2355`](../../backend/main.py#L2355) | `des_alpha_live` scales **all** volatile species by one scalar `f` from a Kremser residual | Per-species $K_i(T,P,\mathbf x)$ and a tray-by-tray MESH solve |

---

## C. Scripted Kinetics

> *Criterion: load-based conversion multipliers or fixed stoichiometric limits instead of
> Arrhenius-based rate equations $r=k\,f(C_A,T)$.*

### C-1 — Urea extent = design extent × load × an equilibrium correlation
**File / line:** [`backend/main.py:3979`](../../backend/main.py#L3979),
[`reactor.py:137`](../../backend/reactor.py#L137),
[`reactor.py:105-108`](../../backend/reactor.py#L105)

```python
xi_urea, _ov_discard, X_conv, L_feed, W_feed = reactor.react_couple(
    feed, dict(REACT_OVERFLOW_DES), REACT_XI_UREA_DES * s, T_overflow_c, ...)
...
xi_urea = xi_urea_scaled * conversion_factor(L, W, T_c)
```

where

```python
fL = (ALPHA_NC * g) / (1.0 + ALPHA_NC * g)               # saturation, a = 3.6180
fW = 1.0 / (1.0 + BETA_HC * W)                           # water penalty, b = 0.85
fT = math.exp(-K_TOPT * ((T_c - topt)**2 - (T0_DES_C - topt)**2))
return min(X_INF * fL * fW * fT, X_INF)
```

**Heuristic:** the load-based conversion multiplier named in the brief, in its purest form.
`REACT_XI_UREA_DES * s` is the design extent times the CO₂ load ratio; the "kinetics" module returns
a dimensionless number that multiplies it. The module docstring is explicit that the temperature
term "replaces the unbounded Arrhenius f_T" with a Gaussian parabola, and that the whole expression
is renormalised so it returns exactly 1.000000 at design. `BETA_HC` was "calibrated UP from 0.60";
`X_INF` was "SOLVED (was 0.85)" to make the anchor hold. Reaction extent is independent of residence
time, of holdup volume, and of concentration except through two feed ratios.

**Required replacement:** the two-step mechanism with real rate laws, integrated over the reactor's
own residence-time distribution.

$$\text{(1) } 2\mathrm{NH_3}+\mathrm{CO_2}\rightleftharpoons\mathrm{NH_2COONH_4}\quad(\text{fast, equilibrium-limited})$$
$$\text{(2) } \mathrm{NH_2COONH_4}\rightleftharpoons\mathrm{NH_2CONH_2}+\mathrm{H_2O}\quad(\text{rate-controlling})$$

$$r_2=k_2(T)\left(a_{carb}-\frac{a_{urea}a_{H_2O}}{K_{eq,2}(T)}\right),\qquad
k_2=A_2\exp\!\left(\frac{-E_{a,2}}{RT}\right)$$

with $a_i=\gamma_i x_i$ from B-1 and

$$\frac{dN_i}{dz}=\nu_i\,r_2\,A_{cs},\qquad
\tau=\int_0^{H}\frac{A_{cs}\rho_l}{\dot m}\,dz$$

so that conversion emerges from $k_2\tau$ and composition — and so that a level drop, a temperature
excursion or a residence-time change moves it.

---

### C-2 — Biuret formation as a pure load multiplier
**File / line:** [`backend/main.py:3981`](../../backend/main.py#L3981)

```python
xi_biu = REACT_XI_BIU_DES * s        # 2.414 kmol/h × load ratio
```

**Heuristic:** biuret extent in the reactor has **no temperature, concentration or residence-time
dependence whatsoever**. It is 2.414 kmol/h scaled by CO₂ load. Biuret is the principal product
quality specification for urea; the model cannot represent a quality excursion from a hot reactor.

**Required replacement:**

$$r_{biu}=A\exp\!\left(\frac{-E_a}{RT}\right)C_{urea}^2,\qquad
\xi_{biu}=\int_V r_{biu}\,dV$$

(the stripper already uses the right *form* — see C-3 — so the constants exist in-repo at
[`main.py:666-668`](../../backend/main.py#L666)).

---

### C-3 — Stripper hydrolysis extent from a dimensionless "efficiency"
**File / line:** [`backend/main.py:3096`](../../backend/main.py#L3096)

```python
xi_hyd_raw = STRIP_XI_HYD_DES * eta_T          # 88.1 kmol/h × the eta_T product of C/B-7 ratios
```

**Heuristic:** urea hydrolysis in 322E001 is the design extent times the same fabricated efficiency
product used for the phase split (B-7). No rate constant, no residence time, no water concentration.

**Required replacement:** the repo already has the correct law for this reaction in
[`main.py:2434-2467`](../../backend/main.py#L2434) (Inoue/Otsuka second-order,
$\ln k_H=21.8-11100/T$). Apply it here:

$$-\frac{dC_U}{dt}=k_H(T)\,C_U C_W,\qquad
\xi_{hyd}=\dot V\!\left[C_{U,0}-C_U(\tau)\right],\quad \tau=\frac{V_{tubes}\epsilon_l}{\dot V}$$

---

### C-4 — Stripper biuret: Arrhenius *form* on a design-anchored extent
**File / line:** [`backend/main.py:3098-3100`](../../backend/main.py#L3098)

```python
xi_biu_raw = (STRIP_XI_BIU_DES
              * math.exp((STRIP_BIU_EA / STRIP_R_GAS_J) * (1.0/STRIP_T_BIU_DES_K - 1.0/T_bot_K))
              * (feed["Urea"] / STRIP_UREA0))
```

**Heuristic:** partially correct — the temperature dependence is genuine Arrhenius and the urea
dependence is first-order. But the pre-exponential is replaced by the design extent, and the order
in urea is 1 where biuret formation ($2\,\mathrm{Urea}\rightarrow\mathrm{Biuret}+\mathrm{NH_3}$) is
second-order. Holdup volume and residence time do not appear.

**Required replacement:** $\xi=A e^{-E_a/RT}C_{urea}^2\,V_l$ with $A$ from the literature and $V_l$
from the tube geometry, so the design extent becomes a *prediction* rather than an *input*.

---

### C-5 — Downstream biuret via a triple-anchored ratio
**File / line:** [`backend/main.py:2098-2110`](../../backend/main.py#L2098)

```python
r_hold = max(M, 0.0) / st["M"]
r_urea = (w.get("Urea", 0.0) / st["w"]["Urea"]) ** SOL_BIU_ORDER
r_arrh = math.exp((SOL_BIU_EA/R) * (1/(st["T"]+273.15) - 1/(T_c+273.15)))
return st["a"]["xi"] * r_hold * r_urea * r_arrh
```

**Heuristic:** the same anchored-ratio pattern — design extent × holdup ratio × concentration ratio
× Arrhenius ratio. Structurally closer to correct than C-2, but still cannot predict an absolute
rate; every stage's design extent is itself back-solved from the PFD in `_sol_stage_anchor`.

**Required replacement:** as C-4, with mass-fraction converted to molar concentration
$C_{urea}=\rho w_{urea}/M_{urea}$ and $\xi = k(T)C_{urea}^2 V_l$.

---

### C-6 — Reactor conversion-deficit slip amplifier
**File / line:** [`backend/main.py:4005-4012`](../../backend/main.py#L4005); gain at
[`main.py:3423`](../../backend/main.py#L3423)

```python
REACT_OFFGAS_DEFICIT_GAIN = 1.0
delta_X = max(1.0 - X_conv / X_ref, 0.0)
g = REACT_OFFGAS_DEFICIT_GAIN * delta_X
for k in ("NH3", "CO2"):
    sh = min(g * offgas.get(k, 0.0), overflow.get(k, 0.0))
```

**Heuristic:** unconverted reagent is moved from liquid to off-gas in proportion to a normalised
conversion shortfall. It is mass-conserving (an improvement on a previous mass-creating version, per
the comment) but is a scripted consequence, not a phase equilibrium: the amount of NH₃ that leaves
overhead should follow from the flash of B-6, not from a conversion residual times a gain of 1.0.

**Required replacement:** delete. With C-1 and B-6 in place, lower conversion leaves more free NH₃
and CO₂ in the effluent and the flash partitions them correctly and automatically.

---

## D. Synthetic Hydraulics

> *Criterion: arbitrary time-delay queues, synthetic pressure drops, non-physical limits instead of
> mechanical $C_v$ curves, node pressures and compressible flow laws.*

### D-1 — Universal "design flow × normalised stroke × √ΔP ratio" pattern
**Files / lines (representative):**

| Tag | Line | Expression |
|---|---|---|
| LV-322501 stripper letdown | [`main.py:5780`](../../backend/main.py#L5780) | `STRIP_BOT_DES_KGH * (lv_open/46.1) * √(dP_lv/dP_des)` |
| LV-323501 | [`main.py:6388`](../../backend/main.py#L6388) | `R323_M314_DES * (lv501_op/OP_DES)` — no ΔP at all |
| LV-323505 | [`main.py:6464`](../../backend/main.py#L6464) | `R323_M319_DES * (lv505_op/OP_DES)` |
| LIC-328503 bottoms | [`main.py:6851`](../../backend/main.py#L6851) | `M743_DES * (lic503_op/50.0)` |
| LIC-328504 bottoms | [`main.py:6919`](../../backend/main.py#L6919) | `M747_DES * (lic504_op/50.0)` |
| LIC-328505 bottoms | [`main.py:6971`](../../backend/main.py#L6971) | `M739_DES * (lic505_op/50.0)` |
| PV-328203B | [`main.py:6898`](../../backend/main.py#L6898) | `M748_DES * (pic203b_op/OP_DES)` |
| 328C002 overhead | [`main.py:6875`](../../backend/main.py#L6875) | `M737_DES * √(dP_737/R328_E004_DP)` |
| 328C004 overhead | [`main.py:6988`](../../backend/main.py#L6988) | `M750_DES * √(dP_live/dP_des)` |
| 323D001 vent | [`main.py:7184`](../../backend/main.py#L7184) | `MV_DES * (op/op_des) * √(dP/dP_des)` |
| 323E011 vent | [`main.py:7236`](../../backend/main.py#L7236) | `MV_DES * (op/op_des) * √(dP/dP_des)` |
| 324F001 barometric leg | [`main.py:7451`](../../backend/main.py#L7451) | `R324_P1_DES * √(M/M_DES)` |
| all `_fic_flow` loops | [`main.py:4293-4300`](../../backend/main.py#L4293) | *"Delivered flow = design × (op/op_des)"* |

**Heuristic:** no valve in the engine has a $C_v$ or $K_{vs}$. Every flow is the design flow scaled
by a normalised stroke and, sometimes, a normalised √ΔP. Consequences: (a) the installed
characteristic is linear regardless of trim; (b) fluid density is absent (it cancels only if
constant, which it is not across 20–99 % urea); (c) `_fic_flow` has no ΔP term at all, so every flow
controller in units 323 and 328 is a pure valve-position gain that cannot be affected by a
downstream pressure change.

**Required replacement:** IEC 60534 / ISA-75.01 with datasheet trim data:

$$\dot m = N_6\,F_p\,C_v(h)\sqrt{\Delta P\,\rho_1}\qquad
C_v(h)=C_{v,max}\,R^{\,h-1}\ \text{(equal-\%)}\ \ \text{or}\ \ C_{v,max}h\ \text{(linear)}$$

with choked-flow limiting $\Delta P_{eff}=\min\!\big(\Delta P,\;F_L^2(P_1-F_F P_v)\big)$, and $\Delta P$
taken from **live node pressures** on both sides.

---

### D-2 — Compressible services treated as incompressible orifices
**File / line:** [`backend/core/valve.py:41`](../../backend/core/valve.py#L41),
[`main.py:4202`](../../backend/main.py#L4202), [`main.py:6153`](../../backend/main.py#L6153),
[`main.py:5573`](../../backend/main.py#L5573),
[`steam_system.py:206-211`](../../backend/steam_system.py#L206)

```python
valve = _eq_pct(hic_pct, SCRUB_HIC604_DES_PCT) * math.sqrt(dP / SCRUB_HV604_DP_DES)
...
def _valve_flow(K, opening_pct, p_up, p_down):
    """Incompressible orifice flow (kg/s)."""
    return K * (op / 100.0) * dP ** 0.5
```

**Heuristic:** HV-322604 lets NH₃/CO₂ vapour down from ~140.7 bar a to ~4 bar a — a pressure ratio of
0.028, deeply choked — and is modelled with an incompressible √ΔP law. The steam header let-downs
(9→4.4 bar a, ratio 0.49) are likewise below the critical ratio for steam (0.546) and likewise
incompressible. Choked flow is a function of upstream conditions **only**; these models make flow
keep rising as downstream pressure falls, which is physically impossible.

**Required replacement:**

$$\dot m = N_8\,F_p\,C_v\,P_1\,Y\sqrt{\frac{x\,M}{T_1 Z}},\qquad
Y=1-\frac{x}{3F_\gamma x_T},\qquad x=\min\!\left(\frac{\Delta P}{P_1},\;F_\gamma x_T\right)$$

so that $\dot m$ saturates at $x=F_\gamma x_T$ (`consequence.expansion_factor()` at
[`consequence.py:116`](../../backend/consequence.py#L116) already implements exactly this and is
simply not wired into the valve models).

---

### D-3 — A vent valve that multiplies its inlet composition vector
**File / line:** [`backend/core/valve.py:47-50`](../../backend/core/valve.py#L47)

```python
comp = {k: offgas_comp.get(k, 0.0) * valve * pass_frac for k in MW_COMP}
```

**Heuristic:** the valve scales every species of the incoming stream by a dimensionless factor. When
`valve < 1` the missing moles are **destroyed** — they do not accumulate upstream, they do not appear
downstream. When `valve > 1` (possible: `_eq_pct` × √ΔP-ratio is unbounded above) they are **created**.
A valve is not a unit operation that changes flow; it is a resistance that a *node pressure balance*
resolves.

**Required replacement:** solve the network. $\dot m$ from D-1/D-2, and whatever the valve cannot
pass raises the upstream node via the vapour-space ODE of A-6.

---

### D-4 — Isenthalpic letdown replaced by a constant Joule–Thomson coefficient
**File / line:** [`backend/core/valve.py:52`](../../backend/core/valve.py#L52),
[`main.py:4207`](../../backend/main.py#L4207)

```python
T_out = T_in - SCRUB_HV604_MU_JT * dP
```

**Heuristic:** a constant μ_JT across a 136 bar letdown of a reacting NH₃/CO₂ mixture. The real
process is carbamate dissociation plus flash — strongly endothermic and composition-dependent — and
$\mu_{JT}=(\partial T/\partial P)_h$ varies by an order of magnitude over this range.

**Required replacement:** PH flash. Hold $h(T_1,P_1,\mathbf z)=h(T_2,P_2,\mathbf z)$ and solve for
$T_2$ and $\psi$ simultaneously with the VLE of B-1 — the same routine required at LV-322501,
LV-323501, LV-323505 and every other letdown in the flowsheet.

---

### D-5 — CO₂ compressor 322K001 has no thermodynamic model
**File / line:** [`backend/main.py:5566-5578`](../../backend/main.py#L5566)

```python
P_line_float = min(s.p_syn_bara + DP_HP_DES, P_line_ceil)
P_line_bara  = P_line_float - CO2_PV_DP_GAIN * pv_open
phi_HP  = min(1.0, (dP_HP / DP_HP_DES) ** 0.5)
g_HP    = dP_HP ** 0.5
g_vent  = (pv_open / 100.0) * CO2_VENT_COND * dP_vent ** 0.5
f_to_HP = g_HP / (g_HP + g_vent)
```

**Heuristic:** the machine's discharge pressure is *defined* as the loop pressure plus a fixed
3.5 bar. There is no speed, no inlet volumetric flow, no polytropic head, no efficiency, no surge
line and no stonewall. `g_HP = dP**0.5` is a bare $\sqrt{\text{bar}}$ used as a conductance —
dimensionally inconsistent with `g_vent`, which carries `CO2_VENT_COND`. On a branch named
`feat/322-1-compressor-speed-widget`, the compressor has no speed input in its own model.

**Required replacement:** a real machine map,

$$H_{poly}=\frac{Z_1RT_1}{M}\frac{n}{n-1}\left[\left(\frac{P_2}{P_1}\right)^{\frac{n-1}{n}}-1\right],\qquad
\frac{n-1}{n}=\frac{\kappa-1}{\kappa\,\eta_p}$$

$$H=f\!\left(\frac{Q_{in}}{N},N\right),\qquad
P_{surge}(N)\le P_2\le P_{stonewall}(N),\qquad
W=\frac{\dot m H_{poly}}{\eta_p\eta_m}$$

with the branch split resolved by a **pressure-node network solve** (Newton on
$\sum\dot m_j(\mathbf P)=0$ at each node), not by a normalised conductance ratio.

---

### D-6 — Ejector 322F001 as a fabricated stall polynomial
**File / line:** [`backend/main.py:2571-2574`](../../backend/main.py#L2571)

```python
phi_sp   = EJ_SPINDLE_R ** ((EJ_OPEN_DES - open_eff) / 100.0)
f_stall  = clamp((phi_m - EJ_STALL_PHI) / (EJ_STALL_REC - EJ_STALL_PHI), 0.0, 1.0) ** EJ_STALL_EXP
capacity = EJ_SUC_TOT_DES * phi_m * phi_sp * f_stall
```

**Heuristic:** the source calls this a *"Representative non-linear liquid-liquid jet-ejector
entrainment law"* — i.e. invented. `EJ_STALL_PHI = 0.20`, `EJ_STALL_REC = 0.35`, `EJ_STALL_EXP = 2`
are a fitted ramp with no source. Discharge pressure `EJ_P_DISCH_BARA` and density `EJ_RHO_DISCH`
are **constants**: the jet pump develops the same head regardless of motive rate. Entrained
composition is a frozen vector `EJ_CARB_FRAC` rather than the live 322E003 sump composition, so
species are not conserved across the unit. `ejector_huang.py` — a proper 1-D ejector model — exists
in the repo and is **never imported**.

**Required replacement:** the constant-area mixing model, i.e. continuity + momentum + energy across
nozzle, mixing chamber and diffuser:

$$\dot m_p u_p+\dot m_s u_s+ (P_p A_p+P_s A_s)=\dot m_m u_m+P_m A_m$$
$$\dot m_p\!\left(h_p+\tfrac{u_p^2}{2}\right)+\dot m_s\!\left(h_s+\tfrac{u_s^2}{2}\right)
=\dot m_m\!\left(h_m+\tfrac{u_m^2}{2}\right)$$
$$P_d=P_m+\eta_d\,\tfrac{1}{2}\rho_m u_m^2,\qquad
\mu=\frac{\dot m_s}{\dot m_p}=f\!\left(\frac{P_d-P_s}{P_p-P_d},\,\frac{A_t}{A_m},\,\eta_n,\eta_m,\eta_d\right)$$

Wire `ejector_huang.py` in, drive $A_t$ from the HV-322602 spindle position, and carry the live sump
composition.

---

### D-7 — Darcy–Weisbach present only as a design-normalised ratio
**File / line:** [`backend/main.py:5751`](../../backend/main.py#L5751),
[`main.py:5892-5905`](../../backend/main.py#L5892)

```python
dP_strip_live = dP_des_strip * (RHO_DES_LIVE / rho_live_strip) * (m_live / m_des)**2
```

**Heuristic:** the $\dot m^2/\rho$ scaling is correct in form, but there is no friction factor, no
Reynolds number, no L/D and no fitting losses — $f$ is frozen at its design value inside
`dP_des_strip`. Across a turndown to 50 % load, $Re$ falls by half and $f$ rises measurably; in the
laminar/transition regime the model is qualitatively wrong. A search for `colebrook`, `reynolds`,
`friction_factor`, `moody` or `ergun` across the engine returns **zero** hits.

**Required replacement:**

$$\Delta P=f\frac{L}{D}\frac{\rho u^2}{2}+\sum K_i\frac{\rho u^2}{2}+\rho g\Delta z,\qquad
\frac{1}{\sqrt f}=-2\log_{10}\!\left(\frac{\varepsilon/D}{3.7}+\frac{2.51}{Re\sqrt f}\right)$$

with $Re=\rho u D/\mu$ from the live viscosity (`core/thermo.py` already supplies
`viscosity_liq_pas`, used at [`main.py:5518`](../../backend/main.py#L5518) and then discarded).

---

### D-8 — Arbitrary transport-delay queues used in place of hydraulics
**File / line:** [`backend/main.py:5805`](../../backend/main.py#L5805),
[`main.py:5586`](../../backend/main.py#L5586)

```python
delayed_bot_kgh = _delay(s.tlag, "322E001_BOT_KGH_LAG", strip["bot_kgh"], 60.0, dt)
...
F_CO2_syn_th = _delay(s.tlag, "FEED_CO2", s.F_CO2_th, FEED_TD_S, dt)   # "Empirical BL->loop transport dead time"
```

**Heuristic:** a flat 60 s FIFO on the stripper bottoms flow, and a fixed `FEED_TD_S = 345 s` on the
CO₂ feed, both labelled empirical. These do not scale with flow, so a turndown to 50 % load leaves
the transit time unchanged when it should double.

**Required replacement:** dead time must be a state of the line inventory. The repo does this
correctly for the 323/324 product train — `consequence.transport_time_s()` at
[`consequence.py:545`](../../backend/consequence.py#L545) computes $t_d=\rho V/\dot m$ — and the same
treatment should replace both fixed delays:

$$t_d=\frac{\rho\,V_{line}}{\dot m},\qquad V_{line}=\frac{\pi D^2}{4}L$$

with $D$ from the datasheets. Where an inventory genuinely exists (the sump), model it as a holdup
ODE, not as a delay line.

---

### D-9 — PSV relief as a linear over-pressure ramp
**File / line:** [`backend/main.py:7941`](../../backend/main.py#L7941); constants at
[`main.py:3587-3588`](../../backend/main.py#L3587)

```python
SYN_PSV_CAP_KGH = 200_000.0
m_psv_kgh = SYN_PSV_CAP_KGH * min(psv_over / SYN_PSV_ACCUM_BAR, 1.0)
```

**Heuristic:** SV-32201 relieves linearly from 0 to 200 t/h over 16.1 bar of accumulation. A real
spring PSV pops, then flows choked — capacity is nearly independent of over-pressure above the set
point.

**Required replacement:** API 520 Part I,

$$W=\frac{C\,K_d\,K_b\,K_c\,A\,P_1}{\sqrt{T Z/M}},\qquad
C=520\sqrt{\kappa\!\left(\frac{2}{\kappa+1}\right)^{\frac{\kappa+1}{\kappa-1}}}$$

with $A$ the actual orifice area (the comment says DN 100) and a pop/blowdown hysteresis on the lift
state.

---

### D-10 to D-22 — further hydraulic violations (summary)

| # | File:line | Heuristic | Required |
|---|---|---|---|
| D-10 | [`main.py:6988`](../../backend/main.py#L6988) | 328C004 overhead $\propto\sqrt{\Delta P/\Delta P_{des}}$, compressible service | ISA-75.01 gas (D-2) |
| D-11 | [`main.py:6756`](../../backend/main.py#L6756) | `m_341 = VENT_DES · gas/gas_des` — fixed vent split fraction | Node pressure balance across the vent line |
| D-12 | [`main.py:6555`](../../backend/main.py#L6555) | `pull_f010 = MEVAP_DES · (P/P_des)` — ejector pull linear in suction P | Ejector suction curve $\dot m_s(P_s)$ from D-6 |
| D-13 | [`steam_system.py:62`](../../backend/steam_system.py#L62) | `K_902` back-sized so 50 % stroke passes design draw | $C_v$ from the valve datasheet |
| D-14 | [`steam_system.py:77-78`](../../backend/steam_system.py#L77) | `C_MP = C_LP = 25.0` — *"lumped, calibrated"*, identical for two different headers | $C=V_{hdr}\,\partial\rho/\partial P|_{T,sat}$ from IF-97 |
| D-15 | [`steam_system.py:83`](../../backend/steam_system.py#L83) | `C_9 = 8.16·0.2174·30.0` — a derived capacitance times a 30× fudge | Remove `F_lump`; use the real header volume |
| D-16 | [`steam_system.py:228`](../../backend/steam_system.py#L228) | `m_valve = m_des · (op / LV_OPEN_DES)` on every drum level valve | ISA-75.01 liquid (D-1) |
| D-17 | [`main.py:4615`](../../backend/main.py#L4615) | PD pump $Q=NV\eta_v$ with $\eta_v$ constant — no slip vs. ΔP | $\eta_v=1-\frac{\Delta P}{\beta}-\frac{c_{slip}\Delta P}{\mu N}$ |
| D-18 | [`main.py:4624`](../../backend/main.py#L4624) | `pump_current_A` linear in rpm, *"display proxy"* | $I=\frac{P_{shaft}/\eta_m}{\sqrt3 V\cos\phi}$ with a no-load offset |
| D-19 | [`main.py:6215`](../../backend/main.py#L6215) | `if level <= 0: suction = min(suction, inflow)` — non-physical empty-vessel guard | Emerges from $\sqrt{h}$ discharge: $h\to0\Rightarrow\dot m\to0$ |
| D-20 | [`main.py:5809-5810`](../../backend/main.py#L5809) | same empty-sump guard on the stripper drain | as D-19 |
| D-21 | [`main.py:6100-6101`](../../backend/main.py#L6100) | same guard on the HPCC level | as D-19 |
| D-22 | [`main.py:3139`](../../backend/main.py#L3139) | `clamp(f, 0.0, 0.999)` — split fraction hard-limited to keep it physical | A converged flash cannot exceed 1 by construction |

**Note on D-19 to D-21:** these are the `if flow < 0: flow = 0` family named in the brief. They are
each a symptom of A-4/A-12/D-1: with a hydrostatic-head discharge law the flow goes to zero at zero
head automatically, and the guard becomes unreachable.

---

## E. Fabricated Consequence Gains and Synthetic Instrument Signals

These do not fall under the four named criteria but are the same defect class — scripted
consequences wired directly to published tags.

### E-1 — Deterministic two-sine "process noise" generator
**File / line:** [`backend/main.py:6237-6240`](../../backend/main.py#L6237); constants at
[`main.py:3593-3600`](../../backend/main.py#L3593)

```python
SCRUB_SWELL_PCT_MAX   = 18.0
SCRUB_SWELL_NOISE_PCT = 2.0
_void_frac = 1.0 - scrub["cool_frac"]
scrub_swell_pct = SCRUB_SWELL_PCT_MAX * _void_frac
scrub_swell_noise = SCRUB_SWELL_NOISE_PCT * _void_frac * (
    math.sin(2*pi*s.sim_t/SCRUB_SWELL_NOISE_T1_S) + 0.6*math.sin(2*pi*s.sim_t/SCRUB_SWELL_NOISE_T2_S)) / 1.6
```

**Heuristic:** LT-329501's two-phase level swell is `18 % × (1 − cool_frac)` and its instability is
**two hardcoded sine waves at 17 s and 7.3 s**. The void fraction is set equal to a condensation
capacity ratio — a quantity with no relation to void.

**Required replacement:** drift-flux void and a real DP reading,

$$\alpha=\frac{j_g}{C_0(j_g+j_l)+u_{gj}},\qquad
u_{gj}=1.53\!\left[\frac{\sigma g(\rho_l-\rho_g)}{\rho_l^2}\right]^{1/4}$$
$$\rho_{mix}=(1-\alpha)\rho_l+\alpha\rho_g,\qquad
\Delta P_{cell}=\rho_{mix}\,g\,h_{col}$$

with $j_g$ from the actual boil-off rate. Instrument noise, if wanted, belongs in a transmitter
model, not in the process state.

### E-2 to E-12 — remaining fabricated gains (summary)

| # | File:line | Constant | Heuristic |
|---|---|---|---|
| E-2 | [`main.py:3462`](../../backend/main.py#L3462) | `SCRUB_CARB_ABS_GAIN = 0.15` | kmol CO₂ scrubbed per kmol surplus wash — a mass-transfer rate replaced by a scalar |
| E-3 | [`main.py:3670`](../../backend/main.py#L3670) | `SCRUB_COND_SPINDLE_GAIN = 0.25` | condenser duty scaled by ejector spindle position |
| E-4 | [`main.py:3555-3556`](../../backend/main.py#L3555) | `SYN_P_DEFICIT_GAIN = SYN_P_VENT_GAIN = 0.30`, both marked `-- calib` | pressure lift per unit condensation/vent deficit |
| E-5 | [`main.py:3626`](../../backend/main.py#L3626) | `SYN_P_PHASE_GAIN = 0.90203` | fictitious mass injected into the loop inventory as a phase-shift proxy ([`main.py:7932`](../../backend/main.py#L7932)) |
| E-6 | [`main.py:665`](../../backend/main.py#L665) | `STRIP_SLIP_GAIN = 4.0` | volatile breakthrough per unit composition "slip" |
| E-7 | [`main.py:3326`](../../backend/main.py#L3326) | `REACT_NC_LOOP_GAIN = 0.50` | maps fresh-feed N/C onto reactor-feed N/C |
| E-8 | [`main.py:3425`](../../backend/main.py#L3425) | `REACT_NC_OVERFLOW_GAIN = 0.5` | NH₃ repartitioned overflow↔off-gas per unit N/C deviation |
| E-9 | [`main.py:3434`](../../backend/main.py#L3434), [`3439`](../../backend/main.py#L3439) | `REACT_FWD_GAIN = 1.0`, `REACT_FWD_TAU_MIN = 8.0` | a **high-pass-filtered fictitious mass pulse** injected into the reactor holdup ([`main.py:6039`](../../backend/main.py#L6039)) so LT-322504 responds to HV-322602; the source admits the sustained part "would INVENT mass" |
| E-10 | [`main.py:3432`](../../backend/main.py#L3432) | `REACT_FRESH_FRAC = 0.30` | fabricated prompt/lagged split of the reactor inflow |
| E-11 | [`main.py:3530`](../../backend/main.py#L3530) | `TIC_329005_LOAD_GAIN = 10.0` | °C of CCW load offset per unit load deviation |
| E-12 | [`consequence.py:192-194`](../../backend/consequence.py#L192) | `E_DES_DEFAULT = 0.004`, `E_EXPONENT = 3.2`, `E_CAP = 0.60`, `E_TRIGGER_MULT = 2.0` | entrainment power law anchored to design; should be Souders–Brown / Ishii–Mishima on live $\rho_v$, $\rho_l$, $\sigma$ and the actual disengagement height |

---

## F. Dead rigorous code

Three physically correct modules exist in the repository and are **not wired into the engine**:

| Module | Lines | Status |
|---|---|---|
| [`backend/vle_nh3co2h2o.py`](../../backend/vle_nh3co2h2o.py) | 315 | never imported by `main.py` |
| [`backend/ejector_huang.py`](../../backend/ejector_huang.py) | 169 | never imported by `main.py` |
| [`backend/core/lp.py`](../../backend/core/lp.py), [`backend/core/mp.py`](../../backend/core/mp.py) | 888 | never imported anywhere; the live 323/328 logic is duplicated inline in `main.py` |

`consequence.expansion_factor()` ([`consequence.py:116`](../../backend/consequence.py#L116)) —
a correct ISA-75.01 compressible expansion factor — is defined but never called by any valve model.
`iapws_if97.py` is used for saturation temperature only, not for the header capacitances of D-14.

> **Status 2026-09-15.** `vle_nh3co2h2o.py` is **live** through `thermo_service.py` (Phases 1 and 5).
> Every valve model uses `hydraulics.expansion_factor` (Phase 2); the `consequence.py` copy is now a
> duplicate called only inside its own module. `iapws_if97` also supplies the chest latent heat
> (A-5). Still dead: `ejector_huang.py` (D-6 used `jet_pump.py`, and D-12 is its intended site),
> `core/lp.py` and `core/mp.py` (`mp.py` also still calls the retired two-argument
> `steam_chest_pressure`), and `core.thermo.EmpiricalThermo` (imported at
> [main.py:50](../../backend/main.py#L50), no caller). **New finding:** the `_sm_flowsheet` block is
> built **twice** ([main.py:6819](../../backend/main.py#L6819) and
> [main.py:6896](../../backend/main.py#L6896)). Of its seven unit objects only `_valve_unit.solve()`
> ([main.py:7843](../../backend/main.py#L7843)) is ever stepped; the other six are constructed and
> never solved, so "Sequential Modular" describes one valve.

**The dead `core/lp.py` and `core/mp.py` are a maintenance hazard**: they are near-identical copies of
live code (e.g. `core/mp.py:142` mirrors `main.py:6488`) and will silently diverge.

---

## G. What is genuinely first-principles

For balance, the following are correct and should be the template for the remediation:

| Item | File:line | Why it is right |
|---|---|---|
| 328C003 urea hydrolysis | [`main.py:2434-2467`](../../backend/main.py#L2434) | Genuine Arrhenius $\ln k=21.8-11100/T$, true second-order PFR integral, live concentrations |
| 323C003 gas-node coupling | [`c003_pressure_coupling.py:47`](../../backend/c003_pressure_coupling.py#L47) | Compressible line law $Q=C\sqrt{P_1^2-P_2^2}$ |
| 323C003/F004/F010 stage energy balances | [`main.py:6397`](../../backend/main.py#L6397), [`6481`](../../backend/main.py#L6481) | Real $M c_p\,dT/dt = \Sigma\dot m c_p\Delta T - \dot m_{vap}\lambda$ with live holdup |
| Transport dead time (323/324 train) | [`consequence.py:545`](../../backend/consequence.py#L545) | $t_d=\rho V/\dot m$, flow-dependent, derived from nozzle bore |
| Steam header mass balance topology | [`steam_system.py:417-432`](../../backend/steam_system.py#L417) | Correct node structure — only the capacitances are fudged (D-14/D-15) |
| Reactor mass holdup | [`main.py:6037-6060`](../../backend/main.py#L6037) | A true conserved $dM/dt$ with $L=M/(\rho A)$ — spoiled only by `k_loop_fill` (A-3) and the fictitious pulse (E-9) |
| Reactor stoichiometry | [`main.py:3943-3956`](../../backend/main.py#L3943) | Exact atom conservation on both reactions |
| IAPWS-IF97 | [`iapws_if97.py`](../../backend/iapws_if97.py) | Correct implementation |

---

## H. Prioritised remediation plan

> **Status 2026-09-15.** Phases 1–4 below have largely landed (see §0a for per-finding detail).
> Phase 5's first cleanup item, `SYN_LOOP_RESID_DES_KGH`, **must not** be deleted on its own: it
> mirrors `REACT_TEAR_DES`, and removing it alone produces a measured −1.45 bar/h PT-329201 bleed. The
> next productive items are the A-2 closure order in §0a, A-11 for 323C003/F004 (the rigorous
> `bubble_t` is already wired for F010), D-1's `_fic_flow`, and the dead code in §F.

The findings are heavily coupled: fixing thermodynamics first makes several other fixes fall out
automatically. Recommended order:

**Phase 1 — Thermodynamic foundation (unblocks B-1…B-14, D-4, A-11)**
1. Wire `thermo_extended_uniquac` + `vle_nh3co2h2o` into a single `flash(T,P,z)` / `flash_PH(h,P,z)` /
   `bubble_T(P,x)` / `dew_T(P,y)` service.
2. Replace `_hpcc_flash_split`, `REACT_THETA_OG`, `STRIP_FRAC_DES`, `sol_vapour_y`,
   `SCRUB_OFFGAS_KMOLH_DES` and the vacuum-condenser `h_eff_kjkg` with calls to it.
3. Delete every `if (at design) return design` short circuit (A-15) and re-validate the design point
   as a *converged* result.

**Phase 2 — Hydraulic network (unblocks A-1, A-4…A-7, D-1…D-3, D-19…D-21)**
4. Build a node-pressure solver: every vessel vapour space gets $dM_v/dt$ + EOS; every connection
   gets an ISA-75.01 valve or a Darcy line.
5. Populate $C_v$/$K_{vs}$, trim characteristic, $F_L$ and $x_T$ from `References/Datasheets`.
6. Delete `steam_chest_pressure`, all `*_P_KP` capacitances and all `m_des × (op/op_des)` flows.

**Phase 3 — Kinetics and reaction energy (unblocks C-1…C-6, A-8, A-9)**
7. Implement carbamate + dehydration rate laws; integrate over the reactor axial profile.
8. Replace the prescribed `REACT_DT_COL_DES` profile with node energy balances carrying
   $(-\Delta H_r)r V$.
9. Replace `xi_hyd = ξ_des·η` and `xi_biu = ξ_des·s` with rate integrals.

**Phase 4 — Machines and relief (D-5, D-6, D-9)**
10. Compressor polytropic map with surge/stonewall; ejector momentum model from `ejector_huang.py`;
    API 520 PSV.

**Phase 5 — Cleanup**
11. Delete `SYN_LOOP_RESID_DES_KGH`, `k_loop_fill`, `m_phase_shift`, `m_fwd_carb_kgh` and every
    `*_GAIN` in section E once the underlying physics supplies the effect.
12. Delete `core/lp.py`, `core/mp.py`, `main*.bak`/`main_*.py` snapshots.
13. Re-run `backend/tests/run_full_audit.py` — expect the design-point "bit-exact" assertions to
    become tolerance-based, which is the correct behaviour for a converged model.

**Validation gate for each phase:** the design point must reproduce the PFD within measurement
tolerance *without* any anchoring term, and the conservation harness
(`gap_g4_conservation_harness.py`) must close $\sum\dot m$, $\sum\dot n_i$ and $\sum\dot m h$ to
$<10^{-6}$ relative at every unit — including the synthesis loop, which currently cannot close
because of A-2.
