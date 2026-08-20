r"""_repro_pump_cas_nc.py -- reproduce: pump on CAS, enter N/C setpoint 2.0 -> reverts to 0.

Drives the two candidate operator flows against a settled State and prints ground truth
(controller mode/bias/sp + telemetry ratio.SP / controllers[SIC].bias) so we can SEE which
field the '0' originates from before touching any code.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import main

DT = 0.1
SETTLE = 1500


def settle():
    main.state = main.State()
    s = main.state
    pin = s.tank_level_frac
    for _ in range(SETTLE):
        main.step_sim(DT)
        s.tank_level_frac = pin
    return s, pin


def step_n(s, pin, n):
    pkt = None
    for _ in range(n):
        pkt = main.step_sim(DT)
        s.tank_level_frac = pin
    return pkt


def show(tag, s, pkt):
    c = s.controllers[tag]
    tc = pkt["controllers"][tag]
    print(f"    {tag}: mode={c.mode:<4} bias={c.bias:+.3f} sp={c.sp:7.3f} mv={c.mv:7.3f}"
          f"   pkt.bias={tc['bias']:+.3f} pkt.sp={tc['sp']:7.3f}")
    print(f"    ratio: SP={pkt['ratio']['SP']:.3f}  PV={pkt['ratio']['PV']:.3f}"
          f"  NC_A={pkt['ratio']['NC_A']:.3f}  NC_B={pkt['ratio']['NC_B']:.3f}")


print("=" * 78)
print("  FLOW A -- PUMP FACEPLATE (REST):  pump A ON -> SIC_321950 CAS -> set_bias 2.0")
print("=" * 78)
s, pin = settle()
main.handle_cmd({"type": "pump_toggle", "id": "A"})   # ensure pump A running
step_n(s, pin, 50)
c = s.controllers["SIC_321950"]
c.set_mode("CAS")
print(f"  after set_mode CAS:  bias={c.bias:+.3f}  mode={c.mode}")
c.set_bias(2.0)                                        # operator enters '2.0' in N/C bias field
print(f"  after set_bias 2.0:  bias={c.bias:+.3f}")
pkt = step_n(s, pin, 30)
print("  +3.0 s:")
show("SIC_321950", s, pkt)

print()
print("=" * 78)
print("  FLOW A' -- PUMP A *OFF* (default):  SIC_321950 CAS -> set_bias 2.0")
print("=" * 78)
s, pin = settle()                                      # pump A off by default
c = s.controllers["SIC_321950"]
c.set_mode("CAS")
print(f"  after set_mode CAS:  bias={c.bias:+.3f}  mode={c.mode}  pv(open_act)={s.pumpA['open_act']:.3f}")
c.set_bias(2.0)
print(f"  after set_bias 2.0:  bias={c.bias:+.3f}")
pkt = step_n(s, pin, 30)
print("  +3.0 s:")
show("SIC_321950", s, pkt)

print()
print("=" * 78)
print("  FLOW B -- RATIO PANEL:  ratio_set sp=2.0  (the 'N/C setpoint' master)")
print("=" * 78)
s, pin = settle()
main.handle_cmd({"type": "ratio_set", "sp": 2.0})
print(f"  after ratio_set 2.0:  ratio_SP={s.ratio_SP:.3f}  ratio_mode={getattr(s,'ratio_mode','n/a')}")
pkt = step_n(s, pin, 30)
print(f"  +3.0 s:  ratio_SP={s.ratio_SP:.3f}  pkt.ratio.SP={pkt['ratio']['SP']:.3f}")
