"""Study mode: scoring formulas (hand-calculated), randomization, answer keys and flags."""
import pytest

from app import data, flags, scoring, study


# ---- SUS: odd items (r - 1), even items (5 - r), sum x 2.5
def test_sus_best_and_worst():
    assert scoring.sus_score([5, 1] * 5) == 100.0
    assert scoring.sus_score([1, 5] * 5) == 0.0


def test_sus_neutral_is_50():
    assert scoring.sus_score([3] * 10) == 50.0


def test_sus_hand_calculated():
    # odd: 4,5,4,3,4 -> 3+4+3+2+3 = 15 ; even: 2,1,2,2,1 -> 3+4+3+3+4 = 17 ; (15+17)*2.5 = 80
    assert scoring.sus_score([4, 2, 5, 1, 4, 2, 3, 2, 4, 1]) == 80.0


def test_sus_rejects_bad_input():
    with pytest.raises(ValueError):
        scoring.sus_score([3] * 9)
    with pytest.raises(ValueError):
        scoring.sus_score([0] + [3] * 9)


def test_tlx_raw_is_mean_of_six():
    ratings = {"mental": 70, "physical": 10, "temporal": 50, "performance": 30, "effort": 60, "frustration": 20}
    assert scoring.tlx_raw(ratings) == 40.0   # 240 / 6
    with pytest.raises(ValueError):
        scoring.tlx_raw({"mental": 50})


@pytest.mark.parametrize("q,answer,expected", [
    ({"answer_type": "number", "answer": 3.2, "tolerance": 0.05}, "3.2", True),
    ({"answer_type": "number", "answer": 3.2, "tolerance": 0.05}, "3.3", False),
    ({"answer_type": "number", "answer": 3.2, "tolerance": 0.05}, "abc", False),
    ({"answer_type": "choice", "answer": "Falling"}, "falling", True),
    ({"answer_type": "time", "answer": "21:37", "tolerance_min": 30}, "21:15", True),
    ({"answer_type": "time", "answer": "00:10", "tolerance_min": 30}, "23:50", True),   # across midnight
    ({"answer_type": "time", "answer": "21:37", "tolerance_min": 30}, "22:30", False),
    ({"answer_type": "text"}, "bleeding risk", None),
])
def test_check_answer(q, answer, expected):
    assert scoring.check_answer(q, answer) is expected


# ---- randomization
def test_plan_balances_views_and_cases():
    for seed in range(200):
        plan = study.make_plan(seed)
        assert sorted(b["view"] for b in plan) == ["glance", "tabbed"]
        all_cases = [c for b in plan for c in b["cases"]]
        assert sorted(all_cases) == ["C1", "C2", "S1", "S2"]
        for block in plan:
            assert sorted(c[0] for c in block["cases"]) == ["C", "S"]


def test_plan_is_reproducible_and_varies():
    assert study.make_plan(41) == study.make_plan(41)
    plans = {str(study.make_plan(s)) for s in range(200)}
    assert len(plans) == 32   # 2 view orders x 2 x 2 case-to-view assignments x 2 x 2 case orders


def test_steps_have_16_questions_and_2_surveys():
    steps = study.make_steps(study.make_plan(7), study.load_questions())
    assert sum(s["kind"] == "question" for s in steps) == 16
    assert sum(s["kind"] == "survey" for s in steps) == 2
    assert steps[-1]["kind"] == "done"


def test_steps_follow_the_protocol_order():
    """Per view: 2 practice questions, 8 timed, the surveys; one break between the views."""
    plan = study.make_plan(7)
    steps = study.make_steps(plan, study.load_questions(), study.load_practice())
    kinds = [s["kind"] for s in steps]
    block = ["practice"] * 2 + ["question"] * 8 + ["survey"]
    assert kinds == block + ["break"] + block + ["done"]
    practice = [s for s in steps if s["kind"] == "practice"]
    assert [s["view"] for s in practice] == [plan[0]["view"]] * 2 + [plan[1]["view"]] * 2
    assert len({s["question"]["id"] for s in practice}) == 4   # no practice question repeats
    assert all(s["case_id"] not in ("S1", "S2", "C1", "C2") for s in practice)


def test_practice_keys_match_the_practice_case():
    case = data.load_case("P1")
    for q in study.load_practice():
        if q["kind"] == "lookup":
            assert scoring.check_answer(q, case["elements"][q["elements"][0]]["latest"]["value"]), q["id"]
        else:
            drug = q["text"].split("next ")[1].split(" dose")[0].lower()
            times = sorted(m["t"] for m in case["med_administrations"]
                           if m["relative"] == "after_handoff" and drug in m["name"].lower())
            assert times and times[0][11:16] == q["answer"], q["id"]


