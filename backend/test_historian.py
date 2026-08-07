"""Unit tests for historian.py — the background trend recorder.

Plain-assert, run directly: python test_historian.py
"""
import os, sys, traceback
from math import isnan
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from historian import Historian, Ring, flatten, PATH_EXCLUDE


def build(period=1.0, cap=10):
    return Historian(rings=(("only", period, cap),))


# ===== flatten =====

def test_flatten_walks_nested_paths():
    flat = flatten({"a": 1, "b": {"c": 2.5, "d": {"e": 3}}})
    assert flat == {"a": 1.0, "b.c": 2.5, "b.d.e": 3.0}, flat


def test_flatten_maps_booleans_to_digital_levels():
    """XV/pump states trend as 0/1 step pens."""
    flat = flatten({"XV_321901": True, "XV_322901": False})
    assert flat == {"XV_321901": 1.0, "XV_322901": 0.0}, flat


def test_flatten_skips_excluded_subtree_whole():
    """STREAMS is 2346 of 3213 numeric leaves and holds composition tables, not instruments."""
    assert "STREAMS" in PATH_EXCLUDE
    flat = flatten({"STREAMS": {"NH3_FEED": {"T_C": 40.0}}, "TI_top1": 25.0})
    assert flat == {"TI_top1": 25.0}, flat


def test_flatten_ignores_strings():
    flat = flatten({"mode": "AUTO", "pv": 12.0})
    assert flat == {"pv": 12.0}, flat


# ===== sampling cadence =====

def test_sampling_is_driven_by_plant_time():
    h = build(period=1.0, cap=10)
    for n in range(10):                       # 10 sub-steps of 0.25 plant-s = 2.5 s
        h.maybe_sample({"x": float(n)}, t_sim=0.25 * (n + 1), t_wall=1000.0 + n)
    ring = h.rings[0]
    assert ring.count == 3, f"want a sample per plant-second, got {ring.count}"


def test_first_sample_is_taken_immediately():
    h = build()
    assert h.maybe_sample({"x": 1.0}, 0.1, 1000.0) is True
    assert h.maybe_sample({"x": 2.0}, 0.2, 1000.1) is False, "must wait a full period"


# ===== ring wrap =====

def test_ring_wraps_and_keeps_the_newest_samples():
    h = build(period=1.0, cap=5)
    for n in range(12):
        h.maybe_sample({"x": float(n)}, float(n), 1000.0 + n)
    ring = h.rings[0]
    assert ring.count == 5, ring.count
    got = [ring.cols["x"][i] for i in ring.order()]
    assert got == [7.0, 8.0, 9.0, 10.0, 11.0], got


def test_order_is_chronological_before_and_after_wrap():
    h = build(period=1.0, cap=4)
    for n in range(3):
        h.maybe_sample({"x": float(n)}, float(n), 1000.0 + n)
    assert [h.rings[0].t_sim[i] for i in h.rings[0].order()] == [0.0, 1.0, 2.0]
    for n in range(3, 9):
        h.maybe_sample({"x": float(n)}, float(n), 1000.0 + n)
    ts = [h.rings[0].t_sim[i] for i in h.rings[0].order()]
    assert ts == sorted(ts), ts


# ===== late paths =====

def test_late_path_is_nan_padded_not_zero_filled():
    """A tag bound mid-run must read 'no data' for the past, not a misleading zero."""
    h = build(period=1.0, cap=10)
    for n in range(3):
        h.maybe_sample({"x": float(n)}, float(n), 1000.0 + n)
    h.maybe_sample({"x": 3.0, "late": 9.0}, 3.0, 1003.0)
    col = h.rings[0].cols["late"]
    assert isnan(col[0]) and isnan(col[1]) and isnan(col[2]), "history before the path existed must be NaN"
    assert col[3] == 9.0


