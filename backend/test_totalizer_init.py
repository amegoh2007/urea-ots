"""FQI-321401 must start at zero on every program initialisation.

Plain-assert, run directly: python test_totalizer_init.py
"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main


def test_fresh_state_totalizer_is_zero():
    """State.__init__ is the only initialisation path; handle_cmd exposes no reset."""
    s = main.State()
    assert s.totalizer_t == 0.0, f"FQI-321401 seeded at {s.totalizer_t}, want 0.0"


def test_fresh_state_sim_clock_is_zero():
    s = main.State()
    assert s.sim_t == 0.0, f"plant clock seeded at {s.sim_t}, want 0.0"


def test_totalizer_tracks_the_flow_integral():
    """FQI-321401 is the running integral of delivered NH3, so it must only rise."""
    main.state = main.State()
    main.state.totalizer_t = 0.0
    prev = 0.0
    for _ in range(40):
        pkt = main.step_sim(0.25)
        now = pkt["totalizer"]
        assert now >= prev - 1e-9, f"totalizer went backwards: {prev} -> {now}"
        prev = now
    assert prev > 0.0, "no NH3 accumulated over 10 s of running pumps"


def test_totalizer_is_display_only():
    """The counter must not feed physics: zeroing it mid-run changes nothing else."""
    main.state = main.State()
    for _ in range(20):
        main.step_sim(0.25)
    before = main.step_sim(0.25)
    main.state.totalizer_t = 0.0
    after = main.step_sim(0.25)
    for key in ("PI_321201", "TI_top1", "FI_321401"):
        a, b = before.get(key), after.get(key)
        if a is None or b is None:
            continue
        assert abs(a - b) < abs(a) * 0.05 + 1.0, f"{key} moved on totalizer reset: {a} -> {b}"


def test_packet_carries_both_clocks():
    main.state = main.State()
    pkt = main.step_sim(0.5)
    assert "t" in pkt and "t_sim" in pkt, "packet must carry desktop and plant clocks"
    assert abs(pkt["t_sim"] - 0.5) < 1e-9, f"plant clock is {pkt['t_sim']}, want 0.5"
    assert pkt["t"] > 1.0e9, "desktop clock must stay an epoch timestamp"


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
