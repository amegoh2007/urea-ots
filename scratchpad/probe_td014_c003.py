"""TD-014 step 2 -- the ramp is BORN in 323C003, not carried in.

probe_td014_trace.py showed the stripper bottoms (stream 208) is bit-flat for 6 h while w_c003
falls at -0.0041 pp/h.  A CSTR with tau = 2 min and constant inputs converges in ~10 min, so
either an input to the C003 species balance is itself ramping, or the balance has a term that
does not close.

This probe intercepts sol_advance and records the ACTUAL arguments of the C003 call every tick,
then reports which of them moves.  It also solves the stage's own algebraic steady state from
those same arguments and compares it with the integrated state: if the two track each other the
ramp is input-driven; if they separate the balance itself is leaking.
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
SAMPLE_MIN = 15.0

_orig = M.sol_advance
_calls = []


def spy(w, M_pre, M_new, m_in, w_in, m_vap, y, m_liq, xi, dt, m_in2=0.0, w_in2=None):
    _calls.append(dict(M_pre=M_pre, M_new=M_new, m_in=m_in, w_in=dict(w_in), m_vap=m_vap,
                       y=dict(y), m_liq=m_liq, xi=xi, m_in2=m_in2,
                       w_in2=(dict(w_in2) if w_in2 else None), w=dict(w)))
    return _orig(w, M_pre, M_new, m_in, w_in, m_vap, y, m_liq, xi, dt, m_in2, w_in2)


M.sol_advance = spy
s = M.state


def ss_urea(c):
    """Algebraic steady state of the C003 stage for urea, from the captured arguments.
       0 = m_in*w_in - m_vap*y - m_liq*w  + nu*xi  ->  w = (m_in*w_in - m_vap*y + nu*xi)/m_liq
       y is frozen at the captured value (it is an explicit function of the previous w)."""
    nu = 2.0 * -M.MW_SOL["Urea"]
    num = c["m_in"] * c["w_in"]["Urea"] - c["m_vap"] * c["y"]["Urea"] + nu * c["xi"]
    return num / c["m_liq"] if c["m_liq"] > 1e-9 else float("nan")


def total_resid(c):
    """kg/h of TOTAL mass the species balance implies vs the total-mass ODE's own dM/dt."""
    gen = 0.0
    for k in M.SOL_SPECIES:
        nu = (2.0 * -M.MW_SOL["Urea"] if k == "Urea" else
              M.MW_SOL["Biuret"] if k == "Biuret" else
              M.MW_SOL["NH3"] if k == "NH3" else 0.0)
        gen += nu * c["xi"]
    return c["m_in"] + c["m_in2"] - c["m_vap"] - c["m_liq"] + gen


n_per = int(SAMPLE_MIN * 60.0 / DT)
n_tot = int(HOURS * 3600.0 / DT)
done = 0
print("%6s %10s %10s %10s %11s %11s %11s %10s %10s %9s"
      % ("t_h", "w_c003", "ss_alg", "xi", "m_in", "m_vap", "m_liq", "M_pre", "T", "y_urea"))
while done < n_tot:
    for _ in range(n_per):
        _calls.clear()
        M.step_sim(DT)
    done += n_per
    c = _calls[0]                       # first sol_advance of the tick == 323C003
    print("%6.2f %10.5f %10.5f %10.6f %11.2f %11.4f %11.2f %10.1f %10.5f %9.6f"
          % (done * DT / 3600.0, 100.0 * s.w_c003["Urea"], 100.0 * ss_urea(c), c["xi"],
             c["m_in"], c["m_vap"], c["m_liq"], c["M_pre"], s.r323_c003_T,
             100.0 * c["y"]["Urea"]))

print()
c = _calls[0]
print("last-tick C003 argument dump")
for k in ("M_pre", "M_new", "m_in", "m_vap", "m_liq", "xi", "m_in2"):
    print("   %-8s %r" % (k, c[k]))
print("   total-mass residual of the species terms: %.6f kg/h" % total_resid(c))
print("   w_in  (stream 208 renormalised) :", {k: round(100.0 * v, 5) for k, v in c["w_in"].items()})
print("   y_305 (top vapour)              :", {k: round(100.0 * v, 5) for k, v in c["y"].items()})
print("   design anchors")
print("     W_S314 urea %.6f   xi_des %.6f   M_des %.2f   T_des %.2f"
      % (100.0 * M.W_S314["Urea"], M.SOL_C003["xi"], M.R323_C003_M_DES, M.R323_C003_T_SP_C))
print("     W_S208 urea %.6f   y_305_des urea %.6f  m305_des %.4f  m314_des %.2f  feed_des %.2f"
      % (100.0 * M.W_S208["Urea"], 100.0 * M.SOL_C003["y"]["Urea"],
         M.R323_M305_DES, M.R323_M314_DES, M.R323_FEED_DES_KGH))
