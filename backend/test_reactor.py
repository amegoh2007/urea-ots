"""322R001 reactor self-test (spec docs/superpowers/specs/2026-06-03-322r001-reactor-design.md).
Plain asserts (repo has no pytest). Run:  python backend/test_reactor.py

C-1 REBUILD CONTRACT (Phase 1): react_322r001 is now a rigorous component mole balance with exact
atom conservation (Basis A explicit recycle-tear).  These tests enforce that contract:
  * design identity   -> overflow/off-gas reproduce the published design vectors BIT-EXACT
  * mass conservation -> mass_in(feed_corrected) - mass_out == 0 to machine zero (atom-consistent MW)
  * atom conservation -> C/N/H/O residual == 0 at design AND off-design (turndown, NH3-rich, CO2-lean)
  * closure_resid     -> a true conservation diagnostic (~0), NOT the old +250 kmol/h pin defect
The bit-exact path drives L/W with the boot-pinned design anchors (== reactor.L0_DES/W0_DES at the
seed), exactly mirroring the live step_sim call (main.py:1731), so conversion_factor == 1.0 and the
conservative NH3-partition / conversion-deficit shifts are identically zero at design."""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
from main import MW_COMP

# atom counts per component (C, N, H, O) -- urea & biuret reactions conserve each exactly
_ATOMS = {"CO2": (1, 0, 0, 2), "CH4": (1, 0, 4, 0), "H2": (0, 0, 2, 0), "H2O": (0, 0, 2, 1),
          "N2": (0, 2, 0, 0), "NH3": (0, 1, 3, 0), "O2": (0, 0, 0, 2),
          "Urea": (1, 2, 4, 1), "Biuret": (2, 3, 5, 2)}


def _atoms(vec):
    r = [0.0, 0.0, 0.0, 0.0]
    for k, n in vec.items():
        if k in _ATOMS:
            for i in range(4):
                r[i] += n * _ATOMS[k][i]
    return tuple(r)


def _mass(vec):
    return sum(vec.get(k, 0.0) * MW_COMP[k] for k in MW_COMP)


def _capture_design_feed():
    """Capture the LIVE design reactor feed exactly as the boot-pin does (fresh State(), ONE MAN
    step) so feed_corrected = feed - TEAR_DES restores the closed design feed bit-exact.  Restores a
    fresh design seed afterwards for the live-path tests below."""
    main.state = main.State()
    cap = {}
    _orig = main.react_322r001
    def _c(*a, **k):
        r = _orig(*a, **k); cap["r"] = r; return r
    main.react_322r001 = _c
    main.step_sim(0.1)
    main.react_322r001 = _orig
    main.state = main.State()
    return dict(cap["r"]["feed_kmolh"])


_DESIGN_FEED = _capture_design_feed()


def _design_hpcc(scale=1.0):
    """hpcc stand-in carrying the LIVE design reactor feed (scaled).  The rebuilt reactor is
    feed-coupled, so a real feed is mandatory (the old all-zeros stub created negative streams)."""
    return {"feed_kmolh": {k: _DESIGN_FEED.get(k, 0.0) * scale for k in MW_COMP}}


def _design_drive():
    """Boot-pinned design L/W anchors -> drive react_couple to conversion_factor == 1.0 (== the live
    step_sim path), giving the bit-exact design partition."""
    return dict(L_drive=main.REACT_L_FEED_DES, W_drive=main.REACT_W_FEED_DES)


