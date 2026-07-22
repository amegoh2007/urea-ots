"""Measure FIC-328404's full-stroke PV authority so TIC-328008's SP span can be set to the
reachable band (CP-4), and prove the velocity-form loop is windup-free (recovers from a rail).

TIC-328008 PV = inferential offgas H2O mol% at the 328C002 top. Its master output strokes
FV-328404 (the 775 reflux). We want the mol% the plant reaches at FV-328404 = 0 % and = 100 %.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa

s = main.state if hasattr(main, "state") else main.STATE
tic = s.TIC_328008
fic = s.FIC_328404

def settle(n):
    for _ in range(n): main.step_sim(0.1)

def pv_now():
    return main.step_sim(0.1)["DESORB_328"]["D001"]["TIC_328008"]["pv"]

settle(600)
print(f"design: TIC-328008 pv={tic['pv']:.3f} mol%  FV-328404 op={fic['op']:.1f}%")

# Drive FV-328404 to each rail in MAN and read the settled offgas mol%
fic["mode"] = "MAN"
fic["op"] = 100.0
settle(4000)
pv_hi = tic["pv"]
fic["op"] = 0.0
settle(4000)
pv_lo = tic["pv"]
print(f"FV-328404 @100%%  -> offgas H2O = {pv_hi:.3f} mol%")
print(f"FV-328404 @  0%%  -> offgas H2O = {pv_lo:.3f} mol%")
lo, hi = sorted((pv_lo, pv_hi))
print(f"REACHABLE PV BAND: {lo:.3f} .. {hi:.3f} mol%  (authority {hi-lo:.3f})")
print(f"  suggest sp_lo={lo+0.05:.2f}  sp_hi={hi-0.05:.2f}  (small guard inside the rails)")

# --- windup test: rail the loop on an UNREACHABLE sp, then give a reachable one; does op recover?
print("\n=== velocity-form windup test ===")
fic["mode"] = "CAS"
tic["mode"] = "AUTO"
tic["sp"] = hi + 5.0                       # deliberately unreachable (above full authority)
settle(3000)
print(f"unreachable sp={tic['sp']:.2f}: FV-328404 op railed to {fic['op']:.1f}%")
tic["sp"] = (lo + hi) / 2.0                # now a reachable mid-band sp
recovered_at = None
for k in range(1, 6001):
    main.step_sim(0.1)
    if recovered_at is None and 1.0 < fic["op"] < 99.0:
        recovered_at = k * 0.1
print(f"reachable sp={tic['sp']:.2f}: op left the rail after {recovered_at}s -> settled {fic['op']:.1f}%")
print("VERDICT:", "WINDUP-FREE (recovers)" if recovered_at and recovered_at < 60 else "WINDS UP (stuck)")
