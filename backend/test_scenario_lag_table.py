"""Regression gate for the inter-vessel process-transport layer and Scenarios4 lag bands.

Plain asserts (repo has no pytest). Run:  python backend/test_scenario_lag_table.py
"""
import math
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main
import consequence as cq

FAILS = []


def check(name, cond, detail=""):
    if not cond:
        FAILS.append(name)
        print("  [FAIL] %s %s" % (name, detail))
    else:
        print("  [PASS] %s" % name)


# ---------------------------------------------------------------- route geometry
print("\n=== five principal product routes ===")
ROUTES = ("322E001_TO_323C003", "323C003_TO_323F004", "323F004_TO_323F010",
          "323F010_TO_323D002", "323D002_TO_324E001")
check("PROCESS_ROUTES contains exactly five entries", set(main.PROCESS_ROUTES) == set(ROUTES))

PIPE_ID_MM = 187.1
LENGTHS_M = [25.0, 15.0, 15.0, 30.0, 40.0]
DENSITIES = [1150.0, 1140.0, 1145.0, 1151.0, 1151.0]
CARRIERS = [main.R323_FEED_DES_KGH, main.R323_M314_DES, main.R323_M319_DES,
            main.R323_M317_DES, main.R324_FEED_DES]

for i, (nm, length_m, rho, carrier) in enumerate(zip(ROUTES, LENGTHS_M, DENSITIES, CARRIERS)):
    route = main.PROCESS_ROUTES[nm]
    vol_m3 = cq.pipe_volume_m3(PIPE_ID_MM, length_m)
    td_computed = cq.transport_time_s(vol_m3, carrier, rho)
    td_route = route.dead_time_s(route.design_carrier_kgh)
    inv_route = route.line_inventory_kg
    inv_computed = route.design_carrier_kgh * td_computed / 3600.0

    check("%s dead_time_s matches transport_time_s" % nm,
          abs(td_route - td_computed) < 0.1,
          "route=%.2f s, computed=%.2f s" % (td_route, td_computed))
    check("%s line_inventory_kg matches V*rho" % nm,
          abs(inv_route - inv_computed) < 1.0,
          "route=%.1f kg, computed=%.1f kg" % (inv_route, inv_computed))
    check("%s 0 < td < 3600 s" % nm, 0.0 < td_route < 3600.0, "%.2f s" % td_route)
    check("%s inventory > 0 kg" % nm, inv_route > 0.0, "%.1f kg" % inv_route)


# ------------------------------------------------------------- FIFO no-early-arrival
print("\n=== FIFO packet staleness (no early arrival) ===")
ROUTE = ROUTES[0]
carrier = main.PROCESS_ROUTES[ROUTE].design_carrier_kgh
td_design = main.PROCESS_ROUTES[ROUTE].dead_time_s(carrier)
st = SimpleNamespace(tlag={})
base = main._cq_packet(carrier, 165.0, {"Urea": 0.55, "H2O": 0.30, "NH3": 0.10, "CO2": 0.05}, 2.6)
step = main._cq_packet(carrier, 185.0, {"Urea": 0.62, "H2O": 0.26, "NH3": 0.08, "CO2": 0.04}, 2.6)

arr = main._transport_process(st, ROUTE, base, carrier, 1.0)
check("boot seeds buffer (arrival == departure)", arr == base)

for _ in range(5):
    arr = main._transport_process(st, ROUTE, step, carrier, 1.0)
check("stale 5 s after step (td=%.1f s)" % td_design, arr == base)

for _ in range(25):
    arr = main._transport_process(st, ROUTE, step, carrier, 1.0)
check("fresh 30 s after step", arr == step)


# ---------------------------------------------------------- Scenarios4 lag-time bands
print("\n=== Scenarios4 deduced lag-time bands ===")
# Steam Header Pressure: θp 1-3 s, τp 30-90 s
check("steam header pressure capacitance (gas-space) 1-3 s",
      1.0 <= main.R323_C003_P_TAU_S <= 3.0, "%.1f s" % main.R323_C003_P_TAU_S)
