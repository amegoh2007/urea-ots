"""handoff.md: add remediation slot 10 and re-point the next-steps list."""
import io

P = "handoff.md"
raw = io.open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")

SLOT = r"""### Remediation slot 10 — TD-014 root cause, TD-013 closed, cp made a property (this session)

**TD-014 was an open-loop temperature integrator, and the operator's stream map is what found it.**
Walking 207 -> 208 -> 301/311 -> 313 -> 302/314 -> 319 -> 317 with every node instrumented
(`scratchpad/probe_td014_trace.py`) showed the stripper bottoms **bit-flat for 6 h** while `w_c003`
fell -0.0041 pp/h. So nothing rides in on the feed -- the ramp is born in the stage. A CSTR with a
2-minute residence and constant inputs cannot ramp for 14 h, so an input had to be moving: the
boil-up, falling 5.97 kg/h per hour, perfectly linearly (`probe_td014_c003.py`).

The identity (`probe_td014_ops.py` asserts it, and `test_equation_audit_td014.py` keeps it asserted):

    m_vap = M_DES*(q_avail/Q_DES)   and   lambda = Q_DES/(M_DES/3600)
    =>  P = q_avail - m_vap*lambda/3600 = q_avail*(1 - 1) = 0   IDENTICALLY, at every load

The stage temperature had **no input**. TIC-323007 was integrating against zero gain and walked
PV-329202 down forever; because a velocity increment is Kc*(dt/Ti)*err the walk RATE is
dt-independent, which is exactly the "tick-invariance" that made this look like physics. It is
one-sided (hence monotone) because the composition-split branch of the `min()` caps the other way.

**Fix:** the bubble-point relaxation 323F004 already used, giving `dT/dt = (T_bub - T)/tau`.
323C003's bubble point rides the live column pressure; 323F010's rides **composition** via Raoult on
water -- the real physics of a fixed-vacuum evaporator, and it makes TIC-323012 the concentration
controller it is on the plant. Raoult is quoted, not fitted, and captures 89-107 % of a 20-90 C
elevation against the licensor's own (w, P, T) triplets. It is **excluded** at 323C003/323F004,
whose NH3/CO2-bearing liquors it overshoots by 33 C and 16 C -- a test asserts that overshoot so
nobody unifies the two forms later.

**Result:** every 323 node's least-squares slope is now **exactly 0.0** over the second half of a
6 h run; PIC-329202 and PIC-329208 are flat to five decimals. `w_f010` settles at 79.9635 % -- the
0.037 pp under the PFD-317 anchor is where the LIVE stripper bottoms put it (55.838 % against a
tabulated 55.867 %), not a drift.

**324E001 / 324E003 are NOT fixed -- see TD-015.** They carry the same identity, but switching the
closure on gives loops tuned against a zero-gain plant a real gain and they diverge (T_e003 -> 138.5
C, PV-329212 -> 86.6 % within 6 h). With both masters in **MAN** the same stages stay within 0.02 C
of design, which is the proof it is tuning and not the model. The closure was reverted there and the
live driver is published every tick as `_DIAG['E001']['dTbub']` so the gap stays measurable.

**TD-013 CLOSED, option (c).** With the inlet stationary the only argument for the 323D002 strength
pin was gone. `s.w_d002` is a plain `sol_advance` now: the tank tracks 323F010 with its own
residence-time lag, the last composition-blind node between reactor and evaporators is open, and a
C2 violation goes with it (`sol_pin_strength` fabricated +0.600 kg urea per 1000 kg holdup per call).
The design-point test that asserted `|w_D002 - 80.00| < 1e-6` was **asserting the pin, not physics**
-- it now carries the inlet's 0.10 pp band plus a stronger assertion that the two agree to 1e-4.

**323D002 rebuilt to its real topology** (operator brief + `References/323D002.md`): Comp I 80 m3
active (every nozzle, LIC-323507, TI-323008, 323P003 suction), Comp II 300 m3 passive (LI-323504,
indication only, dry in normal operation), and the **field tie-in spool** between them as an
operator boolean -- `s.HV_323D002_TIE`, `xv_toggle` id `323D002TIE`, clickable on screen 323-1 under
the tank. Shut: independent, Comp II stranded. Open: connected vessels sharing a *head*, so an equal
level fraction, and 323P003 draws the pool. Opening against a dry Comp II collapses a 10 % head from
80 m3 into 380 m3 -- **10 % -> 2.1 %**, near the pump's cavitation limit. That is the scenario the
button exists for. Three constants corrected from source: LIC-323507 SP **65 % -> 10 %** (the
compartment exists to hold residence under ~6 min so biuret cannot form; 65 % declared a 39-minute
residence), rho **1300 -> 1151 kg/m3** (PFD stream 315/317), Comp II seed **50 % -> 0 %**.
TI-323008 became a real state instead of an echo of the upstream separator.

**cp is a property now, not a section constant.** One lumped 2.5 kJ/kg.K covered the whole 323 train
(44 % @ 40 C to 80 % @ 99 C -- design values 3.029 / 2.760 / 2.679 / 2.500 / 3.248, a 30 % spread)
and one 4.0 covered every aqueous vessel from 40 to 200 C. Both replaced by departures anchored on
their own design point, so each returns the licensor's constant **bit-exactly** at the seed and every
back-solved lambda/UA and the boot-pinned `A328_LAMBDA_ABS` are untouched. `R3232_CP = 3.0` is
deliberately **left alone**: 323E003/323E011 carry a strong ammonium-carbamate liquor, not water, so
`aqueous_cp` is the wrong correlation and converting it would be a fabrication.

**Equipment tags verified, and the brief had two digit slips.** The references are unambiguous:
**322**E003 is the HP Scrubber (`References/322E003 HP Scrubber Describtion.md`;
`Urea_Operating_Manual_Helwan.md`), **323**E003 is the LP Carbamate Condenser
(`References/323E003 323D001 323P001 Datasheets.md`; `328E021 ...` table), and **322**C001 is the LP
Absorber (`References/322P002 322E006 322C001 Datasheets.md`). There is no 323C001 anywhere in the
reference set. The code already matches the references -- nothing was changed.

**New gates:** `test_equation_audit_td014.py` (9), `test_equation_audit_td013_d002.py` (11),
`test_equation_audit_c10_live_cp.py` (7). Pin unmoved throughout: `leaves 25 / keys 15 / diffs 0`.

"""

