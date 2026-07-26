"""AUDIT B1 (part 2) -- ripple through LIVE state, and how DEEP it reaches.

The first pass perturbed module constants.  Two of those (STRIP_FEED207_KMOLH) turned out to be
frozen DEFAULTS that the live tick never reads, so a zero response there proved nothing about the
plant -- it proved my handle was wrong.  This pass perturbs the live state object mid-run, which is
the only way to ask the actual question: does a composition change in one stream reach the streams
below it, and keep going?

Depth is what matters.  A perturbation that moves the next unit and stops has NOT rippled; the
user's requirement is continuous propagation.  So the report groups responding telemetry by unit
and orders the units by their position in the train.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)

import main as M  # noqa: E402

DT = 0.25
SETTLE = 40
PROPAGATE = 240      # long enough for the 323/324/328 trains and the recycle tears


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


# ---- train order, upstream -> downstream.  A ripple must light these up in sequence. -----------
UNITS = [
    ("322 synthesis  (reactor/stripper/HPCC/scrubber)", ("322", "react", "strip", "hpcc", "scrub", "syn")),
    ("323 LP recirculation + evaporation feed",          ("323", "r323")),
    ("324 evaporation / prilling",                       ("324", "r324")),
    ("328 desorption / hydrolysis",                      ("328", "r328", "a328")),
    ("329 steam / utilities",                            ("329", "steam")),
]


def classify(key):
    low = key.lower()
    for name, pats in UNITS:
        if any(p in low for p in pats):
            return name
    return "other / unclassified"


for _ in range(SETTLE):
    pkt = M.step_sim(DT)
base = flatten(pkt)
print("settled.  telemetry leaves: %d\n" % len(base))

s = M.state
snapshot = dict(s.react_overflow_kmolh)

# Perturb the LIVE reactor overflow composition: +4 % NH3, water traded down to hold total moles.
# This is a pure COMPOSITION change -- the stripper sees the same molar throughput.
pert = dict(snapshot)
dn = snapshot["NH3"] * 0.04
pert["NH3"] = snapshot["NH3"] + dn
pert["H2O"] = snapshot["H2O"] - dn
s.react_overflow_kmolh = pert
print("perturbation: live reactor overflow NH3 %+.1f kmol/h, H2O %+.1f kmol/h (total moles held)"
      % (dn, -dn))

seen_step = {}
for i in range(1, PROPAGATE + 1):
    pkt = M.step_sim(DT)
    cur = flatten(pkt)
    for k, v0 in base.items():
        if k in seen_step or k not in cur:
            continue
        if abs(cur[k] - v0) / max(abs(v0), 1e-12) > 1e-9:
            seen_step[k] = i

groups = {}
for k, step in seen_step.items():
    g = classify(k)
    groups.setdefault(g, []).append((step, k))

print("\n%-52s %8s %8s %10s" % ("unit group", "moved", "of", "first tick"))
print("-" * 82)
for name, _ in UNITS + [("other / unclassified", ())]:
    tot = sum(1 for k in base if classify(k) == name)
    got = groups.get(name, [])
    first = min((st for st, _ in got), default=None)
    print("%-52s %8d %8d %10s"
          % (name, len(got), tot, ("%d" % first) if first else "-- NEVER"))

print("\ntotal responding: %d / %d  (%.1f %%)  after %d ticks (%.0f s)"
      % (len(seen_step), len(base), 100.0 * len(seen_step) / len(base), PROPAGATE, PROPAGATE * DT))

dead = sorted(name for name, _ in UNITS if name not in groups)
if dead:
    print("\nBROKEN RIPPLE -- these units never responded to an upstream composition change:")
    for d in dead:
        print("   *", d)
else:
    print("\nripple reached every unit group in the train.")

# a few representative deep-train keys, to show the change is real and not numerical dust
print("\nrepresentative downstream responses:")
cur = flatten(pkt)
picks = [k for k in sorted(seen_step) if any(t in k.lower() for t in ("324", "328", "steam"))][:12]
for k in picks:
    print("   %-58s %12.5g -> %12.5g" % (k[:58], base[k], cur[k]))
