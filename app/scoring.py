"""Survey scoring and answer checking for study mode.

SUS (Brooke 1996): ten items on a 1-5 scale. Odd items score (response - 1),
even items score (5 - response); the sum times 2.5 gives 0-100.

Raw NASA-TLX (Hart 2006): the unweighted mean of six 0-100 ratings (mental,
physical and temporal demand, performance, effort, frustration). Higher means
more workload, so performance runs from 0 (perfect) to 100 (failure).
"""
from __future__ import annotations

SUS_ITEMS = [
    "I think that I would like to use this system frequently.",
    "I found the system unnecessarily complex.",
    "I thought the system was easy to use.",
    "I think that I would need the support of a technical person to be able to use this system.",
    "I found the various functions in this system were well integrated.",
    "I thought there was too much inconsistency in this system.",
    "I would imagine that most people would learn to use this system very quickly.",
    "I found the system very cumbersome to use.",
    "I felt very confident using the system.",
    "I needed to learn a lot of things before I could get going with this system.",
]

TLX_SCALES = [
    ("mental", "Mental demand", "How mentally demanding was the task?", "Very low", "Very high"),
    ("physical", "Physical demand", "How physically demanding was the task?", "Very low", "Very high"),
    ("temporal", "Temporal demand", "How hurried or rushed was the pace of the task?", "Very low", "Very high"),
    ("performance", "Performance", "How successful were you in accomplishing what you were asked to do?",
     "Perfect", "Failure"),
    ("effort", "Effort", "How hard did you have to work to accomplish your level of performance?",
     "Very low", "Very high"),
    ("frustration", "Frustration", "How insecure, discouraged, irritated, stressed and annoyed were you?",
     "Very low", "Very high"),
]


def sus_score(responses: list[int]) -> float:
    if len(responses) != 10:
        raise ValueError("SUS needs exactly 10 responses")
    if any(r not in (1, 2, 3, 4, 5) for r in responses):
        raise ValueError("SUS responses must be integers from 1 to 5")
    total = sum((r - 1) if i % 2 == 0 else (5 - r) for i, r in enumerate(responses))
    return total * 2.5


def tlx_raw(ratings: dict[str, float]) -> float:
    keys = [k for k, *_ in TLX_SCALES]
    missing = [k for k in keys if k not in ratings]
    if missing:
        raise ValueError(f"NASA-TLX is missing {', '.join(missing)}")
    if any(not 0 <= ratings[k] <= 100 for k in keys):
        raise ValueError("NASA-TLX ratings must be between 0 and 100")
    return sum(ratings[k] for k in keys) / len(keys)


def _minutes(hhmm: str) -> int | None:
    try:
        hours, minutes = hhmm.strip().replace(".", ":").split(":")
        return int(hours) * 60 + int(minutes)
    except (ValueError, AttributeError):
        return None


def check_answer(question: dict, answer) -> bool | None:
    """True or False for auto-scored questions; None for synthesis (scored by rubric later)."""
    kind = question["answer_type"]
    if answer is None or answer == "":
        return False if kind != "text" else None
    if kind == "number":
        try:
            return abs(float(answer) - float(question["answer"])) <= float(question.get("tolerance", 0)) + 1e-9
        except (TypeError, ValueError):
            return False
    if kind == "choice":
        return str(answer).strip().lower() == str(question["answer"]).lower()
    if kind == "time":
        given, key = _minutes(str(answer)), _minutes(question["answer"])
        if given is None:
            return False
        diff = abs(given - key)
        return min(diff, 24 * 60 - diff) <= question.get("tolerance_min", 0)
    return None
