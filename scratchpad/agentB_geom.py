"""Agent B: geometry audit of the overlay layer -- off-stage elements and overlapping
   indicator boxes (an overlap means one live value is physically covered by another)."""
import os, re, json, itertools
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
js = open(os.path.join(ROOT, "frontend", "overlays.js"), encoding="utf-8").read()
STAGE_W, STAGE_H = 1366, 720
SZ = {"ind": (34, 18), "avalve": (34, 34), "pump": (54, 54), "xv": (34, 34)}

screens, order = {}, []
for m in re.finditer(r"'(screen-[\w\-]+)':\s*\[", js):
    screens[m.start()] = m.group(1); order.append(m.start())
order.sort()
def screen_of(p):
    cur = None
    for st in order:
        if st <= p: cur = screens[st]
    return cur

rows = {}
for m in re.finditer(r"\{\s*k:\s*'([^']+)'[^\n]*", js):
    line = m.group(0)
    sc = screen_of(m.start())
    t = re.search(r"t:\s*'(\w+)'", line)
    x = re.search(r"x:\s*(-?\d+)", line); y = re.search(r"y:\s*(-?\d+)", line)
    w = re.search(r"w:\s*(\d+)", line);   h = re.search(r"h:\s*(\d+)", line)
    tag = re.search(r"tag:\s*'([^']*)'", line)
    if not (t and x and y): continue
    typ = t.group(1)
    dw, dh = SZ.get(typ, (int(w.group(1)) if w else 120, int(h.group(1)) if h else 16))
    if w: dw = int(w.group(1))
    if h: dh = int(h.group(1))
    rows.setdefault(sc, []).append((m.group(1), tag.group(1) if tag else "?", typ,
                                    int(x.group(1)), int(y.group(1)), dw, dh))

for sc in sorted(rows):
    off = [r for r in rows[sc] if r[3] < 0 or r[4] < 0 or r[3] + r[5] > STAGE_W or r[4] + r[6] > STAGE_H]
    boxes = [r for r in rows[sc] if r[2] in ("ind", "avalve")]
    ov = []
    for a, b in itertools.combinations(boxes, 2):
        ax, ay, aw, ah = a[3], a[4], a[5], a[6]
        bx, by, bw, bh = b[3], b[4], b[5], b[6]
        ix = min(ax+aw, bx+bw) - max(ax, bx)
        iy = min(ay+ah, by+bh) - max(ay, by)
        if ix > 0 and iy > 0:
            ov.append((a[1], b[1], ix, iy, (ax,ay), (bx,by)))
    if off or ov:
        print(f"== {sc}  ({len(rows[sc])} elements)")
        for r in off: print("   OFF-STAGE", r)
        for o in ov:  print(f"   OVERLAP  {o[0]} @{o[4]}  vs  {o[1]} @{o[5]}   ({o[2]}x{o[3]} px)")
print("\nscreens:", {k: len(v) for k, v in sorted(rows.items())})
