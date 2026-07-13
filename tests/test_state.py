import operator
from typing import get_type_hints

from triagem.state import TriageState, initial_state


def test_initial_state_defaults():
    state = initial_state("quero fazer o teste")
    assert state["user_input"] == "quero fazer o teste"
    assert state["intent"] is None
    assert state["phase"] is None
    assert state["current_question"] == 0
    assert state["attempts"] == 0
    assert state["retry_cycles"] == 0
    assert state["answers"] == {}
    assert state["crisis_flag"] is False
    assert state["score"] is None
    assert state["severity_band"] is None
    assert state["report_path"] is None
    assert state["final_answer"] is None
    assert state["error"] is None


def test_answers_reducer_merges_without_losing_accumulated():
    hints = get_type_hints(TriageState, include_extras=True)
    reducer = hints["answers"].__metadata__[0]
    assert reducer is operator.or_
    assert reducer({"q1": 2}, {"q2": 0}) == {"q1": 2, "q2": 0}
    assert reducer({"q1": 2}, {"q1": 3}) == {"q1": 3}
