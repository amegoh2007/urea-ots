"""Integration tests for /api/ctrl REST routes.
Uses FastAPI TestClient (synchronous). Run: python test_ctrl_routes.py
"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi.testclient import TestClient
import main


def fresh():
    """Reset state to design SS; return a new TestClient."""
    main.state = main.State()
    return TestClient(main.app)


# ===== GET routes =====

def test_get_all_has_both_sic():
    c = fresh()
    r = c.get("/api/ctrl")
    assert r.status_code == 200
    data = r.json()
    assert "SIC_321950" in data and "SIC_321951" in data, \
        f"expected both SIC keys, got: {list(data.keys())}"


def test_get_single_tag_schema():
    c = fresh()
    r = c.get("/api/ctrl/SIC_321951")
    assert r.status_code == 200
    pkt = r.json()
    for key in ("mode", "pv", "sp", "mv", "tuning", "limits", "status"):
        assert key in pkt, f"missing key {key!r}"
    assert pkt["mode"] == "MAN"


def test_get_unknown_tag_404():
    c = fresh()
    r = c.get("/api/ctrl/NOPE")
    assert r.status_code == 404


# ===== POST — mode transitions =====

def test_set_mode_man_to_auto():
    c = fresh()
    r = c.post("/api/ctrl/SIC_321951", json={"set_mode": "AUTO"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["mode"] == "AUTO"


def test_set_mode_unknown_tag_404():
    c = fresh()
    r = c.post("/api/ctrl/NOPE", json={"set_mode": "AUTO"})
    assert r.status_code == 404


def test_set_mode_invalid_value_422():
    c = fresh()
    r = c.post("/api/ctrl/SIC_321951", json={"set_mode": "BANANA"})
    assert r.status_code == 422, f"expected 422, got {r.status_code}"


def test_set_mode_oos():
    c = fresh()
    r = c.post("/api/ctrl/SIC_321951", json={"set_mode": "OOS"})
    assert r.status_code == 200
    assert r.json()["mode"] == "OOS"


# ===== POST — set_sp =====

def test_set_sp_in_man_returns_409():
    c = fresh()   # starts MAN
    r = c.post("/api/ctrl/SIC_321951", json={"set_sp": 85.0})
    assert r.status_code == 409, f"expected 409, got {r.status_code}"


def test_set_sp_in_auto():
    c = fresh()
    c.post("/api/ctrl/SIC_321951", json={"set_mode": "AUTO"})
    r = c.post("/api/ctrl/SIC_321951", json={"set_sp": 85.0})
    assert r.status_code == 200
    pkt = c.get("/api/ctrl/SIC_321951").json()
    assert abs(pkt["sp"] - 85.0) < 0.01, f"sp={pkt['sp']}, want 85.0"


def test_set_sp_clamped_to_sp_hi():
    c = fresh()
    c.post("/api/ctrl/SIC_321951", json={"set_mode": "AUTO"})
    c.post("/api/ctrl/SIC_321951", json={"set_sp": 999.0})   # above sp_hi=100
    pkt = c.get("/api/ctrl/SIC_321951").json()
    assert pkt["sp"] <= 100.0, f"sp={pkt['sp']} should clamp to <= 100"


# ===== POST — set_op =====

def test_set_op_in_auto_returns_409():
    c = fresh()
    c.post("/api/ctrl/SIC_321951", json={"set_mode": "AUTO"})
    r = c.post("/api/ctrl/SIC_321951", json={"set_op": 50.0})
    assert r.status_code == 409


def test_set_op_in_man():
    c = fresh()
    r = c.post("/api/ctrl/SIC_321951", json={"set_op": 55.0})
    assert r.status_code == 200
    pkt = c.get("/api/ctrl/SIC_321951").json()
    assert abs(pkt["mv"] - 55.0) < 0.01, f"mv={pkt['mv']}, want 55.0"


# ===== POST — set_bias =====

def test_set_bias_in_man_returns_409():
    c = fresh()
    r = c.post("/api/ctrl/SIC_321951", json={"set_bias": 2.5})
    assert r.status_code == 409


def test_set_bias_in_cas():
    c = fresh()
    c.post("/api/ctrl/SIC_321951", json={"set_mode": "CAS"})
    r = c.post("/api/ctrl/SIC_321951", json={"set_bias": 3.0})
    assert r.status_code == 200
    pkt = c.get("/api/ctrl/SIC_321951").json()
    assert abs(pkt["bias"] - 3.0) < 0.01, f"bias={pkt['bias']}, want 3.0"


# ===== POST — set_tuning (always legal) =====

def test_set_tuning_in_man():
    c = fresh()
    r = c.post("/api/ctrl/SIC_321951", json={"set_tuning": {"Kc": 3.0, "Ti": 12.0}})
    assert r.status_code == 200
    pkt = c.get("/api/ctrl/SIC_321951").json()
    assert abs(pkt["tuning"]["Kc"] - 3.0) < 1e-9
    assert abs(pkt["tuning"]["Ti"] - 12.0) < 1e-9


def test_set_tuning_in_auto():
    c = fresh()
    c.post("/api/ctrl/SIC_321951", json={"set_mode": "AUTO"})
    r = c.post("/api/ctrl/SIC_321951", json={"set_tuning": {"Kc": 1.5}})
    assert r.status_code == 200
    pkt = c.get("/api/ctrl/SIC_321951").json()
    assert abs(pkt["tuning"]["Kc"] - 1.5) < 1e-9


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
