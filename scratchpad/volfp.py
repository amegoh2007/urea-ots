import os, sys, json
B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, os.path.abspath(B)); os.chdir(os.path.abspath(B))
import main as M
for _ in range(20000):
    t = M.step_sim(0.1)
L = t["LPCC_3232"]
print("FIC_323401", json.dumps(L["E011"]["FIC_323401"]))
print("FIC_323418", json.dumps(L["C005"]["FIC_323418"]))
print("FIC_328405", json.dumps(L["C005"]["FIC_328405"]))
