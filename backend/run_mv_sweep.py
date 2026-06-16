"""run_mv_sweep.py  --  TEMPORARY Level-4 Valve-Authority & Process-Response audit.

For each manipulated variable (MV) we:
  1. re-seed a clean 100 %-design steady state (main.State() — HPCC_UA already pinned at import),
  2. settle to baseline, snapshot the primary downstream variables,
  3. drive the MV to MANUAL extreme positions, settle, snapshot again,
  4. report a Cause & Effect matrix and flag Dead Valves / physics violations.

Local-only tick variables (drain_kgh, motive_nh3_kgh, hv604.T_out) are captured by
monkey-patching the module-global functions that step_sim() calls (same hook pattern
_pin_hpcc_ua uses for hpcc_322e002).  drain_kgh is recomputed analytically from the
documented orifice law for the matrix number.
"""
import sys
import math
import main

sys.stdout.reconfigure(encoding="utf-8")   # Windows console is cp1252 -> allow Δ / em-dash

DT      = 0.1
N_FAST  = 3000     # 5  sim-min  — level / ratio (seconds-fast responses)
N_SLOW  = 9000     # 15 sim-min  — p_syn dynamics (tau = SYN_P_TAU_MIN = 4 min -> ~3.75 tau)

# ---------------------------------------------------------------- spies (local-var capture)
_rec = {}
_orig_ej = main.ejector_322f001
_orig_hv = main.hv_322604

def _ej_spy(*a, **k):
    r = _orig_ej(*a, **k)
    _rec["motive_kgh"] = a[0]
    _rec["ej"] = r
    return r

def _hv_spy(*a, **k):
    r = _orig_hv(*a, **k)
    _rec["hv"] = r
    return r

main.ejector_322f001 = _ej_spy
main.hv_322604       = _hv_spy

# ---------------------------------------------------------------- helpers
def fresh():
    main.state = main.State()

def settle(n):
    pkt = None
    for _ in range(n):
        pkt = main.step_sim(DT)
    return pkt

def _drain_kgh(lv_open, p_syn):
    """STRIP_BOT_DES * (Op/Op_des) * sqrt(dP/dP_des)   (f_drain=1: T_bot above 132.7 C)."""
    dP = max(p_syn - main.LV322501_P_DOWN_BARA, 0.0)
    return (main.STRIP_BOT_DES_KGH * (lv_open / main.LV322501_OPEN_DES)
            * math.sqrt(dP / max(main.SYN_P_DES_BARA - main.LV322501_P_DOWN_BARA, 1e-6)))

def snap(pkt):
    st = main.state
    lv_open = max(0.0, min(100.0, st.LIC_322501["op"]))
    ej = _rec.get("ej", {})
    hv = _rec.get("hv", {})
    return {
        "strip_level":  round(st.strip_level, 2),                 # LT-322501 (%)
        "lv_open":      round(lv_open, 1),                        # LV-322501 opening (%)
        "drain_kgh":    round(_drain_kgh(lv_open, st.p_syn_bara), 1),
        "p_syn":        round(st.p_syn_bara, 2),                  # PT-329201 (bar a)
        "ratio_PV":     round(st.ratio_PV, 4),                    # feed molar N/C
        "ccw_tph":      round(st.FIC_329409["pv"], 1),            # CCW circulation (t/h)
        "T_overflow":   pkt["EJ_322F001"]["TI_322002"],           # TT-322002 scrubber overflow (C)
        "hic604":       round(st.HIC_322604, 1),                  # HV-322604 opening (%)
        "hv_T_out":     hv.get("T_out"),                          # off-gas JT outlet T (C)
        "motive_kgh":   round(_rec.get("motive_kgh", 0.0), 1),   # ejector motive NH3 (kg/h)
        "ej_T_C":       round(ej.get("T_C", float("nan")), 1),   # ejector discharge T_d -> TT-322012 (C)
        "pumpA_rpm":    round(st.pumpA["speed_act"], 1),
        "pumpB_rpm":    round(st.pumpB["speed_act"], 1),
        "flags":        {k: v for k, v in st.flags.items() if v},
    }

def case(rig, apply, n_ovr, n_base=N_FAST):
    fresh()
    if rig:
        rig()
    base = snap(settle(n_base))
    apply()
    ovr  = snap(settle(n_ovr))
    return base, ovr

# ---------------------------------------------------------------- rigs
def rig_pumpA_lead():
    """Mirror the native single-pump design point but with A leading and B parked,
    so SIC-321950 (pump A) actually holds authority for a fair sweep."""
    st = main.state
    st.pumpA["on"] = True
    st.pumpB["on"] = False
    st.SIC_321950.set_mode("CAS")                 # cascade ratio demand drives A's opening
    st.SIC_321951.set_mode("MAN"); st.SIC_321951.set_op(0.0)

# ================================================================ RESULTS
R = {}

