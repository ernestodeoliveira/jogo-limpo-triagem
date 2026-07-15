"""End-to-end tests for the questionnaire cycle (T-08).

The graph pauses with interrupt() on each PGSI item and resumes via
Command(resume=...), per decision D-09. Payload access goes through the
canonical read_interrupt_payload helper (risk R-03).
"""

import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from langgraph.types import Command

from triagem.fakes import FakeLLM
from triagem.graph import build_agent, read_interrupt_payload
from triagem.nodes import (
    ABORT_MESSAGE,
    BAND_EXPLANATIONS,
    BAND_LABELS,
    MAX_RETRY_CYCLES,
    RETRY_HINT,
    interpret_offer_reply,
    route_after_validation,
)
from triagem.state import initial_state
from triagem.tools import (
    DISCLAIMER,
    PGSIDataError,
    load_pgsi_questions,
    load_pgsi_scale,
)

HAPPY_REPLIES = ["0", "1", "2", "3", "0", "1", "2", "3", "3"]  # PGSI score 15


def test_first_invoke_pauses_with_question_one_payload(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)

    payload = read_interrupt_payload(result)
    assert payload is not None
    assert set(payload) == {
        "kind",
        "question_id",
        "index",
        "total",
        "text",
        "scale",
        "hint",
    }
    assert payload["kind"] == "question"
    assert payload["question_id"] == "q1"
    assert payload["index"] == 0
    assert payload["total"] == 9
    assert payload["text"] == load_pgsi_questions()[0].text
    assert payload["scale"] == load_pgsi_scale()
    assert payload["hint"] is None


