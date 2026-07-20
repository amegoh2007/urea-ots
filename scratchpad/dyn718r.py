"""Acceptance test for the PFD re-derivation of the 323D011 / 328D003 network.

Supersedes ff718_perturb.py, which kicked FIC-328405 as if it were the 718A leg.
FIC-328405 is now PFD stream 793 (a normally-closed ammonia-water spare off the
328D003 Comp-I discharge header) and 718A is the UNMETERED REMAINDER of the
LIC-323503 total draw: a pure _lag1 with no controller of its own.

Horizons are set by the loops' own dynamics, not by taste:
  * LIC-323503 is PI on an integrating level, wn = 5.0e-3 rad/s, zeta = 0.30
    (main.py LIC_323503 seed comment), so the settling envelope is
        exp(-zeta*wn*t)  ->  tau = 1/(zeta*wn) = 667 s,  ~4*tau = 2700 s.
    Anything shorter measures the tail of the transient, not the steady state.
  * 328D003 Comp I has NO level controller (deferred item 3a) but IS self-regulating,
    because the 735 draw is proportional to the holdup:  m_735 = m735_des*MI/MI_des.
    A step export D on that vessel therefore relaxes first-order:
        MI(t) = MI_des - dMI_ss*(1 - exp(-t/tau_I)),
        dMI_ss = MI_des*D/m735_des,      tau_I = 3600*MI_des/m735_des = 16 100 s.
    Gate 3 checks the trajectory against that closed form instead of demanding a
    settle the vessel physically cannot reach inside a test run.

Conservation is measured as the DERIVATIVE OF THE HOLDUP, dM/dt*3600, not from the
telemetry m_kgh fields -- those round to 1 dp, which is 40x coarser than the drift
being judged.
"""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main as M

s = M.state
RHO401 = M.RHO_401_KGM3
FAIL = 0


def chk(name, got, want, tol, fmt="11.4f"):
    global FAIL
    ok = abs(got - want) <= tol
    FAIL += 0 if ok else 1
    print(f"  {'OK  ' if ok else 'FAIL'} {name:<30s} got {got:{fmt}}   want {want:{fmt}}  (+-{tol})")


def c005(t):
    return t["LPCC_3232"]["C005"]


def run(n, dt=0.1):
    for _ in range(n):
        t = M.step_sim(dt)
    return t


# ---- gate 1 : design hold ---------------------------------------------------
print("gate 1 - design hold (3600 s, > 4*tau of LIC-323503)")
M0 = s.r3232_e011_M
t = run(30000)
c = c005(t)
m718A, m718B = s.tlag["F_718A"], c["FIC_323418"]["m_kgh"]
chk("D011 dM/dt (kg/h)", (s.r3232_e011_M - M0) / 3600.0 * 3600.0, 0.0, 0.10)
chk("LIC-323503 level (%)", s.LIC_323503["pv"], s.LIC_323503["sp"], 1e-4)
chk("718A remainder (kg/h)", m718A, M.R3232_M718A_DES, 0.5)
chk("718B slipstream (kg/h)", m718B, M.R3232_M718B_DES, 0.5)
chk("718 total (kg/h)", m718A + m718B, M.R3232_D011_M718_DES, 1.0)
chk("793 spare (kg/h)", c["FIC_328405"]["m_kgh"], M.S793_M_DES, 0.01)
chk("Comp-I holdup (kg)", s.a328_d003_MI, M.A328_D003_MI_DES, 1.0)

# ---- gate 2 : remainder damping after a level kick --------------------------
print("\ngate 2 - 323D011 inventory kicked +5 % (6000 s, ~9*tau)")
s.r3232_e011_M *= 1.05
peak = s.LIC_323503["pv"]
for i in range(60000):
    t = M.step_sim(0.1)
    peak = max(peak, s.LIC_323503["pv"])
    if i in (0, 6000, 30000, 59999):
        print(f"    t={(i+1)*0.1:7.1f}s  lvl={s.LIC_323503['pv']:8.4f}%  "
              f"718A={s.tlag['F_718A']:8.2f}  718B={c005(t)['FIC_323418']['m_kgh']:8.2f} kg/h")
ampA = ampB = 0.0
pA, pB = s.tlag["F_718A"], c005(t)["FIC_323418"]["m_kgh"]
for _ in range(300):                                     # residual-cycle window, 30 s
    t = M.step_sim(0.1)
    ampA = max(ampA, abs(s.tlag["F_718A"] - pA))
    ampB = max(ampB, abs(c005(t)["FIC_323418"]["m_kgh"] - pB))
    pA, pB = s.tlag["F_718A"], c005(t)["FIC_323418"]["m_kgh"]
chk("level recovered to SP (%)", s.LIC_323503["pv"], s.LIC_323503["sp"], 0.05)
chk("overshoot above SP (%)", peak - s.LIC_323503["sp"], 0.0, 5.0)
chk("718A residual cycle (kg/h)", ampA, 0.0, 0.05)       # the old cascade rang 3.18<->3.50 m3/h
chk("718B residual cycle (kg/h)", ampB, 0.0, 0.05)
chk("718 total back on 7123", s.tlag["F_718A"] + c005(t)["FIC_323418"]["m_kgh"],
    M.R3232_D011_M718_DES, 1.0)

# ---- gate 3 : stream 793 opened --------------------------------------------
print("\ngate 3 - FIC-328405 (stream 793) to MAN 50 % vs the first-order closed form")
MI_DES = M.A328_D003_MI_DES
M735 = M.R328_C002_M738_DES
TAU_I = 3600.0 * MI_DES / M735
MI0 = s.a328_d003_MI
s.FIC_328405["mode"] = "MAN"; s.FIC_328405["op"] = 50.0
D = 0.5 * M.S793_CAP_KGH                                  # export at 50 % stroke (kg/h)
dMI_ss = MI_DES * D / M735
print(f"    export D={D:.1f} kg/h   tau_I={TAU_I:.0f} s   dMI_ss={dMI_ss:.1f} kg")
elapsed = 0.0
for horizon in (900.0, 1800.0, 3600.0):
    t = run(int((horizon - elapsed) / 0.1)); elapsed = horizon
    pred = MI0 - dMI_ss * (1.0 - math.exp(-horizon / TAU_I))
    chk(f"Comp-I MI @ {horizon:.0f}s (kg)", s.a328_d003_MI, pred, 0.02 * dMI_ss, fmt="11.1f")
c = c005(t)
chk("793 draw (kg/h)", c["FIC_328405"]["m_kgh"], D, 5.0)
chk("793 volumetric (m3/h)", c["FIC_328405"]["vol_m3h"], D / RHO401, 0.02)
chk("Comp-I finite and positive", 1.0 if s.a328_d003_MI > 1.0 else 0.0, 1.0, 0.0)
print(f"    Comp-I holdup {MI0:.1f} -> {s.a328_d003_MI:.1f} kg, heading for "
      f"{MI0 - dMI_ss:.1f} kg (self-regulating via m_735 ~ MI; finite, no runaway)")

print(f"\nFAILURES {FAIL}")
