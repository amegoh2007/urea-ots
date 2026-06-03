# DCS UI Generation Guidelines

**Rendering method: image-backed overlay (Rev 2).** This is the standard for every screen,
matching the method last used for screens 321-1 and 322-2. Do **not** redraw equipment,
vessels, or stream lines as DOM/SVG. The cleaned DCS screenshot IS the drawing; the app
only overlays live data and interactive icons on top of it.

---

## 1. Rendering architecture

1. **Background image.** Use the cleaned DCS screenshot as the `.screen` `background-image`,
   stretched to the stage with `background-size: 100% 100%` (`background-repeat: no-repeat`).
   The stage is a fixed logical canvas **1366 × 720 px** (`STAGE_W = 1366`, `STAGE_H = 720`).
   The screenshot is stretched to fill it (vertical/horizontal scale need not be equal).
2. **Overlay layer.** Append one `.ov-layer` child to each `.screen`. All live elements
   (indicators, pumps, valves, XVs) are absolutely-positioned `.ov` divs inside it.
3. **Hide baked children, keep the overlay.** Any DOM baked into the screenshot region must
   be suppressed so live overlays are the only thing on top:
   `.screen.shot > *:not(.ov-layer){ display:none; }`. The `.ov-layer` is exempt. Opaque
   `.ov.ind` boxes sit directly over the screenshot's printed value so the live reading
   covers the static one.
4. **One config array per screen** (`OV[screenId] = [ {k,t,x,y,tag,bind,u,dec,cmd,id}, … ]`).
   `k` = stable key, `t` = type (`ind` | `pump` | `xv` | `avalve`), `x,y` = stage coords,
   `tag` = asset tag text, `bind` = packet key/path (optional), `u` = unit, `dec` = decimals.

## 2. Coordinate mapping

Tag/icon positions are measured on the source screenshot in image pixels, then mapped to the
stretched stage. For a feature at image pixel `(px, py)` on a screenshot of native size
`imgW × imgH`:

```
sx = px * STAGE_W / imgW       # = px * 1366 / imgW
sy = py * STAGE_H / imgH       # = py * 720  / imgH
```

Store the resulting `(sx, sy)` as the element's `x,y`. (Reference native sizes used so far:
321-1 = 1355 × 644; 322-2 = 1357 × 640 — vertical stretch ≈ 1.12×.) When the background image
is replaced, the previously calibrated coords drift; bump the localStorage position key
(e.g. `ots_ov_pos_v3` → `_v4`) so stale drag positions are discarded.

## 3. Overlay element types

1. **Process indicators (`ind`).** Live reading inside a rectangle that covers the baked
   value. **Unbound indicators render as a WHITE FRAME** (tag text only, no value) until the
   stream is identified in a later project stage — never invent a value or a binding.
2. **Dynamic pumps (`pump`).** Clickable icon over the screenshot's pump symbol, cropping it.
   Binary ON/OFF, visually distinct (grey → green). Click sends the toggle command to the
   backend (`pump_toggle{id}`). If a pump has no backend handler yet, render state-only /
   local toggle and note it.
3. **Block valves / XVs (`xv`).** Icon over the screenshot symbol showing OPEN/CLOSED
   (green → red). Click sends `xv_toggle{id}`. Default OPEN in normal operation unless
   specified. No backend handler yet → local toggle.
4. **Automatic valves (`avalve`).** Icon displaying the exact opening percentage (0–100 %),
   driven by the backend physics engine (Cv/datasheet or standard sizing).

## 4. Binding rules

1. **One unit at a time.** Bind indicators only on the active modelled unit (all its tags →
   packet keys) and on the **boundary tags** of a downstream unit that the backend already
   models (e.g. the 322F001 HP-ejector boundary that joins modelled 321 to downstream 322).
   Every other downstream tag stays a WHITE FRAME until its upstream unit is modelled.
2. **Bind to the correct stream.** An indicator must read the exact line it physically sits
   on. Example: PI-329201 lies on the 322E003 → 322F001 suction line, so it reads that
   suction line's pressure — not a discharge/header pressure.
3. **Dotted bind paths.** `bind` may be a flat key (`FI_321401`) or a dotted path into a
   nested packet object (`pumpA.current`, `ratio.NC_A`, `EJ_322F001.TT_322012`).
4. **Dynamic propagation (mandatory).** All modelling equations are dynamic: changing any
   valve opening, stream property, or composition must propagate to every downstream stream,
   transmitter, and equipment item per its modelling equations. Static boundary constants are
   allowed only for not-yet-modelled upstream units, clearly labelled, and swapped for the
   live stream when that unit is built.

## 5. Interactions (carried forward)

1. **Trend.** Right-click a bound indicator → pop-up chart (Chart.js or similar) of parameter
   vs. time, with +/- buttons to scale the X-axis time span.
2. **Controller faceplates.** If an indicator controls an automatic valve, left-click opens a
   faceplate with **MAN** (user enters exact % opening), **AUTO** (user enters SP, backend PID
   drives the valve), and **CAS** (opening driven by a linked parameter; selecting CAS switches
   the master to AUTO adopting the current value as SP, user-adjustable thereafter).
3. **Stream popups.** Left-click a process stream line → pop-up of that stream's current
   composition (mass fractions) and thermodynamic parameters (P, T, flow).
4. **Tag tooltips.** Hovering any asset or parameter overlay shows its tag number as a tooltip.
5. **Signal lines.** Indicator/controller-to-valve signal links are dotted (already in the
   screenshot; only add overlay signal hints if the screenshot lacks them).
6. **Screen navigation.** Right-click empty stage area → dropdown of all screens; selecting one
   switches view. Equipment-tag buttons jump to the screen hosting that equipment. **Screen
   tabs show the screen number only** (e.g. "322", not "322 HP Scrubber").

## 6. Tag editor, calibration & persistence

1. **Edit Layout mode.** An "✎ Edit Layout" toggle adds `body.ov-editing`; in this mode every
   overlay is drag-repositionable and its new position is saved.
2. **Tag CRUD.** Users can add / edit / delete / reposition tags. Adding a tag lets the user
   bind it (dropdown of available packet keys/paths); a bound new tag immediately shows its
   live value, an unbound one shows the WHITE FRAME. A context menu exposes Edit / Bind / Delete.
3. **Two localStorage stores, cleanly separated.** Positions in `ots_ov_pos_v*`; add/edit/delete
   tag overrides in `ots_ov_tags_v*` (`{ add:[…], edit:{k:{…}}, del:[k] }`). A merged-config
   accessor combines seed config + overrides at render time.
4. **Never mutate seed tags destructively.** Deletes are tombstones, edits are overrides, so
   **Reset** always restores the seed layout. Provide Reset (per screen), Export (download
   `ots-ui-layout.json` = `{v,tags,pos}`) and Import (restore from file).

## 7. Backend contract

The backend streams a flat JSON packet over WebSocket `/ws` (push every 0.1 s); the UI maps
indicator `bind` keys onto it and sends user actions back as commands (`pump_toggle`,
`xv_toggle`, `controller_set`, `ratio_set`, etc.). Use host `127.0.0.1` (avoid the IPv6
`localhost` binding gotcha). Backend physics/state is authoritative; the UI never computes
process values locally.
