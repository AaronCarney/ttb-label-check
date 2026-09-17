"""Numeric → Band mapping. The one place these thresholds are written down.

Thresholds (inclusive on the higher band):
- numeric < 0.5  → "low"
- 0.5 ≤ x < 0.85 → "medium"
- 0.85 ≤ x ≤ 1.0 → "high"
"""

from __future__ import annotations

from typing import Literal

Band = Literal["low", "medium", "high"]


def to_band(numeric: float) -> Band:
    if numeric < 0.0 or numeric > 1.0:
        raise ValueError(f"numeric out of [0, 1]: {numeric!r}")
    if numeric >= 0.85:
        return "high"
    if numeric >= 0.5:
        return "medium"
    return "low"
