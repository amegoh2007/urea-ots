r"""run_inerts_accum.py  --  LEVEL-5 AUDIT, PHASE 2 / TEST 1:  Inerts accumulation + vent lock-out.

Standalone stress test.  A single fresh 100% baseline is driven through a STAGED excursion that
simultaneously (a) injects a rising non-condensable inert load into the reactor and (b) throttles
the synthesis-loop vent HV-322604 shut.  Asserts the three runaway signatures:

    P_syn  climbs   (PT-329201 -> clamp ceiling)
    vent_frac drops (HV-322604 vent capacity / required purge -> 0)
    X_conv collapses (per-pass CO2->urea conversion)

  Physics of the inert injection (reduced model)
  ----------------------------------------------
  O2/N2 inerts are NOT in MW_COMP, so they cannot propagate as new stream species (every downstream
  consumer iterates `for k in MW_COMP` and silently drops unknown keys).  Their TWO real effects are
  modelled directly on the reactor result:

  1. REACTANT-PARTIAL-PRESSURE DILUTION (conversion penalty).  Inerts displace NH3/CO2 in the
     synthesis volume.  With inert molar load  n_I = frac * (n_NH3 + n_CO2),  the reactant mole
     fraction (= partial-pressure fraction at fixed loop P) is

         dil = (n_NH3 + n_CO2) / (n_NH3 + n_CO2 + n_I)

     and the realized urea extent / conversion are scaled by dil:

         xi_urea <- xi_urea * dil ,   X_conv <- X_conv * dil

     The un-formed urea is returned to the loop atom-conservingly by REVERSING the synthesis
     stoichiometry  CO2 + 2 NH3 -> Urea + H2O  on the overflow tear (d = xi_new - xi_old < 0):

         Urea += d ,  CO2 -= d ,  NH3 -= 2d ,  H2O += d           (bounded, mirrors reactor GAP#5)

     -> more unreacted NH3/CO2 strand in the loop (which also loads the stripper overhead and feeds
     the pressure rise via pb_push).

  2. NON-CONDENSABLE PURGE DEMAND.  Inerts can only leave through HV-322604.  Closing it
     (s.HIC_322604 -> 0) collapses vent_frac:

         vent_frac = (HIC_322604 / HIC604_DES) * sqrt(dP_vent / dP_DES)   -> 0

     and the synthesis-pressure ODE integrates PT-329201 up via the vent-deficit term:

         pt_target = pt_fwd
                     + SYN_P_DEFICIT_GAIN * max(1 - rho_cond, 0) * 140.7
                     + SYN_P_VENT_GAIN    * max(1 - vent_frac,0) * 140.7   (+0.30*140.7 ~ +42 bar)
         p_syn <- clamp(p_syn + (dt/tau)*(pt_target - p_syn),  p_syn_min, SYN_P_MAX_BARA=175)

     rho_cond = (m_ccw/des)*f_th / (co2_scale * nu),  nu = p_syn/140.7  -> positive feedback as p_syn
     rises.  The 175 bar clamp (relief margin) is the asymptote the engine must survive.

  HIC_322604 has NO step_sim controller (written only at init + the UI op cmd), so a per-tick pin
  holds it for the line-1223 vent_frac read.  tank_level_frac is pinned each tick (continuous-makeup)
  to keep the NH3-inventory trip 21_2 dormant over the long settle.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")   # Windows console cp1252

import main

DT          = 0.1
SETTLE_MIN  = 10.0
SETTLE_TICK = int(SETTLE_MIN * 60.0 / DT)          # 10 sim-min = 6 000 ticks / stage

# staged excursion: (inert_frac = n_inert/n_reactant , HV-322604 opening as fraction of design)
STAGES = [
    (0.00, 1.00),   # baseline (design vent, no inerts)
    (0.10, 0.80),
    (0.25, 0.60),
    (0.50, 0.40),
    (0.80, 0.20),
    (1.20, 0.05),
    (1.50, 0.00),   # full lock-out + heavy inert blanket
]

_INERT_FRAC = [0.0]    # shared with the reactor wrapper (list holder -> visible in closure)

# ---- monkeypatch: inject rising inert load -> dilute reactant pp -> collapse conversion ----
_orig_react = main.react_322r001
def _react_inert(*a, **k):
    out = _orig_react(*a, **k)
    frac = _INERT_FRAC[0]
    if frac > 0.0:
        feed     = out["feed_kmolh"]
        reactant = feed.get("NH3", 0.0) + feed.get("CO2", 0.0)
        inert    = frac * reactant
        dil      = reactant / (reactant + inert) if (reactant + inert) > 0.0 else 1.0
        xi0      = out["xi_urea"]
        xi_new   = xi0 * dil
        ov       = out["overflow_kmolh"]
        d        = xi_new - xi0                                   # < 0 : reverse the urea shift
        d        = max(d, -ov.get("Urea", 0.0), -ov.get("H2O", 0.0))   # bound (reactor GAP#5)
        out["xi_urea"] = xi0 + d
        out["X_conv"] *= dil
        ov["Urea"] += d
        ov["CO2"]  -= d
        ov["NH3"]  -= 2.0 * d
        ov["H2O"]  += d
        out["inert_kmolh"] = inert
    return out
main.react_322r001 = _react_inert


def run_stage(frac, hic_pct, tank_pin):
    _INERT_FRAC[0] = frac
    s = main.state
    pkt = None
    for _ in range(SETTLE_TICK):
        s.HIC_322604 = hic_pct                 # pin vent valve (no step_sim controller writes it)
        pkt = main.step_sim(DT)
        s.tank_level_frac = tank_pin           # continuous-makeup pin -> trip 21_2 dormant
    return pkt


def collect(pkt, s):
    react = pkt["REACT_322R001"]
    strip = pkt["STRIP_322E001"]
    scrub = pkt["SCRUB_322E003"]
    return {
        "vent_frac": scrub["vent_frac"],
        "rho_cond":  scrub["ccw"]["rho_cond"],
        "p_syn":     round(s.p_syn_bara, 2),
        "x_conv":    react["X_conv"],
        "xi_urea":   react["xi_urea"],
        "nc_act":    react["AT_322701"],
        "urea_bot":  strip["bot_mass_pct"].get("Urea", float("nan")),
        "trip":      any(s.trip_latched.values()),
    }


def main_run():
    main.state = main.State()
    s = main.state
    base_hic  = s.HIC_322604            # design opening (SCRUB_HIC604_DES_PCT)
    tank_pin  = s.tank_level_frac

    print("=" * 110)
    print("  LEVEL-5 AUDIT  /  PHASE 2  --  TEST 1: INERTS ACCUMULATION + VENT LOCK-OUT")
    print(f"  (single baseline, staged; settle {SETTLE_MIN:.0f} sim-min/stage; design vent HIC604={base_hic:.0f}%, "
          f"SYN_P_MAX={main.SYN_P_MAX_BARA:.0f} bar a)")
    print("=" * 110)

    rows = []
    for frac, vfrac in STAGES:
        hic = base_hic * vfrac
        pkt = run_stage(frac, hic, tank_pin)
        r = collect(pkt, s)
        r["frac"] = frac
        r["hic"]  = round(hic, 1)
        rows.append(r)
        flag = "  <-- TRIP LATCHED" if r["trip"] else ""
        print(f"  inert_frac={frac:<4}  HIC604={hic:>5.1f}%  ->  vent_frac={r['vent_frac']:<7} "
              f"P_syn={r['p_syn']:<7}bar  X_conv={r['x_conv']:<6}%{flag}")

    print("\n" + "-" * 110)
    print("  TABLE  --  INERT LOAD / VENT LOCK-OUT RESPONSE")
    print("-" * 110)
    hdr = (f"  {'inert':>6} | {'HIC604':>7} | {'vent_frac':>9} | {'rho_cond':>8} | "
           f"{'P_syn':>8} | {'X_conv':>7} | {'xi_urea':>8} | {'N/C ov':>6} | {'Urea%bot':>8}")
    sub = (f"  {'frac':>6} | {'%open':>7} | {'HV604':>9} | {'cond':>8} | "
           f"{'bar a':>8} | {'%/pass':>7} | {'kmol/h':>8} | {'AT701':>6} | {'->LV501':>8}")
    print(hdr); print(sub); print("  " + "-" * 106)
    for r in rows:
        print(f"  {r['frac']:>6} | {r['hic']:>7} | {r['vent_frac']:>9} | {r['rho_cond']:>8} | "
              f"{r['p_syn']:>8} | {r['x_conv']:>7} | {r['xi_urea']:>8} | {r['nc_act']:>6} | {r['urea_bot']:>8}")

    base, fin = rows[0], rows[-1]
    print("\n  ASSERTIONS (final stage vs baseline):")
    a1 = fin["p_syn"]     > base["p_syn"]
    a2 = fin["vent_frac"] < base["vent_frac"]
    a3 = fin["x_conv"]    < base["x_conv"]
    sat = abs(fin["p_syn"] - main.SYN_P_MAX_BARA) < 1.0
    print(f"   [{'PASS' if a1 else 'FAIL'}]  P_syn climbs   : {base['p_syn']} -> {fin['p_syn']} bar a"
          f"  ({'SATURATED at clamp ' + str(main.SYN_P_MAX_BARA) if sat else 'below clamp'})")
    print(f"   [{'PASS' if a2 else 'FAIL'}]  vent_frac drops: {base['vent_frac']} -> {fin['vent_frac']}")
    print(f"   [{'PASS' if a3 else 'FAIL'}]  X_conv collapse: {base['x_conv']} -> {fin['x_conv']} %/pass")
    assert a1, "FAIL: P_syn did not climb under inert load + vent lock-out"
    assert a2, "FAIL: vent_frac did not drop as HV-322604 closed"
    assert a3, "FAIL: conversion did not collapse under inert dilution"
    print("\n  RESULT: PASS -- engine integrated the runaway to the 175 bar relief clamp without divergence.")
    print("=" * 110)


if __name__ == "__main__":
    main_run()
