"""C10 -- urea-solution density correlation, parsed BLOCK BY BLOCK.

The first attempt zipped labelled rows by block index, which silently mixed columns from PFD
sheets that have different widths -- it produced 'stream 203 at 25 % urea', and 203 is carbamate
gas.  Wrong data makes a wrong correlation, so this version rebuilds each sheet as a proper
column table keyed on its own header row before reading anything.

Selection is deliberately strict: a stream counts as a urea solution only if the PFD calls it
one in the description row.  That keeps cooling water and carbamate gas out of a urea fit.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PFD = os.path.normpath(os.path.join(
    HERE, "..", "References", "Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md"))

text = open(PFD, encoding="utf-8").read()
blocks = text.split("\n## ")
print("PFD sheets found: %d" % len(blocks))

pts = []
for blk in blocks:
    table = {}
    for line in blk.splitlines():
        if not line.startswith("|") or set(line) <= set("|:- "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        table.setdefault(cells[0], cells)
    ids = table.get("STREAM No.")
    desc = table.get("Stream description")
    urea = table.get("Urea")
    water = table.get("Water")
    rho = table.get("Density eff.")
    temp = table.get("Operating Temperature")
    if not (ids and desc and urea and rho and temp):
        continue
    width = min(len(ids), len(desc), len(urea), len(rho), len(temp),
                len(water) if water else 10**9)
    for i in range(2, width):
        if "urea sol" not in desc[i].lower():      # the PFD's own classification
            continue
        try:
            u = float(urea[i]) / 100.0
            r = float(rho[i])
            t = float(temp[i])
            w = float(water[i]) / 100.0 if water and water[i] else 0.0
        except ValueError:
            continue
        pts.append({"id": ids[i], "w": u, "wh": w, "rho": r, "T": t})

seen, uniq = set(), []
for d in pts:
    k = (round(d["w"], 5), round(d["rho"], 2), round(d["T"], 2))
    if k not in seen:
        seen.add(k)
        uniq.append(d)
pts = sorted(uniq, key=lambda x: x["w"])

print("urea-solution streams (PFD-classified): %d\n" % len(pts))
print("  %-8s %8s %8s %8s %9s" % ("stream", "urea", "water", "T (C)", "rho"))
for d in pts:
    print("  %-8s %8.4f %8.4f %8.1f %9.1f" % (d["id"], d["w"], d["wh"], d["T"], d["rho"]))

n = len(pts)
X = [[1.0, d["w"], d["T"] - 100.0] for d in pts]
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
print("\nfit:  rho = %.4f %+.4f*w_urea %+.6f*(T-100)      [kg/m3]" % (a, b, c))
print("\n  %-8s %9s %9s %8s" % ("stream", "PFD", "fit", "err %"))
worst = 0.0
for d in pts:
    pred = a + b * d["w"] + c * (d["T"] - 100.0)
    e = 100.0 * (pred - d["rho"]) / d["rho"]
    worst = max(worst, abs(e))
    print("  %-8s %9.1f %9.1f %+8.2f" % (d["id"], d["rho"], pred, e))
print("\n  worst residual %.2f %%" % worst)
print("  d(rho)/d(w_urea) = %+.1f kg/m3 per unit fraction" % b)
print("  d(rho)/dT        = %+.3f kg/m3 per K" % c)
print("\n  SIGN CHECK: density must RISE with urea and FALL with temperature.")
print("    rises with urea : %s" % ("YES" if b > 0 else "NO  <-- WRONG"))
print("    falls with T    : %s" % ("YES" if c < 0 else "NO  <-- WRONG"))