# --- LV-322501 stripper bottom-solution level valve --------------------------
R["LV-322501 pinch 0%"]  = case(None,
    lambda: (main.state.LIC_322501.__setitem__("mode", "MAN"),
             main.state.LIC_322501.__setitem__("op", 0.0)),   N_FAST)
R["LV-322501 open 100%"] = case(None,
    lambda: (main.state.LIC_322501.__setitem__("mode", "MAN"),
             main.state.LIC_322501.__setitem__("op", 100.0)), N_FAST)

# --- HV-322604 HP-scrubber off-gas vent --------------------------------------
def _set_hic(v):
    main.state.HIC_322604 = v
R["HV-322604 pinch 10%"]  = case(None, lambda: _set_hic(10.0),  N_SLOW)
R["HV-322604 open 100%"]  = case(None, lambda: _set_hic(100.0), N_SLOW)

# --- FIC-329409 CCW circulation to scrubber ----------------------------------
def _set_fic(v):
    main.state.FIC_329409["mode"] = "MAN"
    main.state.FIC_329409["op"]   = v
R["FIC-329409 pinch 10%"]  = case(None, lambda: _set_fic(10.0),  N_SLOW)
R["FIC-329409 open 100%"]  = case(None, lambda: _set_fic(100.0), N_SLOW)

# --- SIC-321950 pump-A speed / NH3 feed --------------------------------------
def _set_sic50():
    main.state.SIC_321950.set_mode("MAN")
    main.state.SIC_321950.set_op(50.0)            # 50 % rated -> 76 rpm
# (a) native baseline (pump A OFF, spare): expect NO authority -> NOT a dead valve
R["SIC-321950 -> 50% (native, A=spare)"] = case(None,         _set_sic50, N_FAST)
# (b) pump-A-lead baseline: A is the running feed pump -> real authority
R["SIC-321950 -> 50% (A leading)"]       = case(rig_pumpA_lead, _set_sic50, N_FAST)

# ================================================================ REPORT
def line(label, b, o, keys):
    print(f"\n  {label}")
    print(f"    {'variable':<14}{'baseline':>14}{'override':>14}{'Δ':>14}")
    for k, name in keys:
        bv, ov = b[k], o[k]
        if isinstance(bv, (int, float)) and isinstance(ov, (int, float)):
            print(f"    {name:<14}{bv:>14.3f}{ov:>14.3f}{ov-bv:>+14.3f}")
        else:
            print(f"    {name:<14}{str(bv):>14}{str(ov):>14}{'':>14}")
    fb, fo = b["flags"], o["flags"]
    if fb or fo:
        print(f"    flags base={fb or '-'}  override={fo or '-'}")

print("=" * 70)
print("  LEVEL-4 VALVE-AUTHORITY  &  PROCESS-RESPONSE  —  CAUSE/EFFECT MATRIX")
print("=" * 70)

line("LV-322501  pinch -> 0 %",  *R["LV-322501 pinch 0%"],
     [("lv_open", "LV open %"), ("drain_kgh", "m_drain kg/h"), ("strip_level", "LI-322501 %"), ("p_syn", "PT-329201")])
line("LV-322501  open  -> 100 %", *R["LV-322501 open 100%"],
     [("lv_open", "LV open %"), ("drain_kgh", "m_drain kg/h"), ("strip_level", "LI-322501 %"), ("p_syn", "PT-329201")])

line("HV-322604  pinch -> 10 %",  *R["HV-322604 pinch 10%"],
     [("hic604", "HIC-604 %"), ("p_syn", "PT-329201"), ("hv_T_out", "JT T_out C"), ("T_overflow", "TT-002 C")])
line("HV-322604  open  -> 100 %", *R["HV-322604 open 100%"],
     [("hic604", "HIC-604 %"), ("p_syn", "PT-329201"), ("hv_T_out", "JT T_out C"), ("T_overflow", "TT-002 C")])

line("FIC-329409 pinch -> 10 %",  *R["FIC-329409 pinch 10%"],
     [("ccw_tph", "CCW t/h"), ("T_overflow", "TT-002 C"), ("p_syn", "PT-329201")])
line("FIC-329409 open  -> 100 %", *R["FIC-329409 open 100%"],
     [("ccw_tph", "CCW t/h"), ("T_overflow", "TT-002 C"), ("p_syn", "PT-329201")])

line("SIC-321950 -> 50%  (NATIVE: pump A = idle spare)", *R["SIC-321950 -> 50% (native, A=spare)"],
     [("pumpA_rpm", "pumpA rpm"), ("ratio_PV", "N/C"), ("motive_kgh", "motive kg/h"), ("ej_T_C", "ej T_d C")])
line("SIC-321950 -> 50%  (pump A LEADING)", *R["SIC-321950 -> 50% (A leading)"],
     [("pumpA_rpm", "pumpA rpm"), ("ratio_PV", "N/C"), ("motive_kgh", "motive kg/h"), ("ej_T_C", "ej T_d C")])

print("\n" + "=" * 70)
