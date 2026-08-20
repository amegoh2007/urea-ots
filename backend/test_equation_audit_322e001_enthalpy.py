"""Audit TD-006 (second half): the HP stripper's per-species enthalpy balance, plus the eta_P fix.

Two defects closed here, both of the same family -- a term that was PRESENT in the code but could
not actually respond to anything:

  * the MP-steam duty was proportional to feed MASS, so composition never entered.  The same
    tonnage of pure water and of carbamate-rich reactor liquor demanded identical steam, and the
    single largest heat sink in the unit (carbamate dissociation) was invisible to the header.
  * eta_P was computed from a pressure argument that every call site passed the frozen design
    constant, so it evaluated to exactly 1.0 forever.  A dead lever passes a pin gate perfectly,
    which is how it survived; the tests below are written to FAIL if it ever goes dead again.

Sources for every enthalpy asserted here:
  * carbamate 117 kJ/mol and urea 15.5 kJ/mol -- Frejacques, quoted in Brouwer, "Thermodynamics
    of the Urea Process", UreaKnowHow Process Paper June 2009, p.12, BOTH at process conditions
    (110 atm / 160 C and 160-180 C respectively), not at the 25 C standard state.
  * NH3 desorption and gas cp -- the loop's own HPCC values, asserted equal below.
  * water latent -- steam tables, the same figure HPCC_FLASH_DH already carries.
"""
import math

import main as m


# --------------------------------------------------------------- provenance / self-consistency
def test_enthalpy_constants_match_the_published_signs_and_magnitudes():
    """Carbamate dissociation is strongly ENDOthermic here (the stripper runs Frejacques reaction 1
    backwards); urea hydrolysis is mildly EXOthermic into carbamate (reaction 2 backwards)."""
    assert m.STRIP_DH_CARB_JMOL == 117_000.0
    assert m.STRIP_DH_HYD_JMOL == -15_500.0
    assert m.STRIP_DH_CARB_JMOL > 0 > m.STRIP_DH_HYD_JMOL
    # the process-condition value, NOT the 159-160 kJ/mol quoted for SOLID carbamate at 25 C
    assert m.STRIP_DH_CARB_JMOL < 150_000.0


def test_shared_constants_cannot_drift_from_the_hpcc_values_they_restate():
    """STRIP_DH_NH3_JMOL and STRIP_CP_GAS are restated rather than aliased, because this unit's
    design-point self-call runs before the HPCC block is defined.  Restating risks divergence, so
    pin the equality here -- the whole point is that they are ONE number, not two."""
    assert m.STRIP_DH_NH3_JMOL == m.HPCC_BUB_DHVAP_JMOL
    assert m.STRIP_CP_GAS == m.HPCC_CP_GAS


def test_balance_reproduces_the_licensor_duty_without_fitting():
    """The corroboration that the constant set is right.  Nothing here is fitted: summing the five
    terms over the design streams must land close to the licensor's 39 400 kW.  If a future edit
    pushes this outside 90-105 %, the constants no longer describe this stripper."""
    ratio = m.STRIP_DUTY_RAW_DES_KW / m.STRIP_DUTY_DES_KW
    assert 0.90 < ratio < 1.05, (
        f"first-principles duty is {m.STRIP_DUTY_RAW_DES_KW:.0f} kW against the licensor's "
        f"{m.STRIP_DUTY_DES_KW:.0f} kW ({ratio:.1%}) -- the constant set no longer corroborates")


def test_carbamate_dissociation_is_the_dominant_sink():
    """Physical ordering check.  If some future edit makes water latent or sensible heat outrank
    carbamate dissociation, the balance has been miswired -- this is a CO2 stripper."""
    d = _design()
    assert d["q_carb_kw"] > d["q_nh3_kw"] > d["q_h2o_kw"]
    assert d["q_carb_kw"] > 0.5 * (d["q_carb_kw"] + d["q_nh3_kw"] + d["q_h2o_kw"])
    assert d["q_hyd_kw"] < 0.0, "hydrolysis into carbamate gives heat back; sign is wrong"


