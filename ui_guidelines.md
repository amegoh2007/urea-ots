# DCS UI Generation Guidelines

**Rendering:** Image-backed overlay (Rev 2). Do NOT redraw equipment/lines. Clean DCS screenshot is the background; overlay live data/icons.

## 1. Architecture
* **Background:** `.screen` `background-image` stretched to 1366×720 (`STAGE_W=1366`, `STAGE_H=720`).
* **Overlay:** One `.ov-layer` per screen containing absolute-positioned `.ov` elements.
* **Suppression:** Hide baked DOM children (`.screen.shot > *:not(.ov-layer){ display:none; }`). Opaque `.ov.ind` covers baked values.
* **Config Array:** `OV[screenId] = [{k,t,x,y,tag,bind,u,dec,cmd,id}, …]`

## 2. Coordinate Mapping
Map native image `(px, py)` to stretched stage: `sx = px * 1366 / imgW`, `sy = py * 720 / imgH`. Store as `x,y`. Bump local storage key (e.g., `_v4`) if background changes to discard stale coords.

## 3. Element Types
* **`ind` (Process Indicator):** Live value over baked value. Unbound = WHITE FRAME.
* **`pump` (Dynamic Pump):** Clickable icon over symbol (ON=green, OFF=grey). Sends `pump_toggle{id}`.
* **`xv` (Block Valve/XV):** Clickable icon (OPEN=green, CLOSED=red). Sends `xv_toggle{id}`. Default OPEN.
* **`avalve` (Auto Valve):** Displays exact 0-100% opening driven by backend physics.

## 4. Binding Rules
* **Scope:** Bind indicators only on the active unit and modelled D/S boundary tags. Other D/S tags remain WHITE FRAME.
* **Exact Stream:** Bind to the exact physical line (e.g., suction line pressure, not header).
* **Paths:** Use flat keys (`FI_321401`) or dotted paths (`pumpA.current`).
* **Dynamic Propagation:** All equations are dynamic. Static constants allowed ONLY for unmodelled upstream units; swap immediately when built.

## 5. Interactions
* **Trend:** Right-click any bound `ind`/`avalve`/`xv`/`pump` → context menu (`Trend`, `Add to slot`), or drag it onto a slot. Opens the persistent 10-pen window (`trend.js`). See §13.
* **Faceplates:** Left-click auto-valve indicator → MAN (user %), AUTO (user SP, PID drives), CAS (linked param drives).
* **Stream Popups:** Left-click stream line → Composition/thermo data.
* **Tooltips:** Hover asset → tag number.
* **Navigation:** Right-click stage → screen dropdown. Tags use pure screen numbers (e.g., "322").

## 6. Persistence & Editing
* **Edit Layout:** Toggle `body.ov-editing` for drag-repositioning.
* **Stores:** Separate `ots_ov_pos_v*` (positions) and `ots_ov_tags_v*` (tag CRUD overrides).
* **Operations:** Never destructively mutate seed tags. Use tombstones/overrides.

## 7. Backend Contract (Autonomous Execution)
* **Comms:** WebSocket `/ws` on `127.0.0.1` (push 0.1s).
* **Architecture:** UI maps `bind` keys to JSON packet and sends actions. Backend physics/state is 100% authoritative; UI computes zero process values.
* **Workflow:** Autonomously map UI elements and endpoints. Deep research, plan, then execute code.

---

## 8. Page Scaffold (New Screen Settings)
Every new screen is a `.screen.shot` div inside `#stage`. Reuse the existing shell — never restyle globals.

