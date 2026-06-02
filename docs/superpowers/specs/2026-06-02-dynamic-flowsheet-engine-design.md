# Dynamic Flowsheet Engine — Design Spec

**Date:** 2026-06-02
**Sub-project:** 1 of a 7-item batch (foundation-first sequencing)
**Status:** Approved design → pending spec review → writing-plans

**Rev 2 (2026-06-02):** Frontend pivots from SVG re-draw to **image-backed UI** — the
cleaned DCS screenshot (static transmitter values erased) is the screen background; live
values, faceplates, trends, and stream popups are overlaid at the image's pixel
coordinates. This voids §6.5's SVG stream re-trace and the green-network deferral (the
image carries every line — magenta and green — exactly). Backend engine §2–§5 and
Appendix A are unchanged; the tag registry now feeds overlay divs instead of SVG text.
Scope of Rev 2: screens **321-1** and **322-2** only. See §6, §6.5, §7, §9.

---

## 1. Purpose

Make all modelling in the Urea OTS **dynamic**: changing any valve opening, stream
property, or composition must propagate to **all downstream (D/S) streams,
transmitters, and equipment** through their related modelling equations. Replace the
flat per-tick procedural body of `backend/main.py` with a **sequential-modular
(topological) flowsheet graph** of `Stream` and `Equipment` nodes, while preserving
every existing equation verbatim.

This sub-project also folds in two quick wins and the first visible payoff:
- Quick win #2: Screen 321 XVs not displaying — restore visible OPEN/CLOSED icons.
- Quick win #3: Top tabs show screen **number only** ("322", not "322-2 HP SCRUBBER").
- Payoff #7 (F001 path): indicator→stream binding correctness, e.g. `PT-329201` (overlaid
  on the 322E003→322F001 line in the image) reads **that line's** pressure (`s_E003.P_bara`).
  Stream-line *mapping* is now inherent in the cleaned screenshot background (Rev 2).

### Out of scope (deferred to their own specs)
- #4 Transmitter editor UI (add/remove/edit/reposition) + backend JSON layout store.
- #5 Empty-slot rendering for unbinded transmitters (instruction recorded now; UI later).
- #6 Full visual polish pass across all screens.
- (Voided by Rev 2) Exhaustive re-trace of the green CPL/process network and the magenta
  carbamate path: no longer needed. The cleaned DCS screenshot is the background, so every
  stream line — magenta and green — is pixel-exact by construction. Indicator-on-line
  correctness is achieved by overlaying each transmitter div at the value's pixel position
  in the image (§6, §6.5).

### Constraints honored
- **ONE-UNIT rule:** engine refactors the *existing* units only (BL feed, 321D003,
  321P002A/B, header, 322E003 boundary, 322F001, CO2/ratio). No downstream units added.
- **Mathematical fidelity:** equations reorganized into nodes, never re-derived,
  approximated, or condensed. Full equation set preserved (Appendix A).
- **Fidelity by construction:** the DCS is rendered as its own cleaned screenshot; no
  element is redrawn or repositioned. Overlays register to the image, not the reverse.
- **Packet strategy A (additive):** keep all current bespoke packet keys (no frontend
  break) AND add generic `streams{}` + `tags{}` maps derived from the graph.

---

## 2. Architecture

### 2.1 `Stream` (canonical process stream, extensive basis)

State carried:
- `comp` : dict component → mass flow [kg/h]  *(the primary state)*
- `T_C`  : temperature [°C]
- `P_bara` : pressure [bar a]
- `rho`  : effective density [kg/m³]

Derived on demand (no stored duplication):

$$\dot m=\sum_k \dot m_k,\qquad n=\sum_k \frac{\dot m_k}{MW_k},\qquad
\overline{MW}=\frac{\dot m}{n},\qquad w_k=\frac{\dot m_k}{\dot m},\qquad
\dot V=\frac{\dot m}{\rho}$$

`MW_COMP` table is unchanged:
`{CO2:44.0098, CH4:16.043, H2:2.0158, H2O:18.0152, N2:28.0134, NH3:17.0304,
O2:31.9988, Urea:60.056, Biuret:103.081}`.

### 2.2 `Equipment` node

Interface: `evaluate(inlets: list[Stream], params: dict) -> (outlets: list[Stream], vars: dict)`.
One node per existing unit. Internal/sensor variables (tank level, tank T, pump
current, totalizer) live in `vars`. Pure function of inlets+params+prior internal state.

### 2.3 `Graph` (sequential-modular solver)

- Connections declare named streams (`producer → stream_id → consumer`).
- Topological order derived from connectivity; each tick the graph is walked once
  upstream→downstream. Deterministic, real-time.
