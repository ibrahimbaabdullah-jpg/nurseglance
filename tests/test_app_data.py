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
        assert f'<div class="ng-h">{system}' in glance.panel_html(case, system, data.handoff(case)).replace("&amp;", "&")


@needs_cases
@pytest.mark.parametrize("case_id", CASES)
def test_every_element_is_shown_once(case_id):
    """Each element appears as a row, by name in a panel's none / not charted line, or as a header chip."""
    import re

    from app import glance
    case = data.load_case(case_id)
    ref = data.handoff(case)
    page = "".join(glance.panel_html(case, s, ref) for s in data.ORGAN_SYSTEMS)
    rows = set(re.findall(r'data-eid="([a-z0-9_]+)"', page))
    empty = " ".join(re.findall(r'<div class="ng-empty">(.*?)</div>', page)).replace("&amp;", "&")
    header = glance.header_html(case, ref)
    chips = {"code_status": "Code status", "allergies": "Allergies", "precautions": "Isolation"}
    for eid, el in case["elements"].items():
        if eid in glance.HEADER_EIDS:
            assert chips[eid] in header, eid
            assert eid not in rows, f"{eid} is shown twice"
        else:
            assert eid in rows or glance.short(el["label"]) in empty, eid


@needs_cases
def test_meds_strip_lists_running_drips_and_next_doses():
    from app import glance
    case = data.load_case("S1")
    strip = glance.meds_strip(case, data.handoff(case))
    assert "Heparin Sodium" in strip and "21:37" in strip and "OxyCODONE" in strip
    assert "Done, last 12 h" in strip and "Turned" in strip and "placeholder rule" in strip


def test_diagnoses_sorted_puts_external_causes_last():
    dx = [{"code": "Y838", "version": "ICD-10"}, {"code": "Z66", "version": "ICD-10"},
          {"code": "I609", "version": "ICD-10"}, {"code": "E8788", "version": "ICD-9"}]
    assert [d["code"] for d in sorted(dx, key=data.dx_rank)] == ["I609", "Z66", "Y838", "E8788"]
