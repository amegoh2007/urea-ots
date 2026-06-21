"""
Scenario: HV-322605 (HIC-322605, reactor 322R001 bottom outlet take-off) closed to 20%.
Outlet discharge gated -> m_out < m_in -> reactor liquid backs up -> LT-322504 rises to the
100% flood clamp -> solution carried over the off-gas line (TT-322009 lip) to the HP scrubber.

Reports the 6 requested indicators at the flooded/settled condition:
  1- TT-322014  (322R001 overflow feed temp, C)            STRIP_322E001.TT_322014  = s.react_T_overflow
  2- TT-322009  (322R001 off-gas line temp -> 322E003, C)  REACT_322R001.TT_322009  = react["T_offgas"]
  3- PT-329001  (ABSENT in model -> reported as PT-329201, synthesis overflow line P, bar a)
                                                            EJ_322F001.PI_329201     = s.p_syn_bara
  4- TT-322002  (322E003 overflow temp -> 322F001, C lag)  SCRUB_322E003.TT_322002  = d_TT322002
  5- TT-322011  (322E003 off-gas temp -> HV-322604, C lag) SCRUB_322E003.TT_322011  = d_TT322011
  6- TDY-329125 (TT-329125 - TIC-329005, cond. quality, C) SCRUB_322E003.ccw.TDY_329125

No model edits. Pure forward integration of step_sim(DT) with HIC_322605 held at 20%.
"""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import main

DT = 0.1

def grab(tel):
    return {
        "TT_322014":   tel["STRIP_322E001"]["TT_322014"],
        "TT_322009":   tel["REACT_322R001"]["TT_322009"],
        "PT_329201":   tel["EJ_322F001"]["PI_329201"],
        "TT_322002":   tel["SCRUB_322E003"]["TT_322002"],
        "TT_322011":   tel["SCRUB_322E003"]["TT_322011"],
        "TDY_329125":  tel["SCRUB_322E003"]["ccw"]["TDY_329125"],
        "LT_322504":   tel["REACT_322R001"]["LT_322504"],
        "HIC_322605":  tel["REACT_322R001"]["HIC_322605"],
    }

def main_run():
    main.state = main.State()
    s = main.state

    # baseline at design (one tick, valve untouched at design 60%)
    base = grab(main.step_sim(DT))

    # ---- close HV-322605 to 20% ----
    s.HIC_322605 = 20.0

    MAXT = 200000          # 20000 s cap
    SETTLE_KEYS = ("TT_322014","TT_322009","PT_329201","TT_322002","TT_322011","TDY_329125")
    hist = None
    flood_tick = None
    settle_tick = None
    last = None
    for i in range(1, MAXT+1):
        tel = main.step_sim(DT)
        cur = grab(tel)
        if flood_tick is None and cur["LT_322504"] >= 99.99:
            flood_tick = i
        # settle test: level clamped AND all 6 indicators delta < 1e-3 over 200 ticks (20 s)
        if flood_tick is not None and i % 200 == 0:
            if hist is not None:
                d = max(abs(cur[k]-hist[k]) for k in SETTLE_KEYS)
                if cur["LT_322504"] >= 99.99 and d < 1e-3:
                    settle_tick = i
                    last = cur
                    break
            hist = dict(cur)
        last = cur

    print("=== HV-322605 -> 20% reactor-flood scenario ===")
    print("DT=%.3f s   flood@%.1f s   settle@%s s" % (
        DT,
        (flood_tick*DT if flood_tick else float('nan')),
        ("%.1f" % (settle_tick*DT)) if settle_tick else "NOT-SETTLED(cap)"))
    print()
    hdr = "%-14s %14s %14s" % ("indicator", "design(60%)", "flood(20%)")
    print(hdr); print("-"*len(hdr))
    rows = [
        ("TT-322014",  "C",      "TT_322014"),
        ("TT-322009",  "C",      "TT_322009"),
        ("PT-329201",  "bar a",  "PT_329201"),
        ("TT-322002",  "C",      "TT_322002"),
        ("TT-322011",  "C",      "TT_322011"),
        ("TDY-329125", "C",      "TDY_329125"),
        ("LT-322504",  "%",      "LT_322504"),
        ("HIC-322605", "%",      "HIC_322605"),
    ]
    for tag, unit, key in rows:
        print("%-11s %-3s %12.3f %14.3f" % (tag, unit, base[key], last[key]))

if __name__ == "__main__":
    main_run()
