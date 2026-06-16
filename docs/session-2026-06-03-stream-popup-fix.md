# Session Log — 2026-06-03 — Stream-Click Popup Fix (322R001)

**Project:** Custom OTS — Stamicarbon CO₂-stripping urea synthesis + granulation plant
**Root:** `D:\Work\Urea Simulation`
**Unit in scope:** 322R001 HP Urea Reactor (build ONE unit at a time; scrubber 322E003 NOT modelled — terminal off-gas display stream only)
**Stack:** Python FastAPI/WebSocket backend (`backend/main.py`) + HTML/JS DCS-mimic frontend (`frontend/index.html`, `app.js`, `overlays.js`)

---

## Task

> "Clicking on the following streams does not give me the composition and properties of the stream:
> 1. stream from 322R001 to 322E001
> 2. stream from 322R001 to 322E003
> 3. stream from 322E001 to 323C003"

Originating intent: *"Pressing on any stream should give the whole properties and composition of the stream."*

### Stream key mapping

| # | Pipe (visual) | Stream key | src → dst |
|---|---------------|------------|-----------|
| 1 | 322R001 → 322E001 | `REACT_OVERFLOW` | 322R001 → 322E001 |
| 2 | 322R001 → 322E003 | `REACT_OFFGAS`   | 322R001 → 322E003 |
| 3 | 322E001 → 323C003 | `STRIP_BOT`      | 322E001 → LV-322501 |

---

## Root Cause

Two compounding defects:

1. **Hotspot rects sat OFF the drawn pipes** — wrong stage coordinates, clickable boxes were nowhere near the visible pipe runs.
2. **`.ov.strm` had no CSS rule** → hotspots rendered invisible (zero background/border). User clicked the visible pipe, missed the invisible + misplaced rect → `openStreamPopup` received no element → silent no-op (`if(!s) return`).

---

## Coordinate System (reference)

- Stage = **1366 × 720**. `screen-322-1` is an empty `<div class="screen shot">` with CSS `background-image` PNG, `background-size:100% 100%`.
- Overlay hotspots absolutely positioned in stage coords, centered on (x,y) via `.ov{transform:translate(-50%,-50%)}`.
- PNG native = **1358 × 640**.

Pixel → stage:

$$\text{stage}_x = px \times \frac{1366}{1358} = px \times 1.00589$$

$$\text{stage}_y = py \times \frac{720}{640} = py \times 1.125$$

Inverse (stage → native):

$$px = \text{stage}_x \times 0.99414 \qquad py = \text{stage}_y \times 0.88889$$

---

## Fix (surgical edits)

### `frontend/overlays.js` — relocate 3 hotspots onto the pipes (`'screen-322-1'` array)

```javascript
{ k: 'strm-sbot', t: 'strm', stream: 'STRIP_BOT',      tag: 'STRIP BOTTOM SOLN',     x: 1012, y: 518, w: 40,  h: 110 },
{ k: 'strm-rov',  t: 'strm', stream: 'REACT_OVERFLOW', tag: 'OVERFLOW → 322E001',    x: 650,  y: 376, w: 220, h: 20  },
{ k: 'strm-rog',  t: 'strm', stream: 'REACT_OFFGAS',   tag: 'REACTOR GAS → 322E003', x: 840,  y: 84,  w: 240, h: 20  },
```

Previously (all off-pipe): sbot `x:600 y:660 w:160 h:18`; rov `x:1080 y:420 w:170 h:18`; rog `x:1080 y:170 w:170 h:18`.

### `frontend/index.html` — add `.ov.strm` visibility CSS (after `.ov.ind.fp{...}`)

```css
.ov.strm{background:rgba(64,224,255,.06);border:1px dashed rgba(64,224,255,.45);border-radius:2px;}
.ov.strm:hover{background:rgba(64,224,255,.22);border-color:#41e0ff;box-shadow:0 0 0 1px rgba(64,224,255,.4);}
```

Makes the previously-invisible hotspots discoverable (cyan dashed box, brightens on hover).

### `frontend/app.js` — add 2 `STREAM_TAG` entries (~L328)

```javascript
HPCC_COND:'BFW/COND → 322E002',
REACT_OVERFLOW:'OVERFLOW → 322E001', REACT_OFFGAS:'REACTOR GAS → 322E003'
```

