r"""repro_bugs_3_4.py  --  FAILING reproduction for the two reported physics bugs.

Bug #3  HV-322604 (tiny inert-purge valve) -> PT-329201 over-coupling.
    Opening the off-gas valve from design (50%) to full (100%) currently CRASHES the
    synthesis pressure to the floor (~20 bar drop) because the vent term is two-sided
    and vent_frac is unbounded above (equal-% R=50 -> vent_frac=7.07 at 100%):
        pt_target += SYN_P_VENT_GAIN*(1 - vent_frac)*140.7   (= 0.30*(1-7.07)*140.7 = -256 bar)
    PHYSICAL EXPECTATION: a small inert-purge valve cannot move HP synthesis P much.
    ASSERT |dP_syn| from opening the valve is SMALL (< 2 bar).   <-- currently FAILS.

Bug #4  Reactor level (LT-322504) frozen at the weir lip on feed cut.
    Cut CO2 feed (XV-322902 shut) and HOLD the overflow valve HV-322605 wide open (100%).
    The Francis-weir outflow rho*Cw*(level-crest)^1.5 -> 0 once level reaches the crest
    (~79.8%), so the reactor inventory FREEZES; only ~6 h thermal contraction creeps it.
    PHYSICAL EXPECTATION: an open overflow line drains the vessel well below the lip.
    ASSERT level falls below 60% within 30 sim-min with HV-322605 open.   <-- currently FAILS.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

import main

DT = 0.1


def settle(ticks, **pins):
    s = main.state
    pkt = None
    for _ in range(ticks):
        for k, v in pins.items():
            setattr(s, k, v)
        pkt = main.step_sim(DT)
    return pkt


def bug3_hv604_vs_ptsyn():
    main.state = main.State()
    s = main.state
    # settle at design vent (HIC-322604 = 50%)
    settle(int(3 * 60 / DT), HIC_322604=main.SCRUB_HIC604_DES_PCT)
    p_design = s.p_syn_bara
    # open the tiny inert-purge valve fully and let PT settle
    settle(int(10 * 60 / DT), HIC_322604=100.0)
    p_open = s.p_syn_bara
    dP = p_open - p_design
    print(f"[Bug#3] PT-329201: design(HIC604=50%)={p_design:.2f} bar -> "
          f"full-open(HIC604=100%)={p_open:.2f} bar   dP={dP:+.2f} bar")
    ok = abs(dP) < 2.0
    print(f"   [{'PASS' if ok else 'FAIL'}]  |dP_syn| < 2 bar for a tiny purge valve "
          f"(got {abs(dP):.2f} bar)")
    return ok


def bug4_reactor_drain():
    main.state = main.State()
    s = main.state
    settle(int(2 * 60 / DT), HIC_322605=main.REACT_HIC605_DES_PCT)
    lvl0 = s.react_level_pct
    # cut CO2 feed, hold overflow valve WIDE OPEN, run 30 sim-min
    s.XV_322902 = False
    settle(int(30 * 60 / DT), HIC_322605=100.0, XV_322902=False)
    lvl1 = s.react_level_pct
    print(f"[Bug#4] LT-322504: start={lvl0:.2f}%  ->  after 30 min "
          f"(feed cut, HV-322605=100%)={lvl1:.2f}%   drop={lvl0 - lvl1:.2f}%")
    ok = lvl1 < 60.0
    print(f"   [{'PASS' if ok else 'FAIL'}]  level drains below 60% with overflow valve open "
          f"(got {lvl1:.2f}%)")
    return ok


if __name__ == "__main__":
    print("=" * 96)
    print("  FAILING REPRO  --  Bug #3 (HV-322604 -> PT-329201)  &  Bug #4 (reactor level drain)")
    print("=" * 96)
    r3 = bug3_hv604_vs_ptsyn()
    print("-" * 96)
    r4 = bug4_reactor_drain()
    print("=" * 96)
    print(f"  SUMMARY: Bug#3 {'PASS' if r3 else 'FAIL'} | Bug#4 {'PASS' if r4 else 'FAIL'}  "
          f"(both expected to FAIL before fix)")
    sys.exit(0 if (r3 and r4) else 1)
