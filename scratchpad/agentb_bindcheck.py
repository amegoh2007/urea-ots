import os, sys, json, re
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
            out[p] = v
            out.update(flat(v, p))
    return out

F = flat(pkt)
keys = set(F.keys())

ov = open(os.path.join(HERE, "..", "frontend", "overlays.js"), encoding="utf-8").read()
# strip // comments to avoid picking up commented binds
lines = ov.split("\n")

binds = []   # (lineno, screen, tag, bind)
screen = "?"
for i, ln in enumerate(lines, 1):
    ms = re.match(r"\s*OV\['([^']+)'\]", ln) or re.match(r'\s*OV\["([^"]+)"\]', ln)
    if ms: screen = ms.group(1)
    for m in re.finditer(r"bind:\s*'([^']+)'", ln):
        # ignore if inside a trailing comment
        idx = ln.find("//")
        if idx != -1 and m.start() > idx: continue
        tagm = re.search(r"tag:\s*'([^']*)'", ln)
        binds.append((i, screen, tagm.group(1) if tagm else "?", m.group(1)))
    for m in re.finditer(r"mode:\s*'([^']+)'", ln):
        idx = ln.find("//")
        if idx != -1 and m.start() > idx: continue
        tagm = re.search(r"tag:\s*'([^']*)'", ln)
        binds.append((i, screen, (tagm.group(1) if tagm else "?") + " [MODE]", m.group(1)))

bad = [b for b in binds if b[3] not in keys]
print("total binds checked:", len(binds))
print("UNRESOLVED:", len(bad))
for b in bad:
    print("  L%-5d %-8s %-22s -> %s" % b)

# focus: .pv / .vol_m3h binds
print("\n--- binds ending .vol_m3h or .pv on 321-1/323-1/328-1 ---")
for b in binds:
    if b[3].endswith(".vol_m3h") or b[3].endswith(".pv"):
        print("  L%-5d %-8s %-22s -> %-40s val=%r" % (b[0], b[1], b[2], b[3], F.get(b[3], "MISSING")))
