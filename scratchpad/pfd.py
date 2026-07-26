"""PFD stream extractor: pull only the named stream columns out of the OEM PFD tables.

Usage:  python pfd.py 739 743 746 [--file <pfd.md>]

The source (`References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md`) is a
series of markdown tables, one per OEM sheet, each with a `| STREAM No. | Unnamed: 1 |
<stream> | <stream> | ... |` header.  Dumping a whole table blows the tool output limit
(37.7 KB), so this slices out only the requested columns and prints label -> value rows.

Prints every table that carries at least one requested stream, so a stream appearing in
two sheets (mass balance + utility balance) is reported from both.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(
    os.path.dirname(HERE), "References",
    "Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md",
)


def cells(line):
    """Split a markdown table row into stripped cells."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_rule(line):
    """True for the |:---|:---| separator row."""
    return set(line.strip()) <= set("|:- ")


args = [a for a in sys.argv[1:] if not a.startswith("--")]
path = DEFAULT
if "--file" in sys.argv:
    path = sys.argv[sys.argv.index("--file") + 1]
if not args:
    sys.exit("usage: python pfd.py <stream> [<stream> ...]")

want = [a.strip() for a in args]

with open(path, encoding="utf-8") as f:
    lines = f.read().splitlines()

section = ""
i = 0
hits = 0
while i < len(lines):
    line = lines[i]
    if line.startswith("## "):
        section = line[3:].strip()
        i += 1
        continue
    if line.startswith("|") and "STREAM No." in line:
        hdr = cells(line)
        cols = {w: hdr.index(w) for w in want if w in hdr}
        if not cols:
            i += 1
            continue
        hits += 1
        print(f"\n### {section}")
        print("stream:".ljust(26) + "".join(w.rjust(14) for w in cols))
        print("-" * (26 + 14 * len(cols)))
        j = i + 1
        while j < len(lines) and lines[j].startswith("|"):
            if is_rule(lines[j]):
                j += 1
                continue
            row = cells(lines[j])
            label = row[0]
            if label and label != "STREAM No.":
                vals = [row[k] if k < len(row) else "" for k in cols.values()]
                if any(v not in ("", "nan") for v in vals):
                    print(label[:25].ljust(26) + "".join(v.rjust(14) for v in vals))
            j += 1
        i = j
        continue
    i += 1

if not hits:
    sys.exit(f"no table carries any of: {', '.join(want)}")
