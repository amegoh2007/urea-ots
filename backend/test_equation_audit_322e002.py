"""Regression gate for the EQUATION_AUDIT F-6 / TD-007 fix (322E002 HP carbamate condenser).

WHY THIS FILE EXISTS
--------------------
`HPCC_FRAC_GAS_DES` was a split fraction calibrated at ONE operating point and then frozen, which
made the condenser thermodynamically inert: raising the LP-steam pressure changed the shell duty and
the NTU outlet temperature but not one mole of condensate, and a synthesis-pressure excursion moved
nothing at all.  The boot pin could not see this -- it pins HPCC_UA at the design seed, where the
split is BY DEFINITION its calibrated value.

The fix binds an isothermal (T,P) Rachford-Rice flash anchored ON that calibration, then rate-limits
it through the interfacial film (`HPCC_TAU_FILL_MIN`), because 322E002 is mass-transfer limited, not
equilibrium limited (References/HPCC description.md Sections 5.2-5.3).  These tests assert:

  * design seed still publishes the calibrated split, BIT-EXACT   -> the pin contract is untouched
  * the equilibrium target is monotone in T and in P              -> the physics has the right sign
  * non-distributing species never flash                          -> Urea/Biuret and O2/CH4/H2
  * a shell-temperature move really does move the split           -> the finding itself
  * and the new T <-> split coupling does not self-excite         -> _disturbance_gate loop-gain check

Run from backend/:  python -m pytest test_equation_audit_322e002.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402

DT = 0.25
DIST = ("CO2", "NH3", "H2O", "N2")          # the distributing set (0 < phi_des < 1)


def _fresh(seconds=300.0):
    """Fresh design State, settled `seconds` of sim time; returns the last packet."""
    main.state = main.State()
    return _run(seconds)


def _run(seconds):
    out = None
    for _ in range(int(seconds / DT)):
        out = main.step_sim(DT)
    return out


def _des_feed():
    return main._HPCC_DES["feed_kmolh"]


# ------------------------------------------------------------------ the pin contract is untouched
def test_design_split_is_bit_exact_and_does_not_drift():
    """At the design seed the disturbance gate is shut, so the published split must be the
    calibrated vector to the LAST BIT -- not merely close.  Any drift here means the flash has
    leaked solver tolerance into the boot-pin contract."""
    a = _fresh(300.0)
    phi_a = a["HPCC_322E002"]["phi_gas"]
    assert main._disturbance_gate(main.state) == 0.0
    for k in main.MW_COMP:
        assert phi_a[k] == main.HPCC_FRAC_GAS_DES[k], (k, phi_a[k])
    b = _run(300.0)                                   # a second undisturbed window must not creep
    assert b["HPCC_322E002"]["phi_gas"] == phi_a
    assert b["HPCC_322E002"]["gas_th"] == a["HPCC_322E002"]["gas_th"]
    assert b["HPCC_322E002"]["liq_th"] == a["HPCC_322E002"]["liq_th"]


def test_flash_short_circuits_at_the_calibration_point():
    """Called exactly at (T_des, P_des) the flash must return the calibration itself, with no
    Rachford-Rice sweep at all -- this is what keeps the module-load and boot-pin passes bit-exact."""
    got = main._hpcc_flash_split(_des_feed(), main.HPCC_T_PROD_DES_C, main.SYN_P_DES_BARA)
    assert got == main.HPCC_FRAC_GAS_DES


# ------------------------------------------------------------------------- the physics has signs
def test_equilibrium_target_is_monotone_in_temperature():
    """Hotter melt -> carbamate dissociates -> MORE gas leaves.  Kp = p_NH3^2*p_CO2, so the
    dissociation-pressure slope is dH_carb/3 (Bennett 1953); the sign is what matters here."""
    feed = _des_feed()
    prev = None
    for T in (160.0, 165.0, 170.0, 175.0, 180.0):
        phi = main._hpcc_flash_split(feed, T, main.SYN_P_DES_BARA)
        if prev is not None:
            for k in DIST:
                assert phi[k] >= prev[k] - 1e-12, (k, T, prev[k], phi[k])
        prev = phi


def test_equilibrium_target_is_monotone_in_pressure():
    """Higher synthesis pressure -> K ~ 1/P -> MORE condensation -> LESS gas.  This is the leg the
    frozen split got completely wrong: a pressure excursion used to move nothing."""
    feed = _des_feed()
    prev = None
    for P in (120.0, 130.0, 140.7, 150.0, 160.0):
        phi = main._hpcc_flash_split(feed, 175.0, P)
        if prev is not None:
            for k in DIST:
                assert phi[k] <= prev[k] + 1e-12, (k, P, prev[k], phi[k])
        prev = phi


def test_non_distributing_species_never_flash():
    """Urea/Biuret (phi_des == 0) must never boil and O2/CH4/H2 (phi_des == 1) must never condense,
    at ANY temperature or pressure -- they sit structurally outside the Rachford-Rice set."""
    feed = _des_feed()
    for T in (120.0, 170.0, 220.0):
        for P in (80.0, 140.7, 200.0):
            phi = main._hpcc_flash_split(feed, T, P)
            for k in ("Urea", "Biuret"):
                assert phi[k] == 0.0, (k, T, P, phi[k])
            for k in ("O2", "CH4", "H2"):
                assert phi[k] == 1.0, (k, T, P, phi[k])


# ---------------------------------------------------------------- the finding, on the live plant
def test_shell_temperature_move_now_moves_the_split():
    """THE finding.  Open the MP supply valve (PIC-329204 to MAN first, or AUTO drags it back): the
    LP header climbs, the shell runs hotter, TT-322010 rises -- and the condensate split must follow.
    With the frozen vector every one of these assertions was impossible: phi was a constant."""
    t = _fresh(300.0)
    phi0 = dict(t["HPCC_322E002"]["phi_gas"])
    gas0 = t["HPCC_322E002"]["gas_th"]
    s = main.state

    s.steam.pic204_mode = "MAN"
    s.steam.valve_supply_pct = 62.0
    tp = []
    for _ in range(10):
        t = _run(60.0)
        tp.append(s.tlag["HPCC_TPROD"])
    phi1 = t["HPCC_322E002"]["phi_gas"]

    assert main._disturbance_gate(s) > 0.0                       # the gate really did open
    assert tp[-1] > main.HPCC_T_PROD_DES_C                       # hotter shell -> hotter product
    for k in DIST:
        assert phi1[k] > phi0[k], (k, phi0[k], phi1[k])          # ... and MORE gas leaves
    assert t["HPCC_322E002"]["gas_th"] > gas0 + 1.0
    # the coupling must SETTLE, not ring: the last five minutes span well under a degree
    assert max(tp[-5:]) - min(tp[-5:]) < 0.5, tp[-5:]


def test_split_is_a_partition_so_total_mass_is_invariant():
    """C1.  Wherever the flash puts the phase boundary, gas + liq must still equal the tube-side
    feed -- the split moves material between the two products, it never creates or destroys any.
    dt is set large so the film relaxation lands straight on the equilibrium target."""
    g = main.stripper_322e001(main.CO2_DES_KGH / 1000.0, main.STRIP_STEAM_T_DES_C,
                              main.STRIP_P_DES_BARA)
    l = main.ejector_322f001(main.EJ_MOTIVE_NH3_DES, main.EJ_MOTIVE_T_DES_C, main.EJ_OPEN_DES)
    seen, feed_ref = [], None
    for T in (160.0, 170.0, 185.0):
        h = main.hpcc_322e002(g, l, gate=1.0, t_prod_prev=T, p_loop=main.SYN_P_DES_BARA, dt=1e9)
        feed_kgh = sum(h["feed_kmolh"][k] * main.MW_COMP[k] for k in main.MW_COMP)
        assert abs(h["gas_kgh"] + h["liq_kgh"] - feed_kgh) < 1e-6 * feed_kgh
        if feed_ref is not None:
            assert abs(feed_kgh - feed_ref) < 1e-9      # same feed at every temperature
        feed_ref = feed_kgh
        seen.append(h["gas_kgh"])
    assert seen[0] < seen[1] < seen[2]                  # ... and the split really did move


def test_split_does_not_self_excite_on_an_nc_disturbance():
    """The new T -> K -> phi -> q_carb -> T path must stay negative feedback: hotter melt -> more
    gas leaves -> less CO2 absorbed -> smaller exotherm -> cooler.  If the sign were wrong (or the
    gain above 1) this is where the _disturbance_gate runaway would show up.

    Window widened from 10 to 25 minutes when the eta_P dead lever was fixed (audit TD-006 work).
    That fix added a feedback path the plant did not previously have -- loop pressure now reaches
    the stripper split -- so this disturbance carries one more lag than it used to.  Measured over
    40 minutes, p_syn ramps 141.7 -> 144.2 bar a and saturates at its SYN_P_MAX_BARA ceiling around
    minute 6; the old 10-minute window straddled exactly that saturation event, which is why it
    read a 0.73 span.  Past it the trace settles monotonically (span 0.027 by minute 40, per-minute
    steps decaying 0.44 -> 0.0066).

    The assertion is deliberately made STRONGER rather than merely looser: the span check now runs
    on a settled window AND the step sizes must be shrinking.  A genuine runaway fails the second
    check no matter how long the window is, so widening the window cannot mask one.
    """
    _fresh(300.0)
    s = main.state
    s.ratio_SP = 0.92 * main.RATIO_SP_DES
    tp = []
    for _ in range(25):
        t = _run(60.0)
        tp.append(s.tlag["HPCC_TPROD"])

    h = t["HPCC_322E002"]
    assert h["gas_th"] > 0.0 and h["liq_th"] > 0.0
    for k in main.MW_COMP:
        assert 0.0 <= h["phi_gas"][k] <= 1.0, (k, h["phi_gas"][k])
    assert max(tp[-5:]) - min(tp[-5:]) < 0.5, tp[-5:]             # bounded, converging
    # ... and converging for the right reason: late steps must be smaller than early ones.
    early = sum(abs(tp[i] - tp[i - 1]) for i in range(1, 6))
    late = sum(abs(tp[i] - tp[i - 1]) for i in range(len(tp) - 5, len(tp)))
    assert late < early, f"step sizes are not decaying -- self-excitation (early {early}, late {late})"
