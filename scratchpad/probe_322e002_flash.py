"""TD-007 / AUDIT F-6 probe: the 322E002 (T,P) phase split.

Phase 0  static sweep of _hpcc_flash_split around the calibration point -> monotone? sane band?
Phase A  undisturbed design hold             -> phi must stay on HPCC_FRAC_GAS_DES, no drift
Phase B  CO2 load cut (opens the gate)       -> phi must MOVE, and must not self-excite
Phase C  LP-steam pressure raise             -> t_shell^ -> T_prod^ -> phi^ (was inert before)
"""
import os, sys
_B = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
sys.path.insert(0, _B)
os.chdir(_B)
import main  # noqa: E402

DT = 0.25
KEYS = ("CO2", "NH3", "H2O", "N2")


def run(sec):
    out = None
    for _ in range(int(sec / DT)):
        out = main.step_sim(DT)
    return out


def row(tag, t):
    h, s = t["HPCC_322E002"], main.state
    print(f"{tag:22s} T_prod={s.tlag.get('HPCC_TPROD', 0.0):8.3f}  gas={h['gas_th']:7.2f}"
          f"  liq={h['liq_th']:8.2f}  duty={h['steam']['duty_kW']:8.0f}"
          f"  P_syn={s.p_syn_bara:7.3f}  lvl={s.hpcc_level_pct:6.2f}")


print("=== Phase 0: static EQUILIBRIUM TARGET sweep about the calibration point (170 C, 140.7 bar a) ===")
feed_des = main._HPCC_DES["feed_kmolh"]
print(f"{'':16s}" + "".join(f"{k:>10s}" for k in KEYS))
print(f"{'design phi':16s}" + "".join(f"{main.HPCC_FRAC_GAS_DES[k]:10.4f}" for k in KEYS))
for T in (150.0, 160.0, 170.0, 180.0, 190.0):
    p = main._hpcc_flash_split(feed_des, T, main.SYN_P_DES_BARA)
    print(f"T={T:6.1f} C @des P" + "".join(f"{p[k]:10.4f}" for k in KEYS))
for P in (120.0, 130.0, 140.7, 150.0, 160.0):
    p = main._hpcc_flash_split(feed_des, 175.0, P)
    print(f"P={P:6.1f} b @175C" + "".join(f"{p[k]:10.4f}" for k in KEYS))

print("\n=== Phase A: undisturbed design hold ===")
t = run(300.0); row("A settle 300s", t); a1 = main.state.tlag.get("HPCC_TPROD")
t = run(300.0); row("A settle 600s", t); a2 = main.state.tlag.get("HPCC_TPROD")
print(f"  gate={main._disturbance_gate(main.state):.6f}   T_prod drift={a2 - a1:.3e} C")
print(f"  phi @design == HPCC_FRAC_GAS_DES ? "
      f"{all(t["HPCC_322E002"]["phi_gas"][k] == main.HPCC_FRAC_GAS_DES[k] for k in main.MW_COMP)}")

print("\n=== Phase B: N/C setpoint cut to 92 % (gate opens) ===")
s = main.state
s.ratio_SP = 0.92 * main.RATIO_SP_DES     # N/C setpoint cut: exogenous, in the gate vector
tt = []
for i in range(12):
    t = run(60.0); row(f"B t+{(i + 1) * 60:4d}s", t)
    tt.append(s.tlag.get("HPCC_TPROD"))
print(f"  gate={main._disturbance_gate(s):.4f}   phi_CO2={t["HPCC_322E002"]["phi_gas"]['CO2']:.4f}"
      f" (des {main.HPCC_FRAC_GAS_DES['CO2']:.4f})   phi_NH3={t["HPCC_322E002"]["phi_gas"]['NH3']:.4f}")
print(f"  T_prod last-5 span = {max(tt[-5:]) - min(tt[-5:]):.4f} C   (self-excitation check)")

print("\n=== Phase C: MP-steam supply valve 50 -> 62 % (shell temp up) ===")
main.state = main.State(); t = run(300.0)
g0 = t["HPCC_322E002"]["gas_th"]; p0 = dict(t["HPCC_322E002"]["phi_gas"])
s = main.state
s.steam.pic204_mode = "MAN"            # PIC-329204 AUTO would drag the valve back
s.steam.valve_supply_pct = 62.0
tt = []
for i in range(12):
    t = run(60.0); row(f"C t+{(i + 1) * 60:4d}s", t)
    tt.append(s.tlag.get("HPCC_TPROD"))
print(f"  gate={main._disturbance_gate(s):.4f}")
print(f"  T_prod last-5 span = {max(tt[-5:]) - min(tt[-5:]):.4f} C   (self-excitation check)")
print(f"  gas_th {g0:.2f} -> {t['HPCC_322E002']['gas_th']:.2f}")
for k in KEYS:
    print(f"    phi[{k:>3s}] {p0[k]:.4f} -> {t["HPCC_322E002"]["phi_gas"][k]:.4f}")
