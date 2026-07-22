# Technical Debt Log

Tracked, non-blocking discrepancies. Each item is asserted in the audit suite as an
`XFAIL` (recorded, does not fail the run) so the gap stays visible without going green-by-deletion.

---

## TD-001 — `phi_sp` ejector-spindle helper encodes the SUPERSEDED positive law

- **Status:** OPEN (tracked XFAIL)
- **Opened:** 2026-06-26 (Phase 2, Path B — Option 1 tear closure, `ov_CO2 = 458.358305`)
- **Files:**
  - `backend/tests/audit_f001_ejector.py` — helper `phi_sp` (def) + sweep assertion (`xchk`, was `chk`)
  - `backend/main.py:140-146` — authoritative spindle law (model side)

### Discrepancy

The audit helper still implements the **positive** spindle law (opening the spindle ⇒ more suction):

$$\phi_{sp}^{\text{helper}}(\theta) = R^{\frac{\theta - \theta_{des}}{100}}, \qquad R = 2.1517,\ \theta_{des} = 74$$

The model (`main.py:140-146`) implements the corrected **negative** law. The HV-322602 NH3 nozzle is fed
by the 321P002 A/B **positive-displacement triplex pumps**, so the motive **mass** flow is fixed by pump
speed, *not* by valve opening. At constant $\dot m$ the jet momentum flux

$$\dot m\, v = \frac{\dot m^{2}}{\rho A}$$

varies **inversely** with the nozzle free area $A$. Closing the spindle (smaller $A$) therefore **raises**
jet momentum and entrainment capacity:

$$\phi_{sp}^{\text{model}}(\theta) = R^{\frac{\theta_{des} - \theta}{100}}$$

Helper and model are reciprocals:

$$\phi_{sp}^{\text{helper}}(\theta)\,\cdot\,\phi_{sp}^{\text{model}}(\theta) = 1$$

so the model-vs-helper opening sweep (`ejp(1.0, opn).suction_kgh / EJ_SUC_TOT_DES` vs `phi_sp(opn)`)
fails by construction for every $\theta \neq \theta_{des}$.

### Why deferred (not fixed)

Out of Option-1 (tear-closure) scope. Per directive: *"Leave phi_sp alone."* The model is correct;
only the **test helper** is stale. Fixing now would mix an unrelated test refactor into the reconciliation
commit.

### Fix when scheduled

Re-derive the helper to the negative law, i.e. flip the exponent sign:

```python
def phi_sp(opn):  return EJ_SPINDLE_R ** ((EJ_OPEN_DES - clamp(opn,10.0,100.0))/100.0)
```

Then re-point the helper-internal monotonicity/datasheet-anchor assertions (currently asserting the
positive direction) and promote the sweep `xchk` back to `chk`.

---

## TD-002 — three `.vol_m3h` faceplates write m3/h into kg/h controllers

- **Status:** RESOLVED 2026-07-21 (see Resolution below)
- **Opened:** 2026-07-21
- **Files:**
  - `frontend/overlays.js:280` — `FIC-323402`, binds `LPCC_3232.E011.FIC_323402.vol_m3h`
  - `frontend/overlays.js:324` — `FIC-328404`, binds `DESORB_328.D001.FIC_328404.vol_m3h`
  - `frontend/overlays.js:329` — `FIC-328406`, binds `ABSORB_328.D003.FIC_328406.vol_m3h`
  - `frontend/app.js:471` — the `.pv` test that selects backend-authoritative mode
  - `backend/main.py` — `self.FIC_323402` / `self.FIC_328404` / `self.FIC_328406` seeds

### Discrepancy

`app.js:471` only treats a loop as backend-authoritative when its bind ends in `.pv`:

```js
const blk = (o.bind && o.bind.endsWith('.pv')) ? gp(window.OTS_LAST||{}, o.bind.slice(0,-3)) : null;
```

A `.vol_m3h` bind therefore falls to the `else` branch, where SP / OP / mode come from
**localStorage**, not the engine. Three consequences, all operator-visible:

1. The faceplate PV reads **m3/h** (correctly labelled `M3/H`), so the operator enters an SP in
   m3/h. `apply()` sends `msg.sp = p` unconverted, and `r323_ctrl_set` writes it to a controller
   whose `sp` is in **kg/h** — `FIC_323402` seeds `R3232_E011_M402_DES` (1534 kg/h, `sp_hi` 6000),
   `FIC_328404` seeds `R328_D001_M775_DES` (1675 kg/h, `sp_hi` 4000). Entering the true 1.7 m3/h
   sets `sp = 1.7 kg/h` and the leg collapses to roughly zero flow.
