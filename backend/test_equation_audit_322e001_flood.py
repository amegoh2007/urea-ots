"""Audit TD-006 (second half): the HP stripper's hydrodynamic flooding limit.

Until this block landed, unit 322 had no tube geometry at all -- every "flood" term in
stripper_322e001 was a THERMAL metaphor for the steam-dilution branch, not a hydraulic limit.

The whole bit-exactness argument for this feature is that the plant genuinely runs BELOW its
flooding limit (108.0 of 145 kg/h per tube, 74.5 %), so the constraint does not bind at the design
seed and cannot move the pin.  These tests exist to keep that true: if anyone ever changes the tube
count, the design feed, or the flooding limit such that the design fraction reaches 1.0, the
identity tests below fail LOUDLY rather than silently shifting the pinned state.

Sources for every number asserted here:
  * geometry -- licensor DDS 322E001, Uhde UD-AU-322-DZ-0003-003 rev 00, page 3
  * flooding limit -- Brouwer, "How to Solve Stripper Efficiency Issues", UreaKnowHow 2025,
    citing IFS Proceeding 166
"""
import math

import main as m


# --------------------------------------------------------------------------- geometry provenance
def test_tube_count_is_confirmed_by_the_datasheets_own_surface_area():
    """The DDS is self-consistent: N*pi*d_o*L must reproduce its tabulated exchange surface.

    This is the check that makes the tube count trustworthy.  2600 tubes is not read off a single
    cell and hoped for -- it is confirmed independently by line 25 of the same sheet.
    """
    a = m.STRIP_N_TUBES * math.pi * m.STRIP_TUBE_OD_M * m.STRIP_TUBE_L_EFF_M
    assert abs(a - m.STRIP_SURF_DES_M2) / m.STRIP_SURF_DES_M2 < 0.001, (
        f"N*pi*do*L = {a:.2f} m2 but the DDS tabulates {m.STRIP_SURF_DES_M2:.2f} m2 -- "
        "the tube count and the surface area no longer agree")


def test_tube_id_really_is_the_one_inch_the_flooding_figure_is_quoted_for():
    """145 kg/h is quoted for a 1-inch tube.  It applies here WITHOUT scaling only because the
    DDS bore is 25.0 mm = 0.984 inch.  If the geometry ever changes, the limit needs rescaling."""
    assert m.STRIP_TUBE_ID_M == m.STRIP_TUBE_OD_M - 2.0 * m.STRIP_TUBE_WALL_M
    inches = m.STRIP_TUBE_ID_M / 0.0254
    assert 0.95 < inches < 1.05, f"tube bore is {inches:.3f} inch -- the 145 kg/h figure no longer applies neat"


def test_effective_tube_length_matches_the_source_of_the_80_percent_efficiency_figure():
    """Brouwer ties a 6 m effective tube length to a Stamicarbon CO2 stripper's 80 % design
    stripping efficiency.  The DDS says 6000 mm eff.  Two independent documents, same number."""
    assert m.STRIP_TUBE_L_EFF_M == 6.000


# ------------------------------------------------------------------- the design point is inert
def test_design_sits_below_the_flooding_limit():
    """108.0 of 145 kg/h per tube.  Everything else in this module depends on this staying < 1."""
    per_tube = m.STRIP_FEED_DES_KGH / m.STRIP_N_TUBES
    assert abs(per_tube - 108.0) < 0.1, f"design load is {per_tube:.2f} kg/h per tube, expected ~108.0"
    assert abs(m.STRIP_FLOOD_DES_FRAC - 0.7448) < 0.001
    assert m.STRIP_FLOOD_DES_FRAC < 1.0, (
        "the design point has reached the flooding limit -- the flooding term is no longer inert "
        "at the seed and the pin contract is broken")


def test_flooding_terms_are_exact_identities_at_the_design_seed():
    """The pin contract.  Not 'close to' 1.0 and 0.0 -- exactly, to the bit.

    g_flood multiplies `mod` and dT_flood is added to dT_bot, so anything other than an exact
    1.0 / 0.0 here changes the pinned design state.
    """
    s = m.stripper_322e001(m.CO2_DES_KGH / 1000.0, m.STRIP_STEAM_T_DES_C, m.STRIP_P_DES_BARA)
    assert s["flood_x"] == 0.0
    assert s["g_flood"] == 1.0
    assert s["dT_flood"] == 0.0
    assert s["T_bot"] == m.STRIP_T_BOTTOM_DES_C
    assert s["eta_T"] == 1.0


def test_plant_level_onset_is_the_order_the_literature_reports():
    """Brouwer: a stripper floods at ~110 % of load when new, ~120 % at end of life (the limit
    rises as the bore grows by passive corrosion).  This bundle computes 134 % -- the same order,
    a little roomier, which is what a 0.984-inch bore at 144 bar rather than 140 bar should give."""
    onset = m.STRIP_FLOOD_KGH_TUBE * m.STRIP_N_TUBES / m.STRIP_FEED_DES_KGH
    assert 1.25 < onset < 1.45, f"flooding onset computed at {onset:.1%} of plant load"


