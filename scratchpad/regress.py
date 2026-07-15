"""Boot-pin regression gate.
Deletes the pin cache, imports main (triggers full settle + back-solve),
dumps main._collect_pin() to argv[1]. Compare vs golden_pin.json for bit-exact.
"""
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))

cache = os.path.join(BACKEND, ".boot_pin_cache.json")
if os.path.exists(cache):
    os.remove(cache)

os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main  # noqa: E402  -> triggers _pin_hpcc_ua() full settle

pin = main._collect_pin()
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "pin_out.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(pin, f, indent=2)
print("wrote", out)
