"""328E021 HOT-side (stream 749) design-anchor exactness probe.

Checks that the conservation-exact hot-outlet form

    T_749 = T_c003 - [ m_746*(T_746 - T_c002) + LOSS_DT ] / m_749
    LOSS_DT = m_747_des*(T747_des - T749_des) - m_746_des*(T746_des - T743_des)   [kg.K/h]

reproduces the design anchor 148.0 C BIT-EXACTLY at the design state, so the
boot pin cannot move when sens_c004 is switched from the frozen constant to it.
"""
import os, sys
BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND))
os.chdir(os.path.abspath(BACKEND))
import main as M

m746 = M.R328_C003_M746_DES
m749 = M.R328_C004_M749_DES
Tc002 = M.R328_C002_T_BOT
T746 = M.R328_C003_T746
Tc003 = M.R328_C003_T
T749 = M.R328_C004_T749

print("m_746_des", repr(m746), " m_749_des", repr(m749))
print("T_c002", repr(Tc002), "T_746", repr(T746), "T_c003", repr(Tc003), "T_749", repr(T749))

LOSS_DT = m749 * (Tc003 - T749) - m746 * (T746 - Tc002)
print("LOSS_DT (kg.K/h)", repr(LOSS_DT), " -> kW", repr(LOSS_DT / 3600.0 * M.R328_CP))

# live form evaluated at the design state
T749_live = Tc003 - (m746 * (T746 - Tc002) + LOSS_DT) / m749
print("T_749 live @design", repr(T749_live), " exact:", T749_live == T749)

# cold-side leg used by the live form: T_746 from EPS_T at design
T746_live = Tc002 + M.R328_E021_EPS_T * (Tc003 - Tc002)
print("T_746 live @design", repr(T746_live), " exact:", T746_live == T746)

# and the composed pair (T_746 live feeding T_749 live)
T749_comp = Tc003 - (m746 * (T746_live - Tc002) + LOSS_DT) / m749
print("T_749 composed   ", repr(T749_comp), " exact:", T749_comp == T749)
