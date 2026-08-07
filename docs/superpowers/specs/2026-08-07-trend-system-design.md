# Trend System & Totalizer Reset — Design

Date: 2026-08-07
Branch: `codex/full-simulation-extended-uniquac-audit`
Status: approved (design), pending implementation plan

## Scope

Two deliverables:

1. **Task 1** — reset the ammonia consumption counter `FQI-321401` to `0` on program initialization.
2. **Task 2** — a background data historian plus a globally persistent, 10-slot, drag-and-drop
   interactive trend window with selectable timeframes and PNG export.

## Existing system (verified, not assumed)

| Aspect | Fact |
|---|---|
| Stack | Vanilla JS SPA, no build step. `frontend/index.html` + `app.js` + `overlays.js`. Chart.js via CDN. |
| Backend | FastAPI `backend/main.py`. WS `/ws` broadcast at 10 Hz (`push_task`). Sim tick `DT = 0.1 s`, `STEP_CAP = 0.25 s`. |
| Screens | 10 `.screen.shot` sibling divs inside `#stage`; one carries `.active`. |
| Overlay model | `OV[screenId] = [{k,t,x,y,tag,bind,u,dec,…}]`. `bind` is a dot-path into the WS packet. |
| Element census | 333 overlay elements: 274 `ind`/`avalve`, 25 `pump`/`xv`/`ovrd`, rest `strm`/`nav`. |
| Pacing | `sim_mode` `SLOW` = 1x, `FAST` = 60x (`SIM_SPEED`, main.py:270). |
| Packet clock | `"t"` = `time.time()` (desktop). **No sim clock exists.** |
| Packet size | 3,213 numeric + 532 bool/str leaves, ~68 KB JSON. 2,346 numeric leaves are the `STREAMS` subtree. |

### Defects this design corrects

1. **Overlay trend is broken on 9 of 10 screens.** `overlays.js:643` calls `openTrend(o.tag)` with a
   P&ID tag (`'TT-321001'`); `app.js:222` looks up `history[tag]`, a dict keyed by *packet key*
   (`TI_top1`). The lookup misses and the chart renders empty. Only the legacy `.pi` screen works,
   because there `data-tag` happens to equal the packet key.
2. **History covers 25 tags of 217.** `pushHistory` (app.js:30) logs a hardcoded list; ~90 % of
   instruments have never been recorded.
3. **Chart is destroyed and rebuilt every 500 ms** (`app.js:226-234`), which is the source of the
   visible flicker.
4. **History dies on refresh** and is per-tab.

## Coverage verification

Run against a live `step_sim(0.1)` packet, parsing the `OV` table directly:

```
ind + avalve elements ............ 274   (across all 10 screens)
unique bound tags ................ 217
  -> resolve to numeric leaf ..... 217   (100 %)
  -> fail to resolve .............   0
  -> living under STREAMS ........   0
historian universe (STREAMS excluded)
  numeric paths .................. 867
  boolean paths ..................  46
bound indicator tags not covered ..   0
```

Per-screen (`total / trendable`): 321-1 `19/19`, 322-1 `37/36`, 322-2 `19/17`, 323-1 `30/28`,
323-2 `35/31`, 324-1 `23/21`, 324-1b `29/15`, 328-1 `37/35`, 328-2 `15/12`, 329-1 `30/28`.

### Documented exclusions — no data exists to log

| Class | Count | Detail |
|---|---|---|
| White-frame tags | 31 tags / 32 slots | No `bind` on any screen; unmodelled units per `ui_guidelines` §4. One tag is placed on two screens, hence 32 slots for 31 tags. 24 are Unit-335 (melt/prilling): `335D004`, `335P001A/B`, `335P002`, `335P006`, `335R001A/B`, `FFY-335406`, `FIC-335401`, `FIC-335405B`, `FIC-335407`, `FV-335407`, `HIC-335602`, `HV-335602`, `HV-335609`, `HV-335610`, `LT-335507`. Remainder: `322E003`, `322P002`, `323P003A/B`, `328P002`, `328P003`, `328P006`, `328P007`, `329P003`, `IT-329007`, `IT-329008`, `LT-323506`, `MASTER-SP`, `PY-329207B`, `STARTUP SW`. |
| UI-local pumps/XVs | 15 | `329P002A/B`, `329P004A/B`, `329P006A/B`, `329U001-M01/M02`, `XV-322903`, `XV-322901 INTERLOCK OVERRIDE`, `TRIP_35_3`, `EXT-OVR 323P001A/B`, `EXT-OVR HV-335602`, `EXT-OVR LV-324501A/B` — client-side toggles with no backend state. |
| Legacy `.pi` elements | 23 | All inside `.screen.shot`, hidden by `.screen.shot > *:not(.ov-layer){display:none;}`. Dead UI; excluded from the registry. |