* **Stage:** `#stage` fixed `1366px × 720px`, `position:relative`, `background:var(--bg)`, `margin:0 auto`, `overflow:hidden`.
* **Screen div:** `<div class="screen shot" id="screen-XXX-N" data-label="XXX-N TITLE">`. `.screen{position:absolute;inset:0;display:none;}`; active screen gets `.active` (`display:block`). Only one active at a time.
* **Background image:** add rule `#screen-XXX-N.shot{background-image:url("img/screen-XXX-N.png");}`. Image stretched `background-size:100% 100%`, `position:center`, `no-repeat`. Baked children hidden via `.screen.shot > *:not(.ov-layer){display:none;}`.
* **Title:** `<div id="title">XXX-N UNIT NAME</div>` — `top:8px`, centered, `bold 18px`, color `#fff`, `letter-spacing:1px`.
* **Tab bar:** `#tabbar` auto-populated; each button `bold 12px Arial`, radius `5px 5px 0 0`. Active tab: `background:var(--bg)`, color `#ffd000`, border `#7fd0d8`.
* **Overlay layer:** one `<svg class="ov-layer">`… actually `.ov-layer{position:absolute;inset:0;z-index:4;}` holding absolute `.ov` elements (`z-index:5`, `transform:translate(-50%,-50%)` — x/y are element CENTERS).
* **Registration:** register the screen id in the tab bar + `#screenmenu` nav list and add its `OV[screenId]` config array. Bump the localStorage key suffix (`_v*`) whenever the background image changes so stale coords are discarded.

## 9. Typography
Two font stacks only — do not introduce others.

* **Value/readout font** (`--val-font`): `"Cascadia Mono","Consolas",ui-monospace,"Segoe UI Mono",monospace`, always with `font-variant-numeric:tabular-nums`. Use for every live process value, valve %, RPM, current — anything numeric that updates.
* **UI/chrome font:** global `*` = `Arial,Helvetica,sans-serif`. Rev-2 overlay chrome (toolbar, context menu, and edit modal) = `"Segoe UI",system-ui`. Text inputs, mode tags, DCS tag chips, and stream tables = `Consolas,monospace`.

**Font-size catalogue (px) — match exactly:**

| Element | Size / weight |
|---|---|
| `#title` | 18 bold, letter-spacing 1 |
| `#tabbar button` | 12 bold |
| `.trip` | 13 bold |
| `.block` (equipment) | 12 |
| `.lbl-s` (stream/small label) | 11 |
| `.pi` (process indicator) | 13; unit `.u` 11 |
| `.ov.ind` (live overlay value) | 12 bold; unit `.ou` 10; mode `.mt` 8 |
| `.ov.ind.empty` (unbound WHITE FRAME) | 9 normal |
| `.badge-l` (level/alarm badge) | 10 |
| `.xv` / `.pump-btn` | 11 |
| `.ratio-panel` / `.hic-panel` | 12; row label 11 |
| `.avalve` | 11; opening `.op` 12 |
| `.mode-tag` | 13 bold |
| `.tag` (DCS tag chip) | 11 |
| `.modal .card` | 13; `h3` 14; buttons 12 |
| `.ov-card` (Rev-2 modal) | 13; `h3` 15; label 12 |
| `#ov-cryst` banner | title 12 (800); row 11 (600) |

## 10. Color Palette (`:root` tokens — never hardcode substitutes)
| Token / use | Value |
|---|---|
| `--bg` DCS teal canvas | `#1d4d52` |
| page backdrop | `#0a1416` |
| `--pi-bg` / `--pi-border` / `--pi-text` | `#000` / `#fff` / `#fff` |
| `--pi-alarm` (alarm text, MAN mode) | `#ff3030` |
| `--btn-green` (ON / OPEN / running) | `#22ff22` |
| `--btn-off` / SET-confirm green | `#0aa64d` |
| `--line-nh3` (NH3 / carbamate, magenta) | `#ff00ff` |
| `--line-cpl` (process, green) | `#22d622` |
| `--line-carb` (carbamate feed, orange) | `#ff9a3c` |
| `--signal` (dotted instrument signal) | `#9bbabb` |
| GCB gas main | `#ffd000` |
| `--ratio` (ratio/HIC panel) | `#2e8a8f` |
| `.ov.ind` bg / border / text / unit | `#04110d` / `#e8f4f0` / `#d6f3e4` / `#82b3a3` |
| faceplate accent (`.ov.ind.fp`, active tab border) | `#7fd0d8` |
| Rev-2 chrome bg / accent / text | `#13202c` / `#4aa587` / `#cfe` |
| crystallization warn / alarm banner | `#3a2a08`+`#b3892f` / `#3a0d0d`+`#ff3030` |

