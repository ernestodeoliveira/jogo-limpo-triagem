"""Graph assembly for the PGSI triage agent."""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from triagem.nodes import (
    QuestionPayload,
    abort_node,
    ask_question,
    band_node,
    finalize_node,
    route_after_validation,
    route_safety,
    safety_gate,
    score_node,
    validate_answer,
)
from triagem.state import TriageState, initial_state

__all__ = ["build_agent", "initial_state", "read_interrupt_payload"]


def read_interrupt_payload(result: dict) -> QuestionPayload | None:
    """Single access point for the pending interrupt payload (risk R-03).

    Returns the .value of the pending Interrupt, or None when the run
    completed. Reused by the tests now and by cli.py later (T-17). Every
    interrupt in this graph carries a QuestionPayload.
    """
    pending = result.get("__interrupt__") or ()
    return pending[0].value if pending else None


def build_agent(llm=None, checkpointer=None):
    """Compile the triage graph with a checkpointer (required by interrupt, D-09).

    The llm parameter is accepted but unused until T-10 wires classify_intent.
    """
    builder = StateGraph(TriageState)
    builder.add_node("safety_gate", safety_gate)
    builder.add_node("ask_question", ask_question)
    builder.add_node("validate_answer", validate_answer)
    builder.add_node("abort_node", abort_node)
    builder.add_node("score_node", score_node)
    builder.add_node("band_node", band_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "safety_gate")
    builder.add_conditional_edges("safety_gate", route_safety, {"ok": "ask_question"})
    builder.add_edge("ask_question", "validate_answer")
    builder.add_conditional_edges(
        "validate_answer",
        route_after_validation,
        {
            "ask_question": "ask_question",
            "abort_node": "abort_node",
            "score_node": "score_node",
        },
    )
    builder.add_edge("score_node", "band_node")
    builder.add_edge("band_node", "finalize")
    builder.add_edge("abort_node", "finalize")
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=checkpointer or InMemorySaver())
