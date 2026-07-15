"""Static-indicator audit: parse overlays.js, list every tagged element and whether
it carries a live `bind` path into the WebSocket packet.  An element with no bind
renders a dash forever -> static indicator (audit item 1).
Usage: python audit_indicators.py [--press]
"""
import os
import re
import sys
import collections

OVL = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "frontend", "overlays.js"))

SCREEN_RE = re.compile(r"^\s{0,6}([A-Za-z0-9_]+)\s*:\s*\[")
TAG_RE = re.compile(r"tag:\s*'([^']+)'")
T_RE = re.compile(r"\bt:\s*'([^']+)'")
BIND_RE = re.compile(r"bind:\s*'([^']+)'")
PRESS_RE = re.compile(r"^(PT|PI|PIC|PIT|PV|PDT|PDI)[-_]")


def rows():
    src = open(OVL, encoding="utf-8").read()
    out, screen = [], None
    for i, line in enumerate(src.split("\n"), 1):
        ms = SCREEN_RE.search(line)
        if ms and "tag:" not in line:
            screen = ms.group(1)
        if "tag:" in line:
            tag = TAG_RE.search(line)
            t = T_RE.search(line)
            b = BIND_RE.search(line)
            out.append((i, screen, tag.group(1) if tag else "?",
                        t.group(1) if t else "?", b.group(1) if b else None))
    return out


def main():
    rs = rows()
    nb = [r for r in rs if r[4] is None]
    print("tagged entries: %d   unbound: %d" % (len(rs), len(nb)))
    print("unbound by widget type: %s" % dict(collections.Counter(r[3] for r in nb)))
    print()
    print("--- unbound t='ind' (static indicators) ---")
    for i, s, tag, t, b in nb:
        if t == "ind":
            print("%5d  %-16s %s" % (i, s, tag))
    if "--press" in sys.argv:
        print()
        print("--- ALL pressure tags (bound + unbound) ---")
        for i, s, tag, t, b in rs:
            if PRESS_RE.match(tag):
                print("%5d  %-16s %-14s t=%-7s bind=%s" % (i, s, tag, t, b))


if __name__ == "__main__":
    main()
