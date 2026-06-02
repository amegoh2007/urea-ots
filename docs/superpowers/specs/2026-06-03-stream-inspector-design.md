# Stream Inspector — Design Spec

**Date:** 2026-06-03
**Feature:** Pressing any process stream on the DCS mimic opens a popup showing the whole stream properties and full composition.
**Scope unit:** 321 NH₃ feed + 322 synthesis loop (modelled streams only). Future units extend the same mechanism.

---

## 1. Goal

Click any modelled process stream line on any screen (current and future-generated) → popup shows the **complete** stream state:

- Properties: route, phase, temperature, pressure, mass flow (t/h + kg/h), molar flow, average molecular weight, density, volumetric flow.
- Composition: all present components, each with **both** mole % and mass %.

Replaces the existing partial system (7 hand-written streams, mixed/partial composition) with one uniform, data-driven mechanism.

## 2. Approach (selected: A)

Uniform backend stream registry + generic frontend renderer + data-driven hotspots.

Rationale vs alternatives:

- **B (frontend-only adapters):** keeps per-stream accessor mess; many streams lack the other %-basis or ρ/vol → cannot honour dual-% / full-props uniformly; every future unit needs a new adapter. Rejected.
- **C (on-demand endpoint):** new request path + latency; streams already computed each tick → redundant recompute. Overkill. Rejected.

Only A delivers dual-% from a single source and "works on future screens with no renderer change."

## 3. Data flow

```
unit fns (stripper / ejector / hpcc / co2 / feed)
   |  per-component kmol/h dict each
   v
make_stream(comp_kmolh, T, P, src, dst, phase, rho?)   <- single canonical builder
   |  derives BOTH mol% + mass% from one kmol/h vector
   v
packet["STREAMS"] = { id: streamObj, ... }              <- new packet section
   |  WebSocket push, 2 Hz
   v
frontend lastState.STREAMS[id] --click--> renderStream() --> #streamModal
```

Single builder guarantees mol % and mass % are always mutually consistent (both derived from the same molar vector). Eliminates the historical mol%/mass% drift between unit returns.

## 4. Backend

### 4.1 Canonical stream object

```python
{
  "name": str, "src": str, "dst": str, "phase": str,   # gas | liquid | two-phase | vapor
  "T_C": float, "P_bara": float,
  "mass_kgh": float, "mass_th": float,
  "mol_kmolh": float, "MW": float,
  "rho": float|None, "vol_m3h": float|None,
  "mol_pct":  {9 comps}, "mass_pct": {9 comps},
}
```

### 4.2 Builder

```python
def make_stream(comp_kmolh, T, P, name, src, dst, phase, rho=None):
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
```

### 4.3 Governing relations (display-only, not renormalised)

Per-component mass flow from molar flow:

$$\dot m_i = \dot n_i \, M_{w,i}$$

Totals:

$$\dot n_\text{tot} = \sum_{i} \dot n_i, \qquad \dot m_\text{tot} = \sum_{i} \dot m_i = \sum_{i} \dot n_i M_{w,i}$$

Average molecular weight:

$$\overline{M_w} = \frac{\dot m_\text{tot}}{\dot n_\text{tot}} = \frac{\sum_i \dot n_i M_{w,i}}{\sum_i \dot n_i}$$

Mole and mass fractions (shown as %):

$$y_i^{\text{(mol)}} = \frac{\dot n_i}{\dot n_\text{tot}} \times 100, \qquad
  w_i^{\text{(mass)}} = \frac{\dot n_i M_{w,i}}{\sum_j \dot n_j M_{w,j}} \times 100$$

Volumetric flow when density known:

$$\dot V = \frac{\dot m_\text{tot}}{\rho}$$

Component MW (`MW_COMP`, kg/kmol): CO₂ 44.0098, CH₄ 16.043, H₂ 2.0158, H₂O 18.0152, N₂ 28.0134, NH₃ 17.0304, O₂ 31.9988, Urea 60.056, Biuret 103.081.

Every stream feeds the builder a **kmol/h dict**. Existing unit returns already expose these (`top_kmolh`, `bot_kmolh`, `gas_kmolh`, `liq_kmolh`). Ejector `comp` is kg/h → convert per component $\dot n_i = \dot m_i / M_{w,i}$. Pure streams = single-key dict.

