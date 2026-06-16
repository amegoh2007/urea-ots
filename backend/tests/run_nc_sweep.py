r"""run_nc_sweep.py  --  LEVEL-5 AUDIT, PHASE 1:  Deep N/C Ratio Sweep.

Standalone stress test.  Initializes a fresh 100% baseline per setpoint, FORCES the fresh-feed
molar N/C ratio (NH3/CO2) across 1.6 -> 2.4 in 0.05 steps, settles 30 simulation-minutes of
thermodynamics, then logs the reactor / stripper / HPCC response.

  N/C forcing (bypasses the UI clamp + the per-tick recompute)
  ------------------------------------------------------------
  main.step_sim() recomputes s.ratio_PV every tick from the live pump flows (the fresh-feed
  N/C), then the reactor coupling consumes it:

      L_drive = reactor.L0_DES * (1.0 + REACT_NC_LOOP_GAIN * (s.ratio_PV / RATIO_PV_DES - 1.0))

  The {"type":"set","id":"ratio_set"} handler clamps any operator setpoint to [2.0, 5.0], which
  is ABOVE our 1.6 sweep floor -> the UI path cannot reach the test band.  We bypass it two ways:
    1. write s.ratio_SP / s.ratio_bal directly (cascade/telemetry coherence, no clamp);
    2. monkeypatch hpcc_322e002 (called AFTER the ratio_PV recompute, BEFORE the L_drive
       consumer) to RE-PIN s.ratio_PV = forced value every tick.  The reactor then sees the
       forced N/C and L_drive tracks it.

  Inventory-drain isolation
  -------------------------
  The seeded baseline runs pump B in MAN (86.2%); over 18 000 ticks the NH3 inventory drains and
  trip 21_2 (tank_level_frac < 0.05) latches ~tick 6500, killing the loop mid-settle.  To isolate
  the N/C *thermodynamic* response we pin s.tank_level_frac back to baseline after every tick
  (continuous-makeup assumption).  Single-tick drain from baseline never reaches the 0.05 floor,
  so 21_2 stays dormant for the full settle.

  Urea-content capture
  --------------------
  The reactor->stripper stream composition lives in the step_sim-local `streams` dict
  (streams["REACT_OVERFLOW"]), which is NOT in the returned telemetry packet.  We spy
  make_stream (global lookup -> picks up the wrapper) and grab mass_pct["Urea"] off the
  src="322R001" dst="322E001" stream.

  Tag-mapping notes (logged per the audit brief)
  ----------------------------------------------
    TT-322010   -> HPCC_322E002.TT_322010                (HPCC two-phase product outlet)
    TT-322005..8-> REACT_322R001.TT_322005..008          (reactor axial profile, top->bottom)
    TT-322009   -> REACT_322R001.TT_322009               (model = reactor OFF-GAS line temp;
                                                           brief labels it "overflow temp" -- the
                                                           true overflow temp is react["T_overflow"],
                                                           not exposed as a TT tag -> off-gas logged)
    TT-322014   -> STRIP_322E001.TT_322014               (model = 322R001 overflow FEED-in temp;
                                                           brief labels it "stripper gas-out" -- the
                                                           true top-gas-out is TT_322013, also logged)
    TT-322004   -> STRIP_322E001.TT_322004               (stripper bottoms, pre-flash)
    PT-329201   -> state.p_syn_bara                       (synthesis loop pressure, == scrub P_overflow)
    Urea %      -> streams["REACT_OVERFLOW"].mass_pct.Urea (spied)
    N/C act.    -> REACT_322R001.AT_322701               (reactor->stripper N/C; tracks feed N/C via
                                                          excess-NH3 overflow<->off-gas partition, Finding #1 fix)
    Biuret %    -> STRIP_322E001.bot_mass_pct.Biuret     (MODELED: xi_biu Arrhenius, NOT 'N/A')
    TDY-329125  -> SCRUB_322E003.ccw.TDY_329125          (MAPPED: TT_329125 - TIC-329005, live cascade)
    TT-328011   -> UNMAPPED: section 328 (Desorption/Hydrolysis: Desorber I/II 328C002/004,
                   Hydrolyzer 328C003, AW tank) is NOT implemented in the split-stack main.py, which
                   models only the 322 HP-synthesis loop + 329 steam/scrubber. No edit: mapping this
                   tag requires building the full reverse-urea-hydrolysis section (out of Phase-3 scope).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")   # Windows console cp1252

import main

DT          = 0.1
SETTLE_MIN  = 30.0
SETTLE_TICK = int(SETTLE_MIN * 60.0 / DT)          # 30 sim-min = 18 000 ticks
NC_START, NC_STOP, NC_STEP = 1.6, 2.4, 0.05
TT_328011_STATUS = "Unmapped"                       # no active physics mapped to this tag

# ---- forcing state shared with the monkeypatches (list holders -> visible inside closures) ----
_FORCED_NC = [None]      # current forced fresh-feed N/C; None = passthrough
_TANK_PIN  = [None]      # baseline tank_level_frac to re-pin each tick; None = passthrough
_CAP       = {}          # spy capture: latest REACT_OVERFLOW urea mass %

# ---- monkeypatch 1: re-pin forced N/C after the per-tick recompute, before the L_drive consumer ----
_orig_hpcc = main.hpcc_322e002
def _forced_hpcc(*a, **k):
    out = _orig_hpcc(*a, **k)
    if _FORCED_NC[0] is not None:
        main.state.ratio_PV = _FORCED_NC[0]
    return out
main.hpcc_322e002 = _forced_hpcc

# ---- monkeypatch 2: spy the reactor->stripper overflow stream for urea mass % ----
_orig_make_stream = main.make_stream
def _spy_make_stream(*a, **k):
    out = _orig_make_stream(*a, **k)
    src = a[4] if len(a) > 4 else k.get("src")
    dst = a[5] if len(a) > 5 else k.get("dst")
    if src == "322R001" and dst == "322E001":
        _CAP["urea_pct"] = out["mass_pct"].get("Urea", float("nan"))
    return out
main.make_stream = _spy_make_stream


def settle_one(nc_target):
    """Fresh 100% baseline, force N/C = nc_target, settle SETTLE_TICK ticks; return final packet."""
    main.state = main.State()
    s = main.state

    # bypass the [2.0, 5.0] UI clamp: write the setpoint/balance directly
    s.ratio_SP  = nc_target
    s.ratio_bal = nc_target
    s.ratio_PV  = nc_target

    _FORCED_NC[0] = nc_target
    _TANK_PIN[0]  = s.tank_level_frac          # baseline level captured at seed

    pkt = None
    for _ in range(SETTLE_TICK):
        pkt = main.step_sim(DT)
        s.tank_level_frac = _TANK_PIN[0]       # continuous-makeup pin -> trip 21_2 stays dormant

    _FORCED_NC[0] = None
    _TANK_PIN[0]  = None
    return pkt, s


def collect(pkt, s):
    react = pkt["REACT_322R001"]
    strip = pkt["STRIP_322E001"]
    hpcc  = pkt["HPCC_322E002"]
    ccw   = pkt["SCRUB_322E003"]["ccw"]
    return {
        "nc_act":   react["AT_322701"],
        "tt005":    react["TT_322005"],
        "tt006":    react["TT_322006"],
        "tt007":    react["TT_322007"],
        "tt008":    react["TT_322008"],
        "tt009":    react["TT_322009"],          # reactor off-gas line temp
        "tt010":    hpcc["TT_322010"],           # HPCC outlet
        "tt014":    strip["TT_322014"],          # stripper overflow feed-in
        "tt013":    strip["TT_322013"],          # stripper top gas-out (true)
        "tt004":    strip["TT_322004"],          # stripper bottoms
        "tt011":    pkt["SCRUB_322E003"]["TT_322011"],  # HP scrubber off-gas vent-top temp -> HV-322604
        "p329201":  round(s.p_syn_bara, 1),      # synthesis loop pressure
        "urea_pct": round(_CAP.get("urea_pct", float("nan")), 2),
        "biuret":   strip["bot_mass_pct"].get("Biuret", float("nan")),
        "tdy":      ccw["TDY_329125"],
        "trip21_2": s.trip_latched.get("21_2", False),
    }


def main_run():
    targets, x = [], NC_START
    while x <= NC_STOP + 1e-9:
        targets.append(round(x, 2))
        x += NC_STEP

    print("=" * 118)
    print("  LEVEL-5 AUDIT  /  PHASE 1  --  DEEP N/C RATIO SWEEP   "
          f"(force fresh-feed N/C {NC_START}->{NC_STOP} step {NC_STEP}; settle {SETTLE_MIN:.0f} sim-min/pt)")
    print("=" * 118)

    rows = []
    for nc in targets:
        pkt, s = settle_one(nc)
        r = collect(pkt, s)
        r["nc_set"] = nc
        rows.append(r)
        flag = "  <-- TRIP 21_2 LATCHED" if r["trip21_2"] else ""
        print(f"  settled N/C set={nc:<4}  act(AT-322701)={r['nc_act']:<6}  "
              f"urea={r['urea_pct']:<6}%  P={r['p329201']:<6}bar a{flag}")

    # ---------- Table A : reactor / stripper / HPCC temperatures + loop pressure ----------
    print("\n" + "-" * 118)
    print("  TABLE A  --  TEMPERATURE PROFILE (C) + LOOP PRESSURE (bar a)")
    print("-" * 118)
    hdrA = (f"  {'N/C':>5} | {'TT005':>6} {'TT006':>6} {'TT007':>6} {'TT008':>6} | "
            f"{'TT009':>6} | {'TT010':>6} | {'TT014':>6} {'TT013':>6} | {'TT004':>6} | {'TT011':>6} | {'PT329201':>8}")
    subA = (f"  {'set':>5} | {'Rtop':>6} {'R-B':>6} {'R-C':>6} {'Rbot':>6} | "
            f"{'offg':>6} | {'HPCC':>6} | {'sFeed':>6} {'sGout':>6} | {'sBot':>6} | {'scrOG':>6} | {'loopP':>8}")
    print(hdrA)
    print(subA)
    print("  " + "-" * 124)
    for r in rows:
        print(f"  {r['nc_set']:>5} | {r['tt005']:>6} {r['tt006']:>6} {r['tt007']:>6} {r['tt008']:>6} | "
              f"{r['tt009']:>6} | {r['tt010']:>6} | {r['tt014']:>6} {r['tt013']:>6} | {r['tt004']:>6} | "
              f"{r['tt011']:>6} | {r['p329201']:>8}")

    # ---------- Table B : reactor->stripper composition + diagnostics ----------
    print("\n" + "-" * 118)
    print("  TABLE B  --  REACTOR->STRIPPER STREAM COMPOSITION + DIAGNOSTICS")
    print("-" * 118)
    hdrB = (f"  {'N/C':>5} | {'AT-322701':>9} | {'Urea%':>7} | {'Biuret%':>8} | "
            f"{'TDY-329125':>10} | {'TT-328011':>10}")
    subB = (f"  {'set':>5} | {'N/C act':>9} | {'R->strp':>7} | {'->LV501A':>8} | "
            f"{'ccw cond':>10} | {'(status)':>10}")
    print(hdrB)
    print(subB)
    print("  " + "-" * 114)
    for r in rows:
        print(f"  {r['nc_set']:>5} | {r['nc_act']:>9} | {r['urea_pct']:>7} | {r['biuret']:>8} | "
              f"{r['tdy']:>10} | {TT_328011_STATUS:>10}")

    print("\n  NOTES:")
    print("   - TT-322009 = reactor OFF-GAS line temp (model); true overflow temp react['T_overflow'] "
          "is not a TT tag.")
    print("   - TT-322014 = stripper overflow FEED-in temp (model); true top gas-out = TT-322013 "
          "(both columns shown).")
    print("   - Biuret IS modeled (stripper xi_biu, Arrhenius Ea=85 kJ/mol) -> real % logged, not 'N/A'.")
    print("   - TDY-329125 IS mapped (CCW cond. quality = TT-329125 - TIC-329005, PT-329201 cascade).")
    print("   - TT-322011 (scrOG) = HP scrubber off-gas vent-top temp -> HV-322604; LIVE off excess-NH3 loop "
          "slip: RISES w/ N/C (CO2-limited -> unabsorbed NH3 vents). k=120 C/(N/C) * (AT-322701 - N/C_des), "
          "114.0 C bit-exact at design.")
    print(f"   - TT-328011 = '{TT_328011_STATUS}': section 328 (Desorption/Hydrolysis) not implemented "
          "in split-stack main.py (322 synthesis + 329 only). Out of Phase-3 scope -> no map.")
    print("   - tank_level_frac pinned each tick (continuous-makeup) to keep trip 21_2 dormant over "
          "the 18k-tick settle.")
    print("=" * 118)


if __name__ == "__main__":
    main_run()
