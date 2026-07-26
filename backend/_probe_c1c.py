import main
reactor = main.reactor
MW = main.MW_COMP
OVd = {k: main.REACT_OVERFLOW_DES.get(k,0.0) for k in MW}
OGd = {k: main.REACT_OFFGAS_DES.get(k,0.0) for k in MW}

# module consts the diff introduces
THETA = {k: (OGd[k]/(OVd[k]+OGd[k]) if (OVd[k]+OGd[k])>1e-12 else (1.0 if OGd[k]>0 else 0.0)) for k in MW}

ATOMS = {"CO2":(1,0,0,2),"CH4":(1,0,4,0),"H2":(0,0,2,0),"H2O":(0,0,2,1),
 "N2":(0,2,0,0),"NH3":(0,1,3,0),"O2":(0,0,0,2),"Urea":(1,2,4,1),"Biuret":(2,3,5,2)}
def atoms(v):
    r=[0.0]*4
    for k,n in v.items():
        if k in ATOMS:
            for i in range(4): r[i]+=n*ATOMS[k][i]
    return tuple(r)
def mass(v): return sum(v.get(k,0.0)*MW[k] for k in MW)

# capture design raw feed + extents/diags
cap={}
_o=main.react_322r001
def _c(*a,**k):
    r=_o(*a,**k); cap['r']=r; return r
main.react_322r001=_c
for _ in range(5): main.step_sim(0.1)
main.react_322r001=_o
feed_des=dict(cap['r']['feed_kmolh']); xiu_des=cap['r']['xi_urea']; xib_des=cap['r']['xi_biu']
# boot-pinned design state for conservative shift anchoring (== Phase-2 will make these == reactor.L0_DES/X_DES_RAW)
L_FEED_DES=cap['r']['L_feed']; W_FEED_DES=cap['r']['W_feed']; X_DES=cap['r']['X_conv']

# pin TEAR_DES exactly as boot-pin will: implied_feed = ov+og - nu*xi ; tear = feed_des - implied
def applyrxn(out, xu, xb):
    out["CO2"]-=xu; out["NH3"]-=2*xu; out["Urea"]+=xu; out["H2O"]+=xu
    out["Urea"]-=2*xb; out["Biuret"]+=xb; out["NH3"]+=xb
implied={k:OVd[k]+OGd[k] for k in MW}
_tmp={k:0.0 for k in MW}; applyrxn(_tmp,xiu_des,xib_des)
implied={k:implied[k]-_tmp[k] for k in MW}
TEAR_DES={k:feed_des.get(k,0.0)-implied[k] for k in MW}

def react_new(feed, s, T_overflow_c, L_drive=None, W_drive=None):
    xi_urea,_ov,X_conv,L_feed,W_feed = reactor.react_couple(
        feed, dict(OVd), main.REACT_XI_UREA_DES*s, T_overflow_c, L_override=L_drive, W_override=W_drive)
    xi_biu = main.REACT_XI_BIU_DES*s
    fc={k:feed.get(k,0.0)-TEAR_DES[k]*s for k in MW}
    xi_urea=max(min(xi_urea, fc.get("CO2",0.0), 0.5*fc.get("NH3",0.0)),0.0)
    xi_biu =max(min(xi_biu, 0.5*(fc.get("Urea",0.0)+xi_urea)),0.0)
    out={k:fc[k] for k in MW}; applyrxn(out,xi_urea,xi_biu)
    overflow={k:out[k]*(1.0-THETA[k]) for k in MW}
    offgas  ={k:out[k]*THETA[k]       for k in MW}
    nh3_shift=main.REACT_NC_OVERFLOW_GAIN*(L_feed/L_FEED_DES-1.0)*OVd["NH3"]*s
    nh3_shift=max(min(nh3_shift,0.9*offgas["NH3"]),-0.5*overflow["NH3"])
    overflow["NH3"]+=nh3_shift; offgas["NH3"]-=nh3_shift
    delta_X=max(1.0-X_conv/X_DES,0.0); g=main.REACT_OFFGAS_DEFICIT_GAIN*delta_X
    for k in ("NH3","CO2"):
        sh=min(g*offgas[k],overflow[k]); offgas[k]+=sh; overflow[k]-=sh
    cr=sum(fc.values())-xi_urea-(sum(overflow.values())+sum(offgas.values()))
    return fc,overflow,offgas,xi_urea,xi_biu,cr,X_conv,L_feed

