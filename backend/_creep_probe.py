# Derivative-creep regression (Path B, step 4): fresh design-seed State, step the live loop,
# measure |d(state)/dt| of every dynamic inventory/ratio.  Zero creep <=> reconciled HMB is a
# true stationary fixed point of the LIVE model (not just the static node audit).  READ-ONLY probe.
import main as M

# fresh design seed (discard import-time warm-up transient)
M.state = M.State()

KEYS = ["scrub_holdup_kg", "scrub_level_pct",
        "react_m_liq", "react_m_liq_shadow", "react_level_pct", "react_lt322504_pct",
        "react_W_rec", "react_L_rec", "react_conv_fac",
        "hpcc_level_pct", "strip_level", "p_syn_bara",
        "react_T_overflow", "react_T_offgas"]

def snap():
    return {k: float(getattr(M.state, k)) for k in KEYS}

dt = 0.1                      # min per tick
N_settle = 0                  # measure from the RAW design seed (no settle) -> initial creep
N_steps  = 50

s0 = snap()
for _ in range(N_steps):
    M.step_sim(dt)
s1 = snap()

T = N_steps * dt
print("="*92)
print("DERIVATIVE-CREEP REGRESSION  (fresh design-seed State; %d steps x dt=%.2f min = %.1f min)" % (N_steps, dt, T))
print("="*92)
print("  %-22s %16s %16s %16s" % ("state", "t=0", "t=%.1f" % T, "d/dt (per min)"))
print("  " + "-"*74)
worst = 0.0; worst_k = ""
for k in KEYS:
    v0 = s0[k]; v1 = s1[k]; rate = (v1 - v0) / T
    rel = abs(rate) / (abs(v0) + 1e-12)
    if rel > worst:
        worst = rel; worst_k = k
    print("  %-22s %16.8f %16.8f %16.3e" % (k, v0, v1, rate))
print("  " + "-"*74)
print("  WORST relative drift: %s  |d/dt|/|v0| = %.3e per min" % (worst_k, worst))

# also report the live HPCC-feed W/L ratios that the reconciliation targeted
try:
    pk = M.last_packet
    print("\n  (last_packet keys present: %d)" % len(pk))
except Exception as e:
    print("  last_packet:", e)
