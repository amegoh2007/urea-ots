"""AGENT C Q2: (a) does the plant HOLD the 100 % design point in operation (not just at boot)?
                (b) does PT-329201 actually move on turndown, or only the reactor P constant?"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state if hasattr(main, "state") else main.STATE
DT = 0.1
DES = {
 "m_775 (FIC-328404)": (lambda: main.R328_D001_M775_DES*(s.FIC_328404["op"]/main.R328_D001_FIC404_OP_DES), main.R328_D001_M775_DES),
 "m_931 (FIC-329401)": (lambda: main.R328_C004_M931_DES*(s.FIC_329401["op"]/50.0), main.R328_C004_M931_DES),
 "m_744 (FIC-328402)": (lambda: main.R3232_E003_M744_DES*(s.FIC_328402["op"]/50.0), main.R3232_E003_M744_DES),
 "m_402 (FIC-323402)": (lambda: main.R3232_E011_M402_DES*(s.FIC_323402["op"]/50.0), main.R3232_E011_M402_DES),
 "TIC-328008 op":      (lambda: s.TIC_328008["op"], main.R328_D001_M775_DES),
 "FFIC ratio pv":      (lambda: s.FFIC_329401["pv"], main.R328_FFIC_RATIO_DES),
 "CompI holdup":       (lambda: s.a328_d003_MI, None),
}
print("--- (a) 100 % design hold, untouched, 3600 s ---")
base = {k: fn() for k,(fn,_) in DES.items()}
print(f"TIC-328008  sp={s.TIC_328008['sp']:.6f}  pv={s.TIC_328008['pv']:.6f}  err={s.TIC_328008['pv']-s.TIC_328008['sp']:+.6f} mol%")
for k in (36000,):
    for _ in range(k): main.step_sim(DT)
print(f"{'quantity':22s} {'design':>12s} {'t=0':>14s} {'t=3600s':>14s} {'drift':>12s}")
for k,(fn,des) in DES.items():
    v = fn()
    d = "" if des is None else f"{v-des:+12.6f}"
    print(f"{k:22s} {(des if des is not None else float('nan')):12.4f} {base[k]:14.6f} {v:14.6f} {d}")
print(f"TIC-328008 after 1 h:  sp={s.TIC_328008['sp']:.6f}  pv={s.TIC_328008['pv']:.6f}  op={s.TIC_328008['op']:.4f} kg/h (design 1675.0)")

print("\n--- (b) PT-329201 vs the reactor P indicator across a 50 % turndown ---")
print(f"{'t_s':>7} {'F_CO2':>7} {'PT329201':>9} {'REACT_P':>9} {'HPCC_L':>7} {'LT322504':>9}")
t = main.step_sim(DT)
for k in range(1, 60001):
    frac = 1.0 - 0.5*min(1.0, (k*DT)/600.0)
    s.F_CO2_raw_th = 54.618*frac
    t = main.step_sim(DT)
    if k % 6000 == 0:
        print(f"{k*DT:7.0f} {s.F_CO2_th:7.2f} {s.p_syn_bara:9.4f} {t['REACT_322R001']['P_bara']:9.3f}"
              f" {t['HPCC_322E002']['LT_322E002']:7.2f} {t['REACT_322R001']['LT_322504']:9.2f}")
