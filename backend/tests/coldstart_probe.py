"""
§6.4 cold-start transient acceptance harness (EXTERNAL driver -- does NOT edit the engine).
Reproduces a synthesis-loop pressurization from a cold, empty, depressurized loop with the
design feed lineup held ON (the "feed-on step"), records PT-329201 (s.p_syn_bara), and
identifies an FOPTD using the MODEL-FREE Smith two-point method (no least-squares fit that
can be biased by an assumed model shape):

    tau = 1.5 * (t63 - t28),   t_d = t63 - tau = 1.5*t28 - 0.5*t63

where t28 / t63 are the times to reach 28.3% / 63.2% of the total step span (P0 -> P_f).
P_f is the mean of the last 15 samples (settled plateau, robust to sample noise).

Acceptance (report Section 6.4, DCS-anchored FOPTD band, dcs_anchor_dynamics Section 1.2):
    tau_sim in [2884, 4055] s,  t_d,sim <= 572 s,  P_f in [137.5, 150.5] barg.

Conservation / bit-exactness are untouched: this only sets initial conditions on a fresh State
and calls the public step_sim(). No engine constant is modified.

Run from backend/:  python tests/coldstart_probe.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main

ATM = 1.01325  # bar, bara -> barg

# ---------- 0. baseline: fresh boot design hold must stay pinned (sanity) ----------
p0_hold = main.state.p_syn_bara
for _ in range(20):
    main.step_sim(0.5)
p1_hold = main.state.p_syn_bara
print(f"[baseline] design-hold p_syn: {p0_hold:.6f} -> {p1_hold:.6f} bara  (|d|={abs(p1_hold-p0_hold):.2e})")

# ---------- 1. cold-start initial conditions ----------
main.state = main.State()          # fresh design state
s = main.state

P0_BARG = 5.7                      # field PT-329201 initial (03-06 anchor, report Key numbers)
s.p_syn_bara = P0_BARG + ATM      # cold depressurized loop
# empty the three HP liquid inventories that drive m_loop_frac (the PT floor) + the loop
s.react_level_pct   = 0.0
s.react_lt322504_pct= 0.0
s.react_m_liq       = main.reactor.M_HOLDUP_MIN
s.react_m_in_lag    = 0.0
s.react_fwd_wash    = 0.0
s.hpcc_level_pct    = 0.0
s.strip_level       = 0.0
s.scrub_holdup_kg   = 0.0
s.scrub_level_pct   = 0.0
# fresh transport-delay buffers (feed-on step starts the FEED_TD_S dead time clean)
s.tlag = {}
# feed lineup stays at the design seed = feed ON: pumpB on, XV_321901/322901 open, XV_322902 open.

# ---------- 2. run + record ----------
DT      = 0.5           # s, Euler-stable sub-step (== STEP_CAP)
T_END   = 16000.0       # s, extended so the slow (57.8 min) loop fully plateaus before P_f is read
SAMPLE  = 30.0          # s
t = 0.0; next_s = 0.0
ts = []; ps = []
while t < T_END:
    main.step_sim(DT)
    t += DT
    if t >= next_s:
        ts.append(t); ps.append(s.p_syn_bara)
        next_s += SAMPLE

# ---------- 3. Smith two-point model-free FOPTD identification ----------
P0 = ps[0]
Pf = sum(ps[-15:]) / 15.0                 # settled plateau = mean of last 15 samples
span = Pf - P0

def t_cross(frac):
    """Linear-interpolated time at which P first reaches P0 + frac*span."""
    target = P0 + frac * span
    for i in range(1, len(ps)):
        if ps[i] >= target:
            # interpolate between sample i-1 and i
            p_lo, p_hi = ps[i-1], ps[i]
            t_lo, t_hi = ts[i-1], ts[i]
            if p_hi == p_lo:
                return t_hi
            return t_lo + (target - p_lo) / (p_hi - p_lo) * (t_hi - t_lo)
    return float('nan')                   # never reached (should not happen if plateaued)

t28 = t_cross(0.283)
t63 = t_cross(0.632)
tau_f = 1.5 * (t63 - t28)
td_f  = t63 - tau_f                        # == 1.5*t28 - 0.5*t63

print(f"[coldstart] P0={P0-ATM:.2f} barg  Pf={Pf-ATM:.2f} barg ({Pf:.3f} bara)  n={len(ts)}")
print("\n=== Smith two-point FOPTD ID ===")
print(f"  t28  = {t28:.1f} s   (28.3% of span)")
print(f"  t63  = {t63:.1f} s   (63.2% of span)")
print(f"  t_d  = {td_f:.1f} s")
print(f"  tau  = {tau_f:.1f} s")
print(f"  P_f  = {Pf-ATM:.2f} barg")

print("\n=== Section 6.4 acceptance ===")
g1 = 2884.0 <= tau_f <= 4055.0
g2 = td_f <= 572.0
g3 = 137.5 <= (Pf-ATM) <= 150.5
print(f"  tau in [2884,4055]  : {'PASS' if g1 else 'FAIL'}  ({tau_f:.0f})")
print(f"  t_d <= 572          : {'PASS' if g2 else 'FAIL'}  ({td_f:.0f})")
print(f"  P_f in [137.5,150.5]: {'PASS' if g3 else 'FAIL'}  ({Pf-ATM:.1f})")
print(f"  OVERALL             : {'PASS' if (g1 and g2 and g3) else 'FAIL'}")

# trajectory dump (coarse) for inspection
print("\n=== trajectory (barg) ===")
for i in range(0, len(ts), max(1, len(ts)//24)):
    print(f"  t={ts[i]:6.0f}s  P={ps[i]-ATM:7.2f} barg")
