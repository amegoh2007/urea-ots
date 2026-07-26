import os, sys, re, json
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
BACKEND = os.path.join(ROOT, "backend")
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state if hasattr(main, "state") else main.STATE
pkt = None
for _ in range(3):
    pkt = main.step_sim(0.1)

def gp(o, path):
    cur = o
    for k in path.split("."):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return ("__MISS__", k)
    return cur

js = open(os.path.join(ROOT, "frontend", "overlays.js"), encoding="utf-8").read()

# split into screens
screens = {}
for m in re.finditer(r"'(screen-[\w\-]+)':\s*\[", js):
    screens[m.start()] = m.group(1)
order = sorted(screens)

def screen_of(pos):
    cur = None
    for st in order:
        if st <= pos: cur = screens[st]
    return cur

bad = []
allb = []
for m in re.finditer(r"bind:\s*'([^']+)'", js):
    b = m.group(1); sc = screen_of(m.start())
    # find tag on the same line
    ls = js.rfind("\n", 0, m.start()); le = js.find("\n", m.start())
    line = js[ls+1:le]
    tg = re.search(r"tag:\s*'([^']*)'", line)
    tag = tg.group(1) if tg else "?"
    allb.append((sc, tag, b))
    v = gp(pkt, b)
    if isinstance(v, tuple) and v and v[0] == "__MISS__":
        bad.append((sc, tag, b, v[1]))

modes = []
for m in re.finditer(r"mode:\s*'([^']+)'", js):
    b = m.group(1); sc = screen_of(m.start())
    ls = js.rfind("\n", 0, m.start()); le = js.find("\n", m.start())
    line = js[ls+1:le]
    tg = re.search(r"tag:\s*'([^']*)'", line)
    tag = tg.group(1) if tg else "?"
    v = gp(pkt, b)
    modes.append((sc, tag, b, v))

print("TOTAL BINDS:", len(allb))
print("BROKEN BINDS:", len(bad))
for x in bad: print("  BAD", x)
print()
print("MODE PATHS:", len(modes))
for x in modes:
    v = x[3]
    flag = "BAD" if (isinstance(v, tuple) and v and v[0]=="__MISS__") else "ok"
    print(" ", flag, x[0], x[1], x[2], "=", v)

# controller tags on overlays that open the generic faceplate but have no backend handler
print()
R323 = set(main.R323_CTRL_MODES)
tags = sorted(set(t for _,t,_ in allb if re.match(r"^[A-Z]{1,4}IC-3\d{5}$", t)))
T_BESPOKE = {'LIC-322501','HIC-322605','HIC-322604','FIC-329409','TIC-329005','PIC-329204','PIC-329205','PIC-329207','HIC-329601','LIC-329502','LIC-329503','LIC-329504'}
FE_R323 = set("""TIC-323007 PIC-329202 LIC-323501 LIC-323505 TIC-323012 PIC-329208 LIC-323507 FIC-324401 TIC-323013
PIC-323202 PIC-323203 LIC-323502 SIC-323901 SIC-323902 LIC-323503 FIC-323401 FIC-323402 FIC-328405 FIC-323418
LIC-328501 PIC-328202 TIC-328002 FIC-328404 FIC-329402 PIC-328203 FFIC-329401 FIC-329401 TIC-328008 TIC-328012
LIC-328503 LIC-328504 LIC-328505 FIC-328402 FIC-328406 PIC-322201 LIC-322502""".split())
print("FE R323 set size", len(FE_R323), "BE size", len(R323))
print("FE-only:", sorted(FE_R323 - set(t.replace('_','-') for t in R323)))
print("BE-only:", sorted(set(t.replace('_','-') for t in R323) - FE_R323))
print()
print("Overlay *IC tags with NO write path (silent no-op on SET):")
for t in tags:
    if t in T_BESPOKE or t in FE_R323: continue
    print("   ", t)
