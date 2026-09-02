import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from c003_pressure_coupling import (  # noqa: E402
    c003_pressure_target_bara,
    e011_vent_generation_kgh,
    C003_Q301_DES_M3H,
    C003_Q302_DES_M3H,
    C003_Q_IN_DES_M3H,
    C003_BED_CONDENSATION_DES_M3H,
    C003_GAS_LOAD_COEFF_M3H_PER_BAR,
    C003_P_DES_BARA,
    E003_P_DES_BARA,
)


# ---------------------------------------------------------------------------
# Unit tests for c003_pressure_target_bara (two-path model)
# ---------------------------------------------------------------------------

def test_c003_design_point_closes_exactly():
    """At design both ratios == 1.0 and P must be exactly 4.1 bar a."""
    assert c003_pressure_target_bara(1.0, 1.0, 3.2) == pytest.approx(4.1, abs=1.0e-12)


def test_c003_lv_flash_path_sensitivity():
    """Opening LV-322501 (more flash gas) raises C003 pressure.

    Startup-trend field gain: 0.100 bar per % LV opening,
    normalised at the 46.1 % design opening.
    ∂P/∂(flash_ratio) at design == (field_gain + hydraulic) per unit ratio.
    """
    step = 1.0e-3
    p_hi = c003_pressure_target_bara(1.0 + step, 1.0, 3.2)
    p_lo = c003_pressure_target_bara(1.0 - step, 1.0, 3.2)
    slope = (p_hi - p_lo) / (2.0 * step)
    # sensitivity must be positive and substantial (≥ 1 bar per unit ratio)
    assert slope > 1.0


def test_c003_e002_vap_path_sensitivity():
    """More 323E002 rectifying-heater gas (stream 302, r_e002 > 1) raises C003 pressure
    INDEPENDENTLY of the LV-322501 flash path (r_flash held at design)."""
    step = 1.0e-3
    p_hi = c003_pressure_target_bara(1.0, 1.0 + step, 3.2)
    p_lo = c003_pressure_target_bara(1.0, 1.0 - step, 3.2)
    slope = (p_hi - p_lo) / (2.0 * step)
    # 323E002 gas only uses the hydraulic term (no field-gain correction)
    # at design:  dP_hydr/dr_e002 = Q302_DES / C_gas / sqrt(1 - (P_down/P_des)^2)
    # sign must be strictly positive
    assert slope > 0.0


def test_c003_both_paths_additive_at_design():
    """Doubling both ratios simultaneously raises pressure more than
    doubling either one alone — the two terms genuinely add."""
    p_flash_only = c003_pressure_target_bara(2.0, 1.0, 3.2)
    p_e002_only  = c003_pressure_target_bara(1.0, 2.0, 3.2)
    p_both       = c003_pressure_target_bara(2.0, 2.0, 3.2)
    assert p_both > p_flash_only
    assert p_both > p_e002_only


def test_c003_local_lv_sensitivity_matches_startup_band():
    """Combined (flash-path hydraulic + field-gain) sensitivity must sit inside
    the startup-trend band of 0.10–0.13 bar per % LV opening at design."""
    opening_step = 1.0e-3          # % LV opening step
    ratio_step   = opening_step / 46.1  # normalised at design 46.1 %
    p_hi = c003_pressure_target_bara(1.0 + ratio_step, 1.0, 3.2)
    p_lo = c003_pressure_target_bara(1.0 - ratio_step, 1.0, 3.2)
    slope = (p_hi - p_lo) / (2.0 * opening_step)
    assert slope == pytest.approx(0.122171340, rel=1.0e-5)
    assert 0.10 <= slope <= 0.13


def test_c003_target_never_falls_below_downstream_pressure():
    assert c003_pressure_target_bara(0.0, 1.0, 3.2) == pytest.approx(3.2)
    assert c003_pressure_target_bara(0.0, 0.0, 3.2) == pytest.approx(3.2)


def test_c003_flash_path_zero_e002_still_works():
    """With zero 323E002 heater gas the flash path alone must give a finite pressure."""
    p = c003_pressure_target_bara(1.0, 0.0, 3.2)
    # Only the flash term contributes; result must be finite and > downstream
    assert math.isfinite(p)
    assert p >= 3.2


def test_c003_e002_path_zero_flash_still_works():
    """With zero flash gas the 323E002 heater path alone must give a finite pressure."""
    p = c003_pressure_target_bara(0.0, 1.0, 3.2)
    assert math.isfinite(p)
    assert p >= 3.2