### 4.4 Stream set (modelled)

| id | line | phase | comp source | ρ/vol |
|---|---|---|---|---|
| `NH3_FEED` | BL 309E005 → 321D003 | liquid | pure NH₃ (FI_321401) | const NH₃ ρ |
| `PUMP_SUCT` | suction header → HP pump | liquid | pure NH₃ | — |
| `HP_DISCH` | HP pump → 322F001 motive | liquid | pure NH₃ | — |
| `CARB_RECYCLE` | 322E003 overflow → ejector suction | liquid | carbamate (ej suction) | ej ρ |
| `EJ_DISCH` | 322F001 → 322E002 | liquid | `EJ.comp` kg/h | ej ρ |
| `CO2_FEED` | CO₂ compressor → 322E001 | gas | CO₂ + passivation O₂/N₂/H₂ | gas ρ |
| `STRIP_TOP` | 322E001 → 322E002 (TT-322013) | gas | `strip.top_kmolh` | — |
| `STRIP_BOT` | 322E001 bottom → downstream | liquid | `strip.bot_kmolh` | — |
| `HPCC_PROD` | 322E002 → 322R001 (TT-322010) | two-phase | `hpcc.gas_kmolh + liq_kmolh` | — |
| `HPCC_STEAM` | shell → LP 4.4 bar header | vapor | pure H₂O (`steam_kgh`) | steam ρ |
| `HPCC_COND` | 322D001 A/B → shell (TT-329001) | liquid | pure H₂O | water ρ |

~11 streams now. Future units append rows; builder unchanged. Unknown ρ → `None` → popup shows "—" (no fabricated values).

## 5. Frontend

### 5.1 Generic renderer (replaces all hand-written `STREAM_INFO.rows()`)

```javascript
const COMP_LBL = {CO2:'CO₂',CH4:'CH₄',H2:'H₂',H2O:'H₂O',N2:'N₂',
                  NH3:'NH₃',O2:'O₂',Urea:'Urea',Biuret:'Biuret'};
const f = (v,d)=> (v==null? '—' : (+v).toFixed(d));

function renderStream(s){
  const rows = [
    ['Route',        s.src+' → '+s.dst],
    ['Phase',        s.phase],
    ['Temperature',  f(s.T_C,1)+' °C'],
    ['Pressure',     f(s.P_bara,1)+' bar a'],
    ['Mass flow',    f(s.mass_th,2)+' t/h ('+f(s.mass_kgh,0)+' kg/h)'],
    ['Molar flow',   f(s.mol_kmolh,1)+' kmol/h'],
    ['Avg MW',       f(s.MW,2)+' kg/kmol'],
    ['Density',      s.rho!=null ? f(s.rho,1)+' kg/m³' : '—'],
    ['Volum. flow',  s.vol_m3h!=null ? f(s.vol_m3h,1)+' m³/h' : '—'],
    ['', ''],                                   // spacer
    ['Composition', 'mol %  |  mass %'],        // sub-header
  ];
  Object.keys(COMP_LBL).forEach(k=>{
    const mo=s.mol_pct[k]||0, ma=s.mass_pct[k]||0;
    if(mo>0 || ma>0)
      rows.push([COMP_LBL[k], f(mo,3)+'  |  '+f(ma,3)]);
  });
  return rows;
}
```

Reuses the existing 2-column `#stream-table` — no HTML/CSS change. Composition packed as `mol | mass` in the value cell. Components that are zero in both bases are hidden (noise cut); any present component shows full dual-%.

### 5.2 Popup open

