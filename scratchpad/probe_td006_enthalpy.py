"""TD-006 second half: can a per-species enthalpy balance reproduce the licensor duty?

The whole question is whether the stripper duty can be built from SOURCED constants only.
If a first-principles sum lands near STRIP_DUTY_DES_KW = 39 400 kW with nothing fitted, the
constant set is corroborated and the balance can replace the feed-proportional stand-in.

Constants and where each one comes from:
  * carbamate decomposition   117 kJ/mol   Frejacques, via Brouwer "Thermodynamics of the Urea
                                           Process", UreaKnowHow June 2009, p.12:
                                           CO2(G) + 2 NH3(G) -> NH2COONH4(L), dH = -117 kJ/mol
                                           at 110 atm and 160 C.  The stripper runs the SAME
                                           reaction backwards at 144 bar / 172-183 C.
  * urea hydrolysis           -15.5 kJ/mol same paper, same page: NH2COONH4(L) ->
                                           NH2CONH2(L) + H2O(L), dH = +15.5 kJ/mol at 160-180 C.
                                           Hydrolysis runs it backwards, so -15.5 into carbamate.
  * NH3 desorption            23 kJ/mol    HPCC_BUB_DHVAP_JMOL, already in main.py -- the
                                           NH3-dominated vaporisation enthalpy at synthesis
                                           conditions.  NH3 is SUPERCRITICAL at 183 C (Tc=132.4),
                                           so there is no latent heat; this is the desorption
                                           slope the loop already uses.
  * water latent              steam tables at the stripper's own top-gas temperature
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import main as m

DH_CARB   = 117.0e3     # J/mol CO2 released from carbamate
DH_HYD    = -15.5e3     # J/mol urea hydrolysed (into carbamate; the gas step is counted separately)
DH_NH3    = m.HPCC_BUB_DHVAP_JMOL          # 23 000 J/mol free-NH3 desorption
LAM_H2O   = 36_900.0    # J/mol (HPCC_FLASH_DH["H2O"], 2049 kJ/kg @170 C steam tables)

d = m.stripper_322e001(m.CO2_DES_KGH / 1000.0, m.STRIP_STEAM_T_DES_C, m.STRIP_P_DES_BARA)
feed, top, bot = d["feed_kmolh"], d["top_kmolh"], d["bot_kmolh"]
co2gas = d["co2_feed_kmolh"]          # the CO2 sweep -- enters ALREADY as gas, needs no decomposition

print("design feed  kmol/h :", {k: round(v, 1) for k, v in feed.items() if v})
print("design top   kmol/h :", {k: round(v, 1) for k, v in top.items() if v})
print("CO2 sweep    kmol/h :", {k: round(v, 1) for k, v in co2gas.items() if v})
print("xi_hyd %.3f  xi_biu %.3f  T_bot %.2f  T_top %.2f" %
      (d["xi_hyd"], d["xi_biu"], d["T_bot"], d["T_top"]))

# ---- 1. carbamate decomposition: CO2 that moved from the LIQUID into the gas -------------------
n_co2_desorb = top["CO2"] - co2gas["CO2"]           # kmol/h
q_carb = n_co2_desorb * DH_CARB / 3600.0            # kW  (kmol/h * J/mol == kJ/h)

# ---- 2. free NH3 desorption: overhead NH3 minus the 2:1 carbamate-bound share ------------------
n_nh3_carb   = 2.0 * n_co2_desorb
n_nh3_free   = max(top["NH3"] - co2gas["NH3"] - n_nh3_carb, 0.0)
q_nh3 = n_nh3_free * DH_NH3 / 3600.0

# ---- 3. water vaporised overhead ---------------------------------------------------------------
q_h2o = (top["H2O"] - co2gas["H2O"]) * LAM_H2O / 3600.0

# ---- 4. urea hydrolysis (liquid-phase step only; its gas step is already inside q_carb) --------
q_hyd = d["xi_hyd"] * DH_HYD / 3600.0

# ---- 5. sensible: both products leave at their own temperature, feed arrives at 183 C ----------
m_bot = sum(bot[k] * m.MW_COMP[k] for k in m.MW_COMP)
m_top = sum(top[k] * m.MW_COMP[k] for k in m.MW_COMP)
q_sens_l = m_bot * m.STRIP_CP_BOTTOM * (d["T_bot"] - m.STRIP_FEED207_T_C) / 3600.0
q_sens_g = m_top * m.HPCC_CP_GAS     * (d["T_top"] - m.STRIP_FEED207_T_C) / 3600.0

tot = q_carb + q_nh3 + q_h2o + q_hyd + q_sens_l + q_sens_g
print("\n  CO2 desorbed from liquid : %9.1f kmol/h" % n_co2_desorb)
print("  free NH3 desorbed        : %9.1f kmol/h" % n_nh3_free)
print("\n  q_carb  (carbamate)      : %9.1f kW" % q_carb)
print("  q_nh3   (free NH3)       : %9.1f kW" % q_nh3)
print("  q_h2o   (water latent)   : %9.1f kW" % q_h2o)
print("  q_hyd   (hydrolysis)     : %9.1f kW" % q_hyd)
print("  q_sens  liquid           : %9.1f kW" % q_sens_l)
print("  q_sens  gas              : %9.1f kW" % q_sens_g)
print("  " + "-" * 42)
print("  TOTAL                    : %9.1f kW" % tot)
print("  licensor STRIP_DUTY_DES  : %9.1f kW" % m.STRIP_DUTY_DES_KW)
print("  ratio                    : %9.4f  (%.2f %% of licensor)" %
      (tot / m.STRIP_DUTY_DES_KW, 100.0 * tot / m.STRIP_DUTY_DES_KW))