def test_constants_present():
    for name in ("REACT_OVERFLOW_DES", "REACT_OFFGAS_DES", "REACT_XI_UREA_DES",
                 "REACT_XI_BIU_DES", "REACT_HIC605_DES_PCT", "REACT_OVERFLOW_T_C",
                 "REACT_OFFGAS_T_C", "REACT_P_BARA", "REACT_OFFGAS_P_BARA",
                 "REACT_OFFGAS_RHO", "REACT_OVERFLOW_RHO", "REACT_TT_TEMPS_C",
                 "REACT_TT_EL_MM", "REACT_TAU_TOT_MIN", "REACT_LEVEL_NLL_PCT",
                 "REACT_THETA_OG", "REACT_TEAR_DES", "REACT_L_FEED_DES",
                 "REACT_W_FEED_DES", "REACT_X_DES"):
        assert hasattr(main, name), "missing constant %s" % name
    # overflow design vector IS stream 207 (reactor overflow = stripper feed)
    for k in MW_COMP:
        assert abs(main.REACT_OVERFLOW_DES.get(k, 0.0)
                   - main.STRIP_FEED207_KMOLH.get(k, 0.0)) < 1e-6, k
    assert abs(main.REACT_HIC605_DES_PCT - 60.0) < 1e-9
    # boot-pin populated the C-1 anchors (== reactor design calibration at the seed)
    assert main.REACT_TEAR_DES is not None
    assert abs(main.REACT_L_FEED_DES - main.reactor.L0_DES) < 1e-6
    # W_FEED_DES is the FIRST-tick MAN-seed capture: the recycle-W tear is not yet settled, so it sits
    # ~7e-6 above the fully-converged W0_DES.  Bit-exactness is unaffected (pin AND live both use this
    # captured value); Phase-2 (H-1 seed re-pin) drives this first-tick creep to zero.
    assert abs(main.REACT_W_FEED_DES - main.reactor.W0_DES) < 1e-4
    # State defaults.  Assert on a FRESH State, not the shared module-level one: any earlier test
    # module that moves an HP-loop handle (e.g. the ejector spindle in test_equation_audit_species)
    # leaves main.state settled somewhere else, and "defaults" is then whatever ran last.  This was
    # a latent ordering dependency -- these assertions are about State.__init__, not about history.
    st = main.State()
    assert abs(st.HIC_322605 - 60.0) < 1e-9
    assert isinstance(st.react_overflow_kmolh, dict)
    assert abs(sum(st.react_overflow_kmolh.values())
               - sum(main.STRIP_FEED207_KMOLH.values())) < 1e-6


def test_theta_partition_consistency():
    # theta_i = OGd_i / (OVd_i + OGd_i); off-gas/overflow partition must reconstruct the design totals
    for k in MW_COMP:
        ov = main.REACT_OVERFLOW_DES.get(k, 0.0)
        og = main.REACT_OFFGAS_DES.get(k, 0.0)
        tot = ov + og
        if tot > 1e-12:
            assert abs(main.REACT_THETA_OG[k] - og / tot) < 1e-12, k
        assert 0.0 <= main.REACT_THETA_OG[k] <= 1.0, k


def test_design_identity_overflow():
    r = main.react_322r001(_design_hpcc(), main.CO2_DES_KGH / 1000.0,
                           main.REACT_HIC605_DES_PCT, **_design_drive())
    for k in MW_COMP:
        assert abs(r["overflow_kmolh"][k] - main.STRIP_FEED207_KMOLH.get(k, 0.0)) < 1e-6, k
    for k in MW_COMP:
        assert abs(r["offgas_kmolh"][k] - main.REACT_OFFGAS_DES.get(k, 0.0)) < 1e-6, k
    assert abs(r["phi"] - r["phi_des"]) < 1e-9
    assert abs(r["co2_scale"] - 1.0) < 1e-9


def test_offgas_hmb():
    r = main.react_322r001(_design_hpcc(), main.CO2_DES_KGH / 1000.0,
                           main.REACT_HIC605_DES_PCT, **_design_drive())
    og = r["offgas_kmolh"]
    n_tot = sum(og.values())
    assert abs(n_tot - 963.85) < 0.2, n_tot                       # Σ kmol/h
    mass = sum(og[k] * MW_COMP[k] for k in MW_COMP)
    assert abs(mass - 22355.0) < 50.0, mass                       # kg/h
    assert abs(mass / n_tot - 23.20) < 0.05, mass / n_tot         # MW
    assert abs(og["NH3"] / n_tot * 100.0 - 69.08) < 0.1           # mol % NH3
    assert abs(og["CO2"] / n_tot * 100.0 - 20.51) < 0.1           # mol % CO2


