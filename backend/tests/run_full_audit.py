r"""run_full_audit.py  --  LEVEL-5 EQUATION AUDIT  /  PHASE 2:  Mandated 5-category deep tests.

Standalone stress campaign.  Each point: fresh 100 % baseline -> FORCE one manipulated variable
-> settle SETTLE_MIN sim-minutes -> log the physically-relevant response set.  Per-test physics
verdict (sign / monotonicity / balance) is computed in-script so the artifact self-documents.

  MANDATED CATEGORIES
  -------------------
   1  feed composition ratio (fresh-feed N/C) + feed temperature (NH3 tank T)
   2  valve openings  (HV-322605 reactor overflow, HV-322604 scrubber vent,
                        PV-322203 CO2 vent-min, LV-322501 stripper-bottoms drain)
   3  HP steam (MP header) + LP steam pressures
   4  carbamate recycle flow (323P001 A/B weak-carbamate wash to 322E003)
   5  322F001 HP ejector opening (HV-322602 / HIC-322602)

  FORCING (bypass UI clamps / per-tick recompute; mirrors run_nc_sweep.py)
  -----------------------------------------------------------------------
   * N/C        : monkeypatch hpcc_322e002 (called AFTER ratio_PV recompute, BEFORE the L_drive
                  consumer) to RE-PIN main.state.ratio_PV = forced value every tick.
   * tank T     : pin s.tank_T_C each tick (overrides the 321D003 energy-balance update).
   * P_MP/P_LP  : pin s.steam.P_MP / P_LP each tick (overrides step_steam) -> isolates the
                  saturated-shell-T -> process response.
   * HV valves  : set the hand-valve state (s.HIC_322605/604/602/322203) each tick.
   * LV-322501  : LIC-322501 -> MAN, pin lic["op"] each tick.
   * carb recyc : scale the module global main.SCRUB_CARB_KMOLH_DES (323P001 wash vector) by a
                  factor for the settle, then restore.
   * tank level : pinned to baseline every tick (continuous-makeup) so trip 21_2 stays dormant.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

import main

DT          = 0.1
SETTLE_MIN  = 30.0
SETTLE_TICK = int(SETTLE_MIN * 60.0 / DT)           # 30 sim-min = 18 000 ticks

# ---- shared forcing holders (visible inside the global monkeypatch closures) ----
_FORCED_NC = [None]      # current forced fresh-feed N/C; None = passthrough
_CAP       = {}          # spy: latest REACT_OVERFLOW urea mass %

_orig_hpcc = main.hpcc_322e002
def _forced_hpcc(*a, **k):
    out = _orig_hpcc(*a, **k)
    if _FORCED_NC[0] is not None:
        main.state.ratio_PV = _FORCED_NC[0]
    return out
main.hpcc_322e002 = _forced_hpcc

_orig_make_stream = main.make_stream
def _spy_make_stream(*a, **k):
    out = _orig_make_stream(*a, **k)
    src = a[4] if len(a) > 4 else k.get("src")
    dst = a[5] if len(a) > 5 else k.get("dst")
    if src == "322R001" and dst == "322E001":
        _CAP["urea_pct"] = out["mass_pct"].get("Urea", float("nan"))
    return out
main.make_stream = _spy_make_stream


def settle(pre_fn=None, tick_fn=None):
    """Fresh baseline; pre_fn(s) once after seed; tick_fn(s) every tick after step_sim."""
    main.state = main.State()
    s = main.state
    tank_pin = s.tank_level_frac
    if pre_fn:
        pre_fn(s)
    pkt = None
    for _ in range(SETTLE_TICK):
        pkt = main.step_sim(DT)
        s.tank_level_frac = tank_pin            # continuous-makeup -> trip 21_2 dormant
        if tick_fn:
            tick_fn(s)
    return pkt, s


def grab(pkt, s):
    R = pkt["REACT_322R001"]; ST = pkt["STRIP_322E001"]; H = pkt["HPCC_322E002"]
    SC = pkt["SCRUB_322E003"]; CW = SC["ccw"]; EJ = pkt["EJ_322F001"]
    CO = pkt["CO2_FEED"]; STM = pkt["STEAM_SYSTEM"]
    return {
        # reactor
        "nc_act": R["AT_322701"], "Xconv": R["X_conv"], "urea": round(_CAP.get("urea_pct", float("nan")), 2),
        "Lfeed": R["L_feed"], "Wfeed": R["W_feed"], "xi_urea": R["xi_urea"],
        "tt005": R["TT_322005"], "tt008": R["TT_322008"], "tt009": R["TT_322009"],
        "LT504": R["LT_322504"], "hic605": R["HIC_322605"], "Preact": R["P_bara"],
        # stripper
        "tt004": ST["TT_322004"], "tt013": ST["TT_322013"], "tt014": ST["TT_322014"],
        "etaT": ST["eta_T"], "xi_hyd": ST["xi_hyd"], "xi_biu": ST["xi_biu"],
        "Lstr": ST["L_strip"], "Wstr": ST["W_strip"], "LI501": ST["LI_322501"],
        "LV501": ST["LV_322501"], "drain": ST["drain_th"], "Tshell_mp": ST["steam"]["TI_shell"],
        "biuret": ST["bot_mass_pct"].get("Biuret", float("nan")),
        # hpcc
        "tt010": H["TT_322010"], "hpcc_duty": H["steam"]["duty_kW"], "hpcc_lp_kgh": H["steam"]["kgh"],
        "LT002": H["LT_322E002"], "Tshell_lp": H["steam"]["TI_shell"],
        # scrubber
        "tt002": SC["TT_322002"], "tt011": SC["TT_322011"], "vent_frac": SC["vent_frac"],
        "Povf": SC["P_overflow"], "ov_th": SC["ov_th"], "off_th": SC["off_th"],
        "co2abs": CW["co2_abs"], "qcarb": CW["Q_carb_kW"], "qccw": CW["Q_ccw_kW"],
        "rho_cond": CW["rho_cond"], "tt329125": CW["TT_329125"], "tdy": CW["TDY_329125"],
        # ejector
        "ej_mu": EJ["mu"], "ej_suc": EJ["suction_kgh"], "ej_mot": EJ["motive_kgh"],
        "ej_T": EJ["TT_322012"], "ej_P": EJ["PI_disch"], "ej_tot_th": EJ["total_th"],
        # co2 feed / steam / loop
        "co2_fy": CO["FY_322403"], "pv203": CO["PV_322203"], "pic203": CO["PIC_322203"],
        "Pmp": STM["MP"]["P_bara"], "Tmp": STM["MP"]["TI_sat"],
        "Plp": STM["LP"]["P_bara"], "Tlp": STM["LP"]["TI_sat"],
        "Psyn": round(s.p_syn_bara, 1),
        "PDY_A": pkt["PDY_321203"], "PDY_B": pkt["PDY_321204"],
        "PY": pkt["PY_321201"], "TI020": pkt["TI_321020"], "FI401": pkt["FI_321401"],
        "trip": s.trip_latched.get("21_2", False),
    }


def hdr(title):
    print("\n" + "=" * 120)
    print("  " + title)
    print("=" * 120)


def verdict(label, ok, detail):
    print(f"   [{'PASS' if ok else 'CHECK'}] {label}: {detail}")


def mono(vals, inc=True):
    d = [b - a for a, b in zip(vals, vals[1:])]
    return all(x >= -1e-6 for x in d) if inc else all(x <= 1e-6 for x in d)


# =====================================================================================
def t1_feed():
    hdr("TEST 1  --  FEED COMPOSITION (fresh-feed N/C) + FEED TEMPERATURE (NH3 tank T)")
    # 1a  N/C ratio
    ncs = [1.8, 2.0231315310702604, 2.2, 2.5, 2.8]
    print("\n  1a  fresh-feed N/C  (design PV = 2.0231)")
    print(f"   {'N/C':>7} | {'AT701':>6} {'Xconv%':>7} {'urea%':>6} | {'Lfeed':>6} {'Wfeed':>7} | "
          f"{'tt010':>6} {'tt004':>6} | {'Psyn':>6} {'tt011':>6}")
    rows = []
    for nc in ncs:
        def pre(s, nc=nc):
            s.ratio_SP = nc; s.ratio_bal = nc; s.ratio_PV = nc
        _FORCED_NC[0] = nc
        pkt, s = settle(pre_fn=pre); _FORCED_NC[0] = None
        r = grab(pkt, s); r["x"] = nc; rows.append(r)
        print(f"   {nc:>7.3f} | {r['nc_act']:>6} {r['Xconv']:>7} {r['urea']:>6} | {r['Lfeed']:>6} {r['Wfeed']:>7} | "
              f"{r['tt010']:>6} {r['tt004']:>6} | {r['Psyn']:>6} {r['tt011']:>6}")
    verdict("urea% rises with N/C", mono([r["urea"] for r in rows]), f"{rows[0]['urea']}->{rows[-1]['urea']}")
    verdict("AT-322701 rises with feed N/C (Finding #1)", mono([r["nc_act"] for r in rows]),
            f"{rows[0]['nc_act']}->{rows[-1]['nc_act']}")
    verdict("loop P falls as N/C rises (less free CO2)", mono([r["Psyn"] for r in rows], inc=False),
            f"{rows[0]['Psyn']}->{rows[-1]['Psyn']}")
    verdict("TT-322011 off-gas rises with N/C (NH3 slip)", mono([r["tt011"] for r in rows]),
            f"{rows[0]['tt011']}->{rows[-1]['tt011']}")

    # 1b  NH3 feed temperature (tank T)  -> cavitation margin + discharge T
    temps = [10.0, 20.0, 25.0, 30.0, 40.0]
    print("\n  1b  NH3 feed temperature  (design 25 C; pins s.tank_T_C)")
    print(f"   {'T_feed':>7} | {'PY_sat':>6} {'PDY_A':>6} {'PDY_B':>6} | {'TI020':>6} {'FI401':>6} | "
          f"{'urea%':>6} {'Psyn':>6}")
    rows2 = []
    for T in temps:
        def tick(s, T=T):
            s.tank_T_C = T
        pkt, s = settle(tick_fn=tick)
        r = grab(pkt, s); r["x"] = T; rows2.append(r)
        print(f"   {T:>7.1f} | {r['PY']:>6} {r['PDY_A']:>6} {r['PDY_B']:>6} | {r['TI020']:>6} {r['FI401']:>6} | "
              f"{r['urea']:>6} {r['Psyn']:>6}")
    verdict("NH3 sat vapour P rises with feed T (Antoine)", mono([r["PY"] for r in rows2]),
            f"{rows2[0]['PY']}->{rows2[-1]['PY']}")
    verdict("sub-cooling margin PDY falls as feed T rises", mono([r["PDY_A"] for r in rows2], inc=False),
            f"{rows2[0]['PDY_A']}->{rows2[-1]['PDY_A']}")
    print("   NOTE: CO2 feed T (CO2_T_FEED_C=120 C) is display-only (TI-322017); reactor T is design-pinned"
          " -> CO2 sensible enthalpy not in the reduced-model heat balance (known simplification, not a bug).")


# =====================================================================================
def t2_valves():
    hdr("TEST 2  --  VALVE OPENINGS  (HV-322605 / HV-322604 / PV-322203 / LV-322501)")

    # 2a HV-322605 reactor overflow (phi)
    print("\n  2a  HV-322605 reactor-overflow valve  (design 60 %)")
    print(f"   {'HIC605':>7} | {'LT504':>6} {'ov_th':>6} | {'Xconv%':>7} {'urea%':>6} {'AT701':>6} | {'Psyn':>6}")
    rows = []
    for v in [30.0, 45.0, 60.0, 75.0, 90.0]:
        def tick(s, v=v): s.HIC_322605 = v
        pkt, s = settle(tick_fn=tick); r = grab(pkt, s); r["x"] = v; rows.append(r)
        print(f"   {v:>7.1f} | {r['LT504']:>6} {r['ov_th']:>6} | {r['Xconv']:>7} {r['urea']:>6} {r['nc_act']:>6} | {r['Psyn']:>6}")
    verdict("LT-322504 level falls as overflow valve opens", mono([r["LT504"] for r in rows], inc=False),
            f"{rows[0]['LT504']}->{rows[-1]['LT504']}")
    verdict("overflow mass rises with valve opening", mono([r["ov_th"] for r in rows]),
            f"{rows[0]['ov_th']}->{rows[-1]['ov_th']}")

    # 2b HV-322604 scrubber off-gas vent
    print("\n  2b  HV-322604 scrubber off-gas vent  (design 50 %)")
    print(f"   {'HIC604':>7} | {'vent_f':>6} {'Psyn':>6} {'Povf':>6} | {'off_th':>6} {'tt011':>6}")
    rows = []
    for v in [25.0, 40.0, 50.0, 65.0, 80.0]:
        def tick(s, v=v): s.HIC_322604 = v
        pkt, s = settle(tick_fn=tick); r = grab(pkt, s); r["x"] = v; rows.append(r)
        print(f"   {v:>7.1f} | {r['vent_frac']:>6} {r['Psyn']:>6} {r['Povf']:>6} | {r['off_th']:>6} {r['tt011']:>6}")
    verdict("vent capacity rises with valve opening", mono([r["vent_frac"] for r in rows]),
            f"{rows[0]['vent_frac']}->{rows[-1]['vent_frac']}")
    verdict("PT-329201 falls as vent opens (less back-pressure deficit)",
            mono([r["Psyn"] for r in rows], inc=False), f"{rows[0]['Psyn']}->{rows[-1]['Psyn']}")

    # 2c PV-322203 CO2 vent minimum opening
    print("\n  2c  PV-322203 CO2 vent minimum opening  (HIC-322203, design 0 %)")
    print(f"   {'HIC203':>7} | {'pv203':>6} {'co2_fy':>6} {'pic203':>7} | {'Xconv%':>7} {'urea%':>6}")
    rows = []
    for v in [0.0, 10.0, 20.0, 30.0]:
        def tick(s, v=v): s.HIC_322203 = v
        pkt, s = settle(tick_fn=tick); r = grab(pkt, s); r["x"] = v; rows.append(r)
        print(f"   {v:>7.1f} | {r['pv203']:>6} {r['co2_fy']:>6} {r['pic203']:>7} | {r['Xconv']:>7} {r['urea']:>6}")
    verdict("CO2 feed (FY-322403) falls as vent min opens", mono([r["co2_fy"] for r in rows], inc=False),
            f"{rows[0]['co2_fy']}->{rows[-1]['co2_fy']}")

    # 2d LV-322501 stripper-bottoms drain
    print("\n  2d  LV-322501 stripper-bottoms drain  (LIC-322501 MAN; design op 82 %)")
    print(f"   {'LV op':>7} | {'LI501':>6} {'drain':>6} | {'tt004':>6}")
    rows = []
    for v in [50.0, 65.0, 82.0, 100.0]:
        def pre(s, v=v):
            s.LIC_322501["mode"] = "MAN"; s.LIC_322501["op"] = v
        def tick(s, v=v):
            s.LIC_322501["op"] = v
        pkt, s = settle(pre_fn=pre, tick_fn=tick); r = grab(pkt, s); r["x"] = v; rows.append(r)
        print(f"   {v:>7.1f} | {r['LI501']:>6} {r['drain']:>6} | {r['tt004']:>6}")
    verdict("LT-322501 level falls as drain valve opens", mono([r["LI501"] for r in rows], inc=False),
            f"{rows[0]['LI501']}->{rows[-1]['LI501']}")
    verdict("drain flow rises with valve opening", mono([r["drain"] for r in rows]),
            f"{rows[0]['drain']}->{rows[-1]['drain']}")


# =====================================================================================
def t3_steam():
    hdr("TEST 3  --  HP STEAM (MP header) + LP STEAM PRESSURES")
    # 3a MP (stripper reboiler)
    print("\n  3a  MP header pressure  (HP steam to 329D005 stripper reboiler; design 19.7 bar a)")
    print(f"   {'P_MP':>7} | {'Tsat':>6} {'etaT':>6} {'xi_hyd':>7} {'xi_biu':>6} | {'tt004':>6} {'urea%':>6}")
    rows = []
    for P in [16.0, 18.0, 19.7, 22.0, 24.0]:
        def tick(s, P=P): s.steam.P_MP = P
        pkt, s = settle(tick_fn=tick); r = grab(pkt, s); r["x"] = P; rows.append(r)
        print(f"   {P:>7.1f} | {r['Tmp']:>6} {r['etaT']:>6} {r['xi_hyd']:>7} {r['xi_biu']:>6} | {r['tt004']:>6} {r['urea']:>6}")
    verdict("stripper eta_T rises with MP pressure (hotter steam)", mono([r["etaT"] for r in rows]),
            f"{rows[0]['etaT']}->{rows[-1]['etaT']}")
    verdict("urea hydrolysis xi_hyd rises with steam T", mono([r["xi_hyd"] for r in rows]),
            f"{rows[0]['xi_hyd']}->{rows[-1]['xi_hyd']}")

    # 3b LP (HPCC shell)
    print("\n  3b  LP header pressure  (HPCC 322E002 shell sat-T; design 4.4 bar a)")
    print(f"   {'P_LP':>7} | {'Tshell':>6} {'tt010':>6} {'hpcc_duty':>9} | {'Psyn':>6}")
    rows = []
    for P in [3.5, 4.0, 4.4, 5.5, 6.5]:
        def tick(s, P=P): s.steam.P_LP = P
        pkt, s = settle(tick_fn=tick); r = grab(pkt, s); r["x"] = P; rows.append(r)
        print(f"   {P:>7.1f} | {r['Tshell_lp']:>6} {r['tt010']:>6} {r['hpcc_duty']:>9} | {r['Psyn']:>6}")
    verdict("HPCC shell sat-T rises with LP pressure (Antoine)", mono([r["Tshell_lp"] for r in rows]),
            f"{rows[0]['Tshell_lp']}->{rows[-1]['Tshell_lp']}")
    verdict("HPCC product TT-322010 rises with shell T (less sub-cool)", mono([r["tt010"] for r in rows]),
            f"{rows[0]['tt010']}->{rows[-1]['tt010']}")


# =====================================================================================
def t4_carb():
    hdr("TEST 4  --  CARBAMATE RECYCLE FLOW  (323P001 A/B weak-carbamate wash to 322E003)")
    base = dict(main.SCRUB_CARB_KMOLH_DES)
    print("\n   scale factor on the 323P001 wash vector  (design = 1.0, 36915 kg/h)")
    print(f"   {'factor':>7} | {'co2abs':>6} {'qcarb':>6} {'ov_th':>6} | {'AT701':>6} {'urea%':>6} {'Psyn':>6} {'tt002':>6}")
    rows = []
    for f in [0.6, 0.8, 1.0, 1.2, 1.4]:
        def pre(s, f=f):
            main.SCRUB_CARB_KMOLH_DES = {k: v * f for k, v in base.items()}
        pkt, s = settle(pre_fn=pre)
        main.SCRUB_CARB_KMOLH_DES = dict(base)
        r = grab(pkt, s); r["x"] = f; rows.append(r)
        print(f"   {f:>7.2f} | {r['co2abs']:>6} {r['qcarb']:>6} {r['ov_th']:>6} | {r['nc_act']:>6} {r['urea']:>6} {r['Psyn']:>6} {r['tt002']:>6}")
    main.SCRUB_CARB_KMOLH_DES = dict(base)
    verdict("scrubber overflow mass rises with wash flow", mono([r["ov_th"] for r in rows]),
            f"{rows[0]['ov_th']}->{rows[-1]['ov_th']}")
    verdict("CO2 absorbed into carbamate rises with wash flow", mono([r["co2abs"] for r in rows]),
            f"{rows[0]['co2abs']}->{rows[-1]['co2abs']}")


# =====================================================================================
def t5_ejector():
    hdr("TEST 5  --  322F001 HP EJECTOR OPENING  (HV-322602 / HIC-322602)")
    print("\n   HV-322602 spindle opening  (design 74 %)")
    print(f"   {'HIC602':>7} | {'mu':>7} {'ej_suc':>8} {'ej_T':>6} {'ej_P':>6} | {'tt010':>6} {'LT002':>6} {'Psyn':>6}")
    rows = []
    for v in [55.0, 65.0, 74.0, 85.0, 95.0]:
        def tick(s, v=v): s.HIC_322602 = v
        pkt, s = settle(tick_fn=tick); r = grab(pkt, s); r["x"] = v; rows.append(r)
        print(f"   {v:>7.1f} | {r['ej_mu']:>7} {r['ej_suc']:>8} {r['ej_T']:>6} {r['ej_P']:>6} | {r['tt010']:>6} {r['LT002']:>6} {r['Psyn']:>6}")
    verdict("entrainment mu falls as spindle opens (EJ_OPEN_DES/open)", mono([r["ej_mu"] for r in rows], inc=False),
            f"{rows[0]['ej_mu']}->{rows[-1]['ej_mu']}")
    verdict("carbamate suction falls as mu falls", mono([r["ej_suc"] for r in rows], inc=False),
            f"{rows[0]['ej_suc']}->{rows[-1]['ej_suc']}")


if __name__ == "__main__":
    print("#" * 120)
    print(f"#  LEVEL-5 EQUATION AUDIT / PHASE 2  --  MANDATED 5-CATEGORY DEEP TESTS"
          f"   (settle {SETTLE_MIN:.0f} sim-min/pt, dt={DT}s)")
    print("#" * 120)
    t1_feed()
    t2_valves()
    t3_steam()
    t4_carb()
    t5_ejector()
    print("\n" + "#" * 120)
    print("#  END OF CAMPAIGN")
    print("#" * 120)
