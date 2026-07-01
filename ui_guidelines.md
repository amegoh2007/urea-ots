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