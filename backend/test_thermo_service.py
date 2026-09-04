"""Phase 1 -- unit tests for the unified rigorous VLE / flash service.

These test the SERVICE, not the engine: no `import main`, so they run in ~1 s and are not gated on
the 18 000-tick boot pin.  Engine-level consequences are covered by the existing equation audits.
"""
import math

import pytest

import thermo_service as ts
import vle_nh3co2h2o as vle


def _norm(d):
    tot = sum(d.values())
    return {k: v / tot for k, v in d.items()}


#  The engine's own design vectors (main.py W_S314 / W_S319_TAB / W_S317 / W_S401_TAB / W_S402_TAB)
#  transcribed as literals so this file does not import main.
W_C003 = _norm(dict(Urea=68.74, Biuret=0.36, NH3=2.13, CO2=1.05, H2O=27.72))
W_F004 = _norm(dict(Urea=71.74, Biuret=0.37, NH3=0.88, CO2=0.66, H2O=26.35))
W_F010 = _norm(dict(Urea=80.00, Biuret=0.42, NH3=0.08, CO2=0.02, H2O=19.47))
W_E001 = _norm(dict(Urea=94.31, Biuret=0.69, NH3=0.03, H2O=4.97))
W_E003 = _norm(dict(Urea=97.71, Biuret=0.85, NH3=0.04, H2O=1.39))

#  Reactor overflow (stream 207) as mass fractions -- the HP-loop state that MUST be refused.
_MW = {"Urea": 60.056, "Biuret": 103.081, "NH3": 17.0304, "CO2": 44.0098, "H2O": 18.0152}
_R207_KMOLH = {"Urea": 1302.6, "Biuret": 2.414, "NH3": 4002.4, "CO2": 897.7, "H2O": 2222.0}
W_R207 = _norm({k: v * _MW[k] for k, v in _R207_KMOLH.items()})

STAGES_323 = [("323C003", W_C003, 135.0, 4.10),
              ("323F004", W_F004, 106.0, 1.13),
              ("323F010", W_F010, 99.0, 0.46)]


# ---------------------------------------------------------------- domain classification / refusal

def test_323_stages_are_on_the_electrolyte_domain():
    for tag, w, t_c, p in STAGES_323:
        assert ts.classify(w, t_c, p) == ts.DOMAIN_ELECTROLYTE, tag


def test_324_melts_are_on_the_neutral_urea_domain():
    assert ts.classify(W_E001, 130.0, 0.330) == ts.DOMAIN_NEUTRAL_UREA
    assert ts.classify(W_E003, 140.0, 0.131) == ts.DOMAIN_NEUTRAL_UREA


def test_hp_synthesis_loop_is_refused_not_extrapolated():
    """The 322 loop is 6-54x outside the loading grid; `_bracket` CLAMPS, so a silent answer there
    would be a frozen edge node wearing a rigorous-looking call.  It must refuse instead."""
    assert ts.classify(W_R207, 183.0, 144.9) is None
    with pytest.raises(ts.OutOfDomain):
        ts.flash(W_R207, 183.0, 144.9)
    with pytest.raises(ts.OutOfDomain):
        ts.bubble_p(W_R207, 183.0)


def test_domain_report_names_the_bound_that_failed():
    rep = ts.domain_report(W_R207, 183.0, 144.9)
    assert rep["domain"] is None
    assert rep["n_load_mol_per_kg_water"] > rep["n_envelope"][1]      # NH3 loading off the top
    assert rep["t_c"] > rep["t_envelope_c"][1]                        # and above the top T node


def test_flash_refuses_a_volatile_split_on_a_urea_melt():
    """The neutral binary carries no NH3/CO2 and the electrolyte path is outside its dilute limit in
    a 98 wt% urea melt -- bubble_p stays valid there, a volatile split does not."""
    with pytest.raises(ts.OutOfDomain):
        ts.flash(W_E003, 140.0, 0.131)
    assert ts.bubble_p(W_E003, 140.0) > 0.0


# ---------------------------------------------------------------------------- bubble / dew points

def test_bubble_p_reproduces_the_pfd_within_the_models_stated_accuracy():
    """The model's honest residual against the PFD -- not a fitted anchor.  The test pins the
    ENVELOPE of that residual so a regression in the activity path is caught.

    Ideal-vapour (what `vle_nh3co2h2o.bubble_p_bara` reports): +7.0 / +17.5 / +1.7 %.
    Full gamma-phi (what this service reports, phi < 1 raises P): +8.8 / +18.3 / +2.1 %."""
    expected = {"323C003": (4.10, 0.12), "323F004": (1.13, 0.20), "323F010": (0.46, 0.05)}
    for tag, w, t_c, _p in STAGES_323:
        p_pfd, rel_tol = expected[tag]
        p_model = ts.bubble_p(w, t_c)
        assert math.isclose(p_model, p_pfd, rel_tol=rel_tol), f"{tag}: {p_model} vs {p_pfd}"


