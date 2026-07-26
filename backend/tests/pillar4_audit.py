"""
PILLAR 4 hazard-state & topology audit (read-only forward integration + monkeypatch probes).
No model edits. Captures scrubber/reactor internals via wrappers and main.state.
"""
import os, sys, math
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import main

DT = 0.1

# ---- capture scrubber internals (carry_mass_kgh, liq_carry, closure) per call ----
_orig_scrub = main.scrub_322e003
_scrub_cap = {}
def _wrap_scrub(offgas_feed, co2_scale, *a, **kw):
    r = _orig_scrub(offgas_feed, co2_scale, *a, **kw)
    cm = 0.0
    lc = kw.get("liq_carry_kmolh", None)
    if lc:
        cm = sum(lc.get(k, 0.0) * main.MW_COMP[k] for k in main.MW_COMP)
    _scrub_cap["carry_mass_kgh"] = cm
    _scrub_cap["liq_carry"] = lc
    _scrub_cap["closure_resid"] = r["closure_resid"]
    _scrub_cap["choke_level_pct"] = kw.get("choke_level_pct", None)
    return r

_orig_react = main.react_322r001
_react_cap = {}
def _wrap_react(*a, **kw):
    r = _orig_react(*a, **kw)
    _react_cap["delta_X"] = r["delta_X"]
    _react_cap["X_conv"] = r["X_conv"]
    _react_cap["closure_resid"] = r["closure_resid"]
    return r

main.scrub_322e003 = _wrap_scrub
main.react_322r001 = _wrap_react

def gd(s):
    return main._disturbance_gate(s)

def probe(tel):
    s = main.state
    return dict(
        LT_322504=tel["REACT_322R001"]["LT_322504"],
        LT_329501=tel["SCRUB_322E003"]["LT_329501"],
        ej_suc=tel["EJ_322F001"]["suction_kgh"],
        ov_th=tel["SCRUB_322E003"]["ov_th"],
        PT=tel["EJ_322F001"]["PI_329201"],
        carry=_scrub_cap.get("carry_mass_kgh", 0.0),
        liq_carry=_scrub_cap.get("liq_carry", None),
        scrub_closure=_scrub_cap.get("closure_resid", None),
        react_closure=_react_cap.get("closure_resid", None),
        choke_lvl=_scrub_cap.get("choke_level_pct", None),
        react_m_liq=s.react_m_liq,
        delta_X=_react_cap.get("delta_X", 0.0),
        scrub_holdup=s.scrub_holdup_kg,
        g_dist=gd(s),
        react_lvl_pct=s.react_level_pct,
        TT2002=tel["SCRUB_322E003"]["TT_322002"],
    )

def section(t):
    print("\n" + "="*78 + "\n" + t + "\n" + "="*78)

# =====================================================================
section("PHASE A/B SEQUENCE: reactor flood via HIC-322605 throttle -> carryover -> ejector choke")
# =====================================================================
main.state = main.State()
s = main.state
base = probe(main.step_sim(DT))
print("baseline tick1: LT504=%.3f LT329=%.3f ej_suc=%.1f ov=%.3f PT=%.3f carry=%.3f m_liq=%.1f"
      % (base["LT_322504"], base["LT_329501"], base["ej_suc"], base["ov_th"], base["PT"],
         base["carry"], base["react_m_liq"]))
# M_full reference
T_bulk = 179.7
import reactor
M_full = reactor.liquid_density(T_bulk) * main._react_area_m2 * main.REACT_LIQ_H_M
print("M_full(reactor vessel-full) ~= %.1f kg ; design holdup REACT_M_LIQ_DES = %.1f kg"
      % (M_full, main.REACT_M_LIQ_DES))