# ------------------------------------------------------------------- the off-design response
def _sweep(load):
    ov = {k: v * load for k, v in m.STRIP_FEED207_KMOLH.items()}
    return m.stripper_322e001(m.CO2_DES_KGH / 1000.0 * load, m.STRIP_STEAM_T_DES_C,
                              m.STRIP_P_DES_BARA, overflow_kmolh=ov)


def test_nothing_happens_until_the_limit_is_crossed():
    """A one-sided constraint must be genuinely one-sided: no drift, no soft onset below 1.0."""
    for load in (0.5, 0.9, 1.0, 1.1, 1.2, 1.3):
        s = _sweep(load)
        if s["flood_frac"] < 1.0:
            assert s["g_flood"] == 1.0, f"g_flood moved at {load:.0%} load with frac {s['flood_frac']:.4f}"
            assert s["dT_flood"] == 0.0


def test_bottom_temperature_signature_matches_the_published_3_to_4_degrees():
    """Brouwer: 'a sudden temperature increase of the stripper bottom temperature, let's say
    3-4 C in 15 minutes, is a clear indication for reaching the flooding limit'.

    STRIP_FLOOD_T_K was FIXED by this number rather than tuned to it, so this test is the
    calibration, not a coincidence: at 10 % over the limit the rise must land in the band.
    """
    gap = m.STRIP_T_FLOOD_ANCHOR_C - m.STRIP_T_BOTTOM_DES_C
    dt = gap * (1.0 - math.exp(-m.STRIP_FLOOD_T_K * 0.10))
    assert 3.0 <= dt <= 4.0, f"10 % over the limit gives {dt:.2f} C, outside the published 3-4 C"


def test_flooding_holds_the_volatiles_in_the_bottoms():
    """The operational cascade Brouwer describes: stripping efficiency falls, so NH3 that should
    have gone overhead to the HPCC leaves with the bottoms instead and slips to the LP section,
    raising LP recirculation pressure.  Overhead NH3 recovery must fall monotonically once flooded.
    """
    prev = None
    for load in (1.4, 1.5, 1.6, 1.8):
        s = _sweep(load)
        assert s["flood_frac"] > 1.0, f"{load:.0%} load did not flood"
        rec = s["top_kmolh"]["NH3"] / s["feed_kmolh"]["NH3"]
        if prev is not None:
            assert rec < prev, "overhead NH3 recovery did not fall as flooding deepened"
        prev = rec


def test_bottom_runs_hotter_not_colder_when_flooded():
    """Sign check.  A flooded tube holds un-decomposed carbamate and hot reactor liquor falls
    through untouched, so the bottom must run HOTTER.  The old steam-dilution branch drives the
    bottom the same way, and an earlier bug in this unit had it crashing toward 0 C instead."""
    hot = _sweep(1.5)
    assert hot["dT_flood"] > 0.0
    assert hot["T_bot"] > m.STRIP_T_BOTTOM_DES_C
    assert hot["T_bot"] <= hot["T_steam"] + 1e-9, "bottom out-heated the condensing shell steam"


def test_g_flood_never_leaks_into_the_efficiency_that_drives_hydrolysis():
    """Wrong-sign guard.  Flooding INCREASES liquid residence time (Brouwer: "stagnation or upward
    dragging of the film"), so hydrolysis and biuret go UP, not down.  g_flood must therefore reach
    the SPLIT only, never eta_T -- because eta_T scales xi_hyd, and folding it in would cut
    hydrolysis exactly the wrong way.

    The assertion is that eta_T still reconstructs from its four original factors alone.  It cannot
    be phrased as "hydrolysis stays high when flooded", because by the time the bundle floods the
    pre-existing steam-dilution choke (g_T) has already floored eta_T on its own -- a separate
    mechanism that this test must not conflate with the flooding one.
    """
    flooded = _sweep(1.5)
    assert flooded["g_flood"] < 1.0, "1.5x load did not flood -- the fixture is no longer valid"
    without_flood = min(flooded["eta_T_steam"] * flooded["g_NC"] * flooded["g_HC"] * flooded["g_T"],
                        1.15)
    assert abs(flooded["eta_T"] - without_flood) < 1e-12, (
        f"eta_T {flooded['eta_T']!r} does not reconstruct from its four original factors "
        f"({without_flood!r}) -- g_flood has leaked into the hydrolysis driver")
    # and the leak would be visible: eta_T * g_flood is a materially different number
    assert abs(without_flood * flooded["g_flood"] - without_flood) > 1e-6
