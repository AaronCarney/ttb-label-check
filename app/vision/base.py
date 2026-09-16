"""VisionExtractor Protocol + sub-runner shape declarations.

The Protocol is runtime_checkable so substitutability
tests can assert isinstance() without instantiating the heavy sub-runners.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.schemas.extracted import FieldObservation
from app.schemas.label import Label


@runtime_checkable
class VisionExtractor(Protocol):
    """The reader seam. Two concrete impls: cloud + local (docs/decisions/0005)."""

    async def extract(self, label: Label) -> list[FieldObservation]: ...

    async def ensure_loaded(self) -> None:
        """Warm-up hook. Cloud impl: no-op. Local impl: load model weights."""
        ...