s.HIC_322605 = 10.0   # hard throttle the bottom take-off -> reactor floods
print("\n[t=tick] LT504  LT329  m_liq(kg)  carry(kg/h)  ov(t/h)  ej_suc(kg/h)  PT      Rclos     Sclos   g")
flood_onset = None       # first tick LT_322504 pegs 100
carry_onset = None       # first tick carry_mass_kgh > 0
choke_onset = None       # first tick scrub level rises above NLL (50)
prevsuc = base["ej_suc"]
MAXT = 120000
last = None
log_every = None
for i in range(1, MAXT+1):
    tel = main.step_sim(DT)
    p = probe(tel)
    if flood_onset is None and p["LT_322504"] >= 99.99:
        flood_onset = i
    if carry_onset is None and p["carry"] > 1e-6:
        carry_onset = i
    if choke_onset is None and p["LT_329501"] > 50.01:
        choke_onset = i
    # print a sparse trace around the action
    if i in (1,) or (carry_onset and carry_onset-3 <= i <= carry_onset+3) or i % 20000 == 0:
        print("[%6d] %6.2f %6.2f %9.1f %10.2f %8.4f %12.1f %7.3f %8.2e %8.2e %.2f"
              % (i, p["LT_322504"], p["LT_329501"], p["react_m_liq"], p["carry"],
                 p["ov_th"], p["ej_suc"], p["PT"],
                 (p["react_closure"] or 0.0), (p["scrub_closure"] or 0.0), p["g_dist"]))
    last = p
    # stop once everything has settled past choke
    if choke_onset and i > choke_onset + 60000:
        break

print("\nONSET TICKS (DT=%.2fs):" % DT)
print("  flood (LT-322504 pegged 100%%) : tick %s  (t=%.1fs)" % (flood_onset, (flood_onset or 0)*DT))
print("  carryover begins (carry>0)     : tick %s  (t=%.1fs)" % (carry_onset, (carry_onset or 0)*DT))
print("  scrubber choke (LT-329501>NLL) : tick %s  (t=%.1fs)" % (choke_onset, (choke_onset or 0)*DT))
order_ok = (flood_onset and carry_onset and choke_onset and flood_onset <= carry_onset <= choke_onset)
print("  SEQUENCE A-before-B correct?   : %s" % order_ok)
print("\nSETTLED FLOOD STATE:")
print("  LT-322504=%.2f%%  LT-329501=%.2f%%  react_m_liq=%.1f (M_full=%.1f)  carry=%.2f kg/h"
      % (last["LT_322504"], last["LT_329501"], last["react_m_liq"], M_full, last["carry"]))
print("  ej_suction=%.1f kg/h (des %.1f)  ov=%.3f t/h  PT=%.3f bar (max %.1f)  TT2002=%.2f"
      % (last["ej_suc"], main.EJ_SUC_TOT_DES, last["ov_th"], last["PT"], main.SYN_P_MAX_BARA, last["TT2002"]))
print("  scrub_holdup=%.1f kg (NLL %.1f, MAX %.1f)" % (last["scrub_holdup"], main.SCRUB_HOLDUP_NLL_KG, main.SCRUB_HOLDUP_MAX_KG))

# ---- Phase A mass-conservation closure during carryover ----
section("PHASE A: mass-conservation closure during carryover (feed+=c AND overflow+=c -> net 0)")
# Direct unit test of scrub_322e003 with a synthetic carryover vector vs None.
s2 = main.State()
main.state = s2
off = {k: main.REACT_OFFGAS_DES.get(k,0.0) for k in main.MW_COMP}
r_none = _orig_scrub(off, 1.0, 80.0, main.SCRUB_CCW_KGH_DES, liq_carry_kmolh=None)
carry = {k: 0.05*main.REACT_OVERFLOW_DES.get(k,0.0) for k in main.MW_COMP}  # 5% overflow as melt
cm = sum(carry[k]*main.MW_COMP[k] for k in main.MW_COMP)
r_c = _orig_scrub(off, 1.0, 80.0, main.SCRUB_CCW_KGH_DES, liq_carry_kmolh=carry, t_carry_c=185.0)
print("carry_mass injected = %.2f kg/h" % cm)
print("closure_resid  no-carry = %.4e   with-carry = %.4e   delta = %.4e"
      % (r_none["closure_resid"], r_c["closure_resid"], r_c["closure_resid"]-r_none["closure_resid"]))
fin = sum(carry.values())
fov = sum(r_c["overflow_kmolh"][k]-r_none["overflow_kmolh"][k] for k in main.MW_COMP)
foff = sum(r_c["offgas_kmolh"][k]-r_none["offgas_kmolh"][k] for k in main.MW_COMP)
print("feed delta  =%.6f kmol/h (should == sum carry %.6f)" % (
    sum(r_c["feed_kmolh"][k]-r_none["feed_kmolh"][k] for k in main.MW_COMP), fin))
