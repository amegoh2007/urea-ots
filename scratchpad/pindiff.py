"""Pin gate step 2: leaf-wise repr() diff of a regress.py dump vs golden_pin.json.

Usage:  python pindiff.py <pin_now.json> [golden_pin.json]

Leaves are counted list-aware: a list element is a leaf, not a container.  The mandated
golden count is  leaves: 25  keys: 15  (13 scalars + 3 REACT_MASS_DES + 9 REACT_TEAR_DES).
A dict-only recursion under-counts to 23 and reads like drift when it is not.

Compares repr() so the check is bit-exact, not tolerance-based.  Any non-zero diff blocks
the commit.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def leaves(node, path=""):
    """Yield (dotted_path, value) for every scalar leaf. List elements are leaves."""
    if isinstance(node, dict):
        for k in node:
            yield from leaves(node[k], f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from leaves(v, f"{path}[{i}]")
    else:
        yield path, node


now_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "pin_out.json")
gold_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "golden_pin.json")

with open(now_path, encoding="utf-8") as f:
    now = json.load(f)
with open(gold_path, encoding="utf-8") as f:
    gold = json.load(f)

now_leaves = dict(leaves(now))
gold_leaves = dict(leaves(gold))

diffs = []
for k in sorted(set(now_leaves) | set(gold_leaves)):
    a, b = gold_leaves.get(k, "<MISSING>"), now_leaves.get(k, "<MISSING>")
    if repr(a) != repr(b):
        diffs.append((k, a, b))

print(f"leaves: {len(now_leaves)}  keys: {len(now)}  diffs: {len(diffs)}")
for k, a, b in diffs:
    print(f"  {k}\n    golden: {a!r}\n    now   : {b!r}")
sys.exit(1 if diffs else 0)
