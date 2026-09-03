"""Guard test: every bound indicator and valve opening must stay trendable.

Parses the OV table in frontend/overlays.js and resolves each bind against a live packet.
A bind typo, a renamed packet key, or a subtree moved under STREAMS fails here instead of
silently drawing an empty pen in the trend window.

Plain-assert, run directly: python test_trend_coverage.py
"""
import os, re, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
from historian import flatten

FRONTEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

# Bound-tag count recorded when the trend system was built (2026-08-07). This is a FLOOR:
# binding more tags is progress and must not break the suite; losing one is a regression.
# 2026-09-02: PI-329206 was merged into PI-329207 (both LP-header transmitters now carry the
# 329207 tag), so one tag left the map by intent, not by a lost bind.  The floor is untouched
# because it is already red for unrelated reasons -- reconcile both together, not separately.
#
# 2026-09-02, UI-page migration (321-1 / 322-1 / 322-2 re-seeded from the slide deck): 212 -> 209.
# Fully accounted for, no bind was lost by accident:
#   - N/C 321P002A/B  -> FFIC-321404A/B   same binds (ratio.NC_A/B), the tag the slides print
#   - TI-322002/322017/329125 -> TT-*     same binds, the tag the slides print
#   - PI-329201, TI-321020, TI-322009     renamed onto PT-329201 / TT-321020 / TT-322009, all
#                                         three of which were already in the map -> net -3
#   - MASTER-SP gained (STEAM_SYSTEM.MASTER_SP_329207.sp)
#   - HIC-322203 dropped: the 322-1 drawing does not carry that tag.  The updated slide draws an
#     HS-322203 hand-switch button instead, so CO2_FEED.HIC_322203 is back in the map under the
#     HS-322203 tag (t:'btn' -> 210) and the forced-minimum faceplate is reachable from both that
#     button and PV-322203 (face:'hic2').  Nothing is lost; only the tag name changed.
BOUND_TAG_FLOOR = 217


def parse_ov():
    """Return [{screen, t, tag, bind}] for every element in the OV table."""
    src = open(os.path.join(FRONTEND, "overlays.js"), encoding="utf-8", errors="replace").read()
    start = src.index("const OV = {")
    body = src[start:src.index("\n  };", start)]
    screen_re = re.compile(r"^\s*'(screen-[^']+)':\s*\[")
    out, cur = [], None
    for line in body.splitlines():
        m = screen_re.match(line)
        if m:
            cur = m.group(1)
            continue
        if cur is None or "{" not in line:
            continue
        g = lambda k: (re.search(k + r":\s*'([^']*)'", line) or [None, None])[1]
        if not g("k") or not g("t"):
            continue
        out.append({"screen": cur, "t": g("t"), "tag": g("tag"), "bind": g("bind")})
    return out


def bind_map(entries):
    """tag -> bind, mirroring buildBindMap(): first bound occurrence across all screens."""
    m = {}
    for e in entries:
        if e["t"] in ("ind", "avalve", "btn") and e["bind"] and e["tag"] not in m:
            m[e["tag"]] = e["bind"]
    return m


ENTRIES = parse_ov()
BINDS = bind_map(ENTRIES)
PACKET = main.step_sim(0.1)
FLAT = flatten(PACKET)


def test_ov_table_parses():
    assert len(ENTRIES) > 300, f"only {len(ENTRIES)} overlay elements parsed — parser drifted?"


def test_every_bound_tag_resolves_in_the_packet():
    broken = {tag: path for tag, path in BINDS.items() if path not in FLAT}
    assert not broken, "bound tags that no longer resolve: " + repr(broken)


def test_bound_tag_count_has_not_regressed():
    assert len(BINDS) >= BOUND_TAG_FLOOR, \
        f"{len(BINDS)} bound tags, floor is {BOUND_TAG_FLOOR} — a bind was lost"


def test_no_bound_tag_hides_under_the_excluded_subtree():
    """If an instrument ever moves under STREAMS the historian would stop logging it."""
    under = {t: p for t, p in BINDS.items() if p.split(".")[0] == "STREAMS"}
    assert not under, "bound tags inside the excluded STREAMS subtree: " + repr(under)


def test_historian_universe_covers_every_bound_tag():
    missing = [t for t, p in BINDS.items() if p not in FLAT]
    assert not missing, f"{len(missing)} bound tags outside the historian universe: {missing[:10]}"


def test_valve_openings_are_trendable():
    """'avalve' elements carry the 0-100 % opening; they are half the requirement."""
    avalves = [e for e in ENTRIES if e["t"] == "avalve"]
    assert avalves, "no avalve elements found"
    bound = [e for e in avalves if e["bind"] or e["tag"] in BINDS]
    assert len(bound) >= 40, f"only {len(bound)} of {len(avalves)} valve openings are trendable"
    for e in bound:
        path = e["bind"] or BINDS[e["tag"]]
        assert path in FLAT, f"valve opening {e['tag']} does not resolve ({path})"


def test_boolean_assets_are_recorded_as_digital_pens():
    """Pumps and XVs bound to backend state must be loggable as 0/1."""
    wanted = ["XV_321901", "XV_322901", "pumpA.on", "pumpB.on"]
    missing = [p for p in wanted if p not in FLAT]
    assert not missing, f"digital paths absent from the historian universe: {missing}"
    for p in wanted:
        assert FLAT[p] in (0.0, 1.0), f"{p} is not a digital level: {FLAT[p]}"


def test_unbound_slots_are_the_known_white_frame_set():
    """White frames are unmodelled units, not trend defects. Flag any NEW ones."""
    unbound = sorted({e["tag"] for e in ENTRIES
                      if e["t"] in ("ind", "avalve") and not e["bind"] and e["tag"] not in BINDS})
    assert len(unbound) <= 31, \
        f"{len(unbound)} unbound indicator slots, was 31 — a bind was dropped: {unbound}"


def test_packet_exposes_both_clocks_for_the_trend_axis():
    assert "t_sim" in FLAT and "t" in FLAT, "trend needs plant and desktop clocks in the packet"


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
