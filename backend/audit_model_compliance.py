"""Executable audit probes for the plant-wide modelling requirements.

This is intentionally not a pytest module: known open gaps make several checks fail.
Run from ``backend`` with ``python audit_model_compliance.py``.  A non-zero exit
means the simulator is not yet compliant with every requested MESH/flowsheet rule.
"""

from __future__ import annotations

import json
from pathlib import Path

import main
import steam_system


results: list[dict] = []


def check(name: str, passed: bool, evidence) -> None:
    results.append({"check": name, "passed": bool(passed), "evidence": evidence})


def pfd_stream_count() -> int:
    source = (Path(__file__).resolve().parent.parent / "References"
              / "Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md")
    section = ""
    streams: set[str] = set()
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line
        elif line.startswith("| STREAM No.") and "Cooling_Water" not in section and "Granulation" not in section:
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            streams.update(cell for cell in cells[2:] if cell)
    return len(streams)


# Design-point structural and balance checks.
main.state = main.State()
packet = main.step_sim(0.1)
streams = packet["STREAMS"]
required_stream_fields = {
    "T_C", "P_bara", "mass_kgh", "mol_kmolh", "component_kmolh",
    "component_kgh", "enthalpy_kJkg", "enthalpy_flow_kW",
}
check("stream schema carries required state fields",
      all(required_stream_fields <= set(stream) for stream in streams.values()),
      {"registry_count": len(streams), "required_fields": sorted(required_stream_fields)})

reference_streams = pfd_stream_count()
check("all in-scope PFD streams have canonical records",
      len(streams) >= reference_streams,
      {"registry_records": len(streams), "unique_reference_stream_numbers": reference_streams})

known_h = sum(stream["enthalpy_kJkg"] is not None for stream in streams.values())
check("all canonical streams carry calculated enthalpy",
      known_h == len(streams),
      {"with_enthalpy": known_h, "registry_records": len(streams)})

clip = packet["SPECIES_323_324"]["clip_resid_kgh"]
check("downstream component balances close",
      all(abs(value) <= 1e-6 for value in clip.values()), clip)

thermo_diag = {tag: main._DIAG[tag] for tag in ("E001", "E003")}
check("Unit 324 VLE is routed through the Extended-UNIQUAC boundary",
      all(diag.get("thermo_model") == main.extended_uniquac.MODEL_NAME
          for diag in thermo_diag.values()),
      {tag: {key: diag[key] for key in (
          "thermo_model", "thermo_validity", "thermo_px_residual_bara",
          "iteration_count", "iteration_residual", "converged",
      )} for tag, diag in thermo_diag.items()})

zero_feed = {species: 0.0 for species in main.MW_COMP}
zero_strip = main.stripper_322e001(
    0.0, main.STRIP_STEAM_T_DES_C, main.STRIP_P_DES_BARA,
    overflow_kmolh=zero_feed,
)
check("322E001 reaction extents are bounded by available reactants",
      zero_strip["xi_hyd"] == 0.0 and zero_strip["xi_biu"] == 0.0
      and zero_strip["top_kgh"] == 0.0 and zero_strip["bot_kgh"] == 0.0,
      {key: zero_strip[key] for key in ("xi_hyd", "xi_biu", "top_kgh", "bot_kgh")})

q328 = packet["ABSORB_328"]["D003"]
q328_evidence = {key: q328[key] for key in ("Q328_in_kW", "Q328_out_kW", "Q328_resid_kW")}
check("unit 328 energy balance closes",
      abs(q328["Q328_resid_kW"]) <= 1.0, q328_evidence)

tear_metric = packet.get("RECYCLE_TEAR_RESIDUAL", {})
check("recycle tear residual is observed without claiming an inner solve",
      tear_metric.get("is_solver_convergence") is False,
      tear_metric)


# Live pressure must reach the canonical stream state.
main.state = main.State()
main.state.p_syn_bara = 130.0
expected_strip_p = main.STRIP_P_DES_BARA * 130.0 / main.SYN_P_DES_BARA
packet = main.step_sim(0.1)
streams = packet["STREAMS"]
check("CO2 and stripper stream pressures use live solved nodes",
      streams["CO2_FEED"]["P_bara"] == round(packet["CO2_FEED"]["PIC_322203"], 1)
      and streams["STRIP_TOP"]["P_bara"] == round(expected_strip_p, 1)
      and streams["STRIP_BOT"]["P_bara"] == round(expected_strip_p, 1),
      {key: streams[key]["P_bara"] for key in ("CO2_FEED", "STRIP_TOP", "STRIP_BOT")})


# Internal LP-header pressure is a real thermodynamic disturbance, but the HPCC gate ignores it.
main.state = main.State()
main.state.steam.P_LP = 6.5
gate = main._disturbance_gate(main.state)
packet = main.step_sim(0.1)
lp = packet["STEAM_SYSTEM"]["LP"]
check("LP pressure perturbation propagates into HPCC shell temperature",
      abs(lp["TI_HPCC_shell"] - lp["TI_sat"]) <= 0.1,
      {"gate": gate, "P_LP_bara": lp["P_bara"], "T_sat_C": lp["TI_sat"],
       "T_HPCC_shell_C": lp["TI_HPCC_shell"]})


# Stage-1 evaporation equilibrium must use its actual separator pressure.
main.state = main.State()
main.state.r324_f001_P = 0.60
main.step_sim(0.1)
used_weq = main._DIAG["E001"]["weq"]
live_weq = main.evap_w_eq(
    main.state.r324_e001_T, main.state.r324_f001_P,
    main.R324_W_EV1, main.R324_E001_T_SP_C, main.R324_F001_P_BARA,
)
check("324E001 phase equilibrium uses live separator pressure",
      abs(used_weq - live_weq) <= 1e-9,
      {"P_live_bara": main.state.r324_f001_P, "w_eq_used": used_weq,
       "w_eq_at_live_pressure": live_weq})


# 329D009 has live 9-bar users in this runtime (notably 324E003), yet its design inflow is zero.
main.state = main.State()
packet = main.step_sim(0.1)
actual_903_kgh = main.state.steam.m_903 * 3600.0
check("9-bar steam header includes implemented downstream demand",
      abs(actual_903_kgh - steam_system.M_903_DES * 3600.0) <= 1.0,
      {"actual_903_kgh": actual_903_kgh,
       "PFD_design_903_kgh": steam_system.M_903_DES * 3600.0,
       "324E003_Q_kW": packet["EVAP_324"]["E003"]["Q_kW"]})


print(json.dumps(results, indent=2, sort_keys=True))
failed = sum(not item["passed"] for item in results)
print(f"\nMODEL AUDIT: {len(results) - failed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