Each white-frame tag becomes trendable automatically the moment its unit is modelled and its `bind`
is filled in — no trend-system change required.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Historian lives in the **backend** | Records from process start (not page load), survives refresh and WS reconnect, single source of truth, and is the only place that can sample correctly under FAST pacing where consecutive packets are 6 plant-seconds apart. |
| D2 | X axis measures **plant (sim) time**; **both** clocks are displayed | A 1-hour trend must always show one hour of plant behaviour regardless of pacing. Desktop clock is shown alongside so the trainee can correlate with the wall clock. |
| D3 | **One plot, 10 pens, pen table** | DCS-standard layout; maximises plot area and allows cross-loop correlation, which is the purpose of a multi-pen trend. |
| D4 | Log **every numeric leaf except `STREAMS`** | No hand-maintained tag list to drift; covers all 217 bound tags plus future binds. `STREAMS` is 73 % of leaves and holds composition tables, which are read through the stream popup, not trended. |
| D5 | **Boolean paths trend as digital pens** | 46 boolean paths (`pumpA.on`, `XV_321901`, `XV_322901`, `CO2_FEED.XV_322902`, `ABSORB_328.C001.XV_322915`, `RECIRC_323.D002.HV_tie`, …) plotted `stepped:'before'` at 0/1. Costs 1.2 MB. |
| D6 | Registry sources **`BIND_MAP` only** | The legacy `.pi` screen is invisible; its `TAG_MAP` flat keys (`EJ_motive`, `PA_speed`, …) are synthetic history aliases, not packet paths. |
| D7 | **REST** for backfill, **WS** for live | Backfill is a one-shot bulk pull; adding request/response correlation to a broadcast channel is strictly worse. |
| D8 | **One** trend window, 10 slots | Matches the requirement wording; avoids window-manager scope. |

---

## Task 1 — FQI-321401 reset

`backend/main.py:4268`

```python
self.totalizer_t = 177001.09   # before
self.totalizer_t = 0.0         # after
```

Safe: the value has exactly three touch points — initialise (4268), accumulate (5054,
`s.totalizer_t += F_pump_total_th * dt / 3600.0`), emit (7144). It feeds no physics and no
controller. `State.__init__` is the only initialisation path; `handle_cmd` exposes no reset command.

**Test** (`backend/test_totalizer_init.py`): a fresh `State()` has `totalizer_t == 0.0`, and after
`step_sim` the totalizer equals the time-integral of pump delivery to within tolerance.

---

## Task 2 — architecture

### Layer 1 — backend historian (`backend/historian.py`, new)

**Sim clock.** Add `State.sim_t: float`, advanced by the same `h` the physics integrates inside the
`sim_task` sub-step loop. Packet gains `"t_sim"`; `"t"` keeps its present desktop-clock meaning.

**Storage — columnar with a shared time index.** All paths are sampled on one common tick, so
timestamps are two arrays for the whole historian rather than a pair per path.

```
t_sim  : array('d')   capacity N
t_wall : array('d')   capacity N
cols   : { path -> array('f') }   capacity N each
```

Fixed-capacity circular buffers with a write cursor and a `count`. Not deques: a deque of Python
floats costs roughly 8x the memory of `array('f')` and would push this design past 300 MB. Paths
that first appear mid-run are NaN-padded to the current length.

**Dual-rate rings.**

| ring | period (plant) | depth | serves | memory |
|---|---|---|---|---|
| fast | 1 s | 3600 | 1m, 5m, 30m, 1h | 913 x 3600 x 4 B = 13.1 MB |
| slow | 10 s | 2880 | 2h, 4h, 8h | 913 x 2880 x 4 B = 10.5 MB |

Total ≈ 23.6 MB for 867 numeric + 46 boolean paths.

