"""Deterministic parsing of PGSI answers (T-11).

Only stdlib here (no internal imports) so fakes.py can import from this
module without creating a cycle. The LLM fallback (T-12) is added later in
this same file, kept out of scope for now.
"""

import re
import unicodedata

ANSWER_TABLE = {
    "0": 0,
    "nunca": 0,
    "nao": 0,
    "jamais": 0,
    "1": 1,
    "as vezes": 1,
    "raramente": 1,
    "de vez em quando": 1,
    "2": 2,
    "na maioria das vezes": 2,
    "frequentemente": 2,
    "3": 3,
    "quase sempre": 3,
    "sempre": 3,
    "toda vez": 3,
}


def normalize(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", stripped)).strip()


def parse_answer_deterministic(text: str) -> int | None:
    """Exact match of the full normalized string; anything else is None (D-03)."""
    return ANSWER_TABLE.get(normalize(text))
