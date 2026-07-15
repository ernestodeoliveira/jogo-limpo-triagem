"""Shared fixtures: the whole suite runs offline with deterministic fakes,
except for tests marked real_llm (F-18), which run against the local model
configured via .env / TRIAGE_LLM_BASE_URL and TRIAGE_LLM_MODEL.
"""

import os
import socket
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from hypothesis import settings

from triagem.fakes import get_llm
from triagem.graph import build_agent

REPO_ROOT = Path(__file__).resolve().parents[1]

# Registered here (not in a specific test module) because conftest.py is
# guaranteed to run before any test module is collected, and this keeps a
# single source of truth if property-based tests spread beyond
# test_parsing.py later. derandomize=True makes the example sequence fixed
# per run (no seed-dependent flakiness in CI or locally); max_examples=200
# is generous for these cheap string properties without becoming slow.
settings.register_profile("deterministic", derandomize=True, max_examples=200)
settings.load_profile("deterministic")


def _load_dotenv_minimal(path: Path) -> None:
    """Minimal KEY=VALUE .env loader for the real_llm tier (decision Q6: no
    python-dotenv dependency). Never overwrites a variable already set in
    the environment, so a real shell export still wins over the file.
    """
    if not path.is_file():
        return
    try:
        contents = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    for line in contents.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip()


@pytest.fixture(autouse=True)
def offline_env(request, monkeypatch, tmp_path):
    """Force offline mode (RNF-02), except for tests opted into the real_llm tier."""
    monkeypatch.setenv("TRIAGE_REPORTS_DIR", str(tmp_path / "reports"))
    if request.node.get_closest_marker("real_llm") is not None:
        return
    monkeypatch.setenv("TRIAGE_FAKE_LLM", "1")
    monkeypatch.delenv("TRIAGE_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TRIAGE_LLM_MODEL", raising=False)
    monkeypatch.delenv("TRIAGE_ALLOW_TRACING", raising=False)


@pytest.fixture
def llm():
    return get_llm()


@pytest.fixture
def app(llm):
    """Compiled triage graph with a fresh InMemorySaver per test."""
    return build_agent(llm)


@pytest.fixture
def config():
    """Unique thread_id per test so checkpointed runs never collide."""
    return {"configurable": {"thread_id": uuid4().hex}}


@pytest.fixture
def real_llm_config():
    """Gate fixture for the real_llm tier (F-18): skip unless the local
    endpoint is configured and actually reachable, so `pytest -m real_llm`
    degrades to skips instead of failures when no server is running.
    """
    _load_dotenv_minimal(REPO_ROOT / ".env")
    base_url = os.environ.get("TRIAGE_LLM_BASE_URL")
    model = os.environ.get("TRIAGE_LLM_MODEL")
    if not base_url or not model:
        pytest.skip(
            "TRIAGE_LLM_BASE_URL/TRIAGE_LLM_MODEL not set; skipping real_llm tier"
        )

    parsed = urlparse(base_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=2):
            pass
    except OSError:
        pytest.skip(
            f"real LLM endpoint {base_url!r} is not reachable; skipping real_llm tier"
        )

    return {"base_url": base_url, "model": model}
