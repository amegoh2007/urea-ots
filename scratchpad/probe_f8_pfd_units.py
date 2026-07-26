"""F-8 phase 0: establish the PFD composition-unit convention, then close every
per-component balance in the desorption train (328C002 / 328C003 / 328C004).

The engine's 328 model is lumped mass with three FROZEN overhead split constants
(R328_C002_PHI737, R328_C003_PHI748, R328_C004_PHI750).  Before a species layer can
replace them, the licensor's own component data has to be shown to close.  A first
hand-check said carbon was NOT conserved across 328C002 (1658 kg/h CO2 in, 858 out).
That would have been a licensor data error.  It is not: the PFD tabulates LIQUID
streams in mass % and VAPOUR streams in mole %, and the average-molar-weight row is
the discriminator that proves it.

Run:  python probe_f8_pfd_units.py
"""
import os
import sys

PFD = r"D:\Work\Urea Simulation\References\Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md"

MW = {"CO2": 44.01, "H2O": 18.015, "NH3": 17.03, "Urea": 60.056, "N2": 28.013, "O2": 31.999}
ROW = {"Carbon Dioxide": "CO2", "Water": "H2O", "Ammonia": "NH3", "Urea": "Urea",
       "Nitrogen": "N2", "Oxygen": "O2"}


def load_tables(path):
    """Return {section_title: {stream_no: {row_label: cell}}} for every '## ' block."""
    lines = open(path, encoding="utf-8").read().split("\n")
    starts = [i for i, l in enumerate(lines) if l.startswith("## ")]
    out = {}
    for si, s in enumerate(starts):
        end = starts[si + 1] if si + 1 < len(starts) else len(lines)
        rows = [[c.strip() for c in l.strip().strip("|").split("|")]
                for l in lines[s:end] if l.strip().startswith("|")]
        rows = [r for r in rows if r and not set("".join(r)) <= set("-: ")]
        if not rows:
            continue
        hdr = rows[0]
        tbl = {}
        for col in range(1, len(hdr)):
            sn = hdr[col]
            if not sn or sn.startswith("Unnamed"):
                continue
            tbl[sn] = {r[0]: (r[col] if col < len(r) else "") for r in rows[1:]}
        out[lines[s][3:].strip()] = tbl
    return out


def num(x):
    x = (x or "").strip()
    if not x:
        return 0.0
    if x.endswith("ppm"):
        return float(x[:-3].strip()) * 1e-4      # ppm(mass) -> percent
    try:
        return float(x)
    except ValueError:
        return 0.0


def comp(st):
    """Tabulated composition row as a percent dict (units still unknown)."""
    return {v: num(st.get(k, "")) for k, v in ROW.items()}


def mw_if_mass(pct):
    d = sum(p / 100.0 / MW[k] for k, p in pct.items() if p)
    return 1.0 / d if d else 0.0


def mw_if_mole(pct):
    return sum(p / 100.0 * MW[k] for k, p in pct.items() if p)


def kg_per_h(st, pct, unit):
    """Component kg/h for a stream, given the resolved unit."""
    if unit == "mass":
        m = num(st.get("Mass Flow total", ""))
        return {k: m * p / 100.0 for k, p in pct.items()}
    n = num(st.get("Molar Flow total", ""))
    return {k: n * p / 100.0 * MW[k] for k, p in pct.items()}


tables = load_tables(PFD)

# ---------------------------------------------------------------- phase 0: units
print("=" * 78)
print("PHASE 0  composition units -- 'Average Molar Weight' is the discriminator")
print("=" * 78)
print(f"{'stream':>7} {'description':<12} {'MW tab':>7} {'as mass%':>9} {'as mole%':>9}   verdict")

