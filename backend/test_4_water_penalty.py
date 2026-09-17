"""TEST 4 - Water penalty on reactor equilibrium (LeChatelier).
Action : +10% H2O mass frac in the LIVE 322E003 carbamate recycle (state.y_scrub_ovf) -> ejector -> HPCC.
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

    # PHASE 4b, report D-6: the lever is the LIVE 322E003 sump vector, not the module constant.
    #   `EJ_CARB_FRAC` used to BE the entrained composition -- a frozen design vector -- so a test
    #   could perturb the recycle water by editing it.  The ejector now entrains what the scrubber
    #   sump actually holds, on a one-tick tear (`state.y_scrub_ovf`), which the scrubber rewrites
    #   from its own overflow every tick.  Editing the constant therefore moves nothing after the
    #   first tick, and this test's +10 % water step has to be applied where the water now lives.
    #   The scrubber pins the composition back over the hold window, so the step is re-applied each
    #   tick for the duration -- which is what a sustained wetter recycle IS.
    st = H.main.state
    saved = dict(st.y_scrub_ovf)
    try:
        wet = dict(saved)
        wet["H2O"] *= 1.10                 # +10% H2O mass frac in the 322E003 carbamate recycle
        tot = sum(wet.values())
        wet = {k: v / tot for k, v in wet.items()}
        #   The scrubber rewrites the vector at the END of every SUB-step, so the step has to be
        #   re-applied at the same cadence -- once per sub-step, immediately before the ejector
        #   reads it at the top of the tick.
        new = None
        for _ in range(120 * 8):
            st.y_scrub_ovf = dict(wet)     # hold the wetter recycle against the scrubber's rewrite
            new = H.main.step_sim(H.main.STEP_CAP)
        hc1  = H.find(new, "W_feed")
        x1   = xi_urea(new)
        top1 = H.find(new, "top_th")
    finally:
        st.y_scrub_ovf = dict(saved)

    print("TEST 4 - WATER PENALTY (+10% H2O in carbamate recycle)")
    print(f"  {'TAG':<26} {'BEFORE':>11} {'AFTER':>11}      d%   STATE")
    dhc  = H.row("Reactor feed H/C (W_feed)", hc0, hc1)
    dx   = H.row("Conversion xi_urea (kmol/h)", x0, x1)
    dtop = H.row("Stripper overhead (t/h)", top0, top1)

    p = 0
    p += H.check("H/C rises with recycle water", dhc > H.FLAT,
                 "live 322E003 sump vector -> ejector disch -> HPCC feed -> W_feed (H2O/CO2 molar). Should rise.")
    p += H.check("conversion X drops with H/C (water penalty)", dx < -H.FLAT,
                 "xi_urea conversion-coupled via reactor.py Inoue-Kanai f_W=1/(1+b*W); if flat, check W_feed propagation.")
    p += H.check("stripper overhead load rises (more unconverted)", dtop > H.FLAT,
                 "overflow now carries +CO2/+NH3 when conversion drops (atom-conserving ripple); top vapour should rise.")
    H.verdict(p, 3)


if __name__ == "__main__":
    main_test()
