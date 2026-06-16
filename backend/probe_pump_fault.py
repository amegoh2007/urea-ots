"""probe_pump_fault.py  --  TEMPORARY verification of the lube-oil -> generic-fault abstraction.

Proves the Batch-4 refinement:
  1. trigger_fault command sets pumpB["fault"] = True (generic mechanical-fault flag).
  2. Trip 21_10 FIRES (live condition: pumpB on AND faulted).
  3. Trip 21_10 LATCHES (trip_latched["21_10"] stays True even after the live trip is cleared).
  4. Pump B is SHUT DOWN (pumpB["on"] -> False) by the latch action.
  5. Pump A is UNAFFECTED: pumpA["on"] unchanged, 21_8 neither fires nor latches.
"""
import sys
import main

sys.stdout.reconfigure(encoding="utf-8")   # Windows console cp1252

DT = 0.1

print("=" * 64)
print("  PUMP-FAULT TRIP PROBE  (lube-oil -> generic equipment fault)")
print("=" * 64)

main.state = main.State()
s = main.state

# baseline: design seed has pump A = spare(off), pump B = running(on, 86.2%)
a_on0, b_on0 = s.pumpA["on"], s.pumpB["on"]
print(f"\n  seed:  pumpA on={a_on0} fault={s.pumpA['fault']}   "
      f"pumpB on={b_on0} fault={s.pumpB['fault']}")
print(f"         trips 21_8={s.trips['21_8']} 21_10={s.trips['21_10']}   "
      f"latched 21_8={s.trip_latched['21_8']} 21_10={s.trip_latched['21_10']}")
assert b_on0 is True,  "PRECOND FAIL: pump B must be running at seed for this probe"

# settle a few ticks clean (no fault) -> nothing should trip
for _ in range(20):
    main.step_sim(DT)
assert not s.trip_latched["21_10"], "FAIL: 21_10 latched with NO fault present"
assert not s.trip_latched["21_8"],  "FAIL: 21_8 latched with NO fault present"
print("\n  [clean 2 s] no fault -> no latch.  OK")

# ---- inject pump-B mechanical fault via the instructor command hook ----
main.handle_cmd({"type": "trigger_fault", "id": "B", "value": True})
print(f"\n  COMMAND: trigger_fault id=B value=True  -> pumpB['fault']={s.pumpB['fault']}")
assert s.pumpB["fault"] is True, "FAIL: trigger_fault did not set pumpB['fault']"

# one tick: trip logic evaluates live condition (B on AND faulted) -> 21_10 fires + latches + B off
main.step_sim(DT)
print(f"\n  [tick after fault]  trips 21_10={s.trips['21_10']}   "
      f"latched 21_10={s.trip_latched['21_10']}   pumpB on={s.pumpB['on']}")
assert s.trip_latched["21_10"], "FAIL: trip 21_10 did not latch on pumpB fault"
assert s.pumpB["on"] is False,  "FAIL: latch 21_10 did not shut down pump B"

# pump A must be wholly unaffected by pump-B's fault
print(f"  [tick after fault]  pumpA on={s.pumpA['on']} fault={s.pumpA['fault']}   "
      f"trips 21_8={s.trips['21_8']}  latched 21_8={s.trip_latched['21_8']}")
assert s.pumpA["on"] == a_on0,        f"FAIL: pump A state changed ({a_on0} -> {s.pumpA['on']})"
assert s.pumpA["fault"] is False,     "FAIL: pump A spuriously faulted"
assert not s.trips["21_8"],           "FAIL: 21_8 fired without a pump-A fault"
assert not s.trip_latched["21_8"],    "FAIL: 21_8 latched without a pump-A fault"

# latch persistence: even after clearing the fault, the latch holds until trip_reset
main.handle_cmd({"type": "trigger_fault", "id": "B", "value": False})
main.step_sim(DT)
print(f"\n  COMMAND: trigger_fault id=B value=False  -> live 21_10={s.trips['21_10']}  "
      f"latched 21_10={s.trip_latched['21_10']} (must stay True)")
assert s.trip_latched["21_10"], "FAIL: latch cleared itself when fault removed (should need trip_reset)"
assert s.pumpB["on"] is False,  "FAIL: pump B restarted itself after fault cleared"

# trip_reset now succeeds (live condition recovered: fault False, pump already off)
main.handle_cmd({"type": "trip_reset", "id": "21_10"})
print(f"  COMMAND: trip_reset id=21_10  -> latched 21_10={s.trip_latched['21_10']} (now clearable)")
assert not s.trip_latched["21_10"], "FAIL: trip_reset did not clear 21_10 after fault recovered"

# also confirm generic UI form {"type":"set","id":"pumpA_fault","value":true} routes correctly
main.handle_cmd({"type": "set", "id": "pumpA_fault", "value": True})
print(f"\n  COMMAND: set id=pumpA_fault value=True  -> pumpA['fault']={s.pumpA['fault']}")
assert s.pumpA["fault"] is True, "FAIL: generic set/pumpA_fault did not route to pumpA['fault']"
main.handle_cmd({"type": "set", "id": "pumpA_fault", "value": False})   # restore

print("\n" + "=" * 64)
print("  PASS: pumpB fault -> 21_10 fired, latched, shut down pump B.")
print("        pump A unaffected (21_8 dormant); latch held until trip_reset.")
print("        Both command contracts (trigger_fault + set/*_fault) route correctly.")
print("=" * 64)
