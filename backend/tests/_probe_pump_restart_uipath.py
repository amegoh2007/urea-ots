r"""_probe_pump_restart_uipath.py -- restart reachable from the ACTUAL UI controls only.

The frontend emits ONLY pump_toggle / xv_toggle -- there is NO trip_reset button.  This probe
uses exactly those UI commands (trigger_fault is the instructor arming, then a single pump_toggle
click) to prove the operator can restart a tripped pump without any trip_reset.
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

print(f"init: pumpB on={s.pumpB['on']} fault={s.pumpB['fault']} latch={s.trip_latched['21_10']}")

# 1. instructor arms mechanical fault -> 21_10 latches -> pump forced off
main.handle_cmd({"type": "trigger_fault", "id": "B", "value": True})
settle(20)
print(f"post-fault: on={s.pumpB['on']} fault={s.pumpB['fault']} "
      f"trip={s.trips['21_10']} latch={s.trip_latched['21_10']}  (expect on=False latch=True)")

# 2. operator clicks the pump button (the ONLY available control) -> must clear+restart
main.handle_cmd({"type": "pump_toggle", "id": "B"})
settle(600)  # 60 s -- plenty for any re-trip
print(f"post-click+60s: on={s.pumpB['on']} fault={s.pumpB['fault']} "
      f"trip={s.trips['21_10']} latch={s.trip_latched['21_10']}  (expect on=True, no re-trip)")

ok = s.pumpB["on"] and not s.trips["21_10"] and not s.trip_latched["21_10"]
print("RESULT:", "PASS -- restartable via UI pump button alone" if ok else "FAIL -- still blocked")

# 3. negative control: latch over a STILL-LIVE cause (21_2, tank empty) must STAY blocked
main.state = main.State()
s = main.state
for _ in range(50):
    s.tank_level_frac = 0.0      # PIN tank empty every tick -> 21_2 stays live
    main.step_sim(DT)
print(f"\nempty-tank: on_B={s.pumpB['on']} trip21_2={s.trips['21_2']} latch21_2={s.trip_latched['21_2']}")
s.tank_level_frac = 0.0
main.handle_cmd({"type": "pump_toggle", "id": "B"})   # try restart while cause live
for _ in range(5):
    s.tank_level_frac = 0.0
    main.step_sim(DT)
blocked = (not s.pumpB["on"]) and s.trip_latched["21_2"]
print(f"restart-attempt: on_B={s.pumpB['on']}  (expect False -- blocked, cause live)")
print("RESULT:", "PASS -- live cause still blocks restart" if blocked else "FAIL -- unsafe restart")
