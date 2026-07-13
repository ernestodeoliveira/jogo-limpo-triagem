"""Graph nodes for the PGSI triage agent."""

from typing import Callable, Literal, TypedDict

from langgraph.types import interrupt

from triagem.parsing import make_answer_parser, normalize
from triagem.safety import check_crisis
from triagem.state import TriageState
from triagem.tools import compute_pgsi_score, load_pgsi_questions, load_pgsi_scale

SeverityBand = Literal["sem_risco", "baixo", "moderado", "alto"]

MAX_ATTEMPTS = 3

BAND_LABELS: dict[SeverityBand, str] = {
    "sem_risco": "sem indicativo de risco",
    "baixo": "risco baixo",
    "moderado": "risco moderado",
    "alto": "risco alto",
}

ABORT_MESSAGE = (
    "Não consegui entender as respostas depois de algumas tentativas, então vou "
    "encerrar a triagem por aqui. Você pode recomeçar quando quiser, respondendo "
    "com um número de 0 a 3 para cada pergunta. Se estiver precisando de apoio "
    "agora, o CVV atende pelo telefone 188, todos os dias, 24 horas."
)

RETRY_HINT = (
    "Não consegui entender sua resposta. Responda com um número de 0 a 3, ou "
    "com as palavras da escala: 0 nunca, 1 às vezes, 2 na maioria das vezes, "
    "3 quase sempre."
)

OFFER_MESSAGE = (
    "Não consegui entender suas respostas. Você quer tentar essa pergunta de "
    "novo ou prefere encerrar por aqui?"
)

RETRY_CHOICES = frozenset({
    "tentar de novo", "tentar novamente", "quero tentar de novo",
    "tentar", "continuar", "de novo", "novamente", "sim",
})

INFO_MESSAGE = (
    "Este é o PGSI (Índice de gravidade de problemas com apostas), um "
    "questionário de triagem com 9 perguntas sobre os últimos 12 meses. Cada "
    "resposta usa uma escala de 0 a 3 (0 nunca, 1 às vezes, 2 na maioria das "
    "vezes, 3 quase sempre). O resultado indica uma faixa educacional de risco "
    "e não é um diagnóstico. Nada além das suas 9 respostas é usado no "
    "resultado. Quando quiser começar, é só dizer."
)

FALLBACK_MESSAGE = (
    "Eu consigo ajudar apenas com a triagem educacional sobre o uso de apostas "
    "(questionário PGSI). Se quiser, podemos começar agora: são 9 perguntas "
    "rápidas sobre os últimos 12 meses."
)


class QuestionPayload(TypedDict):
    """Contract of the interrupt payload delivered by ask_question."""

    kind: Literal["question"]
    question_id: str
    index: int
    total: int
    text: str
    scale: dict[str, str]
    hint: str | None


class OfferPayload(TypedDict):
    """Contract of the interrupt payload delivered by retry_offer_node."""

    kind: Literal["retry_offer"]
    question_id: str
    index: int
    total: int
    text: str


def score_to_band(score: int) -> SeverityBand:
    """Map a PGSI score to its severity band: 0 sem_risco, 1-2 baixo, 3-7 moderado, 8-27 alto."""
    if type(score) is not int or not 0 <= score <= 27:
        raise ValueError(f"score must be an int between 0 and 27, got {score!r}")
    if score == 0:
        return "sem_risco"
    if score <= 2:
        return "baixo"
    if score <= 7:
        return "moderado"
    return "alto"


def ask_question(state: TriageState) -> dict:
    """Deliver the current PGSI item and pause waiting for the answer.

    Idempotent by design (risk R-02): on resume this node re-executes from the
    top, so everything before interrupt() must be pure reads and payload
    building. All cycle side effects live in validate_answer.
    """
    questions = load_pgsi_questions()
    scale = load_pgsi_scale()
    index = state["current_question"]
    question = questions[index]
    payload = QuestionPayload(
        kind="question",
        question_id=question.id,
        index=index,
        total=len(questions),
        text=question.text,
        scale=scale,
        hint=RETRY_HINT if state["attempts"] > 0 else None,
    )
    reply = interrupt(payload)
    return {"user_input": reply if isinstance(reply, str) else str(reply)}


