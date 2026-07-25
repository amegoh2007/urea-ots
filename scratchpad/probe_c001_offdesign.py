"""322C001 off-design: open HV-322604 -> more off-gas -> vent NH3 slip must rise absolutely."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa: E402
DT = 0.25
main.state = main.State(); s = main.state
def run(sec):
    for _ in range(int(sec / DT)):
        main.step_sim(DT)
run(900.0)
c = main.step_sim(DT)["ABSORB_328"]["C001"]
print("design  : gcb=%.3ft/h  abs=%.4ft/h  vent=%.3ft/h  vent_nh3=%.1fkg/h (%.2f%%)  co2=%.2f%%" % (
    c["gcb_th"], c["abs_th"], c["vent_th"], c["vent_nh3_kgh"], c["vent_nh3_pct"], c["vent_co2_pct"]))

s.HIC_322604 = 60.0     # open the inert-purge valve wider (equal-% trim -> ~+58% flow)
run(900.0)
c2 = main.step_sim(DT)["ABSORB_328"]["C001"]
print("HV604=60: gcb=%.3ft/h  abs=%.4ft/h  vent=%.3ft/h  vent_nh3=%.1fkg/h (%.2f%%)  co2=%.2f%%  [%s]" % (
    c2["gcb_th"], c2["abs_th"], c2["vent_th"], c2["vent_nh3_kgh"], c2["vent_nh3_pct"], c2["vent_co2_pct"],
    "SLIP UP OK" if c2["vent_nh3_kgh"] > c["vent_nh3_kgh"] else "FAIL"))

s.HIC_322604 = 40.0     # throttle it -> less off-gas -> less slip
run(900.0)
c3 = main.step_sim(DT)["ABSORB_328"]["C001"]
print("HV604=40: gcb=%.3ft/h  abs=%.4ft/h  vent=%.3ft/h  vent_nh3=%.1fkg/h (%.2f%%)  co2=%.2f%%  [%s]" % (
    c3["gcb_th"], c3["abs_th"], c3["vent_th"], c3["vent_nh3_kgh"], c3["vent_nh3_pct"], c3["vent_co2_pct"],
    "SLIP DOWN OK" if c3["vent_nh3_kgh"] < c["vent_nh3_kgh"] else "FAIL"))
print("TT hold:", c["TT_322015"], c2["TT_322015"], c3["TT_322015"])
