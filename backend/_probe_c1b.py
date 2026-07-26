import main

MW = main.MW_COMP
OVd = {k: main.REACT_OVERFLOW_DES.get(k,0.0) for k in MW}
OGd = {k: main.REACT_OFFGAS_DES.get(k,0.0) for k in MW}
XIu = main.REACT_XI_UREA_DES
XIb = main.REACT_XI_BIU_DES

ATOMS = {"CO2":(1,0,0,2),"CH4":(1,0,4,0),"H2":(0,0,2,0),"H2O":(0,0,2,1),
 "N2":(0,2,0,0),"NH3":(0,1,3,0),"O2":(0,0,0,2),"Urea":(1,2,4,1),"Biuret":(2,3,5,2)}
def atoms(v):
    r=[0.0]*4
    for k,n in v.items():
        if k in ATOMS:
            for i in range(4): r[i]+=n*ATOMS[k][i]
    return tuple(r)
def mass(v): return sum(v.get(k,0.0)*MW[k] for k in MW)

# reaction stoichiometry per extent
def react_delta(xu, xb):
    d={k:0.0 for k in MW}
    d["CO2"]+=-xu; d["NH3"]+=-2*xu; d["Urea"]+=xu; d["H2O"]+=xu          # urea couple
    d["Urea"]+=-2*xb; d["Biuret"]+=xb; d["NH3"]+=xb                       # biuret
    return d

# capture design raw feed (live)
cap={}
_o=main.react_322r001
def _c(*a,**k):
    r=_o(*a,**k); cap['r']=r; return r
main.react_322r001=_c
for _ in range(5): main.step_sim(0.1)
main.react_322r001=_o
feed_des = dict(cap['r']['feed_kmolh'])
xiu_des  = cap['r']['xi_urea']; xib_des = cap['r']['xi_biu']

# ---- pinned design constants for proposed rebuild ----
# implied (closed) design feed that makes out == published exactly
d_des = react_delta(xiu_des, xib_des)
IMPLIED_FEED = {k: (OVd[k]+OGd[k]) - d_des[k] for k in MW}
TEAR_DES = {k: feed_des.get(k,0.0) - IMPLIED_FEED[k] for k in MW}       # recycle-tear vector (pinned)
THETA = {k: (OGd[k]/(OVd[k]+OGd[k]) if (OVd[k]+OGd[k])>1e-12 else (1.0 if OGd[k]>0 else 0.0))
         for k in MW}

def react_new(feed, xiu, xib, s):
    fc = {k: feed.get(k,0.0) - TEAR_DES[k]*s for k in MW}               # feed corrected (tear explicit)
    d  = react_delta(xiu, xib)
    out_total = {k: fc[k] + d[k] for k in MW}
    overflow = {k: out_total[k]*(1.0-THETA[k]) for k in MW}
    offgas   = {k: out_total[k]*THETA[k]       for k in MW}
    return fc, overflow, offgas, out_total

print("="*64)
print("PROPOSED CONSERVING REBUILD — BASELINE REGRESSION")
print("="*64)

# ---- (1) DESIGN POINT s=1: must reproduce published overflow/offgas bit-exact ----
fc, ov, og, ot = react_new(feed_des, xiu_des, xib_des, 1.0)
print("\n[1] DESIGN s=1 : new overflow/offgas vs published REACT_*_DES")
print("%-8s %12s %12s %12s %12s"%("comp","ov_new","ov_pub","og_new","og_pub"))
max_ov=max_og=0.0
for k in MW:
    if abs(OVd[k])>1e-9 or abs(OGd[k])>1e-9 or abs(ov[k])>1e-9 or abs(og[k])>1e-9:
        eo=ov[k]-OVd[k]; eg=og[k]-OGd[k]; max_ov=max(max_ov,abs(eo)); max_og=max(max_og,abs(eg))
        print("%-8s %12.4f %12.4f %12.4f %12.4f"%(k,ov[k],OVd[k],og[k],OGd[k]))
print("max|overflow err| = %.3e   max|offgas err| = %.3e kmol/h"%(max_ov,max_og))

def report(tag, feed, xiu, xib, s):
    fc, ov, og, ot = react_new(feed, xiu, xib, s)
    mi=mass(fc); mo=mass(ov)+mass(og)
    ai=atoms(fc); ao=tuple(atoms(ov)[i]+atoms(og)[i] for i in range(4))
    print("\n[%s] s=%.2f"%(tag,s))
    print("  mass_in(corrected)=%.6f  mass_out=%.6f  RESID=%.3e kg/h"%(mi,mo,mi-mo))
    print("  atom RESID [C,N,H,O] = %s kmol-atom/h"%(tuple(round(ai[i]-ao[i],9) for i in range(4)),))

# ---- (2) conservation at design ----
report("2",feed_des,xiu_des,xib_des,1.0)

# ---- (3) conservation off-design: synthetic 70% turndown feed (scale raw feed by 0.7) ----
feed70={k:feed_des.get(k,0.0)*0.7 for k in MW}
report("3",feed70,xiu_des*0.7,xib_des*0.7,0.7)

# ---- (4) conservation under arbitrary perturbed feed (NH3-rich, off-stoich) ----
fp={k:feed_des.get(k,0.0) for k in MW}; fp["NH3"]*=1.15; fp["CO2"]*=0.9
report("4-NH3rich",fp,xiu_des,xib_des,1.0)

print("\n--- TEAR_DES (explicit recycle-tear diagnostic, pinned) kmol/h ---")
print({k:round(v,4) for k,v in TEAR_DES.items() if abs(v)>1e-6})
print("tear mass = %.4f kg/h"%mass(TEAR_DES))
