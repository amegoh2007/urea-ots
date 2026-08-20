"""PHASE-5 BOUNDED FOREGROUND AUDIT  --  321P002 A/B HP NH3 Feed Pumps (ISOLATED).

Re-evaluates the triplex (3-plunger) reciprocating PD pumps + their feed-drum (321D003) integrator
in isolation (pure-function calls + bounded single-state ODE checks; no full synthesis-loop settle).

PIN-BASIS NOTE: unlike 322E002/322F001, the pump FUNCTIONS (pump_flow_m3h / pump_shaft_power_kW /
pump_current_A) are STATELESS pure functions of nameplate constants -- there is NO pump-function live
pin.  The settled EJ_MOTIVE_DES_LIVE=40751.3 is the INTEGRATED-LOOP settled motive (tank level +
cascade + controller), not a pump-function anchor.  So the pump-function laws are audited on pure
nominal constants; the stateful paths (cascade demand split, 321D003 tank mass/energy ODE) are audited
as BOUNDED single-state checks (replicating the exact step_sim recurrence), never a coupled full settle.

Sections:
  A. PD flow law + design anchors : Q == N*V_rev*eta_v*60 linear; mass t/h == Q*rho/1000;
                                    dT_pump bit-exact == EJ_MOTIVE_T_DES_C reconstruction (Domino: pump
                                    thermal -> ejector motive temp -> TT-322012); DCS current anchor 43.9A@131rpm.
  B. Cascade inversion / n_active : rpm_req<->open_cas<->flow round-trip bit-exact; 1- vs 2-pump demand
                                    split; n_active==0 div-0 guard (max(n,1)); rpm clamp.
  C. Shaft power law              : P == Q*dP/eta_m; proportional in rpm & dP; ==0 at rpm 0.
  D. 321D003 tank mass+energy ODE : LIC-321501 SS import==draw zero-offset (level held at SP bit-exact);
                                    off-SP P+FF restore to SP, no rail; energy relax to T_BL; suction-head
                                    P_suct law + suct_open gate; psat NH3 + PDY subcooling margin > 0.
  E. Bounds + directive-#2 domino : rpm>=0 / current floor 0.2 / pump-off -> flow 0 / disch-shut -> motive 0
                                    -> ejector phi_m->0 (composition domino); finite over full grid.
Run:  python backend/tests/audit_p002_pumps.py
"""
import os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import main
from main import (MW_COMP, clamp, ejector_322f001, psat_nh3_bara,
                  pump_flow_m3h, pump_shaft_power_kW, pump_current_A,
                  PUMP_V_PER_REV, PUMP_ETA_V, PUMP_ETA_M, PUMP_RATED_RPM, PUMP_RATED_I,
                  PUMP_NORMAL_RPM, NH3_RHO, G, M_NH3, M_CO2, NC_TO_MASS,
                  TANK_VOL, TANK_H, TANK_LEVEL_SP_FRAC, TANK_LIC_KP_TH, TANK_BL_MAX_TH,
                  P_SYN_DOWN_BAR, P_ATM_BAR, T_BL_FEED_C, CP_NH3, BETA_NH3, ETA_PUMP_HYD,
                  EJ_MOTIVE_T_DES_C, EJ_MOTIVE_NH3_DES, EJ_CARB_FRAC, EJ_MOTIVE_DES_LIVE)

fails = []
def chk(cond, msg):
    print("   [%s] %s" % ("PASS" if cond else "FAIL", msg))
    if not cond: fails.append(msg)

# Exact step_sim helpers (replicated bit-for-bit from main.step_sim, NOT re-derived) -----------------
def p_suct_barG(level, p_top_barG=12.3, suct_open=True):
    if not suct_open: return 0.0
    return p_top_barG + (NH3_RHO * G * level * TANK_H) / 1e5 - 0.15
def dT_pump(level, T_tank_C, p_top_barG=12.3, disch_open=True, on=True):
    if not (on and disch_open): return 0.0
    dP_pa = max(0.0, P_SYN_DOWN_BAR - (p_suct_barG(level, p_top_barG) + P_ATM_BAR)) * 1e5
    T_K   = T_tank_C + 273.15
    return dP_pa / (NH3_RHO * CP_NH3) * (BETA_NH3 * T_K + (1.0 - ETA_PUMP_HYD) / ETA_PUMP_HYD)
def cascade_open(F_NH3_sp_th, n_active):
    Q_total = F_NH3_sp_th * 1000.0 / NH3_RHO
    Q_pp    = Q_total / max(n_active, 1)
    rpm_req = Q_pp / (PUMP_V_PER_REV * PUMP_ETA_V * 60.0)
    return clamp(rpm_req / PUMP_RATED_RPM * 100.0, 0.0, 100.0), rpm_req
