"""probe_wf_pfd_all.py -- READ ONLY.  Completeness: every stream in the 1750 PFD with T>=140 C,
regardless of phase, so nothing above 150 C is missed."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
PFD = r"D:\Work\Urea Simulation\References\Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md"
lines = open(PFD, encoding="utf-8").read().splitlines()
blocks, cur = [], None
for i, ln in enumerate(lines):
    if ln.startswith("| STREAM No."):
        cur = {"hdr": i, "rows": []}
        blocks.append(cur)
    elif cur is not None and ln.startswith("|"):
        cur["rows"].append(i)
    elif cur is not None:
        cur = None


def cells(ln):
    return [c.strip() for c in ln.strip().strip("|").split("|")]


recs = []
for b in blocks:
    hdr = cells(lines[b["hdr"]])
    rowmap = {}
    for ri in b["rows"]:
        c = cells(lines[ri])
        if not c or set("".join(c)) <= set(":- "):
            continue
        rowmap.setdefault(c[0], (ri, c))
    for j, sid in enumerate(hdr[2:]):
        if not sid:
            continue
        r = {"id": sid, "blk": b["hdr"] + 1}
        for k, (ri, c) in rowmap.items():
            v = c[j + 2] if j + 2 < len(c) else ""
            if v:
                r[k] = v
        recs.append(r)


def fl(r, k):
    try:
        return float(r.get(k, ""))
    except Exception:
        return None


print(f"{'blk':>4} {'id':>6} {'desc':<20} {'T,C':>6} {'P':>6} {'rho':>9} {'H2O%':>6} {'NH3%':>6} "
      f"{'CO2%':>6} {'urea%':>6} {'kg/h':>9}")
seen = set()
for r in sorted(recs, key=lambda r: (fl(r, "Operating Temperature") or -1)):
    T = fl(r, "Operating Temperature")
    if T is None or T < 140:
        continue
    key = (r["id"], T, r.get("Density eff."))
    if key in seen:
        continue
    seen.add(key)
    print(f"{r['blk']:>4} {r['id']:>6} {r.get('Stream description','')[:20]:<20} {T:>6.0f} "
          f"{str(fl(r,'Operating Pressure')):>6} {str(fl(r,'Density eff.')):>9} "
          f"{str(fl(r,'Water')):>6} {str(fl(r,'Ammonia')):>6} {str(fl(r,'Carbon Dioxide')):>6} "
          f"{str(fl(r,'Urea')):>6} {str(fl(r,'Mass Flow total')):>9}")
