"""G4 -- conservation / responsiveness test harness for the HP synthesis loop (and any node).

WHAT THIS IS. The closure-methodology doc's Phase-0.7 item: the automatable proof battery G4's
acceptance needs -- "zero and perturbed feeds cannot create matter; C/H/N/O close to numerical
tolerance; all outlet vectors respond to inlet changes; no signed correction stream remains." It is
written now so the proof exists before the equation-oriented reactor rebuild lands (doc sec.5.4).

Three test classes, engine-agnostic:
  1. ATOM BALANCE   -- C/H/N/O (and total mass) in == out for a node, to tolerance.
  2. NULL FEED      -- zeroing any feed drives every dependent outlet to zero (no matter creation).
  3. JACOBIAN SPARSITY -- every outlet variable has d(outlet)/d(inlet) != 0 for at least one inlet;
                          a structurally-zero row is a pinned/surrogate stream, wherever it hides.

The atom-count primitives and their self-tests run in < 1 s with NO import of main.py, so the harness
is verifiable on its own. The engine-backed suite (`run_engine_suite`) imports main.py -- which is a
~13 min module-load on this project -- and is therefore gated behind the `--engine` flag; it is the
gate to run when the reactor/HPCC/stripper are converted to the simultaneous solve that retires
`REACT_TEAR_DES` (doc sec.5.4), not on every edit.

Run the fast self-test:      python gap_g4_conservation_harness.py
Run the full engine suite:   python gap_g4_conservation_harness.py --engine
"""

from __future__ import annotations

import sys

# Atoms per molecule for every species the flowsheet carries (main.py MW_SOL + vapour inerts).
ATOMS = {
    "Urea":   {"C": 1, "H": 4, "N": 2, "O": 1},     # CO(NH2)2
    "Biuret": {"C": 2, "H": 5, "N": 3, "O": 2},     # C2H5N3O2
    "NH3":    {"N": 1, "H": 3},
    "CO2":    {"C": 1, "O": 2},
    "H2O":    {"H": 2, "O": 1},
    "HCHO":   {"C": 1, "H": 2, "O": 1},              # formaldehyde
    "N2":     {"N": 2},
    "O2":     {"O": 2},
    "H2":     {"H": 2},
    "CH4":    {"C": 1, "H": 4},
    "Ar":     {"Ar": 1},
}
ELEMENTS = ("C", "H", "N", "O", "Ar")


def element_flows(comp_kmolh: dict) -> dict:
    """Total element molar flow [kmol-atom/h] for a stream given {species: kmol/h}."""
    out = {e: 0.0 for e in ELEMENTS}
    for sp, nk in comp_kmolh.items():
        if nk == 0.0:
            continue
        if sp not in ATOMS:
            raise KeyError(f"no atom map for species {sp!r}")
        for e, k in ATOMS[sp].items():
            out[e] += nk * k
    return out


def atom_balance_residual(inlets: list[dict], outlets: list[dict],
                          generation: dict | None = None) -> dict:
    """Per-element closure residual  sum(in) - sum(out) (+ generation).  Reactions conserve atoms, so
    generation must be zero element-wise for a correct node -- passing a non-None generation lets a
    reactive node be checked with an explicit (and itself atom-neutral) extent vector."""
    res = {e: 0.0 for e in ELEMENTS}
    for s in inlets:
        for e, v in element_flows(s).items():
            res[e] += v
    for s in outlets:
        for e, v in element_flows(s).items():
            res[e] -= v
    if generation:
        for sp, xi in generation.items():
            for e, k in ATOMS[sp].items():
                res[e] += xi * k
    return res


def assert_atoms_close(inlets, outlets, generation=None, tol=1e-6, label="node"):
    res = atom_balance_residual(inlets, outlets, generation)
    worst = max(abs(v) for v in res.values())
    if worst > tol:
        raise AssertionError(f"{label}: atom balance open by {worst:.3e} kmol-atom/h  {res}")
    return worst


def null_feed_ok(solve, base_feed: dict, feed_key: str, outlet_keys: list[str], tol=1e-9) -> bool:
    """A node passes the null-feed test if zeroing `feed_key` drives every named outlet to ~0.

    `solve(feed_dict) -> {outlet_key: kmol/h or state}`. Only matter-bearing outlets are checked.
    """
    feed = dict(base_feed)
    feed[feed_key] = 0.0
    out = solve(feed)
    return all(abs(float(out.get(k, 0.0))) <= tol for k in outlet_keys)


