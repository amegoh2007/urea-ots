"""Verification: CO2-flow sweep + mass balance + sub-cooling + discharge temp.
Drives step_sim directly (no server). Both pumps ON, both SIC in CAS so the
ratio block (NH3/CO2) sets pump speed."""
import main

s = main.state
s.pumpA["on"] = True
s.pumpB["on"] = True
main.handle_cmd({"type": "controller_set", "id": "SIC_321950", "mode": "CAS"})
main.handle_cmd({"type": "controller_set", "id": "SIC_321951", "mode": "CAS"})
main.handle_cmd({"type": "ratio_set", "sp": 1.928})   # design molar N/C (= 0.746 mass)


def settle(co2, secs=60.0):
    main.handle_cmd({"type": "co2_set", "value": co2})
    pkt = None
    for _ in range(int(secs / 0.1)):
        pkt = main.step_sim(0.1)
    return pkt


print("CO2-FLOW SWEEP  (ratio_SP = 1.928, both pumps CAS)")
print(f"{'CO2':>5} {'NH3dem':>7} {'spdA':>6} {'spdB':>6} {'FT-321401':>9} "
      f"{'ratioPV':>7} {'PT201':>6} {'PY201':>6} {'PDY203':>6} {'TI020':>6}")
prev_ft = -1.0
ok = True
for co2 in [16.0, 22.0, 28.0, 34.0]:
    p = settle(co2)
    dem = 0.746 * co2
    print(f"{co2:>5.1f} {dem:>7.2f} {p['pumpA']['speed']:>6.1f} {p['pumpB']['speed']:>6.1f} "
          f"{p['FI_321401']:>9.2f} {p['ratio']['PV']:>7.3f} {p['PI_321201']:>6.1f} "
          f"{p['PY_321201']:>6.2f} {p['PDY_321203']:>6.2f} {p['TI_321020']:>6.1f}")
    if p['FI_321401'] <= prev_ft:
        ok = False
    prev_ft = p['FI_321401']
    if p['PDY_321203'] <= 0:
        ok = False

print()
print("MASS-BALANCE CLOSURE (sustainable point: NH3 demand <= BL feed):")
s.tank_level_frac = 0.65                       # refill after sweep drained tank
co2_ss = round(s.F_in_BL_th / 0.746, 1)        # demand ~= BL feed -> steady level
p = settle(co2_ss, 180.0)
QA = main.pump_flow_m3h(p['pumpA']['speed'])
QB = main.pump_flow_m3h(p['pumpB']['speed'])
F_from_speed = (QA + QB) * main.NH3_RHO / 1000.0
print(f"  CO2={co2_ss:.1f}  NH3 demand={0.746*co2_ss:.2f} t/h   BL feed={s.F_in_BL_th:.2f} t/h")
print(f"  Q_A={QA:.2f} m3/h  Q_B={QB:.2f} m3/h  -> rho*Q = {F_from_speed:.2f} t/h")
print(f"  FT-321401 packet = {p['FI_321401']:.2f} t/h   tank level = {p['LI_321501']:.1f} %")
print(f"  packet/speed closure |FT - rho*Q| = {abs(p['FI_321401']-F_from_speed):.4f} t/h")
print(f"  demand tracking   |FT - 0.746*CO2| = {abs(p['FI_321401']-0.746*co2_ss):.3f} t/h")

print()
print("FLOW GATING (open_act decay tau~2s -> allow ~15s to settle):")
s.tank_level_frac = 0.65
s.pumpA["on"] = False
s.pumpB["on"] = False
for _ in range(150):
    g = main.step_sim(0.1)
print(f"  both pumps OFF  -> FT-321401 = {g['FI_321401']:.3f} t/h")
s.pumpA["on"] = True
s.pumpB["on"] = True
for _ in range(150):
    g = main.step_sim(0.1)
main.handle_cmd({"type": "xv_toggle", "id": "321901"})   # close suction
for _ in range(200):
    g = main.step_sim(0.1)
print(f"  XV-321901 CLOSED -> FT-321401 = {g['FI_321401']:.3f} t/h")
main.handle_cmd({"type": "xv_toggle", "id": "321901"})   # restore

print()
print("RESULT:", "PASS" if ok else "CHECK")
