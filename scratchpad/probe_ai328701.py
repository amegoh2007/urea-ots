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
    return snap["DESORB_328"]["C004"]

TC4  = main.R328_C004_T      # 143 Desorber-II design temp
TDES = main.R328_C003_T      # 200 hydrolyser design temp

# ---- 1) DESIGN STEADY STATE : anchored bit-exact to PFD 1 ppm guarantee ----
d = settle()
# function is bit-exact at T==143.0 exactly; settled column droops ~0.02 C -> ~0.6% (deep-strip gain)
chk("nh3_740_ppm @design ~ 1.0 (col droop)",  abs(d["nh3_740_ppm"]  - 1.0) < 0.02, d["nh3_740_ppm"], "1.00 +/-0.02")
chk("ppm_infer bit-exact at T_des exact", main.ppm_infer_328701(143.0, 200.0)[0] == 1.0, main.ppm_infer_328701(143.0, 200.0)[0], 1.0)
chk("urea_740_ppm @design == 1.0", abs(d["urea_740_ppm"] - 1.0) < 1e-6, d["urea_740_ppm"], 1.0)
chk("AI_328701 in 6-7.5 uS/cm band (1 ppm NH3)", 6.0 < d["AI_328701"] < 7.5, d["AI_328701"], "~6.9")
chk("TT_328006 @design == 89",     abs(d["TT_328006"] - 89.0) < 0.1, d["TT_328006"], 89.0)

# ---- 2) OFF-DESIGN DIRECTION (direct function calls, physics check) ----
# cooler Desorber-II -> lower K -> less stripping -> higher NH3 slip
nh3_cold, _ = main.ppm_infer_328701(TC4 - 10.0, TDES)
nh3_hot, _  = main.ppm_infer_328701(TC4 + 10.0, TDES)
chk("NH3 ppm rises when 328C004 cools",  nh3_cold > 1.0, round(nh3_cold, 3), "> 1.0")
chk("NH3 ppm falls when 328C004 hotter", nh3_hot < 1.0, round(nh3_hot, 3), "< 1.0")
# cooler hydrolyser -> higher urea slip
_, urea_cold = main.ppm_infer_328701(TC4, TDES - 15.0)
_, urea_hot  = main.ppm_infer_328701(TC4, TDES + 10.0)
chk("urea ppm rises when 328C003 cools", urea_cold > 1.0, round(urea_cold, 3), "> 1.0")
chk("urea ppm falls when 328C003 hotter", urea_hot < 1.0, round(urea_hot, 3), "< 1.0")
# conductivity monotone in NH3
k1 = main.cond_infer_328701(1.0, 1.0, 0.0)
k2 = main.cond_infer_328701(2.0, 1.0, 0.0)
chk("kappa rises with NH3 ppm", k2 > k1, round(k2, 2), f"> {round(k1,2)}")
# urea explicitly moves the reading (directive)
ku = main.cond_infer_328701(1.0, 50.0, 0.0)
chk("kappa moves with urea ppm (non-zero contribution)", ku > k1, round(ku, 3), f"> {round(k1,3)}")

print(f"\nFAILURES {fails}")
sys.exit(1 if fails else 0)