2. `bAuto.onclick` does `sp.value = curPV` for a "bumpless" MAN -> AUTO transfer. `curPV` is the
   m3/h value, so this injects the same unit error on a plain mode click, with no SP typed.
3. The mode shown is `st.mode || 'AUTO'`, fabricated from localStorage. `FIC_328404` is seeded
   `CAS`, so a SET silently sends `AUTO` and drops it out of cascade; `FIC_328406` is pinned `MAN`
   as an idle spare but the faceplate presents it as `AUTO` with a blank SP.

`FI-328404` (`overlays.js:291`) shares the `.vol_m3h` bind but carries no `mode` key, so it is a
read-only indicator and is NOT affected.

### Why deferred (not fixed)

`FIC-328402` already had this exact defect and was fixed by converting the loop to a genuine
volumetric controller (seeds and `sp_hi` divided by rho, `Kc` multiplied by rho to hold the loop
coefficient, `_fic_flow(rho=...)` still returning kg/h, overlay rebound to `.pv`). Applying the
same conversion to three more loops is a physics-engine change and **the pin gate cannot be run**
— there is no Python interpreter on the current machine. Two commits (`26d35de`, `76b97b7`) are
already on origin ungated; adding three more ungated loops before re-gating would compound that.

### Fix when scheduled

Repeat the `FIC-328402` pattern per loop, on a machine that can run
`scratchpad/regress.py` + `scratchpad/pindiff.py`. The densities are already in `main.py`:

| loop | PFD stream | existing constant |
|---|---|---|
| `FIC-323402` | 791 | `S791_VOL_DES` |
| `FIC-328404` | 775 | `S775_VOL_DES` |
| `FIC-328406` | 755 | `A328_M755_RHO` |

Then rebind each overlay from `.vol_m3h` to `.pv` so `app.js:471` takes the backend-authoritative
branch and the real mode is displayed. Alternatively, harden `app.js:471` to locate the sibling
block for any bind, not just `.pv` — that fixes the fabricated-mode half without touching physics,
but NOT the unit half, which needs the controller to actually run in m3/h.

---

## TD-003 — `FFIC-329401` master gain is orders of magnitude too small to move `FV-329401`

- **Status:** RESOLVED 2026-07-21 (see Resolution below)
- **Opened:** 2026-07-21
- **Files:** `backend/main.py` — `self.FFIC_329401` seed (`Kc: 0.8`)

### Discrepancy

The FFIC-329401 master's PV is a **ratio** of order 0.2, while its OUTPUT is an LP-steam demand in
**kg/h** of order 6495 (`op_hi` 12000). The process gain is therefore

$$g = \frac{\partial\,\text{PV}}{\partial\,\text{op}} = \frac{\partial}{\partial m_{931}}\left(\frac{m_{931}/1000}{V_{744}}\right) = \frac{1}{1000 \times 31.4} = 3.19\times10^{-5}\ \text{T/M3 per kg/h}$$

With `Kc = 0.8` and the loop's `a = dt/(tau+dt) = 0.0196`, the loop coefficient is

$$1 - K_c\,a\,g = 1 - 0.8 \times 0.0196 \times 3.19\times10^{-5} \approx 1 - 5\times10^{-7}$$

i.e. indistinguishable from 1.0. The master is effectively **inert**: moving the ratio SP does not
meaningfully move the FIC-329401 cascade SP, and so does not move the FV-329401 opening on any
useful timescale. To command the full 6495 kg/h span against a ratio error of order 0.2 the gain
needs to be around $6495/0.2 \approx 3\times10^{4}$ kg/h per T/M3, so `Kc` is roughly four to five
orders of magnitude low.

### Not introduced by the T/M3 conversion

Commit `26d35de` changed the ratio's DIMENSION (kg/kg 0.20634 -> T/M3 0.20685) but not its
MAGNITUDE, so `g` moved by a factor of only 1.0025. The old kg/kg basis gave
$g = 1/31478 = 3.18\times10^{-5}$ — the same defect existed before. This is pre-existing tuning
debt, not a regression.

