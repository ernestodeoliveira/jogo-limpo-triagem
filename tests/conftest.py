"""Shared fixtures: the whole suite runs offline with deterministic fakes."""

from uuid import uuid4

import pytest

from triagem.fakes import get_llm
from triagem.graph import build_agent


@pytest.fixture(autouse=True)
def offline_env(monkeypatch):
    """Force offline mode (RNF-02) even on a shell with a real endpoint configured."""
    monkeypatch.setenv("TRIAGE_FAKE_LLM", "1")
    monkeypatch.delenv("TRIAGE_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TRIAGE_LLM_MODEL", raising=False)


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
