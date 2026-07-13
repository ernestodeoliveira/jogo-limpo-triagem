"""End-to-end tests for the questionnaire cycle (T-08).

The graph pauses with interrupt() on each PGSI item and resumes via
Command(resume=...), per decision D-09. Payload access goes through the
canonical read_interrupt_payload helper (risk R-03).
"""

import json
from pathlib import Path

import pytest
from langgraph.types import Command

from triagem.graph import read_interrupt_payload
from triagem.nodes import ABORT_MESSAGE, BAND_EXPLANATIONS, RETRY_HINT, interpret_offer_reply
from triagem.state import initial_state
from triagem.tools import DISCLAIMER, load_pgsi_questions, load_pgsi_scale

HAPPY_REPLIES = ["0", "1", "2", "3", "0", "1", "2", "3", "3"]  # PGSI score 15


def test_first_invoke_pauses_with_question_one_payload(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)

    payload = read_interrupt_payload(result)
    assert payload is not None
    assert set(payload) == {"kind", "question_id", "index", "total", "text", "scale", "hint"}
    assert payload["kind"] == "question"
    assert payload["question_id"] == "q1"
    assert payload["index"] == 0
    assert payload["total"] == 9
    assert payload["text"] == load_pgsi_questions()[0].text
    assert payload["scale"] == load_pgsi_scale()
    assert payload["hint"] is None


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
    assert payload["hint"] == RETRY_HINT
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

    # After the 3rd invalid answer the run pauses with a retry offer, it does
    # not abort directly (Q3): the person gets a choice.
    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["kind"] == "retry_offer"
    assert payload["question_id"] == "q1"

    result = app.invoke(Command(resume="encerrar"), config)
    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["error"] == "max_invalid_attempts"
    assert result["final_answer"] == ABORT_MESSAGE
    assert result["score"] is None


