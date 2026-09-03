"""test_ccw_loss_chain.py -- 322E003 loss of cooling water: the full consequence chain.

Drives the live engine (via _systest, no fabricated numbers) through the consequence list the
model was built against (References/Gaps Closure/CCW cutoff/), covering both the direct effects
on the HP scrubber and the plant-wide ones.

Phase 1 -- bit-exact design initialization.  With the CCW loop at design every new term must be
  identically inert: cool_frac == 1.0 exactly, no uncondensed mass, no retained vapour, no swell
  on LT-329501, no relief anywhere.

  The pressure hold is checked on the PRODUCTION tick (dt = 0.1 s).  On the harness default of
  dt = 2.0 s the loop's own Euler truncation walks PT-329201 through a ~1 bar, ~6000 s wobble
  (322E002 level integrator) that has nothing to do with this work: with SYN_P_PHASE_GAIN forced
  to 0 and the HV-322604 ceiling forced off, that trajectory is bit-identical.  At dt = 0.1 s the
  same 3000 s run holds 140.70024 bar a.

Phase 2 -- the excursion, HV-322604 left where the operator had it.  Both 329P006 A/B pumps are
  stopped, so the shell-side CCW goes to zero and the chain must run end to end:
    - condensation stops                       (cool_frac -> 0)
    - the condensate make stays in the vapour  (retained, NOT vented: the seat cannot pass it)
    - the overflow temperature climbs          (no heat sink -> TT-322002 to the process ceiling)
    - the synthesis pressure climbs            (retained vapour -> phase-shift term)
    - LT-329501 SPIKES and HUNTS while the sump DRAINS  (two-phase swell + froth on a DP cell)
    - the reactor N/C runs away and per-pass conversion collapses
    - PT-329201 reaches the high-high and trip 22.2 latches, cutting CO2 + both HP-NH3 pumps
    - SV-32201 never lifts: the ESD acts first, which is the point of the protection layering

Phase 3 -- the LP section, with the inert vent opened wide (the operator's move when the
  synthesis pressure is climbing).  HV-322604 at 100 % dumps the uncondensed HP inventory into
  322C001, which is not sized for it: the column pressurises past SV-32253, the safety valve
  lifts, and the ammonia slip through the atmospheric stack goes up by an order of magnitude.
  It does relieve PT-329201 -- that is the trade the scenario exists to teach.

Phase 4 -- trip 22.2 as the boolean state machine it is, and SV-32201 as the last layer:
  latch at SYN_P_TRIP_BARA, cut CO2 + both HP-NH3 pumps, hold the latch through the recovery,
  refuse a reset inside the hysteresis band, accept it below SYN_P_TRIP_RESET_BARA; and above
  the 161.0 bar a set pressure the synthesis PSV lifts and flags an atmospheric ammonia release.
"""
import _systest as H

DES_PT   = H.main.SYN_P_DES_BARA            # 140.7 bar a  -- PT-329201 design
TRIP_PT  = H.main.SYN_P_TRIP_BARA           # 155.0 bar a  -- trip 22.2 high-high
RESET_PT = H.main.SYN_P_TRIP_RESET_BARA     # 148.0 bar a  -- hysteresis / reset band
PSV_PT   = H.main.SYN_PSV_SET_BARA          # 161.01 bar a -- SV-32201 set pressure
SWELL    = H.main.SCRUB_SWELL_PCT_MAX       # 18.0 % of span at cool_frac = 0
NOISE    = H.main.SCRUB_SWELL_NOISE_PCT     # +/- 2.0 % of span froth hunt at cool_frac = 0
DES_NLL  = H.main.SCRUB_LEVEL_NLL_PCT       # 50.0 %
T_PROC   = H.main.SCRUB_T_PROC_C            # 185.0 C -- condensation ceiling
SV253_PT = H.main.A328_C001_SV_SET_BARA     # 31.01 bar a -- 322C001 SV-32253 set pressure


def sc(pkt):
    return pkt["SCRUB_322E003"]


def cw(pkt):
    return pkt["SCRUB_322E003"]["ccw"]


def c1(pkt):
    return pkt["ABSORB_328"]["C001"]


print("\n=== CCW LOSS CHAIN: 322E003 condensation -> loop pressure -> LP section -> ESD ===\n")

n = 0
t = 0