def make_validate_answer_node(llm) -> Callable[[TriageState], dict]:
    """Bind the llm once at build time; the node validates each resumed answer.

    All side effects of the cycle happen here (risk R-02): recording the
    answer, advancing current_question and controlling attempts.
    """
    parser = make_answer_parser(llm)

    def validate_answer_node(state: TriageState) -> dict:
        text = state["user_input"].strip()
        if check_crisis(text):
            return {"crisis_flag": True}
        value = parser(text)
        if value is not None:
            question_id = f"q{state['current_question'] + 1}"
            return {
                "answers": {question_id: value},
                "current_question": state["current_question"] + 1,
                "attempts": 0,
            }
        return {"attempts": state["attempts"] + 1}

    return validate_answer_node


def route_after_validation(
    state: TriageState,
) -> Literal["ask_question", "retry_offer", "score_node", "crisis_node"]:
    if state["crisis_flag"]:
        return "crisis_node"
    if state["attempts"] >= MAX_ATTEMPTS:
        return "retry_offer"
    if state["current_question"] >= 9:
        return "score_node"
    return "ask_question"


def interpret_offer_reply(text: str) -> Literal["retry", "abort"]:
    """Exact match against RETRY_CHOICES; anything else safely defaults to abort.

    Exact match (not substring) matters: a negation like "não quero tentar de
    novo" must not accidentally match "tentar de novo" via containment.
    """
    if normalize(text) in RETRY_CHOICES:
        return "retry"
    return "abort"


def retry_offer_node(state: TriageState) -> dict:
    """Ask whether to retry the current item or quit, after 3 invalid attempts.

    Idempotent by design (risk R-02), same discipline as ask_question:
    everything before interrupt() is a pure read of state. The reply is only
    interpreted after resume, when the side effect (attempts reset) is safe.
    """
    index = state["current_question"]
    payload = OfferPayload(
        kind="retry_offer",
        question_id=f"q{index + 1}",
        index=index,
        total=9,
        text=OFFER_MESSAGE,
    )
    reply = interrupt(payload)
    text = reply if isinstance(reply, str) else str(reply)
    if check_crisis(text):
        # Crisis wins outright, even over the retry offer (D-04): attempts is
        # deliberately left unchanged (still MAX_ATTEMPTS), the retry/abort
        # logic below must not run at all for this reply.
        return {"user_input": text, "crisis_flag": True}
    if interpret_offer_reply(text) == "retry":
        return {"user_input": text, "attempts": 0}
    return {"user_input": text}


def route_after_offer(
    state: TriageState,
) -> Literal["ask_question", "abort_node", "crisis_node"]:
    """Read the decision retry_offer_node already made, do not reclassify it.

    Crisis is checked first: retry_offer_node's crisis branch does not reset
    attempts, so attempts stays at MAX_ATTEMPTS same as the abort branch, and
    crisis_flag is the only reliable signal to tell them apart.

    Otherwise, retry_offer only has one incoming edge (from
    route_after_validation at the attempts limit), so after retry_offer_node
    runs attempts is either exactly 0 (retry branch reset it) or unchanged at
    MAX_ATTEMPTS (abort branch left it alone): a reliable proxy for the
    node's own decision.
    """
    if state["crisis_flag"]:
        return "crisis_node"
    return "ask_question" if state["attempts"] == 0 else "abort_node"


def abort_node(state: TriageState) -> dict:
    """Polite closure after repeated invalid answers, with support resources."""
    return {"final_answer": ABORT_MESSAGE, "error": "max_invalid_attempts"}


def info_node(state: TriageState) -> dict:
    """Static explanation of the test, the scale and privacy (RF-02)."""
    return {"final_answer": INFO_MESSAGE}


def fallback_node(state: TriageState) -> dict:
    """Gentle redirect to the agent's purpose for off-domain messages (RF-02)."""
    return {"final_answer": FALLBACK_MESSAGE}


def score_node(state: TriageState) -> dict:
    """Controlled scoring: the number comes only from compute_pgsi_score (D-06)."""
    return {"score": compute_pgsi_score(state["answers"]).score}


def band_node(state: TriageState) -> dict:
    return {"severity_band": score_to_band(state["score"])}


def finalize_node(state: TriageState) -> dict:
    """Assemble the final output; minimal this phase, enriched later (T-16).

    Passes through when an earlier node (abort, info, fallback) already
    produced the final message.
    """
    if state["final_answer"] is not None:
        return {}
    band_label = BAND_LABELS[state["severity_band"]]
    return {
        "final_answer": (
            f"Resultado da triagem PGSI: pontuação {state['score']} de 27 "
            f"({band_label}). Esta é uma triagem educacional e não substitui "
            "avaliação profissional."
        )
    }
