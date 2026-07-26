# Audit — Desorber/Hydrolyser (328) and Evaporation (323/324)

Scope: stream-to-equipment binding + mathematical framework (MESH), thermodynamic states, and
downstream flowsheet connectivity.

Sources of truth, in order:
1. `References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md` (PFD_20 / PFD_21 / PFD_22)
2. `References/Mapping of Desorber Hydrolyzer unit.md`
3. `References/Mapping of Evaporation Section.md`

Target: `backend/main.py`.

## Remediation status (2026-07-26)

This report records the original audit and its remediation. The 2026-07-26 condenser/absorber pass
subsequently closed C24/C15/C23 and corrected the 323C005/328D003 routing; current equations and
anchors are documented in `research_plan_324_vacuum_train.md` and As-Built §22.11.

| value | before → after | why |
|---|---|---|
| `DESORB_328.D001.PIC_328202.pv/sp` | 2.6 → 3.5 bar a | B5: transmitter rebound from the drum to the column, matching PFD-22 stream 737 |
| `EVAP_324.E001.motive_kgh` | 650 → 390 kg/h | C16: PFD-21 stream 924 |
| `EVAP_324.VAC.condensate_th` | 16.81 → 28.82 t/h | C2: stream 790 was missing from the condensable load |
| `DESORB_328.C002.ovhd737_th` | 6.66 → 6.67 t/h | not a physical change — stream 737 is 6665 kg/h = 6.665 t/h, exactly on the 2-dp rounding boundary; a 1e-10 float shift flips which way it rounds |
| `LPCC_3232.C005.bot_th` | 2.89 → 2.70 t/h | B10: the demin makeup was overstated by exactly the 190 kg/h of stream 759 it had been standing in for |

Raw state drift elsewhere is ~1e-8 relative or smaller, below published resolution.

| id | defect | status | evidence of the fix |
|---|---|---|---|
| B1 | LIC-328504/505 swapped | **FIXED** | identifiers swapped in `step_sim`, declarations, telemetry blocks and `frontend/overlays.js` |
| B2 | stream 793 destroyed | **FIXED** | now enters `in_d001` + `sens_d001` at the Comp-I bulk temperature |
| B4 | TT-328008 on the wrong stream, aliased to TT-328010 | **FIXED** | TT-328008 → live 328C002 top (117 °C); TT-328010 → live 328E007 cold outlet (114 °C); two distinct instruments, HMI repointed |
| B6 | TT-328011 aliased to TT-328012 | **FIXED** | published from the live hydrolyser state at the PFD 12 °C offset (188 °C) |
| B8 | PT-324201 / PT-324204 unpublished | **FIXED** | both published; shell pressure shares the rounded PFD manifold pending gas-side ΔP data |
| C2 | evaporation → 328D003 loop open | **FIXED** | 719/720/721/759 are individual live condenser returns with distinct thermal states |
| C3 | 324F001 holdup identically frozen | **FIXED** | drain is now a square-root hydraulic law. Probe: a +25 % feed step moves the holdup **+1158.7 kg** (was exactly 0.0) |
| C5 | vacuum ODEs open integrators | **FIXED** | both ejector pulls carry the suction-pressure roll-off 323F010 already had. Probe: HIC-329605 50 → 25 % with PIC-324202 in MAN now **settles at 0.660 bar a** (= 0.33/0.5, the expected fixed point) instead of railing to the 1.0 clamp in 8.4 s |
| C7 | clip residual never read | **FIXED** | published as `SPECIES_323_324.clip_resid_kgh`; reads C003 0, F004 −1.917, F010 0, **E001 −170.105**, **E003 −126.793** kg/h |
| C10 | 328E007 not modelled | **FIXED** | ε-model wired with an energy-balance closure on the hot side (same idiom as 328E021); both anchors verified bit-exact in IEEE754. TT-328006 is live (89.0 → 91.4 under a steam cut) |
| C18 | 324E001 feed temperature frozen | **FIXED** | reads the live 323D002 tank state |
| C31 | TIC-328008 temperature leg frozen | **FIXED** | inferential now rides the live column top |
| C32 | TIC-328012 differential leg frozen | **FIXED** | uses the live 328E021 cold outlet `T_746` |
| C1 | desorber dT/dt ≡ 0 | **FIXED** | 328C002 and 328C004 given pressure states and bubble-point temperatures. Probe: a 30 % LP-steam cut to 328C004 now moves it **−9.93 °C** (143.0 → 133.1; was exactly 0.0), and cutting the 328C003 overhead relief moves 328C002 **−2.33 °C** (was 8e-10). See below for why the auditor's own proposed fix was wrong |
| B5 | PIC-328202 PV on the drum, not the column | **FIXED** | rebound to the live 328C002 pressure state; SP re-seeded 2.6 → 3.5 bar a with the span shifted |
| C16 | 324F002 motive steam 650 vs PFD 390 | **FIXED** | PFD wins; pull is ratio-anchored so the fixed point is untouched |
| C15 | false air 250/120 vs PFD 21/21 | **FIXED** | applied with C24; vacuum inventory now sees post-condenser gas and the sign-rule transient gate passes |
| B10 | stream 759 missing from 328D003 | **FIXED** | 759 is an individual Comp-I condenser return; the supplied absorber map removes the fictitious C005 makeup entirely |
| B3, B7, B9, B11, C4, C6, C8, C9, C11-C17, C19-C30 | — | **OPEN** | unchanged; several need decisions rather than edits |

### C33 — resolved by constrained PFD data reconciliation

**Resolution (2026-07-26):** exact PFD mass/thermal nodes govern condenser and ejector anchors, while
the engine retains molecular conservation for live off-design departures. Independent PFD rounding
and molecular residuals are published rather than hidden behind a fictitious urea sink. This decision
unblocked and closed C24, C15, and C23. The text below is retained as the conflict record.

Attempting C24 surfaced a discrepancy no auditor reported, because the two auditors who would have
caught it (`connectivity`, `thermo-anchor`) never ran. **The evaporation section's own design flows
disagree with the PFD-21 stream rows they would have to feed the condensers with:**

| stream | model design | PFD-21 | gap |
|---|---|---|---|
| 790 — 323F010 vapour | 12.01 t/h | 12.040 | −30 kg/h |
| 705 — 324F001 vapour | 14.07 t/h | 14.778 + 21 air | **−708 kg/h** |
| 709 — 324F003 vapour | 2.74 t/h | 3.321 + 21 air | **−581 kg/h** |
| 401 — Evaporator-I melt | 78.68 t/h | 78.042 | **+638 kg/h** |
| 402 — Evaporator-II melt | 75.94 t/h | 74.721 | **+1219 kg/h** |

The model's melts are wetter than the PFD's and its vapour rates correspondingly lower.

Root cause: **the PFD itself is not urea-conservative across unit 324.** Stream 317 carries
92820 × 0.80 = 74256 kg/h of urea; stream 401 carries 78042 × 0.9431 = 73602; stream 402 carries
74721 × 0.9771 = 72990. That is 654 then 612 kg/h of urea disappearing — about 1266 kg/h total,
against a biuret extent that only accounts for ~298 kg/h (C6). The engine resolves the conflict by
conserving urea and pinning the melt *strengths* to the PFD percentages, which necessarily makes its
*flows* differ from the PFD rows. This is the same inconsistency the clip residual (C7) reports as
−170.1 and −126.8 kg/h and that `sol_pin_strength` exists to paper over.