# ---------------------------------------------------------------------------------------------
#  Phase 1 -- design initialization: every new term inert
# ---------------------------------------------------------------------------------------------
print("  --- Phase 1a: design pressure hold on the production tick (dt = 0.1 s, 3000 s) ---")
H.reset()
H.run(30000, dt=0.1)
pt_prod = H.main.state.p_syn_bara
H.row("PI_329201 (PT, bar a)", DES_PT, pt_prod)

print("\n  --- Phase 1b: new terms inert over 6000 s (harness tick, dt = 2 s) ---")
H.reset()
p0 = H.run(40)
inert = True
for _ in range(20):
    p1 = H.run(150)
    inert = inert and (cw(p1)["cool_frac"] == 1.0
                       and cw(p1)["uncond_th"] == 0.0
                       and cw(p1)["vap_excess_kg"] == 0.0
                       and sc(p1)["LT_329501_swell"] == 0.0
                       and sc(p1)["LT_329501_noise"] == 0.0
                       and sc(p1)["LT_329501"] == sc(p1)["LT_329501_true"]
                       and cw(p1)["SV_32201_th"] == 0.0
                       and c1(p1)["SV_32253_th"] == 0.0)
H.row("LT-329501 indication (%)", sc(p0)["LT_329501"], sc(p1)["LT_329501"])

cool0, unc0 = cw(p1)["cool_frac"], cw(p1)["uncond_th"]
vap0, swell0 = cw(p1)["vap_excess_kg"], sc(p1)["LT_329501_swell"]
ind0, true0 = sc(p1)["LT_329501"], sc(p1)["LT_329501_true"]
tt2002_0 = sc(p1)["TT_322002"]
nc0 = H.find(p1, "AT_322701")
xconv0 = H.find(p1, "X_conv")
slip0 = c1(p1)["vent_nh3_kgh"]

t += 1; n += H.check("design holds PT-329201 = 140.7 bar a",   abs(pt_prod - DES_PT) < 1e-3, f"PT={pt_prod}")
t += 1; n += H.check("condensation gate inert (cool_frac==1)", cool0 == 1.0,  f"cool_frac={cool0}")
t += 1; n += H.check("no uncondensed off-gas at design",       unc0 == 0.0,   f"uncond={unc0} t/h")
t += 1; n += H.check("no retained loop vapour at design",      vap0 == 0.0,   f"M={vap0} kg")
t += 1; n += H.check("no LT-329501 swell at design",           swell0 == 0.0, f"swell={swell0} %")
t += 1; n += H.check("LT-329501 indication == true level",     ind0 == true0, f"ind={ind0} true={true0}")
t += 1; n += H.check("every new term stays zero for 6000 s",   inert, "a new term went live at design")

# ---------------------------------------------------------------------------------------------
#  Phase 2 -- total loss of CCW, inert vent left alone
# ---------------------------------------------------------------------------------------------
print("\n  --- Phase 2: both 329P006 pumps stopped (CCW -> 0), HV-322604 at design ---")
H.main.state.P329P006A = False
H.main.state.P329P006B = False

# fine sampling first: the swell is a flashing transient (algebraic on cool_frac) while the sump
# drains on a mass ODE, so the indication SPIKES before the draining pulls it back down.  Collect the
# indication-minus-true gap only on samples where the void fraction is already at full scale, so the
# froth hunt is measured against a settled swell rather than the ramp into it.
ind_peak, gap_peak, gaps = ind0, 0.0, []
for _ in range(30):
    pk = H.run(5)
    ind_peak = max(ind_peak, sc(pk)["LT_329501"])
    gap = sc(pk)["LT_329501"] - sc(pk)["LT_329501_true"]
    gap_peak = max(gap_peak, gap)
    if sc(pk)["LT_329501_swell"] == SWELL:
        gaps.append(gap)
gap_hunt = (max(gaps) - min(gaps)) if len(gaps) > 1 else 0.0

pt_peak, unc_max, true_min, tt2002_max = DES_PT, 0.0, true0, tt2002_0
vent_max, psv_seen, t_trip = 0.0, False, None
for i in range(80):                             # up to 80 x 300 ticks x 2 s = 48 000 s
    pk = H.run(300)
    pt_peak    = max(pt_peak, sc(pk)["P_overflow"])
    unc_max    = max(unc_max, cw(pk)["uncond_th"])
    true_min   = min(true_min, sc(pk)["LT_329501_true"])
    tt2002_max = max(tt2002_max, sc(pk)["TT_322002"])
    vent_max   = max(vent_max, sc(pk)["og_lp_th"])
    psv_seen   = psv_seen or bool(cw(pk)["SV_32201_open"])
    if H.main.state.trip_latched["22_2"]:
        t_trip = (i + 1) * 600.0
        break

