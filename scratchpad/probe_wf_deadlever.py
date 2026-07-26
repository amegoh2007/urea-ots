"""Read-only AST sweep for class (A) dead levers in backend/main.py.

For each module-level function def, collect its parameter names. Then walk every
Call node in the file (and optionally in other backend/*.py) and record, per
(func, param), the set of distinct argument expressions passed.

A parameter is a DEAD LEVER candidate when every call site passes the SAME
module-level constant name (an UPPER_CASE global), including the default.
"""
import ast, sys, os, io, json
from collections import defaultdict

ROOT = r"D:/Work/Urea Simulation"
MAIN = os.path.join(ROOT, "backend", "main.py")

src = io.open(MAIN, encoding="utf-8").read()
tree = ast.parse(src)

# ---- module level constants (UPPER_CASE assigned at module scope) ----
consts = {}
for node in tree.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id.isupper() or (isinstance(t, ast.Name) and t.id.upper() == t.id):
                consts[t.id] = node.lineno
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        if node.target.id.upper() == node.target.id:
            consts[node.target.id] = node.lineno

# ---- function defs (module level + nested) ----
funcs = {}   # name -> (lineno, [params], defaults dict)
class FD(ast.NodeVisitor):
    def visit_FunctionDef(self, node):
        a = node.args
        params = [p.arg for p in a.posonlyargs] + [p.arg for p in a.args] + [p.arg for p in a.kwonlyargs]
        defaults = {}
        pos = [p.arg for p in a.posonlyargs] + [p.arg for p in a.args]
        for p, d in zip(pos[len(pos) - len(a.defaults):], a.defaults):
            defaults[p] = ast.unparse(d)
        for p, d in zip([p.arg for p in a.kwonlyargs], a.kw_defaults):
            if d is not None:
                defaults[p] = ast.unparse(d)
        if node.name in funcs:
            funcs[node.name + "@%d" % node.lineno] = (node.lineno, params, defaults)
        else:
            funcs[node.name] = (node.lineno, params, defaults)
        self.generic_visit(node)
    visit_AsyncFunctionDef = visit_FunctionDef
FD().visit(tree)

# ---- gather call sites across backend/ ----
callsites = defaultdict(lambda: defaultdict(list))  # func -> param -> [(file,line,exprtext)]
files = []
bdir = os.path.join(ROOT, "backend")
for dirpath, dirnames, filenames in os.walk(bdir):
    dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".pytest_cache", ".claude")]
    for fn in filenames:
        if fn.endswith(".py"):
            files.append(os.path.join(dirpath, fn))
# also scratchpad probes reference it
sdir = os.path.join(ROOT, "scratchpad")
for fn in os.listdir(sdir):
    if fn.endswith(".py"):
        files.append(os.path.join(sdir, fn))

for f in files:
    try:
        s = io.open(f, encoding="utf-8", errors="replace").read()
        t = ast.parse(s)
    except Exception:
        continue
    for node in ast.walk(t):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name):
            name = fn.id
        elif isinstance(fn, ast.Attribute):
            name = fn.attr
        else:
            continue
        if name not in funcs:
            continue
        lineno, params, defaults = funcs[name]
        # positional
        for i, arg in enumerate(node.args):
            if isinstance(arg, ast.Starred):
                break
            if i < len(params):
                callsites[name][params[i]].append((f, node.lineno, ast.unparse(arg)))
        given = set(params[:len(node.args)])
        for kw in node.keywords:
            if kw.arg is None:
                continue
            callsites[name][kw.arg].append((f, node.lineno, ast.unparse(kw.value)))
            given.add(kw.arg)
        # defaults used
        for p in params:
            if p not in given and p in defaults:
                callsites[name][p].append((f, node.lineno, "<default:%s>" % defaults[p]))

out = []
for name, (lineno, params, defaults) in sorted(funcs.items(), key=lambda kv: kv[1][0]):
    for p in params:
        if p in ("self", "cls"):
            continue
        sites = callsites.get(name, {}).get(p, [])
        exprs = set(e for (_, _, e) in sites)
        if not sites:
            continue
        # dead if single distinct expression AND that expression is a const/literal
        if len(exprs) == 1:
            e = list(exprs)[0]
            base = e.replace("<default:", "").rstrip(">")
            isconst = base in consts
            out.append({
                "func": name, "def_line": lineno, "param": p,
                "expr": e, "is_module_const": isconst,
                "const_line": consts.get(base),
                "n_sites": len(sites),
                "sites": ["%s:%d" % (os.path.relpath(f, ROOT).replace("\\", "/"), l) for (f, l, _) in sites],
            })

# report constants only, sorted
print("=== SINGLE-VALUED PARAMS WHERE VALUE IS A MODULE CONSTANT ===")
for r in out:
    if r["is_module_const"]:
        print(json.dumps(r))
print()
print("=== SINGLE-VALUED PARAMS (other literal/expr) ===")
for r in out:
    if not r["is_module_const"]:
        print(json.dumps(r))
