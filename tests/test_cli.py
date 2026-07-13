"""Tests for the interactive CLI session (T-17)."""

from triagem.cli import main, render_offer, render_payload, render_question

HAPPY_REPLIES = ["0", "1", "2", "3", "0", "1", "2", "3", "3"]  # PGSI score 15


def _question_payload(hint=None):
    return {
        "kind": "question",
        "question_id": "q1",
        "index": 0,
        "total": 9,
        "text": "Você apostou mais do que podia perder?",
        "scale": {"0": "Nunca", "1": "Às vezes", "2": "Na maioria das vezes", "3": "Quase sempre"},
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
