# Technical Debt Log

Tracked, non-blocking discrepancies. Each item is asserted in the audit suite as an
`XFAIL` (recorded, does not fail the run) so the gap stays visible without going green-by-deletion.

---

## TD-001 — `phi_sp` ejector-spindle helper encodes the SUPERSEDED positive law

- **Status:** RESOLVED — verified 2026-07-22 by the "close all gaps" audit sweep. The helper at
  `tests/audit_f001_ejector.py:60` already reads `EJ_SPINDLE_R ** ((EJ_OPEN_DES - opn)/100.0)`, the
  NEGATIVE law, and the opening sweep is a real `chk` (not `xchk`): the run prints
  `[PASS] m_suc scales by phi_sp == R^((74-open)/100) across opening sweep (helper==model)` plus
  the bit-exact `phi_sp(74) == 1.0` and datasheet-ratio checks. Only this log entry was stale.
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

- **Status:** **CLOSED 2026-07-23** (commit `1da9280`) — both halves done. The hydrodynamic
  flooding limit landed in `6fb4c09`; the per-species enthalpy balance closed the same day.
- **Opened:** 2026-07-21

### Enthalpy half — CLOSED 2026-07-23

The duty was `STRIP_DUTY_DES_KW · (ṁ_feed/ṁ_feed,des) · 3600` — proportional to feed **mass**, so
composition never entered. The same tonnage of pure water and of carbamate-rich reactor liquor
demanded identical steam, and the single largest heat sink in the unit — carbamate dissociation —
was invisible to the MP header.

**The blocker turned out not to exist.** The previous session recorded this as blocked on sourcing
a carbamate dissociation enthalpy, "none exist in the codebase". That was wrong twice over:
`HPCC_DH_CARB_KJMOL = 160.0` was already at `main.py:2187` with its own provenance, and the better
value was one search away. Frejacques, quoted in **Brouwer, "Thermodynamics of the Urea Process",
UreaKnowHow Process Paper June 2009, p.12**, gives both reactions at *process* conditions:

| reaction | ΔH | conditions |
|---|---|---|
| `CO2(G) + 2 NH3(G) → NH2COONH4(L)` | −117 kJ/mol | 110 atm, 160 °C |
| `NH2COONH4(L) → NH2CONH2(L) + H2O(L)` | +15.5 kJ/mol | 160–180 °C |

Those conditions sit close to this stripper's 144 bar / 172–183 °C, so **117** is used rather than
the 159–160 kJ/mol universally quoted for *solid* carbamate at 1 atm / 25 °C. NH3 is supercritical
at stripper temperature (Tc = 132.4 °C) so it has no latent heat at all; what the duty pays is the
desorption enthalpy, taken as the loop's own `HPCC_BUB_DHVAP_JMOL`.

**Validation — this is the part that matters.** Summed over the design streams with nothing fitted
and no free parameter, the balance gives **37 831 kW against the licensor's 39 400 kW — 96.0 %**.
The 4 % residue is shell/ambient loss, biuret (no published enthalpy, and 0.667 kmol/h against 88.1
for hydrolysis), and the mean-cp approximation. Term breakdown:

| term | kW | share |
|---|---:|---:|
| carbamate dissociation | 22 118 | 58 % |
| free-NH3 desorption | 14 123 | 37 % |
| water latent | 2 803 | 7 % |
| urea hydrolysis (liquid step) | −379 | — |
| sensible, both products | −834 | — |

Only the **ratio** to its own design value is applied, so `STRIP_DUTY_DES_KW` stays the licensor
anchor, the 4 % offset cancels and never reaches the header, and at design the ratio is `X/X == 1.0`
— bit-identical to the feed-proportional form it replaces.

### The unsourced constant — RETIRED 2026-07-23

`STRIP_FLOOD_ETA_K = 1.50`, flagged in the flooding half as "the one number to replace", is gone.
It was wrong twice: **~10× too aggressive** (15 % efficiency loss at 1.5× load against ~1–3 %), and
**double-counting**, since `g_T` already collapses `eta_T` on a feed spike through the thermal path.

It needed no replacement constant, because the bottom-temperature rise and the efficiency loss are
the same event measured two ways — the bottom runs hotter *precisely because* the dissociation
endotherm did not happen:

    g_flood = 1 − (ṁ_feed · cp · ΔT_flood) / (n_carbamate_CO2 · ΔH_carb)

Every term was already sourced. `ΔT_flood` is exactly 0.0 below the limit, so `g_flood` is exactly
1.0 at design — a structural identity, not a float-ordering trick. Three independent cross-checks
agree on a few percent: this balance **2.9 %**, Brouwer's Shangdong Hualu Hengsheng case (a 3 °C
bottom shift alongside 79 % → 81 % efficiency) **2.5 %**, and the licensor length correlation from
the same paper (6 m eff. → 80 %, 8 m → 82 %) **0.8 %**.

### Flooding half — CLOSED 2026-07-23

The unit had **no tube geometry at all**: `grep -E "N_TUBE|TUBE_|D_TUBE|L_TUBE"` returned zero
hits, and every "flood" term already in `stripper_322e001` was a *thermal* metaphor for the
steam-dilution branch (`raw_load < 0`), not a hydraulic limit. A falling-film stripper's real
ceiling is a **liquid-load** limit that is independent of steam duty.

