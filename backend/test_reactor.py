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
                 "REACT_OFFGAS_RHO", "REACT_OVERFLOW_RHO", "REACT_TEMP_HEIGHTS_C",
                 "REACT_LEVEL_NLL_PCT"):
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
