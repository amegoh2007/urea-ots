import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE,"..","backend"))
os.chdir(BACKEND); sys.path.insert(0,BACKEND)
import main
s = main.state if hasattr(main,"state") else main.STATE
for i in range(600): pk = main.step_sim(0.1)
print("=== ARB-3: which pressure node is frozen? ===")
print("  REACT_P_BARA constant      =", main.REACT_P_BARA)
print("  packet REACT.P_bara        =", pk["REACT_322R001"]["P_bara"])
print("  live state s.p_syn_bara    = %.4f" % s.p_syn_bara)
print("  SYN_P_MAX_BARA             =", main.SYN_P_MAX_BARA)
print("\n  load    s.p_syn   REACT.P_bara   HPCC.P    phi_HP-relevant dP")
for frac in (1.0, 0.8, 0.6, 0.4):
    s.F_CO2_raw_th = main.CO2_DES_KGH/1000.0*frac
    for i in range(6000): pk = main.step_sim(0.1)
    hp = pk.get("HPCC_322E002",{})
    print("  %.0f%%    %8.3f   %8.3f      %s" % (frac*100, s.p_syn_bara,
          pk["REACT_322R001"]["P_bara"], hp.get("P_bara")))
