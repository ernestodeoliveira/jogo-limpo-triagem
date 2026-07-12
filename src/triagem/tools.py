"""Deterministic tools for the PGSI triage agent."""

import json
from pathlib import Path

from pydantic import BaseModel

EXPECTED_ITEM_IDS = [f"q{i}" for i in range(1, 10)]


class PGSIDataError(Exception):
    """Raised when the PGSI data file is missing, malformed or incomplete."""


class Question(BaseModel):
    id: str
    text: str


def load_pgsi_questions(path: str = "data/pgsi.json") -> list[Question]:
    """Load and validate the PGSI items: exactly 9, ids q1..q9 in order, non-empty text.

    Raises PGSIDataError with a clear message when the file is malformed.
    """
    file = Path(path)
    if not file.is_file():
        raise PGSIDataError(f"PGSI data file not found: {path}")
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PGSIDataError(f"PGSI data file is not valid JSON: {exc}") from exc
    items = raw.get("items") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        raise PGSIDataError("PGSI data must contain an 'items' list")
    if len(items) != 9:
        raise PGSIDataError(f"PGSI requires exactly 9 items, found {len(items)}")
    questions: list[Question] = []
    for expected_id, item in zip(EXPECTED_ITEM_IDS, items):
        item_id = item.get("id") if isinstance(item, dict) else None
        text = item.get("text") if isinstance(item, dict) else None
        if item_id != expected_id:
            raise PGSIDataError(f"expected item '{expected_id}', found '{item_id}'")
        if not isinstance(text, str) or not text.strip():
            raise PGSIDataError(f"item '{expected_id}' has empty or missing text")
        questions.append(Question(id=item_id, text=text))
    return questions


class ScoreResult(BaseModel):
    score: int  # 0..27
    answers: dict[str, int]


def compute_pgsi_score(answers: dict[str, int]) -> ScoreResult:
    """Controlled pure scoring: requires exactly q1..q9 with int values 0..3.

    Raises ValueError on any violation; never returns a partial score. No I/O.
    """
    missing = [item_id for item_id in EXPECTED_ITEM_IDS if item_id not in answers]
    if missing:
        raise ValueError(f"missing answers for: {', '.join(missing)}")
    extra = sorted(key for key in answers if key not in EXPECTED_ITEM_IDS)
    if extra:
        raise ValueError(f"unexpected answer keys: {', '.join(extra)}")
    for item_id in EXPECTED_ITEM_IDS:
        value = answers[item_id]
        if type(value) is not int or not 0 <= value <= 3:
            raise ValueError(
                f"answer '{item_id}' must be an int between 0 and 3, got {value!r}"
            )
    return ScoreResult(
        score=sum(answers[item_id] for item_id in EXPECTED_ITEM_IDS),
        answers=dict(answers),
    )