print("overflow delta=%.6f kmol/h ; offgas delta=%.6f kmol/h" % (fov, foff))
print("net (feed - overflow - offgas) carryover contribution = %.3e (==0 mass-conserving)"
      % ((sum(carry.values())) - fov - foff))
# below-lip bit-exactness
print("below-lip (liq_carry=None): offgas/overflow IDENTICAL to design? off=%s ov=%s" % (
    all(abs(r_none["offgas_kmolh"][k]-main.SCRUB_OFFGAS_KMOLH_DES.get(k,0.0))<1e-9 for k in main.MW_COMP),
    all(abs(r_none["overflow_kmolh"][k]-main.SCRUB_OVERFLOW_KMOLH_DES.get(k,0.0))<1e-9 for k in main.MW_COMP)))

# =====================================================================
section("RUNAWAY HUNT 1: steam loop  P_LP->t_shell->T_prod->reactor->duty->m_hpcc->P_LP  (g_dist gate)")
# =====================================================================
main.state = main.State()
s = main.state
# REAL operator input: raise raw CO2 +30% via co2_set (s.F_CO2_th is recomputed each tick from raw).
# This forces g_dist=1 and lifts throughput/duty -> drive the steam loop and check P_LP converges.
main.handle_cmd({"type":"co2_set","value":1.30*(main.CO2_DES_KGH/1000.0)})
maxP_LP = -1e9; prevPLP=None; jump=0.0
for i in range(1, 60001):
    tel = main.step_sim(DT)
    plp = main.state.steam.P_LP
    maxP_LP = max(maxP_LP, plp)
    if prevPLP is not None:
        jump = max(jump, abs(plp-prevPLP))   # largest per-tick step (divergence sniff)
    prevPLP = plp
    if i in (1,100,1000) or i % 20000 == 0:
        print("[%6d] g_dist=%.3f  P_LP=%.5f  T_sh_lp=%.3f  react_m_liq=%.1f  delta_X=%.4f"
              % (i, gd(main.state), plp,
                 main.HPCC_STEAM_TSAT_C + gd(main.state)*(main.tsat_steam(plp)-main.tsat_steam(main.HPCC_STEAM_P_BARA)),
                 main.state.react_m_liq, _react_cap.get("delta_X",0)))
print("max P_LP over run = %.5f bar ; max per-tick jump = %.3e (->0 == settled, not diverging)"
      % (maxP_LP, jump))
print("settled P_LP=%.5f bar (design ~%.3f) ; bounded, finite=%s ; g_dist=%.4f"
      % (main.state.steam.P_LP, main.HPCC_STEAM_P_BARA, math.isfinite(main.state.steam.P_LP), gd(main.state)))

# =====================================================================
section("RUNAWAY HUNT 2: off-gas deficit amp = 1 + gain*delta_X  and Pi = kappa*delta_X (PT forcing)")
# =====================================================================
# Force conversion deficit: trip NH3 pump B -> NH3 mass flow halves while CO2 held -> ratio_PV
# crashes -> L_fresh drops -> X_conv << X_DES -> delta_X climbs. Confirm amp/Pi/PT stay bounded.
main.state = main.State()
s = main.state
s.pumpB["on"] = False   # NH3-starvation: half the pumping -> N/C crash
maxPT=-1e9; maxdX=-1e9; prevPT=None; jump=0.0
for i in range(1, 80001):
    tel = main.step_sim(DT)
    dX = _react_cap.get("delta_X",0.0)
    maxdX=max(maxdX,dX); maxPT=max(maxPT,main.state.p_syn_bara)
    if prevPT is not None: jump=max(jump,abs(main.state.p_syn_bara-prevPT))
    prevPT=main.state.p_syn_bara
    if i in (1,1000) or i % 20000 == 0:
        print("[%6d] ratio_PV=%.4f  delta_X=%.4f  amp=%.4f  Pi=%.4f  PT=%.5f (max %.1f)  X_conv=%.4f"
              % (i, main.state.ratio_PV, dX, 1.0+main.REACT_OFFGAS_DEFICIT_GAIN*dX, main.REACT_PI_KAPPA*dX,
                 main.state.p_syn_bara, main.SYN_P_MAX_BARA, _react_cap.get("X_conv",0)))
