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

- **Status:** OPEN
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

- **Status:** OPEN
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
