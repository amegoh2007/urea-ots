# run_hp_validation.py — Full HP Loop Certification (temporary validation script)
#
# Phase 1: 100% steady-state HMB audit (mass flows, T, P for 322R001 / 322E001 /
#          322E002 / 322E003) + synthesis-loop envelope mass-in == mass-out check.
# Phase 2: 70% load turndown transient — step F_CO2_raw to 70%, NH3 follows via the
#          ratio cascade (SIC-321951 in CAS), 30 sim-min Euler integration, 5-min log.

import main as m

DT = 1.0          # Euler step (s)


def run(minutes: float, log_every_min: float = None, log_fn=None):
    """Step the engine `minutes` of sim time; optionally call log_fn every log_every_min."""
    pkt = None
    n = int(minutes * 60.0 / DT)
    log_n = int(log_every_min * 60.0 / DT) if log_every_min else None
    for i in range(1, n + 1):
        pkt = m.step_sim(DT)
        if log_n and (i % log_n == 0) and log_fn:
            log_fn(i * DT / 60.0, pkt)
    return pkt


def hmb_table(pkt):
    st = pkt["STREAMS"]
    R  = pkt["REACT_322R001"];  S = pkt["STRIP_322E001"]
    H  = pkt["HPCC_322E002"];   C = pkt["SCRUB_322E003"]

    rows = [
        # (equipment, stream, t/h, T(C), P(bara))
        ("322R001 Reactor",  "feed (HPCC 2-ph product)", st["HPCC_PROD"]["mass_th"],
                              st["HPCC_PROD"]["T_C"],       st["HPCC_PROD"]["P_bara"]),
        ("",                 "overflow -> 322E001",       st["REACT_OVERFLOW"]["mass_th"],
                              st["REACT_OVERFLOW"]["T_C"],  R["P_bara"]),
        ("",                 "off-gas  -> 322E003",       st["REACT_OFFGAS"]["mass_th"],
                              st["REACT_OFFGAS"]["T_C"],    R["P_offgas"]),
        ("322E001 Stripper", "CO2 strip gas in",          st["CO2_FEED"]["mass_th"],
                              st["CO2_FEED"]["T_C"],        st["CO2_FEED"]["P_bara"]),
        ("",                 "top gas  -> 322E002",       S["top_th"], S["TT_322013"],
                              st["STRIP_TOP"]["P_bara"]),
        ("",                 "bottom soln -> LV-322501",  S["bot_th"], S["TT_322004"],
                              st["STRIP_BOT"]["P_bara"]),
        ("",                 "bottom drain (letdown)",    S["drain_th"], S["TT_323001"], "-"),
        ("322E002 HPCC",     "ejector carbamate in",      st["EJ_DISCH"]["mass_th"],
                              st["EJ_DISCH"]["T_C"],        st["EJ_DISCH"]["P_bara"]),
        ("",                 "2-ph product -> 322R001",   round(H["gas_th"] + H["liq_th"], 3),
                              H["TT_322010"],               H["P_bara"]),
        ("",                 "LP steam raised (shell)",   round(H["steam"]["kgh"] / 1000.0, 3),
                              H["steam"]["TI_shell"],       H["steam"]["P_bara"]),
        ("322E003 Scrubber", "weak carbamate wash in",    C["carb_th"], "-", "-"),
        ("",                 "overflow -> 322F001",       C["ov_th"], C["TT_322002"],
                              C["P_overflow"]),
        ("",                 "off-gas vent (HV-322604)",  C["og_lp_th"], C["TT_322011_lp"],
                              st["SCRUB_OFFGAS_LP"]["P_bara"]),
    ]
    print(f"{'Equipment':<18} {'Stream':<28} {'t/h':>9} {'T (C)':>8} {'P (bara)':>9}")
    print("-" * 78)
    for eq, name, th, T, P in rows:
        print(f"{eq:<18} {name:<28} {th:>9} {str(T):>8} {str(P):>9}")
    print("-" * 78)


def envelope_balance(pkt):
    """Synthesis-loop envelope: internal recycles cancel; boundary streams only.
    IN  = CO2 feed + HP NH3 motive + weak-carbamate wash (323P001)
    OUT = stripper bottom letdown (LV-322501) + LP off-gas vent (HV-322604)"""
    st = pkt["STREAMS"]; S = pkt["STRIP_322E001"]; C = pkt["SCRUB_322E003"]
    m_in  = st["CO2_FEED"]["mass_th"] + st["HP_DISCH"]["mass_th"] + C["carb_th"]
    m_out = S["drain_th"] + C["og_lp_th"]
    err   = m_in - m_out
    print(f"  Mass IN  : CO2 {st['CO2_FEED']['mass_th']:8.3f} + NH3 motive "
          f"{st['HP_DISCH']['mass_th']:7.3f} + carb wash {C['carb_th']:6.3f} "
          f"= {m_in:9.3f} t/h")
    print(f"  Mass OUT : strip bottoms {S['drain_th']:8.3f} + off-gas vent "
          f"{C['og_lp_th']:6.3f}            = {m_out:9.3f} t/h")
    print(f"  Closure  : IN - OUT = {err:+.3f} t/h  ({err / m_in * 100.0:+.3f} % of IN)")
    return err