# -------------------------------------------------------------------- the pin contract
def _design():
    return m.stripper_322e001(m.CO2_DES_KGH / 1000.0, m.STRIP_STEAM_T_DES_C, m.STRIP_P_DES_BARA)


def test_duty_ratio_is_exactly_one_at_the_design_seed():
    """Not 'close to' 1.0 -- exactly.  Q_strip = STRIP_DUTY_DES_KW * ratio * 3600, so anything
    other than a bare 1.0 moves the MP-steam draw and with it the pinned design state."""
    assert _design()["duty_raw_kw"] == m.STRIP_DUTY_RAW_DES_KW
    assert (_design()["duty_raw_kw"] / m.STRIP_DUTY_RAW_DES_KW) == 1.0


def test_flooding_knockdown_is_exactly_one_at_the_design_seed():
    """g_flood is now DERIVED from dT_flood rather than fitted.  dT_flood is exactly 0.0 below the
    flooding limit, so 1 - 0.0/Q is exactly 1.0 -- a structural identity, not a tolerance."""
    d = _design()
    assert d["dT_flood"] == 0.0
    assert d["g_flood"] == 1.0


# -------------------------------------------------------------- the levers must not be dead
def test_duty_responds_to_composition_at_constant_feed_mass():
    """THE regression that TD-006 exists for.  Trade NH3 against water at constant total mass:
    the retired feed-proportional duty returns an identical number for every such feed, so this
    test is precisely the one it could not pass."""
    base = dict(m.STRIP_FEED207_KMOLH)
    lean = dict(base)
    dn = base["NH3"] * 0.10
    lean["NH3"] = base["NH3"] - dn
    lean["H2O"] = base["H2O"] + dn * m.MW_COMP["NH3"] / m.MW_COMP["H2O"]
    mass_base = sum(base[k] * m.MW_COMP[k] for k in base)
    mass_lean = sum(lean[k] * m.MW_COMP[k] for k in lean)
    assert abs(mass_lean - mass_base) / mass_base < 1e-9, "fixture broken: mass must be identical"
    r = m.stripper_322e001(m.CO2_DES_KGH / 1000.0, m.STRIP_STEAM_T_DES_C, m.STRIP_P_DES_BARA,
                           overflow_kmolh=lean)
    assert abs(r["duty_raw_kw"] - m.STRIP_DUTY_RAW_DES_KW) > 100.0, (
        "identical feed MASS gave an identical duty -- the balance is still mass-proportional")
    assert r["duty_raw_kw"] < m.STRIP_DUTY_RAW_DES_KW, (
        "a feed with less NH3 to desorb should need LESS steam, not more")


def test_eta_P_is_not_a_dead_lever():
    """Raising synthesis pressure must suppress stripping: carbamate dissociation makes 3 mol of
    gas from 1 mol of liquid, so pressure pushes the equilibrium back (Le Chatelier).  For years
    every call site passed the frozen design constant and this was identically 1.0."""
    lo = m.stripper_322e001(m.CO2_DES_KGH / 1000.0, m.STRIP_STEAM_T_DES_C,
                            m.STRIP_P_DES_BARA * 0.95)
    hi = m.stripper_322e001(m.CO2_DES_KGH / 1000.0, m.STRIP_STEAM_T_DES_C,
                            m.STRIP_P_DES_BARA * 1.05)
    assert hi["top_kmolh"]["NH3"] < lo["top_kmolh"]["NH3"], (
        "synthesis pressure did not move the split -- eta_P is dead again")


