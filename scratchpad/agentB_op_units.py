"""Agent B: the generic faceplate's OP field is hard-labelled 'Output (%)' with min=0 max=100.
   Which loops have an OP that is NOT a 0-100 percent?  And what does the operator actually get
   when he types the maximum the HMI will let him enter (100) into such a loop in MAN?"""
import os, sys
BACKEND = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state
main.step_sim(0.1)

print(f"{'LOOP':<14}{'op_lo':>10}{'op_hi':>12}   HMI can enter 0..100 -> % of real span")
odd = []
for cid in sorted(main.R323_CTRL_MODES):
    c = getattr(s, cid, None)
    if not isinstance(c, dict) or "op_hi" not in c: continue
    lo, hi = c["op_lo"], c["op_hi"]
    if abs(lo) > 1e-9 or abs(hi - 100.0) > 1e-9:
        odd.append((cid, lo, hi))
        print(f"{cid:<14}{lo:>10.3f}{hi:>12.3f}   100 -> {100.0/hi*100:6.1f} % of span")
print()

# Live demonstration on the TD-004 master
tic = s.TIC_328008; fic = s.FIC_328404
print("TIC-328008 (TD-004 master of FIC-328404): op span 0..%.0f kg/h, faceplate says 'Output (%%)' max=100" % tic["op_hi"])
for _ in range(50): main.step_sim(0.1)
print(f"  design      : TIC op = {tic['op']:8.1f} kg/h   FV-328404 = {fic['op']:6.2f} %   reflux SP = {fic['sp']:.4f} m3/h")
main.handle_cmd({"type": "r323_ctrl_set", "id": "TIC-328008", "mode": "MAN", "op": 100.0})
for _ in range(3000): main.step_sim(0.1)   # 300 s
print(f"  after MAN 100 (operator meant '100 %'): TIC op = {tic['op']:8.1f} kg/h  FV-328404 = {fic['op']:6.2f} %  reflux SP = {fic['sp']:.4f} m3/h")
pkt = main.step_sim(0.1)
d = pkt["DESORB_328"]["D001"]
print("  packet keys published for TIC_328008:", sorted(d["TIC_328008"].keys()))
print("  packet keys published for FIC_328404:", sorted(d["FIC_328404"].keys()))
