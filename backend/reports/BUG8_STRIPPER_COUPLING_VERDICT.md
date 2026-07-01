# Bug 8 Verdict — HV-322605 → 322E001 Stripper-Level Coupling

**Scope:** Determine whether the HV-322605 (HIC_322605, reactor 322R001 bottom take-off) →
322E001 HP-stripper bottom-sump level coupling is a code defect (dead / non-conservative
indicator) or physically correct behavior.
**Method:** `scratchpad/probe_bug8_stripper.py`, `scratchpad/probe_bug8_massbal.py`
(forward integration of `step_sim`, no model edits).
**Discipline:** systematic-debugging Iron Law — *no fix without confirmed root cause*.

---

## 0. Origin of the question

`VALVE_INDICATOR_AUDIT.md` flagged **HV-322605 → LT-322504** (reactor level) as
"FLAT / defensible weir self-regulation." That reactor-level branch was reclassified and
fixed as **Bug 7** (shadow-datum load gate; LT-322504 now carries load authority, matrix
d = −100). **Bug 8** is the sibling: does HV-322605 correctly drive the **stripper** sump
level (LI-322501), or is that indicator dead / leaking mass?

---

## 1. Physical chain (structurally confirmed)

$$\text{HIC\_322605}\;\xrightarrow{\text{outlet\_line\_outflow}}\;\dot m_{out}\;\xrightarrow{f_{strip}=\dot m_{out}/\dot m_{ov,split}}\;\text{react\_overflow\_kmolh}\;\xrightarrow{\text{stripper\_322e001}}\;\text{bot\_kgh}\;\xrightarrow{\text{sump ODE}}\;\text{strip\_level}$$

Sump level ODE (`main.py` L1888–1891):

$$m_{span}=A_{sump}\,H_{span}\,\rho_{bot},\qquad
\text{strip\_level}\;\mathrel{+}=\;\frac{\dot m_{bot}-\dot m_{drain}}{3600}\cdot\frac{dt}{m_{span}}\cdot100$$

under LIC-322501 direct-acting velocity-form PI on LV-322501
($K_c=2.5,\ T_i=90\text{ s}$).

---

## 2. Decisive test — LIVE vs DEAD coupling

A closed-loop level held at SP under AUTO cannot distinguish a live-but-rejected
disturbance from a dead indicator. **Freeze the drain valve (LIC-322501 → MANUAL)** and
move HV-322605: a live coupling must move the level (no drain compensation).

| Run | HV-322605 | feed `bot_th` Δ | LV op Δ | strip_level base → final |
|---|---|---|---|---|
| AUTO  open | 60→90 % | −7.78 t/h | −4.30 % | 50.000 → **50.000** (peak 50.58) |
| **MAN open** | 60→90 % | −7.78 t/h | 0.00 % (frozen) | 50.000 → **14.67** (Δ −35.3 %) |
| **MAN close** | 60→30 % | −45.76 t/h | 0.00 % (frozen) | 50.000 → **0.00** (Δ −50.0 %) |

**→ Coupling is LIVE.** With the drain frozen the level swings hard (−35 % / −50 %). Under
AUTO the LIC drives LV-322501 (op −4.3 %) and returns the level to SP — **correct
closed-loop rejection, not a dead indicator.**

---

## 3. Mass conservation (settled, per HV-322605 setting)

| HV-322605 | overflow feed (t/h) | top_th | bot_th | top+bot (t/h) | (top+bot) − feed |
|---:|---:|---:|---:|---:|---:|
| 30 % | 130.36 | 100.26 | 84.72 | 184.98 | **+54.62** |
| 60 % | 226.18 | 150.32 | 130.48 | 280.80 | **+54.62** |
| 90 % | 326.64 | 258.56 | 122.70 | 381.26 | **+54.62** |

- Reactor→stripper **feed is monotonic** in HV-322605 (130 → 226 → 327 t/h) — opening the
  bottom take-off sends more liquid to the stripper (correct sign, matches DCS field
  sign-check in `dcs_tuning_parameters.md` §3).
- Stripper **total throughput (top+bot) is monotonic** (185 → 281 → 381 t/h).
- **(top+bot) − feed = +54.62 t/h, constant to 2 dp** across all three settings — the
  invariant live-CO₂ strip-gas + steam mass added overhead. Mass is conserved exactly; the
  reactor feed passes through with nothing created or destroyed.

The stripper split is conservative **by construction** (`main.py` L642–648):
$\text{top}[k]=\text{avail}[k]\,f,\ \text{bot}[k]=\text{avail}[k]\,(1-f)\Rightarrow
\text{top}[k]+\text{bot}[k]=\text{avail}[k]$; the hydrolysis and biuret reactions are
atom-balanced ($60+18=2\cdot17+44=78$; $2\cdot60=103+17=120$).

The non-monotonic `bot_th` (130.5 → 122.7 at 90 %) is the split sending more volatile
NH₃/CO₂ **breakthrough overhead** at high throughput (`slip` term), i.e. a mass-conservative
redistribution top↔bot — **not a leak**.

---

## 4. Verdict — **NO CODE DEFECT (defensible)**

1. Coupling is **live** — stripper level responds to HV-322605 (MANUAL: −35 % / −50 %).
2. Mass is **conserved** — feed and total throughput monotonic; overhead offset invariant.
3. AUTO flatness is **correct LIC-322501 disturbance rejection**, not a dead indicator.

Consistent with `VALVE_INDICATOR_AUDIT.md` ("defensible weir self-regulation"). Per the
systematic-debugging Iron Law there is **no confirmed root cause**, so **no fix is applied**;
fabricating one would break a working, mass-conservative coupling and bust the bit-exact
boot pin (LI-322501 = 50.0000 %, LT-322504 = 80.0000 %) for zero benefit — contrary to the
project conservation + Sourcing laws.

**No `main.py` change. No verification suite re-run required (no code changed). No commit.**

---

## 5. Queue status

Bugs 1–7 fixed + verified (all design pins bit-exact, full audit 0 FAIL). **Bug 8 →
investigated → no-defect.** Audit queue closed.
