# PROMPT — Build DCS screen 329-1 "UREA STEAM SYSTEM" (Rev-2 image-backed overlay)

Copy everything below the line into Claude Code.

---

Build the missing DCS screen **329-1 UREA STEAM SYSTEM** as a Rev-2 image-backed overlay. The 4-level steam backend (`backend/steam_system.py`, wired into `main.py`) is already built, probe-verified, and publishing telemetry — this task is the UI page plus minimal design-neutral controller-mode plumbing. Execute autonomously per CLAUDE.md (no halting, prove paths via grep, regression-gate before commit).

## 0. Read-first (blocking, in this order)
1. `ui_guidelines.md` — IN FULL (CLAUDE.md §2 UI Enforcement mandate).
2. `New folder/329-1/329-1 mapping and description.md` — unit mapping/description.
3. View images: `New folder/329-1/329-1 tagged.PNG` (tag identities/locations) and `New folder/329-1/329-1.PNG` (clean background, **1362×644**). Measure coordinates on the CLEAN image geometry; the tagged copy is 1056×502, so scale any coordinate taken from it by 1362/1056 first.
4. `backend/steam_system.py` (whole file) and `backend/main.py`: `STEAM_SYSTEM` telemetry block (~L2629–2664), stripper/HPCC `steam` sub-blocks (~L2602/2622), WS handlers `steam_supply_set` / `steam_letdown_set` / `steam_hpvent_set` / `steam_963_set` (~L2876–2890).
5. `frontend/overlays.js` `OV['screen-321-1']` and `OV['screen-322-2']` — the entry schema to replicate (`{k,t,x,y,tag,bind,u,dec,fp,mode,cmd,id}`).

## 1. Scope lock
Exactly ONE screen: `screen-329-1`. No physics changes (the only backend edits allowed are the PIC mode/SP handlers in §4, which must be bit-exact design-neutral). The working tree has unrelated uncommitted WIP — do not revert, reformat, or commit anything outside the files this task touches.

## 2. Screen scaffold (ui_guidelines §8)
- Copy `New folder/329-1/329-1.PNG` → `frontend/img/screen-329-1.png`.
- `index.html`: add `<div class="screen shot" id="screen-329-1" data-label="329-1 UREA STEAM SYSTEM">` containing one `.ov-layer`; add CSS rule `#screen-329-1.shot{background-image:url("img/screen-329-1.png");}` beside the existing three.
- Tab bar and right-click `#screenmenu` auto-populate from `.screen` divs (`buildTabs()` in app.js) — verify the "329-1" tab appears; do NOT hand-code a tab.
- Coordinate map: native `(px,py)` on the 1362×644 image → `x = px·1366/1362`, `y = py·720/644`. `.ov` x/y are element CENTERS (`translate(-50%,-50%)`).
- Do NOT bump `ots_ov_pos_v3` — bumping is only for a CHANGED background and would discard saved drag positions on 321/322.
- Add `OV['screen-329-1'] = [...]` in overlays.js.

## 3. Bind map (authoritative — every `bind` must grep to a key emitted in the main.py packet builder before you use it)
| Node / asset | Packet path | Design value |
|---|---|---|
| 25-bar BL main (stream 901) | `STEAM_SYSTEM.SUPPLY_25BAR.P_bara` / `.TI_sat` | 25.00 bara / ≈224 °C |
| 329D005 HP saturator | `STEAM_SYSTEM.MP.P_bara` / `.TI_sat` / `.supply_pct` / `.m_supply_th` | 19.70 / 211.6 °C / 50.0 % / ≈76.7 t/h |
| 329D009 9-bar drum | `STEAM_SYSTEM.DRUM_9BAR.P_bara` / `.TI_sat` / `.admit_pct` / `.letdown_pct` / `.m_903_th` / `.m_ld_th` | 9.00 / ≈175 °C / 0 / 0 / 0 / 0 |
| 322D001A/B LP drums | `STEAM_SYSTEM.LP.P_bara` / `.TI_sat` / `.letdown_pct` / `.m_ld_th` / `.m_water_th` | 4.40 / 146.3 °C / 0 / 0 / 0 |
| HV-329601 HP atm vent | `STEAM_SYSTEM.HP_VENT.pct` / `.m_th` | 0 / 0 |
| 4-bar make-up (stream 963) | `STEAM_SYSTEM.LP_MAKEUP.PV_329207C` / `.m_963_th` / `.m_pic_th` | 0 / 0 / 0 |
| Stripper shell (cross-unit) | `STRIP_322E001.steam.TI_shell` / `.P_bara` / `.kgh` / `.duty_kW` | 211.6 / 19.7 / 75300 / 39400 |
| HPCC shell (cross-unit) | `HPCC_322E002.steam.*`, `HPCC_322E002.TT_329001` | TT_329001 = 146.3 |