Geometry came from the licensor DDS (**Uhde UD-AU-322-DZ-0003-003 rev 00, page 3**), and the sheet
is self-consistent — its own tabulated surface area confirms the tube count, so the number is not
a single cell read on trust:

| | DDS | |
|---|---|---|
| number of tubes | **2600** | line 34 |
| tube OD × wall | 31 × 3.0 mm → **ID 25.0 mm** | line 36 |
| effective length | **6000 mm** | line 35 |
| exchange surface | 1519.00 m² | line 25 |
| cross-check | N·π·d_o·L = **1519.27 m²** | **+0.018 %** ✓ |
| ρ_G / ρ_L,in | 10.28 / 989.88 kg/m³ | lines 13–14 |

**Three documents agree, so nothing was fabricated:**
- the DDS bore is 25.0 mm = **0.984 inch**, so the 145 kg/h "1-inch tube" figure applies *without
  scaling*;
- the DDS effective length is **6.000 m**, exactly the length Brouwer ties to the 80 % design
  stripping efficiency;
- the quoted reference condition, 183 °C, **is `STRIP_FEED207_T_C`** — this stripper's own feed
  temperature — and 140 bar is within 3 % of its 144 bar tube side.

**Where the plant sits, computed not tuned:**

```
280 797 / 2600 / 145  =  0.7448      108.0 kg/h per tube, 74.5 % of the limit
plant limit 377 000 kg/h        ->   flooding onset at 134 % of design load
```

That 134 % is the same order as Brouwer's "110 % when new, 120 % at end of life", and slightly
roomier — which is what a 0.984″ bore at 144 bar rather than 140 bar should give.

**The bit-exactness argument is structural, not an anchored ratio.** Because 0.7448 < 1.0 the
constraint is *one-sided and does not bind at the design seed*: `flood_x = max(frac − 1, 0)`
returns the literal `0.0`, so `1 − e^0 = 0.0` and `1/(1 + K·0.0) = 1.0` are exact identities. The
plant genuinely operates below its flooding limit, so the term cannot move a single bit of the pin.
Verified: `g_flood == 1.0` and `dT_flood == 0.0` compare equal, and the gate prints
`leaves: 25  keys: 15  diffs: 0`.

**Calibration, from the literature rather than fitted:** Brouwer's "3–4 °C in 15 minutes" bottom-
temperature signature fixes `STRIP_FLOOD_T_K`. The rise is capped by the *same* 11 °C ceiling the
existing steam-dilution branch uses (`STRIP_T_FLOOD_ANCHOR_C − STRIP_T_BOTTOM_DES_C` = 183 − 172),
because both describe one end state — unstripped reactor liquor falling through untouched. Solving
`11.0 × (1 − e^(−K·0.10)) = 3.5` gives **K = 3.83**, and the model returns 3.50 °C at 10 % over.