**Why it blocks C24:** the condenser train has to be anchored on a design inlet. Anchoring on the
PFD (703 = 26840 kg/h, condensate 719 = 26768) against a live design inlet of only ~26107 kg/h drives
the condensate straight into its `m_in − m_nc` clamp, moving the 328D003 return off design and
breaking the pin. Anchoring on the model's own flows instead means the condensate returns no longer
equal `A328_D003_M719/720/721`, so 328D003's whole inlet set and the `A328_D003_TI` back-solve have
to be re-derived at the same time.

**Order of work implied:** resolve C33 (decide whether urea is conserved or the PFD rows are
authoritative — they cannot both hold), then C6/C7 fall out of the same decision, then C24 can be
anchored, and only then C15 and C23. A partial C24 was written and **reverted** rather than left in
the tree half-anchored.

### C15/C24 sequencing — completed together

Decision taken: PFD overrides the OEM datasheet values. **C16 applied** (324F002 motive steam
650 → 390 kg/h). It is risk-free: the pull is anchored as the ratio `mot9605_m / MOTIVE_DES`, so the
design fixed point is untouched and only the published flow corrects. PFD 390 is also the stronger
evidence — 706 (72) + 924 (390) = 462 = stream 708, exact.

**C15 deliberately deferred.** Correcting the false air 250 → 21 kg/h in isolation would make
PIC-324202 nearly inert: 21 kg/h against a 14 323 kg/h ejector pull is 0.15 % of the load, so the
loop would lose essentially all authority over the 324F001 vacuum. The reason the numbers are that
lopsided is finding C24 — because the condensers are not modelled, the entire 14 t/h of process
vapour is routed through the ejector momentum balance, when on the plant 324E002 condenses it and
the ejector lifts only the non-condensables. Against a non-condensable-only load, 21 kg/h of false
air is a real manipulated variable. So C15 belongs in the same change as C24, together with a
retune of PIC-324202/324203 for the corrected gain. Applying it alone would make the model behave
worse while making one constant more correct.

### C1 — the auditor found the right symptom and prescribed the wrong cure

The cancellation is real and was verified by hand: `LAM737 ≡ Q_DES/(m737_DES/3600)` while
`m_737 ≡ m737_DES·(q/Q_DES)`, so `P_c002 ≡ 0` on the energy branch.

But the auditor's proposed fix — "any formulation where λ is not defined as `Q_DES/(m_vap_DES/3600)`
will restore dT/dt" — would have injected *non-physical* dT/dt. **A boiling vessel at fixed pressure
genuinely does hold its temperature:** surplus duty leaves as vapour, not as sensible heat. Breaking
the λ identity would make the column heat up while boiling, which is worse than the bug.

The real defect was one level down. The boiling temperature was pinned at the **design** value
(139 / 143 °C) because neither column had a pressure state — 328C002's pressure existed only as
`s.a328_d001_P + 0.9` inside a single inferential, and 328C004 had none at all. With no P there is
no `T_bub(P, x)`, so the plant's actual mechanism was missing.

What was implemented instead separates two quantities the old code had collapsed into one:

- **generation** `gen737 / gen750` — the boil-up the net duty sustains (the old "energy cap",
  unchanged in form, so the seed still ties exactly);
- **outflow** `m_737 / m_750` — what the overhead line passes at the *live* column pressure.

Their imbalance drives a pressure ODE, and the temperature is the bubble point at the column bottom:
`T = tsat_steam(P + ΔP_col)`. The chain the plant uses now exists end to end:
**duty → boil-up → pressure → bubble point → temperature.**

The bottom-node offset `ΔP_col` is back-solved from each column's own PFD (T_bottom, P_overhead)
pair. `psat_water_bara` and `tsat_steam` are analytic inverses sharing one set of Antoine
coefficients, and the round trip `tsat_steam(psat_water_bara(T)) == T` was checked and is **bit-exact**
at both 143.0 and 139.0, so the design temperatures are reproduced exactly.

- 328C004: `psat(143) − 3.7 = +0.204 bar` — 22 trays of static head, physically a real column.
- 328C002: `psat(139) − 3.5 = −0.010 bar` — essentially zero. The small *negative* value is the
  dissolved NH3/CO2 raising the liquor's vapour pressure above pure water, so the pure-water bubble
  point slightly overstates it. Carried as one lumped offset and documented as such.

