# Stream Inspector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clicking any modelled process-stream line on the DCS mimic pops up the stream's full properties (route, phase, T, P, mass/molar flow, MW, density, volumetric flow) and full composition (all 9 components, both mol % and mass %).

**Architecture:** One backend builder `make_stream()` converts a per-component kmol/h vector into a uniform stream object (deriving mol % AND mass % from the same molar vector, eliminating drift). `step_sim()` emits `packet["STREAMS"] = {id: streamObj}` for ~11 modelled streams. The frontend has ONE generic `renderStream()` that dumps any stream object — no per-stream code. Hotspots are authored per-screen: existing vector screens via `.stream-click` SVG polylines (`index.html`), image-backed/future screens via a new `t:'strm'` overlay type (`overlays.js`). Future units plug in by appending a backend stream + dropping a hotspot; the schema and renderer never change.

**Tech Stack:** Python (FastAPI/WebSocket sim, `backend/main.py`), vanilla JS/HTML/CSS frontend (`frontend/app.js`, `frontend/overlays.js`, `frontend/index.html`). Backend self-test is a plain-`assert` script (repo has no pytest); JS validated with `node --check`.

**Spec:** `docs/superpowers/specs/2026-06-03-stream-inspector-design.md` (committed 0cd6a3b).

---

## File Structure

- `backend/main.py` — add `make_stream()` builder (after `hpcc_322e002`, ~L337); expose `co2_feed_kmolh` from `stripper_322e001` return (~L264); build `streams = {...}` just before the `step_sim` `return {` (~L603) and add `"STREAMS": streams` to the packet (~L721).
- `backend/test_streams.py` — **new** plain-assert self-test for `make_stream()` invariants + packet integration + cross-links.
- `frontend/app.js` — delete `STREAM_INFO` (L277–315); add `COMP_LBL`, `fStrm()`, `renderStream()`; rewrite `openStreamPopup()` to read `lastState.STREAMS` (L316–321); re-key `STREAM_TAG` (L341–345).
- `frontend/overlays.js` — add `t:'strm'` to `activate()` (~L240), to the build-loop className + sizing (~L294/L300), CSS in `injectCSS()` (~L331); append stream hotspots to `OV['screen-322-1']` (~L91).
- `frontend/index.html` — remap 7 `.stream-click` `data-stream` ids to the new stream ids (L203–371).

---

## Task 1: Backend `make_stream()` builder

**Files:**
- Modify: `backend/main.py` (insert after `hpcc_322e002` return, between L337 blank line and `# ----- PID -----` L339)
- Test: `backend/test_streams.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/test_streams.py`:

