"""The boot-pin cache key must cover every model source the design settle runs through.

`main._PIN_SRC_FILES` is hashed into `.boot_pin_cache.json`'s key.  A module left out of it can be
edited without the key moving, and the engine then boots on constants settled by the OLD code while
reporting a cache hit.  Until 2026-09-17 that was true of hydraulics.py (every valve and vessel
law), iapws_if97.py, machines.py, jet_pump.py, consequence.py, c003_pressure_coupling.py and all of
core/.

The closure is found statically (ast), so this file never imports main and runs in a second.
"""
import ast
import os

HERE = os.path.dirname(os.path.abspath(__file__))
NOT_MODEL = {"historian.py"}          # trend recorder: samples the packet, never enters the settle


def _local_file(module):
    base = os.path.join(HERE, *module.split("."))
    for cand in (base + ".py", os.path.join(base, "__init__.py")):
        if os.path.isfile(cand):
            return os.path.relpath(cand, HERE).replace(os.sep, "/")
    return None


def _import_closure(entry="main"):
    seen, stack = {}, [entry]
    while stack:
        mod = stack.pop()
        if mod in seen:
            continue
        rel = _local_file(mod)
        if rel is None:
            continue
        seen[mod] = rel
        tree = ast.parse(open(os.path.join(HERE, rel), encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                stack.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                stack.append(node.module)
                stack.extend(node.module + "." + a.name for a in node.names)
    return set(seen.values())


def _pin_sources():
    tree = ast.parse(open(os.path.join(HERE, "main.py"), encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "_PIN_SRC_FILES"
                                                for t in node.targets):
            return set(ast.literal_eval(node.value))
    raise AssertionError("_PIN_SRC_FILES not found in main.py")


def test_every_model_module_main_imports_is_in_the_pin_key():
    missing = sorted(_import_closure() - NOT_MODEL - _pin_sources())
    assert not missing, "edits to these would not bust the boot-pin cache: %s" % missing


def test_every_pin_source_exists():
    absent = sorted(f for f in _pin_sources() if not os.path.isfile(os.path.join(HERE, f)))
    assert not absent, "listed pin sources that do not exist hash as a sentinel: %s" % absent
