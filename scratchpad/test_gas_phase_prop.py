"""Gas-phase proportionality of the two coupled pressure nodes (audit items 2 + 3).

  Item 2  PT-323201 (r323_c003_P) vs gas phase of LV-322501 -> 323C003 (top vapour m_305)
          Self-regulating first-order node.  Steady state P == P_tgt gives the exact law
              dP = K_P * (m_305 - m_305_des) / m_305_des        K_P = R323_C003_P_GAIN = 1.20
          so dP / (fractional gas-phase excess) must equal K_P for every stroke.

  Item 3  PIC-323203 (r3232_e011_P) vs gas phase of LV-323501 -> 323F004 (flash vapour m_701)
          Pure accumulator: dP/dt = K_P*(gen_v011 - m_v011)/3600, gen_v011 = PHIV*in_e011,
          in_e011 >= m_701 = PHI_V701 * m_314, m_314 ~ LV-323501 stroke.
          MAN  -> P ramps, ramp rate proportional to gas-phase excess.
          AUTO -> PIC-323203 integral action returns pv to SP; proportionality carried by op.
"""
import os
import sys

BACKEND = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main  # noqa: E402

s = main.state


_pkt = {}


def settle(n=900):
    global _pkt
    for _ in range(n):
        _pkt = main.step_sim(1.0)


def m305():
    return _pkt["RECIRC_323"]["C003"]["v305_th"] * 1000.0


def m701():
    return _pkt["RECIRC_323"]["F004"]["v701_th"] * 1000.0


print("=" * 78)
print("ITEM 2  PT-323201  vs  gas-phase top vapour m_305  (LV-322501 -> 323C003)")
print("=" * 78)
print("  K_P (R323_C003_P_GAIN) = %.4f   m_305_des = %.2f kg/h"
      % (main.R323_C003_P_GAIN, main.R323_M305_DES))
print()
print("  LV-322501    m_305      frac excess    PT-323201    dP      dP/frac")
print("  " + "-" * 68)

s.LIC_322501["mode"] = "MAN"
s.LIC_322501["op"] = main.LV322501_OPEN_DES
settle(1200)
p_base, m_base = s.r323_c003_P, m305()

for op in (main.LV322501_OPEN_DES, 55.0, 65.0, 75.0, 85.0):
    s.LIC_322501["op"] = op
    settle(1200)
    m, p = m305(), s.r323_c003_P
    frac = (m - main.R323_M305_DES) / main.R323_M305_DES
    dp = p - main.R323_C003_P_BARA
    ratio = dp / frac if abs(frac) > 1e-9 else float("nan")
    print("  %6.1f %%   %8.1f    %+9.5f     %8.4f   %+7.4f   %8.4f"
          % (op, m, frac, p, dp, ratio))

print()
print("=" * 78)
print("ITEM 3  PIC-323203 (r3232_e011_P)  vs  gas-phase flash vapour m_701")
print("=" * 78)
s.LIC_322501["op"] = main.LV322501_OPEN_DES
settle(1200)

# --- MAN: accumulator ramp rate vs gas-phase excess ---
s.PIC_323203["mode"] = "MAN"
s.PIC_323203["op"] = main.R3232_E011_PV_OP_DES
s.LIC_323501["mode"] = "MAN"
s.LIC_323501["op"] = main.R323_LV501_OP_DES
settle(1200)
print("  MAN (PV-323203 frozen at %.1f%%): P ramp rate vs LV-323501 stroke" % main.R3232_E011_PV_OP_DES)
print()
print("  LV-323501    m_701      P(t0)     P(t0+300s)   ramp (bar/300s)")
print("  " + "-" * 66)
for op in (main.R323_LV501_OP_DES, 60.0, 75.0, 90.0):
    s.LIC_323501["op"] = op
    settle(600)
    p0 = s.r3232_e011_P
    settle(300)
    print("  %6.1f %%   %8.1f   %8.4f   %8.4f    %+8.5f"
          % (op, m701(), p0, s.r3232_e011_P, s.r3232_e011_P - p0))

# --- AUTO: op carries the proportionality, pv returns to SP ---
print()
print("  AUTO: PIC-323203 pv -> SP (%.2f bar a); op absorbs the gas-phase load"
      % s.PIC_323203["sp"])
print()
print("  LV-323501    m_701      PIC-323203 pv    sp      op %")
print("  " + "-" * 62)
s.PIC_323203["mode"] = "AUTO"
s.LIC_323501["op"] = main.R323_LV501_OP_DES
settle(2000)
for op in (main.R323_LV501_OP_DES, 60.0, 75.0, 90.0):
    s.LIC_323501["op"] = op
    settle(2500)
    print("  %6.1f %%   %8.1f      %8.4f    %6.2f   %6.2f"
          % (op, m701(), s.r3232_e011_P, s.PIC_323203["sp"], s.PIC_323203["op"]))
