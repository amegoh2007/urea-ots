r"""_probe_pump_restart.py -- HP-NH3 pump restart-after-mechanical-trip.

Scenario (pump B, on by default):
  1. instructor sets mechanical fault  -> trip 21_10 latches -> pump forced off
  2. operator trip_reset                -> latch clears AND fault cleared (cause resolved)
  3. operator pump_toggle (restart)     -> pump must come ON and STAY on (no re-trip)
Asserts the mechanical obstacle no longer blocks restart.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import main

DT = 0.1


def settle(n):
    for _ in range(n):
        main.step_sim(DT)


main.state = main.State()
s = main.state
s.tank_level_frac = s.tank_level_frac  # noqa

print(f"init: pumpB on={s.pumpB['on']} fault={s.pumpB['fault']} latch21_10={s.trip_latched['21_10']}")

# 1. arm mechanical fault
main.handle_cmd({"type": "trigger_fault", "id": "B", "value": True})
settle(20)
print(f"post-fault: on={s.pumpB['on']} fault={s.pumpB['fault']} "
      f"trip={s.trips['21_10']} latch={s.trip_latched['21_10']}  (expect on=False latch=True)")

# 2. try restart WHILE still latched -> must stay blocked
main.handle_cmd({"type": "pump_toggle", "id": "B"})
settle(5)
print(f"restart-while-latched: on={s.pumpB['on']}  (expect False, blocked)")

# 3. operator reset -> clears latch + fault
main.handle_cmd({"type": "trip_reset", "id": "21_10"})
print(f"post-reset: fault={s.pumpB['fault']} latch={s.trip_latched['21_10']}  (expect fault=False latch=False)")

# 4. restart -> must come ON and STAY on
main.handle_cmd({"type": "pump_toggle", "id": "B"})
settle(600)  # 60 s, plenty for any re-trip to fire
print(f"post-restart+60s: on={s.pumpB['on']} fault={s.pumpB['fault']} "
      f"trip={s.trips['21_10']} latch={s.trip_latched['21_10']}  (expect on=True, no re-trip)")

ok = s.pumpB["on"] and not s.trips["21_10"] and not s.trip_latched["21_10"]
print("\nRESULT:", "PASS -- pump restartable after cause resolved" if ok else "FAIL -- still blocked / re-tripped")
