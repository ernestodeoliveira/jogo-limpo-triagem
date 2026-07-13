"""Crisis detection gate with absolute precedence (T-14, decision D-04).

This gate runs before intent classification (safety_gate_node, from START)
and again on every resumed reply inside the questionnaire cycle (Q4, inside
validate_answer_node and retry_offer_node in nodes.py): a person in acute
distress must never be kept inside the PGSI flow, regardless of where they
are in it.
"""

from typing import Literal

from triagem.parsing import normalize
from triagem.state import TriageState

_SUICIDAL_PHRASES = [
    "me matar",
    "me suicidar",
    "quero morrer",
    "vontade de morrer",
    "tirar minha vida",
    "tirar a minha vida",
    "acabar com tudo",
    "acabar com minha vida",
    "acabar com a minha vida",
    "nao quero mais viver",
    "desistir de viver",
    "cansado de viver",
    "cansada de viver",
]
_SUICIDAL_WORDS = ["suicidio", "suicida", "morrer"]
_SELF_HARM_PHRASES = ["me machucar", "me cortar", "me ferir"]
_SELF_HARM_WORDS = ["autolesao", "automutilacao", "overdose"]
_ACUTE_DISTRESS_PHRASES = ["nao aguento mais", "sem saida", "preciso de ajuda urgente"]
_ACUTE_DISTRESS_WORDS = ["socorro", "desesperado", "desesperada"]

# Deliberately includes the bare word "morrer" despite the obvious
# false-positive risk (e.g. "morrer de rir"): decision D-04 accepts false
# positives as the safer failure mode for a gambling-harm screening tool
# (risk R-05 asks for high recall), and the cost of a false positive here is
# just ending the triage early with support resources shown, which is
# recoverable (the person can restart). "jogar"/"me jogar" are deliberately
# NOT included: they collide with the questionnaire's own gambling
# vocabulary and would make the whole PGSI conversation untestable.
CRISIS_TERMS: frozenset[str] = frozenset(
    _SUICIDAL_PHRASES
    + _SUICIDAL_WORDS
    + _SELF_HARM_PHRASES
    + _SELF_HARM_WORDS
    + _ACUTE_DISTRESS_PHRASES
    + _ACUTE_DISTRESS_WORDS
)

CRISIS_MESSAGE = (
    "Percebi que você pode estar passando por um momento muito difícil. Sua "
    "segurança é mais importante do que esta triagem, então vou encerrar por "
    "aqui. Você pode ligar para o CVV pelo telefone 188 (gratuito, 24 horas "
    "por dia, todos os dias) para conversar com alguém agora, ou para o SAMU "
    "pelo telefone 192 em caso de emergência. Você não precisa passar por "
    "isso sozinho ou sozinha."
)


def _contains_any(normalized: str, terms: frozenset[str]) -> bool:
    """Whole-word match for single words, substring match for phrases.

    Independent implementation of the same rule used in fakes.py's
    _contains_any (offline test infrastructure): safety.py is production
    code and must not import from fakes.py.
    """
    words = set(normalized.split())
    for term in terms:
        if " " in term:
            if term in normalized:
                return True
        elif term in words:
            return True
    return False


def check_crisis(text: str) -> bool:
    """True when text contains any crisis term, by the whole-word/phrase rule."""
    return _contains_any(normalize(text), CRISIS_TERMS)


def safety_gate_node(state: TriageState) -> dict:
    """Entry-point crisis check, run once from START before classify_intent."""
    if check_crisis(state["user_input"]):
        return {"crisis_flag": True}
    return {}


def route_safety(state: TriageState) -> Literal["ok", "crisis_node"]:
    return "crisis_node" if state["crisis_flag"] else "ok"


def crisis_node(state: TriageState) -> dict:
    """Terminal node: acolhimento + CVV 188 + SAMU 192; ends the triage."""
    return {"final_answer": CRISIS_MESSAGE, "phase": "crise", "crisis_flag": True}