**Sampling.** `PATH_EXCLUDE = ('STREAMS',)`. A flat path list is compiled once and rebuilt only when
the packet key-set changes. Sampling happens inside the sub-step loop so FAST retains true 1
plant-second resolution. If profiling shows this costs meaningful CPU (FAST implies 60 samples per
wall-second), the fallback is one sample per real tick, degrading the fast ring to 6 plant-seconds
in FAST only. Measure before optimising.

**Query API.**

- `GET /api/hist?paths=a,b,c&span=3600&max=800`
  Selects the ring covering `span`, slices the circular buffer, decimates to at most `max` points
  using **min/max envelope pairs** so transient spikes survive decimation.
  Returns `{ "t_sim": [...], "t_wall": [...], "series": { path: [v, ...] } }`.
- `GET /api/hist/paths` — the loggable path list with inferred kind (`NUM` / `BOOL`).

**Error contract.** Unknown path → that series is omitted from `series` and named in a `"missing"`
array. Span larger than retained history → whatever exists, plus `"truncated": true`.

### Layer 2 — frontend registry and store (`frontend/trend.js`, new)

`TagRegistry` is built from `BIND_MAP`, which `overlays.js` already computes; it is exposed as
`window.OV_BINDS`. Resolves `tag -> { path, unit, dec, range, kind }`. This is what repairs defect 1:
the tag-to-path hop that the current code lacks.

**Engineering range** decides whether a 10-pen plot is readable. Resolution order:

1. explicit `rng: [lo, hi]` on the `OV` entry (added where a datasheet range is known);
2. unit-default table — `%` 0-100, `C` 0-250, `BAR G` 0-200, `BAR A` 0-200, `T/H` 0-100,
   `RPM` 0-3000, `A` 0-200, `NM3/H` 0-40000, `KG/H` 0-50000, dimensionless 0-1;
3. auto-scale from the visible window, with the computed range shown in the pen table.

Boolean pens are fixed 0-1 and rendered stepped.

`TrendStore` per slot: backfill via `/api/hist` on add and on span change, then append live values
from each WS packet. `app.js` calls `TrendWindow.onPacket(s)` inside the existing `ws.onmessage`
chain alongside `OV_apply`.

### Layer 3 — trend window (`frontend/trend.js`, markup and CSS in `index.html`)

A single `<div id="trendwin">` appended to `document.body`, **outside `#stage`**. Because the screens
are sibling divs in one page, persistence across navigation is structural — there is no show/hide
logic to maintain. `position: fixed`, dragged by its title bar, resizable, `z-index: 400` (current
maximum in the app is 220 on `#screenmenu`).

**Header**, left to right: `X` close (top-left, per requirement) · `TREND` · live plant clock and
desktop clock · span segmented control `1m 5m 30m 1h 2h 4h 8h` (default **1h**) · `SAVE`.

**Plot.** One `<canvas>`, Chart.js line, 10 datasets, `parsing: false`, `animation: false`,
`pointRadius: 0`, `spanGaps: false`. Every pen is normalised to a shared 0-100 grid via
`(v - lo) / (hi - lo) * 100`. The Y axis tick callback relabels to the **selected** pen's engineering
units, so the selected pen reads directly while the rest stay comparable in shape. The X axis carries
two tick rows: plant clock primary, desktop clock beneath (Chart.js second linear x-axis at
`position: 'bottom'`, sharing the same data range).

**Pen table**, 10 rows: `# · colour chip · TAG · live value · unit · range · X`. Empty rows read
`-- drop indicator here --`. Clicking a row selects that pen and the Y axis follows. Fixed 10-colour
palette chosen for contrast against `#0a1416`, none relying on red/green discrimination alone.

**Redraw** by in-place dataset mutation at 4 Hz with `chart.update('none')`, replacing the current
destroy-and-recreate cycle (defect 3).

**Styling** follows `ui_guidelines.md`: value readouts in `--val-font` with
`font-variant-numeric: tabular-nums`; chrome in `"Segoe UI", system-ui`; chrome background `#13202c`,
accent `#4aa587`, text `#cfe`; the faceplate accent `#7fd0d8` marks the selected pen row.

### Interactions

**Right-click.** Any bound `ind` or `avalve` opens the context menu (reusing `#ctxmenu`): `Trend`
opens the window and fills the first free slot; `Add to slot >` appears when the window is already
open. Unbound white-frame elements show a disabled `Trend — not bound` item. The handler resolves
through `TagRegistry`, replacing the broken direct-tag lookup.