The design fixed point is unaffected either way: at design `ffic_pv == sp`, so `du == 0`, the
LP-steam demand holds 6495 kg/h and the boot pin cannot move. The defect only shows up when an
operator actually moves the ratio SP.

### Fix when scheduled

Retune `Kc` on the same basis the sibling loops use (target loop coefficient roughly 0.25–0.7,
monotone). Needs `scratchpad/regress.py` + `scratchpad/pindiff.py` to confirm the pin is still
`leaves 25 / keys 15 / diffs 0` afterwards — not runnable on the current machine (no Python).

---

## Resolutions — 2026-07-21

**Environment correction that unblocked all of this.** The claim in earlier commit messages and in
`handoff.md` that "there is no Python interpreter on this machine" was **WRONG**. Python 3.14.6 is
installed and works; it is reached as `python3` / `py`, resolved through the
`PythonSoftwareFoundation.PythonManager` MSIX at
`%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe` (the real binary lives under
`%LOCALAPPDATA%\Python\pythoncore-3.14-64\`). The bare `python` alias IS a Store stub and errors —
testing only that one alias, and `where.exe python`, produced the false conclusion. Every
"NOT GATED" note in commits `37504eb`, `26d35de`, `76b97b7` and `c063485` is therefore retracted:
the pin gate was run afterwards against `c063485` and PASSED at `leaves: 25  keys: 15  diffs: 0`.

`pytest` and `httpx` were installed to run the suite. Baseline before any change: **103 passed**.
Run the suite with `-p no:cacheprovider` — `backend/.pytest_cache` has stale directories that
raise `WinError 183`.

### TD-002 — RESOLVED

`FIC-323402` (stream 791) and `FIC-328404` (stream 775) converted to genuine volumetric loops on
the `FIC-328402` / `FIC-323401` pattern: seeds and `sp_hi` divided by rho, `Kc` multiplied by rho so
the loop coefficient `1-Kc*a*g` is unchanged, `_fic_flow(rho=...)` still returning kg/h so the mass
balances are untouched. All three overlays rebound from `.vol_m3h` to `.pv`, so `app.js:471` now
takes the backend-authoritative branch and shows the ENGINE's mode instead of a localStorage guess.

Densities were taken from the PFD's own `Density eff.` row, **not** a mass/volume back-solve:

| stream | loop | kg/h | PFD vol | PFD rho | back-solve | used |
|---|---|---|---|---|---|---|
| 791 | FIC-323402 | 1534 | 1.5 | 992.4 | 1022.7 (+3.0 %) | **992.4** |
| 775 | FIC-328404 | 1675 | 1.5 | 1095 | 1116.7 (+2.0 %) | **1095** |
| 755 | FIC-328406 | 31478 | 31.3 | 1005 | 1005.7 (+0.07 %) | **1005** (unchanged) |

Both 791 and 775 print a 2-significant-figure volume of 1.5 m3/h, so back-solving would have
fabricated a density 2-3 % off the tabulated value. Stream 744 tolerated a back-solve only because
its volume carries 3 figures. Resulting design volumes are 1534/992.4 = 1.546 and 1675/1095 = 1.530,
both of which print as the PFD's 1.5.

Verified: pin gate `leaves: 25  keys: 15  diffs: 0`, suite **103 passed** (no change from baseline).

### TD-003 — RESOLVED

`FFIC-329401` `Kc` raised 0.8 -> 8.0e5, derived rather than guessed:
`g = 1/(1000*S744_VOL_DES) = 3.185e-5 T/M3 per kg/h`, `a = dt/(tau+dt) = 0.1/5.1 = 0.019608`,
so `Kc = 0.5/(a*g) = 8.0e5` places the loop coefficient at 0.500 — inside the 0.46-0.70 band the
sibling flow loops use.

Measured with `scratchpad/probe_ffic_gain.py`, a +5 % ratio SP step (0.206847 -> 0.217189 T/M3):

| | before (Kc 0.8) | after (Kc 8.0e5) |
|---|---|---|
| FV-329401 travel in 600 s | +0.0009 % | **+2.5000 %** |
| FIC-329401 SP | 6495.12 kg/h | **6819.75 kg/h** (= 6495 x 1.05 exactly) |
| ratio PV | 0.206851 (never moved) | **0.217189** (= new SP, zero offset) |

Monotone approach, no ringing, settled by about 300 s. The design fixed point is untouched for any
`Kc` because `pv == sp == pv1 == pv2` gives `du == 0`, so the pin is unaffected — confirmed
`leaves: 25  keys: 15  diffs: 0`, suite **103 passed**.

---

## TD-004 — the `TIC-328008` -> `FIC-328404` cascade is declared but not wired

- **Status:** RESOLVED 2026-07-21 (see Resolutions, part 2)
- **Opened:** 2026-07-21
- **Files:** `backend/main.py` — `self.FIC_328404` seed, its `_fic_flow` call, `_ctrl_ipd(s.TIC_328008, ...)`

### Discrepancy

`FIC-328404` is seeded `"mode": "CAS"` and `R323_CTRL_MODES` offers it `("MAN","AUTO","CAS")`, but
its `_fic_flow` call passes **no** `cas_sp`. `_ctrl_ipd` only overwrites the local setpoint under
`if c["mode"] == "CAS" and cas_sp is not None`, so in CAS the loop simply holds its seeded SP —
it behaves as AUTO. Meanwhile `TIC-328008`'s output is computed every tick and then discarded; it
is routed nowhere, and its own mode tuple is `("MAN","AUTO")` with no CAS.

The stated control narrative is that with `FIC-328404` in CAS the operator sets the SP on the
`TIC-328008` faceplate. That relationship does not exist in the engine today.

For contrast, the cascades that ARE wired (each has a real `cas_sp=` in `step_sim`) are
`PIC-329202`<-`TIC-323007`, `PIC-329208`<-`TIC-323012`, `PIC-329203`<-`TIC-324001`,
`PIC-329212`<-`TIC-324002`, `FIC-324401`<-`LIC-323507`, `FIC-329401`<-`FFIC-329401`,
`FIC-335405`<-`FFIC-335406`.

### Interim mitigation (done)

`app.js` now carries `CAS_MASTER` (the seven wired pairs, which the faceplate names explicitly so
the operator knows which master owns the SP) and `CAS_UNWIRED`, which makes the `FIC-328404`
faceplate state plainly that the cascade is not implemented rather than implying a live master.

### Fix when scheduled

Route `TIC-328008`'s output into the `FIC-328404` `_fic_flow` call as `cas_sp`, add `"CAS"` to
`TIC_328008`'s mode tuple, and pick the master's `op` scaling so that at design the handed-down SP
equals `R328_D001_M775_DES / RHO_775_KGM3` exactly — otherwise the design fixed point moves and the
pin breaks. Needs a re-gate. Confirm the intended pairing against the P&ID first: `TIC-328008`'s PV
is an inferential offgas H2O mol%, which is an unusual master for a carbamate reflux flow.

---

## TD-005 — `FIC-328406`'s PV is its own output, not a flow

- **Status:** RESOLVED 2026-07-21 (see Resolutions, part 2)
- **Opened:** 2026-07-21
- **Files:** `backend/main.py` — `_ctrl_ipd(s.FIC_328406, s.FIC_328406["op"], dt)`, its telemetry block

### Discrepancy

`FIC-328406` is driven as `_ctrl_ipd(s.FIC_328406, s.FIC_328406["op"], dt)` — the controller is fed
its OWN opening as the process variable, so `pv` tracks `op` in **percent**. It never goes through
`_fic_flow`, so there is no flow model behind it. The telemetry then publishes
`vol_m3h = pv / A328_M755_RHO`, which divides a percentage by a density.

Harmless today: the loop is a standby spare pinned `MAN` at 0 (its mode tuple is `("MAN",)`, so the
backend rejects AUTO and CAS), and 0 reads as 0 in any unit. It becomes wrong the moment an operator
moves the opening in MAN — the overlay would display the opening percentage labelled `M3/H`.

### Fix when scheduled

Either drive it through `_fic_flow` against a real design flow for the 755 standby draw so `pv` is a
genuine m3/h measurement, or drop the `vol_m3h` key and relabel the overlay `%` to match what the
value actually is. Confirm from the 322P002 / 328D003 datasheets which is intended.

---

## Resolutions, part 2 — 2026-07-21

### TD-004 — RESOLVED

`TIC-328008` is now the wired MASTER of `FIC-328404`, per the control narrative: with the slave on
CAS, `FV-328404` strokes the 775 carbamate reflux to hold the water content of the gas leaving
328C002 to 328E004 (PFD stream 737).

* The master's OUTPUT is now the slave setpoint in **kg/h** — the `FFIC-329401` convention. This
  matters because `_fic_flow` divides `cas_sp` by rho itself, so a master feeding a volumetric loop
  must still emit MASS. `op` therefore spans the slave's old mass span `0..4000` kg/h instead of
  `0..100 %`, and `Kc` is scaled by that 40x span change (3.0 -> 120.0) to preserve authority.
* `act = -1.0` (DIRECT) was already correct and is unchanged: wetter offgas -> more reflux.
* The controller is now stepped immediately BEFORE its slave so the cascade is same-tick like every
  other master in the engine. Its PV depends only on constants and `s.a328_d001_P`, both settled at
  that point. The old step further down — where its output was computed and discarded — is removed;
  leaving it would have advanced the controller twice per tick.

Design fixed point: `pv == sp == pv1 == pv2` gives `du == 0`, so `op` holds `R328_D001_M775_DES`
exactly, which `_fic_flow` turns into `M775_DES / RHO_775_KGM3` — bit-identical to the slave's
seeded `sp`, and the clamp against `sp_lo/sp_hi` returns it unchanged.

Measured with `scratchpad/probe_td004_cascade.py`, stepping the master SP down 5 % (46.21 -> 43.90
mol%, i.e. demanding drier offgas):

| t (s) | FV-328404 stroke | reflux demand | slave SP |
|---|---|---|---|
| 0 | 30.20 % | 1675 kg/h | 1.5297 m3/h |
| 300 | 35.66 % | 1999.58 kg/h | 1.8261 m3/h |
| 900 | 46.45 % | 2596.61 kg/h | 2.3713 m3/h |

Direction is physically right — drier offgas demands MORE reflux. Still climbing at 900 s, which is
expected for an inferential composition loop with `Ti = 250 s`.

`app.js` `CAS_MASTER` now lists `FIC-328404 -> TIC-328008` as a live pair, and `CAS_UNWIRED` is empty.

### TD-005 — RESOLVED

`FIC-328406` now indicates the real PFD-741 process-condensate RECYCLE, 328E007 -> 328E001 ->
328D003 Comp I, instead of being fed its own opening as a PV.

PFD-22 col 741 is "Pur. Pr. C", **0 kg/h / 0 m3/h** at 40 C / 3.9 bar, rho 992.42 — the line exists
but is normally closed at 100 % load, exactly like the 793 spare. So:

* New constants: `S741_CAP_KGH = R328_C004_M739_DES` (33724 kg/h full stroke — bounded by the
  328C004 bottoms that 328E007 actually condenses, so nothing is fabricated), `RHO_741_KGM3 =
  992.42` (the PFD's own "Density eff." row), `A328_M741_T = 40.0` C.
* Driven through `_fic_flow(..., rho=RHO_741_KGM3)` with `op_des = 100`, so 0 % stroke is exactly
  0 flow and the loop is a genuine VOLUMETRIC m3/h measurement matching its `M3/H` overlay label.
* Wired into the Comp-I balance as an INFLOW: `in_compI` gains `m_741`, and `P_compI` gains
  `m_741 * (A328_M741_T - TI)`. Stream 740 is a boundary export in this model (there is no tracked
  `m_740` — only the `R328_E007_TH_OUT` temperature), so the recycle returns liquid that would
  otherwise leave the envelope.
* The previous `_ctrl_ipd(s.FIC_328406, s.FIC_328406["op"], dt)` self-referential step is removed.
* Telemetry publishes `pv`/`sp` in m3/h plus `m_kgh`; the old `vol_m3h = pv / A328_M755_RHO` is gone
  (it divided a percentage by the density of the WRONG stream — 755 is Amm. Water, 741 is
  purified process condensate).

At design `m_741 == 0`, so every term above is byte-identical to the pre-741 balance.

Verified for both: pin gate `leaves: 25  keys: 15  diffs: 0`, suite **103 passed**.

---

## TD-006 — stripper duty is feed-proportional, not a full enthalpy balance

- **Status:** OPEN (partial fix shipped as G8)
- **Opened:** 2026-07-21
- **Files:** `backend/main.py` step_sim steam-balance handshake (`Q_strip_kjh`), `stripper_322e001`

### What G8 fixed

`Q_strip_kjh` was hardcoded at `STRIP_DUTY_DES_KW` (39,400 kW), so the MP-steam draw was
invariant to load: 76.7 t/h of steam was still consumed at zero feed and the MP header could
never register a stripper flood (Red Team CP-7 / Agent A + D). It now tracks the live feed mass:

    strip_load  = max(m_feed_strip / STRIP_FEED_DES_KGH, 0.0)   # 1.0 at design, bit-exact
    Q_strip_kjh = STRIP_DUTY_DES_KW * strip_load * 3600.0

`STRIP_FEED_DES_KGH` equals the live design feed BIT-EXACTLY (280795.92149696), so design duty is
exactly 39,400 kW — no pin-contract change, no boot capture. `duty_kW` and `kgh` telemetry are now
live, so specific steam consumption is trainable, and zero feed draws zero steam.

### What remains

1. **Feed-proportional is not the rigorous enthalpy balance.** Agent A showed that at a +30 % feed
   spike the product enthalpies demand ~+12 %, not +30 % — extra feed leaves as hotter bottoms
   carrying its own enthalpy out. The correct duty is `Σ product enthalpy − Σ feed enthalpy +
   reaction`, but the model exposes only a single mean `STRIP_CP_BOTTOM` (2.93 kJ/kg·K), no
   per-component cp/latent vectors, so a rigorous balance means adding a species-enthalpy layer.
2. **No steam-limited flood regime.** When PIC-329204 drives the MP valve to 100 % the duty should
   saturate (steam-limited) and the bottom should cool toward the crystallization floor rather than
   the reboiler delivering unbounded heat. That is the abnormal-operation branch; the shipped
   increment models the normal temperature-controlled regime only.
3. `PIC-329204` / the MP header still behaves as a near-infinite steam sink (Agent A): the header
   pressure barely moves under load, so the duty change does not yet feed back into a realistic MP
   pressure excursion. Couple `m_strip` into the MP header dynamics once (1) lands.

Both are larger, pin-sensitive efforts and were deferred deliberately rather than rushed.

---

## TD-007 — HPCC 322E002 condensation split is invariant to shell temperature and loop pressure

**Status: CLOSED 2026-07-22** · raised 2026-07-22 by the full equation audit (`EQUATION_AUDIT.md`,
finding F-6) · severity B (limits training fidelity; not operator-triggerable into wrong physics)

`hpcc_322e002` splits the combined tube-side feed with a frozen calibrated vector:

    gas = {k: feed[k] * HPCC_FRAC_GAS_DES.get(k, 0.0) for k in MW_COMP}      # main.py:1922

`HPCC_FRAC_GAS_DES` is a constant. The duty, the adiabatic exotherm spike and the ε-NTU quench all
respond to the live shell temperature `t_shell` and to throughput, but **not one mole of condensate
moves**. Raising the LP-steam pressure (hotter shell ⇒ less driving force ⇒ physically less
condensation) changes `T_prod` and `q_steam_kw` while the phase split stays exactly at design.

This is the C5 (EoS / activity) gap of the audit: a split fraction is only a legitimate hybrid
layer when it is a *function* φᵢ(T, P, composition). As coded it is a point calibration.

### How it was closed

`_hpcc_flash_split()` binds an isothermal (T,P) Rachford-Rice flash **anchored on** the calibration
rather than replacing it: `K_des,i` is back-solved every tick from `HPCC_FRAC_GAS_DES` and the live
feed (so the melt's measured activity coefficients stay baked in), then corrected to the live product
temperature and synthesis pressure by the carbamate equilibrium `Kp = p²_NH₃·p_CO₂` — whose
dissociation-*pressure* slope is ΔH_carb/3 because Kp is a third-order product (Bennett 1953;
Ramachandran 1998) — with Raoult for H₂O and Henry for N₂. Rachford-Rice is solved by **bisection**,
not Newton: g(ψ) is strictly decreasing, so 60 sweeps are exact to 2⁻⁶⁰ at bounded cost with no
possible convergence failure inside an OTS tick.

The raw equilibrium target proved far too stiff on its own (φ_CO₂ 0.0009 → 1.0 across 150 → 190 °C,
because the distributing K-values are tightly clustered and move together). That is a real property
of the flash, not a coding error — but it is not how this vessel behaves. `References/HPCC
description.md` §5.2–5.3 is explicit that 322E002 is interfacial **mass-transfer** limited, so φ is
relaxed toward the target over the condenser holdup constant `HPCC_TAU_FILL_MIN`, making the split a
dynamic state `s.hpcc_phi`. That was the genuinely missing equation: the condenser had no
composition dynamics at all.

Three independent anchors keep the pin: the flash short-circuits to the calibration when the T and P
ratios are exactly 1 (module-load and boot-pin passes never enter the solver); `dt = 0` on those
passes zeroes the relaxation; and the result is blended through `_disturbance_gate` exactly as
`T_prod` is. Measured: gate 0.000000 and T_prod drift 0.000e+00 over a 600 s design hold, with φ
identical to `HPCC_FRAC_GAS_DES` by identity comparison on every component.

**Loop-gain check** (the runaway path at main.py:1878) came back **negative feedback** in both legs
and was verified, not assumed: T_prod spans 0.0205 °C after a shell-temperature disturbance and
0.2329 °C after an N/C disturbance over the final five minutes — monotone convergence, no ringing.
Also fixed in the same pass: `p_bub` was evaluated at the frozen design temperature; it now uses the
live gated `T_prod` (telemetry only — it does not enter `pt_target`, so no new loop).

Gates: pin `leaves 25 / keys 15 / diffs 0` · suite `123 passed`. Tests:
`backend/test_equation_audit_322e002.py`. Probe: `scratchpad/probe_322e002_flash.py`.

---

## TD-008 — 328C003 hydrolyser carries no reaction extent

**Status: OPEN** · raised 2026-07-22 (`EQUATION_AUDIT.md`, finding F-7) · severity B

`NH2CONH2 + H2O ⇌ 2 NH3 + CO2` is the entire purpose of 328C003, and the engine models it as a
frozen overhead split `gen748 = R328_C003_PHI748 * in_c003` with the reaction endotherm lumped into
the back-solved latent `R328_C003_LAM748`. There is no extent, no rate, no residence-time
dependence in the mass balance.

The kinetics already exist in the codebase — `ppm_infer_328701` uses first-order Arrhenius
hydrolysis (`R328_AI701_EA_UREA = 72000` J/mol, `R328_AI701_KEFF_UREA`, `R328_AI701_TAU_S = 3600` s)
— but only as a **read-only soft sensor**. Promoting that same rate law into the 328C003 mass
balance would make MP-steam rate and residence time actually govern urea destruction, which is what
the loop is trained on.

Depends on TD-009: an extent needs species, and the 328 train is lumped-mass.

---

## TD-009 — component species balance exists only in unit 322

**Status: OPEN** · raised 2026-07-22 (`EQUATION_AUDIT.md`, finding F-8) · severity B

`MW_COMP` (9 species) is tracked rigorously through 322F001 → 322E001 → 322E002 → 322R001 →
322E003. Everything downstream of LV-322501 — the whole of 323, 324, 328, 322C001 — is **lumped
mass** with design split fractions and back-solved latents. Consequences:

* no C2 component balance and therefore no C6 summation equations (Σy = 1, Σx = 1) downstream;
* composition-driven behaviour is reachable only through soft sensors (`conc_infer_324`,
  `ppm_infer_328701`, the TIC-328008 inferential), which are read-only and cannot feed back;
* TD-008 has nowhere to put a reaction extent.

This is the single largest remaining architectural gap. It is also the largest change in the
engine, touching every 323/324/328 stage ODE and every telemetry group, so it needs to be planned
as its own project rather than slotted into a fix pass.

---

## TD-010 — `scratchpad/regress.py` cannot be invoked with the documented relative path

**Status: OPEN** · raised 2026-07-22 (`EQUATION_AUDIT.md`, finding F-9) · severity C (tooling)

`regress.py` does `os.chdir(BACKEND)` before writing `argv[1]`, so the gate command printed in
CLAUDE.md §7 and handoff.md —

    %PY% scratchpad\regress.py scratchpad\pin_now.json

— resolves the output to `backend/scratchpad/pin_now.json`, which does not exist, and dies with
`FileNotFoundError` **after** paying the full settle cost. Until the script resolves `argv[1]`
against its original cwd, invoke the gate with an absolute output path:

    "$PY" scratchpad/regress.py "D:/Work/Urea Simulation/scratchpad/pin_now.json"