def test_ideal_bubble_p_equals_the_sum_of_its_partial_pressures():
    for tag, w, t_c, _p in STAGES_323:
        parts = ts.partial_pressures(w, t_c)
        assert math.isclose(ts.bubble_p(w, t_c, srk=False), sum(parts[s] for s in ts.VOLATILE),
                            rel_tol=1e-12), tag


def test_srk_raises_the_bubble_point_above_the_ideal_sum():
    """phi < 1 for all three volatiles at these states, so P = sum p_i/phi_i must exceed sum p_i.
    If the correction were silently skipped the two would be identical."""
    for tag, w, t_c, _p in STAGES_323:
        assert ts.bubble_p(w, t_c) > ts.bubble_p(w, t_c, srk=False) * (1.0 + 1e-4), tag


def test_bubble_t_inverts_bubble_p():
    for tag, w, t_c, _p in STAGES_323:
        p = ts.bubble_p(w, t_c)
        assert math.isclose(ts.bubble_t(w, p), t_c, abs_tol=1e-3), tag


def test_bubble_t_rises_with_pressure():
    for tag, w, t_c, _p in STAGES_323:
        p = ts.bubble_p(w, t_c)
        assert ts.bubble_t(w, 1.3 * p) > ts.bubble_t(w, 0.8 * p), tag


# --------------------------------------------------------------------------------- the flash itself

def test_flash_converges_at_every_323_design_state():
    ts.flash_cache_clear()
    for tag, w, t_c, p in STAGES_323:
        fr = ts.flash(w, t_c, p)
        assert fr.converged, f"{tag}: residual {fr.residual}"
        assert fr.domain == ts.DOMAIN_ELECTROLYTE, tag


def test_flash_conserves_mass_across_the_phase_split():
    """z = (1-psi)x + psi*y per species, on the mass basis the engine's species layer uses."""
    for tag, w, t_c, p in STAGES_323:
        fr = ts.flash(w, t_c, p)
        for s in ts.SPECIES:
            recon = (1.0 - fr.psi_mass) * fr.x[s] + fr.psi_mass * fr.y[s]
            assert math.isclose(recon, w.get(s, 0.0), abs_tol=2e-3), f"{tag}/{s}"


def test_non_volatiles_never_enter_the_vapour():
    for tag, w, t_c, p in STAGES_323:
        fr = ts.flash(w, t_c, p)
        for s in ts.NONVOLATILE:
            assert fr.y[s] == 0.0, f"{tag}/{s}"
            assert fr.k[s] == 0.0, f"{tag}/{s}"


def test_vapour_fraction_is_bounded_below_total_vaporisation():
    """A liquor that is 69-80 wt% non-volatile urea CANNOT flash to psi = 1.  The non-volatile term
    -z_i/(1-psi) in the Rachford-Rice residual is the only thing that enforces it; dropping those
    species from the sum (the obvious filter, since K = 0 contributes nothing at psi = 0) returned
    psi_mass = 1.0 at all three stages."""
    for tag, w, t_c, p in STAGES_323:
        fr = ts.flash(w, t_c, p)
        assert 0.0 <= fr.psi_mass < 1.0, tag
        assert fr.psi_mass < 1.0 - w["Urea"] + 1e-6, tag


def test_flash_responds_to_temperature_and_pressure():
    """The whole point of Phase 1: the frozen alpha vector this replaces had a derivative of exactly
    zero in both T and P.  More heat -> more vapour; more pressure -> less."""
    w, t_c, p = W_C003, 135.0, 4.10
    assert ts.flash(w, t_c + 6.0, p).psi_mass > ts.flash(w, t_c, p).psi_mass
    assert ts.flash(w, t_c, p * 1.25).psi_mass < ts.flash(w, t_c, p).psi_mass


def test_k_values_order_the_volatiles_physically():
    """At 323F010 (99 C, deep-ish vacuum, near-stripped liquor) the vapour is overwhelmingly water."""
    fr = ts.flash(W_F010, 99.0, 0.46)
    assert fr.y["H2O"] > 0.85
    assert fr.y["H2O"] > fr.y["NH3"] > 0.0


def test_srk_fugacity_is_applied_and_moves_the_answer():
    """phi != 1 at 4.1 bar a: if SRK were silently ideal the K-values would be unchanged."""
    fr = ts.flash(W_C003, 135.0, 4.10)
    y_mole = ts.mass_to_mole(fr.y)
    phi = ts.vapour_fugacity(y_mole, 135.0, 4.10)
    assert any(abs(phi[s] - 1.0) > 1e-3 for s in ("H2O", "NH3", "CO2"))
    for s in ("H2O", "NH3", "CO2"):
        assert 0.5 < phi[s] <= 1.0


