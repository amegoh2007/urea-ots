"""323D011 conservation probe.

The telemetry m_kgh fields round to 1 dp, so a "residual" computed from them is only
meaningful to ~0.1 kg/h.  The structural balance is
    dM/dt = (in_e011 + m_401 - m_v011 - m_718A - m_718B)/3600            (main.py:3980)
so the honest measurement of the net imbalance is the DERIVATIVE OF THE HOLDUP itself:
    resid[kg/h] = (M(t2) - M(t1)) / (t2 - t1) * 3600
That is exact to machine precision and needs no rounded telemetry at all.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(B); sys.path.insert(0, B)
import main as M
s = M.state

print(f"seed M = {s.r3232_e011_M!r}   (design {M.R3232_D011_M_DES!r})")
prev = s.r3232_e011_M
for i in range(180000):                                   # 18 000 s
    t = M.step_sim(0.1)
    if (i + 1) % 6000 == 0:
        now = s.r3232_e011_M
        print(f"  t={(i+1)*0.1:8.0f}s  M={now:.9f} kg  dM/dt={(now-prev)/600.0*3600.0:+.6f} kg/h"
              f"  lvl={s.LIC_323503['pv']:.8f}%  718A={s.tlag['F_718A']:.4f}"
              f"  718B={t['LPCC_3232']['C005']['FIC_323418']['m_kgh']:.1f}")
        prev = now
print(f"\nnet holdup change over 18 000 s: {s.r3232_e011_M - M.R3232_D011_M_DES:+.6e} kg")
