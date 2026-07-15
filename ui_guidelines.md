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
* **Trend:** Right-click bound indicator → Pop-up Chart.js (time vs param).
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
* **UI/chrome font:** global `*` = `Arial,Helvetica,sans-serif`. Rev-2 overlay chrome (toolbar, context menu, edit modal, crystallization banner) = `"Segoe UI",system-ui`. Text inputs / mode tags / DCS tag chips / stream tables = `Consolas,monospace`.

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
| **All hand-valve `HIC/HV-3xxxx`** | its HV opening | Opening % | MANUAL only — **one shared faceplate** |
| `PIC-322203` | PV-322203 | PV (ro), SP, Output % | MAN / AUTO |
| `HIC-322203` | PV-322203 | Min Opening % | forced-minimum |
| `SIC-321950/951` | 321P002A/B speed | PV(ro), SP, MV, N/C bias | MAN / AUTO / CAS / OOS (REST `/api/ctrl/*`) |

**Hand-valve faceplate — one modal, all HVs (mandatory):** every hand valve (`HIC/HV-322602`, `-322605`, `-322604`, and any future HV) opens the single opening-only `#hicModal` (`app.js` `openHicFace`). Do NOT clone a per-valve modal. Each valve's send-command is looked up in the `CMD{tag→{t,f}}` table (e.g. `HIC-322605`→`{t:'hic605_set',f:'op'}`); the title, physics `NOTE`, and current opening are swapped per `cur.tag`; default fallback = `HV-322602`. To add a hand valve: give its overlay `face:'hic'` + a `CMD` row — no new modal.

**Mode-button + live mode-tag color convention (mandatory):**
* MAN → red `#ff3030` · AUTO → green `#22ff22` · CAS → yellow `#ffd000` · OOS → orange `#ff8a3d`.
* Active mode button: `background:#0aa64d`, border `#22ff22`.
* Faceplate rows: `<div class="row"><label>…</label><input …></div>`, `step="0.1"`, `min=0 max=100` for %; readonly PV uses `[readonly]` (cyan `#7fd6ff`).
* Each numeric loop carries a one-line physics note (`font-size:11px`, `#cfeff1`) stating cause→effect (e.g. "↑ PV-322203 opening ⇒ ↓ CO2 feed flow").
* **Trend:** right-click any bound indicator → `#trendModal` Chart.js (time-span +/- stepper, black canvas). **Stream:** left-click stream line → `#streamModal` composition table.