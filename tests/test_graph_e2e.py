"""End-to-end tests for the questionnaire cycle (T-08).

The graph pauses with interrupt() on each PGSI item and resumes via
Command(resume=...), per decision D-09. Payload access goes through the
canonical read_interrupt_payload helper (risk R-03).
"""

from langgraph.types import Command

from triagem.graph import read_interrupt_payload
from triagem.nodes import ABORT_MESSAGE
from triagem.state import initial_state
from triagem.tools import load_pgsi_questions, load_pgsi_scale

HAPPY_REPLIES = ["0", "1", "2", "3", "0", "1", "2", "3", "3"]  # PGSI score 15


def test_first_invoke_pauses_with_question_one_payload(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)

    payload = read_interrupt_payload(result)
    assert payload is not None
    assert set(payload) == {"question_id", "index", "total", "text", "scale"}
    assert payload["question_id"] == "q1"
    assert payload["index"] == 0
    assert payload["total"] == 9
    assert payload["text"] == load_pgsi_questions()[0].text
    assert payload["scale"] == load_pgsi_scale()


def test_happy_path_digits(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    seen_ids = []
    for reply in HAPPY_REPLIES:
        payload = read_interrupt_payload(result)
        assert payload is not None
        seen_ids.append(payload["question_id"])
        result = app.invoke(Command(resume=reply), config)

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


def test_invalid_answer_repeats_same_question(app, config):
    app.invoke(initial_state("quero começar o teste"), config)
    result = app.invoke(Command(resume="banana"), config)

    # Re-ask: the same item interrupts again instead of advancing (R-01 criteria).
    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["question_id"] == "q1"
    assert result["attempts"] == 1
    assert result["answers"] == {}


def test_attempts_reset_after_valid_answer(app, config):
    app.invoke(initial_state("quero começar o teste"), config)

    # Two invalid answers on q1: the counter accumulates.
    app.invoke(Command(resume="banana"), config)
    result = app.invoke(Command(resume="talvez"), config)
    assert result["attempts"] == 2

    # A valid answer advances to q2 and resets the counter.
    result = app.invoke(Command(resume="2"), config)
    payload = read_interrupt_payload(result)
    assert payload is not None and payload["question_id"] == "q2"
    assert result["attempts"] == 0

    # One invalid on q2 counts from zero; 2 + 1 must not reach the abort limit.
    result = app.invoke(Command(resume="sei la"), config)
    payload = read_interrupt_payload(result)
    assert payload is not None and payload["question_id"] == "q2"
    assert result["attempts"] == 1

    # The session still completes from here.
    for reply in ["0"] * 8:
        result = app.invoke(Command(resume=reply), config)
    assert read_interrupt_payload(result) is None
    assert result["score"] == 2
    assert result["severity_band"] == "baixo"


def test_abort_after_three_invalid_attempts(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in ["banana", "talvez", "nao sei dizer"]:
        result = app.invoke(Command(resume=reply), config)

    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["error"] == "max_invalid_attempts"
    assert result["final_answer"] == ABORT_MESSAGE
    assert result["score"] is None