**Overlay mode-tag `.mt` colors:** A `#5fe08f`, E `#7fd0d8`, M `#e0b85f`, O `#e06f6f`.

## 11. Overlay Element Dimensions
| Type | Size | Behavior |
|---|---|---|
| `.ov.ind` | min-width 30, height 18, pad 0 4 | live value; `.empty` = unbound white frame (min-w 34, h 16) |
| `.ov.pump` | 54 × 54 | click → `pump_toggle{id}`; ON green body, OFF grey |
| `.ov.avalve` | 34 × 34 | shows 0–100% opening from backend; `.closed` → red polygon |
| `.ov.xv` | auto | click → `xv_toggle{id}`; OPEN green lamp, CLOSED red |
| `.ov.nav` | transparent hotspot | screen-jump on click |
| `.ov.strm` | dashed cyan hotspot | click → stream composition popup |
| `.ov.ovrd` | pill | external-override arm/confirm (amber `#ffd000` armed) |

Default fallbacks when `o.w/o.h` unset: control 60×24, indicator 120×16.

## 12. Controller Faceplate Guide
Left-click any `*IC-3xxxx` indicator opens a faceplate (regex `CTRL_RE = /[A-Z]IC-3\d{2}/i`). All faceplates are `.modal > .card` (min-width 420, bg `#1b2a30`), inputs `Consolas`, primary SET button green `#0aa64d`. Backend physics is authoritative; faceplate only sends SP/MV/mode/opening.

**Faceplate roster (replicate this pattern for new loops):**
| Loop | Target | Fields | Modes |
|---|---|---|---|
| Generic `#ctlModal` | any `*IC-3*` PV | PV (ro), SP, Output % | MAN / AUTO / CAS |
| **Indicator `#indicatorModal`** | any other bound value | Value (ro), Units, Source | read-only — **fallback for every value** |
| **All hand-valve `HIC/HV-3xxxx`** | its HV opening | Opening % | MANUAL only — **one shared faceplate** |
| `PIC-322203` | PV-322203 | PV (ro), SP, Output % | MAN / AUTO |
| `HIC-322203` | PV-322203 | Min Opening % | forced-minimum |
| `SIC-321950/951` | 321P002A/B speed | PV(ro), N/C SP + PV (ro), SP, MV, CAS bias | MAN / AUTO / CAS / OOS (REST `/api/ctrl/*`) |

**Hand-valve faceplate — one modal, all HVs (mandatory):** every hand valve (`HIC/HV-322602`, `-322605`, `-322604`, and any future HV) opens the single opening-only `#hicModal` (`app.js` `openHicFace`). Do NOT clone a per-valve modal. Each valve's send-command is looked up in the `CMD{tag→{t,f}}` table (e.g. `HIC-322605`→`{t:'hic605_set',f:'op'}`); the title, physics `NOTE`, and current opening are swapped per `cur.tag`; default fallback = `HV-322602`. To add a hand valve: give its overlay `face:'hic'` + a `CMD` row — no new modal.

**Mode-button + live mode-tag color convention (mandatory):**
* MAN → red `#ff3030` · AUTO → green `#22ff22` · CAS → yellow `#ffd000` · OOS → orange `#ff8a3d`.
* Active mode button: `background:#0aa64d`, border `#22ff22`.
* Faceplate rows: `<div class="row"><label>…</label><input …></div>`, `step="0.1"`, `min=0 max=100` for %; readonly PV uses `[readonly]` (cyan `#7fd6ff`).
* Each numeric loop carries a one-line physics note (`font-size:11px`, `#cfeff1`) stating cause→effect (e.g. "↑ PV-322203 opening ⇒ ↓ CO2 feed flow").
* **Trend:** right-click any bound indicator → trend context menu (§13). **Stream:** left-click stream line → `#streamModal` composition table.

**Every value opens a faceplate (mandatory).** A left-click on an indicator, a controller, a
bargraph, a slide-drawn button or a valve-opening must open *something*; a bound value that does
nothing on click is a defect. The route is: the overlay's own `face` → `CTRL_RE` generic
`#ctlModal` → read-only `#indicatorModal`. Tags with no operator handle land on the last one,
which shows the value, its unit and the packet path it came from.

