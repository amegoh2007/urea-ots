"""READ-ONLY: replay 323D002 Comp-I WITHOUT the pin, using the (w_f010, m_317, m_324, M_I)
trajectory recorded by probe_wf_settle.py.  Shows where the tank's own mass balance actually
lands -- i.e. whether there is a 3.5-point gap to the PFD 80.00 anchor or not.
Also replays the reverted "anchor + frozen-reference deviation" fix on the same trajectory."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "probe_wf_settle.json"), encoding="utf-8"))
A = 0.80
W317N = 0.8000162403296788

print(f"{len(rows)} samples, {rows[-1]['t_s']/3600.0:.2f} h of sim")

# --- 1. unpinned tank, integrated at the 60 s sample resolution -------------------------------
w = W317N                      # State() seeds w_d002 with W_S317
for i in range(1, len(rows)):
    r = rows[i]
    dt = r["t_s"] - rows[i - 1]["t_s"]
    M = r["M_I"]
    a = r["m317"] * dt / 3600.0
    b = r["m324"] * dt / 3600.0
    tot = M + a - b
    w = ((M - b) * w + a * r["wf010"]) / tot
print(f"UNPINNED w_d002 after the run : {w*100:.6f} %   (inlet w_f010 = {rows[-1]['wf010']*100:.6f} %)")
print(f"gap to the PFD 80.00 anchor   : {(w-A)*100:+.6f} pp")

# --- 2. reverted fix: auth = A + (balance - frozen reference) ---------------------------------
for label, w_prev0 in (("ref from PINNED prev tick (0.80)", A),
                       ("ref from UNPINNED seed (W_S317)", W317N)):
    r1 = rows[1]
    dt = r1["t_s"] - rows[0]["t_s"]
    M, a, b = r1["M_I"], r1["m317"] * dt / 3600.0, r1["m324"] * dt / 3600.0
    tot = M + a - b
    ref = ((M - b) * w_prev0 + a * r1["wf010"]) / tot
    w = A
    traj = []
    for i in range(1, len(rows)):
        r = rows[i]
        dt = r["t_s"] - rows[i - 1]["t_s"]
        M, a, b = r["M_I"], r["m317"] * dt / 3600.0, r["m324"] * dt / 3600.0
        tot = M + a - b
        w = A + (((M - b) * w + a * r["wf010"]) / tot) - ref
        traj.append((r["t_s"], w))
    print(f"\nFIX [{label}]  ref={ref!r}  A-ref={A-ref:.3e}")
    for t, v in traj[::max(1, len(traj) // 12)]:
        print(f"   t={t:8.0f}s  {v*100:9.4f} %")
    print(f"   end      t={traj[-1][0]:8.0f}s  {traj[-1][1]*100:9.4f} %")

# --- 3. w_f010 drift table --------------------------------------------------------------------
print("\nw_f010 Urea %, sampled:")
for r in rows[::max(1, len(rows) // 20)]:
    print(f"   t={r['t_s']/3600.0:6.2f} h  {r['wf010']*100:.9f}   M_I={r['M_I']:.1f}  "
          f"m317={r['m317']:.1f}  m324={r['m324']:.1f}")
