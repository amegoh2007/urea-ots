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
    """Advance n steps, return last packet."""
    pkt = None
    for _ in range(n):
        pkt = main.step_sim(dt)
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
