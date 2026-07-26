import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
pkt = main.step_sim(0.1)

def flat(d, pre=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            p = pre + ("." if pre else "") + str(k)
            out[p] = v; out.update(flat(v, p))
    return out
F = flat(pkt)

ov = open(os.path.join(HERE, "..", "frontend", "overlays.js"), encoding="utf-8").read()
lines = ov.split("\n")
CTRL_RE = re.compile(r"[A-Z]IC-3\d{2}", re.I)

screen = "?"
rows = []
for i, ln in enumerate(lines, 1):
    ms = re.match(r"\s*OV\['([^']+)'\]", ln)
    if ms: screen = ms.group(1)
    if "t: 'ind'" not in ln and 't:"ind"' not in ln: continue
    idx = ln.find("//")
    tagm = re.search(r"tag:\s*'([^']*)'", ln)
    bm = re.search(r"bind:\s*'([^']+)'", ln)
    mm = re.search(r"mode:\s*'([^']+)'", ln)
    tag = tagm.group(1) if tagm else "?"
    rows.append((i, screen, tag, bm.group(1) if bm else None, mm.group(1) if mm else None))

print("=== controller-tagged indicators WITHOUT a mode: field (no A/M/E badge on HMI) ===")
n = 0
for i, sc, tag, b, m in rows:
    if CTRL_RE.search(tag) and b and not m:
        n += 1; print("  L%-5d %-8s %-14s bind=%s" % (i, sc, tag, b))
print("count:", n)

print("\n=== mode values emitted by backend for every mode: bind ===")
seen = {}
for i, sc, tag, b, m in rows:
    if m:
        v = F.get(m, "<<MISSING>>")
        seen.setdefault(str(v), []).append(tag)
LET = {'MAN':'M','AUTO':'A','CAS':'E','OOS':'O','M':'M','A':'A','E':'E','O':'O'}
for v, tags in sorted(seen.items()):
    print("  raw=%-6s -> letter=%-4s  n=%d  e.g. %s" % (v, LET.get(v, '<<BLANK>>'), len(tags), ", ".join(tags[:6])))

print("\n=== every ind with mode: whose seeded mode is NOT AUTO/CAS ===")
for i, sc, tag, b, m in rows:
    if m and str(F.get(m)) in ("MAN", "M", "OOS", "O"):
        print("  L%-5d %-8s %-14s mode=%s" % (i, sc, tag, F.get(m)))
