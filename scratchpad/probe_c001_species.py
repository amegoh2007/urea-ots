"""Ground the 322C001 design point before writing the species layer."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main  # noqa: E402

print("=== boot-pinned 322C001 design constants ===")
print("A328_GCB_DES    =", main.A328_GCB_DES)
print("A328_GCB_T      =", main.A328_GCB_T)
print("A328_ABS_DES    =", main.A328_ABS_DES)
print("A328_PHI_ABS    =", main.A328_PHI_ABS)
print("A328_VENT_DES   =", main.A328_VENT_DES)
print("A328_LAMBDA_ABS =", main.A328_LAMBDA_ABS)
print("A328_M755_DES   =", main.A328_M755_DES, "@", main.A328_M755_T, "C")
print("A328_CPL_DES    =", main.A328_CPL_DES, "@", main.A328_CPL_T, "C")
print("A328_M756_DES   =", main.A328_M756_DES)
print("A328_C001_M_DES =", main.A328_C001_M_DES)

print("\n=== SCRUB_OFFGAS_KMOLH_DES (per species, to 322C001) ===")
tot_kmol = 0.0; tot_kg = 0.0
for k in main.MW_COMP:
    n = main.SCRUB_OFFGAS_KMOLH_DES.get(k, 0.0)
    if n:
        kg = n * main.MW_COMP[k]
        tot_kmol += n; tot_kg += kg
        print(f"  {k:6s} {n:10.4f} kmol/h  {kg:10.2f} kg/h  MW={main.MW_COMP[k]}")
print(f"  TOTAL  {tot_kmol:10.4f} kmol/h  {tot_kg:10.2f} kg/h")

DT = 0.25
main.state = main.State()
s = main.state
def run(sec):
    for _ in range(int(sec/DT)):
        main.step_sim(DT)
run(1200.0)
out = main.step_sim(DT)

print("\n=== settled live Stage-7 state ===")
# grab the live hv604 by re-deriving from telemetry if present
print("a328_c001_M =", s.a328_c001_M)
print("a328_c001_T =", s.a328_c001_T)
print("a328_c001_P =", s.a328_c001_P)
print("cpl_flow_kgh=", getattr(s, "cpl_flow_kgh", None))

# Look for the LP-absorber telemetry block
def find_block(d, keys, path=""):
    if isinstance(d, dict):
        for kk, vv in d.items():
            p = path + "/" + str(kk)
            if isinstance(vv, dict):
                if any(x in vv for x in keys):
                    print(p, "->", {x: vv[x] for x in keys if x in vv})
                find_block(vv, keys, p)
find_block(out, ["a328_c001_T", "vent", "abs", "GCB", "gcb", "TT_322015", "PIC_322201"])

# dump top-level keys of out to find the 328-2 / absorber section
print("\n=== out top-level keys ===")
print(list(out.keys()))