def test_closure_resid_zero():
    # the OLD pin defect reported closure_resid ~ +250 kmol/h (a physical impossibility baked into the
    # split-fraction vectors).  The rebuilt balance closes EXACTLY -> closure_resid ~ machine zero.
    r = main.react_322r001(_design_hpcc(), main.CO2_DES_KGH / 1000.0,
                           main.REACT_HIC605_DES_PCT, **_design_drive())
    assert abs(r["closure_resid"]) < 1e-6, r["closure_resid"]


def test_mass_conservation_design():
    # mass_in(feed_corrected) - mass_out(overflow + off-gas) == 0 to machine zero (atom-consistent MW)
    r = main.react_322r001(_design_hpcc(), main.CO2_DES_KGH / 1000.0,
                           main.REACT_HIC605_DES_PCT, **_design_drive())
    m_in = _mass(r["feed_corrected_kmolh"])
    m_out = _mass(r["overflow_kmolh"]) + _mass(r["offgas_kmolh"])
    assert abs(m_in - m_out) < 1e-6, m_in - m_out
    a_in = _atoms(r["feed_corrected_kmolh"])
    a_out = tuple(_atoms(r["overflow_kmolh"])[i] + _atoms(r["offgas_kmolh"])[i] for i in range(4))
    for i in range(4):
        assert abs(a_in[i] - a_out[i]) < 1e-6, ("CNHO"[i], a_in[i] - a_out[i])


def test_conservation_offdesign():
    # turndown, NH3-rich, and severe CO2-lean (extent-clamp active): atoms + mass must STILL close.
    cases = [("turndown70", _design_hpcc(0.7), 0.7 * main.CO2_DES_KGH / 1000.0, {}),
             ("NH3rich", {"feed_kmolh": {**{k: _DESIGN_FEED[k] for k in MW_COMP},
                                         "NH3": _DESIGN_FEED["NH3"] * 1.15,
                                         "CO2": _DESIGN_FEED["CO2"] * 0.85}},
              main.CO2_DES_KGH / 1000.0, {}),
             ("CO2lean", {"feed_kmolh": {**{k: _DESIGN_FEED[k] for k in MW_COMP},
                                         "CO2": _DESIGN_FEED["CO2"] * 0.3,
                                         "NH3": _DESIGN_FEED["NH3"] * 0.6}},
              0.5 * main.CO2_DES_KGH / 1000.0, {})]
    for tag, hpcc, co2, kw in cases:
        r = main.react_322r001(hpcc, co2, main.REACT_HIC605_DES_PCT, **kw)
        m_in = _mass(r["feed_corrected_kmolh"])
        m_out = _mass(r["overflow_kmolh"]) + _mass(r["offgas_kmolh"])
        assert abs(m_in - m_out) < 1e-6, (tag, m_in - m_out)
        a_in = _atoms(r["feed_corrected_kmolh"])
        a_out = tuple(_atoms(r["overflow_kmolh"])[i] + _atoms(r["offgas_kmolh"])[i] for i in range(4))
        for i in range(4):
            assert abs(a_in[i] - a_out[i]) < 1e-6, (tag, "CNHO"[i], a_in[i] - a_out[i])
        assert abs(r["closure_resid"]) < 1e-6, (tag, r["closure_resid"])
        # no phantom negative streams
        for k in MW_COMP:
            assert r["overflow_kmolh"][k] > -1e-9, (tag, "ov", k, r["overflow_kmolh"][k])
            assert r["offgas_kmolh"][k] > -1e-9, (tag, "og", k, r["offgas_kmolh"][k])


