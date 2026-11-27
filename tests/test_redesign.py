"""Version 1.1 screens: header facts with their sources, the task strip, the control's tabs,
the virtual-nurse note and the researcher console's completeness check."""
import pytest

from app import data, glance, research, study, tabbed, vn


def test_reason_for_admission_prefers_the_ed_chief_complaint():
    s1, c1 = data.load_case("S1"), data.load_case("C1")
    assert data.reason_for_admission(s1)["text"] == "L Leg DVT"
    assert "8661-1" in data.reason_for_admission(s1)["source"]
    fallback = data.reason_for_admission(c1)
    assert fallback["kind"] == "diagnoses" and "no billing priority" in fallback["source"]


def test_code_status_falls_back_to_the_dnr_code_and_says_so():
    c2 = data.code_status(data.load_case("C2"))
    assert c2["text"] == "DNR" and c2["alert"] and "Z66" in c2["source"]
    assert data.code_status(data.load_case("S2"))["text"] == "Not charted"


def test_allergies_are_never_invented():
    for cid in data.available_cases():
        a = data.allergies(data.load_case(cid))
        assert a["text"] == "Not in FHIR demo" and a["empty"]


def test_vte_prophylaxis_names_its_source():
    s1 = data.vte_prophylaxis(data.load_case("S1"))
    assert "heparin infusion" in s1["text"]            # therapeutic, not prophylaxis
    p1 = data.vte_prophylaxis(data.load_case("P1"))
    assert "heparin SQ" in p1["text"] and "eMAR" in p1["source"]
    assert "compression sleeve" in data.vte_prophylaxis(data.load_case("S2"))["text"]


def test_tasks_done_skip_care_that_was_not_done():
    case = {"stay": {"handoff_time": "2150-01-03T19:00:00"}, "med_administrations": [], "observations": [
        {"t": "2150-01-03T12:00:00", "label": "Oral Care", "value": None, "value_text": "Swab", "source": "c"},
        {"t": "2150-01-03T16:00:00", "label": "Oral Care", "value": None, "value_text": "Deferred", "source": "c"},
        {"t": "2150-01-03T14:00:00", "label": "Eye Care", "value": 0, "value_text": None, "source": "c"},
        {"t": "2150-01-03T18:00:00", "label": "Turn", "value": None, "value_text": "Side to Side", "source": "c"},
    ]}
    done = {t["name"]: t for t in data.tasks_done(case)}
    assert done["Oral care"]["count"] == 1 and "deferred" in done["Oral care"]["note"]
    assert done["Eye care"]["count"] == 0
    turn = data.turn_due(case)
    assert turn["t"] == "2150-01-03T20:00:00" and not turn["overdue"]


def test_header_and_strip_render_for_every_case():
    for cid in data.available_cases():
        case = data.load_case(cid)
        ref = data.handoff(case)
        head = glance.header_html(case, ref)
        for chip in ("Code status", "Allergies", "Isolation", "VTE prophylaxis"):
            assert chip in head
        strip = glance.meds_strip(case, ref)
        assert "Running now" in strip and "Done, last 12 h" in strip and "Due, next 12 h" in strip


def test_running_drips_show_their_titration():
    strip = glance.meds_strip(data.load_case("C2"), data.handoff(data.load_case("C2")))
    assert "Norepinephrine</b> 0.04 mcg/kg/min <small>↓ from 0.2</small>" in strip


def test_control_has_six_tabs_and_no_notes_tab():
    assert tabbed.TABS == ["Summary", "Flowsheet", "Labs", "MAR", "Problems", "Lines & drains"]
    assert "Home meds" in tabbed.MAR_SECTIONS


def test_vn_note_lists_what_is_left_to_confirm():
    case = data.load_case("S1")
    items = vn.checklist_items(case, "Admission")
    checked = [i % 2 == 0 for i in range(len(items))]
    note = vn.handoff_note(case, "Admission", items, checked, 372)
    assert note.startswith("Virtual admission review · S1")
    assert f"Reviewed {sum(checked)} of {len(items)} items in 06:12." in note
    assert "Still to confirm with the bedside nurse:" in note
    still = note.split("Still to confirm")[1]
    assert items[1][1] in still and items[0][1] + " (not in the chart)" in still   # unchecked items
    assert items[2][1] not in still                                                 # a checked item


def test_vn_checklist_marks_what_the_chart_cannot_cover():
    items = {item: covered for _, item, _, covered in vn.checklist_items(data.load_case("S2"), "Discharge")}
    assert items["Allergies"] is False and items["Teaching and follow-up"] is False
    assert items["Infusions running"] is True


@pytest.mark.parametrize("drop,complete", [(None, True), ("session_end", False), ("answer_submit", False)])
def test_researcher_check_flags_incomplete_runs(drop, complete):
    import csv
    with open(research.EXAMPLE_EVENTS, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if drop == "answer_submit":
        first = next(i for i, r in enumerate(rows) if r["event"] == drop)
        rows = rows[:first] + rows[first + 1:]
    elif drop:
        rows = [r for r in rows if r["event"] != drop]
    assert research.check_run(rows)["complete"] is complete


def test_progress_counts_patients_across_the_session():
    plan = study.make_plan(6)
    steps = study.make_steps(plan, study.load_questions(), study.load_practice())
    st_ = {"steps": steps, "plan": plan}
    first_q = next(i for i, s in enumerate(steps) if s["kind"] == "question")
    label, frac = study.progress_text(st_, first_q)
    assert label.startswith("Question 1 of 16 · patient 1 of 4") and frac == 0
    last_q = max(i for i, s in enumerate(steps) if s["kind"] == "question")
    assert study.progress_text(st_, last_q)[0].startswith("Question 16 of 16 · patient 4 of 4")
    assert study.progress_text(st_, 0)[0].startswith("Practice 1 of 2 · not scored")
