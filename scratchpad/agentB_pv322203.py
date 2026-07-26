"""Agent B: PV-322203 end-to-end. Is the opening visible in telemetry, and does opening it
   DIVERT CO2 to the vent rather than pushing it into the HP synthesis loop?"""
import os, sys
B = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
os.chdir(B); sys.path.insert(0, B)
import main
s = main.state
for _ in range(50): main.step_sim(0.1)

print(f"{'HIC-322203':>10} {'PV_322203':>10} {'PIC pv barA':>12} {'raw t/h':>9} {'feed t/h':>9} {'vent t/h':>9} {'sum':>9} {'Load %':>8}")
for hic in [0, 5, 10, 14, 20, 40, 70, 100]:
    main.handle_cmd({"type": "hic2_set", "value": float(hic)})
    for _ in range(600): pkt = main.step_sim(0.1)   # 60 s settle
    c = pkt["CO2_FEED"]
    print(f"{c['HIC_322203']:>10.1f} {c['PV_322203']:>10.1f} {c['PIC_322203']:>12.1f} "
          f"{c['raw_th']:>9.2f} {c['FY_322403']:>9.2f} {c['vent_th']:>9.2f} "
          f"{c['FY_322403']+c['vent_th']:>9.2f} {c['Load']:>8.1f}")
print()
print("PIC-322203 mode/sp/op published:", pkt['CO2_FEED']['PIC_mode'], pkt['CO2_FEED']['PIC_sp'], pkt['CO2_FEED']['PIC_op'])
print("SP - deliverable ceiling =", pkt['CO2_FEED']['PIC_sp'] - (main.SYN_P_MAX_BARA + (main.CO2_P_DES_BARA - main.SYN_P_DES_BARA)), "bar")