**Click-to-expand (mandatory on read-only value fields).** Faceplates round for readability
(`fmt` → 1–2 dp), which hides whether a value has actually moved. Clicking a read-only value field
swaps it to 3 decimal places and back (`fpxBind`/`fpxSet` in `app.js`, formatting shared with
`indicator_faceplate.js` so the terminal and the faceplate agree). Expansion is per field, is
remembered across the live re-fill each tick, and is marked amber (`.fpx.expanded`). Editable
fields (SP / MV / OP) are deliberately excluded — re-formatting under the cursor breaks typing.

---

## 13. Trend Window (`trend.js`)

10-pen trend hosted in a **separate browser window** (`frontend/trend.html`, loaded via
`window.open`). The popup runs `trend.js` in POPUP role — full-page UI, its **own** WebSocket to
`/ws`, its own `/api/hist` backfill — so it lives on a second monitor and is unaffected by anything
in the main app. The main DCS app runs `trend.js` in LAUNCHER role: right-click → `Trend ↗` (or
drag, below) opens/focuses the popup and hands the tag across via a `localStorage` queue
(`ots_trend_pending`) plus a `BroadcastChannel('ots_trend')`. Tag→path resolution in the popup uses
the `ots_ov_binds` mirror overlays.js writes (the popup never runs overlays.js).

The **`TRENDS`** button in `#sys-tools` (fixed top-right, beside `RESET`, so it shows on every
screen) opens/focuses the popup with no tag attached (`TrendWindow.open()`) — the screen-independent
way in when you have no indicator to right-click or drag.

**Cross-window drag:** an HTML5 drag payload cannot cross window boundaries, so on `dragend` the
launcher tests the pointer's screen coordinates against the popup's screen rect and enqueues the tag
if it landed there. Right-click `Trend ↗` is the always-available path.

* **Data:** backend historian (`historian.py`) records every numeric and boolean packet leaf
  except the `STREAMS` subtree — 914 paths, ~23.8 MB — from process start. Backfill via
  `GET /api/hist?paths=…&span=…&max=…`; live extension from the WS packet.
* **Time base:** PLANT clock (`t_sim`), so a 1-hour span is one hour of plant behaviour at
  either pacing. The X axis carries two tick rows: plant clock, then desktop clock (`t`).
  Ticks preceding program start render blank, never a clamped placeholder.
* **Spans:** `1m 5m 30m 1h 2h 4h 8h`, default **1h**.
* **Scaling:** every pen normalises to a shared 0–100 grid. **Analog pens auto-scale by default:**
  the display range is set slightly below the MIN and above the MAX of the samples currently in
  view (5 % pad) and re-derived every redraw, so it expands automatically the instant a value
  exceeds the current bracket (and contracts as old peaks scroll out). The declared engineering
  range (`rng:[lo,hi]` on the OV entry → unit-default table) only seeds lo/hi until the first
  samples arrive. **Digital on/off pens** (no unit) stay pinned to 0–1 so their stepped trace keeps
  full-scale height. The Y axis relabels to the **most recently highlighted** pen's units (`axisPen`);
  labels outside 0–100 % are suppressed.
* **Pen table:** `# · ✓ · colour · TAG · VALUE · MIN · MAX · AVG · RANGE · R1..Rn · UNIT · LOW · HIGH · x`,
  with a sticky header row. **✓** is a highlight tickbox (see below). **RANGE** is a read-only display
  of the pen's current scale (`lo – hi`, with an `A` badge and grey italic when auto-scaled). Ruler
  columns appear only for placed rulers. Empty rows are drop targets. Booleans render as 0/1 stepped pens.
* **Pen highlight (tickbox column → emphasise trends):** the **✓** column after `#` marks a pen for
  highlight. **Multiple pens can be marked at once**: every marked line thickens (3.2 px vs 1.4), keeps
  full colour, and is drawn on top, while the unmarked pens fade to 25 % alpha; marked rows are outlined.
  Clicking anywhere on a filled row toggles its mark too (same as the tickbox). No marks = all pens at
  full strength. The most recently marked pen drives the Y-axis engineering scale (`axisPen`). State is
  `highlights` (a Set) + `axisPen`, persisted as `hl`/`axis` in `ots_trend_v1` (old single-pen `sel`
  migrates in).
