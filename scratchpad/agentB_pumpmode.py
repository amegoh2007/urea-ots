import os,sys
B=os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","backend"))
os.chdir(B); sys.path.insert(0,B)
import main
p=main.step_sim(0.1)
print("pumpA:",p["pumpA"]["mode"],"on",p["pumpA"]["on"])
print("pumpB:",p["pumpB"]["mode"],"on",p["pumpB"]["on"])
print("SIC_321951 mode:",p["controllers"]["SIC_321951"]["mode"])
print("SIC_321950 mode:",p["controllers"]["SIC_321950"]["mode"])
print("ratio_mode:", p.get("ratio",{}).get("mode"))
print("ratio keys:", sorted(p.get("ratio",{}).keys()))
