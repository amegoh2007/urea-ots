"""AUDIT B1 -- the ripple effect, measured rather than read.

Claim under test: a change in the composition or properties of ANY stream must reach every
downstream stream, and keep propagating transitively.

Reading the code cannot settle this.  A term can be present, correctly written, and still be
DEAD -- eta_P was exactly that for years: computed on every tick from an argument every call site
passed as a frozen constant.  So this audit perturbs a real upstream handle, steps the plant, and
records which telemetry numbers actually moved.  A downstream number that does not move when its
upstream does is a broken ripple link, regardless of how the code reads.

Method: flatten the telemetry packet to scalar leaves, take a settled baseline, then for each
perturbation re-settle from a fresh import and diff.  Anything whose relative change is below
FLOOR is reported as NOT propagated.
"""
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)

FLOOR = 1e-9          # relative move below this counts as "did not respond"
SETTLE_STEPS = 60     # ticks to let the perturbation propagate through the recycle tears
DT = 0.25


def flatten(obj, prefix="", out=None):
    if out is None:
        out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            flatten(v, f"{prefix}.{k}" if prefix else str(k), out)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            flatten(v, f"{prefix}[{i}]", out)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out[prefix] = float(obj)
    return out


def run(mutate=None, steps=SETTLE_STEPS):
    """Fresh import, optional mutation of a module-level handle, then settle."""
    cache = os.path.join(BACKEND, ".boot_pin_cache.json")
    for mod in [m for m in list(sys.modules) if m in ("main", "reactor")]:
        del sys.modules[mod]
    import main
    importlib.reload(main) if "main" in sys.modules else None
    if mutate:
        mutate(main)
    pkt = {}
    for _ in range(steps):
        pkt = main.step_sim(DT)
    return flatten(pkt), main


base, mainmod = run()
print("baseline telemetry leaves: %d" % len(base))

# --------------------------------------------------------------------------------------------
# Perturbations.  Each one changes a COMPOSITION or a PROPERTY at a different point in the train,
# never a flow rate alone -- flow-only ripple was already covered by earlier load work.
# --------------------------------------------------------------------------------------------
PERTURBATIONS = {
    "CO2 feed purity (inerts +50%)":
        lambda M: M.CO2_FEED_MOLFRAC.update(
            {"N2": M.CO2_FEED_MOLFRAC["N2"] * 1.5, "O2": M.CO2_FEED_MOLFRAC["O2"] * 1.5,
             "CO2": M.CO2_FEED_MOLFRAC["CO2"] - 0.5 * (M.CO2_FEED_MOLFRAC["N2"]
                                                       + M.CO2_FEED_MOLFRAC["O2"])}),
    "reactor overflow composition (NH3 +3%)":
        lambda M: M.STRIP_FEED207_KMOLH.update({"NH3": M.STRIP_FEED207_KMOLH["NH3"] * 1.03}),
    "reactor overflow water (H2O +5%)":
        lambda M: M.STRIP_FEED207_KMOLH.update({"H2O": M.STRIP_FEED207_KMOLH["H2O"] * 1.05}),
    "MP steam header pressure (+4%)":
        lambda M: setattr(M.state.steam, "P_MP", M.state.steam.P_MP * 1.04),
    "bottom-solution density constant (+3%)":
        lambda M: setattr(M, "STRIP_RHO_BOTTOM", M.STRIP_RHO_BOTTOM * 1.03),
    "urea-solution cp constant (+5%)":
        lambda M: setattr(M, "R323_CP_SOLN", M.R323_CP_SOLN * 1.05),
    "328 desorber cp constant (+5%)":
        lambda M: setattr(M, "R328_CP", M.R328_CP * 1.05),
}

report = {}
for name, mut in PERTURBATIONS.items():
    pert, _ = run(mut)
    moved, still, missing = [], [], []
    for k, v0 in base.items():
        if k not in pert:
            missing.append(k)
            continue
        v1 = pert[k]
        denom = max(abs(v0), 1e-12)
        rel = abs(v1 - v0) / denom
        (moved if rel > FLOOR else still).append((k, rel))
    report[name] = {"moved": len(moved), "still": len(still),
                    "pct": 100.0 * len(moved) / max(len(base), 1),
                    "still_keys": sorted(k for k, _ in still)}
    print("\n%-42s  moved %4d / %4d  (%5.1f %%)"
          % (name, len(moved), len(base), report[name]["pct"]))

with open(os.path.join(HERE, "audit_ripple_out.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)
print("\nwrote audit_ripple_out.json")
