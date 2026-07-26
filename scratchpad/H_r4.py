import os,sys
HERE=os.path.dirname(os.path.abspath(__file__)); B=os.path.normpath(os.path.join(HERE,"..","backend"))
os.chdir(B); sys.path.insert(0,B)
import main
mf=main.CO2_FEED_MOLFRAC
print("CO2 molfrac:", mf.get("CO2"))
co2 = main.CO2_DES_KMOLH*mf.get("CO2",1.0)
print("fresh CO2 kmol/h =", co2)
net_urea = main.REACT_OVERFLOW_DES["Urea"] - main.STRIP_XI_HYD_DES
print("net urea after stripper hydrolysis kmol/h =", net_urea, "=", net_urea*60.0554/1000*24, "t/d")
print("net urea / fresh CO2 =", net_urea/co2)