```javascript
function openStreamPopup(id){
  const s = (lastState.STREAMS||{})[id]; if(!s) return;
  document.getElementById('stream-title').textContent = s.name;
  document.getElementById('stream-table').innerHTML =
    renderStream(s).map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`).join('');
  document.getElementById('streamModal').classList.add('show');
}
```

`STREAM_INFO` deleted. `STREAM_TAG` (hover labels) kept, re-keyed to new ids.

### 5.3 Hotspots — two mechanisms, one handler

**HTML screens (321, 322-2):** existing `.stream-click[data-stream=ID]` divs in index.html. Existing handler binds at app.js ~L235. Existing 7 elements get `data-stream` updated to new ids; missing lines added as new positioned divs.

**Image screens (322-1 and any future generated screen):** new overlay type in overlays.js.

```javascript
// OV entry:
{ t:'strm', stream:'STRIP_TOP', x:600, y:200, w:120, h:18 }
```

Renderer case:

```javascript
if(o.t==='strm'){
  const d=document.createElement('div');
  d.className='stream-click'; d.dataset.stream=o.stream;
  d.style.cssText=`position:absolute;left:${o.x}px;top:${o.y}px;`
                 +`width:${o.w}px;height:${o.h}px;cursor:pointer`;
  d.addEventListener('click',()=>openStreamPopup(o.stream));
  host.appendChild(d); return;
}
```

Transparent rectangle over the baked-in PNG line. Tooltip via the existing `.stream-click` tip selector.

### 5.4 Future-screen extensibility (hard requirement)

A new unit/screen requires **only**:

1. Backend appends its stream(s) to `STREAMS{}` via `make_stream`.
2. Frontend drops `{t:'strm',stream:ID,x,y,w,h}` overlay entries (or `.stream-click` divs on HTML screens).

`renderStream`, `openStreamPopup`, and the schema are never touched. Zero renderer change.

## 6. Migration of existing 7 popups

| old `data-stream` | new id |
|---|---|
| `AL` | `NH3_FEED` |
| `SUCT` | `PUMP_SUCT` |
| `DISCH` | `HP_DISCH` |
| `MOTIVE` | `HP_DISCH` (same motive line) |
| `CPL` | `CARB_RECYCLE` |
| `ESUCT` | `CARB_RECYCLE` |
| `EDISCH` | `EJ_DISCH` |

Update `data-stream` attrs in index.html to new ids; delete `STREAM_INFO`; re-key `STREAM_TAG`. `MOTIVE`+`DISCH` collapse to one physical line → both point at `HP_DISCH` (or drop the duplicate hotspot). `CPL`+`ESUCT` both = carbamate recycle → `CARB_RECYCLE`.

## 7. Edge cases

- **Unknown ρ** → `None` → "—". No fabricated density/vol.
- **Unit off / zero flow** → totals 0 → MW 0, all comps 0 → composition block empty (all hidden); properties show zeros. Acceptable.
- **Pure stream** (NH₃, H₂O) → single comp row at 100.000 | 100.000.
- **Two-phase `HPCC_PROD`** → composition = gas + liquid combined; `phase:"two-phase"`; T = TT-322010 (liquid-phase temp per HPCC mapping). Phase shown so the operator knows the T basis.
- **Missing stream id** in packet → `openStreamPopup` early-returns (no crash).
- **Rounding** → mol%/mass% sums ≈ 100 ± rounding; not renormalised (display only).

## 8. Testing / validation

**Backend** (`py_compile` + design-point self-test):

- `STREAMS["STRIP_TOP"].mass_th` ≈ HMB 60.78 t/h within 0.1 %; `EJ_DISCH`, and `HPCC_PROD` (gas+liq) ≈ 248.6 t/h within 0.1 %.
- Every stream with flow > 0: `sum(mol_pct)` ≈ 100 and `sum(mass_pct)` ≈ 100 (± 0.05).
- Builder self-consistency: `mass_kgh == Σ nᵢ·MWᵢ`.

**Frontend:** `node --check app.js overlays.js`. Manual: click each hotspot on all screens → popup shows full props + dual-% composition; off-unit → graceful zeros; "—" where ρ unknown.

## 9. Files touched

- `backend/main.py` — add `make_stream()`, build `STREAMS{}` (~11 entries), add to packet.
- `frontend/app.js` — delete `STREAM_INFO`, add `renderStream()` + `COMP_LBL`, rewrite `openStreamPopup`, re-key `STREAM_TAG`.
- `frontend/overlays.js` — add `t:'strm'` render case, add stream hotspot entries to `OV["screen-322-1"]`.
- `frontend/index.html` — remap existing `.stream-click` `data-stream` attrs to new ids; add missing hotspot divs on 321 / 322-2.

## 10. Out of scope (YAGNI)

- Unmodelled downstream lines (granulation, evaporation) — no hotspots until those units are modelled.
- No new modal HTML/CSS.
- No on-demand endpoint.
- No composition renormalisation.
