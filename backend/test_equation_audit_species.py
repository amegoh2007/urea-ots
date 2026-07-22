"""Regression gate for the EQUATION_AUDIT F-8 / TD-009 fix — downstream component species balance.

WHY THIS FILE EXISTS
--------------------
Species tracking used to stop dead at LV-322501: everything downstream was lumped mass moved by
design split fractions, so there was no C2 component balance and no C6 summation equation past the
HP loop.  The layer under test rides ON TOP of the existing total-mass and energy ODEs — it must
never perturb them — and adds:

  * a six-species mass-fraction state per downstream stage, Sum w == 1 at all times (C6);
  * relative-volatility vapour compositions, Sum y == 1, anchored on the PFD (C6 again);
  * real biuret kinetics, 2 Urea -> Biuret + NH3, with the stripper's own activation energy (C7);
  * a documented reconciliation onto the PFD urea anchors where they exist (finding F-11).

Run from backend/:  python -m pytest test_equation_audit_species.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main  # noqa: E402

DT = 0.25
LIQ = ("C003", "F004", "F010", "D002", "E001", "E003")
VAP = ("305", "701", "evap", "v1", "v2")


def _fresh(seconds=300.0):
    main.state = main.State()
    return _run(seconds)


def _run(seconds):
    out = None
    for _ in range(int(seconds / DT)):
        out = main.step_sim(DT)
    return out


# --------------------------------------------------------------------- C6 summation equations
def test_liquid_summation_closes_at_every_stage():
    """Sum w == 1 is the C6 summation equation.  It must hold on every downstream stage, at the
    design seed and after a long run — a species vector that does not sum to one is not a
    composition."""
    t = _fresh(300.0)
    for tag in LIQ:
        assert abs(t["SPECIES_323_324"]["sum"][tag] - 100.0) < 1e-6, (tag,)
    t = _run(900.0)
    for tag in LIQ:
        assert abs(t["SPECIES_323_324"]["sum"][tag] - 100.0) < 1e-6, (tag,)


def test_vapour_summation_closes_at_every_stage():
    """Sum y == 1 for every vapour leaving the train.  y is not a free vector: it is the
    relative-volatility normalisation of the live liquid, which IS the summation equation."""
    t = _fresh(300.0)
    for tag in VAP:
        assert abs(sum(t["SPECIES_323_324"]["vap"][tag].values()) - 100.0) < 1e-3, (tag,)


def test_species_fractions_are_physical():
    """Every mass fraction in [0, 1], at the seed and under a disturbance."""
    t = _fresh(300.0)
    main.state.LIC_323501["mode"] = "MAN"
    main.state.LIC_323501["op"] = 75.0
    t = _run(600.0)
    for tag in LIQ:
        for k, v in t["SPECIES_323_324"]["liq"][tag].items():
            assert -1e-9 <= v <= 100.0 + 1e-9, (tag, k, v)


# ------------------------------------------------------------------- PFD anchors are reproduced
def test_design_compositions_sit_on_their_pfd_anchors():
    """Every stage must land on its PFD stream composition.  323F010 is still NOT pinned — it
    publishes the strength the component balance actually produces — but since F-11 was closed by
    adding stream 331 that number now arrives on the anchor by itself, which is the real test."""
    t = _fresh(600.0)
    liq = t["SPECIES_323_324"]["liq"]
    assert abs(liq["C003"]["Urea"] - 68.74) < 0.10, liq["C003"]["Urea"]     # PFD stream 314
    assert abs(liq["F004"]["Urea"] - 71.74) < 0.10, liq["F004"]["Urea"]     # PFD stream 319
    assert abs(liq["D002"]["Urea"] - 80.00) < 1e-6, liq["D002"]["Urea"]     # PFD stream 317 anchor
    assert abs(liq["E001"]["Urea"] - 94.31) < 0.02, liq["E001"]["Urea"]     # PFD stream 401
    assert abs(liq["E003"]["Urea"] - 97.71) < 0.02, liq["E003"]["Urea"]     # PFD stream 402
    # F-11 CLOSED: un-pinned and still on anchor (79.96 vs 80.00).  It used to sit at 78.44.
    assert abs(liq["F010"]["Urea"] - 80.00) < 0.10, liq["F010"]["Urea"]     # PFD stream 315


def test_species_and_scalar_urea_agree():
    """The species layer and the mass/energy scalar path must publish the SAME melt strength — two
    disagreeing urea numbers on one HMI screen would be worse than the constant this replaced."""
    t = _fresh(600.0)
    sp = t["SPECIES_323_324"]["urea_pct_species"]
    assert abs(sp["E001"] - t["EVAP_324"]["E001"]["urea_pct"]) < 0.05
    assert abs(sp["E003"] - t["EVAP_324"]["E003"]["urea_pct"]) < 0.05


def test_biuret_rises_monotonically_through_the_train():
    """C7.  Biuret is FORMED, never consumed, and the PFD shows it climbing 0.24 % at the stripper
    bottoms to 0.85 % in the final melt.  The extents are Arrhenius, so the two hot evaporators
    must dominate — this is the whole reason UF-85 is dosed."""
    t = _fresh(600.0)
    liq = t["SPECIES_323_324"]["liq"]
    xi = t["SPECIES_323_324"]["xi_biuret_kmolh"]
    assert liq["C003"]["Biuret"] < liq["F010"]["Biuret"] < liq["E001"]["Biuret"] \
        < liq["E003"]["Biuret"]
    assert abs(liq["E003"]["Biuret"] - 0.85) < 0.05, liq["E003"]["Biuret"]   # PFD stream 402
    assert all(v >= 0.0 for v in xi.values()), xi                            # never runs backwards
    assert xi["E001"] > xi["C003"] > 0.0, xi                                 # hottest stage wins


def test_biuret_extent_is_arrhenius_in_temperature():
    """The extent must respond to stage temperature with the stripper's activation energy, and be
    exactly its design value at the design anchor (that is what makes the layer stationary)."""
    st = main.SOL_STAGES["E001"]
    xi_des = main.sol_biuret_xi("E001", st["M"], st["w"], st["T"])
    assert abs(xi_des - main.SOL_E001["xi"]) < 1e-12, (xi_des, main.SOL_E001["xi"])
    assert main.sol_biuret_xi("E001", st["M"], st["w"], st["T"] + 10.0) > xi_des
    assert main.sol_biuret_xi("E001", st["M"], st["w"], st["T"] - 10.0) < xi_des
    # second order in urea: halving the urea fraction quarters the extent
    half = dict(st["w"]); half["Urea"] = st["w"]["Urea"] / 2.0
    assert abs(main.sol_biuret_xi("E001", st["M"], half, st["T"]) - xi_des / 4.0) < 1e-9


# ------------------------------------------------------- the layer must not disturb what it rides on
def test_species_layer_does_not_perturb_the_mass_or_energy_balance():
    """The whole design of this layer is that it is ADDITIVE.  The 323/324 anchors that F-1..F-5
    established must be bit-identical to what they were without it."""
    t = _fresh(600.0)
    e1, e3 = t["EVAP_324"]["E001"], t["EVAP_324"]["E003"]
    c3, f4, f10 = (t["RECIRC_323"]["C003"], t["RECIRC_323"]["F004"], t["RECIRC_323"]["F010"])
    assert e1["urea_pct"] == 94.3 and e3["urea_pct"] == 97.7
    assert e1["TT_324001"] == 130.0 and e3["TT_324002"] == 140.0
    assert f4["TT_323005"] == 106.0
    assert abs(c3["v305_th"] - main.R323_M305_DES / 1000.0) < 6e-3
    assert abs(f4["v701_th"] - main.R323_M701_DES / 1000.0) < 6e-3
    assert abs(f10["evap_th"] - main.R323_MEVAP_DES / 1000.0) < 6e-3
    assert abs(e1["vapour_th"] - main.R324_V1_DES / 1000.0) < 6e-3
    assert abs(e3["vapour_th"] - main.R324_V2_DES / 1000.0) < 6e-3


def test_stripper_composition_now_reaches_the_product():
    """The point of the whole layer: the downstream train was BLIND to what the stripper did.  A
    strip-efficiency disturbance must now move the downstream composition."""
    t = _fresh(300.0)
    base = t["SPECIES_323_324"]["liq"]["C003"]["NH3"]
    s = main.state
    s.HIC_322602 = 55.0                    # ejector spindle: exogenous, shifts the whole HP loop
    t = _run(900.0)
    assert t["SPECIES_323_324"]["liq"]["C003"]["NH3"] != base
    for tag in LIQ:                        # ... and the summation still closes throughout
        assert abs(t["SPECIES_323_324"]["sum"][tag] - 100.0) < 1e-6, (tag,)


def test_pin_strength_preserves_the_minor_species_and_the_sum():
    """sol_pin_strength moves ONLY the urea/water pair; the rigorously balanced minor species must
    survive untouched and the vector must still sum to one."""
    w = dict(main.W_S401)
    out = main.sol_pin_strength(w, 0.90)
    for k in ("Biuret", "NH3", "CO2", "HCHO"):
        assert out[k] == w[k], k
    assert abs(sum(out.values()) - 1.0) < 1e-12
    assert abs(out["Urea"] - 0.90) < 1e-12
    # identity at the anchor itself
    same = main.sol_pin_strength(w, w["Urea"])
    assert all(abs(same[k] - w[k]) < 1e-12 for k in main.SOL_SPECIES)


# --------------------------------- F-11: PFD stream 331 is a real feed to 323E010 / 323F010
def test_stream_331_closes_the_f010_total_mass_balance():
    """323F010 takes TWO feeds — stream 319 from the flash drum and stream 331, the urea-recovery
    return from the granulation scrubber — and both enter through 323E010.  With 331 present the
    stage balance closes exactly; without it the back-solve had to clip 1414 kg/h of NEGATIVE urea
    vapour, which is what finding F-11 reported."""
    assert abs((main.R323_M319_DES + main.R323_M331_DES)
               - (main.R323_MEVAP_DES + main.R323_M317_DES)) < 1e-9
    assert main.SOL_F010["resid"] == 0.0, main.SOL_F010["resid"]
    # every design vapour component is now physically possible without clipping
    assert all(main.SOL_F010["y"][k] >= 0.0 for k in main.SOL_SPECIES)
    assert main.SOL_F010["alpha"]["Urea"] > 0.0        # real (small) urea carryover, was clipped to 0
    assert main.SOL_F010["alpha"]["CO2"] > main.SOL_F010["alpha"]["NH3"] > 1.0   # ordering is physical


def test_stream_331_is_published_and_loads_the_pre_evaporator():
    """331 is a battery-limit inflow (the granulation scrubber is outside the simulated boundary),
    so it is constant — but it must be VISIBLE on the HMI and it must show up in the balance, or the
    operator sees a separator whose outflow exceeds its inflow."""
    t = _fresh(300.0)
    f10 = t["RECIRC_323"]["F010"]
    assert abs(f10["feed331_th"] - main.R323_M331_DES / 1000.0) < 6e-3
    assert abs(f10["product317_th"] - main.R323_M317_DES / 1000.0) < 6e-3
    # C1 across the stage, read off the published telemetry
    assert abs((f10["feed331_th"] + t["RECIRC_323"]["F004"]["drain319_th"])
               - (f10["evap_th"] + f10["product317_th"])) < 1e-2
    # 331 arrives at 40 C against a 99 C product, so it is a heat SINK: the duty must exceed what
    # the single-feed model asked for (~5048 kW), not merely differ from it.
    assert main.R323_E010_Q_DES_KW > 6000.0, main.R323_E010_Q_DES_KW
    assert abs(f10["Q_kW"] - main.R323_E010_Q_DES_KW) < 1.0


def test_formaldehyde_traces_from_its_only_source_to_the_melt():
    """Decisive evidence for the F-11 topology: stream 331 is the ONLY formaldehyde source anywhere
    in the plant (UF-85 dosed into the granulation scrubber), and HCHO is non-volatile, so whatever
    331 brings in must reappear in the product.  Before the fix the melt carried HCHO that no stream
    fed — it existed only as a frozen constant in W_S317."""
    t = _fresh(600.0)
    liq = t["SPECIES_323_324"]["liq"]
    assert liq["C003"]["HCHO"] == 0.0 and liq["F004"]["HCHO"] == 0.0   # upstream of the injection
    assert liq["F010"]["HCHO"] > 0.0                                   # ... appears exactly here
    assert liq["F010"]["HCHO"] < liq["E001"]["HCHO"] < liq["E003"]["HCHO"]  # concentrates, never boils
    assert abs(liq["E003"]["HCHO"] - 0.0099) < 5e-4, liq["E003"]["HCHO"]    # PFD stream 402
    # closes on the PFD to better than 2 % on a 7.5 kg/h stream
    h_in = main.R323_M331_DES * main.W_S331["HCHO"]
    h_out = main.R323_M317_DES * main.W_S317["HCHO"]
    assert abs(h_out / h_in - 1.0) < 0.02, (h_in, h_out)


# ------------------------------------------ F-7 / TD-008: 328C003 hydrolyser reaction extent
def test_hydrolyser_design_anchor_is_exact():
    """The overhead generation decomposes into reaction + strip, and both must be exactly their
    design value at the seed, or the 328C003 pressure ODE stops being stationary."""
    assert abs(main.R328_C003_GASHYD_DES + main.R328_C003_GASSTR_DES
               - main.R328_C003_M748_DES) < 1e-9
    assert main.hydrolysis_x_328c003(main.R328_C003_T, main.R328_C003_M746_DES) \
        == main.R328_C003_X_DES
    assert main.R328_C003_GASSTR_DES > 0.0            # the strip term must not go negative
    # 2 Urea couple: NH2CONH2 + H2O -> 2 NH3 + CO2 conserves mass
    assert abs(main.R328_HYD_GAS_MW - (main.MW_SOL["Urea"] + main.MW_SOL["H2O"])) < 1e-3


def test_hydrolysis_conversion_is_arrhenius_and_residence_limited():
    """C7.  Conversion must FALL when the column cools and when it is overloaded — the two levers an
    operator actually has.  Before the fix the extent did not exist: the overhead was a frozen split
    fraction of the inflow and the rate law lived only in a read-only soft sensor."""
    md = main.R328_C003_M746_DES
    xs = [main.hydrolysis_x_328c003(T, md) for T in (140.0, 160.0, 180.0, 200.0)]
    assert xs[0] < xs[1] < xs[2] < xs[3], xs                    # hotter -> more conversion
    assert xs[0] < 0.75, xs[0]                                  # 140 C really does break through
    ov = [main.hydrolysis_x_328c003(200.0, md * r) for r in (1.0, 2.0, 3.0)]
    assert ov[0] > ov[1] > ov[2], ov                            # overload -> less residence
    assert main.hydrolysis_x_328c003(200.0, md * 3.0) < 0.99    # ... measurably


def test_hydrolyser_publishes_a_mass_balance_urea_slip():
    """AI-328701's urea slip is now a mass-balance result of the extent, not an inferential running
    alongside an unrelated split fraction."""
    t = _fresh(600.0)
    c = t["DESORB_328"]["C003"]
    assert abs(c["X_hydrolysis"] - main.R328_C003_X_DES * 100.0) < 1e-3
    assert abs(c["gas_hyd_kgh"] + c["gas_strip_kgh"] - main.R328_C003_M748_DES) < 1.0
    assert 0.0 <= c["urea_slip_ppm"] < 2.0, c["urea_slip_ppm"]   # design: ~0.32 ppm
    assert c["urea_in_kgh"] > 0.0 and c["xi_urea_kmolh"] > 0.0