def settle_tank(L0, F_pump_th, n, dt=0.5, p_top=12.3):
    L = L0
    for _ in range(n):
        F_in  = clamp(F_pump_th + TANK_LIC_KP_TH * (TANK_LEVEL_SP_FRAC - L), 0.0, TANK_BL_MAX_TH)
        dm_kg = (F_in - F_pump_th) * 1000.0 / 3600.0 * dt
        L = clamp(L * TANK_VOL + dm_kg / NH3_RHO, 0.0, TANK_VOL) / TANK_VOL
    return L
def relax_T(T0, F_in_th, n, dt=0.5, level=0.65):
    T = T0; M = level * TANK_VOL * NH3_RHO; F = F_in_th * 1000.0 / 3600.0
    for _ in range(n):
        if M > 1.0: T += (F * (T_BL_FEED_C - T) / M) * dt
    return T

bar = "=" * 116
print(bar); print("  321P002 A/B HP NH3 FEED PUMPS  --  ISOLATED UNIT AUDIT (Phase 5)"); print(bar)
print("  pure-function basis: NAMEPLATE constants (no pump live pin). V_rev=%.9f m3/rev  rated=%.0f rpm  rho=%.1f"
      % (PUMP_V_PER_REV, PUMP_RATED_RPM, NH3_RHO))
print("  context: integrated-loop settled motive EJ_MOTIVE_DES_LIVE=%.4f kg/h (NOT a pump-fn anchor)"
      % (EJ_MOTIVE_DES_LIVE if EJ_MOTIVE_DES_LIVE is not None else float('nan')))

# ============================================================================================== A
print("\n" + bar); print("  A. PD FLOW LAW + DESIGN ANCHORS  (Domino + design HMB + 100% conservation)"); print(bar)
print("\n   PD flow  Q == N*V_rev*eta_v*60  (linear, zero-intercept):")
flow_ok = mass_ok = True
for N in (0.0, 37.0, 62.0, 124.0, 131.0, 152.0):
    Q = pump_flow_m3h(N); exp = N * PUMP_V_PER_REV * PUMP_ETA_V * 60.0
    flow_ok &= abs(Q - exp) < 1e-9
    mass_ok &= abs(Q * NH3_RHO / 1000.0 - exp * NH3_RHO / 1000.0) < 1e-9
    print("      N=%6.1f rpm | Q=%8.4f m3/h  mass=%7.4f t/h  expect=%8.4f" % (N, Q, Q*NH3_RHO/1000.0, exp))
chk(flow_ok, "Q == N*V_rev*eta_v*60 bit-exact (positive-displacement, linear in rpm)")
chk(mass_ok, "mass t/h == Q*rho/1000 bit-exact (1 pump @124rpm ~ %.3f t/h, near design motive)" % (pump_flow_m3h(124.0)*NH3_RHO/1000.0))
chk(pump_flow_m3h(0.0) == 0.0, "zero rpm -> zero flow (no PD slip term)")
chk(pump_flow_m3h(-50.0) == 0.0, "negative rpm clamped -> zero flow (no reverse delivery)")
# A2 design-thermal anchor: step_sim dT_pump at design suction == EJ_MOTIVE_T_DES_C reconstruction (bit-exact)
T_mot_des = T_BL_FEED_C + dT_pump(TANK_LEVEL_SP_FRAC, T_BL_FEED_C, p_top_barG=12.3)
chk(abs(T_mot_des - EJ_MOTIVE_T_DES_C) < 1e-9,
    "DESIGN dT_pump path: T_BL + dT_pump(L=0.65,T=25) == EJ_MOTIVE_T_DES_C %.6f C bit-exact (pump->ejector motive temp Domino)" % EJ_MOTIVE_T_DES_C)
print("      design pump thermal rise dT=%.4f K -> motive temp %.4f C (feeds 322F001 -> TT-322012)" % (T_mot_des-T_BL_FEED_C, T_mot_des))
chk(dT_pump(0.65, 25.0) > dT_pump(0.65, 25.0, p_top_barG=40.0), "dT_pump falls as suction P rises (smaller dP across pump)")
# A3 motor current DCS anchor
chk(abs(pump_current_A(131.0, True) - 43.95) < 0.1, "current DCS anchor: I(131rpm,on) == 43.9 A (= 86%% rated, datasheet)")
chk(abs(pump_current_A(PUMP_RATED_RPM, True) - PUMP_RATED_I) < 1e-9, "current at rated rpm == PUMP_RATED_I %.1f A" % PUMP_RATED_I)

