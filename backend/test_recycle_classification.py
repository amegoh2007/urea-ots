"""G7 closure gate: every recycle is explicitly classified dynamic (transport) or algebraic
(bounded inner solve), algebraic loops meet their declared residual tolerance, and dynamic loops
report transport state rather than solver convergence."""

from __future__ import annotations

import pytest

import main


def _packet():
    original = main.state
    try:
        main.state = main.State()
        packet = None
        for _ in range(5):
            packet = main.step_sim(0.1)
        return packet
    finally:
        main.state = original


def test_recycle_classification_block_is_published() -> None:
    rc = _packet()["RECYCLE_CLASSIFICATION"]
    assert set(rc) == {"algebraic_inner_solves", "dynamic_transport_tears"}


def test_algebraic_324_loops_meet_declared_tolerance() -> None:
    alg = _packet()["RECYCLE_CLASSIFICATION"]["algebraic_inner_solves"]
    assert alg["is_solver_convergence"] is True
    assert alg["method"] == "bounded_picard_fixed_point"
    assert alg["tolerance"] == main.R324_PT_LOOP_TOL
    assert alg["max_iterations"] == main.R324_PT_LOOP_MAXIT
    assert alg["fallback"] == "last_iterate"
    assert alg["all_converged"] is True
    for tag in ("E001", "E003"):
        loop = alg["loops"][tag]
        assert loop["converged"] is True
        assert loop["residual"] <= main.R324_PT_LOOP_TOL
        assert 1 <= loop["iterations"] <= main.R324_PT_LOOP_MAXIT


def test_dynamic_tears_report_transport_not_convergence() -> None:
    dyn = _packet()["RECYCLE_CLASSIFICATION"]["dynamic_transport_tears"]
    assert dyn["is_solver_convergence"] is False
    assert dyn["method"] == "observed_dynamic_transport_tears"
    # the synthesis/328 recycles that carry real vessel inventories
    assert dyn["loops"], "dynamic transport tears must be enumerated"


def test_legacy_tear_residual_key_is_retained_for_the_audit() -> None:
    # audit_model_compliance.py reads RECYCLE_TEAR_RESIDUAL.is_solver_convergence; keep it.
    tear = _packet()["RECYCLE_TEAR_RESIDUAL"]
    assert tear["is_solver_convergence"] is False


def test_pt_loop_constants_are_the_single_source_of_truth() -> None:
    # the loop tolerance/cap the classification advertises must be the actual loop values
    assert main.R324_PT_LOOP_TOL == 1e-12
    assert main.R324_PT_LOOP_MAXIT == 20
