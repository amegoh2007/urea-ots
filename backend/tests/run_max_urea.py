r"""run_max_urea.py -- EXTREME FORCING: probe the maximum reactor-effluent urea mass %.

Reference ceilings:
    ~35-37 %   industrial Stamicarbon equilibrium reality       (NOT encoded in the model)
    ~55.9 %    thermodynamic cap  (X_inf=0.9196 at T0)           (f_L,f_W <= 1)
    ~76.9 %    absolute stoichiometric limit                     (all CO2->urea, no excess dilution)

    X(L,W,T) = min( X_inf * [a(L-2)/(1+a(L-2))] * [1/(1+bW)] * exp[-k((T-Topt)^2-(T0-Topt)^2)], X_inf )
                          \____ f_L <=1 ___/   \__ f_W<=1 _/   \____ f_T parabola (Guard 1) ____/  Guard 2

Phase 4 kinetic rewrite: the old unbounded Arrhenius f_T was replaced by a renormalized parabolic
penalty centered on Topt(L) in [185,195] C (Guard 1, pinned f_T(T0)=1) plus a hard X<=X_inf re-clamp
(Guard 2).  Tier 3 now verifies over-temperature equilibrium REVERSAL: conversion peaks at Topt,
plateaus at the X_inf ceiling, then collapses as T climbs past ~200 C -- no hidden stoich wall.

    Tier 1  LIVE ENVELOPE        settle full loop, force N/C {5,7,10,20} (past UI clamp [2,5]).
    Tier 2  STRUCTURAL CAP       direct-drive react_322r001, T=183, L=1000, W=0.
    Tier 3  TEMPERATURE BREAK    hold (L=1000,W=0), sweep T 183->300 C; log X, urea%, closure.
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import main, reactor

MW  = main.MW_COMP


def urea_pct(ov):
    m = {k: ov.get(k, 0.0) * MW[k] for k in MW}
    tot = sum(m.values())
    return (100.0 * m["Urea"] / tot) if tot > 0 else float("nan")


def f_T(Tc, L):
    return reactor.f_T_parabola(Tc, L)                    # delegate to engine (no formula drift)


# ----- shared live-settle machinery (forced N/C re-pin + REACT_OVERFLOW urea-% spy + hpcc grab) -----
DT, SETTLE_TICK = 0.1, int(30.0 * 60.0 / 0.1)
_FORCED_NC, _TANK_PIN, _CAP, _HPCC = [None], [None], {}, [None]

_orig_hpcc = main.hpcc_322e002
def _forced_hpcc(*a, **k):
    out = _orig_hpcc(*a, **k)
    if _FORCED_NC[0] is not None:
        main.state.ratio_PV = _FORCED_NC[0]
    _HPCC[0] = out
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


def settle_live(nc):
    main.state = main.State()
    s = main.state
    s.ratio_SP = s.ratio_bal = s.ratio_PV = nc
    _FORCED_NC[0], _TANK_PIN[0] = nc, s.tank_level_frac
    pkt = None
    for _ in range(SETTLE_TICK):
        pkt = main.step_sim(DT)
        s.tank_level_frac = _TANK_PIN[0]
    _FORCED_NC[0] = _TANK_PIN[0] = None
    return pkt, s


# ============================== TIER 1 -- LIVE ENVELOPE ==============================
def tier1():
    print("=" * 96)
    print("  TIER 1 -- LIVE ENVELOPE  (force fresh-feed N/C past UI clamp [2,5]; settle 30 sim-min)")
    print("=" * 96)
    print(f"  {'N/C set':>8} | {'AT701':>6} | {'L_feed':>7} {'W_feed':>7} | {'X_conv%':>8} | "
          f"{'cf':>7} | {'Urea%':>7} | {'P bara':>7}")
    print("  " + "-" * 86)
    rows = []
    for nc in [5, 7, 10, 20]:
        pkt, s = settle_live(nc)
        r = pkt["REACT_322R001"]
        row = dict(nc=nc, at=r["AT_322701"], L=r["L_feed"], W=r["W_feed"], X=r["X_conv"],
                   cf=round(r["X_conv"]/100.0/reactor.X_DES_RAW, 4),
                   urea=round(_CAP.get("urea_pct", float("nan")), 2), P=round(s.p_syn_bara, 1))
        rows.append(row)
        print(f"  {row['nc']:>8} | {row['at']:>6} | {row['L']:>7} {row['W']:>7} | {row['X']:>8} | "
              f"{row['cf']:>7} | {row['urea']:>7} | {row['P']:>7}")
    best = max(rows, key=lambda r: r["urea"])
    print("  " + "-" * 86)
    print(f"  TIER 1 MAX urea = {best['urea']} %  at N/C={best['nc']}  (W stays loop-pinned ~0.40)")
    return best


# ===================== TIER 2 / 3 -- DIRECT-DRIVE react_322r001 =====================
def capture_design_inputs():
    """Settle at design N/C, capture a live hpcc feed + design CO2/HIC for direct-drive calls."""
    _, s = settle_live(round(main.RATIO_PV_DES, 4))
    return _HPCC[0], s.F_CO2_th, s.HIC_322605


def react_drive(hpcc, co2_th, hic, L, W, Tc):
    """Direct-drive react_322r001 with L/W overrides; patch the reactor bulk T for the f_T sweep."""
    old = main.REACT_OVERFLOW_T_C
    main.REACT_OVERFLOW_T_C = Tc                           # f_T sweep hook (react_couple reads this)
    try:
        r = main.react_322r001(hpcc, co2_th, hic, L_drive=L, W_drive=W)
    finally:
        main.REACT_OVERFLOW_T_C = old
    ov = r["overflow_kmolh"]
    return dict(L=r["L_feed"], W=r["W_feed"], Tc=Tc, X=r["X_conv"], cf=r["X_conv"]/reactor.X_DES_RAW,
                urea=urea_pct(ov), co2=ov.get("CO2", 0.0), nh3=ov.get("NH3", 0.0),
                mn=min(ov.values()), xi=r["xi_urea"], clo=r["closure_resid"])


def tier2(hpcc, co2_th, hic):
    print("\n" + "=" * 96)
    print("  TIER 2 -- STRUCTURAL CAP  (direct-drive react_322r001; T=183 C; L=1000, W=0)")
    print("=" * 96)
    print(f"  {'L (N/C)':>9} | {'W (H/C)':>8} | {'X_conv%':>8} | {'cf':>7} | {'Urea%':>7} | "
          f"{'CO2_ov':>8} | {'min comp':>9} | {'closure':>9}")
    print("  " + "-" * 88)
    best = None
    for (L, W) in [(3.0, reactor.W0_DES), (1000.0, 0.0)]:
        d = react_drive(hpcc, co2_th, hic, L, W, 183.0)
        print(f"  {L:>9g} | {W:>8.4f} | {d['X']*100:>8.2f} | {d['cf']:>7.4f} | {d['urea']:>7.2f} | "
              f"{d['co2']:>8.1f} | {d['mn']:>9.2f} | {d['clo']:>9.4f}")
        if best is None or d["urea"] > best["urea"]:
            best = d
    print("  " + "-" * 88)
    print(f"  TIER 2 MAX urea = {best['urea']:.2f} %  at L={best['L']:g}, W={best['W']:g}  "
          f"(X={best['X']*100:.2f}% vs X_inf={reactor.X_INF*100:.2f}%)")
    return best


def tier3(hpcc, co2_th, hic):
    print("\n" + "=" * 96)
    print("  TIER 3 -- TEMPERATURE REVERSAL  (corner L=1000, W=0; sweep T 183->300 C; guarded parabola)")
    print("=" * 96)
    print(f"  {'T (C)':>6} | {'f_T':>7} | {'X_conv%':>9} | {'cf':>7} | {'xi_urea':>9} | {'Urea%':>7} | "
          f"{'CO2_ov':>8} | {'min comp':>9} | {'closure':>9}")
    print("  " + "-" * 96)
    best = None
    for Tc in [183.0, 200.0, 210.0, 225.0, 250.0, 275.0, 300.0]:
        d = react_drive(hpcc, co2_th, hic, 1000.0, 0.0, Tc)
        fT = f_T(Tc, 1000.0)
        if d["X"] >= reactor.X_INF - 1e-6:
            flag = "  <-- Guard 2 clamp @X_inf"
        elif fT < 1.0:
            flag = "  <-- reversal (f_T<1)"
        else:
            flag = ""
        print(f"  {Tc:>6g} | {fT:>7.4f} | {d['X']*100:>9.2f} | {d['cf']:>7.4f} | {d['xi']:>9.1f} | "
              f"{d['urea']:>7.2f} | {d['co2']:>8.1f} | {d['mn']:>9.2f} | {d['clo']:>9.4f}{flag}")
        if best is None or d["urea"] > best["urea"]:
            best = d
    print("  " + "-" * 96)
    print(f"  TIER 3 MAX urea = {best['urea']:.2f} %  (X up to {best['X']*100:.1f}%, cf up to {best['cf']:.3f})")
    return best


if __name__ == "__main__":
    b1 = tier1()
    hpcc, co2_th, hic = capture_design_inputs()
    b2 = tier2(hpcc, co2_th, hic)
    b3 = tier3(hpcc, co2_th, hic)
    print("\n" + "=" * 96)
    print("  SUMMARY -- ASCENDING CAPS")
    print("=" * 96)
    print(f"   industrial equilibrium reality ........ ~35-37 %  (NOT encoded)")
    print(f"   Tier 1 live envelope (water floor) .... {b1['urea']:.2f} %  (N/C={b1['nc']}, W~0.40)")
    print(f"   thermodynamic cap X_inf ............... ~55.9 %")
    print(f"   Tier 2 structural f_L,f_W ............. {b2['urea']:.2f} %  (X->X_inf=91.96%)")
    print(f"   Tier 3 parabola peak -> reversal ...... {b3['urea']:.2f} %  (peak X {b3['X']*100:.1f}%, then falls)")
    print(f"   absolute stoichiometric limit ......... ~76.9 %")
    print("=" * 96)
