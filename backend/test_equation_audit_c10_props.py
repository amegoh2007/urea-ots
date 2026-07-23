"""Audit C10 -- urea-solution density and cp are properties, not constants.  Plus the audit-B1
ripple break that shared a root cause with them.

Before this, one cp (2.5 kJ/kg.K) and a set of frozen densities covered every urea solution in the
plant, from 44 % urea in LP recirculation to 97.71 % melt leaving Evaporator II.  The error was
largest exactly where the model does its most important work, because the evaporation train's
whole purpose is to change the composition.

Provenance:
  * cp is BACK-SOLVED (CLAUDE.md §1 permits sourced or back-solved, never guessed): cp_water from
    steam tables, cp_urea fixed by requiring the mixing rule to reproduce the model's own
    R323_CP_SOLN at the design composition.  The 2.0704 kJ/kg.K that falls out matches the
    published molten-urea value (~2.0-2.1) independently -- that is the corroboration.
  * rho is REGRESSED FROM THE PFD, which CLAUDE.md §0 makes the strict source: 12 urea-solution
    streams, 34-98 % urea, 40-183 C.
"""
import main as m


# ------------------------------------------------------------------ the bit-exactness contract
def test_cp_returns_the_design_anchor_bit_exactly():
    """Both correlations are applied as a DEPARTURE from an existing anchor, so at the design
    composition the bracket is a literal 0.0 and anchor + 0.0 == anchor.  Not a tolerance."""
    assert m.urea_soln_cp(m.C10_W_DES, m.C10_T_DES) == m.R323_CP_SOLN
    assert m.R324_CP_FEED1 == m.R324_CP_SOLN


def test_rho_returns_whatever_anchor_the_caller_brought():
    """Each call site keeps its own PFD-published design density and gains only the slopes."""
    for anchor in (1151.0, 1200.0, 933.0, 1092.0):
        assert m.urea_soln_rho(m.C10_W_DES, m.C10_T_DES, anchor) == anchor


# ------------------------------------------------------------------------- physical direction
def test_cp_falls_as_the_solution_concentrates():
    """Urea melt has a much lower cp than water, so concentrating must LOWER cp.  A single
    constant cannot express this, which is the whole defect."""
    weak = m.urea_soln_cp(0.44, 100.0)
    mid = m.urea_soln_cp(0.80, 100.0)
    strong = m.urea_soln_cp(0.9771, 100.0)
    assert weak > mid > strong
    assert 1.8 < strong < 2.4, f"97.71 % melt cp {strong:.3f} is outside the plausible band"


def test_cp_of_pure_water_matches_the_steam_tables():
    assert abs(m.urea_soln_cp(0.0, 100.0) - m.cp_water_kjkgk(100.0)
               - (m.R323_CP_SOLN - m._CP_RAW_DES)) < 1e-12
    assert abs(m.cp_water_kjkgk(20.0) - 4.182) < 0.01
    assert abs(m.cp_water_kjkgk(100.0) - 4.216) < 0.01
    assert abs(m.cp_water_kjkgk(140.0) - 4.285) < 0.01


def test_back_solved_urea_cp_matches_the_published_molten_value():
    """The corroboration.  Nothing forced this number to be physical -- it fell out of requiring
    the mixing rule to reproduce the model's own design constant."""
    assert 2.0 <= m.CP_UREA_MELT <= 2.1, (
        f"back-solved cp_urea = {m.CP_UREA_MELT:.4f}, outside the published molten-urea band")


def test_density_rises_with_urea_and_falls_with_temperature():
    """Both signs came out of the PFD regression rather than being imposed, so this test is a
    genuine check on the source data, not a restatement of an assumption."""
    assert m.C10_RHO_B > 0.0, "density must rise with urea fraction"
    assert m.C10_RHO_C < 0.0, "density must fall with temperature"
    a = 1151.0
    assert m.urea_soln_rho(0.9771, 99.0, a) > m.urea_soln_rho(0.44, 99.0, a)
    assert m.urea_soln_rho(0.80, 140.0, a) < m.urea_soln_rho(0.80, 40.0, a)


def test_density_correlation_reproduces_the_pfd_evaporator_streams():
    """Spot-check against the PFD rows the fit was built from: 401 (94.31 % / 130 C / 1200) and
    402 (97.71 % / 140 C / 1220), carried off the 315 anchor (80 % / 99 C / 1151)."""
    for w, T, pfd in ((0.9431, 130.0, 1200.0), (0.9771, 140.0, 1220.0)):
        got = m.urea_soln_rho(w, T, 1151.0)
        assert abs(got - pfd) / pfd < 0.05, f"w={w} T={T}: got {got:.0f}, PFD {pfd:.0f}"


# ---------------------------------------------------- unit 324 now uses local, not lumped, cp
def test_evaporator_holdups_no_longer_share_the_feed_cp():
    """The two melts are far more concentrated than the feed, so their cp must be materially
    lower.  If these ever collapse back onto R324_CP_SOLN the lumped constant has returned."""
    assert m.R324_CP_HOLD1 < m.R324_CP_FEED1
    assert m.R324_CP_HOLD2 < m.R324_CP_HOLD1
    assert abs(m.R324_CP_HOLD2 - m.R324_CP_SOLN) / m.R324_CP_SOLN > 0.10, (
        "Stage-2 melt cp is within 10 % of the old lumped constant -- the fix is not doing anything")


def test_design_duties_still_use_the_same_cp_the_tick_uses():
    """The fixed point is preserved by CONSTRUCTION: the feed cp appears in both the back-solved
    design duty and the tick, so dT/dt = 0 still holds at the seed.  If the design derivation ever
    drifts back to the lumped constant while the tick uses the local one, the seed silently moves."""
    expected = (m.R324_FEED_DES / 3600.0 * m.R324_CP_FEED1
                * (m.R324_E001_T_SP_C - m.R324_FEED_T_C)
                + m.R324_V1_DES / 3600.0 * m.R324_LAM_V1)
    assert abs(m.R324_E001_Q_DES_KW - expected) < 1e-9


# ------------------------------------------------------------- audit B1: the ripple must flow
def test_the_tank_strength_pin_no_longer_erases_upstream_disturbances():
    """323D002's strength was pinned to the constant R324_W_IN, so sol_pin_strength overwrote the
    urea/water pair every tick and every upstream composition change died there -- 0 of 66 unit-324
    telemetry leaves responded to a reactor-overflow step.  The pin is kept (CLAUDE.md §0, it holds
    the PFD strength against rounding creep) but now carries the live deviation."""
    w = {"Urea": 0.83, "H2O": 0.16, "Biuret": 0.005, "NH3": 0.003, "CO2": 0.001, "HCHO": 0.001}
    # an authority ABOVE the design anchor must actually land above it
    out = m.sol_pin_strength(w, m.R324_W_IN + 0.03)
    assert abs(out["Urea"] - (m.R324_W_IN + 0.03)) < 1e-12
    # and the pair still sums with the untouched minors
    assert abs(sum(out.values()) - sum(w.values())) < 1e-12


def test_zero_deviation_still_lands_exactly_on_the_design_anchor():
    """The pin's original job.  With no deviation the result must be R324_W_IN to the bit."""
    w = {"Urea": 0.77, "H2O": 0.22, "Biuret": 0.005, "NH3": 0.003, "CO2": 0.001, "HCHO": 0.001}
    out = m.sol_pin_strength(w, m.R324_W_IN + 0.0)
    assert out["Urea"] == m.R324_W_IN
