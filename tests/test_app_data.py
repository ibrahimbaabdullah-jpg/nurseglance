"""Checks on the app's data helpers and the restored text codes, using the committed case files."""
import pytest

from app import data, timeline
from etl import build_cases

CASES = data.available_cases()
needs_cases = pytest.mark.skipif(not CASES, reason="no case files in data/processed")


def test_value_codes_restore_vent_mode_text():
    codes = build_cases.load_value_codes()
    assert codes[("223849", 49.0)] == "CMV/ASSIST/AutoFlow"
    assert codes[("223791", 0.0)] == "None"


def test_series_prefers_first_item_and_stays_before_handoff():
    case = {"stay": {"handoff_time": "2150-01-03T19:00:00"}, "observations": [
        {"t": "2150-01-03T18:00:00", "item_id": "220181", "value": 70},   # cuff
        {"t": "2150-01-03T18:00:00", "item_id": "220052", "value": 64},   # arterial wins
        {"t": "2150-01-03T17:00:00", "item_id": "220181", "value": 72},
        {"t": "2150-01-03T20:00:00", "item_id": "220052", "value": 50},   # after handoff
        {"t": "2150-01-02T17:00:00", "item_id": "220052", "value": 99},   # outside 12 h
    ]}
    points = data.series(case, "map", hours=12)
    assert [v for _, v in points] == [72, 64]


def test_lab_flag_uses_reference_range():
    assert data.lab_flag({"value": 5.6, "ref_low": 3.5, "ref_high": 5.1}) == "H"
    assert data.lab_flag({"value": 3.0, "ref_low": 3.5, "ref_high": 5.1}) == "L"
    assert data.lab_flag({"value": 4.0, "ref_low": 3.5, "ref_high": 5.1}) == ""
    assert data.lab_flag({"value": None}) == ""


@needs_cases
@pytest.mark.parametrize("case_id", CASES)
def test_every_case_renders_a_timeline(case_id):
    case = data.load_case(case_id)
    doses, running = timeline.timeline_rows(case)
    handoff = data.handoff(case)
    assert all(data.ts(d["t"]) >= handoff for d in doses)
    assert all(r["running_at_handoff"] for r in running)
    fig = timeline.timeline_figure(case)
    assert fig.layout.xaxis.range[1] == data.ts(case["windows"]["lookahead_end"])


@needs_cases
@pytest.mark.parametrize("case_id", CASES)
def test_every_organ_panel_builds(case_id):
    from app import glance
    case = data.load_case(case_id)
    for system in data.ORGAN_SYSTEMS:
        assert f"<h4>{system}" in glance.panel_html(case, system, data.handoff(case)).replace("&amp;", "&")
