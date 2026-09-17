"""Pure physical-law helpers for the HP carbamate-recycle path."""

from __future__ import annotations

from typing import Mapping


P323_DISPLACEMENT_M3_PER_REV = 0.5046
P323_MIN_RUNNING_RPM = 19.0
P323_MAX_RUNNING_RPM = 81.0


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), low), high)


def pump_323p001_flow_m3h(rpm: float, suction_factor: float = 1.0) -> float:
    """Return 323P001 displacement flow; discharge pressure is not a flow input."""
    if rpm <= 0.0:
        return 0.0
    running_rpm = _clamp(rpm, P323_MIN_RUNNING_RPM, P323_MAX_RUNNING_RPM)
    return P323_DISPLACEMENT_M3_PER_REV * running_rpm * _clamp(suction_factor, 0.0, 1.0)


def reactive_scrubber_split(
    gas_feed: Mapping[str, float],
    wash: Mapping[str, float],
    design_absorption_capacity: Mapping[str, float],
    capacity_ratio: float,
) -> dict:
    """Split scrubber feeds by finite reactive-absorption capacity.

    Components absent from ``design_absorption_capacity`` remain in the gas.
    Wash enters the liquid outlet.  The returned component closure is zero to
    floating-point precision by construction.
    """
    components = set(gas_feed) | set(wash) | set(design_absorption_capacity)
    ratio = max(float(capacity_ratio), 0.0)
    gas, liquid, absorbed, closure = {}, {}, {}, {}
    for component in components:
        gas_in = max(float(gas_feed.get(component, 0.0)), 0.0)
        wash_in = max(float(wash.get(component, 0.0)), 0.0)
        capacity = max(float(design_absorption_capacity.get(component, 0.0)), 0.0) * ratio
        absorbed_i = min(gas_in, capacity)
        gas[component] = gas_in - absorbed_i
        liquid[component] = wash_in + absorbed_i
        absorbed[component] = absorbed_i
        closure[component] = gas_in + wash_in - gas[component] - liquid[component]
    return {
        "gas": gas,
        "liquid": liquid,
        "absorbed": absorbed,
        "closure": closure,
        "breakthrough_kmolh": gas.get("NH3", 0.0) + gas.get("CO2", 0.0),
    }


def capacity_limited_vent(
    available: Mapping[str, float],
    molecular_weights: Mapping[str, float],
    capacity_kgh: float,
) -> dict:
    """Vent available gas up to valve mass capacity and retain the excess."""
    components = set(available) | set(molecular_weights)
    available_kgh = sum(
        max(float(available.get(component, 0.0)), 0.0)
        * max(float(molecular_weights.get(component, 0.0)), 0.0)
        for component in components
    )
    capacity = max(float(capacity_kgh), 0.0)
    vent_fraction = min(capacity / available_kgh, 1.0) if available_kgh > 0.0 else 0.0
    vented = {
        component: max(float(available.get(component, 0.0)), 0.0) * vent_fraction
        for component in components
    }
    retained = {
        component: max(float(available.get(component, 0.0)), 0.0) - vented[component]
        for component in components
    }
    vented_kgh = available_kgh * vent_fraction
    return {
        "vented": vented,
        "retained": retained,
        "available_kgh": available_kgh,
        "vented_kgh": vented_kgh,
        "retained_kgh": available_kgh - vented_kgh,
        "capacity_kgh": capacity,
        "vent_fraction": vent_fraction,
    }


def conversion_loss_burden(
    design_extent_kmolh: float,
    actual_extent_kmolh: float,
    carbamate_dissociation_kj_per_kmol: float = 105000.0,
    steam_latent_kj_per_kg: float = 1850.0,
) -> dict:
    """Return the minimum recycle and steam burden caused by lost conversion."""
    unconverted = max(float(design_extent_kmolh) - float(actual_extent_kmolh), 0.0)
    recycle_kgh = unconverted * (44.0 + 2.0 * 17.0)
    steam_kgh = (
        unconverted * max(float(carbamate_dissociation_kj_per_kmol), 0.0)
        / max(float(steam_latent_kj_per_kg), 1e-9)
    )
    return {
        "unconverted_co2_kmolh": unconverted,
        "hpcc_recycle_increment_kgh": recycle_kgh,
        "stripper_steam_increment_kgh": steam_kgh,
    }


def sustainable_load_factor(recycle_scale: float, synthesis_load_scale: float) -> float:
    """Return the maximum sustainable load fraction supported by recycle flow."""
    load = max(float(synthesis_load_scale), 1e-9)
    return _clamp(float(recycle_scale) / load, 0.0, 1.0)
