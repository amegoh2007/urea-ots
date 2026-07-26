import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state if hasattr(main, "state") else main.STATE
t = main.step_sim(0.1)

def walk(d, pre=""):
    for k, v in d.items():
        if isinstance(v, dict):
            walk(v, pre + k + ".")
        else:
            print(f"{pre}{k} = {v!r}")

walk(t)
