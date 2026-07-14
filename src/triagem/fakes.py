"""Deterministic fakes for offline mode (D-05, RNF-02).

FakeClassifier and FakeAnswerParser mirror the surface used from the real
chat model: with_structured_output(schema) returns a runnable whose invoke()
yields a schema instance. FakeLLM composes both behind a single object,
dispatching by the schema's field names, so build_agent(llm) holds exactly
one llm in both modes. get_llm() is the factory honoring TRIAGE_FAKE_LLM;
the real client targets a local OpenAI-compatible endpoint (decision Q6).
SelfConsistencyLLM wraps that real client with the self-consistency
defense against the intermittent bypass confirmed in F-18
(docs/PARSER_HARDENING_PLAN.md, B-16).
"""

import os
import sys
from urllib.parse import urlparse

from triagem.parsing import majority_vote, normalize, parse_answer_deterministic

LLM_TIMEOUT_SECONDS = 30
LLM_MAX_RETRIES = 2
SELF_CONSISTENCY_SAMPLES = 3

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

_DUVIDA_MARKERS = [
    "o que e",
    "como funciona",
    "para que serve",
    "duvida",
    "explica",
    "privacidade",
    "confidencial",
]
_FORA_DOMINIO_MARKERS = [
    "futebol",
    "placar",
    "receita",
    "clima",
    "filme",
    "musica",
    "noticia",
]
_INICIAR_MARKERS = [
    "comecar",
    "iniciar",
    "quero",
    "vamos",
    "teste",
    "triagem",
    "avaliacao",
    "sim",
]


def _extract_text(input) -> str:
    """Pull the text to decide on: the last message content, like the real model."""
    if isinstance(input, str):
        return input
    if hasattr(input, "to_messages"):
        return _extract_text(input.to_messages())
    if isinstance(input, (list, tuple)) and input:
        last = input[-1]
        if isinstance(last, tuple) and len(last) == 2:
            return str(last[1])
        if isinstance(last, dict) and "content" in last:
            return str(last["content"])
        content = getattr(last, "content", None)
        if content is not None:
            return str(content)
        return str(last)
    return str(input)


def _contains_any(normalized: str, markers: list[str]) -> bool:
    """Whole-word match for single words, substring match for phrases."""
    words = set(normalized.split())
    for marker in markers:
        if " " in marker:
            if marker in normalized:
                return True
        elif marker in words:
            return True
    return False


class _FakeStructuredRunnable:
    """Mimics the runnable returned by ChatOpenAI.with_structured_output(schema)."""

    def __init__(self, schema, decide):
        self._schema = schema
        self._decide = decide

    def invoke(self, input, config=None):
        return self._schema(**self._decide(_extract_text(input)))


class FakeClassifier:
    """Deterministic intent classification by PT-BR keyword table.

    Rule order matters and is part of the contract: duvida beats iniciar so
    "o que e o teste?" is a question, and fora_dominio beats iniciar so
    "quero saber do futebol" stays off-domain.
    """

    def with_structured_output(self, schema, **kwargs):
        return _FakeStructuredRunnable(schema, self._classify)

    @staticmethod
    def _classify(text: str) -> dict:
        normalized = normalize(text)
        if "?" in text or _contains_any(normalized, _DUVIDA_MARKERS):
            return {"intent": "duvida"}
        if _contains_any(normalized, _FORA_DOMINIO_MARKERS):
            return {"intent": "fora_dominio"}
        if _contains_any(normalized, _INICIAR_MARKERS):
            return {"intent": "iniciar"}
        return {"intent": "responder"}


class FakeAnswerParser:
    """Deterministic 0-3 parser by exact match of the full normalized string.

    Exact match keeps "sempre" from swallowing "quase sempre" and makes any
    instruction-like input fall to None instead of being obeyed (D-03).
    This is the offline stand-in for BOTH the deterministic path and the
    make_answer_parser LLM fallback path (T-12): FakeLLM.with_structured_output
    dispatches here for any schema with a "value" field, whether it is called
    directly or invoked as the fallback after a table miss. Because both
    paths reuse the same table, an off-table answer can never be "rescued"
    offline; this is intentional, not a bug, and only the real LLM can
    resolve answers outside ANSWER_TABLE.
    """

    def with_structured_output(self, schema, **kwargs):
        return _FakeStructuredRunnable(schema, self._parse)

    @staticmethod
    def _parse(text: str) -> dict:
        return {"value": parse_answer_deterministic(text)}