def test_abort_writes_no_report(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in ["banana", "talvez", "nao sei dizer"]:
        result = app.invoke(Command(resume=reply), config)

    # abort_node goes straight to finalize, bypassing report_node entirely.
    result = app.invoke(Command(resume="encerrar"), config)
    assert result["report_path"] is None


def test_retry_and_abort(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in ["banana", "talvez", "nao sei dizer"]:
        result = app.invoke(Command(resume=reply), config)

    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["kind"] == "retry_offer"
    assert payload["question_id"] == "q1"

    # Retry: the same item is re-presented with attempts reset.
    result = app.invoke(Command(resume="tentar de novo"), config)
    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["kind"] == "question"
    assert payload["question_id"] == "q1"
    assert payload["hint"] is None

    # Three more invalid answers reopen the offer.
    for reply in ["banana", "talvez", "nao sei dizer"]:
        result = app.invoke(Command(resume=reply), config)
    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["kind"] == "retry_offer"
    assert payload["question_id"] == "q1"

    result = app.invoke(Command(resume="encerrar"), config)
    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["error"] == "max_invalid_attempts"
    assert result["final_answer"] == ABORT_MESSAGE
    assert result["score"] is None


def test_retry_then_valid_answer_advances(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in ["banana", "talvez", "nao sei dizer"]:
        result = app.invoke(Command(resume=reply), config)

    payload = read_interrupt_payload(result)
    assert payload is not None and payload["kind"] == "retry_offer"

    # "sim" is one of the RETRY_CHOICES, so it must count as a retry.
    result = app.invoke(Command(resume="sim"), config)
    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["kind"] == "question"
    assert payload["question_id"] == "q1"
    assert payload["hint"] is None

    result = app.invoke(Command(resume="2"), config)
    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["question_id"] == "q2"
    assert result["answers"] == {"q1": 2}

    # The session still completes normally from here.
    for reply in ["0"] * 8:
        result = app.invoke(Command(resume=reply), config)
    assert read_interrupt_payload(result) is None
    assert result["answers"]["q1"] == 2


def test_offer_unrecognized_reply_aborts(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in ["banana", "talvez", "nao sei dizer"]:
        result = app.invoke(Command(resume=reply), config)

    payload = read_interrupt_payload(result)
    assert payload is not None and payload["kind"] == "retry_offer"

    # An unrecognized reply defaults to abort (safe default, no re-offering).
    result = app.invoke(Command(resume="xyzzy"), config)
    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["error"] == "max_invalid_attempts"
    assert result["final_answer"] == ABORT_MESSAGE
    assert result["score"] is None


@pytest.mark.parametrize(
    "text",
    [
        "tentar de novo",
        "tentar novamente",
        "quero tentar de novo",
        "tentar",
        "continuar",
        "de novo",
        "novamente",
        "sim",
        "TENTAR DE NOVO",
        "  tentar de novo  ",
        "Tentar De Novo",
    ],
)
def test_interpret_offer_reply_recognizes_retry_choices(text):
    assert interpret_offer_reply(text) == "retry"


@pytest.mark.parametrize(
    "text",
    [
        "não",
        "nao",
        "encerrar",
        "parar",
        "xyzzy",
        "",
        # Negation trap: containment would wrongly match "tentar de novo".
        "não quero tentar de novo",
    ],
)
def test_interpret_offer_reply_defaults_to_abort(text):
    assert interpret_offer_reply(text) == "abort"


def test_crisis_mid_questionnaire(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    result = app.invoke(Command(resume="0"), config)
    result = app.invoke(Command(resume="1"), config)
    result = app.invoke(Command(resume="não aguento mais, quero morrer"), config)

    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["crisis_flag"] is True
    assert result["phase"] == "crise"
    assert "188" in result["final_answer"]
    assert "192" in result["final_answer"]
    assert result["score"] is None
    assert result["answers"] == {"q1": 0, "q2": 1}
    assert result["attempts"] == 0


def test_crisis_writes_no_report(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    result = app.invoke(Command(resume="0"), config)
    result = app.invoke(Command(resume="1"), config)
    result = app.invoke(Command(resume="não aguento mais, quero morrer"), config)

    # crisis_node goes straight to finalize, bypassing report_node entirely.
    assert result["report_path"] is None


def test_crisis_at_retry_offer(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in ["banana", "talvez", "nao sei dizer"]:
        result = app.invoke(Command(resume=reply), config)

    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["kind"] == "retry_offer"

    # Crisis wins outright over the retry-offer flow (D-04): same outcome as
    # a fresh-message crisis, not the abort path an unrecognized reply would
    # otherwise take.
    result = app.invoke(Command(resume="quero me matar"), config)
    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["error"] is None
    assert result["crisis_flag"] is True
    assert "188" in result["final_answer"]
    assert "192" in result["final_answer"]


def test_crisis_at_attempts_boundary_wins_over_retry_offer(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in ["banana", "talvez"]:
        result = app.invoke(Command(resume=reply), config)

    payload = read_interrupt_payload(result)
    assert payload is not None and payload["kind"] == "question"
    assert result["attempts"] == 2

    # The 3rd reply would otherwise hit MAX_ATTEMPTS and route to
    # retry_offer, but it is itself a crisis phrase: the crisis check in
    # validate_answer_node runs before the parser/attempts increment, so it
    # must short-circuit straight to crisis_node instead (D-04).
    result = app.invoke(Command(resume="não aguento mais, quero morrer"), config)
    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["crisis_flag"] is True
    assert result["phase"] == "crise"
    assert "188" in result["final_answer"]
    assert "192" in result["final_answer"]
    assert result["attempts"] == 2
    assert result["error"] is None


def test_full_triage(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in HAPPY_REPLIES:
        result = app.invoke(Command(resume=reply), config)

    assert result["score"] == 15
    assert result["severity_band"] == "alto"
    assert result["phase"] == "resultado"

    report_path = result["report_path"]
    assert report_path is not None
    assert config["configurable"]["thread_id"] in Path(report_path).name

    final = result["final_answer"]
    assert "risco alto" in final
    assert "15" in final
    assert BAND_EXPLANATIONS["alto"] in final
    assert DISCLAIMER in final
    assert report_path in final
    assert "188" in final and "gov.br" in final and "CAPS" in final

    md = Path(report_path)
    assert md.exists() and md.suffix == ".md"
    content = md.read_text(encoding="utf-8")
    for i in range(1, 10):
        assert f"q{i}" in content
    assert "alto" in content

    data = json.loads(md.with_suffix(".json").read_text(encoding="utf-8"))
    assert data["score"] == 15
    assert data["answers"]["q9"] == 3
