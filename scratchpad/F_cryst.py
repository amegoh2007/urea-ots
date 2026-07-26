import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state
for _ in range(50):
    t = main.step_sim(0.1)
s.LIC_322501["mode"] = "MAN"; s.LIC_322501["op"] = 0.0
for k in range(1, 9001):
    t = main.step_sim(0.1)
    if k in (600, 1800, 6000, 9000):
        st = t["STREAMS"]["STRIP_BOT"]
        cr = t["CRYST"]["STRIP_BOT"]
        print(f"t={k*0.1:6.0f}s  LI={t['STRIP_322E001']['LI_322501']:6.1f}%  "
              f"TT-322004={t['STRIP_322E001']['TT_322004']:7.1f}C  "
              f"STRIP_BOT={ {kk:st[kk] for kk in st if kk in (chr(84),chr(80),chr(109)+chr(95)+chr(107)+chr(103)+chr(104),chr(107)+chr(103)+chr(104))} }  "
              f"cryst={cr}  flags={[k2 for k2,v in s.flags.items() if v]}")
