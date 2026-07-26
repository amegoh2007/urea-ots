"""As-Built reference: revision-history row 18 + Revision Delta #22."""
import io

P = "Urea OTS — As-Built Mathematical & System Architecture Reference.md"

raw = io.open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")

ROW_ANCHOR = "\n### Revision Delta — changes since the Rev-1 (2026-06-05) snapshot"
ROW = (
 "| 18 | 2026-07-23 | branch `master` | Equation audit remediation, slot 10 — **TD-014 root cause "
 "(open-loop temperature integrator), TD-013 closed, and cp made a property across units 323 and "
 "328.** The 323 train's urea fraction was on a linear −0.0067 pp/h ramp that never arrested and "
 "was tick-invariant, so it read as a model property. Walking the operator-supplied stream map "
 "(207 → 208 → 301/311 → 313 → 302/314 → 319 → 317) with every node instrumented showed the "
 "stripper bottoms **bit-flat for 6 h** while `w_c003` fell −0.0041 pp/h — the ramp is born in the "
 "stage, not carried in. A 2-minute-residence CSTR with constant inputs cannot ramp for 14 h, so an "
 "input had to be moving: the boil-up, falling 5.97 kg/h per hour, perfectly linearly. Cause: three "
 "stages take the energy-limited branch `m_vap = M_DES·(q_avail/Q_DES)` while their latent constants "
 "are back-solved from that same design duty, `λ = Q_DES/(M_DES/3600)`, so `P = q_avail − "
 "m_vap·λ/3600 ≡ 0` **identically at every load** — the temperature had no input, the controller "
 "integrated against zero gain, and its velocity increment Kc·(dt/Ti)·err walked the steam valve down "
 "forever at a dt-independent rate (hence the tick-invariance) and in one direction only (hence the "
 "monotone ramp), because the composition-split branch caps the other side. Fixed with the "
 "bubble-point relaxation 323F004 already used, giving `dT/dt = (T_bub − T)/τ`: 323C003's bubble "
 "point rides the live column pressure, 323F010's rides **composition** through Raoult on water, "
 "which is the real physics of a fixed-vacuum evaporator and makes TIC-323012 the concentration "
 "controller it is on the plant. Raoult is quoted, not fitted, and reproduces 88–99 % of a 20–90 °C "
 "elevation against the licensor's own (w, P, T) triplets; it is explicitly excluded at "
 "323C003/323F004, whose NH₃/CO₂-bearing liquors it overshoots by 33 °C and 16 °C. Every 323 node's "
 "slope is now exactly 0.0. **324E001/324E003 carry the same identity and are not fixed** — "
 "switching the closure on gives loops tuned against a zero-gain plant a real gain and they diverge "
 "(T_e003 → 138.5 °C in 6 h; bounded with both masters in MAN, which proves it is tuning, not the "
 "model). Carried as TD-015 with a measured recommendation. With the inlet stationary the only "
 "argument for the **323D002 strength pin** was gone, so it was dropped (TD-013 closed, option (c)): "
 "the tank tracks 323F010 with its own residence-time lag, the last composition-blind node between "
 "reactor and evaporators is open, and a C2 violation (+0.600 kg urea fabricated per 1000 kg holdup "
 "per call) goes with it. The vessel was rebuilt to its real topology — Comp I 80 m³ active, Comp II "
 "300 m³ passive, and the **field tie-in spool** between them as an operator boolean on screen "
 "323-1; opening it against a dry Comp II collapses a 10 % head from 80 m³ into 380 m³ (10 % → "
 "2.1 %), the hazard it exists to train. Three constants corrected from source: LIC-323507 setpoint "
 "65 % → **10 %** (the compartment exists to hold residence under ~6 min so biuret cannot form), "
 "ρ 1300 → **1151 kg/m³** (PFD stream 315/317), Comp II seed 50 % → **0 %**. TI-323008 became a real "
 "state. Finally **cp is a property, not a constant**: one lumped 2.5 kJ/kg·K covered the whole 323 "
 "train (44 % @ 40 °C to 80 % @ 99 °C, a 30 % spread) and one 4.0 covered every aqueous vessel from "
 "40 to 200 °C — both replaced by per-stream/per-vessel departures anchored on their own design "
 "point. `R3232_CP` deliberately left alone: that liquor is carbamate, not water. Pin unmoved "
 "throughout: `leaves 25 / keys 15 / diffs 0`. See Revision Delta #22. |"
)
if s.count(ROW_ANCHOR) != 1:
    raise SystemExit("row anchor not unique")
s = s.replace(ROW_ANCHOR, "\n" + ROW + ROW_ANCHOR)

TAIL = "\n---\n\n*End of Document — Urea OTS As-Built"
if s.count(TAIL) != 1:
    raise SystemExit("tail anchor not unique")