**Drag and drop.** `draggable="true"` is set on bound `.ov.ind` and `.ov.avalve` elements.
`dragstart` writes `{tag}` to `dataTransfer`; a `dragging` flag suppresses the trailing `click` so a
drag never opens a faceplate. Drop targets are the 10 pen rows (explicit slot) and the plot area
(first free slot). When `body.ov-editing` is active, `draggable` is removed so the existing
reposition-drag in `attach()` is untouched.

**Slot behaviour.** Dropping onto an occupied slot replaces it. Dropping a tag already trended
highlights the existing pen instead of duplicating. All 10 full → the drop is rejected with a
`SLOTS FULL` flash.

### Persistence

Slot tags, span, selected pen, and window geometry are written to `localStorage` under
`ots_trend_v1`. On load the window restores and re-backfills from the historian, which kept logging
through the refresh. Closing with `X` clears the window but retains the slot list, so reopening
restores the previous pen set.

### Export

`SAVE` composes an offscreen canvas — header band (title, plant timestamp, desktop timestamp, span),
the chart bitmap, then the pen table drawn as text rows — and calls `toBlob()`. Delivery:

1. `window.showSaveFilePicker({ suggestedName: 'Trend_Report_YYYY-MM-DD_HH-MM-SS.png' })` — a real
   Save As dialog on Edge and Chrome;
2. fallback `<a download>` with the identical filename where the File System Access API is absent.

No new dependency; html2canvas is deliberately avoided. The filename carries desktop date-time (what
a file needs); the plant clock is printed inside the image.

### Error handling

| Condition | Behaviour |
|---|---|
| `/api/hist` unreachable or backend restarted | `HISTORY UNAVAILABLE — LIVE ONLY` chip in the header; live plotting continues from WS packets. |
| Dropped tag not bound | `NOT BOUND` flash on the slot; slot stays empty. |
| WS reconnect | Every slot re-backfills; the gap is filled from the historian. |
| Path vanishes from the packet | Pen holds its last value, greys out, and the row shows `STALE`. |

## Testing

| File | Covers |
|---|---|
| `backend/test_totalizer_init.py` | Task 1: fresh state is zero; accumulation matches the flow integral. |
| `backend/test_historian.py` | Ring wrap-around; span-to-ring selection; min/max decimation preserves extremes; NaN padding for late paths; `STREAMS` exclusion; memory ceiling. |
| `backend/test_trend_coverage.py` | **Guard test.** Parses the `OV` table, asserts every bound tag resolves to a numeric or boolean leaf in a live packet, and that the bound-tag count is **at least** the 217 recorded here. A bind typo or renamed packet key fails the suite instead of silently drawing an empty pen; newly bound tags raise the floor rather than breaking the test. |
| `frontend/test_trend.js` | Registry resolution; normalisation maths; slot add/replace/remove; localStorage round-trip. Follows the existing lightweight style of `test_lv324501_route.js`. |

## Files

**New** — `backend/historian.py`, `backend/test_historian.py`, `backend/test_totalizer_init.py`,
`backend/test_trend_coverage.py`, `frontend/trend.js`, `frontend/test_trend.js`

**Edited (surgical)**

- `backend/main.py` — `totalizer_t` init; `State.sim_t`; `"t_sim"` packet key; historian sample call
  in the sub-step loop; two REST routes.
- `frontend/index.html` — `trend.js` script tag; `#trendwin` markup; CSS.
- `frontend/app.js` — remove `trendChart` / `openTrend` / `updateTrend` and the `TREND_SPANS`
  stepper; route `window.openTrend` to the new module; call `TrendWindow.onPacket(s)`.
- `frontend/overlays.js` — expose `BIND_MAP` as `window.OV_BINDS`; set `draggable` on bound
  indicators; route `contextmenu` to the new menu.

**Removed** — `#trendModal` markup in `index.html` and its handlers in `app.js`, superseded.

**Documentation** — `ui_guidelines.md` §5 and §12 trend entries; `Urea OTS — As-Built Mathematical &
System Architecture Reference`; `handoff.md`.

## Out of scope

- Trending `STREAMS` composition data (one-line change to `PATH_EXCLUDE` if wanted later).
- Multiple simultaneous trend windows.
- Persisting history to disk across backend restarts.
- Binding the 31 white-frame tags — that is unit-modelling work, tracked in `handoff.md`.
