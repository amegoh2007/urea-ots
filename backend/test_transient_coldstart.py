"""Section 6.4 cold-start transient acceptance gate.

Promotes `tests/coldstart_probe.py` -- a print-only probe that exits 0 whatever it
measures, and which no suite collected -- into an asserting, pytest-collected gate, so
the Section 6.4 criteria fail the build instead of scrolling past in stdout.

Drives the engine headless from a cold, empty, depressurized synthesis loop with the
design feed lineup held ON (the "feed-on step"), records PT-329201 (`s.p_syn_bara`), and
identifies an FOPTD with the MODEL-FREE Smith two-point method -- no least-squares fit
whose result could be biased by an assumed model shape:

    tau = 1.5 * (t63 - t28),    t_d = t63 - tau = 1.5*t28 - 0.5*t63

t28 / t63 are the times to first reach 28.3% / 63.2% of the total step span (P0 -> P_f).
P_f is the mean of the last 15 samples (settled plateau, robust to sample noise).

Acceptance (report Section 6.4; DCS-anchored FOPTD band, dcs_anchor_dynamics Section 1.2
from the 03-06 synthesis startup trend, tau = 3469.5 +/- 585.9 s):

    tau_sim in [2884, 4055] s,   t_d,sim <= 572 s,   P_f in [137.5, 150.5] barg

This is an EXTERNAL driver: it only sets initial conditions on a fresh State and calls the
public step_sim(). No engine constant is modified, so conservation and the boot-pin
bit-exactness are untouched -- test_design_hold_stays_pinned below asserts the design hold
is still bit-identical, which is what makes the cold-start IC legitimate rather than a tune.

Run from backend/:  python test_transient_coldstart.py   (or via pytest)
"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main

ATM = 1.01325           # bar, bara -> barg

# --- 03-06 field anchor + Section 6.4 acceptance band ---
P0_BARG    = 5.7        # field PT-329201 initial (03-06 anchor, report "Key verified numbers")
TAU_LO_S   = 2884.0     # 3469.5 - 585.9
TAU_HI_S   = 4055.0     # 3469.5 + 585.9
TD_MAX_S   = 572.0
PF_LO_BARG = 137.5      # 144.0 - 6.5
PF_HI_BARG = 150.5      # 144.0 + 6.5

# --- drive parameters (match tests/coldstart_probe.py: same scenario, same numbers) ---
DT     = 0.5            # s, Euler-stable sub-step (== STEP_CAP)
T_END  = 16000.0        # s, extended so the slow (57.8 min) loop fully plateaus before P_f is read
SAMPLE = 30.0           # s

_run_cache = {}


def _cold_start_run():
    """Drive the feed-on step from a cold empty loop; return (ts, ps) in (s, bara).
    Cached: the drive is ~32k steps, and all three criteria interrogate one trajectory."""
    if "r" in _run_cache:
        return _run_cache["r"]

    main.state = main.State()          # fresh design state
    s = main.state
    s.p_syn_bara = P0_BARG + ATM       # cold depressurized loop
    # empty the three HP liquid inventories that drive m_loop_frac (the PT floor + tau schedule)
    s.react_level_pct    = 0.0
    s.react_lt322504_pct = 0.0
    s.react_m_liq        = main.reactor.M_HOLDUP_MIN
    s.react_m_in_lag     = 0.0
    s.react_fwd_wash     = 0.0
    s.hpcc_level_pct     = 0.0
    s.strip_level        = 0.0
    s.scrub_holdup_kg    = 0.0
    s.scrub_level_pct    = 0.0
    s.tlag = {}                        # fresh transport-delay buffers: FEED_TD_S starts clean
    # feed lineup stays at the design seed = feed ON (pumpB on, XV_321901/322901/322902 open).

    t, next_s = 0.0, 0.0
    ts, ps = [], []
    while t < T_END:
        main.step_sim(DT)
        t += DT
        if t >= next_s:
            ts.append(t); ps.append(s.p_syn_bara)
            next_s += SAMPLE

    main.state = main.State()          # don't leak the cold state into other tests
    _run_cache["r"] = (ts, ps)
    return _run_cache["r"]


def _foptd():
    """Model-free Smith two-point FOPTD ID. Returns (tau_s, td_s, Pf_barg)."""
    if "f" in _run_cache:
        return _run_cache["f"]
    ts, ps = _cold_start_run()
    P0 = ps[0]
    Pf = sum(ps[-15:]) / 15.0          # settled plateau
    span = Pf - P0

    def t_cross(frac):
        target = P0 + frac * span
        for i in range(1, len(ps)):
            if ps[i] >= target:
                p_lo, p_hi = ps[i - 1], ps[i]
                t_lo, t_hi = ts[i - 1], ts[i]
                if p_hi == p_lo:
                    return t_hi
                return t_lo + (target - p_lo) / (p_hi - p_lo) * (t_hi - t_lo)
        return float("nan")            # never reached -> did not plateau

    t28, t63 = t_cross(0.283), t_cross(0.632)
    tau = 1.5 * (t63 - t28)
    _run_cache["f"] = (tau, t63 - tau, Pf - ATM)
    return _run_cache["f"]


# ===== the pin must survive the harness =====

def test_design_hold_stays_pinned():
    """Design hold is bit-exact: the cold-start IC below is an initial condition, not a tune."""
    main.state = main.State()
    p0 = main.state.p_syn_bara
    for _ in range(20):
        main.step_sim(0.5)
    p1 = main.state.p_syn_bara
    assert p1 == p0, f"design hold drifted: {p0!r} -> {p1!r}"


# ===== Section 6.4 acceptance criteria =====

def test_coldstart_plateaus():
    """Guard the ID itself: a trajectory that never reaches 63.2% makes tau/t_d meaningless."""
    tau, td, pf = _foptd()
    assert tau == tau and td == td, "step never reached 63.2% of span -- loop did not plateau"


def test_coldstart_tau_in_band():
    tau, _, _ = _foptd()
    assert TAU_LO_S <= tau <= TAU_HI_S, \
        f"tau_sim={tau:.1f} s outside Section 6.4 band [{TAU_LO_S:.0f},{TAU_HI_S:.0f}]"


def test_coldstart_dead_time_within_limit():
    _, td, _ = _foptd()
    assert td <= TD_MAX_S, f"t_d,sim={td:.1f} s exceeds Section 6.4 limit {TD_MAX_S:.0f} s"


def test_coldstart_final_pressure_in_band():
    _, _, pf = _foptd()
    assert PF_LO_BARG <= pf <= PF_HI_BARG, \
        f"P_f={pf:.2f} barg outside Section 6.4 band [{PF_LO_BARG},{PF_HI_BARG}]"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    fails = 0
    for t in tests:
        try:
            t(); print("PASS", t.__name__)
        except Exception:
            fails += 1; print("FAIL", t.__name__); traceback.print_exc()
    tau, td, pf = _foptd()
    print(f"\n=== Section 6.4 ===  tau={tau:.1f} s   t_d={td:.1f} s   P_f={pf:.2f} barg")
    raise SystemExit(1 if fails else 0)