- **Tear hook:** a tear-stream list seeds consumers with last-tick values for closed
  recycles. No closed recycle exists yet → list empty → no-op. (Hook present so future
  recycles need no architecture change.)

---

## 3. Node & stream map (existing units only)

```
BL NH3 feed ──s_BL──▶ [321D003 drum] ──s_suct──▶ [321P002A] ─┐
                                       └────────▶ [321P002B] ─┴─s_dischAB─▶ [header ⨂ XV-322901] ──s_motive──▶ [322F001 ejector] ──s_disch──▶ (322E002 boundary)
322E003 overflow ──s_E003───────────────────────────────────────────────────────────────────────────────────┘ (suction inlet)
CO2 feed (boundary) ─────────────▶ ratio block (sensor over pump mass flows; not a stream transform)
```

| Stream id | From → To | Carried by indicators |
|-----------|-----------|-----------------------|
| `s_BL` | BL feed → 321D003 | (AL feed) |
| `s_suct` | 321D003 → pumps | PT-321201/202 (feed P), suction header |
| `s_dischAB` | pumps → header | FT-321401, TT-321020, PI-321203 |
| `s_motive` | header(⨂XV-322901) → 322F001 | FI-322012 (motive) |
| `s_E003` | 322E003 overflow → 322F001 suction | **PT-329201/PI-329201, TI-322002** |
| `s_disch` | 322F001 → 322E002 | TT-322012, PI-322012, FI-322013, MW |

### Node responsibilities (equations in Appendix A)
- **BL NH3 feed (boundary source):** pure NH3 at `F_in_BL_th`, `T_BL_FEED_C = 25 °C`.
- **321D003 drum:** mass balance → level; energy balance → `tank_T_C`; tops pressure;
  emits `s_suct`. Vars: `tank_level_frac`, `tank_T_C`, `totalizer_t`.
- **321P002A / 321P002B:** triplex PD pump. params `{on, opening%}`; opening→rpm→Q→mass
  flow; discharge enthalpy rise sets `s_dischAB` T. Vars: `speed_act`, `current`, `mode`.
- **header ⨂ XV-322901:** sums A+B NH3; gated by XV-322901 (closed → zero) → `s_motive`.
- **322E003 overflow (boundary source):** carbamate at `EJ_CARB_FRAC`, `T = EJ_T_SUCTION_C
  = 178.8 °C`, `P = EJ_P_DISCH_BARA = 144.2 bar a` → `s_E003`. **This stream backs
  PT-329201 / TI-322002.**
- **322F001 ejector:** inlets `s_motive` + `s_E003`; param `HIC_322602`; entrainment μ,
  component balance, energy balance → `s_disch`.
- **ratio block:** molar N/C sensor over pump mass flows + CO2 feed.

---

## 4. Tag registry (binding model)

Single source of truth `TAG → resolver`, resolver references a stream property or an
equipment var. Resolved each tick into packet `tags{ TAG: {v, unit, alarm} }`. This is
where the #7 mis-bindings are corrected:

| Tag | Previous (wrong/static) | Corrected resolver |
|-----|-------------------------|--------------------|
| `PT-329201` | ejector discharge P | **`s_E003.P_bara`** |
| `TI-322002` | hardcoded `178.8` | **`s_E003.T_C`** |
| `TT-322012` | ejector T (ok) | `s_disch.T_C` |
| `FI-322012` | motive (ok) | `s_motive.total_kgh` |
| `FI-322013` | total (ok) | `s_disch.total_kgh` |
| `HIC-322602` | spindle opening (ok) | `ejector.HV_open_pct` |

Effect: HV-322602 change → μ change → `s_disch` **and** `s_E003`-bound readings move
live; every bound transmitter and every stream popup updates from one computation.

> **Label note:** the current UI element on the 322E003→322F001 line is labeled
> `PI-329201` (app.js `TAG_MAP`, index.html `data-tip`); the user refers to it as
> `PT-329201`. They are the same indicator. It reads pressure, so the plan resolves the
> label to `PT-329201` for correctness while keeping its position fixed.

---

## 5. Packet contract (additive)

`step_sim` returns, in addition to **all current bespoke keys (unchanged)**:

```jsonc
"streams": {
  "s_E003":  { "T_C":…, "P_bara":…, "total_kgh":…, "total_th":…,
               "mol_kmolh":…, "MW":…, "rho":…, "vol_m3h":…, "comp_pct": {…} },
  "s_motive":{ … }, "s_disch": { … }, "s_suct": { … }, "s_dischAB": { … }
},
"tags": { "PT-329201": {"v":144.2,"unit":"BAR A","alarm":false}, … }
```

