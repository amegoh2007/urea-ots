"""TEST 1 - N/C ratio shift (compositional coupling).
Action : +5% HP NH3 motive (pump B speed), CO2 feed constant -> N/C rises.
Expect : PT-329201 slightly decreases or stabilizes (excess NH3 lowers melt vapour P);
         stripper eta_T decreases (more inert NH3 dilutes CO2 driving force).
Bridge : HPCC bubble-point P=f(N/C)  +  stripper eta_T=f(N/C).
"""
import _systest as H


def main_test():
    H.reset()
    base = H.run(40)                      # settle design steady state
    fnc0 = base["ratio"]["PV"]            # feed N/C (manipulated var)
    rnc0 = H.find(base, "AT_322701")      # reactor N/C (requested tag)
    lf0  = H.find(base, "L_feed")         # reactor-feed N/C (NH3/CO2 molar) — Inoue-Kanai f_L input
    xc0  = H.find(base, "X_conv")         # per-pass CO2->urea conversion (%) — reactor.py bridge
    pt0  = H.find(base, "PI_329201")     # PT-329201 nested in packet -> deep-get
    et0  = H.eta_T(base)

    H.main.state.SIC_321951.mv *= 1.05     # +5% NH3 motive (Controller MV; SIC is MAN at design -> held)
    new  = H.run(120)
    fnc1 = new["ratio"]["PV"]
    rnc1 = H.find(new, "AT_322701")
    lf1  = H.find(new, "L_feed")
    xc1  = H.find(new, "X_conv")
    pt1  = H.find(new, "PI_329201")
    et1  = H.eta_T(new)

    print("TEST 1 - N/C SHIFT (+5% NH3 motive, CO2 const)")
    print(f"  {'TAG':<26} {'BEFORE':>11} {'AFTER':>11}      d%   STATE")
    dfn = H.row("feed N/C (ratio.PV)", fnc0, fnc1)
    dlf = H.row("Reactor feed N/C (L_feed)", lf0, lf1)
    dxc = H.row("Conversion X_conv (%)", xc0, xc1)
    drn = H.row("Reactor N/C (AT-322701)", rnc0, rnc1)
    dpt = H.row("PT-329201 (bar a)", pt0, pt1)
    det = H.row("stripper eta_T", et0, et1)
    print(f"\n  PT-329201: {'DECREASED/STABLE' if dpt <= H.FLAT else 'SPIKED'};"
          f"  eta_T: {'DROPPED' if det < -H.FLAT else 'FLAT'}")

    p = 0
    p += H.check("feed N/C rises with NH3", dfn > H.FLAT, "")
    p += H.check("conversion X rises with feed N/C (Inoue-Kanai f_L)", dxc > H.FLAT,
                 "X_conv = X(L,W,T)/X(L0,W0,T0) via reactor.py; excess NH3 above L=2 floor lifts conversion.")
    p += H.check("PT-329201 stabilizes/falls (not spike)", dpt <= H.FLAT,
                 "treats excess NH3 as inert -> P would spike")
    p += H.check("eta_T falls with N/C", det < -H.FLAT,
                 "eta_T=f(T_steam,P) only; NO N/C term (line 226). Excess NH3 invisible to stripper.")
    print("  NOTE: AT-322701 (overflow N/C) is invariant by design -- atom-conserving ripple")
    print("        (Urea+d/NH3-2d/CO2-d) holds reactor-product N/C while feed N/C & X_conv move.")
    H.verdict(p, 4)


if __name__ == "__main__":
    main_test()
