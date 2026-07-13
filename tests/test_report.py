import json
from pathlib import Path

import pytest

from triagem.nodes import report_node
from triagem.state import initial_state
from triagem.tools import (
    TriageOutcome,
    _sanitize_thread_id,
    write_triage_report,
)


def _make_outcome(**overrides) -> TriageOutcome:
    answers = {f"q{i}": 1 for i in range(1, 10)}
    answers["q1"] = 3
    answers["q2"] = 2
    defaults = dict(
        thread_id="thread-abc123",
        timestamp="2026-07-12T20:10:33",
        score=15,
        severity_band="alto",
        answers=answers,
    )
    defaults.update(overrides)
    return TriageOutcome(**defaults)


def test_writes_md_and_json_and_returns_md_path(tmp_path):
    outcome = _make_outcome()
    md_path = write_triage_report(outcome, out_dir=str(tmp_path))

    assert md_path.endswith(".md")
    md_file = Path(md_path)
    json_file = md_file.with_suffix(".json")
    assert md_file.is_file()
    assert json_file.is_file()
    assert md_file.parent == tmp_path


def test_md_contains_answers_band_and_referrals(tmp_path):
    outcome = _make_outcome()
    md_path = write_triage_report(outcome, out_dir=str(tmp_path))
    content = Path(md_path).read_text(encoding="utf-8")

    for item_id, value in outcome.answers.items():
        assert f"{item_id}: {value}" in content
    assert "alto" in content
    assert "15" in content
    assert "188" in content
    assert "gov.br" in content
    assert "CAPS" in content
    assert outcome.disclaimer in content


def test_json_contains_calculation_inputs(tmp_path):
    outcome = _make_outcome()
    md_path = write_triage_report(outcome, out_dir=str(tmp_path))
    json_path = Path(md_path).with_suffix(".json")
    data = json.loads(json_path.read_text(encoding="utf-8"))

    assert data["score"] == 15
    assert data["answers"] == outcome.answers
    assert data["thread_id"] == outcome.thread_id
    assert data["timestamp"] == outcome.timestamp
    assert data["severity_band"] == "alto"


def test_refuses_overwrite(tmp_path):
    outcome = _make_outcome()
    write_triage_report(outcome, out_dir=str(tmp_path))

    with pytest.raises(FileExistsError):
        write_triage_report(outcome, out_dir=str(tmp_path))


def test_creates_missing_out_dir(tmp_path):
    out_dir = tmp_path / "a" / "b"
    outcome = _make_outcome()
    md_path = write_triage_report(outcome, out_dir=str(out_dir))

    md_file = Path(md_path)
    assert md_file.is_file()
    assert md_file.with_suffix(".json").is_file()
    assert md_file.parent == out_dir


def test_sanitizes_malicious_thread_id(tmp_path):
    outcome = _make_outcome(thread_id="../../evil")
    out_dir = tmp_path / "reports"
    md_path = write_triage_report(outcome, out_dir=str(out_dir))

    resolved = Path(md_path).resolve()
    assert resolved.is_relative_to(out_dir.resolve())


def test_sanitizes_malicious_timestamp(tmp_path):
    outcome = _make_outcome(timestamp="2026-07-12T20:10:33/../../evil")
    out_dir = tmp_path / "reports"
    md_path = write_triage_report(outcome, out_dir=str(out_dir))

    resolved = Path(md_path).resolve()
    assert resolved.is_relative_to(out_dir.resolve())


def test_rejects_incomplete_answers():
    answers = {f"q{i}": 1 for i in range(1, 9)}  # only q1..q8, missing q9

    with pytest.raises(ValueError, match="missing answers"):
        TriageOutcome(
            thread_id="thread-abc123",
            timestamp="2026-07-12T20:10:33",
            score=8,
            severity_band="baixo",
            answers=answers,
        )


def test_rejects_extra_answer_keys():
    answers = {f"q{i}": 1 for i in range(1, 10)}
    answers["q10"] = 1

    with pytest.raises(ValueError, match="unexpected answer keys"):
        TriageOutcome(
            thread_id="thread-abc123",
            timestamp="2026-07-12T20:10:33",
            score=9,
            severity_band="baixo",
            answers=answers,
        )


def test_sanitize_thread_id_strips_unsafe_chars_and_truncates():
    assert _sanitize_thread_id("../../evil") == "evil"
    assert _sanitize_thread_id("...") == "sem-id"
    assert _sanitize_thread_id("") == "sem-id"
    assert _sanitize_thread_id("a" * 40) == "a" * 32


def test_report_node_honors_reports_dir_env(tmp_path, monkeypatch):
    # Overrides the offline_env autouse fixture's own TRIAGE_REPORTS_DIR
    # default, to confirm report_node reads the env var at call time rather
    # than a value baked in earlier.
    custom_dir = tmp_path / "algum_subdir"
    monkeypatch.setenv("TRIAGE_REPORTS_DIR", str(custom_dir))

    state = initial_state("irrelevante")
    state["score"] = 15
    state["severity_band"] = "alto"
    state["answers"] = {f"q{i}": 1 for i in range(1, 10)}
    config = {"configurable": {"thread_id": "thread-report-env"}}

    result = report_node(state, config)

    report_path = Path(result["report_path"])
    assert report_path.resolve().is_relative_to(custom_dir.resolve())
    assert report_path.is_file()