Because 328C002 now has a real pressure state, two further findings closed with it: **B5**
(PIC-328202's transmitter rebound from the drum to the column) and the frozen `R328_E004_DP`, which
is now the computed difference between two live states.

**Still open and now more visible:** C4 — the per-vessel back-solved latent heats remain mutually
inconsistent (+413 kW created at design). The pressure states did not change that; they make it
easier to fix, because a single enthalpy function can now be evaluated at a real (T, P) per node.

## Confidence status

A multi-agent audit was run. **6 of 8 auditors completed; the adversarial-refutation pass and the
synthesis pass did not run** (session limit). Consequences:

- Findings marked **[V]** were re-derived by hand against the source lines and are confirmed.
- All other findings are **single-source and unverified**. Treat as leads: re-read the cited lines
  before acting.
- Two areas were never audited: **(a)** full sweep of every coded design constant against its PFD
  column, and **(b)** thermodynamic state consistency (coded T/P vs saturation, density constants
  used by volumetric FIC loops, cp anchors, latent heat of the real mixed vapour vs pure water).

---

# A. Stream / tag binding defects in the mapping documents

## A1. `Mapping of Evaporation Section.md:12-13` — stream 705 used for three different lines [V]

The doc calls the 324F001 overhead, the combined line into the 324E002 shell, and the 324E002
uncondensed vent all "705".

PFD_21 closes it exactly:

| line | PFD | check |
|---|---|---|
| 324F001 overhead = **705** | 14799 kg/h, 130 °C, 0.3 bar a | 317 − 401 = 92820 − 78042 = 14778, + 784 air 21 = **14799** |
| combined into 324E002 = **703** | 26840 kg/h, 116 °C | 790 (12040) + 705 (14799) = **26839**; molar 646.98 + 807.70 = 1454.68 vs 703 = 1454.67 |
| 324E002 vent = **706** | 72 kg/h, 45 °C | 703 − 719 = 26840 − 26768 = **72** |

705 is 96.77 % H2O and cannot be a condenser vent; 706 is 38.64 % N2 / 10.26 % O2, which is.

Fix: line 12 → 324F001 overhead is 705, the HV-323605 gas is 790 (as the doc's own line 5 says);
line 13 → mixed line is **703**, uncondensed vent is **706**.

## A2. `Mapping of Evaporation Section.md:16` — stream 717 double-booked [V]

Line 16 gives the 324F002 discharge to 323C005 as 717; line 31 gives the 324F005 discharge to
324E007 as 717. Only line 31 is right.

- 324F002: 706 (72) + motive 924 (390) = **462 = stream 708** (462 kg/h, 121 °C, 1 bar a). 708 is
  otherwise unreferenced in the whole document.
- 324F005: 715 (41) + motive 929 (180) = **221 = stream 717** ✓

Fix: line 16 → "…goes to 323C005 (stream **708**)".

## A3. `Mapping of Evaporation Section.md:12,14` — false air 784 placed on the 324E002 shell

784 is already inside stream 705 (14778 + 21 = 14799 exactly), so PV-324202 breaks vacuum on
**324F001**, upstream of the tee with 790 — not on the 324E002 shell. Adding another 0.73 kmol/h at
the shell would overshoot the 703 closure. `main.py:1528` and `main.py:4013` already bind
PV-324202 to 324F001, i.e. the code is right and the doc is wrong here.

The symmetric statement at line 22 (783 into the 324F003 overhead) **is** correct:
(78042 − 74721) + 21 = 3342 = stream 709 ✓

## A4. `Mapping of Evaporation Section.md:2,4` — TT-323014 on two streams

Line 2 puts it on 319 (106 °C, 1.1 bar a, 71.74 % urea); line 4 puts it on 315 (99 °C, 0.5 bar a,
80.00 % urea). A heater (323E010) and a vacuum flash (323F010) sit between them. One citation is a
transcription slip. `main.py` publishes the two vessels under separate tags
(`TT_323005` at 6268, `TT_323010` at 6277) and has no `TT_323014` at all.

## A5. `Mapping of Evaporation Section.md:6` — HV-323605 cannot lower both sides

Doc: "A step increase in HV-323605 opening will cause a step decrease in pressure inside 323F010
**and shell side of 324E002**." HV-323605 is the only restriction between 0.5 bar a (790/315) and
0.3 bar a (703/719/706). Opening a series throttle transfers pressure downstream — it lowers
323F010 and **raises** the shell. The doc's own line 15 correctly attributes the common-mode drop to
HV-329605 (the 324F002 motive steam).

## A6. `Mapping of Desorber Hydrolyzer unit.md:16,20,27` — LV-328504 letdown flash misdescribed [V]

Doc sends "stream 780 Gas phase" onto the top tray "to be desorbed", then attributes the whole
overhead to 781 while calling the line to 328C002 "750" — i.e. it implies 750 = 781.

PFD_22 says otherwise, exactly:

- 749 (34062 kg/h, 148 °C, 16.6 bar a) lets down to **779** (33413 kg/h liquid, 139 °C, 3.7 bar a)
  + **780** (649 kg/h vapour, 139 °C). 33413 + 649 = **34062** ✓
- **750 = 780 + 781** = 649 + 6184 = **6833** ✓ (component check: H2O 594.1 + 5888.8 = 6482.9 vs
  6833 × 0.9488 = 6483.3; NH3 54.8 + 292.5 = 347.3 vs 347.1)

So 780 **bypasses the trays** and joins the overhead. Implemented as the doc reads, 649 kg/h (9.5 %
of 750) of NH3-rich vapour is lost.

## A7. `Mapping of Desorber Hydrolyzer unit.md:2` — pump "328P004" does not exist

The desorber feed pump on 328D003 → 328E007 → 328C002 (stream 735) is **328P003 A/B**
(`References/328P003, 328P006, 328P007, ... Datasheets.md:18`;
`References/328E021 328E007 328P003 328P006.md:465`). The tag `328P004` appears nowhere else in the
repo. The same doc's line 36 already says 793 comes off 328P003, and PFD_22 gives 735 and 793
identical conditions (56 °C, 4.1 bar a, ρ 992.4) — one discharge header.

## A8. `Mapping of Desorber Hydrolyzer unit.md:35` — "328P008" → **323P008 A/B**

Lean carbamate pump on 323D011 (`References/323E011 323D011 323P008 Datasheets.md:31`).
PFD_22: 718 = 7123, 718A = 3562, 718B = 3562, all 45 °C / 4.1 bar a / ρ 1065.

## A9. `Mapping of Desorber Hydrolyzer unit.md:41` — "328E011" → **323E011**

Stream 786 is tabulated in PFD_21 as well as PFD_22 and is an inlet term of the 323E011 balance
(`main.py:1046`, `main.py:1268`). No tag `328E011` exists anywhere.

## A10. `Mapping of Desorber Hydrolyzer unit.md:42 vs :46` — TIC-328008 given two locations

Line 42 places it on the 328D001 bottoms (774, 61 °C / 2.6 bar a); line 46 defines it as the
overhead water-content soft sensor on 737 (117 °C / 3.5 bar a). Line 46 is the one the PFD and the
328E004/328D001 datasheet support (that datasheet quotes ~46 vol % water in the overheads; PFD 737
gives 46.21 mol% H2O). TIC-328002 is named at line 42 with no service defined anywhere.

## A11. `Mapping of Desorber Hydrolyzer unit.md:31-33` — 47.6 % of the 328P007 discharge has no destination

Doc says "2 lines". PFD_22 says three branches off 740/742 (33724 kg/h, 89 °C, 3.9 bar a):
742A = 17680 (cooling tower, confirmed by PFD_28), 742B = 16043 (granulation network, cf. 742G),
741 = 0 (the FV-328406 recycle). Doc accounts for 17680 + 0 = 17680; **16044 kg/h unassigned**.

## A12. `Mapping of Desorber Hydrolyzer unit.md:45` — the 328C002 reflux has no stream number

It is **775** (1675 kg/h, 61 °C). Without it the column cannot be closed:
in = 738 + 748 + 750 + 775 = 31114 + 812 + 6833 + 1675 = **40434** = out = 737 + 743 = 6665 + 33769 ✓
Also 774 (9950) = 775 (1675) + 776 (8275) ✓ — 774 is the 328P002 suction, not a delivery.

## A13. `Mapping of Desorber Hydrolyzer unit.md:33` — "LV-328406" does not exist; cascade inverted

The valve on that leg is FV-328406 (named in the same sentence). And "If FIC-328406 is set on CAS,
controls LIC-328505" inverts the cascade — in CAS the flow loop is the **slave** of the level
controller. Sentence is also left unclosed.

## A14. `Mapping of Desorber Hydrolyzer unit.md:38` — 328E004 drain is the bottom nozzle

`References/328E004 328D001 328P002 Datasheets.md:28`: "This two-phase mixture exits the bottom
nozzle of the condenser and drops directly into the underlying Level Tank."

## A15. `Mapping of Desorber Hydrolyzer unit.md` — TT-328009 never located; TIC-328002 has no service

TT-328004/005/006/007/008/010/011/012/013 are all placed; 328009 does not occur in the file.

---

# B. Stream / tag binding defects in `backend/main.py`

## B1. LIC-328504 and LIC-328505 are swapped [V] — CRITICAL

- `main.py:5561-5563`: `lvl_c003 = s.a328_c003_M/…` → `_ctrl_ipd(s.LIC_328505, lvl_c003, dt)` →
  drives `m_747` (hydrolyser bottoms).
- `main.py:5605-5607`: `lvl_c004 = s.a328_c004_M/…` → `_ctrl_ipd(s.LIC_328504, lvl_c004, dt)` →
  drives `m_739` (desorber-II bottoms).
- Declarations `main.py:4327` / `main.py:4332` carry the same swap; telemetry `main.py:6389` /
  `main.py:6413` and `frontend/overlays.js:323,326` repeat it.

Mapping doc lines 12/16 put **LIC-328504 on 328C003** (level above the 1st top tray, LV-328504 → top
of 328C004); lines 28/32 put **LIC-328505 on 328C004 bottom** (LV-328505 → cooling-tower B.L.).
PFD_22 supports the doc: LV-328504 is the 16.6 → 3.7 bar letdown on 749; LV-328505 sits on the
739/740 export at 3.9 bar a.

The level→valve **pairing** is physically correct, so no conservation law breaks and the design pin
holds bit-exact (both seed at 50 %). What is wrong is the tag on the faceplate: a trainee answering
a hydrolyser high-level alarm is sent to LIC-328504, which moves the desorber-II export valve.

Fix: swap the identifiers at `main.py:5562` and `main.py:5606`, the comments at 4327/4332, the
telemetry keys between the C003 (6384-6408) and C004 (6409-6429) blocks, and the two `bind:` paths.

## B2. Stream 793 is drawn out of 328D003 Comp-I and delivered nowhere [V] — CRITICAL

`main.py:5470` creates `m_793`; `main.py:5485` subtracts it (`out_compI = m_735 + m_401 + m_402 + m_793`).
`m_793` appears **only** at 5470, 5485 and two read-only telemetry lines (6367, 6368). No node
receives it. `main.py:5626`: `in_d001 = m_737 + m718A_prev` — two inlets only.

`S793_CAP_KGH = 1534.0` (`main.py:1400`). Full stroke destroys 1534 kg/h. At the 0 % design stroke
the leak is 0, which is why the boot pin never catches it.

Mapping doc lines 34-36 fix the destination: into the 737 header ahead of 328E004, i.e. into 328D001.

## B3. FIC-328405 is on stream 793, not 718A; 718A has no controller

`main.py:4200-4204` and `main.py:1244-1249` document the move; `main.py:5774-5780` shows 718A is now
an unmetered `_lag1` remainder. Mapping doc line 35 assigns FIC-328405 to 718A (3562 kg/h). The
stated reason for the move is numerical stability ("made the D011 level loop ring"), not a PFD
value — and the PFD assigns no instruments, so it cannot override the doc here. Result: a real
3562 kg/h metered flow has no handle, and the faceplate carrying its tag drives a 0 kg/h spare.

## B4. TT-328008 reads the 328E007 cold outlet, and is aliased to TT-328010

`main.py:6432` publishes `TT_328008 = R328_E007_TC_OUT` (114 °C = stream 738).
`frontend/overlays.js:346,348` bind **both** TT-328008 and TT-328010 to that one field.
Doc line 46 puts TT-328008 on the 328C002 overhead (737, **117 °C**); doc line 3 puts TT-328010 on
738. The code already knows 117 (`main.py:1086`, `main.py:1445-1446`).

## B5. PIC-328202 PV is on the drum (2.6 bar a), not the column (3.5 bar a)

`main.py:5627` feeds `s.a328_d001_P`. Doc line 5: "PIC-328202 indicates and controls pressure in
328C002". The valve location the code models (PV-328202 on the 786 vent) is right; the transmitter
node is off by exactly one exchanger ΔP — and the code already reconstructs the column node at
`main.py:5637` by adding `R328_E004_DP` (0.9 bar) back on.

## B6. TT-328011 aliased to the 328C003 3rd-tray field

`frontend/overlays.js:347` binds TT-328011 to `C003.TT_328012`, which `main.py:6386` fills from the
constant `R328_C003_T746` = 190 °C. Doc line 17 puts TT-328011 on stream 748 (**188 °C**), and
`R328_C002_T748 = 188.0` already exists at `main.py:1087`.

## B7. Stream 741 returns to Comp I; the doc says the 2nd compartment

`main.py:5484` adds `m_741` to `in_compI`. Doc line 33: "recycled back to 2nd compartment of
328D003". PFD 741 = 0 kg/h so the PFD cannot adjudicate, and both compartment balances close either
way at design. Off-design it matters: `S741_CAP_KGH = 33724` (`main.py:1408`), so full stroke
injects up to 33.7 t/h of 40 °C water into a 34.2 t/h Comp-I inventory and halves the 735 feed
concentration to the desorber.

## B8. PT-324201 and PT-324204 are not published

`main.py:6501` publishes the 324F001 vacuum as `PT_324202`; `main.py:6530` publishes the 324F003
vacuum as `PT_324203`. The doc separates them (lines 11, 14, 20, 24): PT-324201/PT-324204 are the
**separator** transmitters, PIC-324202/PIC-324203 the **condenser-shell** controllers.
The underlying physics is right — PY-324201 and AY-324701 are both implemented and each takes the
correct (T, P) pair (`main.py:6507`, `main.py:6539`). Only the published tag names are wrong.

## B9. Stream 722 → 328V001 does not exist

`main.py:5976` computes `m_324_vent` and `main.py:6564` labels it "→ atm". The only 328V001 node in
the code is a liquid pass-through (`main.py:5446,5453`) with no gas inlet from unit 324.
PFD_21 stream 722 = 31 kg/h, 55 °C, 54.44 % N2 / 14.33 % CO2 / 1.66 % NH3. Stack emission telemetry
therefore omits the whole unit-324 contribution.

## B10. Stream 759 missing from the 328D003 Comp-I inlets

`main.py:1041` enumerates only 719 + 720 + 721; `main.py:5484` and the `P_compI` sum at 5489-5493
follow. PFD_21 759 = 190 kg/h at **55 °C** — the hottest of the four condensates. It is also missing
from the `A328_D003_TI` back-solve denominator at `main.py:1420`, so the 56 °C Comp-I anchor is
fitted on an incomplete inlet set. 324E007 closes exactly: 717 (221) = 759 (190) + 722 (31).

## B11. 323P003 A/B has no pump object

`AUX_PUMPS` (`main.py:6875`) omits it; `m_324` (`main.py:5311`) is a pure function of the FV-324401
stroke with no pump gate — unlike `m_755`, which does gate on 322P002 (`main.py:5499`). The code's
own comment at `main.py:5269` asserts the dependency it does not implement.

---

# C. Mathematical, thermodynamic and connectivity defects

## C1. `P_c002` and `P_c004` are algebraically ZERO on the energy branch [V] — CRITICAL

```
main.py:1097  R328_C002_LAM737 = (SENS + m748·LAM748/3600 + m750·LAM750/3600) / (m737_DES/3600)
main.py:1961  R328_C002_Q_DES  = (SENS + m748·LAM748/3600 + m750·LAM750/3600)
```
so `LAM737 ≡ Q_DES / (m737_DES/3600)`. The runtime then does

```
main.py:5522  m_737  = min( M737_DES·(in/IN_DES),  M737_DES·(q_c002/Q_DES) )
main.py:5524  P_c002 = q_c002 − m_737/3600·LAM737
```

On the energy branch, substituting:
`m_737/3600·LAM737 = [M737_DES·(q/Q_DES)/3600] · [Q_DES/(M737_DES/3600)] = q_c002` → **P_c002 ≡ 0**.

`main.py:1138-1140` vs `main.py:1964-1966` give 328C004 the identical structure → **P_c004 ≡ 0**.

Consequence: the two OTS malfunctions that matter most in unit 328 — loss of MP/LP stripping steam,
loss of the 748/750 hot recycles — move the column temperature by exactly zero. The response is
one-sided: the throughput branch (`in/IN_DES`) does give a non-zero `P`, so the columns can heat but
cannot cool.

Fix: break the cancellation. Either drive the overhead from a pressure/VLE boil-up (K-value flash on
the live `w_328c002`) instead of `M737_DES·(q/Q_DES)`, or keep a split-fraction `m_737` and let
`q − m_737·λ` float. Any formulation where λ is **not** defined as `Q_DES/(m_vap_DES/3600)` while
`m_vap` is simultaneously `m_vap_DES·(q/Q_DES)` restores dT/dt.

## C2. Evaporation → desorption recycle loop is OPEN [V] — CRITICAL

`main.py:5975` computes `m_324_cond = v1_m + v2_m`; grep shows it is consumed **only** by
`main.py:6563` (a telemetry string). Meanwhile

```
main.py:5484  in_compI = A328_D003_M719 + A328_D003_M720 + A328_D003_M721 + bot_c005 + m_741
main.py:1068  A328_D003_M719 = 26768.0 ;  M720 = 2758.0 ;  M721 = 1763.0     # frozen
```

So 16.8 t/h of live process water is created and discarded, while 31.3 t/h is injected into 328D003
from constants that cannot move. Off-design, a change in evaporation load never reaches
328D003 → 735 → 738 → 328C002. Total mass is not conserved across the 324/328 boundary.

## C3. 324F001 holdup cannot move [V] — CRITICAL

```
main.py:5869  p1_m = max(feed1_m − v1_m, 0.0)
main.py:5875  m_p1 = p1_m
main.py:5876  s.r324_f001_M = max(M_pre + (feed1_m − v1_m − m_p1)/3600·dt, 1.0)
```
`v1_m` is clamped to ≤ `feed1_m` (line 5866), so the `max` never bites and the delta is **exactly 0**
every tick. `LI_324F001` (`main.py:6502`) is pinned at 55.0 % forever, and the same frozen holdup is
the denominator of the Stage-1 temperature ODE at `main.py:5874`. The separator cannot surge, run
dry, or flood; a 324F001 level excursion is untrainable.

Fix: make the barometric leg hydraulic — `m_p1 = f(head, P_F001 − P_F003, leg geometry)`, or
minimally `R324_P1_DES·(M/M_des)^0.5` anchored at the design holdup.

## C4. Unit-328 latent heats differ per vessel — **the "+413 kW created" conclusion is WITHDRAWN**

*The λ arithmetic is exact and was re-verified by hand: `LAM737 = 1879.34`, `LAM748(C003) = 1377.97`,
`LAM750(C004) = 2130.04`, `LAM737(D001) = 2163.55`, mismatches +140.30 / −57.02 / +526.2 kW, total
+609.5 kW. Every figure matches the auditor to the last digit.*

**But the conclusion drawn from it does not survive.** Two independent problems:

**1. The envelope check that "confirmed" it had a boundary slip.** A live diagnostic was added
(`ABSORB_328.D003.Q328_*`) over the envelope {328C002, 328C003, 328C004, 328D001, 328E021, 328E007},
reference 0 °C. It reads at design:

```
in 6653.8 kW   out 8344.2 kW   residual −1690.5 kW
```

The **out** side reproduces the auditor's 8344.3 kW exactly. The **in** side does not — the auditor
reported 7931.3 kW, about 1277 kW high, because the feed was taken at 56 °C (before 328E007) while
the export was taken at 89 °C (after it), crediting the 2005 kW interchanger recovery to the inlet
without ever debiting it. With a consistent boundary the residual is not +413 kW of energy created;
it is **−1690 kW**, the opposite sign.

**2. Unit 328 is not a non-reacting envelope, and both arguments treated it as one.** The columns
strip NH₃ and CO₂ out of solution (carbamate decomposition, endothermic); 328D001 re-absorbs them
(carbamate formation, exothermic). Stream 737 alone delivers **39.46 kmol/h of CO₂** into the drum
liquid — at a realistic −100 to −130 kJ/mol that is **1096 to 1425 kW** of genuine reaction
enthalpy. The +526 kW λ737 gap sits comfortably inside it.

So **two different λ for one stream is correct physics here, not a bug**: in 328C002 λ737 is a
*boil-up* latent (vaporise water, strip dissolved gas); in 328D001 it is *condensation plus
carbamate formation*, which must be larger. Applying the auditor's prescribed fix — force the λ
equal — would delete a ~500 kW carbamate exotherm and run the drum cold.

### What the real defect is

The same one finding C9 names for the hydrolyser: **the reaction enthalpy is hidden inside a
back-solved latent instead of being an explicit ξ·ΔH term**, so it scales with whatever drives that
stream's flow rather than with the actual reaction extent. Off-design the enthalpy books are
therefore biased, even though the design point is exact.

The fix is the same shape as C9's: pull ξ·ΔH out into an explicit term driven by the live
absorption/decomposition extent (the species layer already tracks the NH₃/CO₂ vectors needed), then
re-back-solve each λ against the residual. The diagnostic above is the check — it should trend
toward the reaction enthalpy the species layer computes, not toward zero.

*This is the second finding whose symptom was real and whose prescribed cure was wrong (C1 was the
first). Both errors share a cause: the fixes were written without the reaction chemistry in view.
That is consistent with the adversarial-refutation pass never having run.*

Each λ was back-solved per vessel, so every shared stream carries two different values:

| stream | generated at | condensed at | error |
|---|---|---|---|
| 748 | `LAM748` = 1377.97 (C003, `main.py:1121`) | `R328_C002_LAM748` = 2000.0 (`main.py:1090`) | +140.30 kW |
| 750 | `R328_C004_LAM750` = 2130.04 (`main.py:1138`) | `R328_C002_LAM750` = 2100.0 | −57.02 kW |
| 737 | `R328_C002_LAM737` = 1879.34 (`main.py:1097`) | `R328_D001_LAM737` = 2163.57 (`main.py:1291`) | +526.22 kW |

Sum +609.50 kW. Frozen node temperatures (`R328_C002_T748` 188 vs bulk 200; `T750` 140 vs 143;
`T_TOP` 117 vs 139) destroy 196.53 kW. **Net +412.98 kW created.** An independent envelope check
(ref 0 °C, cp 4.0) gives out − in = +413.0 kW — the two methods agree to 0.02 kW. Total steam into
unit 328 is 4539.7 kW, so the model manufactures **9.1 %** of its own heat input.

## C5. The 324 vacuum ODEs are open integrators — CRITICAL

```
main.py:5893  ejpull_live   = R324_F001_EJPULL_DES · (mot9605_m / R324_F002_MOTIVE_DES)
main.py:5895  s.r324_f001_P = clamp(P + K·((v1_m + fa202_m) − ejpull_live)/3600·dt, 0.05, 1.0)
```
No term on the right depends on `s.r324_f001_P`: `v1_m` is evaluated at the **constant** design
vacuum (`main.py:5864`, `R324_F001_P_BARA`), `fa202_m` is a stroke, `ejpull_live` is motive steam
only. Same at `main.py:5952-5956` for 324F003. By contrast 323F010 **does** carry the roll-off
(`main.py:5257`: `… · (s.r323_f010_P / R323_F010_P_BARA) · …`).

Shut HIC-329605 → net 14323 kg/h → dP/dt = 0.02 × 3.978 = 0.0796 bar/s → 324F001 ramps 0.33 → the
1.0 bar clamp in 8.4 s and stays pinned. With PIC-324202 in MAN (a normal operator action) any
imbalance ramps linearly to a clamp; the node has no fixed point except the design tie.

Fix (minimum): multiply `ejpull_live` and `ejpull2_live` by `(P_live / P_des)` — anchored, so the
design seed stays bit-exact.

## C6. Biuret's urea consumption is cancelled at both evaporator stages [V]

The kinetic is genuine (`sol_biuret_xi`, `main.py:1770-1781`, Ea = 85 kJ/mol, 2nd order) and the
sink is applied correctly inside `sol_advance` (`main.py:1793`). It is then overwritten:

```
main.py:5870  w1_live  = clamp(urea1_in / max(p1_m, 1e-6), 0.0, 1.0)     # no reaction term
main.py:5886  s.w_e001 = sol_pin_strength(sol_advance(…), w1_live)
main.py:2138  out["Urea"] = clamp(w_urea_auth, 0.0, share)               # urea forced back
```
ξ_E001 = 1.4868 kmol/h → 178.6 kg/h of urea; ξ_E003 = 0.9959 → 119.6 kg/h. Honouring the reaction
gives w1 = 0.94083 vs the pinned 0.94310 — 0.227 pp of urea fabricated, permanently, and Σw = 1 is
restored by deleting the mass from **water**. At 160 °C the E003 Arrhenius factor is 3.13, so
375 kg/h should be consumed and the model consumes 0: an overheated melt shows rising biuret with no
urea penalty and a spuriously drier product.

## C7. The clip residual is computed, returned, and never read [V]

`main.py:1728` computes `resid`, `main.py:1738` returns it. Grep: **no caller reads it** — no
telemetry, no assertion. This contradicts the function's own docstring at `main.py:1717`
("The clip residual is reported, never hidden"). Recomputed: `SOL_E001['resid']` = −170.1 kg/h
(1.21 % of `R324_V1_DES`), `SOL_E003['resid']` = −126.8 kg/h (**4.63 %** of `R324_V2_DES`) — against
the same docstring's claim that everywhere else it is under 0.4 %.

## C8. LV-328504 flash absent — +337.7 kW of the wrong sign

`main.py:5583` `m_749 = m_747`; `main.py:5608` charges all 34062 kg/h as liquid at ~148 °C:
`34062/3600·4.0·(148−143) = +189.23 kW` **into** the column.
Per the PFD only 33413 kg/h of 139 °C liquid enters a 143 °C sump:
`33413/3600·4.0·(139−143) = −148.50 kW` **out**. Error **+337.74 kW** = 8.76 % of the 3853.7 kW LP
duty, wrong sign. `R328_C004_Q_DES` absorbs it as a −27 kJ/kg bias in λ750.
Composition: 780 is 8.44 mol% NH3 → 52.0 kg/h of NH3 (15.7 % of the 330.4 kg/h arriving in 749)
bypasses the trays on the plant; `main.py:5619-5621` routes 100 % of it through `des_advance`.

## C9. 328C003 hydrolysis endotherm is not on the reaction extent

`main.py:5567-5568`: `P_c003 = sens_c003 + m_911·ΔH/3600 − m_748·LAM748/3600` — no ξ·ΔH_rxn term.
The extent **is** computed one line earlier (`main.py:5557`) and passed only to the species layer and
to `gen748`. The comment at `main.py:1104-1106` states the lumping is deliberate
("λ748_gen … lumps the reaction endotherm and is back-solved so M·cp·dT/dt = 0 at design"), and the
design point is therefore exact. The defect is the **coupling**, not the anchor: because the endotherm
rides on `m_748 = M748_DES·(pic203b_op / PV_OP_DES)`, it scales with the **PV-328203 valve stroke**
instead of with ξ. Doubling the urea handed to the hydrolyser adds up to 142 kW of unmodelled
cooling and produces no temperature response; stroking PV-328203 changes the "reaction heat" with no
reaction change. ΔH: +30.6 kJ/mol aqueous → 36.3 kW; +119.7 kJ/mol gaseous → 142.1 kW, against a
328C003 net of 310.8 kW.

## C10. 328E007 is not modelled at all

`main.py:1441-1443` defines `R328_E007_EPS = 0.6667`, `R328_E007_LOSS = 18.3`,
`R328_E007_TC_OUT = 114.0`, `R328_E007_TH_OUT = 89.0`. Grep: `EPS` and `LOSS` are **dead**; the two
temperatures are used only in telemetry (6419, 6432). The 738 feed enthalpy uses the frozen
`R328_C002_T738 = 114.0` (`main.py:1087` → `main.py:5511`), while the hot side `s.a328_c004_T` is a
live state.

The constants are a correct, PFD-verified ε-model that was simply never wired in:
cold 31114/3600·4.0·(114−56) = 2005.1 kW; hot 33724/3600·4.0·(143−89) = 2023.4 kW;
difference = 18.3 kW = `R328_E007_LOSS` exactly; ε = (114−56)/(143−56) = 0.6667 exactly.

Consequence: a 328C004 steam trip still delivers 31114 kg/h at exactly 114 °C to 328C002, and
TT-328006 still reads 89 °C.

## C11. 328E021 uses a frozen effectiveness

`main.py:1432` `R328_E021_EPS_T = 51/61 = 0.83607`, used live at `main.py:5542`. No U, A or ΔT_lm.
Back-solving UA from that ε: C_cold = 37.52, C_hot = 37.85 kW/K, Cr = 0.9914, NTU = 4.991,
**UA = 187.3 kW/K**. Holding UA and re-evaluating: at 50 % flow ε = 0.9125 → T_746 = 194.7 °C
(model 190.0, **+4.7 K**); at 130 % ε = 0.7961 → 187.6 °C (**−2.4 K**). ε must rise on turndown; a
frozen ε makes the hydrolyser feed temperature — the sole input to the Arrhenius conversion at
`main.py:5551` — track the wrong way with load.

## C12. 328E004 duty is linear in valve stroke

`main.py:5644` `Q_e004 = R328_E004_Q_DES_KW · (tic002_op / R328_E004_TV_OP_DES)` — no ΔT, no CW flow,
no CW temperature, no dependence on the live vapour load. Implied UA at design (61 °C drum, ~35 °C
CW) = 4357/26 = 167.6 kW/K; at a 45 °C drum the true duty is 1676 kW but the model still delivers
4357 kW — **2.6×**. At 100 % stroke it delivers 8714 kW, more than the entire vapour load can release
(m_737·λ = 4005.6 kW), so the drum can be driven arbitrarily cold.

## C13. 328D001 pressure ODE has no condensation sink

`main.py:5629` `gen786 = R328_D001_M786_DES · (m_737 / R328_D001_M737_DES)` — generation depends only
on the incoming vapour rate. `Q_e004` appears in `P_d001` (`main.py:5647`) but **never** in the
pressure ODE (`main.py:5648`). With TIC-328002 shut, the true uncondensed source is the full
6665 kg/h but `gen786` stays at 276 — understated 24×. Physical ramp
0.05·(6665−276)/3600 = **0.089 bar/s**; model gives 0.000. Temperature does respond
(+4357 kW → 0.103 K/s), so the model shows a runaway drum temperature at perfectly constant
pressure. "Lose CW to the reflux condenser" is unrepresentable.

## C14. Stream 790 is omitted from the 324E002-shell node the code itself aliases [V]

`main.py:6526` declares `"P_324E002_sh" = s.r324_f001_P` — one node. But that node's balance
(`main.py:5895`) loads only `v1_m + fa202_m`. The 323F010 vapour `m_evap` is never added, and its own
node (`main.py:5257-5260`) discharges to nowhere. PFD: stream 703 = 705 + 790 = 14799 + 12040, so
**790 is 44.9 % of the shell load**. Code design load = 14322 kg/h against a true 26840 kg/h, and
`R324_F001_EJPULL_DES` (`main.py:1530`) is sized for less than half of what it carries. Raising
TIC-323012 loads the same ejector on the plant; in the model the two nodes are fully decoupled.

## C15. False air 250 / 120 kg/h vs PFD 21 / 21 kg/h [V]

`main.py:1528` `R324_F001_FA_DES = 250.0`; `main.py:1577` `R324_F003_FA_DES = 120.0`.
PFD_21 streams 783 and 784 are both Air, **21 kg/h**, 0.73 kmol/h, 32 °C, 1 bar a — **11.9×** and
**5.7×**. These are the manipulated variables of PIC-324202/PIC-324203, so both loops carry ~12× and
~6× the true process gain, and the published vent (`m_324_vent` = 370 kg/h) is 12× the PFD's stream
722 (31 kg/h).

## C16. 324F002 motive steam 650 kg/h vs PFD 924 = 390 kg/h [V]

`main.py:1553` sources 650 from an ejector datasheet ("324-1 ED-2"), not the PFD. PFD_21 stream 924 =
390 kg/h, and the licensor's own closure confirms it: 706 (72) + 924 (390) = 462 = stream 708, exact.
Under the project rule (PFD strictly overrides coded constants) the PFD value wins; if the datasheet
is believed instead, the 708 closure has to be re-explained. The pull is anchored as a ratio
(`main.py:5893`), so correcting it does not move the design fixed point.

## C17. 324F004 / 324F005 motive steam is not modelled

`main.py:5952` uses HIC-329606 as a pure dimensionless gain; there is no mass term analogous to
`mot9605_m`, and no `R324_F004_MOTIVE_DES` / `R324_F005_MOTIVE_DES`. PFD_21: 927 = 1220 kg/h,
929 = 180 kg/h, both confirmed by closures (712 + 927 = 714; 715 + 929 = 717). That **1400 kg/h**
condenses into 721 and 759 — the model creates neither the steam nor its latent load.

## C18. 324E001 feed temperature frozen at 99 °C

`main.py:1491` `R324_FEED_T_C = R323_F010_T_SP_C`, used in the live energy balance at `main.py:5871`.
The tank temperature is a live ODE state 300 lines earlier (`main.py:5338-5339`) carrying — by the
code's own comment at `main.py:5331` — a **LOW-temperature alarm**. The same line 5871 already reads
the live composition and live melt temperature; only the feed temperature is pinned.
A 10 K tank cooldown withholds 644 kW = 6.1 % of `R324_E001_Q_DES_KW`, i.e. 1067 kg/h less water
evaporated, taking the Stage-1 melt from 94.31 % to 93.05 % urea. The model moves none of it.

## C19. Three mutually inconsistent urea-water VLE relations

- A: `bubble_T_raoult` (`main.py:1655-1680`) → `tsat_steam(P / x_water_mol(w))`, used at
  `main.py:5236` for 323F010.
- B: `_fahmy_Cu` (`main.py:102-119`) → `xw = 1.06425·(0.95·Pv/Pw)^0.92498`, wrapped by `evap_w_eq`
  and used at `main.py:5864`, `5922` for 324E001/E003.
- C: frozen-γ Raoult (`main.py:90-97`) for the PY-324201 / AY-324701 soft sensors.

At 99 °C / 0.46 bar a: Raoult inverts to 79.14 % urea, Fahmy to 73.53 % — **5.6 pp** apart, putting
the PFD's 80.00 % stream-317 melt on opposite sides of the boiling boundary. At 130 °C / 0.33 bar a
the PFD's 94.31 % melt boils at 123.67 °C (Raoult) vs 133.88 °C (Fahmy) — **10.2 °C** apart.
Mitigation: all three are used in anchored-departure form, so the design point is bit-exact and the
slopes agree within 20 %. But no single equation of state can be checked across the train, and the
323D002 → 324E001 junction is thermodynamically inconsistent.

## C20. No activity coefficient / boiling-point-rise model

`bubble_T_raoult` assumes γ_H2O = 1 in a 94-98 % urea melt at 0.13-0.33 bar a. Its own docstring
tabulates the errors: +1.3 °C (323F010), **−6.3 °C** (324E001), **−7.3 °C** (324E003). At 324E001 the
−6.33 °C converts to +1.66 pp of urea, i.e. 1361 kg/h more water evaporated = 9.7 % of `R324_V1_DES`
= 822 kW of latent duty. `main.py:115` folds activity into a fitted exponent with **no composition
argument** — a curve fit, not a γ model.

## C21. Frozen back-solved UA, no LMTD, no fouling or flooding coupling

`main.py:1520` `R324_E001_UA_KW = Q_DES/(tsat(p_chest) − T_sp)` = 776.7 kW/K; `main.py:1570` 600.8
(on a **3.51 K** design driving force); `main.py:971` 419.3 for 323E010. The flooding state is fully
integrated (`main.py:5902-5906`, `s.r324_e001_cond_M`) and grep shows it **never enters**
`Q_e001_kw`. Shutting LV-329505 floods the shell and changes the duty by zero watts, so the
"flooded exchanger" scenario the code went to the trouble of instrumenting is untrainable. There is
no U and no A anywhere in the evaporation train, only their product frozen at one point.

## C22. LP steam header frozen at 4.4 bar while a live header state of the same value exists

`main.py:864` `R323_P_STEAM_SUP = 4.4` builds every chest pressure (5111, 5218, 5840, 5916). The live
header is `s.steam.P_LP` (`main.py:3866`, `HPCC_STEAM_P_BARA = 4.4`), published at `main.py:6583` and
used live elsewhere (`main.py:4692`). The train's design draw is 5858 + 7249 + 10495 + 2111 =
25713 kW = **43.4 t/h of LP steam**, and nothing subtracts it from `s.steam.P_LP`.
A 4.4 → 4.0 bar sag would take 324E003 to **2.9 %** of design duty (its design driving force is only
tsat(3.96) − 140 = 3.51 K); the model shows nothing.

## C23. No ejector entrainment physics

`R324_F001_EJPULL_DES` = 14323.1 kg/h against `R324_F002_MOTIVE_DES` = 650 → **22:1**. The same
HIC-329605 is also the sole motive lever for the 323F010 pull (`main.py:5257`), which adds
`R323_MEVAP_DES` = 12013.3 → **40:1**. A single-stage steam-jet ejector at a compression ratio of ~3
achieves well under 1 kg/kg. Root cause is C2/C24: on the plant the condensers take the condensable
load and the ejector lifts only the non-condensables. No motive pressure, area ratio, compression
ratio or break point exists anywhere, so "ejector broke / vacuum lost" is unreachable.

## C24. The vacuum condenser train has no model

`main.py:5969-5976` is the whole thing: a comment, `m_324_cond = v1_m + v2_m`,
`m_324_vent = fa202_m + fa203_m`. Shell pressure is reported as identically the separator pressure
with zero ΔP (`main.py:6526`, `6548`). Compare the LPCC in the same file, which **does** carry a
driving force (`main.py:5724`, `5782`). Consequences: no cooling-water lever anywhere in the vacuum
section; a fouled or CW-starved condenser cannot be represented; no partial-pressure driving force,
so air in-leakage degrades vacuum only through the linear false-air term, not through the loss of
condensing surface it actually causes.

## C25. `des_alpha_live` has no pressure dependence

`main.py:2014-2027` — no pressure argument. Base alphas are lumped back-solves, not K-values:
α_NH3 = 132.70 / α_CO2 = 584.05 (C002); α_NH3 = 50852.7 (C004) against a real Henry's-law K near 10,
which `main.py:1971` concedes. `K_inf = 9.5` is documented at `main.py:152` as the **Desorber-II**
value at 143 °C, yet `main.py:2009` applies the same `K_inf` to 328C002 at 139 °C. For a stripper
K = γ·Psat/P, so halving the 328C002 top pressure should roughly double the stripping factor; the
model gives exactly 0 change. The NH3-derived stripping factor is also applied to CO2, which in this
liquor is chemically bound as carbamate.
The Kremser residual itself **is** bounded and monotone (`main.py:167-172`, r ∈ (0,1] for S > 0) — the
1e-6/1e6 clamps are anti-overflow only.

## C26. Hydrolysis kinetics: irreversible, no product inhibition, no pressure, holdup ignored

`main.py:2108-2115` — signature `(T_c, m_746)`; `m_911`, pressure, water activity and the NH3/CO2
already in solution appear nowhere. `R328_AI701_KEFF_UREA` is back-fitted to the 1 ppm guarantee
(`main.py:156`), not a sourced pre-exponential; `Ea = 72000` is marked "(literature)" with no
citation. k·τ = 10.14 → X = 0.99996. **Setting FIC-329402 to zero leaves X at 0.99996** — the model
still destroys 256.6 kg/h of urea with no stripping steam at all. τ is scaled off
`R328_C003_M746_DES/m_746`, not off the live `s.a328_c003_M`: at 80 % level the true τ is 5810 s
(+60 %) and `tau_live` is unchanged. The `clamp` to [0,1] is present and correct.

## C27. `des_advance` renormalisation hides the component residual

`main.py:2053-2064`: the implicit solve uses a **per-species** `sink`, so Σ out ≠ M_new in general,
then `w_new = out[k]/tot` throws the difference away. Measured (C002 alphas, M = 1588 kg, dt = 0.25):
design seed −2.8e-9 kg (exact); recycles ×1.15 → +168.4 kg/h; ×1.50 → **+581.6 kg/h** (1.4 % of
throughput); ×2.00 → +1218.5 kg/h. Secondary: `main.py:2050` uses `M = max(M_new, 1.0)` for **both**
the accumulation term (which should use M_old) and the sink denominator, so during a level ramp the
old inventory is rescaled before the step.
Related: `_des_stage_anchor` computes `resid` (`main.py:1925`) and returns it (`main.py:1936`); no
caller reads it.

## C28. No recycle convergence anywhere [V]

Tears are written at `main.py:5793-5802` (`s.tlag["R328_748"]`, `["R328_750"]`, `["R328_775"]`,
`["R3232_718A"]`, `["R328_M931"]`, `["R328_739"]`, …) and read at the top of the next tick
(`main.py:5440-5444`). That is a one-step **Jacobi** update. There is no iteration loop, no residual
norm and no convergence test anywhere in `step_sim`. The steady state is a fixed point of a lagged
map, not a simultaneous solution — which conflicts with the tearing-to-convergence requirement in
`CLAUDE.md §Flowsheet Propagation`. There is also no `Stream` object and no `is_dirty` mechanism:
streams are bare float locals (`m_743`, `T_749`, `w_328c002`).

## C29. Pressure gains are tuned constants; no momentum terms in 328

`R328_C003_P_KP = 0.02` (`main.py:1117`) and `R328_D001_P_KP = 0.05` (`main.py:1281`). Dimensional
test against dP/dt = R·T/(MW·V)·ṁ: for 328C003 (473.15 K, MW 21.36) KP = 0.02 implies **92.1 m³** of
vapour space against a 37.9 m³ liquid inventory in a liquid-filled column; for 328D001 (334.15 K,
MW 17.26) KP = 0.05 implies **32.2 m³** against a whole vessel of 19.1 m³.
The datasheet tray geometry (`main.py:1174-1177`, 3125 holes × 6 mm, weir 40 mm) is consumed only by
`_r328_holdup`. The 328C002 → 328D001 drop is the frozen `R328_E004_DP` = 0.9 bar. There is no
`a328_c002_P` and no `a328_c004_P` state at all: 328C002's pressure exists only as
`s.a328_d001_P + 0.9` inside the TIC-328008 inferential, and 328C004 has no pressure.

## C30. No momentum or pressure-drop terms in 323/324

Every liquid flow is a linear stroke gain: `m_314` (5153), `m_319` (5191), `m_324` (5311), `m_fwd`
(5938) — no ΔP, no Cv, no valve characteristic. The same file **does** model valves properly
elsewhere (`main.py:3512`: equal-% trim × √(ΔP ratio)). 324F001 drains to 324F003 across
0.33 → 0.131 bar a and `m_p1` is independent of both. 323P003 has no head/flow curve and no NPSH.

## C31. TIC-328008 inferential is live on pressure only

`main.py:5635-5637` uses `psat_water_bara(R328_C002_T_TOP)` — a module constant. Grep shows no
328C002 top-temperature state exists; only the bottoms `s.a328_c002_T` is live. Doc line 46
specifies **two** inputs (TT-328008 and PIC-328202); one is implemented.
Sensitivity: psat(117) = 1.8004, psat(120) = 1.9854 → a 3 °C move swings the PV by 4.75 mol%, roughly
**twice** the entire reachable SP band (`main.py:4315`, sp 44.9-47.2).

## C32. TIC-328012 differential leg is frozen

`main.py:5985` `_ctrl_ipd(s.TIC_328012, s.a328_c003_T − R328_C003_T746, dt)` — a differential
controller with one constant leg is a bottoms-temperature controller with a −190 offset. A live
value for that node already exists and is already published as TT-328009 (`main.py:5542`, `6387`),
yet `main.py:6386` publishes `TT_328012` from the frozen constant.

---

# CLEAN — checked and found correct

- **328C002 / 328C003 / 328C004 mass balances** close exactly against PFD_22:
  C002 in 738 + 748 + 750 + 775 = 40434 = out 737 + 743;
  C003 in 746 + 911 = 34874 = out 748 + 747;
  C004 in 749 + 931 = 40557 = out 750 + 739.
- **PFD_21 condenser/ejector train closes to 0-1 kg/h** at every node
  (703 = 705 + 790; 703 = 719 + 706; 706 + 924 = 708; 709 = 720 + 712; 712 + 927 = 714;
  714 = 721 + 715; 715 + 929 = 717; 717 = 759 + 722).
- **MP / LP steam enthalpy anchors are right, superheat included.** [V]
  `R328_C003_M911_DH` = 2235 kJ/kg vs h(325 °C, 16.6 bar) − h_f(200 °C) ≈ 3085 − 852 = 2233.
  `R328_C004_M931_DH` = 2136 vs h_g(3.9 bar) − h_f(143 °C) ≈ 2739 − 602 = 2137.
- **LIC-328503 → 328C002 bottoms → 743** binds correctly (`main.py:5509-5510`).
- **PY-324201 and AY-324701 are both implemented with the correct (T, P) pairs** —
  `main.py:6507` uses `s.r324_e001_T` + `s.r324_f001_P`; `main.py:6539` uses `s.r324_e003_T` +
  `s.r324_f003_P`. Only the published tag names are wrong (see B8).
- **323F004 bottom drain is LV-323505, matching the doc** — `main.py:5190` drives `m_319` off
  `LIC_323505`; `LIC-323501` correctly drives the 323C003 drain (stream 314). The premise that the
  code binds LV-323501 here is false.
- **PV-324202 binds to 324F001 and PV-324203 to 324F003** in the code (`main.py:4013`), which is the
  physically correct placement — the mapping doc is the artefact in error (see A3).
- **Stream 331 (granulation return) does join 319 ahead of 323E010** (`main.py:905-908`).
- **The Kremser residual `_kremser_resid` is bounded and monotone** for S > 0.
- **`hydrolysis_x_328c003` clamps conversion to [0,1]** correctly.
- **328E021 hot-side outlet uses a conservation closure, not a second independent effectiveness**
  (`main.py:5593`), and is pinch-bounded by the two live inlet temperatures.
- **The 718A/718B split conserves the LIC-323503 total draw** and the setpoint feed-forward
  decoupling at `main.py:5762-5774` is sound.