# ------------------------------------------------------------------------------------- PH flash

def test_flash_ph_inverts_the_isothermal_flash():
    """h(T) from a converged flash, fed back through flash_ph, must return the same T."""
    for tag, w, t_c, p in STAGES_323:
        fr = ts.flash(w, t_c, p)
        h = ts.mixture_enthalpy_kj_per_kg(fr)
        back = ts.flash_ph(w, h, p)
        assert math.isclose(back.t_c, t_c, abs_tol=0.05), f"{tag}: {back.t_c} vs {t_c}"


def test_mixture_enthalpy_rises_with_temperature():
    w, p = W_C003, 4.10
    h_lo = ts.mixture_enthalpy_kj_per_kg(ts.flash(w, 120.0, p))
    h_hi = ts.mixture_enthalpy_kj_per_kg(ts.flash(w, 145.0, p))
    assert h_hi > h_lo


# ------------------------------------------------------------------------------------- the cache

def test_quantised_cache_does_not_change_the_answer():
    ts.flash_cache_clear()
    cold = ts.flash(W_C003, 135.0, 4.10)
    warm = ts.flash(W_C003, 135.0, 4.10)
    assert warm is cold                                    # same object -> served from the memo
    ts.flash_cache_clear()
    fresh = ts.flash(W_C003, 135.0, 4.10)
    for s in ts.SPECIES:
        assert math.isclose(fresh.y[s], cold.y[s], rel_tol=1e-12, abs_tol=1e-12), s
    assert math.isclose(fresh.psi_mass, cold.psi_mass, rel_tol=1e-12)


def test_cache_quantum_is_far_below_instrument_resolution():
    """The memo may only hide changes smaller than anything the plant can see."""
    assert ts._T_QUANTUM_C <= 0.05          # C -- finer than any TT
    assert ts._P_QUANTUM_BARA <= 1.0e-3     # bar a -- finer than any PT


def test_cache_misses_when_the_state_actually_moves():
    ts.flash_cache_clear()
    ts.flash(W_C003, 135.0, 4.10)
    ts.flash(W_C003, 135.0 + 10.0 * ts._T_QUANTUM_C, 4.10)
    assert ts.flash_cache_stats()["miss"] == 2


# ------------------------------------------------------------------------- underlying-module wiring

def test_partial_pressure_split_did_not_move_the_legacy_bubble_point():
    """`vle_nh3co2h2o.bubble_p_bara` was refactored to sum `partial_pressures_bara`.  Its documented
    323C003 value must be unchanged."""
    assert math.isclose(vle.bubble_p_bara(W_C003, 135.0), 4.387, abs_tol=1e-3)


def test_out_of_grid_is_flagged_by_the_underlying_module():
    assert vle.partial_pressures_bara(W_C003, 135.0)["in_grid"] is True
    assert vle.partial_pressures_bara(W_R207, 183.0)["in_grid"] is False


# ------------------------------------------------------------------------------------- dew point

def test_dew_t_of_pure_steam_is_the_water_saturation_line():
    """Pressures chosen so T_sat lands INSIDE the table's 80-170 C span; at 0.46 bar a T_sat is
    ~79 C, below the bottom node, and the service correctly refuses rather than clamping to it."""
    assert math.isclose(ts.dew_t({"H2O": 1.0}, 1.0), 100.0, abs_tol=1.0)
    assert math.isclose(ts.dew_t({"H2O": 1.0}, 4.0), 143.6, abs_tol=1.5)
    with pytest.raises(ts.OutOfDomain):
        ts.dew_t({"H2O": 1.0}, 0.46)              # T_sat ~79 C -> below the table floor


def test_dew_t_refuses_a_carbamate_rich_vapour():
    """The incipient liquid of a 48 wt% CO2 vapour is a concentrated carbamate solution at N ~ 39,
    C ~ 35 mol/kg water -- the same high-loading data the HP loop needs and this repo does not have.
    Refusing is correct; returning a clamped edge node would not be."""
    y_c003 = ts.flash(W_C003, 135.0, 4.10).y
    with pytest.raises(ts.OutOfDomain):
        ts.dew_t(y_c003, 4.10)


def test_flash_and_bubble_point_are_mutually_consistent():
    """At T = bubble_t(P) the flash must return essentially zero vapour.  This ties the two entry
    points to ONE thermodynamic surface -- a bubble point computed from partial pressures and a
    vapour fraction computed from Rachford-Rice cannot disagree about where boiling starts."""
    for tag, w, _t, _p in STAGES_323:
        p = 2.0
        t_bub = ts.bubble_t(w, p)
        assert ts.flash(w, t_bub, p).psi_mole < 1e-8, tag
        assert ts.flash(w, t_bub + 3.0, p).psi_mole > 1e-6, tag     # and above it, vapour appears
