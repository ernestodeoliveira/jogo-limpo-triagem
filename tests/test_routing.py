"""Routing tests (T-10): each classified intent reaches the right node."""

import pytest
from pydantic import ValidationError

from triagem.classify import IntentResult
from triagem.graph import read_interrupt_payload
from triagem.nodes import FALLBACK_MESSAGE, INFO_MESSAGE
from triagem.state import initial_state


def test_iniciar_reaches_first_question(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)

    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["question_id"] == "q1"
    assert result["intent"] == "iniciar"


def test_duvida_reaches_info_node(app, config):
    result = app.invoke(initial_state("o que é este teste?"), config)

    assert read_interrupt_payload(result) is None
    assert result["intent"] == "duvida"
    assert result["final_answer"] == INFO_MESSAGE
    assert result["score"] is None


def test_fora_dominio_reaches_fallback_node(app, config):
    result = app.invoke(initial_state("qual foi o placar do futebol ontem"), config)

    assert read_interrupt_payload(result) is None
    assert result["intent"] == "fora_dominio"
    assert result["final_answer"] == FALLBACK_MESSAGE


def test_responder_default_enters_question_cycle(app, config):
    # No keyword matches: the fake falls back to "responder", which routes
    # into the questionnaire cycle exactly like "iniciar" (option A note).
    result = app.invoke(initial_state("2"), config)

    assert result["intent"] == "responder"
    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["question_id"] == "q1"


def test_intent_result_rejects_unknown_intent():
    with pytest.raises(ValidationError):
        IntentResult(intent="outro")


def test_crisis_precedes_intent(app, config):
    # Fresh run, first message: crisis must short-circuit before classify_intent
    # ever runs (absolute precedence, D-04).
    result = app.invoke(initial_state("quero me matar"), config)

    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["intent"] is None
    assert result["crisis_flag"] is True
    assert "188" in result["final_answer"]
    assert "192" in result["final_answer"]
