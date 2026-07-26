import sys
sys.path.insert(0, r"D:\Work\Urea Simulation\backend")
import main

fails = 0
def chk(name, cond, got=None, exp=None):
    global fails
    if not bool(cond):
        fails += 1
        print(f"FAIL {name}: got={got} exp={exp}")
    else:
        print(f"ok   {name}: got={got}")

def settle(n=1200, dt=0.5):
    snap = None
    for _ in range(n):
        snap = main.step_sim(dt)
    return snap["ABSORB_328"]["C001"]

CPL_DES  = main.A328_CPL_DES        # 1750
T_DES    = main.A328_C001_T         # 43
M756_DES = main.A328_M756_DES       # 33358
ABS_DES  = main.A328_ABS_DES        # 130
conc_des = ABS_DES / M756_DES * 100.0   # 0.39

# ---- 1) DESIGN STEADY STATE : sump holds 43 C, dM=0, cpl=1750, conc=design ----
c = settle()
chk("cpl_kgh @design == 1750",  round(c["cpl_kgh"], 0) == round(CPL_DES, 0), c["cpl_kgh"], CPL_DES)
chk("TT_322015 @design ~ 43",   abs(c["TT_322015"] - T_DES) < 0.3, c["TT_322015"], T_DES)
chk("LI_322502 @design ~ 50",   abs(c["LI_322502"] - 50.0) < 1.0, c["LI_322502"], 50.0)   # dM=0 -> level held
chk("liquor756 @design ~ 33.36",abs(c["liquor756_th"] - M756_DES/1000.0) < 0.2, c["liquor756_th"], round(M756_DES/1000.0,2))
chk("make_conc @design ~ 0.39", abs(c["make_conc_pct"] - conc_des) < 0.03, c["make_conc_pct"], round(conc_des,2))

# ---- 2) DYNAMIC : raise condensate 1750 -> 2600 ; downstream MUST respond ----
main.handle_cmd({"type": "cpl_set", "value": 2600.0})
c_hi = settle()
chk("cpl_kgh tracks 2600",       round(c_hi["cpl_kgh"], 0) == 2600.0, c_hi["cpl_kgh"], 2600.0)
chk("liquor756 rises (LIC opens)", c_hi["liquor756_th"] > c["liquor756_th"] + 0.3, c_hi["liquor756_th"], f"> {c['liquor756_th']}")
chk("make_conc dilutes",         c_hi["make_conc_pct"] < c["make_conc_pct"] - 0.005, c_hi["make_conc_pct"], f"< {c['make_conc_pct']}")
chk("sump re-settles dM~0",      abs(c_hi["LI_322502"] - 50.0) < 3.0, c_hi["LI_322502"], "~50")
chk("temp stays bounded (no trip)", c_hi["TT_322015"] < 50.0, c_hi["TT_322015"], "< 50")

# ---- 3) DYNAMIC : lower condensate 2600 -> 900 ; opposite direction ----
main.handle_cmd({"type": "cpl_set", "value": 900.0})
c_lo = settle()
chk("cpl_kgh tracks 900",        round(c_lo["cpl_kgh"], 0) == 900.0, c_lo["cpl_kgh"], 900.0)
chk("liquor756 falls",           c_lo["liquor756_th"] < c["liquor756_th"] - 0.3, c_lo["liquor756_th"], f"< {c['liquor756_th']}")
chk("make_conc concentrates",    c_lo["make_conc_pct"] > c["make_conc_pct"] + 0.005, c_lo["make_conc_pct"], f"> {c['make_conc_pct']}")

# ---- 4) restore design, prove return to baseline (no hysteresis / drift) ----
main.handle_cmd({"type": "cpl_set", "value": CPL_DES})
c_rt = settle()
chk("returns to 43 C",           abs(c_rt["TT_322015"] - T_DES) < 0.3, c_rt["TT_322015"], T_DES)
chk("returns to design conc",    abs(c_rt["make_conc_pct"] - conc_des) < 0.03, c_rt["make_conc_pct"], round(conc_des,2))

print(f"FAILURES {fails}")
sys.exit(1 if fails else 0)