# ---------------------------------------------------------------------------
# Validation constants (ensure design arithmetic is self-consistent)
# ---------------------------------------------------------------------------

def test_c003_inlet_load_is_the_sum_of_both_pfd_source_rows():
    """The two charging streams are read from their OWN PFD rows.

    Catch stream 302 being back-computed as 305 - 301, which understates the
    323E002 gas by the packed-bed condensation and makes stream 305 -- the column
    OUTLET -- an inlet driver.
    """
    assert C003_Q_IN_DES_M3H == pytest.approx(
        C003_Q301_DES_M3H + C003_Q302_DES_M3H, rel=1e-12)
    from c003_pressure_coupling import C003_Q305_DES_M3H
    assert C003_BED_CONDENSATION_DES_M3H == pytest.approx(
        C003_Q_IN_DES_M3H - C003_Q305_DES_M3H, rel=1e-12)
    # 301 + 302 exceeds the overhead: the difference condenses on the bed where the
    # 135 C heater gas meets the 119 C reflux.
    assert C003_BED_CONDENSATION_DES_M3H > 0.0
    assert C003_Q302_DES_M3H != pytest.approx(C003_Q305_DES_M3H - C003_Q301_DES_M3H)


def test_c003_hydraulic_coefficient_correct():
    """GAS_LOAD_COEFF must produce P_des when the design inlet load is used."""
    load = C003_Q301_DES_M3H + C003_Q302_DES_M3H
    p_hyd = math.sqrt(E003_P_DES_BARA ** 2 + (load / C003_GAS_LOAD_COEFF_M3H_PER_BAR) ** 2)
    assert p_hyd == pytest.approx(C003_P_DES_BARA, abs=1e-10)


# ---------------------------------------------------------------------------
# e011 vent generation
# ---------------------------------------------------------------------------

def test_e011_design_gas_closes_pfd_balance():
    assert e011_vent_generation_kgh(6029.0) == pytest.approx(440.0)


def test_e011_incremental_gas_exceeds_fixed_condensation_capacity():
    assert e011_vent_generation_kgh(7029.0) == pytest.approx(1440.0)
    assert e011_vent_generation_kgh(5029.0) == 0.0


@pytest.mark.parametrize("gas_inlet", [math.nan, math.inf, -0.01])
def test_e011_rejects_invalid_gas_inlet(gas_inlet):
    with pytest.raises(ValueError):
        e011_vent_generation_kgh(gas_inlet)


# ---------------------------------------------------------------------------
# Integration tests against the running simulator
# ---------------------------------------------------------------------------

from typing import NamedTuple

import main  # noqa: E402


class LvCase(NamedTuple):
    pt323201_bara: float
    pic323203_pv_bara: float
    pic323203_op: float


def _run_lv_case(opening_pct: float) -> LvCase:
    main.state = main.State()
    state = main.state
    state.LIC_322501["mode"] = "MAN"
    state.LIC_322501["op"] = opening_pct
    for _ in range(round(60.0 / main.STEP_CAP)):
        main.step_sim(main.STEP_CAP)
    return LvCase(
        pt323201_bara=state.r323_c003_P,
        pic323203_pv_bara=state.r3232_e011_P,
        pic323203_op=state.PIC_323203["op"],
    )


def test_lv_opening_materially_separates_pt323201():
    """Opening LV-322501 (more flash gas) must raise 323C003 pressure by > 2.5 bar."""
    closed = _run_lv_case(30.0)
    opened = _run_lv_case(60.0)
    assert opened.pt323201_bara - closed.pt323201_bara > 2.5


def test_lv_opening_materially_separates_pic323203():
    """The LV-322501 lever must reach the 323E011 vent loop.

    Gate on the loop PV, not on PIC-323203's output: the controller is Kc = 0.6 %/bar with
    Ti = 100 s, so over the 60 s case its stroke can only move a few tenths of a point for any
    error inside its own 0.5-2.0 bar SP range -- an output threshold measures the tuning, not
    the coupling.  The pressure it sees separates by ~0.47 bar (1.01 against 1.47 bar a), and
    the stroke must still move the right way.
    """
    closed = _run_lv_case(30.0)
    opened = _run_lv_case(60.0)
    assert opened.pic323203_pv_bara - closed.pic323203_pv_bara > 0.30
    assert opened.pic323203_op > closed.pic323203_op
