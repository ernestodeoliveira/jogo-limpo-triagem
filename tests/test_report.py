import json
import os
import stat
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


def test_json_collision_removes_orphan_md(tmp_path):
    outcome = _make_outcome()
    compact_timestamp = outcome.timestamp.replace("-", "").replace(":", "")
    stem = f"triagem-{_sanitize_thread_id(outcome.thread_id)}-{compact_timestamp}"
    json_path = tmp_path / f"{stem}.json"
    json_path.write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_triage_report(outcome, out_dir=str(tmp_path))

    md_path = tmp_path / f"{stem}.md"
    assert not md_path.exists()  # rollback removed the orphaned .md
    assert json_path.read_text(encoding="utf-8") == "{}"  # pre-existing .json untouched


@pytest.mark.skipif(
    hasattr(os, "getuid") and os.getuid() == 0,
    reason="root ignores directory permission bits, so this check cannot reproduce PermissionError",
)
def test_permission_error_propagates(tmp_path):
    out_dir = tmp_path / "sem_permissao"
    out_dir.mkdir()
    out_dir.chmod(stat.S_IREAD | stat.S_IEXEC)  # read+execute only, no write

    try:
        with pytest.raises(PermissionError):
            write_triage_report(_make_outcome(), out_dir=str(out_dir))
    finally:
        out_dir.chmod(stat.S_IRWXU)  # restore so tmp_path cleanup can remove it


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("thread\x00id", "threadid"),
        ("--evil-flag", "--evil-flag"),
        ("café-com-açúcar", "caf-com-acar"),
        ("😀😀😀", "sem-id"),
        ("CON", "CON"),
        ("NUL.txt", "NULtxt"),
    ],
)
def test_sanitize_thread_id_adversarial_corpus(raw, expected):
    # Documents current behavior (F-14), not asserted vulnerabilities: a
    # leading "--" survives because "-" is an allowed filename char (this
    # value is only ever used as a filename component, never as a CLI
    # argument), and Windows reserved names pass through unchanged because
    # the target platform is POSIX.
    assert _sanitize_thread_id(raw) == expected
