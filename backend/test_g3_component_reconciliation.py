"""G3 closure gate: the 323/324 design-anchor rows are reconciled to atom-consistency so every
_sol_stage_anchor clip is zero and the sol_pin_strength component overwrite is retired, while the hard
urea/water design strengths (R324_W_EV) and the plant HMB are preserved."""

from __future__ import annotations

import pytest

import main


@pytest.mark.parametrize("tag", ["C003", "F004", "F010", "E001", "E003"])
def test_design_anchor_clip_is_zero(tag: str) -> None:
    # the negative-vapour back-charge that used to be -170/-127/-1.9 kg/h is gone by construction
    assert abs(getattr(main, "SOL_" + tag)["resid"]) < 1e-6


def test_sol_pin_strength_is_a_component_conserving_passthrough() -> None:
    probe = {"Urea": 0.5, "H2O": 0.4, "Biuret": 0.1, "NH3": 0.0, "CO2": 0.0, "HCHO": 0.0}
    # retired: it must NOT overwrite the urea/water pair onto an authoritative strength any more
    assert main.sol_pin_strength(probe, 0.99) == probe


def test_reconciliation_preserves_the_hard_design_strength() -> None:
    assert main.R324_W_EV1 == 0.9431
    assert main.R324_W_EV2 == 0.9771
    assert main.W_S401["Urea"] == pytest.approx(0.9431, abs=5e-4)
    assert main.W_S402["Urea"] == pytest.approx(0.9771, abs=5e-4)


def test_reconciliation_conserves_nonvolatiles_exactly() -> None:
    # urea and biuret masses are conserved across E001 (no unsupported net formation)
    for k in ("Urea", "Biuret", "HCHO"):
        m_in = main.R324_FEED_DES * main.W_S317[k]
        m_out = main.R324_P1_DES * main.W_S401[k]
        assert m_out == pytest.approx(m_in, rel=1e-9)


def test_biuret_is_reconciled_below_the_rounded_tabulation() -> None:
    # the tabulated melt biuret over-stated formation; reconciled to mass-conserved
    assert main.W_S401["Biuret"] < main.W_S401_TAB["Biuret"]
    assert main.W_S402["Biuret"] < main.W_S402_TAB["Biuret"]


def test_runtime_component_balance_closes_without_overwrite() -> None:
    original = main.state
    try:
        main.state = main.State()
        packet = None
        for _ in range(400):
            packet = main.step_sim(0.1)
        clip = packet["SPECIES_323_324"]["clip_resid_kgh"]
        assert all(abs(v) <= 1e-6 for v in clip.values())
        # species melt strength holds design without the retired pin
        assert packet["SPECIES_323_324"]["urea_pct_species"]["E001"] == pytest.approx(94.31, abs=0.3)
        assert packet["SPECIES_323_324"]["urea_pct_species"]["E003"] == pytest.approx(97.71, abs=0.3)
    finally:
        main.state = original
