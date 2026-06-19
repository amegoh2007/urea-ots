r"""_probe_indicator_rates.py -- dynamic-response audit of EVERY indicator.

For each stream/composition perturbation the probe settles to steady state, records a baseline
of every numeric indicator in the telemetry packet, applies a STEP to a stream input, then logs
all indicators every tick.  For each indicator that MOVES it measures the discrete rate history
and classifies the response:

  first-order sampled at DT:   x[k+1]-x[k] = (1-exp(-DT/tau)) * (x_final - x[k])
  => first-tick fraction f0 = 1 - exp(-DT/tau)  ~= DT/tau   (tau >> DT)

      step_fraction = max single-tick |dx| / |dx_total|
        ~1.0  -> change completed in ONE tick  -> tau <~ DT  -> INSTANTANEOUS (no time variable)
        <<1   -> spread over many ticks         -> tau >> DT  -> DYNAMIC (first-order, time-governed)

tau63 = time to reach 63.2 % of the total change (the first-order time constant).

A stateless algebraic block DOWNSTREAM of a dynamic state inherits that state's tau and will NOT
be flagged; only indicators with NO upstream time constant snap.  Those are the unphysical ones:
a temperature / composition / level that completes its entire change inside a single 0.1 s tick.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import main

DT       = 0.1
SETTLE   = 3000      # 5 min settle to steady state
NREC     = 1800      # 180 s of post-step recording
REL_TOL  = 0.005     # ignore indicators whose |delta| < 0.5 % of |baseline| ...
ABS_TOL  = 0.20      # ... and < 0.20 absolute (units) -> "did not respond"
FTF_THR  = 0.90      # first-tick-fraction >= this -> flagged INSTANTANEOUS

# operator-panel indicator tags only (exclude model-internal STREAMS.* / *.closure_resid leaves).
# Match the leaf name (last dotted segment) against the panel-tag families.
TAG_RE = re.compile(r"(^|\.)(TT|PT|PI|LT|LI|FT|FI|TI|AT|LIC|FIC|TIC|PIC|HIC)[_-]?[0-9]")


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        elif isinstance(v, bool):
            out[key] = (float(v), True)      # (value, is_bool)
        elif isinstance(v, (int, float)):
            out[key] = (float(v), False)
    return out


def settle_baseline(pin_tank=True):
    main.state = main.State()
    s = main.state
    tank_pin = s.tank_level_frac
    pkt = None
    for _ in range(SETTLE):
        pkt = main.step_sim(DT)
        if pin_tank:
            s.tank_level_frac = tank_pin
    return s, tank_pin, flatten(pkt)


def record(s, tank_pin, pin_tank=True):
    """Run NREC ticks, return {key: [v0, v1, ...]} for every numeric leaf."""
    series = {}
    for _ in range(NREC):
        pkt = main.step_sim(DT)
        if pin_tank:
            s.tank_level_frac = tank_pin
        for k, (v, _b) in flatten(pkt).items():
            series.setdefault(k, []).append(v)
    return series


def analyze(base, series):
    rows = []
    for k, traj in series.items():
        if not TAG_RE.search(k):           # operator-panel indicator tags only
            continue
        if len(traj) < 3:
            continue
        b = base.get(k, (traj[0], False))[0]
        is_bool = base.get(k, (0.0, False))[1]
        f = traj[-1]
        d_tot = f - b
        # responded?
        if abs(d_tot) < ABS_TOL and abs(d_tot) < REL_TOL * max(abs(b), 1e-9):
            continue
        if is_bool or (set(round(x, 6) for x in traj) <= {0.0, 1.0} and abs(d_tot) <= 1.0):
            rows.append((k, b, f, d_tot, float("nan"), float("nan"), "DISCRETE/alarm", float("nan")))
            continue
        # first-tick fraction: how much of the NET change is already present after ONE tick.
        #   ftf ~= 1.0  -> snapped in tick 1 (tau <~ DT, no time variable)  -> INSTANT
        #   ftf  < 1.0  -> spread over many ticks (first-order, tau >> DT)  -> dynamic
        ftf = (traj[0] - b) / d_tot if abs(d_tot) > 1e-12 else 1.0
        # tau63: first time cumulative change reaches 63.2 % of total (only meaningful if monotonic-ish)
        thr = b + 0.632 * d_tot
        tau63 = float("nan")
        for i, x in enumerate(traj):
            if (d_tot > 0 and x >= thr) or (d_tot < 0 and x <= thr):
                tau63 = (i + 1) * DT
                break
        max_rate = abs(traj[0] - b) / DT       # first-tick rate, units / s
        verdict = "INSTANT(no-tau)" if ftf >= FTF_THR else "dynamic"
        rows.append((k, b, f, d_tot, ftf, tau63, verdict, max_rate))
    return rows


def run(label, perturb, pin_tank=True):
    s, tank_pin, base = settle_baseline(pin_tank)
    perturb(s)
    series = record(s, tank_pin, pin_tank)
    rows = analyze(base, series)
    rows.sort(key=lambda r: (-(r[4] if r[4] == r[4] else -1), -abs(r[3])))  # NaN-safe: dynamics first by step_frac

    print(f"\n{'='*104}\n  PERTURBATION: {label}\n{'='*104}")
    print(f"  {'indicator':<26}{'base':>10}{'final':>10}{'delta':>10}"
          f"{'ftf':>10}{'tau63 s':>9}  {'verdict':<16}{'rate0/s':>12}")
    print("  " + "-" * 100)
    inst = []
    for r in rows:
        k, b, f, d, sf, t63 = r[0], r[1], r[2], r[3], r[4], r[5]
        verdict = r[6]
        mr = r[7] if len(r) > 7 else float("nan")
        sf_s  = f"{sf:>10.3f}" if sf == sf else f"{'--':>10}"
        t63_s = f"{t63:>9.2f}" if t63 == t63 else f"{'--':>9}"
        mr_s  = f"{mr:>12.2f}" if mr == mr else f"{'--':>12}"
        print(f"  {k:<26}{b:>10.2f}{f:>10.2f}{d:>10.2f}{sf_s}{t63_s}  {verdict:<16}{mr_s}")
        if verdict.startswith("INSTANT"):
            inst.append(k)
    if inst:
        print(f"\n  >>> FLAGGED INSTANTANEOUS (no time constant -- whole change in <=1 tick): {len(inst)}")
        for k in inst:
            print(f"        - {k}")
    else:
        print("\n  >>> none flagged: every responding indicator is first-order (time-governed).")
    return inst


def p_co2_cut(s):
    s.XV_322902 = False                         # CO2 isolation shut (composition + flow step)


def p_hv604_open(s):
    s.HIC_322604 = 80.0                         # HP off-gas vent valve 50 -> 80 % (stream-property step)


def p_nh3_pumpA(s):
    main.handle_cmd({"type": "pump_toggle", "id": "A"})  # start 2nd NH3 pump (feed-flow step)


if __name__ == "__main__":
    flagged = {}
    flagged["CO2 feed cut (XV-322902 shut)"]      = run("CO2 feed cut (XV-322902 shut)", p_co2_cut)
    flagged["HV-322604 open 50->80 %"]            = run("HV-322604 open 50->80 %", p_hv604_open)
    flagged["start 2nd NH3 pump A (feed-flow up)"] = run("start 2nd NH3 pump A (feed-flow up)", p_nh3_pumpA)

    print(f"\n{'='*104}\n  SUMMARY -- indicators that snap instantaneously (need a thermal/holdup time constant)\n{'='*104}")
    union = sorted(set(k for v in flagged.values() for k in v))
    if not union:
        print("  NONE -- all responding indicators are time-governed first-order responses.")
    for k in union:
        where = [lbl for lbl, ks in flagged.items() if k in ks]
        print(f"  {k:<26} flagged in: {', '.join(where)}")
