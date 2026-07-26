import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
t0=time.time()
for _ in range(2000): main.step_sim(0.1)
print("steps/s", 2000/(time.time()-t0))
