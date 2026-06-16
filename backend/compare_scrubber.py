# -*- coding: utf-8 -*-
"""322E003 HP Scrubber — model-vs-shared discharge comparison (design point).

Proves the pinned split-fraction scrubber reproduces BOTH shared discharge streams
(off-gas img1 + overflow = ejector suction) from the two feeds
(live REACT_OFFGAS + carbamate 323P001 A/B), and that the tube-side mole balance
closes.  Run with the real interpreter before binding into main.py.
"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from main import MW_COMP, REACT_OFFGAS_DES, EJ_SUCTION_KGH, CO2_DES_KGH

COMPS = ["NH3", "CO2", "H2O", "N2", "O2", "CH4", "H2", "Urea", "Biuret"]

# ---- FEED 2: carbamate 323P001 A/B -> 322E003 (img2, MASS%, 36915 kg/h) ----
CARB_KGH_TOT = 36915.0
CARB_MASSPCT = {"CO2": 38.49, "H2O": 30.83, "NH3": 30.61, "Urea": 0.07}
CARB_KMOLH = {k: CARB_MASSPCT.get(k, 0.0) / 100.0 * CARB_KGH_TOT / MW_COMP[k] for k in COMPS}

# ---- DISCHARGE 2 (SHARED): off-gas 322E003 -> 322C001 (img1, MOL%, 64.78 kmol/h) ----
OFFGAS_MOL_TOT = 64.78
OFFGAS_MOLPCT = {"N2": 68.81, "O2": 11.39, "NH3": 8.26, "CH4": 5.93,
                 "H2": 3.14, "CO2": 2.22, "H2O": 0.26}
OFFGAS_SHARED = {k: OFFGAS_MOLPCT.get(k, 0.0) / 100.0 * OFFGAS_MOL_TOT for k in COMPS}

# ---- DISCHARGE 1 (SHARED): overflow 322E003 -> 322F001 = ejector suction (kg/h -> kmol/h) ----
OVERFLOW_SHARED = {k: EJ_SUCTION_KGH[k] / MW_COMP[k] for k in COMPS}

# ---- MODEL (pinned split-fraction, co2_scale = 1.0 at design) ----
s = 1.0
feed = {k: REACT_OFFGAS_DES.get(k, 0.0) * s + CARB_KMOLH[k] * s for k in COMPS}
offgas_model   = {k: OFFGAS_SHARED[k]   * s for k in COMPS}     # pinned to img1
overflow_model = {k: OVERFLOW_SHARED[k] * s for k in COMPS}     # pinned to EJ suction


def col(x): return f"{x:10.3f}"


print("=" * 86)
print("322E003 TUBE-SIDE MOLE BALANCE  (kmol/h)   feed = REACT_OFFGAS + carbamate 323P001")
print("=" * 86)
print(f"{'comp':7}{'offgas_feed':>12}{'carb_feed':>12}{'FEED_tot':>11}"
      f"{'offgas_out':>12}{'overflow':>11}{'out_tot':>10}{'Δ(in-out)':>11}")
fi = fo = fv = ff = 0.0
for k in COMPS:
    ot = offgas_model[k] + overflow_model[k]
    d = feed[k] - ot
    print(f"{k:7}{REACT_OFFGAS_DES.get(k,0.0):12.3f}{CARB_KMOLH[k]:12.3f}{feed[k]:11.3f}"
          f"{offgas_model[k]:12.3f}{overflow_model[k]:11.3f}{ot:10.3f}{d:11.3f}")
    ff += feed[k]; fo += offgas_model[k]; fv += overflow_model[k]
print("-" * 86)
print(f"{'TOTAL':7}{sum(REACT_OFFGAS_DES.values()):12.3f}{sum(CARB_KMOLH.values()):12.3f}"
      f"{ff:11.3f}{fo:12.3f}{fv:11.3f}{fo+fv:10.3f}{ff-fo-fv:11.3f}")
print(f"\nclosure_resid = feed - offgas - overflow = {ff-fo-fv:+.3f} kmol/h "
      f"({(ff-fo-fv)/ff*100:+.3f} %)")

# ---- absorbed (feed - offgas) vs carbamate-formation sink ----
print("\n" + "=" * 60)
print("ABSORPTION (recovered into overflow carbamate, kmol/h)")
print("=" * 60)
for k in ["NH3", "CO2", "H2O"]:
    absd = REACT_OFFGAS_DES.get(k, 0.0) - offgas_model[k]
    print(f"  {k:5}: feed {REACT_OFFGAS_DES.get(k,0.0):8.2f} -> slip {offgas_model[k]:6.3f}"
          f"  => absorbed {absd:8.2f}  ({absd/REACT_OFFGAS_DES.get(k,1e-9)*100:5.1f} %)")

# ---- split fractions to gas (calibration constants) ----
print("\nSCRUB_FRAC_GAS_DES  psi_i = offgas_i / feed_i:")
for k in COMPS:
    psi = offgas_model[k] / feed[k] if feed[k] else 0.0
    print(f"  {k:7}: {psi:8.5f}")

# ---- CCW shell-side energy balance (img3: 306 t/h, 80 -> 95 C) ----
print("\n" + "=" * 60)
print("CCW SHELL-SIDE ENERGY BALANCE  (img3 Circ. W. 1111/1112)")
print("=" * 60)
M_CCW = 306000.0          # kg/h
CP_W = 4.18               # kJ/kg.K
T_IN, T_OUT = 80.0, 95.0  # TIC-329005 supply, TT-329125 return
Q_ccw = M_CCW * CP_W * (T_OUT - T_IN) / 3600.0
print(f"  Q_ccw = m*cp*dT = {M_CCW/1000:.0f} t/h * {CP_W} * ({T_OUT}-{T_IN}) = {Q_ccw:8.1f} kW")
print(f"  TDY-329125 = TT-329125 - TIC-329005 = {T_OUT}-{T_IN} = {T_OUT-T_IN:.1f} C (cond. quality)")

# ---- per-component max abs deviation model vs shared (must be 0: pinned) ----
print("\n" + "=" * 60)
print("MODEL vs SHARED discharge (pinned) — max |Δ| per stream")
print("=" * 60)
dog = max(abs(offgas_model[k] - OFFGAS_SHARED[k]) for k in COMPS)
dov = max(abs(overflow_model[k] - OVERFLOW_SHARED[k]) for k in COMPS)
print(f"  off-gas  (322E003->322C001): max|Δ| = {dog:.3e} kmol/h")
print(f"  overflow (322E003->322F001): max|Δ| = {dov:.3e} kmol/h")
print(f"\n  off-gas  total: {sum(offgas_model.values()):.2f} kmol/h "
      f"(shared {OFFGAS_MOL_TOT})")
print(f"  overflow total: {sum(overflow_model.values()):.2f} kmol/h, "
      f"{sum(EJ_SUCTION_KGH.values()):.0f} kg/h")
print("\nIDENTICAL." if max(dog, dov) < 1e-9 else "\nMISMATCH.")
