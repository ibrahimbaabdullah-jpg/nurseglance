"""Unit tests for the case-selection window logic. No data needed."""
from datetime import datetime

from etl.select_cases import candidate_handoffs, count_between, is_icu_unit, overlaps


def test_handoffs_need_24h_before_and_2h_after():
    times = candidate_handoffs(datetime(2150, 1, 1, 10, 0), datetime(2150, 1, 4, 8, 0))
    # 24 h after admission is Jan 2 10:00, so the first shift change is 19:00.
    # Jan 4 07:00 is excluded because the patient leaves 1 h later.
    assert times == [datetime(2150, 1, 2, 19), datetime(2150, 1, 3, 7), datetime(2150, 1, 3, 19)]


def test_count_between_excludes_start_and_includes_end():
    times = [datetime(2150, 1, 1, h) for h in (6, 7, 8)]
    assert count_between(times, datetime(2150, 1, 1, 6), datetime(2150, 1, 1, 8)) == 2


def test_overlaps():
    iv = [(datetime(2150, 1, 1, 0), datetime(2150, 1, 1, 6))]
    assert overlaps(iv, datetime(2150, 1, 1, 5), datetime(2150, 1, 1, 9))
    assert not overlaps(iv, datetime(2150, 1, 1, 6), datetime(2150, 1, 1, 9))


def test_step_down_units_are_not_icu():
    assert is_icu_unit("Medical Intensive Care Unit (MICU)")
    assert not is_icu_unit("Neuro Stepdown")
    assert not is_icu_unit("Neuro Intermediate")
