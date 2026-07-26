# Scan ALL PFD sections for the Comp-I flush/wash streams + 734/791/735.
# Goal: map FIC-323401 (M401=823) and FIC-323402 (M402=2931) to their true PFD stream masses.
PFD = r"D:\Work\Urea Simulation\References\Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md"

def cells(line):
    p = [c.strip() for c in line.split("|")]
    return p[1:-1] if p and p[0] == "" and p[-1] == "" else p

with open(PFD, encoding="utf-8") as f:
    lines = f.read().splitlines()

# Walk every section; for each, capture header (STREAM No.) + metric rows, then print
# any of the target stream ids found in that section.
targets = {"734", "791", "735", "744", "755", "775", "718", "701", "702", "786", "738", "343", "742", "321", "797", "911", "749", "750"}
sec = None
hdr = None
rows = {}

def flush(sec, hdr, rows):
    if not hdr:
        return
    ids = hdr
    found = [s for s in targets if s in ids]
    if not found:
        return
    print(f"\n=== {sec} ===")
    for s in sorted(found, key=lambda x: (len(x), x)):
        j = ids.index(s)
        def g(m):
            r = rows.get(m, [])
            return r[j] if j < len(r) else "?"
        print(f"  stream {s:>4}: desc={g('Stream description'):>16}  "
              f"mass={g('Mass Flow total'):>8} kg/h  vol={g('Volume Flow'):>8} m3/h  "
              f"rho={g('Density eff.'):>8}  T={g('Operating Temperature')}C  P={g('Operating Pressure')}bar")

for l in lines:
    if l.startswith("## "):
        flush(sec, hdr, rows)
        sec = l.strip("# ").strip()
        hdr = None; rows = {}
        continue
    c = cells(l)
    if not c:
        continue
    key = c[0]
    if key == "STREAM No.":
        hdr = c
    elif key in ("Mass Flow total", "Volume Flow", "Density eff.",
                 "Stream description", "Operating Temperature", "Operating Pressure"):
        rows[key] = c
flush(sec, hdr, rows)