```python
"""Stream-inspector self-test: make_stream() invariants + packet integration.
Plain asserts (repo has no pytest). Run:  python backend/test_streams.py"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
from main import make_stream, MW_COMP

REQ_KEYS = {"name", "src", "dst", "phase", "T_C", "P_bara", "mass_kgh", "mass_th",
            "mol_kmolh", "MW", "rho", "vol_m3h", "mol_pct", "mass_pct"}


def test_make_stream_invariants():
    s = make_stream({"NH3": 1000.0, "CO2": 200.0}, 100.0, 144.2,
                    "t", "A", "B", "gas", rho=600.0)
    assert REQ_KEYS <= set(s), "missing keys: %s" % (REQ_KEYS - set(s))
    exp_kgh = 1000.0 * MW_COMP["NH3"] + 200.0 * MW_COMP["CO2"]
    assert abs(s["mass_kgh"] - round(exp_kgh, 1)) < 0.2          # mass = Σ nᵢ·MWᵢ
    assert abs(s["mass_th"] - s["mass_kgh"] / 1000.0) < 1e-3   # both rounded from m_tot (1 dp vs 3 dp)
    assert abs(sum(s["mol_pct"].values()) - 100.0) < 0.1          # mol % closes
    assert abs(sum(s["mass_pct"].values()) - 100.0) < 0.1         # mass % closes
    assert abs(s["vol_m3h"] - round(exp_kgh / 600.0, 2)) < 0.1    # vol = m/ρ


def test_make_stream_zero_flow():
    s = make_stream({}, 50.0, 1.0, "z", "A", "B", "liquid")
    assert s["mass_kgh"] == 0.0 and s["MW"] == 0.0
    assert s["rho"] is None and s["vol_m3h"] is None              # unknown ρ → None
    assert sum(s["mol_pct"].values()) == 0.0


def test_streams_in_packet():
    pkt = main.step_sim(1.0)
    assert "STREAMS" in pkt
    st = pkt["STREAMS"]
    expect = {"NH3_FEED", "PUMP_SUCT", "HP_DISCH", "CARB_RECYCLE", "EJ_DISCH",
              "CO2_FEED", "STRIP_TOP", "STRIP_BOT", "HPCC_PROD", "HPCC_STEAM", "HPCC_COND"}
    assert expect <= set(st), "missing streams: %s" % (expect - set(st))
    for sid, s in st.items():
        assert REQ_KEYS <= set(s), sid
        if s["mol_kmolh"] > 0:
            assert abs(sum(s["mol_pct"].values()) - 100.0) < 0.2, sid
            assert abs(sum(s["mass_pct"].values()) - 100.0) < 0.2, sid


def test_streams_crosslink():
    main.state.tank_level_frac = 0.5
    main.state.XV_321901 = True
    main.state.XV_322901 = True
    main.state.XV_322902 = True
    main.state.pumpA["on"] = True
    main.state.pumpB["on"] = True
    pkt = {}
    for _ in range(40):
        pkt = main.step_sim(0.5)
    st = pkt["STREAMS"]
    assert abs(st["EJ_DISCH"]["mass_th"] - pkt["EJ_322F001"]["total_th"]) < 0.05
    assert abs(st["STRIP_TOP"]["mass_th"] - pkt["STRIP_322E001"]["top_th"]) < 0.05
    assert abs(st["HPCC_PROD"]["mass_th"]
               - (pkt["HPCC_322E002"]["gas_th"] + pkt["HPCC_322E002"]["liq_th"])) < 0.1


if __name__ == "__main__":
    fails = 0
    for t in (test_make_stream_invariants, test_make_stream_zero_flow,
              test_streams_in_packet, test_streams_crosslink):
        try:
            t(); print("PASS", t.__name__)
        except Exception:
            fails += 1; print("FAIL", t.__name__); traceback.print_exc()
    raise SystemExit(1 if fails else 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python backend/test_streams.py`
Expected: FAIL — `ImportError: cannot import name 'make_stream' from 'main'` (import line raises before any test runs; exit code 1).

- [ ] **Step 3: Write minimal implementation**

In `backend/main.py`, locate the end of `hpcc_322e002` (the return block ending at L336):

```python
        "T_prod": HPCC_T_PROD_DES_C, "P_bara": HPCC_P_DES_BARA,
        "duty_kw": duty_kw, "steam_kgh": steam_kgh,
    }


# ----- PID -----
```

Insert the builder between the `}` and `# ----- PID -----`:

```python
        "T_prod": HPCC_T_PROD_DES_C, "P_bara": HPCC_P_DES_BARA,
        "duty_kw": duty_kw, "steam_kgh": steam_kgh,
    }


def make_stream(comp_kmolh, T, P, name, src, dst, phase, rho=None):
    """Uniform process-stream object. Derives BOTH mol % and mass % from the same
    per-component kmol/h vector, so the two bases can never drift. rho unknown -> None
    -> density/volumetric flow render as '—' (no fabricated numbers)."""
    n = {k: comp_kmolh.get(k, 0.0) for k in MW_COMP}
    m = {k: n[k] * MW_COMP[k] for k in MW_COMP}
    n_tot = sum(n.values()); m_tot = sum(m.values())
    return {
        "name": name, "src": src, "dst": dst, "phase": phase,
        "T_C": round(T, 1), "P_bara": round(P, 1),
        "mass_kgh": round(m_tot, 1), "mass_th": round(m_tot / 1000.0, 3),
        "mol_kmolh": round(n_tot, 2),
        "MW": round(m_tot / n_tot, 3) if n_tot else 0.0,
        "rho": (round(rho, 1) if rho else None),
        "vol_m3h": (round(m_tot / rho, 2) if rho else None),
        "mol_pct":  {k: round(n[k] / n_tot * 100.0, 3) if n_tot else 0.0 for k in MW_COMP},
        "mass_pct": {k: round(m[k] / m_tot * 100.0, 3) if m_tot else 0.0 for k in MW_COMP},
    }


# ----- PID -----
```

