"""probe_wf_pfd_aq.py  -- READ ONLY.
Parse every markdown table in the 1750 MTPD PFD and dump, per stream:
  water%, urea%, NH3%, CO2%, T, P, rho_eff, mass flow, vol flow, avg MW.
Then flag aqueous (water >= 80 mol%) streams and all streams T > 150 C.
"""
import re, sys, io, os

PFD = r"D:\Work\Urea Simulation\References\Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md"
txt = open(PFD, encoding="utf-8").read()
lines = txt.splitlines()

blocks = []          # (header_line_idx, [line indices])
cur = None
for i, ln in enumerate(lines):
    if ln.startswith("| STREAM No."):
        cur = {"hdr": i, "rows": []}
        blocks.append(cur)
    elif cur is not None and ln.startswith("|"):
        cur["rows"].append(i)
    elif cur is not None and not ln.startswith("|"):
        cur = None

def cells(ln):
    parts = [c.strip() for c in ln.strip().strip("|").split("|")]
    return parts

streams = {}   # id -> dict
for b in blocks:
    hdr = cells(lines[b["hdr"]])
    ids = hdr[2:]
    rowmap = {}
    for ri in b["rows"]:
        c = cells(lines[ri])
        if not c or set("".join(c)) <= set(":- "):
            continue
        key = c[0]
        rowmap.setdefault(key, []).append((ri, c))
    for j, sid in enumerate(ids):
        if not sid:
            continue
        rec = streams.setdefault(sid, {"_src": []})
        rec["_src"].append(b["hdr"] + 1)   # 1-based md line of the header
        for key, entries in rowmap.items():
            ri, c = entries[0]
            v = c[j + 2] if j + 2 < len(c) else ""
            if v != "":
                rec.setdefault(key, v)
                rec.setdefault("_ln_" + key, ri + 1)

def f(rec, k):
    v = rec.get(k, "")
    try:
        return float(v)
    except Exception:
        return None

out = []
for sid, rec in streams.items():
    T = f(rec, "Operating Temperature")
    P = f(rec, "Operating Pressure")
    rho = f(rec, "Density eff.")
    w = f(rec, "Water")
    u = f(rec, "Urea")
    a = f(rec, "Ammonia")
    co2 = f(rec, "Carbon Dioxide")
    mw = f(rec, "Average Molar Weight")
    m = f(rec, "Mass Flow total")
    V = f(rec, "Volume Flow")
    out.append((sid, rec.get("Stream description", ""), w, u, a, co2, T, P, rho, mw, m, V, rec))

print("=== ALL streams with water >= 70 mol%% AND rho > 300 (liquid) ===")
print(f"{'id':>6} {'desc':<16} {'H2O%':>6} {'urea%':>6} {'NH3%':>6} {'CO2%':>6} {'T,C':>7} {'P,bara':>7} {'rho':>8} {'MW':>6} {'kg/h':>9} {'m3/h':>9} {'m/V':>8} line")
rows = []
for sid, d, w, u, a, co2, T, P, rho, mw, m, V, rec in out:
    if w is None or rho is None or rho < 300:
        continue
    if w < 70:
        continue
    mv = (m / V) if (m and V) else None
    rows.append((T if T is not None else -1, sid, d, w, u, a, co2, T, P, rho, mw, m, V, rec))
rows.sort()
for T0, sid, d, w, u, a, co2, T, P, rho, mw, m, V, rec in rows:
    print(f"{sid:>6} {d[:16]:<16} {w:>6} {str(u):>6} {str(a):>6} {str(co2):>6} {str(T):>7} {str(P):>7} {str(rho):>8} {str(mw):>6} {str(m):>9} {str(V):>9} "
          f"{(f'{mv:.1f}' if (mv:=((m/V) if (m and V) else None)) else '-'):>8} {rec.get('_ln_Density eff.')}")

print()
print("=== ALL liquid streams (rho>300) with T > 150 C, any composition ===")
rows2 = []
for sid, d, w, u, a, co2, T, P, rho, mw, m, V, rec in out:
    if T is None or rho is None or rho < 300:
        continue
    if T <= 150:
        continue
    rows2.append((T, sid, d, w, u, a, co2, T, P, rho, mw, m, V, rec))
rows2.sort()
for T0, sid, d, w, u, a, co2, T, P, rho, mw, m, V, rec in rows2:
    mv = (m / V) if (m and V) else None
    print(f"{sid:>6} {d[:18]:<18} H2O={str(w):>6} urea={str(u):>6} NH3={str(a):>6} CO2={str(co2):>6} "
          f"T={T:>6} P={str(P):>6} rho={str(rho):>7} MW={str(mw):>6} m={str(m):>8} V={str(V):>8} m/V={(f'{mv:.1f}' if mv else '-'):>8} L{rec.get('_ln_Density eff.')}")

print()
print("=== raw dump for 746, 747, 744, 748, 745, 743 ===")
for sid in ["743", "744", "745", "746", "747", "748", "749", "750"]:
    if sid in streams:
        r = streams[sid]
        print(sid, {k: v for k, v in r.items() if not k.startswith("_")})
        print("   src header md-lines:", r["_src"], " rho line:", r.get("_ln_Density eff."))
