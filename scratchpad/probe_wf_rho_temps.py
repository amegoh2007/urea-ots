"""READ-ONLY probe: temperature excursion envelope of every vessel that sources a
VOLUMETRIC-FIC stream, under OTS-style disturbances.  Writes nothing to backend/.

Streams / frozen densities under test
  401(734)/791/793  <- 328D003 Comp I    s.a328_d003_TI   (PFD 56 C, rho 992.4)
  755               <- 328D003 Comp II   s.a328_d003_TII  (PFD 40 C, rho 1005)
  718/718A/718B     <- 323D011           s.r3232_e011_T   (PFD 45 C, rho 1065)
  775 / 776         <- 328D001           s.a328_d001_T    (PFD 61 C, rho 1095)
  744               <- 323E003 (T-30)    s.r3232_e003_T   (PFD 44 C, rho 1002.48)
  743               <- 328C002           s.a328_c002_T    (PFD 139 C, rho 933)
  739/741           <- 328C004           s.a328_c004_T    (PFD 143 C, rho 923.28)
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
os.chdir(BACKEND); sys.path.insert(0, BACKEND)
import main

s = main.state
DT = 0.5
DES_CO2 = 54.618

T_STATES = {
    "CompI_TI  (734/791/793)": lambda: s.a328_d003_TI,
    "CompII_TII(755)":         lambda: s.a328_d003_TII,
    "D011_T    (718A/718B)":   lambda: s.r3232_e011_T,
    "D001_T    (775/776)":     lambda: s.a328_d001_T,
    "E003_T    (744 = T-30)":  lambda: s.r3232_e003_T,
    "C002_T    (743)":         lambda: s.a328_c002_T,
    "C004_T    (739/741)":     lambda: s.a328_c004_T,
}
DESIGN = {
    "CompI_TI  (734/791/793)": 56.0,
    "CompII_TII(755)":         44.0,
    "D011_T    (718A/718B)":   45.0,
    "D001_T    (775/776)":     61.0,
    "E003_T    (744 = T-30)":  74.0,
    "C002_T    (743)":         139.0,
    "C004_T    (743)":         143.0,
}

def fresh():
    main.state = main.State()
    globals()['s'] = main.state
    main.step_sim(DT)
    return main.state

def run(label, dur_s, setup=None, ramp=None):
    """ramp = (attr, start, target, ramp_s)"""
    st = main.state
    env = {k: [1e30, -1e30] for k in T_STATES}
    if setup: setup(st)
    n = int(dur_s / DT)
    for i in range(n):
        if ramp:
            attr, a, b, rs = ramp
            f = min(1.0, (i * DT) / rs) if rs > 0 else 1.0
            setattr(st, attr, a + (b - a) * f)
        main.step_sim(DT)
        for k, fn in T_STATES.items():
            v = fn()
            if v < env[k][0]: env[k][0] = v
            if v > env[k][1]: env[k][1] = v
    return label, env

RESULTS = []

# --- 0. design hold (2 h) : is anything moving at all? ---
fresh()
RESULTS.append(run("design hold 2h", 7200))

# --- 1. load turndown 100 -> 70 % over 30 min, hold 60 min ---
fresh()
RESULTS.append(run("load 100->70% (30min ramp + 60min hold)", 5400,
                   ramp=("F_CO2_raw_th", DES_CO2, 0.70 * DES_CO2, 1800.0)))

# --- 2. load turndown 100 -> 50 % ---
fresh()
RESULTS.append(run("load 100->50%", 5400,
                   ramp=("F_CO2_raw_th", DES_CO2, 0.50 * DES_CO2, 1800.0)))

# --- 3. load uprate 100 -> 110 % ---
fresh()
RESULTS.append(run("load 100->110%", 5400,
                   ramp=("F_CO2_raw_th", DES_CO2, 1.10 * DES_CO2, 1800.0)))

# --- 4. 328E004 reflux-condenser CW loss (TIC-328002 to MAN 0 %) : D001 heats up ---
def cw_loss(st):
    st.TIC_328002["mode"] = "MAN"; st.TIC_328002["op"] = 10.0
fresh(); RESULTS.append(run("328E004 CW throttled to 10% (TIC-328002 MAN)", 3600, setup=cw_loss))

# --- 5. 323E003 tempered-water TIC-323013 SP +10 C : E003/744 heats up ---
def tw_up(st):
    st.TIC_323013["sp"] = 65.0
fresh(); RESULTS.append(run("TIC-323013 SP 55->65 C (tempered water hot)", 3600, setup=tw_up))

# --- 6. 323E003 tempered-water TIC-323013 SP -15 C ---
def tw_dn(st):
    st.TIC_323013["sp"] = 40.0
fresh(); RESULTS.append(run("TIC-323013 SP 55->40 C (tempered water cold)", 3600, setup=tw_dn))

# --- 7. FIC-328402 (744) SP step -20 % : the volumetric loop itself is disturbed ---
def f402(st):
    st.FIC_328402["sp"] = st.FIC_328402["sp"] * 0.8
fresh(); RESULTS.append(run("FIC-328402 SP -20%", 3600, setup=f402))

# --- 8. LP-steam FIC-329401 to MAN 30 % : desorber-II cools ---
def lp_cut(st):
    st.FIC_329401["mode"] = "MAN"; st.FIC_329401["op"] = 30.0
fresh(); RESULTS.append(run("FIC-329401 LP steam MAN 30%", 3600, setup=lp_cut))

# --- 9. 322P002 trip (755 draw stops) ---
def p002_trip(st):
    st.aux_pumps["322P002A"]["on"] = False
    st.aux_pumps["322P002B"]["on"] = False
fresh(); RESULTS.append(run("322P002 A/B trip (755 draw = 0)", 1800, setup=p002_trip))

# ---------- report ----------
agg = {k: [1e30, -1e30] for k in T_STATES}
print("=" * 108)
for label, env in RESULTS:
    print("\n### %s" % label)
    for k in T_STATES:
        lo, hi = env[k]
        d = DESIGN.get(k, float('nan'))
        print("    %-26s  min %9.3f  max %9.3f   span %7.3f   dev-from-des %+8.3f / %+8.3f"
              % (k, lo, hi, hi - lo, lo - d, hi - d))
        agg[k][0] = min(agg[k][0], lo); agg[k][1] = max(agg[k][1], hi)

print("\n" + "=" * 108)
print("AGGREGATE ENVELOPE OVER ALL DISTURBANCES")
for k in T_STATES:
    lo, hi = agg[k]
    d = DESIGN.get(k, float('nan'))
    print("    %-26s  [%9.3f , %9.3f]  span %8.3f K   (design %6.1f)"
          % (k, lo, hi, hi - lo, d))
json.dump({k: agg[k] for k in agg}, open(os.path.join(HERE, "probe_wf_rho_temps.json"), "w"), indent=2)
