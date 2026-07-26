# RESUME Task B — verify & commit steam_system.py

All context below is pre-verified. Do NOT re-explore, re-read, or re-derive it.

## STATE (trusted)
- `backend/steam_system.py` (280 L): complete 4-header model 25/19.7/9/4.4 bara; split-range PIC-329205; LP master PIC.
- `backend/main.py` (3305 L) wiring: L36 import; L1921 `tsat_steam(s.steam.P_MP)`→322E001 shell; L2011 g_dist-gated `tsat_steam(s.steam.P_LP)`→322E002; telemetry L2632–2649; steam blocks L3202/3250/3267.
- PASSED — do not re-run: `backend/probe_steam_integration.py` (design fixed point 19.7/9.0/4.4 bit-exact; design-neutral m_903=m_ld9=m_pic=0); `backend/tests/audit_p002_pumps.py`; `backend/tests/coldstart_probe.py` (140.700000→140.700000, |d|=0.00e+00, τ=3397); domino 329→322 live, g_dist=0 at design → 146.3 bit-exact.
- `plant_state.md` DOES NOT EXIST anywhere. Do not search for it. Checkout Protocol only if the audit exposes a missing upstream variable.

## DO (in order, nothing else)
1. Kill stale python (`taskkill /F /IM python.exe` on Windows; `pkill -f main.py` otherwise). Run the full conservation audit: `cd backend && python tests/run_full_audit.py`. If that is a scenario driver rather than the conservation gate, `head -30` it once, then use `tests/pillar4_audit.py`. Long run → launch backgrounded with output to a log; poll `tail -5` ~every 60 s.
2. Gate: mass/energy conservation at 100% design, zero steady-state drift. FAIL → `grep -n` the reported variable only, read ±20 lines, minimal fix, re-run the audit ONLY.
3. PASS → stage ONLY `backend/steam_system.py backend/main.py` (tree has unrelated dirty files — NEVER `git add -A`/`-u`). Commit: `feat(steam): 4-level header network (25/19.7/9/4.4 bara), split-range PIC-329205, 329→322 Tsat coupling — design-neutral, coldstart bit-exact`. Push origin.
4. Append a ≤40-line steam section (equations, state vars, coupling points) to `Urea OTS — As-Built Mathematical & System Architecture Reference.md`; second commit, push.

## TOKEN RULES (hard)
- NEVER open: `docs/urea-project-conversation.md` (69k lines), `Combined_*.md`, `Gemini*/`, `Gemini_*.md`, `library/`, `Urea Simulation/`, `New folder/`.
- No full-file reads of `main.py` — `grep -n` then ranged reads only. `steam_system.py` (280 L) may be read once if a fix requires it.
- No `ls`/`find` exploration; all paths above are verified.
- Output style: command → one result line → verdict. No context restatement, no interim summaries, no plan recaps.
- Stop after step 4. Do not start the next unit.
