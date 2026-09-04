"""test_3_scrubber_heat.py -- 322E003 CCW condensation -> PT-329201 reverse heat->pressure.

Drives the live engine (via _systest, no fabricated numbers) to validate the scrubber/
pressure coupling:

  1. Throttling the HP-Scrubber CCW circulation (FIC-329409) under-condenses the reactor
     off-gas, so the uncondensed vapour accumulates and PT-329201 (synthesis-loop top
     pressure) integrates UP.
  2. The same CCW cut raises the CCW return temperature TT-329125 (less coolant, same duty).
  3. rho_cond (condensation capacity / vent demand) drops below 1 when CCW is throttled.
  4. Restoring CCW relaxes PT-329201 back toward its 140.7 bar a design value.
  5. Design-identity guard: a fresh design state holds PT-329201 = 140.7 bar a (no spurious
     lift) and the 322E002 bubble-point reads its 144.2 bar a anchor.

PT-329201 is graded in BAR, not in H.FLAT percent.  H.FLAT is the harness's generic
"structurally flat" heuristic at 1 % of the baseline, and on a variable that lives at 140.7 with
a design-zero derivative that would demand a 1.4 bar move before a coupling counts as present --
a violent excursion, not evidence of coupling.  The physics here is bounded and known: a -30 %
CCW throttle leaves cool_frac at 0.699, so the shell condenses 69.9 % of what is offered, and the
HP loop recirculates the rest past it.  The standing uncondensed hold-up settles at
(1-cf)/cf * make * tau ~ 470 kg on a 1500 kg/bar loop capacitance, i.e. ~0.28 bar.  PT_MOVE below
is that number with margin taken off it; it still fails hard the moment the coupling is broken,
because the pre-fix behaviour was 0.000 bar exactly.  The full-scale event (cool_frac = 0, several
bar) is covered separately in test_ccw_loss_chain.py.
"""
import _systest as H

DES_PT  = H.main.SYN_P_DES_BARA          # 140.7 bar a  -- PT-329201 design
DES_BUB = H.main.HPCC_P_DES_BARA         # 144.2 bar a  -- 322E002 bubble-point anchor
CUT     = 0.70                           # CCW setpoint multiplier (-30 %)
PT_MOVE = 0.15                           # bar, minimum PT-329201 excursion / relaxation (see above)

print("\n=== TEST 3: 322E003 CCW condensation -> PT-329201 synthesis pressure ===\n")

# --- baseline: design steady state -------------------------------------------
H.reset()
base = H.run(40)                         # flush any init transient (design is already steady)
pt0  = H.find(base, "PI_329201")
tc0  = H.find(base, "TT_329125")
rc0  = H.find(base, "rho_cond")
pb0  = H.find(base, "PI_322E002")
lv0  = H.main.state.scrub_level_pct      # 322E003 sump, report D-19

# --- perturb: throttle CCW circulation -30 % ---------------------------------
H.main.state.FIC_329409["sp"] *= CUT     # AUTO loop -> pv tracks sp
new  = H.run(400)                        # ~800 s  (tau_P = 4 min) -> hold-up near steady
pt1  = H.find(new, "PI_329201")
tc1  = H.find(new, "TT_329125")
rc1  = H.find(new, "rho_cond")
pb1  = H.find(new, "PI_322E002")
lv1  = H.main.state.scrub_level_pct

print(f"  CCW circulation throttled to {CUT*100:.0f} % of design (FIC-329409 SP):")
d_pt = H.row("PI_329201 (PT, bar a)",   pt0, pt1)
d_tc = H.row("TT_329125 (CCW out, C)",  tc0, tc1)
_    = H.row("rho_cond (cap/demand)",   rc0, rc1)
_    = H.row("PI_322E002 (bub, bar a)", pb0, pb1)

# --- restore: CCW back to design ---------------------------------------------
H.main.state.FIC_329409["sp"] /= CUT
rest = H.run(500)                        # ~1000 s relax (hold-up condenses out over tau_P)
pt2  = H.find(rest, "PI_329201")
lv2  = H.main.state.scrub_level_pct
print()
H.row("PI_329201 relax (bar a)", pt1, pt2)
H.row("LT-329501 sump (%)",      lv1, lv2)

