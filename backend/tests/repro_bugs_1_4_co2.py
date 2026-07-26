"""repro_bugs_1_4_co2.py -- CO2-feed pressure-driven delivery + PV-322203 vent split.

User bugs:
  #1  CO2 from BL keeps flowing at the same rate as synthesis pressure rises; there is a
      finite dP between the CO2 line (PIC-322203) and synthesis pressure that must gate it.
  #4  Opening PV-322203 must divert almost ALL CO2 out the vent (line P < synthesis P),
      not keep feeding the HP section.

Bugs 1 & 4 are ONE defect: the feed never respected the CO2-line vs synthesis dP.
Model (main.py CO2 block): F_feed = F_raw*feed_factor*phi_HP*f_to_HP
  P_line = min(P_syn + DP_HP_DES, P_line_ceil) - 0.25*PV_open       (compressor floats the dP)
  DP_HP_DES = 144.2-140.7 = 3.5 ;  P_line_ceil = SYN_P_MAX + DP_HP_DES = 144.2+3.5 = 147.7
  phi_HP = min(1, sqrt(dP_HP/DP_HP_DES))   delivery (bug 1), dP_HP = max(P_line - P_syn, 0)
  f_to_HP = g_HP/(g_HP+g_vent)             vent-diversion split (bug 4), dP_vent = max(P_line-5, 0)
Across the normal band (P_syn 140.7..144.2, PV shut) the float holds dP_HP~3.5 so phi_HP=1
and feed = load (small excursions do NOT throttle it -- correct plant behaviour, matches the
scrubber-heat test).  The taper/cutoff appears only when P_syn nears/exceeds the compressor
ceiling, or when PV-322203 opens and pulls the line below synthesis.

All checks read the live State attrs (not rounded telemetry) and run ONE deterministic tick:
the CO2 split is algebraic in (PV_open, p_syn), and the block reads s.p_syn_bara BEFORE the
synthesis ODE updates it, so a single pinned tick exercises the exact off-design point.
"""
import os, sys, math
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import main

DT  = 0.1
RAW = 54.618                       # t/h design raw CO2 from 320K002 (boundary)
DP_HP_DES = main.CO2_P_DES_BARA - main.SYN_P_DES_BARA   # 3.5 bar
n_pass = n_tot = 0

def chk(name, cond, detail=""):
    global n_pass, n_tot
    n_tot += 1
    if cond: n_pass += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"   {detail}" if detail else ""))

P_LINE_CEIL = main.SYN_P_MAX_BARA + DP_HP_DES          # 147.7 bar a compressor deliverable ceiling

def one_tick(pv_open_min=0.0, p_syn=None, raw=RAW):
    """Fresh design state, pin PV-322203 min opening + (optionally) synthesis pressure, 1 tick.
    Returns (F_feed, F_vent, F_raw, P_line) -- P_line is the PIC-322203 PV (line pressure)."""
    main.state = main.State()
    s = main.state
    s.F_CO2_raw_th = raw
    s.HIC_322203   = pv_open_min          # PV-322203 minimum opening (PIC stays MAN, op=0)
    if p_syn is not None:
        s.p_syn_bara = p_syn              # CO2 block reads this before the synthesis ODE
    tel = main.step_sim(DT)
    return s.F_CO2_th, s.F_CO2_vent_th, s.F_CO2_raw_th, tel["CO2_FEED"]["PIC_322203"]

print("\n=== BUGS 1+4: CO2 feed dP-delivery + PV-322203 vent split ===\n")

# --- T0  design identity (PV shut, P_syn=design): F_feed == F_raw, no vent (bit-exact) -------
feed, vent, raw, pline = one_tick(pv_open_min=0.0)
chk("design: F_feed == F_raw (bit-exact)", abs(feed - RAW) < 1e-9, f"feed={feed:.9f}")
chk("design: vent == 0",                   abs(vent) < 1e-9,       f"vent={vent:.9f}")
chk("design: P_line == 144.2 anchor",      abs(pline - main.CO2_P_DES_BARA) < 1e-9, f"P_line={pline:.6f}")
chk("design: mass closure feed+vent==raw", abs(feed + vent - raw) < 1e-9)

