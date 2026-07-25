"""Verify the 322C001 species layer: design bit-exact + physical off-design vent slip + pin."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
cache = os.path.join(BACKEND, ".boot_pin_cache.json")
if os.path.exists(cache):
    os.remove(cache)
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main  # noqa: E402

pin = main._collect_pin()
json.dump(pin, open(os.path.join(HERE, "pin_c001.json"), "w"), indent=2)
print("wrote boot pin  |  A328_ABS_CO2_DES=%.4f  A328_ABS_NH3_DES=%.4f  sum=%.6f" % (
    main.A328_ABS_CO2_DES, main.A328_ABS_NH3_DES, main.A328_ABS_CO2_DES + main.A328_ABS_NH3_DES))
print("W_C001_DES:", {k: round(v, 5) for k, v in main.W_C001_DES.items() if v > 1e-9})

DT = 0.25
main.state = main.State()
s = main.state
def run(sec):
    for _ in range(int(sec / DT)):
        main.step_sim(DT)

# --- design hold: everything must be stationary at the seed ---
w0 = dict(s.a328_c001_w)
run(1200.0)
out = main.step_sim(DT)
c001 = out["ABSORB_328"]["C001"]
dw = max(abs(s.a328_c001_w[k] - w0.get(k, 0.0)) for k in s.a328_c001_w)
print("\n=== DESIGN HOLD (20 min settle) ===")
print("TT_322015 = %.4f  (want 43.0)" % c001["TT_322015"])
print("abs_th    = %.4f t/h  (want 0.130)" % c001["abs_th"])
print("vent_th   = %.4f t/h  (want ~5.771)" % c001["vent_th"])
print("vent_nh3_kgh = %.2f   vent_nh3_pct = %.2f   vent_co2_pct = %.2f" % (
    c001["vent_nh3_kgh"], c001["vent_nh3_pct"], c001["vent_co2_pct"]))
print("liq_nh3_pct  = %.3f   liq_co2_pct  = %.3f" % (c001["liq_nh3_pct"], c001["liq_co2_pct"]))
print("max |dw| over settle = %.3e  (liquor stationary?)" % dw)
print("liquor w now:", {k: round(v, 5) for k, v in s.a328_c001_w.items() if v > 1e-9})
print("sum w = %.9f" % sum(s.a328_c001_w.values()))

# --- off-design: raise reactor N/C -> more NH3 in the purge -> vent NH3 slip must RISE ---
base_nh3 = c001["vent_nh3_kgh"]; base_pct = c001["vent_nh3_pct"]
# push excess-NH3 loop: raise the feed N/C via HIC-322602 (NH3 nozzle) if present, else ratio_SP
s.ratio_SP = getattr(s, "ratio_SP", None)
moved = False
if hasattr(s, "ratio_SP") and s.ratio_SP is not None:
    s.ratio_SP = s.ratio_SP * 1.06
    moved = True
run(1200.0)
out2 = main.step_sim(DT); c2 = out2["ABSORB_328"]["C001"]
print("\n=== OFF-DESIGN: feed N/C +6%% (ratio_SP moved=%s) ===" % moved)
print("vent_nh3_kgh %.2f -> %.2f   (%s)" % (base_nh3, c2["vent_nh3_kgh"],
      "UP OK" if c2["vent_nh3_kgh"] > base_nh3 else "no change / down"))
print("vent_nh3_pct %.2f -> %.2f" % (base_pct, c2["vent_nh3_pct"]))
print("TT_322015 %.3f   abs_th %.4f" % (c2["TT_322015"], c2["abs_th"]))
