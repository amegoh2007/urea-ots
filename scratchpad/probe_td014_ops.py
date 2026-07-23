"""TD-014 step 3 -- confirm the mechanism: an OPEN-LOOP temperature integrator.

Structural claim.  For 323C003 the code back-solves

    R323_LAMBDA_305 = Q305_DES / (M305_DES/3600)          (main.py:916)

and then, in the tick, takes the ENERGY-limited branch

    m_305   = M305_DES * (q_avail / Q305_DES)
    P_c003  = q_avail - m_305/3600*LAMBDA_305
            = q_avail * (1 - M305_DES*LAMBDA_305/(3600*Q305_DES))
            = q_avail * (1 - 1)
            = 0                                            IDENTICALLY, for every q_avail.

So while that branch binds the column temperature has NO input at all: whatever TIC-323007 does to
the reboiler duty is exactly cancelled by the boil-up it produces.  The controller is integrating
against a plant with zero gain, so its velocity-form integral term walks forever on the residual
1e-5 C offset left by the boot settle -- and because the increment is Kc*(dt/Ti)*err, the walk RATE
is independent of dt, which is exactly the tick-invariance measured in TD-014.

The same cancellation exists at 323F010, 324E001 and 324E003.  323F004 is NOT affected: it keeps a
bubble-point relaxation term, so its P is q_relax rather than 0.

This probe prints the four steam-valve strokes and the branch selector for each stage.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)
import main as M  # noqa: E402

DT = float(os.environ.get("PROBE_DT", "1.0"))
HOURS = float(os.environ.get("PROBE_H", "4.0"))
s = M.state

n_per = int(15.0 * 60.0 / DT)
n_tot = int(HOURS * 3600.0 / DT)
done = 0
print("%6s %9s %9s %9s %9s %9s %11s %11s %11s"
      % ("t_h", "PIC02_op", "PIC08_op", "PIC203_op", "PIC212_op", "T_c003", "T_f010",
         "T_e001", "T_e003"))
while done < n_tot:
    for _ in range(n_per):
        tel = M.step_sim(DT)
    done += n_per
    print("%6.2f %9.5f %9.5f %9.5f %9.5f %9.5f %11.5f %11.5f %11.5f"
          % (done * DT / 3600.0, s.PIC_329202["op"], s.PIC_329208["op"], s.PIC_329203["op"],
             s.PIC_329212["op"], s.r323_c003_T, s.r323_f010_T, s.r324_e001_T, s.r324_e003_T))

print()
print("setpoints: TIC_323007 %.4f  TIC_323012 %.4f  TIC_324001 %.4f  TIC_324002 %.4f"
      % (s.TIC_323007["sp"], s.TIC_323012["sp"], s.TIC_324001["sp"], s.TIC_324002["sp"]))
print("design strokes: E002 %.1f  E010 %.1f  E001 %.1f  E003 %.1f"
      % (M.R323_E002_OP_DES, M.R323_E010_OP_DES, M.R324_E001_OP_DES, M.R324_E003_OP_DES))
print()
print("structural identity check (must be 1.0 for a degenerate stage):")
print("  323C003  M305_DES*LAM305/(3600*Q305_DES) = %.15f"
      % (M.R323_M305_DES * M.R323_LAMBDA_305 / (3600.0 * M.R323_Q305_DES_KW)))
print("  323F010  MEVAP_DES*LAM_EVAP/(3600*QEVAP_DES) = %.15f"
      % (M.R323_MEVAP_DES * M.R323_EVAP_LAMBDA / (3600.0 * M.R323_QEVAP_DES_KW)))
print("  324E001  V1_DES*LAM_V1/(3600*Q1_DES) = %.15f"
      % (M.R324_V1_DES * M.R324_LAM_V1 / (3600.0 * M.R324_Q1_DES_KW)))
print("  324E003  V2_DES*LAM_V2/(3600*Q2_DES) = %.15f"
      % (M.R324_V2_DES * M.R324_LAM_V2 / (3600.0 * M.R324_Q2_DES_KW)))
print("  323F004  M701_DES*LAM701/(3600*Q701_DES) = %.15f  (has a relax term, so P = q_relax)"
      % (M.R323_M701_DES * M.R323_LAMBDA_701 / (3600.0 * M.R323_Q701_DES_KW)))
