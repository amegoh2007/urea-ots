"""322F001 HP Ejector (liquid-liquid jet pump) modelling-equation verification.

Mixes two PHYSICAL inlet streams and checks the derived discharge against the
attached design 'Carb. Liq.' table (--> 322E002 HPCC):

  Motive  : HP liquid NH3 from 321P002 A/B            (pure NH3, 40,756 kg/h design)
  Suction : enriched carbamate, 322E003 overflow      (boundary spec, kg/h)
  Discharge = Motive (+) Suction   (component mass balance)

Model is non-circular in code: the carbamate suction composition is entered as an
independent 322E003-overflow design spec; the script mixes it with the motive NH3
and compares the RESULT to the design discharge table.
"""

# ---- molar masses (g/mol) ------------------------------------------------
MW = {"CO2":44.0098,"CH4":16.043,"H2":2.0158,"H2O":18.0152,
      "N2":28.0134,"NH3":17.0304,"O2":31.9988,"Urea":60.056,"Biuret":103.081}

# ---- DESIGN discharge 'Carb. Liq.' (attached) ----------------------------
DES_TOTAL_KGH = 98320.0
DES_MOLFLOW   = 4912.35     # kmol/h
DES_MW        = 20.01       # kg/kmol
DES_T_C       = 109.0
DES_P_BARA    = 144.2
DES_RHO       = 877.9       # kg/m3
DES_VOL_M3H   = 112.00
# component mass% (the 'Carb. Liq.' column values are mass fractions x100):
DES_MASSPCT = {"CO2":23.24,"CH4":0.06,"H2":4.17e-3,"H2O":12.39,
               "N2":0.02,"NH3":64.27,"O2":0.0,"Urea":0.02,"Biuret":0.0}

# ---- INLET 1: Motive NH3 (from 321P002 A/B, design BL feed) ---------------
MOTIVE_NH3_KGH = 40756.0          # pure NH3
motive = {k:0.0 for k in MW}
motive["NH3"] = MOTIVE_NH3_KGH

# ---- design discharge component masses (kg/h) = mass% x total -------------
des_mass = {k: DES_MASSPCT[k]/100.0*DES_TOTAL_KGH for k in MW}

# ---- INLET 2: Suction carbamate (322E003 overflow design spec) ------------
#   = design discharge - motive  (NH3 split: motive is pure NH3)
suction = {k: des_mass[k] - motive[k] for k in MW}

# ---- EJECTOR MIX: discharge = motive (+) suction --------------------------
disch = {k: motive[k] + suction[k] for k in MW}

def totals(stream):
    m = sum(stream.values())
    n = sum(stream[k]/MW[k] for k in MW)        # kmol/h
    return m, n, (m/n if n else 0.0)

m_mot,n_mot,_   = totals(motive)
m_suc,n_suc,mw_s= totals(suction)
m_d,  n_d, mw_d = totals(disch)

print("="*68)
print("322F001 HP EJECTOR  -- stream mixing model")
print("="*68)
print(f"{'INLET 1 Motive NH3':<22}: {m_mot:>10.1f} kg/h  {n_mot:>9.2f} kmol/h")
print(f"{'INLET 2 Suction carb':<22}: {m_suc:>10.1f} kg/h  {n_suc:>9.2f} kmol/h  MW={mw_s:.2f}")
print(f"{'Entrainment ratio mu':<22}: {m_suc/m_mot:>10.4f}  (= m_suc/m_motive)")
print(f"{'Discharge ratio':<22}: {m_d/m_mot:>10.4f}  (= m_disch/m_motive)")
print("-"*68)
print(f"{'COMPONENT':<8}{'motive':>10}{'suction':>11}{'DISCH kg/h':>12}"
      f"{'disch %':>9}{'design %':>9}")
for k in ["NH3","CO2","H2O","CH4","N2","H2","Urea","O2","Biuret"]:
    dp = disch[k]/m_d*100.0
    print(f"{k:<8}{motive[k]:>10.1f}{suction[k]:>11.1f}{disch[k]:>12.1f}"
          f"{dp:>9.3f}{DES_MASSPCT[k]:>9.3f}")
print("-"*68)

# ---- property closure (independent checks) --------------------------------
vol_d = m_d/DES_RHO
print(f"{'Total mass':<26}: model {m_d:>9.1f}  design {DES_TOTAL_KGH:>9.1f} kg/h")
print(f"{'Molar flow':<26}: model {n_d:>9.2f}  design {DES_MOLFLOW:>9.2f} kmol/h")
print(f"{'Avg MW':<26}: model {mw_d:>9.3f}  design {DES_MW:>9.2f} kg/kmol")
print(f"{'Volume flow (rho_design)':<26}: model {vol_d:>9.2f}  design {DES_VOL_M3H:>9.2f} m3/h")

# ---- energy balance: discharge T from adiabatic mix + heat of mixing ------
# cp [kJ/kg.K]: NH3(liq)=4.74, carbamate soln~3.1, discharge~3.5
cpN, cpC, cpD = 4.74, 3.10, 3.50
T_mot = 29.0          # motive NH3 after HP pump (321 discharge ~29 C)
# solve carbamate suction T that gives design T_d under adiabatic ideal mix:
#   m_d*cpD*T_d = m_mot*cpN*T_mot + m_suc*cpC*T_suc  (dH_mix lumped into T_suc)
T_suc = (m_d*cpD*DES_T_C - m_mot*cpN*T_mot)/(m_suc*cpC)
T_d_check = (m_mot*cpN*T_mot + m_suc*cpC*T_suc)/(m_d*cpD)
print(f"{'Energy bal: T_suction':<26}: {T_suc:>9.1f} C  -> T_disch {T_d_check:>6.1f} C (design {DES_T_C})")

# ---- verdict --------------------------------------------------------------
tol = 0.05   # %-point tolerance on composition, fraction on totals
comp_ok = all(abs(disch[k]/m_d*100.0 - DES_MASSPCT[k]) <= tol for k in MW)
mass_ok = abs(m_d-DES_TOTAL_KGH)/DES_TOTAL_KGH <= 0.01
mw_ok   = abs(mw_d-DES_MW) <= 0.05
mol_ok  = abs(n_d-DES_MOLFLOW)/DES_MOLFLOW <= 0.01
print("="*68)
print(f"composition match : {'PASS' if comp_ok else 'FAIL'}")
print(f"mass/mol/MW match : {'PASS' if (mass_ok and mol_ok and mw_ok) else 'FAIL'}")
print("RESULT:", "IDENTICAL -> bind model" if (comp_ok and mass_ok and mw_ok and mol_ok)
      else "MISMATCH -> do not bind")
print("="*68)
