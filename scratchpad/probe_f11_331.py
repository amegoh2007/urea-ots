"""F-11 probe: does adding PFD stream 331 close the 323F010 balance?

Phase 0 -- static anchors: the back-solved stage residual, the water closure term, the alphas.
Phase A -- design hold: every 323 anchor must still sit on its design value and not drift.
Phase B -- the point of the whole exercise: 323F010 must now reach the PFD's 80 % urea unaided.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
import main  # noqa: E402

DT = 0.25


def run(seconds):
    out = None
    for _ in range(int(seconds / DT)):
        out = main.step_sim(DT)
    return out


print("=" * 78)
print("PHASE 0 -- static design anchors")
print("=" * 78)
print(f"  m_319  des      {main.R323_M319_DES:12.2f} kg/h   (PFD 319  101570)")
print(f"  m_331  des      {main.R323_M331_DES:12.2f} kg/h   (PFD 331    3270)")
print(f"  m_evap des      {main.R323_MEVAP_DES:12.2f} kg/h   (PFD 790   12040)")
print(f"  m_317  des      {main.R323_M317_DES:12.2f} kg/h   (PFD 315/317 92820)")
_in = main.R323_M319_DES + main.R323_M331_DES
_out = main.R323_MEVAP_DES + main.R323_M317_DES
print(f"  C1 closure      in {_in:.6f}  out {_out:.6f}  diff {_in - _out:+.3e} kg/h")
print(f"  Q_E010 des      {main.R323_E010_Q_DES_KW:12.1f} kW     (was ~5048 without 331)")
print(f"  UA_E010         {main.R323_E010_UA_KW:12.3f} kW/K")

a = main.SOL_F010
print(f"\n  SOL_F010 resid  {a['resid']:12.3f} kg/h   (was -1414 with 331 missing)")
print(f"  SOL_F010 xi     {a['xi']:12.4f} kmol/h biuret")
print("  design vapour 790 (kg/h)      model      PFD")
_pfd790 = {"H2O": 12040 * 0.9004, "NH3": 12040 * 0.0741, "CO2": 12040 * 0.0229,
           "Urea": 12040 * 0.0014, "Biuret": 0.0, "HCHO": 0.0}
for k in main.SOL_SPECIES:
    print(f"    {k:<8} {a['y'][k] * main.R323_MEVAP_DES:10.1f}   {_pfd790[k]:8.1f}")
print("  relative volatilities vs water:")
for k in main.SOL_SPECIES:
    print(f"    {k:<8} {a['alpha'][k]:10.4f}")

print("\n  HCHO tracer -- stream 331 is the ONLY source in the train:")
_hin = main.R323_M331_DES * main.W_S331["HCHO"]
_hout = main.R323_M317_DES * main.W_S317["HCHO"]
print(f"    in via 331 {_hin:7.2f} kg/h   out via 317 {_hout:7.2f} kg/h   "
      f"closure {(_hout / _hin - 1.0) * 100:+.2f} %")

print("\n" + "=" * 78)
print("PHASE A -- design hold (600 s), anchors + drift")
print("=" * 78)
main.state = main.State()
t = run(600.0)
f10 = t["RECIRC_323"]["F010"]
sp = t["SPECIES_323_324"]
print(f"  TT_323010       {f10['TT_323010']:8.2f} C     (hold 99.0)")
print(f"  feed331_th      {f10['feed331_th']:8.2f} t/h   (des {main.R323_M331_DES / 1000:.2f})")
print(f"  evap_th         {f10['evap_th']:8.2f} t/h   (des {main.R323_MEVAP_DES / 1000:.2f})")
print(f"  product317_th   {f10['product317_th']:8.2f} t/h   (des {main.R323_M317_DES / 1000:.2f})")
print(f"  Q_kW            {f10['Q_kW']:8.0f} kW    (des {main.R323_E010_Q_DES_KW:.0f})")

b = run(600.0)
print("\n  drift over a second 600 s window:")
for tag in ("evap_th", "product317_th", "TT_323010"):
    print(f"    {tag:<15} {b['RECIRC_323']['F010'][tag] - f10[tag]:+.4f}")

print("\n" + "=" * 78)
print("PHASE B -- does 323F010 now reach the PFD composition unaided?")
print("=" * 78)
print("  stage      Urea%    PFD     Biuret%   PFD      sum")
_pfd = {"C003": (68.74, 0.36), "F004": (71.74, 0.37), "F010": (80.00, 0.42),
        "D002": (80.00, 0.42), "E001": (94.31, 0.69), "E003": (97.71, 0.85)}
for tag in ("C003", "F004", "F010", "D002", "E001", "E003"):
    liq = b["SPECIES_323_324"]["liq"][tag]
    u, bi = _pfd[tag]
    print(f"  {tag:<8} {liq['Urea']:8.3f} {u:7.2f}   {liq['Biuret']:8.4f} {bi:6.2f}   "
          f"{b['SPECIES_323_324']['sum'][tag]:10.6f}")

print("\n  formaldehyde now has a source (was 0 everywhere upstream of the pin):")
for tag in ("F004", "F010", "D002", "E001", "E003"):
    print(f"    {tag:<8} {b['SPECIES_323_324']['liq'][tag]['HCHO']:10.6f} %")

print("\n  biuret extents (kmol/h) and total formation:")
xi = b["SPECIES_323_324"]["xi_biuret_kmolh"]
tot = sum(xi.values())
for k, v in xi.items():
    print(f"    {k:<8} {v:10.4f}")
print(f"    TOTAL    {tot:10.4f} kmol/h = {tot * main.MW_SOL['Biuret']:.1f} kg/h "
      f"(PFD flows imply ~322 kg/h)")
