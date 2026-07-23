"""TD-014 -- open-loop step test of the two Unit-324 evaporator temperature loops.

Fixing the degenerate energy ODE gave 324E001/324E003 a real process gain for the first time.  Their
TIC tuning (Kc = 2.0 bar/C, Ti = 120 s) was inherited from a plant whose gain was IDENTICALLY ZERO,
so it carries no information -- and in closed loop it now diverges (measured: T_e003 walks to 138.5
and PV-329212 to 86.6 % in 6 h).  This measures the gain properly instead of guessing at it.

Method: master TIC to MAN, step its output (the chest-pressure demand the slave PIC tracks), record
the melt temperature to steady state.  Reports K_p [C per bar of demand] and the 63 % time.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main as M  # noqa: E402

DT = 1.0
s = M.state


def settle(n):
    for _ in range(n):
        M.step_sim(DT)


def steptest(tic, tag, T_attr, step_bar, warm_s=3600, run_s=5400):
    tic["mode"] = "MAN"
    settle(warm_s)
    T0 = getattr(s, T_attr)
    op0 = tic["op"]
    tic["op"] = op0 + step_bar
    traj = []
    for k in range(run_s):
        M.step_sim(DT)
        traj.append(getattr(s, T_attr))
    T1 = traj[-1]
    K = (T1 - T0) / step_bar
    tgt = T0 + 0.632 * (T1 - T0)
    t63 = next((i for i, v in enumerate(traj)
                if (v >= tgt if T1 > T0 else v <= tgt)), len(traj))
    print("%s: op %.4f -> %.4f bar   T %.5f -> %.5f C" % (tag, op0, tic["op"], T0, T1))
    print("   K_p = %+10.2f C per bar of chest-pressure demand    t63 = %d s" % (K, t63))
    print("   trajectory @ 300 s steps:",
          " ".join("%.4f" % traj[i] for i in range(0, run_s, 900)))
    tic["op"] = op0
    tic["mode"] = "AUTO"
    settle(1800)
    return K, max(t63, 1)


print("=== 324E003 (Evaporator II, 97.71 % urea, 0.131 bar a) ===")
K3, t3 = steptest(s.TIC_324002, "TIC-324002", "r324_e003_T", 0.002)
print()
print("=== 324E001 (Evaporator I, 94.31 % urea, 0.33 bar a) ===")
K1, t1 = steptest(s.TIC_324001, "TIC-324001", "r324_e001_T", 0.002)
print()
print("lambda tuning for a velocity PI, lambda = 3*tau (robust/slow):")
for tag, K, tau, cur in (("TIC-324002", K3, t3, 2.0), ("TIC-324001", K1, t1, 2.0)):
    if abs(K) > 1e-9:
        Kc = tau / (abs(K) * 3.0 * tau)
        print("   %s  K_p=%+9.2f  tau=%5ds  ->  Kc = %.5f  (currently %.2f, factor %.0f)"
              % (tag, K, tau, Kc, cur, cur / max(Kc, 1e-12)))