- [ ] **Step 4: Run the builder tests to verify they pass**

Run: `python backend/test_streams.py`
Expected: `PASS test_make_stream_invariants` and `PASS test_make_stream_zero_flow`.
`test_streams_in_packet` / `test_streams_crosslink` still FAIL (`AssertionError: assert "STREAMS" in pkt`) — implemented in Task 2. Exit code 1 is expected here.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/test_streams.py
git commit -m "feat(streams): add make_stream() uniform stream-object builder"
```

---

## Task 2: Emit `STREAMS` registry from `step_sim`

**Files:**
- Modify: `backend/main.py` — stripper return (L264), `streams` block before `return {` (L603), packet key after HPCC block (L721)
- Test: `backend/test_streams.py` (already written in Task 1)

- [ ] **Step 1: The failing tests already exist**

`test_streams_in_packet` and `test_streams_crosslink` from Task 1 are the failing tests for this task. Confirm current state:

Run: `python backend/test_streams.py`
Expected: `PASS` for the two builder tests, `FAIL test_streams_in_packet` (`assert "STREAMS" in pkt`).

- [ ] **Step 2: Expose the CO2-feed molar vector from the stripper**

`stripper_322e001`'s `feed_kmolh` is reactor-overflow **plus** CO2; the CO2 feed stream needs the CO2-only vector `co2_kmolh` (already computed at L230 but not returned). In `backend/main.py` change the stripper return's first line (L264):

```python
        "feed_kmolh": feed, "top_kmolh": top, "bot_kmolh": bot,
```

to:

```python
        "feed_kmolh": feed, "co2_feed_kmolh": co2_kmolh, "top_kmolh": top, "bot_kmolh": bot,
```

- [ ] **Step 3: Build the `streams` registry just before the packet return**

In `step_sim`, find the discharge-header line and the return (L601–604):

```python
    # Discharge header
    P_disch_header_barG = (P_SYN_DOWN_BAR - 1.0) if (s.pumpA["on"] or s.pumpB["on"]) else 7.5

    return {
```

Insert the `streams` block between `P_disch_header_barG = ...` and `return {` (every referenced local — `ej`, `strip`, `hpcc`, `motive_nh3_kgh`, `F_pump_total_th`, `PT_A`, `TI_321020` — is already in scope at this point):

```python
    # Discharge header
    P_disch_header_barG = (P_SYN_DOWN_BAR - 1.0) if (s.pumpA["on"] or s.pumpB["on"]) else 7.5

    # ---- uniform process-stream registry (clickable stream inspector) ----
    MW_NH3 = MW_COMP["NH3"]
    streams = {
        "NH3_FEED": make_stream(
            {"NH3": F_pump_total_th * 1000.0 / MW_NH3}, s.tank_T_C, s.tank_P_top_barG + 1.0,
            "NH3 ex 309E005", "309E005", "321D003", "liquid", rho=NH3_RHO),
        "PUMP_SUCT": make_stream(
            {"NH3": F_pump_total_th * 1000.0 / MW_NH3}, s.tank_T_C, PT_A + 1.0,
            "NH3 pump suction header", "321D003", "321P002 A/B", "liquid", rho=NH3_RHO),
        "HP_DISCH": make_stream(
            {"NH3": motive_nh3_kgh / MW_NH3}, TI_321020, P_SYN_DOWN_BAR,
            "HP NH3 discharge (motive)", "321P002 A/B", "322F001", "liquid", rho=NH3_RHO),
        "CARB_RECYCLE": make_stream(
            {k: ej["suction_kgh"] * EJ_CARB_FRAC[k] / MW_COMP[k] for k in MW_COMP},
            EJ_T_SUCTION_C, EJ_P_SUCTION_BARA,
            "Carbamate recycle (322E003 overflow)", "322E003", "322F001", "liquid"),
        "EJ_DISCH": make_stream(
            {k: ej["comp"][k] / MW_COMP[k] for k in MW_COMP}, ej["T_C"], ej["P_bara"],
            "Ejector discharge (carbamate liq.)", "322F001", "322E002", "liquid", rho=ej["rho"]),
        "CO2_FEED": make_stream(
            strip["co2_feed_kmolh"], CO2_T_FEED_C, STRIP_P_DES_BARA,
            "CO2 feed gas", "320K002", "322E001", "gas"),
        "STRIP_TOP": make_stream(
            strip["top_kmolh"], strip["T_top"], STRIP_P_DES_BARA,
            "Stripper top gas", "322E001", "322E002", "gas"),
        "STRIP_BOT": make_stream(
            strip["bot_kmolh"], strip["T_bot"], STRIP_P_DES_BARA,
            "Stripper bottom solution", "322E001", "LV-322501", "liquid"),
        "HPCC_PROD": make_stream(
            hpcc["feed_kmolh"], hpcc["T_prod"], hpcc["P_bara"],
            "HPCC two-phase product", "322E002", "322R001", "two-phase"),
        "HPCC_STEAM": make_stream(
            {"H2O": hpcc["steam_kgh"] / MW_COMP["H2O"]}, HPCC_STEAM_TSAT_C, HPCC_STEAM_P_BARA,
            "LP steam (shell side)", "322E002 shell", "LP header", "vapor"),
        "HPCC_COND": make_stream(
            {"H2O": hpcc["steam_kgh"] / MW_COMP["H2O"]}, HPCC_STEAM_TSAT_C, HPCC_STEAM_P_BARA,
            "BFW/condensate feed", "322D001 A/B", "322E002 shell", "liquid"),
    }

    return {
```

(`HPCC_PROD` uses `hpcc["feed_kmolh"]`, which equals gas + liquid by construction — the full two-phase product.)

- [ ] **Step 4: Add the `STREAMS` key to the packet**

Find the end of the `HPCC_322E002` block and the `ratio` key (L720–722):

```python
                "duty_kW":  round(hpcc["duty_kw"], 0),       # condensation duty (kW)
            },
        },
        "ratio": {
```

Insert `"STREAMS": streams,` between the HPCC block's closing `},` and `"ratio": {`:

```python
                "duty_kW":  round(hpcc["duty_kw"], 0),       # condensation duty (kW)
            },
        },
        "STREAMS": streams,
        "ratio": {
```

- [ ] **Step 5: Compile-check then run the full self-test**

Run: `python -m py_compile backend/main.py`
Expected: no output (exit 0).

Run: `python backend/test_streams.py`
Expected: all four lines `PASS ...`; exit code 0.

- [ ] **Step 6: Commit**

```bash
git add backend/main.py
git commit -m "feat(streams): emit STREAMS registry of 11 modelled streams from step_sim"
```

---

## Task 3: Frontend generic `renderStream()` + `openStreamPopup` rewrite

**Files:**
- Modify: `frontend/app.js` — replace `STREAM_INFO` + `openStreamPopup` (L276–321); re-key `STREAM_TAG` (L341–345)

- [ ] **Step 1: Replace `STREAM_INFO` and `openStreamPopup` with the generic renderer**

In `frontend/app.js`, select the whole block from the comment `// ---------- Stream popup data ----------` (L276) through the end of `openStreamPopup` (the line ending `...classList.add('show'); }`, L321). Replace it with:

```javascript
// ---------- Stream popup (generic renderer over packet STREAMS) ----------
const COMP_LBL = {CO2:'CO₂',CH4:'CH₄',H2:'H₂',H2O:'H₂O',N2:'N₂',
                  NH3:'NH₃',O2:'O₂',Urea:'Urea',Biuret:'Biuret'};
const fStrm = (v,d)=> (v==null ? '—' : (+v).toFixed(d));
function renderStream(s){
  const rows = [
    ['Route', s.src+' → '+s.dst], ['Phase', s.phase],
    ['Temperature', fStrm(s.T_C,1)+' °C'], ['Pressure', fStrm(s.P_bara,1)+' bar a'],
    ['Mass flow', fStrm(s.mass_th,2)+' t/h ('+fStrm(s.mass_kgh,0)+' kg/h)'],
    ['Molar flow', fStrm(s.mol_kmolh,1)+' kmol/h'], ['Avg MW', fStrm(s.MW,2)+' kg/kmol'],
    ['Density', s.rho!=null ? fStrm(s.rho,1)+' kg/m³' : '—'],
    ['Volum. flow', s.vol_m3h!=null ? fStrm(s.vol_m3h,1)+' m³/h' : '—'],
    ['', ''], ['Composition', 'mol %  |  mass %'],
  ];
  Object.keys(COMP_LBL).forEach(k=>{
    const mo = (s.mol_pct&&s.mol_pct[k])||0, ma = (s.mass_pct&&s.mass_pct[k])||0;
    if(mo>0 || ma>0) rows.push([COMP_LBL[k], fStrm(mo,3)+'  |  '+fStrm(ma,3)]);
  });
  return rows;
}
function openStreamPopup(id){
  const s = (lastState.STREAMS||{})[id]; if(!s) return;
  document.getElementById('stream-title').textContent = s.name;
  document.getElementById('stream-table').innerHTML =
    renderStream(s).map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`).join('');
  document.getElementById('streamModal').classList.add('show');
}
```

Leave the next line (`document.getElementById('s-close').onclick = ...`, L322) unchanged.

- [ ] **Step 2: Re-key `STREAM_TAG` to the new stream ids**

Replace the `STREAM_TAG` object (L341–345):

```javascript
const STREAM_TAG = {
  AL:'NH3 EX 309E005', SUCT:'NH3 SUCTION HDR',
  DISCH:'NH3 HP DISCHARGE', CPL:'CARBAMATE (CPL)',
  MOTIVE:'MOTIVE NH3', ESUCT:'CARBAMATE EX 322E003', EDISCH:'CARB. LIQ. → 322E002'
};
```

with:

```javascript
const STREAM_TAG = {
  NH3_FEED:'NH3 EX 309E005', PUMP_SUCT:'NH3 SUCTION HDR',
  HP_DISCH:'NH3 HP DISCHARGE', CARB_RECYCLE:'CARBAMATE EX 322E003',
  EJ_DISCH:'CARB. LIQ. → 322E002', CO2_FEED:'CO2 FEED GAS',
  STRIP_TOP:'STRIP TOP GAS', STRIP_BOT:'STRIP BOTTOM SOLN',
  HPCC_PROD:'HPCC PRODUCT → 322R001', HPCC_STEAM:'LP STEAM 4.4 BARA',
  HPCC_COND:'BFW/COND → 322E002'
};
```

- [ ] **Step 3: Syntax-check**

Run: `node --check frontend/app.js`
Expected: no output (exit 0).

- [ ] **Step 4: Commit**

```bash
git add frontend/app.js
git commit -m "feat(streams): replace hand-written STREAM_INFO with generic renderStream()"
```

---

## Task 4: `overlays.js` `t:'strm'` hotspot type + screen-322-1 hotspots

**Files:**
- Modify: `frontend/overlays.js` — `activate()` (~L240), build loop (~L294 + ~L300), `injectCSS()` (~L331), `OV['screen-322-1']` (~L91)

- [ ] **Step 1: Add the run-mode click action**

In `activate()` find the `nav` branch (L238–241):

```javascript
    } else if (o.t === 'nav') {
      if (o.goto && window.otsSwitchScreen) window.otsSwitchScreen(o.goto);
      return;
    } else if (o.t === 'ind') {
```

Insert a `strm` branch between `nav` and `ind`:

```javascript
    } else if (o.t === 'nav') {
      if (o.goto && window.otsSwitchScreen) window.otsSwitchScreen(o.goto);
      return;
    } else if (o.t === 'strm') {
      if (o.stream && window.openStreamPopup) window.openStreamPopup(o.stream);
      return;
    } else if (o.t === 'ind') {
```

- [ ] **Step 2: Add `strm` to the build-loop className**

Find the className line (L294):

```javascript
      el.className = 'ov ' + (o.t === 'pump' ? 'pump' : o.t === 'xv' ? 'avalve' : o.t === 'nav' ? 'nav' : 'ind');
```

Replace with (adds the `strm` class):

```javascript
      el.className = 'ov ' + (o.t === 'pump' ? 'pump' : o.t === 'xv' ? 'avalve' : o.t === 'nav' ? 'nav' : o.t === 'strm' ? 'strm' : 'ind');
```

- [ ] **Step 3: Add `strm` sizing in the build loop**

Find the `nav` sizing branch (L300–303):

```javascript
      } else if (o.t === 'nav') {
        el.style.width = (o.w || 60) + 'px';
        el.style.height = (o.h || 24) + 'px';
      }
