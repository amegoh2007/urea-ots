"""AGENT C: sim steady-state (design) vs the real 29-06-2025 DCS normal-op means."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main
s = main.state if hasattr(main, "state") else main.STATE
for _ in range(6000): t = main.step_sim(0.1)   # 600 s settle

def g(t, p):
    cur = t
    for k in p.split("."):
        cur = cur[k] if isinstance(cur, dict) and k in cur else None
        if cur is None: return None
    return cur

DCS = {  # tag: (mean, min, max)
 "UREA-LOAD": (100.384, 99.1, 101.3), "FYM-322403": (53.206, 52.5, 53.7),
 "PT-329201": (139.603, 137.9, 141.1), "PIC-322203": (144.959, 144.1, 145.7),
 "PV-322203": (0.0, 0.0, 0.0), "PIC-329204": (19.575, 19.4, 19.8),
 "PT-329206": (4.035, 3.99, 4.05), "PT-321202": (20.300, 20.0, 20.5),
 "SIC-321951": (122.768, 119.8, 124.6), "LV-322501": (44.706, 43.6, 45.5),
 "HIC-322604": (78.188, 78.0, 78.5), "HIC-322605": (55.172, 54.5, 55.9),
 "TT-322002": (165.696, 164.1, 167.1), "TT-322004": (168.728, 167.6, 169.3),
 "TT-322005": (183.084, 182.5, 183.7), "TT-322006": (179.697, 179.1, 180.4),
 "TT-322007": (174.303, 173.8, 175.0), "TT-322008": (171.134, 170.4, 171.9),
 "TT-322009": (185.081, 184.6, 185.4), "TT-322010": (169.706, 169.3, 170.1),
 "TT-322011": (130.316, 129.0, 131.5), "TT-322012": (113.165, 111.4, 115.3),
 "TT-322013": (187.491, 187.1, 187.6), "TT-322014": (183.556, 183.4, 183.9),
 "TT-322017": (114.331, 113.4, 115.7), "TIC-329005": (84.459, 83.3, 85.3),
 "AY-322701": (3.236, 3.19, 3.34), "TDY-329125": (20.097, 18.9, 21.5),
}
SIM = {
 "UREA-LOAD": g(t,"CO2_FEED.Load"), "FYM-322403": g(t,"CO2_FEED.FY_322403"),
 "PT-329201": g(t,"EJ_322F001.PI_329201"), "PIC-322203": g(t,"CO2_FEED.PIC_322203"),
 "PV-322203": g(t,"CO2_FEED.PV_322203"), "PIC-329204": g(t,"STEAM_SYSTEM.PIC_329204"),
 "PT-329206": None, "PT-321202": g(t,"PI_321202"),
 "SIC-321951": g(t,"pumpB.speed"), "LV-322501": g(t,"STRIP_322E001.LV_322501"),
 "HIC-322604": g(t,"SCRUB_322E003.HIC_322604"), "HIC-322605": g(t,"REACT_322R001.HIC_322605"),
 "TT-322002": g(t,"SCRUB_322E003.TT_322002"), "TT-322004": g(t,"STRIP_322E001.TT_322004"),
 "TT-322005": g(t,"REACT_322R001.TT_322005"), "TT-322006": g(t,"REACT_322R001.TT_322006"),
 "TT-322007": g(t,"REACT_322R001.TT_322007"), "TT-322008": g(t,"REACT_322R001.TT_322008"),
 "TT-322009": g(t,"REACT_322R001.TT_322009"), "TT-322010": g(t,"HPCC_322E002.TT_322010"),
 "TT-322011": g(t,"SCRUB_322E003.TT_322011"), "TT-322012": g(t,"HPCC_322E002.TT_322012"),
 "TT-322013": g(t,"STRIP_322E001.TT_322013"), "TT-322014": g(t,"STRIP_322E001.TT_322014"),
 "TT-322017": g(t,"CO2_FEED.TI_322017"), "TIC-329005": g(t,"SCRUB_322E003.ccw"),
 "AY-322701": g(t,"REACT_322R001.AT_322701"), "TDY-329125": None,
}
print(f"{'tag':12s} {'DCS mean':>10s} {'DCS min':>9s} {'DCS max':>9s} {'SIM':>12s} {'dev':>10s}  band")
for k,(m,lo,hi) in DCS.items():
    v = SIM[k]
    if isinstance(v, dict): v = v.get("pv", v.get("T_in"))
    if v is None: print(f"{k:12s} {m:10.3f} {lo:9.2f} {hi:9.2f} {'--':>12s}"); continue
    dev = v - m
    band = "IN" if lo <= v <= hi else "OUT"
    print(f"{k:12s} {m:10.3f} {lo:9.2f} {hi:9.2f} {v:12.3f} {dev:+10.3f}  {band}")
print("\nraw ccw:", g(t,"SCRUB_322E003.ccw"))