# ============================================================================================== B
print("\n" + bar); print("  B. CASCADE INVERSION / n_active SPLIT  (SIC-321950/951 demand -> rpm)"); print(bar)
print("\n   round-trip: F_NH3_sp -> open_cas -> speed_act -> flow  (must recover demand exactly):")
rt_ok = True
for F_sp in (20.0, 40.0, 60.0, 81.0):
    for n in (1, 2):
        opn, rpm_req = cascade_open(F_sp, n)
        speed_act = opn / 100.0 * PUMP_RATED_RPM
        Q_pp_recovered = pump_flow_m3h(speed_act) * NH3_RHO / 1000.0
        Q_pp_demand    = F_sp / n
        # exact only when unclamped (open<100): high-demand single-pump cases saturate by design
        if opn < 100.0 - 1e-9:
            rt_ok &= abs(Q_pp_recovered - Q_pp_demand) < 1e-6
        print("      F_sp=%5.1f t/h n=%d | open_cas=%6.2f%%  rpm_req=%6.1f  per-pump recovered=%6.3f demand=%6.3f t/h"
              % (F_sp, n, opn, rpm_req, Q_pp_recovered, Q_pp_demand))
chk(rt_ok, "cascade inversion round-trips bit-exact (unclamped): demand -> open -> rpm -> flow == per-pump demand")
o1, _ = cascade_open(80.0, 1); o2, _ = cascade_open(80.0, 2)
chk(o2 < o1, "2-pump split halves per-pump duty -> lower opening than single-pump for same total demand")
chk(abs(cascade_open(80.0, 1)[1] - 2.0*cascade_open(80.0, 2)[1]) < 1e-9, "single-pump rpm_req == 2 x two-pump rpm_req (load shared equally)")
chk(cascade_open(40.0, 0)[0] == cascade_open(40.0, 1)[0], "n_active==0 guarded by max(n,1) (no div-0; demand sized to 1 pump)")
chk(cascade_open(1e6, 1)[0] == 100.0, "over-demand clamps open_cas to 100%% (rated-speed ceiling)")

# ============================================================================================== C
print("\n" + bar); print("  C. SHAFT POWER LAW  P == Q*dP/eta_m"); print(bar)
print("\n   power vs (rpm, dP):")
pw_ok = True
dP_des = P_SYN_DOWN_BAR - (p_suct_barG(0.65) + P_ATM_BAR)
for (N, dP) in ((124.0, dP_des), (152.0, dP_des), (124.0, dP_des*0.5), (0.0, dP_des)):
    P = pump_shaft_power_kW(N, dP)
    exp = (pump_flow_m3h(N)/3600.0) * dP * 1e5 / PUMP_ETA_M / 1000.0
    pw_ok &= abs(P - exp) < 1e-9
    print("      N=%6.1f dP=%6.2f bar | P=%8.2f kW  expect=%8.2f" % (N, dP, P, exp))
chk(pw_ok, "P == (Q/3600)*dP*1e5/eta_m/1000 bit-exact")
chk(pump_shaft_power_kW(0.0, dP_des) == 0.0, "zero rpm -> zero shaft power (Q=0)")
chk(pump_shaft_power_kW(124.0, dP_des) > 0.0 and abs(pump_shaft_power_kW(124.0, 2*dP_des) - 2*pump_shaft_power_kW(124.0, dP_des)) < 1e-9,
    "power proportional to dP (constant displacement)")
chk(abs(pump_shaft_power_kW(2*124.0, dP_des) - 2*pump_shaft_power_kW(124.0, dP_des)) < 1e-9, "power proportional to rpm (linear flow)")

