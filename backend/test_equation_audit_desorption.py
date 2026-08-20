"""Regression gate for the EQUATION_AUDIT F-8 fix — rigorous species layer in the desorption train.

WHY THIS FILE EXISTS
--------------------
Unit 328 was the last lumped-mass island in the plant.  328C002 and 328C004 moved material with
FROZEN overhead split constants (R328_C002_PHI737, R328_C004_PHI750): a fixed fraction of whatever
flowed in left overhead, and no composition existed anywhere in the unit.  Two consequences the
tests below lock down:

  * the hydrolyser's urea load had to be a hardcoded fraction, and it was the WRONG stream's --
    0.0082 is stream 738, the feed to 328C002, where the PFD gives stream 743/746 as 0.76 %.
    328C002 dilutes 31 114 kg/h into 33 769 kg/h of bottoms, so 328C003 was handed 276.9 kg/h of
    urea against the tabulated 256.6 (+7.9 %);
  * nothing in unit 328 responded to the stripping steam.  Halving FIC-329401 changed the flows and
    left the purified-condensate spec exactly where it was, because there was no spec to move.

Anchors come from PFD_No__22_Desorption and from the licensor mechanical datasheet
Uhde UD-AU-328-EC-0001 rev 01 (15 and 22 executed trays, ID 1250 mm, 40 mm weir, 3125 x 6 mm holes).

Run from backend/:  python -m pytest test_equation_audit_desorption.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402

DT = 0.25
SP = ("CO2", "H2O", "NH3", "Urea")


def _fresh(seconds=300.0):
    main.state = main.State()
    return _run(seconds)


def _run(seconds):
    out = None
    for _ in range(int(seconds / DT)):
        out = main.step_sim(DT)
    return out


def _kg(w, m):
    return {k: m * w[k] for k in SP}


# ------------------------------------------------------- the PFD composition-unit convention
def test_pfd_vapour_rows_are_mole_percent_not_mass_percent():
    """The finding that made F-8 anchorable at all.

    Read as mass %, the PFD says carbon is not conserved across 328C002 -- 1658 kg/h of CO2 in,
    858 out.  It is conserved: vapour rows are MOLE %.  The tabulated 'Average Molar Weight' is the
    discriminator, and for stream 737 it is decisive."""
    mw = main.MW_SOL
    mole = dict(CO2=12.32, H2O=46.21, NH3=41.47)          # PFD stream 737, Carb. Gas
    as_mole = sum(v / 100.0 * mw[k] for k, v in mole.items())
    as_mass = 1.0 / sum(v / 100.0 / mw[k] for k, v in mole.items())
    assert abs(as_mole - 20.81) < 0.02, f"mole-% reading gives {as_mole}, PFD tabulates 20.81"
    assert abs(as_mass - 20.81) > 1.5, "mass-% reading must NOT reproduce the tabulated MW"

    # and the helper the engine uses must implement exactly that reading
    w = main._w_from_molepct(mole)
    assert abs(sum(w.values()) - 1.0) < 1e-12
    assert abs(w["CO2"] - 0.2606) < 5e-4      # 12.32 mol% CO2 is 26.06 mass% of stream 737
    assert abs(w["NH3"] - 0.3394) < 5e-4


# ------------------------------------------------------------------- C2 per-component balances
def test_every_desorption_column_closes_on_every_component():
    """C2 across all three columns, on the licensor's own tabulated flows, nothing fitted.
    Tolerance is 2 kg/h against 34-40 t/h throughputs -- that is PFD percentage rounding."""
    cases = (
        ("328C002",
         [(main.W_S738, main.R328_C002_M738_DES), (main.W_S775, main.R328_C002_M775_DES),
          (main.W_S748, main.R328_C002_M748_DES), (main.W_S750, main.R328_C002_M750_DES)],
         [(main.W_S737, main.R328_C002_M737_DES), (main.W_S743, main.R328_C002_M743_DES)], 0.0),
        ("328C003",
         [(main.W_S743, main.R328_C003_M746_DES), (main.W_STEAM, main.R328_C003_M911_DES)],
         [(main.W_S748, main.R328_C003_M748_DES), (main.W_S747, main.R328_C003_M747_DES)], None),
        ("328C004",
         [(main.W_S747, main.R328_C004_M749_DES), (main.W_STEAM, main.R328_C004_M931_DES)],
         [(main.W_S750, main.R328_C004_M750_DES), (main.W_S739, main.R328_C004_M739_DES)], 0.0),
    )
    for tag, ins, outs, xi_fixed in cases:
        fin = {k: sum(_kg(w, m)[k] for w, m in ins) for k in SP}
        fout = {k: sum(_kg(w, m)[k] for w, m in outs) for k in SP}
        xi = ((fin["Urea"] - fout["Urea"]) / main.MW_SOL["Urea"]) if xi_fixed is None else 0.0
        # 0.01 % of throughput.  These are the TABULATED rows, quoted to 2 dp, so this is the
        # licensor's own percentage rounding; the engine runs on the back-solve, which closes exactly.
        tol = 1.0e-4 * sum(m for _, m in ins)
        for k in SP:
            gen = main.DES_HYD_NU.get(k, 0.0) * xi
            assert abs(fin[k] + gen - fout[k]) < tol, (
                f"{tag} {k}: in {fin[k]:.2f} + gen {gen:.2f} != out {fout[k]:.2f} (tol {tol:.2f})")
        # total mass closes exactly
        assert abs(sum(m for _, m in ins) - sum(m for _, m in outs)) < 1e-9


def test_hydrolysis_extent_is_the_pfd_stoichiometry_not_a_tuned_constant():
    """328C003 destroys exactly the urea the PFD says it destroys, and stream 747 tabulates none."""
    assert abs(main.DES_C003["xi"] - 4.2734) < 1e-3
    assert abs(main.R328_C003_UREA_DES - 256.6) < 0.5, "urea load must be stream 746's, not 738's"
    assert main.R328_C003_W_UREA_746 == main.W_S743["Urea"], "one source of truth for the fraction"
    assert abs(main.R328_C003_W_UREA_746 - 0.0076) < 1e-4
    # 2 NH3 + CO2 out per urea + H2O in, mass conserved by the stoichiometry vector
    nu = main.DES_HYD_NU
    assert abs(nu["Urea"] + nu["H2O"] + nu["NH3"] + nu["CO2"]) < 1e-9
    assert main.DES_C002["xi"] == 0.0 and main.DES_C004["xi"] == 0.0, "no urea reaction in desorbers"


def test_back_solved_vapour_agrees_with_the_pfd_tabulated_overheads():
    """Independent check the 323/324 stages never had: unit 328 tabulates its vapour compositions,
    so the back-solve can be compared against them rather than merely assumed."""
    for tag, a in (("C002", main.DES_C002), ("C003", main.DES_C003), ("C004", main.DES_C004)):
        assert a["dev"] < 0.005, f"{tag} back-solved vapour is {a['dev']*100:.3f} %pt off the PFD"
        assert abs(a["resid"]) < 0.5, f"{tag} clip residual {a['resid']} kg/h"
        assert abs(sum(a["y"].values()) - 1.0) < 1e-12, "C6: Sum y == 1"


# -------------------------------------------------------------- the mechanical datasheet lands
def test_desorber_geometry_comes_from_the_uhde_datasheet():
    """Uhde UD-AU-328-EC-0001 rev 01.  The tray counts are load-bearing -- they set the Kremser
    stage count that makes the columns degrade like columns instead of like a single flash."""
    assert main.R328_C002_NTRAY == 15 and main.R328_C004_NTRAY == 22
    assert main.R328_COL_ID == 1.250
    assert main.R328_TRAY_HWEIR == 0.040
    assert main.R328_TRAY_NHOLE == 3125 and main.R328_TRAY_DHOLE == 0.006
    assert 0.08 < main.R328_TRAY_AHOLE / main.R328_TRAY_ACTIVE < 0.12, "sieve tray free area"
    # holdup is geometry now, not a 900 s residence-time guess (8442 / 8431 kg)
    assert 1400.0 < main.R328_C002_M_DES < 1800.0
    assert 1300.0 < main.R328_C004_M_DES < 1600.0
    # theoretical stages follow the executed tray count through one shared O'Connell efficiency
    assert abs(main.R328_NTHEO_C002 / main.R328_C002_NTRAY
               - main.R328_AI701_NTHEO_C004 / main.R328_C004_NTRAY) < 1e-12


def test_purified_condensate_density_matches_two_independent_licensor_documents():
    """PFD stream 739 'Density eff.' 923.28 @ 143 C and the datasheet's 923.25 @ 143 C -- and both
    are simply water at 143 C, which is what a <1 ppm purified condensate is."""
    assert abs(main.R328_C004_RHO - 923.28) < 0.01
    assert abs(main.R328_C004_RHO - 923.25) < 0.10, "datasheet and PFD must agree"


# ------------------------------------------------------------------------- the layer is inert
def test_design_hold_keeps_every_desorber_on_its_pfd_composition():
    """The species layer must be a FIXED POINT of the design state, or it is a slow leak.

    It was one: explicit Euler on a 1.4 gram ammonia inventory (328C004 holds 1436 kg of liquid at
    1 ppm) with 330 kg/h flowing through walked 328C002 from 0.63 % to 2.2 % ammonia over four
    hours.  des_advance is implicit for exactly this reason."""
    _fresh(300.0)
    _run(60 * 60)
    s = main.state
    for live, ref, tag in ((s.w_328c002, main.W_S743, "328C002"),
                           (s.w_328c003, main.W_S747, "328C003")):
        for k in SP:
            assert abs(live[k] - ref[k]) < 2.0e-4, (
                f"{tag} {k} drifted to {live[k]*100:.5f} % from {ref[k]*100:.5f} %")
        assert abs(sum(live.values()) - 1.0) < 1e-12, f"{tag} C6: Sum w == 1"
    # the guarantee stream stays on its 1 ppm spec
    assert s.w_328c004["NH3"] * 1e6 < 1.5, "purified condensate NH3 must hold under 1 ppm"
    assert s.w_328c004["Urea"] * 1e6 < 1.5, "purified condensate urea must hold under 1 ppm"
    assert abs(s.a328_c002_T - main.R328_C002_T_BOT) < 0.05
    assert abs(s.a328_c004_T - main.R328_C004_T) < 0.05


# -------------------------------------------------------------------- the layer is PREDICTIVE
def test_cutting_the_lp_strip_steam_blows_the_ammonia_spec():
    """The whole point of F-8.  Under the frozen split this test could not be written: cutting
    FIC-329401 moved flows and left composition untouched, because there was none."""
    ppm = []
    for cut in (1.00, 0.90, 0.80, 0.70):
        _fresh(300.0)
        main.state.FIC_329401["mode"] = "AUTO"
        main.state.FIC_329401["sp"] = main.R328_C004_M931_DES * cut
        _run(45 * 60)
        ppm.append(main.state.w_328c004["NH3"] * 1e6)
    assert ppm[0] < 1.5, f"on design the condensate must be on spec, got {ppm[0]:.2f} ppm"
    assert all(b > a for a, b in zip(ppm, ppm[1:])), f"slip must rise monotonically: {ppm}"
    assert ppm[-1] > 100.0, f"a 30 % steam cut must blow the spec, got {ppm[-1]:.1f} ppm"


def test_hydrolyser_temperature_governs_the_urea_slip():
    """Independent corroboration: the Gap Resolution study predicts the slip going from ~0.32 ppm
    at 200 C to over 1200 ppm at 160 C.  The engine's Arrhenius gives 0.30 -> 1161."""
    def slip(T):
        x = main.hydrolysis_x_328c003(T, main.R328_C003_M746_DES)
        return main.R328_C003_UREA_DES * (1.0 - x) / main.R328_C003_M747_DES * 1e6

    assert slip(200.0) < 1.0, "on design the hydrolyser must meet the 1 ppm guarantee"
    assert 800.0 < slip(160.0) < 2000.0, "a 40 C loss must put the slip in the ~1000 ppm decade"
    temps = (200.0, 190.0, 180.0, 170.0, 160.0)
    vals = [slip(T) for T in temps]
    assert all(b > a for a, b in zip(vals, vals[1:])), f"monotone in temperature: {vals}"


def test_overheads_are_energy_limited_not_a_frozen_fraction():
    """R328_C002_PHI737 / R328_C004_PHI750 no longer drive the runtime.  The design duties that
    replaced them are algebraic identities of the latent-heat back-solves, so the seed is exact."""
    assert abs(main.R328_C002_Q_DES
               - main.R328_C002_M737_DES / 3600.0 * main.R328_C002_LAM737) < 1e-9
    assert abs(main.R328_C004_Q_DES
               - main.R328_C004_M750_DES / 3600.0 * main.R328_C004_LAM750) < 1e-9
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py"),
               encoding="utf-8").read()
    for frozen in ("R328_C002_PHI737 * in_c002", "R328_C004_PHI750 * in_c004"):
        assert frozen not in src, f"frozen overhead split still drives the runtime: {frozen}"