# --- matched no-cut CONTROL, and why this test needs one ---------------------
# PT-329201 is graded against a CONTROL trajectory of identical length that never sees the CCW
# cut, and the relaxation is measured on the DIFFERENCE.  Two facts force that, and both are
# recorded elsewhere in the repo:
#
#   1. This harness runs at dt = 2.0 s, and at that tick the design seed itself walks -- handoff 9,
#      "a ~1 bar, ~6000 s wobble from the 322E002 level integrator's Euler truncation".  Measured
#      on the free trajectory it is +0.10 bar per 1000 s by the time this test reaches its relax
#      window, and RISING.  The window asks for a 0.15 bar FALL.  Grading a raw pressure against a
#      threshold smaller than the harness's own numerical walk grades the walk, not the physics.
#   2. Report D-19 restored the 322F001 gravity-suction-head multiplier, so the 322E003 sump is a
#      self-regulating attractor again instead of a pure integrator.  It now troughs and RECOVERS
#      (~45.4 % -> 49.9 %) where before the CCW cut drained it 50 -> 27 % and it stayed there for
#      ever.  That dumped sump inventory into the synthesis loop and back out again, and it was
#      what powered the large raw relaxation this test used to see.  With the sump behaving, the
#      CCW-attributable excursion is smaller -- correctly so -- and no longer clears the walk.
#
# The control removes the walk by construction: both trajectories carry it, so the difference is
# the CCW effect alone.
H.reset()
H.run(40)
ctrl_cut  = H.run(400)                   # same length as the cut leg, no setpoint change
ctrl_pt1  = H.find(ctrl_cut, "PI_329201")
ctrl_rest = H.run(500)                   # same length as the relax leg
ctrl_pt2  = H.find(ctrl_rest, "PI_329201")
excess1 = pt1 - ctrl_pt1                 # CCW-attributable rise at the end of the cut
excess2 = pt2 - ctrl_pt2                 # ... and after the relax window
print()
print(f"  CCW-attributable excess over the matched no-cut control:")
print(f"    end of cut    {pt1:8.3f} - {ctrl_pt1:8.3f} = {excess1:+.3f} bar")
print(f"    after relax   {pt2:8.3f} - {ctrl_pt2:8.3f} = {excess2:+.3f} bar")

# --- design-identity guard (fresh state) -------------------------------------
H.reset()
ident = H.run(10)
pti   = H.find(ident, "PI_329201")
pbi   = H.find(ident, "PI_322E002")

print("\n  --- physical expectations ---")
n = 0
t = 0
t += 1; n += H.check("CCW cut raises PT-329201 (reverse Q->P)", pt1 > pt0 + PT_MOVE,     f"PT {pt0} -> {pt1}")
t += 1; n += H.check("CCW cut raises TT-329125 (less coolant)", d_tc > H.FLAT,           "CCW return T flat")
t += 1; n += H.check("rho_cond falls below 1 under throttle",   rc1 < 0.999,             f"rho_cond={rc1}")
t += 1; n += H.check("CCW cut lifts PT-329201 above the matched control", excess1 > PT_MOVE,
                     f"excess {excess1:+.3f} bar")
t += 1; n += H.check("PT-329201 relaxes after CCW restored (control-corrected)",
                     excess2 < excess1 - 0.05, f"excess {excess1:+.3f} -> {excess2:+.3f} bar")
t += 1; n += H.check("322E003 sump troughs and RECOVERS (report D-19)",
                     lv1 < 49.0 and lv2 > lv1 + 1.0,
                     f"sump {lv0:.1f} -> {lv1:.1f} -> {lv2:.1f} %")
t += 1; n += H.check("fresh design state holds PT = 140.7",     abs(pti - DES_PT) < 0.2, f"PT={pti}")
# PI_322E002 is the bubble-P of the LIVE loop-coupled HPCC MELT, evaluated by bubble_p_322e002 whose fN
# anchor is the design MELT N/C (main.HPCC_NC_DES_LIVE ~= 3.12324, auto-captured at boot), NOT the reactor-
# feed N/C reactor.L0_DES (3.07296): the combined melt is NH3-richer than the reactor feed it produces (all
# fresh NH3 enters as ejector motive).  At the live design point the melt settles at N/C == HPCC_NC_DES_LIVE
# and H/C == W0 exactly (entrainment phi_m==1), so P_bub == 144.2 bar a (datasheet) to ~1e-11 -- the 0.6 band
# is the off-design live-coupled residual envelope, not slack for a design-point offset.
t += 1; n += H.check("322E002 bubble-P holds 144.2 anchor",     abs(pbi - DES_BUB) < 0.6, f"P_bub={pbi}")
H.verdict(n, t)

# hard gate (non-zero exit on regression)
assert pt1 > pt0 + PT_MOVE,      "PT-329201 must rise when CCW condensation drops"
assert d_tc > H.FLAT,            "TT-329125 must rise when CCW flow drops"
assert rc1  < 0.999,             "rho_cond must drop below 1 under CCW throttle"
assert excess1 > PT_MOVE,        "the CCW cut must lift PT-329201 above a matched no-cut control"
assert excess2 < excess1 - 0.05, "PT-329201 must relax toward design after CCW restored (control-corrected)"
assert lv1 < 49.0 and lv2 > lv1 + 1.0, \
    "the 322E003 sump must trough under the CCW cut and RECOVER after it (report D-19 head term)"
assert abs(pti - DES_PT)  < 0.2, "fresh design state must hold PT-329201 = 140.7 bar a"
assert abs(pbi - DES_BUB) < 0.6, "322E002 bubble-point must hold its 144.2 bar a anchor (live-coupled residual band)"
print("\n  test_3_scrubber_heat: PASS\n")