* **Control strip (`#tw-bar`, between plot and pen table):** `◀ ▶` scroll arrows · `LIVE`/`HISTORY`
  state · **CURRENT** plant + desktop clock · **RULER** plant + desktop time with `✕` to clear.
* **Scrolling:** the arrows pan a quarter span per press (`PAN_FRACTION`) and re-backfill from the
  historian via `&end=`, so scrolling reaches recorded data the browser never buffered. The view
  edge is held as an **absolute plant time** (`viewEndT`, `null` = live), so a parked window stays
  on its instant instead of drifting forward with each packet. Back stops at program start and at
  the 8 h retention limit; forward resumes live on arrival. The amber `HISTORY` chip returns to
  live when clicked; arrows disable at their limits.
* **Rulers (up to 10):** click the plot to drop a dashed vertical ruler; each gets a distinct colour
  (amber, cyan, pink, green, orange, violet, red, emerald, white, periwinkle) and an `R1`..`R10`
  label. **Drag a ruler horizontally** to reposition it (grab within 6 px; the cursor turns to
  `ew-resize` over a line); it clamps to the visible window and the readings update live. A plain
  click on empty plot still adds a new ruler. The pen table grows one colour-matched `R{n}` column
  per active ruler, showing each pen's held reading at that instant. Ruler chips in the control strip
  carry plant+desktop time and a ✕; rulers auto-clear when scrolled out of view. An 11th is refused.
* **MIN / MAX / AVG columns:** always shown, computed over the points currently in the visible
  window (respecting scroll and span). AVG is the arithmetic mean of visible samples — for a digital
  pen that reads as its duty fraction.
* **Ruler (legacy single):** click anywhere on the plot to drop a dashed vertical ruler at that instant,
  labelled with plant and desktop time. The `@ RULER` column then shows what every pen read at
  that moment — last sample at or before the ruler (hold semantics, the only correct reading for
  a stepped digital pen); `--` before a pen has data. Clicking again moves it; the amber `RULER
  hh:mm:ss ✕` chip in the header clears it. The ruler auto-clears when it scrolls out of the
  window rather than stranding a column of stale numbers. Drawn as a Chart.js plugin, so it is
  captured by the PNG export along with a `RULER` stamp in the header and an `@ RULER` column.
* **Editable display range:** LOW and HIGH are number inputs per pen. Editing either sets the
  pen's display scale and clears its auto-scale flag; ENTER or blur commits (§12). Blanking a
  field returns the pen to auto-scaling, and auto values render italic/grey to signal they are
  derived, not set. An inverted or zero-width span is refused with a `BAD RANGE` flash and the
  previous scale is restored. A focused field is never overwritten by the 4 Hz redraw. Operator
  ranges persist in `localStorage`; auto pens deliberately store none.
* **Entry:** right-click context menu or HTML5 drag from the overlay. `body.ov-editing`
  disables `draggable` so the reposition drag keeps working.
* **Resolution:** `window.OV_BINDS` (built in `buildBindMap`) maps P&ID tag → packet path for
  `ind`, `avalve`, `xv` and `pump`. This is separate from `BIND_MAP`, which drives `eff()`
  render inheritance and must stay `ind`-only.
* **Persistence:** slots, span, selected pen and geometry in `localStorage` (`ots_trend_v1`);
  restored and re-backfilled on load.
* **Export:** `SAVE` composes an offscreen canvas (header + chart + pen table) and offers
  `Trend_Report_YYYY-MM-DD_HH-MM-SS.png` through `showSaveFilePicker`, falling back to an
  anchor download. No extra libraries.
* **Colours:** pens `#22ff22 #7fd0d8 #ffd000 #ff9a3c #ff00ff #5fe08f #e06f6f #9bbabb #c78fff #ffffff`;
  chrome `#13202c` / accent `#4aa587` / text `#cfe`; selected row outlined `#7fd0d8`.
