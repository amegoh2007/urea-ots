"""Regression gate for the PT-323201 two-path gas-load coupling.

Collects under pytest (the gate at the foot asserts every check passed at import) and also runs
standalone:  python backend/test_c003_two_path_pressure.py  prints the per-check report.

The 323C003 rectifier is charged by TWO physically distinct carbamate-gas sources, which the
PFD tabulates separately at 4.1 bar a:

  stream 301   5064.7 m3/h  119 C  MW 26.39   prompt flash across LV-322501
  stream 302   2875.7 m3/h  135 C  MW 21.14   gas evolved in the 323E002 rectifying heater
  stream 305   7677.1 m3/h  119 C  MW 24.92   combined overhead OUT to 323E003

301 + 302 = 7940.4 m3/h enter and 7677.1 leave, so 263.3 m3/h condense on the packed bed
where the 135 C heater gas meets the 119 C reflux.  These tests exist to stop stream 305 --
an OUTLET -- from being used as an inlet driver again, which would make the gas load feed
back on itself and leave neither source independently observable.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c003_pressure_coupling as cp

FAILS = []


def check(name, cond, detail=""):
    if not cond:
        FAILS.append(name)
        print("  [FAIL] %-56s %s" % (name, detail))
    else:
        print("  [PASS] %-56s %s" % (name, detail))


P_DOWN = cp.E003_P_DES_BARA


def tgt(flash, e002, p_down=P_DOWN):
    return cp.c003_pressure_target_bara(flash, e002, p_down)


# --------------------------------------------------------------- PFD design arithmetic
print("\n=== PFD gas-load arithmetic ===")
check("stream 301 is the PFD letdown flash volume",
      cp.C003_Q301_DES_M3H == 5064.7, "%.1f m3/h" % cp.C003_Q301_DES_M3H)
check("stream 302 is the PFD 323E002 heater-gas volume",
      cp.C003_Q302_DES_M3H == 2875.7, "%.1f m3/h" % cp.C003_Q302_DES_M3H)
check("stream 305 is the PFD combined overhead",
      cp.C003_Q305_DES_M3H == 7677.1, "%.1f m3/h" % cp.C003_Q305_DES_M3H)
check("inlet load is 301 + 302, not 305",
      cp.C003_Q_IN_DES_M3H == cp.C003_Q301_DES_M3H + cp.C003_Q302_DES_M3H,
      "%.1f m3/h" % cp.C003_Q_IN_DES_M3H)
check("302 is read from its own PFD row, not 305 - 301",
      abs(cp.C003_Q302_DES_M3H - (cp.C003_Q305_DES_M3H - cp.C003_Q301_DES_M3H)) > 100.0,
      "302=%.1f, 305-301=%.1f" % (cp.C003_Q302_DES_M3H,
                                  cp.C003_Q305_DES_M3H - cp.C003_Q301_DES_M3H))
check("bed condensation closes the inlet/outlet difference",
      abs(cp.C003_BED_CONDENSATION_DES_M3H
          - (cp.C003_Q_IN_DES_M3H - cp.C003_Q305_DES_M3H)) < 1e-9,
      "%.1f m3/h (%.2f %% of inlet)" % (
          cp.C003_BED_CONDENSATION_DES_M3H,
          cp.C003_BED_CONDENSATION_DES_M3H / cp.C003_Q_IN_DES_M3H * 100.0))
check("gas-load coefficient reproduces the design pressure",
      abs(math.sqrt(P_DOWN ** 2
                    + (cp.C003_Q_IN_DES_M3H / cp.C003_GAS_LOAD_COEFF_M3H_PER_BAR) ** 2)
          - cp.C003_P_DES_BARA) < 1e-12)


# ------------------------------------------------------------------- design fixed point
print("\n=== design fixed point ===")
check("both ratios 1.0 gives exactly 4.1 bar a", tgt(1.0, 1.0) == cp.C003_P_DES_BARA,
      "%.17g" % tgt(1.0, 1.0))


# ------------------------------------------------------------- independence of the paths
print("\n=== the two paths are independent ===")
D = 1.0e-3
slope_flash = (tgt(1.0 + D, 1.0) - tgt(1.0 - D, 1.0)) / (2.0 * D)
slope_e002 = (tgt(1.0, 1.0 + D) - tgt(1.0, 1.0 - D)) / (2.0 * D)
check("more LV-322501 flash gas raises the pressure", slope_flash > 1.0,
      "dP/dr = %.4f bar per unit ratio" % slope_flash)
check("more 323E002 heater gas raises the pressure on its own", slope_e002 > 0.0,
      "dP/dr = %.4f bar per unit ratio" % slope_e002)
check("the 323E002 path moves pressure with the flash path held at design",
      tgt(1.0, 1.5) > tgt(1.0, 1.0) > tgt(1.0, 0.5),
      "%.4f > %.4f > %.4f" % (tgt(1.0, 1.5), tgt(1.0, 1.0), tgt(1.0, 0.5)))
check("the flash path moves pressure with 323E002 held at design",
      tgt(1.5, 1.0) > tgt(1.0, 1.0) > tgt(0.5, 1.0),
      "%.4f > %.4f > %.4f" % (tgt(1.5, 1.0), tgt(1.0, 1.0), tgt(0.5, 1.0)))
check("the two loads genuinely add",
      tgt(2.0, 2.0) > tgt(2.0, 1.0) and tgt(2.0, 2.0) > tgt(1.0, 2.0),
      "both=%.4f flash=%.4f e002=%.4f" % (tgt(2.0, 2.0), tgt(2.0, 1.0), tgt(1.0, 2.0)))
check("losing 323E002 duty entirely still leaves the flash path charging",
      tgt(1.0, 0.0) > P_DOWN, "%.4f bar a" % tgt(1.0, 0.0))
check("shutting LV-322501 entirely still leaves the heater charging",
      tgt(0.0, 1.0) >= P_DOWN, "%.4f bar a" % tgt(0.0, 1.0))


# ------------------------------------------------------------------ field-trend gradient
print("\n=== 2025-06-28 startup-trend LV sensitivity ===")
step = 1.0e-3
ratio_step = step / cp.C003_LV_OPEN_DES_PCT
slope_pct = (tgt(1.0 + ratio_step, 1.0) - tgt(1.0 - ratio_step, 1.0)) / (2.0 * step)
# The 0.10-0.13 band read off that trend is the STARTUP RAMP, not a process gain.  Regressing
# the trend's own 721 rows: whole startup (LV 0.00-45.40 %) slope +0.0980 bar/%, r = +0.983;
# near design (LV 35-50 %, n = 373) slope -0.0099 bar/%, r = -0.072.  At load the field data
# shows no dependence, which is what the closed gas balance produces -- a few hundredths of a
# bar, the hydraulic slope, because 323E003 absorbs the extra gas.
check("LV sensitivity is the hydraulic slope, not the ramp correlation",
      0.015 <= slope_pct <= 0.035, "%.6f bar per %% opening" % slope_pct)


# ---------------------------------------------------------------------- guards / floors
print("\n=== guards ===")
check("no gas load at all collapses to the downstream node",
      tgt(0.0, 0.0) == P_DOWN, "%.4f bar a" % tgt(0.0, 0.0))
check("the target never falls below the downstream pressure",
      all(tgt(f, e) >= P_DOWN
          for f in (0.0, 0.25, 0.5, 1.0, 2.0) for e in (0.0, 0.25, 0.5, 1.0, 2.0)))
for bad in ((math.nan, 1.0), (1.0, math.inf), (-0.01, 1.0), (1.0, -0.01)):
    try:
        tgt(*bad)
        check("rejects %r" % (bad,), False, "no ValueError raised")
    except ValueError:
        check("rejects %r" % (bad,), True)
try:
    cp.c003_pressure_target_bara(1.0, 1.0, 0.0)
    check("rejects a nonpositive downstream pressure", False, "no ValueError raised")
except ValueError:
    check("rejects a nonpositive downstream pressure", True)


# ------------------------------------------------------ 323E011 saturating condensation
print("\n=== 323E011 vent generation ===")
check("design gas load vents the PFD stream-702 rate",
      cp.e011_vent_generation_kgh(cp.E011_GAS_FEED_DES_KGH) == 440.0,
      "%.1f kg/h" % cp.e011_vent_generation_kgh(cp.E011_GAS_FEED_DES_KGH))
check("gas above the fixed capacity is vented one-for-one",
      cp.e011_vent_generation_kgh(cp.E011_GAS_FEED_DES_KGH + 1000.0) == 1440.0)
check("gas below the capacity is fully condensed",
      cp.e011_vent_generation_kgh(cp.E011_GAS_FEED_DES_KGH - 1000.0) == 0.0)
for bad in (math.nan, math.inf, -0.01):
    try:
        cp.e011_vent_generation_kgh(bad)
        check("e011 rejects %r" % (bad,), False, "no ValueError raised")
    except ValueError:
        check("e011 rejects %r" % (bad,), True)

def test_c003_two_path_pressure_regression_gate():
    """pytest entry point -- every check above must have passed at import."""
    assert not FAILS, "failing checks: " + ", ".join(FAILS)


if __name__ == "__main__":
    print("\n=== %d FAIL(S) ===" % len(FAILS) if FAILS else "\n=== ALL CHECKS PASS ===")
    for f in FAILS:
        print("  - " + f)
    raise SystemExit(1 if FAILS else 0)
