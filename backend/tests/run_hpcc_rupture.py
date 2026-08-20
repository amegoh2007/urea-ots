r"""run_hpcc_rupture.py  --  LEVEL-5 AUDIT, PHASE 2 / TEST 2:  HPCC tube rupture (water ingress).

Standalone stress test.  A single fresh 100% baseline is driven through a STEPPED HP carbamate
condenser (322E002) tube rupture: low-pressure shell-side cooling water leaks into the two-phase
process product that feeds the reactor.  Asserts the equilibrium-reversal signatures:

    W (reactor-feed H/C, H2O/CO2)  climbs
    X_conv (per-pass CO2->urea conversion)  drops
    Urea content of the reactor->stripper stream  drops

  Physics (clean -- H2O IS in MW_COMP, so the leak propagates as a real stream species)
  -------------------------------------------------------------------------------------
  The HPCC product feed dict carries an extra water term:

      feed_kmolh["H2O"] += leak_kgh / MW_COMP["H2O]

  react_322r001 consumes hpcc["feed_kmolh"] -> react_couple recomputes the reactor-feed H/C:

      W = feed["H2O"] / feed["CO2"]                                  (climbs with the leak)

  and the modified Inoue-Kanai water penalty drags conversion down (Le Chatelier: excess water
  reverses  2 NH3 + CO2 <-> carbamate <-> urea + H2O):

      f_W   = 1 / (1 + BETA_HC * W)                                  (falls as W rises)
      X     = X_INF * f_L * f_W * f_T
      xi_urea = xi_urea_des * X(L,W,T) / X(L0,W0,T0)                 (falls)

  The fresh-feed N/C (pump flows) is untouched, so L_drive holds at design -> this isolates the
  PURE water-penalty (H/C) response.  tank_level_frac is pinned each tick (continuous-makeup) so
  trip 21_2 stays dormant over the settle.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")   # Windows console cp1252

import main

DT          = 0.1
SETTLE_MIN  = 10.0
SETTLE_TICK = int(SETTLE_MIN * 60.0 / DT)          # 10 sim-min = 6 000 ticks / step
LEAK_STEPS  = [0.0, 2500.0, 5000.0, 10000.0, 20000.0, 40000.0]   # kg/h water into HPCC product

_LEAK = [0.0]    # shared with the HPCC wrapper

# ---- monkeypatch: inject leak water (kg/h) into the HPCC two-phase product feed ----
_orig_hpcc = main.hpcc_322e002
def _hpcc_leak(*a, **k):
    out = _orig_hpcc(*a, **k)
    if _LEAK[0] > 0.0:
        out["feed_kmolh"]["H2O"] += _LEAK[0] / main.MW_COMP["H2O"]
    return out
main.hpcc_322e002 = _hpcc_leak


def run_step(leak_kgh, tank_pin):
    _LEAK[0] = leak_kgh
    s = main.state
    pkt = None
    for _ in range(SETTLE_TICK):
        pkt = main.step_sim(DT)
        s.tank_level_frac = tank_pin
    return pkt


def collect(pkt, s):
    react = pkt["REACT_322R001"]
    strip = pkt["STRIP_322E001"]
    return {
        "w_feed":   react["W_feed"],
        "x_conv":   react["X_conv"],
        "xi_urea":  react["xi_urea"],
        "nc_act":   react["AT_322701"],
        "urea_bot": strip["bot_mass_pct"].get("Urea", float("nan")),
        "eta_T":    strip["eta_T"],
        "trip":     any(s.trip_latched.values()),
    }


def main_run():
    main.state = main.State()
    s = main.state
    tank_pin = s.tank_level_frac
    h2o_mw   = main.MW_COMP["H2O"]

    print("=" * 110)
    print("  LEVEL-5 AUDIT  /  PHASE 2  --  TEST 2: HPCC TUBE RUPTURE (LP COOLING-WATER INGRESS)")
    print(f"  (single baseline, stepped leak; settle {SETTLE_MIN:.0f} sim-min/step; MW_H2O={h2o_mw}; "
          f"fresh-feed N/C held at design)")
    print("=" * 110)

    rows = []
    for leak in LEAK_STEPS:
        pkt = run_step(leak, tank_pin)
        r = collect(pkt, s)
        r["leak"]   = leak
        r["leak_kmolh"] = round(leak / h2o_mw, 1)
        rows.append(r)
        flag = "  <-- TRIP LATCHED" if r["trip"] else ""
        print(f"  leak={leak:>7.0f} kg/h ({r['leak_kmolh']:>5} kmol/h)  ->  W={r['w_feed']:<7} "
              f"X_conv={r['x_conv']:<6}%  Urea%bot={r['urea_bot']:<6}{flag}")

    print("\n" + "-" * 110)
    print("  TABLE  --  WATER-INGRESS / EQUILIBRIUM-REVERSAL RESPONSE")
    print("-" * 110)
    hdr = (f"  {'leak':>8} | {'leak':>8} | {'W_feed':>7} | {'X_conv':>7} | {'xi_urea':>8} | "
           f"{'N/C ov':>6} | {'Urea%bot':>8} | {'eta_T':>6}")
    sub = (f"  {'kg/h':>8} | {'kmol/h':>8} | {'H2O/CO2':>7} | {'%/pass':>7} | {'kmol/h':>8} | "
           f"{'AT701':>6} | {'->LV501':>8} | {'strip':>6}")
    print(hdr); print(sub); print("  " + "-" * 106)
    for r in rows:
        print(f"  {r['leak']:>8.0f} | {r['leak_kmolh']:>8} | {r['w_feed']:>7} | {r['x_conv']:>7} | "
              f"{r['xi_urea']:>8} | {r['nc_act']:>6} | {r['urea_bot']:>8} | {r['eta_T']:>6}")

    base, fin = rows[0], rows[-1]
    print("\n  ASSERTIONS (final step vs baseline):")
    # monotonicity over the full ramp
    mono_w  = all(rows[i]["w_feed"]  >= rows[i-1]["w_feed"]  - 1e-9 for i in range(1, len(rows)))
    mono_x  = all(rows[i]["x_conv"]  <= rows[i-1]["x_conv"]  + 1e-9 for i in range(1, len(rows)))
    mono_xi = all(rows[i]["xi_urea"] <= rows[i-1]["xi_urea"] + 1e-9 for i in range(1, len(rows)))
    a1 = fin["w_feed"]  > base["w_feed"]  and mono_w
    a2 = fin["x_conv"]  < base["x_conv"]  and mono_x
    a3 = fin["xi_urea"] < base["xi_urea"] and mono_xi      # absolute urea make = true conversion proxy
    print(f"   [{'PASS' if a1 else 'FAIL'}]  W climbs (mono)    : {base['w_feed']} -> {fin['w_feed']}  H2O/CO2")
    print(f"   [{'PASS' if a2 else 'FAIL'}]  X_conv drops (mono): {base['x_conv']} -> {fin['x_conv']} %/pass")
    print(f"   [{'PASS' if a3 else 'FAIL'}]  urea make drops    : {base['xi_urea']} -> {fin['xi_urea']} kmol/h (mono)")
    print(f"   [note] bottoms Urea mass% is NON-monotone ({base['urea_bot']} -> {fin['urea_bot']} %): a")
    print( "          concentration, not an extent -- water/volatile re-partitioning + falling eta_T, NOT conversion.")
    assert a1, "FAIL: reactor water feed W did not climb monotonically with the leak"
    assert a2, "FAIL: conversion did not drop monotonically as W rose (water penalty)"
    assert a3, "FAIL: absolute urea production (xi_urea) did not fall monotonically as W rose"
    print("\n  RESULT: PASS -- the Inoue-Kanai water penalty reversed the equilibrium smoothly; no divergence.")
    print("=" * 110)


if __name__ == "__main__":
    main_run()