def test_scale_s080():
    # uniform 0.7..1.0 feed scaling with design L/W drive -> out_total scales linearly -> overflow /
    # off-gas / xi all scale by s exactly (nh3_shift == 0, delta_X == 0 at the design anchors).
    # xi scales relative to the s=1 design extent (xi_live = XI_UREA_DES * conv_fac, and conv_fac sits
    # ppm off 1.0 at the first-tick W_FEED_DES capture -> compare to the live s=1 extent, not the
    # nominal XI_UREA_DES constant, so the linear-throughput invariant is asserted exactly).
    r1 = main.react_322r001(_design_hpcc(1.0), main.CO2_DES_KGH / 1000.0,
                            main.REACT_HIC605_DES_PCT, **_design_drive())
    r = main.react_322r001(_design_hpcc(0.8), 0.8 * main.CO2_DES_KGH / 1000.0,
                           main.REACT_HIC605_DES_PCT, **_design_drive())
    assert abs(r["co2_scale"] - 0.8) < 1e-9
    # The SPLIT (theta) is still uniform, but out_total is not: the extent no longer scales with
    # load, so the products it makes and the reagents it consumes do not either.  The off-gas is
    # nearly linear because it is mostly inerts and unreacted NH3 vapour; the liquid overflow is
    # where the extra conversion shows.
    # Both NH3 streams fall BELOW linear at turndown, and for one reason: the longer residence
    # time raises the per-pass conversion, so more ammonia is consumed and less is left to
    # partition either way.  Measured at 80 % load, overflow -6.0 % and off-gas -7.5 % against
    # their linear values.  Asserting the direction rather than a fitted band -- the magnitude is
    # an output of the rate law, not a contract.
    for stream, des in (("overflow_kmolh", main.REACT_OVERFLOW_DES),
                        ("offgas_kmolh", main.REACT_OFFGAS_DES)):
        assert r[stream]["NH3"] < des["NH3"] * 0.8, stream
        assert r[stream]["NH3"] > des["NH3"] * 0.6, stream      # ... a turndown, not a collapse
    # PHASE 3 (report C-1).  These two assertions used to read
    #     assert abs(r["xi_urea"] - r1["xi_urea"] * 0.8) < 1e-6
    #     assert abs(r["xi_biu"]  - r1["xi_biu"]  * 0.8) < 1e-6
    # i.e. the extent scales EXACTLY linearly with load -- which is the load-multiplier defect
    # itself, `xi = XI_DES * s`, asserted as a contract.  A real rate law cannot do that: at 80 %
    # throughput the same vessel gives the liquid 25 % longer to react, so the per-pass conversion
    # RISES and the extent falls by less than the load does.  Measured 0.556 -> 0.630 conversion
    # between 100 % and 80 % load.
    # The split fractions above are unchanged and still scale linearly -- that part was never the
    # defect.  What is asserted here now is the physics the multiplier could not represent.
    assert r["xi_urea"] < r1["xi_urea"], "extent must still fall with load"
    assert r["xi_urea"] > r1["xi_urea"] * 0.8, "...but SUBLINEARLY: longer residence, more conversion"
    assert r["X_conv"] > r1["X_conv"], "per-pass conversion rises at turndown"
    # Biuret goes the OTHER way at turndown, and that is the physically important result: the melt
    # is more urea-rich (higher conversion) AND sits in the column longer, and r_biu ~ C_urea^2 over
    # the residence time.  Measured 2.414 -> 3.12 kmol/h between 100 % and 80 % load.  A load
    # multiplier said biuret simply falls with throughput; the plant's product-quality specification
    # actually gets WORSE on a deep turndown, which is a scenario this model can now teach.
    assert r["xi_biu"] > r1["xi_biu"], (r["xi_biu"], r1["xi_biu"])


