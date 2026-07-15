"""Tests for the interactive CLI session (T-17)."""

import os

from triagem.cli import main, render_offer, render_payload, render_question
from triagem.graph import build_agent

HAPPY_REPLIES = ["0", "1", "2", "3", "0", "1", "2", "3", "3"]  # PGSI score 15


def _question_payload(hint=None):
    return {
        "kind": "question",
        "question_id": "q1",
        "index": 0,
        "total": 9,
        "text": "Você apostou mais do que podia perder?",
        "scale": {
            "0": "Nunca",
            "1": "Às vezes",
            "2": "Na maioria das vezes",
            "3": "Quase sempre",
        },
        "hint": hint,
    }


def _offer_payload():
    return {
        "kind": "retry_offer",
        "question_id": "q1",
        "index": 0,
        "total": 9,
        "text": "Você quer tentar essa pergunta de novo ou prefere encerrar por aqui?",
    }


def test_render_question_without_hint():
    payload = _question_payload(hint=None)
    output = render_question(payload)
    assert payload["hint"] is None
    assert "Pergunta 1 de 9" in output
    assert payload["text"] in output
    assert "0 = Nunca" in output
    assert "1 = Às vezes" in output
    assert "2 = Na maioria das vezes" in output
    assert "3 = Quase sempre" in output


def test_render_question_with_hint():
    hint = "Não consegui entender sua resposta."
    payload = _question_payload(hint=hint)
    output = render_question(payload)
    assert hint in output
    assert "Pergunta 1 de 9" in output


def test_render_offer():
    payload = _offer_payload()
    output = render_offer(payload)
    assert output == payload["text"]


def test_render_payload_dispatches_by_kind():
    question_payload = _question_payload()
    offer_payload = _offer_payload()
    assert render_payload(question_payload) == render_question(question_payload)
    assert render_payload(offer_payload) == render_offer(offer_payload)


def test_main_happy_path_prints_final_answer_and_report(monkeypatch, capsys):
    replies = iter(["quero começar o teste", *HAPPY_REPLIES])
    monkeypatch.setattr("builtins.input", lambda *a: next(replies))

    exit_code = main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Relatório gravado em" in captured.out


def test_main_eof_exits_cleanly(monkeypatch, capsys):
    def raise_eof(*args):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)

    exit_code = main()

    captured = capsys.readouterr()
    assert exit_code == 0
    from triagem.cli import GOODBYE

    assert GOODBYE in captured.out


def test_main_keyboard_interrupt_prints_goodbye(monkeypatch, capsys):
    def raise_keyboard_interrupt(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", raise_keyboard_interrupt)

    exit_code = main()

    captured = capsys.readouterr()
    assert exit_code == 0
    from triagem.cli import GOODBYE

    assert GOODBYE in captured.out


def test_main_config_error_returns_2(monkeypatch, capsys):
    """When TRIAGE_FAKE_LLM is unset and the real-LLM endpoint envs are
    absent, get_llm() raises RuntimeError before build_agent() finishes;
    main() must report a config error and exit 2 without any network call.
    """
    monkeypatch.delenv("TRIAGE_FAKE_LLM", raising=False)

    exit_code = main()

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Erro de configuração" in captured.out


def test_main_unexpected_exception_is_caught_gracefully(monkeypatch, capsys):
    """A raw runtime failure inside app.invoke() (e.g. PermissionError from
    report_node when TRIAGE_REPORTS_DIR is not writable) must not leak a
    traceback to the terminal; main() should degrade gracefully instead.
    """

    class ExplodingApp:
        def invoke(self, *args, **kwargs):
            raise PermissionError("disk full")

    monkeypatch.setattr("triagem.cli.build_agent", lambda: ExplodingApp())
    monkeypatch.setattr("builtins.input", lambda *a: "quero começar o teste")

    exit_code = main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Erro inesperado" in captured.out


class ExplodingClassifierLLM:
    """Local double whose with_structured_output always returns a runnable
    that raises on invoke, regardless of schema. It stands in for a chat
    model whose first structured call (classify_intent_node, F-10) fails at
    runtime, after the graph has already been built successfully.
    """

    def with_structured_output(self, schema):
        class _Runnable:
            def invoke(self, messages):
                raise ValueError("classifier exploded")

        return _Runnable()


def test_main_classifier_error_reaches_generic_handler(monkeypatch, capsys):
    """An exception raised inside classify_intent_node (no try/except of its
    own) must propagate up to main()'s generic Exception handler (exit 1),
    the same way any other unguarded node failure would (F-10).
    """
    monkeypatch.setattr(
        "triagem.cli.build_agent", lambda: build_agent(ExplodingClassifierLLM())
    )
    monkeypatch.setattr("builtins.input", lambda *a: "quero começar o teste")

    exit_code = main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Erro inesperado" in captured.out


ALL_TRACING_ENV_VARS = (
    "LANGSMITH_TRACING",
    "LANGCHAIN_TRACING_V2",
    "LANGSMITH_TRACING_V2",
    "LANGCHAIN_TRACING",
)


def test_main_disables_tracing_env_by_default(monkeypatch):
    monkeypatch.delenv("TRIAGE_ALLOW_TRACING", raising=False)
    for var in ALL_TRACING_ENV_VARS:
        monkeypatch.setenv(var, "true")

    def raise_eof(*args):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)

    exit_code = main()

    assert exit_code == 0
    for var in ALL_TRACING_ENV_VARS:
        assert os.environ[var] == "false"


def test_main_keeps_tracing_env_on_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("TRIAGE_ALLOW_TRACING", "1")
    for var in ALL_TRACING_ENV_VARS:
        monkeypatch.setenv(var, "true")

    def raise_eof(*args):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)

    exit_code = main()

    assert exit_code == 0
    for var in ALL_TRACING_ENV_VARS:
        assert os.environ[var] == "true"