`tagOf` was falling back to the raw key (e.g. `"REACT_OVERFLOW"`) for the 2 reactor streams; now shows clean labels.

### `backend/main.py` — no change this task

`STRIP_BOT`, `REACT_OVERFLOW` (dst 322E001), `REACT_OFFGAS` (dst 322E003) all already emitted via `make_stream(...)`.

---

## Data Path (verified intact)

- **overlays.js** `build()` → `div.ov.strm` w/ inline w/h + `dataset.stream`; `attach()` binds click → activate → `window.openStreamPopup(o.stream)`.
- **app.js** `openStreamPopup(id)` reads `(lastState.STREAMS||{})[id]`; `if(!s) return` (null-safe). `renderStream(s)` builds the modal.
- **backend** builds `STREAMS` dict via `make_stream(...)`.

---

## Verification

- **Geometry:** drew red rects on a COPY of the PNG at native-px positions, cropped/zoomed the 3 regions, visually confirmed boxes overlay the pipes. Native→stage conversions validated:
  - rog native (715,66,239,18) → stage center (839,84)
  - rov native (537,325,219,18) → stage center (650,376)
  - sbot native (986,411,40,98) → stage center (1012,518)
- **Syntax:** `node --check` clean on overlays.js / app.js.
- **Regression:** `python backend/test_reactor.py` → **11/11 PASS**. `test_packet_tags_and_streams` confirms `REACT_OVERFLOW` (dst 322E001) and `REACT_OFFGAS` (dst 322E003) in `STREAMS`; `STRIP_BOT` present in `main.py`.

---

## Cleanup

- Killed background uvicorn task `bgw4keqnh` (127.0.0.1:8000).
- Deleted preview debris: `_cdp.py`, `_cdp2.py`, `_chrtmp/`, `_pdfimg/`, temp crops (`crop_{top,mid,br}.png`, `box_{top,mid,br}.png`).
- Live `frontend/img/screen-322-1.png` untouched (clean in `git status`).

---

## Status

Fix **complete** — implemented, syntax-checked, regression-tested. **Not committed** (per standing constraint: commit/push only on explicit request).

**Next (await user):** relaunch via `launch.bat`, click each of the 3 lines → composition + properties modal.

---

## Standing Constraints (reference)

- Project root **`D:\Work\Urea Simulation`** — always pass explicit absolute paths (shell cwd resets to `C:\Program Files\Git`).
- Build ONE unit at a time; do NOT model scrubber 322E003.
- Real interpreter: `C:\Users\ameel\AppData\Local\Python\pythoncore-3.14-64\python.exe`. Windows console cp1252 → scripts need `sys.stdout.reconfigure(encoding="utf-8")`.
- Git commit footer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Commit/push ONLY when asked.

---

## Reactor Physics (preserved — completed earlier this session)

**AT-322701 N/C atom ratio:**

$$N/C = \frac{\sum_i n_i\,(\#N)_i}{\sum_i n_i\,(\#C)_i}$$

N atoms {NH₃:1, Urea:2, Biuret:3, N₂:2}; C atoms {CO₂:1, Urea:1, Biuret:2, CH₄:1}. Design $= 3.000$, invariant to throughput $s$ and valve $\phi$.

**Dynamic level (HV-322605 hand-auto valve, does NOT control level):**

$$\frac{dV}{dt} = Q_{in} - Q_{out} = \dot V_{des}\,s\left(1 - \frac{\phi}{\phi_{des}}\right)$$

$$\dot V_{des} \approx 228.46\ \mathrm{m^3/h}, \qquad V_{span} = A \cdot H_L = 6.834 \times 25 = 170.85\ \mathrm{m^3}, \qquad \phi_{des} = 0.60$$

**Reactor split-fraction model (pinned + coupled, Approach A):**

$$\dot n^{ov}_i = \nu^{ov}_{des,i}\cdot s \cdot \frac{\phi}{\phi_{des}} \qquad \dot n^{og}_i = \nu^{og}_{des,i}\cdot s$$

At design point ($s=1$, $\phi=\phi_{des}$) model pinned to design HMB vectors → every component $|\Delta| \approx 0$ (machine precision). Proven by `backend/compare_reactor.py`.
