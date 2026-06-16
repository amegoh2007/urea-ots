"""322R001 reactor self-test (spec docs/superpowers/specs/2026-06-03-322r001-reactor-design.md).
Plain asserts (repo has no pytest). Run:  python backend/test_reactor.py"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
from main import MW_COMP


def test_constants_present():
    for name in ("REACT_OVERFLOW_DES", "REACT_OFFGAS_DES", "REACT_XI_UREA_DES",
                 "REACT_XI_BIU_DES", "REACT_HIC605_DES_PCT", "REACT_OVERFLOW_T_C",
                 "REACT_OFFGAS_T_C", "REACT_P_BARA", "REACT_OFFGAS_P_BARA",
                 "REACT_OFFGAS_RHO", "REACT_OVERFLOW_RHO", "REACT_TT_TEMPS_C",
                 "REACT_TT_EL_MM", "REACT_TAU_TOT_MIN", "REACT_LEVEL_NLL_PCT"):
        assert hasattr(main, name), "missing constant %s" % name
    # overflow design vector IS stream 207 (reactor overflow = stripper feed)
    for k in MW_COMP:
        assert abs(main.REACT_OVERFLOW_DES.get(k, 0.0)
                   - main.STRIP_FEED207_KMOLH.get(k, 0.0)) < 1e-6, k
    assert abs(main.REACT_HIC605_DES_PCT - 60.0) < 1e-9
    # State defaults
    assert abs(main.state.HIC_322605 - 60.0) < 1e-9
    assert isinstance(main.state.react_overflow_kmolh, dict)
    assert abs(sum(main.state.react_overflow_kmolh.values())
               - sum(main.STRIP_FEED207_KMOLH.values())) < 1e-6


def _design_hpcc(feed_tot=None):
    """Minimal hpcc stand-in: feed_kmolh dict only (closure probe)."""
    feed = {k: 0.0 for k in MW_COMP}
    if feed_tot is not None:
        feed["H2O"] = feed_tot          # lump total onto one key; only the sum matters
    return {"feed_kmolh": feed}


def test_design_identity_overflow():
    r = main.react_322r001(_design_hpcc(), main.CO2_DES_KGH / 1000.0,
                           main.REACT_HIC605_DES_PCT)
    for k in MW_COMP:
        assert abs(r["overflow_kmolh"][k] - main.STRIP_FEED207_KMOLH.get(k, 0.0)) < 1e-6, k
    assert abs(r["phi"] - r["phi_des"]) < 1e-9
    assert abs(r["co2_scale"] - 1.0) < 1e-9


def test_offgas_hmb():
    r = main.react_322r001(_design_hpcc(), main.CO2_DES_KGH / 1000.0,
                           main.REACT_HIC605_DES_PCT)
    og = r["offgas_kmolh"]
    n_tot = sum(og.values())
    assert abs(n_tot - 963.85) < 0.2, n_tot                       # Σ kmol/h
    mass = sum(og[k] * MW_COMP[k] for k in MW_COMP)
    assert abs(mass - 22355.0) < 50.0, mass                       # kg/h
    assert abs(mass / n_tot - 23.20) < 0.05, mass / n_tot         # MW
    assert abs(og["NH3"] / n_tot * 100.0 - 69.08) < 0.1           # mol % NH3
    assert abs(og["CO2"] / n_tot * 100.0 - 20.51) < 0.1           # mol % CO2


def test_closure_resid():
    feed_tot = 10943.7                                            # design Σ feed (kmol/h)
    r = main.react_322r001(_design_hpcc(feed_tot), main.CO2_DES_KGH / 1000.0,
                           main.REACT_HIC605_DES_PCT)
    assert 240.0 < r["closure_resid"] < 260.0, r["closure_resid"] # ≈ +250.56
    assert r["closure_resid"] / feed_tot < 0.03                   # bounded < 3 %


def test_scale_s080():
    r = main.react_322r001(_design_hpcc(), 0.8 * main.CO2_DES_KGH / 1000.0,
                           main.REACT_HIC605_DES_PCT)
    assert abs(r["co2_scale"] - 0.8) < 1e-9
    assert abs(r["overflow_kmolh"]["NH3"] - main.REACT_OVERFLOW_DES["NH3"] * 0.8) < 1e-6
    assert abs(r["offgas_kmolh"]["NH3"] - main.REACT_OFFGAS_DES["NH3"] * 0.8) < 1e-6
    assert abs(r["xi_urea"] - main.REACT_XI_UREA_DES * 0.8) < 1e-6


def test_valve_phi048():
    # HIC-322605 = 48 % (−20 % of 60) -> φ/φ_des = 0.8 -> overflow ×0.8, off-gas unchanged
    r = main.react_322r001(_design_hpcc(), main.CO2_DES_KGH / 1000.0, 48.0)
    assert abs(r["overflow_kmolh"]["NH3"] - main.REACT_OVERFLOW_DES["NH3"] * 0.8) < 1e-6
    assert abs(r["offgas_kmolh"]["NH3"] - main.REACT_OFFGAS_DES["NH3"]) < 1e-6


def test_stripper_coupling_regression():
    co2 = main.CO2_DES_KGH / 1000.0
    a = main.stripper_322e001(co2, main.STRIP_STEAM_T_DES_C, main.STRIP_P_DES_BARA)
    r = main.react_322r001(_design_hpcc(), co2, main.REACT_HIC605_DES_PCT)
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
    st = pkt["STREAMS"]
    assert "REACT_OVERFLOW" in st and "REACT_OFFGAS" in st
    # at the design default state, overflow ≈ stream 207 (live loop-coupled model carries a
    # ~2.4 kmol/h, 0.03 % closure residual vs the pinned 207 vector — well inside engineering tol)
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
                           main.REACT_HIC605_DES_PCT)
    nc = main.react_nc_ratio(r["overflow_kmolh"])
    assert abs(nc - 3.000) < 0.01, nc
    # invariant to throughput s and valve φ (pinned overflow scales uniformly)
    r2 = main.react_322r001(_design_hpcc(), 0.7 * main.CO2_DES_KGH / 1000.0, 48.0)
    assert abs(main.react_nc_ratio(r2["overflow_kmolh"]) - nc) < 1e-6


def test_dynamic_level_responds_to_hv605():
    s = main.state
    # φ=φ_des -> Q_in=Q_out -> dV/dt=0 -> level holds (steady inventory)
    s.HIC_322605 = main.REACT_HIC605_DES_PCT; s.react_level_pct = 80.0
    for _ in range(20):
        main.step_sim(1.0)
    assert abs(s.react_level_pct - 80.0) < 0.5, s.react_level_pct
    # OPEN HV-322605 (φ=90 % > φ_des) -> Q_out>Q_in -> level FALLS (user-reported requirement)
    s.HIC_322605 = 90.0; s.react_level_pct = 80.0
    for _ in range(120):
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
