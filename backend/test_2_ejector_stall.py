"""TEST 2 - Ejector / hydraulic stall.
Action : step-close HP NH3 pump discharge to 40% -> motive flow to ejector 322F001 drops.
Output : time-series (every 1 sim minute, 10 min): pump disch P, ejector Re, HPCC level, reactor level.
Expect : Re drops; HPCC (322E002) liquid level swells; reactor (322R001) level falls (starved).
Bridge : ejector Re=f(Pdisch/Psuc)  +  HPCC level state  +  reactor level=f(actual feed).
"""
import _systest as H


def snap(t, pkt):
    pd = H.find(pkt, "PI_disch")            # pump/synthesis discharge header (bar g)
    mu = pkt["EJ_322F001"]["mu"]            # entrainment ratio Re = m_suc/m_motive
    hl = H.find(pkt, "LT_322E002")          # HPCC level — NOT modelled (no state)
    rl = H.find(pkt, "LT_322504")           # reactor level (%)
    hl_s = f"{hl:11.1f}" if hl is not None else f"{'n/a':>11}"
    print(f"  {t:6d} {pd:13.1f} {mu:11.4f} {hl_s} {rl:12.1f}")
    return pd, mu, hl, rl


def main_test():
    H.reset()
    H.run(40)                                # settle
    print("TEST 2 - EJECTOR STALL (pump discharge -> 40%, 10 min)")
    print(f"  {'t(min)':>6} {'Pdisch(barg)':>13} {'Re(mu)':>11} {'HPCC lvl%':>11} {'React lvl%':>12}")

    base = H.run(1)
    pd0, mu0, _, rl0 = snap(0, base)
    H.main.state.SIC_321951.op = 86.2 * 0.40   # step pump discharge to 40%
    last = None
    for m in range(1, 11):
        last = snap(m, H.run(30))            # 30 steps x 2 s = 60 s
    pd1, mu1, hl1, rl1 = last

    print()
    p = 0
    p += H.check("pump discharge P drops", pd1 < pd0 - H.FLAT,
                 "PI_disch pinned to P_SYN_DOWN_BAR-1 (line 887); PD pump, no head curve H=A-B*m^2.")
    p += H.check("ejector Re drops (pressure-ratio stall)", mu1 < mu0 - 1e-6,
                 "mu=f(HV-322602 spindle) only, indep of Pdisch/Psuc (line 209). No stall.")
    p += H.check("HPCC level swells", hl1 is not None,
                 "NO HPCC (322E002) liquid-level state in engine. Inventory not modelled.")
    p += H.check("reactor level falls (starved)", rl1 < rl0 - H.FLAT,
                 "LT-322504 dV=Vdot_DES*s*(1-phi/phi_des): uses DESIGN throughput+valve, "
                 "NOT actual ejector feed (line 845). Decoupled from motive.")
    H.verdict(p, 4)


if __name__ == "__main__":
    main_test()
