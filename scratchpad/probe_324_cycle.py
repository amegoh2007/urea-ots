"""Measure the 324E001/324E003 residual limit-cycle envelope over 16 h (T and separator P).

Baseline current model recorded: E001 T env 0.4435 C, E003 T env 1.5730 C.
Runs a fresh design State, discards a 1 h settle, then samples every 60 s across 16 h.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main  # noqa: E402

DT = 1.0
main.state = main.State()
for _ in range(3600):
    main.step_sim(DT)

s = main.state
t1lo = t1hi = s.r324_e001_T
t3lo = t3hi = s.r324_e003_T
p1lo = p1hi = s.r324_f001_P
p3lo = p3hi = s.r324_f003_P
w1lo = w1hi = s.w_e001["Urea"]
for _ in range(960):
    for _ in range(60):
        main.step_sim(DT)
    t1lo, t1hi = min(t1lo, s.r324_e001_T), max(t1hi, s.r324_e001_T)
    t3lo, t3hi = min(t3lo, s.r324_e003_T), max(t3hi, s.r324_e003_T)
    p1lo, p1hi = min(p1lo, s.r324_f001_P), max(p1hi, s.r324_f001_P)
    p3lo, p3hi = min(p3lo, s.r324_f003_P), max(p3hi, s.r324_f003_P)
    w1lo, w1hi = min(w1lo, s.w_e001["Urea"]), max(w1hi, s.w_e001["Urea"])

print("E001  T env %.4f C (%.4f..%.4f)  P env %.5f (%.5f..%.5f)  final T=%.4f P=%.5f" % (
    t1hi - t1lo, t1lo, t1hi, p1hi - p1lo, p1lo, p1hi, s.r324_e001_T, s.r324_f001_P))
print("E003  T env %.4f C (%.4f..%.4f)  P env %.5f (%.5f..%.5f)  final T=%.4f P=%.5f" % (
    t3hi - t3lo, t3lo, t3hi, p3hi - p3lo, p3lo, p3hi, s.r324_e003_T, s.r324_f003_P))
print("E001  w env %.4f pp (%.4f..%.4f)" % (100.0 * (w1hi - w1lo), 100.0 * w1lo, 100.0 * w1hi))
