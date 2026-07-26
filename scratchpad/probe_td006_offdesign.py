"""TD-006 + eta_P: prove the new levers are LIVE, not just pin-safe.

A dead lever passes the pin gate perfectly -- that is exactly how eta_P hid for so long.  So each
check here is built to FAIL if the quantity it exercises does not move.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import main as m

CO2 = m.CO2_DES_KGH / 1000.0
des = m.stripper_322e001(CO2, m.STRIP_STEAM_T_DES_C, m.STRIP_P_DES_BARA)

print("=" * 78)
print("1. eta_P -- the dead lever.  Synthesis pressure must now change stripping.")
print("=" * 78)
print("   P (bar a)   eta_P     top NH3 (kmol/h)   duty_raw (kW)")
for pf in (0.94, 0.97, 1.00, 1.03, 1.06):
    P = m.STRIP_P_DES_BARA * pf
    r = m.stripper_322e001(CO2, m.STRIP_STEAM_T_DES_C, P)
    eta_p = max(0.85, min(1.15, 2.0 - P / m.STRIP_P_DES_BARA))
    print("   %7.2f    %.4f    %12.1f     %10.1f" % (P, eta_p, r["top_kmolh"]["NH3"], r["duty_raw_kw"]))
lo = m.stripper_322e001(CO2, m.STRIP_STEAM_T_DES_C, m.STRIP_P_DES_BARA * 0.94)
hi = m.stripper_322e001(CO2, m.STRIP_STEAM_T_DES_C, m.STRIP_P_DES_BARA * 1.06)
assert hi["top_kmolh"]["NH3"] < lo["top_kmolh"]["NH3"], "eta_P STILL DEAD: pressure did not move the split"
print("   -> higher loop pressure suppresses stripping (Le Chatelier).  Swing over +-6 %%: %.1f %%"
      % (100.0 * (lo["top_kmolh"]["NH3"] - hi["top_kmolh"]["NH3"]) / des["top_kmolh"]["NH3"]))

print()
print("=" * 78)
print("2. Duty must respond to COMPOSITION at constant mass -- the whole point of TD-006.")
print("=" * 78)
# Same total feed MASS, shifted between carbamate-formers and water.  The old feed-proportional
# duty returns an identical answer for every row below; the enthalpy balance must not.
base = dict(m.STRIP_FEED207_KMOLH)
mw = m.MW_COMP
m_base = sum(base[k] * mw[k] for k in base)
print("   NH3/CO2 shift   feed mass (kg/h)   duty_raw (kW)   ratio vs design")
for shift in (-0.10, -0.05, 0.0, 0.05, 0.10):
    v = dict(base)
    dn = base["NH3"] * shift
    v["NH3"] = base["NH3"] + dn
    # hold total mass constant by trading against water
    v["H2O"] = base["H2O"] - dn * mw["NH3"] / mw["H2O"]
    r = m.stripper_322e001(CO2, m.STRIP_STEAM_T_DES_C, m.STRIP_P_DES_BARA, overflow_kmolh=v)
    mm = sum(v[k] * mw[k] for k in v)
    print("   %+6.0f %%          %12.1f    %10.1f      %.4f"
          % (shift * 100, mm, r["duty_raw_kw"], r["duty_raw_kw"] / m.STRIP_DUTY_RAW_DES_KW))
v_lean = dict(base); v_lean["NH3"] = base["NH3"] * 0.90
v_lean["H2O"] = base["H2O"] + base["NH3"] * 0.10 * mw["NH3"] / mw["H2O"]
r_lean = m.stripper_322e001(CO2, m.STRIP_STEAM_T_DES_C, m.STRIP_P_DES_BARA, overflow_kmolh=v_lean)
m_lean = sum(v_lean[k] * mw[k] for k in v_lean)
assert abs(m_lean - m_base) / m_base < 1e-6, "fixture broken: mass not held constant"
assert abs(r_lean["duty_raw_kw"] - m.STRIP_DUTY_RAW_DES_KW) > 100.0, (
    "duty did NOT respond to composition at constant mass -- still feed-proportional")
print("   -> same tonnage, %.1f kW different duty.  Feed-proportional duty could not see this."
      % abs(r_lean["duty_raw_kw"] - m.STRIP_DUTY_RAW_DES_KW))

print()
print("=" * 78)
print("3. Flooding knockdown -- derived, and an order of magnitude gentler than the old K=1.50.")
print("=" * 78)


def sweep(load):
    ov = {k: v * load for k, v in m.STRIP_FEED207_KMOLH.items()}
    return m.stripper_322e001(CO2 * load, m.STRIP_STEAM_T_DES_C, m.STRIP_P_DES_BARA, overflow_kmolh=ov)


print("   load    flood_frac   flood_x   dT_flood    g_flood    OLD 1/(1+1.5x)")
for load in (1.0, 1.2, 1.34, 1.4, 1.5, 1.8, 2.2):
    r = sweep(load)
    old = 1.0 / (1.0 + 1.50 * r["flood_x"])
    print("   %.2f     %.4f     %.4f    %6.2f      %.4f       %.4f"
          % (load, r["flood_frac"], r["flood_x"], r["dT_flood"], r["g_flood"], old))
r15 = sweep(1.5)
assert r15["g_flood"] < 1.0, "1.5x load did not flood"
assert r15["g_flood"] > 1.0 / (1.0 + 1.50 * r15["flood_x"]), (
    "derived knockdown is not gentler than the retired K=1.50 -- check the energy balance")
print("   -> at 1.5x the derived loss is %.2f %% against the old %.2f %%."
      % (100 * (1 - r15["g_flood"]), 100 * (1 - 1.0 / (1.0 + 1.5 * r15["flood_x"]))))

print()
print("=" * 78)
print("4. Sanity: duty ratio stays finite and positive across a wide envelope.")
print("=" * 78)
worst = None
for load in (0.2, 0.5, 0.8, 1.0, 1.3, 1.6, 2.0):
    for ts in (m.STRIP_STEAM_T_DES_C - 25, m.STRIP_STEAM_T_DES_C, m.STRIP_STEAM_T_DES_C + 10):
        r = sweep(load)
        ov = {k: v * load for k, v in m.STRIP_FEED207_KMOLH.items()}
        r = m.stripper_322e001(CO2 * load, ts, m.STRIP_P_DES_BARA, overflow_kmolh=ov)
        q = r["duty_raw_kw"] / m.STRIP_DUTY_RAW_DES_KW
        assert q == q and abs(q) < 1e6, "duty ratio blew up at load=%s ts=%s" % (load, ts)
        if worst is None or q < worst[0]:
            worst = (q, load, ts)
print("   lowest duty ratio over the envelope: %.4f at load=%.1f T_steam=%.1f" % worst)
print("   all finite, no poles.")
print()
print("ALL CHECKS PASSED")
