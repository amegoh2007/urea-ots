"""Regression tests for hand-valve opening indicators on evaporation pages."""

from pathlib import Path
import re

import pytest


OVERLAYS = Path(__file__).resolve().parents[1] / "frontend" / "overlays.js"

VALVE_DISPLAYS = (
    ("screen-323-1", "HIC-323605", "RECIRC_323.F010.HV_323605"),
    ("screen-323-1", "HV-323605", "RECIRC_323.F010.HV_323605"),
    ("screen-324-1", "HIC-323605", "RECIRC_323.F010.HV_323605"),
    ("screen-324-1", "HV-323605", "RECIRC_323.F010.HV_323605"),
    ("screen-324-1b", "HIC-329606", "EVAP_324.E003.HIC_329606"),
    ("screen-324-1b", "HV-329606", "EVAP_324.E003.HV_329606"),
)


def _overlay_records():
    records = {}
    page = None
    for line in OVERLAYS.read_text(encoding="utf-8").splitlines():
        page_match = re.match(r"\s*'(screen-[^']+)':\s*\[", line)
        if page_match:
            page = page_match.group(1)
        tag_match = re.search(r"tag:\s*'([^']+)'", line)
        if page and tag_match:
            records[(page, tag_match.group(1))] = line
    return records


@pytest.mark.parametrize("page,tag,expected_bind", VALVE_DISPLAYS)
def test_hand_valve_display_uses_opening_telemetry(page, tag, expected_bind):
    record = _overlay_records()[(page, tag)]

    assert f"bind: '{expected_bind}'" in record


@pytest.mark.parametrize("page,tag,_expected_bind", VALVE_DISPLAYS)
def test_hand_valve_display_uses_percent_unit(page, tag, _expected_bind):
    record = _overlay_records()[(page, tag)]

    assert re.search(r"u:\s*'%'", record)