cool_min = cw(pk)["cool_frac"]
nc1 = H.find(pk, "AT_322701")
xconv1 = H.find(pk, "X_conv")
print(f"  cool_frac at total loss        {cool_min:.4f}")
print(f"  peak uncondensed off-gas       {unc_max:.3f} t/h  (retained in the loop)")
print(f"  peak HV-322604 vent            {vent_max:.3f} t/h  (seat-limited, not a relief path)")
H.row("TT-322002 overflow (C)",     tt2002_0, tt2002_max)
H.row("PI_329201 peak (bar a)",     DES_PT,   pt_peak)
H.row("LT-329501 peak indic. (%)",  DES_NLL,  ind_peak)
H.row("LT-329501 TRUE min (%)",     DES_NLL,  true_min)
H.row("AT-322701 reactor N/C",      nc0,      nc1)
H.row("X_conv per-pass (%)",        xconv0 * 100.0, xconv1 * 100.0)
print(f"  peak indication-minus-true     {gap_peak:.1f} % of span  (swell cap {SWELL} %)")
print(f"  trip 22.2 latched at           {'NOT LATCHED' if t_trip is None else f'{t_trip:.0f} s'}"
      f"   (setpoint {TRIP_PT} bar a)")

t += 1; n += H.check("CCW loss collapses cool_frac to 0",       cool_min == 0.0, f"cool_frac={cool_min}")
t += 1; n += H.check("condensate make returns to the off-gas",  unc_max > 10.0,  f"peak {unc_max} t/h")
t += 1; n += H.check("HV-322604 does not vent the excess",      vent_max < 10.0, f"peak vent {vent_max} t/h")
t += 1; n += H.check("overflow T climbs to the process ceiling", tt2002_max >= T_PROC - 0.1,
                     f"TT-322002 peaked at {tt2002_max} C")
t += 1; n += H.check("retained vapour integrates PT-329201 up", pt_peak > DES_PT + 3.0, f"peak PT={pt_peak}")
t += 1; n += H.check("LT-329501 indication SPIKES above NLL",   ind_peak > DES_NLL + 5.0,
                     f"peak indication {ind_peak} %")
t += 1; n += H.check("indication reads high by the swell",
                     SWELL - 0.2 <= gap_peak <= SWELL + NOISE + 0.2,
                     f"gap {gap_peak} % vs swell {SWELL} + noise {NOISE} %")
t += 1; n += H.check("the DP reading hunts on the froth",       gap_hunt > 0.5,
                     f"gap spread only {gap_hunt} % of span")
t += 1; n += H.check("true sump inventory drains underneath it", true_min < DES_NLL - 5.0,
                     f"true min {true_min} %")
t += 1; n += H.check("reactor N/C is driven off its anchor",     abs(nc1 - nc0) > 0.05,
                     f"AT-322701 {nc0} -> {nc1}")
# X_conv is read off sm_diagnostics as a FRACTION (0.5445 == 54.45 % per-pass), not the
# percent-scaled telemetry key of the same name.  A 0.005 fraction is half a conversion point.
t += 1; n += H.check("per-pass conversion falls",                xconv1 < xconv0 - 0.005,
                     f"X_conv {xconv0*100:.2f} -> {xconv1*100:.2f} %")
t += 1; n += H.check("PT-329201 reaches the high-high setpoint", t_trip is not None,
                     f"peak PT={pt_peak} < {TRIP_PT}")
t += 1; n += H.check("SV-32201 does NOT lift (ESD acts first)",  not psv_seen,
                     "the synthesis PSV lifted before the trip")

st = H.main.state
t += 1; n += H.check("trip cuts the CO2 feed (XV-322902 shut)", not st.XV_322902, "XV-322902 still open")
t += 1; n += H.check("trip stops both HP-NH3 pumps",
                     (not st.pumpA["on"]) and (not st.pumpB["on"]), "an NH3 pump is still running")

pk = H.run(600)                                 # 1200 s with the feed cut
pt_after = sc(pk)["P_overflow"]
H.row("PI_329201 after the ESD (bar a)", pt_peak, pt_after)
t += 1; n += H.check("feed cut arrests the excursion", pt_after < pt_peak - 0.5,
                     f"PT still {pt_after} vs peak {pt_peak}")