**Auto valves (`t:'avalve'`):** PV-329204 → `STEAM_SYSTEM.MP.supply_pct`; PV-329205A → `DRUM_9BAR.admit_pct`; PV-329205B → `DRUM_9BAR.letdown_pct`; PV-329207C/HV-329602 → `LP_MAKEUP.PV_329207C`; HV-329601 → `HP_VENT.pct`.

**Operator actions (existing WS handlers, all `{op}` 0–100):** `steam_supply_set` (PV-329204), `steam_963_set`, `steam_hpvent_set` — wire HIC-style manual faceplates (roster pattern HIC-322602). `steam_letdown_set` exists but split-range PIC-329205 overwrites it every tick — manual only meaningful in MAN mode (§4).

## 4. Controller faceplates (PIC-329205, PIC-329207)
`CTRL_RE = /[A-Z]IC-3\d{2}/i` already opens the generic faceplate; the generic path sends `controller_set` (a no-op). Make these two loops real, following the faceplate roster pattern (ui_guidelines §12):
- **PIC-329205** (split-range, PV = `DRUM_9BAR.P_bara`): add backend handler `pic329205_set` {mode: AUTO|MAN, sp}. AUTO (default) = current split-range about SP 9.0 exactly as coded. MAN freezes the split-range writes so `steam_letdown_set`/admit manual values stick. SP re-targets the split.
- **PIC-329207** (LP master trio A/B/C, lumped PI, PV = `LP.P_bara`): add `pic329207_set` {mode: AUTO|MAN, sp}. AUTO (default) = current PI on SP 4.4 (keep the existing anti-windup clamp). MAN freezes `m_pic` at 0. Bumpless on mode return.
- Add mode/sp fields to `SteamState` with design defaults; publish them in the `STEAM_SYSTEM` telemetry; map both tags to the real handlers in the app.js modelled-loop map `T` (~L484); faceplate mode-tag colors per guideline (MAN red / AUTO green). One-line physics note per loop (e.g. "↑ P_9 above SP ⇒ PV-329205B vents 9→4 bar header").
- **Hard constraint:** with defaults untouched the numbers must be BIT-IDENTICAL to current behavior — gate §6 enforces this.

## 5. Unmodelled tags → WHITE FRAME (never fabricate binds)
Position every legible tag from the tagged PNG. Before white-framing, grep app.js/main.py for an existing bind (e.g. FIC-329409, TIC-329005 are real modelled loops). Expected unbound (white frame, ui_guidelines §4): drum level loops (LIC/LV-3296xx on all three vessels), oxygen-scavenger dosing 329U001-M01/M02, turbine 320MT02 internals, MASTER SP / MV-VOTING / START UP SWITCH chips, TRIP_21_2 / TRIP_20_1 (unless a trip latch exists in the packet), the 1948 KG/H hydrolyzer line (stream 911 → 328C003, downstream-only sink, out of scope), and any condensate/BFW flows with no packet key. Boundary blocks that have live screens get `t:'nav'` hotspots (322E001, 322E002 → `screen-322-1`); blocks without screens (320E006, 328C003, 324E003, GRANULATION, 372D001, 329D001, 320MT02) get tooltips only.

## 6. Verification gates (run all, in order; discard and fix on any failure)
1. Kill stale python processes, then `python backend/steam_system.py` → OVERALL PASS, design fixed point 25/19.7/9.0/4.4, `m_903 = m_ld9 = m_pic ≈ 0`.
2. `python backend/tests/coldstart_probe.py` → baseline bit-exact (design anchor drift = 0.00e+00).
3. Spot-check anchors in a short foreground run: `STRIP_322E001.steam.TI_shell = 211.6`, `HPCC_322E002.TT_329001 = 146.3`.
4. `python backend/tests/run_full_audit.py` → conservation/closure green (slow — run to completion).
5. UI conformance self-audit against ui_guidelines: `:root` tokens only, `--val-font` + tabular-nums for every numeric, px catalogue sizes, element dimensions table, no new fonts/colors.
6. Live check: launch backend, open UI → 329-1 tab present; all §3 binds show design values; white frames render; right-click trend works on a bound indicator; domino test: `steam_supply_set` PV-329204 → 0 % → P_MP collapses and TI_shell falls (stripper starves), restore 50 % → recovers 19.7.
7. Grep-audit: every `bind` string in `OV['screen-329-1']` resolves to an emitted packet key.

## 7. Commit (CLAUDE.md §3)
Stage ONLY: `frontend/index.html`, `frontend/overlays.js`, `frontend/app.js` (if touched), `frontend/img/screen-329-1.png`, `backend/main.py`, `backend/steam_system.py`, and the As-Built reference doc (update it with the new screen + PIC handlers per the Continuous Docs law). Commit `feat(329-1): image-backed steam-system DCS screen + PIC-329205/329207 faceplates`, push to origin. Leave all other dirty WIP unstaged.
