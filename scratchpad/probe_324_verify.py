"""TD-016 verification: anchor exactness, Fahmy-Nassar table match, boot pin, 324 design hold."""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
cache = os.path.join(BACKEND, ".boot_pin_cache.json")
if os.path.exists(cache):
    os.remove(cache)
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main  # noqa: E402  -> boot settle

# --- boot pin FIRST (before any stepping moves the state off design) ---
pin = main._collect_pin()
json.dump(pin, open(os.path.join(HERE, "pin_324fix.json"), "w"), indent=2)
print("wrote boot pin")

# --- anchor exactness (must be a literal identity, not a tolerance) ---
a1 = main.evap_w_eq(130.0, 0.33, main.R324_W_EV1, 130.0, 0.33)
a2 = main.evap_w_eq(140.0, 0.131, main.R324_W_EV2, 140.0, 0.131)
print("anchor1 exact:", a1 == main.R324_W_EV1, repr(a1))
print("anchor2 exact:", a2 == main.R324_W_EV2, repr(a2))

# --- Fahmy-Nassar reproduces the reference tables ---
print("Cu(130,0.33)=%.4f [tbl .9371]  Cu(135,0.33)=%.4f [.9470]  Cu(140,0.131)=%.4f [.9819]" % (
    main._fahmy_Cu(130.0, 0.33), main._fahmy_Cu(135.0, 0.33), main._fahmy_Cu(140.0, 0.131)))
print("weq(135,0.33)=%.4f [anchored ~.9530]  weq(125,0.33)=%.4f  weq(140,0.131)=%.4f [.9771]" % (
    main.evap_w_eq(135.0, 0.33, main.R324_W_EV1, 130.0, 0.33),
    main.evap_w_eq(125.0, 0.33, main.R324_W_EV1, 130.0, 0.33),
    main.evap_w_eq(140.0, 0.131, main.R324_W_EV2, 140.0, 0.131)))

# --- 324 design hold (the pin is blind to 324 vapour rates; check directly) ---
main.state = main.State()
out = None
for _ in range(2400):
    out = main.step_sim(0.25)                      # 600 s
e1, e3 = out["EVAP_324"]["E001"], out["EVAP_324"]["E003"]
print("design hold  TT1=%.5f TT2=%.5f  urea1=%.2f urea2=%.2f  v1th=%.4f/%.4f  v2th=%.4f/%.4f" % (
    e1["TT_324001"], e3["TT_324002"], e1["urea_pct"], e3["urea_pct"],
    e1["vapour_th"], main.R324_V1_DES / 1000.0, e3["vapour_th"], main.R324_V2_DES / 1000.0))
