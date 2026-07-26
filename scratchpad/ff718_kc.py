"""Prove the residual 718A limit cycle is a single-loop Kc instability, not coupling.
Perturb 718A off its seed, hold setpoint constant, sweep Kc. Stable Kc => flat.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state
RHO = main.RHO_718_KGM3

for kc_mult in (0.4, 0.2, 0.1, 0.05):
    c = s.FIC_328405
    c["Kc"] = kc_mult * RHO
    # perturb off equilibrium
    c["op"] = main.R3232_FIC405_OP_DES * 1.1
    s.tlag["F_328405"] = main.R3232_M718A_DES * 1.1
    s.tlag.pop("cas718A_f", None)
    amp = 0.0; prev = None
    for i in range(80):
        main.step_sim(1.0)
        if i >= 60:
            if prev is not None:
                amp = max(amp, abs(c["pv"] - prev))
            prev = c["pv"]
    kag = (kc_mult*RHO) * (1.0/6.0) * (main.R3232_M718A_DES/main.R3232_FIC405_OP_DES/RHO)
    print(f"Kc={kc_mult:>4}*rho  Kc*a*g={kag:5.2f}  amp={amp:.5f}  "
          f"{'FLAT' if amp < 1e-3 else 'RINGS'}")
