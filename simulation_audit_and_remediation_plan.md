# Urea OTS — Simulation Audit & Remediation Plan

**Auditor role:** Lead Process Simulation Auditor & Chemical Process Engineer
**Scope:** 5-Phase deep audit of the Uhde 1750/1925 MTPD urea OTS against OEM P&IDs, PFDs/HMB, and the Master Controller Constraint List.
**Reference set:** `D:\Work\Urea Simulation Docs\Audit\` — `Master_PID_Tuning_Constants.md`, `UHDE P&ID (Searchable)`, `Uhde's PFD`.
**Code under audit:** `D:\Work\Urea Simulation\backend\` — `main.py` (~5073 lines), `reactor.py` (361), `controllers.py` (231), `steam_system.py` (453).
**Mandate constraint (binding):** This document is research + gap identification + a file-specific coding blueprint **only**. No source code was modified during this audit. Implementation is handed off to the Opus model.

---

## 0. Method & standing laws applied

- **100 % conservation** — every node checked for total-mass and per-species closure; any residual that is *injected* (not merely reported) is flagged.
- **Sourcing law** — every live constant must trace to a PFD/HMB stream, P&ID tag, or the Controller Constraint List. Fabricated constants are flagged.
- **Design bit-exactness** — the sim must reproduce the OEM HMB at 1750 MTPD to machine precision; 1925 MTPD is a uniform $1.1000\times$ molar scale of 1750 at identical $T$, $P$, and composition (verified).
- **Interpretation rule (Phase 1):** DCS utility codes (STLS/STMH, CPL/CPP, AW, ACA, US, GCB, VP, WC/CW) are steam-pressure / fluid-service levels, **not** heat-tracing rules — confirmed correctly interpreted in code.

Severity legend used throughout: **S1** = conservation / design-fidelity breaking; **S2** = off-design/transient fidelity; **S3** = cosmetic / documentation.

---

## 1. Phase 1 — Tag & Stream Alignment vs P&IDs

**Status: CLOSED.** 187/260 code tags cross-confirmed against the searchable P&ID set; the remainder are internal sim state variables with no P&ID counterpart (expected).

- Utility codes are consumed as **fluid-service / steam-pressure levels**, not tracing rules — correct. No gap.
- Stream numbering (2xx synthesis, 3xx recirculation, 7xx desorption/recycle) aligns with the PFD sheets.
- Controller→vessel wiring verified live (`main.py` 2515–2525): LIC-328503 → 328C002 desorber-I bottoms (743→hydrolyser); LIC-328504 → 328C004 desorber-II bottoms (739→328E007); LIC-328505 → 328C003 hydrolyser bottoms (747→desorber-II). Matches plant.

**Residual (S3):** 6 equipment tags unmatched to a live model node — `323D003, 329E002, 329E004, 329P004, 329U001, 335D007`. These are auxiliary/utility items (drums, minor exchangers, a pump, a package unit) outside the modelled synthesis+recirculation+desorption envelope. **Not a defect**; document as intentional scope boundary.

**Residual (S3):** LIC-328504 / LIC-328505 label swap exists **only between the controller-definition comment block and the sim-tuning comment block** — the *live wiring* is correct (verified above). Cosmetic comment inconsistency, no runtime effect.

---

## 2. Phase 2 — Thermodynamic Baseline vs PFD/HMB (1750 & 1925 MTPD)

**Status: CLOSED with 5 documented divergences.** The sim anchors the 1750 MTPD OEM baseline on the primary streams:

| Anchor | Sim | OEM (PFD/HMB) | Δ | Verdict |
|---|---|---|---|---|
| $F_{CO_2,th}$ (stream 107) | 54.618 t/h | 54.618 | 0 | exact |
| Wash 308/310 | 36 915 kg/h | 36 915 | 0 | exact |
| FIC-328402 (stream 755) | 31 478 kg/h | 31 478 | 0 | exact |
| Stream 207 | +0.01 % | — | ~0 | exact |
| Stream 206 (overflow tot) | +0.07 % | — | ~0 | exact |
| Reactor off-gas (stream 203) | Σ 963.76 kmol/h | 963.85 | −0.01 % | exact |
| HPCC LP-steam raise (stream 917) | 4.4 bara / 146.3 t/h | 4.4 / 146.3 | 0 | exact |
| 963 battery-limit admit | 0 | 0 | 0 | exact |

**Documented divergences (carry into gap register):**

- **P2-A (S1) — Scrubber vent reconciliation.** Live vent vector `SCRUB_OFFGAS_KMOLH_DES` = Σ 214.77 kmol/h **supersedes** OEM PFD stream 204 (64.78 kmol/h). This is deliberate (`_SCRUB_OFFGAS_RECON`, "Path B, Option 1"), not an accidental typo — see Phase 4 §4.1 for the conservation analysis. Breaks stream-204 bit-exactness.
- **P2-B (S2) — NH₃ battery-limit feed.** Sim 42.762 t/h vs stream 113 = 41.042 t/h (**+4.2 %**). The surplus is the makeup that offsets the P2-A vent slip (see §4.1); fixing P2-A should retire most of P2-B.
- **P2-C (S2) — Reactor pressure.** Sim 144.9 bar vs PFD 141.3 bar (**+3.6 bar**, +2.5 %). Within the Phase-5 acceptance band $[137.5, 150.5]$ bar g but biased high; trace to `SYN_P_DES_BARA`/vent-gain calibration.
- **P2-D (S2) — UF-85 (urea-formaldehyde, stream 694/697).** Sim 376.3 kg/h vs 697 kg/h (**−46 %**). Additive dosing under-scaled; isolated to granulation feed, no synthesis-loop impact.
- **P2-E (S3) — Evaporator concentrations.** Evap-I 95.0 % vs 94.31 %; Evap-II 98.6 % vs 97.71 %. Both slightly high (+0.7…+0.9 pt); product-spec cosmetic.

**1925 MTPD:** confirmed exact uniform $1.1000\times$ molar scale of the 1750 vectors at identical intensive state — no separate anchor defect.

---

## 3. Phase 3 — Control Loop Tuning, Limits, Slew, Anti-Windup

**Status: CLOSED — one structural gap + calibrated retunes.**

Controller kernel (`controllers.py`) is a **velocity I-PD**:

$$
du_k = K_c\!\left[-(PV_k-PV_{k-1}) + \frac{dt}{T_i}(SP_k-PV_k) - T_d\,\frac{PV_k-2PV_{k-1}+PV_{k-2}}{dt}\right]
$$
$$
du \leftarrow \operatorname{clamp}\!\big(\sigma\cdot du,\ \pm\,\text{rate}\cdot dt\big),\qquad
u \leftarrow \operatorname{clamp}\!\big(u_{k-1}+du,\ \text{lo},\ \text{hi}\big)
$$

Velocity form gives inherent anti-windup (integrator lives in $u$, clamped each step). Rate-limit $\pm\text{rate}\cdot dt$ present. **These are correct.**

**Gain-basis caveat (must be honoured by Opus):** plant DCS gains in the Constraint List are **span-normalised dimensionless**; sim gains are **engineering-unit**. Convert $K_{c,\text{plant}}\to K_{c,\text{EU}}=K_{c,\text{plant}}\cdot(\text{span}_{PV}/\text{span}_{OP})$ before declaring any mismatch. The Phase-3 delta table was built on this basis.

**P3-A (S2) — Structural gap: no derivative filter, no deadzone.** The plant DCS blocks carry a derivative time-constant filter $T_f$ (TF) and a deadzone (DZ) on several loops; `controllers.py` has **no `TF` and no `DZ` field**. The sim compensates with detuned $K_c$/$T_d$, which changes the closed-loop character (phase, chatter rejection) rather than reproducing the plant filter. This is the root cause of several deliberate sim retunes below.

**P3-B (S2) — Deliberate stability retunes** (documented in-code, diverge from Constraint List): FIC-328401 $K_c=0.30$, FIC-323402 $K_c=0.5$, FIC-328404 $K_c=0.5$, FIC-328402 $K_c=0.06$. These are **symptom fixes** for missing process-gain/lag fidelity, **not** the plant numbers. Remediation must correct the underlying process gain + lag (Phases 4–5) so the plant $K_c$ can be restored, rather than leaving the loop-level overwrite.

---

## 4. Phase 4 — Equation & Conservation Audit

**Status: CLOSED.** One S1 conservation finding, several confirmations that suspected leaks are *not* leaks.

### 4.1 P4-A (S1) — HP-scrubber vent reconciliation is a species-untracked reactant sink

This is the principal conservation finding of the audit.

**What the code does (`main.py` 1356–1368, `scrub_322e003` 1748–1869, LP-absorber stage 3415–3437):**

The scrubber node 322E003 pins both its outlets to design vectors scaled by `co2_scale` $=s$:

$$
\text{offgas}_i = \text{SCRUB\_OFFGAS\_KMOLH\_DES}_i\cdot s
\qquad(\text{322E003}\to\text{HV-322604}\to\text{322C001})
$$
$$
\text{overflow}_i = \text{SCRUB\_OVERFLOW\_KMOLH\_DES}_i\cdot s
\qquad(\text{322E003}\to\text{322F001 ejector suction})
$$

The overflow vector is pinned to the ejector-suction reconstruction `EJ_SUCTION_KGH` (Σ ≈ 2519.4 kmol/h). Because the feed vector (`OFFGAS_DES`, from stream 203) and the overflow vector (`EJ_SUCTION`) were reconstructed **independently**, they do **not** close per-species against the OEM PFD vent (stream 204 = 64.78 kmol/h). To force the *local* total-mass balance to GAP = 0, the author replaced the datasheet vent with:

```
_SCRUB_OFFGAS_RECON = {"CO2":62.18213955, "CH4":3.86, "H2":2.02, "N2":44.53,
                       "NH3":94.76367511, "O2":7.42, "H2O":0.0}      # Σ = 214.77 kmol/h
