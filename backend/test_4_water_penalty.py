"""TEST 4 - Water penalty on reactor equilibrium (LeChatelier).
Action : +10% H2O mass frac in 322E003 carbamate recycle (EJ_CARB_FRAC['H2O']) -> ejector -> HPCC.
Expect : reactor H/C rises; urea conversion X drops (water shifts dehydration back);
         stripper overhead vapour load shifts.
Bridge : reactor X = f(N/C, H/C, T, tau)  with water-penalty term.
NOTE   : reactor kinetic/equilibrium coupling is COMMITTED FUTURE SCOPE (spec 2026-06-03).
"""
import _systest as H


def xi_urea(pkt):
    """Conversion-coupled urea-formation extent, now EMITTED to the packet by reactor.react_couple
    (main.py REACT_322R001['xi_urea']) = REACT_XI_UREA_DES*co2_scale * X(L,W,T)/X(L0,W0,T0).
    The Modified Inoue-Kanai factor carries the H/C water penalty (was pinned/flat before)."""
    return H.find(pkt, "xi_urea")


def main_test():
    H.reset()
    base = H.run(40)
    hc0  = H.find(base, "W_feed")          # reactor-feed H/C (H2O/CO2 molar) — the live coupling driver
    x0   = xi_urea(base)                   # urea formation extent (engine value)
    top0 = H.find(base, "top_th")          # stripper overhead vapour (t/h)

    saved = dict(H.main.EJ_CARB_FRAC)
    try:
        H.main.EJ_CARB_FRAC["H2O"] *= 1.10   # +10% H2O mass frac in 322E003 carbamate recycle -> ejector -> HPCC
        new  = H.run(120)
        hc1  = H.find(new, "W_feed")
        x1   = xi_urea(new)
        top1 = H.find(new, "top_th")
    finally:
        H.main.EJ_CARB_FRAC.clear()
        H.main.EJ_CARB_FRAC.update(saved)   # restore module constant

    print("TEST 4 - WATER PENALTY (+10% H2O in carbamate recycle)")
    print(f"  {'TAG':<26} {'BEFORE':>11} {'AFTER':>11}      d%   STATE")
    dhc  = H.row("Reactor feed H/C (W_feed)", hc0, hc1)
    dx   = H.row("Conversion xi_urea (kmol/h)", x0, x1)
    dtop = H.row("Stripper overhead (t/h)", top0, top1)

    p = 0
    p += H.check("H/C rises with recycle water", dhc > H.FLAT,
                 "EJ_CARB_FRAC H2O -> ejector disch -> HPCC feed -> W_feed (H2O/CO2 molar). Should rise.")
    p += H.check("conversion X drops with H/C (water penalty)", dx < -H.FLAT,
                 "xi_urea conversion-coupled via reactor.py Inoue-Kanai f_W=1/(1+b*W); if flat, check W_feed propagation.")
    p += H.check("stripper overhead load rises (more unconverted)", dtop > H.FLAT,
                 "overflow now carries +CO2/+NH3 when conversion drops (atom-conserving ripple); top vapour should rise.")
    H.verdict(p, 3)


if __name__ == "__main__":
    main_test()
