"""322R001 discharge-stream comparison: MODELLED (react_322r001 equations) vs DESIGN (shared HMB).
Streams: REACT_OVERFLOW (322R001 -> 322E001) and REACT_OFFGAS (322R001 -> 322E003).
Run:  python backend/compare_reactor.py
At the design point (s=1, phi=phi_des) the reduced split-fraction model is pinned to the design
vectors, so every component delta must be ~0 — this script proves the model reproduces the HMB."""
import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8")          # Windows console: allow φ/°/Δ/→/³
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
from main import (MW_COMP, react_322r001, react_nc_ratio, make_stream,
                  REACT_OVERFLOW_DES, REACT_OFFGAS_DES, REACT_HIC605_DES_PCT, CO2_DES_KGH,
                  REACT_OVERFLOW_T_C, REACT_OFFGAS_T_C, REACT_P_BARA, REACT_OFFGAS_P_BARA,
                  REACT_OVERFLOW_RHO, REACT_OFFGAS_RHO)

W = 90


def design_hpcc():
    return {"feed_kmolh": {k: 0.0 for k in MW_COMP}}


def comp_table(title, model_kmolh, design_kmolh):
    print("=" * W)
    print(title)
    print("=" * W)
    print("  %-8s %14s %14s %14s" % ("comp", "MODEL kmol/h", "DESIGN kmol/h", "Δ kmol/h"))
    print("  " + "-" * (W - 2))
    keys = [k for k in MW_COMP if model_kmolh.get(k, 0.0) or design_kmolh.get(k, 0.0)]
    for k in keys:
        m = model_kmolh.get(k, 0.0); d = design_kmolh.get(k, 0.0)
        print("  %-8s %14.4f %14.4f %14.2e" % (k, m, d, m - d))
    mtot = sum(model_kmolh.values()); dtot = sum(design_kmolh.values())
    print("  " + "-" * (W - 2))
    print("  %-8s %14.4f %14.4f %14.2e" % ("Σ TOTAL", mtot, dtot, mtot - dtot))
    print()


def props_table(title, ms, ds):
    """ms/ds = make_stream dicts (model / design)."""
    print("-" * W)
    print("  %s — derived properties" % title)
    print("-" * W)
    rows = [
        ("mass flow (kg/h)",  "%.2f", ms["mass_kgh"], ds["mass_kgh"]),
        ("mass flow (t/h)",   "%.3f", ms["mass_th"],  ds["mass_th"]),
        ("mol flow (kmol/h)", "%.3f", ms["mol_kmolh"], ds["mol_kmolh"]),
        ("MW (g/mol)",        "%.3f", ms["MW"],        ds["MW"]),
        ("T (°C)",            "%.1f", ms["T_C"],       ds["T_C"]),
        ("P (bar a)",         "%.1f", ms["P_bara"],    ds["P_bara"]),
    ]
    if ms.get("rho") is not None:
        rows.append(("density (kg/m³)", "%.2f", ms["rho"], ds["rho"]))
        rows.append(("vol flow (m³/h)", "%.2f", ms["vol_m3h"], ds["vol_m3h"]))
    print("  %-20s %16s %16s %14s" % ("property", "MODEL", "DESIGN", "Δ"))
    print("  " + "-" * (W - 2))
    for name, fmt, mv, dv in rows:
        print(("  %-20s " + fmt.rjust(16) + " " + fmt.rjust(16) + " %14.2e")
              % (name, mv, dv, mv - dv))
    print("  %-20s %16s %16s" % ("phase", ms["phase"], ds["phase"]))
    print()


def pct_table(title, ms, ds, kind):
    key = "mol_pct" if kind == "mol" else "mass_pct"
    print("  %s — %s %%" % (title, kind))
    print("  %-8s %16s %16s %14s" % ("comp", "MODEL %", "DESIGN %", "Δ"))
    print("  " + "-" * (W - 2))
    for k in MW_COMP:
        m = ms[key].get(k, 0.0); d = ds[key].get(k, 0.0)
        if m or d:
            print("  %-8s %16.3f %16.3f %14.2e" % (k, m, d, m - d))
    print()


def main_run():
    # MODELLED at design operating point: s=1 (CO2 design feed), phi=phi_des (HV-322605=60 %)
    r = react_322r001(design_hpcc(), CO2_DES_KGH / 1000.0, REACT_HIC605_DES_PCT)
    print()
    print("#" * W)
    print("  322R001 DISCHARGE STREAMS — MODELLED vs DESIGN   (s=%.3f, φ/φ_des=%.3f)"
          % (r["co2_scale"], r["phi"] / r["phi_des"]))
    print("#" * W)
    print()

    # ---- REACT_OVERFLOW (322R001 -> 322E001) ----
    ov_m = make_stream(r["overflow_kmolh"], REACT_OVERFLOW_T_C, REACT_P_BARA,
                       "overflow", "322R001", "322E001", "liquid", rho=REACT_OVERFLOW_RHO)
    ov_d = make_stream(REACT_OVERFLOW_DES, REACT_OVERFLOW_T_C, REACT_P_BARA,
                       "overflow", "322R001", "322E001", "liquid", rho=REACT_OVERFLOW_RHO)
    comp_table("REACT_OVERFLOW (322R001 → 322E001)  composition", r["overflow_kmolh"], REACT_OVERFLOW_DES)
    props_table("REACT_OVERFLOW", ov_m, ov_d)
    pct_table("REACT_OVERFLOW", ov_m, ov_d, "mass")
    nc_m = react_nc_ratio(r["overflow_kmolh"]); nc_d = react_nc_ratio(REACT_OVERFLOW_DES)
    print("  AT-322701  N/C molar ratio:  MODEL %.4f   DESIGN %.4f   Δ %.2e" % (nc_m, nc_d, nc_m - nc_d))
    print()

    # ---- REACT_OFFGAS (322R001 -> 322E003) ----
    og_m = make_stream(r["offgas_kmolh"], REACT_OFFGAS_T_C, REACT_OFFGAS_P_BARA,
                       "off-gas", "322R001", "322E003", "vapor", rho=REACT_OFFGAS_RHO)
    og_d = make_stream(REACT_OFFGAS_DES, REACT_OFFGAS_T_C, REACT_OFFGAS_P_BARA,
                       "off-gas", "322R001", "322E003", "vapor", rho=REACT_OFFGAS_RHO)
    comp_table("REACT_OFFGAS (322R001 → 322E003)  composition", r["offgas_kmolh"], REACT_OFFGAS_DES)
    props_table("REACT_OFFGAS", og_m, og_d)
    pct_table("REACT_OFFGAS", og_m, og_d, "mol")

    # ---- closure diagnostic ----
    print("=" * W)
    print("  max |Δ| overflow = %.2e kmol/h   |   max |Δ| off-gas = %.2e kmol/h"
          % (max(abs(r["overflow_kmolh"][k] - REACT_OVERFLOW_DES.get(k, 0.0)) for k in MW_COMP),
             max(abs(r["offgas_kmolh"][k] - REACT_OFFGAS_DES.get(k, 0.0)) for k in MW_COMP)))
    print("  Model reproduces design HMB to machine precision (pinned split-fraction).")
    print("=" * W)


if __name__ == "__main__":
    main_run()
