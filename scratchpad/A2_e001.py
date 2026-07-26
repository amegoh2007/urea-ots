"""AGENT A (2nd pass) -- 322E001 HP stripper: is the HV-322605 move a real energy balance
or a mass-routing cheat?  Plus the MP-steam boundary.

Method: back-solve an effective latent heat lambda_eff at the DESIGN point so that
    Q_req = m_bot*cp*(T_bot - T_feed) + m_top*(cp*(T_top - T_feed) + lambda_eff)
equals the design shell duty STRIP_DUTY_DES_KW.  Then perturb HV-322605 and report the
duty the products DEMAND versus the duty the model actually charges the MP header.
"""
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa
s = main.state if hasattr(main, "state") else main.STATE
DT = 0.5
CP = 2.5   # kJ/kg.K urea/carbamate liquor (order-of-magnitude, used only for the RATIO argument)

def settle(n):
    for _ in range(n): main.step_sim(DT)

def strip_now():
    """Re-evaluate the stripper block with the CURRENT tear state (no side effects)."""
    return main.stripper_322e001(s.F_CO2_th, main.tsat_steam(s.steam.P_MP),
                                 main.STRIP_P_DES_BARA,
                                 overflow_kmolh=s.react_overflow_kmolh,
                                 L_feed=s.react_L_feed, W_feed=s.react_W_feed)

settle(600)
st = strip_now()
T_feed = main.REACT_OVERFLOW_T_C
m_top = st["top_kgh"]; m_bot = st["bot_kgh"]; m_feed = st["m_feed_kgh"]
Qdes  = main.STRIP_DUTY_DES_KW
lam = (Qdes*3600.0 - m_bot*CP*(st["T_bot"]-T_feed) - m_top*CP*(st["T_top"]-T_feed)) / m_top
print(f"DESIGN: m_feed={m_feed:9.1f}  m_top={m_top:9.1f}  m_bot={m_bot:9.1f}  "
      f"T_bot={st['T_bot']:.2f}  T_top={st['T_top']:.2f}")
print(f"        back-solved lambda_eff = {lam:.1f} kJ/kg  (closes Q=39400 kW at design)")

def qreq(st):
    return (m_b_cp := st["bot_kgh"]*CP*(st["T_bot"]-T_feed)
            + st["top_kgh"]*(CP*(st["T_top"]-T_feed) + lam))/3600.0

print("\n   HIC605  m_feed(kg/h)  m_top    m_bot    T_bot    T_top   eta_T   "
      "Q_required(kW)  Q_charged(kW)  MP_draw(kg/s)  P_MP   LT322504  strip_lvl")
rows = []
for hic in (60.0, 70.0, 85.0, 100.0, 40.0, 20.0):
    s.HIC_322605 = hic
    settle(1200)                     # 10 min per step
    tel = main.step_sim(DT)
    st = strip_now()
    mstrip = main.STRIP_DUTY_DES_KW/1850.0
    print(f"   {hic:5.0f}  {st['m_feed_kgh']:11.0f} {st['top_kgh']:8.0f} {st['bot_kgh']:8.0f} "
          f"{st['T_bot']:8.2f} {st['T_top']:7.2f} {st['eta_T']:7.4f}  "
          f"{qreq(st):12.0f}  {main.STRIP_DUTY_DES_KW:12.0f}  {mstrip:12.3f}  "
          f"{s.steam.P_MP:6.3f}  {s.react_lt322504_pct:7.1f}  {s.strip_level:7.1f}")
    rows.append((hic, st['m_feed_kgh'], qreq(st)))

print("\nNOTE Q_charged is the literal constant  Q_strip_kjh = STRIP_DUTY_DES_KW*3600  (main.py:3414)")
print("     -> MP steam draw m_strip is INVARIANT to stripper load by construction.")

# --- shell-side check: does the MP header even notice a stripper flood? ---
print(f"\nP_MP after the whole sweep = {s.steam.P_MP:.4f} bar a (design 19.7)")
print(f"valve_supply_pct = {s.steam.valve_supply_pct:.3f}")
