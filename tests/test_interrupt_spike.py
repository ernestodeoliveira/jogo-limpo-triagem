"""T-07 spike: validate the interrupt()/Command(resume=...) cycle on langgraph 1.2.x.

This spike is the committed evidence behind decision D-09 (option A of
ARCHITECTURE section 4). It uses a minimal dedicated graph, not the triage
graph, and pins down as assertions:

- the shape of result["__interrupt__"] (sequence of Interrupt with .value/.id);
- two full pause/resume cycles driven by Command(resume=...);
- node re-execution from the top on resume (risk R-02): side effects placed
  before interrupt() run twice per question, while state writes do not, which
  is why the real ask_question must stay pure before its interrupt() call;
- thread_id isolation on the same compiled app.

The read_interrupt_payload helper is kept local on purpose: this PR does not
touch src/. The canonical helper lands in triagem.graph with T-08 (risk R-03).
"""

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

TOTAL_QUESTIONS = 2


class SpikeState(TypedDict):
    answers: Annotated[list[str], operator.add]


def build_spike_app(executions: list[int]):
    """Compile a two-question loop that pauses with interrupt() on each item."""

    def ask(state: SpikeState) -> dict:
        index = len(state["answers"])
        # Deliberate side effect BEFORE interrupt() to probe re-execution (R-02).
        executions.append(index)
        reply = interrupt({"index": index, "prompt": f"question {index}"})
        return {"answers": [f"{index}:{reply}"]}

    def route(state: SpikeState) -> str:
        return "ask" if len(state["answers"]) < TOTAL_QUESTIONS else END

    builder = StateGraph(SpikeState)
    builder.add_node("ask", ask)
    builder.add_edge(START, "ask")
    builder.add_conditional_edges("ask", route, {"ask": "ask", END: END})
    return builder.compile(checkpointer=InMemorySaver())


def read_interrupt_payload(result: dict) -> dict | None:
    """Local copy of the single access point to the pending interrupt payload."""
    pending = result.get("__interrupt__") or ()
    return pending[0].value if pending else None


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def test_invoke_surfaces_interrupt_with_value_and_id():
    app = build_spike_app(executions=[])

    result = app.invoke({"answers": []}, _config("t-shape"))

    assert "__interrupt__" in result
    pending = result["__interrupt__"]
    # Accept list or tuple so a container change in a patch release (R-03)
    # fails louder in the type assert below than in a subscript error.
    assert isinstance(pending, (list, tuple))
    assert len(pending) == 1
    first = pending[0]
    assert first.value == {"index": 0, "prompt": "question 0"}
    assert isinstance(first.id, str) and first.id


def test_two_pause_resume_cycles_complete():
    app = build_spike_app(executions=[])
    cfg = _config("t-cycles")

    result = app.invoke({"answers": []}, cfg)
    assert read_interrupt_payload(result) == {"index": 0, "prompt": "question 0"}

    result = app.invoke(Command(resume="a"), cfg)
    assert read_interrupt_payload(result) == {"index": 1, "prompt": "question 1"}

    result = app.invoke(Command(resume="b"), cfg)
    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result == {"answers": ["0:a", "1:b"]}


def test_node_reexecutes_from_start_on_resume():
    executions: list[int] = []
    app = build_spike_app(executions)
    cfg = _config("t-reexec")

    app.invoke({"answers": []}, cfg)
    assert executions == [0]

    app.invoke(Command(resume="a"), cfg)
    # The paused node re-ran from its start (0 again), then the next visit
    # paused at question 1: pre-interrupt side effects DO duplicate.
    assert executions == [0, 0, 1]

    result = app.invoke(Command(resume="b"), cfg)
    assert executions == [0, 0, 1, 1]
    # State writes do not duplicate: only the completed execution returns.
    assert result["answers"] == ["0:a", "1:b"]


def test_separate_thread_ids_are_isolated():
    app = build_spike_app(executions=[])
    cfg_one = _config("t-one")
    cfg_two = _config("t-two")

    result_one = app.invoke({"answers": []}, cfg_one)
    result_one = app.invoke(Command(resume="a"), cfg_one)
    assert read_interrupt_payload(result_one) == {"index": 1, "prompt": "question 1"}

    # A fresh thread on the same compiled app starts at question 0.
    result_two = app.invoke({"answers": []}, cfg_two)
    assert read_interrupt_payload(result_two) == {"index": 0, "prompt": "question 0"}

    # The first thread still resumes from its own pending question.
    result_one = app.invoke(Command(resume="b"), cfg_one)
    assert result_one["answers"] == ["0:a", "1:b"]
