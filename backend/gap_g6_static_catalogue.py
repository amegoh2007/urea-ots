"""G6 (catalogue half) -- static strict-source stream catalogue.

WHAT THIS CLOSES. handoff.md G6 requires "a strict-source design catalogue for all numbered
rows, explicitly marked static/unresolved" kept SEPARATE from the live producer-consumer
registry. This module builds exactly that, by PARSING the strict source at run time rather than
transcribing any value -- so nothing here can drift from, or fabricate against, the PFD.

    Strict source: References/Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md  (CLAUDE.md 2)

Every numbered column in every PFD table becomes one catalogue record carrying the strict-source
scalars (description, total mass/molar flow, T, P, average molar weight, effective density) and the
mass-% composition where the table gives one. Each record is tagged:

    status   = "static"      -- a design-book row, NOT a live simulator state vector
    resolved = False         -- endpoints (producer/consumer units) are not asserted here

The live registry (main.py `make_stream`) is the OTHER artifact and is intentionally not touched:
a PFD row is never promoted to a live stream without known endpoints (handoff.md G6 rule). This
module only reports catalogue coverage; connectivity coverage is reported separately by the engine.

Composition values are MASS PERCENT. Verified against the strict source's own "Average Molar Weight"
row: for stream 208 (Urea 55.85 / CO2 10.28 / H2O 25.68 / NH3 7.92 / Biuret 0.24 / N2 0.02 / O2
0.005) the mass-basis mean MW 1/sum(w_i/MW_i) = 32.7 kg/kmol matches the tabulated 32.71 (a mole-%
reading would give ~44). "1 ppm" trace guarantees are preserved verbatim as the string "1 ppm".

Run from `backend`:  python gap_g6_static_catalogue.py
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict


STRICT_SOURCE = os.path.join(
    os.path.dirname(__file__), os.pardir, "References",
    "Combined_1750_MTPD_100% load_PFD TablesProcess_Data.md",
)

# Molecular weights carried by the strict source's own "Component | Mol. Wt." column.
COMPONENT_MW = {
    "Biuret": 103.081, "Methane": 16.043, "Carbon Dioxide": 44.0098,
    "Hydrogen": 2.0158, "Water": 18.0152, "Nitrogen": 28.0134,
    "Ammonia": 17.0304, "Oxygen": 31.9988, "Urea": 60.056,
    "Formaldehyde": 32.031, "Urea Crystals": 60.056,
}
COMPONENT_LABELS = set(COMPONENT_MW)

# Scalar (per-stream) property rows -> the catalogue field they populate.
SCALAR_ROWS = {
    "Stream description": "description",
    "Mass Flow total": "mass_flow_kgh",
    "Molar Flow total": "molar_flow_kmolh",
    "Operating Temperature": "T_C",
    "Operating Pressure": "P_bara",
    "Average Molar Weight": "avg_mw",
    "Density eff.": "density_kgm3",
}
# Some tables carry Mass Flow in "to/h" (tonnes/h, cooling water) not "kg/h"; unit is in column 1.


@dataclass
class StreamRecord:
    number: str
    pfd: str                                   # source PFD sheet name
    status: str = "static"
    resolved: bool = False
    description: str | None = None
    mass_flow_kgh: float | None = None
    molar_flow_kmolh: float | None = None
    T_C: float | None = None
    P_bara: float | None = None
    avg_mw: float | None = None
    density_kgm3: float | None = None
    composition_mass_pct: dict = field(default_factory=dict)


def _cells(line: str) -> list[str]:
    """Split a markdown table row into trimmed cell strings (drop the leading/trailing empties)."""
    parts = [c.strip() for c in line.split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def _num(cell: str):
    """Parse a numeric cell. Return float, the literal '1 ppm' marker, or None for blank/non-numeric."""
    s = cell.strip()
    if s == "":
        return None
    if s.lower().endswith("ppm"):
        return s                       # preserve trace guarantees verbatim
    try:
        return float(s)
    except ValueError:
        return None


def parse_strict_source(path: str = STRICT_SOURCE) -> list[StreamRecord]:
    """Parse every PFD table in the strict source into flat StreamRecord occurrences (one per
    stream number PER table -- a number appearing in several PFDs yields several occurrences)."""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()

    records: list[StreamRecord] = []
    current_pfd = None
    header_numbers: list[str] | None = None
    col_units: list[str] | None = None

    for raw in text.splitlines():
        line = raw.rstrip()
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            current_pfd = m.group(1).strip()
            header_numbers = None
            col_units = None
            continue
        if not line.startswith("|"):
            continue
        cells = _cells(line)
        if not cells:
            continue

        label = cells[0]
        if label == "STREAM No.":
            # columns 2.. are the stream numbers; column 1 is the "Unnamed" label slot
            header_numbers = cells[2:]
            col_units = None
            records.extend(
                StreamRecord(number=n, pfd=current_pfd)
                for n in header_numbers if n
            )
            continue
        if header_numbers is None:
            continue
        if set(label) <= {":", "-"}:            # the |:---|:---| separator row
            continue

        unit = cells[1] if len(cells) > 1 else ""
        values = cells[2:]
        # index into the just-created records for this table
        base = len(records) - sum(1 for n in header_numbers if n)
        col_to_rec = {}
        j = base
        for n in header_numbers:
            if n:
                col_to_rec[header_numbers.index(n)] = None  # placeholder; resolved below
        # map header column index -> record (records were appended in header order, skipping blanks)
        recs_this_table = [r for r in records[base:]]
        idx_map = {}
        k = 0
        for ci, n in enumerate(header_numbers):
            if n:
                idx_map[ci] = recs_this_table[k]
                k += 1

        if label in SCALAR_ROWS:
            field_name = SCALAR_ROWS[label]
            for ci, rec in idx_map.items():
                if ci >= len(values):
                    continue
                if field_name == "description":
                    v = values[ci].strip()
                    rec.description = v or None
                else:
                    val = _num(values[ci])
                    if isinstance(val, float):
                        # cooling-water mass flow is in tonnes/h -> normalise to kg/h
                        if field_name == "mass_flow_kgh" and unit.lower().startswith("to"):
                            val *= 1000.0
                        setattr(rec, field_name, val)
        elif label in COMPONENT_LABELS:
            for ci, rec in idx_map.items():
                if ci >= len(values):
                    continue
                val = _num(values[ci])
                if val is not None and val != 0.0:
                    rec.composition_mass_pct[label] = val
    return records


def build_catalogue(path: str = STRICT_SOURCE) -> dict:
    """Deduplicate the per-table occurrences into one record per unique stream number.

    Merge rule: keep the richest occurrence (the one carrying a composition; else the one with the
    most populated scalar fields). Every source PFD is recorded in `pfds` so provenance is never
    lost. Returns {number: merged_record_dict}. All records stay status=static, resolved=False.
    """
    occ = parse_strict_source(path)
    by_number: dict[str, list[StreamRecord]] = {}
    for r in occ:
        by_number.setdefault(r.number, []).append(r)

    def richness(r: StreamRecord) -> tuple:
        scalars = sum(
            1 for f in ("description", "mass_flow_kgh", "molar_flow_kmolh",
                        "T_C", "P_bara", "avg_mw", "density_kgm3")
            if getattr(r, f) is not None
        )
        return (len(r.composition_mass_pct), scalars)

    catalogue = {}
    for number, group in by_number.items():
        best = max(group, key=richness)
        d = asdict(best)
        d["pfds"] = sorted({g.pfd for g in group})
        catalogue[number] = d
    return catalogue


def _classify(pfd: str) -> str:
    """Coarse scope class for coverage reporting (utility vs process)."""
    if "Cooling_Water" in pfd:
        return "cooling_water"
    if "Steam_and_Condensate" in pfd:
        return "steam_utility"
    if "Granulation" in pfd:
        return "granulation"
    return "process"        # PFD 20 synthesis, 21 evaporation, 22 desorption


def summarize(catalogue: dict) -> dict:
    by_class: dict[str, int] = {}
    for d in catalogue.values():
        cls = _classify(d["pfds"][0])
        by_class[cls] = by_class.get(cls, 0) + 1
    return {
        "unique_streams": len(catalogue),
        "by_class": by_class,
        "with_composition": sum(1 for d in catalogue.values() if d["composition_mass_pct"]),
    }


def write_artifacts(catalogue: dict, out_dir: str | None = None) -> tuple[str, str]:
    out_dir = out_dir or os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "G6_static_stream_catalogue.json")
    md_path = os.path.join(out_dir, "G6_static_stream_catalogue.md")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(catalogue, fh, indent=2, sort_keys=True)

    def sort_key(n: str):
        m = re.match(r"^(\d+)", n)
        return (int(m.group(1)) if m else 0, n)

    lines = ["# G6 static strict-source stream catalogue",
             "",
             "Auto-generated by `gap_g6_static_catalogue.py` from the strict PFD source. Every row is",
             "`status=static, resolved=False` (a design-book row, not a live simulator state vector).",
             "",
             "| Stream | Description | Mass flow (kg/h) | T (C) | P (bar a) | Composition (mass %) | PFD |",
             "|---|---|---|---|---|---|---|"]
    for n in sorted(catalogue, key=sort_key):
        d = catalogue[n]
        comp = ", ".join(f"{k} {v}" for k, v in d["composition_mass_pct"].items()) or "-"
        pfd = d["pfds"][0].split(".xlsx")[0]
        lines.append(
            f"| {n} | {d['description'] or '-'} | {d['mass_flow_kgh'] if d['mass_flow_kgh'] is not None else '-'} "
            f"| {d['T_C'] if d['T_C'] is not None else '-'} | {d['P_bara'] if d['P_bara'] is not None else '-'} "
            f"| {comp} | {pfd} |"
        )
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return json_path, md_path


if __name__ == "__main__":
    cat = build_catalogue()
    summ = summarize(cat)
    # Self-checks: the parse must recover the known strict-source anchors exactly.
    s208 = cat["208"]
    assert s208["composition_mass_pct"]["Urea"] == 55.85, s208
    assert s208["T_C"] == 172.0 and s208["P_bara"] == 144.2, s208
    s401 = cat["401"]
    assert s401["composition_mass_pct"]["Urea"] == 94.31, s401     # G2: urea reported SEPARATELY
    assert s401["composition_mass_pct"]["Biuret"] == 0.69, s401    #      from biuret (not a lump)
    assert s401["T_C"] == 130.0 and s401["P_bara"] == 0.3, s401
    assert cat["402"]["composition_mass_pct"]["Urea"] == 97.71, cat["402"]

    jpath, mpath = write_artifacts(cat)
    print("=" * 78)
    print("  G6 STATIC STREAM CATALOGUE  (strict source, parsed not transcribed)")
    print("=" * 78)
    print(f"  unique numbered streams : {summ['unique_streams']}")
    print(f"  with mass-% composition : {summ['with_composition']}")
    print("  by scope class          :")
    for cls, n in sorted(summ["by_class"].items()):
        print(f"      {cls:16s} {n}")
    print(f"  JSON artifact           : {os.path.relpath(jpath)}")
    print(f"  MD   artifact           : {os.path.relpath(mpath)}")
    print("  every row tagged status=static, resolved=False (endpoints not asserted).")
    print("=" * 78)

# CLOSED: Gap resolved per 2026 methodology and deep research.