```

Replace with (adds a transparent sized hotspot; `dataset.stream` lets `tagOf` resolve the hover label):

```javascript
      } else if (o.t === 'nav') {
        el.style.width = (o.w || 60) + 'px';
        el.style.height = (o.h || 24) + 'px';
      } else if (o.t === 'strm') {
        el.style.width = (o.w || 120) + 'px';
        el.style.height = (o.h || 16) + 'px';
        el.dataset.stream = o.stream;
      }
```

The existing `attach(el, sid, o)` call (L310) already wires drag-to-reposition (edit mode, persisted to `localStorage`), left-click → `activate()` (Step 1 routes `strm` to the popup), and right-click → Edit/Delete menu. No extra wiring needed.

- [ ] **Step 4: Add hotspot CSS**

In `injectCSS()` find the nav editing rule (L331):

```javascript
      'body.ov-editing .ov.nav{border-color:rgba(255,208,0,.6);background:rgba(255,208,0,.08);}' +
```

Insert the `strm` rules immediately after it:

```javascript
      'body.ov-editing .ov.nav{border-color:rgba(255,208,0,.6);background:rgba(255,208,0,.08);}' +
      '.ov.strm{background:transparent;border:1px solid transparent;border-radius:3px;}' +
      '.ov.strm:hover{border-color:rgba(127,208,216,.85);background:rgba(80,160,220,.14);}' +
      'body.ov-editing .ov.strm{border-color:rgba(255,160,60,.7);background:rgba(255,160,60,.10);}' +