check("flash-drum pressure relaxation (vapour) 30-90 s",
      30.0 <= main.R323_F004_P_TAU_S <= 90.0, "%.1f s" % main.R323_F004_P_TAU_S)

# Reactor Thermal Profile: θp 30-60 s, τp 8-360 min
check("reactor forward washout time constant 8-360 min",
      8.0 <= main.REACT_FWD_TAU_MIN <= 360.0, "%.1f min" % main.REACT_FWD_TAU_MIN)
check("reactor thermal (exotherm) time constant 8-360 min",
      8.0 <= main.REACT_THERM_TAU_MIN <= 360.0, "%.1f min" % main.REACT_THERM_TAU_MIN)
check("reactor total residence 8-360 min",
      8.0 <= main.REACT_TAU_TOT_MIN <= 360.0, "%.1f min" % main.REACT_TAU_TOT_MIN)

# Stripper Liquid Level: θp 5-10 s, τp 60-120 s
check("scrubber seal-leg level integrator 60-120 s",
      60.0 <= main.SCRUB_LVL_TAU_S <= 120.0, "%.1f s" % main.SCRUB_LVL_TAU_S)

# Material-path transport: cumulative dead time across the 323/324 train
total_td = sum(main.PROCESS_ROUTES[nm].dead_time_s(main.PROCESS_ROUTES[nm].design_carrier_kgh)
               for nm in ROUTES)
check("total 322E001->324E001 transport dead time > 2 min",
      total_td > 120.0, "%.1f s" % total_td)


# ------------------------------------------------ packet indivisibility (T + comp together)
print("\n=== packet indivisibility ===")
# Mass, temperature and composition all ride one frozen packet, so no observer can ever see
# one of them updated while another still holds the previous parcel's value.
st2 = SimpleNamespace(tlag={})
p0 = main._cq_packet(carrier, 165.0, {"Urea": 0.55, "H2O": 0.45}, 2.6)
p1 = main._cq_packet(carrier * 1.10, 175.0, {"Urea": 0.60, "H2O": 0.40}, 2.6)
main._transport_process(st2, ROUTE, p0, carrier, 1.0)

onset_m = onset_T = onset_w = None
for i in range(1, 61):
    a = main._transport_process(st2, ROUTE, p1, carrier, 1.0)
    if onset_m is None and a.mass_kgh != p0.mass_kgh:
        onset_m = i
    if onset_T is None and a.temperature_c != p0.temperature_c:
        onset_T = i
    if onset_w is None and a.mass_fraction != p0.mass_fraction:
        onset_w = i

check("mass, temperature and composition arrive on the same tick",
      onset_m is not None and onset_m == onset_T == onset_w,
      "mass=%s temp=%s comp=%s" % (onset_m, onset_T, onset_w))
check("that tick is the route dead time, not tick 1",
      onset_m is not None and abs(onset_m - td_design) <= 2.0,
      "onset=%s s, td=%.2f s" % (onset_m, td_design))

# A halved carrier flow must double the transit time (td = rho*V / m_dot, not a tuned constant).
r0 = main.PROCESS_ROUTES[ROUTE]
check("dead time doubles when carrier flow halves",
      abs(r0.dead_time_s(carrier * 0.5) - 2.0 * td_design) < 0.1,
      "%.2f s vs %.2f s" % (r0.dead_time_s(carrier * 0.5), 2.0 * td_design))
check("dead time halves when carrier flow doubles",
      abs(r0.dead_time_s(carrier * 2.0) - 0.5 * td_design) < 0.1,
      "%.2f s vs %.2f s" % (r0.dead_time_s(carrier * 2.0), 0.5 * td_design))

print("\n=== %d FAIL(S) ===" % len(FAILS) if FAILS else "\n=== ALL CHECKS PASS ===")
for f in FAILS:
    print("  - " + f)
raise SystemExit(1 if FAILS else 0)
