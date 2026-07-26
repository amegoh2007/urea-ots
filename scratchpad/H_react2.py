import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); B=os.path.normpath(os.path.join(HERE,"..","backend"))
os.chdir(B); sys.path.insert(0,B)
import main, reactor
for _ in range(200): main.step_sim(0.1)
s = main.state if hasattr(main,"state") else main.STATE
tel = main.telemetry()
import json
def dig(d,pat,pre=""):
    out=[]
    if isinstance(d,dict):
        for k,v in d.items():
            if pat.lower() in str(k).lower() and not isinstance(v,(dict,list)): out.append((pre+"/"+k,v))
            elif isinstance(v,dict): out+=dig(v,pat,pre+"/"+k)
    return out
for p in ("X_conv","conv","N/C","ratio","L_feed","W_feed","tau"):
    h=dig(tel,p)
    if h: print(p,"->",h[:8])
print("\nCO2_DES_KGH=",main.CO2_DES_KGH," CO2_DES_KMOLH=",main.CO2_DES_KMOLH)
print("overflow design urea kmol/h=",main.STRIP_FEED207_KMOLH["Urea"])
print("fresh CO2 kmol/h -> urea/CO2_fresh =", main.STRIP_FEED207_KMOLH["Urea"]/main.CO2_DES_KMOLH)
print("react L_feed live=",s.react_L_feed," W_feed=",s.react_W_feed)
