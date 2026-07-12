"""Graph nodes for the PGSI triage agent.

Only pure helpers for now; graph wiring lands on day 14 (T-07 onwards).
"""

from typing import Literal

SeverityBand = Literal["sem_risco", "baixo", "moderado", "alto"]


def score_to_band(score: int) -> SeverityBand:
    """Map a PGSI score to its severity band: 0 sem_risco, 1-2 baixo, 3-7 moderado, 8-27 alto."""
    if type(score) is not int or not 0 <= score <= 27:
        raise ValueError(f"score must be an int between 0 and 27, got {score!r}")
    if score == 0:
        return "sem_risco"
    if score <= 2:
        return "baixo"
    if score <= 7:
        return "moderado"
    return "alto"
