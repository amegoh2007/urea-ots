import main, json

# settle at design (MAN seed), capture live reactor block
cap = {}
_orig = main.react_322r001
def _cap(*a, **kw):
    r = _orig(*a, **kw); cap['r'] = r; return r
main.react_322r001 = _cap
for _ in range(5):
    main.step_sim(0.1)
main.react_322r001 = _orig

r = cap['r']
MW = main.MW_COMP
feed = r['feed_kmolh']
ov   = r['overflow_kmolh']   # post f_cons/shift (== design pin at s=1)
og   = r['offgas_kmolh']
xi_u = r['xi_urea']; xi_b = r['xi_biu']

# atom counts per component: (C, N, H, O)
ATOMS = {
 "CO2":(1,0,0,2),"CH4":(1,0,4,0),"H2":(0,0,2,0),"H2O":(0,0,2,1),
 "N2":(0,2,0,0),"NH3":(0,1,3,0),"O2":(0,0,0,2),
 "Urea":(1,2,4,1),"Biuret":(2,3,5,2),
}
def atoms(vec):
    C=N=H=O=0.0
    for k,n in vec.items():
        if k not in ATOMS: continue
        c,nn,h,o = ATOMS[k]
        C+=n*c; N+=n*nn; H+=n*h; O+=n*o
    return C,N,H,O

def mass(vec): return sum(vec.get(k,0.0)*MW[k] for k in MW)

aF=atoms(feed); aO=atoms(ov); aG=atoms(og)
out_atoms=tuple(aO[i]+aG[i] for i in range(4))
print("=== DESIGN-POINT REACTOR (s=1) ===")
print("feed   :", {k:round(v,3) for k,v in feed.items() if v})
print("overflow:",{k:round(v,3) for k,v in ov.items() if v})
print("offgas :", {k:round(v,3) for k,v in og.items() if v})
print("xi_urea=%.4f  xi_biu=%.4f  X_conv=%.5f  L_feed=%.5f  W_feed=%.5f"%(
      xi_u, xi_b, r['X_conv'], r['L_feed'], r['W_feed']))
print()
print("--- ATOM BALANCE (kmol-atom/h)  [C, N, H, O] ---")
print("feed atoms in :", tuple(round(x,3) for x in aF))
print("out  atoms    :", tuple(round(x,3) for x in out_atoms))
# reactions conserve atoms, so atom residual = in - out (should be 0 if closed)
res_atoms=tuple(aF[i]-out_atoms[i] for i in range(4))
print("ATOM RESIDUAL :", tuple(round(x,4) for x in res_atoms), " (in - out)")
print()
mF=mass(feed); mO=mass(ov); mG=mass(og)
print("--- MASS BALANCE (kg/h) ---")
print("m_feed = %.4f"%mF)
print("m_ov   = %.4f"%mO)
print("m_og   = %.4f"%mG)
print("m_out  = %.4f"%(mO+mG))
print("MASS RESIDUAL (in-out) = %.4f kg/h  (%.4f %% of feed)"%(mF-(mO+mG),100*(mF-(mO+mG))/mF))
print()
print("--- MOLAR CLOSURE ---")
print("closure_resid (reported) = %.4f kmol/h"%r['closure_resid'])
print("sum feed=%.3f  sum out=%.3f  xi_urea=%.3f"%(sum(feed.values()),sum(ov.values())+sum(og.values()),xi_u))
print()
# per-component implied feed from conserved balance: feed_i = out_i - sum nu_i*xi
# urea couple: CO2+2NH3->Urea+H2O (xi_u); biuret: 2Urea->Biuret+NH3 (xi_b)
nu = {  # per reaction extent
 "urea": {"CO2":-1,"NH3":-2,"Urea":+1,"H2O":+1},
 "biu":  {"Urea":-2,"Biuret":+1,"NH3":+1},
}
print("--- PER-COMPONENT: implied_feed = out - nu*xi  vs actual feed ---")
print("%-8s %12s %12s %12s"%("comp","actual_feed","implied_feed","delta"))
for k in MW:
    outk = ov.get(k,0.0)+og.get(k,0.0)
    dlt = nu["urea"].get(k,0)*xi_u + nu["biu"].get(k,0)*xi_b
    implied = outk - dlt
    a = feed.get(k,0.0)
    if abs(a)>1e-6 or abs(implied)>1e-6:
        print("%-8s %12.3f %12.3f %12.4f"%(k,a,implied,a-implied))
