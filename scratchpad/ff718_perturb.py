"""Robustness: kick 718A off equilibrium at tick 20, confirm the real code path
(tau_s=45 measurement filter, Kc/Ti untouched) damps it back to flat -- i.e. the
limit cycle is structurally dead, not merely an undisturbed fixed point.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state
RHO = main.RHO_718_KGM3

amp = 0.0; prev = None
for i in range(120):
    if i == 20:  # 10% kick on 718A actuator + measurement store
        s.FIC_328405["op"] *= 1.10
        s.tlag["F_328405"] *= 1.10
    main.step_sim(1.0)
    a = s.FIC_328405
    if i >= 100:  # measure residual cycle long after the kick
        if prev is not None:
            amp = max(amp, abs(a["pv"] - prev))
        prev = a["pv"]
    if i in (19, 21, 25, 40, 60, 119):
        print(f"tick {i:3d}  718A_pv={a['pv']:.5f}  718B_pv={s.FIC_323418['pv']:.5f}  "
              f"sum_kgh={a['pv']*RHO + s.FIC_323418['pv']*RHO:9.2f}")
print(f"\nresidual amp ticks 101-119: {amp:.6f} m3/h")
print("RECOVERS FLAT" if amp < 1e-3 else "SUSTAINED CYCLE")