print("="*64);print("FINAL PROPOSED react_322r001 — BASELINE REGRESSION");print("="*64)
fc,ov,og,xu,xb,cr,X,L=react_new(feed_des,1.0,main.REACT_OVERFLOW_T_C,L_drive=L_FEED_DES,W_drive=W_FEED_DES)
print("\n[1] DESIGN s=1 vs published  (driven L/W = design seed; X_conv=%.5f L_feed=%.5f -> shifts must be 0)"%(X,L))
print("  fresh xi_urea=%.6f  captured xiu_des=%.6f  d=%.3e"%(xu,xiu_des,xu-xiu_des))
print("  fresh xi_biu =%.6f  captured xib_des=%.6f  d=%.3e"%(xb,xib_des,xb-xib_des))
mo=mi=0.0
for k in MW:
    eo=ov[k]-OVd[k]; eg=og[k]-OGd[k]
    if abs(eo)>1e-4 or abs(eg)>1e-4: print("   %-8s ov_err=%+.4e og_err=%+.4e"%(k,eo,eg))
    if abs(OVd[k])>1e-9 or abs(OGd[k])>1e-9: mo=max(mo,abs(eo)); mi=max(mi,abs(eg))
print("  max|ov-ov_pub|=%.3e  max|og-og_pub|=%.3e kmol/h"%(mo,mi))
print("  closure_resid=%.3e kmol/h"%cr)

# [1b] SHIPPING INVARIANT: partition the CAPTURED xi (xi_live==xi_pin, as guaranteed in-situ)
fcb={k:feed_des.get(k,0.0)-TEAR_DES[k] for k in MW}
outb={k:fcb[k] for k in MW}; applyrxn(outb,xiu_des,xib_des)
ovb={k:outb[k]*(1.0-THETA[k]) for k in MW}; ogb={k:outb[k]*THETA[k] for k in MW}
mob=mob2=0.0
for k in MW:
    eo=ovb[k]-OVd[k]; eg=ogb[k]-OGd[k]
    if abs(OVd[k])>1e-9 or abs(OGd[k])>1e-9: mob=max(mob,abs(eo)); mob2=max(mob2,abs(eg))
print("\n[1b] SHIPPING INVARIANT (xi_live==xi_pin==captured): partition vs published")
print("  max|ov-ov_pub|=%.3e  max|og-og_pub|=%.3e kmol/h  <- BIT-EXACT"%(mob,mob2))

def chk(tag,feed,s,**kw):
    fc,ov,og,xu,xb,cr,X,L=react_new(feed,s,main.REACT_OVERFLOW_T_C,**kw)
    a_in=atoms(fc); a_out=tuple(atoms(ov)[i]+atoms(og)[i] for i in range(4))
    print("\n[%s] s=%.2f mass_resid=%+.3e kg/h  atom_resid[C,N,H,O]=%s  closure=%.2e"%(
        tag,s,mass(fc)-(mass(ov)+mass(og)),tuple(round(a_in[i]-a_out[i],8) for i in range(4)),cr))
chk("2 design",feed_des,1.0)
chk("3 turndown70",{k:feed_des.get(k,0.0)*0.7 for k in MW},0.7)
fp={k:feed_des.get(k,0.0) for k in MW};fp["NH3"]*=1.15;fp["CO2"]*=0.85
chk("4 NH3-rich",fp,1.0)
fl={k:feed_des.get(k,0.0) for k in MW};fl["CO2"]*=0.3;fl["NH3"]*=0.6   # severe CO2-lean (extent clamp active)
chk("5 CO2-lean",fl,0.5)