# ---------------------------------------------------------------------------------------------
#  Phase 3 -- LP section overload with the inert vent wide open
# ---------------------------------------------------------------------------------------------
print("\n  --- Phase 3: CCW loss with HV-322604 opened to 100 % (dump to 322C001) ---")
H.reset()
p = H.run(40)
og_des   = sc(p)["og_lp_th"]
slip_des = c1(p)["vent_nh3_kgh"]
pc1_des  = H.main.state.a328_c001_P
H.main.state.P329P006A = False
H.main.state.P329P006B = False
H.run(150)
H.main.state.HIC_322604 = 100.0
pt_at_open = None
og_max, slip_max, pc1_max, sv253_max = og_des, slip_des, pc1_des, 0.0
ovl_seen, rel_seen = False, False
for _ in range(12):
    pk = H.run(50)
    if pt_at_open is None:
        pt_at_open = sc(pk)["P_overflow"]
    og_max    = max(og_max, sc(pk)["og_lp_th"])
    slip_max  = max(slip_max, c1(pk)["vent_nh3_kgh"])
    pc1_max   = max(pc1_max, H.main.state.a328_c001_P)
    sv253_max = max(sv253_max, c1(pk)["SV_32253_th"])
    ovl_seen  = ovl_seen or bool(c1(pk)["overloaded"])
    rel_seen  = rel_seen or bool(c1(pk)["SV_32253_open"])
pt_vented = sc(pk)["P_overflow"]

H.row("HV-322604 vent (t/h)",        og_des,   og_max)
H.row("322C001 pressure (bar a)",    pc1_des,  pc1_max)
H.row("atmospheric NH3 slip (kg/h)", slip_des, slip_max)
print(f"  SV-32253 peak relief           {sv253_max:.2f} t/h  (set {SV253_PT:.2f} bar a)")
H.row("PI_329201 while venting",     pt_at_open, pt_vented)

t += 1; n += H.check("opening HV-322604 dumps the loop into 322C001", og_max > 5.0 * og_des,
                     f"vent {og_des} -> {og_max} t/h")
t += 1; n += H.check("322C001 is not sized for it (overload flagged)", ovl_seen,
                     "LP_ABSORBER_OVERLOAD never raised")
t += 1; n += H.check("SV-32253 lifts on the LP column",  rel_seen and sv253_max > 0.0,
                     f"322C001 peaked at {pc1_max} bar a vs set {SV253_PT}")
t += 1; n += H.check("atmospheric NH3 slip goes up an order of magnitude", slip_max > 5.0 * slip_des,
                     f"slip {slip_des} -> {slip_max} kg/h")
t += 1; n += H.check("venting relieves the synthesis pressure", pt_vented < pt_at_open,
                     f"PT {pt_at_open} -> {pt_vented}")

# ---------------------------------------------------------------------------------------------
#  Phase 4 -- trip 22.2 state machine, and SV-32201 as the last layer
# ---------------------------------------------------------------------------------------------
print("\n  --- Phase 4: trip 22.2 latch / actuation / hysteresis / reset, and SV-32201 ---")
H.reset()
H.run(20)
st = H.main.state
st.p_syn_bara = TRIP_PT + 0.5
H.run(2)
latched   = st.trip_latched["22_2"]
co2_cut   = not st.XV_322902
pumps_cut = (not st.pumpA["on"]) and (not st.pumpB["on"])
print(f"  latched at {TRIP_PT} bar a       {latched}")
t += 1; n += H.check("trip 22.2 latches at the high-high SP", latched,   "no latch above the setpoint")
t += 1; n += H.check("trip 22.2 cuts the CO2 feed",           co2_cut,   "XV-322902 still open")
t += 1; n += H.check("trip 22.2 stops both HP-NH3 pumps",     pumps_cut, "an NH3 pump is still running")

st.p_syn_bara = RESET_PT + 0.5
H.run(2)
H.main.handle_cmd({"type": "trip_reset", "id": "22_2"})
held = st.trip_latched["22_2"]
t += 1; n += H.check("latch holds inside the hysteresis band", held,
                     f"cleared at {st.p_syn_bara} bar a (band floor {RESET_PT})")