Bespoke keys (`FI_321401`, `EJ_322F001`, `SIC_321950`, …) remain and are **computed from
the graph**, so the existing frontend keeps working with zero changes except the four
binding fixes below.

---

## 6. Frontend changes — image-backed UI (Rev 2)

Screens **321-1** and **322-2** convert from hand-drawn SVG to a **screenshot-backed
overlay** model. (Other screens convert in their own later sub-projects.)

### 6.1 Background layer
- Source images (clean DCS captures, no red tag boxes):
  `New folder/Screenshots/Enhanced/321.png` (2962×1408) for 321-1;
  `New folder/322-2/322-2.png` (1357×640) for 322-2.
- **Value-erase pass (§6.5):** the static transmitter values baked into each clean image
  are painted out, producing a blank-field template, saved as a served asset
  (`frontend/img/screen-321-1.png`, `frontend/img/screen-322-2.png`).
- Each screen `<div>` uses the cleaned image as a `background-image` at the image's native
  aspect ratio. A fixed design coordinate system equal to the image pixel size
  (321: 2962×1408; 322: 1357×640) anchors all overlays; CSS scales the whole stage
  responsively so overlay-px maps 1:1 to image-px.

### 6.2 Overlay layer (per indicator)
- Each transmitter is an absolutely-positioned `.ind` div at the pixel coordinate of its
  (now-erased) value field. It renders **tag label + live value + unit**, styled to match
  the DCS box.
- The div's `data-tag` binds to the tag registry (§4); each tick the packet `tags{}` value
  fills it. Unbinded tags render as an empty slot (label only) per ui_guidelines R13.
- Coordinates come directly from the erased value rectangle (§6.5) — same list for erase
  and overlay, so every live value lands exactly where its static number was.
- Interactivity preserved on these divs: **hover** → tag tooltip (R9); **left-click** on a
  controller indicator → faceplate MAN/AUTO/CAS (R6); **right-click** → Trend popup (R5).

### 6.3 Stream popups (full interactivity, per user)
- Stream geometry is no longer drawn. A transparent **SVG hit-layer** overlays the
  background in the same coordinate system. For each clickable process stream, a
  transparent `polyline` (wide `stroke`, `stroke="transparent"`, `pointer-events:stroke`)
  is traced along that line **in the image**. Left-click opens the composition / T / P /
  flow popup, fed live from `streams{}` (R7). Decorative segments may be skipped.
- Because tracing is over a static image, hit-regions cannot drift out of alignment.

### 6.4 Tabs, XV, equipment buttons
- **Tabs** (`buildTabs` ~line 425): button text = screen **number** from `sc.id`
  (`screen-322-2` → `322`). All screens. `data-label` kept for tooltip/menu.