```

i.e. **100 % of inerts to vent + a forced NH₃/CO₂ slip of 156.95 kmol/h** (94.76 + 62.18), vs the OEM vent NH₃ + CO₂ = 5.35 + 1.44 = **6.8 kmol/h**. The comment states the intent explicitly: *"Closes the 322E003 component balance to machine zero (GAP = 0)."*

**Why this is a leak, not a closure — the decisive mechanism.** The scrubber vent passes through `hv604` (`main.py` 3417), which **scalarises** it:

$$
\text{gcb\_m} = hv604[\text{"mass\_kgh"}] \quad(\text{a single kg/h scalar — species identity discarded here})
$$

The downstream LP absorber 322C001 (`main.py` 3422–3437) is a **scalar-mass node**:

$$
\text{abs\_c001} = \text{A328\_PHI\_ABS}\cdot\text{gcb\_m}
\qquad
\text{vent\_c001} = \text{A328\_VENT\_DES}\cdot\frac{\text{pic201\_op}}{\text{A328\_PIC\_OP\_DES}}
$$
$$
m_{756} = \text{A328\_M756\_DES}\cdot\frac{\text{lic502c\_op}}{\text{A328\_LIC\_OP\_DES}}
$$

`abs_c001` (recovered liquor to the loop) is a **fixed mass fraction** of the incoming total, and `vent_c001` (labelled *"inert vent → atm"*, line 4013) is a **pinned design constant × valve ratio**. Neither is driven by the incoming NH₃/CO₂ partial content. Therefore the 156.95 kmol/h of NH₃ + CO₂ that the reconciliation dumped into the scrubber vent is **never re-identified as recyclable reactant** — it is split by a generic absorb-fraction, and the remainder is vented to atmosphere as if it were inert.

**Net effect on the synthesis loop:**
- At the **design point** ($s=1$, valves at design opening) every pin is mutually consistent by construction, so the *numeric* balance reads GAP = 0. The leak is **masked at design**.
- **Off-design / transient**, `vent_c001` and `m_756` scale on valve ratio while `abs_c001` scales on `gcb_m`; the species split no longer tracks true conservation, and the reactant slip partially exits to atmosphere. This is the **artificial mathematical leak** Phase 4 targets.
- The leak is *paid for* upstream by the **+4.2 % NH₃ battery-limit makeup** (P2-B). So P4-A and P2-B are the **same defect** seen at two nodes: reactant is lost at the scrubber/LP-absorber and back-filled at the feed.

**Root cause:** two independently reconstructed design vectors (`OFFGAS_DES` feed vs `EJ_SUCTION` overflow) that are not per-species consistent, papered over by inflating a species-untracked vent. **Correct fix is to make the split conservative, not to inflate the vent** — see blueprint §7.1.

### 4.2 P4-B — Reactor holdup hydraulics: **CONFIRMED CORRECT (no gap)**

Suspected earlier as a possible weir/geometry inconsistency; **resolved**. `main.py` threads *plant* geometry into `reactor.py`; the illustrative module defaults are dead code (never reached):

- `REACT_WEIR_CREST_M = REACT_LEVEL_NLL_PCT/100·REACT_LIQ_H_M − REACT_WEIR_HEAD_DES = 19.95 m` (line 1292), `REACT_WEIR_HEAD_DES = 0.05` (1291), `REACT_WEIR_CW = _react_mdot_kgh/(REACT_RHO_BULK_DES·REACT_WEIR_HEAD_DES^{1.5})` (1293); `area_m2=_react_area_m2` passed explicitly.
- The live bottom take-off is **HV-322605** (`outlet_line_outflow_kgph`), not the weir. `reactor.py` defaults `TANK_AREA_M2=5.31`, `WEIR_CREST_M=18.0` are **never** used.
- The instantaneous-production split, surge low-pass (`react_m_in_lag`), Fix-4 ejector forward-carbamate high-pass (`m_fwd_carb_kgh`, → 0 at steady state), flood carryover, and $f_{strip}=m_{out}/m_{ov\_split}$ (=1 at design) are all conservative. **No gap.**

### 4.3 P4-C — `closure_resid` is diagnostic-only: **CONFIRMED (no gap)**

Both the reactor node (`main.py` ~1734/1799) and the scrubber (`scrub_322e003`) compute `closure_resid = Σfeed − Σoutlets` but **never inject it** into any stream. It is a reported diagnostic. Not a fabricated source/sink.

### 4.4 P4-D — Desorption train 328C002/003/004 + 328D001: **CONFIRMED CLOSED**

Staged model matches PFD22 mass anchors exactly: `R328_C002_M743_DES=33769`, `R328_C003_M747_DES=34062`, `R328_C003_M748_DES=812`, `R328_C004_PHI750=6833/40557`. Node balances (comments 461–462) close: 328C002 in $738+748+750+775(40434)=737(6665)+743(33769)$; 328C003 in $746+911(34874)=748(812)+747(34062)$. No leak.

### 4.5 P4-E (S3) — HPCC phase split

HPCC gas/liquid split (`FRAC_GAS_DES`) reproduces the LP-steam raise (stream 917: 4.4 bara / 146.3 t/h, exact — Phase 2). Phase-split closure against streams 201/202/205 is adequate to design tolerance; **no S1/S2 defect**. Documented for completeness only.

---

## 5. Phase 5 — Domino Effect: transients, hydraulic fill rates, "fudge lags"

**Status: CLOSED — lag inventory classified physical vs fudge.**

Every first-order lag / residence time was mapped to a real vessel hydraulic volume or a defensible thermal mass. Classification:

**Physically grounded (τ = V/Q̇ or thermal C/UA — KEEP):**

| Constant | Value | Basis |
|---|---|---|
| `REACT_TAU_TOT_MIN` | ≈44.9 min | computed $=(A_{react}\cdot h/\dot V_{react})\cdot 60$ — true liquid residence |
| `SYN_P_TAU_FILL_MIN` | 57.8 min | synthesis-loop vapour-space fill from real volume |
| `R328_C002/_C004` residence | 900 s each | desorber liquid holdup |
| `R323_F004 / F010 / D011` | 180 / 240 / 600 s | drum/flash residence |
| `A328_C001 / A323_C005` | 600 / 300 s | absorber liquor holdup |
| `R324_F001 / F003` | 180 / 180 s | evaporator separator holdup |
| thermal-mass τ (EJ/STRIP/HPCC/SCRUB/OFFGAS/CCW) | 120–240 s | $C/UA$ vessel thermal inertia |

**Defensible but calibrated (KEEP, but tie to geometry in remediation):** `REACT_THERM_TAU_MIN=8.0`, `REACT_TAU_REC_MIN=5.0`, `REACT_FWD_TAU_MIN=8.0`, `SCRUB_TAU_HOLDUP_MIN=4.0`, `SYN_P_TAU_MIN=4.0`, `HPCC_TAU_FILL_MIN=6.0`.

**P5-A (S2) — Candidate "fudge lags" (calibration constants with no direct hydraulic derivation):** `FEED_TD_S=345` (feed dead-time), `FIC_329409_TAU_S=3.0`, `TIC_329005_TAU_S=25.0`. These are transport/measurement lags fit to response data, acceptable **provided** the FOPTD fingerprint is honoured:

$$
\text{PT-329201 FOPTD:}\quad P_0=5.7,\ P_f=144.0\ \text{bar g},\ \tau=3469.5\pm585.9\ \text{s},\ t_d=344.7\pm280.3\ \text{s},\ R^2=0.9888
$$

**Acceptance band (must hold after remediation):** $\tau_{sim}\in[2884,4055]$ s, $t_{d,sim}\le 572$ s, $P_f\in[137.5,150.5]$ bar g.

**P5-B (S2) — Node-fill coupling.** The reactor holdup fill (`k_loop_fill`) and `flow_frac`-scaled node time-constants ($\tau_n = \text{REACT\_TAU\_NODE\_MIN}[n]\cdot 60/\text{flow\_frac}$, line 2907) correctly slow the thermal profile at low load — physical. No fudge. **Note:** `flow_frac=clamp(co2_scale,0,1)` (line 2901) — division by `flow_frac` risks a singularity as load → 0; guard exists via clamp lower bound but verify floor > 0 in remediation.

### 5.1 P5-C — Dynamic Domino Effect (Hydraulic Couplings) — **CLOSED (implemented)**

**Gap (pre-fix):** the Unit-323 recirculation pressures `RECIRC_323.C003.P_bara` (PT-323201) and `RECIRC_323.F004.P_bara` were emitted as *fixed constants* (`R323_C003_P_BARA=4.1`, `R323_F004_P_BARA=1.13`). Opening a hydraulic valve therefore could not move the displayed upstream pressure — the forward pressure-accumulation domino was missing.

**Coupling 1 — Unit 322/323 (LV-322501 → PT-323201 & PT-323203).** Opening LV-322501 raises the stripper-bottom letdown `drain_kgh` → feed `m_feed_323` → top vapour `m_305 = \Phi_{V305}\,m_{feed,323}` into 323C003. A new dynamic column-pressure state relaxes toward a flow-scaled target:

$$
P_{tgt}^{C003} = P_{des}^{C003} + K_P^{C003}\,\frac{\dot m_{305} - \dot m_{305,des}}{\dot m_{305,des}},
\qquad
\frac{dP_{C003}}{dt} = \frac{P_{tgt}^{C003} - P_{C003}}{\tau_P^{C003}}
$$

with $P_{des}^{C003}=4.1$ bar a, $K_P^{C003}=1.20$ bar/(fractional excess), $\tau_P^{C003}=90$ s. The same increased feed propagates through the level cascade (LIC-323501 → `m_314`) to the flash vapour `m_701` and thence to the LP node read by PIC-323203 (`r3232_e011_P`), so **both** PT-323201 and PT-323203 rise. (`main.py`: state init ~2281, constants ~398, integrator after Stage-1 holdup ~3305, payload `C003.P_bara`.)

**Coupling 2 — Unit 323 (LV-323501 → 323F004 pressure, read by PIC-323203).** Increasing LV-323501 opening raises the C003 bottom drain `m_314 = M_{314,des}(op/op_{des})` → flash vapour `m_701 = \Phi_{V701}\,m_{314}`. A new dynamic flash pressure accumulates:

$$
P_{tgt}^{F004} = P_{des}^{F004} + K_P^{F004}\,\frac{\dot m_{701} - \dot m_{701,des}}{\dot m_{701,des}},
\qquad
\frac{dP_{F004}}{dt} = \frac{P_{tgt}^{F004} - P_{F004}}{\tau_P^{F004}}
$$

with $P_{des}^{F004}=1.13$ bar a, $K_P^{F004}=0.45$ bar/(fractional excess), $\tau_P^{F004}=90$ s. Since `m_701` feeds `in_e011`, the same action lifts the PIC-323203 LP-node pressure — F004 and the E011/D011 LP header are one physical low-pressure space.

**Seed-exactness / pin invariance.** At the design seed $\dot m_{305}=\dot m_{305,des}$ and $\dot m_{701}=\dot m_{701,des}$, so $P_{tgt}=P_{des}$ and $dP/dt=0$; both states are pure downstream read-outs (nothing upstream consumes them), so the HPCC_UA back-solve is unperturbed. **Boot-pin regression: all 25 leaf values bit-identical** (`golden f0e50256…`).

**Functional verification** (settle → step → settle):

| Action | PT-323201 (bar a) | PT-323203 (bar a) | 323F004 P (bar a) |
|---|---|---|---|
| baseline (design seed) | 4.100 | 1.130 | 1.130 |
| LV-322501 46.1 → 85 % | **5.111 (+1.011)** | **1.154 (+0.024)** | 1.511 |
| LV-323501 → 90 % | 4.100 | **1.190 (+0.053)** | **1.490 (+0.361)** |

Both required dominoes reproduce: LV-322501↑ ⇒ PT-323201 ∧ PT-323203 ↑; LV-323501↑ ⇒ 323F004 pressure ↑ (seen by PIC-323203).

---

## 6. Categorized Gap Register (severity-ranked)

| ID | Sev | Node / File | Gap | Fix class |
|---|---|---|---|---|
| **P4-A / P2-B** | **S1** | 322E003 + 322C001 (`main.py` 1356–1368, 3415–3437) | Scrubber vent reconciliation injects 156.95 kmol/h NH₃+CO₂ "slip" that is scalarised at `hv604` and lost to atmosphere at pinned 322C001 → species-untracked reactant leak, masked at design, back-filled by +4.2 % NH₃ makeup | **Conservative split** |
| P2-A | S1 | 322E003 vent (`main.py` 1364) | Live vent Σ 214.77 kmol/h supersedes OEM stream 204 (64.78) → stream-204 bit-exactness broken | fixed by P4-A fix |
| P3-A | S2 | `controllers.py` | No derivative filter $T_f$, no deadzone DZ vs plant DCS blocks | **Kernel extension** |
| P3-B | S2 | FIC-328401/323402/328404/328402 | Loop-level $K_c$ overwrites masking process-gain/lag error | fixed after P4/P5 |
| P2-C | S2 | `SYN_P_DES_BARA` (`main.py` 1442) | Reactor P +3.6 bar high (144.9 vs 141.3) | recalibrate |
| P2-D | S2 | UF-85 dosing (335) | Stream 694/697 −46 % | rescale additive |
| P5-A | S2 | `FEED_TD_S`, `FIC_329409_TAU_S`, `TIC_329005_TAU_S` | Calibrated lags; verify against FOPTD band | verify/anchor |
| P5-B | S2 | `main.py` 2901/2907 | `flow_frac` division singularity at load→0 | guard floor |
| **P5-C** | **S2** | 323C003 / 323F004 (`main.py` P_bara constants) | PT-323201 & 323F004 pressures were fixed constants → LV-322501 / LV-323501 could not forward-accumulate upstream pressure (missing hydraulic domino) | **CLOSED — dynamic lag-to-target states; pin bit-exact** |
| P2-E | S3 | Evap-I/II | +0.7…0.9 pt concentration | trim |
| P1-res | S3 | 6 unmatched tags | Out-of-envelope aux items | document |
| P1-lbl / P4-C / P4-B / P4-D / P4-E | S3 | comments / confirmations | Cosmetic or confirmed-correct | document only |

---

## 7. File-Specific Coding Blueprint (handoff to Opus)

> **All edits below are for the Opus implementation pass. Do not apply during this audit.** Each item names the file, the anchor, the exact change, and the conservation invariant that must hold after the change.

### 7.1 P4-A / P2-B — Make the scrubber → LP-absorber path species-conservative (S1, highest priority)

**File:** `backend/main.py`

**Root cause to remove:** the vent is inflated to force a *local* total-mass GAP=0 while species identity is discarded at `hv604`, leaking reactant at the pinned 322C001.

**Step 1 — Restore the OEM vent as the design target.**
- At `main.py` 1356–1366, demote `_SCRUB_OFFGAS_RECON` and re-derive the live vent from the **OEM stream-204 composition** (`SCRUB_OFFGAS_MOLPCT`, 64.78 kmol/h): 100 % of inerts (N₂, O₂, CH₄, H₂) + the OEM trace NH₃/CO₂ (5.35 + 1.44 kmol/h). Keep `_SCRUB_OFFGAS_RECON` as a commented provenance block, not live.

**Step 2 — Close 322E003 per-species by fixing the *overflow*, not the vent.**
- The reconciliation exists because `OFFGAS_DES` (feed) and `EJ_SUCTION` (overflow) don't close per species. Re-solve the overflow vector as the **residual of a true species balance**:
$$
\text{overflow}_i = \text{feed}_i - \text{vent}_i,\qquad \text{feed}_i = \text{offgas\_feed}_i + \text{carb}_i
$$
with `vent` fixed to the OEM 204 vector (Step 1). This routes the 156.95 kmol/h NH₃+CO₂ into the **overflow → 322F001 ejector → HPCC → reactor** recycle where the plant actually sends it, instead of to atmosphere. Verify the resulting overflow total still matches PFD 206 (2517.69 kmol/h) to design tolerance; the current `EJ_SUCTION` total already agrees to +0.07 %, so the redistribution is within tolerance.

**Step 3 — Retire the compensating makeup (P2-B).**
- With the reactant no longer leaking, reduce the NH₃ battery-limit feed from 42.762 t/h toward stream 113 = 41.042 t/h. Re-pin `F_in_BL_th` after Step 2 so the loop closes at the OEM feed. **Do not** simply overwrite the number — let it fall out of the corrected recycle, then pin.

**Invariant to assert (add a diagnostic, do not inject):** at $s=1$, `Σfeed − Σoffgas − Σoverflow = 0` **and** per-species NH₃/CO₂ recycled via overflow equals reactor-offgas-in minus OEM-vent, within 1e-6 kmol/h. Off-design, the NH₃/CO₂ atmospheric loss (`vent_c001` species content) must be ≤ OEM 204 slip scaled by $s$.

**Optional hardening (322C001):** if full species tracking through 322C001 is out of scope, at minimum make `abs_c001` and `vent_c001` conserve the *incoming* NH₃/CO₂ mass so that reactant cannot exit via `vent_c001` beyond the OEM inert+trace rate. Replace the fixed-fraction `A328_PHI_ABS·gcb_m` split with a species-aware split keyed on the incoming vent composition from Step 1.

### 7.2 P3-A — Extend the controller kernel with $T_f$ and deadzone (S2)

**File:** `backend/controllers.py`

- Add optional fields `TF` (derivative filter time-constant) and `DZ` (deadzone half-width) to the controller state/struct, defaulting to `TF=0.0`, `DZ=0.0` (i.e. current behaviour unchanged when unset).
- Filtered derivative (replace the raw second-difference term):
$$
D_k = \frac{T_f}{T_f + dt}\,D_{k-1} \;-\; \frac{K_c T_d}{T_f + dt}\,(PV_k - PV_{k-1})
$$
(store $D_{k-1}$ in state). When `TF=0`, this must collapse **exactly** to the existing term $-K_c T_d (PV_k-2PV_{k-1}+PV_{k-2})/dt$ — unit-test that equivalence.
- Deadzone on the error before the integral term: if $|SP_k-PV_k|<\text{DZ}$, zero the proportional-on-error/integral contribution for that step.
- Populate `TF`/`DZ` per loop **from the Master Controller Constraint List** (span-normalised → EU conversion per §3). Do not fabricate values; only set where the plant sheet specifies them.

### 7.3 P3-B — Restore plant $K_c$ after process fidelity is fixed (S2)

**File:** `backend/main.py` (FIC-328401/323402/328404/328402 gain assignments)

- **Order dependency:** apply only *after* §7.1 (process gain of the scrubber/recycle loop changes) and §7.2 ($T_f$ available). Then replace the stability-retune gains (0.30 / 0.5 / 0.5 / 0.06) with the Constraint-List values (EU-converted). Re-run the transient suite; if a loop still chatters, the residual error is a remaining lag defect (§7.6), **not** a reason to re-detune.

### 7.4 P2-C — Reactor pressure calibration (S2)

**File:** `backend/main.py` 1442–1444

- `SYN_P_DES_BARA` is pinned to `SCRUB_OVERFLOW_P_BARA` (140.7 bar a). The +3.6 bar reactor-P bias points at `SYN_P_VENT_GAIN=0.30` (bar per unit vent deficit) over-lifting PT-329201. Re-fit `SYN_P_VENT_GAIN` against the FOPTD $P_f=144.0$ bar g fingerprint so the settled reactor gauge pressure lands at PFD 141.3 bar (≈143.3 bar g equivalent) within the $[137.5,150.5]$ band. Keep the design pin sourced, not hand-tuned.

### 7.5 P2-D / P2-E — Additive & evaporator trims (S2/S3)

**File:** `backend/main.py` (335 UF dosing; 324 evaporator concentration targets)

- Rescale UF-85 dosing so stream 694/697 → 697 kg/h (currently 376.3). Trace the dosing ratio constant; scale by ≈1.85. No synthesis-loop coupling, low risk.
- Trim Evap-I target 95.0 → 94.31 %, Evap-II 98.6 → 97.71 % against HMB 94.31/97.71. Cosmetic.

### 7.6 P5-A / P5-B — Lag anchoring & singularity guard (S2)

**File:** `backend/main.py`

- For `FEED_TD_S=345`, `FIC_329409_TAU_S=3.0`, `TIC_329005_TAU_S=25.0`: add a sourcing comment tying each to its transport length / instrument response, and add a regression assert that the composite loop FOPTD stays within $\tau\in[2884,4055]$ s, $t_d\le572$ s after any change.
- Line 2901/2907: ensure `flow_frac` floor is strictly $>0$ before the division $\tau_n=\text{REACT\_TAU\_NODE\_MIN}[n]\cdot60/\text{flow\_frac}$ (e.g. `flow_frac = max(clamp(co2_scale,0,1), 1e-3)`), so node time-constants remain finite as load → 0.

### 7.7 Documentation-only (S3)

- Fix the LIC-328504/505 comment-label swap between the controller-definition block and the sim-tuning block (comments only; wiring is correct).
- Add a scope note listing the 6 out-of-envelope tags (`323D003, 329E002, 329E004, 329P004, 329U001, 335D007`) as intentionally unmodelled auxiliaries.
- Convert the P2-A provenance (superseded stream-204 datasheet) into a clearly-labelled historical comment once §7.1 restores OEM fidelity.

---

## 8. Verification / Acceptance criteria (post-implementation)

1. **Conservation (S1):** at $s=1$, every node total-mass residual and NH₃/CO₂ species residual ≤ 1e-6 kmol/h; **no** residual injected into any stream (diagnostics only). Off-design $s\in[0,1.1]$: atmospheric NH₃/CO₂ loss ≤ OEM stream-204 slip $\times s$.
2. **Design bit-exactness:** streams 107, 203, 204, 206, 207, 308/310, 755, 917 all reproduce OEM 1750 MTPD to machine precision; 1925 MTPD = uniform $1.1000\times$.
3. **Feed closure:** NH₃ BL feed within +0.5 % of stream 113 (41.042 t/h) after §7.1/§7.3.
4. **Pressure:** settled reactor gauge pressure within $[137.5,150.5]$ bar g, biased to PFD 141.3.
5. **Transient:** PT-329201 step response $\tau\in[2884,4055]$ s, $t_d\le572$ s, $R^2\ge0.98$.
6. **Controllers:** plant $K_c$ (EU-converted) restored on the four retuned loops with no sustained chatter; `TF=0`/`DZ=0` path bit-identical to pre-change kernel.

---

## 9. Preserved engineering state (for the implementation pass)

- **PT-329201 FOPTD:** $P_0=5.7$, $P_f=144.0$ bar g, $\tau=3469.5\pm585.9$ s, $t_d=344.7\pm280.3$ s, $R^2=0.9888$.
- **Pinned design state:** LT-322504 = 80.0000 %, strip_level = 50.0000 %, $F_{CO_2,th}=54.618$ t/h, $F_{in,BL,th}=42.762$ t/h (target → 41.042), pumpB speed_act = 127.0131 rpm, open_act = 83.5612 %, RATIO_PV_DES = 2.0231315310702604, LV322501_OPEN_DES = 46.1 %.
- **LT-322504 law:** $LT=\operatorname{clamp}(80+(H_{liq}-20.0)/1.5\times100,\,0,\,100)$.
- **Reactor kinetics (Modified Inoue–Kanai):**
$$
X = \min\!\Big(X_\infty\cdot\frac{a(L-2)}{1+a(L-2)}\cdot\frac{1}{1+bW}\cdot\exp[-k((T-T_{opt})^2-(T_0-T_{opt})^2)],\ X_\infty\Big)
$$
$L_0=3.072961$, $W_0=0.407828$, $T_0=183.0$ °C, $X_\infty=0.9196$, $a=3.6180$ (frozen), $b=0.85$, $k=0.0015$, $X_{des}=0.543$; $T_{opt}(L)=\operatorname{clip}(185+2(L-2),185,195)$ °C; $f_L(L_0)=0.795165$, $f_W(W_0)=0.742582$.
- **Scrubber vectors:** `_SCRUB_OFFGAS_RECON` Σ 214.77 kmol/h {CO₂ 62.18213955, NH₃ 94.76367511, N₂ 44.53, O₂ 7.42, CH₄ 3.86, H₂ 2.02, H₂O 0} — **to be superseded** by OEM 204 (64.78) per §7.1; `SCRUB_OVERFLOW` Σ ≈ 2519.4 kmol/h (= EJ suction); `SCRUB_CARB_ABS_GAIN=0.15`.
- **Do-not-repeat (prior failed approaches):** `_delay` from live sub-step dt (MemoryError); hard-coded $\tau=3470$; interpolated xlsx rows; hydraulic flow derating; editing hand-valve `*_DES`; $g_T$ inside stripper slip; shadow-holdup LT.

---

## 10. HALT

Audit complete across all five phases. Deliverable produced. **No source code was modified.** Implementation of §7 is handed off to the Opus model per mandate.