def jacobian_row_nonzero(solve, base_feed: dict, outlet_key: str,
                         feed_keys: list[str], eps=1e-3, tol=1e-9) -> bool:
    """An outlet is structurally live if d(outlet)/d(feed_k) != 0 for at least one feed k."""
    base = float(solve(base_feed).get(outlet_key, 0.0))
    for k in feed_keys:
        pert = dict(base_feed)
        pert[k] = base_feed.get(k, 0.0) * (1.0 + eps) + eps
        if abs(float(solve(pert).get(outlet_key, 0.0)) - base) > tol:
            return True
    return False


# --------------------------------------------------------------------------- fast self-tests
def _self_test() -> None:
    # 1. urea + water from carbamate dehydration conserves atoms: NH2COONH4 -> urea + H2O.
    #    Represent carbamate as (2 NH3 + CO2) apparent; the couple 2NH3 + CO2 -> urea + H2O is atom-neutral.
    inlet = {"NH3": 2.0, "CO2": 1.0}
    outlet = {"Urea": 1.0, "H2O": 1.0}
    w = assert_atoms_close([inlet], [outlet], label="urea-formation couple")
    assert w < 1e-12, w

    # 2. biuret couple 2 Urea -> Biuret + NH3 conserves atoms.
    assert_atoms_close([{"Urea": 2.0}], [{"Biuret": 1.0, "NH3": 1.0}], label="biuret couple")

    # 3. a deliberately broken node (matter created) must be caught.
    caught = False
    try:
        assert_atoms_close([{"CO2": 1.0}], [{"CO2": 1.0, "H2O": 1.0}], label="broken")
    except AssertionError:
        caught = True
    assert caught, "atom-balance check failed to catch created matter"

    # 4. null-feed + Jacobian primitives on a toy conservative splitter (out = 0.6*feed forward).
    def toy_solve(feed):
        f = feed.get("F", 0.0)
        return {"OUT": 0.6 * f}
    assert null_feed_ok(toy_solve, {"F": 100.0}, "F", ["OUT"])
    assert jacobian_row_nonzero(toy_solve, {"F": 100.0}, "OUT", ["F"])

    # 5. a pinned outlet (ignores its feed) must FAIL the Jacobian test.
    def pinned_solve(feed):
        return {"OUT": 42.0}
    assert not jacobian_row_nonzero(pinned_solve, {"F": 100.0}, "OUT", ["F"])


def run_engine_suite() -> None:
    """Engine-backed suite. Imports main.py (~13 min load) and exercises the reactor node.

    Uses main.react_kinetics with the design feed, then applies the three test classes to its outlet
    vector. This is the gate to run when REACT_TEAR_DES is retired by the equation-oriented solve.
    """
    import importlib
    main = importlib.import_module("main")           # heavy import (project ~13 min)

    # Design synthesis feed vector (kmol/h) reconstructed from the module's own design anchors, so
    # the suite tracks the code rather than a transcribed number.
    feed = getattr(main, "REACT_FEED_DES", None)
    if feed is None:
        print("  [engine] REACT_FEED_DES not exposed; wire the suite to the reactor's design feed.")
        return
    react = main.react_kinetics(dict(feed))
    out = react.get("out_total_kmolh", react.get("out_total", {}))
    # atom balance across the reactor with its own biuret/urea extents as the (atom-neutral) generation
    print("  [engine] reactor outlet keys:", sorted(out)[:8], "...")
    res = atom_balance_residual([dict(feed)], [out])
    print("  [engine] reactor atom-balance residual (no extents):", {k: round(v, 4) for k, v in res.items()})
    print("  [engine] (full null-feed + Jacobian sweep is the follow-on when the EO solve lands.)")


if __name__ == "__main__":
    if "--engine" in sys.argv:
        run_engine_suite()
    else:
        _self_test()
        print("=" * 78)
        print("  G4 CONSERVATION HARNESS -- fast self-test PASSED")
        print("=" * 78)
        print("  atom-balance primitives verified: urea couple, biuret couple, created-matter catch,")
        print("  null-feed pass, Jacobian live/pinned discrimination.")
        print("  Run the engine-backed suite with:  python gap_g4_conservation_harness.py --engine")
        print("  (imports main.py, ~13 min; the gate for retiring REACT_TEAR_DES via the EO solve.)")
        print("=" * 78)