- **321 XV bug** (#2): with the image background, XV-321901 / XV-322901 and their OPEN/CLOSED
  status boxes (visible in `321-Tagged.png`) become overlay state-icons positioned over the
  valve symbols in the image, driven by backend XV state — fixing "XV not displaying" while
  keeping each icon exactly where the DCS draws it.
- Equipment-tag jump buttons (R10) become transparent overlay hot-spots over the equipment
  symbols (`321P002A/B` block → screen-321, etc.).

### 6.5 Value-erase asset prep (replaces SVG re-trace)
The earlier SVG stream re-trace is **dropped**. A one-time asset step produces the cleaned
backgrounds:

1. List every baked static value and its pixel rectangle per image:
   - **321 (`Enhanced/321.png`)** — few remain: `27.8 C`, `15.8 C`, `7.3 BAR G`×2,
     `26.4 C`, `22.3 BAR G`×2, `7.1 BAR G`.
   - **322 (`322-2.png`)** — many: `133.4`, `183.9 C`, `113.9 C`, `138.4 BAR G`, `166.1 C`,
     `33.1 %`, `80.6 C`, `21.0 C`, `24.1`, `42.7 %`, `71.6 %`, `71.0 %`, `100.0`, `41.4 C`,
     `0.0 %`, `100 A`, `101.7 C`, `0.02 A`, `74 %`, `74.0 %`, `28.6 C`, plus any remaining.
2. Paint each rectangle with the locally-sampled box/background colour (Pillow), leaving box
   outlines and any tag text intact, so the field reads empty.
3. Save to `frontend/img/screen-<id>.png`. These become the backgrounds; the live overlay
   sits exactly where the erased number was.

> The erase rectangles and the overlay coordinates are the **same** list — generated once,
> consumed by both the image-clean script and the overlay layout — guaranteeing every live
> value registers precisely on its DCS field.

---

## 7. Instruction-file updates (persisted per request)

**`project_context.md`** — append rule:
> **Dynamic modelling rule:** All modelling equations are dynamic. Changing any valve
> opening, stream property, or composition must propagate to all downstream streams,
> transmitters, and equipment via their related equations. The backend is a
> sequential-modular (topological) flowsheet graph of Stream + Equipment nodes evaluated
> upstream→downstream each tick; recycles are torn with last-tick values.

**`ui_guidelines.md`** — append rules:
> 11. **Stream-line mapping:** Every stream line must connect the exact producer and
>     consumer it represents in the P&ID. Verify endpoints against the mapping before
>     binding.
> 12. **Indicator binding:** An indicator binds to the **stream it physically sits on**.
>     Example: `PT-329201` is on the 322E003→322F001 line, so it reads that line's
>     pressure — not the ejector discharge.
> 13. **Unbinded transmitters:** Leave any transmitter whose source is not yet identified
>     as an **empty slot** (tag shown, value blank) until bound in a later stage.
> 14. **Screenshot-backed UI:** Build each screen on the **cleaned DCS screenshot** as the
>     background layer — do not re-draw equipment or stream lines as vector art. Static
>     transmitter values baked into the screenshot are erased to blank fields.
> 15. **Overlay registration:** Position every live element (value, controller, XV state,
>     equipment hot-spot, stream hit-region) in the image's own pixel coordinate system, so
>     overlays register exactly on the underlying DCS art and cannot drift.
> 16. **Stream interactivity without redraw:** Provide stream-click popups via a transparent
>     SVG hit-layer traced over the lines in the image, not by drawing visible polylines.

---

## 8. Verification

- **Regression (equation-preserving proof):** `backend/verify_322f001.py` must still
  report design PASS (discharge 98320 kg/h, MW 20.01, T 109 °C, P 144.2 bar a, ρ 877.9,
  V 112 m³/h). `backend/test_sweep.py` must still pass.
- **New dynamic assertions:** an HV-322602 sweep (e.g. 100→40 %) asserts:
  - μ increases monotonically: $\mu=EJ\_MU\cdot 74.0/\text{open}_{eff}$;
  - `s_disch.total_kgh` and `s_E003`-bound `PT-329201`/`TI-322002` change monotonically;
  - component balance closes: $\dot m_{disch,k}=\dot m_{motive,k}+\dot m_{suc,k}$.
- **Frontend smoke:** `node --check app.js` OK; cleaned backgrounds load for 321-1/322-2,
  overlay values register on their fields, stream-hit popups + tabs + 321 XV overlays render.

---

## 9. Acceptance criteria

1. `main.py` model layer is a Stream/Equipment/Graph evaluated in topological order;
   `verify_322f001.py` + `test_sweep.py` pass unchanged (equation-preserving).
2. Moving HV-322602 visibly changes `s_disch` discharge properties **and** the
   `s_E003`-bound indicators (`PT-329201`, `TI-322002`) and all related stream popups.
3. `PT-329201` reads `s_E003.P_bara`; `TI-322002` reads `s_E003.T_C` (no hardcoded 178.8).
4. Packet exposes additive `streams{}` + `tags{}`; all bespoke keys still present.
5. Top tabs show number only on every screen.
6. Screen 321 shows its XV(s) with visible OPEN/CLOSED state.
7. `project_context.md` and `ui_guidelines.md` updated with the rules in §7.
8. Screens 321-1 and 322-2 render on the **cleaned DCS screenshot** background (static
   values erased), with live transmitter values overlaid exactly on their DCS fields. No
   stream line is hand-drawn; alignment is inherent in the image.
9. `PT-329201` / `TI-322012` / `TI-322002` overlays land on the 322E003→322F001 line in the
   image and read `s_E003` properties. Stream-click popups, faceplates, and trends work on
   the overlay layer. Screen-321 XV overlays show OPEN/CLOSED over the DCS valve symbols.

---

## Appendix A — Preserved equations (verbatim, must not change)

**Pump (321P002A/B):**
$$V_{rev}=\frac{\pi}{4}D^2 L\,n_{plgr},\quad D=0.140,\ L=0.205,\ n_{plgr}=3$$
$$Q\,[\mathrm{m^3/h}]=N\,[\mathrm{rpm}]\cdot V_{rev}\cdot \eta_v\cdot 60,\quad \eta_v=0.95$$
$$N=\frac{\text{opening}}{100}\,N_{rated},\quad N_{rated}=152,\qquad
\dot m=\frac{Q\,\rho_{NH_3}}{1000}\ [\mathrm{t/h}],\ \rho_{NH_3}=604.8$$
$$P_{shaft}=\frac{Q_{m^3/s}\,\Delta P_{bar}\cdot 10^5}{\eta_m\cdot 1000},\quad \eta_m=0.915,\qquad
I=\frac{N}{N_{rated}}\,I_{rated},\ I_{rated}=51$$

**Drum 321D003 mass & energy balance:**
$$\frac{dM}{dt}=F_{BL,in}-F_{pump,total},\qquad V=\frac{\pi}{4}ID^2 H,\ ID=0.970,\ H=1.400$$
$$M\,c_p\frac{dT}{dt}=F_{BL,in}\,c_p\,(T_{BL}-T),\quad c_{p,NH_3}=4740,\ T_{BL}=25$$

**Feed / sat pressure / sub-cooling:**
$$P_{suct}=P_{top}+\frac{\rho_{NH_3}\,g\,(\text{level})\,H}{10^5}-0.15,\quad g=9.81$$
$$\log_{10}P_{sat}[\mathrm{bar}]=A-\frac{B}{T[\mathrm K]+C},\quad A=4.86886,\ B=1113.928,\ C=-10.409$$
$$PDY=(P_{feed}+P_{atm})-P_{sat},\quad P_{atm}=1.013$$

**Pump discharge enthalpy rise (TI-321020):**
$$\Delta T_{pump}=\frac{\Delta P}{\rho\,c_p}\left(\beta T+\frac{1-\eta_h}{\eta_h}\right),
\quad \beta=1.9\times10^{-3},\ \eta_h=0.85,\qquad T_{321020}=T_{tank}+\Delta T_{pump}$$

**Ratio block (molar N/C):**
$$N\!/\!C=\frac{\dot m_{NH_3}}{\dot m_{CO_2}}\cdot\frac{M_{CO_2}}{M_{NH_3}},\quad
\frac{M_{CO_2}}{M_{NH_3}}=\frac{44.009}{17.031}=2.584$$
$$\dot m_{NH_3,demand}=\frac{N\!/\!C}{2.584}\,\dot m_{CO_2}$$

**322F001 HP ejector:**
$$\mu_{des}=EJ\_MU=\frac{\sum_k \dot m_{suc,k}^{des}}{\dot m_{motive,NH_3}^{des}}\approx 1.4125,\quad
\dot m_{motive,NH_3}^{des}=40756,\ \text{disch}^{des}=98320$$
$$\text{open}_{eff}=\mathrm{clamp}(\text{HV-322602},10,100),\qquad
\mu=EJ\_MU\cdot\frac{EJ\_OPEN\_DES}{\text{open}_{eff}}=EJ\_MU\cdot\frac{74.0}{\text{open}_{eff}}$$
$$\dot m_{suc}=\mu\,\dot m_{motive,NH_3},\qquad
\dot m_{suc,k}=\dot m_{suc}\cdot EJ\_CARB\_FRAC_k$$
$$\dot m_{disch,k}=\big(\dot m_{motive,NH_3}\ \text{if } k=\mathrm{NH_3}\ \text{else }0\big)+\dot m_{suc,k}$$
$$\dot m_d=\sum_k \dot m_{disch,k},\quad n_d=\sum_k \frac{\dot m_{disch,k}}{MW_k},\quad
\overline{MW}_d=\frac{\dot m_d}{n_d},\quad \dot V_d=\frac{\dot m_d}{\rho_d},\ \rho_d=877.9$$
$$T_d=\frac{\dot m_{motive}\,c_{pN}\,T_{motive}+\dot m_{suc}\,c_{pC}\,T_{suc}}{\dot m_d\,c_{pD}},
\quad c_{pN}=4.74,\ c_{pC}=3.10,\ c_{pD}=3.50,\ T_{suc}=178.8,\ P_d=144.2$$

**PID / Controller (SIC torque-converter opening %):**
$$e=SP-PV,\quad I\mathrel{+}=\frac{e\,dt}{T_i},\quad
OP=K_c\!\left(e+I+T_d\frac{e-e_{prev}}{dt}\right),\quad K_c=2.0,\ T_i=8.0$$
with anti-windup clamp on $I$ and $OP\in[0,100]$; MAN holds OP, AUTO uses local SP, CAS
takes SP from ratio block + N/C bias (bumpless on mode change).

**Sim tick:** `DT = 0.1 s`, `dt = min(now-last, 0.5)`.
