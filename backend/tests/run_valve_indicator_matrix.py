r"""run_valve_indicator_matrix.py  --  FULL VALVE x INDICATOR SENSITIVITY AUDIT

For EVERY operator-manipulable valve in the OTS, force it to a LOW and a HIGH opening,
settle to steady state, and diff EVERY numeric indicator leaf in the step_sim packet
(packet is flattened recursively -> ~694 leaves).  Produces:

  1. per-valve RESPONDS list  (indicators that move, signed, sorted by |rel delta|)
  2. STALL CHECK              (physics-expected couplings that DO NOT move -> candidate dead inputs)
  3. DEAD-INDICATOR sweep     (leaves no valve moves at all)

Forcing mirrors run_full_audit.py: HIC valves set the attr each tick; AUTO loops
(LIC/FIC/TIC/PIC) are pinned MAN + op each tick; steam valves set on s.steam.
Tank level pinned (continuous makeup) so the cavitation trip stays dormant.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import main

DT          = 0.1
SETTLE_MIN  = float(os.environ.get("SETTLE_MIN", "20"))
SETTLE_TICK = int(SETTLE_MIN * 60.0 / DT)
REL_TOL     = 1e-4          # |hi-lo| / (|base|+eps) below this = FLAT
ABS_EPS     = 1e-9


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        elif isinstance(v, bool):
            out[key] = float(v)
        elif isinstance(v, (int, float)):
            out[key] = float(v)
    return out


def settle(pre_fn=None, tick_fn=None):
    main.state = main.State()
    s = main.state
    tank_pin = s.tank_level_frac
    if pre_fn:
        pre_fn(s)
    pkt = None
    for _ in range(SETTLE_TICK):
        pkt = main.step_sim(DT)
        s.tank_level_frac = tank_pin
        if tick_fn:
            tick_fn(s)
    return flatten(pkt)


# ---- forcing helpers for the AUTO loops (MAN + pin op every tick) ----
def _man(dictname, op):
    def pre(s):
        getattr(s, dictname)["mode"] = "MAN"
        getattr(s, dictname)["op"]   = op
    def tick(s):
        getattr(s, dictname)["op"]   = op
    return pre, tick


def _attr(name, val):
    def tick(s):
        setattr(s, name, val)
    return None, tick


def _steam(name, val):
    def tick(s):
        setattr(s.steam, name, val)
    return None, tick


# ---- VALVE REGISTRY:  (tag, attr-desc, baseline, lo, hi, kind, key) ----
#   kind/key tell the forcing builder how to drive it.
VALVES = [
    # tag,             baseline, lo,   hi,   builder
    ("HV-322605 reactor-overflow", 60.0, 30.0, 90.0, lambda v: _attr("HIC_322605", v)),
    ("HV-322604 scrubber off-gas vent", 50.0, 25.0, 80.0, lambda v: _attr("HIC_322604", v)),
    ("HV-322602 ejector spindle",  74.0, 55.0, 95.0, lambda v: _attr("HIC_322602", v)),
    ("PV-322203 CO2 vent (HIC min)", 0.0, 0.0, 30.0, lambda v: _attr("HIC_322203", v)),
    ("PV-322203 CO2 (PIC op)",     0.0, 0.0, 40.0, lambda v: _man("PIC_322203", v)),
    ("LV-322501 stripper drain",   82.0, 50.0, 100.0, lambda v: _man("LIC_322501", v)),
    ("FV-329409 CCW circ flow",    60.0, 30.0, 90.0, lambda v: _man("FIC_329409", v)),
    ("TV-329005 CCW supply-T",     50.0, 20.0, 80.0, lambda v: _man("TIC_329005", v)),
    ("MP steam supply valve",      50.0, 30.0, 70.0, lambda v: _steam("valve_supply_pct", v)),
    ("MP->LP letdown valve",       50.0, 30.0, 70.0, lambda v: _steam("valve_letdown_pct", v)),
]

# ---- STALL-CHECK assertions: (valve_tag_substr, indicator_key, why) ----
#   Physics says this indicator SHOULD respond to this valve.  Flat => candidate stall.
STALL_CHECK = [
    ("HV-322604", "SCRUB_322E003.TT_322011", "more vent -> more NH3/inert purge -> off-gas top T should shift"),
    ("HV-322604", "SCRUB_322E003.off_th",    "vent flow sets off-gas mass leaving 322E003"),
    ("HV-322605", "REACT_322R001.LT_322504",  "overflow valve sets reactor level"),
    ("LV-322501", "STRIP_322E001.LI_322501",  "drain valve sets stripper sump level"),
    ("FV-329409", "SCRUB_322E003.ccw.TT_329125", "CCW flow sets shell-return T"),
    ("FV-329409", "SCRUB_322E003.TT_322002",  "CCW flow sets overflow (carbamate) T via e-NTU"),
    ("TV-329005", "SCRUB_322E003.ccw.TT_329125", "CCW supply-T branch shifts shell-return T"),
    ("HV-322602", "EJ_322F001.suction_kgh",   "spindle sets ejector entrainment / suction"),
    ("MP steam",  "STRIP_322E001.TT_322004",  "MP steam T sets stripper bottom T"),
    ("MP->LP",    "HPCC_322E002.TT_322010",   "LP header feeds HPCC shell sat-T -> product T"),
]


def signed(base, lo, hi):
    d = hi - lo
    rel = abs(d) / (abs(base) + ABS_EPS)
    return d, rel


def main_run():
    print("#" * 110)
    print(f"#  FULL VALVE x INDICATOR SENSITIVITY MATRIX   (settle {SETTLE_MIN:.0f} min/pt, dt={DT}s, "
          f"rel_tol={REL_TOL})")
    print("#" * 110)

    print("\n[*] baseline settle ...")
    base = settle()
    keys = sorted(base.keys())
    print(f"    {len(keys)} indicator leaves captured.")

    moved_by_any = set()
    per_valve = {}   # tag -> {key: (delta, rel)}

    for tag, bl, lo, hi, build in VALVES:
        pre_lo, tick_lo = build(lo)
        pre_hi, tick_hi = build(hi)
        flo = settle(pre_lo, tick_lo)
        fhi = settle(pre_hi, tick_hi)
        resp = {}
        for k in keys:
            if k not in flo or k not in fhi:
                continue
            d, rel = signed(base.get(k, flo[k]), flo[k], fhi[k])
            if rel > REL_TOL and abs(d) > ABS_EPS:
                resp[k] = (d, rel)
                moved_by_any.add(k)
        per_valve[tag] = resp
        print(f"\n{'='*110}\n  {tag}   [{lo:g} -> {hi:g}]   moves {len(resp)} indicators")
        print(f"{'='*110}")
        top = sorted(resp.items(), key=lambda kv: -kv[1][1])[:30]
        for k, (d, rel) in top:
            arrow = "UP " if d > 0 else "DN "
            print(f"   {arrow}{k:42s}  d={d:+12.4g}  rel={rel:9.3g}  ({base.get(k, float('nan')):.4g})")
        if not resp:
            print("   (none — valve moves NO indicator)")

    # ---- STALL CHECK ----
    print("\n\n" + "#" * 110)
    print("#  STALL CHECK  --  physics-expected couplings (FLAT = candidate dead input)")
    print("#" * 110)
    for vsub, key, why in STALL_CHECK:
        tag = next((t for t in per_valve if vsub in t), None)
        if tag is None:
            print(f"   [SKIP] no valve match '{vsub}'")
            continue
        hit = per_valve[tag].get(key)
        if hit:
            d, rel = hit
            print(f"   [OK ] {vsub:10s} -> {key:38s} d={d:+.4g} rel={rel:.3g}")
        else:
            present = key in base
            note = "" if present else "  <key-missing>"
            print(f"   [STALL] {vsub:10s} -> {key:38s} FLAT{note}   ({why})")

    # ---- DEAD INDICATORS ----
    dead = [k for k in keys if k not in moved_by_any]
    print("\n\n" + "#" * 110)
    print(f"#  DEAD INDICATORS  --  {len(dead)}/{len(keys)} leaves moved by NO valve "
          f"(constants/design-pins/display expected)")
    print("#" * 110)
    for k in dead:
        print(f"   {k:46s}  = {base[k]:.5g}")


if __name__ == "__main__":
    main_run()
