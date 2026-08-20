r"""run_mp_collapse.py  --  LEVEL-5 AUDIT, PHASE 2 / TEST 3:  MP steam-header collapse.

Standalone stress test.  From a fresh 100% baseline, the MP supply valve is stroked SHUT
(valve_supply_pct -> 0) and held.  With no utility make-up, the stripper reboiler keeps drawing
its fixed design duty, so the lumped-capacitance MP header drains and P_MP crashes from the seed
(19.7 bar a) down through 5 bar toward the floor.  Asserts the stripper-starvation signatures:

    eta_T (stripping efficiency)  collapses
    TT-322004 (bottoms temperature)  collapses
    unstripped carbamate (NH3 + CO2 in the bottoms)  floods

  Physics (dynamic steam_system.py + stripper steam coupling)
  -----------------------------------------------------------
  MP header mass balance (Euler, lumped capacitance C_MP):

      m_supply = K_SUPPLY * (valve%/100) * sqrt(P_EXT_MP - P_MP)        -> 0 at valve 0%
      dP_MP/dt = (m_supply - m_strip - m_ld) / C_MP
      m_strip  = STRIP_DUTY_DES_KW / 1850 ~ 21.3 kg/s   (fixed design reboiler draw)

  -> dP_MP/dt ~ (0 - 21.3 - m_ld)/25 ~ -1.0 bar/s : the header crashes in ~25 s.

  Stripper coupling (shell-side condensing MP steam):

      T_steam  = tsat(P_MP)                                            (Antoine, floored at p=0.01)
      eta_T_steam = clamp(T_steam / STRIP_STEAM_T_DES_C(211.6), 0, 1.15)
      eta_T       = eta_T_steam * g_NC * g_HC * g_T                    (g~1 here: feed unchanged)
      T_bot       = min(T_bot_des + 0.7*dTs + dT_bot + dT_strip,  T_steam)   -> dragged to T_steam
      mod         = eta_T_steam * eta_co2 * eta_P                      (split-fraction modulator -> 0)
      bot[k]      = avail[k] * (1 - clamp(STRIP_FRAC_DES[k]*mod, 0, 0.999))

  As P_MP -> 0:  T_steam -> ~5 C, eta_T_steam -> ~0.02, mod -> ~0, so the volatile split f -> 0 and
  NH3/CO2 stay in the bottoms (unstripped carbamate floods).  tsat is floored (no NaN) -> the engine
  must survive the P_MP -> 0 asymptote with finite, clamped state.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")   # Windows console cp1252

import main

DT        = 0.1
N_TICKS   = 600        # 60 s : long enough to crash P_MP to the floor + settle the bottoms
LOG_EVERY = 25         # 2.5 s


def snapshot(pkt, s, k):
    strip = pkt["STRIP_322E001"]
    bot   = strip["bot_mass_pct"]
    nh3   = bot.get("NH3", 0.0)
    co2   = bot.get("CO2", 0.0)
    return {
        "t":      round(k * DT, 1),
        "p_mp":   round(s.steam.P_MP, 3),
        "t_sat":  strip["steam"]["TI_shell"],     # tsat(P_MP), C
        "eta_T":  strip["eta_T"],
        "t_bot":  strip["TT_322004"],
        "nh3":    nh3,
        "co2":    co2,
        "carb":   round(nh3 + co2, 3),            # unstripped carbamate proxy (bottoms NH3+CO2 mass%)
        "urea":   bot.get("Urea", 0.0),
        "trip":   any(s.trip_latched.values()),
    }


def main_run():
    main._STEAM_READY = True            # ensure live header dynamics (already True post-import)
    main.state = main.State()
    s = main.state

    print("=" * 104)
    print("  LEVEL-5 AUDIT  /  PHASE 2  --  TEST 3: MP STEAM-HEADER COLLAPSE")
    print(f"  (valve_supply -> 0%; header drains at fixed m_strip~21.3 kg/s; seed P_MP={s.steam.P_MP:.1f} bar a, "
          f"design steam T=211.6 C)")
    print("=" * 104)

    # baseline tick (valve still at design 50% -> stationary fixed point)
    pkt0 = main.step_sim(DT)
    base = snapshot(pkt0, s, 0)

    # stroke MP supply valve fully shut and hold
    rows  = [base]
    cap5  = None                         # first sample at/below 5 bar (the instructed setpoint)
    last  = base
    for k in range(1, N_TICKS + 1):
        s.steam.valve_supply_pct = 0.0   # pin shut
        pkt = main.step_sim(DT)
        snap = snapshot(pkt, s, k)
        last = snap
        if cap5 is None and snap["p_mp"] <= 5.0:
            cap5 = snap
        if k % LOG_EVERY == 0:
            rows.append(snap)
    if rows[-1] is not last:
        rows.append(last)

    print("\n" + "-" * 104)
    print("  TRAJECTORY  --  MP HEADER DRAIN -> STRIPPER STARVATION")
    print("-" * 104)
    hdr = (f"  {'t[s]':>6} | {'P_MP':>7} | {'tsat':>6} | {'eta_T':>7} | {'TT004':>7} | "
           f"{'NH3%':>6} {'CO2%':>6} {'carb%':>6} | {'Urea%':>6}")
    print(hdr); print("  " + "-" * 100)
    for r in rows:
        mark = "  <- valve shut" if r["t"] == base["t"] else ""
        print(f"  {r['t']:>6} | {r['p_mp']:>7} | {r['t_sat']:>6} | {r['eta_T']:>7} | {r['t_bot']:>7} | "
              f"{r['nh3']:>6} {r['co2']:>6} {r['carb']:>6} | {r['urea']:>6}{mark}")

    if cap5 is not None:
        print(f"\n  @ P_MP=5 bar a (t={cap5['t']} s):  tsat={cap5['t_sat']} C  eta_T={cap5['eta_T']}  "
              f"TT-322004={cap5['t_bot']} C  carbamate(bot)={cap5['carb']}%")

    fin = last
    finite = all(isinstance(v, (int, float)) and (v == v) and abs(v) != float("inf")
                 for v in (fin["p_mp"], fin["t_sat"], fin["eta_T"], fin["t_bot"], fin["carb"]))
    print("\n  ASSERTIONS (final vs baseline):")
    a1 = fin["eta_T"] < base["eta_T"]
    a2 = fin["t_bot"] < base["t_bot"]
    a3 = fin["carb"]  > base["carb"]
    a4 = fin["p_mp"]  < 5.0 and finite
    print(f"   [{'PASS' if a1 else 'FAIL'}]  eta_T collapses : {base['eta_T']} -> {fin['eta_T']}")
    print(f"   [{'PASS' if a2 else 'FAIL'}]  TT-322004 falls : {base['t_bot']} -> {fin['t_bot']} C")
    print(f"   [{'PASS' if a3 else 'FAIL'}]  carbamate floods: {base['carb']} -> {fin['carb']} % (bottoms NH3+CO2)")
    print(f"   [{'PASS' if a4 else 'FAIL'}]  P_MP crashed <5 : {base['p_mp']} -> {fin['p_mp']} bar a "
          f"({'FINITE - asymptote survived' if finite else 'NON-FINITE - BROKE DOWN'})")
    assert a1, "FAIL: stripping efficiency did not collapse"
    assert a2, "FAIL: bottoms temperature did not fall"
    assert a3, "FAIL: unstripped carbamate did not flood the bottoms"
    assert a4, "FAIL: P_MP did not crash below 5 bar / state went non-finite"
    print("\n  RESULT: PASS -- header crashed to the tsat floor; stripper starved cleanly, state stayed finite.")
    print("=" * 104)


if __name__ == "__main__":
    main_run()
