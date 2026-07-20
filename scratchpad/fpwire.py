"""Faceplate command-routing acceptance test.

Gate 1  routing  : every loop in main.py's R323_CTRL_MODES whitelist must be routed by
                   app.js to a real backend handler (`r323_ctrl_set`, or a bespoke handler
                   in the T map).  A tag missing from both falls through to
                   `controller_set`, whose getattr(state, "FIC-323401") misses and silently
                   discards the write.
Gate 2  liveness : each whitelisted loop, driven through handle_cmd() exactly as the
                   websocket would, must actually take a MAN op write; and the same tag
                   sent through `controller_set` must NOT (proving the defect was real).
Gate 3  guard    : an illegal mode for a loop (e.g. AUTO on the MAN-only spares) must be
                   rejected by the backend whitelist, so an over-broad frontend set is inert.
"""
import os, re, sys

B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, os.path.abspath(B))
os.chdir(os.path.abspath(B))
import main as M

FAIL = 0
src = open(os.path.join("..", "frontend", "app.js"), encoding="utf-8").read()
tmap = set(re.findall(r"'([A-Z]+-\d+)'\s*:", re.search(r"const T=\{(.*?)\};", src, re.S).group(1)))
r323 = set(re.findall(r"'([A-Z]+-\d+)'", re.search(r"const R323=new Set\(\[(.*?)\]\);", src, re.S).group(1)))
wl = list(M.R323_CTRL_MODES)

# ---- gate 1 : routing ------------------------------------------------------
missing = [k for k in wl if k.replace("_", "-") not in (tmap | r323)]
FAIL += len(missing)
print(f"gate 1 - routing   : {len(wl)} whitelisted, {len(wl)-len(missing)} routed, "
      f"{len(missing)} unreachable  {'OK ' if not missing else 'FAIL ' + str(missing)}")

# ---- gate 2 : liveness -----------------------------------------------------
dead = []
for k in wl:
    tag, c = k.replace("_", "-"), getattr(M.state, k)
    # OP spans differ per loop (TIC-323007/012 command a chest PRESSURE, op_hi = the steam
    # header), so aim inside the loop's own range instead of assuming a 0-100 % stroke.
    lo, hi = c["op_lo"], c["op_hi"]
    want = lo + 0.25 * (hi - lo)
    c["mode"], c["op"] = "MAN", hi
    M.handle_cmd({"type": "r323_ctrl_set", "id": tag, "mode": "MAN", "op": want})
    if abs(c["op"] - want) > 1e-9:
        dead.append(tag)
FAIL += len(dead)
print(f"gate 2 - liveness  : {len(wl)-len(dead)}/{len(wl)} loops take a MAN op write via "
      f"r323_ctrl_set  {'OK ' if not dead else 'FAIL ' + str(dead)}")

c = M.state.FIC_323401
c["mode"], c["op"] = "MAN", 50.0
M.handle_cmd({"type": "controller_set", "id": "FIC-323401", "op": 12.0})
old_path_dead = abs(c["op"] - 50.0) < 1e-9
FAIL += 0 if old_path_dead else 1
print(f"           control : the OLD controller_set path is a no-op for these tags "
      f"(op stayed {c['op']})  {'OK ' if old_path_dead else 'FAIL'}")

# ---- gate 3 : whitelist guard ---------------------------------------------
man_only = [k for k, v in M.R323_CTRL_MODES.items() if v == ("MAN",)]
leaked = []
for k in man_only:
    c = getattr(M.state, k)
    c["mode"] = "MAN"
    M.handle_cmd({"type": "r323_ctrl_set", "id": k.replace("_", "-"), "mode": "AUTO"})
    if c["mode"] != "MAN":
        leaked.append(k)
FAIL += len(leaked)
print(f"gate 3 - guard     : MAN-only spares {[k.replace('_','-') for k in man_only]} reject AUTO"
      f"  {'OK ' if not leaked else 'FAIL ' + str(leaked)}")

print(f"\nFAILURES {FAIL}")