def test_path_that_disappears_is_blanked_not_stale():
    h = build(period=1.0, cap=10)
    h.maybe_sample({"x": 1.0, "gone": 5.0}, 0.0, 1000.0)
    h.maybe_sample({"x": 2.0}, 1.0, 1001.0)
    assert isnan(h.rings[0].cols["gone"][1]), "vanished path must blank, not hold a stale value"


# ===== ring selection =====

def test_span_picks_the_finest_ring_that_covers_it():
    h = Historian(rings=(("fast", 1.0, 3600), ("slow", 10.0, 2880)))
    assert h.pick_ring(60).name == "fast"
    assert h.pick_ring(3600).name == "fast"
    assert h.pick_ring(7200).name == "slow"
    assert h.pick_ring(28800).name == "slow"
    assert h.pick_ring(999999).name == "slow", "over-long span falls back to the coarsest ring"


# ===== query / decimation =====

def test_query_preserves_spikes_through_decimation():
    """A min/max envelope is the point: a transient between output points must survive."""
    h = build(period=1.0, cap=200)
    for n in range(100):
        v = 500.0 if n == 47 else 10.0
        h.maybe_sample({"x": v}, float(n), 1000.0 + n)
    q = h.query(["x"], span_s=200.0, max_points=10)
    assert max(v for v in q["series"]["x"] if v is not None) == 500.0, "spike lost in decimation"
    assert len(q["series"]["x"]) <= 10, len(q["series"]["x"])


def test_query_keeps_one_shared_time_axis_for_every_series():
    h = build(period=1.0, cap=100)
    for n in range(50):
        h.maybe_sample({"a": float(n), "b": float(50 - n)}, float(n), 1000.0 + n)
    q = h.query(["a", "b"], span_s=60.0, max_points=12)
    n = len(q["t_sim"])
    assert len(q["t_wall"]) == n
    for path, vals in q["series"].items():
        assert len(vals) == n, f"{path} has {len(vals)} values against {n} timestamps"


def test_query_honours_the_span_window():
    h = build(period=1.0, cap=100)
    for n in range(60):
        h.maybe_sample({"x": float(n)}, float(n), 1000.0 + n)
    q = h.query(["x"], span_s=10.0, max_points=400)
    assert min(q["t_sim"]) >= 49.0, f"returned data older than the span: {min(q['t_sim'])}"


def test_query_can_end_at_an_older_instant():
    """A scrolled-back trend asks for a window that closes in the past."""
    h = build(period=1.0, cap=200)
    for n in range(100):
        h.maybe_sample({"x": float(n)}, float(n), 1000.0 + n)
    q = h.query(["x"], span_s=10.0, max_points=400, end_sim=50.0)
    assert max(q["t_sim"]) <= 50.0, f"window leaked past its end: {max(q['t_sim'])}"
    assert min(q["t_sim"]) >= 40.0, f"window reached past its start: {min(q['t_sim'])}"
    assert max(q["series"]["x"]) <= 50.0


def test_scrolled_window_does_not_return_everything_up_to_now():
    """Without an upper bound the ring would hand back the whole tail."""
    h = build(period=1.0, cap=200)
    for n in range(60):
        h.maybe_sample({"x": float(n)}, float(n), 1000.0 + n)
    near = h.query(["x"], span_s=5.0, max_points=400, end_sim=20.0)
    assert len(near["t_sim"]) <= 12, f"got {len(near['t_sim'])} points for a 5 s window"


def test_old_window_with_a_short_span_falls_to_the_ring_that_still_holds_it():
    """A 5-minute span read from 4 hours ago is past the fast ring's retention."""
    h = Historian()
    assert h.pick_ring(300).name == "fast"
    h_now, span, age = 14400.0, 300.0, 14400.0
    assert h.pick_ring(span + age).name == "slow", "ring choice must account for how far back"


