import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state

def run(op, nsec=300):
    # reset by re-instantiating state
    main.state = main.State(); s = main.state
    s.PIC_322203["mode"] = "MAN"
    s.PIC_322203["op"] = op
    pkt = None
    for _ in range(int(nsec/0.1)):
        pkt = main.step_sim(0.1)
    c = pkt["CO2_FEED"]
    return (op, c["PV_322203"], c["PIC_322203"], c["raw_th"], c["pure_th"], c["vent_th"],
            main.state.F_CO2_th, main.state.ratio_PV, main.state.p_syn_bara)

print("%5s %7s %9s %8s %8s %8s %8s %8s %8s" % ("op%","PVopen","P_line","raw t/h","toHP","vent","F_CO2","N/C","P_syn"))
for op in (0.0, 5.0, 20.0, 50.0, 100.0):
    r = run(op)
    print("%5.1f %7.1f %9.2f %8.2f %8.2f %8.2f %8.2f %8.3f %8.2f" % r)
