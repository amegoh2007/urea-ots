## Revision Delta #20 — 322E001 per-species enthalpy balance, derived flooding knockdown, live $\eta_P$ (2026-07-23)

### 20.1 The duty was blind to composition

Superseded form — duty proportional to feed **mass**:

$$Q_{strip} = Q_{des}\cdot\frac{\dot m_{feed}}{\dot m_{feed,des}}$$

Identical tonnages of pure water and of carbamate-rich reactor liquor therefore demanded identical
steam, and the largest heat sink in the unit was invisible to the MP header. Replaced by a
five-term balance, every constant sourced:

$$Q_{raw} = \underbrace{n_{CO_2}^{des}\,\Delta H_{carb}}_{\text{dissociation}}
          + \underbrace{n_{NH_3}^{free}\,\Delta H_{NH_3}}_{\text{desorption}}
          + \underbrace{n_{H_2O}^{top}\,\lambda_{H_2O}}_{\text{latent}}
          + \underbrace{\xi_{hyd}\,\Delta H_{hyd}}_{\text{hydrolysis}}
          + \underbrace{\dot m_{bot}c_{p,b}(T_b-T_f)+\dot m_{top}c_{p,g}(T_t-T_f)}_{\text{sensible}}$$

with $n_{CO_2}^{des}=y_{CO_2}^{top}-y_{CO_2}^{sweep}$ — the CO₂ sweep enters already as gas and
needs no dissociation heat — and $n_{NH_3}^{free}=y_{NH_3}^{top}-y_{NH_3}^{sweep}-2\,n_{CO_2}^{des}$
from the 2:1 carbamate stoichiometry.

**Constants.** Frejacques, quoted in Brouwer, *Thermodynamics of the Urea Process*, UreaKnowHow
Process Paper June 2009 p.12, at **process** conditions rather than the 25 °C standard state:
$\Delta H_{carb}=+117$ kJ/mol (110 atm, 160 °C) and $\Delta H_{hyd}=-15.5$ kJ/mol (160–180 °C).
NH₃ is supercritical at stripper temperature ($T_c=132.4$ °C), so $\Delta H_{NH_3}$ is a
*desorption* enthalpy — the loop's own `HPCC_BUB_DHVAP_JMOL` — and not a latent heat at all.

**Validation.** The five terms summed over the design streams, with nothing fitted and no free
parameter, give $37\,831$ kW against the licensor's $Q_{des}=39\,400$ kW — **96.0 %**. Only the
ratio is applied:

$$Q_{strip} = Q_{des}\cdot\frac{Q_{raw}}{Q_{raw,des}},\qquad
\left.\frac{Q_{raw}}{Q_{raw,des}}\right|_{des} = \frac{X}{X} = 1.0\ \text{(bit-exact)}$$

so the 4 % absolute offset cancels, never reaches the steam header, and the PFD duty remains the
anchor rather than a computed quantity.

| term | kW | share |
|---|---:|---:|
| carbamate dissociation | 22 118 | 58 % |
| free-NH₃ desorption | 14 123 | 37 % |
| water latent | 2 803 | 7 % |
| urea hydrolysis (liquid step) | −379 | — |
| sensible, both products | −834 | — |

### 20.2 The unsourced constant, retired

Delta #19 flagged `STRIP_FLOOD_ETA_K = 1.50` as the single number in the unit without a source. It
required no replacement constant, because $\Delta T_{flood}$ and the efficiency loss are the same
event measured two ways — the bottom runs hotter *precisely because* the dissociation endotherm did
not happen:

$$g_{flood} = 1 - \frac{\dot m_{feed}\,c_p\,\Delta T_{flood}}{n_{carb}\,\Delta H_{carb}}$$

$\Delta T_{flood}\equiv 0.0$ below the flooding limit, so $g_{flood}\equiv 1.0$ at design — a
structural identity, not a float-operand-ordering argument. Cross-checks at 10 % over the limit:
this energy balance **2.9 %**, Brouwer's Shangdong Hualu Hengsheng case study (a 3 °C bottom-
temperature shift alongside a 79 % → 81 % efficiency change) **2.5 %**, and the licensor length
correlation from the same paper (6 m eff. → 80 %, 8 m → 82 %) **0.8 %** — against **15 %** from the
retired fit, which was additionally double-counting the thermal collapse $g_T$ already carries.

### 20.3 $\eta_P$ — a dead lever