# --- T1  bug 4: PV-322203 fully open -> almost ALL CO2 vents, feed ~ 0 -----------------------
feed, vent, raw, pline = one_tick(pv_open_min=100.0)
chk("PV 100%: feed -> ~0 (diverted)",  feed < 0.01,            f"feed={feed:.4f} t/h")
chk("PV 100%: vent -> ~raw",           abs(vent - RAW) < 0.01, f"vent={vent:.4f} t/h")
chk("PV 100%: line dragged below P_syn", pline < main.SYN_P_DES_BARA, f"P_line={pline:.2f}")
chk("PV 100%: mass closure",           abs(feed + vent - raw) < 1e-9)

# --- T2  bug 4 graded: PV part-open at design P_syn -> partial diversion ---------------------
feed, vent, raw, pline = one_tick(pv_open_min=10.0, p_syn=main.SYN_P_DES_BARA)
chk("PV 10%: 0 < feed < raw (graded)", 0.0 < feed < RAW,       f"feed={feed:.3f} t/h")
chk("PV 10%: vent > 0",                vent > 0.0,             f"vent={vent:.3f} t/h")
chk("PV 10%: mass closure",            abs(feed + vent - raw) < 1e-9)

# --- T3  bug 1: small synthesis excursion (vent shut) does NOT throttle the load feed --------
#   320K002 floats its discharge to hold the design feed dP, so across the normal band the feed
#   stays at load (phi_HP=1) -- a small rise must NOT starve CO2 (this is what test_3 needs) --
#   AND there is ALWAYS a finite dP between the CO2 line and synthesis (bug 1 "there will always
#   be a dP between PIC-322203 and synthesis pressure").
P_SYN_HI = 142.7                                   # +2.0 bar excursion, < ceiling 147.7
feed, vent, raw, pline = one_tick(pv_open_min=0.0, p_syn=P_SYN_HI)
chk("P_syn 142.7: feed held at load (not throttled)", abs(feed - RAW) < 1e-9, f"feed={feed:.6f} t/h")
chk("P_syn 142.7: line floats, dP held ~3.5",  abs(pline - (P_SYN_HI + DP_HP_DES)) < 1e-9, f"P_line={pline:.4f}")
chk("P_syn 142.7: always a dP (line > P_syn)", pline > P_SYN_HI,       f"dP={pline - P_SYN_HI:.3f} bar")
chk("P_syn 142.7: no vent (PV shut)",          abs(vent) < 1e-9,       f"vent={vent:.6f} t/h")

# --- T3b bug 1: near the compressor ceiling, dP_HP shrinks -> delivery tapers (graded) -------
P_SYN_NC = 146.5                                    # P_line pinned at ceiling 147.7 -> dP_HP=1.2
feed, vent, raw, pline = one_tick(pv_open_min=0.0, p_syn=P_SYN_NC)
chk("P_syn 146.5: line capped at ceiling",     abs(pline - P_LINE_CEIL) < 1e-9, f"P_line={pline:.4f}")
chk("P_syn 146.5: 0 < feed < raw (tapering)",  0.0 < feed < RAW - 1.0, f"feed={feed:.3f} t/h")
chk("P_syn 146.5: mass closure",               abs(feed + vent - raw) < 1e-9)

# --- T4  bug 1: synthesis pressure >= compressor ceiling -> check valve shuts, feed = 0 ------
feed, vent, raw, pline = one_tick(pv_open_min=0.0, p_syn=148.0)     # >= P_line_ceil 147.7
chk("P_syn 148 >= ceiling: feed cut to 0", feed < 1e-9,            f"feed={feed:.9f} t/h")
chk("P_syn 148: line held at ceiling",     abs(pline - P_LINE_CEIL) < 1e-9, f"P_line={pline:.4f}")
chk("P_syn 148: all CO2 relieved",         abs(vent - RAW) < 1e-9, f"vent={vent:.4f} t/h")

print(f"\n  {n_pass}/{n_tot} checks passed\n")
assert n_pass == n_tot, f"{n_tot - n_pass} CO2 dP-split checks FAILED"
print("  repro_bugs_1_4_co2: PASS\n")