def ts_header():
    print(f"{'t (min)':>8} {'Load %':>7} {'PT-329201':>10} {'TT-322004':>10} "
          f"{'TT-322010':>10} {'TT-322002':>10} {'NH3 t/h':>8} {'N/C PV':>7}")
    print("-" * 78)


def ts_row(t_min, pkt):
    C = pkt["SCRUB_322E003"]; S = pkt["STRIP_322E001"]; H = pkt["HPCC_322E002"]
    print(f"{t_min:>8.0f} {pkt['CO2_FEED']['Load']:>7.1f} {C['P_overflow']:>10.1f} "
          f"{S['TT_322004']:>10.1f} {H['TT_322010']:>10.1f} {C['TT_322002']:>10.1f} "
          f"{pkt['FI_321401']:>8.2f} {pkt['ratio']['PV']:>7.3f}")


# =====================  PHASE 1 — 100% STEADY-STATE HMB AUDIT  =====================
print("=" * 78)
print("PHASE 1 — 100% DESIGN LOAD STEADY-STATE HMB AUDIT")
print("=" * 78)

# NH3 pump B on cascade: SIC-321951 tracks the ratio-block flow demand (open_cas).
m.state.SIC_321951.set_mode("CAS")

pkt_a = run(15.0)                      # settle
pkt_b = run(15.0)                      # confirm window

# steady-state confirmation: key PVs frozen between the two 15-min windows
drift = {
    "PT-329201 (bar)":  pkt_b["SCRUB_322E003"]["P_overflow"] - pkt_a["SCRUB_322E003"]["P_overflow"],
    "TT-322004 (C)":    pkt_b["STRIP_322E001"]["TT_322004"]  - pkt_a["STRIP_322E001"]["TT_322004"],
    "TT-322010 (C)":    pkt_b["HPCC_322E002"]["TT_322010"]   - pkt_a["HPCC_322E002"]["TT_322010"],
    "TT-322002 (C)":    pkt_b["SCRUB_322E003"]["TT_322002"]  - pkt_a["SCRUB_322E003"]["TT_322002"],
    "NH3 flow (t/h)":   pkt_b["FI_321401"]                   - pkt_a["FI_321401"],
}
print(f"\nSteady state after 30 sim-min  (Load = {pkt_b['CO2_FEED']['Load']:.1f} %, "
      f"N/C = {pkt_b['ratio']['PV']:.3f})")
print("15-min drift check: " + ", ".join(f"{k} {v:+.2f}" for k, v in drift.items()))
print()
hmb_table(pkt_b)
print("\nSynthesis-loop envelope mass balance (boundary streams):")
err = envelope_balance(pkt_b)
verdict = "PASS" if abs(err) < 0.01 * (pkt_b['CO2_FEED']['FY_322403']) else "REVIEW"
print(f"  Verdict  : {verdict}")

# =====================  PHASE 2 — 70% LOAD TURNDOWN TRANSIENT  =====================
print()
print("=" * 78)
print("PHASE 2 — 70% LOAD TURNDOWN TRANSIENT (30 sim-min, controllers AUTO/CAS)")
print("=" * 78)

m.state.F_CO2_raw_th = 0.70 * 54.618   # step BL CO2 feed to 70% of design
print(f"t=0: F_CO2_raw stepped {54.618:.3f} -> {m.state.F_CO2_raw_th:.3f} t/h "
      f"(NH3 follows via ratio cascade, SIC-321951 CAS)\n")

ts_header()
ts_row(0, pkt_b)                       # pre-step reference (100% steady state)
pkt_f = run(30.0, log_every_min=5.0, log_fn=ts_row)

print("\nFinal 70% state:")
print(f"  Load {pkt_f['CO2_FEED']['Load']:.1f} %   N/C PV {pkt_f['ratio']['PV']:.3f} "
      f"(SP {pkt_f['ratio']['SP']:.3f})   vent_frac {pkt_f['SCRUB_322E003']['vent_frac']:.3f}   "
      f"rho_cond {pkt_f['SCRUB_322E003']['ccw']['rho_cond']:.3f}")
print(f"  Reactor level {pkt_f['REACT_322R001']['LT_322504']:.1f} %   "
      f"HPCC level {pkt_f['HPCC_322E002']['LT_322E002']:.1f} %   "
      f"Stripper level {pkt_f['STRIP_322E001']['LI_322501']:.1f} %")
print(f"  X_conv {pkt_f['REACT_322R001']['X_conv']:.2f} %   "
      f"HPCC duty {pkt_f['HPCC_322E002']['steam']['duty_kW']:.0f} kW   "
      f"Scrub CCW duty {pkt_f['SCRUB_322E003']['ccw']['Q_ccw_kW']:.0f} kW")
print("\nEnvelope mass balance at 70%:")
envelope_balance(pkt_f)
