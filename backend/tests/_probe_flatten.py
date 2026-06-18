"""Probe: validate packet-flatten + measure step_sim cost. Throwaway."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import main


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        elif isinstance(v, bool):
            out[key] = float(v)
        elif isinstance(v, (int, float)):
            out[key] = float(v)
    return out


main.state = main.State()
t0 = time.time()
pkt = None
N = 600  # 60 sim-sec at dt=0.1
for _ in range(N):
    pkt = main.step_sim(0.1)
dt_wall = time.time() - t0
flat = flatten(pkt)
print(f"ticks={N}  wall={dt_wall:.2f}s  per_tick_ms={1000*dt_wall/N:.3f}")
print(f"indicator_leaves={len(flat)}")
print(f"top_keys={list(pkt.keys())}")
print("\nfirst 40 leaves:")
for k in sorted(flat)[:40]:
    print(f"   {k:32s} {flat[k]}")