**One sign trap, avoided deliberately.** `g_flood` multiplies the *split* only, never `eta_T`.
`eta_T` scales `xi_hyd`, and flooding **increases** residence time ("stagnation or upward dragging
of the film"), so hydrolysis and biuret go *up*. Folding `g_flood` into `eta_T` would have cut
hydrolysis — the wrong sign. The rise is already carried without a new term: `dT_flood` raises
`T_bot` and `xi_biu` is Arrhenius in `T_bot_K`. A regression test pins this.

Measured cascade (overhead NH₃ recovery, exactly Brouwer's described failure): 89 % at design →
56 % at onset → 30 % at 180 % load, with the volatiles held in the bottoms and slipping to LP.

- **Landed:** `backend/main.py` constant block + `stripper_322e001`;
  `backend/test_equation_audit_322e001_flood.py` (11 tests)
- **Not modelled, deliberately:** the corrosion/lifetime drift (limit rising 110 → 120 % as the
  bore grows) and the metallurgical active-corrosion mode. Both are *multi-year* effects with no
  place in a shift-length OTS scenario; recorded here so the omission is a decision, not an
  oversight.
- **One number is not sourced:** `STRIP_FLOOD_ETA_K`. Brouwer states efficiency drops but publishes
  **no curve**, so rather than invent a fitted slope it reuses the unit's existing efficiency-choke
  scale (`STRIP_ETA_KT` = 1.50). If a real efficiency-vs-flooding curve ever surfaces, this is the
  single number to replace.

### Research complete — the flooding constants, sourced

Primary source: **Brouwer, *How to Solve Stripper Efficiency Issues*, UreaKnowHow, June 2025**,
which attributes the flooding figure to **IFS Proceeding 166**. Corroborated by Stamicarbon's own
stripper literature.

| quantity | value | note |
|---|---|---|
| flooding limit, 1″ tube | **145 kg/h of solution** | at 183 °C reactor-outlet, 140 bar |
| design operating fraction | **70 % of that limit** | "in practice, an upper limit of 70 % is applied" |
| where flooding starts | **top of the tubes** | ~half the liquid has evaporated by the bottom, so gas and liquid loads peak at the top |
| design stripping efficiency | **80 %** on a 6 m effective tube | Chiyoda's 8 m gives 82 % |
| shell-side MP steam | 20–23 bar | |
| control-room symptom | **bottom outlet +3–4 °C in 15 min** | "a clear indication for reaching the flooding limit" |
| downstream consequence | more NH₃ in the bottoms → more gas to LP recirculation → **LP pressure rises**, operators must cut load | |
| corrosion, passive | ≤ 0.1 mm/year | oxygen from passivation air maintains the oxide layer |
| corrosion, active | **20–30 mm/year** | stagnant flooded liquid depletes the oxygen; ends in tube rupture |
| lifetime drift | flooding limit **110 % of plant load when new → 120 % at end of life** | ID grows with passive corrosion; the limit is linear in it |

Metallurgy note for the training scenario: 25-22-2 austenitic tubes are susceptible to the active
mode; Safurex®/E-type super-duplex is immune to active corrosion, though the stripping-efficiency
loss remains either way.

*Superseded by what was actually built.* The plan above proposed a Wallis calculation at the top
axial node with the penalty written as an **anchored ratio**. Two things changed on contact with
the data:

1. **No anchored ratio was needed.** The design point sits at 74.5 % of the limit, so the
   constraint simply does not bind at the seed — a cleaner and more honest guarantee than an
   anchored ratio, because it rests on a physical fact rather than on float operand ordering.
2. **The Wallis form was not used to *set* the limit.** Evaluating √j\*_g + √j\*_l at design gives
   **0.84–1.08** depending on which gas load is taken for the top of the tube, against a classic
   Wallis C of 0.7–1.0 — i.e. the correlation's own threshold band straddles the design point, so
   fitting C would have been fitting noise. The licensor-specific empirical 145 kg/h/tube figure is
   the better anchor: it is what the plant's own engineers use and it needs no C/m fit. The Wallis
   algebra is retained in [`scratchpad/probe_td006_flood.py`](scratchpad/probe_td006_flood.py) as
   the documented reasoning, and remains available if the limit ever needs shifting with gas
   density (pressure/temperature) off the reference condition.

### The remaining half — per-species enthalpy (STILL OPEN)

Now fully unblocked: the species layer reaches 322 (9 components) and, since the F-8 closure, 323,
324 and 328. The stripper duty should become sensible + carbamate dissociation endotherm + latent,
per species, rather than `STRIP_DUTY_DES_KW * strip_load`.
- **Files:** `backend/main.py` step_sim steam-balance handshake (`Q_strip_kjh`), `stripper_322e001`

**The exact bit-exactness contract to honour** (mapped while closing the flooding half, so the next
session does not have to re-derive it). At `main.py` the handshake reads:

```python
m_feed_strip = sum(strip["feed_kmolh"][k] * MW_COMP[k] for k in MW_COMP)
strip_load   = max(m_feed_strip / STRIP_FEED_DES_KGH, 0.0)   # exactly 1.0 at design
Q_strip_kjh  = STRIP_DUTY_DES_KW * strip_load * 3600.0
```

`m_feed_strip` is bit-identical to `STRIP_FEED_DES_KGH` at the seed **only because both iterate
`for k in MW_COMP` in the same order** with the same operand order. Any replacement must therefore
sit in the same left-to-right position — `STRIP_DUTY_DES_KW * <new_factor> * 3600.0` — with
`<new_factor>` evaluating to a bare `1.0`. The natural construction is an enthalpy ratio
`H_live / H_des` where both sides are computed by the *same function*, so the seed gives `X / X`.

**What it still needs, and what must not be invented.** The unit has exactly one thermal constant,
`STRIP_CP_BOTTOM = 2.93`. A per-species balance needs an ammonium-carbamate dissociation enthalpy
and NH₃/CO₂ latent heats at ~183 °C / 140 bar. None of these exist in the codebase, and the
literature sweep that would have sourced them **did not complete** (the subagent fleet hit the
session limit). Per CLAUDE.md §1 these must be sourced or back-solved from the design duty, not
guessed. Sensible-heat and reaction extents are already available (`STRIP_FEED207_T_C` = 183,
`STRIP_T_BOTTOM_DES_C` = 172, `xi_hyd` = 88.1 kmol/h), so only the dissociation and latent terms
are missing.

**Incidental finding while mapping this — worth its own fix.** `eta_P` in `stripper_322e001` is a
**dead lever**: `P_bara` is always passed the frozen `STRIP_P_DES_BARA`, so
`eta_P = clamp(2.0 − P_bara/STRIP_P_DES_BARA, …)` is identically 1.0 in the live loop. Synthesis
pressure therefore has *no* effect on stripping efficiency, which is physically wrong — stripper
performance is strongly pressure-sensitive. Not fixed here (out of scope, and it would move the
pin's sensitivity surface), but it should not stay hidden.

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

**Status: CLOSED 2026-07-22** · raised 2026-07-22 (`EQUATION_AUDIT.md`, finding F-7) · severity B

`NH2CONH2 + H2O ⇌ 2 NH3 + CO2` is the entire purpose of 328C003, and the engine models it as a
frozen overhead split `gen748 = R328_C003_PHI748 * in_c003` with the reaction endotherm lumped into
the back-solved latent `R328_C003_LAM748`. There is no extent, no rate, no residence-time
dependence in the mass balance.

The kinetics already exist in the codebase — `ppm_infer_328701` uses first-order Arrhenius
hydrolysis (`R328_AI701_EA_UREA = 72000` J/mol, `R328_AI701_KEFF_UREA`, `R328_AI701_TAU_S = 3600` s)
— but only as a **read-only soft sensor**. Promoting that same rate law into the 328C003 mass
balance would make MP-steam rate and residence time actually govern urea destruction, which is what
the loop is trained on.

### How it was closed

It turned out **not** to depend on the full TD-009 328 species vector. Hydrolysis is a flow-through
conversion, so it needs only the urea content of the feed (PFD stream 746, 0.82 %) — not a species
holdup in every 328 vessel.

The key modelling call: **328C003 is a trayed column, so it is plug flow, not a CSTR**, and that is
the only way the PFD's 0.82 % inlet → 1 ppm outlet is reachable at all. A CSTR at k·τ = 10.14
converts 91 %; plug flow converts 1 − e^(−10.14) = 99.996 %. Residence time falls as throughput
rises, so `τ = τ_des·(ṁ746_des/ṁ746)` and `X = 1 − exp(−k(T)·τ)` with the soft sensor's own
first-order Arrhenius (Eₐ = 72 kJ/mol).

The 812 kg/h overhead now decomposes into reaction plus strip —
`gen748 = ξ·(2·M_NH3 + M_CO2) + ṁ_strip,des·(ṁ911/ṁ911,des) = 360.0 + 452.0` — with both terms
exactly their design value at the seed, so `gen748 == R328_C003_M748_DES` bit-exact and the pressure
ODE stays stationary. AI-328701's urea slip is now a mass-balance result of the extent.

Operator-visible behaviour that did not exist before: 200 °C → 0.32 ppm slip, 180 °C → 88 ppm,
160 °C → 1252 ppm, 140 °C → 3994 ppm; and at 2× throughput → 102 ppm, 3× → 830 ppm.

Gates: pin `leaves 25 / keys 15 / diffs 0` · suite `136 passed`. Tests in
`backend/test_equation_audit_species.py`.

**Caveat carried forward:** the 328 train's own component balance (TD-009 remainder) is still
outstanding — this closes the reaction, not the species accounting around it.

---

## TD-009 — component species balance exists only in unit 322

**Status: RESOLVED 2026-07-22** (323 + 324, then the 328 desorption train) · raised
2026-07-22 (`EQUATION_AUDIT.md`, finding F-8) · severity B

`MW_COMP` (9 species) is tracked rigorously through 322F001 → 322E001 → 322E002 → 322R001 →
322E003. Everything downstream of LV-322501 — the whole of 323, 324, 328, 322C001 — is **lumped
mass** with design split fractions and back-solved latents. Consequences:

* no C2 component balance and therefore no C6 summation equations (Σy = 1, Σx = 1) downstream;
* composition-driven behaviour is reachable only through soft sensors (`conc_infer_324`,
  `ppm_infer_328701`, the TIC-328008 inferential), which are read-only and cannot feed back;
* TD-008 has nowhere to put a reaction extent.

### How the 323 + 324 half was closed

A six-species layer (Urea, Biuret, NH3, CO2, H2O, HCHO) that **rides on top of** the existing
total-mass and energy ODEs rather than replacing them — `d(M·w_i)/dt = ṁ_in·w_in,i − ṁ_liq·w_i −
ṁ_vap·y_i + ν_i·ξ`, using the SAME flows the mass ODEs already compute. C1 is therefore untouched
by construction and the design anchors cannot move; C2 and C6 are added on top.

Two pieces of real physics fell out of the design data:

* **Biuret formation, 2 Urea → Biuret + NH3.** Back-solving the PFD rise (0.24 % at stream 208 to
  0.85 % at 402) gives extents of 0.660 / 0.000 / 0.006 / 1.487 / 0.996 kmol/h across
  C003/F004/F010/E001/E003 — 324.6 kg/h total against the 322 kg/h the PFD flows imply, with the two
  hot evaporators dominating exactly as expected. Arrhenius, second order in urea, sharing the
  stripper's activation energy. (The 323F010 extent was 0.136 and the total 338 kg/h until TD-011
  was resolved; stream 331 carries biuret in, so less of it has to be made at that stage.)
* **Relative-volatility vapour compositions**, `y_i = α_i·w_i / Σ α_j·w_j`, with α back-solved at
  design *after* the reaction extent is removed. That normalisation IS the C6 summation equation.

Everything is anchored: at the design seed w == w_des at every stage, so y == y_des, so every
species flow equals its design value and dw/dt == 0. Σw reads exactly 100.0000 on every tick.

Closing it immediately exposed **TD-011 / finding F-11** (below) — which turned out to be a missing
feed into 323E010, not a data error, and is now resolved. `sol_pin_strength` survives it as a
rounding guard on the 324 melt only.

### How the 328 half was closed

Not the mechanical extension it was billed as. Three things had to be settled first.

**1. The PFD's composition-unit convention.** Read as mass %, the licensor's own table says carbon
is not conserved across 328C002 — 1658 kg/h of CO₂ in, 858 out. That reading is wrong: **liquid
rows are mass %, vapour/gas rows are mole %**, and the tabulated `Average Molar Weight` proves it
(stream 737 reads 20.81 as mole %, 18.94 as mass %; the PFD tabulates 20.81). Verified across ~90
streams in all four tables. Read correctly, all three columns close per component to under 2 kg/h in
34–40 t/h with nothing fitted. This also retired the "accepted variance" recorded against stream 790
under TD-011 — that was the same misreading, and 790's CO₂ closes to 0.25 kg/h.

**2. The mechanical datasheet.** Uhde UD-AU-328-EC-0001 rev 01 shows 328C002 and 328C004 are **one
25.5 m tower**, C002 stacked on C004 — corroborated independently by Stamicarbon's own "top part /
bottom part of the desorber" description. It gives 15 and 22 executed trays, ID 1250 mm, 40 mm weir,
3125 × ⌀6 mm perforation. Holdup stopped being a 900 s residence-time guess (8442 / 8431 kg) and
became geometry (1588 / 1436 kg) — the real columns respond ~5× faster than the model did. The tray
counts also set the Kremser stage count that makes the columns degrade like columns instead of like
a single flash.

**3. Two defects the lumped model was hiding.**

* `R328_C003_W_UREA_746` was hardcoded **0.0082 — stream 738's urea, not stream 746's**. 328C002
  dilutes 31 114 kg/h of feed into 33 769 kg/h of bottoms, so the PFD gives 743/746 as 0.76 % and
  the hydrolyser was being handed 276.9 kg/h of urea against the tabulated 256.6, **+7.9 %**. It now
  reads off the live 328C002 species vector, so the two cannot drift apart again.
* **The trace species are violently stiff.** 328C004 holds 1436 kg of liquid at 1 ppm ammonia —
  1.4 grams — while 330 kg/h flows through it. τ ≈ 0.015 s against a 0.25 s tick. Explicit Euler
  (which is what the 323/324 layer uses, correctly, because nothing there is at ppm) overshoots
  ~16×, hits the non-negativity clamp, and walked 328C002 from 0.63 % to 2.2 % ammonia over four
  simulated hours. `des_advance` is implicit; lagging the summation denominator makes the removal
  term linear in wᵢ, so the step is closed-form and exactly stationary at the design point.

**Durable lesson:** *a species layer that works at percent concentrations does not automatically
work at ppm.* Integrator choice is set by the smallest inventory in the vessel, not the largest.
Check τ = M·wᵢ/(flow) for the trace species before reusing an explicit scheme.

The frozen overhead splits `R328_C002_PHI737` / `R328_C004_PHI750` are gone from the runtime —
overheads are energy-limited in the same anchored-ratio form used at 323F010. TD-008's hydrolyser
extent now acts on real species.

---

## TD-010 — `scratchpad/regress.py` cannot be invoked with the documented relative path

**Status: RESOLVED 2026-07-22** · raised 2026-07-22 (`EQUATION_AUDIT.md`, finding F-9) · severity
C (tooling). `regress.py` now resolves `argv[1]` against the original cwd before `os.chdir(BACKEND)`,
so the documented relative gate command works. The workaround below is no longer needed.

`regress.py` does `os.chdir(BACKEND)` before writing `argv[1]`, so the gate command printed in
CLAUDE.md §7 and handoff.md —

    %PY% scratchpad\regress.py scratchpad\pin_now.json

— resolves the output to `backend/scratchpad/pin_now.json`, which does not exist, and dies with
`FileNotFoundError` **after** paying the full settle cost. Until the script resolves `argv[1]`
against its original cwd, invoke the gate with an absolute output path:

    "$PY" scratchpad/regress.py "D:/Work/Urea Simulation/scratchpad/pin_now.json"


---

## TD-011 — 323E010 was missing its second feed (PFD stream 331)

**Status: RESOLVED 2026-07-22** · raised 2026-07-22 (`EQUATION_AUDIT.md`, finding F-11) ·
severity B → **A** on diagnosis

Found by closing TD-009: the rigorous component balance would not close across 323F010.

Removing stream 319's water, NH3 and CO2 at the PFD's own tabulated percentages takes out

    water  101570·0.2635 − 92820·0.1947 = 8692 kg/h
    NH3    101570·0.0088 − 92820·0.0008 =  820 kg/h
    CO2    101570·0.0066 − 92820·0.0002 =  651 kg/h
                                          -----------
                                          10163 kg/h

against a tabulated total loss of 101570 − 92820 = **8750 kg/h**. For the licensor's numbers to
close, ≈1413 kg/h of urea has to *appear* across 323F010. It was raised as a suspected source-data
inconsistency, on the reading that stream 331 (the urea-recovery return, 3270 kg/h at 44.37 % urea =
1451 kg/h of urea) was the right magnitude but entered at 323D002, downstream.

### What it actually was

**A topology error in the engine, not a data error.** Confirmed by the licensor: stream 331 joins
stream 319 *ahead of* 323E010. The combined solution is heated by LP steam on the shell side, then
separates in 323F010 under vacuum into gas stream 790 and liquid stream 315 (== 317 after the pump,
which is why the two share a composition column in the PFD).

The reading that raised the finding was the wrong one: the missing 1413 kg/h of urea was not
unexplained, it was stream 331's, arriving at a stage the model did not connect it to. With the
real topology, the total mass balance closes to 20 kg/h in 105 t/h (0.019 %) on the licensor's own
tabulated flows, and the formaldehyde tracer is decisive — 331 carries 7.52 kg/h of HCHO in, 315
carries 7.39 kg/h out, and 331 is the only formaldehyde source anywhere in the plant.

### Fixed by

`R323_M331_DES` / `R323_M331_T_C` as new PFD anchors; `R323_MEVAP_DES` becomes a sum so that
`R323_M317_DES` keeps its exact bits and every unit-324 constant stays byte-identical; the stage
energy balance gains the cold feed's sensible term (design duty 5048 → 7249 kW, since 331 lands
59 °C below the product); `_sol_stage_anchor` and `sol_advance` take an optional second inlet.

The back-solved stage residual goes from **−1414 kg/h to exactly 0.000**, and 323F010 — still
un-pinned — now reaches **79.963 %** urea against the PFD's 80.00, where it published 78.44 before.
`sol_pin_strength` is retained but is an identity at this stage; it holds the 324 melt against PFD
percentage rounding per CLAUDE.md §0 and nothing more.

**Durable lesson:** a component balance that will not close is evidence of a *missing stream* at
least as often as it is evidence of bad data. Check the topology against the licensor before
concluding the numbers are wrong — and prefer a conserved tracer (here, formaldehyde) to argue it,
since a species with exactly one source in the plant cannot be explained away by rounding.

---

## TD-012 — C10 constitutive properties: densities and cp are compile-time constants

- **Status:** **PARTIALLY CLOSED 2026-07-23** — urea-solution cp and density are now live
  correlations and unit 324 uses them per-location. The **aqueous/water** side (the >150 °C
  discrepancy analysed below) and the volumetric-controller densities remain OPEN.
- **Opened:** 2026-07-22 (`EQUATION_AUDIT.md`, category C10)

### Urea-solution cp and rho — CLOSED 2026-07-23

One cp (2.5 kJ/kg·K) and a set of frozen densities covered every urea solution in the plant, from
44 % urea in LP recirculation to 97.71 % melt leaving Evaporator II. The error is largest exactly
where the model does its most important work, because the evaporation train's whole *purpose* is to
change the composition:

| stream | urea | T | true cp | constant 2.5 |
|---|---:|---:|---:|---:|
| 331 | 44.4 % | 40 °C | 3.25 | **23 % low** |
| 315/317 | 80.0 % | 99 °C | 2.50 | anchor |
| 401 | 94.3 % | 130 °C | 2.20 | **14 % high** |
| 402 | 97.7 % | 140 °C | 2.12 | **18 % high** |

**cp is back-solved, not guessed** (CLAUDE.md §1 permits sourced or back-solved): take `cp_water`
from steam tables, require the mass-weighted mixing rule to reproduce the model's own
`R323_CP_SOLN` at the design composition, and solve for the urea term. It yields **2.072 kJ/kg·K**,
and the published value for molten urea is ~2.0–2.1 — an *independent* corroboration, since nothing
in the derivation forced the answer to be physical. It is written as an expression rather than a
literal so it cannot drift out of step with `cp_water`, and a test asserts it stays in band.

**rho is regressed from the PFD**, which §0 makes the strict source: 12 urea-solution streams,
34–98 % urea, 40–183 °C →

    rho = 972.08 + 255.95·w_urea − 0.4659·(T − 100)     kg/m³

Both signs came *out* of the regression rather than being imposed — denser with urea, thinner when
hot — which makes the fit its own evidence. Worst residual 6.2 %, on the two HP synthesis streams
(207/208) that carry dissolved NH3/CO2 and so are not urea/water binaries at all.

**Bit-exactness.** Both are applied as a *departure* from the existing anchor,
`prop = ANCHOR + [raw(w,T) − raw(w_des,T_des)]`. At design the bracket is a literal `0.0` and
`ANCHOR + 0.0 == ANCHOR` in IEEE-754, so every licensor-published design value survives to the bit
and only the off-design response changes. Pin unmoved: `leaves 25 / keys 15 / diffs 0`.

Unit 324 now takes cp at each location's own composition: feed (80 %), Stage-1 melt (94.31 %),
Stage-2 melt (97.71 %). The **feed** cp appears in both the back-solved design duty and the tick and
was changed in both, so `dT/dt = 0` still holds at the seed *by construction*. The **holdup** cp
appears only as the denominator of the temperature ODE, where the design numerator is exactly 0, so
it cannot move the fixed point at any value — only the speed of approach.

### Still open

The analysis below on **water density above 150 °C** stands and is untouched: the PFD's density row
runs ~4 % higher than water can physically be at those temperatures, so a global correlation fitted
to the PFD would be wrong and one fitted to real water would contradict §0 at the design point. The
volumetric-controller densities (`RHO_744_KGM3`, `RHO_741_KGM3`, `R328_C002_RHO`, `R328_C004_RHO`
and the FIC anchors) are likewise unchanged. The anchored-departure helper `urea_soln_rho` is now in
place and is the natural vehicle when that work is scheduled.

### TD-013 — the 323D002 strength pin masks a 3.5-point composition gap (opened 2026-07-23)

`s.w_d002 = sol_pin_strength(sol_advance(...), R324_W_IN)` overwrites the 323D002 urea/water pair
with the constant 0.80 every tick. Two consequences, and the second is the serious one:

1. **No upstream composition disturbance reaches unit 324** — measured 0 of its 66 telemetry leaves
   (`EQUATION_AUDIT.md` audit section R).
2. ~~The 323 mass balance does not land on 80.00 — a 3.5-point gap.~~ **RETRACTED 2026-07-23.**

### Retraction — the "3.5-point gap" was my own bug, not a plant defect

The first write-up of this item claimed the 323 balance misses the PFD anchor by 3.5 points and
that the pin had been masking it. **That is false.** Three measurements settle it:

* `w_f010` — the 323F010 outlet, which is 323D002 Comp-I's **only** inlet — reads
  **80.0014 % urea** after 60 s. **Caveat, added after adversarial review: that is a transient
  reading, not a steady state** (see "Second correction" below). The tank structure is confirmed
  exactly single-inlet / single-outlet / no reaction / no vapour, and `w = w_in` is an exact fixed
  point of `sol_advance` for every holdup, flow and `dt` — so the tank tracks its inlet. What it
  does *not* do is converge to 80.00, because the inlet itself never settles.
* Comp-I holds 67 600 kg against a 92 749 kg/h draw, so it exchanges only
  **α = 9.5 × 10⁻⁵ of its holdup per tick**. The reverted patch measured its deviation against a
  reference captured *once*, then fed the result back into the state that produced it — a linear
  recursion whose fixed point is `w* = (A − ref)/α + w_f010`. **Any** constant inside that loop is
  amplified by **1/α ≈ 10 495**.
* Replaying that recursion with a capture error of **0.0003 percentage points** converges to
  **76.5150 %** — the observed failure value, to four decimals.

So the 3.5 points were manufactured by the patch. `scratchpad/probe_td013.py` and
`probe_td013_recursion.py` carry the arithmetic.

### What this rules out

The amplification is the real constraint on any fix, and it eliminates a whole class:

| form | fixed point | verdict |
|---|---|---|
| `auth = w_bal + (A − ref)` (the reverted patch) | `w_f010 + (A−ref)/α` | **amplified ×10 495** |
| `auth = w_bal + constant_offset` | `w_f010 + offset/α` | **amplified** |
| `auth = w_bal · constant_ratio` | badly offset | **amplified** |
| `auth = A + (w_f010 − W_F010_DES)` | `A` at design, tracks inlet | stable, but no tank lag |
| no pin at all | `w_f010` | stable, correct lag |

Only the last two survive. Choosing between them is a modelling decision, not a bug fix.

### Second correction — the mechanism, and the drift that was missed

Adversarial verification confirmed the headline (no 3.5-point gap) but refuted three details:

1. **"positive feedback runaway" is the wrong mechanism.** The recursion is a *stable contraction*
   — λ = 0.999905 < 1 for every `dt` > 0, so nothing diverges. The right description is **DC-gain
   amplification of a frozen constant**: `w* = w_f010 + (A − ref)/μ` with `1/μ = τ/dt`. Because
   μ = dt/τ, **halving the tick doubles the error** (1/μ = 10 495 at dt = 0.25, 5 248 at 0.5,
   2 624 at 1.0) — which is itself the proof that the construction was numerical, not physical.
2. **The capture error is properly sourced, not back-solved.** My "0.0003 pp" was fitted to match
   the observed value, so its agreement was circular. The real figure is the `_w_norm` residue on
   the PFD-317 row: that row sums to 99.99797, so `_w_norm` lifts 80.00 to
   `W_S317['Urea'] = 0.8000162403296788` while `R324_W_IN` is exactly 0.80. A − ref = −1.624e-05,
   which replayed reproduces **76.5137 %** against the reported 76.515 — 0.0013 pp, derived
   independently.
3. **`scratchpad/probe_td013.py`'s "unpinned" column is inert and proved nothing.** It drives its
   shadow tank with `m_in = s.tlag.get("R323_m317", 0.0)`; no such key exists, so m_in = 0 and
   `sol_advance` returns its input unchanged. That probe was cited as evidence in three documents.

**And the finding that was missed — see TD-014.** `w_f010` is on a perfectly linear ramp of
**−0.0067 pp/h that never arrests**. That is what actually governs the choice above.

Why the ripple break stayed hidden: Comp-I's time constant is ~44 min and no test runs long enough
to watch the tank converge.

## TD-014 — the 323 train's urea fraction is on a linear ramp that never arrests

- **Status:** OPEN — measured and characterised 2026-07-23, origin not yet located
- **Severity:** B (limits fidelity on long runs; no operator action triggers it)
- **Found by:** adversarial verification of TD-013, which asked the question TD-013 itself had not:
  *does the inlet actually settle?*

`w_f010` (PFD stream 317, the 323F010 outlet feeding 323D002) does not converge. It falls on a
**perfectly linear ramp of −0.0067 pp/h** and shows no sign of stopping:

| t | w_f010 |
|---|---|
| 60 s | 80.0013 % |
| 600 s | 79.9759 % |
| 6 h | 79.9239 % |
| 9.5 h | 79.9008 % |
| 14 h | 79.8704 % |

It is a **model property, not an integration artefact**. The least-squares slope is constant to
0.12 % across 12 h (−0.006694 pp/h in the 1.5–2.5 h window, −0.006686 in the 10.5–13.9 h window),
and it is tick-invariant to 0.4 % (dt = 1.0 → −0.006775; dt = 0.5 → −0.006792; dt = 0.25 →
−0.006801). An exponential fitted to the residual decay implies τ ≈ 8500 h (about a year), i.e.
not a settling transient on any operational timescale.

**It breaks a live assertion, just beyond every test's horizon.** `test_equation_audit_species.py:85`
asserts `|w_f010 − 80.00| < 0.10` pp but settles only 600 s. The real trajectory crosses 0.10 pp at
**≈ 9.5 h** of simulated time. Nothing in the suite runs that long, which is why it has never fired.

**Where the urea goes.** Over 14 h urea falls 0.131 pp while H₂O rises 0.118, Biuret 0.010,
NH₃ 0.003 and CO₂ 0.001 — the four gains sum to 0.131, so the vector is internally consistent and
urea is being displaced **predominantly by water**, not by biuret. The inlet to 323F010 drifts too
(`w_f004`, PFD stream 319, at −0.0044 pp/h), so **the origin is at or upstream of 323F004** and was
not traced further.

**Why it matters now.** It is the deciding constraint on TD-013. Dropping the D002 strength pin
gives the tank correct dynamics, but the tank then tracks this ramp: unpinned D002 sits 0.071 pp
low at 6 h and ~0.131 pp low at 14 h. So the drift must be understood before the pin comes out,
or the OTS acquires a slowly-wandering product spec.

**Separately — the pin is itself a component-mass source.** `sol_pin_strength` rewrites the
urea/water pair at constant total mass, so it fabricates **+0.600 kg of urea per 1000 kg of holdup
per call**, violating C2. Tested as a cause of the ramp and **refuted** (−0.00199 pp/15 min pinned
vs −0.00168 unpinned — comparable), so it is a separate, smaller defect, not this one.

### Dead constants found while auditing (2026-07-23)

Five density constants are **defined and never referenced** — they read as though density is
modelled at those points when nothing uses them: `CO2_RHO` (line 396), `SCRUB_CARB_RHO`,
`R323_C003_RHO`, `R323_F004_RHO`, `R323_F010_RHO`. Harmless at runtime, actively misleading to a
reader. Left in place deliberately for now (deleting them is a separate, trivially-reviewable
change) but they should not be mistaken for live property handling.
- **Files:** `backend/main.py` — `R323_CP_SOLN`, `R328_CP`, `A328_CP`, `R3232_CP`, `RHO_744_KGM3`,
  `R328_C002_RHO`, `R328_C004_RHO` and the rest of the density/cp constants

`tsat_steam`, `psat_water_bara` and `psat_nh3_bara` are live functions of state; liquid density and
cp are not. Volumetric controllers (FIC-323402, FIC-328402/404/406, FFIC-329401) are therefore blind
to thermal expansion: heat a stream and its true volumetric flow rises, but the simulated
transmitter does not see it.

### What the PFD's own density row says

The licensor tabulates `Density eff.` for every stream at its own temperature and composition — **43
distinct (T, w, ρ) liquid points** across PFD_20/21/22, and per CLAUDE.md §0 they outrank any
literature correlation. Tested against the standard Kell (1975) water fit
(`scratchpad/probe_c10_density.py`):

| stream | T °C | PFD ρ | Kell | error |
|---|---|---|---|---|
| 120 Proc. Con. | 60 | 983.27 | 983.20 | **−0.007 %** |
| 742G Pur. Pr. C | 88 | 966.40 | 966.65 | +0.026 % |
| 740 Pur. Pr. C | 89 | 965.74 | 965.99 | +0.026 % |
| 739 Pur. Pr. C | 143 | 923.28 | 923.31 | **+0.004 %** |

Four independent points under 0.03 %. This is the quantitative form of the claim made under TD-009
that the purified condensate simply *is* water — and stream 739's 923.28 also matches the Uhde
datasheet's 923.25 for 328C004 to 3 × 10⁻⁵.

### The finding that shapes the fix

**Above about 150 °C the PFD's density row is ~4 % higher than water can actually be.** Stream 747
is 99.02 % water at 200 °C and tabulated at 897.7 kg/m³; saturated water at 200 °C is 864.7, and
compressed liquid at its tabulated 16.6 bar is barely different. Stream 746 at 190 °C is tabulated
908.5 against ~876. The excess grows monotonically with temperature — +0.6 % at 148 °C, +3.7 % at
190 °C, +3.8 % at 200 °C — which is the signature of a property model that under-predicts thermal
expansion, not of the dissolved solids (0.76 % urea buys about 0.25 %).

So a single global correlation fitted to the PFD would be wrong, and a single global correlation
fitted to real water would contradict §0 at the design point. Neither is the answer.

### Fix when scheduled

Anchored ratio, the pattern already used for every other live property in this engine:

    rho(T) = RHO_DES * rho_ref(T) / rho_ref(T_DES)

Absolute value comes from the PFD at the design point (§0 satisfied, and the ratio is bit-exactly
1.0 there, so the pin cannot move); only the *derivative* comes from physics. `rho_ref` must be
valid past 150 °C — Kell is not, and drifts 3.7 % by 190 °C — so use an IAPWS saturated-liquid fit
over 0–250 °C. Same treatment for cp. Record explicitly that the PFD's above-150 °C densities are
followed at the anchor and departed from off it, with the numbers above as the justification.
