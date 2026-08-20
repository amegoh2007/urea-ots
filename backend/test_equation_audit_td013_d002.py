"""Regression gate for TD-013 — 323D002 as the two-compartment vessel it actually is.

WHAT CHANGED
------------
1. THE STRENGTH PIN IS GONE.  `sol_pin_strength(..., R324_W_IN)` used to rewrite the tank's
   urea/water pair to exactly 0.80 on every tick.  That made it the last composition-blind node
   between the reactor and the evaporators (audit B1: a +4 % NH3 step on the reactor overflow moved
   222 of 1162 telemetry leaves but 0 of the 66 belonging to unit 324), and it fabricated +0.600 kg
   of urea per 1000 kg of holdup per call — a straight C2 violation.  It survived only because
   w_f010, the tank's single inlet, was on the unbounded TD-014 ramp.  TD-014 is fixed, the inlet is
   stationary, and the pin has no remaining job.

2. THE TWO COMPARTMENTS ARE MODELLED SEPARATELY, with the field tie-in spool the operator has:
     Comp I   80 m3, ACTIVE   — every nozzle, LIC-323507, TI-323008, 323P003 suction
     Comp II 300 m3, PASSIVE  — LI-323504 indication only, dry in normal operation, fills by weir
     tie shut  -> independent; anything that spilled into Comp II is stranded there
     tie open  -> connected vessels; levels equalise and 323P003 draws the pooled inventory

3. LIC-323507's setpoint is 10 %, not 65 %.  The small compartment exists to hold residence under
   ~6 min so biuret cannot form (References/323D002.md §3.2); a mid-range level defeats it.

4. R323_D002_RHO is the PFD's own 1151 kg/m3 for stream 315/317, not 1300.

Run from backend/:  python -m pytest test_equation_audit_td013_d002.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402

DT = 1.0


def _fresh():
    main.state = main.State()


def _run(seconds):
    out = None
    for _ in range(int(seconds / DT)):
        out = main.step_sim(DT)
    return out


# ------------------------------------------------------------------- the pin is actually gone
def test_the_tank_strength_is_no_longer_pinned():
    """If the pin came back this lands on exactly 0.80 to the bit, which is the tell."""
    _fresh()
    _run(3600.0)
    w = main.state.w_d002["Urea"]
    assert w != main.R324_W_IN, "323D002 is pinned again"
    assert abs(w - main.R324_W_IN) < 1e-3, w          # ...but still on the PFD anchor


def test_the_tank_tracks_its_single_inlet():
    """One inlet, one outlet, no vapour, no reaction: at steady state the tank MUST equal 323F010.
    That is the whole physical content of this vessel and the pin was hiding whether it held."""
    _fresh()
    _run(7200.0)
    assert abs(main.state.w_d002["Urea"] - main.state.w_f010["Urea"]) < 1e-4


def test_the_tank_lags_a_step_instead_of_following_it_instantly():
    """The point of dropping the pin was to get the holdup dynamics back.  Push the inlet and the
    tank must move in the right direction but NOT arrive in one tick."""
    _fresh()
    _run(3600.0)
    w0 = main.state.w_d002["Urea"]
    main.state.w_f010 = {k: v for k, v in main.state.w_f010.items()}
    main.state.w_f010["Urea"] += 0.02                 # +2 pp step on the inlet
    main.state.w_f010["H2O"] -= 0.02
    _run(60.0)
    w1 = main.state.w_d002["Urea"]
    assert w1 > w0, "tank did not respond to its inlet at all"
    assert w1 - w0 < 0.02, "tank followed the step with no holdup lag"


# ----------------------------------------------------------------------- compartment topology
def test_compartment_two_is_dry_and_passive_in_normal_operation():
    _fresh()
    t = _run(3600.0)
    d = t["RECIRC_323"]["D002"]
    assert d["LI_323504"] == 0.0, d["LI_323504"]
    assert abs(d["LI_323507"] - main.R323_D002_LVL_SP) < 2.0, d["LI_323507"]
    assert d["HV_tie"] is False


def test_the_active_compartment_holds_the_licensor_residence_time():
    """80 m3 at 10 % against an 80.6 m3/h feed is under 6 minutes.  This is the biuret constraint
    the compartmentalisation exists to satisfy, asserted rather than assumed."""
    vol_active = main.R323_D002_VOL_I_M3 * main.R323_D002_LVL_SP / 100.0
    feed_m3h = main.R323_M317_DES / main.R323_D002_RHO
    assert vol_active / feed_m3h * 60.0 < 6.0, vol_active / feed_m3h * 60.0


def test_density_is_the_pfd_value():
    assert main.R323_D002_RHO == 1151.0
    # and the 80 m3 / 300 m3 split is the plant's, carried straight into the mass spans
    assert main.R323_D002_M_TIE_FULL == main.R323_D002_M_I_FULL + main.R323_D002_M_II_FULL


def test_the_level_is_a_volume_measurement_on_a_live_density():
    """AUDIT C10.  A level gauge measures VOLUME.  The spans used to be mass spans on a frozen
    1300 kg/m3, so a tank of thinner (hotter or weaker) liquor read low by exactly the density
    error while the operator saw the same inventory.  The steel volumes do not move; what a
    kilogram occupies does."""
    main.state = main.State()
    t = _run(1800.0)
    d = t["RECIRC_323"]["D002"]
    # design anchor: 10 % of 80 m3 is the licensor's 8 m3 active volume
    assert abs(d["m3_comp1"] - 8.0) < 0.05, d["m3_comp1"]
    assert abs(d["LI_323507"] - main.R323_D002_LVL_SP) < 0.5, d["LI_323507"]
    assert abs(d["rho_kgm3"] - main.R323_D002_RHO) < 1.0, d["rho_kgm3"]
    # and the density is live, not the constant: warm the tank and it must thin out
    rho0 = main.urea_soln_rho(0.80, 99.0, main.R323_D002_RHO)
    assert rho0 == main.R323_D002_RHO                       # anchored, bit-exact at design
    assert main.urea_soln_rho(0.80, 130.0, main.R323_D002_RHO) < rho0
    assert main.urea_soln_rho(0.94, 99.0, main.R323_D002_RHO) > rho0


# ------------------------------------------------------------------------- the tie-in spool
def test_opening_the_tie_equalises_the_levels_and_collapses_the_head():
    """The hazard the button exists to train.  With Comp II dry, opening the spool spreads a 10 %
    Comp-I head over 380 m3 -- the level collapses to about 2 % and 323P003 is near cavitation."""
    _fresh()
    _run(3600.0)
    before = main.state.r323_d002_M_I / main.R323_D002_M_I_FULL * 100.0
    main.state.HV_323D002_TIE = True
    t = _run(1.0)
    d = t["RECIRC_323"]["D002"]
    assert abs(d["LI_323507"] - d["LI_323504"]) < 0.1, "connected vessels must read one level"
    assert d["LI_323507"] < before / 3.0, (before, d["LI_323507"])
    assert d["HV_tie"] is True


def test_closing_the_tie_strands_whatever_is_in_compartment_two():
    """The other half: shut the spool and Comp II keeps its inventory with no way out, while
    LIC-323507 refills Comp I on its own.  That stranded volume is the operator's problem, and the
    model has to show it rather than quietly draining it."""
    _fresh()
    _run(3600.0)
    main.state.HV_323D002_TIE = True
    _run(3600.0)
    main.state.HV_323D002_TIE = False
    stranded = main.state.r323_d002_M_II
    assert stranded > 1000.0, stranded
    _run(3600.0)
    assert abs(main.state.r323_d002_M_II - stranded) < 1e-6, "Comp II drained with the tie shut"


def test_the_pooled_volume_is_one_well_mixed_composition():
    _fresh()
    _run(3600.0)
    main.state.HV_323D002_TIE = True
    _run(60.0)
    for k in main.SOL_SPECIES:
        assert abs(main.state.w_d002[k] - main.state.w_d002_II[k]) < 1e-12, k


def test_the_operator_command_is_wired():
    _fresh()
    _run(60.0)
    assert main.state.HV_323D002_TIE is False
    main.handle_cmd({"type": "xv_toggle", "id": "323D002TIE"})
    assert main.state.HV_323D002_TIE is True
    main.handle_cmd({"type": "xv_toggle", "id": "323D002TIE"})
    assert main.state.HV_323D002_TIE is False


# ------------------------------------------------------------------------------ TI-323008
def test_the_tank_has_its_own_temperature_state():
    """TI-323008 used to publish the upstream separator's temperature verbatim, so the tank had no
    thermal inertia and its LOW-temperature alarm -- the crystallisation warning -- could never lag
    or damp anything.  It is a real state now."""
    _fresh()
    _run(1800.0)
    assert abs(main.state.r323_d002_T - main.R323_F010_T_SP_C) < 1e-3
    main.state.r323_f010_T -= 10.0                      # cold shock on the inlet
    _run(30.0)
    assert main.state.r323_d002_T < main.R323_F010_T_SP_C          # it responds
    assert main.state.r323_d002_T > main.R323_F010_T_SP_C - 10.0   # ...but not instantly
