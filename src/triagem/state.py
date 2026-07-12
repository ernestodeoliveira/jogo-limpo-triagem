"""Conversation state for the PGSI triage agent."""

import operator
from typing import Annotated, Literal, TypedDict


class TriageState(TypedDict):
    user_input: str
    intent: Literal["iniciar", "responder", "duvida", "fora_dominio"] | None
    phase: Literal["acolhimento", "triagem", "crise", "resultado"] | None
    current_question: int  # 0..9: index of the next item; 9 means questionnaire complete
    attempts: int  # invalid attempts for the current item
    answers: Annotated[dict, operator.or_]  # {"q1": 2, ...} merged across turns
    crisis_flag: bool
    score: int | None
    severity_band: Literal["sem_risco", "baixo", "moderado", "alto"] | None
    report_path: str | None
    final_answer: str | None
    error: str | None


def initial_state(user_input: str) -> TriageState:
    return TriageState(
        user_input=user_input,
        intent=None,
        phase=None,
        current_question=0,
        attempts=0,
        answers={},
        crisis_flag=False,
        score=None,
        severity_band=None,
        report_path=None,
        final_answer=None,
        error=None,
    )
