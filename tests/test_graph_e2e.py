"""End-to-end tests for the questionnaire cycle (T-08).

The graph pauses with interrupt() on each PGSI item and resumes via
Command(resume=...), per decision D-09. Payload access goes through the
canonical read_interrupt_payload helper (risk R-03).
"""

from uuid import uuid4

from langgraph.types import Command

from triagem.graph import build_agent, read_interrupt_payload
from triagem.nodes import ABORT_MESSAGE
from triagem.state import initial_state
from triagem.tools import load_pgsi_questions, load_pgsi_scale

HAPPY_REPLIES = ["0", "1", "2", "3", "0", "1", "2", "3", "3"]  # PGSI score 15


def _config() -> dict:
    return {"configurable": {"thread_id": uuid4().hex}}


def test_first_invoke_pauses_with_question_one_payload():
    app = build_agent(None)

    result = app.invoke(initial_state("quero começar o teste"), _config())

    payload = read_interrupt_payload(result)
    assert payload is not None
    assert set(payload) == {"question_id", "index", "total", "text", "scale"}
    assert payload["question_id"] == "q1"
    assert payload["index"] == 0
    assert payload["total"] == 9
    assert payload["text"] == load_pgsi_questions()[0].text
    assert payload["scale"] == load_pgsi_scale()


def test_happy_path_digits():
    app = build_agent(None)
    cfg = _config()

    result = app.invoke(initial_state("quero começar o teste"), cfg)
    seen_ids = []
    for reply in HAPPY_REPLIES:
        payload = read_interrupt_payload(result)
        assert payload is not None
        seen_ids.append(payload["question_id"])
        result = app.invoke(Command(resume=reply), cfg)

    assert seen_ids == [f"q{i}" for i in range(1, 10)]
    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["answers"] == {
        "q1": 0, "q2": 1, "q3": 2, "q4": 3, "q5": 0,
        "q6": 1, "q7": 2, "q8": 3, "q9": 3,
    }
    assert result["score"] == 15
    assert result["severity_band"] == "alto"
    assert isinstance(result["final_answer"], str) and "15" in result["final_answer"]


def test_invalid_answer_repeats_same_question():
    app = build_agent(None)
    cfg = _config()

    app.invoke(initial_state("quero começar o teste"), cfg)
    result = app.invoke(Command(resume="banana"), cfg)

    # Re-ask: the same item interrupts again instead of advancing (R-01 criteria).
    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["question_id"] == "q1"
    assert result["attempts"] == 1
    assert result["answers"] == {}


def test_abort_after_three_invalid_attempts():
    app = build_agent(None)
    cfg = _config()

    result = app.invoke(initial_state("quero começar o teste"), cfg)
    for reply in ["banana", "talvez", "nao sei dizer"]:
        result = app.invoke(Command(resume=reply), cfg)

    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["error"] == "max_invalid_attempts"
    assert result["final_answer"] == ABORT_MESSAGE
    assert result["score"] is None
