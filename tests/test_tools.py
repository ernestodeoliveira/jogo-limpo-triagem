import json
from pathlib import Path

import pytest

from triagem.tools import (
    PGSIDataError,
    Question,
    load_pgsi_questions,
    load_pgsi_scale,
)

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "pgsi.json"


def _write(tmp_path, payload: str) -> str:
    file = tmp_path / "pgsi.json"
    file.write_text(payload, encoding="utf-8")
    return str(file)


def test_pgsi_data_file_valid():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    assert data["instrument"] == "PGSI"
    assert data["title_pt"] == "Índice de gravidade de problemas com apostas"
    assert data["stem"] == "Pensando nos últimos 12 meses..."
    assert data["scale"] == {
        "0": "Nunca",
        "1": "Às vezes",
        "2": "Na maioria das vezes",
        "3": "Quase sempre",
    }
    assert "10.11606/s1518-8787.2026060007368" in data["source"]
    items = data["items"]
    assert len(items) == 9
    assert [item["id"] for item in items] == [f"q{i}" for i in range(1, 10)]
    assert all(item["text"].strip() for item in items)


def test_load_valid_items():
    questions = load_pgsi_questions(str(DATA_PATH))
    assert len(questions) == 9
    assert [q.id for q in questions] == [f"q{i}" for i in range(1, 10)]
    assert all(isinstance(q, Question) and q.text.strip() for q in questions)


def test_missing_item_raises(tmp_path):
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    data["items"] = data["items"][:8]
    with pytest.raises(PGSIDataError, match="exactly 9 items"):
        load_pgsi_questions(_write(tmp_path, json.dumps(data)))


def test_empty_text_raises(tmp_path):
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    data["items"][4]["text"] = "   "
    with pytest.raises(PGSIDataError, match="empty or missing text"):
        load_pgsi_questions(_write(tmp_path, json.dumps(data)))


def test_wrong_item_id_raises(tmp_path):
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    data["items"][0]["id"] = "x1"
    with pytest.raises(PGSIDataError, match="expected item 'q1'"):
        load_pgsi_questions(_write(tmp_path, json.dumps(data)))


def test_invalid_json_raises(tmp_path):
    with pytest.raises(PGSIDataError, match="not valid JSON"):
        load_pgsi_questions(_write(tmp_path, "{ not json"))


def test_missing_file_raises(tmp_path):
    with pytest.raises(PGSIDataError, match="not found"):
        load_pgsi_questions(str(tmp_path / "absent.json"))


def test_load_scale_valid():
    scale = load_pgsi_scale(str(DATA_PATH))
    assert scale == {
        "0": "Nunca",
        "1": "Às vezes",
        "2": "Na maioria das vezes",
        "3": "Quase sempre",
    }


def test_load_scale_missing_key_raises(tmp_path):
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    del data["scale"]["3"]
    with pytest.raises(PGSIDataError, match="keys 0..3"):
        load_pgsi_scale(_write(tmp_path, json.dumps(data)))


def test_load_scale_empty_label_raises(tmp_path):
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    data["scale"]["2"] = "  "
    with pytest.raises(PGSIDataError, match="empty or missing label"):
        load_pgsi_scale(_write(tmp_path, json.dumps(data)))


def test_load_scale_missing_file_raises(tmp_path):
    with pytest.raises(PGSIDataError, match="not found"):
        load_pgsi_scale(str(tmp_path / "absent.json"))


def test_pgsi_items_match_validated_text_verbatim():
    questions = load_pgsi_questions(str(DATA_PATH))
    scale = load_pgsi_scale(str(DATA_PATH))

    expected_texts = {
        "q1": "Você apostou mais do que realmente poderia perder?",
        "q2": (
            "Ainda pensando nos últimos 12 meses, você precisou apostar "
            "quantias cada vez maiores de dinheiro para ter a mesma sensação "
            "de prazer?"
        ),
        "q3": (
            "Depois de ter apostado, você retorna outro dia para tentar "
            "recuperar o dinheiro perdido?"
        ),
        "q4": (
            "Você pediu dinheiro emprestado ou vendeu alguma coisa para "
            "conseguir dinheiro para apostar?"
        ),
        "q5": "Você achou que poderia ter algum problema com apostas?",
        "q6": (
            "Apostar já lhe causou algum problema de saúde, como estresse ou ansiedade?"
        ),
        "q7": (
            "As pessoas já lhe criticaram por apostar, ou disseram que você "
            "tinha problemas com apostar, independentemente de você achar que "
            "era verdade ou não?"
        ),
        "q8": (
            "As suas apostas já causaram algum problema financeiro para você "
            "ou sua família?"
        ),
        "q9": (
            "Você já se sentiu culpado(a) pela maneira como você aposta ou "
            "pelo que acontece quando você aposta?"
        ),
    }

    actual_texts = {question.id: question.text for question in questions}
    assert actual_texts == expected_texts

    assert scale == {
        "0": "Nunca",
        "1": "Às vezes",
        "2": "Na maioria das vezes",
        "3": "Quase sempre",
    }