def test_paused_time_is_left_out():
    steps = study.make_steps(study.make_plan(1), study.load_questions())
    q = steps[0]["question"]
    base = {"run_id": "R1", "seed": 1, "view": steps[0]["view"], "case_id": q["case_id"], "question_id": q["id"],
            "target": "", "value": ""}
    rows = [dict(base, ts_utc="2026-11-28T10:00:00.000Z", event="question_shown"),
            dict(base, ts_utc="2026-11-28T10:00:04.000Z", event="pause"),
            dict(base, ts_utc="2026-11-28T10:01:04.000Z", event="resume"),
            dict(base, ts_utc="2026-11-28T10:01:10.000Z", event="answer_submit", target="submit")]
    assert study.summarize(rows, steps)[0]["time_s"] == 10.0   # 70 s on the clock, 60 s paused


# ---- answer keys still match the case files
@pytest.mark.parametrize("q", [q for qs in study.load_questions().values() for q in qs
                               if q["kind"] == "lookup"], ids=lambda q: q["id"])
def test_lookup_keys_match_case_data(q):
    case = data.load_case(q["case_id"])
    el = case["elements"][q["elements"][0]]
    if el["display_rule"] == "running":
        value = next(d["rate"] for d in el["running"] if "orepinephrine" in d["label"])
    else:
        value = el["latest"]["value"]
    assert scoring.check_answer(q, value)


def test_timing_keys_match_emar():
    for qs in study.load_questions().values():
        for q in qs:
            if q["kind"] != "timing":
                continue
            case = data.load_case(q["case_id"])
            drug = q["text"].split("next ")[1].split(" dose")[0].lower()
            times = sorted(m["t"] for m in case["med_administrations"]
                           if m["relative"] == "after_handoff" and drug in m["name"].lower())
            assert times and times[0][11:16] == q["answer"], q["id"]


# ---- flags
def test_flags_carry_rule_and_evidence():
    found = {f.rule_id: f for f in flags.evaluate(data.load_case("C1"))}
    assert {"map_low", "pressor", "lactate", "uop"} <= set(found)
    ev = found["map_low"].evidence[0]
    assert ev["value"] == 64 and ev["t"] and ev["fhir_id"]
    assert "65" in found["map_low"].rule


def test_flags_quiet_for_stable_patient():
    ids = {f.rule_id for f in flags.evaluate(data.load_case("S2"))}
    assert "map_low" not in ids and "pressor" not in ids


# ---- summary
def test_summary_times_and_counts():
    steps = study.make_steps(study.make_plan(1), study.load_questions())
    q = steps[0]["question"]
    base = {"run_id": "R1", "seed": 1, "view": steps[0]["view"], "case_id": q["case_id"], "question_id": q["id"]}
    rows = [dict(base, ts_utc="2026-11-28T10:00:00.000Z", event="question_shown", target="", value=""),
            dict(base, ts_utc="2026-11-28T10:00:05.000Z", event="tab_switch", target="Labs", value=""),
            dict(base, ts_utc="2026-11-28T10:00:07.000Z", event="tab_switch", target="Meds", value=""),
            dict(base, ts_utc="2026-11-28T10:00:12.500Z", event="answer_submit", target="submit",
                 value=str(q.get("answer", "")))]
    out = study.summarize(rows, steps)[0]
    assert out["time_s"] == 12.5 and out["interactions"] == 2 and out["screens_visited"] == 3


def test_returning_to_a_finished_study_restores_its_log_context():
    done = {"run_id": "R017", "seed": 6}
    assert study.context_for(done, None) == {"run_id": "R017", "seed": 6}            # Handoff page cleared it
    assert study.context_for(done, {"run_id": "VN", "seed": ""})["run_id"] == "R017"  # virtual-nurse page replaced it
    assert study.context_for(done, {"run_id": "R017", "seed": 6, "view": ""}) is None


def test_study_export_leaves_out_other_pages_events():
    rows = [{"run_id": "R017", "event": "session_end"}, {"run_id": "VN", "event": "toggle"}]
    assert study.study_rows({"run_id": "R017"}, rows) == rows[:1]


def test_saving_again_with_the_same_stamp_overwrites(tmp_path, monkeypatch):
    monkeypatch.setattr(study, "LOG_DIR", tmp_path)
    study.save_local("R017", "a\n", "s\n", "20261127-010000")
    study.save_local("R017", "a\nnote\n", "s\n", "20261127-010000")
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == ["R017_20261127-010000_events.csv", "R017_20261127-010000_summary.csv"]
    assert "note" in (tmp_path / files[0]).read_text()