```

- [ ] **Step 5: Append stream hotspots to `OV['screen-322-1']`**

Find the `OV['screen-322-1']` array opener (L91):

```javascript
    'screen-322-1': [
      // ===== CO2 FEED LINE (Item 5) — bound to backend CO2_FEED packet =====
```

Insert the hotspot block right after the `[` (keep the existing entries below it). These are initial positions to be drag-aligned to the background lines in edit mode; clicking already shows the correct data regardless of pixel alignment:

```javascript
    'screen-322-1': [
      // ===== STREAM-INSPECTOR HOTSPOTS (clickable process lines; drag in edit mode to align) =====
      { k: 'strm-co2',   t: 'strm', stream: 'CO2_FEED',     tag: 'CO2 FEED GAS',          x: 360, y: 600, w: 160, h: 20 },
      { k: 'strm-nh3',   t: 'strm', stream: 'NH3_FEED',     tag: 'NH3 EX 309E005',        x: 360, y: 418, w: 160, h: 18 },
      { k: 'strm-disch', t: 'strm', stream: 'HP_DISCH',     tag: 'NH3 HP DISCHARGE',      x: 560, y: 300, w: 160, h: 18 },
      { k: 'strm-carb',  t: 'strm', stream: 'CARB_RECYCLE', tag: 'CARBAMATE EX 322E003',  x: 560, y: 360, w: 160, h: 18 },
      { k: 'strm-ejd',   t: 'strm', stream: 'EJ_DISCH',     tag: 'CARB. LIQ. → 322E002',  x: 760, y: 340, w: 160, h: 18 },
      { k: 'strm-stop',  t: 'strm', stream: 'STRIP_TOP',    tag: 'STRIP TOP GAS',         x: 760, y: 200, w: 160, h: 18 },
      { k: 'strm-sbot',  t: 'strm', stream: 'STRIP_BOT',    tag: 'STRIP BOTTOM SOLN',     x: 600, y: 660, w: 160, h: 18 },
      { k: 'strm-prod',  t: 'strm', stream: 'HPCC_PROD',    tag: 'HPCC PRODUCT → 322R001',x: 980, y: 300, w: 160, h: 18 },
      { k: 'strm-stm',   t: 'strm', stream: 'HPCC_STEAM',   tag: 'LP STEAM 4.4 BARA',     x: 980, y: 180, w: 160, h: 18 },
      { k: 'strm-cond',  t: 'strm', stream: 'HPCC_COND',    tag: 'BFW/COND → 322E002',    x: 980, y: 420, w: 160, h: 18 },
      // ===== CO2 FEED LINE (Item 5) — bound to backend CO2_FEED packet =====
```

- [ ] **Step 6: Syntax-check**

Run: `node --check frontend/overlays.js`
Expected: no output (exit 0).

- [ ] **Step 7: Commit**

```bash
git add frontend/overlays.js
git commit -m "feat(streams): add t:'strm' hotspot type + screen-322-1 stream hotspots"
```

---

## Task 5: Remap `index.html` `.stream-click` ids to new stream ids

**Files:**
- Modify: `frontend/index.html` — 7 `data-stream` attributes (L203, L213, L224, L231, L365, L368, L371)

- [ ] **Step 1: Remap each `data-stream` value**

Apply these seven single-attribute edits (id migration per spec §: AL→NH3_FEED, SUCT→PUMP_SUCT, DISCH→HP_DISCH, CPL→CARB_RECYCLE, ESUCT→CARB_RECYCLE, MOTIVE→HP_DISCH, EDISCH→EJ_DISCH):

| Line | From | To |
|------|------|----|
| 203 | `data-stream="AL"` | `data-stream="NH3_FEED"` |
| 213 | `data-stream="SUCT"` | `data-stream="PUMP_SUCT"` |
| 224 | `data-stream="DISCH"` | `data-stream="HP_DISCH"` |
| 231 | `data-stream="CPL"` | `data-stream="CARB_RECYCLE"` |
| 365 | `data-stream="ESUCT"` | `data-stream="CARB_RECYCLE"` |
| 368 | `data-stream="MOTIVE"` | `data-stream="HP_DISCH"` |
| 371 | `data-stream="EDISCH"` | `data-stream="EJ_DISCH"` |

Each edit changes only the quoted id; the `points="..."` geometry and `class="stream-click"` stay as-is. (CPL and ESUCT both map to `CARB_RECYCLE` — two clickable lines for one stream is fine.)

- [ ] **Step 2: Verify no stale ids remain**

Run: `grep -nE 'data-stream="(AL|SUCT|DISCH|CPL|MOTIVE|ESUCT|EDISCH)"' frontend/index.html`
Expected: no matches (exit code 1, empty output). Any match means an id was missed.

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "feat(streams): remap stream-click ids to new STREAMS registry keys"
```

---

## Task 6: End-to-end verification (manual smoke)

**Files:** none (verification only)

- [ ] **Step 1: Backend self-test green**

Run: `python backend/test_streams.py`
Expected: four `PASS` lines, exit 0.

- [ ] **Step 2: Both JS files parse**

Run: `node --check frontend/app.js` then `node --check frontend/overlays.js`
Expected: no output for either (exit 0).

- [ ] **Step 3: Live click-through**

Start the server (`python backend/main.py` or the project's usual launch) and open the UI. With pumps running and CO2 feed admitted:
- On the vector screen (321 schematic), click each of the 7 `.stream-click` lines → the modal title and table show that stream's route/phase/T/P/flows/MW/density and a composition table with `mol %  |  mass %` rows.
- Switch to `screen-322-1`, click each of the 10 stream hotspots → same full popup. If a hotspot does not overlay its line, toggle edit mode and drag it onto the line (position persists in `localStorage`).
- Confirm pure streams (NH3_FEED, PUMP_SUCT, HP_DISCH) show a single `NH₃` composition row at `100.000 | 100.000`; HPCC_PROD shows phase `two-phase`; HPCC_STEAM shows phase `vapor` and density/volumetric flow as `—`.

- [ ] **Step 4: Confirm clean tree**

Run: `git status`
Expected: working tree clean (all five code files committed across Tasks 1–5).