DELTA = r"""
---

## Revision Delta #22 — the degenerate stage-temperature ODE, and 323D002 as a real vessel (2026-07-23)

### 22.1 The defect: an energy balance that cancels itself

Three stages compute their vapour rate as *whatever the available duty can boil*,

$$\dot m_{vap} = \dot m_{vap,des}\cdot\frac{q_{avail}}{Q_{des}},\qquad
q_{avail} = \dot m_{in}c_p(T_{in}-T) + Q$$

while each stage's latent constant is **back-solved from that same design duty** so that
$dT/dt = 0$ at the seed,

$$\lambda = \frac{Q_{des}}{\dot m_{vap,des}/3600}\;\Longrightarrow\;
\frac{\dot m_{vap,des}\,\lambda}{3600\,Q_{des}} = 1 .$$

Substituting the first into the stage energy balance:

$$P = q_{avail} - \frac{\dot m_{vap}\lambda}{3600}
    = q_{avail}\left(1 - \frac{\dot m_{vap,des}\lambda}{3600\,Q_{des}}\right)
    = q_{avail}\,(1-1) = 0$$

**identically, for every $q_{avail}$, at every load.** The stage temperature has no input: any change
the controller makes to the reboiler is cancelled exactly by the boil-up it produces. The PV never
leaves the $10^{-5}$ °C residue of the boot settle, and the velocity-form integral
$\Delta u = K_c(\Delta t/T_i)\,e$ walks the steam valve monotonically forever. Two signatures follow
directly and both were measured: the walk **rate** is independent of $\Delta t$ (so the drift looked
tick-invariant, i.e. "physical"), and it is **one-sided**, because the composition-split branch of
the `min()` caps the opposite direction — hence a monotone ramp rather than a random walk.

Identity value, all four affected stages, asserted in `test_equation_audit_td014.py`:

| stage | $\dot m_{vap,des}\lambda/(3600 Q_{des})$ |
|---|---|
| 323C003 | 1.000000000000000 |
| 323F010 | 1.000000000000000 |
| 324E001 | 1.000000000000000 |
| 324E003 | 1.000000000000000 |

### 22.2 The closure: bubble-point relaxation

The liquid sits at its bubble point, so the duty *not* spent boiling walks the holdup toward it over
the stage's own residence time — the closure 323F004 already carried:

$$q_{relax} = \frac{M\,c_p\,(T_{bub}-T)}{\tau},\qquad
\dot m_{vap} = \dot m_{vap,des}\cdot\frac{q_{avail}-q_{relax}}{Q_{des}}
\;\Longrightarrow\; P = q_{relax}
\;\Longrightarrow\; \frac{dT}{dt} = \frac{T_{bub}-T}{\tau}$$

Energy is still conserved; the temperature is now a genuine state with a genuine driver. At design
$T = T_{bub}$, so $q_{relax}$ is a literal $0.0$, $q_{avail}-0.0 = q_{avail}$ bit-identically, and the
design vapour rate is reproduced exactly (the `min()` ties on two identical values).

**323C003** — its bubble point rides the live column pressure PT-323201, which is itself driven by
the live top-vapour rate, so TIC-323007 gains a correctly-signed plant: more duty → more stream 305 →
higher $P$ → higher $T_{sat}$ → higher $T$. Its composition offset stays frozen at the design value
because this liquor's vapour is 33 % NH₃ / 50 % CO₂: its bubble point sits **9.8 °C below** water's
saturation temperature at 4.1 bar a, a *depression* that Raoult-on-water cannot produce.

$$T_{bub,C003} = T_{des} + \big[T_{sat}(P_{live}) - T_{sat}(4.1)\big]$$

**323F010** — a fixed 0.46 bar a vacuum boundary, so pressure is not a lever and **concentration**
is. That is the physics of a vacuum evaporator, and it makes TIC-323012 what it is on the plant: a
concentration controller acting through temperature.

### 22.3 The bubble-point model — Raoult, quoted not fitted

Water is the only volatile in these liquors. Its partial pressure over the solution is
$x_{H_2O}\,P^{sat}(T)$, and at the bubble point that equals the stage pressure:

$$T_{bub} = T_{sat}\!\left(\frac{P}{x_{H_2O}}\right),\qquad
x_{H_2O} = \frac{w_{H_2O}/M_{H_2O}}{\sum_i w_i/M_i}$$

Urea, biuret and HCHO raise the boiling point purely by diluting the water **on a mole basis**,
which is why the mass-fraction vector has to be converted first. Nothing is adjustable. Validated
against the licensor's own $(w, P, T)$ triplets:

| stage | composition | $P$ | Raoult | PFD | error | elevation captured |
|---|---|---|---|---|---|---|
| 323F010 | 80.00 % urea | 0.46 bar a | 100.3 °C | 99 °C | +1.3 | 107 % |
| 324E001 | 94.31 % urea | 0.33 bar a | 123.7 °C | 130 °C | −6.3 | 89 % |
| 324E003 | 97.71 % urea | 0.131 bar a | 132.7 °C | 140 °C | −7.3 | 92 % |

The residual is non-ideality ($\gamma_{H_2O} < 1$ at these strengths) and is absorbed by the design
anchor, because every call site uses the **departure**
$T_{des} + [\,T_{bub}(live) - T_{bub}(des)\,]$. For a control model the quantity that must be right
is the *slope* against composition, and that is what Raoult supplies. It is **not** valid at
323C003 (+33 °C) or 323F004 (+16 °C), where NH₃ and CO₂ set the bubble point; a test asserts that
overshoot so the two forms are never unified.

### 22.4 Result, and what remains

With the feed held flat for 6 h the least-squares slope at every node of the 323 train is **exactly
0.0** in the second half; `w_f010` settles at 79.9635 % and stays. The 0.037 pp under the PFD-317
anchor is where the *live* stripper bottoms put it (55.838 % against a tabulated 55.867 %), not a
drift. PIC-329202 and PIC-329208 are flat to five decimals over the same window, against 0.0104 %/h
and 0.0085 %/h before.

324E001 and 324E003 are **not** fixed. Switching the same closure on there gives two loops a real
process gain for the first time; their tuning ($K_c = 2.0$ bar/°C, $T_i = 120$ s) was chosen against
a zero-gain plant and carries no information about the real one, and they diverge — $T_{e003}$ to
138.5 °C and PV-329212 to 86.6 % within 6 h. With both masters in **MAN** the same stages are bounded
within 0.02 °C of design, which is the proof that this is a tuning problem and not a model
instability. Carried as **TD-015**, with the live driver published every tick as
`_DIAG['E001']['dTbub']` so the size of the gap stays visible.

### 22.5 323D002 — the pin dropped, and the vessel rebuilt

The only argument for the 323D002 strength pin was that its single inlet was drifting. It is not any
more, so the pin is gone: $w_{D002}$ is a plain `sol_advance` and the tank tracks 323F010 with its
own residence-time lag. That opens the last composition-blind node between the reactor and the
evaporators, and removes a C2 violation — `sol_pin_strength` rewrote the urea/water pair at constant
total mass, fabricating **+0.600 kg of urea per 1000 kg of holdup per call**.

The vessel is now modelled as it is built. Comp I (80 m³) is active and carries every nozzle,
LIC-323507, TI-323008 and the 323P003A/B suction; Comp II (300 m³) is passive with LI-323504 for
indication and alarms only, and fills solely by spilling the internal baffle. Between them is a
**field tie-in spool** — a hand valve, no licensor loop number. Shut (default) the compartments are
independent and anything in Comp II is stranded; open they are connected vessels sharing a *head*,
so an equal level fraction:

$$f = \frac{M_I + M_{II}}{M_{I,full} + M_{II,full}},\qquad M_I = f\,M_{I,full},\quad M_{II} = f\,M_{II,full}$$

and 323P003 draws the pooled inventory. Opening it against a dry Comp II is a real hazard the model
now reproduces: a 10 % Comp-I head redistributes over 380 m³ instead of 80 and collapses to **2.1 %**,
leaving the pump near its cavitation limit.

Three constants corrected from source: LIC-323507's setpoint **65 % → 10 %** (the compartment exists
to hold residence under ~6 min so biuret cannot form — at 65 % the model declared a 39-minute
residence and roughly six times the designed exposure), $\rho$ **1300 → 1151 kg/m³** (the PFD's own
figure for streams 315/317), and Comp II's seed **50 % → 0 %** (it is dry in normal operation; a
50 % seed silently declared a 173 t inventory the plant would alarm on).

### 22.6 cp is a property, not a section constant

One lumped $c_p = 2.5$ kJ/kg·K covered the entire 323 train and one $c_p = 4.0$ every aqueous vessel.
Both are replaced by departures anchored on their own design point, so each returns the licensor's
constant bit-exactly at the seed:

| stream | composition / T | design $c_p$ |
|---|---|---|
| 208 stripper bottoms | 55.87 % @ 119 °C | 3.029 |
| 314 column bottoms | 68.74 % @ 135 °C | 2.760 |
| 319 flash liquid | 71.74 % @ 106 °C | 2.679 |
| 317 product (**anchor**) | 80.00 % @ 99 °C | 2.500 |
| 331 granulation return | 44.37 % @ 40 °C | 3.248 |

— a 30 % spread the single constant was flattening, and each site now takes the cp of the stream it
belongs to (feed terms the feed's, holdup denominators the holdup's; 323F010's two feeds no longer
share one value). The aqueous vessels 328C002/C003/C004, 328D001, 328D003 Comp I/II and 322C001 call
`aqueous_cp()` against IAPWS, each anchored on its own design temperature — 4 % low at the cold end
and 11 % low in the 200 °C hydrolyser before. `R3232_CP = 3.0` is deliberately left alone: 323E003 /
323E011 carry a strong ammonium-carbamate liquor, not water, so `aqueous_cp` is the wrong
correlation and converting it would be a fabrication rather than a fix.
"""

s = s.replace(TAIL, DELTA + TAIL)
if crlf:
    s = s.replace("\n", "\r\n")
io.open(P, "w", encoding="utf-8", newline="").write(s)
print("patched", P)
