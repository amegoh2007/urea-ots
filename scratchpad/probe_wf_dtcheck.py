"""READ-ONLY: is the w_f010 urea drift a property of the MODEL or of the TICK SIZE?
Runs the same 2 h hold at dt = 0.25 / 0.5 / 1.0 and compares the drift slope.  A slope that is
independent of dt is a genuine model drift; a slope that scales with dt is an integration artefact.
"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa

HOURS = 2.0
print(f"{'dt':>6} {'w_f010 @0.5h':>16} {'w_f010 @2h':>16} {'pp/h (0.5->2h)':>16}")
for dt in (1.0, 0.5, 0.25):
    main.state = main.State()
    s = main.state
    n_half = int(0.5 * 3600 / dt)
    n_end = int(HOURS * 3600 / dt)
    w_half = None
    t0 = time.time()
    for i in range(1, n_end + 1):
        main.step_sim(dt)
        if i == n_half:
            w_half = s.w_f010["Urea"]
    w_end = s.w_f010["Urea"]
    slope = (w_end - w_half) * 100.0 / (HOURS - 0.5)
    print(f"{dt:6.2f} {w_half*100:16.9f} {w_end*100:16.9f} {slope:+16.8f}   "
          f"({time.time()-t0:.0f}s wall)")
