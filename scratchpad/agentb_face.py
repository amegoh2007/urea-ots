import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state
main.step_sim(0.1)

print("--- 324/335 faceplate SET path (frontend falls through to controller_set) ---")
for tag, obj in (("TIC-324001", "TIC_324001"), ("FIC-335405A", "FIC_335405"),
                 ("FFIC-335406", "FFIC_335406"), ("LIC-324501", "LIC_324501"),
                 ("PIC-324202", "PIC_324202")):
    before = dict(getattr(s, obj))
    main.handle_cmd({"type": "controller_set", "id": tag, "mode": "MAN", "op": 12.34})
    after = dict(getattr(s, obj))
    print("  %-12s controller_set MAN/op=12.34 -> mode %s->%s  op %.3f->%.3f  %s"
          % (tag, before["mode"], after["mode"], before["op"], after["op"],
             "NO-OP (command silently discarded)" if before == after else "APPLIED"))

print("\n--- same tags via r323_ctrl_set (the handler the frontend does NOT route them to) ---")
for tag, obj in (("TIC-324001", "TIC_324001"),):
    before = dict(getattr(s, obj))
    main.handle_cmd({"type": "r323_ctrl_set", "id": tag, "mode": "MAN", "op": 12.34})
    print("  %-12s -> %s" % (tag, "NO-OP (not in R323_CTRL_MODES either)"
                             if dict(getattr(s, obj)) == before else "APPLIED"))

print("\n--- seeded-CAS loops and whether a cas_sp is actually wired ---")
import re
src = open(os.path.join(BACKEND, "main.py"), encoding="utf-8").read()
for name in ("SIC_321951", "PIC_329202", "PIC_329208", "FIC_324401", "PIC_329203",
             "PIC_329212", "FIC_335405", "SIC_323901", "TIC_323013", "FIC_328404",
             "FIC_329402", "FIC_329401"):
    calls = [l.strip() for l in src.split("\n")
             if ("_ctrl_ipd(s." + name in l or "_fic_flow(s." + name in l or "ctrl.step(" in l and name == "SIC_321951")]
    wired = any(("cas_sp" in c) or ("dt, lic502_op" in c) or ("dt, tic" in c) for c in calls)
    print("  %-12s wired=%-5s   %s" % (name, wired, calls[0][:110] if calls else "<no step call found>"))
