"""Graph assembly for the PGSI triage agent."""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from triagem.classify import make_classify_intent_node, route_intent
from triagem.fakes import get_llm
from triagem.nodes import (
    OfferPayload,
    QuestionPayload,
    abort_node,
    ask_question,
    band_node,
    fallback_node,
    finalize_node,
    info_node,
    make_validate_answer_node,
    retry_offer_node,
    route_after_offer,
    route_after_validation,
    score_node,
)
from triagem.safety import crisis_node, route_safety, safety_gate_node
from triagem.state import TriageState, initial_state

__all__ = ["build_agent", "initial_state", "read_interrupt_payload"]


def read_interrupt_payload(result: dict) -> QuestionPayload | OfferPayload | None:
    """Single access point for the pending interrupt payload (risk R-03).

    Returns the .value of the pending Interrupt, or None when the run
    completed. Reused by the tests now and by cli.py later (T-17). Every
    interrupt in this graph carries either a QuestionPayload or an
    OfferPayload.
    """
    pending = result.get("__interrupt__") or ()
    return pending[0].value if pending else None


def build_agent(llm=None, checkpointer=None):
    """Compile the triage graph with a checkpointer (required by interrupt, D-09).

    When llm is None the factory get_llm() resolves it from the environment
    (FakeLLM under TRIAGE_FAKE_LLM=1).
    """
    llm = llm if llm is not None else get_llm()
    builder = StateGraph(TriageState)
    builder.add_node("safety_gate", safety_gate_node)
    builder.add_node("crisis_node", crisis_node)
    builder.add_node("classify_intent", make_classify_intent_node(llm))
    builder.add_node("info_node", info_node)
    builder.add_node("fallback_node", fallback_node)
    builder.add_node("ask_question", ask_question)
    builder.add_node("validate_answer", make_validate_answer_node(llm))
    builder.add_node("retry_offer", retry_offer_node)
    builder.add_node("abort_node", abort_node)
    builder.add_node("score_node", score_node)
    builder.add_node("band_node", band_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "safety_gate")
    builder.add_conditional_edges(
        "safety_gate",
        route_safety,
        {"ok": "classify_intent", "crisis_node": "crisis_node"},
    )
    builder.add_conditional_edges(
        "classify_intent",
        route_intent,
        {
            "ask_question": "ask_question",
            "info_node": "info_node",
            "fallback_node": "fallback_node",
        },
    )
    builder.add_edge("info_node", "finalize")
    builder.add_edge("fallback_node", "finalize")
    builder.add_edge("ask_question", "validate_answer")
    builder.add_conditional_edges(
        "validate_answer",
        route_after_validation,
        {
            "ask_question": "ask_question",
            "retry_offer": "retry_offer",
            "score_node": "score_node",
            "crisis_node": "crisis_node",
        },
    )
    builder.add_conditional_edges(
        "retry_offer",
        route_after_offer,
        {
            "ask_question": "ask_question",
            "abort_node": "abort_node",
            "crisis_node": "crisis_node",
        },
    )
    builder.add_edge("score_node", "band_node")
    builder.add_edge("band_node", "finalize")
    builder.add_edge("abort_node", "finalize")
    builder.add_edge("crisis_node", "finalize")
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=checkpointer or InMemorySaver())
