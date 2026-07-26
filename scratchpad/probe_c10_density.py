"""C10 phase 0: can a single anchored correlation reproduce the PFD's own 'Density eff.' row?

The engine carries liquid density as a set of compile-time constants.  Before replacing them with a
literature correlation, check what the licensor's own table says: PFD_20/21/22 tabulate 'Density
eff.' for every stream at its own temperature and composition -- roughly ninety (T, w, rho) points,
and per CLAUDE.md §0 they outrank anything from the literature.

Form under test, water reference plus a urea-fraction correction:
    rho(T, w_urea) = rho_water(T) * (1 + b1*w_urea + b2*w_urea^2)
with rho_water from Kell (1975), the standard 0-150 C atmospheric fit.

Run:  python probe_c10_density.py
"""
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_f8_pfd_units import load_tables, comp, num, MW, ROW, PFD  # noqa: E402


def rho_water_kell(t_c: float) -> float:
    """Kell (1975), density of air-free water at 1 atm, kg/m3, t in Celsius. Valid 0-150 C."""
    n = (999.83952 + 16.945176 * t_c - 7.9870401e-3 * t_c ** 2
         - 46.170461e-6 * t_c ** 3 + 105.56302e-9 * t_c ** 4
         - 280.54253e-12 * t_c ** 5)
    return n / (1.0 + 16.879850e-3 * t_c)


tables = load_tables(PFD)
pts = []
for title, tbl in tables.items():
    if "Process Streams" not in title:
        continue
    for sn, st in tbl.items():
        d = st.get("Stream description", "")
        if d not in ("Urea Sol.", "Amm. Water", "Vap. Cond.", "Pur. Pr. C", "Proc. Con.",
                     "Carb. Liq."):
            continue
        rho = num(st.get("Density eff.", ""))
        T = num(st.get("Operating Temperature", ""))
        pct = comp(st)
        if rho <= 200.0 or T <= 0.0:
            continue                     # vapour rows / blanks
        w_u = pct.get("Urea", 0.0) / 100.0
        pts.append((sn, d, T, w_u, pct, rho))

# dedupe identical (T, w, rho) triples -- the same stream appears in several tables
seen, uniq = set(), []
for p in pts:
    key = (round(p[2], 3), round(p[3], 5), round(p[5], 3))
    if key not in seen:
        seen.add(key)
        uniq.append(p)
pts = uniq
print(f"{len(pts)} distinct liquid (T, composition, density) points on the PFD\n")

# ---- 1. the pure-water subset: does Kell reproduce the licensor's numbers unaided? -------------
print("=" * 78)
print("1. near-pure-water streams -- Kell (1975) vs the PFD, no fitting at all")
print("=" * 78)
print(f"{'stream':>7} {'desc':<11} {'T C':>7} {'urea%':>7} {'PFD rho':>9} {'Kell':>9} {'err':>8}")
worst = 0.0
for sn, d, T, w_u, pct, rho in sorted(pts, key=lambda p: p[2]):
    if pct.get("H2O", 0.0) < 98.0:
        continue
    k = rho_water_kell(T)
    e = (k - rho) / rho
    worst = max(worst, abs(e))
    print(f"{sn:>7} {d:<11} {T:7.1f} {w_u*100:7.3f} {rho:9.2f} {k:9.2f} {e:+8.3%}")
print(f"\n  worst deviation on the pure-water subset: {worst:.3%}")

# ---- 2. fit the urea correction on the urea-bearing streams -------------------------------------
print()
print("=" * 78)
print("2. urea-bearing streams -- rho / rho_water(T) against the urea mass fraction")
print("=" * 78)
rows = [(sn, T, w_u, rho, rho / rho_water_kell(T))
        for sn, d, T, w_u, pct, rho in pts if w_u > 0.005]
rows.sort(key=lambda r: r[2])

# least squares on  y - 1 = b1*w + b2*w^2   (forced through 1.0 at w = 0, i.e. pure water)
s11 = s12 = s22 = t1 = t2 = 0.0
for _, _, w, _, y in rows:
    s11 += w ** 2
    s12 += w ** 3
    s22 += w ** 4
    t1 += w * (y - 1.0)
    t2 += w ** 2 * (y - 1.0)
det = s11 * s22 - s12 * s12
b1 = (t1 * s22 - t2 * s12) / det
b2 = (s11 * t2 - s12 * t1) / det
print(f"  fit:  rho = rho_water_kell(T) * (1 + {b1:.6f}*w + {b2:.6f}*w^2)   "
      f"({len(rows)} points, forced exact at w=0)\n")
print(f"{'stream':>7} {'T C':>7} {'urea%':>7} {'PFD rho':>9} {'model':>9} {'err':>8}")
worst2 = 0.0
for sn, T, w, rho, y in rows:
    mdl = rho_water_kell(T) * (1.0 + b1 * w + b2 * w * w)
    e = (mdl - rho) / rho
    worst2 = max(worst2, abs(e))
    print(f"{sn:>7} {T:7.1f} {w*100:7.2f} {rho:9.2f} {mdl:9.2f} {e:+8.3%}")
print(f"\n  worst deviation across the urea streams: {worst2:.3%}")

# ---- 3. the two 328 anchors ---------------------------------------------------------------------
print()
print("=" * 78)
print("3. the anchors the 328 datasheet supplied")
print("=" * 78)
for tag, T, rho_ref, src in (("328C004 / stream 739", 143.0, 923.28, "PFD"),
                             ("328C004 datasheet   ", 143.0, 923.25, "Uhde DDS"),
                             ("328C002 / stream 743", 139.0, 933.00, "PFD")):
    k = rho_water_kell(T)
    print(f"  {tag}  {src:<9} {rho_ref:8.2f}   Kell(T) {k:8.2f}   err {(k-rho_ref)/rho_ref:+.3%}")
print("\n  Kell alone explains the purified condensate to well under a percent -- it IS water.")