def test_feed_temperature_reaches_the_duty():
    """A hotter reactor overflow arrives carrying more sensible heat, so the stripper needs less
    steam to reach the same bottom temperature.  T_feed_C defaulted to a constant before this fix."""
    hot = m.stripper_322e001(m.CO2_DES_KGH / 1000.0, m.STRIP_STEAM_T_DES_C, m.STRIP_P_DES_BARA,
                             T_feed_C=m.STRIP_FEED207_T_C + 5.0)
    assert hot["duty_raw_kw"] < m.STRIP_DUTY_RAW_DES_KW
    assert hot["T_feed"] == m.STRIP_FEED207_T_C + 5.0


# ------------------------------------------------------- the retired constant must stay retired
def test_the_unsourced_flooding_constant_is_gone():
    """STRIP_FLOOD_ETA_K = 1.50 was borrowed from STRIP_ETA_KT with no source behind it.  It is
    replaced by a derivation, and must not creep back."""
    assert not hasattr(m, "STRIP_FLOOD_ETA_K"), (
        "STRIP_FLOOD_ETA_K is back -- the flooding knockdown must stay derived from the energy "
        "balance, not refitted")


def test_derived_knockdown_is_gentler_than_the_retired_fit():
    """The retired K=1.50 gave ~15 % efficiency loss at 1.5x load.  Three independent checks put
    the true figure at a few percent, and g_T already carries the thermal collapse separately --
    so a large hydraulic knockdown on top of it double-counted the same excursion."""
    ov = {k: v * 1.5 for k, v in m.STRIP_FEED207_KMOLH.items()}
    r = m.stripper_322e001(m.CO2_DES_KGH / 1000.0 * 1.5, m.STRIP_STEAM_T_DES_C,
                           m.STRIP_P_DES_BARA, overflow_kmolh=ov)
    assert r["flood_x"] > 0.0, "1.5x load did not flood -- fixture no longer valid"
    retired = 1.0 / (1.0 + 1.50 * r["flood_x"])
    assert r["g_flood"] > retired
    assert 0.90 < r["g_flood"] < 1.0, (
        f"derived knockdown {r['g_flood']:.4f} is outside the few-percent band the three "
        "independent cross-checks agree on")


def test_knockdown_deepens_monotonically_with_excess_load():
    for prev, load in ((None, 1.4), (1.4, 1.6), (1.6, 1.9), (1.9, 2.3)):
        ov = {k: v * load for k, v in m.STRIP_FEED207_KMOLH.items()}
        r = m.stripper_322e001(m.CO2_DES_KGH / 1000.0 * load, m.STRIP_STEAM_T_DES_C,
                               m.STRIP_P_DES_BARA, overflow_kmolh=ov)
        if prev is not None:
            ovp = {k: v * prev for k, v in m.STRIP_FEED207_KMOLH.items()}
            rp = m.stripper_322e001(m.CO2_DES_KGH / 1000.0 * prev, m.STRIP_STEAM_T_DES_C,
                                    m.STRIP_P_DES_BARA, overflow_kmolh=ovp)
            assert r["g_flood"] <= rp["g_flood"], "knockdown eased as flooding deepened"
        assert r["g_flood"] >= m.STRIP_FLOOD_ETA_FLOOR


def test_duty_stays_finite_across_the_operating_envelope():
    """No poles: the balance divides by nothing that can reach zero, and the clamp holds."""
    for load in (0.1, 0.5, 1.0, 1.5, 2.0, 2.5):
        for ts in (m.STRIP_STEAM_T_DES_C - 30, m.STRIP_STEAM_T_DES_C, m.STRIP_STEAM_T_DES_C + 15):
            ov = {k: v * load for k, v in m.STRIP_FEED207_KMOLH.items()}
            r = m.stripper_322e001(m.CO2_DES_KGH / 1000.0 * load, ts, m.STRIP_P_DES_BARA,
                                   overflow_kmolh=ov)
            q = r["duty_raw_kw"]
            assert math.isfinite(q), f"duty blew up at load={load} T_steam={ts}"
            assert math.isfinite(r["g_flood"]) and 0.0 < r["g_flood"] <= 1.0