# ============================================================================================== D
print("\n" + bar); print("  D. 321D003 FEED-DRUM MASS+ENERGY ODE  (LIC-321501, bounded single-state)"); print(bar)
F_des = pump_flow_m3h(PUMP_NORMAL_RPM) * NH3_RHO / 1000.0
print("\n   LIC-321501 mass balance  dM/dt = F_in - F_pump,  F_in = clamp(F_pump + Kp*(SP-L), 0, 90):")
L_ss = settle_tank(TANK_LEVEL_SP_FRAC, F_des, 4000)
chk(abs(L_ss - TANK_LEVEL_SP_FRAC) < 1e-9, "SS at L==SP: import==draw -> level held at SP %.2f bit-exact (zero offset, FF cancels draw)" % TANK_LEVEL_SP_FRAC)
L_lo = settle_tank(0.45, F_des, 8000); L_hi = settle_tank(0.85, F_des, 8000)
chk(abs(L_lo - TANK_LEVEL_SP_FRAC) < 1e-3, "drained start (L0=0.45) restores to SP (P+FF makeup, no permanent offset)")
chk(abs(L_hi - TANK_LEVEL_SP_FRAC) < 1e-3, "flooded start (L0=0.85) drains to SP (no rail at 1.0)")
chk(0.0 <= settle_tank(0.05, F_des, 50) <= 1.0, "level integrator bounded [0,1] (no overshoot past physical drum limits)")
print("      L_ss(from SP)=%.6f  L(from0.45)=%.4f  L(from0.85)=%.4f" % (L_ss, L_lo, L_hi))
print("\n   321D003 energy balance  M*cp*dT/dt = F_in*cp*(T_BL - T):  subcooled NH3 relaxes to BL temp:")
T_relax = relax_T(40.0, F_des, 20000)
chk(abs(T_relax - T_BL_FEED_C) < 0.5, "hot start (40 C) relaxes toward T_BL_FEED %.1f C (adiabatic drum, makeup-driven)" % T_BL_FEED_C)
chk(relax_T(10.0, F_des, 4000) > 10.0, "cold start (10 C) warms toward T_BL (sign correct)")
print("      T(from 40C)=%.3f C  -> T_BL=%.1f" % (T_relax, T_BL_FEED_C))
print("\n   suction-head pressure  PT-321201/202 + subcooling margin PDY:")
chk(p_suct_barG(0.85) > p_suct_barG(0.45), "P_suct rises with tank level (static head term rho*g*L*H)")
chk(p_suct_barG(0.65, suct_open=False) == 0.0, "suct valve shut -> P_suct == 0 (suction-loss trip path)")
PDY = (12.3 + P_ATM_BAR) - psat_nh3_bara(25.0)
chk(PDY > 0.0, "PDY-321203/204 subcooling margin = P_feed(abs) - Psat(25C) = %.2f bar > 0 (liquid, no cavitation)" % PDY)
chk(psat_nh3_bara(60.0) > psat_nh3_bara(25.0), "psat_nh3 monotone-up with T (Antoine, vapour pressure rises)")

# ============================================================================================== E
print("\n" + bar); print("  E. BOUNDS + DIRECTIVE-#2 DOMINO  (pump flow -> ejector phi_m -> composition)"); print(bar)
chk(pump_current_A(0.0, False) == 0.2 and pump_current_A(0.0, True) == 0.2, "current floor 0.2 A (off, and on@0rpm) -> no negative/zero display")
print("\n   pump-total -> motive -> 322F001 entrainment: discharge composition shifts with NH3 delivery:")
base = None; dom_ok = True
for F_tot in (40.756, 30.0, 50.0):
    motive = F_tot * 1000.0
    e = ejector_322f001(motive, EJ_MOTIVE_T_DES_C, 74.0, 1.0)
    if base is None: base = e
    # more motive -> more entrained carbamate (CO2/H2O/etc.) in discharge: every comp scales, NH3 dominates
    dom_ok &= (e["suction_kgh"] > 0.0) and abs(e["comp"]["NH3"] - (motive + e["suction_kgh"]*EJ_CARB_FRAC["NH3"])) < 1e-6
    print("      F_pump=%6.3f t/h | motive=%8.0f -> m_suc=%9.2f  disch CO2=%8.2f  H2O=%8.2f kg/h"
          % (F_tot, motive, e["suction_kgh"], e["comp"]["CO2"], e["comp"]["H2O"]))
chk(dom_ok, "directive #2: pump NH3 delivery sets ejector phi_m -> entrained carbamate -> ALL discharge comps shift (CO2/H2O up with flow)")
e_hi = ejector_322f001(50.0*1000.0, EJ_MOTIVE_T_DES_C, 74.0, 1.0)
e_lo = ejector_322f001(30.0*1000.0, EJ_MOTIVE_T_DES_C, 74.0, 1.0)
chk(e_hi["comp"]["CO2"] > e_lo["comp"]["CO2"] and e_hi["comp"]["H2O"] > e_lo["comp"]["H2O"], "higher pump delivery -> more entrained CO2 & H2O in HP loop (composition domino, not just flow)")
chk(ejector_322f001(0.0, EJ_MOTIVE_T_DES_C, 74.0, 1.0)["total_kgh"] == 0.0, "disch-shut / pump-stop -> motive 0 -> ejector zero flow (no spurious HP loop feed)")
fin_ok = True
for N in (-50.0, 0.0, 62.0, 124.0, 200.0):
    for dP in (0.0, 50.0, dP_des, 300.0):
        fin_ok &= all(math.isfinite(v) for v in (pump_flow_m3h(N), pump_shaft_power_kW(N, dP), pump_current_A(N, True)))
        fin_ok &= pump_flow_m3h(N) >= -1e-12 and pump_shaft_power_kW(N, dP) >= -1e-12
chk(fin_ok, "all pump returns finite & non-negative across rpm x dP grid (no NaN/inf/negative)")

print("\n" + bar)
if fails:
    print("  P002 PUMP AUDIT:  %d CHECK(S) FAILED" % len(fails))
    for m in fails: print("     - " + m)
    raise SystemExit(1)
print("  P002 PUMP AUDIT:  ALL CHECKS PASS  --  synthesis-loop sweep complete (E001->E002->E003->F001->P002)")
print(bar)
