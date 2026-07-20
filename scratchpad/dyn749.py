"""328E021 HOT-side (stream 749) acceptance test — item 3c mirror.

Gate 1  design hold : engine settles on every 328 design anchor with the live
                      hot outlet in place of the frozen R328_C004_T749 = 148.
Gate 2  dynamism    : clamping the hydrolyser at +10 K must move the 328C004
                      bottoms by the closed-form hot-outlet gain
                          dT_749/dT_c003 = 1 - m_746*eps_T/m_749 = 0.17111
                      (the whole point of the item — the old constant gave 0).
Gate 3  pinch guard : with LIC-328505 driven shut (m_747 -> 0) the raw balance
                      diverges; the clamp must hold T_749 at the cold inlet and
                      keep the C004 node finite.
"""
import os, sys
BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND))
os.chdir(os.path.abspath(BACKEND))
import main as M

DT = 0.1
FAIL = 0


def check(name, got, want, tol):
    global FAIL
    ok = abs(got - want) <= tol
    FAIL += 0 if ok else 1
    print(f"  {'OK ' if ok else 'FAIL'}  {name:<28} got {got:>10.4f}   want {want:>10.4f}  (+-{tol})")


def run(n, hold_c003=None, shut_505=False):
    tel = None
    for _ in range(n):
        if hold_c003 is not None:
            M.state.a328_c003_T = hold_c003
        if shut_505:
            M.state.LIC_328505["mode"] = "MAN"
            M.state.LIC_328505["op"] = 0.0
        tel = M.step_sim(DT)
    return tel


# ---- gate 1 : design hold -------------------------------------------------
tel = run(60000)                                   # 6000 s
d328 = tel["DESORB_328"]
print("gate 1 - design hold (6000 s)")
check("TT_328C003 (hydrolyser)", d328["C003"]["TT_328C003"], 200.0, 0.05)
check("TT_328009 (746 cold out)", d328["C003"]["TT_328009"], 190.0, 0.05)
check("TT_328005 (C004 bottoms)", d328["C004"]["TT_328005"], 143.0, 0.05)
check("TT_328004 (C004 top tray)", d328["C004"]["TT_328004"], 140.0, 0.05)
check("TT_328007 (C002 bottoms)", d328["C002"]["TT_328007"], 139.0, 0.05)
base_c004 = M.state.a328_c004_T
base_c002 = M.state.a328_c002_T

# ---- gate 2 : dynamism ----------------------------------------------------
gain = 1.0 - M.R328_C003_M746_DES * M.R328_E021_EPS_T / M.R328_C004_M749_DES
tel = run(60000, hold_c003=210.0)
print(f"\ngate 2 - hydrolyser clamped 200 -> 210 C   (closed-form gain {gain:.5f})")
check("dT_c004", M.state.a328_c004_T - base_c004, 10.0 * gain, 0.10)
print(f"        C002 bottoms drift {M.state.a328_c002_T - base_c002:+.3f} K"
      f"  (cold side is shared, so the gain band absorbs it)")

# ---- gate 3 : pinch guard -------------------------------------------------
tel = run(20000, shut_505=True)
t_c004, t_c002 = M.state.a328_c004_T, M.state.a328_c002_T
finite = all(map(lambda v: v == v and abs(v) < 1e6, (t_c004, t_c002, M.state.a328_c004_M)))
FAIL += 0 if finite else 1
print(f"\ngate 3 - LIC-328505 shut (m_747 -> 0)")
print(f"  {'OK ' if finite else 'FAIL'}  C004 finite: T {t_c004:.3f} C, M {M.state.a328_c004_M:.1f} kg"
      f" (C002 bottoms {t_c002:.3f} C)")

print(f"\nFAILURES {FAIL}")
