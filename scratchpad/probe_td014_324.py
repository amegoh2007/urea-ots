"""TD-014 step 4 -- 323 arrested, 324 did not.  Which branch is 324E001 on?

After the bubble-point closure went in, PIC-329202 and PIC-329208 froze (323 fixed) but PIC-329203
and PIC-329212 still walk down while T_e001 stays at 130.00000 to five decimals.  Two candidate
explanations: (a) the CONCENTRATION branch binds, so v1_m is independent of duty and the surplus
duty should show up as dT/dt -- but it does not; or (b) the DUTY branch binds but the melt
composition is clamped to the design target anyway, so the bubble point cannot move and the new
relax term is identically zero -- an open integrator again, for a different reason.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main as M  # noqa: E402

DT = float(os.environ.get("PROBE_DT", "1.0"))
HOURS = float(os.environ.get("PROBE_H", "3.0"))
s = M.state

n_per = int(15.0 * 60.0 / DT)
n_tot = int(HOURS * 3600.0 / DT)
done = 0
print("%6s %9s %9s %9s %9s %9s %9s %9s %9s"
      % ("t_h", "v1_th", "w1_pct", "e001_ure", "P_324202", "Q_e001", "T_e001",
         "w2_pct", "T_e003"))
while done < n_tot:
    for _ in range(n_per):
        tel = M.step_sim(DT)
    done += n_per
    e1 = tel["EVAP_324"]["E001"]
    e3 = tel["EVAP_324"]["E003"]
    sp = tel["SPECIES_323_324"]["liq"]
    print("%6.2f %9.3f %9.4f %9.4f %9.5f %9.1f %9.5f %9.4f %9.5f"
          % (done * DT / 3600.0, e1["vapour_th"], e1["urea_pct"], sp["E001"]["Urea"],
             s.r324_f001_P, e1["Q_kW"], s.r324_e001_T, e3["urea_pct"], s.r324_e003_T))

print()
print("design: W_EV1 %.6f  W_EV2 %.6f  V1_DES %.2f  V2_DES %.2f"
      % (M.R324_W_EV1, M.R324_W_EV2, M.R324_V1_DES, M.R324_V2_DES))
print("TBUB anchors: E001 %.4f  E003 %.4f  F010 %.4f"
      % (M.R324_E001_TBUB_DES, M.R324_E003_TBUB_DES, M.R323_F010_TBUB_DES))
print("live bubble points: E001 %.6f   E003 %.6f"
      % (M.bubble_T_raoult(s.r324_f001_P, s.w_e001),
         M.bubble_T_raoult(s.r324_f003_P, s.w_e003)))