ANCH = "## How to gate"
if s.count(ANCH) != 1:
    raise SystemExit("gate anchor not unique")
s = s.replace(ANCH, SLOT + ANCH)

OLD_NEXT = """3a. **TD-012 / C10 — PARTIALLY closed 2026-07-23.** Urea-solution cp and density are live
   correlations and unit 324 uses them per-location. Still open: the **aqueous/water** side (the
   PFD's >150 °C density row runs ~4 % above physical water — analysed in TD-012, unchanged) and
   the volumetric-controller densities. `urea_soln_rho` is in place as the vehicle for that work."""
NEW_NEXT = """3a. **TD-012 / C10 — cp side CLOSED, density side still open.** Every cp in units 323, 324 and
   328 and at 322C001 is now a per-stream / per-vessel departure. Still open: the **density** work —
   the PFD's >150 °C row runs ~4 % above physical water (analysed in TD-012, unchanged), the
   volumetric-controller densities (`RHO_744_KGM3`, `RHO_741_KGM3`, `R328_C002_RHO`,
   `R328_C004_RHO`), the four remaining dead density constants, and `R3232_CP`, which needs a
   *sourced carbamate* cp rather than water's. `urea_soln_rho` / `aqueous_rho` are the vehicles.
3b. **TD-015 — the unit-324 half of TD-014.** 324E001/324E003 still carry the degenerate temperature
   ODE. Physics understood and written down; blocked on retuning TIC-324001/TIC-324002, which were
   tuned against a zero-gain plant. Do it in this order: (a) add the bubble-point relax to
   `v1_duty`/`v2_duty` (the `R324_E*_TBUB_DES` anchors and the `_DIAG[...]['dTbub']` driver already
   exist); (b) from a CLEAN design-state boot, step each master in MAN and measure K_p and tau —
   the one step test done so far was contaminated by an already-diverged run and is unusable;
   (c) lambda-tune at lambda ~ 3*tau and record it in `Master_PID_Tuning_Constants.md`; (d) consider
   dropping the `v_conc` concentration cap, which stops doing physical work once T_bub is closed."""
if s.count(OLD_NEXT) != 1:
    raise SystemExit("next-steps anchor not unique")
s = s.replace(OLD_NEXT, NEW_NEXT)

if crlf:
    s = s.replace("\n", "\r\n")
io.open(P, "w", encoding="utf-8", newline="").write(s)
print("patched", P)
