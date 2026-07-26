"""Confirm the v1 offset is an upstream feed characteristic, not a 324 bug."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main  # noqa: E402

main.state = main.State()
s = main.state
t = 0.0
for mark in (600.0, 3600.0, 14400.0):
    while t < mark:
        main.step_sim(0.25)
        t += 0.25
    d1 = main._DIAG["E001"]
    print("t=%.0f" % mark)
    print("  feed1=%.3f (FEED_DES=%.3f d=%.3f)  urea_in=%.3f (U_DES=%.3f)  w_tank=%.5f" % (
        d1["feed"], main.R324_FEED_DES, d1["feed"] - main.R324_FEED_DES,
        d1["urea_in"], main.R324_U_DES, s.w_d002.get("Urea", 0.0)))
    print("  weq1=%.6f (W_EV1=%.4f)  v1=%.3f (V1_DES=%.3f d=%.3f)  T=%.5f P=%.5f" % (
        d1["weq"], main.R324_W_EV1, d1["v"], main.R324_V1_DES, d1["v"] - main.R324_V1_DES,
        s.r324_e001_T, s.r324_f001_P))
