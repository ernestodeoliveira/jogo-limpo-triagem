import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "pgsi.json"


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
