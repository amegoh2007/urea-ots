"""Traceable process-scenario coverage and thermodynamic package routing.

Each manifest entry maps one actionable Markdown subsection to a causal driver,
one local response, one downstream response, and an executable evidence family.
It prevents broad scenario documents from degrading into a few hand-picked flags.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioRequirement:
    source: str
    section: str
    driver: str
    local_observable: str
    downstream_observable: str
    evidence_test: str


def _r(source: str, section: str, driver: str, local: str, downstream: str,
       evidence: str) -> ScenarioRequirement:
    return ScenarioRequirement(source, section, driver, local, downstream, evidence)


SCENARIO_REQUIREMENTS = (
    # Scenarios.md — synthesis, pre-evaporation, and vacuum evaporation.
    _r("Scenarios.md", "1.1", "reactor high level", "reactor liquid carryover",
       "scrubber flooding, stripper load, and synthesis pressure", "test_reactor_level_consequences"),
    _r("Scenarios.md", "1.2", "reactor low level", "residence time and liquid-seal loss",
       "stripper gas blow-through, conversion loss, and recycle load", "test_reactor_level_consequences"),
    _r("Scenarios.md", "2.1", "atmospheric flash tank high level", "vapour-line liquid carryover",
       "condenser flooding and condensate contamination", "test_atmospheric_flash_level_consequences"),
    _r("Scenarios.md", "2.2", "atmospheric flash tank low level", "liquid-seal and NPSH loss",
       "downstream vacuum degradation and temperature rise", "test_atmospheric_flash_level_consequences"),
    _r("Scenarios.md", "3.1", "pre-evaporator steam flow", "flash duty and concentration",
       "condenser load, downstream steam demand, and biuret", "test_evaporator_heat_pressure_temperature_laws"),
    _r("Scenarios.md", "3.2", "pre-evaporator drum pressure", "boiling point and flashing rate",
       "temperature, biuret, and pump NPSH", "test_evaporator_heat_pressure_temperature_laws"),
    _r("Scenarios.md", "3.3", "pre-evaporator discharge temperature", "water retention or flashing",
       "biuret, viscosity, crystallization, and transfer flow", "test_evaporator_heat_pressure_temperature_laws"),
    _r("Scenarios.md", "4.1", "first-stage evaporator steam", "vapour generation and melt strength",
       "vacuum load, second-stage load, and biuret", "test_evaporator_heat_pressure_temperature_laws"),
    _r("Scenarios.md", "4.2", "first-stage separator pressure", "boiling point and auto-refrigeration",
       "biuret or crystallization and restricted flow", "test_evaporator_heat_pressure_temperature_laws"),
    _r("Scenarios.md", "4.3", "first-stage discharge temperature", "reaction and saturation margin",
       "second-stage flashing or line restriction", "test_evaporator_heat_pressure_temperature_laws"),
    _r("Scenarios.md", "5.1", "second-stage evaporator steam", "final moisture and vapour velocity",
       "product quality, condenser entrainment, and biuret", "test_final_evaporator_consequences"),
    _r("Scenarios.md", "5.2", "second-stage separator pressure", "boiling point and flash cooling",
       "biuret, wet product, or melt freezing", "test_final_evaporator_consequences"),
    _r("Scenarios.md", "5.3", "second-stage discharge temperature", "final melt reaction and phase margin",
       "product failure and line blockage", "test_final_evaporator_consequences"),
    _r("Scenarios.md", "5.4", "second-stage discharge-line level", "residence time or hydraulic-seal loss",
       "condenser flooding, atmospheric ingress, and vacuum collapse", "test_final_evaporator_consequences"),

    # Scenarios2.md — HP operation, LP rectification, and wastewater treatment.
    _r("Scenarios2.md", "1.1", "HP ejector opening decrease", "scrubber sump draw and overflow temperature",
       "HPCC feed temperature and tempered-water return", "test_hp_scrubber_operator_gradients"),
    _r("Scenarios2.md", "1.2", "HP scrubber vent opening", "hot vent flow and scrubber condensation",
       "synthesis pressure and LP absorber load", "test_hp_scrubber_operator_gradients"),
    _r("Scenarios2.md", "1.3", "HP scrubber recycle carbamate flow", "absorption and sump inventory",
       "synthesis pressure, HPCC traffic, and temperatures", "test_hp_scrubber_operator_gradients"),
    _r("Scenarios2.md", "1.4", "HP scrubber tempered-water temperature and flow", "heat removal and condensation",
       "synthesis pressure, sump level, and outlet temperatures", "test_hp_scrubber_operator_gradients"),
    _r("Scenarios2.md", "2.1", "HP stripper steam", "stripping efficiency and bottoms temperature",
       "HPCC vapour load, LP load, steam export, and biuret", "test_hp_stripper_operator_gradients"),
    _r("Scenarios2.md", "2.2", "HP stripper level", "film flooding or liquid-seal loss",
       "LP carbamate overload or gas blow-through", "test_hp_stripper_operator_gradients"),
    _r("Scenarios2.md", "2.3", "HP stripper level-valve step", "sump drain or accumulation",
       "LP surge, dry-out, or delayed carbamate release", "test_hp_stripper_operator_gradients"),
    _r("Scenarios2.md", "3.1", "reactor downcomer valve step", "reactor and stripper inventory transfer",
       "stripper flooding, dry-out, corrosion, and pressure", "test_reactor_downcomer_gradients"),
    _r("Scenarios2.md", "3.2", "passivation-air loss", "noncondensable inventory loss",
       "HP pressure drop, HPCC response, and LP absorber overload", "test_passivation_air_loss"),
    _r("Scenarios2.md", "4.1", "rectifying-column steam", "volatile stripping and bottoms purity",
       "LPCC load, water recycle, vacuum, and biuret", "test_rectifier_gradients"),
    _r("Scenarios2.md", "4.2", "rectifying-column level", "carryover or liquid-seal loss",
       "LPCC contamination or vacuum blow-through", "test_rectifier_gradients"),
    _r("Scenarios2.md", "4.3", "rectifying level-valve step", "liquid surge or starvation",
       "evaporator temperature, vacuum, and crystallization", "test_rectifier_gradients"),
    _r("Scenarios2.md", "5.1", "wastewater feed flow", "residence time, temperature, and column traffic",
       "reflux load and final urea/ammonia slip", "test_wastewater_gradients"),
    _r("Scenarios2.md", "5.2", "lower-desorber steam", "NH3 stripping and column pressure drop",
       "hydrolyzer inhibition, reflux load, and final slip", "test_wastewater_gradients"),
    _r("Scenarios2.md", "5.3", "hydrolyzer steam", "hydrolysis kinetics and temperature",
       "first-desorber vapour load and final urea slip", "test_wastewater_gradients"),

    # Scenarios3.md — LPCC, condensers, storage, and rectification.
    _r("Scenarios3.md", "1.1", "LPCC ammonia-water flow", "absorption and crystallization margin",
       "atmospheric vent load, recycle H/C, and reactor conversion", "test_lpcc_gradients"),
    _r("Scenarios3.md", "1.2", "LPCC drum level", "vapour space or pump NPSH",
       "atmospheric entrainment or HP recycle loss", "test_lpcc_gradients"),
    _r("Scenarios3.md", "1.3", "LPCC drum pressure", "condensation temperature and upstream backpressure",
       "rectifier efficiency and atmospheric vent load", "test_lpcc_gradients"),
    _r("Scenarios3.md", "1.4", "LPCC cooling-water temperature", "heat-transfer driving force",
       "pressure, venting, or carbamate crystallization", "test_lpcc_gradients"),
    _r("Scenarios3.md", "1.5", "LPCC cooling-water flow", "heat removal and wall subcooling",
       "pressure, venting, or exchanger fouling", "test_lpcc_gradients"),
    _r("Scenarios3.md", "1.6", "LPCC reflux-pump solution flow", "tail-gas scrubbing",
       "ammonia emissions, water balance, and reactor H/C", "test_lpcc_gradients"),
    _r("Scenarios3.md", "1.7", "lean-carbamate pump flow", "LPCC inventory draw or backup",
       "pump cavitation, HP wash, and synthesis N/C", "test_lpcc_gradients"),
    _r("Scenarios3.md", "2.1", "reflux-condenser ammonia-water flow", "dilution and absorption",
       "plugging, atmospheric venting, and reactor H/C", "test_reflux_condenser_gradients"),
    _r("Scenarios3.md", "2.2", "reflux accumulator level", "vapour space or reflux-pump NPSH",
       "vent entrainment or desorber/hydrolyzer efficiency", "test_reflux_condenser_gradients"),
    _r("Scenarios3.md", "2.3", "reflux-condenser pressure", "condensation temperature and backpressure",
       "desorber stripping, hydrolyzer load, and venting", "test_reflux_condenser_gradients"),
    _r("Scenarios3.md", "2.4", "lean-carbamate flow to reflux condenser", "cold absorbent capacity",
       "condenser pressure, venting, and LPCC NPSH", "test_reflux_condenser_gradients"),
    _r("Scenarios3.md", "3.1", "flash-condenser ammonia-water flow", "absorption and temperature",
       "backpressure, emissions, and wastewater hydraulic load", "test_flash_condenser_gradients"),
    _r("Scenarios3.md", "3.2", "flash-condenser accumulator level", "vapour space or extraction-pump NPSH",
       "vent entrainment or downstream wastewater flow", "test_flash_condenser_gradients"),
    _r("Scenarios3.md", "4.1", "ammonia-water tank level", "overflow or pump static head",
       "contaminated drainage or absorber solvent loss", "test_storage_tank_gradients"),
    _r("Scenarios3.md", "4.2", "ammonia-water tank temperature", "NH3 solubility and vapour pressure",
       "atmospheric emissions and pump NPSH", "test_storage_tank_gradients"),
    _r("Scenarios3.md", "4.3", "urea-solution tank level", "residence time or pump availability",
       "biuret or evaporation-section shutdown", "test_storage_tank_gradients"),
    _r("Scenarios3.md", "4.4", "urea-solution tank temperature", "biuret/hydrolysis or crystallization",
       "vent load or evaporator-feed loss", "test_storage_tank_gradients"),
    _r("Scenarios3.md", "5.1", "first-desorber reflux flow", "top temperature and tray loading",
       "steam demand, hydrolyzer inhibition, or condenser fouling", "test_first_desorber_reflux_gradients"),
    _r("Scenarios3.md", "6.1", "rectifying-column pressure", "boiling point, gas velocity, and condensation",
       "steam demand, LPCC venting, entrainment, and fouling", "test_rectifier_gradients"),
)


_THERMO_PACKAGES = {
    "HP_SYNTHESIS": "VOSKOV_VORONIN_HP_UNIQUAC_VIRIAL",
    "LP_NH3_CO2_H2O": "DARDE_EXTENDED_UNIQUAC_SRK",
    "UREA_WATER_VACUUM": "NEUTRAL_UNIQUAC_IAPWS_IF97",
    "STEAM_WATER": "IAPWS_IF97",
}


def thermo_package_for(section: str) -> str:
    """Return the approved package name for a process domain."""
    try:
        return _THERMO_PACKAGES[section]
    except KeyError as exc:
        raise ValueError(f"unknown thermodynamic section: {section}") from exc


__all__ = ["SCENARIO_REQUIREMENTS", "ScenarioRequirement", "thermo_package_for"]
