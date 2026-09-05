"""Shared harness for system-level validation tests (test_1..test_4).
Drives the live engine (main.state / main.step_sim) — no fabrication, reads real packet.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402


def reset():
    """Re-instantiate design steady state."""
    main.state = main.State()


def run(n, dt=2.0):
    """Advance n ticks of `dt` PLANT SECONDS, integrated in STEP_CAP-bounded sub-steps.

    The plant time each caller advances is unchanged -- n*dt seconds, exactly as before -- but the
    PHYSICS is now integrated the way the engine integrates it.  `main.STEP_CAP` is 0.25 s and
    `sim_task` bounds every physical sub-step by it whatever the wall tick or the speed multiplier;
    its own comment records that 0.5 s "is UNSTABLE".  This harness was calling step_sim(2.0), i.e.
    EIGHT times a step the engine declares unstable at two, and the results at that step are not
    the model's.

    Measured, on this file's own CCW-cut scenario (test_3): at 0.25 s the 322E003 sump troughs to
    45.8 % and recovers to 49.8 %, which is what report D-19 says it should do; at 2.0 s it saturates
    at 100 % and PT-329201 runs to 145.5 bar a.  The mechanism is not new and is not the scrubber's:
    SIC-321951's actuator lag is `alpha = min(1, dt/2)`, so at dt >= 2 s the lag COLLAPSES, the
    speed loop becomes a pure algebraic feedback with characteristic roots {1, -2}, and the NH3
    motive flow rings at +/-20 % of stroke.  That ringing used to be invisible because the CO2 feed
    and the ejector capacity were both pinned constants that could not propagate it; reports D-5 and
    D-6 make both live, and the jet-pump closure amplifies a motive deviation about tenfold at this
    machine's operating point.  So the harness step had to be fixed before any of these tests could
    grade physics rather than truncation error.
    """
    pkt = None
    remaining = float(n) * float(dt)
    while remaining > 1e-12:
        h = min(main.STEP_CAP, remaining)
        pkt = main.step_sim(h)
        remaining -= h
    return pkt


def find(d, key):
    """Deep-search nested dict for first occurrence of `key` (unique tags only)."""
    if isinstance(d, dict):
        if key in d:
            return d[key]
        for v in d.values():
            r = find(v, key)
            if r is not None:
                return r
    elif isinstance(d, list):
        for v in d:
            r = find(v, key)
            if r is not None:
                return r
    return None


def eta_T(pkt):
    """Stripper thermal efficiency — direct tag or back-out from xi_biu = XI_BIU_DES*eta_T."""
    e = find(pkt, "eta_T")
    if e is not None:
        return e
    xb = find(pkt, "xi_biu")
    des = getattr(main, "STRIP_XI_BIU_DES", None)
    return (xb / des) if (xb is not None and des) else None


def hc_ratio(pkt):
    """Reactor-feed H/C (water-to-carbon) molar ratio from HPCC 322E002 liquid product (mass %)."""
    comp = (pkt.get("HPCC_322E002") or {}).get("liq_mass_pct")
    if not comp:
        return None
    mw, cat = main.MW_COMP, main.REACT_C_ATOMS
    n = {k: comp.get(k, 0.0) / mw[k] for k in mw}            # rel moles per 100 g
    n_c = sum(n[k] * cat.get(k, 0) for k in mw)
    return (n.get("H2O", 0.0) / n_c) if n_c else None


def pct(new, base):
    return (new - base) / base * 100.0 if base else float("nan")


FLAT = 1.0  # |Δ%| below this = structurally flat (no coupling)


def row(tag, base, new):
    if base is None or new is None:                       # tag not emitted to packet
        b = f"{base:>11.3f}" if base is not None else f"{'n/a':>11}"
        n = f"{new:>11.3f}" if new is not None else f"{'n/a':>11}"
        print(f"  {tag:<26} {b} -> {n}   {'n/a':>7}  [n/a ]")
        return 0.0
    d = pct(new, base)
    flag = "FLAT" if abs(d) < FLAT else ("UP" if d > 0 else "DOWN")
    print(f"  {tag:<26} {base:>11.3f} -> {new:>11.3f}   {d:+7.1f}%  [{flag}]")
    return d


def check(label, ok, gap):
    print(f"  [{'PASS' if ok else 'GAP '}] {label}" + ("" if ok else f"  --> {gap}"))
    return ok


def verdict(passes, total):
    print(f"\n  VERDICT: {passes}/{total} physical expectations met.", end=" ")
    print("STRUCTURALLY SOUND." if passes == total else "STRUCTURAL GAPS recorded above.")
