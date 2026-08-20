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
    assert abs(r["overflow_kmolh"]["NH3"] - main.REACT_OVERFLOW_DES["NH3"] * 0.8) < 1e-6
    assert abs(r["offgas_kmolh"]["NH3"] - main.REACT_OFFGAS_DES["NH3"] * 0.8) < 1e-6
    assert abs(r["xi_urea"] - r1["xi_urea"] * 0.8) < 1e-6
    assert abs(r["xi_biu"] - r1["xi_biu"] * 0.8) < 1e-6


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
    # residence-time axial T profile: rises with elevation toward 183 C overflow
    assert abs(blk["TT_322005"] - 182.9) < 0.1     # N6 A top  (EL +21700)
    assert abs(blk["TT_322008"] - 172.6) < 0.1     # N6 D bot  (EL +1000, near feed inlet)
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
    # invariant to uniform throughput scaling (overflow scales uniformly -> N/C unchanged)
    r2 = main.react_322r001(_design_hpcc(0.7), 0.7 * main.CO2_DES_KGH / 1000.0,
                            main.REACT_HIC605_DES_PCT, **_design_drive())
    assert abs(main.react_nc_ratio(r2["overflow_kmolh"]) - nc) < 1e-6


def test_dynamic_level_responds_to_hv605():
    s = main.state
    # φ=φ_des -> Q_in=Q_out -> dV/dt=0 -> level holds (steady inventory)
    s.HIC_322605 = main.REACT_HIC605_DES_PCT; s.react_level_pct = 80.0
    for _ in range(20):
        main.step_sim(1.0)
    assert abs(s.react_level_pct - 80.0) < 0.5, s.react_level_pct
    # OPEN HV-322605 (φ=90 % > φ_des) -> Q_out>Q_in -> level FALLS (user-reported requirement).
    # The drain near the 80 % design holdup is hydrostatically self-limiting (Q_out falls as head
    # drops), so the approach to the new equilibrium is asymptotic -> allow an adequate horizon.
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
