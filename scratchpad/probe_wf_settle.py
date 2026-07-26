"""READ-ONLY probe.  Settles the undisturbed design sim for a long horizon and records the
323F010 product composition (s.w_f010) and the 323D002 Comp-I composition (s.w_d002), plus the
tank's own inlet/outlet/holdup so the CSTR pole (lambda) and the pin-fix amplification 1/mu can
be computed from real numbers.

Nothing in backend/ is touched.  The "attempted fix" is NOT re-applied to main.py -- instead its
exact recursion is replayed OFFLINE on the recorded (lambda, mu, w_in) trajectory, which is
mathematically identical to running it in-line because 323D002 is a pure sink (its composition
feeds unit 324 only, and unit 324 does not feed back into 323F010).
"""
import os, sys, time, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
OUT = os.path.join(HERE, "probe_wf_settle.json")
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa

DT = 0.5
HOURS = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
NSTEP = int(HOURS * 3600.0 / DT)
SAMPLE = int(60.0 / DT)          # sample every 60 sim-seconds

main.state = main.State()
s = main.state

print("seed  W_S317['Urea'] =", repr(main.W_S317["Urea"]))
print("seed  R324_W_IN      =", repr(main.R324_W_IN))
print("seed  w_f010['Urea'] =", repr(s.w_f010["Urea"]))
print("seed  w_d002['Urea'] =", repr(s.w_d002["Urea"]))
print("R323_M317_DES =", main.R323_M317_DES, " R323_M324_DES =", main.R323_M324_DES)
print("R323_D002_M_I_FULL =", main.R323_D002_M_I_FULL, " seed M_I =", s.r323_d002_M_I)
print()

rows = []
t0 = time.time()
for i in range(NSTEP):
    pkt = main.step_sim(DT)
    if i % SAMPLE == 0:
        rows.append(dict(
            t_s=i * DT,
            wf010=s.w_f010["Urea"], wf010_h2o=s.w_f010["H2O"], wf010_biu=s.w_f010["Biuret"],
            wf010_nh3=s.w_f010["NH3"], wf010_co2=s.w_f010["CO2"], wf010_hcho=s.w_f010.get("HCHO", 0.0),
            wd002=s.w_d002["Urea"],
            wf004=s.w_f004["Urea"],
            M_I=s.r323_d002_M_I, M_f010=s.r323_f010_M,
            m317=pkt["RECIRC_323"]["F010"]["product317_th"] * 1000.0,
            m324=pkt["RECIRC_323"]["D002"]["product324_th"] * 1000.0,
            evap=pkt["RECIRC_323"]["F010"]["evap_th"] * 1000.0,
            m319=pkt["RECIRC_323"]["F004"]["drain319_th"] * 1000.0,
            T010=pkt["RECIRC_323"]["F010"]["TT_323010"],
        ))
el = time.time() - t0
print(f"ran {NSTEP} steps ({HOURS} h sim) in {el:.1f}s wall")
print()
hdr = f"{'t_h':>7} {'w_f010 Urea %':>16} {'w_d002 Urea %':>16} {'w_f004 Urea %':>15} {'M_I kg':>12}"
print(hdr)
for r in rows[::max(1, len(rows) // 40)]:
    print(f"{r['t_s']/3600.0:7.3f} {r['wf010']*100:16.9f} {r['wd002']*100:16.9f} "
          f"{r['wf004']*100:15.9f} {r['M_I']:12.1f}")
print()
print("FINAL  w_f010['Urea'] =", repr(s.w_f010["Urea"]), "  -> %", s.w_f010["Urea"] * 100)
print("FINAL  w_d002['Urea'] =", repr(s.w_d002["Urea"]))
print("FINAL  w_f010 full    =", {k: round(v, 9) for k, v in s.w_f010.items()})

# ---- drift rate of w_f010, in percentage-points per hour, over the last half of the run ----
if len(rows) > 4:
    a, b = rows[len(rows) // 2], rows[-1]
    dh = (b["t_s"] - a["t_s"]) / 3600.0
    print(f"\nw_f010 drift over last {dh:.2f} h: "
          f"{(b['wf010'] - a['wf010'])*100:+.6f} pp  -> {(b['wf010']-a['wf010'])*100/dh:+.6f} pp/h")
    c = rows[1]
    dh2 = (b["t_s"] - c["t_s"]) / 3600.0
    print(f"w_f010 drift over whole {dh2:.2f} h: "
          f"{(b['wf010'] - c['wf010'])*100:+.6f} pp  -> {(b['wf010']-c['wf010'])*100/dh2:+.6f} pp/h")

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(rows, f)
print("\nwrote", OUT)
