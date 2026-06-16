"""probe_steam_integration.py  --  TEMPORARY integrated steam-handshake proof.

Proves the steam_system <-> main.py wiring:
  1. Import succeeds  -> boot-pin (_pin_hpcc_ua, 18000 warm-up ticks) still runs with steam active.
  2. Design bit-exactness  -> at the seeded steady state the stripper shell sat-steam temperature
     is byte-identical to STRIP_STEAM_T_DES_C (= tsat(19.7)), HPCC product == 170.0 C, and the
     MP/LP headers are stationary (pinned valve coeffs -> net flow ~ 0, no spurious drift).
  3. Handshake  -> dropping the MP supply valve to 0 % decays the MP header pressure, which lowers
     tsat(P_MP) feeding the stripper shell, which drops the stripper BOTTOMS temperature.
"""
import sys
import main

sys.stdout.reconfigure(encoding="utf-8")   # Windows console cp1252 -> allow Δ / em-dash

DT = 0.1

# ---- spy stripper_322e001 to capture its full return (T_bot, T_steam) each tick
_orig_strip = main.stripper_322e001
_rec = {}
def _strip_spy(*a, **k):
    r = _orig_strip(*a, **k)
    _rec["strip"] = r
    return r
main.stripper_322e001 = _strip_spy


def settle(n):
    pkt = None
    for _ in range(n):
        pkt = main.step_sim(DT)
    return pkt


print("=" * 64)
print("  INTEGRATED STEAM-HANDSHAKE PROBE  (steam_system <-> main)")
print("=" * 64)
print(f"  import OK -> HPCC_UA pinned = {main.HPCC_UA:.1f} kJ/h.K  (boot-pin survived steam wiring)")
print(f"  pinned steam coeffs: K_SUPPLY={__import__('steam_system').K_SUPPLY:.4f}  "
      f"M_USERS_LP={__import__('steam_system').M_USERS_LP:.4f} kg/s")

# ---------------------------------------------------------------- 1. design steady state
main.state = main.State()
s = main.state
print(f"\n  seed: P_MP={s.steam.P_MP}  P_LP={s.steam.P_LP}  "
      f"supply={s.steam.valve_supply_pct}%  letdown={s.steam.valve_letdown_pct}%")

# tick 1: stripper shell T must be bit-exact (P_MP still at seed during this tick's forward pass)
main.step_sim(DT)
t_steam_t1 = _rec["strip"]["T_steam"]
print(f"\n  [tick 1] stripper shell T_steam = {t_steam_t1!r}")
print(f"           STRIP_STEAM_T_DES_C    = {main.STRIP_STEAM_T_DES_C!r}")
assert t_steam_t1 == main.STRIP_STEAM_T_DES_C, \
    f"BIT-EXACT FAIL: stripper steam T {t_steam_t1} != design {main.STRIP_STEAM_T_DES_C}"
print("           -> bit-exact at design forward pass. OK")

pkt = settle(2000)                                   # 200 s hold on the STABLE MAN design plateau.
#   (Free-running MAN drains the NH3 inventory and trips 21_2 ~tick 6500 — a pre-existing process
#    behaviour, independent of steam: frozen-steam == pre-steam. We assert stationarity on the
#    pre-trip plateau, where the HPCC duty is flat and the pinned headers hold a true fixed point.)
s = main.state
base_pmp   = s.steam.P_MP
base_plp   = s.steam.P_LP
base_tbot  = _rec["strip"]["T_bot"]
base_tt010 = pkt["HPCC_322E002"]["TT_322010"]
print(f"\n  [200 s] P_MP={base_pmp:.4f}  P_LP={base_plp:.4f}  "
      f"T_steam={_rec['strip']['T_steam']:.3f}  T_bot={base_tbot:.3f}")
print(f"           HPCC TT_322010 = {base_tt010}  (design pin 170.0)")
print(f"           STEAM_SYSTEM.MP={pkt['STEAM_SYSTEM']['MP']}")
print(f"           STEAM_SYSTEM.LP={pkt['STEAM_SYSTEM']['LP']}")

# headers stationary at design (pinned coeffs -> true fixed point); allow only numerical residue
assert abs(base_pmp - main.STRIP_STEAM_P_BARA) < 0.15, f"MP header drifted at design: {base_pmp}"
assert abs(base_plp - main.HPCC_STEAM_P_BARA) < 0.15, f"LP header drifted at design: {base_plp}"
assert abs(base_tt010 - 170.0) < 0.2, f"HPCC product temp off design pin: {base_tt010}"
print("           -> headers stationary, HPCC pin intact. OK")

# ---------------------------------------------------------------- 2. drop MP supply -> 0 %
main.handle_cmd({"type": "steam_supply_set", "op": 0.0})
print(f"\n  COMMAND: steam_supply_set op=0  -> valve_supply_pct={s.steam.valve_supply_pct}")

print(f"\n  {'t [s]':>8}{'P_MP':>10}{'T_steam':>10}{'T_bot':>10}")
traj = []
for k in range(2000):                                # 200 s — handshake transient is FAST (supply=0 ->
    pkt = main.step_sim(DT)                          #   dP_MP/dt ~= -(m_strip+m_ld)/C_MP ~= -1 bar/s),
    if k % 200 == 0:                                 #   craters in ~20 s, long before the 21_2 trip.
        traj.append((round(k * DT, 0), round(main.state.steam.P_MP, 3),
                     round(_rec["strip"]["T_steam"], 2), round(_rec["strip"]["T_bot"], 2)))
for t, p, ts, tb in traj:
    print(f"  {t:>8}{p:>10}{ts:>10}{tb:>10}")

s = main.state
fin_pmp  = s.steam.P_MP
fin_ts   = _rec["strip"]["T_steam"]
fin_tbot = _rec["strip"]["T_bot"]
print(f"\n  final: P_MP={fin_pmp:.3f}  T_steam={fin_ts:.2f}  T_bot={fin_tbot:.2f}")

assert fin_pmp < base_pmp - 1.0, \
    f"FAIL: MP header did not decay (base {base_pmp:.2f} -> {fin_pmp:.2f})"
assert fin_tbot < base_tbot - 1.0, \
    f"FAIL: stripper bottoms T did not drop (base {base_tbot:.2f} -> {fin_tbot:.2f})"

print("\n" + "=" * 64)
print(f"  PASS: supply 0% -> P_MP {base_pmp:.2f}->{fin_pmp:.2f} bar  "
      f"(Δ{fin_pmp-base_pmp:+.2f})")
print(f"        stripper bottoms T_bot {base_tbot:.2f}->{fin_tbot:.2f} C  "
      f"(Δ{fin_tbot-base_tbot:+.2f})")
print("        Handshake proven: header decay propagates to stripper bottoms temperature.")
print("=" * 64)
