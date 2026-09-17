"""Coverage contract for every actionable subsection in References/scenarios."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import consequence as cq
import hp_recycle
import main
from scenario_coverage import SCENARIO_REQUIREMENTS, thermo_package_for


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = ROOT / "References" / "scenarios"


def documented_requirements() -> set[tuple[str, str]]:
    """Return source/section keys for process scenarios, excluding evidence notes."""
    found: set[tuple[str, str]] = set()
    for path in sorted(SCENARIO_DIR.glob("Scenarios*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^###\s+(\d+\.\d+)\s+(.+)$", line)
            if match and "Data Confidence" not in match.group(2):
                found.add((path.name, match.group(1)))
    return found


def test_manifest_covers_every_documented_process_scenario_once():
    """Catch a new or omitted scenario subsection with no executable evidence mapping."""
    documented = documented_requirements()
    manifested = {(item.source, item.section) for item in SCENARIO_REQUIREMENTS}

    assert len(SCENARIO_REQUIREMENTS) == len(manifested), "duplicate manifest keys"
    assert len(documented) == 48
    assert manifested == documented


@pytest.mark.parametrize("item", SCENARIO_REQUIREMENTS)
def test_manifest_entries_define_cause_local_effect_and_downstream_evidence(item):
    """Catch a coverage entry that names a scenario but provides no causal contract."""
    assert item.driver.strip()
    assert item.local_observable.strip()
    assert item.downstream_observable.strip()
    assert item.evidence_test.startswith("test_")


@pytest.mark.parametrize(
    ("section", "expected"),
    [
        ("HP_SYNTHESIS", "VOSKOV_VORONIN_HP_UNIQUAC_VIRIAL"),
        ("LP_NH3_CO2_H2O", "DARDE_EXTENDED_UNIQUAC_SRK"),
        ("UREA_WATER_VACUUM", "NEUTRAL_UNIQUAC_IAPWS_IF97"),
        ("STEAM_WATER", "IAPWS_IF97"),
    ],
)
def test_thermodynamic_router_keeps_each_package_in_its_process_domain(section, expected):
    """Catch accidental reuse of one thermodynamic package outside its fitted domain."""
    assert thermo_package_for(section) == expected


def test_thermodynamic_router_rejects_unknown_process_domains():
    with pytest.raises(ValueError, match="unknown thermodynamic section"):
        thermo_package_for("UNKNOWN")


def test_equivalent_unlisted_consequences_transport_identical_properties_and_composition():
    """Catch scenario identity changing the D/S stream produced by the shared consequence law."""
    route = cq.ConsequenceRoute("source", "destination", 3600.0, 5.0)
    consequence = cq.make_stream_packet(
        100.0, {"NH3": 20.0, "CO2": 30.0, "H2O": 50.0}, 120.0, 2.0
    )
    stores = ({}, {})
    for _ in range(100):
        for store in stores:
            cq.transport_stream_packet(
                store, "route", cq.ZERO_PACKET, route, 3600.0, 0.1
            )
    outputs = []
    for _ in range(51):
        outputs = [
            cq.transport_stream_packet(
                store, "route", consequence, route, 3600.0, 0.1
            )
            for store in stores
        ]

    assert outputs[0] == outputs[1] == consequence
    assert sum(outputs[0].component_kgh.values()) == pytest.approx(outputs[0].mass_kgh)
    assert sum(outputs[0].mass_fraction.values()) == pytest.approx(1.0)


def _carry(level: float, vapour: float = 100.0, pressure: float = 1.0) -> float:
    return cq.entrainment_carryover_kgh(
        vapour, 100.0, level, 0.5,
        p_bara=pressure, p_des_bara=1.0, t_c=100.0, t_des_c=100.0,
    )


def _npsh(level_head: float, psat: float) -> float:
    return cq.npsh_available_m(1.01325, psat, 1000.0, level_head)


def _absorption(capacity_ratio: float) -> dict:
    return hp_recycle.reactive_scrubber_split(
        {"NH3": 100.0, "CO2": 50.0, "N2": 10.0},
        {"NH3": 5.0, "CO2": 2.0, "H2O": 100.0},
        {"NH3": 90.0, "CO2": 45.0},
        capacity_ratio,
    )


def test_reactor_level_consequences():
    assert _carry(0.95) > _carry(0.50)
    assert cq.seal_fraction(0.0, 5.0, 3.0) == 0.0
    assert cq.seal_fraction(50.0, 5.0, 3.0) == 1.0


def test_atmospheric_flash_level_consequences():
    assert _carry(0.95) > 0.0
    assert _npsh(0.1, 0.95) < _npsh(5.0, 0.50)
    assert cq.pump_capacity_factor(0.0, 2.0) == 0.0


def test_evaporator_heat_pressure_temperature_laws():
    anchor = main.evap_w_eq(134.0, 0.33, 0.95, 134.0, 0.33)
    assert main.evap_w_eq(136.0, 0.33, 0.95, 134.0, 0.33) > anchor
    assert main.evap_w_eq(134.0, 0.40, 0.95, 134.0, 0.33) < anchor
    assert main.sol_biuret_xi("C003", main.R323_C003_M_DES, main.W_S314, 140.0) > \
        main.sol_biuret_xi("C003", main.R323_C003_M_DES, main.W_S314, 130.0)


def test_final_evaporator_consequences():
    assert _carry(0.90, vapour=150.0, pressure=0.08) > _carry(0.50)
    assert cq.air_ingress_kgh(0.13, 100.0) > 0.0
    assert cq.liquor_crystallization_T(main.W_S402) > \
        cq.liquor_crystallization_T(main.W_S317)


def test_hp_scrubber_operator_gradients():
    rich, starved = _absorption(1.0), _absorption(0.4)
    assert rich["breakthrough_kmolh"] < starved["breakthrough_kmolh"]
    assert all(abs(v) < 1.0e-12 for v in rich["closure"].values())
    design = main.scrub_322e003(
        main.REACT_OFFGAS_DES, 1.0, main.SCRUB_CCW_T_IN_DES,
        main.SCRUB_CCW_KGH_DES,
    )
    cold = main.scrub_322e003(
        main.REACT_OFFGAS_DES, 1.0, main.SCRUB_CCW_T_IN_DES - 10.0,
        main.SCRUB_CCW_KGH_DES,
    )
    assert cold["capacity_ratio"] > design["capacity_ratio"]
    assert cold["breakthrough_kmolh"] < design["breakthrough_kmolh"]


def test_hp_stripper_operator_gradients():
    base = main.stripper_322e001(
        main.CO2_DES_KGH / 1000.0, main.STRIP_STEAM_T_DES_C,
        main.STRIP_P_DES_BARA, strip_level_pct=50.0,
    )
    hotter = main.stripper_322e001(
        main.CO2_DES_KGH / 1000.0, main.STRIP_STEAM_T_DES_C + 5.0,
        main.STRIP_P_DES_BARA, strip_level_pct=50.0,
    )
    flooded = main.stripper_322e001(
        main.CO2_DES_KGH / 1000.0, main.STRIP_STEAM_T_DES_C,
        main.STRIP_P_DES_BARA, strip_level_pct=500.0,
    )
    assert hotter["eta_T"] > base["eta_T"]
    assert hotter["xi_biu"] > base["xi_biu"]
    assert flooded["g_flood"] < base["g_flood"]


def test_reactor_downcomer_gradients():
    sealed = cq.blowthrough_kgh(100_000.0, 1100.0, 140.0, 0.5, 80.0, 140.0, 136.0, 1.0)
    open_seal = cq.blowthrough_kgh(100_000.0, 1100.0, 140.0, 0.5, 80.0, 140.0, 136.0, 0.0)
    assert sealed == 0.0 < open_seal


def test_passivation_air_loss():
    base = main.stripper_322e001(
        main.CO2_DES_KGH / 1000.0, main.STRIP_STEAM_T_DES_C, main.STRIP_P_DES_BARA,
    )
    tripped = main.stripper_322e001(
        main.CO2_DES_KGH / 1000.0, main.STRIP_STEAM_T_DES_C, main.STRIP_P_DES_BARA,
        air_trip=True,
    )
    assert base["top_kmolh"]["O2"] + base["top_kmolh"]["N2"] > 0.0
    assert tripped["top_kmolh"]["O2"] + tripped["top_kmolh"]["N2"] == 0.0


def test_rectifier_gradients():
    assert _carry(0.95, vapour=150.0) > _carry(0.50)
    assert main.hydrolysis_x_328c003(200.0, main.R328_C003_M746_DES, w_nh3=0.02) < \
        main.hydrolysis_x_328c003(200.0, main.R328_C003_M746_DES, w_nh3=0.0063)


def test_wastewater_gradients():
    design = main.hydrolysis_x_328c003(200.0, main.R328_C003_M746_DES)
    assert main.hydrolysis_x_328c003(205.0, main.R328_C003_M746_DES) > design
    assert main.hydrolysis_x_328c003(200.0, 1.5 * main.R328_C003_M746_DES) < design
    assert main.hydrolysis_x_328c003(200.0, main.R328_C003_M746_DES, vol_ratio=1.5) > design


def test_lpcc_gradients():
    assert _absorption(1.0)["breakthrough_kmolh"] < _absorption(0.5)["breakthrough_kmolh"]
    assert _carry(0.95) > _carry(0.50)
    assert hp_recycle.pump_323p001_flow_m3h(70.0) > hp_recycle.pump_323p001_flow_m3h(35.0)


def test_reflux_condenser_gradients():
    assert _absorption(1.2)["breakthrough_kmolh"] < _absorption(0.6)["breakthrough_kmolh"]
    assert _npsh(0.2, 0.95) < _npsh(4.0, 0.50)


def test_flash_condenser_gradients():
    assert _absorption(1.0)["absorbed"]["NH3"] > _absorption(0.3)["absorbed"]["NH3"]
    assert _carry(0.95) > 0.0


def test_storage_tank_gradients():
    assert _npsh(0.2, 0.95) < _npsh(4.0, 0.50)
    assert main.sol_biuret_xi("C003", main.R323_C003_M_DES, main.W_S314, 110.0) > \
        main.sol_biuret_xi("C003", main.R323_C003_M_DES, main.W_S314, 90.0)
    assert cq.liquor_crystallization_T(main.W_S317) > 70.0


def test_first_desorber_reflux_gradients():
    lean = main.hydrolysis_x_328c003(200.0, main.R328_C003_M746_DES, w_nh3=0.0063)
    ammonia_rich = main.hydrolysis_x_328c003(200.0, main.R328_C003_M746_DES, w_nh3=0.02)
    assert ammonia_rich < lean
    assert _carry(0.90, vapour=150.0) > _carry(0.50)


def test_manifest_evidence_names_are_executable():
    available = globals()
    missing = sorted({item.evidence_test for item in SCENARIO_REQUIREMENTS if item.evidence_test not in available})
    assert not missing, missing