RESOLVED = {}
for title, tbl in tables.items():
    if "Process Streams" not in title:
        continue
    for sn, st in tbl.items():
        mw_tab = num(st.get("Average Molar Weight", ""))
        pct = comp(st)
        if mw_tab <= 0 or sum(pct.values()) < 50.0:
            continue
        a, b = mw_if_mass(pct), mw_if_mole(pct)
        da, db = abs(a - mw_tab), abs(b - mw_tab)
        # a single pure component cannot discriminate -- skip those from the verdict
        pure = max(pct.values()) > 99.5
        unit = "mass" if da <= db else "mole"
        RESOLVED[sn] = ("pure" if pure else unit, st.get("Stream description", ""))
        if pure:
            continue
        print(f"{sn:>7} {st.get('Stream description','')[:12]:<12} {mw_tab:7.2f} "
              f"{a:9.2f} {b:9.2f}   {unit.upper():4s}  (err {min(da,db):.3f})")

print()
print("  cross-tab: which descriptions resolve to which unit")
byd = {}
for sn, (u, d) in RESOLVED.items():
    byd.setdefault(d, set()).add(u)
for d in sorted(byd):
    print(f"    {d:<14} -> {sorted(byd[d])}")

# ------------------------------------------------------- phase 1: 328 balances
print()
print("=" * 78)
print("PHASE 1  per-component balance, desorption train (kg/h)")
print("=" * 78)

DES = tables["PFD_No__22_Desorption_1750_MTPD.xlsx - Process Streams Final.csv"]


def unit_of(sn, st):
    """Liquid -> mass %, vapour/gas -> mole %.  Resolved above, applied by class."""
    d = st.get("Stream description", "")
    return "mole" if d in ("Carb. Gas", "Vapour", "MP Steam", "LP Steam", "HP Steam") else "mass"


def flows(sn):
    st = DES[sn]
    return kg_per_h(st, comp(st), unit_of(sn, st)), num(st.get("Mass Flow total", ""))


UREA_MW = MW["Urea"]
COLS = [
    ("328C002  Desorber-I ", ["738", "775", "748", "750"], ["737", "743"], 0.0),
    ("328C003  Hydrolyser ", ["746", "911"],               ["748", "747"], None),
    ("328C004  Desorber-II", ["749", "931"],               ["750", "739"], 0.0),
]

for name, ins, outs, xi_fixed in COLS:
    fin = {k: 0.0 for k in MW}
    fout = {k: 0.0 for k in MW}
    m_in = m_out = 0.0
    for sn in ins:
        f, m = flows(sn)
        for k in f:
            fin[k] += f[k]
        m_in += m
    for sn in outs:
        f, m = flows(sn)
        for k in f:
            fout[k] += f[k]
        m_out += m

    # urea hydrolysis extent that the licensor's own numbers imply
    xi = (fin["Urea"] - fout["Urea"]) / UREA_MW if xi_fixed is None else 0.0
    gen = {"Urea": -xi * UREA_MW, "H2O": -xi * MW["H2O"],
           "NH3": 2.0 * xi * MW["NH3"], "CO2": xi * MW["CO2"]}

    print(f"\n{name}   in {'+'.join(ins)}  ->  out {'+'.join(outs)}")
    print(f"   total mass  in {m_in:10.1f}   out {m_out:10.1f}   diff {m_in-m_out:+8.2f}")
    if xi:
        print(f"   urea hydrolysis extent xi = {xi:.4f} kmol/h "
              f"({xi*UREA_MW:.1f} kg/h urea destroyed)")
    print(f"   {'species':>6} {'in':>10} {'gen':>9} {'out':>10} {'diff':>9}  {'rel':>8}")
    for k in ("CO2", "H2O", "NH3", "Urea"):
        g = gen.get(k, 0.0)
        d = fin[k] + g - fout[k]
        rel = d / fout[k] if fout[k] > 1e-9 else 0.0
        print(f"   {k:>6} {fin[k]:10.1f} {g:9.1f} {fout[k]:10.1f} {d:+9.2f}  {rel:+8.2%}")

