import pytest

from triagem.nodes import score_to_band
from triagem.tools import ScoreResult, compute_pgsi_score


def _answers(values):
    return {f"q{i}": v for i, v in enumerate(values, start=1)}


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([0] * 9, 0),
        ([1] + [0] * 8, 1),
        ([1, 1] + [0] * 7, 2),
        ([1, 1, 1] + [0] * 6, 3),
        ([3, 3, 1] + [0] * 6, 7),
        ([3, 3, 2] + [0] * 6, 8),
        ([3] * 9, 27),
    ],
)
def test_score_boundaries(values, expected):
    result = compute_pgsi_score(_answers(values))
    assert isinstance(result, ScoreResult)
    assert result.score == expected
    assert result.answers == _answers(values)


def test_missing_key_raises():
    answers = _answers([1] * 9)
    del answers["q5"]
    with pytest.raises(ValueError, match="missing answers for: q5"):
        compute_pgsi_score(answers)


def test_extra_key_raises():
    answers = _answers([1] * 9)
    answers["q10"] = 1
    with pytest.raises(ValueError, match="unexpected answer keys: q10"):
        compute_pgsi_score(answers)


@pytest.mark.parametrize("bad", [4, -1, "2", 2.0, True, None])
def test_value_out_of_range_raises(bad):
    answers = _answers([0] * 9)
    answers["q9"] = bad
    with pytest.raises(ValueError, match="q9"):
        compute_pgsi_score(answers)


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (0, "sem_risco"),
        (1, "baixo"),
        (2, "baixo"),
        (3, "moderado"),
        (7, "moderado"),
        (8, "alto"),
        (27, "alto"),
    ],
)
def test_severity_bands(score, band):
    assert score_to_band(score) == band


@pytest.mark.parametrize("bad", [-1, 28, "3", 2.5, True, None])
def test_severity_band_invalid_score_raises(bad):
    with pytest.raises(ValueError):
        score_to_band(bad)
