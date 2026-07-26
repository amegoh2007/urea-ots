"""Agent F -- documented-disturbance injection probe.

Usage:  python F_dist.py <scenario> [seconds]

Scenarios
  base       no disturbance (drift control)
  pumptrip   321P002B mechanical fault  -> trip 21.10 (HP NH3 feed pump trip)
  co2trip    XV-322902 shut             -> CO2 compressor trip / loss of CO2 feed
  o2loss     passivation air lost       -> CO2-feed O2 mol% -> 0
  flood      LIC-322501 -> MAN 0 %      -> HP stripper sump floods
  vaclost    PIC-324202 SP 0.33 -> 0.90 bara (1st-stage evaporator vacuum loss)
  nh3half    SIC-321951 speed -50 %     -> partial NH3 feed loss (N/C runaway)
"""
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa

SCEN = sys.argv[1] if len(sys.argv) > 1 else "base"
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 1800.0
DT = 0.1
s = main.state


def g(t, path):
    cur = t
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


TAGS = [
    ("P_syn",      "REACT_322R001.P_bara"),
    ("PI_329201",  "EJ_322F001.PI_329201"),
    ("PI_disch",   "EJ_322F001.PI_disch"),
    ("HPCC_P",     "HPCC_322E002.P_bara"),
    ("PIC322203",  "CO2_FEED.PIC_322203"),
    ("T_R009",     "REACT_322R001.TT_322009"),
    ("Xconv",      "REACT_322R001.X_conv"),
    ("NC_AT701",   "REACT_322R001.AT_322701"),
    ("LT_322504",  "REACT_322R001.LT_322504"),
    ("CO2_th",     "CO2_FEED.FY_322403"),
    ("Load%",      "CO2_FEED.Load"),
    ("EJ_motive",  "EJ_322F001.motive_kgh"),
    ("EJ_total",   "EJ_322F001.total_kgh"),
    ("Strip_Tbot", "STRIP_322E001.TT_322004"),
    ("Strip_Ttop", "STRIP_322E001.TT_322013"),
    ("Strip_LI",   "STRIP_322E001.LI_322501"),
    ("Strip_eta",  "STRIP_322E001.eta_T"),
    ("Strip_bot",  "STRIP_322E001.bot_th"),
    ("HPCC_LT",    "HPCC_322E002.LT_322E002"),
    ("HPCC_T010",  "HPCC_322E002.TT_322010"),
    ("Scrub_O2%",  "SCRUB_322E003.off_mol_pct.O2"),
    ("Scrub_H2%",  "SCRUB_322E003.off_mol_pct.H2"),
    ("Strip_drn",  "STRIP_322E001.drain_th"),
    ("LV_322501",  "STRIP_322E001.LV_322501"),
    ("C003_feed",  "RECIRC_323.C003.feed_th"),
    ("E001_feed",  "EVAP_324.E001.feed_th"),
    ("E003_prod",  "EVAP_324.E003.product_th"),
    ("E001_T",     "EVAP_324.E001.TT_324001"),
    ("E003_T",     "EVAP_324.E003.TT_324002"),
    ("E003_P",     "EVAP_324.E003.PT_324203"),
    ("PY_324201",  "EVAP_324.E001.PY_324201"),
    ("AY_324701",  "EVAP_324.E003.AY_324701"),
    ("E001_vap",   "EVAP_324.E001.vapour_th"),
    ("E001_melt",  "EVAP_324.E001.melt_th"),
    ("E003_vap",   "EVAP_324.E003.vapour_th"),
    ("E003_urea%", "EVAP_324.E003.urea_pct"),
    ("E001_urea%", "EVAP_324.E001.urea_pct"),
    ("E001_P",     "EVAP_324.E001.PT_324202"),
    ("C001_T",     "ABSORB_328.C001.TT_322015"),
]


def snap(t):
    return {n: g(t, p) for n, p in TAGS}


def line(tag, d):
    out = [f"{tag:>9s}"]
    for n, _ in TAGS:
        v = d[n]
        out.append(f"{v:9.3f}" if isinstance(v, (int, float)) else f"{'--':>9s}")
    return " ".join(out)


def flags():
    lat = [k for k, v in s.trip_latched.items() if v]
    liv = [k for k, v in s.trips.items() if v]
    fl = [k for k, v in s.flags.items() if v]
    return f"live={liv} latched={lat} flags={fl}"


# settle
for _ in range(50):
    t = main.step_sim(DT)
d0 = snap(t)
print("SCENARIO:", SCEN, " duration", SECS, "s")
print(" " * 10 + " ".join(f"{n:>9s}" for n, _ in TAGS))
print(line("t=0", d0))
print("   pre-flags:", flags())

# ---- inject ----
if SCEN == "pumptrip":
    main.handle_cmd({"type": "trigger_fault", "id": "B", "value": True})
elif SCEN == "co2trip":
    main.handle_cmd({"type": "xv_toggle", "id": "322902"})
elif SCEN == "o2loss":
    main.CO2_FEED_MOLFRAC["O2"] = 0.0
    main.CO2_FEED_MOLFRAC["N2"] = 0.0415       # keep sum = 1
elif SCEN == "flood":
    s.LIC_322501["mode"] = "MAN"; s.LIC_322501["op"] = 0.0
elif SCEN == "vaclost":
    s.PIC_324202["mode"] = "MAN"; s.PIC_324202["op"] = 100.0
elif SCEN == "nh3half":
    main.handle_cmd({"type": "controller_set", "id": "SIC_321951", "mode": "MAN"})
    main.handle_cmd({"type": "controller_set", "id": "SIC_321951", "op": 31.5})
elif SCEN != "base":
    raise SystemExit("unknown scenario " + SCEN)

marks = sorted({10, 30, 60, 120, 300, 600, 900, 1200, int(SECS)})
mset = {int(m / DT) for m in marks if m <= SECS}
seen = {}
for k in range(1, int(SECS / DT) + 1):
    t = main.step_sim(DT)
    if k in mset:
        d = snap(t)
        print(line(f"t={k*DT:.0f}s", d))
        seen[k * DT] = flags()

print("\n-- flag timeline --")
prev = None
for tt, f in seen.items():
    if f != prev:
        print(f"  t={tt:7.0f}s  {f}")
        prev = f
print("  final:", flags())

print("\n-- delta vs t=0 --")
dN = snap(t)
for n, _ in TAGS:
    a, b = d0[n], dN[n]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        print(f"  {n:>10s}  {a:10.3f} -> {b:10.3f}   ({b-a:+.3f})")
