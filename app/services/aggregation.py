"""Pure min-aggregation: disposition confidence is the min over per-field."""
from __future__ import annotations

from collections.abc import Iterable

from app.schemas.wire.disposition import FieldFindingWire
from app.services.confidence import Band, to_band


def min_aggregate_confidence(fields: Iterable[FieldFindingWire]) -> tuple[Band, float]:
    fields = tuple(fields)
    if not fields:
        return ("low", 0.0)
    numeric = min(f.field_confidence.numeric for f in fields)
    return (to_band(numeric), numeric)
