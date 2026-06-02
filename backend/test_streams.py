"""Stream-inspector self-test: make_stream() invariants + packet integration.
Plain asserts (repo has no pytest). Run:  python backend/test_streams.py"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
from main import make_stream, MW_COMP

REQ_KEYS = {"name", "src", "dst", "phase", "T_C", "P_bara", "mass_kgh", "mass_th",
            "mol_kmolh", "MW", "rho", "vol_m3h", "mol_pct", "mass_pct"}


def test_make_stream_invariants():
    s = make_stream({"NH3": 1000.0, "CO2": 200.0}, 100.0, 144.2,
                    "t", "A", "B", "gas", rho=600.0)
    assert REQ_KEYS <= set(s), "missing keys: %s" % (REQ_KEYS - set(s))
    exp_kgh = 1000.0 * MW_COMP["NH3"] + 200.0 * MW_COMP["CO2"]
    assert abs(s["mass_kgh"] - round(exp_kgh, 1)) < 0.2          # mass = Σ nᵢ·MWᵢ
    assert abs(s["mass_th"] - s["mass_kgh"] / 1000.0) < 1e-3   # both rounded from m_tot (1 dp vs 3 dp)
    assert abs(sum(s["mol_pct"].values()) - 100.0) < 0.1          # mol % closes
    assert abs(sum(s["mass_pct"].values()) - 100.0) < 0.1         # mass % closes
    assert abs(s["vol_m3h"] - round(exp_kgh / 600.0, 2)) < 0.1    # vol = m/ρ


def test_make_stream_zero_flow():
    s = make_stream({}, 50.0, 1.0, "z", "A", "B", "liquid")
    assert s["mass_kgh"] == 0.0 and s["MW"] == 0.0
    assert s["rho"] is None and s["vol_m3h"] is None              # unknown ρ → None
    assert sum(s["mol_pct"].values()) == 0.0


def test_streams_in_packet():
    pkt = main.step_sim(1.0)
    assert "STREAMS" in pkt
    st = pkt["STREAMS"]
    expect = {"NH3_FEED", "PUMP_SUCT", "HP_DISCH", "CARB_RECYCLE", "EJ_DISCH",
              "CO2_FEED", "STRIP_TOP", "STRIP_BOT", "HPCC_PROD", "HPCC_STEAM", "HPCC_COND"}
    assert expect <= set(st), "missing streams: %s" % (expect - set(st))
    for sid, s in st.items():
        assert REQ_KEYS <= set(s), sid
        if s["mol_kmolh"] > 0:
            assert abs(sum(s["mol_pct"].values()) - 100.0) < 0.2, sid
            assert abs(sum(s["mass_pct"].values()) - 100.0) < 0.2, sid


def test_streams_crosslink():
    main.state.tank_level_frac = 0.5
    main.state.XV_321901 = True
    main.state.XV_322901 = True
    main.state.XV_322902 = True
    main.state.pumpA["on"] = True
    main.state.pumpB["on"] = True
    pkt = {}
    for _ in range(40):
        pkt = main.step_sim(0.5)
    st = pkt["STREAMS"]
    assert abs(st["EJ_DISCH"]["mass_th"] - pkt["EJ_322F001"]["total_th"]) < 0.05
    assert abs(st["STRIP_TOP"]["mass_th"] - pkt["STRIP_322E001"]["top_th"]) < 0.05
    assert abs(st["HPCC_PROD"]["mass_th"]
               - (pkt["HPCC_322E002"]["gas_th"] + pkt["HPCC_322E002"]["liq_th"])) < 0.1


if __name__ == "__main__":
    fails = 0
    for t in (test_make_stream_invariants, test_make_stream_zero_flow,
              test_streams_in_packet, test_streams_crosslink):
        try:
            t(); print("PASS", t.__name__)
        except Exception:
            fails += 1; print("FAIL", t.__name__); traceback.print_exc()
    raise SystemExit(1 if fails else 0)
