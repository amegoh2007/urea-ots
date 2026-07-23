"""Regression gate for TD-014 — the open-loop temperature integrator in the 323 concentration train.

WHAT THE DEFECT WAS
-------------------
Three stages compute their vapour rate as "whatever the available duty can boil":

    m_vap = M_DES * (q_avail / Q_DES)

and each stage's latent constant is BACK-SOLVED from that same design duty,
`λ = Q_DES / (M_DES/3600)`, so that dT/dt = 0 at the seed.  Put the two together and the
temperature ODE collapses:

    P = q_avail − m_vap·λ/3600
      = q_avail · (1 − M_DES·λ/(3600·Q_DES))
      = q_avail · (1 − 1)
      = 0        IDENTICALLY, for every q_avail, at every load.

The stage temperature therefore had NO input.  Anything the temperature controller did to the
reboiler was cancelled exactly by the boil-up it produced, so the PV never moved off the 1e-5 °C
residue left by the boot settle, and the velocity-form integral walked the steam valve down
forever.  Because a velocity increment is Kc·(dt/Ti)·err, the walk RATE is independent of dt —
which is precisely the tick-invariance that made TD-014 look like a model property.

Measured before the fix: w_f010 fell on a perfectly linear −0.0067 pp/h ramp that crossed the
0.10 pp assertion in test_equation_audit_species.py at ≈ 9.5 h, beyond every test's horizon, while
the stripper bottoms feeding it were bit-flat for 6 h.

THE FIX
-------
The liquid sits at its BUBBLE POINT, so the duty not spent boiling walks the holdup toward it over
the stage's own residence time — the closure 323F004 already used.  Substituted back it gives
exactly dT/dt = (T_bub − T)/τ, so energy is still conserved and the temperature is a real state:

  * 323C003 — bubble point rides the live column pressure (frozen composition offset: its vapour is
    33 % NH3 / 50 % CO2, so the offset is a 9.8 °C DEPRESSION that Raoult-on-water cannot produce);
  * 323F010 — fixed 0.46 bar a vacuum boundary, so the lever is CONCENTRATION, via Raoult.

Run from backend/:  python -m pytest test_equation_audit_td014.py -q
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


# ------------------------------------------------------- the cancellation is real, and documented
def test_the_latent_constants_really_do_cancel_the_available_duty():
    """This is the DEFECT's own identity, asserted rather than described.  It stays exactly 1.0 —
    that is what makes the back-solve consistent — so the fix cannot be "break the cancellation",
    it has to be "give the temperature a driver that survives it"."""
    for tag, m_des, lam, q_des in (
            ("323C003", main.R323_M305_DES, main.R323_LAMBDA_305, main.R323_Q305_DES_KW),
            ("323F010", main.R323_MEVAP_DES, main.R323_EVAP_LAMBDA, main.R323_QEVAP_DES_KW),
            ("324E001", main.R324_V1_DES, main.R324_LAM_V1, main.R324_Q1_DES_KW),
            ("324E003", main.R324_V2_DES, main.R324_LAM_V2, main.R324_Q2_DES_KW)):
        assert abs(m_des * lam / (3600.0 * q_des) - 1.0) < 1e-12, tag


# ------------------------------------------------------------------- the ramp is actually stopped
def test_the_323_train_reaches_a_real_steady_state():
    """The headline.  Sample w_f010 over the last half hour of a 3 h run and require the slope to be
    zero to well inside the old ramp.  −0.0067 pp/h was the measured defect; 1e-4 pp/h is a 67×
    margin and still an order of magnitude below anything an operator could see."""
    _fresh()
    _run(9000.0)                                    # 2.5 h: past the genuine settling transient
    pts = []
    for k in range(6):
        _run(300.0)
        pts.append((k * 300.0 / 3600.0, 100.0 * main.state.w_f010["Urea"]))
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    den = sum((p[0] - mx) ** 2 for p in pts)
    slope = sum((p[0] - mx) * (p[1] - my) for p in pts) / den
    assert abs(slope) < 1e-4, "w_f010 still drifting at %.6f pp/h" % slope
    assert abs(pts[-1][1] - 80.00) < 0.10, pts[-1][1]      # and it settles ON the PFD-317 anchor


def test_the_323_steam_valves_stop_walking():
    """The mechanism, measured at its source.  Before the fix PIC-329202 fell 0.0104 % per hour and
    PIC-329208 0.0085 %/h, without limit.  Both must now be stationary."""
    _fresh()
    _run(7200.0)
    a02 = main.state.PIC_329202["op"]
    a08 = main.state.PIC_329208["op"]
    _run(1800.0)
    assert abs(main.state.PIC_329202["op"] - a02) < 1e-6, main.state.PIC_329202["op"] - a02
    assert abs(main.state.PIC_329208["op"] - a08) < 1e-6, main.state.PIC_329208["op"] - a08


def test_the_column_and_pre_evaporator_hold_their_setpoints():
    _fresh()
    _run(7200.0)
    assert abs(main.state.r323_c003_T - main.R323_C003_T_SP_C) < 1e-3
    assert abs(main.state.r323_f010_T - main.R323_F010_T_SP_C) < 1e-3


# --------------------------------------------------------------- the bubble-point model itself
def test_bubble_point_anchors_are_bit_exact():
    """Every call site uses the DEPARTURE  T_des + [T_bub(live) − T_bub(design)], so at the design
    composition the bracket must be a literal 0.0 — not a tolerance, or the seed moves."""
    assert main.bubble_T_raoult(main.R323_F010_P_BARA, main.W_S317) == main.R323_F010_TBUB_DES
    assert main.bubble_T_raoult(main.R324_F001_P_BARA, main.W_S401) == main.R324_E001_TBUB_DES
    assert main.bubble_T_raoult(main.R324_F003_P_BARA, main.W_S402) == main.R324_E003_TBUB_DES


def test_raoult_reproduces_the_pfd_bubble_points_with_nothing_fitted():
    """The corroboration.  Raoult has no adjustable parameter, so agreement with the licensor's own
    (composition, pressure, temperature) triplets is evidence, not curve-fitting.  It must stay
    within 8 °C of a 20-90 °C elevation, i.e. account for the great majority of it."""
    for w, P, pfd_T in ((main.W_S317, 0.46, 99.0),
                        (main.W_S401, 0.33, 130.0),
                        (main.W_S402, 0.131, 140.0)):
        raoult = main.bubble_T_raoult(P, w)
        elev = pfd_T - main.tsat_steam(P)
        assert abs(raoult - pfd_T) < 8.0, (raoult, pfd_T)
        assert abs(raoult - pfd_T) < 0.40 * elev, "captures less than 60 %% of a %.1f C elevation" % elev


def test_raoult_is_excluded_exactly_where_it_fails():
    """The other half of the argument, and the reason 323C003/323F004 keep the frozen-offset form:
    their liquors carry NH3 and CO2, whose partial pressures set the bubble point.  Raoult-on-water
    overshoots by tens of degrees there — assert that, so nobody "unifies" the two forms later."""
    for w, P, pfd_T in ((main.W_S314, main.R323_C003_P_BARA, main.R323_C003_T_SP_C),
                        (main.W_S319, main.R323_F004_P_BARA, main.R323_F004_T_SP_C)):
        assert main.bubble_T_raoult(P, w) - pfd_T > 10.0, (
            "Raoult now agrees here; the justification for the frozen-offset form has changed")


def test_x_water_mol_is_a_real_mole_fraction():
    assert abs(main.x_water_mol({"H2O": 1.0}) - 1.0) < 1e-12
    assert main.x_water_mol(main.W_S402) < main.x_water_mol(main.W_S401) < main.x_water_mol(main.W_S317)
    # 80 % urea BY MASS is a minority of the MOLES -- the conversion is the whole point
    assert 0.40 < main.x_water_mol(main.W_S317) < 0.50


# --------------------------------------------------------------- TD-015: the unit-324 half, closed
def test_the_unit_324_stages_carry_the_same_closure():
    """324E001/324E003 had the identical defect and are now fixed the same way.  Closing it needed
    the controllers retuned as well: Kc = 2.0 / Ti = 120 was inherited from a plant whose
    temperature ODE was identically zero, so it described nothing.  With a real plant the measured
    gain is +8.3 °C/bar on both loops (central difference over 1 h means, master in MAN), which made
    the old Kc a loop gain of 16.7."""
    assert main.State().TIC_324001["Kc"] == 0.02
    assert main.State().TIC_324002["Kc"] == 0.02
    assert main.State().TIC_324001["Ti"] == 360.0
    _fresh()
    _run(600.0)
    for tag in ("E001", "E003"):
        d = main._DIAG[tag]
        assert "relax" in d and "Tbub" in d
        assert d["v"] == min(d["conc"], d["duty"])


def test_the_324_evaporator_temperatures_stay_bounded():
    """The residual is a slow limit cycle from the `min(v_conc, v_duty)` branch switching, not a
    walk.  Measured 16 h envelope at this tuning: 0.25 °C on 324E001, 0.88 °C on 324E003 -- against
    a valve that used to walk without limit.  Bound it at 3 h, generously, so the gate fires on a
    regression rather than on the cycle it is documenting."""
    _fresh()
    _run(3600.0)
    t1lo = t1hi = main.state.r324_e001_T
    t3lo = t3hi = main.state.r324_e003_T
    for _ in range(8):
        _run(900.0)
        t1lo, t1hi = min(t1lo, main.state.r324_e001_T), max(t1hi, main.state.r324_e001_T)
        t3lo, t3hi = min(t3lo, main.state.r324_e003_T), max(t3hi, main.state.r324_e003_T)
    assert t1hi - t1lo < 0.6, (t1lo, t1hi)
    assert t3hi - t3lo < 1.5, (t3lo, t3hi)
    assert abs(t1hi - main.R324_E001_T_SP_C) < 1.0 and abs(t1lo - main.R324_E001_T_SP_C) < 1.0
    assert abs(t3hi - main.R324_E003_T_SP_C) < 1.5 and abs(t3lo - main.R324_E003_T_SP_C) < 1.5
