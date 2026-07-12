"""Graph nodes for the PGSI triage agent."""

from typing import Literal, TypedDict

from langgraph.types import interrupt

from triagem.state import TriageState
from triagem.tools import compute_pgsi_score, load_pgsi_questions, load_pgsi_scale

SeverityBand = Literal["sem_risco", "baixo", "moderado", "alto"]

MAX_ATTEMPTS = 3
VALID_DIGITS = {"0", "1", "2", "3"}

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

    question_id: str
    index: int
    total: int
    text: str
    scale: dict[str, str]


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


def safety_gate(state: TriageState) -> dict:
    """Stub: crisis detection lands on day 15 (T-14); no state change for now."""
    return {}


def route_safety(state: TriageState) -> Literal["ok"]:
    """Stub route: always "ok" until the crisis heuristic exists (T-14)."""
    return "ok"


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
        question_id=question.id,
        index=index,
        total=len(questions),
        text=question.text,
        scale=scale,
    )
    reply = interrupt(payload)
    return {"user_input": reply if isinstance(reply, str) else str(reply)}


def validate_answer(state: TriageState) -> dict:
    """Validate the resumed answer; only digits "0".."3" are accepted this phase.

    All side effects of the cycle happen here (risk R-02): recording the
    answer, advancing current_question and controlling attempts.
    """
    text = state["user_input"].strip()
    if text in VALID_DIGITS:
        question_id = f"q{state['current_question'] + 1}"
        return {
            "answers": {question_id: int(text)},
            "current_question": state["current_question"] + 1,
            "attempts": 0,
        }
    return {"attempts": state["attempts"] + 1}


def route_after_validation(
    state: TriageState,
) -> Literal["ask_question", "abort_node", "score_node"]:
    if state["attempts"] >= MAX_ATTEMPTS:
        return "abort_node"
    if state["current_question"] >= 9:
        return "score_node"
    return "ask_question"


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
