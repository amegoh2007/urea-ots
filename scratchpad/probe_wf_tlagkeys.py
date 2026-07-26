"""READ-ONLY: does s.tlag actually carry a key 'R323_m317'?  scratchpad/probe_td013.py -- the
probe cited by EQUATION_AUDIT.md / TECH_DEBT.md for the retraction -- drives its 'unpinned' shadow
tank with  m_in = s.tlag.get('R323_m317', 0.0) or 0.0 ."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main as M  # noqa

for _ in range(400):
    M.step_sim(0.25)
s = M.state
print("tlag keys after 100 s:", sorted(s.tlag.keys()))
print("'R323_m317' present  :", "R323_m317" in s.tlag)
print("value used by probe_td013.py:", s.tlag.get("R323_m317", 0.0) or 0.0)

# what sol_advance returns with that m_in
w = dict(s.w_d002)
w2 = M.sol_advance(w, s.r323_d002_M_I, s.r323_d002_M_I, 0.0, s.w_f010, 0.0, w, 0.0, 0.0, 0.25)
print("sol_advance(..., m_in=0.0, m_liq=0.0, xi=0.0) changes anything? ",
      any(abs(w2[k] - w[k]) > 0.0 for k in M.SOL_SPECIES))
print("  in :", {k: round(v, 12) for k, v in w.items()})
print("  out:", {k: round(v, 12) for k, v in w2.items()})
