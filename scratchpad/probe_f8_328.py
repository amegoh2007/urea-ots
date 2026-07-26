"""F-8 verification: the desorption-train species layer.

Phase A  design hold      -- nothing moves at the seed (the layer is a fixed point)
Phase B  PFD anchors      -- every section lands on its tabulated composition
Phase C  C1 closure       -- total and per-component mass close across all three columns
Phase D  off-design       -- cut the LP strip steam and watch the urea/NH3 slip respond

Run:  python probe_f8_328.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
import main as m  # noqa: E402

SP = ("CO2", "H2O", "NH3", "Urea")


def settle(state, n, dt=0.25, **over):
    for k, v in over.items():
        setattr(state, k, v)
    for _ in range(n):
        m.step_sim(state, dt)
    return state


def snap(s):
    return {
        "c002_T": s.a328_c002_T, "c002_M": s.a328_c002_M,
        "c003_T": s.a328_c003_T, "c003_M": s.a328_c003_M,
        "c004_T": s.a328_c004_T, "c004_M": s.a328_c004_M,
        "w002": dict(s.w_328c002), "w003": dict(s.w_328c003), "w004": dict(s.w_328c004),
    }


print("=" * 78)
print("PHASE A  design hold -- 20 min at the seed, nothing must move")
print("=" * 78)
s = m.SimState()
a0 = snap(s)
settle(s, int(20 * 60 / 0.25))
a1 = snap(s)
for k in ("c002_T", "c002_M", "c003_T", "c003_M", "c004_T", "c004_M"):
    print(f"  {k:8s} {a0[k]:12.6f} -> {a1[k]:12.6f}   drift {a1[k]-a0[k]:+.3e}")
worst = 0.0
for tag in ("w002", "w003", "w004"):
    for k in SP:
        worst = max(worst, abs(a1[tag][k] - a0[tag][k]))
print(f"  worst species drift over 20 min: {worst:.3e} mass fraction")

print()
print("=" * 78)
print("PHASE B  species vs the PFD tabulated compositions (mass %)")
print("=" * 78)
for tag, live, ref, name in (
        ("328C002 bot", a1["w002"], m.W_S743, "PFD 743"),
        ("328C003 bot", a1["w003"], m.W_S747, "PFD 747"),
        ("328C004 bot", a1["w004"], m.W_S739, "PFD 739")):
    print(f"  {tag}  ({name})")
    for k in SP:
        lv, rv = live[k] * 100.0, ref[k] * 100.0
        d = lv - rv
        print(f"      {k:5s} live {lv:10.5f}   pfd {rv:10.5f}   diff {d:+.2e}")

print()
print("  design anchors struck from the PFD:")
for tag, a in (("C002", m.DES_C002), ("C003", m.DES_C003), ("C004", m.DES_C004)):
    print(f"    {tag}: xi={a['xi']:8.4f} kmol/h  resid={a['resid']:+8.3f} kg/h  "
          f"y-vs-PFD dev={a['dev']*100:.3f} %pt")

print()
print("=" * 78)
print("PHASE C  C1 -- total mass closure across the train at the design seed")
print("=" * 78)
tel = m.publish(s) if hasattr(m, "publish") else None
print(f"  328C002  in {m.R328_C002_IN_DES:10.1f}  out "
      f"{m.R328_C002_M737_DES + m.R328_C002_M743_DES:10.1f}  "
      f"diff {m.R328_C002_IN_DES - m.R328_C002_M737_DES - m.R328_C002_M743_DES:+.3e}")
print(f"  328C003  in {m.R328_C003_IN_DES:10.1f}  out "
      f"{m.R328_C003_M748_DES + m.R328_C003_M747_DES:10.1f}  "
      f"diff {m.R328_C003_IN_DES - m.R328_C003_M748_DES - m.R328_C003_M747_DES:+.3e}")
print(f"  328C004  in {m.R328_C004_IN_DES:10.1f}  out "
      f"{m.R328_C004_M750_DES + m.R328_C004_M739_DES:10.1f}  "
      f"diff {m.R328_C004_IN_DES - m.R328_C004_M750_DES - m.R328_C004_M739_DES:+.3e}")
print(f"\n  holdups from the datasheet: C002 {m.R328_C002_M_DES:7.1f} kg "
      f"({m.R328_C002_NTRAY} trays)   C004 {m.R328_C004_M_DES:7.1f} kg "
      f"({m.R328_C004_NTRAY} trays)")
print(f"  hydrolyser urea load {m.R328_C003_UREA_DES:6.1f} kg/h  "
      f"(was 276.9 on the wrong stream's fraction; PFD says 256.6)")

print()
print("=" * 78)
print("PHASE D  off-design -- cut FIC-329401 LP strip steam, watch the slip")
print("=" * 78)


def slip(state):
    """ppm urea and NH3 in the purified condensate, straight off the species vector."""
    return state.w_328c004["Urea"] * 1e6, state.w_328c004["NH3"] * 1e6


s2 = m.SimState()
settle(s2, int(5 * 60 / 0.25))
u0, n0 = slip(s2)
print(f"  design            urea {u0:10.3f} ppm   NH3 {n0:10.3f} ppm   "
      f"T_c004 {s2.a328_c004_T:6.2f} C")
for cut in (0.90, 0.75, 0.60):
    s3 = m.SimState()
    settle(s3, int(5 * 60 / 0.25))
    s3.FIC_329401["sp"] = s3.FIC_329401["sp"] * cut
    settle(s3, int(30 * 60 / 0.25))
    u, n = slip(s3)
    print(f"  strip steam {cut:4.0%}  urea {u:10.3f} ppm   NH3 {n:10.3f} ppm   "
          f"T_c004 {s3.a328_c004_T:6.2f} C")

print()
print("  hydrolyser temperature sweep (TIC-328012) -- urea slip out of 328C003:")
for dT in (0.0, -10.0, -20.0, -40.0):
    s4 = m.SimState()
    settle(s4, int(5 * 60 / 0.25))
    x = m.hydrolysis_x_328c003(m.R328_C003_T + dT, m.R328_C003_M746_DES)
    ppm = m.R328_C003_UREA_DES * (1.0 - x) / m.R328_C003_M747_DES * 1e6
    print(f"    T = {m.R328_C003_T + dT:6.1f} C   conversion {x:10.6f}   "
          f"urea in 747 {ppm:12.2f} ppm")