$\eta_P = \mathrm{clamp}\!\left(2-P/P_{des},\,0.85,\,1.15\right)$ was recomputed on every tick from
an argument that every call site passed as the frozen $P_{des}$. It was therefore identically 1.0,
and synthesis pressure had **no** effect on stripping efficiency — physically wrong, and invisible
to the pin gate precisely because a dead lever perturbs nothing. Now

$$P_{live} = P_{des}\cdot\frac{p_{syn}}{p_{syn,des}}$$

which is exactly $P_{des}$ at design since $p_{syn}\equiv p_{syn,des}$ there. Gated on
`_STEAM_READY` exactly as `step_steam` is: the fix introduces a feedback path that did not
previously exist, and the boot-pin settle would otherwise capture `HPCC_UA` and `HPCC_LIQ_DES_LIVE`
off a different transient (measured +305 kg/h, 0.16 %). Those are *calibration* constants; they
must not depend on which transient reached the design point.

---

## Revision Delta #21 — C10 urea-solution properties, and the ripple break (2026-07-23)

### 21.1 Properties as a departure from the anchor

Both correlations are applied as a *departure*, never as an absolute. That is what preserves every
licensor-published design value to the bit:

$$\phi(w,T) = \phi_{anchor} + \big[\phi_{raw}(w,T) - \phi_{raw}(w_{des},T_{des})\big]$$

At the design composition the bracket is a literal $0.0$, and $\phi_{anchor}+0.0=\phi_{anchor}$
exactly in IEEE-754.

**Heat capacity — back-solved, not guessed.** With $c_{p,w}$ from steam tables (quadratic least
squares over 20–200 °C, worst residual 0.0085 kJ/kg·K), $c_{p,u}$ follows from requiring the
mass-weighted mixing rule to reproduce the model's own design anchor:

$$c_{p,u} = \frac{c_{p,des} - (1-w_{des})\,c_{p,w}(T_{des})}{w_{des}} = 2.072\ \text{kJ/kg·K}$$

The published value for molten urea is 2.0–2.1 kJ/kg·K. Nothing in the derivation forced the answer
to be physical, so that agreement is an *independent* corroboration rather than a restatement. The
solution property is then $c_p(w,T)=w\,c_{p,u}+(1-w)\,c_{p,w}(T)$.

**Density — regressed from the PFD**, which §0 makes the strict source (12 urea-solution streams,
34–98 % urea, 40–183 °C):

$$\rho = 972.08 + 255.95\,w_{urea} - 0.4659\,(T-100)\quad\text{kg/m}^3$$

Both signs came *out* of the regression rather than being imposed — denser with urea, thinner when
hot — which makes the fit its own evidence. Worst residual 6.2 %, on streams 207 and 208, the HP
synthesis streams carrying dissolved NH₃/CO₂ that are not urea/water binaries at all.

**Unit 324** now evaluates $c_p$ at each location's own composition — feed 80 %, Stage-1 melt
94.31 %, Stage-2 melt 97.71 % — where a single 2.5 kJ/kg·K previously ran 14–18 % high at the
evaporator ends and 23 % low at the LP end. The *feed* $c_p$ appears in both the back-solved design
duty and the tick and was changed in both, so $dT/dt=0$ still holds at the seed **by construction**.
The *holdup* $c_p$ enters only as the denominator of the temperature ODE, where the design numerator
is exactly 0 — so no value of it can move the fixed point, only the speed of approach.

### 21.2 The ripple break

$$\text{was:}\quad w_{D002} \leftarrow \mathrm{pin}\big(\mathrm{advance}(\cdot),\ W_{IN}\big)
\qquad\Longrightarrow\qquad w^{urea}_{D002} \equiv 0.80\ \text{on every tick}$$

The 323D002 tank strength was pinned to the **constant** $W_{IN}$, so `sol_pin_strength` overwrote
the urea/water pair each tick and every upstream composition disturbance died in the buffer tank.
Measured: a +4 % NH₃ step on the live reactor overflow (water traded down, total moles held) moved
222 of 1162 telemetry leaves — and **0 of unit 324's 66**. The block's own comment claimed it gave
324 "a real composition instead of a constant"; the next line took it away.

The pin retains its §0 job — holding the PFD-published strength against percentage-rounding creep
across 324E001/E003 — but now carries the live deviation rather than overwriting it:

$$w_{auth} = W_{IN} + \big(w^{urea}_{bal} - w^{urea}_{bal,des}\big)$$

which is exactly $W_{IN}$ at the seed. After the fix 246 leaves respond and **every unit group in
the train** does, unit 324 included at 13 of 66, first responding at tick 39 — the 80 m³ buffer-tank
holdup lag, which is physically correct.

---