def test_valve_phi_decoupled_phase1():
    # PHASE 1: the phi (HIC-322605) -> overflow split coupling of the prior pinned model was part of
    # the mass-CREATING defect and is intentionally NOT reintroduced (conservative theta(phi) deferred
    # to Phase 3).  The component balance is therefore INVARIANT to phi: overflow/off-gas at phi=48 %
    # equal those at phi=60 % bit-exact.  (HIC-322605 still drives the level hydraulics in step_sim.)
    r60 = main.react_322r001(_design_hpcc(), main.CO2_DES_KGH / 1000.0, 60.0, **_design_drive())
    r48 = main.react_322r001(_design_hpcc(), main.CO2_DES_KGH / 1000.0, 48.0, **_design_drive())
    for k in MW_COMP:
        assert abs(r48["overflow_kmolh"][k] - r60["overflow_kmolh"][k]) < 1e-9, k
        assert abs(r48["offgas_kmolh"][k] - r60["offgas_kmolh"][k]) < 1e-9, k
    assert abs(r48["phi"] - 0.48) < 1e-9


def test_stripper_coupling_regression():
    co2 = main.CO2_DES_KGH / 1000.0
    a = main.stripper_322e001(co2, main.STRIP_STEAM_T_DES_C, main.STRIP_P_DES_BARA)
    r = main.react_322r001(_design_hpcc(), co2, main.REACT_HIC605_DES_PCT, **_design_drive())
    b = main.stripper_322e001(co2, main.STRIP_STEAM_T_DES_C, main.STRIP_P_DES_BARA,
                              overflow_kmolh=r["overflow_kmolh"])
    for key in ("top_th", "bot_th", "top_MW", "bot_MW"):
        assert abs(a[key] - b[key]) < 1e-9, key          # design overflow == frozen constant


def test_packet_tags_and_streams():
    main.state = main.State()          # snapshot design SS (live overflow now loop-coupled; isolate)
    pkt = main.step_sim(1.0)
    assert "REACT_322R001" in pkt
    blk = pkt["REACT_322R001"]
    for tag in ("TT_322005", "TT_322006", "TT_322007", "TT_322008", "TT_322009",
                "LT_322504", "AT_322701", "HIC_322605", "HV_322605", "P_bara",
                "P_offgas", "closure_resid"):
        assert tag in blk, tag
    assert abs(blk["AT_322701"] - 3.000) < 0.01           # N/C atom ratio of overflow
    # Axial T profile: rises with elevation toward the 183 C overflow.
    #
    # PHASE 3 (report A-8).  These used to assert 182.9 and 172.6 to +/-0.1 C.  Those numbers were
    # not measurements -- they were the output of the fitted Damkohler heat-release shape the energy
    # balance replaced, i.e. the test was asserting the fit against itself.  The plant's own DCS
    # trend (References/Urea_NormalOp_29-06-2025_Trends.md, 1921 samples) reads
    #
    #     TT-322008 171.134   TT-322007 174.303   TT-322006 179.697   TT-322005 183.084
    #
    # and the retired shape was 6.5 C out at TT-322007: it put nearly the whole column rise below
    # the second thermowell, where the real profile is very nearly linear.  The assertions now point
    # at the MEASURED values, with a 1.0 C tolerance that reflects the model's actual accuracy
    # (RMS 0.43 C against those four readings, against 3.66 C for the shape it replaced).
    assert abs(blk["TT_322005"] - 183.084) < 1.0   # N6 A top  (EL +21700)
    assert abs(blk["TT_322006"] - 179.697) < 1.0   # N6 B      (EL +14800)
    assert abs(blk["TT_322007"] - 174.303) < 1.0   # N6 C      (EL  +7900)
    assert abs(blk["TT_322008"] - 171.134) < 1.0   # N6 D bot  (EL  +1000, near feed inlet)
    assert blk["TT_322005"] > blk["TT_322006"] > blk["TT_322007"] > blk["TT_322008"]
    assert abs(blk["HIC_322605"] - 60.0) < 0.1
    assert abs(blk["HV_322605"] - 60.0) < 0.1
    # rebuilt balance closes -> the live design-seed closure residual is now ~0 (was ~+2.4 kmol/h)
    assert abs(blk["closure_resid"]) < 1.0, blk["closure_resid"]
    st = pkt["STREAMS"]
    assert "REACT_OVERFLOW" in st and "REACT_OFFGAS" in st
    # at the design default state, overflow == stream 207 (conserving model closes the loop tightly)
    assert abs(st["REACT_OVERFLOW"]["mol_kmolh"]
               - sum(main.STRIP_FEED207_KMOLH.values())) < 3.0
    # off-gas stream composition closes
    assert abs(sum(st["REACT_OFFGAS"]["mol_pct"].values()) - 100.0) < 0.2
    assert st["REACT_OVERFLOW"]["dst"] == "322E001"
    assert st["REACT_OFFGAS"]["dst"] == "322E003"


