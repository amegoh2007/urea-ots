# H-1 seed-stationarity probe: does the MAN design seed settle to a fixed point where
#   W_feed -> reactor.W0_DES, conv_fac -> 1.0, and all temporal derivatives -> 0?
# (W_feed/L_feed/conv_fac are tear-independent -> post-import trajectory == boot-capture trajectory.)
import main
reactor = main.reactor
W0 = reactor.W0_DES; L0 = reactor.L0_DES; XR = reactor.X_DES_RAW

cap = {}
_o = main.react_322r001
def _c(*a, **k):
    r = _o(*a, **k); cap['r'] = r; return r
main.react_322r001 = _c

main.state = main.State()                 # fresh MAN design seed (same kind boot captures)
s = main.state

def snap():
    r = cap['r']
    return dict(W=r["W_feed"], L=r["L_feed"], X=r["X_conv"],
                cf=r["X_conv"]/XR,
                lvl=s.react_level_pct, T=list(s.react_T_node),
                Lrec=s.react_L_rec, Wrec=s.react_W_rec, conv=s.react_conv_fac)

main.step_sim(0.1); prev = snap()
TICK1 = dict(prev)                        # what the CURRENT boot captures (single tick)

hist = []
for i in range(2, 40001):
    main.step_sim(0.1); cur = snap()
    dW = cur["W"]-prev["W"]; dL = cur["L"]-prev["L"]; dcf = cur["cf"]-prev["cf"]
    dlvl = cur["lvl"]-prev["lvl"]
    dT = max(abs(cur["T"][n]-prev["T"][n]) for n in range(4))
    hist.append((i, cur, dW, dL, dcf, dlvl, dT))
    prev = cur

main.react_322r001 = _o

print("="*78)
print("H-1 SEED-STATIONARITY PROBE  (per-tick dt=0.1 s, fresh MAN design seed)")
print("="*78)
print("\nreactor design fixed points:  W0_DES=%.8f  L0_DES=%.8f  X_DES_RAW=%.8f" % (W0, L0, XR))
print("\n[CURRENT BOOT = tick 1 capture]")
print("  W_FEED  =%.8f   (W0_DES=%.8f   Delta=%+.3e)" % (TICK1["W"], W0, TICK1["W"]-W0))
print("  L_FEED  =%.8f   (L0_DES=%.8f   Delta=%+.3e)" % (TICK1["L"], L0, TICK1["L"]-L0))
print("  conv_fac=%.9f  (target 1.0    Delta=%+.3e)" % (TICK1["cf"], TICK1["cf"]-1.0))

print("\n[SETTLE TRAJECTORY -> approach to fixed point]")
print("  %8s %14s %14s %15s %12s %12s" % ("tick", "W_feed", "conv_fac", "dW/dt", "dlvl/dt", "dT_max/dt"))
for tk in (2, 10, 50, 200, 1000, 5000, 10000, 20000, 30000, 40000):
    rec = next(h for h in hist if h[0] == tk)
    i, cur, dW, dL, dcf, dlvl, dT = rec
    print("  %8d %14.8f %14.9f %15.3e %12.3e %12.3e" % (
        i, cur["W"], cur["cf"], dW/0.1, dlvl/0.1, dT/0.1))

fin = hist[-1][1]
print("\n[SETTLED FIXED POINT @ tick %d]" % hist[-1][0])
print("  W_feed  =%.8f   (W0_DES=%.8f   Delta=%+.3e)" % (fin["W"], W0, fin["W"]-W0))
print("  L_feed  =%.8f   (L0_DES=%.8f   Delta=%+.3e)" % (fin["L"], L0, fin["L"]-L0))
print("  conv_fac=%.9f  (target 1.0    Delta=%+.3e)" % (fin["cf"], fin["cf"]-1.0))
print("  react_W_rec=%.8f  react_L_rec=%.8f  react_conv_fac=%.9f" % (fin["Wrec"], fin["Lrec"], fin["conv"]))

last = hist[-1]
print("\n[TEMPORAL DERIVATIVES @ settled tick %d]" % last[0])
print("  dW_feed/dt =%+.3e /s" % (last[2]/0.1))
print("  dL_feed/dt =%+.3e /s" % (last[3]/0.1))
print("  dconv_fac/dt=%+.3e /s" % (last[4]/0.1))
print("  dlevel/dt  =%+.3e %%/s" % (last[5]/0.1))
print("  dT_max/dt  =%+.3e C/s" % (last[6]/0.1))
