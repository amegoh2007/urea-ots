"""AGENT A probe 4 -- HV-322605 -> 322E001: closed energy balance, or mass-routing cheat?

Opens HV-322605 from 60 % to 100 % and to 20 %, and each time reports:
   * stripper feed mass (m_feed_kgh)  -- the mass surge that HV-322605 routes
   * TT-322004 T_bot, TT-322013 T_top
   * the MP steam mass the model actually DRAWS for the stripper
   * a first-law check on the tube side:
        Q_needed = m_feed*cp*(T_bot - T_feed_in) + sum(xi_decomp)*dH_carb  [kW]
     vs Q_supplied = m_steam * lambda_MP  [kW]
   If Q_supplied is a fixed constant while Q_needed swings, the "energy balance" is a correlation.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa
s = main.state if hasattr(main, "state") else main.STATE
DT = 0.5
CP = main.STRIP_CP_BOTTOM
LAM_MP = 1850.0                      # kJ/kg, the model's own MP latent heat (main.py:3416)
DH_CARB = main.SCRUB_DH_CARB_KJMOL   # kJ/mol carbamate formation (decomposition = -this)

print("STRIP_DUTY_DES_KW =", main.STRIP_DUTY_DES_KW, "  STRIP_STEAM_KGH_DES =", main.STRIP_STEAM_KGH_DES)
print("Q_strip_kjh in step_sim is hardcoded  STRIP_DUTY_DES_KW*3600  (main.py:3414)\n")


def row(tag, t):
    S = t["STRIP_322E001"]
    R = t["REACT_322R001"]
    st = main.stripper_322e001(s.F_CO2_th, main.tsat_steam(s.steam.P_MP), main.STRIP_P_DES_BARA,
                               overflow_kmolh=s.react_overflow_kmolh,
                               L_feed=s.react_L_feed, W_feed=s.react_W_feed)
    m_feed = st["m_feed_kgh"]
    T_in = R["TT_322005"]                       # reactor top / overflow feed T
    # CO2 stripped overhead (kmol/h) -> carbamate decomposition endotherm proxy
    n_co2_top = st["top_kmolh"]["CO2"]
    Q_sens = m_feed / 3600.0 * CP * (st["T_bot"] - T_in) / 1000.0            # kW
    Q_dec = n_co2_top * 1000.0 * DH_CARB / 3600.0                            # kW (decomposition endotherm)
    Q_need = Q_sens + Q_dec
    m_steam_kgh = main.STRIP_DUTY_DES_KW * 3600.0 / LAM_MP                   # what the model draws
    Q_sup = m_steam_kgh / 3600.0 * LAM_MP                                     # == STRIP_DUTY_DES_KW
    print(f"{tag:22s} HIC605={s.HIC_322605:6.1f}%  LT504={R['LT_322504']:6.1f}%  "
          f"m_feed={m_feed:10.0f} kg/h  T_bot={st['T_bot']:7.2f}  T_top={st['T_top']:7.2f}  "
          f"eta_T={st['eta_T']:6.4f}  || Q_need={Q_need:9.0f} kW (sens {Q_sens:8.0f} + dec {Q_dec:8.0f})  "
          f"Q_sup={Q_sup:8.0f} kW  m_MP={m_steam_kgh:8.0f} kg/h  MISMATCH={Q_need - Q_sup:+9.0f} kW")


t = main.step_sim(DT)
row("design phi=60", t)

for target, secs in ((100.0, 1800.0), (60.0, 1800.0), (20.0, 1800.0)):
    s.HIC_322605 = target
    n = int(secs / DT)
    for k in range(n):
        t = main.step_sim(DT)
        if k in (int(60 / DT), int(600 / DT), n - 1):
            row(f"phi={target:.0f} t={k*DT:6.0f}s", t)
    print()
