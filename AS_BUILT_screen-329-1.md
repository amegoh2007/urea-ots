# As-Built — DCS Screen `329-1 UREA STEAM SYSTEM`

Rev-2 image-backed overlay screen + PIC-329205 / PIC-329207 controller faceplates.
Backend steam model (4-level network) was pre-existing; this change adds the operator screen and
the two split-range/master mode+SP handlers.

## Files touched
| File | Change |
|---|---|
| `frontend/index.html` | `#screen-329-1.shot` background rule; empty `.screen.shot#screen-329-1` div (tab auto-built by `buildTabs()`) |
| `frontend/overlays.js` | `OV['screen-329-1']` — 26 overlay entries (10 bound ind, 5 avalve, 2 faceplate, 5 white-frame ind, 4 nav) |
| `frontend/app.js` | `T` type-map: `PIC-329205→pic329205_set`, `PIC-329207→pic329207_set`; per-loop physics `note` appended to faceplate status line |
| `backend/steam_system.py` | `SteamState.pic205_mode/pic205_sp/pic207_mode/pic207_sp`; AUTO-gated split-range (205A/205B) and LP master PI; MAN = bumpless freeze |
| `backend/main.py` | `STEAM_SYSTEM.PIC_329205` / `PIC_329207` telemetry blocks `{pv,sp,op,mode}`; WS handlers `pic329205_set` / `pic329207_set` |
| `frontend/img/screen-329-1.png` | clean background (LOCAL asset — `.gitignore:5 *.png`, same as all sibling screen PNGs; not committed) |

## Bind map (every bind resolves to an emitted packet leaf key)
| Tag | Bind | Design |
|---|---|---|
| PT-329251 | `STEAM_SYSTEM.SUPPLY_25BAR.P_bara` | 25.00 bar a |
| TT-329101 | `STEAM_SYSTEM.SUPPLY_25BAR.TI_sat` | ~224 °C |
| PIC-329204 | `STEAM_SYSTEM.MP.P_bara` | 19.70 bar a |
| PV-329204 (avalve) | `STEAM_SYSTEM.MP.supply_pct` | 50.0 % |
| HV-329601 (avalve) | `STEAM_SYSTEM.HP_VENT.pct` | 0 % |
| PIC-329205 (faceplate) | `STEAM_SYSTEM.PIC_329205.pv` / `.mode` | 9.00 bar a / AUTO |
| PV-329205A (avalve) | `STEAM_SYSTEM.DRUM_9BAR.admit_pct` | 0 % |
| PV-329205B (avalve) | `STEAM_SYSTEM.DRUM_9BAR.letdown_pct` | 0 % |
| TT-329001 | `STEAM_SYSTEM.LP.TI_sat` | 146.3 °C |
| PI-329206 | `STEAM_SYSTEM.LP.P_bara` | 4.40 bar a |
| PIC-329207 (faceplate) | `STEAM_SYSTEM.PIC_329207.pv` / `.mode` | 4.40 bar a / AUTO |
| PV-329207C (avalve) | `STEAM_SYSTEM.LP_MAKEUP.PV_329207C` | 0 % |

White-frame (unmodelled, tag only, no bind): MASTER-SP, LIC-329504/503/502, LV-329504/503,
FT-329403, FT-329407, PV-329207A, PV-329207B.
Nav hotspots → `screen-322-1`: 322E001 (×2), 322E002 (×2) — boundary exchangers with live home screen.

## Faceplate physics (mode = MAN red / AUTO green)
- **PIC-329205** split-range on 9-bar drum (PV = `DRUM_9BAR.P_bara`):
  $P_9 > \text{SP}+\text{DB}_9 \Rightarrow$ PV-329205B let-down opens (9→4 bar);
  $P_9 < \text{SP}-\text{DB}_9 \Rightarrow$ PV-329205A admits 25-bar BL steam.
- **PIC-329207** 4-bar header master (PV = `LP.P_bara`), PI with anti-windup clamp:
  $\uparrow P_{LP} \Rightarrow$ vent; $\downarrow P_{LP} \Rightarrow$ 25-bar make-up (stream 963).
- MAN freezes the actuator writes / holds `i_pic`; defaults (`pic205_sp=P_9\_SP\_BARA=9.0`,
  `pic207_sp=P_LP\_SP\_BARA=4.4`, mode AUTO) reproduce the fixed point **bit-for-bit**.

## Verification (all green)
1. `steam_system.py` self-test: OVERALL PASS (25 / 19.7 / 9.0 / 4.4; m_903=m_ld9=m_pic=0).
2. `tests/coldstart_probe.py`: PASS; MAN→AUTO bumpless return dP9 = dP_LP = **0.000e+00**.
3. Domino spot-check: `STRIP_322E001.steam.TI_shell`=211.6, `HPCC_322E002.TT_329001`=146.3.
4. `run_full_audit`: EXIT 0 (backend engine unchanged since).
5. UI conformance: `node --check` clean; OV invariants PASS (faceplates match `CTRL_RE`, nav has `goto`, avalve has bind).
6. Live WS (`ws://127.0.0.1:8000/ws`): all 8 `STEAM_SYSTEM` blocks emit; `pic329205_set{mode:MAN}` and `pic329207_set{sp:4.5}` applied and read back.
7. Grep-audit: every bind resolves to an emitted leaf key.
