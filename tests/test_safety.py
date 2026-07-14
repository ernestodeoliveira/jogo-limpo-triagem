"""Unit tests for the crisis detection gate (T-14, decision D-04)."""

import pytest

from triagem.safety import (
    CRISIS_TERMS,
    check_crisis,
    crisis_node,
    route_safety,
    safety_gate_node,
)
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
        # Hyphenated phrasing must still match: normalize() folds '-' to a
        # space for word-splitting consumers like this one (B-16 review
        # finding: a fix scoped to parsing.py's answer table must not
        # regress the crisis gate, which shares normalize()).
        "quero-morrer",
        "socorro-urgente",
        "me-matar, por favor",
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


_SENTENCE_TEMPLATES = {
    "me matar": "às vezes eu só penso em me matar e não sei mais o que fazer",
    "me suicidar": "estou pensando seriamente em me suicidar essa semana",
    "quero morrer": "eu só quero morrer, não aguento mais nada",
    "vontade de morrer": "tenho tido muita vontade de morrer ultimamente",
    "tirar minha vida": "cheguei a pensar em tirar minha vida ontem à noite",
    "tirar a minha vida": "penso em tirar a minha vida quando fico sozinho",
    "acabar com tudo": "só quero acabar com tudo de uma vez",
    "acabar com minha vida": "penso em acabar com minha vida quase todo dia",
    "acabar com a minha vida": "quero acabar com a minha vida, não vejo mais saída",
    "nao quero mais viver": "eu não quero mais viver desse jeito",
    "desistir de viver": "estou perto de desistir de viver",
    "cansado de viver": "estou tão cansado de viver, nada faz mais sentido",
    "cansada de viver": "estou cansada de viver, queria que tudo parasse",
    "suicidio": "já pensei em cometer suicídio mais de uma vez",
    "suicida": "eu me sinto suicida hoje, preciso conversar com alguém",
    "morrer": "às vezes bate uma vontade enorme de simplesmente morrer",
    "me machucar": "tenho vontade de me machucar quando fico muito triste",
    "me cortar": "às vezes penso em me cortar para aliviar a dor",
    "me ferir": "tive vontade de me ferir de propósito ontem",
    "autolesao": "tenho praticado autolesão nas últimas semanas",
    "automutilacao": "estou lidando com automutilação há um tempo",
    "overdose": "pensei em tomar uma overdose de remédios",
    "nao aguento mais": "eu não aguento mais essa situação, preciso de ajuda",
    "sem saida": "me sinto completamente sem saída, não sei o que fazer",
    "preciso de ajuda urgente": "preciso de ajuda urgente, não sei mais o que fazer",
    "socorro": "socorro, eu não aguento mais essa dor",
    "desesperado": "estou muito desesperado, não vejo mais solução",
    "desesperada": "estou desesperada e não sei a quem recorrer",
}


def test_check_crisis_every_term_fires():
    # Canary: keeps this corpus honest if CRISIS_TERMS ever changes.
    assert set(_SENTENCE_TEMPLATES) == CRISIS_TERMS
    for term, sentence in _SENTENCE_TEMPLATES.items():
        assert check_crisis(sentence) is True, (
            f"term {term!r} did not fire in: {sentence!r}"
        )


@pytest.mark.parametrize(
    "text",
    [
        "não aguento mais viver desse jeito",
        "só quero morrer mesmo",
        "socorro, não aguento mais isso",
        "tô com vontade de morrer, não aguento mais",
        "quero acabar com tudo, não vejo outra saída",
        "eu simplesmente não quero mais viver",
    ],
)
def test_check_crisis_colloquial_positives(text):
    assert check_crisis(text) is True


# Known recall gaps (F-12): plausible PT-BR colloquial expressions of crisis
# that CRISIS_TERMS does not currently catch. Documented here rather than
# fixed: widening safety.py's recall is a production-code change and needs
# its own explicit decision, out of scope for this test-only audit session.
#   - "quero sumir do mapa" (no term matches "sumir")
#   - "não tenho mais forças pra continuar" (no term matches "forcas")
#   - "seria melhor se eu não existisse" (no term matches "existir")
#   - "cansei de tudo isso, não aguento" (missing the exact three-word phrase
#     "nao aguento mais"; drops "mais")
#   - "cortei meus pulsos ontem" (does not contain the phrase "me cortar")
#   - "não vejo mais saída pra minha vida" (does not contain the phrase
#     "sem saida"; has "mais saida" instead of "sem saida")