def test_default_end_is_still_the_newest_sample():
    h = build(period=1.0, cap=50)
    for n in range(30):
        h.maybe_sample({"x": float(n)}, float(n), 1000.0 + n)
    a = h.query(["x"], span_s=10.0, max_points=400)
    b = h.query(["x"], span_s=10.0, max_points=400, end_sim=29.0)
    assert a["t_sim"] == b["t_sim"], "omitting end must equal ending at the newest sample"


def test_query_reports_unknown_paths_instead_of_failing():
    h = build()
    h.maybe_sample({"x": 1.0}, 0.0, 1000.0)
    q = h.query(["x", "does.not.exist"], span_s=60.0)
    assert q["missing"] == ["does.not.exist"], q["missing"]
    assert "x" in q["series"]


def test_query_on_empty_historian_is_safe():
    q = build().query(["x"], span_s=60.0)
    assert q["t_sim"] == [] and q["series"] == {}, q


def test_query_flags_truncation_when_history_is_shorter_than_the_span():
    h = build(period=1.0, cap=100)
    for n in range(20):
        h.maybe_sample({"x": float(n)}, float(n), 1000.0 + n)
    assert h.query(["x"], span_s=3600.0)["truncated"] is True
    assert h.query(["x"], span_s=5.0)["truncated"] is False


def test_all_nan_bucket_returns_nulls_not_zeros():
    h = build(period=1.0, cap=10)
    h.maybe_sample({"x": 1.0}, 0.0, 1000.0)
    h.maybe_sample({"x": 2.0, "late": 7.0}, 1.0, 1001.0)
    q = h.query(["late"], span_s=60.0, max_points=400)
    assert q["series"]["late"][0] is None, "padding must serialise as null, not 0"


# ===== memory ceiling =====

def test_memory_is_linear_in_path_count():
    """The cost invariant, not a fixed total: columnar array('f') is 4 B per path per sample
    plus 16 B per sample for the two shared timestamp arrays. This holds as the packet grows
    (the plant model added ~250 paths after the historian shipped, 914 -> ~1167), so the guard
    tests the per-path law rather than an absolute that packet growth silently breaches."""
    h = Historian()
    h.maybe_sample({f"p{i}": float(i) for i in range(1000)}, 0.0, 1000.0)
    stats = h.stats()
    for r in h.rings:
        expected = 4 * r.cap * 1000 + 16 * r.cap
        assert stats[r.name]["bytes"] == expected, \
            f"{r.name}: {stats[r.name]['bytes']} B != {expected} B (columnar formula)"
    total = sum(s["bytes"] for s in stats.values())
    per_path = total / 1000.0
    # 4 B/sample * (3600 + 2880) depths = 25 920 B per path, plus timestamp overhead amortised.
    assert 25000 <= per_path <= 27000, f"{per_path:.0f} B/path — columnar layout drifted"


def test_realistic_packet_stays_within_a_sane_bound():
    """Even well above today's ~1167 paths the archive must stay small (it is RAM, all rings)."""
    h = Historian()
    h.maybe_sample({f"p{i}": float(i) for i in range(1500)}, 0.0, 1000.0)
    total = sum(r["bytes"] for r in h.stats().values())
    assert total < 45e6, f"historian would use {total/1e6:.1f} MB at 1500 paths"
    assert total > 15e6, f"only {total/1e6:.1f} MB allocated — rings look under-sized"


def test_stats_report_every_ring():
    h = Historian()
    h.maybe_sample({"x": 1.0}, 0.0, 1000.0)
    assert set(h.stats()) == {"fast", "slow"}
    assert h.stats()["fast"]["period"] == 1.0
    assert h.stats()["slow"]["capacity"] == 2880


def test_paths_lists_what_is_recorded():
    h = Historian()
    h.maybe_sample({"a": 1.0, "b": {"c": 2.0}}, 0.0, 1000.0)
    assert set(h.paths()) == {"a", "b.c"}


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print("PASS", name)
        except Exception:
            failed += 1
            print("FAIL", name)
            traceback.print_exc()
    print("---", "all passed" if not failed else f"{failed} failed")
    sys.exit(1 if failed else 0)