def test_happy_path_digits(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    seen_ids = []
    for reply in HAPPY_REPLIES:
        payload = read_interrupt_payload(result)
        assert payload is not None
        seen_ids.append(payload["question_id"])
        result = app.invoke(Command(resume=reply), config)

    assert seen_ids == [f"q{i}" for i in range(1, 10)]
    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["answers"] == {
        "q1": 0,
        "q2": 1,
        "q3": 2,
        "q4": 3,
        "q5": 0,
        "q6": 1,
        "q7": 2,
        "q8": 3,
        "q9": 3,
    }
    assert result["score"] == 15
    assert result["severity_band"] == "alto"
    assert isinstance(result["final_answer"], str) and "15" in result["final_answer"]


def test_invalid_answer_repeats_same_question(app, config):
    app.invoke(initial_state("quero começar o teste"), config)
    result = app.invoke(Command(resume="banana"), config)

    # Re-ask: the same item interrupts again instead of advancing (R-01 criteria).
    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["question_id"] == "q1"
    assert payload["hint"] == RETRY_HINT
    assert result["attempts"] == 1
    assert result["answers"] == {}


def test_attempts_reset_after_valid_answer(app, config):
    app.invoke(initial_state("quero começar o teste"), config)

    # Two invalid answers on q1: the counter accumulates.
    app.invoke(Command(resume="banana"), config)
    result = app.invoke(Command(resume="talvez"), config)
    assert result["attempts"] == 2

    # A valid answer advances to q2 and resets the counter.
    result = app.invoke(Command(resume="2"), config)
    payload = read_interrupt_payload(result)
    assert payload is not None and payload["question_id"] == "q2"
    assert result["attempts"] == 0

    # One invalid on q2 counts from zero; 2 + 1 must not reach the abort limit.
    result = app.invoke(Command(resume="sei la"), config)
    payload = read_interrupt_payload(result)
    assert payload is not None and payload["question_id"] == "q2"
    assert result["attempts"] == 1

    # The session still completes from here.
    for reply in ["0"] * 8:
        result = app.invoke(Command(resume=reply), config)
    assert read_interrupt_payload(result) is None
    assert result["score"] == 2
    assert result["severity_band"] == "baixo"


def test_abort_after_three_invalid_attempts(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in ["banana", "talvez", "nao sei dizer"]:
        result = app.invoke(Command(resume=reply), config)

    # After the 3rd invalid answer the run pauses with a retry offer, it does
    # not abort directly (Q3): the person gets a choice.
    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["kind"] == "retry_offer"
    assert payload["question_id"] == "q1"

    result = app.invoke(Command(resume="encerrar"), config)
    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["error"] == "max_invalid_attempts"
    assert result["final_answer"] == ABORT_MESSAGE
    assert result["score"] is None
    # abort_node goes straight to finalize, bypassing report_node entirely.
    assert result["report_path"] is None


def test_retry_and_abort(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in ["banana", "talvez", "nao sei dizer"]:
        result = app.invoke(Command(resume=reply), config)

    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["kind"] == "retry_offer"
    assert payload["question_id"] == "q1"

    # Retry: the same item is re-presented with attempts reset.
    result = app.invoke(Command(resume="tentar de novo"), config)
    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["kind"] == "question"
    assert payload["question_id"] == "q1"
    assert payload["hint"] is None

    # Three more invalid answers reopen the offer.
    for reply in ["banana", "talvez", "nao sei dizer"]:
        result = app.invoke(Command(resume=reply), config)
    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["kind"] == "retry_offer"
    assert payload["question_id"] == "q1"

    result = app.invoke(Command(resume="encerrar"), config)
    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["error"] == "max_invalid_attempts"
    assert result["final_answer"] == ABORT_MESSAGE
    assert result["score"] is None


def test_retry_then_valid_answer_advances(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in ["banana", "talvez", "nao sei dizer"]:
        result = app.invoke(Command(resume=reply), config)

    payload = read_interrupt_payload(result)
    assert payload is not None and payload["kind"] == "retry_offer"

    # "sim" is one of the RETRY_CHOICES, so it must count as a retry.
    result = app.invoke(Command(resume="sim"), config)
    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["kind"] == "question"
    assert payload["question_id"] == "q1"
    assert payload["hint"] is None

    result = app.invoke(Command(resume="2"), config)
    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["question_id"] == "q2"
    assert result["answers"] == {"q1": 2}

    # The session still completes normally from here.
    for reply in ["0"] * 8:
        result = app.invoke(Command(resume=reply), config)
    assert read_interrupt_payload(result) is None
    assert result["answers"]["q1"] == 2


def test_offer_unrecognized_reply_aborts(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in ["banana", "talvez", "nao sei dizer"]:
        result = app.invoke(Command(resume=reply), config)

    payload = read_interrupt_payload(result)
    assert payload is not None and payload["kind"] == "retry_offer"

    # An unrecognized reply defaults to abort (safe default, no re-offering).
    result = app.invoke(Command(resume="xyzzy"), config)
    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["error"] == "max_invalid_attempts"
    assert result["final_answer"] == ABORT_MESSAGE
    assert result["score"] is None


@pytest.mark.parametrize(
    "text",
    [
        "tentar de novo",
        "tentar novamente",
        "quero tentar de novo",
        "tentar",
        "continuar",
        "de novo",
        "novamente",
        "sim",
        "TENTAR DE NOVO",
        "  tentar de novo  ",
        "Tentar De Novo",
        # Hyphenated phrasing must still match: normalize() folds '-' to a
        # space here too (B-16 review finding: a fix scoped to parsing.py's
        # answer table must not regress this exact-match lookup).
        "tentar-novamente",
        "tentar-de-novo",
    ],
)
def test_interpret_offer_reply_recognizes_retry_choices(text):
    assert interpret_offer_reply(text) == "retry"


@pytest.mark.parametrize(
    "text",
    [
        "não",
        "nao",
        "encerrar",
        "parar",
        "xyzzy",
        "",
        # Negation trap: containment would wrongly match "tentar de novo".
        "não quero tentar de novo",
    ],
)
def test_interpret_offer_reply_defaults_to_abort(text):
    assert interpret_offer_reply(text) == "abort"


def test_crisis_mid_questionnaire(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    result = app.invoke(Command(resume="0"), config)
    result = app.invoke(Command(resume="1"), config)
    result = app.invoke(Command(resume="não aguento mais, quero morrer"), config)

    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["crisis_flag"] is True
    assert result["phase"] == "crise"
    assert "188" in result["final_answer"]
    assert "192" in result["final_answer"]
    assert result["score"] is None
    assert result["answers"] == {"q1": 0, "q2": 1}
    assert result["attempts"] == 0
    # crisis_node goes straight to finalize, bypassing report_node entirely.
    assert result["report_path"] is None


def test_crisis_at_retry_offer(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in ["banana", "talvez", "nao sei dizer"]:
        result = app.invoke(Command(resume=reply), config)

    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["kind"] == "retry_offer"

    # Crisis wins outright over the retry-offer flow (D-04): same outcome as
    # a fresh-message crisis, not the abort path an unrecognized reply would
    # otherwise take.
    result = app.invoke(Command(resume="quero me matar"), config)
    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["error"] is None
    assert result["crisis_flag"] is True
    assert "188" in result["final_answer"]
    assert "192" in result["final_answer"]


def test_crisis_at_attempts_boundary_wins_over_retry_offer(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in ["banana", "talvez"]:
        result = app.invoke(Command(resume=reply), config)

    payload = read_interrupt_payload(result)
    assert payload is not None and payload["kind"] == "question"
    assert result["attempts"] == 2

    # The 3rd reply would otherwise hit MAX_ATTEMPTS and route to
    # retry_offer, but it is itself a crisis phrase: the crisis check in
    # validate_answer_node runs before the parser/attempts increment, so it
    # must short-circuit straight to crisis_node instead (D-04).
    result = app.invoke(Command(resume="não aguento mais, quero morrer"), config)
    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["crisis_flag"] is True
    assert result["phase"] == "crise"
    assert "188" in result["final_answer"]
    assert "192" in result["final_answer"]
    assert result["attempts"] == 2
    assert result["error"] is None


def test_full_triage(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in HAPPY_REPLIES:
        result = app.invoke(Command(resume=reply), config)

    assert result["score"] == 15
    assert result["severity_band"] == "alto"
    assert result["phase"] == "resultado"

    report_path = result["report_path"]
    assert report_path is not None
    assert config["configurable"]["thread_id"] in Path(report_path).name

    final = result["final_answer"]
    assert "risco alto" in final
    assert "15" in final
    assert BAND_EXPLANATIONS["alto"] in final
    assert DISCLAIMER in final
    assert report_path in final
    assert "188" in final and "gov.br" in final and "CAPS" in final

    md = Path(report_path)
    assert md.exists() and md.suffix == ".md"
    content = md.read_text(encoding="utf-8")
    for i in range(1, 10):
        assert f"q{i}" in content
    assert "alto" in content

    data = json.loads(md.with_suffix(".json").read_text(encoding="utf-8"))
    assert data["score"] == 15
    assert data["answers"]["q9"] == 3


class CountingLLM:
    """Wraps FakeLLM and records the schema name of every LLM invocation.

    Distinguishes IntentResult (one call at session start, D-09) from
    AnswerValue (the parser fallback), so tests can assert the fallback was
    never reached without a production-code call counter (A-03/O-02).
    """

    def __init__(self):
        self.schema_calls = []
        self._inner = FakeLLM()

    def with_structured_output(self, schema, **kwargs):
        runnable = self._inner.with_structured_output(schema, **kwargs)
        calls = self.schema_calls
        name = getattr(schema, "__name__", repr(schema))

        class _Counting:
            def invoke(self, input, config=None):
                calls.append(name)
                return runnable.invoke(input, config=config)

        return _Counting()


def test_overlong_answer_counts_attempt_without_llm_call():
    llm = CountingLLM()
    app = build_agent(llm)
    config = {"configurable": {"thread_id": uuid4().hex}}

    result = app.invoke(initial_state("quero começar o teste"), config)
    baseline = list(llm.schema_calls)

    result = app.invoke(Command(resume="x" * 301), config)

    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["question_id"] == "q1"
    assert payload["hint"] == RETRY_HINT
    assert result["attempts"] == 1
    assert llm.schema_calls == baseline


def test_answer_at_length_limit_still_reaches_parser():
    llm = CountingLLM()
    app = build_agent(llm)
    config = {"configurable": {"thread_id": uuid4().hex}}

    app.invoke(initial_state("quero começar o teste"), config)
    app.invoke(Command(resume="y" * 300), config)

    assert llm.schema_calls.count("AnswerValue") == 1


def test_overlong_crisis_message_still_wins(app, config):
    app.invoke(initial_state("quero começar o teste"), config)
    result = app.invoke(Command(resume="quero morrer " + "x" * 400), config)

    assert result["crisis_flag"] is True
    assert "188" in result["final_answer"]


def test_route_after_validation_aborts_when_retry_cycles_exhausted():
    exhausted_state = {
        **initial_state("x"),
        "attempts": 3,
        "retry_cycles": MAX_RETRY_CYCLES,
    }
    assert route_after_validation(exhausted_state) == "abort_node"

    not_yet_state = {
        **initial_state("x"),
        "attempts": 3,
        "retry_cycles": MAX_RETRY_CYCLES - 1,
    }
    assert route_after_validation(not_yet_state) == "retry_offer"


def test_sixth_retry_cycle_aborts_politely(app, config):
    result = app.invoke(initial_state("quero começar o teste"), config)

    for cycle in range(MAX_RETRY_CYCLES):
        for reply in ["banana", "talvez", "nao sei dizer"]:
            result = app.invoke(Command(resume=reply), config)
        payload = read_interrupt_payload(result)
        assert payload is not None and payload["kind"] == "retry_offer"

        result = app.invoke(Command(resume="tentar de novo"), config)
        assert result["retry_cycles"] == cycle + 1
        payload = read_interrupt_payload(result)
        assert payload is not None and payload["kind"] == "question"

    for reply in ["banana", "talvez", "nao sei dizer"]:
        result = app.invoke(Command(resume=reply), config)

    assert read_interrupt_payload(result) is None
    assert "__interrupt__" not in result
    assert result["final_answer"] == ABORT_MESSAGE
    assert result["error"] == "max_invalid_attempts"
    assert result["score"] is None


@pytest.mark.parametrize(
    ("answers", "expected_band", "expected_score"),
    [
        (["0"] * 9, "sem_risco", 0),
        (["0"] * 8 + ["1"], "baixo", 1),
        (["1"] * 5 + ["0"] * 4, "moderado", 5),
        # Score 10, distinct from HAPPY_REPLIES' score of 15 (already covered
        # by test_full_triage above): still inside the 8-27 "alto" range.
        (["2"] * 5 + ["0"] * 4, "alto", 10),
    ],
)
def test_final_answer_matches_band(app, config, answers, expected_band, expected_score):
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in answers:
        payload = read_interrupt_payload(result)
        assert payload is not None
        result = app.invoke(Command(resume=reply), config)

    assert read_interrupt_payload(result) is None
    assert result["score"] == expected_score
    assert result["severity_band"] == expected_band
    assert BAND_LABELS[expected_band] in result["final_answer"]
    assert BAND_EXPLANATIONS[expected_band] in result["final_answer"]


@pytest.mark.parametrize(
    ("payload", "expected_value", "expected_attempts"),
    [
        (2, 2, 0),
        ({"unexpected": "shape"}, None, 1),
        ([1, 2, 3], None, 1),
    ],
)
def test_resume_with_non_string_payloads(
    app, config, payload, expected_value, expected_attempts
):
    app.invoke(initial_state("quero começar o teste"), config)
    result = app.invoke(Command(resume=payload), config)

    if expected_value is None:
        # nodes.py coerces any non-string resume payload with str() (F-04);
        # neither of these stringify to a table entry, so each counts as an
        # invalid attempt on the same question rather than crashing.
        current = read_interrupt_payload(result)
        assert current is not None
        assert current["question_id"] == "q1"
        assert result["attempts"] == expected_attempts
    else:
        # An int payload is the one non-string case that stringifies into a
        # valid table entry ("2" -> 2), so it is silently accepted (F-04).
        assert result["answers"]["q1"] == expected_value
        assert result["attempts"] == expected_attempts


def test_resume_with_none_payload_crashes_before_reaching_nodes(app, config):
    # Correction to the original hypothesis behind this test (F-04): a
    # None resume payload was expected to be str()-coerced by ask_question
    # just like the int/dict/list cases above, ending in a normal invalid
    # attempt. In reality, Command(resume=None) never reaches nodes.py at
    # all. langgraph's own SyncPregelLoop._first (pregel/_loop.py) treats a
    # resume value of None as "no resume was provided" (the same sentinel
    # meaning as app.invoke(None, config)): the branch that would set its
    # internal resume_is_map flag is skipped, but a few lines later that
    # flag is read unconditionally, raising UnboundLocalError from inside
    # langgraph itself. So unlike the other three non-string payloads, None
    # is not a graceful invalid-attempt case: it is an unhandled crash at
    # the graph-runtime layer, a stronger version of F-04 than originally
    # described.
    app.invoke(initial_state("quero começar o teste"), config)
    with pytest.raises(UnboundLocalError):
        app.invoke(Command(resume=None), config)


def test_resume_on_finished_thread_is_noop(app, config):
    # F-05: against langgraph 1.2.9 (pin in pyproject.toml) + InMemorySaver,
    # resuming a thread that already reached finalize is a silent no-op. The
    # checkpoint for a finished thread has no pending task, so invoke() just
    # returns the last saved values again, with no __interrupt__ and without
    # rerunning report_node (no new report file is written to disk).
    result = app.invoke(initial_state("quero começar o teste"), config)
    for reply in HAPPY_REPLIES:
        result = app.invoke(Command(resume=reply), config)

    assert read_interrupt_payload(result) is None
    assert result["score"] == 15
    assert result["report_path"] is not None

    reports_dir = Path(os.environ["TRIAGE_REPORTS_DIR"])
    files_before = sorted(reports_dir.glob("*"))

    resumed = app.invoke(Command(resume="algo"), config)

    assert read_interrupt_payload(resumed) is None
    assert "__interrupt__" not in resumed
    assert resumed["score"] == result["score"]
    assert resumed["severity_band"] == result["severity_band"]
    assert resumed["final_answer"] == result["final_answer"]
    assert resumed["report_path"] == result["report_path"]

    # No report_node run means no new file: same set of paths as before.
    files_after = sorted(reports_dir.glob("*"))
    assert files_after == files_before


def test_resume_on_unknown_thread_raises_keyerror(app, config):
    # F-05: resuming a thread_id that was never invoked before (config here
    # is freshly generated by the fixture and initial_state() was never sent
    # through it) has no checkpoint at all. Against langgraph 1.2.9 (pin in
    # pyproject.toml) + InMemorySaver, this starts a brand new run from START
    # with an empty state instead of failing outright. safety_gate is the
    # first node in the graph (graph.py) and reads state["user_input"]
    # (safety.py), a field only ever set by initial_state(...), so it raises
    # KeyError. A future langgraph upgrade could change this behavior;
    # re-confirm empirically if this test ever starts failing differently.
    with pytest.raises(KeyError, match="user_input"):
        app.invoke(Command(resume="0"), config)

    # The crash happens mid-step, so it leaves a partial checkpoint pending
    # right before the node that raised, instead of cleaning up after itself.
    state = app.get_state(config)
    assert state.next == ("safety_gate",)


def test_combining_character_grapheme_exceeds_length_limit():
    llm = CountingLLM()
    app = build_agent(llm)
    config = {"configurable": {"thread_id": uuid4().hex}}

    app.invoke(initial_state("quero começar o teste"), config)
    baseline = list(llm.schema_calls)

    # 300 graphemes of base "a" + a combining acute accent (U+0301) is 600
    # Unicode code points: MAX_ANSWER_LENGTH counts code points via len(),
    # not visual graphemes, so this is rejected even though it "looks" like
    # 300 characters (F-13).
    combining_answer = ("a" + "́") * 300
    assert len(combining_answer) == 600

    result = app.invoke(Command(resume=combining_answer), config)

    payload = read_interrupt_payload(result)
    assert payload is not None
    assert payload["question_id"] == "q1"
    assert result["attempts"] == 1
    assert llm.schema_calls == baseline


def test_single_code_point_emoji_at_length_limit_reaches_parser():
    llm = CountingLLM()
    app = build_agent(llm)
    config = {"configurable": {"thread_id": uuid4().hex}}

    app.invoke(initial_state("quero começar o teste"), config)

    # 300 single-code-point emoji: len() == 300, at the limit but not over
    # it, so (unlike the combining-character grapheme case) this still
    # reaches the LLM fallback (F-13) even though it is visually "longer".
    emoji_answer = "😊" * 300
    assert len(emoji_answer) == 300

    app.invoke(Command(resume=emoji_answer), config)

    assert llm.schema_calls.count("AnswerValue") == 1


def test_pgsi_corruption_mid_session_raises_pgsi_error(
    app, config, tmp_path, monkeypatch
):
    # Corrupting pgsi.json mid-session must raise PGSIDataError.
    #
    # ask_question is idempotent by design (D-09/R-02): on every resume it
    # re-runs from the start and re-reads data/pgsi.json from scratch
    # (load_pgsi_questions and load_pgsi_scale are called with no argument,
    # path relative to the process cwd, not to nodes.py's file location).
    # This test copies the repo's real pgsi.json into tmp_path/data/, points
    # the process cwd there via chdir, advances the session while the file
    # is still intact, corrupts the file, and only then resumes again: the
    # re-read on the following resume must propagate the error instead of
    # using a stale in-memory state. There is no monkeypatch of the loader;
    # the file read is real, via chdir.
    real_pgsi_path = Path(__file__).resolve().parents[1] / "data" / "pgsi.json"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pgsi_copy = data_dir / "pgsi.json"
    shutil.copy(real_pgsi_path, pgsi_copy)

    monkeypatch.chdir(tmp_path)

    result = app.invoke(initial_state("quero começar o teste"), config)
    payload = read_interrupt_payload(result)
    assert payload is not None and payload["question_id"] == "q1"

    # Valid answer for q1: the same invoke already re-runs ask_question to
    # build the q2 payload, re-reading the file while it is still valid.
    result = app.invoke(Command(resume="0"), config)
    payload = read_interrupt_payload(result)
    assert payload is not None and payload["question_id"] == "q2"

    # Corrupt the file now, between the two resumes.
    pgsi_copy.write_text("{ isto não é um json válido", encoding="utf-8")

    # The next resume re-runs ask_question from the start and re-reads the
    # file, now corrupted: PGSIDataError must propagate instead of being
    # swallowed.
    with pytest.raises(PGSIDataError):
        app.invoke(Command(resume="0"), config)


def test_fresh_agent_instance_does_not_share_state(config):
    # Two build_agent() instances with the same thread_id share no
    # checkpoint at all between them (documented limitation, README section
    # 10: "InMemorySaver does not persist across processes").
    #
    # build_agent() creates a new InMemorySaver on every call (graph.py):
    # the thread_id only identifies a session within the same graph object,
    # not across different instances. This test advances a session in the
    # first agent up to q2 and shows that a second agent, with the same
    # thread_id, starts from scratch at q1, with no trace of the prior
    # progress.
    agent_one = build_agent(FakeLLM())
    agent_two = build_agent(FakeLLM())

    result = agent_one.invoke(initial_state("quero começar o teste"), config)
    payload = read_interrupt_payload(result)
    assert payload is not None and payload["question_id"] == "q1"

    result = agent_one.invoke(Command(resume="0"), config)
    payload = read_interrupt_payload(result)
    assert payload is not None and payload["question_id"] == "q2"
    assert result["answers"] == {"q1": 0}

    # Direct proof: agent_two's checkpointer has no record at all for this
    # thread_id, even with all the progress already saved in agent_one. An
    # empty StateSnapshot is only possible because each build_agent() creates
    # its own InMemorySaver (graph.py); if the checkpoint were shared,
    # get_state here would return the values already advanced by agent_one.
    assert agent_two.get_state(config).values == {}

    # Same thread_id, but a new graph instance: pauses at q1 again, with no
    # visibility at all into the progress made in agent_one.
    fresh_result = agent_two.invoke(initial_state("quero começar o teste"), config)
    fresh_payload = read_interrupt_payload(fresh_result)
    assert fresh_payload is not None
    assert fresh_payload["question_id"] == "q1"
    # answers uses Annotated[dict, operator.or_] (state.py): if the
    # checkpoint were truly shared, this merge would preserve {"q1": 0} here
    # even after a "from scratch" invoke. Coming back empty closes the proof
    # that there is nothing to merge, not just that the question index
    # reset.
    assert fresh_result["answers"] == {}
