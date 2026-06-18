# Valve × Indicator Sensitivity Audit — Section 322 / 329 OTS

**Harness:** `backend/tests/run_valve_indicator_matrix.py` → `backend/tests/_matrix_out.txt`
**Method:** each operator-manipulable valve forced LO→HI, settled 20 min/pt (DT=0.1 s, 12 000 ticks), every numeric leaf of the `step_sim` packet flattened (694 leaves) and diffed. FLAT ≡ `|hi−lo|/(|base|+1e-9) ≤ 1e-4`.
**Discipline:** this is an AUDIT. Root cause is established for every stall below; **no fixes are applied** (Iron Law — fixes await go-ahead).

---

## 1. Per-valve responsiveness (every valve is LIVE)

| Valve | Driver | LO→HI | Indicators moved / 694 |
|---|---|---:|---:|
| PV-322203 CO2 (PIC op) | `PIC_322203` MAN | 0→40 | 258 |
| PV-322203 CO2 vent | `HIC_322203` | 0→30 | 256 |
| MP steam supply | `valve_supply_pct` | 30→70 | 197 |
| HV-322605 reactor-overflow | `HIC_322605` | 30→90 | 179 |
| HV-322602 ejector spindle | `HIC_322602` | 55→95 | 174 |
| MP→LP letdown | `valve_letdown_pct` | 30→70 | 141 |
| FV-329409 CCW circ flow | `FIC_329409` MAN | 30→90 | 36 |
| HV-322604 scrubber off-gas vent | `HIC_322604` | 25→80 | 28 |
| TV-329005 CCW supply-T | `TIC_329005` MAN | 20→80 | 28 |
| LV-322501 stripper drain | `LIC_322501` MAN | 50→100 | 5 |

No fully-dead valve. Low movers (LV-322501=5) are physically narrow (drain affects only the stripper-sump level chain), not stalled.

## 2. STALL CHECK — physics-expected couplings (10 probed)

| Valve → Indicator | Result | Δ (lo→hi) | Verdict |
|---|---|---|---|
| **HV-322604 → SCRUB_322E003.TT_322011** | **FLAT** | 0 | **TRUE STALL (bug)** |
| **HV-322604 → SCRUB_322E003.off_th** | **FLAT** | 0 | **TRUE STALL (bug)** |
| HV-322605 → REACT_322R001.LT_322504 | FLAT | 0 | Defensible (weir self-regulation) |
| LV-322501 → STRIP_322E001.LI_322501 | OK | −100 (rel 2.0) | pass |
| FV-329409 → SCRUB_322E003.ccw.TT_329125 | OK | −19.46 | pass |
| FV-329409 → SCRUB_322E003.TT_322002 | OK | −8.8 | pass |
| TV-329005 → SCRUB_322E003.ccw.TT_329125 | OK | −17.57 | pass |
| HV-322602 → EJ_322F001.suction_kgh | OK | −1.05e4 | pass |
| MP steam → STRIP_322E001.TT_322004 | OK | +185.7 | pass |
| MP→LP → HPCC_322E002.TT_322010 | OK | +169.5 | pass |

7 OK, 3 FLAT → 2 true dead-input bugs + 1 defensible reduced-model pin.

---

## 3. Root-cause classification

### STALL #1 + #2 — HV-322604 → TT-322011 and → off_th  (TRUE BUG; user's reported stall)

One root cause produces both. In `scrub_322e003()` the scrubber-top off-gas state is decoupled from the vent valve opening $\theta_{HIC604}$:

- **off_th** — off-gas mass leaving 322E003 is pinned to the design split × throughput, with no $\theta$ term ([main.py:889](backend/main.py:889)):

$$\dot n_{offgas,i} = \mathrm{SCRUB\_OFFGAS\_KMOLH\_DES}_i \cdot s \qquad \Rightarrow\quad \dot m_{off,th}=\sum_i \dot n_{offgas,i}\,M_i \;\;\perp\;\; \theta_{HIC604}$$

- **TT-322011** — scrubber-top off-gas temperature is keyed only to the loop N/C slip (AT-322701), again with no $\theta$ term ([main.py:932](backend/main.py:932)):

$$T^{TT\text{-}322011}_{offgas} = \mathrm{clip}\!\Big(\underbrace{\mathrm{SCRUB\_OFFGAS\_T\_C}}_{114.0} + \underbrace{\mathrm{SCRUB\_OFFGAS\_T\_GAIN}}_{120.0}\,(\mathrm{nc}_{act}-\mathrm{nc}_{des}),\; t_{ccw,in},\; T_{proc}\Big)$$