class FakeLLM:
    """Single offline stand-in for the real chat model.

    Dispatches with_structured_output to the fake matching the schema's field
    names, so schemas defined later (IntentResult in T-10, the parsing schema
    in T-11) bind to the right behavior without imports in this module.
    """

    def with_structured_output(self, schema, **kwargs):
        fields = getattr(schema, "model_fields", {})
        if "intent" in fields:
            return FakeClassifier().with_structured_output(schema, **kwargs)
        if "value" in fields:
            return FakeAnswerParser().with_structured_output(schema, **kwargs)
        name = getattr(schema, "__name__", repr(schema))
        raise ValueError(f"no fake behavior registered for schema {name}")


class _MajorityVoteRunnable:
    """Calls the wrapped runnable `samples` times and votes on the results."""

    def __init__(self, schema, structured, samples):
        self._schema = schema
        self._structured = structured
        self._samples = samples

    def invoke(self, input, config=None):
        values = [
            self._structured.invoke(input, config).value for _ in range(self._samples)
        ]
        return self._schema(value=majority_vote(values))


class SelfConsistencyLLM:
    """Wraps a chat model with the self-consistency defense (B-16).

    with_structured_output votes across `samples` independent calls for any
    schema with a "value" field (the answer parser); every other schema
    (the intent classifier) passes through with a single call, unaffected
    (scope decision B-17, docs/PARSER_HARDENING_PLAN.md).
    """

    def __init__(self, llm, samples: int = SELF_CONSISTENCY_SAMPLES):
        self.llm = llm
        self._samples = samples

    def with_structured_output(self, schema, **kwargs):
        structured = self.llm.with_structured_output(schema, **kwargs)
        if "value" not in getattr(schema, "model_fields", {}):
            return structured
        return _MajorityVoteRunnable(schema, structured, self._samples)


def _warn_if_non_local_endpoint(base_url: str) -> None:
    """Warn, but do not block, when TRIAGE_LLM_BASE_URL is not a local host (A-02)."""
    host = urlparse(base_url).hostname or ""
    if host.lower() not in _LOCAL_HOSTS:
        print(
            f"Aviso: TRIAGE_LLM_BASE_URL aponta para um host não local ({host!r}). "
            "Respostas dos usuários serão enviadas para esse endpoint.",
            file=sys.stderr,
        )


def get_llm():
    """Factory honoring TRIAGE_FAKE_LLM (RNF-02).

    TRIAGE_FAKE_LLM=1 returns the deterministic FakeLLM; otherwise builds a
    ChatOpenAI client for the local OpenAI-compatible endpoint (decision Q6),
    wrapped in the self-consistency defense against the intermittent bypass
    confirmed in F-18 (B-16, docs/PARSER_HARDENING_PLAN.md).
    """
    if os.environ.get("TRIAGE_FAKE_LLM") == "1":
        return FakeLLM()
    base_url = os.environ.get("TRIAGE_LLM_BASE_URL")
    model = os.environ.get("TRIAGE_LLM_MODEL")
    if not base_url or not model:
        raise RuntimeError(
            "Set TRIAGE_LLM_BASE_URL and TRIAGE_LLM_MODEL for the local endpoint, "
            "or set TRIAGE_FAKE_LLM=1 for offline mode."
        )
    _warn_if_non_local_endpoint(base_url)

    from langchain_openai import ChatOpenAI  # lazy import keeps offline path light

    real_llm = ChatOpenAI(
        base_url=base_url,
        model=model,
        # Local MLX/LM Studio endpoints ignore the key, but the client requires one.
        api_key=os.environ.get("OPENAI_API_KEY", "not-needed"),
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
    )
    return SelfConsistencyLLM(real_llm)
