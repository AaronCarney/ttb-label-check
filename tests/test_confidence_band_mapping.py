"""One place decides the numeric-to-band mapping, so no caller can invent its
own thresholds."""

import pytest

from app.services.confidence import to_band


@pytest.mark.parametrize(
    "numeric, expected",
    [
        (0.0, "low"),
        (0.49, "low"),
        (0.5, "medium"),
        (0.84, "medium"),
        (0.85, "high"),
        (0.92, "high"),
        (1.0, "high"),
    ],
)
def test_to_band_edges(numeric, expected):
    assert to_band(numeric) == expected


def test_to_band_monotonic():
    rank = {"low": 0, "medium": 1, "high": 2}
    last = -1
    for x in [i / 100 for i in range(101)]:
        b = to_band(x)
        assert rank[b] >= last
        last = rank[b]


def test_to_band_rejects_out_of_range():
    with pytest.raises(ValueError):
        to_band(-0.01)
    with pytest.raises(ValueError):
        to_band(1.01)