def test_hic605_command():
    main.state.HIC_322605 = 60.0
    main.handle_cmd({"type": "hic605_set", "id": "HIC-322605", "mode": "MAN", "op": 48.0})
    assert abs(main.state.HIC_322605 - 48.0) < 1e-9
    # clamp
    main.handle_cmd({"type": "hic605_set", "id": "HIC-322605", "mode": "MAN", "op": 130.0})
    assert abs(main.state.HIC_322605 - 100.0) < 1e-9
    main.handle_cmd({"type": "hic605_set", "id": "HIC-322605", "mode": "MAN", "op": -5.0})
    assert abs(main.state.HIC_322605 - 0.0) < 1e-9
    main.state.HIC_322605 = 60.0                       # restore design default for later tests


def test_at322701_nc_ratio():
    # AT-322701: molar N/C of 322R001 overflow. Design N = 4002.4·1 + 1302.6·2 + 2.414·3 = 6614.84;
    #            C = 897.7·1 + 1302.6·1 + 2.414·2 = 2205.13;  N/C = 3.000.
    r = main.react_322r001(_design_hpcc(), main.CO2_DES_KGH / 1000.0,
                           main.REACT_HIC605_DES_PCT, **_design_drive())
    nc = main.react_nc_ratio(r["overflow_kmolh"])
    assert abs(nc - 3.000) < 0.01, nc
    # PHASE 3 (report C-1).  This used to assert the overflow N/C was INVARIANT to throughput
    # scaling to 1e-6, which holds only while the extent is a load multiplier and the whole vector
    # scales uniformly.  With a real rate law a turndown lengthens the residence time, raises the
    # per-pass conversion, and so consumes more ammonia per unit carbon: the overflow N/C FALLS.
    # Measured 3.000 -> 2.968 between 100 % and 70 % load.  That is a real, operator-visible
    # behaviour on AT-322701 that the multiplier could not produce at all.
    r2 = main.react_322r001(_design_hpcc(0.7), 0.7 * main.CO2_DES_KGH / 1000.0,
                            main.REACT_HIC605_DES_PCT, **_design_drive())
    nc2 = main.react_nc_ratio(r2["overflow_kmolh"])
    assert nc2 < nc, (nc2, nc)
    assert abs(nc2 - nc) < 0.10, (nc2, nc)      # ... but a turndown, not a collapse


def test_dynamic_level_responds_to_hv605():
    s = main.state
    # φ=φ_des -> Q_in=Q_out -> dV/dt=0 -> level holds (steady inventory)
    s.HIC_322605 = main.REACT_HIC605_DES_PCT; s.react_level_pct = 80.0
    for _ in range(20):
        main.step_sim(1.0)
    assert abs(s.react_level_pct - 80.0) < 0.5, s.react_level_pct
    # OPEN HV-322605 (φ=90 % > φ_des) -> Q_out>Q_in -> level FALLS (user-reported requirement).
    # It falls to the overflow-funnel lip (77.2 % of the 25 m frame), where the weir takes over from
    # the valve and passes production (As-Built Phase 5r).
    s.HIC_322605 = 90.0; s.react_level_pct = 80.0
    for _ in range(240):
        main.step_sim(1.0)
    assert s.react_level_pct < 79.0, s.react_level_pct
    # THROTTLE below design (φ=30 % < φ_des) -> Q_in>Q_out -> level RISES
    s.HIC_322605 = 30.0; s.react_level_pct = 50.0
    for _ in range(120):
        main.step_sim(1.0)
    assert s.react_level_pct > 51.0, s.react_level_pct
    s.HIC_322605 = main.REACT_HIC605_DES_PCT             # restore design defaults
    s.react_level_pct = main.REACT_LEVEL_NLL_PCT