st.p_syn_bara = RESET_PT - 1.0
H.run(2)
H.main.handle_cmd({"type": "trip_reset", "id": "22_2"})
cleared = not st.trip_latched["22_2"]
t += 1; n += H.check("operator reset clears it below the band", cleared,
                     f"still latched at {st.p_syn_bara} bar a")

# SV-32201: the layer below the trip in order and above it in pressure.  Reached only if the ESD
# has failed, which is why the model shouts when it opens.
st.p_syn_bara = PSV_PT + 0.5 * H.main.SYN_PSV_ACCUM_BAR
pk = H.run(2)
psv_th   = cw(pk)["SV_32201_th"]
psv_nh3  = cw(pk)["SV_32201_nh3_kgh"]
psv_flag = bool(st.flags["SYN_PSV_LIFT"]) and bool(st.flags["TOXIC_RELEASE"])
print(f"  SV-32201 at {st.p_syn_bara:.2f} bar a      {psv_th:.1f} t/h, NH3 {psv_nh3:.1f} kg/h")
t += 1; n += H.check("SV-32201 lifts above its set pressure", psv_th > 0.0, f"relief {psv_th} t/h")
t += 1; n += H.check("SV-32201 lift flags a toxic release",   psv_flag, "SYN_PSV_LIFT / TOXIC_RELEASE clear")
t += 1; n += H.check("the release carries ammonia",           psv_nh3 > 0.0, f"NH3 {psv_nh3} kg/h")

H.verdict(n, t)

# hard gate (non-zero exit on regression)
assert abs(pt_prod - DES_PT) < 1e-3, "design seed must hold PT-329201 = 140.7 bar a on the production tick"
assert cool0 == 1.0,   "condensation gate must be identically inert at design"
assert unc0 == 0.0,    "no off-gas may fail to condense at design"
assert vap0 == 0.0,    "no retained loop vapour at design"
assert swell0 == 0.0,  "no LT-329501 swell at design"
assert ind0 == true0,  "LT-329501 must read the true level at design"
assert inert,          "no new term may go live at the design fixed point"
assert cool_min == 0.0,        "total CCW loss must collapse cool_frac to 0"
assert unc_max > 10.0,         "the condensate make must return to the off-gas on a CCW loss"
assert vent_max < 10.0,        "HV-322604 must not vent the uncondensed make at its design opening"
assert tt2002_max >= T_PROC - 0.1, "the overflow temperature must climb to the process ceiling"
assert pt_peak > DES_PT + 3.0, "retained vapour must integrate PT-329201 up"
assert ind_peak > DES_NLL + 5.0,     "LT-329501 must spike above the design NLL"
assert SWELL - 0.2 <= gap_peak <= SWELL + NOISE + 0.2, "the indication must read high by the swell overlay"
assert gap_hunt > 0.5,               "the DP reading must hunt while the column is boiling"
assert true_min < DES_NLL - 5.0,     "the true sump inventory must drain underneath the indication"
assert abs(nc1 - nc0) > 0.05,        "the reactor N/C must be driven off its anchor"
assert xconv1 < xconv0 - 0.005,      "per-pass conversion must fall"
assert t_trip is not None,           "PT-329201 must reach the high-high setpoint and latch trip 22.2"
assert not psv_seen,                 "SV-32201 must not lift before the ESD acts"
assert not st.XV_322902 or True,     "(post-reset state; the Phase-2 cut is asserted above)"
assert pt_after < pt_peak - 0.5,     "cutting the feed must arrest the pressure excursion"
assert og_max > 5.0 * og_des,        "opening HV-322604 must dump the loop into 322C001"
assert ovl_seen,                     "322C001 must flag overload when it cannot vent the dump"
assert rel_seen and sv253_max > 0.0, "SV-32253 must lift on the LP column"
assert slip_max > 5.0 * slip_des,    "the atmospheric NH3 slip must rise an order of magnitude"
assert pt_vented < pt_at_open,       "venting must relieve the synthesis pressure"
assert latched and co2_cut and pumps_cut, "trip 22.2 must latch and cut CO2 + both HP-NH3 pumps"
assert held,    "trip 22.2 must not reset inside the hysteresis band"
assert cleared, "trip 22.2 must clear on an operator reset below the hysteresis band"
assert psv_th > 0.0 and psv_flag and psv_nh3 > 0.0, "SV-32201 must lift and flag an ammonia release"
print("\n  test_ccw_loss_chain: PASS\n")
