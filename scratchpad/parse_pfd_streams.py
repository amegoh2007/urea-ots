# parse PFD-22 desorption table -> exact mass/vol/density per stream (no hand-count)
PFD = r"D:\Work\Urea Simulation\References\Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md"
want = {"775", "755", "734", "791", "744", "735", "911"}

def cells(line):
    # markdown row -> list of trimmed cells (drop leading/trailing empties from | .. |)
    p = [c.strip() for c in line.split("|")]
    return p[1:-1] if p and p[0] == "" and p[-1] == "" else p

with open(PFD, encoding="utf-8") as f:
    lines = f.read().splitlines()

# find the PFD-22 section, then its header (STREAM No.) + the metric rows
start = next(i for i, l in enumerate(lines) if "PFD_No__22_Desorption" in l)
hdr = None
rows = {}
for l in lines[start + 1:]:
    if l.startswith("## "):
        break                     # next section -> stop (do not spill into PFD-24)
    c = cells(l)
    if not c:
        continue
    key = c[0]
    if key == "STREAM No.":
        hdr = c
    elif key in ("Mass Flow total", "Volume Flow", "Density eff.",
                 "Stream description", "Operating Temperature", "Operating Pressure"):
        rows[key] = c

# hdr layout: [ 'STREAM No.', 'Unnamed: 1', <stream ids...> ]
ids = hdr
print("DEBUG start line:", start, repr(lines[start]))
print("DEBUG hdr:", ids[:8], "...", "len", len(ids) if ids else None)
for s in sorted(want, key=lambda x: (len(x), x)):
    if s not in ids:
        print(f"{s}: NOT FOUND"); continue
    j = ids.index(s)
    def g(metric):
        r = rows.get(metric, [])
        return r[j] if j < len(r) else "?"
    print(f"stream {s:>4}: desc={g('Stream description'):>11}  mass={g('Mass Flow total'):>7} kg/h  "
          f"vol={g('Volume Flow'):>7} m3/h  rho={g('Density eff.'):>7}  "
          f"T={g('Operating Temperature')}C  P={g('Operating Pressure')}bar")