def test_hv322605_kv_follows_the_vendor_sizing_table():
    # CONVAL sizing UD-MR-G00-DZ-0042-021 p.3: linear trim, Kvs 600, the mean-flow point at 58.961 %
    # stroke is Kv 358.69 and the max-flow point at 65.516 % is Kv 397.24.
    kv = main.reactor.hv322605_kv
    assert kv(0.0) == 0.0 and kv(100.0) == 600.0
    for s_pct, k in ((5.0, 41.4), (25.0, 159.0), (50.0, 306.0), (75.0, 453.0)):
        assert abs(kv(s_pct) - k) < 1e-9, (s_pct, kv(s_pct))
    assert abs(kv(58.961) - 358.69) < 0.05, kv(58.961)
    assert abs(kv(65.516) - 397.24) < 0.05, kv(65.516)
    assert all(kv(a) < kv(a + 1.0) for a in range(0, 100))


def test_the_reactor_discharges_over_its_overflow_funnel():
    # A-12: min(valve at design dP, Francis weir over the 1044 mm funnel lip).  The lip sits 0.7 m
    # under NLL from LT-322504's geometry (top tap 1.0 m above it, 1.5 m span, NLL 80 %).
    r, m_des = main.reactor, main._react_mdot_kgh
    lip, cw, t_b = main.REACT_WEIR_CREST_M, main.REACT_WEIR_CW, main.REACT_T_BULK_DES
    assert abs(main.REACT_LEVEL_DES_M - lip - 0.7) < 1e-9, lip
    th = main.REACT_HIC605_DES_PCT
    out = lambda lvl, theta: r.outlet_line_outflow_kgph(lvl, m_des, theta, th, lip, cw, t_b)
    assert out(main.REACT_LEVEL_DES_M, th) == m_des                        # bit-exact at design
    assert out(main.REACT_LEVEL_DES_M, 90.0) == m_des * r.hv322605_kv(90.0) / r.hv322605_kv(th)
    assert out(main.REACT_LEVEL_DES_M, 0.0) == 0.0                         # shut valve
    assert out(lip, 100.0) == 0.0 and out(lip - 1.0, 100.0) == 0.0          # no drain below the lip
    # the free-overflow head at the design flow is a few cm (Francis: 0.048 m at 228 m3/h)
    h = (m_des / (r.liquid_density(t_b) * cw)) ** (2.0 / 3.0)
    assert 0.03 < h < 0.07, h
    assert abs(out(lip + h, 100.0) - m_des) < 1e-6 * m_des
    # the level is state, the valve does not see it while the funnel is flooded
    assert out(main.REACT_LEVEL_DES_M + 1.0, 75.0) == out(main.REACT_LEVEL_DES_M - 0.5, 75.0)


def test_the_empty_reactor_guard_is_gone():
    import inspect
    src = inspect.getsource(main.step_sim)
    assert "react_level_pct <= 0.0 and m_out_kgh > m_in_kgh" not in src
    assert "REACT_WEIR_CREST_M" in src and "REACT_PHI_FWD_FLOOR" not in dir(main)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    fails = 0
    for t in tests:
        try:
            t(); print("PASS", t.__name__)
        except Exception:
            fails += 1; print("FAIL", t.__name__); traceback.print_exc()
    raise SystemExit(1 if fails else 0)
