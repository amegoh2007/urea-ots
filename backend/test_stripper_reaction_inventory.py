"""Focused inventory guards for the 322E001 stripper reactions."""

import math

import pytest

import main as m


ATOMS = {
    "CO2": {"C": 1, "O": 2},
    "CH4": {"C": 1, "H": 4},
    "H2": {"H": 2},
    "H2O": {"H": 2, "O": 1},
    "N2": {"N": 2},
    "NH3": {"N": 1, "H": 3},
    "O2": {"O": 2},
    "Urea": {"C": 1, "H": 4, "N": 2, "O": 1},
    "Biuret": {"C": 2, "H": 5, "N": 3, "O": 2},
}


def _feed(**components):
    feed = {species: 0.0 for species in m.MW_COMP}
    feed.update(components)
    return feed


def _run(feed):
    return m.stripper_322e001(
        0.0,
        m.STRIP_STEAM_T_DES_C,
        m.STRIP_P_DES_BARA,
        overflow_kmolh=feed,
    )


def _assert_conserved(feed, result):
    products = {
        species: result["top_kmolh"][species] + result["bot_kmolh"][species]
        for species in m.MW_COMP
    }

    for element in ("C", "H", "N", "O"):
        atoms_in = sum(feed[species] * ATOMS[species].get(element, 0) for species in m.MW_COMP)
        atoms_out = sum(products[species] * ATOMS[species].get(element, 0) for species in m.MW_COMP)
        assert atoms_out == pytest.approx(atoms_in, abs=1e-10)

    mass_in = sum(feed[species] * m.MW_COMP[species] for species in m.MW_COMP)
    mass_out = result["top_kgh"] + result["bot_kgh"]
    assert mass_out == pytest.approx(mass_in, rel=1e-12, abs=1e-9)


def test_zero_feed_cannot_create_reaction_products():
    result = _run(_feed())

    assert result["xi_hyd"] == 0.0
    assert result["xi_biu"] == 0.0
    assert result["top_kgh"] == 0.0
    assert result["bot_kgh"] == 0.0
    assert all(value == 0.0 for value in result["top_kmolh"].values())
    assert all(value == 0.0 for value in result["bot_kmolh"].values())


@pytest.mark.parametrize(
    ("feed", "expected_hydrolysis"),
    [
        pytest.param(_feed(Urea=1.0, H2O=0.25), 0.25, id="water-starved"),
        pytest.param(_feed(Urea=0.25, H2O=1.0), 0.25, id="urea-starved"),
    ],
)
def test_hydrolysis_is_limited_by_each_reagent(feed, expected_hydrolysis):
    result = _run(feed)

    assert result["xi_hyd"] == pytest.approx(expected_hydrolysis)
    remaining_urea = feed["Urea"] - result["xi_hyd"]
    assert 0.0 <= result["xi_biu"] <= 0.5 * remaining_urea + 1e-12
    _assert_conserved(feed, result)


def test_biuret_is_limited_by_urea_remaining_after_hydrolysis():
    # The unconstrained Arrhenius extent is about 0.309 kmol/h here, but
    # hydrolysis leaves only 0.005 kmol/h urea for the 2:1 biuret reaction.
    feed = _feed(Urea=92.51, H2O=200.0)
    result = _run(feed)

    assert result["xi_hyd"] == pytest.approx(92.505)
    assert result["xi_biu"] == pytest.approx(0.0025)
    assert math.isclose(
        2.0 * result["xi_biu"],
        feed["Urea"] - result["xi_hyd"],
        rel_tol=0.0,
        abs_tol=1e-10,
    )
    _assert_conserved(feed, result)