dX = _react_cap.get("delta_X",0.0)
print("max delta_X=%.4f (theoretical cap 1.0) ; max PT=%.5f (SYN_P_MAX=%.1f) ; max per-tick jump=%.3e"
      % (maxdX, maxPT, main.SYN_P_MAX_BARA, jump))
print("settled delta_X=%.4f ; amp=1+gain*dX=%.4f (bounded) ; PT clamped<=%.1f ; finite=%s"
      % (dX, 1.0+main.REACT_OFFGAS_DEFICIT_GAIN*dX, main.SYN_P_MAX_BARA, math.isfinite(main.state.p_syn_bara)))

# =====================================================================
section("RUNAWAY HUNT 3: g_dist gate effectiveness — at-design g_dist must be 0 (no spurious loop)")
# =====================================================================
main.state = main.State()
g0 = gd(main.state)
print("g_dist at fresh design state = %.6f  (must be 0 -> steam loop frozen at design)" % g0)
# tiny noise below deadband
main.state.HIC_322605 = main.REACT_HIC605_DES_PCT * (1+0.001)
print("g_dist after +0.1%% HIC605 (below deadband 0.2%%) = %.6f" % gd(main.state))
main.state.HIC_322605 = main.REACT_HIC605_DES_PCT * (1+0.02)
print("g_dist after +2%% HIC605 (above ramp) = %.6f (clamped 1)" % gd(main.state))

# =====================================================================
section("CHOKE/STALL PHYSICS: ejector capacity vs motive NH3 (f_stall) — motive-dependent, not arbitrary")
# =====================================================================
print("phi_m   motive(kg/h)  f_stall   capacity(kg/h)  m_suc@L=NLL   note")
for phi_m in [1.0, 0.5, 0.36, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10, 0.0]:
    mot = phi_m * (main.EJ_MOTIVE_DES_LIVE or main.EJ_MOTIVE_NH3_DES)
    r = main.ejector_322f001(mot, main.EJ_MOTIVE_T_DES_C, main.EJ_OPEN_DES, scrub_level_frac=1.0)
    # recompute f_stall for display
    pm = mot/(main.EJ_MOTIVE_DES_LIVE or main.EJ_MOTIVE_NH3_DES)
    f_stall = main.clamp((pm-main.EJ_STALL_PHI)/(main.EJ_STALL_REC-main.EJ_STALL_PHI),0,1)**main.EJ_STALL_EXP
    note = "DESIGN" if abs(phi_m-1.0)<1e-9 else ("STALL KNEE" if abs(phi_m-0.2)<1e-9 else
            ("RECOVERY" if abs(phi_m-0.35)<1e-9 else ("DEEP STALL" if phi_m<0.2 else "")))
    print("%.3f  %11.1f  %7.4f  %14.1f  %11.1f   %s"
          % (phi_m, mot, f_stall, r["suction_kgh"]/max(main.clamp(1.0,0,main.EJ_HYD_FRAC_MAX),1e-9), r["suction_kgh"], note))
print("\nEJ_MOTIVE_DES_LIVE pin = %.4f vs const EJ_MOTIVE_NH3_DES = %.1f (delta %.4f kg/h, %.4f%%)"
      % (main.EJ_MOTIVE_DES_LIVE, main.EJ_MOTIVE_NH3_DES,
         main.EJ_MOTIVE_DES_LIVE-main.EJ_MOTIVE_NH3_DES,
         100*(main.EJ_MOTIVE_DES_LIVE-main.EJ_MOTIVE_NH3_DES)/main.EJ_MOTIVE_NH3_DES))
print("HYD choke ceiling: m_suc at L=2*NLL (frac=2) capped at EJ_HYD_FRAC_MAX=%.2f:" % main.EJ_HYD_FRAC_MAX)
r_hi = main.ejector_322f001(main.EJ_MOTIVE_DES_LIVE, main.EJ_MOTIVE_T_DES_C, main.EJ_OPEN_DES, scrub_level_frac=2.0)
print("  m_suc(frac=2.0)=%.1f  vs capacity*1.25=%.1f  (must equal -> head-choke active)"
      % (r_hi["suction_kgh"], main.EJ_SUC_TOT_DES*1.25))

print("\nAUDIT COMPLETE")