# --------------------------------------------- phase 2: the F-11 leftover, 790
print()
print("=" * 78)
print("PHASE 2  stream 790 re-examined under the resolved convention")
print("=" * 78)
EVA = tables["PFD_No__21_Evaporation_1750_MTPD.xlsx - Process Streams Cont.csv"]
for sn in ("319", "331", "315", "790"):
    st = EVA.get(sn)
    if not st:
        print(f"  {sn}: not tabulated here")
        continue
    d = st.get("Stream description", "")
    u = "mole" if d in ("Carb. Gas", "Vapour") else "mass"
    f = kg_per_h(st, comp(st), u)
    print(f"  {sn:>4} {d:<10} [{u}%]  m={num(st.get('Mass Flow total','')):9.1f}  "
          + "  ".join(f"{k}={f[k]:8.1f}" for k in ("CO2", "H2O", "NH3", "Urea")))

fi = {k: 0.0 for k in MW}
fo = {k: 0.0 for k in MW}
for sn in ("319", "331"):
    st = EVA[sn]
    for k, v in kg_per_h(st, comp(st), "mass").items():
        fi[k] += v
for sn in ("315", "790"):
    st = EVA[sn]
    d = st.get("Stream description", "")
    u = "mole" if d in ("Carb. Gas", "Vapour") else "mass"
    for k, v in kg_per_h(st, comp(st), u).items():
        fo[k] += v
print(f"\n   {'species':>6} {'in 319+331':>11} {'out 315+790':>12} {'diff':>9}")
for k in ("CO2", "H2O", "NH3", "Urea"):
    print(f"   {k:>6} {fi[k]:11.1f} {fo[k]:12.1f} {fi[k]-fo[k]:+9.2f}")

# ------------------------------------------- phase 3: datasheet-derived geometry
print()
print("=" * 78)
print("PHASE 3  328C002 / 328C004 geometry from the Uhde datasheet UD-AU-328-EC-0001")
print("=" * 78)
import math

ID = 1.250                       # m, shell inside diameter, both sections
A_COL = math.pi / 4.0 * ID ** 2  # m2
N_HOLE, D_HOLE = 3125, 0.006     # per tray, m   (section X-X)
H_WEIR = 0.040                   # m             (section C-C)
DC_W = 0.202                     # m, downcomer chord width from the wall
R = ID / 2.0
seg = R * R * math.acos((R - DC_W) / R) - (R - DC_W) * math.sqrt(2 * R * DC_W - DC_W ** 2)
A_HOLE = N_HOLE * math.pi / 4.0 * D_HOLE ** 2
A_ACT = A_COL - 2.0 * seg
print(f"  column area      {A_COL:8.4f} m2      (ID {ID*1000:.0f} mm)")
print(f"  downcomer seg    {seg:8.4f} m2      (chord {DC_W*1000:.0f} mm from wall)")
print(f"  active area      {A_ACT:8.4f} m2")
print(f"  hole area        {A_HOLE:8.4f} m2      ({N_HOLE} x dia {D_HOLE*1000:.0f} mm)")
print(f"  hole / active    {A_HOLE/A_ACT:8.2%}      (typical sieve tray 8-12 %)")
print(f"  weir height      {H_WEIR*1000:8.0f} mm")

for tag, ntray, h_nll, rho in (("328C002", 15, 1.150, 933.0), ("328C004", 22, 0.920, 923.28)):
    tray_hold = ntray * A_ACT * H_WEIR * rho * 0.5     # 0.5 = aeration/froth factor
    sump = A_COL * h_nll * rho
    print(f"\n  {tag}: {ntray} exec. trays")
    print(f"    tray holdup   {tray_hold:8.0f} kg   (clear liquid ~= 0.5 x weir height)")
    print(f"    sump at NLL   {sump:8.0f} kg   (NLL {h_nll*1000:.0f} mm above T.L.)")
    print(f"    TOTAL         {tray_hold+sump:8.0f} kg")

print("\n  cross-check vs PFD 'Density eff.':")
print("    328C004 datasheet rho_liq 923.25 @ 143 C   vs PFD stream 739  923.28 @ 143 C")
print("    328C002 datasheet rho_liq 944.00 @ 138 C   vs PFD stream 743  933.00 @ 139 C")
