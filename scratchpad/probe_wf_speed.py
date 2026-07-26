"""READ-ONLY speed probe: how many step_sim(dt) per wall-second."""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main  # noqa

main.state = main.State()
DT = 0.5
t0 = time.time()
N = 400
for _ in range(N):
    main.step_sim(DT)
el = time.time() - t0
print(f"{N} steps in {el:.2f}s -> {N/el:.1f} steps/s ; sim-s per wall-s = {N*DT/el:.1f}")
print("w_f010 Urea =", repr(main.state.w_f010["Urea"]))
print("w_d002 Urea =", repr(main.state.w_d002["Urea"]))
print("W_S317 Urea =", repr(main.W_S317["Urea"]))
print("R324_W_IN   =", repr(main.R324_W_IN))
