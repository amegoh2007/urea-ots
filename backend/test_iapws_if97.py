"""IAPWS-IF97 (R7-97) pure-water boundary validation.

Every expected value below is an OFFICIAL IF97 verification figure from the
release document (Regions 1, 2, and 4), not a value produced by this engine.
The tolerances are relative and generous versus the ~1e-9 accuracy actually
achieved, so a coefficient transcription slip fails loudly.
"""

from __future__ import annotations

import importlib

import pytest


def _if97():
    return importlib.import_module("iapws_if97")


# --- Region 4 saturation line (official verification points, Tables 35/36) ---
@pytest.mark.parametrize(
    ("temperature_k", "psat_mpa_ref"),
    [(300.0, 0.353658941e-2), (500.0, 0.263889776e1), (600.0, 0.123443146e2)],
)
def test_region4_forward_psat(temperature_k, psat_mpa_ref):
    w = _if97()
    assert w.psat_mpa(temperature_k) == pytest.approx(psat_mpa_ref, rel=1.0e-8)


@pytest.mark.parametrize(
    ("pressure_mpa", "tsat_k_ref"),
    [(0.1, 0.372755919e3), (1.0, 0.453035632e3), (10.0, 0.584149488e3)],
)
def test_region4_backward_tsat(pressure_mpa, tsat_k_ref):
    w = _if97()
    assert w.tsat_k(pressure_mpa) == pytest.approx(tsat_k_ref, rel=1.0e-8)


# --- Region 1 liquid enthalpy/volume (official verification, Table 5) ---
@pytest.mark.parametrize(
    ("temperature_k", "pressure_mpa", "h_ref", "v_ref"),
    [
        (300.0, 3.0, 0.115331273e3, 0.100215168e-2),
        (300.0, 80.0, 0.184142828e3, 0.971180894e-3),
        (500.0, 3.0, 0.975542239e3, 0.120241800e-2),
    ],
)
def test_region1_liquid(temperature_k, pressure_mpa, h_ref, v_ref):
    w = _if97()
    h, v = w._region1(temperature_k, pressure_mpa)
    assert h == pytest.approx(h_ref, rel=1.0e-7)
    assert v == pytest.approx(v_ref, rel=1.0e-7)


# --- Region 2 vapour enthalpy/volume (official verification, Table 15) ---
@pytest.mark.parametrize(
    ("temperature_k", "pressure_mpa", "h_ref", "v_ref"),
    [
        (300.0, 0.0035, 0.254991145e4, 0.394913866e2),
        (700.0, 0.0035, 0.333568375e4, 0.923015898e2),
        (700.0, 30.0, 0.263149474e4, 0.542946619e-2),
    ],
)
def test_region2_vapour(temperature_k, pressure_mpa, h_ref, v_ref):
    w = _if97()
    h, v = w._region2(temperature_k, pressure_mpa)
    assert h == pytest.approx(h_ref, rel=1.0e-7)
    assert v == pytest.approx(v_ref, rel=1.0e-7)


# --- saturation curve is self-inverse across every plant steam/vacuum band ---
@pytest.mark.parametrize(
    "pressure_bara",
    [0.033, 0.131, 0.33, 0.46, 1.0, 1.8, 2.4, 3.0, 4.1, 4.4, 9.0, 16.0, 19.7, 24.0],
)
def test_saturation_round_trip(pressure_bara):
    w = _if97()
    t_c = w.tsat_c(pressure_bara)
    assert w.psat_bara(t_c) == pytest.approx(pressure_bara, rel=1.0e-8)


# --- latent heat / saturated enthalpies stay on the steam table ---
@pytest.mark.parametrize(
    ("temperature_c", "hvap_ref"),
    [(40.0, 2406.0), (100.0, 2256.5), (143.0, 2135.2), (211.6, 1893.0)],
)
def test_latent_heat_tracks_steam_table(temperature_c, hvap_ref):
    w = _if97()
    # 0.1 % band versus published steam-table latent heats.
    assert w.hvap_kjkg(temperature_c) == pytest.approx(hvap_ref, rel=1.0e-3)


def test_saturated_liquid_enthalpy_reference_point():
    w = _if97()
    # Triple-point-referenced hL(100 C) is ~419.0 kJ/kg on the IF97 scale.
    assert w.h_liquid_sat_kjkg(100.0) == pytest.approx(419.0, abs=0.5)


def test_out_of_range_saturation_is_explicit():
    w = _if97()
    with pytest.raises(w.OutOfRange):
        w.psat_mpa(700.0)  # above the critical temperature
    with pytest.raises(w.OutOfRange):
        w.tsat_k(30.0)  # above the critical pressure
