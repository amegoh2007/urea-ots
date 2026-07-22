"""AUDIT F-8 / TD-009 probe: the downstream component species balance (units 323 + 324).

Phase 0  design anchors back-solved from the PFD -- biuret extents and the clip residual that
         exposed finding F-11 (the stream-317 composition is unreachable from stream 319)
Phase A  design hold -> every stage must sit on its PFD composition and Sum w must read 100.0000
Phase B  strip-efficiency disturbance -> the downstream composition must MOVE (it was blind before)
"""
import os, sys
_B = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
sys.path.insert(0, _B)
os.chdir(_B)
import main  # noqa: E402

DT = 0.25
LIQ = ("C003", "F004", "F010", "D002", "E001", "E003")
PFD = {"C003": 68.74, "F004": 71.74, "F010": 80.00, "D002": 80.00, "E001": 94.31, "E003": 97.71}
PFD_BIU = {"C003": 0.36, "F004": 0.37, "F010": 0.42, "D002": 0.42, "E001": 0.69, "E003": 0.85}


def run(sec):
    out = None
    for _ in range(int(sec / DT)):
        out = main.step_sim(DT)
    return out


def table(tag, t):
    sp = t["SPECIES_323_324"]
    print(f"  {tag}")
    print(f"    {'stage':6s} {'Urea%':>9s} {'(PFD)':>8s} {'Biuret%':>9s} {'(PFD)':>7s}"
          f" {'NH3%':>8s} {'CO2%':>7s} {'H2O%':>9s} {'Sum':>11s}")
    for k in LIQ:
        w = sp["liq"][k]
        print(f"    {k:6s} {w['Urea']:9.3f} {PFD[k]:8.2f} {w['Biuret']:9.3f} {PFD_BIU[k]:7.2f}"
              f" {w['NH3']:8.3f} {w['CO2']:7.3f} {w['H2O']:9.3f} {sp['sum'][k]:11.4f}")


print("=== Phase 0: design anchors back-solved from the PFD ===")
print(f"  {'stage':6s} {'xi_biuret kmol/h':>18s} {'clip kg/h':>12s}")
for tag, a in (("C003", main.SOL_C003), ("F004", main.SOL_F004), ("F010", main.SOL_F010),
               ("E001", main.SOL_E001), ("E003", main.SOL_E003)):
    print(f"  {tag:6s} {a['xi']:18.4f} {a['resid']:12.1f}")
print("  -> the -1414 kg/h clip at F010 is finding F-11 (see EQUATION_AUDIT §5)")
tot_biu = sum(a["xi"] for a in (main.SOL_C003, main.SOL_F004, main.SOL_F010,
                                main.SOL_E001, main.SOL_E003)) * main.MW_SOL["Biuret"]
print(f"  total biuret made = {tot_biu:.1f} kg/h   (PFD stream flows imply ~322 kg/h)")

print("\n=== Phase A: design hold ===")
t = _t = run(600.0); table("t = 600 s", t)
t = run(1800.0);     table("t = 2400 s (stationarity check)", t)
sp = t["SPECIES_323_324"]
print(f"  species urea% {sp['urea_pct_species']}   scalar urea% "
      f"{t['EVAP_324']['E001']['urea_pct']} / {t['EVAP_324']['E003']['urea_pct']}")
print("  vapour compositions (mass %, components > 0.01 only):")
for k, v in sp["vap"].items():
    print(f"    {k:5s} " + "  ".join(f"{kk}={vv:.3f}" for kk, vv in v.items() if vv > 0.01))

print("\n=== Phase B: ejector-spindle disturbance (shifts the whole HP loop) ===")
main.state = main.State()
t = run(300.0)
base = {k: t["SPECIES_323_324"]["liq"][k]["NH3"] for k in LIQ}
main.state.HIC_322602 = 55.0
t = run(900.0)
print(f"    {'stage':6s} {'NH3% before':>13s} {'NH3% after':>12s} {'delta':>10s}")
for k in LIQ:
    now = t["SPECIES_323_324"]["liq"][k]["NH3"]
    print(f"    {k:6s} {base[k]:13.4f} {now:12.4f} {now - base[k]:+10.4f}")
table("post-disturbance", t)
