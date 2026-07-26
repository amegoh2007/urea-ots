"""Item 22 acceptance: FFIC-335406 UF85 injection re-anchored to PFD stream 697.
 - R324_UF_RATIO numerator 697.0 -> 694.0 kg/h (694 kg/h @design, PFD stream 697)
 - R324_UF85_RHO 1320.0 -> 1305.0 kg/m3 (40 C stream density, was the xmtr SG-cal)
 - dead R324_UF85_RHO now wired: uf85_m3h = m_uf / RHO telemetry (~0.53 m3/h)
UF85 is an external additive OFF the urea/water conservation network, so this
must not move the pin or the design anchor.  Run: cd backend && python ../scratchpad/probe_uf22.py
"""
import sys, os
BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, BACKEND); os.chdir(BACKEND)
import main

P2   = main.R324_P2_DES
ratio= main.R324_UF_RATIO
rho  = main.R324_UF85_RHO
mdes = main.R324_M_UF_DES
print(f"R324_P2_DES        = {P2:.3f} kg/h")
print(f"R324_UF_RATIO      = {ratio:.7f}   (expect 694/{P2:.3f} = {694.0/P2:.7f})")
print(f"R324_UF85_RHO      = {rho:.1f} kg/m3   (expect 1305.0)")
print(f"R324_M_UF_DES      = {mdes:.1f} kg/h   (expect 694.0)")

telem = main.step_sim(0.1)                                  # tick 1 = design
e003  = telem["EVAP_324"]["E003"]
uf_kg = e003["uf85_kgh"]
uf_m3 = e003.get("uf85_m3h")
print(f"uf85_kgh (live)    = {uf_kg} kg/h   (expect ~694)")
print(f"uf85_m3h (live)    = {uf_m3} m3/h   (expect ~0.53)")

bad = 0
if abs(ratio - 694.0/P2) > 1e-9:
    print("FAIL: UF ratio not 694/P2_DES"); bad += 1
if abs(rho - 1305.0) > 1e-9:
    print("FAIL: RHO not 1305"); bad += 1
if abs(mdes - 694.0) > 0.05:
    print("FAIL: design UF injection != 694 kg/h"); bad += 1
if abs(uf_kg - 694.0) > 1.0:
    print("FAIL: live uf85_kgh != 694 at design"); bad += 1
if uf_m3 is None:
    print("FAIL: uf85_m3h telemetry absent (RHO still dead)"); bad += 1
elif abs(uf_m3 - 694.0/1305.0) > 0.02:
    print(f"FAIL: uf85_m3h wrong ({uf_m3}, expect {694.0/1305.0:.3f})"); bad += 1

print(f"\nFAILURES: {bad}")
sys.exit(1 if bad else 0)
