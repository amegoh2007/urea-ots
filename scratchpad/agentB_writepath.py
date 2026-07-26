"""Agent B probe: does the generic faceplate SET actually reach the engine for every
   *IC-3xxxx overlay tag?  Replays exactly what frontend/app.js apply() would send."""
import os, sys, re, json, copy
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
BACKEND = os.path.join(ROOT, "backend")
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state
main.step_sim(0.1)

T = {'LIC-322501':'lic_set','HIC-322605':'hic605_set','HIC-322604':'hic604_set','FIC-329409':'fic_set',
     'TIC-329005':'tic_set','PIC-329204':'pic329204_set','PIC-329205':'pic329205_set','PIC-329207':'pic329207_set',
     'HIC-329601':'steam_hpvent_set','LIC-329502':'lic329502_set','LIC-329503':'lic329503_set','LIC-329504':'lic329504_set'}
R323 = set("""TIC-323007 PIC-329202 LIC-323501 LIC-323505 TIC-323012 PIC-329208 LIC-323507 FIC-324401 TIC-323013
PIC-323202 PIC-323203 LIC-323502 SIC-323901 SIC-323902 LIC-323503 FIC-323401 FIC-323402 FIC-328405 FIC-323418
LIC-328501 PIC-328202 TIC-328002 FIC-328404 FIC-329402 PIC-328203 FFIC-329401 FIC-329401 TIC-328008 TIC-328012
LIC-328503 LIC-328504 LIC-328505 FIC-328402 FIC-328406 PIC-322201 LIC-322502""".split())

js = open(os.path.join(ROOT, "frontend", "overlays.js"), encoding="utf-8").read()
# only tags that have NO face: on their overlay row -> they fall through to the generic ctl faceplate
rows = []
for line in js.splitlines():
    m = re.search(r"tag:\s*'([A-Z]{1,4}IC-3\d{5}[A-Z]?)'", line)
    if not m: continue
    tag = m.group(1)
    has_face = "face:" in line or "fp:" in line
    b = re.search(r"bind:\s*'([^']+)'", line)
    rows.append((tag, has_face, b.group(1) if b else None))

seen = set()
print(f"{'TAG':<14}{'route':<16}{'MODE-write':<12}{'SP/OP-write':<12} bind")
for tag, has_face, bind in rows:
    if tag in seen: continue
    seen.add(tag)
    if has_face:
        print(f"{tag:<14}{'dedicated fp':<16}{'-':<12}{'-':<12} {bind}")
        continue
    typ = T.get(tag) or ('r323_ctrl_set' if tag in R323 else 'controller_set')
    # snapshot the loop block via the packet
    def blk():
        pkt = main.step_sim(0.1)
        if not bind or not bind.endswith('.pv'): return None
        cur = pkt
        for k in bind[:-3].split('.'):
            cur = cur.get(k) if isinstance(cur, dict) else None
            if cur is None: return None
        return copy.deepcopy(cur)
    b0 = blk()
    main.handle_cmd({"type": typ, "id": tag, "mode": "MAN", "op": 13.0})
    b1 = blk()
    if b0 is None or b1 is None:
        mres, ores = "no-block", "no-block"
    else:
        mres = "OK" if b1.get("mode") == "MAN" else f"IGNORED({b1.get('mode')})"
        ores = "OK" if abs(float(b1.get("op", -1)) - 13.0) < 1e-6 else f"IGNORED({b1.get('op')})"
    print(f"{tag:<14}{typ:<16}{mres:<12}{ores:<12} {bind}")
    # restore
    if b0 is not None:
        main.handle_cmd({"type": typ, "id": tag, "mode": b0.get("mode", "AUTO")})