$\theta_{HIC604}$ enters the model **only downstream** of the scrubber top, in `hv_322604()` ([main.py:945-961](backend/main.py:945)):

$$\dot m_{og}=\dot m_{og,des}\,s\,\frac{\theta}{\theta_{des}}\sqrt{\frac{\max(P_{up}-P_{down},0)}{\Delta P_{des}}},\qquad T_{out}=T_{in}-\mu_{JT}\,\Delta P\quad(\mu_{JT}=0.55,\ \theta_{des}=50\%)$$

So the valve **is** live to the *post-valve* leaves (`og_lp_th` +1.06 rel, `TT_322011_lp` +13.9 °C JT, `vent_frac`, `PI_329201`/`P_offgas` −25.4 bar PT cascade, CCW duty/`rho_cond`, `LT_329501`, `TT_322002` −6.2, `ccw.TT_329125` −0.94 — the 28-leaf RESPONDS list). What is missing is the **back-influence of vent demand on the scrubber-top split and energy balance**: opening HV-322604 pulls more off-gas (more NH₃/inert purge) off 322E003, which must (a) raise `off_th` and (b) shift `TT-322011`. The pinned split + N/C-only temperature key sever exactly that path — matching the operator report verbatim: *"opening HV-322604 has no effect on the HP scrubber off-gas stream temperature although it allows more NH₃ to escape through this stream."*

**Fix pattern already exists in this same function** ([main.py:891-905](backend/main.py:891)): the carbamate-recycle deviation injection (`carb_dev`, identically 0 at design ⇒ bit-exact HMB preserved). A $\theta$-keyed deviation on the off-gas split and on the TT-322011 driver, zeroed at $\theta=\theta_{des}$, restores the coupling without disturbing the design heat-and-mass balance. **Not applied — awaiting go-ahead.**

### STALL #3 — HV-322605 → LT-322504  (DEFENSIBLE; not a code defect)

Reactor level is a **conserved-holdup state regulated by a gravity weir**, explicitly modeled open-loop w.r.t. the overflow valve ([main.py:1046-1047](backend/main.py:1046)):

$$\frac{dV}{dt}=Q_{in}-Q_{out}(\phi),\qquad \mathrm{level}=\frac{m_{liq}}{\rho(T)\,A},\qquad Q_{out}=f(\text{head}-\text{crest})\ \ \text{(weir, not valve)}$$

HIC-322605 routes the overflow **split/composition** (`overflow_kmolh`, AT-322701) but the weir crest sets the outflow, so at steady state holdup returns to design NLL and `LT_322504` reads 80 % regardless of $\theta_{HIC605}$ ([main.py:1386-1392](backend/main.py:1386)). FLAT-at-steady-state is correct weir physics. **Flag only as an operator-intuition gap** (operators expect an overflow valve to move level); reclassify to a bug only if the plant intent is a throttling level valve rather than a weir.

---

## 4. DEAD-INDICATOR sweep (context)

406 / 694 leaves move under no valve. Spot-checked: dominated by (a) **Section 321 ammonia-feed constants** (`CO2_FEED.*`, `FI_321401`, `LI_321501`, `PI_32120x`, `PDY_32120x` — 321 is a fixed upstream boundary), (b) **zero-pinned trace species** (`*_pct.{Biuret,H2,O2,CH4}=0`), (c) **display/alarm margins**. `REACT_322R001.LT_322504 = 80` appears here, consistent with STALL #3. No additional surprise dead inputs in the synthesis loop beyond the off-gas pair.

---

## 5. Verdict

| # | Coupling | Class | Location |
|---|---|---|---|
| 1 | HV-322604 → TT-322011 | **True dead-input bug** | [main.py:932](backend/main.py:932) |
| 2 | HV-322604 → off_th | **True dead-input bug** (same root) | [main.py:889](backend/main.py:889) |
| 3 | HV-322605 → LT-322504 | Defensible weir self-regulation | [main.py:1046](backend/main.py:1046) |

The user's lead example is confirmed and generalized: it is **two** stalled leaves driven by one decoupling (pinned off-gas split + N/C-only top-temperature). All other physics-expected valve couplings pass. Remediation direction (deviation-injection, mirroring the in-file carbamate fix) is identified but **not implemented pending approval**.
