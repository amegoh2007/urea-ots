r"""run_nc_max_urea.py -- PRONG B: live-loop reachable MAX reactor-overflow urea content.

Sweeps the fresh-feed N/C setpoint from design (RATIO_PV_DES) up THROUGH the operator
clamp ceiling (ratio_SP clamp = [2.0, 5.0]), settles the full HP-synthesis loop 30 sim-min
per point, and captures the settled REACT_OVERFLOW urea mass % together with the LIVE
reactor-feed L (N/C) / W (H/C) the loop actually realizes and the per-pass conversion X.

Goal: the realistically reachable urea content (operator can only set N/C; W=H/C is
loop-emergent), to reconcile against the mechanism-sweep absolute ceiling (55.90 % at
L->inf, W->0).  Reuses the run_nc_sweep monkeypatch machinery (forced N/C + make_stream spy).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import main, reactor

DT, SETTLE_MIN = 0.1, 30.0
SETTLE_TICK = int(SETTLE_MIN * 60.0 / DT)
# design + up through the operator clamp ceiling (ratio_SP clamp hi = 5.0)
TARGETS = [round(main.RATIO_PV_DES, 4), 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]

_FORCED_NC = [None]
_TANK_PIN  = [None]
_CAP       = {}

_orig_hpcc = main.hpcc_322e002
def _forced_hpcc(*a, **k):
    out = _orig_hpcc(*a, **k)
    if _FORCED_NC[0] is not None:
        main.state.ratio_PV = _FORCED_NC[0]
    return out
main.hpcc_322e002 = _forced_hpcc

_orig_make_stream = main.make_stream
def _spy_make_stream(*a, **k):
    out = _orig_make_stream(*a, **k)
    src = a[4] if len(a) > 4 else k.get("src")
    dst = a[5] if len(a) > 5 else k.get("dst")
    if src == "322R001" and dst == "322E001":
        _CAP["urea_pct"] = out["mass_pct"].get("Urea", float("nan"))
    return out
main.make_stream = _spy_make_stream


def settle_one(nc):
    main.state = main.State()
    s = main.state
    s.ratio_SP = s.ratio_bal = s.ratio_PV = nc
    _FORCED_NC[0] = nc
    _TANK_PIN[0]  = s.tank_level_frac
    pkt = None
    for _ in range(SETTLE_TICK):
        pkt = main.step_sim(DT)
        s.tank_level_frac = _TANK_PIN[0]
    _FORCED_NC[0] = None
    _TANK_PIN[0]  = None
    return pkt, s


print("=" * 96)
print("  PRONG B -- LIVE-LOOP REACHABLE MAX UREA CONTENT  (force fresh-feed N/C design->clamp 5.0)")
print(f"  RATIO_PV_DES={main.RATIO_PV_DES:.4f}  REACT_NC_LOOP_GAIN={main.REACT_NC_LOOP_GAIN}  "
      f"L0={reactor.L0_DES:.4f}  W0={reactor.W0_DES:.4f}  X_DES_RAW={reactor.X_DES_RAW:.6f}")
print("=" * 96)
hdr = (f"  {'N/C set':>8} | {'AT701':>6} | {'L_feed':>7} {'W_feed':>7} | {'X_conv%':>8} | "
       f"{'cf':>7} | {'Urea%':>7} | {'P bar a':>8} | {'TT011':>6}")
print(hdr); print("  " + "-" * 86)
rows = []
for nc in TARGETS:
    pkt, s = settle_one(nc)
    react = pkt["REACT_322R001"]
    r = dict(nc=nc, at=react["AT_322701"], L=react["L_feed"], W=react["W_feed"],
             X=react["X_conv"], cf=round(react["X_conv"]/100.0/reactor.X_DES_RAW, 4),
             urea=round(_CAP.get("urea_pct", float("nan")), 2),
             P=round(s.p_syn_bara, 1), tt011=pkt["SCRUB_322E003"]["TT_322011"])
    rows.append(r)
    print(f"  {r['nc']:>8} | {r['at']:>6} | {r['L']:>7} {r['W']:>7} | {r['X']:>8} | "
          f"{r['cf']:>7} | {r['urea']:>7} | {r['P']:>8} | {r['tt011']:>6}")

best = max(rows, key=lambda r: r["urea"])
print("  " + "-" * 86)
print(f"  LIVE-REACHABLE MAX urea = {best['urea']} %  at N/C set={best['nc']} "
      f"(L={best['L']}, W={best['W']}, X={best['X']}%)")
print(f"  mechanism ceiling (L->inf, W->0) = 55.90 %  (X->X_inf=91.96%)")
print("=" * 96)
