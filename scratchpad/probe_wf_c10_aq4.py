"""probe_wf_c10_aq4.py -- READ ONLY.
Rigorous, model-free test of the dissolved-solids explanation: back out the apparent
partial specific volume (and hence apparent density) the solutes would need in order to
reproduce the tabulated 'Density eff.' with IF97 water as the solvent.
   1/rho_tab = (1-w_s)/rho_w(T) + w_s/rho_app     ->    rho_app = w_s / (1/rho_tab - (1-w_s)/rho_w)
A negative or absurd rho_app falsifies the solute explanation outright.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_wf_if97 import sat_liq

MW = {"H2O": 18.0152, "NH3": 17.0304, "CO2": 44.0098, "urea": 60.056}
S = [  # id, T, rho_tab, mol% H2O/urea/NH3/CO2
    ("744", 44.0, 1002.0, 91.13, 0.89, 4.17, 3.81),
    ("755", 40.0, 1005.0, 91.13, 0.89, 4.17, 3.81),
    ("343", 56.0,  992.2, 90.24, 0.82, 5.23, 3.71),
    ("738", 114.0, 959.7, 90.24, 0.82, 5.23, 3.71),
    ("743", 139.0, 933.0, 98.50, 0.76, 0.63, 0.11),
    ("746", 190.0, 908.5, 98.50, 0.76, 0.63, 0.11),
    ("779", 139.0, 928.9, 99.16, 0.00, 0.83, 0.01),
    ("749", 148.0, 924.1, 99.02, 0.00, 0.97, 0.02),
    ("747", 200.0, 897.7, 99.02, 0.00, 0.97, 0.02),
]
print("Apparent density the dissolved NH3+CO2+urea would have to have")
print(f"{'id':>5} {'T,C':>6} {'rho_tab':>8} {'rho_w':>8} {'w_solute':>9} {'v_solute':>12} {'rho_app':>10}  verdict")
for sid, T, rt, mH, mU, mN, mC in S:
    mol = {"H2O": mH, "urea": mU, "NH3": mN, "CO2": mC}
    m = {k: mol[k] * MW[k] for k in mol}
    tot = sum(m.values())
    ws = 1.0 - m["H2O"] / tot
    rw = sat_liq(T)[0]
    v_tot = 1.0 / rt
    v_w = (1.0 - ws) / rw
    v_s = v_tot - v_w
    if abs(v_s) < 1e-12:
        ra = float("inf")
    else:
        ra = ws / v_s
    if ra < 0:
        verd = "IMPOSSIBLE (negative solute volume)"
    elif ra > 2000:
        verd = "unphysical (> 2000 kg/m3 for NH3/urea/carbamate)"
    else:
        verd = "physically plausible"
    print(f"{sid:>5} {T:>6.0f} {rt:>8.1f} {rw:>8.2f} {100*ws:>8.3f}% {v_s:>+12.3e} {ra:>10.1f}  {verd}")

print()
print("Same-composition pairs -- the solute term is IDENTICAL, so it cannot explain the growth:")
for a, b in (("743", "746"), ("749", "747")):
    da = [x for x in S if x[0] == a][0]
    db = [x for x in S if x[0] == b][0]
    ea = 100 * (da[2] / sat_liq(da[1])[0] - 1)
    eb = 100 * (db[2] / sat_liq(db[1])[0] - 1)
    print(f"  {a} @ {da[1]:.0f} C excess {ea:+.2f} %   ->   {b} @ {db[1]:.0f} C excess {eb:+.2f} %"
          f"   growth {eb-ea:+.2f} points over {db[1]-da[1]:.0f} K at unchanged composition")

print()
print("Upper bound on the solute term: assume the solutes are as dense as solid urea (1335 kg/m3),")
print("which is the densest species present, and recompute:")
for sid, T, rt, mH, mU, mN, mC in S:
    mol = {"H2O": mH, "urea": mU, "NH3": mN, "CO2": mC}
    m = {k: mol[k] * MW[k] for k in mol}
    tot = sum(m.values())
    ws = 1.0 - m["H2O"] / tot
    rw = sat_liq(T)[0]
    rmax = 1.0 / ((1 - ws) / rw + ws / 1335.0)
    print(f"  {sid} @ {T:>5.1f} C: max plausible rho = {rmax:8.2f}  tabulated {rt:8.1f}"
          f"   {'OK' if rt <= rmax + 0.5 else 'EXCEEDS by %+.2f kg/m3 (%+.2f %%)' % (rt - rmax, 100*(rt/rmax-1))}")
