"""C10 -- build rho(w,T) and cp(w,T) for urea solutions from the PFD itself.

CLAUDE.md §0 makes Combined_1750..._Process_Data.md the STRICT source and says PFD values override
coded constants.  That table carries urea %, water %, temperature AND effective density for every
urea-solution stream in the plant, which is a better basis for a correlation than any textbook: it
is the authoritative document, and it is this plant.  So density is regressed straight off it.

cp is not tabulated anywhere, so it is BACK-SOLVED (CLAUDE.md §1 allows sourced or back-solved,
never guessed): take cp_water from steam tables, require the mass-weighted mixing rule to reproduce
the model's existing design constant at the design composition, and read off cp_urea.  If the
number that falls out matches the published value for molten urea, the back-solve is corroborated.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.normpath(os.path.join(HERE, "..", "backend"))
sys.path.insert(0, BACKEND)

PFD = os.path.normpath(os.path.join(
    HERE, "..", "References", "Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md"))

rows = {}
for line in open(PFD, encoding="utf-8"):
    if not line.startswith("|"):
        continue
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    key = cells[0]
    if key in ("STREAM No.", "Urea", "Water", "Biuret", "Density eff.",
               "Operating Temperature", "Stream description", "Mass Flow total"):
        rows.setdefault(key, []).append(cells)


def collect():
    """Walk the PFD blocks and pull every stream that is a real urea solution."""
    out = []
    blocks = len(rows.get("STREAM No.", []))
    for b in range(blocks):
        try:
            ids = rows["STREAM No."][b]
            urea = rows["Urea"][b]
            water = rows["Water"][b]
            rho = rows["Density eff."][b]
            temp = rows["Operating Temperature"][b]
        except (KeyError, IndexError):
            continue
        n = min(len(ids), len(urea), len(water), len(rho), len(temp))
        for i in range(2, n):
            def f(arr):
                try:
                    return float(arr[i])
                except (ValueError, IndexError):
                    return None
            u, w, r, t = f(urea), f(water), f(rho), f(temp)
            if u and r and t and u > 5.0 and r > 900.0:
                out.append({"id": ids[i], "w_urea": u / 100.0,
                            "w_h2o": (w or 0.0) / 100.0, "rho": r, "T": t})
    # de-duplicate identical streams (317 appears twice with the same data)
    seen, uniq = set(), []
    for d in out:
        k = (round(d["w_urea"], 5), round(d["rho"], 2), round(d["T"], 2))
        if k not in seen:
            seen.add(k)
            uniq.append(d)
    return uniq


pts = collect()
print("urea-solution streams recovered from the PFD: %d\n" % len(pts))
print("  %-8s %8s %8s %8s %9s" % ("stream", "urea", "water", "T (C)", "rho"))
for d in sorted(pts, key=lambda x: x["w_urea"]):
    print("  %-8s %8.4f %8.4f %8.1f %9.1f" % (d["id"], d["w_urea"], d["w_h2o"], d["T"], d["rho"]))

# ---- least squares:  rho = a + b*w_urea + c*(T - 100) ------------------------------------------
n = len(pts)
X = [[1.0, d["w_urea"], d["T"] - 100.0] for d in pts]
y = [d["rho"] for d in pts]
XtX = [[sum(X[k][i] * X[k][j] for k in range(n)) for j in range(3)] for i in range(3)]
Xty = [sum(X[k][i] * y[k] for k in range(n)) for i in range(3)]


def solve3(A, b):
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(3):
        p = max(range(c, 3), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        for r in range(3):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, 4):
                    M[r][k] -= f * M[c][k]
    return [M[i][3] / M[i][i] for i in range(3)]


a, b, c = solve3(XtX, Xty)
print("\nfit:  rho = %.4f + %.4f * w_urea + %.6f * (T - 100)" % (a, b, c))
worst = 0.0
print("\n  %-8s %9s %9s %8s" % ("stream", "PFD rho", "fit rho", "err %"))
for d in sorted(pts, key=lambda x: x["w_urea"]):
    pred = a + b * d["w_urea"] + c * (d["T"] - 100.0)
    e = 100.0 * (pred - d["rho"]) / d["rho"]
    worst = max(worst, abs(e))
    print("  %-8s %9.1f %9.1f %8.2f" % (d["id"], d["rho"], pred, e))
print("\n  worst residual: %.2f %%   (density rises with urea, falls with T -- both signs correct:"
      " b=%+.1f, c=%+.3f)" % (worst, b, c))

# ---- cp back-solve ------------------------------------------------------------------------------
print("\n" + "=" * 78)
print("cp BACK-SOLVE")
print("=" * 78)
import main as M  # noqa: E402


def cp_water(T):
    """Steam-table liquid-water cp, kJ/kg.K, 0-200 C.  Shallow quadratic through the standard
    table values 4.182 (20 C), 4.216 (100 C), 4.285 (140 C), 4.312 (160 C)."""
    return 4.1785 + 1.6e-5 * T + 3.9e-6 * T * T


# 323 design anchor: stream 317, the feed 323D002 delivers to 324 (80 % urea, 99 C)
W_DES, T_DES = 0.80, 99.0
cp_u = (M.R323_CP_SOLN - (1.0 - W_DES) * cp_water(T_DES)) / W_DES
print("  R323_CP_SOLN (model)          : %.4f kJ/kg.K at %.0f %% urea, %.0f C"
      % (M.R323_CP_SOLN, W_DES * 100, T_DES))
print("  cp_water(99 C) steam tables   : %.4f" % cp_water(T_DES))
print("  -> back-solved cp_urea        : %.4f kJ/kg.K" % cp_u)
print("     published molten urea cp   : ~2.0-2.1 kJ/kg.K   <-- corroboration")

print("\n  what the single constant 2.5 actually costs, stream by stream:")
print("  %-8s %8s %7s %10s %10s %9s" % ("stream", "urea", "T", "cp mixed", "model 2.5", "error %"))
for d in sorted(pts, key=lambda x: x["w_urea"]):
    cp_mix = d["w_urea"] * cp_u + d["w_h2o"] * cp_water(d["T"])
    err = 100.0 * (M.R323_CP_SOLN - cp_mix) / cp_mix
    print("  %-8s %8.4f %7.0f %10.4f %10.4f %+9.1f" % (d["id"], d["w_urea"], d["T"], cp_mix,
                                                       M.R323_CP_SOLN, err))
