"""Verify the three Mapping vacuum sign-rules, plus pin + design hold."""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
cache = os.path.join(BACKEND, ".boot_pin_cache.json")
if os.path.exists(cache):
    os.remove(cache)
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main  # noqa: E402

pin = main._collect_pin()
json.dump(pin, open(os.path.join(HERE, "pin_vacrules.json"), "w"), indent=2)
print("wrote boot pin")

DT = 0.25
main.state = main.State()
s = main.state


def run(sec):
    for _ in range(int(sec / DT)):
        main.step_sim(DT)


run(1200.0)  # settle
out = main.step_sim(DT)
e1, e3 = out["EVAP_324"]["E001"], out["EVAP_324"]["E003"]
print("design hold  TT1=%.4f TT2=%.4f urea1=%.2f urea2=%.2f  P_f010=%.4f P_f001=%.4f P_f003=%.4f" % (
    e1["TT_324001"], e3["TT_324002"], e1["urea_pct"], e3["urea_pct"],
    s.r323_f010_P, s.r324_f001_P, s.r324_f003_P))

# --- Rule A: HV-323605 up -> 323F010 P down; down -> up ---
base = s.r323_f010_P
s.HIC_323605 = 80.0
run(600.0)
up = s.r323_f010_P
s.HIC_323605 = 20.0
run(600.0)
dn = s.r323_f010_P
print("RULE A  HV-323605 50->80: P_f010 %.4f->%.4f (%s) ; ->20: ->%.4f (%s)" % (
    base, up, "DOWN OK" if up < base else "FAIL", dn, "UP OK" if dn > up else "FAIL"))
s.HIC_323605 = 50.0
run(600.0)

# --- Rule B: HV-329605 up -> 324F001 P down AND 323F010 P down (324F001 loop in MAN for the direct effect) ---
s.PIC_324202["mode"] = "MAN"
b1, b2 = s.r324_f001_P, s.r323_f010_P
s.HIC_329605 = 85.0
run(700.0)
print("RULE B  HV-329605 50->85: P_f001 %.4f->%.4f (%s) ; P_f010 %.4f->%.4f (%s)" % (
    b1, s.r324_f001_P, "DOWN OK" if s.r324_f001_P < b1 else "FAIL",
    b2, s.r323_f010_P, "DOWN OK" if s.r323_f010_P < b2 else "FAIL"))

# --- Rule C: HV-329606 up -> 324F003 P down (PIC-324203 in MAN for the direct effect) ---
s.PIC_324203["mode"] = "MAN"
c = s.r324_f003_P
s.HIC_329606 = 85.0
run(700.0)
print("RULE C  HV-329606 50->85: P_f003 %.4f->%.4f (%s)  [324E005 shell = same node]" % (
    c, s.r324_f003_P, "DOWN OK" if s.r324_f003_P < c else "FAIL"))
