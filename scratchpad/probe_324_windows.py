"""Is the 324F001 separator-P swing a sustained cycle or a damping transient?
Report the P envelope over successive 3 h windows after a 1 h settle."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main  # noqa: E402

DT = 1.0
main.state = main.State()
s = main.state
for _ in range(3600):
    main.step_sim(DT)

for win in range(5):                       # 5 windows x 3 h = 15 h
    p1lo = p1hi = s.r324_f001_P
    p3lo = p3hi = s.r324_f003_P
    t1lo = t1hi = s.r324_e001_T
    for _ in range(180):                   # 3 h at 60 s sampling
        for _ in range(60):
            main.step_sim(DT)
        p1lo, p1hi = min(p1lo, s.r324_f001_P), max(p1hi, s.r324_f001_P)
        p3lo, p3hi = min(p3lo, s.r324_f003_P), max(p3hi, s.r324_f003_P)
        t1lo, t1hi = min(t1lo, s.r324_e001_T), max(t1hi, s.r324_e001_T)
    print("win %d (h %d-%d)  E001 P env %.4f (%.4f..%.4f)  E003 P env %.4f (%.4f..%.4f)  E001 T env %.5f" % (
        win, 1 + win * 3, 4 + win * 3, p1hi - p1lo, p1lo, p1hi, p3hi - p3lo, p3lo, p3hi, t1hi - t1lo))
