"""Unit tests for the crisis detection gate (T-14, decision D-04)."""

import pytest

from triagem.safety import check_crisis, crisis_node, route_safety, safety_gate_node
from triagem.state import initial_state


@pytest.mark.parametrize(
    "text",
    [
        "quero me matar",
        "Quero me matar!",
        "QUERO ME MATAR",
        "não aguento mais, quero morrer",
        "Não aguento mais, quero morrer.",
        "NAO AGUENTO MAIS QUERO MORRER",
        "estou pensando em suicídio",
        "Estou pensando em SUICÍDIO...",
        "vou me machucar",
        "Vou me machucar!",
        "Socorro!",
        "socorro",
        "SOCORRO",
        "sem saída",
        "Sem saída...",
        "SEM SAÍDA",
    ],
)
def test_check_crisis_positives(text):
    assert check_crisis(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "quero começar o teste",
        "nunca",
        "3",
        "às vezes",
        "na maioria das vezes",
        "aposto quase sempre",
        "perdi dinheiro ontem",
    ],
)
def test_check_crisis_negatives(text):
    assert check_crisis(text) is False


def test_safety_gate_sets_flag():
    state = initial_state("quero me matar")
    assert safety_gate_node(state) == {"crisis_flag": True}


def test_safety_gate_noop():
    state = initial_state("quero começar o teste")
    assert safety_gate_node(state) == {}


def test_route_safety_reads_flag():
    crisis_state = initial_state("quero me matar")
    crisis_state["crisis_flag"] = True
    assert route_safety(crisis_state) == "crisis_node"

    ok_state = initial_state("quero começar o teste")
    assert route_safety(ok_state) == "ok"


def test_crisis_node_output():
    state = initial_state("quero me matar")
    result = crisis_node(state)
    assert "188" in result["final_answer"]
    assert "192" in result["final_answer"]
    assert result["phase"] == "crise"
    assert result["crisis_flag"] is True
